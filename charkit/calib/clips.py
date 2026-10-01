"""Calibration adapter for the hair clips (charkit.accqa's 'accessories' part, tool/accessories5): its declared checks
(acc_KIND_VIEW_visible: the share of a clip that shows, Michael's non-occlusion rule) and the star's face-on proportions
(acc_star_arms, acc_star_minor). The stand-in for ours is the design's own clips (head_turnaround, accqa.design):
  design            each drawn clip standing for ours: its drawn mask is its own silhouette, and the other drawn clips
                    moved 1-2 px against it cover what they reach (the drawn clips touch along their shared outline:
                    the check must read two clips side by side as shown); the star's arms read on each view's drawn
                    star (its longer side arm: the other can be under the drawn crab)
  star_under_crab   (probe) the drawn crab moved 0.05 L onto the star's middle: a star a clip covers must read hidden
  compass           (floor) the clips-alone sheet's star (an equal-armed compass star: side arms 0.48 of its height)
                    as ours face-on: the arms check must fail it
  four_point        (floor) the star template without its minor points (the round-1 placeholder's structure) as ours
                    face-on: the minor check must fail it
Known-bad: acc_r4_overlap (pipeline-3d 00494de, round 4's placement: the star bent over the crab, the crab 62-78% shown).
"""
import numpy as np

CALIBRATION = [
    dict(check='acc_star_arms', part='accessories', adapter='Clips', known_bad=None,
         no_known_bad='no stored build has the compass star; the floor is the clips-alone sheet\'s',
         baseline=['compass'], shape=['acc_star_shape'], better='lower'),
    dict(check='acc_star_minor', part='accessories', adapter='Clips', known_bad=None,
         no_known_bad='the 4-point placeholder build is not stored; the floor is its structure',
         baseline=['four_point'], shape=['acc_star_shape'], better='lower'),
]
MOVE_UNDER = 0.05           # L: the probe's crab moved onto the star


class Clips:
    part = 'accessories'
    generators = {
        'star_under_crab': '(probe) the drawn crab moved 0.05 L onto the star in each view: the star partly covered',
        'compass': "(floor) the clips-alone sheet's star (side arms 0.48 of its height) as ours face-on",
        'four_point': '(floor) the star template without its minor points as ours face-on',
    }

    def __init__(self, B, design):
        from .. import accqa
        self.B, self.design = B, design
        got = design.clips()
        self.D = None
        if got:
            D, P = got
            self.D = next((d for d in D.values() if d['graded']), None)
        al = accqa.alone_clips(B.spec)
        self.alone = al[0] if al else {}
        self.objs = accqa.clip_objects(B)

    def _visible(self, kind, arg):
        """the declared checks on the drawn clips standing for ours -> {check: dict}."""
        from .. import accqa, declared
        if self.D is None:
            return {}
        names = ['-'] + [o.name for _, o in self.objs]
        pm = {accqa.PIECE[k]: [(o.name, None)] for k, o in self.objs if k in accqa.PIECE}
        I = dict(O={}, names=names, masks={}, alone={}, dv={}, pm=pm, ppl=self.D['ppl'])
        for v, dv in self.D['views'].items():
            ms = {k: dv['masks'].get(accqa.PIECE[k]) for k, _ in self.objs}
            if any(m is None for m in ms.values()):
                continue
            lab = np.zeros(next(iter(ms.values())).shape, np.int64)
            alone = {}
            for i, (k, o) in enumerate(self.objs):
                own = ms[k].copy()
                for k2, o2 in self.objs:
                    if k2 == k:
                        continue
                    other = ms[k2]
                    if kind == 'design':
                        other = np.roll(np.roll(other, arg[0], 0), arg[1], 1)
                    elif kind == 'star_under_crab' and k == 'star':
                        other = _onto(other, ms[k], MOVE_UNDER * self.D['ppl'])
                    own &= ~other
                lab[own] = i + 1
                alone[o.name] = ms[k]
                I['masks']['%s__%s' % (v, accqa.PIECE[k])] = ms[k]
            I['O'][v] = {'lab': lab}
            I['alone'][v] = alone
            I['dv'][v] = {}
        return declared.evaluate_part('accessories', I)[1]

    def _arms(self, kind, arg):
        """acc_star_arms and acc_star_minor on a stand-in star mask per view (design: each view's drawn star; a floor:
        one face-on star) -> {check: dict}: the worst view's."""
        from .. import accessories as acc, accqa
        if kind == 'design':
            if self.D is None:
                return {}
            masks = [np.roll(np.roll(dv['masks'].get(accqa.PIECE['star']), arg[0], 0), arg[1], 1)
                     for dv in self.D['views'].values() if dv['masks'].get(accqa.PIECE['star']) is not None
                     and dv['masks'][accqa.PIECE['star']].sum() >= accqa.MIN_PX]
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
        C = {}
        if kind in ('design', 'star_under_crab'):
            C.update(self._visible(kind, arg))
        if kind in ('design', 'compass', 'four_point'):
            C.update(self._arms(kind, arg))
        return C


def _onto(m, target, d):
    """mask m moved d px toward target's centroid."""
    from ..accqa import _centroid
    if not m.any() or not target.any():
        return m
    c0, c1 = _centroid(m), _centroid(target)
    v = c1 - c0
    v = v / max(1e-9, np.linalg.norm(v)) * d
    return np.roll(np.roll(m, int(round(v[0])), 0), int(round(v[1])), 1)
