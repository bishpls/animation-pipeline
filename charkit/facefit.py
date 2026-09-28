"""The face QA closes its loop: its measurements choose the face, eye and neck knobs (docs/CHARKIT.md §4). The generic
machinery (knobs, terms, the pool, the optimiser, the sensitivity table, triage) is charkit/fitkit.py; this module says
which knobs the face owns, which checks it answers to, and how to measure them fast (charkit/faceeval.py).

    python -m charkit fit SPEC.json [--out DIR] [--base anime] [--only eyes|face] [--budget N] [--workers N]
                                    [--views] [--verify] [--write-spec]
    from charkit import facefit; spec, report = facefit.fit('charkit/spec/clawd.json', 'charkit/out/clawd_fit')

  1. resolve the spec as `build` does (the manifest, refs.fit as the first guess) and cache what only Blender makes: the
     generated target and the scene's hair and garments (charkit/fit_blender.py, once per spec: charkit/out/fit_cache);
  2. measure the start with charkit.faceeval: the QA's own checks without Blender, a few seconds each;
  3. the sensitivity table (fitkit.SCHEMA): every knob a step down and up, every measured value's change, at
     DIR/sensitivity.json, with a readable summary in DIR/sensitivity.md;
  4. least squares per group (the eyes answer to the eye checks; the face and neck to the sheet and face-shape checks:
     front, three-quarter, profile and depth at once), from the start's values;
  5. DIR/NAME.fit.json: the resolved spec with the fitted knobs written in (`build` takes it as it is), DIR/fit_report.json
     and .md: every check before and after, the residuals per view, the knobs (and which ended at a bound), the triage
     of what still fails (needs a knob / knob at bound / trade-off).
  --views also fits the face to each view's terms alone: when each view can pass alone but not together, one rigid
  face can't match them all (a case for view-dependent face keys). --verify builds the fitted spec in Blender (DIR/build)
  and puts its QA in the report. --write-spec writes the fitted knobs back into SPEC.
"""
import copy, hashlib, json, os, subprocess, sys, time

import numpy as np

from . import fitkit
from .fitkit import Knob, Term

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLENDER = os.environ.get('BLENDER', '/Applications/Blender.app/Contents/MacOS/Blender')

# the knobs the face fit owns (defaults: the modules' own: head.DEFAULT_HEAD, eyes.DEFAULT_EYE, eyetex.DEFAULT_IRIS,
# body.DEFAULT_BODY)
KNOBS = [
    Knob('head.face_len', ('head', 'face_len'), 1.0, 0.03, (0.70, 1.10), 'face'),
    Knob('head.cheek', ('head', 'cheek'), 1.0, 0.06, (0.70, 1.50), 'face'),
    Knob('head.jaw_w', ('head', 'jaw_w'), 1.0, 0.08, (0.70, 2.00), 'face'),
    Knob('head.chin', ('head', 'chin'), 1.0, 0.12, (0.50, 2.20), 'face'),
    Knob('head.chin_fwd', ('head', 'chin_fwd'), 1.0, 0.05, (0.80, 1.50), 'face'),
    Knob('head.flat', ('head', 'flat'), 1.0, 0.06, (0.60, 1.30), 'face'),
    Knob('head.depth', ('head', 'depth'), 1.0, 0.03, (0.85, 1.15), 'face'),
    Knob('head.nose_tip', ('head', 'nose_tip'), 0.0, 0.015, (0.0, 0.12), 'face'),
    Knob('head.neck_r', ('head', 'neck_r'), 1.0, 0.08, (0.60, 1.30), 'face'),
    Knob('body.neck_w', ('body', 'proportions', 'neck_w'), 0.82, 0.05, (0.40, 1.00), 'face'),
    Knob('body.neck_len', ('body', 'proportions', 'neck_len'), 0.72, 0.06, (0.60, 1.20), 'face'),
    Knob('eyes.width', ('eyes', 'width'), 0.19, 0.008, (0.15, 0.25), 'eyes'),
    Knob('eyes.height', ('eyes', 'height'), 0.62, 0.04, (0.45, 1.10), 'eyes'),
    Knob('eyes.lower', ('eyes', 'lower'), 0.42, 0.04, (0.25, 0.60), 'eyes'),
    Knob('eyes.lash', ('eyes', 'lash'), 0.028, 0.004, (0.015, 0.06), 'eyes'),
    Knob('eyes.flick', ('eyes', 'flick'), 0.16, 0.03, (0.0, 0.35), 'eyes'),
    Knob('iris.rx', ('iris', 'rx'), 0.27, 0.015, (0.18, 0.40), 'eyes'),
    Knob('iris.rz', ('iris', 'rz'), 0.37, 0.03, (0.25, 0.60), 'eyes'),
    Knob('iris.pupil_rx', ('iris', 'pupil_rx'), 0.085, 0.006, (0.015, 0.12), 'eyes'),
    Knob('iris.pupil_rz', ('iris', 'pupil_rz'), 0.135, 0.015, (0.06, 0.30), 'eyes'),
]
GROUP_WHAT = {'eyes': ('eyes',), 'face': ('sheet', 'face_shape')}
# the model sheet's measures are smoothed over these sub-pixel grids while the fit searches (a pixel is 0.009 L there)
JITTER = [(0, 0, 0), (0.5, 0.5, 0.5), (0.25, 0.75, 0.5), (0.75, 0.25, 0.25)]
AUTHORITY = {'face_front': 'sheet', 'face_three_quarter': 'sheet', 'face_profile': 'sheet', 'chin': 'sheet',
             'feature_heights': 'sheet', 'face_depth': 'trellis', 'eyes': 'rig'}
VIEWS = ('front', 'three_quarter', 'profile', 'depth', 'eyes')


def terms():
    """the graded checks the face fit answers to, as fitkit terms (tolerances: each QA module's PASS limit)."""
    from . import eyeqa, faceqa, sheetqa
    E, S, F = eyeqa.LIMITS, sheetqa.LIMITS, faceqa.LIMITS
    T = [Term('eye_' + k, None, 'ratio', E[k][0], 'eyes', 'rig', 'eyes', 'eyes')
         for k in ('aspect', 'width', 'iris_ratio', 'pupil_run', 'pupil_aspect', 'lid_span')]
    T.append(Term('eye_lid_gap', None, 'gap', eyeqa.LID_GAP[0], 'eyes', 'rig', 'eyes', 'eyes'))
    for chk, sub, kind, tol, measure, ref, view in (
            ('sheet_width', 'd55', 'ratio', S['width'][0], 'face_front', 'sheet', 'front'),
            ('sheet_width', 'd75', 'ratio', S['width'][0], 'face_front', 'sheet', 'front'),
            ('sheet_neck_to_jaw', None, 'ratio', S['width'][0], 'face_front', 'sheet', 'front'),
            ('sheet_cheek', None, 'abs', S['cheek'][0], 'face_three_quarter', 'sheet', 'three_quarter'),
            ('sheet_cheek_chin', None, 'abs', S['chin'][0], 'chin', 'sheet', 'three_quarter'),
            ('sheet_profile', None, 'abs', S['profile'][0], 'face_profile', 'sheet', 'profile'),
            ('sheet_nose_reach', None, 'abs', S['reach'][0], 'face_profile', 'sheet', 'profile'),
            ('sheet_chin_reach', None, 'abs', S['reach'][0], 'face_profile', 'sheet', 'profile'),
            ('sheet_profile_chin', None, 'abs', S['chin'][0], 'chin', 'sheet', 'profile'),
            ('face_shape_width', 'mouth', 'ratio', F['width'][0], 'face_front', 'trellis', 'front'),
            ('face_shape_width', 'jaw', 'ratio', F['width'][0], 'face_front', 'trellis', 'front'),
            ('face_shape_cheek', None, 'abs', F['cheek'][0], 'face_three_quarter', 'trellis', 'three_quarter'),
            ('face_shape_profile', None, 'abs', F['profile'][0], 'face_profile', 'trellis', 'profile'),
            ('face_shape_chin', None, 'abs', F['chin'][0], 'chin', 'trellis', 'profile'),
            ('face_shape_depth', 'cheeks', 'abs', F['depth'][0], 'face_depth', 'trellis', 'depth'),
            ('face_shape_depth', 'chin', 'abs', F['depth'][0], 'face_depth', 'trellis', 'depth')):
        T.append(Term(chk, sub, kind, tol, measure, ref, view, 'face'))
    return T


def declare():
    """what the face fit owns and answers to: {'knobs': {name: {path, default, step, bounds, group}}, 'terms': [...]}."""
    return {'knobs': {k.name: k.declare() for k in KNOBS}, 'terms': [t.declare() for t in terms()]}


class FaceChecks:
    """the fit's evaluator in each worker (fitkit's protocol): the face's checks for a spec, per group ('all': every
    check, with the hair and clothes); fine=False smooths the sheet's measures over JITTER."""

    def __init__(self, spec, R, cache):
        from . import faceeval
        self.E = faceeval.Evaluator(spec, R, cache)

    def checks(self, spec, group, fine=False):
        what = GROUP_WHAT.get(group, ('eyes', 'sheet', 'face_shape'))
        return self.E.run(spec, what=what, covers=(group == 'all'), jitter=None if fine else JITTER)['checks']


# ------------------------------------------------------------------------------------------------------------ preparing
def _p(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def cache_dir(spec):
    """where fit_blender's arrays for this spec live: keyed by what makes them (body, hair, garments, the target)."""
    keys = {k: spec.get(k) for k in ('base', 'body', 'hair', 'hair_colors', 'accessories', 'garments', 'eyes')}
    h = hashlib.sha1(json.dumps(keys, sort_keys=True, default=str).encode()).hexdigest()[:12]
    return os.path.join(ROOT, 'charkit', 'out', 'fit_cache', '%s_%s' % (spec['name'], h))


def prepare(spec_path, out, base=None, log=print):
    """the resolved spec (as `build` resolves it), the rig's measures, and the Blender caches. -> (spec, R, cache)."""
    from . import cli
    os.makedirs(out, exist_ok=True)
    spec, resolved = cli.resolve(spec_path, out, base=base)
    R = json.load(open(os.path.join(out, 'ref_measure.json')))
    cache = cache_dir(spec)
    if not (os.path.exists(os.path.join(cache, 'target.npz')) and os.path.exists(os.path.join(cache, 'env.npz'))):
        os.makedirs(cache, exist_ok=True)
        log('fit: caching the target, hair and garments in Blender -> %s' % cache)
        cmd = [BLENDER, '-b', '--factory-startup', '--python', os.path.join(ROOT, 'charkit', 'fit_blender.py'), '--',
               resolved, cache, '--env']
        r = subprocess.run(cmd, capture_output=True, text=True)
        if 'CHARKIT_FIT_BLENDER_DONE' not in r.stdout:
            sys.stderr.write(r.stdout[-3000:] + r.stderr[-3000:])
            raise SystemExit('fit: the Blender cache step failed')
    return spec, R, cache


# ------------------------------------------------------------------------------------------------------------ the fit
def fit(spec, out, budget=None, base=None, workers=None, groups=('eyes', 'face'), views=False, log=print):
    """fit the face, eye and neck knobs of a spec (a path, or a dict already resolved with out/ref_measure.json in place)
    to its QA; write the fitted spec and the reports into out. budget: the most evaluations (each a few seconds of one
    core), None: each group's own limit. -> (fitted spec, report)."""
    t0 = time.time()
    os.makedirs(out, exist_ok=True)
    if isinstance(spec, str):
        spec, R, cache = prepare(spec, out, base=base, log=log)
    else:
        spec = copy.deepcopy(spec)
        R = json.load(open(os.path.join(out, 'ref_measure.json')))
        cache = cache_dir(spec)
    authority = dict(AUTHORITY); authority.update((spec.get('ref') or {}).get('authority') or {})
    T = terms()
    workers = workers or max(1, min(8, (os.cpu_count() or 2) - 2))
    pool = fitkit.Pool('charkit.facefit:FaceChecks', (spec, R, cache), workers)
    rep = {'spec': spec['name'], 'base': spec.get('base', 'makehuman'), 'authority': authority, 'declare': declare(),
           'groups': {}}
    try:
        before = pool.map([(spec, 'all', True)])[0]         # the start, as the QA measures it (hair and clothes too)
        log('fit: start measured')
        table = fitkit.sensitivity(pool, spec, [k for k in KNOBS if k.group in groups])
        json.dump(table, open(os.path.join(out, 'sensitivity.json'), 'w'), indent=1)
        open(os.path.join(out, 'sensitivity.md'), 'w').write(sensitivity_md(table, T))
        log('fit: sensitivity table written (%d knobs)' % len(table['knobs']))
        fitted, left = spec, budget
        for g in groups:
            share = None if left is None else max(20, int(left * sum(k.group == g for k in KNOBS) /
                                                          max(1, sum(k.group in groups for k in KNOBS))))
            fitted, info = fitkit.optimise(pool, fitted, KNOBS, T, g, authority, budget=share, log=log)
            rep['groups'][g] = {k: v for k, v in info.items() if k != 'history'}
            rep['groups'][g]['cost_history'] = [h['cost'] for h in info['history']]
            if left is not None:
                left = max(0, left - info['evaluations'])
        after = pool.map([(fitted, 'all', True)])[0]
        if views:
            rep['views_alone'] = views_alone(pool, spec, T, authority, log)
    finally:
        pool.close()
    fitted = copy.deepcopy(fitted)
    fitted['fit'] = {'by': 'charkit.facefit', 'knobs': {k.name: k.get(fitted) for k in KNOBS if k.group in groups}}
    rb, ra = fitkit.residuals(before, T, authority), fitkit.residuals(after, T, authority)
    rep.update(before=summary(before), after=summary(after), residuals=per_view(rb, ra),
               knobs={k.name: {'start': k.get(spec), 'fitted': k.get(fitted), 'default': k.default,
                               'bounds': list(k.bounds), 'at_bound': k.at_bound(k.get(fitted))}
                      for k in KNOBS if k.group in groups},
               triage=fitkit.triage(ra, table, KNOBS, fitted), sensitivity=os.path.join(out, 'sensitivity.json'),
               seconds=round(time.time() - t0, 1), evaluations=sum(g['evaluations'] for g in rep['groups'].values()))
    p = os.path.join(out, spec['name'] + '.fit.json')
    json.dump(fitted, open(p, 'w'), indent=1)
    rep['fitted_spec'] = p
    json.dump(rep, open(os.path.join(out, 'fit_report.json'), 'w'), indent=1, default=str)
    open(os.path.join(out, 'fit_report.md'), 'w').write(report_md(rep))
    log('fit: wrote %s (%.0f s)' % (p, rep['seconds']))
    return fitted, rep


def views_alone(pool, spec, T, authority, log=print):
    """the face fitted to each view's terms alone (all together is the main fit): each view's best residuals."""
    out = {}
    for view in ('front', 'three_quarter', 'profile', 'depth'):
        sub = [t for t in T if t.group == 'face' and t.view == view]
        s2, info = fitkit.optimise(pool, spec, KNOBS, sub, 'face', authority, log=lambda *a: None)
        res = fitkit.residuals(pool.map([(s2, 'face', True)])[0], sub, authority)
        out[view] = {'rms': round(float(np.sqrt(np.mean([r['r'] ** 2 for r in res]))), 3),
                     'worst': max(res, key=lambda r: abs(r['r']))['name'], 'max': round(max(abs(r['r']) for r in res), 3),
                     'fitted': info['fitted'], 'evaluations': info['evaluations']}
        log('fit: %s alone -> RMS %.2f' % (view, out[view]['rms']))
    return out


# ------------------------------------------------------------------------------------------------------------ reporting
def summary(checks):
    """a check set, the fields worth keeping: value, status, and the per-part numbers."""
    keep = ('value', 'status', 'ours', 'design', 'ratios', 'regions', 'per_height', 'missing')
    return {k: {q: v for q, v in c.items() if q in keep} for k, c in checks.items() if isinstance(c, dict)}


def per_view(rb, ra):
    """the residuals grouped by view, before and after: each term, and the view's RMS and how many pass."""
    out = {}
    for v in VIEWS:
        b = [r for r in rb if r['view'] == v]; a = [r for r in ra if r['view'] == v]
        if not b:
            continue
        rows = [{'term': x['name'], 'ref': x['ref'], 'weight': x['w'], 'before': round(x['r'], 3), 'after': round(y['r'], 3),
                 'value_after': y['value']} for x, y in zip(b, a)]
        rms = lambda s: round(float(np.sqrt(np.mean([r['r'] ** 2 for r in s]))), 3)
        out[v] = {'rms_before': rms(b), 'rms_after': rms(a), 'within_tolerance_after': sum(abs(r['r']) <= 1 for r in a),
                  'terms': len(a), 'rows': rows}
    return out


def sensitivity_md(table, T):
    """the sensitivity table, readable: per knob the graded terms it moves most, and per term the knobs that move it
    (in the term's PASS tolerances per knob step)."""
    tol = {t.name: t.tol for t in T}
    L = ['# Sensitivity (%s)' % table['schema'], '',
         "Each knob one step down and up from the fit's start. The numbers: a graded term's change over one knob step, in "
         "units of its PASS tolerance (so 1.0 = one step moves it a whole tolerance).", '', '## Per knob', '']
    for n, e in table['knobs'].items():
        rows = sorted(((abs(d['per_step'] / tol[m]), m, d['per_step'] / tol[m]) for m, d in e['measures'].items()
                       if d.get('per_step') is not None and m in tol), reverse=True)
        top = ', '.join('%s %+.2f' % (m, v) for _, m, v in rows[:5] if abs(v) >= 0.05) or 'nothing graded moves'
        L.append('- **%s** = %.4g (step %.4g, bounds %s%s): %s' % (n, e['value'], e['step'], e['bounds'],
                                                                  ', at its %s bound' % e['at_bound'] if e['at_bound'] else '', top))
    L += ['', '## Per graded term', '']
    for t in T:
        rows = sorted(((abs(e['measures'][t.name]['per_step'] / t.tol), n, e['measures'][t.name]['per_step'] / t.tol)
                       for n, e in table['knobs'].items()
                       if t.name in e['measures'] and e['measures'][t.name].get('per_step') is not None), reverse=True)
        top = ', '.join('%s %+.2f' % (n, v) for _, n, v in rows[:4] if abs(v) >= 0.05) or '**no knob moves it**'
        L.append('- %s (%s, tol %g): %s' % (t.name, t.view, t.tol, top))
    return '\n'.join(L) + '\n'


def report_md(rep):
    L = ['# Face fit: %s (%s base)' % (rep['spec'], rep['base']), '',
         '%d evaluations, %.0f s. Fitted spec: `%s`. Sensitivity: `%s`.' % (rep['evaluations'], rep['seconds'],
                                                                         rep['fitted_spec'], rep['sensitivity']), '',
         "## Checks, before and after (charkit.faceeval: the QA's own measures)", '', '| check | before | after |',
         '|---|---|---|']
    b, a = rep['before'], rep['after']
    f = lambda c: '' if not c else '%s %s' % (json.dumps(c.get('value')), c.get('status', ''))
    for k in sorted(set(b) | set(a)):
        if k.startswith(('eye_', 'sheet_', 'face_shape_')):
            L.append('| %s | %s | %s |' % (k, f(b.get(k)), f(a.get(k))))
    L += ['', '## Residuals per view (in tolerances; |r| <= 1 passes)', '']
    for v, d in rep['residuals'].items():
        L += ['**%s**: RMS %.2f -> %.2f, %d of %d within tolerance' % (v, d['rms_before'], d['rms_after'],
                                                                      d['within_tolerance_after'], d['terms']),
              '', '| term | ref | weight | before | after |', '|---|---|---|---|---|']
        L += ['| %s | %s | %.2f | %+.2f | %+.2f |' % (r['term'], r['ref'], r['weight'], r['before'], r['after']) for r in d['rows']]
        L.append('')
    if rep.get('views_alone'):
        L += ['## Each view fitted alone', '', '| view | RMS alone | worst alone | RMS in the joint fit |', '|---|---|---|---|']
        for v, d in rep['views_alone'].items():
            L.append('| %s | %.2f | %s %+.2f | %.2f |' % (v, d['rms'], d['worst'], d['max'], rep['residuals'][v]['rms_after']))
        L.append('')
    L += ['## Knobs', '', '| knob | start | fitted | default | bounds | at bound |', '|---|---|---|---|---|---|']
    for n, k in rep['knobs'].items():
        L.append('| %s | %.4g | %.4g | %.4g | %s | %s |' % (n, k['start'], k['fitted'], k['default'], k['bounds'], k['at_bound'] or ''))
    L += ['', '## Still outside tolerance', '']
    for t in rep['triage'] or []:
        L.append('- %s (r %+.2f): **%s**%s' % (t['term'], t['r'], t['why'], (' — ' + ', '.join(
            '%s %+.2f/step%s' % (k['knob'], k['per_step_tol'], ' (blocked)' if k['blocked'] else '') for k in t['knobs'][:3]))
            if t['knobs'] else ''))
    if rep.get('verify'):
        L += ['', '## Blender build of the fitted spec', '', '`%s`: %s' % (rep['verify'].get('out'), rep['verify'].get('summary'))]
    return '\n'.join(L) + '\n'


# ------------------------------------------------------------------------------------------------------------ cli
def write_spec(src, fitted, groups=('eyes', 'face')):
    """the fitted knobs written back into the source spec (only the knobs the fit owns)."""
    S = json.load(open(src))
    for k in KNOBS:
        if k.group in groups:
            k.put(S, k.get(fitted))
    json.dump(S, open(src, 'w'), indent=1)


def main(args):
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    spec_path = args[0]
    name = json.load(open(spec_path))['name']
    out = _p(opt('--out', 'charkit/out/%s_fit' % name))
    groups = (opt('--only'),) if opt('--only') else ('eyes', 'face')
    fitted, rep = fit(spec_path, out, budget=int(opt('--budget')) if opt('--budget') else None, base=opt('--base'),
                      workers=int(opt('--workers')) if opt('--workers') else None, groups=groups, views='--views' in args)
    if '--verify' in args:
        from . import cli
        bout = os.path.join(out, 'build')
        cli.build([rep['fitted_spec'], '--out', bout, '--boards', 'views,expressions'])
        qa = json.load(open(os.path.join(bout, 'qa', 'qa.json')))
        rep['verify'] = {'out': bout, 'summary': qa.get('summary'),
                         'checks': {k: [v.get('value'), v.get('status')] for k, v in qa['checks'].items() if k != 'mesh'}}
        json.dump(rep, open(os.path.join(out, 'fit_report.json'), 'w'), indent=1, default=str)
        open(os.path.join(out, 'fit_report.md'), 'w').write(report_md(rep))
    if '--write-spec' in args:
        write_spec(spec_path, fitted, groups)
        print('wrote the fitted knobs into', spec_path)
    for v, d in rep['residuals'].items():
        print('%-14s RMS %.2f -> %.2f  (%d/%d within tolerance)' % (v, d['rms_before'], d['rms_after'],
                                                                    d['within_tolerance_after'], d['terms']))
    print('report', os.path.join(out, 'fit_report.md'))
