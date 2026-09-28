"""Blender entry for the build worker (charkit/worker.py): serve build jobs on a Unix socket until asked to stop.
    blender -b --factory-startup --python charkit/worker_blender.py -- SOCKET INFO.json

Each job: charkit's modules dropped and imported afresh, the scene reset to factory settings, the datablock counts and
charkit's own app handlers checked against the first clean state (a difference is reported as CHARKIT_WORKER_LEAK and the worker restarts
itself in place after the job), then charkit.build_blender.main(job) with its output streamed back line by line.
This file stays outside the purge: it holds the loop, and nothing of charkit between jobs.
"""
import importlib, json, os, socket, sys, time, traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import bpy

ARGS = sys.argv[sys.argv.index('--') + 1:]
SOCK, INFO = ARGS[0], ARGS[1]
STATE = {'pid': os.getpid(), 'started': time.time(), 'sock': SOCK, 'root': ROOT, 'jobs': 0, 'busy': None, 'last': None,
         'blender': bpy.app.version_string}


def save_info():
    tmp = INFO + '.tmp'
    json.dump(STATE, open(tmp, 'w'), indent=1)
    os.replace(tmp, INFO)


def purge():
    for k in [k for k in sys.modules if k == 'charkit' or k.startswith('charkit.')]:
        del sys.modules[k]
    importlib.invalidate_caches()


def clean():
    """charkit unloaded, the scene at factory settings. -> the counts a later job's clean state must match."""
    purge()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    n = {c: len(getattr(bpy.data, c)) for c in dir(bpy.data)
         if isinstance(getattr(bpy.data, c, None), bpy.types.bpy_prop_collection)}
    # charkit's own app handlers (Blender's bundled add-ons add theirs again at every factory reset, fresh builds too)
    n['handlers'] = sum(1 for k in dir(bpy.app.handlers) if isinstance(getattr(bpy.app.handlers, k), list)
                        for f in getattr(bpy.app.handlers, k) if _ours(f))
    return n


def _ours(f):
    code = getattr(f, '__code__', None)
    return getattr(f, '__module__', '').startswith('charkit') or bool(code and code.co_filename.startswith(ROOT))


class Stream:
    """a job's stdout and stderr, line by line to the client (and to the worker's log)."""

    def __init__(self, conn, kind):
        self.conn, self.kind, self.buf = conn, kind, ''

    def write(self, s):
        sys.__stdout__.write(s)
        self.buf += s
        while '\n' in self.buf:
            l, self.buf = self.buf.split('\n', 1)
            self.send({self.kind: l})
        return len(s)

    def send(self, m):
        try:
            self.conn.sendall((json.dumps(m) + '\n').encode())
        except OSError:
            pass                                             # the client went away: finish the job anyway

    def flush(self):
        sys.__stdout__.flush()


def job(conn, msg, base):
    t = time.time()
    now = clean()
    leak = {k: [base.get(k), v] for k, v in now.items() if base.get(k) != v}
    STATE['busy'] = {'label': ' '.join(os.path.basename(a) for a in msg['argv'][:2]), 'since': t}
    save_info()
    out, err = Stream(conn, 'out'), Stream(conn, 'out')
    old = sys.stdout, sys.stderr
    env0 = {k: v for k, v in os.environ.items() if k.startswith('CHARKIT_')}
    for k in env0:
        del os.environ[k]
    os.environ.update(msg.get('env') or {})                  # the client's CHARKIT_* settings, for this job only
    sys.stdout, sys.stderr = out, err
    ok = True
    try:
        if leak:
            print('CHARKIT_WORKER_LEAK', json.dumps(leak))
        import charkit.build_blender as bb
        bb.main(list(msg['argv']), worker=True, t0=t)
    except BaseException:
        ok = False
        traceback.print_exc()
    finally:
        sys.stdout, sys.stderr = old
        for k in [k for k in os.environ if k.startswith('CHARKIT_')]:
            del os.environ[k]
        os.environ.update(env0)
    STATE['jobs'] += 1
    STATE['busy'] = None
    STATE['last'] = {'label': ' '.join(os.path.basename(a) for a in msg['argv'][:2]), 'seconds': round(time.time() - t, 2),
                     'ok': ok, 'leak': bool(leak)}
    save_info()
    out.send({'done': True, 'ok': ok, 'seconds': round(time.time() - t, 2), 'job': STATE['jobs'], 'leak': leak or None})
    return bool(leak)


def serve():
    base = clean()
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    if os.path.exists(SOCK):
        os.remove(SOCK)
    srv.bind(SOCK)
    os.chmod(SOCK, 0o600)
    srv.listen(8)
    save_info()
    print('charkit worker: pid %d on %s' % (os.getpid(), SOCK), flush=True)
    restart = False
    while True:
        conn, _ = srv.accept()
        try:
            line = b''
            while not line.endswith(b'\n'):
                b = conn.recv(1 << 16)
                if not b:
                    break
                line += b
            if not line.strip():
                continue
            msg = json.loads(line)
            op = msg.get('op')
            if op == 'ping':
                conn.sendall((json.dumps({'pong': True, 'pid': os.getpid(), 'jobs': STATE['jobs']}) + '\n').encode())
            elif op == 'stop':
                conn.sendall((json.dumps({'stopping': True}) + '\n').encode())
                conn.close()
                break
            elif op == 'build':
                restart = job(conn, msg, base)
        except Exception:
            traceback.print_exc()
        finally:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            conn.close()
        if restart:
            break
    srv.close()
    if os.path.exists(SOCK):
        os.remove(SOCK)
    if restart:
        print('charkit worker: state left over after a job; restarting in place', flush=True)
        sys.stdout.flush()
        os.execv(bpy.app.binary_path, [bpy.app.binary_path, '-b', '--factory-startup', '--python', __file__, '--'] + ARGS)
    if os.path.exists(INFO):
        os.remove(INFO)


serve()
