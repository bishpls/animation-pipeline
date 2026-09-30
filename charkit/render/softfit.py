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


# ------------------------------------------------------------------------------------------------------------ the knobs
# fit G's knobs (skirt_scratch/fit.py PARAMS: path in the left flap's spec, step, bounds), less `band`: the band's
# material and rows only, not the silhouette. Each fit works in steps from its start, as fitkit does.
PARAMS = [
    ('e1o', ('edges', 4, 1), 2.0, 110, 132), ('e1i', ('edges', 4, 2), 2.0, 150, 164),
    ('standm', ('stand', 1, 1), 0.02, -0.02, 0.15), ('stand1', ('stand', 2, 1), 0.02, -0.02, 0.2),
    ('first', ('tail', 'first'), 0.02, 0.05, 0.5), ('rise', ('tail', 'rise'), 0.02, 0.05, 0.25),
    ('droop', ('droop',), 0.1, -0.5, 0.9), ('out', ('out',), 0.1, -0.4, 0.6), ('twist', ('twist',), 0.1, -0.3, 0.8),
]
STARTS = {   # fit G's own start (skirt_scratch/t8.json), and one far from it (every knob moved 2-6 steps)
    'g': dict(e1o=123.0, e1i=159.0, standm=-0.02, stand1=0.1, first=0.16, rise=0.15, droop=0.4, out=0.4, twist=0.1),
    'far': dict(e1o=117.0, e1i=153.0, standm=0.08, stand1=0.02, first=0.3, rise=0.08, droop=0.0, out=0.0, twist=0.4),
}


def getp(s, p):
    for k in p:
        s = s[k]
    return s


def putp(s, p, v):
    for k in p[:-1]:
        s = s[k]
    s[p[-1]] = v


class Flaps:
    """the flap template on the frozen scene: build(x) (the knobs' values) -> both flaps' meshes; hard(x) the QA's
    flap IoUs (skirtqa's flap_{view}_iou_{side}: the flap's visible pixels against the drawn flap, profile R from the
    other side, mirrored onto the drawn near flap) and the objective J = sum over them of VW[view] (1 - IoU);
    soft(x, s) the same on soft silhouettes, with dJ / dx through the vertices. Counts every build and render."""

    def __init__(self, path=os.path.join(OUT, 'flap_scene.pkl'), params=PARAMS):
        from charkit import garments as gm
        from charkit.render import softras
        self.gm, self.sr = gm, softras
        S = pickle.load(open(path, 'rb'))
        self.S, self.params = S, params
        self.spec, self.A, self.hull = S['spec'], S['A'], S['hull']
        self.base = copy.deepcopy(S['flaps']['overskirt_panel_L'])
        self.base.setdefault('out', 0.0)
        self.right = S['flaps']['overskirt_panel_R']
        self.views = {v: softras.SheetView(d['az'], d['origin'], S['L'], 1.0 / S['ppl'], S['win'])
                      for v, d in S['views'].items()}
        self.terms = []                                     # (name, view drawn in, side, view we're seen in, mask, w)
        for view in VIEWS:
            for side in 'LR':
                ov = 'profile_R' if (view == 'profile' and side == 'R') else view
                dp = 'overskirt_panel_L' if (view == 'profile' and side == 'R') else 'overskirt_panel_' + side
                m = S['drawn'][view][dp]
                if m.sum() < 200:                            # skirtqa.MIN_PX
                    continue
                self.terms.append(('flap_%s_iou_%s' % (view, side), view, side, ov,
                                   m[:, ::-1] if ov == 'profile_R' else m, VW[view]))
        self.n = dict(builds=0, hard=0, soft=0, grad=0, build_s=0.0, render_s=0.0)
        memo, orig = {}, gm.skirt_hull

        def skirt_memo(A, spec, hull):                      # the skirt under the flaps doesn't change in these fits
            k = json.dumps({a: b for a, b in spec.items() if a != '_spec'}, sort_keys=True, default=str)
            if k not in memo:
                memo[k] = orig(A, spec, hull)
            return memo[k]
        gm.skirt_hull = skirt_memo

    # ---- knobs
    def x_of(self, spec_l):
        return np.array([float(getp(spec_l, p)) for _, p, _, _, _ in self.params])

    def spec_at(self, x):
        s = copy.deepcopy(self.base)
        for (_, p, _, _, _), v in zip(self.params, x):
            putp(s, p, float(v))
        return s

    def start(self, name):
        st = STARTS[name]
        return np.array([st[k] for k, _, _, _, _ in self.params], float)

    def build(self, x):
        """-> {'L': (V, tris), 'R': (V, tris)} (quads split as the QA splits them)."""
        t = time.time()
        sl = self.spec_at(x)
        whole = copy.deepcopy(self.spec)
        whole['garments'] = [sl if g['name'] == 'overskirt_panel_L' else g for g in whole['garments']]
        out = {}
        for side, sp in (('L', sl), ('R', self.right)):
            G = self.gm.flap(self.A, dict(sp, _spec=whole), self.hull)
            out[side] = (np.asarray(G['verts'], float), self.sr.triangles(G['faces']))
        self.n['builds'] += 1
        self.n['build_s'] += time.time() - t
        return out

    # ---- the silhouettes
    def _depths(self, geo, ov):
        """each flap's own hard depth in view ov (whole view, inf off it)."""
        from charkit.geom.raster import _raster
        vw = self.views[ov]
        out = {}
        for side, (V, T) in geo.items():
            P2, d = vw.project(V)
            y0, y1, x0, x1 = self.sr.crop(P2, vw.shape, 2)
            zb, _, _, _ = _raster(np.ascontiguousarray(P2 - [x0, y0]), np.ascontiguousarray(d), T, x1 - x0, y1 - y0)
            z = np.full(vw.shape, np.inf)
            z[y0:y1, x0:x1] = zb
            out[side] = z
        return out

    def render(self, geo, s=0.5, grad=False, soft=True):
        """-> (J, {term: iou}, {side: dJ/dV} or None). soft False: the hard silhouettes (the QA's) for J."""
        t = time.time()
        J, ious = 0.0, {}
        dV = {side: np.zeros_like(V) for side, (V, _) in geo.items()} if grad else None
        need = {}
        for name, view, side, ov, m, w in self.terms:
            need.setdefault(ov, []).append((name, side, m, w))
        for ov, ts in need.items():
            z = self._depths(geo, ov)
            st = self.S['views'][ov]['depth']
            sil = {}
            for side in set(t_[1] for t_ in ts):
                other = 'R' if side == 'L' else 'L'
                V, T = geo[side]
                sil[side] = self.sr.silhouette(V, T, self.views[ov], s=s, occ=np.minimum(st, z[other]))
            for name, side, m, w in ts:
                S_ = sil[side]
                iou, g = S_.iou(m, None if soft else S_.hard.astype(float))
                ious[name] = iou
                J += w * (1 - iou)
                if grad:
                    dV[side] += S_.backward(-w * g)
        self.n['soft' if soft else 'hard'] += 1
        self.n['render_s'] += time.time() - t
        return J, ious, dV

    def hard(self, x):
        J, ious, _ = self.render(self.build(x), soft=False)
        return J, ious

    def value_and_grad(self, x, s=0.5, h=0.01, info=None):
        """the soft J at x and dJ/dx: dJ/dV from the silhouettes, dV/dx by central differences of the builder at h steps,
        a vertex whose two one-sided differences disagree (the builder re-sampled its rows or columns there: a
        topology event) taking the smaller; a knob whose builds change the faces on both sides by differences of the
        soft J itself."""
        geo = self.build(x)
        J, ious, dV = self.render(geo, s=s, grad=True)
        self.n['grad'] += 1
        g = np.zeros(len(x))
        how = []
        for k, (name, _, step, _, _) in enumerate(self.params):
            e = np.zeros(len(x)); e[k] = h * step
            gp, gm_ = self.build(x + e), self.build(x - e)
            tot, ok = 0.0, True
            for side, (V0, T0) in geo.items():
                Vp, Tp = gp[side]; Vm, Tm = gm_[side]
                sp = Vp.shape == V0.shape and np.array_equal(Tp, T0)
                sm = Vm.shape == V0.shape and np.array_equal(Tm, T0)
                if sp and sm:
                    dp, dm = (Vp - V0) / e[k], (V0 - Vm) / e[k]
                    np_, nm = np.linalg.norm(dp, axis=1), np.linalg.norm(dm, axis=1)
                    jump = np.linalg.norm(dp - dm, axis=1) > 0.2 * (np_ + nm) + 1e-9
                    d = np.where(jump[:, None], np.where((np_ <= nm)[:, None], dp, dm), 0.5 * (dp + dm))
                elif sp or sm:
                    d = (Vp - V0) / e[k] if sp else (V0 - Vm) / e[k]
                else:
                    ok = False
                    break
                tot += float((dV[side] * d).sum())
            if ok:
                g[k] = tot * step; how.append('chain')        # (d/d step units)
            else:
                Jp = self.render(gp, s=s)[0]; Jm = self.render(gm_, s=s)[0]
                g[k] = (Jp - Jm) / (2 * h); how.append('loss')
        if info is not None:
            info['how'] = how
            info['ious'] = ious
        return J, g

    def pieces(self, x):
        """the piece IoUs qa3d grades (bodymeasure.piece_shapes on the side-split labels, qa3d.grade_pieces) for the
        flaps: {piece: [value, status, views {view: iou_tol}]}."""
        from charkit import bodymeasure, qa3d
        from charkit.geom.raster import window_zbuffer
        geo = self.build(x)
        idx = self.S['flap_idx']
        labels = {}
        for v in VIEWS:
            d = self.S['views'][v]
            vw = self.views[v]
            meshes = []
            for side in 'LR':
                V, T = geo[side]
                i = idx['overskirt_panel_' + side]
                meshes.append((V, T, np.where(V[T].mean(1)[:, 0] >= 0, i, i + 1000)))
            df, lf = window_zbuffer(meshes, vw.az, vw.origin, vw.L, vw.pix, vw.win)
            lab = d['lab_pc'].copy()
            m = (lf >= 0) & (df < d['depth'])
            lab[m] = lf[m]
            labels[v] = lab
        PS = bodymeasure.piece_shapes(labels, self.S['names'], self.S['masks'], self.S['graph'], self.spec,
                                      self.S['ppl'])
        PC = qa3d.grade_pieces(PS)
        return {p: [PC[p]['value'], PC[p]['status'], {v: round(r['iou_tol'], 4) for v, r in PS[p]['views'].items()}]
                for p in FLAPS if p in PC}


# ------------------------------------------------------------------------------------------------------------ the fits
def coordinate_descent(F, x0, log=print, sweeps=12):
    """the skirt's fit (skirt_scratch/fit.py) on the hard J: each knob a step up then down, the first move that lowers
    J taken and the sweep begun again; a sweep with no move halves every step, until `first`'s is under 0.004 (three
    halvings). -> (x, J, history)."""
    t0 = time.time()
    steps = np.array([p[2] for p in F.params], float)
    lo = np.array([p[3] for p in F.params], float); hi = np.array([p[4] for p in F.params], float)
    x = np.clip(np.array(x0, float), lo, hi)
    best, ious = F.hard(x)
    hist = [dict(t=time.time() - t0, evals=F.n['hard'], J=best)]
    kf = [p[0] for p in F.params].index('first')
    for sweep in range(sweeps):
        improved = False
        for k in range(len(x)):
            for sgn in (1, -1):
                y = x.copy(); y[k] = np.clip(y[k] + sgn * steps[k], lo[k], hi[k])
                if y[k] == x[k]:
                    continue
                J, io = F.hard(y)
                if J < best - 1e-6:
                    best, x, ious, improved = J, y, io, True
                    log('  cd sweep %d %s=%.4g J %.4f (%d evaluations, %.1f s)' % (sweep, F.params[k][0], y[k], J,
                                                                                F.n['hard'], time.time() - t0))
                    hist.append(dict(t=time.time() - t0, evals=F.n['hard'], J=best))
                    break
            if improved:
                break
        if not improved:
            steps = steps / 2
            log('  cd sweep %d: no move, steps halved' % sweep)
            if steps[kf] < 0.004:
                break
    return x, best, hist


def gradient_fit(F, x0, s=0.5, log=print, maxiter=60, anneal=()):
    """L-BFGS-B (scipy) on the soft J with its analytic-chain gradient, in steps from x0 inside the knobs' bounds.
    anneal: softnesses run first, each from the last's result. -> (x, hard J there, history)."""
    from scipy.optimize import minimize
    t0 = time.time()
    steps = np.array([p[2] for p in F.params], float)
    lo = np.array([p[3] for p in F.params], float); hi = np.array([p[4] for p in F.params], float)
    x0 = np.clip(np.array(x0, float), lo, hi)
    hist = []
    x = x0.copy()
    for s_ in tuple(anneal) + (s,):
        def fun(u):
            info = {}
            J, g = F.value_and_grad(x0 + u * steps, s=s_, info=info)
            hist.append(dict(t=time.time() - t0, evals=F.n['grad'], builds=F.n['builds'], J_soft=J, s=s_,
                             how=info['how']))
            return J, g
        r = minimize(fun, (x - x0) / steps, jac=True, method='L-BFGS-B',
                     bounds=list(zip((lo - x0) / steps, (hi - x0) / steps)),
                     options=dict(maxiter=maxiter, ftol=1e-7, gtol=1e-6))
        x = x0 + r.x * steps
        Jh, _ = F.hard(x)
        hist[-1]['J_hard'] = Jh
        log('  l-bfgs s %.2f: J soft %.4f, hard %.4f, %d iterations, %d evaluations, %.1f s (%s)' % (
            s_, r.fun, Jh, r.nit, r.nfev, time.time() - t0, r.message))
    return x, F.hard(x)[0], hist


def run_fit(method, start='g', out=OUT, s=0.5, anneal=(), log=print):
    """one fit from a named start, its record written to OUT/fit_METHOD_START.json."""
    F = Flaps(os.path.join(out, 'flap_scene.pkl'))
    x0 = F.start(start)
    F.hard(x0)                                              # (warm: numba's compile, the skirt's memo)
    F.value_and_grad(x0, s=s)
    F.n = dict(builds=0, hard=0, soft=0, grad=0, build_s=0.0, render_s=0.0)
    J0, i0 = F.hard(x0)
    F.n = dict(builds=0, hard=0, soft=0, grad=0, build_s=0.0, render_s=0.0)
    t = time.time()
    if method == 'cd':
        x, J, hist = coordinate_descent(F, x0, log=log)
    else:
        x, J, hist = gradient_fit(F, x0, s=s, log=log, anneal=anneal)
    wall = time.time() - t
    n = dict(F.n)
    J1, i1 = F.hard(x)
    rec = dict(method=method, start=start, s=s, anneal=list(anneal), wall=wall, counts=n,
               knobs=[p[0] for p in F.params], x0=x0.tolist(), x=x.tolist(), J0=J0, J=J1, iou0=i0, iou=i1,
               pieces0=F.pieces(x0), pieces=F.pieces(x), history=hist, spec=F.spec_at(x))
    tag = method + ('_s%g' % s if method != 'cd' else '') + ('_anneal' if anneal else '')
    p = os.path.join(out, 'fit_%s_%s.json' % (tag, start))
    json.dump(rec, open(p, 'w'), indent=1, default=float)
    log('%s from %s: J %.4f -> %.4f in %.1f s; %s -> %s' % (method, start, J0, J1, wall, n, p))
    return rec


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd')
    ap.add_argument('method', nargs='?')
    ap.add_argument('--spec', default='charkit/spec/clawd.json')
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--start', default='g')
    ap.add_argument('--s', type=float, default=0.5)
    ap.add_argument('--anneal', default='')
    a = ap.parse_args()
    if a.cmd == 'scene':
        build_scene(a.spec, a.out)
    elif a.cmd == 'fit':
        run_fit(a.method, a.start, a.out, a.s, tuple(float(v) for v in a.anneal.split(',') if v))
