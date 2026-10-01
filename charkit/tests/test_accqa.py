"""charkit.accqa (the hair clips' QA and the reclass: the clips their own class on both sides) on synthetic fixtures
with known answers (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import accqa


def _canvas():
    rgb = np.full((200, 300, 3), 0.8)                                       # grey paper
    rgb[20:180, 20:280] = (0.84, 0.48, 0.33)                                # hair, lit
    rgb[110:180, 20:280] = (0.66, 0.33, 0.22)                               # and in shade
    yy, xx = np.mgrid[0:200, 0:300]
    rgb[(yy - 60) ** 2 + (xx - 200) ** 2 < 15 ** 2] = (0.98, 0.86, 0.47)    # a yellow disc: the star
    rgb[(yy - 60) ** 2 + (xx - 150) ** 2 < 10 ** 2] = (0.83, 0.38, 0.26)    # a red disc: the crab
    return rgb


def test_design_clips_by_colour():
    pieces = {'pin_star': dict(srgb=np.array([0.988, 0.875, 0.451])), 'pin_crab': dict(srgb=np.array([0.886, 0.376, 0.267]))}
    win = dict(x=1.5, top=1.0, bottom=-1.0)                                 # 300 x 200 at 100 px/L round (150, 100)
    m, info = accqa.design_clips(_canvas(), 100.0, pieces, (), win)
    star, crab = m['pin_star'], m['pin_crab']
    assert abs(star.sum() - np.pi * 15 ** 2) < 60 and abs(crab.sum() - np.pi * 10 ** 2) < 40
    M = accqa.measure(star, 100.0, win)
    assert abs(M['u'] - 0.5) < 0.01 and abs(M['z'] - 0.4) < 0.01          # (200, 60) px from (150, 100)


def test_shape_iou_ignores_place_and_scale():
    a = np.zeros((100, 100), bool); a[20:40, 30:70] = True
    b = np.zeros((300, 300), bool); b[100:160, 50:170] = True               # 3x, moved
    assert accqa.shape_iou(a, b) > 0.93                                     # (resampling a 20 px edge)
    c = np.zeros((300, 300), bool); c[50:170, 100:160] = True               # turned 90 degrees
    assert accqa.shape_iou(a, c) < 0.5


def test_measure_angle_and_triangulate():
    m = np.zeros((200, 200), bool)
    yy, xx = np.mgrid[0:200, 0:200]
    m[np.abs((xx - 100) - 0.3 * (100 - yy)) < 5] = True                     # a bar leaning right at the top
    m[:40] = m[160:] = False
    ang = accqa.measure(m, 100.0, dict(x=1.0, top=1.0, bottom=-1.0))['angle']
    assert abs(ang - np.degrees(np.arctan(0.3))) < 1.0
    P = np.array([0.3, 0.2, 0.4]); a = 36.0
    M = {'front': dict(px=1, u=P[0], z=P[2]), 'profile': dict(px=1, u=P[1], z=P[2]),
         'three_quarter': dict(px=1, u=P[0] * np.cos(np.radians(a)) + P[1] * np.sin(np.radians(a)), z=P[2])}
    xyz, res = accqa.triangulate(M, a)
    assert np.allclose(xyz, P) and res < 1e-9


def test_window_to_grid_and_reclass():
    from charkit.bodyqa import WIN as BW
    ppl, eye = 20.0, (100.3, 80.6)
    m = np.zeros((int(round((accqa.WIN['top'] - accqa.WIN['bottom']) * ppl)), int(round(2 * accqa.WIN['x'] * ppl))), bool)
    m[5, 7] = True
    g = accqa.window_to_grid(m, eye, ppl)
    # the same sheet pixel: crop()'s origin in each window
    sheet_px = (7 + int(round(eye[0] - accqa.WIN['x'] * ppl)), 5 + int(round(eye[1] - accqa.WIN['top'] * ppl)))
    r, c = np.argwhere(g)[0]
    assert (c + int(round(eye[0] - BW['x'] * ppl)), r + int(round(eye[1] - BW['top'] * ppl))) == sheet_px
    dv = {'front': dict(cls=np.full(g.shape, 2), raw=np.full(g.shape, 2), fg=np.ones(g.shape, bool))}
    out = accqa.reclass(dv, {'front': {'pin_crab': g}})
    assert out['front']['cls'][r, c] == accqa.ACCESSORY and (out['front']['cls'] == 2).sum() == g.size - 1
    assert dv['front']['cls'][r, c] == 2                                    # the input untouched


def test_hair_tones_class_an_accessory_by_object():
    """the evaluator's clips are their own class (accqa.ACCESSORY), whatever their colour: the old rule classed one by
    its colour family, and a yellow star is the iris's (the palette's iris pooled the fitted star, round 3); one made of
    the hair's material (a bun built as an accessory) stays hair."""
    from charkit import bodyeval
    from charkit.bodyqa import CLASS as CL, family
    star = (0.98, 0.855, 0.49)                                               # the fitted star's #fada7d
    assert family(np.array(star)) == CL['iris']                              # what the old rule made of it
    parts = []
    for name, a in (('star_0', dict(kind='star', color=star)), ('crab_1', dict(kind='crab', color=(0.82, 0.4, 0.27))),
                    ('bun_2', dict(kind='bun', material='hair'))):
        p = bodyeval.Part(name, 'accessories', np.zeros((3, 3)), [(0, 1, 2)] * 4)
        p.spec = a
        parts.append(p)
    bodyeval.hair_tones(parts, {})
    assert (parts[0].cls == accqa.ACCESSORY).all() and (parts[1].cls == accqa.ACCESSORY).all()
    assert (parts[2].cls == CL['hair']).all()


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
