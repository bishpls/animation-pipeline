"""Builds that know their own processes: every Blender a charkit command starts is recorded in its output folder
(`.pid.json`: pid, command, start time) while it runs, so a build can be listed and stopped by its own record, never by a
pattern that would match another worktree's builds.

Builds also share a machine-wide number of slots, and start only when the machine has memory to spare. A Clawd build
with QA and export peaks at 2.2 GB of Blender (measured), and five worktrees building at once ran a 16 GB machine out
of memory. A build takes a free slot (an flock on ~/.cache/charkit/slots/N, released by the OS when the process ends,
crashed or not) once at least CHARKIT_BUILD_MEM_GB (default 3) is available, or waits. The slot count is the
environment's CHARKIT_BUILD_SLOTS, else the machine setting `python -m charkit slots N` writes (waiting builds pick it
up), else 2.

    python -m charkit ps                  # the slots, who holds them, the running builds (every worktree)
    python -m charkit kill OUT_DIR        # stop that build's recorded process
    python -m charkit wait OUT_DIR [--timeout S]   # until that build ends (by its recorded pid)
    python -m charkit slots [N]           # show or set the machine's slot count

The build worker (charkit/worker.py) is recorded the same way in charkit/out/worker/, and a build it runs is recorded
in its output folder with the worker's pid: stopping that build stops the worker. The worker takes a slot per job
(acquire_slot, with its memory check) and releases it between jobs.

Gates before sweeps. Three priorities: a gate's (CHARKIT_SLOT_PRIO=gate: set for a box job of kind gate or pregate by
charkit/boxjob.py, and read from the tree for a gate's or pre-gate's clone under /srv/work), normal (the default) and
background (low: sweeps, optimize and their workers, which call background()). A free slot goes to a waiting gate
first (nothing else takes one while a gate waits), and a background holder gives its slot back between rows when a
gate waits for one (Slot.yield_point: an optimize run's persistent workers held their slots for an hour while gates
queued behind them), then waits for a slot again behind it. Background work also runs at CPU niceness 10 (NICE), so on
a box whose cores are oversubscribed everything else gets the CPU first. CHARKIT_SLOT_YIELD=0: holders never yield.
"""
import contextlib, fcntl, glob, json, os, signal, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIDFILE = '.pid.json'


SLOTS_DIR = os.environ.get('CHARKIT_SLOTS_DIR') or os.path.expanduser('~/.cache/charkit/slots')
PRIO_ENV = 'CHARKIT_SLOT_PRIO'
PRIO = {'low': 0, 'normal': 1, 'gate': 2}
NICE = 10                            # background work's CPU niceness (nice -n 10)
GATE_ROOTS = ('/srv/work/gates/', '/srv/work/pregates/')   # gates' and pre-gates' clones (remote.gate, .pregate)


def priority(env=None):
    """this process's slot priority (PRIO): CHARKIT_SLOT_PRIO, else a gate's when charkit runs from a gate's or a
    pre-gate's clone, else normal."""
    v = (env if env is not None else os.environ).get(PRIO_ENV)
    if v in PRIO:
        return PRIO[v]
    return PRIO['gate'] if (ROOT + '/').startswith(GATE_ROOTS) else PRIO['normal']


def background(nice=NICE):
    """this process, and what it starts, as background work (sweeps, optimize and their workers): build slots taken
    at the lowest priority (given back to a waiting gate between rows) and the CPU at niceness `nice` (raised only,
    never lowered) -> the niceness now."""
    os.environ[PRIO_ENV] = 'low'
    try:
        cur = os.nice(0)
        if cur < nice:
            cur = os.nice(nice - cur)
    except OSError:
        cur = None
    return cur


def _waiter_prio(w):
    """a wait record's priority: its own, else a gate's when it waits from a gate's tree, else normal."""
    p = w.get('prio')
    if isinstance(p, int):
        return p
    return PRIO['gate'] if (str(w.get('root') or '') + '/').startswith(GATE_ROOTS) else PRIO['normal']


def outranked(prio, why=None):
    """the live waiters of a priority above prio (slots/wait/*.json; only those waiting for slots when why='slots')
    -> [record]."""
    out = []
    for f in glob.glob(os.path.join(SLOTS_DIR, 'wait', '*.json')):
        try:
            w = json.load(open(f))
            pid = int(w['pid'])
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if pid == os.getpid() or not _alive(pid) or _waiter_prio(w) <= prio:
            continue
        if why and w.get('why') != why:
            continue
        out.append(w)
    return out


def slots():
    if os.environ.get('CHARKIT_BUILD_SLOTS'):
        return max(1, int(os.environ['CHARKIT_BUILD_SLOTS']))
    try:
        return max(1, int(open(os.path.join(SLOTS_DIR, 'count')).read().strip()))
    except (OSError, ValueError):
        return 2


def available_gb():
    """memory the machine can hand out now (free + inactive + speculative pages; macOS vm_stat), or None elsewhere."""
    try:
        out = subprocess.run(['vm_stat'], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    page = 16384
    vals = {}
    for line in out.splitlines():
        if 'page size of' in line:
            page = int(line.split('page size of')[1].split()[0])
        elif ':' in line:
            k, v = line.split(':', 1)
            try:
                vals[k.strip()] = int(v.strip().rstrip('.'))
            except ValueError:
                pass
    pages = sum(vals.get(k, 0) for k in ('Pages free', 'Pages inactive', 'Pages speculative'))
    return pages * page / 2 ** 30 if vals else None


def _waiting(label, why, since, prio=None):
    """slots/wait/<pid>.json while this process waits (the box's load sampler counts the queue from these; a lower
    priority's acquire_slot defers to it, a background holder yields to it)."""
    try:
        d = os.path.join(SLOTS_DIR, 'wait')
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, '%d.json' % os.getpid())
        rec = {'pid': os.getpid(), 'label': label, 'root': ROOT, 'since': since, 'why': why,
               'prio': priority() if prio is None else prio}
        tmp = p + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(rec, f)
        os.replace(tmp, p)                  # (read by other processes: never half written)
        return p
    except OSError:
        return None


def _got(slot, label, since, why):
    """one line per slot taken in slots/waits.jsonl: how long it waited and for what (slots, memory, or nothing)."""
    try:
        with open(os.path.join(SLOTS_DIR, 'waits.jsonl'), 'a') as f:
            f.write(json.dumps({'at': round(time.time(), 1), 'pid': os.getpid(), 'label': label,
                                'root': os.path.basename(ROOT), 'slot': slot, 'of': slots(),
                                'waited': round(time.time() - since, 1), 'why': why}) + '\n')
    except OSError:
        pass


HELD = 'CHARKIT_SLOT_HELD'           # set (to the holder's pid) while a build holds its slot: what it starts takes none


class _Held:
    """the slot a build already holds, standing in for a lock of its own (closing it releases nothing)."""

    def close(self):
        pass

    def claim(self):
        return None

    def yield_point(self, poll=2.0, log=None):
        return 0.0


@contextlib.contextmanager
def build_slot(label='build'):
    """a machine-wide build slot held for the block: a whole build, its produced references, venv steps, Blender and
    QA (only Blender took one before, and the Python stages ran unbounded: 8.3 builds at once on the 8-slot box, load
    32.6), with CHARKIT_SLOT_HELD set meanwhile, so what it starts (its Blender, a worker's job, a build inside it)
    doesn't wait for a second slot. Inside another's block: nothing more taken."""
    if os.environ.get(HELD):
        yield None
        return
    lock = acquire_slot(label)
    os.environ[HELD] = str(os.getpid())
    try:
        yield lock
    finally:
        os.environ.pop(HELD, None)
        lock.close()


THREAD_VARS = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMBA_NUM_THREADS', 'BLIS_NUM_THREADS',
               'VECLIB_MAXIMUM_THREADS', 'LP_NUM_THREADS')


def thread_cap():
    """the threads each of a build's pools gets (numba, BLAS, OpenMP, llvmpipe: THREAD_VARS): CHARKIT_THREADS (a
    number, or 'off'), else on a machine of 16 cores or more a slot's share of them (max(2, min(8, cores // 8)): 4 on
    the 32-core box, 8 slots), else None (uncapped: the laptop). Milestone A's A/B on the box: capped at 4, the same
    wall time at 527 s of CPU against 1,313 s, outputs bit-identical: uncapped pools spin."""
    v = os.environ.get('CHARKIT_THREADS', '')
    if v == 'off':
        return None
    if v:
        return max(1, int(v))
    n = os.cpu_count() or 1
    return max(2, min(8, n // 8)) if n >= 16 else None


def thread_env(n=None):
    """the environment that caps a process's pools at n threads (default thread_cap()), OpenMP's waits passive."""
    n = thread_cap() if n is None else n
    if not n:
        return {}
    return dict({k: str(n) for k in THREAD_VARS}, OMP_WAIT_POLICY='PASSIVE')


def cap_threads():
    """this process and what it starts capped (thread_env), called before numpy, numba or a BLAS loads (they read these
    once); a variable already set wins (a gate's own caps). -> the cap in force, or None."""
    for k, v in thread_env().items():
        os.environ.setdefault(k, v)
    v = os.environ.get('NUMBA_NUM_THREADS')
    return int(v) if v and v.isdigit() else None


class Slot:
    """a held build slot (acquire_slot): close() gives it back (as the process ending does). A background holder (a
    sweep's shard, an optimize worker) calls yield_point() between rows: when a gate waits for a slot it gives this
    one back and waits for a slot again behind the gate."""

    def __init__(self, f, index, label, prio):
        self.f, self.index, self.label, self.prio = f, index, label, prio
        self.yields = 0

    def close(self):
        if self.f is not None:
            self.f.close()
            self.f = None

    @property
    def closed(self):
        return self.f is None

    def claim(self):
        """a gate waiting for a slot that no other holder has given one to yet, claimed for this one (a background holder
        only, and not with CHARKIT_SLOT_YIELD=0) -> its wait record, or None. One holder gives way per waiting gate:
        the claim is slots/wait/<gate pid>.given, made once (O_EXCL) for that wait (its `since`)."""
        if self.f is None or self.prio >= PRIO['normal'] or os.environ.get('CHARKIT_SLOT_YIELD', '1') == '0':
            return None
        for g in sorted(outranked(PRIO['gate'] - 1, why='slots'), key=lambda w: w.get('since') or 0):
            mark = os.path.join(SLOTS_DIR, 'wait', '%s.given' % g['pid'])
            stamp = '%s %d\n' % (g.get('since'), os.getpid())
            try:
                fd = os.open(mark, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            except FileExistsError:
                try:
                    old = open(mark).read().split()
                except OSError:
                    continue
                if old and old[0] == str(g.get('since')) and len(old) > 1 and old[1].isdigit() and _alive(int(old[1])):
                    continue                    # (another holder gives this gate its slot)
                tmp = mark + '.%d' % os.getpid()     # a claim left from an earlier wait, or by a holder now gone
                open(tmp, 'w').write(stamp)
                os.replace(tmp, mark)
                return g
            except OSError:
                continue
            os.write(fd, stamp.encode())
            os.close(fd)
            return g
        return None

    def give(self, gate, poll=2.0, log=None):
        """this slot given to the claimed gate (claim()), and one taken again behind it -> the seconds without one."""
        t0 = time.time()
        (log or (lambda m: sys.stderr.write(m + '\n')))(
            'charkit: build slot %d given to a waiting gate (%s pid %s); waiting for a slot again' % (
                self.index, gate.get('label', '?'), gate['pid']))
        self.close()
        again = acquire_slot(self.label, poll=poll, prio=self.prio, why='yield')
        self.f, self.index = again.f, again.index
        self.yields += 1
        return time.time() - t0

    def yield_point(self, poll=2.0, log=None):
        """between rows: when a gate waits for a slot (claim()), give it this one and take one again behind it -> the
        seconds given up (0.0: nothing was waiting)."""
        g = self.claim()
        return self.give(g, poll, log) if g else 0.0


def acquire_slot(label='build', poll=2.0, mem=None, prio=None, why=None):
    """take a machine-wide build slot once enough memory is free, waiting while all slots are held, memory is short or
    a gate waits for one (a free slot goes to a waiting gate first; prio: priority()'s) -> a Slot (keep it; closing
    releases). The wait is recorded (slots/wait/<pid>.json while waiting, with its reason and priority, a line in
    slots/waits.jsonl once a slot is taken): the numbers behind the box's capacity (charkit/boxjob.py). Inside a build
    that holds one (build_slot: CHARKIT_SLOT_HELD) -> a stand-in: the build's slot covers it."""
    if os.environ.get(HELD):
        return _Held()
    os.makedirs(SLOTS_DIR, exist_ok=True)
    need = float(os.environ.get('CHARKIT_BUILD_MEM_GB', '3')) if mem is None else mem
    prio = priority() if prio is None else prio
    waited, wf, t0 = False, None, time.time()

    def wait(reason, msg):
        nonlocal waited, why, wf
        if not waited or why != reason:
            if not waited:
                sys.stderr.write(msg)
            waited, why = True, reason
            wf = _waiting(label, reason, t0, prio)
    try:
        while True:
            free = available_gb()
            if free is not None and free < need:
                wait('memory', 'charkit: %.1f GB free, waiting for %.1f GB (CHARKIT_BUILD_MEM_GB)\n' % (free, need))
                time.sleep(poll)
                continue
            if prio < PRIO['gate'] and outranked(PRIO['gate'] - 1):
                wait(why if why == 'yield' else 'gate', 'charkit: a gate waits for a build slot: it goes first; waiting\n')
                time.sleep(poll)
                continue
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
                _got(i, label, t0, why)
                return Slot(f, i, label, prio)
            wait('slots', 'charkit: all %d build slots busy (CHARKIT_BUILD_SLOTS); waiting\n' % slots())
            time.sleep(poll)
    finally:
        if wf:
            for f in (wf, wf[:-len('.json')] + '.given'):
                try:
                    os.remove(f)
                except OSError:
                    pass


def write(out, pid, label, cmd):
    """record a process in `out`/.pid.json. -> the record's path."""
    os.makedirs(out, exist_ok=True)
    pf = os.path.join(out, PIDFILE)
    json.dump({'pid': pid, 'label': label, 'cmd': cmd[:4] + ['...'], 'cwd': os.getcwd(), 'root': ROOT,
               'started': time.strftime('%Y-%m-%dT%H:%M:%S')}, open(pf, 'w'))
    return pf


@contextlib.contextmanager
def record(out, pid, label, cmd):
    """`out`/.pid.json names `pid` while the block runs."""
    pf = write(out, pid, label, cmd)
    try:
        yield pf
    finally:
        if os.path.exists(pf):
            os.remove(pf)


def run(cmd, out, label='build', slot=True, **kw):
    """run a command to completion in a build slot, its pid recorded in `out`/.pid.json (removed when it ends)
    -> CompletedProcess."""
    lock = acquire_slot(label) if slot else None
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **kw)
        with record(out, p.pid, label, cmd):
            so, se = p.communicate()
    finally:
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


def set_slots(args):
    """show or set the machine's slot count (CHARKIT_BUILD_SLOTS in the environment still wins)."""
    os.makedirs(SLOTS_DIR, exist_ok=True)
    if args:
        open(os.path.join(SLOTS_DIR, 'count'), 'w').write(str(max(1, int(args[0]))) + '\n')
    free = available_gb()
    print('build slots: %d%s; %s GB available' % (slots(), ' (from CHARKIT_BUILD_SLOTS)' if os.environ.get('CHARKIT_BUILD_SLOTS') else '',
                                                   '%.1f' % free if free is not None else '?'))


def ps(args=()):
    held = slot_holders()
    free = available_gb()
    print('build slots: %d of %d busy; %s GB available' % (len(held), slots(), '%.1f' % free if free is not None else '?'))
    for i, who in held:
        print('  slot %d: %s' % (i, who))
    try:
        from . import cache
        print(cache.size_line())
    except Exception:
        pass
    rs = records()
    if not rs:
        print('no charkit builds running'); return
    for pf, rec, alive in rs:
        print('%-7s %-6s %-8s %s  (%s)' % (rec['pid'], 'alive' if alive else 'stale', rec['label'], os.path.dirname(pf), rec['started']))


def wait(args):
    """block until the build recorded in an output folder ends (its pid gone), or --timeout seconds pass; exit 0 when it
    ended, 2 on timeout. Waiting on the recorded pid can't match the waiting shell itself, as `pgrep -f` does."""
    out = os.path.abspath(args[0])
    t_max = float(args[args.index('--timeout') + 1]) if '--timeout' in args else 3600.0
    pf = os.path.join(out, PIDFILE)
    t0 = time.time()
    while time.time() - t0 < t_max:
        if not os.path.exists(pf):
            print('ended', out); return
        try:
            pid = json.load(open(pf))['pid']
        except (OSError, ValueError, KeyError):
            pid = None
        if pid is not None and not _alive(pid):
            print('ended (stale record)', out); return
        time.sleep(2)
    print('still running after %.0f s' % t_max, out); raise SystemExit(2)


def kill(args):
    """stop the build recorded in an output folder (only that pid)."""
    pf = os.path.join(os.path.abspath(args[0]), PIDFILE)
    if not os.path.exists(pf):
        raise SystemExit('no running build recorded in %s' % args[0])
    rec = json.load(open(pf))
    if _alive(rec['pid']):
        os.kill(rec['pid'], signal.SIGTERM); print('stopped', rec['pid'])
    os.remove(pf)
