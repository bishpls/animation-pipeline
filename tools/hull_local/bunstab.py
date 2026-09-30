"""The buns' fit under tiny input moves (tool/hull-local; face round 5's terminator carrier): how far each bun moves when
the fit's inputs move by 1 um (the head's centre, the hull's bun points), on the real inputs of a build.

    python tools/hull_local/bunstab.py capture BUILD HULL_DIR OUT.pkl      # the fit's inputs, both buns (a pieces run)
    python tools/hull_local/bunstab.py stab IN.pkl OUT.json [--method nm|soft] [--eps 1e-6] [--sides L,R]

capture runs charkit.cli.pieces_hair's build on BUILD's resolved spec with HULL_DIR's hull (hairswap.py's _cut) and
records every hairpieces.fit_block call's arguments. stab refits each bun on them and on perturbed copies: the head's
centre moved eps (m) along +-x, +-y, +-z; every bun point moved eps in a random direction (3 seeds); all bun points moved
eps along +y. The move: the bun mesh's (bun_block + tails) largest vertex displacement from the unperturbed fit, in L.
The acceptance (the brief): under 1e-4 L for every perturbation, both buns. Also each fit's per-view IoU and loss."""
import contextlib, io, json, os, pickle, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
os.chdir(ROOT)
import numpy as np


def capture(build, hull_dir, out):
    import hairswap
    from charkit import bodyeval
    from charkit.geom import hairpieces as hp
    calls, case = [], {}
    real, real_build = hp.fit_block, hp.build

    def rec(*a, **k):
        calls.append((a, k))
        return real(*a, **k)

    def rec_build(C, *a, **k):
        case['L'] = float(C.L)
        return real_build(C, *a, **k)
    hp.fit_block, hp.build = rec, rec_build
    spec_full = bodyeval.resolve('charkit/spec/clawd.json')
    t = time.time()
    P, centre, buns, fit = hairswap.run(hairswap._cut(build, hull_dir, os.path.join(build, 'geom', 'head_code.npz')),
                                        spec_full)
    hp.fit_block, hp.build = real, real_build
    L = case['L']
    sides, own = [], hairswap.own(build)
    for (a, k), side in zip(calls, ('bun_L', 'bun_R')):
        sides.append(dict(side=side, args=a, kwargs=k, rebuilt=P.get(side), built=own.get(side)))
        if own.get(side) is not None and len(own[side]) == len(P[side]):
            print(side, 'rebuilt vs the build\'s own: %.3g L' % (np.linalg.norm(own[side] - P[side], axis=1).max() / L))
    pickle.dump(dict(sides=sides, centre=centre, L=L, build=build, hull=hull_dir, seconds=time.time() - t),
                open(out, 'wb'))
    print('captured', len(calls), 'fit calls', out, round(time.time() - t), 's')


def bun_mesh(P, head_c, style, sgn, fit, kind):
    from charkit.geom import hairpieces as hp
    V = [hp.bun_block(P, head_c, style, sgn, fit, kind)['V']]
    if fit.get('tails') is not None:
        V += [b['V'] for b in hp.bun_tails(fit['c'], fit['R'], fit['half'], head_c, style, fit['tails'])]
    return np.concatenate(V)


def fit_one(a, k, method):
    from charkit.geom import hairpieces as hp
    k = dict(k)
    if method is not None:
        k['method'] = method
    t = time.time()
    fit, rep = hp.fit_block(*a, **k)
    return fit, rep, time.time() - t


def perturbations(P, head_c, eps):
    """(name, P, head_c) moved by eps: the head's centre along each axis both ways, every bun point in a random
    direction (3 seeds), all bun points along +y; interleaved so a prefix (--only N) samples both inputs."""
    head, pts = [], []
    for i, ax in enumerate('xyz'):
        for s in (1, -1):
            e = np.zeros(3); e[i] = s * eps
            head.append(('head_c %s%s' % ('+' if s > 0 else '-', ax), P, head_c + e))
    for seed in range(3):
        d = np.random.default_rng(seed).normal(size=P.shape)
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        pts.append(('points random %d' % seed, P + eps * d, head_c))
    pts.append(('points +y', P + np.array([0.0, eps, 0.0]), head_c))
    head = [head[0], head[3], head[4], head[1], head[2], head[5]]
    out = []
    for i in range(6):
        out.append(head[i])
        if i < len(pts):
            out.append(pts[i])
    return out


def override(sets):
    """hairpieces' module constants for this run: 'NAME=V,NAME=A:B:C' (a tuple)."""
    from charkit.geom import hairpieces as hp
    for kv in (sets or '').split(','):
        if kv:
            k, v = kv.split('=')
            setattr(hp, k, tuple(float(x) for x in v.split(':')) if ':' in v else float(v))
    return sets


def stab(inp, out, method=None, eps=1e-6, sides=None, sets=None, only=None):
    D = pickle.load(open(inp, 'rb'))
    L = D['L']
    override(sets)
    res = dict(input=inp, method=method or 'default', eps_m=eps, eps_L=eps / L, L=L, sets=sets, sides={})
    for S in D['sides']:
        if sides and S['side'][-1] not in sides:
            continue
        a, k = S['args'], S['kwargs']
        P, head_c, style = a[0], np.asarray(a[1], float), a[2]
        kind = a[7] if len(a) > 7 else k.get('kind', 'block')
        sgn = 1 if S['side'] == 'bun_L' else -1
        fit0, rep0, dt = fit_one(a, k, method)
        V0 = bun_mesh(P, head_c, style, sgn, fit0, kind)
        row = dict(seconds=round(dt, 1), after=rep0.get('after'), soft=rep0.get('soft'), before=rep0.get('before'),
                   perturbed={})
        if S.get('built') is not None and len(S['built']) == len(V0):
            row['vs_build_L'] = float('%.3g' % (np.linalg.norm(S['built'] - V0, axis=1).max() / L))
        for name, Pp, hc in perturbations(P, head_c, eps)[:only]:
            a2 = (Pp, hc) + tuple(a[2:])
            fit, rep, dt = fit_one(a2, k, method)
            V = bun_mesh(Pp, hc, style, sgn, fit, kind)
            mv = float(np.linalg.norm(V - V0, axis=1).max() / L)
            row['perturbed'][name] = dict(move_L=float('%.3g' % mv), after=rep.get('after'),
                                          loss=(rep.get('soft') or {}).get('loss'))
            print(S['side'], name, '%.3g L' % mv, rep.get('after'), round(dt, 1), 's', flush=True)
        mv = [r['move_L'] for r in row['perturbed'].values()]
        row['max_move_L'] = max(mv)
        row['median_move_L'] = float(np.median(mv))
        row['amplification'] = float('%.3g' % (max(mv) / (eps / L)))
        res['sides'][S['side']] = row
        print(S['side'], sets or '', 'max move %.3g L (x%.3g), median %.3g' % (max(mv), max(mv) / (eps / L),
              np.median(mv)), json.dumps({k_: float(v_) for k_, v_ in rep0.get('after').items()}),
              (rep0.get('soft') or {}).get('loss'), '%.1f s' % dt, flush=True)
    json.dump(res, open(out, 'w'), indent=1)
    return res


def main(a):
    if a[0] == 'capture':
        capture(*a[1:4])
    elif a[0] == 'stab':
        method = a[a.index('--method') + 1] if '--method' in a else None
        eps = float(a[a.index('--eps') + 1]) if '--eps' in a else 1e-6
        sides = a[a.index('--sides') + 1].split(',') if '--sides' in a else None
        only = int(a[a.index('--only') + 1]) if '--only' in a else None
        for i, sets in enumerate(a[a.index('--set') + 1].split(';') if '--set' in a else [None]):
            stab(a[1], a[2].replace('.json', '_%d.json' % i) if '--set' in a else a[2], method, eps, sides, sets, only)


if __name__ == '__main__':
    main(sys.argv[1:])
