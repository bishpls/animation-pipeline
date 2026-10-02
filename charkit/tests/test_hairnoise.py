"""hair_noise's speckle measure (round 4, tool/hairshell3): qa3d.speckles on synthetic hair pictures."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import numpy as np


def picture(H=120, W=160):
    px = np.zeros((H, W, 4)); px[10:H - 10, 5:W - 5, 3] = 1.0          # the hair's silhouette, background round it
    px[..., :3] = (0.84, 0.47, 0.33)                                    # the lit tone
    lab = (px[..., 3] > 0.5).astype(int)
    ink = np.zeros((H, W), bool)
    return px, lab, ink


def test_a_lock_shaped_shadow_is_no_speckle():
    from charkit import qa3d
    px, lab, ink = picture()
    px[20:100, 40:60, :3] = (0.67, 0.33, 0.24)                         # a long shadow (1600 px): a lock's, not a blot
    sp, n, npx = qa3d.speckles(px, lab, ink, step=0.144, ppl=82.3)
    assert n == 0 and not sp.any() and npx == lab.sum()


def test_small_blots_are_speckles_and_the_ink_and_the_edge_are_not():
    from charkit import qa3d
    px, lab, ink = picture()
    for (r, c) in ((30, 30), (60, 90), (90, 120)):                      # three light blots of 3x3 px in the mass
        px[r:r + 3, c:c + 3, :3] = (0.97, 0.86, 0.78)
    px[50:53, 10:13, :3] = (0.97, 0.86, 0.78); ink[48:56, 8:16] = True  # one under the ink: the line's
    px[10:12, 70:73, :3] = (0.97, 0.86, 0.78)                           # one on the silhouette's edge (2 px)
    px[60:62, 140:142, :3] = (0.86, 0.49, 0.34)                         # a faint one (under half the cel step)
    sp, n, _ = qa3d.speckles(px, lab, ink, step=0.144, ppl=82.3)
    assert n == 3, n


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
