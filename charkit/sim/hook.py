"""The opt-in hook (charkit.geomstage.garments_product): a garment whose spec asks for it is settled by the cloth solver
at rest before the build finalizes it. Off unless asked: no spec sets it, so no build changes.

    {"name": "overskirt_panel_L", ..., "drape": {"solver": "xpbd", "style": "anime", "rest": "template",
                                                 "colliders": ["skirt", "shorts"], "seconds": 5, "dials": {...}}}

style: the style profile (default the spec's `style`, else anime); rest: 'template' (the drawn shape is the rest shape)
or 'pattern' (flat, the template's lengths); colliders: the other recorded garments it rests on (the body always);
dials: charkit.sim.settings' dials by name (hold_shape, cloth_stiffness, hang, ...). The settled coarse vertices replace
the recording's; the stats go into the product's meta ('drape').
"""
import numpy as np


def wants(specs):
    """the garments that ask for the solver."""
    return [g['name'] for g in specs or [] if isinstance(g.get('drape'), dict) and g['drape'].get('solver') == 'xpbd']


def apply(P, A, specs, spec_all=None, log=None):
    """the product (before finalize) with each asking garment's coarse vertices settled against the body (the
    assembly A) and its colliders (recorded garments, finalized as the build will): -> P (the arrays replaced)."""
    from .. import evalmesh, geomstage
    from . import drape, xpbd
    names = wants(specs)
    if not names:
        return P
    obs = geomstage.pieces(P)[0]
    by = {o['name']: o for o in obs}
    L = float(A['head']['L'])
    body = (np.asarray(A['verts'], float), xpbd.triangulate(A['faces']))
    style0 = (spec_all or {}).get('style', 'anime')
    ids = {}
    for e in P['meta']['events']:
        if e[0] == 'call' and e[2] == '_object':
            d = dict(zip(geomstage.OBJECT_ARGS, e[3])); d.update(e[4])
            ids[d['name']] = d['verts']['$a']
    stats = {}
    for g in specs:
        if g['name'] not in names:
            continue
        o = by[g['name']]
        dr = g['drape']
        meshes = [body]
        for c in dr.get('colliders', ['skirt', 'shorts']):
            if c in by and c != g['name']:
                F = evalmesh.finalize(by[c]) if by[c]['mods'] else None
                if F is not None:
                    meshes.append((F['V'], drape._fan(F['loopv'], F['counts'])))
        V = o['V']
        box = (V.min(0) - 0.15 * L, V.max(0) + 0.15 * L)
        G = None
        for Vm, Tm in meshes:
            g_ = xpbd.SDFGrid.from_mesh(Vm, Tm, float(dr.get('grid', 0.01)) * L, box=box, sign='winding')
            G = g_ if G is None else xpbd.SDFGrid(np.minimum(G.G, g_.G), G.o, G.h)
        R = drape.settle(o, G, L, style=dr.get('style', style0), rest=dr.get('rest', 'template'),
                         seconds=float(dr.get('seconds', 5.0)), log=log or (lambda *a: None), **(dr.get('dials') or {}))
        P['arrays'][ids[g['name']]] = np.asarray(R['V'], float)
        stats[g['name']] = {k: v for k, v in R['stats'].items() if k != 'trace'}
    P['meta']['drape'] = stats
    return P
