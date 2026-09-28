"""TRELLIS.2's decoded voxel fields as a file: <tag>_field.npz (format 'trellis2-field/1'), written next to the GLB by
tools/imageto3d/trellis_run.py, read here with numpy alone (scipy for the solid and signed distance).

What the decoder gives, at the final stage's resolution `res` (1024 for 1024_cascade; less when the cascade had to drop it
for its token budget): a SPARSE set of surface voxels (only voxels the surface passes through; there is no inside/outside
and no signed distance in TRELLIS.2's O-Voxel shape decoder), and per voxel:
    coords      (N,3) uint16   voxel index (i, j, k) along x, y, z
    dual        (N,3) uint8    the flexible-dual-grid vertex inside the voxel, in voxel units -0.5..1.5 (stored as
                               q/255*2 - 0.5; Field.dual is the float): the surface point p = aabb[0] + (coords + dual) *
                               voxel_size; these points ARE the raw mesh's vertices
    edge_logit  (N,3) int8     decoder logits x10 (clipped to +-12.7; Field.edge_logit is the float) that the voxel's x, y,
                               z primal edge (the one along its +y+z, +x+z, +x+y corner lines) crosses the surface; > 0 means
                               crossed, and a crossed edge makes one quad of the raw mesh
    split       (N,)  float16  the quad split weight (which diagonal a quad is cut along)
  and with the texture stage (else absent):
    base_color  (N,3) uint8    sRGB-encoded 0..255, exactly what the GLB's base-colour texture samples
    metallic, roughness, alpha (N,) uint8   0..255
  plus
    res, voxel_size (= 1/res), aabb [[-.5,-.5,-.5],[.5,.5,.5]]
    ss_coords (M,3) uint8, ss_res   the first stage's coarse occupancy (32^3 or 64^3)
    meta      JSON: seed, pipeline type, input images, multi-view mode, upstream commit, frame convention
Frame: TRELLIS.2's native one, z up, in the unit cube. The GLB stores (x, z, -y) (glTF is y up); Blender's glTF import turns
that back, so Blender coordinates of the imported GLB equal these. The character's front faces -y (see meta 'frame').

Derived here (not decoder outputs): a dense solid occupancy (flood fill from outside at a working resolution), a signed
distance (negative inside), the raw mesh rebuilt from the edge flags, previews.

    python tools/imageto3d/trellis_ext/field.py FIELD.npz [--out PNG] [--slices R]     # a preview sheet (and SDF slices)
    python tools/imageto3d/trellis_ext/field.py A.npz B.npz ... --out PNG                # rows side by side
"""
import json
import os
import numpy as np

FORMAT = 'trellis2-field/1'
AABB = np.array([[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]], np.float32)
FRAME = 'native TRELLIS.2: z up, unit cube, character front toward -y; GLB = (x, z, -y); Blender import of the GLB = native'


def save(path, fields, meta=None):
    """write a field dict (numpy arrays, as trellis_ext.pipeline.run returns them) and a meta dict."""
    m = dict(format=FORMAT, frame=FRAME)
    m.update(meta or {})
    np.savez_compressed(path, meta=np.array(json.dumps(m)), **fields)


class Field:
    """a <tag>_field.npz. Arrays as attributes (see the module docstring); `meta` a dict."""

    def __init__(self, path):
        z = np.load(path, allow_pickle=False)
        self.path = path
        self.meta = json.loads(str(z['meta']))
        if self.meta.get('format') != FORMAT:
            raise ValueError(f'{path}: not a {FORMAT} file')
        for k in z.files:
            if k != 'meta':
                setattr(self, k, z[k])
        if self.dual.dtype == np.uint8:                         # quantised (see the module docstring)
            self.dual = self.dual.astype(np.float32) * (2.0 / 255) - 0.5
        if self.edge_logit.dtype == np.int8:
            self.edge_logit = self.edge_logit.astype(np.float32) / 10
        self.res = int(self.res)
        self.voxel_size = float(self.voxel_size)
        self.aabb = np.asarray(self.aabb, np.float32)
        self.has_color = hasattr(self, 'base_color')

    def __len__(self):
        return len(self.coords)

    # --- per voxel ---------------------------------------------------------------------------------------------------
    def centers(self):
        """(N,3) world voxel centres."""
        return self.aabb[0] + (self.coords.astype(np.float32) + 0.5) * self.voxel_size

    def points(self):
        """(N,3) world surface points (the dual vertices)."""
        return self.aabb[0] + (self.coords.astype(np.float32) + self.dual.astype(np.float32)) * self.voxel_size

    def edges(self):
        """(N,3) bool: which of the voxel's x, y, z primal edges cross the surface."""
        return self.edge_logit > 0

    def colors(self):
        """(N,3) float sRGB 0..1 base colour (grey without the texture stage)."""
        if not self.has_color:
            return np.full((len(self), 3), 0.7, np.float32)
        return self.base_color.astype(np.float32) / 255

    # --- the raw mesh ------------------------------------------------------------------------------------------------
    def mesh(self):
        """the raw flexible-dual-grid mesh, rebuilt like o_voxel's flexible_dual_grid_to_mesh (numpy): one quad per crossed
        edge whose 4 surrounding voxels all exist, split along the diagonal the split weights choose. -> (V (N,3), F (M,3)).
        Faces are NOT consistently oriented (the decoder has no inside/outside), and thin parts are two-sided shells."""
        off = np.array([[[0, 0, 0], [0, 0, 1], [0, 1, 1], [0, 1, 0]],
                        [[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]],
                        [[0, 0, 0], [0, 1, 0], [1, 1, 0], [1, 0, 0]]], np.int64)
        c = self.coords.astype(np.int64)
        key = _key(c, self.res + 2)
        order = np.argsort(key)
        ks = key[order]
        quads = []
        E = self.edges()
        for a in range(3):
            src = np.nonzero(E[:, a])[0]
            nb = c[src][:, None, :] + off[a][None]                                  # (m,4,3)
            k = _key(nb.reshape(-1, 3), self.res + 2)
            pos = np.clip(np.searchsorted(ks, k), 0, len(ks) - 1)
            hit = (ks[pos] == k).reshape(-1, 4)
            idx = order[pos].reshape(-1, 4)
            quads.append(idx[hit.all(1)])
        q = np.concatenate(quads)
        s = self.split.astype(np.float32)
        w02, w13 = s[q[:, 0]] * s[q[:, 2]], s[q[:, 1]] * s[q[:, 3]]
        t1 = q[:, [0, 1, 2, 0, 2, 3]]
        t2 = q[:, [0, 1, 3, 3, 1, 2]]
        F = np.where((w02 > w13)[:, None], t1, t2).reshape(-1, 3)
        return self.points(), F

    # --- dense derivations -------------------------------------------------------------------------------------------
    def cell_index(self, R):
        """(N,3) index of each field voxel's surface point in an R^3 grid over the aabb."""
        g = (self.points() - self.aabb[0]) / (self.aabb[1] - self.aabb[0]) * R
        return np.clip(g.astype(np.int64), 0, R - 1)

    def dense(self, R=256):
        """the surface on an R^3 grid: dict(surface (R,R,R) bool, color (R,R,R,3) float sRGB mean of the voxels in each
        cell (0 elsewhere), count (R,R,R) int32, cell (N,3) the index of each field voxel)."""
        ci = self.cell_index(R)
        lin = (ci[:, 0] * R + ci[:, 1]) * R + ci[:, 2]
        cnt = np.bincount(lin, minlength=R ** 3).astype(np.int32)
        col = np.zeros((R ** 3, 3), np.float32)
        C = self.colors()
        for k in range(3):
            col[:, k] = np.bincount(lin, weights=C[:, k], minlength=R ** 3)
        col /= np.maximum(cnt, 1)[:, None]
        return dict(surface=(cnt > 0).reshape(R, R, R), color=col.reshape(R, R, R, 3), count=cnt.reshape(R, R, R),
                    cell=ci)

    def solid(self, R=256, close=1, surface=None, vote=0.9):
        """(R,R,R) bool occupancy: the surface cells (closed by `close` cells so pinholes don't leak), everything the
        outside can't reach, and, because generated shells are often open (a head crop's shoulders cut by the image
        frame, gaps between hair locks, eye sockets), every cell from which at least `vote` of the 26 axis and diagonal
        rays hit the surface (a discrete visibility vote; 0.9: at most 2 escape). The space under a skirt or between the
        legs stays outside: many rays escape there. Thin sheets become one or two cells thick at this resolution."""
        from scipy import ndimage
        S = self.dense(R)['surface'] if surface is None else surface
        if close > 0:
            st = ndimage.generate_binary_structure(3, 1)
            S = ndimage.binary_closing(np.pad(S, close + 1), st, iterations=close)[
                close + 1:-close - 1, close + 1:-close - 1, close + 1:-close - 1] | S
        solid = ndimage.binary_fill_holes(S)
        if vote:
            lo = np.maximum(np.argwhere(S).min(0) - 1, 0)
            hi = np.minimum(np.argwhere(S).max(0) + 2, R)
            box = tuple(slice(l, h) for l, h in zip(lo, hi))
            frac = ray_vote(ndimage.binary_dilation(S[box]))
            solid[box] |= frac >= vote
        return solid

    def sdf(self, R=256, band=3.0, close=1):
        """(R,R,R) float32 signed distance in world units at cell centres, negative inside the solid. Within `band` cells
        of the surface it is the distance to the nearest surface point (the dual vertices, sub-voxel), farther out the
        Euclidean distance transform of the solid. -> (sdf, solid)."""
        from scipy import ndimage
        from scipy.spatial import cKDTree
        solid = self.solid(R, close)
        cs = float(self.aabb[1, 0] - self.aabb[0, 0]) / R
        d = np.where(solid, ndimage.distance_transform_edt(solid), ndimage.distance_transform_edt(~solid)) * cs
        near = d < band * cs
        idx = np.argwhere(near)
        P = self.aabb[0] + (idx + 0.5) * cs
        du, _ = cKDTree(self.points()).query(P, k=1, workers=-1)
        d[near] = du
        return np.where(solid, -d, d).astype(np.float32), solid

    def cell_to_world(self, R, ijk):
        return self.aabb[0] + (np.asarray(ijk, np.float32) + 0.5) * float(self.aabb[1, 0] - self.aabb[0, 0]) / R


def ray_vote(S):
    """the fraction of the 26 grid directions (axes, face and space diagonals) in which a ray from each cell hits a
    True cell of S (stepping cell by cell, the cell itself excluded). -> (same shape) float32."""
    import itertools
    count = np.zeros(S.shape, np.uint8)
    dirs = [d for d in itertools.product((-1, 0, 1), repeat=3) if any(d)]
    for d in dirs:
        a = next(i for i in range(3) if d[i])
        Sa = np.moveaxis(S, a, 0)
        B = np.zeros_like(Sa)
        db, dc = [d[i] for i in range(3) if i != a]
        n = Sa.shape[0]
        for i in (range(n - 2, -1, -1) if d[a] > 0 else range(1, n)):
            j = i + d[a]
            B[i] = _shift2(Sa[j] | B[j], db, dc)
        count += np.moveaxis(B, 0, a)
    return count.astype(np.float32) / len(dirs)


def _shift2(x, db, dc):
    """out[u, v] = x[u + db, v + dc], False outside."""
    out = np.zeros_like(x)
    H, W = x.shape
    out[max(0, -db):H - max(0, db), max(0, -dc):W - max(0, dc)] = x[max(0, db):H - max(0, -db), max(0, dc):W - max(0, -dc)]
    return out


def _key(c, n):
    c = c + 1                                                   # neighbours at -1..res fit in 0..res+1
    return (c[:, 0] * n + c[:, 1]) * n + c[:, 2]


# --- rendering (numpy + PIL): orthographic point splats with screen-space shading ----------------------------------------
VIEWS = {  # camera: (right, up, toward-camera) axes in the native frame
    'front': ((1, 0, 0), (0, 0, 1), (0, -1, 0)),
    'right': ((0, 1, 0), (0, 0, 1), (1, 0, 0)),        # the character's left side, seen from +x
    'back': ((-1, 0, 0), (0, 0, 1), (0, 1, 0)),
    'left': ((0, -1, 0), (0, 0, 1), (-1, 0, 0)),
    'top': ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
    'three_quarter': ((0.7071, 0.7071, 0), (0, 0, 1), (0.7071, -0.7071, 0)),   # between front and right
}


def render_points(P, C, view='front', size=512, bg=(245, 245, 248), box=None, shade=True, radius=1):
    """P (N,3) world points, C (N,3) float 0..1 colours -> (size, size, 3) uint8. The frame is the unit cube (or `box`
    (lo, hi) in the view plane) so views of different samples line up. Nearest point per pixel wins; with `shade` the depth
    image's normals give a head-light Lambert term."""
    r, u, f = (np.asarray(a, np.float32) for a in (VIEWS[view] if isinstance(view, str) else view))
    x, y, d = P @ r, P @ u, P @ f                                                 # d: toward the camera
    lo, hi = box if box is not None else (-0.5, 0.5)
    px = ((x - lo) / (hi - lo) * (size - 1)).round().astype(np.int64)
    py = ((hi - y) / (hi - lo) * (size - 1)).round().astype(np.int64)
    img = np.empty((size, size, 3), np.float32); img[:] = np.asarray(bg, np.float32) / 255
    depth = np.full((size, size), -np.inf, np.float32)
    colr = np.zeros((size, size, 3), np.float32)
    for dy in range(-radius + 1, radius):
        for dx in range(-radius + 1, radius):
            qx, qy = px + dx, py + dy
            ok = (qx >= 0) & (qx < size) & (qy >= 0) & (qy < size)
            lin = qy[ok] * size + qx[ok]
            dd = d[ok]
            o = np.lexsort((-dd, lin))                           # per pixel, nearest first
            lin_o = lin[o]
            first = np.r_[True, lin_o[1:] != lin_o[:-1]]
            sel = o[first]
            L = lin[sel]
            better = dd[sel] > depth.ravel()[L]
            L, sel = L[better], sel[better]
            depth.ravel()[L] = dd[sel]
            colr.reshape(-1, 3)[L] = C[ok][sel]
    m = np.isfinite(depth)
    if shade and m.any():
        D = np.where(m, depth, np.nan)
        pix = (hi - lo) / size
        gy, gx = np.gradient(D / pix)
        n = np.stack([-gx, gy, np.ones_like(gx)], -1)
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        l = np.array([-0.35, 0.45, 0.82], np.float32); l /= np.linalg.norm(l)
        lam = np.nan_to_num(np.clip((n * l).sum(-1), 0, 1), nan=1.0)
        k = 0.45 + 0.55 * lam
        colr = colr * k[..., None]
    img[m] = colr[m]
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


def sheet(images, labels=None, pad=6, bg=(255, 255, 255)):
    """rows of equally sized images (list of lists of HxWx3 uint8) -> one image, optional text labels per tile."""
    from PIL import Image, ImageDraw
    rows = [r for r in images if r]
    h = max(im.shape[0] for r in rows for im in r)
    w = max(im.shape[1] for r in rows for im in r)
    ncol = max(len(r) for r in rows)
    out = Image.new('RGB', (ncol * (w + pad) + pad, len(rows) * (h + pad) + pad), bg)
    dr = ImageDraw.Draw(out)
    for ri, r in enumerate(rows):
        for ci, im in enumerate(r):
            x, y = pad + ci * (w + pad), pad + ri * (h + pad)
            out.paste(Image.fromarray(im), (x, y))
            if labels and labels[ri] and ci < len(labels[ri]) and labels[ri][ci]:
                dr.text((x + 6, y + 4), labels[ri][ci], fill=(40, 40, 40))
    return out


def preview(field, path, views=('front', 'three_quarter', 'right', 'back', 'top'), size=512):
    """a sheet of the field's surface points in base colour from several views (and grey-shaded geometry below)."""
    F = field if isinstance(field, Field) else Field(field)
    P, C = F.points(), F.colors()
    grey = np.full_like(C, 0.78)
    rows = [[render_points(P, C, v, size) for v in views], [render_points(P, grey, v, size) for v in views]]
    name = os.path.basename(F.path).replace('_field.npz', '')
    sheet(rows, [[f'{name}  {v}' for v in views], [f'{len(F)} voxels @ {F.res}^3' if i == 0 else '' for i in range(len(views))]]).save(path)
    return path


def compare(paths, path, views=('front', 'three_quarter', 'right', 'back'), size=384, grey=True):
    """one row per field (its base colour, then its geometry in grey), the same views and framing for all."""
    rows, labels = [], []
    for p in paths:
        F = p if isinstance(p, Field) else Field(p)
        P, C = F.points(), F.colors()
        name = os.path.basename(F.path).replace('_field.npz', '')
        rows.append([render_points(P, C, v, size) for v in views] +
                    ([render_points(P, np.full_like(C, 0.78), v, size) for v in views] if grey else []))
        labels.append([f'{name} {v}' if i == 0 else v for i, v in enumerate(views)] + ([''] * len(views) if grey else []))
    sheet(rows, labels).save(path)
    return path


def slices_png(field, path, R=256, n=6):
    """z- and y-slices of the dense signed distance (blue inside, red outside, black the surface cells)."""
    F = field if isinstance(field, Field) else Field(field)
    sdf, solid = F.sdf(R)
    surf = F.dense(R)['surface']
    cs = 1.0 / R
    lim = 12 * cs

    def tint(s, srf):
        t = np.clip(s / lim, -1, 1)
        rgb = np.ones(s.shape + (3,), np.float32)
        rgb[..., 0] = np.where(t < 0, 1 + t * 0.8, 1)
        rgb[..., 1] = 1 - np.abs(t) * 0.8
        rgb[..., 2] = np.where(t > 0, 1 - t * 0.8, 1)
        rgb[srf] = 0.1
        return (rgb * 255).astype(np.uint8)
    occ = np.argwhere(surf)
    zlo, zhi = occ[:, 2].min(), occ[:, 2].max()
    ylo, yhi = occ[:, 1].min(), occ[:, 1].max()
    zs = np.linspace(zlo, zhi, n + 2)[1:-1].astype(int)[::-1]
    ys = np.linspace(ylo, yhi, n + 2)[1:-1].astype(int)
    row1 = [tint(sdf[:, :, z].T[::-1], surf[:, :, z].T[::-1]) for z in zs]          # top view: x right, y up
    row2 = [tint(sdf[:, y, :].T[::-1], surf[:, y, :].T[::-1]) for y in ys]          # front view: x right, z up
    labels = [[f'z={F.cell_to_world(R, [0, 0, z])[2]:+.3f}' for z in zs], [f'y={F.cell_to_world(R, [0, y, 0])[1]:+.3f}' for y in ys]]
    sheet([row1, row2], labels).save(path)
    return path


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='preview a trellis2 field npz (several: a comparison sheet, one row each)')
    ap.add_argument('npz', nargs='+')
    ap.add_argument('--out', help='PNG (default: next to the npz)')
    ap.add_argument('--slices', type=int, default=0, help='also write SDF slices at this working resolution')
    a = ap.parse_args()
    if len(a.npz) > 1:
        print(compare(a.npz, a.out or 'compare.png'))
        raise SystemExit
    a.npz = a.npz[0]
    F = Field(a.npz)
    out = a.out or a.npz.replace('.npz', '.png')
    print(preview(F, out))
    if a.slices:
        print(slices_png(F, out.replace('.png', '_slices.png'), a.slices))
