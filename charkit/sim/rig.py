"""Venv-side posing for the motion pilot: the skeleton's skinning matrices from a build's joints (bundle landmarks) and
motion QA's poses (charkit.evalmesh.POSES: per bone a rotation (axis, degrees) in the armature's frame about its head,
composed down the chain, as evalmesh.motion_main poses Blender's armature), linear blend skinning, and capsule colliders
fitted to the skin (uniform radius per capsule, as VRMC_springBone's colliders are).

    R = Rig(joints)
    D = R.skinning(POSES['kick'], f=0.5)        # {bone: 4x4}, half way into the pose
    X = lbs(V, W, D)                            # W {bone: (n,)}
    caps = fit_capsules(V, W, R)                # [(name, bone, a, b, radius, fit stats)]
"""
import numpy as np

from .xpbd import rotation

LEG_BONES = ('leftUpperLeg', 'leftLowerLeg', 'rightUpperLeg', 'rightLowerLeg')   # (the pelvis as one capsule
# across the hip joints fits badly: 0.24 L at p90 on Clawd; left out)
AXES = {'X': (1.0, 0.0, 0.0), 'Y': (0.0, 1.0, 0.0), 'Z': (0.0, 0.0, 1.0)}


class Rig:
    """the VRM humanoid skeleton (charkit.mh.VRM_JOINTS, VRM_PARENT) on a build's joints."""

    def __init__(self, joints):
        from ..mh import VRM_JOINTS, VRM_PARENT
        self.head, self.tail, self.parent = {}, {}, {}
        for b, (h, t) in VRM_JOINTS.items():
            if h in joints and t in joints:
                self.head[b] = np.asarray(joints[h], float)
                self.tail[b] = np.asarray(joints[t], float)
                if np.linalg.norm(self.tail[b] - self.head[b]) < 1e-4:
                    self.tail[b] = self.head[b] + np.array([0, 0, 0.02])
                self.parent[b] = VRM_PARENT.get(b)
        order, seen = [], set()

        def visit(b):
            if b in seen:
                return
            p = self.parent.get(b)
            if p in self.head:
                visit(p)
            seen.add(b)
            order.append(b)
        for b in self.head:
            visit(b)
        self.order = order

    def skinning(self, pose, f=1.0):
        """{bone: 4x4 deformation (world rest -> world posed)} for pose {bone: (axis, degrees)} taken f of the way."""
        D = {}
        for b in self.order:
            M = np.eye(4)
            if b in (pose or {}):
                ax, deg = pose[b]
                R = rotation(AXES[ax], np.radians(deg) * f)
                h = self.head[b]
                M[:3, :3] = R
                M[:3, 3] = h - R @ h
            p = self.parent.get(b)
            D[b] = D[p] @ M if p in D else M
        return D


def lbs(V, W, D):
    """linear blend skinning of V (n, 3) with weights {bone: (n,)} (normalised, as Blender's Armature does) by D."""
    V = np.asarray(V, float)
    X = np.zeros_like(V)
    tot = np.zeros(len(V))
    for b, w in W.items():
        if b not in D:
            continue
        w = np.asarray(w, float)
        nz = w > 0
        if not nz.any():
            continue
        M = D[b]
        X[nz] += w[nz, None] * (V[nz] @ M[:3, :3].T + M[:3, 3])
        tot[nz] += w[nz]
    free = tot <= 0
    X[~free] /= tot[~free, None]
    X[free] = V[free]
    return X


def fit_capsules(V, W, rig, bones=LEG_BONES, split=2, dominant=0.5, q=50):
    """capsules fitted to the skin: per bone its dominant vertices (weight over `dominant`), its segment split into
    `split` capsules along the bone, each a uniform radius, the `q` percentile of those vertices' distance from it (50:
    the surface through them); the hips a capsule across the pelvis between the upper legs' heads. -> [dict(name, bone,
    a, b, r, n, err_p50, err_p90)]: err the vertices' |distance - r|, L-free (m)."""
    V = np.asarray(V, float)
    names = sorted(W)
    Wm = np.stack([np.asarray(W[b], float) for b in names], 1)
    dom = np.array(names)[Wm.argmax(1)]
    out = []
    for b in bones:
        if b not in rig.head:
            continue
        sel = (dom == b) & (np.asarray(W[b]) > dominant)
        P = V[sel]
        if b == 'hips':
            if 'leftUpperLeg' not in rig.head:
                continue
            segs = [(rig.head['leftUpperLeg'], rig.head['rightUpperLeg'])]
        else:
            a, e = rig.head[b], rig.tail[b]
            segs = [(a + (e - a) * k / split, a + (e - a) * (k + 1) / split) for k in range(split)]
        for k, (a, e) in enumerate(segs):
            ab = e - a
            t = ((P - a) @ ab) / max(1e-12, ab @ ab)
            inn = (t >= 0) & (t <= 1)
            if inn.sum() < 8:
                continue
            c = a + np.clip(t[inn], 0, 1)[:, None] * ab
            rho = np.linalg.norm(P[inn] - c, axis=1)
            r = float(np.percentile(rho, q))
            err = np.abs(rho - r)
            out.append(dict(name='%s_%d' % (b, k), bone=b, a=a, b=e, r=r, n=int(inn.sum()),
                            err_p50=float(np.percentile(err, 50)), err_p90=float(np.percentile(err, 90))))
    return out


def fit_torso(V, W, rig, bones=('hips', 'spine'), slabs=3, dominant=0.5, q=50, trim=0.05):
    """the pelvis and the belly as capsules across the body (VRM's collider shape): per bone its dominant skin vertices,
    cut into `slabs` along the bone, each slab a capsule whose segment runs left-right (world x) through the slab, its
    depth centre, half-length and radius fitted to the slab's vertices (the stadium a capsule's section makes against the
    torso's rounded section; round 1's one capsule between the hip joints fitted at 0.24 L p90). -> [dict] as
    fit_capsules'."""
    from scipy.optimize import least_squares
    V = np.asarray(V, float)
    names = sorted(W)
    Wm = np.stack([np.asarray(W[b], float) for b in names], 1)
    dom = np.array(names)[Wm.argmax(1)]
    out = []
    for b in bones:
        if b not in rig.head:
            continue
        sel = (dom == b) & (np.asarray(W[b]) > dominant)
        P = V[sel]
        if len(P) < 32:
            continue
        a, e = rig.head[b], rig.tail[b]
        ax = (e - a) / np.linalg.norm(e - a)
        s = (P - a) @ ax
        lo, hi = np.quantile(s, [trim, 1 - trim])
        cuts = np.linspace(lo, hi, slabs + 1)
        x0 = float(np.median(P[:, 0]))
        for k in range(slabs):
            m = (s >= cuts[k]) & (s <= cuts[k + 1])
            Q = P[m]
            if len(Q) < 16:
                continue
            h = 0.5 * (cuts[k] + cuts[k + 1])
            base = a + h * ax
            xh = np.array([1.0, 0.0, 0.0])

            def res(z, Q=Q):
                c = np.array([x0, z[0], base[2] + z[1]])
                t = np.clip((Q - c) @ xh, -z[2], z[2])
                return np.linalg.norm(Q - (c + t[:, None] * xh), axis=1) - z[3]
            y0, w0, d0 = float(np.median(Q[:, 1])), 0.5 * np.ptp(Q[:, 0]), 0.5 * np.ptp(Q[:, 1])
            z0 = [y0, 0.0, max(0.0, w0 - d0), d0]
            r = least_squares(res, z0, bounds=([-np.inf, -0.5 * (cuts[1] - cuts[0]), 0.0, 1e-4],
                                               [np.inf, 0.5 * (cuts[1] - cuts[0]), np.inf, np.inf]), loss='soft_l1')
            y, dz, hl, rad = r.x
            c = np.array([x0, y, base[2] + dz])
            d = res(r.x) + rad
            rad = float(np.percentile(d, q))
            err = np.abs(d - rad)
            out.append(dict(name='%s_%d' % (b, k), bone=b, a=c - hl * xh, b=c + hl * xh, r=rad, n=int(len(Q)),
                            err_p50=float(np.percentile(err, 50)), err_p90=float(np.percentile(err, 90))))
    return out


def rest_clear(caps, P, margin):
    """the capsules shrunk so none holds a point of P at rest (the cloth's own rest vertices: a collider that already
    holds the garment would push the drawn shape out before anything moves); each keeps `margin` clear. -> caps
    (copies, with 'r_fit' the fitted radius)."""
    P = np.asarray(P, float)
    out = []
    for c in caps:
        ab = c['b'] - c['a']
        t = np.clip(((P - c['a']) @ ab) / max(1e-24, ab @ ab), 0, 1)
        d = np.linalg.norm(P - (c['a'] + t[:, None] * ab), axis=1)
        out.append(dict(c, r_fit=c['r'], r=float(max(0.0, min(c['r'], d.min() - margin)))))
    return out


def transfer_weights(P, V, F, W):
    """skin weights carried to points P from the nearest point of the mesh (V, F) with vertex weights W {bone: (n,)}
    (barycentric at that point: a garment made to follow the body under it, as production rigs transfer the body's
    weights to cloth). -> {bone: (len(P),)}."""
    from ..geom.bvh import BVH
    P = np.asarray(P, float)
    B = BVH((np.asarray(V, float), np.asarray(F, np.int64)))
    _, tri, q = B.nearest(P)
    T = np.asarray(F)[tri]
    A, Bv, C = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    v0, v1, v2 = Bv - A, C - A, q - A
    d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1)
    d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
    den = np.maximum(d00 * d11 - d01 * d01, 1e-30)
    bv = (d11 * d20 - d01 * d21) / den
    bw = (d00 * d21 - d01 * d20) / den
    bc = np.clip(np.stack([1 - bv - bw, bv, bw], 1), 0, 1)
    bc /= bc.sum(1, keepdims=True)
    return {b: (np.asarray(w, float)[T] * bc).sum(1) for b, w in W.items()}


def capsule_rows(caps, D, shrink=0.0):
    """the capsules posed by D: rows (a, b, r, r) for xpbd.Capsules (radius less `shrink`)."""
    rows = []
    for c in caps:
        M = D[c['bone']]
        a = M[:3, :3] @ c['a'] + M[:3, 3]
        b = M[:3, :3] @ c['b'] + M[:3, 3]
        r = max(0.0, c['r'] - shrink)
        rows.append(np.r_[a, b, r, r])
    return np.array(rows)


def smoothstep(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)
