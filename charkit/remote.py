"""Builds off the laptop, on the CPU build box (infra/gcp/build.sh; its config infra/gcp/build.env is gitignored): the
same charkit commands, run in a copy of this worktree there (rsync through IAP, only what changed), their outputs
fetched back. The laptop keeps one build slot (`python -m charkit slots 1`); the box has its own.

    python -m charkit remote build SPEC [build args]     sync, build there, fetch its --out
    python -m charkit remote tune SPEC [tune args]       sync, tune there, fetch its --out
    python -m charkit remote gate BRANCH --into BASE [--spec SPEC] [--args ARGS] [--accept PATTERN,...] [--build]
                              [--code REF] [--keep-older]
                                                         the gate there, in a clone kept current by git bundles, its
                                                         report fetched into charkit/out/gate (SPEC a path on the box).
                                                         It stops the branch's older gate still running (same spec;
                                                         --keep-older doesn't). --code REF: the gate's own code from REF,
                                                         not BASE's (to try a change to the gate itself)
    python -m charkit remote run [--fetch DIR] CMD...    anything, in the synced copy (DIR fetched back when it ends)
    python -m charkit remote jobs [--days N] [--silences] every box's jobs: running, finished (N days, default 1), lost.
                                                         A running job with no output for its limit (20 min; a gate 45,
                                                         a pregate 30: charkit/boxjob.py STALL_MIN) is flagged SILENT, one
                                                         past 2x the duration it declared OVERRUN; nothing is stopped.
                                                         --silences: each kind's longest silences (N days, default 7)
    python -m charkit remote build|tune|gate|pregate [--expect MIN] [--stall MIN] ...,  remote run [--fetch DIR]
                              [--expect MIN] [--stall MIN] CMD...
                                                         the job declares the minutes it expects (flagged past 2x) and
                                                         its own silence limit (or CHARKIT_JOB_EXPECT_MIN, _STALL_MIN)
    python -m charkit remote attach JID                  follow a job again (its log from the start) and collect its outputs
    python -m charkit remote kill JID                    stop a job on its box (its processes only)
    python -m charkit remote load [--hours N] [--fresh] [--json]
                                                         each box's utilisation, slot waits and peak load (charkit/boxload.py)
    python -m charkit remote up | status | stop
    python -m charkit remote --box render build SPEC --boards views,body ...   # the GPU box (infra/gcp/render.env): boards render

Builds, tunes, runs and gates run on the box as detached jobs (charkit/boxjob.py): the box runs the job under a
supervisor no ssh session owns, and this command follows its log. A dropped connection drops only the follow: it
reattaches by itself at the byte it had reached, with backoff, and never runs the job again. The job's exit code is this
command's. If this command itself dies, the job goes on: `remote attach JID` (the id is printed at the start, and kept in
charkit/out/remote/jobs/) follows it again and collects its outputs. CHARKIT_DETACH=0 runs a job inside the ssh session
as before.
"""
import json, os, re, shlex, subprocess, sys, threading, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_SH = os.path.join(ROOT, 'infra', 'gcp', 'build.sh')
BOX = {'env': os.path.join(ROOT, 'infra', 'gcp', 'build.env')}   # which box: --box NAME reads infra/gcp/NAME.env
BOX_SLOTS = 8                     # concurrent builds on the box (32 vCPU, 128 GB)
JOBS_BOX = '/srv/work/.jobs'      # the box's job directories (charkit/boxjob.py)
JOBS_HERE = os.path.join(ROOT, 'charkit', 'out', 'remote', 'jobs')   # this worktree's record of the jobs it sent
SSH_FAIL = 255                    # ssh's own failure (a dropped or refused connection), not the remote command's
WATCHDOG = 75                     # s without a frame (the box sends a heartbeat every 15 s): the follow is dead
GIVE_UP = 45 * 60                 # s of failed reattaches in a row before this command stops waiting (the job goes on)


def _detach():
    return os.environ.get('CHARKIT_DETACH', '1') != '0'


def _sh(*args, check=True, capture=False, input=None, retry=False):
    """build.sh ARGS. retry: rerun while it fails as ssh itself fails (exit 255: a dropped or refused connection),
    for the steps that are safe to repeat (sync, push, pull, an idempotent ssh)."""
    waits = [5, 15, 30, 60] if retry else []
    for i in range(len(waits) + 1):
        r = subprocess.run([BUILD_SH, *args], text=True, capture_output=capture, input=input,
                           env=dict(os.environ, CHARKIT_BOX_ENV=BOX['env']))
        if r.returncode != SSH_FAIL or i == len(waits):
            break
        print('remote: %s: the connection failed (ssh exit 255); retrying in %d s' % (args[0], waits[i]),
              file=sys.stderr, flush=True)
        time.sleep(waits[i])
    if check and r.returncode:
        raise subprocess.CalledProcessError(r.returncode, [BUILD_SH, *args], r.stdout, r.stderr)
    return r.stdout if capture else r.returncode


def _bucket():
    """bulk data goes through the box's bucket (charkit/bucketsync.py), unless CHARKIT_SYNC=rsync (the IAP tunnel)."""
    return os.environ.get('CHARKIT_SYNC', 'bucket') != 'rsync' and bool(_env('BUCKET'))


def _rel(a):
    """a path under this worktree as relative (the box's copy has the same layout under another root)."""
    if isinstance(a, str) and os.path.isabs(a) and a.startswith(ROOT + os.sep):
        return os.path.relpath(a, ROOT)
    return a


def _portable_spec(path):
    """a spec with every absolute path under this worktree made relative, written beside the build's outputs."""
    s = open(os.path.join(ROOT, path) if not os.path.isabs(path) else path).read()
    s = s.replace(ROOT + os.sep, '')
    out = os.path.join(ROOT, 'charkit', 'out', 'remote')
    os.makedirs(out, exist_ok=True)
    p = os.path.join(out, os.path.basename(path))
    open(p, 'w').write(s)
    return os.path.relpath(p, ROOT)


def _opt(args, k, d=None):
    return args[args.index(k) + 1] if k in args else d


def up():
    """the box started if stopped, and kept awake: its idle stop honours /srv/work/.keepalive for two hours (a long upload
    to the box otherwise looks idle there, and the box stopped under a seed's transfer)."""
    preflight()
    _sh('up')
    _sh('ssh', 'touch /srv/work/.keepalive', check=False, retry=True)


def seed():
    """a box with no copy of any worktree yet (the render box's first sync) gets this one through the bucket: a tarball
    of its tracked files, rather than ~0.3 GB through the IAP tunnel; rsync then sends what differs.
    The bucket sync needs no seed: the box fetches the blobs it lacks from the bucket itself."""
    if _bucket():
        return
    name = os.path.basename(ROOT)
    have = _sh('ssh', 'ls -d /srv/work/*/charkit 2>/dev/null | head -1; true', capture=True, check=False).strip()
    if have:
        return
    import tarfile, tempfile
    tmp = os.path.join(tempfile.mkdtemp(), 'seed-%s.tar' % name)
    files = subprocess.run(['git', '-C', ROOT, 'ls-files'], capture_output=True, text=True, check=True).stdout.split()
    with tarfile.open(tmp, 'w') as tf:
        for f in files:
            if os.path.isfile(os.path.join(ROOT, f)):
                tf.add(os.path.join(ROOT, f), arcname=f)
    put(tmp, '/srv/work/.seed.tar')
    _sh('ssh', 'mkdir -p /srv/work/%s && tar -xf /srv/work/.seed.tar -C /srv/work/%s && rm -f /srv/work/.seed.tar'
        % (name, name))
    os.remove(tmp)


def _publisher():
    """(the shell that saves bucketsync.py on the box from the ssh's stdin, the command that runs it, its source) for a
    job inside the ssh session; a detached job has its own copy in its job directory."""
    from charkit import bucketsync
    if _detach():
        return '', 'BS_ROLE=box BUCKET=%s python3 "$BOXJOB_DIR/bucketsync.py"' % shlex.quote(_env('BUCKET')), None
    install, runner, script = bucketsync.box_install(_env('BUCKET'))
    return install, runner, script.decode()


def charkit(cmd, publish=None, collect=None):
    """a charkit command in the box's copy of this worktree (synced first), as a detached job. publish=(PATH, NAME): PATH
    in the copy is published to the bucket under NAME when it ends (charkit/bucketsync.py), for `build.sh pull`.
    collect: what `remote attach` does with a finished job (kept in the job's local record)."""
    cmd = _take_job_opts(cmd)
    up()
    seed()
    _sh('sync', ROOT, retry=True)
    line = 'python -m charkit slots %d >/dev/null && python -m charkit %s' % (_slots(), ' '.join(shlex.quote(c) for c in cmd))
    script, install = None, ''
    if publish and _bucket():
        install, runner, script = _publisher()
        line = '{ %s; rc=$?; %s publish %s --name %s >/dev/null 2>&1; exit $rc; }' % (
            line, runner, shlex.quote(publish[0]), shlex.quote(publish[1]))
    if not _detach():
        return _sh('run', ROOT, (install + ' && ' if install else '') + line, check=False, input=script)
    run = 'source /opt/anim-build/env && cd /srv/work/%s && %s' % (shlex.quote(os.path.basename(ROOT)), line)
    return job(cmd[0], run, ' '.join(cmd[:2]), collect=collect)


def build(args, kind='build'):
    """remote build or tune: the spec made portable, the command run there, its --out fetched."""
    args = _take_job_opts(args)
    spec = _portable_spec(args[0])
    rest = [_rel(a) for a in args[1:]]
    name = json.load(open(os.path.join(ROOT, spec))).get('name', 'char')
    out = _opt(rest, '--out', 'charkit/out/%s' % name)
    import uuid
    pub = 'build-%s-%s' % (re.sub(r'[^A-Za-z0-9._-]', '_', os.path.basename(ROOT)), uuid.uuid4().hex[:8])
    what = dict(pull=pub, to=out, fetch=out)
    code = charkit([kind, spec] + rest, publish=(out, pub), collect=what)
    if code == STILL_RUNNING:
        return code
    collect(what)
    print('remote %s: exit %d, %s fetched' % (kind, code, out))
    return code


def collect(what):
    """a finished job's outputs: pulled from the bucket (the job published them when it ended), else fetched through the
    box (it publishes the directory then). what: pull (the published name), to (here, relative to ROOT), fetch (the
    worktree-relative directory on the box, for the fallback) or gate (the gate's id: its report from /srv/work/_gate)."""
    to = os.path.join(ROOT, what['to'])
    if _bucket() and what.get('pull') and _sh('pull', what['pull'], to, check=False, retry=True) == 0:
        return 0
    if what.get('fetch'):
        return _sh('fetch', ROOT, what['fetch'], check=False, retry=True)
    if what.get('gate'):
        return subprocess.run(['rsync', '-az', '-e', 'ssh -F %s' % _cfg()[0], '%s:/srv/work/_gate/%s/' % (
            _env('VM'), what['gate']), to + '/'], check=False).returncode
    return 1


def gate(args):
    """the gate on the box, run in parallel with other workstreams' gates. A git bundle of what the box's clone
    (/srv/work/repo) lacks is fetched into it under a short lock, into refs of this gate's own, and the gate gets a clone
    of its own (git clone --shared: the objects are the clone's, the refs, checkout and inputs are this gate's), where
    `charkit gate` runs with the exact commits named here. Gates into one commit share its baseline through
    /srv/work/gate-out (gate.py builds each baseline once, under a lock of its own), and the box's build slots bound how
    many builds run at once. Only this gate's report comes back. The old way held one lock for the whole gate, so gates
    queued for hours on a box two-thirds idle (2026-09-29)."""
    import uuid
    args = _take_job_opts(args)
    branch, into = args[0], _opt(args, '--into', 'pipeline-3d')
    gate_code = _opt(args, '--code')
    tag = re.sub(r'[^A-Za-z0-9._-]', '_', branch)
    gid = '%s-%s' % (tag, uuid.uuid4().hex[:8])
    bundle = os.path.join(ROOT, 'charkit', 'out', 'remote', 'repo-%s.bundle' % gid)
    boxed = '/srv/work/repo-%s.bundle' % gid
    G = '/srv/work/gates/%s' % gid
    os.makedirs(os.path.dirname(bundle), exist_ok=True)
    up()
    # only what the box's clone lacks: its refs' commits (known here, since they came from here) are left out
    # (a failed ssh here must not read as "the box has nothing": that bundle would be the whole history, 1.8 GB)
    have = _sh('ssh', 'git -C /srv/work/repo for-each-ref --format="%(objectname)" 2>/dev/null; true', capture=True,
               retry=True).split()
    known = sorted({c for c in have if subprocess.run(['git', '-C', ROOT, 'cat-file', '-e', c + '^{commit}'],
                                                      capture_output=True).returncode == 0})
    r = subprocess.run(['git', '-C', ROOT, 'bundle', 'create', bundle, into, branch] + ([gate_code] if gate_code else []) +
                       ['^' + c for c in known], capture_output=True, text=True)
    if r.returncode != 0 and 'empty bundle' not in r.stderr:
        raise SystemExit(r.stderr)
    if r.returncode == 0:
        put(bundle, boxed)
        os.remove(bundle)
    # (no generated inputs to send: charkit/out/i3d, TRELLIS's output, was the only one, and no build reads it since
    # the sheet-only outfit masks, decision 8)
    sha = {b: subprocess.run(['git', '-C', ROOT, 'rev-parse', b], capture_output=True, text=True, check=True).stdout.strip()
           for b in (into, branch) + ((gate_code,) if gate_code else ())}
    q = shlex.quote
    install, publish, script = '', '', None
    if _bucket():                               # the report goes back through the bucket (charkit/bucketsync.py)
        install, runner, script = _publisher()
        publish = '%s publish /srv/work/_gate/%s --name gate-%s >/dev/null 2>&1; ' % (runner, gid, gid)
    fetch = ('cd /srv/work && ( [ -d repo/.git ] || git clone -q %(b)s repo ) && '
             '{ [ ! -f %(b)s ] || git -C repo fetch -q -f %(b)s "refs/heads/*:refs/gates/%(gid)s/*"; } && rm -f %(b)s && '
             'git clone -q --shared --no-checkout /srv/work/repo %(G)s'
             % dict(b=boxed, gid=gid, G=G))
    more = ''.join(' %s %s' % (k, q(_opt(args, k))) for k in ('--spec', '--args', '--accept') if k in args)
    more += ' --build' if '--build' in args else ''
    # a killed gate (remote kill: SIGTERM to its processes) still removes its clone, its inputs and its temporary
    # files (its worktrees and the builds' scratch live under G.tmp)
    step = ('rc=1; cleanup() { cd /srv/work && rm -rf %(G)s %(G)s.log %(G)s.tmp; }; '
            'trap "cleanup; exit 143" TERM INT HUP; '
            'mkdir -p %(G)s.tmp && export TMPDIR=%(G)s.tmp && '
            'flock /srv/work/.gate-fetch.lock bash -c %(fetch)s && cd %(G)s && '
            'git config user.name charkit-gate && git config user.email gate@localhost && '
            'git sparse-checkout set --cone charkit && '
            'git update-ref refs/heads/%(into)s %(si)s && git update-ref refs/heads/%(branch)s %(sb)s && '
            'git checkout -q -f %(checkout)s && mkdir -p charkit/out /srv/work/gate-out /srv/work/_gate/%(gid)s && '
            'ln -s /srv/work/gate-out charkit/out/gate && '
            'python -m charkit slots %(slots)d >/dev/null && '
            '{ python -m charkit gate %(branch)s --into %(into)s%(more)s 2>&1 | tee %(G)s.log; rc=${PIPESTATUS[0]}; } ; '
            'for r in $(sed -n "s/^report //p" %(G)s.log); do cp "${r%%.md}.md" "${r%%.md}.json" /srv/work/_gate/%(gid)s/ '
            '2>/dev/null; cp "${r%%.md}.summary.json" /srv/work/_gate/%(gid)s/ 2>/dev/null; done; %(publish)scleanup; '
            'find /srv/work/gate-out -maxdepth 1 -name "cand_*" -mtime +3 -exec rm -rf {} + 2>/dev/null; exit $rc'
            % dict(fetch=q(fetch), G=G, gid=gid, into=q(into), branch=q(branch), si=sha[into], sb=sha[branch],
                   slots=_slots(), more=more, publish=publish, checkout=sha[gate_code] if gate_code else q(into)))
    # with the box's environment, not in this worktree's synced copy (a worktree that has only ever gated has none)
    # (the report comes back into this gate's own folder, keyed by its id, and only a report of this branch at this
    # sha into this head is taken from it: never "the newest report" in charkit/out/gate)
    what = dict(pull='gate-' + gid, to=os.path.join(GATES_HERE, gid), gate=gid,
                report=dict(branch=branch, tip=sha[branch], head=sha[into], into=into),
                reports=os.path.join('charkit', 'out', 'gate'))
    label = '%s into %s%s' % (branch, into, more) + (' (gate code %s)' % gate_code if gate_code else '')
    if '--keep-older' not in args:
        supersede(branch, _opt(args, '--spec'))
    if _detach():
        code = job('gate', 'source /opt/anim-build/env && bash -c %s' % q(step), label, collect=what)
        if code == STILL_RUNNING:
            return code
    else:
        code = _sh('ssh', '%ssource /opt/anim-build/env && bash -c %s' % (install and install + '; ', q(step)),
                   check=False, input=script)
    # the report was published to the bucket when the gate ended: no second connection through the tunnel
    collect(what)
    return gate_result(what, code)


GATES_HERE = os.path.join('charkit', 'out', 'remote', 'gates')   # each gate's report as it came back, by the gate's id
PREGATES_HERE = os.path.join('charkit', 'out', 'pregate')


def pregate(args):
    """`pregate --box [NAME | auto]` (Michael's rule, 2026-10-01: the pre-gate's body evaluator is too heavy for the
    shared laptop): the pre-gate of this branch's committed tip merged into BASE, run on a box. As `remote gate`
    does: a git bundle of what the box's clone (/srv/work/repo) lacks, fetched into refs of this run's own under the
    gates' fetch lock, a shared clone of its own where `charkit pregate --pair BRANCH --into BASE` runs (a box's copy of
    the worktree has no .git); the target's baseline is kept per commit in /srv/work/pregate-out (shared by the box's
    pre-gates), the gates' reports are read from /srv/work/gate-out (pregate.gate_names), and the report comes back
    through the bucket into charkit/out/pregate. Uncommitted edits aren't seen: commit first."""
    import uuid
    args = _take_job_opts(args)
    into = _opt(args, '--into', 'pipeline-3d')
    branch = subprocess.run(['git', '-C', ROOT, 'rev-parse', '--abbrev-ref', 'HEAD'], capture_output=True, text=True,
                            check=True).stdout.strip()
    dirty = subprocess.run(['git', '-C', ROOT, 'status', '--porcelain', '--', 'charkit'], capture_output=True,
                           text=True).stdout.strip()
    if dirty:
        print('remote pregate: uncommitted edits under charkit/ are not sent (the box runs the committed tip)')
    tag = re.sub(r'[^A-Za-z0-9._-]', '_', branch)
    gid = 'pregate-%s-%s' % (tag, uuid.uuid4().hex[:8])
    bundle = os.path.join(ROOT, 'charkit', 'out', 'remote', 'repo-%s.bundle' % gid)
    boxed = '/srv/work/repo-%s.bundle' % gid
    G = '/srv/work/pregates/%s' % gid
    os.makedirs(os.path.dirname(bundle), exist_ok=True)
    up()
    have = _sh('ssh', 'git -C /srv/work/repo for-each-ref --format="%(objectname)" 2>/dev/null; true', capture=True,
               retry=True).split()
    known = sorted({c for c in have if subprocess.run(['git', '-C', ROOT, 'cat-file', '-e', c + '^{commit}'],
                                                      capture_output=True).returncode == 0})
    r = subprocess.run(['git', '-C', ROOT, 'bundle', 'create', bundle, into, branch] + ['^' + c for c in known],
                       capture_output=True, text=True)
    if r.returncode != 0 and 'empty bundle' not in r.stderr:
        raise SystemExit(r.stderr)
    if r.returncode == 0:
        put(bundle, boxed)
        os.remove(bundle)
    sha = {b: subprocess.run(['git', '-C', ROOT, 'rev-parse', b], capture_output=True, text=True, check=True
                             ).stdout.strip() for b in (into, branch)}
    q = shlex.quote
    install, publish, script = '', '', None
    if _bucket():
        install, runner, script = _publisher()
        publish = '%s publish /srv/work/_pregate/%s --name %s >/dev/null 2>&1; ' % (runner, gid, gid)
    fetch = ('cd /srv/work && ( [ -d repo/.git ] || git clone -q %(b)s repo ) && '
             '{ [ ! -f %(b)s ] || git -C repo fetch -q -f %(b)s "refs/heads/*:refs/pregates/%(gid)s/*"; } && '
             'rm -f %(b)s && git clone -q --shared --no-checkout /srv/work/repo %(G)s' % dict(b=boxed, gid=gid, G=G))
    more = ''.join(' %s %s' % (k, q(_opt(args, k))) for k in ('--spec',) if k in args)
    step = ('rc=1; cleanup() { cd /srv/work && rm -rf %(G)s %(G)s.log %(G)s.tmp; }; '
            'trap "cleanup; exit 143" TERM INT HUP; '
            'mkdir -p /srv/work/pregates %(G)s.tmp && export TMPDIR=%(G)s.tmp && '
            'flock /srv/work/.gate-fetch.lock bash -c %(fetch)s && cd %(G)s && '
            'git config user.name charkit-pregate && git config user.email pregate@localhost && '
            'git sparse-checkout set --cone charkit && '
            'git update-ref refs/heads/%(into)s %(si)s && git update-ref refs/heads/%(branch)s %(sb)s && '
            'git checkout -q -f %(into)s && mkdir -p charkit/out /srv/work/gate-out /srv/work/pregate-out '
            '/srv/work/_pregate/%(gid)s && ln -s /srv/work/gate-out charkit/out/gate && '
            'ln -s /srv/work/pregate-out charkit/out/pregate && '
            'python -m charkit slots %(slots)d >/dev/null && '
            '{ python -m charkit pregate --pair %(branch)s --into %(into)s%(more)s 2>&1 | tee %(G)s.log; '
            'rc=${PIPESTATUS[0]}; } ; '
            'for r in $(sed -n "s/.*; report //p" %(G)s.log); do cp "${r%%.md}.md" "${r%%.md}.json" '
            '/srv/work/_pregate/%(gid)s/ 2>/dev/null; done; %(publish)scleanup; exit $rc'
            % dict(fetch=q(fetch), G=G, gid=gid, into=q(into), branch=q(branch), si=sha[into], sb=sha[branch],
                   slots=_slots(), more=more, publish=publish))
    what = dict(pull=gid, to=PREGATES_HERE)
    label = 'pregate %s into %s' % (branch, into)
    if _detach():
        code = job('pregate', 'source /opt/anim-build/env && bash -c %s' % q(step), label, collect=what)
        if code == STILL_RUNNING:
            return code
    else:
        code = _sh('ssh', '%ssource /opt/anim-build/env && bash -c %s' % (install and install + '; ', q(step)),
                   check=False, input=script)
    collect(what)
    print('remote pregate: exit %s; reports in %s' % (code, os.path.join(ROOT, PREGATES_HERE)))
    return code


PREFER = 'build'               # pick_box: the build box while it has room; the render boxes take the overflow
MIN_FREE = 4                   # ... room: at least this many free slots beyond the reserve


def pick_box(reserve=1, log=print):
    """`--box auto` (sweep optimize, pregate): every running box's free slots (box_slots), the build box when it has
    MIN_FREE beyond the reserve, else the box with the most free (overflow rather than wait) -> (name, readings)."""
    got = []
    for env in _boxes():
        try:
            got.append(box_slots(env))
        except Exception as e:                      # (a box we can't read is skipped)
            got.append(dict(name=os.path.basename(env)[:-4], status='unreadable', why=str(e)[:200]))
    for g in got:
        log('box %-8s %s' % (g['name'], '%d of %d slots free (%d held, %d waiting)' % (
            g['free'], g['count'], g['held'], g['waiting']) if 'free' in g else g['status']))
    up_ = [g for g in got if 'free' in g]
    if not up_:
        raise SystemExit('--box auto: no running box could be read')
    pref = next((g for g in up_ if g['name'] == PREFER), None)
    if pref and pref['free'] - reserve >= MIN_FREE:
        return pref['name'], got
    return max(up_, key=lambda g: (g['free'], g['name'] == PREFER))['name'], got


def gate_report(folder, branch, tip, head):
    """the report in a gate's own folder (its collected files) of branch at tip into head (shas: a prefix of either
    side matches) -> the .md's path, or None. Never another gate's: the folder is this gate's, and its json must say
    this branch and these commits."""
    import glob
    same = lambda a, b: bool(a and b) and (a.startswith(b) or b.startswith(a))
    for j in sorted(glob.glob(os.path.join(folder, 'gate_*_into_*.json'))):
        if j.endswith('.summary.json'):
            continue
        try:
            r = json.load(open(j))
        except (OSError, ValueError):
            continue
        if r.get('branch') == branch and same(r.get('tip'), tip) and same(r.get('head'), head):
            return j[:-5] + '.md'
    return None


def gate_result(what, code):
    """a finished gate job's own report (what: its collect record) copied into charkit/out/gate and named, with its
    verdict -> the exit code: the job's, or 1 when no report of this branch and sha came back (a PASS is never
    claimed without its report)."""
    import shutil
    want = what.get('report')
    if not want:                                   # (a job recorded before reports were keyed: its folder only)
        print('remote gate: exit %s, report in %s' % (code, os.path.join(ROOT, what['to'])))
        return code
    md = gate_report(os.path.join(ROOT, what['to']), want['branch'], want['tip'], want['head'])
    if md is None:
        print('remote gate: exit %s, but no report of %s (%s) into %s (%s) came back from gate %s (its folder: %s)' % (
            code, want['branch'], want['tip'][:7], want['into'], want['head'][:7], what['gate'], what['to']))
        return code if code not in (0, None) else 1
    dst = os.path.join(ROOT, what.get('reports') or os.path.join('charkit', 'out', 'gate'))
    os.makedirs(dst, exist_ok=True)
    for ext in ('.md', '.json', '.summary.json'):
        src = md[:-3] + ext
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(dst, os.path.basename(src)))
    try:
        v = json.load(open(md[:-3] + '.summary.json')).get('verdict')
    except (OSError, ValueError):
        v = None
    print('remote gate: exit %s, gate %s: %s (%s) into %s (%s): %s, report %s' % (
        code, what['gate'], want['branch'], want['tip'][:7], want['into'], want['head'][:7], v or '?',
        os.path.join(dst, os.path.basename(md))))
    return code


def _gate_label(label):
    """a gate job's label -> (branch, spec or None): '<branch> into <base>[ --spec S][ --args ...]...'."""
    branch, _, rest = (label or '').partition(' into ')
    m = re.search(r"--spec ('[^']*'|\S+)", rest)
    return branch, (shlex.split(m.group(1))[0] if m else None)


def supersede(branch, spec=None):
    """one live gate per branch: this branch's gates still running on the box for the same spec are stopped (remote
    kill: their processes only; a gate's trap then removes its clone), since a new gate replaces them."""
    from charkit import boxjob
    cfg, vm = _cfg()
    r = subprocess.run(['ssh', '-F', cfg, vm, 'python3 - list --days 0'], input=open(boxjob.__file__, 'rb').read(),
                       capture_output=True)
    if r.returncode:
        print('remote gate: could not list the box\'s jobs (exit %d): older gates of %s left alone' % (r.returncode, branch),
              file=sys.stderr)
        return []
    rows = [json.loads(l) for l in r.stdout.decode().splitlines() if l.startswith('{')]
    old = [x['jid'] for x in rows if x.get('kind') == 'gate' and x.get('state') == 'running' and
           _gate_label(x.get('label')) == (branch, spec)]
    for jid in old:
        k = subprocess.run(['ssh', '-F', cfg, vm, 'python3 - kill %s' % shlex.quote(jid)],
                           input=open(boxjob.__file__, 'rb').read(), capture_output=True)
        print('remote gate: stopped the older gate of %s still running, %s (%s)' % (
            branch, jid, (k.stdout.decode().strip() or k.stderr.decode().strip())[-120:]), file=sys.stderr, flush=True)
    return old


# ------------------------------------------------------------------------------------------------ detached box jobs
STILL_RUNNING = 75                # this command stopped following, the job goes on (EX_TEMPFAIL): `remote attach JID`
LOST = 70                         # the job ended without an exit code (its box stopped or rebooted under it)


def _cfg():
    """build.sh's ssh config for the box (ProxyCommand: the IAP tunnel) and the host name in it."""
    vm = _env('VM')
    cfg = os.path.expanduser('~/.ssh/charkit-%s.config' % vm)
    mark = '# gcloud: %s\n' % (_gcloud() or os.environ.get('CLOUDSDK_CONFIG') or 'default')
    try:
        fresh = mark in open(cfg).read()
    except OSError:
        fresh = False
    if not fresh:                     # build.sh writes it on first use, and rewrites it for another gcloud config
        _sh('ssh', 'true', check=False, retry=True)
    return cfg, vm


def _gcloud():
    """the box's gcloud config, CLOUDSDK_CONFIG in its env file (the box-control service account's: no reauth; see
    docs/workstreams/infra-auth.md), put in this process's environment for its gcloud calls and ssh sessions -> it,
    or None (gcloud's default login)."""
    c = _env('CLOUDSDK_CONFIG')
    if c:
        os.environ['CLOUDSDK_CONFIG'] = os.path.expanduser(c)
    return c and os.path.expanduser(c)


CHECKED = set()                   # the gcloud configs whose credential worked in this process


def preflight():
    """before a job: the box's gcloud credential can act without a prompt (a token). Otherwise exit with one line on
    what to run, rather than a traceback from the first gcloud or ssh call."""
    c = _gcloud() or os.environ.get('CLOUDSDK_CONFIG') or 'default'
    if c in CHECKED or os.environ.get('CHARKIT_NO_PREFLIGHT'):
        return
    try:
        r = subprocess.run(['gcloud', 'auth', 'print-access-token', '--quiet'], capture_output=True, text=True,
                           stdin=subprocess.DEVNULL, timeout=60)
        err = r.stderr.strip().splitlines()
        ok = r.returncode == 0 and bool(r.stdout.strip())
        why = next((l for l in err if l.startswith('ERROR')), err[-1] if err else 'no token')
    except (OSError, subprocess.TimeoutExpired) as e:
        ok, why = False, str(e)
    if not ok:
        fix = ('its service-account key is not active: CLOUDSDK_CONFIG=%s gcloud auth activate-service-account '
               '--key-file=KEY (docs/workstreams/infra-auth.md), or delete the CLOUDSDK_CONFIG line in %s and run '
               '`gcloud auth login`' % (c, BOX['env'])) if c != 'default' else 'run `gcloud auth login`'
        raise SystemExit('remote: gcloud (config %s) cannot act for the box: %s. Fix: %s' % (c, why.strip()[-160:], fix))
    CHECKED.add(c)


def _record(rec):
    os.makedirs(JOBS_HERE, exist_ok=True)
    p = os.path.join(JOBS_HERE, rec['jid'] + '.json')
    with open(p + '.tmp', 'w') as f:
        json.dump(rec, f, indent=1)
    os.replace(p + '.tmp', p)


def _box_status():
    """the box's state from gcloud (RUNNING, TERMINATED, ...), or None when gcloud can't say."""
    _gcloud()
    r = subprocess.run(['gcloud', 'compute', 'instances', 'describe', _env('VM'), '--zone', _env('ZONE'), '--project',
                        _env('PROJECT'), '--format=value(status)'], capture_output=True, text=True)
    return (r.stdout.strip() or None) if r.returncode == 0 else None


def _take_job_opts(args):
    """leading --expect MIN and --stall MIN (right after remote's command: `remote run --expect 30 sweep ...`, `remote
    gate --stall 60 BRANCH ...`), kept for the job's meta (_job_opts) -> args without them."""
    args = list(args)
    while len(args) > 1 and args[0] in ('--expect', '--stall'):
        float(args[1])                              # (a number of minutes, or a ValueError here, not on the box)
        BOX[args[0][2:]] = args[1]
        args = args[2:]
    return args


def _job_opts():
    """the job's declared duration (--expect MIN, CHARKIT_JOB_EXPECT_MIN: `remote jobs` flags it past 2x) and its silence
    limit (--stall MIN, CHARKIT_JOB_STALL_MIN: default per kind, charkit/boxjob.py STALL_MIN) -> meta fields."""
    out = {}
    for key, name in (('expect_min', 'expect'), ('stall_min', 'stall')):
        v = BOX.get(name) or os.environ.get('CHARKIT_JOB_%s_MIN' % name.upper())
        if v:
            out[key] = float(v)
    return out


def job(kind, script, label, collect=None):
    """script run on the box as a detached job (charkit/boxjob.py), followed here until it ends -> its exit code
    (STILL_RUNNING if this command gave up following; LOST if it ended without one)."""
    import io, tarfile, uuid
    from charkit import boxjob, bucketsync
    wt = os.path.basename(ROOT)
    jid = '%s-%s-%s-%s' % (re.sub(r'[^A-Za-z0-9._-]', '_', kind), re.sub(r'[^A-Za-z0-9._-]', '_', wt.replace(
        'animation-pipeline-', '')), time.strftime('%m%d-%H%M%S'), uuid.uuid4().hex[:4])
    meta = dict(v=1, jid=jid, kind=kind, wt=wt, label=label, bucket=_env('BUCKET'), created=time.time(), **_job_opts())
    # (unbuffered: the log is followed as it's written; Python block-buffers a file otherwise)
    files = {'run.sh': ('#!/usr/bin/env bash\n# charkit box job %s: %s %s (from %s)\nexport PYTHONUNBUFFERED=1\n%s\n'
                        % (jid, kind, label, wt, script), 0o755),
             'meta.json': (json.dumps(meta, indent=1), 0o644),
             'boxjob.py': (open(boxjob.__file__).read(), 0o644),
             'bucketsync.py': (open(bucketsync.__file__).read(), 0o644)}
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w') as tf:
        for name, (text, mode) in files.items():
            b = text.encode()
            ti = tarfile.TarInfo(name)
            ti.size, ti.mode, ti.mtime = len(b), mode, int(time.time())
            tf.addfile(ti, io.BytesIO(b))
    preflight()
    rec = dict(jid=jid, box=os.path.basename(BOX['env'])[:-4], kind=kind, label=label, collect=collect,
               sent=time.strftime('%Y-%m-%dT%H:%M:%S'), state='starting', **_job_opts())
    _record(rec)
    cfg, vm = _cfg()
    # a retried start (the first one's connection dropped) finds the job claimed and doesn't run it again
    start = ('J=%s/%s; mkdir -p "$J" && if [ -e "$J/claim" ]; then cat >/dev/null; else tar -xf - -C "$J"; fi && '
             'python3 "$J/boxjob.py" start %s' % (JOBS_BOX, jid, jid))
    for i, w in enumerate([5, 15, 30, 60, 0]):
        r = subprocess.run(['ssh', '-F', cfg, vm, start], input=buf.getvalue(), capture_output=True)
        out = r.stdout.decode(errors='replace')
        if 'BOXJOB-STARTED' in out or 'BOXJOB-RUNNING' in out:
            break
        if r.returncode != SSH_FAIL or not w:
            sys.stderr.write(out + r.stderr.decode(errors='replace'))
            raise SystemExit('remote: the box did not start job %s (exit %d)' % (jid, r.returncode))
        print('remote: starting %s: the connection failed; retrying in %d s' % (jid, w), file=sys.stderr, flush=True)
        time.sleep(w)
    rec['state'] = 'running'
    _record(rec)
    print('remote: job %s started on the %s box (detached: a dropped connection reattaches; if this command dies, '
          '`python -m charkit remote attach %s`)' % (jid, rec['box'], jid), file=sys.stderr, flush=True)
    return attach(jid, rec)


REATTACH = 3                      # s before reattaching after a connection that had worked drops


def _follow_argv(cfg, vm, jid, at):
    return ['ssh', '-F', cfg, '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=4', vm,
            'python3 %s/%s/boxjob.py follow %s %d' % (JOBS_BOX, jid, jid, at)]


def attach(jid, rec=None, out=None):
    """follow a job's log until it ends -> its exit code. A dropped connection (ssh exits, or no frame for WATCHDOG s)
    reconnects with backoff and resumes at the byte it had reached; the job itself is never touched."""
    from charkit import boxjob
    out = out or sys.stdout.buffer
    rec = rec or {'jid': jid}
    # (a copy of the job's log here, by its id, whatever this command's own output is redirected to: two commands
    # sharing one redirect file garbled each other's output, 2026-09-30; a reattach appends from the byte it reached)
    os.makedirs(JOBS_HERE, exist_ok=True)
    keep = open(os.path.join(JOBS_HERE, jid + '.log'), 'ab')
    if keep.tell():
        keep.truncate(0)                          # (a follow from the start: attach replays the whole log)
    wrote = [time.time(), False]                  # the job's last output seen here, and whether its silence was told

    def data(b):
        out.write(b), out.flush(), keep.write(b), keep.flush()
        wrote[:] = [time.time(), False]
    fr = boxjob.Frames(data)
    limit = boxjob.stall_limit(rec.get('kind') or jid.split('-')[0], rec.get('stall_min'))
    cfg, vm = _cfg()
    drops, failing_since, errors = 0, None, 0
    while True:
        fr.reset()                                    # the next follow starts at the last byte delivered
        at = fr.got
        p = subprocess.Popen(_follow_argv(cfg, vm, jid, at), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        rec['ssh_pid'] = p.pid
        _record(rec)
        last = [time.time()]
        frames0 = fr.frames
        errbuf = []

        def read():
            while True:
                b = p.stdout.read1(1 << 16)
                if not b:
                    return
                last[0] = time.time()
                fr.feed(b)
                if fr.end is not None:
                    return
        t = threading.Thread(target=read, daemon=True)
        te = threading.Thread(target=lambda: errbuf.append(p.stderr.read()), daemon=True)
        t.start(); te.start()
        try:
            while t.is_alive():
                t.join(2)
                if not wrote[1] and time.time() - wrote[0] > limit * 60:
                    wrote[1] = True               # (the stall alarm, as `remote jobs` shows it; told once per silence)
                    print('\nremote: job %s has written nothing for %.0f min (its limit %g): not stopped; `python -m '
                          'charkit remote kill %s` if it hangs' % (jid, (time.time() - wrote[0]) / 60, limit, jid),
                          file=sys.stderr, flush=True)
                if t.is_alive() and time.time() - last[0] > WATCHDOG:
                    print('\nremote: no word from the box for %d s: reconnecting' % WATCHDOG, file=sys.stderr, flush=True)
                    p.kill()
                    t.join(10)
                    break
        except KeyboardInterrupt:
            p.kill()
            print('\nremote: stopped following; job %s goes on. `python -m charkit remote attach %s` follows it again, '
                  '`python -m charkit remote kill %s` stops it.' % (jid, jid, jid), file=sys.stderr, flush=True)
            return 130
        if fr.end is None:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
        else:
            p.terminate()
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
        te.join(2)
        if fr.end is not None:
            break
        stderr = (errbuf[0] if errbuf else b'').decode(errors='replace').strip()
        connected = fr.frames > frames0 or fr.got > at
        if connected:
            failing_since, errors = None, 0
        failing_since = failing_since or time.time()
        if p.returncode not in (SSH_FAIL, -9, None) and not connected:
            errors += 1                              # the box answered but the follow failed (not a dropped connection)
            if errors >= 3:
                sys.stderr.write(stderr + '\n')
                print('remote: cannot follow job %s (exit %d)' % (jid, p.returncode), file=sys.stderr)
                return 1
        drops += 1
        if time.time() - failing_since > GIVE_UP:
            print('remote: no connection to the box for %d min; job %s goes on there: `python -m charkit remote attach %s`'
                  % (GIVE_UP // 60, jid, jid), file=sys.stderr, flush=True)
            rec['state'] = 'detached'
            _record(rec)
            return STILL_RUNNING
        w = min(60, 5 * 2 ** min(drops - 1, 4)) if not connected else REATTACH
        if drops >= 3 and not connected and _box_status() not in ('RUNNING', None):
            print('remote: the box is %s: job %s was lost' % (_box_status(), jid), file=sys.stderr)
            rec['state'] = 'lost'
            _record(rec)
            return LOST
        print('\nremote: the connection to the box dropped (ssh exit %s%s) at byte %d of job %s; reattaching in %d s '
              '(drop %d)' % (p.returncode, ': ' + stderr.splitlines()[-1][:120] if stderr else '', fr.got, jid, w, drops),
              file=sys.stderr, flush=True)
        time.sleep(w)
    if drops:
        print('remote: job %s followed to its end through %d dropped connection%s' % (jid, drops, 's' * (drops != 1)),
              file=sys.stderr, flush=True)
    rec.update(state='done', rc=fr.end, drops=drops, ended=time.strftime('%Y-%m-%dT%H:%M:%S'))
    rec.pop('ssh_pid', None)
    _record(rec)
    if fr.end == 'lost':
        print('remote: job %s ended without an exit code (its box stopped or rebooted under it)' % jid, file=sys.stderr)
        return LOST
    if fr.end == 'nojob':
        print('remote: the box has no job %s' % jid, file=sys.stderr)
        return 2
    return fr.end


def _boxes():
    """the boxes to ask: --box's, else every infra/gcp/*.env with a VM and a bucket (the GPU box's gpu.env is the render
    box's), each once."""
    out, seen = [], set()
    for name in ['build', 'render'] + sorted(f[:-4] for f in os.listdir(os.path.join(ROOT, 'infra', 'gcp')) if f.endswith('.env')):
        p = os.path.join(ROOT, 'infra', 'gcp', name + '.env')
        if os.path.exists(p):
            BOX['env'] = p
            if _env('VM') and _env('VM') not in seen:
                seen.add(_env('VM'))
                out.append(p)
    return out


def box_slots(env=None):
    """a box's build slots now (env: its infra/gcp/NAME.env; default the chosen box) -> dict(name, status, count, held,
    waiting, free), or with status only when it isn't running or can't say. Read over ssh as `remote jobs` reads its
    jobs (charkit/boxjob.py's `slots`), so nothing is synced or started."""
    from charkit import boxjob
    if env:
        BOX['env'] = env
    name = os.path.basename(BOX['env'])[:-4]
    st = _box_status()
    if st != 'RUNNING':
        return dict(name=name, status=st or 'unknown')
    cfg, vm = _cfg()
    r = subprocess.run(['ssh', '-F', cfg, vm, 'python3 - slots'], input=open(boxjob.__file__, 'rb').read(),
                       capture_output=True)
    line = next((l for l in r.stdout.decode(errors='replace').splitlines() if l.startswith('{')), None)
    if r.returncode or not line:
        return dict(name=name, status='unreadable', why=r.stderr.decode(errors='replace')[-200:])
    s = json.loads(line)
    count = int(_env('SLOTS') or s.get('count') or 0)      # (the env file's: what a job sets the box to)
    return dict(name=name, status=st, count=count, held=s.get('held', 0), waiting=s.get('waiting', 0),
                free=max(0, count - s.get('held', 0) - s.get('waiting', 0)))


def box_has(path):
    """does the chosen box's copy of this worktree hold path (worktree-relative)?"""
    cfg, vm = _cfg()
    r = subprocess.run(['ssh', '-F', cfg, vm, 'test -e %s' % shlex.quote('/srv/work/%s/%s' % (
        os.path.basename(ROOT), path))], capture_output=True)
    return r.returncode == 0


def jobs(args):
    """every box's jobs (running, and finished in the last --days, default 1), a running one's alarms under it (SILENT,
    OVERRUN: charkit.boxjob.flags); --silences: each kind's longest silences instead (silences)."""
    from charkit import boxjob
    if '--silences' in args:
        return silences(args)
    days = _opt(args, '--days', '1')
    envs = [BOX['env']] if BOX.get('chosen') else _boxes()
    for env in envs:
        BOX['env'] = env
        name = os.path.basename(env)[:-4]
        st = _box_status()
        if st != 'RUNNING':
            print('%s box: %s (its jobs are listed when it runs)' % (name, st or 'unknown'))
            continue
        cfg, vm = _cfg()
        r = subprocess.run(['ssh', '-F', cfg, vm, 'python3 - list --days %s' % shlex.quote(days)],
                           input=open(boxjob.__file__, 'rb').read(), capture_output=True)
        if r.returncode:
            print('%s box: could not list jobs (exit %d) %s' % (name, r.returncode, r.stderr.decode(errors='replace')[-300:]))
            continue
        rows = [json.loads(l) for l in r.stdout.decode().splitlines() if l.startswith('{')]
        run = [x for x in rows if x['state'] == 'running']
        alarms = [x for x in run if x.get('flags')]
        print('%s box: %d running, %d finished in %s day(s)%s' % (name, len(run), len(rows) - len(run), days, (
            ', %d FLAGGED (silent past its limit, or past 2x its expected time)' % len(alarms)) if alarms else ''))
        for x in sorted(rows, key=lambda x: (x['state'] != 'running', -(x['started'] or 0))):
            dur = ((x['ended'] or time.time()) - x['started']) if x['started'] else 0
            quiet = ''
            if x['state'] == 'running' and x.get('quiet') is not None:
                quiet = ' quiet %.0f' % (x['quiet'] / 60)
            print('  %-44s %-8s %-5s %s %6.1f min%-9s %-26s %s' % (
                x['jid'], x['state'], '' if x['rc'] is None else 'rc %d' % x['rc'],
                time.strftime('%m-%d %H:%M', time.localtime(x['started'])) if x['started'] else '--',
                dur / 60, quiet, (x['label'] or '')[:26], (x['tail'] or '')[:70]))
            for f in x.get('flags') or ():
                print('      ^ %s' % flag_text(f, x['jid']))
    return 0


def flag_text(f, jid='JID'):
    """one alarm (charkit.boxjob.flags) in words."""
    if f['flag'] == 'silent':
        return ('SILENT: no output for %.0f min (its limit %g); not stopped: read its log (`remote attach %s`), '
                '`remote kill %s` if it hangs' % (f['minutes'], f['limit'], jid, jid))
    return 'OVERRUN: running %.0f min, past 2x the %g min it expected; not stopped' % (f['minutes'], f['expect'])


def silences(args):
    """`remote jobs --silences [--days N]`: per box and kind, the longest silence of each job the box's load sampler
    saw (its `quiet`, each minute: charkit.boxjob.silences), for the jobs that ended rc 0 (and apart, the others), beside
    the kind's limit: the measurement STALL_MIN is checked against."""
    from charkit import boxjob
    days = _opt(args, '--days', '7')
    for env in ([BOX['env']] if BOX.get('chosen') else _boxes()):
        BOX['env'] = env
        name = os.path.basename(env)[:-4]
        if _box_status() != 'RUNNING':
            print('%s box: not running' % name)
            continue
        cfg, vm = _cfg()
        r = subprocess.run(['ssh', '-F', cfg, vm, 'python3 - silences --days %s' % shlex.quote(days)],
                           input=open(boxjob.__file__, 'rb').read(), capture_output=True)
        rows = [json.loads(l) for l in r.stdout.decode().splitlines() if l.startswith('{')]
        print('%s box: the longest silence of each job, by kind (minutes; %s day(s) of samples)' % (name, days))
        print('  %-14s %-8s %5s %6s %6s %6s %6s  %s' % ('kind', 'ended', 'jobs', 'p50', 'p90', 'max', 'limit', 'worst'))
        for x in rows:
            print('  %-14s %-8s %5d %6.1f %6.1f %6.1f %6g  %s%s' % (
                x['kind'][:14], x['ended'], x['jobs'], x['p50'], x['p90'], x['max'], x['limit'], x['worst'],
                '  (over the limit)' if x['ended'] == 'ok' and x['max'] >= x['limit'] else ''))
        if not rows:
            print('  (no samples with `quiet` yet: the sampler records it from boxjob VERSION 4 on)')
    return 0


def _local(jid):
    p = os.path.join(JOBS_HERE, jid + '.json')
    return json.load(open(p)) if os.path.exists(p) else None


def main_attach(args):
    jid = args[0]
    rec = _local(jid)
    if rec and not BOX.get('chosen'):
        BOX['env'] = os.path.join(ROOT, 'infra', 'gcp', rec['box'] + '.env')
    code = attach(jid, rec)
    if rec and rec.get('collect') and code not in (STILL_RUNNING, 130):
        collect(rec['collect'])
        if rec['collect'].get('gate'):
            return gate_result(rec['collect'], code)
        print('remote attach: exit %s, outputs in %s' % (code, rec['collect']['to']))
    return code


def main_kill(args):
    from charkit import boxjob
    rec = _local(args[0])
    if rec and not BOX.get('chosen'):
        BOX['env'] = os.path.join(ROOT, 'infra', 'gcp', rec['box'] + '.env')
    cfg, vm = _cfg()
    return subprocess.run(['ssh', '-F', cfg, vm, 'python3 - kill %s' % shlex.quote(args[0])],
                          input=open(boxjob.__file__, 'rb').read()).returncode


BUCKET_OVER = 100 << 20           # bytes: a bigger file goes through the bucket (the IAP tunnel carries ~2-3 MB/s)


def _slots():
    """the box's build slots: its env file's SLOTS, else BOX_SLOTS (the build box's)."""
    v = _env('SLOTS')
    return int(v) if v else BOX_SLOTS


def _env(key):
    """KEY's value in the box's env file (a bash file: `export KEY=...` too, and $HOME expanded)."""
    for line in open(BOX['env']):
        line = line[len('export '):] if line.startswith('export ') else line
        if line.startswith(key + '='):
            return os.path.expandvars(line.split('=', 1)[1].split('#')[0].strip())
    return None


def put(local, remote):
    """a file onto the box: through its bucket (build.sh push: charkit/bucketsync.py); with CHARKIT_SYNC=rsync, through
    the bucket when big (the box's service account reads it), else rsync."""
    if _bucket():
        _sh('push', local, remote)
    elif os.path.getsize(local) > BUCKET_OVER and _env('BUCKET'):
        url = '%s/remote/%s' % (_env('BUCKET').rstrip('/'), os.path.basename(local))
        _gcloud()
        subprocess.run(['gcloud', 'storage', 'cp', '--quiet', local, url, '--project', _env('PROJECT')], check=True)
        _sh('ssh', 'gcloud storage cp --quiet %s %s' % (shlex.quote(url), shlex.quote(remote)))
    else:
        _sh('push', local, remote)


def main(args):
    if '--box' in args:                     # another box: infra/gcp/NAME.env (render: the GPU box, where boards render)
        i = args.index('--box')
        BOX['env'] = os.path.join(ROOT, 'infra', 'gcp', args[i + 1] + '.env')
        BOX['chosen'] = True
        args = args[:i] + args[i + 2:]
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return 0
    cmd, rest = args[0], args[1:]
    if cmd in ('build', 'tune'):
        return build(rest, cmd)
    if cmd == 'gate':
        return gate(rest)
    if cmd == 'run':
        if rest and rest[0] == '--fetch':            # run --fetch DIR CMD...: DIR (worktree-relative) fetched when it ends
            d = _rel(rest[1])
            import uuid
            pub = 'run-%s-%s' % (re.sub(r'[^A-Za-z0-9._-]', '_', os.path.basename(ROOT)), uuid.uuid4().hex[:8])
            what = dict(pull=pub, to=d, fetch=d)
            code = charkit(rest[2:], publish=(d, pub), collect=what)
            if code != STILL_RUNNING:
                collect(what)
                print('remote run: exit %d, %s fetched' % (code, d))
            return code
        return charkit(rest)
    if cmd == 'jobs':
        return jobs(rest)
    if cmd == 'attach':
        return main_attach(rest)
    if cmd == 'kill':
        return main_kill(rest)
    if cmd == 'load':
        from charkit import boxload
        return boxload.main(rest, BOX)
    if cmd in ('up', 'status', 'stop'):
        return _sh(cmd)
    print(__doc__)
    return 1
