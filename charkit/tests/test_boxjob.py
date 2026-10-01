"""charkit.boxjob (detached box jobs, the load sampler) and the laptop's follow in charkit.remote: a job runs once however
often it's started, its log comes back whole and in order across dropped connections, its exit code propagates, a
job whose supervisor vanished reads as lost, kill stops only the job; the sampler sees held slots and waiting builds;
charkit.boxload summarises samples (venv or the box's python: run this file)."""
import io, json, os, shutil, subprocess, sys, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ['BOXJOB_NO_CRON'] = '1'                  # never a crontab from a test
from charkit import boxjob, boxload


def _setup():
    boxjob.JOBS = tempfile.mkdtemp()
    boxjob.LOAD = tempfile.mkdtemp()
    boxjob.WORK = tempfile.mkdtemp()
    os.environ.update(BOXJOB_ROOT=boxjob.JOBS, BOXJOB_LOAD=boxjob.LOAD, BOXJOB_WORK=boxjob.WORK)


def _job(script, jid='t1'):
    d = os.path.join(boxjob.JOBS, jid)
    os.makedirs(d)
    open(os.path.join(d, 'run.sh'), 'w').write(script)
    json.dump(dict(kind='test', wt='wt', label='x'), open(os.path.join(d, 'meta.json'), 'w'))
    shutil.copy(boxjob.__file__, os.path.join(d, 'boxjob.py'))
    return d


def _start(jid):
    return subprocess.run([sys.executable, os.path.join(boxjob.JOBS, jid, 'boxjob.py'), 'start', jid],
                          capture_output=True, text=True, env=dict(os.environ))


def _wait_done(d, t=20):
    t0 = time.time()
    while boxjob.state(d) == 'running' and time.time() - t0 < t:
        time.sleep(0.1)
    return boxjob.state(d)


def _follow(jid, offset=0):
    buf = io.BytesIO()
    boxjob.follow(jid, offset, out=buf, heartbeat=0.3, poll=0.05)
    got = []
    fr = boxjob.Frames(got.append)
    fr.feed(buf.getvalue())
    return b''.join(got), fr.end


def test_runs_once_log_and_exit_code():
    _setup()
    d = _job('echo hello; for i in $(seq 1 200); do echo "line $i"; done; echo err >&2; sleep 0.5; exit 3\n')
    r1 = _start('t1')
    assert 'BOXJOB-STARTED t1' in r1.stdout, r1
    r2 = _start('t1')                                  # a retried start: the claim holds, nothing runs twice
    assert 'BOXJOB-RUNNING t1' in r2.stdout, r2
    assert _wait_done(d) == 'done'
    log = open(os.path.join(d, 'log'), 'rb').read()
    assert log.count(b'hello') == 1 and b'err' in log and b'line 200' in log
    data, end = _follow('t1')
    assert data == log and end == 3
    # reattaching at any byte gives exactly the rest
    for k in (0, 1, 17, len(log) // 2, len(log)):
        rest, end = _follow('t1', k)
        assert rest == log[k:] and end == 3
    rows = [json.loads(l) for l in subprocess.run([sys.executable, os.path.join(d, 'boxjob.py'), 'list'], capture_output=True,
                                                  text=True, env=dict(os.environ)).stdout.splitlines()]
    assert [(x['jid'], x['state'], x['rc']) for x in rows] == [('t1', 'done', 3)]


def test_frames_across_split_reads():
    buf = io.BytesIO()
    payload = bytes(range(256)) * 300 + b'D 5\nnot a frame\n'
    buf.write(b'H 1\n')
    for i in range(0, len(payload), 1000):
        chunk = payload[i:i + 1000]
        buf.write(b'D %d\n' % len(chunk) + chunk)
    buf.write(b'E 0\n')
    raw = buf.getvalue()
    got = []
    fr = boxjob.Frames(got.append)
    for i in range(0, len(raw), 7):                   # arriving 7 bytes at a time
        fr.feed(raw[i:i + 7])
    assert b''.join(got) == payload and fr.end == 0 and fr.got == len(payload)


def test_lost_and_kill():
    _setup()
    d = _job('exit 0\n', 'lost1')
    open(os.path.join(d, 'claim'), 'w').write('1 0\n')
    p = subprocess.Popen([sys.executable, '-c', 'pass'])
    p.wait()
    open(os.path.join(d, 'pid'), 'w').write('%d %d\n' % (p.pid, p.pid))      # a supervisor that is gone, no exit code
    assert boxjob.state(d) == 'lost'
    assert _follow('lost1')[1] == 'lost'
    d2 = _job('sleep 30 & wait\n', 'k1')
    assert 'STARTED' in _start('k1').stdout
    t0 = time.time()
    while boxjob.pids(d2)[1] is None and time.time() - t0 < 10:
        time.sleep(0.05)
    assert boxjob.state(d2) == 'running'
    r = subprocess.run([sys.executable, os.path.join(d2, 'boxjob.py'), 'kill', 'k1'], capture_output=True, text=True,
                       env=dict(os.environ))
    assert r.returncode == 0, r
    assert _wait_done(d2) == 'done'
    assert boxjob.exit_of(d2)[0] == 143 and time.time() - t0 < 20


def test_remote_attach_reattaches_after_drops():
    """charkit.remote.attach over a 'connection' that drops after every 700 bytes: the whole log arrives once, in
    order, with the job's exit code."""
    _setup()
    from charkit import remote
    d = _job('for i in $(seq 1 400); do echo "line $i"; done; exit 5\n', 'r1')
    _start('r1')
    assert _wait_done(d) == 'done'
    calls = []

    def argv(cfg, vm, jid, at):
        calls.append(at)
        code = ('import subprocess, sys; p = subprocess.Popen([sys.executable, %r, "follow", %r, "%d"], '
                'stdout=subprocess.PIPE); b = p.stdout.read(700); sys.stdout.buffer.write(b); sys.stdout.flush(); '
                'p.kill(); sys.exit(255)' % (os.path.join(d, 'boxjob.py'), jid, at))
        return [sys.executable, '-c', code]
    old = remote._follow_argv, remote._cfg, remote.REATTACH, remote._record
    remote._follow_argv, remote._cfg, remote.REATTACH, remote._record = argv, (lambda: (None, None)), 0, (lambda r: None)
    try:
        out = io.BytesIO()
        err = sys.stderr
        sys.stderr = io.StringIO()
        try:
            rc = remote.attach('r1', out=out)
        finally:
            sys.stderr = err
    finally:
        remote._follow_argv, remote._cfg, remote.REATTACH, remote._record = old
    log = open(os.path.join(d, 'log'), 'rb').read()
    assert rc == 5 and out.getvalue() == log, (rc, len(out.getvalue()), len(log))
    assert len(calls) > 3 and calls == sorted(calls) and calls[0] == 0


def test_sampler_sees_slots_and_waits():
    if not os.path.exists('/proc/stat'):
        print('skip (no /proc: not Linux)')
        return
    _setup()
    import fcntl
    sd = tempfile.mkdtemp()
    open(os.path.join(sd, 'count'), 'w').write('3\n')
    f = open(os.path.join(sd, '0'), 'a+')
    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    f.write('%d build clawd /srv/work/wt\n' % os.getpid()); f.flush()
    open(os.path.join(sd, '1'), 'a+').close()             # a free slot
    os.makedirs(os.path.join(sd, 'wait'))
    json.dump(dict(pid=os.getpid(), label='build x', root='/srv/work/wt2', since=time.time() - 30, why='slots'),
              open(os.path.join(sd, 'wait', '%d.json' % os.getpid()), 'w'))
    json.dump(dict(pid=999999999, since=0), open(os.path.join(sd, 'wait', '999999999.json'), 'w'))   # gone: not counted
    open(os.path.join(sd, 'waits.jsonl'), 'w').write(json.dumps(dict(at=time.time(), waited=12.5, why='slots')) + '\n')
    s1 = boxjob.sample(boxjob.LOAD, sd)
    s2 = boxjob.sample(boxjob.LOAD, sd, now=time.time() + 60)
    assert s1['slots']['count'] == 3 and s1['slots']['held'] == 1 and s1['slots']['holders'][0]['label'] == 'build'
    assert s1['slots']['waiting'] == 1 and s1['slots']['waiters'][0]['waited'] >= 29
    assert s1['jobs'] == [] and s1['quiet'] == {}                   # (no job running in this JOBS)
    assert s2['cpu'] is not None and 0 <= s2['cpu']['busy'] <= 1 and len(s2['load']) == 3
    assert os.path.exists(os.path.join(boxjob.LOAD, 'waits.jsonl'))
    samples, waits = boxload.read(boxjob.LOAD, 0)
    assert len(samples) == 2 and len(waits) == 1
    f.close()


def test_summary():
    t0 = 1.7e9
    S = []
    for i in range(120):
        full = 40 <= i < 100
        S.append(dict(t='2026-09-30T%02d:%02d:00Z' % (10 + i // 60, i % 60), ts=t0 + 60 * i, ncpu=32, load=[20.0 + (i == 70) * 36, 18, 17],
                      cpu=dict(busy=0.95 if full else 0.3, user=0.5, system=0.1, iowait=0.01, steal=0.0),
                      mem=dict(total=125, avail=60, used=65, swap_used=0),
                      slots=dict(count=8, held=8 if full else 3, waiting=2 if 60 <= i < 70 else 0), jobs=['a'], blender=8))
    W = [dict(at=t0, waited=0.0, why=None)] * 6 + [dict(at=t0, waited=w, why='slots') for w in (30, 60, 600)]
    s = boxload.summarise(S, W)
    assert s['minutes'] == 120 and s['slots']['share_full'] == 0.5 and s['load']['peak'] == 56.0
    assert s['queue']['max'] == 2 and abs(s['queue']['share_waiting'] - 10 / 120) < 1e-9
    assert s['waits']['taken'] == 9 and s['waits']['waited'] == 3 and s['waits']['max'] == 600
    assert 'CPU' in s['reading'] or 'slot' in s['reading']
    txt = boxload.text('build', s, boxload.hourly(S))
    assert 'peak 56.0' in txt and '3 waited' in txt


def test_cron_lines_at_boot_and_each_minute():
    """j: the sampler's crontab has the per-minute line and the @reboot one; an older form of ours is replaced, the
    owner's other lines kept, and a crontab that has both is left alone."""
    dst = '/srv/work/.jobs/bin/boxjob.py'
    old = '* * * * * python3 %s sample >/dev/null 2>&1 %s' % (dst, boxjob.CRON_MARK)
    other = '0 3 * * * echo keep  # the owner\'s own'
    new = boxjob.cron_merge('%s\n%s\n' % (other, old), dst)
    lines = new.splitlines()
    assert lines[0] == other and set(lines[1:]) == set(boxjob.cron_lines(dst)), lines
    assert any(l.startswith('@reboot ') and ' sample --boot ' in l for l in lines)
    assert boxjob.cron_merge(new, dst) is None                       # installed: nothing to do
    assert set(boxjob.cron_merge('', dst).splitlines()) == set(boxjob.cron_lines(dst))
    moved = boxjob.cron_merge(new.replace(dst, '/elsewhere/boxjob.py'), dst)   # another path of ours: replaced
    assert moved.count(boxjob.CRON_MARK) == 2 and '/elsewhere/' not in moved and other in moved


def test_gaps_read_by_boot_time():
    """a gap between samples of two boots is the box down; of one boot, the sampler missing; before `boot`, unknown."""
    def smp(ts, boot):
        d = dict(t='T%d' % ts, ts=ts)
        if boot:
            d['boot'] = boot
        return d
    S = [smp(0, 1), smp(60, 1), smp(4000, 3900), smp(4060, 3900), smp(5000, 3900), smp(5060, None), smp(9000, None)]
    g = boxload.gaps(S)
    assert [x['kind'] for x in g] == ['down', 'missed', '?'], g
    assert g[0]['minutes'] == 66 and g[0]['booted'].endswith('01:05:00Z')
    assert boxload.gaps(S[:2]) == []


def _running(jid, kind, silent_min, ran_min, **meta):
    """a job dir that reads as running (its supervisor: this process) whose log was last written silent_min ago and
    which started ran_min ago."""
    d = os.path.join(boxjob.JOBS, jid)
    os.makedirs(d)
    json.dump(dict(kind=kind, wt='wt', label='x', **meta), open(os.path.join(d, 'meta.json'), 'w'))
    now = time.time()
    for f, ago in (('claim', ran_min), ('log', silent_min)):
        open(os.path.join(d, f), 'w').write('x\n')
        os.utime(os.path.join(d, f), (now - 60 * ago, now - 60 * ago))
    open(os.path.join(d, 'pid'), 'w').write('%d %d\n' % (os.getpid(), os.getpid()))
    return d


def test_stall_alarm_flags_silent_and_overrun_jobs():
    """task 7: a running job silent past its kind's limit is flagged SILENT (a build 20 min, a gate 45: a gate prints
    only at its end), one past 2x the minutes it declared OVERRUN, a job's own limit wins; finished jobs and jobs within
    their limits carry no flag, and nothing is stopped."""
    _setup()
    from charkit import remote
    cases = {'b_quiet25': ('build', 25, 30, {}, ['silent']), 'b_quiet5': ('build', 5, 30, {}, []),
             'g_quiet25': ('gate', 25, 25, {}, []), 'g_quiet50': ('gate', 50, 50, {}, ['silent']),
             'p_quiet25': ('pregate', 25, 25, {}, []), 'p_quiet35': ('pregate', 35, 35, {}, ['silent']),
             's_over': ('sweep', 1, 25, {'expect_min': 10}, ['overrun']),
             's_both': ('sweep', 21, 25, {'expect_min': 10}, ['silent', 'overrun']),
             'own_limit': ('build', 6, 10, {'stall_min': 5}, ['silent'])}
    for jid, (kind, quiet, ran, meta, want) in cases.items():
        _running(jid, kind, quiet, ran, **meta)
    done = _running('finished', 'build', 90, 120)
    open(os.path.join(done, 'exit'), 'w').write('0 %f\n' % time.time())
    rows = {r['jid']: r for r in (boxjob.info(os.path.join(boxjob.JOBS, j)) for j in list(cases) + ['finished'])}
    for jid, (kind, quiet, ran, meta, want) in cases.items():
        got = [f['flag'] for f in rows[jid]['flags']]
        assert got == want, (jid, got, want)
        assert rows[jid]['state'] == 'running'
    assert rows['finished']['flags'] == [] and rows['finished']['state'] == 'done'
    f = rows['b_quiet25']['flags'][0]
    assert f['limit'] == 20 and 24.5 < f['minutes'] < 26 and rows['g_quiet50']['flags'][0]['limit'] == 45
    assert rows['own_limit']['flags'][0]['limit'] == 5
    assert 24.5 * 60 < rows['b_quiet25']['quiet'] < 26 * 60 and 'quiet' not in rows['finished']
    txt = remote.flag_text(f, 'b_quiet25')
    assert txt.startswith('SILENT') and 'not stopped' in txt and 'remote kill b_quiet25' in txt
    assert 'OVERRUN' in remote.flag_text(rows['s_over']['flags'][0])


def test_quiet_sampled_and_silences_by_kind():
    """the sampler's `quiet` (each running job's log bytes and seconds since its last write) and the per-kind longest
    silence read back from the samples (`remote jobs --silences`), split by how the job ended."""
    _setup()
    a = _running('a', 'build', 3, 30)
    b = _running('b', 'build', 0, 30)
    c = _running('c', 'gate', 10, 30)
    q = boxjob.quiet_now(['a', 'b', 'c', 'gone'], now=time.time())
    assert set(q) == {'a', 'b', 'c'} and 170 < q['a'][1] < 190 and q['a'][0] == 2
    t = time.time()
    with open(os.path.join(boxjob.LOAD, 'load-%s.jsonl' % time.strftime('%Y%m%d', time.gmtime(t))), 'w') as f:
        for quiet in ({'a': [1, 60], 'b': [5, 30], 'c': [9, 600]}, {'a': [1, 720], 'b': [9, 10], 'c': [9, 1500]},
                      {'a': [4, 5], 'c': [9, 2100]}):
            f.write(json.dumps(dict(ts=t, jobs=sorted(quiet), quiet=quiet)) + '\n')
        f.write(json.dumps(dict(ts=t, jobs=[])) + '\n')                        # (a sample from before `quiet`)
    for d, rc in ((a, 0), (b, 0), (c, 1)):
        open(os.path.join(d, 'exit'), 'w').write('%d %f\n' % (rc, t))
    S = {(r['kind'], r['ended']): r for r in boxjob.silences(days=1)}
    assert S[('build', 'ok')]['jobs'] == 2 and S[('build', 'ok')]['max'] == 12.0 and S[('build', 'ok')]['worst'] == 'a'
    assert S[('build', 'ok')]['limit'] == 20 and S[('gate', 'failed')]['max'] == 35.0


def test_follow_tells_a_silence_once():
    """the laptop's follow prints the stall alarm when the job has written nothing for its limit (here 0.03 min), once
    per silence, and the job goes on to its end (no kill)."""
    _setup()
    from charkit import remote
    d = _job('echo first; sleep 4; echo second; exit 0\n', 'q1')
    _start('q1')

    def argv(cfg, vm, jid, at):
        return [sys.executable, os.path.join(d, 'boxjob.py'), 'follow', jid, str(at)]
    old = remote._follow_argv, remote._cfg, remote._record
    remote._follow_argv, remote._cfg, remote._record = argv, (lambda: (None, None)), (lambda r: None)
    err, sys.stderr = sys.stderr, io.StringIO()
    try:
        rc = remote.attach('q1', rec={'jid': 'q1', 'kind': 'test', 'stall_min': 0.03}, out=io.BytesIO())
        told = sys.stderr.getvalue()
    finally:
        sys.stderr = err
        remote._follow_argv, remote._cfg, remote._record = old
    assert rc == 0 and told.count('has written nothing for') == 1 and 'not stopped' in told, told


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
