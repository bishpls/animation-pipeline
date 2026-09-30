"""charkit.detailqa's midriff and boot measures on masks and meshes with known answers (venv: run this file, or
pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import detailqa as dq

PPL = 100.0                          # px per L in these masks
WIN = dict(x=2.0, top=0.0, bottom=-3.0)


def rect(shape, r0, r1, c0, c1):
    m = np.zeros(shape, bool)
    m[r0:r1, c0:c1] = True
    return m


# ------------------------------------------------------------------------------------------------------------ midriff
def test_torso_step_is_found_and_signed():
    # a torso 60 px wide from row 0 to 40, then a band 8 px wider each side from 40 to 60 (a step out at row 40)
    fg = rect((80, 200), 0, 40, 70, 130) | rect((80, 200), 40, 60, 62, 138)
    torso = fg.copy()
    rows, lo, hi = dq.torso_edges(fg, torso, PPL, 0.0, -0.595, WIN)
    left, right = dq.largest_jump(lo, rows, PPL, -1, win=WIN), dq.largest_jump(hi, rows, PPL, 1, win=WIN)
    assert left['out'] == 0.08 and left['inward'] == 0.0, left
    assert right['out'] == 0.08 and abs(right['out_z'] + 0.405) < 1e-9, right
    # a band set in by 5 px: an inward step
    fg2 = rect((80, 200), 0, 40, 70, 130) | rect((80, 200), 40, 60, 75, 125)
    r2 = dq.largest_jump(dq.torso_edges(fg2, fg2, PPL, 0.0, -0.595, WIN)[2], np.arange(60), PPL, 1, win=WIN)
    assert r2['inward'] == 0.05 and r2['out'] == 0.0, r2


def test_torso_edge_dropped_where_something_stands_beside_it():
    # an arm touching the torso's left side on rows 10-20: those rows' left edge isn't the torso's silhouette
    torso = rect((40, 200), 0, 40, 70, 130)
    arm = rect((40, 200), 10, 20, 40, 70)
    rows, lo, hi = dq.torso_edges(torso | arm, torso, PPL, 0.0, -0.395, WIN)
    assert np.isnan(lo[10:20]).all() and np.isfinite(lo[:10]).all() and np.isfinite(hi).all()


def test_junction_gap_and_overlap():
    lab = np.full((60, 40), -1)
    dep = np.full((60, 40), np.inf)
    lab[0:20], dep[0:20] = 1, 1.0                 # the top down to row 19
    lab[24:40], dep[24:40] = 2, 1.0               # the band from row 24: rows 20-23 see through
    j = dq.junction(lab, dep, [1], [2], PPL, 1.0, range(40))
    assert j['gap'] == 0.04 and j['over'] == 0.0 and j['share'] == 1.0, j
    lab[20:24] = 1                                # closed: the top meets the band
    assert dq.junction(lab, dep, [1], [2], PPL, 1.0, range(40))['gap'] == 0.0
    lab2 = lab.copy()
    lab2[26:30, 10:20] = 1                        # the top showing over the band's face
    assert dq.junction(lab2, dep, [1], [2], PPL, 1.0, range(40))['over'] == 0.04


def test_skirt_overhang_finds_a_ledge_beside_the_band():
    # a band 60 px wide on rows 20-40; a skirt from row 36 (under the band's lower rows) flaring below it; on the image's
    # left the skirt's top juts 12 px past the band level with it (a ledge), on the right it stays inside
    band = rect((80, 200), 20, 40, 70, 130)
    skirt = np.zeros((80, 200), bool)
    for r in range(36, 80):
        w = 28 + (r - 36) // 2
        skirt[r, 100 - w:100 + w] = True
    skirt[34:40, 58:70] = True
    o = dq.skirt_overhang(band, skirt, PPL)
    assert o['left'] == 0.12 and o['right'] == 0.0, o
    C = dq.overhang_checks(o, dict(left=0.0, right=0.0))
    assert C['body_front_skirt_overhang_R']['status'] == 'FAIL' and C['body_front_skirt_overhang_L']['status'] == 'PASS'
    assert C['body_front_skirt_overhang_mirror']['value'] == 0.12
    same = dq.overhang_checks(dict(left=0.05, right=0.05), dict(left=0.08, right=0.08))
    assert all(v['status'] == 'PASS' for v in same.values()), same


def test_leg_back_bump_against_the_design():
    # profile class images: a face to the image's left of the hair at the eye line; a leg (skin) whose back edge runs
    # straight, and ours with a 10 px bump behind it on a few rows and the whole leg 3 px further back
    win = dict(x=2.0, top=1.0, bottom=-4.5)
    H, W = int(5.5 * PPL), 400
    z = win['top'] - (np.arange(H) + 0.5) / PPL
    def fig(shift=0, bump=0):
        c = np.zeros((H, W), int)
        eye = np.abs(z) < 0.2
        c[eye, 150:180] = dq.CL['skin']; c[eye, 180:230] = dq.CL['hair']
        leg = (z <= -2.6) & (z >= -4.0)
        c[leg, 170 + shift:230 + shift] = dq.CL['skin']
        b = (z <= -2.8) & (z >= -2.9)
        c[b, 230 + shift:230 + shift + bump] = dq.CL['skin']
        return c
    back = dq.leg_back(fig(), PPL, win=win)
    assert len(back) > 100 and abs(max(back.values()) - 2.29) < 1e-6, max(back.values())
    C = dq.leg_back_check(fig(3, 10), fig(), PPL, win=win)
    assert C['value'] == 0.1 and C['offset'] == 0.03 and C['status'] == 'FAIL', C


def test_leg_back_reads_ours_on_the_designs_facing_and_skips_the_garment_edges():
    # ours with a lock of hair in front of the eyes (face_side then reads ours facing the other way), and the design's
    # boot cuff line sloping: its last two leg rows cut short at the back. Neither is a bump of the leg
    win = dict(x=2.0, top=1.0, bottom=-4.5)
    H, W = int(5.5 * PPL), 400
    z = win['top'] - (np.arange(H) + 0.5) / PPL
    def fig(lock=False, cuff=False):
        c = np.zeros((H, W), int)
        eye = np.abs(z) < 0.2
        c[eye, 150:180] = dq.CL['skin']; c[eye, 180:230] = dq.CL['hair']
        if lock:
            c[eye, 100:150] = dq.CL['hair']
        leg = (z <= -2.6) & (z >= -4.0)
        c[leg, 170:230] = dq.CL['skin']
        if cuff:
            c[(z < -3.98) & (z >= -4.0), 215:230] = 0
        return c
    assert dq.face_side(fig(lock=True), PPL, win) == 1 and dq.face_side(fig(), PPL, win) == -1
    C = dq.leg_back_check(fig(lock=True), fig(cuff=True), PPL, win=win)
    assert C['value'] == 0.0 and C['offset'] == 0.0 and C['status'] == 'PASS', C
    assert C['rows'][1] > -4.0 + dq.LEG_EDGE - 0.01, C


def _legs(win, H, W):
    """a profile figure maker for the leg tests: face left of the hair at the eye line, a leg (skin) from -2.74 to
    -4.0, optionally a hand (skin) above the shorts, the shorts (dark) from -2.6 to -2.74, a bump behind the thigh,
    and a flap (orange) hanging against the thigh's back."""
    z = win['top'] - (np.arange(H) + 0.5) / PPL
    def fig(bump=0, hand=False, flap=0, gap=0):
        c = np.zeros((H, W), int)
        eye = np.abs(z) < 0.2
        c[eye, 150:180] = dq.CL['skin']; c[eye, 180:230] = dq.CL['hair']
        c[(z <= -2.6) & (z > -2.74), 160:240] = dq.CL['dark']
        c[(z <= -2.74) & (z >= -4.0), 170:230] = dq.CL['skin']
        if hand:
            c[(z <= -2.6) & (z >= -2.66), 250:290] = dq.CL['skin']
        b = (z <= -2.8) & (z >= -2.9)
        c[b, 230:230 + bump] = dq.CL['skin']
        if flap:
            c[(z <= -2.76) & (z >= -3.1), 230 + gap:230 + gap + flap] = dq.CL['orange']
        return c
    return fig


def test_leg_back_takes_the_designs_leg_alone_and_reads_the_bare_leg():
    # the design's hand above its shorts is skin in the band too: only the leg's own rows count. A bump the dressed
    # figure hides under a flap hanging against the thigh shows on the bare leg; the design against itself reads 0
    win = dict(x=2.0, top=1.0, bottom=-4.5)
    H, W = int(5.5 * PPL), 400
    fig = _legs(win, H, W)
    design = fig(hand=True, flap=40, gap=60)
    assert dq.leg_rows([5, 6, 7, 20, 21, 22, 23, 24]) == [20, 21, 22, 23, 24] and dq.leg_rows([]) == []
    self = dq.leg_back_check(design, design, PPL, win=win)
    assert self['value'] == 0.0 and self['status'] == 'PASS' and self['rows'][0] < -2.74, self
    bare = dq.leg_back_check(fig(bump=10), design, PPL, win=win)
    assert bare['value'] == 0.1 and bare['status'] == 'FAIL' and -2.9 <= bare['at'] <= -2.8, bare
    dressed = dq.leg_back_check(np.where(fig(flap=40) > 0, fig(flap=40), fig(bump=10)), design, PPL, win=win)
    assert dressed['status'] == 'PASS', dressed           # the flap over the bump: the dressed leg can't see it


def test_leg_outline_sees_a_garment_hugging_the_thigh():
    win = dict(x=2.0, top=1.0, bottom=-4.5)
    H, W = int(5.5 * PPL), 400
    fig = _legs(win, H, W)
    design = fig(flap=40, gap=60)                          # the design's flap hangs clear of the leg
    O = dq.leg_outline_check(fig(flap=40), design, PPL, win=win)
    assert O['status'] == 'FAIL' and O['value'] == 0.4 and O['hugging'] >= 30 and O['hugging_design'] == 0, O
    clear = dq.leg_outline_check(design, design, PPL, win=win)
    assert clear['value'] == 0.0 and clear['hugging'] == 0 and clear['status'] == 'PASS', clear


def test_outline_roughness_staircase_against_straight():
    straight = np.zeros((100, 200), bool)
    for c in range(200):
        straight[: 40 + c // 10, c] = True            # a gentle slope, one pixel every ten columns
    stair = np.zeros((100, 200), bool)
    for c in range(200):
        stair[: 40 + 8 * (c // 40) + (10 if (c // 10) % 2 else 0), c] = True   # 10 px teeth every 10 columns
    rs, rt = dq.outline_roughness(straight, PPL, 0.03), dq.outline_roughness(stair, PPL, 0.03)
    assert rs <= 0.005 and rt >= 0.015, (rs, rt)


def test_fragments_and_holes():
    m = rect((60, 60), 10, 50, 10, 50)
    assert dq.fragments(m) == (0, 0)
    m[20:24, 20:24] = False                        # a hole
    m[55, 55] = True                               # a speck: a fragment
    assert dq.fragments(m) == (1, 1)


# ------------------------------------------------------------------------------------------------------------ boots
def boot_front(jog=0):
    """a front-view boot 200 rows tall: a shaft 30 px wide, the foot below row 110 shifted by `jog` px."""
    M = np.zeros((220, 120), bool)
    M[10:110, 40:70] = True
    M[110:210, 40 + jog:70 + jog] = True
    return M


def test_ankle_jog():
    a = dq.ankle(boot_front(0), 10, 209, PPL)
    assert abs(a['jog']) < 1e-6 and abs(a['bend']) < 1e-6, a
    b = dq.ankle(boot_front(8), 10, 209, PPL)
    assert abs(b['jog'] - 0.08) < 1e-6, b


def boot_profile(bump_front=0, bump_back=0, heel=True):
    """a profile boot 200 rows tall, toe to the left: a shaft (cols 60-90) to row 130, a foot sweeping to col 10 at the
    bottom; a heel block (cols 70-90, rows 160-200) under a raised arch when `heel`; bumps (px) at row 100 on the
    shaft's front (left) and back (right) edges, 16 rows tall."""
    M = np.zeros((220, 140), bool)
    dark = np.zeros_like(M)
    for r in range(10, 210):
        lo, hi = 60, 90
        if r >= 130:
            lo = int(60 - 50 * ((r - 130) / 80) ** 1.6)
        if 92 <= r < 108:
            k = 1 - abs(r - 100) / 8
            lo -= int(round(bump_front * k)); hi += int(round(bump_back * k))
        bottom = 209
        M[r, lo:hi + 1] = True
    if heel:
        M[170:210, 45:70] = False                 # the arch: nothing under the foot between the forefoot and the heel
        M[190:210, 30:45] = True                  # (the forefoot's sole stays on the ground)
        dark[170:210, 70:91] = True               # the heel block
        dark[165:170, 30:91] = True               # the sole over the arch
        dark[200:210, 10:45] = True               # the forefoot's sole
    else:
        dark[200:210] = True
    return M, dark & M


def test_scrunch_front_and_back():
    M, _ = boot_profile(bump_front=4, bump_back=0)
    f, b = dq.scrunch(M, 10, 209, PPL, 'front'), dq.scrunch(M, 10, 209, PPL, 'back')
    assert f['present'] and abs(f['size'] - 0.04) <= 0.011 and 0.4 < f['at'] < 0.5, f
    assert not b['present'], b
    M2, _ = boot_profile(bump_front=0, bump_back=3)
    assert dq.scrunch(M2, 10, 209, PPL, 'back')['present'] and not dq.scrunch(M2, 10, 209, PPL, 'front')['present']


def test_heel_present_and_absent():
    M, dark = boot_profile(heel=True)
    h = dq.heel(M, dark, 10, 209, PPL, low=1.0)
    assert h['present'] and abs(h['height'] - 0.45) < 0.02 and abs(h['depth'] - 0.21) < 0.02, h
    M2, dark2 = boot_profile(heel=False)
    assert not dq.heel(M2, dark2, 10, 209, PPL, low=1.0)['present']


def test_doubled_strokes():
    fg = rect((100, 100), 10, 90, 10, 90)
    one = rect((100, 100), 10, 90, 40, 42)
    assert dq.doubled(one, fg, PPL) == 0
    two = one | rect((100, 100), 10, 90, 50, 52)  # a second stroke 8 px off, surface between: doubled over 80 rows
    assert dq.doubled(two, fg, 1000.0) == 0.08
    far = one | rect((100, 100), 10, 90, 70, 72)  # 28 px apart at 1000 px per L: 0.028 L, past the gap
    assert dq.doubled(far, fg, 1000.0) == 0


def box(x0, x1, y0, y1, z0, z1):
    V = np.array([[x, y, z] for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)], float)
    T = np.array([[0, 2, 1], [1, 2, 3], [4, 5, 6], [5, 7, 6], [0, 1, 4], [1, 5, 4], [2, 6, 3], [3, 6, 7],
                  [0, 4, 2], [2, 4, 6], [1, 3, 5], [3, 7, 5]])
    return V, T


def sole_grid(roll_toe):
    """a foot's bottom, 0.3 wide and 0.8 long along y, as two halves of triangles; the toe's half rolled `roll_toe`
    degrees about the foot's axis."""
    g = np.linspace(0.0, 0.3, 7)
    Vs, Ts = [], []
    for y0, y1, rl in ((0.0, 0.4, 0.0), (-0.4, 0.0, roll_toe)):
        base = len(Vs)
        for yy in np.linspace(y0, y1, 5):
            for xx in g:
                Vs.append([xx, yy, np.tan(np.radians(rl)) * (xx - 0.15)])
        for j in range(4):
            for i in range(len(g) - 1):
                a, b = base + j * len(g) + i, base + (j + 1) * len(g) + i
                Ts += [[a, b, a + 1], [a + 1, b, b + 1]]
    return np.array(Vs, float), np.array(Ts)


def test_sole_flat_and_twisted():
    V, T = sole_grid(0.0)                              # a flat bottom, long along y
    s = dq.sole(V, T, 1.0, (0.0, -1.0))
    assert s['flat'] < 1e-6 and s['twist'] < 0.5, s
    V2, T2 = sole_grid(6.0)                            # the toe's half rolled 6 degrees: twisted
    s2 = dq.sole(V2, T2, 1.0, (0.0, -1.0))
    assert s2['twist'] > 4 and s2['flat'] > 0.005, s2


def test_mirrors():
    a = rect((50, 100), 10, 40, 10, 30)
    b = rect((50, 100), 10, 40, 70, 90)
    assert dq.mirror_iou(a, b) == 1.0
    c = rect((50, 100), 10, 40, 70, 95)
    assert dq.mirror_iou(a, c) < 0.85
    V, T = box(0.2, 0.4, -0.4, 0.4, 0.0, 0.3)
    Vr = V * np.array([-1, 1, 1])
    assert dq.footprints_mirror(V, T, Vr, T[:, ::-1], 0.0, 1.0) > 0.99
    assert dq.footprints_mirror(V, T, Vr, T[:, ::-1], 0.05, 1.0) < 0.8

if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
