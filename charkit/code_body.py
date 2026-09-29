"""The authored body, fitted to the visual hull (docs/workstreams/body.md): the body as the design's inner envelope,
where the drawings show skin or a tight garment, and bounded by the hull's envelope everywhere else, so no part of it
stands out of the design (a piece lying on it would be buried). Built in the hull's own frame (L, eye line z = 0,
x toward her left, -y toward the viewer), aligned to the build by the eyes as the hull is.

The torso: a radius field round a vertical axis (charkit.geom.loft) from the neck cut down to the hips. Rows the hull
shows (the lower bodice, the waistband, bare skin) are measured, each piece pulled in by its thickness; rows it hides
(the chest under the bow and collar, the hips under the skirt) are interpolated per angle between the measured rows
and the anchors (the neck ring; the hips from the graph skeleton's leg joints and the thighs' radius), then held
inside the hull's torso envelope less a clearance.

    the measures and the review page: charkit.bodypage (python -m charkit.bodypage SPEC), kept apart so a build stage
    importing this module doesn't depend on the QA (charkit.cache's code closure)
"""
import json, os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUT = -0.52                      # L: the neck cut (code_base.CUT)
TIGHT = {'top': 0.022, 'waistband': 0.035, 'skin': 0.0}     # L: what the body sits under, by the piece's thickness
CLEAR = 0.012                    # L: the body stays this far inside the hull's envelope where nothing measures it
ENVELOPE_SKIP = ('bow', 'bow_tail_L', 'bow_tail_R', 'collar')   # pieces in front of the chest, not bounding the torso
IN_FRONT = {'bow': 0.08, 'bow_tail_L': 0.04, 'bow_tail_R': 0.04}
# L: a piece that stands in front of the body, and how deep it is: the torso stays behind its surface less that depth
# where the piece shows (the chest behind the bow: a torso reaching its surface leaves the bow inside the top). The
# design's bow and tails lie flat, 0.02-0.06 L proud of the chest (measured on the hull); the collar lies on the skin
CROTCH = 0.08                    # L: the torso ends this far under the hip joints
NECK_R = 0.13                    # L: the neck's radius at the cut when the hull shows too little of it
ARM_R = 0.22                     # L: hull points this close to an arm's bone (in the front view) are the arm's
TORSO_SKIN_X = 0.45              # L: bare skin within this of the midline, above the arms' reach, is the torso's


class Hull:
    """the hull's mesh and per-vertex pieces in its own frame (charkit.geom.hull's outputs) -> .V, .piece (labels),
    .names {id: label}, .ids {name: label}."""

    def __init__(self, hull_dir):
        from .geom import io as gio
        J = json.load(open(os.path.join(hull_dir, 'hull.glb.json')))
        self.V = np.asarray(gio.load(os.path.join(hull_dir, 'hull.ply')).V, float)
        self.piece = np.load(os.path.join(hull_dir, J['pieces']))
        self.names = {int(k): v for k, v in J['piece_names'].items()}
        self.ids = {v: k for k, v in self.names.items()}
        self.eyes = J['eyes']

    def points(self, name):
        k = self.ids.get(name)
        return self.V[self.piece == k] if k is not None else np.zeros((0, 3))


def skeleton(graph):
    """the outfit graph's skeleton: {bone: ((x0, z0), (x1, z1))} in the front view, L from the eye line."""
    return {b: (tuple(s[0]), tuple(s[1])) for b, s in (graph.get('skeleton') or {}).items()}


def _seg_dist(P, a, b):
    """the front-view (x, z) distance of points to a segment."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    q = P[:, [0, 2]] - a
    d = b - a
    t = np.clip(q @ d / max(1e-12, d @ d), 0, 1)
    return np.linalg.norm(q - t[:, None] * d, axis=1)


def arm_mask(P, sk):
    """points near an arm's bones (upper arm, forearm, hand) in the front view."""
    m = np.zeros(len(P), bool)
    for side in ('left', 'right'):
        for b in ('UpperArm', 'LowerArm', 'Hand'):
            s = sk.get(side + b)
            if s:
                m |= _seg_dist(P, *s) < ARM_R
    return m


def section_r(p, th, ay, M=512):
    """a superellipse section's radius from the axis (at y = ay) toward angles th: p = (a half-width, bf front depth,
    bb back depth from its centre, n exponent, cy its centre's y); the front toward -y."""
    a, bf, bb, n, cy = p
    phi = np.linspace(-np.pi, np.pi, M, endpoint=False)
    s_, c_ = np.sin(phi), np.cos(phi)
    x = a * np.sign(s_) * np.abs(s_) ** (2.0 / n)
    y = cy - np.where(c_ > 0, bf, bb) * np.sign(c_) * np.abs(c_) ** (2.0 / n)
    tq = np.arctan2(x, -(y - ay))
    rq = np.hypot(x, y - ay)
    o = np.argsort(tq)
    return np.interp(th, tq[o], rq[o], period=2 * np.pi)


PRIOR = dict(depth=0.85, n=2.3)   # a torso section's front and back depths, as shares of its half-width, and exponent
W_SMOOTH = (6.0, 6.0, 6.0, 2.0, 6.0)   # second differences down the rows, per parameter (a, bf, bb, n, cy)
W_PRIOR = 0.25
W_ANCHOR = 20.0


def fit_sections(meas, Rc, th_c, ay, x0, anchors=(), depth=None, n=None, w_smooth=W_SMOOTH, w_centre=0.4):
    """every row's superellipse (section_r) at once: the measured cells (meas, Rc: rows x sectors at angles th_c) as
    data, the parameters smooth down the rows (second differences, w_smooth), held weakly (W_PRIOR) to front and back
    depths of `depth` times the half-width, an exponent n and a centre at ay (w_centre), and pinned by anchors
    [(row, parameter index, value)] (W_ANCHOR). One least-squares solve with a sparse Jacobian: a row's cells depend
    only on its own section. -> (rows, 5)."""
    from scipy.optimize import least_squares
    from scipy.sparse import lil_matrix
    depth = PRIOR['depth'] if depth is None else depth
    n = PRIOR['n'] if n is None else n
    nz = len(meas)
    rows = [np.nonzero(meas[k])[0] for k in range(nz)]
    X0 = np.array(x0, float).reshape(nz, 5)
    lo = np.tile([0.02, 0.02, 0.02, 1.8, ay - 0.6], nz)
    hi = np.tile([1.2, 1.2, 1.2, 4.0, ay + 0.6], nz)
    nd = sum(len(r) for r in rows)
    ns = 5 * (nz - 2)
    npr = 4 * nz
    anchors = list(anchors)

    def res(x):
        X = x.reshape(nz, 5)
        out = [section_r(X[k], th_c[rows[k]], ay) - Rc[k, rows[k]] for k in range(nz) if len(rows[k])]
        out.append(((X[2:] - 2 * X[1:-1] + X[:-2]) * np.array(w_smooth)).ravel())
        a = X[:, 0]
        out.append(W_PRIOR * np.r_[X[:, 1] / a - depth, X[:, 2] / a - depth, X[:, 3] - n, w_centre * (X[:, 4] - ay)])
        out.append(np.array([W_ANCHOR * (X[k, q] - v) for k, q, v in anchors]))
        return np.concatenate(out)
    J = lil_matrix((nd + ns + npr + len(anchors), 5 * nz), dtype=int)
    r0 = 0
    for k in range(nz):
        if len(rows[k]):
            J[r0:r0 + len(rows[k]), 5 * k:5 * k + 5] = 1
            r0 += len(rows[k])
    for k in range(nz - 2):
        for q in range(5):
            J[r0 + 5 * k + q, [5 * k + q, 5 * (k + 1) + q, 5 * (k + 2) + q]] = 1
    r0 += ns
    for q, col in enumerate((1, 2, 3, 4)):
        for k in range(nz):
            J[r0 + q * nz + k, 5 * k] = 1
            J[r0 + q * nz + k, 5 * k + col] = 1
    r0 += npr
    for i_, (k, q, v) in enumerate(anchors):
        J[r0 + i_, 5 * k + q] = 1
    sol = least_squares(res, np.clip(X0.ravel(), lo, hi), bounds=(lo, hi), jac_sparsity=J, x_scale='jac')
    return sol.x.reshape(nz, 5)


def _behind(H, ax, ts, th_c, nz, nth, grow=1, drawn=None):
    """per cell, how far out the torso may reach behind the pieces in front of it (IN_FRONT): the smallest radius of a
    piece's points in the cell less the piece's depth, spread `grow` cells round (inf where none). drawn: the pieces'
    drawn front extents {piece: (x0, z0, x1, z1) L}: only the points inside count (the hull labels some of the collar's
    lapels as bow, both cream, and the chest under them had been pulled in 0.07 L)."""
    B = np.full((nz, nth), np.inf)
    for name, depth in IN_FRONT.items():
        Q = H.points(name)
        if drawn and name in drawn and len(Q):
            x0, z0, x1, z1 = drawn[name]
            Q = Q[(Q[:, 0] >= x0) & (Q[:, 0] <= x1) & (Q[:, 2] >= z0) & (Q[:, 2] <= z1)]
        if not len(Q):
            continue
        t, th, r = ax.coords(Q)
        keep = (t >= ts[0] - 0.02) & (t <= ts[-1] + 0.02)
        ii = np.clip(np.rint(np.interp(t[keep], ts, np.arange(nz))).astype(int), 0, nz - 1)
        jj = np.clip(((th[keep] + np.pi) / (2 * np.pi) * nth).astype(int), 0, nth - 1)
        np.minimum.at(B, (ii, jj), r[keep] - depth)
    for _ in range(grow):
        B = np.minimum.reduce([B, np.roll(B, 1, 1), np.roll(B, -1, 1), np.r_[B[:1], B[:-1]], np.r_[B[1:], B[-1:]]])
    return B


def fit_torso(meas, Rc, th_c, ay, neck, hw=None, hy=None):
    """the torso's sections (fit_sections): its cut's row pinned to the neck ring, its bottom row to the hips' half-width
    and centre depth."""
    nz = len(meas)
    X0 = np.tile([0.33, 0.28, 0.28, PRIOR['n'], ay], (nz, 1))
    X0[0] = neck
    anchors = [(0, q, float(v)) for q, v in enumerate(neck)]
    if hw:
        anchors.append((nz - 1, 0, float(hw)))
    if hy is not None:
        anchors.append((nz - 1, 4, float(hy)))
    return fit_sections(meas, Rc, th_c, ay, X0, anchors)


def torso(H, sk, nz=56, nth=72, hip_z=None, drawn=None):
    """the torso: one superellipse section per row (section_r) between the neck cut and the crotch, round a vertical
    axis, all fitted at once (fit_torso) to the cells the hull measures (tight pieces pulled in by their thickness, bare
    skin as it is, mirrored across the midline), anchored at the neck ring and the hips, then held inside the hull's
    torso envelope less CLEAR at every angle.
    -> dict(ax, F (loft.Field over t = CUT - z), params (per row), rows, measured, env, src)."""
    from .geom import loft
    hips = sk.get('hips')
    z_bot = hip_z if hip_z is not None else (min(hips[0][1], hips[1][1]) - CROTCH if hips else -2.63)
    rows = np.linspace(CUT, z_bot, nz)
    ts = CUT - rows
    lab = H.piece
    # the envelope leaves out what stands in front of the body without shaping it: the hair, and the accessories on the
    # chest (the bow, its tails, the collar): under them the torso takes its fitted shape, not their outer surface (a
    # torso grown into the bow's space hides the bow behind the top)
    off = np.isin(lab, [H.ids[k] for k in ('hair',) + ENVELOPE_SKIP if k in H.ids])
    band = (H.V[:, 2] <= CUT + 0.02) & (H.V[:, 2] >= z_bot - 0.05)
    E = H.V[band & ~off]
    E = E[~arm_mask(E, sk)]
    src = []
    for name, dt in TIGHT.items():
        Q = H.points(name)
        if name == 'skin':
            Q = Q[(np.abs(Q[:, 0]) < TORSO_SKIN_X) & (Q[:, 2] <= CUT + 0.02) & (Q[:, 2] > -1.0)]
        Q = Q[~arm_mask(Q, sk)] if len(Q) else Q
        if len(Q):
            src.append((Q, dt))
    Pm = np.concatenate([q for q, _ in src])
    mid = Pm[(Pm[:, 2] < -1.0) & (Pm[:, 2] > -1.4)]
    c = np.median(mid if len(mid) > 20 else Pm, 0)
    ay = float(c[1])
    ax = loft.Axis((0.0, ay, CUT), (0, 0, -1), (0, -1, 0))
    t, th, r = [], [], []
    for Q, dt in src:
        a_, b_, c_ = ax.coords(Q)
        t.append(a_); th.append(b_); r.append(c_ - dt)
    t, th, r = np.concatenate(t), np.concatenate(th), np.concatenate(r)
    # mirror the measurements across the midline: the design is symmetric
    t, th, r = np.r_[t, t], np.r_[th, -th], np.r_[r, r]
    te, the, re = ax.coords(E)
    env = loft.field(te, the, re, ts, nth=nth, q=0.5, smooth=(1.0, 1.0), min_row=0.3)
    # the cells: per row and sector, the median measured radius
    ii = np.clip(np.rint(np.interp(t, ts, np.arange(nz))).astype(int), 0, nz - 1)
    jj = np.clip(((th + np.pi) / (2 * np.pi) * nth).astype(int), 0, nth - 1)
    th_c = -np.pi + (np.arange(nth) + 0.5) * 2 * np.pi / nth
    cells = {}
    for a_, b_, v_ in zip(ii, jj, r):
        cells.setdefault((a_, b_), []).append(v_)
    meas = np.zeros((nz, nth), bool)
    Rc = np.full((nz, nth), np.nan)
    for (a_, b_), vs in cells.items():
        meas[a_, b_] = True
        Rc[a_, b_] = np.median(vs)
    share = meas.mean(1)
    # the anchors: the neck ring at the cut (a circle as wide as its bare skin, set back from the skin's front by its
    # radius); the hips' half-width across at the bottom (the leg joints apart plus the thighs' radius where their skin
    # shows below the shorts)
    nk = H.points('skin')
    nk = nk[(np.abs(nk[:, 0]) < 0.25) & (nk[:, 2] <= CUT + 0.1) & (nk[:, 2] >= CUT - 0.03)]
    if len(nk) >= 5:
        rn = float(np.percentile(np.abs(nk[:, 0]), 95))
        yn = float(nk[:, 1].min()) + rn
    else:
        rn, yn = NECK_R, ay
    neck = np.array([rn, rn, rn, 2.0, yn])
    ll, rl = sk.get('leftUpperLeg'), sk.get('rightUpperLeg')
    hw = hy = None
    if ll and rl:
        thigh = H.points('skin')
        thigh = thigh[(thigh[:, 2] < z_bot - 0.1) & (thigh[:, 2] > z_bot - 0.4) & (np.abs(thigh[:, 0]) < 0.6)]
        tr = float(np.median(np.abs(np.abs(thigh[:, 0]) - abs(ll[0][0])))) if len(thigh) else 0.2
        hw = abs(ll[0][0] - rl[0][0]) / 2 + tr
        if len(thigh) > 20:                     # the thighs' centre depth: the middle of their front and back skin
            hy = float(0.5 * (np.percentile(thigh[:, 1], 5) + np.percentile(thigh[:, 1], 95)))
    Pi = fit_torso(meas, Rc, th_c, ay, neck, hw, hy)
    R = np.stack([section_r(Pi[k], th_c, ay) for k in range(nz)])
    R = np.minimum(R, env.R - CLEAR)
    R = np.minimum(R, _behind(H, ax, ts, th_c, nz, nth, drawn=drawn))
    return dict(ax=ax, F=loft.Field(ts, th_c, R, meas), params=Pi, rows=rows, measured=share, env=env, src=src)


LIMBS = {'leg': (('UpperLeg', 'LowerLeg'), {'skin': 0.0, 'boot': 0.016}, 0.32),
         'arm': (('UpperArm', 'LowerArm', 'Hand'), {'skin': 0.0, 'sleeve_cuff': 0.02, 'cuff': 0.03}, 0.24)}
# a limb: its bones in order, what measures it (by piece, with the pull-in; a side's pieces take the side's suffix), and
# how far (front view, L) from its bones a point may be to count as its


def _piece_names(kind, side):
    """a limb's measuring pieces with their pull-in, the side's own ('boot_L' for her left leg)."""
    suf = '_L' if side == 'left' else '_R'
    return {(k if k == 'skin' else k + suf): v for k, v in LIMBS[kind][1].items()}


class Chain:
    """a limb's bone chain in 3D: joints (n, 3) in order (hip, knee, ankle), each segment an axis (loft.Axis, front
    toward -y) and its arc length from the chain's start."""

    def __init__(self, joints):
        from .geom import loft
        self.J = np.asarray(joints, float)
        self.axes = [loft.Axis(a, b - a, (0, -1, 0)) for a, b in zip(self.J[:-1], self.J[1:])]
        self.len = np.linalg.norm(np.diff(self.J, axis=0), axis=1)
        self.s0 = np.r_[0.0, np.cumsum(self.len)[:-1]]
        self.total = float(self.len.sum())

    def coords(self, P):
        """points -> (s along the chain, theta round the nearest segment, r from it, segment index)."""
        best = None
        for k, ax in enumerate(self.axes):
            t, th, r = ax.coords(P)
            tc = np.clip(t, 0, self.len[k])
            d = np.hypot(r, t - tc)
            cand = (d, self.s0[k] + t, th, r, np.full(len(P), k))
            if best is None:
                best = cand
            else:
                m = d < best[0]
                best = tuple(np.where(m, c, b) for c, b in zip(cand, best))
        return best[1], best[2], best[3], best[4].astype(int)

    def point(self, s, th, r):
        """(s along the chain, theta, r) -> points, each on the segment holding s."""
        s = np.asarray(s, float)
        k = np.clip(np.searchsorted(self.s0, s, side='right') - 1, 0, len(self.axes) - 1)
        out = np.empty(s.shape + (3,))
        for q, ax in enumerate(self.axes):
            m = k == q
            if m.any():
                out[m] = ax.point(s[m] - self.s0[q], np.broadcast_to(th, s.shape)[m], np.broadcast_to(r, s.shape)[m])
        return out


def limb_joints(H, sk, side, kind, hy=None):
    """a limb's joints in 3D: the graph skeleton's front-view joints, each at the depth of the middle of the limb's
    points about it (their front and back), or hy (the hip, inside the skirt: the torso's hips' depth)."""
    bones = [side + b for b in LIMBS[kind][0]]
    pts2 = [sk[bones[0]][0]] + [sk[b][1] for b in bones]
    names = _piece_names(kind, side)
    P = np.concatenate([H.points(n) for n in names])
    ys = []
    for i, (x, z) in enumerate(pts2):
        near = P[(np.hypot(P[:, 0] - x, P[:, 2] - z) < 0.15)]
        if i == 0 and hy is not None:
            ys.append(hy)
        elif len(near) >= 10:
            ys.append(0.5 * (np.percentile(near[:, 1], 5) + np.percentile(near[:, 1], 95)))
        else:
            ys.append(np.nan)
    ys = np.array(ys, float)
    ok = np.isfinite(ys)
    if not ok.any():
        ys[:] = hy if hy is not None else 0.0
    else:
        # a joint whose depth nothing measured (a shoulder under its puff) takes its nearest measured neighbour's
        idx = np.arange(len(ys))
        ys = np.interp(idx, idx[ok], ys[ok])
    return np.array([(x, y, z) for (x, z), y in zip(pts2, ys)])


def limb(H, sk, side, kind, hy=None, step=0.04, nth=48):
    """a limb as sections along its bone chain (fit_sections, near-circular priors), from the points the design shows
    of it (bare skin as it is, a boot or cuff pulled in by its thickness), within reach of its bones in the front view.
    -> dict(chain, rows (s), params, measured, src)."""
    J = limb_joints(H, sk, side, kind, hy)
    ch = Chain(J)
    names = _piece_names(kind, side)
    reach = LIMBS[kind][2]
    bones = [side + b for b in LIMBS[kind][0]]
    src = []
    for n, dt in names.items():
        Q = H.points(n)
        if not len(Q):
            continue
        d = np.min([_seg_dist(Q, *sk[b]) for b in bones], axis=0)
        Q = Q[(d < reach) & (Q[:, 2] <= J[0, 2] + 0.02) & (Q[:, 2] >= J[-1, 2] - 0.02)]
        if len(Q):
            src.append((Q, dt))
    s_, th, r, seg = [], [], [], []
    for Q, dt in src:
        a, b, c, k = ch.coords(Q)
        s_.append(a); th.append(b); r.append(c - dt)
    s_, th, r = np.concatenate(s_), np.concatenate(th), np.concatenate(r)
    rows = np.linspace(0, ch.total, max(8, int(ch.total / step)))
    nz = len(rows)
    ii = np.clip(np.rint(np.interp(s_, rows, np.arange(nz))).astype(int), 0, nz - 1)
    jj = np.clip(((th + np.pi) / (2 * np.pi) * nth).astype(int), 0, nth - 1)
    th_c = -np.pi + (np.arange(nth) + 0.5) * 2 * np.pi / nth
    keep = (s_ >= -0.02) & (s_ <= ch.total + 0.02) & (r > 0)
    meas = np.zeros((nz, nth), bool)
    Rc = np.full((nz, nth), np.nan)
    cells = {}
    for a, b, v in zip(ii[keep], jj[keep], r[keep]):
        cells.setdefault((a, b), []).append(v)
    for (a, b), vs in cells.items():
        meas[a, b] = True
        Rc[a, b] = np.median(vs)
    r0 = float(np.median(r[keep])) if keep.any() else 0.12
    X0 = np.tile([r0, r0, r0, 2.0, 0.0], (nz, 1))
    P = fit_sections(meas, Rc, th_c, 0.0, X0, depth=1.0, n=2.0, w_centre=2.0)
    return dict(chain=ch, rows=rows, params=P, measured=meas.mean(1), src=src, th=th_c)


def _tube(P, nth, caps=(True, True)):
    """a grid of rings (rows, nth, 3) as triangles, capped at either end by a fan to the ring's centre -> (V, T)."""
    nr = len(P)
    V = [P.reshape(-1, 3)]
    T = []
    for i in range(nr - 1):
        for j in range(nth):
            a, b = i * nth + j, i * nth + (j + 1) % nth
            c, d = (i + 1) * nth + (j + 1) % nth, (i + 1) * nth + j
            T += [(a, b, c), (a, c, d)]
    n0 = nr * nth
    for end, ring in ((0, 0), (1, nr - 1)):
        if caps[end]:
            V.append(P[ring].mean(0)[None])
            cidx = n0
            n0 += 1
            for j in range(nth):
                a, b = ring * nth + j, ring * nth + (j + 1) % nth
                T.append((cidx, b, a) if end == 0 else (cidx, a, b))
    return np.concatenate(V), np.array(T)


def torso_mesh(T_):
    ax, F = T_['ax'], T_['F']
    TT, TH = np.meshgrid(F.ts, F.th, indexing='ij')
    return _tube(ax.point(TT, TH, F.R), len(F.th))


def limb_mesh(L_):
    ch, P, rows, th = L_['chain'], L_['params'], L_['rows'], L_['th']
    R = np.stack([section_r(P[k], th, 0.0) for k in range(len(rows))])
    S, TH = np.meshgrid(rows, th, indexing='ij')
    return _tube(ch.point(S, TH, R), len(th))


FOOT_PULL = 0.03                # L: the foot inside the boot's surface (the boot's thickness and its shoe's offset)


def foot(H, side, ankle, step=0.03, nth=48):
    """a foot as sections stacked from the ankle down to the sole round a vertical axis (fit_sections, a foot's
    proportions: longer than wide), from the boot's hull points below the ankle pulled in by FOOT_PULL. -> dict(axis,
    rows (z), params, th, front, back (the foot's y extent: the toes' end and the heel))."""
    from .geom import loft
    suf = '_L' if side == 'left' else '_R'
    Q = np.concatenate([H.points(n) for n in ('boot' + suf,) if len(H.points(n))])
    Q = Q[Q[:, 2] < ankle[2] - 0.02]
    if len(Q) < 50:
        raise ValueError('foot %s: %d boot points below the ankle' % (side, len(Q)))
    top, sole = ankle[2], float(Q[:, 2].min())
    c = np.median(Q, 0)
    ax = loft.Axis((c[0], c[1], top), (0, 0, -1), (0, -1, 0))
    t, th, r = ax.coords(Q)
    r = r - FOOT_PULL
    rows = np.linspace(0, top - sole - FOOT_PULL, max(6, int((top - sole) / step)))
    nz = len(rows)
    th_c = -np.pi + (np.arange(nth) + 0.5) * 2 * np.pi / nth
    ii = np.clip(np.rint(np.interp(t, rows, np.arange(nz))).astype(int), 0, nz - 1)
    jj = np.clip(((th + np.pi) / (2 * np.pi) * nth).astype(int), 0, nth - 1)
    meas = np.zeros((nz, nth), bool)
    Rc = np.full((nz, nth), np.nan)
    cells = {}
    for a, b, v in zip(ii, jj, r):
        cells.setdefault((a, b), []).append(v)
    for (a, b), vs in cells.items():
        meas[a, b] = True
        Rc[a, b] = np.median(vs)
    r0 = float(np.median(r))
    X0 = np.tile([0.6 * r0, r0, 0.6 * r0, 2.4, 0.0], (nz, 1))
    P = fit_sections(meas, Rc, th_c, 0.0, X0, depth=1.5, n=2.4, w_centre=0.2)
    return dict(axis=ax, rows=rows, params=P, th=th_c, front=float(Q[:, 1].min() + FOOT_PULL),
                back=float(Q[:, 1].max() - FOOT_PULL))


def body(H, sk, drawn=None):
    """the authored body's parts: the torso and the four limbs -> dict(torso, limbs {name: limb()}, meshes {name: (V, T)})."""
    T_ = torso(H, sk, drawn=drawn)
    hy = float(T_['params'][-1, 4])
    limbs = {'%s_%s' % (k, s_): limb(H, sk, s_, k, hy=hy if k == 'leg' else None)
             for k in ('leg', 'arm') for s_ in ('left', 'right')}
    feet = {'foot_' + s_: foot(H, s_, limbs['leg_' + s_]['chain'].J[-1]) for s_ in ('left', 'right')}
    meshes = {'torso': torso_mesh(T_)}
    meshes.update({n: limb_mesh(L_) for n, L_ in limbs.items()})
    meshes.update({n: foot_mesh(F_) for n, F_ in feet.items()})
    return dict(torso=T_, limbs=limbs, feet=feet, meshes=meshes)


def foot_rings(F_):
    """a foot's rings (rows, nth, 3) in the hull's frame."""
    R = np.stack([section_r(F_['params'][k], F_['th'], 0.0) for k in range(len(F_['rows']))])
    TT, TH = np.meshgrid(F_['rows'], F_['th'], indexing='ij')
    return F_['axis'].point(TT, TH, R)


def foot_mesh(F_):
    return _tube(foot_rings(F_), len(F_['th']))




# ------------------------------------------------------------------------------------------------ into the build
PARTS = ('torso', 'leg_left', 'leg_right', 'arm_left', 'arm_right', 'foot_left', 'foot_right')
UV_SLOTS = {'torso': (0.0, 0.0, 0.25, 1.0), 'leg_left': (0.25, 0.2, 0.33, 1.0), 'leg_right': (0.33, 0.2, 0.41, 1.0),
            'arm_left': (0.41, 0.2, 0.46, 1.0), 'arm_right': (0.46, 0.2, 0.5, 1.0),
            'foot_left': (0.25, 0.0, 0.375, 0.2), 'foot_right': (0.375, 0.0, 0.5, 0.2)}
TOE_SHARE = 0.35                  # the front of the foot, as a share of its length, is the toes'
HEAD_UV_BOX = (0.5, 0.0, 1.0, 1.0)
BLEND = 0.06                      # L: a bone's weight eases into the next over this either side of their joint
TORSO_BONES = ('neck', 'upperChest', 'chest', 'spine', 'hips')     # top to bottom, by the graph skeleton's heights



def _blend(x, edges, n):
    """weights of n consecutive bones along x (increasing), bone i owning [edges[i-1], edges[i]], eased over BLEND
    either side of each edge -> (len(x), n)."""
    W = np.zeros((len(x), n))
    for i in range(n):
        lo = -np.inf if i == 0 else edges[i - 1]
        hi = np.inf if i == n - 1 else edges[i]
        a = np.clip((x - (lo - BLEND)) / (2 * BLEND), 0, 1) if np.isfinite(lo) else np.ones(len(x))
        b = np.clip(((hi + BLEND) - x) / (2 * BLEND), 0, 1) if np.isfinite(hi) else np.ones(len(x))
        W[:, i] = np.minimum(a, b)
    return W / np.maximum(W.sum(1, keepdims=True), 1e-9)


def _grid(P, uv_slot, cap_start, cap_end):
    """a part's rings (rows, nth, 3) as quads (and fan caps) with a UV per ring and column (the seam column doubled)
    -> (V, faces, face_uv (per face, its corners' UV indices), uvs, ring rows per vertex (the caps' centres: -1 / rows))."""
    nr, nth = P.shape[:2]
    V = [P.reshape(-1, 3)]
    rowof = [np.repeat(np.arange(nr), nth)]
    u0, v0, u1, v1 = uv_slot
    uvs = [(u0 + (u1 - u0) * j / nth, v1 - (v1 - v0) * i / max(1, nr - 1)) for i in range(nr) for j in range(nth + 1)]
    uvi = lambda i, j: i * (nth + 1) + j
    faces, fuv = [], []
    for i in range(nr - 1):
        for j in range(nth):
            j2 = (j + 1) % nth
            faces.append((i * nth + j, i * nth + j2, (i + 1) * nth + j2, (i + 1) * nth + j))
            fuv.append((uvi(i, j), uvi(i, j + 1), uvi(i + 1, j + 1), uvi(i + 1, j)))
    n0 = nr * nth
    for flag, ring in ((cap_start, 0), (cap_end, nr - 1)):
        if not flag:
            continue
        V.append(P[ring].mean(0)[None]); rowof.append(np.array([ring]))
        c = n0; n0 += 1
        cu = len(uvs); uvs.append(((u0 + u1) / 2, v1 if ring == 0 else v0))
        for j in range(nth):
            a, b = ring * nth + j, ring * nth + (j + 1) % nth
            faces.append((c, b, a) if ring == 0 else (c, a, b))
            fuv.append((cu, uvi(ring, j + 1), uvi(ring, j)) if ring == 0 else (cu, uvi(ring, j), uvi(ring, j + 1)))
    # rows run down (or along the limb) and columns round toward her left: (right, down) crosses inward, so each face
    # is reversed for outward normals (the shells lift along them, the collar's ray finds the surface, outlines see out)
    faces = [tuple(reversed(f)) for f in faces]
    fuv = [tuple(reversed(q)) for q in fuv]
    return np.concatenate(V), faces, fuv, uvs, np.concatenate(rowof)


def build_body_data(spec, chin, log=print):
    """the authored body as the build's body data (charkit.body.build_body_data's contract, for code_base.wrap): verts in
    metres (the eye line where the code head's chin puts it: z = height - L - chin L, feet near 0), faces (quads, fan caps),
    per-face UVs (a slot per part; the head's box left free: head_uv_box), weights per VRM bone (the torso by height
    between the graph skeleton's joints, each limb along its chain), joints under MakeHuman's names (every VRM bone:
    the fingers laid in the mitten, weightless), the torso's open top ring as the neck ring. Blender-safe (numpy)."""
    from . import body as bodylib, mh
    Z = np.load(spec['body_code'])
    sk = {k: (tuple(a), tuple(b)) for k, (a, b) in json.loads(str(Z['skeleton'])).items()}
    P = bodylib._merge(bodylib.DEFAULT_BODY, spec.get('body'))
    Hm = float(P['height_m'])
    L = Hm / float(P['heads_tall'])
    Oz = Hm - L - chin * L
    world = lambda X: np.asarray(X, float) * L + np.array([0.0, 0.0, Oz])
    Vs, Fs, FUV, UVs, W = [], [], [], [], {}
    nv = nuv = 0
    neck_ring = None
    parts = {}
    for name in PARTS:
        Pp = Z[name + '_P']
        cap_start = name != 'torso'                        # the torso's top ring stays open: the neck ring
        V_, F_, fuv_, uv_, row = _grid(Pp, UV_SLOTS[name], cap_start, True)
        nr, nth = Pp.shape[:2]
        if name == 'torso':
            neck_ring = list(range(nv, nv + nth))
            z = Z['torso_z'][np.clip(row, 0, nr - 1)]
            edges = [sk['upperChest'][1][1], sk['chest'][1][1], sk['spine'][1][1], sk['hips'][1][1]]
            Wp = _blend(-z, [-e for e in edges], len(TORSO_BONES))
            for i, b in enumerate(TORSO_BONES):
                W.setdefault(b, []).append((nv, Wp[:, i]))
        elif name.startswith('foot_'):
            side = name.split('_')[1]
            y = Pp.reshape(-1, 3)[:, 1]
            y = np.r_[y, [Pp[0].mean(0)[1], Pp[-1].mean(0)[1]]][:len(V_)]
            front, back = float(Z[name + '_front']), float(Z[name + '_back'])
            ytoe = front + TOE_SHARE * (back - front)
            Wp = _blend(-y, [-ytoe], 2)                         # (toward the front: -y) the foot, then the toes
            W.setdefault(side + 'Foot', []).append((nv, Wp[:, 0]))      # (the heel side: larger y)
            W.setdefault(side + 'Toes', []).append((nv, Wp[:, 1]))
        else:
            kind, side = name.split('_')
            bones = [side + b for b in LIMBS[kind][0]]
            s = Z[name + '_s'][np.clip(row, 0, nr - 1)]
            s0 = Z[name + '_s0']
            Wp = _blend(s, list(s0[1:len(bones)]), len(bones))
            for i, b in enumerate(bones):
                W.setdefault(b, []).append((nv, Wp[:, i]))
        parts[name] = (nv, nv + len(V_))
        Vs.append(world(V_))
        Fs += [tuple(v + nv for v in f) for f in F_]
        FUV += [tuple(u + nuv for u in q) for q in fuv_]
        UVs += uv_
        nv += len(V_); nuv += len(uv_)
    V = np.concatenate(Vs)
    weights = {}
    for b, chunks in W.items():
        a = np.zeros(nv)
        for start, w in chunks:
            a[start:start + len(w)] = w
        weights[b] = a
    J = _joints(Z, sk, world, L)
    missing = [j for pair in mh.VRM_JOINTS.values() for j in pair if j not in J]
    if missing:
        raise ValueError('authored body: no joint for %s' % missing[:5])
    log('code body: %d verts, %d faces, %d bones weighted' % (nv, len(Fs), len(weights)))
    eye_y = float(np.mean(Z['eyes'][:, 1])) * L if 'eyes' in Z.files else None     # (world y: x and z need no move)
    return dict(verts=V, faces=Fs, face_uv=FUV, uvs=np.array(UVs), weights=weights, joints=J, neck_ring=neck_ring,
                params=P, head_len=L, scale=1.0, head_w=np.zeros(nv), marks={}, authored=True,
                head_uv_box=HEAD_UV_BOX, parts=parts, eye_y=eye_y)


def _joints(Z, sk, world, L):
    """MakeHuman-named joints for every VRM bone, from the graph skeleton's front-view joints, the torso's centre depth
    at each height and the limbs' fitted chains; the fingers laid across the hand (weightless), the toes forward of the
    ankle on the sole."""
    zc, cy = Z['torso_z'], Z['torso_cy']
    ty = lambda z: float(np.interp(-z, -zc, cy))
    J = {}
    spine = [('spine05____head', sk['hips'][0][1]), ('spine04____head', sk['hips'][1][1]),
             ('spine03____head', sk['spine'][1][1]), ('spine01____head', sk['chest'][1][1]),
             ('neck01____head', sk['upperChest'][1][1]), ('head____head', sk['neck'][1][1]),
             ('head____tail', sk['head'][1][1])]
    for name, z in spine:
        J[name] = world((0.0, ty(z), z))                     # (above the cut: the neck ring's depth)
    for side, S_ in (('left', 'L'), ('right', 'R')):
        arm = Z['arm_%s_J' % side]; leg = Z['leg_%s_J' % side]
        cz = sk[side + 'Shoulder'][0][1]
        J['clavicle.%s____head' % S_] = world((0.3 * arm[0][0], ty(cz), cz))
        J['shoulder01.%s____head' % S_] = world(arm[0])
        J['lowerarm01.%s____head' % S_] = world(arm[1])
        J['wrist.%s____head' % S_] = world(arm[2])
        hand = arm[3] - arm[2]
        hl = np.linalg.norm(hand); hd = hand / max(hl, 1e-9)
        across = np.array([0.0, -1.0, 0.0])                  # the fingers side by side front to back (palms inward)
        for f in range(1, 6):
            off = (f - 3) * 0.035                            # L: finger spacing across the hand
            base = arm[2] + hd * hl * (0.2 if f == 1 else 0.5) + across * off
            for seg in range(1, 4):
                a = base + hd * hl * 0.5 * (seg - 1) / 3
                b = base + hd * hl * 0.5 * seg / 3
                J['finger%d-%d.%s____head' % (f, seg, S_)] = world(a)
                J['finger%d-%d.%s____tail' % (f, seg, S_)] = world(b)
        J['upperleg01.%s____head' % S_] = world(leg[0])
        J['lowerleg01.%s____head' % S_] = world(leg[1])
        J['foot.%s____head' % S_] = world(leg[2])
        sole = float(Z['sole_z'])
        front, back = float(Z['foot_%s_front' % side]), float(Z['foot_%s_back' % side])
        J['toe1-1.%s____head' % S_] = world((leg[2][0], front + TOE_SHARE * (back - front), sole + 0.06))
        J['toe1-1.%s____tail' % S_] = world((leg[2][0], front, sole + 0.04))
    return J
