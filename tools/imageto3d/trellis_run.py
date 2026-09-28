"""TRELLIS.2 runner on the GPU box (tools/imageto3d/trellis_remote.sh pushes and calls it).
    python trellis_run.py OUT_DIR RES SEEDS IMG [IMG ...]      RES: 512 | 1024 | 1024_cascade; SEEDS: 1,2,3
The pipeline loads from a local copy of TRELLIS.2-4B's pipeline.json with the background remover switched to
ZhengPeng7/BiRefNet (MIT) instead of briaai/RMBG-2.0 (non-commercial); RGBA inputs skip it anyway. Offline once the weights
are cached (the gated DINOv3 needs no token at run time)."""
import json, os, sys, time
os.environ.setdefault('OPENCV_IO_ENABLE_OPENEXR', '1')
os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')
os.environ.setdefault('HF_HUB_OFFLINE', '1')
import numpy as np
import torch
from PIL import Image
from huggingface_hub import snapshot_download

T2 = '/srv/work/trellis2'
sys.path.insert(0, T2)


def local_pipeline_dir():
    snap = snapshot_download('microsoft/TRELLIS.2-4B')
    d = '/srv/work/i3d/model'
    os.makedirs(d, exist_ok=True)
    cfg = json.load(open(os.path.join(snap, 'pipeline.json')))
    cfg['args']['rembg_model'] = {'name': 'BiRefNet', 'args': {'model_name': 'ZhengPeng7/BiRefNet'}}
    json.dump(cfg, open(os.path.join(d, 'pipeline.json'), 'w'), indent=1)
    if not os.path.exists(os.path.join(d, 'ckpts')):
        os.symlink(os.path.join(snap, 'ckpts'), os.path.join(d, 'ckpts'))
    return d


def main():
    out, res, seeds, imgs = sys.argv[1], sys.argv[2], [int(s) for s in sys.argv[3].split(',')], sys.argv[4:]
    os.makedirs(out, exist_ok=True)
    import cv2, imageio, trimesh
    import o_voxel
    from trellis2.pipelines import Trellis2ImageTo3DPipeline
    from trellis2.utils import render_utils
    from trellis2.renderers import EnvMap
    t0 = time.time()
    pipe = Trellis2ImageTo3DPipeline.from_pretrained(local_pipeline_dir())
    pipe.cuda()
    envmap = EnvMap(torch.tensor(cv2.cvtColor(cv2.imread(f'{T2}/assets/hdri/forest.exr', cv2.IMREAD_UNCHANGED),
                                              cv2.COLOR_BGR2RGB), dtype=torch.float32, device='cuda'))
    log = {'load_s': round(time.time() - t0, 1), 'runs': []}
    for path in imgs:
        name = os.path.splitext(os.path.basename(path))[0]
        img = Image.open(path)
        for seed in seeds:
            torch.cuda.reset_peak_memory_stats()
            t = time.time()
            mesh = pipe.run(img, seed=seed, pipeline_type=res)[0]
            t_gen = time.time() - t
            mesh.simplify(16777216)
            tag = f'{name}_s{seed}'
            v = mesh.vertices.detach().cpu().numpy(); f = mesh.faces.detach().cpu().numpy()
            trimesh.Trimesh(v, f, process=False).export(os.path.join(out, tag + '_shape.ply'))
            glb = o_voxel.postprocess.to_glb(vertices=mesh.vertices, faces=mesh.faces, attr_volume=mesh.attrs,
                                             coords=mesh.coords, attr_layout=mesh.layout, voxel_size=mesh.voxel_size,
                                             aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]], decimation_target=400000,
                                             texture_size=2048, remesh=True, remesh_band=1, remesh_project=0, verbose=False)
            glb.export(os.path.join(out, tag + '.glb'), extension_webp=False)
            frames = render_utils.make_pbr_vis_frames(render_utils.render_video(mesh, envmap=envmap, num_frames=60))
            imageio.mimsave(os.path.join(out, tag + '.mp4'), frames, fps=15)
            r = dict(image=name, seed=seed, res=res, gen_s=round(t_gen, 1), total_s=round(time.time() - t, 1),
                     peak_gb=round(torch.cuda.max_memory_allocated() / 1e9, 2), verts=int(len(v)), faces=int(len(f)))
            print(r, flush=True)
            log['runs'].append(r)
            del mesh
            torch.cuda.empty_cache()
    json.dump(log, open(os.path.join(out, 'run.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
