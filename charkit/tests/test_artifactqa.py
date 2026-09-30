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
    recs = A._records(json.load(open(p)))
    assert recs
    for D in recs:
        assert D['stamp'] and set(D['inputs']) >= {'face_sheet', 'body_sheet', 'masks', 'pieces', 'eye_x', 'code'}
        assert set(D['head']) >= {'front', 'three_quarter', 'profile'}
        assert all(set(v) >= {'hair', 'face', 'neck'} for k, v in D['head'].items() if k != 'back')
        assert set(D['body']) >= {'front', 'three_quarter', 'profile', 'back'}
        assert all(r in D['body']['front'] for r in A.BODY_REGIONS)
        assert all(set(D['body']['front'][r]) >= {'spikes', 'points', 'bumps'} for r in ('boots', 'sleeves', 'legs'))
        assert 'mirror' in D['body']['front']['waist'] and 'band' in D['body']['front']['lower']


# ---------------------------------------------------------------------------------- silhouettes (Michael's flags)
def _kinds(**masks):
    return {k: m for k, m in masks.items()}


def test_a_horn_on_the_silhouette_is_a_spike_a_disc_has_none():
    horn = (np.abs(XX - 200) < 4) & (YY > 40) & (YY < 90)             # 8 px wide, 30 px out of the disc's top
    fig = DISC | horn
    assert A.figure_spikes(DISC, _kinds(skirt=DISC), PPL) == []
    sp = A.figure_spikes(fig, _kinds(skirt=DISC, boots=horn), PPL)
    assert len(sp) == 1 and sp[0][0] == 'boots' and sp[0][1] >= A.SPIKE_H, sp


def test_a_square_has_cap_points_a_disc_none():
    sq = (np.abs(YY - 200) < 100) & (np.abs(XX - 200) < 100)
    caps = [x for x in A.figure_points(sq, _kinds(top=sq), PPL) if x[0] == 'cap']
    assert len(caps) == 4 and all(x[2] > 70 for x in caps), caps
    assert not [x for x in A.figure_points(DISC, _kinds(top=DISC), PPL) if x[0] == 'cap']


def test_a_knob_on_a_region_of_its_own_is_a_bump():
    knob = np.hypot(YY - 200, XX - 330) < 25                         # a round knob on the disc's side
    fig = DISC | knob
    out = [x for x in A.figure_points(fig, _kinds(skin=fig), PPL) if x[0] == 'bump' and x[2] > 0]
    assert out and max(x[2] for x in out) > 30, out
    assert not [x for x in A.figure_points(DISC, _kinds(skin=DISC), PPL) if x[0] == 'bump' and x[2] > 20]   # (its curve)
    # the knob as a piece of its own: its tip is that piece's bump; the junctions' pinches are corners by design
    pts = [x for x in A.figure_points(fig, _kinds(skin=DISC, boots=knob & ~DISC), PPL) if x[0] == 'bump']
    assert [x[1] for x in pts if x[2] > 30] == ['boots'], pts
    assert not [x for x in pts if x[2] < -30], pts
    assert [x for x in A.figure_points(fig, _kinds(skin=fig), PPL) if x[0] == 'bump' and x[2] < -30]   # (one piece)


def test_mirror_reads_a_one_sided_bulge():
    ax = A.mirror_axis(DISC, PPL)
    assert abs(ax - 200) <= 0.5 and A.mirror(DISC, ax, PPL)['asym'] < 0.01
    bulge = DISC | ((np.abs(YY - 200) < 40) & (XX > 200) & (XX < 345))
    assert A.mirror(bulge, A.mirror_axis(DISC, PPL), PPL)['asym'] > 0.05


def test_a_band_in_pixel_stairs_has_more_kinks_than_one_in_clean_steps():
    orange, dark = np.array([0.84, 0.47, 0.33]), np.array([0.29, 0.23, 0.21])
    region = (YY > 50) & (YY < 350) & (XX > 50) & (XX < 350)
    def band(edge):                                                  # the dark band under the edge row per column
        rgb = np.where((YY >= edge[None, :])[..., None], dark, orange)
        return A.band_edge(rgb, region, PPL)
    cols = np.arange(W)
    clean = 250 - 20 * ((cols - 50) // 75)                         # four clean steps, 20 px each
    stairs = clean + 3 * ((cols // 3) % 2)                           # the same with 3 px teeth all along
    a, b = band(clean), band(stairs)
    assert a and b and b['kinks'] > 3 * max(a['kinks'], 1.0), (a, b)


def test_shape_checks_grade_ours_beyond_the_design():
    rec = lambda h, t: {'boots': {'spikes': {'height': h}, 'points': {'turn': t}}}
    ours = {'body': {'front': rec(0.06, 90.0), 'profile': rec(0.0, 40.0)}}
    design = {'body': {'front': rec(0.0, 50.0), 'profile': rec(0.0, 0.0)}}
    C = A.shape_checks(ours, design)
    assert C['spikes_boots']['value'] == 0.06 and C['spikes_boots']['grade'] == 'FAIL'
    # the design's cap floored at CAP_MIN: the profile's 40 is 15 beyond; the front's 90 is 40 beyond 50
    assert C['points_boots']['excess'] == {'front': 40.0, 'profile': 15.0} and C['points_boots']['worst'] == 'front'


def test_the_design_stamp_reads_only_the_graphs_piece_types(tmp_path):
    g = {'pieces': [{'id': 'collar', 'type': 'collar', 'extent': [1, 2]}, {'id': 'bow', 'type': 'bow'}],
         'springs': [{'length': 1.6}], 'comparison': {'matched': []}}
    a, b = tmp_path / 'a.json', tmp_path / 'b.json'
    a.write_text(json.dumps(g))
    g2 = dict(g, springs=[{'length': 2.1}], comparison={'matched': [1]})       # (what differs between copies and specs)
    g2['pieces'] = [dict(g['pieces'][1]), dict(g['pieces'][0], extent=[3, 4])]
    b.write_text(json.dumps(g2))
    assert A._piece_types(str(a)) == A._piece_types(str(b))
    g2['pieces'][0]['type'] = 'top'
    b.write_text(json.dumps(g2))
    assert A._piece_types(str(a)) != A._piece_types(str(b))


def test_the_design_code_covers_its_detectors_constants_not_the_grades(monkeypatch):
    c = A.design_code()
    monkeypatch.setattr(A, 'PEEKS', (1, 2))                                   # a grade's limit: not the design's
    monkeypatch.setattr(A, 'SHAPE_CHECKS', {})
    assert A.design_code() == c
    monkeypatch.setattr(A, 'SPIKE_R', A.SPIKE_R * 2)                          # a detector's constant: the design's
    assert A.design_code() != c


def test_a_stale_design_is_measured_once_per_machine(tmp_path, monkeypatch):
    monkeypatch.setenv('CHARKIT_PRODUCED_CACHE', str(tmp_path))
    made = []
    make = lambda: made.append(1) or {'head': {'front': {}}, 'body': {}, 'chin': 0.35}
    inp = {'eye_x': 0.168}
    D, hit = A._shared_design('abc', inp, make)
    assert not hit and made == [1] and D['chin'] == 0.35
    D, hit = A._shared_design('abc', {'eye_x': 0.169}, make)                  # within EYE_X_TOL: the same sheets
    assert hit and made == [1] and D['chin'] == 0.35 and D['stamp'] == 'abc'
    A._shared_design('abd', inp, make)                                         # another stamp: made
    assert made == [1, 1]
    monkeypatch.setenv('CHARKIT_PRODUCED_CACHE', 'off')
    A._shared_design('abc', inp, make)
    assert made == [1, 1, 1]


def test_calibrated_checks_warn_until_promoted_the_rest_stay_info():
    C = {'outline_neck': {'value': 7.9, 'grade': 'FAIL', 'status': 'INFO'},
         'bumps_legs': {'value': 0.0, 'grade': 'PASS', 'status': 'INFO'},
         'outline_top': {'value': 3.6, 'grade': 'FAIL', 'status': 'INFO'}}
    A.promote(C)
    assert C['outline_neck']['status'] == 'WARN' and C['outline_neck']['flag']
    assert C['bumps_legs']['status'] == 'PASS'
    assert C['outline_top']['status'] == 'INFO'
    # promoted (tool/look4): the grade is the status, a FAIL fails; the sleeves' and the band's wait at WARN
    assert set(A.PROMOTED) == {'spikes_boots', 'bumps_boots', 'bumps_legs', 'mirror_waist'} <= set(A.CALIBRATED)
    P = A.promote({'spikes_boots': {'value': 0.063, 'grade': 'FAIL'}, 'mirror_waist': {'value': 1.8, 'grade': 'WARN'},
                   'bumps_sleeves': {'value': 45.6, 'grade': 'FAIL'}, 'band_lower': {'value': 2.2, 'grade': 'FAIL'}})
    assert [P[k]['status'] for k in ('spikes_boots', 'mirror_waist', 'bumps_sleeves', 'band_lower')] == \
        ['FAIL', 'WARN', 'WARN', 'WARN']
    assert set(A.CALIBRATED) <= {'%s_%s' % (d, r) for d in list(A.DETECTORS) + ['peeks'] for r in A.REGIONS} | \
        {'%s_%s' % (k, r) for k, v in A.SHAPE_CHECKS.items() for r in v[5]}


def test_the_part_is_registered_after_the_look():
    from charkit import registry
    P = {p.name: p for p in registry.parts()}
    assert P['artifacts'].fn is A.measure and P['artifacts'].prefix == 'art_' and P['artifacts'].order > P['look'].order


if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main([__file__, '-q']))
