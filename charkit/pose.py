"""Named poses as data (tool/rom, 2026-10-01): a pose is a preset in a JSON library (charkit/poses/*.json), applied to
any humanoid skeleton (the VRM humanoid bones: charkit.mh.VRM_JOINTS / VRM_PARENT) in anatomical terms, so motion tests,
the range-of-motion suite (charkit.rom) and shots reuse the same presets on any character.

    from charkit import pose
    lib = pose.library()                                # charkit/poses/rom.json: {name: preset}
    sk = pose.Skeleton(heads, tails)                    # {bone: (3,)} in Blender's frame (Z up, facing -Y, her left +X)
    D = pose.solve(sk, lib['elbows_90'], f=1.0)         # {bone: 4x4 world deformation (rest -> posed)}, f of the way

A preset: {"group", "what", "bones": {KEY: {op: value}}}. KEY is a bone name ("leftLowerArm", "spine") or a side-less
name or fnmatch pattern over side-less names ("LowerArm", "[IMRL]*Proximal"), which applies to both sides, mirrored; a
later key's op replaces an earlier one's for the same bone. The ops, each about the bone's head (carried by its parent),
applied in this order, angles in degrees:
  aim     the direction the bone points afterwards: a name (up, down, forward, back, out, in) or [out, forward, up]
          (out: away from the midline on the bone's side; for the middle bones [left, forward, up])
  raise   its direction turned toward up by that much (away from up when negative)
  swing   its direction turned toward forward (toward back when negative)
  bend    flexion about the joint's anatomical hinge: the elbow and the shoulder toward the front, the knee toward the
          back, the hip toward the front, the wrist and the fingers toward the palm, the thumb across it, the ankle toward
          the sole, the spine, neck and head forward, the clavicle up (negative: extension); the thumb across the
          fingers toward the little finger
  spread  abduction in the palm's plane: a finger away from the middle finger, the thumb away from the index
  twist   about the bone's own axis: positive turns its front toward the midline (internal rotation; mirrored per side)
  turn, nod, tilt   about the body's axes: turn about up (toward her left; mirrored for a side bone), nod about the
          left-right axis (forward), tilt about the front-back axis (toward her left; mirrored for a side bone)
A preset taken f of the way scales every angle (aim: the angle to the target) by f: the same preset is a ramp.
Deterministic: plain float64 numpy, no randomness.
"""
import fnmatch, json, os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LIBRARY = os.path.join(HERE, 'poses', 'rom.json')
UP, FWD, LEFT = np.array([0.0, 0.0, 1.0]), np.array([0.0, -1.0, 0.0]), np.array([1.0, 0.0, 0.0])
OPS = ('aim', 'raise', 'swing', 'bend', 'spread', 'twist', 'turn', 'nod', 'tilt')
THUMB_PALM = 0.15           # the thumb's flexion: across toward the little finger, this much toward the palm (at 1.0
                            # a fist's thumb stood out of the palm on Clawd's hand; tool/rom close-ups, 2026-10-01)
MIDDLE = ('hips', 'spine', 'chest', 'upperChest', 'neck', 'head')
FINGERS = ('Index', 'Middle', 'Ring', 'Little')
NAMED = {'up': (0.0, 0.0, 1.0), 'down': (0.0, 0.0, -1.0), 'forward': (0.0, 1.0, 0.0), 'back': (0.0, -1.0, 0.0),
         'out': (1.0, 0.0, 0.0), 'in': (-1.0, 0.0, 0.0)}


def library(path=LIBRARY):
    """a pose library file -> {name: preset} (in the file's order)."""
    js = json.load(open(path))
    return dict(js.get('poses', js))


def rotation(axis, deg):
    """the rotation by deg degrees about axis (right-handed; Rodrigues)."""
    a = np.asarray(axis, float)
    n = np.linalg.norm(a)
    if n < 1e-12 or abs(deg) < 1e-12:
        return np.eye(3)
    a = a / n
    t = np.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(t) * K + (1 - np.cos(t)) * K @ K


def _unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def _perp(v, d):
    """v's part perpendicular to unit d, unit."""
    return _unit(v - (v @ d) * d)


def side_of(bone):
    return 'left' if bone.startswith('left') else 'right' if bone.startswith('right') else None


def bare(bone):
    """a bone's side-less name ('leftLowerArm' -> 'LowerArm')."""
    s = side_of(bone)
    return bone[len(s):] if s else bone


class Skeleton:
    """the humanoid's rest skeleton (Blender's frame): heads and tails per VRM bone, parents (charkit.mh.VRM_PARENT),
    and per bone its anatomical directions at rest: the hinge's flexion direction, the palm's normal for the hand's
    bones, the spread direction for the digits."""

    def __init__(self, heads, tails=None, parents=None):
        from .mh import VRM_PARENT
        self.head = {b: np.asarray(h, float) for b, h in heads.items()}
        par = dict(parents or VRM_PARENT)
        self.parent = {b: par.get(b) if par.get(b) in self.head else None for b in self.head}
        kids = {}
        for b, p in self.parent.items():
            if p:
                kids.setdefault(p, []).append(b)
        self.tail = {}
        for b in self.head:
            t = None if tails is None else tails.get(b)
            if t is not None and np.linalg.norm(np.asarray(t, float) - self.head[b]) > 1e-5:
                self.tail[b] = np.asarray(t, float)
                continue
            ch = [c for c in kids.get(b, ()) if bare(c) in ('LowerArm', 'Hand', 'LowerLeg', 'Foot', 'Toes', 'neck',
                                                            'head', 'spine', 'chest', 'upperChest', 'UpperArm',
                                                            'MiddleProximal')
                  or bare(c).endswith(('Intermediate', 'Distal')) or (bare(c) == 'ThumbProximal')]
            if ch:
                self.tail[b] = self.head[ch[0]]
            elif self.parent.get(b):                     # (a leaf: its parent's direction continued, half its length)
                p = self.parent[b]
                d = self.head[b] - self.head[p]
                self.tail[b] = self.head[b] + 0.6 * d
            else:
                self.tail[b] = self.head[b] + np.array([0, 0, 0.05])
        order, seen = [], set()

        def visit(b):
            if b in seen:
                return
            if self.parent.get(b):
                visit(self.parent[b])
            seen.add(b)
            order.append(b)
        for b in sorted(self.head):
            visit(b)
        self.order = order
        self._anatomy()

    def dir(self, b):
        return _unit(self.tail[b] - self.head[b])

    def sgn(self, b):
        return -1.0 if side_of(b) == 'right' else 1.0

    def palm(self, s):
        """side s's palm normal (toward the palm, unit) and its knuckle line (little -> index, unit), or (None, None)."""
        H, I, Lt = s + 'Hand', s + 'IndexProximal', s + 'LittleProximal'
        if not all(b in self.head for b in (H, I, Lt)):
            return None, None
        h = self.dir(H)
        k = _perp(self.head[I] - self.head[Lt], h)
        n = _unit(np.cross(h, k)) * (1.0 if s == 'left' else -1.0)
        return n, k

    def _anatomy(self):
        self.flex, self.spread = {}, {}
        palms = {s: self.palm(s) for s in ('left', 'right')}
        for b in self.head:
            d, s, nb = self.dir(b), side_of(b), bare(b)
            n, k = palms.get(s, (None, None)) if s else (None, None)
            if nb in ('LowerLeg',):
                f = -FWD
            elif nb in ('Foot', 'Toes'):
                f = -UP
            elif nb == 'Shoulder':
                f = UP
            elif nb.startswith('Thumb') and n is not None:
                f = _unit(THUMB_PALM * n - k)         # across the fingers toward the little finger, a little palmward
            elif (nb == 'Hand' or nb.startswith(FINGERS)) and n is not None:
                f = n
            else:                                      # arms, hips' legs, spine, neck, head: toward the front
                f = FWD
            self.flex[b] = _perp(f, d)
            if k is not None and (nb.startswith(FINGERS) or nb.startswith('Thumb')):
                away = k if nb.startswith(('Index', 'Thumb', 'Middle')) else -k
                self.spread[b] = _perp(away, d)

    def target(self, b, aim):
        """an aim (a name or [out, forward, up]) as a world direction for bone b."""
        v = np.array(NAMED[aim] if isinstance(aim, str) else aim, float)
        sx = self.sgn(b) if side_of(b) else 1.0
        return _unit(np.array([sx * v[0], -v[1], v[2]]))


def ops_of(sk, preset):
    """a preset's ops per bone: {bone: {op: value}} (side-less keys and patterns expanded to both sides)."""
    out = {}
    for key, ops in (preset.get('bones') or {}).items():
        hit = [b for b in sk.head if b == key or fnmatch.fnmatchcase(bare(b), key)]
        if not hit and key not in sk.head:
            continue
        for b in hit:
            out.setdefault(b, {}).update(ops)
    return out


def _from_to(a, b):
    """axis and degrees of the smallest rotation taking unit a onto unit b."""
    c = float(np.clip(a @ b, -1.0, 1.0))
    ax = np.cross(a, b)
    if np.linalg.norm(ax) < 1e-9:
        if c > 0:
            return np.array([1.0, 0, 0]), 0.0
        ax = np.cross(a, LEFT if abs(a @ LEFT) < 0.9 else UP)
    return _unit(ax), float(np.degrees(np.arccos(c)))


def bone_rotation(sk, b, ops, d, flex, spread, f=1.0):
    """the rotation (3x3, world) of bone b's ops taken f of the way, from its carried direction d, hinge direction flex
    and spread direction (both carried)."""
    R = np.eye(3)
    sx = sk.sgn(b) if side_of(b) else 1.0

    def apply(Q):
        nonlocal R, d, flex, spread
        R = Q @ R
        d, flex = Q @ d, Q @ flex
        spread = None if spread is None else Q @ spread
    if 'aim' in ops:
        ax, deg = _from_to(d, sk.target(b, ops['aim']))
        apply(rotation(ax, deg * f))
    for op, toward in (('raise', UP), ('swing', FWD)):
        if op in ops:
            ax = np.cross(d, toward)
            if np.linalg.norm(ax) < 1e-6:              # (pointing that way already: turn about the hinge instead)
                ax = np.cross(d, flex)
            apply(rotation(ax, float(ops[op]) * f))
    if 'bend' in ops:
        apply(rotation(np.cross(d, flex), float(ops['bend']) * f))
    if 'spread' in ops and spread is not None:
        apply(rotation(np.cross(d, spread), float(ops['spread']) * f))
    if 'twist' in ops:
        apply(rotation(d, sx * float(ops['twist']) * f))
    for op, axis, mirror in (('turn', UP, True), ('nod', LEFT, False), ('tilt', -FWD, True)):
        if op in ops:
            apply(rotation(axis, (sx if mirror else 1.0) * float(ops[op]) * f))
    return R


def solve(sk, preset, f=1.0):
    """{bone: 4x4 world deformation} of a preset taken f of the way (rest -> posed; Blender's frame), composed down the
    hierarchy: each bone's ops turn it about its head where its parent has carried it."""
    ops = ops_of(sk, preset)
    D = {}
    for b in sk.order:
        p = sk.parent.get(b)
        Dp = D[p] if p in D else np.eye(4)
        Rp = Dp[:3, :3]
        h = Rp @ sk.head[b] + Dp[:3, 3]
        M = np.eye(4)
        if b in ops:
            sp = sk.spread.get(b)
            R = bone_rotation(sk, b, ops[b], Rp @ sk.dir(b), Rp @ sk.flex[b], None if sp is None else Rp @ sp, f)
            M[:3, :3] = R
            M[:3, 3] = h - R @ h
        D[b] = M @ Dp
    return D


def posed_joints(sk, D):
    """each bone's posed head and tail -> ({bone: head}, {bone: tail})."""
    H, T = {}, {}
    for b, M in D.items():
        H[b] = M[:3, :3] @ sk.head[b] + M[:3, 3]
        T[b] = M[:3, :3] @ sk.tail[b] + M[:3, 3]
    return H, T


def angle_between(sk, D, a, b):
    """the posed angle (degrees) between bones a and b's directions (the flexion a joint reached)."""
    H, T = posed_joints(sk, D)
    u, v = _unit(T[a] - H[a]), _unit(T[b] - H[b])
    return float(np.degrees(np.arccos(np.clip(u @ v, -1, 1))))
