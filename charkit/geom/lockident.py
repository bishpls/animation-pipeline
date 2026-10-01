"""Cross-view lock identity (tool/hairident, docs/workstreams/hairident.md): which drawn lock in one view is which in the
others, decided the way an animator works: each lock's 3D path decided once, projected into every view, matched to
the drawn locks there, refitted, and again.

The pilot's lock shells (charkit.geom.lockshell) fit each drawn lock in its primary view, then let each other view's
nearest drawn lock join one at a time (greedy, the first lock to claim a target keeps it): 2 of 17 locks ended in two
views, and a joined view cost the primary 1-3 -> 5-9 px. Here:

  Scene        a fit's surroundings (lockshell.build_shells' own: the views' drawn hair as signed distances, the
               families' regions, the envelope's first surface per view, each view's drawn targets), so a lock can be
               made, given views and fitted outside a build
  assign       one view's drawn targets matched to the 3D locks at once (Hungarian, scipy's linear_sum_assignment): the
               cost of a pair the projected centreline's distance to the drawn one over the heights both span, plus the
               tips' height apart; a lock the view can't show (faces away) or no target near enough stays unassigned
               (a dummy column at cost `assign_max`); the layer order (the splitter's T-junction ranks) as a constraint:
               a pair of locks whose order in depth the assignment would flip pays `layer_w` each
  joint_fit    every lock fitted in its primary view, then rounds of: assign every other view, refit each lock with
               its assigned views (a view the refit can't follow within view_cost_max is dropped for the round), until
               the assignment stops changing

Everything here is opt-in: the default build doesn't call it (the pieces step reaches it only through lock_shells'
`ident` option).
"""
import math

import numpy as np

from . import lockshell as ls

VIEWS = ('front', 'three_quarter', 'profile', 'back')


class Scene:
    """the fit's surroundings for a build's context (lockshell.context's dict) and the shells' options."""

    def __init__(self, ctx, opts=None, split=None):
        o = dict(ls.DEFAULT, **(opts or {}))
        self.o = o
        F, views, hf, L = ctx['F'], ctx['views'], ctx['hull_frame'], ctx['L']
        if o.get('det'):
            F, views, hf, L = ls.det_inputs(F, views, hf, L, o.get('det_q_in'))
        self.F, self.views, self.hull_frame, self.L = F, views, hf, L
        self.masks = ctx['masks']
        self.S = ls.load_split(split or ctx['split'])
        from scipy import ndimage as nd
        self.sdist = {}
        for vn, W_ in self.S['views'].items():
            hm = W_['img'] > 0
            for k_, m_ in self.masks.items():
                if k_.startswith(vn + '__') and m_.shape == hm.shape:
                    hm = hm | m_
            self.sdist[vn] = (nd.distance_transform_edt(~hm) - nd.distance_transform_edt(hm)).astype(np.float32)
        self._fd, self._ed, self._co = {}, {}, {}

    # ---------------------------------------------------------------------------------------------- build_shells' own
    def az(self, vn):
        return self.S['views'][vn]['az']

    def facing(self, P, vn):
        rad = (P - self.F['chart'].c)[:, :2].mean(0)
        rad /= np.linalg.norm(rad) + 1e-12
        a_ = math.radians(self.az(vn))
        return float(rad @ np.array([math.sin(a_), -math.cos(a_)]))

    def fam_dist(self, vn, fam):
        k_ = (vn, fam)
        if k_ not in self._fd:
            from scipy import ndimage as nd
            fm = self.masks.get('%s__%s' % (vn, fam))
            if fm is None or fm.shape != self.S['views'][vn]['img'].shape or not self.o['contain_family']:
                self._fd[k_] = self.sdist[vn]
            else:
                fm = nd.binary_dilation(fm, iterations=3)
                self._fd[k_] = (nd.distance_transform_edt(~fm) - nd.distance_transform_edt(fm)).astype(np.float32)
        return self._fd[k_]

    def env_depth(self, vn):
        if vn not in self._ed:
            from scipy import ndimage as nd
            W_ = self.S['views'][vn]
            sd = self.sdist[vn][::2, ::2]
            rr, cc = np.nonzero(sd < 3)
            D = np.full(sd.shape, np.nan, np.float32)
            a_ = math.radians(W_['az'])
            e = np.array([math.sin(a_), -math.cos(a_), 0.0])
            for i in range(0, len(rr), 2000):
                Pw = ls.envelope_points(self.F, self.views[vn], W_['az'], self.hull_frame, 2 * cc[i:i + 2000],
                                        2 * rr[i:i + 2000], self.L)
                D[rr[i:i + 2000], cc[i:i + 2000]] = Pw @ e
            bad = ~np.isfinite(D)
            if bad.any() and (~bad).any():
                _, (ir, ic) = nd.distance_transform_edt(bad, return_indices=True)
                D = D[ir, ic]
            self._ed[vn] = D
        return self._ed[vn]

    def coef(self, key, arr):
        if key not in self._co:
            self._co[key] = ls._coef(arr)
        return self._co[key]

    def set_contain(self, lk):
        o = lk.o
        if o['view_depth']:
            lk.env_depth = {vn: self.env_depth(vn) for vn in lk.drawn}
            if o.get('det'):
                lk.env_depth3 = {vn: self.coef(('env', vn), lk.env_depth[vn]) for vn in lk.drawn}
        P_ = lk.curve()
        hw = float(np.median(lk.drawn[lk.primary]['W'])) / 2
        vs = [vn for vn in self.S['views'] if vn in self.views and self.facing(P_, vn) >= o['facing']]
        if o.get('det'):
            lk.contain = {vn: (self.az(vn), self.coef(('fam', vn, lk.family), self.fam_dist(vn, lk.family)), hw)
                          for vn in vs}
        else:
            lk.contain = {vn: (self.az(vn), self.fam_dist(vn, lk.family), hw) for vn in vs}

    def targets(self, vn, fam, unit='locks'):
        """build_shells' targets: each splitter lock's part in the family's mask, fragments merged -> [dict(id, lock,
        mask, root, info, area, D)]."""
        from scipy import ndimage
        from .hairpieces import strand_centreline
        o, S, masks = self.o, self.S, self.masks
        allfams = ('bangs', 'side_locks', 'upper_back', 'lower_back', 'ahoge', 'flyaways')
        V = S['views'][vn]
        fm = masks.get('%s__%s' % (vn, fam))
        parts_ = []
        for lid, x in V['locks'].items():
            m = V['img'] == lid
            if fm is not None and fm.shape == m.shape:
                m = m & fm
            elif any(masks.get('%s__%s' % (vn, f_)) is not None for f_ in allfams):
                continue
            lab, n = ndimage.label(m)
            for j in range(1, n + 1):
                parts_.append([int(lid), j, lab == j])
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
        b = V['box']
        out = []
        for lid, j, mj in parts_:
            x = V['locks'][lid]
            if mj.sum() < o['min_px']:
                continue
            rr, cc = np.nonzero(mj)
            r0, c0 = x['root_rc'][0] + b[0], x['root_rc'][1] + b[2]
            q = int(np.argmin(np.hypot(rr - r0, cc - c0)))
            base = np.zeros(mj.shape, bool)
            base[max(0, rr[q] - 3):rr[q] + 4, max(0, cc[q] - 3):cc[q] + 4] = True
            cl = strand_centreline(mj, base, o['bins'])
            out.append(dict(id=(int(lid), j), lock=int(lid), mask=mj, root=(float(rr[q]), float(cc[q])), info=x,
                            area=int(mj.sum()), D=None if cl is None else cl[0], W=None if cl is None else cl[1],
                            layer=float(x.get('layer') or 0.0)))
        return sorted(out, key=lambda t_: -t_['area'])

    # ---------------------------------------------------------------------------------------------- locks
    def lock(self, name, fam, primary, mask, root, lid=0, layer=0.0, opts=None, offset=0.0):
        """a Lock fitted to one view's drawn mask (root: (row, col) at its root end) -> the Lock, or None."""
        o = dict(self.o, **(opts or {}))
        lk = ls.Lock(name, fam, primary, self.F, self.views, self.hull_frame, self.L, o)
        lk.offset = offset
        if not lk.add_view(primary, self.az(primary), mask, root, lid, layer):
            return None
        lk.init()
        return lk

    def add(self, lk, vn, mask, root, lid=0, layer=0.0):
        return lk.add_view(vn, self.az(vn), mask, root, lid, layer)

    def fit(self, lk, cap=None):
        self.set_contain(lk)
        lk.nfev_cap = cap
        lk.fit()
        lk.nfev_cap = None
        return lk

    def iou(self, lk, part=None, views=None):
        """the lock's shell against each of its drawn masks (or the given {view: mask}) -> {view: IoU}."""
        part = part or lk.shell()
        out = {}
        for vn, m in (views or {vn: d['mask'] for vn, d in lk.drawn.items()}).items():
            sil = ls.silhouette(part['V'], part['T'], self.views[vn], self.az(vn), self.hull_frame, m.shape)
            out[vn] = round(float((sil & m).sum() / max(1, (sil | m).sum())), 3)
        return out


def root_of(mask):
    """a drawn lock's root end when nothing else says: its topmost pixel (the middle one of its top row)."""
    rr, cc = np.nonzero(mask)
    r0 = rr.min()
    c = cc[rr == r0]
    return (float(r0), float(np.sort(c)[len(c) // 2]))


def lock_picture(sc, fits, masks, path, rgb=None, k=2, pad=40):
    """per view a crop round the drawn masks: the drawing (dimmed), the drawn mask outlined, its centreline (green),
    and each fit's projected centreline and shell outline in its colour -> path. fits: [(label, Lock, (r, g, b))]."""
    from PIL import Image, ImageDraw
    from scipy import ndimage
    tiles = []
    for vn, m in masks.items():
        rr, cc = np.nonzero(m)
        r0, r1 = max(0, rr.min() - pad), min(m.shape[0], rr.max() + pad)
        c0, c1 = max(0, cc.min() - pad), min(m.shape[1], cc.max() + pad)
        base = (np.asarray(rgb[vn], float) * 255 if rgb is not None and vn in rgb else np.full(m.shape + (3,), 235.0))
        base = 0.55 * base + 0.45 * 255
        e = m & ~ndimage.binary_erosion(m, iterations=1)
        base[e] = (90, 90, 90)
        im = Image.fromarray(base[r0:r1, c0:c1].astype(np.uint8)).resize(((c1 - c0) * k, (r1 - r0) * k), Image.NEAREST)
        d = ImageDraw.Draw(im)
        for lab, lk, col in fits:
            if vn not in lk.drawn:
                continue
            D = lk.drawn[vn]['D']
            d.line([((x - c0) * k, (y - r0) * k) for x, y in D], fill=(0, 160, 0), width=3)
            pc = lk.px(lk.curve(), vn)
            d.line([((x - c0) * k, (y - r0) * k) for x, y in pc], fill=col, width=2)
            d.ellipse([((pc[0, 0] - c0) * k - 4, (pc[0, 1] - r0) * k - 4), ((pc[0, 0] - c0) * k + 4, (pc[0, 1] - r0) * k + 4)],
                      outline=col)
        y = 4
        d.text((4, y), vn, fill=(0, 0, 0))
        for lab, lk, col in fits:
            if vn in lk.cost:
                y += 12
                d.text((4, y), '%s %.1f px' % (lab, lk.cost[vn]), fill=col)
        tiles.append(im)
    W = sum(t.size[0] for t in tiles) + 6 * (len(tiles) - 1)
    H = max(t.size[1] for t in tiles)
    canvas = Image.new('RGB', (W, H), (255, 255, 255))
    x = 0
    for t in tiles:
        canvas.paste(t, (x, 0)); x += t.size[0] + 6
    canvas.save(path)
    return path


# ------------------------------------------------------------------------------------------------ the joint fit

IDENT = dict(rounds=3, assign_max=12.0, tip_w=0.25, overlap_min=0.3, overlap_w=6.0, layer_w=4.0, layer_gap=0.3,
             depth_two=0.0, view_w={}, az_eff={}, join_cost_max=6.0, nfev=150, refit_nfev=300,
             depth_sigma=0.0, depth_sigma_known=0.03, shift_pen=0.15, known_sep=30.0, assign_facing=-0.25,
             primary_slack=3.0, later_primaries='after', height_cost=False)
# rounds          assignment / refit rounds (stops early when no view's assignment changes)
# assign_max      px: a lock left unassigned in a view costs this (the Hungarian's dummy column): a pair dearer stays apart
# tip_w           the tips' height apart (px) per px of centreline cost
# overlap_min     a pair whose heights overlap less than this share of the shorter is not a candidate
# overlap_w       px added per missing share of overlap
# layer_w         px added to each of two pairs whose depth order the assignment would flip (the splitter's T-junction
#                 ranks: a lock in front of its neighbour in one view is in front in the others)
# layer_gap       ranks closer than this don't order a pair
# depth_two       view_depth once a lock is fitted in two or more views (the views place it in depth; the envelope's
#                 first surface, round 2's hull, pulled each view's lock onto it and the joined views fought: 0 frees it)
# view_w          {view: weight} of a view's terms in the refit (a view drawn view-dependently counts less)
# az_eff          {view: {family: deg}}: the azimuth a view's drawing places a family at (the three-quarter's side locks
#                 are drawn as if turned further than its face: tools/hairident/az3scan.py)
# join_cost_max   px: a view whose refitted cost exceeds this is dropped for the round (the lock and the drawing there
#                 disagree)
# nfev, refit_nfev  evaluation caps of a trial and of the round's final refit
# depth_sigma     L: how far a lock fitted in one view may lie in depth from the envelope's guess: in another view its
#                 projection may slide sideways by depth_sigma * |sin(the views' angle)| (a front lock's depth is the
#                 hull's guess until a second view places it); 0 off. depth_sigma_known once two views >= known_sep deg
#                 apart have placed it
# shift_pen       px of cost per px of that slide
# assign_facing   a lock whose outward direction faces a view less than this isn't a candidate there (the shells'
#                 own `facing`, 0.2, kept the face-framing locks out of the three-quarter, where the drawing shows them)
# height_cost     where the lock's depth isn't placed yet (depth_sigma's slide), the pair's cost from its heights:
#                 height_cost() (the projected curve's shape there is the hull's guess, not the lock's)
# primary_slack   px: a join that raises the lock's primary view past its own fit by more than this is dropped
# later_primaries 'after': a family's later primary views (the side locks' profile) seed locks only from the targets
#                 the first round's assignment left over (a drawn lock is first the same lock seen again); 'before':
#                 the shells' way (seeded with the first, by shell coverage)


def centre_cost(Pp, D, o):
    """a projected centreline (n, 2: col, row; root to tip) against a drawn one (k, 2) -> px, or inf when their heights
    overlap too little: both ways' mean distance over the heights both span, the tips' heights apart, the overlap's
    shortfall."""
    from .hairpieces import _seg_dist
    lo, hi = max(Pp[:, 1].min(), D[:, 1].min()), min(Pp[:, 1].max(), D[:, 1].max())
    span = min(np.ptp(Pp[:, 1]), np.ptp(D[:, 1])) + 1e-9
    ov = (hi - lo) / span
    if ov < o['overlap_min']:
        return np.inf
    sd = (D[:, 1] >= lo) & (D[:, 1] <= hi)
    sp = (Pp[:, 1] >= lo) & (Pp[:, 1] <= hi)
    if sd.sum() < 2 or sp.sum() < 2:
        return np.inf
    d = 0.5 * (float(np.mean(_seg_dist(D[sd], Pp))) + float(np.mean(_seg_dist(Pp[sp], D))))
    return d + o['tip_w'] * abs(float(Pp[-1, 1] - D[-1, 1])) + o['overlap_w'] * max(0.0, 1.0 - ov)


def height_cost(Pp, D, S, o):
    """a projected centreline against a drawn one when the lock's depth is unknown: the tips' rows apart, half the
    roots', the heights' overlap shortfall, and the mean column apart beyond the depth's slide S px (a tenth)."""
    lo, hi = max(Pp[:, 1].min(), D[:, 1].min()), min(Pp[:, 1].max(), D[:, 1].max())
    span = min(np.ptp(Pp[:, 1]), np.ptp(D[:, 1])) + 1e-9
    ov = (hi - lo) / span
    if ov < o['overlap_min']:
        return np.inf
    dc = abs(float(np.mean(Pp[:, 0]) - np.mean(D[:, 0])))
    return (abs(float(Pp[-1, 1] - D[-1, 1])) + 0.5 * abs(float(Pp[0, 1] - D[0, 1])) +
            o['overlap_w'] * max(0.0, 1.0 - ov) + 0.1 * max(0.0, dc - S))


class Ident:
    """the joint fit's state: locks (lockshell.Lock), their families and primary targets; per view the targets."""

    def __init__(self, sc, cfg=None, views=VIEWS, log=print):
        self.sc, self.log = sc, log or (lambda *a: None)
        self.cfg = dict(cfg or {})
        self.io = dict(IDENT, **(self.cfg.get('ident') or {}))
        self.views = [v for v in views if v in sc.S['views'] and v in sc.views]
        self.locks, self.meta = [], []     # meta: dict(family, primary, target id, group opts)
        self.tg = {}

    def targets(self, vn, fam):
        if (vn, fam) not in self.tg:
            self.tg[(vn, fam)] = [t for t in self.sc.targets(vn, fam) if t['D'] is not None]
        return self.tg[(vn, fam)]

    def az_of(self, vn, fam):
        return float((self.io['az_eff'].get(vn) or {}).get(fam, self.sc.az(vn)))

    def lock_opts(self, grp):
        o = dict(grp.get('opts') or {}) if grp else {}
        if self.io.get('view_w'):
            o['view_w'] = dict(self.io['view_w'])
        for k in ('twist_axis', 'tip_curl', 'depth_ratio', 'twist_max'):
            if k in self.cfg:
                o.setdefault(k, self.cfg[k])
        return o

    def init_locks(self):
        """every primary view's drawn targets a lock each, fitted alone (a later primary's target an earlier lock's
        shell covers is that lock seen again: it waits for the assignment)."""
        sc, o = self.sc, self.sc.o
        jobs = [(f, None) for f in self.cfg.get('families', ('side_locks',))] + \
               [(g['family'], g) for g in self.cfg.get('groups', ())]
        for fam, grp in jobs:
            prim = [grp['view']] if grp else list(o['primary'].get(fam, ('front',)))
            if self.io['later_primaries'] == 'after':
                prim = prim[:1]
            for pv in prim:
                if pv not in self.views:
                    continue
                for T_ in self.targets(pv, fam):
                    x = T_['info']
                    if grp and grp.get('phi'):
                        p_ = x.get('tip_phi')
                        if p_ is None or not (grp['phi'][0] <= p_ <= grp['phi'][1]):
                            continue
                    if pv != prim[0]:
                        cov = 0.0
                        for lk, mt in zip(self.locks, self.meta):
                            if mt['family'] != fam or sc.facing(lk.curve(), pv) < o['facing']:
                                continue
                            p2 = lk.shell()
                            sil = ls.silhouette(p2['V'], p2['T'], sc.views[pv], sc.az(pv), sc.hull_frame,
                                                T_['mask'].shape)
                            cov = max(cov, float((sil & T_['mask']).sum()) / T_['mask'].sum())
                        if cov >= o['dedup']:
                            continue
                    off = -o['over'] * sc.L if grp and not grp.get('replace', True) else 0.0
                    name = '%s:%s%d.%d' % (fam if not grp else '%s_%s' % (fam, grp.get('view', '')), pv[0],
                                           T_['lock'], T_['id'][1])
                    lk = sc.lock(name, fam, pv, T_['mask'], T_['root'], T_['lock'], T_['layer'],
                                 opts=self.lock_opts(grp), offset=off)
                    if lk is None:
                        continue
                    lk.over = bool(grp and not grp.get('replace', True))
                    sc.fit(lk, cap=self.io['refit_nfev'])
                    self.locks.append(lk)
                    self.meta.append(dict(family=fam, primary=pv, target=T_['id'], group=grp, layer=T_['layer'],
                                          assign={pv: T_['id']}, solo=lk.cost.get(pv)))
        self.log('lockident: %d locks from the primary views' % len(self.locks))

    def seed_later(self, A):
        """the later primary views' targets no lock was assigned (a drawn lock no lock of the first views is) -> new
        locks, fitted alone (later_primaries 'after')."""
        sc, o = self.sc, self.sc.o
        n0 = len(self.locks)
        for fam in self.cfg.get('families', ('side_locks',)):
            for pv in list(o['primary'].get(fam, ('front',)))[1:]:
                if pv not in self.views:
                    continue
                taken = {t['id'] for i, t in A.get(pv, {}).items() if self.meta[i]['family'] == fam}
                for T_ in self.targets(pv, fam):
                    if T_['id'] in taken:
                        continue
                    lk = sc.lock('%s:%s%d.%d' % (fam, pv[0], T_['lock'], T_['id'][1]), fam, pv, T_['mask'], T_['root'],
                                 T_['lock'], T_['layer'], opts=self.lock_opts(None))
                    if lk is None:
                        continue
                    sc.fit(lk, cap=self.io['refit_nfev'])
                    self.locks.append(lk)
                    self.meta.append(dict(family=fam, primary=pv, target=T_['id'], group=None, layer=T_['layer'],
                                          assign={pv: T_['id']}, solo=lk.cost.get(pv)))
        self.log('lockident: %d locks seeded from the later primary views\' leftover targets' % (len(self.locks) - n0))

    def assign(self, vn):
        """one view's targets matched to the locks at once -> {lock index: target id}."""
        from scipy.optimize import linear_sum_assignment
        sc, o = self.sc, self.io
        out = {}
        for fam in sorted({m['family'] for m in self.meta}):
            idx = [i for i, m in enumerate(self.meta) if m['family'] == fam and m['primary'] != vn]
            own = {m['target'] for m in self.meta if m['family'] == fam and m['primary'] == vn}
            tgs = [t for t in self.targets(vn, fam) if t['id'] not in own]
            if not idx or not tgs:
                continue
            from .hairpieces import view_px
            az = self.az_of(vn, fam)
            C = np.full((len(idx), len(tgs)), np.inf)
            ppl = sc.views[vn].ppl
            for a, i in enumerate(idx):
                lk = self.locks[i]
                P = lk.curve()
                if sc.facing(P, vn) < o['assign_facing']:
                    continue
                c_, r_ = view_px(P, sc.views[vn], az, False, sc.hull_frame)
                Pp = np.c_[c_, r_]
                shifts = [0.0]
                if o['depth_sigma']:
                    azs = [d['az'] for v_, d in lk.drawn.items() if v_ != vn]
                    sep = max((abs((x - y + 180) % 360 - 180) for x in azs for y in azs), default=0.0)
                    sg = o['depth_sigma_known'] if sep >= o['known_sep'] else o['depth_sigma']
                    near = min(azs, key=lambda x: abs((x - az + 180) % 360 - 180)) if azs else az
                    S_ = sg * abs(math.sin(math.radians(az - near))) * ppl
                    if S_ >= 1.0:
                        shifts = list(np.linspace(-S_, S_, 2 * int(min(8, math.ceil(S_ / 3.0))) + 1))
                for b, t in enumerate(tgs):
                    if len(shifts) > 1 and o.get('height_cost'):
                        # the depth not yet placed: the heights decide (a lock's root and tip rows are the same in
                        # every view), the side position within the slide's reach
                        C[a, b] = height_cost(Pp, t['D'], max(abs(shifts[0]), 1.0), o)
                    else:
                        C[a, b] = min(centre_cost(Pp + np.array([dx, 0.0]), t['D'], o) + o['shift_pen'] * abs(dx)
                                      for dx in shifts)
            big = 1e6
            for it in range(4):
                M = np.where(np.isfinite(C), C, big)
                Dm = np.full((len(idx), len(idx)), big)
                np.fill_diagonal(Dm, o['assign_max'])
                rows, cols = linear_sum_assignment(np.c_[M, Dm])
                pick = {a: b for a, b in zip(rows, cols) if b < len(tgs) and M[a, b] < o['assign_max']}
                # the layer order: a pair of locks whose depth order the assignment flips pays layer_w on both pairs
                flips = []
                ks = sorted(pick)
                for x_ in range(len(ks)):
                    for y_ in range(x_ + 1, len(ks)):
                        a1, a2 = ks[x_], ks[y_]
                        la, lb = self.meta[idx[a1]]['layer'], self.meta[idx[a2]]['layer']
                        ta, tb = tgs[pick[a1]]['layer'], tgs[pick[a2]]['layer']
                        if abs(la - lb) >= o['layer_gap'] and abs(ta - tb) >= o['layer_gap'] and (la - lb) * (ta - tb) < 0:
                            flips.append((a1, a2))
                if not flips:
                    break
                for a1, a2 in flips:
                    C[a1, pick[a1]] += o['layer_w']
                    C[a2, pick[a2]] += o['layer_w']
            for a, b in pick.items():
                out[idx[a]] = tgs[b]
        return out

    def refit(self, i, views_targets):
        """lock i fitted in its primary and the given {view: target} -> {view: cost} (views it can't follow out)."""
        sc, lk, mt = self.sc, self.locks[i], self.meta[i]
        keep = lk.state()
        drawn0 = {vn: d for vn, d in lk.drawn.items() if vn == mt['primary']}
        lk.drawn = dict(drawn0)
        for vn, t in views_targets.items():
            lk.add_view(vn, self.az_of(vn, mt['family']), t['mask'], t['root'], t['lock'], t['layer'])
        if len(lk.drawn) > 1 and self.io['depth_two'] is not None:
            lk.o = dict(lk.o, view_depth=self.io['depth_two'])
        else:
            lk.o = dict(lk.o, view_depth=sc.o['view_depth'])
        sc.fit(lk, cap=self.io['refit_nfev'])
        bad = [vn for vn, c in lk.cost.items() if vn != mt['primary'] and c > self.io['join_cost_max']]
        if not bad and mt.get('solo') is not None and len(lk.cost) > 1 and \
                lk.cost.get(mt['primary'], 0.0) > mt['solo'] + self.io['primary_slack']:
            bad = [max((vn for vn in lk.cost if vn != mt['primary']), key=lambda v_: lk.cost[v_])]
        if bad:
            for vn in bad:
                lk.drawn.pop(vn)
            if len(lk.drawn) == 1:
                lk.o = dict(lk.o, view_depth=sc.o['view_depth'])
            sc.fit(lk, cap=self.io['refit_nfev'])
        mt['assign'] = {vn: (views_targets[vn]['id'] if vn in views_targets else mt['target'])
                        for vn in lk.drawn}
        mt['dropped'] = bad
        return dict(lk.cost)

    def run(self):
        self.init_locks()
        prev = None
        for r in range(self.io['rounds']):
            A = {vn: self.assign(vn) for vn in self.views}
            if r == 0 and self.io['later_primaries'] == 'after':
                self.seed_later(A)
                A = {vn: self.assign(vn) for vn in self.views}
            sig = {(vn, i): t['id'] for vn, a in A.items() for i, t in a.items()}
            if sig == prev:
                break
            prev = sig
            for i in range(len(self.locks)):
                vt = {vn: A[vn][i] for vn in self.views if i in A[vn]}
                self.refit(i, vt)
            n2 = sum(1 for lk in self.locks if len(lk.drawn) > 1)
            self.log('lockident round %d: %d assignments, %d of %d locks in 2+ views' % (
                r + 1, len(sig), n2, len(self.locks)))
        return self

    def report(self):
        locks = []
        for lk, mt in zip(self.locks, self.meta):
            part = lk.shell()
            locks.append(dict(name=lk.name, family=mt['family'], primary=mt['primary'], views=sorted(lk.drawn),
                              assign={vn: list(t) for vn, t in mt['assign'].items()}, cost_px=dict(lk.cost),
                              iou=self.sc.iou(lk, part), dropped=mt.get('dropped', []),
                              twist_deg=round(math.degrees(lk.twist), 1)))
        return dict(locks=locks, fitted_2plus=sum(1 for x in locks if len(x['views']) > 1), n=len(locks))


# ------------------------------------------------------------------------------------------------ the build's shells

def build_shells(F, masks, views, hull_frame, L, ls_opts, log=print):
    """lockshell.build_shells' product (dict(parts {family or group key: [part dicts]}, report, opts)) from the joint
    fit: the shells' options (hair.shape.pieces_opts.lock_shells) with `ident` (True or this module's IDENT overrides)
    decide each lock's views by the assignment rounds instead of the shells' greedy association."""
    o = dict(ls.DEFAULT, **{k: v for k, v in ls_opts.items() if k not in ('split', 'ident')})
    ctx = dict(F=F, masks=masks, views=views, hull_frame=hull_frame, L=L, split=ls_opts['split'])
    lock_o = {k: v for k, v in o.items() if k not in ('families', 'groups')}
    sc = Scene(ctx, lock_o)
    idn = ls_opts.get('ident')
    cfg = dict(families=list(o['families']), groups=list(o['groups']), ident=idn if isinstance(idn, dict) else {})
    idt = Ident(sc, cfg, log=log).run()
    out, report = {}, dict(locks=[], ident=dict(cfg['ident']))
    for lk, mt in zip(idt.locks, idt.meta):
        grp = mt['group']
        key = mt['family'] if grp is None else grp.get('name', '%s_%s' % (grp['family'], grp.get('view', '')))
        part = lk.shell()
        ious = {}
        for vn, d in lk.drawn.items():
            sil = ls.silhouette(part['V'], part['T'], sc.views[vn], d['az'], sc.hull_frame, d['mask'].shape)
            ious[vn] = round(float((sil & d['mask']).sum() / max(1, (sil | d['mask']).sum())), 3)
        part['fit']['iou'] = ious
        part['fit']['name'] = lk.name
        part['fit']['assign'] = {vn: list(t) for vn, t in mt['assign'].items()}
        part['fit']['dropped'] = list(mt.get('dropped') or [])
        part['_drawn'] = {vn: d['mask'] for vn, d in lk.drawn.items()}
        part['fit']['side'] = 'L' if (part['V'][:, 0].mean() - sc.F['chart'].c[0]) > 0 else 'R'
        out.setdefault(key, []).append(part)
        report['locks'].append(part['fit'])
        if log:
            log('lock shell %s: views %s, cost px %s, IoU %s' % (lk.name, sorted(lk.drawn), lk.cost, ious))
    report['fitted_2plus'] = sum(1 for x in report['locks'] if len(x.get('views') or ()) > 1)
    return dict(parts=out, report=report, opts={k: v for k, v in o.items() if k != 'split'})
