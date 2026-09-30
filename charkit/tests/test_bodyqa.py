"""charkit.bodyqa on a drawn figure with known answers (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import bodyqa

C = bodyqa.CLASS
PAPER, LINE = (0.97, 0.97, 0.93), (0.12, 0.08, 0.07)
ORANGE, CREAM, CREAM_SHADE, SKIN, DARK, WHITE = ((0.83, 0.47, 0.32), (0.96, 0.9, 0.75), (0.78, 0.63, 0.48),
                                                 (0.98, 0.85, 0.75), (0.28, 0.22, 0.19), (0.95, 0.95, 0.95))
PPL = 40.0
WIN = bodyqa.WIN


def grid(ppl=PPL):
    H = int(round((WIN['top'] - WIN['bottom']) * ppl)); W = int(round(2 * WIN['x'] * ppl))
    z = WIN['top'] - (np.arange(H) + 0.5) / ppl
    u = (np.arange(W) + 0.5) / ppl - WIN['x']
    return np.meshgrid(u, z)


def figure(skirt=1.2, hem=-3.0, feet=-5.2, boot=-4.0, hair_w=0.8, ppl=PPL):
    """a front figure drawn on the shared grid, outlined: an orange hair mass round the head (to 0.5 L under the eyes), a
    skin face, an orange bodice, a flared orange skirt (half-width `skirt` L at the hem `hem`) with a cream panel (its
    shadow in skin's hue), dark shorts, skin legs, white boots from `boot` down to the feet. -> (rgb, fg)."""
    U, Z = grid(ppl)
    im = np.ones(U.shape + (3,)) * PAPER
    fg = np.zeros(U.shape, bool)

    def put(m, col):
        im[m] = col; fg[m] = True
    put((np.abs(U) <= hair_w) & (Z <= 0.9) & (Z >= -0.5), ORANGE)                        # hair
    put(((U / 0.34) ** 2 + ((Z + 0.1) / 0.4) ** 2) <= 1, SKIN)                          # face
    put((np.abs(U) <= 0.1) & (Z < -0.5) & (Z >= -0.8), SKIN)                          # neck
    put((np.abs(U) <= 0.45) & (Z < -0.8) & (Z >= -1.5), ORANGE)                       # bodice
    t = np.clip((-1.5 - Z) / (-1.5 - hem), 0, 1)
    sk = (np.abs(U) <= 0.35 + (skirt - 0.35) * t) & (Z < -1.5) & (Z >= hem)
    put(sk, ORANGE)
    put(sk & (np.abs(U) <= 0.15), CREAM)
    put((np.abs(U) <= 0.3) & (Z < hem) & (Z >= hem - 0.2), DARK)                      # shorts
    legs = (np.abs(np.abs(U) - 0.17) <= 0.12) & (Z < hem - 0.2) & (Z >= feet)
    put(legs & (Z >= boot), SKIN)
    put(legs & (Z < boot), WHITE)
    # outlines round every region (thin: 1 px) and between hair and bodice
    edge = np.zeros_like(fg)
    for a in (im[..., 0], im[..., 1]):
        edge |= np.abs(np.diff(a, axis=0, prepend=a[:1])) > 0.05
        edge |= np.abs(np.diff(a, axis=1, prepend=a[:, :1])) > 0.05
    edge &= fg | bodyqa.dilate(fg, 1)
    im[edge] = LINE; fg |= edge
    im[sk & (np.abs(U) <= 0.12) & (Z < -1.6) & (Z > -1.75)] = CREAM_SHADE       # a fold's shadow in skin's hue, no line
    return im, fg


def test_classes_split_hair_from_the_dress_and_cream_from_skin():
    im, fg = figure()
    cls, raw = bodyqa.classes(im, fg, WIN['top'] * PPL, PPL)
    U, Z = grid()
    at = lambda u, z: cls[int(np.argmin(np.abs(Z[:, 0] - z))), int(np.argmin(np.abs(U[0] - u)))]
    assert at(0.6, 0.3) == C['hair']                    # orange above the shoulders
    assert at(0.3, -1.1) == C['orange']                  # orange below them: the bodice
    assert at(0.0, -1.68) == C['cream']                  # the panel's shadow votes with its panel, not skin
    assert at(0.0, -0.1) == C['skin'] and at(0.0, -3.1) == C['dark'] and at(0.17, -4.5) == C['white']
    assert (raw == C['line']).sum() > 0 and (cls == C['line']).sum() < 0.1 * (raw == C['line']).sum()


def test_measures_known_extents():
    im, fg = figure()
    cls, _ = bodyqa.classes(im, fg, WIN['top'] * PPL, PPL)
    M = bodyqa.measure(cls, fg, PPL, 'front')
    tol = 2.5 / PPL
    assert abs(M['feet'] - (-5.2)) < tol, M['feet']
    assert abs(M['skirt']['hem'] - (-3.0)) < tol, M['skirt']
    assert abs(M['skirt']['width'] - 2.4) < 3 * tol, M['skirt']
    assert abs(M['hair']['width'] - 1.6) < 3 * tol and abs(M['hair']['bottom'] - (-0.5)) < tol, M['hair']
    assert abs(M['boot_top'] - (-4.0)) < tol and abs(M['leg'] - (-3.2 + 5.2)) < 2 * tol, (M.get('leg_top'), M.get('boot_top'))


def test_compare_grades_a_shorter_skirt_and_passes_itself():
    d_im, d_fg = figure()
    o_im, o_fg = figure(skirt=0.8, hem=-2.6)
    dcls, _ = bodyqa.classes(d_im, d_fg, WIN['top'] * PPL, PPL)
    ocls, _ = bodyqa.classes(o_im, o_fg, WIN['top'] * PPL, PPL)
    D, O = bodyqa.measure(dcls, d_fg, PPL, 'front'), bodyqa.measure(ocls, o_fg, PPL, 'front')
    C_ = bodyqa.compare(O, D, ocls, dcls, o_fg, d_fg, 'front')
    assert C_['skirt_width']['status'] == 'FAIL' and C_['hem']['status'] == 'FAIL' and C_['hem']['value'] > 0.3
    same = bodyqa.compare(D, D, dcls, dcls, d_fg, d_fg, 'front')
    graded = [v['status'] for v in same.values() if v['status'] not in ('INFO', 'SKIPPED')]
    assert graded and all(s == 'PASS' for s in graded), same


def test_evaluate_takes_a_zbuffer_label_image():
    """the body fitter's path: a label image (faceqa.zbuffer's: -1 where nothing is) against design_views-style data."""
    im, fg = figure()
    cls, raw = bodyqa.classes(im, fg, WIN['top'] * PPL, PPL)
    design = {'front': dict(cls=cls, raw=raw, fg=fg, rgb=im, ppl=PPL, eye=(0, 0), win=dict(WIN), cut=None)}
    label = np.where(fg, cls, -1)
    table, C_, views = bodyqa.evaluate({'front': (np.zeros(label.shape), label)}, design)
    assert C_['front_iou']['value'] > 0.99 and C_['front_skirt_width']['status'] == 'PASS'
    assert views and views[0][0] == 'front' and 'skirt' in table['views']['front']['ours']


def test_skirt_width_with_no_row_free_in_both_compares_one_row():
    """no row is free of hands in both figures: the design's widest free row, and ours on that same row (each figure's
    own widest over the design's free rows sat at different heights: ours' top row against the design's bottom one)."""
    im, fg = figure()
    cls, _ = bodyqa.classes(im, fg, WIN['top'] * PPL, PPL)
    D = bodyqa.measure(cls, fg, PPL, 'front')
    D['ppl'] = PPL
    O = dict(D)
    # the design's free rows 10..14, widening downward (0.70 .. 0.88); ours blocked on every row, narrower at the top and
    # wider below: ours' widest over those rows (0.92 at row 10) would sit against the design's at row 14
    D['skirt'] = dict(D['skirt'], _rows={r: (0.70 + 0.045 * (r - 10), False) for r in range(10, 15)})
    D['skirt']['_rows'].update({r: (1.0, True) for r in range(15, 20)})
    O['skirt'] = dict(O['skirt'], _rows={r: (0.92 - 0.01 * (r - 10), True) for r in range(10, 20)})
    C_ = bodyqa.compare(O, D, cls, cls, fg, fg, 'front')
    sw = C_['skirt_width']
    assert sw['design'] == 0.88 and sw['ours'] == 0.88 and sw['value'] == 1.0, sw
    assert abs(sw['z'] - (WIN['top'] - 14.5 / PPL)) < 1e-3, sw


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
