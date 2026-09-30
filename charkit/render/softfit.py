"""Template fits by gradients through the soft silhouettes (charkit.render.softras; docs/workstreams/softras.md): the
pilot harness, behind no default. The chain is template knobs -> vertices (the template's builder, its Jacobian by
finite differences with a limiter, since no builder here has an analytic one) -> per-view soft silhouettes (softras,
analytic d/dvertices) -> a soft IoU against the design's per-view masks; L-BFGS-B (scipy) over it. The pilot is the
overskirt flap template (garments.flap_template, the skirt's fit G), against its coordinate descent on the hard
silhouettes from the same start.

    python -m charkit.render.softfit scene [--spec SPEC] [--out DIR]      # the flap's frozen scene (once, ~minutes)
    python -m charkit.render.softfit fit cd|grad [--start g|far] [--s 0.5] [--anneal 2,1] [--sweeps 12|0]
                                                                          # a fit from a named start -> OUT/fit_*.json
    python -m charkit.render.softfit scan [--start g]                      # the objective along each knob -> scan.json
    python -m charkit.render.softfit page                                  # the review page, OUT/index.html

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
        fmemo, forig = {}, gm.flap_template

        def flap_memo(A, spec, hull):                       # flap_mirror builds the left flap again: the last few kept
            k = json.dumps({a: b for a, b in spec.items() if a != '_spec'}, sort_keys=True, default=str)
            if k not in fmemo:
                if len(fmemo) > 4:
                    fmemo.pop(next(iter(fmemo)))
                fmemo[k] = forig(A, spec, hull)
            return fmemo[k]
        gm.flap_template = flap_memo

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
                sil[side] = self.sr.silhouette(V, T, self.views[ov], s=s, occ=np.minimum(st, z[other]), soft=soft)
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
    halvings). sweeps: at most this many sweeps (fit.py's 12, a move or a halving each), None to convergence.
    -> (x, J, history)."""
    t0 = time.time()
    steps = np.array([p[2] for p in F.params], float)
    lo = np.array([p[3] for p in F.params], float); hi = np.array([p[4] for p in F.params], float)
    x = np.clip(np.array(x0, float), lo, hi)
    best, ious = F.hard(x)
    hist = [dict(t=time.time() - t0, evals=F.n['hard'], J=best)]
    kf = [p[0] for p in F.params].index('first')
    sweep = -1
    while sweeps is None or sweep + 1 < sweeps:
        sweep += 1
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


def run_fit(method, start='g', out=OUT, s=0.5, anneal=(), sweeps=12, log=print):
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
        x, J, hist = coordinate_descent(F, x0, log=log, sweeps=sweeps)
    else:
        x, J, hist = gradient_fit(F, x0, s=s, log=log, anneal=anneal)
    wall = time.time() - t
    n = dict(F.n)
    J1, i1 = F.hard(x)
    rec = dict(method=method, start=start, s=s, anneal=list(anneal), sweeps=sweeps if method == 'cd' else None,
               wall=wall, counts=n,
               knobs=[p[0] for p in F.params], x0=x0.tolist(), x=x.tolist(), J0=J0, J=J1, iou0=i0, iou=i1,
               pieces0=F.pieces(x0), pieces=F.pieces(x), history=hist, spec=F.spec_at(x))
    tag = method + ('_s%g' % s if method != 'cd' else ('' if sweeps else '_full')) + ('_anneal' if anneal else '')
    p = os.path.join(out, 'fit_%s_%s.json' % (tag, start))
    json.dump(rec, open(p, 'w'), indent=1, default=float)
    log('%s from %s: J %.4f -> %.4f in %.1f s; %s -> %s' % (method, start, J0, J1, wall, n, p))
    return rec


# ------------------------------------------------------------------------------------------------------------ evidence
def scan(F, x, span=1.0, n=41, s=0.5, log=print):
    """each knob swept +-span steps round x at n points, the other knobs held: the hard J (the QA's pixels) and the soft
    J; and at x the chain's gradient against central differences of the hard J at 0.01, 0.1 and 1 step and of the
    soft J at 0.01 step (all per step). -> {knob: {t (steps), hard, soft, grad {chain, hard_0.01, hard_0.1, hard_1,
    soft_0.01}, hard_tv, soft_tv (the curves' total variation), hard_flat (the share of neighbouring points the hard
    J doesn't change between)}}."""
    _, g = F.value_and_grad(x, s=s)
    out = {}
    for k, (name, _, step, lo, hi) in enumerate(F.params):
        ts = np.linspace(-span, span, n)
        hard, soft = [], []
        for t_ in ts:
            y = x.copy(); y[k] += t_ * step
            geo = F.build(y)
            hard.append(F.render(geo, soft=False)[0]); soft.append(F.render(geo, s=s)[0])
        gr = {'chain': float(g[k])}
        for h in (0.01, 0.1, 1.0):
            yp, ym = x.copy(), x.copy(); yp[k] += h * step; ym[k] -= h * step
            gr['hard_%g' % h] = (F.hard(yp)[0] - F.hard(ym)[0]) / (2 * h)
        yp, ym = x.copy(), x.copy(); yp[k] += 0.01 * step; ym[k] -= 0.01 * step
        gr['soft_0.01'] = (F.render(F.build(yp), s=s)[0] - F.render(F.build(ym), s=s)[0]) / 0.02
        hard, soft = np.array(hard), np.array(soft)
        out[name] = dict(t=ts.tolist(), hard=hard.tolist(), soft=soft.tolist(), grad=gr,
                         hard_tv=float(np.abs(np.diff(hard)).sum()), soft_tv=float(np.abs(np.diff(soft)).sum()),
                         hard_flat=float((np.abs(np.diff(hard)) < 1e-12).mean()))
        log('  scan %-7s chain %+.4f  hard fd 0.01/0.1/1 step %+.4f %+.4f %+.4f  soft fd %+.4f  flat %.2f' % (
            name, gr['chain'], gr['hard_0.01'], gr['hard_0.1'], gr['hard_1'], gr['soft_0.01'], out[name]['hard_flat']))
    return out


def silhouettes(F, x):
    """each view's visible flaps at x (hard, the QA's): {view: bool (H, W)} over both flaps, profile and profile_R apart
    (each shows its near flap), and the drawn ones the same way."""
    geo = F.build(x)
    ours, drawn = {}, {}
    for name, view, side, ov, m, w in F.terms:
        z = F._depths(geo, ov)
        other = 'R' if side == 'L' else 'L'
        V, T = geo[side]
        S_ = F.sr.silhouette(V, T, F.views[ov], s=0.5, occ=np.minimum(F.S['views'][ov]['depth'], z[other]))
        ours[ov] = ours.get(ov, False) | S_.full(S_.hard)
        drawn[ov] = drawn.get(ov, False) | m
    return ours, drawn


def fit_label(r):
    if r['method'] == 'cd':
        return 'cd (12 sweeps)' if r.get('sweeps') else 'cd (to convergence)'
    return 'l-bfgs s%g%s' % (r['s'], ' anneal ' + ','.join('%g' % a for a in r['anneal']) if r['anneal'] else '')


PAGE_CSS = ('body{font:13px system-ui;margin:16px;background:#f4f4f6;color:#222}.row{display:flex;flex-wrap:wrap;'
            'gap:6px}figure{margin:0}figure img{width:250px;border:1px solid #ccc}figcaption{font-size:11px}'
            'table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #ccc;padding:2px 5px;text-align:right}')


def page(out=OUT, open_it=True):
    """the review page (OUT/index.html): the fits' table, J against wall time, the objective along each knob (scan.json),
    and per start and fit each view's drawn flaps against ours (drawn only blue, ours only red, both dark). -> path."""
    import glob, html
    from PIL import Image
    recs = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(out, 'fit_*.json')))]
    if not recs:
        raise SystemExit('no fits in %s' % out)
    F = Flaps(os.path.join(out, 'flap_scene.pkl'))
    img = os.path.join(out, 'page')
    os.makedirs(img, exist_ok=True)
    ppl, top = F.S['ppl'], F.S['win']['top']
    r0, r1, c0, c1 = int((top + 1.2) * ppl), int((top + 3.6) * ppl), 150, 830
    order = ('front', 'three_quarter', 'profile', 'profile_R', 'back')

    def panel(o, d, path):
        rgb = np.full(o.shape + (3,), 235, np.uint8)
        rgb[d & ~o] = (120, 170, 255); rgb[o & ~d] = (235, 90, 80); rgb[o & d] = (70, 60, 120)
        Image.fromarray(rgb[r0:r1, c0:c1]).save(path)

    rows = []
    for start in sorted(set(r['start'] for r in recs)):
        rs = [r for r in recs if r['start'] == start]
        states = [('start', rs[0]['x0'], rs[0]['iou0'], rs[0]['J0'], rs[0]['pieces0'], None)] + \
                 [(fit_label(r), r['x'], r['iou'], r['J'], r['pieces'], r) for r in rs]
        for label, x, iou, J, pc, r in states:
            o, d = silhouettes(F, np.array(x))
            cells = []
            for v in order:
                fn = '%s_%s_%s.png' % (start, ''.join(c if c.isalnum() else '_' for c in label), v)
                panel(o[v], d[v], os.path.join(img, fn))
                vv = 'profile' if v == 'profile_R' else v
                ks = [k for k in iou if k.startswith('flap_%s_iou_' % vv) and
                      (v != 'profile_R' or k.endswith('_R')) and (v != 'profile' or k.endswith('_L'))]
                cells.append('<figure><img src="page/%s"><figcaption>%s: %s</figcaption></figure>' % (
                    fn, v, ' '.join('%s %.3f' % (k[-1], iou[k]) for k in sorted(ks))))
            info = 'J (QA pixels) %.4f' % J
            if r is not None:
                info += ' &middot; %.1f s wall &middot; %d evaluations &middot; %d builds' % (
                    r['wall'], r['counts']['hard'] + r['counts']['grad'], r['counts']['builds'])
            pcs = ' &middot; '.join('%s %.3f %s %s' % (p.replace('overskirt_panel_', 'piece_overskirt_panel_'), v[0], v[1],
                                                      ' '.join('%s %.3f' % kv for kv in sorted(v[2].items())))
                                    for p, v in sorted(pc.items()))
            rows.append('<h3>start %s: %s</h3><p>%s<br>%s</p><div class="row">%s</div>' % (
                html.escape(start), html.escape(label), info, pcs, ''.join(cells)))
    th = ('<tr><th>start</th><th>fit</th><th>wall s</th><th>evaluations</th><th>builds</th><th>J start</th>'
          '<th>J end</th>' + ''.join('<th>%s</th>' % t[0].replace('flap_', '').replace('_iou', '') for t in F.terms) +
          '<th>piece L</th><th>piece R</th></tr>')
    tr = []
    for r in recs:
        tr.append('<tr><td>%s</td><td>%s</td><td>%.1f</td><td>%d</td><td>%d</td><td>%.4f</td><td><b>%.4f</b></td>%s'
                  '<td>%.3f %s</td><td>%.3f %s</td></tr>' % (
                      r['start'], fit_label(r), r['wall'], r['counts']['hard'] + r['counts']['grad'],
                      r['counts']['builds'], r['J0'], r['J'], ''.join('<td>%.3f</td>' % r['iou'][t[0]] for t in F.terms),
                      r['pieces']['overskirt_panel_L'][0], r['pieces']['overskirt_panel_L'][1],
                      r['pieces']['overskirt_panel_R'][0], r['pieces']['overskirt_panel_R'][1]))
    W_, H_ = 700, 280
    tmax = max(max(h['t'] for h in r['history']) for r in recs) or 1.0
    Js = [h.get('J', h.get('J_soft')) for r in recs for h in r['history']]
    jlo, jhi = min(Js), max(Js)
    cols = ['#d55e00', '#e69f00', '#0072b2', '#009e73', '#cc79a7', '#56b4e9', '#999999', '#000000', '#8c564b', '#17becf']
    lines = []
    for i, r in enumerate(recs):
        c = cols[i % len(cols)]
        pts = ' '.join('%.1f,%.1f' % (40 + (W_ - 260) * h['t'] / tmax,
                                      10 + (H_ - 40) * (1 - (h.get('J', h.get('J_soft')) - jlo) / max(1e-9, jhi - jlo)))
                       for h in r['history'])
        lines.append('<polyline fill="none" stroke="%s" stroke-width="2" points="%s"></polyline><text x="%d" y="%d" '
                     'fill="%s" font-size="11">%s: %s</text>' % (c, pts, W_ - 210, 20 + 14 * i, c, r['start'],
                                                                 html.escape(fit_label(r))))
    svg = ('<svg width="%d" height="%d" style="background:#fff"><text x="4" y="14" font-size="11">%.2f</text>'
           '<text x="4" y="%d" font-size="11">%.2f</text><text x="%d" y="%d" font-size="11">%.0f s</text>%s</svg>' %
           (W_, H_, jhi, H_ - 30, jlo, W_ - 260, H_ - 12, tmax, ''.join(lines)))
    sc = ''
    sp = os.path.join(out, 'scan.json')
    if os.path.exists(sp):
        blocks = []
        for name, d in json.load(open(sp)).items():
            ys = d['hard'] + d['soft']
            lo_, hi_ = min(ys), max(ys)

            def f(t, y):
                return '%.1f,%.1f' % (10 + 200 * (t + 1) / 2, 10 + 100 * (1 - (y - lo_) / max(1e-9, hi_ - lo_)))
            blocks.append('<figure><svg width="220" height="120" style="background:#fff"><polyline fill="none" '
                          'stroke="#d55e00" points="%s"/><polyline fill="none" stroke="#0072b2" points="%s"/></svg>'
                          '<figcaption>%s (+-1 step): hard (orange) flat on %.0f%% of steps; soft (blue).<br>dJ/dstep: '
                          'chain %+.4f; hard fd at 0.01 / 0.1 / 1 step %+.4f / %+.4f / %+.4f</figcaption></figure>' % (
                              ' '.join(f(t, y) for t, y in zip(d['t'], d['hard'])),
                              ' '.join(f(t, y) for t, y in zip(d['t'], d['soft'])), name, 100 * d['hard_flat'],
                              d['grad']['chain'], d['grad']['hard_0.01'], d['grad']['hard_0.1'], d['grad']['hard_1']))
        sc = '<h2>The objective along each knob, round fit G\'s start</h2><div class="row">%s</div>' % ''.join(blocks)
    doc = ('<!doctype html><meta charset="utf-8"><title>Softras flap pilot</title><style>%s</style>'
           '<h1>Differentiable silhouettes: the flap template fitted by gradients against coordinate descent</h1>'
           '<p>J = sum over the flap\'s QA IoUs (flap_VIEW_iou_SIDE) of VW[view] (1 - IoU); VW back 1, profile 1, front '
           '0.7, three-quarter 0.4 (fit G\'s). J and every IoU are read on the QA\'s hard pixels; piece_* is qa3d\'s graded '
           'piece IoU (bodymeasure.piece_shapes) over the views. Starts: g = fit G\'s own start (skirt_scratch/t8.json), '
           'far = every knob 2-6 steps off it. Panels: rows z -1.2 .. -3.6 L; drawn only blue, ours only red, both dark. '
           'Data: charkit/out/softras/fit_*.json, scan.json.</p><table>%s%s</table><h2>J against wall time</h2>%s%s'
           '<h2>The fits, view by view</h2>%s' % (PAGE_CSS, th, ''.join(tr), svg, sc, ''.join(rows)))
    path = os.path.join(out, 'index.html')
    open(path, 'w').write(doc)
    if open_it:
        os.system('open "%s"' % path)
    return path


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
    ap.add_argument('--sweeps', type=int, default=12, help='cd: at most this many sweeps (0: to convergence)')
    a = ap.parse_args()
    if a.cmd == 'scene':
        build_scene(a.spec, a.out)
    elif a.cmd == 'fit':
        run_fit(a.method, a.start, a.out, a.s, tuple(float(v) for v in a.anneal.split(',') if v), a.sweeps or None)
    elif a.cmd == 'scan':
        F = Flaps(os.path.join(a.out, 'flap_scene.pkl'))
        json.dump(scan(F, F.start(a.start), s=a.s), open(os.path.join(a.out, 'scan.json'), 'w'), default=float)
    elif a.cmd == 'page':
        print(page(a.out))
