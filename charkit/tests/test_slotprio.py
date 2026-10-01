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


# a holder: takes a slot at its priority, runs ROWS rows of SECS each with a yield point between them, and prints when
# it got the slot, each yield and when it ended (times since T0)
HOLDER = r'''
import sys, time
from charkit import procs
t0, rows, secs, prio = float(sys.argv[1]), int(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4])
s = procs.acquire_slot(sys.argv[5], poll=0.05, prio=prio)
print('GOT %.2f' % (time.time() - t0), flush=True)
for i in range(rows):
    gave = s.yield_point(poll=0.05, log=lambda m: None)
    if gave:
        print('YIELD %.2f %.2f' % (time.time() - t0, gave), flush=True)
    time.sleep(secs)
s.close()
print('END %.2f' % (time.time() - t0), flush=True)
'''


def _holder(env, t0, rows, secs, prio, label):
    return subprocess.Popen([sys.executable, '-c', HOLDER, str(t0), str(rows), str(secs), str(prio), label], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _read(p):
    out, err = p.communicate(timeout=60)
    assert p.returncode == 0, err[-800:]
    got = {}
    for line in out.split('\n'):
        if line:
            k, *v = line.split()
            got.setdefault(k, []).append([float(x) for x in v])
    return got


def _gate_latency(n_slots, n_workers, rows, secs, yield_on, gate_at=0.6):
    """n_workers background holders fill n_slots; a gate asks for a slot at gate_at s -> (its wait in s, the workers'
    outputs)."""
    d = tempfile.mkdtemp(prefix='slotprio-')
    env = _env(d, n_slots, **({} if yield_on else {'CHARKIT_SLOT_YIELD': '0'}))
    t0 = time.time()
    W = [_holder(env, t0, rows, secs, procs.PRIO['low'], 'optimize %d' % i) for i in range(n_workers)]
    time.sleep(gate_at)
    G = _holder(env, t0, 1, 0.5, procs.PRIO['gate'], 'gate build')
    g = _read(G)
    w = [_read(p) for p in W]
    return g['GOT'][0][0] - gate_at, w


def test_a_background_holder_gives_its_slot_to_a_gate_between_rows():
    """2 slots held by 2 optimize-like workers (12 rows of 0.25 s each, 3 s): a gate arriving at 0.6 s waited for a
    worker to finish everything before (2.4 s); now one worker gives way at its next row (<= 0.25 s + a poll), one
    only, and every row still runs."""
    wait_off, w_off = _gate_latency(2, 2, 12, 0.25, yield_on=False)
    wait_on, w_on = _gate_latency(2, 2, 12, 0.25, yield_on=True)
    print('gate wait: %.2f s without yielding, %.2f s with' % (wait_off, wait_on))
    assert wait_off > 2.0, wait_off
    assert wait_on < 0.6, wait_on
    yields = sum(len(x.get('YIELD', [])) for x in w_on)
    assert yields == 1, w_on                                          # one holder per waiting gate
    assert all('END' in x for x in w_on) and not any('YIELD' in x for x in w_off)


def test_a_free_slot_goes_to_a_waiting_gate_first():
    """one slot, held by a background holder; a gate and then a normal build wait for it. When it frees, the gate
    takes it (the normal build was asking too, and before this it was a race), then the build."""
    d = tempfile.mkdtemp(prefix='slotprio-')
    env = _env(d, 1, CHARKIT_SLOT_YIELD='0')
    t0 = time.time()
    L = _holder(env, t0, 1, 1.5, procs.PRIO['low'], 'sweep')
    time.sleep(0.3)
    G = _holder(env, t0, 1, 0.6, procs.PRIO['gate'], 'gate build')
    time.sleep(0.3)
    N = _holder(env, t0, 1, 0.3, procs.PRIO['normal'], 'build')
    l, g, n = _read(L), _read(G), _read(N)
    assert g['GOT'][0][0] < n['GOT'][0][0], (g, n)
    assert g['GOT'][0][0] >= l['END'][0][0] - 0.05 and n['GOT'][0][0] >= g['END'][0][0] - 0.05, (l, g, n)
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
            gate.append(_holder(_env(os.path.join(d, 'slots'), 2), time.time(), 1, 1.0, procs.PRIO['gate'],
                                'gate build'))
        import threading
        th = threading.Thread(target=arrive, daemon=True)
        th.start()
        logs = []
        R = op.Run(decl, os.path.join(d, 'pool'), workers=2, log=logs.append, inproc=False)
        o = R.run(confirm=False)
        th.join(30)
        g = _read(gate[0])
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
    R1, _ = to.run(decl, os.path.join(d, 'inproc'))
    assert sorted((h['name'], h['f']) for h in R1.H) == sorted((h['name'], h['f']) for h in R.H)
    assert any('gave its build slot to a waiting gate' in str(m) for m in logs), logs
    assert any('has a slot again' in str(m) for m in logs), logs
    assert 'GOT' in g and o['workers'] == 2


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
