"""Gates before sweeps (charkit.procs): a free build slot goes to a waiting gate first; a background holder (a sweep's
shard, an optimize worker) gives its slot to a waiting gate between rows, one holder per gate, and takes one again
behind it; background work runs at niceness 10. Every process here uses a slots directory of its own
(CHARKIT_SLOTS_DIR), never the live one (venv: run this file, or pytest)."""
import json, os, subprocess, sys, tempfile, time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
from charkit import procs

SLOT_VARS = (procs.HELD, 'CHARKIT_BUILD_SLOTS', 'CHARKIT_BUILD_MEM_GB', procs.PRIO_ENV, 'CHARKIT_SLOT_YIELD',
             'CHARKIT_SLOTS_DIR', 'CHARKIT_OPT_SLOT')


def _env(slots_dir, n, **kw):
    e = {k: v for k, v in os.environ.items() if k not in SLOT_VARS}
    e.update(CHARKIT_SLOTS_DIR=slots_dir, CHARKIT_BUILD_SLOTS=str(n), CHARKIT_BUILD_MEM_GB='0', PYTHONPATH=REPO, **kw)
    return e


# a holder: takes a slot at its priority and logs each event to a shared file, one append each (O_APPEND: the file's
# order is the events' order across processes): GOT, YIELD (it gave its slot to a waiting gate between rows and has one
# again), END. It runs rows until STOP exists (or `rows` rows when STOP is '-'), with a yield point between them. The
# tests read the ORDER of events, never elapsed seconds (2026-10-01: wall-clock bounds broke on a loaded box)
HOLDER = r'''
import os, sys, time
from charkit import procs
log, label, prio, rows, stop = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
def ev(what):
    fd = os.open(log, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    os.write(fd, ('%s %s\n' % (what, label)).encode())
    os.close(fd)
s = procs.acquire_slot(label, poll=0.05, prio=prio)
ev('GOT')
i = 0
while (os.path.exists(stop) is False) if stop != '-' else i < rows:
    if s.yield_point(poll=0.05, log=lambda m: None):
        ev('YIELD')
    time.sleep(0.05)
    i += 1
s.close()
ev('END')
'''


def _holder(env, log, label, prio, rows=1, stop='-'):
    return subprocess.Popen([sys.executable, '-c', HOLDER, log, label, str(prio), str(rows), stop], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _done(p):
    _, err = p.communicate(timeout=120)
    assert p.returncode == 0, err[-800:]


def _events(log):
    return [tuple(l.split(' ', 1)) for l in open(log).read().splitlines()]


def _until(cond, what, limit=60.0):
    """wait for a condition (a deadline only against a hang: nothing is judged by how long it took)."""
    t = time.time()
    while not cond():
        assert time.time() - t < limit, 'never happened: ' + what
        time.sleep(0.02)


def _waiting(d, label):
    """is a holder labelled so waiting for a slot (its wait record, procs.acquire_slot)?"""
    for f in os.listdir(os.path.join(d, 'wait')) if os.path.isdir(os.path.join(d, 'wait')) else ():
        if f.endswith('.json'):
            try:
                if json.load(open(os.path.join(d, 'wait', f))).get('label') == label:
                    return True
            except (OSError, ValueError):
                pass
    return False


def _gate_among_workers(yield_on):
    """2 slots held by 2 background workers that run until told to stop; a gate asks for a slot once both hold theirs
    -> the event log. With yielding, the gate can only get a slot from a worker between rows (they never end before
    it does); without, only once a worker ends (the test stops them once the gate is seen waiting)."""
    d = tempfile.mkdtemp(prefix='slotprio-')
    log, stop = os.path.join(d, 'events'), os.path.join(d, 'stop')
    env = _env(d, 2, **({} if yield_on else {'CHARKIT_SLOT_YIELD': '0'}))
    W = [_holder(env, log, 'optimize %d' % i, procs.PRIO['low'], stop=stop) for i in range(2)]
    _until(lambda: os.path.exists(log) and sum(e[0] == 'GOT' for e in _events(log)) == 2, 'both workers hold a slot')
    G = _holder(env, log, 'gate build', procs.PRIO['gate'])
    if yield_on:
        _done(G)                                       # (a worker gives its slot between rows)
        open(stop, 'w').close()
    else:
        _until(lambda: _waiting(d, 'gate build'), 'the gate waits for a slot')
        open(stop, 'w').close()                        # (only a worker's end frees a slot)
        _done(G)
    for p in W:
        _done(p)
    return _events(log)


def test_a_background_holder_gives_its_slot_to_a_gate_between_rows():
    """2 slots held by 2 optimize-like workers: without yielding, a gate gets a slot only after a worker ends; with
    it, one worker (one only) gives way at its next row, the gate runs and ends, the worker takes a slot again behind
    it, and both workers run on to their end. Read from the order of events."""
    off = _gate_among_workers(False)
    on = _gate_among_workers(True)
    print('without yielding:', off, '\nwith:', on)
    pos = lambda E, what, label: E.index((what, label))
    assert not any(w == 'YIELD' for w, _ in off)
    first_end = min(pos(off, 'END', 'optimize %d' % i) for i in range(2))
    assert pos(off, 'GOT', 'gate build') > first_end, off
    ys = [l for w, l in on if w == 'YIELD']
    assert len(ys) == 1, on                                            # one holder per waiting gate
    g0, g1, y = pos(on, 'GOT', 'gate build'), pos(on, 'END', 'gate build'), pos(on, 'YIELD', ys[0])
    assert g0 < g1 < y < pos(on, 'END', ys[0]), on                     # it gave, the gate ran, it has a slot again
    assert all(pos(on, 'END', 'optimize %d' % i) > g0 for i in range(2)), on     # (no worker had ended: a yield)


def test_a_free_slot_goes_to_a_waiting_gate_first():
    """one slot, held by a background holder; a gate and then a normal build wait for it. When it frees, the gate
    takes it (the normal build was asking too, and before this it was a race), then the build. Read from the order
    of events."""
    d = tempfile.mkdtemp(prefix='slotprio-')
    log, stop = os.path.join(d, 'events'), os.path.join(d, 'stop')
    env = _env(d, 1, CHARKIT_SLOT_YIELD='0')
    L = _holder(env, log, 'sweep', procs.PRIO['low'], stop=stop)
    _until(lambda: os.path.exists(log) and ('GOT', 'sweep') in _events(log), 'the sweep holds the slot')
    G = _holder(env, log, 'gate build', procs.PRIO['gate'], rows=3)
    _until(lambda: _waiting(d, 'gate build'), 'the gate waits')
    N = _holder(env, log, 'build', procs.PRIO['normal'], rows=3)
    _until(lambda: _waiting(d, 'build'), 'the build waits')
    open(stop, 'w').close()
    for p in (L, G, N):
        _done(p)
    E = _events(log)
    assert E == [('GOT', 'sweep'), ('END', 'sweep'), ('GOT', 'gate build'), ('END', 'gate build'), ('GOT', 'build'),
                 ('END', 'build')], E
    W = [json.loads(x) for x in open(os.path.join(d, 'waits.jsonl'))]
    why = {w['label']: w['why'] for w in W}
    assert why['gate build'] == 'slots' and why['build'] in ('gate', 'slots'), W


def test_priorities_read_from_the_environment_and_the_tree():
    assert procs.priority({procs.PRIO_ENV: 'gate'}) == 2 and procs.priority({procs.PRIO_ENV: 'low'}) == 0
    assert procs.priority({}) in (1, 2)
    # a wait record from before the priority field: a gate's when it waits from a gate's (or pre-gate's) clone
    assert procs._waiter_prio({'root': '/srv/work/gates/tool_x-1234abcd'}) == 2
    assert procs._waiter_prio({'root': '/srv/work/pregates/pregate-tool_x-1'}) == 2
    assert procs._waiter_prio({'root': '/srv/work/animation-pipeline-x'}) == 1
    assert procs._waiter_prio({'root': '/srv/work/gates/x', 'prio': 0}) == 0


def test_background_work_runs_nice_and_low():
    """procs.background(): niceness 10 (never lowered), the low slot priority in the environment its children inherit;
    `charkit sweep` (and so optimize and its workers) calls it."""
    code = ('import os, subprocess, sys; from charkit import procs; n = procs.background(); '
            'c = subprocess.run([sys.executable, "-c", "import os; print(os.nice(0), os.environ.get(%r))"], '
            'capture_output=True, text=True).stdout.split(); print(n, os.environ[%r], *c)' % (procs.PRIO_ENV,
                                                                                             procs.PRIO_ENV))
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, env=_env(tempfile.mkdtemp(), 1))
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ['10', 'low', '10', 'low'], r.stdout
    r = subprocess.run([sys.executable, '-c', 'import os; os.nice(15); from charkit import procs; print(procs.background())'],
                       capture_output=True, text=True, env=_env(tempfile.mkdtemp(), 1))
    assert r.stdout.split() == ['15'], r.stdout + r.stderr                 # (already lower: left)
    code = ('import os; from charkit import procs, sweep; seen = []; procs.background = lambda: seen.append(1)\n'
            'try:\n    sweep.main(["table", "/nonexistent/sweep.json"])\nexcept Exception:\n    pass\nprint(seen)')
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, env=_env(tempfile.mkdtemp(), 1))
    assert r.stdout.strip().endswith('[1]'), r.stdout + r.stderr


def test_the_optimize_pool_moves_a_yielded_row_to_another_worker():
    """the persistent workers (`sweep worker`, each in a build slot): a gate asking for a slot mid-run gets one from a
    worker between rows; that worker's row goes to the other, the worker takes a slot again once the gate's done, and
    the results equal the in-process evaluator's."""
    saved = {k: os.environ.get(k) for k in SLOT_VARS}   # (before test_optimize's import sets CHARKIT_SLOT_HELD)
    from charkit import optimize as op
    from charkit.tests import test_optimize as to
    d = tempfile.mkdtemp(prefix='slotprio-opt-')
    try:
        for k in SLOT_VARS:
            os.environ.pop(k, None)
        os.environ.update(CHARKIT_SLOTS_DIR=os.path.join(d, 'slots'), CHARKIT_BUILD_SLOTS='2',
                          CHARKIT_BUILD_MEM_GB='0', CHARKIT_SLOT_PRIO='low', CHARKIT_OPT_SLOT='1')
        decl = to.syn(budget=dict(generations=4), stop=dict(stall=0))
        decl['args'] = dict(sleep=0.3)
        gate = []

        def arrive():                               # the gate comes once both workers hold their slots
            sd, procs.SLOTS_DIR = procs.SLOTS_DIR, os.path.join(d, 'slots')
            try:
                t = time.time()
                while len(procs.slot_holders()) < 2 and time.time() - t < 60:
                    time.sleep(0.2)
            finally:
                procs.SLOTS_DIR = sd
            time.sleep(0.5)
            gate.append(_holder(_env(os.path.join(d, 'slots'), 2), os.path.join(d, 'events'), 'gate build',
                                procs.PRIO['gate'], rows=20))
        import threading
        th = threading.Thread(target=arrive, daemon=True)
        th.start()
        logs = []
        R = op.Run(decl, os.path.join(d, 'pool'), workers=2, log=logs.append, inproc=False)
        o = R.run(confirm=False)
        th.join(30)
        _done(gate[0])
        g = _events(os.path.join(d, 'events'))
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
    R1, _ = to.run(decl, os.path.join(d, 'inproc'))
    assert sorted((h['name'], h['f']) for h in R1.H) == sorted((h['name'], h['f']) for h in R.H)
    assert any('gave its build slot to a waiting gate' in str(m) for m in logs), logs
    assert any('has a slot again' in str(m) for m in logs), logs
    assert ('GOT', 'gate build') in g and o['workers'] == 2


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
