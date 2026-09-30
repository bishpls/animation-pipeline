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


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
