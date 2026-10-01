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


def test_panel_space_strokes_ride_across_the_panel():
    # (f, v) across a skirt's front panel: f -1 and 1 its edge columns' u (G['panel_u']), 0 its middle
    G = dict(sheet(), panel_u=(0.3, 0.7))
    K = g.ink_strokes(G, dict(CS, space='panel', strokes=[[[0.5, 0.2], [0.5, 0.8]]]), 1.0)
    assert np.allclose(K['verts'][:, 0].mean(), 0.6, atol=0.01)            # halfway from the middle (0.5) to 0.7
    assert g.ink_strokes(sheet(), dict(CS, space='panel'), 1.0) is None     # (no panel: nothing drawn)


def test_panel_warp_tapers_the_panel_and_keeps_the_columns_in_order():
    n = 144
    th = -np.pi + (np.arange(n) + 0.5) * 2 * np.pi / n
    half = np.radians(20)
    ks = np.nonzero(np.abs(th) < half)[0]
    bl, br = th[ks.min()], th[ks.max() + 1]
    c, h0 = (bl + br) / 2, (br - bl) / 2
    VV = np.array([[0.0] * n, [0.5] * n, [1.0] * n])
    W = g.panel_warp(th, half, VV, dict(top=0.1, power=1.0, scale=1.0))
    for i, f in enumerate((0.1, 0.55, 1.0)):
        assert np.isclose(W[i, ks.min()], c - f * h0) and np.isclose(W[i, ks.max() + 1], c + f * h0)
        assert (np.diff(np.unwrap(W[i])) > 0).all()                          # no column crosses another
    assert np.allclose(W[2], th)                                              # at the hem: as it was


def test_field_at_reads_the_grid_bilinearly_and_round_the_seam():
    class F_:
        pass
    n, vs = 8, np.linspace(0, 1, 5)
    F = F_(); F.th = -np.pi + (np.arange(n) + 0.5) * 2 * np.pi / n
    F.R = np.add.outer(vs * 10, np.arange(n, dtype=float))
    assert np.isclose(g._field_at(F, vs, np.array([0.5]), np.array([F.th[3]]))[0], 5 + 3)
    mid = (F.th[3] + F.th[4]) / 2
    assert np.isclose(g._field_at(F, vs, np.array([0.375]), np.array([mid]))[0], 3.75 + 3.5)
    seam = F.th[-1] + np.pi / n                                               # between the last column and the first
    assert np.isclose(g._field_at(F, vs, np.array([0.0]), np.array([seam]))[0], (7 + 0) / 2)


def test_the_render_drawing_reads_ink_primitives_as_the_ink_surface(monkeypatch):
    # charkit.qarender: the export draws a piece's *_ink primitive as surface pixels; they map to qa3d.render_surfaces'
    # ink surface (a line, as a hull is), not the cloth's, so declared.our_lines reads the creases with the render drawing
    from types import SimpleNamespace as NS
    from charkit import qarender
    monkeypatch.setattr(qarender, 'setting', lambda: 'render')
    memo = {}
    B = NS(memo=lambda k, f: memo.setdefault(k, f()))
    o = NS(name='skirt', group='garment', outline={'slot': 2}, materials=['skirt', 'skirt_ink', 'line_ink'])
    prims = [NS(object='skirt', material=0, variant=None), NS(object='skirt', material=1, variant=None)]
    Q = NS(objects=['skirt', 'skirt'], prims=prims, M=NS(js={'materials': [{'name': 'skirt'}, {'name': 'skirt_ink'}]}))
    surfs = [dict(o=o, variant='eval', hull=False, slots=np.array([0, 0])),
             dict(o=o, variant='eval', hull=True, slots=np.array([1, 1])),
             dict(o=o, variant='eval', hull=True, slots=np.array([2, 2]))]
    v = qarender.view(B, surfs, 0.0, None, Q=Q)
    assert v.index[(0, False)] == 0 and v.index[(1, False)] == 1           # the cloth; the strokes: the ink surface
    assert v.index[(0, True)] == 2 and v.index[(1, True)] == 2             # the outline: the hull

