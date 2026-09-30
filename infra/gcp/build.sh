#!/usr/bin/env bash
# The CPU build box, from the laptop (config: infra/gcp/build.env; SSH goes through IAP, the box has no external IP).
# CHARKIT_BOX_ENV names another box's config (infra/gcp/render.env: the GPU box, where boards render); the commands are
# the same. Bulk data goes through the box's bucket (charkit/bucketsync.py: content-addressed, only missing blobs move);
# CHARKIT_SYNC=rsync sends it through the IAP tunnel as before.
#   infra/gcp/build.sh up                        start it if stopped and wait until the boot script is done
#   infra/gcp/build.sh ssh [cmd...]              a shell, or one command
#   infra/gcp/build.sh sync WORKTREE             a worktree's code and inputs to /srv/work/<its name> (only changes)
#   infra/gcp/build.sh run WORKTREE cmd...       run a command in that copy, with Blender and the venv (/opt/anim-build/env)
#   infra/gcp/build.sh fetch WORKTREE PATH       PATH (a build's out dir) back into the worktree (only what differs)
#   infra/gcp/build.sh push LOCAL [REMOTE] [--link]  a file or directory to the box (default /srv/work/); --link: inputs
#   infra/gcp/build.sh pull NAME LOCAL           a tree the box published under NAME (bucketsync publish --name)
#   infra/gcp/build.sh verify WORKTREE           check the box's copy against the worktree, file by file
#   infra/gcp/build.sh status | stop             it also stops itself after IDLE_MINUTES idle
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); source "${CHARKIT_BOX_ENV:-$HERE/build.env}"
G="gcloud --project=$PROJECT"; Z="--zone=$ZONE"
CFG="$HOME/.ssh/charkit-$VM.config"
# the gcloud config the box calls use: the env file's CLOUDSDK_CONFIG (the box-control service account's, which never
# needs a reauth), else the default login. The ssh config names it in its ProxyCommand, so any `ssh -F` works without it
# in the environment, and is rewritten when it changes (fresh), with the account's OS Login user
GC="${CLOUDSDK_CONFIG:-default}"
fresh() { [ -f "$CFG" ] && grep -qxF "# gcloud: $GC" "$CFG"; }
config() {  # an ssh config whose ProxyCommand opens the IAP tunnel, so plain ssh and rsync work
  local user; user=$(gcloud compute os-login describe-profile --format='value(posixAccounts[0].username)' 2>/dev/null) || true
  [ -n "$user" ] || { echo "gcloud can't read the OS Login profile (config $GC): $(auth_hint)" >&2; exit 1; }
  mkdir -p "$HOME/.ssh"
  cat > "$CFG.$$" <<EOC
# gcloud: $GC
Host $VM
  User $user
  IdentityFile ~/.ssh/google_compute_engine
  StrictHostKeyChecking no
  UserKnownHostsFile ~/.ssh/charkit-$VM.known_hosts
  ServerAliveInterval 30
  ProxyCommand env ${CLOUDSDK_CONFIG:+CLOUDSDK_CONFIG=$CLOUDSDK_CONFIG }gcloud compute start-iap-tunnel $VM 22 --listen-on-stdin --project=$PROJECT --zone=$ZONE --verbosity=warning
EOC
  mv "$CFG.$$" "$CFG"
}
auth_hint() {  # what to run when gcloud can't act (one line)
  if [ -n "${CLOUDSDK_CONFIG:-}" ]; then echo "the service account's config $CLOUDSDK_CONFIG has no working key: see docs/workstreams/infra-auth.md"
  else echo "run: gcloud auth login"; fi
}
ssh_() { fresh || config; ssh -F "$CFG" "$VM" "$@"; }
name() { basename "$(cd "$1" && pwd)"; }
# bulk data through the bucket (charkit/bucketsync.py, standard library: any python3); the rsync paths below remain
BS="$HERE/../../charkit/bucketsync.py"
bucket() { [ "${CHARKIT_SYNC:-bucket}" != rsync ] && [ -n "${BUCKET:-}" ] && [ -f "$BS" ]; }
bs() { fresh || config; BUCKET=$BUCKET VM=$VM BS_SSHCFG=$CFG "${CHARKIT_PY:-python3}" "$BS" "$@"; }
case "${1:-status}" in
  status) $G compute instances describe "$VM" $Z --format="table(status,machineType.basename(),lastStartTimestamp,lastStopTimestamp)";;
  up)
    source "$HERE/gpu-start.sh"
    box_start || { rc=$?; [ $rc = 2 ] && echo "no capacity in $ZONE for any shape (a stockout, not a fault): retry in a few minutes" >&2; exit $rc; }
    [ -f "$HOME/.ssh/google_compute_engine" ] || $G compute ssh "$VM" $Z --tunnel-through-iap --command=true
    config
    for _ in $(seq 1 60); do
      ssh_ -o ConnectTimeout=15 "test -f /opt/anim-build/READY" 2>/dev/null && { echo ready; exit 0; }
      sleep 15
    done
    echo "not ready after 15 min: infra/gcp/build.sh ssh 'sudo tail -40 /var/log/anim-build-startup.log'"; exit 1;;
  ssh) shift; ssh_ "$@";;
  sync)
    WT=$2; fresh || config
    # through the bucket: blobs by sha256, uploaded once for every worktree and box; the box links its copy from its blob
    # cache and deletes what the worktree no longer has, under the same excludes as the rsync below
    if bucket; then bs sync "$WT" "/srv/work/$(name "$WT")"; exit $?; fi
    # a worktree's first sync: seeded by hard links from the most recently synced worktree copy on the box (the tracked
    # files, ~0.3 GB, are mostly the same across worktrees), so the tunnel (~1-3 MB/s) carries only what differs; rsync
    # replaces a changed file rather than writing through the shared link. None of the source's outputs is kept: its
    # builds, caches and produced references are its own (charkit/out/i3d, TRELLIS's output, isn't sent any more: no
    # build reads it since the sheet-only outfit masks, decision 8; a copy's own is left alone)
    D="/srv/work/$(name "$WT")"
    ssh_ "[ -d $D ] || { S=\$(ls -td /srv/work/*/charkit 2>/dev/null | grep -v '^/srv/work/repo/' | head -1); \
      [ -z \"\$S\" ] || { cp -al \"\$(dirname \$S)\" $D && \
      find $D/charkit/out -mindepth 1 -maxdepth 1 -exec rm -rf {} +; }; }"
    # what git ignores stays home (a full worktree's projects/*/out, node_modules, the mocap and bone refs, the env
    # files: 1.7 GB, 15+ min through the tunnel); excluded paths on the box are left alone
    IGN=$(mktemp); { git -C "$WT" ls-files -o -i --exclude-standard --directory | grep -v '^charkit/out' | sed 's|^|/|' || true; } > "$IGN"
    rsync -az --delete -e "ssh -F $CFG" --exclude .git --exclude '__pycache__' --exclude '.cache' \
      --include 'charkit/out/' --include 'charkit/out/remote/' \
      --include 'charkit/out/remote/*.json' --exclude 'charkit/out/*' --exclude-from="$IGN" \
      "$WT/" "$VM:/srv/work/$(name "$WT")/"; rc=$?; rm -f "$IGN"; exit $rc;;
  run) WT=$2; shift 2; ssh_ "source /opt/anim-build/env && cd /srv/work/$(name "$WT") && $*";;
  push) fresh || config
    if bucket; then bs push "$2" "${3:-/srv/work/}" ${4:+"$4"}; exit $?; fi
    rsync -az -e "ssh -F $CFG" "$2" "$VM:${3:-/srv/work/}";;
  fetch) WT=$2; P=$3; fresh || config
    if bucket; then bs fetch "/srv/work/$(name "$WT")/$P" "$WT/$P"; exit $?; fi
    mkdir -p "$WT/$P"; rsync -az -e "ssh -F $CFG" "$VM:/srv/work/$(name "$WT")/$P/" "$WT/$P/";;
  pull) bs pull "$2" "$3";;
  verify) bs verify "$2" "/srv/work/$(name "$2")";;
  stop) $G compute instances stop "$VM" $Z;;
  *) sed -n '2,14p' "$0"; exit 1;;
esac
