"""a pieces dir mixed for attribution: copy PIECES_IN, then drop some pieces' locks (their faces) or take some pieces
whole from another pieces dir.
    python tools/hairshell3/piecemix.py PIECES_IN OUT [drop:PIECE:a-b ...] [take:PIECE:OTHER_DIR ...]"""
import json, os, shutil, sys
import numpy as np
a = sys.argv[1:]
pin, out = a[:2]
if os.path.exists(out):
    shutil.rmtree(out)
shutil.copytree(pin, out)
for x in a[2:]:
    kind, name, arg = x.split(':', 2)
    f = os.path.join(out, name + '.npz')
    if kind == 'take':
        shutil.copy(os.path.join(arg, name + '.npz'), f)
        print('took', name, 'from', arg)
        continue
    z = dict(np.load(f))
    lo, hi = map(int, arg.split('-'))
    drop = (z['lock'] >= lo) & (z['lock'] <= hi)
    keepf = ~drop[z['F']].any(1)
    used = np.zeros(len(z['V']), bool); used[z['F'][keepf].ravel()] = True
    remap = np.cumsum(used) - 1
    nv = len(z['V'])
    for k, v in list(z.items()):
        if hasattr(v, 'shape') and v.shape[:1] == (nv,) and k != 'F':
            z[k] = v[used]
    z['F'] = remap[z['F'][keepf]]
    np.savez(f, **z)
    print('dropped', name, 'locks', arg, int(drop.sum()), 'vertices')
