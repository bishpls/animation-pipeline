"""The merge gate: what a branch would do to the integration branch, measured before it lands. Nothing is merged and no
branch moves: a throwaway worktree at the integration head builds the baseline (cached per commit and build options),
takes the branch with `git merge --no-commit`, runs the tests, builds again, and the two builds' QA and traces are
compared.

    python -m charkit gate BRANCH [--into REF] [--spec SPEC] [--args "--base anime"] [--accept PATTERN,...] [--keep]

The worktree is a sparse checkout (charkit/sparse.py's charkit profile: the code, plus the paths the character's
manifest names): a few hundred MB instead of every film's assets. The gate refuses to start with under 5 GB free.

The verdict:
  FAIL   the merge conflicts, a test fails, a build fails, or a graded check gets worse (PASS -> WARN/FAIL, WARN -> FAIL)
         or disappears
  WARN   a graded check's value moves the wrong way without changing status, or the build takes 1.5x as long
  PASS   otherwise
A check whose measurement the branch changes (a measurement step it registers: charkit.history, charkit/steps/) is
`remeasured`, neither better nor worse. When the branch also changes the geometry, the gate scores it both ways (the
2x2, Michael's no-gaming rule): the baseline's QA code measures the candidate's geometry bundle (the old measure on the
new geometry) and the candidate's measures the baseline's (the new measure on the old geometry). A remeasured check that
gets worse under either measure alike (the old on both geometries, or the new on both) fails the gate, unless it's
accepted by name (--accept PATTERN[,PATTERN]).
The report (markdown and json) is written to charkit/out/gate/: the checks that changed, the 2x2, the tests, the trace
diff.
"""
import fnmatch, glob, json, os, shlex, shutil, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
RANK = {'PASS': 0, 'WARN': 1, 'FAIL': 2}


def _git(*a, cwd=ROOT, check=True):
    r = subprocess.run(['git', *a], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise SystemExit('git %s: %s' % (' '.join(a), r.stderr.strip()))
    return r


def _free_gb(path):
    return shutil.disk_usage(path).free / 2 ** 30


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


def _cpu_children():
    import resource
    u = resource.getrusage(resource.RUSAGE_CHILDREN)
    return u.ru_utime + u.ru_stime


def _build(wt, spec, out, args):
    """-> (ok, wall seconds, log tail). The build's CPU seconds (it and everything it waited for: Blender, the QA's
    venv) go to OUT/cpu_seconds.json: wall time moves with the box's load, and gates now run side by side."""
    t, c = time.time(), _cpu_children()
    r = subprocess.run([PY, '-m', 'charkit', 'build', spec, '--out', out, '--boards', 'views', '--no-blend'] + args,
                       cwd=wt, capture_output=True, text=True)
    ok = r.returncode == 0 and os.path.exists(os.path.join(out, 'qa', 'qa.json'))
    if ok:
        json.dump({'cpu_seconds': round(_cpu_children() - c, 1)}, open(os.path.join(out, 'cpu_seconds.json'), 'w'))
    return ok, round(time.time() - t, 1), (r.stdout + r.stderr)[-1500:]


def _cpu(out):
    p = os.path.join(out, 'cpu_seconds.json')
    return json.load(open(p))['cpu_seconds'] if os.path.exists(p) else None


def compare_qa(a, b, remeasured=None):
    """per check: baseline -> candidate, with a verdict (regressed, improved, value, new, gone, removed, ungraded;
    remeasured for a check in `remeasured`, whose measurement changed between the two builds: charkit.history.STEPS).
    A graded check that disappears is gone (the gate fails), unless a measurement step the branch brings covers it:
    then it was retired by that step (removed), as an ungraded one that disappears is."""
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
            stepped = remeasured and any(fnmatch.fnmatchcase(k, p) for p in remeasured)
            v = 'gone' if sx in RANK and not stepped else 'removed'
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


def cross_qa(tree, bundle_dir, out):
    """one tree's QA code on another build's geometry bundle (the 2x2's crossed cells): `python -m charkit qa` run in
    tree, its cache off (a part's cache key is its code, and a crossed run must not restore the other side's) -> the
    report (qa.json's) or {'error': why}."""
    os.makedirs(out, exist_ok=True)
    r = subprocess.run([PY, '-m', 'charkit', 'qa', bundle_dir, '--out', out, '--cache', 'off'], cwd=tree,
                       capture_output=True, text=True)
    p = os.path.join(out, 'qa.json')
    if r.returncode or not os.path.exists(p):
        return {'error': 'exit %d: %s' % (r.returncode, (r.stdout + r.stderr)[-800:])}
    q = json.load(open(p))
    # a tree whose QA draws with charkit.render, on a bundle whose build wrote no export for it (a baseline older than
    # the look export): every frame fell back to the numpy drawing, so this cell isn't that tree's measure
    d = (q.get('measured') or {}).get('draw') or {}
    fr = d.get('frames') or {}
    if d.get('setting') == 'render' and not fr.get('render') and any(k.startswith('numpy (') for k in fr):
        return {'error': "the render drawing fell back to numpy on every frame: %s" % ', '.join(sorted(fr))}
    return q


def twobytwo(base, cand, old_on_new, new_on_old, remeasured, accept=()):
    """the 2x2 for each remeasured check: its value and status in base (the old geometry, the old measure), old_on_new
    (the new geometry, the old measure), new_on_old (the old geometry, the new measure) and cand (the new geometry, the
    new measure) -> rows, each with `old` (the new geometry against the old under the old measure: regressed, improved,
    value, same, unmeasured) and `new` (the same under the new measure), and `accepted` (a pattern in accept covers it).
    A check the old measure doesn't have is new with its step: it has no old-measure row."""
    import fnmatch

    def cell(q, k):
        c = (q or {}).get('checks', {}).get(k)
        return [c.get('value'), c.get('status')] if c else None

    def verdict(a, b):
        if a is None or b is None:
            return 'unmeasured' if a is not None else None
        (va, sa), (vb, sb) = a, b
        if sa in RANK and sb in RANK and RANK[sb] != RANK[sa]:
            return 'regressed' if RANK[sb] > RANK[sa] else 'improved'
        if sa in RANK and sb not in RANK:
            return 'unmeasured'
        return 'value' if va != vb else 'same'
    names = set()
    for q in (base, cand, old_on_new, new_on_old):
        names |= set((q or {}).get('checks', {}))
    rows = []
    for k in sorted(names):
        if not any(fnmatch.fnmatchcase(k, p) for p in remeasured or {}):
            continue
        r = dict(check=k, base=cell(base, k), old_on_new=cell(old_on_new, k), new_on_old=cell(new_on_old, k),
                 cand=cell(cand, k))
        r['old'] = verdict(r['base'], r['old_on_new'])
        r['new'] = verdict(r['new_on_old'], r['cand'])
        r['accepted'] = any(fnmatch.fnmatchcase(k, p) for p in accept)
        if r['old'] is None and r['new'] is None:
            continue
        rows.append(r)
    return rows


def geometry(out):
    """a build's geometry, for the 2x2's "did the geometry change": its bundle's array hashes (charkit/bundle.py's
    bundle.json), not the bundle's content hash, which also covers the metadata (the resolved spec's absolute output
    paths, which differ between any two builds) -> (digest, {array: hash}) or (None, {})."""
    import hashlib
    p = os.path.join(out, 'bundle', 'bundle.json')
    if not os.path.exists(p):
        return None, {}
    h = json.load(open(p)).get('hashes') or {}
    return hashlib.sha1(json.dumps(sorted(h.items())).encode()).hexdigest()[:12], h


def twobytwo_drops(rows):
    """the 2x2's hidden regressions: a remeasured check that reads worse on the new geometry under either measure alike
    (the old on both geometries, or the new on both), not accepted -> [(check, [the measures it's worse under])]."""
    out = []
    for r in rows:
        worse = [m for m in ('old', 'new') if r.get(m) == 'regressed']
        if worse and not r.get('accepted'):
            out.append((r['check'], worse))
    return out


def gate(branch, into='HEAD', spec='charkit/spec/clawd.json', args=(), keep=False, accept=()):
    head = _git('rev-parse', '--short', into).stdout.strip()
    tip = _git('rev-parse', '--short', branch).stdout.strip()
    tag = '%s_%s' % (branch.replace('/', '-'), tip)
    opts = '_'.join(a.strip('-') for a in args) or 'default'
    gdir = os.path.join(ROOT, 'charkit', 'out', 'gate')
    stem = os.path.basename(spec).split('.')[0]
    # a spec other than the default is in the candidate's and report's names: gates of one commit on two specs ran one
    # after the other and the second overwrote the first's; run in parallel they would collide
    suffix = '' if stem == 'clawd' else '_' + stem
    base_out = os.path.join(gdir, 'base_%s_%s_%s' % (head, stem, opts))
    cand_out = os.path.join(gdir, 'cand_%s_into_%s%s_%s' % (tag, head, suffix, opts))
    wt = tempfile.mkdtemp(prefix='charkit-gate-')
    os.rmdir(wt)
    rep = {'branch': branch, 'tip': tip, 'into': into, 'head': head, 'spec': spec, 'args': list(args),
           'suffix': suffix, 't': time.strftime('%Y-%m-%dT%H:%M:%S'), 'accept': list(accept)}
    if _free_gb(os.path.dirname(wt)) < 5:
        raise SystemExit('gate: only %.1f GB free on disk; free some before gating' % _free_gb(os.path.dirname(wt)))
    _git('worktree', 'add', '--no-checkout', '--detach', wt, head)
    from . import sparse
    _git('sparse-checkout', 'set', '--cone', *sparse.dirs('charkit', spec), cwd=wt)
    _git('checkout', '--detach', head, cwd=wt)
    try:
        _link_inputs(wt)
        # the baseline: cached per integration commit, spec and options; built under its own lock, so gates running in
        # parallel into one commit build it once and the others wait for it and reuse it
        import fcntl
        os.makedirs(gdir, exist_ok=True)
        with open(base_out + '.lock', 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
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
        # the measurement steps the branch brings, as the merged tree registers them (this code's STEPS lacks the
        # branch's own)
        steps = history.load_steps(os.path.join(wt, 'charkit', 'history.py'))
        rep['remeasured'] = history.steps_between(head, tip, steps, repo=wt)
        rep['qa'] = compare_qa(qa_a, qa_b, rep['remeasured'])
        # the 2x2: a remeasured check on changed geometry scored under both measures. The candidate's code (the merged
        # tree, here now) measures the baseline's bundle; then, the merge undone, the baseline's measures the candidate's
        (ga, ha), (gb, hb) = geometry(base_out), geometry(cand_out)
        stepped = [k for k in set(qa_a.get('checks', {})) | set(qa_b.get('checks', {}))
                   if any(fnmatch.fnmatchcase(k, p) for p in rep["remeasured"])]
        if stepped and ga != gb:
            new_on_old = cross_qa(wt, os.path.join(base_out, 'bundle'), os.path.join(cand_out, 'x_new_measure_old_geometry'))
            _git('merge', '--abort', cwd=wt, check=False)
            old_on_new = cross_qa(wt, os.path.join(cand_out, 'bundle'), os.path.join(cand_out, 'x_old_measure_new_geometry'))
            errs = {k: q['error'] for k, q in (('new measure on the old geometry', new_on_old),
                                               ('old measure on the new geometry', old_on_new)) if 'error' in q}
            rep['twobytwo'] = {'rows': twobytwo(qa_a, qa_b, None if errs else old_on_new, None if errs else new_on_old,
                                                rep['remeasured'], accept), 'errors': errs,
                               'bundles': [ga, gb], 'arrays_changed': sum(ha.get(k) != hb.get(k) for k in set(ha) | set(hb))}
        elif stepped:
            rep['twobytwo'] = {'rows': [], 'errors': {}, 'bundles': [ga, gb], 'same_geometry': True}
        from . import trace
        rep['trace'] = trace.diff(trace.read(os.path.join(base_out, 'trace.jsonl')), trace.read(os.path.join(cand_out, 'trace.jsonl')))
        # (the last end: a build whose QA runs in the venv after Blender appends its own, with the whole build's time)
        ta = ([r['total'] for r in trace.read(os.path.join(base_out, 'trace.jsonl')) if r['event'] == 'end'] or [None])[-1]
        tb = ([r['total'] for r in trace.read(os.path.join(cand_out, 'trace.jsonl')) if r['event'] == 'end'] or [None])[-1]
        rep['blender_seconds'] = [ta, tb]
        bad_tests = [k for k, v in rep['tests'].items() if v != 'ok']
        regressed = [r['check'] for r in rep['qa'] if r['verdict'] in ('regressed', 'gone')]
        tb = rep.get('twobytwo') or {}
        hidden = ['%s (%s)' % (k, ', '.join('the %s measure' % m for m in ms)) for k, ms in twobytwo_drops(tb.get('rows', []))]
        if bad_tests or regressed or hidden:
            rep['verdict'] = 'FAIL'
            rep['why'] = '; '.join(filter(None, ['tests failing: ' + ', '.join(bad_tests) if bad_tests else '',
                                                 'checks worse: ' + ', '.join(regressed) if regressed else '',
                                                 'worse on the new geometry under one measure on both (a remeasure '
                                                 'step covered it; accept with --accept): ' + ', '.join(hidden)
                                                 if hidden else '']))
        else:
            worse = [r['check'] for r in rep['qa'] if r['verdict'] == 'value']
            # the slowness check is on CPU seconds, which the box's load barely moves; wall time only where a cached
            # baseline predates the CPU record
            ca, cb = _cpu(base_out), _cpu(cand_out)
            rep['cpu_seconds'] = [ca, cb]
            ra, rb = (ca, cb) if ca and cb else (ta, tb)
            slow = ra and rb and rb > 1.5 * ra
            unverified = sorted(tb.get('errors') or {})
            rep['verdict'] = 'WARN' if slow or unverified else 'PASS'
            rep['why'] = '; '.join(filter(None, [
                ('the build takes %.1fx the %s' % (rb / ra, 'CPU time' if ca and cb else 'time')) if slow else '',
                ('the 2x2 could not run (%s): the remeasured checks are unverified under the old measure'
                 % ', '.join(unverified)) if unverified else '']))
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
    base = os.path.join(gdir, 'gate_%s_into_%s%s' % (tag, rep['head'], rep.get('suffix', '')))
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
    tb = rep.get('twobytwo')
    if tb:
        L.append('\n**The 2x2** (remeasured checks; value status per cell; geometry %s -> %s, %s arrays changed):' % (
            tuple(str(g)[:12] for g in tb.get('bundles', [None, None])) + (tb.get('arrays_changed', '?'),)))
        if tb.get('same_geometry'):
            L.append('\nThe geometry is unchanged: the remeasured rows above are the measure alone.')
        for k, e in (tb.get('errors') or {}).items():
            L.append('\n%s: could not run: `%s`' % (k, e.strip().splitlines()[-1][:200] if e.strip() else e))
        if tb.get('rows'):
            cell = lambda c: '%s %s' % (str(c[0])[:10], c[1] or '') if c else '-'
            L.append('\n| check | old geometry, old measure | new geometry, old measure | old geometry, new measure | '
                     'new geometry, new measure (candidate) | under the old measure | under the new |\n'
                     '| --- | --- | --- | --- | --- | --- | --- |')
            mark = lambda r, m: ('**regressed**%s' % (' (accepted)' if r['accepted'] else '')) if r[m] == 'regressed' \
                else r[m] or '-'
            for r in sorted(tb['rows'], key=lambda r: ('regressed' not in (r['old'], r['new']), r['check'])):
                L.append('| %s | %s | %s | %s | %s | %s | %s |' % (
                    r['check'], cell(r['base']), cell(r['old_on_new']), cell(r['new_on_old']), cell(r['cand']),
                    mark(r, 'old'), mark(r, 'new')))
    if rep.get('blender_seconds'):
        L.append('\nBuild time (Blender and QA): %s s -> %s s' % tuple(rep['blender_seconds']))
    if rep.get('cpu_seconds') and all(rep['cpu_seconds']):
        L.append('\nBuild CPU time (all processes): %s s -> %s s' % tuple(rep['cpu_seconds']))
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
               args=shlex.split(opt('--args', '')), keep='--keep' in args,
               accept=[a for a in opt('--accept', '').split(',') if a])
    raise SystemExit(0 if rep['verdict'] != 'FAIL' else 1)
