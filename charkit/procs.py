"""Builds that know their own processes: every Blender a charkit command starts is recorded in its output folder
(`.pid.json`: pid, command, start time) while it runs, so a build can be listed and stopped by its own record, never by a
pattern that would match another worktree's builds.

    python -m charkit ps                  # the running charkit builds (every worktree under the same parent folder)
    python -m charkit kill OUT_DIR        # stop that build's recorded process
"""
import glob, json, os, signal, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIDFILE = '.pid.json'


def run(cmd, out, label='build', **kw):
    """run a command to completion with its pid recorded in `out`/.pid.json (removed when it ends) -> CompletedProcess."""
    os.makedirs(out, exist_ok=True)
    pf = os.path.join(out, PIDFILE)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **kw)
    json.dump({'pid': p.pid, 'label': label, 'cmd': cmd[:4] + ['...'], 'cwd': os.getcwd(), 'root': ROOT,
               'started': time.strftime('%Y-%m-%dT%H:%M:%S')}, open(pf, 'w'))
    try:
        so, se = p.communicate()
    finally:
        if os.path.exists(pf):
            os.remove(pf)
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


def ps(args=()):
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
