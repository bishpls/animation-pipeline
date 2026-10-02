"""lab (round 4, the back view's terminator): is the flicks' stepped terminator a normals problem? A pieces dir copied
with chosen pieces' locks given radial envelope normals: each vertex the hull build's outer hair surface normal along
the ray from the head's centre through it (the outermost of the hull's hair vertices nearest in direction, k of them,
their normals averaged by closeness), so a lock and the mass behind it shade alike at one screen place.
    python tools/hairshell3/radialnormals.py PIECES_IN HULL_PIECES OUT_DIR PIECE:LOCKS[,..] ... [--k 12] [--up 0.3]
        LOCKS: 'all', or lock ids a-b (e.g. lower_back:7-10)"""
import json, os, shutil, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import numpy as np
from scipy.spatial import cKDTree

a = sys.argv[1:]
opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
pin, phull, out = a[:3]
sel = [x for x in a[3:] if ':' in x]
k = int(opt('--k', 12)); up = float(opt('--up', 0.3))
from charkit import bundle
B = bundle.load(os.path.join(ROOT, 'charkit', 'out', 'hs_hull_r', 'bundle'))
L = float(B.assembly['L']); c = np.array(B.assembly['centre'], float) + np.array([0, 0, up * L])
Hv, Hn = [], []
for p in json.load(open(os.path.join(phull, 'pieces.json')))['pieces']:
    if p['name'] in ('ahoge', 'flyaways'):
        continue
    z = np.load(os.path.join(phull, p['file']))
    Hv.append(z['V']); Hn.append(z['vn'])
Hv, Hn = np.concatenate(Hv), np.concatenate(Hn)
d = Hv - c; r = np.linalg.norm(d, axis=1); u = d / r[:, None]
T = cKDTree(u)
if os.path.exists(out):
    shutil.rmtree(out)
shutil.copytree(pin, out)
for s in sel:
    name, locks = s.split(':')
    f = os.path.join(out, name + '.npz')
    z = dict(np.load(f))
    m = np.ones(len(z['V']), bool) if locks == 'all' else np.isin(z['lock'], np.arange(int(locks.split('-')[0]), int(locks.split('-')[-1]) + 1))
    q = z['V'][m] - c; uq = q / np.linalg.norm(q, axis=1)[:, None]
    dd, ii = T.query(uq, k=k)
    rr = r[ii]
    # the outer surface: the hull vertices in the cone within 0.01 L of the outermost
    w = (rr >= rr.max(1, keepdims=True) - 0.01 * L) * np.exp(-(dd / max(1e-9, np.median(dd))) ** 2)
    n = (Hn[ii] * w[..., None]).sum(1)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    z['vn'] = z['vn'].copy(); z['vn'][m] = n
    np.savez(f, **z)
    print(name, locks, int(m.sum()), 'vertices; mean turn %.1f deg' % np.degrees(np.arccos(np.clip(
        (np.load(os.path.join(pin, name + '.npz'))['vn'][m] * n).sum(1), -1, 1))).mean())
