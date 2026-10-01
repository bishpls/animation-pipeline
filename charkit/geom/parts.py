"""Part extraction from a generated character (the real case): a generated GLB (TRELLIS.2's when this was written; the 3D
target is the visual hull now) aligned onto our assembled body the way the Blender build aligns it
(charkit.scene.eye_target + charkit.target3d.align_by_eyes), and a part of it (the hair, the skirt) cut out as one clean
closed surface:

    solid(generated)                      the generated surface is a thin double-walled shell: its enclosed solid, flooded
                                          from outside over the whole character (so the hollow head and body fill)
    - (our body grown by `clear`)         the face, neck and the clothes lying on us fall away
    & region                              where the part lives (the head above the chin minus a margin, not the sleeves...)
    & colour                              near the generated surface, only voxels whose nearest surface point is coloured
                                          like the part (skin, collar, clips and eyes out)
    -> cleanup                            thin slivers against the body opened away, small parts dropped, cavities filled
    -> signed distance                    exact to the generated surface where it bounds the part, voxel-smooth elsewhere
    -> marching cubes -> Taubin -> remesh -> envelope normals

    C = Case.load('charkit/spec/clawd.json', glb='/abs/path/clawd_3dstyle_s1.glb')
    R = hair(C)                            # R['mesh'] (Mesh with vn = envelope normals), R['stats'], R['vn_geom']
    save_part(R, 'charkit/out/geom/clawd_hair.npz')
"""
import hashlib
import json
import os
import pickle
import time

import numpy as np

from . import io as gio, repair, smooth, volume
from .mesh import Mesh, as_mesh, vertex_normals

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VERSION = 5                     # bump when an extraction default changes (python -m charkit build re-cuts on a new version)


# ------------------------------------------------------------------------------------------------------------ the case
def load_generated(path, compat=True):
    """(V, F, C) of a generated GLB in Blender's frame, the same numbers charkit.target3d.load_glb gives in Blender
    (compat=True: its colours too). A drop-in `load` for charkit.scene.fit_cranium."""
    m = gio.load(path, blender_compat=compat)
    return m.V, [tuple(f) for f in m.F], m.vc


class Case:
    """a generated character aligned onto our assembled character. gen: Mesh (world, vc = true sRGB base colour),
    gen_compat: target3d.load_glb's colours (what the spec's colour knobs were tuned on), body: our skin (triangulated), A: the
    assembly dict (charkit.character.assemble), spec: the resolved spec."""

    def __init__(self, spec, A, gen, gen_compat, body, align):
        self.spec, self.A, self.gen, self.gen_compat, self.body, self.align = spec, A, gen, gen_compat, body, align
        Hd = A['head']
        self.L = float(Hd['L'])
        self.centre = np.asarray(Hd['centre'], float)
        self.chin_z = float(self.centre[2] - Hd['H'].chin)
        self.eye_z = float(self.centre[2] + Hd['eye_knobs']['z'] * self.L)
        from ..garments import bone_seg
        self.bone = lambda b: bone_seg(A, b)
        self._welded = None

    def gen_welded(self, tol=1e-7):
        """the generated surface with its UV-seam duplicates welded (for connectivity)."""
        if self._welded is None:
            self._welded = repair.merge_close(self.gen, tol)
        return self._welded

    @classmethod
    def load(cls, spec_path, glb=None, cache=True, fit=True, verbose=True):
        """resolve the spec as `python -m charkit build` does (refs fit, then the cranium fitted to the generated hair),
        assemble our character (numpy, charkit.geomstage.assemble's memo, shared with the build's other venv steps) and
        align the generated character by its eyes."""
        from .. import character, cli, target3d, manifest, refs, scene
        spec = manifest.resolve(json.load(open(spec_path)))          # ref.manifest: the rig, the image, "ref:KEY" paths
        shape = (spec.get('hair') or {}).get('shape') or {}
        if glb:
            shape['glb'] = os.path.abspath(glb)
        path = shape.get('glb')
        if not path:
            raise ValueError('no generated shape: pass glb= or set spec.hair.shape.glb')
        path = path if os.path.isabs(path) else os.path.join(ROOT, path)
        ref = spec.get('ref', {})
        if fit and isinstance(ref, dict) and ref.get('rig'):
            R = refs.measure(cli._path(ref['rig']), spec.get('eyes', {}).get('x', 0.168))
            spec = refs.fit(spec, R, ref.get('fit', ('face', 'features', 'hair')))
        spec = scene.fit_cranium(spec, ROOT, load=lambda p: load_generated(p, compat=True))
        t = time.time()
        from .. import geomstage                         # the build's shared assembly memo (the garments step reads it
        A = geomstage.assemble(spec, keep=cache)         # too): keyed on the sections it reads and its code closure
        if verbose:
            print('assembled %s in %.1fs' % (spec.get('name'), time.time() - t))
        gc = gio.load(path, blender_compat=True)
        gt = gio.load(path)
        eyes = target3d.glb_eyes(path, gc.V, gc.vc)
        if eyes is None:
            raise RuntimeError('no eyes found on the generated shape')
        mid, spacing = scene.eye_target(A, shape)
        V = target3d.align_by_eyes(gc.V, eyes, mid, spacing)
        s = spacing / max(1e-9, abs(eyes[0][0] - eyes[1][0]))
        align = dict(eyes=[e.tolist() for e in eyes], eye_mid=mid.tolist(), spacing=float(spacing), scale=float(s),
                     translate=(np.asarray(mid) - (eyes[0] + eyes[1]) / 2 * s).tolist(), glb=path)
        gen = Mesh(V, gt.F, vc=gt.vc)
        gen_c = Mesh(V, gt.F, vc=gc.vc)
        lab = generated_labels(path, len(V))
        if lab is not None:
            # the generated shape carries its classes (a visual hull's, charkit.geom.hull): what the drawings show as
            # clothes is recoloured out of the hair's colour family, so the colour tests keep hair and not the top
            # (the same orange); skin and hair keep their colours
            from ..bodyqa import CLASS
            clothes = ~np.isin(lab, [CLASS['hair'], CLASS['skin'], CLASS['iris'], CLASS['line'], CLASS['none']])
            gen.vc = np.asarray(gen.vc, float).copy(); gen.vc[clothes] = (0.25, 0.35, 0.8)
            gen_c.vc = np.asarray(gen_c.vc, float).copy(); gen_c.vc[clothes] = (0.25, 0.35, 0.8)
        body = Mesh.from_polys(A['verts'], A['faces'])
        return cls(spec, A, gen, gen_c, body, align)


def generated_labels(path, n):
    """per-vertex classes a generated GLB's sidecar names (PATH.json 'labels': an .npy beside it), or None."""
    side = str(path) + '.json'
    if not os.path.exists(side):
        return None
    f = json.load(open(side)).get('labels')
    if not f:
        return None
    lab = np.load(os.path.join(os.path.dirname(str(path)), f))
    return lab if len(lab) == n else None


# ------------------------------------------------------------------------------------------------------------- colour
def hsv(C):
    from ..target3d import hsv as _hsv
    return _hsv(C)


def color_at(m, bvh, P, max_dist=np.inf):
    """the mesh's vertex colour at the closest surface point to each P (barycentric), and the distance."""
    d, f, q = bvh.nearest(P, max_dist)
    ok = f >= 0
    C = np.zeros((len(P), 3))
    if ok.any():
        T = m.V[m.F[f[ok]]]
        w = barycentric(T, q[ok])
        C[ok] = np.einsum('pk,pkd->pd', w, m.vc[m.F[f[ok]]])
    return C, d


def barycentric(T, q):
    """barycentric coordinates of points q (P,3) in triangles T (P,3,3), clipped to the triangle."""
    a, b, c = T[:, 0], T[:, 1], T[:, 2]
    v0, v1, v2 = b - a, c - a, q - a
    d00 = np.einsum('ij,ij->i', v0, v0); d01 = np.einsum('ij,ij->i', v0, v1); d11 = np.einsum('ij,ij->i', v1, v1)
    d20 = np.einsum('ij,ij->i', v2, v0); d21 = np.einsum('ij,ij->i', v2, v1)
    den = np.maximum(d00 * d11 - d01 * d01, 1e-30)
    v = (d11 * d20 - d01 * d21) / den
    w = (d00 * d21 - d01 * d20) / den
    W = np.clip(np.stack([1 - v - w, v, w], 1), 0, 1)
    return W / np.maximum(W.sum(1, keepdims=True), 1e-12)


class ColorClass:
    """a colour family in HSV: hue within hue_tol degrees of hue (when set), saturation and value within their ranges.
    Several families can be combined with `any_of`."""

    def __init__(self, hue=None, hue_tol=20.0, sat=(0.0, 1.0), val=(0.0, 1.0)):
        self.hue, self.hue_tol, self.sat, self.val = hue, hue_tol, tuple(sat), tuple(val)

    def __call__(self, C):
        h, s, v = hsv(C)
        ok = (s >= self.sat[0]) & (s <= self.sat[1]) & (v >= self.val[0]) & (v <= self.val[1])
        if self.hue is not None:
            ok &= np.abs(((h - self.hue) + 180) % 360 - 180) <= self.hue_tol
        return ok

    def to_dict(self):
        return dict(hue=None if self.hue is None else float(self.hue), hue_tol=self.hue_tol, sat=self.sat, val=self.val)

    @staticmethod
    def any_of(*classes):
        return lambda C: np.any([c(C) for c in classes], axis=0)


def dominant_class(C, hue_tol=None, margin=0.12, upper=False):
    """a ColorClass fitted to a sample of colours (e.g. the crown of a generated head, which is all hair): the circular
    median hue (tolerance: twice the 95th percentile deviation, at least 12 degrees), saturation and value from their 2nd
    and 1st percentiles less `margin`, and with upper=True also capped at their 95th percentiles plus `margin` (for a
    family bounded on both sides, like skin between the pale whites and the saturated clothes)."""
    h, s, v = hsv(C)
    good = s > 0.05
    a = np.radians(h[good])
    hue = float(np.degrees(np.arctan2(np.median(np.sin(a)), np.median(np.cos(a)))) % 360)
    dh = np.abs(((h[good] - hue) + 180) % 360 - 180)
    tol = hue_tol if hue_tol is not None else float(max(12.0, 2.0 * np.percentile(dh, 95)))
    s_lo = float(max(0.0, np.percentile(s[good], 2) - margin))
    v_lo = float(max(0.0, np.percentile(v[good], 1) * 0.6))
    s_hi = float(min(1.0, np.percentile(s[good], 95) + margin)) if upper else 1.0
    v_hi = 1.0
    return ColorClass(hue, tol, (s_lo, s_hi), (v_lo, v_hi))


# ------------------------------------------------------------------------------------------------------------ extraction
def extract(case, region, keep_color, h=None, clear=None, color_depth=None, sliver=None, min_frac=0.02, seeds=None,
            bounds=None, cover=None, seal=None, seal_zone=None, hidden=None, post=None, close_pits=None, verbose=True,
            name='part', debug=None):
    """cut a part out of the generated character as a signed-distance grid (see the module doc).
    region: fn(points (N,3)) -> bool, where the part may be. keep_color: fn(colours (N,3)) -> bool (the part's colours).
    h: voxel size (default 0.006 L). clear: how far our body is grown before it is subtracted (default 0.012 L).
    color_depth: how deep under the generated surface its colour decides (default 0.03 L; np.inf: every voxel takes the
    colour of the generated surface nearest to it). close_pits: dents and pinholes narrower than 2 x this are filled at
    the end (default 1.5 h). seal: gaps in the generated
    surface (with our body as a wall) narrower than 2 x seal are closed when finding its solid (default 0.012 L);
    seal_zone=(seal2, fn(points) -> bool): a bigger seal where fn allows (hair: the cap, so the mass sits on the scalp
    instead of a thin sheet over a gap, while the fringe and the hanging locks keep their shapes). sliver: parts thinner than
    2 x this lying against our body are opened away (default 1.5 h). min_frac: parts smaller than this share of the
    biggest are dropped (seeds: world points whose parts are always kept). bounds: (lo, hi) of the work box (default: the
    generated character's points in the region). cover: dict(centre, depth, reach, thick, bin): close the holes our body
    makes where it pokes out through the part (see _poke_cover). hidden: dict(color, centre): drop part voxels the
    generated character hides under its own skin (a ray from the voxel straight out from the vertical axis through
    `centre` meets a surface coloured `color` first: hair tucked behind the generated face, which a narrower face of
    ours would show). post: fn(occ, grid) -> occ, a last voxel filter before
    the parts pass (hair: hanging()). -> dict(sdf Grid, occ Grid, stats)."""
    from .bvh import BVH
    from scipy import ndimage as ndi
    L = case.L
    h = h or 0.006 * L
    clear = 0.012 * L if clear is None else clear
    color_depth = 0.03 * L if color_depth is None else color_depth
    sliver = 1.5 * h if sliver is None else sliver
    seal = 0.012 * L if seal is None else seal
    G = case.gen
    T0 = time.time()
    tick = [T0]

    def log(msg):
        if verbose:
            t = time.time()
            print('  [%s] %-38s %6.1fs' % (name, msg, t - tick[0]))
            tick[0] = t
    if bounds is None:
        inr = region(G.V)
        lo, hi = G.V[inr].min(0), G.V[inr].max(0)
    else:
        lo, hi = bounds
    grid = volume.lattice(lo, hi, h, pad=4)
    stats = dict(h=h, grid=list(grid.shape), clear=clear)
    log('grid %s' % (grid.shape,))
    gb = BVH(G)
    S_body = volume.sdf(case.body, grid=grid)
    log('body signed distance')
    body_wall = S_body.data <= clear
    S_gen_occ = volume.solid(G, grid, walls=body_wall, seal=seal)
    if seal_zone is not None:
        big = volume.solid(G, grid, walls=body_wall, seal=seal_zone[0])
        zone = seal_zone[1](grid.points()).reshape(grid.shape)
        extra = big.data & ~S_gen_occ.data & zone
        S_gen_occ.data |= extra
        stats['seal_zone_vox'] = int(extra.sum())
    log('solid of the generated shell')
    S_gen = volume.solid_sdf(G, S_gen_occ, bvh=gb)
    log('its signed distance')
    occ = S_gen_occ.data & ~body_wall
    # region
    P_all = grid.points()
    reg = region(P_all).reshape(grid.shape)
    occ &= reg
    log('minus body, in region')
    # colour: voxels within color_depth of the generated surface take its colour there
    depth_in = cover.get('depth', 0.08 * L) if cover else 0.0
    cand = S_gen_occ.data & reg & (np.abs(S_gen.data) < color_depth + h) & (S_body.data > min(clear, -depth_in))
    near = np.flatnonzero(cand)
    C, dist = color_at(G, gb, grid.points(near))
    bad = ~keep_color(C) & (dist < color_depth)
    occ.flat[near[bad]] = False
    stats['color_removed_vox'] = int(bad.sum())
    log('colour mask (%d voxels out)' % bad.sum())
    if hidden:
        idx = np.flatnonzero(occ)
        P = grid.points(idx)
        c0 = np.asarray(hidden['centre'], float)
        D = P - c0
        D[:, 2] = 0.0
        ln = np.linalg.norm(D, axis=1)
        ok = ln > 1e-6
        D[ok] /= ln[ok, None]
        t, f, uv = gb.ray_cast(P[ok], D[ok], tmax=hidden.get('reach', 0.3 * L), tmin=0.5 * h, return_uv=True)
        hit = f >= 0
        col = np.zeros((len(f), 3))
        if hit.any():
            w = np.stack([1 - uv[hit].sum(1), uv[hit, 0], uv[hit, 1]], 1)
            col[hit] = np.einsum('pk,pkd->pd', w, G.vc[G.F[f[hit]]])
        under = np.zeros(len(idx), bool)
        under[np.nonzero(ok)[0]] = hit & hidden['color'](col)
        occ.flat[idx[under]] = False
        stats['hidden_removed_vox'] = int(under.sum())
        log('hidden under the skin (%d voxels out)' % under.sum())
    # slivers against the body: thin remnants within reach of our (grown) skin
    near_body = S_body.data < clear + 2 * sliver + h
    thin = np.zeros(grid.shape, bool)
    if sliver > 0:
        thin = occ & ~volume.opening(grid.like(occ), sliver).data & near_body
    cov = None
    if cover:
        # where our body pokes out through the generated part (the part's coloured surface lies inside our body, and
        # nothing of it but slivers is left outside along that direction), a layer of `thick` over our grown body closes
        # the hole; it joins the part before the sliver pass (so the hole's thin rim bonds to it) and is never removed
        good = np.zeros(grid.shape, bool)
        good.flat[near[~bad & (dist < color_depth)]] = True
        good &= S_gen_occ.data & reg
        inside = good & (S_body.data <= clear) & (S_body.data > -cover.get('depth', 0.08 * L))
        outside = occ & ~thin & (S_body.data < clear + cover.get('reach', 0.10 * L))
        layer = (S_body.data > clear - h) & (S_body.data <= clear + cover.get('thick', 0.012 * L)) & reg
        if 'zmin' in cover:
            zs = grid.axes()[2]
            above = (zs > cover['zmin'])[None, None, :]
            inside &= above; layer &= above
        cov = _poke_cover(grid, inside, outside, layer, np.asarray(cover['centre'], float), cover.get('bin', 2.5),
                          grow=cover.get('grow', 2), exclude=cover.get('exclude'), debug=debug)
        stats['cover_vox'] = int(cov.sum())
        occ |= cov
        log('cover poke-through (%d voxels)' % cov.sum())
    if sliver > 0:
        if cov is not None:
            thin = occ & ~volume.opening(grid.like(occ), sliver).data & near_body & ~cov
        occ &= ~thin
        stats['sliver_removed_vox'] = int(thin.sum())
    if post is not None:
        occ = post(occ, grid)
        log('post filter')
    if debug is not None:
        debug.update(cov=cov, occ_pre=occ.copy(), S_body=S_body, S_gen=S_gen, grid=grid, inside=inside if cover else None)
    # parts: the biggest, those above min_frac of it, those holding seeds
    st = ndi.generate_binary_structure(3, 1)
    lab, n = ndi.label(occ, st)
    sizes = np.bincount(lab.ravel(), minlength=n + 1); sizes[0] = 0
    keep = sizes >= min_frac * sizes.max() if n else np.zeros(1, bool)
    if seeds is not None and n:
        I = np.round(grid.index(seeds)).astype(int)
        ok = np.all((I >= 0) & (I < np.array(grid.shape)), 1)
        keep[np.unique(lab[I[ok, 0], I[ok, 1], I[ok, 2]])] = True
    keep[0] = False
    stats['parts_found'] = int(n); stats['parts_kept'] = int(keep.sum())
    occ = keep[lab]
    occ = ~volume.outside_region(occ)                       # no inner cavities
    log('cleanup: %d parts, kept %d' % (n, keep.sum()))
    # the signed distance: exact against the generated surface and our grown body where they bound the part; where the
    # voxel masks (region, colour, slivers, parts) cut, the mask's own distance
    phi = np.maximum(S_gen.data, clear - S_body.data)
    if cov is not None:
        # the cover layer's own exact shell: from our grown body out by `thick`
        th = cover.get('thick', 0.012 * L)
        cl = ndi.binary_dilation(cov, st) & ndi.binary_dilation(occ, st)
        lay = np.maximum(clear - S_body.data, S_body.data - clear - th)
        phi[cl] = np.minimum(phi[cl], lay[cl])
    M = ndi.binary_dilation(occ, st, iterations=1)
    phi_m = volume.signed_edt(M, h)
    phi = np.maximum(phi, phi_m)
    # outside the kept solid grown by 2 voxels nothing may survive
    far = ~ndi.binary_dilation(occ, st, iterations=2)
    phi[far] = np.maximum(phi[far], h)
    close_pits = 1.5 * h if close_pits is None else close_pits
    if close_pits > 0:
        inside = phi < 0
        filled = volume.closing(grid.like(inside), close_pits).data & ~inside
        phi[filled] = -0.5 * h
        stats['pits_filled_vox'] = int(filled.sum())
    S = grid.like(phi.astype(np.float32))
    stats['time_s'] = round(time.time() - T0, 1)
    return dict(sdf=S, occ=grid.like(occ), stats=stats, grid=grid)


FINISH_KW = ('target_edge', 'taubin_iters', 'remesh', 'decimate_to', 'envelope', 'close', 'blur', 'smooth_after', 'env_mix',
             'min_part')


def _poke_cover(grid, inside, outside, layer, centre, bin_deg=2.5, grow=2, exclude=None, debug=None):
    """the layer voxels in the directions (from `centre`, bins of bin_deg degrees) where the part is found `inside` our
    body but none of it `outside`: our body pokes through the part there. exclude: fn(az, el) (degrees; az 0 = the front,
    + = her left; el up) -> bool, directions never covered (the face, for hair)."""
    from scipy import ndimage as ndi

    def bins(mask):
        idx = np.flatnonzero(mask)
        P = grid.points(idx) - centre
        az = np.degrees(np.arctan2(P[:, 0], -P[:, 1]))
        el = np.degrees(np.arctan2(P[:, 2], np.hypot(P[:, 0], P[:, 1])))
        return idx, np.clip(((az + 180) / bin_deg).astype(int), 0, nA - 1), np.clip(((el + 90) / bin_deg).astype(int), 0, nE - 1)
    nA, nE = int(np.ceil(360 / bin_deg)), int(np.ceil(180 / bin_deg))
    I = np.zeros((nA, nE), bool); O = np.zeros((nA, nE), bool)
    _, a, e = bins(inside); I[a, e] = True
    _, a, e = bins(outside); O[a, e] = True
    poke = I & ~O
    if exclude is not None:
        A_, E_ = np.meshgrid(-180 + (np.arange(nA) + 0.5) * bin_deg, -90 + (np.arange(nE) + 0.5) * bin_deg, indexing='ij')
        poke &= ~exclude(A_, E_)
    # a bin's worth of slack round each hole (the rim meets the part), wrapping in azimuth
    if grow:
        poke = ndi.binary_dilation(np.concatenate([poke[-grow:], poke, poke[:grow]]), iterations=grow)[grow:-grow]
    if debug is not None:
        debug.update(poke_in=I, poke_out=O, poke=poke)
    idx, a, e = bins(layer)
    out = np.zeros(grid.shape, bool)
    out.flat[idx[poke[a, e]]] = True
    return out


def finish(S, target_edge=None, taubin_iters=10, remesh=True, decimate_to=None, smooth_after=10, envelope=True,
           close=None, blur=None, env_mix=0.0, min_part=0.01, verbose=True, name='part'):
    """a part's SDF grid to the final surface: marching cubes (closed, manifold), Taubin smoothing, an isotropic remesh to
    target_edge (default 2.5 h; or with remesh=False a quadric decimation to `decimate_to` faces), a last Taubin pass, any
    self-crossings (folds in features thinner than an edge) relaxed or cut out and refilled, and envelope normals (the part's solid closed by `close` and blurred by `blur`,
    defaults 20 h and 16 h; env_mix blends in the geometric normal). -> dict(mesh (vn = the envelope normals), vn_geom,
    report)."""
    from . import remesh as rm
    t0 = time.time()
    h = S.h
    m = volume.to_mesh(S)
    m = repair.remove_small_parts(m, min_area_frac=min_part)       # specks go; real separate pieces stay (and count)
    if verbose:
        print('  [%s] marching cubes: %d tris  %.1fs' % (name, m.nf, time.time() - t0))
    m = smooth.taubin(m, iters=taubin_iters)
    if remesh:
        m = rm.isotropic(m, target_edge or 2.5 * h, iters=4)
    if decimate_to:
        m = rm.decimate(m, decimate_to)
    if smooth_after:
        m = smooth.taubin(m, iters=smooth_after)
    m, left = repair.fix_self_intersections(m, iters=4)
    if left:
        m, left = repair.cut_intersections(m)
    geo = vertex_normals(m.V, m.F)
    out = dict(vn_geom=geo)
    if envelope:
        close = 20 * h if close is None else close
        blur = 16 * h if blur is None else blur
        env = smooth.envelope_normals(m, h=max(h, blur / 6.0), close=close, blur=blur, fallback_mix=env_mix)
        m = m.with_(vn=env)
        out['envelope'] = dict(close=close, blur=blur, mix=env_mix)
    else:
        m = m.with_(vn=geo)
    out['mesh'] = m
    out['report'] = repair.report(m, sample=m.nf)
    if verbose:
        r = out['report']
        print('  [%s] final: %d tris, parts %d, open %d, non-manifold %d, self-x %d  (%.1fs)' % (
            name, m.nf, r['parts'], r['open_edges'], r['nonmanifold_edges'], r.get('self_intersecting_faces_est', -1),
            time.time() - t0))
    return out


# ----------------------------------------------------------------------------------------------------------------- parts
def hair_region(case, below=None, shoulder_x=None, face=False):
    """the head: above the chin minus `below` (head lengths; the spec's hair.shape.below, default 0.33), below the chin
    (+2 cm) nothing further out than shoulder_x (the spec's, default 0.19 m: the same-coloured sleeves), and with face=True
    also charkit.scene.cull_face's rule (face_cull; off by default: the colour test keeps the face clear and the side
    locks that hang in front of the cheeks, which that rule cuts flat)."""
    shape = (case.spec.get('hair') or {}).get('shape') or {}
    below = shape.get('below', 0.33) if below is None else below
    sx = shape.get('shoulder_x', 0.19) if shoulder_x is None else shoulder_x
    zc = case.chin_z - below * case.L
    chin = case.chin_z
    cull = face_cull(case) if face else None

    def region(P):
        ok = P[:, 2] > zc
        low = P[:, 2] < chin + 0.02
        ok &= ~(low & (np.abs(P[:, 0]) > sx))
        if cull is not None:
            ok &= ~cull(P)
        return ok
    return region


def face_cull(case, margin=0.04, clear=None, depth=0.15):
    """fn(P) -> bool: points over our face, charkit.scene.cull_face's rule: below the eyes (by 0.06 L, down to the chin)
    within 0.92 of the face's half-width, in front of its surface or less than `margin` L behind it (only side locks lie
    there); from there up to 0.22 L above the eyes and within the face's width, from `clear` L (the spec's
    hair.shape.clear, default 0.02) in front of the face to `depth` L behind it (the fringe hangs clear of the forehead;
    scene.cull_face has no depth limit there, so it also drops back hair in that band). Tabulated from charkit's anime
    face."""
    from scipy.interpolate import RegularGridInterpolator
    from ..eyes import Face
    Hd = case.A['head']; L = case.L; H = Hd['H']
    shape = (case.spec.get('hair') or {}).get('shape') or {}
    clear = shape.get('clear', 0.02) if clear is None else clear
    Fc = Face(H, Hd['centre'])
    cz = float(Hd['centre'][2])
    z0, z1, z2 = -H.chin * 1.05, -0.06 * L, 0.22 * L
    zs = np.linspace(z0, z2, 40)
    half = np.array([H.section(z)[0] * 0.92 for z in zs])
    xs = np.linspace(-0.30 * L, 0.30 * L, 25)
    Y = np.array([[Fc.y(x, cz + z) for z in zs] for x in xs])
    fy = RegularGridInterpolator((xs, zs), Y, bounds_error=False, fill_value=None)

    def cull(P):
        zr = P[:, 2] - cz
        m = (zr > z0) & (zr < z2) & (np.abs(P[:, 0]) < 0.30 * L)
        out = np.zeros(len(P), bool)
        if m.any():
            Q = P[m]; z = zr[m]
            y = fy(np.stack([Q[:, 0], z], 1))
            inw = np.abs(Q[:, 0]) < np.interp(z, zs, half)
            low = (z < z1) & inw & (Q[:, 1] < y + margin * L)
            up = (z >= z1) & inw & (Q[:, 1] > y - clear * L) & (Q[:, 1] < y + depth * L)
            out[m] = low | up
        return out
    return cull


def hanging(occ, grid, z_top):
    """keep, below height z_top, only what hangs from the part above it: slice by slice downward, the 2D-connected pieces
    touching (within a voxel) what was kept in the slice above. Things that only join from below (a sleeve under a lock's
    tip, a garment under the chin) are dropped."""
    from scipy import ndimage as ndi
    zs = grid.axes()[2]
    k0 = int(np.searchsorted(zs, z_top))
    if k0 <= 0 or k0 >= occ.shape[2]:
        return occ
    out = occ.copy()
    st = ndi.generate_binary_structure(2, 2)
    prev = out[:, :, k0]
    for k in range(k0 - 1, -1, -1):
        sl = out[:, :, k]
        if not sl.any():
            continue
        lab, n = ndi.label(sl, st)
        touch = np.unique(lab[ndi.binary_dilation(prev, st) & sl])
        keep = np.zeros(n + 1, bool); keep[touch] = True; keep[0] = False
        out[:, :, k] = keep[lab]
        prev = out[:, :, k]
    return out


def face_cone(az, el):
    """directions (from the hair centre) of the face, the jaw and the throat: never covered with hair."""
    a = np.abs(az)
    return ((a < 60) & (el < 25)) | ((a < 100) & (el < -20))


def hair_color(case, sample=None):
    """the hair's colour family: the character's palette's hair roles where it declares one (charkit.palette: a crown or
    a hat on top would make the sample below the headwear's), else fitted to the generated crown (its top, well above
    the eyes and within the head's width: all hair, as Clawd's is)."""
    from .. import palette
    if palette.active() is not None:
        return palette.RoleClass(palette.active(), ('hair', 'hair_shade'))
    G = case.gen
    c = case.centre; L = case.L
    m = (G.V[:, 2] > c[2] + 0.3 * L) & (np.abs(G.V[:, 0]) < 0.35 * L)
    return dominant_class(G.vc[m])


def hair(case, h=None, verbose=True, **kw):
    """the hair of the case as one closed surface. kw: extract()'s and finish()'s options."""
    reg = hair_region(case, kw.pop('below', None), kw.pop('shoulder_x', None), face=kw.pop('face', False))
    cc = kw.pop('keep_color', None) or hair_color(case)
    kw.setdefault('color_depth', np.inf)                  # every voxel takes its nearest generated surface's colour
    fin = {k: kw.pop(k) for k in list(kw) if k in FINISH_KW}
    fin.setdefault('close', 0.30 * case.L)                  # envelope: the gaps between locks closed, one big soft mass
    fin.setdefault('blur', 0.25 * case.L)
    fin.setdefault('decimate_to', 50000)                    # quadric decimation after the remesh: the shape at half the faces
    seeds = np.array([[0.0, case.centre[1], case.centre[2] + 0.45 * case.L]])
    Hd = case.A['head']
    hc = case.centre + np.array([0.0, (Hd['H'].db - Hd['H'].df) / 2, 0.06 * case.L])     # charkit.hair.Volume's centre
    cover = kw.pop('cover', dict(centre=hc, zmin=case.chin_z, exclude=face_cone))
    if 'seal_zone' not in kw:
        zc = case.eye_z - 0.1 * case.L

        def cap(P):
            # above the ears' middle and outside the face's cone (from the hair centre)
            Q = P - hc
            az = np.degrees(np.arctan2(Q[:, 0], -Q[:, 1]))
            el = np.degrees(np.arctan2(Q[:, 2], np.hypot(Q[:, 0], Q[:, 1])))
            return (P[:, 2] > zc) & ~face_cone(az, el)
        kw['seal_zone'] = (0.04 * case.L, cap)
    post = kw.pop('post', lambda occ, grid: hanging(occ, grid, case.chin_z))
    kw.setdefault('hidden', dict(color=skin_color(case), centre=hc))
    E = extract(case, reg, cc, h=h, seeds=seeds, cover=cover, post=post, verbose=verbose, name='hair', **kw)
    R = finish(E['sdf'], verbose=verbose, name='hair', **fin)
    R.update(E)
    R['stats']['keep_color'] = cc.to_dict() if hasattr(cc, 'to_dict') else None
    return R


def facial_region(case, top=None, length=None, reach=None):
    """where facial hair may be: from `top` L under the eye line (default 0.12: the moustache under the nose, the
    sideburns' lower half) down to `length` L under the chin (default 1.2), in front of the head's vertical axis and
    within `reach` degrees of straight ahead from the hair's centre (default 100: the jaw's sides, not the nape)."""
    top = 0.12 if top is None else top
    length = 1.2 if length is None else length
    reach = 100.0 if reach is None else reach
    Hd = case.A['head']
    hc = case.centre + np.array([0.0, (Hd['H'].db - Hd['H'].df) / 2, 0.06 * case.L])
    z1, z0 = case.eye_z - top * case.L, case.chin_z - length * case.L

    def region(P):
        Q = P - hc
        az = np.degrees(np.arctan2(Q[:, 0], -Q[:, 1]))
        return (P[:, 2] < z1) & (P[:, 2] > z0) & (np.abs(az) < reach)
    return region


def facial_hair(case, h=None, verbose=True, **kw):
    """a design's facial hair (beard and moustache) as one closed surface: the hair-coloured generated character over the
    lower face (facial_region), which hair() leaves out (its cover keeps the face, jaw and throat clear: Clawd has none).
    kw: extract()'s and finish()'s options."""
    reg = facial_region(case, kw.pop('top', None), kw.pop('length', None), kw.pop('reach', None))
    cc = kw.pop('keep_color', None) or hair_color(case)
    fin = {k: kw.pop(k) for k in list(kw) if k in FINISH_KW}
    fin.setdefault('close', 0.12 * case.L)                  # the locks' gaps closed, finer than the hair's envelope
    fin.setdefault('blur', 0.08 * case.L)
    fin.setdefault('decimate_to', 30000)
    Hd = case.A['head']
    front = case.centre[1] - Hd['H'].df                     # the face's front (toward -y)
    seeds = np.array([[0.0, front, case.chin_z]])
    E = extract(case, reg, cc, h=h, seeds=seeds, verbose=verbose, name='facial_hair', **kw)
    R = finish(E['sdf'], verbose=verbose, name='facial_hair', **fin)
    R.update(E)
    R['stats']['keep_color'] = cc.to_dict() if hasattr(cc, 'to_dict') else None
    return R


def skirt_region(case, top=None, bottom=None):
    """between the waist and mid-thigh: top = the skirt spec's waist height (hips..spine joint, `waist` of the way) plus
    `top` head lengths (default 0.08); bottom = halfway from the hip joints to the knees minus `bottom` head lengths
    (default 0)."""
    hj = case.bone('hips')[0]; sj = case.bone('spine')[1]
    sk = next((g for g in case.spec.get('garments', []) if g.get('kind') == 'skirt'), {})
    zw = hj[2] + (sj[2] - hj[2]) * sk.get('waist', 0.55)
    hipL = case.bone('leftUpperLeg')[0]; knee = case.bone('leftLowerLeg')[0]
    zmid = (hipL[2] + knee[2]) / 2
    z1 = zw + (0.08 if top is None else top) * case.L
    z0 = zmid - (0.0 if bottom is None else bottom) * case.L

    def region(P):
        return (P[:, 2] > z0) & (P[:, 2] < z1)
    region.z = (z0, z1)
    return region


def skin_color(case, hue_tol=15.0):
    """the generated character's skin colour family, fitted to its nose and the cheeks right beside it (between the eyes
    and the mouth, within 0.12 L of the midline, at the front: no lips, eyes, brows or locks in the sample)."""
    G = case.gen
    c = case.centre; L = case.L
    m = (np.abs(G.V[:, 0]) < 0.12 * L) & (G.V[:, 2] < case.eye_z - 0.12 * L) & (G.V[:, 2] > case.eye_z - 0.28 * L) & \
        (G.V[:, 1] < c[1] - 0.2 * L)
    return dominant_class(G.vc[m], hue_tol=hue_tol, margin=0.08, upper=True)


def surface_parts(case, region, drop_color, max_drop=0.3, min_frac=0.01, hug=None, weld=1e-7):
    """the generated surface's own pieces in a region: its faces there, split into edge-connected parts (after welding
    the UV seams); the parts with `max_drop` or more of their area coloured like drop_color (skin: the legs, the hands)
    are dropped; with hug (world units), so are the faces of the other parts lying within `hug` of a dropped part (shorts
    and tights hug the legs; a skirt stands off them), and the rest is split again; parts under min_frac of the biggest
    go. -> (Mesh of the kept faces, info per part)."""
    from scipy.spatial import cKDTree
    from .mesh import compact, components, face_areas
    G = case.gen_welded(weld)
    sub, _ = compact(G, region(G.V[G.F].mean(1)))
    lab, k = components(sub.F, by='face')
    ar = face_areas(sub.V, sub.F)
    bad_f = drop_color(sub.vc)[sub.F].mean(1)
    area = np.bincount(lab, weights=ar, minlength=k)
    badf = np.bincount(lab, weights=ar * bad_f, minlength=k) / np.maximum(area, 1e-12)
    dropped = badf >= max_drop
    keep_f = ~dropped[lab]
    hugged = 0
    if hug and dropped.any() and keep_f.any():
        tree = cKDTree(sub.V[np.unique(sub.F[~keep_f])])
        d, _ = tree.query(sub.V[sub.F[keep_f]].mean(1))
        near = np.zeros(len(keep_f), bool)
        near[np.nonzero(keep_f)[0][d < hug]] = True
        hugged = int(near.sum())
        keep_f &= ~near
    kept, _ = compact(sub, keep_f)
    lab2, k2 = components(kept.F, by='face')
    ar2 = face_areas(kept.V, kept.F)
    area2 = np.bincount(lab2, weights=ar2, minlength=k2)
    big = area2 >= min_frac * (area2.max() if k2 else 0)
    info = dict(pieces=[dict(area_m2=round(float(area[i]), 5), drop_share=round(float(badf[i]), 3),
                             dropped=bool(dropped[i])) for i in np.argsort(-area)],
                hugging_faces_dropped=hugged, kept_parts=[round(float(a), 5) for a in sorted(area2[big], reverse=True)])
    out, _ = compact(kept, big[lab2])
    return out, info


def skirt(case, h=None, top=None, bottom=None, thick=None, hug=None, verbose=True, **kw):
    """the skirt of the case as one closed surface: the generated surface between the waist and mid-thigh split into its
    own pieces (the skirt panels come apart from the legs-and-shorts piece and the hands once cut to the band; with
    top=None the band's top is searched, waist +0.10 .. -0.12 L, for the cut that frees the most skirt), the
    pieces that aren't skin and don't hug it (the shorts: median distance from the skin under `hug`, default 0.05 L)
    kept, and that sheet thickened into a solid `thick` across (default 0.016 L: TRELLIS makes
    cloth as a hair-thin double wall) before the same finishing as the hair. kw: finish()'s options."""
    t0 = time.time()
    L = case.L
    h = h or 0.006 * L
    hug = 0.05 * L if hug is None else hug
    skin = skin_color(case)
    if top is None:
        # the highest cut below which the skirt comes apart from the body: the one keeping the most non-skin area
        best = None
        for t in np.arange(0.10, -0.121, -0.02):
            reg_t = skirt_region(case, t, bottom)
            sh, inf = surface_parts(case, reg_t, skin, hug=hug)
            area = sum(inf['kept_parts'])
            if best is None or area > best[0] * 1.02:
                best = (area, t, sh, inf)
        _, top, sheet, info = best
        reg = skirt_region(case, top, bottom)
    else:
        reg = skirt_region(case, top, bottom)
        sheet, info = surface_parts(case, reg, skin, hug=hug)
    r = 0.5 * (0.016 * L if thick is None else thick)
    S = volume.thicken(sheet, r, h=h)
    # panels hanging side by side from the waistband come a few mm apart: bridged where they come close
    S, apart = volume.weld(S, 1.5 * r)
    if verbose:
        print('  [skirt] %d parts kept of %d pieces (%d hugging faces out), sheet %d tris, grid %s  %.1fs' % (
            len(info['kept_parts']), len(info['pieces']), info['hugging_faces_dropped'], sheet.nf, S.shape,
            time.time() - t0))
    fin = {k: kw.pop(k) for k in list(kw) if k in FINISH_KW}
    fin.setdefault('close', 0.10 * L)
    fin.setdefault('blur', 0.08 * L)
    fin.setdefault('target_edge', min(2.5 * h, 1.6 * r))      # edges no longer than the cloth is thick: no folds across it
    fin.setdefault('decimate_to', 60000)                       # then quadric decimation: the pleats are flat
    R = finish(S, verbose=verbose, name='skirt', **fin)
    R.update(sdf=S, sheet=sheet, stats=dict(h=h, grid=list(S.shape), thick=2 * r, z_band=list(reg.z), top=round(float(top), 3),
                                            pieces_not_welded=apart, parts=info,
                                            time_s=round(time.time() - t0, 1)))
    return R


# ----------------------------------------------------------------------------------------------------------- measuring
AZ = (0, 45, 90, 135, 180, 270)


def reference(case, region, keep_color):
    """the generated character's own faces of a part, for comparing against: faces whose three vertices are coloured like
    the part and lie in the region. -> Mesh."""
    from .mesh import compact
    G = case.gen
    ok_v = keep_color(G.vc) & region(G.V)
    keep = ok_v[G.F].all(1)
    return compact(G, keep)[0]


def silhouettes(part, ref, frame, azimuths=AZ, zmin=None):
    """silhouette IoU of a part against a reference per azimuth (orthographic, qa3d's convention), optionally only above
    height zmin. -> (dict az -> iou, dict az -> (part mask, ref mask))."""
    from . import raster
    out, masks = {}, {}
    for az in azimuths:
        a = raster.silhouette(part, az, frame)
        b = raster.silhouette(ref, az, frame)
        if zmin is not None:
            H = frame.res[1]
            row = int(round((0.5 - (zmin - frame.centre[2]) / frame.scale) * H))
            a[max(0, row):] = False; b[max(0, row):] = False
        out[az] = round(raster.iou(a, b), 4)
        masks[az] = (a, b)
    return out, masks


def measure(case, R, region, keep_color, zmin=None, res=480, out_dir=None, name='part', ref=None):
    """a part's numbers: health (parts, open / non-manifold edges, self-crossings, genus, volume) and silhouette IoU
    against the generated part (its faces coloured like the part in the region, or `ref`) from six azimuths (whole
    region, and above zmin when given); with out_dir, the overlays (grey both, red only ours, blue only the generated) as
    PNG. -> dict."""
    from . import raster
    m = R['mesh']
    ref = reference(case, region, keep_color) if ref is None else ref
    fr = raster.Frame.around([m, ref], res=res, aspect=1.0)
    iou, masks = silhouettes(m, ref, fr)
    rep = R['report']
    stats = dict(faces=rep['faces'], verts=rep['verts'], parts=rep['parts'], open_edges=rep['open_edges'],
                 nonmanifold_edges=rep['nonmanifold_edges'], nonmanifold_verts=rep['nonmanifold_verts'],
                 watertight=rep['watertight'], self_intersecting_faces=rep.get('self_intersecting_faces_est'),
                 genus=rep.get('genus'), volume_l=round(rep.get('volume', 0) * 1000, 4),
                 silhouette_iou=iou, silhouette_iou_mean=round(float(np.mean(list(iou.values()))), 4))
    if zmin is not None:
        iz, mz = silhouettes(m, ref, fr, zmin=zmin)
        stats['silhouette_iou_above'] = iz
        stats['silhouette_iou_above_mean'] = round(float(np.mean(list(iz.values()))), 4)
    if out_dir:
        ims = [raster.overlay(*masks[a]) for a in AZ]
        stats['overlay_png'] = raster.save_png(raster.sheet(ims, cols=len(ims)),
                                               os.path.join(out_dir, f'{name}_silhouettes.png'))
    return stats


def render_sheet(case, R, out_path, res=360, with_body=True, azimuths=(0, 45, 90, 135, 180, 270)):
    """the part per azimuth: toon-shaded with its envelope normals (row 1), with its own geometric normals (row 2), then on
    our body (row 3) above the generated character from the same view (row 4). -> path."""
    from . import raster
    m = R['mesh']
    lo, hi = m.bounds()
    c = (lo + hi) / 2
    size = float(max(hi[2] - lo[2], np.linalg.norm((hi - lo)[:2]))) * 1.08
    fr = raster.Frame(c, size, (res, res))
    col = np.array([0.93, 0.55, 0.40])
    light = (-0.6, 0.6, 0.5)
    rows = [[], [], [], []]
    for az in azimuths:
        rows[0].append(raster.render([(m, dict(color=col, normals=m.vn, shade='toon'))], az, fr, light=light))
        rows[1].append(raster.render([(m, dict(color=col, normals=R['vn_geom'], shade='toon'))], az, fr, light=light))
        if with_body:
            rows[2].append(raster.render([(m, dict(color=col, normals=m.vn, shade='toon')),
                                          (case.body, dict(color=(0.98, 0.86, 0.80), shade='lambert'))], az, fr,
                                         light=light))
            rows[3].append(raster.render([(case.gen, dict(color=case.gen.vc, shade='lambert'))], az, fr, light=light))
    ims = rows[0] + rows[1] + (rows[2] + rows[3] if with_body else [])
    return raster.save_png(raster.sheet(ims, cols=len(azimuths)), out_path)


def save_part(R, path, meta=None):
    """write a part for the Blender stage: .npz (V, F, vn = envelope normals, vn_geom, meta json) and a .ply next to it
    (V, F, vn = envelope normals). -> (npz path, ply path)."""
    base = os.path.splitext(path)[0]
    m = R['mesh']
    info = dict(meta or {})
    info.setdefault('stats', R.get('stats'))
    info.setdefault('report', R.get('report'))
    if 'envelope' in R:
        info['envelope'] = R['envelope']
    info['frame'] = 'blender world (z up, metres), the assembled character\'s rest pose'
    info['normals'] = 'vn: envelope normals (custom split normals); vn_geom: the geometric vertex normals'
    npz = gio.save_npz(m, base + '.npz', meta=json.loads(json.dumps(info, default=_jsonable)), vn_geom=R['vn_geom'])
    ply = gio.save_ply(m, base + '.ply')
    return npz, ply


def _jsonable(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    return str(o)
