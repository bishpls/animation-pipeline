"""The motion test, geometry only (Michael, 2026-10-02: "ability to facilitate motion and detail in 'life'"; "careful on
the motion test" - so no rendering here, seconds per run).

Every hair piece (a clump id: a lock, a cut sheet) gets a spring chain along its length (K nodes from its vertices'
position along the piece, `sv`); the gathered section, underlayers, the core, the buns and the ahoge ride the head
rigidly. The head turns and nods (TURN deg yaw, NOD deg pitch, about a pivot in the neck) over DUR s at FPS; chains are
pinned at the root, pulled toward their rest shape (stiffness falling toward the tip: tips lag and flick), under
gravity, damped, length-constrained. Vertices follow their chain (linear along it).

Measures (max or mean over the clip):
  penetration   share of sampled hair vertices inside the head (its radial skin map) or the body (nearest skin vertex,
                signed by its normal), and the deepest (cm)
  silhouette    the front silhouette in head space against the rest pose: mean and min IoU (holds its shape: high,
                but not 1: it moves)
  amplitude     the tips' mean displacement relative to the head (cm): alive (not rigid) without flying apart
  lag_spread    the spread (frames) of when each chain's tip peaks: layered, out-of-phase motion (one block: ~0)
  stretch       the largest length-constraint error (%)

    python motion.py BUNDLE TAG     -> studio/TAG_motion.json
"""
import json, os, sys, time
import numpy as np
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'studio')
K, FPS, DUR, SUB = 8, 24, 2.5, 4
TURN, NOD = 35.0, 12.0
RIGID_IDS = {1999, 2998}                      # the gathered underlayer, the loose core
FREQ = {2: (3.0, 1.0), 4: (3.2, 1.2), 5: (3.2, 1.2), 6: (4.0, 1.6), 7: (2.5, 0.9)}   # group: (root Hz, tip Hz)


def rot(yaw, pitch):
    cy, sy = np.cos(np.radians(yaw)), np.sin(np.radians(yaw))
    cp, sp = np.cos(np.radians(pitch)), np.sin(np.radians(pitch))
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    return Rz @ Rx


def main(bdir, tag):
    t0 = time.time()
    A = np.load(os.path.join(bdir, 'arrays.npz'))
    M = json.load(open(os.path.join(bdir, 'bundle.json')))
    ez = M['assembly']['eye_z']
    C = np.array([0.0, 0.0185, ez + 0.025])
    pivot = np.array([0.0, 0.02, ez - 0.17])
    skin = A['o/clawd_skin/eval/V']
    # the head (rides the head) and the body (static): split at the neck
    head = skin[skin[:, 2] > ez - 0.13]
    body = skin[skin[:, 2] <= ez - 0.13]
    hd = (head - C) / np.linalg.norm(head - C, axis=1, keepdims=True)
    htree, hr = cKDTree(hd), np.linalg.norm(head - C, axis=1)
    # body normals (area-weighted vertex normals of the skin mesh)
    loopv, counts = A['o/clawd_skin/eval/loopv'], A['o/clawd_skin/eval/counts']
    starts = np.concatenate([[0], np.cumsum(counts)[:-1]])
    N = np.zeros_like(skin)
    tri = np.concatenate([np.stack([loopv[starts], loopv[starts + i], loopv[starts + i + 1]], 1)[counts > i + 1]
                          for i in range(1, counts.max() - 1)])
    fn = np.cross(skin[tri[:, 1]] - skin[tri[:, 0]], skin[tri[:, 2]] - skin[tri[:, 0]])
    for j in range(3):
        np.add.at(N, tri[:, j], fn)
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
    bmask = skin[:, 2] <= ez - 0.13
    btree, bN = cKDTree(skin[bmask]), N[bmask]

    # hair pieces -> chains
    names = [o['name'] for o in M['objects'] if o['group'] == 'hair']
    chains, verts, rigid_v = [], [], []
    for nm in names:
        V = A['o/%s/eval/V' % nm]
        cl = A.get('o/%s/eval/clump' % nm) if hasattr(A, 'get') else None
        k_ = 'o/%s/eval/clump' % nm
        if 'bun' in nm or 'ahoge' in nm or k_ not in A.files or ('o/%s/eval/sv' % nm) not in A.files:
            rigid_v.append(V); continue
        cl = A[k_]; sv = A['o/%s/eval/sv' % nm]
        lv, cn = A['o/%s/eval/loopv' % nm], A['o/%s/eval/counts' % nm]
        vcl = np.full(len(V), -1, np.int64)
        vcl[lv] = np.repeat(cl, cn)
        for c in np.unique(vcl):
            idx = np.where(vcl == c)[0]
            g = int(c) // 1000
            if c < 0 or c in RIGID_IDS or g == 1 or len(idx) < 12:
                rigid_v.append(V[idx]); continue
            s = np.clip(sv[idx], 0, 1)
            nodes = np.zeros((K, 3))
            for i in range(K):
                m = np.abs(s * (K - 1) - i) <= 0.6
                nodes[i] = V[idx][m].mean(0) if m.any() else np.nan
            ok = np.isfinite(nodes[:, 0])
            if ok.sum() < 3:
                rigid_v.append(V[idx]); continue
            for j in range(3):
                nodes[:, j] = np.interp(np.arange(K), np.where(ok)[0], nodes[ok, j])
            chains.append(dict(nodes=nodes, g=g))
            verts.append((V[idx], s, len(chains) - 1))
    nc = len(chains)
    R0 = np.stack([c['nodes'] for c in chains])                      # (nc, K, 3) rest
    L0 = np.linalg.norm(np.diff(R0, axis=1), axis=2)                  # rest lengths
    kk = np.stack([(2 * np.pi * np.linspace(*FREQ.get(c['g'], (3.0, 1.0)), K)) ** 2 for c in chains])[..., None]
    X, Xp = R0.copy(), R0.copy()
    nf = int(DUR * FPS)
    dt = 1.0 / FPS / SUB
    g_ = np.array([0, 0, -9.8])
    tips, frames_disp = [], []
    # sampled vertices for the measures
    rng = np.random.default_rng(0)
    samp = []
    for Vv, s, ci in verts:
        pick = rng.choice(len(Vv), size=min(len(Vv), 60), replace=False)
        samp.append((Vv[pick], s[pick], ci))
    pen_share, pen_depth, ious, stretch = [], [], [], []

    def head_xf(t):
        yaw = TURN * np.sin(2 * np.pi * t / DUR)
        pitch = NOD * np.sin(4 * np.pi * t / DUR)
        return rot(yaw, pitch)

    def sil(P):
        cells = np.floor((P[:, [0, 2]] - np.array([-0.25, ez - 0.4])) / 0.004).astype(int)
        m = np.zeros((125, 175), bool)
        ok = (cells[:, 0] >= 0) & (cells[:, 0] < 125) & (cells[:, 1] >= 0) & (cells[:, 1] < 175)
        m[cells[ok, 0], cells[ok, 1]] = True
        from scipy import ndimage
        return ndimage.binary_dilation(m, iterations=2)
    restS = None
    onion = []
    ONION = (0, 9, 18, 27, 36, 45)
    for f in range(nf):
        for sub in range(SUB):
            t = (f * SUB + sub) * dt
            R = head_xf(t)
            T = (R0 - pivot) @ R.T + pivot                           # rest shape carried by the head
            acc = kk * (T - X)                                       # (the rest shape already hangs: no extra gravity)
            Xn = X + (X - Xp) * 0.97 + acc * dt * dt
            Xn[:, 0] = T[:, 0]                                       # roots pinned
            for _ in range(12):                                      # length constraints
                d = Xn[:, 1:] - Xn[:, :-1]
                ln = np.linalg.norm(d, axis=2, keepdims=True)
                corr = (ln - L0[..., None]) / np.maximum(ln, 1e-9) * d
                Xn[:, 1:] -= corr * 0.5
                Xn[:, :-1] += corr * 0.5
                Xn[:, 0] = T[:, 0]
            Xp, X = X, Xn
        t = (f + 1) * SUB * dt
        R = head_xf(t)
        T = (R0 - pivot) @ R.T + pivot
        D = X - T                                                    # chain displacement relative to the head
        if f in ONION:
            onion.append((f, X.copy(), R.copy()))
        tips.append(np.linalg.norm(D[:, -1], axis=1))
        stretch.append(float(np.max(np.abs(np.linalg.norm(np.diff(X, axis=1), axis=2) / np.maximum(L0, 1e-9) - 1))))
        # sampled vertices in world space
        P_all = []
        for Vv, s, ci in samp:
            u = s * (K - 1); i0 = np.clip(np.floor(u).astype(int), 0, K - 2); fr = (u - i0)[:, None]
            disp = (1 - fr) * D[ci, i0] + fr * D[ci, i0 + 1]
            P_all.append((Vv - pivot) @ R.T + pivot + disp)
        P = np.concatenate(P_all)
        # penetration: the head (in head space, radial) and the body (static, nearest-normal)
        Ph = (P - pivot) @ R + pivot
        dh = Ph - C; rh = np.linalg.norm(dh, axis=1); uh = dh / rh[:, None]
        dd, ii = htree.query(uh, k=4)
        rs = hr[ii].max(1)
        inside_h = (rh < rs - 0.003) & (dd.max(1) < 0.04) & (Ph[:, 2] > ez - 0.05)   # (above the jaw)
        db, jb = btree.query(P)
        sd = np.sum((P - skin[bmask][jb]) * bN[jb], axis=1)
        inside_b = (sd < -0.003) & (db < 0.03)
        ins = inside_h | inside_b
        pen_share.append(float(ins.mean()))
        pen_depth.append(float(max((rs - rh)[inside_h].max() if inside_h.any() else 0, (-sd)[inside_b].max() if inside_b.any() else 0)))
        Sm = sil(Ph)
        if restS is None:
            restS = sil(np.concatenate([Vv for Vv, _, _ in samp]))
        ious.append(float((Sm & restS).sum() / max((Sm | restS).sum(), 1)))
    tips = np.array(tips)                                            # (nf, nc)
    peak = np.argmax(tips, axis=0)
    rep = dict(tag=tag, chains=nc, seconds=round(time.time() - t0, 1),
               penetration=dict(max_share=round(max(pen_share), 4), max_depth_cm=round(max(pen_depth) * 100, 2)),
               silhouette=dict(mean_iou=round(float(np.mean(ious)), 3), min_iou=round(float(np.min(ious)), 3)),
               amplitude_cm=round(float(tips.mean() * 100), 2), lag_spread=round(float(np.std(peak)), 2),
               stretch_pct=round(max(stretch) * 100, 2))
    json.dump(rep, open(os.path.join(OUT, tag + '_motion.json'), 'w'), indent=1)
    # the onion skin: the chains at a few frames, front (x, z) and side (y, z), world space; the head's skin outline grey
    from PIL import Image, ImageDraw
    W_, H_ = 900, 520
    im = Image.new('RGB', (W_, H_), (250, 250, 252)); dr = ImageDraw.Draw(im)
    cols = [(40, 40, 40), (220, 60, 60), (230, 150, 30), (60, 160, 80), (50, 110, 220), (150, 70, 200)]
    sc = 760
    def to(p, side):
        u = p[1] if side else p[0]
        return (W_ * (0.74 if side else 0.26) + (u - (C[1] if side else 0)) * sc, H_ * 0.42 - (p[2] - ez) * sc)
    for side in (0, 1):
        for pt in skin[skin[:, 2] > ez - 0.35][::25]:
            dr.point(to(pt, side), fill=(190, 190, 196))
        for ci_, (f, Xf, Rf) in enumerate(onion):
            for ch in Xf:
                dr.line([to(q, side) for q in ch], fill=cols[ci_ % len(cols)], width=1)
    dr.text((8, 6), '%s: chains at frames %s (black = rest; front left, side right)' % (tag, ', '.join(str(f) for f, _, _ in onion)), fill=(30, 30, 30))
    im.save(os.path.join(OUT, tag + '_onion.png'))
    print(json.dumps(rep))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
