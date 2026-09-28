"""The build worker on real builds: jobs start clean and leave nothing behind (charkit/worker.py). Blender and minutes per
build: a script that prints its results. One Blender at a time: the fresh build runs before the worker starts.

    ~/animation-pipeline/.venv/bin/python charkit/tests/worker_builds.py [--boards views] [--keep]

In a throwaway copy of the checkout (its own worker, cache and output; this checkout's worker, if any, is left alone):
  A0  clawd in a fresh Blender (--no-worker), before the worker starts
  A1  clawd in the worker (--cache off: the scene built, not restored)
  B   clawd_locks in the worker (another character: analytic hair, other objects and materials)
  A2  clawd in the worker again
  A1, A2 against A0: trace diff `no differences` (stage times left out), qa.json values identical, no leak reported
  C1, C2  clawd in the worker with the cache on: cold, then warm (every step restored), against A0 the same way
It also checks the process records (`ps` lists the worker, a job's record is gone once it ends, `worker stop` leaves no
worker and no record) and prints the worker's resident memory idle and after each job.
"""
import json, os, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PY = sys.executable
sys.path.insert(0, HERE)
from cache_builds import copy_checkout  # noqa: E402


def main(args):
    boards = args[args.index('--boards') + 1] if '--boards' in args else 'views'
    root = tempfile.mkdtemp(prefix='charkit-worker-')
    copy_checkout(root)
    sys.path.insert(0, root)
    from charkit import worker                                  # the copy's: its own folder, socket and record
    assert worker.ROOT == root, worker.ROOT
    env = dict(os.environ, CHARKIT_CACHE_DIR=os.path.join(root, 'charkit', 'out', '.cache'))
    out = lambda n: os.path.join(root, 'charkit', 'out', n)
    clawd = os.path.join(root, 'charkit', 'spec', 'clawd.json')
    locks = os.path.join(root, 'charkit', 'spec', 'clawd_locks.json')
    B = ['--boards', boards, '--no-blend']
    fails = []

    def cli(*a):
        return subprocess.run([PY, '-m', 'charkit'] + list(a), cwd=root, capture_output=True, text=True, env=env)

    def build(spec, o, *a):
        t = time.time()
        r = cli('build', spec, '--out', o, *a)
        if r.returncode:
            raise SystemExit('build %s failed:\n%s' % (o, (r.stdout + r.stderr)[-3000:]))
        w = next((json.loads(l.split(' ', 1)[1]) for l in r.stdout.splitlines() if l.startswith('CHARKIT_WORKER ')), None)
        recs = [json.loads(l) for l in open(os.path.join(o, 'trace.jsonl'))]
        steps = {x['name']: x['cache'] for x in recs if x.get('cache') and x['event'] in ('stage', 'span', 'product', 'part')}
        return dict(seconds=round(time.time() - t, 1), worker=w, steps=steps)

    def diff(a, b):
        return cli('trace', os.path.join(a, 'trace.jsonl'), os.path.join(b, 'trace.jsonl'), '--no-time').stdout.strip()

    def qa_same(a, b):
        va, vb = ({k: (c.get('value'), c.get('status')) for k, c in json.load(open(os.path.join(d, 'qa', 'qa.json')))
                   ['checks'].items()} for d in (a, b))
        return sorted(k for k in set(va) | set(vb) if va.get(k) != vb.get(k))

    def check(ok, what):
        print(('  ok    ' if ok else '  FAIL  ') + what, flush=True)
        if not ok:
            fails.append(what)
    print('checkout copy %s' % root, flush=True)
    R = {'A0': build(clawd, out('A0'), *B, '--cache', 'off', '--no-worker')}
    check(R['A0']['worker'] is None, 'A0 ran in a fresh Blender (%.1fs)' % R['A0']['seconds'])
    print(cli('worker', 'start').stdout.strip(), flush=True)
    pid = worker.info()['pid']
    mem = {'idle at start': worker.rss_mb(pid)}
    try:
        check(any('worker' in l and str(pid) in l for l in cli('ps').stdout.splitlines()), 'ps lists the worker (pid %d)' % pid)
        for n, spec, a in (('A1', clawd, ['--cache', 'off']), ('B', locks, ['--cache', 'off']), ('A2', clawd, ['--cache', 'off']),
                           ('C1', clawd, []), ('C2', clawd, [])):
            R[n] = build(spec, out(n), *B, *a)
            mem['idle after ' + n] = worker.rss_mb(pid)
            w = R[n]['worker']
            check(w is not None and w['pid'] == pid, '%s ran in the worker (job %s, %.1fs)' % (n, w and w['job'], R[n]['seconds']))
            check(w is not None and not w.get('leak'), '%s: no state left over from the job before' % n)
            check(not os.path.exists(os.path.join(out(n), '.pid.json')), '%s: the job\'s process record is gone' % n)
        for n in ('A1', 'A2', 'C1', 'C2'):
            d = diff(out('A0'), out(n))
            check(d == 'no differences', '%s against the fresh build: %s' % (n, d[:300]))
            q = qa_same(out('A0'), out(n))
            check(not q, '%s: qa.json values identical to the fresh build%s' % (n, '' if not q else ': ' + ', '.join(q)))
        check(all(not c.get('hit') for c in R['C1']['steps'].values()), 'C1 (worker, cache cold): everything ran')
        check(all(c.get('hit') for c in R['C2']['steps'].values()), 'C2 (worker, cache warm): everything restored')
        print('\ntimes (wall clock, s):', json.dumps({k: v['seconds'] for k, v in R.items()}))
        print('worker resident memory (MB):', json.dumps({k: round(v) if v else v for k, v in mem.items()}), flush=True)
    finally:
        print(cli('worker', 'stop').stdout.strip(), flush=True)
    check(not os.path.exists(os.path.join(worker.DIR, '.pid.json')) and not worker._alive(pid), 'stop left no worker and no record')
    print('%d checks failed' % len(fails) if fails else 'all checks passed')
    if '--keep' not in args:
        shutil.rmtree(root, ignore_errors=True)
    else:
        print('kept', root)
    return not fails


if __name__ == '__main__':
    sys.exit(0 if main(sys.argv[1:]) else 1)
