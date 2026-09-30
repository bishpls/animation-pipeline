"""Template fits by gradients through the soft silhouettes (charkit.render.softras; docs/workstreams/softras.md): the
pilot harness, behind no default. The chain is template knobs -> vertices (the template's builder, its Jacobian by
finite differences with a limiter, since no builder here has an analytic one) -> per-view soft silhouettes (softras,
analytic d/dvertices) -> a soft IoU against the design's per-view masks; L-BFGS-B (scipy) over it. The pilot is the
overskirt flap template (garments.flap_template, the skirt's fit G), against its coordinate descent on the hard
silhouettes from the same start.

    python -m charkit.render.softfit scene [--spec SPEC] [--out DIR]      # the flap's frozen scene (once, ~minutes)
    python -m charkit.render.softfit fit cd|grad [--start g|far] [--s 0.5] [--anneal 2,1] [--sweeps 12|0]
                                                                          # a fit from a named start -> OUT/fit_*.json
    python -m charkit.render.softfit fitkit fd|grad [--start g|far]       # fitkit.optimise on the same IoUs, its
                                                                          # finite differences or its gradient path
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
# Michael's call A for the flaps: the front, back and profile win; the three-quarter's drawn tails (the only flap it
# draws) disagree with them, so its terms weigh 0: measured and reported, not fitted
VW_A = {'back': 1.0, 'profile': 1.0, 'three_quarter': 0.0, 'front': 0.7}
WEIGHTS = {'g': VW, 'a': VW_A}
LAMBDA = 1.0            # the distance term: J + LAMBDA * sum over terms of w * chamfer (L)


# ------------------------------------------------------------------------------------------------------------ the scene
def build_scene(spec_path='charkit/spec/clawd.json', out=OUT, log=print, pieces=FLAPS, name='flap'):
    """a template's frozen scene (see the module): the scene without `pieces`, their drawings (the flaps:
    skirtqa.drawn_pieces; anything else: the outfit masks, as piece_shapes reads them) -> OUT/NAME_scene.pkl."""
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
    static = [i for i in vis if names[i] not in pieces]
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
    if name == 'flap':
        P = sq.drawn_pieces(S.design, masks, marks, ppl)
        drawn = {v: {f: P[v]['full'][f] for f in FLAPS} for v in P}
    else:
        H, W = views['front']['depth'].shape
        drawn = {v: {f: masks.get('%s__%s' % (v, f), np.zeros((H, W), bool)) for f in pieces} for v in VIEWS}
    g = dict(graph)
    g['pieces'] = [p for p in graph['pieces'] if p['id'] in tuple(pieces) + (('skirt',) if name == 'flap' else ())]
    scene = dict(spec=G.spec, A=G.A, hull=hull, L=float(L), ppl=float(ppl), win=dict(bodyqa.WIN), names=names,
                 piece_idx={n: names.index(n) for n in pieces}, views=views, drawn=drawn, masks=masks, graph=g,
                 specs={n: next(x for x in G.spec['garments'] if x['name'] == n) for n in pieces})
    path = os.path.join(out, '%s_scene.pkl' % name)
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

    PARAMS, STARTS, NAMES, ORDER = PARAMS, STARTS, {'L': FLAPS[0], 'R': FLAPS[1]}, \
        ('front', 'three_quarter', 'profile', 'profile_R', 'back')

    def __init__(self, path=os.path.join(OUT, 'flap_scene.pkl'), params=None, weights='g', dist=0.0, occlusion='hard'):
        from charkit import garments as gm
        from charkit.render import softras
        self.gm, self.sr = gm, softras
        S = pickle.load(open(path, 'rb'))
        self.S, self.params = S, params or self.PARAMS
        self.spec, self.A, self.hull = S['spec'], S['A'], S['hull']
        self.specs = S.get('specs') or S['flaps']
        self.base = copy.deepcopy(self.specs[self.NAMES['L']])
        self.right = self.specs[self.NAMES['R']]
        self.views = {v: softras.SheetView(d['az'], d['origin'], S['L'], 1.0 / S['ppl'], S['win'])
                      for v, d in S['views'].items()}
        self.weights, self.dist, self._outlines, self.last_chamfer = weights, float(dist), {}, {}
        self.occlusion = occlusion                          # 'soft': the depth-order edges differentiated too
        self.terms = self.make_terms(S, WEIGHTS.get(weights, VW))   # (name, view drawn, side, view seen in, mask, w)
        self.n = dict(builds=0, hard=0, soft=0, grad=0, build_s=0.0, render_s=0.0)
        self.setup(gm)

    def make_terms(self, S, vw):
        self.base.setdefault('out', 0.0)
        out = []
        for view in VIEWS:
            for side in 'LR':
                ov = 'profile_R' if (view == 'profile' and side == 'R') else view
                dp = 'overskirt_panel_L' if (view == 'profile' and side == 'R') else 'overskirt_panel_' + side
                m = S['drawn'][view][dp]
                if m.sum() < 200:                            # skirtqa.MIN_PX
                    continue
                out.append(('flap_%s_iou_%s' % (view, side), view, side, ov, m[:, ::-1] if ov == 'profile_R' else m,
                            vw[view]))
        return out

    def outline(self, name):
        if name not in self._outlines:
            self._outlines[name] = self.sr.Outline(next(t[4] for t in self.terms if t[0] == name))
        return self._outlines[name]

    def setup(self, gm):
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
        st = self.STARTS[name]
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

    def render(self, geo, s=0.5, grad=False, soft=True, per_term=None, chamfer=False):
        """-> (J, {term: iou}, {side: dJ/dV} or None). soft False: the hard silhouettes (the QA's) for J. per_term (a
        dict, with grad): filled with {term: {side: d iou / dV}}. With self.dist (soft), J adds dist * w * each term's
        outline chamfer (softras.chamfer, in L), and its gradient; chamfer: measure the chamfers (last_chamfer) even
        without the term."""
        t = time.time()
        J, ious, cham = 0.0, {}, {}
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
                sil[side] = self.sr.silhouette(V, T, self.views[ov], s=s, occ=np.minimum(st, z[other]), soft=soft,
                                               **(self.occ_args(ov, z[other]) if soft else {}))
            for name, side, m, w in ts:
                S_ = sil[side]
                iou, g = S_.iou(m, None if soft else S_.hard.astype(float))
                ious[name] = iou
                J += w * (1 - iou)
                if grad and (w or per_term is not None):
                    d_ = S_.backward(g)
                    dV[side] -= w * d_
                    if per_term is not None:
                        per_term[name] = {side: d_}
                if soft and (self.dist or chamfer):
                    val, back = self.sr.chamfer(S_, self.outline(name))
                    if val is not None:
                        pix = self.views[ov].pix
                        cham[name] = val * pix
                        J += self.dist * w * val * pix
                        if grad and self.dist and w:
                            dV[side] += back(self.dist * w * pix)
        if soft and (self.dist or chamfer):
            self.last_chamfer = cham
        self.n['soft' if soft else 'hard'] += 1
        self.n['render_s'] += time.time() - t
        return J, ious, dV

    def occ_args(self, ov, z_other):
        """softras.silhouette's occlusion settings in view ov: soft, the occluder's surfaces labelled (the frozen scene's
        objects; the other piece, -2, where it is nearer: its depth isn't differentiated, it isn't this piece's knob
        path's occluder anywhere in these pilots, docs/workstreams/softras.md round 4)."""
        if self.occlusion != 'soft':
            return {}
        d = self.S['views'][ov]

        def lab(y0, y1, x0, x1):                            # (on the silhouette's crop only)
            out = d['lab'][y0:y1, x0:x1].copy()
            out[z_other[y0:y1, x0:x1] < d['depth'][y0:y1, x0:x1]] = -2
            return out
        return dict(occlusion='soft', occ_lab=lab)

    def measure(self, x):
        """the QA's J (hard IoUs, this fit's weights), the IoUs, and the outline chamfers (L) with their weighted sum."""
        geo = self.build(x)
        J, ious, _ = self.render(geo, soft=False)
        self.render(geo, s=0.5, chamfer=True)
        ch = dict(self.last_chamfer)
        wt = {t[0]: t[5] for t in self.terms}
        return J, ious, ch, float(sum(wt[k] * v for k, v in ch.items()))

    def hard(self, x):
        J, ious, _ = self.render(self.build(x), soft=False)
        return J, ious

    def value_and_grad(self, x, s=0.5, h=0.01, info=None, per_term=False):
        """the soft J at x and dJ/dx: dJ/dV from the silhouettes, dV/dx by central differences of the builder at h steps,
        a vertex whose two one-sided differences disagree (the builder re-sampled its rows or columns there: a
        topology event) taking the smaller; a knob whose builds change the faces on both sides by differences of the
        soft J itself. per_term: info['terms'] = {term: d iou / d step} as well."""
        geo = self.build(x)
        pt = {} if per_term else None
        J, ious, dV = self.render(geo, s=s, grad=True, per_term=pt)
        gt = {t: np.zeros(len(x)) for t in (pt or {})}
        self.n['grad'] += 1
        g = np.zeros(len(x))
        how = []
        for k, (name, _, step, _, _) in enumerate(self.params):
            e = np.zeros(len(x)); e[k] = h * step
            gp, gm_ = self.build(x + e), self.build(x - e)
            tot, ok, ds = 0.0, True, {}
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
                ds[side] = d
            if ok:
                g[k] = tot * step; how.append('chain')        # (d/d step units)
                for t, dd in (pt or {}).items():
                    gt[t][k] = step * sum(float((dv * ds[sd]).sum()) for sd, dv in dd.items())
            else:
                Jp, ip, _ = self.render(gp, s=s); Jm, im, _ = self.render(gm_, s=s)
                g[k] = (Jp - Jm) / (2 * h); how.append('loss')
                for t in gt:
                    gt[t][k] = (ip[t] - im[t]) / (2 * h)
        if info is not None:
            info['how'] = how
            info['ious'] = ious
            info['terms'] = gt
        return J, g

    def pieces(self, x):
        """the piece IoUs qa3d grades (bodymeasure.piece_shapes on the side-split labels, qa3d.grade_pieces) for the
        flaps: {piece: [value, status, views {view: iou_tol}]}."""
        from charkit import bodymeasure, qa3d
        from charkit.geom.raster import window_zbuffer
        geo = self.build(x)
        idx = self.S.get('piece_idx') or self.S['flap_idx']
        labels = {}
        for v in VIEWS:
            d = self.S['views'][v]
            vw = self.views[v]
            meshes = []
            for side in 'LR':
                V, T = geo[side]
                i = idx[self.NAMES[side]]
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
                for p in self.NAMES.values() if p in PC}


# ------------------------------------------------------------------------------------------------------------ sleeves
# the puff sleeve (garments.puff): its knot table's four extents (columns 1-4: out and forward, in and back of the arm's
# frame) each scaled, a taper across the stations (x (1 + taper (t - mid) / span)), the cap's height and the section's
# roundness. The stations themselves stay (they set the rows: no topology change).
SLEEVE_PARAMS = [('sxp', 1, 0.05, 0.6, 1.6), ('syp', 2, 0.05, 0.6, 1.6), ('sxm', 3, 0.05, 0.6, 1.6),
                 ('sym', 4, 0.05, 0.6, 1.6), ('taper', 'taper', 0.05, -0.6, 0.6), ('cap', ('cap',), 0.02, 0.0, 0.3),
                 ('round', ('round',), 0.2, 1.5, 4.0)]
SLEEVE_STARTS = {   # the spec's own sleeve (its knots as fitted), and one far from it (every knob 3-5 steps off)
    'g': dict(sxp=1.0, syp=1.0, sxm=1.0, sym=1.0, taper=0.0, cap=0.12, round=2.3),
    'far': dict(sxp=1.2, syp=0.8, sxm=0.8, sym=1.2, taper=0.25, cap=0.2, round=3.1),
}


class Sleeves(Flaps):
    """the puff sleeves on their frozen scene (build_scene(pieces=sleeves, name='sleeve')): both sides' piece IoUs in
    every view whose outfit mask shows 200 px or more (sleeve_{view}_iou_{side}, the outfit masks as piece_shapes reads
    them), every view weighing 1; the right sleeve mirrors the left's knots (garments.puff's `mirror`)."""
    PARAMS, STARTS, NAMES, ORDER = SLEEVE_PARAMS, SLEEVE_STARTS, {'L': 'sleeve_L', 'R': 'sleeve_R'}, VIEWS

    def make_terms(self, S, vw):
        out = []
        for view in VIEWS:
            for side in 'LR':
                m = S['drawn'][view][self.NAMES[side]]
                if m.sum() >= 200:
                    out.append(('sleeve_%s_iou_%s' % (view, side), view, side, view, m, 1.0))
        return out

    def setup(self, gm):
        pass

    def spec_at(self, x):
        v = dict(zip([p[0] for p in self.params], x))
        s = copy.deepcopy(self.base)
        K = np.asarray(s['profile'], float)
        span = max(1e-9, K[-1, 0] - K[0, 0])
        f = 1 + v['taper'] * (K[:, 0] - 0.5 * (K[0, 0] + K[-1, 0])) / span
        for c, k in ((1, 'sxp'), (2, 'syp'), (3, 'sxm'), (4, 'sym')):
            K[:, c] = K[:, c] * v[k] * f
        s['profile'] = K.round(6).tolist()
        s['cap'], s['round'] = float(v['cap']), float(v['round'])
        return s

    def build(self, x):
        t = time.time()
        sl = self.spec_at(x)
        whole = copy.deepcopy(self.spec)
        whole['garments'] = [sl if g['name'] == self.NAMES['L'] else g for g in whole['garments']]
        out = {}
        for side, sp in (('L', sl), ('R', self.right)):
            G = self.gm.puff(self.A, dict(sp, _spec=whole), self.hull)
            out[side] = (np.asarray(G['verts'], float), self.sr.triangles(G['faces']))
        self.n['builds'] += 1
        self.n['build_s'] += time.time() - t
        return out


TEMPLATES = {'flap': (Flaps, FLAPS), 'sleeve': (Sleeves, ('sleeve_L', 'sleeve_R'))}


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
    halvings = 0
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
            halvings += 1
            if halvings >= 3:                                # (fit.py: `first`'s step under 0.004, from 0.02)
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


def run_fit(method, start='g', out=OUT, s=0.5, anneal=(), sweeps=12, log=print, template='flap', weights='g',
            dist=0.0, occlusion='hard'):
    """one fit from a named start, its record written to OUT/fit_[TEMPLATE_]METHOD..._START.json. weights: the view
    weights ('g' fit G's, 'a' Michael's call A); dist: the gradient fit's distance term (LAMBDA, per L of chamfer)."""
    F = TEMPLATES[template][0](os.path.join(out, '%s_scene.pkl' % template), weights=weights,
                               dist=dist if method != 'cd' else 0.0, occlusion=occlusion if method != 'cd' else 'hard')
    x0 = F.start(start)
    F.hard(x0)                                              # (warm: numba's compile, the skirt's memo)
    F.value_and_grad(x0, s=s)
    F.n = dict(builds=0, hard=0, soft=0, grad=0, build_s=0.0, render_s=0.0)
    J0, i0, c0, C0 = F.measure(x0)
    F.n = dict(builds=0, hard=0, soft=0, grad=0, build_s=0.0, render_s=0.0)
    t = time.time()
    if method == 'cd':
        x, J, hist = coordinate_descent(F, x0, log=log, sweeps=sweeps)
    else:
        x, J, hist = gradient_fit(F, x0, s=s, log=log, anneal=anneal)
    wall = time.time() - t
    n = dict(F.n)
    J1, i1, c1, C1 = F.measure(x)
    rec = dict(method=method, start=start, s=s, anneal=list(anneal), sweeps=sweeps if method == 'cd' else None,
               template=template, weights=weights, dist=F.dist, occlusion=F.occlusion, chamfer0=c0, chamfer=c1, C0=C0,
               C=C1,
               wall=wall, counts=n,
               knobs=[p[0] for p in F.params], x0=x0.tolist(), x=x.tolist(), J0=J0, J=J1, iou0=i0, iou=i1,
               pieces0=F.pieces(x0), pieces=F.pieces(x), history=hist, spec=F.spec_at(x))
    tag = method + ('_s%g' % s if method != 'cd' else ('' if sweeps else '_full')) + ('_anneal' if anneal else '')
    tag = ('' if template == 'flap' else template + '_') + tag + ('_d%g' % F.dist if F.dist else '') + \
        ('_w%s' % weights if weights != 'g' else '') + ('_occ' if F.occlusion == 'soft' else '')
    p = os.path.join(out, 'fit_%s_%s.json' % (tag, start))
    json.dump(rec, open(p, 'w'), indent=1, default=float)
    log('%s %s from %s: J %.4f -> %.4f, chamfer %.4f -> %.4f L, in %.1f s; %s -> %s' % (
        template, method, start, J0, J1, C0, C1, wall, n, p))
    return rec


# ------------------------------------------------------------------------------------------------------------ fitkit
class FlapChecks:
    """the flap's IoUs as a fitkit evaluator (fitkit's worker protocol), on the knobs spec['flap'][knob]:
    checks(spec, group, fine): fine the QA's hard IoUs, else the soft ones (the smooth reading, as facefit's jitter is
    for the face); jacobian(spec, group, names): the soft IoUs and d IoU / d knob through the chain (the gradient
    path, fitkit.optimise(gradient=True))."""

    def __init__(self, path=os.path.join(OUT, 'flap_scene.pkl'), s=0.5):
        self.F, self.s = Flaps(path), s

    def x(self, spec):
        f = spec.get('flap', {})
        return np.array([float(f[k]) for k, _, _, _, _ in self.F.params])

    def checks(self, spec, group, fine=False):
        geo = self.F.build(self.x(spec))
        _, ious, _ = self.F.render(geo, s=self.s, soft=not fine)
        return {k: {'value': v, 'status': 'PASS'} for k, v in ious.items()}

    def jacobian(self, spec, group, names):
        info = {}
        self.F.value_and_grad(self.x(spec), s=self.s, info=info, per_term=True)
        col = {k: i for i, (k, _, _, _, _) in enumerate(self.F.params)}
        steps = {k: st for k, _, st, _, _ in self.F.params}
        D = {t: {n: float(g[col[n]]) / steps[n] for n in names} for t, g in info['terms'].items()}   # per knob unit
        return {k: {'value': v, 'status': 'PASS'} for k, v in info['ious'].items()}, D


def run_fitkit(start='g', gradient=False, out=OUT, s=0.5, log=print):
    """fitkit.optimise on the flap's IoUs (each term 'ratio' at tol 0.1: (IoU - 1) / 0.1, weighted by fit G's view
    weight; no protection: every IoU may trade), finite-difference Jacobians or the gradient path, from a named start.
    -> its record, OUT/fitkit_{fd|grad}_START.json."""
    from charkit import fitkit
    ev = FlapChecks(os.path.join(out, 'flap_scene.pkl'), s)
    F = ev.F
    knobs = [fitkit.Knob(k, ('flap', k), None, st, (lo, hi), 'flap') for k, _, st, lo, hi in F.params]
    x0 = F.start(start)
    for k, v in zip(knobs, x0):
        k.default = float(v)                             # (the regulariser pulls toward the start)
    terms = [fitkit.Term(name, None, 'ratio', 0.1, name, 'sheet', view, 'flap', weight=w)
             for name, view, side, ov, m, w in F.terms]
    spec = {'flap': {k.name: float(v) for k, v in zip(knobs, x0)}}
    pool = fitkit.Pool('charkit.render.softfit:FlapChecks', (os.path.join(out, 'flap_scene.pkl'), s), workers=1)
    pool.map([(spec, 'flap', True), (spec, 'flap', False)])  # (warm)
    t = time.time()
    fitted, info = fitkit.optimise(pool, spec, knobs, terms, 'flap', protect=False, gradient=gradient,
                                   log=lambda *a: None)
    wall = time.time() - t
    x = np.array([fitted['flap'][k.name] for k in knobs])
    J0, i0 = F.hard(x0)
    J1, i1 = F.hard(x)
    rec = dict(method='fitkit ' + ('gradient' if gradient else 'fd'), start=start, s=s, wall=wall,
               evaluations=info['evaluations'], phases=info['phases'], knobs=[k.name for k in knobs], x0=x0.tolist(),
               x=x.tolist(), J0=J0, J=J1, iou0=i0, iou=i1, pieces0=F.pieces(x0), pieces=F.pieces(x),
               history=[dict(t=None, J=h['cost']) for h in info['history']])
    p = os.path.join(out, 'fitkit_%s_%s.json' % ('grad' if gradient else 'fd', start))
    json.dump(rec, open(p, 'w'), indent=1, default=float)
    log('fitkit %s from %s: J %.4f -> %.4f in %.1f s, %d evaluations %s -> %s' % (
        'gradient' if gradient else 'fd', start, J0, J1, wall, info['evaluations'],
        {k: v['evaluations'] for k, v in info['phases'].items()}, p))
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


def boundary_kinds(S, occ, lab, z_other, static):
    """where one term's visible outline runs (hard, the QA's pixels): 4-neighbour pairs of a visible pixel and one that
    isn't, split into free (the piece doesn't cover the other pixel: its own contour), depth-order (the occluder covers
    both on one surface, continuous in depth: where the piece passes into or behind it), occluder edge (the occluder's
    own outline over the piece: fixed while only the piece moves) and other piece. -> {kind: pairs}."""
    y0, y1, x0, x1 = S.box
    cov, vis = S.cov_hard, S.hard
    so, lb, zo = static[y0:y1, x0:x1], lab[y0:y1, x0:x1], z_other[y0:y1, x0:x1]
    H, W = cov.shape
    out = dict(free=0, depth_order=0, occluder_edge=0, other_piece=0)
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        ys, xs = np.nonzero(vis)
        qy, qx = ys + dy, xs + dx
        ok = (qy >= 0) & (qy < H) & (qx >= 0) & (qx < W)
        ys, xs, qy, qx = ys[ok], xs[ok], qy[ok], qx[ok]
        k = ~vis[qy, qx]
        ys, xs, qy, qx = ys[k], xs[k], qy[k], qx[k]
        free = ~cov[qy, qx]
        out['free'] += int(free.sum())
        ys, xs, qy, qx = ys[~free], xs[~free], qy[~free], qx[~free]
        oth = zo[qy, qx] <= so[qy, qx]
        out['other_piece'] += int(oth.sum())
        ys, xs, qy, qx = ys[~oth], xs[~oth], qy[~oth], qx[~oth]
        same = np.isfinite(so[ys, xs]) & (lb[ys, xs] == lb[qy, qx])
        cont = same & (np.abs(so[ys, xs] - so[qy, qx]) < 4 * np.maximum(np.abs(S.zbuf[ys, xs] - S.zbuf[qy, qx]),
                                                                          1e-3 * S.view.px_world() * 100))
        out['depth_order'] += int(cont.sum()); out['occluder_edge'] += int((~cont).sum())
    return out


def agreement(S):
    """a soft silhouette against the hard one it approximates (the QA's z-buffered visible pixels): the IoU of
    cov >= 0.5 with it, the mean symmetric distance (px) between their outlines, the area bias (soft sum / hard sum -
    1) and the soft-occlusion band's pixels."""
    from scipy import ndimage
    h, c = S.hard, S.cov >= 0.5
    iou = float((h & c).sum() / max(1, (h | c).sum()))
    bh, bc = h & ~ndimage.binary_erosion(h), c & ~ndimage.binary_erosion(c)
    if bh.any() and bc.any():
        ed = 0.5 * (ndimage.distance_transform_edt(~bh)[bc].mean() + ndimage.distance_transform_edt(~bc)[bh].mean())
    else:
        ed = float('nan')
    band = int(np.isfinite(S.d_occ).sum()) if getattr(S, 'd_occ', None) is not None else 0
    return dict(iou=iou, edge_px=float(ed), bias=float(S.cov.sum() / max(1, h.sum()) - 1), occ_band=band)


def occ_measure(F, x, ss=(0.25, 0.5, 1.0), log=print, steps=(0.01,), hard_steps=(0.1, 0.3, 1.0)):
    """soft occlusion measured before it is built on (round 4): at x, per term, where the visible outline runs
    (boundary_kinds), each softness's agreement with the hard z-buffered masks, hard and soft occlusion
    (agreement), and the soft IoU against the hard one; then per knob the chain's dJ/dstep, hard and soft occlusion,
    against differences of the soft J (each mode, 0.01 step) and of the hard J (0.1, 0.3, 1 step). -> a record."""
    geo = F.build(x)
    rec = dict(x=list(map(float, x)), terms={}, grad={})
    mode0 = F.occlusion
    for name, view, side, ov, m, w in F.terms:
        z = F._depths(geo, ov)
        other = 'R' if side == 'L' else 'L'
        d = F.S['views'][ov]
        V, T = geo[side]
        occ = np.minimum(d['depth'], z[other])
        S0 = F.sr.silhouette(V, T, F.views[ov], s=0.5, occ=occ)
        r = dict(kinds=boundary_kinds(S0, occ, d['lab'], z[other], d['depth']), hard_iou=float(S0.iou(m, S0.hard.astype(float))[0]))
        for s_ in ss:
            for mode in ('hard', 'soft'):
                F.occlusion = mode
                S_ = F.sr.silhouette(V, T, F.views[ov], s=s_, occ=occ, **F.occ_args(ov, z[other]))
                a = agreement(S_)
                a['soft_iou'] = float(S_.iou(m)[0])
                r['s%g_%s' % (s_, mode)] = a
        rec['terms'][name] = r
        k = r['kinds']; tot = max(1, sum(k.values()))
        log('  %-26s outline %4d pairs: free %3.0f%%, depth-order %3.0f%%, occluder edge %3.0f%%, other piece %3.0f%%;'
            ' s 0.5 hard/soft occlusion: IoU %.4f / %.4f, edge %.3f / %.3f px, bias %+.4f / %+.4f, soft IoU - hard'
            ' %+.4f / %+.4f' % (name, tot, *(100 * k[q] / tot for q in ('free', 'depth_order', 'occluder_edge',
                                                                        'other_piece')),
                                r['s0.5_hard']['iou'], r['s0.5_soft']['iou'], r['s0.5_hard']['edge_px'],
                                r['s0.5_soft']['edge_px'], r['s0.5_hard']['bias'], r['s0.5_soft']['bias'],
                                r['s0.5_hard']['soft_iou'] - r['hard_iou'], r['s0.5_soft']['soft_iou'] - r['hard_iou']))
    for mode in ('hard', 'soft'):
        F.occlusion = mode
        rec['grad']['chain_' + mode] = F.value_and_grad(x, s=0.5)[1].tolist()
        for h in steps:
            g = []
            for k, p in enumerate(F.params):
                yp, ym = x.copy(), x.copy(); yp[k] += h * p[2]; ym[k] -= h * p[2]
                g.append((F.render(F.build(yp), s=0.5)[0] - F.render(F.build(ym), s=0.5)[0]) / (2 * h))
            rec['grad']['soft_fd%g_%s' % (h, mode)] = g
    F.occlusion = mode0
    for h in hard_steps:
        g = []
        for k, p in enumerate(F.params):
            yp, ym = x.copy(), x.copy(); yp[k] += h * p[2]; ym[k] -= h * p[2]
            g.append((F.hard(yp)[0] - F.hard(ym)[0]) / (2 * h))
        rec['grad']['hard_fd%g' % h] = g
    G = rec['grad']
    log('  %-7s %9s %9s | %9s %9s | %9s %9s %9s | ratio chain/own fd hard, soft' % (
        'knob', 'chain hd', 'chain sf', 'fd sf hd', 'fd sf sf', 'hard .1', 'hard .3', 'hard 1'))
    for k, p in enumerate(F.params):
        rh = G['chain_hard'][k] / G['soft_fd0.01_hard'][k] if G['soft_fd0.01_hard'][k] else float('nan')
        rs = G['chain_soft'][k] / G['soft_fd0.01_soft'][k] if G['soft_fd0.01_soft'][k] else float('nan')
        log('  %-7s %+9.4f %+9.4f | %+9.4f %+9.4f | %+9.4f %+9.4f %+9.4f | %.2fx %.2fx' % (
            p[0], G['chain_hard'][k], G['chain_soft'][k], G['soft_fd0.01_hard'][k], G['soft_fd0.01_soft'][k],
            G['hard_fd0.1'][k], G['hard_fd0.3'][k], G['hard_fd1'][k], rh, rs))
    return rec


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
    w = ' [weights %s]' % r['weights'] if r.get('weights', 'g') != 'g' else ''
    if r['method'] == 'cd':
        return ('cd (12 sweeps)' if r.get('sweeps') else 'cd (to convergence)') + w
    return 'l-bfgs s%g%s%s%s%s' % (r['s'], ' anneal ' + ','.join('%g' % a for a in r['anneal']) if r['anneal'] else '',
                                   ' + chamfer x%g' % r['dist'] if r.get('dist') else '',
                                   ' + soft occlusion' if r.get('occlusion') == 'soft' else '', w)


PAGE_CSS = ('body{font:13px system-ui;margin:16px;background:#f4f4f6;color:#222}.row{display:flex;flex-wrap:wrap;'
            'gap:6px}figure{margin:0}figure img{width:250px;border:1px solid #ccc}figcaption{font-size:11px}'
            'table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #ccc;padding:2px 5px;text-align:right}')


def page(out=OUT, open_it=True, template='flap'):
    """the review page (OUT/index.html): the fits' table, J against wall time, the objective along each knob (scan.json),
    and per start and fit each view's drawn flaps against ours (drawn only blue, ours only red, both dark). -> path."""
    import glob, html
    from PIL import Image
    recs = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(out, 'fit_*.json')))]
    recs = [r for r in recs if r.get('template', 'flap') == template]
    if not recs:
        raise SystemExit('no fits in %s' % out)
    F = TEMPLATES[template][0](os.path.join(out, '%s_scene.pkl' % template), weights=recs[0].get('weights', 'g'))
    img = os.path.join(out, 'page')
    os.makedirs(img, exist_ok=True)
    ppl, top = F.S['ppl'], F.S['win']['top']
    allm = np.logical_or.reduce([t[4] for t in F.terms])
    rr, cc = np.nonzero(allm.any(1))[0], np.nonzero(allm.any(0))[0]
    r0, r1 = max(0, rr[0] - 60), min(allm.shape[0], rr[-1] + 60)
    c0, c1 = max(0, cc[0] - 60), min(allm.shape[1], cc[-1] + 60)
    order = F.ORDER

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
                fn = '%s_%s_%s_%s.png' % (template, start, ''.join(c if c.isalnum() else '_' for c in label), v)
                panel(o[v], d[v], os.path.join(img, fn))
                ks = [t[0] for t in F.terms if t[3] == v]
                cells.append('<figure><img src="page/%s"><figcaption>%s: IoU %s</figcaption></figure>' % (
                    fn, v, ' '.join('%s %.3f' % (k[-1], iou[k]) for k in sorted(ks) if k in iou)))
            info = 'J (QA pixels) %.4f' % J + (' &middot; chamfer %.4f L' % r['C'] if r and 'C' in r else '')
            if r is not None:
                info += ' &middot; %.1f s wall &middot; %d evaluations &middot; %d builds' % (
                    r['wall'], r['counts']['hard'] + r['counts']['grad'], r['counts']['builds'])
            pcs = ' &middot; '.join('%s %.3f %s %s' % (p.replace('overskirt_panel_', 'piece_overskirt_panel_'), v[0], v[1],
                                                      ' '.join('%s %.3f' % kv for kv in sorted(v[2].items())))
                                    for p, v in sorted(pc.items()))
            rows.append('<h3>start %s: %s</h3><p>%s<br>%s</p><div class="row">%s</div>' % (
                html.escape(start), html.escape(label), info, pcs, ''.join(cells)))
    th = ('<tr><th>start</th><th>fit</th><th>wall s</th><th>evaluations</th><th>builds</th><th>J start</th>'
          '<th>J end</th><th>chamfer L (start, end)</th>' + ''.join('<th>%s</th>' % t[0].replace('flap_', '').replace(
              '_iou', '') for t in F.terms) +
          '<th>piece L</th><th>piece R</th></tr>')
    tr = []
    for r in recs:
        tr.append('<tr><td>%s</td><td>%s</td><td>%.1f</td><td>%d</td><td>%d</td><td>%.4f</td><td><b>%.4f</b></td><td>%s</td>%s'
                  '<td>%.3f %s</td><td>%.3f %s</td></tr>' % (
                      r['start'], fit_label(r), r['wall'], r['counts']['hard'] + r['counts']['grad'],
                      r['counts']['builds'], r['J0'], r['J'],
                      '%.4f, %.4f' % (r['C0'], r['C']) if 'C' in r else '-',
                      ''.join('<td>%.3f</td>' % r['iou'][t[0]] for t in F.terms),
                      r['pieces'][F.NAMES['L']][0], r['pieces'][F.NAMES['L']][1],
                      r['pieces'][F.NAMES['R']][0], r['pieces'][F.NAMES['R']][1]))
    for p_ in sorted(glob.glob(os.path.join(out, 'fitkit_*.json'))) if template == 'flap' else ():
        r = json.load(open(p_))
        tr.append('<tr><td>%s</td><td>%s</td><td>%.1f</td><td>%d</td><td>-</td><td>%.4f</td><td><b>%.4f</b></td><td>-</td>%s'
                  '<td>%.3f %s</td><td>%.3f %s</td></tr>' % (
                      r['start'], r['method'], r['wall'], r['evaluations'], r['J0'], r['J'],
                      ''.join('<td>%.3f</td>' % r['iou'][t[0]] for t in F.terms),
                      r['pieces'][F.NAMES['L']][0], r['pieces'][F.NAMES['L']][1],
                      r['pieces'][F.NAMES['R']][0], r['pieces'][F.NAMES['R']][1]))
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
    path = os.path.join(out, 'index.html' if template == 'flap' else 'index_%s.html' % template)
    open(path, 'w').write(doc)
    if open_it:
        os.system('open "%s"' % path)
    return path


def occ_page(out=OUT, summary='', open_it=True, templates=(('sleeve', 'g'), ('flap', 'a'))):
    """the soft-occlusion review (OUT/occ.html): the summary box, then per template the measurement (occ_*_g.json:
    where each term's outline runs, soft against hard occlusion's agreement with the QA's z-buffered masks, the chain
    against differences per knob) and the fits (fit_*.json: J, evaluations, wall time, the piece IoUs in every view),
    linking each template's view-by-view page (page()). -> path."""
    import glob, html
    css = PAGE_CSS + ('.box{background:#fff;border:2px solid #0072b2;padding:8px 14px;margin:0 0 14px;max-width:1100px}'
                      '.box h2{margin:4px 0}td.l,th.l{text-align:left}.good{background:#dff3e4}.bad{background:#fbe3e0}')
    parts = ['<div class="box">%s</div>' % summary]
    for tmpl, w in templates:
        mp = os.path.join(out, 'occ_%s_g.json' % tmpl)
        if not os.path.exists(mp):
            continue
        M = json.load(open(mp))
        F = TEMPLATES[tmpl][0](os.path.join(out, '%s_scene.pkl' % tmpl), weights=w)
        wt = {t[0]: t[5] for t in F.terms}
        rows = []
        for name, r in M['terms'].items():
            k = r['kinds']; tot = max(1, sum(k.values()))
            h, sft = r['s0.5_hard'], r['s0.5_soft']
            rows.append('<tr><td class="l">%s</td><td>%g</td><td>%d</td>%s<td>%.4f / %.4f</td><td>%.3f / %.3f</td>'
                        '<td>%+.2f%% / %+.2f%%</td><td>%d</td><td>%+.4f / %+.4f</td></tr>' % (
                            name, wt.get(name, 0), tot, ''.join('<td>%.0f%%</td>' % (100 * k[q] / tot) for q in (
                                'free', 'depth_order', 'occluder_edge', 'other_piece')),
                            h['iou'], sft['iou'], h['edge_px'], sft['edge_px'], 100 * h['bias'], 100 * sft['bias'],
                            sft['occ_band'], h['soft_iou'] - r['hard_iou'], sft['soft_iou'] - r['hard_iou']))
        G = M['grad']
        grows = []
        for i, p in enumerate(F.params):
            rh = G['chain_hard'][i] / G['soft_fd0.01_hard'][i] if G['soft_fd0.01_hard'][i] else float('nan')
            rs = G['chain_soft'][i] / G['soft_fd0.01_soft'][i] if G['soft_fd0.01_soft'][i] else float('nan')
            cls = lambda r_: 'good' if abs(r_ - 1) <= 0.1 else 'bad'
            grows.append('<tr><td class="l">%s</td><td>%+.4f</td><td>%+.4f</td><td class="%s">%.2fx</td><td>%+.4f</td>'
                         '<td>%+.4f</td><td class="%s">%.2fx</td><td>%+.4f</td><td>%+.4f</td><td>%+.4f</td></tr>' % (
                             p[0], G['chain_hard'][i], G['soft_fd0.01_hard'][i], cls(rh), rh, G['chain_soft'][i],
                             G['soft_fd0.01_soft'][i], cls(rs), rs, G['hard_fd0.1'][i], G['hard_fd0.3'][i],
                             G['hard_fd1'][i]))
        recs = [json.load(open(q)) for q in sorted(glob.glob(os.path.join(out, 'fit_*.json')))]
        recs = [r for r in recs if r.get('template', 'flap') == tmpl]
        frows = []
        for r in sorted(recs, key=lambda r: (r['start'], r['method'] != 'cd', r.get('occlusion', 'hard'), r['s'])):
            pc = '<br>'.join('%s %.3f %s: %s' % (pn, v[0], v[1], ' '.join('%s %.3f' % kv for kv in sorted(v[2].items())))
                             for pn, v in sorted(r['pieces'].items()))
            pc0 = {pn: v[0] for pn, v in r['pieces0'].items()}
            frows.append('<tr><td>%s</td><td class="l">%s</td><td>%.1f</td><td>%d</td><td>%d</td><td>%.4f</td>'
                         '<td><b>%.4f</b></td><td class="l" style="font-size:11px">%s<br>(start %s)</td></tr>' % (
                             r['start'], html.escape(fit_label(r)), r['wall'], r['counts']['hard'] + r['counts']['grad'],
                             r['counts']['builds'], r['J0'], r['J'], pc,
                             ', '.join('%s %.3f' % kv for kv in sorted(pc0.items()))))
        link = 'index.html' if tmpl == 'flap' else 'index_%s.html' % tmpl
        parts.append(
            '<h2>%s</h2><h3>1. The measurement at the start (g): where the outline runs, and soft occlusion against the '
            'QA\'s hard z-buffered masks (s 0.5; hard / soft occlusion)</h3><table><tr><th class="l">term</th><th>weight'
            '</th><th>outline pairs</th><th>free</th><th>depth-order</th><th>occluder edge</th><th>other piece</th>'
            '<th>IoU(cov &ge; 0.5, hard)</th><th>outline distance px</th><th>area bias</th><th>soft-occlusion band px'
            '</th><th>soft IoU - hard IoU</th></tr>%s</table>'
            '<h3>2. dJ/dstep at g: the chain against differences of the soft J (0.01 step), hard and soft occlusion, and '
            'of the QA\'s hard J (0.1, 0.3, 1 step)</h3><table><tr><th class="l">knob</th><th>chain, hard occl.</th>'
            '<th>soft J fd</th><th>ratio</th><th>chain, soft occl.</th><th>soft J fd</th><th>ratio</th><th>hard J 0.1'
            '</th><th>hard J 0.3</th><th>hard J 1</th></tr>%s</table>'
            '<h3>3. The fits (J on the QA\'s hard pixels; piece IoUs in every view beside each)</h3><table><tr><th>start'
            '</th><th class="l">fit</th><th>wall s</th><th>evaluations</th><th>builds</th><th>J start</th><th>J end</th>'
            '<th class="l">piece IoU (qa3d) and per view</th></tr>%s</table><p>View by view (drawn only blue, ours only '
            'red, both dark): <a href="%s">%s</a>. Data: %s, fit_*.json.</p>' % (
                tmpl, ''.join(rows), ''.join(grows), ''.join(frows), link, link, os.path.basename(mp)))
    doc = ('<!doctype html><meta charset="utf-8"><title>Soft occlusion review</title><style>%s</style>'
           '<h1>Soft occlusion: the edge where a piece passes behind the body, differentiated</h1>%s' % (css, ''.join(parts)))
    path = os.path.join(out, 'occ.html')
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
    ap.add_argument('--template', default='flap', choices=sorted(TEMPLATES))
    ap.add_argument('--weights', default='g', choices=sorted(WEIGHTS))
    ap.add_argument('--dist', type=float, default=0.0, help='the distance term (LAMBDA %g: per L of chamfer)' % LAMBDA)
    ap.add_argument('--occ', default='hard', choices=('hard', 'soft'), help='the gradient fit: soft occlusion')
    a = ap.parse_args()
    if a.cmd == 'scene':
        build_scene(a.spec, a.out, pieces=TEMPLATES[a.template][1], name=a.template)
    elif a.cmd == 'fit':
        run_fit(a.method, a.start, a.out, a.s, tuple(float(v) for v in a.anneal.split(',') if v), a.sweeps or None,
                template=a.template, weights=a.weights, dist=a.dist, occlusion=a.occ)
    elif a.cmd == 'fitkit':
        run_fitkit(a.start, a.method == 'grad', a.out, a.s)
    elif a.cmd == 'scan':
        F = Flaps(os.path.join(a.out, 'flap_scene.pkl'))
        json.dump(scan(F, F.start(a.start), s=a.s), open(os.path.join(a.out, 'scan.json'), 'w'), default=float)
    elif a.cmd == 'occ':
        F = TEMPLATES[a.template][0](os.path.join(a.out, '%s_scene.pkl' % a.template), weights=a.weights)
        x = F.start(a.start) if not a.method else np.array(json.load(open(a.method))['x'])
        r = occ_measure(F, x)
        tag = a.start if not a.method else os.path.basename(a.method)[:-5]
        json.dump(r, open(os.path.join(a.out, 'occ_%s_%s.json' % (a.template, tag)), 'w'), default=float)
    elif a.cmd == 'page':
        print(page(a.out, template=a.template))
