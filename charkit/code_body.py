"""The authored body, fitted to the visual hull (docs/workstreams/body.md): the body as the design's inner envelope,
where the drawings show skin or a tight garment, and bounded by the hull's envelope everywhere else, so no part of it
stands out of the design (a piece lying on it would be buried). Built in the hull's own frame (L, eye line z = 0,
x toward her left, -y toward the viewer), aligned to the build by the eyes as the hull is.

The torso: a radius field round a vertical axis (charkit.geom.loft) from the neck cut down to the hips. Rows the hull
shows (the lower bodice, the waistband, bare skin) are measured, each piece pulled in by its thickness; rows it hides
(the chest under the bow and collar, the hips under the skirt) are interpolated per angle between the measured rows
and the anchors (the neck ring; the hips from the graph skeleton's leg joints and the thighs' radius), then held
inside the hull's torso envelope less a clearance.

    python -m charkit.code_body SPEC [--out DIR]        # the torso measured against the hull, and its review page
"""
import json, os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUT = -0.52                      # L: the neck cut (code_base.CUT)
TIGHT = {'top': 0.022, 'waistband': 0.035, 'skin': 0.0}     # L: what the body sits under, by the piece's thickness
CLEAR = 0.012                    # L: the body stays this far inside the hull's envelope where nothing measures it
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


def fit_torso(meas, Rc, th_c, ay, neck, hw=None, hy=None):
    """every row's superellipse at once: the measured cells as data, smooth down the rows (second differences,
    W_SMOOTH), held weakly to a torso's proportions (PRIOR), the cut's row to the neck ring and the bottom row's
    half-width to the hips' (W_ANCHOR). One least-squares solve with a sparse Jacobian (a row's cells depend only on its
    own section) -> (nz, 5)."""
    from scipy.optimize import least_squares
    from scipy.sparse import lil_matrix
    nz = len(meas)
    rows = [np.nonzero(meas[k])[0] for k in range(nz)]
    X0 = np.tile([0.33, 0.28, 0.28, PRIOR['n'], ay], (nz, 1))
    X0[0] = neck
    lo = np.tile([0.05, 0.05, 0.05, 1.8, ay - 0.6], nz)
    hi = np.tile([1.2, 1.2, 1.2, 4.0, ay + 0.6], nz)
    nd = sum(len(r) for r in rows)
    ns = 5 * (nz - 2)
    npr = 4 * nz
    na = 5 + (1 if hw else 0) + (1 if hy is not None else 0)

    def res(x):
        X = x.reshape(nz, 5)
        out = [section_r(X[k], th_c[rows[k]], ay) - Rc[k, rows[k]] for k in range(nz) if len(rows[k])]
        d2 = (X[2:] - 2 * X[1:-1] + X[:-2]) * np.array(W_SMOOTH)
        out.append(d2.ravel())
        a = X[:, 0]
        out.append(W_PRIOR * np.r_[X[:, 1] / a - PRIOR['depth'], X[:, 2] / a - PRIOR['depth'], X[:, 3] - PRIOR['n'],
                                   0.4 * (X[:, 4] - ay)])
        anc = [W_ANCHOR * (X[0] - neck)]
        if hw:
            anc.append([W_ANCHOR * (X[-1, 0] - hw)])
        if hy is not None:
            anc.append([W_ANCHOR * (X[-1, 4] - hy)])
        out.append(np.concatenate(anc))
        return np.concatenate(out)
    J = lil_matrix((nd + ns + npr + na, 5 * nz), dtype=int)
    r0 = 0
    for k in range(nz):
        n_ = len(rows[k])
        if n_:
            J[r0:r0 + n_, 5 * k:5 * k + 5] = 1
            r0 += n_
    for k in range(nz - 2):
        for q in range(5):
            J[r0 + 5 * k + q, [5 * k + q, 5 * (k + 1) + q, 5 * (k + 2) + q]] = 1
    r0 += ns
    for q, col in enumerate((1, 2, 3, 4)):
        for k in range(nz):
            J[r0 + q * nz + k, 5 * k] = 1
            J[r0 + q * nz + k, 5 * k + col] = 1
    r0 += npr
    J[r0:r0 + 5, 0:5] = 1
    r0 += 5
    if hw:
        J[r0, 5 * (nz - 1)] = 1
        r0 += 1
    if hy is not None:
        J[r0, 5 * (nz - 1) + 4] = 1
    sol = least_squares(res, np.clip(X0.ravel(), lo, hi), bounds=(lo, hi), jac_sparsity=J, x_scale='jac')
    return sol.x.reshape(nz, 5)


def torso(H, sk, nz=56, nth=72, hip_z=None):
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
    hair = lab == H.ids.get('hair', -1)
    band = (H.V[:, 2] <= CUT + 0.02) & (H.V[:, 2] >= z_bot - 0.05)
    E = H.V[band & ~hair]
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
    return dict(ax=ax, F=loft.Field(ts, th_c, R, meas), params=Pi, rows=rows, measured=share, env=env, src=src)


def signed_out(B, ax, F):
    """per point of the design (B, on its surface), how far our torso stands out of it (L; + out: it would bury a piece
    lying there)."""
    t, th, r = ax.coords(B)
    return F.at(t, th) - r


def measure(H, T, sk):
    """the torso against the hull: per tight piece, where our torso stands out of it (median, p90, share out by more
    than 0.02 L, all after its pull-in), within the torso's rows."""
    out = {}
    lo, hi = T['F'].ts[0], T['F'].ts[-1]
    for name, dt in TIGHT.items():
        Q = H.points(name)
        if name == 'skin':
            Q = Q[(np.abs(Q[:, 0]) < TORSO_SKIN_X) & (Q[:, 2] <= CUT + 0.02) & (Q[:, 2] > -1.0)]
        if not len(Q):
            continue
        Q = Q[~arm_mask(Q, sk)]
        t = T['ax'].coords(Q)[0]
        Q = Q[(t >= lo) & (t <= hi)]
        if not len(Q):
            continue
        s = signed_out(Q, T['ax'], T['F']) + dt
        out[name] = dict(n=int(len(Q)), median=round(float(np.median(s)), 4), p90=round(float(np.percentile(s, 90)), 4),
                         out=round(float((s > 0.02).mean()), 3))
    return out


def page(H, T, sk, out, rep):
    """the torso's review page: sections at several heights (the hull's envelope points, the measured points, our
    section), the rows' measured share, and the numbers."""
    import html
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(os.path.join(out, 'img'), exist_ok=True)
    ax, F = T['ax'], T['F']
    picks = np.linspace(0, len(T['rows']) - 1, 12).astype(int)
    fig, axs = plt.subplots(3, 4, figsize=(14, 10.5))
    hair = H.piece == H.ids.get('hair', -1)
    allE = H.V[~hair]
    for a_, k in zip(axs.flat, picks):
        z = T['rows'][k]
        E = allE[np.abs(allE[:, 2] - z) < 0.02]
        E = E[~arm_mask(E, sk)]
        a_.scatter(E[:, 0], E[:, 1], s=2, c='#bbb', label='hull (not hair, not arms)')
        for Q, dt in T['src']:
            q = Q[np.abs(Q[:, 2] - z) < 0.02]
            if len(q):
                a_.scatter(q[:, 0], q[:, 1], s=4, label='measured (pull-in %.3f)' % dt)
        th = np.linspace(-np.pi, np.pi, 200)
        p = ax.point(np.full(200, F.ts[k]), th, F.at(np.full(200, F.ts[k]), th))
        a_.plot(p[:, 0], p[:, 1], 'k-', lw=1.5, label='our torso')
        a_.set_title('z %.2f L  measured %.0f%%' % (z, 100 * T['measured'][k]), fontsize=10)
        a_.set_aspect('equal'); a_.invert_yaxis(); a_.set_xlim(-1.1, 1.1); a_.set_ylim(0.9, -0.7)
    axs.flat[0].legend(fontsize=7, loc='lower left')
    fig.tight_layout()
    fig.savefig(os.path.join(out, 'img', 'sections.png'), dpi=90)
    plt.close(fig)
    L = ['<!doctype html><meta charset="utf-8"><title>authored torso</title><style>body{font:14px/1.45 -apple-system,'
         'system-ui,sans-serif;margin:24px;background:#fafafa;color:#222}table{border-collapse:collapse;font-size:13px}'
         'td,th{border:1px solid #ddd;padding:3px 8px;text-align:right}th{background:#f0f0f0}td:first-child{text-align:'
         'left}.note{color:#555;font-size:13px;max-width:980px}img{max-width:100%;border:1px solid #ddd}</style>',
         '<h1>The authored torso against the hull</h1>',
         '<p class="note">Sections seen from above (x across, the front up). Grey: the hull at that height (the '
         'design\'s outer surface, hair and arms left out). Colours: the points that measure the torso (a tight piece '
         'or bare skin, each pulled in by its thickness). Black: our torso. Where nothing measures a row, it is '
         'interpolated between measured rows and anchors and held inside the grey. The table: where our torso stands '
         'out of each tight piece (L; + out). The MakeHuman body under the top: median +0.077, p90 +0.155, 86%% out '
         'by more than 0.02 L.</p>',
         '<table><tr><th>piece</th><th>points</th><th>median</th><th>p90</th><th>share out &gt; 0.02 L</th></tr>']
    for k, v in rep['out'].items():
        L.append('<tr><td>%s</td><td>%d</td><td>%+.3f</td><td>%+.3f</td><td>%.0f%%</td></tr>' % (
            html.escape(k), v['n'], v['median'], v['p90'], 100 * v['out']))
    L.append('</table><h2>Sections</h2><img src="img/sections.png">')
    open(os.path.join(out, 'index.html'), 'w').write('\n'.join(L))
    json.dump(rep, open(os.path.join(out, 'torso.json'), 'w'), indent=1)
    return os.path.join(out, 'index.html')


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return 0
    from . import manifest
    spec = manifest.resolve(json.load(open(args[0])))
    out = args[args.index('--out') + 1] if '--out' in args else os.path.join(ROOT, 'charkit', 'out', 'body', spec['name'])
    hull_path = manifest.produced(spec, 'hull')
    masks = manifest.produced(spec, 'outfit_masks')
    H = Hull(os.path.dirname(hull_path))
    sk = skeleton(json.load(open(os.path.join(os.path.dirname(masks), 'outfit_graph.json'))))
    T = torso(H, sk)
    rep = {'out': measure(H, T, sk), 'measured_rows': [round(float(x), 3) for x in T['measured']],
           'rows': [round(float(z), 3) for z in T['rows']]}
    for k, v in rep['out'].items():
        print('%-10s n %5d  median %+.3f  p90 %+.3f  out>0.02 %.0f%%' % (k, v['n'], v['median'], v['p90'], 100 * v['out']))
    print(page(H, T, sk, out, rep))
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv[1:]))
