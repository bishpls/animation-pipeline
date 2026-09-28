"""Per-piece fitting of the body, garments and hair (docs/CHARKIT.md §4). The model sheet's body checks and the generated
shape's silhouettes choose the body's proportions and rest pose, each garment piece's cut and the hair's extent, measured
by the fast evaluator (charkit.bodyeval): a couple of seconds an evaluation instead of a Blender build.

    python -m charkit bodyfit SPEC [--out DIR] [--pieces body,skirt,boots,sleeves,hair] [--palette] [--budget N]
                                   [--write-spec]

  1. resolve the spec as `build` does, and measure the start: every shape_*, body_* and palette_* check, as the QA does;
  2. piece by piece (the body, then the skirt, the boots, the sleeves and the hair), least squares over that piece's
     knobs against all its terms at once: the sheet's four views and the generated shape's six, so a fix in one view
     that breaks another costs. Each term is weighted by the manifest's authority map: full weight where its reference
     is the authority for its measure, a quarter otherwise. Each knob is pulled toward its template default;
  3. --palette: the colour knobs set to the sheet's palette (charkit.paletteqa's tones), each class's knobs solved in
     CIEDE2000;
  4. write DIR/NAME.bodyfit.json (the resolved spec with the fitted knobs) and DIR/bodyfit_report.json and .md: every
     check before and after, the knobs per piece (and which ended at a bound), and what still fails and why.
     --write-spec writes the fitted knobs back into SPEC.

The terms follow charkit.fitkit's conventions (tool/fit): a residual in tolerances, a hinge beyond it and a pull to the
template. Until fitkit is on the integration branch, `optimise` here is a small trust-region least-squares fit with a
pattern-search polish.
"""
import copy, json, os, time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HINGE = 2.0                     # beyond its tolerance a residual counts again, this many times (fitkit's)
REG = 0.3                       # the pull toward the template default: REG * (x - default) / range (fitkit's)
LOSS_SCALE = 3.0                # soft-L1 above this many tolerances
AUTHORITY = {'body_silhouette': 'sheet', 'hair_silhouette': 'sheet', 'hair_shape': 'trellis', 'palette': 'sheet'}
VIEWS = ('front', 'three_quarter', 'profile', 'back')


# ------------------------------------------------------------------------------------------------------------ knobs
class Knob:
    """a knob the fit owns: its name, the spec paths it sets (a left/right pair moves together), the template default, a
    step (the finite difference and the unit of the search), bounds and the piece it belongs to. fitkit.Knob's fields,
    with bodyeval's dotted paths (list items by name) so garment pieces can be addressed."""

    def __init__(self, name, paths, default, step, bounds, group):
        self.name, self.paths, self.default, self.step, self.bounds, self.group = name, list(paths), default, step, tuple(bounds), group

    def get(self, spec):
        from .bodyeval import get_knob
        v = get_knob(spec, self.paths[0], self.default)
        return float(self.default if v is None else v)

    def put(self, spec, value):
        from .bodyeval import set_knob
        for p in self.paths:
            set_knob(spec, p, round(float(value), 5))

    def at_bound(self, x, eps=1e-6):
        lo, hi = self.bounds
        return 'lower' if x <= lo + eps * (hi - lo) else 'upper' if x >= hi - eps * (hi - lo) else None

    def declare(self):
        return {'paths': self.paths, 'default': self.default, 'step': self.step, 'bounds': list(self.bounds), 'group': self.group}


def _pairs(spec, kind):
    """a kind's garment pieces, left/right pairs together: [(name, [piece names])]."""
    names = [g['name'] for g in spec.get('garments') or [] if g['kind'] == kind]
    out, seen = [], set()
    for n in names:
        if n in seen:
            continue
        base = n[:-2] if n.endswith(('_L', '_R')) else None
        mates = [m for m in names if base and m[:-2] == base and m.endswith(('_L', '_R'))] if base else [n]
        seen.update(mates)
        out.append((base or n, mates))
    return out


def knobs(spec):
    """the knobs the body fit owns for a spec, by piece. Defaults are the templates' (body.DEFAULT_BODY, the garment
    builders', hair.shape's); steps and bounds are bodysens's. The neck's width and length are left to the face fit."""
    from .body import DEFAULT_BODY
    from .bodysens import GARMENT, HAIR_SHAPE, PROPORTION
    K = [Knob('body.heads_tall', ['body.heads_tall'], DEFAULT_BODY['heads_tall'], 0.1, (5.0, 7.5), 'body')]
    for k in ('leg', 'shin', 'hip', 'leg_slim', 'arm', 'torso', 'waist'):
        K.append(Knob('body.' + k, ['body.proportions.' + k], DEFAULT_BODY['proportions'][k], PROPORTION[0],
                      (0.7, 1.4), 'body'))
    for k, st, hi in (('arm_down', 3.0, 35.0), ('leg_in', 1.5, 12.0), ('elbow', 3.0, 25.0)):
        K.append(Knob('body.pose.' + k, ['body.pose.' + k], 0.0, st, (0.0, hi), 'body'))
    for name, ps in _pairs(spec, 'skirt'):
        G = GARMENT['skirt']
        for k in ('flare', 'length', 'back', 'waist'):
            d, st, lo, hi, _ = G[k]
            K.append(Knob('%s.%s' % (name, k), ['garments.%s.%s' % (p, k) for p in ps], d, st, (lo, hi), 'skirt'))
    # boots: a shell over the lower legs (its region's start on each shin together), their cuffs and the shoes' soles
    for g in spec.get('garments') or []:
        if g['kind'] == 'shell' and all(r[0].endswith('LowerLeg') for r in g.get('region', [])) and g.get('region'):
            ps = ['garments.%s.region.%d.1' % (g['name'], i) for i in range(len(g['region']))]
            K.append(Knob(g['name'] + '.top', ps, 0.34, 0.03, (0.05, 0.8), 'boots'))
    for name, ps in _pairs(spec, 'band'):
        bones = {next(x for x in spec['garments'] if x['name'] == p)['bone'] for p in ps}
        if all(b.endswith('LowerLeg') for b in bones):
            K.append(Knob(name + '.t', ['garments.%s.t' % p for p in ps], 0.5, 0.03, (0.05, 0.8), 'boots'))
    for name, ps in _pairs(spec, 'sleeve'):
        for k in ('puff', 't1'):
            d, st, lo, hi, _ = GARMENT['sleeve'][k]
            K.append(Knob('%s.%s' % (name, k), ['garments.%s.%s' % (p, k) for p in ps], d, st, (lo, hi), 'sleeves'))
    shape = (spec.get('hair') or {}).get('shape')
    if shape and shape.get('mode') in ('mesh', 'geom'):
        for k in ('below', 'shoulder_x'):
            d, st, lo, hi, _ = HAIR_SHAPE[k]
            K.append(Knob('hair.shape.' + k, ['hair.shape.' + k], d, st, (lo, hi), 'hair'))
    return K


# ------------------------------------------------------------------------------------------------------------ terms
class Term:
    """one graded check's residual (fitkit.Term's fields): 'abs' v / tol, 'ratio' (v - 1) / tol, 'floor' (an IoU):
    max(0, floor - v) / tol; the measure it belongs to and the reference that measured it (the authority map weights it),
    its view and the piece (group) it is fitted with."""

    def __init__(self, check, sub, kind, tol, measure, ref, view, group, floor=None):
        self.check, self.sub, self.kind, self.tol = check, sub, kind, tol
        self.measure, self.ref, self.view, self.group, self.floor = measure, ref, view, group, floor

    @property
    def name(self):
        return self.check + ('.' + self.sub if self.sub else '')

    def residual(self, checks):
        c = checks.get(self.check) or {}
        v = c.get('value')
        if c.get('status') in ('SKIPPED', None) or not isinstance(v, (int, float)) or isinstance(v, bool):
            return 3.0, None
        if self.kind == 'ratio':
            return (v - 1) / self.tol, v
        if self.kind == 'floor':
            return max(0.0, self.floor - v) / self.tol, v
        return v / self.tol, v


def terms(spec):
    """the checks the body fit answers to, per piece: the sheet's body checks in every view (lengths to 0.08 L, widths
    to 8 %, IoUs up to their PASS, the arms' angle to 3 degrees), the generated shape's IoUs per band (a quarter weight
    for the body, whose silhouette the sheet decides; full for the hair's shape, which the generated shape decides)."""
    from .bodyqa import LIMITS as B
    from .qa3d import LIMITS as Q
    T = []
    iou_floor = lambda key: (B[key][0], B[key][0] - B[key][1])
    for v in VIEWS:
        body = [('feet', 'abs', B['length'][0]), ('iou', 'floor', iou_floor('iou')), ('iou_skin', 'floor', iou_floor('iou_part'))]
        if v in ('front', 'back'):
            body += [('leg', 'abs', B['length'][0]), ('arms', 'abs', 3.0)]
        for chk, kind, tol in body:
            fl, tl = tol if kind == 'floor' else (None, tol)
            T.append(Term('body_%s_%s' % (v, chk), None, kind, tl, 'body_silhouette', 'sheet', v, 'body', fl))
        skirt = [('skirt_width', 'ratio', B['width'][0]), ('hem', 'abs', B['length'][0]),
                 ('iou_outfit', 'floor', iou_floor('iou_part'))]
        if v != 'profile':
            skirt.append(('hem_mid', 'abs', B['length'][0]))
        for chk, kind, tol in skirt:
            fl, tl = tol if kind == 'floor' else (None, tol)
            T.append(Term('body_%s_%s' % (v, chk), None, kind, tl, 'body_silhouette', 'sheet', v, 'skirt', fl))
        if v in ('front', 'back'):
            T.append(Term('body_%s_boot' % v, None, 'abs', B['length'][0], 'body_silhouette', 'sheet', v, 'boots'))
        if v != 'profile':
            T.append(Term('body_%s_sleeves' % v, None, 'ratio', B['width'][0], 'body_silhouette', 'sheet', v, 'sleeves'))
        for chk, kind, tol in (('hair_length', 'abs', B['length'][0]), ('hair_width', 'ratio', B['width'][0]),
                               ('iou_hair', 'floor', iou_floor('iou_part')), ('top', 'abs', B['length'][0])):
            fl, tl = tol if kind == 'floor' else (None, tol)
            T.append(Term('body_%s_%s' % (v, chk), None, kind, tl, 'hair_silhouette', 'sheet', v, 'hair', fl))
    for band, grp in (('torso', 'body'), ('legs', 'body'), ('skirt', 'skirt')):
        T.append(Term('shape_iou_' + band, None, 'floor', 0.15, 'body_silhouette', 'trellis', 'shape', grp, 0.8))
    T.append(Term('shape_iou', None, 'floor', Q['shape_iou'][0] - Q['shape_iou'][1], 'body_silhouette', 'trellis', 'shape',
                  'body', Q['shape_iou'][0]))
    T.append(Term('ref_iou', None, 'floor', Q['ref_iou'][0] - Q['ref_iou'][1], 'body_silhouette', 'key3d', 'front', 'body',
                  Q['ref_iou'][0]))
    T.append(Term('shape_iou_hair', None, 'floor', Q['shape_iou_hair'][0] - Q['shape_iou_hair'][1], 'hair_shape', 'trellis',
                  'shape', 'hair', Q['shape_iou_hair'][0]))
    return T


GUARD = 4.0                     # the weight a term gets when its check read worse than at the start (the guard pass)


def residuals(checks, terms, authority=None, protect=()):
    """-> [dict(name, view, measure, ref, group, r (in tolerances), w (weight), value)]; a protected check's terms weigh
    GUARD times more."""
    A = authority or AUTHORITY
    out = []
    for t in terms:
        r, v = t.residual(checks)
        w = (1.0 if A.get(t.measure, t.ref) == t.ref else 0.25) * (GUARD if t.check in protect else 1.0)
        out.append(dict(name=t.name, view=t.view, measure=t.measure, ref=t.ref, group=t.group, r=float(r), value=v,
                        tol=t.tol, w=w))
    return out


RANK = {'PASS': 0, 'WARN': 1, 'FAIL': 2}


def regressions(before, after):
    """graded checks whose status got worse (as the merge gate reads them): {check: [before, after]}."""
    return {k: [b['status'], after[k]['status']] for k, b in before.items()
            if b.get('status') in RANK and (after.get(k) or {}).get('status') in RANK
            and RANK[after[k]['status']] > RANK[b['status']]}


def vector(res, x=None, ks=()):
    r = np.array([t['r'] for t in res]); w = np.sqrt([t['w'] for t in res])
    parts = [w * r, w * HINGE * np.sign(r) * np.maximum(0, np.abs(r) - 1)]
    if x is not None and len(ks):
        parts.append(np.array([REG * (xi - k.default) / (k.bounds[1] - k.bounds[0]) for xi, k in zip(x, ks)]))
    return np.concatenate(parts)


def cost(res, x=None, ks=()):
    f = vector(res, x, ks)
    c = LOSS_SCALE
    return float(0.5 * np.sum(c * c * 2 * (np.sqrt(1 + (f / c) ** 2) - 1)))


# ------------------------------------------------------------------------------------------------------------ checks
class BodyChecks:
    """the fit's evaluator (fitkit's protocol): checks(spec, group, fine) -> {check name: check} as qa.json names them:
    shape_* and ref_iou (qa3d's silhouettes; fine: the render's subdivision, else the viewport's), body_* (the model
    sheet's) and, for group 'palette' or 'all', palette_*."""

    def __init__(self, spec):
        from . import bodyeval
        self.E = bodyeval.Evaluator(spec)

    def checks(self, spec, group='all', fine=False):
        from .qa3d import LIMITS
        G = self.E.geometry(spec=spec)
        Q = self.E.qa(G, levels='render' if fine else 'viewport')
        out = {}
        for k, v in Q['checks'].items():
            if k in LIMITS:
                p, w = LIMITS[k]
                out[k] = {'value': v, 'status': 'PASS' if v >= p else 'WARN' if v >= w else 'FAIL'}
            else:
                out[k] = {'value': v, 'status': 'INFO'}
        out.update(self.E.sheet_checks(G, palette=group in ('all', 'palette')))
        return out


# ------------------------------------------------------------------------------------------------------------ the fit
class Budget(Exception):
    pass


def optimise(ev, spec, ks, T, group, authority=None, budget=None, protect=(), log=print):
    """least squares over one piece's knobs and terms from the spec's values: a trust region (scipy, bounded, soft-L1)
    on a Jacobian by finite differences at one knob step, then a pattern search (each knob one and half a step either way
    while the cost drops). Deterministic. -> (spec with the fitted knobs, info)."""
    from scipy.optimize import least_squares
    ks = [k for k in ks if k.group == group]
    T = [t for t in T if t.group == group]
    st = np.array([k.step for k in ks])
    lo = np.array([k.bounds[0] for k in ks]); hi = np.array([k.bounds[1] for k in ks])
    x0 = np.clip(np.array([k.get(spec) for k in ks]), lo, hi)
    ulo, uhi = (lo - x0) / st, (hi - x0) / st
    memo, hist = {}, []
    budget = budget or 12 * len(ks) + 24

    def spec_at(u):
        S = copy.deepcopy(spec)
        for k, v in zip(ks, x0 + np.asarray(u) * st):
            k.put(S, v)
        return S

    def res(u):
        key = tuple(np.round(u, 6))
        if key not in memo:
            if len(memo) >= budget:
                raise Budget()
            memo[key] = residuals(ev.checks(spec_at(u), group), T, authority, protect)
            c = cost(memo[key], x0 + np.asarray(u) * st, ks)
            hist.append({'x': (x0 + np.asarray(u) * st).round(4).tolist(), 'cost': round(c, 4)})
            log('  %-8s cost %8.3f  %s' % (group, c, ' '.join('%s=%.4g' % (k.name.split('.')[-1], v)
                                                             for k, v in zip(ks, x0 + np.asarray(u) * st))))
        return memo[key]

    def fun(u):
        return vector(res(u), x0 + np.asarray(u) * st, ks)

    def jac(u):
        f0 = fun(u)
        J = np.zeros((len(f0), len(u)))
        for i in range(len(u)):
            e = np.zeros(len(u)); e[i] = 1.0 if u[i] + 1 <= uhi[i] else -1.0
            J[:, i] = (fun(u + e) - f0) / e[i]
        return J

    def c_at(u):
        return cost(res(u), x0 + np.asarray(u) * st, ks)
    u = np.zeros(len(ks))
    stopped = None
    try:
        r = least_squares(fun, u, jac=jac, bounds=(ulo - 1e-9, uhi + 1e-9), method='trf', x_scale=1.0, loss='soft_l1',
                          f_scale=LOSS_SCALE, max_nfev=max(3, 2 * len(ks)), xtol=1e-3, ftol=1e-3)
        cands = [np.round(v, 6) for v in [r.x] + [np.array(k) for k in memo]]
        u = min(cands, key=lambda v: c_at(np.clip(v, ulo, uhi)))
        cur = c_at(u)
        for d in (1.0, 0.5):                                             # the polish
            moved = True
            while moved:
                moved = False
                for i in range(len(u)):
                    for sgn in (-1, 1):
                        v = u.copy(); v[i] = np.clip(v[i] + sgn * d, ulo[i], uhi[i])
                        if not np.allclose(v, u) and c_at(v) < cur - 1e-6:
                            u, cur, moved = v, c_at(v), True
    except Budget:
        stopped = 'budget'
        u = min((np.array(k) for k in memo), key=lambda v: c_at(v))
    x = x0 + u * st
    info = {'group': group, 'start': dict(zip([k.name for k in ks], x0.round(5).tolist())),
            'fitted': dict(zip([k.name for k in ks], x.round(5).tolist())),
            'at_bound': {k.name: k.at_bound(xi) for k, xi in zip(ks, x) if k.at_bound(xi)},
            'evaluations': len(memo), 'stopped': stopped, 'cost': [hist[0]['cost'], round(c_at(u), 4)], 'history': hist}
    return spec_at(u), info


def fit(spec_path, out, pieces=('body', 'skirt', 'boots', 'sleeves', 'hair'), palette=False, budget=None, log=print):
    """fit a spec's body, garments and hair piece by piece (see the module); write the fitted spec and the report into
    out. -> (fitted spec, report)."""
    from . import bodyeval
    t0 = time.time()
    os.makedirs(out, exist_ok=True)
    spec = bodyeval.resolve(spec_path)
    ev = BodyChecks(spec)
    authority = dict(AUTHORITY); authority.update((spec.get('ref') or {}).get('authority') or {})
    K, T = knobs(spec), terms(spec)
    before = ev.checks(spec, 'all', fine=True)
    # the terms whose checks the start measures (a cut figure on the sheet has no feet, a view no sleeves)
    T = [t for t in T if (before.get(t.check) or {}).get('status') not in (None, 'SKIPPED')]
    log('bodyfit: start measured (%d checks, %d terms)' % (len(before), len(T)))
    rep = {'spec': spec_path, 'authority': authority, 'knobs_declared': {k.name: k.declare() for k in K}, 'pieces': {}}
    fitted = spec
    for g in pieces:
        if not any(k.group == g for k in K):
            continue
        fitted, info = optimise(ev, fitted, K, T, g, authority, budget=budget, log=log)
        rep['pieces'][g] = {k: v for k, v in info.items() if k != 'history'}
        log('bodyfit: %s %s' % (g, info['fitted']))
    # the guard: a graded check that reads worse than at the start (the merge gate counts it against the fit) has its
    # terms weighed GUARD times more and its pieces fitted again from where they are
    after = ev.checks(fitted, 'all', fine=True)
    reg = regressions(before, after)
    if reg:
        log('bodyfit: guard: %s' % reg)
        prot = set(reg)
        for g in [g for g in pieces if any(t.group == g and t.check in prot for t in T)]:
            fitted, info = optimise(ev, fitted, K, T, g, authority, budget=budget, protect=prot, log=log)
            rep['pieces'][g + '_guard'] = {k: v for k, v in info.items() if k != 'history'}
        rep['guard'] = {'regressed': reg}
    if palette:
        fitted, rep['palette'] = fit_palette(ev, fitted, log=log)
    after = ev.checks(fitted, 'all', fine=True)
    rep['regressions'] = regressions(before, after)
    rep['before'] = {k: [v.get('value'), v.get('status')] for k, v in before.items()}
    rep['after'] = {k: [v.get('value'), v.get('status')] for k, v in after.items()}
    rep['residuals'] = {'before': residuals(before, T, authority), 'after': residuals(after, T, authority)}
    rep['still_failing'] = triage(after, T, K, fitted, authority)
    rep['seconds'] = round(time.time() - t0, 1)
    fitted = copy.deepcopy(fitted)
    fitted['bodyfit'] = {k.name: k.get(fitted) for k in K if k.group in pieces}
    name = spec.get('name', 'char')
    json.dump(fitted, open(os.path.join(out, name + '.bodyfit.json'), 'w'), indent=1)
    json.dump(rep, open(os.path.join(out, 'bodyfit_report.json'), 'w'), indent=1, default=str)
    open(os.path.join(out, 'bodyfit_report.md'), 'w').write(report_md(rep))
    log('bodyfit: wrote %s (%.0f s)' % (os.path.join(out, name + '.bodyfit.json'), rep['seconds']))
    return fitted, rep


# ------------------------------------------------------------------------------------------------------------ palette
def palette_members(spec):
    """the colour knobs behind each palette class: {class: [(path, kind)]}. kind 'garment': a garment toon (lit = the
    colour, shade = the colour * garments' fixed shade multiplier); 'toon3': a lit / shade / deep triple set on its own
    (the skin, the hair). A garment colour belongs to the class its colour family is (charkit.bodyqa.family)."""
    from .bodyqa import CLASS, family
    from .scene import SKIN
    names = {v: k for k, v in CLASS.items()}
    M = {'skin': [('skin', 'toon3')]}
    if spec.get('hair') is not None:
        M['hair'] = [('hair_colors', 'toon3')]
    for g in spec.get('garments') or []:
        for k in ('color', 'panel_color', 'hem_color', 'stripe_color', 'sole_color'):
            if k in g:
                c = names.get(int(family(np.asarray(g[k], float)[None])[0]))
                M.setdefault(c, []).append(('garments.%s.%s' % (g['name'], k), 'garment'))
        if isinstance(g.get('panel'), dict) and 'color' in g['panel']:
            c = names.get(int(family(np.asarray(g['panel']['color'], float)[None])[0]))
            M.setdefault(c, []).append(('garments.%s.panel.color' % g['name'], 'garment'))
    M['_skin_default'] = SKIN
    return M


def fit_palette(ev, spec, log=print):
    """the colour knobs set to the sheet's palette, class by class (charkit.paletteqa's tones, CIEDE2000): a toon3 class
    (the skin, the hair) takes the design's lit and shade tones (its deep tone keeps its ratio to the shade); a class of
    garment colours moves by one shift, the one that minimises the lit and shade dE00 together (the shade follows the lit
    at garments' fixed multiplier), held inside the class's colour family so no piece changes class. The iris is painted
    by its texture and left to the eye fit. A class that doesn't read better with the whole character re-measured keeps
    its colours. -> (spec, info {class: {before, after, paths}})."""
    from scipy.optimize import minimize
    from .bodyeval import get_knob, set_knob
    from .bodyqa import CLASS, family
    from .paletteqa import LIMITS as PL, ciede2000, srgb_to_lab
    LIT_PASS, SHADE_PASS = PL['lit'][0], PL['shade'][0]
    from .bodyeval import SHADE_MUL as MUL
    S = ev.E.sheet()
    if S is None:
        return spec, {'status': 'SKIPPED', 'why': 'no model sheet'}
    D = S.palette
    M = palette_members(spec)
    sk_default = M.pop('_skin_default')
    info = {'paths': []}
    dE = lambda a, b: ciede2000(srgb_to_lab(np.clip(a, 0, 1)), srgb_to_lab(np.clip(b, 0, 1)))

    def measured(sp):
        return {k[len('palette_'):]: v for k, v in ev.checks(sp, 'palette').items() if k.startswith('palette_')}
    cur = measured(spec)
    fitted = copy.deepcopy(spec)
    from . import bodymeasure, paletteqa
    G = ev.E.geometry(spec=spec)
    O = paletteqa.ours(bodymeasure.colours(G.bundle('viewport')))
    for cls, members in M.items():
        if cls not in D or D[cls] is None or cls not in O or cls == 'iris':
            continue
        dl, ds = D[cls].get('lit'), D[cls].get('shade')
        trial = copy.deepcopy(fitted)
        paths = []
        if members[0][1] == 'toon3':
            path = members[0][0]
            tri = {k: np.asarray(v, float) for k, v in (get_knob(fitted, path) or {}).items()}
            if not tri and path == 'skin':
                tri = {k: np.asarray(v, float) for k, v in sk_default.items()}
            new = dict(tri)
            if dl is not None:
                new['lit'] = np.clip(dl, 0, 1)
            if ds is not None:
                ratio = tri['deep'] / np.maximum(tri['shade'], 1e-3) if 'deep' in tri and 'shade' in tri else 0.8
                new['shade'] = np.clip(ds, 0, 1); new['deep'] = np.clip(ds * ratio, 0, 1)
            for k, v in new.items():
                set_knob(trial, '%s.%s' % (path, k), [round(float(x), 4) for x in v])
                paths.append('%s.%s' % (path, k))
        else:
            ol, osd = np.asarray(O[cls]['lit']), np.asarray(O[cls]['shade'])
            cols = {p: np.asarray(get_knob(fitted, p), float) for p, _ in members}
            code = CLASS[cls]

            def f(dv):
                if any(int(family(np.clip(c + dv, 0, 1)[None])[0]) != code for c in cols.values()):
                    return 1e3
                e = (dE(ol + dv, dl) / LIT_PASS) ** 2 if dl is not None else 0.0      # each tone in its own PASS limits
                return e + ((dE(osd + dv * MUL, ds) / SHADE_PASS) ** 2 if ds is not None else 0.0)
            r = minimize(f, np.zeros(3), method='Nelder-Mead', options=dict(xatol=1e-4, fatol=1e-3, maxiter=600,
                                                                            initial_simplex=np.vstack([np.zeros(3), 0.05 * np.eye(3)])))
            dv = r.x if r.fun < f(np.zeros(3)) else np.zeros(3)
            for p, c in cols.items():
                set_knob(trial, p, [round(float(x), 4) for x in np.clip(c + dv, 0, 1)])
                paths.append(p)
        after = measured(trial)
        lim = {'lit': LIT_PASS, 'shade': SHADE_PASS}
        before_c = sum(((cur.get('%s_%s' % (cls, t)) or {}).get('value') or 0) ** 2 / lim[t] ** 2 for t in lim)
        after_c = sum(((after.get('%s_%s' % (cls, t)) or {}).get('value') or 0) ** 2 / lim[t] ** 2 for t in lim)
        keep = after_c < before_c - 1e-6
        info[cls] = {'before': {t: (cur.get('%s_%s' % (cls, t)) or {}).get('value') for t in ('lit', 'shade')},
                     'after': {t: (after.get('%s_%s' % (cls, t)) or {}).get('value') for t in ('lit', 'shade')},
                     'kept': keep, 'paths': paths}
        log('palette: %-6s %s -> %s%s' % (cls, info[cls]['before'], info[cls]['after'], '' if keep else ' (not kept)'))
        if keep:
            fitted, cur = trial, after
            info['paths'] += paths
    return fitted, info


# ------------------------------------------------------------------------------------------------------------ report
def triage(checks, T, K, spec, authority=None):
    """each term still outside its tolerance: which piece owns it, its knobs' values (and bounds), the residual."""
    out = []
    for r in residuals(checks, T, authority):
        if abs(r['r']) <= 1:
            continue
        ks = [k for k in K if k.group == r['group']]
        out.append(dict(term=r['name'], r=round(r['r'], 3), value=r['value'], piece=r['group'],
                        knobs={k.name: [round(k.get(spec), 4), k.at_bound(k.get(spec))] for k in ks}))
    return out


def report_md(rep):
    L = ['# Body fit: %s' % rep['spec'], '', 'Seconds: %s. Authority: %s.' % (rep['seconds'], rep['authority']), '']
    L += ['## Checks before and after', '', '| check | before | after |', '| --- | --- | --- |']
    for k in sorted(rep['after']):
        b, a = rep['before'].get(k, [None, None]), rep['after'][k]
        if b != a and a[1] in ('PASS', 'WARN', 'FAIL', 'INFO'):
            L.append('| %s | %s %s | %s %s |' % (k, _f(b[0]), b[1], _f(a[0]), a[1]))
    L += ['', '## Pieces', '']
    for g, info in rep['pieces'].items():
        L.append('- **%s** (%d evaluations, cost %s -> %s): %s%s' % (
            g, info['evaluations'], info['cost'][0], info['cost'][1],
            ', '.join('%s %s -> %s' % (k, info['start'][k], v) for k, v in info['fitted'].items()),
            ('; at a bound: %s' % info['at_bound']) if info['at_bound'] else ''))
    if rep.get('regressions'):
        L += ['', '## Read worse than at the start', ''] + ['- %s: %s -> %s' % (k, a, b) for k, (a, b) in rep['regressions'].items()]
    L += ['', '## Still failing', '', '| term | residual (tolerances) | piece | its knobs |', '| --- | --- | --- | --- |']
    for t in rep['still_failing']:
        L.append('| %s | %+.2f | %s | %s |' % (t['term'], t['r'], t['piece'],
                                            ', '.join('%s %s%s' % (k, v[0], ' (%s bound)' % v[1] if v[1] else '')
                                                      for k, v in t['knobs'].items())))
    return '\n'.join(L) + '\n'


def _f(v):
    return ('%.3f' % v) if isinstance(v, float) else str(v)


def write_spec(src, fitted, names):
    """the fitted knobs written back into a spec file (only the knobs the fit owns; the rest of the file as it was)."""
    from .bodyeval import get_knob, set_knob
    S = json.load(open(src))
    for p in names:
        v = get_knob(fitted, p)
        if v is not None:
            set_knob(S, p, v)
    json.dump(S, open(src, 'w'), indent=1)
    return src


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return
    from . import bodyeval
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    spec_path = args[0]
    name = json.load(open(bodyeval._abs(spec_path)))['name']
    out = bodyeval._abs(opt('--out', 'charkit/out/bodyfit/%s' % name))
    pieces = opt('--pieces', 'body,skirt,boots,sleeves,hair').split(',')
    fitted, rep = fit(spec_path, out, pieces, palette='--palette' in args,
                      budget=int(opt('--budget')) if opt('--budget') else None, log=lambda *a: print(*a, flush=True))
    if '--write-spec' in args:
        paths = [p for k in knobs(fitted) if k.group in pieces for p in k.paths]
        if '--palette' in args:
            paths += (rep.get('palette') or {}).get('paths', [])
        write_spec(bodyeval._abs(spec_path), fitted, paths)
        print('wrote the fitted knobs into', spec_path)
