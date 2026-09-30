"""the bow's tail knobs (garments._bow_mesh `ribbon.turn`, bow_hull `ribbon.stand`, tool/garments3 round 3): the tails
hung in front of the jacket read torn in profile when flush with its front (bow_profile_torn 0.066 -> 0.0 with stand
0.03 L on Clawd)."""
import numpy as np

from charkit import garments as gm


def _mesh(**rb):
    return gm._bow_mesh(np.zeros(3), 0.2, 0.62, 0.25, ribbon=rb or None)


def test_tail_share_marks_the_tails_only():
    G = _mesh()
    ts = G['tail_s']
    tails = np.isfinite(ts)
    assert tails.any() and not tails.all()
    assert ts[tails].min() == 0.0 and ts[tails].max() == 1.0
    # the tails hang below the lobes: their ends are the mesh's lowest points
    assert G['verts'][ts == 1.0][:, 2].max() < G['verts'][~tails][:, 2].min()


def test_turn_zero_is_the_old_ribbon():
    a, b = _mesh(), _mesh(turn=0.0)
    assert np.allclose(a['verts'], b['verts'])


def test_turn_swings_the_outer_edge_back_and_keeps_the_width():
    a, b = _mesh(), _mesh(turn=30.0)
    ts = a['tail_s']
    end = ts == 1.0
    Va, Vb = a['verts'][end], b['verts'][end]
    for V in (Va, Vb):
        assert len(V) == 12                                  # both tails' end sections (6 corners each)
    # the lobes and knot don't move
    assert np.allclose(a['verts'][~np.isfinite(ts)], b['verts'][~np.isfinite(ts)])
    for sx in (-1, 1):
        ea, eb = Va[np.sign(Va[:, 0]) == sx], Vb[np.sign(Vb[:, 0]) == sx]
        diam = lambda E: max(np.linalg.norm(p_[[0, 1]] - q_[[0, 1]]) for p_ in E for q_ in E)
        wa, wb = diam(ea), diam(eb)
        assert abs(wa - wb) < 0.02 * wa                      # a rotation: the section's size kept
        outer = eb[np.argmax(sx * eb[:, 0])]
        inner = eb[np.argmin(sx * eb[:, 0])]
        assert outer[1] > inner[1]                           # the outer edge back (+y), the inner forward
