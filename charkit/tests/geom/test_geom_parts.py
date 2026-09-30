"""charkit.geom.parts on a synthetic "generated character": a TRELLIS-like hollow double-walled head shell, hair-coloured
on top and skin-coloured below, over our body (a smaller ball), cut out as one closed part; the poke-through cover; and,
when the real GLB is there and CHARKIT_GEOM_REAL=1, the Clawd hair and skirt."""
import os, sys, types

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: F401
from charkit.geom import mesh, parts, primitives as pr, repair, bvh

HAIR = np.array([0.76, 0.26, 0.10])
SKIN = np.array([0.92, 0.72, 0.62])


def _case(body_centre=(0, 0, 0)):
    outer = pr.icosphere(4, r=0.125); inner = pr.icosphere(4, r=0.122)
    shell = mesh.concatenate([outer, inner.with_(F=inner.F[:, ::-1].copy())])
    vc = np.where(shell.V[:, 2:3] > 0.0, HAIR, SKIN)
    gen = shell.with_(vc=vc)
    body = pr.icosphere(4, r=0.1, centre=body_centre)
    return types.SimpleNamespace(L=0.25, gen=gen, body=body)


def test_extract_a_cap_from_a_hollow_shell():
    C = _case()
    keep = parts.ColorClass(hue=13, hue_tol=12, sat=(0.6, 1), val=(0.3, 1))
    assert keep(HAIR[None])[0] and not keep(SKIN[None])[0]
    E = parts.extract(C, lambda P: P[:, 2] > -0.05, keep, h=0.003, clear=0.003, color_depth=np.inf, seal=0.004,
                      verbose=False)
    R = parts.finish(E['sdf'], verbose=False, close=0.03, blur=0.02)
    r = R['report']
    assert r['watertight'] and r['shells'] == 1 and r['self_intersecting_faces_est'] == 0
    want = 2 / 3 * np.pi * (0.125 ** 3 - 0.103 ** 3)          # the upper half shell between our grown ball and the hair
    assert abs(r['volume'] - want) / want < 0.12, (r['volume'], want)
    m = R['mesh']
    assert m.V[:, 2].min() > -0.01                             # the skin-coloured lower half is gone
    assert np.linalg.norm(m.V, axis=1).min() > 0.1             # nothing inside our body
    # envelope normals on the outer surface point outward (the inner one faces our head, hidden)
    rad = np.linalg.norm(m.V, axis=1)
    out = (rad > 0.12) & (m.V[:, 2] > 0.02)
    assert (np.einsum('ij,ij->i', m.vn[out], m.V[out] / rad[out, None]) > 0.5).mean() > 0.95


def test_cover_closes_a_poke_through():
    C = _case(body_centre=(0.03, 0, 0))                          # our ball pokes out of the shell on +x
    keep = parts.ColorClass(hue=13, hue_tol=12, sat=(0.6, 1), val=(0.3, 1))
    ray = lambda m: bvh.BVH(m).ray_count(np.array([[0.03, 0, 0.03]]), np.array([[1.0, 0, 0.3]]))[0]
    E0 = parts.extract(C, lambda P: P[:, 2] > -0.05, keep, h=0.003, clear=0.003, color_depth=np.inf, verbose=False)
    E1 = parts.extract(C, lambda P: P[:, 2] > -0.05, keep, h=0.003, clear=0.003, color_depth=np.inf, verbose=False,
                       cover=dict(centre=(0.0, 0, 0), thick=0.004, depth=0.02))
    from charkit.geom import volume
    m0, m1 = volume.to_mesh(E0['sdf']), volume.to_mesh(E1['sdf'])
    assert ray(m0) == 0                                          # the hole: the ray out through it meets nothing
    assert ray(m1) >= 1 and E1['stats']['cover_vox'] > 0
    assert repair.report(m1, self_intersections=False)['watertight']


def test_color_classes():
    C = np.array([HAIR, SKIN, [0.98, 0.9, 0.7], [0.1, 0.05, 0.05]])
    fit = parts.dominant_class(np.repeat(HAIR[None], 50, 0) + np.random.default_rng(0).normal(0, 0.01, (50, 3)))
    assert list(fit(C)) == [True, False, False, False]


def test_real_clawd_if_asked():
    glb = os.environ.get('CHARKIT_GEOM_GLB')            # a generated character's GLB (TRELLIS.2's, kept by hand)
    if os.environ.get('CHARKIT_GEOM_REAL') != '1' or not glb:
        return
    C = parts.Case.load(os.path.join(_common.ROOT, 'charkit/spec/clawd.json'), glb=glb, verbose=False)
    R = parts.hair(C, verbose=False)
    st = parts.measure(C, R, parts.hair_region(C), parts.hair_color(C), zmin=C.chin_z)
    assert st['parts'] == 1 and st['open_edges'] == 0 and st['nonmanifold_edges'] == 0
    assert st['self_intersecting_faces'] == 0 and st['silhouette_iou_above_mean'] > 0.97
    S = parts.skirt(C, verbose=False)
    assert S['report']['shells'] == 1 and S['report']['watertight']


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
