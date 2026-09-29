"""fit the overskirt panels' template knobs to the drawn panel masks on the authored body: the panels rebuilt from the
template (garments.panel) into a cached bundle, the bundle z-buffered on the design's grids, each panel's iou_tol per
view (weighted by the drawn pixels) the objective; a coordinate search, the right panel the left's mirror."""
import copy, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import ev
from charkit import bodymeasure as bm, garments as gm

d = ev.evaluator()
E = d['E']
spec = copy.deepcopy(E.spec)
for g in spec['garments']:
    if g['name'].startswith('overskirt_panel'):
        g.pop('source', None)
        g['offset'] = 0.02
G0 = E.geometry(spec=spec)
B = G0.bundle('viewport')
A, _ = E.assembly(spec)
L = A['head']['L']
names = [o['name'] for o in B['objects']]
idx = {n: i for i, n in enumerate(names)}
sheet = d['sheet']; masks = d['masks']; ppl = sheet.ppl
views = [v for v in ('front', 'three_quarter', 'profile', 'back')]
tol_px = bm.OUTLINE_TOL * ppl
base = {g['name']: g for g in spec['garments'] if g['name'].startswith('overskirt_panel')}
KEYS = ('az', 'width', 'length', 'flare', 'waist', 'spread')
REACH_W = 1.0


def tris(F):
    out = []
    for f in F:
        f = list(f)
        out += [[f[0], f[k], f[k + 1]] for k in range(1, len(f) - 1)]
    return np.array(out)


def spec_for(p, side):
    s = copy.deepcopy(base['overskirt_panel_' + side])
    for k, v in p.items():
        s[k] = (-v if side == 'R' and k == 'az' else v)
    return s


def score(p, detail=False):
    objs = B['objects']
    for side in ('L', 'R'):
        s = spec_for(p, side)
        Gp = gm.panel(A, s)
        o = objs[idx['overskirt_panel_' + side]]
        o['V'] = np.asarray(Gp['verts'], float)
        o['F'] = tris(Gp['faces'])
        if 'label' in o:
            o['label'] = np.full(len(o['F']), o['label'][0] if len(o['label']) else 7)
    labels = bm.piece_views(B, sheet, which=views)
    tot, per = 0.0, {}
    # reach: in the front view the panels' lowest row and outermost column against the drawn ones (L)
    lab = labels['front']
    ours = bm.member_mask(lab, idx, [('overskirt_panel_L', None), ('overskirt_panel_R', None)])
    drawn = masks['front__overskirt_panel_L'] | masks['front__overskirt_panel_R']
    if ours.any():
        ro, co = np.nonzero(ours); rd, cd = np.nonzero(drawn)
        c0 = lab.shape[1] / 2
        d_bot = (ro.max() - rd.max()) / ppl
        d_out = (np.abs(co - c0).max() - np.abs(cd - c0).max()) / ppl
    else:
        d_bot = d_out = 1.0
    per['reach bottom'] = round(d_bot, 3); per['reach out'] = round(d_out, 3)
    for side in ('L', 'R'):
        pid = 'overskirt_panel_' + side
        num = den = 0.0
        for v in views:
            dm = masks.get('%s__%s' % (v, pid))
            if dm is None or dm.sum() < 40:
                continue
            m = bm.member_mask(labels[v], idx, [(pid, None)])
            rr, cc = np.nonzero(dm | m)
            p_ = int(0.1 * ppl)
            sl = (slice(max(0, rr.min() - p_), rr.max() + p_ + 1), slice(max(0, cc.min() - p_), cc.max() + p_ + 1))
            val = bm.iou_tol(m[sl], dm[sl], tol_px)
            num += val * dm.sum(); den += dm.sum()
            per['%s %s' % (side, v)] = round(val, 3)
        tot += num / max(1, den) / 2
    tot -= REACH_W * (abs(d_bot) + abs(d_out))
    return (tot, per) if detail else tot


def search(p0, steps, rounds=4):
    p = dict(p0); best = score(p)
    for r in range(rounds):
        improved = False
        for k in KEYS:
            for sgn in (1, -1):
                q = dict(p); q[k] = p[k] + sgn * steps[k]
                sc = score(q)
                if sc > best + 1e-4:
                    p, best, improved = q, sc, True
                    break
        print('round %d: %.4f %s' % (r, best, {k: round(v, 3) for k, v in p.items()}), flush=True)
        if not improved:
            steps = {k: v / 2 for k, v in steps.items()}
    return p, best


if __name__ == '__main__':
    g = base['overskirt_panel_L']
    p0 = {k: float(g.get(k, dflt)) for k, dflt in (('az', 180.0), ('width', 0.4), ('length', 1.0), ('flare', 30.0),
                                                     ('waist', 0.5), ('spread', 0.2))}
    t = time.time(); s0, per0 = score(p0, True); print('start %.4f (%.1fs)' % (s0, time.time() - t), per0, flush=True)
    steps = {'az': 12.0, 'width': 0.1, 'length': 0.2, 'flare': 8.0, 'waist': 0.15, 'spread': 0.15}
    p, best = search(p0, steps, rounds=int(sys.argv[1]) if len(sys.argv) > 1 else 8)
    s1, per1 = score(p, True)
    print('best %.4f' % s1, per1)
    json.dump(p, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'panels_fit.json'), 'w'))
