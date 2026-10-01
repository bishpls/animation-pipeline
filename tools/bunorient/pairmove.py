"""How far each hair object moved between two finished builds (tool/bunorient: which piece a gate pair moved, and the
buns' orientation): per object with the same vertex count in both bundles, the largest vertex move (L), and for the
buns their rigid part (Kabsch: the rotation angle in degrees between the two vertex sets about their centroids, and the
centroid's move) and what's left after it (L).

    python tools/bunorient/pairmove.py BUILD_A BUILD_B [OUT.json]
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import numpy as np


def kabsch(A, B):
    """the rotation taking A's shape onto B's (both centred) -> (angle deg, R, residual max (m))."""
    a, b = A - A.mean(0), B - B.mean(0)
    U, _, Vt = np.linalg.svd(a.T @ b)
    d = np.sign(np.linalg.det(U @ Vt))
    R = (U @ np.diag([1, 1, d]) @ Vt).T
    ang = float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))
    return ang, R, float(np.linalg.norm(a @ R.T - b, axis=1).max())


def compare(a, b):
    from charkit import bundle as bl
    A, B = bl.load(os.path.join(a, 'bundle')), bl.load(os.path.join(b, 'bundle'))
    L = float(A.assembly['L'])
    na = {o.name: o for o in A.objects(visible=False)}
    nb = {o.name: o for o in B.objects(visible=False)}
    out = dict(A=a, B=b, L=L, objects={})
    for n, oa in na.items():
        if oa.group != 'hair' or n not in nb:
            continue
        Va, Vb = np.asarray(oa.V(), float), np.asarray(nb[n].V(), float)
        if len(Va) != len(Vb):
            out['objects'][n] = dict(verts=(len(Va), len(Vb)))
            continue
        r = dict(max_move_L=float('%.3g' % (np.linalg.norm(Va - Vb, axis=1).max() / L)))
        if 'bun' in n:
            ang, R, res = kabsch(Va, Vb)
            r.update(rot_deg=round(ang, 4), centroid_L=float('%.3g' % (np.linalg.norm(Va.mean(0) - Vb.mean(0)) / L)),
                     nonrigid_L=float('%.3g' % (res / L)))
        out['objects'][n] = r
    return out


if __name__ == '__main__':
    r = compare(sys.argv[1], sys.argv[2])
    for n, v in sorted(r['objects'].items()):
        print('%-22s %s' % (n, v))
    if len(sys.argv) > 3:
        json.dump(r, open(sys.argv[3], 'w'), indent=1)
