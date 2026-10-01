"""Calibration adapter for Michael's hair flags (charkit.hairflagqa, part 'hair_flags'; tool/hair5). Ours is our hair's
label images on the design's grids and our ink inside the hair; here the design stands in: the hand-checked hair truth's
regions as our parts (its drawn lines and cut paths absorbed into the nearest region, as our shells meet with no ink
between them) and the drawing's own lines as our ink, moved or perturbed; the part's measuring code runs unchanged on
them (hairflagqa.our_labels and our_lines patched for the run).

Generators (the floors and the probes; seeded):
  rotate_ahoge   the drawn ahoge turned about its root by 25-45 degrees either way (a strand bent off its drawn curl)
  blob_ahoge     the drawn ahoge replaced by an ellipse of its area along its root-to-tip axis (a clump)
  wiggle_ahoge   (probe) the drawn ahoge bent sideways along its length by a 1.5-wave of 0.012 L (bent and jagged)
  shift_pieces   each drawn ahoge and flyaway moved 0.03-0.06 L in a random direction (a piece off its root)
  voronoi_lines  the ink inside the mass: a random partition's boundaries (about the drawing's line length per L^2)
  solid          no ink inside the mass (a solid orange mass)
  stripes        (probe) the drawing's ink plus vertical lines every 0.12 L across the mass (the back's stripes)
  smooth_hem     the back view's hair with its lower edge smoothed over 0.15 L (a bob's hem)
"""
import contextlib

import numpy as np

from .labels import patched, voronoi

CALIBRATION = [
    dict(check='hair_ahoge_shape', part='hair_flags', adapter='HairFlags', known_bad='hair5_1580f95',
         baseline=['rotate_ahoge', 'blob_ahoge'], probes=['wiggle_ahoge'], shape=['hair_piece_ahoge'], better='higher'),
    dict(check='hair_ahoge_bend', part='hair_flags', adapter='HairFlags', known_bad='hair5_1580f95', kind='defect',
         baseline=['rotate_ahoge'], probes=['wiggle_ahoge'], shape=['hair_piece_ahoge', 'hair_ahoge_shape'],
         better='lower'),
    dict(check='hair_attached', part='hair_flags', adapter='HairFlags', known_bad='hair5_1580f95', kind='defect',
         baseline=['shift_pieces'], shape=['hair_piece_flyaways', 'hair_piece_ahoge'], better='lower'),
    dict(check='hair_back_lines', part='hair_flags', adapter='HairFlags', known_bad='hair5_1580f95', kind='defect',
         baseline=['voronoi_lines'], probes=['stripes'], shape=['hair_piece_upper_back', 'hair_piece_lower_back'],
         better='lower'),
    dict(check='hair_lock_lines_*', part='hair_flags', adapter='HairFlags', known_bad='hair5_1580f95',
         baseline=['voronoi_lines', 'solid'], probes=['stripes'],
         shape=['hair_piece_side_locks', 'hair_piece_upper_back', 'hair_piece_lower_back', 'hair_piece_bangs'],
         better='higher'),
    dict(check='hair_back_hem', part='hair_flags', adapter='HairFlags', known_bad='hair5_1580f95', kind='defect',
         baseline=['smooth_hem'], shape=['hair_piece_lower_back', 'hair_piece_upper_back'], better='lower'),
]


def _rotate(m, centre, deg):
    """a mask turned by deg about centre (row, col)."""
    from scipy import ndimage
    a = np.radians(deg)
    R = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
    c = np.asarray(centre, float)
    # output p reads input R^T (p - c) + c
    return ndimage.affine_transform(m.astype(np.uint8), R.T, offset=c - R.T @ c, order=0, mode='constant',
                                    cval=0).astype(bool)


def _root_tip(ah, rest):
    """a strand's root (the centroid of its pixels touching `rest`, else its lowest) and tip (its pixel furthest from
    the root) as (row, col)."""
    from scipy import ndimage
    r, c = np.nonzero(ah)
    touch = ndimage.binary_dilation(rest, iterations=2) & ah
    if touch.any():
        rr, cc = np.nonzero(touch)
        root = np.array([rr.mean(), cc.mean()])
    else:
        k = int(np.argmax(r))
        root = np.array([r[k], c[k]], float)
    k = int(np.argmax(np.hypot(r - root[0], c - root[1])))
    return root, np.array([r[k], c[k]], float)


def _refill(lab, gone, keep_codes=None):
    """pixels a moved piece left: the nearest label of what stayed (the sky, the mass behind)."""
    from scipy import ndimage
    if not gone.any():
        return lab
    src = ~gone
    _, (iy, ix) = ndimage.distance_transform_edt(~src, return_indices=True)
    out = lab.copy()
    out[gone] = lab[iy[gone], ix[gone]]
    return out


class HairFlags:
    part = 'hair_flags'
    generators = {
        'rotate_ahoge': 'the drawn ahoge turned about its root by 25-45 degrees either way',
        'blob_ahoge': "the drawn ahoge replaced by an ellipse of its area along its root-to-tip axis (a clump)",
        'wiggle_ahoge': 'the drawn ahoge bent sideways along its length by a 1.5-wave of 0.012 L',
        'shift_pieces': 'each drawn ahoge and flyaway moved 0.03-0.06 L in a random direction',
        'voronoi_lines': "the ink inside the mass: a random partition's boundaries (about the drawing's line length)",
        'solid': 'no ink inside the mass (a solid orange mass)',
        'stripes': "the drawing's ink plus vertical lines every 0.12 L across the mass",
        'smooth_hem': "the back view's hair with its lower edge smoothed over 0.15 L (a bob's hem)",
    }

    def __init__(self, B, design):
        from .. import hairflagqa as hf, hairlayers
        self.B, self.design = B, design
        self.D, self.ppl = hf.design_inputs(B, design)
        self.truth = hairlayers.load_truth(hairlayers._p(hf.truth_path(B)))
        self.lab, self.pieces = hf.design_labels(self.truth, design.design_views())
        self.lines = self.D['lines']

    def _codes(self, names):
        from ..hairflagqa import PART0
        return [PART0 + i for i, p in enumerate(self.pieces) if p in names]

    def stand_in(self, kind, arg):
        """({view: labels}, {view: lines}) for a move (kind 'design', arg (dy, dx)) or a generator (arg its seed)."""
        from scipy import ndimage
        from .. import hairflagqa as hf
        ppl = self.ppl
        if kind == 'design':
            return ({v: hf.shift(L, arg[0], arg[1], 0) for v, L in self.lab.items()},
                    {v: hf.shift(m, arg[0], arg[1], False) for v, m in self.lines.items()})
        rng = np.random.default_rng(7000 + int(arg))
        lab = {v: L.copy() for v, L in self.lab.items()}
        lines = dict(self.lines)
        ah_codes = self._codes(('ahoge',))
        if kind in ('rotate_ahoge', 'blob_ahoge', 'wiggle_ahoge'):
            for v, L in lab.items():
                ah = np.isin(L, ah_codes)
                if ah.sum() < hf.MIN_PX:
                    continue
                code = int(np.bincount(L[ah]).argmax())
                rest = (L >= hf.PART0) & ~ah
                root, tip = _root_tip(ah, rest)
                if kind == 'rotate_ahoge':
                    new = _rotate(ah, root, rng.uniform(25, 45) * rng.choice([-1, 1]))
                elif kind == 'blob_ahoge':
                    r, c = np.nonzero(ah)
                    cen = np.array([r.mean(), c.mean()])
                    ax = (tip - root) / (np.linalg.norm(tip - root) + 1e-9)
                    a = 0.5 * np.linalg.norm(tip - root) * 0.8
                    b = ah.sum() / (np.pi * a)
                    yy, xx = np.mgrid[:L.shape[0], :L.shape[1]]
                    dy, dx = yy - cen[0], xx - cen[1]
                    u = dy * ax[0] + dx * ax[1]
                    w = -dy * ax[1] + dx * ax[0]
                    new = (u / a) ** 2 + (w / b) ** 2 <= 1
                else:
                    r, c = np.nonzero(ah)
                    ax = (tip - root) / (np.linalg.norm(tip - root) + 1e-9)
                    t = ((r - root[0]) * ax[0] + (c - root[1]) * ax[1]) / (np.linalg.norm(tip - root) + 1e-9)
                    off = 0.012 * ppl * np.sin(2 * np.pi * 1.5 * np.clip(t, 0, 1)) * np.clip(t * 4, 0, 1)
                    nr = np.clip(np.rint(r - ax[1] * off).astype(int), 0, L.shape[0] - 1)
                    nc = np.clip(np.rint(c + ax[0] * off).astype(int), 0, L.shape[1] - 1)
                    new = np.zeros_like(ah)
                    new[nr, nc] = True
                    new = ndimage.binary_closing(new, iterations=1)
                L2 = _refill(L, ah)
                L2[new & (L2 < hf.PART0)] = code
                lab[v] = L2
        elif kind == 'shift_pieces':
            codes = self._codes(('ahoge', 'flyaways'))
            for v, L in lab.items():
                L2 = L.copy()
                for code in codes:
                    m = L == code
                    if not m.any():
                        continue
                    a = rng.uniform(0, 2 * np.pi)
                    d = rng.uniform(0.03, 0.06) * ppl
                    dy, dx = int(round(d * np.sin(a))), int(round(d * np.cos(a)))
                    L2 = _refill(L2, L2 == code)
                    new = hf.shift(m, dy, dx, False)
                    L2[new & (L2 < hf.PART0)] = code
                lab[v] = L2
        elif kind in ('voronoi_lines', 'solid', 'stripes'):
            for v, L in lab.items():
                keep = self.D['keep'].get(v)
                if keep is None:
                    continue
                if kind == 'solid':
                    lines[v] = self.lines[v] & ~keep
                elif kind == 'stripes':
                    st = np.zeros_like(keep)
                    step = max(2, int(round(0.12 * ppl)))
                    st[:, ::step] = True
                    lines[v] = self.lines[v] | (st & keep)
                else:
                    ld = hf.skeleton(self.lines[v]) & keep
                    area = keep.sum() / ppl ** 2
                    dens = ld.sum() / ppl / max(area, 1e-6)
                    # a random partition of the mass with about the drawing's line length: n cells in area A give about
                    # 1.9 sqrt(n A) of boundary (a Voronoi tiling), so n ~ (dens A / 1.9)^2 / A
                    n = int(max(3, min(400, (dens * area / 1.9) ** 2 / max(area, 1e-6))))
                    V = voronoi(keep, list(range(n)), [1.0] * n, n, rng)
                    lines[v] = (self.lines[v] & ~keep) | (hf.part_lines(np.where(keep, V + hf.PART0, 0)) & keep)
        elif kind == 'smooth_hem':
            from scipy.ndimage import gaussian_filter1d
            v = 'back'
            L = lab[v]
            hair = L >= hf.PART0
            cols = np.nonzero(hair.any(0))[0]
            rows = np.arange(L.shape[0])
            low = np.array([rows[hair[:, c]].max() for c in cols], float)
            sm = gaussian_filter1d(low, 0.15 * ppl / 2.355, mode='nearest')
            L2 = L.copy()
            for c, lo, s in zip(cols, low, sm):
                s = int(round(s))
                if s < lo:
                    L2[s + 1:int(lo) + 1, c] = np.where(L2[s + 1:int(lo) + 1, c] >= hf.PART0, 0,
                                                       L2[s + 1:int(lo) + 1, c])
                elif s > lo:
                    col = L2[:, c]
                    fill = col[int(lo)]
                    seg = col[int(lo) + 1:s + 1]
                    col[int(lo) + 1:s + 1] = np.where(seg < hf.PART0, fill, seg)
            lab[v] = L2
        else:
            raise KeyError(kind)
        return lab, lines

    @contextlib.contextmanager
    def substitute(self, kind, arg):
        from .. import hairflagqa as hf
        lab, lines = self.stand_in(kind, arg)
        pieces = list(self.pieces)
        with patched([(hf, 'our_labels', lambda B, design: (lab, pieces)),
                      (hf, 'our_lines', lambda B, design, ours: lines)]):
            yield
