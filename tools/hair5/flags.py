"""The hair flags' measures (charkit.hairflagqa) on the lab's label images: the design as ours, and builds.

    python tools/hair5/flags.py OUT.json NAME=OURS.npz ...
"""
import json, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'tools', 'hair5'))
import ctx
from charkit import hairflagqa as hf


def run(out, sets):
    B = ctx.load_build(os.path.join(ROOT, 'charkit/out/h4n_nocrown'))
    Dz = ctx.design(B)
    ppl = Dz['ppl']
    D = hf.design_side(Dz['truth'], Dz['dv'], ppl)
    res = {}
    lab, pcs = hf.design_labels(Dz['truth'], Dz['dv'])
    res['design'] = hf.measure_labels(lab, pcs, D, ppl, lines=D['lines'])
    for name, path in sets:
        Z = np.load(path)
        img = {v: Z[v] for v in hf.VIEWS if v in Z.files}
        res[name] = hf.measure_labels(img, json.loads(str(Z['pieces'])), D, ppl)
    json.dump(res, open(out, 'w'), indent=1, default=float)
    for name, (t, C) in res.items():
        print('==', name)
        for k, c in C.items():
            print('  %-30s %s' % (k, {a: b for a, b in c.items() if a != 'flag'}))
        print('   lines', {v: {k: x[k] for k in ('ours', 'design', 'p', 'r', 'f')} for v, x in t['lines'].items()})
    return res


if __name__ == '__main__':
    run(sys.argv[1], [a.split('=', 1) for a in sys.argv[2:]])
