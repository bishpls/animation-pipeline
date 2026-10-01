"""art hair checks: a base bundle with a pieces dir's hair spliced the sweep's way; ow=1 scales the shrink by the
pieces' outline_w (as the Blender build's outline_w vertex group does)."""
import sys, os, json, time
import numpy as np
from charkit import bundle, artifactqa, qa3d, sweep
from charkit.geom.io import load_npz

def splice(B0, pdir, ow=True):
    idx = json.load(open(os.path.join(pdir, 'pieces.json')))
    rep = {}
    for p in idx['pieces']:
        z = np.load(os.path.join(pdir, p['file']))
        m = load_npz(os.path.join(pdir, p['file']))
        n = 'hair_' + p['name']
        if not B0.has('o/%s/eval/V' % n):
            continue
        r, d = sweep.hair_arrays(B0, n, np.asarray(m.V, float), np.asarray(m.F, np.int64), np.asarray(m.vn, float))
        k = 'o/%s/eval/shrink' % n
        if ow and k in r and 'outline_w' in z.files:
            r[k] = (r[k] * np.asarray(z['outline_w'], float)[:, None]).astype(np.float32)
        rep.update(r)
    return sweep.spliced(B0, rep)

def read(B):
    _, C = artifactqa.measure(B, qa3d.Design(B), None)
    out = {}
    for k in ('terminator_hair', 'peeks_hair'):
        c = C.get(k) or C.get('art_' + k)
        out[k] = (c.get('value'), c.get('per_view'))
    return out

if __name__ == '__main__':
    base, pdir, ow = sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1
    B0 = bundle.load(os.path.join(base, 'bundle'))
    print(os.path.basename(base), pdir.split('/out/')[-1], 'ow', ow, json.dumps(read(splice(B0, pdir, bool(ow)))), flush=True)
