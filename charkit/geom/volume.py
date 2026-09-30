"""Volumes: meshes to voxel grids and back, and boolean / morphological operations on them, with world-space voxel size.

A Grid holds voxel-centre samples on a regular lattice: `origin` is the world position of voxel (0, 0, 0)'s centre, `h`
the voxel size, `data` (nx, ny, nz) either bool occupancy or float32 signed distance (negative inside). Grids made with
the same h are snapped to the world lattice (origin a multiple of h), so grids from different meshes line up exactly and
combine voxel for voxel.

    G = occupancy(mesh, h=0.002)                 # winding number (robust to holes and open or messy input), or 'parity'
    S = sdf(mesh, h=0.002)                       # exact distances near the surface, EDT far away, sign by winding number
    m = to_mesh(S)                               # marching cubes -> a closed, consistently oriented Mesh
    union(a, b), intersection(a, b), difference(a, b), dilate(S, r), erode(S, r), opening, closing, blur
    fill_cavities(G), keep_components(G, ...), restrict(G, mask_fn)
"""
import numpy as np

from .mesh import Mesh, as_mesh


class Grid:
    __slots__ = ('origin', 'h', 'data')

    def __init__(self, origin, h, data):
        self.origin = np.asarray(origin, np.float64)
        self.h = float(h)
        self.data = data

    @property
    def shape(self):
        return self.data.shape

    @property
    def is_sdf(self):
        return self.data.dtype != np.bool_

    def like(self, data):
        return Grid(self.origin.copy(), self.h, data)

    def axes(self):
        return [self.origin[k] + self.h * np.arange(self.shape[k]) for k in range(3)]

    def points(self, idx=None):
        """world positions of voxel centres: all (as (N,3) in C order) or of an (N,3) index array / flat indices."""
        if idx is None:
            ax = self.axes()
            X, Y, Z = np.meshgrid(*ax, indexing='ij')
            return np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
        idx = np.asarray(idx)
        if idx.ndim == 1:
            idx = np.stack(np.unravel_index(idx, self.shape), 1)
        return self.origin + idx * self.h

    def index(self, P):
        """continuous voxel coordinates of world points."""
        return (np.asarray(P, float) - self.origin) / self.h

    def bounds(self):
        return self.origin - self.h / 2, self.origin + self.h * (np.array(self.shape) - 0.5)

    def sample(self, P, outside=None):
        """trilinear interpolation of an SDF grid (occupancy as 0/1) at world points; `outside` beyond the grid (default:
        the nearest voxel)."""
        from scipy.ndimage import map_coordinates
        X = self.index(P).T
        d = self.data.astype(np.float32) if self.data.dtype == np.bool_ else self.data
        if outside is None:
            return map_coordinates(d, X, order=1, mode='nearest')
        return map_coordinates(d, X, order=1, mode='constant', cval=outside)

    def gradient(self, P):
        """the grid's trilinear gradient (world units) at points (central differences of the SDF)."""
        g = np.gradient(self.data.astype(np.float32), self.h)
        from scipy.ndimage import map_coordinates
        X = self.index(P).T
        return np.stack([map_coordinates(gk, X, order=1, mode='nearest') for gk in g], 1)

    def occupancy(self):
        return self.data if self.data.dtype == np.bool_ else self.data < 0

    def voxel_volume(self):
        return float(self.occupancy().sum()) * self.h ** 3

    def __repr__(self):
        return f'Grid({self.shape}, h={self.h:g}, {"sdf" if self.is_sdf else "occupancy"})'


def lattice(lo, hi, h, pad=2):
    """an empty Grid (float32 zeros) covering [lo, hi] plus `pad` voxels, snapped to the world lattice of spacing h."""
    lo = np.floor(np.asarray(lo, float) / h - pad) * h
    hi = np.ceil(np.asarray(hi, float) / h + pad) * h
    shape = tuple(int(x) for x in np.round((hi - lo) / h).astype(int) + 1)
    return Grid(lo, h, np.zeros(shape, np.float32))


def grid_for(m, h, pad=3, bounds=None):
    m = as_mesh(m)
    lo, hi = (m.bounds() if bounds is None else bounds)
    return lattice(lo, hi, h, pad)


# ------------------------------------------------------------------------------------------------------- mesh -> occupancy
def _surface_voxels(m, G, spacing=0.5):
    """voxels the surface passes through (dense barycentric samples on each triangle at <= spacing * h)."""
    V, F = m.V, m.F
    T = V[F]
    lo, hi = G.bounds()
    inb = np.all((T.max(1) >= lo - G.h) & (T.min(1) <= hi + G.h), axis=1)
    T = T[inb]
    L = np.max(np.linalg.norm(T - np.roll(T, 1, axis=1), axis=2), axis=1)
    k = np.maximum(1, np.ceil(L / (spacing * G.h))).astype(np.int64)
    out = np.zeros(G.shape, bool)
    shape = np.array(G.shape)
    for kk in np.unique(k):
        sel = np.nonzero(k == kk)[0]
        i, j = np.meshgrid(np.arange(kk + 1), np.arange(kk + 1), indexing='ij')
        ok = (i + j) <= kk
        a = (i[ok] / kk); b = (j[ok] / kk); c = 1 - a - b
        W = np.stack([c, a, b], 1)                          # (S,3)
        for chunk in np.array_split(sel, max(1, len(sel) * len(W) // 2_000_000 + 1)):
            P = np.einsum('sk,tkd->tsd', W, T[chunk]).reshape(-1, 3)
            I = np.round(G.index(P)).astype(np.int64)
            good = np.all((I >= 0) & (I < shape), axis=1)
            I = I[good]
            out[I[:, 0], I[:, 1], I[:, 2]] = True
    return out


def occupancy(m, h=None, grid=None, method='winding', beta=2.0, fast=True, pad=3):
    """voxel occupancy of a mesh (a bool Grid). method:
      'winding'  generalised winding number > 0.5 (robust to holes, open parts, self-intersections and double layers;
                 needs outward orientation; run repair.orient first if the input's winding is inconsistent)
      'parity'   ray crossings along +x, +y and +z per voxel column, majority vote (orientation-free; leaks where a hole
                 lines up with a column on two axes)
    fast: evaluate every voxel near the surface, and far from it one decision per connected region (checked at several of
    its voxels; any disagreement evaluates the whole region)."""
    m = as_mesh(m)
    G = grid if grid is not None else grid_for(m, h, pad)
    if method == 'parity':
        return G.like(_parity(m, G))
    from .bvh import BVH
    B = BVH(m)
    if not fast:
        w = B.winding_number(G.points(), beta).reshape(G.shape)
        return G.like(w > 0.5)
    from scipy import ndimage as ndi
    near = ndi.binary_dilation(_surface_voxels(m, G), iterations=1)
    occ = np.zeros(G.shape, bool)
    ni = np.flatnonzero(near)
    occ.flat[ni] = B.winding_number(G.points(ni), beta) > 0.5
    lab, n = ndi.label(~near)
    if n:
        # a few voxels per region (deterministic: evenly spaced through its voxel list)
        flat = lab.ravel()
        order = np.argsort(flat, kind='stable')
        cnt = np.bincount(flat, minlength=n + 1)
        starts = np.r_[0, np.cumsum(cnt)[:-1]]
        picks, owner = [], []
        for r in range(1, n + 1):
            c = cnt[r]
            k = min(c, 8)
            sel = order[starts[r] + np.linspace(0, c - 1, k).astype(np.int64)]
            picks.append(sel); owner.append(np.full(k, r))
        picks = np.concatenate(picks); owner = np.concatenate(owner)
        w = B.winding_number(G.points(picks), beta)
        ins = w > 0.5
        all_in = np.bincount(owner, weights=ins, minlength=n + 1)
        tot = np.bincount(owner, minlength=n + 1)
        mixed = (all_in > 0) & (all_in < tot)
        region_in = (all_in == tot) & (tot > 0)
        fill = region_in[lab] & ~near
        occ |= fill
        for r in np.nonzero(mixed)[0]:
            idx = np.flatnonzero(lab == r)
            occ.flat[idx] = B.winding_number(G.points(idx), beta) > 0.5
    return G.like(occ)


def _parity(m, G):
    from .bvh import BVH
    B = BVH(m)
    votes = np.zeros(G.shape, np.int8)
    ax_pts = G.axes()
    lo, hi = G.bounds()
    for ax in range(3):
        u, v = [k for k in range(3) if k != ax]
        U, W = np.meshgrid(ax_pts[u], ax_pts[v], indexing='ij')
        O = np.zeros((U.size, 3))
        O[:, u] = U.ravel(); O[:, v] = W.ravel(); O[:, ax] = lo[ax] - 10 * G.h
        # a tiny deterministic tilt-free jitter off the lattice keeps rays off shared edges and vertices
        O[:, u] += G.h * 1e-3 * np.sqrt(2); O[:, v] += G.h * 1e-3 * np.sqrt(3)
        D = np.zeros(3); D[ax] = 1.0
        hits = _all_hits(B, O, D)
        coords = ax_pts[ax]
        inside = np.zeros((U.size, len(coords)), bool)
        for i, t in enumerate(hits):
            if len(t) < 2:
                continue
            z = O[i, ax] + np.sort(t)
            n_below = np.searchsorted(z, coords)
            inside[i] = (n_below % 2) == 1
        inside = inside.reshape(U.shape[0], U.shape[1], len(coords))
        votes += np.moveaxis(inside, 2, ax).astype(np.int8)
    return votes >= 2


def _all_hits(B, O, D):
    """every hit distance along each ray (list of arrays)."""
    off, T = B.ray_hits(O, D)
    return [T[off[i]:off[i + 1]] for i in range(len(off) - 1)]


# ------------------------------------------------------------------------------------------------------------- distances
def signed_edt(occ, h):
    """a signed distance from an occupancy grid (negative inside), voxel-centre based: the distance to the nearest voxel of
    the other kind, minus half a voxel so the zero level sits between them."""
    from scipy.ndimage import distance_transform_edt as edt
    occ = np.asarray(occ, bool)
    if occ.all() or not occ.any():
        return np.full(occ.shape, -1e3 * h if occ.all() else 1e3 * h, np.float32)
    dout = edt(~occ) * h
    din = edt(occ) * h
    return np.where(occ, -(din - 0.5 * h), dout - 0.5 * h).astype(np.float32)


def sdf(m, h=None, grid=None, band=3.0, occ=None, beta=2.0, pad=3):
    """a signed distance grid (float32, negative inside) of a mesh: exact distances (BVH) within `band` voxels of the
    surface, the EDT of the occupancy beyond; the sign from the winding number (occupancy()), or from `occ` if given."""
    m = as_mesh(m)
    G = grid if grid is not None else grid_for(m, h, pad=max(pad, int(np.ceil(band)) + 1))
    O = occupancy(m, grid=G, beta=beta) if occ is None else occ
    occ_ = O.data if isinstance(O, Grid) else np.asarray(O, bool)
    D = signed_edt(occ_, G.h)
    from .bvh import BVH
    B = BVH(m)
    near = np.flatnonzero(np.abs(D) < (band + 1) * G.h)
    d, _, _ = B.nearest(G.points(near))
    sgn = np.where(occ_.flat[near], -1.0, 1.0)
    D.flat[near] = (d * sgn).astype(np.float32)
    return G.like(D)


def thicken(m, r, h=None, grid=None, pad=3):
    """a closed solid around a surface (open sheets, single or double-walled, any orientation): everything within r of
    it, as an exact signed distance (unsigned distance - r) in a narrow band. The robust 'solidify'. -> SDF Grid."""
    from scipy import ndimage as ndi
    from .bvh import BVH
    m = as_mesh(m)
    G = grid if grid is not None else grid_for(m, h, pad=pad + int(np.ceil(r / h)))
    k = int(np.ceil(r / G.h)) + 2
    near = ndi.binary_dilation(_surface_voxels(m, G), iterations=k)
    D = np.full(G.shape, np.float32(k * G.h), np.float32)
    idx = np.flatnonzero(near)
    d, _, _ = BVH(m).nearest(G.points(idx))
    D.flat[idx] = (d - r).astype(np.float32)
    return G.like(D)


def as_sdf(G, blur=0.0):
    """an SDF grid from an occupancy grid (signed EDT, optionally Gaussian-blurred by `blur` voxels); SDFs pass through."""
    if G.is_sdf:
        D = G.data
    else:
        D = signed_edt(G.data, G.h)
    if blur > 0:
        from . import det                   # the same bits on every machine: marching cubes thresholds this
        D = det.gaussian(D, blur, mode='nearest')
    return G.like(D.astype(np.float32))


def redistance(G):
    """rebuild a clean SDF (EDT of the zero level set's occupancy, exact-ish only to a voxel)."""
    return G.like(signed_edt(G.occupancy(), G.h))


# ---------------------------------------------------------------------------------------------------------- mesh from grid
def to_mesh(G, level=0.0, blur=0.0, step=1, keep_border_closed=True):
    """marching cubes (scikit-image, Lewiner) of an SDF grid at `level` (occupancy grids go through a signed EDT, blurred
    by `blur` voxels to lose the stair steps). The grid is padded with outside values, so the result is closed; faces are
    wound outward. -> Mesh (world units)."""
    from skimage.measure import marching_cubes
    S = as_sdf(G, blur)
    D = S.data
    if keep_border_closed:
        D = np.pad(D, 1, mode='constant', constant_values=max(float(D.max()), level + S.h))
        org = S.origin - S.h
    else:
        org = S.origin
    if not (D.min() < level < D.max()):
        return Mesh(np.zeros((0, 3)), np.zeros((0, 3), np.int64))
    # samples exactly at the level make degenerate triangles (and, dropped, non-manifold edges): nudge them outside
    eq = D == level
    if eq.any():
        D = D.copy()
        D[eq] = level + 1e-6 * S.h
    v, f, n, _ = marching_cubes(D, level=level, spacing=(S.h,) * 3, step_size=step, allow_degenerate=False,
                                method='lewiner')
    m = Mesh(v + org, f.astype(np.int64))
    # scikit-image can emit a coincident pair of opposite triangles (a flat zero-volume pocket) in rare cell
    # configurations: drop such pairs (and any repeated vertex), which leaves the surface closed and manifold
    from .repair import clean
    m = clean(m)
    from .mesh import signed_volume
    if signed_volume(m.V, m.F) < 0:
        m = m.with_(F=m.F[:, ::-1].copy())
    return m


# ------------------------------------------------------------------------------------------------------------- booleans
def common(a, b):
    """a and b resampled onto one lattice covering both (same h: exact index shifts; else b is trilinearly resampled onto a's
    spacing). -> (A data, B data, Grid template)."""
    h = a.h
    lo = np.minimum(a.bounds()[0], b.bounds()[0]) + h / 2
    hi = np.maximum(a.bounds()[1], b.bounds()[1]) - h / 2
    T = lattice(lo, hi, h, pad=0)
    return _onto(a, T), _onto(b, T), T


def _onto(g, T):
    """g's data on T's lattice (outside values beyond g: False, or the SDF's max)."""
    if abs(g.h - T.h) < 1e-12 * T.h:
        off = np.round((g.origin - T.origin) / T.h).astype(int)
        if np.allclose(g.origin, T.origin + off * T.h, atol=1e-6 * T.h):
            fill = False if g.data.dtype == np.bool_ else np.float32(max(float(g.data.max()), g.h))
            out = np.full(T.shape, fill, g.data.dtype)
            src = [slice(max(0, -off[k]), min(g.shape[k], T.shape[k] - off[k])) for k in range(3)]
            dst = [slice(s.start + off[k], s.stop + off[k]) for k, s in enumerate(src)]
            out[tuple(dst)] = g.data[tuple(src)]
            return out
    fill = 0.0 if g.data.dtype == np.bool_ else max(float(g.data.max()), g.h)
    v = g.sample(T.points(), outside=fill).reshape(T.shape)
    return (v > 0.5) if g.data.dtype == np.bool_ else v.astype(np.float32)


def _op(a, b, fs, fo):
    if a.is_sdf != b.is_sdf:
        a, b = as_sdf(a), as_sdf(b)
    A, B, T = common(a, b)
    return T.like(fs(A, B) if a.is_sdf else fo(A, B))


def union(a, b):
    return _op(a, b, np.minimum, np.logical_or)


def intersection(a, b):
    return _op(a, b, np.maximum, np.logical_and)


def difference(a, b):
    """a minus b."""
    return _op(a, b, lambda x, y: np.maximum(x, -y), lambda x, y: x & ~y)


# ---------------------------------------------------------------------------------------------------------- morphology
def dilate(G, r):
    """grow by r (world units): an SDF shifts by r (exact within its band; `redistance` first if r exceeds it); an
    occupancy grid grows by the Euclidean ball of radius r."""
    if G.is_sdf:
        return G.like((G.data - r).astype(np.float32))
    from scipy.ndimage import distance_transform_edt as edt
    return G.like(edt(~G.data) * G.h <= r)


def erode(G, r):
    if G.is_sdf:
        return G.like((G.data + r).astype(np.float32))
    from scipy.ndimage import distance_transform_edt as edt
    return G.like(edt(G.data) * G.h > r)


def opening(G, r):
    """erode then dilate: removes parts thinner than 2r (slivers, thin fins)."""
    if G.is_sdf:
        return G.like(signed_edt(G.data + r < 0, G.h) - r)
    return dilate(erode(G, r), r)


def closing(G, r):
    """dilate then erode: fills gaps and dents narrower than 2r."""
    if G.is_sdf:
        return G.like(signed_edt(G.data - r < 0, G.h) + r)
    return erode(dilate(G, r), r)


def blur(G, sigma):
    """Gaussian blur of an SDF, sigma in world units (as_sdf first for occupancy)."""
    from scipy.ndimage import gaussian_filter
    S = as_sdf(G)
    return S.like(gaussian_filter(S.data, sigma / S.h, mode='nearest').astype(np.float32))


def outside_region(block, connectivity=1):
    """voxels connected to the grid's border without crossing `block` (bool array): the flood-filled outside."""
    from scipy import ndimage as ndi
    lab, n = ndi.label(~block, ndi.generate_binary_structure(3, connectivity))
    border = np.unique(np.concatenate([lab[0].ravel(), lab[-1].ravel(), lab[:, 0].ravel(), lab[:, -1].ravel(),
                                       lab[:, :, 0].ravel(), lab[:, :, -1].ravel()]))
    out = np.zeros(n + 1, bool)
    out[border] = True
    out[0] = False
    return out[lab]


def fill_cavities(G):
    """fill enclosed voids (anything not connected to the grid's border outside): one solid, no inner shells."""
    occ = ~outside_region(G.occupancy())
    if G.is_sdf:
        D = G.data.copy()
        newly = occ & ~(G.data < 0)
        D[newly] = -np.abs(D[newly]) - 0.5 * G.h
        return G.like(D)
    return G.like(occ)


def seal_faces(block):
    """close the block's cross-sections on the grid's six faces (2D hole filling), so a grid that cuts through a body
    doesn't let a flood from its border into the body."""
    from scipy.ndimage import binary_fill_holes
    b = block.copy()
    for ax in range(3):
        for end in (0, -1):
            sl = [slice(None)] * 3
            sl[ax] = end
            b[tuple(sl)] |= binary_fill_holes(b[tuple(sl)])
    return b


def enclosed(block, h=1.0, seal=0.0, faces=True):
    """voxels not reachable from the grid's border without crossing `block`: gaps in the block narrower than 2 x seal
    (world units) are closed against the flood (it runs through the block grown by `seal`, then regrows by as much without
    crossing the block itself), and with faces=True the block's cross-sections on the grid faces are sealed.
    -> bool array (True = enclosed, the block included)."""
    from scipy import ndimage as ndi
    from scipy.ndimage import distance_transform_edt as edt
    blk = seal_faces(block) if faces else block
    k = int(np.ceil(seal / h - 1e-9)) if seal > 0 else 0
    if k == 0:
        return ~outside_region(blk)
    grown = edt(~blk) <= seal / h
    out = outside_region(grown)
    s6 = ndi.generate_binary_structure(3, 1)
    s26 = ndi.generate_binary_structure(3, 3)
    free = ~blk
    for i in range(k):
        out = ndi.binary_dilation(out, s26 if i % 2 else s6, mask=free)
    return ~out


def solid(m, grid=None, h=None, walls=None, seal=0.0, faces=True, whole=False, pad=3, beta=2.0):
    """the solid a surface encloses, robust to thin double-walled ("hollow") shells, open sheets and holes: the surface is
    voxelised, the outside flooded in from the grid border (enclosed(): `walls`, a bool array of extra blocking voxels such
    as our body, gaps up to 2 x seal closed, the grid faces sealed), and everything else is solid; on the outer boundary
    the winding number decides the voxels the surface passes through, so the solid isn't half a voxel fat.
    whole=True floods on the whole mesh's lattice instead of `grid` (for a closed character cut by a small grid; walls and
    faces don't apply then). -> bool Grid on `grid` (or a new one of voxel h)."""
    from scipy import ndimage as ndi
    m = as_mesh(m)
    G = grid if grid is not None else grid_for(m, h, pad)
    if whole:
        Fl = grid_for(m, G.h, pad=2)
        surf_f = _surface_voxels(m, Fl)
        inside_f = enclosed(surf_f, Fl.h, seal, faces=False)
        outside_f = ~inside_f
        S = G.like(_onto(Fl.like(inside_f), G))
        outer = G.like(_onto(Fl.like(surf_f & ndi.binary_dilation(outside_f)), G)).data
    else:
        surf = _surface_voxels(m, G)
        blk = surf if walls is None else (surf | walls)
        inside = enclosed(blk, G.h, seal, faces)
        S = G.like(inside)
        outer = surf & ndi.binary_dilation(~inside)
    cand = np.flatnonzero(outer)
    if len(cand):
        from .bvh import BVH
        w = BVH(m).winding_number(G.points(cand), beta)
        S.data.flat[cand[w <= 0.5]] = False
    return S


def solid_sdf(m, occ, band=2.5, bvh=None):
    """a signed distance grid for a solid made by solid() or any occupancy of the mesh `m`: exact distances to the mesh on
    the outside within `band` voxels (so the zero level sits on the true outer surface), the EDT of the occupancy inside
    and far out."""
    from .bvh import BVH
    G = occ
    D = signed_edt(G.data, G.h)
    near = np.flatnonzero((D > 0) & (D < band * G.h))
    if len(near):
        B = bvh or BVH(m)
        d, _, _ = B.nearest(G.points(near))
        D.flat[near] = np.minimum(d, D.flat[near] + 0.5 * G.h).astype(np.float32)
    return G.like(D)


def keep_components(G, largest=None, min_voxels=None, min_frac=None, connectivity=1, seeds=None):
    """keep connected solid parts (6-connected with connectivity=1, 26 with 3): the `largest` k, those of at least
    min_voxels or min_frac of the solid, or those containing any of `seeds` (world points). -> Grid (same kind)."""
    from scipy import ndimage as ndi
    occ = G.occupancy()
    st = ndi.generate_binary_structure(3, connectivity)
    lab, n = ndi.label(occ, st)
    if n == 0:
        return G
    sizes = np.bincount(lab.ravel(), minlength=n + 1)
    sizes[0] = 0
    keep = np.zeros(n + 1, bool)
    if largest is not None:
        keep[np.argsort(-sizes, kind='stable')[:largest]] = True
    if min_voxels is not None:
        keep |= sizes >= min_voxels
    if min_frac is not None:
        keep |= sizes >= min_frac * sizes.sum()
    if seeds is not None:
        I = np.round(G.index(seeds)).astype(int)
        ok = np.all((I >= 0) & (I < np.array(G.shape)), 1)
        keep[np.unique(lab[I[ok, 0], I[ok, 1], I[ok, 2]])] = True
    if largest is None and min_voxels is None and min_frac is None and seeds is None:
        keep[:] = True
    keep[0] = False
    km = keep[lab]
    if G.is_sdf:
        D = G.data.copy()
        drop = occ & ~km
        D[drop] = np.abs(D[drop]) + G.h
        return G.like(D)
    return G.like(km)


def weld(G, r, min_frac=0.02):
    """bridge a part's separate pieces where they come within 2 r of the main one: the voxels whose distances to the two
    add up to at most 2 r become solid (the lens between them; a local closing between pieces only, the gaps inside a
    piece, like pleats, are left alone). Pieces under min_frac of the biggest are ignored. -> (Grid, pieces still
    apart)."""
    from scipy import ndimage as ndi
    from scipy.ndimage import distance_transform_edt as edt
    occ = G.occupancy()
    lab, n = ndi.label(occ, ndi.generate_binary_structure(3, 1))
    if n < 2:
        return G, 0
    sizes = np.bincount(lab.ravel(), minlength=n + 1); sizes[0] = 0
    order = np.argsort(-sizes)
    main = lab == order[0]
    d_main = edt(~main) * G.h
    add = np.zeros(G.shape, bool)
    apart = 0
    for j in order[1:]:
        if sizes[j] < min_frac * sizes[order[0]]:
            break
        dj = edt(lab != j) * G.h
        bridge = (dj + d_main <= 2 * r) & ~occ
        if bridge.any():
            add |= bridge
        else:
            apart += 1
    if G.is_sdf:
        D = G.data.copy()
        D[add] = np.minimum(D[add], -0.5 * G.h)
        return G.like(D), apart
    return G.like(occ | add), apart


def restrict(G, keep):
    """zero out (make outside) voxels where keep(points (N,3)) -> bool (N,) is False; `keep` may also be a bool array of the
    grid's shape."""
    K = keep if isinstance(keep, np.ndarray) and keep.shape == G.shape else keep(G.points()).reshape(G.shape)
    if G.is_sdf:
        D = G.data.copy()
        D[~K] = np.maximum(np.abs(D[~K]), G.h)
        return G.like(D)
    return G.like(G.data & K)


def component_count(G, connectivity=1):
    from scipy import ndimage as ndi
    return int(ndi.label(G.occupancy(), ndi.generate_binary_structure(3, connectivity))[1])
