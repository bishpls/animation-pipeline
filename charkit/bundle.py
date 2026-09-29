"""The geometry bundle (schema charkit.bundle/1, docs/CHARKIT.md §4): everything the QA measures of one build, written once
by the Blender stage and read in the venv, where every check runs (charkit.qa3d). The fast evaluators (charkit.faceeval)
make the same object in memory, so a fit's objective and the build's QA are one measurement.

    OUT/bundle/bundle.json   the schema, the content hash, each array's hash, and the metadata (below)
    OUT/bundle/arrays.npz    the arrays by name ('o/clawd_skin/eval/V', 'img/iris', ...)

The metadata: `spec` (the resolved spec the scene was built from), `ref_measure` (the design rig's measures), `assembly`
(the head: L, centre, the chin, the eye knobs; each eye's centre, side and lid chains; the mouth's centre and lip chains;
the waist and knee heights), `landmarks` (charkit.trace's), `materials` (per material: its flat tones as
material_tones reads them, the texture it multiplies in, back-face culling, and a plain toon3's shading parameters),
`images` (their sizes: pixels in `img/NAME`, rows bottom-up as Blender keeps them, bytes where Blender stores bytes),
`target` (the generated character, aligned as the build aligned it) and `objects`.

Each object (the skin, the eye and mouth parts, the hair, accessories and garments) has its group, part, side, visibility,
material slots and, when it has one, its outline hull's material slot; and one or more variants of its geometry, each
V (float64 world, as Blender evaluates it), polygons (`loopv` per corner, `counts` per polygon), `pmat` (a material slot
per polygon), and per variant as needed `luv` (UV per corner), `lnor` (the render's normal per corner), `shrink` (how
far the outline modifier pulls each vertex in: the rendered surface is V + shrink and its hull V, flipped and culled),
`parent` (the base polygon each polygon came from) and `keys` (shape keys: world offsets, sparse):
  eval         the evaluated mesh without its outline hull or garment mask (what trace.mesh_arrays reads)
  masked       the skin with its garment mask on (what renders)
  base         the armature-posed base mesh with its shape keys (as Blender holds them: float32)
  assembly     the skin as the assembly made it (float64) with its lid and mouth keys (the fold count's)
  raw          the mesh data itself (hair and garments: poke-through, open edges)
  render_eye_L the skin round each eye at the render's subdivision level, its garment mask on (the eye renders)

    B = bundle.load('OUT/bundle')
    for o in B.objects(groups=('hair',)): V, T = o.mesh('eval')[:2]
"""
import hashlib, json, os, time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = 'charkit.bundle/1'
META, ARRAYS = 'bundle.json', 'arrays.npz'
GROUPS = ('skin', 'eye', 'mouth', 'hair', 'accessory', 'garment')
EYE_BOX = 0.42                      # the eye render's window (L, square round each eye centre; charkit.qa3d.EYE_SIZE)
EYE_MARGIN = 0.03                   # the render patch reaches this far past the window (L)


# ------------------------------------------------------------------------------------------------------ materials (bpy)
def _srgb(c):
    c = np.clip(np.asarray(c, float)[:3], 0, None)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def material_tones(m):
    """what a material renders unlit, read from its nodes (no override, no render): toon3's lit, shade and deep tones (sRGB)
    or a flat emission's colour, and the image a texture multiplies in (a textured toon, an eye plate) or None.
    -> dict(lit, shade, deep, image)."""
    out = dict(lit=None, shade=None, deep=None, image=None)
    if m is None or not m.use_nodes:
        return out
    nodes = m.node_tree.nodes
    for n in nodes:                     # toon3: the lit mix takes the shade/deep mix in A and the lit tone in B
        if n.type == 'MIX' and getattr(n, 'data_type', '') == 'RGBA' and n.blend_type == 'MIX' and \
                n.inputs['A'].is_linked and not n.inputs['B'].is_linked:
            src = n.inputs['A'].links[0].from_node
            if src.type == 'MIX' and not src.inputs['A'].is_linked and not src.inputs['B'].is_linked:
                out.update(lit=_srgb(n.inputs['B'].default_value), shade=_srgb(src.inputs['B'].default_value),
                           deep=_srgb(src.inputs['A'].default_value))
                break
    for n in nodes:
        if n.type == 'MIX' and getattr(n, 'data_type', '') == 'RGBA' and n.blend_type == 'MULTIPLY' and \
                not n.inputs['Factor'].is_linked and n.inputs['B'].is_linked and n.inputs['B'].links[0].from_node.type == 'TEX_IMAGE':
            out['image'] = n.inputs['B'].links[0].from_node.image                    # a textured toon (skirt, panel)
    em = next((n for n in nodes if n.type == 'EMISSION'), None)
    if out['lit'] is None and em is not None:
        c = em.inputs['Color']
        if not c.is_linked:
            out['lit'] = out['shade'] = out['deep'] = _srgb(c.default_value)
        elif c.links[0].from_node.type == 'TEX_IMAGE':                                # a plate: the image is the colour
            out['image'] = c.links[0].from_node.image
            out['lit'] = out['shade'] = out['deep'] = np.ones(3)
    return out


def _toon3(m):
    """a charkit.shade.toon3 material's shading (the emission fed by its rim screen, or by the screen multiplied by a
    texture: a textured toon), else None: dict(ldir, lit, shade, deep (linear), lit_at, deep_at (ramp element
    positions), rim, rim_amt, blend, rim_from, strength, texture (the image multiplied in, or None))."""
    nodes = m.node_tree.nodes
    em = next((n for n in nodes if n.type == 'EMISSION'), None)
    if em is None or not em.inputs['Color'].is_linked:
        return None
    rm = em.inputs['Color'].links[0].from_node
    texture = None
    if rm.type == 'MIX' and rm.blend_type == 'MULTIPLY' and not rm.inputs['Factor'].is_linked and \
            rm.inputs['B'].is_linked and rm.inputs['B'].links[0].from_node.type == 'TEX_IMAGE' and rm.inputs['A'].is_linked:
        texture = rm.inputs['B'].links[0].from_node.image
        rm = rm.inputs['A'].links[0].from_node
    if rm.type != 'MIX' or rm.blend_type != 'SCREEN' or not rm.inputs['A'].is_linked:
        return None
    m2 = rm.inputs['A'].links[0].from_node
    if m2.type != 'MIX' or not m2.inputs['A'].is_linked or not m2.inputs['Factor'].is_linked:
        return None
    m1 = m2.inputs['A'].links[0].from_node
    s_lit, s_deep = m2.inputs['Factor'].links[0].from_node, m1.inputs['Factor'].links[0].from_node
    ld = nodes.get('ldir')
    lm2 = rm.inputs['Factor'].links[0].from_node
    lm = lm2.inputs[0].links[0].from_node
    rr = lm.inputs[0].links[0].from_node
    lw = rr.inputs['Value'].links[0].from_node
    if ld is None or s_lit.type != 'VALTORGB' or s_deep.type != 'VALTORGB' or lw.type != 'LAYER_WEIGHT':
        return None
    pos = lambda r: [float(e.position) for e in r.color_ramp.elements]
    return dict(ldir=[float(ld.inputs[i].default_value) for i in range(3)], lit=list(m2.inputs['B'].default_value)[:3],
                shade=list(m1.inputs['B'].default_value)[:3], deep=list(m1.inputs['A'].default_value)[:3],
                lit_at=pos(s_lit), deep_at=pos(s_deep), rim=list(rm.inputs['B'].default_value)[:3],
                rim_amt=float(lm.inputs[1].default_value), blend=float(lw.inputs['Blend'].default_value),
                rim_from=[float(rr.inputs['From Min'].default_value), float(rr.inputs['From Max'].default_value)],
                strength=float(em.inputs['Strength'].default_value), texture=texture.name if texture is not None else None)


def material_record(m):
    """a material as the bundle keeps it: tones (material_tones), texture, culling, and how it shades: 'toon3' (plain,
    with its parameters), 'flat' (an emission colour), 'plate' (an emission texture), else 'other'."""
    t = material_tones(m)
    rec = {k: (None if t[k] is None else [float(x) for x in t[k]]) for k in ('lit', 'shade', 'deep')}
    rec['image'] = t['image'].name if t['image'] is not None else None
    rec['cull'] = bool(m is not None and m.use_backface_culling)
    kind, shading = 'other', None
    if m is not None and m.use_nodes:
        em = next((n for n in m.node_tree.nodes if n.type == 'EMISSION'), None)
        shading = _toon3(m)
        if shading is not None:
            kind = 'toon3'
        elif em is not None and not em.inputs['Color'].is_linked:
            kind = 'flat'
            shading = dict(color=list(em.inputs['Color'].default_value)[:3], strength=float(em.inputs['Strength'].default_value))
        elif em is not None and em.inputs['Color'].links[0].from_node.type == 'TEX_IMAGE':
            kind = 'plate'
            tx = em.inputs['Color'].links[0].from_node
            shading = dict(interpolation=tx.interpolation, extension=tx.extension)
    rec.update(kind=kind, shading=shading)
    return rec


def _image(img):
    """a Blender image's pixels as stored (rows bottom-up, RGBA): bytes for a byte image (exact), else float32."""
    w, h = img.size
    px = np.empty(w * h * img.channels, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, img.channels)
    if img.channels == 3:
        px = np.concatenate([px, np.ones((h, w, 1), np.float32)], -1)
    if not img.is_float:
        return np.round(px * 255).astype(np.uint8)
    return px


# ------------------------------------------------------------------------------------------------------ meshes (bpy)
def _read(ob, uv=False, normals=False):
    """the evaluated mesh as it stands (the caller sets the modifiers): dict(V float64 world, loopv, counts, pmat,
    luv?, lnor?)."""
    import bpy
    dg = bpy.context.evaluated_depsgraph_get()
    oe = ob.evaluated_get(dg)
    me = oe.to_mesh()
    try:
        n = len(me.vertices)
        co = np.empty(n * 3, np.float64); me.vertices.foreach_get('co', co)
        M = np.array(ob.matrix_world)
        V = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
        nf = len(me.polygons)
        counts = np.empty(nf, np.int64); me.polygons.foreach_get('loop_total', counts)
        starts = np.empty(nf, np.int64); me.polygons.foreach_get('loop_start', starts)
        loopv = np.empty(len(me.loops), np.int64); me.loops.foreach_get('vertex_index', loopv)
        if nf and not np.array_equal(starts, np.concatenate([[0], np.cumsum(counts)[:-1]])):
            order = np.concatenate([np.arange(s, s + c) for s, c in zip(starts, counts)])
            loopv = loopv[order]
        else:
            order = None
        pmat = np.empty(nf, np.int64); me.polygons.foreach_get('material_index', pmat)
        out = dict(V=V, loopv=loopv.astype(np.int32), counts=counts.astype(np.int32), pmat=pmat.astype(np.int16))
        if uv:
            lay = me.uv_layers.get('uv')
            if lay is not None and len(me.loops):
                luv = np.empty(len(me.loops) * 2, np.float32); lay.data.foreach_get('uv', luv)
                luv = luv.reshape(-1, 2)
                out['luv'] = luv[order] if order is not None else luv
        if normals and len(me.loops):
            cn = np.empty(len(me.loops) * 3, np.float32)
            me.corner_normals.foreach_get('vector', cn)
            cn = cn.reshape(-1, 3) @ M[:3, :3].T.astype(np.float32)
            out['lnor'] = (cn[order] if order is not None else cn).astype(np.float32)
        if 'bundle_parent' in me.attributes:
            par = np.empty(nf, np.int32); me.attributes['bundle_parent'].data.foreach_get('value', par)
            out['parent'] = par
        return out
    finally:
        oe.to_mesh_clear()


def _mods(ob, on):
    """set which modifiers show (a predicate on the modifier) -> the previous state, for _restore."""
    prev = [(m, m.show_viewport) for m in ob.modifiers]
    for m in ob.modifiers:
        m.show_viewport = bool(on(m))
    return prev


def _restore(prev):
    for m, v in prev:
        m.show_viewport = v


def _sparse(D, tol=0.0):
    D = np.asarray(D, float)
    idx = np.nonzero(np.abs(D).max(1) > tol)[0] if len(D) else np.zeros(0, np.int64)
    return idx.astype(np.int32), D[idx]


def _key_offsets(ob):
    """an object's shape keys as world offsets from its basis -> {name: (idx, D)}."""
    ks = ob.data.shape_keys
    if not ks:
        return {}
    n = len(ob.data.vertices)
    base = np.empty(n * 3); ks.key_blocks[0].data.foreach_get('co', base)
    M3 = np.array(ob.matrix_world)[:3, :3]
    out = {}
    for kb in ks.key_blocks[1:]:
        co = np.empty(n * 3); kb.data.foreach_get('co', co)
        out[kb.name] = _sparse(((co - base).reshape(-1, 3)) @ M3.T)
    return out


def _outline(ob):
    """the inverted-hull outline modifier (charkit.shade.outline names it 'outline') or None."""
    m = ob.modifiers.get('outline')
    return m if m is not None and m.type == 'SOLIDIFY' else None


def _polys_in_box(G, box):
    """the polygons with a vertex inside box (x0, x1, z0, z1), compacted -> the same dict shape."""
    V = G['V']
    x0, x1, z0, z1 = box
    inside = (V[:, 0] > x0) & (V[:, 0] < x1) & (V[:, 2] > z0) & (V[:, 2] < z1)
    cnt = G['counts'].astype(np.int64)
    pid = np.repeat(np.arange(len(cnt)), cnt)
    keep = np.zeros(len(cnt), bool)
    np.logical_or.at(keep, pid, inside[G['loopv']])
    lk = keep[pid]
    loopv = G['loopv'][lk]
    used = np.unique(loopv)
    remap = np.full(len(V), -1, np.int64); remap[used] = np.arange(len(used))
    out = dict(V=V[used], loopv=remap[loopv].astype(np.int32), counts=G['counts'][keep], pmat=G['pmat'][keep])
    for k in ('shrink',):
        if k in G:
            out[k] = G[k][used]
    return out


def export(S, out, ref_measure=None):
    """write the scene's bundle into `out` (inside Blender, after scene.build): see the module. -> the bundle.json path."""
    import bpy
    from . import trace
    t0 = time.perf_counter()
    os.makedirs(out, exist_ok=True)
    ch = S.character
    A = ch['data']; Hd = A['head']; L = float(Hd['L'])
    skin = ch['skin']
    objects = [(skin, 'skin', None, None)]
    for E, p in zip(A['eyes'], ch['eyes']):
        side = 'L' if E['side'] > 0 else 'R'
        for k in ('sclera', 'iris', 'lash', 'brow'):
            if p.get(k) is not None:
                objects.append((p[k], 'eye', k, side))
    for nm, o in ch['mouth'].items():
        if o is not None:
            objects.append((o, 'mouth', nm, None))
    objects += [(o, 'hair', None, None) for o in S.hair if o.type == 'MESH']
    objects += [(o, 'accessory', None, None) for o in S.accessories if o.type == 'MESH']
    objects += [(o, 'garment', None, None) for o in S.garments if o.type == 'MESH']
    arrays, recs, mats = {}, [], {}

    def put(name, variant, G):
        for k, v in G.items():
            if k == 'keys':
                for kn, (idx, D) in v.items():
                    arrays['o/%s/%s/keys/%s/idx' % (name, variant, kn)] = idx
                    arrays['o/%s/%s/keys/%s/d' % (name, variant, kn)] = D
            else:
                arrays['o/%s/%s/%s' % (name, variant, k)] = v
    # the skin's base polygon per evaluated polygon (the subdivision copies a face attribute to the faces it makes)
    at = skin.data.attributes.new('bundle_parent', 'INT', 'FACE')
    at.data.foreach_set('value', np.arange(len(skin.data.polygons), dtype=np.int32))
    try:
        for ob, group, part, side in objects:
            ol = _outline(ob)
            rec = dict(name=ob.name, group=group, part=part, side=side, hidden=bool(ob.hide_render),
                       materials=[m.name if m else None for m in ob.data.materials],
                       outline=None, variants=[])
            for m in ob.data.materials:
                if m is not None and m.name not in mats:
                    mats[m.name] = m
            if ol is not None:
                rec['outline'] = dict(slot=int(ol.material_offset), thickness=float(ol.thickness), offset=float(ol.offset))
            uv = bool(ob.data.uv_layers.get('uv'))
            hair = group == 'hair'
            # eval: no outline, no garment mask
            oln = ol.name if ol is not None else None
            prev = _mods(ob, lambda m: m.show_viewport and m.name not in trace.OUTLINE_MODS and m.name != oln)
            try:
                G = _read(ob, uv=uv)
            finally:
                _restore(prev)
            if ob.name != skin.name:
                G.pop('parent', None)
            variants = {'eval': G}
            if ob.name == skin.name:
                prev = _mods(ob, lambda m: m.show_viewport and m.name != oln)
                try:
                    variants['masked'] = _read(ob, uv=uv)
                finally:
                    _restore(prev)
            if ol is not None:
                # the outline pulls the surface in (the solidify's first half is the original vertices, moved) and leaves
                # its hull on the original surface: the render's shrink and normals come from the evaluation with it on
                key = 'masked' if ob.name == skin.name else 'eval'
                prev = _mods(ob, lambda m: m.show_viewport and (m.name != 'under_garments' or ob.name == skin.name))
                try:
                    Go = _read(ob, normals=hair)
                finally:
                    _restore(prev)
                Gv = variants[key]
                n, nl = len(Gv['V']), len(Gv['loopv'])
                if len(Go['V']) >= 2 * n and np.array_equal(Go['loopv'][:nl], Gv['loopv']):
                    Gv['shrink'] = (Go['V'][:n] - Gv['V']).astype(np.float32)
                    if hair:
                        Gv['lnor'] = Go['lnor'][:nl]
                else:
                    rec['outline']['unmatched'] = True
            elif hair:
                Gv = variants['eval']
                Gn = _read(ob, normals=True)
                if np.array_equal(Gn['loopv'], Gv['loopv']):
                    Gv['lnor'] = Gn['lnor']
            if ob.data.shape_keys:
                prev = _mods(ob, lambda m: m.type == 'ARMATURE')
                try:
                    Gb = _read(ob, uv=uv)
                finally:
                    _restore(prev)
                Gb.pop('parent', None)
                Gb['keys'] = _key_offsets(ob)
                variants['base'] = Gb
            if group in ('hair', 'garment'):
                me = ob.data
                co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', co)
                Mw = np.array(ob.matrix_world)
                cnt = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get('loop_total', cnt)
                lv = np.empty(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', lv)
                variants['raw'] = dict(V=co.reshape(-1, 3) @ Mw[:3, :3].T + Mw[:3, 3], loopv=lv, counts=cnt,
                                       pmat=np.zeros(len(cnt), np.int16))
            for vn, G in variants.items():
                put(ob.name, vn, G)
                rec['variants'].append(vn)
            recs.append(rec)
        # the skin's assembly: the assembly's own mesh and lid and mouth keys, float64 as charkit.character made them
        # (the fold count reads these; the shape keys Blender holds are them in float32)
        G = assembly_variant(A)
        put(skin.name, 'assembly', dict(G, loopv=G['loopv'].astype(np.int32)))
        recs[0]['variants'].append('assembly')
        # the eye renders' skin: each eye's window at the render's subdivision level, the garment mask on
        sub = next((m for m in skin.modifiers if m.type == 'SUBSURF'), None)
        lv0 = sub.levels if sub is not None else None
        try:
            if sub is not None:
                sub.levels = sub.render_levels
            prev = _mods(skin, lambda m: m.show_viewport and m.name != 'outline')
            try:
                Gr = _read(skin)
            finally:
                _restore(prev)
            Go = _read(skin)
            n, nl = len(Gr['V']), len(Gr['loopv'])
            if len(Go['V']) >= 2 * n and np.array_equal(Go['loopv'][:nl], Gr['loopv']):
                Gr['shrink'] = (Go['V'][:n] - Gr['V']).astype(np.float32)
            del Go
        finally:
            if sub is not None:
                sub.levels = lv0
        Gr.pop('parent', None)
        for E in A['eyes']:
            tag = 'L' if E['side'] > 0 else 'R'
            h = EYE_BOX / 2 + EYE_MARGIN
            G = _polys_in_box(Gr, (E['c'][0] - h * L, E['c'][0] + h * L, E['c'][1] - h * L, E['c'][1] + h * L))
            put(skin.name, 'render_eye_' + tag, G)
            recs[0]['variants'].append('render_eye_' + tag)
    finally:
        skin.data.attributes.remove(skin.data.attributes['bundle_parent'])
    # the full-figure views' framing: the objects' own meshes' heights (as charkit.qa3d_blender frames them)
    zs = []
    for ob, *_ in objects:
        if len(ob.data.vertices):
            co = np.empty(len(ob.data.vertices) * 3, np.float32); ob.data.vertices.foreach_get('co', co)
            M = np.array(ob.matrix_world)
            zs.append((co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3])[:, 2])
    zs = np.concatenate(zs)
    # what the garment mask hides (the base vertices under the clothes)
    g = skin.vertex_groups.get('under_garments')
    hidden = np.zeros(len(skin.data.vertices), bool)
    if g is not None:
        for v in skin.data.vertices:
            for e in v.groups:
                if e.group == g.index and e.weight > 0.5:
                    hidden[v.index] = True
    arrays['skin/under_garments'] = hidden
    # the assembly's per-vertex head weight (the scalp region) and what the checks read of the head, eyes and mouth
    arrays['assembly/head_w'] = np.asarray(A['body']['head_w'], float)
    asm = assembly_meta(A, S.spec)
    asm['raw_z'] = [float(zs.min()), float(zs.max())]
    # materials and their images
    mrec, images = {}, {}
    for name, m in mats.items():
        mrec[name] = material_record(m)
        t = material_tones(m)
        if t['image'] is not None and t['image'].name not in images:        # (what a check samples: plates, textured
            images[t['image'].name] = _image(t['image'])                    # toons; not the face shading's maps)
    for name, px in images.items():
        arrays['img/' + name] = px
    # the generated character, aligned as the build aligned it
    target = None
    full, cols = getattr(S, 'shape_full', None), getattr(S, 'shape_colors', None)
    if full is not None and cols is not None:
        arrays['target/V'] = np.asarray(full[0], float)
        F = full[1]
        arrays['target/T'] = np.asarray(F, np.int32) if isinstance(F, np.ndarray) else np.array(F, np.int32)
        arrays['target/C'] = np.asarray(cols, np.float32)
        target = dict(glb=((S.spec.get('hair') or {}).get('shape') or {}).get('glb'))
        tp = target_pieces(target['glb'], len(arrays['target/V']))
        if tp is not None:
            arrays['target/pieces'], target['piece_names'] = tp
    meta = dict(schema=SCHEMA, source='blender', created=time.strftime('%Y-%m-%dT%H:%M:%S'),
                spec={k: v for k, v in dict(S.spec).items() if k != '_dir'}, ref_measure=ref_measure, assembly=asm,
                landmarks=trace._plain(trace.landmarks(S)), materials=mrec,
                images={k: dict(shape=list(v.shape), dtype=str(v.dtype), rows='bottom-up') for k, v in images.items()},
                target=target, objects=recs)
    path = write(out, meta, arrays)
    trace.note('bundle', seconds=round(time.perf_counter() - t0, 2), arrays=len(arrays),
               bytes=os.path.getsize(os.path.join(out, ARRAYS)), objects=len(recs))
    return path


def assembly_variant(A):
    """the skin's `assembly` variant: the assembly's vertices, polygons and material per polygon (0 body, 1 head, 2 mouth
    cavity, 3 eye line), its lid keys per eye and both eyes summed, its mouth keys (sparse, float64)."""
    fl = [np.asarray(f) for f in A['faces']]
    G = dict(V=np.asarray(A['verts'], float), loopv=np.concatenate(fl).astype(np.int64),
             counts=np.array([len(f) for f in fl], np.int32), pmat=np.asarray(A['fmat']).astype(np.int16))
    keys = {}
    if A['eyes'][0].get('keys'):
        for name in A['eyes'][0]['keys']:
            both = np.zeros_like(G['V'])
            for E in A['eyes']:
                keys['eye_%s_%s' % (name, 'L' if E['side'] > 0 else 'R')] = _sparse(E['keys'][name][0])
                both = both + E['keys'][name][0]
            keys['eye_' + name] = _sparse(both)
        for sh, D in A['mouth']['keys'].items():
            keys['mouth_' + sh] = _sparse(D)
    G['keys'] = keys
    return G


def assembly_meta(A, spec):
    """what the checks read of an assembly (charkit.character.assemble's dict) as plain metadata: the head's length,
    centre, chin, top, mouth height and eye knobs; each eye's side, centre, lid chains and key names; the mouth's centre,
    lip chains and key names; the waist's and knee's heights; the base."""
    from .garments import bone_seg
    Hd = A['head']; H = Hd['H']; L = float(Hd['L'])
    return dict(L=L, centre=[float(x) for x in Hd['centre']], chin=float(H.chin), top=float(H.top),
                mouth_z=float(H.mouth_z), df=float(H.df), eye_knobs={k: float(v) for k, v in Hd['eye_knobs'].items()
                                                                       if isinstance(v, (int, float))},
                eye_z=float(Hd.get('eye_z', Hd['centre'][2] + Hd['eye_knobs']['z'] * L)),
                eyes=[dict(side=int(E['side']), c=[float(x) for x in E['c']], upper=[int(i) for i in E['eye']['upper']],
                           lower=[int(i) for i in E['eye']['lower']], margin=[int(i) for i in E['eye']['margin']],
                           keys=list(E.get('keys') or {})) for E in A['eyes']],
                mouth=dict(c=[float(x) for x in A['mouth']['c']], upper=[int(i) for i in A['mouth']['m']['upper']],
                           lower=[int(i) for i in A['mouth']['m']['lower']], keys=list(A['mouth'].get('keys') or {})),
                waist_z=float(bone_seg(A, 'spine')[0][2]), knee_z=float(bone_seg(A, 'leftLowerLeg')[0][2]),
                base=spec.get('base', 'makehuman'))


def bytes_to_float(px):
    """8-bit pixels as Blender's Image.pixels reads them: byte * (1 / 255) in float32 (not byte / 255, which differs in
    the last bit for half the byte values)."""
    return np.asarray(px).astype(np.float32) * (np.float32(1.0) / np.float32(255.0))


# ------------------------------------------------------------------------------------------------------ writing
def _plain(x):
    """JSON-safe metadata (numpy values as plain numbers, cache.TrackedDicts as dicts)."""
    if isinstance(x, dict):
        return {str(k): _plain(v) for k, v in dict.items(x)}
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    if isinstance(x, np.ndarray):
        return _plain(x.tolist())
    if isinstance(x, np.generic):
        return x.item()
    return x


def array_hash(a):
    a = np.ascontiguousarray(a)
    h = hashlib.sha1(('%s%s' % (a.dtype.str, a.shape)).encode())
    h.update(a.tobytes())
    return h.hexdigest()[:20]


def meta_hash(x):
    return hashlib.sha1(json.dumps(_plain(x), sort_keys=True).encode()).hexdigest()[:20]


def _savez(path, arrays, level=1):
    """an .npz (np.load reads it) with fast deflate: a third of np.savez_compressed's time at nearly its size."""
    import zipfile
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=level) as z:
        for k, a in arrays.items():
            with z.open(k + '.npy', 'w', force_zip64=True) as f:
                np.lib.format.write_array(f, np.asanyarray(a), allow_pickle=False)


def write(out, meta, arrays):
    """bundle.json and arrays.npz into `out`, with each array's hash and the content hash. -> bundle.json's path."""
    os.makedirs(out, exist_ok=True)
    meta = _plain(meta)
    hashes = {k: array_hash(v) for k, v in sorted(arrays.items())}
    meta['hashes'] = hashes
    meta['content'] = meta_hash([{k: v for k, v in meta.items() if k not in ('created', 'hashes', 'content')}, hashes])
    tmp = os.path.join(out, '.arrays.tmp.npz')
    _savez(tmp, arrays)
    os.replace(tmp, os.path.join(out, ARRAYS))
    with open(os.path.join(out, META), 'w') as f:
        json.dump(meta, f, indent=1)
    return os.path.join(out, META)


# ------------------------------------------------------------------------------------------------------ reading
class Reads:
    """what a measurement read of a bundle (the QA cache keys a part on it): array names and metadata paths."""

    def __init__(self):
        self.arrays, self.meta, self.files = set(), set(), set()


class Tracked(dict):
    """a metadata dict that records the keys read from it (two levels down) into the bundle's open Reads."""

    def __init__(self, d, B, path):
        super().__init__(d)
        self._B, self._path = B, path

    def _rec(self, k):
        if self._B._reads:
            p = self._path + (k,)
            for r in self._B._reads:
                r.meta.add(p)

    def __getitem__(self, k):
        self._rec(k)
        v = dict.__getitem__(self, k)
        if isinstance(v, dict) and len(self._path) < 1:
            return Tracked(v, self._B, self._path + (k,))
        return v

    def get(self, k, d=None):
        self._rec(k)
        if k not in self:
            return d
        return self[k]

    def __contains__(self, k):
        self._rec(k)
        return dict.__contains__(self, k)

    def items(self):
        for k in dict.keys(self):
            yield k, self[k]

    def values(self):
        for k in dict.keys(self):
            yield self[k]

    def __iter__(self):
        self._rec('\0*')
        return dict.__iter__(self)

    def keys(self):
        self._rec('\0*')
        return dict.keys(self)

    def copy(self):
        return {k: self[k] for k in dict.keys(self)}


class Bundle:
    """a bundle, read from its folder (load) or made in memory (Bundle(meta, arrays)): the metadata, the arrays by name,
    the objects (Obj). Reads are recorded while a `recording()` is open (charkit.qa3d's part cache keys on them)."""

    def __init__(self, meta, arrays, path=None):
        self._meta = dict(meta)
        self._arrays = arrays                       # a dict, or an open NpzFile (arrays load on first use)
        self._loaded = {}
        self.path = path
        self._reads = []
        self._objs = {r['name']: Obj(self, r) for r in self._meta.get('objects', [])}
        self._tri, self._memo = {}, {}

    # -------------------------------------------------------------------------------------------- reads
    def recording(self):
        import contextlib

        @contextlib.contextmanager
        def rec():
            r = Reads()
            self._reads.append(r)
            try:
                yield r
            finally:
                self._reads.remove(r)
        return rec()

    def memo(self, key, fn):
        """fn() made once per bundle (a measurement two parts share); a later call records the reads the first made into
        the recordings open now, so each part's cache key still holds them."""
        got = self._memo.get(key)
        if got is None:
            with self.recording() as r:
                got = self._memo[key] = (fn(), r)
        for rr in self._reads:
            rr.arrays |= got[1].arrays; rr.meta |= got[1].meta; rr.files |= got[1].files
        return got[0]

    def has(self, key):
        return key in (self._arrays.files if hasattr(self._arrays, 'files') else self._arrays)

    def array(self, key):
        for r in self._reads:
            r.arrays.add(key)
        if key not in self._loaded:
            self._loaded[key] = self._arrays[key]
        return self._loaded[key]

    def meta(self, key, default=None):
        """a metadata entry; a dict records the keys read from it, anything else is recorded whole."""
        v = self._meta.get(key, default)
        if isinstance(v, dict):
            return Tracked(v, self, (key,))
        for r in self._reads:
            r.meta.add((key,))
        return v

    @property
    def spec(self):
        return self.meta('spec') or {}

    @property
    def assembly(self):
        return self.meta('assembly')

    @property
    def materials(self):
        return self.meta('materials') or {}

    def hash_of(self, what):
        """the hash of an array name or a metadata path (a tuple), for keying a cache on what was read."""
        if isinstance(what, str):
            h = (self._meta.get('hashes') or {}).get(what)
            return h if h is not None else array_hash(self.array(what))
        v = self._meta
        for k in what:
            if k == '\0*':
                return meta_hash(sorted(v) if isinstance(v, dict) else None)
            v = v.get(k) if isinstance(v, dict) else None
        return meta_hash(v)

    def content(self):
        return self._meta.get('content') or meta_hash([{k: v for k, v in self._meta.items() if k != 'objects'},
                                                      {k: array_hash(self._arrays[k]) for k in sorted(self._arrays)}])

    # -------------------------------------------------------------------------------------------- objects
    def _rec_objects(self):
        for r in self._reads:
            r.meta.add(('objects',))

    def objects(self, groups=None, visible=True, parts=None, side=None):
        """the objects (their records: which there are is itself a read), by group, visibility, part and side."""
        self._rec_objects()
        return [o for o in self._objs.values() if (groups is None or o.group in groups) and (not visible or not o.hidden)
                and (parts is None or o.part in parts) and (side is None or o.side == side)]

    def obj(self, name):
        self._rec_objects()
        return self._objs[name]

    def skin(self):
        self._rec_objects()
        return next(o for o in self._objs.values() if o.group == 'skin')

    def part(self, part, side=None):
        self._rec_objects()
        return next((o for o in self._objs.values() if o.part == part and (side is None or o.side == side)), None)

    def image(self, name):
        """an image's pixels as floats, row 0 = top (a byte image as Blender reads it: bytes_to_float)."""
        return self.image_raw(name)[::-1]

    def image_raw(self, name):
        """an image as Blender keeps it: rows bottom-up, floats (qa3d.poly_colours samples it so)."""
        px = self.array('img/' + name)
        return bytes_to_float(px) if px.dtype == np.uint8 else px.astype(np.float32)

    def target(self):
        """the generated character aligned (V, triangles, per-vertex colours) or None."""
        if self._meta.get('target') is None or not self.has('target/V'):
            return None
        return self.array('target/V'), self.array('target/T'), self.array('target/C').astype(np.float64)

    def target_pieces(self):
        """the target's per-vertex outfit piece labels and their names ({k: piece id}; bundle.target_pieces) or None."""
        if not self.has('target/pieces'):
            return None
        return self.array('target/pieces'), {int(k): v for k, v in (self._meta['target'].get('piece_names') or {}).items()}

    def moved(self, d):
        """the same bundle rigidly moved by d (world): every object's geometry, the head's centre and eye centres, the
        target (the same scene on another pixel grid: the fit's jitter)."""
        d = np.asarray(d, float)
        arrays = {k: (self.array(k) + d if k.endswith('/V') else self.array(k))
                  for k in (self._arrays.files if hasattr(self._arrays, 'files') else self._arrays)}
        meta = json.loads(json.dumps(_plain({k: v for k, v in self._meta.items() if k != 'hashes'})))
        A = meta['assembly']
        A['centre'] = [c + x for c, x in zip(A['centre'], d)]
        for E in A.get('eyes', ()):
            E['c'] = [E['c'][0] + d[0], E['c'][1] + d[2]]
        if 'c' in A.get('mouth', {}):
            A['mouth']['c'] = [A['mouth']['c'][0] + d[0], A['mouth']['c'][1] + d[2]]
        for k in ('eye_z', 'waist_z', 'knee_z'):
            if k in A:
                A[k] += d[2]
        if 'raw_z' in A:
            A['raw_z'] = [z + d[2] for z in A['raw_z']]
        meta.pop('content', None)
        B = Bundle(meta, arrays, self.path)
        B.shift = d
        return B


class Obj:
    """one object of a bundle: its record (name, group, part, side, hidden, materials, outline) and its variants."""

    def __init__(self, B, rec):
        self.B, self.rec = B, rec
        for k in ('name', 'group', 'part', 'side', 'hidden', 'materials', 'outline'):
            setattr(self, k, rec.get(k))

    def __repr__(self):
        return '<Obj %s %s>' % (self.name, self.group)

    def has(self, variant):
        return variant in self.rec.get('variants', ())

    def a(self, variant, field):
        k = 'o/%s/%s/%s' % (self.name, variant, field)
        return self.B.array(k) if self.B.has(k) else None

    def polys(self, variant='eval'):
        """(loopv, starts, counts)."""
        cnt = self.a(variant, 'counts').astype(np.int64)
        return self.a(variant, 'loopv').astype(np.int64), np.concatenate([[0], np.cumsum(cnt)[:-1]]).astype(np.int64), cnt

    def tris(self, variant='eval'):
        """the fan triangulation (charkit.faceqa.triangles') -> (T (m, 3) vertex indices, poly (m,), Tl (m, 3) loops)."""
        key = (self.name, variant)
        if key not in self.B._tri:
            from .faceqa import triangle_loops
            loopv, starts, counts = self.polys(variant)
            Tl, poly = triangle_loops(starts, counts)
            self.B._tri[key] = (loopv[Tl], poly, Tl)
        return self.B._tri[key]

    def mesh(self, variant='eval'):
        """-> (V, T, material slot per triangle, polygon per triangle)."""
        T, poly, _ = self.tris(variant)
        return self.a(variant, 'V'), T, self.a(variant, 'pmat').astype(np.int64)[poly], poly

    def V(self, variant='eval'):
        return self.a(variant, 'V')

    def corners(self, variant, field):
        """a per-corner field (luv, lnor) per triangle corner -> (m, 3, k) or None."""
        f = self.a(variant, field)
        if f is None:
            return None
        return f[self.tris(variant)[2]]

    def puv(self, variant='eval'):
        """each polygon's mean UV (as trace.mesh_arrays computes it), NaN without UVs -> (npoly, 2)."""
        luv = self.a(variant, 'luv')
        loopv, starts, counts = self.polys(variant)
        if luv is None or not len(counts):
            return np.full((len(counts), 2), np.nan)
        return np.add.reduceat(luv.astype(np.float64), starts, axis=0) / counts[:, None]

    def keys(self, variant='base'):
        """{name: (idx, D)}: the shape keys' world offsets."""
        pre = 'o/%s/%s/keys/' % (self.name, variant)
        names = sorted({k[len(pre):].rsplit('/', 1)[0] for k in self.B._arrays_names() if k.startswith(pre)})
        return {n: (self.B.array(pre + n + '/idx').astype(np.int64), self.B.array(pre + n + '/d')) for n in names}

    def material(self, slot):
        nm = self.materials[slot] if 0 <= slot < len(self.materials) else None
        return nm, (self.B.materials.get(nm) if nm else None)


def _names(self):
    return list(self._arrays.files) if hasattr(self._arrays, 'files') else list(self._arrays)


Bundle._arrays_names = _names


class Builder:
    """a bundle made in memory by an evaluator (charkit.faceeval; the body evaluator likewise): objects, materials,
    images, the target and the metadata, in the schema export() writes. Geometry is rounded to float32 values, as
    Blender keeps it (its evaluated meshes are float32 cast up), unless exact=True.

        b = Builder(spec, assembly, ref_measure)
        b.material('skin', lit=(1, .9, .86))
        b.add('clawd_skin', 'skin', {'eval': dict(V=V, faces=quads, pmat=fm)})
        B = b.build()
    """

    def __init__(self, spec, assembly, ref_measure=None, source='evaluator', exact=False):
        self.meta = dict(schema=SCHEMA, source=source, spec=spec, assembly=assembly, ref_measure=ref_measure,
                         materials={}, images={}, target=None, objects=[])
        self.arrays = {}
        self.exact = exact

    def _v(self, V):
        V = np.asarray(V, float)
        return V if self.exact else V.astype(np.float32).astype(np.float64)

    def material(self, name, lit=None, shade=None, deep=None, image=None, cull=False, kind='flat', shading=None):
        """a material's record (material_record's shape): its flat tones (sRGB), texture, culling and shading."""
        t = lambda c: None if c is None else [float(x) for x in c]
        if kind == 'flat' and shading is None and lit is not None:
            shading = dict(color=[float(x) for x in np.where(np.asarray(lit, float) <= 0.04045, np.asarray(lit, float) / 12.92,
                                                             ((np.asarray(lit, float) + 0.055) / 1.055) ** 2.4)], strength=1.0)
        self.meta['materials'][name] = dict(lit=t(lit), shade=t(shade if shade is not None else lit),
                                            deep=t(deep if deep is not None else lit), image=image, cull=bool(cull),
                                            kind=kind, shading=shading)

    def image(self, name, rgba_top_down):
        """an image from floats (row 0 = top) stored as Blender stores a byte image: bytes, rows bottom-up."""
        px = np.floor(np.clip(np.asarray(rgba_top_down, float), 0, 1) * 255 + 0.5).astype(np.uint8)[::-1]
        self.arrays['img/' + name] = np.ascontiguousarray(px)
        self.meta['images'][name] = dict(shape=list(px.shape), dtype='uint8', rows='bottom-up')

    def add(self, name, group, variants, part=None, side=None, materials=(), outline=None, hidden=False):
        """an object: variants {name: dict(V, faces (polygons: a list of index tuples or an (n, k) array; or loopv and
        counts), pmat?, luv? (per corner, polygon order), uv? (per vertex: its corners get it), lnor?, shrink?, keys?
        {name: dense (N, 3) or (idx, D)}, exact? (keep V in float64))}."""
        rec = dict(name=name, group=group, part=part, side=side, hidden=bool(hidden), materials=list(materials),
                   outline=outline, variants=[])
        for vn, G in variants.items():
            if 'faces' not in G:                              # (polygons given as loopv and counts)
                G = dict(G, faces=None)
            faces = G['faces']
            if faces is None:
                loopv, counts = np.asarray(G['loopv']), np.asarray(G['counts'])
            elif isinstance(faces, np.ndarray) and faces.ndim == 2:
                loopv = faces.ravel(); counts = np.full(len(faces), faces.shape[1])
            else:
                counts = np.array([len(f) for f in faces]); loopv = np.array([i for f in faces for i in f])
            pre = 'o/%s/%s/' % (name, vn)
            self.arrays[pre + 'V'] = np.asarray(G['V'], float) if G.get('exact') else self._v(G['V'])
            self.arrays[pre + 'loopv'] = loopv.astype(np.int32)
            self.arrays[pre + 'counts'] = counts.astype(np.int32)
            self.arrays[pre + 'pmat'] = np.asarray(G.get('pmat', np.zeros(len(counts))), np.int16)
            if G.get('uv') is not None:
                self.arrays[pre + 'luv'] = np.asarray(G['uv'], np.float32)[loopv]
            for k in ('luv', 'lnor', 'shrink', 'parent'):
                if G.get(k) is not None:
                    self.arrays[pre + k] = np.asarray(G[k])
            for kn, D in (G.get('keys') or {}).items():
                idx, d = D if isinstance(D, tuple) else _sparse(D)
                self.arrays[pre + 'keys/%s/idx' % kn] = np.asarray(idx, np.int32)
                self.arrays[pre + 'keys/%s/d' % kn] = np.asarray(d, float)
            rec['variants'].append(vn)
        self.meta['objects'].append(rec)
        return rec

    def target(self, V, T, C, glb=None):
        self.arrays['target/V'] = np.asarray(V, float)
        self.arrays['target/T'] = np.asarray(T, np.int32)
        self.arrays['target/C'] = np.asarray(C, np.float32)
        self.meta['target'] = dict(glb=glb)
        tp = target_pieces(glb, len(V))
        if tp is not None:
            self.arrays['target/pieces'], self.meta['target']['piece_names'] = tp

    def build(self):
        return Bundle(_plain(self.meta), dict(self.arrays))


def target_pieces(glb, n):
    """the outfit piece of each vertex of a generated shape, when its sidecar (GLB.json, charkit.geom.hull's) names a
    per-vertex piece file for it: -> (labels (n,) int16: k for the sidecar's piece_names[k], 1000 + a bodyqa class where
    no piece claims it, 0 none; {k: piece id}) or None. None too when the file's length isn't the shape's (it was made
    for another shape)."""
    import json as _json
    if not glb:
        return None
    p = glb if os.path.isabs(glb) else os.path.join(ROOT, glb)
    side = p + '.json'
    if not os.path.exists(side):
        return None
    J = _json.load(open(side))
    if not J.get('pieces'):
        return None
    lp = os.path.join(os.path.dirname(p), J['pieces'])
    if not os.path.exists(lp):
        return None
    lab = np.load(lp)
    if len(lab) != n:
        return None
    return lab.astype(np.int16), {str(k): v for k, v in (J.get('piece_names') or {}).items()}


def load(path):
    """a bundle folder (or its bundle.json) -> Bundle."""
    if path.endswith('.json'):
        path = os.path.dirname(path)
    meta = json.load(open(os.path.join(path, META)))
    if meta.get('schema') != SCHEMA:
        raise ValueError('%s: schema %s, not %s' % (path, meta.get('schema'), SCHEMA))
    return Bundle(meta, np.load(os.path.join(path, ARRAYS)), path=path)
