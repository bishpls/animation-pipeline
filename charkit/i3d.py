"""Image-to-3D results as kit data (docs/CHARKIT.md §5): a TRELLIS.2 GLB (tools/imageto3d) imported, turned to face the kit's
front (the view whose outline best matches the input image's alpha), scaled and placed in head space from the design's own
measurements (charkit.refs: pixels per head length, the eyes), its vertices coloured from the base-colour texture, and split
into parts by colour (hair, skin, ...). The hair part becomes charkit.hair's volume (MeshVolume); the head can be a wrap
target for charkit.anime_head.
"""
import math
import os

import numpy as np


def _raster(P2, faces, n=160):
    """a filled silhouette of 2D points P2 (N,2) in [0,1]^2 on an n x n grid (row 0 = top)."""
    img = np.zeros((n, n), bool)
    Q = P2 * (n - 1)
    for f in faces:
        for k in range(1, len(f) - 1):
            t = Q[[f[0], f[k], f[k + 1]]]
            x0, x1 = int(max(0, np.floor(t[:, 0].min()))), int(min(n - 1, np.ceil(t[:, 0].max())))
            y0, y1 = int(max(0, np.floor(t[:, 1].min()))), int(min(n - 1, np.ceil(t[:, 1].max())))
            if x1 < x0 or y1 < y0:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
            (ax, ay), (bx, by), (cx, cy) = t
            d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if abs(d) < 1e-12:
                continue
            l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / d
            l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / d
            img[y0:y1 + 1, x0:x1 + 1] |= (l1 >= -0.01) & (l2 >= -0.01) & (l1 + l2 <= 1.01)
    return img


def _norm_mask(alpha, n=160):
    """the image's alpha cropped to its bbox, fitted into n x n keeping the aspect, top-left anchored like _fit2d."""
    ys, xs = np.nonzero(alpha)
    a = alpha[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = a.shape
    s = (n - 1) / max(h, w)
    out = np.zeros((n, n), bool)
    yy, xx = np.nonzero(a)
    out[(yy * s).astype(int), (xx * s).astype(int)] = True
    return out, (xs.min(), ys.min(), w, h)


def _fit2d(P2):
    lo, hi = P2.min(0), P2.max(0)
    return (P2 - lo) / (hi - lo).max(), lo, (hi - lo).max()


def orient(V, faces, alpha, n=160, sub=6000):
    """the rotation about z (0, 90, 180, 270 degrees, optionally mirrored) under which the mesh's front view (looking along
    +y, x right, z up) best matches the image alpha. -> (rotated V, dict(angle, mirror, iou))."""
    ref, _ = _norm_mask(alpha, n)
    fs = faces if len(faces) <= sub else [faces[i] for i in np.linspace(0, len(faces) - 1, sub).astype(int)]
    best = None
    for ang in (0, 90, 180, 270):
        c, s_ = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        R = np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1]])
        W = V @ R.T
        for mirror in (False, True):
            X = -W[:, 0] if mirror else W[:, 0]
            P2 = np.stack([X, -W[:, 2]], 1)                    # image coords: x right, y down
            Q, _, _ = _fit2d(P2)
            m = _raster(Q, fs, n)
            iou = (m & ref).sum() / max(1, (m | ref).sum())
            if best is None or iou > best[0]:
                best = (iou, ang, mirror, W * (np.array([-1, 1, 1]) if mirror else 1))
    return best[3], dict(angle=best[1], mirror=best[2], iou=float(best[0]))


def align(V, bbox_px, ppl, eye_px, centre, L, face_y=None):
    """scale and place a front-oriented mesh in world: the mesh's front-view bbox is the image alpha bbox (bbox_px: x, y, w,
    h), pixels per head length ppl; the image's eye centre (eye_px) lands on the kit's eye line centre (centre: head-space
    origin in world). face_y: optional world y for the mesh's frontmost point near the eyes (else the head centre's
    front)."""
    x0, y0, w, h = bbox_px
    lo, hi = V.min(0), V.max(0)
    s = (h / ppl * L) / (hi[2] - lo[2])
    W = (V - np.array([(lo[0] + hi[0]) / 2, 0, hi[2]])) * s             # x centred on the bbox, z = 0 at the top
    ex = (eye_px[0] - (x0 + w / 2)) / ppl * L
    ez = -(eye_px[1] - y0) / ppl * L
    W = W - np.array([ex, 0, ez]) + np.array([centre[0], 0, centre[2]])
    near = (np.abs(W[:, 2] - centre[2]) < 0.08 * L) & (np.abs(W[:, 0] - centre[0]) < 0.12 * L)
    fy = W[near, 1].min() if near.any() else W[:, 1].min()
    W[:, 1] += (face_y if face_y is not None else centre[1]) - fy
    return W


def classify(colors, palette, max_d=0.25):
    """label each colour by the nearest palette entry {name: [rgb, ...]} (sRGB 0..1); -1 when nothing is within max_d."""
    names = list(palette)
    best = np.full(len(colors), -1); bd = np.full(len(colors), np.inf)
    for i, nm in enumerate(names):
        for c in palette[nm]:
            d = np.linalg.norm(colors - np.asarray(c), axis=1)
            m = d < bd
            bd[m] = d[m]; best[m] = i
    best[bd > max_d] = -1
    return best, names


def load_glb(path):
    """Blender: import a GLB and return (verts world (N,3), faces, per-vertex base colour (N,3) sRGB) of its meshes joined.
    The imported objects are removed again."""
    import bpy
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    obs = [o for o in bpy.data.objects if o not in before and o.type == 'MESH']
    V, F, C, off = [], [], [], 0
    for ob in obs:
        me = ob.data
        M = np.array(ob.matrix_world)
        v = np.array([tuple(x.co) for x in me.vertices])
        v = (np.c_[v, np.ones(len(v))] @ M.T)[:, :3]
        col = np.full((len(v), 3), 0.5)
        img = None
        for s_ in ob.material_slots:
            if s_.material and s_.material.node_tree:
                for nd in s_.material.node_tree.nodes:
                    if nd.type == 'TEX_IMAGE' and nd.image and any(l.to_socket.name == 'Base Color' for l in nd.outputs['Color'].links):
                        img = nd.image
        if img is not None and me.uv_layers:
            w, h = img.size
            px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, img.channels)[..., :3]
            uv = np.zeros((len(v), 2)); cnt = np.zeros(len(v))
            lay = me.uv_layers.active.data
            for p in me.polygons:
                for li in p.loop_indices:
                    vi = me.loops[li].vertex_index
                    uv[vi] += lay[li].uv; cnt[vi] += 1
            uv /= np.maximum(cnt, 1)[:, None]
            xi = np.clip((uv[:, 0] % 1) * (w - 1), 0, w - 1).astype(int)
            yi = np.clip((uv[:, 1] % 1) * (h - 1), 0, h - 1).astype(int)
            lin = px[yi, xi]
            col = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(np.maximum(lin, 0), 1 / 2.4) - 0.055)
        elif img is None and len(me.color_attributes):
            # no base-colour texture: the mesh's own vertex colours (COLOR_0, as charkit.geom.io writes them: the
            # visual hull's, charkit.geom.hull), read as sRGB, per vertex or averaged over a vertex's corners
            ca = me.color_attributes.active_color or me.color_attributes[0]
            vals = np.empty(len(ca.data) * 4, np.float32)
            ca.data.foreach_get('color_srgb', vals)
            vals = vals.reshape(-1, 4)[:, :3]
            if ca.domain == 'POINT':
                col = vals.astype(float)
            else:
                vi = np.empty(len(me.loops), np.int64)
                me.loops.foreach_get('vertex_index', vi)
                acc = np.zeros((len(v), 3)); cnt = np.zeros(len(v))
                np.add.at(acc, vi, vals); np.add.at(cnt, vi, 1)
                col = acc / np.maximum(cnt, 1)[:, None]
        V.append(v); C.append(col)
        F += [tuple(off + i for i in p.vertices) for p in me.polygons]
        off += len(v)
    for ob in list(bpy.data.objects):
        if ob not in before:
            bpy.data.objects.remove(ob, do_unlink=True)
    return np.vstack(V), F, np.vstack(C)


def glb_eyes(path, V, C):
    """a generated character's eye centres -> (left (+x), right) or None: known ones from a sidecar next to the GLB
    (PATH.json {"eyes": [left, right]}, in the frame the GLB loads in: charkit.geom.hull writes its own, since it knows
    them exactly and colour finds them only roughly on a smooth surface), else found by colour (find_eyes)."""
    import json as _json
    side = str(path) + '.json'
    if os.path.exists(side):
        E = _json.load(open(side)).get('eyes')
        if E:
            return np.asarray(E[0], float), np.asarray(E[1], float)
    return find_eyes(V, C)


def find_eyes(V, C, head_frac=0.3, depth=0.03, dark=0.3):
    """the two eye centres of a generated character: the darkest texels (lash lines, pupils) on the very front of the head
    (the top `head_frac` of its height, within `depth` of its frontmost point), split left and right. (Amber or iris colours
    are ambiguous: hair highlights and yellow clips share them.) -> (left (+x) centre, right centre) or None."""
    h, s_, v = hsv(C)
    z0, z1 = V[:, 2].min(), V[:, 2].max()
    head = V[:, 2] > z1 - (z1 - z0) * head_frac
    yf = np.percentile(V[head, 1], 3)
    m = head & (V[:, 1] < yf + depth * (z1 - z0)) & (v < dark)
    if m.sum() < 20:
        return None
    P = V[m]
    cx = np.median(P[:, 0])
    L_, R_ = P[P[:, 0] > cx + 0.005 * (z1 - z0)], P[P[:, 0] < cx - 0.005 * (z1 - z0)]
    if len(L_) < 5 or len(R_) < 5:
        return None
    return np.median(L_, 0), np.median(R_, 0)


def eye_target(A, shape):
    """where a generated character's eyes land on ours (align_by_eyes): the midpoint of our eyes, `eye_depth` (head
    lengths) behind the front of the face, and our eye spacing times `spacing`. eye_anchor 'iris': at our irises'
    height (their plates' mean, as the QA and the drawings' eye line (the drawn irises' centroid) take it: an eye whose
    opening sits above its knob line holds its iris higher), else the knobs' line. -> (eye_mid (3,), spacing)."""
    Hd = A['head']; L = Hd['L']; EK = Hd['eye_knobs']
    df = getattr(Hd['H'], 'eye_df', Hd['H'].df)            # the face's front at the eyes (a head that sets them back)
    z = Hd['centre'][2] + EK['z'] * L
    if shape.get('eye_anchor', 'knobs') == 'iris':
        I = [np.asarray(E['iris'][0], float) for E in (A.get('eyes') or []) if E.get('iris') is not None]
        if I:
            z = float(np.mean([i[:, 2].mean() for i in I]))
    eye_mid = np.array([0.0, Hd['centre'][1] - df + shape.get('eye_depth', 0.01) * L, z])
    return eye_mid, 2 * EK['x'] * L * shape.get('spacing', 1.0)


def align_by_eyes(V, eyes, eye_mid, spacing):
    """scale and move a mesh so its eyes' midpoint lands on eye_mid (world) and their spacing equals `spacing`."""
    el, er = eyes
    s = spacing / max(1e-9, abs(el[0] - er[0]))
    mid = (el + er) / 2
    return (V - mid) * s + np.asarray(eye_mid)


def hair_part(V, C, F, hair_colors, chin_z, shoulder_x, below=0.10, max_d=0.2):
    """the hair of an aligned generated character: faces coloured like the hair (nearest to hair_colors within max_d),
    above chin_z - `below` (world) and within the shoulders' width at the lowest part (so same-coloured sleeves and dress
    don't count). -> (verts, faces) of the hair part (re-indexed)."""
    lab, _ = classify(C, {'hair': hair_colors}, max_d=max_d)
    keep_v = (lab == 0) & (V[:, 2] > chin_z - below)
    low = V[:, 2] < chin_z + 0.02
    keep_v &= ~(low & (np.abs(V[:, 0]) > shoulder_x))
    fk = [f for f in F if sum(keep_v[v] for v in f) >= len(f) - 1]
    used = sorted({v for f in fk for v in f})
    remap = {o: n for n, o in enumerate(used)}
    return V[used], [tuple(remap[v] for v in f) for f in fk]


def hsv(C):
    """(N,3) sRGB -> hue (degrees), saturation, value."""
    C = np.asarray(C, float)
    mx, mn = C.max(1), C.min(1)
    d = mx - mn
    h = np.zeros(len(C))
    r, g, b = C[:, 0], C[:, 1], C[:, 2]
    m = d > 1e-6
    rr = m & (mx == r); gg = m & (mx == g) & ~rr; bb = m & ~rr & ~gg
    h[rr] = ((g - b)[rr] / d[rr]) % 6
    h[gg] = (b - r)[gg] / d[gg] + 2
    h[bb] = (r - g)[bb] / d[bb] + 4
    return h * 60, np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0), mx


def hair_by_hue(V, C, F, hue, chin_z, shoulder_x, below=0.1, sat=0.38, hue_tol=22.0):
    """the hair of an aligned generated character by hue and saturation (robust to its baked shading and highlights: the
    pale skin, whites and dark clothes fall out), above chin_z - `below`, within the shoulders low down. -> (verts, faces)."""
    h, s_, v_ = hsv(C)
    dh = np.abs(((h - hue) + 180) % 360 - 180)
    keep_v = (dh < hue_tol) & (s_ > sat) & (v_ > 0.25) & (V[:, 2] > chin_z - below)
    low = V[:, 2] < chin_z + 0.02
    keep_v &= ~(low & (np.abs(V[:, 0]) > shoulder_x))
    fk = [f for f in F if sum(keep_v[v] for v in f) >= len(f) - 1]
    used = sorted({v for f in fk for v in f})
    remap = {o: n for n, o in enumerate(used)}
    return V[used], [tuple(remap[v] for v in f) for f in fk]


def hair_by_exclusion(V, C, F, chin_z, shoulder_x, below=0.1, skin_sat=0.32, skin_val=0.6):
    """the hair of an aligned generated character as everything in the head region that isn't skin (pale, low-saturation
    warm texels: the face, ears, neck), cream or white (a collar, eye whites): hair keeps its baked highlights and
    shadows this way, so no holes. Above chin_z - `below`, within the shoulders low down. -> (verts, faces)."""
    h, s_, v_ = hsv(C)
    pale = (s_ < skin_sat) & (v_ > skin_val)
    keep_v = ~pale & (V[:, 2] > chin_z - below)
    low = V[:, 2] < chin_z + 0.02
    keep_v &= ~(low & (np.abs(V[:, 0]) > shoulder_x))
    fk = [f for f in F if sum(keep_v[v] for v in f) >= len(f) - 1]
    used = sorted({v for f in fk for v in f})
    remap = {o: n for n, o in enumerate(used)}
    return V[used], [tuple(remap[v] for v in f) for f in fk]


def hair_by_outside(V, C, F, body_v, body_f, chin_z, shoulder_x, below=0.1, clear=0.006, grow=2):
    """the hair of an aligned generated character by geometry: its surface lying clearly outside our own body (signed
    distance to our skin > `clear`) in the head region; the generated face and neck sit on our skin and fall away whatever
    their colour; below the chin, pale texels (a collar) are left out; then `grow` rings of neighbours close pinholes.
    Blender only (BVH). -> (verts, faces)."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    bvh = BVHTree.FromPolygons([Vector(v) for v in body_v], [tuple(f) for f in body_f])
    sd = np.full(len(V), 1.0)
    for i, p in enumerate(V):
        loc, nrm, _, dist = bvh.find_nearest(Vector(p))
        if loc is not None:
            sd[i] = (Vector(p) - loc).dot(nrm)
    h, s_, v_ = hsv(C)
    keep_v = (sd > clear) & (V[:, 2] > chin_z - below)
    low = V[:, 2] < chin_z + 0.02
    keep_v &= ~(low & (np.abs(V[:, 0]) > shoulder_x))
    keep_v &= ~(low & (s_ < 0.3) & (v_ > 0.6))
    region = (V[:, 2] > chin_z - below) & (sd > -clear)
    from collections import defaultdict
    nb = defaultdict(set)
    for f in F:
        for a, b in zip(f, tuple(f[1:]) + (f[0],)):
            nb[a].add(b); nb[b].add(a)
    for _ in range(grow):
        add = [w for v in np.nonzero(keep_v)[0] for w in nb[v] if region[w] and not keep_v[w]]
        keep_v[add] = True
    fk = [f for f in F if all(keep_v[v] for v in f)]
    used = sorted({v for f in fk for v in f})
    remap = {o: n for n, o in enumerate(used)}
    return V[used], [tuple(remap[v] for v in f) for f in fk]
