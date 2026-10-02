"""Clawd's new hairstyle (Michael, 2026-10-02: "give it a shot. You have a lot of aesthetic freedom here, really the only
lock-in is the color palette"): long, wavy, half-up, built from its structure for 3D.

  crown     a smooth held shell from the whorl to the ear line (the face open), rigid
  knot      half-up: the upper hair on her left gathered into a small twisted knot (a coil and two tufts), where the
            crab and star clips sit; the gathered locks run over the skull into it
  bangs     curved flame blades (cycle 69's)
  front     two wave clumps a side from the temples, draped in front of the shoulders down over the chest
  back      the long hair: an outer layer of big wave clumps from under the crown, draped down the back to the waist
            (longest at the centre, shorter toward the sides), over an inner, darker, shorter layer
  waves     big coherent S-curves (designed phases), amplitude growing from the root; tips pointed, curling outward
  drape     below the head a clump follows the body and the outfit at a standoff: the curtain model (hanging straight
            from the most protruding part above, relaxing slightly inward, never inside the body)

    python groom_long.py SRC DST STYLE.json
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
src3 = open(os.path.join(HERE, 'groom3.py')).read()
exec(src3.split("S = STYLE\nout = {}")[0])
src42 = open(os.path.join(HERE, 'groom42.py')).read()
exec(src42[src42.index('def cut_sheet('):src42.index('def mirror_mesh(')])
exec(src42[src42.index('def slerp_dirs('):src42.index('# --------------------------------------------------------------------------------------------- the gathered section')])
S = STYLE
TW = {'converge': 0.55}
SMOOTH_DRAPE = S.get('smooth_drape', False)
STY_RELAX = S.get('sty_relax', 0.05)
BLEND = S.get('blend', 0.08)
out = {}

# ------------------------------------------------------------------------------------------------- the body's drape map
TORSO_G = ('top', 'bodice_panel', 'collar', 'bow', 'skirt', 'waistband', 'overskirt_panel_R', 'overskirt_panel_L', 'shorts')
pts_ = [skin[(skin[:, 2] < EYE_Z - 0.12)]]
for o in M['objects']:
    if o['name'] in TORSO_G and ('o/%s/eval/V' % o['name']) in A:
        pts_.append(A['o/%s/eval/V' % o['name']])
BP = np.concatenate(pts_)
YC = 0.012
lim = np.where(BP[:, 2] > 1.07, 0.19, 0.15)                  # (the arms hang outside: torso only)
BP = BP[np.abs(BP[:, 0]) < lim]
ZB = np.arange(0.6, 1.32, 0.005)
ALB = np.arange(-180, 180, 5.0)
rb = np.hypot(BP[:, 0], BP[:, 1] - YC)
ab = np.degrees(np.arctan2(BP[:, 0], BP[:, 1] - YC))
iz = np.clip(((BP[:, 2] - ZB[0]) / 0.005).astype(int), 0, len(ZB) - 1)
ia = ((ab + 180) / 5).astype(int) % len(ALB)
RB = np.zeros((len(ZB), len(ALB)))
np.maximum.at(RB, (iz, ia), rb)
from scipy import ndimage as _nd
RB = _nd.grey_closing(RB, size=(3, 3))
RB = _nd.gaussian_filter(RB, (2.0, 1.2), mode=('nearest', 'wrap'))


def r_body(z, a):
    i = np.clip((np.asarray(z) - ZB[0]) / 0.005, 0, len(ZB) - 1.001)
    j = ((np.asarray(a) + 180) / 5) % len(ALB)
    i0, j0 = np.floor(i).astype(int), np.floor(j).astype(int) % len(ALB)
    j1 = (j0 + 1) % len(ALB)
    fi, fj = i - np.floor(i), j - np.floor(j)
    return ((1 - fi) * (1 - fj) * RB[i0, j0] + (1 - fi) * fj * RB[i0, j1] + fi * (1 - fj) * RB[np.minimum(i0 + 1, len(ZB) - 1), j0]
            + fi * fj * RB[np.minimum(i0 + 1, len(ZB) - 1), j1])


def clump_path(a, th_root, th_leave, z_tip, h_head, so, relax, n=70, sway=0.0, waves=1.6, phase=0.0, bump=0.0,
               curl=0.0, a_drift=0.0):
    """a clump's centreline: over the head from th_root to th_leave (alpha a, envelope fraction h_head), then draped
    down to z_tip; the S-wave sideways (sway, m) and outward (bump), growing from the root; a_drift deg of alpha
    drift down the drape (front clumps fall forward of the shoulder)."""
    nh = 18
    th = np.linspace(th_root, th_leave, nh)
    hh = h_head * (0.9 + 0.1 * np.clip(np.linspace(0, 1, nh) / 0.5, 0, 1))   # (tucked under the crown at the root)
    Ph = point(th, np.full(nh, a), hh)
    z0 = Ph[-1, 2]
    r0 = np.hypot(Ph[-1, 0], Ph[-1, 1] - YC)
    nd = n - nh
    z = np.linspace(z0, z_tip, nd + 1)[1:]
    aa = a + a_drift * np.linspace(0, 1, nd) ** 1.3
    rbody = r_body(z, aa) + so
    r = np.empty(nd)
    run, zmax = r0, z0
    for i in range(nd):
        if rbody[i] >= run:
            run, zmax = rbody[i], z[i]
        r[i] = max(rbody[i], run - relax * (zmax - z[i]))
    if SMOOTH_DRAPE:
        # one silhouette, no break: r eases from where it leaves the head toward the curtain (a smooth step over
        # BLEND metres of drop), then is smoothed and kept outside the body
        drop = z0 - z
        e = np.clip(drop / BLEND, 0, 1); e = e * e * (3 - 2 * e)
        r = r0 + (r - r0) * e
        r = _nd.gaussian_filter1d(r, 4, mode='nearest')
        r = np.maximum(r, rbody - so * 0.4)
    Pd = np.stack([r * np.sin(np.radians(aa)), YC + r * np.cos(np.radians(aa)), z], 1)
    P = np.concatenate([Ph, Pd])
    if SMOOTH_DRAPE:                                             # (smooth the head-to-drape junction itself)
        Pj = P.copy()
        for k_ in range(3):
            Pj[:, k_] = _nd.gaussian_filter1d(P[:, k_], 3, mode='nearest')
        wj = np.exp(-((np.arange(len(P)) - nh) / 5.0) ** 2)[:, None]
        P = P * (1 - wj) + Pj * wj
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    s /= s[-1]
    # the wave: sideways (horizontal, perpendicular to the radial direction) and outward
    rad = P - np.array([0, YC, 0]); rad[:, 2] = 0
    rad /= np.maximum(np.linalg.norm(rad, axis=1, keepdims=True), 1e-9)
    side = np.stack([rad[:, 1], -rad[:, 0], np.zeros(len(P))], 1)
    ramp = np.clip((s - 0.12) / 0.3, 0, 1) ** 1.5
    w = np.sin(2 * np.pi * waves * s + phase)
    P = P + side * (sway * w * ramp)[:, None] + rad * (bump * np.cos(2 * np.pi * waves * s + phase) * ramp)[:, None]
    if curl:                                                     # the tip curls outward and up
        cu = np.clip((s - 0.85) / 0.15, 0, 1) ** 2
        P = P + rad * (curl * cu)[:, None] + np.array([0, 0, 1.0]) * (0.4 * curl * cu)[:, None]
    # resample evenly
    s2 = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    u = np.linspace(0, s2[-1], n)
    return np.stack([np.interp(u, s2, P[:, k]) for k in range(3)], 1)


def styled_path(a, th_root, th_leave, z_end, h_head, gap, vol, sway, waves, phase, curl_r, curl_turns, curl_dir,
                n=80, a_drift=0.0):
    """a styled clump (the idol makeover): over the head from th_root to th_leave, then falling free in a soft S to
    z_end, standing off the body by at least `gap` with a volume bulge `vol` (air under it: not draped), then a barrel
    curl at the end (curl_r m radius, curl_turns turns, curl_dir +1 an outward flip / -1 an under-curl, rolling about the
    clump's sideways axis). -> (P (n, 3), side (3,): the curl's roll axis, also the ribbon's width direction)"""
    nh = 16
    th = np.linspace(th_root, th_leave, nh)
    hh = h_head * (0.9 + 0.1 * np.clip(np.linspace(0, 1, nh) / 0.5, 0, 1))
    Ph = point(th, np.full(nh, a), hh)
    z0 = Ph[-1, 2]
    r0 = np.hypot(Ph[-1, 0], Ph[-1, 1] - YC)
    nd = 40
    z = np.linspace(z0, z_end, nd + 1)[1:]
    u = np.linspace(0, 1, nd)
    aa = a + a_drift * u ** 1.3
    rbody = r_body(z, aa)
    r = np.empty(nd)
    run, zmax = r0, z0
    for i in range(nd):                                          # the curtain: hanging from the widest point above
        if rbody[i] + gap >= run:
            run, zmax = rbody[i] + gap, z[i]
        r[i] = max(rbody[i] + gap, run - STY_RELAX * (zmax - z[i]))
    r = r + vol * np.sin(np.pi * u) ** 1.2
    r = _nd.gaussian_filter1d(r, 3, mode='nearest')
    r = np.maximum(r, rbody + gap * 0.7)
    Pd = np.stack([r * np.sin(np.radians(aa)), YC + r * np.cos(np.radians(aa)), z], 1)
    P = np.concatenate([Ph, Pd])
    rad = P - np.array([0, YC, 0]); rad[:, 2] = 0
    rad /= np.maximum(np.linalg.norm(rad, axis=1, keepdims=True), 1e-9)
    sidev = np.stack([rad[:, 1], -rad[:, 0], np.zeros(len(P))], 1)
    s0 = np.linspace(0, 1, len(P))
    P = P + sidev * (sway * np.sin(2 * np.pi * waves * s0 + phase) * np.clip((s0 - 0.25) / 0.3, 0, 1))[:, None]
    # the barrel curl
    end = P[-1]; d = P[-1] - P[-3]; d /= np.linalg.norm(d)
    o = rad[-1] * curl_dir
    o = o - d * (o @ d); o /= np.linalg.norm(o)
    nc = 28
    ph = np.linspace(0, 2 * np.pi * curl_turns, nc + 1)[1:]
    rc = curl_r * (1 - 0.3 * ph / ph[-1])
    Pc = end + np.outer(rc * np.sin(ph), d) + np.outer(rc * (1 - np.cos(ph)), o)
    P = np.concatenate([P, Pc])
    s2 = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    uu = np.linspace(0, s2[-1], n)
    P = np.stack([np.interp(uu, s2, P[:, k]) for k in range(3)], 1)
    side = np.cross(d, o); side /= np.linalg.norm(side)
    # per point: the surface's sideways (horizontal tangent) along the fall, blended into the roll axis in the curl
    radp = P - np.array([0, YC, 0]); radp[:, 2] = 0
    radp /= np.maximum(np.linalg.norm(radp, axis=1, keepdims=True), 1e-9)
    sidep = np.stack([radp[:, 1], -radp[:, 0], np.zeros(len(P))], 1)
    sidep *= np.sign(sidep @ side + 1e-9)[:, None]
    zc = end[2]
    w_ = np.clip((zc - P[:, 2]) / 0.01 + 0.0, 0, 1) * 0 + (np.linspace(0, 1, len(P)) > (1 - nc / (nh + nd + nc))).astype(float)
    w_ = _nd.gaussian_filter1d(w_, 3)
    S_ = sidep * (1 - w_)[:, None] + side[None] * w_[:, None]
    S_ /= np.maximum(np.linalg.norm(S_, axis=1, keepdims=True), 1e-9)
    return P, S_


def ribbon_side(m, P, side, width, thick, curl=0.3, s_vals=None, k=12):
    """a clump whose width runs along a fixed sideways axis (a rolled sheet: right for barrel curls, where the radial
    frame degenerates); a rounded lens cross-section, edges curled toward the clump's inner side."""
    n = len(P)
    T = np.gradient(P, axis=0); T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    sd = side if side.ndim == 2 else np.broadcast_to(side, P.shape)
    Bn = sd - T * np.sum(T * sd, axis=1, keepdims=True); Bn /= np.maximum(np.linalg.norm(Bn, axis=1, keepdims=True), 1e-12)
    Out = np.cross(Bn, T)
    u = np.linspace(0, 2 * np.pi, k, endpoint=False)
    rings = []
    for i in range(n - 1):
        cw = np.cos(u) * width[i] / 2
        st = np.sin(u) * thick[i] / 2 * (1 - 0.35 * np.cos(u) ** 2) - curl * thick[i] * np.cos(u) ** 2
        rings.append(P[i] + cw[:, None] * Bn[i] + st[:, None] * Out[i])
    V = np.concatenate(rings + [P[-1:]])
    sv = np.linspace(0, 1, n) if s_vals is None else s_vals
    m.pending_s = np.concatenate([np.repeat(sv[:-1], k), [sv[-1]]])
    m.pending_u = np.concatenate([np.tile(np.cos(u), n - 1), [0.0]])
    F = [list(range(k))[::-1]]
    for i in range(n - 2):
        for j in range(k):
            a_, b_ = i * k + j, i * k + (j + 1) % k
            F.append([a_, b_, b_ + k, a_ + k])
    tip, base = len(V) - 1, (n - 2) * k
    for j in range(k):
        F.append([base + j, base + (j + 1) % k, tip])
    m.add(V, F)


def styled_clump(m, cid, P, side, width, prof, tratio, root_thin=None):
    CID[0] += 1
    m.cur = cid
    s = np.linspace(0, 1, len(P))
    W = width * leaf(s, prof)
    Tk = np.maximum(W * tratio, 0.001)
    if root_thin:
        rt = (root_thin[0], max(root_thin[1], 0.55))                    # (a long ramp: no ledge where it thickens)
        Tk = Tk * (rt[0] + (1 - rt[0]) * np.clip(s / rt[1], 0, 1) ** 1.2)
    # the path is the clump's OUTER surface: it grows inward as it thickens (no step out)
    T_ = np.gradient(P, axis=0); T_ /= np.maximum(np.linalg.norm(T_, axis=1, keepdims=True), 1e-12)
    rh = P - C; rh -= T_ * np.sum(rh * T_, axis=1, keepdims=True)
    rh /= np.maximum(np.linalg.norm(rh, axis=1, keepdims=True), 1e-12)
    ncurl = int(0.25 * len(P))
    w_in = np.ones(len(P)); w_in[-ncurl:] = np.linspace(1, 0, ncurl)       # (not in the curl: it rolls)
    P = P - rh * (Tk * 0.5 * w_in)[:, None]
    LOCKS.append(dict(group=int(GROUP[0]), P=P.round(5).tolist(), width=float(width), width_max=float(width),
                      thick=float(Tk.max()), wprof=[float(x) for x in leaf(np.linspace(0, 1, 11), prof)], span=0.0))
    ribbon_side(m, P, side, W, Tk)


def leaf(s, prof):
    return np.interp(s, *zip(*prof))


def ribbon3(m, P, width, thick, twist, k=12, curl=0.45, s_vals=None):
    """a clump with volume: a rounded cross-section (a lens, edges curled in toward the head), twisting along its length
    (twist: radians per point, its broad face turning), frame from the radial direction; s_vals the vertices' position
    along the clump."""
    n = len(P)
    T = np.gradient(P, axis=0); T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    Out = P - C; Out -= np.sum(Out * T, axis=1, keepdims=True) * T
    Out /= np.maximum(np.linalg.norm(Out, axis=1, keepdims=True), 1e-12)
    Bn = np.cross(T, Out)
    c_, s_ = np.cos(twist)[:, None], np.sin(twist)[:, None]
    Bn, Out = c_ * Bn + s_ * Out, c_ * Out - s_ * Bn
    u = np.linspace(0, 2 * np.pi, k, endpoint=False)
    rings = []
    for i in range(n - 1):
        cw = np.cos(u) * width[i] / 2
        st = np.sin(u) * thick[i] / 2 * (1 - 0.35 * np.cos(u) ** 2) - curl * thick[i] * np.cos(u) ** 2
        rings.append(P[i] + cw[:, None] * Bn[i] + st[:, None] * Out[i])
    V = np.concatenate(rings + [P[-1:]])
    sv = np.linspace(0, 1, n) if s_vals is None else s_vals
    m.pending_s = np.concatenate([np.repeat(sv[:-1], k), [sv[-1]]])
    m.pending_u = np.concatenate([np.tile(np.cos(u), n - 1), [0.0]])
    F = [list(range(k))[::-1]]
    for i in range(n - 2):
        for j in range(k):
            a_, b_ = i * k + j, i * k + (j + 1) % k
            F.append([a_, b_, b_ + k, a_ + k])
    tip, base = len(V) - 1, (n - 2) * k
    for j in range(k):
        F.append([base + j, base + (j + 1) % k, tip])
    m.add(V, F)


def wave_clump(m, cid, P, width, prof, thick=0.005, curl_sec=0.3, sub=None, twist=0.0, tratio=None):
    """a clump; with `sub` it splits into sub-clumps from sub['from'] down (each a share of the width, diverging,
    lengths staggered by design), so the lower half reads as a hierarchy, not one flat noodle."""
    CID[0] += 1
    m.cur = cid
    n = len(P)
    s = np.linspace(0, 1, n)
    LOCKS.append(dict(group=int(GROUP[0]), P=P.round(5).tolist(), width=float(width), width_max=float(width),
                      thick=thick, wprof=[float(x) for x in leaf(np.linspace(0, 1, 11), prof)], span=0.0))
    W = width * leaf(s, prof)
    Tk = np.maximum((W * tratio) if tratio else thick * leaf(s, prof), 0.001)
    rr = S.get('root_thin')
    if rr:                                                       # thin where it emerges from under the crown
        Tk = Tk * (rr[0] + (1 - rr[0]) * np.clip(s / rr[1], 0, 1) ** 1.5)
    tw = twist * np.sin(np.pi * s) * np.sin(2 * np.pi * 0.8 * s + 0.6)
    if not sub:
        ribbon3(m, P, W, Tk, tw, curl=curl_sec)
        return
    s0 = sub['from']
    i0 = int(s0 * (n - 1))
    ribbon3(m, P[:i0 + 3], np.maximum(W[:i0 + 3], 0.002), Tk[:i0 + 3], tw[:i0 + 3], curl=curl_sec, s_vals=s[:i0 + 3])
    T = np.gradient(P, axis=0); T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    Out = P - C; Out -= np.sum(Out * T, axis=1, keepdims=True) * T
    Out /= np.maximum(np.linalg.norm(Out, axis=1, keepdims=True), 1e-12)
    side = np.cross(T, Out)
    shares = sub['shares']
    cum = np.concatenate([[0], np.cumsum(shares)]) / np.sum(shares)
    for j, sh in enumerate(shares):
        centre_off = (cum[j] + cum[j + 1]) / 2 - 0.5                     # (where in the clump's width this one sits)
        part = np.clip((s - s0) / (1 - s0), 0, 1)
        off = (centre_off * W[i0] + centre_off * sub['spread'] * width * part ** 1.3)[:, None] * side
        lf = sub['lengths'][j]
        idx = np.where(s >= s0 - 0.04)[0]
        idx = idx[s[idx] <= lf]
        if len(idx) < 4:
            continue
        Ps = P[idx] + off[idx] + Out[idx] * (0.003 * (j % 2))
        ss = s[idx]
        u_ = (ss - ss[0]) / max(ss[-1] - ss[0], 1e-9)
        wj = W[i0] * (sh / np.sum(shares)) * 1.15 * np.interp(u_, [0, 0.55, 0.85, 1.0], [1.0, 0.95, 0.5, 0.0])
        tj = np.maximum(wj * (tratio or 0.25), 0.001)
        ribbon3(m, Ps, wj, tj, tw[idx] + 0.3 * j, curl=curl_sec, s_vals=ss)


# ----------------------------------------------------------------------------------------------------------- the crown
crown = Mesh()
GROUP[0] = 1
Cr = S['crown']
cut_sheet(crown, -180, 180, lambda a: 0.5, lambda a: float(np.interp(abs(((a + 180) % 360) - 180), *zip(*Cr['edge']))),
          list(np.arange(-180, 180, 360.0 / Cr.get('scallops', 1))) if Cr.get('scallops') else [999.0],
          Cr.get('depth', 0.0), 0, 0, thick=0.004, na=300, nt=34, cid=1001, h_prof=Cr['h_prof'])
# the knot: a coil on her left with two tufts; the gathered locks into it
Kn = S['knot']
kd = dir_of(Kn['theta'], Kn['alpha'])
kbase = C + kd * (scalp_r(kd[None])[0][0] + Kn['lift'])
ax_ = kd
e1 = np.cross(ax_, [0, 0, 1.0]); e1 /= np.linalg.norm(e1); e2 = np.cross(ax_, e1)
tt = np.linspace(0, 2 * np.pi * Kn['turns'], 90)
coil = kbase + np.outer(np.cos(tt), e1) * Kn['r'] + np.outer(np.sin(tt), e2) * Kn['r'] + np.outer(tt / tt[-1], ax_) * Kn['rise']
GROUP[0] = 1
crown.cur = 1500
if not S.get('no_knot'):
  ribbon2(crown, coil, coil, np.full(len(coil), Kn['w']) * np.interp(np.linspace(0, 1, len(coil)), [0, 0.1, 0.85, 1], [0.6, 1, 1, 0.5]),
        np.full(len(coil), Kn['w'] * 0.7), k=10, curl=0.2)
for q, (da, db) in enumerate([] if S.get('no_knot') else Kn['tufts']):
    sq = np.linspace(0, 1, 18)[:, None]
    d_ = np.cos(np.radians(da)) * e1 + np.sin(np.radians(da)) * e2
    Pq = kbase + ax_ * Kn['rise'] * 0.6 + d_ * Kn['r'] * 1.2 * sq + ax_ * db * sq + d_ * 0.015 * sq ** 2 * 3
    ribbon2(crown, Pq, Pq, Kn['w'] * 0.9 * np.interp(sq[:, 0], [0, 0.4, 1], [0.8, 1, 0]), np.full(18, Kn['w'] * 0.3), k=8, curl=0.3)
kend = kd
for (th_s, al_s) in ([] if S.get('no_knot') else Kn['from']):
    gathered_lock(crown, dir_of(th_s, al_s), kend, end_lift=max(Kn['lift'] - 0.004, 0), w0=Kn['lock_w'], slack=0.003,
                  tension=0.006, thick=0.004)
out['hair_upper_back'] = crown

# ----------------------------------------------------------------------------------------------------- the long hair
back = Mesh()
Bk = S['back']
if S.get('styled'):
    Sy = S['styled']
    for li, Ly in enumerate(Sy['layers']):
        GROUP[0] = 3 if li == 0 else 2
        als = np.linspace(-Ly['al'], Ly['al'], Ly['n'])
        for i, a in enumerate(als):
            u = abs(a) / Ly['al']
            z_end = Ly['z_centre'] + (Ly['z_side'] - Ly['z_centre']) * u ** 1.3 + Ly.get('z_rhythm', [0])[i % len(Ly.get('z_rhythm', [0]))]
            cd = Ly['curl_dir'][i % len(Ly['curl_dir'])]
            cr = Ly['curl_r'] * Ly.get('curl_rhythm', [1.0])[i % len(Ly.get('curl_rhythm', [1.0]))]
            P, side = styled_path(a, Ly['th_root'], Ly['th_leave'], z_end, Ly['h_head'], Ly['gap'], Ly['vol'], Ly['sway'],
                                  Ly['waves'], Ly['phase0'] + Ly['phase_step'] * i, cr, Ly['curl_turns'], cd)
            wd = Ly['width'] * (1 - 0.15 * u) * Ly.get('rhythm', [1.0])[i % len(Ly.get('rhythm', [1.0]))]
            styled_clump(back, (3 if li == 0 else 2) * 1000 + i + 1, P, side, wd, Ly['prof'], Ly['tratio'], S.get('root_thin'))
    for side_, sg in (('L', 1), ('R', -1)):
        m = Mesh()
        GROUP[0] = 4 if sg > 0 else 5
        for i, F in enumerate(Sy['front']):
            P, sv_ = styled_path(sg * F['at'], F['th_root'], F['th_leave'], F['z_end'], F['h_head'], F['gap'], F['vol'],
                                 F['sway'] * sg, F['waves'], F['phase'], F['curl_r'], F['curl_turns'], F['curl_dir'],
                                 a_drift=sg * F.get('drift', 0))
            styled_clump(m, (4 if sg > 0 else 5) * 1000 + i + 1, P, sv_, F['width'], F['prof'], F['tratio'], S.get('root_thin'))
        out['hair_side_lock_' + side_] = m
    Bk = dict(Bk, layers=[])
for li, Ly in enumerate(Bk['layers']):
    GROUP[0] = 3 if li == 0 else 2
    n_ = Ly['n']
    als = np.linspace(-Ly['al'], Ly['al'], n_) + Ly.get('a_off', 0.0)
    for i, a in enumerate(als):
        u = abs(a) / Ly['al']
        z_tip = Ly['z_tip_centre'] + (Ly['z_tip_side'] - Ly['z_tip_centre']) * u ** 1.4
        P = clump_path(a, Ly['th_root'], Ly['th_leave'], z_tip, Ly['h_head'], Ly['standoff'], Ly['relax'],
                       sway=Ly['sway'] * (1 if i % 2 == 0 else 0.85), waves=Ly['waves'],
                       phase=Ly['phase0'] + Ly['phase_step'] * i, bump=Ly['bump'], curl=Ly['curl'])
        wd = Ly['width'] * (1 - 0.18 * u)
        if Ly.get('rhythm'):
            wd *= Ly['rhythm'][i % len(Ly['rhythm'])]
        sub = None
        if Ly.get('sub'):
            pat = Ly['sub']['patterns'][i % len(Ly['sub']['patterns'])]
            sub = dict(Ly['sub'], shares=pat['shares'], lengths=pat['lengths'])
        wave_clump(back, (3 if li == 0 else 2) * 1000 + i + 1, P, wd, Ly['prof'], thick=Ly.get('thick', 0.006),
                   sub=sub, twist=Ly.get('twist', 0.0), tratio=Ly.get('tratio'))
out['hair_lower_back'] = back

for side, sg in (('L', 1), ('R', -1)) if not S.get('styled') else ():
    m = Mesh()
    GROUP[0] = 4 if sg > 0 else 5
    for i, F in enumerate(S['front']):
        P = clump_path(sg * F['at'], F['th_root'], F['th_leave'], F['z_tip'], F['h_head'], F['standoff'], F['relax'],
                       sway=F['sway'] * sg, waves=F['waves'], phase=F['phase'], bump=F['bump'], curl=F['curl'],
                       a_drift=sg * F['drift'])
        sub = dict(F['sub'], shares=F['sub']['patterns'][0]['shares'], lengths=F['sub']['patterns'][0]['lengths']) if F.get('sub') else None
        wave_clump(m, (4 if sg > 0 else 5) * 1000 + i + 1, P, F['width'], F['prof'], thick=0.005, sub=sub,
                   twist=F.get('twist', 0.0), tratio=F.get('tratio'))
    out['hair_side_lock_' + side] = m

bangs = Mesh()
GROUP[0] = 6
Bg = S['bangs']
for k_, pc in enumerate(Bg['pieces']):
    a0, a1 = 180 + pc['at'] - pc['w'] / 2, 180 + pc['at'] + pc['w'] / 2
    so = [[x, y + pc.get('layer', 0) * 0.0025] for x, y in Bg['standoff']]
    cut_sheet(bangs, a0, a1, Bg['th0'], lambda a, pc=pc: pc['tip'], [180 + pc['at']], 0.0, 0, 0, thick=0.004,
              cid=6000 + k_ + 1, standoff=so, na=40, nt=36, centre=180 + pc['at'], wprof=Bg['blade'],
              bend=pc.get('bend', 0.0), s_bend=pc.get('s_bend', 0.0))
out['hair_bangs'] = bangs

if S.get('ahoge'):
    # a long, expressive ahoge: a tapered blade rising from the crown, arcing forward and curling over (a chain, so
    # it bounces); replaces the fitted one
    Ah = S['ahoge']
    GROUP[0] = 8
    d0_ = dir_of(Ah['theta'], Ah['alpha'])
    root = C + d0_ * (scalp_r(d0_[None])[0][0] + 0.012)
    fwd = np.array([np.sin(np.radians(Ah['alpha'])), np.cos(np.radians(Ah['alpha'])), 0.0])
    fwd -= d0_ * (fwd @ d0_); fwd /= np.linalg.norm(fwd)
    cps = np.array([[0, 0], [0.032, 0.004], [0.062, 0.028], [0.066, 0.062], [0.046, 0.086], [0.022, 0.082]]) * Ah['size']
    from scipy.interpolate import CubicSpline
    tt_ = np.linspace(0, 1, len(cps))
    cs = CubicSpline(tt_, cps, bc_type='natural')
    uu_ = np.linspace(0, 1, 48)
    q = cs(uu_)
    Pa = root[None] + np.outer(q[:, 0], d0_) + np.outer(q[:, 1], fwd)
    side_ = np.cross(d0_, fwd)
    Pa = Pa + np.outer(np.sin(np.pi * uu_) * Ah.get('lean', 0.0), side_)
    am = Mesh()
    am.cur = 8001
    wa = Ah['width'] * np.interp(uu_, [0, 0.25, 0.6, 0.85, 1.0], [0.7, 1.0, 0.85, 0.45, 0.0])
    ribbon3(am, Pa, wa, np.maximum(wa * 0.35, 0.0008), 0.6 * np.sin(np.pi * uu_), curl=0.3)
    out['hair_ahoge'] = am
# the buns are gone; the ahoge re-seated on the crown; the flyaways dropped
for nm in ('hair_bun_L', 'hair_bun_R', 'hair_flyaways'):
    M['objects'] = [o for o in M['objects'] if o['name'] != nm]
    for k_ in [k_ for k_ in A if k_.startswith('o/%s/' % nm)]:
        del A[k_]
if 'o/hair_ahoge/eval/V' in A and not S.get('ahoge'):
    Va = A['o/hair_ahoge/eval/V']
    base_ = Va[Va[:, 2] <= np.percentile(Va[:, 2], 5)].mean(0)
    v_ = (base_ - C) / np.linalg.norm(base_ - C)
    target = scalp_r(v_[None])[0][0] + 0.007
    for var_ in ('eval', 'raw'):
        k_ = 'o/hair_ahoge/%s/V' % var_
        if k_ in A:
            A[k_] = (A[k_] - v_ * (np.linalg.norm(base_ - C) - target)).astype(A[k_].dtype)
if STYLE.get('no_clips'):
    for nm in ('crab_0', 'star_1'):
        M['objects'] = [o for o in M['objects'] if o['name'] != nm]
        for k_ in [k_ for k_ in A if k_.startswith('o/%s/' % nm)]:
            del A[k_]
# the clips: moved to the knot (the crab under it, the star on it)
for nm, off in (('crab_0', Kn['crab_off']), ('star_1', Kn['star_off'])):
    k_ = 'o/%s/eval/V' % nm
    if k_ in A:
        cv = A[k_].mean(0)
        o_ = np.asarray(off)
        tgt = kbase + o_[0] * e1 + o_[1] * e2 + o_[2] * ax_          # (offsets in the knot's frame: e1, e2, outward)
        for var_ in ('eval', 'raw'):
            kk = 'o/%s/%s/V' % (nm, var_)
            if kk in A:
                A[kk] = (A[kk] - cv + tgt).astype(A[kk].dtype)

if STYLE.get('palette'):
    pal = STYLE['palette']
    sh = M['materials']['hair_shape']['shading']
    for k_ in ('lit', 'shade', 'deep', 'rim', 'lit_at', 'deep_at', 'rim_from', 'rim_amt', 'blend'):
        if k_ in pal:
            sh[k_] = pal[k_]
    if 'highlight_amount' in pal and isinstance(sh.get('highlight'), dict):
        sh['highlight']['amount'] = pal['highlight_amount']
if STYLE.get('ao'):
    build_topmap([m for m in out.values() if m.V])
_gsrc = open(os.path.join(HERE, 'groom.py')).read()
exec(_gsrc.split('# ------------------------------------------------------------------------------------------------ the bundle')[1])
json.dump(dict(centre=C.tolist(), L=float(M['assembly']['L']), locks=LOCKS), open(os.path.join(DST, 'locks.json'), 'w'))
