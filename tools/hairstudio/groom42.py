"""Cycle 42: a fluffy, messy twin-bun, built from the hairstyle's structure (Michael, 2026-10-02: "what does a fluffy,
messy twin-bun look like in 3D? Forget the reference image, let's start from that question"; "you tend to get stuck
hillclimbing an idea ... this is breaking out and going in a different direction").

The structure, not the drawing:
  - a half-up style: a centre part and a gather line at about ear height split the head; above the gather line each
    side is pulled into its bun (the buns are the flow field's sinks, overriding the crown's whorl)
  - the GATHERED section: locks from the hairline and the gather line to the bun base, close to the skull (tension)
    with slack puffs, narrowing as they converge; a few wisps escape at the temples and the nape
  - the LOOSE section below the gather line: two layers with air between (an inner fill, an outer layer of leaf
    blades), varied lengths, waves pushing them apart, tips at many heights
  - BANGS: separated, wispy pieces falling forward from the front of the part
  - TENDRILS: one or two per side left down in front of the ear
  - the buns, the ahoge and the bun flyaways kept as built

    python groom42.py SRC_BUNDLE_DIR DST_BUNDLE_DIR STYLE.json
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
src3 = open(os.path.join(HERE, 'groom3.py')).read()
infra = src3.split("S = STYLE\nout = {}")[0]
exec(infra)                                                   # groom3's infrastructure (envelope, ribbons, sheets, Mesh)
S = STYLE
out = {}
TW = S['twin']


def slerp_dirs(d0, d1, s):
    d0, d1 = d0 / np.linalg.norm(d0), d1 / np.linalg.norm(d1)
    om = np.arccos(np.clip(d0 @ d1, -1, 1))
    if om < 1e-6:
        return np.outer(1 - s, d0) + np.outer(s, d1)
    return (np.sin((1 - s) * om)[:, None] * d0 + np.sin(s * om)[:, None] * d1) / np.sin(om)


def scalp_r(D):
    """the scalp's radius along unit directions D (the skin's radial map, with the inner fallback)."""
    r = np.linalg.norm(D, axis=1)
    th = np.degrees(np.arccos(np.clip(D[:, 2] / r, -1, 1)))
    al = np.degrees(np.arctan2(D[:, 0], D[:, 1]))
    return inner(th, al) - 0.004, th, al


def gathered_lock(m, d_start, d_end, end_lift, w0, slack, tension=0.004, n=40, k=8, thick=0.004, wave=0.0):
    """a lock pulled from the hairline / gather line to a bun base: on the skull at `tension` (m), a slack puff of
    `slack` (m) mid-way, diving `end_lift` (m) into the bun's base at the end; narrowing to a third as it converges."""
    CID[0] += 1
    m.cur = GROUP[0] * 1000 + CID[0] % 1000
    s = np.linspace(0, 1, n)
    D = slerp_dirs(d_start, d_end, s)
    rs, th, al = scalp_r(D)
    stand = tension + slack * np.sin(np.pi * s) ** 1.3 + end_lift * np.clip((s - 0.75) / 0.25, 0, 1) ** 2
    if wave:
        stand = stand + wave * np.sin(2 * np.pi * 1.5 * s) * np.sin(np.pi * s)
    P = C + D * (rs + stand)[:, None]
    width = w0 * (1 - TW.get('converge', 0.65) * s ** 1.2)
    LOCKS.append(dict(group=int(GROUP[0]), P=P.round(5).tolist(), width=float(np.median(width)),
                      width_max=float(width.max()), thick=thick, wprof=(np.interp(np.linspace(0, 1, 11), s, width) /
                                                                         width.max()).round(3).tolist(), span=0.0))
    ribbon2(m, P, P, width, np.full(n, thick), k=k, curl=0.25)


def dir_of(th, al):
    return dirv(np.atleast_1d(float(th)), np.atleast_1d(float(al)))[0]


# --------------------------------------------------------------------------------------------- the gathered section
gathered = Mesh()
GROUP[0] = 1
buns = {}
if TW.get('reseat_buns'):
    # the buns were placed on the hull's crown (about 2.3 cm off the skull): sink each radially so its base sits
    # reseat_buns metres above our crown (the designed tension standoff)
    for side in ('L', 'R'):
        Bv = A['o/hair_bun_%s/eval/V' % side]
        b_ = np.array([Bv[:, 0].mean(), Bv[:, 1].mean(), Bv[:, 2].min()])
        v_ = (b_ - C) / np.linalg.norm(b_ - C)
        target = scalp_r(v_[None])[0][0] + TW['tension'] + TW['reseat_buns']
        sink = np.linalg.norm(b_ - C) - target
        for var_ in ('eval', 'raw'):
            k_ = 'o/hair_bun_%s/%s/V' % (side, var_)
            if k_ in A:
                A[k_] = (A[k_] - v_ * sink).astype(A[k_].dtype)
        print('bun %s re-seated: sunk %.2f cm' % (side, sink * 100))
for side in ('L', 'R'):
    Bv = A['o/hair_bun_%s/eval/V' % side]
    base = np.array([Bv[:, 0].mean(), Bv[:, 1].mean(), Bv[:, 2].min()])
    buns[side] = base - C
gl = TW['gather']                                             # the gather line: theta per |alpha| (table)
gather_th = lambda a: float(np.interp(abs(a), *zip(*gl)))
for side, sg in (('L', 1.0), ('R', -1.0)):
    d_end = buns[side] / np.linalg.norm(buns[side])
    rb = np.linalg.norm(buns[side])
    starts = []
    # the front hairline from the part to the temple (behind the bangs' roots)
    for a in np.linspace(TW['part_gap'], TW['temple'], TW['n_front']):
        starts.append((TW['hairline_th'], sg * (180 - a)))
    # the gather line from the temple round to the back's centre
    for a in np.linspace(180 - TW['temple'], 3, TW['n_back']):
        starts.append((gather_th(a), sg * a))
    # the centre part: from the forehead hairline over the top and down the back to the gather line, each side's
    # locks sweeping sideways from it to their bun (cycle 42 left the crown bald without these)
    for t in np.linspace(TW['hairline_th'] - 2, 4, TW.get('n_part_front', 5)):
        starts.append((t, sg * (180 - TW['part_gap'] * 0.5)))
    for t in np.linspace(6, gather_th(0) - 4, TW.get('n_part_back', 8)):
        starts.append((t, sg * TW['part_gap'] * 0.5))
    rng_ = np.random.default_rng(11 if sg > 0 else 12)
    order = np.argsort([abs(a) for _, a in starts])             # (the back first: the front locks lie over them)
    for j, i in enumerate(order[::-1]):
        th_s, al_s = starts[i]
        d_s = dir_of(th_s, al_s)
        # the lock's width from its share of the boundary (metric spacing at the start), fuller than the gap
        w0 = TW['width'] * (0.75 + 0.5 * rng_.uniform())
        rs_end = scalp_r(d_end[None])[0][0]
        smooth_ = TW.get('smooth')
        gathered_lock(gathered, d_s, d_end, end_lift=max(rb * 0.92 - rs_end, 0.0), w0=w0,
                      slack=TW['slack'] * (1.0 if smooth_ else rng_.uniform(0.3, 1.0)),
                      tension=TW['tension'] + TW.get('stack', 0.0006) * j,
                      thick=TW['thick'], wave=0.0 if smooth_ else TW.get('gwave', 0.0) * rng_.uniform(0, 1))
# the gathered underlayer: one continuous thin sheet over the scalp above the gather line (real gathered hair covers
# the scalp; the pulled locks are relief on it). Cycle 42-43's bald patches were the gaps between converging locks.
if TW.get('underlayer', True):
    gathered.cur = 1999
    def _ul_lo(a):
        return gather_th(a) + 2
    slab(gathered, 0.0, _ul_lo, -179.5, 179.5, 0.0, 0.0, nt=36, na=144, wrap=True)
    # (slab's h is a fraction of the envelope span: pull it onto the skull at the gathered locks' tension)
    Vu = gathered.V[-1]
    r_, th_, al_ = sph(Vu)
    D_ = (Vu - C) / r_[:, None]
    rs_ = scalp_r(D_)[0]
    half = len(Vu) // 2
    stand_ = np.concatenate([np.full(half, TW['tension'] * 0.7), np.full(len(Vu) - half, TW['tension'] * 0.2)])
    gathered.V[-1] = C + D_ * (rs_ + stand_)[:, None]
# escaping wisps at the temples and the nape (group 7)
GROUP[0] = 7
wisps = Mesh()
for (th0, a0, dth, da) in TW['wisps']:
    for sg in (1, -1):
        clump(wisps, sg * a0 - 2, sg * a0 + 2, th0, th0 + dth, 1.0, 1.4, 0.4, wave=0.08, waves=1.2, sway=4 * sg,
              flick=0.3, flick_up=10, thick=0.002, overlap=1.0, brush=dict(w=[[0, 0.6], [0.3, 1.0], [0.7, 0.6], [1, 0]],
                                                                         c=[[0, 0], [0.5, 0.2], [1, 0.6]]))
out['hair_upper_back'] = gathered
if TW.get('reseat_ahoge') and 'o/hair_ahoge/eval/V' in A:
    # the ahoge was placed on the hull's crown (about 2.3 cm off the skull); sink it radially onto ours
    Va = A['o/hair_ahoge/eval/V']
    base_ = Va[Va[:, 2] <= np.percentile(Va[:, 2], 5)].mean(0)
    v_ = (base_ - C) / np.linalg.norm(base_ - C)
    Gv = np.concatenate(gathered.V)
    dd_ = Gv - C
    rr_ = np.linalg.norm(dd_, axis=1)
    m_ = np.degrees(np.arccos(np.clip((dd_ / rr_[:, None]) @ v_, -1, 1))) < 3.0
    gap_ = np.linalg.norm(base_ - C) - rr_[m_].max() - TW.get('ahoge_embed', 0.003)
    for var_ in ('eval', 'raw'):
        k_ = 'o/hair_ahoge/%s/V' % var_
        if k_ in A:
            A[k_] = (A[k_] - v_ * gap_).astype(A[k_].dtype)
    print('ahoge re-seated: sunk %.2f cm' % (gap_ * 100))

# ------------------------------------------------------------------------------------------------ the loose section
def cut_sheet(m, al_lo, al_hi, th0, base_fn, points, depth, h_root, h_tip, thick=0.004, na=140, nt=30, sweep=0.0,
              flick=0.0, cid=0, forward=0.0, fwd_from=0.5, back_sweep=0.0, h_prof=None, standoff=None, centre=None,
              wprof=None, bend=0.0, s_bend=0.0):
    """one continuous sheet over alpha [al_lo, al_hi] from theta th0 to its hem, the hem CUT into lock points: the hem
    reaches base_fn(alpha) at each point and rises by `depth` deg midway between them (V-points). Standoff from h_root
    at the root to h_tip at the hem (lying on the forehead), `sweep` deg sideways along the length, `flick` at the hem.
    The lock identity is in the cut, not in separate strands (anime bangs and panels)."""
    m.cur = cid
    pts = np.sort(np.asarray(points, float))
    sp = np.diff(pts).mean() if len(pts) > 1 else (al_hi - al_lo)
    al_ = np.linspace(al_lo, al_hi, na)
    s = np.linspace(0, 1, nt)
    G, Sv, Uv = np.zeros((nt, na, 3)), np.zeros((nt, na)), np.zeros((nt, na))
    for j, a in enumerate(al_):
        dd = np.min(np.abs(pts - a))
        notch = depth * np.clip(dd / (sp / 2), 0, 1) ** 0.75
        tip = base_fn(a) - notch
        t0_ = th0(a) if callable(th0) else th0
        tt = t0_ + (tip - t0_) * s
        hh = (np.interp(s, *zip(*h_prof)) if h_prof else h_root + (h_tip - h_root) * s ** 0.7) \
            + flick * np.clip((s - 0.8) / 0.2, 0, 1) ** 1.5
        fw = forward * np.clip((s - fwd_from) / (1 - fwd_from), 0, 1) ** 1.6 * np.sign(a)   # toward the face (+-180)
        aa = a + sweep * s + fw - back_sweep * s * np.sign(a)
        if centre is not None:
            # a flame / leaf blade: the width follows wprof along the length (pointed tip), and the centreline curves
            # sideways: a C (bend deg, accelerating toward the tip) plus an S (s_bend deg)
            wp = np.interp(s, *zip(*wprof)) if wprof else 1.0
            aa = centre + (a - centre) * wp + bend * s ** 1.6 + s_bend * np.sin(2 * np.pi * s) * np.sin(np.pi * s) \
                + sweep * s
        if standoff:                                            # metres off the skull (the scalp map), not envelope fractions
            so = np.interp(s, *zip(*standoff))
            D_ = dirv(tt, aa)
            G[:, j] = C + D_ * (inner(tt, aa) - 0.004 + so)[:, None]
        else:
            G[:, j] = point(tt, aa, hh)
        Sv[:, j] = s
        Uv[:, j] = np.clip(dd / (sp / 2), 0, 1)
    sheets = [G]
    D_ = (G - C) / np.linalg.norm(G - C, axis=2, keepdims=True)
    sheets.append(G - D_ * thick)
    V = np.concatenate([sh.reshape(-1, 3) for sh in sheets])
    o2 = nt * na
    F = []
    for i in range(nt - 1):
        for j in range(na - 1):
            a_, b_, c_, d_ = i * na + j, i * na + j + 1, (i + 1) * na + j + 1, (i + 1) * na + j
            F.append([a_, b_, c_, d_]); F.append([o2 + d_, o2 + c_, o2 + b_, o2 + a_])
    for j in range(na - 1):
        for i in (0, nt - 1):
            a_, b_ = i * na + j, i * na + j + 1
            F.append([a_, o2 + a_, o2 + b_, b_] if i else [b_, o2 + b_, o2 + a_, a_])
    for i in range(nt - 1):
        for j in (0, na - 1):
            a_, d_ = i * na + j, (i + 1) * na + j
            F.append([a_, d_, o2 + d_, o2 + a_] if j == 0 else [d_, a_, o2 + a_, o2 + d_])
    m.pending_s = np.concatenate([Sv.ravel(), Sv.ravel()])
    m.pending_u = np.concatenate([Uv.ravel(), Uv.ravel()])
    m.add(V, F)


def mirror_mesh(m, cid_off=500):
    """the mesh's left half mirrored to the right (x about the head's centre), winding reversed: a symmetric cut."""
    V = np.concatenate(m.V)
    n = len(V)
    Vm = V.copy()
    Vm[:, 0] = 2 * C[0] - Vm[:, 0]
    nF = len(m.F)
    m.F += [[i + n for i in f[::-1]] for f in m.F[:nF]]
    m.V.append(Vm)
    m.n += n
    m.cid += [c + cid_off if c >= 0 else c for c in m.cid[:nF]]
    for attr in ('S', 'U'):
        if hasattr(m, attr):
            setattr(m, attr, getattr(m, attr) + getattr(m, attr)[:n])
    if hasattr(m, 'RA'):
        m.RA = m.RA + m.RA[:n]
    for lk in [l for l in LOCKS if l['group'] == GROUP[0]]:
        P_ = np.array(lk['P']); P_[:, 0] = 2 * C[0] - P_[:, 0]
        LOCKS.append(dict(lk, P=P_.round(5).tolist()))


_hem_raw = hem
_hem_tab = np.array([_hem_raw(a) for a in np.arange(-180, 181, 3.0)])
_hem_s = np.convolve(np.pad(_hem_tab, 6, mode='wrap'), np.ones(13) / 13, mode='same')[6:-6]


def hem_smooth(a):
    return float(np.interp(a, np.arange(-180, 181, 3.0), _hem_s))


loose = Mesh()
GROUP[0] = 2
Lo = S['loose']
if Lo.get('face'):
    FACE_CFG[2] = dict(Lo['face'], dir=[0.0, -1.0, 0.0])       # (the front is -y)
top = lambda a: gather_th(a) - Lo['tuck']
if Lo.get('designed'):
    hem = hem_smooth
    fc = Lo.get('face_cut', 0.0)                                 # degrees shorter at the face (|alpha| 180)
    _h0 = hem
    hem = lambda a, _h0=_h0: _h0(a) - fc * np.clip((abs(a) - 110) / 40.0, 0, 1)
for pi, PL in enumerate(Lo.get('paper', [])):
    GROUP[0] = 2
    al_p = PL['al']
    hem_p = lambda a, PL=PL: top(a) + PL['frac'] * (hem(a) - top(a))
    npts = PL['n']
    pts_p = list(np.linspace(-al_p + al_p / npts, al_p - al_p / npts, npts))
    cut_sheet(loose, -al_p, al_p, top, hem_p, pts_p, PL['depth'], 0, 0, thick=PL.get('thick', 0.004), na=220, nt=30,
              flick=0.0, cid=2000 + 100 * pi, standoff=PL['standoff'])
for layer in ([] if Lo.get('paper') else Lo['layers']):
    end_ = (lambda a, e=layer.get('hem_extra', 0), f=layer['frac']: top(a) + f * (hem(a) + e - top(a))) \
        if layer.get('frac') else (lambda a, e=layer.get('hem_extra', 0): hem(a) + e)
    _mir = Lo.get('designed') and Lo.get('designed_mirror', True)
    lo_ = 0.0 if _mir else -layer['al']
    nn_ = (layer['n'] + 1) // 2 if _mir else layer['n']
    sheet(loose, lo_, layer['al'], nn_, top, end_,
          layer['h'][0], layer['h'][1], layer.get('split', 0.6), jitter=layer.get('jitter', 8),
          hook=lambda a: float(np.sin(np.radians(a))) * (float(np.clip(1 - (abs(a) - Lo['hook_fade'][0]) /
                       (Lo['hook_fade'][1] - Lo['hook_fade'][0]), Lo['hook_fade'][2], 1)) if Lo.get('hook_fade') else 1.0),
          **{k_: layer[k_] for k_ in ('wave', 'waves', 'sway', 'flick', 'flick_up', 'flick_from', 'thick', 'overlap',
                                      'brush', 'phase_step', 'split_jitter', 'shingle', 'lift', 'lift_at') if k_ in layer})
if Lo.get('designed') and Lo.get('designed_mirror', True):
    mirror_mesh(loose)
if Lo.get('core'):
    # the loose section's core: one continuous mass under its locks (a closed shell), the same principle as the
    # gathered underlayer: hair is a mass with relief, not a set of separate sheets (cycle 51's isolation view)
    Co = Lo['core']
    loose.cur = 2998
    na, nt = 96, 24
    al_ = np.linspace(-Co['al'], Co['al'], na)
    sheets = []
    for off in (0.0, -Co.get('thick', 0.004)):
        G = np.zeros((nt, na, 3))
        for j, a in enumerate(al_):
            t0, t1 = top(a) + Co.get('top_in', 4), hem(a) - Co.get('hem_in', 6)
            tt = np.linspace(t0, t1, nt)
            fr_ = np.interp(np.linspace(0, 1, nt), [0, 0.35, 1], Co['frac'])
            P_ = point(tt, np.full(nt, a), fr_)
            d_ = (P_ - C) / np.linalg.norm(P_ - C, axis=1, keepdims=True)
            G[:, j] = P_ + d_ * off
        sheets.append(G)
    Vc = np.concatenate([sheets[0].reshape(-1, 3), sheets[1].reshape(-1, 3)])
    o2 = nt * na
    Fc = []
    for i in range(nt - 1):
        for j in range(na - 1):
            a_, b_, c_, d_ = i * na + j, i * na + j + 1, (i + 1) * na + j + 1, (i + 1) * na + j
            Fc.append([a_, b_, c_, d_]); Fc.append([o2 + d_, o2 + c_, o2 + b_, o2 + a_])
    for j in range(na - 1):                                     # rims: bottom and top
        for i in (0, nt - 1):
            a_, b_ = i * na + j, i * na + j + 1
            Fc.append([a_, o2 + a_, o2 + b_, b_] if i else [b_, o2 + b_, o2 + a_, a_])
    for i in range(nt - 1):                                     # the two side edges
        for j in (0, na - 1):
            a_, d_ = i * na + j, (i + 1) * na + j
            Fc.append([a_, d_, o2 + d_, o2 + a_] if j == 0 else [d_, a_, o2 + a_, o2 + d_])
    loose.add(Vc, Fc)
out['hair_lower_back'] = loose

# ---------------------------------------------------------------------------------------------- tendrils and bangs
for side, sg in (('L', 1), ('R', -1)):
    m = Mesh()
    GROUP[0] = 4 if sg > 0 else 5
    if S.get('side_panels'):
        layers = S['side_panels'] if isinstance(S['side_panels'], list) else [S['side_panels']]
        for li, SP in enumerate(layers):
            lo, hi = SP['al']
            base = lambda a, SP=SP: float(np.interp(abs(a), [SP['al'][0], SP['al'][1]], SP['tip']))
            cut_sheet(m, lo if sg > 0 else -hi, hi if sg > 0 else -lo, SP['th0'], base,
                      [sg * p_ for p_ in SP['points']], SP['depth'], SP['h'][0], SP['h'][1],
                      thick=SP.get('thick', 0.004), flick=SP.get('flick', 0.0), forward=SP.get('forward', 0.0),
                      fwd_from=SP.get('fwd_from', 0.5), back_sweep=SP.get('back_sweep', 0.0), standoff=SP.get('standoff'),
                      cid=(4 if sg > 0 else 5) * 1000 + 1 + li)
        out['hair_side_lock_' + side] = m
        continue
    for (a0, th0, th1, wdeg) in TW['tendrils']:
        clump(m, sg * a0 - wdeg / 2, sg * a0 + wdeg / 2, th0, th1, 0.7, 0.95, 0.5, wave=0.06, waves=1.3, sway=5 * sg,
              flick=0.18, flick_up=8, thick=0.004, overlap=1.0, hook_sign=-sg,
              brush=dict(w=[[0, 0.7], [0.3, 1.0], [0.6, 0.8], [0.85, 0.45], [1, 0]],
                         c=[[0, 0], [0.35, 0.2], [0.65, -0.15], [1, 0.5]]))
    out['hair_side_lock_' + side] = m
bangs = Mesh()
GROUP[0] = 6
Bg = S['bangs']
bang_tip = lambda a: Bg['tip_centre'] - Bg['tip_slope'] * abs(((a - 180) + 180) % 360 - 180)
if Bg.get('pieces'):
    # bold bangs: separate pointed pieces fanned from the part, each a cut sheet with one point (a leaf: widest near
    # the root, tapering to a sharp tip), gaps between them near the tips (the forehead's negative space defines their
    # shapes), layered by `layer` (higher on top) with a small standoff step
    for k_, pc in enumerate(Bg['pieces']):
        a0 = 180 + pc['at'] - pc['w'] / 2
        a1 = 180 + pc['at'] + pc['w'] / 2
        so = [[x, y + pc.get('layer', 0) * 0.0025] for x, y in Bg['standoff']]
        blade = Bg.get('blade')
        cut_sheet(bangs, a0, a1, Bg['th0'], lambda a, pc=pc: pc['tip'], [180 + pc['at'] + pc.get('lean', 0.0)],
                  0.0 if blade else pc.get('depth', (pc['tip'] - Bg['th0']) * 0.38), 0, 0, thick=0.004,
                  sweep=0.0 if blade else pc.get('sweep', 0.0), cid=6000 + k_ + 1, standoff=so, na=40, nt=36,
                  centre=(180 + pc['at']) if blade else None, wprof=blade, bend=pc.get('bend', 0.0),
                  s_bend=pc.get('s_bend', 0.0))
elif Bg.get('cut'):
    Ct = Bg['cut']
    cut_sheet(bangs, 180 - Bg['half'], 180 + Bg['half'], Bg['th0'], bang_tip, [180 + p_ for p_ in Ct['points']],
              Ct['depth'], Bg['h'][0], Bg['h'][1], thick=Ct.get('thick', 0.004), sweep=Ct.get('sweep', 0.0),
              flick=Ct.get('flick', 0.0), cid=6001, h_prof=Ct.get('h_prof'), standoff=Ct.get('standoff'))
else:
  sheet(bangs, 180 - Bg['half'], 180 + Bg['half'], Bg['n'], lambda a: Bg['th0'], bang_tip, Bg['h'][0], Bg['h'][1],
      0.55, jitter=Bg.get('jitter', 4), **{k_: Bg[k_] for k_ in ('thick', 'overlap', 'brush', 'sweep', 'lift', 'lift_at')
                                           if k_ in Bg})
out['hair_bangs'] = bangs

fly = wisps
for side, sg in (('L', 1), ('R', -1)):
    Bv = A['o/hair_bun_%s/eval/V' % side]
    base = np.array([Bv[:, 0].mean(), Bv[:, 1].mean(), Bv[:, 2].min() + 0.01])
    for out_, down, fwd in ((0.045, 0.06, -0.005), (0.06, 0.04, 0.015)):
        s_ = np.linspace(0, 1, 16)[:, None]
        P = base + np.array([sg * out_, fwd, 0]) * s_ + np.array([0, 0, -down]) * s_ ** 1.3 \
            + np.array([sg * 0.015, 0, 0.012]) * np.sin(np.pi * s_) ** 2 * s_
        ribbon(fly, P, taper(s_[:, 0], 0.007, 0.25), np.maximum(taper(s_[:, 0], 0.0035, 0.25), 0.0006))
out['hair_flyaways'] = fly

if STYLE.get('no_flyaways'):
    # (Michael, 2026-10-02: the flyaways and wisps don't work stylistically in 3D) the object is dropped from the bundle
    out.pop('hair_flyaways', None)
    M['objects'] = [o for o in M['objects'] if o['name'] != 'hair_flyaways']
    for k_ in [k_ for k_ in A if k_.startswith('o/hair_flyaways/')]:
        del A[k_]
if STYLE.get('ao'):
    build_topmap([m for m in out.values()])                  # (the outermost hair per direction, for the occlusion)
if STYLE.get('palette'):
    pal = STYLE['palette']
    sh = M['materials']['hair_shape']['shading']
    for k_ in ('lit', 'shade', 'deep', 'rim', 'lit_at', 'deep_at', 'rim_from', 'rim_amt', 'blend'):
        if k_ in pal:
            sh[k_] = pal[k_]
    if 'highlight_amount' in pal and isinstance(sh.get('highlight'), dict):
        sh['highlight']['amount'] = pal['highlight_amount']
_gsrc = open(os.path.join(HERE, 'groom.py')).read()
exec(_gsrc.split('# ------------------------------------------------------------------------------------------------ the bundle')[1])
json.dump(dict(centre=C.tolist(), L=float(M['assembly']['L']), locks=LOCKS), open(os.path.join(DST, 'locks.json'), 'w'))
