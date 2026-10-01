"""Calibration adapter for the hair clips (charkit.accqa's 'accessories' part, tool/accessories5): the views' checks
(acc_KIND_VIEW_{iou,size,pos,angle}, measured as the drawing shows each clip since accessories5, and acc_KIND_pos3d),
its declared checks (acc_KIND_VIEW_visible: the share of a clip that shows, Michael's non-occlusion rule) and the star's
face-on proportions (acc_star_arms, acc_star_minor). The stand-in for ours is the design's own clips (head_turnaround,
accqa.design) as our label images, scored by accqa.evaluate itself (its `labels`):
  design            the drawn clips moved 1-2 px together; each its own silhouette (they don't overlap: shown whole);
                    the star's arms read on each view's drawn star (its longer side arm: the other can be under the crab)
  swap              (floor, shape) each drawn clip replaced by the other's, moved and scaled onto it (centroid, area)
  scaled            (floor, size) each drawn clip shrunk to 0.55-0.7 of its width about its centroid
  moved             (floor, place) each drawn clip moved 0.07-0.12 L in a random direction
  turned            (floor, axis) each drawn clip turned 25-40 degrees about its centroid
  touching          (probe) the drawn clips moved 2 px into each other (the star over the crab): two clips side by side,
                    touching along their outline, must still read as shown
  star_under_crab   (floor, the star's visible share) the drawn crab moved 0.05 L onto the star, over it: a star a clip
                    covers must read hidden (no build hides the star, so this stands for its known-bad)
  compass           (floor, arms) the clips-alone sheet's star (an equal-armed compass star: side arms 0.48 of its height)
  four_point        (floor, minor) the star template without its minor points (the round-1 placeholder's structure)
The crab's parts face-on (tool/accessories6: acc_crab_legs, _leg_reach, _leg_roots, _claw_fingers, _claw_notch,
_stalks; the declared FACE view): the stand-in is the clips-alone sheet's crab: for a design move (dy, dx) redrawn at
1 + 0.015 dy its scale and moved (dy, dx) / 2 px (each move a different raster of the same drawing), and each floor the
sheet's crab with one part spoiled (charkit.limbs.spoil):
  legless           (floor, legs) its legs cut to stubs at the body
  short_legs        (floor, reach) its legs cut to 45% of their reach
  thin_legs         (floor, width) its legs thinned to half their width
  bottom_legs       (floor, roots) its legs turned under the body (55 degrees down round it)
  solid_claws       (floor, fingers and notch) its claws' notches filled
  no_stalks         (floor, stalks) its eye stalks cut
The crab against the star (acc_crab_VIEW_bearing, _gap, _turn, _flow; the declared family 'pair'): the drawn clips stand
for ours (the crab's axis the drawing's, accqa.CRAB_AXIS, turned with the stand-in); floors:
  orbit             (floor, bearing) the drawn crab moved round the star by 90-150 degrees, turned with it
  pointing_away     (floor, turn) the drawn crab turned so its claws point away from the star
  across_flow       (floor, flow) the drawn crab turned 60-120 degrees in place
  apart             (floor, gap) the drawn crab moved 0.06-0.1 L further from the star
Known-bad acc_a3_crab: pipeline-3d 25ff0f25 (round 5's crab, A3: short legs under the body, solid round pincers; the crab
under the star's lower tip, turned with it).
Known-bad: acc_r4_overlap (pipeline-3d 00494de, round 4's placement: the star bent over the crab, the crab 62-78% shown)
for the crab's visible share; it passes the other checks in some views, so those take floors (their verdict: guard).
"""
import numpy as np

# (a literal: charkit.calibrate reads it with ast. The known-bad, round 4's placement, passes these in some views, so
# their floors are the drawn clips spoiled)
CALIBRATION = [
    dict(check='acc_*_iou', part='accessories', adapter='Clips', known_bad=None, no_known_bad="the stored known-bad (round 4's placement) passes this in some views: the floors are the drawn clips spoiled",
         baseline=['swap'], shape=[], better='higher'),
    dict(check='acc_*_size', part='accessories', adapter='Clips', known_bad=None, no_known_bad="the stored known-bad (round 4's placement) passes this in some views: the floors are the drawn clips spoiled",
         baseline=['scaled'], shape=['acc_crab_shape', 'acc_star_shape']),
    dict(check='acc_*_pos', part='accessories', adapter='Clips', known_bad=None, no_known_bad="the stored known-bad (round 4's placement) passes this in some views: the floors are the drawn clips spoiled",
         baseline=['moved'], shape=['acc_crab_shape', 'acc_star_shape'], better='lower'),
    dict(check='acc_*_angle', part='accessories', adapter='Clips', known_bad=None, no_known_bad="the stored known-bad (round 4's placement) passes this in some views: the floors are the drawn clips spoiled",
         baseline=['turned'], shape=['acc_crab_shape', 'acc_star_shape']),
    dict(check='acc_*_pos3d', part='accessories', adapter='Clips', known_bad=None, no_known_bad="the stored known-bad (round 4's placement) passes this in some views: the floors are the drawn clips spoiled",
         baseline=['moved'], shape=['acc_crab_shape', 'acc_star_shape'], better='lower'),
    dict(check='acc_star_arms', part='accessories', adapter='Clips', known_bad=None,
         no_known_bad="no stored build has the compass star; the floor is the clips-alone sheet's",
         baseline=['compass'], shape=['acc_star_shape'], better='lower'),
    dict(check='acc_star_minor', part='accessories', adapter='Clips', known_bad=None,
         no_known_bad='the 4-point placeholder build is not stored; the floor is its structure',
         baseline=['four_point'], shape=['acc_star_shape'], better='lower'),
]
MOVE_UNDER = 0.05           # L: the probe's crab moved onto the star
PAIR_FLOORS = ('orbit', 'pointing_away', 'across_flow', 'apart')    # the pair checks' floors (the crab against the star)
TOUCH = 2                   # px: the probe's clips moved into each other


def _roll(m, dy, dx):
    return np.roll(np.roll(m, int(dy), 0), int(dx), 1)


def _affine(m, s=1.0, deg=0.0, shift=(0.0, 0.0)):
    """a mask scaled s and turned deg degrees about its centroid, then moved shift (rows, columns)."""
    from scipy import ndimage
    if not m.any():
        return m
    ys, xs = np.nonzero(m)
    c = np.array([ys.mean(), xs.mean()])
    a = np.radians(deg)
    R = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]]) * s
    Ri = np.linalg.inv(R)
    yy, xx = np.mgrid[0:m.shape[0], 0:m.shape[1]]
    P = np.stack([yy - c[0] - shift[0], xx - c[1] - shift[1]], 0).reshape(2, -1)
    Q = Ri @ P + c[:, None]
    return ndimage.map_coordinates(m.astype(float), Q, order=0, mode='constant').reshape(m.shape) > 0.5


def _resample(m, s=1.0, shift=(0.0, 0.0)):
    """a mask redrawn at scale s about its centroid and moved shift px (rows, columns), bilinear then halved: a
    different raster of the same drawing."""
    from scipy import ndimage
    ys, xs = np.nonzero(m)
    c = np.array([ys.mean(), xs.mean()])
    pad = int(abs(s - 1) * max(m.shape)) + 4
    M = np.pad(m, pad).astype(float)
    yy, xx = np.mgrid[0:M.shape[0], 0:M.shape[1]]
    c = c + pad
    return ndimage.map_coordinates(M, [(yy - c[0] - shift[0]) / s + c[0], (xx - c[1] - shift[1]) / s + c[1]], order=1,
                                   mode='constant') >= 0.5


def _turn(m, deg, about=None):
    """a mask turned deg degrees counter-clockwise in the picture about a point (rows, columns; default its centroid)."""
    from scipy import ndimage
    if not m.any():
        return m
    if about is None:
        ys, xs = np.nonzero(m)
        about = (ys.mean(), xs.mean())
    r0, c0 = about
    a = np.radians(deg)
    yy, xx = np.mgrid[0:m.shape[0], 0:m.shape[1]]
    x, y = xx - c0, -(yy - r0)                                 # the target pixel in the picture's frame
    sx = x * np.cos(a) + y * np.sin(a)                         # its source: turned back
    sy = -x * np.sin(a) + y * np.cos(a)
    return ndimage.map_coordinates(m.astype(float), [r0 - sy, c0 + sx], order=0, mode='constant') > 0.5


def _onto(m, target, d=None):
    """mask m moved d px toward target's centroid (d None: onto it)."""
    from ..accqa import _centroid
    if not m.any() or not target.any():
        return m
    v = _centroid(target) - _centroid(m)
    if d is not None:
        v = v / max(1e-9, np.linalg.norm(v)) * d
    return _roll(m, round(v[0]), round(v[1]))


class Clips:
    part = 'accessories'
    generators = {
        'swap': "each drawn clip replaced by the other's, moved and scaled onto it (centroid, area)",
        'scaled': 'each drawn clip shrunk to 0.55-0.7 of its width about its centroid',
        'moved': 'each drawn clip moved 0.07-0.12 L in a random direction',
        'turned': 'each drawn clip turned 25-40 degrees about its centroid',
        'touching': '(probe) the drawn clips moved 2 px into each other, the star over the crab',
        'star_under_crab': 'the drawn crab moved 0.05 L onto the star, over it',
        'compass': "the clips-alone sheet's star (side arms 0.48 of its height) as ours face-on",
        'four_point': 'the star template without its minor points as ours face-on',
        'legless': "the clips-alone sheet's crab with its legs cut to stubs at the body (charkit.limbs.spoil)",
        'short_legs': "the clips-alone sheet's crab with its legs cut to 45% of their reach",
        'thin_legs': "the clips-alone sheet's crab with its legs thinned to half their width",
        'bottom_legs': "the clips-alone sheet's crab with its legs turned under the body (55 degrees down)",
        'solid_claws': "the clips-alone sheet's crab with its claws' notches filled",
        'no_stalks': "the clips-alone sheet's crab with its eye stalks cut",
        'orbit': 'the drawn crab moved round the drawn star by 90-150 degrees (turned with it: its turn against the star '
                 'kept)',
        'pointing_away': "the drawn crab turned in place so its claws point away from the star (its axis along the "
                         "bearing)",
        'across_flow': 'the drawn crab turned in place 60-120 degrees (across the hair)',
        'apart': 'the drawn crab moved 0.06-0.1 L further from the star',
    }
    face_floors = ('legless', 'short_legs', 'thin_legs', 'bottom_legs', 'solid_claws', 'no_stalks')

    def __init__(self, B, design):
        from .. import accqa
        self.B, self.design = B, design
        self.got = design.clips()
        al = accqa.alone_clips(B.spec)
        self.alone = al[0] if al else {}

    def _labels(self, kind, arg):
        """the stand-in's labels(sheet, view, dv, kinds) for accqa.evaluate."""
        from .. import accqa
        rng = np.random.default_rng(7000 + (int(arg) if np.isscalar(arg) else 0))
        D = {n: d for n, d in self.got[0].items()} if self.got else {}
        cache = {}

        def labels(sname, v, dv, kinds):
            if sname == accqa.FACE_SHEET:
                return self._face(kind, arg, kinds)
            if not D.get(sname, {}).get('graded'):
                return None
            ppl = D[sname]['ppl']
            drawn = [dv['masks'].get(accqa.PIECE.get(k)) for k in kinds]
            if any(m is None for m in drawn):
                return None
            if (sname, v) in cache:
                return cache[(sname, v)]
            ms = []
            extra = {}
            star_m = drawn[kinds.index('star')] if 'star' in kinds else None
            for i, m in enumerate(drawn):
                if not m.any():
                    ms.append(m)
                    continue
                crab = kinds[i] == 'crab' and star_m is not None and star_m.any() and v in accqa.CRAB_AXIS
                if crab and kind in PAIR_FLOORS:
                    # (the pair checks' floors: the drawn crab moved or turned against the drawn star; its axis in
                    # the picture turns with it)
                    ax0 = accqa.CRAB_AXIS[v]
                    cs, cc = accqa._centroid(star_m), accqa._centroid(m)
                    bearing = float(np.degrees(np.arctan2(-(cc[0] - cs[0]), cc[1] - cs[1])))
                    if kind == 'orbit':
                        t = float(rng.choice([-1, 1]) * rng.uniform(90, 150))
                        m, extra['axis'] = _turn(m, t, about=cs), ax0 + t
                    elif kind == 'pointing_away':
                        t = bearing - ax0
                        m, extra['axis'] = _turn(m, t), ax0 + t
                    elif kind == 'across_flow':
                        t = float(rng.choice([-1, 1]) * rng.uniform(60, 120))
                        m, extra['axis'] = _turn(m, t), ax0 + t
                    elif kind == 'apart':
                        d = rng.uniform(0.06, 0.1) * ppl
                        a = np.radians(bearing)
                        m = _roll(m, round(-d * np.sin(a)), round(d * np.cos(a)))
                    ms.append(m)
                    continue
                if kind == 'design':
                    m = _roll(m, arg[0], arg[1])
                elif kind == 'swap':
                    o = drawn[(i + 1) % len(drawn)]
                    m = _onto(_affine(o, np.sqrt(m.sum() / max(1, o.sum()))), m) if o.any() else m
                elif kind == 'scaled':
                    m = _affine(m, rng.uniform(0.55, 0.7))
                elif kind == 'moved':
                    a, d = rng.uniform(0, 2 * np.pi), rng.uniform(0.07, 0.12) * ppl
                    m = _roll(m, round(d * np.sin(a)), round(d * np.cos(a)))
                elif kind == 'turned':
                    t = rng.uniform(25, 40)
                    m = _affine(m, 1.0, t)                  # (counter-clockwise in the picture)
                    if crab:
                        extra['axis'] = accqa.CRAB_AXIS[v] + t
                elif kind == 'touching' and kinds[i] == 'star':
                    others = [x for j, x in enumerate(drawn) if j != i and x.any()]
                    m = _onto(m, np.any(others, 0), TOUCH) if others else m
                elif kind == 'star_under_crab' and kinds[i] == 'crab':
                    star = drawn[kinds.index('star')] if 'star' in kinds else None
                    m = _onto(m, star, MOVE_UNDER * ppl) if star is not None else m
                ms.append(m)
            # painted in order, the later over the earlier (the star over the crab), but the probe's crab over the star
            order = list(range(len(ms)))
            if kind == 'star_under_crab' and 'crab' in kinds:
                order.remove(kinds.index('crab')); order.append(kinds.index('crab'))
            lab = np.zeros(ms[0].shape, np.int64)
            for i in order:
                lab[ms[i]] = i + 1
            cache[(sname, v)] = (lab, ms, extra)
            return lab, ms, extra
        return labels

    def _face(self, kind, arg, kinds):
        """the FACE view's stand-in for ours: the clips-alone sheet's clips (design: redrawn at a slightly different scale
        and sub-pixel place; a floor: the crab spoiled one way) as face_labels -> (label image, None) or None."""
        from .. import accqa, limbs
        if kind not in ('design',) + self.face_floors:
            return None
        ms = []
        for k in kinds:
            m = self.alone.get(k)
            if m is None:
                ms.append(np.zeros((8, 8), bool))
                continue
            if kind == 'design':
                m = _resample(m, 1 + 0.015 * arg[0], (0.5 * arg[0], 0.5 * arg[1]))
            elif k == 'crab':
                m = limbs.spoil(m, kind)
            ms.append(m)
        return accqa.face_labels(ms), None

    def _arms(self, kind, arg):
        """acc_star_arms and acc_star_minor on a stand-in star (design: each view's drawn star, the worst; a floor: one
        face-on star) -> {check: dict}."""
        from .. import accessories as acc, accqa
        if kind == 'design':
            masks = []
            for D in (self.got[0].values() if self.got else ()):
                if D['graded']:
                    for dv in D['views'].values():
                        m = dv['masks'].get(accqa.PIECE['star'])
                        if m is not None and m.sum() >= accqa.MIN_PX:
                            masks.append(_roll(m, arg[0], arg[1]))
        elif kind == 'compass':
            masks = [self.alone['star']] if self.alone.get('star') is not None else []
        elif kind == 'four_point':
            sh = dict(next((a.get('shape') or {} for a in self.B.spec.get('accessories') or [] if a['kind'] == 'star'),
                           {}), minor=0.0)
            V, F = acc.star(sh)
            masks = [accqa.face_on(V, F, np.eye(3), ppl=240 / np.ptp(V[:, 1]))]
        else:
            return {}
        C = {}
        for m in masks:
            a = accqa.arms(m)
            if a is None:
                continue
            for key, name in (('side', 'arms'), ('minor', 'minor')):
                t, p, w = accqa.STAR_ARMS[key]
                d = round(a[key] - t, 3)
                st = 'PASS' if abs(d) <= p else 'WARN' if abs(d) <= w else 'FAIL'
                c = C.get('acc_star_%s' % name)
                if c is None or abs(d) > abs(c['value']):
                    C['acc_star_%s' % name] = {'value': d, 'status': st, 'ours': a[key]}
        return C

    def run(self, kind, arg):
        from .. import accqa
        C = {}
        if self.got and kind not in ('compass', 'four_point'):
            _, C, _ = accqa.evaluate(self.B, self.got[0], self.got[1], labels=self._labels(kind, arg),
                                     alone=self.alone or None)
        if kind in ('design', 'compass', 'four_point'):
            C.update(self._arms(kind, arg))
        return C
