#!/usr/bin/env bash
# Creates the CPU build box in the GPU box's isolated VPC (gpu-provision.sh makes the VPC, NAT, service account and
# bucket): SSH in only through IAP, egress through Cloud NAT, no external IP. Prints the gcloud commands; --execute runs
# them. Re-runnable: a step whose resource exists is skipped.
#   infra/gcp/build-provision.sh              # read the plan
#   infra/gcp/build-provision.sh --execute
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source "$HERE/build.env"
EXEC=0; [ "${1:-}" = "--execute" ] && EXEC=1
SA="$SA_NAME@$PROJECT.iam.gserviceaccount.com"
G="gcloud --project=$PROJECT --quiet"
SUBNET="$NETWORK-$REGION"; TAG=anim-build

step() {  # step "what" "existence check (or empty)" command...
  local what=$1 check=$2; shift 2
  echo "## $what"; echo "   $*"
  [ $EXEC = 1 ] || return 0
  if [ -n "$check" ] && eval "$check" >/dev/null 2>&1; then echo "   (exists, skipped)"; return 0; fi
  "$@"
}

step "the VPC exists (gpu-provision.sh)" "" $G compute networks describe "$NETWORK" --format="value(name)"
step "firewall: SSH from IAP only, to the build box" "$G compute firewall-rules describe $NETWORK-allow-iap-ssh-build" \
  $G compute firewall-rules create "$NETWORK-allow-iap-ssh-build" --network="$NETWORK" --direction=INGRESS \
  --source-ranges=35.235.240.0/20 --allow=tcp:22 --target-tags="$TAG"
step "VM" "$G compute instances describe $VM --zone=$ZONE" \
  $G compute instances create "$VM" --zone="$ZONE" --machine-type="$MACHINE_TYPE" \
  --image-family="$IMAGE_FAMILY" --image-project="$IMAGE_PROJECT" \
  --boot-disk-size="${DISK_GB}GB" --boot-disk-type=pd-balanced \
  --network="$NETWORK" --subnet="$SUBNET" --no-address --tags="$TAG" \
  --service-account="$SA" --scopes=cloud-platform \
  --shielded-vtpm --shielded-integrity-monitoring --labels="$LABELS" \
  --metadata=enable-oslogin=TRUE,idle-minutes="$IDLE_MINUTES",blender-version="$BLENDER_VERSION",python-version="$PYTHON_VERSION" \
  --metadata-from-file=startup-script="$HERE/build-startup.sh"

[ $EXEC = 1 ] && echo "done: infra/gcp/build.sh up" || echo "(plan only; --execute to run)"
