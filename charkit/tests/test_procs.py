"""charkit.procs's build slots: a third build waits while two slots are held, and a slot frees when its holder ends
(venv: run this file)."""
import os, subprocess, sys, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import procs


def test_slot_count_setting_and_memory_wait():
    procs.SLOTS_DIR = tempfile.mkdtemp()
    os.environ.pop('CHARKIT_BUILD_SLOTS', None)
    assert procs.slots() == 2
    procs.set_slots(['3'])
    assert procs.slots() == 3
    os.environ['CHARKIT_BUILD_SLOTS'] = '1'
    assert procs.slots() == 1
    free = procs.available_gb()
    assert free is None or free > 0
    real = procs.available_gb
    seq = iter([0.5, 0.5, 8.0])
    procs.available_gb = lambda: next(seq)
    try:
        f = procs.acquire_slot('m', poll=0.01, mem=3)                 # waits twice for memory, then takes a slot
        f.close()
    finally:
        procs.available_gb = real


def test_slots_queue_and_release():
    procs.SLOTS_DIR = tempfile.mkdtemp()
    os.environ['CHARKIT_BUILD_SLOTS'] = '2'
    os.environ['CHARKIT_BUILD_MEM_GB'] = '0'
    a = procs.acquire_slot('a'); b = procs.acquire_slot('b')
    assert len(procs.slot_holders()) == 2
    # a third taker in another process waits until one is released
    code = ('import sys, time; sys.path.insert(0, %r); from charkit import procs; procs.SLOTS_DIR = %r; '
            't = time.time(); procs.acquire_slot("c", poll=0.1); print(round(time.time() - t, 1))'
            % (os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), procs.SLOTS_DIR))
    p = subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         env=dict(os.environ))
    time.sleep(1.0)
    assert p.poll() is None                                       # still waiting
    a.close()                                                     # release one
    out, _ = p.communicate(timeout=10)
    assert float(out.strip()) >= 0.9
    # every slot taken is logged with its wait (the box's load sampler reads these); nothing is left waiting
    import json
    W = [json.loads(l) for l in open(os.path.join(procs.SLOTS_DIR, 'waits.jsonl'))]
    assert [w['label'] for w in W] == ['a', 'b', 'c'] and W[0]['why'] is None and W[2]['why'] == 'slots'
    assert W[2]['waited'] >= 0.9 and W[0]['waited'] < 0.5 and not os.listdir(os.path.join(procs.SLOTS_DIR, 'wait'))
    b.close()
    # run() records the pid and releases its slot afterwards
    d = tempfile.mkdtemp()
    r = procs.run([sys.executable, '-c', 'print(42)'], d, 'test')
    assert r.stdout.strip() == '42' and not os.path.exists(os.path.join(d, procs.PIDFILE))
    assert procs.slot_holders() == []


def test_wait_ends_with_the_build():
    d = tempfile.mkdtemp()
    p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(1.5)'])
    import json
    json.dump({'pid': p.pid}, open(os.path.join(d, procs.PIDFILE), 'w'))
    t = time.time()
    try:
        procs.wait([d, '--timeout', '1'])
        assert False, 'should time out'
    except SystemExit as e:
        assert e.code == 2
    p.wait()
    procs.wait([d, '--timeout', '5'])                             # the pid is gone: a stale record ends the wait
    os.remove(os.path.join(d, procs.PIDFILE))
    procs.wait([d])                                               # no record: ended


def test_a_build_holds_one_slot_for_all_it_starts():
    """a whole build in one slot (i): what it starts (its Blender through procs.run, a worker's job, a build inside it)
    takes none of its own, so one slot (the laptop's) can't deadlock; the slot frees when the block ends."""
    procs.SLOTS_DIR = tempfile.mkdtemp()
    os.environ['CHARKIT_BUILD_SLOTS'] = '1'
    os.environ['CHARKIT_BUILD_MEM_GB'] = '0'
    os.environ.pop(procs.HELD, None)
    with procs.build_slot('outer') as lock:
        assert lock is not None and os.environ[procs.HELD] == str(os.getpid())
        assert len(procs.slot_holders()) == 1
        inner = procs.acquire_slot('blender', poll=0.01)            # would wait forever on one slot otherwise
        assert isinstance(inner, procs._Held)
        inner.close()
        r = procs.run([sys.executable, '-c', 'import os; print(os.environ.get("CHARKIT_SLOT_HELD"))'],
                      tempfile.mkdtemp(), 'child')
        assert r.stdout.strip() == str(os.getpid())                  # children see the held slot
        with procs.build_slot('nested') as n2:
            assert n2 is None
        assert os.environ.get(procs.HELD)                           # a nested block leaves the outer's mark
    assert procs.HELD not in os.environ and not procs.slot_holders()
    procs.acquire_slot('after', poll=0.01).close()


def test_thread_caps():
    """the box's builds capped (i): a slot's share of a many-core machine, CHARKIT_THREADS to set or turn it off, and
    a variable already set (a gate's) wins."""
    old = {k: os.environ.pop(k, None) for k in procs.THREAD_VARS + ('CHARKIT_THREADS', 'OMP_WAIT_POLICY')}
    real = os.cpu_count
    try:
        os.cpu_count = lambda: 32
        assert procs.thread_cap() == 4
        E = procs.thread_env()
        assert E['LP_NUM_THREADS'] == '4' and E['NUMBA_NUM_THREADS'] == '4' and E['OMP_WAIT_POLICY'] == 'PASSIVE'
        os.cpu_count = lambda: 12
        assert procs.thread_cap() is None and procs.thread_env() == {}          # the laptop: uncapped
        os.environ['CHARKIT_THREADS'] = '3'
        assert procs.thread_cap() == 3
        os.environ['CHARKIT_THREADS'] = 'off'
        os.cpu_count = lambda: 32
        assert procs.thread_cap() is None
        os.environ.pop('CHARKIT_THREADS')
        os.environ['NUMBA_NUM_THREADS'] = '2'
        assert procs.cap_threads() == 2 and os.environ['OPENBLAS_NUM_THREADS'] == '4'
    finally:
        os.cpu_count = real
        for k, v in old.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
