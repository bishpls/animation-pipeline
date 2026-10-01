"""Calibration adapter for the neck's join crease (charkit.faceregion.neck_crease, part face_region: the sharpest bend of
the visible skin's outline down any column round the neck at the join, each column the skin's exact cut). A defect
detector on our geometry alone: no drawing grades a 3D bend, so, as charkit.calib.motion does for the motion checks, its
stand-ins are computed from the build under calibration (tool/garments4, 2026-10-01).

  design     the join as the code builds it (code_base._join_neck: the head's neck kept to the cut, one monotone cubic
             per column into the torso), its limit surface sampled one subdivision level finer than the build's
             (charkit.subdiv: the same surface, other rows), with the measure's alignment moved per move: the window
             (the cut) 1-2 design pixels (0.0047 L) up or down, the columns' phase 2.5-5 degrees round. Each must PASS:
             a crease measure reads the surface, not its tessellation (the vertex measure before 2026-10-01 read the
             build's own join 26.9-44.7, its exact cut bends 12.6-14.4)
  known-bad  computed, nothing stored: 'neck_ring' the same skin with a ring 0.02 L proud at the cut, 0.006 L wide (the
             join before tool/face: "the neck was a stalk ending in a ring", docs/workstreams/face.md)
  floor      'jitter_skin': the skin round the join moved along its radius by seeded noise (sd 0.003 L, per vertex): a
             surface with no designed join; a defect detector's floor may pass
"""
import math

import numpy as np

CALIBRATION = [
    dict(check='neck_crease', part='face_region', adapter='NeckJoin', known_bad='neck_ring', kind='defect',
         baseline=['jitter_skin'], shape=[], better='lower'),
]

RING = (0.02, 0.006)            # L: the known-bad's ring, proud and wide (charkit/tests/test_faceregion's)
JITTER = 0.003                  # L: the floor's radial noise
PIX = 0.0047                    # L: a design pixel at the body sheet's scale (212 px per L)


class NeckJoin:
    part = 'face_region'
    generators = {'jitter_skin': 'the skin round the join moved along its radius by seeded noise (sd %.3f L per vertex)'
                                 % JITTER}

    def __init__(self, B, design=None):
        from .. import faceregion as fr
        self.B = B
        self.c, self.L, _ = fr.frame(B)
        o = B.skin()
        try:
            self.V, self.T = fr._mesh(o, 'masked')
            self.variant = 'masked'
        except (KeyError, ValueError):
            self.V, self.T = fr._mesh(o, 'eval')
            self.variant = 'eval'
        self.o = o
        self._fine = None

    @staticmethod
    def _check(K):
        from .. import faceregion as fr
        if K is None:
            return {'neck_crease': {'value': None, 'status': 'SKIPPED'}}
        return {'neck_crease': dict(value=K['max'], status=fr._grade(K['max'], fr.CREASE), worst_column=K['worst'])}

    def _band(self):
        from .. import faceregion as fr
        zc = self.c[2] + fr.CUT * self.L
        return (self.V[:, 2] > zc - (fr.JOIN[0] + 0.08) * self.L) & (self.V[:, 2] < zc + (fr.JOIN[1] + 0.08) * self.L)

    def measure(self, B=None):
        from .. import faceregion as fr
        return self._check(fr.crease_of(self.V, self.T, self.c, self.L))

    def fine(self):
        """the join's skin one subdivision level finer (its polygons round the join, Catmull-Clark at the limit) ->
        (V, T)."""
        if self._fine is None:
            from .. import subdiv
            loopv, starts, counts = self.o.polys(self.variant)
            faces = [tuple(loopv[s:s + n]) for s, n in zip(starts, counts)]
            keep = self._band()
            Vr, Fr, _, _ = subdiv.region(self.V, faces, keep)
            V1, quads, _ = subdiv.catmull_clark(Vr, Fr, levels=1)
            quads = np.asarray(quads)
            T1 = np.concatenate([quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]])
            self._fine = (np.asarray(V1, float), T1)
        return self._fine

    def run(self, kind, arg):
        from .. import faceregion as fr
        if kind == 'design':
            dy, dx = arg
            V, T = self.fine()
            c = np.array(self.c, float)
            c[2] += dy * PIX * self.L                       # (the cut, and its window, moved up or down)
            V = _turn(V, c, math.radians(2.5 * dx))         # (the columns' phase moved round)
            return self._check(fr.crease_of(V, T, c, self.L))
        if kind == 'jitter_skin':
            rng = np.random.default_rng(int(arg))
            V = _radial(self.V, self.c, rng.normal(0.0, JITTER * self.L, len(self.V)) * self._band())
            return self._check(fr.crease_of(V, self.T, self.c, self.L))
        raise KeyError(kind)

    def measure_known_bad(self, name):
        from .. import faceregion as fr
        if name != 'neck_ring':
            raise KeyError(name)
        zc = self.c[2] + fr.CUT * self.L
        dr = RING[0] * self.L * np.exp(-0.5 * ((self.V[:, 2] - zc) / (RING[1] * self.L)) ** 2)
        return self._check(fr.crease_of(_radial(self.V, self.c, dr), self.T, self.c, self.L))


def _axis(V, c):
    return np.asarray(c, float)[:2]


def _radial(V, c, dr):
    """V moved dr along its radius from the vertical axis through c (the neck's axis as near as the head's centre)."""
    q = V[:, :2] - _axis(V, c)
    r = np.maximum(np.hypot(q[:, 0], q[:, 1]), 1e-9)
    out = np.array(V, float, copy=True)
    out[:, :2] += q / r[:, None] * np.asarray(dr)[:, None]
    return out


def _turn(V, c, a):
    """V turned by a round the vertical axis through c."""
    q = V[:, :2] - _axis(V, c)
    ca, sa = math.cos(a), math.sin(a)
    out = np.array(V, float, copy=True)
    out[:, 0] = _axis(V, c)[0] + ca * q[:, 0] - sa * q[:, 1]
    out[:, 1] = _axis(V, c)[1] + sa * q[:, 0] + ca * q[:, 1]
    return out
