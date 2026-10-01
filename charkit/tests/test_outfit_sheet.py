"""charkit.outfit_sheet: a rig-free character's skeleton from its front silhouette, and its piece masks by palette within
each piece's zone."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import outfit_sheet as osh  # noqa: E402

PPL = 50.0


def figure():
    """a front A-pose figure (eye line at row 100, axis at column 300, 50 px per L): a head, a torso widening at the
    shoulders (z -0.9), arms apart from the body below z -1.6 reaching to z -3.6, legs parting at z -3.0, soles at -6.9.
    A 1-px vertical stroke through the torso (a drawn line) must not split it."""
    H, W = 500, 600
    m = np.zeros((H, W), bool)
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    m |= ((xx - 300) / 28) ** 2 + ((yy - 95) / 38) ** 2 <= 1                      # head
    m |= (np.abs(xx - 300) < 12) & (yy > 120) & (yy < 145)                          # neck
    z = (100 - yy) / PPL
    m |= (np.abs(xx - 300) < 60) & (z < -0.9) & (z > -3.1)                          # torso and hips
    for s in (-1, 1):                                                                # arms: from the shoulder out and down
        t = np.clip((-0.95 - z) / 2.65, 0, 1)
        cx = 300 + s * (55 + 40 * t)
        m |= (np.abs(xx - cx) < 10 + 6 * (z > -1.6)) & (z < -0.95) & (z > -3.6)
        m |= (np.abs(xx - (300 + s * 28)) < 22) & (z <= -3.0) & (z > -6.9)          # legs
    m[:, 300] &= ~((z[:, 0] < -1.0) & (z[:, 0] > -2.5))                                        # the drawn stroke
    return m


def test_skeleton_from_the_front_silhouette():
    sk, rows = osh.skeleton_front(figure(), (300.0, 100.0), PPL)
    assert abs(rows['shoulder'] + 0.9) < 0.1, rows
    assert abs(rows['crotch'] + 3.1) < 0.05, rows                                   # the torso's bottom
    assert abs(rows['sole'] + 6.9) < 0.05, rows
    for b in ('head', 'neck', 'chest', 'hips', 'leftUpperArm', 'rightHand', 'leftUpperLeg', 'rightFoot'):
        assert b in sk, b
    assert sk['leftUpperArm'][0][0] > 0 > sk['rightUpperArm'][0][0]                # the character's left: image right
    tip = sk['leftHand'][1]
    assert abs(tip[1] + 3.6) < 0.1 and tip[0] > 1.5, tip                             # the fingertips, out to the side
    assert sk['leftFoot'][1][1] < -6.8


def test_zone_band_takes_both_sides_and_pads():
    sk = {'leftFoot': ((0.5, -6.0), (0.5, -6.5)), 'rightFoot': ((-0.5, -6.1), (-0.5, -6.5)),
          'spine': ((0, -2.5), (0, -2.0))}
    lo, hi = osh.zone_band(sk, ['Foot'])
    assert abs(lo - (-6.5 - osh.ZONE_PAD)) < 1e-9 and abs(hi - (-6.0 + osh.ZONE_PAD)) < 1e-9
    assert osh.zone_band(sk, ['nothing']) is None


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
