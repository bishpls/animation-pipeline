"""charkit.faceflags' measures on drawn masks with known answers (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import faceflags as ff


def _ellipse(n, cx, cy, a, b):
    yy, xx = np.mgrid[0:n, 0:n] + 0.5
    return ((xx - cx) / a) ** 2 + ((yy - cy) / b) ** 2 <= 1


def eye_masks(n=300, iris_h=1.0):
    """an opening (an ellipse 0.7 as tall as wide) and an iris 0.4 of its width, its own height iris_h x the opening's,
    clipped by it; an arc lash band over it with three thin flicks off its top toward the outer end."""
    O = _ellipse(n, 150, 150, 100, 70)
    I = _ellipse(n, 150, 150, 40, 70 * iris_h) & O
    yy, xx = np.mgrid[0:n, 0:n] + 0.5
    band = _ellipse(n, 150, 150, 108, 84) & ~O & (yy < 150)
    flicks = np.zeros_like(O)
    for k, ang in enumerate((40, 50, 60)):                 # off the band's top, over its middle-outer part
        t = np.linspace(0, 30, 200)
        x = 175 + 18 * k + t * np.cos(np.radians(ang))
        y = 74 + 3 * k - t * np.sin(np.radians(ang))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                flicks[np.clip((y + dy).astype(int), 0, n - 1), np.clip((x + dx).astype(int), 0, n - 1)] = True
    return dict(I=I, O=O | I, U=band | (flicks & ~O))


def test_iris_fit_reads_an_inscribed_iris_as_one_and_a_clipped_one_over():
    a = ff.eye_numbers(eye_masks(iris_h=1.0), 900.0)
    b = ff.eye_numbers(eye_masks(iris_h=1.4), 900.0)
    assert abs(a['iris_fit'] - 1.0) < 0.05, a
    assert abs(b['iris_fit'] - 1.4) < 0.08, b
    assert b['iris_bottom'] < -0.15 < a['iris_bottom']


def test_lash_spikes_and_gaps_see_flicks_a_smooth_band_has_none():
    E = eye_masks()
    a = ff.eye_numbers(E, 900.0)
    from scipy import ndimage
    smooth = dict(E, U=ndimage.gaussian_filter(E['U'].astype(float), 5) > 0.5)
    b = ff.eye_numbers(smooth, 900.0)
    assert a['lash_spikes'] >= 3, a
    assert b['lash_spikes'] < a['lash_spikes'], (a, b)
    assert a['lash_gaps'] >= 2 and b['lash_gaps'] < a['lash_gaps'], (a, b)


def test_a_line_curve_reads_its_width_sag_and_thickness():
    n = 400
    m = np.zeros((n, n), bool)
    xs = np.arange(100, 300)
    ys = 200 + 0.002 * (xs - 200) ** 2 * -1 + 20          # an upturned smile: ends 20 px over its middle
    for x, y in zip(xs, ys):
        m[int(y) - 2:int(y) + 2, x] = True
    c = ff._line_curve(m, 400.0)
    assert abs(c['width'] - 0.5) < 0.01
    assert 0.08 < c['sag'] < 0.12, c                       # 20 px over 200 px wide
    assert abs(c['thick'] - 4 / 400.0) < 0.003


def test_brow_numbers_read_a_crescent_thicker_in_its_middle():
    n = 300
    m = np.zeros((n, n), bool)
    for x in range(50, 250):
        t = (x - 50) / 200.0
        y = 150 - 30 * np.sin(np.pi * t)
        th = 2 + 14 * np.sin(np.pi * t)
        m[int(y - th / 2):int(y + th / 2) + 1, x] = True
    b = ff._brow_numbers(m, 900.0)
    assert abs(b['length'] - 200 / 900.0) < 0.003
    assert b['taper'] < 0.6 and 0.12 < b['arch'] < 0.17, b


def test_corner_share_reads_the_far_corner_height():
    """the opening's far (outer) corner as a share of its height from the bottom (tool/face7): an opening whose outer
    fifth is a sliver a quarter of the way down its height reads 0.75 on that side; her right eye's outer end is the
    picture's left."""
    n = 200
    O = np.zeros((n, n), bool)
    top, bot = 50, 150                                     # rows; the corner row 75 -> (150 - 75) / 101
    for c in range(20, 181):
        t = (c - 20) / 160.0                               # 0 at the left end, 1 at the right
        if t > 0.8:
            O[74:77, c] = True                             # the far corner's sliver
        else:
            O[top:bot + 1, c] = True
    E = dict(O=O, I=np.zeros_like(O), U=np.zeros_like(O))
    got = ff.corner_share(E, 'L')
    assert abs(got - 75 / 101.0) < 0.03, got
    left = ff.corner_share(E, 'R')                         # the left end spans the whole height: its middle row
    assert abs(left - 0.5) < 0.03, left


def test_contour_reads_the_leading_edge_from_the_anchor():
    ppl = 200.0
    F = dict(ppl=ppl, anchor=(100.0, 50.0), lead=np.full(400, 70.0))      # the face's left edge 30 px left of it
    assert abs(ff.contour_at(F, ff.CONTOUR_ROWS) - 30 / ppl) < 1e-9
    F['lead'][:] = np.nan
    assert ff.contour_at(F, ff.CONTOUR_ROWS) is None


def test_the_calibration_registry_reads():
    from charkit import calibrate
    E = [e for e in calibrate.entries() if e['module'] == 'charkit.calib.faceflags']
    assert E and all(e['part'] == 'face_flags' for e in E)
    assert calibrate.entry_for('eye_iris_fit_front', E)['shape'] == ['face_piece_iris']


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
