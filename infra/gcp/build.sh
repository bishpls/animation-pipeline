#!/usr/bin/env bash
# The CPU build box, from the laptop (config: infra/gcp/build.env; SSH and rsync go through IAP, the box has no external IP).
# CHARKIT_BOX_ENV names another box's config (infra/gcp/render.env: the GPU box, where boards render); the commands are
# the same.
#   infra/gcp/build.sh up                        start it if stopped and wait until the boot script is done
#   infra/gcp/build.sh ssh [cmd...]              a shell, or one command
#   infra/gcp/build.sh sync WORKTREE             rsync a worktree's code and inputs to /srv/work/<its name> (only changes)
#   infra/gcp/build.sh run WORKTREE cmd...       run a command in that copy, with Blender and the venv (/opt/anim-build/env)
#   infra/gcp/build.sh fetch WORKTREE PATH       rsync PATH (a build's out dir) back into the worktree
#   infra/gcp/build.sh push LOCAL [REMOTE]       rsync a file or directory to the box (default /srv/work/)
#   infra/gcp/build.sh status | stop             it also stops itself after IDLE_MINUTES idle
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); source "${CHARKIT_BOX_ENV:-$HERE/build.env}"
G="gcloud --project=$PROJECT"; Z="--zone=$ZONE"
CFG="$HOME/.ssh/charkit-$VM.config"
config() {  # an ssh config whose ProxyCommand opens the IAP tunnel, so plain ssh and rsync work
  local user; user=$(gcloud compute os-login describe-profile --format='value(posixAccounts[0].username)' 2>/dev/null)
  mkdir -p "$HOME/.ssh"
  cat > "$CFG" <<EOC
Host $VM
  User $user
  IdentityFile ~/.ssh/google_compute_engine
  StrictHostKeyChecking no
  UserKnownHostsFile ~/.ssh/charkit-$VM.known_hosts
  ServerAliveInterval 30
  ProxyCommand gcloud compute start-iap-tunnel $VM 22 --listen-on-stdin --project=$PROJECT --zone=$ZONE --verbosity=warning
EOC
}
ssh_() { [ -f "$CFG" ] || config; ssh -F "$CFG" "$VM" "$@"; }
name() { basename "$(cd "$1" && pwd)"; }
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
    WT=$2; [ -f "$CFG" ] || config
    # a worktree's first sync: seeded by hard links from the most recently synced worktree copy on the box (the tracked
    # files, ~0.3 GB, and charkit/out/i3d, ~0.5 GB, are mostly the same across worktrees), so the tunnel (~1-3 MB/s)
    # carries only what differs; rsync replaces a changed file rather than writing through the shared link. Of the
    # source's outputs only charkit/out/i3d is kept: its builds, caches and produced references are its own
    D="/srv/work/$(name "$WT")"
    ssh_ "[ -d $D ] || { S=\$(ls -td /srv/work/*/charkit 2>/dev/null | grep -v '^/srv/work/repo/' | head -1); \
      [ -z \"\$S\" ] || { cp -al \"\$(dirname \$S)\" $D && \
      find $D/charkit/out -mindepth 1 -maxdepth 1 ! -name i3d -exec rm -rf {} +; }; }"
    # what git ignores stays home (a full worktree's projects/*/out, node_modules, the mocap and bone refs, the env
    # files: 1.7 GB, 15+ min through the tunnel), except the outputs kept above; excluded paths on the box are left alone
    IGN=$(mktemp); { git -C "$WT" ls-files -o -i --exclude-standard --directory | grep -v '^charkit/out' | sed 's|^|/|' || true; } > "$IGN"
    rsync -az --delete -e "ssh -F $CFG" --exclude .git --exclude '__pycache__' --exclude '.cache' \
      --include 'charkit/out/' --include 'charkit/out/i3d/***' --include 'charkit/out/remote/' \
      --include 'charkit/out/remote/*.json' --exclude 'charkit/out/*' --exclude-from="$IGN" \
      "$WT/" "$VM:/srv/work/$(name "$WT")/"; rc=$?; rm -f "$IGN"; exit $rc;;
  run) WT=$2; shift 2; ssh_ "source /opt/anim-build/env && cd /srv/work/$(name "$WT") && $*";;
  push) [ -f "$CFG" ] || config; rsync -az -e "ssh -F $CFG" "$2" "$VM:${3:-/srv/work/}";;
  fetch) WT=$2; P=$3; [ -f "$CFG" ] || config
    mkdir -p "$WT/$P"; rsync -az -e "ssh -F $CFG" "$VM:/srv/work/$(name "$WT")/$P/" "$WT/$P/";;
  stop) $G compute instances stop "$VM" $Z;;
  *) sed -n '2,10p' "$0"; exit 1;;
esac
