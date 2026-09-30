"""charkit.skirtqa's flap, band and back measures on masks with known answers, and its calibration: every check passes
on the design itself (when the outfit masks are produced) and fails on a known-bad version of it (venv: run this file,
or pytest)."""
import json, os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import skirtqa as sq

PPL = 200.0                          # px per L in these masks


def stair_edge(treads, rises, x0=10):
    """a band's top edge (a row per column): treads px wide, each rise px lower than the last."""
    cols, rows, r = [], [], 100
    c = x0
    for i, t in enumerate(treads):
        cols += list(range(c, c + t)); rows += [r] * t
        c += t
        if i < len(rises):
            r += rises[i]
    return np.array(cols), np.array(rows)


# ------------------------------------------------------------------------------------------------------------ the band
def test_clean_stair_counts_its_risers():
    c, r = stair_edge([20, 20, 20, 20], [16, 16, 16])            # 0.1 L treads, 0.08 L rises
    s = sq.steps_of(c, r, PPL)
    assert s['steps'] == 3 and all(abs(x - 0.08) < 1e-9 for x in s['risers']), s


def test_tilted_stair_still_counts():
    c, r = stair_edge([24, 24, 24], [20, 20])
    r = r + (0.3 * (c - c[0])).astype(int)                        # treads sloping 17 deg, as the drawn flaps' do
    assert sq.steps_of(c, r, PPL)['steps'] == 2


def test_pixel_stairs_and_curves_are_no_steps():
    c, r = stair_edge([3] * 30, [2] * 29)                          # fine pixel-stairs: 0.01 L risers, 0.015 L treads
    assert sq.steps_of(c, r, PPL)['steps'] == 0
    c = np.arange(200)
    r = (100 + 40 * ((c - 100) / 100.0) ** 2).astype(int)          # a hem's curve
    assert sq.steps_of(c, r, PPL)['steps'] == 0


def test_band_under_a_stepped_face():
    H, W = 200, 120
    face = np.zeros((H, W), bool); band = np.zeros((H, W), bool)
    for i, (c0, c1) in enumerate(((10, 40), (40, 70), (70, 100))):
        bottom = 80 + 20 * i
        face[20:bottom, c0:c1] = True
        band[bottom:bottom + 24, c0:c1] = True                      # 0.12 L thick under each tread
    b = sq.band(face, band & ~face, PPL)
    assert b['steps'] == 2 and b['rise'] == 0.1 and abs(b['height'] - 0.12) < 1e-9, b


# ------------------------------------------------------------------------------------------------------------ the flaps
def test_fill_between_lines_and_a_wall_bridging_a_gap():
    H, W = 300, 300
    rgb = np.full((H, W, 3), 0.8)
    rgb[:, 150] = 0.0                                              # a drawn line down the middle ...
    rgb[100:130, 150] = 0.8                                        # ... fading out for 30 px
    D = dict(rgb=rgb, fg=np.ones((H, W), bool))
    x, z = (60 + 0.5) / PPL - sq.WIN['x'], sq.WIN['top'] - (150 + 0.5) / PPL
    m = sq.face_fill(D, [(x, z)], PPL, close=1)
    assert m[:, 200:].any()                                        # leaks through the gap
    xw = (150.5) / PPL - sq.WIN['x']
    wall = [xw, sq.WIN['top'] - 95 / PPL, xw, sq.WIN['top'] - 135 / PPL]
    m = sq.face_fill(D, [(x, z)], PPL, close=1, walls_extra=[wall])
    assert m[:, :148].sum() > 0.9 * 148 * H and not m[:, 153:].any()


def test_shape_width_angle_and_gap():
    H, W = 400, 400
    a = np.zeros((H, W), bool)
    for r in range(100, 300):                                      # a wedge widening and leaning right going down
        c0 = 100 + (r - 100) // 4
        a[r, c0:c0 + 20 + (r - 100) // 5] = True
    s = sq.shape(a, PPL)
    assert s['angle'] > 10 and abs(s['width'][299] - (20 + 199 // 5) / PPL) < 1e-9
    g = sq.flap_gap(a, a[:, ::-1], PPL, 10, -10)                  # its mirror image: a gap narrowing going down
    assert len(g) == 200 and abs(g[100] - 160 / PPL) < 1e-9 and g[299] < g[100], (g[100], g[299])
    over = sq.flap_gap(a, np.roll(a, 10, axis=1), PPL, 10, -10)   # the same flap 10 px over: they overlap
    assert all(v < 0 for v in over.values())


# ------------------------------------------------------------------------------------------------------ calibration
def _design():
    """the design's views and the produced outfit masks, or None when they aren't produced here."""
    from charkit import bodyeval, bodymeasure
    spec = json.load(open(os.path.join(sq.ROOT, 'charkit', 'spec', 'clawd.json')))
    from charkit import manifest
    spec = manifest.resolve(spec)
    try:
        r = manifest.load(spec['ref']['manifest'])['references']['outfit_masks']
    except Exception:
        return None
    p = r['path'] if os.path.isabs(r['path']) else os.path.join(sq.ROOT, r['path'])
    if not os.path.exists(p):
        return None
    got = bodymeasure.piece_masks(spec)
    sh = bodymeasure.Sheet(spec)
    marks = json.load(open(sq.marks_path(spec)))
    return sh, got[0], marks


def test_design_passes_and_a_bad_version_fails():
    got = _design()
    if got is None:
        print('skipped: the outfit masks are not produced here')
        return
    sh, masks, marks = got
    O, names = sq.design_as_ours(sh.design, masks, marks, sh.ppl)
    T, C = sq.evaluate(O, names, sh.design, masks, marks, sh.ppl)
    bad = {k: v for k, v in C.items() if v['status'] != 'PASS'}
    assert len(C) > 30 and not bad, bad
    # a round-6-like version: each flap widened by 0.1 L into a lobe, the skirt's band 0.1 L taller in fine stairs
    from scipy import ndimage
    L_, R_ = names.index('overskirt_panel_L'), names.index('overskirt_panel_R')
    sk = names.index('skirt')
    for v, o in O.items():
        lab, cls = o['lab'].copy(), o['cls'].copy()
        for i in (L_, R_):
            grow = ndimage.binary_dilation(lab == i, iterations=int(0.1 * sh.ppl))
            lab[grow & ((lab < 0) | (lab == sk))] = i
        m = lab == sk
        cols = np.nonzero(m.any(0))[0]
        for c in cols:
            rr = np.nonzero(m[:, c])[0]
            k = int(0.1 * sh.ppl) + (4 if (c // 6) % 2 else 0)
            cls[rr[-1] - k:rr[-1] + 1, c] = sq.CL['dark']
        if v == 'back':                                            # the skirt's top jutting 0.06 L past the band (the outline)
            wb = lab == names.index('waistband')
            rows = np.nonzero(wb.any(1))[0]
            for r in rows[len(rows) // 2:]:
                c = np.nonzero(wb[r])[0]
                k = int(0.06 * sh.ppl)
                for a_, b_ in ((c[0] - k, c[0]), (c[-1] + 1, c[-1] + 1 + k)):
                    lab[r, a_:b_] = sk
        if v in ('profile', 'profile_R'):                         # the train hugging the back of the leg
            fl = L_ if v == 'profile' else R_
            fg = o['fg'].copy()
            for r, g in sq.leg_clearance(cls, fg, sh.ppl).items():
                if g:
                    c = np.nonzero(cls[r] == sq.CL['skin'])[0].max()
                    k = int(round(g * sh.ppl))
                    lab[r, c + 1:c + 1 + k] = fl; cls[r, c + 1:c + 1 + k] = sq.CL['orange']; fg[r, c + 1:c + 1 + k] = True
            O[v] = dict(o, lab=lab, cls=cls, fg=fg)
            continue
        O[v] = dict(o, lab=lab, cls=cls)
    T, C2 = sq.evaluate(O, names, sh.design, masks, marks, sh.ppl)
    for k in ('flap_back_width_L', 'flap_back_width_R', 'flap_profile_width_L', 'hemband_skirt_height', 'hemband_skirt_steps',
              'skirt_back_outline', 'flap_profile_clear_L', 'flap_profile_clear_R'):
        assert C2[k]['status'] != 'PASS', (k, C2[k])


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
