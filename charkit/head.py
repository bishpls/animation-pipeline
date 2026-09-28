"""The anime head shape (docs/CHARKIT.md §2): a knob-driven analytic surface (spline profiles for the face and the back of
the skull, an elliptical dome cranium, superellipse sections) that charkit/anime_head.py wraps MakeHuman's head topology
onto.

Head space: origin at the eye line's centre, x = her left, y = back (front is -y), z = up, metres. L = head length (chin to
skull top) = height / heads_tall. All shape knobs are multipliers around 1.0 (defaults: a HoYoverse-style young heroine).
"""
import math
import numpy as np

DEFAULT_HEAD = {
    'width': 1.0,      # every half-width (the face at the eye line is 0.34 L)
    'temple': 1.0,     # the cranium's widest half-width (0.35 L, just above the brow)
    'cranium': 1.0,    # skull top above the eye line, x 0.555 L
    'face_len': 1.0,   # chin below the eye line, x 0.445 L
    'cheek': 1.0,      # how full the cheek stays below the eyes
    'jaw_w': 1.0,      # half-width through the jaw (the V's sides)
    'chin': 1.0,       # chin width (0.6 = pointed, 1.4 = soft)
    'chin_fwd': 1.0,   # chin depth (forward/back)
    'forehead': 1.0,   # forehead slope (< 1 slopes back more)
    'flat': 1.0,       # face flatness (superellipse)
    'depth': 1.0,      # front-to-back depth of the skull
    'back': 1.0,       # back-of-skull bulge
    'socket': 1.0,     # eye socket depth
    'eye_x': 1.0,      # eye spacing (socket centres)
    'eye_z': 0.0,      # eye sockets up (+) / down, in L
    'nose': 1.0,       # nose ridge and tip (the analytic features() bump; the wrap leaves it out)
    'nose_tip': 0.0,   # the nose's projection in front of the face, in L: a relief on the wrapped face (nose_relief)
    'mouth_z': 1.0,    # mouth below the eye line, x 0.28 L
    'nose_z': 1.0,     # nose tip below the eye line, x 0.145 L
    'mouth_w': 1.0,    # mouth half-width, x 0.085 L
    'neck_r': 1.0,     # neck radius under the jaw
    'ear': 1.0,        # ear size (the MakeHuman ear's detail)
    'low_wf': None,    # optional: the lower face's half-widths at LOW_D (in L), e.g. fitted to a design by charkit.refs
}

# profiles (units of L): the lower face by d = 0 (eye line) .. 1 (chin); the cranium from the eye line to Z_C (its widest)
# and then an elliptical dome to the top
LOW_D = [0.0, 0.2, 0.4, 0.6, 0.8, 0.93, 1.0]
LOW_WF = [0.340, 0.334, 0.305, 0.255, 0.180, 0.125, 0.085]     # the face's half-width: cheeks, the V, the chin
LOW_WB = [0.350, 0.345, 0.330, 0.300, 0.255, 0.225, 0.205]     # behind the ears: the skull narrowing to the nape
LOW_DF = [0.355, 0.353, 0.347, 0.338, 0.325, 0.312, 0.300]     # the face plane (without features)
LOW_DB = [0.465, 0.445, 0.400, 0.330, 0.270, 0.240, 0.230]     # the back of the skull
Z_C = 0.13
CR = dict(wf=0.350, wb=0.356, df=0.345, db=0.470)                # at Z_C


class Pchip:
    """monotone cubic interpolation (Fritsch-Carlson) of (xs, ys); clamped outside. Slopes precomputed."""

    def __init__(self, xs, ys):
        self.xs = xs = np.asarray(xs, float); self.ys = ys = np.asarray(ys, float)
        self.h = h = np.diff(xs); dl = np.diff(ys) / h
        m = np.zeros(len(xs))
        m[0], m[-1] = dl[0], dl[-1]
        for k in range(1, len(xs) - 1):
            if dl[k - 1] * dl[k] > 0:
                w1, w2 = 2 * h[k] + h[k - 1], h[k] + 2 * h[k - 1]
                m[k] = (w1 + w2) / (w1 / dl[k - 1] + w2 / dl[k])
        self.m = m

    def __call__(self, x):
        xs, ys, h, m = self.xs, self.ys, self.h, self.m
        if x <= xs[0]:
            return float(ys[0])
        if x >= xs[-1]:
            return float(ys[-1])
        k = int(np.searchsorted(xs, x) - 1)
        t = (x - xs[k]) / h[k]
        t2, t3 = t * t, t * t * t
        return float((2 * t3 - 3 * t2 + 1) * ys[k] + (t3 - 2 * t2 + t) * h[k] * m[k] + (-2 * t3 + 3 * t2) * ys[k + 1]
                     + (t3 - t2) * h[k] * m[k + 1])

    def many(self, x):
        """__call__ over an array (the same arithmetic)."""
        xs, ys, h, m = self.xs, self.ys, self.h, self.m
        x = np.asarray(x, float)
        k = np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2)
        t = (x - xs[k]) / h[k]
        t2, t3 = t * t, t * t * t
        v = ((2 * t3 - 3 * t2 + 1) * ys[k] + (t3 - 2 * t2 + t) * h[k] * m[k] + (-2 * t3 + 3 * t2) * ys[k + 1]
             + (t3 - t2) * h[k] * m[k + 1])
        return np.where(x <= xs[0], ys[0], np.where(x >= xs[-1], ys[-1], v))


def pchip(xs, ys, x):
    return Pchip(xs, ys)(x)


def _knobs(k):
    K = dict(DEFAULT_HEAD); K.update(k or {})
    return K


class Head:
    def __init__(self, L, knobs=None, features=True):
        self.L = L
        self.K = K = _knobs(knobs)
        self.feat = features
        self.top = 0.555 * L * K['cranium']
        self.chin = 0.445 * L * K['face_len']
        self.w0 = 0.340 * L * K['width']
        self.df = 0.355 * L * K['depth']              # face plane depth at the eye line
        self.db = 0.465 * L * K['depth'] * K['back']  # back of the skull at the eye line
        self.mouth_z = -0.28 * L * K['mouth_z']
        self.nose_z = -0.145 * L * K['nose_z']
        self.mouth_w = 0.085 * L * K['mouth_w']
        self.eye_x = 0.168 * L * K['eye_x']
        self.eye_z = 0.012 * L + K['eye_z'] * L
        # the lower-face profiles with the knobs folded in
        c, j, ch = K['cheek'], K['jaw_w'], K['chin']
        zone = [1, 1 + (c - 1) * 0.6, c, 0.5 * (c + j), j, 0.5 * (j + ch), ch]
        base_wf = K.get('low_wf') or LOW_WF                     # a fitted profile (charkit.refs) replaces the default
        self.lwf = [w * L * K['width'] * z for w, z in zip(base_wf, zone)]
        self.lwb = [w * L * K['width'] for w in LOW_WB]
        cf = K['chin_fwd']
        self.ldf = [d * L * K['depth'] * (1 + (cf - 1) * t ** 2) for d, t in zip(LOW_DF, LOW_D)]
        self.ldb = [d * L * K['depth'] * K['back'] for d in LOW_DB]
        self._p = [Pchip(LOW_D, v) for v in (self.lwf, self.lwb, self.ldf, self.ldb)]
        self.zc = Z_C * L * K['cranium']
        self.cr = dict(wf=CR['wf'] * L * K['width'] * K['temple'], wb=CR['wb'] * L * K['width'] * K['temple'],
                       df=CR['df'] * L * K['depth'] * (1 - 0.3 * (1 - K['forehead'])),
                       db=CR['db'] * L * K['depth'] * K['back'])

    def section(self, z):
        """(front half-width, back half-width, front depth, back depth, superellipse n) at height z."""
        K = self.K
        if z >= 0:
            if z <= self.zc:
                t = z / self.zc
                e = t * t * (3 - 2 * t)
                wf = self.lwf[0] + (self.cr['wf'] - self.lwf[0]) * e
                wb = self.lwb[0] + (self.cr['wb'] - self.lwb[0]) * e
                df = self.ldf[0] + (self.cr['df'] - self.ldf[0]) * e
                db = self.ldb[0] + (self.cr['db'] - self.ldb[0]) * e
                return wf, wb, df, db, 2.35 * K['flat']
            t = min(1.0, (z - self.zc) / (self.top - self.zc))
            k = max(0.0, 1 - t * t) ** 0.5
            n = (2.35 - 0.3 * t) * K['flat']
            return self.cr['wf'] * k, self.cr['wb'] * k, self.cr['df'] * k, self.cr['db'] * k, n
        d = min(1.0, -z / self.chin)
        n = (2.35 - 0.85 * d ** 1.4) * K['flat']                 # the lower face narrows to a forward V in section
        return self._p[0](d), self._p[1](d), self._p[2](d), self._p[3](d), max(1.45, n)

    def sections(self, z):
        """section() over an array of heights -> five arrays."""
        K = self.K
        z = np.asarray(z, float)
        o = np.ones_like(z)
        # up to the cranium's widest (Z_C)
        t = np.clip(z / self.zc, 0, 1)
        e = t * t * (3 - 2 * t)
        mid = [self.lwf[0] + (self.cr['wf'] - self.lwf[0]) * e, self.lwb[0] + (self.cr['wb'] - self.lwb[0]) * e,
               self.ldf[0] + (self.cr['df'] - self.ldf[0]) * e, self.ldb[0] + (self.cr['db'] - self.ldb[0]) * e,
               2.35 * K['flat'] * o]
        # the dome
        t = np.minimum(1.0, (z - self.zc) / (self.top - self.zc))
        k = np.maximum(0.0, 1 - t * t) ** 0.5
        top = [self.cr['wf'] * k, self.cr['wb'] * k, self.cr['df'] * k, self.cr['db'] * k, (2.35 - 0.3 * t) * K['flat']]
        # the lower face
        d = np.clip(-z / self.chin, 0, 1)
        n = (2.35 - 0.85 * d ** 1.4) * K['flat']
        low = [p.many(d) for p in self._p] + [np.maximum(1.45, n)]
        return tuple(np.where(z < 0, lo_, np.where(z <= self.zc, mi, tp)) for lo_, mi, tp in zip(low, mid, top))

    def _xy(self, a, sec):
        """surface() over arrays of azimuths a with their sections sec (sections() of the heights) -> (x, y) without the
        features."""
        wf, wb, df, db, n = sec
        s, c = np.sin(a), np.cos(a)
        front = c > 0
        w = np.where(front, wf, wf + (wb - wf) * np.minimum(1, -c * 2.2))
        dep = np.where(front, df, db)
        ex = 1.0 + (2 / n - 1.0) * np.where(front, np.maximum(c, 0.0) ** 0.5, 0.0)
        return np.copysign(np.abs(s) ** ex, s) * w, -np.copysign(np.abs(c) ** ex, c) * dep

    def surfaces(self, a, z):
        """surface() over arrays of azimuths and heights -> (M, 3)."""
        a, z = np.broadcast_arrays(np.asarray(a, float), np.asarray(z, float))
        x, y = self._xy(a, self.sections(z))
        if self.feat:
            y = y + np.where(np.cos(a) > 0, self.features_many(x, z), 0.0)
        return np.stack([x, y, z], -1)

    def surface(self, a, z):
        wf, wb, df, db, n = self.section(z)
        s, c = math.sin(a), math.cos(a)
        front = c > 0
        w = wf if front else wf + (wb - wf) * min(1, -c * 2.2)
        dep = df if front else db
        ex = 1.0 + (2 / n - 1.0) * (c ** 0.5 if front else 0.0)      # flat face -> round skull, smoothly through the sides
        x = math.copysign(abs(s) ** ex, s) * w
        y = -math.copysign(abs(c) ** ex, c) * dep
        if front and self.feat:
            y += self.features(x, z)
        return np.array([x, y, z])

    def features(self, x, z):
        """offsets in y (+ = back) on the face: eye sockets, the nose ridge and tip, the mouth set back a touch, cheeks."""
        L, K = self.L, self.K
        off = 0.0
        for sx in (-1, 1):                              # eye sockets: shallow, wide ovals
            off += 0.012 * L * K['socket'] * math.exp(-((x - sx * self.eye_x) / (0.10 * L)) ** 2 - ((z - self.eye_z) / (0.075 * L)) ** 2)
        nz = -0.115 * L                                  # nose tip below the eye line
        off -= 0.020 * L * K['nose'] * math.exp(-(x / (0.022 * L)) ** 2 - ((z - nz) / (0.035 * L)) ** 2)
        off -= 0.007 * L * K['nose'] * math.exp(-(x / (0.018 * L)) ** 2) * (1 if nz < z < 0.0 else 0)
        off += 0.004 * L * math.exp(-(x / (0.06 * L)) ** 2 - ((z - self.mouth_z) / (0.03 * L)) ** 2)
        return off

    def nose_relief(self, x, y, z):
        """the anime nose as a relief on the wrapped face: how far (metres, forward) head-space points move for the
        'nose_tip' knob (the tip's projection in L). A ridge from just under the eye line grows to the tip at the nose
        height and turns back under it within ~0.03 L; narrow (about 0.02 L either side at the tip), on the front only."""
        L, tip = self.L, self.K.get('nose_tip', 0.0)
        x, y, z = (np.asarray(a, float) / L for a in (x, y, z))
        if not tip:
            return np.zeros_like(x)
        nz, zb = self.nose_z / L, -0.035
        ramp = np.clip((zb - z) / (zb - nz), 0, None) ** 1.6
        cap = np.exp(-(np.maximum(0.0, nz - z) / 0.02) ** 2)
        w = 0.010 + 0.016 * np.minimum(1.0, ramp)
        front = np.clip((-y - 0.2) / 0.1, 0, 1)
        return tip * L * ramp * cap * np.exp(-(x / w) ** 2) * front

    def features_many(self, x, z):
        """features() over arrays."""
        L, K = self.L, self.K
        off = 0.0
        for sx in (-1, 1):
            off = off + 0.012 * L * K['socket'] * np.exp(-((x - sx * self.eye_x) / (0.10 * L)) ** 2 - ((z - self.eye_z) / (0.075 * L)) ** 2)
        nz = -0.115 * L
        off = off - 0.020 * L * K['nose'] * np.exp(-(x / (0.022 * L)) ** 2 - ((z - nz) / (0.035 * L)) ** 2)
        off = off - 0.007 * L * K['nose'] * np.exp(-(x / (0.018 * L)) ** 2) * ((nz < z) & (z < 0.0))
        return off + 0.004 * L * np.exp(-(x / (0.06 * L)) ** 2 - ((z - self.mouth_z) / (0.03 * L)) ** 2)


def jaw_z(H, a):
    """the head's lower boundary height at azimuth a: the chin at the front, the jaw corner at the sides, the nape behind."""
    c = math.cos(a)
    front = -H.chin
    side = -H.chin * 0.52
    back = -0.34 * H.L
    if c >= 0:
        t = c ** 0.9
        return side + (front - side) * t
    t = (-c) ** 1.2
    return side + (back - side) * t
