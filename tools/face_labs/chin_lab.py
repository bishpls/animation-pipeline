"""the chin lab (face round 4): the front's V at sub-pixel precision, and where the cage puts the jaw's rim.

The jaw checks read the outline off a picture at the head sheet's own px per L (401: a pixel is 0.0025 L). chin_angle
fits the V's arms over 0.06 L of arc, 24 px, so a pixel's step at one end of an arm moves the opening 2.4 degrees:
at the sheet's scale the check can't tell geometry changes of a few thousandths of L apart. Ours can be drawn at any
scale, so this reads the same measures (faceregion.taper_front on the emulated outline, hair hidden) on ours drawn K
times finer, in the level camera (the design's projection) and the boards'; the design's own values stay the sheet's.
Per cage column round the chin it also prints the rim UnderJaw finds (where the column's envelope crosses its
underside) against the rim's target (the design's V less TIP_BIAS), and where the rim falls between the cage's rows.

    python chin_lab.py GEOM_DIR [K=4] [JSON=out.json] [KEY=VALUE ...]     # headgeom constants for a try

GEOM_DIR holds a build's head_code.npz and body_code.npz (the local assembly: jaw_lab.local, the skin subdivided once
as the QA's eval mesh). DESIGN_CACHE=path.pkl as taper_lab's."""
import ast, json, math, os, pickle, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import numpy as np
from charkit import faceregion as fr
from charkit.geom import headgeom as hg

import jaw_lab


def design(spec):
    cache = os.environ.get('DESIGN_CACHE')
    if cache and os.path.exists(cache):
        return pickle.load(open(cache, 'rb'))
    got = fr.design_jaw(spec, 0.168)
    if cache:
        pickle.dump(got, open(cache, 'wb'))
    return got


def front(V, T, iris, ez, L, ppl, az, z0):
    """ours in front, bare, in both cameras at ppl -> {cam: taper_front's dict}."""
    iris = fr.eye_anchor(np.asarray(iris), ez)
    ref = iris.mean(0)
    out = {}
    for cam, cfg in (('board', fr.BOARD_CAM), ('level', fr.LEVEL_CAM)):
        target = np.array([0.0, 0.0, ez + cfg['lift'] * L])
        cls = fr.board_view([(V, T, np.ones(len(T), int))], (V, T), az['front'], target, ref, L, ppl, dist=cfg['dist'])[0]
        out[cam] = fr.taper_front(cls, ppl, z0)
    return out


def rims(geom, spec):
    """per cage column round the chin: the rim UnderJaw finds, its target, where it falls between the rows."""
    from charkit import code_base
    spec = dict(spec)
    spec['head_code'] = os.path.join(geom, 'head_code.npz')
    S, C, _ = code_base.head_sections(spec)
    H = code_base.head_mesh(S, C, -0.52, code_base.eye_outline(spec), code_base.mouth_block(spec))
    Cg = H['cage']
    U = Cg.under
    rows = []
    for t in Cg.th:
        if t < -1e-9 or t > 0.8:
            continue
        P, s, info = U.meridian(t)
        if info['rim'] is None:
            continue
        zt = U.z_top_at(t)
        sel = np.nonzero(np.isclose(Cg.chart_th, t, atol=1e-7) & (Cg.chart_z < zt - 1e-9) & (Cg.chart_z > U.z_bottom))[0]
        q = U.arc(t, np.sort(Cg.chart_z[sel])[::-1], s, info)
        k = int(np.searchsorted(q, info['s_rim']))
        pos = k - 1 + (info['s_rim'] - q[k - 1]) / (q[k] - q[k - 1]) + 1 if 0 < k < len(q) else float('nan')
        x = info['rim'][0] * math.sin(t)
        rows.append(dict(theta=round(float(t), 3), x=round(x, 4), z=round(info['rim'][1], 4),
                         target=round(float(np.interp(x, U.jx, U.jz)), 4), row=round(float(pos), 2)))
    return rows


def main(argv):
    geom = argv[0]
    k = 4
    for kv in argv[1:]:
        key, v = kv.split('=', 1)
        if key == 'K':
            k = int(v)
        elif key == 'JSON':
            os.environ['JSON'] = v
        else:
            setattr(hg, key, ast.literal_eval(v))
            print('set', key, v)
    t0 = time.time()
    spec = jaw_lab.spec_of()
    D, ppl, _, az = design(spec)
    z0 = D['front']['taper']['z0']
    V, T, iris, ez, L, A = jaw_lab.local(geom)
    out = dict(design={kk: D['front']['taper'].get(kk) for kk in ('chin_angle', 'chin_arms', 'tip_share', 'w90')})
    for scale in (1, k):
        F = front(V, T, iris, ez, L, ppl * scale, az, z0)
        for cam, M in F.items():
            arms = M.get('arms') or {}
            out['%s_x%d' % (cam, scale)] = dict(chin_angle=M.get('chin_angle'), chin_arms=M.get('chin_arms'),
                                                tip_share=M.get('tip_share'), w90=M.get('w90'), chin=M.get('chin'),
                                                bend=max([a['bend'] for a in arms.values()] or [None]))
    out['rims'] = rims(geom, spec)
    print('%-10s %8s %14s %6s %7s %6s' % ('', 'angle', 'arms', 'tip', 'w90', 'bend'))
    for key in ['design'] + [kk for kk in out if kk.startswith(('board', 'level'))]:
        m = out[key]
        print('%-10s %8s %14s %6s %7s %6s' % (key, m.get('chin_angle'), m.get('chin_arms'), m.get('tip_share'),
                                             m.get('w90'), m.get('bend', '')))
    print('rim per column (theta, x, z, target, z - target, row):')
    for r in out['rims']:
        print('  %6.3f %7.4f %7.4f %7.4f %+.4f %5.2f' % (r['theta'], r['x'], r['z'], r['target'], r['z'] - r['target'],
                                                        r['row']))
    print('(%.1fs)' % (time.time() - t0))
    if os.environ.get('JSON'):
        json.dump(out, open(os.environ['JSON'], 'w'), indent=1, default=float)
    return out


if __name__ == '__main__':
    main(sys.argv[1:])
