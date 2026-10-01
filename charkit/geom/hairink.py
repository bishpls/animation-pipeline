"""The hair's ink strokes (tool/hairstrokes; Michael, 2026-10-01: the hair lacks "detail in the bulk of the mass", which in
anime hair is mostly ink strokes inside the locks: strand lines and partial separations, not relief). The skirt's
creases were drawn as a line layer traced from the design (charkit.garments.ink_strokes, tool/garments4); this is the
same for the hair, on whichever pieces build it (the hull shell's locks or the lock shells: the strokes ride on the
surface they land on, so the geometry track's shells and this layer stay independent).

  trace    per view of the body turnaround, the lines drawn inside the hair's mass (hairflagqa's design side: the line
           class and the fainter strokes, off the hair's outline, clear of the buns, the ahoge and the clips), with
           `set` 'strand' those within `wall` L of a boundary between two of the splitter's locks left out (the lock
           lines: the shells' outlines draw them), skeletonized and traced into polylines (charkit.inkfit), each point
           (u, z) in L round the view's origin on its design grid
  project  each stroke cast along its own view onto the nearest hair piece (the pieces z-buffered with the skin as an
           occluder; the hit point exact on its triangle), with the piece's shading normal, lock and strand direction
           there. The cameras are the QA's (frames(): the azimuths from the sheet's three-quarter eyes, each window
           centred on our eyes, bodyqa.origin), so a stroke lands where the QA compares it with the drawing (the hull
           views' frame sat 1-6 px off it in profile and three-quarter)
  keep     a drawn stroke stays where its own view faces the surface (by `min_face`, within `margin` of the best view's
           facing) and where every other view that sees it squarely draws a line near where it lands there (the veto:
           the turnaround's views draw their strand texture independently, so a stroke from one view is kept where no
           other view's drawing contradicts it; the back draws its mass plain, so nothing lands on what the back
           sees squarely unless the back draws a line there)
  ribbon   each kept run a ribbon lying on its piece (`lift` L off the piece's surface; the render's surface is the
           outline's pull-in, 0.0056 L, under it), `width` L across, narrowing to `tip` of that over `taper` of its
           length at each end (the drawn strokes taper), appended to the piece's mesh on an ink slot (per-face `ink`):
           it moves with the piece; its vertices carry the piece's lock under them (per-lock rigging to come), no
           outline (outline_w 0) and the surface's shading normal

Templates first: the strokes are the design's; what the spec holds is how they are drawn (hair.shape.strokes: set,
width, taper, tip, lift, margin, views). Measured per view by the declared checks charkit.hairstrokeqa (presence and
place, direction, extra strokes).

    S, near = trace(spec, opts)                      # {view: [(n, 2) (u, z) L round the view's origin]}, the veto's
    F = frames(spec, iris, centre, L)                # the QA's cameras
    K, rep = place(pieces, S, F, L, opts, skin=(V, T), near=near)   # {piece: ribbons}
    apply(R, K)                                      # R: charkit.geom.hairpieces.build's, in place
"""
import os

import numpy as np

VIEWS = ('front', 'three_quarter', 'profile', 'back')
MASS = ('bangs', 'side_locks', 'upper_back', 'lower_back')      # the families strokes land on (hairpieces' MASS)
OPTS = dict(
    set='strand',       # 'strand': the lock lines left out (the shells draw them); 'all': every interior line
    wall=0.012,         # L: a drawn line this close to a boundary between two of the splitter's locks is a lock line
    min_len=0.02,       # L: shorter traced strokes are dropped
    tol=0.003,          # L: the traced polylines' simplification (Ramer-Douglas-Peucker)
    width=0.0035,       # L: a ribbon's width (the hair's outline is 0.0056 L: inner lines thinner)
    tip=0.15,           # its width at its ends, a share of `width`
    taper=0.6,          # the share of its length over which it narrows, half at each end
    lift=-0.002,        # L off the piece's surface (negative: inside it, still in front of the render's pulled-in surface)
    step=0.004,         # L: samples along a ribbon
    margin=0.5,         # facing slack: a stroke stays where its view's facing is within this of the best view's (0.5:
                        # each view's strokes kept wherever it faces the surface by min_face; the views draw
                        # their strand texture independently, so owning each part from one view cost the others)
    min_face=0.2,       # ... and where its own view faces the surface at least this much (no grazing projections)
    min_run=0.015,      # L: a kept run shorter than this is dropped
    views=('front', 'three_quarter', 'profile'),   # the views traced (the back's interior ink is the hem flicks'
                        # notch ticks, the flick shells' own: the design's back mass draws no strand texture)
    veto=VIEWS,         # the views that veto: a stroke stays only where each of these that sees it squarely draws a
                        # line within `veto_near` of it (the views draw their strand texture independently)
    veto_face={'front': 0.65, 'three_quarter': 0.65, 'profile': 0.65, 'back': 0.05},   # a view vetoes a point it sees
                        # with at least this facing (a number: every view's): the back vetoes whatever it sees (its mass
                        # is drawn plain; hair_back_lines, Michael's flag 5), the others what they see squarely
    veto_near=0.04,     # L: a drawn line this close to where a stroke lands in a view supports it there
    veto_depth=0.01,    # L: a point this far behind the view's nearest surface is hidden there
    ss=4,               # the projection's z-buffer supersampling over the sheet's px per L
    buns=True,          # the buns' drawn lines (the edge where a bun's front block meets the one behind, its tiers'
                        # steps: inside each drawn bun, off its outline by bun_band) traced and laid on the bun pieces
    bun_band=0.015,     # L: a bun's outline band left out
    bun_views=VIEWS,    # the views the buns' lines are traced from (the back's too: they lie off the back's mass)
    bun_veto=VIEWS,     # the views that veto a bun's line
    bun_veto_face=0.9,  # their facing threshold (a bun line from one view lands off the others: our bun block isn't
                        # the drawn one exactly; only a view facing the bun face head-on vetoes it)
)


# ------------------------------------------------------------------------------------------------------------ helpers
def lock_boundaries(lock):
    """where a lock image changes between two locks (both > 0), either side of the step -> bool image."""
    b = np.zeros(lock.shape, bool)
    for a0, a1 in (((slice(None, -1), slice(None)), (slice(1, None), slice(None))),
                   ((slice(None), slice(None, -1)), (slice(None), slice(1, None)))):
        x, y = lock[a0], lock[a1]
        e = (x != y) & (x > 0) & (y > 0)
        b[a0] |= e
        b[a1] |= e
    return b


def view_dir(az):
    """the view direction (into the scene) for a camera at azimuth az (charkit.faceqa.view's convention)."""
    a = np.radians(az)
    return np.array([-np.sin(a), np.cos(a), 0.0])


# ------------------------------------------------------------------------------------------------------------ trace
def drawn_strokes(lines, keep, ppl, lock=None, set_='strand', wall=OPTS['wall'], min_len=OPTS['min_len']):
    """the strokes drawn inside the hair's mass on a design grid: the lines (hairflagqa's drawn lines) skeletonized
    inside keep (the mass's inside); set 'strand': those within `wall` L of a boundary between two locks of `lock` (the
    splitter's lock image) left out; skeleton pieces (8-connected) shorter than `min_len` L dropped (specks: a
    highlight's or a tone's edge read as a faint stroke). The measure (charkit.declared's strokes family) and the tracer
    read the same strokes. -> bool image."""
    from scipy import ndimage
    from skimage.morphology import skeletonize
    sk = skeletonize(lines) & keep
    if set_ == 'strand' and lock is not None:
        b = lock_boundaries(lock)
        if b.shape == sk.shape and b.any():
            sk &= ndimage.distance_transform_edt(~b) > wall * ppl
    if min_len > 0 and sk.any():
        lab, n = ndimage.label(sk, structure=np.ones((3, 3)))
        size = np.bincount(lab.ravel())
        size[0] = 0
        sk = (size >= min_len * ppl)[lab]
    return sk


def split_locks(spec):
    """the produced lock split's lock images (charkit.hairsplit: hairsplit.npz, VIEW the lock image on the design grid)
    -> {view: int image} or {} without one."""
    from charkit import manifest
    p = manifest.produced(spec, 'hair_split', log=lambda *a: None)
    z = os.path.splitext(p)[0] + '.npz' if p else None
    if not z or not os.path.exists(z):
        return {}
    Z = np.load(z)
    return {k: Z[k] for k in Z.files if '__' not in k}


def design_lines(spec, set_='strand', wall=OPTS['wall'], views=VIEWS, min_len=OPTS['min_len']):
    """the design's strokes inside the hair's mass per view (drawn_strokes on hairflagqa's design side: the line class
    and the fainter strokes, the mass's inside) on the body sheet's design grids (bodyqa.design_views), and each view's
    distance (L) to its nearest drawn line (any: the outline, the lock lines) -> ({view: bool image}, ppl,
    {view: distance image})."""
    from scipy import ndimage
    from skimage.morphology import skeletonize
    from charkit import hairflagqa, hairlayers, manifest
    dv, ppl = hairlayers.design(spec)
    R = manifest.load(spec['ref']['manifest'])['references']
    truth = hairlayers.load_truth(hairlayers._p(R['hair_truth']['path']))
    D = hairflagqa.design_side(truth, dv, ppl, views=tuple(v for v in VIEWS if v in dv))
    locks = split_locks(spec) if set_ == 'strand' else {}
    out, near = {}, {}
    for v in VIEWS:
        if v not in D['keep']:
            continue
        near[v] = ndimage.distance_transform_edt(~skeletonize(D['lines'][v])) / ppl
        if v in views:
            out[v] = drawn_strokes(D['lines'][v], D['keep'][v], ppl, locks.get(v), set_, wall, min_len)
    return out, ppl, near


def trace(spec, opts=None):
    """the design's interior strokes per view, traced into polylines on the design grids, each point (u, z) in L round
    the view's origin (the QA's: bodyqa.WIN round the drawn eyes, pixel centres) -> ({view: [(n, 2) array]}, {view:
    distance image (L) to the view's nearest drawn line, on its design grid}: the veto's)."""
    from charkit import inkfit
    from charkit.bodyqa import WIN
    o = dict(OPTS, **(opts or {}))
    S, ppl, near = design_lines(spec, o['set'], o['wall'], tuple(o['views']))
    out = {}
    for v, sk in S.items():
        polys = inkfit.join(inkfit.trace(sk, ppl, o['min_len'], o['tol']))
        out[v] = [np.c_[(P[:, 1] + 0.5) / ppl - WIN['x'], WIN['top'] - (P[:, 0] + 0.5) / ppl] for P in polys]
    return out, near


def bun_lines(spec, views=VIEWS, band=OPTS['bun_band'], min_len=OPTS['min_len']):
    """the lines drawn inside each drawn bun per view (the outfit masks' VIEW__bun_L / bun_R, closed and filled, their
    outline's band `band` L left out; hairflagqa's drawn lines), skeletonized, pieces under min_len dropped -> ({view:
    bool image}, ppl)."""
    from scipy import ndimage
    from skimage.morphology import skeletonize
    from charkit import hairflagqa, hairlayers, manifest
    dv, ppl = hairlayers.design(spec)
    Z = np.load(manifest.produced(spec, 'outfit_masks', log=lambda *a: None))
    out = {}
    for v in views:
        if v not in dv:
            continue
        lines = hairflagqa.drawn_lines(dv[v])
        R = np.zeros(lines.shape, bool)
        for b in ('bun_L', 'bun_R'):
            k = '%s__%s' % (v, b)
            if k in Z.files and Z[k].shape == R.shape:
                R |= ndimage.binary_fill_holes(ndimage.binary_closing(Z[k], iterations=3))
        if not R.any():
            continue
        sk = skeletonize(lines & ndimage.binary_erosion(R, iterations=max(1, int(round(band * ppl)))))
        lab, n = ndimage.label(sk, structure=np.ones((3, 3)))
        size = np.bincount(lab.ravel())
        size[0] = 0
        out[v] = (size >= min_len * ppl)[lab]
    return out, ppl


def trace_buns(spec, opts=None):
    """the buns' drawn lines (bun_lines) traced as trace() traces the strands -> {view: [(n, 2) array]}."""
    from charkit import inkfit
    from charkit.bodyqa import WIN
    o = dict(OPTS, **(opts or {}))
    S, ppl = bun_lines(spec, tuple(o['bun_views']), o['bun_band'], o['min_len'])
    return {v: [np.c_[(P[:, 1] + 0.5) / ppl - WIN['x'], WIN['top'] - (P[:, 0] + 0.5) / ppl]
                for P in inkfit.join(inkfit.trace(sk, ppl, o['min_len'], o['tol']))] for v, sk in S.items()}


def frames(spec, iris, centre, L):
    """each view's camera as the QA draws ours on the design grids (charkit.bodyqa: its azimuth from the sheet's
    three-quarter eyes, as qa3d.Design.sheet_context measures it; the window's origin our eyes there, bodyqa.origin)
    -> {view: dict(az, origin (u, z world), L (m per L), ppl)}. iris: our iris centres (world, (2, 3)); centre: the
    head's centre."""
    from charkit import bodyqa, hairlayers, manifest, sheetqa
    R = manifest.load(spec['ref']['manifest'])['references']
    rgb = hairlayers.load_rgb(R['body_turnaround']['path'])
    ex = (spec.get('eyes') or {}).get('x', 0.168)
    D = sheetqa.detect_figures(rgb, None, ex, -1)
    ppl = float(D['ppl'])
    te = D['figures'].get('three_quarter', {}).get('eyes') or []
    az3 = float(np.degrees(np.arccos(np.clip(abs(te[1][0] - te[0][0]) / (2 * ex * ppl), 0, 1)))) if len(te) == 2 else 35.0
    az = bodyqa.azimuths(round(az3, 1))
    iris = np.asarray(iris, float)
    return {v: dict(az=float(az[v]), origin=bodyqa.origin(v, az[v], iris, centre), L=float(L), ppl=ppl)
            for v in VIEWS if v in D['figures']}


# ------------------------------------------------------------------------------------------------------------ place
def project(strokes, pieces, fr, ss=OPTS['ss'], skin=None, names=None, occ=()):
    """a view's strokes (u, z L round its origin) cast along it onto the nearest piece (the skin occluding): each point
    -> (piece name, triangle, barycentric, world point) or None. pieces {name: dict(V, T)}; fr: frames()' view;
    names: the pieces strokes may land on."""
    from . import raster
    names = list(names or pieces)
    pts = np.concatenate(strokes) if strokes else np.zeros((0, 2))
    if not len(pts):
        return []
    a = np.radians(fr['az'])
    eu, d, Lw = np.array([np.cos(a), np.sin(a), 0.0]), view_dir(fr['az']), fr['L']
    pad = 0.05
    win = dict(x=float(np.abs(pts[:, 0]).max() + pad), top=float(pts[:, 1].max() + pad),
               bottom=float(pts[:, 1].min() - pad))
    pix = 1.0 / (fr['ppl'] * ss)
    meshes = [(np.asarray(pieces[n]['V'], float), np.asarray(pieces[n]['T']), 0) for n in names]
    meshes += [(np.asarray(pieces[n]['V'], float), np.asarray(pieces[n]['T']), -1) for n in occ]
    if skin is not None:
        meshes.append((np.asarray(skin[0], float), np.asarray(skin[1]), -1))
    _, lab, mi, ti, _ = raster.window_zbuffer(meshes, fr['az'], fr['origin'], Lw, pix, win, ids=True)
    H, W = lab.shape
    u0, z0 = fr['origin']
    out = []
    for P in strokes:
        rec = []
        for u, z in P:
            c, r = int(np.floor((u + win['x']) / pix)), int(np.floor((win['top'] - z) / pix))
            if not (0 <= r < H and 0 <= c < W) or mi[r, c] < 0 or mi[r, c] >= len(names):
                rec.append(None)
                continue
            n = names[mi[r, c]]
            V, T = meshes[mi[r, c]][0], meshes[mi[r, c]][1]
            t = int(ti[r, c])
            A, B, C = V[T[t]]
            # the ray: world u = u0 + u L along eu, z = z0 + z L, from well in front along the view
            O = eu * (u0 + u * Lw) + np.array([0.0, 0.0, z0 + z * Lw]) - 10.0 * Lw * d
            nrm = np.cross(B - A, C - A)
            den = float(nrm @ d)
            if abs(den) < 1e-18:
                rec.append(None)
                continue
            X = O + d * float(((A - O) @ nrm) / den)
            # barycentric of X on the triangle (clamped: the pixel's hit may sit a sub-pixel off its own triangle)
            v0, v1, v2 = B - A, C - A, X - A
            d00, d01, d11, d20, d21 = v0 @ v0, v0 @ v1, v1 @ v1, v2 @ v0, v2 @ v1
            den2 = d00 * d11 - d01 * d01
            if abs(den2) < 1e-24:
                rec.append(None)
                continue
            b1 = (d11 * d20 - d01 * d21) / den2
            b2 = (d00 * d21 - d01 * d20) / den2
            w = np.clip(np.array([1 - b1 - b2, b1, b2]), 0, None)
            w /= w.sum()
            rec.append((n, t, w, (w[:, None] * V[T[t]]).sum(0)))
        out.append(rec)
    return out


def _interp(arr, T, t, w):
    return (np.asarray(arr)[np.asarray(T)[t]] * w[:, None]).sum(0)


class _Veto:
    """the cross-view rule: a stroke point stays only where every vetoing view that sees it squarely (its facing at
    least veto_face, nothing of ours nearer along its ray by veto_depth) draws a line within veto_near of where it
    lands (near: each view's distance to its nearest drawn line, L, on its design grid)."""

    def __init__(self, frames_, near, pieces, names, skin, o):
        from . import raster
        from charkit.bodyqa import WIN
        self.o, self.near, self.F = o, near, {}
        meshes = [(np.asarray(pieces[n]['V'], float), np.asarray(pieces[n]['T']), 0) for n in names]
        if skin is not None:
            meshes.append((np.asarray(skin[0], float), np.asarray(skin[1]), -1))
        for v in o['veto']:
            if v not in frames_ or v not in near:
                continue
            fr = frames_[v]
            depth, _ = raster.window_zbuffer(meshes, fr['az'], fr['origin'], fr['L'], 1.0 / fr['ppl'], WIN)
            self.F[v] = (fr, depth)
        self.win = WIN

    def ok(self, X, N, src):
        """is a point X (world) with shading normal N, traced from view src, supported in every vetoing view?"""
        for v, (fr, depth) in self.F.items():
            if v == src:
                continue
            a = np.radians(fr['az'])
            d = view_dir(fr['az'])
            vf = self.o['veto_face']
            if float(-d @ N) < (vf.get(v, 0.65) if isinstance(vf, dict) else vf):
                continue
            u = (X[0] * np.cos(a) + X[1] * np.sin(a) - fr['origin'][0]) / fr['L']
            z = (X[2] - fr['origin'][1]) / fr['L']
            c, r = int(np.floor((u + self.win['x']) * fr['ppl'])), int(np.floor((self.win['top'] - z) * fr['ppl']))
            H, W = depth.shape
            if not (0 <= r < H and 0 <= c < W):
                continue
            if float(d @ X) > depth[r, c] + self.o['veto_depth'] * fr['L']:
                continue                                         # (hidden there)
            nm = self.near[v]
            if r < nm.shape[0] and c < nm.shape[1] and nm[r, c] > self.o['veto_near']:
                return False
        return True


def place(pieces, strokes, frames_, L, opts=None, skin=None, log=None, near=None, families=MASS):
    """the traced strokes (trace()) placed on the pieces: projected along their views, kept where their view faces the
    surface (within `margin` of the best view's facing, at least `min_face`) and where every other view that sees them
    squarely draws a line near them (near: trace()'s distance images; None: no veto), as ribbons -> ({piece name:
    dict(verts, faces, vn, strand, lock)}, a report)."""
    o = dict(OPTS, **(opts or {}))
    names = [n for n, p in pieces.items() if p.get('family') in families]
    occ = [n for n, p in pieces.items() if p.get('family') in MASS + ('buns',) and n not in names]
    dirs = {v: view_dir(f['az']) for v, f in frames_.items()}
    veto = _Veto(frames_, near, pieces, names + occ, skin, o) if near and o.get('veto') else None
    runs = {}                                  # piece -> [(points (k, 3), normals, locks)]
    rep = dict(views={}, pieces={})
    for v, S in strokes.items():
        if v not in frames_ or not S:
            continue
        got = project(S, pieces, frames_[v], o['ss'], skin, names, occ)
        kept_len = vetoed = 0.0
        for P2, rec in zip(S, got):
            seg = []
            for x in rec + [None]:
                ok = False
                if x is not None:
                    n, t, w, X = x
                    p = pieces[n]
                    N = _interp(p['vn_shade'], p['T'], t, w)
                    N /= max(np.linalg.norm(N), 1e-12)
                    face = {k: float(-dk @ N) for k, dk in dirs.items()}
                    ok = face[v] >= o['min_face'] and face[v] >= max(face.values()) - o['margin']
                    if ok and veto is not None and not veto.ok(X, N, v):
                        ok = False
                        vetoed += 1
                    if ok and seg and seg[-1][0] != n:
                        ok = 'split'
                if ok is True:
                    lk = int(np.asarray(p['lock'])[np.asarray(p['T'])[t][int(np.argmax(w))]])
                    seg.append((n, X, N, lk))
                    continue
                if len(seg) >= 2:
                    Ps = np.array([s_[1] for s_ in seg])
                    ln = float(np.linalg.norm(np.diff(Ps, axis=0), axis=1).sum())
                    if ln >= o['min_run'] * L:
                        runs.setdefault(seg[0][0], []).append((Ps, np.array([s_[2] for s_ in seg]),
                                                               np.array([s_[3] for s_ in seg])))
                        kept_len += ln
                seg = []
                if ok == 'split':
                    lk = int(np.asarray(p['lock'])[np.asarray(p['T'])[t][int(np.argmax(w))]])
                    seg = [(n, X, N, lk)]
        rep['views'][v] = dict(strokes=len(S), traced_L=round(sum(float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())
                                                                       for P in S), 3),
                               kept_L=round(kept_len / L, 3), vetoed_points=int(vetoed))
    out = {}
    for n, rs in runs.items():
        K = ribbons(rs, L, o)
        if K is not None:
            out[n] = K
            rep['pieces'][n] = dict(strokes=len(rs), verts=len(K['verts']))
    if log:
        log('hair strokes: %s' % ', '.join('%s %d' % (k, r['strokes']) for k, r in rep['pieces'].items()))
    return out, rep


def ribbons(runs, L, o):
    """runs [(points (k, 3) world, normals (k, 3), locks (k,))] as tapered ribbons on their surface -> dict(verts,
    faces (quads split in two triangles), vn, strand, lock) or None."""
    width, lift, step = o['width'] * L, o['lift'] * L, o['step'] * L
    taper, tip = o['taper'], o['tip']
    V, F, N_, S_, K_ = [], [], [], [], []
    for P, N, lk in runs:
        sl = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
        if sl[-1] < 2 * step:
            continue
        sa = np.linspace(0, sl[-1], max(3, int(round(sl[-1] / step)) + 1))
        Ps = np.stack([np.interp(sa, sl, P[:, k]) for k in range(3)], 1)
        Ns = np.stack([np.interp(sa, sl, N[:, k]) for k in range(3)], 1)
        Ns /= np.maximum(np.linalg.norm(Ns, axis=1, keepdims=True), 1e-15)
        ks = lk[np.clip(np.searchsorted(sl, sa), 0, len(lk) - 1)]
        Tg = np.gradient(Ps, axis=0)
        Tg /= np.maximum(np.linalg.norm(Tg, axis=1, keepdims=True), 1e-15)
        Sd = np.cross(Ns, Tg)
        Sd /= np.maximum(np.linalg.norm(Sd, axis=1, keepdims=True), 1e-15)
        f_ = sa / sa[-1]
        e_ = np.minimum(f_, 1 - f_) / max(taper / 2, 1e-9)
        hw = 0.5 * width * (tip + (1 - tip) * np.clip(e_, 0, 1))
        base = len(V)
        for i in range(len(sa)):
            c_ = Ps[i] + Ns[i] * lift
            V += [c_ + Sd[i] * hw[i], c_ - Sd[i] * hw[i]]
            N_ += [Ns[i], Ns[i]]
            S_ += [Tg[i], Tg[i]]
            K_ += [ks[i], ks[i]]
        for i in range(len(sa) - 1):
            a_ = base + 2 * i
            # (a quad's two triangles, wound so their normal is the surface's: outward)
            F += [(a_, a_ + 1, a_ + 3), (a_, a_ + 3, a_ + 2)]
    if not F:
        return None
    V = np.asarray(V, float)
    F = np.asarray(F, np.int64)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    Nn = np.asarray(N_, float)
    flip = (fn * Nn[F[:, 0]]).sum(1) < 0
    F[flip] = F[flip][:, [0, 2, 1]]
    return dict(verts=V, faces=F, vn=Nn, strand=np.asarray(S_, float), lock=np.asarray(K_, int))


# ------------------------------------------------------------------------------------------------------------ apply
def apply(R, K):
    """the ribbons K (place()'s) appended to R's pieces (hairpieces.build's) in place: their vertices after the piece's
    with its shading normals, strand and lock arrays extended, outline_w 0 on them (the piece's own kept or 1), shell
    False, and a per-face `ink` mask (the build's ink slot)."""
    for n, k in K.items():
        p = R['pieces'][n]
        nv, nt = len(p['V']), len(p['T'])
        m = len(k['verts'])
        p['V'] = np.r_[np.asarray(p['V'], float), k['verts']]
        p['T'] = np.r_[np.asarray(p['T']), k['faces'] + nv]
        p['vn_shade'] = np.r_[np.asarray(p['vn_shade'], float), k['vn']]
        st = np.asarray(p['strand'], float)
        p['strand'] = np.r_[st, k['strand'] if st.ndim == 2 else np.zeros(m, st.dtype)]
        p['lock'] = np.r_[np.asarray(p['lock']), k['lock'].astype(np.asarray(p['lock']).dtype)]
        ow = np.asarray(p['outline_w'], float) if p.get('outline_w') is not None else np.ones(nv)
        p['outline_w'] = np.r_[ow, np.zeros(m)]
        if p.get('shell') is not None:
            p['shell'] = np.r_[np.asarray(p['shell'], bool), np.zeros(m, bool)]
        if p.get('outer') is not None:
            p['outer'] = np.r_[np.asarray(p['outer'], bool), np.zeros(m, bool)]
        ink = np.asarray(p['ink'], bool) if p.get('ink') is not None else np.zeros(nt, bool)
        p['ink'] = np.r_[ink, np.ones(len(k['faces']), bool)]
    return R


def build(R, spec, iris, centre, L, opts=None, skin=None, log=print):
    """trace, place and apply in one: R's pieces with the design's interior strokes (opts: hair.shape.strokes); iris
    our iris centres, centre the head's (the QA's frames) -> the report."""
    o = dict(OPTS, **(opts or {}))
    S, near = trace(spec, o)
    F = frames(spec, iris, centre, L)
    K, rep = place(R['pieces'], S, F, L, o, skin=skin, log=log, near=near)
    apply(R, K)
    if o.get('buns'):
        ob = dict(o, veto=o['bun_veto'], veto_face=o['bun_veto_face'] if o.get('bun_veto_face') is not None else
                  o['veto_face'])
        Kb, rb = place(R['pieces'], trace_buns(spec, o), F, L, ob, skin=skin, log=log, near=near, families=('buns',))
        apply(R, Kb)
        rep['buns'] = rb
    return rep
