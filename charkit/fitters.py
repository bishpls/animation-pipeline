"""The tune loop's fitters (docs/CHARKIT.md §4): each fast fitter behind one interface, declaring which checks it targets
and which knobs it owns, so the loop can run them in turn and the triage can say who moves what.

    Fitter.name        'face', 'body', 'options'
    Fitter.landed      the real fitter is present (False: a stub, marked STUB in every record: it declares the knobs and
                       targets the real one will have, and fits nothing)
    Fitter.targets     check patterns it fits ('eye_*', 'sheet_width', ...)
    Fitter.knobs       {knob: {'path': (section, ..., key), 'default', 'step', 'bounds': (lo, hi), 'block'}} (a fitkit
                       fitter's declare(): its knobs, and its terms' checks as the targets)
    Fitter.owns        spec-path patterns it owns beyond its knobs (the knob inventory: 'body.proportions.*')
    Fitter.run(spec_path, args, out, log) -> a fit result:
        {fitter, status: fitted | no change | stub | failed, spec (the fitted spec's path), args (build options),
         changed {knob: [from, to]}, blocks {block: [knob...]}, bounds [{knob, side, value, bound}],
         sensitivity (charkit.fitkit's table, schema charkit.sensitivity/1: {knobs: {knob: {value, step, bounds, group,
         at_bound, measures: {measure: {at, minus, plus, per_step, per_unit}}}}}),
         predicted {check: [before, after]} (the fast evaluator's values), report, seconds, why}

The registry (`registry(config)`): build options first (a discrete choice per checkpoint, from the character's tune config),
then the face fitter (charkit.facefit, `python -m charkit fit`: tool/fit), then the body, garment and hair fitter
(tool/bodyfit: a stub until it lands).
"""
import copy, fnmatch, json, os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable


def _path(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


# ------------------------------------------------------------------------------------------------------------ knobs
def get(spec, path, default=None):
    d = spec
    for k in path[:-1]:
        d = d.get(k) if isinstance(d, dict) else None
        if d is None:
            return default
    return d.get(path[-1], default) if isinstance(d, dict) else default


def put(spec, path, value):
    d = spec
    for k in path[:-1]:
        d = d.setdefault(k, {})
    d[path[-1]] = value


def dotted(path):
    return '.'.join(str(p) for p in path)


def inventory(spec, prefix=()):
    """every numeric knob in a spec -> {dotted path: value}. Lists of numbers count as one knob; a list item with a
    name is addressed by it (garments.skirt.flare); structural selectors (lists mixing names and numbers, such as a
    garment's region [bone, from, to]) and the derived fit data (ref, silhouette, low_wf) are left out."""
    out = {}
    if isinstance(spec, dict):
        for k, v in spec.items():
            if k in ('ref', 'name', 'fit', 'silhouette', 'geom') or str(k).startswith('_'):
                continue
            out.update(inventory(v, prefix + (k,)))
    elif isinstance(spec, list):
        num = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool)
        if spec and all(num(x) for x in spec):
            out[dotted(prefix)] = spec
        elif spec and all(isinstance(x, list) and all(num(y) for y in x) for x in spec):
            out[dotted(prefix)] = spec                        # a table of numbers (a hem profile, bang tips): one knob
        elif any(isinstance(x, str) for x in spec):
            pass                                              # a selector (a bone name with its range)
        else:
            for i, v in enumerate(spec):
                key = v.get('name') or ('%s_%d' % (v['kind'], i) if v.get('kind') else i) if isinstance(v, dict) else i
                out.update(inventory(v, prefix + (key,)))
    elif isinstance(spec, (int, float)) and not isinstance(spec, bool):
        out[dotted(prefix)] = spec
    return out


def merge_args(base, extra):
    """build options: `extra` replaces `base`'s value of the same flag (['--hair', 'mesh'] + ['--hair', 'geom'])."""
    out, i, flags = [], 0, {}
    for seq in (base, extra):
        i = 0
        while i < len(seq):
            f = seq[i]
            val = seq[i + 1] if i + 1 < len(seq) and not str(seq[i + 1]).startswith('--') else None
            flags[f] = val
            i += 2 if val is not None else 1
    for f, v in flags.items():
        out += [f] + ([v] if v is not None else [])
    return out


class Fitter:
    name = '?'
    branch = None                 # where the real one comes from, while it is a stub
    landed = False
    targets = ()
    knobs = {}
    owns = ()

    def targets_of(self, names):
        return [n for n in names if any(fnmatch.fnmatchcase(n, p) for p in self.targets)]

    def owner_of(self, knob_path):
        return knob_path in {dotted(k['path']) for k in self.knobs.values()} or \
            any(fnmatch.fnmatchcase(knob_path, p) for p in self.owns)

    def describe(self):
        return {'name': self.name, 'landed': self.landed, 'stub': not self.landed, 'branch': self.branch,
                'targets': list(self.targets), 'knobs': {k: dict(v, path=dotted(v['path'])) for k, v in self.knobs.items()},
                'owns': list(self.owns)}

    def run(self, spec_path, args, out, log=print):
        return {'fitter': self.name, 'status': 'stub', 'why': 'STUB: %s has not landed' % (self.branch or self.name)}


# ------------------------------------------------------------------------------------------------------------ face
# STUB declaration of charkit.facefit's knobs (its KNOBS: spec path, default, step, bounds, block), used only until
# tool/fit lands; the real table is read from the module when it is present.
FACE_KNOBS_DECLARED = {
    'head.face_len': (('head', 'face_len'), 1.0, 0.04, (0.70, 1.10), 'face'),
    'head.cheek': (('head', 'cheek'), 1.0, 0.06, (0.70, 1.40), 'face'),
    'head.jaw_w': (('head', 'jaw_w'), 1.0, 0.06, (0.70, 1.60), 'face'),
    'head.chin': (('head', 'chin'), 1.0, 0.10, (0.50, 2.00), 'face'),
    'head.chin_fwd': (('head', 'chin_fwd'), 1.0, 0.06, (0.70, 1.50), 'face'),
    'head.flat': (('head', 'flat'), 1.0, 0.06, (0.60, 1.30), 'face'),
    'head.depth': (('head', 'depth'), 1.0, 0.04, (0.85, 1.20), 'face'),
    'head.nose_tip': (('head', 'nose_tip'), 0.0, 0.015, (0.0, 0.12), 'face'),
    'head.jaw_line': (('head', 'jaw_line'), 0.0, 0.2, (0.0, 1.0), 'face'),
    'head.neck_r': (('head', 'neck_r'), 1.0, 0.08, (0.6, 1.3), 'face'),
    'body.neck_w': (('body', 'proportions', 'neck_w'), 0.82, 0.06, (0.40, 1.00), 'face'),
    'body.neck_len': (('body', 'proportions', 'neck_len'), 0.72, 0.06, (0.60, 1.20), 'face'),
    'eyes.width': (('eyes', 'width'), 0.19, 0.008, (0.15, 0.25), 'eyes'),
    'eyes.height': (('eyes', 'height'), 0.62, 0.04, (0.45, 1.10), 'eyes'),
    'eyes.lower': (('eyes', 'lower'), 0.42, 0.04, (0.25, 0.60), 'eyes'),
    'eyes.lash': (('eyes', 'lash'), 0.028, 0.004, (0.015, 0.06), 'eyes'),
    'eyes.flick': (('eyes', 'flick'), 0.16, 0.03, (0.0, 0.35), 'eyes'),
    'iris.rx': (('iris', 'rx'), 0.27, 0.015, (0.18, 0.40), 'eyes'),
    'iris.rz': (('iris', 'rz'), 0.37, 0.03, (0.25, 0.60), 'eyes'),
    'iris.pupil_rx': (('iris', 'pupil_rx'), 0.085, 0.006, (0.015, 0.12), 'eyes'),
    'iris.pupil_rz': (('iris', 'pupil_rz'), 0.135, 0.015, (0.06, 0.30), 'eyes'),
}
FACE_TARGETS_DECLARED = ('eye_aspect', 'eye_width', 'eye_iris_ratio', 'eye_pupil_run', 'eye_pupil_aspect', 'eye_lid_span',
                         'eye_lid_gap', 'sheet_width', 'sheet_neck_to_jaw', 'sheet_cheek', 'sheet_cheek_chin',
                         'sheet_profile', 'sheet_nose_reach', 'sheet_chin_reach', 'sheet_profile_chin',
                         'face_shape_width', 'face_shape_cheek', 'face_shape_profile', 'face_shape_chin',
                         'face_shape_depth')


def _facefit():
    """charkit.facefit when tool/fit has landed with its command (`fit` in the CLI), else None."""
    p = os.path.join(ROOT, 'charkit', 'facefit.py')
    if not os.path.exists(p):
        return None
    try:
        from . import facefit
    except Exception:
        return None
    return facefit if hasattr(facefit, 'main') and (hasattr(facefit, 'declare') or hasattr(facefit, 'KNOBS')) else None


def _knob_table(K):
    """a fitter's knobs as {name: {path, default, step, bounds, block}}: from a declare() dict ({name: {path, default,
    step, bounds, group}}), a list of fitkit.Knob, or the older {name: (path, default, step, bounds, block)}."""
    out = {}
    if isinstance(K, dict):
        for n, v in K.items():
            if isinstance(v, dict):
                out[n] = {'path': tuple(v['path']), 'default': v.get('default'), 'step': v['step'],
                          'bounds': tuple(v['bounds']), 'block': v.get('group', v.get('block'))}
            else:
                out[n] = {'path': tuple(v[0]), 'default': v[1], 'step': v[2], 'bounds': tuple(v[3]), 'block': v[4]}
    else:
        for k in K:
            out[k.name] = {'path': tuple(k.path), 'default': k.default, 'step': k.step, 'bounds': tuple(k.bounds), 'block': k.group}
    return out


class FaceFitter(Fitter):
    """charkit.facefit (tool/fit): least squares over the face, eye and neck knobs on charkit.faceeval's fast checks."""
    name = 'face'
    branch = 'tool/fit'

    def __init__(self, budget=None, workers=None):
        self.mod = _facefit()
        self.landed = self.mod is not None
        self.budget, self.workers = budget, workers
        self.targets = FACE_TARGETS_DECLARED
        self.knobs = _knob_table(FACE_KNOBS_DECLARED)
        if self.landed:
            try:
                D = self.mod.declare() if hasattr(self.mod, 'declare') else None
                self.knobs = _knob_table(D['knobs'] if D else self.mod.KNOBS)
                if D:
                    self.targets = tuple(sorted({t['check'] for t in D['terms']}))
            except Exception:
                pass

    def run(self, spec_path, args, out, log=print):
        if not self.landed:
            return {'fitter': self.name, 'status': 'stub', 'why': 'STUB: charkit.facefit (tool/fit) has not landed'}
        from . import procs
        os.makedirs(out, exist_ok=True)
        t = time.time()
        cmd = [PY, '-m', 'charkit', 'fit', spec_path, '--out', out]
        if '--base' in args:
            cmd += ['--base', args[args.index('--base') + 1]]
        if self.budget:
            cmd += ['--budget', str(self.budget)]
        if self.workers:
            cmd += ['--workers', str(self.workers)]
        r = procs.run(cmd, out, 'fit face', cwd=ROOT, start_new_session=True)
        open(os.path.join(out, 'fit.log'), 'w').write(r.stdout + r.stderr)
        name = json.load(open(spec_path))['name']
        fitted = os.path.join(out, name + '.fit.json')
        if r.returncode or not os.path.exists(fitted):
            return {'fitter': self.name, 'status': 'failed', 'seconds': round(time.time() - t, 1),
                    'why': (r.stdout + r.stderr)[-800:]}
        res = read_fit(out, spec_path, fitted, self.knobs)
        res.update(fitter=self.name, seconds=round(time.time() - t, 1), args=list(args))
        return res

    def probe(self, spec_path, out, log=print):
        """a short look before a full fit: the sensitivity table at the spec (each knob a step either way: two fast
        evaluations per knob) and how far the fitter's own objective (fitkit's cost over its terms, the regulariser
        included) drops at the best single step -> {cost, best: [knob, side, cost], headroom (the relative drop),
        evaluations, seconds, table}, or None when it can't be measured. A fit that starts at its optimum has none."""
        t = time.time()
        T = self.sensitivity_at(spec_path, out, log)
        if not T:
            return None
        spec = json.load(open(spec_path))
        A = dict(getattr(self.mod, 'AUTHORITY', {}))
        A.update((spec.get('ref') or {}).get('authority') or {})
        r = probe_headroom(T, spec, self.mod.terms(), self.mod.KNOBS, A)
        r.update(seconds=round(time.time() - t, 1), table=T)
        return r

    def validate(self, build, log=print):
        """the fast evaluator against a finished build's own QA (`python -m charkit fit --validate BUILD`) -> rows
        [{check, eval, blender, diff, same_status}] (BUILD/qa/faceeval_agreement.json), or None."""
        if not self.landed or not hasattr(self.mod, 'validate'):
            return None
        from . import procs
        r = procs.run([PY, '-m', 'charkit', 'fit', '--validate', build], build, 'validate face', cwd=ROOT, start_new_session=True)
        p = os.path.join(build, 'qa', 'faceeval_agreement.json')
        return json.load(open(p)) if r.returncode == 0 and os.path.exists(p) else None

    def sensitivity_at(self, spec_path, out, log=print):
        """the sensitivity table at a spec (the end state's, for the triage; the fit's own is at its start) ->
        out/sensitivity.json, or None when the fitter can't measure one. Runs in a subprocess (the fit's workers)."""
        if not self.landed:
            return None
        from . import procs
        os.makedirs(out, exist_ok=True)
        code = ('import json,sys; from charkit import facefit, fitkit; '
                'spec, R, cache = facefit.prepare(sys.argv[1], sys.argv[2], log=lambda *a: None); '
                'pool = fitkit.Pool("charkit.facefit:FaceChecks", (spec, R, cache), %d); '
                'T = fitkit.sensitivity(pool, spec, facefit.KNOBS); pool.close(); '
                'json.dump(T, open(sys.argv[2] + "/sensitivity.json", "w"), indent=1)' % (self.workers or max(1, min(8, (os.cpu_count() or 2) - 2))))
        r = procs.run([PY, '-c', code, spec_path, out], out, 'sensitivity face', cwd=ROOT, start_new_session=True)
        open(os.path.join(out, 'sensitivity.log'), 'w').write(r.stdout + r.stderr)
        p = os.path.join(out, 'sensitivity.json')
        return json.load(open(p)) if r.returncode == 0 and os.path.exists(p) else None


def read_fit(out, spec_path, fitted, knobs):
    """a fit's outputs -> the fit result: the knobs it moved, those left at a bound, its sensitivity table and its
    predicted before/after per check (fit_report.json)."""
    a, b = json.load(open(spec_path)), json.load(open(fitted))
    changed, blocks, bounds = {}, {}, []
    for n, k in knobs.items():
        x0, x1 = get(a, k['path'], k['default']), get(b, k['path'], k['default'])
        if isinstance(x0, (int, float)) and isinstance(x1, (int, float)) and abs(x1 - x0) > 1e-6:
            changed[n] = [x0, x1]
            blocks.setdefault(k['block'], []).append(n)
        lo, hi = k['bounds']
        if isinstance(x1, (int, float)):
            tol = 0.05 * k['step']
            if x1 <= lo + tol:
                bounds.append({'knob': n, 'side': 'lower', 'value': x1, 'bound': lo})
            elif x1 >= hi - tol:
                bounds.append({'knob': n, 'side': 'upper', 'value': x1, 'bound': hi})
    sens = None
    sp = os.path.join(out, 'sensitivity.json')
    if os.path.exists(sp):
        sens = json.load(open(sp))
    predicted = {}
    rp = os.path.join(out, 'fit_report.json')
    if os.path.exists(rp):
        rep = json.load(open(rp))
        predicted = predicted_checks(rep)
        K = rep.get('knobs') or {}
        if K and any(isinstance(v, dict) and 'at_bound' in v for v in K.values()):     # the fit's own word on its bounds
            bounds = [{'knob': n, 'side': v['at_bound'], 'value': v.get('fitted'),
                       'bound': v['bounds'][0 if v['at_bound'] == 'lower' else 1]}
                      for n, v in K.items() if isinstance(v, dict) and v.get('at_bound')]
    return {'status': 'fitted' if changed else 'no change', 'spec': fitted, 'changed': changed, 'blocks': blocks,
            'bounds': bounds, 'sensitivity': sens, 'predicted': predicted, 'report': rp if os.path.exists(rp) else None}


def predicted_checks(rep):
    """a fit report's before/after per check -> {check: [before, after]} (the fast evaluator's values). Reads the shapes a
    report may take: {'checks': {name: {'before': {value}, 'after': {value}}}} or {'before': {name: {value}}, 'after': ...}."""
    out = {}
    C = rep.get('checks')
    if isinstance(C, dict):
        for k, c in C.items():
            if isinstance(c, dict) and 'before' in c and 'after' in c:
                v0, v1 = c['before'], c['after']
                out[k] = [v0.get('value') if isinstance(v0, dict) else v0, v1.get('value') if isinstance(v1, dict) else v1]
    for side in ('before', 'after'):
        S = rep.get(side)
        if isinstance(S, dict):
            S = S.get('checks', S)
            for k, c in S.items():
                if isinstance(c, dict) and 'value' in c:
                    out.setdefault(k, [None, None])[0 if side == 'before' else 1] = c['value']
    return out


def with_block(spec_path, fitted_path, knobs, block, out_path):
    """the spec with only one block's fitted knobs applied (a partial checkpoint) -> out_path."""
    a, b = json.load(open(spec_path)), json.load(open(fitted_path))
    S = copy.deepcopy(a)
    for n, k in knobs.items():
        if k['block'] == block:
            v = get(b, k['path'])
            if v is not None:
                put(S, k['path'], v)
    json.dump(S, open(out_path, 'w'), indent=1)
    return out_path


def probe_headroom(table, spec, terms, knobs, authority=None):
    """from a sensitivity table (charkit.sensitivity/1), the fit objective at the table's point and at each knob's step
    either way (fitkit.residuals and fitkit.cost over `terms`, with the regulariser over `knobs`, a list of fitkit.Knob)
    -> {cost, best: [knob, side, cost], headroom: (cost - best) / cost, evaluations}."""
    from . import fitkit
    K = table.get('knobs', table)

    def checks_of(flat):
        C = {}
        for m, v in flat.items():
            if v is None:
                continue
            c, _, sub = m.partition('.')
            e = C.setdefault(c, {'status': 'PASS'})
            if sub:
                if sub != 'ours':
                    e.setdefault('ratios', {})[sub] = v
            else:
                e['value'] = v
        return C
    at = {}
    for e in K.values():
        for m, d in e['measures'].items():
            at.setdefault(m, d.get('at'))
    x0 = [k.get(spec) for k in knobs]
    c0 = fitkit.cost(fitkit.residuals(checks_of(at), terms, authority), x0, knobs)
    best = None
    for i, k in enumerate(knobs):
        e = K.get(k.name)
        if not e:
            continue
        for side, sgn in (('minus', -1), ('plus', 1)):
            flat = dict(at)
            flat.update({m: d.get(side) for m, d in e['measures'].items() if d.get(side) is not None})
            x = list(x0)
            x[i] = min(k.bounds[1], max(k.bounds[0], x0[i] + sgn * k.step))
            c = fitkit.cost(fitkit.residuals(checks_of(flat), terms, authority), x, knobs)
            if best is None or c < best[2]:
                best = [k.name, side, round(float(c), 4)]
    head = (c0 - best[2]) / c0 if best and c0 > 0 else 0.0
    return {'cost': round(float(c0), 4), 'best': best, 'headroom': round(float(head), 4),
            'evaluations': 2 * len(K) + len({e.get('group') for e in K.values()})}


def interpolate(spec_path, fitted_path, knobs, t, out_path):
    """the spec with every fitted knob moved a fraction t of the way from its start to the fit (a shorter step along
    the fit's move) -> out_path."""
    a, b = json.load(open(spec_path)), json.load(open(fitted_path))
    S = copy.deepcopy(a)
    for n, k in knobs.items():
        x0, x1 = get(a, k['path'], k['default']), get(b, k['path'], k['default'])
        if isinstance(x0, (int, float)) and isinstance(x1, (int, float)) and x0 != x1:
            put(S, k['path'], round(x0 + t * (x1 - x0), 5))
    json.dump(S, open(out_path, 'w'), indent=1)
    return out_path


# ------------------------------------------------------------------------------------------------------------ body
class BodyFitter(Fitter):
    """STUB for tool/bodyfit: the body, garments, hair and palette fitted to the silhouette, model-sheet body and palette
    checks. Declares its targets and the spec sections it will own; fits nothing until it lands (then:
    `python -m charkit bodyfit`, same result shape)."""
    name = 'body'
    branch = 'tool/bodyfit'
    targets = ('shape_iou', 'shape_iou_*', 'ref_iou', 'body_*', 'palette_*', 'scalp_px', 'poke_share')
    owns = ('body.height_m', 'body.heads_tall', 'body.proportions.*', 'hair.*', 'garments.*', 'outfit.*', 'accessories.*',
            'skin.*', 'hair_colors.*', 'lash_color', 'brow_color', 'iris.top', 'iris.mid', 'iris.bottom', 'iris.ring',
            'iris.pupil')

    def __init__(self):
        self.landed = os.path.exists(os.path.join(ROOT, 'charkit', 'bodyfit.py'))
        self.knobs = {}
        if self.landed:
            try:
                from . import bodyfit
                self.knobs = _knob_table(getattr(bodyfit, 'KNOBS', {}))
                self.landed = hasattr(bodyfit, 'main')
            except Exception:
                self.landed = False

    def run(self, spec_path, args, out, log=print):
        if not self.landed:
            return {'fitter': self.name, 'status': 'stub', 'why': 'STUB: the body fitter (tool/bodyfit) has not landed'}
        from . import procs
        os.makedirs(out, exist_ok=True)
        t = time.time()
        r = procs.run([PY, '-m', 'charkit', 'bodyfit', spec_path, '--out', out], out, 'fit body', cwd=ROOT, start_new_session=True)
        open(os.path.join(out, 'fit.log'), 'w').write(r.stdout + r.stderr)
        name = json.load(open(spec_path))['name']
        fitted = os.path.join(out, name + '.fit.json')
        if r.returncode or not os.path.exists(fitted):
            return {'fitter': self.name, 'status': 'failed', 'seconds': round(time.time() - t, 1), 'why': (r.stdout + r.stderr)[-800:]}
        res = read_fit(out, spec_path, fitted, self.knobs)
        res.update(fitter=self.name, seconds=round(time.time() - t, 1), args=list(args))
        return res


# ------------------------------------------------------------------------------------------------------------ options
class OptionsFitter(Fitter):
    """build options as a discrete choice: each option in the character's tune config (`options`: {name, set: {spec
    path: value}, args: [...], targets: [...]}) is tried once as its own checkpoint and kept if the comparison accepts it.
    `set` writes into the spec (so the fitters see it too: hair.shape.mode, base); `args` go to the build."""
    name = 'options'
    landed = True

    def __init__(self, options):
        self.options = list(options or [])
        self.tried = set()
        self.targets = tuple(sorted({t for o in self.options for t in o.get('targets', ['*'])}))
        self.knobs = {}

    def pending(self, failing):
        return [o for o in self.options if o['name'] not in self.tried and
                (not failing or any(fnmatch.fnmatchcase(c, t) for c in failing for t in o.get('targets', ['*'])))]

    def run(self, spec_path, args, out, log=print, option=None):
        o = option or next(iter(self.pending(None)), None)
        if o is None:
            return {'fitter': self.name, 'status': 'no change', 'why': 'every option tried'}
        self.tried.add(o['name'])
        S = json.load(open(spec_path))
        changed = {}
        for p, v in (o.get('set') or {}).items():
            path = tuple(p.split('.'))
            old = get(S, path)
            if old != v:
                changed[p] = [old, v]
                put(S, path, v)
        new_args = merge_args(list(args), list(o.get('args') or []))
        if not changed and new_args == list(args):
            return {'fitter': self.name, 'option': o['name'], 'status': 'no change', 'why': 'already set'}
        os.makedirs(out, exist_ok=True)
        p = os.path.join(out, '%s.option-%s.json' % (S['name'], o['name']))          # one file per option
        json.dump(S, open(p, 'w'), indent=1)
        return {'fitter': self.name, 'option': o['name'], 'status': 'fitted', 'spec': p, 'args': new_args,
                'changed': changed, 'blocks': {}, 'bounds': [], 'why': o.get('why', '')}


def registry(config=None, budget=None, only=None, workers=None):
    """the fitters in the order the loop runs them (budget: each fast fitter's evaluations)."""
    config = config or {}
    F = [OptionsFitter(config.get('options')), FaceFitter(budget, workers), BodyFitter()]
    return [f for f in F if not only or f.name in only]
