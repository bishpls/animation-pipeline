"""Calibration adapter for the hand against its hand sheet (charkit.handsheetqa's 'hand_sheet' part: handsheet_open_span,
handsheet_open_fingers). The stand-in for ours is the sheet's own drawn hands (charkit.handsheet.cells) in place of our
template drawn on the sheet's terms: the design moved 1-2 px (its ratios can't move), and generated hands:

  wide_palm    floor: the open hand's palm widened across the arm about its middle, 1.25-1.45x (the fingers with it)
  narrow_palm  floor: narrowed, 0.6-0.8x
  long_palm    floor: the palm lengthened along the arm above the MCP line, 1.2-1.45x, the fingers carried down unchanged
               (the fingers short for their palm)
  thumb_only   invariant (Michael, 2026-10-01: the palm page read a thumb across the knuckle line as palm): the thumb
               alone turned 10-30 degrees about its root, toward the palm or away; the palm and fingers untouched. A
               structure check that moves under it reads the thumb, not the palm
Known-bad: comb_hand (de2fa87's hand: its spec's template, palm narrow for its length, the fingers fanned).
"""
import contextlib

import numpy as np

CALIBRATION = [
    dict(check='handsheet_open_span', part='hand_sheet', adapter='HandSheet', known_bad='comb_hand',
         baseline=['wide_palm', 'narrow_palm'], invariant=['thumb_only'], shape=['hand_shape_L', 'hand_shape_R'],
         better='lower'),
    dict(check='handsheet_open_fingers', part='hand_sheet', adapter='HandSheet', known_bad='comb_hand',
         baseline=['long_palm'], invariant=['thumb_only'], shape=['hand_shape_L', 'hand_shape_R'], better='lower'),
]


class HandSheet:
    part = 'hand_sheet'
    generators = {
        'wide_palm': "the sheet's open hand widened across the arm about its middle, 1.25-1.45x",
        'narrow_palm': "the sheet's open hand narrowed across the arm about its middle, 0.6-0.8x",
        'long_palm': "the sheet's open hand's palm lengthened along the arm above its MCP line, 1.2-1.45x, the fingers "
                     "carried down unchanged",
        'thumb_only': "the sheet's open hand's thumb alone turned 10-30 degrees about its root (toward the palm or away)",
    }

    def __init__(self, B, design=None):
        from .. import handsheet
        self.B, self.design = B, design
        self.S = handsheet.cells()

    def hands(self, kind, arg):
        """the stand-in's 'ours': {(pose, row): h} the sheet's own, the open hand changed by the generator."""
        from ..calib.labels import _shift
        out = {}
        for k, h in self.S.items():
            h2 = dict(h)
            if kind == 'design':
                dy, dx = arg
                h2['mask'] = _shift(h['mask'], dy, dx, False)
                h2['c'] = np.asarray(h['c'], float) + [dx, dy]
            out[k] = h2
        if kind != 'design':
            rng = np.random.default_rng(7000 + int(arg))
            out[('open', 'back')] = dict(out[('open', 'back')], mask=_generated(self.S[('open', 'back')], kind, rng))
        return out

    @contextlib.contextmanager
    def substitute(self, kind, arg):
        from .. import handsheetqa
        from .labels import patched
        H = self.hands(kind, arg)
        with patched([(handsheetqa, 'ours', lambda B, poses=handsheetqa.POSES: H)]):
            yield

    def measure(self, B):
        from .. import handsheetqa
        return {'handsheet_' + k: v for k, v in handsheetqa.measure(B)[1].items()}

    def run(self, kind, arg):
        with self.substitute(kind, arg):
            return self.measure(self.B)


def _generated(h, kind, rng):
    """an open hand's mask changed by a generator (see the module doc)."""
    from scipy import ndimage
    from .. import handsheet
    m = h['mask']
    c, u = np.asarray(h['c'], float), np.asarray(h['u'], float)
    acr = np.array([-u[1], u[0]])
    H, W = m.shape
    yy, xx = np.mgrid[:H, :W].astype(float)
    P = np.stack([xx - c[0], yy - c[1]], -1)
    s, t = P @ u, P @ acr
    D = handsheet.digits(h)
    L = handsheet.landmarks(h, open_hand=D)
    r = L['reach_px']
    t0 = float(np.mean([(np.asarray(w) - c) @ acr for w in L['webs']]))      # the palm's middle across
    s_mcp = h['end'] * h['ppl'] + L['mcp_s'] * r
    if kind in ('wide_palm', 'narrow_palm'):
        k = rng.uniform(1.25, 1.45) if kind == 'wide_palm' else rng.uniform(0.6, 0.8)
        ss, tt = s, t0 + (t - t0) / k                         # (inverse map: the source of each output pixel)
    elif kind == 'long_palm':
        k = rng.uniform(1.2, 1.45)
        s_end = h['end'] * h['ppl']
        ss = np.where(s < s_end + (s_mcp - s_end) * k, s_end + (s - s_end) / k, s - (k - 1) * (s_mcp - s_end))
        ss = np.where(s < s_end, s, ss)
        tt = t
    elif kind == 'thumb_only':
        th = max(D['digits'], key=lambda d: d['angle'])
        wp = np.array(L['wrist_pts'])
        root = wp[np.argmin([np.linalg.norm(p - th['tip']) for p in wp])]
        web = np.asarray(th['cleft'], float)
        # the thumb's region: the hand past the line from its root to its web, on the thumb's side
        n = web - root
        n = np.array([-n[1], n[0]])
        if (th['tip'] - root) @ n < 0:
            n = -n
        Q = np.stack([xx, yy], -1) - root
        thumb = m & ((Q @ n) > 0) & ((Q @ (web - root)) > -0.05 * r)
        lab, k_ = ndimage.label(thumb)
        if k_:
            ti = lab[int(round(th['tip'][1])), int(round(th['tip'][0]))] if m[int(round(th['tip'][1])),
                                                                                 int(round(th['tip'][0]))] else 0
            thumb = (lab == ti) if ti else thumb
        ang = np.radians(rng.uniform(10, 30) * (1 if rng.random() < 0.5 else -1))
        rest = m & ~thumb
        ys, xs = np.nonzero(thumb)
        Pt = np.c_[xs, ys] - root
        R = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
        Pn = Pt @ R.T + root
        out = rest.copy()
        xi, yi = np.round(Pn[:, 0]).astype(int), np.round(Pn[:, 1]).astype(int)
        ok = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
        out[yi[ok], xi[ok]] = True
        return ndimage.binary_closing(out, iterations=1) | rest
    else:
        raise KeyError(kind)
    X = c[0] + ss * u[0] + tt * acr[0]
    Y = c[1] + ss * u[1] + tt * acr[1]
    return ndimage.map_coordinates(m.astype(float), [Y, X], order=0, mode='constant', cval=0.0) > 0.5
