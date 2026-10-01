"""charkit.nose (the nose's drawn mark) and the lash line's spikes (charkit.eyes.spikes): known shapes on a flat face
(venv: run this file, or pytest)."""
import json, os, sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from charkit import eyes, nose  # noqa: E402
from charkit.tests.test_mouth import Flat  # noqa: E402

SPEC = json.load(open(os.path.join(ROOT, 'charkit', 'spec', 'clawd.json')))


def test_the_nose_mark_sits_round_the_tip_in_front_of_the_face():
    K = nose.knobs({'nose': {}})
    v, q, sl = nose.mark(Flat(), K, 1.0, (0.0, 0.0))
    assert set(sl) == {0, 1} and len(q) == len(sl)
    tick = v[:len(v) // 2]
    assert abs(tick[:, 0].mean()) < 1e-9 and np.ptp(tick[:, 2]) <= K['tick'][1] + 1e-9
    assert np.all(v[:, 1] < -0.1)                             # a hair in front of the skin (the face looks down -y)
    assert v[len(v) // 2:, 2].mean() > tick[:, 2].mean()      # the highlight over the tick


def test_spikes_leave_the_band_upward_and_outward():
    K = eyes.knobs(SPEC)
    up = lambda t: eyes.outline(K, 1.0, t, 'upper')
    lines = eyes.spike_lines(K, 1.0, up)
    assert len(lines) == len(SPEC['eyes']['spikes'])
    for (t0, ln, ang, w, curl), (pts, th) in zip(SPEC['eyes']['spikes'], lines):
        d = pts[-1] - pts[0]
        assert d[1] > 0                                       # up, off the lid
        assert np.sign(d[0]) == np.sign(ang)                  # toward the corner it leans to
        assert th[0] > th[-1]                                 # tapering


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
