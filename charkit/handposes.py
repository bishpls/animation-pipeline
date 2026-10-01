"""The hands' poses (tool/hands, docs/workstreams/hands.md): skeletal, not shape keys (Michael, 2026-09-30): a pose
turns the finger bones the hand template weights (charkit/code_hand.py), per hand, and poses blend. Round 6 (hands3)
uses them to validate the template's structure fitted to the hand sheet's open pose: each pose's angles fitted to the
sheet's cell per row (fit_pose) and graded (grade), the posing done by the template's own weights (linear blend
skinning), which exercises the finger joints ahead of the range-of-motion work. The `hands` expression component
(charkit.expressions) stays deferred (Michael, 2026-09-30).

A pose, per digit (index, middle, ring, little; thumb):
  curl     degrees each joint bends toward the palm: (MCP, PIP, DIP) for a finger, (CMC, MCP, IP) for the thumb; a
           number is the same at every joint
  spread   degrees the digit turns at its first joint about the back of the hand's normal, away from the middle finger
           (the index and the thumb toward the thumb's side, the ring and little finger toward the little finger's);
           negative closes the fan
  oppose   the thumb only: degrees its metacarpal turns about the hand's long axis, across the palm (opposition)
Angles are on top of the rest hand (the template's own curl and fan, fitted to the A-pose's drawn hands): `relaxed`
is the rest, the empty pose.

    from charkit import handposes as hp
    hp.pose('fist')                              # {digit: {curl, spread[, oppose]}}
    hp.pose({'fist': 0.5, 'open': 0.5})          # blended by weight (normalised)
    hp.blend('relaxed', 'point', 0.3)            # 30% of the way to point
    hp.posed(H, 'fist')                          # the template hand's rings posed (linear blend skinning, numpy)
    hp.rotations(H, 'fist')                      # {VRM bone: (3x3 rotation in the rest frame, about its head)}
    python -m charkit handposes fit|grade [--spec S] [--poses open,relaxed,fist,point] [--out DIR]

Pure Python but posed()/rotations()/grade() (numpy).
"""
import json, os, sys

from . import handqa

ROOT_ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DIGITS = ('thumb', 'index', 'middle', 'ring', 'little')
SPREAD_SIDE = dict(thumb=1.0, index=1.0, middle=0.0, ring=-1.0, little=-1.0)   # + toward the thumb's side (radial)

_Z = dict(curl=(0.0, 0.0, 0.0), spread=0.0)
# the template's poses: the hand sheet's four columns (relaxed, open, fist, point; charkit/refs/clawd/gen/
# hand_breakdown.png), as a hand bends: a fist curls the MCPs ~85, the PIPs ~95, the DIPs ~60, the thumb opposed across
# the curled index and middle; open straightens the rest's curl and fans the fingers; point keeps the index straight
POSES = {
    'relaxed': {},
    # (open: fitted to the hand sheet's open hand per row, round 6's poses1: curl -6.4, spread 11.5, the thumb's
    # spread 33, opposition 19, curl 12; handposes.from_knobs('open', ...))
    'open': dict(thumb=dict(curl=(4.8, 11.9, 13.7), spread=33.3, oppose=19.1),
                 index=dict(curl=-6.4, spread=11.5), middle=dict(curl=-6.4, spread=0.0),
                 ring=dict(curl=-6.4, spread=11.5), little=dict(curl=-6.4, spread=22.9)),
    'fist': dict(thumb=dict(curl=(15.0, 35.0, 40.0), spread=-10.0, oppose=55.0),
                 index=dict(curl=(85.0, 95.0, 60.0), spread=-2.0), middle=dict(curl=(85.0, 95.0, 60.0)),
                 ring=dict(curl=(85.0, 95.0, 60.0), spread=-2.0), little=dict(curl=(85.0, 95.0, 60.0), spread=-4.0)),
    'point': dict(thumb=dict(curl=(10.0, 30.0, 35.0), spread=-8.0, oppose=50.0),
                  index=dict(curl=-6.0, spread=2.0), middle=dict(curl=(85.0, 95.0, 60.0)),
                  ring=dict(curl=(85.0, 95.0, 60.0), spread=-2.0), little=dict(curl=(85.0, 95.0, 60.0), spread=-4.0)),
}


def _digit(d):
    """a digit's entry -> dict(curl (3,), spread, oppose)."""
    d = d or {}
    c = d.get('curl', 0.0)
    c = tuple(float(x) for x in c) if isinstance(c, (list, tuple)) else (float(c),) * 3
    return dict(curl=c, spread=float(d.get('spread', 0.0)), oppose=float(d.get('oppose', 0.0)))


def pose(P):
    """a pose by name (POSES), as given ({digit: {...}}), or a blend {name: weight, ...} (weights normalised; a name
    alone weighs 1) -> {digit: dict(curl, spread, oppose)} for every digit. None: the rest (relaxed)."""
    if P is None:
        P = 'relaxed'
    if isinstance(P, str):
        if P not in POSES:
            raise KeyError('hand pose %r: one of %s' % (P, ', '.join(sorted(POSES))))
        return {d: _digit(POSES[P].get(d)) for d in DIGITS}
    if P and all(k in POSES for k in P) and not any(k in DIGITS for k in P):
        tot = sum(float(w) for w in P.values()) or 1.0
        out = {d: dict(curl=(0.0, 0.0, 0.0), spread=0.0, oppose=0.0) for d in DIGITS}
        for name, w in P.items():
            for d, v in pose(name).items():
                k = float(w) / tot
                o = out[d]
                o['curl'] = tuple(a + k * b for a, b in zip(o['curl'], v['curl']))
                o['spread'] += k * v['spread']
                o['oppose'] += k * v['oppose']
        return out
    return {d: _digit(P.get(d)) for d in DIGITS}


def blend(a, b, t):
    """t of the way from pose a to pose b -> a pose."""
    A, B = pose(a), pose(b)
    return {d: dict(curl=tuple((1 - t) * x + t * y for x, y in zip(A[d]['curl'], B[d]['curl'])),
                    spread=(1 - t) * A[d]['spread'] + t * B[d]['spread'],
                    oppose=(1 - t) * A[d]['oppose'] + t * B[d]['oppose']) for d in DIGITS}


def per_hand(P):
    """a `hands` component value -> {'L': pose, 'R': pose}: a name or blend for both hands, or {'L': .., 'R': ..}."""
    if isinstance(P, dict) and set(P) <= {'L', 'R'} and P:
        return {s: pose(P.get(s)) for s in ('L', 'R')}
    return {s: pose(P) for s in ('L', 'R')}


# ------------------------------------------------------------------------------------------------------- the bones
def _transforms(H_, name, D):
    """a digit's bone transforms under a pose: [(R, t)] for (the Hand, bone 1, 2, 3), each x -> R x + t in the rest
    frame (the Hand's identity), composed down the chain about each joint where the chain so far has put it."""
    import numpy as np
    from .code_hand import _rot
    Jd, F, _ = H_['digits'][name]
    W0, R = H_['frame']
    T = [(np.eye(3), np.zeros(3))]
    Racc, tacc = np.eye(3), np.zeros(3)
    for k in range(3):
        p = Racc @ Jd[k] + tacc
        Fk = Racc @ F[k]
        Rk = _rot(np.cross(Fk[:, 0], -Fk[:, 2]), D['curl'][k])            # bend toward the palm
        if k == 0:
            side = SPREAD_SIDE[name]
            if side and D['spread']:
                # about the back's normal, the sense that takes the digit toward its side (radial + for the thumb's)
                tw = R[:, 1] * side
                Rk = _rot(np.cross(Fk[:, 0], tw), D['spread']) @ Rk
            if name == 'thumb' and D['oppose']:
                Rk = _rot(R[:, 0], D['oppose'] * (1.0 if H_['side'] == 'left' else -1.0)) @ Rk
        Racc, tacc = Rk @ Racc, Rk @ (tacc - p) + p
        T.append((Racc.copy(), tacc.copy()))
    return T


def posed(H_, P):
    """the template hand's rings posed (linear blend skinning with its own weights, numpy) -> {part: rings}."""
    import numpy as np
    from .code_hand import PARTS
    D = pose(P)
    out = {}
    for name in PARTS:
        rings, Wt, bones = H_['parts'][name]
        if name == 'palm':
            out[name] = rings
            continue
        T = _transforms(H_, name, D[name])
        Pp = rings.reshape(-1, 3)
        Wv = np.repeat(Wt, rings.shape[1], axis=0)
        Q = sum(Wv[:, i:i + 1] * (Pp @ T[i][0].T + T[i][1]) for i in range(4))
        out[name] = Q.reshape(rings.shape)
    return out


def rotations(H_, P):
    """each finger bone's rotation under a pose, in the rest frame relative to its parent's (the rig's local turn, before
    its roll is applied) -> {VRM bone: 3x3}."""
    import numpy as np
    from .code_hand import FINGERS, VRM, SEGS
    D = pose(P)
    s_ = H_['side']
    out = {}
    for name in ('thumb',) + FINGERS:
        T = _transforms(H_, name, D[name])
        segs = SEGS.get(name, ('Proximal', 'Intermediate', 'Distal'))
        for k, g in enumerate(segs):
            out['%s%s%s' % (s_, VRM[name], g)] = T[k + 1][0] @ T[k][0].T
    return out


# ------------------------------------------------------------------------------------------------- against the sheet
FIT = {        # each pose's angles for fit_pose: name -> [(knob, lo, hi)]; from_knobs makes the pose
    'open': [('curl', -20.0, 10.0), ('spread', 0.0, 30.0), ('t_spread', -10.0, 60.0), ('t_oppose', -40.0, 20.0),
             ('t_curl', -20.0, 20.0)],
    'relaxed': [('curl', -10.0, 30.0), ('spread', -6.0, 10.0), ('t_spread', -20.0, 30.0), ('t_oppose', -20.0, 40.0),
                ('t_curl', -10.0, 30.0)],
    'fist': [('mcp', 30.0, 100.0), ('pip', 40.0, 115.0), ('dip', 10.0, 80.0), ('t_oppose', 0.0, 80.0),
             ('t_curl', 0.0, 60.0), ('t_spread', -30.0, 10.0)],
    'point': [('i_curl', -15.0, 15.0), ('mcp', 30.0, 100.0), ('pip', 40.0, 115.0), ('dip', 10.0, 80.0),
              ('t_oppose', 0.0, 80.0), ('t_curl', 0.0, 60.0)],
}


def from_knobs(name, k):
    """a pose from its fit knobs (FIT[name]: a dict) -> {digit: {...}}."""
    fan = dict(index=1.0, ring=1.0, little=2.0)
    tc = k.get('t_curl', 0.0)
    thumb = dict(curl=(0.4 * tc, tc, 1.15 * tc), spread=k.get('t_spread', 0.0), oppose=k.get('t_oppose', 0.0))
    if name in ('open', 'relaxed'):
        P = {d: dict(curl=k['curl'], spread=k['spread'] * fan.get(d, 0.0)) for d in ('index', 'middle', 'ring', 'little')}
    else:
        c = (k['mcp'], k['pip'], k['dip'])
        P = {d: dict(curl=c, spread=-2.0 * fan.get(d, 0.0)) for d in ('index', 'middle', 'ring', 'little')}
        if name == 'point':
            P['index'] = dict(curl=k['i_curl'], spread=2.0)
    P['thumb'] = thumb
    return P


class PoseGrade:
    """our template hand (its rest: the spec's knobs) posed into the sheet's poses and graded per row against the sheet's
    cell (charkit.handsheet): the silhouettes' IoU, the tip count, the reach past the cuff. One scale per row for every
    pose: the one at which our hand posed open reaches as far as the sheet's open hand (proportions from the sheet, size
    from the turnaround), so a fist's shortening is graded too."""
    WEIGHT = 0.05

    def __init__(self, spec_path=None, open_pose=None, over=None, spec=None):
        import numpy as np
        from . import code_hand, handsheet
        if spec is None:
            spec = json.load(open(spec_path or os.path.join(ROOT_, 'charkit', 'spec', 'clawd.json')))
        self.P = code_hand.params(spec, **(over or {}))
        self.H = code_hand.hand(handsheet.CHAIN, 'left', self.P)
        self.S = handsheet.cells()
        self.D = {k: handsheet.digits(v) for k, v in self.S.items()}
        self.open_pose = open_pose or POSES['open']
        rings = posed(self.H, self.open_pose)
        self.ppl = {}
        for row in handsheet.ROW_AXES:
            h = handsheet.draw(self.H, row, 400.0, handsheet.CUFF_END, rings=rings, turn=handsheet.TURN[row])
            r = handqa.reach(h, h['ppl'])
            self.ppl[row] = self.D[('open', row)]['reach'] * self.S[('open', row)]['ppl'] / max(r, 1e-6)

    def ours(self, P, row):
        from . import handsheet
        h = handsheet.draw(self.H, row, self.ppl[row], handsheet.CUFF_END, rings=posed(self.H, P),
                           turn=handsheet.TURN[row])
        return h, handsheet.digits(h)

    def grade(self, name, P, row):
        """one pose in one row -> dict(iou, tips (ours, sheet), reach (ours, sheet: shares of the open hand's))."""
        h, Do = self.ours(P, row)
        cell = self.S[(name, row)]
        iou = handqa.shape_iou(cell['mask'], h['mask'])
        Ds = self.D[(name, row)]
        ro = Do['reach'] * h['ppl'] / (self.D[('open', row)]['reach'] * self.S[('open', row)]['ppl'])
        rs = Ds['reach'] / self.D[('open', row)]['reach']
        return dict(iou=round(iou, 4), tips=(len(Do['digits']), len(Ds['digits'])), reach=(round(ro, 3), round(rs, 3)))

    def cost(self, name, P):
        c, per = 0.0, {}
        for row in ('back', 'side'):
            g = self.grade(name, P, row)
            per[row] = g
            c += (1 - g['iou']) + self.WEIGHT * 2.0 * abs(g['tips'][0] - g['tips'][1]) + 2.0 * (g['reach'][0] - g['reach'][1]) ** 2
        return c / 2.0, per


def fit_pose(G, name, log=print, maxfev=400):
    """a pose's angles (FIT[name]) fitted to the sheet's cell per row (Powell within the bounds, from the middle of
    the box) -> (knobs, cost, per row)."""
    import numpy as np
    from scipy.optimize import minimize
    spec_ = FIT[name]
    to = lambda x: {k: float(np.clip(v, lo, hi)) for (k, lo, hi), v in zip(spec_, x)}
    f = lambda x: G.cost(name, from_knobs(name, to(x)))[0]
    best = None
    for start in (0.5, 0.25, 0.75):
        x0 = np.array([lo + start * (hi - lo) for _, lo, hi in spec_])
        res = minimize(f, x0, method='Powell', bounds=[(lo, hi) for _, lo, hi in spec_],
                       options=dict(maxfev=maxfev, xtol=0.5, ftol=1e-4))
        if best is None or res.fun < best.fun:
            best = res
    k = {kk: round(v, 2) for kk, v in to(best.x).items()}
    c, per = G.cost(name, from_knobs(name, k))
    log('%s: cost %.4f %s %s' % (name, c, json.dumps(per), json.dumps(k)))
    return k, c, per


def picture(G, poses, out):
    """per pose and row the sheet's hand (grey) and ours posed (red outline), on the centroids, the IoU above."""
    import numpy as np
    from PIL import Image, ImageDraw
    from scipy import ndimage
    tiles = []
    for name, P in poses.items():
        for row in ('back', 'side'):
            h, _ = G.ours(P, row)
            g = G.grade(name, P, row)
            A, Bm = handqa.aligned_pair(G.S[(name, row)]['mask'], h['mask'])
            img = np.full(A.shape + (3,), 255, np.uint8)
            img[A] = (190, 190, 190)
            img[ndimage.binary_dilation(Bm & ~ndimage.binary_erosion(Bm))] = (220, 30, 30)
            canvas = np.full((img.shape[0] + 30, max(img.shape[1], 200), 3), 255, np.uint8)
            canvas[30:, :img.shape[1]] = img
            im = Image.fromarray(canvas)
            ImageDraw.Draw(im).text((2, 2), '%s %s IoU %.3f tips %s/%s' % (name, row, g['iou'], *g['tips']), fill=(0, 0, 0))
            ImageDraw.Draw(im).text((2, 15), 'reach %.2f/%.2f of open' % g['reach'], fill=(0, 0, 0))
            tiles.append(np.asarray(im))
    H = max(t.shape[0] for t in tiles)
    row = np.concatenate([np.pad(t, ((0, H - t.shape[0]), (0, 10), (0, 0)), constant_values=255) for t in tiles], 1)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    Image.fromarray(row).save(out)
    return out


def main(args):
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    if not args or args[0] not in ('grade', 'fit'):
        print(__doc__)
        return 0
    names = (opt('--poses') or 'open,relaxed,fist,point').split(',')
    over = json.loads(opt('--over')) if opt('--over') else None
    out = opt('--out', os.path.join(ROOT_, 'charkit', 'out', 'hands3', 'poses'))
    G = PoseGrade(opt('--spec'), over=over)
    got = {}
    if args[0] == 'fit':
        if 'open' in names:                       # the open pose first: it sets the scale every pose is graded at
            k, c, per = fit_pose(G, 'open', log=lambda *a: print(*a, flush=True))
            got['open'] = dict(knobs=k, cost=round(c, 4), per=per)
            G = PoseGrade(opt('--spec'), open_pose=from_knobs('open', k), over=over)
        for n in names:
            if n == 'open':
                continue
            k, c, per = fit_pose(G, n, log=lambda *a: print(*a, flush=True))
            got[n] = dict(knobs=k, cost=round(c, 4), per=per)
        poses = {n: from_knobs(n, got[n]['knobs']) for n in got}
    else:
        poses = {n: POSES[n] for n in names}
        got = {n: {row: G.grade(n, poses[n], row) for row in ('back', 'side')} for n in names}
    os.makedirs(out, exist_ok=True)
    json.dump(got, open(os.path.join(out, 'poses.json'), 'w'), indent=1, default=str)
    print(json.dumps(got, indent=1, default=str))
    print(picture(G, poses, os.path.join(out, 'poses.png')))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
