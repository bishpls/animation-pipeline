"""does the puff contain the arm side of the shoulder? The build's assembly (the fast evaluator at its own spec, its
head and body codes from geom/) and its puff (garments.puff at the spec, or with --set overrides), the skin's vertices
of the bridge (body part shoulder_SIDE) and the upper arm (arm_SIDE, down to the puff's band) placed in the puff's frame
(t down the arm, angle round it: 0 out, 90 front, 180 in, -90 back), and per vertex the puff's radius there less the
vertex's: the margin (L; < 0 the skin comes out through the puff). Prints the share and depth outside per angle sector
and station band; --png the margin map (angle x t).
    python tools/garments6/contain.py BUILD [--side left] [--set PATH=JSON ..] [--png OUT.png] [--gap 0.0]"""
import sys, os, json, copy
sys.path.insert(0, '.')
import numpy as np

args = sys.argv[1:]
def opt(k, d):
    if k in args:
        i = args.index(k); v = args[i + 1]; del args[i:i + 2]; return v
    return d
SIDE = opt('--side', 'left')
PNG = opt('--png', None)
GAP = float(opt('--gap', '0'))
sets = []
while '--set' in args:
    i = args.index('--set'); sets.append(args[i + 1]); del args[i:i + 2]
build = args[0]

from charkit import sweep, bodyeval, garments as gm
B0 = sweep.load_bundle(build, True)
spec = sweep.base_spec({'base': build, 'stage': 'garments'}, B0)
for s in sets:
    p, v = s.split('=', 1)
    bodyeval.set_knob(spec, p, json.loads(v))
E = bodyeval.Evaluator(spec)
A, how = E.assembly(spec)
hull = gm.hull_pieces(spec, A)
L = A['head']['L']
name = 'sleeve_' + ('L' if SIDE == 'left' else 'R')
sp = dict(next(g for g in spec['garments'] if g['name'] == name), _spec=spec)
G = gm.puff(A, sp, hull)
fr = G['frame']
h, d, o, f = fr['origin'], fr['d'], fr['o'], fr['f']
V = np.asarray(G['verts'], float)
nth = sp.get('cols', 64)
Q = V[1:].reshape(-1, nth, 3) - h
TT, XX, YY = Q @ d / L, Q @ o / L, Q @ f / L
ts = TT.mean(1)
th = np.arctan2(YY, XX).mean(0)
RR = np.hypot(XX, YY)
parts = A['body']['parts']
idx = []
for k in ('shoulder_' + SIDE, 'arm_' + SIDE):
    if k in parts:
        a_, b_ = parts[k]
        idx += list(range(a_, b_))
idx = np.array(idx)
P = A['verts'][idx] - h
tq, xq, yq = P @ d / L, P @ o / L, P @ f / L
thq, rq = np.arctan2(yq, xq), np.hypot(xq, yq)
t_band = G.get('t_band') or ts.max()
k = (tq <= t_band) & (tq >= ts.min() - 0.15)
# the puff's radius at each vertex's (t, angle): bilinear on its rows and columns
order = np.argsort(th)
ths, RRs = th[order], RR[:, order]
def R_at(t, a):
    i = np.clip(np.searchsorted(ts, t) - 1, 0, len(ts) - 2)
    w = np.clip((t - ts[i]) / np.maximum(ts[i + 1] - ts[i], 1e-9), 0, 1)
    ra = np.array([np.interp(a_, ths, RRs[ii], period=2 * np.pi) for a_, ii in zip(a, i)])
    rb = np.array([np.interp(a_, ths, RRs[ii + 1], period=2 * np.pi) for a_, ii in zip(a, i)])
    return ra * (1 - w) + rb * w
tq_, thq_, rq_ = tq[k], thq[k], rq[k]
m = R_at(tq_, thq_) - rq_ - GAP
deg = np.degrees(thq_)
print('== %s %s: %d skin vertices (bridge + arm to the band t %.3f) | puff rows t %.3f..%.3f' % (
    os.path.basename(build), name, len(m), t_band, ts.min(), ts.max()))
print('   outside (margin < 0): %.1f%%, depth p90 %.3f max %.3f L' % (
    100 * (m < 0).mean(), np.percentile(-m[m < 0], 90) if (m < 0).any() else 0, -m.min()))
print('   by sector (deg; 0 out, 90 front, 180 in, -90 back): share outside, max depth L, t range outside')
for a0 in range(-180, 180, 30):
    s = (deg >= a0) & (deg < a0 + 30)
    if s.sum():
        bad = s & (m < 0)
        print('   %4d..%4d  n %4d  out %5.1f%%  max %.3f  t %s' % (
            a0, a0 + 30, s.sum(), 100 * bad.sum() / s.sum(), max(0, -m[s].min()),
            '%.2f..%.2f' % (tq_[bad].min(), tq_[bad].max()) if bad.any() else '-'))
print('   by station band (t L): share outside, max depth')
for t0 in np.arange(np.floor(ts.min() * 10) / 10, ts.max(), 0.05):
    s = (tq_ >= t0) & (tq_ < t0 + 0.05)
    if s.sum():
        print('   t %5.2f..%5.2f  n %4d  out %5.1f%%  max %.3f' % (t0, t0 + 0.05, s.sum(), 100 * (m[s] < 0).mean(),
                                                               max(0, -m[s].min())))
if PNG:
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 1, figsize=(9, 5))
    sc = ax.scatter(deg, tq_, c=np.clip(m, -0.08, 0.08), cmap='RdBu', vmin=-0.08, vmax=0.08, s=4)
    ax.invert_yaxis(); ax.set_xlabel('angle (0 out, 90 front, 180/-180 in, -90 back)'); ax.set_ylabel('t (L down the arm)')
    ax.set_title('%s %s: puff radius - skin radius (red: skin outside)' % (os.path.basename(build), name))
    fig.colorbar(sc); fig.savefig(PNG, dpi=80); print(PNG)
