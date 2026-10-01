"""Calibration: a check proven before it is trusted (Michael's rule: a new check passes on the design and fails on a
known-bad example; docs/CHARKIT_HANDOFF.md, "When a check and Michael's eye disagree"). Several checks passed while the
thing they claim to measure was wrong (tool/calib, 2026-09-30): look5's chin read the design's own shadow moved 1-2 px
as IoU 0.55-0.87; hair_piece_bangs read 0.79 PASS while our bang locks scored no better than a random split;
piece_sleeve passed while the puff caps rose above the shoulder line. Each round hand-rolled its own calibration. This
is the one tool: the calibration triple, per check, recorded.

    python -m charkit calibrate CHECK[,CHECK..] [--build DIR] [--seeds N] [--no-write] [--json OUT] [--declared F.json]
        CHECK a check name or pattern (fnmatch). The checks' QA part runs on:
          design    the design's own inputs standing for ours, moved 1-2 px in each direction (MOVES): it must PASS
                    every move; the spread is reported
          known-bad the named flagged build (a stored bundle, `calibrate store`), with this tree's QA code: it must FAIL
          floor     a random baseline standing for ours (the registry's generator: shuffled labels or partitions, a
                    jittered or affine-perturbed geometry, SEEDS seeds): it must not PASS, and the current build must
                    beat it clearly (MARGIN of the way from the floor to the design). A current build that PASSes
                    while it sits at the floor means the check is too coarse or measures the wrong thing
          probes    (optional) a perturbation of structure the design draws (the sleeves' caps raised): a check that
                    still PASSes is blind to it (the granularity check); reported, it doesn't decide the verdict
          current   --build DIR (default: the newest build under charkit/out/calib/cur_*), this tree's QA code
        and the record goes to charkit/calib/records/CHECK.json (the gate reads it: a new or remeasured check needs one)
        A declared check (charkit.declared: a family, a piece, limits) carries its entry in its declaration; the
        adapter is its part's stand-in (Declared for the 'declared' part), so a new flag needs no adapter code.
        --declared F.json: declarations from a file (a draft flag, before it is committed), measured and calibrated
    python -m charkit calibrate store NAME BUILD_DIR --why TEXT [--commit C] [--flag TEXT]
        keep a build as a named known-bad: its bundle, qa, geometry and look export hard-linked (no copy) under
        charkit/out/calib/builds/NAME, the bundle's paths rebased there; charkit/calib/known_bad/NAME.json says what it is
    python -m charkit calibrate list [PATTERN]      the registry's checks and their records' verdicts
    python -m charkit calibrate show CHECK          a record

The registry: each module under charkit/calib/ holds a module-level literal CALIBRATION = [dict, ...] (read with ast,
nothing imported, so the gate reads the merged tree's without running it; no central list to conflict on):
    check      the check name or pattern
    part       the QA part that measures it
    adapter    the module's class that stands the design (or a baseline) in for ours: Adapter(B, design) with
               .part (a name), .substitute(kind, arg) (a context manager: kind 'design' with arg a move (dy, dx), or a
               generator's name with arg a seed), .generators {name: what it does}
    known_bad  the stored build's name (charkit/calib/known_bad/NAME.json), or None with `no_known_bad` saying why
    baseline   the floor's generators (names in the adapter's .generators)
    probes     (optional) structure probes (names in .generators)
    invariant  (optional) generators that change only what the check must NOT see (the hands' MCP span under a thumb
               moved alone: Michael 2026-10-01, a palm width read across the thumb): every seed must PASS, else the
               verdict is 'confounded'
    shape      the piece shape checks that guard it (the gate's anti-gaming guard: this check improving while one of
               these drops by more than DROP in any view blocks); default: piece_<its first word> when qa.json has it
    better     'lower' or 'higher' (default: from the design against the floor)
    kind       'shape' (the default: agreement with the drawing; a random stand-in must not pass, and the current build
               must beat it clearly) or 'defect' (a detector of one flagged defect: a random stand-in lacks the defect
               and may pass it, which says the check sees that defect, not the shape: its `shape` guards the shape)

The verdict (a record's `verdict`): calibrated; guard (calibrated without a known-bad: a guard check); miscalibrated
(the design fails its own check moved 1-2 px); blind (the known-bad passes); coarse (a random baseline passes, or the
current build passes at the floor); unmeasured (the triple couldn't run, or the check has neither a known-bad nor a
random floor: nothing it must fail).
"""
import ast, contextlib, fnmatch, glob, importlib, json, os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAL = os.path.join('charkit', 'calib')
RECORDS = os.path.join(CAL, 'records')                     # (paths relative to a tree's root)
KNOWN = os.path.join(CAL, 'known_bad')
ACCEPTED = os.path.join('charkit', 'accepted')             # Michael's accepted new FAILs (accept(); the gate reads them)
STORE = os.path.join(ROOT, 'charkit', 'out', 'calib', 'builds')
REG = 'CALIBRATION'
RANK = {'PASS': 0, 'WARN': 1, 'FAIL': 2}
MOVES = ((0, 1), (0, 2), (1, 0), (2, 0), (0, -1), (0, -2), (-1, 0), (-2, 0))     # px (rows, columns): 1-2 each way
SEEDS = 5
MARGIN = 0.5            # the current build beats the floor "clearly": this share of the way from the floor to the design
DROP = 0.15             # the anti-gaming guard: a piece's shape IoU falling by more than this (relative) in a view
GOOD = ('calibrated', 'guard')


# ------------------------------------------------------------------------------------------------------------ registry
def _literal(src, name=REG):
    """a module source's top-level `NAME = [...]` literal (ast; nothing run) -> list, or None."""
    if name not in src:
        return None
    for node in ast.parse(src).body:
        targets = node.targets if isinstance(node, ast.Assign) else []
        if any(getattr(t, 'id', None) == name for t in targets):
            return _lit(node.value)
    return None


def _lit(n):
    """a literal, with dict(key=literal, ...) calls read as dicts (the registry's entries are written that way)."""
    if isinstance(n, ast.Call) and getattr(n.func, 'id', None) == 'dict' and not n.args:
        return {k.arg: _lit(k.value) for k in n.keywords}
    if isinstance(n, (ast.List, ast.Tuple)):
        return [_lit(x) for x in n.elts]
    if isinstance(n, ast.Dict):
        return {_lit(k): _lit(v) for k, v in zip(n.keys, n.values)}
    return ast.literal_eval(n)


def _files(root, rel):
    """the files under root/rel: root a directory (a worktree) -> {relative path: text}."""
    out = {}
    for p in sorted(glob.glob(os.path.join(root, rel, '*'))):
        if os.path.isfile(p):
            out[os.path.relpath(p, root)] = open(p, encoding='utf-8').read()
    return out


def _git_files(repo, rev, rel):
    """the files under rel in a git revision or tree id -> {relative path: text} (nothing checked out; one git process
    for all the blobs)."""
    r = subprocess.run(['git', 'ls-tree', '%s:%s' % (rev, rel)], cwd=repo, capture_output=True, text=True)
    ents = [l.split(None, 3) for l in r.stdout.splitlines()] if r.returncode == 0 else []
    ents = [(e[2], e[3]) for e in ents if len(e) == 4 and e[1] == 'blob']
    if not ents:
        return {}
    b = subprocess.run(['git', 'cat-file', '--batch'], cwd=repo, capture_output=True,
                       input=''.join(sha + '\n' for sha, _ in ents).encode())
    out, buf, i = {}, b.stdout, 0
    for sha, name in ents:
        head_end = buf.index(b'\n', i)
        size = int(buf[i:head_end].split()[2])
        out[os.path.join(rel, name)] = buf[head_end + 1:head_end + 1 + size].decode('utf-8', 'replace')
        i = head_end + 1 + size + 1
    return out


def read_tree(tree=ROOT, rel=CAL, repo=ROOT):
    """a tree's files under rel: tree a directory, or (repo, rev) a git revision or tree id."""
    if isinstance(tree, (tuple, list)):
        return _git_files(tree[0], tree[1], rel)
    return _files(tree, rel)


def entries(tree=ROOT):
    """every registry entry (each charkit/calib module's CALIBRATION literal, module by module in name order), then the
    entries the declared checks carry (charkit.declared: a declaration's `calibrate` block, its part's stand-in as the
    adapter; a calib module's own entry for the same check comes first) -> [dict], each with 'module'."""
    out = []
    for path, src in sorted(read_tree(tree, CAL).items()):
        if not path.endswith('.py') or path.endswith('__init__.py'):
            continue
        got = _literal(src)
        for e in got or ():
            out.append(dict(e, module='charkit.calib.' + os.path.basename(path)[:-3]))
    try:
        from . import declared
        files = read_tree(tree, 'charkit')
        out += declared.calibration_entries(declared.declarations(files=files))
    except Exception:                                   # (a tree from before charkit.declared, a syntax error there)
        pass
    return out


def entry_for(check, E=None):
    """the first registry entry whose pattern matches check -> dict or None."""
    for e in E if E is not None else entries():
        if fnmatch.fnmatchcase(check, e['check']):
            return e
    return None


def _write_json(path, obj):
    """a record written as a new file (temp + rename): a box's copy of the worktree hard-links its synced inputs from a
    read-only blob cache (charkit/bucketsync.py), and writing through that link fails (tool/hands2's first box
    calibration: PermissionError on an existing record)."""
    tmp = path + '.tmp%d' % os.getpid()
    with open(tmp, 'w') as f:
        json.dump(obj, f, indent=1, default=str)
    os.replace(tmp, path)


def records(tree=ROOT):
    """a tree's calibration records -> {check: record}."""
    out = {}
    for path, src in read_tree(tree, RECORDS).items():
        if path.endswith('.json'):
            try:
                r = json.loads(src)
                out[r.get('check') or os.path.basename(path)[:-5]] = r
            except ValueError:
                pass
    return out


def accepted(tree=ROOT):
    """a tree's recorded acceptances of named new FAILs (accept()) -> {check: record}."""
    out = {}
    for path, src in read_tree(tree, ACCEPTED).items():
        if path.endswith('.json'):
            try:
                r = json.loads(src)
                out[r['check']] = r
            except (ValueError, KeyError):
                pass
    return out


def shapes_of(check, E=None, qa=None):
    """the piece shape checks that guard a check (its entry's `shape`; else piece_<its first word> when a qa.json has
    it, e.g. bow_profile_ribbon -> piece_bow) -> [names]."""
    e = entry_for(check, E)
    if e and e.get('shape') is not None:
        return list(e['shape'])
    word = check.split('_')[0]
    names = set()
    for q in qa or ():
        names |= set((q or {}).get('checks', {}))
    return ['piece_' + word] if 'piece_' + word in names and 'piece_' + word != check else []


def graded(c):
    """a check's status as calibrated: its proposed grade when it reports INFO beside one (charkit.artifactqa's way),
    else its status."""
    if not isinstance(c, dict):
        return None
    if c.get('status') in ('INFO', 'WARN', 'PASS') and c.get('grade') in RANK:
        return c['grade']
    return c.get('status')


# ------------------------------------------------------------------------------------------------------ builds, store
def load_bundle(build, tmp=None):
    """a build folder's (or its bundle folder's) bundle, its spec's paths rebased to where the build is now."""
    from . import bundle, gate
    bdir = build if os.path.exists(os.path.join(build, 'bundle.json')) else os.path.join(build, 'bundle')
    tmp = tmp or os.path.join(ROOT, 'charkit', 'out', 'calib', 'rebased')
    return bundle.load(gate.rebased_bundle(bdir, tmp))


def known_bad(name, tree=ROOT):
    """a named known-bad build: (its folder in the store, its record) or (None, record or None)."""
    rec = None
    for path, src in read_tree(tree, KNOWN).items():
        if os.path.basename(path) == name + '.json':
            rec = json.loads(src)
    d = os.path.join(STORE, name)
    return (d if os.path.isdir(os.path.join(d, 'bundle')) else None), rec


def store(name, src, why, commit=None, flag=None):
    """keep build src as the named known-bad: bundle/, qa/qa.json, geom/, the look export and the spec hard-linked into
    STORE/NAME (no copy: the store keeps them when src is removed), bundle.json copied with its spec's paths into src
    rebased onto the store; charkit/calib/known_bad/NAME.json written (commit it)."""
    src = os.path.abspath(src)
    dst = os.path.join(STORE, name)
    os.makedirs(dst, exist_ok=True)
    orig = os.path.basename(src)
    for sub in ('bundle', 'qa', 'geom'):
        for d, _, fs in os.walk(os.path.join(src, sub)):
            for f in fs:
                a = os.path.join(d, f)
                b = os.path.join(dst, os.path.relpath(a, src))
                os.makedirs(os.path.dirname(b), exist_ok=True)
                if os.path.lexists(b):
                    os.remove(b)
                if f == 'bundle.json' and sub == 'bundle':
                    continue
                try:
                    os.link(a, b)
                except OSError:
                    import shutil
                    shutil.copy2(a, b)
    for f in os.listdir(src):
        if f.endswith(('.look.glb', '.spec.json')) and os.path.isfile(os.path.join(src, f)):
            b = os.path.join(dst, f)
            if not os.path.lexists(b):
                os.link(os.path.join(src, f), b)
    meta = json.load(open(os.path.join(src, 'bundle', 'bundle.json')))

    def fix(x):
        if isinstance(x, dict):
            return {k: fix(v) for k, v in x.items()}
        if isinstance(x, list):
            return [fix(v) for v in x]
        if isinstance(x, str) and os.path.isabs(x) and ('/%s/' % orig) in x:
            return os.path.join(dst, x.split('/%s/' % orig, 1)[1])
        return x
    meta['spec'] = fix(meta.get('spec'))
    json.dump(meta, open(os.path.join(dst, 'bundle', 'bundle.json'), 'w'))
    q = os.path.join(src, 'qa', 'qa.json')
    rec = dict(name=name, why=why, flag=flag, commit=commit, source=src.replace(os.path.expanduser('~'), '~'),
               stored=time.strftime('%Y-%m-%d'),
               bundle=(meta.get('content') or '')[:16] if isinstance(meta.get('content'), str) else None,
               qa_checks=len(json.load(open(q)).get('checks', {})) if os.path.exists(q) else None)
    os.makedirs(os.path.join(ROOT, KNOWN), exist_ok=True)
    json.dump(rec, open(os.path.join(ROOT, KNOWN, name + '.json'), 'w'), indent=1)
    return dst, rec


def current_build():
    """the newest build under charkit/out/calib/cur_* (a build of the integration head), or None."""
    got = sorted((d for d in glob.glob(os.path.join(ROOT, 'charkit', 'out', 'calib', 'cur_*'))
                  if os.path.isdir(os.path.join(d, 'bundle'))), key=os.path.getmtime)
    return got[-1] if got else None


# ------------------------------------------------------------------------------------------------------------ the triple
def _vs(C, k):
    c = (C or {}).get(k)
    return [None, None] if not isinstance(c, dict) else [c.get('value'), graded(c)]


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _median(xs):
    xs = sorted(x for x in xs if _num(x))
    return None if not xs else xs[len(xs) // 2] if len(xs) % 2 else 0.5 * (xs[len(xs) // 2 - 1] + xs[len(xs) // 2])


def verdict(rec):
    """the triple's reading -> (verdict, why): see the module's docstring."""
    D, K, F, cur = rec.get('design') or {}, rec.get('known_bad') or {}, rec.get('floor') or {}, rec.get('current') or {}
    if not D.get('moves'):
        return 'unmeasured', 'the design against itself did not run'
    if rec.get('kind') == 'score':
        # an ungraded score: its calibration is its separations (the design's worst move beyond the known-bad, the
        # known-bad beyond the floor), and the current build clear of the floor
        hi = rec.get('better') != 'lower'
        worst = D.get('min') if hi else D.get('max')
        fl = _median([f.get('median') for f in F.values()])
        beyond = lambda a, b: _num(a) and _num(b) and ((a > b) if hi else (a < b))
        if not beyond(worst, K.get('value')):
            return 'blind', "the known-bad %s reads %s, not below the design's worst move %s" % (
                K.get('name'), K.get('value'), worst)
        if not beyond(K.get('value'), fl):
            return 'coarse', 'the floor %s reads as well as the known-bad %s' % (fl, K.get('value'))
        if (cur.get('margin') or 0) < MARGIN:
            return 'coarse', 'the current build sits at the floor (margin %s)' % cur.get('margin')
        return 'calibrated', "a score: the design's worst move %s, the known-bad %s %s, the floor %s, the current %s " \
            "(margin %s)" % (worst, K.get('name'), K.get('value'), fl, cur.get('value'), cur.get('margin'))
    st = [s for _, s in D['moves'].values()]
    if any(s != 'PASS' for s in st):
        bad = [m for m, (_, s) in D['moves'].items() if s != 'PASS']
        return 'miscalibrated', 'the design reads %s moved %s px (%d of %d moves)' % (
            '/'.join(sorted({D['moves'][m][1] or 'none' for m in bad})), ', '.join(bad[:4]), len(bad), len(st))
    if K.get('name') and K.get('status') != 'FAIL':
        return 'blind', 'the known-bad %s reads %s %s' % (K['name'], K.get('value'), K.get('status'))
    moved = [g for g, r in (rec.get('invariant') or {}).items() if any(s != 'PASS' for s in r['statuses'])]
    if moved:
        return 'confounded', 'the check moved under %s (a change it must not see): %s' % (
            moved[0], rec['invariant'][moved[0]]['values'])
    if not K.get('name') and not F:
        # (nothing it must fail: the design passing its own check proves nothing; sleeve_standoff, a 3D measure)
        return 'unmeasured', 'no known-bad (%s) and no random floor: nothing it must fail' % (
            rec.get('no_known_bad') or '?')
    passing = [g for g, f in F.items() if f.get('status') == 'PASS']
    if rec.get('kind') == 'defect':
        # a defect detector: a random stand-in lacks the defect it looks for and may pass; its shape is the guard's
        guard_ = ', '.join(rec.get('shape') or ()) or 'NONE: name one'
        if not K.get('name'):
            return 'guard', 'a defect detector with no known-bad (%s); the design passes; shape guarded by %s' % (
                rec.get('no_known_bad') or '?', guard_)
        return 'calibrated', 'a defect detector: the design passes every move (spread %s), %s reads %s FAIL; a random ' \
            'stand-in %s; shape guarded by %s' % (D.get('spread'), K['name'], K.get('value'),
                                                  'passes it (%s)' % ', '.join(passing) if passing else 'fails it',
                                                  guard_)
    if passing:
        return 'coarse', 'a random baseline passes (%s: %s)' % (passing[0], F[passing[0]].get('median'))
    if cur.get('status') == 'PASS' and cur.get('margin') is not None and cur['margin'] < MARGIN:
        return 'coarse', 'the current build passes at the floor (margin %.2f of the way from the floor to the design)' % \
            cur['margin']
    if not K.get('name'):
        return 'guard', 'no known-bad (%s); the design passes and the floor does not' % (rec.get('no_known_bad') or '?')
    return 'calibrated', 'the design passes every move (spread %s), %s reads %s FAIL, the floor %s' % (
        D.get('spread'), K['name'], K.get('value'), ', '.join('%s %s' % (g, f.get('status')) for g, f in F.items()))


def assess(check, e, cur, bad, design, floors, probes, bad_name=None, invariant=None):
    """one check's record from the part's runs: cur, bad ({check: dict} or None), design {move: checks}, floors
    {generator: [checks per seed]}, probes {generator: checks}."""
    rec = dict(check=check, part=e.get('part'), adapter=e.get('adapter'), module=e.get('module'),
               at=time.strftime('%Y-%m-%dT%H:%M:%S'), better=e.get('better'), kind=e.get('kind', 'shape'),
               shape=e.get('shape'))
    mv = {'%+d,%+d' % m: _vs(C, check) for m, C in design.items()}
    vals = [v for v, _ in mv.values() if _num(v)]
    rec['design'] = dict(moves=mv, min=min(vals) if vals else None, max=max(vals) if vals else None,
                         spread=round(max(vals) - min(vals), 4) if vals else None, median=_median(vals))
    views = {}
    for C in design.values():
        for v, x in ((((C or {}).get(check) or {}).get('views')) or {}).items():
            if _num(x):
                views.setdefault(v, []).append(x)
    if views:
        rec['design']['views'] = {v: [min(xs), max(xs)] for v, xs in sorted(views.items())}
    if bad_name:
        v, s = _vs(bad, check)
        rec['known_bad'] = dict(name=bad_name, value=v, status=s)
    else:
        rec['known_bad'] = dict(name=None)
        rec['no_known_bad'] = e.get('no_known_bad')
    rec['floor'] = {}
    for g, runs in floors.items():
        got = [_vs(C, check) for C in runs]
        vs = [v for v, _ in got if _num(v)]
        med = _median(vs)
        # the floor's status: the status of the seed at the median (a random floor is a distribution: most seeds decide)
        st = [s for _, s in got]
        order = sorted(range(len(got)), key=lambda i: (got[i][0] is None, got[i][0] if _num(got[i][0]) else 0))
        mid = got[order[len(order) // 2]][1] if got else None
        rec['floor'][g] = dict(values=[v for v, _ in got], statuses=st, median=med, status=mid,
                               passing=sum(s == 'PASS' for s in st))
    rec['probes'] = {g: dict(zip(('value', 'status'), _vs(C, check))) for g, C in (probes or {}).items()}
    rec['blind_to'] = sorted(g for g, p in rec['probes'].items() if p['status'] == 'PASS')
    if invariant:
        rec['invariant'] = {g: dict(values=[_vs(C, check)[0] for C in runs], statuses=[_vs(C, check)[1] for C in runs])
                            for g, runs in invariant.items()}
    v, s = _vs(cur, check)
    fl = _median([f['median'] for f in rec['floor'].values()])
    dm = rec['design']['median']
    better = e.get('better') or (('higher' if dm > fl else 'lower') if _num(dm) and _num(fl) and dm != fl else None)
    rec['better'] = better
    margin = None
    if _num(v) and _num(fl) and _num(dm) and dm != fl:
        margin = round((v - fl) / (dm - fl), 3)
    rec['current'] = dict(value=v, status=s, margin=margin)
    rec['verdict'], rec['why'] = verdict(rec)
    if rec['verdict'] in GOOD and rec['kind'] != 'defect' and margin is not None and margin < MARGIN and s != 'PASS':
        rec['note'] = 'the current build sits near the floor and fails the check (an open flag, not a coarse check)'
    return rec


def _evaluate(A, B):
    from . import qa3d
    return qa3d.evaluate(B, parts=(A.part,), design=A.design)


def run_group(module, adapter, es, checks, build, seeds=SEEDS, log=print):
    """the triple for the checks of one adapter (one part): each run of the part serves all of them -> {check: record}."""
    from . import qa3d
    mod = importlib.import_module(module)
    B = load_bundle(build)
    A = getattr(mod, adapter)(B, qa3d.Design(B))
    t0 = time.time()
    log('calibrate: %s.%s on %s (%d checks)' % (module.split('.')[-1], adapter, os.path.relpath(build, ROOT)
                                                if build.startswith(ROOT) else build, len(checks)))
    cur = A.measure(B) if hasattr(A, 'measure') else _evaluate(A, B)

    def once(kind, arg):
        if hasattr(A, 'run'):                   # (an adapter that scores its stand-ins itself: the chin, a truth's score)
            return A.run(kind, arg)
        with A.substitute(kind, arg):
            return _evaluate(A, B)
    bads = {}
    for name in sorted({e.get('known_bad') for e in es if e.get('known_bad')}):
        if hasattr(A, 'measure_known_bad'):
            bads[name] = A.measure_known_bad(name)
            continue
        d, _ = known_bad(name)
        if d is None:
            log('  known-bad %s: not stored here (python -m charkit calibrate store %s BUILD --why ...)' % (name, name))
            bads[name] = None
            continue
        Bk = load_bundle(d)
        Ak = getattr(mod, adapter)(Bk, qa3d.Design(Bk))
        bads[name] = Ak.measure(Bk) if hasattr(Ak, 'measure') else _evaluate(Ak, Bk)
    design = {}
    for m in MOVES:
        design[m] = once('design', m)
    floors, probes = {}, {}
    for g in sorted({g for e in es for g in e.get('baseline') or ()}):
        floors[g] = [once(g, s) for s in range(seeds)]
    for g in sorted({g for e in es for g in e.get('probes') or ()}):
        probes[g] = once(g, 0)
    invs = {g: [once(g, s) for s in range(seeds)] for g in sorted({g for e in es for g in e.get('invariant') or ()})}
    out = {}
    for k in checks:
        e = entry_for(k, es)
        kb = e.get('known_bad')
        if kb and bads.get(kb) is None:
            rec = assess(k, e, cur, None, design, {g: floors[g] for g in e.get('baseline') or ()},
                         {g: probes[g] for g in e.get('probes') or ()})
            rec['verdict'], rec['why'] = 'unmeasured', 'the known-bad %s is not stored on this machine' % kb
        else:
            rec = assess(k, e, cur, bads.get(kb) if kb else None, design,
                         {g: floors[g] for g in e.get('baseline') or ()}, {g: probes[g] for g in e.get('probes') or ()},
                         bad_name=kb, invariant={g: invs[g] for g in e.get('invariant') or ()})
        rec['build'] = os.path.relpath(build, ROOT) if build.startswith(ROOT) else build
        rec['generators'] = {g: A.generators.get(g) for g in list(e.get('baseline') or ()) + list(e.get('probes') or ())
                             + list(e.get('invariant') or ())}
        rec['seconds'] = round(time.time() - t0, 1)
        out[k] = rec
    return out


def calibrate(patterns, build=None, seeds=SEEDS, write=True, log=print):
    """the triple for every check matching patterns that the registry covers and the current build (or the part's
    runs) has -> {check: record}; records written to charkit/calib/records unless write is False."""
    from . import qa3d
    build = build or current_build()
    if not build:
        raise SystemExit('calibrate: no build (--build DIR, or a build of the integration head under '
                         'charkit/out/calib/cur_*)')
    E = entries()
    groups = {}
    q = os.path.join(build, 'qa', 'qa.json')
    Q = json.load(open(q)) if os.path.exists(q) else {}
    names = set(Q.get('checks', {}))
    owned = ((Q.get('measured') or {}).get('part_checks')) or {}
    drafts = set()
    try:                        # (a declared check not in the build's qa.json yet: a draft, CHARKIT_DECLARED's)
        from . import declared
        drafts = {n for n, _, _ in declared.expand(declared.declarations())} - names
        names |= drafts
    except Exception:
        pass
    for e in E:
        got = [k for k in names if fnmatch.fnmatchcase(k, e['check']) and any(fnmatch.fnmatchcase(k, p) for p in patterns)
               and (not owned.get(e.get('part')) or k in owned[e['part']] or k in drafts)]
        if not got and any(fnmatch.fnmatchcase(e['check'], p) or e['check'] == p for p in patterns) and \
                not any(c in e['check'] for c in '*?['):
            got = [e['check']]                  # (a scorer, not a qa.json check: its adapter measures it)
        for k in got:
            if entry_for(k, E) is e:
                groups.setdefault((e['module'], e['adapter']), ([], []))
                groups[(e['module'], e['adapter'])][0].append(e)
                groups[(e['module'], e['adapter'])][1].append(k)
    if not groups:
        raise SystemExit('calibrate: no registered check matches %s (python -m charkit calibrate list)' %
                         ', '.join(patterns))
    out = {}
    for (module, adapter), (es, ks) in sorted(groups.items()):
        es = [dict(t) for t in {json.dumps(x, sort_keys=True): x for x in es}.values()]
        out.update(run_group(module, adapter, es, sorted(set(ks)), build, seeds, log))
    if write:
        os.makedirs(os.path.join(ROOT, RECORDS), exist_ok=True)
        for k, r in out.items():
            _write_json(os.path.join(ROOT, RECORDS, k + '.json'), r)
    return out


def line(r):
    """one record as a line."""
    D, K, C = r.get('design') or {}, r.get('known_bad') or {}, r.get('current') or {}
    fl = '; '.join('%s %s %s' % (g, _f(f.get('median')), f.get('status')) for g, f in (r.get('floor') or {}).items())
    pr = '; '.join('%s %s %s' % (g, _f(p.get('value')), p.get('status')) for g, p in (r.get('probes') or {}).items())
    return '%-24s %-13s design %s..%s (spread %s) | known-bad %s %s %s | floor %s | current %s %s (margin %s)%s' % (
        r['check'], r['verdict'].upper(), _f(D.get('min')), _f(D.get('max')), _f(D.get('spread')), K.get('name') or '-',
        _f(K.get('value')), K.get('status') or '', fl or '-', _f(C.get('value')), C.get('status') or '',
        C.get('margin'), (' | probes ' + pr) if pr else '')


def _f(x):
    return ('%.4g' % x) if _num(x) else str(x)


# ------------------------------------------------------------------------------------------------ the gate's readings
def requirements(tree, base_tree, qa_a, qa_b, rep):
    """what the gate asks of the calibration records (Michael's rule: new checks ship calibrated, remeasures are
    recalibrated): every graded check the merge adds needs a record in the merged tree; every graded check it remeasures
    (a registered measurement step, or a measure the gate found changed with none) needs a record the merge adds or
    changes; a record whose verdict isn't calibrated (or guard) doesn't pass. tree: the merged tree (a directory);
    base_tree: the integration head ((repo, rev)). -> {'rows': [dict(check, why ('new'|'remeasured'), record
    ('missing'|'stale'|verdict), ok)], 'records': n}."""
    R, R0 = records(tree), records(base_tree)
    ca, cb = (qa_a or {}).get('checks', {}), (qa_b or {}).get('checks', {})
    rows = []
    stepped = set()
    for r in rep.get('qa') or ():
        if r['verdict'] == 'remeasured':
            stepped.add(r['check'])
    for r in (rep.get('twobytwo') or {}).get('rows') or ():
        stepped.add(r['check'])
    stepped |= set(((rep.get('unregistered') or {}).get('checks')) or ())
    for k in sorted(set(cb) - set(ca)):
        if cb[k].get('status') in RANK:
            stepped.discard(k)
            rows.append(dict(check=k, why='new', **_state(k, R, None)))
    for k in sorted(stepped):
        if k in cb and k in ca and cb[k].get('status') in RANK:
            rows.append(dict(check=k, why='remeasured', **_state(k, R, R0)))
        elif k in cb and k not in ca:
            pass
    return {'rows': rows, 'records': len(R)}


def _state(k, R, R0):
    r = R.get(k)
    if r is None:
        return dict(record='missing', ok=False)
    if R0 is not None and R0.get(k) == r:
        return dict(record='stale', ok=False, verdict=r.get('verdict'), at=r.get('at'))
    return dict(record=r.get('verdict'), ok=r.get('verdict') in GOOD, why_record=r.get('why'), at=r.get('at'))


def improvements(rep, qa_a, qa_b, is_flag):
    """the checks a merge improves that are its own new checks or Michael's flag checks -> [dict(check, how, from, to)]:
    a flag check whose status gets better, or whose value moves toward the design (its record's `better`); a check the
    merge adds or remeasures that reads better on the new geometry than the old under its new measure (the 2x2); a
    check it adds with no old-geometry reading that doesn't FAIL (counted: the guard can't see it wasn't gamed)."""
    out, seen = [], set()
    for r in (rep.get('twobytwo') or {}).get('rows') or ():
        a, b = r.get('new_on_old'), r.get('cand')
        if a and b:
            seen.add(r['check'])                # (it has an old-geometry reading: improved or not, that decides)
            if _better(r['check'], a, b, None):
                out.append(dict(check=r['check'], how='the new measure on both geometries', **{'from': a, 'to': b}))
    R = None
    for r in rep.get('qa') or ():
        k = r['check']
        if k in seen:
            continue
        if r['verdict'] == 'new' and (r.get('cand') or [None, None])[1] in ('PASS', 'WARN'):
            out.append(dict(check=k, how='new, with no old-geometry reading', **{'from': None, 'to': r['cand']}))
        elif is_flag(k) and r['verdict'] in ('improved', 'value'):
            if R is None:
                R = records()
            if r['verdict'] == 'improved' or _better(k, r['base'], r['cand'], (R.get(k) or {}).get('better')):
                out.append(dict(check=k, how='a flag check', **{'from': r['base'], 'to': r['cand']}))
    return out


def _better(k, a, b, better):
    (va, sa), (vb, sb) = a, b
    if sa in RANK and sb in RANK and sa != sb:
        return RANK[sb] < RANK[sa]
    if better and _num(va) and _num(vb) and va != vb:
        return (vb > va) == (better == 'higher')
    return False


SHAPE_FLOOR = 0.5       # a view where the design itself, moved 1-2 px, reads under this isn't a shape the guard can read


def guard(rep, qa_a, qa_b, is_flag, E=None, drop=DROP, R=None):
    """the anti-gaming guard (Michael, 2026-09-30): a merge that improves its own new or flag check while that check's
    piece's shape IoU (its registry `shape`: piece_<id>'s per-view values) drops by more than drop in any view ->
    [dict(check, how, from, to, shape, view, base, cand, rel)], one per offending view (the tool/bow merge: the ribbons
    passed bow_profile_ribbon by swinging forward as flat blades while piece_bow's profile fell 0.52 -> 0.34). A view
    the shape check's own calibration record (R: records) shows the design can't score (its worst move under
    SHAPE_FLOOR: piece_collar's profile reads 0.09-0.12 on the design itself) is left out."""
    E = entries() if E is None else E
    R = records() if R is None else R
    ca, cb = (qa_a or {}).get('checks', {}), (qa_b or {}).get('checks', {})
    out = []
    for imp in improvements(rep, qa_a, qa_b, is_flag):
        for s in shapes_of(imp['check'], E, (qa_a, qa_b)):
            va, vb = (ca.get(s) or {}).get('views') or {}, (cb.get(s) or {}).get('views') or {}
            dv = (((R.get(s) or {}).get('design') or {}).get('views')) or {}
            for view in sorted(set(va) & set(vb)):
                x, y = va[view], vb[view]
                if dv.get(view) and _num(dv[view][0]) and dv[view][0] < SHAPE_FLOOR:
                    continue
                if _num(x) and _num(y) and x > 0.05 and (x - y) / x > drop:
                    out.append(dict(imp, shape=s, view=view, base=x, cand=y, rel=round((y - x) / x, 3)))
    return out


def shape_report(rep, qa_a, qa_b, E=None):
    """every improved or new check's pieces' shape IoU in all views, before and after (the guard's evidence; reported
    whether it blocks or not) -> [dict(check, shape, views {view: [base, cand]})]."""
    E = entries() if E is None else E
    ca, cb = (qa_a or {}).get('checks', {}), (qa_b or {}).get('checks', {})
    out, done = [], set()
    for r in rep.get('qa') or ():
        if r['verdict'] not in ('new', 'improved', 'remeasured'):
            continue
        for s in shapes_of(r['check'], E, (qa_a, qa_b)):
            if (r['check'], s) in done:
                continue
            done.add((r['check'], s))
            va, vb = (ca.get(s) or {}).get('views') or {}, (cb.get(s) or {}).get('views') or {}
            if va or vb:
                out.append(dict(check=r['check'], shape=s, views={v: [va.get(v), vb.get(v)] for v in sorted(set(va) |
                                                                                                    set(vb))}))
    return out


# ------------------------------------------------------------------------------------------------ Michael's acceptances
def accept(check, by, why, value=None, status='FAIL', branch=None, recorded_by='coordinator', root=ROOT):
    """record Michael's acceptance of a named new FAIL (or a guard block on it): who decided, when and why, into
    charkit/accepted/CHECK.json (commit it on the branch; the gate reads the merged tree's and reports it; git keeps the
    history). Only the coordinator records one, on Michael's call. -> the record."""
    if not (by and why):
        raise SystemExit('accept: --by (whose call) and --why are required')
    rec = dict(check=check, status=status, value=value, by=by, why=why, at=time.strftime('%Y-%m-%dT%H:%M:%S'),
               branch=branch, recorded_by=recorded_by)
    d = os.path.join(root, ACCEPTED)
    os.makedirs(d, exist_ok=True)
    json.dump(rec, open(os.path.join(d, check + '.json'), 'w'), indent=1)
    return rec


def covers(rec, branch=None):
    """does an acceptance record cover this gate (its branch, when it names one)?"""
    return bool(rec) and (not rec.get('branch') or not branch or rec['branch'] == branch)


# ------------------------------------------------------------------------------------------------------------ the CLI
def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return 0
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    if args[0] == 'store':
        d, rec = store(args[1], args[2], why=opt('--why') or '', commit=opt('--commit'), flag=opt('--flag'))
        print('stored %s: %s (%s)' % (args[1], os.path.relpath(d, ROOT), rec['why']))
        return 0
    if args[0] == 'list':
        pat = args[1] if len(args) > 1 else '*'
        R = records()
        for e in entries():
            if fnmatch.fnmatchcase(e['check'], pat) or pat == '*':
                got = sorted(k for k in R if fnmatch.fnmatchcase(k, e['check']))
                print('%-26s %-14s %-22s known-bad %-14s floor %s%s' % (
                    e['check'], e.get('part'), e['module'].split('.')[-1] + '.' + e.get('adapter', ''),
                    e.get('known_bad') or '-', ','.join(e.get('baseline') or ()),
                    '  records: ' + ', '.join('%s %s' % (k, R[k].get('verdict')) for k in got) if got else ''))
        return 0
    if args[0] == 'show':
        r = records().get(args[1])
        print(json.dumps(r, indent=1) if r else 'no record for %s' % args[1])
        return 0
    pats = [p for p in args[0].split(',') if p]
    if opt('--declared'):
        from . import declared
        os.environ[declared.ENV] = os.path.abspath(opt('--declared'))
    out = calibrate(pats, build=opt('--build'), seeds=int(opt('--seeds', SEEDS)), write='--no-write' not in args)
    for k in sorted(out):
        print(line(out[k]))
        print('    ' + out[k]['why'])
    if opt('--json'):
        json.dump(out, open(opt('--json'), 'w'), indent=1, default=str)
    return 0 if all(r['verdict'] in GOOD for r in out.values()) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
