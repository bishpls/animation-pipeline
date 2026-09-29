"""The face's anime shading (docs/CHARKIT.md §2, materials): an SDF threshold map (the Genshin method: per face pixel, the light
angle past which it falls into shadow, so the shadow is a designed shape, not the geometry's), the fringe's shadow on the
forehead, a blush, and a per-vertex face mask (rest pose, head space) that blends it with ordinary toon shading round the
sides and back of the head. Maps live in the 'face' UV (front projection in head space, charkit.character.build).

The light goes in head space through the 'ldir_head' node; set_light() fills it (call per frame when the head turns).

With the style's look.face.normals 'proxy' the head and neck shade on a smooth stand-in's normals (proxy_normals: the
head's own normals blurred to its large shapes, the neck's round its axis and tilted down under the jaw), carried onto
the rendered skin after its outline by a Data Transfer from a hidden, rigged copy (as the hair's envelope normals are):
the toon terminator round the sides of the head and on the neck is one clean shape that moves with the light and never
follows the eye hollows, cheek bumps or neck bands, the jaw's underside and the neck under it fall into shade as drawn,
and the face mask is taken from the same normals (no holes at the eye sockets).
"""
import math
import numpy as np

from . import shade

FACE_WIN = (-0.42, 0.42, -0.45, 0.60)       # the 'face' UV's window in head space, in L: x0, x1, z0, z1


def _grid(size, L):
    x0, x1, z0, z1 = (w * L for w in FACE_WIN)
    u = (np.arange(size) + 0.5) / size
    U, Vv = np.meshgrid(u, u[::-1])           # row 0 = the window's top
    return x0 + U * (x1 - x0), z0 + Vv * (z1 - z0)


def _blur(a, r):
    if r <= 0:
        return a
    k = np.exp(-0.5 * (np.arange(-3 * r, 3 * r + 1) / r) ** 2); k /= k.sum()
    a = np.apply_along_axis(lambda m: np.convolve(m, k, mode='same'), 0, a)
    return np.apply_along_axis(lambda m: np.convolve(m, k, mode='same'), 1, a)


def sdf(H, size=512, nose=True, tri=False):
    """the threshold map (float, 0..1) for light from HER LEFT (+x); the shader mirrors it for the right. t = 0 light from the
    front, 0.5 from the side, 1 from behind: a pixel is lit while the light's t is below its value."""
    L = H.L
    X, Z = _grid(size, L)
    wid = np.array([H.section(z)[0] for z in Z[:, 0]])[:, None] + 1e-5
    s = np.clip(X / wid, -1.3, 1.3)                    # -1 her right edge (far from the light) .. +1 her left edge
    t_edge = 0.5 + 0.5 * np.sign(s) * np.abs(s) ** 1.6
    thr = 0.06 + 0.90 * t_edge
    if nose:                                           # the nose's small shadow on her right cheek, early
        nx, nz = X / (0.07 * L), (Z - H.nose_z) / (0.06 * L)
        m = (nx < 0.2) & (nx > -1.1) & (np.abs(nz) < 1.0 - 0.6 * np.abs(nx + 0.3))
        thr = np.where(m, np.minimum(thr, 0.22 + 0.08 * np.abs(nx)), thr)
    if tri:                                            # the lit triangle under the far eye (Rembrandt), held past side-on
        tx, tz = (X + H.eye_x) / (0.09 * L), (Z + 0.12 * L) / (0.08 * L)
        m = (np.abs(tx) < 1) & (tz > -1) & (tz < 1 - np.abs(tx) * 1.2) & (s < 0)
        thr = np.where(m, np.maximum(thr, 0.52), thr)
    return np.clip(_blur(thr, 2.0 * size / 512), 0, 1)


def blush(H, size=512, color=(1.0, 0.62, 0.62), amount=0.5):
    """RGBA: two soft ovals under the eyes (alpha = amount)."""
    L = H.L
    X, Z = _grid(size, L)
    b = sum(np.exp(-(((X - sx * H.eye_x * 1.05) / (0.07 * L)) ** 2 + ((Z + 0.10 * L) / (0.035 * L)) ** 2)) for sx in (-1, 1))
    a = np.clip(b, 0, 1) * amount
    return np.dstack([np.full_like(a, color[0]), np.full_like(a, color[1]), np.full_like(a, color[2]), a])


def fringe_shadow(H, centre, bangs, size=512, drop=0.03, soft=1.5):
    """the bangs' shadow on the face (0..1): their front silhouette in head space, dropped by `drop` (in L) and softened.
    bangs: (verts, faces) in world at rest."""
    L = H.L
    X, Z = _grid(size, L)
    x0, x1, z0, z1 = (w * L for w in FACE_WIN)
    img = np.zeros((size, size))
    v, faces = bangs
    q = np.asarray(v) - np.asarray(centre)
    px = (q[:, 0] - x0) / (x1 - x0) * size
    pz = (z1 - (q[:, 2] - drop * L)) / (z1 - z0) * size
    front = q[:, 1] < H.df * 0.2                       # only the parts in front of the forehead
    for f in faces:
        if not all(front[i] for i in f):
            continue
        for k in range(1, len(f) - 1):
            tri = [f[0], f[k], f[k + 1]]
            xs, zs = px[tri], pz[tri]
            xa, xb = int(max(0, math.floor(xs.min()))), int(min(size - 1, math.ceil(xs.max())))
            za, zb = int(max(0, math.floor(zs.min()))), int(min(size - 1, math.ceil(zs.max())))
            if xa > xb or za > zb:
                continue
            gx, gz = np.meshgrid(np.arange(xa, xb + 1) + 0.5, np.arange(za, zb + 1) + 0.5)
            (ax, az_), (bx, bz), (cx, cz) = zip(xs, zs)
            d = (bz - cz) * (ax - cx) + (cx - bx) * (az_ - cz)
            if abs(d) < 1e-9:
                continue
            l1 = ((bz - cz) * (gx - cx) + (cx - bx) * (gz - cz)) / d
            l2 = ((cz - az_) * (gx - cx) + (ax - cx) * (gz - cz)) / d
            inside = (l1 >= 0) & (l2 >= 0) & (l1 + l2 <= 1)
            img[za:zb + 1, xa:xb + 1] = np.maximum(img[za:zb + 1, xa:xb + 1], inside)
    return np.clip(_blur(img, soft * size / 512), 0, 1)


def face_mask(V, faces, head_w, centre, H, normals=None):
    """per vertex (rest pose): 1 on the face (facing forward, between the chin and the hairline), 0 round the sides and
    back. normals: the shading normals to judge facing by (default the mesh's own)."""
    from . import anime_head as ah
    n = ah.vertex_normals(V, faces) if normals is None else normals
    fwd = -n[:, 1]
    q = V - np.asarray(centre)
    L = H.L
    m = np.clip((fwd + 0.35) / 0.3, 0, 1)                  # the whole front half (hair covers the handover)
    m *= np.clip((q[:, 2] + H.chin * 1.02) / (0.04 * L), 0, 1) * np.clip((0.30 * L - q[:, 2]) / (0.06 * L), 0, 1)
    m *= np.clip((head_w - 0.3) / 0.4, 0, 1)
    return m


def _blur_normals(V, n, sel, sigma, chunk=2048):
    """the normals of the vertices in sel averaged with their neighbours' by a Gaussian of distance (sigma, m): the
    surface's large shapes without its small ones (numpy only: Blender's Python has no scipy)."""
    idx = np.nonzero(sel)[0]
    P, Nn = V[idx], n[idx]
    out = n.copy()
    for a in range(0, len(idx), chunk):
        d2 = ((P[a:a + chunk, None, :] - P[None, :, :]) ** 2).sum(-1)
        w = np.exp(-0.5 * d2 / sigma ** 2)
        m = w @ Nn
        out[idx[a:a + chunk]] = m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-9)
    return out


def proxy_normals(V, faces, head_w, centre, L, chin, neck, blur=0.22, chin_tilt=60.0, tilt_power=0.6):
    """the skin's shading normals from a smooth stand-in (rest pose, world): over the head and neck (head_w > 0 or above
    the neck's base) the mesh's normals blurred by a Gaussian of `blur` L (the eye hollows, cheek and lip bumps and the
    neck's folds gone, the head's turn kept); on the neck (within 1.25 times its radius of its axis: the jaw and chin
    stand out past it) turned round its axis and tilted down by
    up to chin_tilt degrees under the jaw (tapering as (height up the neck)^tilt_power to 0 at its base), so a light
    from above leaves the neck under the chin in shade, as a drawn neck is. Elsewhere the mesh's own.
    neck: (base, head) joint positions. -> (normals (N, 3), weight (N,): 0 own .. 1 stand-in, the neck (N,): 0 .. 1)."""
    from . import anime_head as ah
    V = np.asarray(V, float)
    n = ah.vertex_normals(V, faces)
    c = np.asarray(centre, float)
    p0, p1 = (np.asarray(x, float) for x in neck)
    u = (p1 - p0) / np.linalg.norm(p1 - p0)
    s = (V - p0) @ u / np.linalg.norm(p1 - p0)                   # 0 at the neck's base, 1 at the head joint
    hw = np.asarray(head_w, float)
    # the region: the head and neck, fading in over the neck's lower fifth (the shoulders and chest keep their own)
    w = np.clip((s + 0.1) / 0.3, 0, 1)
    w = np.maximum(w, np.clip(hw * 3, 0, 1)) * (np.linalg.norm((V - p0) - np.outer((V - p0) @ u, u), axis=1) < 1.2 * L)
    sm = _blur_normals(V, n, w > 0, blur * L)
    # the neck: the skin within its own radius of its axis (the jaw and chin stand out past it; the nape joins it),
    # below the head joint; turned round the axis and tilted down under the jaw
    z_chin = c[2] - chin
    s_chin = (np.array([c[0], c[1], z_chin]) - p0) @ u / np.linalg.norm(p1 - p0)
    rv = (V - p0) - np.outer((V - p0) @ u, u)
    dist = np.linalg.norm(rv, axis=1)
    mid = (s > 0.25) & (s < 0.6) & (dist < 0.6 * L)
    rn = float(np.median(dist[mid])) if mid.sum() > 10 else 0.2 * L
    r = rv / np.maximum(dist, 1e-9)[:, None]
    t = np.clip(s / max(s_chin, 1e-6), 0, 1) ** tilt_power
    tau = np.radians(chin_tilt) * t
    cyl = np.cos(tau)[:, None] * r - np.sin(tau)[:, None] * u
    k = (np.clip((1.25 * rn - dist) / (0.15 * rn), 0, 1) * np.clip((1.15 - s) / 0.15, 0, 1)
         * np.clip((s + 0.1) / 0.3, 0, 1))[:, None]
    out = sm * (1 - k) + cyl * k
    out = n * (1 - w[:, None]) + out * w[:, None]
    return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9), w, k[:, 0]


def neck_weight(V, centre, L, chin, neck):
    """proxy_normals' neck (the skin within 1.25 times the neck's radius of its axis, below the head joint): 0 .. 1."""
    V = np.asarray(V, float)
    p0, p1 = (np.asarray(x, float) for x in neck)
    u = (p1 - p0) / np.linalg.norm(p1 - p0)
    s = (V - p0) @ u / np.linalg.norm(p1 - p0)
    dist = np.linalg.norm((V - p0) - np.outer((V - p0) @ u, u), axis=1)
    mid = (s > 0.25) & (s < 0.6) & (dist < 0.6 * L)
    rn = float(np.median(dist[mid])) if mid.sum() > 10 else 0.2 * L
    return (np.clip((1.25 * rn - dist) / (0.15 * rn), 0, 1) * np.clip((1.15 - s) / 0.15, 0, 1)
            * np.clip((s + 0.1) / 0.3, 0, 1)), rn


def ink(H, V, centre, neck_w, size=512, width=0.0045, reach=0.9, color=(0.42, 0.24, 0.20)):
    """the drawn lines the outline can't give, in the 'face' UV (RGBA, alpha = coverage): the jaw's lower edge where it
    crosses the neck (from the front the chin and jaw don't turn away from the camera there, so no hull shows; the
    drawing inks it). The edge is the lowest point of the head's front (not the neck: neck_w < 0.5) per column, a band
    `width` L above it, fading out past `reach` of the jaw's half-width (the ears, where the hull draws the jaw).
    Applied only off the neck (the 'ck_ink_w' attribute), so the front projection doesn't paint the neck behind."""
    L = H.L
    q = np.asarray(V, float) - np.asarray(centre, float)
    x0, x1, z0, z1 = (w * L for w in FACE_WIN)
    sel = (np.asarray(neck_w) < 0.5) & (q[:, 1] < 0.35 * L) & (q[:, 2] < 0.0) & (q[:, 2] > z0)
    X, Z = _grid(size, L)
    xs = X[0]
    low = np.full(size, np.nan)
    col = np.clip(((q[sel, 0] - x0) / (x1 - x0) * size).astype(int), 0, size - 1)
    for c_, z_ in zip(col, q[sel, 2]):
        if not z_ >= low[c_]:
            low[c_] = z_
    ok = np.isfinite(low)
    if ok.sum() < 10:
        return np.zeros((size, size, 4))
    low = np.interp(xs, xs[ok], low[ok])
    k = np.exp(-0.5 * (np.arange(-6, 7) / 3.0) ** 2); k /= k.sum()
    low = np.convolve(np.pad(low, 6, mode='edge'), k, mode='valid')
    hw = np.abs(xs[ok]).max()
    px = (z1 - z0) / size
    d = Z - low[None, :]                                            # height above the edge
    a = np.clip((d + px) / px, 0, 1) * np.clip((width * L - d) / px + 0.5, 0, 1)
    a *= np.clip((reach * hw - np.abs(X)) / (0.1 * hw), 0, 1)
    rgb = np.broadcast_to(np.asarray(color, float), (size, size, 3))
    return np.dstack([rgb, a])


def apply_proxy_normals(skin, N, name='skin_normals'):
    """the stand-in's normals onto the rendered skin: a hidden copy of its base mesh (rigged as it is, without its shape
    keys) carrying N as custom normals, transferred after the outline (Solidify re-derives corner normals; see
    charkit.geom.blender.transfer_normals) by interpolation from the nearest face (the skin renders subdivided)."""
    import bpy
    me = skin.data.copy()
    me.name = name
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if me.shape_keys is not None:
        ob.shape_key_clear()
    for vg in skin.vertex_groups:                        # the same groups in the same order: the rig deforms it alike
        ob.vertex_groups.new(name=vg.name)
    ob.parent = skin.parent
    ob.matrix_world = skin.matrix_world.copy()
    arm = next((m for m in skin.modifiers if m.type == 'ARMATURE'), None)
    if arm is not None:
        a2 = ob.modifiers.new('rig', 'ARMATURE'); a2.object = arm.object
    if hasattr(me, 'use_auto_smooth'):
        me.use_auto_smooth = True
    me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), bool))
    me.normals_split_custom_set_from_vertices([tuple(v) for v in np.asarray(N, float)])
    ob.hide_render = True
    ob.hide_viewport = True
    dt = skin.modifiers.new('proxy_normals', 'DATA_TRANSFER')
    dt.object = ob
    dt.use_loop_data = True
    dt.data_types_loops = {'CUSTOM_NORMAL'}
    dt.loop_mapping = 'POLYINTERP_NEAREST'
    i = next((k for k, m in enumerate(skin.modifiers) if m.name == 'outline'), None)
    j = len(skin.modifiers) - 1
    if i is not None and j != i + 1:                     # right after the outline (before the garment mask)
        skin.modifiers.move(j, i + 1)
    return ob


def material(name, lit, shade_c, deep, maps, rim=(1.0, 0.94, 0.92), soft=0.012, shadow_amt=0.85):
    """the skin material with the face shading: toon3 everywhere, replaced on the face (the 'face_mask' colour attribute)
    by the SDF shading, the fringe shadow and the blush. maps: dict of Blender images (sdf, blush, fringe)."""
    import bpy
    m = shade.toon3(name, lit, shade_c, deep, rim=rim)
    nt = m.node_tree; N = nt.nodes.new; Lk = nt.links.new
    em = next(n for n in nt.nodes if n.type == 'EMISSION')
    toon = em.inputs['Color'].links[0].from_socket
    ld = N('ShaderNodeCombineXYZ'); ld.name = 'ldir_head'
    for i in range(3):
        ld.inputs[i].default_value = float(shade.LDIR[i])
    sep = N('ShaderNodeSeparateXYZ'); Lk(ld.outputs[0], sep.inputs[0])
    negy = N('ShaderNodeMath'); negy.operation = 'MULTIPLY'; negy.inputs[1].default_value = -1.0
    Lk(sep.outputs['Y'], negy.inputs[0])
    absx = N('ShaderNodeMath'); absx.operation = 'ABSOLUTE'; Lk(sep.outputs['X'], absx.inputs[0])
    ang = N('ShaderNodeMath'); ang.operation = 'ARCTAN2'; Lk(absx.outputs[0], ang.inputs[0]); Lk(negy.outputs[0], ang.inputs[1])
    t = N('ShaderNodeMath'); t.operation = 'DIVIDE'; t.inputs[1].default_value = math.pi; Lk(ang.outputs[0], t.inputs[0])
    uvn = N('ShaderNodeUVMap'); uvn.uv_map = 'face'
    suv = N('ShaderNodeSeparateXYZ'); Lk(uvn.outputs[0], suv.inputs[0])
    flipu = N('ShaderNodeMath'); flipu.operation = 'SUBTRACT'; flipu.inputs[0].default_value = 1.0
    Lk(suv.outputs['X'], flipu.inputs[1])
    right = N('ShaderNodeMath'); right.operation = 'LESS_THAN'; right.inputs[1].default_value = 0.0
    Lk(sep.outputs['X'], right.inputs[0])
    mu = N('ShaderNodeMix'); mu.data_type = 'FLOAT'
    Lk(right.outputs[0], mu.inputs['Factor']); Lk(suv.outputs['X'], mu.inputs['A']); Lk(flipu.outputs[0], mu.inputs['B'])
    cuv = N('ShaderNodeCombineXYZ'); Lk(mu.outputs['Result'], cuv.inputs[0]); Lk(suv.outputs['Y'], cuv.inputs[1])
    tx = N('ShaderNodeTexImage'); tx.image = maps['sdf']; tx.extension = 'EXTEND'; tx.interpolation = 'Cubic'
    Lk(cuv.outputs[0], tx.inputs['Vector'])
    diff = N('ShaderNodeMath'); diff.operation = 'SUBTRACT'; Lk(t.outputs[0], diff.inputs[0]); Lk(tx.outputs['Color'], diff.inputs[1])
    edge = N('ShaderNodeMapRange'); edge.inputs['From Min'].default_value = -soft; edge.inputs['From Max'].default_value = soft
    Lk(diff.outputs[0], edge.inputs['Value'])
    # the fringe's shadow adds to it (only while the face is lit from the front half)
    fr = N('ShaderNodeTexImage'); fr.image = maps['fringe']; fr.extension = 'CLIP'
    Lk(uvn.outputs[0], fr.inputs['Vector'])
    frs = N('ShaderNodeMapRange'); frs.inputs['From Min'].default_value = 0.35; frs.inputs['From Max'].default_value = 0.55
    Lk(fr.outputs['Color'], frs.inputs['Value'])
    sh = N('ShaderNodeMath'); sh.operation = 'MAXIMUM'; sh.use_clamp = True
    Lk(edge.outputs['Result'], sh.inputs[0]); Lk(frs.outputs['Result'], sh.inputs[1])
    col = N('ShaderNodeMix'); col.data_type = 'RGBA'
    col.inputs['A'].default_value = (*shade.lin(lit), 1); col.inputs['B'].default_value = (*shade.lin(shade_c), 1)
    Lk(sh.outputs[0], col.inputs['Factor'])
    last = col.outputs['Result']
    bt = N('ShaderNodeTexImage'); bt.image = maps['blush']; bt.extension = 'CLIP'
    Lk(uvn.outputs[0], bt.inputs['Vector'])
    bm = N('ShaderNodeMix'); bm.data_type = 'RGBA'; bm.blend_type = 'MULTIPLY'
    Lk(bt.outputs['Alpha'], bm.inputs['Factor']); Lk(last, bm.inputs['A']); Lk(bt.outputs['Color'], bm.inputs['B'])
    last = bm.outputs['Result']
    # blend with the toon shading by the face mask
    at = N('ShaderNodeAttribute'); at.attribute_name = 'face_mask'; at.attribute_type = 'GEOMETRY'
    fm = N('ShaderNodeMix'); fm.data_type = 'RGBA'
    Lk(at.outputs['Fac'], fm.inputs['Factor']); Lk(toon, fm.inputs['A']); Lk(last, fm.inputs['B'])
    for lnk in list(em.inputs['Color'].links):
        nt.links.remove(lnk)
    out = fm.outputs['Result']
    if maps.get('ink') is not None:                     # the drawn lines (ink()), off the neck
        it = N('ShaderNodeTexImage'); it.image = maps['ink']; it.extension = 'CLIP'; it.name = 'ck_ink'
        Lk(uvn.outputs[0], it.inputs['Vector'])
        iw = N('ShaderNodeAttribute'); iw.attribute_name = 'ck_ink_w'; iw.attribute_type = 'GEOMETRY'
        ia = N('ShaderNodeMath'); ia.operation = 'MULTIPLY'
        Lk(it.outputs['Alpha'], ia.inputs[0]); Lk(iw.outputs['Fac'], ia.inputs[1])
        im = N('ShaderNodeMix'); im.data_type = 'RGBA'; im.name = 'ck_ink_mix'
        Lk(ia.outputs[0], im.inputs['Factor']); Lk(out, im.inputs['A']); Lk(it.outputs['Color'], im.inputs['B'])
        out = im.outputs['Result']
    Lk(out, em.inputs['Color'])
    return m


def set_light(ldir_world, head_matrix=None):
    """the face materials' light, in head space (head_matrix: the head bone's world 3x3 rotation, or None at rest)."""
    d = np.asarray(ldir_world, float)
    if head_matrix is not None:
        d = np.asarray(head_matrix).T @ d
    for m in shade.MATS.values():
        if m.node_tree and 'ldir_head' in m.node_tree.nodes:
            nd = m.node_tree.nodes['ldir_head']
            for i in range(3):
                nd.inputs[i].default_value = float(d[i])


def apply(C, bangs=None, colors=None, size=512, look=None):
    """give an assembled, built character (charkit.character.build's dict) the face shading on its head faces, and with
    the look's face.normals 'proxy' the stand-in's normals over the head and neck (proxy_normals)."""
    import bpy
    from . import eyetex
    A = C['data']; Hd = A['head']; H = Hd['H']; centre = Hd['centre']
    fl = (look or {}).get('face') or {}
    from . import mh
    J = A['joints']
    neck = [np.asarray(J[k], float) for k in mh.VRM_JOINTS['neck']]
    Np = None
    if fl.get('normals') == 'proxy':
        Np, _, _ = proxy_normals(A['verts'], A['faces'], A['body']['head_w'], centre, H.L, H.chin, neck,
                                 blur=fl.get('blur', 0.22), chin_tilt=fl.get('chin_tilt', 60.0),
                                 tilt_power=fl.get('tilt_power', 0.6))
    ink_img, ink_w = None, None
    if fl.get('jaw_line'):
        nk, _ = neck_weight(A['verts'], centre, H.L, H.chin, neck)
        ink_w = 1.0 - nk
        px = ink(H, A['verts'], centre, nk, size, width=fl.get('jaw_width', 0.0045), reach=fl.get('jaw_reach', 0.9),
                 color=fl.get('ink_color', (0.42, 0.24, 0.20)))
        ink_img = eyetex.to_blender_image('face_ink', px)
    col = dict(lit=(1.0, 0.90, 0.86), shade=(0.95, 0.76, 0.74), deep=(0.84, 0.60, 0.62))
    col.update(colors or {})
    thr = sdf(H, size)
    img = bpy.data.images.new('face_sdf', size, size, alpha=False, float_buffer=True)
    img.colorspace_settings.name = 'Non-Color'
    img.pixels.foreach_set(np.dstack([thr, thr, thr, np.ones_like(thr)])[::-1].astype(np.float32).ravel())
    img.pack()
    fr = fringe_shadow(H, centre, bangs, size) if bangs is not None else np.zeros((size, size))
    fimg = bpy.data.images.new('face_fringe', size, size, alpha=False, float_buffer=True)
    fimg.colorspace_settings.name = 'Non-Color'
    fimg.pixels.foreach_set(np.dstack([fr, fr, fr, np.ones_like(fr)])[::-1].astype(np.float32).ravel())
    fimg.pack()
    bl = eyetex.to_blender_image('face_blush', blush(H, size))
    mat = material('face_skin', col['lit'], col['shade'], col['deep'], dict(sdf=img, fringe=fimg, blush=bl, ink=ink_img))
    skin = C['skin']; me = skin.data
    fmk = face_mask(A['verts'], A['faces'], A['body']['head_w'], centre, H, normals=Np)
    at = me.color_attributes.new('face_mask', 'FLOAT_COLOR', 'POINT')
    at.data.foreach_set('color', np.repeat(fmk[:, None], 4, 1).astype(np.float32).ravel())
    if ink_w is not None:
        at = me.color_attributes.new('ck_ink_w', 'FLOAT_COLOR', 'POINT')
        at.data.foreach_set('color', np.repeat(ink_w[:, None], 4, 1).astype(np.float32).ravel())
    me.materials[1] = mat
    if Np is not None:
        apply_proxy_normals(skin, Np)
    return mat
