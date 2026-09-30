"""VRMC_springBone chains, simulated as the VRM 1.0 spec describes (a verlet tail per joint: inertia less drag, a pull
toward the rest direction carried by the parent (stiffness), gravity, the bone's length kept, sphere and capsule
colliders pushing the tail out by its hit radius; each bone then aimed at its tail). The rig's spring chains for the
flaps and the skirt are data in the outfit graph (charkit.outfit.springs, charkit.flapchains) and aren't built into the
build's rig yet (the flaps ride the hips); this is how a VRM runtime would move them, to compare with the cloth solver
and to tune their stiffness and colliders from it.

    ch = Chain(joints, stiffness=, drag=, gravity=, gravity_dir=, hit_radius=)
    ch.reset(D_root)                         # its root bone's deformation (4x4) at the first frame
    ch.step(D_root, dt, capsules)            # capsules: rows (a, b, r, r) as xpbd.Capsules
    ch.carry(V, u)                           # vertices on the chain (u: their place along it, 0 .. bones) moved
"""
import numpy as np


def from_to(a, b):
    """the smallest rotation taking direction a onto direction b."""
    a = a / max(1e-15, np.linalg.norm(a))
    b = b / max(1e-15, np.linalg.norm(b))
    v = np.cross(a, b)
    c = float(a @ b)
    s = np.linalg.norm(v)
    if s < 1e-12:
        if c > 0:
            return np.eye(3)
        p = np.cross(a, [1, 0, 0]) if abs(a[0]) < 0.9 else np.cross(a, [0, 1, 0])
        p /= np.linalg.norm(p)
        return 2 * np.outer(p, p) - np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K * ((1 - c) / (s * s))


class Chain:
    def __init__(self, joints, stiffness=1.0, drag=0.4, gravity=0.0, gravity_dir=(0, 0, -1), hit_radius=0.02):
        self.J = np.asarray(joints, float)
        self.m = len(self.J) - 1
        self.d0 = self.J[1:] - self.J[:-1]
        self.len = np.linalg.norm(self.d0, axis=1)
        self.dir0 = self.d0 / self.len[:, None]
        self.stiff, self.drag, self.grav = float(stiffness), float(drag), float(gravity)
        self.gdir = np.asarray(gravity_dir, float)
        self.hit = float(hit_radius)

    def reset(self, D):
        R, t = D[:3, :3], D[:3, 3]
        self.cur = self.J[1:] @ R.T + t
        self.prev = self.cur.copy()
        self.R = np.stack([R] * self.m)
        self.head = np.vstack([self.J[0] @ R.T + t, self.cur[:-1]])

    def step(self, D, dt, capsules=None):
        Rp = D[:3, :3]
        head = self.J[0] @ Rp.T + D[:3, 3]
        heads, Rs = [], []
        for k in range(self.m):
            aim = Rp @ self.dir0[k]
            nxt = (self.cur[k] + (self.cur[k] - self.prev[k]) * (1.0 - self.drag) + dt * self.stiff * aim
                   + dt * self.grav * self.gdir)
            nxt = head + (nxt - head) / max(1e-15, np.linalg.norm(nxt - head)) * self.len[k]
            if capsules is not None:
                for a, b, r, _ in [(c[0:3], c[3:6], c[6], c[7]) for c in capsules]:
                    ab = b - a
                    t = np.clip(((nxt - a) @ ab) / max(1e-15, ab @ ab), 0, 1)
                    q = a + t * ab
                    d = nxt - q
                    ld = np.linalg.norm(d)
                    if ld < r + self.hit and ld > 1e-12:
                        nxt = q + d / ld * (r + self.hit)
                        nxt = head + (nxt - head) / max(1e-15, np.linalg.norm(nxt - head)) * self.len[k]
            self.prev[k] = self.cur[k]
            self.cur[k] = nxt
            Rk = from_to(aim, nxt - head) @ Rp
            heads.append(head)
            Rs.append(Rk)
            head, Rp = nxt, Rk
        self.head = np.array(heads)
        self.R = np.array(Rs)

    def transforms(self):
        """per bone (R, head now, head at rest)."""
        return self.R, self.head, self.J[:-1]

    def weights(self, u):
        """hat weights (n, bones) on each bone's middle for vertices at u (0 .. m along the chain)."""
        c = np.arange(self.m) + 0.5
        W = np.clip(1.0 - np.abs(np.asarray(u, float)[:, None] - c[None]), 0, 1)
        W[np.asarray(u) <= 0.5, 0] = 1.0
        W[np.asarray(u) >= self.m - 0.5, -1] = 1.0
        return W / W.sum(1, keepdims=True)

    def carry(self, V, u):
        """rest vertices V at chain parameters u, moved with the chain's bones (blended per weights(u))."""
        V = np.asarray(V, float)
        W = self.weights(u)
        X = np.zeros_like(V)
        for k in range(self.m):
            w = W[:, k]
            nz = w > 0
            X[nz] += w[nz, None] * ((V[nz] - self.J[k]) @ self.R[k].T + self.head[k])
        return X


def arc_param(P, J):
    """each point's place along the polyline J (0 .. len(J) - 1): its nearest point on it, as segment index plus the
    fraction along that segment."""
    P = np.asarray(P, float)
    best = np.full(len(P), np.inf)
    u = np.zeros(len(P))
    for k in range(len(J) - 1):
        a, b = J[k], J[k + 1]
        ab = b - a
        t = np.clip(((P - a) @ ab) / max(1e-15, ab @ ab), 0, 1)
        d = np.linalg.norm(P - (a + t[:, None] * ab), axis=1)
        m = d < best
        best[m] = d[m]
        u[m] = k + t[m]
    return u
