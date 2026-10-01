"""The hair clips' fits (tool/accessories5, docs/workstreams/accessories5.md): charkit.accessories' star and crab built
from a few shape knobs fitted to the design's clips, then placed on a build's hair; every fit is scored as the QA
measures (charkit.accqa): each clip's shape IoU per view as the drawing shows it (accqa.as_drawn), and the placement's
size, position, visible share (Michael's non-occlusion rule), seat and back view.

The design (design()): head_turnaround's clips per view (accqa.design; the graded sheet) and the clips-alone drawings
(hair_clips_layers' bottom row, accqa.alone_clips: face-on and edge-on; the structure authority, layerrefs.md).

The template fit (fit_shape): one shape for every view and a pose per view (a turn about its up axis and a spin in its
plane: the turnaround draws each clip nearly face-on in every view, so a view's pose is its own), each view scored by
the as-drawn shape IoU (the other drawn clip's cover taken out of both), plus `w_alone` times the face-on IoU against
the clips-alone drawing (its structure where the turnaround hides it: the crab's right claw under the star), and for
the star W_ARMS times its tips' reach off the drawn star's (accqa.arms, accqa.STAR_ARMS: an IoU barely sees a tip).

The placement fit (fit_place): both clips' at / facing / tilt / size on a build's hair (its bundle: the hair they rest
on, everything else drawn once per view as what can cover them), the shapes fixed, by Nelder-Mead. The loss per clip
and view (front, three-quarter 1, profile 0.6: Michael's balance, 2026-09-30) is (1 - IoU) + 1.5 |log size| + 4 pos
(round 2's) + ANGLE_W a degree of its axis past ANGLE_OK off the drawn, plus the rules: VIS_W per unit of a clip's share hidden below VIS_MIN in a view the design draws it (pieces
don't hide each other), the star shown from behind past BACK_PX (+2 + px / 40), the seat beyond 0.004 L (x 20).

    python -m charkit accfit shape star|crab SPEC [--minutes M] [--out DIR] [--w-alone W]
    python -m charkit accfit place BUILD SPEC [--minutes M] [--out DIR] [--start JSON] [--plain W]
    python -m charkit accfit measure BUILD SPEC [--out DIR]        # the spec's clips placed and measured, a picture
    python -m charkit accfit measure BUILD SPEC --starts A.json,B.json   # several placements, the QA's and the plain measure
"""
import json, math, os, sys, time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWS = ('front', 'three_quarter', 'profile')
WEIGHT = {'front': 1.0, 'three_quarter': 1.0, 'profile': 0.6}     # Michael's balance between the front and the side
KINDS = ('crab', 'star')
W_ARMS = 2.0                          # the star fit's tip-reach term, per unit of arms() off the drawn star's
VIS_MIN, VIS_W = 0.985, 20.0          # the non-occlusion term: VIS_W per unit of share hidden below VIS_MIN
SEAT_TOL, SEAT_W = 0.004, 20.0
BACK_PX = 20                          # the star shown from behind past this many pixels costs (the QA fails it at 40)
PLAIN_W = 0.0                         # > 0: the gate's old measure (as_drawn off: the 2x2's old measure on the new
                                      # geometry) kept off FAIL, a hinge at its FAIL limits (angle 18 deg, iou 0.62,
                                      # size 0.23) times this (--plain W)
ANGLE_OK, ANGLE_W = 8.0, 0.05         # a clip's axis off the drawn past this many degrees costs ANGLE_W a degree (the QA
                                      # passes 10, warns 20: an IoU aligned on centroid and area barely sees a turn)
# the shape knobs each template fit moves, with their starting steps (the shape's own units: fractions of the star's
# height, of the crab's body width; degrees)
SHAPE_KNOBS = {
    'star': {'up': 0.03, 'down': 0.03, 'side': 0.04, 'minor': 0.04, 'inner': 0.02, 'curve': 0.03, 'minor_at': 6.0},
    'crab': {'body_h': 0.06, 'claw': 0.06, 'claw_at.0': 0.05, 'claw_at.1': 0.05, 'claw_up': 10.0, 'claw_notch': 10.0,
             'arm': 0.02, 'leg': 0.04, 'leg_r': 0.008, 'leg_span.0': 8.0, 'leg_span.1': 8.0, 'eye_at.0': 0.04,
             'eye_at.1': 0.04, 'eyes': 0.015},
}
BOUNDS = {'leg': (0.15, 0.6), 'claw': (0.2, 0.8), 'body_h': (0.5, 1.1), 'side': (0.2, 0.6), 'minor': (0.1, 0.45),
          'inner': (0.08, 0.3), 'curve': (0.0, 0.3), 'arm': (0.03, 0.2), 'leg_r': (0.015, 0.07), 'eyes': (0.03, 0.12)}


# ------------------------------------------------------------------------------------------------------------ design
def design(spec):
    """the design's clips -> dict(ppl, az3, views {view: {kind: mask}}, alone {kind, kind_edge: mask}, files)."""
    from . import accqa, eyes as eyelib
    from .bodymeasure import load_graph
    fs = spec['ref']['face_sheet']
    pieces = accqa.clip_pieces(load_graph(spec))
    from .layerref import _load
    D = accqa.design(_load(fs['image']), eyelib._knobs(spec.get('eyes'))['x'], pieces, 'head', fs.get('facing', -1))
    by = {v: k for k, v in accqa.PIECE.items()}
    out = dict(ppl=D['ppl'], az3=D['az3'], views={}, rgb={}, files=[fs['image']])
    for v, dv in D['views'].items():
        out['views'][v] = {by[p]: m for p, m in dv['masks'].items() if p in by}
        out['rgb'][v] = dv['rgb']
    al = accqa.alone_clips(spec)
    out['alone'] = al[0] if al else {}
    out['files'] += al[1] if al else []
    return out


def occluder(D, view, kind):
    """the drawing's other clips over this one in a view (their drawn masks), or None."""
    ms = [m for k, m in D['views'].get(view, {}).items() if k != kind and m is not None and m.any()]
    return np.any(ms, 0) if ms else None


# ------------------------------------------------------------------------------------------------------------ shapes
def get(shape, key):
    if '.' in key:
        k, i = key.split('.')
        return shape[k][int(i)]
    return shape[key]


def put(shape, key, v):
    if '.' in key:
        k, i = key.split('.')
        x = list(shape[k]); x[int(i)] = v; shape[k] = x
    else:
        shape[key] = v


def template(kind, shape):
    """a clip's local mesh (its back on z = 0, facing +z): the star's height 1, the crab's body 1 wide -> (V, F)."""
    from . import accessories as acc
    if kind == 'star':
        V, F = acc.star(dict(shape, rings=1))
        return V / max(1e-9, np.ptp(V[:, 1])), F
    V, F, _ = acc.crab(shape)
    return V, F


def posed(V, yaw=0.0, roll=0.0):
    """local verts turned yaw degrees about their up axis (y) and spun roll degrees in their plane (about z)."""
    a, b = math.radians(yaw), math.radians(roll)
    Ry = np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]])
    Rz = np.array([[math.cos(b), -math.sin(b), 0], [math.sin(b), math.cos(b), 0], [0, 0, 1]])
    return np.asarray(V, float) @ (Ry @ Rz).T


def silhouette(V, F, px=240):
    """local verts drawn along -z (face-on), about px across -> bool mask (orthographic; the QA's raster)."""
    from . import accqa
    ext = max(np.ptp(V[:, 0]), np.ptp(V[:, 1]))
    return accqa.face_on(V, F, np.eye(3), ppl=px / max(ext, 1e-9))


def score_shape(kind, shape, poses, D, w_alone=0.0, views=VIEWS, w_arms=W_ARMS):
    """a template's per-view as-drawn IoU (poses {view: (yaw, roll)}) and its face-on IoU against the clips-alone
    drawing -> dict(views {view: iou}, alone, loss)."""
    from . import accqa
    V, F = template(kind, shape)
    out = {'views': {}}
    loss = 0.0
    for v in views:
        md = D['views'].get(v, {}).get(kind)
        if md is None or md.sum() < accqa.MIN_PX:
            continue
        mo = silhouette(posed(V, *poses[v]), F)
        mo_d, cut = accqa.as_drawn(mo, md, occluder(D, v, kind), lw=2)
        iou = accqa.shape_iou(mo_d, md) or 0.0
        out['views'][v] = round(iou, 4)
        loss += WEIGHT[v] * (1 - iou)
    al = D.get('alone', {}).get(kind)
    face = silhouette(V, F)
    if al is not None:
        out['alone'] = round(accqa.shape_iou(face, al) or 0.0, 4)
        loss += w_alone * (1 - out['alone'])
    if kind == 'star' and w_arms:
        # the tips' reach (accqa.arms against the drawn star's own readings, accqa.STAR_ARMS): thin tips weigh little
        # in an IoU, so a fit to the silhouettes alone shortens them
        a = accqa.arms(face) or {}
        out['arms'] = {k: a.get(k) for k in ('side', 'minor')}
        loss += w_arms * sum(abs(a.get(k, 0.0) - accqa.STAR_ARMS[k][0]) for k in ('side', 'minor'))
    out['loss'] = round(loss, 5)
    return out


def _nm(f, x0, steps, minutes, log=print, every=50, tol=1e-5):
    """Nelder-Mead from an explicit simplex (real steps on every knob), restarted at its best until the time is up or
    a restart gains under tol -> (x, f(x), evaluations)."""
    t0, n_ev = time.time(), [0]
    x0 = np.asarray(x0, float)
    best = [x0, f(x0)]

    def g(x):
        n_ev[0] += 1
        y = f(x)
        if y < best[1]:
            best[0], best[1] = x.copy(), y
        if n_ev[0] % every == 0:
            log('  %5d evals %6.1f s  best %.5f' % (n_ev[0], time.time() - t0, best[1]))
        return y
    while time.time() - t0 < minutes * 60:
        start = best[1]
        n = len(x0)
        S = [best[0].copy()] + [best[0] + np.eye(n)[i] * steps[i] for i in range(n)]
        Y = [g(s) for s in S]
        for _ in range(200 * n):
            if time.time() - t0 > minutes * 60:
                break
            o = np.argsort(Y); S = [S[i] for i in o]; Y = [Y[i] for i in o]
            if abs(Y[-1] - Y[0]) < tol * 0.1:
                break
            c = np.mean(S[:-1], 0)
            xr = c + (c - S[-1]); yr = g(xr)
            if yr < Y[0]:
                xe = c + 2 * (c - S[-1]); ye = g(xe)
                S[-1], Y[-1] = (xe, ye) if ye < yr else (xr, yr)
            elif yr < Y[-2]:
                S[-1], Y[-1] = xr, yr
            else:
                xc = c + 0.5 * (S[-1] - c) if yr >= Y[-1] else c + 0.5 * (xr - c)
                yc = g(xc)
                if yc < min(yr, Y[-1]):
                    S[-1], Y[-1] = xc, yc
                else:
                    for i in range(1, len(S)):
                        S[i] = S[0] + 0.5 * (S[i] - S[0]); Y[i] = g(S[i])
        steps = np.asarray(steps, float) * 0.5
        if start - best[1] < tol:
            break
    return best[0], best[1], n_ev[0]


def fit_shape(kind, D, shape0, minutes=10.0, w_alone=0.25, log=print):
    """the template's shape knobs (SHAPE_KNOBS) and each view's pose fitted -> dict(shape, poses, score)."""
    knobs = list(SHAPE_KNOBS[kind])
    views = [v for v in VIEWS if D['views'].get(v, {}).get(kind) is not None]
    shape0 = dict(shape0)
    from . import accessories as acc
    full = dict(acc.STAR if kind == 'star' else acc.CRAB, **shape0)
    x0 = [get(full, k) for k in knobs] + [0.0] * (2 * len(views))
    steps = [SHAPE_KNOBS[kind][k] for k in knobs] + [12.0, 8.0] * len(views)

    def unpack(x):
        s = dict(full)
        for k, v in zip(knobs, x):
            lo, hi = BOUNDS.get(k.split('.')[0], (-1e9, 1e9))
            put(s, k, float(np.clip(v, lo, hi)))
        poses = {v: (float(x[len(knobs) + 2 * i]), float(x[len(knobs) + 2 * i + 1])) for i, v in enumerate(views)}
        return s, poses

    def f(x):
        s, p = unpack(x)
        return score_shape(kind, s, p, D, w_alone, views)['loss']
    log('%s: start %s' % (kind, json.dumps(score_shape(kind, *unpack(x0), D, w_alone, views))))
    x, y, n = _nm(f, x0, steps, minutes, log)
    s, p = unpack(x)
    sc = score_shape(kind, s, p, D, w_alone, views)
    log('%s: %d evaluations, %s' % (kind, n, json.dumps(sc)))
    return dict(shape={k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()},
                poses={v: [round(a, 2), round(b, 2)] for v, (a, b) in p.items()}, score=sc, evaluations=n)


# ------------------------------------------------------------------------------------------------------------ the scene
class Scene:
    """a build's scene for placing its clips: the hair they rest on (accessories.Ground, its BVHs built once), and per
    view everything else z-buffered once (depth and object), on accqa's window at the design's scale."""

    def __init__(self, build, D, views=VIEWS + ('back',)):
        from . import accessories as acc, accqa, qa3d
        from .calibrate import load_bundle
        from .faceqa import zbuffer
        B = load_bundle(build)
        self.B, self.D = B, D
        As = B.assembly
        self.L, self.centre = float(As['L']), np.asarray(As['centre'], float)
        iris = np.array(qa3d.iris_centres(B))
        clip_names = {o.name for _, o in accqa.clip_objects(B)}
        meshes, objn = qa3d.scene_objects(B)
        occ = [(V, T, np.full(len(T), 1000 + i, np.int64)) for i, ((V, T, _), n) in enumerate(zip(meshes, objn))
               if n not in clip_names]
        self.objn = list(objn)
        self.ppl = D['ppl']
        a3 = D['az3']
        self.az = {'front': 0.0, 'three_quarter': a3, 'profile': 90.0, 'back': 180.0}
        self.org, self.depth, self.lab = {}, {}, {}
        for v in views:
            self.org[v] = accqa.origin(v, self.az[v], iris, self.centre)
            self.depth[v], self.lab[v] = zbuffer(occ, self.az[v], self.org[v], self.L, 1.0 / self.ppl, accqa.WIN)
        self.hair = [o.mesh('eval')[:2] for o in B.objects(groups=('hair',)) if o.has('eval')]
        self.ground = acc.Ground([(V, [tuple(t) for t in T]) for V, T in self.hair])
        self.spec_acc = [a for a in (B.spec.get('accessories') or []) if a['kind'] in KINDS]

    def place(self, specs):
        """the clips placed as the build places them (accessories.generate on the hair) -> [(kind, V, F, spec)]."""
        from . import accessories as acc
        got = acc.generate(None, self.L, specs, ground=self.ground, centre=self.centre)
        return [(s['kind'], v, f, s) for _, v, f, s in got]

    def draw(self, clips, view):
        """the clips z-buffered in a view against the scene -> (shown {i: mask}, alone {i: mask}, covered_by {i: {name:
        px}})."""
        from . import accqa
        from .faceqa import zbuffer
        ms = [(np.asarray(V, float), accqa._tris(F), np.full(len(accqa._tris(F)), i + 1, np.int64))
              for i, (_, V, F, _) in enumerate(clips)]
        d, lab = zbuffer(ms, self.az[view], self.org[view], self.L, 1.0 / self.ppl, accqa.WIN)
        H, W = d.shape
        front = d < self.depth[view][:H, :W]
        shown, alone, by = {}, {}, {}
        for i, m in enumerate(ms):
            da, la = zbuffer([m], self.az[view], self.org[view], self.L, 1.0 / self.ppl, accqa.WIN)
            alone[i] = la > 0
            shown[i] = (lab == i + 1) & front
            hid = alone[i] & ~shown[i]
            cov = {}
            if hid.any():
                other = hid & (lab > 0) & (lab != i + 1) & front
                for j in np.unique(lab[other]):
                    cov[clips[j - 1][0]] = int((other & (lab == j)).sum())
                rest = hid & ~other
                ids, n = np.unique(self.lab[view][:H, :W][rest], return_counts=True)
                for k, c in zip(ids, n):
                    name = self.objn[k - 1000] if k >= 1000 else 'none'
                    cov[name] = cov.get(name, 0) + int(c)
            by[i] = dict(sorted(cov.items(), key=lambda t: -t[1]))
        return shown, alone, by

    def seat(self, V, L=None):
        """the least of a clip's vertices' heights over the hair under them along its thin axis (accqa.seat's gap), L."""
        from . import accqa
        n = accqa.clip_axes(V, self.centre)[:, 2]
        R = 0.6 * self.L
        t = self.ground.copy(len(self.hair)).cast(np.asarray(V) + n * R, np.repeat(-n[None], len(V), 0), 2 * R)
        ok = np.isfinite(t)
        return float((t[ok] - R).min()) / self.L if ok.any() else None

    def measure(self, specs, detail=False):
        """the clips placed and measured as the QA does -> dict per kind: views {view: iou, size, pos, visible,
        covered_by}, back px, seat; and the loss."""
        from . import accqa
        clips = self.place(specs)
        res, loss = {}, 0.0
        for i, (kind, V, F, s) in enumerate(clips):
            res[kind] = dict(views={}, seat=None, back=0, conform_lift=s.get('conform_lift'))
        for v in VIEWS + ('back',):
            if v not in self.depth:
                continue
            shown, alone, by = self.draw(clips, v)
            for i, (kind, V, F, s) in enumerate(clips):
                md = self.D['views'].get(v, {}).get(kind)
                mo = shown[i]
                H_, W_ = mo.shape
                if v == 'back':
                    res[kind]['back'] = int(mo.sum())
                    continue
                if md is None or md.sum() < accqa.MIN_PX:
                    continue
                md = md[:H_, :W_]
                occ = occluder(self.D, v, kind)
                C, O, Dm = accqa.compare(mo, md, self.ppl, kind, v, occ=occ[:H_, :W_] if occ is not None else None)
                tag = 'acc_%s_%s_' % (kind, v)
                vis = float(mo.sum()) / max(1, alone[i].sum())
                r = dict(iou=C.get(tag + 'iou', {}).get('value', 0.0), size=C.get(tag + 'size', {}).get('value'),
                         pos=C.get(tag + 'pos', {}).get('value'), angle=C.get(tag + 'angle', {}).get('value'),
                         visible=round(vis, 4), covered_by=by[i], px=int(mo.sum()))
                if detail:
                    r['checks'] = C
                res[kind]['views'][v] = r
                w = WEIGHT[v]
                iou = r['iou'] or 0.0
                sz = r['size'] or 1e-3
                loss += w * ((1 - iou) + 1.5 * abs(math.log(max(sz, 1e-3))) + 4 * (r['pos'] or 1.0))
                loss += VIS_W * max(0.0, VIS_MIN - vis)
                ang = C.get(tag + 'angle', {})
                if ang.get('status') not in (None, 'INFO') and r['angle'] is not None:
                    loss += w * ANGLE_W * max(0.0, abs(r['angle']) - ANGLE_OK)
                if PLAIN_W:
                    P_, _, _ = accqa.compare(mo, md, self.ppl, kind, v)
                    pa, pi, ps = P_.get(tag + 'angle', {}), P_.get(tag + 'iou', {}), P_.get(tag + 'size', {})
                    r['plain'] = dict(iou=pi.get('value'), size=ps.get('value'), angle=pa.get('value'))
                    if pa.get('status') not in (None, 'INFO') and pa.get('value') is not None:
                        loss += PLAIN_W * 0.1 * max(0.0, abs(pa['value']) - 18.0)
                    if pi.get('value') is not None:
                        loss += PLAIN_W * 5 * max(0.0, 0.62 - pi['value'])
                    if ps.get('value') is not None:
                        loss += PLAIN_W * 5 * max(0.0, abs(ps['value'] - 1) - 0.23)
        for i, (kind, V, F, s) in enumerate(clips):
            g = self.seat(V)
            res[kind]['seat'] = None if g is None else round(g, 4)
            if g is not None:
                loss += SEAT_W * max(0.0, abs(g) - SEAT_TOL)
            if res[kind]['back'] > BACK_PX:
                loss += 2 + res[kind]['back'] / 40.0
        res['loss'] = round(loss, 5)
        if detail:
            res['clips'] = clips
        return res


# the placement's knobs per clip: at (3, L), facing (az, el degrees), tilt (degrees), size (log), with their steps
PLACE_KNOBS = (('at.0', 0.03), ('at.1', 0.03), ('at.2', 0.03), ('facing.0', 8.0), ('facing.1', 6.0), ('tilt', 8.0),
               ('size', 0.03))


def fit_place(S, specs, minutes=30.0, kinds=KINDS, log=print):
    """both clips' placements fitted on the scene S (the shapes fixed) -> dict(specs, result)."""
    specs = [dict(s) for s in specs]
    idx = {s['kind']: i for i, s in enumerate(specs)}
    keys = [(k, kn, st) for k in kinds for kn, st in PLACE_KNOBS]

    def unpack(x):
        out = [dict(s) for s in specs]
        for (k, kn, _), v in zip(keys, x):
            s = out[idx[k]]
            if kn == 'size':
                s['size'] = float(specs[idx[k]]['size'] * math.exp(v))
            elif '.' in kn:
                a, j = kn.split('.')
                lst = list(s[a]); lst[int(j)] = float(v); s[a] = lst
            else:
                s[kn] = float(v)
        return out

    def val(k, kn):
        s = specs[idx[k]]
        if kn == 'size':
            return 0.0
        if '.' in kn:
            a, j = kn.split('.')
            return float(s[a][int(j)])
        return float(s.get(kn, 0.0))
    x0 = [val(k, kn) for k, kn, _ in keys]
    steps = [st for _, _, st in keys]
    r0 = S.measure(specs)
    log('place: start loss %.4f %s' % (r0['loss'], _brief(r0)))
    x, y, n = _nm(lambda x: S.measure(unpack(x))['loss'], x0, steps, minutes, log, every=25)
    out = unpack(x)
    r = S.measure(out)
    log('place: %d evaluations, loss %.4f %s' % (n, r['loss'], _brief(r)))
    return dict(specs=out, result=r, start=r0, evaluations=n)


def _brief(r):
    out = {}
    for k in KINDS:
        if k in r:
            out[k] = {v: [x['iou'], x['visible'], x['pos']] for v, x in r[k]['views'].items()}
            out[k]['back'] = r[k]['back']; out[k]['seat'] = r[k]['seat']
    return json.dumps(out)


def clean(r):
    """a measure() result without its meshes, for JSON."""
    return {k: v for k, v in r.items() if k != 'clips'}


# ------------------------------------------------------------------------------------------------------------ picture
def picture(S, specs, scale=2, pad=0.08):
    """per view: the drawing, ours (the clips over the scene's grey: crab red, star yellow, what covers them dark) and
    the silhouettes as the QA draws them -> image (H, W, 3)."""
    from . import accqa
    clips = S.place(specs)
    pics = {}
    for v in VIEWS + ('back',):
        if v not in S.depth:
            continue
        shown, alone, _ = S.draw(clips, v)
        H_, W_ = shown[0].shape
        lab = np.zeros((H_, W_), np.int64)
        for i in shown:
            lab[shown[i]] = i + 1
        rgb = S.D['rgb'].get(v)
        if rgb is None:
            continue
        masks = {accqa.PIECE[k]: m[:H_, :W_] for k, m in S.D['views'].get(v, {}).items()}
        pics[v] = (rgb[:H_, :W_], masks, lab, [k for k, _, _, _ in clips])
    return accqa.picture(pics, S.ppl, lambda k: accqa.PIECE.get(k, k), scale)


def shape_picture(kind, shape, poses, D, S=96):
    """a template fit's picture: per view (and the clips-alone drawing face-on) ours aligned on the drawn clip as the
    QA aligns it (accqa.normalised: centroid and area, the drawing's cover taken out of ours: as_drawn), grey where both
    are, blue the drawing only, red ours only, the cover dark -> image."""
    from . import accqa
    V, F = template(kind, shape)
    tiles = []
    items = [(v, posed(V, *poses[v]), D['views'].get(v, {}).get(kind), occluder(D, v, kind)) for v in VIEWS
             if v in poses and D['views'].get(v, {}).get(kind) is not None]
    if D.get('alone', {}).get(kind) is not None:
        items.append(('alone', V, D['alone'][kind], None))
    for v, Vp, md, occ in items:
        mo = silhouette(Vp, F)
        mo_d, _ = accqa.as_drawn(mo, md, occ, lw=2) if occ is not None else (mo, 0.0)
        # both on the drawn clip's normalised frame: ours scaled to its area, the cover moved alike
        A, B_ = accqa.normalised(mo_d, S), accqa.normalised(md, S)
        im = np.full(A.shape + (3,), 0.97)
        if occ is not None:
            from scipy import ndimage
            ys, xs = np.nonzero(md)
            k = np.sqrt(len(ys)) / S
            N = A.shape[0]
            yy, xx = np.mgrid[0:N, 0:N]
            cov = ndimage.map_coordinates(occ.astype(float), [ys.mean() + (yy + 0.5 - N / 2) * k - 0.5,
                                                               xs.mean() + (xx + 0.5 - N / 2) * k - 0.5], order=0) > 0.5
            im[cov] = (0.35, 0.33, 0.3)
        im[A & B_] = (0.55, 0.55, 0.6); im[B_ & ~A] = (0.3, 0.45, 0.95); im[A & ~B_] = (0.92, 0.3, 0.3)
        tiles.append(np.pad(im, ((4, 4), (4, 4), (0, 0)), constant_values=1.0))
    return np.concatenate(tiles, 1) if tiles else None


# ------------------------------------------------------------------------------------------------------------ the CLI
def _spec(path):
    from . import manifest
    return manifest.resolve(json.load(open(path if os.path.isabs(path) else os.path.join(ROOT, path))))


def _save(path, im):
    from PIL import Image
    Image.fromarray((np.clip(im, 0, 1) * 255).astype(np.uint8)).save(path)


def main(args):
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    cmd = args[0]
    out = opt('--out', os.path.join(ROOT, 'charkit', 'out', 'accfit'))
    os.makedirs(out, exist_ok=True)
    if cmd == 'shape':
        kind, spec = args[1], _spec(args[2])
        D = design(spec)
        s0 = next((a.get('shape') or {} for a in spec.get('accessories') or [] if a['kind'] == kind), {})
        if opt('--start'):
            s0 = json.load(open(opt('--start')))['shape']
        r = fit_shape(kind, D, s0, float(opt('--minutes', 10)), float(opt('--w-alone', 0.25)))
        json.dump(r, open(os.path.join(out, 'shape_%s.json' % kind), 'w'), indent=1)
        print(os.path.join(out, 'shape_%s.json' % kind))
    elif cmd == 'measure' and opt('--starts'):
        # several placements measured on one scene, each under the QA's measure and the plain one (as_drawn off: the
        # old measure, the gate's 2x2) -> OUT/measure_NAME.{json,png}
        from . import accqa
        build, spec = args[1], _spec(args[2])
        S = Scene(build, design(spec))
        plain = lambda mo, md, occ, lw=2, it=10: (mo, 0.0)
        for path in opt('--starts').split(','):
            name = os.path.splitext(os.path.basename(path))[0]
            specs = json.load(open(path))['specs']
            r = S.measure(specs)
            keep, accqa.as_drawn = accqa.as_drawn, plain
            try:
                r0 = S.measure(specs)
            finally:
                accqa.as_drawn = keep
            json.dump(dict(specs=specs, result=clean(r), plain=clean(r0)),
                      open(os.path.join(out, 'measure_%s.json' % name), 'w'), indent=1)
            _save(os.path.join(out, 'measure_%s.png' % name), picture(S, specs))
            print(name, r['loss'], _brief(r), 'plain', _brief(r0))
    elif cmd in ('place', 'measure'):
        build, spec = args[1], _spec(args[2])
        D = design(spec)
        S = Scene(build, D)
        specs = [a for a in spec.get('accessories') or [] if a['kind'] in KINDS]
        if opt('--start'):
            specs = json.load(open(opt('--start')))['specs']
        if cmd == 'place':
            global PLAIN_W
            PLAIN_W = float(opt('--plain', PLAIN_W))
            r = fit_place(S, specs, float(opt('--minutes', 30)))
            json.dump(dict(specs=r['specs'], result=clean(r['result']), start=clean(r['start']),
                           evaluations=r['evaluations']), open(os.path.join(out, 'place.json'), 'w'), indent=1)
            specs = r['specs']
        r = S.measure(specs)
        json.dump(dict(specs=specs, result=clean(r)), open(os.path.join(out, 'measure.json'), 'w'), indent=1)
        _save(os.path.join(out, 'measure.png'), picture(S, specs))
        print(json.dumps(clean(r), indent=1))
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
