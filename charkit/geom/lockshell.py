"""Hair locks as their own shells (option B, Michael 2026-09-30; tool/hairshell, docs/workstreams/hairshell.md): each lock
the drawing sections (charkit.hairsplit's locks, per view, with their roots, tips and layer ranks) built as a thick,
tapered tube of its own, the way anime 3D hair is modelled, instead of a region painted on the visual hull's one shell.

A lock is a template of a few parameters fitted to its drawn cells:
  centreline  a degree-5 Bezier in 3-d (six control points: a lock can hang, sweep and curl at its tip), root to tip,
              fitted by least squares so its projection runs down the drawn lock's centreline in every view the lock
              is matched in (both ways' distances, the root and the tip), with a weak pull to its depth on the hair's
              envelope (the hull: an initial guess and a measurement, never the surface) and its smoothness
  section     a lens `depth_ratio` as thick as it is wide; its broad side tangent to the head (the thickness along the
              radial direction out of the crown chart's centre) turned by one fitted twist about the centreline (a side
              lock shows its broad side to the front)
  width       per station, solved in closed form from the drawn widths of every matched view (each view sees the
              section's extent across the projected centreline), smoothed, to a point at the tip
  layer       the splitter's T-junction ranks: a lock behind its neighbours sits `inset` L deeper per rank
  root        carried root_in L on into the hair along its own direction, under the locks above it, and never within
              `gap` of the skin (the crown chart's skin field)
Views: a lock is fitted first in its primary view (the one its family's masks name it in: the front for the side
locks, the back for the hem's flicks), then its shell is projected into the other views and claims the drawn lock it
covers most (the splitter's own cross-view ids are weak: lock-level precision 0.40), and is fitted again with every
claimed view. Where the views disagree the fit is the least-squares compromise and each view's cost is reported.

Opt-in: hair.shape.pieces_opts.lock_shells (charkit.geom.hairpieces.build), e.g.
    {"families": ["side_locks"], "groups": [{"family": "lower_back", "view": "back", "phi": [100, 175]}]}
The default spec doesn't set it, so nothing changes there.
"""
import json, math, os

import numpy as np

DEFAULT = dict(families=('side_locks',), groups=(), primary={'side_locks': ('front', 'profile'),
                                                             'lower_back': ('back', 'front', 'profile')},
               share=0.5, min_px=150, bins=14, samples=40, depth_ratio=0.35, inset=0.010, root_in=0.05, gap=0.006,
               prior_depth=0.15, prior_smooth=1.0, prior_twist=0.5, assoc=0.35, assoc_cover=0.3, tip_w=0.12,
               w_max=2.5, n_ring=10, refit=True, views=('front', 'three_quarter', 'profile', 'back'), facing=0.2,
               assoc_L=0.1, assoc_overlap=0.5, twist_max=0.8, view_cost_max=4.0, frag_L2=0.008, frag_reach=4,
               widen_lw=1.0, contain=1.0, dedup=0.5, unit='locks', over=0.004,
               contain_family=True, view_depth=1.0, soft_width=True, diff_step=1e-3, shade='proxy', shade_lock=None,
               under=(), trim_other=False, trim_px=6.0, root_w_other=2.0, tip_w_other=2.0, primary_slack=None,
               join='sequential', over_ink=None, under_inset=0.0)
# (tool/hairshell2) shade: 'proxy' (the shells' normals from the default pieces' envelope: hairpieces.shade_normals) or
# 'union' (round 1: the envelope of every piece, shells included); shade_lock: lock_shading on the shells (None: the
# style's); under: families whose wedges stay under their shells; widen_lw: a number or {family: number}; trim_other,
# root_w_other, tip_w_other: a secondary view's drawn lock trimmed to the heights the shell spans, its root's end not
# pulled (another view's drawn lock is cut where its family's mask ends), its tip's; primary_slack: px the joint fit
# may cost the primary view (None: unbounded); join: 'sequential' (each other view tried alone, kept if the fit
# follows it) or 'joint' (round 1: all at once, every view the fit can't follow dropped); over_ink: a laid-over
# group's shells ink only their last over_ink of length (None: all of it)
VIEWS_AZ = None


# ------------------------------------------------------------------------------------------------ the splitter's locks

def load_split(path):
    """charkit.hairsplit's product (hairsplit.json and .npz beside it) -> dict(views {name: dict(img, az, ppl, col_axis,
    row_eye, box, locks {id: info})}, shell)."""
    J = json.load(open(path))
    Z = np.load(os.path.join(os.path.dirname(path), 'hairsplit.npz'))
    out = dict(views={}, meta=J)
    for n, v in J['views'].items():
        if n not in Z.files:
            continue
        out['views'][n] = dict(img=Z[n], cells=Z[n + '__cells'] if n + '__cells' in Z.files else None,
                               az=float(v['az']), ppl=float(v.get('ppl', 0) or 0),
                               col_axis=v.get('col_axis'), row_eye=v.get('row_eye'), box=v['box'],
                               locks={int(k): x for k, x in v['locks'].items()})
    return out


def lock_family(img, masks, view, families):
    """per lock of one view's image: its family by majority over the hair layers' masks (None where no mask names it)
    -> {lock: (family, share)}."""
    out = {}
    fm = {f: masks.get('%s__%s' % (view, f)) for f in families}
    fm = {f: m for f, m in fm.items() if m is not None and m.shape == img.shape}
    if not fm:
        return out
    for l in np.unique(img[img > 0]):
        m = img == l
        n = m.sum()
        best = max(((f, float((m & q).sum()) / n) for f, q in fm.items()), key=lambda x: x[1])
        out[int(l)] = best
    return out


# ------------------------------------------------------------------------------------------------ geometry helpers

def bernstein(Q, t):
    """a Bezier curve of degree len(Q) - 1 at parameters t -> (len(t), 3)."""
    from scipy.special import comb
    n = len(Q) - 1
    t = np.asarray(t, float)[:, None]
    B = np.stack([comb(n, k) * t[:, 0] ** k * (1 - t[:, 0]) ** (n - k) for k in range(n + 1)], 1)
    return B @ np.asarray(Q)


def bernstein_matrix(n, t):
    from scipy.special import comb
    t = np.asarray(t, float)
    return np.stack([comb(n, k) * t ** k * (1 - t) ** (n - k) for k in range(n + 1)], 1)


def frames(P, chart, twist=0.0):
    """per centreline point: tangent t, thickness axis a (out of the chart's centre, square to t, turned by twist rad
    about t) and broad axis b = t x a."""
    t = np.gradient(P, axis=0)
    t /= np.linalg.norm(t, axis=1, keepdims=True) + 1e-12
    r = P - chart.c
    a0 = r - t * np.einsum('ij,ij->i', r, t)[:, None]
    st = np.linalg.norm(a0, axis=1) / (np.linalg.norm(r, axis=1) + 1e-12)       # how well the radial defines it
    a0 /= np.linalg.norm(a0, axis=1, keepdims=True) + 1e-12
    # where the centreline runs along the radial (a root going in to the scalp) the radial frame is undefined: the
    # frame is carried along from its neighbour (parallel transport), from the tip end, blended in as the radial fades
    n = len(P)
    a = a0.copy()
    for k in range(n - 2, -1, -1):
        tr = a[k + 1] - t[k] * (a[k + 1] @ t[k])
        tr /= np.linalg.norm(tr) + 1e-12
        w = float(np.clip((st[k] - 0.25) / 0.5, 0.0, 1.0))
        v = w * a0[k] + (1 - w) * tr
        if v @ tr < 0:
            v = tr
        a[k] = v / (np.linalg.norm(v) + 1e-12)
    if n > 4:
        # no faster turn of the section than the centreline's own: the frame smoothed along it (a wide lens whose
        # frame turns between two stations crosses its own faces)
        from scipy.ndimage import gaussian_filter1d
        a = gaussian_filter1d(a, 2.0, axis=0, mode='nearest')
        a = a - t * np.einsum('ij,ij->i', a, t)[:, None]
        a /= np.linalg.norm(a, axis=1, keepdims=True) + 1e-12
    b = np.cross(t, a)
    if twist:
        c, s = math.cos(twist), math.sin(twist)
        a, b = c * a + s * b, c * b - s * a
    return t, a, b


def tube(P, W, Tk, chart, twist=0.0, n_ring=10):
    """a closed lens-section tube along P (root to tip): width W, thickness Tk per point. -> part dict (V, T, strand,
    vn_env, chain, outer, push)."""
    P = np.asarray(P, float)
    n = len(P)
    t, a, b = frames(P, chart, twist)
    ang = 2 * np.pi * np.arange(n_ring) / n_ring
    # a lens: the broad side flat-ish (|cos|^0.6 keeps the edges thin, the faces full)
    cb = np.sign(np.cos(ang)) * np.abs(np.cos(ang)) ** 0.8
    sa = np.sign(np.sin(ang)) * np.abs(np.sin(ang)) ** 0.6
    V = (P[:, None, :] + b[:, None, :] * (W[:, None, None] / 2) * cb[None, :, None] +
         a[:, None, :] * (Tk[:, None, None] / 2) * sa[None, :, None]).reshape(-1, 3)
    tip = len(V); root = tip + 1
    V = np.r_[V, [P[-1] + t[-1] * 1e-4], [P[0] - t[0] * 1e-4]]
    T = []
    for k in range(n - 1):
        for s in range(n_ring):
            a0, a1 = k * n_ring + s, k * n_ring + (s + 1) % n_ring
            T += [(a0, a1, a1 + n_ring), (a0, a1 + n_ring, a0 + n_ring)]
    for s in range(n_ring):
        T.append(((n - 1) * n_ring + s, (n - 1) * n_ring + (s + 1) % n_ring, tip))
        T.append((root, (s + 1) % n_ring, s))
    T = np.array(T, np.int64)
    cen = np.r_[np.repeat(P, n_ring, 0), [P[-1], P[0]]]
    tri = V[T]
    fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    if (np.einsum('ij,ij->i', fn, tri.mean(1) - cen[T].mean(1)) < 0).mean() > 0.5:
        T = T[:, [0, 2, 1]]
    vn = V - cen
    vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12
    strand = np.r_[np.repeat(t, n_ring, 0), [t[-1], t[0]]]
    return dict(V=V, T=T, strand=strand, vn_env=vn, chain=P[np.linspace(0, n - 1, min(n, 6)).astype(int)],
                outer=np.ones(len(V), bool), push=0.0)


def silhouette(V, T, view, az, hull_frame, shape):
    """a mesh's silhouette on a view's design grid (its triangles filled) -> bool image."""
    from skimage.draw import polygon
    from .hairpieces import view_px
    c, r = view_px(V, view, az, False, hull_frame)
    m = np.zeros(shape, bool)
    for tri in np.asarray(T):
        rr, cc = polygon(r[tri], c[tri], shape)
        m[rr, cc] = True
    return m


def envelope_points(F, view, az, hull_frame, cols, rows, L):
    """each pixel's ray (the view's camera: the viewer at e = (sin az, -cos az, 0)) cast onto the hair's envelope (the
    crown chart's R over its valid cells): the first point inside it from the viewer; a ray that misses it takes its
    point nearest the envelope. -> world points (n, 3)."""
    from charkit.bodyqa import WIN
    s_, tr = hull_frame
    ppl = view.ppl
    a = math.radians(az)
    ox = (view.grid_eye[0] - view.axis) / ppl
    org = (ox, (view.eye_y - view.grid_eye[1]) / ppl)
    u = np.asarray(cols, float) / ppl + org[0] - WIN['x']
    z = WIN['top'] + org[1] - np.asarray(rows, float) / ppl
    ex = np.array([math.sin(a), -math.cos(a), 0.0])
    ux = np.array([math.cos(a), math.sin(a), 0.0])
    ts = np.linspace(2.0, -2.0, 321)
    H = u[:, None, None] * ux + z[:, None, None] * np.array([0, 0, 1.0]) + ts[None, :, None] * ex
    Wd = H * s_ + np.asarray(tr, float)
    ch, G = F['chart'], F['grid']
    ph, th, r = ch.coords(Wd.reshape(-1, 3))
    R = G.sample(F['R'], ph, th)
    ok = np.isfinite(R) & (th < G.th[-1] + G.dth / 2)
    gap = np.where(ok, r - R, np.inf).reshape(len(u), -1)
    inside = gap <= 0
    first = np.where(inside.any(1), inside.argmax(1), np.argmin(np.abs(gap), 1))
    n = np.arange(len(u))
    out = Wd[n, first]
    # the crossing between the last sample outside and the first inside, interpolated on the gap: the point moves
    # continuously with the envelope (the first sample alone jumps a ray step when 1e-10 m of noise flips a sample)
    k = first
    prev = np.maximum(k - 1, 0)
    g0, g1 = gap[n, prev], gap[n, k]
    ok_ = inside.any(1) & (k > 0) & np.isfinite(g0) & np.isfinite(g1) & (g0 > g1)
    f = np.where(ok_, g0 / np.where(ok_, g0 - g1, 1.0), 1.0)
    return np.where(ok_[:, None], Wd[n, prev] + f[:, None] * (Wd[n, k] - Wd[n, prev]), out)


# ------------------------------------------------------------------------------------------------ the fit

class Lock:
    """one lock's fit: its views' drawn centrelines and widths, the curve, the twist, the widths."""

    def __init__(self, name, family, primary, F, views, hull_frame, L, o):
        self.name, self.family, self.primary = name, family, primary
        self.F, self.views, self.hull_frame, self.L, self.o = F, views, hull_frame, L, o
        self.drawn = {}           # view -> dict(D (k,2) cols rows, W (k,) px, mask, lock id, layer)
        self.Q = None
        self.twist = 0.0
        self.offset = 0.0         # m: how far under the envelope the lock's outer surface sits (its layer)
        self.cost = {}
        self.assoc = {}

    def add_view(self, vname, az, mask, root_rc, lock_id, layer=None):
        from scipy import ndimage
        from .hairpieces import strand_centreline
        base = np.zeros(mask.shape, bool)
        r, c = int(round(root_rc[0])), int(round(root_rc[1]))
        r = min(max(r, 0), mask.shape[0] - 1); c = min(max(c, 0), mask.shape[1] - 1)
        if not mask[r, c]:
            # the nearest lock pixel to the root
            rr, cc = np.nonzero(mask)
            j = int(np.argmin(np.hypot(rr - r, cc - c)))
            r, c = int(rr[j]), int(cc[j])
        base[max(0, r - 3):r + 4, max(0, c - 3):c + 4] = True
        got = strand_centreline(mask, base & ~mask | base, self.o['bins'])
        if got is None:
            return False
        D, W = got
        self.drawn[vname] = dict(az=az, D=D, W=W, mask=mask, lock=lock_id, layer=layer)
        return True

    def px(self, P, vname):
        from .hairpieces import view_px
        c, r = view_px(P, self.views[vname], self.drawn[vname]['az'], False, self.hull_frame)
        return np.c_[c, r]

    def init(self):
        """the start: the primary view's centreline cast onto the envelope, `offset` and half a thickness under it."""
        d = self.drawn[self.primary]
        v = self.views[self.primary]
        E = envelope_points(self.F, v, d['az'], self.hull_frame, d['D'][:, 0], d['D'][:, 1], self.L)
        s_ = self.hull_frame[0]
        Tk = self.o['depth_ratio'] * d['W'] / v.ppl * s_
        ch = self.F['chart']
        rad = E - ch.c
        rad /= np.linalg.norm(rad, axis=1, keepdims=True) + 1e-12
        P0 = E - rad * (self.offset + Tk / 2)[:, None]
        seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P0, axis=0), axis=1))]
        tt = seg / max(seg[-1], 1e-9)
        M = bernstein_matrix(5, tt)
        self.Q = np.linalg.lstsq(M, P0, rcond=None)[0]
        self.ts = np.linspace(0, 1, self.o['samples'])
        self.target_r = None

    def curve(self, Q=None):
        return bernstein(self.Q if Q is None else Q, self.ts)

    def drawn_width(self, pc, d):
        """the drawn width (px) at projected points pc: with soft_width, the drawn stations' widths weighted by a
        Gaussian of their distance (sigma: the stations' median spacing), so the fit's objective is smooth in the curve
        (the nearest station's width, a step at every change of station, made the fit end in a different place for
        input differences of 1e-10 m: two builds of one spec 1.3 cm apart); else the nearest station's."""
        dd = np.linalg.norm(pc[:, None, :] - d['D'][None], axis=2)
        if not self.o.get('soft_width', False) or len(d['D']) < 2:
            return d['W'][np.argmin(dd, 1)]
        sg = max(1.0, float(np.median(np.linalg.norm(np.diff(d['D'], axis=0), axis=1))))
        w = np.exp(-0.5 * ((dd - dd.min(1, keepdims=True)) / sg) ** 2)
        return (w * d['W'][None]).sum(1) / w.sum(1)

    def widths(self, P, twist):
        """per curve sample: the true width that best explains every view's drawn width (closed form), and per view the
        projected extents' coefficients."""
        from .hairpieces import _seg_dist
        t, a, b = frames(P, self.F['chart'], twist)
        s_ = self.hull_frame[0]
        num = np.zeros(len(P)); den = np.zeros(len(P))
        for vn, d in self.drawn.items():
            pc = self.px(P, vn)
            g = np.gradient(pc, axis=0)
            g /= np.linalg.norm(g, axis=1, keepdims=True) + 1e-12
            nrm = np.c_[-g[:, 1], g[:, 0]]
            pb = self.px(P + b * 1e-3, vn) - pc
            pa = self.px(P + a * 1e-3, vn) - pc
            # the section's extent across the projected centreline, per unit width (px per m of width)
            cvec = (np.abs(np.einsum('ij,ij->i', pb, nrm)) + self.o['depth_ratio'] * np.abs(np.einsum('ij,ij->i', pa, nrm))) / 1e-3
            wd = self.drawn_width(pc, d)
            num += cvec * wd; den += cvec ** 2
        Wt = num / np.maximum(den, 1e-12)
        return Wt

    def residuals(self, x, views=None):
        from .hairpieces import _seg_dist
        Q = x[:18].reshape(6, 3)
        twist = x[18]
        P = self.curve(Q)
        out = []
        for vn, d in self.drawn.items():
            if views and vn not in views:
                continue
            pc = self.px(P, vn)
            # the root's end only in the primary view: another view's drawn lock is cut where its family's mask ends
            # (a lock's root lies under the locks above it, drawn at another height in each view); the tip in all
            rw = 2.0 if vn == self.primary else self.o.get('root_w_other', 2.0)
            tw = 2.0 if vn == self.primary else self.o.get('tip_w_other', 2.0)
            if vn != self.primary and d.get('span') is not None:
                # (a secondary view over the heights both draw: its curve part there against its drawn part)
                lo_, hi_ = d['span']
                m_ = self.o.get('trim_px', 6.0)
                wr = np.clip((pc[:, 1] - lo_) / m_, 0, 1) * np.clip((hi_ - pc[:, 1]) / m_, 0, 1)
                out += [_seg_dist(d['D'], pc), wr * _seg_dist(pc, d['D']), rw * (pc[0] - d['D'][0]), tw * (pc[-1] - d['D'][-1])]
            else:
                out += [_seg_dist(d['D'], pc), _seg_dist(pc, d['D']), rw * (pc[0] - d['D'][0]), tw * (pc[-1] - d['D'][-1])]
        # depth: the curve's radius about the chart's centre near its start's (the envelope less its offset)
        ch, G = self.F['chart'], self.F['grid']
        ph, th, r = ch.coords(P)
        ppl = self.views[self.primary].ppl
        s_ = self.hull_frame[0]
        tpx = ppl / s_                                   # px per metre
        if self.target_r is not None:
            out.append(self.o['prior_depth'] * (r - self.target_r(ph, th)) * tpx)
        # each view that draws the lock sees it on top there: its centreline right under the envelope's first surface
        # along that view's ray (offset and half a thickness under it)
        from scipy.ndimage import map_coordinates
        for vn, d in self.drawn.items():
            Dv = getattr(self, 'env_depth', {}).get(vn)
            if Dv is None:
                continue
            from .hairpieces import view_px
            c, rw = view_px(P, self.views[vn], d['az'], False, self.hull_frame)
            de = map_coordinates(Dv, [rw / 2.0, c / 2.0], order=1, mode='nearest', cval=np.nan)
            a_ = math.radians(d['az'])
            dep = P @ np.array([math.sin(a_), -math.cos(a_), 0.0])
            half = 0.5 * self.o['depth_ratio'] * float(np.median(d['W'])) / self.views[vn].ppl * s_
            res = dep - (de - self.offset - half)
            out.append(self.o['view_depth'] * np.where(np.isfinite(res), res, 0.0) * tpx)
        # the skin: never within gap of it
        Sk = G.sample(self.F['S'], ph, th)
        clear = np.where(np.isfinite(Sk), np.maximum(0.0, Sk + self.o['gap'] * self.L - r), 0.0)
        out.append(10.0 * clear * tpx)
        d2 = Q[2:] - 2 * Q[1:-1] + Q[:-2]
        out.append(self.o['prior_smooth'] * d2.ravel() * tpx)
        # the widths: each view's drawn width against the section's projected extent
        Wt = self.widths(P, twist)
        for vn, d in self.drawn.items():
            if views and vn not in views:
                continue
            pc = self.px(P, vn)
            g = np.gradient(pc, axis=0)
            g /= np.linalg.norm(g, axis=1, keepdims=True) + 1e-12
            nrm = np.c_[-g[:, 1], g[:, 0]]
            t, a, b = frames(P, ch, twist)
            pb = self.px(P + b * 1e-3, vn) - pc
            pa = self.px(P + a * 1e-3, vn) - pc
            cvec = (np.abs(np.einsum('ij,ij->i', pb, nrm)) + self.o['depth_ratio'] * np.abs(np.einsum('ij,ij->i', pa, nrm))) / 1e-3
            wd = self.drawn_width(pc, d)
            out.append(0.5 * (cvec * Wt - wd))
        out.append(np.array([self.o['prior_twist'] * twist * 10.0]))
        # every view the lock faces: its centreline at least half a drawn width inside the drawn hair (the multi-view
        # constraint the visual hull carves with; a lock fitted in one view otherwise wanders out of the others)
        from scipy.ndimage import map_coordinates
        for vn, (az, sd, hw) in getattr(self, 'contain', {}).items():
            from .hairpieces import view_px
            c, r = view_px(P, self.views[vn], az, False, self.hull_frame)
            d = map_coordinates(sd, [r, c], order=1, mode='nearest')
            out.append(self.o['contain'] * np.maximum(0.0, d + 0.5 * hw))
        return np.concatenate([np.ravel(q) for q in out])

    def fit(self):
        from scipy.optimize import least_squares
        ch, G = self.F['chart'], self.F['grid']
        P0 = self.curve()
        ph0, th0, r0 = ch.coords(P0)
        R0 = G.sample(self.F['R'], ph0, th0)
        dr = float(np.median(R0 - r0))                 # how far under the envelope the start lies
        self.target_r = lambda ph, th: G.sample(self.F['R'], ph, th) - dr
        tw = self.o['twist_max']
        x0 = np.r_[self.Q.ravel(), np.clip(self.twist, -0.99 * tw, 0.99 * tw)]
        scale = np.r_[np.full(18, 0.01 * self.L), 0.3]
        # diff_step: the Jacobian's finite-difference step (relative; under 1 m, in m: 1e-3 is a millimetre, about a
        # pixel of the drawing). scipy's default (1.5e-8) probes the objective far below its pixel-level corners, so
        # the fit's end moved with input noise
        sol = least_squares(self.residuals, x0, x_scale=scale, max_nfev=300, diff_step=self.o.get('diff_step'),
                            bounds=(np.r_[np.full(18, -np.inf), -tw], np.r_[np.full(18, np.inf), tw]))
        self.Q = sol.x[:18].reshape(6, 3)
        self.twist = float(sol.x[18])
        P = self.curve()
        for vn, d in self.drawn.items():
            from .hairpieces import _seg_dist
            pc = self.px(P, vn)
            self.cost[vn] = round(float(np.mean(_seg_dist(d['D'], pc))), 2)
        return sol

    def shell(self):
        """the lock's tube (a hairpieces part): stations evenly spaced along it, its root carried on into the hair."""
        from scipy.ndimage import gaussian_filter1d
        n = self.o['samples']
        # even arc length (the Bezier's own parameter crowds its stations where it turns: a fold's start)
        Pd = bernstein(self.Q, np.linspace(0, 1, 8 * n))
        sd = np.r_[0, np.cumsum(np.linalg.norm(np.diff(Pd, axis=0), axis=1))]
        su = np.linspace(0, sd[-1], n)
        P = np.stack([np.interp(su, sd, Pd[:, j]) for j in range(3)], 1)
        Wt = self.widths(P, self.twist)
        s_ = self.hull_frame[0]
        ppl = self.views[self.primary].ppl
        Wd = np.max([d['W'].max() for d in self.drawn.values()]) / ppl * s_
        W = np.clip(gaussian_filter1d(Wt, 1.5, mode='nearest'), 0.2 * Wd / self.o['w_max'], self.o['w_max'] * Wd)
        u = np.linspace(0, 1, len(P))
        W = W * np.clip((1 - u) / 0.2, self.o['tip_w'], 1.0) ** 0.6
        wl = self.o['widen_lw']
        wl = float(wl.get(self.family, 1.0)) if isinstance(wl, dict) else float(wl)
        W = W + 2 * wl * self.o.get('lw_px', 2.0) / ppl * s_ * np.clip((1 - u) / 0.2, 0, 1)
        # the root carried on into the hair: along the lock's own direction root_in L, diving toward the scalp as it
        # goes (its radius blended to the skin's clearance where there is skin under it), narrowing to 0.6 of its width
        ch, G = self.F['chart'], self.F['grid']
        d0 = P[0] - P[1]
        d0 /= np.linalg.norm(d0) + 1e-12
        k = 6
        f = np.linspace(1, 1.0 / k, k)
        E = P[0] + d0 * (self.o['root_in'] * self.L) * f[:, None]
        ph, th, r = ch.coords(E)
        Sk = G.sample(self.F['S'], ph, th)
        r0 = float(ch.coords(P[:1])[2][0])
        floor = np.where(np.isfinite(Sk), Sk + self.o['gap'] * self.L + self.o['depth_ratio'] * W[0] / 2, r0)
        dive = np.clip(r0 - floor, 0.0, 0.6 * self.o['root_in'] * self.L)          # at most a 31 degree dive
        rr = r - dive * (3 * f ** 2 - 2 * f ** 3)                                      # smoothstep: no kink
        E = ch.point(ph, th, rr)
        line = np.r_[E, P]
        Wl = np.r_[W[0] * (1 - 0.4 * f), W]
        # no fold where the lock bends across its broad side: half its width within 0.8 of the bend's radius
        t, a, b = frames(line, ch, self.twist)
        ds = np.linalg.norm(np.gradient(line, axis=0), axis=1) + 1e-12
        kb = np.abs(np.einsum('ij,ij->i', np.gradient(t, axis=0) / ds[:, None], b))
        ka = np.abs(np.einsum('ij,ij->i', np.gradient(t, axis=0) / ds[:, None], a))
        from scipy.ndimage import maximum_filter1d
        Wl = np.minimum(Wl, 1.6 / np.maximum(maximum_filter1d(kb, 5, mode='nearest'), 1e-9))
        Tl = np.minimum(self.o['depth_ratio'] * Wl, 1.6 / np.maximum(maximum_filter1d(ka, 5, mode='nearest'), 1e-9))
        part = tube(line, Wl, Tl, ch, self.twist, self.o['n_ring'])
        keep = self.o.get('over_ink')
        if getattr(self, 'over', False) and keep is not None:
            # (tool/hairshell2) a lock laid over its family's mass (the back's hem flicks) draws its ink only over the
            # last `over_ink` of its length, eased in over 0.1 of it, as the design draws the hem's flicks: lobes of
            # the mass with a short tick at each notch, no lines down the back (hair_back_lines)
            sl = np.r_[0, np.cumsum(np.linalg.norm(np.diff(line, axis=0), axis=1))]
            sl = sl / max(sl[-1], 1e-12)
            x = np.clip((sl - (1.0 - float(keep) - 0.1)) / 0.1, 0, 1)
            w = x * x * (3 - 2 * x)
            part['outline_w'] = np.r_[np.repeat(w, self.o['n_ring']), [1.0, 0.0]]
        from .hairpieces import folds
        nf = folds(part['V'], part['T'], part['outer'], part['vn_env'])
        part['fit'] = dict(views=sorted(self.drawn), cost_px=self.cost, twist_deg=round(math.degrees(self.twist), 1),
                           width_L=round(float(W.max()) / self.L, 4), length_L=round(float(
                               np.linalg.norm(np.diff(P, axis=0), axis=1).sum()) / self.L, 4),
                           locks={vn: int(d['lock']) for vn, d in self.drawn.items()}, folds=int(nf))
        return part


def build_shells(F, masks, views, hull_frame, L, ls, log=print):
    """the lock shells the spec asks for (pieces_opts.lock_shells: see the module) -> dict(parts {family or group: [part
    dicts]}, groups [{family, view, phi}], report)."""
    o = dict(DEFAULT, **{k: v for k, v in ls.items() if k not in ('split',)})
    S = load_split(ls['split'])
    fams = list(o['families']) + [g['family'] for g in o['groups']]
    allfams = ('bangs', 'side_locks', 'upper_back', 'lower_back', 'ahoge', 'flyaways')
    fam_of = {vn: lock_family(S['views'][vn]['img'], masks, vn, allfams) for vn in S['views']}
    claimed = {vn: set() for vn in S['views']}
    out, report = {}, dict(locks=[])

    def full_rc(vn, rc):
        b = S['views'][vn]['box']
        return (rc[0] + b[0], rc[1] + b[2])

    def ranks(vn):
        lk = S['views'][vn]['locks']
        r = [x.get('layer') or 0.0 for x in lk.values()]
        return (min(r), max(r)) if r else (0.0, 0.0)

    def targets(vn, fam, unit='locks'):
        """the view's drawn targets for a family: each lock's part in the family's mask (a lock the splitter ran on
        across two families gives each its part), components of min_px or more; a view without family masks (the
        three-quarter): its locks whole."""
        from scipy import ndimage
        V = S['views'][vn]
        fm = masks.get('%s__%s' % (vn, fam))
        parts_ = []
        if unit == 'cells' and V.get('cells') is not None:
            # the splitter's cells (closed by the strokes and the hem's tone necks) in place of its locks: a hem
            # flick is a cell its stripe lock carries down from the crown (the canonical rule's sub-cut)
            for cid in np.unique(V['cells'][V['cells'] > 0]):
                m = V['cells'] == cid
                if fm is not None and fm.shape == m.shape:
                    m = m & fm
                elif any(masks.get('%s__%s' % (vn, f_)) is not None for f_ in allfams):
                    continue
                if not m.any():
                    continue
                lid = int(np.bincount(V['img'][m]).argmax())
                if lid not in V['locks']:
                    continue
                lab, n = ndimage.label(m)
                for j in range(1, n + 1):
                    parts_.append([lid, int(cid) * 100 + j, lab == j])
        else:
          for lid, x in V['locks'].items():
            m = V['img'] == lid
            if fm is not None and fm.shape == m.shape:
                m = m & fm
            elif any(masks.get('%s__%s' % (vn, f_)) is not None for f_ in allfams):
                continue
            lab, n = ndimage.label(m)
            for j in range(1, n + 1):
                parts_.append([int(lid), j, lab == j])
        # fragments (a lock's sliver in the family, a splitter cell cut off) join the neighbour they touch most across
        # the ink between them, the smallest first: an animator's lock, not the splitter's every piece
        frag = o['frag_L2'] * (V['ppl'] or 212.5) ** 2
        r_ = int(round(o['frag_reach']))
        while True:
            sizes = [q[2].sum() for q in parts_]
            small = [i for i in np.argsort(sizes) if sizes[i] < frag]
            done = True
            for i in small:
                g = ndimage.binary_dilation(parts_[i][2], iterations=r_)
                best = max(((int((g & q[2]).sum()), k) for k, q in enumerate(parts_) if k != i), default=(0, None))
                if best[0] > 0:
                    k = best[1]
                    if sizes[k] >= sizes[i]:
                        parts_[k][2] = parts_[k][2] | parts_[i][2]
                    else:
                        parts_[k] = [parts_[i][0], parts_[i][1], parts_[k][2] | parts_[i][2]]
                    parts_.pop(i)
                    done = False
                    break
            if done:
                break
        out_ = []
        for lid, j, mj in parts_:
            x = V['locks'][lid]
            if mj.sum() < o['min_px']:
                continue
            if True:
                rr, cc = np.nonzero(mj)
                r0, c0 = full_rc(vn, x['root_rc'])
                q = int(np.argmin(np.hypot(rr - r0, cc - c0)))
                base = np.zeros(mj.shape, bool)
                base[max(0, rr[q] - 3):rr[q] + 4, max(0, cc[q] - 3):cc[q] + 4] = True
                from .hairpieces import strand_centreline
                cl = strand_centreline(mj, base, o['bins'])
                out_.append(dict(id=(int(lid), j), lock=int(lid), mask=mj, root=(float(rr[q]), float(cc[q])), info=x,
                                 area=int(mj.sum()), D=None if cl is None else cl[0]))
        return sorted(out_, key=lambda t_: -t_['area'])

    # each view's drawn hair as a signed distance (px: + outside, - inside): the shells' containment
    from scipy import ndimage as _nd
    sdist = {}
    for vn, W_ in S['views'].items():
        hm = W_['img'] > 0
        for k_, m_ in masks.items():
            if k_.startswith(vn + '__') and m_.shape == hm.shape:
                hm = hm | m_
        sdist[vn] = (_nd.distance_transform_edt(~hm) - _nd.distance_transform_edt(hm)).astype(np.float32)

    def facing(P, az):
        rad = (P - F['chart'].c)[:, :2].mean(0)
        rad /= np.linalg.norm(rad) + 1e-12
        a_ = math.radians(az)
        return rad @ np.array([math.sin(a_), -math.cos(a_)]) >= o['facing']

    fdist = {}

    def fam_dist(vn, fam):
        """the family's drawn region (dilated a few px) as a signed distance, where the view has the family's mask (a
        side lock that shows must show where side locks are drawn, not over the lower back); else the hair's."""
        k_ = (vn, fam)
        if k_ not in fdist:
            fm = masks.get('%s__%s' % (vn, fam))
            if fm is None or fm.shape != S['views'][vn]['img'].shape or not o['contain_family']:
                fdist[k_] = sdist[vn]
            else:
                fm = _nd.binary_dilation(fm, iterations=3)
                fdist[k_] = (_nd.distance_transform_edt(~fm) - _nd.distance_transform_edt(fm)).astype(np.float32)
        return fdist[k_]

    edepth = {}

    def env_depth(vn):
        """the envelope's first surface along each ray of a view (every 2nd pixel of its drawn hair; its depth toward
        the viewer, world m), nan off the hair."""
        if vn not in edepth:
            W_ = S['views'][vn]
            sd = sdist[vn][::2, ::2]
            rr, cc = np.nonzero(sd < 3)
            D = np.full(sd.shape, np.nan, np.float32)
            a_ = math.radians(W_['az'])
            e = np.array([math.sin(a_), -math.cos(a_), 0.0])
            for i in range(0, len(rr), 2000):
                Pw = envelope_points(F, views[vn], W_['az'], hull_frame, 2 * cc[i:i + 2000], 2 * rr[i:i + 2000], L)
                D[rr[i:i + 2000], cc[i:i + 2000]] = Pw @ e
            # off the drawn hair: the nearest ray's depth (a NaN there read 0 in the fit: a step the curve's samples
            # crossed at the hair's edge)
            bad = ~np.isfinite(D)
            if bad.any() and (~bad).any():
                _, (ir, ic) = _nd.distance_transform_edt(bad, return_indices=True)
                D = D[ir, ic]
            edepth[vn] = D
        return edepth[vn]

    def set_contain(lk):
        if o['view_depth']:
            lk.env_depth = {vn: env_depth(vn) for vn in lk.drawn}
        P_ = lk.curve()
        hw = float(np.median(lk.drawn[lk.primary]['W'])) / 2
        lk.contain = {vn: (W_['az'], fam_dist(vn, lk.family), hw) for vn, W_ in S['views'].items()
                      if vn in views and facing(P_, W_['az'])}

    jobs = [(f, None) for f in o['families']] + [(g['family'], g) for g in o['groups']]
    for fam, grp in jobs:
        key = fam if grp is None else grp.get('name', '%s_%s' % (fam, grp.get('view', '')))
        parts = []
        prim = [grp['view']] if grp else list(o['primary'].get(fam, ('front',)))
        unit = (grp or {}).get('unit', o['unit'].get(fam, 'locks') if isinstance(o['unit'], dict) else o['unit'])
        tg = {vn: targets(vn, fam, unit) for vn in S['views'] if vn in views}
        lks = []
        for pv in prim:
            if pv not in S['views'] or pv not in views:
                continue
            V = S['views'][pv]
            lo, hi = ranks(pv)
            for T_ in tg[pv]:
                x, lid = T_['info'], T_['lock']
                if T_['id'] in claimed[pv]:
                    continue
                if grp and grp.get('phi'):
                    p_ = x.get('tip_phi')
                    if p_ is None or not (grp['phi'][0] <= p_ <= grp['phi'][1]):
                        continue
                lk = Lock('%s:%s%d.%d' % (key, pv[0], lid, T_['id'][1]), fam, pv, F, views, hull_frame, L, o)
                lay = x.get('layer') or 0.0
                lk.offset = o['inset'] * L * ((hi - lay) / max(1e-6, hi - lo) if hi > lo else 0.0)
                if grp and not grp.get('replace', True):
                    lk.offset = -o['over'] * L         # laid over the family's own pieces, not in place of them
                    lk.over = True
                elif not grp and fam in (o.get('under') or ()):
                    # (tool/hairshell2) the family's own pieces stay under its shells, the hull's mass as the base an
                    # anime build lays its locks over: every shell over it, the front-most layer furthest out
                    lk.offset = -o['over'] * L * (1.0 + ((lay - lo) / (hi - lo) if hi > lo else 0.0))
                if not lk.add_view(pv, V['az'], T_['mask'], T_['root'], lid, lay):
                    continue
                claimed[pv].add(T_['id'])
                lk.init()
                if pv != prim[0] and lks:
                    # a later primary view: a target an earlier lock's shell already covers is that lock seen again
                    # (the association missed it), not a new lock: it joins that lock if the joint fit follows both
                    best = None
                    for L2 in lks:
                        if pv in L2.drawn or not facing(L2.curve(), V['az']):
                            continue
                        p2 = L2.shell()
                        sil = silhouette(p2['V'], p2['T'], views[pv], V['az'], hull_frame, T_['mask'].shape)
                        cov = float((sil & T_['mask']).sum()) / T_['mask'].sum()
                        if cov >= o['dedup'] and (best is None or cov > best[0]):
                            best = (cov, L2)
                    if best is not None:
                        L2 = best[1]
                        keep = (L2.Q.copy(), L2.twist, dict(L2.cost))
                        L2.drawn[pv] = lk.drawn[pv]
                        set_contain(L2)
                        L2.fit()
                        if L2.cost.get(pv, 1e9) > o['view_cost_max'] or any(
                                c > o['view_cost_max'] for vn, c in L2.cost.items() if vn != L2.primary and vn != pv):
                            L2.drawn.pop(pv)
                            L2.Q, L2.twist, L2.cost = keep
                        report.setdefault('dedup', []).append(dict(target='%s:%s' % (pv, T_['id']), into=L2.name,
                                                                    cover=round(best[0], 3),
                                                                    joined=pv in L2.drawn))
                        continue
                set_contain(lk)
                lk.fit()
                # the other views: the drawn lock this shell covers most claims it
                if o['refit']:
                    part = lk.shell()
                    Pc = lk.curve()
                    rad = (Pc - F['chart'].c)[:, :2].mean(0)
                    rad /= np.linalg.norm(rad) + 1e-12
                    for vn in o['views']:
                        if vn == pv or vn not in S['views'] or vn not in views:
                            continue
                        W_ = S['views'][vn]
                        a_ = math.radians(W_['az'])
                        fc_ = float(rad @ np.array([math.sin(a_), -math.cos(a_)]))
                        if fc_ < o['facing']:
                            lk.assoc[vn] = dict(status='faces away', facing=round(fc_, 2))
                            continue                   # the lock faces away from this view: hidden behind the mass
                        # the drawn lock in this view whose centreline runs nearest the shell's projected one over
                        # the heights both span (the depth is the envelope's guess until this view joins the fit)
                        from .hairpieces import view_px, _seg_dist
                        cc_, rr_ = view_px(Pc, views[vn], W_['az'], False, hull_frame)
                        Pp = np.c_[cc_, rr_]
                        tol = o['assoc_L'] * views[vn].ppl
                        best = None
                        near_any = None
                        for T2 in tg[vn]:
                            if T2['D'] is None:
                                continue
                            _cl = T2['id'] in claimed[vn]
                            D2 = T2['D']
                            lo_, hi_ = max(Pp[:, 1].min(), D2[:, 1].min()), min(Pp[:, 1].max(), D2[:, 1].max())
                            span = min(np.ptp(Pp[:, 1]), np.ptp(D2[:, 1])) + 1e-9
                            if hi_ - lo_ < o['assoc_overlap'] * span:
                                continue
                            sel = (D2[:, 1] >= lo_) & (D2[:, 1] <= hi_)
                            if sel.sum() < 2:
                                continue
                            dist = float(np.mean(_seg_dist(D2[sel], Pp)))
                            if near_any is None or dist < near_any[0]:
                                near_any = (dist, T2['id'], _cl)
                            if _cl:
                                continue
                            if dist <= tol and (best is None or dist < best[0]):
                                best = (dist, T2)
                        if best is None:
                            lk.assoc[vn] = dict(status='no candidate', nearest=None if near_any is None else
                                                [round(near_any[0], 1), list(near_any[1]), near_any[2]], tol=round(tol, 1))
                            continue
                        T2 = best[1]
                        lk.assoc[vn] = dict(status='joined', dist=round(best[0], 1), target=list(T2['id']))
                        if lk.add_view(vn, W_['az'], T2['mask'], T2['root'], T2['lock'], T2['info'].get('layer')):
                            claimed[vn].add(T2['id'])
                            if o.get('trim_other'):
                                # the drawn part over the heights the shell spans (rows), a few px either side
                                d_ = lk.drawn[vn]
                                m_ = o.get('trim_px', 6.0)
                                lo2, hi2 = Pp[:, 1].min() - m_, Pp[:, 1].max() + m_
                                keep = (d_['D'][:, 1] >= lo2) & (d_['D'][:, 1] <= hi2)
                                if keep.sum() >= 3:
                                    d_['D'], d_['W'] = d_['D'][keep], d_['W'][keep]
                                d_['span'] = (d_['D'][:, 1].min() - m_, d_['D'][:, 1].max() + m_)
                        else:
                            lk.assoc[vn]['status'] = 'no centreline'
                    if len(lk.drawn) > 1 and o.get('join', 'sequential') == 'sequential':
                        # each other view on its own, the nearest first, kept when the fit follows it (a view the
                        # fit can't follow no longer takes the others out with it)
                        others = sorted((vn for vn in lk.drawn if vn != pv),
                                        key=lambda v_: lk.assoc.get(v_, {}).get('dist', 1e9))
                        pend = {vn: lk.drawn.pop(vn) for vn in others}
                        for vn in others:
                            keep = (lk.Q.copy(), lk.twist, dict(lk.cost))
                            solo = lk.cost.get(pv, 0.0)
                            lk.drawn[vn] = pend[vn]
                            set_contain(lk)
                            lk.fit()
                            ok = all(c <= o['view_cost_max'] for v_, c in lk.cost.items() if v_ != pv) and (
                                o.get('primary_slack') is None or lk.cost.get(pv, 0.0) <= solo + o['primary_slack'])
                            if not ok:
                                lk.assoc.setdefault(vn, {}).update(status='dropped', cost=lk.cost.get(vn),
                                                                   primary_cost=lk.cost.get(pv))
                                d = lk.drawn.pop(vn)
                                claimed[vn] = {q for q in claimed[vn] if q[0] != d['lock'] or q not in
                                               [T2['id'] for T2 in tg[vn] if T2['mask'] is d['mask']]}
                                lk.Q, lk.twist, lk.cost = keep
                                set_contain(lk)
                    elif len(lk.drawn) > 1:
                        solo = lk.cost.get(pv, 0.0)
                        set_contain(lk)
                        lk.fit()
                        # a view the joint fit can't follow (its drawn lock wasn't this one): out, fitted again; and
                        # with primary_slack, the joint fit may cost the primary view at most that many px more
                        bad = [vn for vn, c in lk.cost.items() if vn != pv and c > o['view_cost_max']]
                        if not bad and o.get('primary_slack') is not None and \
                                lk.cost.get(pv, 0.0) > solo + o['primary_slack']:
                            bad = [max((vn for vn in lk.cost if vn != pv), key=lambda v_: lk.cost[v_])]
                        if bad:
                            for vn in bad:
                                lk.assoc.setdefault(vn, {}).update(status='dropped', cost=lk.cost.get(vn),
                                                                   primary_cost=lk.cost.get(pv))
                                d = lk.drawn.pop(vn)
                                claimed[vn] = {q for q in claimed[vn] if q[0] != d['lock'] or q not in
                                               [T2['id'] for T2 in tg[vn] if T2['mask'] is d['mask']]}
                                lk.cost.pop(vn, None)
                            lk.init()
                            set_contain(lk)
                            lk.fit()
                lks.append(lk)
        for lk in lks:
            if True:
                part = lk.shell()
                # each view's IoU of the shell's silhouette with its drawn lock
                ious = {}
                for vn, d in lk.drawn.items():
                    sil = silhouette(part['V'], part['T'], views[vn], d['az'], hull_frame, d['mask'].shape)
                    ious[vn] = round(float((sil & d['mask']).sum() / max(1, (sil | d['mask']).sum())), 3)
                part['fit']['iou'] = ious
                part['fit']['name'] = lk.name
                part['fit']['assoc'] = lk.assoc         # per other view: faces away, no candidate, joined, dropped
                part['_drawn'] = {vn: d['mask'] for vn, d in lk.drawn.items()}
                part['fit']['side'] = 'L' if (part['V'][:, 0].mean() - F['chart'].c[0]) > 0 else 'R'
                parts.append(part)
                report['locks'].append(part['fit'])
                if log:
                    log('lock shell %s: views %s, cost px %s, IoU %s, twist %.0f deg, width %.3f L' % (
                        lk.name, sorted(lk.drawn), lk.cost, ious, math.degrees(lk.twist), part['fit']['width_L']))
        out[key] = parts
    report['fitted_2plus'] = sum(1 for x in report['locks'] if len(x.get('views') or ()) > 1)
    return dict(parts=out, report=report, opts={k: v for k, v in o.items() if k != 'split'})


# ------------------------------------------------------------------------------------------------ measuring a fit

def _rebase(x):
    """a spec's absolute paths from another machine's copy (a box build's /srv/work/...) pointed into this tree."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if isinstance(x, dict):
        return {k: _rebase(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_rebase(v) for v in x]
    if isinstance(x, str) and x.startswith('/') and not os.path.exists(x) and '/charkit/' in x:
        q = os.path.join(root, 'charkit', x.split('/charkit/', 1)[1])
        return q if os.path.exists(q) else x
    return x


def context(build, cache=None, log=print):
    """what the hair pieces step has when it shapes the pieces (charkit.cli.pieces_hair's run on a build's own cut spec,
    geom/pieces.spec.json): the case, the views, the hair layers, the hull frame and the crown chart's fields (hairpieces
    .build with fields_only) -> dict. Pickled to `cache` when given (the fields take about a minute)."""
    import pickle
    if cache and os.path.exists(cache):
        return pickle.load(open(cache, 'rb'))
    from PIL import Image
    from charkit import manifest, styles
    from . import hairpieces as hp, hull, io as gio, parts
    cut = os.path.join(build, 'geom', 'pieces.spec.json')
    spec = _rebase(json.load(open(cut)))
    cut = os.path.join(build, 'geom', 'pieces.spec.local.json')
    json.dump(spec, open(cut, 'w'), indent=1)
    C = parts.Case.load(cut, fit=False)
    glb = C.align['glb']
    side = json.load(open(glb + '.json'))
    Vh = gio.load(glb)
    lab = np.load(os.path.join(os.path.dirname(glb), side['labels']))
    pcs = np.load(os.path.join(os.path.dirname(glb), side['pieces']))
    M = manifest.load(spec['ref']['manifest'])
    rgb = np.asarray(Image.open(manifest._p(M['references']['body_turnaround']['path'])).convert('RGB')).astype(float) / 255
    views, info = hull.views_from_sheet(rgb, (spec.get('eyes') or {}).get('x', 0.168), -1)
    Z = np.load(manifest.produced(spec, 'hair_layers'))
    masks = {k: Z[k] for k in Z.files}
    fam, _ = hp.label_hull(np.asarray(Vh.V), np.asarray(Vh.F), lab, pcs, side['piece_names'], views, masks, info['ppl'])
    style = styles.load(spec.get('style', 'anime'))['hair_pieces']
    popts = dict((spec['hair']['shape'].get('pieces_opts') or {}), fields_only=True)
    popts.pop('lock_shells', None)
    hf = (C.align['scale'], np.asarray(C.align['translate']))
    R = hp.build(C, fam, masks, style, views=views, hull_frame=hf, opts=popts)
    # the scene the shells show among (the pictures' z-buffer): our skin and the build's other hair pieces
    from .io import load_npz
    occ = [(np.asarray(C.A['verts'], float), hp._tris(C.A['faces']))]
    pdir = os.path.join(build, 'geom', 'hair_pieces')
    for pc in json.load(open(os.path.join(pdir, 'pieces.json')))['pieces']:
        if pc['family'] != 'side_locks':
            m = load_npz(os.path.join(pdir, pc['file']))
            occ.append((np.asarray(m.V, float), np.asarray(m.F, np.int64)))
    ctx = dict(F=R['fields'], masks=masks, views=views, hull_frame=hf, L=C.L, spec=spec,
               split=manifest.produced(spec, 'hair_split'), occluders=occ)
    if cache:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        pickle.dump(ctx, open(cache, 'wb'))
    return ctx


def visible(parts, ctx, vn, az, shape):
    """the shells z-buffered among the scene's occluders (our skin, the other hair pieces) on a view's design grid
    -> label image (k + 1: parts[k] shows there; 0 an occluder; -1 nothing)."""
    from .hairpieces import view_window
    from .raster import window_zbuffer
    origin, Lw, pix, win = view_window(ctx['views'][vn], az, False, ctx['hull_frame'])
    meshes = [(V, T, 0) for V, T in ctx.get('occluders', ())]
    meshes += [(p['V'], p['T'], k + 1) for k, p in enumerate(parts)]
    _, lab = window_zbuffer(meshes, az, origin, Lw, pix, win)
    if lab.shape != shape:
        out = np.full(shape, -1, lab.dtype)
        h, w = min(shape[0], lab.shape[0]), min(shape[1], lab.shape[1])
        out[:h, :w] = lab[:h, :w]
        lab = out
    return lab


def picture(res, ctx, path, k=2, pad=0.08):
    """per view, the hair cropped: the drawing dimmed, each fitted lock's drawn cells outlined in its colour and its
    shell's silhouette filled in it, the fit's IoU written by it; the views side by side -> path."""
    from PIL import Image, ImageDraw
    from scipy import ndimage
    S = load_split(ctx['split'])
    rng = np.random.RandomState(7)
    parts = [p for ps in res['parts'].values() for p in ps]
    cols = [tuple(int(x) for x in rng.randint(40, 230, 3)) for _ in parts]
    tiles = []
    for vn in ('front', 'three_quarter', 'profile', 'back'):
        if vn not in S['views'] or vn not in ctx['views']:
            continue
        W_ = S['views'][vn]
        img = W_['img']
        hair = img > 0
        ys, xs = np.nonzero(hair)
        m = int(pad * W_['ppl'] if W_['ppl'] else 15)
        r0, r1, c0, c1 = max(0, ys.min() - m), ys.max() + m, max(0, xs.min() - m), xs.max() + m
        base = np.full(img.shape + (3,), 245, np.uint8)
        base[hair] = 200
        out = base.astype(float)
        lab = visible(parts, ctx, vn, W_['az'], img.shape)
        for k_, (p, col) in enumerate(zip(parts, cols)):
            sil = lab == k_ + 1
            out[sil] = 0.45 * out[sil] + 0.55 * np.array(col)
            mk = p.get('_drawn', {}).get(vn)
            if mk is not None:
                e = mk & ~ndimage.binary_erosion(mk, iterations=2)
                out[e] = np.array(col) * 0.6
        im = Image.fromarray(out[r0:r1, c0:c1].astype(np.uint8)).resize(((c1 - c0) * k, (r1 - r0) * k), Image.NEAREST)
        d = ImageDraw.Draw(im)
        d.text((4, 4), vn, fill=(0, 0, 0))
        for p, col in zip(parts, cols):
            mk = p.get('_drawn', {}).get(vn)
            if mk is None:
                continue
            rr, cc = np.nonzero(mk)
            d.text(((cc.mean() - c0) * k, (rr.mean() - r0) * k), '%.2f' % p['fit']['iou'].get(vn, 0), fill=(0, 0, 0))
        tiles.append(im)
    W = sum(t.size[0] for t in tiles) + 8 * (len(tiles) - 1)
    H = max(t.size[1] for t in tiles)
    canvas = Image.new('RGB', (W, H), (255, 255, 255))
    x = 0
    for t in tiles:
        canvas.paste(t, (x, 0)); x += t.size[0] + 8
    canvas.save(path)
    return path


def main(args):
    """python -m charkit.geom.lockshell BUILD [--out DIR] [--opts JSON] [--cache PKL]: the lock shells a spec's
    lock_shells would build, fitted on a build's own inputs, their per-view fit (cost, IoU against the drawn lock) and
    the picture (DIR/fit.json, DIR/fit.png)."""
    build = args[0]
    out = args[args.index('--out') + 1] if '--out' in args else os.path.join(build, 'lockshells')
    opts = json.loads(args[args.index('--opts') + 1]) if '--opts' in args else {
        'families': ['side_locks'], 'groups': [{'family': 'lower_back', 'view': 'back', 'phi': [100, 175]}]}
    cache = args[args.index('--cache') + 1] if '--cache' in args else None
    ctx = context(build, cache)
    os.makedirs(out, exist_ok=True)
    res = build_shells(ctx['F'], ctx['masks'], ctx['views'], ctx['hull_frame'], ctx['L'], dict(opts, split=ctx['split']))
    json.dump(res['report'], open(os.path.join(out, 'fit.json'), 'w'), indent=1)
    picture(res, ctx, os.path.join(out, 'fit.png'))
    # each family's coverage per view: the visible shells' union against the hair layers' family mask (the guard's
    # hair_piece_<family> in miniature: the build's own measure is the QA's)
    S = load_split(ctx['split'])
    cov = {}
    for fam in opts.get('families', ()):
        parts = res['parts'].get(fam, [])
        for vn in ('front', 'profile', 'back'):
            fm = ctx['masks'].get('%s__%s' % (vn, fam))
            if fm is None or vn not in S['views']:
                continue
            lab = visible(parts, ctx, vn, S['views'][vn]['az'], fm.shape)
            m = lab > 0
            cov['%s %s' % (fam, vn)] = round(float((m & fm).sum() / max(1, (m | fm).sum())), 3)
    res['report']['coverage'] = cov
    json.dump(res['report'], open(os.path.join(out, 'fit.json'), 'w'), indent=1)
    print('coverage (IoU of the visible shells with the family mask):', cov)
    ious = [v for x in res['report']['locks'] for v in x['iou'].values()]
    print('lock shells: %d, views fitted %d, IoU mean %.3f median %.3f' % (
        len(res['report']['locks']), len(ious), np.mean(ious) if ious else 0, np.median(ious) if ious else 0))
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv[1:]))
