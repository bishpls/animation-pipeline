"""The clip studio (Michael, 2026-10-02: "build out whatever tooling you need ... a local build and clip studio"): a short
motion clip of a groom, simulated and drawn on the laptop (numpy drawing at clip resolution: ~0.3 s a frame, no box,
no export), with measures that only exist in motion.

The move (MOVE): hold, a snappy 45 deg turn, hold (follow-through), a small hop, turn back, hold. The camera carries
the turn and the hop (the whole figure moves; equivalent for the hair, which the sim drives by the same head motion);
the hair deforms in head space by spring chains (motion.py's model: a chain per piece, pinned at the root, pulled
toward its rest shape, stiffness by frequency, root 3 Hz to tip 1 Hz).

Measures:
  flicker       the share of hair pixels whose tone (lit / shade / deep) flips between consecutive frames, counting only
                pixels that are hair in both (tone popping)
  settle_s      after the turn stops, the time for the tips' motion (relative to the head) to fall under 20% of its
                peak: follow-through (alive 0.3-0.8 s; floppy longer; stiff shorter)
  arc_jerk      the tips' paths' mean jerk (third difference, mm/frame^3) relative to the head: smooth arcs low
  overlap       the spread (frames) of the tips' peak times after the turn: layered motion

    python clip.py BUNDLE TAG [--views 0,30] [--ppl 160] [--ss 2]   -> clips/TAG.mp4, clips/TAG_clip.json
"""
import json, os, sys, time, subprocess
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
sys.path.insert(0, os.path.expanduser('~/animation-pipeline-3d'))
OUTD = os.path.join(HERE, 'clips')
os.makedirs(OUTD, exist_ok=True)
K, FPS, SUB = 8, 24, int(os.environ.get('CLIP_SUB', 4))
KB = 16
RIGID_IDS = {1999, 2998}
FREQ = {2: (3.0, 1.0), 4: (3.2, 1.2), 5: (3.2, 1.2), 6: (4.0, 1.6), 7: (2.5, 0.9)}


def ease(x):
    x = np.clip(x, 0, 1)
    if os.environ.get('CLIP_EASE', 'smoother') == 'smoother':        # C2: no acceleration jumps (no jolts)
        return x * x * x * (x * (6 * x - 15) + 10)
    return x * x * (3 - 2 * x)


def MOVE(t):
    """-> (yaw deg, hop m) at time t (s): 3.0 s."""
    yaw = 45 * ease((t - 0.5) / 0.35) - 45 * ease((t - 2.05) / 0.4)
    hop = 0.04 * np.sin(np.pi * np.clip((t - 1.43) / 0.34, 0, 1)) ** 2
    return yaw, hop


DUR = 3.0
TURN_END = 0.85


def rot_z(yaw):
    c, s = np.cos(np.radians(yaw)), np.sin(np.radians(yaw))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def build_rig(A, M):
    """chains by clump id ACROSS objects (Sonnet's braid and its bands share one chain), K nodes each from the vertices'
    position along the piece (sv); long pieces (the braid: id 7001) get KB nodes."""
    ez = M['assembly']['eye_z']
    C = np.array([0.0, 0.0185, ez + 0.025])
    pivot = np.array([0.0, 0.02, ez - 0.17])
    objs = [o['name'] for o in M['objects'] if o['group'] in ('hair', 'accessory')]
    pool = {}
    per = {}
    for nm in objs:
        kc, ks = 'o/%s/eval/clump' % nm, 'o/%s/eval/sv' % nm
        if 'bun' in nm or kc not in A.files or ks not in A.files:
            continue
        V = A['o/%s/eval/V' % nm]; cl = A[kc]; sv = np.clip(A[ks], 0, 1)
        lv, cn = A['o/%s/eval/loopv' % nm], A['o/%s/eval/counts' % nm]
        vcl = np.full(len(V), -1, np.int64)
        vcl[lv] = np.repeat(cl, cn)
        per[nm] = dict(vcl=vcl, sv=sv)
        for c in np.unique(vcl):
            if c < 0 or c in RIGID_IDS or int(c) // 1000 == 1 or (int(c) // 1000 == 6 and os.environ.get('CLIP_RIGID_BANGS') == '1'):
                continue
            idx = np.where(vcl == c)[0]
            pool.setdefault(int(c), []).append((V[idx], sv[idx]))
    global K
    if 7001 in pool or os.environ.get('CLIP_K'):
        K = int(os.environ.get('CLIP_K', KB))                                                       # (one node count for every chain)
    chains, cid_to_chain = [], {}
    for c, parts in pool.items():
        Vs = np.concatenate([p[0] for p in parts]); ss = np.concatenate([p[1] for p in parts])
        if len(Vs) < 12:
            continue
        Kc = K
        nodes = np.full((Kc, 3), np.nan)
        for i in range(Kc):
            m = np.abs(ss * (Kc - 1) - i) <= 0.6
            if m.any():
                nodes[i] = Vs[m].mean(0)
        ok = np.isfinite(nodes[:, 0])
        if ok.sum() < 3:
            continue
        for jx in range(3):
            nodes[:, jx] = np.interp(np.arange(Kc), np.where(ok)[0], nodes[ok, jx])
        if Kc != K:                                                  # resample to K nodes for the shared arrays
            pass
        cid_to_chain[c] = len(chains)
        chains.append(dict(nodes=nodes, g=c // 1000, K=Kc))
    per_obj = {}
    for nm, d in per.items():
        vchain = np.array([cid_to_chain.get(int(c), -1) for c in d['vcl']], np.int64)
        per_obj[nm] = dict(vchain=vchain, sv=d['sv'])
    return dict(C=C, pivot=pivot, chains=chains, per_obj=per_obj, ez=ez)


MODEL = os.environ.get('CLIP_MODEL', 'vrm')
TALL = os.environ.get('CLIP_TALL') == '1'
MOVE_NAME = os.environ.get('CLIP_MOVE', 'turn')


def MOVE_TOSS(t):
    """a hair toss: hold, a quick flick of the head (yaw 30 deg and back over 0.45 s), hold to watch the hair follow
    through -> (yaw, hop)."""
    yaw = 30 * np.sin(np.pi * np.clip((t - 0.4) / 0.45, 0, 1)) ** 2 * (t < 0.85) + 0.0
    return yaw, 0.0


def _rot_between(a, b, v):
    """v rotated by the minimal rotation taking unit a to unit b (row-wise)."""
    c = np.sum(a * b, -1, keepdims=True)
    ax = np.cross(a, b)
    return v * c + np.cross(ax, v) + ax * np.sum(ax * v, -1, keepdims=True) / np.maximum(1 + c, 1e-6)


COLLIDE = {}


def collider(A, M):
    """the body below the neck (static during these head moves): its vertices and vertex normals, a KD-tree."""
    from scipy.spatial import cKDTree
    ez = M['assembly']['eye_z']
    names = [o['name'] for o in M['objects'] if o['group'] == 'skin' or
             (o['group'] == 'garment' and not any(k in o['name'] for k in ('boot', 'cuff', 'wrist', 'sleeve')))]
    Ps, Ns = [], []
    for nm in names:
        if ('o/%s/eval/V' % nm) not in A.files:
            continue
        V = A['o/%s/eval/V' % nm]; lv, cn = A['o/%s/eval/loopv' % nm], A['o/%s/eval/counts' % nm]
        st = np.concatenate([[0], np.cumsum(cn)[:-1]])
        tri = np.concatenate([np.stack([lv[st], lv[st + i], lv[st + i + 1]], 1)[cn > i + 1] for i in range(1, cn.max() - 1)])
        fn = np.cross(V[tri[:, 1]] - V[tri[:, 0]], V[tri[:, 2]] - V[tri[:, 0]])
        N = np.zeros_like(V)
        for j in range(3):
            np.add.at(N, tri[:, j], fn)
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
        m = (V[:, 2] < ez - 0.16) if os.environ.get('CLIP_HEAD_COLLIDE') != '1' else np.ones(len(V), bool)
        Ps.append(V[m]); Ns.append(N[m])
    P_, N_ = np.concatenate(Ps), np.concatenate(Ns)
    COLLIDE.update(tree=cKDTree(P_), P=P_, N=N_)


def radial_collider(A, M):
    """a smooth body proxy: the max radius from the body's vertical axis per height (5 mm) and angle (5 deg) of the
    skin below the neck and the torso garments (arms excluded), closed and Gaussian-smoothed."""
    from scipy import ndimage as nd_
    ez = M['assembly']['eye_z']
    keep = ('top', 'bodice_panel', 'collar', 'bow', 'skirt', 'waistband', 'overskirt_panel_R', 'overskirt_panel_L', 'shorts')
    pts = []
    for o in M['objects']:
        if o['group'] == 'skin' or o['name'] in keep:
            k = 'o/%s/eval/V' % o['name']
            if k in A.files:
                V = A[k]; pts.append(V[V[:, 2] < ez - 0.12])
    P = np.concatenate(pts)
    lim = np.where(P[:, 2] > 1.07, 0.19, 0.15)
    P = P[np.abs(P[:, 0]) < lim]
    yc = 0.012
    ZB = np.arange(0.6, ez - 0.1, 0.005); AL_ = np.arange(-180, 180, 5.0)
    r = np.hypot(P[:, 0], P[:, 1] - yc); a = np.degrees(np.arctan2(P[:, 0], P[:, 1] - yc))
    iz = np.clip(((P[:, 2] - ZB[0]) / 0.005).astype(int), 0, len(ZB) - 1); ia = ((a + 180) / 5).astype(int) % len(AL_)
    RB = np.zeros((len(ZB), len(AL_))); np.maximum.at(RB, (iz, ia), r)
    RB = nd_.grey_closing(RB, size=(3, 3)); RB = nd_.gaussian_filter(RB, (2.0, 1.2), mode=('nearest', 'wrap'))
    COLLIDE.update(radial=dict(RB=RB, z0=ZB[0], n=len(ZB), yc=yc, zmax=ZB[-1]))


def collide_radial(X, r=0.015):
    R_ = COLLIDE['radial']
    P = X[:, 1:].reshape(-1, 3)
    z = P[:, 2]
    ok = (z > R_['z0']) & (z < R_['zmax'])
    i = np.clip((z - R_['z0']) / 0.005, 0, R_['n'] - 1.001)
    a = np.degrees(np.arctan2(P[:, 0], P[:, 1] - R_['yc']))
    j = ((a + 180) / 5) % 72
    i0, j0 = np.floor(i).astype(int), np.floor(j).astype(int) % 72
    j1 = (j0 + 1) % 72; fi, fj = i - np.floor(i), j - np.floor(j)
    RB = R_['RB']
    i1 = np.minimum(i0 + 1, R_['n'] - 1)
    rb = (1 - fi) * (1 - fj) * RB[i0, j0] + (1 - fi) * fj * RB[i0, j1] + fi * (1 - fj) * RB[i1, j0] + fi * fj * RB[i1, j1]
    rr = np.hypot(P[:, 0], P[:, 1] - R_['yc'])
    m = ok & (rr < rb + r) & (rb > 0.01)
    if m.any():
        sc = (rb[m] + r) / np.maximum(rr[m], 1e-9)
        P[m, 0] *= sc; P[m, 1] = R_['yc'] + (P[m, 1] - R_['yc']) * sc
    X[:, 1:] = P.reshape(X[:, 1:].shape)
    return X


def collide(X, r=0.02, R=None, pv=None, off=None):
    if os.environ.get('CLIP_NOCOLLIDE') == '1':
        return X
    """push chain nodes out of the body: in the body's frame (the figure turns with the move: R about pv, offset off)."""
    if not COLLIDE:
        return X
    if R is not None:
        Xb = X.copy()
        Xb[:, 1:] = (X[:, 1:] - pv - off) @ R + pv
        Xb = collide(Xb, r)
        X = X.copy()
        X[:, 1:] = (Xb[:, 1:] - pv) @ R.T + pv + off
        return X
    if 'radial' in COLLIDE and os.environ.get('CLIP_COLLIDER', 'radial') == 'radial':
        X = collide_radial(X)
        if os.environ.get('CLIP_HEAD_COLLIDE') != '1':
            return X
        # (the head stays a mesh collider: only nodes above the neck)
        hm = X[:, 1:, 2] > COLLIDE['radial']['zmax']
        if not hm.any():
            return X
    flat = X[:, 1:].reshape(-1, 3)
    d, j = COLLIDE['tree'].query(flat)
    p, n = COLLIDE['P'][j], COLLIDE['N'][j]
    sd = np.sum((flat - p) * n, 1)
    push = (sd < r) & (d < 0.08)
    flat[push] += n[push] * (r - sd[push])[:, None]
    X[:, 1:] = flat.reshape(X[:, 1:].shape)
    return X


def simulate_vrm(rig, nf, move):
    """VRM spring-bone chains (each segment pulled toward its parent segment's current direction, so motion travels
    from the root to the tip: successive breaking of joints): per substep, root to tip, nextTail = tail + inertia
    (1 - drag) + dt x stiffness x (the parent's rotation applied to the rest direction), then held at its length from
    the (already updated) previous node. Stiffness falls from root to tip."""
    R0 = np.stack([c['nodes'] for c in rig['chains']])              # (nc, K, 3)
    nc = len(R0)
    L0 = np.linalg.norm(np.diff(R0, axis=1), axis=2)
    d0 = np.diff(R0, axis=1) / np.maximum(L0[..., None], 1e-9)       # rest directions (nc, K-1, 3)
    # per chain and segment: stiffness by group (bangs and framing held, the braid soft), and how much each segment's
    # rest direction is carried by the head (short held pieces: all; the braid: its first 15%, then the world's down)
    G = np.array([c['g'] for c in rig['chains']])
    LONG = np.array([np.linalg.norm(np.diff(c['nodes'], axis=0), axis=1).sum() > 0.2 for c in rig['chains']])
    sk = np.linspace(0, 1, K - 1)
    stiff = np.stack([np.linspace(*(STIFF_LONG if lg else STIFF_G.get(int(g), (STIFF_ROOT, STIFF_TIP))), K - 1)
                      for g, lg in zip(G, LONG)])                                                          # (nc, K-1)
    STYLED = os.environ.get('CLIP_STYLED') == '1'
    carry = np.stack([np.clip(1 - sk / 0.2, 0, 1) if ((g == 7 or lg) and not STYLED) else np.ones(K - 1)
                      for g, lg in zip(G, LONG)])
    sn = np.linspace(0, 1, K)
    hold = np.stack([((STY_HOLD if STYLED else 0.0) if lg else HOLD_G.get(int(g), 0.0)) * (1 - 0.75 * sn) for g, lg in zip(G, LONG)])[..., None]
    hold[:, 0] = 0
    grav = np.where(LONG, GRAV_LONG, GRAVITY)[:, None]
    pv = rig['pivot']
    X, Xp = R0.copy(), R0.copy()
    dt = 1.0 / FPS / SUB
    out = []
    nw = int(WARMUP * FPS)
    for f in range(-nw, nf):
        for sub in range(SUB):
            t = max((f * SUB + sub) * dt, 0.0)
            yaw, hop = move(t)
            R = rot_z(yaw)
            off = np.array([0, 0, hop])
            root = (R0[:, 0] - pv) @ R.T + pv + off
            Xn = X.copy()
            Xn[:, 0] = root
            for k in range(1, K):
                w_ = carry[:, k - 1:k]
                rest_dir = w_ * (d0[:, k - 1] @ R.T) + (1 - w_) * d0[:, k - 1]   # head-carried near the root, world below
                rest_dir /= np.maximum(np.linalg.norm(rest_dir, axis=1, keepdims=True), 1e-9)
                if k >= 2:
                    w2 = carry[:, k - 2:k - 1]
                    par_rest = w2 * (d0[:, k - 2] @ R.T) + (1 - w2) * d0[:, k - 2]
                    par_rest /= np.maximum(np.linalg.norm(par_rest, axis=1, keepdims=True), 1e-9)
                    par_now = Xn[:, k - 1] - Xn[:, k - 2]
                    par_now /= np.maximum(np.linalg.norm(par_now, axis=1, keepdims=True), 1e-9)
                    target = _rot_between(par_rest, par_now, rest_dir)
                else:
                    target = rest_dir
                tail = X[:, k] + (X[:, k] - Xp[:, k]) * (1 - DRAG) + target * (stiff[:, k - 1:k] * dt * L0[:, k - 1, None]) \
                    + np.array([0, 0, -1.0]) * (grav * dt)
                v = tail - Xn[:, k - 1]
                Xn[:, k] = Xn[:, k - 1] + v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9) * L0[:, k - 1, None]
            # hold: styled pieces pulled back toward their head-carried shape each substep (stronger at the root)
            Th = (R0 - pv) @ R.T + pv + off
            Xn = Xn + hold * (Th - Xn)
            Xc = collide(Xn, R=R, pv=pv, off=off)
            push = Xc - Xn
            Xp_new = X + push * INELASTIC
            if FRICTION:                                         # nodes in contact lose that much of their velocity
                contact = (np.linalg.norm(push, axis=2) > 1e-7)[..., None]
                Xp_new = np.where(contact, Xc - (Xc - Xp_new) * (1 - FRICTION), Xp_new)
            Xp, X = Xp_new, Xc
        if f < 0:
            continue
        t = (f + 1) * SUB * dt
        yaw, hop = move(t)
        R = rot_z(yaw)
        T = (R0 - pv) @ R.T + pv + np.array([0, 0, hop])
        out.append((t, yaw, hop, (X - T) @ R))
    return out


WARMUP = float(os.environ.get('CLIP_WARMUP', 1.5))
INELASTIC = float(os.environ.get('CLIP_INELASTIC', 1.0))
STY_HOLD = float(os.environ.get('CLIP_STY_HOLD', 0.03))
FRICTION = float(os.environ.get('CLIP_FRICTION', 0.3))
HOLD_G = {8: 0.03, 6: 0.12, 4: 0.08, 5: 0.08, 2: 0.04}


STIFF_LONG = tuple(float(x) for x in os.environ.get('CLIP_STIFF_LONG', '30,8').split(','))
GRAV_LONG = float(os.environ.get('CLIP_GRAV_LONG', 0.25))
STIFF_G = {8: (60.0, 18.0), 6: (90.0, 30.0), 4: (70.0, 22.0), 5: (70.0, 22.0), 2: (40.0, 12.0), 7: (14.0, 4.0)}
STIFF_ROOT, STIFF_TIP, DRAG, GRAVITY = float(os.environ.get('CLIP_SR', 14)), float(os.environ.get('CLIP_ST', 4)), float(os.environ.get('CLIP_DRAG', 0.5)), 0.0


def simulate(rig, nf):
    move = MOVE_TOSS if MOVE_NAME == 'toss' else MOVE
    if MODEL == 'vrm':
        return simulate_vrm(rig, nf, move)
    return simulate_springs(rig, nf, move)


def simulate_springs(rig, nf, move=None):
    move = move or MOVE
    """-> per frame: (yaw, hop, D) with D (nc, K, 3) the chains' displacement from the head-carried rest, in head space."""
    R0 = np.stack([c['nodes'] for c in rig['chains']])
    L0 = np.linalg.norm(np.diff(R0, axis=1), axis=2)
    kk = np.stack([(2 * np.pi * np.linspace(*FREQ.get(c['g'], (3.0, 1.0)), K)) ** 2 for c in rig['chains']])[..., None]
    pv = rig['pivot']
    X, Xp = R0.copy(), R0.copy()
    dt = 1.0 / FPS / SUB
    out = []
    for f in range(nf):
        for sub in range(SUB):
            t = (f * SUB + sub) * dt
            yaw, hop = move(t)
            R = rot_z(yaw)
            T = (R0 - pv) @ R.T + pv + np.array([0, 0, hop])
            Xn = X + (X - Xp) * 0.97 + kk * (T - X) * dt * dt
            Xn[:, 0] = T[:, 0]
            for _ in range(12):
                d = Xn[:, 1:] - Xn[:, :-1]
                ln = np.linalg.norm(d, axis=2, keepdims=True)
                corr = (ln - L0[..., None]) / np.maximum(ln, 1e-9) * d
                Xn[:, 1:] -= corr * 0.5; Xn[:, :-1] += corr * 0.5
                Xn[:, 0] = T[:, 0]
            Xn = collide(Xn, R=R, pv=pv, off=np.array([0, 0, hop]))
            Xp, X = X, Xn
        t = (f + 1) * SUB * dt
        yaw, hop = move(t)
        R = rot_z(yaw)
        T = (R0 - pv) @ R.T + pv + np.array([0, 0, hop])
        out.append((t, yaw, hop, (X - T) @ R))                      # head space
    return out


def main(bdir, tag, views=(0.0, 30.0), ppl=160, ss=2):
    from charkit import bundle as bl, palette, qa3d
    from charkit.detailqa import _Window
    from PIL import Image, ImageDraw
    t0 = time.time()
    B = bl.load(bdir); palette.activate_spec(B.spec)
    A = np.load(os.path.join(bdir, 'arrays.npz'))
    M = json.load(open(os.path.join(bdir, 'bundle.json')))
    rig = build_rig(A, M)
    collider(A, M)
    radial_collider(A, M)
    nf = int(DUR * FPS)
    sim = simulate(rig, nf)
    t_sim = time.time() - t0
    if os.environ.get('CLIP_SIM_ONLY') == '1':
        allD = np.array([d for (_, _, _, d) in sim]); mv0 = int(0.4 * FPS)
        segD = np.linalg.norm(allD[mv0:mv0 + FPS], axis=3)
        pk = np.argmax(segD >= 0.5 * np.maximum(segD.max(0, keepdims=True), 1e-9), axis=0).astype(float)   # onset
        slopes = [np.polyfit(np.arange(1, K), pk[c, 1:], 1)[0] for c in range(pk.shape[0]) if segD[:, c, -1].max() > 1e-4]
        whip = segD[:, :, -1].max(0) / np.maximum(segD[:, :, K // 2].max(0), 1e-6)
        print(json.dumps(dict(model=MODEL, move=MOVE_NAME, sim_s=round(t_sim, 2),
                              propagation_frames_per_node=round(float(np.median(slopes)), 3),
                              whip_ratio=round(float(np.median(whip)), 2),
                              tip_peak_cm=round(float(segD[:, :, -1].max(0).mean() * 100), 2),
                              arc_jerk=round(float(np.abs(np.diff(allD[:, :, -1], 3, axis=0)).mean() * 1000), 3),
                              chains=len(rig['chains']), K=K)))
        return
    L = float(B.assembly['L'])
    groups = ('hair', 'skin', 'eye', 'mouth', 'garment', 'accessory')
    base = []
    for o in B.objects():
        if o.group not in groups:
            continue
        variant = 'masked' if o.group == 'skin' and o.has('masked') else 'eval'
        if o.has(variant):
            for s_ in qa3d.surfaces(B, o, variant):
                base.append((o.name, s_, s_['V'].copy()))
    frames_dir = os.path.join(OUTD, tag + '_frames')
    os.makedirs(frames_dir, exist_ok=True)
    tones, tipD = [], []
    for f, (t, yaw, hop, D) in enumerate(sim):
        surfs = []
        for nm, s_, V0 in base:
            po = rig['per_obj'].get(nm)
            if po is not None and len(V0) == len(po['vchain']):
                vc, sv = po['vchain'], po['sv']
                m = vc >= 0
                u = sv[m] * (K - 1); i0 = np.clip(np.floor(u).astype(int), 0, K - 2); fr = (u - i0)[:, None]
                Vn = V0.copy()
                Vn[m] = V0[m] + (1 - fr) * D[vc[m], i0] + fr * D[vc[m], i0 + 1]
                s_ = dict(s_, V=Vn)
            surfs.append(s_)
        tiles = []
        for vi, az in enumerate(views):
            c = np.array(B.assembly['centre'], float)
            if TALL:
                c[2] = float(B.assembly['eye_z']) - 1.0 * L - hop
                fr_ = _Window(c, az - yaw, 1.0 * L, 2.2 * L, L / 100.0 / ss)
            else:
                c[2] = float(B.assembly['eye_z']) + 0.1 * L - hop
                fr_ = _Window(c, az - yaw, 1.0 * L, 1.1 * L, L / ppl / ss)
            aux = {}
            img = qa3d.draw(B, surfs, az - yaw, fr_, transparent=False, ss=ss, aux=aux)
            tiles.append((np.clip(img[..., :3], 0, 1) * 255).astype(np.uint8))
            if vi == 0:
                tone = aux.get('tone')
                tones.append(np.nan_to_num(tone, nan=-1).round().astype(np.int8) if tone is not None else None)
        frame = np.concatenate(tiles, 1)
        im = Image.fromarray(frame)
        ImageDraw.Draw(im).text((6, 4), '%s  %.2fs' % (tag, t), fill=(40, 40, 40))
        im.save(os.path.join(frames_dir, '%04d.png' % f))
        tipD.append(D[:, -1].copy())
    t_draw = time.time() - t0 - t_sim
    mp4 = os.path.join(OUTD, tag + '.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i', os.path.join(frames_dir, '%04d.png'),
                    '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', mp4],
                   check=True)
    # measures
    fl = []
    for a, b in zip(tones[:-1], tones[1:]):
        if a is None or b is None:
            continue
        both = (a >= 0) & (b >= 0)
        if both.any():
            fl.append(float(((a != b) & both).sum() / both.sum()))
    tipD = np.array(tipD)                                           # (nf, nc, 3)
    mag = np.linalg.norm(tipD, axis=2)
    after = [i for i, (t, *_ ) in enumerate(sim) if t >= TURN_END]
    i0 = after[0]
    seg = mag[i0:i0 + int(0.55 * FPS)]                           # (before the hop at 1.43 s)
    peak = seg.max(0)
    settle = []
    for c in range(seg.shape[1]):
        above = np.where(seg[:, c] > 0.2 * max(peak[c], 1e-6))[0]
        settle.append((above.max() + 1) / FPS if len(above) else 0.0)
    jerk = np.abs(np.diff(tipD, 3, axis=0)).mean() * 1000
    # propagation: for each chain, the frame each node's displacement (head space) peaks in the second after the move
    # starts; the slope of peak frame against node index (frames per node: root first, tip last = positive)
    allD = np.array([d for (_, _, _, d) in sim])                     # (nf, nc, K, 3)
    mv0 = int(0.4 * FPS)
    segD = np.linalg.norm(allD[mv0:mv0 + FPS], axis=3)               # (F, nc, K)
    pk = np.argmax(segD >= 0.5 * np.maximum(segD.max(0, keepdims=True), 1e-9), axis=0).astype(float)   # onset frame
    ks = np.arange(1, K)
    slopes = [np.polyfit(ks, pk[c, 1:], 1)[0] for c in range(pk.shape[0]) if segD[:, c, -1].max() > 1e-4]
    whip = segD[:, :, -1].max(0) / np.maximum(segD[:, :, K // 2].max(0), 1e-6)
    rep = dict(tag=tag, frames=nf, seconds=dict(sim=round(t_sim, 1), draw=round(t_draw, 1)),
               flicker=round(float(np.mean(fl)), 4) if fl else None, flicker_max=round(float(np.max(fl)), 4) if fl else None,
               settle_s=round(float(np.median(settle)), 2), arc_jerk=round(float(jerk), 3),
               overlap=round(float(np.std(np.argmax(seg, axis=0))), 2), model=MODEL, move=MOVE_NAME,
               propagation_frames_per_node=round(float(np.median(slopes)), 3) if slopes else None,
               whip_ratio=round(float(np.median(whip)), 2), mp4=mp4)
    json.dump(rep, open(os.path.join(OUTD, tag + '_clip.json'), 'w'), indent=1)
    print(json.dumps(rep))


if __name__ == '__main__':
    a = sys.argv[1:]
    opt = lambda k, d: a[a.index(k) + 1] if k in a else d
    main(a[0], a[1], views=tuple(float(x) for x in opt('--views', '0,30').split(',')), ppl=int(opt('--ppl', 160)),
         ss=int(opt('--ss', 2)))
