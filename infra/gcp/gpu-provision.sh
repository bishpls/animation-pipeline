#!/usr/bin/env bash
# Creates the GPU research box: an isolated VPC (SSH in only through IAP, egress through Cloud NAT, no external IP), a
# service account that can write only its own bucket and logs, the bucket, and the VM. Research repos run arbitrary
# code, so the box shares no network and no credentials with anything else in the project.
# Prints the gcloud commands; --execute runs them. Re-runnable: a step whose resource exists is skipped.
#   infra/gcp/gpu-provision.sh              # read the plan
#   infra/gcp/gpu-provision.sh --execute
# Recreating the box elsewhere (a zone out of GPUs) from its disk snapshot (gpu.sh snapshot), then set ZONE in gpu.env
# and render.env to the new zone:
#   infra/gcp/gpu-provision.sh --zone Z --from-snapshot NAME [--machine-type M] [--subnet-range R] [--execute]
#   (another region needs its own --subnet-range: subnets in one VPC can't overlap; M = FALLBACK_MACHINE_TYPE adds
#   FALLBACK_GPU)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source "$HERE/gpu.env"
EXEC=0; SNAP=; RANGE_SET=0; HOME_REGION=$REGION
while [ $# -gt 0 ]; do
  case $1 in
    --execute) EXEC=1;;
    --zone) ZONE=$2; REGION=${2%-*}; shift;;
    --from-snapshot) SNAP=$2; shift;;
    --machine-type) MACHINE_TYPE=$2; shift;;
    --subnet-range) SUBNET_RANGE=$2; RANGE_SET=1; shift;;
    *) sed -n '2,13p' "$0"; exit 1;;
  esac; shift
done
if [ "$REGION" != "$HOME_REGION" ] && [ $RANGE_SET = 0 ]; then
  echo "$REGION isn't $HOME_REGION: pass --subnet-range (not $SUBNET_RANGE, which $HOME_REGION's subnet has)" >&2; exit 1
fi
BOOT=(--image-family="$IMAGE_FAMILY" --image-project=deeplearning-platform-release)
[ -n "$SNAP" ] && BOOT=(--source-snapshot="$SNAP")
GPU=()
[ "$MACHINE_TYPE" = "${FALLBACK_MACHINE_TYPE:-}" ] && GPU=(--accelerator="type=$FALLBACK_GPU,count=1")
SA="$SA_NAME@$PROJECT.iam.gserviceaccount.com"
G="gcloud --project=$PROJECT --quiet"
SUBNET="$NETWORK-$REGION"; ROUTER="$NETWORK-router"; TAG=anim-gpu

step() {  # step "what" "existence check (or empty)" command...
  local what=$1 check=$2; shift 2
  echo "## $what"; echo "   $*"
  [ $EXEC = 1 ] || return 0
  if [ -n "$check" ] && eval "$check" >/dev/null 2>&1; then echo "   (exists, skipped)"; return 0; fi
  "$@"
}

step "VPC" "$G compute networks describe $NETWORK" \
  $G compute networks create "$NETWORK" --subnet-mode=custom --description="animation-pipeline GPU research box; isolated"
step "subnet" "$G compute networks subnets describe $SUBNET --region=$REGION" \
  $G compute networks subnets create "$SUBNET" --network="$NETWORK" --region="$REGION" --range="$SUBNET_RANGE" \
  --enable-private-ip-google-access
step "router" "$G compute routers describe $ROUTER --region=$REGION" \
  $G compute routers create "$ROUTER" --network="$NETWORK" --region="$REGION"
step "NAT (egress for pip, git, Hugging Face)" "$G compute routers nats describe $NETWORK-nat --router=$ROUTER --region=$REGION" \
  $G compute routers nats create "$NETWORK-nat" --router="$ROUTER" --region="$REGION" \
  --auto-allocate-nat-external-ips --nat-all-subnet-ip-ranges
step "firewall: SSH from IAP only" "$G compute firewall-rules describe $NETWORK-allow-iap-ssh" \
  $G compute firewall-rules create "$NETWORK-allow-iap-ssh" --network="$NETWORK" --direction=INGRESS \
  --source-ranges=35.235.240.0/20 --allow=tcp:22 --target-tags="$TAG"
step "service account" "$G iam service-accounts describe $SA" \
  $G iam service-accounts create "$SA_NAME" --display-name="animation-pipeline GPU box (own bucket + logs only)"
step "SA: write logs" "" \
  $G projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$SA" --role=roles/logging.logWriter --condition=None
step "SA: write metrics" "" \
  $G projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$SA" --role=roles/monitoring.metricWriter --condition=None
step "bucket" "gcloud storage buckets describe $BUCKET" \
  gcloud storage buckets create "$BUCKET" --project="$PROJECT" --location="$REGION" --uniform-bucket-level-access \
  --public-access-prevention
step "SA: its bucket" "" \
  gcloud storage buckets add-iam-policy-binding "$BUCKET" --member="serviceAccount:$SA" --role=roles/storage.objectAdmin
step "VM" "$G compute instances describe $VM --zone=$ZONE" \
  $G compute instances create "$VM" --zone="$ZONE" --machine-type="$MACHINE_TYPE" \
  "${BOOT[@]}" ${GPU[@]+"${GPU[@]}"} \
  --boot-disk-size="${DISK_GB}GB" --boot-disk-type=pd-balanced \
  --network="$NETWORK" --subnet="$SUBNET" --no-address --tags="$TAG" \
  --service-account="$SA" --scopes=cloud-platform \
  --maintenance-policy=TERMINATE --provisioning-model=STANDARD \
  --shielded-vtpm --shielded-integrity-monitoring --labels="$LABELS" \
  --metadata=enable-oslogin=TRUE,install-nvidia-driver=True,idle-minutes="$IDLE_MINUTES",bucket="$BUCKET" \
  --metadata-from-file=startup-script="$HERE/gpu-startup.sh"

[ $EXEC = 1 ] && echo "done: infra/gcp/gpu.sh up" || echo "(plan only; --execute to run)"
