#!/usr/bin/env bash
# Boot script for the GPU research box (root, every boot, idempotent): base tools, uv, a shared work dir, and a
# GPU-aware idle stop. Research repos get their own uv/venv environments under /srv/work; nothing is installed globally.
set -uo pipefail
exec > >(tee -a /var/log/anim-gpu-startup.log) 2>&1
echo "== anim-gpu startup $(date -Is)"
MD=http://metadata.google.internal/computeMetadata/v1/instance/attributes
md() { curl -sf -H Metadata-Flavor:Google "$MD/$1"; }

if [ ! -f /opt/anim-gpu/.base ]; then
  mkdir -p /opt/anim-gpu /srv/work && chmod 1777 /srv/work
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y ffmpeg git git-lfs tmux htop jq unzip build-essential libgl1 libglib2.0-0 libegl1 libosmesa6
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
  touch /opt/anim-gpu/.base
fi

# Idle stop: no login session, GPU under 5%, 5-min load under 1, and no keepalive touched in the last 2 h
# (touch /srv/work/.keepalive before a long download). Stopping keeps the disk; `gpu.sh up` starts it again.
IDLE=$(md idle-minutes || echo 30)
cat > /usr/local/sbin/anim-gpu-idle <<EOF
#!/usr/bin/env bash
S=/var/lib/anim-gpu-idle; mkdir -p \$S; busy=0
[ "\$(who | wc -l)" -gt 0 ] && busy=1
u=\$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | sort -n | tail -1)
[ "\${u:-0}" -gt 5 ] && busy=1
awk '{exit !(\$2 >= 1.0)}' /proc/loadavg && busy=1
[ -f /srv/work/.keepalive ] && [ \$(( \$(date +%s) - \$(stat -c %Y /srv/work/.keepalive) )) -lt 7200 ] && busy=1
if [ \$busy = 1 ] || [ ! -f \$S/last_busy ]; then date +%s > \$S/last_busy; exit 0; fi
if [ \$(( (\$(date +%s) - \$(cat \$S/last_busy)) / 60 )) -ge $IDLE ]; then
  logger -t anim-gpu-idle "idle $IDLE min: stopping"; rm -f \$S/last_busy; shutdown -h now
fi
EOF
chmod +x /usr/local/sbin/anim-gpu-idle
mkdir -p /var/lib/anim-gpu-idle && date +%s > /var/lib/anim-gpu-idle/last_busy
cat > /etc/systemd/system/anim-gpu-idle.service <<'EOF'
[Unit]
Description=anim-gpu idle check
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/anim-gpu-idle
EOF
cat > /etc/systemd/system/anim-gpu-idle.timer <<'EOF'
[Unit]
Description=anim-gpu idle check every 5 minutes
[Timer]
OnBootSec=10min
OnUnitActiveSec=5min
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload && systemctl enable --now anim-gpu-idle.timer

nvidia-smi -L || echo "no GPU visible yet (driver still installing?)"
touch /opt/anim-gpu/READY
echo "== anim-gpu ready $(date -Is)"
