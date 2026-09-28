"""Fitting spec knobs to QA checks, generically: the machinery charkit/facefit.py uses for the face, eyes and neck, and a
body, garment or hair fitter can use for its own (docs/CHARKIT.md §4).

  Knob      a spec value the fit owns: its path in the spec, the template default, a finite-difference step, bounds, and
            the group it is fitted in (groups whose checks don't share knobs are fitted apart, each at its own cost)
  Term      one graded check's residual: the check (and which of its sub-values); how it's read ('ratio': (v - 1) / tol,
            'abs': v / tol, 'gap': one-sided, 0 under half the tolerance and 1 at it, 'floor': max(0, floor - v) / tol,
            a guard keeping another measure readable); its PASS tolerance and WARN line; the measure it belongs to and
            the reference that measured it (the character's authority map, charkit/refs/NAME/manifest.json, weights it:
            full where that reference is the measure's authority, a quarter otherwise); the view it is seen in
  evaluator a picklable class, built once in each worker process, with checks(spec, group, fine) -> {name: check};
            fine=True measures exactly as the QA does, fine=False may smooth (charkit.facefit's jitters the sheet's grid)

The objective: every term's residual (1 = its tolerance), again beyond the tolerance (a hinge: a check that fails costs
more than two that nearly pass), a missing check at MISSING, and a regulariser pulling each knob toward its template
default (its distance over its range, times REG). Least squares over all the group's terms at once (scipy's trust region,
bounded), the Jacobian by finite differences at one knob step each (in parallel), then a polish at the QA's own grid
(each knob two, one and half a step either way while the fine cost drops), restarted while it helps. Each term is also
kept in the status band it started in (or had in a baseline QA): past it, a steep extra residual (PROTECT), since the
merge gate fails any graded check that reads worse. Checks no term aims at are held by guard(): a group's change is
scaled back while one of them reads worse. Deterministic: no randomness anywhere.

    pool = fitkit.Pool('charkit.facefit:FaceChecks', (spec, R, cache), workers=6)
    T = fitkit.sensitivity(pool, spec, knobs)                        # the stable table (SCHEMA)
    spec2, info = fitkit.optimise(pool, spec, knobs, terms, group, authority, budget=200)
    rows = fitkit.triage(after_residuals, T, knobs, spec2)           # needs a knob / knob at bound / trade-off
"""
import copy, importlib, math

import numpy as np

SCHEMA = 'charkit.sensitivity/1'
MISSING = 3.0                   # the residual of a check that couldn't be measured
HINGE = 2.0                     # beyond its tolerance a residual counts again, this many times
REG = 0.3                       # the pull toward the template defaults: residual REG * (x - default) / range
LOSS_SCALE = 3.0                # soft-L1 above this many tolerances (the smooth phase)
POLISH = (2.0, 1.0, 0.5)        # the pattern search's step sizes, in knob steps
POLISH_MOVES = 12               # at most this many moves per step size
CYCLES = 3                      # trust region then polish, restarted from the polished point while the fine cost drops
PROTECT = 6.0                   # a term leaving the status band it started in (PASS, or WARN) costs this much more per
                                # tolerance: the merge gate fails any graded check that gets worse


class Knob:
    def __init__(self, name, path, default, step, bounds, group):
        self.name, self.path, self.default, self.step = name, tuple(path), default, step
        self.bounds, self.group = tuple(bounds), group

    def get(self, spec):
        d = spec
        for k in self.path[:-1]:
            d = d.get(k) or {}
        return float(d.get(self.path[-1], self.default))

    def put(self, spec, value):
        d = spec
        for k in self.path[:-1]:
            d = d.setdefault(k, {})
        d[self.path[-1]] = round(float(value), 5)

    def at_bound(self, x, eps=1e-6):
        lo, hi = self.bounds
        return 'lower' if x <= lo + eps * (hi - lo) else 'upper' if x >= hi - eps * (hi - lo) else None

    def declare(self):
        return {'path': list(self.path), 'default': self.default, 'step': self.step, 'bounds': list(self.bounds),
                'group': self.group}


class Term:
    def __init__(self, check, sub, kind, tol, measure, ref, view, group, floor=None, warn=2.0, weight=None):
        self.check, self.sub, self.kind, self.tol = check, sub, kind, tol
        self.measure, self.ref, self.view, self.group, self.floor = measure, ref, view, group, floor
        self.warn = warn                # the WARN limit in tolerances (the FAIL line)
        self.weight = weight            # a fixed weight instead of the authority's (a small one: a term kept, not aimed at)

    @property
    def name(self):
        return self.check + ('.' + self.sub if self.sub else '')

    def value(self, checks):
        c = checks.get(self.check)
        if not c or c.get('status') in ('SKIPPED', None):
            return None
        if self.sub is None:
            v = c.get('value')
        elif 'ratios' in c:
            v = c['ratios'].get(self.sub)
        elif 'per_height' in c:
            v = (c['per_height'].get(self.sub) or {}).get('ratio')
        elif 'regions' in c:
            v = c['regions'].get(self.sub)
        else:
            v = None
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    def residual(self, checks):
        v = self.value(checks)
        if v is None:
            return MISSING, None
        if self.kind == 'ratio':
            r = (v - 1) / self.tol
        elif self.kind == 'gap':
            r = max(0.0, 2 * v / self.tol - 1)
        elif self.kind == 'floor':
            r = max(0.0, self.floor - v) / self.tol
        else:
            r = v / self.tol
        miss = (checks.get(self.check) or {}).get('missing')
        if miss:
            r = r * (1 - miss) + MISSING * miss
        return float(r), v

    def declare(self):
        return {'check': self.check, 'sub': self.sub, 'kind': self.kind, 'tol': self.tol, 'measure': self.measure,
                'ref': self.ref, 'view': self.view, 'group': self.group, 'floor': self.floor, 'weight': self.weight}


def with_knobs(spec, x, knobs):
    S = copy.deepcopy(spec)
    for k, v in zip(knobs, x):
        k.put(S, v)
    return S


# ------------------------------------------------------------------------------------------------------------ objective
def residuals(checks, terms, authority=None):
    """-> [dict(name, view, measure, ref, r (in tolerances), w (weight), value)]."""
    A = authority or {}
    out = []
    for t in terms:
        r, v = t.residual(checks)
        w = t.weight if t.weight is not None else 1.0 if A.get(t.measure, t.ref) == t.ref else 0.25
        out.append(dict(name=t.name, view=t.view, measure=t.measure, ref=t.ref, r=r, value=v, tol=t.tol, warn=t.warn, w=w))
    return out


def bands(res):
    """each residual's status band at the start: 1 (it passes: keep it inside 1), its WARN line (it warns), or None."""
    return [1.0 if abs(t['r']) <= 1 else t['warn'] if abs(t['r']) <= t['warn'] else None for t in res]


def vector(res, x=None, knobs=(), keep=None):
    """residuals (and the knob values, for the regulariser; keep: bands(start) to protect) -> the least-squares vector."""
    r = np.array([t['r'] for t in res]); w = np.sqrt([t['w'] for t in res])
    parts = [w * r, w * HINGE * np.sign(r) * np.maximum(0, np.abs(r) - 1)]
    if keep is not None:
        lim = np.array([b if b is not None else np.inf for b in keep])
        parts.append(PROTECT * np.sign(r) * np.maximum(0, np.abs(r) - lim))
    if x is not None and len(knobs):
        parts.append(np.array([REG * (xi - k.default) / (k.bounds[1] - k.bounds[0]) for xi, k in zip(x, knobs)]))
    return np.concatenate(parts)


def cost(res, x=None, knobs=(), loss='linear', keep=None):
    """0.5 sum of the loss over the vector, as scipy's least_squares counts it ('linear' or 'soft_l1' at LOSS_SCALE)."""
    f = vector(res, x, knobs, keep)
    if loss == 'soft_l1':
        c = LOSS_SCALE
        return float(0.5 * np.sum(c * c * 2 * (np.sqrt(1 + (f / c) ** 2) - 1)))
    return float(0.5 * np.sum(f ** 2))


# ------------------------------------------------------------------------------------------------------------ workers
_W = None


def _init(factory, args):
    global _W
    mod, cls = factory.split(':')
    _W = getattr(importlib.import_module(mod), cls)(*args)


def _run(job):
    spec, group, fine = job
    return plain(_W.checks(spec, group, fine))


def plain(x):
    """a check set made json- and pickle-safe (arrays and private keys dropped, numpy scalars as floats)."""
    if isinstance(x, dict):
        return {k: plain(v) for k, v in x.items() if not str(k).startswith('_')}
    if isinstance(x, (list, tuple)):
        return [plain(v) for v in x]
    if isinstance(x, np.ndarray):
        return None
    if isinstance(x, (np.floating, np.integer)):
        return x.item()
    return x


class Pool:
    """evaluations in worker processes, each holding its own evaluator (factory 'module:Class', built with args)."""

    def __init__(self, factory, args, workers=1):
        import multiprocessing as mp
        self.n = max(1, int(workers))
        self.calls = 0
        if self.n > 1:
            self.p = mp.get_context('spawn').Pool(self.n, initializer=_init, initargs=(factory, args))
        else:
            self.p = None
            _init(factory, args)

    def map(self, jobs):
        self.calls += len(jobs)
        return self.p.map(_run, jobs) if self.p else [_run(j) for j in jobs]

    def close(self):
        if self.p:
            self.p.close(); self.p.join()


# ------------------------------------------------------------------------------------------------------------ sensitivity
def measures(checks):
    """the numbers a check set holds, flat: 'check', 'check.sub' (ratios, regions, per-height ratios), 'check.ours'."""
    out = {}
    for k, c in checks.items():
        if not isinstance(c, dict):
            continue
        v = c.get('value')
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = float(v)
        for sub in ('ratios', 'regions'):
            for q, x in (c.get(sub) or {}).items():
                if isinstance(x, (int, float)):
                    out[k + '.' + q] = float(x)
        for q, x in (c.get('per_height') or {}).items():
            if isinstance(x, dict) and isinstance(x.get('ratio'), (int, float)):
                out[k + '.' + q] = float(x['ratio'])
        if isinstance(c.get('ours'), (int, float)) and not isinstance(c.get('ours'), bool):
            out[k + '.ours'] = float(c['ours'])
    return out


def sensitivity(pool, spec, knobs, fine=False):
    """every knob one step down and up from the spec, every measured value's change.
    -> {'schema': SCHEMA, 'knobs': {knob: {'value', 'step', 'bounds', 'group', 'at_bound',
        'measures': {measure: {'at', 'minus', 'plus', 'per_step', 'per_unit'}}}}}
    per_unit = (plus - minus) / (2 step): the change per unit of the knob (None where a side didn't measure)."""
    jobs, index = [], []
    for g in sorted(set(k.group for k in knobs)):
        jobs.append((spec, g, fine)); index.append((None, g, 0))
    for k in knobs:
        x0 = k.get(spec)
        for sgn in (-1, 1):
            jobs.append((with_knobs(spec, [min(k.bounds[1], max(k.bounds[0], x0 + sgn * k.step))], [k]), k.group, fine))
            index.append((k, k.group, sgn))
    out = pool.map(jobs)
    base = {g: measures(c) for (k, g, s), c in zip(index, out) if k is None}
    T = {}
    for (k, g, sgn), c in zip(index, out):
        if k is None:
            continue
        x0 = k.get(spec)
        t = T.setdefault(k.name, {'value': x0, 'step': k.step, 'bounds': list(k.bounds), 'group': g,
                                  'at_bound': k.at_bound(x0), 'measures': {}})
        xs = min(k.bounds[1], max(k.bounds[0], x0 + sgn * k.step))
        t.setdefault('_x', {})[sgn] = xs
        for m, v in measures(c).items():
            e = t['measures'].setdefault(m, {'at': base[g].get(m)})
            e['minus' if sgn < 0 else 'plus'] = v
    for name, t in T.items():
        dx = t['_x'][1] - t['_x'][-1]
        for m, e in t['measures'].items():
            a, b = e.get('minus'), e.get('plus')
            ok = a is not None and b is not None and dx > 0
            e['per_unit'] = round((b - a) / dx, 6) if ok else None
            e['per_step'] = round((b - a) / dx * t['step'], 6) if ok else None
        del t['_x']
    return {'schema': SCHEMA, 'knobs': T}


# ------------------------------------------------------------------------------------------------------------ the fit
class Budget(Exception):
    pass


def optimise(pool, spec, knobs, terms, group, authority=None, budget=None, loss='soft_l1', protect=True, baseline=None,
             log=print):
    """least squares over one group's knobs and terms from the spec's values (see the module). protect: each term kept
    in the status band it started in (or had in `baseline`, a check set, where it has the check).
    -> (spec with the fitted knobs, info {start, fitted, at_bound, evaluations, history, stopped})."""
    from scipy.optimize import least_squares
    knobs = [k for k in knobs if k.group == group]
    terms = [t for t in terms if t.group == group]
    st = np.array([k.step for k in knobs])
    lo = np.array([k.bounds[0] for k in knobs]); hi = np.array([k.bounds[1] for k in knobs])
    x0 = np.clip(np.array([k.get(spec) for k in knobs]), lo, hi)
    x0 = np.clip(x0, lo + 0.5 * st, hi - 0.5 * st)          # half a step inside its bounds: a trust region can move
    ulo, uhi = (lo - x0) / st, (hi - x0) / st
    memo, hist, used = {}, [], [0]

    def evaluate(us, fine=False):
        keys = [(tuple(np.round(u, 6)), fine) for u in us]
        todo = list(dict.fromkeys(k for k in keys if k not in memo))
        if todo:
            if budget is not None and used[0] + len(todo) > budget:
                raise Budget()
            used[0] += len(todo)
            cs = pool.map([(with_knobs(spec, x0 + np.array(k[0]) * st, knobs), group, fine) for k in todo])
            for k, c in zip(todo, cs):
                memo[k] = residuals(c, terms, authority)
        return [memo[k] for k in keys]

    keep = None
    if protect:
        keep = bands(evaluate([np.zeros(len(knobs))], True)[0])
        if baseline:
            kb = bands(residuals(baseline, terms, authority))
            keep = [b if t.check in baseline else k for t, k, b in zip(terms, keep, kb)]

    def f(u, fine=False):
        return vector(evaluate([u], fine)[0], x0 + np.asarray(u) * st, knobs, keep)

    best = {'u': np.zeros(len(knobs)), 'c': None}

    def fun(u):
        v = f(u)
        c = cost(evaluate([u])[0], x0 + np.asarray(u) * st, knobs, loss, keep)
        hist.append({'x': (x0 + u * st).round(5).tolist(), 'cost': round(c, 4)})
        if best['c'] is None or c < best['c']:
            best.update(u=np.array(u), c=c)
        log('  %s cost %8.3f  %s' % (group, c, ' '.join('%s=%.4g' % (k.name.split('.')[-1], v_)
                                                         for k, v_ in zip(knobs, x0 + u * st))))
        return v

    def jac(u):
        pts = []
        for i in range(len(u)):
            e = np.zeros(len(u)); e[i] = 1.0 if u[i] + 1 <= uhi[i] else -1.0
            pts.append(u + e)
        R = evaluate([u] + pts)
        f0 = vector(R[0], x0 + u * st, knobs, keep)
        return np.stack([(vector(R[i + 1], x0 + pts[i] * st, knobs, keep) - f0) / (pts[i] - u)[i] for i in range(len(u))], 1)

    def polish(u):
        """a pattern search at the QA's own grid: every knob two steps, one, then half a step either way, the best move
        taken while it lowers the fine cost (it also crosses what the smooth phase couldn't). -> (u, fine cost)."""
        cur = cost(evaluate([u], True)[0], x0 + u * st, knobs, loss, keep)
        for dstep in POLISH:
            for _ in range(POLISH_MOVES):
                cands = []
                for i in range(len(u)):
                    for sgn in (-1, 1):
                        v = u.copy(); v[i] = np.clip(v[i] + sgn * dstep, ulo[i], uhi[i])
                        if not np.allclose(v, u):
                            cands.append((i, v))
                cs = [cost(r, x0 + v * st, knobs, loss, keep) for r, (_, v) in zip(evaluate([v for _, v in cands], True), cands)]
                j = int(np.argmin(cs))
                if cs[j] >= cur - 1e-6:
                    break
                i = cands[j][0]
                log('  polish %s %+.1f step -> %.3f' % (knobs[i].name, cands[j][1][i] - u[i], cs[j]))
                cur, u = cs[j], cands[j][1]
        return u, cur

    stopped, u, done = None, np.zeros(len(knobs)), None
    try:
        for cycle in range(CYCLES):
            best.update(u=np.array(u), c=None)
            # soft-L1 (the default): a term that jumps (a measure flipping between two readings) can't dominate the
            # step; 'linear' (plain least squares) converges faster where every term is smooth
            least_squares(fun, u, jac=jac, bounds=(ulo, uhi), method='trf', x_scale=1.0, loss=loss,
                          f_scale=LOSS_SCALE, max_nfev=max(3, 4 * len(knobs)), xtol=1e-3, ftol=1e-4, gtol=1e-6)
            u, c = polish(np.clip(best['u'], ulo, uhi))
            if done is not None and c >= done[1] - 1e-6:
                break
            done = (u, c)
            log('  %s cycle %d: fine cost %.3f' % (group, cycle + 1, c))
    except Budget:
        stopped = 'budget'
    u = done[0] if done is not None else np.clip(best['u'], ulo, uhi)
    x = x0 + u * st
    info = {'group': group, 'start': dict(zip([k.name for k in knobs], x0.round(5).tolist())),
            'fitted': dict(zip([k.name for k in knobs], x.round(5).tolist())),
            'at_bound': {k.name: k.at_bound(xi) for k, xi in zip(knobs, x) if k.at_bound(xi)},
            'evaluations': used[0], 'stopped': stopped, 'history': hist}
    return with_knobs(spec, x, knobs), info


RANK = {'PASS': 0, 'WARN': 1, 'FAIL': 2}


def regressions(before, after, names=None):
    """graded checks whose status got worse (or that disappeared), optionally only those `names` accepts."""
    out = {}
    for k, c in before.items():
        if not isinstance(c, dict) or c.get('status') not in RANK or (names and not names(k)):
            continue
        a = (after.get(k) or {}).get('status')
        if a not in RANK or RANK[a] > RANK[c['status']]:
            out[k] = [c['status'], a]
    return out


def guard(pool, start, fitted, knobs, before, names, steps=(0.75, 0.5, 0.25, 0.0), log=print):
    """checks the fit doesn't aim at but mustn't break (names(check) -> bool): while any reads a worse status than at
    the start, the whole fitted change is scaled back (steps of the change). -> (spec, info {kept, regressions})."""
    x0 = np.array([k.get(start) for k in knobs]); x1 = np.array([k.get(fitted) for k in knobs])
    specs = [with_knobs(start, x0 + t * (x1 - x0), knobs) for t in (1.0,) + tuple(steps)]
    cs = pool.map([(s_, 'all', True) for s_ in specs])
    for t, s_, c in zip((1.0,) + tuple(steps), specs, cs):
        reg = regressions(before, c, names)
        if not reg:
            if t < 1.0:
                log('  guard: the change scaled to %.2f to keep %s' % (t, ', '.join(regressions(before, cs[0], names))))
            return s_, {'kept': t, 'regressions_at_full': regressions(before, cs[0], names), 'checks': c}
    return start, {'kept': 0.0, 'regressions_at_full': regressions(before, cs[0], names), 'checks': cs[-1]}


# ------------------------------------------------------------------------------------------------------------ triage
def triage(res, table, knobs, spec, thresh=0.25):
    """each term still outside its tolerance after a fit, sorted into why: 'needs a knob' (no knob moves it by `thresh`
    of its tolerance per step), 'knob at bound' (every knob that would move it the right way sits at that bound), or
    'trade-off' (a knob that would help is free, so helping it costs other terms more).
    -> [dict(term, r, why, knobs [dict(knob, per_step_tol, blocked)])]."""
    kn = {k.name: k for k in knobs}
    out = []
    for t in res:
        if abs(t['r']) <= 1:
            continue
        movers = []
        for name, e in table['knobs'].items():
            m = e['measures'].get(t['name'])
            if name in kn and m and m.get('per_step') is not None:
                movers.append((name, m['per_step'] / t['tol']))
        strong = [(n, g) for n, g in movers if abs(g) >= thresh]
        if not strong:
            out.append(dict(term=t['name'], r=round(t['r'], 3), why='needs a knob',
                            knobs=[dict(knob=n, per_step_tol=round(float(g), 3), blocked=None)
                                   for n, g in sorted(movers, key=lambda m: -abs(m[1]))[:3]]))
            continue
        rows = []
        for n, g in strong:
            want = -np.sign(t['r']) * np.sign(g)            # the knob's helpful direction
            b = kn[n].at_bound(kn[n].get(spec))
            rows.append(dict(knob=n, per_step_tol=round(float(g), 3),
                             blocked=bool((b == 'upper' and want > 0) or (b == 'lower' and want < 0))))
        out.append(dict(term=t['name'], r=round(t['r'], 3),
                        why='knob at bound' if all(r['blocked'] for r in rows) else 'trade-off',
                        knobs=sorted(rows, key=lambda r: -abs(r['per_step_tol']))))
    return out
