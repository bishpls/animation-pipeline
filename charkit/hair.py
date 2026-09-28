"""Anime hair (docs/CHARKIT.md §2, hair): a hair volume fitted to the character's head (ray-cast from the head's centre, then
thickened, hung below the jaw), and a hairstyle spec of clump layers laid over it: bangs, side locks, the crown and back
mass, an under layer, the ahoge; lens-section clumps that taper to points, wave and curl at the tips, shaded with the
volume's smooth normals (big clean anime shadow shapes) and an angel-ring highlight broken clump by clump.

Directions from the hair centre: az degrees around z from the front (+ = her left), el degrees up from the horizontal.
Every clump carries a UV layer 'lock': u across it (-1 .. 1), v along it (0 root .. 1 tip).
"""
import math, random
import numpy as np

from . import anime_head as ah, head as headlib

DEFAULT_STYLE = {
    'seed': 7,
    'part': 8.0,            # part azimuth (degrees; + = her left)
    'thick': 1.0,           # volume thickness multiplier
    'crown': 1.0,           # crown height multiplier
    'length': 0.55,         # back length below the chin, in L
    'side_len': 0.35,       # face-framing locks below the chin, in L
    'bangs': {
        'count': 9, 'span': 118.0, 'tip_el': [8, -2, 4, -12, 2, -8, 6, -1, 10],   # tip elevations across the fringe
        'width': 0.07, 'thick': 0.30, 'sweep': 14.0, 'curve_in': 0.012, 'tip': 1.9,
    },
    'sides': {'az': [62, 74], 'width': [0.07, 0.08], 'wave': 0.016, 'curl': 0.008},
    'back': {'count': 24, 'width': 0.10, 'wave': 0.018, 'curl': 0.012},
    'under': {'count': 16, 'width': 0.12},
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


def lock(V, az_f, el_f, r_f, n=22, wave=0.0, waves=1.5, phase=0.0, bob=0.0, curl=0.0, lift=0.0):
    """a clump's centre line over the volume (az/el/r functions of s in [0, 1]), with sideways waves along the surface, in-out
    bobbing, and the last quarter curling out. -> (points (n+1, 3), outward normals)."""
    pts, nrs = [], []
    for i in range(n + 1):
        s = i / n
        az, el, r = az_f(s), el_f(s), r_f(s)
        p = V.point(az, el, r)
        nr = V.normal(az, el)
        tg = V.point(az + 1, el, r) - V.point(az - 1, el, r)
        tg /= max(1e-12, np.linalg.norm(tg))
        p = p + tg * wave * math.sin(2 * math.pi * waves * s + phase) * s ** 0.8
        p = p + nr * bob * math.sin(2 * math.pi * waves * s + phase + 1.3) * s ** 0.7
        if curl and s > 0.72:
            u = (s - 0.72) / 0.28
            p = p + nr * curl * 0.6 * u * u + np.array([0, 0, curl * 1.1 * u ** 2])
        if s > 0.8:
            p = p - nr * 0.012 * ((s - 0.8) / 0.2) ** 2 * V.L / 0.25
        pts.append(p + nr * lift); nrs.append(nr)
    return np.array(pts), np.array(nrs)


def clump(path, normals, width, thick=0.38, root_taper=0.45, tip=0.8, sides=10):
    """a tapered clump along a path with its outward normals: lens cross-section, fuller outside, a sharp point.
    -> (verts, faces, uvs per vertex)."""
    n = len(path) - 1
    verts, uvs = [], []
    for i, c in enumerate(path):
        s = i / n
        d = path[min(i + 1, n)] - path[max(i - 1, 0)]
        d /= max(1e-12, np.linalg.norm(d))
        nr = normals[i]
        side = np.cross(d, nr)
        ls = np.linalg.norm(side)
        side = side / ls if ls > 1e-6 else np.array([1.0, 0, 0])
        up = np.cross(side, d); up /= max(1e-12, np.linalg.norm(up))
        if up @ nr < 0:
            up = -up
        wr = root_taper + (1 - root_taper) * min(1.0, s / 0.2)
        belly = 1 + 0.25 * math.sin(math.pi * min(1.0, s / 0.85))
        tl = tip * 0.28
        wt = max(0.02, 1 - max(0.0, (s - (1 - tl)) / tl)) ** 0.9
        w = width * wr * wt * belly
        th = w * thick
        for k in range(sides):
            ph = 2 * math.pi * k / sides
            cx, sy = math.cos(ph), math.sin(ph)
            px = math.copysign(abs(cx) ** 0.75, cx) * w
            py = sy * th * (1.0 if sy > 0 else 0.55)
            verts.append(c + side * px + up * py); uvs.append((cx, s))
    faces = []
    for i in range(n):
        for k in range(sides):
            a, b = i * sides + k, i * sides + (k + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    faces.append(tuple(range(sides - 1, -1, -1)))                  # root cap
    return np.array(verts), faces, uvs


class Builder:
    def __init__(self):
        self.v, self.f, self.uv = [], [], []

    def add(self, verts, faces, uvs):
        o = sum(len(x) for x in self.v)
        self.v.append(verts); self.f += [tuple(i + o for i in f) for f in faces]; self.uv += list(uvs)

    def data(self):
        return (np.vstack(self.v) if self.v else np.zeros((0, 3))), self.f, self.uv


def generate(H, centre, target, style=None):
    """the hairstyle's meshes (numpy): {name: (verts, faces, uvs)}, and the volume (for the normals proxy)."""
    S = _style(style)
    L = H.L
    V = Volume(H, centre, S, target)
    R = random.Random(S['seed'])
    part = S['part']
    out = {}

    # under layer: fat clumps round the sides and back (fills the mass, darker)
    B = Builder()
    U = S['under']
    for k in range(U['count']):
        az0 = part + 62 + (360 - 124) * k / max(1, U['count'] - 1) + R.uniform(-4, 4)
        el_end = -60 + R.uniform(-8, 6)
        p, n = lock(V, lambda s, a=az0: a + 5 * s, lambda s, e=el_end: 72 - (72 - e) * s, lambda s: 0.975 + 0.02 * s,
                    wave=0.012 * L / 0.25, bob=0.006, phase=R.uniform(0, 6), curl=0.02)
        B.add(*clump(p, n, U['width'] * L * (0.9 + 0.2 * R.random()), thick=0.42))
    out['hair_under'] = B.data()

    # main mass: from the crown down the sides and back, overlapping, waving, tips curling out
    B = Builder()
    K = S['back']
    for k in range(K['count']):
        az0 = part + 58 + (360 - 116) * k / max(1, K['count'] - 1) + R.uniform(-3, 3)
        swirl = R.uniform(-10, 10)
        el_end = -60 + (0, -12, 5, -7, 9, -3, -14, 3)[k % 8] + R.uniform(-3, 3)
        p, n = lock(V, lambda s, a=az0, w=swirl: a + w * s, lambda s, e=el_end: 86 - (86 - e) * s,
                    lambda s: 1.0 + 0.012 * math.sin(s * 3),
                    wave=K['wave'] * L / 0.25 * (0.8 + 0.5 * R.random()), bob=0.012 * (0.8 + 0.6 * R.random()),
                    waves=1.5 + 0.5 * R.random(), phase=R.uniform(0, 6), curl=K['curl'] * (0.8 + 0.6 * R.random()))
        B.add(*clump(p, n, K['width'] * L * (0.85 + 0.3 * R.random()), thick=0.44, tip=0.85))
    out['hair_main'] = B.data()

    # bangs: pointed clumps from near the part over the forehead, tips at staggered heights, sweeping out
    B = Builder()
    G = S['bangs']
    nb = G['count']
    for k in range(nb):
        t = (k + 0.5) / nb
        az_t = part + (t - 0.5) * G['span']
        el_t = G['tip_el'][k % len(G['tip_el'])]
        az_r = part + (az_t - part) * 0.25
        sweep = G['sweep'] * (t - 0.5) * 2
        w = G['width'] * L * (0.85 + 0.3 * R.random()) * (1 - 0.35 * abs(t - 0.5))
        p, n = lock(V, lambda s, a0=az_r, a1=az_t, sw=sweep: a0 + (a1 - a0) * s ** 0.8 + sw * s ** 3,
                    lambda s, e=el_t: 74 - (74 - e) * s ** 0.9,
                    lambda s: 1.0 - 0.06 * s ** 1.6, wave=0.002, waves=0.5, phase=R.uniform(0, 3), n=20)
        B.add(*clump(p, n, w, thick=G['thick'], tip=G['tip']))
    # face-framing side locks, in front of the ears, down past the chin
    Sd = S['sides']
    for sx in (-1, 1):
        for az, wd in zip(Sd['az'], Sd['width']):
            el_end = -52 - S['side_len'] * 40
            p, n = lock(V, lambda s, a=az, x=sx: x * (a * 0.74 + a * 0.26 * s), lambda s, e=el_end: 40 - (40 - e) * s,
                        lambda s: 1.02 + 0.03 * s, wave=Sd['wave'] * L / 0.25, bob=0.006, waves=1.3,
                        phase=0.0 if sx > 0 else math.pi, curl=Sd['curl'])
            B.add(*clump(p, n, wd * L, thick=0.42))
    if S['ahoge']:
        base = V.point(part - 10, 86, 0.99)
        u = np.linspace(0, 1, 15)
        pts = np.stack([base + np.array([0.18 * L * x ** 1.6, 0.016 * L * x, 0.30 * L * math.sin(x * 2.5)]) for x in u])
        B.add(*clump(pts, np.tile([0, 0, 1.0], (15, 1)), 0.03 * L, thick=0.6, root_taper=0.8))
    out['hair_bangs'] = B.data()

    # the cap: a smooth shell under everything so no scalp shows (open over the face)
    NA, NE = 64, 26
    verts, uvs = [], []
    els = [90 - (90 - (-40)) * i / NE for i in range(NE + 1)]
    for el in els:
        for k in range(NA):
            az = -180 + 360 * k / NA
            verts.append(V.point(az, el, 0.965)); uvs.append((0.0, 0.0))
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


def material(name, lit, shade_c, deep, ring=(1.0, 0.86, 0.80), head_z=0.0, ring_el=40.0, thresh=0.5):
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
    Lk(hi.outputs['Result'], em.inputs['Color'])
    return m


def build(A, arm, style=None, colors=None):
    """Blender objects for the hairstyle on an assembled character A (charkit.character.assemble), parented to the head
    bone. colors: dict(lit, shade, deep, ring, under, line). -> [objects]."""
    import bpy
    from . import character, shade
    C = dict(lit=(0.96, 0.93, 0.98), shade=(0.72, 0.74, 0.90), deep=(0.52, 0.52, 0.72), ring=(1.0, 1.0, 1.0),
             under=(0.62, 0.64, 0.82), line=(0.36, 0.34, 0.50))
    C.update(colors or {})
    Hd = A['head']
    H, centre = Hd['H'], Hd['centre']
    meshes, V = generate(H, centre, Hd['info']['target'], style)
    pv, pf = proxy_mesh(V)
    proxy = character._mesh('hair_normals_proxy', pv, pf, None, [])
    proxy.hide_render = True; proxy.hide_viewport = True
    character._to_head(proxy, arm)
    mat = material('hair', C['lit'], C['shade'], C['deep'], ring=C['ring'], head_z=tuple(V.c))
    under = shade.toon3('hair_under', C['under'], C['deep'], tuple(np.array(C['deep']) * 0.8))
    obs = []
    for name, (v, f, uv) in meshes.items():
        m = under if name in ('hair_under', 'hair_cap') else mat
        ob = character._mesh(name, v, f, None, [m])
        me = ob.data
        lay = me.uv_layers.new(name='lock')
        for p in me.polygons:
            p.use_smooth = True
            for li in p.loop_indices:
                lay.data[li].uv = uv[me.loops[li].vertex_index]
        import bmesh
        bm = bmesh.new(); bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me); bm.free()
        dt = ob.modifiers.new('volume_normals', 'DATA_TRANSFER')
        dt.object = proxy; dt.use_loop_data = True; dt.data_types_loops = {'CUSTOM_NORMAL'}
        dt.loop_mapping = 'POLYINTERP_NEAREST'; dt.mix_factor = 0.85 if name != 'hair_cap' else 1.0
        if name != 'hair_cap':
            shade.outline(ob, thick=0.0016, color=C['line'], name='hair_line')
        character._to_head(ob, arm)
        obs.append(ob)
    return obs
