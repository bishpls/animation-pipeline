#!/usr/bin/env bash
# Box control through a service account, without moving the box's state. Everything on a box (/srv/work, its worktree
# copies, the detached jobs in /srv/work/.jobs, the build slots, the crontab's load sampler) belongs to one Unix user,
# the owner's (BOX_OWNER in the env file). The service account's own OS Login user is a different one, so sshd runs
# that user's sessions as the owner: a Match block (ForceCommand) and a wrapper that sudoes to the owner. Plain ssh
# commands, rsync, scp/sftp and the job supervisor then behave as they did under the owner's login.
#   infra/gcp/as-owner.sh install   the wrapper (/usr/local/bin/charkit-as-owner) and the Match block
#                                   (/etc/ssh/sshd_config.d/90-charkit-as-owner.conf): sshd -t checks it, then ssh reloads
#                                   (open sessions stay; a failed check puts the old files back)
#   infra/gcp/as-owner.sh remove    both removed, ssh reloaded: the service account logs in as itself again
#   infra/gcp/as-owner.sh status    who the active gcloud account's sessions run as
# Run from the laptop with the service account's gcloud config (CLOUDSDK_CONFIG, which the env file exports). The first
# install logs in as the service account itself (OS Login admin: sudo); later ones log in through the wrapper, as the
# owner, whose sudo does the same. Both files are on the box's disk, outside what the boot scripts and the guest agent
# write (the agent edits only its section of /etc/ssh/sshd_config), so they survive reboots. CHARKIT_BOX_ENV picks the
# box's env file (default build.env). The owner's own login is unchanged throughout.
set -euo pipefail
W=/usr/local/bin/charkit-as-owner
C=/etc/ssh/sshd_config.d/90-charkit-as-owner.conf

if [ "${1:-}" = box ]; then                     # on the box, as root: box install|remove SA_USER OWNER
  op=$2 sa=$3 owner=$4
  case "$op" in
    install)
      id "$owner" >/dev/null && id "$sa" >/dev/null
      [ "$sa" != "$owner" ] || { echo "the service account's user is the owner" >&2; exit 1; }
      cat > "$W.new" <<EOW
#!/bin/bash
# charkit (infra/gcp/as-owner.sh): sshd runs this for the box-control service account's sessions (ForceCommand in
# $C), so each runs as $owner, who owns the box's work, jobs and slots. Undo: infra/gcp/as-owner.sh remove.
OWNER=$owner
H=\$(getent passwd "\$OWNER" | cut -d: -f6); cd "\${H:-/}" 2>/dev/null || cd /
# no command: a login shell; otherwise the command as sshd would run it under the owner's login (sftp included:
# SSH_ORIGINAL_COMMAND is then the sftp server's path)
[ -n "\${SSH_ORIGINAL_COMMAND:-}" ] || exec sudo -n -u "\$OWNER" -i
exec sudo -n -u "\$OWNER" -H -- bash -c "\$SSH_ORIGINAL_COMMAND"
EOW
      chmod 755 "$W.new" && mv "$W.new" "$W"
      [ -f "$C" ] && cp -p "$C" "$C.bak"
      printf '# charkit (infra/gcp/as-owner.sh): the box-control service account runs as %s. Remove this file and\n# reload ssh to undo.\nMatch User %s\n    ForceCommand %s\n' \
        "$owner" "$sa" "$W" > "$C.new"
      mv "$C.new" "$C"
      if ! sshd -t; then
        echo "sshd -t failed: the old config put back" >&2
        if [ -f "$C.bak" ]; then mv "$C.bak" "$C"; else rm -f "$C"; fi
        exit 1
      fi
      rm -f "$C.bak"
      systemctl reload ssh
      echo "installed: $sa runs as $owner (forcecommand for $sa: $(sshd -T -C user="$sa",host=x,addr=127.0.0.1 | grep -i '^forcecommand' || echo none))";;
    remove)
      rm -f "$C" && sshd -t && systemctl reload ssh && rm -f "$W"
      echo "removed: $sa logs in as itself";;
  esac
  exit 0
fi

HERE=$(cd "$(dirname "$0")" && pwd); source "${CHARKIT_BOX_ENV:-$HERE/build.env}"
: "${BOX_OWNER:?set BOX_OWNER in the env file: the posix user who owns the box state}"
me=$(gcloud compute os-login describe-profile --format='value(posixAccounts[0].username)') || true
[ -n "$me" ] || { echo "no OS Login profile for the active gcloud account (CLOUDSDK_CONFIG=${CLOUDSDK_CONFIG:-unset})" >&2; exit 1; }
[ "$me" != "$BOX_OWNER" ] || { echo "the active gcloud account is the owner itself: set CLOUDSDK_CONFIG to the service account's" >&2; exit 1; }
CFG=$(mktemp); trap 'rm -f "$CFG"' EXIT
cat > "$CFG" <<EOC
Host $VM
  User $me
  IdentityFile ~/.ssh/google_compute_engine
  StrictHostKeyChecking no
  UserKnownHostsFile ~/.ssh/charkit-$VM.known_hosts
  ProxyCommand env ${CLOUDSDK_CONFIG:+CLOUDSDK_CONFIG=$CLOUDSDK_CONFIG} gcloud compute start-iap-tunnel $VM 22 --listen-on-stdin --project=$PROJECT --zone=$ZONE --verbosity=warning
EOC
case "${1:-status}" in
  install|remove) ssh -F "$CFG" "$VM" "sudo -n bash -s -- box $1 $me $BOX_OWNER" < "$0";;
  status) ssh -F "$CFG" "$VM" 'echo "$(id -un) (login as '"$me"'), in $(pwd)"';;
  *) sed -n '2,17p' "$0"; exit 1;;
esac
