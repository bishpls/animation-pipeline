"""A mocap clip on the styled hair (Michael, 2026-10-02: "rig up a motion clip using one of the mocap data segments ...
use the curtsy as the first test"). Numpy, laptop:

  retarget  a canonical clip (projects/clawd3d/refs/mocap/NAME.clip.npz: SOMA 77, local quaternions, a metric root,
            Y up facing +Z) onto the build's VRM humanoid (charkit.rom.Rig from the export), by the clawd3d method
            (projects/clawd3d/build/motion.py): each mapped bone's world deformation is the source joint's world rotation
            times the calibration that turns the target's rest direction onto the source's rest direction
            (soma_map.BONE_MAP); heads carried down the target hierarchy; the root at the source root's displacement,
            scaled by the hips' height ratio
  skin      the bundle's objects (the styled groom's bundle: its materials draw) by weights transferred from the export's
            nearest rest vertex (linear blend skinning); the groom's hair rides the head bone, its spring chains
            simulated in the head's frame (clip.py's VRM model, styled mode) with the body proxy carried by the chest
  draw      the QA's toon drawing per frame (two views), ffmpeg -> clips/TAG.mp4

    python mocap.py BUILD_DIR GROOM_BUNDLE CLIP.npz TAG [--views 20,200] [--ppl 110] [--trim N] [--face] [--measure-only]
"""
import json, os, sys, time, subprocess
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, '..', '..')); sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'projects', 'clawd3d', 'build'))
YUP_TO_ZUP = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)


def quat_to_mat(q):
    w, x, y, z = np.moveaxis(q, -1, 0)
    return np.stack([np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], -1),
                     np.stack([2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], -1),
                     np.stack([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)], -1)], -2)


def fk(clip):
    rot = quat_to_mat(clip['rot'].astype(np.float64))
    par, off, root = clip['parents'], clip['offsets'].astype(np.float64), clip['root'].astype(np.float64)
    T, J = rot.shape[:2]
    G = np.zeros((T, J, 3, 3)); Pw = np.zeros((T, J, 3))
    for j in range(J):
        p = par[j]
        if p < 0:
            G[:, j] = rot[:, j]; Pw[:, j] = root
        else:
            G[:, j] = G[:, p] @ rot[:, j]
            Pw[:, j] = Pw[:, p] + np.einsum('tab,b->ta', G[:, p], off[j])
    C = YUP_TO_ZUP
    return C @ G @ C.T, Pw @ C.T


def rot_between(a, b):
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b)
    v = np.cross(a, b); c = a @ b
    if np.linalg.norm(v) < 1e-9:
        if c > 0:
            return np.eye(3)
        p = np.cross(a, [1, 0, 0] if abs(a[0]) < 0.9 else [0, 1, 0]); p /= np.linalg.norm(p)
        return 2 * np.outer(p, p) - np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K * (1 / (1 + c))


def heading(G):
    """the hips' heading per frame (deg; 0 = facing -Y, the target's front)."""
    f = G[:, 0] @ np.array([0, -1.0, 0])
    return np.degrees(np.arctan2(f[:, 0], -f[:, 1]))


def retarget(rig, clip, trim=0, face=False):
    """-> list of {bone: 4x4 world deformation (rest -> posed)} per frame (the target's frame: Blender, facing -Y).
    trim: drop the clip's first frames (a video capture's settling glitch); face: turn the whole clip about the vertical
    so the hips' median heading faces the front (a capture canonicalised on a bad first frame)."""
    from soma_map import BONE_MAP
    G, Pw = fk(clip)
    G, Pw = G[trim:], Pw[trim:]
    if face:
        h = float(np.median(np.unwrap(np.radians(heading(G)))))
        c, s_ = np.cos(-h), np.sin(-h)
        Rz = np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1.0]])
        G = Rz @ G; Pw = Pw @ Rz.T
    J = [str(j) for j in clip['joints']]
    rest_clip = dict(clip, rot=np.tile(np.array([1.0, 0, 0, 0]), (1, len(J), 1)), root=np.zeros((1, 3)))
    _, P0 = fk(rest_clip); P0 = P0[0]
    sk = rig.sk
    A = {}
    for b, (j, ch) in BONE_MAP.items():
        if b not in sk.head or b not in sk.tail or j not in J or ch not in J:
            continue
        d_src = P0[J.index(ch)] - P0[J.index(j)]
        d_tgt = sk.tail[b] - sk.head[b]
        if np.linalg.norm(d_src) > 1e-6 and np.linalg.norm(d_tgt) > 1e-6:
            A[b] = rot_between(d_tgt, d_src)
        if b.endswith(('Foot', 'Toes')):
            # both rests stand flat: the feet correspond as they are (aimed along the source's ankle->ball, a heeled
            # boot's steep foot bone (65 deg down vs the source's 21) tipped the foot 44 deg toe-up off the shin)
            A[b] = np.eye(3)
    # the order: parents before children
    order, seen = [], set()
    def visit(b):
        if b in seen:
            return
        p = sk.parent.get(b)
        if p:
            visit(p)
        seen.add(b); order.append(b)
    for b in sk.head:
        visit(b)
    hips_src = float(clip['offsets'][0][1])                      # (the source's rest hips height: Y up)
    scale = sk.head['hips'][2] / max(hips_src, 1e-6)
    root0 = Pw[0, 0].copy(); root0[2] = 0.0
    frames = []
    for t in range(len(G)):
        D = {}
        for b in order:
            j = BONE_MAP.get(b, (None,))[0]
            p = sk.parent.get(b)
            if b in A and j in J:
                R = G[t, J.index(j)] @ A[b]
            else:
                R = D[p][:3, :3] if p in D else np.eye(3)       # (unmapped: carried by its parent)
            if p is None:
                disp = (Pw[t, 0] - root0) * scale
                h_new = np.array([sk.head[b][0] + disp[0], sk.head[b][1] + disp[1], Pw[t, 0][2] * scale])
            else:
                h_new = D[p][:3, :3] @ sk.head[b] + D[p][:3, 3]
            M = np.eye(4); M[:3, :3] = R; M[:3, 3] = h_new - R @ sk.head[b]
            D[b] = M
        frames.append(D)
    # the ground: lift (or drop) the whole figure so the planted ankles stand at their rest height on average
    con = np.asarray(clip['contact'])[trim:] > 0.5
    dz = [(fr_[b][:3, :3] @ sk.head[b] + fr_[b][:3, 3])[2] - sk.head[b][2]
          for k, b in ((0, 'leftFoot'), (2, 'rightFoot')) for f_, fr_ in enumerate(frames) if con[f_, k]]
    if dz:
        lift = -float(np.mean(dz))
        for D in frames:
            for M in D.values():
                M[2, 3] += lift
    return frames


def transfer_weights(rig, nm, group, V):
    """a bundle surface's vertices -> (J (n,k), W (n,k)) from the export object of the same name's nearest rest vertex
    (the counts differ: the export is subdivided); hair, and anything the export doesn't hold, rides the head."""
    from scipy.spatial import cKDTree
    eo = rig.objs.get(nm)
    if eo is None or group == 'hair':
        return np.full((len(V), 1), rig.bones.index('head')), np.ones((len(V), 1)), eo is None and group != 'hair'
    if not hasattr(eo, '_tree'):
        eo._tree = cKDTree(eo.V)
    # the k nearest export vertices' weights blended by inverse distance (one nearest vertex steps the weights where
    # the two meshes' vertices disagree: the skirt's hem read as stairs), the four largest kept
    k = 8
    d, idx = eo._tree.query(V, k=k)
    w_ = 1.0 / np.maximum(d, 1e-5) ** 2; w_ /= w_.sum(1, keepdims=True)
    nb = len(rig.bones)
    dense = np.zeros((len(V), nb))
    for q in range(k):
        Jq, Wq = eo.J[idx[:, q]], eo.W[idx[:, q]]
        for m in range(Jq.shape[1]):
            np.add.at(dense, (np.arange(len(V)), Jq[:, m]), w_[:, q] * Wq[:, m])
    top = np.argsort(-dense, axis=1)[:, :4]
    Wt = np.take_along_axis(dense, top, 1)
    return top, Wt / np.maximum(Wt.sum(1, keepdims=True), 1e-12), False


def lbs(V, J, W, R, t):
    X = np.zeros_like(V)
    for k in range(J.shape[1]):
        w = W[:, k]
        nz = w > 0
        if nz.any():
            j = J[nz, k]
            X[nz] += w[nz, None] * (np.einsum('nij,nj->ni', R[j], V[nz]) + t[j])
    tot = W.sum(1)
    X[tot <= 0] = V[tot <= 0]
    X[tot > 0] /= tot[tot > 0, None]
    return X


def main(build, groom, clip_path, tag, views=(20.0, 200.0), ppl=110, ss=2, trim=0, face=False):
    os.environ.setdefault('CLIP_STYLED', '1'); os.environ.setdefault('CLIP_GRAV_LONG', '0.12')
    os.environ.setdefault('CLIP_RIGID_BANGS', '1'); os.environ.setdefault('CLIP_STIFF_LONG', '40,12')
    os.environ.setdefault('CLIP_K', '12'); os.environ.setdefault('CLIP_HEAD_COLLIDE', '1')
    import clip as C
    from charkit import rom, bundle as bl, palette, qa3d
    from charkit.detailqa import _Window
    from PIL import Image, ImageDraw
    t0 = time.time()
    rig, _ = rom.load(build)
    B = bl.load(groom); palette.activate_spec(B.spec)
    clip = {k: v for k, v in np.load(clip_path, allow_pickle=False).items()}
    frames = retarget(rig, clip, trim, face)
    fps = float(clip['fps'])
    nf = len(frames)
    # the hair's chains, driven by the head bone's deformation per frame
    A = np.load(os.path.join(groom, 'arrays.npz')); M = json.load(open(os.path.join(groom, 'bundle.json')))
    hr = C.build_rig(A, M); C.collider(A, M); C.radial_collider(A, M)
    Hs = [f['head'] for f in frames]
    Cs = [f.get('upperChest', f.get('chest')) for f in frames]
    sim = simulate_head(C, hr, Hs, Cs, fps)
    t_ret = time.time() - t0
    meas = measure(rig, frames, sim, clip, trim, fps)
    json.dump(meas, open(os.path.join(C.OUTD, tag + '.measure.json'), 'w'), indent=1)
    print(json.dumps(meas), flush=True)
    if MEASURE_ONLY:
        return
    base, missing = [], set()
    for o in B.objects():
        if o.group not in ('hair', 'skin', 'eye', 'mouth', 'garment', 'accessory'):
            continue
        variant = 'masked' if o.group == 'skin' and o.has('masked') else 'eval'
        if o.has(variant):
            for s_ in qa3d.surfaces(B, o, variant):
                Jw, Ww, miss = transfer_weights(rig, o.name, o.group, s_['V'])
                if miss:
                    missing.add(o.name)
                base.append((o.name, s_, s_['V'].copy(), Jw, Ww))
    print('not in the export (ride the head):', sorted(missing), flush=True)
    cam = np.mean([f_['hips'][:3, 3] + f_['hips'][:3, :3] @ rig.sk.head['hips'] for f_ in frames], 0)
    fdir = os.path.join(C.OUTD, tag + '_frames')
    if os.path.isdir(fdir):
        for x in os.listdir(fdir):
            if x.endswith('.png'):
                os.remove(os.path.join(fdir, x))
    os.makedirs(fdir, exist_ok=True)
    L = float(B.assembly['L'])
    for f in range(nf):
        Rm, tm = rig.matrices(frames[f])
        D = sim[f]
        surfs = []
        for nm, s_, V0, Jw, Ww in base:
            Vd = V0.copy()
            po = hr['per_obj'].get(nm)
            if po is not None and len(V0) == len(po['vchain']):            # hair: its chain offsets (head space) first
                vc, sv = po['vchain'], po['sv']; m = vc >= 0
                u = sv[m] * (C.K - 1); i0 = np.clip(np.floor(u).astype(int), 0, C.K - 2); fr = (u - i0)[:, None]
                Vd[m] = V0[m] + (1 - fr) * D[vc[m], i0] + fr * D[vc[m], i0 + 1]
            surfs.append(dict(s_, V=lbs(Vd, Jw, Ww, Rm, tm)))
        tiles = []
        for az in views:
            c = np.array([cam[0], cam[1], 0.74])                 # (a fixed camera on the clip's mean hips: the whole figure)
            px = L / ppl / ss
            snap = lambda h: px * ss * round(h / (px * ss))          # (whole output pixels: the downsample needs it)
            fr_ = _Window(c, az, snap(2.0 * L), snap(0.78), px)
            img = qa3d.draw(B, surfs, az, fr_, transparent=False, ss=ss)
            tiles.append((np.clip(img[..., :3], 0, 1) * 255).astype(np.uint8))
        im = Image.fromarray(np.concatenate(tiles, 1))
        ImageDraw.Draw(im).text((6, 4), '%s  %.2fs' % (tag, f / fps), fill=(40, 40, 40))
        im.save(os.path.join(fdir, '%04d.png' % f))
    mp4 = os.path.join(C.OUTD, tag + '.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', '%g' % fps, '-i', os.path.join(fdir, '%04d.png'),
                    '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', mp4],
                   check=True)
    print(json.dumps(dict(tag=tag, frames=nf, seconds=dict(retarget_sim=round(t_ret, 1), total=round(time.time() - t0, 1)),
                          mp4=mp4)))


def simulate_head(C, rig, Hs, Cs, fps=24.0):
    """clip.simulate_vrm's spring bones, driven by a full head transform per frame (4x4 world deformation) instead of
    the turn's yaw: the chains' rest shape carried by the head, the body proxy carried by the chest. -> per frame the
    chains' displacement from their head-carried rest, in the head's REST frame (so LBS by the head adds it back)."""
    K = C.K
    R0 = np.stack([c['nodes'] for c in rig['chains']])
    L0 = np.linalg.norm(np.diff(R0, axis=1), axis=2)
    d0 = np.diff(R0, axis=1) / np.maximum(L0[..., None], 1e-9)
    G = np.array([c['g'] for c in rig['chains']])
    LONG = np.array([np.linalg.norm(np.diff(c['nodes'], axis=0), axis=1).sum() > 0.2 for c in rig['chains']])
    stiff = np.stack([np.linspace(*(C.STIFF_LONG if lg else C.STIFF_G.get(int(g), (C.STIFF_ROOT, C.STIFF_TIP))), K - 1)
                      for g, lg in zip(G, LONG)])
    sn = np.linspace(0, 1, K)
    hold = np.stack([((C.STY_HOLD) if lg else C.HOLD_G.get(int(g), 0.0)) * (1 - 0.75 * sn) for g, lg in zip(G, LONG)])[..., None]
    hold[:, 0] = 0
    grav = np.where(LONG, C.GRAV_LONG, C.GRAVITY)[:, None]
    nf = len(Hs)
    SUB = C.SUB
    dt = 1.0 / fps / SUB
    def xf(M, P):
        return P @ M[:3, :3].T + M[:3, 3]
    def lerpM(a, b, u):
        # (linear blend of 4x4s between frames: fine at 4 substeps for these small per-frame rotations)
        return a * (1 - u) + b * u
    X = xf(Hs[0], R0); Xp = X.copy()
    for _ in range(int(C.WARMUP * fps) * SUB):
        X, Xp = step(C, X, Xp, Hs[0], Cs[0], R0, d0, L0, stiff, hold, grav, dt)
    out = []
    for f in range(nf):
        for sub in range(SUB):
            u = (sub + 1) / SUB
            Hm = lerpM(Hs[f - 1] if f else Hs[0], Hs[f], u)
            Cm = lerpM(Cs[f - 1] if f else Cs[0], Cs[f], u)
            X, Xp = step(C, X, Xp, Hm, Cm, R0, d0, L0, stiff, hold, grav, dt)
        T = xf(Hs[f], R0)
        Hinv = np.linalg.inv(Hs[f])
        out.append((X - T) @ Hinv[:3, :3].T)
        WORLD.append(X.copy())
    return out


WORLD = []                     # (the chains' world positions per frame, from the last simulate_head: for measure())


def measure(rig, frames, sim, clip, trim, fps):
    """the clip's numbers: the hair's own motion (tips in the head's frame: power share above 6 Hz = buzz, peak speed),
    the feet on our rig while the source says planted (slide, mm per frame), the hands' nearest approach to the hair's
    chains (the arms aren't colliders: a hand through the hair shows here first), the hips' height range."""
    D = np.array(sim); tip = D[:, :, -1]
    F = np.fft.rfftfreq(len(tip), 1 / fps)
    hfs = []
    for c in range(tip.shape[1]):
        x = tip[:, c] - tip[:, c].mean(0)
        Pw = (np.abs(np.fft.rfft(x * np.hanning(len(x))[:, None], axis=0)) ** 2).sum(1)
        hfs.append(Pw[F > 6].sum() / max(Pw[F > 0.3].sum(), 1e-18))
    tip_speed = np.linalg.norm(np.diff(tip, axis=0), axis=2) * fps
    def pos(f, b):
        M = frames[f][b]
        return M[:3, :3] @ rig.sk.head[b] + M[:3, 3]
    con = np.asarray(clip['contact'])[trim:] > 0.5
    slide = {}
    for k, b in ((0, 'leftFoot'), (2, 'rightFoot')):
        P = np.array([pos(f, b) for f in range(len(frames))])
        v = np.linalg.norm(np.diff(P[:, :2], axis=0), axis=1) * 1000
        pl = con[1:, k] & con[:-1, k]
        slide[b] = dict(planted_frames=int(pl.sum()), mean_mm=round(float(v[pl].mean()), 2) if pl.any() else None,
                        p95_mm=round(float(np.percentile(v[pl], 95)), 2) if pl.any() else None)
        # the joint angles below the knee (the heeled boot's foot bone broke here once: 52 deg toes-up off a flat
        # source), and the ankle's height while planted against rest (sinking or floating)
        side = b[:-4]
        ang = lambda p_, c_: [np.degrees(np.arccos(np.clip((np.trace(frames[f][p_][:3, :3].T @ frames[f][c_][:3, :3]) - 1) / 2,
                                                            -1, 1))) for f in range(len(frames))]
        slide[b].update(foot_shin_deg_max=round(float(np.max(ang(side + 'LowerLeg', b))), 1),
                        toes_foot_deg_max=round(float(np.max(ang(b, side + 'Toes'))), 1),
                        ankle_dz_planted_cm=round(float((P[1:, 2][pl] - rig.sk.head[b][2]).mean() * 100), 2) if pl.any() else None)
    W = np.array(WORLD)
    near = []
    for f in range(len(frames)):
        Xn = W[f].reshape(-1, 3)
        dm = min(np.linalg.norm(Xn - (pos(f, h) + 0.5 * (pos(f, h) - pos(f, la))), axis=1).min()
                 for h, la in (('leftHand', 'leftLowerArm'), ('rightHand', 'rightLowerArm')))
        near.append(dm)
    near = np.array(near)
    hz = np.array([pos(f, 'hips')[2] for f in range(len(frames))])
    return dict(frames=len(frames), fps=fps,
                hair=dict(hf_share=round(float(np.mean(hfs)), 4), hf_share_max=round(float(np.max(hfs)), 4),
                          tip_speed_p95=round(float(np.percentile(tip_speed, 95)), 3),
                          tip_offset_max_cm=round(float(np.linalg.norm(tip, axis=2).max() * 100), 1)),
                feet=slide,
                hands_to_hair=dict(min_cm=round(float(near.min() * 100), 1), frames_under_3cm=int((near < 0.03).sum())),
                hips_z=dict(min=round(float(hz.min()), 3), max=round(float(hz.max()), 3)))


def step(C, X, Xp, H, Ch, R0, d0, L0, stiff, hold, grav, dt):
    K = R0.shape[1]
    Rh = H[:3, :3]
    T = R0 @ Rh.T + H[:3, 3]
    Xn = X.copy(); Xn[:, 0] = T[:, 0]
    for k in range(1, K):
        rest_dir = d0[:, k - 1] @ Rh.T
        if k >= 2:
            par_rest = d0[:, k - 2] @ Rh.T
            par_now = Xn[:, k - 1] - Xn[:, k - 2]
            par_now /= np.maximum(np.linalg.norm(par_now, axis=1, keepdims=True), 1e-9)
            target = C._rot_between(par_rest, par_now, rest_dir)
        else:
            target = rest_dir
        tail = X[:, k] + (X[:, k] - Xp[:, k]) * (1 - C.DRAG) + target * (stiff[:, k - 1:k] * dt * L0[:, k - 1, None]) \
            + np.array([0, 0, -1.0]) * (grav * dt)
        v = tail - Xn[:, k - 1]
        Xn[:, k] = Xn[:, k - 1] + v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9) * L0[:, k - 1, None]
    Xn = Xn + hold * (T - Xn)
    # the body proxy, carried by the chest: into the chest's rest frame, collide, back
    Ci = np.linalg.inv(Ch)
    Xb = Xn @ Ci[:3, :3].T + Ci[:3, 3]
    Xc = C.collide_radial(Xb.copy())
    Xc = Xc @ Ch[:3, :3].T + Ch[:3, 3]
    if 'tree' in C.COLLIDE:                              # the head: its mesh, in the head's frame, nodes above the neck
        Hi = np.linalg.inv(H)
        Xh = Xc @ Hi[:3, :3].T + Hi[:3, 3]
        flat = Xh[:, 1:].reshape(-1, 3)
        hm = flat[:, 2] > C.COLLIDE['radial']['zmax']
        if hm.any():
            d, j = C.COLLIDE['tree'].query(flat[hm])
            p, n = C.COLLIDE['P'][j], C.COLLIDE['N'][j]
            sd = np.sum((flat[hm] - p) * n, 1)
            push = (sd < 0.02) & (d < 0.08)
            q = flat[hm]; q[push] += n[push] * (0.02 - sd[push])[:, None]; flat[hm] = q
            Xh[:, 1:] = flat.reshape(Xh[:, 1:].shape)
            Xc = Xh @ H[:3, :3].T + H[:3, 3]
    push = Xc - Xn
    Xp_new = X + push * C.INELASTIC
    if C.FRICTION:
        contact = (np.linalg.norm(push, axis=2) > 1e-7)[..., None]
        Xp_new = np.where(contact, Xc - (Xc - Xp_new) * (1 - C.FRICTION), Xp_new)
    return Xc, Xp_new


MEASURE_ONLY = '--measure-only' in sys.argv

if __name__ == '__main__':
    a = sys.argv[1:]
    opt = lambda k, d: a[a.index(k) + 1] if k in a else d
    main(a[0], a[1], a[2], a[3], views=tuple(float(x) for x in opt('--views', '20,200').split(',')),
         ppl=int(opt('--ppl', 110)), trim=int(opt('--trim', 0)), face='--face' in a)
