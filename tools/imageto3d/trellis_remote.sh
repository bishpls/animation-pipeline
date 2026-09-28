#!/usr/bin/env bash
# TRELLIS.2 (microsoft/TRELLIS.2, MIT; weights microsoft/TRELLIS.2-4B, MIT) on the GPU box: image -> textured 3D mesh, the
# shape prior for charkit (docs/CHARKIT.md: hair and costume volumes, head targets for the wrap).
#     tools/imageto3d/trellis_remote.sh --install                   # once per box: env, extensions, weights
#     tools/imageto3d/trellis_remote.sh [--out DIR] [--res 512|1024] [--seeds 1,2] IMG.png [IMG.png ...]
# Per image and seed, in DIR (default charkit/out/i3d): <name>_s<seed>.glb (textured, PBR), <name>_s<seed>_shape.ply (the raw
# shape), <name>_s<seed>.mp4 (a turntable), run.json (times, peak VRAM). Images with an alpha channel are used as-is (no
# background removal); others go through BiRefNet (ZhengPeng7/BiRefNet, MIT), never briaai/RMBG-2.0 (non-commercial).
# The image encoder is Meta's DINOv3 (facebook/dinov3-vitl16-pretrain-lvd1689m: gated, DINOv3 License; the HF token comes
# from Secret Manager on the box (its name: HF_SECRET in infra/gcp/gpu.env) and is never written to disk or logged).
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd); GPU="$ROOT/infra/gcp/gpu.sh"
export PATH="$HOME/google-cloud-sdk/bin:$PATH"
W=/srv/work/i3d; T2=/srv/work/trellis2
q() { grep -v -e '^WARNING' -e NumPy -e increasing_the -e '^$' || true; }
box() { "$GPU" ssh "$*" 2>&1 | q; }

install() {
  local s; s=$(mktemp); cat > "$s" <<'EOS'
#!/usr/bin/env bash
set -euxo pipefail
( while true; do touch /srv/work/.keepalive; sleep 600; done ) & KA=$!; trap "kill $KA" EXIT
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libjpeg-dev ffmpeg
cd /srv/work; [ -d trellis2 ] || git clone -b main https://github.com/microsoft/TRELLIS.2.git trellis2; cd trellis2
git submodule update --init --recursive; git rev-parse HEAD
rm -rf .venv; uv venv .venv --python 3.10; source .venv/bin/activate
export UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cu124 UV_INDEX_STRATEGY=unsafe-best-match
uv pip install torch==2.6.0+cu124 torchvision==0.21.0+cu124
uv pip install imageio imageio-ffmpeg tqdm easydict opencv-python-headless ninja trimesh transformers tensorboard pandas \
  lpips zstandard kornia timm pillow huggingface_hub setuptools wheel psutil
uv pip install git+https://github.com/EasternJournalist/utils3d.git@9a4eb15e4021b67b12c460c7057d642626897ec8
export CUDA_HOME=/usr/local/cuda-12.9 TORCH_CUDA_ARCH_LIST=8.9 MAX_JOBS=8
uv pip install flash-attn==2.7.3 --no-build-isolation || echo "flash-attn: no wheel/build; falling back to sdpa"
mkdir -p /tmp/ext
[ -d /tmp/ext/nvdiffrast ] || git clone -b v0.4.0 https://github.com/NVlabs/nvdiffrast.git /tmp/ext/nvdiffrast
uv pip install /tmp/ext/nvdiffrast --no-build-isolation
[ -d /tmp/ext/nvdiffrec ] || git clone -b renderutils https://github.com/JeffreyXiang/nvdiffrec.git /tmp/ext/nvdiffrec
uv pip install /tmp/ext/nvdiffrec --no-build-isolation
[ -d /tmp/ext/CuMesh ] || git clone --recursive https://github.com/JeffreyXiang/CuMesh.git /tmp/ext/CuMesh
uv pip install /tmp/ext/CuMesh --no-build-isolation
[ -d /tmp/ext/FlexGEMM ] || git clone --recursive https://github.com/JeffreyXiang/FlexGEMM.git /tmp/ext/FlexGEMM
uv pip install /tmp/ext/FlexGEMM --no-build-isolation
rm -rf /tmp/ext/o-voxel; cp -r o-voxel /tmp/ext/o-voxel; uv pip install /tmp/ext/o-voxel --no-build-isolation
python -c "import torch, o_voxel, cumesh, flex_gemm, nvdiffrast.torch; print('torch', torch.__version__, torch.cuda.is_available())"
# weights: the MIT ones anonymously; DINOv3 with the token (gated) if access has been granted
python - <<'PY'
from huggingface_hub import snapshot_download
for r in ('microsoft/TRELLIS.2-4B', 'ZhengPeng7/BiRefNet'):
    print(r, snapshot_download(r))
snapshot_download('microsoft/TRELLIS-image-large', allow_patterns=['ckpts/ss_dec_conv3d_16l8_fp16*'])
PY
set +x    # never trace the token
python - <<'PY' || echo "DINOv3: not accessible yet (request access on Hugging Face)"
import subprocess
from huggingface_hub import snapshot_download
tok = subprocess.run(['gcloud', 'secrets', 'versions', 'access', 'latest', '--secret=__HF_SECRET__'],
                     capture_output=True, text=True).stdout.strip()
print(snapshot_download('facebook/dinov3-vitl16-pretrain-lvd1689m', token=tok))
PY
set -x
touch /srv/work/trellis2/.installed
EOS
  source "$ROOT/infra/gcp/gpu.env"; sed -i.bak "s/__HF_SECRET__/${HF_SECRET:?set HF_SECRET in infra/gcp/gpu.env}/" "$s"
  "$GPU" up >/dev/null
  "$GPU" push "$s" /srv/work/trellis_install.sh >/dev/null 2>&1
  box "chmod +x /srv/work/trellis_install.sh; tmux kill-session -t t2i 2>/dev/null; tmux new -d -s t2i 'bash /srv/work/trellis_install.sh > /srv/work/trellis_install.log 2>&1'"
  echo "installing in tmux 't2i' on the box; log: /srv/work/trellis_install.log"
}

if [ "${1:-}" = --install ]; then install; exit 0; fi
OUT="$ROOT/charkit/out/i3d"; RES=1024_cascade; SEEDS=1
while [ $# -gt 0 ]; do case "$1" in
  --out) OUT=$2; shift 2;; --res) RES=$2; shift 2;; --seeds) SEEDS=$2; shift 2;; *) break;; esac; done
[ $# -gt 0 ] || { sed -n '2,12p' "$0"; exit 1; }
"$GPU" up >/dev/null
job=$(date +%Y%m%d_%H%M%S); R=$W/$job
box "mkdir -p $R/in"
for f in "$@"; do "$GPU" push "$f" "$R/in/" >/dev/null 2>&1; done
"$GPU" push "$ROOT/tools/imageto3d/trellis_run.py" "$W/trellis_run.py" >/dev/null 2>&1
ins=$(for f in "$@"; do printf '%s ' "$R/in/$(basename "$f")"; done)
box "tmux kill-session -t i3d 2>/dev/null; tmux new -d -s i3d 'cd $T2 && ( while true; do touch /srv/work/.keepalive; sleep 300; done ) & source $T2/.venv/bin/activate && python $W/trellis_run.py $R/out $RES $SEEDS $ins > $R/log.txt 2>&1; touch $R/DONE'"
echo "job $job running on the box (tmux i3d); polling"
until box "test -f $R/DONE && echo done" | grep -q done; do sleep 30; box "tail -1 $R/log.txt" | tail -1; done
box "tail -5 $R/log.txt"
mkdir -p "$OUT"
"$GPU" pull "$R/out" "$OUT/$job" >/dev/null 2>&1
echo "-> $OUT/$job"; ls "$OUT/$job" 2>/dev/null || ls "$OUT/$job/out"
