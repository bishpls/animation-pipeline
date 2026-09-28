"""Anime hair (docs/CHARKIT.md §2, hair): a hair volume fitted to the character's head (ray-cast from the head's centre, then
thickened, hung below the jaw), and a hairstyle of designed locks laid over it: each lock a spline through a few control
points (root, the S-bend, the tip) with a width profile that ends in a clean point; the silhouette set by a hem curve (tip
height round the head) with a length rhythm; layers (a darker inner layer for depth, the main mass, the fringe and the
face-framing locks, flyaways, the ahoge); shaded with the volume's smooth normals (big clean anime shadow shapes), a root
to tip gradient, drawn strand lines and an angel ring broken lock by lock; thin outlines that vanish at the tips.

Directions from the hair centre: az degrees around z from the front (+ = her left), el degrees up from the horizontal.
Every clump carries a UV layer 'lock': u across it (-1 .. 1), v along it (0 root .. 1 tip).
"""
import math, random
import numpy as np

from . import anime_head as ah, head as headlib

DEFAULT_STYLE = {
    'seed': 7,
    'part': 6.0,            # part azimuth (degrees; + = her left)
    'thick': 1.0,           # volume thickness multiplier
    'crown': 1.0,           # crown height multiplier
    'length': 0.25,         # how far the hanging mass drops below the jaw line, in L
    # the silhouette's lower edge: tip elevation by |azimuth from the front| (degrees), bangs excluded
    'hem': [(50, -46), (75, -60), (110, -66), (150, -64), (180, -62)],
    'hem_var': [3, -5, 1, -7, 4, -2, -6, 2],   # a repeating length rhythm along the hem (degrees)
    'flick': 0.06,          # hem tips flick out (+) / tuck in (-), in L
    'wave': 0.6,            # S-curve strength of the long locks
    'back': {'count': 14, 'width': 0.15, 'inner': 12, 'sway': 14.0},
    'sides': {'count': 2, 'az': (56, 72), 'width': 0.095, 'drop': 6.0},
    'bangs': {
        # main fringe locks: (tip azimuth, tip elevation, width scale), her right to her left
        'tips': [(-46, -4, 0.9), (-28, -10, 1.1), (-10, -4, 0.9), (2, -19, 0.7), (16, -8, 1.0), (33, -12, 1.1),
                 (48, -2, 0.9)],
        'width': 0.13, 'thick': 0.32, 'bow': 0.04, 'tuck': 0.035, 'sub': True, 'tip': 0.32, 'sharp': 1.1,
    },
    'flyaways': [(-95, -48), (100, -52), (160, -58), (-150, -55), (40, 70), (-60, 62)],   # (az, el) roots of stray locks
    'ahoge': True,
}


def _style(s):
    S = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAULT_STYLE.items()}
    for k, v in (s or {}).items():
        if isinstance(v, dict) and isinstance(S.get(k), dict):
            S[k].update(v)
        else:
            S[k] = v
    return S


def _dir(az, el):
    a, e = math.radians(az), math.radians(el)
    return np.array([math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)])


class Volume:
    """The hair mass's outer surface. Built from the head: its radius along each direction from the hair centre (a ray-cast
    grid), plus a thickness that is fullest at the crown and thin at the hairline; below el0 the mass hangs: straight down,
    bulging a little, the ends curling in."""

    def __init__(self, H, centre, S, target):
        L = H.L
        self.L = L
        self.c = np.asarray(centre) + np.array([0.0, (H.db - H.df) / 2, 0.06 * L])
        self.S = S
        TV, TT = target
        TVw = TV + np.asarray(centre)
        self.azs = np.arange(-180, 181, 5.0)
        self.els = np.arange(-40, 91, 5.0)
        D = np.array([_dir(a, e) for e in self.els for a in self.azs])
        t = ah.raycast(self.c, D, TVw, TT)
        t = np.where(np.isfinite(t), t, np.nan).reshape(len(self.els), len(self.azs))
        # fill misses (under the jaw) from the row above
        for i in range(len(self.els) - 2, -1, -1):
            row = t[i]
            bad = np.isnan(row)
            row[bad] = t[i + 1][bad]
        self.r = np.nan_to_num(t, nan=0.4 * L)
        self.el0 = -22.0

    def head_r(self, az, el):
        az = ((az + 180) % 360) - 180
        el = min(90.0, max(-40.0, el))
        i = (el + 40) / 5.0; j = (az + 180) / 5.0
        i0, j0 = int(min(len(self.els) - 2, math.floor(i))), int(min(len(self.azs) - 2, math.floor(j)))
        fi, fj = i - i0, j - j0
        r = self.r
        return ((1 - fi) * ((1 - fj) * r[i0, j0] + fj * r[i0, j0 + 1]) + fi * ((1 - fj) * r[i0 + 1, j0] + fj * r[i0 + 1, j0 + 1]))

    def thickness(self, az, el):
        L, S = self.L, self.S
        front = max(0.0, math.cos(math.radians(az)))
        crown = max(0.0, math.sin(math.radians(max(el, 0))))
        t = (0.026 + 0.040 * crown * S['crown'] + 0.010 * (1 - front)) * L * S['thick']
        # thin over the forehead (the bangs lie close) and at the temples
        t *= 1 - 0.55 * front * max(0.0, 1 - max(0.0, el - 10) / 45)
        return t

    def point(self, az, el, r=1.0):
        if el >= self.el0:
            rr = self.head_r(az, el) + self.thickness(az, el)
            return self.c + _dir(az, el) * rr * r
        p0 = self.point(az, self.el0, 1.0)
        f = (self.el0 - el) / 60.0                         # 0 at el0 .. 1 at the ends
        hc = p0 - self.c; hc[2] = 0
        bulge = 1 + 0.08 * math.sin(min(1.0, f) * math.pi * 0.7) - 0.12 * max(0.0, f - 0.8)
        drop = (self.S['length'] + 0.35) * self.L
        p = self.c + hc * bulge * r
        p[2] = p0[2] - drop * f
        return p

    def normal(self, az, el):
        p = self.point(az, el)
        da = self.point(az + 1, el) - self.point(az - 1, el)
        de = self.point(az, el + 1) - self.point(az, el - 1)
        n = np.cross(de, da)
        h = p - self.c
        if n @ h < 0:
            n = -n
        ln = np.linalg.norm(n)
        return n / ln if ln > 1e-12 else h / np.linalg.norm(h)


def catmull(P, n):
    """a uniform Catmull-Rom curve through control points P (k, d), sampled at n + 1 points."""
    P = np.asarray(P, float)
    ext = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    segs = len(P) - 1
    out = []
    for i in range(n + 1):
        t = i / n * segs
        k = min(int(t), segs - 1); u = t - k
        p0, p1, p2, p3 = ext[k:k + 4]
        out.append(0.5 * (2 * p1 + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3))
    return np.array(out)


def sweep(V, pts, width, th=0.34, w_root=0.55, s_max=0.28, tip=0.45, sharp=1.5, twist=0.0, n=28, sides=10):
    """one lock: a lens-section tube along a Catmull-Rom path through control points (az, el, r) on the volume, its width
    rising from the root to s_max, holding, then tapering over the last `tip` share to a sharp point; twist (degrees at the
    tip) turns it to show an edge. -> (verts, faces, uvs 'lock' (across, along))."""
    Q = catmull(pts, n)
    C = np.array([V.point(a, e, r) for a, e, r in Q])
    Nr = np.array([V.normal(a, e) for a, e, _ in Q])
    verts, uvs = [], []
    for i in range(n + 1):
        s = i / n
        d = C[min(i + 1, n)] - C[max(i - 1, 0)]
        d /= max(1e-12, np.linalg.norm(d))
        side = np.cross(d, Nr[i]); ls = np.linalg.norm(side)
        side = side / ls if ls > 1e-9 else np.array([1.0, 0, 0])
        up = np.cross(side, d); up /= max(1e-12, np.linalg.norm(up))
        if up @ Nr[i] < 0:
            up = -up
        tw = math.radians(twist) * s * s
        side, up = side * math.cos(tw) + up * math.sin(tw), up * math.cos(tw) - side * math.sin(tw)
        rise = w_root + (1 - w_root) * (3 * min(1, s / s_max) ** 2 - 2 * min(1, s / s_max) ** 3)
        taper = min(1.0, (1 - s) / tip) ** sharp if tip > 0 else 1.0
        w = width * rise * taper + 1e-6
        t_ = max(w * th, 0.18 * width * taper)
        for k in range(sides):
            ph = 2 * math.pi * k / sides
            cx, sy = math.cos(ph), math.sin(ph)
            px = math.copysign(abs(cx) ** 0.8, cx) * w
            py = sy * t_ * (1.0 if sy > 0 else 0.5) * (1 - 0.35 * abs(cx))       # a ridge down the middle
            verts.append(C[i] + side * px + up * py); uvs.append((cx, s))
    faces = []
    for i in range(n):
        for k in range(sides):
            a, b = i * sides + k, i * sides + (k + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    faces.append(tuple(range(sides - 1, -1, -1)))
    return np.array(verts), faces, uvs


class Builder:
    def __init__(self):
        self.v, self.f, self.uv = [], [], []

    def add(self, verts, faces, uvs):
        o = sum(len(x) for x in self.v)
        self.v.append(verts); self.f += [tuple(i + o for i in f) for f in faces]; self.uv += list(uvs)

    def data(self):
        return (np.vstack(self.v) if self.v else np.zeros((0, 3))), self.f, self.uv


def hem(S, az):
    """the silhouette's tip elevation at an azimuth (degrees from the front, either side)."""
    a = abs(((az + 180) % 360) - 180)
    xs, ys = zip(*S['hem'])
    return float(np.interp(a, xs, ys))


def generate(H, centre, target, style=None):
    """the hairstyle's meshes by layer (numpy): {name: (verts, faces, uvs)}, and the volume (for the normals proxy).
    Layers: hair_cap (under everything), hair_inner (darker, fills), hair_main (the back and sides), hair_front (bangs,
    face-framing locks, flyaways, ahoge)."""
    S = _style(style)
    L = H.L
    V = Volume(H, centre, S, target)
    part = S['part']
    rhythm = S['hem_var']
    wv = S['wave']
    out = {}

    def long_lock(az0, el0, az_t, el_t, r0=0.99, bow=0.025, flick=None, sway=None, k=0):
        """a long lock from a root down to the hem: an S-bend (sway one way high, the other low), bowing out, the tip
        flicking out (or tucking) past the hem."""
        fl = S['flick'] if flick is None else flick
        sway = S['back'].get('sway', 10.0) if sway is None else sway
        sg = 1 if k % 2 == 0 else -1
        e1, e2 = el0 + (el_t - el0) * 0.35, el0 + (el_t - el0) * 0.72
        a1 = az0 + (az_t - az0) * 0.35 + sg * sway * wv
        a2 = az0 + (az_t - az0) * 0.72 - sg * sway * wv * 0.8
        return [(az0, el0, r0), (a1, e1, r0 + bow), (a2, e2, r0 + bow * 1.2), (az_t, el_t, r0 + bow + fl / 0.4)]

    # the inner layer: wide, darker locks round the sides and back (fills the mass, gives the top layer depth)
    B = Builder()
    ni = S['back']['inner']
    for k in range(ni):
        az0 = part + 60 + 240 * (k + 0.5) / ni
        el_t = hem(S, az0) + rhythm[(k + 3) % len(rhythm)] + 4
        B.add(*sweep(V, long_lock(az0, 70, az0 + 3, el_t, r0=0.975, bow=0.01, flick=S['flick'] * 0.6, k=k),
                     S['back']['width'] * 1.25 * L, th=0.4, tip=0.4))
    out['hair_inner'] = B.data()

    # the main layer: locks from the crown (along the part) down the sides and back to the hem
    B = Builder()
    nb = S['back']['count']
    for k in range(nb):
        t = (k + 0.5) / nb
        az0 = part + 52 + 256 * t
        el_r = 86 - 6 * abs(math.sin(math.radians(az0 - part)))
        az_t = az0 + 4 * math.sin(k * 1.7)
        el_t = hem(S, az_t) + rhythm[k % len(rhythm)]
        wid = S['back']['width'] * L * (0.9 + 0.2 * ((k * 7) % 5) / 4)
        B.add(*sweep(V, long_lock(az0, el_r, az_t, el_t, k=k), wid, th=0.36, tip=0.42, twist=8 * math.sin(k * 2.3)))
    out['hair_main'] = B.data()

    # the front: the fringe, sub-locks behind it, the face-framing locks, flyaways, the ahoge
    B = Builder()
    G = S['bangs']
    tips = G['tips']
    for k, (az_t, el_t, ws) in enumerate(tips):
        az_r = part + (az_t - part) * 0.22
        pts = [(az_r, 80, 0.995), (az_r + (az_t - az_r) * 0.25, 56, 1.0 + G['bow']),
               (az_r + (az_t - az_r) * 0.75, 28 + 0.4 * el_t, 1.0 + G['bow'] * 0.8), (az_t, el_t, 1.0 - G['tuck'])]
        B.add(*sweep(V, pts, G['width'] * L * ws, th=G['thick'], w_root=0.8, s_max=0.3, tip=G['tip'], sharp=G['sharp'],
                     twist=-6 * math.copysign(1, az_t - part)))
    if G.get('sub'):
        for (a0, e0, _), (a1, e1, _) in zip(tips, tips[1:]):
            az_t = (a0 + a1) / 2; el_t = max(e0, e1) + 7
            az_r = part + (az_t - part) * 0.3
            pts = [(az_r, 78, 0.985), (az_r + (az_t - az_r) * 0.25, 54, 1.0 + G['bow'] * 0.7),
                   (az_r + (az_t - az_r) * 0.75, 28 + 0.4 * el_t, 1.0 + G['bow'] * 0.5), (az_t, el_t, 0.985)]
            B.add(*sweep(V, pts, G['width'] * L * 0.6, th=G['thick'], w_root=0.8, tip=G['tip'], sharp=G['sharp']))
    Sd = S['sides']
    for sx in (-1, 1):
        for j in range(Sd['count']):
            az = Sd['az'][0] + (Sd['az'][1] - Sd['az'][0]) * j / max(1, Sd['count'] - 1)
            el_t = hem(S, az) - Sd['drop'] + rhythm[(j * 3) % len(rhythm)]
            pts = [(sx * az * 0.8, 58, 1.0), (sx * az * 0.93, 22, 1.03), (sx * az * 0.9, -20, 1.02),
                   (sx * (az - 6), el_t, 1.02 + S['flick'] * 0.5 / 0.4)]
            B.add(*sweep(V, pts, Sd['width'] * L * (1.1 - 0.15 * j), th=0.36, tip=0.45, twist=-10 * sx))
    for k, (az, el) in enumerate(S['flyaways']):
        sg = 1 if k % 2 == 0 else -1
        if el > 0:                                   # a stray lock off the crown, arcing out
            pts = [(az, el + 12, 1.0), (az + 8 * sg, el, 1.12), (az + 14 * sg, el - 14, 1.18)]
        else:                                        # a curl off the hem
            pts = [(az, el + 18, 1.0), (az + 6 * sg, el, 1.06), (az + 14 * sg, el - 6, 1.16), (az + 18 * sg, el + 4, 1.2)]
        B.add(*sweep(V, pts, 0.035 * L, th=0.4, w_root=0.8, tip=0.6, n=16))
    if S['ahoge']:
        base = np.array([part - 6, 84, 1.0])
        pts = [tuple(base), (part - 2, 92, 1.12), (part + 14, 98, 1.25), (part + 30, 92, 1.3)]
        B.add(*sweep(V, pts, 0.028 * L, th=0.5, w_root=0.9, tip=0.7, sharp=1.2, n=18))
    out['hair_front'] = B.data()

    # the cap: a smooth shell under everything so no scalp shows (open over the face)
    NA, NE = 64, 26
    verts, uvs = [], []
    for i in range(NE + 1):
        el = 90 - 130 * i / NE
        for k in range(NA):
            verts.append(V.point(-180 + 360 * k / NA, el, 0.965)); uvs.append((0.0, 0.0))
    faces = []
    for i in range(NE):
        for k in range(NA):
            az = -180 + 360 * (k + 0.5) / NA
            el = 90 - 130 * (i + 0.5) / NE
            if abs(az) < 58 and el < 30:
                continue
            a, b = i * NA + k, i * NA + (k + 1) % NA
            faces.append((a, b, b + NA, a + NA))
    out['hair_cap'] = (np.array(verts), faces, uvs)
    return out, V


def proxy_mesh(V, NA=72, NE=40):
    """the volume as a mesh (the clumps take their normals from it). -> (verts, faces)."""
    verts = []
    for i in range(NE + 1):
        el = 90 - 160 * i / NE
        for k in range(NA):
            verts.append(V.point(-180 + 360 * k / NA, el))
    verts = np.array(verts)
    faces = []
    for i in range(NE):
        for k in range(NA):
            f = (i * NA + k, i * NA + (k + 1) % NA, (i + 1) * NA + (k + 1) % NA, (i + 1) * NA + k)
            P = verts[list(f)]
            n = np.cross(P[2] - P[0], P[3] - P[1])
            faces.append(f if n @ (P.mean(0) - V.c) >= 0 else f[::-1])       # outward (the proxy is open at the bottom)
    return verts, faces


def material(name, lit, shade_c, deep, ring=(1.0, 0.86, 0.80), head_z=0.0, ring_el=40.0, thresh=0.5, root_mul=0.82,
             lines=0.35, line_col=(0.55, 0.45, 0.62)):
    """toon3 plus the angel ring: a band at ring_el above the hair centre, on each clump's centre line, on the lit side."""
    from . import shade
    m = shade.toon3(name, lit, shade_c, deep, thresh=thresh)
    nt = m.node_tree; N = nt.nodes.new; Lk = nt.links.new
    em = next(n for n in nt.nodes if n.type == 'EMISSION')
    src = em.inputs['Color'].links[0].from_socket
    uv = N('ShaderNodeUVMap'); uv.uv_map = 'lock'
    sep = N('ShaderNodeSeparateXYZ'); Lk(uv.outputs[0], sep.inputs[0])
    across = N('ShaderNodeMath'); across.operation = 'ABSOLUTE'; Lk(sep.outputs['X'], across.inputs[0])
    mid = N('ShaderNodeMapRange'); mid.inputs['From Min'].default_value = 0.95; mid.inputs['From Max'].default_value = 0.85
    Lk(across.outputs[0], mid.inputs['Value'])
    tc = N('ShaderNodeTexCoord')
    rel = N('ShaderNodeVectorMath'); rel.operation = 'SUBTRACT'; rel.inputs[1].default_value = tuple(head_z)
    Lk(tc.outputs['Object'], rel.inputs[0])
    sp = N('ShaderNodeSeparateXYZ'); Lk(rel.outputs[0], sp.inputs[0])
    hx = N('ShaderNodeCombineXYZ'); Lk(sp.outputs['X'], hx.inputs[0]); Lk(sp.outputs['Y'], hx.inputs[1])
    hl = N('ShaderNodeVectorMath'); hl.operation = 'LENGTH'; Lk(hx.outputs[0], hl.inputs[0])
    el = N('ShaderNodeMath'); el.operation = 'ARCTAN2'; Lk(sp.outputs['Z'], el.inputs[0]); Lk(hl.outputs['Value'], el.inputs[1])
    dz = N('ShaderNodeMath'); dz.operation = 'SUBTRACT'; dz.inputs[1].default_value = math.radians(ring_el)
    Lk(el.outputs[0], dz.inputs[0])
    adz = N('ShaderNodeMath'); adz.operation = 'ABSOLUTE'; Lk(dz.outputs[0], adz.inputs[0])
    u2 = N('ShaderNodeMath'); u2.operation = 'POWER'; u2.inputs[1].default_value = 2.0; Lk(across.outputs[0], u2.inputs[0])
    wid = N('ShaderNodeMath'); wid.operation = 'MULTIPLY_ADD'; wid.inputs[1].default_value = -math.radians(5.0)
    wid.inputs[2].default_value = math.radians(5.0); Lk(u2.outputs[0], wid.inputs[0])
    lens = N('ShaderNodeMath'); lens.operation = 'SUBTRACT'; Lk(wid.outputs[0], lens.inputs[0]); Lk(adz.outputs[0], lens.inputs[1])
    band = N('ShaderNodeMapRange'); band.inputs['From Min'].default_value = 0.0
    band.inputs['From Max'].default_value = math.radians(1.2)
    Lk(lens.outputs[0], band.inputs['Value'])
    lw = N('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value = 0.5
    face = N('ShaderNodeMapRange'); face.inputs['From Min'].default_value = 0.55; face.inputs['From Max'].default_value = 0.25
    Lk(lw.outputs['Facing'], face.inputs['Value'])
    ramp = next(n for n in nt.nodes if n.type == 'VALTORGB' and abs(n.color_ramp.elements[0].position - (thresh - 0.015)) < 1e-6)
    m1 = N('ShaderNodeMath'); m1.operation = 'MULTIPLY'; Lk(mid.outputs[0], m1.inputs[0]); Lk(band.outputs[0], m1.inputs[1])
    m2 = N('ShaderNodeMath'); m2.operation = 'MULTIPLY'; Lk(m1.outputs[0], m2.inputs[0]); Lk(face.outputs[0], m2.inputs[1])
    m3 = N('ShaderNodeMath'); m3.operation = 'MULTIPLY'; Lk(m2.outputs[0], m3.inputs[0]); Lk(ramp.outputs['Color'], m3.inputs[1])
    fade = N('ShaderNodeMath'); fade.operation = 'MULTIPLY'; fade.inputs[1].default_value = 0.6
    Lk(m3.outputs[0], fade.inputs[0])
    hi = N('ShaderNodeMix'); hi.data_type = 'RGBA'; hi.inputs['B'].default_value = (*shade.lin(ring), 1)
    Lk(fade.outputs[0], hi.inputs['Factor']); Lk(src, hi.inputs['A'])
    # root -> tip gradient (darker, richer at the roots)
    g = N('ShaderNodeMapRange'); g.inputs['From Min'].default_value = 0.0; g.inputs['From Max'].default_value = 0.55
    g.inputs['To Min'].default_value = root_mul; g.inputs['To Max'].default_value = 1.0
    Lk(sep.outputs['Y'], g.inputs['Value'])
    gm = N('ShaderNodeVectorMath'); gm.operation = 'SCALE'
    Lk(hi.outputs['Result'], gm.inputs[0]); Lk(g.outputs['Result'], gm.inputs['Scale'])
    # drawn strand lines: two thin lines along each lock, fading before the tip
    off = N('ShaderNodeMath'); off.operation = 'SUBTRACT'; off.inputs[1].default_value = 0.5
    Lk(across.outputs[0], off.inputs[0])
    aoff = N('ShaderNodeMath'); aoff.operation = 'ABSOLUTE'; Lk(off.outputs[0], aoff.inputs[0])
    ln = N('ShaderNodeMapRange'); ln.inputs['From Min'].default_value = 0.025; ln.inputs['From Max'].default_value = 0.06
    ln.inputs['To Min'].default_value = 1.0; ln.inputs['To Max'].default_value = 0.0
    Lk(aoff.outputs[0], ln.inputs['Value'])
    lf = N('ShaderNodeMapRange'); lf.inputs['From Min'].default_value = 0.5; lf.inputs['From Max'].default_value = 0.8
    lf.inputs['To Min'].default_value = lines; lf.inputs['To Max'].default_value = 0.0
    Lk(sep.outputs['Y'], lf.inputs['Value'])
    lm = N('ShaderNodeMath'); lm.operation = 'MULTIPLY'; Lk(ln.outputs['Result'], lm.inputs[0]); Lk(lf.outputs['Result'], lm.inputs[1])
    lmix = N('ShaderNodeMix'); lmix.data_type = 'RGBA'; lmix.blend_type = 'MULTIPLY'
    lmix.inputs['B'].default_value = (*shade.lin(line_col), 1)
    Lk(lm.outputs[0], lmix.inputs['Factor']); Lk(gm.outputs[0], lmix.inputs['A'])
    Lk(lmix.outputs['Result'], em.inputs['Color'])
    return m


def build(A, arm, style=None, colors=None):
    """Blender objects for the hairstyle on an assembled character A (charkit.character.assemble), parented to the head
    bone. colors: dict(lit, shade, deep, ring, inner, line, strand). -> [objects]."""
    import bmesh
    from . import character, shade
    C = dict(lit=(0.96, 0.93, 0.98), shade=(0.72, 0.74, 0.90), deep=(0.52, 0.52, 0.72), ring=(1.0, 1.0, 1.0),
             inner=0.55, line=(0.36, 0.34, 0.50), strand=(0.62, 0.58, 0.78))
    C.update(colors or {})
    Hd = A['head']
    H, centre = Hd['H'], Hd['centre']
    meshes, V = generate(H, centre, Hd['info']['target'], style)
    pv, pf = proxy_mesh(V)
    proxy = character._mesh('hair_normals_proxy', pv, pf, None, [])
    proxy.hide_render = True; proxy.hide_viewport = True
    character._to_head(proxy, arm)
    top = material('hair', C['lit'], C['shade'], C['deep'], ring=C['ring'], head_z=tuple(V.c), line_col=C['strand'],
                   lines=0.22)
    k = C['inner']
    inner = material('hair_inner', tuple(np.array(C['lit']) * k + np.array(C['shade']) * (1 - k)),
                     tuple(np.array(C['shade']) * 0.94), tuple(np.array(C['deep']) * 0.95), ring=C['ring'], head_z=tuple(V.c),
                     line_col=C['strand'], lines=0.0)
    obs = []
    for name, (v, f, uv) in meshes.items():
        m = {'hair_inner': inner, 'hair_cap': inner}.get(name, top)
        ob = character._mesh(name, v, f, None, [m])
        me = ob.data
        lay = me.uv_layers.new(name='lock')
        for p in me.polygons:
            p.use_smooth = True
            for li in p.loop_indices:
                lay.data[li].uv = uv[me.loops[li].vertex_index]
        bm = bmesh.new(); bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me); bm.free()
        dt = ob.modifiers.new('volume_normals', 'DATA_TRANSFER')
        dt.object = proxy; dt.use_loop_data = True; dt.data_types_loops = {'CUSTOM_NORMAL'}
        dt.loop_mapping = 'POLYINTERP_NEAREST'; dt.mix_factor = 0.85 if name != 'hair_cap' else 1.0
        if name != 'hair_cap':
            # thin outlines that vanish toward the tips (a vertex group drives the shell's thickness)
            g = ob.vertex_groups.new(name='outline_w')
            along = np.array([u[1] for u in uv])
            for w_ in np.unique(np.round(1 - np.clip((along - 0.6) / 0.4, 0, 1) ** 1.5, 2)):
                ids = np.nonzero(np.round(1 - np.clip((along - 0.6) / 0.4, 0, 1) ** 1.5, 2) == w_)[0]
                g.add([int(i) for i in ids], float(w_), 'REPLACE')
            sol = shade.outline(ob, thick=0.0011, color=C['line'], name='hair_line')
            sol.vertex_group = 'outline_w'; sol.thickness_vertex_group = 0.0
        character._to_head(ob, arm)
        obs.append(ob)
    return obs
