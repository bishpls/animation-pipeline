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


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
