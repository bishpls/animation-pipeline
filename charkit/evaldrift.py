"""The numpy evaluator against the box (Michael, 2026-09-30: trustworthy local loops). For one spec, a box build and the
fast evaluator (charkit.bodyeval, as the body fit reads it: bodyfit.BodyChecks) measure the same commit, and every check
both produce is compared. A check whose values differ by more than its tolerance is drift: a fit tuned on the evaluator
aims at a number the build doesn't give (the body round found the hems 0.024-0.028 L apart).

    python -m charkit evaldrift [SPEC] [--tol 0.01] [--out DIR]   a build on the build box, then the evaluator there on
                                                                  the same synced copy; the report fetched into DIR
                                                                  (default charkit/out/evaldrift/<spec>)
    python -m charkit evaldrift SPEC --build DIR --here           the evaluator and the comparison where it runs, against
                                                                  the build in DIR (what the box runs)

The report: DIR/drift.json and DIR/drift.md, every compared check (box value and status, evaluator value and status,
the difference, its tolerance), the drifted ones first. It exits 1 when any check drifts.
"""
import fnmatch, json, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = 'charkit/spec/clawd.json'
TOL = [                          # (check pattern, the largest difference that isn't drift), the first match wins
    ('palette_*', 0.5),          # CIEDE2000
    ('*', 0.01),                 # L, IoUs and shares
]


def tolerance(check, tol=None):
    """a check's tolerance: tol (a number) for every check, else the first TOL pattern it matches."""
    if tol is not None:
        return float(tol)
    return next(t for p, t in TOL if fnmatch.fnmatchcase(check, p))


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def compare(box, ev, tol=None):
    """box's checks against the evaluator's ({check: {value, status}} each, as qa.json names them), over the checks
    both have -> dict(rows (drifted first, then by difference), drift [names], status [names whose grade differs],
    only_box, only_eval, compared). A check drifts when its values differ by more than its tolerance (numbers) or at all
    (anything else)."""
    rows = []
    for k in sorted(set(box) & set(ev)):
        b, e = box[k] or {}, ev[k] or {}
        vb, ve = b.get('value'), e.get('value')
        if vb is None and ve is None:
            continue
        t = tolerance(k, tol)
        if _num(vb) and _num(ve):
            d = round(float(ve) - float(vb), 6)
            drift = abs(d) > t + 1e-12
        else:
            d, drift = None, vb != ve
        rows.append(dict(check=k, box=[vb, b.get('status')], eval=[ve, e.get('status')], diff=d, tol=t, drift=drift,
                         status_differs=b.get('status') != e.get('status')))
    rows.sort(key=lambda r: (not r['drift'], -(abs(r['diff']) if r['diff'] is not None else float('inf')), r['check']))
    return dict(rows=rows, compared=len(rows), drift=[r['check'] for r in rows if r['drift']],
                status=[r['check'] for r in rows if r['status_differs']],
                only_box=sorted(k for k in set(box) - set(ev) if (box[k] or {}).get('value') is not None),
                only_eval=sorted(k for k in set(ev) - set(box) if (ev[k] or {}).get('value') is not None))


def evaluator_checks(spec_path):
    """every check the fast evaluator gives for the spec, as the body fit reads them (bodyfit.BodyChecks, group 'all',
    fine: the render's subdivision) -> ({check: {value, status}}, seconds)."""
    from . import bodyeval, bodyfit, bodymeasure
    t = time.time()
    spec = bodyeval.resolve(spec_path)
    graph = bodymeasure.load_graph(spec) if spec.get('ref') else None
    C = bodyfit.BodyChecks(spec, graph).checks(spec, 'all', fine=True)
    return {k: {'value': v.get('value'), 'status': v.get('status')} for k, v in C.items()}, round(time.time() - t, 1)


def _git_of(build):
    tp = os.path.join(build, 'trace.jsonl')
    if os.path.exists(tp):
        for line in open(tp):
            rec = json.loads(line)
            if rec.get('event') == 'begin':
                return rec.get('git')
    return None


def here(spec_path, build, tol=None):
    """the evaluator against the build in `build` (its qa/qa.json), both on this machine -> the report (also written to
    build/drift.json and drift.md)."""
    qa = json.load(open(os.path.join(build, 'qa', 'qa.json')))
    box = {k: {'value': c.get('value'), 'status': c.get('status')} for k, c in qa['checks'].items()}
    ev, secs = evaluator_checks(spec_path)
    rep = dict(spec=spec_path, build=os.path.relpath(build, ROOT), git=_git_of(build), tol=tol, tolerances=TOL,
               evaluator_seconds=secs, t=time.strftime('%Y-%m-%dT%H:%M:%S'), **compare(box, ev, tol))
    json.dump(rep, open(os.path.join(build, 'drift.json'), 'w'), indent=1, default=str)
    open(os.path.join(build, 'drift.md'), 'w').write(markdown(rep))
    return rep


def markdown(rep):
    L = ['# evaldrift: %s at %s: %d of %d checks drift' % (rep['spec'], rep.get('git'), len(rep['drift']), rep['compared']),
         '', 'The box build (`%s`) against the fast evaluator (bodyeval, as bodyfit reads it) on the same commit; '
         'tolerance per check: %s. Checks only the build has: %d; only the evaluator: %d.' % (
             rep['build'], rep['tol'] if rep.get('tol') is not None else ', '.join('%s %s' % pt for pt in rep['tolerances']),
             len(rep['only_box']), len(rep['only_eval'])), '',
         '| check | box | evaluator | eval - box | tol | |', '| --- | --- | --- | --- | --- | --- |']
    for r in rep['rows']:
        L.append('| %s | %s %s | %s %s | %s | %s | %s |' % (
            r['check'], r['box'][0], r['box'][1] or '', r['eval'][0], r['eval'][1] or '',
            '' if r['diff'] is None else '%+.4f' % r['diff'], r['tol'],
            ('**drift**' if r['drift'] else '') + (' grade differs' if r['status_differs'] else '')))
    return '\n'.join(L) + '\n'


def main(args):
    if args and args[0] in ('-h', '--help'):
        print(__doc__); return 0
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    pos = [a for i, a in enumerate(args) if not a.startswith('--') and (i == 0 or args[i - 1] not in ('--tol', '--build', '--out'))]
    spec = pos[0] if pos else SPEC
    tol = float(opt('--tol')) if opt('--tol') else None
    if '--here' in args:
        rep = here(spec, os.path.join(ROOT, opt('--build')), tol)
    else:
        from . import remote
        stem = os.path.basename(spec).split('.')[0]
        out = opt('--out', 'charkit/out/evaldrift/%s' % stem)
        code = remote.build([spec, '--out', out, '--boards', 'views', '--no-blend'])
        if code:
            raise SystemExit('evaldrift: the box build failed (exit %d)' % code)
        more = ['--tol', str(tol)] if tol is not None else []
        code = remote.charkit(['evaldrift', remote._portable_spec(spec), '--build', out, '--here'] + more)
        remote._sh('fetch', ROOT, out)
        p = os.path.join(ROOT, out, 'drift.json')
        if not os.path.exists(p):
            raise SystemExit('evaldrift: the evaluator run failed on the box (exit %d)' % code)
        rep = json.load(open(p))
    print(markdown(rep).split('\n')[0])
    for r in rep['rows']:
        if r['drift']:
            print('  %-40s box %-10s eval %-10s diff %+.4f' % (r['check'], r['box'][0], r['eval'][0], r['diff'])
                  if r['diff'] is not None else '  %-40s box %s eval %s' % (r['check'], r['box'][0], r['eval'][0]))
    print('report', os.path.join(ROOT, rep['build'], 'drift.md'))
    return 1 if rep['drift'] else 0
