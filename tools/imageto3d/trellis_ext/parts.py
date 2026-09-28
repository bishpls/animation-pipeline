"""Part labels for a TRELLIS.2 field (trellis_ext/field.py): hair / skin / garment / other per voxel, as a label volume, and
per-part closed surfaces (marching cubes, scikit-image) as PLY. numpy, scipy and scikit-image only, and independent of the
geometry kernel (tool/geom), which can take over the surfacing from the label volume later.

    python tools/imageto3d/trellis_ext/parts.py FIELD.npz [--out DIR] [--res 256] [--skin '#f6d2bc'] [--hair '#e8825a']
writes <tag>_labels.npz, <tag>_<part>.ply (hair, skin, garment, other), <tag>_parts.json (the labelling's findings and
each surface's health in charkit.trace.health's terms) and <tag>_parts.png (a board) into DIR.

The method, a simple explainable baseline (every threshold is a keyword of label(); defaults tuned on Clawd):
 1. The field's surface on an R^3 working grid (mean base colour per cell); the solid (Field.solid: flood fill from
    outside plus a 26-ray visibility vote, so shells cut open by the image frame or gapped between locks still fill).
 2. Colours clustered: k-means in CIELAB, lightness weighted by `light_w` (0.5 keeps baked shading and highlights in one
    cluster; 1 when the model gave hair and skin nearly one hue, --lightness).
 3. Hair colour: the clusters owning the crown (the top band of the surface), or --hair.
 4. Height bands from the face: seen from the front of each horizontal facing, the topmost sizeable blob of skin-like
    colour (warm, not too dark or saturated, not hair; or near --skin), the facing where it reaches highest. It gives the
    facing, the skin colour, the chin (where the blob narrows to the neck) and the head's size (1.25 face widths).
    Clusters nearer the hair colour than the skin's (within `hair_tol`) are hair-coloured, nearer the skin's (within
    `skin_tol`) skin. Hair-coloured surface is hair only when tied to the crown through hair colour and above
    `hair_below` head heights under the chin; below, or cut off, it is garment (same-coloured sleeves and dress); with
    long_hair, hair colour hanging behind the head's axis within its footprint stays hair.
 5. Painted features: cells of other colours in the face near its skin (eyes, brows, mouth, blush) are skin, and so are
    the model's inner shells inside the head; small pieces elsewhere on the head are hair when dark or hair-coloured and
    lying on the hair (the shading between locks), else 'other' (clips, ribbons); the rest is garment.
 6. Clean-up: islands under `min_cells` take the majority label of their border.
 7. Inside the solid, by distance from a body proxy: under skin is body (skin); under hair a layer `hair_depth` head
    heights deep over the skull (an ellipsoid behind the face), and hair masses off the skull (buns, thick locks) hair
    through (below the chin only 0.3 head heights deep); under garments a layer `cloth_depth` deep, the body below; every layer at least 2 cells.
 8. Per part: voids filled, the mask smoothed, marching cubes at 0.5, specks dropped (closed, manifold, wound outward),
    vertex colours from the nearest field voxel, and a per-vertex 'outer' flag: 1 on the object's outer surface, 0 on an
    interface inside it (hair against the skull).
Frame: the field's (native TRELLIS.2, z up, unit cube, front toward -y; Blender import of the GLB = native).
"""
import json
import os
import numpy as np

try:
    from .field import Field, render_points, sheet
except ImportError:                                            # run as a script
    from field import Field, render_points, sheet

NAMES = ['empty', 'hair', 'skin', 'garment', 'other']
HAIR, SKIN, GARMENT, OTHER = 1, 2, 3, 4
SHOW = np.array([[0.9, 0.9, 0.9], [0.93, 0.45, 0.2], [0.98, 0.82, 0.72], [0.25, 0.45, 0.85], [0.6, 0.85, 0.3]], np.float32)


# --- colour ---------------------------------------------------------------------------------------------------------
def hexrgb(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255


def srgb_to_lab(c):
    c = np.asarray(c, np.float64).reshape(-1, 3)
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ M.T / np.array([0.95047, 1.0, 1.08883])
    e = 6 / 29
    f = np.where(xyz > e ** 3, np.cbrt(xyz), xyz / (3 * e * e) + 4 / 29)
    return np.stack([116 * f[:, 1] - 16, 500 * (f[:, 0] - f[:, 1]), 200 * (f[:, 1] - f[:, 2])], 1)


def kmeans(X, k, iters=30, seed=0, sample=200000):
    """Lloyd's k-means with k-means++ seeding on (a sample of) X. -> (labels for all X, centres)."""
    rng = np.random.default_rng(seed)
    S = X[rng.choice(len(X), min(sample, len(X)), replace=False)]
    C = [S[rng.integers(len(S))]]
    d2 = ((S - C[0]) ** 2).sum(1)
    for _ in range(1, k):
        C.append(S[rng.choice(len(S), p=d2 / d2.sum())])
        d2 = np.minimum(d2, ((S - C[-1]) ** 2).sum(1))
    C = np.array(C)
    for _ in range(iters):
        lab = ((S[:, None] - C[None]) ** 2).sum(2).argmin(1)
        newC = np.array([S[lab == j].mean(0) if (lab == j).any() else C[j] for j in range(k)])
        if np.allclose(newC, C, atol=1e-3):
            break
        C = newC
    out = np.empty(len(X), np.int64)
    for i in range(0, len(X), 500000):
        out[i:i + 500000] = ((X[i:i + 500000, None] - C[None]) ** 2).sum(2).argmin(1)
    return out, C


# --- labelling ------------------------------------------------------------------------------------------------------
W_LAB = np.array([0.5, 1.0, 1.0])            # lightness down-weighted (label()'s light_w overrides it)


def de(A, B, w=W_LAB):
    """weighted CIELAB distance between rows of A (n,3) and B (m,3) -> (n,m)."""
    return np.sqrt((((np.asarray(A)[:, None] - np.asarray(B)[None]) * w) ** 2).sum(2))


# the four horizontal facings the character may have: (facing vector, viewer's-right vector)
FACINGS = [((0.0, -1.0), (1.0, 0.0)), ((0.0, 1.0), (-1.0, 0.0)), ((-1.0, 0.0), (0.0, -1.0)), ((1.0, 0.0), (0.0, 1.0))]


def front_map(P, C, facing, M=512):
    """the object seen from the front of a facing (orthographic, the unit cube framed): per pixel (u right, z up) the
    nearest point's colour and index. -> (mask (M,M), colour (M,M,3), index (M,M) into P, -1 where empty)."""
    f, r = np.asarray(facing[0]), np.asarray(facing[1])
    u = np.clip(((P[:, :2] @ r + 0.5) * M).astype(np.int64), 0, M - 1)
    v = np.clip(((P[:, 2] + 0.5) * M).astype(np.int64), 0, M - 1)
    depth = -(P[:, :2] @ f)                                                  # smaller = nearer the viewer
    lin = u * M + v
    o = np.lexsort((depth, lin))
    first = np.r_[True, lin[o][1:] != lin[o][:-1]]
    sel = o[first]
    idx = np.full(M * M, -1, np.int64)
    idx[lin[sel]] = sel
    idx = idx.reshape(M, M)
    m = idx >= 0
    col = np.zeros((M, M, 3), np.float32)
    col[m] = C[idx[m]]
    return m, col, idx


def find_face(P, C, is_skin_lab, M=512, min_area=0.004, neck=0.65):
    """the face: on the front view of each horizontal facing, the topmost sizeable blob of skin-coloured pixels
    (is_skin_lab: (n,3) Lab -> bool). The facing whose blob reaches highest wins (from behind the topmost skin is an arm
    or the nape, lower down), the larger among near ties (a profile shows less face). The chin: scanning down from the blob's widest row, the first row where its width
    falls under `neck` of that. -> dict(facing, right, width, chin, top (world), centre (world point), face_lab, pix)
    or None."""
    from scipy import ndimage
    found = []
    for fv, rv in FACINGS:
        m, col, idx = front_map(P, C, (fv, rv), M)
        L = srgb_to_lab(col.reshape(-1, 3)).reshape(M, M, 3)
        sk = m & is_skin_lab(L.reshape(-1, 3)).reshape(M, M)
        sk = ndimage.binary_opening(sk)
        lbl, n = ndimage.label(sk)
        if n == 0:
            continue
        area = ndimage.sum(sk, lbl, range(1, n + 1))
        objs = ndimage.find_objects(lbl)
        big = [j for j in range(n) if area[j] >= min_area * m.sum()]
        if not big:
            continue
        j = max(big, key=lambda j: objs[j][1].stop)                        # the topmost (z grows upward)
        found.append((objs[j][1].stop, area[j], fv, rv, lbl == j + 1, L, idx))
    if not found:
        return None
    hi = max(f[0] for f in found)
    _, _, fv, rv, blob, L, idx = max((f for f in found if f[0] >= hi - 0.03 * M), key=lambda f: f[1])
    rows = np.nonzero(blob.any(0))[0]                                       # z rows, ascending
    width = blob.sum(0).astype(float)
    upper = rows[rows >= rows.min() + 0.3 * (rows.max() - rows.min())]
    zw = upper[np.argmax(width[upper])]                                     # the cheeks
    wmax = width[zw]
    chin = None
    for zz in range(zw, max(rows.min(), int(zw - 1.3 * wmax)) - 1, -1):
        if width[zz] < neck * wmax:
            chin = zz
            break
    if chin is None or chin < rows.max() - 1.6 * wmax:          # no neck in sight (a face blob run into the chest)
        chin = int(rows.max() - 1.1 * wmax)
    face = blob.copy()
    face[:, :chin] = False
    uu, zz = np.nonzero(face)
    pts = P[idx[uu, zz]]
    return dict(facing=np.array(fv), right=np.array(rv), width=wmax / M, chin=chin / M - 0.5, top=rows.max() / M - 0.5,
                centre=pts.mean(0), face_lab=np.median(L[uu, zz], 0), pix=int(face.sum()))


def label(F, R=256, k=14, skin=None, hair=None, crown=0.035, hair_tol=16.0, skin_tol=18.0, hair_below=0.35, light_w=0.5,
          long_hair=False,
          feature_max=0.02, min_cells=40, hair_depth=0.10, cloth_depth=0.035, verbose=True):
    """-> dict(vol (R,R,R) uint8 labels over the solid, surf_cells (n,3), surf_label (n,), voxel_labels (N,) for the
    field's voxels, info). Lengths are in head heights (1.25 face widths, the face found by find_face)."""
    from scipy import ndimage
    if not F.has_color:
        raise ValueError('this field has no colours (run with the texture stage)')
    D = F.dense(R)
    S = D['surface']
    solid = F.solid(R, surface=S)
    cells = np.argwhere(S)
    lab = srgb_to_lab(D['color'][S])
    W = np.array([light_w, 1.0, 1.0])
    cl, C = kmeans(lab * W, k)
    Cl = C / W                                                              # centres back in Lab
    z = cells[:, 2]
    zmin, zmax = z.min(), z.max()
    H = zmax - zmin
    st26 = np.ones((3, 3, 3), bool)

    def comps(sel):
        """26-connected components of a subset of surface cells -> component id per cell (-1 outside the subset)."""
        lbl, n = ndimage.label(_mask(S.shape, cells[sel]), st26)
        return lbl[tuple(cells.T)] - 1, n

    # 3. hair colours: the crown's own clusters (or given)
    top = z >= zmax - crown * H
    if hair:
        hair_lab = srgb_to_lab(np.array([hexrgb(h) for h in hair]))
    else:
        cc = np.bincount(cl[top], minlength=k)
        hair_lab = Cl[np.nonzero(cc >= 0.15 * cc.sum())[0]]
    # 4. the face: skin candidates are warm, not too dark, not too saturated and not hair-coloured; the face is the topmost
    # skin blob seen from the front; it gives the skin colour, the chin and the head's size (1.25 face widths)
    dh = de(Cl, hair_lab, W).min(1)
    hue = np.degrees(np.arctan2(Cl[:, 2], Cl[:, 1])) % 360
    chroma = np.hypot(Cl[:, 1], Cl[:, 2])
    if skin:
        cand = de(Cl, srgb_to_lab(hexrgb(skin)), W).min(1) < skin_tol
    else:
        cand = (dh >= 0.5 * hair_tol) & ((hue < 75) | (hue > 340)) & (Cl[:, 0] > 30) & (chroma > 3) & (chroma < 45)
    cs = float(F.aabb[1, 0] - F.aabb[0, 0]) / R
    is_skin_lab = lambda X: cand[((((X[:, None] - Cl[None]) * W) ** 2).sum(2)).argmin(1)]
    Fc = find_face(F.points(), F.colors(), is_skin_lab)
    if Fc is not None:
        face_lab = Fc['face_lab']
        front = Fc['facing']
        chin = (Fc['chin'] - F.aabb[0, 2]) / cs
        head_h = 1.25 * Fc['width'] / cs
        head_c = (Fc['centre'] - F.aabb[0]) / cs
        head_c[:2] -= front * 0.5 * Fc['width'] / cs                       # the head's axis, behind the face
        face_w = Fc['width'] / cs
    else:                                                                   # no face: assume the canonical front
        face_lab = Cl[cand].mean(0) if cand.any() else np.array([80.0, 15, 20])
        front = np.array([0.0, -1.0])
        chin = zmax - 0.3 * H
        head_h = 0.3 * H
        head_c = cells[top].mean(0)
        face_w = 0.8 * head_h
    ds = de(Cl, face_lab[None], W)[:, 0]
    hair_cl = np.nonzero((dh < hair_tol) & (dh < ds))[0]
    skin_cl = np.nonzero((ds < skin_tol) & (ds <= dh))[0]
    is_hc = np.isin(cl, hair_cl)
    is_sk = np.isin(cl, skin_cl)
    if verbose:
        face_s = f"facing {front.tolist()}, width {face_w:.0f}, chin z {chin:.0f}" if Fc else 'not found'
        print(f'R={R} surface cells {len(cells)}; clusters (L,a,b): ' + ', '.join(
            f'{j}:{Cl[j, 0]:.0f},{Cl[j, 1]:.0f},{Cl[j, 2]:.0f}' for j in range(k)))
        print(f'face: {face_s}; face colour {np.round(face_lab, 1).tolist()}; hair clusters {hair_cl.tolist()}, '
              f'skin {skin_cl.tolist()}; head height {head_h:.0f} cells of {H}')

    lab_s = np.full(len(cells), GARMENT, np.uint8)
    lab_s[is_sk] = SKIN
    # hair: hair colour tied to the crown, down to hair_below head heights under the chin
    hc, _ = comps(is_hc)
    ids = np.unique(hc[top & is_hc])
    hair_ok = is_hc & np.isin(hc, ids[ids >= 0]) & (z >= chin - hair_below * head_h)
    hc2, _ = comps(hair_ok)                                                # recut: still tied to the crown above the limit
    ids = np.unique(hc2[top & hair_ok])
    hair_ok &= np.isin(hc2, ids[ids >= 0])
    # long hair (opt-in: a same-coloured garment on the upper back would join it): hair colour below the limit, tied to
    # the hair, behind the head's axis within its footprint
    hp = cells[hair_ok]
    if long_hair and len(hp):
        back = -((cells[:, 0] - head_c[0]) * front[0] + (cells[:, 1] - head_c[1]) * front[1])
        rad = np.percentile(np.hypot(*(hp[:, :2] - head_c[:2]).T), 95)
        foot = np.hypot(cells[:, 0] - head_c[0], cells[:, 1] - head_c[1]) < rad
        hang = is_hc & ~hair_ok & (back > 0.3 * rad) & foot
        hc3, _ = comps(hair_ok | hang)
        ids = np.unique(hc3[hair_ok])
        hair_ok |= hang & np.isin(hc3, ids[ids >= 0])
    lab_s[hair_ok] = HAIR
    # 5. painted features: non-hair, non-skin cells in the face, close to its skin (eyes, brows, mouth, blush), are skin;
    # small pieces elsewhere on the head are hair when dark or hair-coloured and lying on the hair (shading in the
    # crevices between locks), else 'other' (clips, ribbons)
    in_head = z >= chin - 0.05 * head_h
    u_axis = np.array([-front[1], front[0]])                                # the viewer's right
    rel = cells[:, :2] - head_c[:2]
    uu, dd = rel @ u_axis, rel @ front
    in_face = (np.abs(uu) < 0.6 * face_w) & (z > chin - 0.05 * head_h) & (z < chin + 0.8 * head_h) & (dd > 0)
    near_skin = ndimage.binary_dilation(_mask(S.shape, cells[is_sk & in_face]), st26,
                                        iterations=max(2, int(round(0.12 * face_w))))[tuple(cells.T)]
    rest = lab_s == GARMENT
    lab_s[rest & in_face & near_skin] = SKIN
    # surfaces inside the head the outside can't reach (the model's inner eye and mouth shells) are the head's
    outer = ndimage.binary_dilation(~solid, st26)[tuple(cells.T)]
    in_foot = np.hypot(*(cells[:, :2] - head_c[:2]).T) < 0.8 * head_h
    lab_s[(lab_s == GARMENT) & ~outer & (z > chin - 0.1 * head_h) & in_foot] = SKIN
    rest = (lab_s == GARMENT) & in_head & outer
    rc, nr = comps(rest)
    small = feature_max * len(cells)
    hair_m = ndimage.binary_dilation(_mask(S.shape, cells[lab_s == HAIR]), st26, iterations=2)[tuple(cells.T)]
    dark = lab[:, 0] < 30
    for j in range(nr):
        m = rc == j
        if m.sum() > small:
            continue
        if hair_m[m].mean() > 0.5 and (is_hc[m].mean() > 0.5 or dark[m].mean() > 0.5):
            lab_s[m] = HAIR
        else:
            lab_s[m] = OTHER
    # 6. islands
    lab_s = _islands(S.shape, cells, lab_s, min_cells)

    # 7. inside, by distance from the surface and a body proxy: under skin, and deeper than a garment layer, is body
    # (skin); under hair, a hair layer over the skull (an ellipsoid behind the face), and hair masses off the skull
    # (buns, thick locks) hair through; layers at least 2 cells so every part survives the surfacing
    dist, ind = ndimage.distance_transform_edt(~S, return_indices=True)
    vol = np.zeros(S.shape, np.uint8)
    lab_grid = np.zeros(S.shape, np.uint8)
    lab_grid[tuple(cells.T)] = lab_s
    inside = solid & ~S
    ii = np.argwhere(inside)
    near = lab_grid[ind[0][inside], ind[1][inside], ind[2][inside]]
    d = dist[inside]
    del ind, dist
    t_hair, t_cloth = max(2.0, hair_depth * head_h), max(2.0, cloth_depth * head_h)
    skull = _skull(ii, head_c, front, chin, head_h)
    hair_in = (near == HAIR) & ((d <= t_hair) | (~skull & ((ii[:, 2] > chin) | (d <= 0.3 * head_h))))
    cloth_in = ((near == GARMENT) | (near == OTHER)) & (d <= t_cloth)
    vol[S] = lab_grid[S]
    vol[tuple(ii.T)] = np.where(hair_in | cloth_in, near, SKIN)
    vl = lab_grid[tuple(F.cell_index(R).T)]
    w = lambda zz: float(F.cell_to_world(R, [0, 0, zz])[2])
    info = dict(R=R, k=k, clusters_lab=np.round(Cl, 1).tolist(), cluster_cells=np.bincount(cl, minlength=k).tolist(),
                hair_lab=np.round(hair_lab, 1).tolist(), face_lab=np.round(face_lab, 1).tolist(),
                hair_clusters=hair_cl.tolist(), skin_clusters=skin_cl.tolist(),
                face_found=Fc is not None, front=[float(front[0]), float(front[1]), 0.0], chin_z=w(chin),
                head_height=float(head_h * cs), face_width=float(face_w * cs),
                params=dict(skin=skin, hair=hair, crown=crown, hair_tol=hair_tol, skin_tol=skin_tol, light_w=light_w,
                            long_hair=long_hair,
                            hair_below=hair_below, feature_max=feature_max, min_cells=min_cells, hair_depth=hair_depth,
                            cloth_depth=cloth_depth),
                surface_counts={NAMES[i]: int((lab_s == i).sum()) for i in range(1, 5)},
                volume_counts={NAMES[i]: int((vol == i).sum()) for i in range(1, 5)})
    return dict(vol=vol, surf_cells=cells, surf_label=lab_s, voxel_labels=vl, info=info, solid=solid)


def _skull(P, head_c, front, chin, head_h):
    """inside the skull proxy: an ellipsoid over the chin, behind the face (grid units)."""
    q = P[:, :2] - head_c[:2]
    lat, dep = q @ np.array([-front[1], front[0]]), q @ front
    ez = (P[:, 2] - (chin + 0.5 * head_h)) / (0.5 * head_h)
    return (lat / (0.46 * head_h)) ** 2 + (dep / (0.45 * head_h)) ** 2 + ez ** 2 < 1


def _mask(shape, cells):
    m = np.zeros(shape, bool)
    if len(cells):
        m[tuple(np.asarray(cells).T)] = True
    return m


def _islands(shape, cells, lab_s, min_cells):
    """per label, 26-connected surface islands smaller than min_cells take the most common label bordering them."""
    from scipy import ndimage
    grid = np.zeros(shape, np.uint8)
    grid[tuple(cells.T)] = lab_s
    st = np.ones((3, 3, 3), bool)
    for L in (HAIR, SKIN, GARMENT, OTHER):
        lbl, n = ndimage.label(grid == L, st)
        if n == 0:
            continue
        sizes = np.bincount(lbl.ravel())
        objs = ndimage.find_objects(lbl)
        for j in np.nonzero((sizes < min_cells) & (np.arange(len(sizes)) > 0))[0]:
            sl = tuple(slice(max(s.start - 2, 0), s.stop + 2) for s in objs[j - 1])
            m = lbl[sl] == j
            ring = ndimage.binary_dilation(m, st) & ~m
            around = grid[sl][ring]
            around = around[(around > 0) & (around != L)]
            if len(around):
                grid[sl][m] = np.bincount(around).argmax()
    return grid[tuple(cells.T)]


# --- surfaces -------------------------------------------------------------------------------------------------------
def _drop_debris(v, f, nrm, min_faces):
    """drop mesh shells (edge-connected) with fewer than min_faces faces: marching cubes leaves 8-face specks where the
    smoothed mask barely peaks over the level."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    n = len(v)
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]]])
    _, lab = connected_components(coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n)), directed=False)
    sh = lab[f[:, 0]]
    keep_f = np.bincount(sh, minlength=lab.max() + 1)[sh] >= min_faces
    f = f[keep_f]
    used = np.zeros(n, bool)
    used[f.ravel()] = True
    remap = np.cumsum(used) - 1
    return v[used], remap[f], nrm[used]


def surfaces(F, L, sigma=0.8, min_voxels=30, min_shell=64):
    """closed surfaces per label from the label volume. -> {name: (V (n,3) world, F (m,3), normals, colours uint8, outer)}"""
    from scipy import ndimage
    from scipy.spatial import cKDTree
    from skimage import measure
    vol = L['vol']
    R = vol.shape[0]
    cs = float(F.aabb[1, 0] - F.aabb[0, 0]) / R
    P = F.points()
    tree = cKDTree(P)
    Cf = (F.colors() * 255).round().astype(np.uint8)
    out = {}
    for i in (HAIR, SKIN, GARMENT, OTHER):
        m = vol == i
        if m.sum() < min_voxels:
            continue
        lbl, n = ndimage.label(m, np.ones((3, 3, 3), bool))
        sizes = np.bincount(lbl.ravel())
        keep = np.nonzero(sizes >= min_voxels)[0]
        keep = keep[keep > 0]
        m = ndimage.binary_fill_holes(np.isin(lbl, keep))                  # no voids inside a part: one closed skin each
        if not m.any():
            continue
        lo = np.maximum(np.argwhere(m).min(0) - 3, 0)
        hi = np.minimum(np.argwhere(m).max(0) + 4, R)
        sub = ndimage.gaussian_filter(m[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]].astype(np.float32), sigma)
        sub = np.pad(sub, 1)
        pocket = ndimage.binary_fill_holes(sub > 0.5) & (sub <= 0.5)        # smoothing can seal a thin air channel
        sub[pocket] = 0.51
        v, f, nrm, _ = measure.marching_cubes(sub, 0.5)
        v, f, nrm = _drop_debris(v, f, nrm, min_shell)
        V = F.aabb[0] + (v - 1 + lo + 0.5) * cs
        d, j = tree.query(V, k=1, workers=-1)
        outer = (d < 1.5 * cs).astype(np.uint8)
        col = Cf[j].copy()
        if (~outer.astype(bool)).any() and outer.any():
            col[outer == 0] = Cf[j[outer == 1]].mean(0).round().astype(np.uint8)
        # skimage's normals point outward here but its winding is clockwise seen from outside: flip it (charkit.trace
        # .health counts shells with negative signed volume as inside-out)
        out[NAMES[i]] = (V.astype(np.float32), f[:, ::-1].astype(np.int32), nrm.astype(np.float32), col, outer)
    return out


def write_ply(path, V, Fc, N=None, C=None, outer=None):
    """binary little-endian PLY: x y z [nx ny nz] [red green blue] [outer], triangles."""
    n = len(V)
    props = [('x', 'f4'), ('y', 'f4'), ('z', 'f4')]
    if N is not None:
        props += [('nx', 'f4'), ('ny', 'f4'), ('nz', 'f4')]
    if C is not None:
        props += [('red', 'u1'), ('green', 'u1'), ('blue', 'u1')]
    if outer is not None:
        props += [('outer', 'u1')]
    a = np.empty(n, dtype=[(p, '<' + t) for p, t in props])
    a['x'], a['y'], a['z'] = V.T
    if N is not None:
        a['nx'], a['ny'], a['nz'] = N.T
    if C is not None:
        a['red'], a['green'], a['blue'] = C.T
    if outer is not None:
        a['outer'] = outer
    fa = np.empty(len(Fc), dtype=[('n', 'u1'), ('v', '<i4', (3,))])
    fa['n'] = 3
    fa['v'] = Fc
    tn = {'f4': 'float', 'u1': 'uchar'}
    head = ['ply', 'format binary_little_endian 1.0', 'comment trellis_ext.parts (native TRELLIS.2 frame, z up)',
            f'element vertex {n}'] + [f'property {tn[t]} {p}' for p, t in props] + \
           [f'element face {len(Fc)}', 'property list uchar int vertex_indices', 'end_header']
    with open(path, 'wb') as fh:
        fh.write(('\n'.join(head) + '\n').encode())
        fh.write(a.tobytes())
        fh.write(fa.tobytes())


def save_labels(path, F, L):
    R = L['vol'].shape[0]
    np.savez_compressed(path, labels=L['vol'], voxel_labels=L['voxel_labels'], names=np.array(json.dumps(NAMES)),
                        aabb=F.aabb, res=np.int32(R), cell=np.float32(float(F.aabb[1, 0] - F.aabb[0, 0]) / R),
                        info=np.array(json.dumps(L['info'])), field=np.array(os.path.basename(F.path)))


def load_labels(path):
    """-> dict(labels (R,R,R) uint8, voxel_labels, names, aabb, res, cell, info)."""
    z = np.load(path, allow_pickle=False)
    d = {k: z[k] for k in z.files}
    d['names'] = json.loads(str(d['names']))
    d['info'] = json.loads(str(d['info']))
    d['res'] = int(d['res'])
    return d


def label_points(Lz, P):
    """labels of world points P (n,3) by the cell they fall in (e.g. a GLB's vertices, in the native frame)."""
    R = Lz['res']
    g = np.clip(((np.asarray(P) - Lz['aabb'][0]) / Lz['cell']).astype(np.int64), 0, R - 1)
    return Lz['labels'][g[:, 0], g[:, 1], g[:, 2]]


def sample_surface(V, Fc, C, density, seed=0):
    """points spread over a triangle mesh, area-weighted, `density` per unit area; colours interpolated."""
    rng = np.random.default_rng(seed)
    A = 0.5 * np.linalg.norm(np.cross(V[Fc[:, 1]] - V[Fc[:, 0]], V[Fc[:, 2]] - V[Fc[:, 0]]), axis=1)
    n = int(min(4e6, max(1, A.sum() * density)))
    fi = rng.choice(len(Fc), n, p=A / A.sum())
    r1, r2 = np.sqrt(rng.random(n)), rng.random(n)
    w = np.stack([1 - r1, r1 * (1 - r2), r1 * r2], 1)
    P = (V[Fc[fi]] * w[..., None]).sum(1)
    return P, (C[Fc[fi]] * w[..., None]).sum(1)


def board(F, L, parts, path, size=384):
    """row 1: the surface coloured by label, four views; row 2: the base colour; row 3: each part's surface (three-
    quarter), row 4: the same from the back, each part framed to its own extent."""
    R = L['vol'].shape[0]
    cs = float(F.aabb[1, 0] - F.aabb[0, 0]) / R
    Pc = F.aabb[0] + (L['surf_cells'] + 0.5) * cs
    views = ('front', 'three_quarter', 'right', 'back')
    row1 = [render_points(Pc, SHOW[L['surf_label']], v, size, radius=2) for v in views]
    row2 = [render_points(F.points(), F.colors(), v, size) for v in views]
    row3, row4, lab3 = [], [], []
    for nm in ('hair', 'skin', 'garment', 'other'):
        if nm in parts:
            V, Fc, _, col, _ = parts[nm]
            c, h = (V.min(0) + V.max(0)) / 2, (V.max(0) - V.min(0)).max() / 2 * 1.1
            Vn = (V - c) / (2 * h)                                          # each part framed to itself
            Ps, Cs = sample_surface(Vn, Fc, col / 255.0, 2.5 * size ** 2)
            row3.append(render_points(Ps, Cs, 'three_quarter', size))
            row4.append(render_points(Ps, Cs, 'back', size))
            lab3.append(f'{nm} ({len(V)} verts)')
    sheet([row1, row2, row3, row4], [[f'labels {v}' for v in views], ['base colour'] + [''] * 3, lab3,
                                      [s.split(' ')[0] + ' back' for s in lab3]]).save(path)
    return path


def _health_fn():
    """charkit.trace.health (pure numpy; open, non-manifold, shells, inside-out shells, degenerate faces) when the repo
    is at hand, else None: this module doesn't need charkit."""
    import sys
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root not in sys.path:
        sys.path.append(root)
    try:
        from charkit.trace import health
        return health
    except Exception:
        return None


def main():
    import argparse
    import time
    ap = argparse.ArgumentParser(description='part labels and per-part surfaces for a trellis2 field')
    ap.add_argument('npz')
    ap.add_argument('--out', help='directory (default: next to the npz)')
    ap.add_argument('--res', type=int, default=256, help='working grid resolution')
    ap.add_argument('--k', type=int, default=14, help='colour clusters')
    ap.add_argument('--hair-tol', type=float, default=16.0, help='colour distance from the crown colours still hair')
    ap.add_argument('--lightness', type=float, default=0.5,
                    help='weight of CIELAB lightness in colour distances (0.5 keeps baked shading together; 1 when hair and '
                         'skin differ mostly in lightness)')
    ap.add_argument('--skin', help="skin colour hex as the MODEL coloured it (default: found from the face)")
    ap.add_argument('--hair', help="hair colour hex list, comma-separated (default: the crown's colours)")
    ap.add_argument('--hair-below', type=float, default=0.35, help='hair may reach this many head heights below the chin')
    ap.add_argument('--long-hair', action='store_true', help='hair-coloured surface hanging behind the head below the '
                    'limit is hair too (off: a same-coloured garment on the upper back would join it)')
    ap.add_argument('--hair-depth', type=float, default=0.10, help='hair shell thickness, head heights')
    ap.add_argument('--cloth-depth', type=float, default=0.035, help='garment shell thickness, head heights')
    ap.add_argument('--sigma', type=float, default=0.8, help='mask smoothing before marching cubes, cells')
    a = ap.parse_args()
    t = time.time()
    F = Field(a.npz)
    out = a.out or os.path.dirname(os.path.abspath(a.npz))
    os.makedirs(out, exist_ok=True)
    tag = os.path.basename(a.npz).replace('_field.npz', '')
    L = label(F, a.res, a.k, skin=a.skin, hair_tol=a.hair_tol, light_w=a.lightness, long_hair=a.long_hair,
              hair=a.hair.split(',') if a.hair else None,
              hair_below=a.hair_below, hair_depth=a.hair_depth, cloth_depth=a.cloth_depth)
    parts = surfaces(F, L, a.sigma)
    health = _health_fn()
    L['info']['surfaces'] = {}
    for nm, (V, Fc, N, C, o) in parts.items():
        write_ply(os.path.join(out, f'{tag}_{nm}.ply'), V, Fc, N, C, o)
        h = health(V, Fc) if health else {}
        L['info']['surfaces'][nm] = dict(file=f'{tag}_{nm}.ply', verts=int(len(V)), faces=int(len(Fc)),
                                         outer=round(float(o.mean()), 3), health=h)
        print(f'{nm}: {len(V)} verts {len(Fc)} faces, outer {o.mean():.2f}' + (f', health {h}' if h else ''))
    save_labels(os.path.join(out, tag + '_labels.npz'), F, L)
    json.dump(L['info'], open(os.path.join(out, tag + '_parts.json'), 'w'), indent=1)
    print(board(F, L, parts, os.path.join(out, tag + '_parts.png')))
    print(f'{time.time() - t:.1f} s')


if __name__ == '__main__':
    main()
