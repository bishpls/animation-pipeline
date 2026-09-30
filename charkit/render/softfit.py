"""Template fits by gradients through the soft silhouettes (charkit.render.softras; docs/workstreams/softras.md): the
pilot harness, behind no default. The chain is template knobs -> vertices (the template's builder, its Jacobian by
finite differences with a limiter, since no builder here has an analytic one) -> per-view soft silhouettes (softras,
analytic d/dvertices) -> a soft IoU against the design's per-view masks; L-BFGS-B (scipy) over it. The pilot is the
overskirt flap template (garments.flap_template, the skirt's fit G), against its coordinate descent on the hard
silhouettes from the same start.

    python -m charkit.render.softfit scene [--spec SPEC] [--out DIR]      # the flap's frozen scene (once, ~minutes)
    python -m charkit.render.softfit fit cd|grad [--out DIR] [--start JSON]  # a fit from the same start, logged
    python -m charkit.render.softfit compare DIR                           # the fits' table and review page

The frozen scene (DIR/flap_scene.pkl): the assembly and hull the flap builder reads, the spec, the QA's windows per view
(skirtqa's our_views: bodyqa's azimuths and origins on the sheet's grid), the scene without the flaps z-buffered once per
view (object labels, depth, the side-split labels piece_shapes reads), the drawn flaps (skirtqa.drawn_pieces), the outfit
masks and graph. A candidate then costs its two flaps' builds and their rasterisation alone: skirt_scratch/fast.py's
compositing, by depth against the frozen scene.
"""
import copy, json, os, pickle, sys, time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'charkit', 'out', 'softras')
FLAPS = ('overskirt_panel_L', 'overskirt_panel_R')
VIEWS = ('front', 'three_quarter', 'profile', 'back')
VW = {'back': 1.0, 'profile': 1.0, 'three_quarter': 0.4, 'front': 0.7}     # fit G's view weights (skirt_scratch/fit.py)


# ------------------------------------------------------------------------------------------------------------ the scene
def build_scene(spec_path='charkit/spec/clawd.json', out=OUT, log=print):
    """the flap's frozen scene (see the module) -> its path."""
    from charkit import bodyeval, bodymeasure, bodyqa, cli, skirtqa as sq
    from charkit.faceqa import view as proj
    from charkit.geom import raster
    os.makedirs(out, exist_ok=True)
    t = time.time()
    spec = bodyeval.resolve(spec_path)
    res = os.path.join(out, 'resolved.json')
    spec = cli.code_head(spec, res, out)
    log('head code %.0f s' % (time.time() - t))
    spec = cli.code_body(spec, res, out)
    log('body code %.0f s' % (time.time() - t))
    E = bodyeval.Evaluator(spec)
    G = E.geometry()
    log('geometry %.0f s' % (time.time() - t))
    hull = next(v for k, v in E._garments.items() if k[1] == 'hull')
    Bd = G.bundle('viewport')
    S = E.sheet()
    ppl = S.ppl
    masks, graph = bodymeasure.piece_masks(G.spec)[:2]
    marks = json.load(open(sq.marks_path(G.spec)))
    objs = Bd['objects']
    names = [o['name'] for o in objs]
    vis = [i for i, o in enumerate(objs) if o.get('role') != 'unmasked']
    lm = Bd['landmarks']
    iris, centre, L = np.asarray(lm['iris'], float), lm['centre'], lm['L']
    az = bodyqa.azimuths(S.az3)
    az['profile_R'] = 270.0
    static = [i for i in vis if names[i] not in FLAPS]
    om = [(objs[i]['V'], objs[i]['F'], np.full(len(objs[i]['F']), i)) for i in static]
    pm = [(objs[i]['V'], objs[i]['F'], np.where(objs[i]['V'][objs[i]['F']].mean(1)[:, 0] >= 0, i, i + 1000))
          for i in static]
    views = {}
    for v in VIEWS + ('profile_R',):
        if v == 'profile_R':
            P = iris[np.argmin(iris[:, 0])][None]
            org = (float(proj(P, 270.0)[0][0]), float(np.mean(iris[:, 2])))
        else:
            org = bodyqa.origin(v, az[v], iris, centre)
        a = (az[v], org, L, 1.0 / ppl, bodyqa.WIN)
        d_o, l_o = raster.window_zbuffer(om, *a)
        d_p, l_p = raster.window_zbuffer(pm, *a)
        views[v] = dict(az=float(az[v]), origin=(float(org[0]), float(org[1])), depth=d_o, lab=l_o, lab_pc=l_p)
    P = sq.drawn_pieces(S.design, masks, marks, ppl)
    drawn = {v: {f: P[v]['full'][f] for f in FLAPS} for v in P}
    g = dict(graph)
    g['pieces'] = [p for p in graph['pieces'] if p['id'] in FLAPS + ('skirt',)]
    scene = dict(spec=G.spec, A=G.A, hull=hull, L=float(L), ppl=float(ppl), win=dict(bodyqa.WIN), names=names,
                 flap_idx={n: names.index(n) for n in FLAPS}, views=views, drawn=drawn, masks=masks, graph=g,
                 flaps={n: next(x for x in G.spec['garments'] if x['name'] == n) for n in FLAPS})
    path = os.path.join(out, 'flap_scene.pkl')
    pickle.dump(scene, open(path, 'wb'), protocol=pickle.HIGHEST_PROTOCOL)
    log('scene %s (%.0f s)' % (path, time.time() - t))
    return path


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd')
    ap.add_argument('--spec', default='charkit/spec/clawd.json')
    ap.add_argument('--out', default=OUT)
    a = ap.parse_args()
    if a.cmd == 'scene':
        build_scene(a.spec, a.out)
