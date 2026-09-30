"""charkit.eyeqa on drawn eyes with known answers (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import eyeqa

AMBER, WHITE, DARK, SKIN = (0.85, 0.6, 0.15), (0.97, 0.97, 0.99), (0.08, 0.05, 0.04), (1.0, 0.88, 0.82)


def eye(n=200, open_h=0.8, pupil=(0.25, 0.4), gap=0):
    """an eye drawing: an opening (ellipse, height open_h of its width), an iris 0.3 of the width filling the height,
    a pupil (its half-axes as shares of the iris's), a lid line `gap` px above the opening, skin around."""
    yy, xx = np.mgrid[0:n, 0:n] / n
    im = np.zeros((n, n, 4)); im[..., :3] = SKIN; im[..., 3] = 1
    op = ((xx - 0.5) / 0.4) ** 2 + ((yy - 0.5) / (0.4 * open_h)) ** 2 <= 1
    ir = (((xx - 0.5) / 0.12) ** 2 + ((yy - 0.5) / (0.4 * open_h)) ** 2 <= 1) & op
    pu = ((xx - 0.5) / (0.12 * pupil[0])) ** 2 + ((yy - 0.5) / (0.4 * open_h * pupil[1])) ** 2 <= 1
    im[op, :3] = WHITE; im[ir, :3] = AMBER; im[pu & ir, :3] = DARK
    # the upper lid line: a band following the opening's top edge, lifted `gap` px off it
    yl = yy + gap / n
    band = (((xx - 0.5) / 0.42) ** 2 + ((yl - 0.5) / (0.4 * open_h + 0.03)) ** 2 <= 1) & \
           ~(((xx - 0.5) / 0.4) ** 2 + ((yl - 0.5) / (0.4 * open_h)) ** 2 <= 1) & (yl < 0.5) & ~op
    im[band, :3] = DARK
    return im


def test_measures():
    M = eyeqa.measure(eye(), 200.0)                                   # 200 px per L
    assert abs(M['aspect'] - 0.8) < 0.05, M['aspect']
    assert abs(M['pupil_run'] - 0.4) < 0.06, M['pupil_run']
    assert M['lid_gap'] is not None and M['lid_gap'] < 0.01


def test_slit_and_flat_eye_fail():
    d = eyeqa.measure(eye(), 200.0)
    o = eyeqa.measure(eye(open_h=0.55, pupil=(0.12, 0.8), gap=8), 200.0)
    C = eyeqa.compare(o, d)
    assert C['aspect']['status'] == 'FAIL' and C['pupil_run']['status'] == 'FAIL' and C['pupil_aspect']['status'] == 'FAIL'
    assert C['lid_gap']['status'] in ('WARN', 'FAIL')
    same = eyeqa.compare(d, d)
    assert all(v['status'] == 'PASS' for v in same.values()), same


def drawn(n=120, ss=4, iris_x=0.5, iris_rx=0.12, pupil=(0.028, 0.10), open_rx=0.4, open_h=0.8, front=None):
    """an anti-aliased eye drawing (drawn at ss times the size, box-filtered down): an opening (an ellipse, or with
    front='flat' a vertical front edge at its left), an iris (iris_rx of the picture's width, at iris_x, as tall as the
    opening), a pupil ellipse (half-axes in picture widths) at the iris's centre, skin round it."""
    N = n * ss
    yy, xx = (np.mgrid[0:N, 0:N] + 0.5) / N
    op = ((xx - 0.5) / open_rx) ** 2 + ((yy - 0.5) / (open_rx * open_h)) ** 2 <= 1
    if front == 'flat':
        op = (np.abs(yy - 0.5) <= open_rx * open_h * np.sqrt(np.clip(1 - ((xx - 0.1) / (2 * open_rx)) ** 2, 0, 1))) & \
             (xx >= 0.1) & (xx <= 0.1 + 2 * open_rx)
    ir = (((xx - iris_x) / iris_rx) ** 2 + ((yy - 0.5) / (open_rx * open_h)) ** 2 <= 1) & op
    pu = ((xx - iris_x) / pupil[0]) ** 2 + ((yy - 0.5) / pupil[1]) ** 2 <= 1
    im = np.zeros((N, N, 3)); im[:] = SKIN
    im[op] = WHITE; im[ir] = AMBER; im[pu & ir] = DARK
    im = im.reshape(n, ss, n, ss, 3).mean((1, 3))
    return np.concatenate([im, np.ones((n, n, 1))], -1)


def test_pupil_shape_sub_pixel():
    """a 6.7 px wide pupil ellipse: its width over the iris's at 25/50/75% of its height (an ellipse's quarter widths
    are sqrt(3)/2 of its middle's), its area share, axis ratio and centre, measured to a few percent."""
    n = 120
    im = drawn(n, pupil=(0.028, 0.10))
    M = eyeqa.measure_view(im, 400.0, nasal=-1)
    iris_w = 2 * 0.12 * np.sqrt(1 - 0 ** 2)                          # the iris's chord at its middle row (picture widths)
    assert abs(M['pupil_w50'] - 2 * 0.028 / iris_w) < 0.02, M['pupil_w50']
    assert abs(M['pupil_taper'] - np.sqrt(3) / 2) < 0.05, M['pupil_taper']
    assert abs(M['pupil_axis'] - 0.28) < 0.03, M['pupil_axis']
    assert abs(M['pupil_h'] * 400 / n - 0.2) < 0.02, M['pupil_h']       # its height, less the tips' half-pixel cut
    assert abs(M['pupil_cx']) < 0.05 and abs(M['pupil_cy']) < 0.05, (M['pupil_cx'], M['pupil_cy'])
    assert abs(M['pupil_fill'] - 1.0) < 0.06, M['pupil_fill']
    # a slit (thin and even) and a round pupil: the width profile and the axis ratio tell them apart
    slit = eyeqa.measure_view(drawn(n, pupil=(0.012, 0.16)), 400.0)
    rnd = eyeqa.measure_view(drawn(n, pupil=(0.05, 0.05)), 400.0)
    assert slit['pupil_w50'] < M['pupil_w50'] < rnd['pupil_w50']
    assert slit['pupil_axis'] < M['pupil_axis'] < rnd['pupil_axis'] and rnd['pupil_axis'] > 0.9


def test_gaze_front_gap():
    """an iris against the opening's nasal edge has no front gap and all its sclera behind; centred, it has the gap
    and half behind; the offset's sign follows the nose's side."""
    front = eyeqa.measure_view(drawn(iris_x=0.22, iris_rx=0.12), 400.0, nasal=-1)
    mid = eyeqa.measure_view(drawn(iris_x=0.5, iris_rx=0.12), 400.0, nasal=-1)
    assert front['front_gap'] < 0.03 and front['behind'] > 0.95 and front['gaze_off'] > 0.2, front
    assert 0.25 < mid['front_gap'] < 0.4 and abs(mid['behind'] - 0.5) < 0.05 and abs(mid['gaze_off']) < 0.02, mid
    flip = eyeqa.measure_view(drawn(iris_x=0.22, iris_rx=0.12), 400.0, nasal=1)
    assert flip['front_gap'] > 0.3 and flip['gaze_off'] < -0.2


def test_front_edge_straight_or_pointed():
    """an opening whose nasal edge is a vertical line measures straight and upright; an almond's pointed corner doesn't."""
    flat = eyeqa.measure_view(drawn(front='flat', iris_x=0.22), 400.0, nasal=-1)
    almond = eyeqa.measure_view(drawn(), 400.0, nasal=-1)
    assert abs(flat['edge_angle']) < 3 and flat['edge_rms'] < 0.01, flat
    assert almond['edge_rms'] > 2 * flat['edge_rms'] + 0.01, almond


def test_views_design_against_itself_resampled():
    """the head sheet's eyes against themselves, shifted half a pixel and at 0.8 and 1.25 times the scale: every
    per-view check passes (the measures hold across the render grid and scale)."""
    import json
    from PIL import Image
    from charkit import eyepage
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    spec = json.load(open(os.path.join(root, 'charkit/spec/clawd_body.json')))
    spec['ref']['manifest'] = os.path.join(root, spec['ref']['manifest'])
    des, ppl = eyepage.design_eyes(spec)
    for view, pairs in des.items():
        for side, px in pairs:
            n = eyeqa.NASAL[(view, side)]
            d = eyeqa.measure_view(px, ppl, n)
            for s in (0.8, 1.25):
                H, W = px.shape[:2]
                im = np.asarray(Image.fromarray((px * 255).astype(np.uint8)).resize((int(W * s), int(H * s)),
                                Image.BICUBIC), float) / 255
                im[..., 3] = (im[..., 3] > 0.5)
                o = eyeqa.measure_view(im, ppl * s, n)
                C = eyeqa.compare_view(o, d, eyeqa.VIEW_CHECKS[view])
                bad = {k: (c['ours'], c['design']) for k, c in C.items() if c['status'] != 'PASS'}
                assert not bad, (view, side, s, bad)


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
