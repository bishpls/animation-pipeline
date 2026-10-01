"""the back view's flick pixels against the mass behind them (round 4): per flick (lower_back locks lo-hi) its pixels'
cel tone against the same pixel's with the flicks removed (the mass), the depth the flick stands off the mass (L),
and the angle between the two normals; a picture of the disagreement.
    python tools/hairshell3/flickoff.py BUILD PIECES_WITH PIECES_WITHOUT OUT.png [--view back]"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
from charkit import artifactqa as aq, lookqa, bundle
from splice2x2 import splice
from kinkattr import comps_of
a = sys.argv[1:]
opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
B0 = bundle.load(os.path.join(a[0], 'bundle'))
v = opt('--view', 'back'); az = {'front': 0.0, 'three_quarter': 35.5, 'profile': 90.0, 'back': 180.0}[v]
out = {}
for tag, pd in (('with', a[1]), ('without', a[2])):
    B = splice(B0, pd)
    fr = lookqa.HeadFrame(B, ppl=aq.HEAD_PPL, ss=1, win=aq.HEAD_WIN)
    surfs = lookqa._scene(B, skin_outline=True, line_scale=lookqa.line_scale(B, aq.HEAD_PPL, int(round((aq.HEAD_WIN[1] + aq.HEAD_WIN[2]) * aq.HEAD_PPL))))
    mesh, tone = aq.buffers(B, surfs, az, fr)
    zb, _, mi, ti, bc = fr.zbuffer([(s['V'], s['T'], s['slots'], s['cull']) for s in surfs], az, ids=True)
    names = np.array([s['o'].name for s in surfs] + ['-'])
    hull = np.array([bool(s['hull']) for s in surfs] + [False])
    lb = (names[np.where(mesh >= 0, mesh, len(surfs))] == 'hair_lower_back') & ~hull[np.where(mesh >= 0, mesh, len(surfs))]
    lock = np.full(mesh.shape, -1)
    for j in np.unique(mesh[lb]):
        o = surfs[j]['o']
        Lk = None
        try:
            Z = np.load(os.path.join(pd, 'lower_back.npz')); Lk = Z['lock']
        except Exception:
            pass
        sel = lb & (mesh == j) & (ti >= 0)
        T = surfs[j]['T']
        if Lk is not None and len(Lk) == len(surfs[j]['V']):
            lock[sel] = Lk[T[ti[sel], 0]]
    out[tag] = dict(tone=tone, zb=zb, lock=lock, lb=lb, mesh=mesh)
W_, O_ = out['with'], out['without']
L = float(B0.assembly['L'])
fl = W_['lock'] >= 7
both = fl & np.isfinite(W_['tone']) & np.isfinite(O_['tone']) & O_['lb']
print('flick px over the lower back mass', both.sum(), 'over anything else', (fl & ~O_['lb']).sum())
dt = W_['tone'] - O_['tone']
dz = (W_['zb'] - O_['zb']) / L
print('flick px', fl.sum(), 'with mass behind', both.sum())
for k in range(7, 11):
    m = both & (W_['lock'] == k)
    if m.sum() == 0:
        continue
    tw, to = np.rint(np.clip(W_['tone'][m], 0, 2)), np.rint(np.clip(O_['tone'][m], 0, 2))
    print('flick %d: %d px; tone flick lit/shade %.2f/%.2f, mass %.2f/%.2f; disagree %.2f; mean tone diff %+.3f; depth off the mass median %.4f L (p90 %.4f)' % (
        k, m.sum(), (tw == 0).mean(), (tw >= 1).mean(), (to == 0).mean(), (to >= 1).mean(), (tw != to).mean(),
        np.mean(dt[m]), np.median(np.abs(dz[m])), np.percentile(np.abs(dz[m]), 90)))
img = np.ones(fl.shape + (3,)) * 0.97
base = np.array([0.93, 0.62, 0.48])
t = np.nan_to_num(W_['tone'], nan=0)
hm = W_['mesh'] >= 0
img[hm] = base * (1 - 0.25 * np.clip(np.rint(t[hm]), 0, 2))[:, None]
dis = both & (np.rint(np.clip(W_['tone'], 0, 2)) != np.rint(np.clip(O_['tone'], 0, 2)))
img[dis & (W_['tone'] < O_['tone'])] = (1.0, 0.95, 0.2)    # the flick lit where the mass is shaded
img[dis & (W_['tone'] > O_['tone'])] = (0.3, 0.3, 1.0)     # the flick shaded where the mass is lit
ys, xs = np.nonzero(fl)
img = img[max(0, ys.min() - 60):ys.max() + 20, max(0, xs.min() - 80):xs.max() + 80]
Image.fromarray((img * 255).astype(np.uint8)).resize((img.shape[1] * 2, img.shape[0] * 2), Image.NEAREST).save(a[3])
