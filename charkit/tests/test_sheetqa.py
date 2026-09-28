"""charkit.sheetqa on a drawn face with known answers (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import sheetqa

BG, SKIN, LINE, IRIS, SHADE = (0.97, 0.97, 0.94), (0.98, 0.855, 0.757), (0.10, 0.08, 0.07), (0.95, 0.80, 0.10), (0.75, 0.62, 0.52)


def drawing(ppl=100.0, half_w=0.30, chin=0.40, neck=0.12):
    """a front face: an outlined skin ellipse (half-width half_w L, the chin `chin` L under the eye line), two iris dots
    0.168 L either side, a shaded neck `neck` L half-wide under a drawn jaw line."""
    n = 200
    im = np.ones((n, n, 3)) * BG
    yy, xx = np.mgrid[0:n, 0:n].astype(float)
    cx, ey = 100.0, 70.0
    top = ey - 0.3 * ppl
    cy, ry = (top + ey + chin * ppl) / 2, (ey + chin * ppl - top) / 2
    face = ((xx - cx) / (half_w * ppl)) ** 2 + ((yy - cy) / ry) ** 2 <= 1
    ring = (((xx - cx) / (half_w * ppl + 1.5)) ** 2 + ((yy - cy) / (ry + 1.5)) ** 2 <= 1) & ~face
    nk = (np.abs(xx - cx) <= neck * ppl) & (yy > cy) & ~face & ~ring
    im[nk] = SHADE; im[ring] = LINE; im[face] = SKIN
    for sx in (-1, 1):
        im[((xx - cx - sx * 0.168 * ppl) ** 2 + (yy - ey) ** 2) <= 16] = IRIS
    return im, [(cx - 0.168 * ppl, ey), (cx + 0.168 * ppl, ey)]


def test_front_measures():
    im, eyes = drawing()
    M = sheetqa.measure_figure(im, 'front', 100.0, eyes)
    assert abs(M['chin'] - (-0.40)) < 0.02, M['chin']
    # an ellipse's half-width at 55% of the way down from its centre-ish eye line: compare with the analytic value
    assert M['widths']['d55'] and 0.2 < M['widths']['d55'] < 0.31
    assert abs(M['neck'] - 0.12) < 0.02, M['neck']


def test_compare_catches_a_narrow_face_and_thick_neck():
    d_im, d_eyes = drawing()
    o_im, o_eyes = drawing(half_w=0.22, neck=0.18)
    D = {'front': sheetqa.measure_figure(d_im, 'front', 100.0, d_eyes)}
    O = {'front': sheetqa.measure_figure(o_im, 'front', 100.0, o_eyes)}
    C = sheetqa.compare(O, D)
    assert C['width']['status'] == 'FAIL' and C['neck_to_jaw']['status'] == 'FAIL'
    same = sheetqa.compare(D, D)
    assert same['width']['status'] == 'PASS' and same['neck_to_jaw']['status'] == 'PASS'


HAIR = (0.83, 0.48, 0.33)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def sheet(ppl=40.0):
    """a synthetic model sheet on paper: front, three-quarter, profile and back figures (a hair head, a skin face with iris
    dots where each view has eyes, an outlined body), an expression head and a hand (skin, no hair). -> (rgb, truth)."""
    H, W = 420, 900
    im = np.ones((H, W, 3)) * BG
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    truth = {}

    def disc(cx, cy, rx, ry, col, ring=True):
        m = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1
        if ring:
            im[(((xx - cx) / (rx + 1.5)) ** 2 + ((yy - cy) / (ry + 1.5)) ** 2 <= 1) & ~m] = LINE
        im[m] = col
        return m
    ey = 60.0
    for view, cx, eyes in (('front', 90, (-0.168, 0.168)), ('three_quarter', 300, (-0.26, 0.02)), ('profile', 500, (-0.3,)),
                           ('back', 700, ())):
        body = (np.abs(xx - cx) <= 0.45 * ppl) & (yy > ey + 0.5 * ppl) & (yy < ey + 5.0 * ppl)
        im[body] = (0.8, 0.4, 0.25)
        disc(cx, ey - 0.1 * ppl, 0.62 * ppl, 0.62 * ppl, HAIR)
        if eyes:
            fx = cx + (eyes[0] + eyes[-1]) / 2 * ppl if view != 'profile' else cx - 0.25 * ppl
            disc(fx, ey + 0.12 * ppl, 0.38 * ppl, 0.42 * ppl, SKIN, ring=False)
            for e in eyes:
                disc(cx + e * ppl, ey, 0.07 * ppl, 0.09 * ppl, IRIS, ring=False)
        truth[view] = dict(cx=cx, eyes=[cx + e * ppl for e in eyes])
    # an expression head (closed eyes: no iris) and a hand
    disc(820, 330, 0.62 * ppl, 0.62 * ppl, HAIR); disc(820, 342, 0.38 * ppl, 0.4 * ppl, SKIN, ring=False)
    disc(840, 150, 18, 24, SKIN)
    return im, truth


def test_label_counts_components():
    m = np.zeros((20, 30), bool)
    m[2:5, 2:6] = True; m[10:18, 10:12] = True; m[10:12, 12:20] = True; m[15, 25] = True
    lab, n = sheetqa.label(m)
    assert n == 3
    B, area = sheetqa.boxes(lab, n)
    assert sorted(area.tolist()) == [1, 12, 32]


def test_detect_figures_on_a_synthetic_sheet():
    ppl = 40.0
    im, truth = sheet(ppl)
    D = sheetqa.detect_figures(im, ppl=ppl)
    assert set(D['figures']) == {'front', 'three_quarter', 'profile', 'back'}, D['figures'].keys()
    assert D['facing'] == -1
    for v, t in truth.items():
        f = D['figures'][v]
        assert len(f['eyes']) == len(t['eyes']), (v, f['eyes'])
        for (x, _), tx in zip(f['eyes'], t['eyes']):
            assert abs(x - tx) < 1.5
        assert abs(f['eye_y'] - 60) < 1.5, (v, f['eye_y'])
    # the head box: HEAD_BOX's framing round the eyes (front: centred on them, `back` L toward the back of the head)
    K = sheetqa.HEAD_BOX
    hb = D['figures']['front']['head']
    assert abs((hb[0] + hb[2]) / 2 - (90 + K['back'] * ppl)) <= 1 and abs(hb[1] - (60 - K['above'] * ppl)) <= 1
    assert abs(hb[2] - hb[0] - K['size'] * ppl) <= 1
    pb = D['figures']['profile']['head']                       # a turned view: centred `axis` L behind the eye
    assert abs((pb[0] + pb[2]) / 2 - (500 - 0.3 * ppl + (K['axis'] + K['back']) * ppl)) <= 1
    assert len(D['expressions']) == 1 and len(D['skipped']) == 1
    M = sheetqa.manifest_figures(D)
    assert set(M['heads']) == {'front', 'three_quarter', 'profile'} and M['facing'] == -1
    assert sheetqa.verify_figures(D, M)['front']['ok']


def test_detect_figures_on_the_sheet():
    """the real acceptance check: Clawd's model sheet, scaled by its rig, against the manifest's hand-typed head boxes."""
    import json
    path = os.path.join(ROOT, 'projects/hello-world/refs/idol_D.png')
    rig = os.path.join(ROOT, 'projects/tsuzuku/rig/clawd')
    man = os.path.join(ROOT, 'charkit/refs/clawd/manifest.json')
    if not all(os.path.exists(p) for p in (path, rig, man)):
        print('  (skipped: the sheet, rig or manifest is missing)'); return
    from PIL import Image
    from charkit import refs
    rgb = np.asarray(Image.open(path).convert('RGB')).astype(float) / 255
    alpha = np.asarray(Image.open(os.path.join(rig, 'base.png')).convert('RGBA'))[..., 3] / 255.0
    figs = json.load(open(man))['references']['sheet']['figures']
    ppl = sheetqa.sheet_ppl(rgb, figs['front_figure'], alpha, refs.measure(rig)['ppl'])
    D = sheetqa.detect_figures(rgb, ppl=ppl)
    assert set(D['figures']) == {'front', 'three_quarter', 'profile', 'back'}
    assert D['figures']['three_quarter']['partial'] and not D['figures']['front']['partial']
    assert len(D['expressions']) == 4 and len(D['skipped']) == 2                     # four heads; two hand studies
    V = sheetqa.verify_figures(D, figs, tol=5)
    assert all(r['ok'] for r in V.values()), V


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
