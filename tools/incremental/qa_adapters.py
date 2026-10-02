"""The QA of one bundle drawn on each wgpu adapter, side by side (incremental round 1, item 2: the QA's drawing on a GPU).

    python -m charkit script tools/incremental/qa_adapters.py BUILD_DIR OUT_DIR ADAPTER[,ADAPTER...] [--threads N]

Each adapter (CHARKIT_RENDER_ADAPTER: cpu, gpu, auto, or a name) runs `python -m charkit qa BUILD/bundle --profile full
--cache off --out OUT/ADAPTER` in its own process, all at once, its wall and CPU (os.wait4: the process and its threads,
Mesa's included) recorded; then every check compared across the runs (value and status). Writes OUT/adapters.json.
"""
import json, os, subprocess, sys, time

args = sys.argv[1:]
build, out, ads = args[0], args[1], args[2].split(',')
threads = args[args.index('--threads') + 1] if '--threads' in args else '4'
os.makedirs(out, exist_ok=True)
procs = {}
for a in ads:
    env = dict(os.environ, CHARKIT_RENDER_ADAPTER=a, CHARKIT_QA_PROFILE='full')
    for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMBA_NUM_THREADS', 'BLIS_NUM_THREADS',
              'VECLIB_MAXIMUM_THREADS', 'LP_NUM_THREADS'):
        env[k] = threads                                     # (a gate build's caps)
    env['OMP_WAIT_POLICY'] = 'PASSIVE'
    d = os.path.join(out, a)
    os.makedirs(d, exist_ok=True)
    log = open(os.path.join(out, a + '.log'), 'w')
    t = time.time()
    p = subprocess.Popen([sys.executable, '-m', 'charkit', 'qa', os.path.join(build, 'bundle'), '--profile', 'full',
                          '--cache', 'off', '--out', d], stdout=log, stderr=subprocess.STDOUT, env=env)
    procs[a] = (p, t, log)
res = {}
for a, (p, t, log) in procs.items():
    _, st, ru = os.wait4(p.pid, 0)
    log.close()
    res[a] = dict(rc=os.waitstatus_to_exitcode(st), wall=round(time.time() - t, 1), cpu=round(ru.ru_utime + ru.ru_stime, 1))
    q = os.path.join(out, a, 'qa.json')
    if os.path.exists(q):
        Q = json.load(open(q))
        m = Q.get('measured') or {}
        res[a].update(parts=m.get('parts'), draw=m.get('draw'), qa_cpu=m.get('cpu_s'), qa_wall=m.get('seconds'))
        res[a]['checks'] = {k: [v.get('value'), v.get('status')] for k, v in Q['checks'].items() if isinstance(v, dict)}
    print(a, {k: res[a].get(k) for k in ('rc', 'wall', 'cpu', 'qa_cpu', 'qa_wall')}, flush=True)
try:
    from charkit.render import gpu
    for a in ads:
        res[a]['adapter'] = gpu.device(a)[1]
except Exception as e:
    print('adapter info:', e)
first = ads[0]
for a in ads[1:]:
    A, B = res[first].get('checks') or {}, res[a].get('checks') or {}
    diff = {k: [A.get(k), B.get(k)] for k in sorted(set(A) | set(B)) if A.get(k) != B.get(k)}
    res[a]['differs_from_' + first] = diff
    print('%s vs %s: %d of %d checks differ' % (a, first, len(diff), len(set(A) | set(B))), flush=True)
    for k, v in list(diff.items())[:60]:
        print('   ', k, v[0], '->', v[1])
json.dump(res, open(os.path.join(out, 'adapters.json'), 'w'), indent=1, default=str)
