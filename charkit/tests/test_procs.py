"""charkit.procs's build slots: a third build waits while two slots are held, and a slot frees when its holder ends
(venv: run this file)."""
import os, subprocess, sys, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import procs


def test_slots_queue_and_release():
    procs.SLOTS_DIR = tempfile.mkdtemp()
    os.environ['CHARKIT_BUILD_SLOTS'] = '2'
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
    b.close()
    # run() records the pid and releases its slot afterwards
    d = tempfile.mkdtemp()
    r = procs.run([sys.executable, '-c', 'print(42)'], d, 'test')
    assert r.stdout.strip() == '42' and not os.path.exists(os.path.join(d, procs.PIDFILE))
    assert procs.slot_holders() == []


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
