"""charkit.artifactqa's detectors on synthetic masks with known answers: a clean disc scores low; a toothed disc, a
faceted terminator, a fragmented mask and a dotted line score high (venv: run this file, or pytest)."""
import json, os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import artifactqa as A

PPL = 400
H = W = 400
YY, XX = np.mgrid[0:H, 0:W]
R = np.hypot(YY - 200, XX - 200)
TH = np.arctan2(YY - 200, XX - 200)
DISC = R < 120


def test_clean_disc_has_no_corners_or_fragments():
    o = A.outline(DISC, PPL)
    assert o['corners'] == 0 and o['kinks'] == 0, o
    assert o['rms'] < 0.001, o
    assert abs(o['len'] - 2 * np.pi * 120 / PPL) < 0.02, o
    f = A.fragments(DISC, PPL)
    assert f['n'] == 0 and f['slivers'] == 0, f


def test_toothed_disc_scores_high():
    teeth = R < 120 + 5 * np.sign(np.sin(TH * 40))              # 40 square teeth, 10 px deep, ~19 px wide
    o = A.outline(teeth, PPL)
    assert o['corners'] > 20, o                                  # the clean disc's is 0
    assert o['rms'] > 3 * A.outline(DISC, PPL)['rms']


def test_a_square_counts_its_four_corners():
    sq = (np.abs(YY - 200) < 100) & (np.abs(XX - 200) < 100)
    o = A.outline(sq, PPL)
    assert o['n_corners'] == 4, o


def test_faceted_terminator_has_kinks_a_smooth_one_none():
    smooth = np.where(YY > 200 + 15 * np.sin(XX / 40.0), 1, 0).astype(np.int8)    # a gentle wave across the disc
    t0 = A.terminator(DISC, smooth, PPL)
    assert t0['kinks'] == 0, t0
    zig = 200 + 6 * (2 * np.abs(((XX / 10.0) % 2) - 1) - 1)      # a zigzag: 45-degree facets every 10 px (0.025 L)
    faceted = np.where(YY > zig, 1, 0).astype(np.int8)
    t1 = A.terminator(DISC, faceted, PPL)
    assert t1['kinks'] > 10 * max(t0['kinks'], 1), t1
    assert 0.45 < t1['shade'] < 0.55


def test_tone_islands_counted_inside_away_from_the_edge():
    tone = np.zeros((H, W), np.int8)
    for k in range(6):                                           # six 4x4 shade patches inside the lit disc
        tone[150:154, 120 + 25 * k:124 + 25 * k] = 1
    tone[200:204, 79:83] = 1                                     # one on the outline: the outline's, not an island
    t = A.terminator(DISC, tone, PPL)
    assert t['n_islands'] == 6, t


def test_fragments_and_slivers():
    m = DISC.copy()
    for k in range(8):                                           # eight loose bits off the edge
        m[40 + 40 * k:44 + 40 * k, 340:346] = True
    f = A.fragments(m, PPL)
    assert f['n'] == 8 and f['slivers'] == 0, f
    s = DISC.copy()
    s[195:198, 318:380] = True                                   # a 3 px strip (0.0075 L) sticking out
    f2 = A.fragments(s, PPL)
    assert f2['n'] == 0 and f2['slivers'] == 1 and f2['sliver_area'] > 0, f2


def test_a_dotted_line_in_the_skin_is_speckle():
    tone = np.zeros((H, W), np.int8)
    dotted = tone.copy()
    for k in range(12):                                          # a row of 2x2 shade dots: the neck seam's
        dotted[250:252, 120 + 14 * k:122 + 14 * k] = 1
    assert A.speckle(DISC, tone, PPL)['n'] == 0
    s = A.speckle(DISC, dotted, PPL)
    assert s['n'] == 12, s
    foreign = np.zeros((H, W), bool)
    foreign[180:182, 150:152] = True                             # another surface showing through, a speck of it
    skin = DISC & ~foreign
    assert A.speckle(skin, tone, PPL, foreign=foreign)['n'] == 1


def test_image_tone_splits_two_tones_and_ignores_lines():
    rgb = np.ones((H, W, 3)) * np.array([0.98, 0.86, 0.80])
    rgb[YY > 220] = (0.85, 0.66, 0.60)                           # the shade below row 220
    wall = np.zeros((H, W), bool)
    wall[100:103, 100:300] = True                                # a drawn line across the lit part
    rgb[wall] = (0.1, 0.05, 0.05)
    t = A.image_tone(rgb, DISC, wall)
    assert (t[DISC & (YY < 215) & ~wall] == 0).all() and (t[DISC & (YY > 225)] == 1).all()
    assert (t[wall & DISC] == 0).all()                           # the line takes the tone round it
    flat = A.image_tone(np.ones((H, W, 3)) * 0.9, DISC, np.zeros((H, W), bool))
    assert (flat[DISC] == 0).all()


def test_buffer_tone_cuts_at_the_steps_and_fills_lines():
    tone = np.where(YY < 150, 0.1, np.where(YY < 250, 1.1, 1.9))
    tone[DISC & (np.abs(XX - 200) < 2)] = np.nan                 # a line (an outline hull: no tone)
    t = A.buffer_tone(tone, DISC)
    assert set(np.unique(t[DISC])) == {0, 1, 2}
    assert (t[DISC & (YY < 140)] == 0).all() and (t[DISC & (YY > 260)] == 2).all()
    assert (t[DISC] >= 0).all()


def test_checks_grade_the_worst_view_against_a_floored_design():
    rec = lambda c: {'hair': {'outline': {'corners': c, 'len': 1.0}}}
    ours = {'head': {'front': rec(6.0), 'profile': rec(1.0)}}
    design = {'head': {'front': rec(2.0), 'profile': rec(0.1)}}   # the profile's 0.1 floored to 1.0
    C = A.checks(ours, design)
    c = C['outline_hair']
    assert c['ratio'] == {'front': 3.0, 'profile': 1.0} and c['value'] == 3.0 and c['worst'] == 'front'
    assert c['status'] == 'INFO' and c['grade'] == A.grade(3.0, 'outline') == 'FAIL'
    assert A.grade(1.0, 'outline') == 'PASS'


def test_the_stored_design_measures_are_whole():
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'refs', 'clawd', A.DESIGN_FILE)
    D = json.load(open(p))
    assert D['stamp'] and set(D['inputs']) >= {'face_sheet', 'body_sheet', 'graph', 'eye_x', 'code'}
    assert set(D['head']) >= {'front', 'three_quarter', 'profile'}
    assert all(set(v) >= {'hair', 'face', 'neck'} for k, v in D['head'].items() if k != 'back')
    assert set(D['body']) >= {'front', 'three_quarter', 'profile', 'back'}
    assert all(r in D['body']['front'] for r in A.BODY_REGIONS)


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f()
            print('ok', k)
