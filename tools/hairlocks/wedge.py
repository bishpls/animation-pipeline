"""The ceiling of the builder's lock model: the bangs piece's surface re-cut into K wedges on the crown chart (phi
cuts, straight meridians as hairpieces.locks makes them; or sheared, each cut phi = a + b (theta - 60)), the cuts placed
to fit the lock truth in front, three-quarter and profile at once (coordinate descent on the mean lock IoU). If even
the best cuts stay far from the truth, the wedge model is the limit, not where its notches fall.

    python tools/hairlocks/wedge.py BUILD OUT.json [--k 4,5,6] [--shear]
"""
import json, os, re, sys, tempfile
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctx as cx, score as sc
from charkit import hairlocks as hk


def setup(build):
    from charkit import bundle as bl, qa3d, bodyqa
    from charkit.geom import hairpieces as hp, parts
    B = bl.load(os.path.join(build, 'bundle'))
    D = qa3d.Design(B)
    txt = open(os.path.join(build, 'geom', 'pieces.spec.json')).read()
    txt = re.sub(r'/srv/work/[^/"]+/', ROOT + '/', txt)
    cut = os.path.join(tempfile.mkdtemp(prefix='wedge-'), 'pieces.spec.json')
    open(cut, 'w').write(txt)
    case = parts.Case.load(cut, fit=False)
    Hd = case.A['head']
    c = case.centre + np.array([0.0, (Hd['H'].db - Hd['H'].df) / 2, 0.06 * case.L])
    ch = hp.Chart(c, hp.OPTS['crown_tilt'])
    pdir = os.path.join(build, 'geom', 'hair_pieces')
    P = json.load(open(os.path.join(pdir, 'pieces.json')))
    Z = np.load(os.path.join(pdir, 'bangs.npz'))
    V, F = Z['V'], Z['F']
    ph, th, _ = ch.coords(V[F].mean(1))
    other = []
    for pc in P['pieces']:
        if pc['name'] != 'bangs':
            Zo = np.load(os.path.join(pdir, pc['file']))
            other.append((Zo['V'], Zo['F']))
    # the scene with each bangs triangle its own code (100 + index)
    sc_ = D.sheet_context()
    As = B.assembly
    meshes = []
    Vs, Ts = B.skin().mesh('masked')[:2]
    meshes.append((Vs, Ts, np.zeros(len(Ts), int)))
    for o in B.objects(groups=('eye', 'mouth', 'accessory', 'garment')):
        if o.has('eval'):
            V2, T2 = o.mesh('eval')[:2]
            meshes.append((V2, T2, np.zeros(len(T2), int)))
    for V2, T2 in other:
        meshes.append((V2, T2, np.full(len(T2), 99)))
    meshes.append((V, F, 100 + np.arange(len(F))))
    lab = bodyqa.zbuffer_views(meshes, sc_['az3'], np.array(qa3d.iris_centres(B)), As['centre'], As['L'], sc_['ppl'],
                               ['front', 'three_quarter', 'profile'])
    tri = {v: np.where(l[1] >= 100, l[1] - 100, -1) for v, l in lab.items()}
    return dict(ph=ph, th=th, tri=tri, lock=np.load(os.path.join(pdir, 'bangs.npz'))['lock'][F[:, 0]])


def partition(S, cuts, shear=None, th0=60.0):
    """cuts (sorted phi) and per cut a shear b (deg phi per deg theta) -> {view: image 1..K, 0 none}."""
    out = {}
    for v, t in S['tri'].items():
        img = np.zeros(t.shape, np.int32)
        m = t >= 0
        p, q = S['ph'][t[m]], S['th'][t[m]]
        k = np.zeros(len(p), np.int32)
        for i, a in enumerate(cuts):
            b = 0.0 if shear is None else shear[i]
            k += (p > a + b * (q - th0)).astype(np.int32)
        img[m] = k + 1
        out[v] = img
    return out


def evaluate(S, T, hair, ppl, cuts, shear=None):
    r = hk.score(partition(S, cuts, shear), T, hair, ppl, views=('front', 'three_quarter', 'profile'))
    return r['all']['lock_iou'], r


def descend(S, T, hair, ppl, cuts, shear=None, span=(24, 8, 3, 1), sspan=(0.4, 0.15, 0.05)):
    cuts = list(cuts); shear = None if shear is None else list(shear)
    best, _ = evaluate(S, T, hair, ppl, cuts, shear)
    for step in span:
        improved = True
        while improved:
            improved = False
            for i in range(len(cuts)):
                for d in (-step, step):
                    c2 = cuts.copy(); c2[i] += d
                    if (i > 0 and c2[i] <= c2[i - 1]) or (i < len(cuts) - 1 and c2[i] >= c2[i + 1]):
                        continue
                    s, _ = evaluate(S, T, hair, ppl, c2, shear)
                    if s > best + 1e-4:
                        best, cuts, improved = s, c2, True
            if shear is not None:
                for ss in sspan:
                    for i in range(len(shear)):
                        for d in (-ss, ss):
                            s2 = shear.copy(); s2[i] += d
                            s, _ = evaluate(S, T, hair, ppl, cuts, s2)
                            if s > best + 1e-4:
                                best, shear, improved = s, s2, True
    return best, cuts, shear


if __name__ == '__main__':
    a = sys.argv[1:]
    build, out = a[0], a[1]
    ks = [int(q) for q in a[a.index('--k') + 1].split(',')] if '--k' in a else [4, 5, 6]
    C = cx.make()
    T = hk.load_truth('charkit/refs/clawd/hair_locks_truth.npz')
    hair = sc.fillable(C)
    ppl = T[2]['ppl']
    S = setup(build)
    res = {}
    # the builder's own partition, through this path (checks the path: it must read as tools/hairlocks/score.py does)
    own = {}
    for v, t in S['tri'].items():
        img = np.zeros(t.shape, np.int32); m = t >= 0
        img[m] = S['lock'][t[m]] + 1
        own[v] = img
    r = hk.score(own, T, hair, ppl, views=('front', 'three_quarter', 'profile'))
    res['builder'] = dict(lock_iou=r['all']['lock_iou'], views={v: r[v]['lock_iou'] for v in r if v != 'all'})
    print('builder (bangs only)', res['builder'])
    lo, hi = np.percentile(S['ph'], [1, 99])
    # the builder's own cuts: between consecutive locks' phi ranges (its triangles' centroids)
    own_cuts = []
    for k in range(int(S['lock'].max())):
        pa = np.percentile(S['ph'][S['lock'] == k], 95); pb = np.percentile(S['ph'][S['lock'] == k + 1], 5)
        own_cuts.append(float((pa + pb) / 2))
    res['builder']['cuts'] = [round(c, 1) for c in own_cuts]
    starts = {}
    for k in ks:
        starts[k] = list(np.linspace(lo, hi, k + 1)[1:-1])
    if '--own' in a:
        starts = {len(own_cuts) + 1: own_cuts}
    for k, c0 in starts.items():
        best, cuts, _ = descend(S, T, hair, ppl, c0)
        _, r = evaluate(S, T, hair, ppl, cuts)
        res['wedge_%d' % k] = dict(lock_iou=best, lock_iou_in=r['all']['lock_iou_in'], cuts=[round(c, 1) for c in cuts],
                                   views={v: r[v]['lock_iou'] for v in r if v != 'all'})
        print('wedges k=%d' % k, res['wedge_%d' % k])
        if '--shear' in a:
            best, cuts2, sh = descend(S, T, hair, ppl, cuts, [0.0] * len(cuts))
            _, r = evaluate(S, T, hair, ppl, cuts2, sh)
            res['shear_%d' % k] = dict(lock_iou=best, lock_iou_in=r['all']['lock_iou_in'],
                                       cuts=[round(c, 1) for c in cuts2], shear=[round(s, 2) for s in sh],
                                       views={v: r[v]['lock_iou'] for v in r if v != 'all'})
            print('sheared k=%d' % k, res['shear_%d' % k])
    json.dump(res, open(out, 'w'), indent=1)
