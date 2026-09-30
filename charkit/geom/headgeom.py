"""The authored head's geometry, apart from how it's fitted to the design (charkit/geom/headfit.py): its sections, the
placement of chart points on them, the cage on the head's own chart (charkit.geom.headmesh.cylinder), and a fitted mesh's
health. The build's side (charkit/code_base.py, in Blender) reads only this and headmesh: the fitting reads the reference
images and the QA's measures, which a build stage mustn't depend on (charkit.cache: a QA edit would invalidate it)."""
import numpy as np

class Sections:
    """the head as one closed section per row: its radius r[k, j] at angle TH[j] round the row's centre (0, cy[k]),
    angle 0 toward the front (-y) and increasing toward her left (+x). zs descend (the skull's grid rows)."""
    N = 256

    def __init__(self, zs, cy, r):
        self.zs, self.cy, self.r = zs, cy, r
        self.th = np.linspace(-np.pi, np.pi, self.N, endpoint=False)

    def xy(self, k):
        return np.sin(self.th) * self.r[k], self.cy[k] - np.cos(self.th) * self.r[k]

    def solid(self, A):
        """the sections as occupancy on A's grid (A.zs must be the sections' rows)."""
        X, Yg = np.meshgrid(A.xs, A.ys, indexing='ij')
        V = np.zeros((len(A.xs), len(A.ys), len(self.zs)), bool)
        for k in range(len(self.zs)):
            if not np.isfinite(self.r[k]).all() or self.r[k].max() <= 0:
                continue
            dx, dy = X, Yg - self.cy[k]
            th = np.arctan2(dx, -dy)
            rr = np.interp(th, self.th, self.r[k], period=2 * np.pi)
            V[:, :, k] = np.hypot(dx, dy) <= rr
        return V

def _smooth_rows(v, sigma):
    """a Gaussian over rows (sigma in rows) of a series with NaNs (weights renormalised)."""
    from scipy.ndimage import gaussian_filter1d
    ok = np.isfinite(v)
    num = gaussian_filter1d(np.where(ok, v, 0.0), sigma)
    den = gaussian_filter1d(ok.astype(float), sigma)
    return np.where(ok, num / np.maximum(den, 1e-9), np.nan)

def _smoothstep(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)

def _row_at(S, z):
    """the sections interpolated to height z -> (cy, r (N,)) or None outside them."""
    ok = np.isfinite(S.cy) & np.isfinite(S.r).all(1)
    zs = S.zs[ok]
    if not (zs.min() <= z <= zs.max()):
        return None
    i = np.clip(np.searchsorted(-zs, -z), 1, len(zs) - 1)
    t = (zs[i - 1] - z) / (zs[i - 1] - zs[i])
    return (1 - t) * S.cy[ok][i - 1] + t * S.cy[ok][i], (1 - t) * S.r[ok][i - 1] + t * S.r[ok][i]

def place(S, theta, z):
    """chart points (theta round the head, 0 the front; z) onto the sections' surface -> (N, 3)."""
    out = np.full((len(theta), 3), np.nan)
    for zz in np.unique(z):
        row = _row_at(S, zz)
        if row is None:
            continue
        cy, r = row
        sel = z == zz
        rr = np.interp(theta[sel], S.th, r, period=2 * np.pi)
        out[sel] = np.stack([np.sin(theta[sel]) * rr, cy - np.cos(theta[sel]) * rr, np.full(sel.sum(), zz)], 1)
    return out

def theta_of(S, x, z):
    """the front angle at which the surface at height z reaches front-view x."""
    row = _row_at(S, z)
    cy, r = row
    front = np.abs(S.th) <= np.pi / 2
    xs = np.sin(S.th[front]) * r[front]
    o = np.argsort(xs)
    return float(np.interp(x, xs[o], S.th[front][o]))

def _inside(S, P):
    """points (N, 3) inside the sections' solid (each row's polar outline round its centre; rows interpolated)."""
    zs = S.zs
    k = np.clip(np.searchsorted(-zs, -P[:, 2]), 1, len(zs) - 1)       # zs descend
    t = np.clip((zs[k - 1] - P[:, 2]) / (zs[k - 1] - zs[k]), 0, 1)
    out = np.zeros(len(P), bool)
    valid = np.nonzero(np.isfinite(S.cy) & np.isfinite(S.r).all(1))[0]
    within = (P[:, 2] <= zs[valid[0]]) & (P[:, 2] >= zs[valid[-1]])   # above the top row or under the last: outside
    ok = np.isfinite(S.cy[k - 1]) & np.isfinite(S.cy[k]) & within
    cy = np.where(ok, (1 - t) * S.cy[k - 1] + t * S.cy[k], np.nan)
    dx, dy = P[:, 0], P[:, 1] - cy
    th = np.arctan2(dx, -np.nan_to_num(dy))
    j = np.round((th + np.pi) / (2 * np.pi) * len(S.th)).astype(int) % len(S.th)
    rr = (1 - t) * S.r[k - 1, j] + t * S.r[k, j]
    out[ok] = (np.hypot(dx, dy) <= rr)[ok]
    return out

def project(S, origins, dirs, reach=1.2, step=0.002):
    """each ray (origin inside the head, direction) marched out to where it leaves the sections' solid -> (N, 3)."""
    d = dirs / np.maximum(np.linalg.norm(dirs, axis=1, keepdims=True), 1e-12)
    ts = np.arange(0, reach, step)
    last = np.zeros(len(origins))
    for t in ts:
        ins = _inside(S, origins + t * d)
        last = np.where(ins, t, last)
    return origins + last[:, None] * d

def front_point(S, x, z):
    """the surface's front point at front-view (x, z) (arrays): per row, the angle where the outline reaches x."""
    zs = S.zs
    out = np.full((len(x), 3), np.nan)
    for i, (xx, zz) in enumerate(zip(x, z)):
        k = int(np.argmin(np.abs(zs - zz)))
        if not np.isfinite(S.cy[k]):
            continue
        front = np.abs(S.th) <= np.pi / 2
        xs = np.sin(S.th[front]) * S.r[k, front]
        ys = S.cy[k] - np.cos(S.th[front]) * S.r[k, front]
        o = np.argsort(xs)
        if xs.min() <= xx <= xs.max():
            out[i] = (xx, np.interp(xx, xs[o], ys[o]), zz)
    return out

def sections_mesh(S, step=2):
    """the sections as a closed-top mesh: rows of the (angle, height) grid joined as quads (split to triangles), the top
    closed by a fan to its centre, the bottom (the neck) open -> Mesh."""
    from .mesh import Mesh
    rows = [k for k in range(0, len(S.zs), step) if np.isfinite(S.cy[k]) and np.isfinite(S.r[k]).all()]
    n = len(S.th)
    V = []
    for k in rows:
        x, y = S.xy(k)
        V.append(np.stack([x, y, np.full(n, S.zs[k])], 1))
    V = np.concatenate(V + [[[0.0, S.cy[rows[0]], S.zs[rows[0]]]]])
    F = []
    for i in range(len(rows) - 1):
        a, b = i * n, (i + 1) * n
        for j in range(n):
            j1 = (j + 1) % n
            F += [[a + j, b + j, b + j1], [a + j, b + j1, a + j1]]
    top = len(V) - 1
    F += [[top, j, (j + 1) % n] for j in range(n)]
    m = Mesh(V, np.array(F))
    from .mesh import signed_volume
    if signed_volume(m.V, m.F) < 0:
        m.F = m.F[:, ::-1]
    return m

def quality(V, F, O=None):
    """a fitted quad mesh's health: faces flipped against the way out (each face's normal against the direction from its
    rays' origins, or from the mesh's centroid), and each quad's worst corner (the smallest signed sine of its four
    corners in its own plane: 1 a square, 0 a degenerate corner, < 0 a folded one) -> dict."""
    P = V[F]
    n = np.cross(P[:, 2] - P[:, 0], P[:, 3] - P[:, 1])
    c = P.mean(1)
    out = c - (O[F].mean(1) if O is not None else V.mean(0))
    flipped = (np.einsum('ij,ij->i', n, out) < 0)
    nn = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    worst = np.full(len(F), np.inf)
    for i in range(4):
        a, b, d = P[:, i], P[:, (i + 1) % 4], P[:, (i - 1) % 4]
        e1, e2 = b - a, d - a
        s = np.einsum('ij,ij->i', np.cross(e1, e2), nn) / np.maximum(np.linalg.norm(e1, axis=1) * np.linalg.norm(e2, axis=1), 1e-12)
        worst = np.minimum(worst, s)
    return {'faces': len(F), 'flipped': int(flipped.sum()), 'folded_corners': int((worst < 0).sum()),
            'corner_p05': round(float(np.percentile(worst, 5)), 3), 'corner_min': round(float(worst.min()), 3),
            'flipped_idx': np.nonzero(flipped | (worst < 0))[0]}

def _neighbours(F, n):
    """vertex adjacency of a quad mesh -> (indices (E,), offsets (n + 1,)) in CSR form."""
    E = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 3]], F[:, [3, 0]]])
    E = np.unique(np.sort(np.concatenate([E, E[:, ::-1]]), 1), axis=0)
    E = np.concatenate([E, E[:, ::-1]])
    o = np.argsort(E[:, 0], kind='stable')
    E = E[o]
    off = np.searchsorted(E[:, 0], np.arange(n + 1))
    return E[:, 1], off

def _harmonic(values, fixed, nb, off, iters=300):
    """values (n, k) relaxed to the mean of their neighbours where not fixed (Jacobi iterations)."""
    V = values.copy()
    deg = np.diff(off)
    owner = np.repeat(np.arange(len(V)), deg)
    free = ~fixed
    for _ in range(iters):
        acc = np.zeros_like(V)
        np.add.at(acc, owner, V[nb])
        mean = acc / np.maximum(deg, 1)[:, None]
        V[free] = mean[free]
    return V

def _near(mask, nb, off, k):
    """the vertices within k rings of a mask."""
    out = mask.copy()
    owner = np.repeat(np.arange(len(mask)), np.diff(off))
    for _ in range(k):
        grow = np.zeros(len(mask), bool)
        grow[owner[out[nb]]] = True
        out |= grow
    return out

JAW_BAND_DZ = 0.0075     # L of chart height per cage row in the jaw's band (its columns run over the chin, back along
                         # the underside and down the neck to the band's foot: in front three times its height)
JAW_BAND_END = 0.11      # L under the mouth block: the band ends at the first cage row this far down (the neck under
                         # the throat; under it, to the join, the rows are on the sections, their spacing growing
                         # evenly from the band's to the cage's own)
JAW_TOP_GAP = 0.012      # L: the underside kept this far under the band's top row (the mouth block's bottom)
POCKET_FADE = 0.02       # L: the pocket under the jaw, whole over the neck's width, fades out over this past it
TIP_BIAS = (0.006, 0.06) # L: the rim's target lowered this much at the chin point, tapering to nothing this far out: the
                         # subdivision rounds the V's point across the cage's columns (0.033 L apart there), which
                         # raises it that much (headfit.CHIN_BIAS does the same in profile)
UNDER_ROUND = (0.75, 1.15, 0.12)  # the underside's slope: this share of the rise at the rim, this share UNDER_ROUND[2] L in
                                  # (the start kept steeper than the boards' camera looks down at the chin, 6.5 degrees)
POCKET_MIN = 0.005       # L: the least depth of the pocket at a column's rim (less: the column is the envelope's)
POCKET_DROP = 0.1        # L: where the pocket fades out the underside sinks this far (a gentle wall, not a cliff the
                         # columns' solve can't follow; the cap keeps it off the jaw's sides anyway)


EDGE_TIP = (0.03, 0.07)  # L of the V's half-width: the edge's depth correction fades in over this (at the point the cage
                         # rounds the V anyway)
EDGE_BAND = False        # the band's top raised round the sides, UnderJaw's pocket under the jaw's side (off: the side
                         # columns found no rim, their rows twisted along the neck's sides, the three-quarter's jaw
                         # line broke off; face.md, the chin's taper)
EDGE_FADE = 0.05         # L: the edge's shaping fades out over this under the jaw angle (where it reaches the side's depth)
EDGE_TOP = 0.04          # L: round the sides the band's top is this far over the jaw's angle
EDGE_TOP_COLS = (0.1, 0.3)   # rad past the mouth block's columns: the band's top starts rising, and over this
EDGE_TOP_BACK = (1.6, 2.0)   # rad round from the front: behind the jaw's angle it comes back down to the block's
EDGE_PHI_FADE = 0.12     # rad round the neck's axis past the jaw's angle: the side's pocket fades out over this
EDGE_Y_FADE = 0.05       # L: the side's pocket fades out over this toward the neck's axis
EDGE_PIECEWISE = False   # the side's rows split at the band's top (the rim held to one row): it twisted them more
EDGE_BUMP = 1.0          # the share of the way out to the edge's point the outline is brought
EDGE_WEDGE = True        # where the edge lies inside the outline, hold the front behind a prow to it
EDGE_PROW = 1.5          # the prow's shape: y from the midline's front to the edge as (|x| / x_V)^this (1 a wedge,
                         # with a ridge down the chin's midline that the cage crumpled; 1.2 left the three-quarter's
                         # hollow at 0.0055 L, 1.5 0.0048)
EDGE_SOFT = 0.004        # L: the prow's hold is a soft maximum over this
EDGE_REF = (0.06, 0.16)  # L of the V's half-width: the design's recession is placed at our chin's depth over this span
# The jaw's side (round 3): the pocket carried round the sides to the jaw's angle along the rim. Each cage column's
# underside hangs from its own rim point (where the jaw's edge crosses the column's sheet), rising inward along the
# column at the jaw's rise to the neck. U's polar form round the neck's axis had swept across the rim going in along a
# side column (the column's rays there start from the sections' own centre, 0.1 L in front of the axis), and the pocket
# dropped out; without it the pocket ended at the neck's width and the side was a ledge at the band's top (z -0.31): the
# three-quarter's jaw line ran flat, then hooked down into the neck. The rows keep the rim and the throat on fixed band
# rows across the pocket's columns (edge loops along the jaw line), so no row runs from the face onto the underside
# between two columns.
SIDE = True              # the per-column pocket round the sides (style face.jaw_side); False: UnderJaw's U (the chin only)
SIDE_ROWS = (3, 9)       # the band's rows under its top (the mouth block's bottom) that the rim and the throat keep
                         # round the sides. (4, 11): 14 edges over 90 degrees where the neck's rows met them; (4, 10):
                         # 2, and two faces at the jaw's side just past the neck's width turned in and back (x 0.13,
                         # z -0.296: the rows over the rim crowded where the band's top starts to rise; face_folds 4 ->
                         # 32 on the box, those two under every mouth key); (3, 9): none, the sharpest edge 85 degrees
SIDE_FADE = 0.2          # rad round the band's centre past the jaw's angle: the pocket blends into the envelope over this
SIDE_EASE = (0.4, 0.7)   # rad round the band's centre: the rows' map eases from the linear one (the chin's, where the
                         # rim and the throat fall on rows 3-5 and 8-12 of the band) to SIDE_ROWS over this
SIDE_UOLD = None         # rad (a, b): the chin's columns keep U's height (the polar form) under a, the per-column form
                         # over b. (0.45, 0.7): the board's chin_angle 116.3 -> 119.9, but a kink where the V crosses
                         # the neck's edge (jaw_line_bend 4.9 -> 7.8): off
SIDE_RELAX = 1.0         # rad past the jaw's angle: behind it the rows (the rim's at the jaw angle's height there) ease
                         # back to level over this (dropped over the pocket's fade alone, 0.1 L in two columns, they folded)
SIDE_DROP = 0.05         # L: behind the jaw's angle the throat's row runs this far under the rim's (no underside there)
SIDE_RIMFIT = 0          # (lab) rounds of re-hanging each column's underside so its rim lands on the edge's height at its x
SIDE_RIMFIT_A = 9.0      # (lab) rad: ... in the columns under this angle round the band's centre only
SIDE_RIM_ROW = False     # the rim on its row (SIDE_ROWS[0]) at the chin too: the jaw line one edge loop from the chin
                         # round to the jaw's angle
JAW_CREASE = 0           # the rim's loop creased this many columns either side of the chin's (0: none)


def jaw_depth(jaw):
    """the jaw edge's depth behind the chin point per unit of its half-width, the design's (jaw['depth']: [x], [D] from
    the front's V and the three-quarter's jaw line, headfit.jaw_depth) -> D(x) or None: monotone, through the point, a
    quadratic's least squares, continued past its last sample at its end slope."""
    dd = jaw.get('depth')
    if not dd or len(dd[0]) < 4:
        return None
    x, D = np.asarray(dd[0], float), np.asarray(dd[1], float)
    o = np.argsort(x)
    x, D = x[o], np.maximum.accumulate(D[o])
    c = np.linalg.lstsq(np.stack([x, x * x], 1), D, rcond=None)[0]
    xe = float(x.max())
    se = max(float(c[0] + 2 * c[1] * xe), 0.0)
    De = float(c[0] * xe + c[1] * xe * xe)
    return lambda q: np.where(np.asarray(q) <= xe, c[0] * np.asarray(q) + c[1] * np.asarray(q) ** 2,
                              De + se * (np.asarray(q) - xe))


def jaw_envelope(S, jaw, log=None):
    """the mesh's envelope with the jaw's edge (the sections S stay the hull's, the eyes', the hair's): the design's
    jaw line as one edge in 3D, its V in front (jaw['x'], jaw['z']) at the depth the design's three-quarter puts it
    (jaw_depth: its recession from the chin point, placed at our chin's own depth over EDGE_REF). Per row up to the jaw
    angle (where that depth reaches the side's), for the V's half-width x_V at the row's height, the outline is made to
    pass through the edge's point (x_V, y_J), faded in over EDGE_TIP of x_V and out over EDGE_FADE over the angle:
      - where the point lies outside it, moved out radially round the row's centre (a smooth bump at its angle, 0 at
        the midline: the profile stays the design's);
      - where inside, the front held behind a prow from the midline's front to it (EDGE_PROW: round at the midline).
    Our chin had a flat front near its point and sides that swung back late (0.05 L behind the design's edge where the
    V crosses the neck): the boards' camera, 6 degrees over the chin, lifts what lies further back, and read it as a
    round bottom with steep sides; in three-quarter it left a hollow over the chin. UnderJaw's rim then lies on the
    edge, and cylinder_cage carries the pocket under it round the sides (the band's top raised there). -> (Sections,
    info: y_ref, z_angle (the jaw angle's height), rows) or (S, None) without the design's depth.
    """
    Dfn = jaw_depth(jaw)
    if Dfn is None:
        return S, None
    th = S.th
    ok = np.isfinite(S.cy) & np.isfinite(S.r).all(1)
    jx, jz = np.asarray(jaw['x'], float), np.asarray(jaw['z'], float)
    chin = float(jaw['chin'])
    tmp = UnderJaw(S, jaw, chin + 0.07, chin - 0.1)      # (its rim: the envelope's front on the V, and the neck)
    x_neck = tmp.x_neck
    # our chin's depth for the design's recession: the rim's own over EDGE_REF, less the design's there
    sel = (tmp.jx >= EDGE_REF[0]) & (tmp.jx <= EDGE_REF[1])
    y_ref = float(np.median(tmp.y0[sel] - Dfn(tmp.jx[sel]))) if sel.any() else float(tmp.y0[0])
    R = S.r.copy()
    rows, z_g = [], None
    for k in np.nonzero(ok & (S.zs >= chin - 0.01) & (S.zs <= jz.max()))[0][::-1]:     # from the chin up
        zz, cy = float(S.zs[k]), float(S.cy[k])
        xV = float(np.interp(zz, jz, jx))
        yJ = y_ref + float(Dfn(xV))
        x, y = np.sin(th) * R[k], cy - np.cos(th) * R[k]
        y_side = float(y[np.argmax(x)])
        if z_g is None and yJ >= y_side and xV > x_neck:
            z_g = zz                                      # the jaw angle: the edge at the side's depth
        beta = 1.0 if z_g is None else float(_smoothstep(1 - (zz - z_g) / EDGE_FADE))
        if beta <= 0:
            break
        if xV < 1e-3:
            continue
        yJ = min(yJ, y_side)
        tJ = float(np.arctan2(xV, cy - yJ))
        rJ = float(np.hypot(xV, cy - yJ))
        r = R[k].copy()
        a = np.abs(th)
        bump = np.where(a <= tJ, np.sin(0.5 * np.pi * a / tJ) ** 2,
                        np.where(a - tJ < tJ, np.cos(0.5 * np.pi * (a - tJ) / tJ) ** 2, 0.0))
        w_tip = float(_smoothstep((xV - EDGE_TIP[0]) / (EDGE_TIP[1] - EDGE_TIP[0])))
        d = rJ - float(np.interp(tJ, th, r, period=2 * np.pi))
        if d >= 0:                                        # the edge further out: the outline brought out to it
            r = r + beta * w_tip * EDGE_BUMP * d * bump
        elif EDGE_WEDGE:                                  # further in: the front held behind a convex curve from
            ym = cy - float(r[int(np.argmin(np.abs(th)))])     # the midline's front to the edge (a prow, round at the
            x, y = np.sin(th) * r, cy - np.cos(th) * r         # midline: no ridge down the chin; a soft max, no kink)
            s_ = np.minimum(np.abs(x) / xV, 1.0)
            prow = ym + (yJ - ym) * s_ ** EDGE_PROW
            front = (np.cos(th) > 0) & (y < yJ + 0.02)
            k_ = EDGE_SOFT
            y2 = y + k_ * np.logaddexp(0.0, (prow - y) / k_) - k_ * np.log(2.0) * np.exp(-((prow - y) / k_) ** 2)
            y2 = np.where(front, y + beta * w_tip * (np.maximum(y2, y) - y), y)
            tn = np.arctan2(x, -(y2 - cy)); o = np.argsort(tn)
            r = np.interp(th, tn[o], np.hypot(x, y2 - cy)[o], period=2 * np.pi)
        R[k] = r
        rows.append((round(zz, 4), round(xV, 4), round(yJ, 4), round(beta, 3)))
    info = dict(y_ref=round(y_ref, 4), z_angle=None if z_g is None else round(z_g, 4), x_neck=round(x_neck, 4),
                rows=rows[::8])
    if log:
        log('jaw edge: depth placed at %.3f, jaw angle %s' % (y_ref, info['z_angle']))
    return Sections(S.zs, S.cy, R), info


class UnderJaw:
    """the jaw's underside, which one closed section per row can't hold (the chin overhangs the neck: between the chin
    point and the throat a row crosses the chin, then air, then the neck). The sections S stay the envelope (each row's
    outline, the air under the chin filled); the solid is the envelope less a pocket:
      - the underside: z = U(x, y), from the design's jaw line in front (jaw['x'], jaw['z']: the V, the lower face's
        outline over x) laid on the envelope's front (the rim), rising from it at jaw['rise'] degrees along lines in
        plan toward the neck's axis (straight back at the midline, round toward the neck at the sides), kept
        JAW_TOP_GAP under z_top (so it never reaches the jaw's sides over the neck's width: their outline is the
        envelope's own, a silhouette against what's behind); with `top` (theta -> the band's top per column: raised
        round the sides) under that column's top, and with `phi_end` the pocket reaches round the sides to that angle
        round the neck's axis (the jaw's angle: its side's underside, the rim there the jaw edge, jaw_envelope);
      - the pocket: under U, outside the neck, over the neck (whole within its half-width, fading out over POCKET_FADE past it)
        and in front of its axis; a column holds it where it is POCKET_MIN deep at least, its underside continuous and its
        throat no lower than its rim (round the neck's sides the envelope closes on the neck and the pocket with it). The neck above its top row (z_n0, the first row under the chin that is the neck's
        alone) is that row continued up.
    Each cage column (a sheet of the sections' own rays at one angle, theta round each row's centre) then runs down
    the envelope to the rim (where it meets U), back along U to the neck (the throat) and down the neck: meridian().
    place(theta, z) puts chart rows under z_top along it by arc length, so the cage's rows follow the surface round the
    chin and the chin's underside is its own band of quads (no step for the limit fit to ring on)."""

    def __init__(self, S, jaw, z_top, z_bottom, dz=0.001, reach=0.0, top=None, phi_end=None, side=None):
        self.side = side                                  # dict(z_angle, rows): the per-column pocket round the sides
        self.reach = float(reach)                         # L: the pocket kept whole this far past the neck's width
        self.top = top                                    # the band's top per column (theta -> z; default z_top)
        self.phi_end = phi_end                            # the pocket ends past this angle round the neck's axis
        self.y_fade = 0.05                                # L: ... and fades out over this toward the neck's axis
        self.lat_rise = 0.05                              # L of the top's rise over which the rim's row eases in
        ok = np.isfinite(S.cy) & np.isfinite(S.r).all(1)
        self.S, self.th = S, S.th
        self.zs, self.cy, self.r = S.zs[ok], S.cy[ok], S.r[ok]
        self.z_top, self.z_bottom, self.dz = float(z_top), float(z_bottom), dz
        self.jx, self.jz = np.asarray(jaw['x'], float), np.asarray(jaw['z'], float)
        self.tan = float(np.tan(np.radians(jaw['rise'])))
        j0 = int(np.argmin(np.abs(S.th)))
        front = self.cy - self.r[:, j0]
        # the neck's top row: the first, 0.03 L or more under the chin, whose front is the neck's (within 0.004 L of its
        # median front further down: the rows just under the chin still carry the old step's smoothing, a lip)
        chin = float(jaw['chin'])
        below = self.zs < chin - 0.03
        ref = float(np.median(front[(self.zs < chin - 0.04) & (self.zs > chin - 0.12)])) if below.any() else np.nan
        k0 = np.nonzero(below & (np.abs(front - ref) < 0.004))[0]
        self.k0 = int(k0[0]) if len(k0) else int(np.nonzero(below)[0][0])
        if self.zs[self.k0] < self.z_bottom:                # no lower than the band's foot (the rows under it are the
            self.k0 = int(np.argmin(np.abs(self.zs - self.z_bottom)))   # sections': the neck must meet them there)
        self.z_n0 = float(self.zs[self.k0])
        xn = np.sin(S.th) * self.r[self.k0]
        yn = self.cy[self.k0] - np.cos(S.th) * self.r[self.k0]
        self.neck_poly = (xn, yn)
        self.x_neck = max(float(jaw.get('neck') or 0.0), float(np.abs(xn).max()))       # (the design's, or our neck's if wider)
        self.y_axis = float(0.5 * (yn.min() + yn.max()))
        # the rim no lower than the envelope's own chin at each x (its front there before it steps back to the neck: a
        # head whose rows stop short of the drawn jaw line still gets its rim on the chin), and its depth: the envelope's
        # front a hair over the rim
        self.jz = np.array([max(z, self._chin_bottom(x, z) + 0.003) for x, z in zip(self.jx, self.jz)])
        self.jz = self.jz - TIP_BIAS[0] * np.clip(1 - self.jx / TIP_BIAS[1], 0, 1)
        self.y0 = np.array([self._front_y(x, z + 0.003) for x, z in zip(self.jx, self.jz)])
        # the rim in polar form round the neck's axis (U's lines run toward it): its angle (kept rising: the rim seen
        # from the axis sweeps round one way) and distance
        self.rim_phi = np.maximum.accumulate(np.arctan2(self.jx, self.y_axis - self.y0))
        self.rim_r = np.hypot(self.jx, self.y_axis - self.y0)
        self.y_c = float(self.centre(np.array([0.5 * (self.z_top + self.z_bottom)]))[0])
        self._mer = {}
        if side is not None:                              # the rim by column: the edge's angle round the band's centre
            over = np.nonzero(self.jz > float(side['z_angle']))[0]            # (the V from the chin up to the jaw's angle)
            n = max(2, int(over[0]) if len(over) else len(self.jz))
            c_ = self.centre(self.jz[:n])
            th_e = np.arctan2(self.jx[:n], c_ - self.y0[:n])
            self.rim_th, self.rim_zs = np.maximum.accumulate(th_e), self.jz[:n]
            self.rim_rho = np.hypot(self.jx[:n], c_ - self.y0[:n])

    def z_top_at(self, theta):
        """the band's top at column theta (the chart's height its meridian starts from)."""
        return float(self.top(theta)) if self.top is not None else self.z_top

    def rise(self, d):
        """the underside's height over the rim d L in from it: rounding off the chin, its slope from UNDER_ROUND[0] of the
        rise at the rim to UNDER_ROUND[1] of it UNDER_ROUND[2] L in (the design's underside runs flat under the chin's
        round bottom, then climbs to the throat; a line fitted over its middle reads the rise)."""
        a, b, d1 = UNDER_ROUND
        s0, s1 = a * self.tan, b * self.tan
        d = np.asarray(d, float)
        dp = np.maximum(d, 0.0)
        return np.where(d < 0, s0 * d, s0 * dp + (s1 - s0) * np.where(dp < d1, dp * dp / (2 * d1), dp - d1 / 2))

    def _rows(self, z):
        """the envelope's rows at heights z (array) -> (cy (n,), r (n, N))."""
        zl = np.clip(z, self.zs[-1], self.zs[0])
        i = np.clip(np.searchsorted(-self.zs, -zl), 1, len(self.zs) - 1)
        t = (self.zs[i - 1] - zl) / (self.zs[i - 1] - self.zs[i])
        return (1 - t) * self.cy[i - 1] + t * self.cy[i], (1 - t)[:, None] * self.r[i - 1] + t[:, None] * self.r[i]

    def _chin_bottom(self, x, z, span=0.04, step=0.001):
        """the lowest height near z (within span) at which the envelope's front at lateral x is still the chin's: under
        it the front steps back past the neck's (the neck's top row's front, continued up)."""
        xn, yn = self.neck_poly
        fr_ = yn < self.y_axis
        o = np.argsort(xn[fr_])
        neck_front = float(np.interp(x, xn[fr_][o], yn[fr_][o], left=np.inf, right=np.inf))
        zz = np.arange(z + span, z - span, -step)
        ys = np.array([self._front_y(x, q) for q in zz])
        chin = ys < neck_front - POCKET_MIN
        if not chin.any():
            return z
        k = int(np.nonzero(chin)[0][-1]) if chin.all() else int(np.argmin(chin)) - 1
        return float(zz[max(k, 0)])

    def _front_y(self, x, z):
        """the envelope's front at lateral x on the row at height z: the front-most crossing of its outline with the line
        at x (the outline can turn back in x round its sides)."""
        cy, r = self._rows(np.array([z]))
        xs, ys = np.sin(self.th) * r[0], cy[0] - np.cos(self.th) * r[0]
        x0, x1, y0, y1 = xs, np.roll(xs, -1), ys, np.roll(ys, -1)
        hit = (x0 - x) * (x1 - x) <= 0
        if not hit.any():
            return float(ys[np.argmin(np.abs(xs - x))])
        t = np.where(np.abs(x1 - x0) > 1e-12, (x - x0) / np.where(np.abs(x1 - x0) > 1e-12, x1 - x0, 1.0), 0.0)
        return float(np.min((y0 + t * (y1 - y0))[hit]))

    def U(self, x, y, fade=True):
        """the underside's height at (x, y) (arrays): a ruled surface, from each point of the rim a line in plan toward
        the neck's axis (0, y_axis), rising at the jaw's rise: in polar form round the axis, the rim's height at the
        point's angle plus the rise over how far inside the rim it lies. So it passes through the drawn jaw line exactly,
        rises at the rise straight back down the midline (the profile's underside) and toward the neck round its sides,
        and is continuous; far under the band where there is no pocket."""
        ax, y = np.abs(np.asarray(x, float)), np.asarray(y, float)
        phi = np.arctan2(ax, self.y_axis - y)
        r = np.hypot(ax, self.y_axis - y)
        u = np.interp(phi, self.rim_phi, self.jz) + self.rise(np.interp(phi, self.rim_phi, self.rim_r) - r)
        if self.top is None:
            cap = self.z_top - JAW_TOP_GAP
        else:                                             # (the band's top where the point's column is)
            cap = np.vectorize(self.z_top_at)(np.arctan2(ax, self.y_c - y)) - JAW_TOP_GAP
        u = cap - np.logaddexp(0.0, (cap - u) / 0.004) * 0.004          # a soft min with the cap (0.004 L round it)
        if not fade:                                      # (its height alone: the per-column form ends the pocket)
            return u
        w = _smoothstep((self.x_neck + self.reach + POCKET_FADE - ax) / POCKET_FADE) * _smoothstep((self.y_axis - y) / self.y_fade)
        if self.phi_end is not None:                      # (round the side the pocket ends at the jaw's angle)
            w = w * _smoothstep((self.phi_end + EDGE_PHI_FADE - phi) / EDGE_PHI_FADE)
        return u - POCKET_DROP * (1 - w)

    def centre(self, z):
        """the band's columns hang from a centre line: straight from the top row's centre to the bottom row's through
        the middle (the sections' own centres jump back at the chin's step, which would twist the columns' sheets), eased
        into the sections' own at both ends (sin^2 of the way down: the position and the slope meet the rows over and
        under the band, else the columns shear there and the limit surface's normals kink: a lit ring round the neck)."""
        z = np.asarray(z, float)
        c0, c1 = self._rows(np.array([self.z_top, self.z_bottom]))[0]
        t = np.clip((self.z_top - z) / (self.z_top - self.z_bottom), 0, 1)
        own = self._rows(np.atleast_1d(z))[0].reshape(np.shape(z))
        w = np.sin(np.pi * t) ** 2
        return own + w * (c0 + (c1 - c0) * t - own)

    @staticmethod
    def _ray(theta, xs, ys, c):
        """a closed outline's (points xs, ys) radius at angle theta from (0, c): its polar form round that point."""
        a = np.arctan2(xs, -(ys - c)); rr = np.hypot(xs, ys - c)
        o = np.argsort(a)
        return np.interp(theta, a[o], rr[o], period=2 * np.pi)

    def rho(self, theta, z):
        """the envelope's and the neck's radius along column theta (from the band's centre line) at heights z ->
        (envelope (n,), neck (n,)): the neck is the envelope under z_n0 and its top row continued up above."""
        z = np.asarray(z, float)
        cy, r = self._rows(z)
        cb = self.centre(z)
        st, ct = np.sin(self.th), np.cos(self.th)
        env = np.array([self._ray(theta, st * rr, c - ct * rr, b) for c, rr, b in zip(cy, r, cb)])
        xn, yn = self.neck_poly
        neck = np.array([self._ray(theta, xn, yn, b) if zz > self.z_n0 else e for zz, b, e in zip(z, cb, env)])
        return env, neck

    def _path(self, theta, rho, zz):
        """a column's path (radius, height along column theta round the band's centre line) -> (points (M, 3), arc
        lengths)."""
        P = np.stack([rho * np.sin(theta), self.centre(zz) - rho * np.cos(theta), zz], 1)
        return P, np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])

    def side_weight(self, theta):
        """the pocket's share at column theta in the per-column form: whole up to the jaw's angle (the rim's last
        column), easing to none over SIDE_FADE past it."""
        a = abs(float(np.angle(np.exp(1j * float(theta)))))
        return float(_smoothstep(1 - (a - self.rim_th[-1]) / SIDE_FADE)) if a > self.rim_th[-1] else 1.0

    def _meridian_side(self, theta):
        """the per-column form (self.side): column theta's path down the envelope to its rim point (where the jaw's edge
        crosses the column: the rim's height by the column's angle, the rim held at the jaw's angle past it), in along the
        underside hung from it (the rise over how far in from the rim, capped JAW_TOP_GAP under the column's top) to the
        neck (the throat), down the neck -> (points, arc lengths, info: rim, throat, w (the pocket's share: side_weight),
        env (the envelope's own path and arc lengths, for w < 1))."""
        zt = self.z_top_at(theta)
        zg = np.arange(zt, self.z_bottom - 1e-9, -self.dz)
        zg[-1] = self.z_bottom
        rS, rN = self.rho(theta, zg)
        Pe, se = self._path(theta, rS, zg)
        info = dict(rim=None, throat=None, w=self.side_weight(theta), env=(Pe, se),
                    a=abs(float(np.angle(np.exp(1j * float(theta))))))
        a = min(info['a'], float(self.rim_th[-1]))
        z_e, r_e = float(np.interp(a, self.rim_th, self.rim_zs)), float(np.interp(a, self.rim_th, self.rim_rho))
        if info['w'] <= 0 or z_e >= zt - 0.01 or z_e <= self.z_bottom + 0.01:
            return Pe, se, info
        cap = zt - JAW_TOP_GAP
        c_e, ct = float(self.centre(np.array([z_e]))[0]), float(np.cos(theta))

        st_ = float(np.sin(theta))
        bu = 1.0 if SIDE_UOLD is None else float(_smoothstep((info['a'] - SIDE_UOLD[0]) / (SIDE_UOLD[1] - SIDE_UOLD[0])))

        hang = [z_e]                                      # (the height it hangs from: SIDE_RIMFIT corrects it)

        def Uc(rho, z):                                   # the column's underside: hung from its point of the edge,
            d = (r_e - rho) + (self.centre(z) - c_e) * ct    # rising over how far in from it it lies in plan (the
            u = hang[0] + self.rise(d)                       # column's centre line moves with the height)
            u = cap - np.logaddexp(0.0, (cap - u) / 0.004) * 0.004     # (a soft min with the cap, as U's)
            if bu < 1.0:
                u = bu * u + (1 - bu) * self.U(rho * st_, self.centre(z) - rho * ct, fade=False)
            return u
        for it in range(SIDE_RIMFIT + 1):
            g = zg - Uc(rS, zg)
            cand = np.nonzero((g < 0) & (rS > rN + POCKET_MIN))[0]
            if not len(cand) or cand[0] == 0:
                return Pe, se, info
            i = int(cand[0])
            f = g[i - 1] / (g[i - 1] - g[i])
            z_r, r_r = zg[i - 1] + f * (zg[i] - zg[i - 1]), rS[i - 1] + f * (rS[i] - rS[i - 1])
            if it == SIDE_RIMFIT or info['a'] >= min(float(self.rim_th[-1]), SIDE_RIMFIT_A):
                break
            # the rim where the column's envelope crosses the underside lies off the edge's height at its own x
            # (the envelope's front bulges past the edge's point or falls short of it): hang it again by the gap
            z_t = float(np.interp(abs(r_r * st_), self.jx, self.jz))
            if abs(z_t - z_r) < 1e-4:
                break
            if it:                                        # (a secant step: the rim moves less than the hang)
                gain = float(np.clip((z_r - prev[1]) / (hang[0] - prev[0]) if hang[0] != prev[0] else 1.0, 0.2, 2.0))
            else:
                gain = 1.0
            prev = (hang[0], z_r)
            hang[0] += (z_t - z_r) / gain
        rho_u = np.arange(r_r, 0.0, -self.dz)
        lo, hi = np.full(len(rho_u), z_r - 0.02), np.full(len(rho_u), zt)     # (its height per radius: bisection)
        for _ in range(32):
            m = 0.5 * (lo + hi)
            h = m - Uc(rho_u, m)
            lo, hi = np.where(h < 0, m, lo), np.where(h < 0, hi, m)
        zu = 0.5 * (lo + hi)
        rn_u = self.rho(theta, zu)[1]
        hit = np.nonzero(rho_u <= rn_u)[0]
        j = int(hit[0]) if len(hit) else 0
        if j < 2 or np.abs(np.diff(zu[:j + 1])).max() >= 0.01:
            return Pe, se, info
        d0, d1 = rho_u[j - 1] - rn_u[j - 1], rho_u[j] - rn_u[j]
        f = d0 / (d0 - d1)
        z_j, r_j = zu[j - 1] + f * (zu[j] - zu[j - 1]), rho_u[j - 1] + f * (rho_u[j] - rho_u[j - 1])
        below = zg < z_j
        rho = np.concatenate([rS[:i], [r_r], rho_u[1:j], [r_j], rN[below]])
        zz = np.concatenate([zg[:i], [z_r], zu[1:j], [z_j], zg[below]])
        P, s = self._path(theta, rho, zz)
        info.update(rim=(float(r_r), float(z_r)), throat=(float(r_j), float(z_j)), s_rim=float(s[i]),
                    s_throat=float(s[i + j]))
        return P, s, info

    def meridian(self, theta):
        """column theta's path from z_top to z_bottom -> (points (M, 3), arc length (M,), info dict(rim, throat: (radius,
        z) or None))."""
        key = round(float(theta), 9)
        if key in self._mer:
            return self._mer[key]
        if self.side is not None:
            self._mer[key] = self._meridian_side(theta)
            return self._mer[key]
        zt = self.z_top_at(theta)
        zg = np.arange(zt, self.z_bottom - 1e-9, -self.dz)
        zg[-1] = self.z_bottom
        rS, rN = self.rho(theta, zg)
        cb = self.centre(zg)
        st, ct = np.sin(theta), np.cos(theta)
        g = zg - self.U(rS * st, cb - rS * ct)
        cand = np.nonzero((g < 0) & (rS > rN + POCKET_MIN))[0]
        info = dict(rim=None, throat=None)
        rho, zz = rS, zg
        if len(cand) and cand[0] > 0:
            i = int(cand[0])
            f = g[i - 1] / (g[i - 1] - g[i])
            z_r, r_r = zg[i - 1] + f * (zg[i] - zg[i - 1]), rS[i - 1] + f * (rS[i] - rS[i - 1])
            # the underside: inward from the rim, its height solved per radius (bisection in z: z - U rises with z)
            rho_u = np.arange(r_r, 0.0, -self.dz)
            lo, hi = np.full(len(rho_u), z_r - 0.02), np.full(len(rho_u), self.z_top)   # (it rises from its rim)
            for _ in range(32):
                m = 0.5 * (lo + hi)
                h = m - self.U(rho_u * st, self.centre(m) - rho_u * ct)
                lo, hi = np.where(h < 0, m, lo), np.where(h < 0, hi, m)
            zu = 0.5 * (lo + hi)
            rn_u = self.rho(theta, zu)[1]
            hit = np.nonzero(rho_u <= rn_u)[0]
            j = int(hit[0]) if len(hit) else 0
            if j > 0 and np.abs(np.diff(zu[:j + 1])).max() < 0.01 and zu[j] >= z_r - 0.005:
                d0, d1 = rho_u[j - 1] - rn_u[j - 1], rho_u[j] - rn_u[j]
                f = d0 / (d0 - d1)
                z_j, r_j = zu[j - 1] + f * (zu[j] - zu[j - 1]), rho_u[j - 1] + f * (rho_u[j] - rho_u[j - 1])
                below = zg < z_j
                rho = np.concatenate([rS[:i], [r_r], rho_u[1:j], [r_j], rN[below]])
                zz = np.concatenate([zg[:i], [z_r], zu[1:j], [z_j], zg[below]])
                info = dict(rim=(float(r_r), float(z_r)), throat=(float(r_j), float(z_j)))
        P = np.stack([rho * st, self.centre(zz) - rho * ct, zz], 1)
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
        if info['rim'] is not None:                   # the arc lengths at the rim and the throat
            info['s_rim'], info['s_throat'] = float(s[i]), float(s[i + j])
        self._mer[key] = (P, s, info)
        return self._mer[key]

    def arc(self, theta, z, s, info):
        """chart heights z on column theta -> arc lengths along its meridian (s its arc lengths, info its rim): linear
        from the column's top to the band's foot; where the top is raised over the band's own (round the sides), the
        rows over the band's top run down to the rim and those under it the rest (the underside, the neck), so the rim
        keeps to one chart row across the side's columns (a linear map put a row on the underside in one column and on
        the neck in the next: the quads twisted along the neck's sides), eased in as the top rises."""
        zt = self.z_top_at(theta)
        span = zt - self.z_bottom
        lin = np.clip((zt - np.asarray(z, float)) / span, 0, 1) * s[-1]
        if self.side is not None:
            if info['rim'] is None:
                return self._arc_env(zt, np.asarray(z, float), info)
            return self._arc_side(zt, np.asarray(z, float), s, info)
        if not EDGE_PIECEWISE or self.top is None or zt <= self.z_top + 1e-9 or info['rim'] is None:
            return lin
        b_lin = (zt - self.z_top) / span * s[-1]
        w = float(np.clip((zt - self.z_top) / max(self.lat_rise, 1e-9), 0, 1))
        b = w * info['s_rim'] + (1 - w) * b_lin
        z = np.asarray(z, float)
        above = z >= self.z_top
        q_a = (zt - z) / max(zt - self.z_top, 1e-9) * b
        q_b = b + (self.z_top - z) / (self.z_top - self.z_bottom) * (s[-1] - b)
        return np.clip(np.where(above, q_a, q_b), 0, s[-1])

    def _arc_side(self, zt, z, s, info):
        """the per-column form's rows: the rim on chart row side['rows'][0] and the throat on [1] in every column with
        the pocket, each stretch between (the face down to the rim, the underside, the neck) by chart height."""
        s_r, s_j, s_e = info['s_rim'], info['s_throat'], s[-1]
        b = float(_smoothstep((info['a'] - SIDE_EASE[0]) / (SIDE_EASE[1] - SIDE_EASE[0])))
        span = zt - self.z_bottom                         # (the linear map's own breakpoints, eased to the fixed rows)
        z_R = self.side['rows'][0] if SIDE_RIM_ROW else (1 - b) * (zt - s_r / s_e * span) + b * self.side['rows'][0]
        z_T = (1 - b) * (zt - s_j / s_e * span) + b * self.side['rows'][1]
        q = np.where(z >= z_R, (zt - z) / max(zt - z_R, 1e-9) * s_r,
                     np.where(z >= z_T, s_r + (z_R - z) / (z_R - z_T) * (s_j - s_r),
                              s_j + (z_T - z) / max(z_T - self.z_bottom, 1e-9) * (s_e - s_j)))
        return np.clip(q, 0, s_e)

    def _arc_env(self, zt, z, info):
        """the per-column form's rows on a column's envelope (no pocket: behind the jaw's angle, and blended with the
        pocket's over its fade): the rim's and the throat's rows at heights easing from the jaw angle's (the rim's
        there, SIDE_DROP under it) back to their own over SIDE_RELAX past it, each stretch between by chart height."""
        Pe, se = info['env']
        s_e = se[-1]
        a = info.get('a', np.pi)
        e = float(_smoothstep((self.rim_th[-1] + SIDE_RELAX - a) / SIDE_RELAX))
        span = zt - self.z_bottom
        if e <= 0 or a < self.rim_th[-1] - 1e-9:
            return np.clip((zt - z) / span, 0, 1) * s_e
        z_R, z_T = self.side['rows']
        z_g = float(self.rim_zs[-1])
        h_R = z_R + e * (z_g - z_R)
        h_T = z_T + e * (z_g - SIDE_DROP - z_T)
        zp = Pe[:, 2]
        s_R, s_T = float(np.interp(h_R, zp[::-1], se[::-1])), float(np.interp(h_T, zp[::-1], se[::-1]))
        q = np.where(z >= z_R, (zt - z) / max(zt - z_R, 1e-9) * s_R,
                     np.where(z >= z_T, s_R + (z_R - z) / (z_R - z_T) * (s_T - s_R),
                              s_T + (z_T - z) / max(z_T - self.z_bottom, 1e-9) * (s_e - s_T)))
        return np.clip(q, 0, s_e)

    def place(self, theta, z, part=None):
        """chart points (theta, z) -> (N, 3): at or over z_top and under z_bottom the sections' own (place); between,
        along the column's meridian by arc length (z_top at its start, z_bottom at its end). part: an array (N,) filled with where each point
        fell: 0 the envelope (over the rim, or a column without the pocket), 1 the underside (strictly between the rim and
        the throat), 2 the neck under the throat."""
        theta, z = np.asarray(theta, float), np.asarray(z, float)
        out = place(self.S, theta, z)
        if part is not None:
            part[:] = 0
        zt = np.array([self.z_top_at(t) for t in theta]) if self.top is not None else np.full(len(theta), self.z_top)
        band = (z < zt - 1e-9) & (z >= self.z_bottom - 1e-9)    # (under the band's foot: the sections')
        for t in np.unique(theta[band]):
            sel = band & (theta == t)
            P, s, info = self.meridian(t)
            q = self.arc(t, z[sel], s, info)
            out[sel] = np.stack([np.interp(q, s, P[:, k]) for k in range(3)], 1)
            w = info.get('w', 1.0)
            if info['rim'] is not None and w < 1.0:        # (past the jaw's angle: blended into the envelope's own)
                Pe, se = info['env']
                qe = self._arc_env(self.z_top_at(t), z[sel], info)
                out[sel] = w * out[sel] + (1 - w) * np.stack([np.interp(qe, se, Pe[:, k]) for k in range(3)], 1)
            if part is not None and info['rim'] is not None:
                part[sel] = np.where(q >= info['s_throat'] - 1e-9, 2, np.where(q > info['s_rim'] + 1e-9, 1, 0))
        return out


def orient_faces(V, F):
    """a manifold mesh's faces wound consistently (every shared edge run opposite ways by its two faces), from the face
    furthest forward on the forehead's midline, turned to face forward: the cage's own rule (each quad faces away from
    the head's axis at its height) doesn't hold where the surface faces down, as under the jaw -> F (a copy)."""
    from collections import deque
    F = [list(f) for f in F]
    by = {}
    for i, f in enumerate(F):
        for a, b in zip(f, f[1:] + f[:1]):
            by.setdefault((min(a, b), max(a, b)), []).append(i)
    C = np.array([np.mean([V[k] for k in f], 0) for f in F])
    fore = np.nonzero((np.abs(C[:, 0]) < 0.05) & (np.abs(C[:, 2] - 0.15) < 0.05))[0]
    seed = int(fore[np.argmin(C[fore, 1])]) if len(fore) else int(np.argmin(C[:, 1]))
    P = np.array([V[k] for k in F[seed]])
    if np.cross(P[2] - P[0], P[3 % len(P)] - P[1])[1] > 0:
        F[seed] = F[seed][::-1]
    done = np.zeros(len(F), bool)
    done[seed] = True
    q = deque([seed])
    while q:
        i = q.popleft()
        f = F[i]
        for a, b in zip(f, f[1:] + f[:1]):
            for j in by[(min(a, b), max(a, b))]:
                if done[j]:
                    continue
                g = F[j]
                if any(x == a and y == b for x, y in zip(g, g[1:] + g[:1])):     # the same way round: flip it
                    F[j] = g[::-1]
                done[j] = True
                q.append(j)
    return F


EYE_GAP = 0.035          # L between an eye's outline and its block's edge: room for its rings (0.012 L apart at 3)
EYE_GAP_BELOW = 0.025    # ... under it, where the mouth's block needs the room
EYE_BLOCK = (0.135, 0.09)   # the eye block's least half-width and half-height (L), round the eye centre


def cylinder_cage(S, C, nth=64, dz=0.03, z_top=0.25, z_bottom=-0.6, dome=7, eye_w=0.21, eye_h=0.13, mouth_w=0.12,
                  mouth_h=0.03, rings=(3, 2), caps=True, eye_outline=None, mouth_block=None, mouth_outline=None, jaw=None):
    """the authored cage on the head's own chart (charkit.geom.headmesh.cylinder): rows of the sections from z_top down
    the neck, a dome of rays from the head's centre above, the eyes' and the mouth's blocks where the front view draws
    them. eye_outline: her left eye's opening (K, 2) in L round its centre (x outward, z up; charkit.eyes.
    outline_polygon), the right's mirrored: the lid margin's loop is authored on it, and each eye's block grows to
    hold it with EYE_GAP for the rings; None: an almond eye_w x eye_h. mouth_block: (half-width, above, below) in L round
    the mouth's centre, for the lips' reach (the widest and tallest of its shapes: the rings between them need the room),
    else +-0.09 x +-0.045. mouth_outline: the lip loop (K, 2) in L round the mouth's centre (x her left, z up), else an
    almond mouth_w x mouth_h. jaw: the jaw's underside (headfit.jaw_under's dict): the rows under the mouth block are
    laid JAW_BAND_DZ apart in the chart and placed along UnderJaw's meridians (Cg.under: the UnderJaw; Cg.chart_z: each
    vertex's chart height, for the UVs); None: every row on the sections. -> (Cage, the dome's centre)."""
    from . import headmesh as hm
    ex, mz = C['eye_x'], C['nose_z'] - 0.11
    mw, mt, mb = mouth_block or (0.09, 0.045, 0.045)
    if eye_outline is None:
        a = np.linspace(0, 2 * np.pi, 64, endpoint=False)
        eye_outline = np.stack([eye_w / 2 * np.cos(a), eye_h / 2 * np.sin(a) * (1 + 0.15 * np.cos(a))], 1)
    eo = np.asarray(eye_outline, float)
    bw = max(EYE_BLOCK[0], np.abs(eo[:, 0]).max() + EYE_GAP)
    bt, bb = max(EYE_BLOCK[1], eo[:, 1].max() + EYE_GAP), max(EYE_BLOCK[1], -eo[:, 1].min() + EYE_GAP_BELOW)
    # the mouth block's top half a row clear of the eyes' (no sliver between) and a row under the nose's tip (reaching
    # its underside, the upper lip's rings ran over it and lapped over the open mouth: face_mouth_cover 0.02)
    mt = max(0.045, min(mt, -bb - dz / 2 - mz, C['nose_z'] - dz - mz))
    # the blocks' edges, and the rows the face is sampled on whatever the features' sizes: the nose's tip, and the lines
    # the default blocks put there (a feature's size mustn't move the rows through the nose and the jaw's silhouette),
    # each kept only a third of a row clear of an edge (no sliver row)
    edges = [-bb, bt, mz - mb, mz + mt]
    keep = [z for z in (C['nose_z'], -EYE_BLOCK[1], EYE_BLOCK[1], mz - 0.045, mz + 0.045)
            if min(abs(z - e) for e in edges) > dz / 3]
    zs = hm.lines(z_bottom, z_top, dz, must=edges + keep)[::-1]
    under, edge = None, None
    if jaw:
        # the jaw's band: from the mouth block's bottom row down to the first row JAW_BAND_END under it, whose rows are
        # laid finer and placed along UnderJaw's meridians; the rows under it (the neck down to the join) are the cage's
        # own, on the sections as without the jaw
        z_a = mz - mb
        low = zs[zs <= z_a - JAW_BAND_END + 1e-9]
        z_n = float(low.max()) if len(low) else float(z_bottom)
        n = max(2, int(round((z_a - z_n) / JAW_BAND_DZ)))
        d_band = (z_a - z_n) / n
        # under the band to the join the rows' spacing grows evenly from the band's to the cage's own (an abrupt 4x step
        # concentrated the nape's curvature on one row: the limit surface's normals kinked, a lit ring round the neck)
        span, d1 = z_n - z_bottom, 1.3 * d_band
        m = max(1, int(np.ceil(2 * span / (d1 + dz))))
        dm = 2 * span / m - d1
        steps = d1 + (dm - d1) * np.arange(m) / max(1, m - 1)
        under_rows = z_n - np.cumsum(steps)
        under_rows[-1] = z_bottom
        zs = np.concatenate([zs[zs >= z_a - 1e-9], z_a - (z_a - z_n) * np.arange(1, n) / n, [z_n], under_rows])
        # the jaw's edge in 3D (the design's three-quarter depth): the mesh's envelope, the sections kept for the rest;
        # round the sides the band's top rises over the jaw's edge (outside the mouth's block), so the jaw's side has an
        # underside of its own, as the chin has, up to the jaw's angle
        S_env, edge = jaw_envelope(S, jaw)
        top = None
        side = SIDE if jaw.get('side') is None else bool(jaw['side'])
        if side and edge and edge.get('z_angle') is not None:
            # the pocket round the sides, per column (SIDE): the band's top raised round the sides over the rim (as
            # EDGE_BAND's), the rim and the throat on fixed band rows
            t_b = abs(theta_of(S, mw, mz))
            z_lat = min(edge['z_angle'] + EDGE_TOP, -EYE_BLOCK[1] - 0.05)

            back = [EDGE_TOP_BACK[0], EDGE_TOP_BACK[1]]      # (set from the rim's end below: the top comes back down
                                                             # behind the jaw once the rows have relaxed, SIDE_RELAX)

            def top(t, z_a=z_a, t_b=t_b, z_lat=z_lat, back=back):
                a_ = abs(float(np.angle(np.exp(1j * t))))
                w_ = _smoothstep((a_ - t_b - EDGE_TOP_COLS[0]) / EDGE_TOP_COLS[1]) * _smoothstep((back[1] - a_) / (back[1] - back[0]))
                return z_a + (z_lat - z_a) * float(w_)
            rows_ = (z_a - SIDE_ROWS[0] * d_band, z_a - SIDE_ROWS[1] * d_band)
            under = UnderJaw(S_env, jaw, z_a, z_n, top=top, side=dict(z_angle=edge['z_angle'], rows=rows_, z_a=z_a,
                                                                       d_band=d_band))
            back[0] = float(under.rim_th[-1]) + SIDE_RELAX
            back[1] = back[0] + (EDGE_TOP_BACK[1] - EDGE_TOP_BACK[0])
        elif EDGE_BAND and edge and edge.get('z_angle') is not None:
            t_b = abs(theta_of(S, mw, mz))                 # (the mouth block's columns)
            z_lat = min(edge['z_angle'] + EDGE_TOP, -EYE_BLOCK[1] - 0.05)

            def top(t, z_a=z_a, t_b=t_b, z_lat=z_lat):
                a_ = abs(float(np.angle(np.exp(1j * t))))
                w_ = _smoothstep((a_ - t_b - EDGE_TOP_COLS[0]) / EDGE_TOP_COLS[1]) * _smoothstep((EDGE_TOP_BACK[1] - a_) / (EDGE_TOP_BACK[1] - EDGE_TOP_BACK[0]))
                return z_a + (z_lat - z_a) * float(w_)
        if under is None:
            under = UnderJaw(S_env, jaw, z_a, z_n, reach=1.0 if top else 0.0, top=top)
            if top is not None:
                xg = float(np.interp(edge['z_angle'], jaw['z'], jaw['x']))
                yg = float(np.interp(xg, under.jx, under.y0))
                under.phi_end = float(np.arctan2(xg, under.y_axis - yg))
                under.y_fade = EDGE_Y_FADE
    th = 2 * np.pi * np.arange(nth) / nth - np.pi
    col = lambda t: int(np.argmin(np.abs(th - t)))
    row = lambda z: int(np.argmin(np.abs(zs - z)))
    okr = np.isfinite(S.cy)
    ctr = np.array([0.0, float(np.interp(-z_top, -S.zs[okr], S.cy[okr])), z_top])

    def dome_place(t, phi):
        d = np.stack([np.sin(t) * np.cos(phi), -np.cos(t) * np.cos(phi), np.sin(phi)], 1)
        return project(S, np.repeat(ctr[None], len(t), 0), d)

    def almond(cx, cz, w, h, n=64):
        a = np.linspace(0, 2 * np.pi, n, endpoint=False)
        return np.stack([cx + w / 2 * np.cos(a), cz + h / 2 * np.sin(a) * (1 + 0.15 * np.cos(a))], 1)

    def chart(outline):
        return np.array([(theta_of(S, x, z), z) for x, z in outline])
    def radius(z):
        cy, r = _row_at(S, z)
        return float(r[int(np.argmin(np.abs(S.th)))])
    feats = []
    for name, cx, sd in (('eye_L', ex, 1.0), ('eye_R', -ex, -1.0)):
        j0, j1 = sorted((col(theta_of(S, cx - bw, 0.0)), col(theta_of(S, cx + bw, 0.0))))
        feats.append(dict(name=name, block=(j0, j1, row(bt), row(-bb)), outline_tz=chart(np.stack([cx + sd * eo[:, 0], eo[:, 1]], 1)),
                          rings=rings[0], theta_scale=radius(0.0), cap=caps))
    j0, j1 = col(theta_of(S, -mw, mz)), col(theta_of(S, mw, mz))
    mo = almond(0.0, mz, mouth_w, mouth_h) if mouth_outline is None else np.asarray(mouth_outline, float) + np.array([0.0, mz])
    feats.append(dict(name='mouth', block=(j0, j1, row(mz + mt), row(mz - mb)), outline_tz=chart(mo),
                      rings=rings[1], theta_scale=radius(mz), cap=caps))
    chart = {}

    def place_fn(t, z):
        if under is None:
            return place(S, t, z)
        part = np.zeros(len(np.atleast_1d(z)), int)
        P = under.place(t, z, part)
        for p, tc, zc, pt in zip(P, np.broadcast_to(np.asarray(t, float), np.shape(z)), np.asarray(z, float), part):
            chart[tuple(np.round(p, 7))] = (float(zc), int(pt), float(tc))
        return P
    Cg = hm.cylinder(nth, zs, dome, place_fn, dome_place, feats)
    if under is not None:
        Cg.F = np.array(orient_faces(Cg.V, Cg.F), np.int64)
    Cg.under = under
    Cg.jaw_edge = edge
    Cg.rim_row = under.side['rows'][0] if under is not None and under.side is not None else None
    got = [chart.get(tuple(np.round(p, 7)), (p[2], 0, np.nan)) for p in Cg.V]
    Cg.chart_z = np.array([g[0] for g in got])
    Cg.under_part = np.array([g[1] for g in got], int)          # (UnderJaw.place's parts: 1 the underside)
    Cg.chart_th = np.array([g[2] for g in got])
    # each vertex's way out, for checking the fit: from the head's axis at its height, or the dome's centre above it
    O = np.stack([np.zeros(len(Cg.V)), np.interp(-np.minimum(Cg.V[:, 2], z_top), -S.zs[okr], S.cy[okr]),
                  np.minimum(Cg.V[:, 2], z_top)], 1)
    Cg.origins = O
    return Cg, ctr
