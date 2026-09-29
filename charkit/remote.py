"""Builds off the laptop, on the CPU build box (infra/gcp/build.sh; its config infra/gcp/build.env is gitignored): the
same charkit commands, run in a copy of this worktree there (rsync through IAP, only what changed), their outputs
fetched back. The laptop keeps one build slot (`python -m charkit slots 1`); the box has its own.

    python -m charkit remote build SPEC [build args]     sync, build there, fetch its --out
    python -m charkit remote tune SPEC [tune args]       sync, tune there, fetch its --out
    python -m charkit remote gate BRANCH --into BASE [--spec SPEC] [--args ARGS]
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


def _sh(*args, check=True, capture=False):
    r = subprocess.run([BUILD_SH, *args], check=check, text=True, capture_output=capture,
                       env=dict(os.environ, CHARKIT_BOX_ENV=BOX['env']))
    return r.stdout if capture else r.returncode


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
    _sh('up')


def seed():
    """a box with no copy of any worktree yet (the render box's first sync) gets this one through the bucket: a tarball
    of its tracked files and charkit/out/i3d, rather than ~0.8 GB through the IAP tunnel; rsync then sends what differs."""
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


def charkit(cmd):
    """a charkit command in the box's copy of this worktree (synced first)."""
    up()
    seed()
    _sh('sync', ROOT)
    line = 'python -m charkit slots %d >/dev/null && python -m charkit %s' % (_slots(), ' '.join(shlex.quote(c) for c in cmd))
    return _sh('run', ROOT, line, check=False)


def build(args, kind='build'):
    """remote build or tune: the spec made portable, the command run there, its --out fetched."""
    spec = _portable_spec(args[0])
    rest = [_rel(a) for a in args[1:]]
    name = json.load(open(os.path.join(ROOT, spec))).get('name', 'char')
    out = _opt(rest, '--out', 'charkit/out/%s' % name)
    code = charkit([kind, spec] + rest)
    _sh('fetch', ROOT, out)
    print('remote %s: exit %d, %s fetched' % (kind, code, out))
    return code


def gate(args):
    """the gate on the box: a git bundle of what the box's clone lacks brought into it, the gitignored inputs the builds
    read (charkit/out/i3d) beside it, the gate run in the clone, its report fetched. Gates from several worktrees queue
    on a lock there (they share the clone), so parallel workstreams can each gate when ready."""
    branch, into = args[0], _opt(args, '--into', 'pipeline-3d')
    tag = re.sub(r'[^A-Za-z0-9._-]', '_', branch)
    bundle = os.path.join(ROOT, 'charkit', 'out', 'remote', 'repo-%s.bundle' % tag)
    boxed = '/srv/work/repo-%s.bundle' % tag
    os.makedirs(os.path.dirname(bundle), exist_ok=True)
    up()
    # only what the box's clone lacks: its refs' commits (known here, since they came from here) are left out
    have = _sh('ssh', 'git -C /srv/work/repo for-each-ref --format="%(objectname)" 2>/dev/null; true', capture=True,
               check=False).split()
    known = [c for c in have if subprocess.run(['git', '-C', ROOT, 'cat-file', '-e', c + '^{commit}'],
                                              capture_output=True).returncode == 0]
    r = subprocess.run(['git', '-C', ROOT, 'bundle', 'create', bundle, into, branch] + ['^' + c for c in known],
                       capture_output=True, text=True)
    if r.returncode != 0 and 'empty bundle' not in r.stderr:
        raise SystemExit(r.stderr)
    if r.returncode == 0:
        put(bundle, boxed)
        os.remove(bundle)
    i3d = os.path.join(ROOT, 'charkit', 'out', 'i3d')
    if os.path.isdir(i3d):
        # seeded on the box from its synced copy of this worktree when there is one, so the tunnel carries only changes
        seed = '/srv/work/%s/charkit/out/i3d/' % os.path.basename(ROOT)
        _sh('ssh', 'mkdir -p /srv/work/repo/charkit/out/i3d && { [ ! -d %s ] || rsync -a %s /srv/work/repo/charkit/out/i3d/; }'
            % (seed, seed))
        _sh('push', i3d + '/', '/srv/work/repo/charkit/out/i3d/')
    # under the lock: the refs set to this worktree's commits exactly (an empty bundle means the clone has them all; the
    # bundle is removed once read, so a later run never fetches a stale one), then the gate
    sha = {b: subprocess.run(['git', '-C', ROOT, 'rev-parse', b], capture_output=True, text=True, check=True).stdout.strip()
           for b in (into, branch)}
    refs = ' && '.join('git update-ref refs/heads/%s %s' % (shlex.quote(b), sha[b]) for b in (into, branch))
    step = ('cd /srv/work && ( [ -d repo/.git ] || git clone -q %(b)s repo ) && cd repo && '
            'git config user.name charkit-gate && git config user.email gate@localhost && '
            '{ [ ! -f %(b)s ] || git fetch -q -f %(b)s "refs/heads/*:refs/heads/*" --update-head-ok; } && '
            '%(refs)s && git checkout -q -f %(into)s && rm -f %(b)s && '
            'python -m charkit slots %(slots)d >/dev/null && python -m charkit gate %(branch)s --into %(into)s%(more)s'
            % dict(b=boxed, refs=refs, into=shlex.quote(into), branch=shlex.quote(branch), slots=_slots(),
                   more=''.join(' %s %s' % (k, shlex.quote(_opt(args, k))) for k in ('--spec', '--args') if k in args)))
    # over plain ssh with the box's environment: `run` would first cd into this worktree's synced copy, which a worktree
    # that has only ever gated doesn't have
    code = _sh('ssh', 'source /opt/anim-build/env && flock /srv/work/.gate.lock bash -c %s' % shlex.quote(step), check=False)
    _sh('ssh', 'mkdir -p /srv/work/_gate && cp -r /srv/work/repo/charkit/out/gate/. /srv/work/_gate/ 2>/dev/null; true')
    local = os.path.join(ROOT, 'charkit', 'out', 'gate')
    os.makedirs(local, exist_ok=True)
    subprocess.run(['rsync', '-az', '-e', 'ssh -F %s' % os.path.expanduser('~/.ssh/charkit-%s.config' % _box_name()),
                    '%s:/srv/work/_gate/' % _box_name(), local + '/'], check=False)
    print('remote gate: exit %d, reports in %s' % (code, local))
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
    """a file onto the box: through its bucket when big (the box's service account reads it), else rsync."""
    if os.path.getsize(local) > BUCKET_OVER and _env('BUCKET'):
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
