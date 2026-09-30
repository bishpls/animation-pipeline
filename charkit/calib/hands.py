"""Calibration adapter for the hands (charkit.handqa's 'hands' part: hand_shape_*, hand_*_reach_*, hand_*_digits_*,
hand_*_cleft_*). The stand-in for ours is labels.py's Garments (the drawing's skin class and the outfit's drawn piece
masks as our objects' labels, the drawing's lines absorbed: our skin, our wrist cuffs), with the drawing's ink inside
the figure standing for the seams our outline draws (handqa.our_seams), moved with the labels.

Generators (seeded):
  stub_hands   each drawn hand cut off at 35-60% of its reach past the cuff (a short, fingerless hand: the mitten's
               fault, at random lengths)
  blob_hands   each drawn hand replaced by the ellipse of its own area, centroid and second moments (the best a mitten
               can do: no digits, no cleft; as a probe of the silhouette checks: in the views that draw the fingers
               together, the back of the hand in profile, a matched blob is a fair silhouette, so hand_shape can't be
               the digits' check)
Known-bad: mitten (pipeline-3d 1580f95's preview build: the authored body's hand, the arm's tube ending in a capped
stub 0.21-0.25 L past the cuff where the drawn hands reach 0.59-0.62 L).
"""
import contextlib

import numpy as np

from .labels import Garments, _shift, patched

CALIBRATION = [
    dict(check='hand_shape_[LR]', part='hands', adapter='Hands', known_bad='mitten',
         baseline=['stub_hands'], probes=['blob_hands'], shape=[], better='higher'),
    dict(check='hand_*_reach_[LR]', part='hands', adapter='Hands', known_bad='mitten',
         baseline=['stub_hands'], shape=['hand_shape_L', 'hand_shape_R'], better='lower'),
    dict(check='hand_*_digits_[LR]', part='hands', adapter='Hands', known_bad='mitten',
         baseline=['blob_hands'], shape=['hand_shape_L', 'hand_shape_R'], better='lower'),
    dict(check='hand_*_cleft_[LR]', part='hands', adapter='Hands', known_bad='mitten',
         baseline=['blob_hands'], shape=['hand_shape_L', 'hand_shape_R'], better='lower'),
]


class Hands(Garments):
    """hands: Garments' labels, the drawn ink as our seams, and the drawn hands for the generators."""
    part = 'hands'
    generators = {
        'stub_hands': 'each drawn hand cut off at 35-60% of its reach past the cuff',
        'blob_hands': "each drawn hand replaced by the ellipse of its own area, centroid and second moments",
    }

    def __init__(self, B, design):
        from .. import bodymeasure, handqa
        Garments.__init__(self, B, design)
        masks, graph, _ = bodymeasure.piece_masks(B.spec)
        self.pm = bodymeasure.piece_map(graph, B.spec)
        self.seams = handqa.design_seams(self.dv)
        idx = {n: i for i, n in enumerate(self.names)}
        self.skin = [idx[n] for n in handqa._skin_names(B, self.names) if n in idx][:1]
        self.hands = {}
        for v, lab in self.lab.items():
            sk = np.isin(lab, [c + k for c in self.skin for k in (0, 1000)])
            for s in handqa.sides(v):
                from ..pieceqa import members
                cuff = members(lab, self.names, self.pm, 'cuff_' + s)
                h = handqa.hand_mask(sk, cuff, self.ppl) if cuff.sum() >= handqa.MIN_PX else None
                if h is not None:
                    h['cuff'] = cuff
                    self.hands[(v, s)] = h

    def labels(self, kind, arg):
        if kind == 'design':
            return {v: _shift(L, arg[0], arg[1], -1) for v, L in self.lab.items()}
        from .. import handqa
        rng = np.random.default_rng(4000 + int(arg))
        out = {v: L.copy() for v, L in self.lab.items()}
        self._cleared = {v: np.zeros(L.shape, bool) for v, L in self.lab.items()}
        for (v, s), h in sorted(self.hands.items()):
            m = h['mask']
            if kind == 'stub_hands':
                sS, _ = handqa.coords(m.shape, h['c'], h['u'], self.ppl)
                cut = h['end'] + rng.uniform(0.35, 0.6) * handqa.reach(h, self.ppl)
                gone = m & (sS > cut)
                out[v][gone] = -1
                self._cleared[v] |= gone
            elif kind == 'blob_hands':
                e = ellipse(m) & ~h['cuff']              # (in front of everything but its own cuff, as the hand is)
                out[v][m & ~e] = -1
                out[v][e] = self.skin[0]
                self._cleared[v] |= m | e
            else:
                raise KeyError(kind)
        return out

    def seam_images(self, kind, arg):
        if kind == 'design':
            return {v: _shift(S, arg[0], arg[1], False) for v, S in self.seams.items()}
        return {v: S & ~self._cleared.get(v, np.zeros(S.shape, bool)) for v, S in self.seams.items()}

    @contextlib.contextmanager
    def substitute(self, kind, arg):
        from .. import handqa
        L = self.labels(kind, arg)
        S = self.seam_images(kind, arg)

        def our_seams(B, ppl, az3, O, names, views=handqa.VIEWS):
            return {v: S[v] for v in views if v in S}
        with patched(self.patches(L, kind) + [(handqa, 'our_seams', our_seams)]):
            yield


def ellipse(m):
    """the ellipse with a mask's area, centroid and second moments (pixels)."""
    ys, xs = np.nonzero(m)
    c = np.array([xs.mean(), ys.mean()])
    Si = np.linalg.inv(np.cov((np.c_[xs, ys] - c).T))
    yy, xx = np.mgrid[:m.shape[0], :m.shape[1]]
    Q = np.stack([xx - c[0], yy - c[1]], -1)
    d2 = np.einsum('...i,ij,...j->...', Q, Si, Q)
    return d2 <= np.partition(d2.ravel(), int(m.sum()) - 1)[int(m.sum()) - 1]
