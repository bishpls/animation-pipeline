"""A character scene from a spec (docs/CHARKIT.md §3), Blender-side: the stages in order, each a function of the spec and
what came before, so a build can stop after any stage, swap one out (the hair from a generated shape instead of the
analytic volume, say), or render boards from the result.

    body+head -> face features -> face shading -> hair -> accessories -> garments -> (boards, export)

    from charkit import scene; S = scene.build(spec)     # inside Blender: S.character, S.hair, S.garments, ...
    scene.boards(S, out, which=('views', 'expressions', 'mouths', 'body'))     # expressions: EXPR and PRESETS
"""
import functools, json, os

import numpy as np

SKIN = dict(lit=(1.0, 0.90, 0.86), shade=(0.95, 0.76, 0.74), deep=(0.84, 0.60, 0.62))
EXPR = ['blink', 'happy', 'half', 'wide', 'angry', 'sad', 'squint', 'shock']
MOUTH = ['neutral', 'aa', 'ih', 'ou', 'ee', 'oh', 'smile', 'grin', 'frown', 'surprised', 'laugh', 'wavy', 'yawn']
# combined expressions: the eyes, mouth and brows together (the template's own; the model sheet's heads are matched to them
# in charkit/exprqa.py, and a head none of them covers asks for a new one)
PRESETS = {
    'laugh': dict(eye='happy', mouth='laugh', brow='raise'),
    'angry': dict(eye=None, mouth='frown', brow='angry'),
    'fluster': dict(eye='shock', mouth='wavy', brow='surprised'),
    'yawn': dict(eye='blink', mouth='yawn', brow='raise'),
}


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
    elif shape and shape.get('mode') == 'pieces':
        # the hair as authored pieces, built venv-side by charkit.geom.hairpieces (python -m charkit build runs it)
        S.hair = hair_pieces_objects(S, shape, hc)
        S.hair_volume = vol
    elif shape and shape.get('mode') == 'geom':
        # the generated hair cut out venv-side by charkit.geom (python -m charkit build runs it): one closed surface
        S.hair = [hair_geom_mesh(S, shape, hc)]
        S.hair_volume = vol
        if shape.get('cap', False):
            cap = hair_cap(S, hc)
            if cap is not None:
                S.hair.append(cap)
    else:
        S.hair, S.hair_volume = hair.build(S.character['data'], S.character['arm'], S.spec.get('hair'), hc, volume=vol)
    acc = S.spec.get('accessories') or []
    if shape and shape.get('mode') in ('mesh', 'geom', 'pieces'):
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


def eye_target(A, shape):
    """i3d.eye_target (where a generated character's eyes land on ours)."""
    from . import i3d
    return i3d.eye_target(A, shape)


def hair_shape_volume(S, shape, hc):
    """the hair volume from a generated character (TRELLIS.2 GLB): aligned by its eyes onto ours, its hair taken by colour
    above the chin (not the same-coloured clothes), as a charkit.hair.MeshVolume."""
    from . import hair, i3d
    A = S.character['data']; Hd = A['head']; L = Hd['L']
    path = shape['glb'] if os.path.isabs(shape['glb']) else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), shape['glb'])
    V, F, C = i3d.load_glb(path)
    eyes = i3d.glb_eyes(path, V, C)
    if eyes is None:
        raise RuntimeError('no eyes found on the generated shape')
    eye_mid, spacing = eye_target(A, shape)
    V = i3d.align_by_eyes(V, eyes, eye_mid, spacing)
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


def hair_geom_mesh(S, shape, hc):
    """the hair charkit.geom extracted (shape['geom']: its .npz, written by `python -m charkit build` venv-side): a closed,
    manifold surface in world space with envelope normals as custom split normals, given charkit's hair look and outline
    and rigged to the head. No remesh, smoothing or culling here: the kernel did it."""
    from . import character, shade
    from .geom.blender import load_part
    path = shape['geom'] if os.path.isabs(shape['geom']) else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), shape['geom'])
    C = dict(lit=(0.96, 0.93, 0.98), shade=(0.72, 0.74, 0.90), deep=(0.52, 0.52, 0.72), line=(0.36, 0.34, 0.50)); C.update(hc)
    m = shade.toon3('hair_shape', C['lit'], C['shade'], C['deep'], rim_amt=0.0)
    from .geom.blender import normals_proxy, transfer_normals
    envelope = shape.get('normals', 'envelope') == 'envelope'
    ob, meta = load_part(path, 'hair_shape', material=m, normals=None if envelope else 'geometric')
    from . import trace
    rep = (meta or {}).get('report') or {}
    trace.note('hair_geom', path=os.path.basename(path), faces=rep.get('faces'), open_edges=rep.get('open_edges'),
               shells=rep.get('shells', rep.get('parts')), self_intersecting=rep.get('self_intersecting_faces_est'))
    shade.outline(ob, thick=0.0014, color=C['line'], name='hair_line')
    if envelope:
        # the envelope normals ride in after the outline (Solidify would re-derive custom normals set on the mesh)
        proxy = normals_proxy(path, 'hair_shape_normals')
        transfer_normals(ob, proxy)
        character._to_head(proxy, S.character['arm'])
    character._to_head(ob, S.character['arm'])
    return ob


PIECE_NORMALS = 'exact'   # the hair pieces' envelope normals: 'exact' (geom.blender.set_normals, one per vertex) or
                          # 'transfer' (a hidden proxy's by position: 400 of a side lock's vertices took a coincident or
                          # near neighbour's, up to 12.7 degrees off; face round 4)


def hair_pieces_objects(S, shape, hc):
    """the hair's pieces (shape['pieces']: charkit.geom.hairpieces' parts and pieces.json, written venv-side) as one
    object each (hair_NAME), with charkit's hair look and outline, rigged to the head; the style's 'envelope' normals ride
    in after the outline from a hidden proxy (as the geom hair's do), so the pieces shade as one mass."""
    from . import character, shade, trace
    from .geom.blender import load_part, normals_proxy, set_normals, transfer_normals
    from .geom.io import load_npz
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pdir = shape['pieces'] if os.path.isabs(shape['pieces']) else os.path.join(root, shape['pieces'])
    index = json.load(open(os.path.join(pdir, 'pieces.json')))
    C = dict(lit=(0.96, 0.93, 0.98), shade=(0.72, 0.74, 0.90), deep=(0.52, 0.52, 0.72), line=(0.36, 0.34, 0.50)); C.update(hc)
    # the look's hair materials (charkit.shade.hair_toon): the drawn highlight, the under layers a step darker
    hl = shade.look_of(S.spec).get('hair') or {}
    centre = S.character['data']['head']['centre']
    m = shade.hair_toon('hair_shape', C['lit'], C['shade'], C['deep'], centre, hl)
    under = set(hl.get('under', ())) if hl.get('lock_shade') else set()
    m_under = shade.hair_toon('hair_under', C['lit'], C['shade'], C['deep'], centre, dict(hl, highlight=None),
                              inner=hl.get('lock_shade', 0.0)) if under else m
    envelope = index.get('normals', 'envelope') == 'envelope'
    obs = []
    for p in index['pieces']:
        path = os.path.join(pdir, p['file'])
        ob, meta = load_part(path, 'hair_' + p['name'], material=m_under if p['family'] in under else m,
                             normals=None if envelope else 'geometric')
        ob['charkit_family'] = p['family']
        shade.outline(ob, thick=0.0014, color=C['line'], name='hair_line')
        if envelope and not (PIECE_NORMALS == 'exact' and set_normals(ob, load_npz(path).vn) is not None):
            proxy = normals_proxy(path, 'hair_%s_normals' % p['name'])
            transfer_normals(ob, proxy)
            character._to_head(proxy, S.character['arm'])
        character._to_head(ob, S.character['arm'])
        obs.append(ob)
    trace.note('hair_pieces', pieces=[p['name'] for p in index['pieces']],
               locks={p['name']: p['locks'] for p in index['pieces']})
    return obs


def stage_face_shading(S):
    from . import faceshade, shade
    look = shade.look_of(S.spec)
    bangs = None
    # the hair that shades the face: the analytic hair's hair_front, the cut pieces' bangs (and with the look's
    # face.fringe_sides their side locks too), as one mesh
    fam = ('bangs', 'side_locks') if (look.get('face') or {}).get('fringe_sides') else ('bangs',)
    frs = [o for o in S.hair if o.name.startswith('hair_front') or o.name == 'hair_bangs'
           or o.get('charkit_family') in fam]
    if frs and (look.get('face') or {}).get('fringe', True):
        Vs, Fs, off = [], [], 0
        for fr in frs:
            M = np.array(fr.matrix_world)
            co = np.array([v.co for v in fr.data.vertices])
            Vs.append(co @ M[:3, :3].T + M[:3, 3])
            Fs += [tuple(i + off for i in p.vertices) for p in fr.data.polygons]
            off += len(co)
        bangs = (np.concatenate(Vs), Fs)
    ln = look.get('lines') or {}
    look = dict(look, face=dict(look.get('face') or {}, ink_color=tuple(
        ln['ink'] if ln.get('color') == 'ink' else S.spec.get('skin_line', (0.42, 0.24, 0.20)))))
    faceshade.apply(S.character, bangs=bangs, colors=S.skin_colors, look=look)


def stage_garments(S):
    from . import garments
    specs = S.spec.get('garments')
    if S.spec.get('garments_geom'):
        # the garments computed venv-side (`python -m charkit build` runs charkit.geomstage.garments_step, the evaluator's
        # own step): Blender only replays the objects, materials, modifiers and the skin mask (docs/GEOM_TRUTH.md)
        from . import geomstage
        S.garments = geomstage.garments_instantiate(S, S.spec['garments_geom'])
        return
    hull = garments.hull_pieces(S.spec, S.character['data']) if any(g.get('source') == 'hull' for g in specs or []) \
        else None
    S.garments = garments.build(S.character, specs, hull=hull, spec_all=S.spec)


STAGES = [('character', stage_character), ('hair', stage_hair), ('face_shading', stage_face_shading),
          ('garments', stage_garments)]


# ------------------------------------------------------------------------------------------------------ the stage cache
# What a stage reads of earlier stages' output only in part (charkit/cache.py keys every other read whole, exactly).
# 'structure': a Blender object's names, modifier stack, groups, slots and transform, not its geometry (a stage that only
# parents to the rig, or adds a group and a modifier to the skin). A function: the part of the value that matters.
GARMENT_KINDS = ('shell', 'band', 'shoe', 'boot', 'belt', 'sleeve', 'skirt', 'panel', 'collar', 'bow')


def body_below_neck(verts, S):
    """garments read the body below the neck's middle: shell regions (the Clawd top reaches 0.3 up the neck), the collar's
    neckline (0.08 L round the neck's base), bands, the skirt's and belt's sections, the bow on the chest, nearest-vertex
    weights for pieces lying on the torso and limbs. -> (the cut's height, the rows under it, their positions); all of
    verts when an outfit reaches higher (a region, cut or band on the head or past the neck's middle, a kind this doesn't
    know)."""
    from . import mh
    J = S.character['data']['joints']
    h, t = (np.asarray(J[k], float) for k in mh.VRM_JOINTS['neck'])
    for g in S.spec.get('garments') or []:
        if g.get('kind') not in GARMENT_KINDS or g.get('kind') == 'collar' and g.get('rise', 0.0) > 0.05:
            return verts
        for bone, *rest in list(g.get('region', [])) + list(g.get('cuts', [])) + ([[g['bone'], g.get('t', 0.5)]]
                                                                                    if 'bone' in g else []):
            ts = [x for x in rest if isinstance(x, (int, float))]
            if bone == 'head' or bone == 'neck' and max(ts, default=1.0) > 0.45:
                return verts
    z = float(0.5 * (h[2] + t[2]))
    rows = np.nonzero(verts[:, 2] < z)[0]
    return z, rows, verts[rows]


def fringe(objs, S):
    """face shading reads which hair objects there are and the fringe (hair_front*: its shadow on the face), not the
    rest of the hair."""
    return [o.name for o in objs], [o for o in objs if o.name.startswith('hair_front')]


DEPS = {
    'hair': {'character.arm': 'structure'},
    'face_shading': {'character.skin': 'structure', 'hair': fringe},
    'garments': {'character.skin': 'structure', 'character.arm': 'structure', 'character.data.verts': body_below_neck},
}


def fit_cranium(spec, root, load=None):
    """the cranium knob from a generated shape: aligned by its eyes (the spec's eye spacing and head length, no build needed),
    the hair's top along the midline sets our skull's top `under` (head lengths) below it: the head fits inside the hair.
    load: the GLB reader, path -> (V, F, C) (default charkit.i3d.load_glb, in Blender; charkit.geom.parts.load_generated
    reads the same numbers in the venv)."""
    from . import i3d
    shape = (spec.get('hair') or {}).get('shape') or {}
    if not shape.get('glb') or not shape.get('fit_cranium', True):
        return spec
    P = spec.get('body', {})
    L = P.get('height_m', 1.6) / P.get('heads_tall', 6.5)
    path = shape['glb'] if os.path.isabs(shape['glb']) else os.path.join(root, shape['glb'])
    V, F, C = (load or i3d.load_glb)(path)
    eyes = i3d.glb_eyes(path, V, C)
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
        print('fit_cranium: hair top %.3f L -> cranium %.3f' % (top, head['cranium']))
        from . import trace
        trace.note('fit_cranium', hair_top_L=top, slices=len(tops), cranium=head['cranium'])
    return spec


def build(spec, until=None, skip=(), cache=None):
    """run the stages in order (stop after `until`, leave out `skip`), each restored from `cache` (a charkit.cache.Cache)
    instead when nothing it reads has changed. -> Scene."""
    from . import trace
    reset()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if cache is None:
        with trace.span('fit_cranium'):
            spec = fit_cranium(spec, root)
    else:
        spec = cache.spec_step('fit_cranium', fit_cranium, spec, root)
    reset()
    from . import shade
    shade.set_look(shade.look_of(spec))              # the style's look: each board view's light and line widths
    S = Scene(spec)
    for name, fn in STAGES:
        if name not in skip:
            if cache is None:
                with trace.stage(name, S):
                    fn(S)
            else:
                cache.stage(name, fn, S, DEPS.get(name))
        if name == until:
            break
    shade.line_colors()                              # the look's outline colours (after the stages: not cached)
    return S


# ------------------------------------------------------------------------------------------------------------------ boards
def boards(S, out, which=('views', 'expressions', 'mouths', 'body')):
    """render the review boards into out/: head views (front .. back), the expression and mouth sets, full-body views,
    the head in the design's projection ('design')."""
    import bpy
    from . import qa
    from .boards.face_board import set_expr, set_mouth, set_preset
    os.makedirs(out, exist_ok=True)
    sc = bpy.context.scene
    A = S.character['data']; eye_z = A['head']['eye_z']; L = A['head']['L']
    cam = bpy.data.objects.get('board_cam')
    if cam is None:
        cam = bpy.data.objects.new('board_cam', bpy.data.cameras.new('board_cam')); sc.collection.objects.link(cam)
    sc.camera = cam
    # each set's views as one animation render where they share a camera (qa.render_views: the same pictures as a
    # still per view, in a quarter of the time); the features laid through the hair where there are covers
    feats = (S.features, S.covers, [S.character['skin']]) if S.covers else None
    V = qa.View
    made = []
    if 'views' in which:
        sc.render.resolution_x, sc.render.resolution_y = 900, 900
        made += qa.render_views(cam, [V((0, 0, eye_z + 0.06 * L), az, 1.0, 0.0, os.path.join(out, f'face_{az:03d}.png'),
                                        lens=85) for az in (0, 30, 60, 90, 150)], features=feats)
    if 'body' in which:
        sc.render.resolution_x, sc.render.resolution_y = 600, 1000
        H_ = S.spec.get('body', {}).get('height_m', 1.6)
        made += qa.render_views(cam, [V((0, 0, H_ * 0.52), az, 6.0, 0.0, os.path.join(out, f'body_{az:03d}.png'),
                                        ortho=H_ * 1.12) for az in (0, 35, 90, 180)])
    if 'design' in which:
        # the design's projection (head_turnaround's: level and orthographic), for review close-ups (charkit.preview crops
        # them to the design's scale): centred on the head at its eye line, 2.4 L across at 400 px per L (head_turnaround
        # is ~400 at its own size), at the design's azimuths (0, 35, 90, 180) and a turntable. The views above look from a
        # perspective camera 1 m out, which rounds the chin. (Local constants: scene's top level keys every stage.)
        DESIGN_WINDOW, DESIGN_PPL = 2.4, 400
        DESIGN_AZ = (0, 30, 35, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330)
        n = int(round(DESIGN_WINDOW * DESIGN_PPL))
        sc.render.resolution_x, sc.render.resolution_y = n, n
        c = A['head'].get('centre')
        c = (0.0, 0.0, eye_z) if c is None else [float(x) for x in c]
        made += qa.render_views(cam, [V((c[0], c[1], eye_z), az, 4.0, 0.0, os.path.join(out, f'design_{az:03d}.png'),
                                        ortho=DESIGN_WINDOW * L) for az in DESIGN_AZ], features=feats)
    if 'expressions' in which:
        sc.render.resolution_x, sc.render.resolution_y = 600, 600
        made += qa.render_views(cam, [V((0, 0, eye_z - 0.02 * L), 0, 0.42, 0.0, os.path.join(out, f'expr_{e}.png'),
                                        lens=85, state=functools.partial(set_expr, S.character, e)) for e in EXPR],
                                features=feats)
        set_expr(S.character, None)
        made += qa.render_views(cam, [V((0, 0, eye_z - 0.12 * L), 0, 0.5, 0.0, os.path.join(out, f'preset_{e}.png'),
                                        lens=85, state=functools.partial(set_preset, S.character, e))
                                      for e in PRESETS], features=feats)
        set_preset(S.character, None)
    if 'mouths' in which:
        sc.render.resolution_x, sc.render.resolution_y = 600, 600
        made += qa.render_views(cam, [V((0, 0, eye_z - 0.28 * L), 0, 0.30, 0.0, os.path.join(out, f'mouth_{m}.png'),
                                        lens=85, state=functools.partial(set_mouth, S.character, m)) for m in MOUTH])
        set_mouth(S.character, 'neutral')
    from . import shade
    shade.set_view(0)                                # the front's light and the build's line widths back (the bundle and
    return made                                      # the export read them)


def save(path):
    import bpy
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(path), compress=True)
