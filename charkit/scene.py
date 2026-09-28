"""A character scene from a spec (docs/CHARKIT.md §3), Blender-side: the stages in order, each a function of the spec and
what came before, so a build can stop after any stage, swap one out (the hair from a generated shape instead of the
analytic volume, say), or render boards from the result.

    body+head -> face features -> face shading -> hair -> accessories -> garments -> (boards, export)

    from charkit import scene; S = scene.build(spec)     # inside Blender: S.character, S.hair, S.garments, ...
    scene.boards(S, out, which=('views', 'expressions', 'mouths', 'body'))
"""
import json, os

import numpy as np

SKIN = dict(lit=(1.0, 0.90, 0.86), shade=(0.95, 0.76, 0.74), deep=(0.84, 0.60, 0.62))
EXPR = ['blink', 'happy', 'half', 'wide', 'angry', 'sad', 'squint']
MOUTH = ['neutral', 'aa', 'ih', 'ou', 'ee', 'oh', 'smile', 'grin', 'frown', 'surprised']


class Scene:
    """what a build made: the character (charkit.character.build's dict) and each stage's objects."""

    def __init__(self, spec):
        self.spec = spec
        self.name = spec['name']
        self.character = None
        self.hair, self.hair_volume, self.accessories, self.garments = [], None, [], []

    @property
    def features(self):
        return [p[k] for p in self.character['eyes'] for k in ('sclera', 'iris', 'lash', 'brow')]

    @property
    def covers(self):
        return self.hair + self.accessories


def load(path):
    spec = json.load(open(path))
    spec.setdefault('_dir', os.path.dirname(os.path.abspath(path)))
    return spec


def reset(bg=(0.86, 0.86, 0.90)):
    import bpy
    from . import shade
    bpy.ops.wm.read_factory_settings(use_empty=True)
    shade.MATS.clear()
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.view_settings.view_transform = 'Standard'
    w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (*bg, 1)


def stage_character(S):
    from . import character, shade
    sk = {k: tuple(v) for k, v in S.spec.get('skin', {}).items()} or SKIN
    S.character = character.build(S.spec, clay=shade.toon3('skin', **sk))
    shade.outline(S.character['skin'], thick=0.0011, color=tuple(S.spec.get('skin_line', (0.42, 0.24, 0.20))))
    S.skin_colors = sk


def stage_hair(S):
    from . import accessories, hair, shade
    if S.spec.get('hair') is None:
        return
    hc = {k: tuple(v) for k, v in S.spec.get('hair_colors', {}).items()}
    vol = None
    shape = S.spec['hair'].get('shape')
    if shape:
        vol = hair_shape_volume(S, shape, hc)
    if shape and shape.get('mode') == 'mesh':
        S.hair_volume_for_normals = vol
        S.hair = [hair_shape_mesh(S, shape, hc)]
        S.hair_volume = vol
        cap = hair_cap(S, hc)
        if cap is not None:
            S.hair.append(cap)
    else:
        S.hair, S.hair_volume = hair.build(S.character['data'], S.character['arm'], S.spec.get('hair'), hc, volume=vol)
    acc = S.spec.get('accessories') or []
    if shape and shape.get('mode') == 'mesh':
        acc = [a for a in acc if a['kind'] not in shape.get('carries', ['bun'])]
    S.accessories = accessories.build(S.character['data'], S.character['arm'], S.hair_volume, acc,
                                      {'hair': shade.MATS.get('hair') or shade.MATS.get('hair_shape')})


def cull_face(S, hv, hf, shape):
    """drop generated 'hair' lying on or behind our face (the generated face's own lips, brows, nose) and anything over the
    lower face (only side locks belong there)."""
    from .eyes import Face
    Hd = S.character['data']['head']; L = Hd['L']
    Fc = Face(Hd['H'], Hd['centre'])
    cz = Hd['centre'][2]
    keep = np.ones(len(hv), bool)
    for i, p in enumerate(hv):
        zr = p[2] - cz
        if -Hd['H'].chin * 1.05 < zr < 0.22 * L and abs(p[0]) < 0.30 * L:
            if zr < -0.06 * L:
                # below the eyes nothing lies over the face (only the side locks, outside its width)
                if abs(p[0]) < Hd['H'].section(zr)[0] * 0.92 and p[1] < Fc.y(p[0], p[2]) + 0.04 * L:
                    keep[i] = False
            elif p[1] > Fc.y(p[0], p[2]) - shape.get('clear', 0.02) * L:
                keep[i] = False
    hf = [f for f in hf if all(keep[v] for v in f)]
    used = sorted({v for f in hf for v in f}); remap = {o: n for n, o in enumerate(used)}
    hv = hv[used]; hf = [tuple(remap[v] for v in f) for f in hf]
    return hv, hf


def hair_shape_volume(S, shape, hc):
    """the hair volume from a generated character (TRELLIS.2 GLB): aligned by its eyes onto ours, its hair taken by colour
    above the chin (not the same-coloured clothes), as a charkit.hair.MeshVolume."""
    from . import hair, i3d
    A = S.character['data']; Hd = A['head']; L = Hd['L']
    path = shape['glb'] if os.path.isabs(shape['glb']) else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), shape['glb'])
    V, F, C = i3d.load_glb(path)
    eyes = i3d.find_eyes(V, C)
    if eyes is None:
        raise RuntimeError('no eyes found on the generated shape')
    EK = Hd['eye_knobs']
    eye_mid = np.array([0.0, Hd['centre'][1] - Hd['H'].df + shape.get('eye_depth', 0.01) * L, Hd['centre'][2] + EK['z'] * L])
    V = i3d.align_by_eyes(V, eyes, eye_mid, 2 * EK['x'] * L * shape.get('spacing', 1.0))
    S.shape_full = (V, F)                                   # the whole aligned shape (QA compares against it)
    S.shape_colors = C                                      # its per-vertex colours (the face QA finds its skin by them)
    cols = shape.get('colors') or [hc.get('lit', (0.95, 0.5, 0.3)), hc.get('shade', (0.8, 0.35, 0.22)),
                                   hc.get('deep', (0.6, 0.22, 0.16))]
    chin_z = Hd['centre'][2] - Hd['H'].chin
    if shape.get('select') == 'outside':
        hv, hf = i3d.hair_by_outside(V, C, F, A['verts'], A['faces'], chin_z, shape.get('shoulder_x', 0.16),
                                     below=shape.get('below', 0.25) * L, clear=shape.get('clear_skin', 0.025) * L)
    elif shape.get('select') == 'exclude':
        hv, hf = i3d.hair_by_exclusion(V, C, F, chin_z, shape.get('shoulder_x', 0.16), below=shape.get('below', 0.25) * L)
    elif 'hue' in shape:
        hv, hf = i3d.hair_by_hue(V, C, F, shape['hue'], chin_z, shape.get('shoulder_x', 0.16),
                                 below=shape.get('below', 0.25) * L, sat=shape.get('sat', 0.38))
    else:
        hv, hf = i3d.hair_part(V, C, F, cols, chin_z, shape.get('shoulder_x', 0.16), below=shape.get('below', 0.25) * L,
                               max_d=shape.get('max_d', 0.22))
    hv, hf = cull_face(S, hv, hf, shape)
    S.hair_shape = (hv, hf)
    style = hair._style(S.spec['hair'])
    return hair.MeshVolume(Hd['H'], Hd['centre'], style, Hd['info']['target'], (hv, hf))


def hair_cap(S, hc):
    """the analytic hair volume's cap as a backstop under generated hair: no scalp shows through its gaps."""
    from . import character, hair, shade
    A = S.character['data']; Hd = A['head']
    plain = {k: v for k, v in S.spec.get('hair', {}).items() if k not in ('silhouette', 'shape')}
    plain['thick'] = min(plain.get('thick', 1.0), 1.0)
    meshes, Vol = hair.generate(Hd['H'], Hd['centre'], Hd['info']['target'], plain)
    v, f, uv = meshes['hair_cap']
    v = Vol.c + (v - Vol.c) * 0.97                          # just inside the hair
    C = dict(shade=(0.72, 0.74, 0.90), deep=(0.52, 0.52, 0.72)); C.update(hc)
    m = shade.toon3('hair_cap', C['shade'], C['deep'], tuple(np.array(C['deep']) * 0.85))
    ob = character._mesh('hair_cap', v * 0.0 + v, f, None, [m])
    for p in ob.data.polygons:
        p.use_smooth = True
    character._to_head(ob, S.character['arm'])
    return ob


def hair_volume_mesh(S, shape):
    """the generated hair as one clean closed surface: the aligned generated character clipped to the head region, voxel-
    remeshed (watertight: no double shells, no holes), minus our body inflated by `inflate` (its face, neck and the clothes
    lying on us fall away), with the same-coloured sleeves low at the sides cut off. -> (verts, faces) world."""
    import bpy, bmesh
    from . import character
    A = S.character['data']; Hd = A['head']; L = Hd['L']
    V, F = S.shape_full
    chin_z = Hd['centre'][2] - Hd['H'].chin
    zcut = chin_z - shape.get('below', 0.33) * L
    ob = character._mesh('hair_vol', V, F, None, [])
    bm = bmesh.new(); bm.from_mesh(ob.data)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    r = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, zcut), plane_no=(0, 0, 1), clear_inner=True)
    edges = [e for e in r['geom_cut'] if isinstance(e, bmesh.types.BMEdge)]
    if edges:
        bmesh.ops.holes_fill(bm, edges=edges)
    bm.to_mesh(ob.data); bm.free()
    rm = ob.modifiers.new('rm', 'REMESH'); rm.mode = 'VOXEL'; rm.voxel_size = shape.get('vox', 0.008) * L
    with bpy.context.temp_override(object=ob):
        bpy.ops.object.modifier_apply(modifier='rm')
    # our body, inflated, as the cutter
    from .anime_head import vertex_normals
    BV = A['verts'] + vertex_normals(A['verts'], A['faces']) * shape.get('inflate', 0.02) * L
    cut = character._mesh('hair_cutter', BV, A['faces'], None, [])
    bo = ob.modifiers.new('cut', 'BOOLEAN'); bo.operation = 'DIFFERENCE'; bo.object = cut; bo.solver = 'EXACT'
    with bpy.context.temp_override(object=ob):
        bpy.ops.object.modifier_apply(modifier='cut')
    bpy.data.objects.remove(cut, do_unlink=True)
    me = ob.data
    hv = np.array([v.co for v in me.vertices]); hf = [tuple(p.vertices) for p in me.polygons]
    bpy.data.objects.remove(ob, do_unlink=True)
    low = hv[:, 2] < chin_z + 0.02
    bad = low & (np.abs(hv[:, 0]) > shape.get('shoulder_x', 0.19))
    hf = [f for f in hf if not any(bad[v] for v in f)]
    return hv, hf


def hair_shape_mesh(S, shape, hc):
    """the generated hair itself as the hair: remeshed into clean even topology (voxel remesh), smoothed, reduced, shaded
    with charkit's hair look (toon ramp and outline, normals from a blurred copy of itself for big clean shadow shapes),
    rigged to the head."""
    import bpy
    from . import character, hair, shade
    if shape.get('select') == 'volume':
        S.hair_shape = cull_face(S, *hair_volume_mesh(S, shape), shape)
    hv, hf = S.hair_shape
    L = S.character['data']['head']['L']
    ob = character._mesh('hair_shape', hv, hf, None, [])
    bpy.context.view_layer.objects.active = ob
    # TRELLIS already outputs clean remeshed surfaces; a voxel remesh coarser than the hair's shell tears it into lace, so
    # it is optional (voxel > 0, and then fine)
    mods = []
    if shape.get('voxel', 0) > 0:
        rm = ob.modifiers.new('remesh', 'REMESH'); rm.mode = 'VOXEL'; rm.voxel_size = shape['voxel'] * L
        rm.use_smooth_shade = True; mods.append('remesh')
    # (plain smoothing: the Laplacian modifier explodes on the generated mesh's degenerate faces)
    sm = ob.modifiers.new('smooth', 'SMOOTH'); sm.factor = shape.get('smooth_factor', 0.5); sm.iterations = shape.get('smooth', 6)
    mods.append('smooth')
    dec = ob.modifiers.new('decimate', 'DECIMATE'); dec.ratio = shape.get('decimate', 0.5); mods.append('decimate')
    with bpy.context.temp_override(object=ob):
        for m in mods:
            bpy.ops.object.modifier_apply(modifier=m)
    # consistent outward winding (the generated surface's isn't), then merge coincident vertices
    import bmesh
    bm = bmesh.new(); bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005 * L)
    # drop the small loose fragments the selection leaves (slivers and specks); keep the pieces that make the hair
    bm.faces.ensure_lookup_table()
    seen, small, kept = set(), [], []
    min_faces = shape.get('min_part', 150)
    for f0 in bm.faces:
        if f0.index in seen:
            continue
        part, stack = [], [f0]; seen.add(f0.index)
        while stack:
            f = stack.pop(); part.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen:
                        seen.add(g.index); stack.append(g)
        if len(part) < min_faces:
            small += part
        else:
            kept.append(len(part))
    from . import trace
    ks = np.array(sorted(kept, reverse=True))
    trace.note('hair_shape.parts', kept=len(ks), largest=ks[:8].tolist(), under_50=int((ks < 50).sum()),
               faces_kept=int(ks.sum()), dropped_parts_faces=len(small), min_part=min_faces, faces_in=len(bm.faces))
    bmesh.ops.delete(bm, geom=small, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data); bm.free()
    # normals from the hair's smooth envelope (the ray-cast mass, charkit.hair.MeshVolume): big clean shadow shapes, the
    # anime way (a blurred copy of the thin two-sided shell collapses on itself and gives no clean outward direction)
    pv, pf = hair.proxy_mesh(S.hair_volume_for_normals)
    proxy = character._mesh('hair_shape_normals', pv, pf, None, [])
    proxy.hide_render = True; proxy.hide_viewport = True
    C = dict(lit=(0.96, 0.93, 0.98), shade=(0.72, 0.74, 0.90), deep=(0.52, 0.52, 0.72), line=(0.36, 0.34, 0.50)); C.update(hc)
    m = shade.toon3('hair_shape', C['lit'], C['shade'], C['deep'], rim_amt=0.0)
    m.use_backface_culling = True                        # the generated hair is a thin two-sided shell: hide its inner side
    ob.data.materials.append(m)
    for p in ob.data.polygons:
        p.use_smooth = True
    dt = ob.modifiers.new('volume_normals', 'DATA_TRANSFER'); dt.object = proxy; dt.use_loop_data = True
    dt.data_types_loops = {'CUSTOM_NORMAL'}; dt.loop_mapping = 'POLYINTERP_NEAREST'; dt.mix_factor = shape.get('normal_mix', 1.0)
    shade.outline(ob, thick=0.0014, color=C['line'], name='hair_line')
    character._to_head(ob, S.character['arm']); character._to_head(proxy, S.character['arm'])
    return ob


def stage_face_shading(S):
    from . import faceshade
    bangs = None
    fr = next((o for o in S.hair if o.name.startswith('hair_front')), None)
    if fr is not None:
        bangs = (np.array([v.co for v in fr.data.vertices]), [tuple(p.vertices) for p in fr.data.polygons])
    faceshade.apply(S.character, bangs=bangs, colors=S.skin_colors)


def stage_garments(S):
    from . import garments
    S.garments = garments.build(S.character, S.spec.get('garments'))


STAGES = [('character', stage_character), ('hair', stage_hair), ('face_shading', stage_face_shading),
          ('garments', stage_garments)]


def fit_cranium(spec, root, loaded=None):
    """the cranium knob from a generated shape: aligned by its eyes (the spec's eye spacing and head length, no build needed),
    the hair's top along the midline sets our skull's top `under` (head lengths) below it: the head fits inside the hair.
    loaded: the shape's (V, F, C) when already loaded (charkit.faceeval, without Blender)."""
    from . import i3d
    shape = (spec.get('hair') or {}).get('shape') or {}
    if not shape.get('glb') or not shape.get('fit_cranium', True):
        return spec
    P = spec.get('body', {})
    L = P.get('height_m', 1.6) / P.get('heads_tall', 6.5)
    path = shape['glb'] if os.path.isabs(shape['glb']) else os.path.join(root, shape['glb'])
    V, F, C = loaded if loaded is not None else i3d.load_glb(path)
    eyes = i3d.find_eyes(V, C)
    if eyes is None:
        return spec
    ex = spec.get('eyes', {}).get('x', 0.168)
    V = i3d.align_by_eyes(V, eyes, np.zeros(3), 2 * ex * L)            # eye line at z = 0, the midline at x = 0
    ey = (eyes[0][1] + eyes[1][1]) / 2
    # the crown: the middle of the head (behind the fringe and the ahoge, in front of the back), the hair's highest points
    # per thin slice along the midline, their median (an ahoge or a bun is an outlier)
    tops = []
    for dy in np.linspace(0.25, 0.5, 6):
        m = (np.abs(V[:, 0]) < 0.03 * L) & (np.abs(V[:, 1] - dy * L) < 0.03 * L) & (V[:, 2] > 0)
        if m.any():
            tops.append(V[m, 2].max())
    if not tops:
        return spec
    top = float(np.median(tops)) / L                                   # the hair's crown above the eye line, in L
    under = shape.get('under', 0.05)
    head = spec.setdefault('head', {})
    if 'cranium' not in head:
        head['cranium'] = round(max(0.6, min(1.1, (top - under) / 0.555)), 3)
        if loaded is None:
            print('fit_cranium: hair top %.3f L -> cranium %.3f' % (top, head['cranium']))
        from . import trace
        trace.note('fit_cranium', hair_top_L=top, slices=len(tops), cranium=head['cranium'])
    return spec


def build(spec, until=None, skip=()):
    """run the stages in order (stop after `until`, leave out `skip`). -> Scene."""
    from . import trace
    reset()
    with trace.span('fit_cranium'):
        spec = fit_cranium(spec, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    reset()
    S = Scene(spec)
    for name, fn in STAGES:
        if name not in skip:
            with trace.stage(name, S):
                fn(S)
        if name == until:
            break
    return S


# ------------------------------------------------------------------------------------------------------------------ boards
def boards(S, out, which=('views', 'expressions', 'mouths', 'body')):
    """render the review boards into out/: head views (front .. back), the expression and mouth sets, full-body views."""
    import bpy
    from . import qa, trace
    from .boards.face_board import set_expr, set_mouth
    os.makedirs(out, exist_ok=True)
    sc = bpy.context.scene
    A = S.character['data']; eye_z = A['head']['eye_z']; L = A['head']['L']
    cam = bpy.data.objects.get('board_cam')
    if cam is None:
        cam = bpy.data.objects.new('board_cam', bpy.data.cameras.new('board_cam')); sc.collection.objects.link(cam)
    sc.camera = cam
    covers = S.covers

    def shot(path, *a, **kw):
        with trace.span('board', path=os.path.basename(path)):
            qa.render_view(cam, *a, path, **kw)
            if covers:
                qa.features_through(path, S.features, covers, [S.character['skin']])
    made = []
    if 'views' in which:
        sc.render.resolution_x, sc.render.resolution_y = 900, 900
        for az in (0, 30, 60, 90, 150):
            p = os.path.join(out, f'face_{az:03d}.png'); made.append(p)
            shot(p, (0, 0, eye_z + 0.06 * L), az, 1.0, 0.0, lens=85)
    if 'body' in which:
        sc.render.resolution_x, sc.render.resolution_y = 600, 1000
        H_ = S.spec.get('body', {}).get('height_m', 1.6)
        for az in (0, 35, 90, 180):
            p = os.path.join(out, f'body_{az:03d}.png'); made.append(p)
            with trace.span('board', path=os.path.basename(p)):
                qa.render_view(cam, (0, 0, H_ * 0.52), az, 6.0, 0.0, p, ortho=H_ * 1.12)
    if 'expressions' in which:
        sc.render.resolution_x, sc.render.resolution_y = 600, 600
        for e in EXPR:
            set_expr(S.character, e)
            p = os.path.join(out, f'expr_{e}.png'); made.append(p)
            shot(p, (0, 0, eye_z - 0.02 * L), 0, 0.42, 0.0, lens=85)
        set_expr(S.character, None)
    if 'mouths' in which:
        sc.render.resolution_x, sc.render.resolution_y = 600, 600
        for m in MOUTH:
            set_mouth(S.character, m)
            p = os.path.join(out, f'mouth_{m}.png'); made.append(p)
            with trace.span('board', path=os.path.basename(p)):
                qa.render_view(cam, (0, 0, eye_z - 0.28 * L), 0, 0.30, 0.0, p, lens=85)
        set_mouth(S.character, 'neutral')
    return made


def save(path):
    import bpy
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(path), compress=True)
