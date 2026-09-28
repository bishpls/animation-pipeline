"""Builds that know their own processes: every Blender a charkit command starts is recorded in its output folder
(`.pid.json`: pid, command, start time) while it runs, so a build can be listed and stopped by its own record, never by a
pattern that would match another worktree's builds.

Builds also share a machine-wide number of slots (CHARKIT_BUILD_SLOTS, default 2: a Blender build of a character with
its QA holds a few GB, and several worktrees building at once ran a 16 GB machine out of memory). A build takes a free
slot (an flock on ~/.cache/charkit/slots/N, released by the OS when the process ends, crashed or not) or waits for one.

    python -m charkit ps                  # the running charkit builds (every worktree under the same parent folder)
    python -m charkit kill OUT_DIR        # stop that build's recorded process
"""
import fcntl, glob, json, os, signal, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIDFILE = '.pid.json'


SLOTS_DIR = os.path.expanduser('~/.cache/charkit/slots')


def slots():
    return max(1, int(os.environ.get('CHARKIT_BUILD_SLOTS', '2')))


def acquire_slot(label='build', poll=2.0):
    """take a machine-wide build slot, waiting while all are held -> the open lock file (keep it; closing releases)."""
    os.makedirs(SLOTS_DIR, exist_ok=True)
    waited = False
    while True:
        for i in range(slots()):
            f = open(os.path.join(SLOTS_DIR, str(i)), 'a+')
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                f.close()
                continue
            f.seek(0); f.truncate(); f.write('%d %s %s\n' % (os.getpid(), label, ROOT)); f.flush()
            if waited:
                sys.stderr.write('charkit: got build slot %d\n' % i)
            return f
        if not waited:
            sys.stderr.write('charkit: all %d build slots busy (CHARKIT_BUILD_SLOTS); waiting\n' % slots())
            waited = True
        time.sleep(poll)


def run(cmd, out, label='build', slot=True, **kw):
    """run a command to completion in a build slot, its pid recorded in `out`/.pid.json (removed when it ends)
    -> CompletedProcess."""
    os.makedirs(out, exist_ok=True)
    pf = os.path.join(out, PIDFILE)
    lock = acquire_slot(label) if slot else None
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **kw)
    json.dump({'pid': p.pid, 'label': label, 'cmd': cmd[:4] + ['...'], 'cwd': os.getcwd(), 'root': ROOT,
               'started': time.strftime('%Y-%m-%dT%H:%M:%S')}, open(pf, 'w'))
    try:
        so, se = p.communicate()
    finally:
        if os.path.exists(pf):
            os.remove(pf)
        if lock is not None:
            lock.close()
    return subprocess.CompletedProcess(cmd, p.returncode, so, se)


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def records(roots=None):
    """the recorded processes under charkit/out of this worktree and its sibling worktrees -> [(pidfile, record, alive)]."""
    roots = roots or sorted(glob.glob(os.path.join(os.path.dirname(ROOT), os.path.basename(ROOT).split('-')[0] + '*')))
    out = []
    for r in roots:
        for pf in glob.glob(os.path.join(r, 'charkit', 'out', '**', PIDFILE), recursive=True):
            try:
                rec = json.load(open(pf))
            except (OSError, ValueError):
                continue
            out.append((pf, rec, _alive(rec['pid'])))
    return out


def slot_holders():
    """who holds the build slots now -> [(slot, 'pid label root')]."""
    out = []
    for i in range(slots()):
        p = os.path.join(SLOTS_DIR, str(i))
        if not os.path.exists(p):
            continue
        with open(p, 'a+') as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(f, fcntl.LOCK_UN)
            except BlockingIOError:
                f.seek(0)
                out.append((i, f.read().strip()))
    return out


def ps(args=()):
    held = slot_holders()
    print('build slots: %d of %d busy' % (len(held), slots()))
    for i, who in held:
        print('  slot %d: %s' % (i, who))
    rs = records()
    if not rs:
        print('no charkit builds running'); return
    for pf, rec, alive in rs:
        print('%-7s %-6s %-8s %s  (%s)' % (rec['pid'], 'alive' if alive else 'stale', rec['label'], os.path.dirname(pf), rec['started']))


def kill(args):
    """stop the build recorded in an output folder (only that pid)."""
    pf = os.path.join(os.path.abspath(args[0]), PIDFILE)
    if not os.path.exists(pf):
        raise SystemExit('no running build recorded in %s' % args[0])
    rec = json.load(open(pf))
    if _alive(rec['pid']):
        os.kill(rec['pid'], signal.SIGTERM); print('stopped', rec['pid'])
    os.remove(pf)
