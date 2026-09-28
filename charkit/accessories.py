"""Hair accessories and small props (docs/CHARKIT.md §2): meshes placed on the hair volume by (az, el, r), oriented to its
surface. Kinds: 'bun' (stacked rounded pads, like Clawd's), 'star' (an n-pointed clip), 'crab' (a little crab clip).
Each accessory spec: {kind, az, el, r, size (in L), tilt (degrees about the surface normal), lean (degrees outward),
color / material}.
"""
import math
import numpy as np


def rounded_box(sx, sy, sz, rad, segs=4):
    """a rounded box centred at the origin (a subdivided cube pushed onto the rounded shape). -> (verts, quads)."""
    n = segs * 2 + 2
    verts, index = [], {}

    def vid(i, j, k):
        key = (i, j, k)
        if key not in index:
            p = np.array([i, j, k], float) / (n - 1) * 2 - 1           # -1 .. 1
            half = np.array([sx, sy, sz]) / 2
            inner = half - rad
            q = p * half
            c = np.clip(q, -inner, inner)
            d = q - c
            ln = np.linalg.norm(d)
            verts.append(c + (d / ln * rad if ln > 1e-12 else d))
            index[key] = len(verts) - 1
        return index[key]
    faces = []
    r = range(n - 1)
    for a in r:
        for b in r:
            faces.append((vid(0, a, b), vid(0, a, b + 1), vid(0, a + 1, b + 1), vid(0, a + 1, b)))
            faces.append((vid(n - 1, a, b), vid(n - 1, a + 1, b), vid(n - 1, a + 1, b + 1), vid(n - 1, a, b + 1)))
            faces.append((vid(a, 0, b), vid(a + 1, 0, b), vid(a + 1, 0, b + 1), vid(a, 0, b + 1)))
            faces.append((vid(a, n - 1, b), vid(a, n - 1, b + 1), vid(a + 1, n - 1, b + 1), vid(a + 1, n - 1, b)))
            faces.append((vid(a, b, 0), vid(a, b + 1, 0), vid(a + 1, b + 1, 0), vid(a + 1, b, 0)))
            faces.append((vid(a, b, n - 1), vid(a + 1, b, n - 1), vid(a + 1, b + 1, n - 1), vid(a, b + 1, n - 1)))
    return np.array(verts), faces


def star(points=4, r_out=1.0, r_in=0.32, depth=0.18, long=1.35):
    """an n-pointed star in the xz plane, thickness along y, the vertical points longer (a sparkle). -> (verts, faces)."""
    ring = []
    for k in range(points * 2):
        a = math.pi / 2 + math.pi * k / points
        r = r_out if k % 2 == 0 else r_in
        if k % 2 == 0 and abs(math.sin(a)) > 0.7:
            r *= long
        ring.append((math.cos(a) * r, math.sin(a) * r))
    m = len(ring)
    verts = [(x, -depth / 2, z) for x, z in ring] + [(x, depth / 2, z) for x, z in ring]
    verts += [(0, -depth * 0.9, 0), (0, depth * 0.9, 0)]
    cf, cb = 2 * m, 2 * m + 1
    faces = []
    for k in range(m):
        k2 = (k + 1) % m
        faces.append((cf, k2, k))
        faces.append((cb, m + k, m + k2))
        faces.append((k, k2, m + k2, m + k))
    return np.array(verts, float), faces


def crab():
    """a little crab: a flattened body and two claws, as (verts, faces, part colours index 0 body / 1 claws)."""
    parts = []
    bv, bf = rounded_box(1.0, 0.45, 0.62, 0.22, segs=3)
    parts.append((bv, bf))
    for sx in (-1, 1):
        cv, cf = rounded_box(0.36, 0.28, 0.30, 0.12, segs=2)
        parts.append((cv + np.array([sx * 0.66, -0.05, 0.28]), cf))
    V, F, o = [], [], 0
    for v, f in parts:
        V.append(v); F += [tuple(i + o for i in q) for q in f]; o += len(v)
    return np.vstack(V), F


def _frame(V, az, el, tilt=0.0, lean=0.0):
    """a frame on the hair volume: origin on it, z = its outward normal leaned toward 'up', x across."""
    p = V.point(az, el)
    n = V.normal(az, el)
    up = np.array([0, 0, 1.0])
    x = np.cross(up, n)
    if np.linalg.norm(x) < 1e-6:
        x = np.array([1.0, 0, 0])
    x /= np.linalg.norm(x)
    y = np.cross(n, x)
    t = math.radians(tilt)
    x, y = x * math.cos(t) + y * math.sin(t), y * math.cos(t) - x * math.sin(t)
    lz = math.radians(lean)
    n2 = n * math.cos(lz) + y * math.sin(lz)
    y2 = y * math.cos(lz) - n * math.sin(lz)
    return p, np.stack([x, y2, n2], 1)          # columns: local x, y, z in world


def generate(V, L, specs):
    """accessory meshes: list of (name, verts, faces, spec)."""
    out = []
    for i, s in enumerate(specs or []):
        k = s['kind']
        size = s.get('size', 0.2) * L
        p, R = _frame(V, s['az'], s['el'], s.get('tilt', 0.0), s.get('lean', 0.0))
        p = p + R[:, 2] * s.get('lift', 0.0) * L
        if k == 'bun':
            # stacked pads: a big square pad, a second behind and above it, a third behind that
            vs, fs, o = [], [], 0
            for j, (dy, dz, sc) in enumerate(((0.0, 0.0, 1.0), (0.12, 0.30, 0.86), (0.22, 0.52, 0.7))):
                v, f = rounded_box(1.0 * sc, 1.0 * sc, 0.42 * sc, 0.16 * sc, segs=3)
                v = v + np.array([0.0, dy, -dz]) * 1.0
                vs.append(v); fs += [tuple(a + o for a in q) for q in f]; o += len(v)
            v = np.vstack(vs); f = fs
            # the pad lies across the head: its thin axis (z) along the surface normal
            v = v * size + np.array([0, 0, 0.28 * size])
        elif k == 'star':
            v, f = star(s.get('points', 4))
            v = v[:, [0, 2, 1]] * np.array([1, 1, 1]) * size * 0.5       # the star's face toward the normal
            v[:, 2] += 0.12 * size
        elif k == 'crab':
            v, f = crab()
            v = v[:, [0, 2, 1]] * size * 0.5
            v[:, 2] += 0.12 * size
        else:
            raise ValueError(k)
        w = p + v @ R.T
        out.append((s.get('name', f'{k}_{i}'), w, f, s))
    return out


def build(A, arm, V, specs, mats):
    """Blender objects for the accessories, parented to the head. mats: {kind: material} (or a spec's own 'material')."""
    from . import character, shade
    L = A['head']['L']
    obs = []
    for name, v, f, s in generate(V, L, specs):
        m = mats.get(s.get('material', s['kind'])) or shade.flat(name + '_mat', s.get('color', (0.9, 0.9, 0.9)))
        ob = character._mesh(name, v, f, None, [m])
        for p in ob.data.polygons:
            p.use_smooth = s['kind'] != 'star'
        import bmesh
        bm = bmesh.new(); bm.from_mesh(ob.data)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(ob.data); bm.free()
        shade.outline(ob, thick=0.0010, color=s.get('line', (0.35, 0.16, 0.12)), name=f'{name}_line')
        character._to_head(ob, arm)
        obs.append(ob)
    return obs
