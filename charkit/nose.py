"""The nose's drawn mark (Michael's flag, 2026-09-30: the nose read only in profile; from the front and three-quarter
the design draws a small mark there). An anime nose is drawn, not shaded: head_turnaround and head_construction draw
a short ink tick under the tip and a pale highlight on the bridge over it in front, and the tick (with a faint
highlight) in three-quarter; in profile the nose is its silhouette. The mark is a decal laid on the face's surface
round the nose tip (charkit.eyes.Face), a hair in front of it, riding the head (it moves with the head, no keys of its
own): slot 0 the ink tick, slot 1 the highlight.

Knobs (spec `nose`; each (width, height, centre above the tip) in L; a part with no size is left out):
  tick       the ink tick under the tip
  high       the highlight on the bridge
  lift       how far in front of the skin (L)
  color, high_color
"""
import numpy as np

DEFAULT_NOSE = {
    'tick': (0.0045, 0.016, -0.006),
    'high': (0.011, 0.016, 0.026),
    'lift': 0.0008,
    'color': (0.30, 0.13, 0.11),
    'high_color': (1.0, 0.97, 0.95),
}


def knobs(spec):
    K = dict(DEFAULT_NOSE)
    K.update((spec or {}).get('nose') or {})
    return K


def _lens(w, h, n):
    """a pointed lens (a drawn tick or a highlight), its outline round (0, 0) as (x, z): widest at its middle."""
    t = np.linspace(0.0, 1.0, n)
    z = h * (t - 0.5)
    hw = 0.5 * w * np.sin(np.pi * t) ** 0.8
    return z, hw


def mark(F, K, L, tip, n=9):
    """the decal round the nose tip (world x, z) on the face F -> (verts, quads, slot per quad) or None (no part)."""
    verts, quads, slots = [], [], []
    for slot, part in enumerate(('tick', 'high')):
        spec = K.get(part)
        if not spec or spec[0] <= 0 or spec[1] <= 0:
            continue
        w, h, dz = (float(v) * L for v in spec)
        z, hw = _lens(w, h, n)
        xs = np.concatenate([tip[0] - hw, tip[0] + hw])
        zs = np.concatenate([tip[1] + dz + z, tip[1] + dz + z])
        P = F.points(xs, zs)
        P[:, 1] -= float(K['lift']) * L                      # (toward the camera: the face looks down -y)
        o = sum(len(v) for v in verts)
        verts.append(P)
        for i in range(n - 1):
            quads.append((o + i, o + n + i, o + n + i + 1, o + i + 1))    # (counter-clockwise from the front)
            slots.append(slot)
    if not verts:
        return None
    return np.vstack(verts), quads, slots


def tip_of(H, centre):
    """the nose tip's world (x, z) on a head that knows it (charkit.code_base.SectionsHead: nose_z under the eye line), or
    None (a base without one: no mark)."""
    nz = getattr(H, 'nose_z', None)
    if nz is None:
        return None
    return (float(centre[0]), float(centre[2]) + float(nz))
