"""charkit.paletteqa with known answers: CIEDE2000 on Sharma, Wu and Dalal's test pairs, tones split from a two-tone class
(venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import paletteqa

SHARMA = [  # (Lab 1, Lab 2, dE00) from the paper's table
    ((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485), 2.0425),
    ((50.0, 3.1571, -77.2803), (50.0, 0.0, -82.7485), 2.8615),
    ((50.0, 2.5, 0.0), (50.0, 0.0, -2.5), 4.3065),
    ((50.0, 2.5, 0.0), (73.0, 25.0, -18.0), 27.1492),
    ((60.2574, -34.0099, 36.2677), (60.4626, -34.1751, 39.4387), 1.2644),
    ((22.7233, 20.0904, -46.694), (23.0331, 14.973, -42.5619), 2.0373),
    ((90.8027, -2.0831, 1.441), (91.1528, -1.6435, 0.0447), 1.4441),
]


def test_ciede2000_matches_the_reference_pairs():
    for a, b, want in SHARMA:
        assert abs(paletteqa.ciede2000(a, b) - want) < 1e-3, (a, b, paletteqa.ciede2000(a, b), want)
        assert abs(paletteqa.ciede2000(b, a) - want) < 1e-3


def test_lab_of_white_and_black():
    assert np.allclose(paletteqa.srgb_to_lab([1, 1, 1]), (100, 0, 0), atol=0.01)
    assert np.allclose(paletteqa.srgb_to_lab([0, 0, 0]), (0, 0, 0), atol=0.01)


def test_tones_split_lit_and_shade():
    rng = np.random.default_rng(1)
    lit, shade = np.array([0.98, 0.85, 0.75]), np.array([0.82, 0.66, 0.59])
    px = np.concatenate([lit + rng.normal(0, 0.01, (700, 3)), shade + rng.normal(0, 0.01, (300, 3))])
    T = paletteqa.tones(px)
    assert np.abs(T['lit'] - lit).max() < 0.02 and np.abs(T['shade'] - shade).max() < 0.02
    assert abs(T['shade_share'] - 0.3) < 0.03
    one = paletteqa.tones(lit + rng.normal(0, 0.01, (500, 3)))
    assert one['shade'] is None and np.abs(one['lit'] - lit).max() < 0.02


def test_compare_grades_a_paler_skin():
    D = {'skin': {'lit': np.array([0.98, 0.84, 0.75]), 'shade': np.array([0.82, 0.66, 0.59]), 'px': 1000}}
    same = paletteqa.compare({'skin': {'lit': D['skin']['lit'], 'shade': D['skin']['shade']}}, D)
    assert same['skin_lit']['status'] == 'PASS' and same['skin_lit']['value'] < 0.01
    pale = paletteqa.compare({'skin': {'lit': np.array([1.0, 0.93, 0.89]), 'shade': np.array([0.97, 0.8, 0.76])}}, D)
    assert pale['skin_lit']['dL'] > 3 and pale['skin_lit']['dC'] < -5 and pale['skin_lit']['status'] != 'PASS'
    assert pale['skin_shade']['status'] != 'PASS' and pale['skin_shade']['dL'] > 10


def test_ours_weights_by_area():
    cols = {1: [((1.0, 0.9, 0.8), (0.9, 0.7, 0.6), 3.0), ((0.5, 0.5, 0.5), (0.4, 0.4, 0.4), 1.0)]}
    O = paletteqa.ours(cols)
    assert np.allclose(O['skin']['lit'], (1.0, 0.9, 0.8)) and O['skin']['area'] == 4.0


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
