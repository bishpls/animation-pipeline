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
               share=0.5, min_px=60, bins=14, samples=40, depth_ratio=0.35, inset=0.010, root_in=0.03, gap=0.006,
               prior_depth=0.15, prior_smooth=0.02, prior_twist=0.5, assoc=0.35, assoc_cover=0.3, tip_w=0.12,
               w_max=2.5, n_ring=10, refit=True, views=('front', 'three_quarter', 'profile', 'back'))
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
        out['views'][n] = dict(img=Z[n], az=float(v['az']), ppl=float(v.get('ppl', 0) or 0),
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
    a = r - t * np.einsum('ij,ij->i', r, t)[:, None]
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
    return Wd[np.arange(len(u)), first]


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
            # the drawn width at each sample: the nearest drawn station's
            dd = np.linalg.norm(pc[:, None, :] - d['D'][None], axis=2)
            wd = d['W'][np.argmin(dd, 1)]
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
            out += [_seg_dist(d['D'], pc), _seg_dist(pc, d['D']), 2 * (pc[0] - d['D'][0]), 2 * (pc[-1] - d['D'][-1])]
        # depth: the curve's radius about the chart's centre near its start's (the envelope less its offset)
        ch, G = self.F['chart'], self.F['grid']
        ph, th, r = ch.coords(P)
        ppl = self.views[self.primary].ppl
        s_ = self.hull_frame[0]
        tpx = ppl / s_                                   # px per metre
        if self.target_r is not None:
            out.append(self.o['prior_depth'] * (r - self.target_r(ph, th)) * tpx)
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
            dd = np.linalg.norm(pc[:, None, :] - d['D'][None], axis=2)
            wd = d['W'][np.argmin(dd, 1)]
            out.append(0.5 * (cvec * Wt - wd))
        out.append(np.array([self.o['prior_twist'] * twist * 10.0]))
        return np.concatenate([np.ravel(q) for q in out])

    def fit(self):
        from scipy.optimize import least_squares
        ch, G = self.F['chart'], self.F['grid']
        P0 = self.curve()
        ph0, th0, r0 = ch.coords(P0)
        R0 = G.sample(self.F['R'], ph0, th0)
        dr = float(np.median(R0 - r0))                 # how far under the envelope the start lies
        self.target_r = lambda ph, th: G.sample(self.F['R'], ph, th) - dr
        x0 = np.r_[self.Q.ravel(), self.twist]
        scale = np.r_[np.full(18, 0.01 * self.L), 0.3]
        sol = least_squares(self.residuals, x0, x_scale=scale, max_nfev=300)
        self.Q = sol.x[:18].reshape(6, 3)
        self.twist = float(sol.x[18])
        P = self.curve()
        for vn, d in self.drawn.items():
            from .hairpieces import _seg_dist
            pc = self.px(P, vn)
            self.cost[vn] = round(float(np.mean(_seg_dist(d['D'], pc))), 2)
        return sol

    def shell(self):
        """the lock's tube (a hairpieces part), its root carried on into the hair."""
        P = self.curve()
        Wt = self.widths(P, self.twist)
        from scipy.ndimage import gaussian_filter1d
        s_ = self.hull_frame[0]
        ppl = self.views[self.primary].ppl
        Wd = np.max([d['W'].max() for d in self.drawn.values()]) / ppl * s_
        W = np.clip(gaussian_filter1d(Wt, 1.5, mode='nearest'), 0.2 * Wd / self.o['w_max'], self.o['w_max'] * Wd)
        u = np.linspace(0, 1, len(P))
        W = W * np.clip((1 - u) / 0.2, self.o['tip_w'], 1.0) ** 0.6
        Tk = self.o['depth_ratio'] * W
        # the root carried on into the hair
        d0 = P[0] - P[1]
        d0 /= np.linalg.norm(d0) + 1e-12
        k = 3
        ext = P[0] + d0 * (self.o['root_in'] * self.L) * np.linspace(1, 1.0 / k, k)[:, None]
        line = np.r_[ext, P]
        Wl = np.r_[np.full(k, W[0]), W]
        Tl = np.r_[np.full(k, Tk[0]), Tk]
        part = tube(line, Wl, Tl, self.F['chart'], self.twist, self.o['n_ring'])
        part['fit'] = dict(views=sorted(self.drawn), cost_px=self.cost, twist_deg=round(math.degrees(self.twist), 1),
                           width_L=round(float(W.max()) / self.L, 4), length_L=round(float(
                               np.linalg.norm(np.diff(P, axis=0), axis=1).sum()) / self.L, 4),
                           locks={vn: int(d['lock']) for vn, d in self.drawn.items()})
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

    jobs = [(f, None) for f in o['families']] + [(g['family'], g) for g in o['groups']]
    for fam, grp in jobs:
        key = fam if grp is None else grp.get('name', '%s_%s' % (fam, grp.get('view', '')))
        parts = []
        prim = [grp['view']] if grp else list(o['primary'].get(fam, ('front',)))
        for pv in prim:
            if pv not in S['views'] or pv not in views:
                continue
            V = S['views'][pv]
            lo, hi = ranks(pv)
            for lid, x in sorted(V['locks'].items(), key=lambda kv: -kv[1]['area_px']):
                f_, share = fam_of[pv].get(lid, (None, 0.0))
                if f_ != fam or share < o['share'] or lid in claimed[pv] or x['area_px'] < o['min_px']:
                    continue
                if grp and grp.get('phi'):
                    p_ = x.get('tip_phi')
                    if p_ is None or not (grp['phi'][0] <= p_ <= grp['phi'][1]):
                        continue
                mask = V['img'] == lid
                lk = Lock('%s:%s%d' % (key, pv[0], lid), fam, pv, F, views, hull_frame, L, o)
                lay = x.get('layer') or 0.0
                lk.offset = o['inset'] * L * ((hi - lay) / max(1e-6, hi - lo) if hi > lo else 0.0)
                if not lk.add_view(pv, V['az'], mask, full_rc(pv, x['root_rc']), lid, lay):
                    continue
                claimed[pv].add(lid)
                lk.init()
                lk.fit()
                # the other views: the drawn lock this shell covers most claims it
                if o['refit']:
                    part = lk.shell()
                    for vn in o['views']:
                        if vn == pv or vn not in S['views'] or vn not in views:
                            continue
                        W_ = S['views'][vn]
                        sil = silhouette(part['V'], part['T'], views[vn], W_['az'], hull_frame, W_['img'].shape)
                        if sil.sum() < o['min_px']:
                            continue
                        best = None
                        for l2 in np.unique(W_['img'][sil & (W_['img'] > 0)]):
                            if l2 in claimed[vn]:
                                continue
                            m2 = W_['img'] == l2
                            inter = float((m2 & sil).sum())
                            cover, prec = inter / m2.sum(), inter / sil.sum()
                            sc = min(cover, prec)
                            if prec >= o['assoc'] and cover >= o['assoc_cover'] and (best is None or sc > best[0]):
                                best = (sc, int(l2), m2)
                        if best is None:
                            continue
                        x2 = W_['locks'][best[1]]
                        if lk.add_view(vn, W_['az'], best[2], full_rc(vn, x2['root_rc']), best[1], x2.get('layer')):
                            claimed[vn].add(best[1])
                    if len(lk.drawn) > 1:
                        lk.fit()
                part = lk.shell()
                # each view's IoU of the shell's silhouette with its drawn lock
                ious = {}
                for vn, d in lk.drawn.items():
                    sil = silhouette(part['V'], part['T'], views[vn], d['az'], hull_frame, d['mask'].shape)
                    ious[vn] = round(float((sil & d['mask']).sum() / max(1, (sil | d['mask']).sum())), 3)
                part['fit']['iou'] = ious
                part['fit']['name'] = lk.name
                part['fit']['side'] = 'L' if (part['V'][:, 0].mean() - F['chart'].c[0]) > 0 else 'R'
                parts.append(part)
                report['locks'].append(part['fit'])
                if log:
                    log('lock shell %s: views %s, cost px %s, IoU %s, twist %.0f deg, width %.3f L' % (
                        lk.name, sorted(lk.drawn), lk.cost, ious, math.degrees(lk.twist), part['fit']['width_L']))
        out[key] = parts
    return dict(parts=out, report=report, opts={k: v for k, v in o.items() if k != 'split'})
