"""The native hair construction (shot 2's model) driven by a style vector (STYLE.json): sheets from the crown whorl,
clumps as relief, each layer continuous at its roots and splitting toward its tips.

    python groom3.py SRC_BUNDLE_DIR DST_BUNDLE_DIR STYLE.json
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
STYLE = json.load(open(sys.argv[3]))
src = open(os.path.join(HERE, 'groom.py')).read()
head, _ = src.split('# ------------------------------------------------------------------------------------------------ the groups')
lean = STYLE.get('normals_lean', 0.9)
head = head.replace('lean = 0.65 * R[loopv] + 0.35 * own', 'lean = %r * R[loopv] + %r * own' % (lean, 1 - lean))
head = head.replace('return np.where(np.isnan(s), 0.6 * e, np.minimum(s + 0.004, e - 0.004))',
                    'return np.where(np.isnan(s), 0.6 * e, np.minimum(s + 0.004 + %r, e - 0.004))'
                    % STYLE.get('clearance', 0.0))
exec(head)
rng = np.random.default_rng(STYLE.get('seed', 7))
if STYLE.get('envelope') == 'head':
    # the hair a modest standoff off the scalp, falling by gravity below the ears (a vertical drop at the side's
    # distance, a little flare): volume is a style number, not the drawing's silhouette
    E = STYLE.get('env', {})
    s0, s1, ear, flare = E.get('crown', 0.012), E.get('side', 0.022), E.get('ear', 96.0), E.get('flare', 0.18)
    Sf = _carry(SCALP)
    NE = np.zeros_like(ENVF)
    ie = int(round(ear / 2))
    ft = E.get('face_tuck', 0.0)
    bk = E.get('back_flare', 1.0)                               # the flare's share at the back (1 at the sides / front)
    for j in range(NE.shape[1]):
        aj = abs(AL[j])
        flare_j = flare * (bk + (1 - bk) * min(aj / 90.0, 1.0))
        tuck = 1 - ft * np.clip((aj - 110) / 70.0, 0, 1)          # (the standoff shrinks toward the face)
        d_side = (np.nanmax(Sf[max(ie - 6, 0):ie + 1, j]) * np.sin(np.radians(ear))) + s1 * tuck
        for i, t in enumerate(TH):
            if t <= ear:
                NE[i, j] = Sf[i, j] + s0 + (s1 * tuck - s0) * (t / ear) ** 1.5
            else:
                if E.get('shape') == 'round':                     # a rounded bob: bulge toward the jaw, tuck at the hem
                    span = E.get('span', 50.0)
                    f = flare_j * np.sin(np.pi * np.clip((t - ear) / span, 0, 1)) + E.get('tuck', 0.0) * np.clip((t - ear - span) / 20.0, 0, 1)
                else:
                    f = flare_j * (t - ear) / 60.0
                NE[i, j] = d_side * (1 + f) / max(np.sin(np.radians(t)), 0.25)
    ENVF = NE
    print('head-native envelope: crown %.3f side %.3f flare %.2f' % (s0, s1, flare))
    if STYLE.get('hem_by_height', True):
        # the locks end at the hull's hem HEIGHT per direction (cycle 28's volume profile: ending at the hull's hem
        # ANGLE made them far too long on a fuller envelope)
        _hem_angle = hem

        def hem(al_):
            t_h = _hem_angle(al_)
            ia_ = int(np.round((al_ + 180) / 3)) % len(AL)
            it_ = int(np.clip(round(t_h / 2), 0, len(TH) - 1))
            r_h = ENV[it_, ia_] if not np.isnan(ENV[it_, ia_]) else ENVF[it_, ia_]
            z_h = r_h * np.cos(np.radians(t_h))                      # (relative to C)
            zs = ENVF[:, ia_] * np.cos(np.radians(TH))
            below = np.where(zs <= z_h)[0]
            return float(TH[below[0]]) if len(below) else t_h
_add0, _arr0 = Mesh.add, Mesh.arrays
CID = [0]
LOCKS = []
GROUP = [0]


def _add(self, V, F):
    if not hasattr(self, 'cid'):
        self.cid, self.S = [], []
    sv = getattr(self, 'pending_s', None)
    self.S += list(sv) if sv is not None and len(sv) == len(V) else [1.0] * len(V)
    if not hasattr(self, 'U'):
        self.U = []
    uv_ = getattr(self, 'pending_u', None)
    self.U += list(uv_) if uv_ is not None and len(uv_) == len(V) else [0.0] * len(V)
    self.pending_u = None
    if not hasattr(self, 'RA'):
        self.RA = []
    self.RA += [getattr(self, 'cur_roll', None) or getattr(self, 'roll', None) or
                (STYLE.get('root_roll', 0.0), STYLE.get('roll_len', 0.35))] * len(V)
    self.pending_s = None
    self.cid += [getattr(self, 'cur', -1)] * len(F)
    _add0(self, V, F)


def _arrays(self):
    g = _arr0(self)
    g['clump'] = np.array(getattr(self, 'cid', []), np.int32)
    g['sv'] = np.array(getattr(self, 'S', [1.0] * len(g['V'])), np.float32)
    g['uv'] = np.array(getattr(self, 'U', [0.0] * len(g['V'])), np.float32)
    r_, th_, al_ = sph(g['V'])
    ri_, re_ = inner(th_, al_), env(th_, al_)
    g['hv'] = np.clip((r_ - ri_) / np.maximum(re_ - ri_, 1e-6), 0, 1.5).astype(np.float32)   # depth in the stack
    if TOPMAP.get('top') is not None:
        # occlusion: how much hair lies OUTSIDE this point along its radial direction (0 on the outer surface .. 1
        # under STYLE['ao'] metres of hair): the real depth, not the envelope proxy
        top_ = TOPMAP['top']
        it_ = np.clip((th_ / OH_T).astype(int), 0, top_.shape[0] - 1)
        ia_ = ((al_ + 180) / OH_A).astype(int) % top_.shape[1]
        g['ao'] = np.clip((top_[it_, ia_] - r_) / max(STYLE.get('ao', 0.02), 1e-6), 0, 1).astype(np.float32)
    if hasattr(self, 'S') and hasattr(self, 'RA'):
        sv = np.array(self.S)[g['loopv']]
        ra = np.array(self.RA, float)[g['loopv']]
        amt = (ra[:, 0] * np.clip(1 - sv / np.maximum(ra[:, 1], 1e-6), 0, 1))[:, None]
        if TOPMAP.get('top') is not None:                         # + the overhang shadow
            amt = np.maximum(amt, STYLE.get('overhang', 0.0) * overhang(g['V'])[g['loopv']][:, None])
        # (the ribbons are wound inward: the renderer sees their outer faces as back faces and flips the normal, so a
        # normal pointing into the head is drawn pointing out; the roll goes the same way, so it is drawn downward)
        Rl = g['V'][g['loopv']] - C
        sgn = np.sign(np.sum(g['lnor'] * Rl, axis=1, keepdims=True) + 1e-12)
        n = g['lnor'] + amt * sgn * np.array([0.0, 0.0, -1.0])
        g['lnor'] = (n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)).astype(np.float32)
    return g


Mesh.add, Mesh.arrays = _add, _arrays


def edge_fn(table):
    xs, ys = zip(*table)
    return lambda a: float(np.interp(abs(((a + 180) % 360) - 180) / 180, xs, ys))


FACE_CFG = {}


def ribbon2(m, P, Pb, width, thick, k=8, curl=0.3, face=None):
    """ribbon() with the cross-section's frame taken from the uncurled path Pb: a flicked tip bends without its section
    flipping into a flat flag (it2's folded ends)."""
    n = len(P)
    T = np.gradient(Pb, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    Out = Pb - C
    Out -= np.sum(Out * T, axis=1, keepdims=True) * T
    Out /= np.maximum(np.linalg.norm(Out, axis=1, keepdims=True), 1e-12)
    Bn = np.cross(T, Out)
    if face is not None and face[1]:
        F_, phi = np.asarray(face[0], float), np.radians(face[1])
        sg = np.sign(Bn @ F_ + 1e-12)[:, None]
        Out, Bn = np.cos(phi) * Out + np.sin(phi) * sg * Bn, np.cos(phi) * Bn - np.sin(phi) * sg * Out
    u = np.linspace(0, 2 * np.pi, k, endpoint=False)
    rings = []
    for i in range(n - 1):
        cw, st = np.cos(u) * width[i] / 2, np.sin(u) * thick[i] / 2
        st = st - curl * thick[i] * np.cos(u) ** 2
        rings.append(P[i] + cw[:, None] * Bn[i] + st[:, None] * Out[i])
    V = np.concatenate(rings + [P[-1:]])
    m.pending_s = np.concatenate([np.repeat(np.linspace(0, 1, n)[:-1], k), [1.0]])
    m.pending_u = np.concatenate([np.tile(np.cos(u), n - 1), [0.0]])
    F = [list(range(k))[::-1]]
    for i in range(n - 2):
        for j in range(k):
            a, b = i * k + j, i * k + (j + 1) % k
            F.append([a, b, b + k, a + k])
    tip, base = len(V) - 1, (n - 2) * k
    for j in range(k):
        F.append([base + j, base + (j + 1) % k, tip])
    m.add(V, F)


TOPMAP = {}
OH_T, OH_A = 0.5, 0.75                                             # the overhang map's cells (deg)


def build_topmap(meshes):
    """the outermost hair radius per direction, on a fine (theta, alpha) grid, from every groomed mesh."""
    V = np.concatenate([np.concatenate(m.V) for m in meshes if m.V])
    r, th, al = sph(V)
    it = np.clip((th / OH_T).astype(int), 0, int(180 / OH_T))
    ia = ((al + 180) / OH_A).astype(int) % int(360 / OH_A)
    top = np.zeros((int(180 / OH_T) + 1, int(360 / OH_A)))
    np.maximum.at(top, (it, ia), r)
    TOPMAP['top'] = top


def overhang(V):
    """0..1 per vertex: hair a little above it (toward the crown, within OH_WIN deg along the surface) standing out past
    it by more than a lock's thickness: the shadow an overhanging lock or layer edge casts on what lies below it."""
    top = TOPMAP['top']
    r, th, al = sph(V)
    it = np.clip((th / OH_T).astype(int), 0, top.shape[0] - 1)
    ia = ((al + 180) / OH_A).astype(int) % top.shape[1]
    win = int(STYLE.get('overhang_win', 8) / OH_T)
    eps, ramp = STYLE.get('overhang_eps', 0.006), STYLE.get('overhang_ramp', 0.008)
    k = STYLE.get('overhang_k', 1.0)              # how far a shadow reaches per unit of overhang height
    out_ = np.zeros(len(V))
    for d in range(1, win + 1):
        step = r * np.radians(d * OH_T)           # the distance along the surface up to the overhanging hair
        h = top[np.clip(it - d, 0, None), ia] - r - eps
        out_ = np.maximum(out_, np.clip((h - step / k) / ramp + 1, 0, 1) * (h > 0))
    return out_


def clump(m, ua, ub, th0, th1, h0, h1, split, wave=0.0, waves=1.0, phase=0.0, sway=0.0, flick=0.0, flick_up=0.0,
          flick_from=0.75, thick=0.014, overlap=1.12, n=40, k=10, curl=0.35, sweep=0.0, tip_power=0.85, brush=None,
          hook_sign=1.0, lift=0.0, lift_at=0.3, relief_i=0.0):
    CID[0] += 1
    m.cur = GROUP[0] * 1000 + CID[0] % 1000
    s = np.linspace(0, 1, n)
    uc = (ua + ub) / 2 + sweep * s
    if brush:
        v = 1 + brush.get('vary', 0.12) * rng.uniform(-1, 1)
        sh = brush.get('shift', 0.05) * rng.uniform(-1, 1)
        Wb = np.interp(np.clip(s + sh * s * (1 - s) * 4, 0, 1), *zip(*brush['w']))
        cb = np.interp(np.clip(s + sh, 0, 1), *zip(*brush['c'])) * v * hook_sign
        uc = uc + cb * (ub - ua)
    th = th0 + (th1 - th0) * s
    wv = np.sin(2 * np.pi * waves * s + phase) * np.clip(s * 2.5, 0, 1)
    al = uc + sway * wv
    h = h0 + (h1 - h0) * s + wave * wv
    if relief_i:
        h = h + relief_i * np.clip((s - 0.12) / 0.45, 0, 1) ** 1.5
    if lift:
        h = h + lift * np.sin(np.pi * np.clip(s / lift_at, 0, 1)) * (s < lift_at) + \
            lift * (s >= lift_at) * np.exp(-((s - lift_at) / 0.35) ** 2)   # rise off the scalp, settle
    fl = np.clip((s - flick_from) / (1 - flick_from), 0, 1) ** 1.5
    h = h + flick * fl
    th = th - flick_up * fl
    P = point(th, al, h)
    Pb = point(th0 + (th1 - th0) * s, al, h0 + (h1 - h0) * s + wave * wv)   # the uncurled path: the section's frame
    LOCKS.append(dict(group=int(GROUP[0]), P=P.round(5).tolist()))
    half = (ub - ua) / 2 * overlap
    w = np.linalg.norm(point(th, al + half, h) - point(th, al - half, h), axis=1)
    tp = np.where(s < split, 1.0, np.clip(1 - (s - split) / (1 - split), 0, 1) ** tip_power)
    if brush:
        tp = Wb * v
    tk = np.maximum(thick * np.where(s < split, 1.0, 0.35 + 0.65 * tp), 0.0008)
    wp = w * tp
    LOCKS[-1].update(width=float(np.median(wp)), width_max=float(wp.max()), thick=float(np.median(tk)),
                     wprof=(np.interp(np.linspace(0, 1, 11), s, wp) / max(wp.max(), 1e-9)).round(3).tolist(),
                     span=float(ub - ua))
    sub = STYLE.get('sub_split')
    if sub and STYLE.get('sub_split_groups') and GROUP[0] not in STYLE['sub_split_groups']:
        sub = None
    fc = FACE_CFG.get(GROUP[0])
    face = None
    if fc:
        ac_ = abs((ua + ub) / 2)
        face = (fc['dir'], fc['max'] * float(np.clip((ac_ - fc['from']) / (fc['to'] - fc['from']), 0, 1)))
    if not sub:
        ribbon2(m, P, Pb, np.maximum(w * tp, 0.0), tk, k=k, curl=curl, face=face)
        return
    T_ = np.gradient(Pb, axis=0)
    T_ /= np.maximum(np.linalg.norm(T_, axis=1, keepdims=True), 1e-12)
    O_ = Pb - C
    O_ -= np.sum(O_ * T_, axis=1, keepdims=True) * T_
    O_ /= np.maximum(np.linalg.norm(O_, axis=1, keepdims=True), 1e-12)
    Bn_ = np.cross(T_, O_)
    s0_, spread, short = sub.get('from', 0.66), sub.get('spread', 0.35), sub.get('short', 0.82)
    part = np.clip((s - s0_) / (1 - s0_), 0, 1) ** 1.4
    for side_, lf in ((-1.0, 1.0), (1.0, short)):
        off = side_ * (w * tp / 4 + spread * w[0] * part)[:, None] * Bn_
        tp_i = np.interp(np.clip(s / lf, 0, 1), s, tp) * (s <= lf + 1e-9)
        ribbon2(m, P + off, Pb + off, np.maximum(w * tp_i / 2, 0.0), tk * 0.8, k=k, curl=curl, face=face)


def sheet(m, al_lo, al_hi, n, th0_fn, th1_fn, h0, h1, split, jitter=0.0, split_jitter=0.08, phase_step=0.35,
          hook=None, shingle=0.0, shingle_order='out', **kw):
    hier = (STYLE.get('hierarchy') or {}).get(str(GROUP[0]))
    if hier:
        wts = rng.choice(hier['sizes'], size=n, p=hier['probs'])
        edges = al_lo + (al_hi - al_lo) * np.concatenate([[0], np.cumsum(wts) / wts.sum()])
    else:
        wts = np.ones(n)
        edges = np.linspace(al_lo, al_hi, n + 1)
    for i in range(n):
        ua, ub = edges[i], edges[i + 1]
        ac = (ua + ub) / 2
        hs = 1.0 if hook is None else hook(ac)
        dz = shingle * (i / max(n - 1, 1) if shingle_order == 'across' else abs(ac - (al_lo + al_hi) / 2) /
                        max((al_hi - al_lo) / 2, 1e-6))
        fj = STYLE.get('flick_jitter', 0.0)
        kw_ = dict(kw)
        if fj and 'flick' in kw_:
            kw_['flick'] = kw_['flick'] * (1 + rng.uniform(-fj, fj))
            kw_['flick_up'] = kw_.get('flick_up', 0) * (1 + rng.uniform(-fj, fj))

        rel = STYLE.get('relief', {}).get(str(GROUP[0]), 0.0)
        if STYLE.get('relief_mode') == 'grow':                  # irregular, growing in along the lock (smooth at the root)
            kw_['relief_i'] = rel * rng.uniform(0.0, 1.0)
        else:
            dz = dz + (rel if i % 2 else 0.0) + rel * 0.5 * rng.uniform(-1, 1)
        dlen = hier.get('len_k', 0.0) * (wts[i] - 1.0) if hier else 0.0
        clump(m, ua, ub, th0_fn(ac), th1_fn(ac) + rng.uniform(-jitter, jitter) + dlen, h0 + dz, h1 + dz,
              split + rng.uniform(-split_jitter, split_jitter), phase=phase_step * i + STYLE.get('phase_rand', 0.3) * rng.uniform(-1, 1),
              hook_sign=hs, **kw_)


S = STYLE
out = {}
FRONT = S['front_band']
U, Lw, Sd, Bg = S['upper'], S['lower'], S['side'], S['bangs']
cap_edge = edge_fn(U['edge'])
knobs = lambda d: {k: d[k] for k in ('wave', 'waves', 'sway', 'flick', 'flick_up', 'flick_from', 'thick', 'overlap',
                                     'curl', 'tip_power', 'sweep', 'phase_step', 'split_jitter', 'brush', 'shingle', 'shingle_order', 'lift', 'lift_at') if k in d}

upper = Mesh()
GROUP[0] = 1
sheet(upper, -(180 - FRONT), 180 - FRONT, U['n'], lambda a: 0.0, cap_edge, U['h'][0], U['h'][1], U['split'],
      jitter=U.get('jitter', 3), **knobs(U))
if STYLE.get('outer'):
    O_ = STYLE['outer']
    GROUP[0] = 7
    cap_o = edge_fn(O_.get('edge', U['edge']))
    sheet(upper, -(180 - FRONT) + O_.get('inset', 6), 180 - FRONT - O_.get('inset', 6), O_['n'], lambda a: O_.get('th0', 8.0),
          lambda a: cap_o(a) * O_.get('len', 0.8), O_['h'][0], O_['h'][1], O_.get('split', 0.75), jitter=O_.get('jitter', 6),
          **knobs(dict(U, **O_)))
out['hair_upper_back'] = upper

lower = Mesh()
GROUP[0] = 2
if Lw.get('roll'):
    lower.roll = tuple(Lw['roll'])
if not Lw.get('tiers'):
  sheet(lower, -Lw['al'], Lw['al'], Lw['n'], lambda a: cap_edge(a) - Lw['start_above_edge'],
      lambda a: hem(a) + Lw.get('hem_extra', 0), Lw['h'][0], Lw['h'][1], Lw['split'], jitter=Lw.get('jitter', 5),
      hook=lambda a: float(np.sin(np.radians(a))), **knobs(Lw))
for ti, T in enumerate(Lw.get('tiers', [])):
    GROUP[0] = 2
    f0, f1 = T['span']
    top = lambda a: cap_edge(a) - Lw['start_above_edge']
    spans = [(-T['al'], T['al'], T['n'])] if not T.get('al_in') else \
        [(T['al_in'], T['al'], T['n']), (-T['al'], -T['al_in'], T['n'])]
    lower.cur_roll = tuple(T['roll']) if T.get('roll') else None
    for lo_, hi_, n_ in spans:
        sheet(lower, lo_, hi_, n_, lambda a, f0=f0: top(a) + f0 * (hem(a) + Lw.get('hem_extra', 0) - top(a)),
              lambda a, f1=f1: top(a) + f1 * (hem(a) + Lw.get('hem_extra', 0) - top(a)), T['h'][0], T['h'][1],
              T.get('split', 0.6), jitter=T.get('jitter', 3), hook=lambda a: float(np.sin(np.radians(a))),
              **knobs(dict(Lw, **T)))
if Lw.get('tier2'):                                               # an outer tier: shorter, flicking at mouth/chin height
    GROUP[0] = 3
    T2 = Lw['tier2']
    sheet(lower, -T2['al'], T2['al'], T2['n'], lambda a: cap_edge(a) - Lw['start_above_edge'],
          lambda a: cap_edge(a) + T2['frac'] * (hem(a) - cap_edge(a)), T2['h'][0], T2['h'][1], T2['split'],
          jitter=T2.get('jitter', 4), hook=lambda a: float(np.sin(np.radians(a))), **knobs(T2))
lower.cur = 8000
lower.cur_roll = (1.6, 50.0)
slab(lower, 100, lambda a: hem(a) - 10, -120, 120, 0.5, 0.38, nt=14, na=40)
out['hair_lower_back'] = lower

for side, sg in (('L', 1), ('R', -1)):
    m = Mesh()
    GROUP[0] = 4 if sg > 0 else 5
    lo, hi = Sd['band']
    a0, a1 = (lo, hi) if sg > 0 else (-hi, -lo)
    kw = knobs(Sd)
    kw['sway'] = kw.get('sway', 0) * sg
    for tier in (Sd.get('tiers') or [dict(th=Sd['th'], h=Sd['h'], n=Sd['n'])]):
        m.cur_roll = tuple(tier['roll']) if tier.get('roll') else None
        kt = dict(kw, **{k: tier[k] for k in ('brush', 'flick', 'flick_up', 'shingle') if k in tier})
        sheet(m, a0, a1, tier['n'], lambda a, t=tier: t['th'][0], lambda a, t=tier: t['th'][1], tier['h'][0],
              tier['h'][1], Sd['split'], jitter=Sd.get('jitter', 4), hook=lambda a, sg=sg: -sg, **kt)
    out['hair_side_lock_' + side] = m

bangs = Mesh()
GROUP[0] = 6
bang_tip = lambda a: Bg['tip_centre'] - Bg['tip_slope'] * abs(((a - 180) + 180) % 360 - 180)
sheet(bangs, 180 - FRONT, 180 + FRONT, Bg['n'], lambda a: Bg['th0'], bang_tip, Bg['h'][0], Bg['h'][1], Bg['split'],
      jitter=Bg.get('jitter', 3), **knobs(Bg))
out['hair_bangs'] = bangs

fly = Mesh()
fly.cur = 7000
for side, sg in (('L', 1), ('R', -1)):
    Bv = A['o/hair_bun_%s/eval/V' % side]
    base = np.array([Bv[:, 0].mean(), Bv[:, 1].mean(), Bv[:, 2].min() + 0.01])
    for out_, down, fwd in S.get('flyaways', ((0.045, 0.06, -0.005), (0.06, 0.04, 0.015))):
        s = np.linspace(0, 1, 16)[:, None]
        P = base + np.array([sg * out_, fwd, 0]) * s + np.array([0, 0, -down]) * s ** 1.3 \
            + np.array([sg * 0.015, 0, 0.012]) * np.sin(np.pi * s) ** 2 * s
        ribbon(fly, P, taper(s[:, 0], 0.007, 0.25), np.maximum(taper(s[:, 0], 0.0035, 0.25), 0.0006))
out['hair_flyaways'] = fly

def resolve_stack(meshes, eps=0.002, res=(0.5, 0.75)):
    """collision-free stacking: lock by lock in build order (each Mesh.V entry is one lock or slab), every vertex is
    pushed out along its radial direction to sit at least eps above everything already placed in that direction."""
    rt, ra = res
    top = np.zeros((int(180 / rt) + 1, int(360 / ra)))
    moved = 0
    for m in meshes:
        for i, V in enumerate(m.V):
            r, th, al = sph(V)
            it = np.clip((th / rt).astype(int), 0, top.shape[0] - 1)
            ia = ((al + 180) / ra).astype(int) % top.shape[1]
            floor_ = top[it, ia] + eps
            push = floor_ > r
            if push.any():
                d = (V - C) / np.maximum(r, 1e-9)[:, None]
                rn = np.where(push, floor_, r)
                V = C + d * rn[:, None]
                m.V[i] = V
                moved += int(push.sum())
                r = rn
            np.maximum.at(top, (it, ia), r)
    print('stack resolver: %d vertices pushed' % moved)


if STYLE.get('stack_resolve'):
    order = [out[k] for k in ('hair_upper_back', 'hair_lower_back', 'hair_side_lock_L', 'hair_side_lock_R',
                              'hair_bangs') if k in out]
    resolve_stack(order, eps=STYLE.get('stack_eps', 0.002))
if STYLE.get('overhang'):
    build_topmap([m for m in out.values()])
if STYLE.get('palette'):
    pal = STYLE['palette']
    sh = M['materials']['hair_shape']['shading']
    for k_ in ('lit', 'shade', 'deep', 'rim'):
        if k_ in pal:
            sh[k_] = pal[k_]
    for k_ in ('lit_at', 'deep_at', 'rim_from', 'rim_amt', 'blend'):
        if k_ in pal:
            sh[k_] = pal[k_]
exec(src.split('# ------------------------------------------------------------------------------------------------ the bundle')[1])
json.dump(dict(centre=C.tolist(), L=float(M['assembly']['L']), locks=LOCKS), open(os.path.join(DST, 'locks.json'), 'w'))
