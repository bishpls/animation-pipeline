"""Image-to-3D results as kit data (docs/CHARKIT.md §5): a TRELLIS.2 GLB (tools/imageto3d) imported, turned to face the kit's
front (the view whose outline best matches the input image's alpha), scaled and placed in head space from the design's own
measurements (charkit.refs: pixels per head length, the eyes), its vertices coloured from the base-colour texture, and split
into parts by colour (hair, skin, ...). The hair part becomes charkit.hair's volume (MeshVolume); the head can be a wrap
target for charkit.anime_head.
"""
import math
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
        V.append(v); C.append(col)
        F += [tuple(off + i for i in p.vertices) for p in me.polygons]
        off += len(v)
    for ob in list(bpy.data.objects):
        if ob not in before:
            bpy.data.objects.remove(ob, do_unlink=True)
    return np.vstack(V), F, np.vstack(C)
