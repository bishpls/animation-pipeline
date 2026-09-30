"""charkit.pieceqa's measures on synthetic masks: spikes on an outline (a horn, a pointed corner) against a clean round
shape; the drawing's fold strokes closed before an outline is measured; the silhouette's outline pixels; a puff's
widths across its arm (the stand-off and the gathers); a band's edges and width (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import pieceqa as pq

PPL = 200.0


def disk(n, cx, cy, r):
    y, x = np.mgrid[:n, :n]
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def test_a_round_shape_has_no_spikes():
    m = disk(200, 100, 100, 50)
    s = pq.spikes(m, PPL)
    assert s['n'] == 0 and s['depth'] == 0.0


def test_a_horn_is_a_spike_as_deep_as_it_stands_out():
    m = disk(200, 100, 100, 40)
    m[40:62, 97:103] = True                              # a horn 6 px wide standing 0.1 L (20 px) out of the disk
    s = pq.spikes(m, PPL)
    assert s['n'] == 1
    assert abs(s['depth'] - 0.1) < 0.02, s
    r, c = s['at'][0]
    assert r <= 42 and 95 <= c <= 105                      # its tip


def test_a_pointed_corner_is_a_spike_a_rounded_one_is_not():
    n = 200
    y, x = np.mgrid[:n, :n]
    sharp = (y > 60) & (y < 160) & (np.abs(x - 100) < (y - 60) * 0.5 + 1)         # a triangle, its apex 53 degrees
    s = pq.spikes(sharp, PPL)
    assert s['n'] == 3 and min(r for r, c in s['at']) <= 62     # its three corners, the apex at the top among them
    round_ = disk(n, 100, 110, 45)
    assert pq.spikes(round_, PPL)['n'] == 0


def test_spikes_only_where_the_outline_is_the_silhouette():
    m = disk(200, 100, 100, 40)
    m[20:62, 97:103] = True
    fg = np.ones_like(m)                                  # the horn lies against another piece, not the background
    where = pq.silhouette(m, fg, PPL)
    assert pq.spikes(m, PPL, where=where)['n'] == 0
    fg = m.copy()
    assert pq.spikes(m, PPL, where=pq.silhouette(m, fg, PPL))['n'] == 1


def test_clean_closes_the_drawings_fold_strokes():
    m = disk(200, 100, 100, 50)
    m[60:100, 99:101] = False                             # a fold stroke cut out of the mask, open to nothing
    m[100:140, 80:82] = False
    c = pq.clean(m, PPL)
    assert c[60:100, 99:101].all() and c[100:140, 80:82].all()
    assert pq.spikes(m, PPL)['n'] >= 0 and pq.outline_roughness(c, PPL) <= pq.outline_roughness(m, PPL)


def pear(n=300, gather=0.6):
    """a puff down an arm along +rows: widest low, gathered into a band, the bare arm below."""
    y, x = np.mgrid[:n, :n]
    s = (y - 40) / 160.0                                  # 0 at its top .. 1 at the band
    half = np.where(s < 0.8, 20 + 40 * np.sin(np.pi / 2 * np.clip(s / 0.8, 0, 1)),
                    60 - (60 - 60 * gather) * np.clip((s - 0.8) / 0.2, 0, 1))
    sleeve = (s >= 0) & (s <= 1) & (np.abs(x - 150) <= half)
    cuff = (y > 200) & (y <= 220) & (np.abs(x - 150) <= 34)
    arm = (y > 220) & (y < 290) & (np.abs(x - 150) <= 20)
    return sleeve, cuff, arm


def test_arm_profile_reads_the_stand_off_and_the_gathers():
    sleeve, cuff, arm = pear()
    p = pq.arm_profile(sleeve, cuff, arm, PPL)
    assert abs(p['puff'] - 0.6) < 0.02, p                 # 120 px widest
    assert abs(p['arm'] - 0.205) < 0.01, p
    assert abs(p['standoff'] - p['puff'] / p['arm']) < 1e-3
    tight = pq.arm_profile(*pear(gather=0.5), PPL)
    loose = pq.arm_profile(*pear(gather=0.9), PPL)
    assert tight['gather'] < loose['gather']
    w = p['widths']
    assert len(w) == 11 and w[0] < w[3] < w[8]            # narrow at the cap, widest low


def test_edges_of_a_band():
    m = np.zeros((200, 200), bool)
    m[80:110, 40:160] = True
    m[75:80, 40:50] = True                                # its ends curve up (left out: the middle columns decide)
    e = pq.edges(m)
    assert e['top'] == 80 and e['bottom'] == 109 and e['width'] == 120


def cup(n=300, top=60, bottom=48):
    """a wrist cuff down an arm along +rows (its top the elbow's side), the forearm above it and the hand below."""
    y, x = np.mgrid[:n, :n]
    f = np.clip((y - 120) / 60.0, 0, 1)
    half = top + (bottom - top) * f
    M = (y >= 120) & (y <= 180) & (np.abs(x - 150) <= half)
    skin = ((y >= 40) & (y < 120) | (y > 180) & (y < 260)) & (np.abs(x - 150) <= 30)
    cream = M & (y < 135)
    return M, skin, cream


def test_cuff_shape_reads_the_flare_and_the_trim():
    M, skin, cream = cup()
    c = pq.cuff_shape(M, skin, cream, PPL)
    assert c['flare'] > 1.15 and abs(c['trim'] - 0.25) < 0.05, c
    M2, skin2, cream2 = cup(top=50, bottom=56)                 # a band wider at its bottom, no trim
    c2 = pq.cuff_shape(M2, skin2, np.zeros_like(M2), PPL)
    assert c2['flare'] < 1.0 and c2['trim'] == 0.0


def junction(tucked):
    """a jacket over a band (or tucked under it): the composite and each drawn alone."""
    n = 120
    top_a = np.zeros((n, n), bool); band_a = np.zeros((n, n), bool)
    top_a[10:70, 20:100] = True                                   # the jacket down to row 69
    band_a[60:90, 20:100] = True                                  # the band from row 60
    if tucked:
        comp_band = band_a.copy(); comp_top = top_a & ~band_a      # the band in front
    else:
        comp_top = top_a.copy(); comp_band = band_a & ~top_a        # the jacket in front
    return comp_top, comp_band, top_a, band_a


def test_junction_order_tells_which_hides_which():
    j = pq.junction_order(*junction(tucked=True), PPL)
    assert j['under'] == 1.0 and j['over'] == 0.0
    j = pq.junction_order(*junction(tucked=False), PPL)
    assert j['over'] == 1.0 and j['under'] == 0.0


def test_a_jacket_hung_over_all_round_is_not_tucked_by_its_back_panel():
    """drawn alone, a jacket over the band shows its back panel below its front hem (through its open front, and past
    the hem), far behind the band: with depths that isn't tucked; a front hem just inside the band is."""
    comp_top, comp_band, top_a, band_a = junction(tucked=False)
    n = top_a.shape[0]
    top_a = top_a.copy(); top_a[70:88, 20:100] = True             # the back panel, seen below the front hem
    d_top = np.full((n, n), 5.0); d_comp = np.full((n, n), 1.0)    # it lies 4 behind the band
    band_a2 = band_a.copy(); band_a2[60:70] = False                # the band not reaching up behind: only `under` counts
    j = pq.junction_order(comp_top, comp_band, top_a, band_a2, PPL, depths=(d_top, d_comp), near=0.3)
    assert j['under'] == 0.0
    d_top[70:88] = 1.1                                             # a front hem just inside the band: tucked
    j = pq.junction_order(comp_top, comp_band, top_a, band_a2, PPL, depths=(d_top, d_comp), near=0.3)
    assert j['under'] == 1.0


def test_half_widths_round_the_middle():
    m = np.zeros((700, 400), bool)
    r = int(round((pq.WIN['top'] + 1.1) * PPL - 0.5))
    m[r - 5:r + 5, 180:221] = True                                 # 41 px wide round column 200
    w = pq.half_widths(m, PPL, [-1.1, -2.0], cx=200)
    assert abs(w[0] - 20.5 / PPL) < 1e-6 and w[1] is None


def test_ink_core_leaves_the_jackets_part_of_the_band_mask_out():
    """the outfit masks give the band the jacket's lower part where it hangs over the band: the jacket's hem stroke
    (ink) cuts it off, and the band's own part is the larger one left."""
    from charkit import bodyqa
    band = np.zeros((60, 80), bool)
    band[10:50, 10:70] = True                       # the mask: the jacket's hem (rows 10-19) and the band (21-49)
    cls = np.zeros((60, 80), np.int32)
    cls[20, :] = bodyqa.CLASS['line']               # the jacket's hem stroke across it
    core = pq.ink_core(band, cls)
    rows = np.nonzero(core.any(1))[0]
    assert rows.min() >= 21 and rows.max() == 49    # the band below the stroke (its grown pixel), the jacket's left out
    assert pq.ink_core(band, np.zeros_like(cls)) is band      # no ink: the mask itself


def test_the_windowed_measures_read_as_the_whole_grid_does():
    """spikes, clean and bodymeasure's outline_f and iou_tol work on the pieces' own window (bodymeasure.window, the QA's
    time): the same numbers as on the whole grid, a piece at the grid's edge included."""
    from scipy import ndimage
    from charkit import bodymeasure as bm
    rng = np.random.default_rng(3)
    n = 300
    for k in range(6):
        m = disk(n, 60 + 40 * k, 150 + (k % 3) * 30, 25 + 5 * k)
        m[rng.integers(0, n, 40), rng.integers(0, n, 40)] = True            # specks and a horn
        m[140:150, 150:215] = k % 2 == 0
        if k == 5:
            m[:, :12] = True                                                  # at the grid's edge
        d = disk(n, 70 + 40 * k, 155 + (k % 3) * 30, 28 + 4 * k)
        # the whole-grid versions (the code before the window): spikes and clean padded round the whole grid
        rp = max(1.0, pq.SPIKE_R * PPL); pad = int(np.ceil(rp)) + 2
        M = np.pad(m, pad)
        op = ndimage.binary_opening(M, structure=pq.disk(rp))
        s = pq.spikes(m, PPL)
        if op.any():
            dd = ndimage.distance_transform_edt(~op)
            lab, nl = ndimage.label(M & ~op, structure=np.ones((3, 3)))
            deep = sorted([float(dd[lab == j].max()) / PPL for j in range(1, nl + 1)], reverse=True)
            assert s['depths'] == [round(x, 4) for x in deep if x >= pq.SPIKE_MIN]
        for (r_, c_), dep in zip(s['at'], s['depths']):
            assert m[r_, c_]
        rc = max(1.0, pq.CLOSE * PPL); pc = int(np.ceil(rc)) + 2
        full = ndimage.binary_fill_holes(ndimage.binary_closing(np.pad(m, pc), structure=pq.disk(rc)))[pc:-pc, pc:-pc]
        assert (pq.clean(m, PPL) == full).all()
        a, b = bm.outline(m), bm.outline(d)
        ta, tb = ndimage.distance_transform_edt(~a), ndimage.distance_transform_edt(~b)
        f = bm.outline_f(m, d, 3.0)
        assert f['p'] == float((tb[a] <= 3.0).mean()) and f['r'] == float((ta[b] <= 3.0).mean())
        assert f['d_ours'] == float(tb[a].mean()) and f['d_drawn'] == float(ta[b].mean())
        band = min(3.0, 0.5 * float(ndimage.distance_transform_edt(d).max()))
        keep = tb > band
        assert bm.iou_tol(m, d, 3.0) == float(((m & d) & keep).sum() / ((m | d) & keep).sum())
    assert bm.window(np.zeros((5, 5), bool)) is None


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
