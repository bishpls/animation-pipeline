#!/usr/bin/env bash
# GEM-X on the GPU box (docs/PIPELINE_3D.md §2): push directed reference clips (one dancer, locked camera), run GEM-X's full offline
# pipeline in static-camera mode, convert each result into our canonical clip (tools/mocap3d/soma_clip.py) and pull it back.
#     tools/mocap3d/gemx_remote.sh [--out DIR] CLIP.mp4 [CLIP.mp4 ...]    # DIR defaults to projects/clawd3d/refs/mocap
#     tools/mocap3d/gemx_remote.sh --install                               # once per box: GEM-X, SOMA-X, detectron2, the weights
# Per clip, in DIR: <name>.clip.npz, <name>.bvh, <name>.aux.npz (mesh sole height, 2D keypoint confidences), <name>_overlay.mp4
# (GEM-X's 77-keypoint overlay | in-camera mesh | global mesh, side by side), and gemx/<name>/ (GEM-X's raw hpe_results.pt,
# vitpose.pt, bbx.pt, its overlay videos, <name>.raw.npz, run.json with runtime and peak VRAM). GEM-X's in-camera mesh render
# shows blocky patches on one side (Open3D's depth readback under Vulkan); the data is unaffected. Then the QA:
#     .venv/bin/python tools/mocap3d/soma_clip.py --qa DIR [--mp POSE_DIR]  # writes DIR/qa.json
# SOMA only: the gem_smpl* checkpoints are never downloaded, the G1 retargeter is not installed. The box is started if stopped
# (infra/gcp/gpu.sh up); the job runs in tmux there and this script polls it, so a dropped SSH doesn't kill it.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd); GPU="$ROOT/infra/gcp/gpu.sh"
export PATH="$HOME/google-cloud-sdk/bin:$PATH"
W=/srv/work/mocap; GEMX=/srv/work/gemx
q() { grep -v -e '^WARNING' -e NumPy -e increasing_the -e '^$' || true; }
box() { "$GPU" ssh "$*" 2>&1 | q; }

install() {
  local s; s=$(mktemp); cat > "$s" <<'EOF'
#!/usr/bin/env bash
set -euxo pipefail
( while true; do touch /srv/work/.keepalive; sleep 600; done ) & KA=$!; trap "kill $KA" EXIT
# the GCP DLVM ships the compute-only driver (libnvidia-compute-5xx-server): GEM-X's Open3D renderer needs Vulkan, so add the
# driver's own userspace GL/EGL/Vulkan package at the exact installed version (no kernel change) and the Vulkan loader
pkg=$(dpkg-query -W -f='${Package} ${Version}\n' 'libnvidia-compute-*' | head -1)
sudo apt-get update -qq; sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$(echo "$pkg" | awk '{sub("compute","gl",$1); print $1"="$2}')" libvulkan1
cd /srv/work; [ -d gemx ] || git clone https://github.com/NVlabs/GEM-X.git gemx; cd gemx; git rev-parse HEAD
# --recursive would fail: third_party/soma-retargeter is an SSH-only submodule (G1 robot retargeting, not needed)
git submodule update --init third_party/sam-3d-body third_party/soma
rm -rf .venv; uv venv .venv --python 3.12; source .venv/bin/activate
# pin torch to the repo's tested build (requirements.txt); unpinned, install_env.sh's SAM-3D-Body deps swap in torch 2.12 (CUDA 13)
# from PyPI and detectron2's CUDA build fails against the box's nvcc 12.9
printf 'torch==2.10.0+cu126\ntorchvision==0.25.0+cu126\n' > constraints.txt
export UV_CONSTRAINT=$PWD/constraints.txt UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cu126 UV_INDEX_STRATEGY=unsafe-best-match
uv pip install torch==2.10.0+cu126 torchvision==0.25.0+cu126
uv pip install -e third_party/soma; (cd third_party/soma && git lfs install --local && git lfs pull)
TORCH_CUDA_ARCH_LIST=8.9 MAX_JOBS=8 CUDA_HOME=/usr/local/cuda-12.9 bash scripts/install_env.sh
# the YOLOX person detector runs on ONNX Runtime, which install_env.sh only installs on macOS; 1.24+ on PyPI is built for CUDA 13
uv pip install onnxruntime-gpu==1.23.2
mkdir -p inputs; [ -e inputs/soma_assets ] || ln -s "$PWD/third_party/soma/assets" inputs/soma_assets   # the Linux docs omit this
python - <<'PY'
from gem.utils import hf_utils as h   # anonymous, huggingface.co/nvidia/GEM-X (not gated); SOMA files only
for f in (h.download_checkpoint, h.download_vitpose_checkpoint, h.download_sam3d_checkpoint, h.download_mhr_model, h.download_soma_data): print(f())
PY
python -c "from gem.utils.yolox_detector import _download_yolox_onnx as d; print(d())"
python -c "import torch, gem, soma, detectron2; print('imports ok', torch.__version__, torch.version.cuda)"
echo INSTALL_DONE
EOF
  "$GPU" up; box "mkdir -p /srv/work/scripts /srv/work/logs"
  "$GPU" push "$s" /srv/work/scripts/install_gemx.sh 2>&1 | q; rm -f "$s"
  box "tmux new-session -d -s install 'bash /srv/work/scripts/install_gemx.sh > /srv/work/logs/install_gemx.log 2>&1'"
  echo "installing (15-25 min); watch: infra/gcp/gpu.sh ssh 'tail -5 /srv/work/logs/install_gemx.log'"
}

run() {
  local out=$1; shift; mkdir -p "$out/gemx"; local names=() job; job=gemx_$(date +%Y%m%d_%H%M%S)
  "$GPU" up; box "mkdir -p $W/in $W/out $W/tools $W/jobs"
  for c in "$@"; do "$GPU" push "$c" "$W/in/" 2>&1 | q; names+=("$(basename "${c%.*}")"); done
  "$GPU" push "$ROOT/tools/mocap3d/soma_clip.py" "$W/tools/" 2>&1 | q
  local s; s=$(mktemp); cat > "$s" <<EOF
#!/usr/bin/env bash
# box side: GEM-X per clip (static camera), with wall time and peak GPU memory (nvidia-smi, sampled every 200 ms), then the conversion
set -uo pipefail
( while true; do touch /srv/work/.keepalive; sleep 300; done ) & KA=\$!; trap "kill \$KA" EXIT
cd $GEMX; source .venv/bin/activate; export PYOPENGL_PLATFORM=egl EGL_PLATFORM=surfaceless
for n in ${names[*]}; do
  o=$W/out/\$n; rm -rf \$o; mkdir -p \$o
  cmd="python scripts/demo/demo_soma.py --video $W/in/\$n.mp4 --static_cam --output_root $W/out --ckpt inputs/pretrained/gem_soma.ckpt"
  nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -lms 200 > \$o/vram.log & SMI=\$!
  t0=\$(date +%s.%N); \$cmd > \$o/gemx.log 2>&1; rc=\$?; t1=\$(date +%s.%N); kill \$SMI
  base=\$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
  python $W/tools/soma_clip.py \$o/hpe_results.pt \$o/\$n --src $W/in/\$n.mp4 --gemx $GEMX --cmd "\$cmd" > \$o/convert.log 2>&1; rc2=\$?
  frames=\$(ffprobe -v error -count_packets -select_streams v:0 -show_entries stream=nb_read_packets -of csv=p=0 $W/in/\$n.mp4)
  python -c "import json;v=[int(x) for x in open('\$o/vram.log').read().split() if x.strip().isdigit()];json.dump({'clip':'\$n','frames':\$frames,'gemx_seconds':round(\$t1-\$t0,1),'peak_vram_mib':max(v) if v else None,'idle_vram_mib':\$base,'gemx_rc':\$rc,'convert_rc':\$rc2,'gpu':'NVIDIA L4 24 GB','cmd':'''\$cmd'''},open('\$o/run.json','w'),indent=1)"
  echo "\$n gemx_rc=\$rc convert_rc=\$rc2 \$(cat \$o/run.json | tr -d '\n ')"
  (cd \$o && tar czf $W/out/\$n.pull.tgz --ignore-failed-read \$n.clip.npz \$n.bvh \$n.aux.npz \$n.raw.npz hpe_results.pt preprocess/vitpose.pt preprocess/bbx.pt \
     0_kp2d77_overlay.mp4 \${n}_1_incam.mp4 \${n}_2_global.mp4 \${n}_3_incam_global_horiz.mp4 run.json gemx.log convert.log)
done
echo JOB_DONE
EOF
  "$GPU" push "$s" "$W/jobs/$job.sh" 2>&1 | q; rm -f "$s"
  box "tmux new-session -d -s $job 'bash $W/jobs/$job.sh > $W/jobs/$job.log 2>&1'"
  echo "job $job on the box: ${names[*]}"
  local seen=0
  until "$GPU" ssh "grep -q JOB_DONE $W/jobs/$job.log" >/dev/null 2>&1; do
    sleep 30
    "$GPU" ssh "tail -n +$((seen + 1)) $W/jobs/$job.log" 2>/dev/null | q | grep -E 'gemx_rc' || true
    seen=$("$GPU" ssh "wc -l < $W/jobs/$job.log" 2>/dev/null | q | tail -1 | tr -d ' ' || echo "$seen")
  done
  for n in "${names[@]}"; do
    local g="$out/gemx/$n"; mkdir -p "$g"
    "$GPU" pull "$W/out/$n.pull.tgz" "$g/" 2>&1 | q; tar xzf "$g/$n.pull.tgz" -C "$g" && rm "$g/$n.pull.tgz"
    for f in clip.npz bvh aux.npz; do [ -f "$g/$n.$f" ] && mv "$g/$n.$f" "$out/"; done
    [ ! -f "$g/${n}_3_incam_global_horiz.mp4" ] || ffmpeg -y -loglevel error -i "$g/0_kp2d77_overlay.mp4" -i "$g/${n}_3_incam_global_horiz.mp4" \
      -filter_complex "[0:v]scale=-2:640[a];[1:v]scale=-2:640[b];[a][b]hstack" -c:v libx264 -crf 23 -pix_fmt yuv420p "$out/${n}_overlay.mp4"
    if [ -f "$out/$n.clip.npz" ]; then echo "$n -> $out/$n.clip.npz $out/$n.bvh $out/${n}_overlay.mp4"
    else echo "$n FAILED: see $g/gemx.log, $g/convert.log"; fi
  done
}

OUT="$ROOT/projects/clawd3d/refs/mocap"
case "${1:-}" in
  --install) install;;
  --out) OUT=$2; shift 2; run "$OUT" "$@";;
  ''|-h|--help) sed -n '2,12p' "$0";;
  *) run "$OUT" "$@";;
esac
