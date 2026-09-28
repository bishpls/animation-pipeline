"""Cloak secondary motion: a verlet sim of CK_NC chains (CK_NS+1 points each), anchored to the chest,
with a weak shape-matching spring toward the rest drape, air drag against wind, body-capsule collision.
Bones in char.build_cloak damped-track empties placed at the simulated points."""
import bpy, math
from mathutils import Vector
import char as CH


def _closest(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-9)))
    return a + ab * t


class CloakSim:
    def __init__(self, ch, stiff=(0.0, 0.10, 0.06, 0.035), drag=5.0, grav=0.7, sub=4):
        self.ch, self.arm = ch, ch['arm']
        self.stiff, self.drag, self.grav, self.sub = stiff, drag, grav, sub
        NC, NS, V0 = CH.CK_NC, CH.CK_NS, CH.CK_V0
        self.NC, self.NS = NC, NS
        vs = [V0 + (1 - V0) * k / NS for k in range(NS + 1)]
        cm = self.arm.data.bones['chest'].matrix_local.inverted()
        self.local = [[cm @ CH.cloak_point(c / (NC - 1), v) for v in vs] for c in range(NC)]
        self.L = [[(self.local[c][k + 1] - self.local[c][k]).length for k in range(NS)] for c in range(NC)]
        self.W = [[(self.local[c + 1][k] - self.local[c][k]).length for k in range(NS + 1)] for c in range(NC - 1)]
        self.E = {}
        for c in range(NC):
            for k in range(NS):
                e = bpy.data.objects.new(f'ckt{c}_{k}', None); e.empty_display_size = 0.03
                bpy.context.scene.collection.objects.link(e)
                self.E[c, k] = e
                pb = self.arm.pose.bones[f'ck{c}_{k}']
                con = pb.constraints.new('DAMPED_TRACK'); con.target = e; con.track_axis = 'TRACK_Y'
        self.X = None

    def rest_world(self):
        M = self.arm.matrix_world @ self.arm.pose.bones['chest'].matrix
        return [[M @ p for p in col] for col in self.local]

    def capsules(self):
        mw, PB = self.arm.matrix_world, self.arm.pose.bones
        C = [(mw @ PB['hips'].head + Vector((0, 0, -0.04)), mw @ PB['chest'].tail, 0.15),
             (mw @ PB['chest'].tail, mw @ PB['neck'].tail, 0.10)]
        for s in 'LR':
            C += [(mw @ PB[f'thigh.{s}'].head, mw @ PB[f'thigh.{s}'].tail, 0.095),
                  (mw @ PB[f'shin.{s}'].head, mw @ PB[f'shin.{s}'].tail, 0.075)]
        return C

    def reset(self):
        R = self.rest_world()
        self.X = [[p.copy() for p in col] for col in R]
        self.P = [[p.copy() for p in col] for col in R]

    def step(self, dt, wind, t):
        """wind: world air velocity (m/s). Call after the pose for this frame is applied."""
        if self.X is None:
            self.reset()
        R = self.rest_world()
        caps = self.capsules()
        h = dt / self.sub
        g = Vector((0, 0, -9.8 * self.grav))
        for _ in range(self.sub):
            for c in range(self.NC):
                gust = 1 + 0.35 * math.sin(t * 7.1 + c * 1.3) + 0.2 * math.sin(t * 13.7 + c * 2.9)
                w = Vector(wind) * gust
                for k in range(1, self.NS + 1):
                    x, xp = self.X[c][k], self.P[c][k]
                    vel = (x - xp) / h
                    acc = g + (w - vel) * self.drag * (0.6 + 0.4 * k / self.NS)
                    nx = x + (x - xp) * 0.995 + acc * h * h
                    nx += (R[c][k] - nx) * self.stiff[k]
                    self.P[c][k] = x
                    self.X[c][k] = nx
                self.X[c][0] = R[c][0]; self.P[c][0] = R[c][0]
            for _it in range(3):
                for c in range(self.NC):          # chains: keep segment lengths
                    for k in range(self.NS):
                        a, b = self.X[c][k], self.X[c][k + 1]
                        d = b - a; ln = max(d.length, 1e-6)
                        self.X[c][k + 1] = a + d * (self.L[c][k] / ln)
                for c in range(self.NC - 1):      # neighbours: loose width limits (no tearing, no bunching)
                    for k in range(1, self.NS + 1):
                        a, b = self.X[c][k], self.X[c + 1][k]
                        d = b - a; ln = max(d.length, 1e-6); r0 = self.W[c][k]
                        tgt = min(max(ln, r0 * 0.55), r0 * 1.25)
                        if tgt != ln:
                            corr = d * ((ln - tgt) / ln * 0.5)
                            self.X[c][k] = a + corr; self.X[c + 1][k] = b - corr
                for c in range(self.NC):          # body collision
                    for k in range(1, self.NS + 1):
                        p = self.X[c][k]
                        for a, b, r in caps:
                            q = _closest(p, a, b); d = p - q
                            if d.length < r + 0.02:
                                p = q + (d.normalized() if d.length > 1e-6 else Vector((0, 1, 0))) * (r + 0.02)
                        if p.z < 0.03:
                            p.z = 0.03
                        self.X[c][k] = p

    def apply(self, frame=None):
        for (c, k), e in self.E.items():
            e.location = self.X[c][k + 1]
            if frame is not None:
                e.keyframe_insert('location', frame=frame)
