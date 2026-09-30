"""The merge gate: what a branch would do to the integration branch, measured before it lands. Nothing is merged and no
branch moves: throwaway worktrees at the integration head take the baseline and, with `git merge --no-commit`, the
candidate; the tests run, each side is built when it has to be, and the two builds' QA and traces are compared.

    python -m charkit gate BRANCH [--into REF] [--spec SPEC] [--args "--base anime"] [--accept PATTERN,...] [--keep]
                                  [--build]
    python -m charkit gate --rejudge REPORT.json|PATTERN ... [--json]   # earlier reports read under policy K
    python -m charkit gate --carry BRANCH [--into pipeline-3d] [--spec SPEC] [--args ".."] [--no-tests] [--dry-run]
                                  [--json]
        # an earlier gate of BRANCH's tip carried to INTO's head without a build: the tests the move reaches rerun
        # here (exit 0 PASS, 1 FAIL, 3 not carried: gate it)

The worktrees are sparse checkouts (charkit/sparse.py's charkit profile: the code, plus the paths the character's
manifest names): a few hundred MB instead of every film's assets. The gate refuses to start with under 5 GB free.

No build when none can change anything (charkit/closure.py). A build run by the gate records its input closure: every
file under the worktree it read (the modules it imported or parsed, the spec, the references, the generated inputs by
sha256), in OUT/closure.json. The candidate isn't built when no change the merge makes reaches the baseline's closure:
its stage cache keys would equal the baseline's, so it would be the same build. Only the tests run, and the report
says so (--build builds anyway). The baseline itself is taken from an earlier baseline (another commit's, of the same
spec and options) when no change since that commit reaches its closure. When both sides must be built they build side
by side, each in its worktree, with the tests alongside (on a machine with 16 or more cores; CHARKIT_GATE_PARALLEL=0/1).
The builds skip the VRM export unless the branch changes its code (EXPORT_CODE: then the candidate exports and checks it).

The verdict: Michael's policy K (2026-09-30). The merge is blocked (FAIL) only by
  - the merge conflicting, a test failing, a build failing;
  - a new FAIL: a check that PASSed or WARNed on the baseline and FAILs on the candidate (a check the branch adds
    that FAILs is reported, not blocking: it measures a known fault, it doesn't make one);
  - a regression in a check built from Michael's flags (a check carrying `flag`: charkit.registry.FLAG): its status or
    its calibrated grade gets worse, or it disappears;
  - the build's CPU time over 1.5x the baseline's.
Everything else (a PASS going WARN, a value moving, a check going or new, the 2x2's drops short of those) is reported,
not enforced: the report's "Report" section and its summary (REPORT.summary.json: the verdict, what blocks, and each
reported move, for the integrator's morning report). PASS otherwise.
A check whose measurement the branch changes (a measurement step it registers: charkit.history, charkit/steps/) is
`remeasured`, neither better nor worse. When the branch also changes the geometry, the gate scores it both ways (the
2x2, Michael's no-gaming rule): the baseline's QA code measures the candidate's geometry bundle (the old measure on the
new geometry) and the candidate's measures the baseline's (the new measure on the old geometry). A remeasured check that
gets worse under either measure alike (the old on both geometries, or the new on both) blocks under K when it gets to
FAIL there or is a flag check, unless it's accepted by name (--accept PATTERN[,PATTERN]); otherwise it's reported.
The report (markdown, json, summary json) is written to charkit/out/gate/: what blocks, the report, the build decision,
the gate's phases (each with its start and length, the builds' own steps), the tests, the trace diff.
A gate's builds run with their thread pools capped (THREAD_VARS, _threads(): 4 on the 32-core box) and OpenMP's waits
passive: the same wall time, a third of the CPU, bit-identical outputs, and a CPU figure the box's load doesn't inflate.
"""
import concurrent.futures, contextlib, fnmatch, glob, json, os, shlex, shutil, signal, subprocess, sys, tempfile, \
    threading, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
RANK = {'PASS': 0, 'WARN': 1, 'FAIL': 2}
CPU_LIMIT = 1.5                     # policy K: the candidate's build CPU over this times the baseline's blocks
# the VRM export's code (build_blender's product('vrm', ..., [gltf.export_scene, gltf.check])): a gate's builds skip the
# export (no --vrm: about 80 s, most of it evaluating shape keys) unless the branch changes it; then the candidate builds
# with --vrm, and the export checks itself on the way out (a failed check fails the build)
EXPORT_CODE = ('charkit/gltf.py',)
# a gate build's thread pools (BLAS, OpenMP, numba), and its OpenMP threads sleep rather than spin while they wait.
# Measured on the build box under load (2026-09-30, one build of clawd.json each, side by side): 490 s wall and 1,313 s
# CPU uncapped, 485 s and 527 s capped at 4, the outputs bit-identical (733 arrays, 351 checks). Uncapped, the CPU
# a build burns spinning grows with the box's load (the same build measured 379 s and 1,291 s), which made policy K's
# CPU rule noise. CHARKIT_GATE_THREADS overrides (0: uncapped).
THREAD_VARS = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMBA_NUM_THREADS', 'BLIS_NUM_THREADS',
               'VECLIB_MAXIMUM_THREADS')


def _threads():
    v = os.environ.get('CHARKIT_GATE_THREADS')
    return int(v) if v else max(2, min(8, (os.cpu_count() or 4) // 8))


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


class Clock:
    """the gate's phases: each one's start (s since the gate began), length and a note; phases may overlap."""

    def __init__(self):
        self.t0, self.rows = time.time(), []

    @contextlib.contextmanager
    def __call__(self, name, note=''):
        r = {'phase': name, 'start': round(time.time() - self.t0, 1), 'seconds': None, 'note': note}
        self.rows.append(r)
        t = time.time()
        try:
            yield r
        finally:
            r['seconds'] = round(time.time() - t, 1)


def _test_jobs():
    v = os.environ.get('CHARKIT_GATE_TEST_JOBS')
    return int(v) if v else max(1, min(8, (os.cpu_count() or 2) // 4))


def _tests(wt, jobs=None, logs=None, only=None):
    """every charkit/tests/test_*.py (only: those names), JOBS at a time -> ({file: 'ok' or its output's tail}, {file:
    seconds}). logs: a folder; each test file's input closure is recorded there as NAME.log (CHARKIT_CLOSURE;
    charkit/closure.py), so a later target's changes can be tested against what each test read (`gate --carry`)."""
    files = sorted(t for t in glob.glob(os.path.join(wt, 'charkit', 'tests', 'test_*.py'))
                   if only is None or os.path.basename(t) in only)

    def one(t):
        t0 = time.time()
        env = dict(os.environ, CHARKIT_CLOSURE=os.path.join(logs, os.path.basename(t) + '.log')) if logs else None
        r = subprocess.run([PY, t], cwd=wt, capture_output=True, text=True, env=env)
        return os.path.basename(t), 'ok' if r.returncode == 0 else (r.stdout + r.stderr)[-600:], round(time.time() - t0, 1)
    with concurrent.futures.ThreadPoolExecutor(jobs or _test_jobs()) as ex:
        got = list(ex.map(one, files))
    return {n: v for n, v, _ in got}, {n: s for n, _, s in got}


def _cpu_children():
    import resource
    u = resource.getrusage(resource.RUSAGE_CHILDREN)
    return u.ru_utime + u.ru_stime


def _build(wt, spec, out, args, record=True, procs=None):
    """a build of the tree in wt into out -> {ok, seconds, cpu, log (its output's tail), steps ({step: seconds}: its
    CHARKIT_PHASE lines), cache (its CHARKIT_CACHE and CHARKIT_PRODUCED lines), killed}. Its CPU seconds (it and
    everything it waited for: Blender, the QA's venv; os.wait4, so the tests running beside it don't count) go to
    OUT/cpu_seconds.json: wall time moves with the box's load, and gates run side by side. record: its input closure to
    OUT/closure.json (charkit/closure.py). procs: a list the running build's Popen is added to (to stop it)."""
    from . import closure
    os.makedirs(out, exist_ok=True)
    log = os.path.join(out, 'closure.log')
    for f in (log, os.path.join(out, 'closure.json'), os.path.join(out, 'cpu_seconds.json')):
        if os.path.exists(f):
            os.remove(f)
    env = {k: v for k, v in os.environ.items() if k != 'CHARKIT_CLOSURE'}
    if record:
        env['CHARKIT_CLOSURE'] = log
    if _threads():
        env.update({k: str(_threads()) for k in THREAD_VARS}, OMP_WAIT_POLICY='PASSIVE')
    t = time.time()
    # (no boards: nothing the gate reads draws from them, and the box's toon boards took 16 s a build)
    p = subprocess.Popen([PY, '-m', 'charkit', 'build', spec, '--out', out, '--boards', '', '--no-blend'] + list(args),
                         cwd=wt, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env,
                         start_new_session=True)
    if procs is not None:
        procs.append(p)
    lines = list(p.stdout)
    _, status, ru = os.wait4(p.pid, 0)
    p.returncode = os.waitstatus_to_exitcode(status)
    cpu = round(ru.ru_utime + ru.ru_stime, 1)
    ok = p.returncode == 0 and os.path.exists(os.path.join(out, 'qa', 'qa.json'))
    steps = {}
    for l in lines:
        w = l.split()
        if len(w) == 3 and w[0] == 'CHARKIT_PHASE':
            try:
                steps[w[1]] = float(w[2])
            except ValueError:
                pass
    res = dict(ok=ok, seconds=round(time.time() - t, 1), cpu=cpu, steps=steps, killed=getattr(p, 'killed', False),
               threads=_threads() or None,
               cache=[l.strip()[:200] for l in lines if l.startswith(('CHARKIT_CACHE', 'CHARKIT_PRODUCED'))][:40],
               log=''.join(lines)[-1500:])
    if ok:
        json.dump({'cpu_seconds': cpu, 'threads': _threads() or None}, open(os.path.join(out, 'cpu_seconds.json'), 'w'))
        if record and os.path.exists(log):
            C = closure.summarise(log, wt)
            C['commit'] = _git('rev-parse', 'HEAD', cwd=wt).stdout.strip()
            json.dump(C, open(os.path.join(out, 'closure.json'), 'w'), indent=1)
    return res


def _stop(procs):
    """stop running builds (their process groups: the build, its Blender and QA)."""
    for p in procs or ():
        if p.poll() is None:
            p.killed = True
            try:
                os.killpg(p.pid, signal.SIGTERM)
            except OSError:
                pass


def _cpu(out, key='cpu_seconds'):
    """a build's CPU seconds (key 'threads': its thread cap, None uncapped or from before the caps)."""
    p = os.path.join(out, 'cpu_seconds.json')
    return json.load(open(p)).get(key) if os.path.exists(p) else None


def _closure_of(out):
    p = os.path.join(out, 'closure.json')
    return json.load(open(p)) if os.path.exists(p) else None


def build_steps(out, wall=None):
    """a build's time by part, from its trace: blender (the Blender stages and the bundle), qa (the venv's QA), and
    before (the venv's steps before Blender: resolve, the code head and body, the hair pieces, the garments; the rest of
    the wall time) -> dict."""
    from . import trace
    recs = trace.read(os.path.join(out, 'trace.jsonl')) if os.path.exists(os.path.join(out, 'trace.jsonl')) else []
    ends = [r['total'] for r in recs if r['event'] == 'end']
    out_ = {}
    if ends:
        out_['blender'] = round(ends[0], 1)
        out_['qa'] = round(ends[-1] - ends[0], 1)
        if wall:
            out_['before'] = round(wall - ends[-1], 1)
    for r in recs:
        if r['event'] == 'stage':
            out_['stage ' + r['name']] = round(r.get('dt', 0), 1)
    return out_


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


def _worktree(head, spec, label):
    """a sparse worktree at head, its generated inputs linked."""
    from . import sparse
    wt = tempfile.mkdtemp(prefix='charkit-gate-%s-' % label)
    os.rmdir(wt)
    _git('worktree', 'add', '--no-checkout', '--detach', wt, head)
    _git('sparse-checkout', 'set', '--cone', *sparse.dirs('charkit', spec), cwd=wt)
    _git('checkout', '--detach', head, cwd=wt)
    _link_inputs(wt)
    return wt


def _reference(gdir, stem, opts, head, wt):
    """an earlier baseline that stands for head's: the newest base_COMMIT_STEM_OPTS (a folder, not a link) with a closure
    that no change from COMMIT to head reaches -> (its folder, COMMIT, the changes) or None."""
    from . import closure
    suffix = '_%s_%s' % (stem, opts)
    cone = closure.cone(wt)
    dirs = [d for d in glob.glob(os.path.join(gdir, 'base_*' + suffix)) if os.path.isdir(d) and not os.path.islink(d)]
    for d in sorted(dirs, key=os.path.getmtime, reverse=True)[:12]:
        c = os.path.basename(d)[len('base_'):-len(suffix)]
        C = _closure_of(d)
        if c == head or C is None or not os.path.exists(os.path.join(d, 'qa', 'qa.json')):
            continue
        if _git('cat-file', '-e', c + '^{commit}', cwd=wt, check=False).returncode:
            continue
        ch = closure.changes(wt, c, head)
        if not closure.affected(C, ch, wt, cone, rev=c, new=head):
            return d, c, ch
    return None


def _link_base(ref, base_out):
    """base_out made a link to an equivalent baseline's folder (the next gate into this commit finds it cached)."""
    tmp = base_out + '.link-%d' % os.getpid()
    try:
        os.symlink(os.path.basename(ref), tmp)
        os.replace(tmp, base_out)
    except OSError:
        if os.path.lexists(tmp):
            os.remove(tmp)


def _newest_closure(gdir, stem, opts):
    """the newest baseline closure of this spec and options (any commit) -> (its folder, the closure) or (None, None):
    what a nearby build read, for the static no-build rule and for guessing whether a candidate will be needed."""
    suffix = '_%s_%s' % (stem, opts)
    for d in sorted(glob.glob(os.path.join(gdir, 'base_*' + suffix)), key=lambda d: os.path.getmtime(d)
                    if os.path.exists(d) else 0, reverse=True)[:6]:
        C = _closure_of(d) if os.path.isdir(d) else None
        if C:
            return d, C
    return None, None


_OLD_GIT = []


def _merge_tree(wt, a, b):
    """the tree `git merge` of b into a makes (a clean merge) -> its id, or None (a conflict, or a commit missing).
    `git merge-tree --write-tree` (git 2.38); an older git (the build box's 2.34) merges in a throwaway sparse worktree
    instead (a few seconds) and writes its index as a tree."""
    if not _OLD_GIT:
        r = _git('merge-tree', '--write-tree', a, b, cwd=wt, check=False)
        if r.returncode in (0, 1):
            return r.stdout.split()[0] if r.returncode == 0 and r.stdout.strip() else None
        if 'write-tree' not in r.stderr and 'usage' not in r.stderr:
            return None                                 # (a missing commit)
        _OLD_GIT.append(True)
    tmp = tempfile.mkdtemp(prefix='charkit-mergetree-')
    os.rmdir(tmp)
    try:
        if _git('worktree', 'add', '--no-checkout', '--detach', tmp, a, cwd=wt, check=False).returncode:
            return None
        _git('sparse-checkout', 'set', '--cone', 'charkit', cwd=tmp, check=False)
        _git('checkout', '--detach', a, cwd=tmp, check=False)
        m = subprocess.run(['git', '-c', 'user.name=gate', '-c', 'user.email=gate@localhost', 'merge', '--no-commit',
                            '--no-ff', b], cwd=tmp, capture_output=True, text=True)
        if m.returncode:
            return None
        r = _git('write-tree', cwd=tmp, check=False)
        return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None
    finally:
        _git('worktree', 'remove', '--force', tmp, cwd=wt, check=False)
        shutil.rmtree(tmp, ignore_errors=True)


def _cand_reference(gdir, tip, suffix, opts, head, wc):
    """an earlier candidate of this tip (any branch name), built into another commit H0, that stands for this one: no
    difference between its merged tree (tip into H0) and this merge (the index in wc) reaches its closure -> (its
    folder, H0, the changes) or None. This carries a gate over when the integration branch moves under it."""
    import re
    from . import closure
    pat = re.compile(r'cand_.+_%s_into_([0-9a-f]{7,40})%s_%s$' % (re.escape(tip), re.escape(suffix), re.escape(opts)))
    cone = closure.cone(wc)
    dirs = [d for d in glob.glob(os.path.join(gdir, 'cand_*_%s_into_*' % tip)) if os.path.isdir(d)
            and not os.path.islink(d) and pat.match(os.path.basename(d))]
    for d in sorted(dirs, key=os.path.getmtime, reverse=True)[:8]:
        h0 = pat.match(os.path.basename(d)).group(1)
        C = _closure_of(d)
        if h0 == head or C is None or not os.path.exists(os.path.join(d, 'qa', 'qa.json')):
            continue
        t0 = _merge_tree(wc, h0, tip)
        if t0 is None:
            continue
        ch = closure.changes(wc, t0)
        if not closure.affected(C, ch, wc, cone, rev=t0):
            return d, h0, ch
    return None


def gate(branch, into='HEAD', spec='charkit/spec/clawd.json', args=(), keep=False, accept=(), force_build=False,
         parallel=None):
    from . import closure, history, trace
    clock = Clock()
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
    if parallel is None:
        v = os.environ.get('CHARKIT_GATE_PARALLEL')
        parallel = (os.cpu_count() or 1) >= 16 if v is None else v != '0'
    rep = {'branch': branch, 'tip': tip, 'into': into, 'head': head, 'spec': spec, 'args': list(args),
           'suffix': suffix, 't': time.strftime('%Y-%m-%dT%H:%M:%S'), 'accept': list(accept), 'policy': 'K',
           'hard': [], 'phases': clock.rows, 'build': {}, 'parallel': parallel}
    if _free_gb(tempfile.gettempdir()) < 5:
        raise SystemExit('gate: only %.1f GB free on disk; free some before gating' % _free_gb(tempfile.gettempdir()))
    os.makedirs(gdir, exist_ok=True)
    wts, running = [], []
    ex = concurrent.futures.ThreadPoolExecutor(4)
    try:
        with clock('setup', 'the baseline and candidate worktrees at %s' % head):
            wb = _worktree(head, spec, 'base')
            wts.append(wb)
            wc = _worktree(head, spec, 'cand')
            wts.append(wc)
        with clock('merge'):
            m = _git('merge', '--no-commit', '--no-ff', branch, cwd=wc, check=False)
        if m.returncode:
            conf = _git('diff', '--name-only', '--diff-filter=U', cwd=wc, check=False).stdout.split()
            rep['conflicts'] = conf
            rep['hard'].append({'kind': 'the merge conflicts', 'files': conf})
            return _finish(rep, gdir, tag, clock)
        rep['files'] = _git('diff', '--cached', '--stat', cwd=wc).stdout.strip().splitlines()[-1:]
        changed = closure.changes(wc, head)
        rep['build']['changed_files'] = len(changed)
        export = sorted(p for _, p in changed if p in EXPORT_CODE)
        cand_args = list(args) + (['--vrm'] if export and '--vrm' not in args else [])
        rep['build']['vrm'] = bool(export)
        rep['closures'] = {}

        def tests():
            logs = tempfile.mkdtemp(prefix='charkit-gate-tests-')
            with clock('tests', '%d at a time' % _test_jobs()):
                r = _tests(wc, logs=logs)
            rep['closures']['tests'] = _tests_closures(logs, wc)
            shutil.rmtree(logs, ignore_errors=True)
            return r
        # no build at all when nothing the merge changes can reach one whatever its code (docs, tests): the baseline
        # isn't needed either (the smoke-docs gate into a fresh commit built both sides: 705 s for a one-line doc)
        near_d, near_C = _newest_closure(gdir, stem, opts)
        if not (force_build or export) and closure.unreadable(changed, near_C):
            rep['build'].update(candidate='skipped', static=True, why='nothing the merge changes can reach a build (%d '
                                'files, all docs or tests%s)' % (len(changed), ', none read by %s' % os.path.basename(
                                    near_d) if near_d else ''))
            rep['base_build'], rep['cand_build'] = {'ok': True, 'skipped': True}, {'ok': True, 'skipped': True}
            rep['qa'] = []
            return _finish(rep, gdir, tag, clock, tests_r=tests())
        # the candidate carried over from an earlier gate of this tip into another commit, when nothing between that
        # merge and this one reaches its closure (the integration branch moved under the branch)
        cref = None if (force_build or export) else _cand_reference(gdir, tip, suffix, opts, head, wc)
        if cref:
            _link_base(cref[0], cand_out)
            rep['build']['carried_from'] = os.path.basename(cref[0])

        def build(side, wt, out, **kw):
            with clock('%s build' % side) as ph:
                r = _build(wt, spec, out, cand_args if side == 'candidate' else args, procs=running, **kw)
                ph['note'] = 'CPU %s s%s' % (r['cpu'], ', stopped' if r['killed'] else '')
                return r
        # the tests: beside the builds on a machine with the cores for them, else first, on their own
        tests_f, tests_r = (ex.submit(tests), None) if parallel else (None, tests())
        # the baseline: cached per integration commit, spec and options, or an earlier one standing for it; built under
        # its own lock, so gates running in parallel into one commit build it once and the others wait and reuse it
        import fcntl
        lock = open(base_out + '.lock', 'w')

        def settle():
            """(the lock held) the baseline cached, or an earlier one standing for it -> base_build, or None: build it"""
            if os.path.exists(os.path.join(base_out, 'qa', 'qa.json')):
                return dict({'ok': True, 'cached': True}, **(
                    {'same_as': os.readlink(base_out)} if os.path.islink(base_out) else {}))
            ref = None if force_build else _reference(gdir, stem, opts, head, wc)
            if ref:
                _link_base(ref[0], base_out)
                return {'ok': True, 'cached': True, 'same_as': os.path.basename(ref[0]),
                        'why': 'no change since %s reaches its build (%d files changed)' % (ref[1], len(ref[2]))}
            return None

        def base_job(wait=False):
            """the baseline built (the lock held; released when done), or, after waiting for another gate building
            it (wait), taken from that one."""
            try:
                if wait:
                    with clock('baseline lock', 'another gate was building this baseline'):
                        fcntl.flock(lock, fcntl.LOCK_EX)
                    bb = settle()
                    if bb:
                        return dict(bb, waited=True)
                return build('baseline', wb, base_out)
            finally:
                lock.close()
        base_f = None
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            bb = settle()
            if bb:
                rep['base_build'] = bb
                lock.close()
            else:
                base_f = ex.submit(base_job)
        except BlockingIOError:
            # another gate into this commit is building the baseline: this one waits for it beside the candidate
            base_f = ex.submit(base_job, True)
        # the candidate: built unless the baseline's closure says nothing the merge changes reaches its build
        C = _closure_of(base_out) if base_f is None else None
        decide = lambda C: closure.affected(C, changed, wc, closure.cone(wc), rev=head)
        cand_f, why = None, None
        start_cand = lambda: None if cref else ex.submit(build, 'candidate', wc, cand_out, record=True)
        if force_build:
            why = '--build'
        elif export:
            why = 'the branch changes the VRM export (%s): the candidate builds with --vrm' % ', '.join(export)
        elif base_f is None and C is None:
            why = 'the baseline has no closure record (built before charkit/closure.py)'
        elif base_f is None:
            hits = decide(C)
            why = hits and 'the merge changes what the build reads: ' + ', '.join('%s (%s)' % h for h in hits[:8]) + (
                ' and %d more' % (len(hits) - 8) if len(hits) > 8 else '')
            rep['build']['affected'] = hits[:50]
        else:
            why = 'the baseline is being built (its closure decides afterwards)'
        # beside an unfinished baseline only when the candidate looks needed: the newest baseline's closure (a nearby
        # commit's) is reached by the merge; when it isn't, the baseline builds first and its own closure decides
        guess = near_C is not None and not closure.affected(near_C, changed, wc, closure.cone(wc), rev=head,
                                                            untracked=False)
        rep['build']['speculative'] = bool(why and base_f is not None and parallel and not guess and not cref)
        if why and (base_f is None or (parallel and not guess)):
            cand_f = start_cand()
        base_r = base_f.result() if base_f is not None else None
        if base_r is not None and base_r.get('cached'):
            rep['base_build'], base_r = base_r, None
            C = _closure_of(base_out)
            if not (force_build or export):
                if C is None:
                    why = 'the baseline has no closure record (built before charkit/closure.py)'
                else:
                    hits = decide(C)
                    rep['build']['affected'] = hits[:50]
                    why = hits and 'the merge changes what the build reads: ' + ', '.join('%s (%s)' % h for h in hits[:8])
                    if not hits and cand_f is not None and not cand_f.done():
                        _stop(running)
            if why and cand_f is None:
                cand_f = start_cand()
        if base_r is not None:
            rep['base_build'] = {k: base_r.get(k) for k in ('ok', 'seconds', 'cpu', 'steps', 'cache', 'threads')}
            rep['base_build']['parts'] = build_steps(base_out, base_r['seconds'])
            if not base_r['ok']:
                _stop(running)
                rep['hard'].append({'kind': 'the baseline build failed'})
                rep['log'] = base_r['log']
                return _finish(rep, gdir, tag, clock, tests_f, tests_r)
            C = _closure_of(base_out)
            if force_build or export:
                pass
            elif C is None:
                why = 'the baseline recorded no closure (its code predates charkit/closure.py)'
            else:
                hits = decide(C)
                rep['build']['affected'] = hits[:50]
                if not hits:
                    why = None
                    if cand_f is not None and not cand_f.done():
                        _stop(running)                 # the candidate can't differ: its build stops
                else:
                    why = 'the merge changes what the build reads: ' + ', '.join('%s (%s)' % h for h in hits[:8])
            if why and cand_f is None:
                cand_f = start_cand()
        cand_r = cand_f.result() if cand_f is not None else None
        if cand_r is not None and cand_r['killed'] and not why:
            cand_r = None                               # stopped: the baseline's closure showed it the same build
            rep['build']['stopped'] = True
        carried = bool(cref and why)
        rep['build']['candidate'] = 'built' if cand_r is not None else 'carried' if carried else 'skipped'
        rep['build']['why'] = why or 'nothing the merge changes reaches the baseline build (%d files changed, none among ' \
            'the %d it read, its scans or its data)' % (len(changed), len((C or {}).get('reads') or ()))
        if cand_r is not None:
            rep['cand_build'] = {k: cand_r.get(k) for k in ('ok', 'seconds', 'cpu', 'steps', 'cache', 'threads')}
            rep['cand_build']['parts'] = build_steps(cand_out, cand_r['seconds'])
            if not cand_r['ok']:
                rep['hard'].append({'kind': 'the candidate build failed'})
                rep['log'] = cand_r['log']
                return _finish(rep, gdir, tag, clock, tests_f, tests_r)
        elif carried:
            rep['cand_build'] = {'ok': True, 'cached': True, 'same_as': os.path.basename(cref[0]),
                                 'why': 'no difference between %s merged into %s and this merge reaches its build (%d '
                                        'files differ)' % (tip, cref[1], len(cref[2]))}
        else:
            rep['cand_build'] = {'ok': True, 'skipped': True}
        cand_q = cand_out if (cand_r is not None or carried) else base_out
        rep['closures'].update(base=closure.compact(_closure_of(base_out)), cand=closure.compact(_closure_of(cand_q)))
        with clock('compare'):
            qa_a = json.load(open(os.path.join(base_out, 'qa', 'qa.json')))
            qa_b = json.load(open(os.path.join(cand_q, 'qa', 'qa.json')))
            # the measurement steps the branch brings, as the merged tree registers them (this code's STEPS lacks the
            # branch's own)
            steps = history.load_steps(os.path.join(wc, 'charkit', 'history.py'))
            rep['remeasured'] = history.steps_between(head, tip, steps, repo=wc)
            rep['qa'] = compare_qa(qa_a, qa_b, rep['remeasured'])
        # the 2x2: a remeasured check on changed geometry scored under both measures: the candidate's code (the merged
        # worktree) measures the baseline's bundle, the baseline's measures the candidate's
        (ga, ha), (gb, hb) = geometry(base_out), geometry(cand_q)
        stepped = [k for k in set(qa_a.get('checks', {})) | set(qa_b.get('checks', {}))
                   if any(fnmatch.fnmatchcase(k, p) for p in rep["remeasured"])]
        if stepped and ga != gb:
            with clock('2x2', 'both QA codes on both bundles'):
                f1 = ex.submit(cross_qa, wc, os.path.join(base_out, 'bundle'), os.path.join(cand_out, 'x_new_measure_old_geometry'))
                f2 = ex.submit(cross_qa, wb, os.path.join(cand_out, 'bundle'), os.path.join(cand_out, 'x_old_measure_new_geometry'))
                new_on_old, old_on_new = f1.result(), f2.result()
            errs = {k: q['error'] for k, q in (('new measure on the old geometry', new_on_old),
                                               ('old measure on the new geometry', old_on_new)) if 'error' in q}
            rep['twobytwo'] = {'rows': twobytwo(qa_a, qa_b, None if errs else old_on_new, None if errs else new_on_old,
                                                rep['remeasured'], accept), 'errors': errs,
                               'bundles': [ga, gb], 'arrays_changed': sum(ha.get(k) != hb.get(k) for k in set(ha) | set(hb))}
        elif stepped:
            rep['twobytwo'] = {'rows': [], 'errors': {}, 'bundles': [ga, gb], 'same_geometry': True}
        if cand_q == cand_out:
            rep['trace'] = trace.diff(trace.read(os.path.join(base_out, 'trace.jsonl')),
                                      trace.read(os.path.join(cand_out, 'trace.jsonl')))
            # (the last end: a build whose QA runs in the venv after Blender appends its own, with the whole build's time)
            ends = [([r['total'] for r in trace.read(os.path.join(o, 'trace.jsonl')) if r['event'] == 'end'] or [None])[-1]
                    for o in (base_out, cand_out)]
            rep['blender_seconds'] = ends
            rep['cpu_seconds'] = [_cpu(base_out), _cpu(cand_out)]
            rep['cpu_threads'] = [_cpu(base_out, 'threads'), _cpu(cand_out, 'threads')]
        return _finish(rep, gdir, tag, clock, tests_f, tests_r, qa_a, qa_b)
    finally:
        _stop(running)
        ex.shutdown(wait=True)
        for wt in wts:
            if keep:
                print('kept', wt)
            else:
                _git('worktree', 'remove', '--force', wt, check=False)
                shutil.rmtree(wt, ignore_errors=True)


# ----------------------------------------------------------------------------------- carrying a verdict to a new target
def _tests_closures(logs, wt):
    """each test file's recorded closure, packed: {'paths': every tracked path read, 'files': {test: {'reads': indexes
    into paths, 'listed', 'scans'}}} (53 files read about 300 paths between them, most of them each)."""
    from . import closure
    per = {}
    for f in sorted(glob.glob(os.path.join(logs, 'test_*.py.log'))):
        per[os.path.basename(f)[:-len('.log')]] = closure.summarise(f, wt)
    paths = sorted({p for C in per.values() for p in C['reads']})
    ix = {p: i for i, p in enumerate(paths)}
    return {'paths': paths, 'files': {t: {'reads': [ix[p] for p in C['reads']], 'listed': C['listed'],
                                          'scans': C['scans']} for t, C in per.items()}}


def _tests_at(root, tree, head, tip, spec, names):
    """the named test files run in a throwaway sparse worktree of TREE (the merge of tip into head, as a commit object
    no ref points to) -> ({file: 'ok' or its tail}, {file: seconds})."""
    from . import sparse
    c = _git('-c', 'user.name=charkit-gate', '-c', 'user.email=gate@localhost', 'commit-tree', tree, '-p', head, '-p',
             tip, '-m', 'gate --carry: %s into %s' % (tip, head), cwd=root)       # (the box's git has no identity)
    wt = tempfile.mkdtemp(prefix='charkit-carry-')
    os.rmdir(wt)
    try:
        _git('worktree', 'add', '--no-checkout', '--detach', wt, c.stdout.strip(), cwd=root)
        try:
            _git('sparse-checkout', 'set', '--cone', *sparse.dirs('charkit', spec, root=root), cwd=wt)
        except (Exception, SystemExit):
            pass                                       # (no manifest: the whole tree)
        _git('checkout', '--detach', c.stdout.strip(), cwd=wt)
        _link_inputs(wt)
        return _tests(wt, jobs=min(4, _test_jobs()), only=set(names))
    finally:
        _git('worktree', 'remove', '--force', wt, cwd=root, check=False)
        shutil.rmtree(wt, ignore_errors=True)


def _test_closure(T, name):
    """one test file's closure from _tests_closures' packing."""
    f = T['files'][name]
    return dict(f, reads=[T['paths'][i] for i in f['reads']])


def _report_dirs():
    """where gate reports land: this worktree's charkit/out/gate, then every other worktree's of this repository (a
    `remote gate` pulls its report into the worktree that ran it)."""
    out = [os.path.join(ROOT, 'charkit', 'out', 'gate')]
    for l in _git('worktree', 'list', '--porcelain', check=False).stdout.splitlines():
        if l.startswith('worktree '):
            d = os.path.join(l[len('worktree '):], 'charkit', 'out', 'gate')
            if d not in out and os.path.isdir(d):
                out.append(d)
    return out


def carry(branch, into='pipeline-3d', spec='charkit/spec/clawd.json', args=(), write=True, reports=None, root=ROOT,
          run_tests=True):
    """the newest gate of the branch's tip (any branch name) into an ancestor H0 of INTO, carried over to INTO with no
    build and no box, when the verdict can't differ there (ROADMAP "Reuse a gate when pipeline-3d moves"):
      - the branch still merges into INTO cleanly (git merge-tree);
      - no change from H0 to INTO reaches the baseline's closure (so INTO's baseline is H0's build);
      - no difference between the two merged trees (the tip into H0, the tip into INTO) reaches the candidate's closure
        (so the candidate is the same build) or the tests' (so the tests read the same files; a test file added or
        deleted counts);
      - or, for a gate that built nothing because the branch changes only docs and tests, the merge into INTO still
        changes only those, and the tests' closure is untouched.
    The report's json holds the three closures (reports from before this can't carry). -> dict: carried (bool),
    verdict (the old one, when carried), why, from (the report), hits ({baseline, candidate, tests: [(path, why)]}),
    report (the new report's .md, written as gate_TAG_into_HEAD when write)."""
    import re
    from . import closure, sparse
    head = _git('rev-parse', '--short', into, cwd=root).stdout.strip()
    tip = _git('rev-parse', '--short', branch, cwd=root).stdout.strip()
    stem = os.path.basename(spec).split('.')[0]
    suffix = '' if stem == 'clawd' else '_' + stem
    # a report of this tip under any branch name, or of this branch at an earlier tip (an ancestor: notes committed
    # after the gate are the common case; what those commits change is in the merged trees' difference below)
    pat = re.compile(r'gate_(.+)_([0-9a-f]{7,40})_into_([0-9a-f]{7,40})%s\.json$' % re.escape(suffix))
    found, anc = [], {}
    for d in ([reports] if isinstance(reports, str) else reports or _report_dirs()):
        for p in glob.glob(os.path.join(d, 'gate_*_into_*.json')):
            m = pat.search(os.path.basename(p))
            if not m or m.group(1) != branch.replace('/', '-') and m.group(2) != tip:
                continue
            t0 = m.group(2)
            if t0 != tip and t0 not in anc:
                anc[t0] = not _git('merge-base', '--is-ancestor', t0, tip, cwd=root, check=False).returncode
            if t0 != tip and not anc[t0]:
                continue
            try:
                r = json.load(open(p))
            except ValueError:
                continue
            if r.get('spec') == spec and list(r.get('args') or ()) == list(args) and r.get('tip') == t0:
                found.append((r.get('t') or '', p, r))
    res = dict(branch=branch, tip=tip, into=into, head=head, carried=False, verdict=None, why=None, report=None)
    if not found:
        res['why'] = 'no gate report of %s (%s) with this spec and options in %s' % (branch, tip, ', '.join(
            _report_dirs() if reports is None else [str(reports)]))
        return res
    t1 = _merge_tree(root, head, tip)
    if t1 is None:
        res['why'] = 'the branch no longer merges into %s cleanly (or a commit is missing here)' % head
        return res
    try:
        cone = sparse.dirs('charkit', spec, root=root)
    except Exception:                               # (no manifest to read: the whole checkout counts)
        cone = None
    reasons = []
    for _, p, old in sorted(found, key=lambda x: x[0], reverse=True):
        h0, tip0, name = old['head'], old['tip'], os.path.basename(p)
        if h0 == head and tip0 == tip:
            res.update(carried=True, verdict=old['verdict'], why='already gated into %s' % head, report=p[:-5] + '.md',
                       **{'from': name})
            return res
        if old.get('conflicts') or not old.get('tests'):
            reasons.append('%s: the gate stopped before its tests' % name)
            continue
        if _git('merge-base', '--is-ancestor', h0, head, cwd=root, check=False).returncode:
            reasons.append('%s: %s is not an ancestor of %s' % (name, h0, head))
            continue
        t0 = _merge_tree(root, h0, tip0)
        Cs = old.get('closures') or {}
        if t0 is None or 'tests' not in Cs:
            reasons.append('%s: %s' % (name, 'its merge tree is missing here' if t0 is None else
                                       'it holds no closures (a gate from before carrying)'))
            continue
        moved, diff = closure.changes(root, h0, head), closure.changes(root, t0, t1)
        T = Cs['tests'] if 'files' in (Cs['tests'] or {}) else {'paths': [], 'files': {}}
        # the tests a difference reaches (each file's own closure), and the test files added: these run again
        rerun = {os.path.basename(p_): [(p_, 'a test file added')] for st, p_ in diff
                 if st == 'A' and p_.startswith('charkit/tests/test_') and p_.endswith('.py')}
        for t in sorted(T['files']):
            h = closure.affected(_test_closure(T, t), diff, root, cone, rev=t0, new=t1, untracked=False)
            if h and ('charkit/tests/' + t) not in {p_ for st, p_ in diff if st == 'D'}:
                rerun[t] = h
        hits = {}
        if (old.get('build') or {}).get('static'):
            mine = closure.changes(root, head, t1)
            hits['candidate'] = [] if closure.unreadable(mine) else [
                (p_, 'the merge now changes more than docs and tests') for _, p_ in mine[:8]]
        elif Cs.get('base') and Cs.get('cand'):
            hits['baseline'] = closure.affected(Cs['base'], moved, root, cone, rev=h0, new=head, untracked=False)
            hits['candidate'] = closure.affected(Cs['cand'], diff, root, cone, rev=t0, new=t1, untracked=False)
        else:
            reasons.append('%s: its builds recorded no closure' % name)
            continue
        if any(hits.values()):
            res.setdefault('hits', {k: v[:20] for k, v in hits.items() if v})
            res.setdefault('from', name)
            reasons.append('%s (into %s): %s' % (name, h0, '; '.join('%s reads %s' % (k, ', '.join(
                '%s (%s)' % h for h in v[:4]) + (' and %d more' % (len(v) - 4) if len(v) > 4 else ''))
                for k, v in hits.items() if v)))
            continue
        why = '%s moved %d files since %s%s and the merged trees differ in %d; none reaches the baseline or the ' \
              'candidate build' % (into, len(moved), h0, '' if tip0 == tip else ' (and the branch since %s: %d files)'
                                   % (tip0, len(closure.changes(root, tip0, tip))), len(diff))
        tests = dict(old.get('tests') or {})
        res.update(rerun={t: h[:4] for t, h in rerun.items()})
        if rerun and not run_tests:
            res.update(why=why + '; the tests %s read what moved: run them (or drop --no-tests)' % ', '.join(sorted(rerun)),
                       **{'from': name})
            return res
        if rerun:
            t_start = time.time()
            got, secs = _tests_at(root, t1, head, tip, spec, sorted(rerun))
            tests.update(got)
            res['tests_run'] = {'files': sorted(got), 'seconds': round(time.time() - t_start, 1),
                                'failed': sorted(k for k, v in got.items() if v != 'ok')}
            why += '; %d test file%s the move reaches ran again here (%s): %s' % (
                len(got), 's' * (len(got) != 1), ', '.join(sorted(got)), 'all ok' if not res['tests_run']['failed'] else
                'FAILING: ' + ', '.join(res['tests_run']['failed']))
        else:
            why += ', nor any test'
        verdict = old['verdict'] if not (res.get('tests_run') or {}).get('failed') else 'FAIL'
        res.update(carried=True, verdict=verdict, why=why, hits={}, **{'from': name})
        if write:
            new = dict(old, into=into, head=head, tip=tip, t=time.strftime('%Y-%m-%dT%H:%M:%S'), phases=[],
                       seconds=None, tests=tests,
                       carried={'report': name, 'from_head': h0, 'from_tip': tip0, 'why': why, 'moved': len(moved),
                                             'differ': len(diff), 'tests_run': res.get('tests_run')})
            if (res.get('tests_run') or {}).get('failed'):
                bad = {'kind': 'tests failing', 'files': res['tests_run']['failed']}
                new.update(hard=list(new.get('hard') or ()) + [bad], blocking=list(new.get('blocking') or ()) + [bad],
                           verdict='FAIL')
                new['why'] = '; '.join(_why(b) for b in new['blocking'])
            new.pop('summary', None)
            tag = '%s_%s' % (old['branch'].replace('/', '-'), tip)
            res['report'] = _write(new, os.path.join(root, 'charkit', 'out', 'gate'), tag)['summary']['md']
        return res
    res['why'] = 'not carried: ' + ' | '.join(reasons[:4])
    return res


def _finish(rep, gdir, tag, clock, tests_f=None, tests_r=None, qa_a=None, qa_b=None):
    """the tests' results in, the verdict under K, the report written -> rep."""
    if tests_f is not None:
        tests_r = tests_f.result()
    if tests_r is not None:
        rep['tests'], rep['test_seconds'] = tests_r
        bad = [k for k, v in rep['tests'].items() if v != 'ok']
        if bad:
            rep['hard'].append({'kind': 'tests failing', 'files': bad})
    rep['verdict'], rep['blocking'], rep['report'] = judge(rep, qa_a, qa_b)
    rep['verdict_pre_k'] = verdict_pre_k(rep)
    rep['why'] = '; '.join(_why(b) for b in rep['blocking'])
    rep['seconds'] = round(time.time() - clock.t0, 1)
    return _write(rep, gdir, tag)


# ------------------------------------------------------------------------------------------------ the verdict: policy K
def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _delta(vx, vy):
    if not (_num(vx) and _num(vy)):
        return {}
    d = vy - vx
    return {'delta': round(d, 6), 'rel': round(d / abs(vx), 4) if vx else None}


def judge(rep, qa_a, qa_b):
    """Michael's policy K on a gate's comparison -> (verdict, blocking, report). Blocking: rep['hard'] (the merge
    conflicting, a test failing, a build failing); a new FAIL (a check PASSing or WARNing on the baseline and FAILing
    on the candidate; a remeasured check is judged by its 2x2 instead); a flag check (charkit.registry.is_flag, on either
    side's qa.json) whose status or calibrated grade gets worse, or which goes; the 2x2's drops that end at FAIL under
    that measure or are flag checks (not --accept'ed); the build's CPU over CPU_LIMIT x. The report: everything else,
    by kind (warn: a check PASS -> WARN; new_failing: checks the branch adds that FAIL; flag_values and values: value
    moves, the biggest first; gone; new; improved; removed; remeasured; twobytwo; notes)."""
    from . import registry
    ca, cb = (qa_a or {}).get('checks', {}), (qa_b or {}).get('checks', {})
    is_flag = lambda k: registry.is_flag(ca.get(k)) or registry.is_flag(cb.get(k))
    block = [dict(h) for h in rep.get('hard') or ()]
    R = {k: [] for k in ('warn', 'new_failing', 'flag_values', 'values', 'gone', 'new', 'improved', 'removed',
                         'remeasured', 'twobytwo', 'notes')}
    for r in rep.get('qa') or ():
        k, v = r['check'], r['verdict']
        (vx, sx), (vy, sy) = r['base'], r['cand']
        gx, gy = (ca.get(k) or {}).get('grade'), (cb.get(k) or {}).get('grade')
        row = dict(check=k, base=[vx, sx], cand=[vy, sy], verdict=v, **_delta(vx, vy))
        if gx is not None or gy is not None:
            row['grade'] = [gx, gy]
        fl = is_flag(k)
        if fl:
            row['flag'] = (cb.get(k) or ca.get(k) or {}).get(registry.FLAG)
        if v == 'remeasured':
            R['remeasured'].append(row)
        elif sy == 'FAIL' and sx in ('PASS', 'WARN'):
            block.append(dict(row, kind='new FAIL'))
        elif fl and (v in ('regressed', 'gone', 'ungraded') or (gx in RANK and gy in RANK and RANK[gy] > RANK[gx])):
            block.append(dict(row, kind='flag check regressed'))
        else:
            R['new_failing' if v == 'new' and sy == 'FAIL' else {
                'regressed': 'warn', 'gone': 'gone', 'ungraded': 'gone', 'new': 'new', 'improved': 'improved',
                'removed': 'removed', 'value': 'flag_values' if fl else 'values'}.get(v, 'values')].append(row)
    for b in ('flag_values', 'values'):
        R[b].sort(key=lambda x: -abs(x.get('rel') or 0) if x.get('rel') is not None else -abs(x.get('delta') or 0))
    tb = rep.get('twobytwo') or {}
    for r in tb.get('rows') or ():
        worse = [m for m in ('old', 'new') if r.get(m) == 'regressed']
        if not worse:
            continue
        after = {'old': (r.get('old_on_new') or [None, None])[1], 'new': (r.get('cand') or [None, None])[1]}
        m0 = worse[0]                                   # the cells it's worse between, under that measure
        row = dict(check=r['check'], measures=worse, base=r.get('base'), old_on_new=r.get('old_on_new'),
                   new_on_old=r.get('new_on_old'), cand=r.get('cand'),
                   **{'from': r.get('base' if m0 == 'old' else 'new_on_old'),
                      'to': r.get('old_on_new' if m0 == 'old' else 'cand')})
        if r.get('accepted'):
            R['twobytwo'].append(dict(row, note='accepted (--accept)'))
        elif any(after[m] == 'FAIL' for m in worse):
            block.append(dict(row, kind='new FAIL under one measure on both geometries (the 2x2)'))
        elif is_flag(r['check']):
            block.append(dict(row, kind='flag check worse under one measure on both geometries (the 2x2)'))
        else:
            R['twobytwo'].append(row)
    for k in sorted(tb.get('errors') or {}):
        R['notes'].append('the 2x2 could not run the %s: its remeasured checks are unverified there' % k)
    ca_, cb_ = (rep.get('cpu_seconds') or [None, None])[:2]
    ta, tb_ = (rep.get('cpu_threads') or [None, None])[:2]
    if ca_ and cb_:
        rep['cpu_ratio'] = round(cb_ / ca_, 2)
        if ta != tb_:
            R['notes'].append('build CPU %.2fx (%s -> %s s) not judged: the builds ran with different thread caps (%s -> '
                              '%s), and an uncapped build burns CPU spinning as the box gets busier' % (
                                  rep['cpu_ratio'], ca_, cb_, ta or 'uncapped', tb_ or 'uncapped'))
        elif cb_ > CPU_LIMIT * ca_:
            block.append({'kind': 'build CPU', 'base': ca_, 'cand': cb_, 'ratio': rep['cpu_ratio']})
    elif (rep.get('cand_build') or {}).get('skipped'):
        rep['cpu_ratio'] = None
    elif rep.get('qa') is not None:
        R['notes'].append('build CPU not compared (a baseline from before the CPU record)')
    return ('FAIL' if block else 'PASS'), block, R


def verdict_pre_k(rep):
    """the verdict the gate gave before policy K (FAIL on any check worse or gone and the 2x2's drops, WARN on 1.5x the
    build's time or an unverified 2x2), for comparison while the integrator moves to K."""
    if rep.get('hard'):
        return 'FAIL'
    tb = rep.get('twobytwo') or {}
    if any(r['verdict'] in ('regressed', 'gone') for r in rep.get('qa') or ()) or twobytwo_drops(tb.get('rows') or ()):
        return 'FAIL'
    ra, rb = (rep.get('cpu_seconds') or [None, None])[:2]
    if not (ra and rb):
        ra, rb = (rep.get('blender_seconds') or [None, None])[:2]
    return 'WARN' if (ra and rb and rb > 1.5 * ra) or tb.get('errors') else 'PASS'


def _why(b):
    k = b.get('kind')
    if 'check' in b:
        a, z = (b['from'], b['to']) if 'from' in b else (b.get('base'), b.get('cand'))
        return '%s: %s %s -> %s' % (k, b['check'], _cell(a), _cell(z))
    if k == 'build CPU':
        return 'the build takes %.2fx the CPU time (%s -> %s s)' % (b['ratio'], b['base'], b['cand'])
    if b.get('files'):
        return '%s: %s' % (k, ', '.join(b['files'][:12]))
    return k


def _cell(c):
    if not c:
        return '-'
    v, s = c
    return ('%s %s' % (str(round(v, 4) if _num(v) else v)[:12], s or '')).strip()


def summary(rep, md=None):
    """the machine-readable summary (REPORT.summary.json): the verdict under K, what blocks, the report by kind."""
    t = rep.get('tests') or {}
    return dict(branch=rep['branch'], tip=rep['tip'], into=rep['into'], head=rep['head'], spec=rep['spec'],
                t=rep['t'], policy='K', verdict=rep['verdict'], verdict_pre_k=rep.get('verdict_pre_k'),
                why=rep.get('why'), blocking=rep.get('blocking') or [],
                report={k: v for k, v in (rep.get('report') or {}).items() if v},
                counts={k: len(v) for k, v in (rep.get('report') or {}).items() if v},
                build=dict(rep.get('build') or {}, base=_brief(rep.get('base_build')), cand=_brief(rep.get('cand_build'))),
                cpu_seconds=rep.get('cpu_seconds'), cpu_ratio=rep.get('cpu_ratio'),
                tests=dict(n=len(t), failed=sorted(k for k, v in t.items() if v != 'ok'),
                           seconds=round(sum((rep.get('test_seconds') or {}).values()), 1)),
                phases=rep.get('phases'), seconds=rep.get('seconds'), carried=rep.get('carried'), md=md)


def _brief(b):
    return {k: v for k, v in (b or {}).items() if k in ('ok', 'cached', 'same_as', 'why', 'skipped', 'seconds', 'cpu',
                                                      'parts', 'steps')}


def rejudge(path):
    """an earlier gate report (its json) read under policy K: the check rows it holds, the flags from the two builds'
    qa.json beside it (when the builds are still there), the CPU from their records -> dict."""
    rep = json.load(open(path))
    d = os.path.dirname(os.path.abspath(path))
    opts = '_'.join(a.strip('-') for a in rep.get('args') or ()) or 'default'
    stem = os.path.basename(rep.get('spec') or 'clawd').split('.')[0]
    tag = '%s_%s' % (rep['branch'].replace('/', '-'), rep['tip'])
    base = os.path.join(d, 'base_%s_%s_%s' % (rep['head'], stem, opts))
    cand = os.path.join(d, 'cand_%s_into_%s%s_%s' % (tag, rep['head'], rep.get('suffix', ''), opts))
    qa = lambda o: json.load(open(os.path.join(o, 'qa', 'qa.json'))) if os.path.exists(os.path.join(o, 'qa', 'qa.json')) \
        else None
    qa_a, qa_b = qa(base), qa(cand)
    hard = list(rep.get('hard') or ())
    if not hard:
        if rep.get('conflicts'):
            hard.append({'kind': 'the merge conflicts', 'files': rep['conflicts']})
        bad = [k for k, v in (rep.get('tests') or {}).items() if v != 'ok']
        if bad:
            hard.append({'kind': 'tests failing', 'files': bad})
        for side in ('base', 'cand'):
            if (rep.get(side + '_build') or {}).get('ok') is False:
                hard.append({'kind': 'the %s build failed' % side})
    old = dict(rep, hard=hard)
    if not all(old.get('cpu_seconds') or [None]):
        old['cpu_seconds'] = [_cpu(base), _cpu(cand)]
    v, block, R = judge(old, qa_a, qa_b)
    return dict(report=path, branch=rep['branch'], tip=rep['tip'], head=rep['head'], verdict_then=rep['verdict'],
                verdict_k=v, why_k='; '.join(_why(b) for b in block), blocking=block,
                counts={k: len(x) for k, x in R.items() if x}, flags_read=qa_a is not None and qa_b is not None,
                cpu_ratio=old.get('cpu_ratio'))


# ------------------------------------------------------------------------------------------------------------ the report
def _table(rows, cols):
    L = ['| %s |' % ' | '.join(c for c, _ in cols), '|' + ' --- |' * len(cols)]
    for r in rows:
        L.append('| %s |' % ' | '.join(str(f(r)) for _, f in cols))
    return L


def _write(rep, gdir, tag):
    os.makedirs(gdir, exist_ok=True)
    base = os.path.join(gdir, 'gate_%s_into_%s%s' % (tag, rep['head'], rep.get('suffix', '')))
    rep['summary'] = summary(rep, base + '.md')
    json.dump(rep, open(base + '.json', 'w'), indent=1, default=str)
    json.dump(rep['summary'], open(base + '.summary.json', 'w'), indent=1, default=str)
    B, R = rep.get('build') or {}, rep.get('report') or {}
    n_rep = sum(len(v) for v in R.values())
    L = ['# gate: %s (%s) into %s (%s): **%s**' % (rep['branch'], rep['tip'], rep['into'], rep['head'], rep['verdict'])]
    line = 'Policy K. %s. %d item%s reported.' % (
        'Nothing blocks' if not rep['blocking'] else '%d thing%s block%s' % (
            len(rep['blocking']), 's' * (len(rep['blocking']) != 1), 's' * (len(rep['blocking']) == 1)),
        n_rep, 's' * (n_rep != 1))
    if B.get('candidate') == 'skipped':
        line += ' **No candidate build:** %s.' % B.get('why')
    elif B.get('candidate') == 'carried':
        line += ' **The candidate carried over** from %s.' % B.get('carried_from')
    if rep.get('carried'):
        line += ' **Carried over** from %s: %s.' % (rep['carried'].get('report'), rep['carried'].get('why'))
    if rep.get('verdict_pre_k') and rep['verdict_pre_k'] != rep['verdict']:
        line += ' (Before K: %s.)' % rep['verdict_pre_k']
    L.append('\n' + line)
    if rep.get('why'):
        L.append('\n' + rep['why'])
    L.append('\n## Blocking (policy K)\n')
    if rep['blocking']:
        for b in rep['blocking']:
            L.append('- ' + _why(b) + (' (flag: %s)' % b['flag'] if b.get('flag') else ''))
    else:
        L.append('Nothing: no new FAIL, no flag-check regression, build CPU within %.1fx.' % CPU_LIMIT)
    L.append('\n## Report (not blocking)\n')
    cell = lambda k: (lambda r: _cell(r.get(k)))
    num = lambda k, f='%+.4g': (lambda r: (f % r[k]) if r.get(k) is not None else '')
    for key, title in (('warn', 'Checks going PASS -> WARN'), ('new_failing', 'New checks that FAIL (the branch adds '
                                                                               'them)'), ('flag_values', "Flag checks' values moved (status and "
                                                                                      'grade unchanged)'),
                       ('values', 'Values moved (status unchanged), the biggest first'), ('gone', 'Checks gone or ungraded'),
                       ('new', 'New checks'), ('improved', 'Improved'), ('removed', 'Retired by a measurement step'),
                       ('remeasured', 'Remeasured'), ('twobytwo', "The 2x2's drops (not blocking)")):
        rows = R.get(key) or []
        if not rows:
            continue
        L.append('**%s** (%d):\n' % (title, len(rows)))
        if key == 'twobytwo':
            L += _table(rows, [('check', lambda r: r['check']), ('worse under', lambda r: ', '.join(r['measures'])),
                               ('old geometry, old measure', cell('base')), ('new geometry, old measure', cell('old_on_new')),
                               ('old geometry, new measure', cell('new_on_old')), ('candidate', cell('cand')),
                               ('note', lambda r: r.get('note', ''))])
        else:
            rel = lambda r: '%+.1f%%' % (100 * r['rel']) if r.get('rel') is not None else ''
            L += _table(rows[:60], [('check', lambda r: r['check']), ('base', cell('base')), ('candidate', cell('cand')),
                                    ('change', num('delta')), ('relative', rel),
                                    ('grade', lambda r: '%s -> %s' % tuple(r['grade']) if r.get('grade') else '')])
            if len(rows) > 60:
                L.append('\n(%d more in the json)' % (len(rows) - 60))
        L.append('')
    for n in R.get('notes') or ():
        L.append('- ' + n)
    if not n_rep:
        L.append('Nothing to report.')
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
            c2 = lambda c: '%s %s' % (str(c[0])[:10], c[1] or '') if c else '-'
            L.append('\n| check | old geometry, old measure | new geometry, old measure | old geometry, new measure | '
                     'new geometry, new measure (candidate) | under the old measure | under the new |\n'
                     '| --- | --- | --- | --- | --- | --- | --- |')
            mark = lambda r, m: ('**regressed**%s' % (' (accepted)' if r['accepted'] else '')) if r[m] == 'regressed' \
                else r[m] or '-'
            for r in sorted(tb['rows'], key=lambda r: ('regressed' not in (r['old'], r['new']), r['check'])):
                L.append('| %s | %s | %s | %s | %s | %s | %s |' % (
                    r['check'], c2(r['base']), c2(r['old_on_new']), c2(r['new_on_old']), c2(r['cand']),
                    mark(r, 'old'), mark(r, 'new')))
    L.append('\n## Build\n')
    bb, cb = rep.get('base_build') or {}, rep.get('cand_build') or {}
    L.append('- baseline: %s' % ('same as %s (%s)' % (bb['same_as'], bb.get('why') or 'linked') if bb.get('same_as') else
                                 'cached' if bb.get('cached') else 'not built' if bb.get('skipped') else
                                 'built, %s s wall, %s s CPU' % (bb.get('seconds'), bb.get('cpu'))))
    L.append('- candidate: %s' % ('**not built**: ' + B.get('why', '') if cb.get('skipped') else
                                  '**carried over**: the build of %s (%s)' % (cb['same_as'], cb.get('why')) if
                                  cb.get('same_as') else
                                  'built, %s s wall, %s s CPU: %s' % (cb.get('seconds'), cb.get('cpu'), B.get('why', ''))))
    if B.get('speculative'):
        L.append('- the candidate was started beside the baseline (the newest baseline closure said it would be needed)')
    if B.get('stopped'):
        L.append('- the candidate build was started beside the baseline and stopped once the baseline showed it the same')
    if rep.get('files'):
        L.append('- the merge: %s' % rep['files'][0].strip())
    if rep.get('blender_seconds'):
        L.append('- build time (Blender and QA, from the traces): %s s -> %s s' % tuple(rep['blender_seconds']))
    if rep.get('cpu_seconds') and all(rep['cpu_seconds']):
        L.append('- build CPU time (all processes): %s s -> %s s (%.2fx); threads %s -> %s' % (
            tuple(rep['cpu_seconds']) + (rep['cpu_seconds'][1] / rep['cpu_seconds'][0],
                                         bb.get('threads') or ('uncapped' if not bb.get('cached') else 'cached'),
                                         cb.get('threads') or (rep.get('cpu_threads') or [None, None])[1] or
                                         'uncapped')))
    L.append('\n## Phases\n')
    L += _table(rep.get('phases') or [], [('phase', lambda r: r['phase']), ('start (s)', lambda r: r['start']),
                                          ('seconds', lambda r: r['seconds']), ('note', lambda r: r.get('note', ''))])
    L.append('\nThe gate took %s s.' % rep.get('seconds'))
    parts = [(s, (rep.get(s + '_build') or {})) for s in ('base', 'cand')]
    if any(b.get('steps') or b.get('parts') for _, b in parts):
        names = []
        for _, b in parts:
            for k in list(b.get('steps') or {}) + list(b.get('parts') or {}):
                if k not in names:
                    names.append(k)
        L.append('\nThe builds by step (s; `steps` from the build, `stage` and blender/qa from its trace):\n')
        L += _table(names, [('step', lambda k: k), ('baseline', lambda k: (parts[0][1].get('steps') or {}).get(
            k, (parts[0][1].get('parts') or {}).get(k, ''))), ('candidate', lambda k: (parts[1][1].get('steps') or {}).get(
                k, (parts[1][1].get('parts') or {}).get(k, '')))])
    if rep.get('tests'):
        ts = rep.get('test_seconds') or {}
        slow = sorted(ts, key=ts.get, reverse=True)[:5]
        L.append('\n## Tests\n\n%d files, %d failing%s; %.0f s of test time, the slowest %s.' % (
            len(rep['tests']), sum(v != 'ok' for v in rep['tests'].values()),
            ' (%s)' % ', '.join(k for k, v in rep['tests'].items() if v != 'ok') if any(
                v != 'ok' for v in rep['tests'].values()) else '', sum(ts.values()),
            ', '.join('%s %s s' % (k, ts[k]) for k in slow)))
        L.append('\nTests: ' + ', '.join('%s %s' % (k, 'ok' if v == 'ok' else 'FAILED') for k, v in rep['tests'].items()))
    if rep.get('conflicts'):
        L.append('\nConflicts: ' + ', '.join(rep['conflicts']))
    if rep.get('qa'):
        L.append('\n## All changed checks\n\n| check | base | candidate | verdict |\n| --- | --- | --- | --- |')
        order = {'regressed': 0, 'gone': 1, 'value': 2, 'new': 3, 'improved': 4, 'remeasured': 5, 'ungraded': 6, 'removed': 7}
        for r in sorted(rep['qa'], key=lambda r: order.get(r['verdict'], 9)):
            L.append('| %s | %s %s | %s %s | %s |' % (r['check'], str(r['base'][0])[:10], r['base'][1] or '',
                                                     str(r['cand'][0])[:10], r['cand'][1] or '', r['verdict']))
    elif rep.get('qa') is not None:
        L.append('\n(no check changed)')
    if B.get('affected'):
        L.append('\nWhat the merge changes that the build reads: ' + ', '.join('%s (%s)' % tuple(a) for a in B['affected'][:30]))
    if rep.get('trace'):
        L.append('\n```\n' + rep['trace'][:6000] + '\n```')
    if rep.get('log'):
        L.append('\n```\n' + rep['log'] + '\n```')
    open(base + '.md', 'w').write('\n'.join(L) + '\n')
    print(L[0])
    print(line)
    if rep.get('why'):
        print(rep['why'])
    print('report', base + '.md')
    return rep


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return
    if args[0] == '--rejudge':
        for p in sorted(x for a in args[1:] if not a.startswith('--') for x in (glob.glob(a) or [a])):   # (patterns too)
            r = rejudge(p)
            if '--json' in args:
                print(json.dumps(r, default=str))
            else:
                print('%s (%s) into %s: then %s, under K %s%s%s' % (
                    r['branch'], r['tip'], r['head'], r['verdict_then'], r['verdict_k'],
                    (': ' + r['why_k']) if r['why_k'] else '', '' if r['flags_read'] else ' (flags not read: builds gone)'))
        return
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    if args[0] == '--carry':
        # the integrator's merge queue: exit 0 when a PASS carries to INTO, 1 when a FAIL does, 3 when nothing carries
        # (then gate it: `python -m charkit remote gate BRANCH --into INTO`)
        r = carry(args[1], into=opt('--into', 'pipeline-3d'), spec=opt('--spec', 'charkit/spec/clawd.json'),
                  args=shlex.split(opt('--args', '')), write='--dry-run' not in args, reports=opt('--reports'),
                  run_tests='--no-tests' not in args)
        if '--json' in args:
            print(json.dumps(r, default=str))
        else:
            print('%s (%s) into %s (%s): %s%s' % (r['branch'], r['tip'], r['into'], r['head'],
                                                 'carried: %s from %s' % (r['verdict'], r.get('from')) if r['carried']
                                                 else 'NOT carried', ': ' + r['why'] if r['why'] else ''))
            if r.get('report'):
                print('report', r['report'])
        raise SystemExit(3 if not r['carried'] else 0 if r['verdict'] == 'PASS' else 1)
    rep = gate(args[0], into=opt('--into', 'HEAD'), spec=opt('--spec', 'charkit/spec/clawd.json'),
               args=shlex.split(opt('--args', '')), keep='--keep' in args,
               accept=[a for a in opt('--accept', '').split(',') if a], force_build='--build' in args)
    raise SystemExit(0 if rep['verdict'] != 'FAIL' else 1)
