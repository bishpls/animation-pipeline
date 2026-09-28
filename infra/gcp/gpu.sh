#!/usr/bin/env bash
# The GPU research box, from the laptop (config: infra/gcp/gpu.env; SSH goes through IAP, the box has no external IP).
#   infra/gcp/gpu.sh up                     start it if stopped and wait until the boot script is done
#   infra/gcp/gpu.sh ssh [cmd...]           a shell, or one command
#   infra/gcp/gpu.sh push LOCAL [REMOTE]    copy to the box (default /srv/work/)
#   infra/gcp/gpu.sh pull REMOTE [LOCAL]    copy back (default .)
#   infra/gcp/gpu.sh status | stop          it also stops itself after IDLE_MINUTES idle
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); source "$HERE/gpu.env"
G="gcloud --project=$PROJECT"; Z="--zone=$ZONE"
ssh_() { $G compute ssh "$VM" $Z --tunnel-through-iap "$@"; }
case "${1:-status}" in
  status) $G compute instances describe "$VM" $Z --format="table(status,machineType.basename(),lastStartTimestamp,lastStopTimestamp)";;
  up)
    [ "$($G compute instances describe "$VM" $Z --format='value(status)')" = RUNNING ] || $G compute instances start "$VM" $Z
    for _ in $(seq 1 40); do
      ssh_ --command="test -f /opt/anim-gpu/READY" -- -o ConnectTimeout=10 -o StrictHostKeyChecking=no 2>/dev/null && { echo ready; exit 0; }
      sleep 15
    done
    echo "not ready after 10 min: infra/gcp/gpu.sh ssh 'tail -40 /var/log/anim-gpu-startup.log'"; exit 1;;
  ssh) shift; if [ $# -gt 0 ]; then ssh_ --command="$*"; else ssh_; fi;;
  push) $G compute scp $Z --tunnel-through-iap --recurse "$2" "$VM:${3:-/srv/work/}";;
  pull) $G compute scp $Z --tunnel-through-iap --recurse "$VM:$2" "${3:-.}";;
  stop) $G compute instances stop "$VM" $Z;;
  *) sed -n '2,7p' "$0"; exit 1;;
esac
