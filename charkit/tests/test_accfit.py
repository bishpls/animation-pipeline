"""charkit.accfit (the hair clips' template and placement fits) on synthetic fixtures (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import accfit, accqa


def _design(kind, shape, poses):
    """a design whose drawn clip is the template itself, posed per view."""
    V, F = accfit.template(kind, shape)
    views = {v: {kind: accfit.silhouette(accfit.posed(V, *poses[v]), F)} for v in accfit.VIEWS}
    return dict(views=views, alone={})


def test_score_shape_reads_the_template_itself_whole():
    shape = dict(up=0.5, down=0.5, side=0.39, minor=0.3, inner=0.16, curve=0.0, minor_at=45.0)
    poses = {'front': (10.0, 2.0), 'three_quarter': (0.0, 0.0), 'profile': (-5.0, 1.0)}
    D = _design('star', shape, poses)
    sc = accfit.score_shape('star', shape, poses, D, 0.0, w_arms=0.0)
    assert all(v > 0.97 for v in sc['views'].values())
    # another pose reads worse
    off = accfit.score_shape('star', shape, {v: (40.0, 25.0) for v in accfit.VIEWS}, D, 0.0, w_arms=0.0)
    assert all(off['views'][v] < sc['views'][v] - 0.05 for v in accfit.VIEWS)


def test_posed_turns_about_up_and_spins_in_plane():
    V = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    P = accfit.posed(V, yaw=90.0)
    assert np.allclose(P[0], [0, 0, -1], atol=1e-9) and np.allclose(P[1], [0, 1, 0], atol=1e-9)
    Q = accfit.posed(V, roll=90.0)
    assert np.allclose(Q[0], [0, 1, 0], atol=1e-9)


def test_occluder_is_the_other_drawn_clips():
    a = np.zeros((10, 10), bool); a[2:4, 2:4] = True
    b = np.zeros((10, 10), bool); b[5:7, 5:7] = True
    D = dict(views={'front': {'crab': a, 'star': b}})
    assert (accfit.occluder(D, 'front', 'crab') == b).all() and (accfit.occluder(D, 'front', 'star') == a).all()
    assert accfit.occluder(D, 'profile', 'crab') is None


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
