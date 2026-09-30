"""ablate.py BUILD 'name|json' ...: per variant the three-quarter figure's IoU (bodyqa's iou: foreground) and its hair
class IoU against the design, as the body QA draws ours (the QA scene, z-buffered), plus the per-view hair classes."""
import json, os, sys
sys.path.insert(0, os.path.expanduser('~/animation-pipeline-hair3'))
os.chdir(os.path.expanduser('~/animation-pipeline-hair3'))
import numpy as np
from charkit import hairlab as hl, bodyqa, qa3d
ctx = hl.context(os.path.abspath(sys.argv[1]))
B, D = ctx['B'], ctx['D']
dv = D.design_views()
sc = D.sheet_context()
As = B.assembly
base_meshes = []
V, T = B.skin().mesh('masked')[:2]
base_meshes.append((V, T, np.full(len(T), 1)))
for o in B.objects(groups=('eye', 'mouth', 'accessory', 'garment')):
    if o.has('eval'):
        V, T = o.mesh('eval')[:2]
        base_meshes.append((V, T, np.full(len(T), 5)))
prev = None
for arg in sys.argv[2:]:
    name, js = arg.split('|', 1)
    v_ = json.loads(js)
    R, Cq, fs, hair = hl.run(ctx, v_.get('style'), v_.get('opts'))
    meshes = base_meshes + [(ev[0], ev[1], np.full(len(ev[1]), 2)) for ev, _ in hair.values()]
    views = [v for v in ('front', 'three_quarter', 'profile', 'back') if v in dv]
    lab = bodyqa.zbuffer_views(meshes, sc['az3'], np.array(qa3d.iris_centres(B)), As['centre'], As['L'], sc['ppl'], views)
    out = {}
    for v in views:
        lb = lab[v][1]
        dcls = dv[v]['cls']
        ofg, dfg = lb >= 1, dcls > 0
        oh, dh = lb == 2, dcls == 2
        iou = lambda a, b: round(float((a & b).sum() / max(1, (a | b).sum())), 4)
        out[v] = (iou(ofg, dfg), iou(oh, dh))
    print('%-14s fg/hair IoU  ' % name + '  '.join('%s %s/%s' % (v[:5], a, b) for v, (a, b) in out.items()), flush=True)
