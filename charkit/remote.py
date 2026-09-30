"""Builds off the laptop, on the CPU build box (infra/gcp/build.sh; its config infra/gcp/build.env is gitignored): the
same charkit commands, run in a copy of this worktree there (rsync through IAP, only what changed), their outputs
fetched back. The laptop keeps one build slot (`python -m charkit slots 1`); the box has its own.

    python -m charkit remote build SPEC [build args]     sync, build there, fetch its --out
    python -m charkit remote tune SPEC [tune args]       sync, tune there, fetch its --out
    python -m charkit remote gate BRANCH --into BASE [--spec SPEC] [--args ARGS] [--accept PATTERN,...]
                                                         the gate there, in a clone kept current by git bundles, its
                                                         report fetched into charkit/out/gate (SPEC a path on the box)
    python -m charkit remote run [--fetch DIR] CMD...    anything, in the synced copy (DIR fetched back when it ends)
    python -m charkit remote jobs [--days N]             every box's jobs: running, finished (N days, default 1), lost
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
    _sh('up')
    _sh('ssh', 'touch /srv/work/.keepalive', check=False, retry=True)


def seed():
    """a box with no copy of any worktree yet (the render box's first sync) gets this one through the bucket: a tarball
    of its tracked files and charkit/out/i3d, rather than ~0.8 GB through the IAP tunnel; rsync then sends what differs.
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
        i3d = os.path.join(ROOT, 'charkit', 'out', 'i3d')
        if os.path.isdir(i3d):
            tf.add(i3d, arcname='charkit/out/i3d')
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
    branch, into = args[0], _opt(args, '--into', 'pipeline-3d')
    tag = re.sub(r'[^A-Za-z0-9._-]', '_', branch)
    gid = '%s-%s' % (tag, uuid.uuid4().hex[:8])
    bundle = os.path.join(ROOT, 'charkit', 'out', 'remote', 'repo-%s.bundle' % gid)
    boxed = '/srv/work/repo-%s.bundle' % gid
    G, GI = '/srv/work/gates/%s' % gid, '/srv/work/gates/%s.i3d' % gid
    os.makedirs(os.path.dirname(bundle), exist_ok=True)
    up()
    # only what the box's clone lacks: its refs' commits (known here, since they came from here) are left out
    # (a failed ssh here must not read as "the box has nothing": that bundle would be the whole history, 1.8 GB)
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
    # this gate's inputs (charkit/out/i3d): seeded by links from this worktree's synced copy, or the clone's, then this
    # worktree's changes sent (rsync replaces a changed file, never writing through a link)
    i3d = os.path.join(ROOT, 'charkit', 'out', 'i3d')
    seed = '/srv/work/%s/charkit/out/i3d' % os.path.basename(ROOT)
    # (safe to repeat after a dropped connection: the links land under a temporary name, renamed into place)
    _sh('ssh', 'mkdir -p /srv/work/gates && S=%s; [ -d $S ] || S=/srv/work/repo/charkit/out/i3d; [ -e %s ] || '
        '{ { [ -d $S ] && rm -rf %s.tmp && cp -al $S %s.tmp && mv %s.tmp %s; } || mkdir -p %s; }'
        % (seed, GI, GI, GI, GI, GI, GI), retry=True)
    if os.path.isdir(i3d):
        _sh('push', i3d + '/', GI + '/', '--link', retry=True)
    sha = {b: subprocess.run(['git', '-C', ROOT, 'rev-parse', b], capture_output=True, text=True, check=True).stdout.strip()
           for b in (into, branch)}
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
    step = ('rc=1; flock /srv/work/.gate-fetch.lock bash -c %(fetch)s && cd %(G)s && '
            'git config user.name charkit-gate && git config user.email gate@localhost && '
            'git sparse-checkout set --cone charkit && '
            'git update-ref refs/heads/%(into)s %(si)s && git update-ref refs/heads/%(branch)s %(sb)s && '
            'git checkout -q -f %(into)s && mkdir -p charkit/out /srv/work/gate-out /srv/work/_gate/%(gid)s && '
            'ln -s %(GI)s charkit/out/i3d && ln -s /srv/work/gate-out charkit/out/gate && '
            'python -m charkit slots %(slots)d >/dev/null && '
            '{ python -m charkit gate %(branch)s --into %(into)s%(more)s 2>&1 | tee %(G)s.log; rc=${PIPESTATUS[0]}; } ; '
            'for r in $(sed -n "s/^report //p" %(G)s.log); do cp "${r%%.md}.md" "${r%%.md}.json" /srv/work/_gate/%(gid)s/ '
            '2>/dev/null; done; %(publish)scd /srv/work && rm -rf %(G)s %(GI)s %(G)s.log; '
            'find /srv/work/gate-out -maxdepth 1 -name "cand_*" -mtime +3 -exec rm -rf {} + 2>/dev/null; exit $rc'
            % dict(fetch=q(fetch), G=G, GI=GI, gid=gid, into=q(into), branch=q(branch), si=sha[into], sb=sha[branch],
                   slots=_slots(), more=more, publish=publish))
    # with the box's environment, not in this worktree's synced copy (a worktree that has only ever gated has none)
    what = dict(pull='gate-' + gid, to=os.path.join('charkit', 'out', 'gate'), gate=gid)
    if _detach():
        code = job('gate', 'source /opt/anim-build/env && bash -c %s' % q(step), '%s into %s%s' % (branch, into, more),
                   collect=what)
        if code == STILL_RUNNING:
            return code
    else:
        code = _sh('ssh', '%ssource /opt/anim-build/env && bash -c %s' % (install and install + '; ', q(step)),
                   check=False, input=script)
    local = os.path.join(ROOT, 'charkit', 'out', 'gate')
    os.makedirs(local, exist_ok=True)
    # the report was published to the bucket when the gate ended: no second connection through the tunnel
    collect(what)
    print('remote gate: exit %d, report in %s' % (code, local))
    return code


# ------------------------------------------------------------------------------------------------ detached box jobs
STILL_RUNNING = 75                # this command stopped following, the job goes on (EX_TEMPFAIL): `remote attach JID`
LOST = 70                         # the job ended without an exit code (its box stopped or rebooted under it)


def _cfg():
    """build.sh's ssh config for the box (ProxyCommand: the IAP tunnel) and the host name in it."""
    vm = _env('VM')
    cfg = os.path.expanduser('~/.ssh/charkit-%s.config' % vm)
    if not os.path.exists(cfg):
        _sh('ssh', 'true', check=False, retry=True)          # build.sh writes the config on first use
    return cfg, vm


def _record(rec):
    os.makedirs(JOBS_HERE, exist_ok=True)
    p = os.path.join(JOBS_HERE, rec['jid'] + '.json')
    with open(p + '.tmp', 'w') as f:
        json.dump(rec, f, indent=1)
    os.replace(p + '.tmp', p)


def _box_status():
    """the box's state from gcloud (RUNNING, TERMINATED, ...), or None when gcloud can't say."""
    r = subprocess.run(['gcloud', 'compute', 'instances', 'describe', _env('VM'), '--zone', _env('ZONE'), '--project',
                        _env('PROJECT'), '--format=value(status)'], capture_output=True, text=True)
    return (r.stdout.strip() or None) if r.returncode == 0 else None


def job(kind, script, label, collect=None):
    """script run on the box as a detached job (charkit/boxjob.py), followed here until it ends -> its exit code
    (STILL_RUNNING if this command gave up following; LOST if it ended without one)."""
    import io, tarfile, uuid
    from charkit import boxjob, bucketsync
    wt = os.path.basename(ROOT)
    jid = '%s-%s-%s-%s' % (re.sub(r'[^A-Za-z0-9._-]', '_', kind), re.sub(r'[^A-Za-z0-9._-]', '_', wt.replace(
        'animation-pipeline-', '')), time.strftime('%m%d-%H%M%S'), uuid.uuid4().hex[:4])
    meta = dict(v=1, jid=jid, kind=kind, wt=wt, label=label, bucket=_env('BUCKET'), created=time.time())
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
    rec = dict(jid=jid, box=os.path.basename(BOX['env'])[:-4], kind=kind, label=label, collect=collect,
               sent=time.strftime('%Y-%m-%dT%H:%M:%S'), state='starting')
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
    fr = boxjob.Frames(lambda b: (out.write(b), out.flush()))
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
    for name in ('build', 'render'):
        p = os.path.join(ROOT, 'infra', 'gcp', name + '.env')
        if os.path.exists(p):
            BOX['env'] = p
            if _env('VM') and _env('VM') not in seen:
                seen.add(_env('VM'))
                out.append(p)
    return out


def jobs(args):
    """every box's jobs (running, and finished in the last --days, default 1)."""
    from charkit import boxjob
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
        print('%s box: %d running, %d finished in %s day(s)' % (name, len(run), len(rows) - len(run), days))
        for x in sorted(rows, key=lambda x: (x['state'] != 'running', -(x['started'] or 0))):
            dur = ((x['ended'] or time.time()) - x['started']) if x['started'] else 0
            print('  %-44s %-8s %-5s %s %6.1f min  %-26s %s' % (
                x['jid'], x['state'], '' if x['rc'] is None else 'rc %d' % x['rc'],
                time.strftime('%m-%d %H:%M', time.localtime(x['started'])) if x['started'] else '--',
                dur / 60, (x['label'] or '')[:26], (x['tail'] or '')[:70]))
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
    for line in open(BOX['env']):
        if line.startswith(key + '='):
            return line.split('=', 1)[1].split('#')[0].strip()
    return None


def put(local, remote):
    """a file onto the box: through its bucket (build.sh push: charkit/bucketsync.py); with CHARKIT_SYNC=rsync, through
    the bucket when big (the box's service account reads it), else rsync."""
    if _bucket():
        _sh('push', local, remote)
    elif os.path.getsize(local) > BUCKET_OVER and _env('BUCKET'):
        url = '%s/remote/%s' % (_env('BUCKET').rstrip('/'), os.path.basename(local))
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
