"""Builds off the laptop, on the CPU build box (infra/gcp/build.sh; its config infra/gcp/build.env is gitignored): the
same charkit commands, run in a copy of this worktree there (rsync through IAP, only what changed), their outputs
fetched back. The laptop keeps one build slot (`python -m charkit slots 1`); the box has its own.

    python -m charkit remote build SPEC [build args]     sync, build there, fetch its --out
    python -m charkit remote tune SPEC [tune args]       sync, tune there, fetch its --out
    python -m charkit remote gate BRANCH --into BASE [--spec SPEC] [--args ARGS] [--accept PATTERN,...]
                                                         the gate there, in a clone kept current by git bundles, its
                                                         report fetched into charkit/out/gate (SPEC a path on the box)
    python -m charkit remote run CMD...                  anything, in the synced copy
    python -m charkit remote up | status | stop
    python -m charkit remote --box render build SPEC --boards views,body ...   # the GPU box (infra/gcp/render.env): boards render
"""
import json, os, re, shlex, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_SH = os.path.join(ROOT, 'infra', 'gcp', 'build.sh')
BOX = {'env': os.path.join(ROOT, 'infra', 'gcp', 'build.env')}   # which box: --box NAME reads infra/gcp/NAME.env
BOX_SLOTS = 8                     # concurrent builds on the box (32 vCPU, 128 GB)


def _sh(*args, check=True, capture=False, input=None):
    r = subprocess.run([BUILD_SH, *args], check=check, text=True, capture_output=capture, input=input,
                       env=dict(os.environ, CHARKIT_BOX_ENV=BOX['env']))
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
    _sh('ssh', 'touch /srv/work/.keepalive', check=False)


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


def charkit(cmd, publish=None):
    """a charkit command in the box's copy of this worktree (synced first). publish=(PATH, NAME): PATH in the copy is
    published to the bucket under NAME at the end of the same ssh (charkit/bucketsync.py), for `build.sh pull`."""
    up()
    seed()
    _sh('sync', ROOT)
    line = 'python -m charkit slots %d >/dev/null && python -m charkit %s' % (_slots(), ' '.join(shlex.quote(c) for c in cmd))
    script = None
    if publish and _bucket():
        from charkit import bucketsync
        install, runner, script = bucketsync.box_install(_env('BUCKET'))
        line = '%s && { %s; rc=$?; %s publish %s --name %s >/dev/null 2>&1; exit $rc; }' % (
            install, line, runner, shlex.quote(publish[0]), shlex.quote(publish[1]))
        script = script.decode()
    return _sh('run', ROOT, line, check=False, input=script)


def build(args, kind='build'):
    """remote build or tune: the spec made portable, the command run there, its --out fetched."""
    spec = _portable_spec(args[0])
    rest = [_rel(a) for a in args[1:]]
    name = json.load(open(os.path.join(ROOT, spec))).get('name', 'char')
    out = _opt(rest, '--out', 'charkit/out/%s' % name)
    import uuid
    pub = 'build-%s-%s' % (re.sub(r'[^A-Za-z0-9._-]', '_', os.path.basename(ROOT)), uuid.uuid4().hex[:8])
    code = charkit([kind, spec] + rest, publish=(out, pub))
    # the outputs were published in the build's own ssh: pulled from the bucket, else fetched
    if not (_bucket() and _sh('pull', pub, os.path.join(ROOT, out), check=False) == 0):
        _sh('fetch', ROOT, out)
    print('remote %s: exit %d, %s fetched' % (kind, code, out))
    return code


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
    have = _sh('ssh', 'git -C /srv/work/repo for-each-ref --format="%(objectname)" 2>/dev/null; true', capture=True,
               check=False).split()
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
    _sh('ssh', 'mkdir -p /srv/work/gates && S=%s; [ -d $S ] || S=/srv/work/repo/charkit/out/i3d; '
        '[ -d $S ] && cp -al $S %s || mkdir -p %s' % (seed, GI, GI))
    if os.path.isdir(i3d):
        _sh('push', i3d + '/', GI + '/', '--link')
    sha = {b: subprocess.run(['git', '-C', ROOT, 'rev-parse', b], capture_output=True, text=True, check=True).stdout.strip()
           for b in (into, branch)}
    q = shlex.quote
    install, publish, script = '', '', None
    if _bucket():                               # the report goes back through the bucket (charkit/bucketsync.py)
        from charkit import bucketsync
        install, runner, script = bucketsync.box_install(_env('BUCKET'))
        script = script.decode()
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
    # over plain ssh with the box's environment: `run` would first cd into this worktree's synced copy, which a worktree
    # that has only ever gated doesn't have
    code = _sh('ssh', '%ssource /opt/anim-build/env && bash -c %s' % (install and install + '; ', q(step)), check=False,
               input=script)
    local = os.path.join(ROOT, 'charkit', 'out', 'gate')
    os.makedirs(local, exist_ok=True)
    # the report was published to the bucket inside the gate's own ssh: no second connection through the tunnel
    if not (_bucket() and _sh('pull', 'gate-' + gid, local, check=False) == 0):
        subprocess.run(['rsync', '-az', '-e', 'ssh -F %s' % os.path.expanduser('~/.ssh/charkit-%s.config' % _box_name()),
                        '%s:/srv/work/_gate/%s/' % (_box_name(), gid), local + '/'], check=False)
    print('remote gate: exit %d, report in %s' % (code, local))
    return code


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


def _box_name():
    return _env('VM') or 'anim-build-1'


def main(args):
    if '--box' in args:                     # another box: infra/gcp/NAME.env (render: the GPU box, where boards render)
        i = args.index('--box')
        BOX['env'] = os.path.join(ROOT, 'infra', 'gcp', args[i + 1] + '.env')
        args = args[:i] + args[i + 2:]
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return 0
    cmd, rest = args[0], args[1:]
    if cmd in ('build', 'tune'):
        return build(rest, cmd)
    if cmd == 'gate':
        return gate(rest)
    if cmd == 'run':
        return charkit(rest)
    if cmd in ('up', 'status', 'stop'):
        return _sh(cmd)
    print(__doc__)
    return 1
