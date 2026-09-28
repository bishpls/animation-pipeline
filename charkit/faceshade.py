"""The face's anime shading (docs/CHARKIT.md §2, materials): an SDF threshold map (the Genshin method: per face pixel, the light
angle past which it falls into shadow, so the shadow is a designed shape, not the geometry's), the fringe's shadow on the
forehead, a blush, and a per-vertex face mask (rest pose, head space) that blends it with ordinary toon shading round the
sides and back of the head. Maps live in the 'face' UV (front projection in head space, charkit.character.build).

The light goes in head space through the 'ldir_head' node; set_light() fills it (call per frame when the head turns).
"""
import math
import numpy as np

from . import shade

FACE_WIN = (-0.16, 0.16, -0.45, 0.25)       # the 'face' UV's window in head space, in L: x0, x1, z0, z1


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


def sdf(H, size=512, nose=True, tri=True):
    """the threshold map (float, 0..1) for light from HER LEFT (+x); the shader mirrors it for the right. t = 0 light from the
    front, 0.5 from the side, 1 from behind: a pixel is lit while the light's t is below its value."""
    L = H.L
    X, Z = _grid(size, L)
    wid = np.array([H.section(z)[0] for z in Z[:, 0]])[:, None] + 1e-5
    s = np.clip(X / wid, -1.3, 1.3)                    # -1 her right edge (far from the light) .. +1 her left edge
    t_edge = 0.5 + 0.5 * np.sign(s) * np.abs(s) ** 1.25
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


def face_mask(V, faces, head_w, centre, H):
    """per vertex (rest pose): 1 on the face (facing forward, between the chin and the hairline), 0 round the sides and back."""
    from . import anime_head as ah
    n = ah.vertex_normals(V, faces)
    fwd = -n[:, 1]
    q = V - np.asarray(centre)
    L = H.L
    m = np.clip((fwd - 0.05) / 0.35, 0, 1)
    m *= np.clip((q[:, 2] + H.chin * 1.02) / (0.04 * L), 0, 1) * np.clip((0.30 * L - q[:, 2]) / (0.06 * L), 0, 1)
    m *= np.clip((head_w - 0.3) / 0.4, 0, 1)
    return m


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
    Lk(fm.outputs['Result'], em.inputs['Color'])
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


def apply(C, bangs=None, colors=None, size=512):
    """give an assembled, built character (charkit.character.build's dict) the face shading on its head faces."""
    import bpy
    from . import eyetex
    A = C['data']; Hd = A['head']; H = Hd['H']; centre = Hd['centre']
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
    mat = material('face_skin', col['lit'], col['shade'], col['deep'], dict(sdf=img, fringe=fimg, blush=bl))
    skin = C['skin']; me = skin.data
    fmk = face_mask(A['verts'], A['faces'], A['body']['head_w'], centre, H)
    at = me.color_attributes.new('face_mask', 'FLOAT_COLOR', 'POINT')
    at.data.foreach_set('color', np.repeat(fmk[:, None], 4, 1).astype(np.float32).ravel())
    me.materials[1] = mat
    return mat
