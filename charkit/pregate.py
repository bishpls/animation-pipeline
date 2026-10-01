"""The local pre-gate check (docs/ROADMAP.md "Iteration speed", redesign item 2): the fast evaluator's checks on this
worktree as it is (uncommitted edits included) against pipeline-3d's, judged as the gate judges them (charkit.gate's
compare_qa and judge: policy K), on the laptop, before a box gate. The evaluator is charkit.bodyeval as the body fit
reads it (charkit.evaldrift.evaluator_checks): the silhouettes (shape_*, ref_iou), the model sheet's body_*, palette_*,
the face's sheet_* and the pieces. The target's side runs once per commit, in a sparse worktree of it (its own code),
kept in charkit/out/pregate/base_COMMIT_SPEC.json; each iteration then evaluates this worktree alone.

    python -m charkit pregate [--into pipeline-3d] [--spec SPEC]    this worktree against the target's head
    python -m charkit pregate --pair TIP [--into HEAD]              the merge of TIP into HEAD (commits), as a gate does
    python -m charkit pregate --against GATE_REPORT.json            that report's pair, then the agreement: which checks
                                                                    the gate and the pre-gate saw move, and which way
    python -m charkit pregate --rejudge PREGATE_REPORT.json         judged again from the checks it holds
    python -m charkit pregate --box [NAME | auto] [--into BASE]     this branch's committed tip merged into BASE, on a
                                                                    box (charkit.remote.pregate: the laptop is shared;
                                                                    auto: the build box while it has room, else the
                                                                    box with the most free slots)

K blocks only on checks the gate's QA names (gate_names: every check in this repository's gate reports); the
evaluator's own rows (bodymeasure's per-view, per-side pieces) that would block are listed apart.

The report: charkit/out/pregate/pregate_TAG_into_HEAD.{md,json}: K's verdict, what blocks, the moves, the coverage and
the seconds. Exit 0 PASS, 1 FAIL.

What it can't see (the gate still does): the Blender build's own geometry (subdivision, Solidify, the cut-piece hair:
the evaluator's hair is the generated shape; docs/GEOM_TRUTH.md step 7b), the QA parts that need the full bundle
(art_*, hair_*, poke, mesh, eyes, expressions, the charkit.render drawing), the 2x2, the tests and the CPU. The
evaluator's values drift from the build's (evaldrift); a pre-gate compares the evaluator with itself, so what it
reports is the move.
"""
import json, os, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'charkit', 'out', 'pregate')
PY = sys.executable
SPEC = 'charkit/spec/clawd.json'
# (run in the tree, with its own code: the build's resolve and venv steps, cached, into OUT, then the evaluator on the
# resolved spec, as evaldrift reads a build's; a spec file alone lacks the code head's and body's geometry files)
# (only what older commits have too: a target from before evaldrift or the garments step still evaluates)
_EVAL = """import json, os, sys, time
from charkit import cli, bodyeval, bodyfit, bodymeasure
spec_path, res, out = sys.argv[1:4]
os.makedirs(out, exist_ok=True)
T = {}
t = time.time()
spec, resolved = cli.resolve(spec_path, out)
T['resolve'] = round(time.time() - t, 1)
for n in ('code_head', 'code_body', 'geom_hair', 'pieces_hair', 'garments_geom'):
    if hasattr(cli, n):
        t = time.time()
        spec = getattr(cli, n)(spec, resolved, out, 'on')
        T[n] = round(time.time() - t, 1)
t = time.time()
S = bodyeval.resolve(resolved)
graph = bodymeasure.load_graph(S) if S.get('ref') else None
C = bodyfit.BodyChecks(S, graph).checks(S, 'all', fine=True)
T['evaluator'] = round(time.time() - t, 1)
C = {k: {'value': v.get('value'), 'status': v.get('status')} for k, v in C.items()}
json.dump({'checks': C, 'seconds': T['evaluator'], 'steps': T}, open(res, 'w'), default=float)
"""


def _git(*a, cwd=ROOT, check=True):
    return subprocess.run(['git', *a], cwd=cwd, capture_output=True, text=True, check=check)


def evaluate(tree, spec=SPEC):
    """the evaluator's checks with tree's own code (a subprocess in tree) -> {'checks': {check: {value, status}},
    'seconds': the evaluator's, 'wall': the process's}."""
    fd, p = tempfile.mkstemp(suffix='.json', prefix='pregate-')
    os.close(fd)
    t = time.time()
    try:
        r = subprocess.run([PY, '-c', _EVAL, spec, p, os.path.join(tree, 'charkit', 'out', 'pregate', 'prep')],
                           cwd=tree, capture_output=True, text=True, env=_env())
        if r.returncode:
            raise SystemExit('pregate: the evaluator failed in %s:\n%s' % (tree, (r.stdout + r.stderr)[-2000:]))
        out = json.load(open(p))
    finally:
        os.remove(p)
    out['wall'] = round(time.time() - t, 1)
    return out


def _env():
    """the venv steps' entries in one folder the pre-gate's trees share (the target's worktree and this one: an
    unchanged step restores), keyed on all the code a step reaches, as the gate's builds are (gate._step_cache_env)."""
    from . import gate
    return dict(os.environ, **gate._step_cache_env())


def _tree(rev, spec, merge=None):
    """a sparse worktree at rev (the gate's: its generated inputs linked), with merge merged in when given."""
    from . import gate
    wt = gate._worktree(rev, spec, 'pregate')
    if merge:
        m = _git('merge', '--no-commit', '--no-ff', merge, cwd=wt, check=False)
        if m.returncode:
            _drop(wt)
            raise SystemExit('pregate: %s does not merge cleanly into %s' % (merge, rev))
    return wt


def _drop(wt):
    import shutil
    _git('worktree', 'remove', '--force', wt, check=False)
    shutil.rmtree(wt, ignore_errors=True)


def baseline(head, spec=SPEC, fresh=False):
    """the target commit's evaluator checks, kept per commit and spec -> (the result, its file, whether it was kept)."""
    stem = os.path.basename(spec).split('.')[0]
    p = os.path.join(OUT, 'base_%s_%s.json' % (head, stem))
    if os.path.exists(p) and not fresh:
        return json.load(open(p)), p, True
    wt = _tree(head, spec)
    try:
        r = evaluate(wt, spec)
    finally:
        _drop(wt)
    r['commit'] = head
    os.makedirs(OUT, exist_ok=True)
    json.dump(r, open(p, 'w'), indent=1)
    return r, p, False


def _steps_at(rev):
    from . import history
    fd, p = tempfile.mkstemp(suffix='.py')
    os.close(fd)
    try:
        open(p, 'w').write(_git('show', '%s:charkit/history.py' % rev).stdout)
        return history.load_steps(p) or []
    finally:
        os.remove(p)


def remeasured_here(head):
    """the measurement steps this worktree registers that head doesn't -> {check pattern: why}."""
    from . import history
    have = {(s[0], s[1]) for s in _steps_at(head)}
    return {s[0]: s[2] for s in history.load_steps(os.path.join(ROOT, 'charkit', 'history.py')) or []
            if (s[0], s[1]) not in have}


def gate_names(dirs=None):
    """the check names the gate's QA gives, as far as its reports here show (every row of every gate report in this
    repository's worktrees: the checks that ever moved or went) -> set. The evaluator also measures checks the build's
    QA doesn't name (bodymeasure's per-view, per-side piece rows: piece_shorts_profile_top), which a gate can't block on."""
    import glob
    from . import gate
    names = set()
    for d in dirs or gate._report_dirs():
        for p in glob.glob(os.path.join(d, 'gate_*.json')):
            if p.endswith('.summary.json'):
                continue
            try:
                R = json.load(open(p))
            except (OSError, ValueError):
                continue
            names |= {r.get('check') for r in list(R.get('qa') or []) + list((R.get('twobytwo') or {}).get('rows') or [])
                      if isinstance(r, dict)}
    names.discard(None)
    return names


def judge(base, cand, remeasured, known=None):
    """K on the evaluator's two check sets -> (verdict, blocking, report, rows). known: the checks the gate names
    (gate_names()); a blocking row on a check outside them is reported (report['evaluator_only']), not blocking."""
    from . import gate
    qa_a, qa_b = {'checks': base['checks']}, {'checks': cand['checks']}
    rows = gate.compare_qa(qa_a, qa_b, remeasured)
    rep = {'qa': rows, 'hard': []}
    v, block, R = gate.judge(rep, qa_a, qa_b)
    if known is not None:
        R['evaluator_only'] = [b for b in block if b.get('check') not in known]
        block = [b for b in block if b.get('check') in known]
        v = 'FAIL' if block else 'PASS'
    return v, block, R, rows


def agreement(gate_rep, rows, base, cand, known=None):
    """the pre-gate's moves against a real gate's, over the checks both measure: a check moved (its value or status
    changed) in one and not the other, and for the moved in both whether they agree on the way (the status's, else the
    value's sign) -> dict."""
    E = set(base['checks']) | set(cand['checks'])
    G = {r['check']: r for r in gate_rep.get('qa') or () if r['check'] in E}
    P = {r['check']: r for r in rows}
    both = sorted(set(G) & set(P))

    def way(r):
        v = r.get('verdict')
        if v in ('regressed', 'improved'):
            return v
        (a, _), (b, _) = r.get('base') or [None, None], r.get('cand') or [None, None]
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
            return 'up' if b > a else 'down' if b < a else 'same'
        return v
    same_way = [k for k in both if way(G[k]) == way(P[k])]
    gate_all = {r['check'] for r in gate_rep.get('qa') or ()}
    out = dict(measured=len(E), gate_moved=len(G), pregate_moved=len(P), both=len(both), same_way=len(same_way),
                gate_only=sorted(set(G) - set(P)), pregate_only=sorted(set(P) - set(G)),
                disagree=[dict(check=k, gate=[G[k]['base'], G[k]['cand'], G[k]['verdict']],
                               pregate=[P[k]['base'], P[k]['cand'], P[k]['verdict']]) for k in both if k not in same_way],
                unseen=len(gate_all - E), gate_checks_moved=len(gate_all),
                recall=round(len(both) / len(G), 3) if G else None,
                precision=round(len(both) / len(P), 3) if P else None,
                verdict=[gate_rep.get('verdict'), None])
    if known:                                   # the pre-gate's moves on checks the gate's QA names at all
        Pk = [k for k in P if k in known]
        out.update(pregate_moved_named=len(Pk), precision_named=round(len(set(Pk) & set(G)) / len(Pk), 3) if Pk else None,
                   pregate_only_named=sorted(set(Pk) - set(G)))
    return out


def run(into='pipeline-3d', spec=SPEC, pair=None, report=None, fresh=False, name=None):
    """the pre-gate: this worktree (or pair's merge into `into`) against `into`'s head -> the report dict (written)."""
    from . import history
    t0 = time.time()
    head = _git('rev-parse', '--short', into).stdout.strip()
    if pair:
        tip = _git('rev-parse', '--short', pair).stdout.strip()
        tag = '%s_%s' % ((name or pair).replace('/', '-'), tip)
    else:
        tip = _git('rev-parse', '--short', 'HEAD').stdout.strip()
        dirty = bool(_git('status', '--porcelain', '--', 'charkit').stdout.strip())
        tag = '%s_%s%s' % (_git('rev-parse', '--abbrev-ref', 'HEAD').stdout.strip().replace('/', '-'), tip,
                           '+dirty' if dirty else '')
    base, bpath, kept = baseline(head, spec, fresh)
    t1 = time.time()
    if pair:
        wt = _tree(head, spec, merge=tip)
        try:
            cand = evaluate(wt, spec)
            steps = history.load_steps(os.path.join(wt, 'charkit', 'history.py')) or []
        finally:
            _drop(wt)
        remeasured = history.steps_between(head, tip, steps, repo=ROOT)
    else:
        cand = evaluate(ROOT, spec)
        remeasured = remeasured_here(head)
    known = gate_names()
    v, block, R, rows = judge(base, cand, remeasured, known if len(known) > 50 else None)
    rep = dict(tag=tag, tip=tip, into=into, head=head, spec=spec, verdict=v, blocking=block, report=R, qa=rows,
               remeasured=remeasured, checks=len(set(base['checks']) | set(cand['checks'])),
               seconds=dict(total=round(time.time() - t0, 1), baseline=None if kept else round(t1 - t0, 1),
                            candidate=cand['wall'], evaluator=cand['seconds']),
               baseline=os.path.relpath(bpath, ROOT), t=time.strftime('%Y-%m-%dT%H:%M:%S'))
    if report:
        rep['against'] = os.path.basename(report['path'])
        rep['agreement'] = agreement(report, rows, base, cand, known)
        rep['agreement']['verdict'][1] = v
    os.makedirs(OUT, exist_ok=True)
    stem = os.path.join(OUT, 'pregate_%s_into_%s' % (tag, head))
    json.dump(dict(rep, base=base, cand=cand), open(stem + '.json', 'w'), indent=1, default=float)
    open(stem + '.md', 'w').write(markdown(rep))
    rep['md'] = stem + '.md'
    return rep


def rejudge(path):
    """a pre-gate report (its json) judged again from the check sets it holds (no evaluation): the names the gate's
    reports know now, the agreement with its gate report again -> the report dict (rewritten)."""
    R = json.load(open(path))
    base, cand = R.pop('base'), R.pop('cand')
    known = gate_names()
    v, block, Rep, rows = judge(base, cand, R.get('remeasured') or {}, known if len(known) > 50 else None)
    R.update(verdict=v, blocking=block, report=Rep, qa=rows)
    if R.get('against'):
        from . import gate
        g = next((os.path.join(d, R['against']) for d in gate._report_dirs()
                  if os.path.exists(os.path.join(d, R['against']))), None)
        if g:
            R['agreement'] = agreement(json.load(open(g)), rows, base, cand, known)
            R['agreement']['verdict'][1] = v
    json.dump(dict(R, base=base, cand=cand), open(path, 'w'), indent=1, default=float)
    open(path[:-5] + '.md', 'w').write(markdown(R))
    R['md'] = path[:-5] + '.md'
    return R


def markdown(rep):
    from . import gate
    L = ['# Pre-gate: %s into %s (%s)\n' % (rep['tag'], rep['into'], rep['head']),
         '**%s** under K on the evaluator\'s %d checks (%s). %.0f s (baseline %s, candidate %.0f s).\n' % (
             rep['verdict'], rep['checks'], rep['spec'], rep['seconds']['total'],
             'kept' if rep['seconds']['baseline'] is None else '%.0f s' % rep['seconds']['baseline'],
             rep['seconds']['candidate'])]
    L.append('## Blocking\n')
    L += ['- ' + gate._why(b) for b in rep['blocking']] or ['Nothing.']
    eo = (rep.get('report') or {}).get('evaluator_only') or []
    if eo:
        L.append('\nWould block, but the gate\'s QA has no such check (the evaluator\'s own rows; not blocking):\n')
        L += ['- ' + gate._why(b) for b in eo]
    L.append('\n## Moved (%d)\n' % len(rep['qa']))
    if rep['qa']:
        L.append('| check | baseline | candidate | verdict |\n| --- | --- | --- | --- |')
        for r in sorted(rep['qa'], key=lambda r: (r['verdict'] != 'regressed', r['check'])):
            L.append('| %s | %s | %s | %s |' % (r['check'], gate._cell(r['base']), gate._cell(r['cand']), r['verdict']))
    A = rep.get('agreement')
    if A:
        L.append('\n## Against the gate (%s)\n' % rep['against'])
        L.append('- the evaluator measures %d checks; the gate moved %d checks in all, %d of them measured here (%d of '
                 'the gate\'s moved checks are outside the evaluator)' % (A['measured'], A['gate_checks_moved'],
                                                                        A['gate_moved'], A['unseen']))
        L.append('- moved in both: %d (recall %s of the gate\'s, precision %s of the pre-gate\'s); the same way: %d' % (
            A['both'], A['recall'], A['precision'], A['same_way']))
        if A.get('precision_named') is not None:
            L.append("- on the checks the gate's QA names: the pre-gate moved %d, precision %s; moved here only: %s" % (
                A['pregate_moved_named'], A['precision_named'], ', '.join(A['pregate_only_named'][:30]) or 'none'))
        L.append('- verdicts: gate %s, pre-gate %s' % tuple(A['verdict']))
        if A['gate_only']:
            L.append('- the gate only: ' + ', '.join(A['gate_only'][:40]))
        if A['pregate_only']:
            L.append('- the pre-gate only: ' + ', '.join(A['pregate_only'][:40]))
        for d in A['disagree'][:20]:
            L.append('- other way: %s: gate %s -> %s (%s), pre-gate %s -> %s (%s)' % (
                d['check'], gate._cell(d['gate'][0]), gate._cell(d['gate'][1]), d['gate'][2],
                gate._cell(d['pregate'][0]), gate._cell(d['pregate'][1]), d['pregate'][2]))
    L.append("\nNot covered here (the gate's): the Blender build's geometry, the full bundle's QA parts (art_*, hair_*, "
             "poke, mesh, eyes, expressions, the render drawing), the 2x2, the tests, the CPU.")
    return '\n'.join(L) + '\n'


def main(args):
    if args and args[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    report = None
    if '--box' in args:
        from . import remote
        i = args.index('--box')
        name = args[i + 1] if i + 1 < len(args) and not args[i + 1].startswith('-') else None
        rest = args[:i] + args[i + (2 if name else 1):]
        if name == 'auto':
            name, _ = remote.pick_box()
            print('pregate --box auto: %s' % name)
        remote.BOX['env'] = os.path.join(ROOT, 'infra', 'gcp', (name or 'build') + '.env')
        remote.BOX['chosen'] = True
        return remote.pregate(rest)
    if opt('--rejudge'):
        rep = rejudge(opt('--rejudge'))
        print('pregate (rejudged): %s, %d blocking; %s' % (rep['verdict'], len(rep['blocking']), rep['md']))
        return 0 if rep['verdict'] == 'PASS' else 1
    pair, into = opt('--pair'), opt('--into', 'pipeline-3d')
    spec = opt('--spec', SPEC)
    if opt('--against'):
        report = json.load(open(opt('--against')))
        report['path'] = opt('--against')
        pair, into, spec = report['tip'], report['head'], report.get('spec') or spec
    rep = run(into, spec, pair=pair, report=report, fresh='--fresh' in args, name=report and report.get('branch'))
    print('pregate: %s (%d moved, %d blocking), %.0f s; report %s' % (rep['verdict'], len(rep['qa']),
                                                                     len(rep['blocking']), rep['seconds']['total'],
                                                                     rep['md']))
    A = rep.get('agreement')
    if A:
        print('against the gate: %d moved in both of %d (gate) and %d (pre-gate), %d the same way; verdicts %s / %s'
              % (A['both'], A['gate_moved'], A['pregate_moved'], A['same_way'], *A['verdict']))
    return 0 if rep['verdict'] == 'PASS' else 1
