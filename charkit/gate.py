"""The merge gate: what a branch would do to the integration branch, measured before it lands. Nothing is merged and no
branch moves: throwaway worktrees at the integration head take the baseline and, with `git merge --no-commit`, the
candidate; the tests run, each side is built when it has to be, and the two builds' QA and traces are compared.

    python -m charkit gate BRANCH [--into REF] [--spec SPEC] [--args "--base anime"] [--accept PATTERN,...] [--keep]
                                  [--build]
    python -m charkit gate --rejudge REPORT.json|PATTERN ... [--json]   # earlier reports read under policy K
    python -m charkit gate --accept-fail CHECK --by NAME --why TEXT [--branch BRANCH] [--value V]
        # the coordinator records Michael's acceptance of a named new FAIL (charkit/accepted/CHECK.json: commit it on
        # the branch): the gate reports it, with who, when and why, instead of blocking on it
    python -m charkit gate --carry BRANCH [--into pipeline-3d] [--spec SPEC] [--args ".."] [--no-tests] [--dry-run]
                                  [--json] [--rule definitions|files]
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
  - the build's CPU time over 1.5x the baseline's;
  - a graded check the merge adds with no calibration record (charkit/calibrate.py), or one it remeasures without a
    fresh record, or a record whose verdict isn't calibrated;
  - the anti-gaming guard: the merge improves its own new or flag check while that check's piece's shape IoU (its
    registry `shape`, per view) drops by more than 15% in a view.
A new FAIL (or a guard block) Michael has accepted by name (charkit/accepted/CHECK.json, `gate --accept-fail`) is
reported with who, when and why instead.
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
from .procs import THREAD_VARS         # (numba, BLAS, OpenMP, llvmpipe) every build on the box has them now (procs.cap_threads)


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


def _step_cache_env():
    """the venv steps' entries (charkit.cache.file_step: the code head and body, the hair pieces, the garments) in one
    folder the box's gate builds share (CHARKIT_GATE_STEP_CACHE, default ~/.cache/charkit/steps; 'off': each worktree's
    own, cold, as before), keyed portably and on all the code each step reaches (CHARKIT_STEP_DEPTH=all), so a branch
    that doesn't reach a step restores it in every clone: pieces_hair took 120-200 s a gate, rebuilt each time."""
    v = os.environ.get('CHARKIT_GATE_STEP_CACHE', '~/.cache/charkit/steps')
    if v == 'off':
        return {}
    return {'CHARKIT_STEP_CACHE': os.path.abspath(os.path.expanduser(v)), 'CHARKIT_STEP_DEPTH': 'all'}


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
    env.update(_step_cache_env())
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


# (run in the tree, with its own code: the gate's code may differ from a baseline's)
_PRODUCE = """import json, sys
from charkit import character, manifest
s = character.check_spec(manifest.resolve(json.load(open(sys.argv[1]))))
ref = s.get('ref') if isinstance(s.get('ref'), dict) else {}
R = manifest.load(ref['manifest'])['references'] if ref.get('manifest') else {}
for k, r in R.items():
    if r.get('produced_by'):
        print('CHARKIT_PRODUCED_INPUT', k, manifest.produced(s, k), flush=True)
"""


def produce_inputs(tree, spec):
    """the manifest's produced references (produced_by: the hull, the outfit masks, the hair layers) made in tree by its
    own code from spec, as its build makes them, for a crossed QA there: the QA reads them when they exist and skips
    what needs them otherwise, so in a worktree that never built (a cached baseline's) the old measure measured none of
    the hair_piece_* checks on the new geometry (tool/hairtag 37c09cf's gate: every old-measure cell unmeasured).
    Mostly restores from the shared cache (charkit.manifest). -> None, or why it failed."""
    r = subprocess.run([PY, '-c', _PRODUCE, spec], cwd=tree, capture_output=True, text=True)
    if r.returncode:
        return 'exit %d: %s' % (r.returncode, (r.stdout + r.stderr)[-800:])
    return None


def rebased_bundle(bundle_dir, tmp):
    """a bundle whose spec's paths into its build's out folder (the hair pieces' report, the code head and body, the
    garments) point where that folder is now -> the bundle's folder (itself when they all resolve; else a copy in tmp,
    its arrays linked). A cached baseline was built in another gate's clone, since removed, so a crossed QA on it lost
    what those paths hold: hair_folds read 1342 FAIL (the dihedral fallback) where the build read 5 WARN from the
    builder's report (tool/infra4's real-pair gates, 2026-09-30)."""
    p = os.path.join(bundle_dir, 'bundle.json')
    if not os.path.exists(p):
        return bundle_dir
    meta = json.load(open(p))
    here = os.path.realpath(os.path.dirname(os.path.abspath(bundle_dir)))
    names = {os.path.basename(here), os.path.basename(os.path.dirname(os.path.abspath(bundle_dir)))}
    moved = [0]

    def fix(x):
        if isinstance(x, dict):
            return {k: fix(v) for k, v in x.items()}
        if isinstance(x, list):
            return [fix(v) for v in x]
        if isinstance(x, str) and os.path.isabs(x) and not os.path.exists(x):
            for n in names:
                i = x.find('/' + n + '/')
                if i >= 0 and os.path.exists(os.path.join(here, x[i + len(n) + 2:])):
                    moved[0] += 1
                    return os.path.join(here, x[i + len(n) + 2:])
        return x
    meta['spec'] = fix(meta.get('spec'))
    if not moved[0]:
        return bundle_dir
    # (a mirror of the build's folder, every entry linked, the bundle's own metadata rewritten: the QA finds the build's
    # export beside its bundle, OUT/NAME.look.glb, for the render drawing)
    # (the links name the real folders: a gate reaches gate-out through its own clone's charkit/out/gate link, which
    # goes with the clone; and a mirror an earlier gate of the same pair left in the candidate's folder is repointed:
    # its links named that gate's clone, and the 2x2 couldn't load arrays.npz, tool/calib's re-gates 2026-09-30)
    src = os.path.realpath(os.path.dirname(os.path.abspath(bundle_dir)))
    real = os.path.realpath(bundle_dir)
    mirror = os.path.join(tmp, os.path.basename(src))
    dst = os.path.join(mirror, os.path.basename(real))
    os.makedirs(dst, exist_ok=True)
    for f in os.listdir(src):
        if f != os.path.basename(dst):
            _link(os.path.join(src, f), os.path.join(mirror, f))
    for f in os.listdir(real):
        if f != 'bundle.json':
            _link(os.path.join(real, f), os.path.join(dst, f))
    json.dump(meta, open(os.path.join(dst, 'bundle.json'), 'w'))
    return dst


def _link(target, link):
    """link made a symlink to target, replacing a link that names anything else."""
    if os.path.islink(link) and os.readlink(link) != target:
        os.remove(link)
    if not os.path.lexists(link):
        os.symlink(target, link)


def cross_qa(tree, bundle_dir, out):
    """one tree's QA code on another build's geometry bundle (the 2x2's crossed cells): `python -m charkit qa` run in
    tree, its cache off (a part's cache key is its code, and a crossed run must not restore the other side's), on the
    bundle rebased to where its build's folder is now (rebased_bundle) -> the report (qa.json's) or {'error': why}."""
    os.makedirs(out, exist_ok=True)
    bundle_dir = rebased_bundle(bundle_dir, os.path.join(out, 'rebased'))
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


def twobytwo(base, cand, old_on_new, new_on_old, remeasured, accept=(), detected=()):
    """the 2x2 for each remeasured check: its value and status in base (the old geometry, the old measure), old_on_new
    (the new geometry, the old measure), new_on_old (the old geometry, the new measure) and cand (the new geometry, the
    new measure) -> rows, each with `old` (the new geometry against the old under the old measure: regressed, improved,
    value, same, unmeasured) and `new` (the same under the new measure), and `accepted` (a pattern in accept covers it).
    A check the old measure doesn't have is new with its step: it has no old-measure row. detected: checks whose
    measure changed with no registered step (measure_moved); their rows carry `detected`."""
    import fnmatch
    detected = set(detected or ())

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
        stepped = any(fnmatch.fnmatchcase(k, p) for p in remeasured or {})
        if not stepped and k not in detected:
            continue
        r = dict(check=k, base=cell(base, k), old_on_new=cell(old_on_new, k), new_on_old=cell(new_on_old, k),
                 cand=cell(cand, k))
        if not stepped:
            r['detected'] = True
        r['old'] = verdict(r['base'], r['old_on_new'])
        r['new'] = verdict(r['new_on_old'], r['cand'])
        r['unmeasured'] = unmeasured_cells(r)
        for m, c in (('old', 'old measure on the new geometry'), ('new', 'new measure on the old geometry')):
            if c in r['unmeasured']:
                r[m] = 'unmeasured'
        r['accepted'] = any(fnmatch.fnmatchcase(k, p) for p in accept)
        if r['old'] is None and r['new'] is None:
            continue
        rows.append(r)
    return rows


def unmeasured_cells(r):
    """a 2x2 row's crossed cells that couldn't be measured -> their names: the old measure on the new geometry when the
    old measure has the check (it measured the baseline), the new measure on the old geometry when both do. Each is
    the only view of a remeasured check's geometry change under one fixed measure (Michael's no-gaming rule), so one
    missing blocks the gate (judge), never passes as 'unmeasured'. A check the branch adds has no old-measure cell."""
    ok = lambda c: bool(c) and c[1] not in (None, 'SKIPPED')
    out = []
    if ok(r.get('base')) and not ok(r.get('old_on_new')):
        out.append('old measure on the new geometry')
    if ok(r.get('base')) and ok(r.get('cand')) and not ok(r.get('new_on_old')):
        out.append('new measure on the old geometry')
    return out


def part_owners(meas, *reports):
    """the checks each changed QA part owns -> {part: [checks] or None (unknown)}: the part's own record in a build's
    qa.json (measured.part_checks; the candidate's first), else its registration's naming (a prefix, or a kept name
    start) over the checks the reports have; a part with neither is unknown (any check may be its)."""
    from . import codediff
    names = set()
    for q in reports:
        names |= set((q or {}).get('checks', {}))
    out = {}
    for part, m in meas.items():
        got = next((c for c in (codediff.part_checks(q, part) for q in reports) if c is not None), None)
        if got is None:
            P = m.get('part') or {}
            pre = [x for x in (P.get('prefix'), P.get('keep')) if x]
            got = sorted(k for k in names if k.startswith(tuple(pre)) or k == P.get('skip_key')) if pre else None
        out[part] = got
    return out


def measure_moved(base, cand, old_on_new, new_on_old, names):
    """the checks (of names) that the two measures read differently on the same geometry, on the old or the new one
    -> sorted names: the measure changed for them, whatever the registry says."""
    def cell(q, k):
        c = (q or {}).get('checks', {}).get(k)
        return [c.get('value'), c.get('status')] if c else None
    return sorted(k for k in names if cell(base, k) != cell(new_on_old, k) or cell(old_on_new, k) != cell(cand, k))


def draw_exports(qa_a, qa_b):
    """both QAs must draw from the same kind of export (the look export): a --vrm candidate that had none drew from its
    VRM, and 7 face_shadow values moved with no change (tool/evalmesh ed0f91a, 2026-09-30; builds now write the look
    export beside the VRM) -> a note when the two reports (measured.draw.export) name different kinds, else None."""
    dx = [(((q or {}).get('measured') or {}).get('draw') or {}).get('export') for q in (qa_a, qa_b)]
    kind = lambda f: 'look' if f.endswith('.look.glb') else os.path.splitext(f)[1].lstrip('.')
    if all(dx) and kind(dx[0]) != kind(dx[1]):
        return "the two QAs drew from different exports (%s -> %s): the drawn checks' moves may be the export's, not " \
               "the branch's" % tuple(dx)
    return None


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
    """a sparse worktree at head (no generated inputs linked: charkit/out/i3d, TRELLIS's output, was the only one, and no
    build reads it since the sheet-only outfit masks, decision 8)."""
    from . import sparse
    wt = tempfile.mkdtemp(prefix='charkit-gate-%s-' % label)
    os.rmdir(wt)
    _git('worktree', 'add', '--no-checkout', '--detach', wt, head)
    _git('sparse-checkout', 'set', '--cone', *sparse.dirs('charkit', spec), cwd=wt)
    _git('checkout', '--detach', head, cwd=wt)
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
        # a check whose measuring code the merge changes, registered or not (charkit.codediff: each QA part's code, the
        # baseline's tree against the merged; tool/evalmesh 0c9eb95 changed qa3d.poke with the geometry and registered
        # nothing, and the gate compared poke_share across both changes at once)
        meas = {}
        if cand_q != base_out:
            from . import codediff
            with clock('measure code', "each QA part's measuring code, the baseline's tree against the merged") as ph:
                try:
                    meas = codediff.measure_changes(wb, wc)
                except Exception as e:                  # (never the gate's failure: the note says it wasn't looked at)
                    rep.setdefault('notes', []).append("the QA's code wasn't compared (%s: %s)" % (type(e).__name__, e))
                ph['note'] = '%d part%s changed' % (len(meas), 's' * (len(meas) != 1))
        owners = part_owners(meas, qa_b, qa_a)
        n = draw_exports(qa_a, qa_b)
        if n:
            rep.setdefault('notes', []).append(n)
        # the 2x2: a remeasured check on changed geometry scored under both measures: the candidate's code (the merged
        # worktree) measures the baseline's bundle, the baseline's measures the candidate's
        (ga, ha), (gb, hb) = geometry(base_out), geometry(cand_q)
        stepped = [k for k in set(qa_a.get('checks', {})) | set(qa_b.get('checks', {}))
                   if any(fnmatch.fnmatchcase(k, p) for p in rep["remeasured"])]
        every = set(qa_a.get('checks', {})) | set(qa_b.get('checks', {}))
        owned = every if any(v is None for v in owners.values()) else {k for v in owners.values() for k in v}
        owned = {k for k in owned if not any(fnmatch.fnmatchcase(k, p) for p in rep['remeasured'])}
        if meas:
            rep['unregistered'] = {'parts': {p: v['units'][:12] for p, v in meas.items()},
                                   'owners': {p: (v[:40] if v is not None else None) for p, v in owners.items()},
                                   'geometry': 'changed' if ga != gb else 'unchanged', 'checks': []}
            if ga == gb:
                # the same geometry: every move of these checks is the measure's (judged as usual: nothing registered)
                rep['unregistered']['checks'] = sorted(r['check'] for r in rep['qa'] if r['check'] in owned)
        if (stepped or (meas and owned)) and ga != gb:
            with clock('2x2', 'both QA codes on both bundles'):
                # each tree's produced references first: a tree that didn't build (a cached baseline's, a carried
                # candidate's) has none, and its QA would skip the checks that read them
                def crossed(tree, bundle, x):
                    e = produce_inputs(tree, spec)
                    return {'error': "its produced references couldn't be made: " + e} if e else \
                        cross_qa(tree, bundle, x)
                f1 = ex.submit(crossed, wc, os.path.join(base_out, 'bundle'), os.path.join(cand_out, 'x_new_measure_old_geometry'))
                f2 = ex.submit(crossed, wb, os.path.join(cand_out, 'bundle'), os.path.join(cand_out, 'x_old_measure_new_geometry'))
                new_on_old, old_on_new = f1.result(), f2.result()
            errs = {k: q['error'] for k, q in (('new measure on the old geometry', new_on_old),
                                               ('old measure on the new geometry', old_on_new)) if 'error' in q}
            # the checks whose measure changed with no registered step: the two measures read them differently
            detected = [] if errs or not meas else measure_moved(qa_a, qa_b, old_on_new, new_on_old, owned)
            if meas:
                rep['unregistered']['checks'] = detected
            rep['twobytwo'] = {'rows': twobytwo(qa_a, qa_b, None if errs else old_on_new, None if errs else new_on_old,
                                                rep['remeasured'], accept, detected), 'errors': errs,
                               'bundles': [ga, gb], 'arrays_changed': sum(ha.get(k) != hb.get(k) for k in set(ha) | set(hb))}
        elif stepped:
            rep['twobytwo'] = {'rows': [], 'errors': {}, 'bundles': [ga, gb], 'same_geometry': True}
        # the calibration records a new or remeasured check needs, the anti-gaming guard, Michael's acceptances: read
        # from the merged tree (charkit/calibrate.py), only when checks moved (milliseconds: json and a literal)
        if rep['qa']:
            calibration_step(rep, wc, head, qa_a, qa_b, clock)
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


def calibration_step(rep, tree, head, qa_a, qa_b, clock=None):
    """the merged tree's calibration records against what the merge adds and remeasures (rep['calibration']), the
    anti-gaming guard's findings and the pieces' shapes beside the improved checks (rep['guard'], rep['shapes']), and
    Michael's recorded acceptances (rep['accepted']). tree: the merged worktree; head: the integration commit."""
    from . import calibrate, registry
    ca, cb = (qa_a or {}).get('checks', {}), (qa_b or {}).get('checks', {})
    is_flag = lambda k: registry.is_flag(ca.get(k)) or registry.is_flag(cb.get(k))
    with (clock('calibration', "the records, the guard and the acceptances, from the merged tree") if clock else
          contextlib.nullcontext({})) as ph:
        try:
            E = calibrate.entries(tree)
            rep['calibration'] = calibrate.requirements(tree, (tree, head), qa_a, qa_b, rep)
            rep['guard'] = calibrate.guard(rep, qa_a, qa_b, is_flag, E=E, R=calibrate.records(tree))
            rep['shapes'] = calibrate.shape_report(rep, qa_a, qa_b, E=E)
            rep['accepted'] = calibrate.accepted(tree)
        except Exception as e:                      # (never the gate's failure: the note says what wasn't read)
            rep.setdefault('notes', []).append("the calibration records weren't read (%s: %s)" % (type(e).__name__, e))
            rep['calibration'] = {'rows': [], 'error': str(e)}
        n = rep.get('calibration') or {}
        ph['note'] = '%d check%s need a record, %d guard finding%s' % (
            len(n.get('rows') or ()), 's' * (len(n.get('rows') or ()) != 1), len(rep.get('guard') or ()),
            's' * (len(rep.get('guard') or ()) != 1))
    return rep


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


def _kit_py(p):
    """charkit's own Python, as the code walk compares it (its tests and outputs aside)."""
    return p.startswith('charkit/') and p.endswith('.py') and not p.startswith(('charkit/tests/', 'charkit/out/'))


def _carry_hits(root, cone, Cs, old, h0, head, t0, t1, moved, diff, later=()):
    """what stops an earlier gate (tip into h0, merged tree t0) carrying to head (t1): the definition rule -> {kind:
    [(what, why)]}.
      - charkit's Python: the move's changed definitions (h0 -> head) and the branch's (h0 -> t0) meet: one side's among
        what the other's reach, in either tree (charkit.codediff.interacts). A file both touch, or one the builds read,
        no longer stops it by itself: an infra-only move (gate.py, cache.py, remote.py) reaches nothing the branch
        changed.
      - the QA's boundary, where data rather than calls joins the two: the move changes a QA part's measuring code (or
        adds a part) while the branch changes what the QA reads (its candidate was built); or the branch changes a
        measure (registered or not) while the move changes a file the baseline read.
      - anything else (data files, Python outside charkit), and every file the branch itself changed since the gated
        tip (later): as before, the files the two builds read."""
    from . import cache, closure, codediff
    trees = {}
    T = lambda r: trees.setdefault(r, cache.Tree(repo=root, rev=r))
    other = lambda ch: [(st, p) for st, p in ch if not _kit_py(p)]
    own = [(st, p) for st, p in diff if p in later]
    hits = {'baseline': closure.affected(Cs['base'], other(moved), root, cone, rev=h0, new=head, untracked=False),
            'candidate': closure.affected(Cs['cand'], other([x for x in diff if x not in own]) + own, root, cone,
                                          rev=t0, new=t1, untracked=False)}
    mv = sorted(p for _, p in moved if _kit_py(p))
    br = sorted(p for _, p in closure.changes(root, h0, t0) if _kit_py(p))
    if mv and br:
        M = codediff.changed(T(h0), T(head), paths=mv, repo=root)
        B = codediff.changed(T(h0), T(t0), paths=br, repo=root)
        if M and B:
            hits['definitions'] = codediff.interacts(M, B, [T(head), T(t1)], [T(t0), T(t1)])
    built = (old.get('build') or {}).get('candidate') in ('built', 'carried')
    if mv and built:
        mq = codediff.measure_changes(T(h0), T(head))
        new_parts = sorted({P['name'] for P in codediff.part_defs(T(head))} -
                           {P['name'] for P in codediff.part_defs(T(h0))})
        hits['measure'] = [(p, 'the move changes its measuring code (%s) and the branch changes what the QA reads' % (
            ', '.join(v['units'][:3]))) for p, v in mq.items()] + [
            (p, 'the move adds this QA part and the branch changes what the QA reads') for p in new_parts]
    if br and moved:
        bq = codediff.measure_changes(T(h0), T(t0)) if built else {}
        if bq or old.get('remeasured'):
            reach = closure.affected(Cs['base'], moved, root, cone, rev=h0, new=head, untracked=False)
            if reach:
                hits.setdefault('measure', []).extend(
                    (p, 'the branch changes a measure (%s) and the move changes what the baseline build read' % (
                        ', '.join(sorted(bq) or sorted(old.get('remeasured') or ()))[:120])) for p, _ in reach[:4])
    return hits


def carry(branch, into='pipeline-3d', spec='charkit/spec/clawd.json', args=(), write=True, reports=None, root=ROOT,
          run_tests=True, rule='definitions'):
    """the newest gate of the branch's tip (any branch name) into an ancestor H0 of INTO, carried over to INTO with no
    build and no box, when the verdict can't differ there (ROADMAP "Reuse a gate when pipeline-3d moves"):
      - the branch still merges into INTO cleanly (git merge-tree);
      - no change from H0 to INTO reaches the baseline's closure (so INTO's baseline is H0's build);
      - no difference between the two merged trees (the tip into H0, the tip into INTO) reaches the candidate's closure
        (so the candidate is the same build) or the tests' (so the tests read the same files; a test file added or
        deleted counts);
      - or, for a gate that built nothing because the branch changes only docs and tests, the merge into INTO still
        changes only those, and the tests' closure is untouched.
    rule 'definitions' (the default since tool/infra4): charkit's Python counts at the level of definitions (the move's
    changed definitions against the branch's and what they reach; _carry_hits), data and other files as before; 'files':
    every file either build read (the first rule: an infra-only move or a shared file with no shared definition stopped
    it).
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
            if rule == 'files':
                hits['baseline'] = closure.affected(Cs['base'], moved, root, cone, rev=h0, new=head, untracked=False)
                hits['candidate'] = closure.affected(Cs['cand'], diff, root, cone, rev=t0, new=t1, untracked=False)
            else:
                hits.update(_carry_hits(root, cone, Cs, old, h0, head, t0, t1, moved, diff,
                                        {p_ for _, p_ in closure.changes(root, tip0, tip)} if tip0 != tip else set()))
        else:
            reasons.append('%s: its builds recorded no closure' % name)
            continue
        if any(hits.values()):
            res.setdefault('hits', {k: v[:20] for k, v in hits.items() if v})
            res.setdefault('from', name)
            head_ = {'baseline': 'the baseline reads', 'candidate': 'the candidate reads',
                     'definitions': 'the move and the branch meet at', 'measure': 'the QA boundary:'}
            reasons.append('%s (into %s): %s' % (name, h0, '; '.join('%s %s' % (head_.get(k, k), ', '.join(
                '%s (%s)' % h for h in v[:4]) + (' and %d more' % (len(v) - 4) if len(v) > 4 else ''))
                for k, v in hits.items() if v)))
            continue
        why = '%s moved %d files since %s%s and the merged trees differ in %d; none reaches the baseline or the ' \
              'candidate build%s' % (into, len(moved), h0, '' if tip0 == tip else ' (and the branch since %s: %d files)'
                                     % (tip0, len(closure.changes(root, tip0, tip))), len(diff),
                                     ' (charkit\'s Python by definition: the move\'s changes and the branch\'s don\'t '
                                     'meet)' if rule != 'files' and any(_kit_py(p_) for _, p_ in moved) else '')
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
                         'remeasured', 'unregistered', 'twobytwo', 'accepted', 'calibration', 'shapes', 'notes')}
    R['notes'] += list(rep.get('notes') or ())
    # a QA part whose measuring code changed with no registered step (charkit.codediff): its checks' moves are judged
    # as any others (nothing is relaxed), and on changed geometry the 2x2 scores them under each measure too
    ur = rep.get('unregistered') or {}
    for part, units in sorted((ur.get('parts') or {}).items()):
        own = (ur.get('owners') or {}).get(part)
        checks = [k for k in ur.get('checks') or () if own is None or k in own]
        R['unregistered'].append(dict(part=part, units=units, checks=checks, geometry=ur.get('geometry'),
                                      owners_known=own is not None))
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
    # the 2x2 never skips silently: a crossed cell it couldn't measure, or a crossed QA that couldn't run, blocks
    # (from the cells, so --rejudge reads an old report's rows the same way)
    for r in tb.get('rows') or ():
        cells = unmeasured_cells(r)
        if cells:
            row = dict(check=r['check'], cells=cells, base=r.get('base'), old_on_new=r.get('old_on_new'),
                       new_on_old=r.get('new_on_old'), cand=r.get('cand'), measures=[])
            if r.get('accepted'):
                R['twobytwo'].append(dict(row, note='unmeasured: %s; accepted (--accept)' % ', '.join(cells)))
            else:
                block.append(dict(row, kind="the 2x2 couldn't measure it" + (
                    ' (its measure changed with no registered step)' if r.get('detected') else '')))
    for k in sorted(tb.get('errors') or {}):
        if all(r.get('accepted') for r in tb.get('rows') or ()) and tb.get('rows'):
            R['notes'].append('the 2x2 could not run the %s: its remeasured checks (all accepted) are unverified '
                              'there' % k)
        else:
            block.append({'kind': 'the 2x2 could not run the %s' % k, 'error': str(tb['errors'][k])[-300:]})
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
        why = '; its measure changed with no registered step: register a remeasure' if r.get('detected') else ''
        if r.get('detected'):
            row['detected'] = True
        if r.get('accepted'):
            R['twobytwo'].append(dict(row, note='accepted (--accept)'))
        elif any(after[m] == 'FAIL' for m in worse):
            block.append(dict(row, kind='new FAIL under one measure on both geometries (the 2x2%s)' % why))
        elif is_flag(r['check']):
            block.append(dict(row, kind='flag check worse under one measure on both geometries (the 2x2%s)' % why))
        else:
            R['twobytwo'].append(row)
    # calibration (Michael's rule): a graded check the merge adds needs a record, one it remeasures a fresh one, and a
    # record must say calibrated (charkit/calibrate.py; rep['calibration'] from the merged tree)
    for r in (rep.get('calibration') or {}).get('rows') or ():
        c = (cb.get(r['check']) or {})
        row = dict(check=r['check'], why=r['why'], record=r['record'], cand=[c.get('value'), c.get('status')],
                   why_record=r.get('why_record'))
        (R['calibration'] if r.get('ok') else block).append(row if r.get('ok') else dict(row, kind='calibration'))
    # the anti-gaming guard (Michael, 2026-09-30): the merge improves its own new or flag check while that check's
    # piece's shape IoU drops by more than calibrate.DROP in a view
    G = rep.get('guard')
    if G is None and qa_a and qa_b:
        from . import calibrate
        G = calibrate.guard(rep, qa_a, qa_b, is_flag)
        if rep.get('shapes') is None:
            rep['shapes'] = calibrate.shape_report(rep, qa_a, qa_b)
    R['shapes'] = list(rep.get('shapes') or ())
    by = {}
    for g in G or ():
        by.setdefault(g['check'], []).append(g)
    for k, gs in sorted(by.items()):
        g0 = min(gs, key=lambda g: g['rel'])
        block.append(dict(check=k, kind='anti-gaming guard', how=g0['how'], **{'from': g0['from'], 'to': g0['to']},
                          drops=[{x: g[x] for x in ('shape', 'view', 'base', 'cand', 'rel')} for g in gs]))
    # Michael's acceptance of a named new FAIL (or a guard block on it), recorded in the merged tree (charkit/accepted/):
    # reported with who decided, when and why, not blocking
    acc = rep.get('accepted') or {}
    if acc:
        from . import calibrate
        keep = []
        for b in block:
            a = acc.get(b.get('check'))
            if b.get('kind') in ('new FAIL', 'anti-gaming guard') and calibrate.covers(a, rep.get('branch')):
                R['accepted'].append(dict(b, accepted={k: a.get(k) for k in ('by', 'at', 'why', 'value', 'branch',
                                                                              'recorded_by')}))
            else:
                keep.append(b)
        block = keep
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
    if k == 'calibration':
        rec = b.get('record')
        what = {'missing': 'no calibration record', 'stale': 'the calibration record not refreshed'}.get(
            rec, 'the calibration record says %s' % rec)
        return '%s: %s (%s check%s; python -m charkit calibrate %s)' % (
            what, b['check'], 'a new' if b.get('why') == 'new' else 'a remeasured',
            ': ' + b['why_record'] if b.get('why_record') and rec not in ('missing', 'stale') else '', b['check'])
    if k == 'anti-gaming guard':
        d = min(b['drops'], key=lambda x: x['rel'])
        return 'anti-gaming guard: %s improved (%s -> %s; %s) while %s fell in %s %.3g -> %.3g (%+.0f%%)%s' % (
            b['check'], _cell(b.get('from')), _cell(b.get('to')), b.get('how'), d['shape'], d['view'], d['base'],
            d['cand'], 100 * d['rel'], ' and %d more view%s' % (len(b['drops']) - 1, 's' * (len(b['drops']) > 2))
            if len(b['drops']) > 1 else '')
    if b.get('cells'):
        return '%s: %s (%s; the old geometry %s, the candidate %s)' % (k, b['check'], ', '.join(b['cells']),
                                                                     _cell(b.get('base')), _cell(b.get('cand')))
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
                       ('remeasured', 'Remeasured'),
                       ('unregistered', 'Measuring code changed with no registered step (register a remeasure in '
                                        'charkit/steps/ if intended)'),
                       ('twobytwo', "The 2x2's drops (not blocking)"),
                       ('accepted', "Accepted by name (Michael's call, recorded in charkit/accepted/)"),
                       ('calibration', 'Calibration records of the new and remeasured checks (charkit/calib/records)'),
                       ('shapes', "The pieces' shape beside the checks that moved (the anti-gaming guard's evidence)")):
        rows = R.get(key) or []
        if not rows:
            continue
        L.append('**%s** (%d):\n' % (title, len(rows)))
        if key == 'accepted':
            L += _table(rows, [('check', lambda r: r['check']), ('what', lambda r: r.get('kind')),
                               ('candidate', lambda r: _cell(r.get('cand') or r.get('to'))),
                               ('by', lambda r: r['accepted'].get('by')), ('when', lambda r: r['accepted'].get('at')),
                               ('why', lambda r: r['accepted'].get('why'))])
            L.append('')
            continue
        if key == 'calibration':
            L += _table(rows, [('check', lambda r: r['check']), ('', lambda r: r['why']),
                               ('record', lambda r: r['record']), ('candidate', lambda r: _cell(r.get('cand'))),
                               ('the record says', lambda r: r.get('why_record') or '')])
            L.append('')
            continue
        if key == 'shapes':
            f = lambda x: '-' if x is None else '%.3g' % x
            L += _table(rows, [('check', lambda r: r['check']), ('shape', lambda r: r['shape']),
                               ('per view, base -> candidate', lambda r: '; '.join(
                                   '%s %s -> %s%s' % (v, f(a), f(b), ' (%+.0f%%)' % (100 * (b - a) / a) if a and b is
                                                      not None else '') for v, (a, b) in r['views'].items()))])
            L.append('')
            continue
        if key == 'unregistered':
            L += _table(rows, [('QA part', lambda r: r['part']),
                               ('its code that changed', lambda r: ', '.join(r['units'][:6]) + (
                                   ' and %d more' % (len(r['units']) - 6) if len(r['units']) > 6 else '')),
                               ('checks read differently' if rows[0].get('geometry') == 'changed' else 'checks that moved'
                                ' (the geometry is the same)', lambda r: ', '.join(r['checks'][:8]) + (
                                    ' and %d more' % (len(r['checks']) - 8) if len(r['checks']) > 8 else '') or '-'),
                               ('', lambda r: '' if r['owners_known'] else "(the part's checks unrecorded: any)")])
            L.append('')
            continue
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
                    r['check'] + (' (unregistered)' if r.get('detected') else ''), c2(r['base']), c2(r['old_on_new']), c2(r['new_on_old']), c2(r['cand']),
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
                  run_tests='--no-tests' not in args, rule=opt('--rule', 'definitions'))
        if '--json' in args:
            print(json.dumps(r, default=str))
        else:
            print('%s (%s) into %s (%s): %s%s' % (r['branch'], r['tip'], r['into'], r['head'],
                                                 'carried: %s from %s' % (r['verdict'], r.get('from')) if r['carried']
                                                 else 'NOT carried', ': ' + r['why'] if r['why'] else ''))
            if r.get('report'):
                print('report', r['report'])
        raise SystemExit(3 if not r['carried'] else 0 if r['verdict'] == 'PASS' else 1)
    if args[0] == '--accept-fail':
        # Michael's acceptance of a named new FAIL, recorded for the gate (the coordinator's, on Michael's call)
        from . import calibrate
        v = opt('--value')
        r = calibrate.accept(args[1], by=opt('--by'), why=opt('--why'), value=float(v) if v else None,
                             branch=opt('--branch'), recorded_by=opt('--recorded-by', 'coordinator'))
        print('recorded: %s accepted by %s (%s): %s -> %s; commit it on the branch' % (
            r['check'], r['by'], r['at'], r['why'], os.path.join(calibrate.ACCEPTED, r['check'] + '.json')))
        return
    rep = gate(args[0], into=opt('--into', 'HEAD'), spec=opt('--spec', 'charkit/spec/clawd.json'),
               args=shlex.split(opt('--args', '')), keep='--keep' in args,
               accept=[a for a in opt('--accept', '').split(',') if a], force_build='--build' in args)
    raise SystemExit(0 if rep['verdict'] != 'FAIL' else 1)
