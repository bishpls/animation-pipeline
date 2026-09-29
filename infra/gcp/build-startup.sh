#!/usr/bin/env bash
# Boot script for the CPU build box (root, every boot, idempotent): Blender headless at the laptop's version, a Python
# venv with charkit's packages (/opt/anim-build/venv), a shared work dir (/srv/work: one directory per synced worktree),
# and an idle stop. /opt/anim-build/env sets BLENDER and the venv for a build.
set -uo pipefail
exec > >(tee -a /var/log/anim-build-startup.log) 2>&1
echo "== anim-build startup $(date -Is)"
MD=http://metadata.google.internal/computeMetadata/v1/instance/attributes
md() { curl -sf -H Metadata-Flavor:Google "$MD/$1"; }
BV=$(md blender-version || echo 5.2.2)
PV=$(md python-version || echo 3.14)
IDLE=$(md idle-minutes || echo 30)

if [ ! -f /opt/anim-build/.base ]; then
  mkdir -p /opt/anim-build /srv/work && chmod 1777 /srv/work
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  # Blender headless: its X and GL client libraries (no display needed in background mode)
  apt-get install -y git rsync tmux htop jq xz-utils curl build-essential libgl1 libegl1 libglib2.0-0 libxi6 \
    libxkbcommon0 libxrender1 libsm6 libxxf86vm1 libxfixes3 libxext6 libx11-6 libxcursor1 libxinerama1 libxrandr2
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
  touch /opt/anim-build/.base
fi

if [ ! -x /opt/blender/blender ] || ! /opt/blender/blender --version 2>/dev/null | grep -q "Blender $BV"; then
  MM=$(echo "$BV" | cut -d. -f1,2)
  curl -fL "https://download.blender.org/release/Blender$MM/blender-$BV-linux-x64.tar.xz" -o /tmp/blender.tar.xz \
    && rm -rf /opt/blender && mkdir -p /opt/blender \
    && tar -xJf /tmp/blender.tar.xz -C /opt/blender --strip-components=1 && rm -f /tmp/blender.tar.xz
fi

# uv's managed Python under /opt (its default is root's home, which a login user can't read through the venv's link)
export UV_PYTHON_INSTALL_DIR=/opt/anim-build/python
if [ ! -x /opt/anim-build/venv/bin/python ] || ! readlink -f /opt/anim-build/venv/bin/python | grep -q '^/opt/'; then
  rm -rf /opt/anim-build/venv
  uv venv --python "$PV" /opt/anim-build/venv
  VIRTUAL_ENV=/opt/anim-build/venv uv pip install numpy scipy scikit-image numba pillow manifold3d matplotlib \
    opencv-python-headless pytest
fi

printf '%s\n' 'export BLENDER=/opt/blender/blender' 'export VIRTUAL_ENV=/opt/anim-build/venv' \
  'export PATH=/opt/anim-build/venv/bin:$PATH' > /opt/anim-build/env
chmod 644 /opt/anim-build/env

# Idle stop: no login session, 5-min load under 1, no charkit process, and no keepalive touched in the last 2 h
# (touch /srv/work/.keepalive before a long job). Stopping keeps the disk; `build.sh up` starts it again.
mkdir -p /var/lib/anim-build-idle
printf '%s\n' '#!/usr/bin/env bash' \
  'S=/var/lib/anim-build-idle; busy=0' \
  '[ "$(who | wc -l)" -gt 0 ] && busy=1' \
  'awk '"'"'{exit !($2 >= 1.0)}'"'"' /proc/loadavg && busy=1' \
  'pgrep -f charkit >/dev/null && busy=1' \
  '[ -f /srv/work/.keepalive ] && [ $(( $(date +%s) - $(stat -c %Y /srv/work/.keepalive) )) -lt 7200 ] && busy=1' \
  'if [ $busy = 1 ] || [ ! -f $S/last_busy ]; then date +%s > $S/last_busy; exit 0; fi' \
  "if [ \$(( (\$(date +%s) - \$(cat \$S/last_busy)) / 60 )) -ge $IDLE ]; then" \
  "  logger -t anim-build-idle 'idle $IDLE min: stopping'; rm -f \$S/last_busy; shutdown -h now" \
  'fi' > /usr/local/sbin/anim-build-idle
chmod +x /usr/local/sbin/anim-build-idle
date +%s > /var/lib/anim-build-idle/last_busy
printf '%s\n' '[Unit]' 'Description=anim-build idle check' '[Service]' 'Type=oneshot' \
  'ExecStart=/usr/local/sbin/anim-build-idle' > /etc/systemd/system/anim-build-idle.service
printf '%s\n' '[Unit]' 'Description=anim-build idle check every 5 minutes' '[Timer]' 'OnBootSec=10min' \
  'OnUnitActiveSec=5min' '[Install]' 'WantedBy=timers.target' > /etc/systemd/system/anim-build-idle.timer
systemctl daemon-reload && systemctl enable --now anim-build-idle.timer

/opt/blender/blender --version | head -1 || echo "Blender missing"
/opt/anim-build/venv/bin/python -c "import numpy, scipy, numba, skimage; print('venv ok')" || echo "venv broken"
touch /opt/anim-build/READY
echo "== anim-build ready $(date -Is)"
