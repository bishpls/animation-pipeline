"""charkit sweep optimize: a fit's knobs tuned by a batch optimizer instead of an agent hand-stepping sweeps (sweep, read
the table, design the next sweep: face on sweep 8, lapels 7+, hair shells 11 on 2026-10-01). One launch, one read
(tool/optimize, docs/workstreams/optimize.md). Each generation's population runs in parallel through the sweep's own
stages (charkit/sweep.py: the variant rebuilt at its stage, spliced into the base bundle, measured by the QA's parts)
on persistent workers, each holding the stage's context and a build slot; the top candidates are then confirmed by real
builds.

    python -m charkit sweep optimize DECL.json [--out DIR] [--workers N|auto] [--reserve K] [--resume] [--no-confirm]
                                     [--confirm K] [--evals N] [--minutes M] [--seed S] [--box [NAME]] [--plan]
    python -m charkit sweep --optimize DECL.json ...                     # the same
    python -m charkit sweep optimize report OUT                          # the tables, plots and review page again
    python -m charkit sweep optimize audit BUILD [--parts P,..] [--out DIR]   # which checks the fast path measures
                                                                         # as the real build does (fast-OK / real-only)

The declaration is a sweep's (base, stage, spec, set, parts, checks, objects, boards: charkit/sweep.py) with an
`optimize` block:

  knobs       [{path | name, lo, hi, int, log, x0, step, round}]: a spec path (the sweep's dotted override paths, list
              items by name, kind or index; `qa:` and `style.` keys too) or a name used by `template`; bounds [lo, hi];
              int: integer; log: searched on a log scale; x0: the start (default: the spec's value at path, else the
              middle); step: the first search's spread in knob units (default sigma0 of the range); round: decimals
  template    {PATH: value}: values built from the knobs; a string '=EXPR' is arithmetic over knob names (+ - * / **,
              min, max, abs, round): e.g. monotone knots from gaps {"garments.skirt.band.stair": [[0, 0.35], ["=g1",
              "=h1"], ["=g1+g2", "=h2"]]}
  objective   [{check, toward, weight, field | view, limits, better, target, scale, margin, log, proxy}]: check a name
              or fnmatch pattern (each matching check its own term, matched on the control row); toward
                'pass'    the check's distance from PASS in warn bands (charkit.checks.severity's: 0 at the pass limit,
                          1 at the fail limit), from its limits: the term's own, else the check's declaration
                          (charkit.declared), else charkit.checks' table; margin > 0 keeps rewarding up to that many
                          bands inside PASS; with no limits, its status (PASS 0, WARN 0.5, FAIL 1.5)
                'max'/'min'  the value (or field: 'views.front', 'ratio.front'; view V = 'views.V') over scale
                'target'  |value - target| / scale (log: |ln(value / target)| / scale)
              weight (1); a term on a real-only check (FIDELITY) is left out of the screen and scored at the confirm
              (proxy: true scores it on the screen's drawing as well)
  constraints enforced, not weighted (a candidate that breaks one ranks below every one that doesn't: feasibility
              first, then the objective; the best reported is always feasible). Against the control row:
                guard       every piece's shape IoU per view (sheet_pieces' piece_*, hair_pieces' hair_piece_*) may not
                            drop by more than this relative share (default calibrate.DROP, 0.15: the anti-gaming guard)
                flags       true (default): no flag check's status or calibrated grade gets worse, none goes
                no_new_fail true (default): no graded check goes from PASS or WARN to FAIL
                keep        [patterns]: those checks stay PASS (or no worse than the control, where it isn't PASS)
                proxy_real  true (default): a real-only check's constraints are enforced on the screen's drawing too
                            (against the control in the same drawing), and again on the real builds
  method      'cma' (default; CMA-ES, our own: charkit.optimize.CMA) or 'random' (uniform in the bounds: a baseline)
  seed        0; every generation's draw is seeded from (seed, generation): a run is reproducible and resumable
  sigma0      0.2 (the search's first spread, as a share of each knob's range)
  popsize     'auto' (default): the workers (the free build slots, less --reserve), at least 4 + 3 ln(knobs)
  budget      {evals 300, minutes 120, generations 60}: whichever comes first (evaluations run, cache hits free)
  stop        {tolfun 1e-3, stall 8, tolx 1e-3, target}: stop when the best feasible objective improved by less than
              tolfun over `stall` generations with the search narrowed (every continuous knob's spread under 5% of
              its range; while it is still wide, over three times as many), or the spread fell under tolx (no
              integer knobs), or the best reached target (default 0 when every term is toward 'pass' with no
              margin: everything passes)
  probe       true (default): before the search, each knob one step either side of the start (OAT): the splice set
              (when `objects` isn't declared: what any probe changed), dead knobs (a step that changes nothing),
              and each knob's local effect (sensitivity)
  reference   {NAME: {PATH: value}}: points evaluated beside the search for comparison (a hand-found result)
  confirm     {top 3, spec, args, where 'auto' | 'here' | 'remote', box, control 'auto', compare {NAME: BUILD}}: the
              best `top` distinct feasible candidates built for real (`charkit build`: Blender, the render drawing,
              every QA part), scored against a real build of the control (the base build itself when `set` is empty)
              with every term and constraint, the real-only ones included; the pick is the best confirmed feasible;
              compare: existing builds scored the same way beside them (a hand-found result)
  fidelity    {PATTERN: 'fast' | 'real'}: overrides FIDELITY for this run (a check the audit read differently)

Fidelity (FIDELITY, REAL_PARTS; `optimize audit BUILD` measures it): the screen draws every row with the numpy
drawing (a spliced bundle has no export of its own: charkit/sweep.py), which has no highlights and draws the terminator
and lighting differently from the toon renderer the real build's QA uses. A check whose reading depends on that (the
look's shading, highlights, the terminator, the lit and shaded palette) is real-only: scored at the confirm.

Outputs in OUT: decl.json; history.jsonl (one line per evaluation: its knobs, overrides, objective and terms, the
constraints it broke, every check measured with every piece's shape IoU per view) and history.csv (the same, one column
per check and per piece-view); state.json (the optimizer's state after each generation: resume); opt.json (the summary:
best, stop reason, evaluations, wall, splice set, workers); best_override.json (the best as a spec override: the
sweep's `set` form, and the spec with it applied); history.md (the table); sensitivity.json / .md / .png (per knob:
the OAT probe's effect, the effect across its range fitted on every feasible point and near the best, the rank
correlation, the search's final spread); convergence.png; sweep.json (control, references, best and the top
candidates in the sweep's own form: `charkit sweep table`, review pages); confirm.json; review/ (the review page).

Resume: `--resume` (or the same command again on an OUT holding state.json) carries on from the last finished
generation; the history is the cache, so a generation cut short reruns only what it hadn't evaluated. The
declaration's optimize block must be unchanged (its hash is kept).

    python -m charkit sweep optimize charkit/out/remote/stairs_opt.json --box --out charkit/out/optimize/stairs
"""
import ast, contextlib, copy, fnmatch, hashlib, io, json, math, os, queue, re, subprocess, sys, threading, time

import numpy as np

from . import sweep as sw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RANK = {'PASS': 0, 'WARN': 1, 'FAIL': 2}
STATUS_SEV = {'PASS': 0.0, 'WARN': 0.5, 'FAIL': 1.5}
CONTROL = 'control'
DEFAULTS = dict(method='cma', seed=0, sigma0=0.2, popsize='auto', probe=True,
                budget=dict(evals=300, minutes=120, generations=60),
                stop=dict(tolfun=1e-3, stall=8, tolx=1e-3, target=None),
                constraints=dict(guard=None, flags=True, no_new_fail=True, keep=[], proxy_real=True))
MAX_WORKERS = 16
MIN_QUEUED = 4                # workers queued for slots when a busy machine has fewer free
INT_FLOOR = 0.4               # an integer knob's spread kept at least this many integer steps (it can't stall on a value)
STALL_SPREAD = 0.05           # the stall rule's narrowed search: every continuous knob's spread under this share of its range
MIN_IOU = 0.05                # the guard reads a piece-view whose control IoU is above this (sweep.guard's)

# Real-only checks: the screen's numpy drawing reads them differently from the real build's toon render. Measured by
# `optimize audit BUILD` on opt_base (ad081524, 2026-10-01; charkit/out/optimize/audit_opt_base): of 639 checks over
# every part, 10 read differently (status, or value by more than 2%): the look part's face shadows (face_shadow_neck_3q
# 0.099 real / 0.040 numpy, chin_edge 0.057 / 0.048, 3q 0.30 / 0.33), the terminator (art_terminator_bow 4.83 FAIL /
# 2.37 WARN, collar 5.72 / 8.45), the hem band (art_band_lower 1.111 / 1.238) and the ink fragments (bow 3.17 / 3.05,
# collar 6.49 / 6.64). The palette (palette_*_lit / _shade) and the eyes read the same. Highlights stay real-only (the
# numpy drawing draws none: a check measuring them would read nothing). Patterns over check names; REAL_PARTS: every
# check of these QA parts.
FIDELITY = [
    ('art_terminator_*', 'the terminator as the toon renderer draws it (audit: bow 4.83 real / 2.37 numpy)'),
    ('art_band_*', 'the dark hem band as the renderer shades it (audit: art_band_lower 1.111 / 1.238)'),
    ('art_fragments_*', 'ink fragments as the renderer\'s screen lines draw them (audit: 2-4% off)'),
    ('*highlight*', 'highlights: the numpy drawing has none'),
    ('face_shadow_*', 'the face\'s cast and form shadows (audit: up to 59% off)'),
]
REAL_PARTS = ('look',)


# ------------------------------------------------------------------------------------------------------- the knobs
class Knob:
    """one knob: a spec path (or a name the template reads), its bounds, integer or continuous, linear or log."""

    def __init__(self, d, spec=None):
        self.path = d.get('path')
        self.name = d.get('name') or self.path
        if not self.name:
            raise SystemExit('optimize: a knob needs a path or a name: %r' % (d,))
        self.lo, self.hi = float(d['lo']), float(d['hi'])
        if not self.hi > self.lo:
            raise SystemExit('optimize: knob %s: hi must be above lo' % self.name)
        self.int = bool(d.get('int'))
        self.log = bool(d.get('log'))
        if self.log and self.lo <= 0:
            raise SystemExit('optimize: knob %s: a log knob needs lo > 0' % self.name)
        self.decimals = d.get('round', None if self.int else 4)
        x0 = d.get('x0')
        if x0 is None and self.path and spec is not None:
            try:
                v = sw._get(spec, self.path)
                x0 = v if isinstance(v, (int, float)) and not isinstance(v, bool) else None
            except (KeyError, IndexError, TypeError):
                x0 = None
        self.x0 = float(min(max(x0, self.lo), self.hi)) if x0 is not None else self.from_unit(0.5, raw=True)
        self.step = d.get('step')

    def to_unit(self, x):
        if self.log:
            return (math.log(x) - math.log(self.lo)) / (math.log(self.hi) - math.log(self.lo))
        return (x - self.lo) / (self.hi - self.lo)

    def from_unit(self, u, raw=False):
        u = min(max(float(u), 0.0), 1.0)
        x = math.exp(math.log(self.lo) + u * (math.log(self.hi) - math.log(self.lo))) if self.log else \
            self.lo + u * (self.hi - self.lo)
        if raw:
            return x
        return self.value(x)

    def value(self, x):
        if self.int:
            return int(min(max(round(x), math.ceil(self.lo - 1e-9)), math.floor(self.hi + 1e-9)))
        x = min(max(x, self.lo), self.hi)
        return round(x, self.decimals) if self.decimals is not None else x

    def unit_step(self, sigma0):
        """the first search's spread in unit space."""
        if self.step is None:
            return sigma0
        s = float(self.step)
        if self.log:
            mid = self.x0
            return abs(math.log((mid + s) / mid)) / (math.log(self.hi) - math.log(self.lo)) if mid + s > 0 else sigma0
        return s / (self.hi - self.lo)

    def int_floor(self):
        """an integer knob's least spread in unit space (INT_FLOOR integer steps), else 0."""
        if not self.int:
            return 0.0
        return INT_FLOOR / (self.hi - self.lo) if not self.log else INT_FLOOR / max(1.0, self.hi - self.lo)

    def doc(self):
        return dict(path=self.path, name=self.name, lo=self.lo, hi=self.hi, int=self.int, log=self.log, x0=self.x0)


_OPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b, ast.Pow: lambda a, b: a ** b, ast.Mod: lambda a, b: a % b}
_FUNCS = {'min': min, 'max': max, 'abs': abs, 'round': round}


def expr(text, env):
    """arithmetic over knob names (+ - * / ** %, unary -, min, max, abs, round) -> number. Nothing else is evaluated."""
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.Name):
            if n.id not in env:
                raise SystemExit('optimize: template names %r, which is no knob' % n.id)
            return env[n.id]
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            return -ev(n.operand) if isinstance(n.op, ast.USub) else ev(n.operand)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUNCS and not n.keywords:
            return _FUNCS[n.func.id](*[ev(a) for a in n.args])
        raise SystemExit('optimize: template expression %r: only arithmetic over knob names' % text)
    v = ev(ast.parse(text, mode='eval'))
    if isinstance(v, float) and v == int(v) and all(isinstance(env.get(x), int) for x in re.findall(r'[A-Za-z_]\w*', text)
                                                    if x not in _FUNCS):
        return int(v)
    return round(v, 6) if isinstance(v, float) else v


def fill(tpl, env):
    """a template value with every '=EXPR' string evaluated."""
    if isinstance(tpl, str) and tpl.startswith('='):
        return expr(tpl[1:], env)
    if isinstance(tpl, list):
        return [fill(x, env) for x in tpl]
    if isinstance(tpl, dict):
        return {k: fill(v, env) for k, v in tpl.items()}
    return tpl


class Problem:
    """the declaration's optimize block, parsed: knobs, template, objective terms, constraints, method and limits."""

    def __init__(self, decl, spec=None):
        o = decl.get('optimize') or {}
        if not o.get('knobs'):
            raise SystemExit('optimize: the declaration has no optimize.knobs')
        self.decl = decl
        self.raw = o
        self.knobs = [Knob(k, spec) for k in o['knobs']]
        names = [k.name for k in self.knobs]
        dup = sorted({n for n in names if names.count(n) > 1})
        if dup:
            raise SystemExit('optimize: knobs named twice: %s' % ', '.join(dup))
        self.template = o.get('template') or {}
        self.objective = [dict(t) for t in (o.get('objective') or [])]
        if not self.objective:
            raise SystemExit('optimize: the declaration has no optimize.objective')
        self.constraints = dict(DEFAULTS['constraints'], **(o.get('constraints') or {}))
        if self.constraints.get('guard') is None:
            try:
                from . import calibrate
                self.constraints['guard'] = calibrate.DROP
            except Exception:
                self.constraints['guard'] = 0.15
        self.method = o.get('method', DEFAULTS['method'])
        if self.method not in ('cma', 'random'):
            raise SystemExit('optimize: method %r is not cma or random' % self.method)
        self.seed = int(o.get('seed', DEFAULTS['seed']))
        self.sigma0 = float(o.get('sigma0', DEFAULTS['sigma0']))
        self.popsize = o.get('popsize', DEFAULTS['popsize'])
        self.budget = dict(DEFAULTS['budget'], **(o.get('budget') or {}))
        self.stop = dict(DEFAULTS['stop'], **(o.get('stop') or {}))
        if self.stop.get('target') is None and all(t.get('toward', 'pass') == 'pass' and not t.get('margin')
                                                   for t in self.objective):
            self.stop['target'] = 0.0
        self.probe = bool(o.get('probe', DEFAULTS['probe']))
        self.reference = o.get('reference') or {}
        self.confirm = dict(dict(top=3, spec=None, args=['--boards', '', '--no-blend'], where='auto', box=None,
                                 control='auto'), **(o.get('confirm') or {}))
        self.fidelity = o.get('fidelity') or {}

    def n(self):
        return len(self.knobs)

    def values(self, u):
        """unit coordinates -> {knob name: value} (rounded as each knob rounds)."""
        return {k.name: k.from_unit(x) for k, x in zip(self.knobs, u)}

    def unit(self, vals):
        return np.array([k.to_unit(vals[k.name]) for k in self.knobs])

    def x0(self):
        return {k.name: k.value(k.x0) for k in self.knobs}

    def overrides(self, vals):
        """{knob name: value} -> the row's overrides (the sweep's `set` form): knobs with a path, then the template."""
        over = {k.path: vals[k.name] for k in self.knobs if k.path}
        over.update({p: fill(v, vals) for p, v in self.template.items()})
        return over

    def row_set(self, vals):
        return dict(self.decl.get('set') or {}, **self.overrides(vals))

    def hash(self):
        """the optimize block and what it runs on (base, stage, spec, set, parts, objects): a resume must match."""
        keep = {k: self.decl.get(k) for k in ('base', 'stage', 'spec', 'set', 'parts', 'objects', 'python', 'args')}
        keep['optimize'] = {k: v for k, v in self.raw.items() if k not in ('budget', 'stop', 'confirm')}
        return hashlib.sha1(json.dumps(keep, sort_keys=True, default=str).encode()).hexdigest()[:12]


def key(vals):
    """a candidate's cache key: its knob values (rounded) as canonical JSON."""
    return json.dumps(vals, sort_keys=True, separators=(',', ':'))


# ------------------------------------------------------------------------------------------------------------ CMA-ES
def reflect(y):
    """unbounded genotype -> [0, 1] (mirrored at both bounds: a box constraint the search's distribution never sees)."""
    y = np.mod(np.asarray(y, float), 2.0)
    return np.where(y > 1.0, 2.0 - y, y)


class CMA:
    """(mu/mu_w, lambda)-CMA-ES (Hansen's tutorial, arXiv:1604.00772), on the unit cube through reflect(). Each
    generation's draw is seeded by (seed, generation), so ask() is a function of the state: a run resumes exactly.
    Integer coordinates keep a least spread (floors, unit space): a margin so the search never stalls on one value."""

    def __init__(self, m0, sigma0, lam=None, stds=None, floors=None, seed=0):
        n = len(m0)
        self.n, self.seed = n, int(seed)
        self.lam = int(lam or 4 + int(3 * math.log(n)))
        self.mu = self.lam // 2
        w = math.log(self.mu + 0.5) - np.log(np.arange(1, self.mu + 1))
        self.w = w / w.sum()
        self.mueff = 1.0 / float((self.w ** 2).sum())
        me = self.mueff
        self.cc = (4 + me / n) / (n + 4 + 2 * me / n)
        self.cs = (me + 2) / (n + me + 5)
        self.c1 = 2 / ((n + 1.3) ** 2 + me)
        self.cmu = min(1 - self.c1, 2 * (me - 2 + 1 / me) / ((n + 2) ** 2 + me))
        self.damps = 1 + 2 * max(0.0, math.sqrt((me - 1) / (n + 1)) - 1) + self.cs
        self.chiN = math.sqrt(n) * (1 - 1 / (4 * n) + 1 / (21 * n * n))
        self.m = np.asarray(m0, float).copy()
        self.sigma = float(sigma0)
        s = np.ones(n) if stds is None else np.asarray(stds, float) / self.sigma
        self.C = np.diag(s ** 2)
        self.pc, self.ps = np.zeros(n), np.zeros(n)
        self.floors = np.zeros(n) if floors is None else np.asarray(floors, float)
        self.gen = 0
        self._eig()

    def _eig(self):
        self.C = (self.C + self.C.T) / 2
        d, B = np.linalg.eigh(self.C)
        self.D = np.sqrt(np.maximum(d, 1e-20))
        self.B = B

    def ask(self, gen=None):
        """the generation's genotypes (lam, n): reflect() them for the candidates."""
        g = self.gen if gen is None else gen
        rng = np.random.default_rng([self.seed, g])
        Z = rng.standard_normal((self.lam, self.n))
        return self.m + self.sigma * (Z * self.D) @ self.B.T

    def tell(self, Y, order):
        """Y the generation's genotypes, order their indices best first (feasibility first, then the objective)."""
        n, mu = self.n, self.mu
        Y = np.asarray(Y, float)
        m0 = self.m.copy()
        Ys = (Y[np.asarray(order[:mu])] - m0) / self.sigma
        yw = self.w @ Ys
        self.m = m0 + self.sigma * yw
        inv = self.B @ np.diag(1 / self.D) @ self.B.T
        self.ps = (1 - self.cs) * self.ps + math.sqrt(self.cs * (2 - self.cs) * self.mueff) * (inv @ yw)
        hs = np.linalg.norm(self.ps) / math.sqrt(1 - (1 - self.cs) ** (2 * (self.gen + 1))) / self.chiN < \
            1.4 + 2 / (n + 1)
        self.pc = (1 - self.cc) * self.pc + hs * math.sqrt(self.cc * (2 - self.cc) * self.mueff) * yw
        rank_mu = (Ys.T * self.w) @ Ys
        self.C = (1 - self.c1 - self.cmu) * self.C + self.c1 * (np.outer(self.pc, self.pc) + (1 - hs) * self.cc *
                                                                (2 - self.cc) * self.C) + self.cmu * rank_mu
        self.sigma *= math.exp((self.cs / self.damps) * (np.linalg.norm(self.ps) / self.chiN - 1))
        # (the spread past a whole unit range means nothing on the cube)
        top = self.sigma * math.sqrt(max(float(np.max(np.diag(self.C))), 1e-30))
        if top > 1.0:
            self.sigma /= top
        for i in np.nonzero(self.floors > 0)[0]:
            s = self.sigma * math.sqrt(max(self.C[i, i], 1e-30))
            if s < self.floors[i]:
                f = self.floors[i] / s
                self.C[i, :] *= f
                self.C[:, i] *= f
        self.gen += 1
        self._eig()

    def spread(self):
        """each coordinate's standard deviation (unit space)."""
        return self.sigma * np.sqrt(np.maximum(np.diag(self.C), 0))

    def state(self):
        return dict(n=self.n, lam=self.lam, seed=self.seed, m=self.m.tolist(), sigma=self.sigma, C=self.C.tolist(),
                    pc=self.pc.tolist(), ps=self.ps.tolist(), gen=self.gen, floors=self.floors.tolist())

    @classmethod
    def from_state(cls, s):
        c = cls(np.asarray(s['m']), s['sigma'], lam=s['lam'], seed=s['seed'], floors=s.get('floors'))
        c.C = np.asarray(s['C'], float)
        c.pc, c.ps = np.asarray(s['pc'], float), np.asarray(s['ps'], float)
        c.gen = int(s['gen'])
        c._eig()
        return c


class Uniform:
    """method 'random': each generation uniform in the cube (a baseline to judge the search against)."""

    def __init__(self, n, lam, seed=0):
        self.n, self.lam, self.seed, self.gen = n, lam, seed, 0
        self.m, self.sigma = np.full(n, 0.5), 1.0

    def ask(self, gen=None):
        return np.random.default_rng([self.seed, self.gen if gen is None else gen, 7]).random((self.lam, self.n))

    def tell(self, Y, order):
        self.gen += 1

    def spread(self):
        return np.full(self.n, 1 / math.sqrt(12))

    def state(self):
        return dict(n=self.n, lam=self.lam, seed=self.seed, gen=self.gen, method='random')

    @classmethod
    def from_state(cls, s):
        u = cls(s['n'], s['lam'], s['seed'])
        u.gen = s['gen']
        return u


# --------------------------------------------------------------------------------------------- fidelity and limits
def fidelity(check, part=None, extra=None):
    """'real' when the screen's drawing can't read the check as the real build does (FIDELITY, REAL_PARTS, a run's own
    `fidelity` map first), else 'fast'."""
    for pat, v in (extra or {}).items():
        if fnmatch.fnmatchcase(check, pat):
            return v
    if part in REAL_PARTS:
        return 'real'
    return 'real' if any(fnmatch.fnmatchcase(check, p) for p, _ in FIDELITY) else 'fast'


_DECL = None


def declared_limits():
    """{check: (pass, warn, better)} from every declaration (charkit.declared), '{view}' expanded."""
    global _DECL
    if _DECL is None:
        _DECL = {}
        try:
            from . import declared
            for name, _, d in declared.expand(declared.declarations()):
                try:
                    p, w = declared.limits_of(d)
                except Exception:
                    continue
                better = d.get('better') or ('higher' if d.get('family') == 'shape_iou' else 'lower')
                _DECL[name] = (float(p), float(w), better)
        except Exception:
            pass
    return _DECL


def limits_for(check, term=None):
    """a check's grading for a 'pass' term -> (kind, pass, warn) or None: the term's own limits (better 'lower'
    default, or 'higher'), the check's declaration, charkit.checks' table."""
    term = term or {}
    if term.get('limits'):
        p, w = term['limits']
        return ('hi' if term.get('better') == 'higher' else 'lo'), float(p), float(w)
    d = declared_limits().get(check)
    if d:
        return ('hi' if d[2] == 'higher' else 'lo'), d[0], d[1]
    try:
        from . import checks
        kind, p, w, _ = checks.rule(check)
        if kind != 'status':
            return kind, float(p), float(w)
    except Exception:
        pass
    return None


def raw_severity(lim, v):
    """charkit.checks.severity's reading without its floor at 0: negative inside PASS (a margin's reward)."""
    kind, p, w = lim
    band = abs(w - p) or 1.0
    v = float(v)
    if kind == 'hi':
        return (p - v) / band
    if kind == 'lo':
        return (v - p) / band
    if kind == 'ratio':
        return (abs(v - 1) - p) / band
    if kind == 'abs':
        return (abs(v) - p) / band
    return 0.5 * v


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x == x


def field(c, path):
    cur = c
    for k in path.split('.'):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


# ---------------------------------------------------------------------------------------------- objective, constraints
class Scorer:
    """the objective's terms (expanded on the control's checks) and the constraints against the control -> each
    candidate's objective f, violation v (0: feasible) and why."""

    def __init__(self, P, control, mode='fast', log=print):
        self.P, self.ctrl, self.mode = P, control or {}, mode
        self.terms, self.left_out, self.warnings = [], [], []
        for t in P.objective:
            pat = t['check']
            got = [k for k in self.ctrl if fnmatch.fnmatchcase(k, pat)] if any(ch in pat for ch in '*?[') else [pat]
            if not got:
                self.warnings.append('objective %r matches no check the control measured' % pat)
            for k in got:
                c = self.ctrl.get(k) or {}
                fid = fidelity(k, c.get('part'), P.fidelity)
                tt = dict(t, check=k, fidelity=fid)
                tt['field'] = t.get('field') or ('views.' + t['view'] if t.get('view') else 'value')
                if tt.get('toward', 'pass') == 'pass':
                    tt['lim'] = limits_for(k, t)
                    if tt['lim'] is None:
                        self.warnings.append('%s: no limits known (give the term limits and better): graded by '
                                             'status alone' % k)
                if fid == 'real' and mode == 'fast' and not t.get('proxy'):
                    self.left_out.append(k)
                    continue
                self.terms.append(tt)
        for w in self.warnings:
            log('optimize: ' + w)
        if not self.terms:
            raise SystemExit('optimize: no objective term left to screen (real-only: %s): run with fidelity real, or '
                             'proxy: true on the term' % ', '.join(self.left_out))

    def term(self, t, C):
        c = C.get(t['check'])
        if not isinstance(c, dict):
            return None
        v = field(c, t['field'])
        w = float(t.get('weight', 1.0))
        how = t.get('toward', 'pass')
        if how == 'pass':
            if t.get('lim') and _num(v):
                return w * max(raw_severity(t['lim'], v), -float(t.get('margin', 0.0)))
            s = STATUS_SEV.get(c.get('grade') or c.get('status'))
            return None if s is None else w * s
        if not _num(v):
            return None
        sc = float(t.get('scale', 1.0)) or 1.0
        if how == 'max':
            return -w * v / sc
        if how == 'min':
            return w * v / sc
        if how == 'target':
            tg = float(t['target'])
            if t.get('log'):
                return w * abs(math.log(max(v, 1e-12) / tg)) / sc
            return w * abs(v - tg) / sc
        raise SystemExit('optimize: toward %r is not pass, max, min or target' % how)

    def _real_ok(self, k, c):
        """is a check's constraint read in this mode? (a real-only one on the screen: only as a proxy)."""
        if self.mode != 'fast':
            return True
        return fidelity(k, (c or {}).get('part'), self.P.fidelity) == 'fast' or self.P.constraints.get('proxy_real',
                                                                                                    True)

    def violations(self, C):
        """the constraints a candidate's checks break against the control -> [dict(kind, check, view, control, row,
        amount)]: guard (amount: the drop past the limit, in limits), flag, new_fail, keep (amount: status steps,
        plus the severity's move where limits are known), missing."""
        P, C0 = self.P, self.ctrl
        K = P.constraints
        out = []
        drop = float(K.get('guard') or 0.15)
        if drop > 0:
            for k, c0 in C0.items():
                if not sw.SHAPE_CHECK.match(k) or not isinstance(c0, dict) or not isinstance(c0.get('views'), dict):
                    continue
                c1 = C.get(k) or {}
                v1 = c1.get('views') if isinstance(c1.get('views'), dict) else {}
                for view, a in c0['views'].items():
                    if not _num(a) or a <= MIN_IOU:
                        continue
                    b = v1.get(view)
                    b = 0.0 if not _num(b) else b
                    rel = (a - b) / a
                    if rel > drop:
                        out.append(dict(kind='guard', check=k, view=view, control=a, row=b, rel=round(-rel, 4),
                                        amount=(rel - drop) / drop))

        def st(c):
            return (c or {}).get('grade') or (c or {}).get('status')

        def sev_move(k, c0, c1):
            lim = limits_for(k)
            if lim and _num((c0 or {}).get('value')) and _num((c1 or {}).get('value')):
                return max(0.0, raw_severity(lim, c1['value']) - raw_severity(lim, c0['value']))
            return 0.0
        from . import registry
        keep = K.get('keep') or []
        names = set(C0) | set(C)
        for k in sorted(names):
            c0, c1 = C0.get(k), C.get(k)
            if not self._real_ok(k, c0 or c1):
                continue
            s0, s1 = st(c0), st(c1)
            if K.get('flags', True) and (registry.is_flag(c0) or registry.is_flag(c1)) and s0 in RANK:
                if s1 not in RANK:
                    out.append(dict(kind='flag', check=k, control=s0, row=s1 or 'gone', amount=1.0))
                elif RANK[s1] > RANK[s0]:
                    out.append(dict(kind='flag', check=k, control=s0, row=s1,
                                    amount=RANK[s1] - RANK[s0] + 0.25 * sev_move(k, c0, c1)))
                    continue
            if K.get('no_new_fail', True) and s0 in ('PASS', 'WARN') and s1 == 'FAIL':
                out.append(dict(kind='new_fail', check=k, control=s0, row=s1, amount=1.0 + 0.25 * sev_move(k, c0, c1)))
                continue
            if keep and any(fnmatch.fnmatchcase(k, p) for p in keep) and s0 in RANK:
                need = RANK['PASS'] if s0 == 'PASS' else RANK[s0]
                if s1 not in RANK or RANK[s1] > need:
                    out.append(dict(kind='keep', check=k, control=s0, row=s1 or 'gone',
                                    amount=(RANK.get(s1, 2) - need) + 0.25 * sev_move(k, c0, c1)))
        return out

    def score(self, C, error=None):
        """-> dict(f, v, feasible, terms {check: contribution}, viol [..])."""
        if error is not None or C is None:
            return dict(f=None, v=float('inf'), feasible=False, terms={}, viol=[dict(kind='error', why=str(error))])
        terms, f, viol = {}, 0.0, []
        for t in self.terms:
            x = self.term(t, C)
            if x is None:
                viol.append(dict(kind='missing', check=t['check'], amount=1.0))
                continue
            terms[t['check'] + ('' if t['field'] == 'value' else ':' + t['field'])] = round(x, 6)
            f += x
        viol += self.violations(C)
        v = round(sum(x.get('amount', 0.0) for x in viol), 6)
        return dict(f=round(f, 6), v=v, feasible=v <= 0, terms=terms, viol=viol)


def rank_key(r):
    """feasibility first, then the objective (an infeasible row by its violation)."""
    v = r.get('v')
    v = float('inf') if v is None else v
    if v > 0:
        return (1, v, 0.0)
    return (0, 0.0, r['f'] if r.get('f') is not None else float('inf'))


# ------------------------------------------------------------------------------------------------- evaluation context
class Context:
    """what one process needs to evaluate rows: the sweep's stage (its context made once: the base bundle, the spec,
    the evaluator) and the parts, or a python evaluator (stage 'python': `python` 'MODULE:FACTORY', FACTORY(decl) ->
    an object with evaluate(set) -> {check: dict})."""

    def __init__(self, decl, out, log=print):
        self.decl, self.out, self.log = decl, out, log
        t0 = time.time()
        self.ctrl_geo = None
        if decl.get('stage') == 'python':
            mod, _, fn = decl['python'].partition(':')
            import importlib
            self.fn = getattr(importlib.import_module(mod), fn)(decl)
            self.S = None
        else:
            dd = dict(decl, _out=out)
            self.B0 = sw.load_bundle(decl['base'], decl.get('rebase', True))
            self.spec = sw.base_spec(dd, self.B0)
            sw.produce(self.spec)
            self.S = sw.STAGE[decl['stage']](dd, self.B0, self.spec)
            self.parts = list(dict.fromkeys(list(decl.get('parts') or ()) + list(decl.get('shape_parts',
                                                                                           sw.SHAPE_PARTS))))
        self.seconds = round(time.time() - t0, 1)

    def geometry(self, row):
        if self.S is None:
            return {}
        return self.S.objects(row, os.path.join(self.out, 'rows', sw._safe(row['name'])))

    def changed(self, geo):
        """the objects a row's rebuild changed against the control's (the control rebuilt once, in this process)."""
        if self.S is None:
            return []
        if self.ctrl_geo is None:
            self.ctrl_geo = self.geometry(dict(name=CONTROL, set=dict(self.decl.get('set') or {})))
        return sorted(n for n in set(geo) | set(self.ctrl_geo) if sw._changed(geo.get(n), self.ctrl_geo.get(n)))

    def evaluate(self, row, objects=None, board=None):
        """one row: rebuilt, spliced (objects: the run's splice set; None: what it changed), measured -> rec."""
        t = time.time()
        if self.S is None:
            C = self.fn.evaluate(dict(row['set']))
            return dict(name=row['name'], checks=sw._plain(C), seconds=round(time.time() - t, 2), seconds_build=0.0,
                        spliced=[], changed=[])
        geo = self.geometry(row)
        tb = round(time.time() - t, 1)
        ch = self.changed(geo)
        names = ch if objects is None else objects
        objs = {n: o for n, o in geo.items() if n in set(names)}
        B = self.S.bundle(objs)
        C = sw.measure(B, self.parts, row['set'])
        rec = dict(name=row['name'], checks=sw.kept(C), seconds=round(time.time() - t, 1), seconds_build=tb,
                   spliced=sorted(objs), changed=ch)
        if board:
            try:
                os.makedirs(os.path.dirname(board), exist_ok=True)
                rec['board'] = sw.board(B, os.path.dirname(board), name=os.path.basename(board),
                                        **(self.decl.get('boards') or {}))
            except Exception as e:                      # (a picture is optional)
                rec['board_error'] = '%s: %s' % (type(e).__name__, e)
        return rec

    def changes(self, row):
        """a row's rebuild only: the objects it changes against the control (the probe's splice set)."""
        if self.S is None:
            return dict(name=row['name'], changed=[])
        return dict(name=row['name'], changed=self.changed(self.geometry(row)))


def serve(decl_path, out, wid=0):
    """`sweep worker DECL --out OUT`: one worker. It takes a build slot, makes the context once, then answers JSON lines
    on stdin ({id, op: eval | changes | stop, row, objects, board}) on its protocol stream (the original stdout; stdout
    itself goes to stderr, so a stage's prints can't break the protocol)."""
    proto = os.fdopen(os.dup(1), 'w', buffering=1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    from . import procs
    lock = procs.acquire_slot('optimize') if os.environ.get('CHARKIT_OPT_SLOT', '1') == '1' else None
    try:
        decl = json.load(open(decl_path))
        try:
            ctx = Context(decl, out)
        except BaseException as e:
            import traceback
            traceback.print_exc()
            proto.write(json.dumps(dict(ready=False, error='%s: %s' % (type(e).__name__, e))) + '\n')
            return 1
        proto.write(json.dumps(dict(ready=True, pid=os.getpid(), seconds=ctx.seconds, wid=wid)) + '\n')
        for line in sys.stdin:
            if not line.strip():
                continue
            req = json.loads(line)
            if req.get('op') == 'stop':
                break
            try:
                if req.get('op') == 'changes':
                    rec = ctx.changes(req['row'])
                else:
                    rec = ctx.evaluate(req['row'], req.get('objects'), req.get('board'))
                proto.write(json.dumps(dict(id=req['id'], rec=rec)) + '\n')
            except Exception as e:
                import traceback
                traceback.print_exc()
                proto.write(json.dumps(dict(id=req['id'], error='%s: %s' % (type(e).__name__, e))) + '\n')
    finally:
        if lock is not None:
            lock.close()
    return 0


class InProc:
    """the evaluator in this process (one worker's work, serially): tests, and a laptop's one slot."""

    def __init__(self, decl, out, log=print):
        self.ctx = Context(decl, out, log)
        self.n = 1
        self.context_seconds = self.ctx.seconds

    def run(self, reqs, on_result=None):
        out = []
        for i, r in enumerate(reqs):
            try:
                rec = self.ctx.changes(r['row']) if r.get('op') == 'changes' else \
                    self.ctx.evaluate(r['row'], r.get('objects'), r.get('board'))
                msg = dict(rec=rec, worker=0)
            except Exception as e:
                import traceback
                traceback.print_exc()
                msg = dict(error='%s: %s' % (type(e).__name__, e), worker=0)
            out.append(msg)
            if on_result:
                on_result(i, msg)
        return out

    def close(self):
        pass


class _Batch:
    """one run()'s rows: their replies as they come, and a wait that ends when every row has one."""

    def __init__(self, n, on_result):
        self.res, self.left, self.on_result = [None] * n, n, on_result
        self.cv = threading.Condition()

    def done(self, i, msg):
        with self.cv:
            if self.res[i] is not None:
                return
            self.res[i] = msg
        try:
            if self.on_result:                          # (recorded before the row counts as done: run() returns
                self.on_result(i, msg)                  # only once every row's entry is written)
        finally:
            with self.cv:
                self.left -= 1
                self.cv.notify_all()


class Pool:
    """n persistent workers (`sweep worker`), each a fresh interpreter (fork+exec, so no fork-after-threads hazard) in a
    build slot with its own context, all fed from one queue. A worker joins as soon as it has its slot and context (on
    a busy box the pool starts with those ready and grows as slots free up); one that dies has its row run again once
    by another (a row that kills two fails)."""

    RETRIES = 1

    def __init__(self, decl_path, out, n, log=print, env=None):
        self.log, self.out = log, out
        self.procs, self.logs, self.threads = [], [], []
        self.jobs = queue.Queue()
        self.state = {}                                  # worker -> 'starting' | 'ready' | 'failed' | 'dead'
        self.secs = {}
        self.cv = threading.Condition()
        os.makedirs(os.path.join(out, 'workers'), exist_ok=True)
        cmd = [sys.executable, '-m', 'charkit', 'sweep', 'worker', decl_path, '--out', out]
        log('optimize: starting %d workers (each takes a build slot, then makes the stage\'s context; the pool starts '
            'with the first ready and grows; logs %s)' % (n, os.path.join(out, 'workers')))
        for i in range(n):
            lf = open(os.path.join(out, 'workers', 'worker_%d.log' % i), 'a')
            p = subprocess.Popen(cmd + ['--id', str(i)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=lf,
                                 text=True, bufsize=1, cwd=ROOT, env=dict(os.environ, **(env or {})))
            self.procs.append(p)
            self.logs.append(lf)
            self.state[i] = 'starting'
        for i in range(n):
            t = threading.Thread(target=self._serve, args=(i,), daemon=True)
            t.start()
            self.threads.append(t)
        t0 = time.time()
        with self.cv:
            while not any(s == 'ready' for s in self.state.values()) and \
                    any(s == 'starting' for s in self.state.values()):
                self.cv.wait(30)
                if time.time() - t0 > 300 and not any(s == 'ready' for s in self.state.values()):
                    t0 = time.time()
                    log('optimize: no worker ready yet (waiting for build slots: `python -m charkit ps`)')
        if not any(s == 'ready' for s in self.state.values()):
            self.close()
            raise SystemExit('optimize: no worker started (see %s)' % os.path.join(out, 'workers'))

    @property
    def n(self):
        return max(1, sum(1 for s in self.state.values() if s == 'ready'))

    @property
    def context_seconds(self):
        return round(max(self.secs.values()), 1) if self.secs else None

    def _set(self, w, s):
        with self.cv:
            self.state[w] = s
            self.cv.notify_all()

    def _serve(self, w):
        p = self.procs[w]
        line = p.stdout.readline()
        try:
            msg = json.loads(line) if line else dict(ready=False, error='exited before it was ready')
        except ValueError:
            msg = dict(ready=False, error='bad line %r' % line[:200])
        if not msg.get('ready'):
            self.log('optimize: worker %d failed to start: %s (%s)' % (
                w, msg.get('error'), os.path.join(self.out, 'workers', 'worker_%d.log' % w)))
            self._set(w, 'failed')
            return
        self.secs[w] = msg.get('seconds') or 0.0
        self._set(w, 'ready')
        self.log('optimize: worker %d ready (pid %s, context %s s; %d ready)' % (w, msg.get('pid'), msg.get('seconds'),
                                                                               self.n))
        while True:
            item = self.jobs.get()
            if item is None:
                return
            batch, i, req, tries = item
            try:
                p.stdin.write(json.dumps(dict(req, id=i)) + '\n')
                p.stdin.flush()
                line = p.stdout.readline()
                reply = json.loads(line) if line else None
            except (OSError, ValueError):
                reply = None
            if reply is None:
                self.log('optimize: worker %d died on row %s (%s)' % (w, req['row']['name'], os.path.join(
                    self.out, 'workers', 'worker_%d.log' % w)))
                self._set(w, 'dead')
                if tries < self.RETRIES and self._alive():
                    self.jobs.put((batch, i, req, tries + 1))
                else:
                    batch.done(i, dict(error='worker %d died' % w, worker=w))
                return
            reply.pop('id', None)
            reply['worker'] = w
            batch.done(i, reply)

    def _alive(self):
        return any(s in ('ready', 'starting') for s in self.state.values())

    def run(self, reqs, on_result=None):
        batch = _Batch(len(reqs), on_result)
        for i, r in enumerate(reqs):
            self.jobs.put((batch, i, r, 0))
        with batch.cv:
            while batch.left:
                batch.cv.wait(15)
                if batch.left and not self._alive():
                    break
        if batch.left:                                   # (every worker gone: what's left fails)
            while True:
                try:
                    b, i, r, _ = self.jobs.get_nowait()
                except queue.Empty:
                    break
                b.done(i, dict(error='no worker left'))
            for i, x in enumerate(batch.res):
                if x is None:
                    batch.done(i, dict(error='no worker left'))
        return batch.res

    def close(self):
        for _ in self.threads:
            self.jobs.put(None)
        for p in self.procs:
            try:
                if p.poll() is None:
                    p.stdin.write(json.dumps(dict(op='stop')) + '\n')
                    p.stdin.flush()
                    p.stdin.close()
            except (OSError, ValueError):
                pass
        for p in self.procs:
            try:
                p.wait(timeout=60)
            except subprocess.TimeoutExpired:
                p.kill()
        for f in self.logs:
            f.close()


def free_slots():
    """(the machine's build slots, those free now): the box's /proc locks (charkit.boxjob), else charkit.procs'."""
    from . import procs
    total = procs.slots()
    try:
        held = len(procs.slot_holders())
    except Exception:
        held = 0
    waiting = 0
    if sys.platform.startswith('linux'):
        try:
            from . import boxjob
            waiting = int(boxjob.slots_now(procs.SLOTS_DIR).get('waiting') or 0)
        except Exception:
            pass
    return total, max(0, total - held - waiting)


def load_decl(decl):
    """a declaration (path or dict) -> dict, its base absolute: the sweep's (charkit.sweep.load_decl), with the
    'python' stage too."""
    if isinstance(decl, str):
        path = sw._abs(decl)
        decl = json.load(open(path))
        decl.setdefault('_dir', os.path.dirname(path))
    d = dict(decl)
    d.setdefault('stage', 'qa')
    if d['stage'] == 'python':
        if not d.get('python'):
            raise SystemExit('optimize: stage python needs `python`: "MODULE:FACTORY"')
        if d.get('base'):
            d['base'] = sw._abs(d['base'])
        return d
    return sw.load_decl(d)


# ---------------------------------------------------------------------------------------------------------- the run
class Run:
    """one optimization: its folder, history (the cache), state and limits."""

    def __init__(self, decl, out, workers='auto', reserve=1, log=print, inproc=False, overrides=None):
        self.out = sw._abs(out)
        os.makedirs(self.out, exist_ok=True)
        self.decl = load_decl(decl)
        ov = overrides or {}
        o = self.decl.setdefault('optimize', {})
        for k in ('seed',):
            if ov.get(k) is not None:
                o[k] = ov[k]
        if ov.get('evals') or ov.get('minutes'):
            o['budget'] = dict(o.get('budget') or {}, **{k: ov[k] for k in ('evals', 'minutes') if ov.get(k)})
        if ov.get('confirm') is not None:
            o['confirm'] = dict(o.get('confirm') or {}, top=ov['confirm'])
        self.log = log
        self.inproc = inproc
        self.workers_req, self.reserve = workers, reserve
        self.decl_path = os.path.join(self.out, 'decl.json')
        self.H = []                                      # the history: one dict per evaluation
        self.cache = {}                                  # key -> history index of its first evaluation
        self.t0 = time.time()

    # -- files
    def path(self, *p):
        return os.path.join(self.out, *p)

    def _write_decl(self):
        json.dump({k: v for k, v in self.decl.items() if not k.startswith('_')}, open(self.decl_path, 'w'), indent=1)

    def load_history(self):
        p = self.path('history.jsonl')
        self.H, self.cache = [], {}
        if os.path.exists(p):
            for line in open(p):
                if line.strip():
                    try:
                        h = json.loads(line)
                    except ValueError:              # (a line cut short by a crash)
                        continue
                    self.H.append(h)
                    if h.get('key') and not h.get('cached') and h['key'] not in self.cache and not h.get('error'):
                        self.cache[h['key']] = len(self.H) - 1

    def append(self, h):
        self.H.append(h)
        if h.get('key') and not h.get('cached') and h['key'] not in self.cache and not h.get('error'):
            self.cache[h['key']] = len(self.H) - 1
        with open(self.path('history.jsonl'), 'a') as f:
            f.write(json.dumps(h) + '\n')

    # -- the evaluator
    def evaluator(self, n):
        if self.inproc or n <= 1 and self.decl.get('stage') == 'python':
            return InProc(self.decl, self.out, self.log)
        env = {}
        if self.decl.get('stage') == 'python':
            env['CHARKIT_OPT_SLOT'] = '0'               # (a python evaluator is light: no build slot)
        return Pool(self.decl_path, self.out, n, self.log, env)

    def n_workers(self, lam_default):
        if isinstance(self.workers_req, int) or (isinstance(self.workers_req, str) and self.workers_req.isdigit()):
            return max(1, int(self.workers_req))
        total, free = free_slots()
        # the free slots less the reserve; on a busy machine at least MIN_QUEUED (they wait for slots and join the
        # pool as they get them)
        floor = max(1, min(MIN_QUEUED, total - int(self.reserve)))
        n = max(floor, min(MAX_WORKERS, free - int(self.reserve)))
        self.log('optimize: %d build slots, %d free: %d workers (reserve %d%s)' % (
            total, free, n, self.reserve, '; queued for slots' if n > free else ''))
        return n

    # -- evaluating candidates
    def evaluate(self, E, cands, objects, boards=()):
        """cands [dict(name, vals, kind, gen, y)] -> their history entries in cands' order (cache hits free; the rest
        in parallel, each written to the history as it finishes, so an interrupted batch keeps what it had done).
        boards: the names whose board is drawn (the declaration's `boards`)."""
        todo = []
        for c in cands:
            k = c.get('key') or key(c['vals'])
            c['key'] = k
            if k in self.cache or any(t['key'] == k for t in todo):
                continue
            todo.append(c)
        rs = lambda c: dict(c['set']) if 'set' in c else self.P.row_set(c['vals'])
        reqs = [dict(op='eval', row=dict(name=c['name'], set=rs(c)), objects=objects,
                     board=self.path('boards', sw._safe(c['name']) + '.png') if c['name'] in boards else None)
                for c in todo]
        lock = threading.Lock()
        fresh = {}

        def head(c):
            return dict(name=c['name'], kind=c['kind'], gen=c.get('gen'), knobs=c['vals'],
                        u=[round(x, 6) for x in self.P.unit(c['vals'])], key=c['key'],
                        y=None if c.get('y') is None else [round(float(x), 8) for x in c['y']])

        def done(j, r):
            c = todo[j]
            rec = r.get('rec') or {}
            sc = self.scorer.score(rec.get('checks'), r.get('error')) if self.scorer else {}
            h = dict(head(c), set=rs(c), checks=rec.get('checks'), seconds=rec.get('seconds'),
                     seconds_build=rec.get('seconds_build'), spliced=rec.get('spliced'), changed=rec.get('changed'),
                     worker=r.get('worker'), error=r.get('error'), board=rec.get('board'), **sc)
            if rec.get('board_error'):
                h['board_error'] = rec['board_error']
            if objects is not None and rec.get('changed') and set(rec['changed']) - set(objects):
                h['unspliced'] = sorted(set(rec['changed']) - set(objects))
            with lock:
                h['i'], h['t'] = len(self.H), round(time.time() - self.t0, 1)
                self.append(h)
                fresh[c['key']] = h
                # (a line per finished row: a stalled worker shows within one row's time, not a generation's)
                self.log('    %-14s %s  f %s v %s  %s s  worker %s  [%d/%d]%s' % (
                    c['name'], ' '.join('%s=%s' % (k, _fmt(v)) for k, v in c['vals'].items())[:90], _fmt(h.get('f')),
                    _fmt(h.get('v')), h.get('seconds'), h.get('worker'), len(fresh), len(todo),
                    ('  ERROR ' + str(h['error'])[:120]) if h.get('error') else ''))
        t = time.time()
        if reqs:
            E.run(reqs, on_result=done)
        wall = time.time() - t
        out = []
        for c in cands:
            k = c['key']
            h = fresh.get(k)
            if h is not None and h['name'] == c['name']:
                out.append(h)
                continue
            src = h if h is not None else (self.H[self.cache[k]] if k in self.cache else None)
            h = dict(head(c), cached=True, source=src['name'] if src else None, i=len(self.H),
                     t=round(time.time() - self.t0, 1))
            for f in ('f', 'v', 'feasible', 'terms', 'viol', 'error'):
                h[f] = src.get(f) if src else None
            self.append(h)
            out.append(h)
        n_new = len(todo)
        if n_new:
            self.log('  %d evaluated in %.0f s (%.1f s a row over %d workers)%s' % (
                n_new, wall, wall * E.n / max(1, n_new), E.n,
                '; %d from the cache' % (len(cands) - n_new) if len(cands) > n_new else ''))
        return out

    def best(self, kinds=('cma', 'probe', 'start', 'partial')):
        """the best feasible evaluation of the search (control and references aside) -> history entry or None."""
        got = [h for h in self.H if h.get('kind') in kinds and h.get('f') is not None and not h.get('cached')]
        got.sort(key=lambda h: (rank_key(h), h['i']))
        return got[0] if got and got[0].get('feasible') else (got[0] if got else None)

    def n_evals(self):
        return sum(1 for h in self.H if not h.get('cached') and h.get('kind') != 'confirm')

    # -- the search
    def run(self, resume=False, confirm=True, plan_only=False):
        d = self.decl
        spec = None
        if d.get('stage') != 'python':
            B0 = sw.load_bundle(d['base'], d.get('rebase', True))
            spec = sw.apply(copy.deepcopy(B0._meta.get('spec') or {}), d.get('set') or {})
        self.P = P = Problem(d, spec)
        self._spec = spec
        state_p = self.path('state.json')
        st = json.load(open(state_p)) if os.path.exists(state_p) else None
        n = P.n()
        lam_default = 4 + int(3 * math.log(n)) if n > 1 else 4
        if plan_only:
            return self.plan(lam_default)
        if st and not resume:
            raise SystemExit('optimize: %s holds a run (state.json): --resume to carry on, or another --out' % self.out)
        if st and st.get('hash') != P.hash():
            raise SystemExit('optimize: the declaration changed since %s was started (hash %s, now %s): another --out' % (
                self.out, st.get('hash'), P.hash()))
        if not st and os.path.exists(self.path('history.jsonl')):
            os.remove(self.path('history.jsonl'))
        self._write_decl()
        self.load_history()
        if st and st.get('done'):
            self.log('optimize: %s finished (%s): its confirm and reports' % (self.out, st.get('stop')))
            ctrl = next((h for h in self.H if h.get('kind') == 'control'), None)
            self.scorer = Scorer(P, (ctrl or {}).get('checks') or {}, log=lambda *_: None)
            if confirm and not st.get('confirmed') and P.confirm.get('top'):
                self.confirm_stage(st)
            report(self.out, log=self.log)
            return json.load(open(self.path('opt.json')))
        W = self.n_workers(lam_default)
        lam = int(st['lam']) if st else (int(P.popsize) if str(P.popsize).isdigit() else max(lam_default, W))
        W = min(W, lam)
        self.log('optimize: %d knobs, population %d, %d workers, method %s, seed %d, budget %s' % (
            n, lam, W, P.method, P.seed, P.budget))
        self.scorer = None
        E = self.evaluator(W)
        meta = dict(st or {}, hash=P.hash(), lam=lam, workers=E.n, context_seconds=E.context_seconds,
                    started=(st or {}).get('started') or time.strftime('%Y-%m-%dT%H:%M:%S'),
                    seconds_before=(st or {}).get('seconds_total', 0.0))
        O = None
        try:
            objects = self.splice_set(E, meta)
            meta['objects'] = objects
            self.write_state(meta, None)
            # the control, the start, the probe and the references (on a resume: only those it hadn't evaluated)
            x0 = P.x0()
            # (the control: the base spec with `set` alone, whatever the knobs' template would make of its values)
            first = [dict(name=CONTROL, vals=self.control_vals(), kind='control', gen=-2, key='"control"',
                          set=dict(d.get('set') or {})),
                     dict(name='start', vals=x0, kind='start', gen=-1)]
            if P.probe:
                first += self.probe_rows(x0)
            for name, over in P.reference.items():
                first.append(dict(name='ref_' + name, vals=self.ref_vals(over), kind='reference', gen=-1))
            have = {h['name'] for h in self.H}
            first = [c for c in first if c['name'] not in have]
            if first:
                bnames = {CONTROL, 'start'} | {'ref_' + n for n in P.reference} if d.get('boards') else ()
                self.evaluate(E, first, objects, boards=bnames)
            ctrl = next(h for h in self.H if h['kind'] == 'control')
            if ctrl.get('error'):
                raise SystemExit('optimize: the control failed: %s' % ctrl['error'])
            self.scorer = Scorer(P, ctrl['checks'], log=self.log)
            for h in self.H:                                # (scored now the control is known)
                self.rescore(h)
            self.rewrite_history()
            meta['dead'] = self.dead_knobs()
            meta['left_out'] = self.scorer.left_out
            meta['warnings'] = self.scorer.warnings
            for k in meta['dead']:
                self.log('optimize: knob %s: a step either side of its start moves no check (dead: its path doesn\'t '
                         'reach the stage, or its step is too small)' % k)
            s0 = next((h for h in self.H if h['kind'] == 'start'), {})
            self.log('optimize: control f %s v %s; start f %s v %s' % (ctrl.get('f'), ctrl.get('v'), s0.get('f'),
                                                                       s0.get('v')))
            # the search
            O = self.optimizer(st, lam)
            best_hist = list(meta.get('best_hist') or [])
            while True:
                stop = self.should_stop(O, best_hist, meta)
                if stop:
                    break
                g = O.gen
                Y = O.ask()
                U = reflect(Y) if P.method == 'cma' else Y
                cands = [dict(name='g%02d_%02d' % (g, k), vals=P.values(u), kind='cma', gen=g, y=y)
                         for k, (u, y) in enumerate(zip(U, Y))]
                part = [h for h in self.H if h.get('kind') == 'cma' and h.get('gen') == g]
                if part:                                     # (a generation cut short: kept as the cache)
                    for h in part:
                        h['kind'] = 'partial'
                    self.rewrite_history()
                hs = self.evaluate(E, cands, objects)
                order = sorted(range(len(hs)), key=lambda k: (rank_key(hs[k]), k))
                O.tell(Y, order)
                b = self.best()
                best_hist.append(b['f'] if b and b.get('feasible') else None)
                feas = sum(1 for h in hs if h.get('feasible'))
                self.log('gen %2d: %d/%d feasible, its best f %s; best so far %s f %s v %s; sigma %.4f; %d evaluations, '
                         '%.0f s' % (g, feas, len(hs), hs[order[0]].get('f'), b['name'] if b else '-',
                                     b.get('f') if b else None, b.get('v') if b else None,
                                     float(getattr(O, 'sigma', float('nan'))), self.n_evals(),
                                     meta['seconds_before'] + time.time() - self.t0))
                meta['best_hist'] = best_hist
                meta['sigma_hist'] = list(meta.get('sigma_hist') or []) + [float(getattr(O, 'sigma', 0.0))]
                meta['mean_hist'] = list(meta.get('mean_hist') or []) + [[round(float(x), 6) for x in reflect(O.m)]]
                self.write_state(meta, O)
            meta['stop'] = stop
            meta['workers'] = max(meta.get('workers') or 0, E.n)
            self.log('optimize: stopped: %s' % stop)
            if d.get('boards'):
                self.boards(E, objects)
            meta['done'] = True
            self.write_state(meta, O)
        finally:
            E.close()
        if confirm and P.confirm.get('top'):
            self.confirm_stage(json.load(open(state_p)))
        report(self.out, log=self.log)
        return json.load(open(self.path('opt.json')))

    def control_vals(self):
        """the control's knob values: the base spec's (with `set`) at each knob's path, else its start."""
        vals = {}
        spec = self._spec
        for k in self.P.knobs:
            v = None
            if k.path and spec is not None:
                try:
                    v = sw._get(spec, k.path)
                except (KeyError, IndexError, TypeError):
                    v = None
            vals[k.name] = v if _num(v) else k.value(k.x0)
        return vals

    def ref_vals(self, over):
        vals = dict(self.P.x0())
        for k in self.P.knobs:
            if k.path in over:
                vals[k.name] = over[k.path]
            elif k.name in over:
                vals[k.name] = over[k.name]
        return vals

    def probe_rows(self, x0):
        rows = []
        for k in self.P.knobs:
            u0 = k.to_unit(x0[k.name])
            s = k.unit_step(self.P.sigma0)
            if k.int:
                s = max(s, 1.0 / (k.hi - k.lo))
            seen = set()
            for sgn in (-1, 1):
                u = u0 + sgn * s
                if u < 0 or u > 1:                      # (at a bound: two steps the other way instead)
                    u = u0 - sgn * 2 * s if 0 <= u0 - sgn * 2 * s <= 1 else min(max(u, 0), 1)
                v = dict(x0, **{k.name: k.from_unit(u)})
                if v[k.name] == x0[k.name] or v[k.name] in seen:
                    continue
                seen.add(v[k.name])
                side = 'lo' if v[k.name] < x0[k.name] else 'hi'
                if any(r['name'] == 'probe_%s_%s' % (sw._safe(k.name), side) for r in rows):
                    side += '2'
                rows.append(dict(name='probe_%s_%s' % (sw._safe(k.name), side), vals=v, kind='probe', gen=-1,
                                 knob=k.name))
        return rows

    def splice_set(self, E, meta):
        """the objects every row splices: declared, else what any probe row's rebuild changes (the control's too)."""
        if self.decl.get('objects') is not None:
            return list(self.decl['objects'])
        if meta.get('objects') is not None:
            return meta['objects']
        if self.decl.get('stage') in ('qa', 'python'):
            return []
        x0 = self.P.x0()
        rows = [dict(name='start', vals=x0)] + self.probe_rows(x0) + [
            dict(name='ref_' + n, vals=self.ref_vals(o)) for n, o in self.P.reference.items()]
        reqs = [dict(op='changes', row=dict(name=r['name'], set=self.P.row_set(r['vals']))) for r in rows]
        t = time.time()
        res = E.run(reqs)
        got = sorted({n for r in res for n in ((r.get('rec') or {}).get('changed') or ())})
        self.log('optimize: splice set %s (from %d probe rebuilds, %.0f s)' % (got, len(rows), time.time() - t))
        meta['probe_changed'] = {r['name']: (x.get('rec') or {}).get('changed') for r, x in zip(rows, res)}
        return got

    def dead_knobs(self):
        ctrl = {h['name']: h for h in self.H}
        start = ctrl.get('start')
        dead = []
        for k in self.P.knobs:
            ps = [h for h in self.H if h.get('kind') == 'probe' and h['name'].startswith('probe_%s_' % sw._safe(k.name))]
            if not ps or not start:
                continue
            if all(_same_checks(h.get('checks'), start.get('checks')) for h in ps):
                dead.append(k.name)
        return dead

    def rescore(self, h):
        if h.get('cached'):
            src = next((x for x in self.H if x['name'] == h.get('source')), None)
            if src:
                for f in ('f', 'v', 'feasible', 'terms', 'viol', 'error'):
                    h[f] = src.get(f)
            return
        h.update(self.scorer.score(h.get('checks'), h.get('error')))

    def rewrite_history(self):
        with open(self.path('history.jsonl'), 'w') as f:
            for h in self.H:
                f.write(json.dumps(h) + '\n')

    def optimizer(self, st, lam):
        P = self.P
        if st and st.get('opt'):
            return (CMA if P.method == 'cma' else Uniform).from_state(st['opt'])
        if P.method == 'random':
            return Uniform(P.n(), lam, P.seed)
        u0 = P.unit(P.x0())
        stds = [max(k.unit_step(P.sigma0), k.int_floor()) for k in P.knobs]
        return CMA(u0, P.sigma0, lam=lam, stds=stds, floors=[k.int_floor() for k in P.knobs], seed=P.seed)

    def should_stop(self, O, best_hist, meta):
        P = self.P
        B, S = P.budget, P.stop
        if self.n_evals() >= int(B.get('evals') or 1e9):
            return 'budget: %d evaluations' % self.n_evals()
        if O.gen >= int(B.get('generations') or 1e9):
            return 'budget: %d generations' % O.gen
        el = meta.get('seconds_before', 0.0) + time.time() - self.t0
        if el >= 60 * float(B.get('minutes') or 1e9):
            return 'budget: %.0f minutes' % (el / 60)
        b = self.best()
        if S.get('target') is not None and b and b.get('feasible') and b['f'] <= float(S['target']):
            return 'target reached: best f %s <= %s' % (b['f'], S['target'])
        # stalled: the best improved by less than tolfun over `stall` generations, with the search narrowed (its spread
        # under STALL_SPREAD of each continuous knob's range); still wide, three times as long (it wanders)
        stall = int(S.get('stall') or 0)
        if stall and P.method == 'cma':
            sp = O.spread()
            cont = [i for i, k in enumerate(P.knobs) if not k.int]
            narrow = not cont or float(np.max(sp[cont])) < STALL_SPREAD
            need = stall if narrow else 3 * stall
            if len(best_hist) > need and best_hist[-need - 1] is not None and \
                    best_hist[-need - 1] - best_hist[-1] < float(S.get('tolfun') or 0):
                return 'converged: the best improved by less than %s over %d generations%s' % (
                    S.get('tolfun'), need, '' if narrow else ' (the search still wide)')
        if P.method == 'cma' and O.gen > 0:
            # (an integer knob keeps a least spread: with one, the stall rule ends the search)
            if not any(k.int for k in P.knobs) and float(np.max(O.spread())) < float(S.get('tolx') or 0):
                return 'converged: the spread fell under %s' % S.get('tolx')
        return None

    def write_state(self, meta, O):
        meta = dict(meta)
        meta['opt'] = O.state() if O is not None else meta.get('opt')
        meta['seconds_total'] = round((meta.get('seconds_before') or 0.0) + time.time() - self.t0, 1)
        meta['evaluations'] = self.n_evals()
        meta['updated'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        tmp = self.path('state.json.tmp')
        json.dump(meta, open(tmp, 'w'), indent=1)
        os.replace(tmp, self.path('state.json'))

    def plan(self, lam_default):
        P = self.P
        total, free = free_slots()
        W = self.n_workers(lam_default)
        lam = int(P.popsize) if str(P.popsize).isdigit() else max(lam_default, W)
        rows = ['knob | path | lo | hi | int | x0 | step', '---|---|---|---|---|---|---']
        rows += ['%s | %s | %s | %s | %s | %s | %s' % (k.name, k.path, k.lo, k.hi, k.int, k.value(k.x0),
                                                      k.step if k.step is not None else '%.3g' % (P.sigma0 * (k.hi - k.lo)))
                 for k in P.knobs]
        txt = '\n'.join(['optimize plan: %d knobs, population %d over %d workers (%d slots, %d free), %s, seed %d' % (
            P.n(), lam, min(W, lam), total, free, P.method, P.seed), ''] + rows + [
            '', 'start overrides: %s' % json.dumps(P.overrides(P.x0())),
            'objective: %s' % json.dumps(P.objective), 'constraints: %s' % json.dumps(P.constraints),
            'budget: %s; stop: %s' % (P.budget, P.stop)])
        self.log(txt)
        return dict(plan=txt)

    def boards(self, E, objects):
        """the best's board (and any of the control, start and references not drawn yet), on the live workers."""
        best = self.best()
        names = [CONTROL, 'start'] + ([best['name']] if best else []) + ['ref_' + n for n in self.P.reference]
        hs = [next((h for h in self.H if h['name'] == n and not h.get('cached')), None) for n in names]
        hs = [h for h in hs if h and not os.path.exists(self.path('boards', sw._safe(h['name']) + '.png'))]
        if hs:
            E.run([dict(op='eval', row=dict(name=h['name'], set=h['set']), objects=objects,
                        board=self.path('boards', sw._safe(h['name']) + '.png')) for h in hs])

    # -- the confirm stage: real builds
    def confirm_stage(self, st):
        """the best `top` distinct feasible candidates built for real, with the control (when `set` changes the base)
        -> confirm.json; the pick: the best confirmed feasible under every term and constraint."""
        P, C = self.P, self.P.confirm
        if self.decl.get('stage') == 'python':
            self.log('optimize: confirm: a python evaluator has no real build (skipped)')
            return None
        top = int(C.get('top') or 0)
        cand = [h for h in self.H if h.get('kind') in ('cma', 'probe', 'start') and not h.get('cached') and
                h.get('feasible')]
        cand.sort(key=lambda h: (rank_key(h), h['i']))
        picks = []
        for h in cand:
            if all(h['key'] != p['key'] for p in picks):
                picks.append(h)
            if len(picks) >= top:
                break
        refs = [h for h in self.H if h.get('kind') == 'reference' and not h.get('cached')]
        builds = []
        need_ctrl = C.get('control') == 'build' or (C.get('control') == 'auto' and (self.decl.get('set') or {}))
        if need_ctrl:
            builds.append(next(h for h in self.H if h['kind'] == 'control'))
        builds += picks + (refs if C.get('references') else [])
        skipped = [k for h in builds for k in (h.get('set') or {}) if k.startswith((sw.QA_PATCH, sw.STYLE))]
        if skipped:
            self.log('optimize: confirm: %s are measurement or style patches a build doesn\'t take (left out)' %
                     sorted(set(skipped)))
        spec_path = C.get('spec') or self.decl.get('spec') or 'charkit/spec/clawd.json'
        spec_path = spec_path if os.path.isabs(spec_path) else os.path.join(ROOT, spec_path)
        raw = json.load(open(spec_path))
        where = C.get('where') or 'auto'
        if where == 'auto':
            where = 'here' if sys.platform.startswith('linux') and os.path.isdir('/srv/work') else 'remote'
        jobs = []
        for h in builds:
            d = self.path('confirm', sw._safe(h['name']))
            os.makedirs(d, exist_ok=True)
            over = {k: v for k, v in (h.get('set') or {}).items() if not k.startswith((sw.QA_PATCH, sw.STYLE))}
            s = sw.apply(raw, over)
            sp = os.path.join(d, 'spec.json')
            json.dump(s, open(sp, 'w'), indent=1)
            bdir = os.path.join(d, 'build')
            args = list(C.get('args') or [])
            if where == 'here':
                cmd = [sys.executable, '-m', 'charkit', 'build', sp, '--out', bdir] + args
            else:
                cmd = [sys.executable, '-m', 'charkit', 'remote'] + (['--box', C['box']] if C.get('box') else []) + \
                      ['build', os.path.relpath(sp, ROOT), '--out', os.path.relpath(bdir, ROOT)] + args
            jobs.append((h, d, bdir, cmd))
        self.log('optimize: confirm: %d real builds (%s): %s' % (len(jobs), where, ', '.join(h['name'] for h, *_ in jobs)))
        ps = []
        for h, d, bdir, cmd in jobs:
            lf = open(os.path.join(d, 'build.log'), 'w')
            ps.append((subprocess.Popen(cmd, cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT), lf))
        for p, lf in ps:
            p.wait()
            lf.close()
        base_qa = os.path.join(self.decl['base'], 'qa', 'qa.json')
        ref_name = CONTROL if need_ctrl else 'base'
        q0 = None
        if need_ctrl:
            p0 = os.path.join(self.path('confirm', CONTROL, 'build'), 'qa', 'qa.json')
            q0 = json.load(open(p0)) if os.path.exists(p0) else None
        elif os.path.exists(base_qa):
            q0 = json.load(open(base_qa))
        if q0 is None:
            self.log('optimize: confirm: no real control to score against (its build failed?)')
            res = dict(error='no real control', builds=[dict(name=h['name'], build=b) for h, _, b, _ in jobs])
            json.dump(res, open(self.path('confirm.json'), 'w'), indent=1)
            return res
        R = Scorer(P, q0.get('checks') or {}, mode='real', log=self.log)
        rows = []
        for h, d, bdir, cmd in jobs:
            qp = os.path.join(bdir, 'qa', 'qa.json')
            if not os.path.exists(qp):
                rows.append(dict(name=h['name'], build=bdir, error='no qa.json (see %s)' % os.path.join(d, 'build.log')))
                continue
            q = json.load(open(qp))
            sc = R.score(q.get('checks') or {})
            cpu = None
            try:
                cpu = json.load(open(os.path.join(bdir, 'build_cpu.json'))).get('cpu_seconds')
            except (OSError, ValueError, AttributeError):
                pass
            rows.append(dict(name=h['name'], build=bdir, screen=dict(f=h.get('f'), v=h.get('v')), knobs=h.get('knobs'),
                             cpu=cpu, **{k: sc[k] for k in ('f', 'v', 'feasible', 'terms', 'viol')}))
        for name, path in (C.get('compare') or {}).items():      # (existing real builds scored alike: a hand result)
            bp = sw._abs(path, ROOT)
            qp = os.path.join(bp, 'qa', 'qa.json')
            if os.path.exists(qp):
                sc = R.score(json.load(open(qp)).get('checks') or {})
                rows.append(dict(name=name, build=bp, compare=True, **{k: sc[k] for k in ('f', 'v', 'feasible', 'terms',
                                                                                         'viol')}))
        ok = [r for r in rows if r.get('feasible') and r['name'] != CONTROL and not r.get('compare')]
        ok.sort(key=lambda r: r['f'])
        res = dict(against=ref_name, against_qa=base_qa if not need_ctrl else os.path.join(
            self.path('confirm', CONTROL, 'build'), 'qa', 'qa.json'), terms=[t['check'] for t in R.terms],
            rows=rows, pick=ok[0]['name'] if ok else None, where=where)
        json.dump(sw._plain(res), open(self.path('confirm.json'), 'w'), indent=1)
        st = json.load(open(self.path('state.json')))
        st['confirmed'] = True
        json.dump(st, open(self.path('state.json'), 'w'), indent=1)
        self.log('optimize: confirm: pick %s' % res['pick'])
        return res


def _same_checks(a, b, eps=1e-9):
    if not a or not b:
        return False
    for k in set(a) | set(b):
        x, y = (a.get(k) or {}), (b.get(k) or {})
        if x.get('status') != y.get('status'):
            return False
        vx, vy = x.get('value'), y.get('value')
        if _num(vx) and _num(vy):
            if abs(vx - vy) > eps:
                return False
        elif vx != vy:
            return False
        if x.get('views') != y.get('views'):
            return False
    return True


# ---------------------------------------------------------------------------------------------------------- reports
def load(out):
    out = sw._abs(out)
    H = [json.loads(l) for l in open(os.path.join(out, 'history.jsonl')) if l.strip()]
    st = json.load(open(os.path.join(out, 'state.json')))
    decl = json.load(open(os.path.join(out, 'decl.json')))
    return out, decl, st, H


def sensitivity(P, H, O_spread=None):
    """per knob: the probe's one-step effect (OAT), the effect over its range fitted on every feasible point (a linear
    fit on unit coordinates) and on the better half near the best, the rank correlation with the objective, and the
    search's final spread in knob units -> {knob: dict}, plus per objective term the rank correlations."""
    pts = [h for h in H if not h.get('cached') and h.get('kind') in ('cma', 'probe', 'start') and h.get('f') is not None
           and h.get('feasible')]
    out = {}
    if pts:
        X = np.array([h['u'] for h in pts], float)
        y = np.array([h['f'] for h in pts], float)
    for i, k in enumerate(P.knobs):
        r = dict(path=k.path, lo=k.lo, hi=k.hi, int=k.int)
        start = next((h for h in H if h.get('kind') == 'start' and not h.get('cached')), None)
        oat = {}
        for h in H:
            if h.get('kind') == 'probe' and h['name'].startswith('probe_%s_' % sw._safe(k.name)) and start and \
                    h.get('f') is not None and start.get('f') is not None:
                oat[h['name'].rsplit('_', 1)[1]] = dict(value=h['knobs'][k.name], df=round(h['f'] - start['f'], 5),
                                                        feasible=h.get('feasible'))
        r['oat'] = oat
        if pts and len(pts) > P.n() + 1:
            r['spearman'] = _spearman(X[:, i], y)
            r['range_effect'] = _linfit(X, y)[i]
            o = np.argsort(y)[:max(P.n() + 2, len(y) // 2)]
            r['near_best_effect'] = _linfit(X[o], y[o])[i] if len(o) > P.n() + 1 else None
        if O_spread is not None:
            sd = float(O_spread[i])
            r['final_spread'] = round(sd * (k.hi - k.lo), 5) if not k.log else round(sd, 5)
        out[k.name] = r
    terms = {}
    if pts:
        names = sorted({t for h in pts for t in (h.get('terms') or {})})
        for t in names:
            yt = np.array([(h.get('terms') or {}).get(t, np.nan) for h in pts], float)
            ok = np.isfinite(yt)
            if ok.sum() > 3:
                terms[t] = {k.name: _spearman(X[ok, i], yt[ok]) for i, k in enumerate(P.knobs)}
    return dict(knobs=out, terms=terms, points=len(pts))


def _rank(a):
    o = np.argsort(a, kind='mergesort')
    r = np.empty(len(a))
    r[o] = np.arange(len(a))
    # ties share their mean rank
    _, inv, cnt = np.unique(a, return_inverse=True, return_counts=True)
    s = np.bincount(inv, r)
    return s[inv] / cnt[inv]


def _spearman(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) < 3 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return None
    a, b = _rank(x), _rank(y)
    return round(float(np.corrcoef(a, b)[0, 1]), 3)


def _linfit(X, y, ridge=1e-3):
    """y ~ a + b . X (ridge): b_i the objective's change across knob i's whole range (linear)."""
    A = np.c_[np.ones(len(X)), X]
    R = ridge * np.eye(A.shape[1])
    R[0, 0] = 0
    try:
        b = np.linalg.solve(A.T @ A + R, A.T @ y)
    except np.linalg.LinAlgError:
        return [None] * X.shape[1]
    return [round(float(x), 5) for x in b[1:]]


def _fmt(v):
    if isinstance(v, float):
        return '%.4g' % v
    return json.dumps(v, separators=(',', ':')) if not isinstance(v, str) else v


def report(out, log=print):
    """the tables, plots and review page from a run's folder (history.jsonl, state.json, decl.json)."""
    out, decl, st, H = load(out)
    spec = None
    P = Problem(decl, spec)
    O = None
    if st.get('opt'):
        O = (CMA if P.method == 'cma' else Uniform).from_state(st['opt'])
    ctrl = next((h for h in H if h.get('kind') == 'control'), None)
    search = [h for h in H if h.get('kind') in ('cma', 'probe', 'start') and h.get('f') is not None and
              not h.get('cached')]
    search.sort(key=lambda h: (rank_key(h), h['i']))
    best = search[0] if search else None
    refs = [h for h in H if h.get('kind') == 'reference' and not h.get('cached')]
    start = next((h for h in H if h.get('kind') == 'start'), None)
    conf = json.load(open(os.path.join(out, 'confirm.json'))) if os.path.exists(os.path.join(out, 'confirm.json')) \
        else None
    pick = None
    if conf and conf.get('pick'):
        pick = next((h for h in H if h['name'] == conf['pick'] and not h.get('cached')), None)
    chosen = pick or best
    # the best as a spec override
    if chosen:
        bo = dict(name=chosen['name'], knobs=chosen['knobs'], set=chosen.get('set') or P.row_set(chosen['knobs']),
                  overrides=P.overrides(chosen['knobs']), f=chosen.get('f'), v=chosen.get('v'),
                  feasible=chosen.get('feasible'), confirmed=bool(pick), base=decl.get('base'), stage=decl.get('stage'))
        json.dump(sw._plain(bo), open(os.path.join(out, 'best_override.json'), 'w'), indent=1)
    sens = sensitivity(P, H, O.spread() if O is not None else None)
    json.dump(sw._plain(sens), open(os.path.join(out, 'sensitivity.json'), 'w'), indent=1)
    n_eval = sum(1 for h in H if not h.get('cached'))
    summ = dict(out=out, base=decl.get('base'), stage=decl.get('stage'), knobs=[k.doc() for k in P.knobs],
                evaluations=n_eval, cache_hits=sum(1 for h in H if h.get('cached')), generations=(st.get('opt') or {}
                                                                                                     ).get('gen'),
                stop=st.get('stop'), seconds=st.get('seconds_total'), workers=st.get('workers'), lam=st.get('lam'),
                context_seconds=st.get('context_seconds'), objects=st.get('objects'), dead=st.get('dead'),
                left_out=st.get('left_out'),
                control=_brief(ctrl), start=_brief(start), best=_brief(best), references=[_brief(h) for h in refs],
                confirm=dict(pick=conf.get('pick'), rows=[{k: r.get(k) for k in ('name', 'f', 'v', 'feasible', 'cpu',
                                                                                 'error')}
                                                          for r in conf.get('rows') or ()]) if conf else None,
                chosen=chosen['name'] if chosen else None)
    json.dump(sw._plain(summ), open(os.path.join(out, 'opt.json'), 'w'), indent=1)
    _history_md(out, P, H, decl)
    _history_csv(out, P, H)
    _sens_md(out, P, sens)
    _sweep_json(out, decl, st, H, [ctrl, start] + refs + search[:5])
    try:
        convergence_plot(out, P, H, st)
        sensitivity_plot(out, P, sens)
    except Exception as e:                              # (the numbers stand without the pictures)
        log('optimize: plots: %s: %s' % (type(e).__name__, e))
    page = review_json(out, decl, P, st, H, summ, conf)
    try:
        from . import reviewpage
        path = reviewpage.make(page, os.path.join(out, 'review'), log=log)
        log('optimize: review page %s' % path)
    except Exception as e:
        log('optimize: review page: %s: %s' % (type(e).__name__, e))
    log('optimize: %s: %d evaluations, %s; best %s f %s v %s' % (out, n_eval, st.get('stop'), chosen and chosen['name'],
                                                                chosen and chosen.get('f'), chosen and chosen.get('v')))
    return summ


def _brief(h):
    if not h:
        return None
    return dict(name=h['name'], knobs=h.get('knobs'), f=h.get('f'), v=h.get('v'), feasible=h.get('feasible'),
                terms=h.get('terms'), viol=[{k: x.get(k) for k in ('kind', 'check', 'view', 'control', 'row', 'rel')}
                                            for x in (h.get('viol') or [])][:12])


def _history_md(out, P, H, decl):
    names = [k.name for k in P.knobs]
    terms = list(dict.fromkeys(t for h in H for t in (h.get('terms') or {})))
    L = ['# optimize: %s stage on %s' % (decl.get('stage'), os.path.basename(str(decl.get('base') or '').rstrip('/'))),
         '', 'Every evaluation (cache hits marked); f: the objective (lower is better); v: the constraints\' '
             'violation (0: feasible); the terms are each check\'s share of f.', '',
         '| # | row | gen | ' + ' | '.join(names) + ' | f | v | ok | ' + ' | '.join(terms) + ' | broken | s |',
         '|' + '---|' * (len(names) + len(terms) + 8)]
    for h in H:
        br = '; '.join('%s %s%s' % (x.get('kind'), x.get('check') or x.get('why') or '',
                                    (' ' + x['view']) if x.get('view') else '') for x in (h.get('viol') or [])[:3])
        L.append('| %d | %s%s | %s | %s | %s | %s | %s | %s | %s | %s |' % (
            h['i'], h['name'], ' (cache)' if h.get('cached') else '', h.get('gen'),
            ' | '.join(_fmt(h['knobs'].get(n)) for n in names), _fmt(h.get('f')), _fmt(h.get('v')),
            'yes' if h.get('feasible') else 'no', ' | '.join(_fmt((h.get('terms') or {}).get(t)) for t in terms),
            br.replace('|', '/'), _fmt(h.get('seconds'))))
    open(os.path.join(out, 'history.md'), 'w').write('\n'.join(L) + '\n')


def _history_csv(out, P, H):
    """the full table: knobs, objective, every check's value and status, every piece's shape IoU per view."""
    import csv
    checks = list(dict.fromkeys(k for h in H for k in (h.get('checks') or {})))
    views = list(dict.fromkeys('%s.%s' % (k, v) for h in H for k, c in (h.get('checks') or {}).items()
                               if sw.SHAPE_CHECK.match(k) and isinstance(c.get('views'), dict) for v in c['views']))
    cols = ['i', 'name', 'kind', 'gen', 'cached', 'f', 'v', 'feasible'] + ['knob:' + k.name for k in P.knobs] + \
        [c + ':value' for c in checks] + [c + ':status' for c in checks] + ['iou:' + v for v in views]
    with open(os.path.join(out, 'history.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(cols)
        for h in H:
            src = h
            if h.get('cached'):
                src = next((x for x in H if x['name'] == h.get('source')), h)
            C = src.get('checks') or {}
            row = [h['i'], h['name'], h.get('kind'), h.get('gen'), bool(h.get('cached')), h.get('f'), h.get('v'),
                   h.get('feasible')] + [h['knobs'].get(k.name) for k in P.knobs]
            row += [(C.get(c) or {}).get('value') if not isinstance((C.get(c) or {}).get('value'), (dict, list))
                    else json.dumps((C.get(c) or {}).get('value')) for c in checks]
            row += [(C.get(c) or {}).get('status') for c in checks]
            for v in views:
                k, _, vv = v.rpartition('.')
                row.append(((C.get(k) or {}).get('views') or {}).get(vv))
            w.writerow(row)


def _sens_md(out, P, sens):
    L = ['# Sensitivity per knob', '', 'From %d feasible evaluations. oat: the objective\'s move one step either side '
         'of the start (the probe); range: its move across the knob\'s whole range (a linear fit on every feasible '
         'point); near best: the same fit on the better half; rho: the rank correlation with the objective (+: '
         'raising the knob worsens it); spread: the search\'s final standard deviation (knob units).' % sens['points'],
         '', '| knob | start | oat (value: objective move) | range | near best | rho | spread |',
         '|---|---|---|---|---|---|---|']
    for k in P.knobs:
        r = sens['knobs'].get(k.name) or {}
        o = r.get('oat') or {}
        L.append('| %s | %s | %s | %s | %s | %s | %s |' % (
            k.name, _fmt(k.value(k.x0)), '; '.join('%s: %+.4g' % (_fmt(x['value']), x['df']) for _, x in
                                                   sorted(o.items(), key=lambda kv: kv[1]['value'])) or '-',
            _fmt(r.get('range_effect')), _fmt(r.get('near_best_effect')), _fmt(r.get('spearman')),
            _fmt(r.get('final_spread'))))
    if sens.get('terms'):
        names = [k.name for k in P.knobs]
        L += ['', 'Rank correlation of each objective term with each knob:', '',
              '| term | ' + ' | '.join(names) + ' |', '|' + '---|' * (len(names) + 1)]
        for t, row in sens['terms'].items():
            L.append('| %s | %s |' % (t, ' | '.join(_fmt(row.get(n)) for n in names)))
    open(os.path.join(out, 'sensitivity.md'), 'w').write('\n'.join(L) + '\n')


def _sweep_json(out, decl, st, H, rows):
    """the control, start, references and best candidates in the sweep's own result form (sweep table, review page)."""
    seen, R = set(), []
    for h in rows:
        if not h or h['name'] in seen:
            continue
        seen.add(h['name'])
        src = h if not h.get('cached') else next((x for x in H if x['name'] == h.get('source')), h)
        R.append(dict(name=h['name'], set=sw._plain(src.get('set') or {}), control=h.get('kind') == 'control',
                      objects=src.get('spliced') or [], seconds=src.get('seconds'), checks=src.get('checks') or {}))
    res = dict(decl={k: v for k, v in decl.items() if k != 'optimize'}, code=ROOT, commit=sw._head(ROOT),
               seconds=st.get('seconds_total'), rows=R)
    res['decl'].setdefault('checks', sorted({t['check'] for t in decl['optimize'].get('objective') or ()}))
    try:
        res['guard'] = sw.guard(res)
    except Exception:
        res['guard'] = []
    json.dump(sw._plain(res), open(os.path.join(out, 'sweep.json'), 'w'), indent=1)
    open(os.path.join(out, 'sweep.md'), 'w').write(sw.table(res))


# the plots: the reference palette (dataviz skill: categorical slots in fixed order; text in ink, not series colours)
INK, INK2, GRID = '#0b0b0b', '#52514e', '#e4e3df'
SERIES = ('#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948')
MUTED = '#a3a29d'


def _axes(ax):
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    for s in ('left', 'bottom'):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def convergence_plot(out, P, H, st):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    ev = [h for h in H if not h.get('cached') and h.get('kind') in ('cma', 'probe', 'start')]
    fig, axs = plt.subplots(3, 1, figsize=(9, 9.5), dpi=110)
    ax = axs[0]
    _axes(ax)
    xs = np.arange(len(ev))
    fe = [(i, h['f']) for i, h in enumerate(ev) if h.get('feasible') and h.get('f') is not None]
    inf = [(i, h['f']) for i, h in enumerate(ev) if not h.get('feasible') and h.get('f') is not None]
    if inf:
        ax.scatter(*zip(*inf), marker='x', s=22, color=MUTED, linewidths=1.2, label='breaks a constraint')
    if fe:
        ax.scatter(*zip(*fe), s=26, color=SERIES[0], edgecolors='white', linewidths=1.5, label='feasible', zorder=3)
    bs, b = [], None
    for h in ev:
        if h.get('feasible') and h.get('f') is not None and (b is None or h['f'] < b):
            b = h['f']
        bs.append(b)
    if any(x is not None for x in bs):
        ax.plot(xs, [np.nan if x is None else x for x in bs], color=INK, linewidth=2, label='best feasible so far',
                zorder=4)
    for k, h in enumerate([x for x in H if x.get('kind') in ('control', 'reference') and not x.get('cached')]):
        if h.get('f') is not None:
            ax.axhline(h['f'], color=SERIES[1 + k % 7], linewidth=1.2, zorder=2)
            ax.annotate('%s %.3g' % (h['name'], h['f']), (len(ev) - 1, h['f']), color=INK2, fontsize=8,
                        ha='right', va='bottom')
    ax.set_xlabel('evaluation (search order: start, probe, generations)', color=INK2, fontsize=9)
    ax.set_ylabel('objective (lower is better)', color=INK2, fontsize=9)
    ax.set_title('Objective per evaluation', color=INK, fontsize=11, loc='left')
    ax.legend(frameon=False, fontsize=8, labelcolor=INK2)
    ax = axs[1]
    _axes(ax)
    gens = sorted({h['gen'] for h in ev if h.get('kind') == 'cma'})
    med = [np.median([h['f'] for h in ev if h.get('gen') == g and h.get('f') is not None] or [np.nan]) for g in gens]
    feas = [np.mean([bool(h.get('feasible')) for h in H if h.get('kind') == 'cma' and h.get('gen') == g]) for g in gens]
    ax.plot(gens, st.get('sigma_hist') or [np.nan] * len(gens), color=SERIES[0], linewidth=2, marker='o',
            markersize=5, markeredgecolor='white', label='step size sigma (unit range)')
    ax.plot(gens, feas, color=SERIES[2], linewidth=2, marker='o', markersize=5, markeredgecolor='white',
            label='share feasible')
    ax.set_ylim(0, 1.05)
    ax.set_xlabel('generation', color=INK2, fontsize=9)
    ax.set_title('Search spread and feasibility per generation (median objective in the table)', color=INK,
                 fontsize=11, loc='left')
    ax.legend(frameon=False, fontsize=8, labelcolor=INK2)
    ax = axs[2]
    _axes(ax)
    M = np.array(st.get('mean_hist') or [], float)
    for i, k in enumerate(P.knobs[:8]):
        if len(M):
            ax.plot(gens[:len(M)], M[:, i], color=SERIES[i % 8], linewidth=2, label=k.name)
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel('generation', color=INK2, fontsize=9)
    ax.set_ylabel('search mean (share of range)', color=INK2, fontsize=9)
    ax.set_title('Each knob\'s search mean per generation (first 8 knobs)', color=INK, fontsize=11, loc='left')
    ax.legend(frameon=False, fontsize=8, labelcolor=INK2, ncol=4)
    fig.tight_layout()
    fig.savefig(os.path.join(out, 'convergence.png'), facecolor='white')
    plt.close(fig)
    _ = med


def sensitivity_plot(out, P, sens):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    ks = [k.name for k in P.knobs]
    rng = [(sens['knobs'].get(k) or {}).get('range_effect') for k in ks]
    near = [(sens['knobs'].get(k) or {}).get('near_best_effect') for k in ks]
    if not any(x is not None for x in rng):
        return
    fig, ax = plt.subplots(figsize=(8, 0.45 * len(ks) + 1.6), dpi=110)
    _axes(ax)
    y = np.arange(len(ks))
    ax.barh(y - 0.18, [x or 0 for x in rng], height=0.34, color=SERIES[0], label='across the range (every feasible '
                                                                                 'point)')
    ax.barh(y + 0.18, [x or 0 for x in near], height=0.34, color=SERIES[1], label='near the best (better half)')
    ax.axvline(0, color=INK2, linewidth=1)
    ax.set_yticks(y)
    ax.set_yticklabels(ks, color=INK2, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel('objective change from the knob\'s low bound to its high bound (linear fit; + worsens)', color=INK2,
                  fontsize=9)
    ax.set_title('Per-knob sensitivity', color=INK, fontsize=11, loc='left')
    ax.legend(frameon=False, fontsize=8, labelcolor=INK2)
    fig.tight_layout()
    fig.savefig(os.path.join(out, 'sensitivity.png'), facecolor='white')
    plt.close(fig)


def review_json(out, decl, P, st, H, summ, conf):
    """the review page's declaration (charkit review page): the summary box first."""
    o = decl.get('optimize') or {}
    ctrl = next((h for h in H if h.get('kind') == 'control'), None)
    chosen = next((h for h in H if h['name'] == summ.get('chosen') and not h.get('cached')), None)
    refs = [h for h in H if h.get('kind') == 'reference' and not h.get('cached')]
    cols = ['', 'control (the base, `set`)'] + ['reference %s' % h['name'][4:] for h in refs] + [
        'optimizer (%s)' % (chosen['name'] if chosen else '-')]
    rowsh = [ctrl] + refs + [chosen]
    terms = list(dict.fromkeys(t for h in rowsh if h for t in (h.get('terms') or {})))

    def val(h, t):
        if not h:
            return '-'
        c = (h.get('checks') or {}).get(t.split(':')[0]) or {}
        v = c.get('value')
        return '%s %s' % (_fmt(v) if v is not None else '-', (c.get('grade') or c.get('status') or '')[:1])
    nums = [['objective f (lower is better)'] + [_fmt(h.get('f')) if h else '-' for h in rowsh],
            ['constraints broken (v)'] + [_fmt(h.get('v')) if h else '-' for h in rowsh]]
    nums += [[t] + [val(h, t) for h in rowsh] for t in terms]
    if conf and conf.get('rows'):
        for r in conf['rows']:
            nums.append(['real build %s: f / v / feasible' % r['name'], '', *[''] * len(refs),
                         '%s / %s / %s' % (_fmt(r.get('f')), _fmt(r.get('v')), r.get('feasible'))])
    rec = o.get('recommended') or (
        'Take %s (%s): objective %s against the control\'s %s, every constraint held (each piece\'s shape IoU within '
        '%d%% of the control in every view, no flag check worse, no new FAIL)%s.' % (
            chosen['name'], json.dumps(P.overrides(chosen['knobs'])), _fmt(chosen.get('f')), _fmt((ctrl or {}).get('f')),
            round(100 * P.constraints['guard']), '; confirmed by a real build' if conf and conf.get('pick') == chosen[
                'name'] else '') if chosen and chosen.get('feasible') else 'No feasible candidate: see the history.')
    notes = ['%d evaluations (%d cache hits) in %s s over %s workers (population %s, %s generations); stopped: %s. '
             'Splice set %s. Context %s s a worker.' % (summ['evaluations'], summ['cache_hits'], summ.get('seconds'),
                                                         summ.get('workers'), summ.get('lam'), summ.get('generations'),
                                                         summ.get('stop'), summ.get('objects'),
                                                         summ.get('context_seconds')),
             'Files: history.md / history.csv (every evaluation: knobs, objective, constraints, every check, every '
             'piece\'s shape IoU per view), sensitivity.md, best_override.json, opt.json.']
    if summ.get('dead'):
        notes.append('Dead knobs (a step either side changed nothing): %s.' % ', '.join(summ['dead']))
    if summ.get('left_out'):
        notes.append('Real-only objective terms left out of the screen (scored at the confirm): %s.' % ', '.join(
            summ['left_out']))
    figs = [dict(title='Convergence', text='The objective per evaluation (feasible blue, constraint-breaking grey), '
                                           'the best so far, the control and references as lines; the search\'s spread'
                                           ' and each knob\'s mean per generation.',
                 images=[dict(path=os.path.join(out, 'convergence.png'), caption='convergence.png')], height=640),
            dict(title='Sensitivity', text='Each knob\'s effect on the objective (linear fits on the evaluated points)',
                 images=[dict(path=os.path.join(out, 'sensitivity.png'), caption='sensitivity.png')], height=360)]
    bds = [dict(path=os.path.join(out, 'boards', sw._safe(n) + '.png'), caption=n) for n in
           [CONTROL, 'start'] + [h['name'] for h in refs] + ([chosen['name']] if chosen else [])
           if os.path.exists(os.path.join(out, 'boards', sw._safe(n) + '.png'))]
    if bds:
        figs.append(dict(title='Boards (the screen\'s numpy drawing)', images=bds, height=300))
    builds = []
    if conf:
        for r in conf.get('rows') or ():
            if r.get('build') and os.path.exists(os.path.join(r['build'], 'qa', 'qa.json')):
                builds.append(dict(label='real: %s' % r['name'], path=r['build']))
    page = dict(title=o.get('title') or 'Optimizer: %s' % os.path.basename(out.rstrip('/')),
                summary=dict(recommended=rec, asked=o.get('asked') or ['nothing: informational'],
                             numbers=dict(columns=cols, rows=nums)),
                notes=notes, figures=[f for f in figs if all(os.path.exists(i['path']) for i in f['images'])],
                sweep=os.path.join(out, 'sweep.json'), builds=builds, regions=o.get('regions') or [],
                checks=sorted({t.split(':')[0] for t in terms}))
    os.makedirs(os.path.join(out, 'review'), exist_ok=True)
    json.dump(page, open(os.path.join(out, 'review', 'page.json'), 'w'), indent=1)
    return page


# ----------------------------------------------------------------------------------------------------------- audit
def audit(build, parts=None, out=None, log=print):
    """which checks the screen measures as the real build does: the build's own geometry measured with the numpy
    drawing (the sweep's qa stage) against its qa.json (the render drawing) -> {check: dict(real, numpy, same_status,
    rel, class)}; OUT/audit.json and audit.md."""
    build = sw._abs(build)
    q = json.load(open(os.path.join(build, 'qa', 'qa.json')))
    owned = (q.get('measured') or {}).get('part_checks') or {}
    if not parts:
        parts = sorted(owned)
    B0 = sw.load_bundle(build)
    sw.produce(copy.deepcopy(B0._meta.get('spec') or {}))
    t = time.time()
    C = sw.measure(sw.spliced(B0, {}), list(parts))
    rows = {}
    for k, c in sorted(C.items()):
        r = (q.get('checks') or {}).get(k)
        if not isinstance(c, dict) or not isinstance(r, dict):
            continue
        a, b = r.get('value'), c.get('value')
        sa, sb = r.get('grade') or r.get('status'), c.get('grade') or c.get('status')
        rel = None
        if _num(a) and _num(b):
            rel = abs(b - a) / max(abs(a), 1e-9) if a != b else 0.0
        same = sa == sb
        cls = 'fast' if same and (rel is None and a == b or rel is not None and rel <= 0.02) else 'real'
        rows[k] = dict(real=a, numpy=b, status=[sa, sb], rel=None if rel is None else round(rel, 4), cls=cls,
                       part=c.get('part'), declared=fidelity(k, c.get('part')))
    out = sw._abs(out or os.path.join(ROOT, 'charkit', 'out', 'optimize', 'audit_' + os.path.basename(build)))
    os.makedirs(out, exist_ok=True)
    res = dict(build=build, parts=list(parts), seconds=round(time.time() - t, 1), draw=(q.get('measured') or {}
                                                                                          ).get('draw'), checks=rows)
    json.dump(sw._plain(res), open(os.path.join(out, 'audit.json'), 'w'), indent=1)
    differ = {k: r for k, r in rows.items() if r['cls'] == 'real'}
    miss = {k: r for k, r in differ.items() if r['declared'] == 'fast'}
    L = ['# Fidelity audit: %s' % build, '', '%d checks compared (parts %s): the build\'s qa.json (its %s drawing) '
         'against its own geometry measured with the numpy drawing (the screen\'s). %d read differently (status, or '
         'value by more than 2%%); %d of those FIDELITY doesn\'t mark real-only.' % (
             len(rows), ', '.join(parts), (res['draw'] or {}).get('setting'), len(differ), len(miss)), '',
         '| check | part | real build | numpy | rel | FIDELITY |', '|---|---|---|---|---|---|']
    for k, r in sorted(differ.items(), key=lambda kv: -(kv[1]['rel'] or 9)):
        L.append('| %s | %s | %s %s | %s %s | %s | %s |' % (k, r['part'], _fmt(r['real']), r['status'][0],
                                                            _fmt(r['numpy']), r['status'][1], _fmt(r['rel']),
                                                            r['declared']))
    open(os.path.join(out, 'audit.md'), 'w').write('\n'.join(L) + '\n')
    log('\n'.join(L[:4]))
    log('optimize audit: %s' % os.path.join(out, 'audit.md'))
    return res


# ------------------------------------------------------------------------------------------------- synthetic problem
class Synthetic:
    """a test objective (stage 'python', python 'charkit.optimize:synthetic'): knobs a, b, c (and n: an integer) set
    as `a`, `b`, `c`, `n`; checks:
      bowl        a smooth bowl with its minimum at (args.opt), graded lower-is-better [0.05, 0.2]
      piece_toy   a shape check whose front IoU falls as `a` passes args.cliff (the anti-gaming trap: the bowl's
                  minimum lies past it), its profile view as `b` rises
      flag_toy    a flag check that FAILs when c > args.flag_at
      keep_toy    a check that WARNs when n > args.keep_at"""

    def __init__(self, decl):
        self.args = dict(dict(opt=[0.8, 0.3, 0.6, 3], cliff=0.6, flag_at=0.75, keep_at=5, noise=0.0, sleep=0.0),
                         **(decl.get('args') or {}))
        self.n = 0

    def evaluate(self, s):
        A = self.args
        a, b, c, n = (float(s.get(k, 0.0)) for k in ('a', 'b', 'c', 'n'))
        o = A['opt']
        if os.environ.get('CHARKIT_OPT_TEST_INTERRUPT') and self.n + 1 >= int(os.environ['CHARKIT_OPT_TEST_INTERRUPT']):
            raise KeyboardInterrupt('the test\'s interrupt')         # (test_optimize's resume: a run cut short)
        bowl = (a - o[0]) ** 2 + (b - o[1]) ** 2 + 0.5 * (c - o[2]) ** 2 + 0.01 * (n - o[3]) ** 2
        self.n += 1
        if A.get('sleep'):
            time.sleep(A['sleep'])
        if A.get('noise'):
            bowl += A['noise'] * float(np.random.default_rng(int(1e6 * (a + 2 * b + 3 * c + 5 * n))).normal())
        front = 0.9 if a <= A['cliff'] else max(0.0, 0.9 - 2.0 * (a - A['cliff']))
        prof = 0.8 - 0.1 * b
        st = 'PASS' if bowl <= 0.05 else ('WARN' if bowl <= 0.2 else 'FAIL')
        return {
            'bowl': dict(value=round(bowl, 8), status=st, part='synthetic'),
            'piece_toy': dict(value=round(min(front, prof), 6), status='PASS' if min(front, prof) > 0.6 else 'WARN',
                              views=dict(front=round(front, 6), profile=round(prof, 6)), part='sheet_pieces'),
            'flag_toy': dict(value=round(c, 6), status='FAIL' if c > A['flag_at'] else 'PASS', flag='a test flag',
                             part='synthetic'),
            'keep_toy': dict(value=n, status='WARN' if n > A['keep_at'] else 'PASS', part='synthetic'),
        }


def synthetic(decl):
    return Synthetic(decl)


# ------------------------------------------------------------------------------------------------------------- CLI
def _opt(args, k, d=None):
    return args[args.index(k) + 1] if k in args and args.index(k) + 1 < len(args) else d


def main(args):
    """`sweep optimize ...` (args after 'optimize')."""
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    if args[0] == 'report':
        report(args[1])
        return 0
    if args[0] == 'audit':
        audit(args[1], [x for x in (_opt(args, '--parts') or '').split(',') if x] or None, _opt(args, '--out'))
        return 0
    if '--box' in args:
        return _box(args)
    decl = args[0]
    name = os.path.splitext(os.path.basename(decl))[0]
    out = _opt(args, '--out') or os.path.join(sw.home(), 'charkit', 'out', 'optimize', name)
    w = _opt(args, '--workers', 'auto')
    ov = dict(seed=int(_opt(args, '--seed')) if _opt(args, '--seed') else None,
              evals=int(_opt(args, '--evals')) if _opt(args, '--evals') else None,
              minutes=float(_opt(args, '--minutes')) if _opt(args, '--minutes') else None,
              confirm=int(_opt(args, '--confirm')) if _opt(args, '--confirm') else None)
    R = Run(sw._abs(decl), out, workers=int(w) if str(w).isdigit() else 'auto',
            reserve=int(_opt(args, '--reserve', 1)), inproc='--inproc' in args, overrides=ov)
    R.run(resume='--resume' in args, confirm='--no-confirm' not in args, plan_only='--plan' in args)
    return 0


def _box(args):
    """--box [NAME]: the run on the box (remote run --fetch OUT), then its reports made here from the fetched folder."""
    from . import remote
    i = args.index('--box')
    name = args[i + 1] if i + 1 < len(args) and not args[i + 1].startswith('-') else None
    rest = args[:i] + args[i + (2 if name else 1):]
    out = _opt(rest, '--out')
    if not out:
        raise SystemExit('sweep optimize --box: give --out (a folder under this worktree, fetched back when it ends)')
    rel = os.path.relpath(sw._abs(out), ROOT)
    decl = rest[0]
    drel = os.path.relpath(sw._abs(decl), ROOT)
    if drel.startswith('charkit/out/') and not drel.startswith('charkit/out/remote/'):
        raise SystemExit('sweep optimize --box: the declaration must reach the box: put it under charkit/out/remote/ '
                         '(synced) or a tracked folder, not %s' % drel)
    rest = [drel if x == decl else rel if x == out else x for x in rest]
    code = remote.main((['--box', name] if name else []) + ['run', '--fetch', rel, 'sweep', 'optimize'] + rest)
    if os.path.exists(os.path.join(sw._abs(out), 'history.jsonl')):
        try:
            report(sw._abs(out))
        except Exception as e:
            print('optimize: report here: %s: %s' % (type(e).__name__, e))
    return code
