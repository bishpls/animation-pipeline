#!/usr/bin/env bash
# TRELLIS.2 (microsoft/TRELLIS.2, MIT; weights microsoft/TRELLIS.2-4B, MIT) on the GPU box: image(s) -> textured 3D mesh and
# the decoded voxel fields, the shape prior for charkit (docs/CHARKIT.md: hair and costume volumes, head targets for the wrap).
#     tools/imageto3d/trellis_remote.sh --install                   # once per box: env, extensions, weights
#     tools/imageto3d/trellis_remote.sh [options] SAMPLE [SAMPLE ...]
# SAMPLE: IMG.png, or views of one object joined by '+' for one multi-view sample, the first the primary (front), each
# optionally weighted with @W and the sample optionally named:  clawd=front.png@2+left.png+back.png
# Options: --out DIR (default charkit/out/i3d/<job>)  --res 512|1024|1024_cascade|1536_cascade  --seeds 1,2  --repeat N
#   --no-glb  --no-field  --video  --raw-ply
# Per sample (they apply to the samples after them): --mv stochastic|multidiffusion (default stochastic: one view per
#   step; multidiffusion averages every view each step, V times the cost)  --mv-stages ss,shape,tex  --no-mv-rescale
#   --no-tex | --tex (--no-tex: structure + shape only: faster, fields without colours, a simplified _shape.ply, no GLB)
# All samples run on one model load (tools/imageto3d/trellis_run.py; outputs and run.json documented there). Our extension
# (tools/imageto3d/trellis_ext: multi-view, stages, field export) is pushed with each job and wraps the upstream clone
# without editing it. Images with an alpha channel are used as-is (no background removal); others go through BiRefNet
# (ZhengPeng7/BiRefNet, MIT), never briaai/RMBG-2.0 (non-commercial).
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
[ -x .venv/bin/python ] || uv venv .venv --python 3.10; source .venv/bin/activate
have() { python -c "import $1" 2>/dev/null; }
export UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cu124 UV_INDEX_STRATEGY=unsafe-best-match
uv pip install torch==2.6.0+cu124 torchvision==0.21.0+cu124
uv pip install imageio imageio-ffmpeg tqdm easydict opencv-python-headless ninja trimesh transformers tensorboard pandas \
  lpips zstandard kornia timm pillow huggingface_hub setuptools wheel psutil "transformers>=4.56,<4.58"   # 5.x moved DINOv3's layers
uv pip install git+https://github.com/EasternJournalist/utils3d.git@9a4eb15e4021b67b12c460c7057d642626897ec8
export CUDA_HOME=/usr/local/cuda-12.9 TORCH_CUDA_ARCH_LIST=8.9 MAX_JOBS=3   # 8 parallel nvcc jobs exhaust the 32 GB box
have flash_attn || uv pip install flash-attn==2.7.3 --no-build-isolation || echo "flash-attn: no wheel/build"
mkdir -p /tmp/ext
[ -d /tmp/ext/nvdiffrast ] || git clone -b v0.4.0 https://github.com/NVlabs/nvdiffrast.git /tmp/ext/nvdiffrast
have nvdiffrast.torch || uv pip install /tmp/ext/nvdiffrast --no-build-isolation
[ -d /tmp/ext/nvdiffrec ] || git clone -b renderutils https://github.com/JeffreyXiang/nvdiffrec.git /tmp/ext/nvdiffrec
have renderutils || have nvdiffrec_render || uv pip install /tmp/ext/nvdiffrec --no-build-isolation
[ -d /tmp/ext/CuMesh ] || git clone --recursive https://github.com/JeffreyXiang/CuMesh.git /tmp/ext/CuMesh
have cumesh || uv pip install /tmp/ext/CuMesh --no-build-isolation
[ -d /tmp/ext/FlexGEMM ] || git clone --recursive https://github.com/JeffreyXiang/FlexGEMM.git /tmp/ext/FlexGEMM
have flex_gemm || uv pip install /tmp/ext/FlexGEMM --no-build-isolation
have o_voxel || { rm -rf /tmp/ext/o-voxel; cp -r o-voxel /tmp/ext/o-voxel; uv pip install /tmp/ext/o-voxel --no-build-isolation; }
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
# our extension (tools/imageto3d/trellis_ext) wraps the clone without editing it; jobs push the current copy
python -c "import sys; sys.path[:0] = ['/srv/work/i3d', '/srv/work/trellis2']; import trellis_ext.pipeline, trellis_ext.field; print('trellis_ext ok')"
touch /srv/work/trellis2/.installed
EOS
  source "$ROOT/infra/gcp/gpu.env"; sed -i.bak "s/__HF_SECRET__/${HF_SECRET:?set HF_SECRET in infra/gcp/gpu.env}/" "$s"
  "$GPU" up >/dev/null
  "$GPU" push "$s" /srv/work/trellis_install.sh >/dev/null 2>&1
  box "mkdir -p $W"; "$GPU" push "$ROOT/tools/imageto3d/trellis_ext" "$W/" >/dev/null 2>&1
  box "chmod +x /srv/work/trellis_install.sh; tmux kill-session -t t2i 2>/dev/null; tmux new -d -s t2i 'bash /srv/work/trellis_install.sh > /srv/work/trellis_install.log 2>&1'"
  echo "installing in tmux 't2i' on the box; log: /srv/work/trellis_install.log"
}

if [ "${1:-}" = --install ]; then install; exit 0; fi
OUT=""; args=()
while [ $# -gt 0 ]; do case "$1" in --out) OUT=$2; shift 2;; *) args+=("$1"); shift;; esac; done
[ ${#args[@]} -gt 0 ] || { sed -n '2,17p' "$0"; exit 1; }
job=$(date +%Y%m%d_%H%M%S); R=$W/$job; OUT=${OUT:-$ROOT/charkit/out/i3d/$job}
stage=$(mktemp -d); mkdir -p "$stage/in"
cp -R "$ROOT/tools/imageto3d/trellis_ext" "$ROOT/tools/imageto3d/trellis_run.py" "$stage/"
find "$stage/trellis_ext" -name __pycache__ -prune -exec rm -rf {} +
rev=$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo none)
dirty=$(git -C "$ROOT" status --porcelain -- tools/imageto3d 2>/dev/null | head -1)
python3 - "$stage" "$R" "$rev" "${dirty:+dirty}" "${args[@]}" <<'PY'
import json, os, shutil, sys
stage, R, rev, dirty = sys.argv[1:5]
argv = sys.argv[5:]
job = dict(out=f'{R}/out', pipeline_type='1024_cascade', seeds=[1], repeat=1, texture=True,
           outputs=dict(glb=True, field=True, preview=True, video=False, raw_ply=False),
           mv_mode='stochastic', mv_stages=['ss', 'shape', 'tex'], samples=[], repo=dict(commit=rev, dirty=bool(dirty)))
cur = dict(mv_mode='stochastic', mv_stages=['ss', 'shape', 'tex'], mv_rescale=True, texture=True)   # sticky per sample
seen, names = {}, set()
i = 0
while i < len(argv):
    a = argv[i]
    val = argv[i + 1] if i + 1 < len(argv) else None
    if a == '--res': job['pipeline_type'] = val; i += 2; continue
    if a == '--seeds': job['seeds'] = [int(x) for x in val.split(',')]; i += 2; continue
    if a == '--repeat': job['repeat'] = int(val); i += 2; continue
    if a in ('--no-glb', '--no-field', '--video', '--raw-ply'):
        k = {'--no-glb': 'glb', '--no-field': 'field', '--video': 'video', '--raw-ply': 'raw_ply'}[a]
        job['outputs'][k] = a in ('--video', '--raw-ply')
        job['outputs']['preview'] = job['outputs']['field']; i += 1; continue
    if a == '--mv': cur['mv_mode'] = val; i += 2; continue
    if a == '--mv-stages': cur['mv_stages'] = val.split(','); i += 2; continue
    if a in ('--mv-rescale', '--no-mv-rescale'): cur['mv_rescale'] = a == '--mv-rescale'; i += 1; continue
    if a in ('--tex', '--no-tex'): cur['texture'] = a == '--tex'; i += 1; continue
    if a.startswith('-'): sys.exit(f'unknown option {a}')
    name, spec = a.split('=', 1) if '=' in a.split('+')[0] else (None, a)
    imgs, w = [], []
    for part in spec.split('+'):
        path, _, wt = part.partition('@')
        base = os.path.basename(path)
        if seen.get(base, path) != path:
            sys.exit(f'two different inputs named {base}')
        if base not in seen:
            shutil.copy(path, os.path.join(stage, 'in', base)); seen[base] = path
        imgs.append(f'{R}/in/{base}'); w.append(float(wt or 1))
    if not name:
        name = os.path.splitext(os.path.basename(imgs[0]))[0]
        if len(imgs) > 1:
            name += f"_mv{len(imgs)}{cur['mv_mode'][0]}" + ('' if cur['mv_rescale'] or cur['mv_mode'] != 'multidiffusion' else 'n')
            if cur['mv_stages'] != ['ss', 'shape', 'tex']:
                name += '-' + '-'.join(cur['mv_stages'])
        if not cur['texture']:
            name += '_notex'
        base, k = name, 2
        while name in names:
            name = f'{base}_{k}'; k += 1
    names.add(name)
    job['samples'].append(dict(name=name, images=imgs, mv_weights=w if len(set(w)) > 1 else None, **cur))
    cur = dict(cur, mv_stages=list(cur['mv_stages']))
    i += 1
if not job['samples']:
    sys.exit('no samples')
json.dump(job, open(os.path.join(stage, 'job.json'), 'w'), indent=1)
for s in job['samples']:
    print(s['name'], '<-', ' + '.join(os.path.basename(i) for i in s['images']),
          '' if len(s['images']) == 1 else f"({s['mv_mode']}: {','.join(s['mv_stages'])})", '' if s['texture'] else '(no texture)')
PY
cat > "$stage/job.sh" <<EOJ
#!/usr/bin/env bash
( while true; do touch /srv/work/.keepalive; sleep 300; done ) & KA=\$!
cd $T2 && . $T2/.venv/bin/activate && PYTHONUNBUFFERED=1 python $R/trellis_run.py $R/job.json > $R/log.txt 2>&1
kill \$KA; touch $R/DONE
EOJ
tar czf "$stage.tgz" -C "$stage" .
"$GPU" up >/dev/null
box "mkdir -p $R"
"$GPU" push "$stage.tgz" "$R/job.tgz" >/dev/null 2>&1
rm -rf "$stage" "$stage.tgz"
box "cd $R && tar xzf job.tgz && rm job.tgz && tmux kill-session -t i3d 2>/dev/null; tmux new -d -s i3d 'bash $R/job.sh'"
echo "job $job running on the box (tmux i3d); polling"
until box "test -f $R/DONE && echo done" | grep -q done; do
  sleep 30; box "grep -h -o '\"tag\": \"[^\"]*\"\|Sampling [a-zA-Z ]*\|Traceback' $R/log.txt | tail -1"
done
box "grep '^{' $R/log.txt | cut -c1-400; grep -A3 Traceback $R/log.txt | tail -8"
mkdir -p "$OUT"; tmp="$OUT/.pull$$"
"$GPU" pull "$R/out" "$tmp" >/dev/null 2>&1
mv "$tmp"/* "$OUT"/ && rmdir "$tmp"
echo "-> $OUT"; ls "$OUT"
