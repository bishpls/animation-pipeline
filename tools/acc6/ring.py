"""The crab placed by hand round the star (tool/accessories6): for each bearing (the direction from the star's centroid
to the crab's in the front view, degrees: 0 the picture's right, 90 up) the crab's anchor and tilt solved so it sits
there `gap` L clear of the star with its own axis (toward its claws) at `axis` degrees in the picture (default: the
bearing plus the drawn pair's turn, accqa: the crab turned against the star as drawn); its facing turned with its
anchor (the start's facing kept against the surface), the star as given. Each placement measured as accfit measures it
(the loss, its terms, the pair checks). Writes the starts for `sweep optimize` (its knobs' values) and each placement's
specs.
    python tools/acc6/ring.py BUILD SPEC OUT_DIR [--shape crab=BEST_OVERRIDE.json] [--bearings 0,45,...]
                              [--extra NAME:BEARING:AXIS,...] [--gap 0.012]"""
import json, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import numpy as np
from scipy.optimize import minimize
from charkit import accfit, accqa, accessories as acc, declared


def opt(a, k, d=None):
    return a[a.index(k) + 1] if k in a else d


def front_reading(S, specs):
    """(star mask, crab mask, crab axis) in the front view, each drawn alone."""
    clips = S.place(specs)
    _, al, _ = S.draw(clips, 'front')
    kinds = [k for k, _, _, _ in clips]
    c = clips[kinds.index('crab')]
    ax = accqa.axis_in_view(accqa.own_axes(c[1], c[3], S.centre), 0.0)
    return al[kinds.index('star')], al[kinds.index('crab')], ax


def solve(S, specs, bearing, axis, gap_t):
    by = {s['kind']: dict(s) for s in specs}
    star, crab0 = by['star'], by['crab']
    a0 = np.asarray(crab0['at'], float)
    az0, el0 = math.degrees(math.atan2(a0[0], -a0[1])), math.degrees(math.atan2(a0[2], math.hypot(a0[0], a0[1])))
    fa0, fe0 = crab0['facing']

    def make(x):
        dx, dz, tilt = x
        a = a0 + np.array([dx, 0.0, dz])
        az, el = math.degrees(math.atan2(a[0], -a[1])), math.degrees(math.atan2(a[2], math.hypot(a[0], a[1])))
        return [dict(crab0, at=[round(float(v), 5) for v in a], tilt=round(float(tilt), 3),
                     facing=[round(fa0 + (az - az0), 3), round(fe0 + (el - el0), 3)]), star]

    def cost(x):
        ms, mc, ax = front_reading(S, make(x))
        r = declared.pair_read(ms, mc, S.ppl, ax)
        if r is None:
            return 50.0
        return (declared._wrap(r['bearing'] - bearing) / 10) ** 2 + ((r['gap'] - gap_t) / 0.01) ** 2 + \
            (declared._wrap(r['axis'] - axis) / 5) ** 2
    best = None
    sa = np.asarray(star['at'], float)
    for d in (0.16, 0.21, 0.26):                    # (the crab's anchor that far from the star's, along the bearing)
        b = math.radians(bearing)
        x0 = [sa[0] + d * math.cos(b) - a0[0], sa[2] + d * math.sin(b) - a0[2], float(declared._wrap(axis - 90.0))]
        simplex = [x0, [x0[0] + 0.03, x0[1], x0[2]], [x0[0], x0[1] + 0.03, x0[2]], [x0[0], x0[1], x0[2] + 10]]
        r = minimize(cost, x0, method='Nelder-Mead', options=dict(xatol=1e-3, fatol=1e-4, maxfev=160,
                                                                  initial_simplex=simplex))
        if best is None or r.fun < best.fun:
            best = r
        if best.fun < 0.02:
            break
    return make(best.x), float(best.fun)


def main(a):
    build, spec_p, out = a[0], a[1], a[2]
    os.makedirs(out, exist_ok=True)
    spec = accfit._spec(spec_p)
    specs = [x for x in spec.get('accessories') or [] if x['kind'] in accfit.KINDS]
    for kv in (opt(a, '--shape') or '').split(','):
        if kv:
            kind, p = kv.split('=')
            bo = json.load(open(p))
            knobs = {k: v for k, v in bo.get('knobs', bo).items() if not k.startswith('pose.')}
            for x in specs:
                if x['kind'] == kind:
                    sh = dict(x.get('shape') or {})
                    for k, v in knobs.items():
                        accfit.put(sh, k, v)
                    x['shape'] = sh
    rel = json.loads(opt(a, '--relate', '{}'))
    accfit.W_REL = float(rel.get('w_rel', accfit.W_REL))
    accfit.ANGLE_NEAR = rel.get('angle_near', accfit.ANGLE_NEAR)
    S = accfit.Scene(build, accfit.design(spec))
    # the drawn pair's turn in the front view
    D = S.D['views']['front']
    rd = declared.pair_read(D['star'], D['crab'], S.ppl, accqa.CRAB_AXIS['front'])
    turn = rd['turn']
    gap_t = float(opt(a, '--gap', 0.012))
    bs = opt(a, '--bearings') or '0,45,90,135,180,225,270,315'
    jobs = [] if bs == 'none' else [('b%03d' % int(b), float(b), float(b) + turn) for b in bs.split(',')]
    for e in (opt(a, '--extra') or '').split(','):
        if e:
            n, b, ax = e.split(':')
            jobs.append((n, float(b), float(ax)))
    res = {'drawn': rd, 'starts': {}, 'placements': {}}
    for name, b, ax in [('given', None, None)] + jobs:
        if b is None:
            sp, c = specs, 0.0
        else:
            sp, c = solve(S, specs, b, ax, gap_t)
        r = S.measure(sp)
        crab = next(x for x in sp if x['kind'] == 'crab')
        res['placements'][name] = dict(bearing=b, axis=ax, cost=round(c, 4), loss=r['loss'],
                                       specs=sp, views={k: {v: {f: x.get(f) for f in ('iou', 'pos', 'angle', 'visible')}
                                                            for v, x in r[k]['views'].items()} for k in accfit.KINDS},
                                       seat={k: r[k]['seat'] for k in accfit.KINDS}, back=r['star']['back'],
                                       pair={k: (c_.get('value'), c_.get('status')) for k, c_ in (r.get('pair') or {}).items()})
        if b is not None:
            res['starts'][name] = {'crab.at.0': crab['at'][0], 'crab.at.1': crab['at'][1], 'crab.at.2': crab['at'][2],
                                   'crab.facing.0': crab['facing'][0], 'crab.facing.1': crab['facing'][1],
                                   'crab.tilt': crab['tilt']}
        json.dump(dict(specs=sp), open(os.path.join(out, 'specs_%s.json' % name), 'w'), indent=1)
        print('%-12s bearing %s axis %s cost %.4f loss %.3f vis %s pair %s' % (
            name, b, ax, c, r['loss'], {k: [x['visible'] for x in r[k]['views'].values()] for k in accfit.KINDS},
            {k.replace('acc_crab_', ''): v for k, v in res['placements'][name]['pair'].items()}), flush=True)
    json.dump(res, open(os.path.join(out, 'ring.json'), 'w'), indent=1, default=float)


if __name__ == '__main__':
    main(sys.argv[1:])
