"""The hand template (tool/hands, docs/workstreams/hands.md; docs/ROADMAP.md item 7): the authored body's hand, replacing
the mitten the arm's tube ended in. Templates first: a few parameters (the hand's length and the palm's share of it,
the palm's width and thickness, the fingers' lengths, widths and taper, the thumb's base and angles, the hand's turn
about the forearm) fitted to the design's drawn hands per view (fit(): the hand checks' own measure, charkit.handqa),
stylised anime proportions: a narrow palm, long slim tapering fingers.

Built in the hull's frame (L, eye line z = 0, x toward her left, -y toward the viewer), at the arm chain's wrist.
The hand's frame: ex along the hand (toward the fingertips), ez out of its back (dorsal), ey across it toward the
thumb's side (radial). At yaw 0 the back of the hand faces out to her side (the palm toward the thigh); yaw turns the
back toward the viewer.

Parts, each a tube of rings (rows, nth, 3) capped at both ends, with per-ring weights on its bones (by construction
along its chain, eased over a finger's joint by JOINT_BLEND of its radius):
  palm     a rounded box from inside the cuff to past the knuckles: the Hand bone
  thumb    CMC -> MCP -> IP -> tip: Metacarpal, Proximal, Distal (the Hand's where it enters the palm)
  index, middle, ring, little    MCP -> PIP -> DIP -> tip: Proximal, Intermediate, Distal (the Hand's in the palm)
Each finger carries joint loops: two rings either side of each knuckle, so a bend keeps its volume there.
Joints (MakeHuman's names, as code_body._joints lays them): finger1 the thumb .. finger5 the little finger, segments 1-3.

    P = code_hand.params(spec)                                  # the spec's body.hand over DEFAULT
    H = code_hand.hand(J, 'left', P)                            # J: the arm chain (shoulder, elbow, wrist, hand end)
    python -m charkit.code_hand fit --build BUILD [--write SPEC]  # fit the knobs to the drawn hands (a build: its grids)
"""
import json, os, sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT = dict(
    length=0.66,          # L: the wrist joint to the middle fingertip
    palm=0.46,            # the palm's share of the length (the middle knuckle's distance from the wrist)
    palm_w=0.2,           # L: the palm's width across the knuckles
    wrist_w=0.13,         # L: its width at the wrist
    palm_t=0.07,          # L: its thickness
    finger_w=0.05,        # L: the middle finger's width at its knuckle
    taper=0.7,            # a finger's width at its tip over its knuckle's
    fingers=(0.93, 1.0, 0.95, 0.78),    # index, middle, ring, little: lengths over the middle's
    spread=3.0,           # degrees between neighbouring fingers (a fan about the middle)
    curl=6.0,             # degrees each finger joint bends toward the palm at rest (the drawn relaxed hand)
    thumb_len=0.3,        # L: the thumb from its CMC to its tip
    thumb_w=0.056,        # L: its width at its MCP
    thumb_out=30.0,       # degrees the thumb opens from the hand's axis toward its side (radial)
    thumb_down=35.0,      # degrees it turns toward the palm (opposition)
    thumb_base=0.1,       # L: its CMC from the wrist along the hand
    yaw=40.0,             # degrees the back of the hand turns from her side toward the viewer, about the forearm
    bend=0.0,             # degrees the hand bends at the wrist toward the palm (flexion; - extension)
    dev=0.0,              # degrees it bends toward the little finger's side (ulnar deviation; - radial)
)
FIT_KNOBS = ('length', 'palm', 'palm_w', 'wrist_w', 'palm_t', 'finger_w', 'taper', 'yaw', 'bend', 'dev', 'thumb_base',
             'thumb_len', 'thumb_out', 'thumb_down', 'spread', 'curl')
BOUNDS = dict(length=(0.45, 0.85), palm=(0.4, 0.52), palm_w=(0.14, 0.27), wrist_w=(0.09, 0.18),
              palm_t=(0.045, 0.085), finger_w=(0.035, 0.062), taper=(0.55, 0.9), spread=(0.0, 12.0), curl=(0.0, 30.0),
              thumb_len=(0.22, 0.38), thumb_w=(0.04, 0.075), thumb_out=(5.0, 70.0), thumb_down=(0.0, 70.0),
              thumb_base=(0.04, 0.16), yaw=(-60.0, 110.0), bend=(-30.0, 30.0), dev=(-25.0, 25.0))
FINGERS = ('index', 'middle', 'ring', 'little')
PHALANGES = (0.45, 0.3, 0.25)         # a finger's proximal, intermediate and distal shares of its length
THUMB_BONES = (0.36, 0.36, 0.28)      # the thumb's metacarpal, proximal and distal shares
WIDTH = (1.0, 1.03, 0.96, 0.84)       # index .. little: width over the middle's
KNUCKLE_ARC = (0.035, 0.0, 0.03, 0.09)  # index .. little: the knuckle's setback from the middle's, over the palm's length
ACROSS = (0.36, 0.12, -0.12, -0.36)   # index .. little: the knuckle across the palm, over its width (radial +)
DEPTH = 0.86                          # a finger's section: its dorsal-palmar depth over its width
JOINT_BLEND = 0.8                     # a finger's weight eases across a knuckle over this share of its radius each side
INSET = 0.04                          # L: a finger's tube starts this far inside the palm, behind its knuckle
NTH = dict(palm=20, thumb=10, finger=10)
WRIST_KEEP = 0.0                      # L: the arm's tube keeps its rows up to this past the wrist (under the cuff; the palm
                                      # starts 0.06 behind the wrist, inside it)
UV_BAND = (0.25, 0.1, 0.5, 0.2)       # the hands' UV slots: this band (under the legs' slots, beside the feet's) in 12
PARTS = ('palm', 'thumb') + FINGERS
VRM = {'thumb': 'Thumb', 'index': 'Index', 'middle': 'Middle', 'ring': 'Ring', 'little': 'Little'}
SEGS = {'thumb': ('Metacarpal', 'Proximal', 'Distal')}
MH = {'thumb': 1, 'index': 2, 'middle': 3, 'ring': 4, 'little': 5}


def params(spec=None, **over):
    """the hand's knobs: DEFAULT, the spec's body.hand over it, then over."""
    P = dict(DEFAULT)
    P.update(((spec or {}).get('body') or {}).get('hand') or {})
    P.update(over)
    P['fingers'] = tuple(P['fingers'])
    return P


def _rot(axis, deg):
    """a rotation matrix about a unit axis by deg degrees (right-handed)."""
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    t = np.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(t) * K + (1 - np.cos(t)) * K @ K


def frame(J, side, P):
    """the hand's frame at the wrist: (W, R) with R's columns ex (along the hand), ey (radial), ez (dorsal), from the arm
    chain J (shoulder, elbow, wrist, ...) and the knobs yaw, bend, dev."""
    W = np.asarray(J[2], float)
    f = W - np.asarray(J[1], float)
    f /= np.linalg.norm(f)
    sgn = 1.0 if side == 'left' else -1.0
    out = np.array([sgn, 0.0, 0.0])
    ez = out - (out @ f) * f
    ez /= np.linalg.norm(ez)
    # yaw: the back of the hand turns from her side toward the viewer (-y): about f, the sense that takes ez toward -y
    fwd = np.array([0.0, -1.0, 0.0])
    r = _rot(f, P['yaw'])
    if (r @ ez) @ fwd < (_rot(f, -P['yaw']) @ ez) @ fwd:
        r = _rot(f, -P['yaw'])
    ez = r @ ez
    ex = f
    ey = sgn * np.cross(ex, ez)                      # the thumb's side (left: ex x ez; mirrored on the right)
    # bend (flexion, toward the palm: -ez) about ey; dev (toward the little finger: -ey) about ez
    Rb = _rot(np.cross(ex, ez), P['bend'])          # (about the axis taking ex toward -ez for a positive bend)
    ex, ey, ez = Rb @ ex, Rb @ ey, Rb @ ez
    Rd = _rot(ez, -sgn * P['dev'])
    ex, ey, ez = Rd @ ex, Rd @ ey, Rd @ ez
    return W, np.stack([ex, ey, ez], 1)


def _turn(R, toward, deg):
    """a frame turned so its along axis moves toward `toward` (a unit vector across it) by deg degrees (either hand:
    the axis is along x toward, so the sense never depends on the frame's handedness)."""
    if not deg:
        return R
    return _rot(np.cross(R[:, 0], toward), deg) @ R


def _chain(base, R0, lengths, curls, spread_deg=0.0, out_deg=0.0, down_deg=0.0):
    """a digit's joints and per-segment frames: from base, first turned by spread and out (toward its radial side)
    and down (toward the palm), then each segment bent by its curl toward the palm -> (joints (4, 3), frames [R (3, 3):
    columns along, radial, dorsal] per segment)."""
    R = _turn(R0.copy(), R0[:, 1], spread_deg + out_deg)
    R = _turn(R, -R[:, 2], down_deg)
    pts, frames = [np.asarray(base, float)], []
    for L_, c in zip(lengths, curls):
        R = _turn(R, -R[:, 2], c)
        frames.append(R.copy())
        pts.append(pts[-1] + R[:, 0] * L_)
    return np.array(pts), frames


def digits(W, R, P):
    """every digit's joints and segment frames -> {name: (joints (4, 3), frames, widths (base, tip))}."""
    ex, ey, ez = R[:, 0], R[:, 1], R[:, 2]
    palm_len = P['length'] * P['palm']
    fl = P['length'] - palm_len
    out = {}
    for i, name in enumerate(FINGERS):
        base = W + ex * palm_len * (1 - KNUCKLE_ARC[i]) + ey * P['palm_w'] * ACROSS[i] + ez * 0.12 * P['palm_t']
        lens = [fl * P['fingers'][i] * s for s in PHALANGES]
        J, F = _chain(base, R, lens, [P['curl']] * 3, spread_deg=P['spread'] * (1.3 - i))
        w0 = P['finger_w'] * WIDTH[i]
        out[name] = (J, F, (w0, w0 * P['taper']))
    base = W + ex * P['thumb_base'] + ey * 0.42 * P['wrist_w'] - ez * 0.15 * P['palm_t']
    lens = [P['thumb_len'] * s for s in THUMB_BONES]
    J, F = _chain(base, R, lens, [0.0, P['curl'] * 0.6, P['curl'] * 0.6], out_deg=P['thumb_out'],
                  down_deg=P['thumb_down'])
    out['thumb'] = (J, F, (P['thumb_w'] * 1.15, P['thumb_w'] * P['taper']))
    return out


def _ellipse_ring(c, R, a, b, nth, n=2.0):
    """a ring round c in the plane of R's radial and dorsal columns: half-widths a (radial) and b (dorsal), a
    superellipse of exponent n -> (nth, 3)."""
    th = np.linspace(0, 2 * np.pi, nth, endpoint=False)
    s_, c_ = np.sin(th), np.cos(th)
    x = a * np.sign(c_) * np.abs(c_) ** (2.0 / n)
    y = b * np.sign(s_) * np.abs(s_) ** (2.0 / n)
    return c + np.outer(x, R[:, 1]) + np.outer(y, R[:, 2])


def digit_rings(J, F, widths, nth, bones, inset=INSET):
    """a digit's tube: rings along its chain (from inset behind its first joint, loops either side of each knuckle,
    a rounded tip) and each ring's weights on (the Hand, then its three bones) -> (rings (rows, nth, 3), W (rows, 4))."""
    seg = np.linalg.norm(np.diff(J, axis=0), axis=1)
    s0 = np.r_[0.0, np.cumsum(seg)]
    total = s0[-1]
    w0, w1 = widths
    rad = lambda s: 0.5 * (w0 + (w1 - w0) * np.clip(s / total, 0, 1))
    S = [-inset, -0.5 * inset]
    for k in range(3):
        a, b = s0[k], s0[k + 1]
        r = rad(a)
        S += [a - 0.45 * r, a, a + 0.45 * r] if k else [a - 0.3 * r, a, a + 0.45 * r]
        n_mid = max(1, int((b - a) / (1.6 * r)))
        S += list(np.linspace(a + 0.45 * r, b - 0.45 * r, n_mid + 2)[1:-1])
    rt = rad(total)
    tip = [total - rt * (1 - np.cos(t)) for t in np.radians((60, 35, 15))]
    S = sorted(set(np.round([s for s in S if s < total - rt] + tip, 6)))
    rings, Wt = [], []
    for s in S:
        k = int(np.clip(np.searchsorted(s0, s, side='right') - 1, 0, 2))
        Rk = F[k]
        if 0 < k and s - s0[k] < 0.45 * rad(s0[k]):          # a knuckle's loop: the bisector of its two segments
            Rk = _avg_frame(F[k - 1], F[k])
        elif k < 2 and s0[k + 1] - s < 0.45 * rad(s0[k + 1]):
            Rk = _avg_frame(F[k], F[k + 1])
        c = J[k] + F[k][:, 0] * (s - s0[k]) if s >= 0 else J[0] + F[0][:, 0] * s
        r = rad(max(s, 0.0))
        if s > total - rt:                                   # the tip's round: a quarter circle of the tip's radius
            q = (s - (total - rt)) / rt
            r = rt * max(np.sqrt(max(0.0, 1 - q * q)), 0.25)
        rings.append(_ellipse_ring(c, Rk, r, r * DEPTH, nth))
        Wt.append(_weights(s, s0, rad))
    return np.array(rings), np.array(Wt)


def _avg_frame(A, B):
    """two segment frames' mean, re-orthonormalised (a knuckle loop's plane)."""
    M = A + B
    x = M[:, 0] / np.linalg.norm(M[:, 0])
    z = M[:, 2] - (M[:, 2] @ x) * x
    z /= np.linalg.norm(z)
    return np.stack([x, np.cross(z, x), z], 1)


def _weights(s, s0, rad):
    """a ring's weights on (the Hand, bone 1, bone 2, bone 3) by its arc length s along its digit: each bone owns its
    segment, eased across each joint over JOINT_BLEND of the digit's radius there (the Hand behind the first joint)."""
    edges = s0[:3]
    w = np.zeros(4)
    for i in range(4):
        lo = -np.inf if i == 0 else edges[i - 1]
        hi = np.inf if i == 3 else edges[i]
        a = 1.0 if not np.isfinite(lo) else np.clip((s - lo) / (2 * JOINT_BLEND * rad(lo)) + 0.5, 0, 1)
        b = 1.0 if not np.isfinite(hi) else np.clip((hi - s) / (2 * JOINT_BLEND * rad(hi)) + 0.5, 0, 1)
        w[i] = min(a, b)
    return w / max(w.sum(), 1e-9)


def palm_rings(W, R, P, nth=NTH['palm']):
    """the palm: a rounded box from inside the cuff to past the knuckles, its width easing from the wrist's to the
    knuckles', its far end rounded -> (rings (rows, nth, 3), W (rows, 4): all the Hand's)."""
    ex = R[:, 0]
    pl = P['length'] * P['palm']
    X = np.r_[np.linspace(-0.06, pl * 0.85, 9), pl * np.array([0.93, 0.99, 1.03, 1.06])]
    rings = []
    for x in X:
        u = np.clip(x / (0.7 * pl), 0, 1)
        e = u * u * (3 - 2 * u)
        a = 0.5 * (P['wrist_w'] + (P['palm_w'] - P['wrist_w']) * e)
        b = 0.5 * P['palm_t'] * (0.95 + 0.1 * e)
        if x > pl * 0.88:                                    # the far end's round, over the knuckles
            q = min(1.0, (x - pl * 0.88) / (pl * 0.2))
            k = np.sqrt(max(0.0, 1 - q * q))
            a, b = a * max(k, 0.55), b * max(k, 0.4)
        rings.append(_ellipse_ring(W + ex * x, R, a, b, nth, n=2.6))
    Wt = np.tile([1.0, 0.0, 0.0, 0.0], (len(X), 1))
    return np.array(rings), Wt


def hand(J, side, P):
    """a hand at the arm chain's wrist -> dict(parts {name: (rings, W, bones)}, joints {MakeHuman name: point},
    frame (W, R))."""
    W, R = frame(J, side, P)
    S_ = 'Left' if side == 'left' else 'Right'
    s_ = side
    D = digits(W, R, P)
    parts = {'palm': palm_rings(W, R, P) + ([s_ + 'Hand'] * 4,)}
    joints = {}
    for name in ('thumb',) + FINGERS:
        Jd, F, widths = D[name]
        segs = SEGS.get(name, ('Proximal', 'Intermediate', 'Distal'))
        bones = [s_ + 'Hand'] + ['%s%s%s' % (s_, VRM[name], g) for g in segs]
        rings, Wt = digit_rings(Jd, F, widths, NTH['thumb' if name == 'thumb' else 'finger'], bones)
        parts[name] = (rings, Wt, bones)
        k = MH[name]
        L_ = 'L' if side == 'left' else 'R'
        for seg in range(3):
            joints['finger%d-%d.%s____head' % (k, seg + 1, L_)] = Jd[seg]
            joints['finger%d-%d.%s____tail' % (k, seg + 1, L_)] = Jd[seg + 1]
    return dict(parts=parts, joints=joints, frame=(W, R), digits=D)


def tube_mesh(rings):
    """rings (rows, nth, 3) -> (V, T) triangles, both ends capped (code_body._tube)."""
    from .code_body import _tube
    return _tube(rings, rings.shape[1])


def mesh(H_):
    """a hand's parts as one triangle mesh -> (V, T, part index per triangle)."""
    Vs, Ts, Ls, n = [], [], [], 0
    for i, name in enumerate(PARTS):
        V, T = tube_mesh(H_['parts'][name][0])
        Vs.append(V)
        Ts.append(T + n)
        Ls.append(np.full(len(T), i))
        n += len(V)
    return np.concatenate(Vs), np.concatenate(Ts), np.concatenate(Ls)


# ------------------------------------------------------------------------------------------------------------ the fit
def cuff_end(H, side, J, spec=None):
    """our wrist cuff's far edge along the forearm, L from the wrist joint: the spec's band on the lower arm (its
    middle at t along the bone, `width` L wide: garments.band), else the hull's cuff's (its points' 98th percentile)."""
    f = np.asarray(J[2], float) - np.asarray(J[1], float)
    n = np.linalg.norm(f)
    f /= n
    bone = side + 'LowerArm'
    for g in (spec or {}).get('garments') or []:
        if g.get('kind') == 'band' and g.get('bone') == bone:
            return float((g.get('t', 0.5) - 1.0) * n + 0.5 * g.get('width', 0.08))
    C = H.points('cuff_' + ('L' if side == 'left' else 'R'))
    return float(np.percentile((C - J[2]) @ f, 98)) if len(C) else 0.06


class Fit:
    """the hand's knobs against the design's drawn hands: per view and side, the hand-check measures (handqa's
    shape IoU laid on the centroids, reach past the cuff) of the template rendered with the QA's projection (the
    hull's frame: the design's grids), the part past the cuff's far edge standing for what shows past our cuff."""

    def __init__(self, B, design, spec, hull_dir, graph_path):
        from . import bodymeasure, handqa
        from .bodyqa import CLASS
        from .code_body import Hull, limb_joints, skeleton
        self.ctx = design.sheet_context()
        self.ppl, self.az3 = self.ctx['ppl'], self.ctx['az3']
        masks, graph, _ = bodymeasure.piece_masks(B.spec)
        dv = design.design_views()
        self.H = Hull(hull_dir)
        sk = skeleton(json.load(open(graph_path)))
        self.J = {s: limb_joints(self.H, sk, s, 'arm') for s in ('left', 'right')}
        self.cuff = {s: cuff_end(self.H, s, self.J[s], spec) for s in ('left', 'right')}
        self.drawn = {}
        for v in handqa.VIEWS:
            cls, fg = dv[v]['cls'], dv[v]['fg']
            for s in handqa.sides(v):
                m = masks.get('%s__cuff_%s' % (v, s))
                if m is None:
                    continue
                h = handqa.hand_mask(fg & (cls == CLASS['skin']), m[:cls.shape[0], :cls.shape[1]], self.ppl)
                if h is not None:
                    self.drawn[(v, s)] = dict(mask=h['mask'], reach=handqa.reach(h, self.ppl), u=h['u'])
        self.base = params(spec)

    def silhouettes(self, P, side):
        """the template's part past the cuff per view -> {view: (mask, reach L past the cuff along the drawn arm, the
        forearm's direction in the view (x, y))}."""
        from . import bodyqa, handqa
        from .faceqa import zbuffer, view as proj
        J = self.J[side]
        H_ = hand(J, side, P)
        V, T, _ = mesh(H_)
        f = J[2] - J[1]
        f = f / np.linalg.norm(f)
        keep = ((V[T].mean(1) - J[2]) @ f) > self.cuff[side]
        T = T[keep]
        eyes = np.asarray(self.H.eyes, float)
        az = bodyqa.azimuths(self.az3)
        out = {}
        S = 'L' if side == 'left' else 'R'
        for (v, s), d in self.drawn.items():
            if s != S:
                continue
            org = bodyqa.origin(v, az[v], eyes, (0.0, 0.0, 0.0))
            _, lab = zbuffer([(V, T, np.zeros(len(T), int))], az[v], org, 1.0, 1.0 / self.ppl, bodyqa.WIN)
            m = lab >= 0
            # the reach past the cuff along the drawn arm's direction in this view: the cuff plane's point projected
            u, z, _ = proj((J[2] + f * self.cuff[side])[None], az[v])
            cx = (u[0] - org[0] + bodyqa.WIN['x']) * self.ppl
            cy = (bodyqa.WIN['top'] - (z[0] - org[1])) * self.ppl
            ys, xs = np.nonzero(m)
            r = float(np.percentile((xs - cx) * d['u'][0] + (ys - cy) * d['u'][1], 99.5)) / self.ppl if len(ys) else 0.0
            u2, z2, _ = proj(np.array([J[1], J[2]]), az[v])                # the forearm's direction in the view
            uf = np.array([u2[1] - u2[0], -(z2[1] - z2[0])])
            out[v] = (m, r, uf / max(np.linalg.norm(uf), 1e-9))
        return out

    def score(self, P):
        """-> (cost, per hand {key: (iou, reach error)}): 1 - IoU plus the reach error over 0.1 L, the mean over hands."""
        from . import handqa
        per, costs = {}, []
        for side in ('left', 'right'):
            got = self.silhouettes(P, side)
            S = 'L' if side == 'left' else 'R'
            for v, (m, r, uf) in got.items():
                d = self.drawn[(v, S)]
                iou = handqa.shape_iou(d['mask'], m, d['u'], uf) if m.any() else 0.0
                per['%s_%s' % (v, S)] = (round(iou, 4), round(r - d['reach'], 4))
                costs.append((1 - iou) + abs(r - d['reach']) / 0.1)
        return float(np.mean(costs)), per

    def run(self, knobs=FIT_KNOBS, rounds=3, log=print):
        """Powell's method over the knobs within BOUNDS (scaled to their ranges), then a coordinate search at a fine step
        -> (P, cost, per)."""
        from scipy.optimize import minimize
        P0 = dict(self.base)
        lo = np.array([BOUNDS[k][0] for k in knobs])
        hi = np.array([BOUNDS[k][1] for k in knobs])
        x0 = (np.clip([P0[k] for k in knobs], lo, hi) - lo) / (hi - lo)
        best = {'c': np.inf}

        def f(x):
            P = dict(P0)
            P.update({k: float(lo[i] + (hi[i] - lo[i]) * np.clip(x[i], 0, 1)) for i, k in enumerate(knobs)})
            c, per = self.score(P)
            if c < best['c']:
                best.update(c=c, P=P, per=per)
            return c
        c0 = f(x0)
        log('start %.4f %s' % (c0, best['per']))
        for r in range(rounds):
            res = minimize(f, x0 if r == 0 else (np.array([best['P'][k] for k in knobs]) - lo) / (hi - lo),
                           method='Powell', bounds=[(0, 1)] * len(knobs),
                           options=dict(xtol=0.01, ftol=1e-4, maxfev=400))
            log('round %d %.4f (%d evaluations) %s' % (r, best['c'], res.nfev,
                                                        {k: round(best['P'][k], 4) for k in knobs}))
        return best['P'], best['c'], best['per']


def main(args):
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    if not args or args[0] != 'fit':
        print(__doc__)
        return 0
    from . import bundle, manifest, qa3d
    build = opt('--build')
    B = bundle.load(os.path.join(build, 'bundle'))
    D = qa3d.Design(B)
    spec_path = opt('--write') or opt('--spec') or os.path.join(ROOT, 'charkit', 'spec', 'clawd.json')
    spec = json.load(open(spec_path))
    hull = manifest.produced(B.spec, 'hull')
    masks = manifest.produced(B.spec, 'outfit_masks')
    F = Fit(B, D, spec, os.path.dirname(hull), os.path.join(os.path.dirname(masks), 'outfit_graph.json'))
    P, c, per = F.run(rounds=int(opt('--rounds', 3)))
    print(json.dumps(dict(cost=round(c, 4), per=per, knobs={k: (round(v, 4) if isinstance(v, float) else v)
                                                              for k, v in P.items()}), indent=1))
    if opt('--write'):
        spec.setdefault('body', {})['hand'] = {k: (round(P[k], 4) if isinstance(P[k], float) else list(P[k]))
                                               for k in P}
        json.dump(spec, open(spec_path, 'w'), indent=1)
        print('wrote body.hand into %s' % spec_path)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))


# ------------------------------------------------------------------------------------------------- the weights posed
def curl_pose(H_, curl=80.0, thumb=40.0):
    """a fist's skinning, numpy only: every finger joint bent `curl` degrees toward the palm (the thumb's joints
    `thumb`), each part's rings moved by linear blend skinning with its own weights -> {part: posed rings}. The
    weights' check before a rig holds them: the bend happens at the knuckles' loops and nowhere else."""
    W0, R = H_['frame']
    out = {}
    for name in PARTS:
        rings, Wt, bones = H_['parts'][name]
        if name == 'palm':
            out[name] = rings
            continue
        Jd, F, _ = H_['digits'][name]
        deg = thumb if name == 'thumb' else curl
        T = [(np.eye(3), np.zeros(3))]                       # the Hand: rest
        Racc, tacc = np.eye(3), np.zeros(3)
        for k in range(3):
            axis = np.cross(F[k][:, 0], -F[k][:, 2])          # bends along toward the palm
            Rk = _rot(axis, deg if (name != 'thumb' or k) else 0.0)
            p = Racc @ Jd[k] + tacc                           # the joint where the chain so far has put it
            Racc, tacc = Rk @ Racc, Rk @ (tacc - p) + p
            T.append((Racc.copy(), tacc.copy()))
        P = rings.reshape(-1, 3)
        Wv = np.repeat(Wt, rings.shape[1], axis=0)
        Q = sum(Wv[:, i:i + 1] * (P @ T[i][0].T + T[i][1]) for i in range(4))
        out[name] = Q.reshape(rings.shape)
    return out


def ring_area(ring):
    """a ring's area on its best-fit plane."""
    c = ring.mean(0)
    _, _, Vt = np.linalg.svd(ring - c)
    xy = (ring - c) @ Vt[:2].T
    x, y = xy[:, 0], xy[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def fist_report(H_, curl=80.0, thumb=40.0):
    """the fist's numbers: per finger the knuckle loops' smallest area over its rest area (the volume kept at the
    bends), and the interpenetration between neighbouring fingers (each posed ring's points inside the neighbour's
    posed tube: their share, and the deepest, L) -> dict."""
    from scipy.spatial import cKDTree
    posed = curl_pose(H_, curl, thumb)
    rep = {'curl': curl, 'thumb': thumb, 'knuckle_area': {}, 'overlap': {}}
    for name in FINGERS + ('thumb',):
        rest, now = H_['parts'][name][0], posed[name]
        ratios = [ring_area(now[i]) / max(ring_area(rest[i]), 1e-12) for i in range(len(rest))]
        rep['knuckle_area'][name] = round(float(min(ratios)), 3)
    for a, b in zip(FINGERS[:-1], FINGERS[1:]):
        A, Bp = posed[a], posed[b]
        cb, rb = Bp.mean(1), np.linalg.norm(Bp - Bp.mean(1)[:, None], axis=2).mean(1)
        tree = cKDTree(cb)
        P = A.reshape(-1, 3)
        d, i = tree.query(P)
        depth = rb[i] - np.linalg.norm(P - cb[i], axis=1)
        inside = depth > 0
        rep['overlap']['%s/%s' % (a, b)] = dict(share=round(float(inside.mean()), 3),
                                                deepest=round(float(depth.max()), 4))
    return rep
