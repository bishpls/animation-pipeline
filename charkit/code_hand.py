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
    palm_w=0.15,          # L: the palm's width across the knuckles (the fingers' span there: they tile it)
    wrist_w=0.11,         # L: its width at the wrist (the drawn hands narrow to the wrist: 0.66-0.84 of their widest)
    palm_t=0.07,          # L: its thickness
    taper=0.6,            # a finger's width at its tip over its knuckle's
    overlap=0.12,         # the share of a finger's width its neighbour overlaps (fingers held together: the drawn
                          # relaxed hand shows no background between them, 0-0.01 of its span at the tips)
    tip_gap=None,         # L: the fingertips this far apart (None: overlapping as at the knuckles). A gap narrower than
                          # the hand's line is filled by the neighbours' outline hulls: a drawn hairline between the
                          # fingers from where they part to the tips (the design's 2-3 lines; round 6's seam gap)
    fingers=(0.93, 1.0, 0.95, 0.78),    # index, middle, ring, little: lengths over the middle's
    spread=0.0,           # degrees each finger fans out from the middle's line beyond the touching layout (- closer)
    palm_len=None,        # L: the ratio mode's size (from_ratios: the reference's wrist line to the middle MCP); None: the
                          # geometric knobs as given
    wrist_offset=0.0,     # L: the reference's wrist line past the wrist joint (Clawd: the cuff's edge hides the crease)
    ratios=None,          # the hand's structural ratios over the style profile's prior (hand_ratios)
    segments=None, thumb_segments=None,    # a digit's segments (proximal : middle : distal), None: PHALANGES/THUMB_BONES
    fan_index=0.0, fan_middle=0.0, fan_ring=0.0, fan_little=0.0,   # degrees each finger turns toward the thumb's side
                          # beyond that (the sheet's open hand: index +14, ring -16, little -34 about the middle)
    curl=6.0,             # degrees each finger joint bends toward the palm at rest (the drawn relaxed hand)
    thumb_len=0.27,       # L: the thumb from its CMC to its tip
    thumb_w=0.05,         # L: its width at its MCP
    thumb_out=20.0,       # degrees the thumb opens from the hand's axis toward its side (radial; the drawn V cleft)
    thumb_down=15.0,      # degrees it turns toward the palm (opposition)
    thumb_base=0.06,      # L: its CMC from the wrist along the hand
    thumb_across=0.3,     # its CMC across the palm toward the thumb's side, over the wrist's width
    yaw=40.0,             # degrees the back of the hand turns from her side toward the viewer, about the forearm
    bend=0.0,             # degrees the hand bends at the wrist toward the palm (flexion; - extension)
    dev=0.0,              # degrees it bends toward the little finger's side (ulnar deviation; - radial)
    out=0.0,              # degrees the hand turns away from her side in her frontal plane (about the forward axis)
    line=1.0,             # the hand's outline width over the skin's (charkit.character.outline_weights): the drawn
                          # hands' finer line (their fill share, charkit/out/hands/ink.py)
)
# (rest orientation A, Michael 2026-09-30: yaw and out stay the joint fit's; tool/hands2 refits the shape only)
FIT_KNOBS = ('length', 'palm', 'palm_w', 'wrist_w', 'palm_t', 'taper', 'overlap', 'spread', 'curl', 'bend', 'dev',
             'thumb_base', 'thumb_len', 'thumb_w', 'thumb_out', 'thumb_down')
BOUNDS = dict(length=(0.45, 0.85), palm=(0.38, 0.56), palm_w=(0.09, 0.30), wrist_w=(0.07, 0.18),
              palm_t=(0.04, 0.085), taper=(0.35, 0.9), overlap=(-0.1, 0.35), spread=(-4.0, 8.0), curl=(-15.0, 30.0),
              thumb_len=(0.16, 0.46), thumb_w=(0.03, 0.085), thumb_out=(0.0, 60.0), thumb_down=(0.0, 60.0),
              thumb_base=(0.0, 0.16), yaw=(-60.0, 110.0), bend=(-20.0, 20.0), dev=(-20.0, 20.0),
              fan_index=(-10.0, 30.0), fan_middle=(-15.0, 15.0), fan_ring=(-30.0, 10.0), fan_little=(-50.0, 10.0),
              thumb_across=(0.0, 0.6), tip_gap=(-0.01, 0.01), palm_len=(0.15, 0.4))
FINGERS = ('index', 'middle', 'ring', 'little')
PHALANGES = (0.45, 0.3, 0.25)         # a finger's proximal, intermediate and distal shares of its length
THUMB_BONES = (0.36, 0.36, 0.28)      # the thumb's metacarpal, proximal and distal shares
WIDTH = (1.0, 1.03, 0.96, 0.84)       # index .. little: width over the middle's
KNUCKLE_ARC = (0.035, 0.0, 0.03, 0.09)  # index .. little: the knuckle's setback from the middle's, over the palm's length
DEPTH = 0.86                          # a finger's section: its dorsal-palmar depth over its width
JOINT_BLEND = 0.8                     # a finger's weight eases across a knuckle over this share of its radius each side
INSET = 0.04                          # L: a finger's tube starts this far inside the palm, behind its knuckle
NTH = dict(palm=20, thumb=10, finger=10)
SEAM_MAX = 0.005                      # L: a gap between touching fingers this narrow or less is a seam: the outline's hulls
                                      # (~0.012 L a side at line 1) fill it with ink, a hairline (the QA's labels: < 1 px)
WRIST_KEEP = 0.0                      # L: the arm's tube keeps its rows up to this past the wrist (under the cuff; the palm
                                      # starts 0.06 behind the wrist, inside it)
UV_BAND = (0.25, 0.1, 0.5, 0.2)       # the hands' UV slots: this band (under the legs' slots, beside the feet's) in 12
PARTS = ('palm', 'thumb') + FINGERS
VRM = {'thumb': 'Thumb', 'index': 'Index', 'middle': 'Middle', 'ring': 'Ring', 'little': 'Little'}
SEGS = {'thumb': ('Metacarpal', 'Proximal', 'Distal')}
MH = {'thumb': 1, 'index': 2, 'middle': 3, 'ring': 4, 'little': 5}


RATIO_KEYS = ('span', 'wrist', 'thick', 'middle', 'index', 'ring', 'little', 'segments', 'taper', 'thumb_cmc', 'thumb',
              'thumb_segments', 'thumb_w')


def ratio_prior(style='anime'):
    """the style profile's hand prior: {ratio: [default, lo, hi]} (charkit/styles: 'hand')."""
    from . import styles
    return {k: v for k, v in styles.load(style).get('hand', {}).items() if not k.startswith('_')}


def hand_ratios(spec=None, style=None):
    """the hand's structural ratios: the style profile's defaults, the spec's body.hand.ratios over them (an open hand's
    landmarks: charkit.handsheet.sheet_ratios) -> {ratio: value}."""
    style = style or (spec or {}).get('style') or 'anime'
    pr = ratio_prior(style)
    R = {k: (list(v) if k.endswith('segments') else v[0]) for k, v in pr.items()}   # (a segments' prior: the triple)
    R.update((((spec or {}).get('body') or {}).get('hand') or {}).get('ratios') or {})
    return R


def from_ratios(R, palm_len, wrist_offset=0.0):
    """the template's knobs from the hand's structural ratios (Michael, 2026-10-01: fixed ratios, poses only rotate
    joints): R {ratio: value} (hand_ratios), palm_len (L: the reference's wrist line to the middle finger's MCP: the
    size), wrist_offset (L: the reference's wrist line past the wrist joint: Clawd's is the cuff's edge, which hides the
    wrist crease) -> {knob: value} over DEFAULT's (length, palm, palm_w, wrist_w, palm_t, taper, fingers, segments,
    thumb_base, thumb_len, thumb_w, thumb_segments)."""
    PL = float(palm_len)
    mcp = wrist_offset + PL
    span = R['span'] * PL
    length = mcp + R['middle'] * PL
    return dict(length=length, palm=mcp / length, palm_w=span, wrist_w=R['wrist'] * span, palm_t=R['thick'] * span,
                taper=R['taper'], fingers=(R['index'], 1.0, R['ring'], R['little']), segments=list(R['segments']),
                thumb_base=wrist_offset + R['thumb_cmc'] * PL, thumb_len=R['thumb'] * PL, thumb_w=R['thumb_w'] * PL,
                thumb_segments=list(R['thumb_segments']))


def params(spec=None, **over):
    """the hand's knobs: DEFAULT, the spec's body.hand over it, then over; with body.hand.palm_len (the ratio mode:
    the hand built from its structural ratios, from_ratios) the geometric knobs derived from hand_ratios(spec) at that
    size (and over's own palm_len / ratios)."""
    P = dict(DEFAULT)
    P.update(((spec or {}).get('body') or {}).get('hand') or {})
    P.update(over)
    if P.get('palm_len') is not None:
        R = hand_ratios(spec)
        R.update(P.get('ratios') or {})
        P['ratios'] = R                                # (the full set: geometry() derives the knobs from it, live)
        P = geometry(P)
    P['fingers'] = tuple(P['fingers'])
    return P


def geometry(P):
    """the knobs a hand is built from: in the ratio mode (palm_len set) the geometric knobs derived from P['ratios'] at
    P['palm_len'] (from_ratios), so a fit moving palm_len or a ratio moves the hand (ratio2 moved palm_len to its bound
    with no effect: the knobs had been derived once); else P as it is."""
    if P.get('palm_len') is None or not P.get('ratios'):
        return P
    Q = dict(P)
    Q.update(from_ratios(P['ratios'], P['palm_len'], P.get('wrist_offset', 0.0)))
    Q['fingers'] = tuple(Q['fingers'])
    return Q


def _shares(seg, default):
    """a digit's segment lengths as shares of its length: the ratios' triple (proximal : middle : distal) normalised,
    else the default shares."""
    if not seg:
        return default
    t = float(sum(seg))
    return tuple(float(x) / t for x in seg)


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
    # out: the whole hand turned away from her side in her frontal plane (about the forward axis at the wrist): the
    # drawn hands flare out past the forearm's line (front and back: 4-6 degrees more than their forearms)
    Ro = _rot(np.array([0.0, -sgn, 0.0]), P.get('out', 0.0))
    ex, ey, ez = Ro @ ex, Ro @ ey, Ro @ ez
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


def layout(P):
    """the fingers held together (round 4, tool/hands2: de2fa87's four thin tubes fanned apart read as a comb): their
    widths tiling the knuckle line (palm_w, neighbours overlapping by `overlap` of their width), and their tips laid
    the same way at their tapered widths about the middle finger's, so each finger runs from its knuckle to its tip
    beside its neighbours and the hand converges on the middle fingertip -> (widths at the knuckles, across at the
    knuckles, across at the tips; radial +, L, from the hand's axis), each (4,)."""
    o = P['overlap']
    Wd = np.asarray(WIDTH, float)
    pitch = lambda w: 0.5 * (w[:-1] + w[1:]) * (1 - o)          # neighbouring centres' distances
    unit = 0.5 * (Wd[0] + Wd[-1]) + pitch(Wd).sum()
    w0 = Wd * P['palm_w'] / unit                                 # the outer edges span the palm's knuckle width
    c0 = np.r_[0.0, -np.cumsum(pitch(w0))]                       # index .. little, radial +
    c0 -=0.5 * ((c0[0] + 0.5 * w0[0]) + (c0[-1] - 0.5 * w0[-1]))  # the span centred on the hand's axis
    w1 = w0 * P['taper']
    g = P.get('tip_gap')
    c1 = np.r_[0.0, -np.cumsum(pitch(w1) if g is None else 0.5 * (w1[:-1] + w1[1:]) + g)]
    c1 += c0[1] - c1[1]                                          # about the middle finger's line
    return w0, c0, c1


def digits(W, R, P):
    """every digit's joints and segment frames -> {name: (joints (4, 3), frames, widths (base, tip))}."""
    ex, ey, ez = R[:, 0], R[:, 1], R[:, 2]
    palm_len = P['length'] * P['palm']
    fl = P['length'] - palm_len
    w0, c0, c1 = layout(P)
    out = {}
    for i, name in enumerate(FINGERS):
        base = W + ex * palm_len * (1 - KNUCKLE_ARC[i]) + ey * c0[i] + ez * 0.12 * P['palm_t']
        lens = [fl * P['fingers'][i] * s for s in _shares(P.get('segments'), PHALANGES)]
        # toward its tip's place beside its neighbours (the tips converge on the middle's), plus the spread's fan
        conv = np.degrees(np.arctan2(c1[i] - c0[i], sum(lens)))
        fan = P.get('fan_' + name, 0.0)
        J, F = _chain(base, R, lens, [P['curl']] * 3, spread_deg=conv + P['spread'] * (1 - i) + fan)
        out[name] = (J, F, (w0[i], w0[i] * P['taper']))
    # the thumb: from its CMC inside the palm's radial edge near the wrist, opened out (radial) and toward the palm
    base = W + ex * P['thumb_base'] + ey * P.get('thumb_across', 0.3) * P['wrist_w'] - ez * 0.15 * P['palm_t']
    lens = [P['thumb_len'] * s for s in _shares(P.get('thumb_segments'), THUMB_BONES)]
    J, F = _chain(base, R, lens, [0.0, P['curl'] * 0.6, P['curl'] * 0.6], out_deg=P['thumb_out'],
                  down_deg=P['thumb_down'])
    out['thumb'] = (J, F, (P['thumb_w'] * 1.15, P['thumb_w'] * max(P['taper'], 0.7)))
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
    """two segment frames' mean, re-orthonormalised (a knuckle loop's plane), of their handedness (the left hand's
    frames are mirrored: a right-handed loop between them turned its ring the other way round, and the tube folded
    over itself at every knuckle, b1's knobs)."""
    M = A + B
    x = M[:, 0] / np.linalg.norm(M[:, 0])
    z = M[:, 2] - (M[:, 2] @ x) * x
    z /= np.linalg.norm(z)
    y = np.cross(z, x) * np.sign(np.linalg.det(A))
    return np.stack([x, y, z], 1)


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
    P = geometry(P)
    W, R = frame(J, side, P)
    s_ = side
    D = digits(W, R, P)
    # the right hand's frame is mirrored (ey = -(ex x ez)), which turns its rings the other way round: reversed there,
    # so every part's faces point out on both hands (b1 rendered the right hand inside out: its outline hull went
    # inside the skin, no line, the shading flipped)
    o = (lambda r: r[:, ::-1]) if side == 'right' else (lambda r: r)
    rp, wp = palm_rings(W, R, P)
    parts = {'palm': (o(rp), wp, [s_ + 'Hand'] * 4)}
    joints = {}
    for name in ('thumb',) + FINGERS:
        Jd, F, widths = D[name]
        segs = SEGS.get(name, ('Proximal', 'Intermediate', 'Distal'))
        bones = [s_ + 'Hand'] + ['%s%s%s' % (s_, VRM[name], g) for g in segs]
        rings, Wt = digit_rings(Jd, F, widths, NTH['thumb' if name == 'thumb' else 'finger'], bones)
        parts[name] = (o(rings), Wt, bones)
        k = MH[name]
        L_ = 'L' if side == 'left' else 'R'
        for seg in range(3):
            joints['finger%d-%d.%s____head' % (k, seg + 1, L_)] = Jd[seg]
            joints['finger%d-%d.%s____tail' % (k, seg + 1, L_)] = Jd[seg + 1]
    return dict(parts=parts, joints=joints, frame=(W, R), digits=D, side=side)


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
            if 'span' in g and 't' not in g:                  # the cuff template (garments.cuff): span L from the elbow
                return float(g['span'][1] - n)
            return float((g.get('t', 0.5) - 1.0) * n + 0.5 * g.get('width', 0.08))
    C = H.points('cuff_' + ('L' if side == 'left' else 'R'))
    return float(np.percentile((C - J[2]) @ f, 98)) if len(C) else 0.06


STRUCT = 0.1     # the fit's weight on each structure measure at its PASS limit (beside 1 - IoU and the reach / 0.1 L)
STRUCT_CAP = 3.0 # a structure term's units are capped here (a FAIL either way; the deepest pocket can jump from one
                 # pocket to another as a knob moves, and an uncapped jump steers the search)
FLOOR_W = 5.0    # the cost of each IoU point under a view's floor (Fit.floors: the guard's intent inside the fit)
FAIL_COST = 2.0  # the cost of a graded structure term past its WARN limit (a FAIL: the gate's 'no new FAIL' inside the
                 # fit; rest1 folded the thumb in for IoU and lost the three-quarter's cleft, 0.16 vs 0.62)


class Fit:
    """the hand's knobs against the design's drawn hands: per view and side, the hand-check measures (handqa's
    shape IoU laid on the centroids, reach past the cuff; and since round 4 the structure inside the silhouette the IoU
    can't see: the fingertips' gaps, the taper to the fingertips, where the thumb's cleft lies, the wrist's narrowing)
    of the template rendered with the QA's projection (the hull's frame: the design's grids), the part past the cuff's
    far edge standing for what shows past our cuff."""

    def __init__(self, B, design, spec, hull_dir, graph_path):
        from . import bodymeasure, handqa
        from .bodyqa import CLASS
        from .code_body import Hull, limb_joints, pose_arm, skeleton
        self.ctx = design.sheet_context()
        self.design = design
        self.ppl, self.az3 = self.ctx['ppl'], self.ctx['az3']
        masks, graph, _ = bodymeasure.piece_masks(B.spec)
        dv = design.design_views()
        self.H = Hull(hull_dir)
        sk = skeleton(json.load(open(graph_path)))
        arm = (spec.get('body') or {}).get('arm')            # (the build's chain: posed as code_body.limb poses it)
        self.J = {s: pose_arm(limb_joints(self.H, sk, s, 'arm'), s, arm) for s in ('left', 'right')}
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
                    self.drawn[(v, s)] = dict(mask=h['mask'], reach=handqa.reach(h, self.ppl), u=h['u'], c=h['c'],
                                              end=h['end'],
                                              W=handqa.bands_across(h, self.ppl, handqa.PROFILE_BANDS)[0],
                                              **self.structure(h))
        self.base = params(spec)
        self.floors = None          # {view_side: IoU}: each view's shape IoU kept at least this (FLOOR_W per point under)

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
            uf = uf / max(np.linalg.norm(uf), 1e-9)
            out[v] = (m, r, uf, np.array([cx, cy]))
        return out

    def structure(self, h):
        """handqa's structure measures of one hand (h: hand_mask's dict) -> dict(gaps, taper, cleft, cleft_at, wrist)."""
        from . import handqa
        cd, _ = handqa.cleft(h['mask'], self.ppl)
        return dict(gaps=handqa.gaps(h, self.ppl), taper=handqa.taper(h, self.ppl), cleft=cd,
                    cleft_at=handqa.cleft_at(h['mask'], h, self.ppl), wrist=handqa.wrist(h, self.ppl))

    def terms(self, d, f, view, side):
        """one hand's structure against the drawn, each over its check's PASS limit (handqa.LIMITS; the wrist, not
        graded, over 0.1), where the check grades it -> {name: (ours, design, cost units)}."""
        from . import handqa
        T = {}
        for k in ('gaps', 'taper'):
            if (view, side) in handqa.EDGE_ON.get(k, {}):
                continue
            x = f[k] - d[k]
            T[k] = (f[k], d[k], (max(x, 0.0) if k == 'gaps' else abs(x)) / handqa.LIMITS[k][0])
        if d['cleft'] >= handqa.CLEFT_MIN:
            T['cleftpos'] = (f['cleft_at'], d['cleft_at'], 2.0 if f['cleft_at'] is None or d['cleft_at'] is None else
                             abs(f['cleft_at'] - d['cleft_at']) / handqa.LIMITS['cleftpos'][0])
        T['wrist'] = (f['wrist'], d['wrist'], abs(f['wrist'] - d['wrist']) / 0.1)
        return T

    def score(self, P, structure=True, detail=False):
        """-> (cost, per hand {key: (iou, reach error)}): 1 - IoU plus the reach error over 0.1 L plus STRUCT times each
        structure term (terms()), the mean over hands and views. detail: per {key: dict(iou, reach, terms)}."""
        from . import handqa
        per, costs, full = {}, [], {}
        for side in ('left', 'right'):
            got = self.silhouettes(P, side)
            S = 'L' if side == 'left' else 'R'
            for v, (m, r, uf, c) in got.items():
                d = self.drawn[(v, S)]
                iou = handqa.shape_iou(d['mask'], m, d['u'], uf) if m.any() else 0.0
                per['%s_%s' % (v, S)] = (round(iou, 4), round(r - d['reach'], 4))
                cost = (1 - iou) + abs(r - d['reach']) / 0.1
                fl = (self.floors or {}).get('%s_%s' % (v, S))
                if fl is not None:
                    cost += FLOOR_W * max(0.0, fl - iou)
                if structure or detail:
                    T = self.terms(d, self.structure(dict(mask=m, c=c, u=uf, end=0.0)), v, S) if m.sum() > 50 else {}
                    if structure:
                        cost += STRUCT * sum(min(t[2], STRUCT_CAP) for t in T.values())
                        cost += FAIL_COST * sum(1 for k, t in T.items()
                                                if k in handqa.LIMITS and t[2] * handqa.LIMITS[k][0] > _warn(k))
                    full['%s_%s' % (v, S)] = dict(iou=round(iou, 4), reach=round(r - d['reach'], 4),
                                                  terms={k: (None if a is None else round(a, 3),
                                                             None if b is None else round(b, 3), round(u, 2))
                                                         for k, (a, b, u) in T.items()})
                costs.append(cost)
        if detail:
            return float(np.mean(costs)), full
        return float(np.mean(costs)), per

    def run(self, knobs=FIT_KNOBS, rounds=3, log=print, method='powell', workers=1, seed=0, maxiter=40, popsize=12,
            maxfev=400):
        """search() over the knobs from the spec's -> (P, cost, per)."""
        return search(self, knobs, rounds=rounds, log=log, method=method, workers=workers, seed=seed, maxiter=maxiter,
                      popsize=popsize, maxfev=maxfev)


def bounds_of(k):
    """a knob's bounds: KNOB_BOUNDS, or a prefixed knob's ('open.curl': curl's)."""
    return KNOB_BOUNDS[k] if k in KNOB_BOUNDS else KNOB_BOUNDS[k.split('.', 1)[1]]


def get_knob(P, k):
    """a knob's value; 'fingers.I' is the I-th of the fingers' lengths; a prefixed knob ('open.curl') its own key, else
    the unprefixed one's."""
    if '.' in k and not k.startswith('fingers.'):
        return P.get(k, P.get(k.split('.', 1)[1]))
    if k.startswith('fingers.'):
        return P['fingers'][int(k.split('.')[1])]
    return P[k]


def set_knob(P, k, v):
    """P with knob k set (a copy of the fingers' tuple for 'fingers.I')."""
    if k.startswith('fingers.'):
        f = list(P['fingers'])
        f[int(k.split('.')[1])] = v
        P['fingers'] = tuple(f)
    else:
        P[k] = v
    return P


KNOB_BOUNDS = dict(BOUNDS, **{'fingers.0': (0.75, 1.05), 'fingers.2': (0.75, 1.05), 'fingers.3': (0.6, 0.95),
                              'view_turn_side': (-50.0, 50.0), 'view_turn_back': (-30.0, 30.0)})


def _to_P(P0, knobs, lo, hi, x):
    P = dict(P0)
    for i, k in enumerate(knobs):
        set_knob(P, k, float(lo[i] + (hi[i] - lo[i]) * np.clip(x[i], 0, 1)))
    return P


def search(fit, knobs, rounds=3, log=print, method='powell', workers=1, seed=0, maxiter=40, popsize=12, maxfev=400):
    """Powell's method over the knobs within KNOB_BOUNDS (scaled to their ranges), from fit.base, `rounds` times from
    the best so far; or method 'de': differential evolution over the box first (scipy; `workers` processes spawned,
    each rebuilding the fit from fit.src = ('module:factory', args)), a progress line per generation. fit: .score(P)
    -> (cost, per), .base, .floors, .src -> (P, cost, per)."""
    from scipy.optimize import minimize
    P0 = dict(fit.base)
    lo = np.array([bounds_of(k)[0] for k in knobs])
    hi = np.array([bounds_of(k)[1] for k in knobs])
    x0 = (np.clip([get_knob(P0, k) for k in knobs], lo, hi) - lo) / (hi - lo)
    best = {'c': np.inf}
    to_P = lambda x: _to_P(P0, knobs, lo, hi, x)

    def f(x):
        P = to_P(x)
        c, per = fit.score(P)
        if c < best['c']:
            best.update(c=c, P=P, per=per)
        return c
    c0 = f(x0)
    log('start %.4f %s' % (c0, best['per']))
    if method == 'de':
        # (workers spawned, each building its own fit from fit.src: a pool forked after this process had evaluated
        # once hung on the old render box, fit2 at 110 min with no generation done)
        from scipy.optimize import differential_evolution
        global _DE
        _DE = (fit, to_P)
        pool, gen = None, [0]
        if workers > 1:
            import multiprocessing as mp
            for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMBA_NUM_THREADS'):
                os.environ[k] = '1'
            pool = mp.get_context('spawn').Pool(workers, initializer=_de_init,
                                                initargs=(fit.src, fit.floors, P0, list(knobs), lo, hi))

        def progress(xk, convergence=None):
            gen[0] += 1
            c, per = fit.score(to_P(xk))
            log('de generation %d: best %.4f (convergence %.3f) %s' % (
                gen[0], c, convergence or 0.0, ' '.join('%s %s' % (k, v[0] if isinstance(v, tuple) else v)
                                                        for k, v in per.items())))
        try:
            res = differential_evolution(_de_cost, [(0, 1)] * len(knobs), x0=x0, seed=seed, maxiter=maxiter,
                                         popsize=popsize, tol=1e-4, polish=False, init='sobol',
                                         workers=pool.map if pool else 1, callback=progress,
                                         updating='deferred' if pool else 'immediate')
        finally:
            if pool:
                pool.close()
        f(res.x)
        log('de %.4f (%d evaluations) %s' % (best['c'], res.nfev, {k: round(get_knob(best['P'], k), 4) for k in knobs}))
    for r in range(rounds):
        xs = (np.array([get_knob(best['P'], k) for k in knobs]) - lo) / (hi - lo)
        res = minimize(f, xs, method='Powell', bounds=[(0, 1)] * len(knobs),
                       options=dict(xtol=0.01, ftol=1e-4, maxfev=maxfev))
        log('round %d %.4f (%d evaluations) %s' % (r, best['c'], res.nfev,
                                                    {k: round(get_knob(best['P'], k), 4) for k in knobs}))
    return best['P'], best['c'], best['per']


_DE = None


def _warn(k):
    """a structure check's WARN limit (handqa.LIMITS: past it, FAIL)."""
    from . import handqa
    return handqa.LIMITS[k][1]


def _de_init(src, floors, P0, knobs, lo, hi):
    """a spawned worker's fit (src: ('module:factory', args)), its knobs' mapping as the parent's."""
    global _DE
    import importlib
    mod, name = src[0].split(':')
    F = getattr(importlib.import_module(mod), name)(*src[1])
    F.floors = floors
    _DE = (F, lambda x: _to_P(P0, knobs, lo, hi, x))


def _de_cost(x):
    """differential evolution's cost (module level: a worker reaches its fit through _DE)."""
    F, to_P = _DE
    return F.score(to_P(x))[0]


def _fit_for(build, spec_path, over=None):
    from . import calibrate, manifest, qa3d
    B = calibrate.load_bundle(build)
    D = qa3d.Design(B)
    spec = json.load(open(spec_path))
    if over:
        spec.setdefault('body', {}).setdefault('hand', {}).update(over)
    hull = manifest.produced(B.spec, manifest.body_hull(B.spec))
    masks = manifest.produced(B.spec, 'outfit_masks')
    F = Fit(B, D, spec, os.path.dirname(hull), os.path.join(os.path.dirname(masks), 'outfit_graph.json'))
    F.src = ('charkit.code_hand:_fit_only', (build, spec_path, over))
    return F, spec


def _fit_only(build, spec_path, over=None):
    return _fit_for(build, spec_path, over)[0]


def show(F, P, out):
    """a picture of the template against the drawn hands: per view and side the drawn hand (grey) with ours (red
    outline) turned to the drawn arm and laid on the centroids, as hand_shape lays them; the IoU and the structure
    terms (ours / drawn) under each -> the path."""
    from PIL import Image, ImageDraw
    from scipy import ndimage
    from . import handqa
    _, full = F.score(P, detail=True)
    tiles = []
    for side in ('left', 'right'):
        S = 'L' if side == 'left' else 'R'
        for v, (m, r, uf, c) in F.silhouettes(P, side).items():
            d = F.drawn[(v, S)]
            A, Bm = handqa.aligned_pair(d['mask'], handqa.rotated(m, uf, d['u']))
            img = np.full(A.shape + (3,), 255, np.uint8)
            img[A] = (175, 175, 175)
            img[Bm & ~ndimage.binary_erosion(Bm)] = (220, 30, 30)
            img = np.kron(img, np.ones((3, 3, 1), np.uint8))
            k = '%s_%s' % (v, S)
            lines = ['%s IoU %.3f reach %+.3f' % (k, full[k]['iou'], full[k]['reach'])]
            lines += ['%s %s / %s' % (n, a, b) for n, (a, b, _) in full[k]['terms'].items()]
            canvas = np.full((img.shape[0] + 12 * len(lines) + 4, max(img.shape[1], 190), 3), 255, np.uint8)
            canvas[:img.shape[0], :img.shape[1]] = img
            im = Image.fromarray(canvas)
            for i, t in enumerate(lines):
                ImageDraw.Draw(im).text((2, img.shape[0] + 2 + 12 * i), t, fill=(0, 0, 0))
            tiles.append(np.asarray(im))
    H = max(t.shape[0] for t in tiles)
    row = np.concatenate([np.pad(t, ((0, H - t.shape[0]), (0, 8), (0, 0)), constant_values=255) for t in tiles], 1)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    Image.fromarray(row).save(out)
    return out


def main(args):
    """python -m charkit.code_hand fit --build B [--spec S | --write S] [--rounds N] [--over JSON] [--knobs a,b]
                                        [--png P] [--json J] [--floors JSON] [--method de --workers N --maxiter N]
                                        [--bounds '{"curl": [-10, 12]}']
       python -m charkit.code_hand show --build B [--spec S] [--over JSON] --out PNG    (the template vs the drawn)"""
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    if not args or args[0] not in ('fit', 'show'):
        print(__doc__)
        return 0
    spec_path = opt('--write') or opt('--spec') or os.path.join(ROOT, 'charkit', 'spec', 'clawd.json')
    over = json.loads(opt('--over')) if opt('--over') else None
    F, spec = _fit_for(opt('--build'), spec_path, over)
    if opt('--floors'):
        F.floors = json.loads(opt('--floors'))
    if args[0] == 'show':
        c, full = F.score(F.base, detail=True)
        print(json.dumps(dict(cost=round(c, 4), per=full), indent=1))
        print(show(F, F.base, opt('--out', 'hand_fit.png')))
        return 0
    knobs = tuple(opt('--knobs').split(',')) if opt('--knobs') else FIT_KNOBS
    if opt('--floors'):
        F.floors = json.loads(opt('--floors'))
    if opt('--bounds'):                     # {knob: [lo, hi]}: this run's bounds (ratio4 ran curl to its bound 30: shut)
        KNOB_BOUNDS.update({k: tuple(v) for k, v in json.loads(opt('--bounds')).items()})
    P, c, per = F.run(knobs=knobs, rounds=int(opt('--rounds', 3)), log=lambda *a, **k: print(*a, flush=True),
                      method=opt('--method', 'powell'), workers=int(opt('--workers', 1)), seed=int(opt('--seed', 0)),
                      maxiter=int(opt('--maxiter', 40)), popsize=int(opt('--popsize', 12)),
                      maxfev=int(opt('--maxfev', 400)))
    c, full = F.score(P, detail=True)
    res = dict(cost=round(c, 4), per=full, knobs={k: (round(v, 4) if isinstance(v, float) else v) for k, v in P.items()},
               fist=fist_report(hand(F.J['left'], 'left', P)))
    print(json.dumps(res, indent=1))
    if opt('--json'):
        os.makedirs(os.path.dirname(os.path.abspath(opt('--json'))), exist_ok=True)
        json.dump(res, open(opt('--json'), 'w'), indent=1)
    if opt('--png'):
        print(show(F, P, opt('--png')))
    if opt('--write'):
        spec = json.load(open(spec_path))
        spec.setdefault('body', {})['hand'] = {k: (round(P[k], 4) if isinstance(P[k], float) else list(P[k]))
                                               for k in DEFAULT if k in P}
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
    posed tube: their share, and the deepest, L), at rest too (`rest_overlap`: since round 4 the fingers are held
    together, overlapping by `overlap` of their width) -> dict."""
    from scipy.spatial import cKDTree
    posed = curl_pose(H_, curl, thumb)
    rep = {'curl': curl, 'thumb': thumb, 'knuckle_area': {}, 'overlap': {}, 'rest_overlap': {}}
    for name in FINGERS + ('thumb',):
        rest, now = H_['parts'][name][0], posed[name]
        ratios = [ring_area(now[i]) / max(ring_area(rest[i]), 1e-12) for i in range(len(rest))]
        rep['knuckle_area'][name] = round(float(min(ratios)), 3)
    rest = {n: H_['parts'][n][0] for n in FINGERS}
    for key, got in (('overlap', posed), ('rest_overlap', rest)):
        for a, b in zip(FINGERS[:-1], FINGERS[1:]):
            A, Bp = got[a], got[b]
            cb, rb = Bp.mean(1), np.linalg.norm(Bp - Bp.mean(1)[:, None], axis=2).mean(1)
            tree = cKDTree(cb)
            P = A.reshape(-1, 3)
            d, i = tree.query(P)
            depth = rb[i] - np.linalg.norm(P - cb[i], axis=1)
            inside = depth > 0
            rep[key]['%s/%s' % (a, b)] = dict(share=round(float(inside.mean()), 3),
                                              deepest=round(float(max(depth.max(), 0.0)), 4))
    return rep
