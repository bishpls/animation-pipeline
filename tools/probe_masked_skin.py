"""k's probe (docs/workstreams/infra5.md): is the masked skin's evaluation deterministic?

    blender -b BUILD.blend [-t N] --python tools/probe_masked_skin.py -- OUT.json [REPEATS]

Opens a build's blend and reads the skin (the object with the 'under_garments' mask) the way charkit.bundle does, REPEATS
times, each after a fresh evaluation (every modifier off, the depsgraph updated, the bundle's set back on): the 'eval'
variant (no outline, no mask), 'masked' (the mask on, no outline or proxy normals) and 'masked_shrink' (the outline on:
the surface the bundle's masked/shrink comes from). Then, with the mask on, each modifier after the mask turned off in
turn. Writes each read's sha1 of V (float64 world, as the bundle stores it) and, against the first read, the vertices
that differ and by how much. Two processes' OUT.json compare across processes (-t 1 against the default threads).
"""
import hashlib, json, sys

import bpy
import numpy as np

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.dirname(__import__('os').path.abspath(__file__))))
from charkit import bundle, trace  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
out = argv[0] if argv else '/tmp/probe_masked_skin.json'
reps = int(argv[1]) if len(argv) > 1 else 6

skin = next(o for o in bpy.data.objects if o.type == 'MESH' and o.modifiers.get('under_garments'))
ol = bundle._outline(skin)
oln = ol.name if ol is not None else None
stack = [(m.name, m.type, m.show_viewport) for m in skin.modifiers]
PRED = {
    'eval': lambda m: m.show_viewport and m.name not in trace.OUTLINE_MODS and m.name != oln,
    'masked': lambda m: m.show_viewport and m.name != oln and m.name not in bundle.NORMAL_MODS,
    'masked_shrink': lambda m: m.show_viewport,
}


def fresh():
    prev = bundle._mods(skin, lambda m: False)
    bpy.context.view_layer.update()
    bundle._restore(prev)
    bpy.context.view_layer.update()


def read(pred):
    fresh()
    prev = bundle._mods(skin, pred)
    try:
        return bundle._read(skin)['V']
    finally:
        bundle._restore(prev)


def row(V, V0):
    r = dict(sha=hashlib.sha1(np.ascontiguousarray(V).tobytes()).hexdigest()[:12], n=len(V))
    if V0 is not None and V.shape == V0.shape:
        d = np.abs(V - V0).max(1)
        r.update(differ=int((d > 0).sum()), max=float(d.max()) if len(d) else 0.0)
    return r


res = dict(blend=bpy.data.filepath, threads=(sys.argv[sys.argv.index('-t') + 1] if '-t' in sys.argv else 'default'), stack=stack,
           skin=skin.name, reads={})
for name, pred in PRED.items():
    V0 = None
    rows = []
    for i in range(reps):
        V = read(pred)
        rows.append(row(V, V0))
        V0 = V if V0 is None else V0
    res['reads'][name] = rows
# with the mask on, each modifier after it off in turn (which one makes the masked read vary)
names = [m.name for m in skin.modifiers]
after = names[names.index('under_garments') + 1:]
res['without'] = {}
for n in after:
    pred = lambda m, n=n: PRED['masked'](m) and m.name != n
    V0, rows = None, []
    for i in range(reps):
        V = read(pred)
        rows.append(row(V, V0))
        V0 = V if V0 is None else V0
    res['without'][n] = rows
json.dump(res, open(out, 'w'), indent=1)
print('PROBE', out, {k: len({r['sha'] for r in v}) for k, v in res['reads'].items()},
      {k: len({r['sha'] for r in v}) for k, v in res['without'].items()})
