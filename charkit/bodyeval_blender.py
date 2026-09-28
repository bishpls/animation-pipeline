"""Blender entry for `python -m charkit bodyeval SPEC --validate` (charkit/bodyeval.py): build a resolved spec's scene (no
boards, no QA) and dump every character object's geometry to an npz, so the numpy evaluator is checked against Blender
object by object.
    blender -b --factory-startup --python charkit/bodyeval_blender.py -- SPEC.json OUT.npz

Per object (key prefix `o/NAME/`): base (world verts of the mesh as built, before modifiers), loops / starts / counts,
evaluated (world verts with modifiers, the outline and garment mask off, as charkit.trace hashes them) with its
ev_loops / ev_starts / ev_counts and ev_mats (material index per polygon; matnames), hash (the trace's geometry hash of
the evaluated mesh). Also: the landmarks the QA bands use, the generated shape's alignment, the hair
selection before Blender's smoothing (hair_sel_V / hair_sel_F) and the MeshVolume's radius grid.
"""
import json, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
from charkit import qa3d, scene, trace
from charkit.garments import bone_seg

a = sys.argv[sys.argv.index('--') + 1:]
spec = scene.load(a[0])
t = time.time()
S = scene.build(spec)
dt = time.time() - t
out = {}
names = []
for o in qa3d._character_objects(S):
    if o.type != 'MESH':
        continue
    names.append(o.name)
    n = len(o.data.vertices)
    co = np.empty(n * 3, np.float64); o.data.vertices.foreach_get('co', co)
    M = np.array(o.matrix_world)
    out['o/%s/base' % o.name] = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    nf = len(o.data.polygons)
    st = np.empty(nf, np.int64); ct = np.empty(nf, np.int64)
    o.data.polygons.foreach_get('loop_start', st); o.data.polygons.foreach_get('loop_total', ct)
    lv = np.empty(len(o.data.loops), np.int64); o.data.loops.foreach_get('vertex_index', lv)
    out['o/%s/loops' % o.name], out['o/%s/starts' % o.name], out['o/%s/counts' % o.name] = lv, st, ct
    V, F, mats = trace.mesh_arrays(o, materials=True)
    out['o/%s/evaluated' % o.name] = V
    out['o/%s/hash' % o.name] = np.array(trace.geometry_hash(V, F))
    out['o/%s/ev_loops' % o.name], out['o/%s/ev_starts' % o.name], out['o/%s/ev_counts' % o.name] = F
    out['o/%s/ev_mats' % o.name] = mats
    out['o/%s/matnames' % o.name] = np.array([(m.name if m else '').split('.')[0] for m in o.data.materials] or [''])
    out['o/%s/base_hash' % o.name] = np.array(trace.geometry_hash(out['o/%s/base' % o.name], (lv, st, ct)))
A = S.character['data']; Hd = A['head']
lm = dict(L=Hd['L'], centre=list(Hd['centre']), chin=float(Hd['centre'][2] - Hd['H'].chin),
          waist=float(bone_seg(A, 'spine')[0][2]), knee=float(bone_seg(A, 'leftLowerLeg')[0][2]), build_s=dt,
          objects=names, groups={'hair': [o.name for o in S.hair], 'accessories': [o.name for o in S.accessories],
                                 'garments': [o.name for o in S.garments]})
if getattr(S, 'hair_shape', None) is not None:
    out['hair_sel_V'] = np.asarray(S.hair_shape[0]); out['hair_sel_F'] = np.array([list(f) for f in S.hair_shape[1]])
if getattr(S, 'shape_full', None) is not None:
    out['shape_V'] = np.asarray(S.shape_full[0], np.float32)
vol = getattr(S, 'hair_volume', None)
if vol is not None and hasattr(vol, 'mr'):
    out['vol_mr'] = vol.mr; out['vol_c'] = np.asarray(vol.c)
out['meta'] = np.array(json.dumps(lm))
np.savez_compressed(a[1], **out)
print('CHARKIT_BODYEVAL_DUMP', a[1], '%.1fs' % dt)
