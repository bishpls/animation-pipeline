"""The eye region on the head's sections, before any build: the hollow and cheek lead down the eye's column, the
across-face profile at the eye row, the predicted eye widths, and the head's own sheet checks. Run in the face worktree:
    python eye_lab.py [json configs...]"""
import json, os, sys, time
import numpy as np
sys.path.insert(0, os.getcwd())
from charkit import manifest, refcheck
from charkit.geom import headfit

spec = manifest.resolve(json.load(open('charkit/spec/clawd_body.json')))
fs = spec['ref']['face_sheet']; ex = spec.get('eyes', {}).get('x', 0.168)
t = time.time()
C = headfit.contours(refcheck._load(fs['image']), ex, fs.get('facing', -1))
V = headfit.skull_analytic(spec, log=lambda *a: None)
print('prep %.1fs' % (time.time() - t), 'eyes', C['eyes'])


def ycol(S, x0, z):
    k = int(np.argmin(np.abs(S.zs - z)))
    if not np.isfinite(S.cy[k]):
        return np.nan
    x = np.sin(S.th) * S.r[k]; y = S.cy[k] - np.cos(S.th) * S.r[k]
    f = np.cos(S.th) > 0
    o = np.argsort(x[f])
    if x0 > x[f].max() - 0.04:                    # off the face's front (the outline turns back there)
        return np.nan
    return float(np.interp(x0, x[f][o], y[f][o]))


def measure(S, W):
    zs = np.arange(0.2, -0.2 - 1e-9, -0.02)
    ys = np.array([ycol(S, ex, z) for z in zs])
    chord = np.interp(zs, [zs[-1], zs[0]], [ys[-1], ys[0]])
    hollow = float(np.max(ys - chord))
    at = float(np.interp(0.0, zs[::-1], ys[::-1]))
    below = (zs < -0.03) & (zs > -0.16)
    lead = float(at - ys[below].min())
    zc = W['zc'] if W else 0.03
    fw = (C['eyes'].get('front') or {}).get('w', 0.178)
    yi, yo = ycol(S, ex - fw / 2, zc), ycol(S, ex + fw / 2, zc)
    dy = yo - yi
    a = np.radians(C['az3'])
    across = [(round(x, 2), round(ycol(S, x, zc) - ycol(S, ex, zc), 3)) for x in (0.0, 0.05, 0.1, 0.168, 0.22, 0.26, 0.3)]
    return dict(hollow=round(hollow, 4), cheek_lead=round(lead, 4), y_eye=round(ycol(S, ex, zc), 4),
                prof_w=round(dy, 4), prof_ratio=round(dy / C['eyes']['profile']['w'], 2),
                tq_ratio=round((fw * np.cos(a) + dy * np.sin(a)) / C['eyes']['three_quarter']['w'], 2),
                col=[(round(z, 2), round(y, 3)) for z, y in zip(zs[::2], ys[::2])], across=across)


def concavity(S, h=0.06):
    """local hollows over the eye region: at each (x, z) on a grid, how far the surface sits behind the chord of its
    neighbours h L away, along x and along z -> (max along x, where), (max along z, where)."""
    xs = np.arange(0.02, 0.34, 0.02); zg = np.arange(0.3, -0.3, -0.02)
    Y = np.array([[ycol(S, x, z) for x in xs] for z in zg])
    n = int(round(h / 0.02))
    cx = (Y[:, n:-n] - 0.5 * (Y[:, :-2 * n] + Y[:, 2 * n:]))
    cz = (Y[n:-n, :] - 0.5 * (Y[:-2 * n, :] + Y[2 * n:, :]))
    i = np.unravel_index(np.nanargmax(cx), cx.shape); j = np.unravel_index(np.nanargmax(cz), cz.shape)
    return ((round(float(cx[i]), 4), (round(xs[i[1] + n], 2), round(zg[i[0]], 2))),
            (round(float(cz[j]), 4), (round(xs[j[1]], 2), round(zg[j[0] + n], 2))))


cfgs = [json.loads(a) for a in sys.argv[1:]] or [None, {'eye_region': 'window'}]
for cfg in cfgs:
    terms = cfg.pop('terms') if isinstance(cfg, dict) and 'terms' in cfg else ('corr', 'rel', 'cheek', 'scale', 'warp', 'socket')
    S, rep = headfit.assemble(headfit.Face(C), V, face=cfg, terms=tuple(terms))
    m = measure(S, rep.get('eye_window'))
    checks, _ = headfit.grade(S, spec, C['design'])
    st = {}
    for k, v in checks.items():
        st.setdefault(v.get('status'), []).append(k)
    print('\n==', cfg, 'window', rep.get('eye_window'))
    for k in ('hollow', 'cheek_lead', 'y_eye', 'prof_w', 'prof_ratio', 'tq_ratio'):
        print('  %-11s %s' % (k, m[k]))
    print('  concave x, z', concavity(S))
    print('  column', m['col']); print('  across', m['across'])
    print("  vals", {k: checks[k].get("value") for k in checks})
    print('  checks', {k: len(v) for k, v in st.items()}, 'not PASS:', {k: (checks[k].get('value'), checks[k]['status'])
                                                                      for k in checks if checks[k].get('status') != 'PASS'})


if os.environ.get('SHADE'):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import shade
    from PIL import Image
    rows = []
    for cfg in [json.loads(a) for a in sys.argv[1:]] or [None]:
        terms = cfg.pop('terms') if isinstance(cfg, dict) and 'terms' in cfg else ('corr', 'rel', 'cheek', 'scale', 'warp', 'socket')
        S, rep = headfit.assemble(headfit.Face(C), V, face=cfg, terms=tuple(terms))
        rows.append(np.concatenate([shade.shade(S, az) for az in (0, C['az3'], 70)], 1))
    Image.fromarray(np.concatenate(rows, 0)).save(os.environ['SHADE'])
    print('shaded', os.environ['SHADE'])
