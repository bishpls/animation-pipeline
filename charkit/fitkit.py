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
            fine=True measures exactly as the QA does, fine=False may smooth (charkit.facefit's jitters the sheet's grid).
            Optionally jacobian(spec, group, knob_names) -> (checks as checks(spec, group, False) gives them,
            {measure ('check' or 'check.sub', as measures() names them): {knob: d value / d knob}}): the gradient path
            (optimise(gradient=True), off by default: GRADIENT), e.g. silhouettes differentiated by
            charkit.render.softras and chained through the template's builder (charkit.render.softfit)

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
import copy, importlib, math, os, sys, time

import numpy as np

SCHEMA = 'charkit.sensitivity/1'
MISSING = 3.0                   # the residual of a check that couldn't be measured
HINGE = 2.0                     # beyond its tolerance a residual counts again, this many times
REG = 0.3                       # the pull toward the template defaults: residual REG * (x - default) / range
LOSS_SCALE = 3.0                # soft-L1 above this many tolerances (the smooth phase)
POLISH = (2.0, 1.0, 0.5)        # the pattern search's step sizes, in knob steps
POLISH_MOVES = 12               # at most this many moves per step size
CYCLES = 3                      # trust region then polish, restarted from the polished point while the fine cost drops
FAST = True                     # optimise(fast=): Broyden updates between full Jacobians, and a model-guided polish
BROYDEN_REFRESH = 4             # fast: a full finite-difference Jacobian at least every this many trust-region steps
POLISH_SHARE = 0.25             # fast: the polish first tries this share of its moves, those the Jacobian predicts best
GRADIENT = False                # optimise(gradient=): the trust region's Jacobian from the evaluator's own jacobian()
                                # (one call, the analytic chain) instead of a finite difference per knob. Opt-in: an
                                # evaluator that has no jacobian() can't take it
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

    def dresidual(self, checks, D, names):
        """d residual / d knob (the knobs `names`, in knob units) from the evaluator's jacobian() D: the reading's own
        derivative (ratio and abs 1 / tol; gap 2 / tol past half the tolerance, else 0; floor -1 / tol below the floor,
        else 0), 0 where the check is missing. -> (len(names),)."""
        r, v = self.residual(checks)
        if v is None:
            return np.zeros(len(names))
        dv = np.array([float((D.get(self.name) or {}).get(n, 0.0)) for n in names])
        if self.kind == 'gap':
            k = 2.0 / self.tol if 2 * v / self.tol - 1 > 0 else 0.0
        elif self.kind == 'floor':
            k = -1.0 / self.tol if self.floor - v > 0 else 0.0
        else:
            k = 1.0 / self.tol
        miss = (checks.get(self.check) or {}).get('missing') or 0.0
        return k * dv * (1 - miss)

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


def vector_jacobian(res, dres, knobs=(), keep=None):
    """vector()'s Jacobian from each residual's gradient dres (terms x knobs, knob units): the weighted residual, its
    hinge past the tolerance, the protection past its band, the regulariser's diagonal."""
    r = np.array([t['r'] for t in res]); w = np.sqrt([t['w'] for t in res])[:, None]
    parts = [w * dres, w * HINGE * (np.abs(r) > 1)[:, None] * dres]
    if keep is not None:
        lim = np.array([b if b is not None else np.inf for b in keep])
        parts.append(PROTECT * (np.abs(r) > lim)[:, None] * dres)
    if len(knobs):
        parts.append(np.diag([REG / (k.bounds[1] - k.bounds[0]) for k in knobs]))
    return np.concatenate(parts, 0)


def cost(res, x=None, knobs=(), loss='linear', keep=None):
    """0.5 sum of the loss over the vector, as scipy's least_squares counts it ('linear' or 'soft_l1' at LOSS_SCALE)."""
    return loss_of(vector(res, x, knobs, keep), loss)


def loss_of(f, loss='linear'):
    """cost's loss over a least-squares vector."""
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
    """one evaluation in a worker -> (checks, meta {seconds, stages (the evaluator's `timing`, if it keeps one), pid,
    peak_mb (the worker's peak resident memory)})."""
    import resource
    spec, group, fine = job
    t = time.time()
    c = plain(_W.checks(spec, group, fine))
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss                 # bytes on macOS, KB on Linux
    return c, {'seconds': time.time() - t, 'stages': dict(getattr(_W, 'timing', None) or {}), 'pid': os.getpid(),
               'peak_mb': rss / (1 << 20) if sys.platform == 'darwin' else rss / 1024}


def _run_jac(job):
    """one gradient in a worker (the evaluator's jacobian()) -> (checks, {measure: {knob: d/d knob}}, meta)."""
    import resource
    spec, group, names = job
    t = time.time()
    c, D = _W.jacobian(spec, group, names)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    D = {m: {k: float(v) for k, v in d.items()} for m, d in D.items()}
    return plain(c), D, {'seconds': time.time() - t, 'stages': dict(getattr(_W, 'timing', None) or {}),
                         'pid': os.getpid(), 'peak_mb': rss / (1 << 20) if sys.platform == 'darwin' else rss / 1024}


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
    """evaluations in worker processes, each holding its own evaluator (factory 'module:Class', built with args).
    map(jobs, phase) labels what the evaluations were for; report() gives, per phase, how many there were, the wall time
    they took and the time the workers spent (their ratio is the parallelism the phase got: more workers help only a
    phase whose parallelism is near the worker count), the evaluator's own stage times, and each worker's peak memory."""

    def __init__(self, factory, args, workers=1):
        import multiprocessing as mp
        self.n = max(1, int(workers))
        self.calls = 0
        self.stats, self.peak, self.t0 = {}, {}, time.time()
        if self.n > 1:
            self.p = mp.get_context('spawn').Pool(self.n, initializer=_init, initargs=(factory, args))
        else:
            self.p = None
            _init(factory, args)

    def map(self, jobs, phase='other'):
        t = time.time()
        self.calls += len(jobs)
        R = self.p.map(_run, jobs) if self.p else [_run(j) for j in jobs]
        s = self.stats.setdefault(phase, {'calls': 0, 'evaluations': 0, 'seconds': 0.0, 'eval_seconds': 0.0, 'stages': {}})
        s['calls'] += 1
        s['evaluations'] += len(jobs)
        s['seconds'] += time.time() - t
        for _, m in R:
            s['eval_seconds'] += m['seconds']
            for k, v in m['stages'].items():
                s['stages'][k] = s['stages'].get(k, 0.0) + v
            self.peak[m['pid']] = max(self.peak.get(m['pid'], 0.0), m['peak_mb'])
        return [c for c, _ in R]

    def jacobian(self, jobs, phase='jacobian'):
        """the evaluator's jacobian() for each job (spec, group, knob names), counted as map() counts evaluations.
        -> [(checks, {measure: {knob: d/d knob}})]."""
        t = time.time()
        self.calls += len(jobs)
        R = self.p.map(_run_jac, jobs) if self.p else [_run_jac(j) for j in jobs]
        s = self.stats.setdefault(phase, {'calls': 0, 'evaluations': 0, 'seconds': 0.0, 'eval_seconds': 0.0, 'stages': {}})
        s['calls'] += 1
        s['evaluations'] += len(jobs)
        s['seconds'] += time.time() - t
        for _, _, m in R:
            s['eval_seconds'] += m['seconds']
            self.peak[m['pid']] = max(self.peak.get(m['pid'], 0.0), m['peak_mb'])
        return [(c, D) for c, D, _ in R]

    def report(self):
        """-> {workers, seconds (since the pool started), phases {phase: {calls, evaluations, seconds (wall),
        eval_seconds (summed over the workers), per_eval, parallelism (eval_seconds / seconds), stages {stage: seconds
        per evaluation}}}, peak_mb (the largest worker's), peak_mb_total (all workers')}."""
        ph = {}
        for k, s in sorted(self.stats.items(), key=lambda kv: -kv[1]['seconds']):
            n = max(1, s['evaluations'])
            ph[k] = {'calls': s['calls'], 'evaluations': s['evaluations'], 'seconds': round(s['seconds'], 1),
                     'eval_seconds': round(s['eval_seconds'], 1), 'per_eval': round(s['eval_seconds'] / n, 3),
                     'parallelism': round(s['eval_seconds'] / max(1e-9, s['seconds']), 2),
                     'stages': {st: round(v / n, 3) for st, v in sorted(s['stages'].items(), key=lambda kv: -kv[1])}}
        return {'workers': self.n, 'seconds': round(time.time() - self.t0, 1), 'phases': ph,
                'peak_mb': round(max(self.peak.values(), default=0.0)), 'peak_mb_total': round(sum(self.peak.values()))}

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
    out = pool.map(jobs, phase='sensitivity')
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
             fast=None, log=print, gradient=None):
    """least squares over one group's knobs and terms from the spec's values (see the module). protect: each term kept
    in the status band it started in (or had in `baseline`, a check set, where it has the check). fast (default FAST):
    the trust region's Jacobian is updated from each step's own evaluation (Broyden) between full finite-difference ones
    (at least every BROYDEN_REFRESH steps), one evaluation a step instead of one per knob; and the polish tries the moves
    the Jacobian predicts best first (POLISH_SHARE of them), sweeping them all only to confirm it has stopped at its
    finest step, where the plain polish sweeps every move every time. gradient (default GRADIENT, off): every Jacobian
    from the evaluator's jacobian() at the point (one call, counted as one evaluation, phase 'jacobian'), no finite
    differences and no Broyden updates; the polish is unchanged.
    -> (spec with the fitted knobs, info {start, fitted, at_bound, evaluations, phases, fast, gradient, history,
    stopped})."""
    from scipy.optimize import least_squares
    fast = FAST if fast is None else fast
    gradient = GRADIENT if gradient is None else gradient
    knobs = [k for k in knobs if k.group == group]
    terms = [t for t in terms if t.group == group]
    st = np.array([k.step for k in knobs])
    lo = np.array([k.bounds[0] for k in knobs]); hi = np.array([k.bounds[1] for k in knobs])
    x0 = np.clip(np.array([k.get(spec) for k in knobs]), lo, hi)
    x0 = np.clip(x0, lo + 0.5 * st, hi - 0.5 * st)          # half a step inside its bounds: a trust region can move
    ulo, uhi = (lo - x0) / st, (hi - x0) / st
    memo, hist, used, phases = {}, [], [0], {}

    def evaluate(us, fine=False, phase='step'):
        keys = [(tuple(np.round(u, 6)), fine) for u in us]
        todo = list(dict.fromkeys(k for k in keys if k not in memo))
        if todo:
            if budget is not None and used[0] + len(todo) > budget:
                raise Budget()
            used[0] += len(todo)
            t = time.time()
            cs = pool.map([(with_knobs(spec, x0 + np.array(k[0]) * st, knobs), group, fine) for k in todo], phase=phase)
            P = phases.setdefault(phase, {'evaluations': 0, 'calls': 0, 'seconds': 0.0})
            P['evaluations'] += len(todo); P['calls'] += 1; P['seconds'] = round(P['seconds'] + time.time() - t, 2)
            for k, c in zip(todo, cs):
                memo[k] = residuals(c, terms, authority)
        return [memo[k] for k in keys]

    keep = None
    if protect:
        keep = bands(evaluate([np.zeros(len(knobs))], True, 'start')[0])
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

    model = {'J': None, 'u': None, 'f': None, 'age': 0}        # the latest Jacobian, where it was taken, and its age

    def jac_fd(u):
        pts = []
        for i in range(len(u)):
            e = np.zeros(len(u)); e[i] = 1.0 if u[i] + 1 <= uhi[i] else -1.0
            pts.append(u + e)
        R = evaluate([u] + pts, phase='gradient')
        f0 = vector(R[0], x0 + u * st, knobs, keep)
        return np.stack([(vector(R[i + 1], x0 + pts[i] * st, knobs, keep) - f0) / (pts[i] - u)[i] for i in range(len(u))], 1)

    def jac_grad(u):
        """the analytic Jacobian (the evaluator's jacobian()) at u, in step units; its checks go into the memo."""
        key = (tuple(np.round(u, 6)), False)
        if budget is not None and used[0] + 1 > budget:
            raise Budget()
        used[0] += 1
        t = time.time()
        c, D = pool.jacobian([(with_knobs(spec, x0 + u * st, knobs), group, [k.name for k in knobs])])[0]
        P = phases.setdefault('jacobian', {'evaluations': 0, 'calls': 0, 'seconds': 0.0})
        P['evaluations'] += 1; P['calls'] += 1; P['seconds'] = round(P['seconds'] + time.time() - t, 2)
        memo.setdefault(key, residuals(c, terms, authority))
        dres = np.array([t_.dresidual(c, D, [k.name for k in knobs]) for t_ in terms]).reshape(len(terms), len(knobs))
        return vector_jacobian(memo[key], dres, knobs, keep) * st[None, :]

    def jac(u):
        u = np.asarray(u, float)
        if gradient:
            Jm = jac_grad(u)
            model.update(J=Jm, u=u.copy(), f=f(u), age=0)
            return Jm
        fu = f(u)                                    # trf evaluated fun(u) before asking for its Jacobian: no evaluation
        if fast and model['J'] is not None and model['age'] < BROYDEN_REFRESH:
            s_ = u - model['u']
            ss = float(s_ @ s_)
            if ss > 1e-12:                           # Broyden's update: the secant through the step just taken
                Jn = model['J'] + np.outer(fu - model['f'] - model['J'] @ s_, s_) / ss
                model.update(J=Jn, u=u.copy(), f=fu, age=model['age'] + 1)
                return Jn
        Jm = jac_fd(u)
        model.update(J=Jm, u=u.copy(), f=fu, age=0)
        return Jm

    def costs(cands):
        return [cost(r, x0 + v * st, knobs, loss, keep) for r, (_, v) in zip(evaluate([v for _, v in cands], True, 'polish'), cands)]

    def polish(u):
        """a pattern search at the QA's own grid: every knob two steps, one, then half a step either way, the best move
        taken while it lowers the fine cost (it also crosses what the smooth phase couldn't). fast: the moves the
        Jacobian predicts best are tried first; past the finest step size a miss ends that step size, and at the finest
        the other moves are swept before it stops. -> (u, fine cost)."""
        cur = cost(evaluate([u], True, 'polish')[0], x0 + u * st, knobs, loss, keep)
        for si, dstep in enumerate(POLISH):
            finest = si == len(POLISH) - 1
            for _ in range(POLISH_MOVES):
                cands = []
                for i in range(len(u)):
                    for sgn in (-1, 1):
                        v = u.copy(); v[i] = np.clip(v[i] + sgn * dstep, ulo[i], uhi[i])
                        if not np.allclose(v, u):
                            cands.append((i, v))
                if not cands:
                    break
                if fast and model['J'] is not None and len(cands) > 4:
                    f0 = f(u, True)
                    pred = [loss_of(f0 + model['J'] @ (v - u), loss) for _, v in cands]
                    order = list(np.argsort(pred, kind='stable'))
                    k = max(2, int(np.ceil(POLISH_SHARE * len(cands))))
                    tried = [cands[i] for i in order[:k]]
                    cs = costs(tried)
                    if min(cs) >= cur - 1e-6:
                        if not finest:
                            break                    # the model's best don't help at this step size: go finer
                        rest = [cands[i] for i in order[k:]]
                        tried, cs = tried + rest, cs + costs(rest)
                else:
                    tried, cs = cands, costs(cands)
                j = int(np.argmin(cs))
                if cs[j] >= cur - 1e-6:
                    break
                i = tried[j][0]
                log('  polish %s %+.1f step -> %.3f' % (knobs[i].name, tried[j][1][i] - u[i], cs[j]))
                cur, u = cs[j], tried[j][1]
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
            'evaluations': used[0], 'phases': phases, 'fast': fast, 'gradient': bool(gradient), 'stopped': stopped,
            'history': hist}
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
    cs = pool.map([(s_, 'all', True) for s_ in specs], phase='guard')
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
