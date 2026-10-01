"""A build's locks on the design grids, cached: BUILD -> OUT.npz ({view: image}, names) and a picture per view.

    python tools/hairlocks/ours.py BUILD OUT.npz
"""
import json, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from charkit import hairlocks as hk


def load(path):
    Z = np.load(path)
    names = {int(k): v for k, v in json.loads(str(Z['names'])).items()}
    return {k: Z[k] for k in Z.files if k not in ('names', 'ppl')}, names, float(Z['ppl'])


if __name__ == '__main__':
    build, out = sys.argv[1], sys.argv[2]
    img, names, ppl = hk.build_locks(build)
    np.savez_compressed(out, names=json.dumps(names), ppl=ppl, **img)
    for v, m in img.items():
        codes = np.unique(m[m > 0])
        print(v, len(codes), 'locks visible:', ', '.join('%s %d' % (names[c], (m == c).sum()) for c in codes))
