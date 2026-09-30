"""A build's input closure: every file under the worktree that a build read (the charkit modules it imported, the spec,
the manifest and its references, the generated inputs), recorded while it ran, so the merge gate can tell that a branch
can't change the build without building it: none of the files the baseline build read changed, so the candidate's
stage cache keys (charkit/cache.py: code, spec, files; upstream follows from those) equal the baseline's.

Recording (standard library only). With CHARKIT_CLOSURE=LOG in the environment, importing charkit installs an audit
hook (sys.addaudithook) in that process: the venv's `charkit build`, the Blender it starts (build_blender.py imports
charkit; Blender passes the environment on) and any other charkit process under them. Each appends a line per path, once
per process, to LOG:
    R path     opened for reading (a module imported: its .py, or its cached .pyc mapped to the .py)
    W path     opened for writing, renamed, linked, copied or deleted onto: an output, never an input
    L dir      listed by the build's own code (os.listdir, os.scandir, glob): a file added there can reach the build
               (the import system's own listings are left out)
    X path     a file named in a command the build started (Blender's --python charkit/build_blender.py)
    M path     the process's main script
    S dir\tre  a scan: every .py under dir read for a marker (charkit.registry: `@qa_part(`, MEASUREMENT_STEPS), its
               reads left out; a change there counts when the marker is in the file's old or new text
Code that looks at files without depending on them (the cache's check for sources edited mid-build) runs under
`paused()`: nothing it opens or lists is recorded, in its own thread.
Paths are relative to the worktree; a path through a link in charkit/out (the gate's charkit/out/i3d and
charkit/out/gate) is recorded as the link's. Paths outside the worktree (the venv, Blender, the shared caches) are the
environment's, which the gate doesn't compare.

    closure.summarise(LOG, root, skip=(out,)) -> the closure (what OUT/closure.json holds): tracked paths read, untracked
        inputs by sha256 (charkit/out/i3d), folders listed, the counts
    closure.affected(C, changes, root) -> [(path, why)]: the changes that can reach a build whose closure is C

What can change a build, given its closure (affected()):
  - a file it read, or ran, changed (tracked: the merge's changes; untracked: its sha256 differs);
  - a file added, changed or deleted in a folder its own code listed;
  - a data file (not Python, not documentation) changed anywhere in the checkout: Blender's C code reads images and
    libraries the audit hook can't see, so a data file the record doesn't name still counts (conservative);
  - a Python file under a scanned folder whose old or new text has the scan's marker;
A Python module the build never imported, parsed or ran, documentation (*.md, docs/) and the tests can't change it.
"""
import contextlib, os, re, sys, threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = 'CHARKIT_CLOSURE'
DOCS = ('.md', '.rst', '.txt')
NEVER = ('docs/', 'charkit/tests/')          # (prefixes) nothing a build reads lives here
CACHES = ('charkit/out/.cache/',)            # (prefixes) derived from what the build reads: never an input
_STATE = {}
_TLS = threading.local()                    # this thread's pause depth


# ---------------------------------------------------------------------------------------------------------- recording
def _prefixes(root):
    """(absolute prefix, worktree-relative prefix): the worktree itself (as named and resolved) and each link in
    charkit/out (the gate's i3d and gate folders), resolved."""
    out = [(root + os.sep, ''), (os.path.realpath(root) + os.sep, '')]
    d = os.path.join(root, 'charkit', 'out')
    try:
        for n in os.listdir(d):
            p = os.path.join(d, n)
            if os.path.islink(p):
                out.append((os.path.realpath(p) + os.sep, 'charkit/out/%s/' % n))
    except OSError:
        pass
    return sorted(set(out), key=lambda x: -len(x[0]))


def _rel(path, prefixes, source=True):
    if isinstance(path, bytes):
        path = path.decode(errors='replace')
    elif not isinstance(path, str):
        path = os.fspath(path) if hasattr(path, '__fspath__') else None
        if not isinstance(path, str):
            return None
    if not os.path.isabs(path):
        try:
            path = os.path.join(os.getcwd(), path)
        except OSError:
            return None
    path = os.path.normpath(path)
    for a, r in prefixes:
        if path.startswith(a):
            p = r + path[len(a):]
            if source and '/__pycache__/' in '/' + p and p.endswith('.pyc'):      # a cached module: its source
                d, f = p.rsplit('/__pycache__/', 1) if '/__pycache__/' in p else ('', p.split('__pycache__/', 1)[1])
                p = (d + '/' if d else '') + f.split('.', 1)[0] + '.py'
            return p
    return None


_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND


def start(log=None, root=ROOT):
    """install the recorder in this process (once), appending to LOG (CHARKIT_CLOSURE)."""
    log = log or os.environ.get(ENV)
    if not log or _STATE.get('log') == log:
        return False
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    pre = _prefixes(root)
    seen = set()
    _STATE.update(log=log, fd=fd, seen=seen, on=True, pre=pre)

    def emit(kind, path):
        p = _rel(path, pre, kind == 'R')
        if p is None or (kind, p) in seen or '__pycache__/' in p or p.startswith(CACHES):
            return                  # (byte code, numba's caches and the build cache: derived from the code and inputs)
        seen.add((kind, p))
        try:
            os.write(fd, ('%s %s\n' % (kind, p)).encode('utf-8', 'replace'))
        except OSError:
            pass

    def hook(event, args):
        if not _STATE.get('on') or getattr(_TLS, 'paused', 0):
            return
        try:
            if event == 'open':
                path, mode, flags = (tuple(args) + (None, None, None))[:3]
                if isinstance(path, int):
                    return
                w = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or \
                    (mode is None and isinstance(flags, int) and flags & _WRITE_FLAGS)
                emit('W' if w else 'R', path)
            elif event in ('os.rename', 'os.replace', 'os.link', 'os.symlink'):
                emit('W', args[0]) if event in ('os.rename', 'os.replace') else None
                emit('W', args[1])
            elif event in ('os.remove', 'os.unlink', 'shutil.rmtree'):
                emit('W', args[0])
            elif event in ('os.listdir', 'os.scandir'):
                f = sys._getframe(1)
                if f.f_code.co_filename.startswith('<frozen importlib'):
                    return                                      # the import system looking for a module
                emit('L', args[0] if args and args[0] is not None else '.')
            elif event in ('subprocess.Popen', 'os.posix_spawn', 'os.exec'):
                argv = args[1] if len(args) > 1 else ()
                for a in (argv if isinstance(argv, (list, tuple)) else [argv]):
                    if isinstance(a, (str, bytes)) and os.path.isfile(a):
                        emit('X', a)
        except Exception:
            pass
    _STATE['emit'] = emit
    sys.addaudithook(hook)
    main = getattr(sys.modules.get('__main__'), '__file__', None)
    if main:
        emit('M', main)
    for m in list(sys.modules.values()):          # what this process imported before the hook
        f = getattr(m, '__file__', None)
        if f:
            emit('R', f)
    return True


@contextlib.contextmanager
def paused():
    """nothing this thread opens or lists inside is recorded (a look at files that doesn't make them inputs)."""
    _TLS.paused = getattr(_TLS, 'paused', 0) + 1
    try:
        yield
    finally:
        _TLS.paused -= 1


@contextlib.contextmanager
def scanning(folder, marker):
    """a scan of the .py files under folder for a marker (a regular expression, multiline): recorded as the scan, not
    as reads of every file (a file matters when its old or new text has the marker)."""
    emit = _STATE.get('emit')
    if emit is not None and _STATE.get('on') and not getattr(_TLS, 'paused', 0):
        p = _rel(folder, _STATE['pre'], False)
        if p is not None:
            key = ('S', p + '\t' + marker)
            if key not in _STATE['seen']:
                _STATE['seen'].add(key)
                os.write(_STATE['fd'], ('S %s\t%s\n' % (p, marker)).encode())
    with paused():
        yield


def stop():
    """(tests) stop recording in this process; the hook stays installed (they can't be removed) but writes nothing."""
    _STATE['on'] = False
    _STATE.pop('log', None)


# ------------------------------------------------------------------------------------------------------- the closure
def _git(root, *a):
    import subprocess
    r = subprocess.run(['git', *a], cwd=root, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def sha256(path, chunk=1 << 20):
    import hashlib
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            for b in iter(lambda: f.read(chunk), b''):
                h.update(b)
    except OSError:
        return None
    return h.hexdigest()


def summarise(log, root, skip=()):
    """a build's recorded log -> its closure: {'reads': tracked files read or run, 'untracked': {path: sha256} (read,
    never written, not tracked, not under `skip` (worktree-relative prefixes: its own out folder) or the build cache),
    'listed': folders its code listed, 'wrote': how many paths it wrote, 'lines': the log's length}."""
    R, W, L, S = set(), set(), set(), {}
    n = 0
    for line in open(log, encoding='utf-8', errors='replace'):
        k, _, p = line.rstrip('\n').partition(' ')
        n += 1
        if not p:
            continue
        if k in ('R', 'X', 'M'):
            R.add(p)
        elif k == 'W':
            W.add(p)
        elif k == 'L':
            L.add(p.rstrip('/'))
        elif k == 'S':
            d, _, m = p.partition('\t')
            S.setdefault(d.rstrip('/'), set()).add(m)
    tracked = set((_git(root, 'ls-files', '-z') or '').split('\0')) - {''}
    skip = tuple(s.rstrip('/') + '/' for s in skip) + CACHES
    reads = sorted(p for p in R - W if p in tracked)
    untracked = {}
    for p in sorted(R - W - tracked):
        if p.startswith(skip) or '__pycache__/' in p or not os.path.isfile(os.path.join(root, p)):
            continue
        untracked[p] = sha256(os.path.join(root, p))
    L = {d for d in L if not (d + '/').startswith(skip) and '__pycache__' not in d}
    return {'schema': 1, 'reads': reads, 'untracked': untracked, 'listed': sorted(L),
            'scans': {d: sorted(m) for d, m in sorted(S.items())}, 'wrote': len(W), 'lines': n}


def _in_cone(path, cone):
    """a path inside a sparse checkout's cone (cone mode: the listed folders whole, and the files directly in the root
    and in each ancestor of a listed folder); cone None: a full checkout."""
    if cone is None:
        return True
    d = os.path.dirname(path)
    if not d:
        return True
    for c in cone:
        if path.startswith(c + '/') or c == d or c.startswith(d + '/'):
            return True
    return False


def changes(root, rev='HEAD', rev2=None):
    """the changes in a worktree: its index against REV (a merge not yet committed), or REV2 against REV ->
    [(status, path)] (A, M, D, T; renames as a delete and an add)."""
    a = ['diff', '--name-status', '--no-renames', '-z'] + (['--cached', rev] if rev2 is None else [rev, rev2])
    out = _git(root, *a) or ''
    f = out.split('\0')
    return [(f[i][:1], f[i + 1]) for i in range(0, len(f) - 1, 2)]


def cone(root):
    """the sparse checkout's folders, or None for a full checkout."""
    if (_git(root, 'config', '--bool', 'core.sparseCheckout') or '').strip() != 'true':
        return None
    return [l.strip().strip('/') for l in (_git(root, 'sparse-checkout', 'list') or '').splitlines() if l.strip()]


def _text(root, rev, p):
    """a file's text in the worktree (rev None) or at rev ('' when it isn't there)."""
    if rev is None:
        try:
            return open(os.path.join(root, p), encoding='utf-8', errors='replace').read()
        except OSError:
            return ''
    return _git(root, 'show', '%s:%s' % (rev, p)) or ''


def affected(C, changed, root, cone_dirs=None, rev='HEAD', new=None):
    """the changes (from changes()) that can reach a build whose closure is C -> [(path, why)], empty when none can.
    Untracked inputs are compared by content in root; a scanned file's old text is read at rev, its new one at new
    (None: the worktree)."""
    reads, listed = set(C.get('reads') or ()), set(C.get('listed') or ())
    scans = C.get('scans') or {}
    out = []
    for st, p in changed:
        marks = [m for d, ms in scans.items() if p.endswith('.py') and (not d or p.startswith(d + '/')) for m in ms]
        hit = next((m for m in marks if re.search(m, _text(root, new, p), re.M) or
                    re.search(m, _text(root, rev, p), re.M)), None) if marks else None
        if p in reads:
            out.append((p, 'the build read it'))
        elif os.path.dirname(p) in listed:
            out.append((p, 'in a folder the build lists (%s)' % (os.path.dirname(p) or '.')))
        elif hit:
            out.append((p, 'the build scans for %r, which it has' % hit))
        elif p.startswith(NEVER) or p.endswith(DOCS) or p.endswith('.py'):
            continue
        elif not _in_cone(p, cone_dirs):
            continue                                     # outside the checkout: the build can't read it
        else:
            out.append((p, 'a data file (Blender reads some unseen: counted whether or not it was recorded)'))
    for p, h in sorted((C.get('untracked') or {}).items()):
        if '__pycache__/' in p or p.startswith(CACHES):
            continue                                     # (a record from before these were left out)
        if sha256(os.path.join(root, p)) != h:
            out.append((p, 'an untracked input whose content differs'))
    return out
