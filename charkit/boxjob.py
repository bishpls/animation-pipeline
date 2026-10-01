"""Box jobs that outlive their ssh, and the boxes' load, measured (standard library only, Python 3.9+: the box runs this
file with its system python3).

A build or gate used to run inside the ssh session that started it and died with it: two gates were lost to "broken
pipe" while the build box sat at load 56 on 32 vCPUs (2026-09-30). Now the laptop (charkit/remote.py) sends a job to the
box, which runs it detached, and follows its log; a dropped connection only drops the follow, which reattaches at the
byte it had reached. The job never runs twice.

A job is a directory, JOBS/<jid>/ (/srv/work/.jobs on the box):
    run.sh          the job's shell script (from the laptop)
    meta.json       who sent it: kind, worktree, label, the bucket (for publishing), when
    boxjob.py       this file, and bucketsync.py (charkit/bucketsync.py, for publishing outputs): the job's own copies
    claim           created once (O_EXCL) by the first `start`: a retried start never launches a second run
    pid             "SUPERVISOR JOB": the supervisor (setsid, so no ssh session owns it) and the job's process group
    log             the job's stdout and stderr
    exit            "RC ENDED_EPOCH", written (atomically) when the job ends

Box side (python3 JOBS/<jid>/boxjob.py CMD ...):
    start JID                   launch the job detached, once; prints BOXJOB-STARTED or BOXJOB-RUNNING
    follow JID OFFSET           the log from byte OFFSET as frames until the job ends: "D <n>\\n" + n bytes, "H <t>\\n" (a
                                heartbeat every HEARTBEAT s), then "E <rc>\\n" (or "E lost\\n": no exit and no supervisor)
    list [--days N]             every job as a JSON line (running, done, lost), finished ones from the last N days;
                                a running job's alarms in `flags` (silent past its limit, past 2x its expected time)
    kill JID                    SIGTERM to the job's processes (its process group and descendants; nothing else)
    sample [--boot]             one load sample into LOAD/load-YYYYMMDD.jsonl (cron, once a minute and at boot; see below)
    silences [--days N]         each kind's longest silences (the sampler's `quiet`), one JSON line per kind
    supervise JID charkit-job   (internal) the detached supervisor; its command line names charkit so the build box's
                                idle stop (`pgrep -f charkit`) counts a running job as busy

The load sampler (task: a data-driven call on build-box capacity). Once a minute (a user crontab line installed by the
first job; its command line doesn't name charkit, so it never keeps a box awake), and once at boot (an @reboot line beside
it: a `boot` event, so a stop reads as a stop and the first minute after a start has its CPU share), it appends to
LOAD/load-<UTC day>.jsonl, each sample with the kernel's boot time (`boot`: a gap between two samples of one boot is the
sampler missing minutes, across two boots the box was down):
the 1/5/15-minute load, CPU busy share since the last sample (user, system, iowait), memory used and available, the
build slots (~/.cache/charkit/slots: count and holders, read from /proc/locks without touching the locks), builds waiting
for a slot (charkit.procs writes slots/wait/<pid>.json while it waits and slots/waits.jsonl when it gets one), running
jobs and each one's silence (`quiet`: its log's bytes and the seconds since its last write, the stall alarm's record),
the processes and their CPU share by class (charkit build, qa, gate, ...; Blender; other: from /proc/PID/stat, so the
work outside the slots shows too: a build's Python stages run before it takes a slot, which only its Blender step
holds), GPU use where nvidia-smi exists, and /srv/work's free disk. A job's supervisor publishes LOAD
to the bucket when the job ends (bucketsync publish --name load-<host>), and `python -m charkit remote load` reads it.
"""
import glob, json, os, signal, subprocess, sys, time

VERSION = 4
JOBS = os.environ.get('BOXJOB_ROOT', '/srv/work/.jobs')
LOAD = os.environ.get('BOXJOB_LOAD', '/srv/work/.load')
WORK = os.environ.get('BOXJOB_WORK', '/srv/work')
SLOTS_DIR = os.path.expanduser('~/.cache/charkit/slots')     # charkit.procs.SLOTS_DIR on the box
HEARTBEAT = 15                                             # s between heartbeats while a followed job is quiet
FRAME = 64 << 10
KEEP_DAYS = 14                                             # finished jobs' directories are kept this long
LOAD_DAYS = 60                                             # and the daily load logs
CRON_MARK = '# boxjob load sampler'
# The stall alarm (`remote jobs`, never a kill). A running job whose log hasn't been written for its limit is flagged
# SILENT: its own (meta 'stall_min', `remote --stall MIN`), else its kind's, else 20 min. The kinds that print only at
# the end get longer, from the box's kept jobs on 2026-10-01 (those that ended rc 0): a gate prints 3 lines at its end
# (100 of 102: silent throughout; p90 17 min, max 36.5), a pregate one (max 20 min); the others write as they go. A job
# may declare the duration it expects (meta 'expect_min', `remote --expect MIN`): flagged OVERRUN past 2x that. The
# load sampler records each running job's silence every minute (`quiet`), and `remote jobs --silences` reads, per kind,
# the longest silence of the jobs that ended well: the numbers these limits are checked against.
STALL_MIN = {'default': 20, 'gate': 45, 'pregate': 30}
OVERRUN = 2.0
GATE_KINDS = ('gate', 'pregate')                           # their builds take build slots first (charkit.procs PRIO)


# ------------------------------------------------------------------------------------------------------------- helpers
def jdir(jid):
    if not jid or '/' in jid or jid.startswith('.') or jid == 'bin':
        raise SystemExit('boxjob: bad job id %r' % jid)
    return os.path.join(JOBS, jid)


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _read(path, default=None):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return default


def _write(path, text):
    """a small file, atomically (a reader sees the old content or the new, never half)."""
    tmp = '%s.%d.tmp' % (path, os.getpid())
    with open(tmp, 'w') as f:
        f.write(text)
    os.replace(tmp, path)


def pids(d):
    """(supervisor pid, job pid) from the job's pid file, or (None, None)."""
    p = (_read(os.path.join(d, 'pid')) or '').split()
    try:
        return int(p[0]), (int(p[1]) if len(p) > 1 else None)
    except (IndexError, ValueError):
        return None, None


def exit_of(d):
    """(rc, ended epoch) once the job has ended, else None."""
    e = (_read(os.path.join(d, 'exit')) or '').split()
    if not e:
        return None
    try:
        return int(e[0]), float(e[1]) if len(e) > 1 else None
    except ValueError:
        return None


def state(d):
    """'pending' (not started), 'running', 'done' or 'lost' (no exit code and no supervisor: the box stopped under it)."""
    if not os.path.exists(os.path.join(d, 'claim')):
        return 'pending'
    if exit_of(d) is not None:
        return 'done'
    sup, _ = pids(d)
    if sup is None:
        # claimed a moment ago, the supervisor not yet recorded
        return 'running' if time.time() - os.path.getmtime(os.path.join(d, 'claim')) < 60 else 'lost'
    if alive(sup):
        return 'running'
    return 'done' if exit_of(d) is not None else 'lost'


def _proc_children():
    """{ppid: [pid, ...]} over /proc (Linux); {} elsewhere."""
    out = {}
    for s in glob.glob('/proc/[0-9]*/stat'):
        try:
            with open(s) as f:
                t = f.read()
            pid = int(t.split(' ', 1)[0])
            ppid = int(t.rsplit(')', 1)[1].split()[1])
            out.setdefault(ppid, []).append(pid)
        except (OSError, ValueError, IndexError):
            pass
    return out


def descendants(pid):
    kids, out, todo = _proc_children(), [], [pid]
    while todo:
        p = todo.pop()
        for c in kids.get(p, ()):
            out.append(c)
            todo.append(c)
    return out


# ------------------------------------------------------------------------------------------------------------- the job
def start(jid):
    """launch the job detached, once. A retried start (the first one's ssh dropped) finds the claim and only reports."""
    d = jdir(jid)
    if not os.path.exists(os.path.join(d, 'run.sh')):
        print('BOXJOB-NOJOB %s' % jid)
        return 2
    try:
        fd = os.open(os.path.join(d, 'claim'), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        print('BOXJOB-RUNNING %s %s' % (jid, state(d)))
        return 0
    os.write(fd, ('%d %f\n' % (os.getpid(), time.time())).encode())
    os.close(fd)
    with open(os.path.join(d, 'supervisor.log'), 'ab') as err:
        p = subprocess.Popen([sys.executable, os.path.abspath(__file__), 'supervise', jid, 'charkit-job'], cwd=d,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=err, close_fds=True,
                             start_new_session=True)
    print('BOXJOB-STARTED %s %d' % (jid, p.pid))
    try:
        install_sampler(d)
    except Exception as e:                                  # never fails the job
        print('boxjob: sampler not installed: %s' % e, file=sys.stderr)
    prune()
    return 0


def supervise(jid):
    """(detached) run the job, record its exit code, publish the load log."""
    d = jdir(jid)
    meta = json.loads(_read(os.path.join(d, 'meta.json'), '{}') or '{}')
    env = dict(os.environ, BOXJOB_ID=jid, BOXJOB_DIR=d)
    if meta.get('kind') in GATE_KINDS:                      # its builds take a free slot first (charkit.procs)
        env.setdefault('CHARKIT_SLOT_PRIO', 'gate')
    with open(os.path.join(d, 'log'), 'ab', buffering=0) as log:
        p = subprocess.Popen(['bash', os.path.join(d, 'run.sh')], cwd=d, stdin=subprocess.DEVNULL, stdout=log,
                             stderr=subprocess.STDOUT, env=env, preexec_fn=os.setpgrp)
        _write(os.path.join(d, 'pid'), '%d %d\n' % (os.getpid(), p.pid))
        signal.signal(signal.SIGTERM, lambda *a: _kill_job(d))
        t0 = time.time()
        touched = t0
        while True:
            try:
                rc = p.wait(timeout=60)
                break
            except subprocess.TimeoutExpired:
                # a long job keeps the box's idle stop off (its keepalive, 2 h): the build box's idle check also sees
                # this process's command line, the render box's doesn't
                if time.time() - t0 > 3600 and time.time() - touched > 1800:
                    try:
                        open(os.path.join(WORK, '.keepalive'), 'a').close()
                        os.utime(os.path.join(WORK, '.keepalive'))
                    except OSError:
                        pass
                    touched = time.time()
    rc = 128 - rc if rc < 0 else rc
    _write(os.path.join(d, 'exit'), '%d %f\n' % (rc, time.time()))
    publish_load(d, meta)
    return 0


def _kill_job(d):
    sup, job = pids(d)
    if not job:
        return []
    victims = [job] + descendants(job)
    try:
        os.killpg(job, signal.SIGTERM)
    except OSError:
        pass
    for v in victims:
        try:
            os.kill(v, signal.SIGTERM)
        except OSError:
            pass
    return victims


def kill(jid):
    d = jdir(jid)
    if state(d) != 'running':
        print('boxjob: %s is %s, nothing to stop' % (jid, state(d)))
        return 1
    v = _kill_job(d)
    print('boxjob: sent SIGTERM to %s (%d processes)' % (jid, len(v)))
    return 0


def follow(jid, offset=0, out=None, heartbeat=HEARTBEAT, poll=0.5):
    """the log from byte offset as frames until the job ends (see the module's docstring)."""
    out = out or sys.stdout.buffer
    d = jdir(jid)
    if not os.path.exists(os.path.join(d, 'claim')):
        out.write(b'E nojob\n')
        out.flush()
        return 2
    log = os.path.join(d, 'log')
    last = time.time()
    while True:
        st = state(d)                          # read before the log: a job that ends now has all its bytes there
        data = b''
        try:
            with open(log, 'rb') as f:
                f.seek(offset)
                data = f.read(FRAME)
        except OSError:
            pass
        if data:
            out.write(b'D %d\n' % len(data))
            out.write(data)
            out.flush()
            offset += len(data)
            last = time.time()
            continue
        if st == 'done':
            out.write(b'E %d\n' % exit_of(d)[0])
            out.flush()
            return 0
        if st == 'lost':
            out.write(b'E lost\n')
            out.flush()
            return 0
        if time.time() - last >= heartbeat:
            out.write(b'H %d\n' % int(time.time()))
            out.flush()
            last = time.time()
        time.sleep(poll)


class Frames:
    """the laptop's side of follow: feed it bytes as they arrive; it hands log bytes to on_data as soon as they come (a
    frame cut by a dropped connection still counts what arrived: the next follow resumes at `got`) and keeps the exit
    code. reset() before feeding a new connection's bytes."""
    def __init__(self, on_data):
        self.on_data = on_data
        self.end = None            # the E frame's value: an int rc, 'lost' or 'nojob'
        self.got = 0               # log bytes delivered
        self.frames = 0
        self.reset()

    def reset(self):
        self.buf = b''
        self.need = 0              # bytes still to come of the current D frame

    def feed(self, b):
        self.buf += b
        while self.end is None and self.buf:
            if self.need:
                data, self.buf = self.buf[:self.need], self.buf[self.need:]
                self.need -= len(data)
                self.got += len(data)
                self.on_data(data)
                if not self.need:
                    self.frames += 1
                continue
            nl = self.buf.find(b'\n')
            if nl < 0:
                return
            head = self.buf[:nl].decode('ascii', 'replace').split()
            self.buf = self.buf[nl + 1:]
            if not head:
                continue
            if head[0] == 'D':
                self.need = int(head[1])
                continue
            if head[0] == 'E':
                v = head[1] if len(head) > 1 else 'lost'
                self.end = int(v) if v.lstrip('-').isdigit() else v
            self.frames += 1


def info(d):
    jid = os.path.basename(d)
    meta = json.loads(_read(os.path.join(d, 'meta.json'), '{}') or '{}')
    st = state(d)
    ex = exit_of(d)
    claim = os.path.join(d, 'claim')
    started = os.path.getmtime(claim) if os.path.exists(claim) else None
    log = os.path.join(d, 'log')
    size = os.path.getsize(log) if os.path.exists(log) else 0
    tail = ''
    if size:
        with open(log, 'rb') as f:
            f.seek(max(0, size - 400))
            lines = [l for l in f.read().decode('utf-8', 'replace').splitlines() if l.strip()]
            tail = lines[-1][-160:] if lines else ''
    wrote = os.path.getmtime(log) if os.path.exists(log) else started       # (no log yet: it has been quiet since it began)
    row = dict(jid=jid, kind=meta.get('kind'), wt=meta.get('wt'), label=meta.get('label'), state=st,
               rc=ex[0] if ex else None, started=started, ended=ex[1] if ex else None, log_bytes=size, tail=tail,
               sent_from=meta.get('host'), last_write=wrote, expect_min=meta.get('expect_min'),
               stall_min=meta.get('stall_min'))
    if st == 'running':                                     # (read on the box's clock, as the flags are)
        row['quiet'] = round(max(0.0, time.time() - wrote), 1) if wrote else None
    row['flags'] = flags(row)
    return row


def stall_limit(kind, stall_min=None):
    """minutes of silence after which a running job of this kind is flagged: its own (stall_min), else its kind's, else 20."""
    return float(stall_min) if stall_min else float(STALL_MIN.get(kind or '', STALL_MIN['default']))


def flags(row, now=None):
    """the alarms on one job row (info's), for a RUNNING job only: [{'flag': 'silent', 'minutes': quiet, 'limit': N}] when
    its log has not been written for stall_limit minutes, [{'flag': 'overrun', 'minutes': elapsed, 'expect': E}] when it
    has run longer than OVERRUN (2x) the duration it declared. Both may hold. Nothing is stopped."""
    if row.get('state') != 'running' or not row.get('started'):
        return []
    now = now or time.time()
    out = []
    quiet = (now - (row.get('last_write') or row['started'])) / 60
    lim = stall_limit(row.get('kind'), row.get('stall_min'))
    if quiet >= lim:
        out.append({'flag': 'silent', 'minutes': round(quiet, 1), 'limit': lim})
    exp = row.get('expect_min')
    if exp and (now - row['started']) / 60 > OVERRUN * float(exp):
        out.append({'flag': 'overrun', 'minutes': round((now - row['started']) / 60, 1), 'expect': float(exp)})
    return out


def list_jobs(days=1):
    cut = time.time() - days * 86400
    rows = []
    for d in sorted(glob.glob(os.path.join(JOBS, '*'))):
        if os.path.basename(d) == 'bin' or not os.path.isdir(d):
            continue
        r = info(d)
        if r['state'] in ('running', 'pending') or (r['ended'] or r['started'] or 0) >= cut:
            rows.append(r)
    for r in rows:
        print(json.dumps(r))
    return 0


def prune(days=KEEP_DAYS):
    """finished or lost jobs' directories older than days."""
    cut = time.time() - days * 86400
    for d in glob.glob(os.path.join(JOBS, '*')):
        if os.path.basename(d) == 'bin' or not os.path.isdir(d):
            continue
        try:
            if state(d) in ('done', 'lost') and os.path.getmtime(d) < cut and os.path.getmtime(
                    os.path.join(d, 'log') if os.path.exists(os.path.join(d, 'log')) else d) < cut:
                subprocess.run(['rm', '-rf', d], check=False)
        except OSError:
            pass


# ------------------------------------------------------------------------------------------------------------- the load
def cron_lines(dst):
    """the sampler's user crontab lines: once a minute, and at boot (a `boot` event)."""
    return ['* * * * * python3 %s sample >/dev/null 2>&1 %s' % (dst, CRON_MARK),
            '@reboot python3 %s sample --boot >/dev/null 2>&1 %s' % (dst, CRON_MARK)]


def cron_merge(cur, dst):
    """the crontab text `cur` with the sampler's lines (cron_lines) added where missing; another line of ours (another
    path, an older form) is replaced, everything else kept as it was -> the new text, or None when nothing changes."""
    want = cron_lines(dst)
    lines = cur.splitlines()
    ours = [l for l in lines if l.rstrip().endswith(CRON_MARK)]
    if sorted(ours) == sorted(want):
        return None
    keep = [l for l in lines if not l.rstrip().endswith(CRON_MARK)]
    return '\n'.join(keep + want) + '\n'


def install_sampler(d):
    """this file into JOBS/bin (when newer than what's there) and the user crontab lines running its `sample` each
    minute and at boot (cron_lines; the jobs run as the box's owner, so it's the owner's crontab)."""
    if os.environ.get('BOXJOB_NO_CRON') or not os.path.exists('/proc/stat'):   # tests; not a Linux box
        return
    b = os.path.join(JOBS, 'bin')
    os.makedirs(b, exist_ok=True)
    dst = os.path.join(b, 'boxjob.py')
    have = _read(dst, '')
    mine = _read(os.path.abspath(__file__))
    def version(src):
        for line in (src or '').splitlines():
            if line.startswith('VERSION = '):
                return int(line.split('=')[1])
        return -1
    if have != mine and version(mine) >= version(have):
        _write(dst, mine)
    try:
        r = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
    except OSError:
        return
    if r.returncode and r.stdout.strip():                   # an error with output: don't overwrite what we can't read
        return
    new = cron_merge(r.stdout if not r.returncode else '', dst)
    if new is not None:
        subprocess.run(['crontab', '-'], input=new, text=True, check=False)


def _btime():
    """the kernel's boot time (epoch s), from /proc/stat."""
    try:
        with open('/proc/stat') as f:
            for line in f:
                if line.startswith('btime '):
                    return int(line.split()[1])
    except OSError:
        pass
    return None


def _cpu():
    with open('/proc/stat') as f:
        v = [int(x) for x in f.readline().split()[1:]]
    # user nice system idle iowait irq softirq steal
    v += [0] * (8 - len(v))
    return dict(user=v[0] + v[1], system=v[2] + v[5] + v[6], idle=v[3], iowait=v[4], steal=v[7], total=sum(v[:8]))


def _meminfo():
    m = {}
    with open('/proc/meminfo') as f:
        for line in f:
            k, v = line.split(':', 1)
            m[k] = int(v.split()[0]) / 2 ** 20                     # kB -> GB
    return m


def _locks():
    """{(major, minor, inode): pid} for the flocks held (not waited on) now."""
    out = {}
    try:
        with open('/proc/locks') as f:
            for line in f:
                p = line.split()
                if '->' in p or len(p) < 6 or p[1] != 'FLOCK':
                    continue
                mj, mn, ino = p[5].split(':')
                out[(int(mj, 16), int(mn, 16), int(ino))] = int(p[4])
    except (OSError, ValueError):
        pass
    return out


def slots_now(slots_dir=SLOTS_DIR):
    """the build slots: count, held (with who holds them) and the builds waiting for one."""
    try:
        count = int(_read(os.path.join(slots_dir, 'count'), '2').strip())
    except ValueError:
        count = 2
    locks = _locks()
    held = []
    for f in glob.glob(os.path.join(slots_dir, '[0-9]*')):
        try:
            st = os.stat(f)
        except OSError:
            continue
        pid = locks.get((os.major(st.st_dev), os.minor(st.st_dev), st.st_ino))
        if pid:
            who = (_read(f, '') or '').split(None, 2)
            held.append(dict(slot=int(os.path.basename(f)), pid=pid, label=who[1] if len(who) > 1 else '',
                             root=os.path.basename(who[2].strip()) if len(who) > 2 else ''))
    waiting = []
    for f in glob.glob(os.path.join(slots_dir, 'wait', '*.json')):
        try:
            w = json.loads(_read(f, '{}'))
        except ValueError:
            continue
        if w.get('pid') and alive(int(w['pid'])):
            waiting.append(dict(pid=w['pid'], label=w.get('label', ''), root=os.path.basename(w.get('root', '')),
                                waited=round(time.time() - float(w.get('since', time.time())), 1), why=w.get('why')))
    return dict(count=count, held=len(held), holders=sorted(held, key=lambda h: h['slot']), waiting=len(waiting),
                waiters=waiting)


def _classify(argv):
    """a process's class for the CPU accounting: blender, charkit <sub> (build, tune, qa, gate, fit, ...), or other."""
    if not argv:
        return 'other'
    if os.path.basename(argv[0]) in (b'blender', b'blender.bin'):
        return 'blender'
    if b'charkit' in argv:
        i = argv.index(b'charkit')
        if i > 0 and argv[i - 1] == b'-m':
            sub = argv[i + 1].decode(errors='replace') if len(argv) > i + 1 else ''
            return 'charkit ' + (sub if sub in ('build', 'tune', 'qa', 'gate', 'fit', 'run', 'evaldrift') else 'other')
    return 'other'


def _procs(prev):
    """per class (_classify): how many processes, and CPU ticks used since the last sample (by /proc/PID/stat's utime and
    stime; a pid new since then counts from its start) -> ({class: n}, {class: ticks}, this sample's per-pid ticks)."""
    n, ticks, now = {}, {}, {}
    for d in glob.glob('/proc/[0-9]*'):
        try:
            with open(d + '/cmdline', 'rb') as f:
                argv = [a for a in f.read().split(b'\0') if a]
            with open(d + '/stat') as f:
                rest = f.read().rsplit(')', 1)[1].split()
        except (OSError, IndexError):
            continue
        if not argv:
            continue                                   # kernel threads
        c = _classify(argv)
        n[c] = n.get(c, 0) + 1
        pid, used, born = os.path.basename(d), int(rest[11]) + int(rest[12]), rest[19]
        now[pid] = [used, born]
        p = prev.get(pid)
        ticks[c] = ticks.get(c, 0) + used - (p[0] if p and p[1] == born and p[0] <= used else 0)
    return n, ticks, now


def _gpu():
    try:
        r = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used', '--format=csv,noheader,nounits'],
                           capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode or not r.stdout.strip():
        return None
    u, m = r.stdout.strip().splitlines()[0].split(',')
    return dict(util=float(u), mem_gb=round(float(m) / 1024, 2))


def running_jobs():
    out = []
    for d in glob.glob(os.path.join(JOBS, '*')):
        if os.path.basename(d) != 'bin' and os.path.isdir(d) and state(d) == 'running':
            out.append(os.path.basename(d))
    return sorted(out)


def quiet_now(jids, now=None):
    """each running job's log now -> {jid: [bytes, seconds since its last write]} (the sampler's `quiet`: a job's
    longest silence is the largest of its samples', to the minute)."""
    now = time.time() if now is None else now
    out = {}
    for j in jids:
        try:
            st = os.stat(os.path.join(JOBS, j, 'log'))
        except OSError:
            continue
        out[j] = [st.st_size, round(max(0.0, now - st.st_mtime), 1)]
    return out


def silences(days=7, load_dir=None):
    """the longest silence of each job the sampler saw (its samples' largest `quiet`), by kind, for the jobs that ended
    rc 0 -> [{kind, jobs, p50, p90, max (minutes), limit, worst}] (and the jobs that ended otherwise, apart)."""
    cut = time.strftime('%Y%m%d', time.gmtime(time.time() - days * 86400))
    worst = {}
    for f in sorted(glob.glob(os.path.join(load_dir or LOAD, 'load-*.jsonl'))):
        if os.path.basename(f)[5:13] < cut:
            continue
        with open(f) as fh:
            for line in fh:
                if '"quiet"' not in line:
                    continue
                try:
                    q = json.loads(line).get('quiet') or {}
                except ValueError:
                    continue
                for j, (_, s) in q.items():
                    if s > worst.get(j, -1):
                        worst[j] = s
    by = {}
    for j, s in worst.items():
        d = os.path.join(JOBS, j)
        meta = json.loads(_read(os.path.join(d, 'meta.json'), '{}') or '{}')
        ex = exit_of(d)
        key = (meta.get('kind') or '?', 'ok' if ex and ex[0] == 0 else 'running' if not ex else 'failed')
        by.setdefault(key, []).append((s / 60, j))
    out = []
    for (kind, how), v in sorted(by.items()):
        v.sort()
        m = [x[0] for x in v]
        out.append(dict(kind=kind, ended=how, jobs=len(v), p50=round(m[len(m) // 2], 1),
                        p90=round(m[min(len(m) - 1, int(0.9 * (len(m) - 1) + 0.5))], 1), max=round(m[-1], 1),
                        limit=stall_limit(kind), worst=v[-1][1]))
    return out


def sample(load_dir=LOAD, slots_dir=SLOTS_DIR, now=None, boot=False):
    """one sample appended to load_dir/load-<UTC day>.jsonl -> the sample. boot: the @reboot line's (event 'boot')."""
    os.makedirs(load_dir, exist_ok=True)
    now = time.time() if now is None else now
    cpu = _cpu()
    prev_p = os.path.join(load_dir, '.cpu.json')
    try:
        prev = json.loads(_read(prev_p, '{}') or '{}')
    except ValueError:
        prev = {}
    nproc, ticks, pt = _procs(prev.get('pids', {}))
    _write(prev_p, json.dumps(dict(cpu, t=now, pids=pt)))
    busy = None
    if prev.get('total') and cpu['total'] > prev['total']:
        dt = cpu['total'] - prev['total']
        busy = dict(busy=round(1 - (cpu['idle'] - prev['idle'] + cpu['iowait'] - prev['iowait']) / dt, 4),
                    user=round((cpu['user'] - prev['user']) / dt, 4), system=round((cpu['system'] - prev['system']) / dt, 4),
                    iowait=round((cpu['iowait'] - prev['iowait']) / dt, 4), steal=round((cpu['steal'] - prev['steal']) / dt, 4),
                    over=round(now - prev.get('t', now), 1),
                    by=({c: round(t / dt, 4) for c, t in sorted(ticks.items()) if t > 0} if prev.get('pids') else None))
    m = _meminfo()
    with open('/proc/loadavg') as f:
        la = [float(x) for x in f.read().split()[:3]]
    blender = nproc.get('blender', 0)
    jobs = running_jobs()
    charkit = sum(v for k, v in nproc.items() if k.startswith('charkit'))
    try:
        sv = os.statvfs(WORK)
        disk = round(sv.f_bavail * sv.f_frsize / 1e9, 1)
    except OSError:
        disk = None
    s = dict(t=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now)), ts=round(now, 1), host=os.uname()[1].split('.')[0],
             ncpu=os.cpu_count(), load=la, cpu=busy,
             mem=dict(total=round(m.get('MemTotal', 0), 2), avail=round(m.get('MemAvailable', 0), 2),
                      used=round(m.get('MemTotal', 0) - m.get('MemAvailable', 0), 2),
                      swap_used=round(m.get('SwapTotal', 0) - m.get('SwapFree', 0), 2)),
             slots=slots_now(slots_dir), jobs=jobs, quiet=quiet_now(jobs, now), blender=blender, charkit=charkit,
             procs={k: v for k, v in sorted(nproc.items()) if k != 'other'}, disk_free_gb=disk, boot=_btime())
    if boot:
        s['event'] = 'boot'
    g = _gpu()
    if g:
        s['gpu'] = g
    with open(os.path.join(load_dir, 'load-%s.jsonl' % time.strftime('%Y%m%d', time.gmtime(now))), 'a') as f:
        f.write(json.dumps(s, separators=(',', ':')) + '\n')
    # the slot waits charkit.procs recorded, beside the samples (published together)
    w = os.path.join(slots_dir, 'waits.jsonl')
    if os.path.exists(w):
        dst = os.path.join(load_dir, 'waits.jsonl')
        if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(w) or os.path.getmtime(dst) < os.path.getmtime(w):
            _write(dst, _read(w, ''))
    cut = time.strftime('%Y%m%d', time.gmtime(now - LOAD_DAYS * 86400))
    for f in glob.glob(os.path.join(load_dir, 'load-*.jsonl')):
        if os.path.basename(f)[5:13] < cut:
            os.remove(f)
    return s


def publish_load(d, meta):
    """the load log into the bucket under load-<host> (the job's own bucketsync.py), when a job ends."""
    bs = os.path.join(d, 'bucketsync.py')
    if not meta.get('bucket') or not os.path.exists(bs) or not os.path.isdir(LOAD):
        return
    env = dict(os.environ, BS_ROLE='box', BUCKET=meta['bucket'])
    with open(os.path.join(d, 'post.log'), 'ab') as log:
        subprocess.run([sys.executable, bs, 'publish', LOAD, '--name', 'load-' + os.uname()[1].split('.')[0]], env=env,
                       stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, timeout=600, check=False)


# ------------------------------------------------------------------------------------------------------------------ cli
def main(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    cmd, a = argv[0], argv[1:]
    if cmd == 'start':
        return start(a[0])
    if cmd == 'supervise':
        return supervise(a[0])
    if cmd == 'follow':
        return follow(a[0], int(a[1]) if len(a) > 1 else 0)
    if cmd == 'list':
        return list_jobs(float(a[a.index('--days') + 1]) if '--days' in a else 1)
    if cmd == 'silences':                   # (remote jobs --silences: each kind's longest silences, from the sampler)
        for r in silences(float(a[a.index('--days') + 1]) if '--days' in a else 7):
            print(json.dumps(r))
        return 0
    if cmd == 'kill':
        return kill(a[0])
    if cmd == 'sample':
        sample(boot='--boot' in a)
        return 0
    if cmd == 'version':
        print(VERSION)
        return 0
    if cmd == 'slots':                      # (charkit.remote.box_slots: the slots now, as one JSON line)
        print(json.dumps(slots_now()))
        return 0
    print(__doc__)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
