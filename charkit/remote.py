"""Builds off the laptop, on the CPU build box (infra/gcp/build.sh; its config infra/gcp/build.env is gitignored): the
same charkit commands, run in a copy of this worktree there (rsync through IAP, only what changed), their outputs
fetched back. The laptop keeps one build slot (`python -m charkit slots 1`); the box has its own.

    python -m charkit remote build SPEC [build args]     sync, build there, fetch its --out
    python -m charkit remote tune SPEC [tune args]       sync, tune there, fetch its --out
    python -m charkit remote gate BRANCH --into BASE     the gate there, in a clone kept current by git bundles, its
                                                         report fetched into charkit/out/gate
    python -m charkit remote run CMD...                  anything, in the synced copy
    python -m charkit remote up | status | stop
"""
import json, os, shlex, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_SH = os.path.join(ROOT, 'infra', 'gcp', 'build.sh')
BOX_SLOTS = 8                     # concurrent builds on the box (32 vCPU, 128 GB)


def _sh(*args, check=True, capture=False):
    r = subprocess.run([BUILD_SH, *args], check=check, text=True, capture_output=capture)
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
    _sh('run', ROOT, 'mkdir -p /srv/work && true')


def charkit(cmd):
    """a charkit command in the box's copy of this worktree (synced first)."""
    up()
    _sh('sync', ROOT)
    line = 'python -m charkit slots %d >/dev/null && python -m charkit %s' % (BOX_SLOTS, ' '.join(shlex.quote(c) for c in cmd))
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
    """the gate on the box: a git bundle of the branch and its base brought into a clone there, the gitignored inputs the
    builds read (charkit/out/i3d) beside it, the gate run in the clone, its report fetched."""
    branch, into = args[0], _opt(args, '--into', 'pipeline-3d')
    bundle = os.path.join(ROOT, 'charkit', 'out', 'remote', 'repo.bundle')
    os.makedirs(os.path.dirname(bundle), exist_ok=True)
    subprocess.run(['git', '-C', ROOT, 'bundle', 'create', bundle, into, branch], check=True, capture_output=True)
    up()
    _sh('push', bundle, '/srv/work/repo.bundle')
    _sh('run', ROOT, 'cd /srv/work && ( [ -d repo/.git ] || git clone -q repo.bundle repo ) && cd repo && '
        'git fetch -q -f ../repo.bundle "refs/heads/*:refs/heads/*" --update-head-ok && git checkout -q -f %s' % shlex.quote(into))
    i3d = os.path.join(ROOT, 'charkit', 'out', 'i3d')
    if os.path.isdir(i3d):
        _sh('run', ROOT, 'mkdir -p /srv/work/repo/charkit/out')
        _sh('push', i3d + '/', '/srv/work/repo/charkit/out/i3d/')
    code = _sh('run', ROOT, 'cd /srv/work/repo && python -m charkit slots %d >/dev/null && python -m charkit gate %s --into %s' % (
        BOX_SLOTS, shlex.quote(branch), shlex.quote(into)), check=False)
    _sh('ssh', 'mkdir -p /srv/work/_gate && cp -r /srv/work/repo/charkit/out/gate/. /srv/work/_gate/ 2>/dev/null; true')
    local = os.path.join(ROOT, 'charkit', 'out', 'gate')
    os.makedirs(local, exist_ok=True)
    subprocess.run(['rsync', '-az', '-e', 'ssh -F %s' % os.path.expanduser('~/.ssh/anim-build.config'),
                    '%s:/srv/work/_gate/' % _box_name(), local + '/'], check=False)
    print('remote gate: exit %d, reports in %s' % (code, local))
    return code


def _box_name():
    for line in open(os.path.join(ROOT, 'infra', 'gcp', 'build.env')):
        if line.startswith('VM='):
            return line.split('=', 1)[1].split('#')[0].strip()
    return 'anim-build-1'


def main(args):
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
