"""a view's hair components (each surface's connected triangle sets: a lock shell, a wedge) over its cel tones, at the
head frame's 400 px/L, with the terminator's kinks: which pieces the terminator crosses where it steps.
    python tools/hairshell3/compview.py BUILD OUT.png [--view back] [--pieces DIR] [--crop r0,r1,c0,c1]"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from charkit import artifactqa as aq, lookqa, bundle
from kinkattr import comps_of
a = sys.argv[1:]
opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
B = bundle.load(os.path.join(a[0], 'bundle'))
if opt('--pieces'):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from splice2x2 import splice
    B = splice(B, opt('--pieces'))
v = opt('--view', 'back')
az = {'front': 0.0, 'three_quarter': 35.5, 'profile': 90.0, 'back': 180.0}[v]
ppl, win = aq.HEAD_PPL, aq.HEAD_WIN
fr = lookqa.HeadFrame(B, ppl=ppl, ss=1, win=win)
surfs = lookqa._scene(B, skin_outline=True, line_scale=lookqa.line_scale(B, ppl, int(round((win[1] + win[2]) * ppl))))
mesh, tone = aq.buffers(B, surfs, az, fr)
_, _, mi, ti, _ = fr.zbuffer([(s['V'], s['T'], s['slots'], s['cull']) for s in surfs], az, ids=True)
hair = np.array([aq.object_kind(s['o']) == 'hair' and not s['hull'] for s in surfs] + [False])
H = hair[np.where(mesh >= 0, mesh, len(surfs))]
comp = np.full(mesh.shape, -1, np.int64)
for j in np.unique(mesh[H]):
    c = comps_of(surfs[j]); sel = H & (mesh == j) & (ti >= 0)
    comp[sel] = j * 1000 + c[ti[sel]]
line = np.array([bool(s['hull']) for s in surfs] + [False])[np.where(mesh >= 0, mesh, len(surfs))]
base = np.array([0.93, 0.62, 0.48])
img = np.ones(mesh.shape + (3,)) * 0.97
t = np.nan_to_num(tone, nan=0)
img[H] = base * (1 - 0.25 * np.clip(t[H], 0, 2))[:, None]
img[line] = (0.15, 0.1, 0.1)
edge = (comp != np.roll(comp, 1, 0)) | (comp != np.roll(comp, 1, 1))
img[edge & H] = (0.1, 0.6, 0.2)
im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
dr = ImageDraw.Draw(im)
for k in np.unique(comp[comp >= 0]):
    m = comp == k
    if m.sum() < 60:
        continue
    r, c = ndimage.center_of_mass(m)
    dr.text((c - 10, r - 5), '%s#%d' % (surfs[k // 1000]['o'].name.replace('hair_', ''), k % 1000), fill=(0, 0, 160))
cr = opt('--crop')
if cr:
    r0, r1, c0, c1 = map(int, cr.split(','))
    im = im.crop((c0, r0, c1, r1))
im.save(a[1]); print(a[1], im.size)
