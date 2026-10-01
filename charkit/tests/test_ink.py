"""Creases as a line layer (charkit.garments.ink_strokes / with_ink, tool/garments4): strokes given in a piece's own UV
become thin ribbons lying just off its rendered surface, on an ink material slot, taking no outline (the outline_w
group 0) and no thickness (charkit.evalmesh.finalize leaves them out of the Solidify), so the piece stays one object."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import garments as g


def sheet(n=12, bulge=0.0):
    """a sheet over x, z in [0, 1], facing -y (toward the camera), its UV (x, z)."""
    xs = np.linspace(0, 1, n)
    X, Z = np.meshgrid(xs, xs, indexing='ij')
    Y = -bulge * np.sin(np.pi * X) * np.sin(np.pi * Z)
    V = np.c_[X.ravel(), Y.ravel(), Z.ravel()]
    F = [(i * n + j, (i + 1) * n + j, (i + 1) * n + j + 1, i * n + j + 1) for i in range(n - 1) for j in range(n - 1)]
    return dict(verts=V, faces=F, weights={'hips': np.ones(len(V))}, uv=[(x, z) for x, z in V[:, [0, 2]]])


CS = dict(strokes=[[[0.5, 0.2], [0.5, 0.8]]], width=0.02, lift=0.01, step=0.02, taper=0.3)


def test_a_stroke_lies_on_the_surface_at_its_uv_and_off_it_by_lift():
    G = sheet(bulge=0.1)
    K = g.ink_strokes(G, CS, 1.0)
    assert K is not None and len(K['faces']) >= 20
    P = K['verts']
    assert np.allclose(P[:, 0].mean(), 0.5, atol=0.01)                     # along u = 0.5
    assert P[:, 2].min() > 0.18 and P[:, 2].max() < 0.82                   # from v 0.2 to 0.8
    mid = np.abs(P[:, 2] - 0.5) < 0.03
    # in front of the bulged (subdivided) surface there, by about the lift
    assert (P[mid, 1] < -0.1 * 0.9).all()
    w = np.linalg.norm(P[0::2] - P[1::2], axis=1)
    assert w.max() <= 0.02 + 1e-9 and w.min() < 0.5 * w.max()             # the ends taper


def test_with_ink_appends_an_ink_slot_with_no_outline_and_finalize_gives_it_no_thickness(monkeypatch):
    from charkit import evalmesh
    monkeypatch.setattr(g, '_toon', lambda name, color, shade_mul=None: name)    # (Blender's material: its name here)
    G = sheet()
    n0, f0 = len(G['verts']), len(G['faces'])
    G2, mats, midx = g.with_ink(G, dict(name='skirt', creases=CS), ['m0'], None, 1.0, (0.3, 0.18, 0.16))
    assert mats == ['m0', 'skirt' + g.INK] and midx[:f0] == [0] * f0 and set(midx[f0:]) == {1}
    ow = G2['weights'][g.OUTLINE_W]
    assert (ow[:n0] == 1).all() and (ow[n0:] == 0).all()
    o = dict(name='skirt', V=G2['verts'], polys=G2['faces'], weights=G2['weights'], uv=G2['uv'], uv_corner=None,
             mat_idx=midx, materials=[dict(name='skirt'), dict(name='skirt' + g.INK)],
             mods={'thick': dict(type='SOLIDIFY', settings=dict(thickness=0.05, offset=-1.0, use_rim=True)),
                   'sub': dict(type='SUBSURF', settings=dict(levels=1, render_levels=1))})
    F = evalmesh.finalize(o)
    mat = np.asarray(F['mat_idx'])
    nink = len(G2['faces']) - f0
    assert (mat == 1).sum() == 4 * nink                                    # the strokes once (subdivided), no copy
    lay = np.asarray(F['layer'])
    assert set(lay[mat == 1]) == {0}
