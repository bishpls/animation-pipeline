"""charkit.refcheck on synthetic drawings with known answers (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import faceqa, refcheck


def test_guide_lines_are_painted_out_and_the_head_kept():
    H, W = 400, 600
    rgb = np.full((H, W, 3), 0.76)                                        # the grey paper
    yy, xx = np.mgrid[:H, :W]
    head = (yy - 200) ** 2 + (xx - 300) ** 2 < 120 ** 2
    rgb[head] = (0.97, 0.85, 0.76)                                        # a skin disk
    for y in (100, 230, 330):                                             # guide lines across paper and skin alike
        rgb[y:y + 2] = 0.35
    out, rows = refcheck.without_guides(rgb)
    assert len(rows) == 3 and all(abs(r - y) <= 2 for r, y in zip(rows, (100, 230, 330))), rows
    assert np.allclose(out[230, 300], (0.97, 0.85, 0.76), atol=0.02)      # the skin under the line comes back
    assert np.allclose(out[100, 50], 0.76, atol=0.02)                     # and the paper
    away = head & np.all([np.abs(yy - y) > 6 for y in (100, 230, 330)], 0)   # the rest of the head is untouched
    assert np.allclose(out[away], rgb[away])


def test_drawn_chin_finds_the_turn_to_the_neck_on_a_receding_profile():
    """an anime profile's lower face slopes back from the nose to the chin, then the edge jumps back to the neck."""
    z = np.arange(0.0, -0.6, -0.005)
    lead = np.where(z > -0.36, 0.16 + 0.54 * (z + 0.1), -0.2)            # receding 0.54 L per L (head_turnaround's
                                                                          # profile, measured), then the neck
    lead[z > -0.1] = np.nan
    chin = refcheck.drawn_chin(lead, z)
    assert abs(chin - (-0.355)) < 0.01, chin
    # the QA's rule for our 3D face (the chin as the most forward point) stops halfway down the slope on a drawing
    assert faceqa.chin_bottom(-lead, z, -0.2) > -0.34


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
