"""A build's locks on the design grids, cached, two ways: the strands as locks (hairlocks.TRUTH_FAMILIES, tool/hair5's
scorer) and the mass families only (LOCK_FAMILIES, the scorer before; the strands occlude as hair), so the change's
effect on the bangs-only scores can be checked. BUILD -> OUT.npz (the strands as locks) and OUT_mass.npz.

    python tools/hair5truth/ours5.py BUILD OUT.npz
"""
import json, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from charkit import hairlocks as hk


def build_locks(build, families):
    from charkit import bundle as bl, qa3d
    B = bl.load(os.path.join(build, 'bundle'))
    D = qa3d.Design(B)
    pdir = os.path.join(build, 'geom', 'hair_pieces')
    locks = hk.pieces_locks(pdir, families)
    P = json.load(open(os.path.join(pdir, 'pieces.json')))
    other = []
    for pc in P['pieces']:
        if pc['family'] not in families:
            Z = np.load(os.path.join(pdir, pc['file']))
            other.append((Z['V'], Z['F']))
    img, names = hk.lock_labels(B, D, locks, hair_other=other)
    return img, names, D.sheet_context()['ppl']


def load(path):
    Z = np.load(path)
    names = {int(k): v for k, v in json.loads(str(Z['names'])).items()}
    return {k: Z[k] for k in Z.files if k not in ('names', 'ppl')}, names, float(Z['ppl'])


if __name__ == '__main__':
    build, out = sys.argv[1], sys.argv[2]
    for fams, o in ((hk.TRUTH_FAMILIES, out), (hk.LOCK_FAMILIES, out.replace('.npz', '_mass.npz'))):
        img, names, ppl = build_locks(build, fams)
        np.savez_compressed(o, names=json.dumps(names), ppl=ppl, **img)
        for v, m in img.items():
            codes = np.unique(m[m > 0])
            print(o, v, len(codes), 'locks visible:', ', '.join('%s %d' % (names[c], (m == c).sum()) for c in codes))
