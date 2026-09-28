"""The build worker: one long-running Blender that keeps charkit loaded and takes build jobs over a local socket, so a
build skips Blender's start-up and keeps its warm render state (shaders compiled, add-ons registered).

    python -m charkit worker start | stop | status

`python -m charkit build` sends its job to the worker when one is running for this checkout, and starts a fresh Blender
otherwise (or with --no-worker). Each job starts clean (charkit/worker_blender.py): charkit's modules are dropped and
imported again, so edited code and module state never carry over, and the scene is reset to factory settings; the
datablock counts and charkit's own app handlers are then checked against the first clean state. A job that finds anything left
over says so (CHARKIT_WORKER_LEAK) and the worker restarts itself in place after it (same pid). The same spec built twice
in the worker, with another spec between, and once in a fresh Blender, trace-diff to no differences
(charkit/tests/worker_builds.py).

The worker is recorded in charkit/out/worker/.pid.json (charkit/procs.py: `ps` lists it; `kill charkit/out/worker` stops
it by that pid only), and each job in its output folder, with the worker's pid. `stop` asks the worker to exit and, if
it doesn't, signals the recorded pid after checking it is still this checkout's worker. Its log is
charkit/out/worker/worker.log; worker.json holds its pid, start time, jobs run and the job in hand.
"""
import hashlib, json, os, signal, socket, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, 'charkit', 'out', 'worker')
INFO = os.path.join(DIR, 'worker.json')
BLENDER = os.environ.get('BLENDER', '/Applications/Blender.app/Contents/MacOS/Blender')
ENTRY = os.path.join(ROOT, 'charkit', 'worker_blender.py')


def sock_path():
    """the worker's socket: in its folder, or (a path too long for a Unix socket) in the temp folder, named by checkout."""
    p = os.path.join(DIR, 'worker.sock')
    if len(p.encode()) < 100:
        return p
    return os.path.join(tempfile.gettempdir(), 'charkit-%s.sock' % hashlib.sha1(ROOT.encode()).hexdigest()[:12])


def info():
    try:
        return json.load(open(INFO))
    except (OSError, ValueError):
        return None


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _is_ours(pid):
    """is pid still this checkout's worker (not a reused pid)?"""
    r = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True)
    return ENTRY in r.stdout


def _connect(timeout=2.0, wait=10.0):
    """a connection to the running worker (waiting up to `wait` s while it restarts in place), or None."""
    t = time.time()
    while True:
        I = info()
        if not I or not _alive(I['pid']):
            return None
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect(I.get('sock') or sock_path())
            s.settimeout(None)
            return s
        except OSError:
            s.close()
            if time.time() - t > wait:
                return None
            time.sleep(0.25)


def _lines(s):
    buf = b''
    while True:
        b = s.recv(1 << 16)
        if not b:
            if buf:
                yield json.loads(buf)
            return
        buf += b
        while b'\n' in buf:
            l, buf = buf.split(b'\n', 1)
            if l:
                yield json.loads(l)


def request(msg, timeout=None):
    """one request -> the worker's replies (None when no worker runs)."""
    s = _connect()
    if s is None:
        return None
    try:
        s.settimeout(timeout)
        s.sendall((json.dumps(msg) + '\n').encode())
        return list(_lines(s))
    except OSError:
        return None
    finally:
        s.close()


def submit(job, out, label):
    """run a build job (build_blender's arguments) in the worker, recorded in `out` under the worker's pid. -> a
    CompletedProcess (stdout: the job's lines), or None when no worker is running or it died mid-job (the caller builds in
    a fresh Blender)."""
    from . import procs
    I = info()
    s = _connect()
    if s is None:
        return None
    lines, done, killed = [], None, False
    with procs.record(out, I['pid'], label + ' (worker)', ['blender-worker', ENTRY]) as pf:
        try:
            env = {k: v for k, v in os.environ.items() if k.startswith('CHARKIT_')}      # the cache's settings, per job
            s.sendall((json.dumps({'op': 'build', 'argv': job, 'env': env}) + '\n').encode())
            for m in _lines(s):
                if 'out' in m:
                    lines.append(m['out'])
                if m.get('done'):
                    done = m
        except (OSError, ValueError):
            done = None
        finally:
            s.close()
        killed = done is None and not os.path.exists(pf)          # `charkit kill OUT` took the record with it
    if killed:
        raise SystemExit('the build was stopped (python -m charkit kill): its worker, pid %d, with it' % I['pid'])
    if done is None:
        sys.stderr.write('the worker stopped mid-job; building in a fresh Blender\n')
        return None
    lines.append('CHARKIT_WORKER %s' % json.dumps({'pid': I['pid'], 'job': done.get('job'), 'seconds': done.get('seconds'),
                                                   'leak': done.get('leak')}))
    return subprocess.CompletedProcess(['worker'] + job, 0 if done.get('ok') else 1, '\n'.join(lines) + '\n', '')


def start(wait=60):
    from . import procs
    I = info()
    if I and _alive(I['pid']) and request({'op': 'ping'}, timeout=5):
        print('worker already running: pid %d' % I['pid']); return I
    os.makedirs(DIR, exist_ok=True)
    for p in (INFO, sock_path()):
        if os.path.exists(p):
            os.remove(p)
    log = open(os.path.join(DIR, 'worker.log'), 'a')
    cmd = [BLENDER, '-b', '--factory-startup', '--python', ENTRY, '--', sock_path(), INFO]
    p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True,
                         cwd=ROOT)
    procs.write(DIR, p.pid, 'worker', cmd)
    t = time.time()
    while time.time() - t < wait:
        I = info()
        if I and I['pid'] == p.pid and request({'op': 'ping'}, timeout=5):
            print('worker started: pid %d, socket %s' % (p.pid, I['sock'])); return I
        if p.poll() is not None:
            break
        time.sleep(0.2)
    stop(quiet=True)
    raise SystemExit('the worker did not start (see %s)' % os.path.join(DIR, 'worker.log'))


def stop(quiet=False, wait=20):
    I = info()
    rec = os.path.join(DIR, '.pid.json')
    pid = I['pid'] if I else (json.load(open(rec))['pid'] if os.path.exists(rec) else None)
    if pid is None or not _alive(pid):
        if not quiet:
            print('no worker running')
    else:
        request({'op': 'stop'}, timeout=5)
        t = time.time()
        while _alive(pid) and time.time() - t < wait:
            time.sleep(0.2)
        if _alive(pid) and _is_ours(pid):
            os.kill(pid, signal.SIGTERM)
            t = time.time()
            while _alive(pid) and time.time() - t < 10:
                time.sleep(0.2)
            if _alive(pid) and _is_ours(pid):
                os.kill(pid, signal.SIGKILL)
        if not quiet:
            print('worker stopped: pid %d' % pid)
    for p in (INFO, rec, sock_path()):
        if os.path.exists(p):
            os.remove(p)


def status():
    I = info()
    if not I:
        print('no worker running'); return None
    if not _alive(I['pid']):
        print('no worker running (stale record of pid %d cleared)' % I['pid'])
        stop(quiet=True)
        return None
    busy = I.get('busy')
    m = rss_mb(I['pid'])
    print('worker pid %d, up %s, %d jobs, %s, %s MB resident' % (
        I['pid'], _age(I['started']), I.get('jobs', 0),
        ('busy: %s (%s%s)' % (busy['label'], _age(busy['since']), '' if busy.get('slot') else ', waiting for a build slot'))
        if busy else 'idle (no build slot held)', '%.0f' % m if m else '?'))
    if I.get('last'):
        L = I['last']
        print('  last job: %s, %.1fs, %s%s' % (L.get('label'), L.get('seconds', 0), 'ok' if L.get('ok') else 'FAILED',
                                             ', LEAK' if L.get('leak') else ''))
    if I.get('restarts'):
        print('  restarted in place %d times (memory held idle, or state left over)' % I['restarts'])
    print('  socket %s, log %s' % (I['sock'], os.path.join(DIR, 'worker.log')))
    return I


def rss_mb(pid):
    """a process's resident memory, MB (None when it can't be read)."""
    r = subprocess.run(['ps', '-o', 'rss=', '-p', str(pid)], capture_output=True, text=True)
    try:
        return int(r.stdout.strip()) / 1024
    except ValueError:
        return None


def _age(t):
    s = time.time() - t
    return '%.0fs' % s if s < 120 else '%.0fm' % (s / 60) if s < 7200 else '%.1fh' % (s / 3600)


def main(args):
    cmd = args[0] if args else 'status'
    if cmd == 'start':
        start()
    elif cmd == 'stop':
        stop()
    elif cmd == 'status':
        status()
    else:
        raise SystemExit(__doc__)
