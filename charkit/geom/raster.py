"""A small z-buffer rasteriser in numpy/numba for measuring and looking at meshes without Blender: orthographic views round
the character by azimuth (qa3d's convention: az 0 looks at the front from -y, x to the right, z up), silhouettes, IoU, and
shaded renders (flat / lambert / toon from per-vertex normals, optional vertex colours) saved as PNG.

    fr = Frame.around([mesh1, mesh2], res=512)            # one framing shared by everything compared
    m = silhouette(mesh, 45, fr)                           # bool (H, W)
    img = render([(mesh, dict(color=(0.9, 0.5, 0.3), normals=vn, shade='toon'))], 45, fr)
    save_png(img, 'out.png')
"""
import math

import numpy as np
import numba as nb

from .mesh import as_mesh, vertex_normals


class Frame:
    """an orthographic framing: world centre (x, z at the image centre), `scale` world units across the image height,
    resolution (W, H)."""

    def __init__(self, centre, scale, res=(512, 512)):
        self.centre = np.asarray(centre, float)
        self.scale = float(scale)
        self.res = (int(res[0]), int(res[1]))

    @classmethod
    def around(cls, meshes, res=512, margin=1.08, aspect=None):
        P = np.vstack([as_mesh(m).V for m in meshes])
        lo, hi = P.min(0), P.max(0)
        c = (lo + hi) / 2
        rad = np.linalg.norm((hi - lo)[:2]) / 2                   # any azimuth fits horizontally
        hz = hi[2] - lo[2]
        if aspect is None:
            aspect = max(0.3, min(3.0, 2 * rad / max(hz, 1e-9)))
        scale = max(hz, 2 * rad / aspect) * margin
        H = int(res)
        W = int(round(res * aspect))
        return cls(c, scale, (W, H))

    def basis(self, az, el=0.0):
        a, e = math.radians(az), math.radians(el)
        d = np.array([-math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), -math.sin(e)])  # view direction
        right = np.array([math.cos(a), math.sin(a), 0.0])
        up = np.cross(right, d)
        return right, up, d

    def project(self, V, az, el=0.0):
        """-> (pixel xy (N,2) float, depth (N,) larger = farther)."""
        right, up, d = self.basis(az, el)
        Q = V - self.centre
        W, H = self.res
        s = H / self.scale
        x = Q @ right * s + W / 2
        y = -(Q @ up) * s + H / 2
        return np.stack([x, y], 1), Q @ d


@nb.njit(cache=True, error_model='numpy')
def _raster(P2, depth, F, W, H):
    zb = np.full((H, W), np.inf)
    fb = np.full((H, W), -1, np.int64)
    b1 = np.zeros((H, W)); b2 = np.zeros((H, W))
    for t in range(F.shape[0]):
        a, b, c = F[t, 0], F[t, 1], F[t, 2]
        ax, ay = P2[a, 0], P2[a, 1]
        bx, by = P2[b, 0], P2[b, 1]
        cx, cy = P2[c, 0], P2[c, 1]
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if not (abs(den) >= 1e-12):                 # (also skips nan)
            continue
        if not (math.isfinite(ax) and math.isfinite(bx) and math.isfinite(cx) and math.isfinite(ay) and
                math.isfinite(by) and math.isfinite(cy)):
            continue
        x0 = int(max(0.0, math.floor(min(ax, bx, cx))))
        x1 = int(min(W - 1.0, math.ceil(max(ax, bx, cx))))
        y0 = int(max(0.0, math.floor(min(ay, by, cy))))
        y1 = int(min(H - 1.0, math.ceil(max(ay, by, cy))))
        for py in range(y0, y1 + 1):
            yy = py + 0.5
            for px in range(x0, x1 + 1):
                xx = px + 0.5
                l1 = ((by - cy) * (xx - cx) + (cx - bx) * (yy - cy)) / den
                l2 = ((cy - ay) * (xx - cx) + (ax - cx) * (yy - cy)) / den
                l3 = 1.0 - l1 - l2
                if l1 < -1e-9 or l2 < -1e-9 or l3 < -1e-9:
                    continue
                z = l1 * depth[a] + l2 * depth[b] + l3 * depth[c]
                if z < zb[py, px]:
                    zb[py, px] = z; fb[py, px] = t; b1[py, px] = l1; b2[py, px] = l2
    return zb, fb, b1, b2


@nb.njit(cache=True, error_model='numpy')
def _raster_thin(P2, depth, F, thin, W, H):
    """_raster, with the triangles flagged thin splatted instead: sampled on a barycentric grid under 0.6 px apart, each
    sample claiming its pixel (every pixel the triangle reaches into keeps it: a thin line stays at least a pixel wide,
    as a drawn stroke does; charkit.faceqa.zbuffer_splat's rule)."""
    zb = np.full((H, W), np.inf)
    fb = np.full((H, W), -1, np.int64)
    b1 = np.zeros((H, W)); b2 = np.zeros((H, W))
    for t in range(F.shape[0]):
        a, b, c = F[t, 0], F[t, 1], F[t, 2]
        ax, ay = P2[a, 0], P2[a, 1]
        bx, by = P2[b, 0], P2[b, 1]
        cx, cy = P2[c, 0], P2[c, 1]
        if not (math.isfinite(ax) and math.isfinite(bx) and math.isfinite(cx) and math.isfinite(ay) and
                math.isfinite(by) and math.isfinite(cy)):
            continue
        if thin[t] != 0:
            e = max(math.hypot(ax - bx, ay - by), math.hypot(bx - cx, by - cy), math.hypot(cx - ax, cy - ay))
            k = min(64, max(1, int(math.ceil(e / 0.6))))
            for i in range(k + 1):
                for j in range(k + 1 - i):
                    w1, w2 = i / k, j / k
                    w0 = 1.0 - w1 - w2
                    px = int(math.floor(ax * w0 + bx * w1 + cx * w2))
                    py = int(math.floor(ay * w0 + by * w1 + cy * w2))
                    if px < 0 or px >= W or py < 0 or py >= H:
                        continue
                    z = depth[a] * w0 + depth[b] * w1 + depth[c] * w2
                    if z < zb[py, px]:
                        zb[py, px] = z; fb[py, px] = t; b1[py, px] = w0; b2[py, px] = w1
            continue
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if not (abs(den) >= 1e-12):
            continue
        x0 = int(max(0.0, math.floor(min(ax, bx, cx))))
        x1 = int(min(W - 1.0, math.ceil(max(ax, bx, cx))))
        y0 = int(max(0.0, math.floor(min(ay, by, cy))))
        y1 = int(min(H - 1.0, math.ceil(max(ay, by, cy))))
        for py in range(y0, y1 + 1):
            yy = py + 0.5
            for px in range(x0, x1 + 1):
                xx = px + 0.5
                l1 = ((by - cy) * (xx - cx) + (cx - bx) * (yy - cy)) / den
                l2 = ((cy - ay) * (xx - cx) + (ax - cx) * (yy - cy)) / den
                l3 = 1.0 - l1 - l2
                if l1 < -1e-9 or l2 < -1e-9 or l3 < -1e-9:
                    continue
                z = l1 * depth[a] + l2 * depth[b] + l3 * depth[c]
                if z < zb[py, px]:
                    zb[py, px] = z; fb[py, px] = t; b1[py, px] = l1; b2[py, px] = l2
    return zb, fb, b1, b2


def rasterize(m, az, frame, el=0.0):
    """-> (zbuffer (H,W) inf where empty, face id (-1), barycentrics (H,W,3))."""
    m = as_mesh(m)
    P2, dep = frame.project(m.V, az, el)
    W, H = frame.res
    zb, fb, b1, b2 = _raster(np.ascontiguousarray(P2), np.ascontiguousarray(dep), np.ascontiguousarray(m.F), W, H)
    return zb, fb, np.stack([b1, b2, 1 - b1 - b2], -1)


def silhouette(m, az, frame, el=0.0):
    return rasterize(m, az, frame, el)[1] >= 0


# --------------------------------------------------------------------------------------------- windows round a point
def window_shape(pix, win):
    """a measuring window's pixel size (W, H): win = dict(x, top, bottom) in units of L round the origin."""
    return int(round(2 * win['x'] / pix)), int(round((win['top'] - win['bottom']) / pix))


def window_project(V, az, origin, L, pix, win):
    """world points -> (pixel x, y (N, 2), depth along the view (N,), smaller = nearer) on a measuring window: the
    camera at azimuth az (charkit.faceqa.view's convention), the window centred on origin (u, z world), pix and win in
    units of L; pixel (r, c) spans u in [c pix - win.x, (c + 1) pix - win.x) L round origin, z likewise from win.top."""
    a = np.radians(az)
    V = np.asarray(V, float)
    u = V[:, 0] * np.cos(a) + V[:, 1] * np.sin(a)
    d = -V[:, 0] * np.sin(a) + V[:, 1] * np.cos(a)
    x = ((u - origin[0]) / L + win['x']) / pix
    y = (win['top'] - (V[:, 2] - origin[1]) / L) / pix
    return np.stack([x, y], 1), d


def facing(V, T, az):
    """per triangle: does its front (counter-clockwise winding, Blender's) face a camera at azimuth az?"""
    a = np.radians(az)
    d = np.array([-np.sin(a), np.cos(a), 0.0])                        # the view direction, into the scene
    V = np.asarray(V, float)
    n = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    return n @ d < 0


def window_zbuffer(meshes, az, origin, L, pix, win, ids=False, thin=()):
    """the nearest surface per pixel centre of a measuring window (window_project), every mesh occluding every other:
    meshes [(V world, tris, per-triangle label)] or [(V, tris, labels, cull)] where cull (per triangle, or one bool)
    drops a triangle whose back faces the camera (a back-face-culled material). thin: labels drawn at least a pixel wide
    (every pixel a triangle touches: lines and brows, as a drawing's strokes are). -> (depth (H, W), inf where empty;
    label (H, W), -1 where empty), and with ids also (mesh index, triangle index in its mesh, barycentric weights
    (H, W, 3) of its corners), -1 / 0 where empty. Ties (coplanar surfaces) go to the earlier mesh."""
    W, H = window_shape(pix, win)
    Ps, Ds, Ts, labs, owner, local, off = [], [], [], [], [], [], 0
    for k, m in enumerate(meshes):
        V, T, lab = m[0], np.asarray(m[1]), m[2]
        cull = m[3] if len(m) > 3 else None
        if not len(T):
            continue
        P2, d = window_project(V, az, origin, L, pix, win)
        tx, ty = P2[T, 0], P2[T, 1]
        keep = (tx.max(1) >= -0.5) & (tx.min(1) <= W + 0.5) & (ty.max(1) >= -0.5) & (ty.min(1) <= H + 0.5)
        if cull is not None and np.any(cull):
            keep &= ~(np.broadcast_to(np.asarray(cull, bool), (len(T),)) & ~facing(V, T, az))
        sel = np.nonzero(keep)[0]
        if not len(sel):
            continue
        Ps.append(P2); Ds.append(d); Ts.append(T[sel] + off)
        labs.append(np.broadcast_to(np.asarray(lab), (len(T),))[sel]); owner.append(np.full(len(sel), k)); local.append(sel)
        off += len(V)
    if not Ts:
        z, lab = np.full((H, W), np.inf), np.full((H, W), -1)
        if ids:
            return z, lab, np.full((H, W), -1), np.zeros((H, W), np.int64), np.zeros((H, W, 3))
        return z, lab
    P2, dep, T = np.concatenate(Ps), np.concatenate(Ds), np.concatenate(Ts)
    L_ = np.concatenate(labs).astype(np.int64)
    args = (np.ascontiguousarray(P2), np.ascontiguousarray(dep), np.ascontiguousarray(T, np.int64))
    th = np.isin(L_, list(thin)) if len(thin) else None
    if th is not None and th.any():
        zb, fb, b1, b2 = _raster_thin(*args, th.astype(np.uint8), W, H)
    else:
        zb, fb, b1, b2 = _raster(*args, W, H)
    hit = fb >= 0
    lab = np.full((H, W), -1, np.int64)
    lab[hit] = L_[fb[hit]]
    if not ids:
        return zb, lab
    ow, lo = np.concatenate(owner), np.concatenate(local)
    mi = np.full((H, W), -1); ti = np.zeros((H, W), np.int64)
    mi[hit] = ow[fb[hit]]; ti[hit] = lo[fb[hit]]
    return zb, lab, mi, ti, np.stack([b1, b2, 1 - b1 - b2], -1)


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 1.0


def overlay(a, b):
    """an RGB float image: both (grey), only a (red), only b (blue)."""
    img = np.full(a.shape + (3,), 0.93)
    img[a & b] = (0.55, 0.55, 0.6); img[a & ~b] = (0.9, 0.2, 0.2); img[b & ~a] = (0.2, 0.35, 0.95)
    return img


def render(items, az, frame, el=0.0, bg=(0.93, 0.93, 0.95), light=(-0.45, 0.55, 0.7), outline=True, light_world=None):
    """shade meshes together (one z-buffer). items: [(mesh, opts)], opts: color (rgb or per-vertex (N,3)), normals (per
    vertex; default the mesh's vn or angle-weighted), shade 'toon' | 'lambert' | 'flat' | 'normal', line (outline colour).
    -> RGB float (H, W, 3)."""
    W, H = frame.res
    zb = np.full((H, W), np.inf)
    img = np.empty((H, W, 3)); img[:] = bg
    obj = np.full((H, W), -1)
    L = np.asarray(light, float); L /= np.linalg.norm(L)
    right, up, d = frame.basis(az, el)
    for k, (m, o) in enumerate(items):
        m = as_mesh(m)
        z, fb, bc = rasterize(m, az, frame, el)
        hit = (fb >= 0) & (z < zb)
        if not hit.any():
            continue
        f = fb[hit]
        w = bc[hit]
        N = o.get('normals')
        if N is None:
            N = m.vn if m.vn is not None else vertex_normals(m.V, m.F)
        shade = o.get('shade', 'lambert')
        if shade == 'flat':
            from .mesh import face_normals
            n = face_normals(m.V, m.F)[f]
        else:
            n = np.einsum('pk,pkd->pd', w, N[m.F[f]])
            n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        col = o.get('color', (0.8, 0.8, 0.82))
        col = np.asarray(col, float)
        if col.ndim == 2:
            c = np.einsum('pk,pkd->pd', w, col[m.F[f]])
        else:
            c = np.broadcast_to(col, (len(f), 3))
        # the light is fixed to the camera: (right, up, toward the camera); default from the upper left front
        if light_world is not None:
            Lw = np.asarray(light_world, float)
        else:
            Lw = right * L[0] + up * L[1] - d * L[2]
        Lw /= np.linalg.norm(Lw)
        ndl = n @ Lw
        if shade == 'normal':
            out = n * 0.5 + 0.5
        elif shade == 'toon' and light_world is not None:
            half = 0.5 * ndl + 0.5                                # charkit.shade.toon3's steps
            tone = np.where(half > 0.5, 1.0, np.where(half > 0.27, 0.74, 0.55))
            out = c * tone[:, None]
        elif shade == 'toon':
            tone = np.where(ndl > 0.15, 1.0, np.where(ndl > -0.35, 0.74, 0.55))
            out = c * tone[:, None]
        else:
            out = c * (0.35 + 0.65 * np.clip(ndl, 0, 1))[:, None]
        img[hit] = np.clip(out, 0, 1)
        zb[hit] = z[hit]
        obj[hit] = k
    if outline:
        # object and depth-discontinuity edges
        e = np.zeros((H, W), bool)
        e[:, 1:] |= obj[:, 1:] != obj[:, :-1]; e[1:] |= obj[1:] != obj[:-1]
        zf = np.where(np.isfinite(zb), zb, 1e9)
        thr = 0.02 * frame.scale
        e[:, 1:] |= np.abs(zf[:, 1:] - zf[:, :-1]) > thr; e[1:] |= np.abs(zf[1:] - zf[:-1]) > thr
        img[e] = img[e] * 0.35
    return img


def save_png(img, path):
    from PIL import Image
    import os
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    a = np.clip(np.asarray(img, float), 0, 1)
    if a.ndim == 2:
        a = np.repeat(a[..., None], 3, -1)
    Image.fromarray((a * 255 + 0.5).astype(np.uint8)).save(path)
    return path


def sheet(images, cols=None, pad=4, bg=1.0):
    """tile equally sized images (H, W, 3) into one."""
    n = len(images)
    cols = cols or n
    rows = (n + cols - 1) // cols
    H, W = images[0].shape[:2]
    out = np.full((rows * H + (rows - 1) * pad, cols * W + (cols - 1) * pad, 3), bg, float)
    for i, im in enumerate(images):
        r, c = divmod(i, cols)
        out[r * (H + pad):r * (H + pad) + H, c * (W + pad):c * (W + pad) + W] = im[..., :3]
    return out
