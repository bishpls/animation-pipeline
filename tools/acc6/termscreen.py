"""art_terminator_hair for candidate crab placements, screened on a build's bundle (tool/accessories6): each candidate's
clips placed as the build places them (accfit.Scene.place: the bundle's crab vertices reproduced to 1e-7), its crab
substituted into the bundle (same template, so the same vertices), the artifacts part measured with the numpy drawing
(charkit.sweep swap's: it reads the real build's values, 2.432 / 2.509 on the base and the fit), at the gate's single
placement and optionally six (render.calibrate.OFFSETS).
    python tools/acc6/termscreen.py BUILD CANDS.json OUT.json [--part I/N] [--six]"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from charkit import accfit, artifactqa, qa3d, bundle as bl
from charkit.calibrate import load_bundle
from term6 import reading
from charkit.render.calibrate import OFFSETS

a = sys.argv[1:]
build, cands, out = a[0], json.load(open(a[1])), a[2]
if '--part' in a:
    i, n = (int(x) for x in a[a.index('--part') + 1].split('/'))
    cands = cands[i::n]
six = '--six' in a
B0 = load_bundle(build)
spec = accfit._spec(os.path.join(ROOT, 'charkit/spec/clawd.json'))
S = accfit.Scene(build, accfit.design(spec))
crab = next(o for o in B0.objects(groups=('accessory',)) if o.name.startswith('crab'))
key = 'o/%s/eval/V' % crab.name
res = {}
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
for c in cands:
    cl = S.place(c['specs'])
    V = next(v for k, v, f, s in cl if k == 'crab')
    B = bl.Bundle(B0._meta, B0._arrays, path=B0.path)
    B._loaded = dict(B0._loaded)
    B.array(key)                                     # (loaded, then replaced)
    B._loaded[key] = np.asarray(V, B0.array(key).dtype)
    offs = OFFSETS[:6] if six else OFFSETS[:1]
    R = [reading(B, off) for off in offs]
    v = [r['terminator_hair'][0] for r in R]
    res[c['name']] = dict(place=v[0], values=v, mean=round(float(np.mean(v)), 3), per_view=R[0]['terminator_hair'][1],
                          peeks=[r.get('peeks_hair', (None,))[0] for r in R])
    print('%-16s terminator %.3f%s per view %s' % (c['name'], v[0], (' six mean %.3f' % np.mean(v)) if six else '',
                                                  R[0]['terminator_hair'][1]), flush=True)
    json.dump(res, open(out, 'w'), indent=1)
