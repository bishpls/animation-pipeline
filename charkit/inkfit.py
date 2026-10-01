"""Crease strokes traced from the design (tool/garments4): the lines a design view draws inside a piece (its ink and its
fainter strokes, as declared.ink_inside reads them), skeletonized and traced into polylines in the QA's frame (x, z in L
from the view's origin and the eye line: bodyqa's grids), for a garment's `creases` {space: 'front', strokes}
(charkit.garments.ink_strokes projects them onto the piece's front). Templates first: the numbers then live in the
spec, checked in every view by the ink_inside checks (charkit.creaseqa), the other views being the cross-check.

    python -m charkit.inkfit SPEC PIECE [--region R] [--view front] [--band 0.02] [--min 0.03] [--tol 0.004]
                             [--build DIR]        prints the strokes as JSON (a build's bundle gives the design's grid)
    strokes = trace(mask, ppl, min_len, tol)        the skeleton's polylines (pixel rows, cols)
"""
import json, sys

import numpy as np

NB8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def _rdp(P, tol):
    """Ramer-Douglas-Peucker on a polyline (n, 2) -> the kept points."""
    if len(P) < 3:
        return P
    a, b = P[0], P[-1]
    d = b - a
    n = np.hypot(*d)
    dist = np.abs(d[0] * (P[:, 1] - a[1]) - d[1] * (P[:, 0] - a[0])) / n if n > 0 else np.hypot(*(P - a).T)
    i = int(np.argmax(dist))
    if dist[i] > tol:
        return np.r_[_rdp(P[:i + 1], tol)[:-1], _rdp(P[i:], tol)]
    return np.array([a, b])


def trace(S, ppl, min_len=0.03, tol=0.004):
    """a skeleton (bool image) traced into polylines: walked from its ends (and round its loops), split at junctions,
    each simplified to `tol` L, those shorter than `min_len` L dropped -> [array (n, 2) of (row, col)]."""
    S = np.asarray(S, bool).copy()
    H, W = S.shape
    nb = lambda r, c: [(r + dr, c + dc) for dr, dc in NB8 if 0 <= r + dr < H and 0 <= c + dc < W and S[r + dr, c + dc]]
    deg = {}
    for r, c in zip(*np.nonzero(S)):
        deg[(r, c)] = len(nb(r, c))
    used = set()
    paths = []

    def walk(p0):
        path = [p0]
        used.add(p0)
        cur = p0
        while True:
            nxt = [q for q in nb(*cur) if q not in used]
            if not nxt:
                break
            # prefer 4-neighbours (a skeleton's diagonal and straight steps both touch)
            nxt.sort(key=lambda q: abs(q[0] - cur[0]) + abs(q[1] - cur[1]))
            cur = nxt[0]
            path.append(cur)
            used.add(cur)
            if deg.get(cur, 0) > 2:
                break
        return path
    starts = sorted(p for p, d in deg.items() if d == 1) + sorted(p for p, d in deg.items() if d > 2)
    for p in starts:
        if p in used and deg[p] == 1:
            continue
        for q in ([p] if p not in used else [q for q in nb(*p) if q not in used]):
            if q in used and q != p:
                continue
            pth = walk(q) if q not in used else []
            if p in used and q != p and pth:
                pth = [p] + pth
            if len(pth) >= 2:
                paths.append(np.array(pth, float))
    for p in sorted(deg):                                         # loops (no ends)
        if p not in used:
            pth = walk(p)
            if len(pth) >= 2:
                paths.append(np.array(pth, float))
    out = []
    for P in paths:
        if np.hypot(*np.diff(P, axis=0).T).sum() / ppl < min_len:
            continue
        out.append(_rdp(P, tol * ppl))
    return out


def design_strokes(B, piece, region=None, view='front', band=0.02, min_len=0.03, tol=0.004):
    """the design's lines inside a piece's drawn region in one view (declared.ink_inside's: ink and fainter strokes,
    skeletonized, the outline's band left out), traced -> [[[x, z], ...], ...] in L (x from the view's origin, z from
    the eye line: bodyqa's grid)."""
    from scipy import ndimage
    from skimage.morphology import skeletonize
    from . import bodyqa, declared, outfit, qa3d
    I = declared.inputs(B, qa3d.Design(B), (view,))
    ppl = I['ppl']
    sh = I['O'][view]['lab'].shape
    R = declared.fit(I['masks']['%s__%s' % (view, region or piece)], sh)
    R = ndimage.binary_fill_holes(ndimage.binary_closing(R, iterations=3))
    inner = ndimage.binary_erosion(R, iterations=max(1, int(round(band * ppl))))
    dv = I['dv'][view]
    ink = (dv['raw'] == bodyqa.CLASS['line']) | (outfit.ridges(dv['rgb']) & (dv['raw'] != bodyqa.CLASS['skin']))
    S = skeletonize(declared.fit(ink, sh) & inner)
    W = sh[1]
    win = bodyqa.WIN
    st = [np.array([[(c - W / 2) / ppl, win['top'] - r / ppl] for r, c in P]) for P in trace(S, ppl, min_len, tol)]
    return [[[round(float(x), 4), round(float(z), 4)] for x, z in P] for P in join(st)]


def join(st, reach=0.035, turn=35.0):
    """strokes split at a junction joined again: two whose ends lie within `reach` L and whose directions there turn by
    under `turn` degrees become one -> the strokes."""
    st = [np.asarray(P, float) for P in st]
    ang = lambda u, v: np.degrees(np.arccos(np.clip(np.dot(u, v) / max(1e-12, np.linalg.norm(u) * np.linalg.norm(v)),
                                                    -1, 1)))
    while True:
        best = None
        for i in range(len(st)):
            for j in range(len(st)):
                if i == j:
                    continue
                for P in (st[i], st[i][::-1]):
                    for Q in (st[j], st[j][::-1]):
                        d = np.hypot(*(P[-1] - Q[0]))
                        if d < reach and ang(P[-1] - P[-2], Q[1] - Q[0]) < turn and (best is None or d < best[0]):
                            best = (d, i, j, P, Q)
        if best is None:
            return st
        _, i, j, P, Q = best
        st = [x for k, x in enumerate(st) if k not in (i, j)] + [np.r_[P, Q[1:]]]


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    from . import bundle
    B = bundle.load(opt('--build', 'charkit/out/g4_before') + '/bundle')
    st = design_strokes(B, args[1], opt('--region'), opt('--view', 'front'), float(opt('--band', 0.02)),
                        float(opt('--min', 0.03)), float(opt('--tol', 0.004)))
    print(json.dumps(st))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]) or 0)
