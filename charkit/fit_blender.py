"""The Blender side of `python -m charkit fit` (charkit/facefit.py): what the numpy face evaluator (charkit/faceeval.py)
can't make itself, saved once as arrays.

  target   the 3D target (the spec's hair.shape.glb: the visual hull) as loaded: vertices, triangles and
           per-vertex colours, before any alignment (the evaluator aligns it on each head as the build does)
  env      with --env: the scene's hair, accessories and garments (evaluated, world), the triangles near the head. The face
           and eye knobs don't make them, so they stand as occluders (garments) and cover (hair) for the face measures;
           the hair's cull against the face follows the head it was built on; with the skin they were fitted on, so the
           evaluator moves the garments with the skin when body knobs (the neck) change

    blender -b --factory-startup --python charkit/fit_blender.py -- RESOLVED_SPEC.json OUT_DIR [--env]
"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np

from charkit import faceqa, target3d, scene, trace

a = sys.argv[sys.argv.index('--') + 1:]
spec = scene.load(a[0])
out = a[1]
os.makedirs(out, exist_ok=True)
shape = (spec.get('hair') or {}).get('shape') or {}
if shape.get('glb'):
    path = shape['glb'] if os.path.isabs(shape['glb']) else os.path.join(ROOT, shape['glb'])
    scene.reset()
    V, F, C = target3d.load_glb(path)
    T = np.array([f for f in F if len(f) == 3], np.int32)
    quads = [f for f in F if len(f) == 4]
    if quads:
        Q = np.array(quads, np.int32)
        T = np.vstack([T, Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])
    np.savez_compressed(os.path.join(out, 'target.npz'), V=np.asarray(V, np.float64), T=T, C=np.asarray(C, np.float32),
                        glb=path)
    print('CHARKIT_FIT_TARGET', len(V), len(T))
if '--env' in a:
    S = scene.build(spec)
    A = S.character['data']; Hd = A['head']; L = Hd['L']
    low = Hd['centre'][2] - Hd['H'].chin - 0.6 * L
    d = {}
    for group, obs in (('hair', S.hair), ('accessory', S.accessories), ('garment', S.garments)):
        Vs, Ts, off = [], [], 0
        for o in obs:
            if o.type != 'MESH' or o.hide_render:
                continue
            v, f = trace.mesh_arrays(o)
            t, _ = faceqa.triangles(*f)
            keep = v[t].max(1)[:, 2] > low
            Vs.append(v); Ts.append(t[keep] + off); off += len(v)
        d[group + '_V'] = np.vstack(Vs) if Vs else np.zeros((0, 3))
        d[group + '_T'] = np.vstack(Ts).astype(np.int32) if Ts else np.zeros((0, 3), np.int32)
    d['skin_V'] = np.asarray(A['verts'], np.float64)                # what the garments were fitted on (they follow its moves)
    np.savez_compressed(os.path.join(out, 'env.npz'), **d)
    print('CHARKIT_FIT_ENV', {k: len(v) for k, v in d.items()})
print('CHARKIT_FIT_BLENDER_DONE')
