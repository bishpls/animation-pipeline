# Start a box, preferring its own machine shape and falling back to another GPU when the zone is out of it (a
# stockout). Sourced by gpu.sh and build.sh after their env file. It uses PROJECT, ZONE and VM from the env file, and:
#   MACHINE_TYPE           the preferred shape (g2-standard-8)
#   MACHINE_GPU            its GPU (nvidia-l4; a G2 must keep it)
#   FALLBACK_MACHINE_TYPE  the shape to switch to on a stockout (n1-standard-8); unset for no fallback
#   FALLBACK_GPU           the GPU attached with it (nvidia-tesla-t4)
# A shape is switched only while the VM is stopped, and the disk, network and setup stay. Each start from stopped
# tries the preferred shape first, so the box goes back to it once the zone has stock again.
#   box_start      start if stopped, and print the shape it runs as. Status 2: every shape is stocked out.
#                  BOX_SHAPES="n1-standard-8" overrides the order (to test or time the fallback while the L4 is in stock).

_gc() { gcloud --project="$PROJECT" --quiet "$@"; }
_state() { _gc compute instances describe "$VM" --zone="$ZONE" --format="value(${1:-status})"; }

_shape() {  # _shape MACHINE_TYPE: switch the stopped VM to it, with its GPU (reshape.py: both in one update)
  local now g=${MACHINE_GPU:-}; now=$(_state 'machineType.basename()')
  [ "$now" = "$1" ] && return 0
  echo "switching $VM: $now -> $1" >&2
  [ "$1" = "${FALLBACK_MACHINE_TYPE:-}" ] && g=$FALLBACK_GPU
  python3 "$(dirname "${BASH_SOURCE[0]}")/reshape.py" "$PROJECT" "$ZONE" "$VM" "$1" $g
}

box_start() {
  local st
  # an unreadable state is gcloud, not the box: say so rather than go on to a misleading "could not switch"
  st=$(_state 2>&1) || { echo "can't read $VM's state from gcloud: ${st##*ERROR: }" >&2
    if [ -n "${CLOUDSDK_CONFIG:-}" ]; then echo "(the service account's gcloud config $CLOUDSDK_CONFIG: docs/workstreams/infra-auth.md)" >&2
    else echo "(expired login? run: gcloud auth login)" >&2; fi; return 1; }
  [ "$st" = RUNNING ] && { echo "running as $(_state 'machineType.basename()')"; return 0; }
  local shape err
  for shape in ${BOX_SHAPES:-${MACHINE_TYPE:-} ${FALLBACK_MACHINE_TYPE:-}}; do
    _shape "$shape" || { echo "could not switch $VM to $shape" >&2; return 1; }
    if err=$(_gc compute instances start "$VM" --zone="$ZONE" 2>&1); then echo "started as $shape"; return 0; fi
    if ! echo "$err" | grep -q 'RESOURCE_POOL_EXHAUSTED\|STOCKOUT'; then echo "$err" >&2; return 1; fi
    echo "no $shape capacity in $ZONE right now (a stockout)" >&2
  done
  [ -n "${MACHINE_TYPE:-}" ] || { _gc compute instances start "$VM" --zone="$ZONE"; return; }
  return 2
}
