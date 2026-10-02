"""the lock-shell fit's reproducibility (tool/hairshell3): build_shells on a fit context (lockshell.context's pickle),
optionally with its float inputs perturbed (--perturb EPS: every field, the hull frame and the chart's centre moved by
uniform noise of EPS m: two builds of one head on two machines differ by ~1e-10), -> OUT.json: per lock its name, views,
costs, the sha256 of its shell's vertex array, its Bezier control points and twist; the fits' least_squares status.

    python tools/hairshell3/determ.py CTX.pkl OUT.json [--perturb 1e-10] [--seed 0] [--opts JSON]
    python tools/hairshell3/determ.py --cmp A.json B.json      per lock: identical, or its max |dV|
"""
import hashlib, json, os, pickle, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import numpy as np

PILOT = {'families': ['side_locks'], 'groups': [{'family': 'lower_back', 'view': 'back', 'phi': [100, 175],
                                                 'replace': False}]}


def perturb(ctx, eps, seed=0):
    rng = np.random.RandomState(seed)
    F = dict(ctx['F'])
    for k in ('R', 'Rn', 'S'):
        a = np.array(F[k], float)
        m = np.isfinite(a)
        a[m] += rng.uniform(-eps, eps, m.sum())
        F[k] = a
    ch = F['chart']
    import copy
    ch = copy.copy(ch)
    ch.c = np.asarray(ch.c, float) + rng.uniform(-eps, eps, 3)
    F['chart'] = ch
    s, t = ctx['hull_frame']
    hf = (s + rng.uniform(-eps, eps), np.asarray(t, float) + rng.uniform(-eps, eps, 3))
    views = {}
    for k, v in ctx['views'].items():
        v2 = copy.copy(v)
        for a in ('ppl', 'axis', 'eye_y'):
            setattr(v2, a, float(getattr(v2, a)) + rng.uniform(-eps, eps))
        v2.grid_eye = tuple(float(x) + rng.uniform(-eps, eps) for x in v2.grid_eye)
        views[k] = v2
    return dict(ctx, F=F, hull_frame=hf, views=views)


def run(ctx, opts, ls_kw=None, polish=None):
    from scipy import optimize
    from charkit.geom import lockshell as ls
    real = optimize.least_squares
    stats = []
    t0 = [time.time()]

    def patched(f, x0, **k):
        k.update(ls_kw or {})
        s = real(f, x0, **k)
        n = int(s.nfev)
        if polish:
            k2 = dict(k, **polish)
            s = real(f, s.x, **k2)
            n += int(s.nfev)
        stats.append(dict(status=int(s.status), nfev=n, cost=float(s.cost)))
        if os.environ.get('DETERM_LOG'):
            print('  fit %d: status %d nfev %d m %d %.1f s' % (len(stats), s.status, n, len(s.fun), time.time() - t0[0]),
                  flush=True)
        t0[0] = time.time()
        return s
    optimize.least_squares = patched
    t = time.time()
    try:
        r = ls.build_shells(ctx['F'], ctx['masks'], ctx['views'], ctx['hull_frame'], ctx['L'],
                            dict(opts, split=ctx['split']), log=None)
    finally:
        optimize.least_squares = real
    locks = []
    for k, ps in r['parts'].items():
        for p in ps:
            f = p['fit']
            locks.append(dict(name=f['name'], group=k, views=f['views'], cost=f['cost_px'], iou=f['iou'],
                              folds=f['folds'], sha=hashlib.sha256(np.ascontiguousarray(p['V']).tobytes()).hexdigest()[:16],
                              V=np.asarray(p['V']).round(9).tolist()))
    return dict(locks=locks, fits=stats, seconds=round(time.time() - t, 1),
                fitted_2plus=r['report'].get('fitted_2plus'))


def cmp(a, b):
    A = {x['name']: x for x in json.load(open(a))['locks']}
    B = {x['name']: x for x in json.load(open(b))['locks']}
    same = 0
    for n in sorted(set(A) | set(B)):
        if n not in A or n not in B:
            print('  %-28s only in %s' % (n, 'A' if n in A else 'B')); continue
        x, y = A[n], B[n]
        if x['sha'] == y['sha']:
            same += 1; print('  %-28s identical' % n); continue
        Va, Vb = np.array(x['V']), np.array(y['V'])
        d = float(np.abs(Va - Vb).max()) if Va.shape == Vb.shape else float('nan')
        print('  %-28s max|dV| %.2e m  views %s / %s  cost %s / %s  folds %s / %s' % (
            n, d, x['views'], y['views'], x['cost'], y['cost'], x['folds'], y['folds']))
    print('identical %d of %d' % (same, len(set(A) | set(B))))


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == '--cmp':
        cmp(a[1], a[2]); sys.exit(0)
    ctx = pickle.load(open(a[0], 'rb'))
    if '--perturb' in a:
        ctx = perturb(ctx, float(a[a.index('--perturb') + 1]), int(a[a.index('--seed') + 1]) if '--seed' in a else 0)
    opts = json.loads(a[a.index('--opts') + 1]) if '--opts' in a else PILOT
    ls_kw = json.loads(a[a.index('--ls') + 1]) if '--ls' in a else None
    polish = json.loads(a[a.index('--polish') + 1]) if '--polish' in a else None
    res = run(ctx, opts, ls_kw, polish)
    json.dump(res, open(a[1], 'w'))
    print('%d locks, %d fits (%d at max_nfev), %.0f s; 2+ views %s' % (
        len(res['locks']), len(res['fits']), sum(1 for s in res['fits'] if s['status'] == 0), res['seconds'],
        res['fitted_2plus']))
    print('nfev', [s['nfev'] for s in res['fits']], 'status', [s['status'] for s in res['fits']])
