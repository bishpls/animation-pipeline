"""The merge gate: what a branch would do to the integration branch, measured before it lands. Nothing is merged and no
branch moves: a throwaway worktree at the integration head builds the baseline (cached per commit and build options),
takes the branch with `git merge --no-commit`, runs the tests, builds again, and the two builds' QA and traces are
compared.

    python -m charkit gate BRANCH [--into REF] [--spec SPEC] [--args "--base anime"] [--keep]

The verdict:
  FAIL   the merge conflicts, a test fails, a build fails, or a graded check gets worse (PASS -> WARN/FAIL, WARN -> FAIL)
         or disappears
  WARN   a graded check's value moves the wrong way without changing status, or the build takes 1.5x as long
  PASS   otherwise
A check whose measurement the branch changes (charkit.history.STEPS) is `remeasured`, neither better nor worse.
The report (markdown and json) is written to charkit/out/gate/: the checks that changed, the tests, the trace diff.
"""
import glob, json, os, shlex, shutil, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
RANK = {'PASS': 0, 'WARN': 1, 'FAIL': 2}


def _git(*a, cwd=ROOT, check=True):
    r = subprocess.run(['git', *a], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise SystemExit('git %s: %s' % (' '.join(a), r.stderr.strip()))
    return r


def _link_inputs(wt):
    """the gitignored generated inputs a build reads (charkit/out/i3d), shared read-only from this worktree."""
    src = os.path.join(ROOT, 'charkit', 'out', 'i3d')
    dst = os.path.join(wt, 'charkit', 'out', 'i3d')
    if os.path.isdir(src) and not os.path.exists(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.symlink(src, dst)


def _tests(wt):
    res = {}
    for t in sorted(glob.glob(os.path.join(wt, 'charkit', 'tests', 'test_*.py'))):
        r = subprocess.run([PY, t], cwd=wt, capture_output=True, text=True)
        res[os.path.basename(t)] = 'ok' if r.returncode == 0 else (r.stdout + r.stderr)[-600:]
    return res


def _build(wt, spec, out, args):
    t = time.time()
    r = subprocess.run([PY, '-m', 'charkit', 'build', spec, '--out', out, '--boards', 'views', '--no-blend'] + args,
                       cwd=wt, capture_output=True, text=True)
    ok = r.returncode == 0 and os.path.exists(os.path.join(out, 'qa', 'qa.json'))
    return ok, round(time.time() - t, 1), (r.stdout + r.stderr)[-1500:]


def compare_qa(a, b, remeasured=None):
    """per check: baseline -> candidate, with a verdict (regressed, improved, value, new, gone, removed, ungraded;
    remeasured for a check in `remeasured`, whose measurement changed between the two builds: charkit.history.STEPS)."""
    import fnmatch
    ca, cb = a.get('checks', {}), b.get('checks', {})
    rows = []
    for k in sorted(set(ca) | set(cb)):
        x, y = ca.get(k), cb.get(k)
        sx, sy = (x or {}).get('status'), (y or {}).get('status')
        vx, vy = (x or {}).get('value'), (y or {}).get('value')
        if x == y:
            continue
        if x is None:
            v = 'new'
        elif y is None:
            v = 'gone' if sx in RANK else 'removed'
        elif remeasured and any(fnmatch.fnmatchcase(k, p) for p in remeasured) and (sx, vx) != (sy, vy):
            v = 'remeasured'
        elif sx in RANK and (sy not in RANK):
            v = 'gone' if y is None or sy in ('SKIPPED', None) else 'ungraded'
        elif sy in RANK and sx not in RANK:
            v = 'new'
        elif sx in RANK and sy in RANK and RANK[sy] > RANK[sx]:
            v = 'regressed'
        elif sx in RANK and sy in RANK and RANK[sy] < RANK[sx]:
            v = 'improved'
        elif vx != vy:
            v = 'value'
        else:
            continue
        rows.append({'check': k, 'base': [vx, sx], 'cand': [vy, sy], 'verdict': v})
    return rows


def gate(branch, into='HEAD', spec='charkit/spec/clawd.json', args=(), keep=False):
    head = _git('rev-parse', '--short', into).stdout.strip()
    tip = _git('rev-parse', '--short', branch).stdout.strip()
    tag = '%s_%s' % (branch.replace('/', '-'), tip)
    opts = '_'.join(a.strip('-') for a in args) or 'default'
    gdir = os.path.join(ROOT, 'charkit', 'out', 'gate')
    base_out = os.path.join(gdir, 'base_%s_%s_%s' % (head, os.path.basename(spec).split('.')[0], opts))
    cand_out = os.path.join(gdir, 'cand_%s_into_%s_%s' % (tag, head, opts))
    wt = tempfile.mkdtemp(prefix='charkit-gate-')
    os.rmdir(wt)
    rep = {'branch': branch, 'tip': tip, 'into': into, 'head': head, 'spec': spec, 'args': list(args),
           't': time.strftime('%Y-%m-%dT%H:%M:%S')}
    _git('worktree', 'add', '--detach', wt, head)
    try:
        _link_inputs(wt)
        # the baseline: cached per integration commit, spec and options
        if not os.path.exists(os.path.join(base_out, 'qa', 'qa.json')):
            ok, dt, log = _build(wt, spec, base_out, list(args))
            rep['base_build'] = {'ok': ok, 'seconds': dt}
            if not ok:
                rep['verdict'] = 'FAIL'; rep['why'] = 'the baseline build failed'; rep['log'] = log
                return _write(rep, gdir, tag)
        else:
            rep['base_build'] = {'ok': True, 'cached': True}
        m = _git('merge', '--no-commit', '--no-ff', branch, cwd=wt, check=False)
        if m.returncode:
            conf = _git('diff', '--name-only', '--diff-filter=U', cwd=wt, check=False).stdout.split()
            _git('merge', '--abort', cwd=wt, check=False)
            rep['verdict'] = 'FAIL'; rep['why'] = 'the merge conflicts'; rep['conflicts'] = conf
            return _write(rep, gdir, tag)
        rep['files'] = _git('diff', '--cached', '--stat', cwd=wt).stdout.strip().splitlines()[-1:]
        rep['tests'] = _tests(wt)
        ok, dt, log = _build(wt, spec, cand_out, list(args))
        rep['cand_build'] = {'ok': ok, 'seconds': dt}
        if not ok:
            rep['verdict'] = 'FAIL'; rep['why'] = 'the candidate build failed'; rep['log'] = log
            return _write(rep, gdir, tag)
        qa_a = json.load(open(os.path.join(base_out, 'qa', 'qa.json')))
        qa_b = json.load(open(os.path.join(cand_out, 'qa', 'qa.json')))
        from . import history
        rep['remeasured'] = history.steps_between(head, tip)          # measurement steps the branch brings
        rep['qa'] = compare_qa(qa_a, qa_b, rep['remeasured'])
        from . import trace
        rep['trace'] = trace.diff(trace.read(os.path.join(base_out, 'trace.jsonl')), trace.read(os.path.join(cand_out, 'trace.jsonl')))
        ta = next((r['total'] for r in trace.read(os.path.join(base_out, 'trace.jsonl')) if r['event'] == 'end'), None)
        tb = next((r['total'] for r in trace.read(os.path.join(cand_out, 'trace.jsonl')) if r['event'] == 'end'), None)
        rep['blender_seconds'] = [ta, tb]
        bad_tests = [k for k, v in rep['tests'].items() if v != 'ok']
        regressed = [r['check'] for r in rep['qa'] if r['verdict'] in ('regressed', 'gone')]
        if bad_tests or regressed:
            rep['verdict'] = 'FAIL'
            rep['why'] = '; '.join(filter(None, ['tests failing: ' + ', '.join(bad_tests) if bad_tests else '',
                                                 'checks worse: ' + ', '.join(regressed) if regressed else '']))
        else:
            worse = [r['check'] for r in rep['qa'] if r['verdict'] == 'value']
            slow = ta and tb and tb > 1.5 * ta
            rep['verdict'] = 'WARN' if slow else 'PASS'
            rep['why'] = 'the build is %.1fx slower' % (tb / ta) if slow else ''
            rep['values_moved'] = worse
        return _write(rep, gdir, tag)
    finally:
        _git('merge', '--abort', cwd=wt, check=False)
        if keep:
            print('kept', wt)
        else:
            _git('worktree', 'remove', '--force', wt, check=False)
            shutil.rmtree(wt, ignore_errors=True)


def _write(rep, gdir, tag):
    os.makedirs(gdir, exist_ok=True)
    base = os.path.join(gdir, 'gate_%s_into_%s' % (tag, rep['head']))
    json.dump(rep, open(base + '.json', 'w'), indent=1, default=str)
    L = ['# gate: %s (%s) into %s (%s): **%s**' % (rep['branch'], rep['tip'], rep['into'], rep['head'], rep['verdict'])]
    if rep.get('why'):
        L.append('\n' + rep['why'])
    if rep.get('conflicts'):
        L.append('\nConflicts: ' + ', '.join(rep['conflicts']))
    if rep.get('tests'):
        L.append('\nTests: ' + ', '.join('%s %s' % (k, 'ok' if v == 'ok' else 'FAILED') for k, v in rep['tests'].items()))
    if rep.get('qa') is not None:
        L.append('\n| check | base | candidate | verdict |\n| --- | --- | --- | --- |')
        order = {'regressed': 0, 'gone': 1, 'value': 2, 'new': 3, 'improved': 4, 'remeasured': 5, 'ungraded': 6, 'removed': 7}
        for r in sorted(rep['qa'], key=lambda r: order.get(r['verdict'], 9)):
            L.append('| %s | %s %s | %s %s | %s |' % (r['check'], str(r['base'][0])[:10], r['base'][1] or '',
                                                     str(r['cand'][0])[:10], r['cand'][1] or '', r['verdict']))
        if not rep['qa']:
            L.append('| (no check changed) | | | |')
    for k, why in (rep.get('remeasured') or {}).items():
        L.append('\nremeasured: %s: %s' % (k, why))
    if rep.get('blender_seconds'):
        L.append('\nBlender time: %s s -> %s s' % tuple(rep['blender_seconds']))
    if rep.get('trace'):
        L.append('\n```\n' + rep['trace'][:6000] + '\n```')
    if rep.get('log'):
        L.append('\n```\n' + rep['log'] + '\n```')
    open(base + '.md', 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L[:1] + ([L[1]] if rep.get('why') else [])))
    print('report', base + '.md')
    return rep


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    rep = gate(args[0], into=opt('--into', 'HEAD'), spec=opt('--spec', 'charkit/spec/clawd.json'),
               args=shlex.split(opt('--args', '')), keep='--keep' in args)
    raise SystemExit(0 if rep['verdict'] != 'FAIL' else 1)
