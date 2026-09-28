"""charkit.exprqa on drawn faces with known answers (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import exprqa

C = exprqa.CLASS
PPL = 100.0
WIN = exprqa.WIN


def grid(ppl=PPL):
    H = int(round((WIN['top'] - WIN['bottom']) * ppl)); W = int(round(2 * WIN['x'] * ppl))
    return np.meshgrid((np.arange(W) + 0.5) / ppl - WIN['x'], WIN['top'] - (np.arange(H) + 0.5) / ppl)


def face(eyes='open', arc=0.03, mouth='closed', lift=0.02, brow_tilt=20.0, iris=0.10):
    """a face's class image on the window (x, z in L from the eyes' midpoint): skin; eyes 0.168 L out (open: a white
    opening 0.19 x 0.12 L round an iris `iris` L wide; closed: a lid line arching `arc` L, + up); a mouth 0.2 L wide at
    -0.28 L (closed: a line whose corners sit `lift` L above its middle; open: a D 0.1 L deep, lined, red inside); brows
    0.14 L above the eyes, 0.13 L long, their inner ends `brow_tilt` degrees low."""
    U, Z = grid()
    cls = np.full(U.shape, C['skin'])
    t = 1.5 / PPL
    for s in (-1, 1):
        x = U - s * 0.168
        if eyes == 'open':
            op = (x / 0.095) ** 2 + (Z / 0.06) ** 2 <= 1
            cls[op] = C['white']
            cls[op & ((x / (iris / 2)) ** 2 + (Z / 0.06) ** 2 <= 1)] = C['iris']
        else:
            zl = arc * (1 - (x / 0.09) ** 2)
            cls[(np.abs(x) <= 0.09) & (np.abs(Z - zl) <= t)] = C['line']
        # the brow: a tilted stroke, its inner end (toward the midline) low
        xb = U - s * 0.168
        zb = 0.14 + np.tan(np.radians(brow_tilt)) * (s * xb)
        cls[(np.abs(xb) <= 0.065) & (np.abs(Z - zb) <= t)] = C['line']
    if mouth == 'closed':
        zm = -0.28 + lift * (U / 0.1) ** 2
        cls[(np.abs(U) <= 0.1) & (np.abs(Z - zm) <= t)] = C['line']
    else:
        d = (np.abs(U) <= 0.1) & (Z <= -0.25) & ((U / 0.1) ** 2 + ((Z + 0.25) / 0.1) ** 2 <= 1)
        ring = (np.abs(U) <= 0.1 + t) & (Z <= -0.25 + t) & ((U / (0.1 + t)) ** 2 + ((Z + 0.25) / (0.1 + t)) ** 2 <= 1) & ~d
        cls[ring | (d & (Z > -0.25 - t))] = C['line']
        cls[d & (Z <= -0.25 - t)] = C['mouth']
    return cls


def at(cls):
    return exprqa.measure(cls, PPL, WIN['top'] * PPL, WIN['x'] * PPL)


def test_eyes_open_closed_and_the_arc():
    M = at(face('open'))
    assert all(e['open'] for e in M['eyes'])
    assert abs(M['eyes'][0]['iris_ratio'] - 0.10 / 0.19) < 0.08, M['eyes'][0]
    arch, sag = at(face('closed', arc=0.03)), at(face('closed', arc=-0.03))
    assert all(e['open'] is False for e in arch['eyes'] + sag['eyes'])
    assert all(e['arc'] > 0.05 for e in arch['eyes']) and all(e['arc'] < -0.05 for e in sag['eyes'])


def test_mouth_width_open_and_lift():
    M = at(face(mouth='closed', lift=0.02))['mouth']
    assert M['found'] and abs(M['width'] - 0.2) < 0.03 and M['open'] == 0 and M['lift'] > 0.02, M
    F = at(face(mouth='closed', lift=-0.02))['mouth']
    assert F['lift'] < -0.02
    O = at(face(mouth='open'))['mouth']
    assert abs(O['open'] - 0.1) < 0.025 and O['area'] > 0.008 and O['lift'] > 0.1, O     # a D: corners at its top


def test_brow_tilt():
    M = at(face(brow_tilt=20.0))
    b = [x for x in M['brows'] if x]
    assert b and all(abs(x['tilt'] - 20.0) < 5 for x in b), M['brows']
    M = at(face(brow_tilt=-15.0))
    assert all(x['tilt'] < -8 for x in M['brows'] if x)


def test_match_picks_the_closest_and_flags_what_is_missing():
    d = exprqa.summary(at(face('closed', arc=0.03, mouth='open')))
    lib = {'eye': {'happy': exprqa.summary(at(face('closed', arc=0.03))), 'blink': exprqa.summary(at(face('closed', arc=-0.03))),
                   'neutral': exprqa.summary(at(face('open')))},
           'mouth': {'neutral': exprqa.summary(at(face(mouth='closed'))), 'laugh': exprqa.summary(at(face(mouth='open')))}}
    m = exprqa.match(d, lib)
    assert m['eye'][0] == 'happy' and m['mouth'][0] == 'laugh' and m['mouth'][1] < 0.2
    del lib['mouth']['laugh']
    m = exprqa.match(d, lib)
    assert m['mouth'][1] > exprqa.MISSING                  # nothing in the library is close: add it to the template


def test_render_applies_a_key():
    """ours: a skin quad and a line triangle whose key moves it up 0.2 L; the class image shows it moved."""
    L = 1.0
    V = np.array([[-0.6, 0, -0.7], [0.6, 0, -0.7], [0.6, 0, 0.4], [-0.6, 0, 0.4]], float)
    skin = ('skin', V, np.array([[0, 1, 2], [0, 2, 3]]), np.array([C['skin'], C['skin']]), {})
    Vl = np.array([[-0.1, -0.01, -0.3], [0.1, -0.01, -0.3], [0.0, -0.01, -0.25]], float)
    line = ('mouth_line', Vl, np.array([[0, 1, 2]]), np.array([C['line']]), {'mouth_up': (np.arange(3), np.tile([0, 0, 0.2], (3, 1)))})
    data = dict(parts=[skin, line], eye_z=0.0, L=L)
    assert exprqa.library(data)['mouth'] == ['neutral', 'up']
    a, b = exprqa.render(data, {}, PPL), exprqa.render(data, {'mouth': 'up'}, PPL)
    ra, rb = (np.nonzero((x == C['line']).any(1))[0].mean() for x in (a, b))
    assert abs((ra - rb) / PPL - 0.2) < 0.02


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
