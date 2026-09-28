"""The build worker on real builds: jobs start clean and leave nothing behind (charkit/worker.py). Blender and minutes per
build: a script that prints its results.

    ~/animation-pipeline/.venv/bin/python charkit/tests/worker_builds.py [--boards views] [--keep]

In a worker of its own (it refuses to run while this checkout already has one), with a throwaway cache:
  A1  clawd in the worker (--cache off: the scene built, not restored)
  B   clawd_locks in the worker (another character: analytic hair, other objects and materials)
  A2  clawd in the worker again
  A0  clawd in a fresh Blender (--no-worker)
  A1, A2 against A0: trace diff `no differences` (stage times left out), qa.json values identical, no leak reported
  C1, C2  clawd in the worker with the cache on: cold, then warm (every step restored), against A0 the same way
It also checks the process records: `ps` lists the worker, a job is recorded in its out folder under the worker's pid, and
`worker stop` leaves no record behind.
"""
import json, os, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PY = sys.executable
sys.path.insert(0, ROOT)
from charkit import worker  # noqa: E402


def cli(*a, env=None):
    return subprocess.run([PY, '-m', 'charkit'] + list(a), cwd=ROOT, capture_output=True, text=True, env=env)


def build(spec, out, *a, env=None):
    t = time.time()
    r = cli('build', spec, '--out', out, *a, env=env)
    if r.returncode:
        raise SystemExit('build %s failed:\n%s' % (out, (r.stdout + r.stderr)[-3000:]))
    w = next((json.loads(l.split(' ', 1)[1]) for l in r.stdout.splitlines() if l.startswith('CHARKIT_WORKER ')), None)
    recs = [json.loads(l) for l in open(os.path.join(out, 'trace.jsonl'))]
    steps = {x['name']: x['cache'] for x in recs if x.get('cache') and x['event'] in ('stage', 'span', 'product', 'part')}
    return dict(seconds=round(time.time() - t, 1), worker=w, steps=steps, stdout=r.stdout)


def diff(a, b):
    return cli('trace', os.path.join(a, 'trace.jsonl'), os.path.join(b, 'trace.jsonl'), '--no-time').stdout.strip()


def qa_same(a, b):
    va, vb = ({k: (c.get('value'), c.get('status')) for k, c in json.load(open(os.path.join(d, 'qa', 'qa.json')))['checks']
               .items()} for d in (a, b))
    return sorted(k for k in set(va) | set(vb) if va.get(k) != vb.get(k))


def main(args):
    boards = args[args.index('--boards') + 1] if '--boards' in args else 'views'
    if worker.info() and worker._alive(worker.info()['pid']):
        raise SystemExit('a worker is already running for this checkout: stop it first (python -m charkit worker stop)')
    tmp = tempfile.mkdtemp(prefix='charkit-worker-')
    env = dict(os.environ, CHARKIT_CACHE_DIR=os.path.join(tmp, 'cache'))
    out = lambda n: os.path.join(tmp, n)
    clawd = os.path.join(ROOT, 'charkit', 'spec', 'clawd.json')
    locks = os.path.join(ROOT, 'charkit', 'spec', 'clawd_locks.json')
    B = ['--boards', boards, '--no-blend']
    fails = []

    def check(ok, what):
        print(('  ok    ' if ok else '  FAIL  ') + what)
        if not ok:
            fails.append(what)
    r = cli('worker', 'start', env=env)
    print(r.stdout.strip())
    pid = worker.info()['pid']
    try:
        check(any('worker' in l and str(pid) in l for l in cli('ps').stdout.splitlines()), 'ps lists the worker (pid %d)' % pid)
        R = {}
        R['A1'] = build(clawd, out('A1'), *B, '--cache', 'off', env=env)
        R['B'] = build(locks, out('B'), *B, '--cache', 'off', env=env)
        R['A2'] = build(clawd, out('A2'), *B, '--cache', 'off', env=env)
        R['A0'] = build(clawd, out('A0'), *B, '--cache', 'off', '--no-worker', env=env)
        for n in ('A1', 'B', 'A2'):
            w = R[n]['worker']
            check(w is not None and w['pid'] == pid, '%s ran in the worker (job %s, %.1fs)' % (n, w and w['job'], R[n]['seconds']))
            check(w is not None and not w.get('leak'), '%s: no state left over from the job before' % n)
        check(R['A0']['worker'] is None, 'A0 ran in a fresh Blender (%.1fs)' % R['A0']['seconds'])
        for n in ('A1', 'A2'):
            d = diff(out('A0'), out(n))
            check(d == 'no differences', '%s against the fresh build: %s' % (n, d[:300]))
            q = qa_same(out('A0'), out(n))
            check(not q, '%s: qa.json values identical to the fresh build%s' % (n, '' if not q else ': ' + ', '.join(q)))
        R['C1'] = build(clawd, out('C1'), *B, env=env)
        R['C2'] = build(clawd, out('C2'), *B, env=env)
        check(all(not c.get('hit') for c in R['C1']['steps'].values()), 'C1 (worker, cache cold): everything ran')
        check(all(c.get('hit') for c in R['C2']['steps'].values()), 'C2 (worker, cache warm): everything restored')
        for n in ('C1', 'C2'):
            d = diff(out('A0'), out(n))
            check(d == 'no differences', '%s against the fresh build: %s' % (n, d[:300]))
            q = qa_same(out('A0'), out(n))
            check(not q, '%s: qa.json values identical to the fresh build%s' % (n, '' if not q else ': ' + ', '.join(q)))
        check(not os.path.exists(os.path.join(out('C2'), '.pid.json')), 'the job\'s process record is gone once it ended')
        print('\ntimes (wall clock, s):', json.dumps({k: v['seconds'] for k, v in R.items()}))
    finally:
        print(cli('worker', 'stop', env=env).stdout.strip())
    check(not os.path.exists(os.path.join(worker.DIR, '.pid.json')) and not worker._alive(pid), 'stop left no worker and no record')
    print('%d checks failed' % len(fails) if fails else 'all checks passed')
    if '--keep' not in args:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print('kept', tmp)
    return not fails


if __name__ == '__main__':
    sys.exit(0 if main(sys.argv[1:]) else 1)
