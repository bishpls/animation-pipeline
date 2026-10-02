"""A single-shot groom of Clawd's hair from the coordinator's eyeballed construction plan (2026-10-02; Michael: "give
your construction process a shot, single-shot, not repeated iterations"). Rough plausibility test, not pipeline code.

Locks are grown, not carved: each is a tapered ribbon (lens cross-section) along a guide path in head-centred spherical
coordinates (theta from the top, alpha = atan2(x, y): 0 the back, +90 her left, 180 the front), placed at a height h
between the scalp (the skin's radial map) and the mass envelope (the hull hair's radial map: the overall outline is the
mass target). Groups: the crown cap with a scalloped back edge (hair_upper_back); the lower layer in two tiers of wavy
clumps with outward-flicking tips, plus the dark under-layer (hair_lower_back); two side locks a side; five bangs and two
thin accents; flyaways under the buns and at the temples. The buns, ahoge and clips are kept as built. Shading normals
lean on the envelope (65% the radial direction, 35% the lock's own) so the cel shadows follow the head, not the facets.

    python groom.py SRC_BUNDLE_DIR DST_BUNDLE_DIR
"""
import json, os, shutil, sys
import numpy as np

SRC, DST = sys.argv[1], sys.argv[2]
A = dict(np.load(os.path.join(SRC, 'arrays.npz')))
M = json.load(open(os.path.join(SRC, 'bundle.json')))
As = M['assembly']
EYE_Z = As['eye_z']
D2R = np.pi / 180

# ------------------------------------------------------------------------------------------------ the head frame
SKIN = next(o['name'] for o in M['objects'] if o['group'] == 'skin')
skin = A['o/%s/eval/V' % SKIN]
head = skin[(skin[:, 2] > EYE_Z - 0.03) & (np.abs(skin[:, 0]) < 0.13)]
C = np.array([0.0, (head[:, 1].min() + head[:, 1].max()) / 2, EYE_Z + 0.025])
print('centre', np.round(C, 4))


def sph(P):
    d = P - C
    r = np.linalg.norm(d, axis=1)
    th = np.arccos(np.clip(d[:, 2] / np.maximum(r, 1e-9), -1, 1)) / D2R
    al = np.arctan2(d[:, 0], d[:, 1]) / D2R
    return r, th, al


def dirv(th, al):
    th, al = th * D2R, al * D2R
    return np.stack([np.sin(th) * np.sin(al), np.sin(th) * np.cos(al), np.cos(th)], -1)


# radial maps on a (theta, alpha) grid: 2 deg x 3 deg
TH = np.arange(0, 181, 2.0)
AL = np.arange(-180, 180, 3.0)


def radial_map(P, smooth=2):
    r, th, al = sph(P)
    it = np.clip(np.round(th / 2).astype(int), 0, len(TH) - 1)
    ia = np.round((al + 180) / 3).astype(int) % len(AL)
    R = np.full((len(TH), len(AL)), np.nan)
    np.fmax.at(R, (it, ia), r)
    have = ~np.isnan(R)
    from scipy import ndimage
    # fill small holes (grid cells the sparse vertices missed): nearest of the dilated support. Alpha wraps: pad the
    # columns across the +-180 seam first (cycle 60's sections found the front centre line missing without it, and
    # the hair there sinking 2-4 cm into the forehead)
    pw = 8
    Hp = np.concatenate([have[:, -pw:], have, have[:, :pw]], 1)
    Rp = np.concatenate([R[:, -pw:], R, R[:, :pw]], 1)
    # (and across the pole: the rows above theta 0 are the rows below it seen from the opposite alpha; cycle 62 found
    # the crown's top cells missing and the hair there sinking up to 4 cm into the skull)
    half_ = len(AL) // 2
    top_h = np.roll(Hp[1:pw + 1][::-1], half_, axis=1)
    top_r = np.roll(Rp[1:pw + 1][::-1], half_, axis=1)
    Hp = np.concatenate([top_h, Hp], 0)
    Rp = np.concatenate([top_r, Rp], 0)
    sup = ndimage.binary_closing(Hp, iterations=2, structure=np.ones((3, 3)))[pw:, pw:-pw]
    idx = ndimage.distance_transform_edt(~Hp, return_distances=False, return_indices=True)
    F = Rp[idx[0], idx[1]][pw:, pw:-pw]
    F[~sup] = np.nan
    if smooth:
        G = np.where(np.isnan(F), 0, F)
        W = (~np.isnan(F)).astype(float)
        Gs = ndimage.gaussian_filter(G, smooth, mode=('nearest', 'wrap'))
        Ws = ndimage.gaussian_filter(W, smooth, mode=('nearest', 'wrap'))
        F = np.where(np.isnan(F), np.nan, Gs / np.maximum(Ws, 1e-6))
    return F


HULL = ['hair_bangs', 'hair_side_lock_L', 'hair_side_lock_R', 'hair_upper_back', 'hair_lower_back']
if all(('o/%s/eval/V' % n) in A and len(A['o/%s/eval/V' % n]) > 100 for n in HULL):
    hullV = np.concatenate([A['o/%s/eval/V' % n] for n in HULL])
    ENV = radial_map(hullV)
else:
    # no drawn-hull hair (a character groomed from scratch): a synthetic envelope, the scalp's radial map 2 cm out,
    # cut at the style's hem (theta per |alpha|: sys.argv[3]'s style 'hem_table')
    _st = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else {}
    _ht = _st.get('hem_table', [[0, 120], [180, 100]])
    ENV = radial_map(head) + 0.02
    for j_, a_ in enumerate(AL):
        cut_ = np.interp(abs(a_), *zip(*_ht))
        ENV[TH > cut_, j_] = np.nan
SCALP = radial_map(head, smooth=1)


def sample(Mp, th, al, fallback=None):
    th = np.clip(np.asarray(th, float), 0, 180)
    al = (np.asarray(al, float) + 180) % 360 - 180
    ft, fa = th / 2, (al + 180) / 3
    t0 = np.clip(np.floor(ft).astype(int), 0, len(TH) - 2)
    a0 = np.floor(fa).astype(int) % len(AL)
    a1 = (a0 + 1) % len(AL)
    wt, wa = ft - t0, fa - np.floor(fa)
    v = ((1 - wt) * (1 - wa) * Mp[t0, a0] + (1 - wt) * wa * Mp[t0, a1] + wt * (1 - wa) * Mp[t0 + 1, a0]
         + wt * wa * Mp[t0 + 1, a1])
    if fallback is not None:
        v = np.where(np.isnan(v), fallback, v)
    return v


def _carry(Mp):
    """each alpha column's empty cells filled from the nearest filled theta above (below the hem: the hem's radius),
    and above its first filled one from that one; a column with none from its neighbours."""
    F = Mp.copy()
    for j in range(F.shape[1]):
        col = F[:, j]
        ok = np.where(~np.isnan(col))[0]
        if len(ok) == 0:
            continue
        col[:ok[0]] = col[ok[0]]
        last = col[ok[0]]
        for i in range(ok[0], len(col)):
            if np.isnan(col[i]):
                col[i] = last
            else:
                last = col[i]
    for j in np.where(np.isnan(F).all(0))[0]:
        k = 1
        while np.isnan(F[:, (j + k) % F.shape[1]]).all() and np.isnan(F[:, (j - k) % F.shape[1]]).all():
            k += 1
        a, b = F[:, (j + k) % F.shape[1]], F[:, (j - k) % F.shape[1]]
        F[:, j] = np.where(np.isnan(a), b, a)
    return F


ENVF = _carry(ENV)


def env(th, al):
    """the envelope's radius (past the hull's hem or off its edge: carried from the nearest filled theta above)."""
    return sample(ENVF, th, al)


def inner(th, al):
    e = env(th, al)
    s = sample(SCALP, th, al)
    return np.where(np.isnan(s), 0.6 * e, np.minimum(s + 0.004, e - 0.004))


def hem(al):
    """the envelope's lowest theta per alpha (the hull's hem)."""
    ia = int(np.round((al + 180) / 3)) % len(AL)
    col = ~np.isnan(ENV[:, ia])
    return float(TH[np.where(col)[0].max()]) if col.any() else 120.0


def point(th, al, h):
    ri, re = inner(th, al), env(th, al)
    r = ri + h * (re - ri)
    return C + r[..., None] * dirv(th, al)


# ------------------------------------------------------------------------------------------------ geometry
class Mesh:
    def __init__(self):
        self.V, self.F = [], []
        self.n = 0

    def add(self, V, F):
        self.V.append(V)
        self.F += [[i + self.n for i in f] for f in F]
        self.n += len(V)

    def arrays(self):
        V = np.concatenate(self.V)
        counts = np.array([len(f) for f in self.F], np.int32)
        loopv = np.array([i for f in self.F for i in f], np.int32)
        # vertex normals (area-weighted, fan triangles), the envelope's radial lean for the render's normals
        N = np.zeros_like(V)
        for f in self.F:
            p = V[f]
            for k in range(1, len(f) - 1):
                c = np.cross(p[k] - p[0], p[k + 1] - p[0])
                N[f[0]] += c; N[f[k]] += c; N[f[k + 1]] += c
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
        R = V - C
        R /= np.maximum(np.linalg.norm(R, axis=1, keepdims=True), 1e-12)
        own = N[loopv]
        lean = 0.65 * R[loopv] + 0.35 * own
        lean *= np.sign(np.sum(lean * own, axis=1, keepdims=True) + 1e-9)     # never facing away from its face
        lean /= np.maximum(np.linalg.norm(lean, axis=1, keepdims=True), 1e-12)
        shrink = (-N * 0.0014).astype(np.float32)
        return dict(V=V, loopv=loopv, counts=counts, pmat=np.zeros(len(counts), np.int16), shrink=shrink,
                    lnor=lean.astype(np.float32))


def ribbon(m, P, width, thick, k=8, curl=0.3):
    """a tapered lock along centreline P (n, 3): a lens cross-section (width across, thick out from the head, its edges
    curled toward the head by curl x thick), the root capped, the tip a point."""
    n = len(P)
    T = np.gradient(P, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    Out = P - C
    Out -= np.sum(Out * T, axis=1, keepdims=True) * T
    Out /= np.maximum(np.linalg.norm(Out, axis=1, keepdims=True), 1e-12)
    Bn = np.cross(T, Out)
    u = np.linspace(0, 2 * np.pi, k, endpoint=False)
    rings = []
    for i in range(n - 1):
        cw, st = np.cos(u) * width[i] / 2, np.sin(u) * thick[i] / 2
        st = st - curl * thick[i] * np.cos(u) ** 2
        rings.append(P[i] + cw[:, None] * Bn[i] + st[:, None] * Out[i])
    V = np.concatenate(rings + [P[-1:]])
    F = [list(range(k))[::-1]]                                      # root cap
    for i in range(n - 2):
        for j in range(k):
            a, b = i * k + j, i * k + (j + 1) % k
            F.append([a, b, b + k, a + k])
    tip = len(V) - 1
    base = (n - 2) * k
    for j in range(k):
        F.append([base + j, base + (j + 1) % k, tip])
    m.add(V, F)


def taper(s, root, mid_at=0.35, tip_round=0.0):
    """a lock's width profile: root -> widest at mid_at (1.15 x root) -> a point."""
    w = np.where(s < mid_at, root * (1 + 0.15 * s / mid_at), root * 1.15 * (1 - (s - mid_at) / (1 - mid_at)) ** 0.8)
    return np.maximum(w, root * tip_round)


def lock(m, th0, th1, al0, al1, h0, h1, width, thick, n=30, wave=0.0, waves=1.0, sway=0.0, flick=0.0,
         flick_up=0.0, mid_at=0.35):
    s = np.linspace(0, 1, n)
    th = th0 + (th1 - th0) * s
    al = al0 + (al1 - al0) * s + sway * np.sin(2 * np.pi * waves * s)
    h = h0 + (h1 - h0) * s + wave * np.sin(np.pi * 2 * waves * s + 0.3) * np.clip(s * 3, 0, 1)
    fl = np.clip((s - 0.72) / 0.28, 0, 1) ** 1.6                  # the last 28% flicks out and up
    h = h + flick * fl
    th = th - flick_up * fl
    P = point(th, al, h)
    ribbon(m, P, taper(s, width, mid_at), np.maximum(taper(s, thick, mid_at), 0.0008))


def slab(m, th_lo, th_hi_fn, al_lo, al_hi, h_out, h_in, nt=26, na=72, wrap=False):
    """a closed shell over theta in [th_lo, th_hi_fn(alpha)], alpha in [al_lo, al_hi]: the outer sheet at h_out, the
    inner at h_in, their rims joined."""
    al = np.linspace(al_lo, al_hi, na, endpoint=not wrap)
    rows = []
    for a in al:
        t = np.linspace(th_lo, th_hi_fn(a), nt)
        rows.append(t)
    TT = np.array(rows).T                                           # (nt, na)
    AA = np.broadcast_to(al, TT.shape)
    O = point(TT, AA, np.full(TT.shape, h_out))
    I = point(TT, AA, np.full(TT.shape, h_in))
    V = np.concatenate([O.reshape(-1, 3), I.reshape(-1, 3)])
    off = nt * na
    F = []
    amax = na if wrap else na - 1
    for i in range(nt - 1):
        for j in range(amax):
            j2 = (j + 1) % na
            a, b, c, d = i * na + j, i * na + j2, (i + 1) * na + j2, (i + 1) * na + j
            F.append([a, b, c, d])
            F.append([off + d, off + c, off + b, off + a])
    for j in range(amax):                                           # the bottom rim (and the top, unless wrapped)
        j2 = (j + 1) % na
        a, b = (nt - 1) * na + j, (nt - 1) * na + j2
        F.append([a, off + a, off + b, b])
        if not wrap:
            pass
    if not wrap:                                                    # the side rims
        for i in range(nt - 1):
            for j in (0, na - 1):
                a, d = i * na + j, (i + 1) * na + j
                F.append([a, d, off + d, off + a] if j == 0 else [d, a, off + a, off + d])
    m.add(V, F)


# ------------------------------------------------------------------------------------------------ the groups
def cap_bottom(a):
    """the crown cap's lower edge: the front under the bangs' roots, the sides at the ear line, the back at jaw height
    with four scallops (the back view's lobes)."""
    a = (a + 180) % 360 - 180
    front = abs(a) / 180.0                                          # 0 back .. 1 front
    base = np.interp(front, [0, 0.5, 0.72, 0.82, 1.0], [116, 104, 96, 50, 42])
    sc = 7 * np.clip(np.cos(4 * a * D2R), 0, 1) if abs(a) < 95 else 0
    return float(base + sc)


out = {}

cap = Mesh()
slab(cap, 0.0, cap_bottom, -180, 180, 0.84, 0.70, nt=30, na=120, wrap=True)    # shot 1b: under the locks (plan's layer order)
out['hair_upper_back'] = cap

low = Mesh()
# tier B: long clumps to the hem, round the sides and back
for a in np.linspace(-138, 138, 11):
    t0 = cap_bottom(a) - 14
    t1 = hem(a) - 1
    lock(low, t0, t1, a, a + 4 * np.sign(a), 0.76, 0.96, width=0.052, thick=0.016, wave=0.07, waves=1.25,
         sway=3.0, flick=0.16, flick_up=7)
# tier A: shorter outer clumps flicking at mouth / chin height, staggered between B's
for a in np.linspace(-126, 126, 9):
    t0 = cap_bottom(a) - 16
    t1 = t0 + 0.62 * (hem(a) - t0)
    lock(low, t0, t1, a, a + 6 * np.sign(a), 0.78, 1.02, width=0.046, thick=0.014, wave=0.06, waves=1.0,
         sway=2.5, flick=0.22, flick_up=9)
# the under-layer: the dark inside of the back mass, behind the neck
slab(low, 100, lambda a: hem(a) - 8, -120, 120, 0.55, 0.42, nt=14, na=40)
out['hair_lower_back'] = low

for side, sg in (('L', 1), ('R', -1)):
    m = Mesh()
    # (alpha toward the front: her left side is +alpha, so the front-ish side locks sit at +/-(135..152))
    lock(m, 58, 120, sg * 152, sg * 140, 0.92, 1.0, width=0.034, thick=0.012, wave=0.05, waves=1.0, sway=3 * sg,
         flick=0.2, flick_up=8)
    lock(m, 64, 112, sg * 138, sg * 128, 0.9, 1.0, width=0.03, thick=0.011, wave=0.05, waves=0.9, sway=2 * sg,
         flick=0.18, flick_up=7)
    out['hair_side_lock_' + side] = m

bangs = Mesh()
# five bangs from a root arc behind the hairline over the forehead; the centre one longest (to between the eyes),
# a sweep to her right (-x: alpha past 180 toward -180 ... written as 180 + d, d > 0 her right)
for d, tip, w in ((-36, 86, 0.040), (-17, 92, 0.044), (2, 99, 0.042), (19, 93, 0.044), (37, 85, 0.040)):
    lock(bangs, 30, tip, 180 + d * 0.8, 180 + d * 1.05 + 5, 0.98, 0.32, width=w, thick=0.011, mid_at=0.3,
         wave=0.0, flick=0.0)
for d, tip in ((-8, 95), (12, 96)):                                 # two thin accent strands
    lock(bangs, 34, tip, 180 + d, 180 + d * 1.2 + 4, 1.0, 0.36, width=0.012, thick=0.006, mid_at=0.2)
out['hair_bangs'] = bangs

fly = Mesh()
for side, sg in (('L', 1), ('R', -1)):
    Bv = A['o/hair_bun_%s/eval/V' % side]
    base = np.array([Bv[:, 0].mean(), Bv[:, 1].mean(), Bv[:, 2].min() + 0.01])
    for i, (out_, down, fwd) in enumerate(((0.05, 0.05, -0.01), (0.035, 0.07, 0.01), (0.06, 0.035, 0.02))):
        s = np.linspace(0, 1, 16)[:, None]
        P = base + np.array([sg * out_, fwd, 0]) * s + np.array([0, 0, -down]) * s ** 1.3 \
            + np.array([sg * 0.012, 0, 0.01]) * np.sin(np.pi * s) ** 2 * s
        ribbon(fly, P, taper(s[:, 0], 0.008, 0.25), np.maximum(taper(s[:, 0], 0.004, 0.25), 0.0006))
    # the temple flyaway: a hooked strand off the side above the ear
    lock(fly, 66, 84, sg * 112, sg * 118, 1.0, 1.25, width=0.01, thick=0.004, flick=0.15, flick_up=6)
out['hair_flyaways'] = fly

# ------------------------------------------------------------------------------------------------ the bundle
os.makedirs(DST, exist_ok=True)
for f in os.listdir(SRC):
    if f not in ('arrays.npz', 'bundle.json'):
        s = os.path.join(SRC, f)
        if os.path.isdir(s):
            shutil.copytree(s, os.path.join(DST, f), dirs_exist_ok=True)
        else:
            shutil.copy(s, DST)
stats = {}
for name, m in out.items():
    for k in [k for k in A if k.startswith('o/%s/' % name)]:
        del A[k]
    g = m.arrays()
    for var in ('eval', 'raw'):
        for f, v in g.items():
            if var == 'raw' and f in ('shrink', 'lnor'):
                continue
            A['o/%s/%s/%s' % (name, var, f)] = v.astype(np.float32) if (var == 'raw' and f == 'V') else v
    stats[name] = dict(verts=int(len(g['V'])), polys=int(len(g['counts'])))
np.savez(os.path.join(DST, 'arrays.npz'), **A)
M['groom'] = dict(note='single-shot groom test, coordinator 2026-10-02', pieces=stats)
json.dump(M, open(os.path.join(DST, 'bundle.json'), 'w'))
print(json.dumps(stats))
