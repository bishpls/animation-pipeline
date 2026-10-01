"""--box auto (charkit.remote.choose, pick_box, route): fake box readings in, the chosen box out. The pick is by free
CPU (cores less the 1-minute load, times the box's per-core speed) among the boxes with a free slot beyond the reserve,
not by free slots alone: the build box at load 129 on 32 vCPUs still had slots to spare (2026-10-01). Boards prefer a
render box; a stopped CPU box is started when every running one is busy (venv: run this file)."""
import os, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import remote, boxjob  # noqa: E402


def box(name, ncpu=32, load=0.0, count=16, held=0, waiting=0, speed=1.0, gpu=False):
    """a running box's reading, as box_slots makes it."""
    return dict(name=name, status='RUNNING', gpu=gpu, speed=speed, count=count, held=held, waiting=waiting,
                free=max(0, count - held - waiting), ncpu=ncpu, load=load, mem_avail_gb=100.0,
                cpu_free=round(max(0.0, ncpu - load) * speed, 1))


def off(name, gpu=False, speed=1.0, status='TERMINATED'):
    return dict(name=name, status=status, gpu=gpu, speed=speed)


def test_free_cpu_not_free_slots():
    """the build box oversubscribed with slots to spare loses to a box with free cores (the old picker took it)."""
    R = [box('build', load=60, held=4), box('render2', load=6, count=10, held=1, gpu=True),
         box('build2', ncpu=44, load=30, count=22, held=12)]
    name, why = remote.choose(R)
    assert name == 'render2', (name, why)                  # 26 - 4 kept for boards = 22 > build2's 14 > build's 0
    R[2]['load'], R[2]['cpu_free'] = 4.0, 40.0
    assert remote.choose(R)[0] == 'build2'


def test_speed_weights_the_cores():
    """per-core speed (CPU_SPEED) scales the free cores: 20 fast cores beat 24 slow ones."""
    R = [box('build', load=8), box('build2', ncpu=44, load=24, count=22, speed=1.4)]
    assert R[0]['cpu_free'] == 24.0 and R[1]['cpu_free'] == 28.0
    assert remote.choose(R)[0] == 'build2'
    R[1] = box('build2', ncpu=44, load=24, count=22, speed=1.1)    # 22 < 24
    assert remote.choose(R)[0] == 'build'


def test_reserve_and_full_slots():
    """a box needs a free slot beyond the reserve; with none anywhere, the most free slots (the shortest wait)."""
    R = [box('build', load=0, count=16, held=15), box('build2', ncpu=44, load=40, count=22, held=10)]
    assert remote.choose(R, reserve=1)[0] == 'build2'             # build: 1 free = the reserve, no room
    assert remote.choose(R, reserve=0)[0] == 'build'              # 32 free cores
    R = [box('build', count=16, held=16), box('build2', ncpu=44, count=22, held=20, waiting=1)]
    name, why = remote.choose(R, wake=False)
    assert name == 'build2' and 'most free slots' in why, why     # 1 free against 0


def test_ties_go_to_a_cpu_box_then_the_order():
    R = [box('build', load=4), box('render2', load=0, gpu=True)]           # 28 against 32 - 4 kept = 28
    assert remote.choose(R)[0] == 'build'
    R = [box('render', ncpu=8, gpu=True), box('build', load=4), box('build2', load=4)]
    assert remote.choose(R)[0] == 'build'


def test_boards_prefer_a_render_box_with_room():
    R = [box('build', load=0), box('render2', load=20, count=10, gpu=True)]
    assert remote.choose(R, gpu=True)[0] == 'render2'             # 12 free cores, room: the GPU draws the boards
    R[1] = box('render2', load=30, count=10, gpu=True)            # 2 free: busy, so a CPU box (the toon renderer)
    name, why = remote.choose(R, gpu=True)
    assert name == 'build' and 'toon' in why, why
    R[1] = box('render2', load=0, count=10, held=10, gpu=True)    # no slot
    assert remote.choose(R, gpu=True)[0] == 'build'
    assert remote.choose([box('build')], gpu=True)[0] == 'build'  # no render box at all


def test_need_gpu_takes_only_a_render_box():
    R = [box('build', load=0), box('render2', load=31, count=10, gpu=True), off('render', gpu=True)]
    name, why = remote.choose(R, gpu=True, need=True)
    assert name == 'render' and 'starting' in why, why            # busy: the stopped render box is started
    assert remote.choose(R, gpu=True, need=True, wake=False)[0] == 'render2'
    assert remote.choose([box('build')], need=True, wake=False)[0] is None


def test_wake_a_stopped_cpu_box_when_every_running_one_is_busy():
    R = [box('build', load=40), box('render2', load=30, count=10, gpu=True), off('build2', speed=1.4)]
    name, why = remote.choose(R)
    assert name == 'build2' and 'every running box is busy' in why, why
    assert remote.choose(R, wake=False)[0] == 'build'              # the freest of the busy ones (0 against -2)
    R[0]['load'], R[0]['cpu_free'] = 20.0, 12.0                    # room on the build box: nothing started
    assert remote.choose(R)[0] == 'build'
    # a render box isn't started for CPU work; an unreadable box (no permission) is never started
    assert remote.choose([box('build', load=40), off('render', gpu=True), off('build2', status='unknown')])[0] == 'build'
    # nothing running: the fastest stopped CPU box
    assert remote.choose([off('build'), off('build2', speed=1.4), off('render2', gpu=True)])[0] == 'build2'
    assert remote.choose([off('build'), off('render2', gpu=True)], wake=False)[0] is None


def test_unreadable_and_unknown_load():
    R = [dict(name='build', status='unreadable', gpu=False, speed=1.0, why='ssh'), box('build2', ncpu=44, load=10)]
    assert remote.choose(R)[0] == 'build2'
    R = [box('build', load=0), dict(box('build2', ncpu=44), load=None, cpu_free=None)]   # no load read: 0 free cores
    assert remote.choose(R)[0] == 'build'
    assert 'load ?' in remote.describe(R[1])


def test_wants_gpu():
    assert remote.wants_gpu('build', ['s.json'])                                  # the default draws four sets
    assert remote.wants_gpu('build', ['s.json', '--boards', 'views'])
    assert not remote.wants_gpu('build', ['s.json', '--boards', '', '--no-blend'])   # a QA build (gates, confirm)
    assert not remote.wants_gpu('build', ['s.json', '--boards', 'views', '--boards-renderer', 'toon'])
    assert remote.wants_gpu('tune', ['s.json'])
    assert not remote.wants_gpu('run', ['build', 's.json', '--boards', 'views'])
    assert not remote.wants_gpu('gate', ['b', '--into', 'pipeline-3d'])


def _gcp(names):
    """a fake infra/gcp with these boxes' env files; remote.ROOT pointed at it."""
    d = tempfile.mkdtemp()
    g = os.path.join(d, 'infra', 'gcp')
    os.makedirs(g)
    for i, n in enumerate(names):
        open(os.path.join(g, n + '.env'), 'w').write('VM=vm-%d\nBUCKET=gs://x\n%s' % (
            i, 'MACHINE_GPU=nvidia-l4\n' if n.startswith('render') else ''))
    return d


def test_pick_box_reads_every_box_and_logs_each():
    readings = {'build': box('build', load=50), 'build2': box('build2', ncpu=44, load=3, count=22),
                'render2': off('render2', gpu=True)}
    old = remote.ROOT, remote.BOX.copy(), remote.box_slots
    try:
        remote.ROOT = _gcp(['build', 'build2', 'render2'])
        remote.box_slots = lambda env: readings[os.path.basename(env)[:-4]]
        lines = []
        name, got = remote.pick_box(log=lines.append)
        assert name == 'build2' and [g['name'] for g in got] == ['build', 'build2', 'render2']
        assert len(lines) == 4 and lines[-1].startswith('--box auto: build2 (')
        assert 'box build    32 vCPU, load 50.0: 0.0 cores free; 16 of 16 slots free' in lines[0], lines[0]
        assert 'TERMINATED' in lines[2]
        # nothing running and nothing to start: the build box (its up() starts it)
        readings.update(build=off('build', status='unknown'), build2=off('build2', status='unknown'))
        assert remote.pick_box(log=lines.append)[0] == 'build'
        # a box whose reading raises is skipped
        def boom(env):
            if 'build2' in env:
                raise RuntimeError('ssh died')
            return box(os.path.basename(env)[:-4], load=10, gpu='render' in env)
        remote.box_slots = boom
        name, got = remote.pick_box(log=lines.append)
        assert name == 'build' and got[1]['status'] == 'unreadable'
    finally:
        remote.ROOT, remote.box_slots = old[0], old[2]
        remote.BOX.clear(); remote.BOX.update(old[1])


def test_main_routes_by_default_and_a_name_wins():
    """remote build|tune|run|gate with no --box: auto (route); --box NAME: that box, unread; CHARKIT_BOX: the default;
    up/status/stop: the build box, unrouted."""
    calls = []
    old = (remote.ROOT, remote.BOX.copy(), remote.pick_box, remote.charkit, remote.build, remote._sh,
           os.environ.get('CHARKIT_BOX'))
    try:
        remote.ROOT = _gcp(['build', 'build2', 'render2'])
        remote.BOX['env'] = os.path.join(remote.ROOT, 'infra', 'gcp', 'build.env')

        def pick(reserve=1, log=print, gpu=False, need=False, wake=None):
            calls.append(('pick', gpu, need))
            return 'build2', [box('build2')]
        remote.pick_box = pick
        remote.charkit = lambda cmd, publish=None, collect=None: calls.append(('run', remote.BOX['env'])) or 0
        remote.build = lambda args, kind='build': calls.append((kind, remote.BOX['env'], args)) or 0
        remote._sh = lambda *a, **k: calls.append(('sh',) + a) or 0
        env = lambda n: os.path.join(remote.ROOT, 'infra', 'gcp', n + '.env')
        os.environ.pop('CHARKIT_BOX', None)

        def fresh():
            remote.BOX.pop('chosen', None)
            remote.BOX['env'] = env('build')
            del calls[:]
        fresh()
        remote.main(['run', 'slots'])
        assert calls == [('pick', False, False), ('run', env('build2'))], calls
        fresh()
        remote.main(['build', 's.json', '--boards', '', '--no-blend'])
        assert calls[0] == ('pick', False, False) and calls[1][:2] == ('build', env('build2'))
        fresh()
        remote.main(['build', 's.json', '--boards', 'views'])                 # boards: a render box preferred
        assert calls[0] == ('pick', True, False)
        fresh()
        remote.main(['--gpu', 'run', 'preview'])                               # --gpu: only a render box
        assert calls[0] == ('pick', True, True) and calls[1] == ('run', env('build2'))
        fresh()
        remote.main(['--box', 'auto', 'tune', 's.json'])
        assert calls[0] == ('pick', True, False) and calls[1][0] == 'tune'
        fresh()
        remote.main(['--box', 'render2', 'run', 'slots'])                      # a name wins: nothing read
        assert calls == [('run', env('render2'))], calls
        fresh()
        os.environ['CHARKIT_BOX'] = 'build'                                     # the default, named
        remote.main(['run', 'slots'])
        assert calls == [('run', env('build'))], calls
        os.environ.pop('CHARKIT_BOX')
        fresh()
        remote.main(['status'])                                                 # not routed: the build box
        assert calls == [('sh', 'status')], calls
        fresh()
        try:
            remote.main(['--box', 'auto', 'status'])
            assert False, 'auto for status'
        except SystemExit as e:
            assert 'auto' in str(e)
        fresh()
        try:
            remote.main(['--box', 'nosuch', 'run', 'x'])
            assert False, 'an unknown box'
        except SystemExit as e:
            assert 'nosuch' in str(e)
    finally:
        (remote.ROOT, _, remote.pick_box, remote.charkit, remote.build, remote._sh, cb) = old
        remote.BOX.clear(); remote.BOX.update(old[1])
        if cb is None:
            os.environ.pop('CHARKIT_BOX', None)
        else:
            os.environ['CHARKIT_BOX'] = cb


def test_box_side_reading():
    """boxjob's `slots` (what box_slots reads over ssh): the slots, with the cores, the load and memory."""
    d = tempfile.mkdtemp()
    open(os.path.join(d, 'count'), 'w').write('22\n')
    r = boxjob.reading(d)
    assert r['count'] == 22 and r['held'] == 0 and r['waiting'] == 0
    assert r['ncpu'] == os.cpu_count() and len(r['load']) == 3 and all(x >= 0 for x in r['load'])


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
