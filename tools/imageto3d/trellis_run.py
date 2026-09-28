"""TRELLIS.2 runner on the GPU box (tools/imageto3d/trellis_remote.sh writes the job, pushes it with trellis_ext/ and calls it).
    python trellis_run.py JOB.json
JOB = {"out": DIR, "pipeline_type": "512" | "1024" | "1024_cascade" | "1536_cascade", "seeds": [1, 2], "repeat": 1,
       "outputs": {"glb": true, "field": true, "preview": true, "video": false, "raw_ply": false},
       "samples": [{"name": "clawd_head_mv2", "images": ["/srv/.../front.png", "/srv/.../left.png"], "mv_weights": null,
                    "mv_mode": "stochastic" | "multidiffusion", "mv_stages": ["ss", "shape", "tex"], "mv_rescale": true,
                    "texture": true}],
       "repo": {...}}              # our commit, recorded in run.json; job-level texture / mv_mode / mv_stages are defaults
All samples run on one model load. Per sample and seed, in DIR (<tag> = <name>_s<seed>, plus _r<k> for repeats):
    <tag>_field.npz   the decoded voxel fields (trellis_ext/field.py documents the format), <tag>_field.png a preview
    <tag>.glb         textured PBR mesh (texture stage on); remeshed, falling back to plain simplification on failure
    <tag>_shape.ply   a simplified untextured mesh (texture stage off, or outputs.raw_ply: then the raw mesh unsimplified)
    <tag>_view<i>.png the preprocessed condition images; <tag>.mp4 a PBR turntable (outputs.video, needs the repo's HDRI)
    run.json          the job, versions, and per sample: stage timings, peak VRAM (torch and device), voxel and face
                      counts, a hash of the fields (reproducibility), the GLB path taken, errors
The pipeline loads from a local copy of TRELLIS.2-4B's pipeline.json with the background remover switched to
ZhengPeng7/BiRefNet (MIT) instead of briaai/RMBG-2.0 (non-commercial); RGBA inputs skip it anyway. Offline once the weights
are cached (the gated DINOv3 needs no token at run time)."""
import hashlib, json, os, subprocess, sys, time, traceback
os.environ.setdefault('OPENCV_IO_ENABLE_OPENEXR', '1')
os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')
os.environ.setdefault('HF_HUB_OFFLINE', '1')
import numpy as np
import torch
from PIL import Image
from huggingface_hub import snapshot_download

T2 = '/srv/work/trellis2'
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, T2)
sys.path.insert(0, HERE)
from trellis_ext import field as fieldio            # noqa: E402
from trellis_ext import pipeline as ext             # noqa: E402


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


def export_glb(mesh, path, target=400000, tex_size=2048):
    """textured GLB. The remeshed path (dual contouring at the grid resolution) can exhaust CuMesh's memory on big
    surfaces (a head filling the cube); then plain simplification, then a pre-decimated mesh. -> the path taken."""
    import o_voxel
    tries = [('remesh', dict(remesh=True, remesh_band=1, remesh_project=0), None),
             ('simplify', dict(remesh=False), None),
             ('predecimate', dict(remesh=False), 2_000_000)]
    errs = []
    for name, kw, pre in tries:
        try:
            v, f = mesh.vertices, mesh.faces
            if pre is not None and len(f) > pre:
                import cumesh
                cm = cumesh.CuMesh()
                cm.init(v.cuda(), f.cuda())
                cm.simplify(pre, verbose=False)
                v, f = cm.read()
            glb = o_voxel.postprocess.to_glb(vertices=v, faces=f, attr_volume=mesh.attrs, coords=mesh.coords,
                                             attr_layout=mesh.layout, voxel_size=mesh.voxel_size, aabb=ext.AABB,
                                             decimation_target=target, texture_size=tex_size, verbose=False, **kw)
            glb.export(path, extension_webp=False)
            return name, errs
        except Exception as e:                                # CuMesh raises RuntimeError on CUDA OOM
            errs.append(f'{name}: {str(e).splitlines()[0][:200]}')
            torch.cuda.empty_cache()
    raise RuntimeError('; '.join(errs))


def export_shape(mesh, path, target):
    """untextured mesh as binary PLY, simplified to `target` faces (None: as decoded)."""
    import trimesh
    if target is not None and len(mesh.faces) > target:
        mesh.simplify(target)
    v = mesh.vertices.detach().cpu().numpy()
    f = mesh.faces.detach().cpu().numpy()
    trimesh.Trimesh(v, f, process=False).export(path)
    return len(v), len(f)


def field_hash(fields):
    h = hashlib.sha1()
    for k in ('coords', 'dual', 'edge_logit', 'base_color'):
        if k in fields:
            h.update(np.ascontiguousarray(fields[k]).tobytes())
    return h.hexdigest()[:16]


def git_rev(d):
    try:
        return subprocess.run(['git', '-C', d, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    except Exception:
        return None


def main():
    job = json.load(open(sys.argv[1]))
    out = job['out']
    os.makedirs(out, exist_ok=True)
    ptype = job.get('pipeline_type', '1024_cascade')
    seeds = job.get('seeds', [1])
    outs = dict(glb=True, field=True, preview=True, video=False, raw_ply=False)
    outs.update(job.get('outputs', {}))
    from trellis2.pipelines import Trellis2ImageTo3DPipeline
    t0 = time.time()
    pipe = Trellis2ImageTo3DPipeline.from_pretrained(local_pipeline_dir())
    pipe.cuda()
    envmap = None
    if outs['video']:
        import cv2
        from trellis2.renderers import EnvMap
        hdr = cv2.imread(f'{T2}/assets/hdri/forest.exr', cv2.IMREAD_UNCHANGED)
        if hdr is not None:                               # the repo's HDRI is a git-LFS asset; without it, no mp4
            envmap = EnvMap(torch.tensor(cv2.cvtColor(hdr, cv2.COLOR_BGR2RGB), dtype=torch.float32, device='cuda'))
    log = dict(job=job, load_s=round(time.time() - t0, 1), gpu=torch.cuda.get_device_name(0), torch=torch.__version__,
               trellis2=git_rev(T2), sampler_params={k: getattr(pipe, k + '_params') for k in
                                                     ('sparse_structure_sampler', 'shape_slat_sampler', 'tex_slat_sampler')},
               runs=[])
    for s in job['samples']:
        imgs = [Image.open(p) for p in s['images']]
        texture = s.get('texture', job.get('texture', True))
        mv_mode = s.get('mv_mode', job.get('mv_mode', 'stochastic'))
        mv_rescale = s.get('mv_rescale', job.get('mv_rescale', True))
        mv_stages = tuple(s.get('mv_stages', job.get('mv_stages', ('ss', 'shape', 'tex'))))
        for seed in seeds:
            for rep in range(job.get('repeat', 1)):
                tag = f"{s['name']}_s{seed}" + (f'_r{rep}' if rep else '')
                r = dict(tag=tag, name=s['name'], images=[os.path.basename(p) for p in s['images']], seed=seed,
                         pipeline_type=ptype, texture=texture, views=len(imgs),
                         mv_mode=mv_mode if len(imgs) > 1 else None, mv_stages=list(mv_stages) if len(imgs) > 1 else None,
                         mv_rescale=mv_rescale if len(imgs) > 1 and mv_mode == 'multidiffusion' else None,
                         outputs={})
                t = time.time()
                try:
                    with ext.VramPeak() as vp:
                        res = ext.run(pipe, imgs, seed=seed, pipeline_type=ptype, texture=texture,
                                      mv_mode=mv_mode, mv_weights=s.get('mv_weights'), mv_stages=mv_stages,
                                      mv_rescale=mv_rescale)
                    r.update(gen_s=round(time.time() - t, 1), stages=res['timings'], peak_torch_gb=vp.torch_gb,
                             peak_device_gb=vp.device_gb, res=res['res'], voxels=int(len(res['fields']['coords'])),
                             raw_faces=int(len(res['mesh'].faces)), field_sha=field_hash(res['fields']), **res['stats'])
                    for i, v in enumerate(res['views']):
                        v.save(os.path.join(out, f'{tag}_view{i}.png'))
                    te = time.time()
                    with ext.VramPeak() as vx:
                        if outs['field']:
                            p = os.path.join(out, tag + '_field.npz')
                            fieldio.save(p, res['fields'], dict(
                                seed=seed, pipeline_type=ptype, images=r['images'], texture=texture,
                                mv_mode=r['mv_mode'], mv_stages=r['mv_stages'], mv_weights=s.get('mv_weights'),
                                trellis2=log['trellis2'],
                                repo=job.get('repo')))
                            r['outputs']['field'] = os.path.basename(p)
                            if outs['preview']:
                                r['outputs']['preview'] = os.path.basename(
                                    fieldio.preview(fieldio.Field(p), os.path.join(out, tag + '_field.png')))
                        if texture and outs['glb']:
                            try:
                                r['glb_path'], errs = export_glb(res['mesh'], os.path.join(out, tag + '.glb'))
                                if errs:
                                    r['glb_errors'] = errs
                                r['outputs']['glb'] = tag + '.glb'
                            except Exception as e:
                                r['glb_error'] = str(e)[:500]
                        if envmap is not None and texture:
                            import imageio
                            from trellis2.utils import render_utils
                            frames = render_utils.make_pbr_vis_frames(render_utils.render_video(res['mesh'], envmap=envmap,
                                                                                                num_frames=60))
                            imageio.mimsave(os.path.join(out, tag + '.mp4'), frames, fps=15)
                            r['outputs']['video'] = tag + '.mp4'
                        if not texture or outs['raw_ply']:
                            try:
                                nv, nf = export_shape(res['mesh'], os.path.join(out, tag + '_shape.ply'),
                                                      None if outs['raw_ply'] else 1_000_000)
                                r['outputs']['shape'] = tag + '_shape.ply'
                                r['shape_faces'] = nf
                            except Exception as e:
                                r['shape_error'] = str(e)[:300]
                    r.update(export_s=round(time.time() - te, 1), export_peak_device_gb=vx.device_gb,
                             total_s=round(time.time() - t, 1))
                    del res
                except Exception as e:
                    r['error'] = f'{type(e).__name__}: {e}'[:1000]
                    traceback.print_exc()
                print(json.dumps(r), flush=True)
                log['runs'].append(r)
                json.dump(log, open(os.path.join(out, 'run.json'), 'w'), indent=1)
                torch.cuda.empty_cache()
    log['total_s'] = round(time.time() - t0, 1)
    json.dump(log, open(os.path.join(out, 'run.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
