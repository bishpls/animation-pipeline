"""charkit.trace's mesh health and diff on meshes with known answers (venv: python -m pytest charkit/tests, or run this file)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import trace

CUBE_V = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]], float)
CUBE_F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]   # outward


def test_closed_cube():
    h = trace.health(CUBE_V, CUBE_F)
    assert h['open_edges'] == 0 and h['nonmanifold_edges'] == 0
    assert h['shells'] == 1 and h['closed_shells'] == 1 and h['inverted_shells'] == 0
    assert h['edges'] == 12 and h['degenerate_faces'] == 0 and h['loose_verts'] == 0
    assert abs(h['area'] - 6) < 1e-9


def test_open_inverted_two_shells_loose():
    h = trace.health(CUBE_V, CUBE_F[1:])
    assert h['open_edges'] == 4 and h['closed_shells'] == 0
    inv = [f[::-1] for f in CUBE_F]
    assert trace.health(CUBE_V, inv)['inverted_shells'] == 1
    V2 = np.vstack([CUBE_V, CUBE_V + 3, [[9, 9, 9]]])
    F2 = CUBE_F + [tuple(i + 8 for i in f) for f in CUBE_F]
    h = trace.health(V2, F2)
    assert h['shells'] == 2 and h['closed_shells'] == 2 and h['loose_verts'] == 1


def test_nonmanifold_and_degenerate():
    V = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [2, 0, 0]], float)
    F = [(0, 1, 2), (0, 1, 3), (0, 1, 4), (0, 1, 5)]           # four faces on edge 0-1; the last one has no area
    h = trace.health(V, F)
    assert h['nonmanifold_edges'] == 1 and h['degenerate_faces'] == 1


def test_flat_forms_and_hash():
    a = trace.health(CUBE_V, np.array(CUBE_F))
    loopv = np.array([i for f in CUBE_F for i in f]); starts = np.arange(6) * 4; counts = np.full(6, 4)
    b = trace.health(CUBE_V, (loopv, starts, counts))
    assert a == b
    assert trace.geometry_hash(CUBE_V, CUBE_F) == trace.geometry_hash(CUBE_V + 1e-7, CUBE_F)
    assert trace.geometry_hash(CUBE_V, CUBE_F) != trace.geometry_hash(CUBE_V * 1.01, CUBE_F)


def test_diff():
    def build(scale, knob):
        V = CUBE_V * scale
        obj = dict(type='MESH', hash=trace.geometry_hash(V, CUBE_F), health=trace.health(V, CUBE_F),
                   bbox=[V.min(0).tolist(), V.max(0).tolist()])
        return [dict(event='begin', git='x', spec_hash=knob),
                dict(event='stage', name='character', dt=1.0, objects=1, added={'skin': obj}, changed={}, removed=[],
                     knobs={'head': knob}, landmarks={'L': 0.25 * scale}),
                dict(event='qa', checks={'shape_iou': [0.5, 'FAIL']})]
    assert trace.diff(build(1, 'a'), build(1, 'a')) == 'no differences'
    d = trace.diff(build(1, 'a'), build(1.1, 'b'))
    assert 'knobs head changed' in d and 'landmarks.L' in d and 'skin.bbox' in d and 'skin.health.area' in d
    assert 'summary' not in d and 'stage character' in trace.summary(build(1, 'a'))


def test_faults_sheets():
    h = trace.health(CUBE_V, CUBE_F[1:])
    assert trace.faults({'health': h}) == {'open_edges': 4}
    assert trace.faults({'health': h, 'sheet': True}) == {}


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
