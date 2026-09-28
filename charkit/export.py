"""charkit export: a character built in Blender to VRM 1.0 (and a plain glTF fallback), for three.js + three-vrm
(docs/CHARKIT.md §2 "export and QA", docs/PIPELINE_3D.md §1: one character, two runtimes).

    blender -b --factory-startup --python charkit/export.py -- clawd [--out charkit/out/export]   # build Clawd, export both, validate
    blender -b --factory-startup --python charkit/export.py -- --check charkit/out/export/clawd.vrm  # validate (and re-import) a VRM
    python charkit/export.py --clip projects/clawd3d/refs/mocap/hook_v1.clip.npz OUT.motion.json   # a canonical clip for the browser

The VRM Add-on for Blender (saturday06, MIT OR GPL-3.0-or-later; we take it under MIT) is pinned below, downloaded once into
the gitignored vendor/blender_addons/ and registered from there: always run Blender with --factory-startup, and this module
never saves preferences, so the user's global Blender config is never touched.

What export_vrm writes (export_gltf writes the same meshes, unlit, with no VRM extensions):
  meshes       each mesh as Blender renders it: modifiers applied (subdivision capped at level 1 for the triangle budget,
               the hair's transferred custom normals baked in), the inverted-hull outline cut away (kit.add_outline's
               SOLIDIFY moves the visible surface in by the line width; the hull's faces are dropped), closed parts that
               are inside out rewound (Blender draws the cel materials two-sided; MToon culls). Skinned meshes stay skinned,
               bone-parented props stay bone-parented.
  humanoid     the armature's bones already carry VRM 1.0 humanoid names (hips, spine, ..., leftIndexDistal); each is
               assigned to itself. The add-on's autoPose turns the A-pose rest into the T-pose VRM 1.0 requires at export
               (the mesh keeps its A-pose bind; the joints' rest nodes are the T-pose).
  expressions  drawn face decals (one object per state, swapped by visibility in Blender) become one mesh per state, named
               '<group>_<state>' and trimmed to where its drawing has ink. The group's default state sits on the face with
               a 'hide' shape key; every other state sits sunk inside the head (the head hides it) with a 'show' key. An
               expression binds 'show' on its state and 'hide' on the default, isBinary (a drawing is never half-shown);
               emotions block the blink (overrideBlink), as the VRM presets expect.
  springs      helper bones (hairSpring, skirtSpring) become one-joint VRM springs, with an added '<bone>_end' tail bone;
               stiffness and drag from motion.bake's damped spring (springs_from: approximate, VRM springs are verlet).
  materials    the emission cel materials become MToon: lit and shade colours, the step's threshold and softness as
               shading shift and toony, two-sided; the outline as MToon's world-space outline (width and colour from the
               SOLIDIFY 'outline' modifier; one material copy per outline, so hands and body keep their own line); decals
               as unshaded alpha-blended MToon; the face's blush baked into its lit and shade textures.
What doesn't map (MToon and VRM have no slot for it; see NOT_MAPPED): the third (deep) shadow tone, the SDF face shadow,
the hair's angel-ring highlight, the eyes' gaze (an iris UV shift inside a layered shader), the lit-side rim. Expressions
with no drawing: sad, blinkRight (one wink is drawn), lookUp/Down/Left/Right.
"""
import hashlib, json, math, os, re, shutil, struct, sys, tempfile, urllib.request, zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDONS = os.path.join(REPO, 'vendor', 'blender_addons')
VRM_ADDON = {  # extensions.blender.org's build of github.com/saturday06/VRM-Addon-for-Blender (supports Blender 4.2 .. <5.3)
    'module': 'io_scene_vrm', 'version': '4.7.2',
    'url': 'https://extensions.blender.org/download/sha256:e85588660bfbb4099910a86803fa87dc8348e65541a4ccdcaf40c538f60027dc/add-on-vrm-v4.7.2.zip',
    'sha256': 'e85588660bfbb4099910a86803fa87dc8348e65541a4ccdcaf40c538f60027dc',
    'licence_url': 'https://raw.githubusercontent.com/saturday06/VRM-Addon-for-Blender/main/LICENSE_(OPTION1)_MIT.txt',
}
NOT_MAPPED = {
    'deep shadow tone': 'MToon has two tones (lit, shade); toon3\'s third, deep core tone is dropped',
    'SDF face shadow': 'MToon has no threshold-map shading; the face exports always lit (shading shift +1, the usual VRoid '
                       'choice): an N.L step put a shade band under the jaw that the SDF face never shows',
    'hair angel ring': 'the lit-side highlight band (a node trick on the lock UVs) has no MToon slot; matcap could fake it',
    'eye gaze': 'the iris moves inside a layered eye shader (white, iris, shine, lines); VRM lookAt would need the iris as '
                'its own texture-transform layer. The eyes export as the flat composite (eyes_open.png)',
    'rim': 'our rim is a hard band on the lit side only, from |N.V|; MToon\'s parametric rim is 1 - N.V clamped, so '
           'every surface whose normal turns from the camera (the hair\'s smoothed volume normals, the jaw) gets the full '
           'rim colour: it read as pale patches, so export_vrm leaves the rim off (mtoon(rim=True) turns it back on)',
}


# ---------------------------------------------------------------- the add-on (downloaded once, registered per run)
def install_addon(force=False):
    """Download, verify (sha256) and unpack the pinned VRM add-on into vendor/blender_addons/io_scene_vrm."""
    dest = os.path.join(ADDONS, VRM_ADDON['module'])
    stamp = os.path.join(dest, '.charkit_version')
    if not force and os.path.exists(stamp) and open(stamp).read().strip() == VRM_ADDON['version']:
        return dest
    os.makedirs(ADDONS, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        z = os.path.join(tmp, 'vrm.zip')
        req = urllib.request.Request(VRM_ADDON['url'], headers={'User-Agent': 'Blender/5.2 (charkit)'})   # the site 403s urllib's
        with urllib.request.urlopen(req) as r, open(z, 'wb') as f:
            f.write(r.read())
        digest = hashlib.sha256(open(z, 'rb').read()).hexdigest()
        if digest != VRM_ADDON['sha256']:
            raise RuntimeError(f'VRM add-on checksum mismatch: {digest}')
        shutil.rmtree(dest, ignore_errors=True)
        zipfile.ZipFile(z).extractall(dest)
    try:
        with urllib.request.urlopen(VRM_ADDON['licence_url']) as r:
            open(os.path.join(dest, 'LICENSE_MIT.txt'), 'wb').write(r.read())
    except Exception as e:                                     # the zip ships no licence file; keep going without it
        print('[export] could not fetch the add-on licence text:', e)
    open(stamp, 'w').write(VRM_ADDON['version'])
    return dest


def enable_addon():
    """Register the vendored add-on in this Blender session only (preferences are never saved)."""
    import bpy, addon_utils
    install_addon()
    bpy.context.preferences.use_preferences_save = False
    if ADDONS not in sys.path:
        sys.path.insert(0, ADDONS)
    mod = VRM_ADDON['module']
    if mod not in bpy.context.preferences.addons:
        addon_utils.enable(mod, default_set=True, persistent=False, handle_error=None)
    if 'vrm' not in dir(bpy.ops.export_scene):
        raise RuntimeError('VRM add-on did not register')
    return sys.modules[mod]


# ---------------------------------------------------------------- reading our cel materials
def _lin_to_srgb(c):
    return tuple(x ** (1 / 2.2) for x in c[:3])


def material_info(m):
    """Parse one of the build's emission materials (kit.toon/toon3/flat/decal/eye_material, head.face_material,
    hair.hair_material) -> {'kind', 'lit', 'shade', 'deep', 'thresh', 'soft', 'rim', 'rim_amt', 'image', 'alpha'}.
    Colours are linear (as stored in the node sockets)."""
    nt = m.node_tree
    info = {'kind': 'flat', 'lit': (0.8, 0.8, 0.8), 'shade': None, 'deep': None, 'thresh': 0.5, 'soft': 0.012,
            'rim': None, 'rim_amt': 0.0, 'image': None, 'alpha': False, 'name': m.name}
    if not nt:
        return info
    N = nt.nodes
    tex = [n for n in N if n.type == 'TEX_IMAGE' and n.image]
    if 'gaze' in N:                                            # the layered eye: export the flat composite
        lines = next((n.image for n in tex if n.image.filepath.endswith('_lines.png')), tex[0].image)
        path = bpy_abspath(lines.filepath).replace('_lines.png', '.png')
        info.update(kind='decal', image=path, alpha=True, lit=(1, 1, 1))
        return info
    if tex and 'ldir' not in N and 'ramp' not in N:            # a decal
        info.update(kind='decal', image=bpy_abspath(tex[0].image.filepath), alpha=True, lit=(1, 1, 1))
        return info
    mixes = [n for n in N if n.type == 'MIX' and getattr(n, 'data_type', '') == 'RGBA']
    if 'ldir' in N and 'ramp' not in N and any(n.bl_idname == 'ShaderNodeVectorTransform' for n in N):   # the SDF face
        col = next(n for n in mixes if not n.inputs['A'].is_linked and not n.inputs['B'].is_linked and n.blend_type == 'MIX')
        blush = next((n.image for n in tex if 'blush' in n.image.filepath), None)
        info.update(kind='face', lit=tuple(col.inputs['A'].default_value[:3]), shade=tuple(col.inputs['B'].default_value[:3]),
                    thresh=0.0, soft=0.02, image=bpy_abspath(blush.filepath) if blush else None)
        rim = next((n for n in mixes if n.blend_type == 'SCREEN'), None)
        if rim:
            info.update(rim=tuple(rim.inputs['B'].default_value[:3]), rim_amt=0.18)
        return info
    if 'ramp' in N:                                            # toon / toon3 (+ hair's ring on top)
        flat_mixes = [n for n in mixes if n.blend_type == 'MIX' and not n.inputs['B'].is_linked]
        m1 = next((n for n in flat_mixes if not n.inputs['A'].is_linked), None)          # toon3: deep | shade; toon: shade | lit
        m2 = next((n for n in flat_mixes if n.inputs['A'].is_linked and n is not m1 and
                   n.inputs['A'].links[0].from_node == m1), None)                        # toon3: (deep|shade) | lit
        if m2:
            info.update(kind='toon3', deep=tuple(m1.inputs['A'].default_value[:3]), shade=tuple(m1.inputs['B'].default_value[:3]),
                        lit=tuple(m2.inputs['B'].default_value[:3]))
        elif m1:
            info.update(kind='toon', shade=tuple(m1.inputs['A'].default_value[:3]), lit=tuple(m1.inputs['B'].default_value[:3]))
        e0, e1 = N['ramp'].color_ramp.elements[0].position, N['ramp'].color_ramp.elements[-1].position
        info.update(thresh=(e0 + e1) / 2, soft=max(1e-3, (e1 - e0) / 2))
        rim = next((n for n in mixes if n.blend_type == 'SCREEN'), None)
        if rim:
            info['rim'] = tuple(rim.inputs['B'].default_value[:3])
            amt = N.get('rim_amt')
            if amt:
                info['rim_amt'] = float(amt.inputs[1].default_value)
            else:                                              # kit.toon: MULTIPLY node feeding the rim factor
                mul = [n for n in N if n.type == 'MATH' and n.operation == 'MULTIPLY' and not n.inputs[1].is_linked]
                info['rim_amt'] = float(mul[0].inputs[1].default_value) if mul else 0.2
        info['ring'] = 'hair' in m.name and any(n.type == 'UVMAP' for n in N)
        return info
    em = next((n for n in N if n.type == 'EMISSION'), None)
    if em:
        info['lit'] = tuple(em.inputs['Color'].default_value[:3])
    return info


def bpy_abspath(p):
    import bpy
    return os.path.normpath(bpy.path.abspath(p))


def outline_of(ob):
    """(width m, linear colour) of the inverted-hull outline (kit.add_outline's SOLIDIFY), or None."""
    for md in ob.modifiers:
        if md.type == 'SOLIDIFY' and md.use_flip_normals:
            mats = ob.data.materials
            m = mats[md.material_offset] if 0 <= md.material_offset < len(mats) else None
            col = (0.05, 0.03, 0.03)
            if m and m.node_tree:
                em = next((n for n in m.node_tree.nodes if n.type == 'EMISSION'), None)
                if em:
                    col = tuple(em.inputs['Color'].default_value[:3])
            return abs(md.thickness), col, (m.name if m else None)
    return None


# ---------------------------------------------------------------- the export rig: baked copies of the character
class ExportRig:
    """A disposable copy of the character for one export: the armature (+ '<spring>_end' tail bones), every mesh with its
    modifiers applied except the armature and the outline hull (subdivision, custom-normal transfer baked in), material
    copies, and the decal groups merged into shape-keyed meshes. The originals are renamed out of the way while it lives
    (glTF node and mesh names come from object names) and restored on exit.
        with ExportRig(arm, meshes, decals, defaults, springs) as R: R.arm, R.meshes, R.groups, R.minfo, R.mat_outline"""

    SUFFIX = '__src'

    def __init__(self, arm, meshes, decals=None, defaults=None, springs=(), sink=0.5, trim=True, subsurf=1):
        self.src_arm, self.src_meshes = arm, [m for m in meshes if m.type == 'MESH']
        self.decals, self.defaults = decals or {}, defaults or {}
        self.springs, self.sink, self.trim, self.subsurf = list(springs), sink, trim, subsurf

    def __enter__(self):
        import bpy
        self.renamed = []
        self.created = []
        self.coll = bpy.data.collections.new('charkit_export')
        bpy.context.scene.collection.children.link(self.coll)
        for ob in bpy.context.scene.objects:
            ob.select_set(False)
        self.arm = self._copy_armature()
        self.minfo, self.mat_map, self.mat_outline, self.variants, self.src_info = {}, {}, {}, {}, {}
        self.flipped = {}
        self.meshes = [self._bake(ob) for ob in self.src_meshes]
        self.groups = {g: self._decal_group(g, states) for g, states in self.decals.items()}
        bpy.context.view_layer.update()
        return self

    def __exit__(self, *exc):
        import bpy
        datas = []
        for ob in self.created:
            try:
                datas.append(ob.data)
                bpy.data.objects.remove(ob, do_unlink=True)
            except ReferenceError:
                pass
        for d in datas:
            try:
                if d.users == 0:
                    (bpy.data.meshes if isinstance(d, bpy.types.Mesh) else bpy.data.armatures).remove(d)
            except ReferenceError:
                pass
        bpy.data.collections.remove(self.coll)
        for m in self.mat_map.values():
            try:
                bpy.data.materials.remove(m)
            except ReferenceError:
                pass
        for idb, name in reversed(self.renamed):
            idb.name = name
        return False

    # -- helpers
    def _rename(self, idb):
        name = idb.name
        idb.name = name + self.SUFFIX
        self.renamed.append((idb, name))
        return name

    def _link(self, ob):
        self.coll.objects.link(ob)
        self.created.append(ob)
        return ob

    def _copy_armature(self):
        import bpy
        src = self.src_arm
        name, dname = self._rename(src), self._rename(src.data)
        arm = self._link(bpy.data.objects.new(name, src.data.copy()))
        arm.data.name = dname
        arm.matrix_world = src.matrix_world
        arm.hide_viewport = False
        bpy.context.view_layer.update()                        # the pose exists once the depsgraph has seen the object
        for pb in arm.pose.bones:
            pb.rotation_mode = 'QUATERNION'
            pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0); pb.scale = (1, 1, 1)
        if self.springs:                                        # a tail bone per one-bone spring, so the chain has a tip
            bpy.context.view_layer.objects.active = arm
            arm.select_set(True)
            bpy.ops.object.mode_set(mode='EDIT')
            eb = arm.data.edit_bones
            for b in self.springs:
                src_b = eb[b]
                e = eb.new(b + '_end')
                d = src_b.tail - src_b.head
                e.head = src_b.tail
                e.tail = src_b.tail + d.normalized() * 0.02
                e.roll = src_b.roll
                e.parent = src_b
                e.use_deform = False
            bpy.ops.object.mode_set(mode='OBJECT')
            arm.select_set(False)
        return arm

    def _material(self, m, outline=None):
        """A copy of material m for this export; one copy per outline (width, colour), since MToon's outline is per
        material (the body's skin and the hands' skin carry different lines)."""
        if m in self.src_info:                                 # seen: m is the original (already renamed away)
            base, info = self.src_info[m]
        else:
            base, info = m.name, material_info(m)
            self._rename(m)
            self.src_info[m] = (base, info)
        key = (base, outline)
        if key in self.variants:
            return self.mat_map[self.variants[key]]
        n = sum(1 for k in self.variants if k[0] == base)
        name = base if n == 0 else f'{base}_v{n + 1}'
        c = m.copy()
        c.name = name
        self.variants[key] = name
        self.mat_map[name] = c
        self.minfo[name] = dict(info)
        self.mat_outline[name] = outline
        return c

    def _bake(self, ob):
        """-> a new object: the evaluated mesh without its armature deform and outline hull, parented like the source.
        The hull is evaluated and then cut away, not switched off: kit.add_outline's SOLIDIFY (offset 1, negative
        thickness) moves the visible surface inward by the line width and leaves the hull where the surface was, so the
        surface Blender renders (and the face decals were cut against) is the evaluated one minus the hull's faces."""
        import bpy, bmesh
        ol = outline_of(ob)
        saved, levels = [], []
        for md in ob.modifiers:
            if md.type == 'ARMATURE':
                saved.append((md, md.show_viewport)); md.show_viewport = False
            if md.type == 'SUBSURF' and md.levels > self.subsurf:     # a triangle budget: cap subdivision
                levels.append((md, md.levels)); md.levels = self.subsurf
        was_hidden = ob.hide_viewport
        ob.hide_viewport = False
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        for md, s in saved:
            md.show_viewport = s
        for md, lv in levels:
            md.levels = lv
        ob.hide_viewport = was_hidden
        # cut the hull (its faces carry the outline material, kit.add_outline's last slot) and drop that slot
        if ol and ol[2]:
            slot = next((i for i, m in enumerate(me.materials) if m and m.name == ol[2]), None)
            if slot is not None:
                bm = bmesh.new(); bm.from_mesh(me)
                bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index == slot], context='FACES')
                bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
                bm.to_mesh(me); bm.free()
                if slot == len(me.materials) - 1:
                    me.materials.pop(index=slot)
        if not me.has_custom_normals:
            self.flipped[ob.name] = self._orient_closed_parts(me)
        for i, m in enumerate(me.materials):
            if m:
                me.materials[i] = self._material(m, tuple(ol[:2]) if ol else None)
        name = self._rename(ob)
        self._claim(me, name)
        new = self._link(bpy.data.objects.new(name, me))
        for vg in ob.vertex_groups:                           # names live on the object for the weights new_from_object kept
            if vg.name not in new.vertex_groups:
                new.vertex_groups.new(name=vg.name)
        self._parent_like(new, ob)
        return new

    @staticmethod
    def _orient_closed_parts(me):
        """Wind every closed (manifold) loose part outward: Blender draws our cel materials two-sided, so an inside-out
        part (kit.lock's ribbon tubes) looks fine there, but MToon culls it and pushes its outline inward. -> parts fixed."""
        import bmesh
        bm = bmesh.new(); bm.from_mesh(me)
        seen, fixed = set(), 0
        for f0 in bm.faces:
            if f0 in seen:
                continue
            part, stack = [], [f0]; seen.add(f0)
            while stack:
                f = stack.pop(); part.append(f)
                for e in f.edges:
                    for g in e.link_faces:
                        if g not in seen:
                            seen.add(g); stack.append(g)
            if not all(len(e.link_faces) == 2 for f in part for e in f.edges):
                continue
            before = [f.normal.copy() for f in part]
            bmesh.ops.recalc_face_normals(bm, faces=part)
            if any(f.normal.dot(n) < 0 for f, n in zip(part, before)):
                fixed += 1
        if fixed:
            bm.to_mesh(me)
        bm.free()
        return fixed

    def _parent_like(self, new, ob):
        new.parent = self.arm if ob.parent == self.src_arm else ob.parent
        new.parent_type = ob.parent_type
        if ob.parent_type == 'BONE':
            new.parent_bone = ob.parent_bone
        new.matrix_world = ob.matrix_world
        if any(md.type == 'ARMATURE' for md in ob.modifiers):
            md = new.modifiers.new('Armature', 'ARMATURE')
            md.object = self.arm

    def _decal_group(self, group, states):
        """A decal group ({state: object}: patches cut from the same head surface, one drawing each) -> one object per
        state, trimmed to where its drawing has ink. The default state sits on the surface with a 'hide' shape key; every
        other state sits sunk inside the head (toward the middle of its bone, by self.sink) with a 'show' key."""
        import bpy, bmesh
        import numpy as np
        default = self.defaults.get(group) or next(iter(states))
        order = [default] + [s for s in states if s != default]
        out = {}
        for s in order:
            src = states[s]
            mat = self._material(src.data.materials[0])
            keep = self._ink_faces(src, self.minfo[mat.name]['image']) if self.trim else None
            b = self.arm.data.bones[src.parent_bone]
            c = np.array(self.arm.matrix_world @ ((b.head_local + b.tail_local) / 2))
            bm = bmesh.new(); bm.from_mesh(src.data)
            bmesh.ops.transform(bm, matrix=src.matrix_world, verts=bm.verts)       # armature space (bone-parented shells)
            bm.faces.ensure_lookup_table()
            # drop faces without ink, and faces behind the head's middle (faces.py cuts the shells from the head WITH its
            # flipped outline hull, whose far side also faces front: invisible in Blender, stray triangles in an export)
            drop = [f for f in bm.faces if (keep is not None and not keep[f.index]) or f.calc_center_median().y > c[1]]
            bmesh.ops.delete(bm, geom=drop, context='FACES')
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
            name = f'{group}_{s}'
            self._rename(src)
            me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
            self._claim(me, name)
            me.materials.append(mat)
            for p in me.polygons:
                p.use_smooth = True
            ob = self._link(bpy.data.objects.new(name, me))
            co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
            sunk = c + (co - c) * self.sink
            on = s == default
            me.vertices.foreach_set('co', (co if on else sunk).ravel())
            ob.shape_key_add(name='Basis', from_mix=False)
            k = ob.shape_key_add(name='hide' if on else 'show', from_mix=False)
            k.data.foreach_set('co', (sunk if on else co).ravel())
            vg = ob.vertex_groups.new(name=b.name)                   # skinned to the bone, weight 1
            vg.add(list(range(len(me.vertices))), 1.0, 'REPLACE')
            ob.parent = self.arm
            md = ob.modifiers.new('Armature', 'ARMATURE'); md.object = self.arm
            out[s] = ob
        return {'objects': out, 'default': default, 'states': order,
                'verts': {s: len(o.data.vertices) for s, o in out.items()}}

    @staticmethod
    def _ink_faces(ob, image_path, block=8, grow=1):
        """-> per face, whether the drawing has ink (alpha > 2/255) under its UV box (a block-max mask, grown a block)."""
        import bpy
        import numpy as np
        img = bpy.data.images.load(image_path, check_existing=True)
        w, h = img.size
        px = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(px)
        a = px.reshape(h, w, 4)[..., 3] > 2 / 255
        B = block
        m = a[:h // B * B, :w // B * B].reshape(h // B, B, w // B, B).any(axis=(1, 3))
        for _ in range(grow):
            g = m.copy()
            g[1:] |= m[:-1]; g[:-1] |= m[1:]; g[:, 1:] |= m[:, :-1]; g[:, :-1] |= m[:, 1:]
            m = g
        gh, gw = m.shape
        uv = ob.data.uv_layers.active.data
        keep = []
        for p in ob.data.polygons:
            us = [uv[li].uv for li in p.loop_indices]
            u0, u1 = min(x[0] for x in us), max(x[0] for x in us)
            v0, v1 = min(x[1] for x in us), max(x[1] for x in us)
            if u1 < 0 or v1 < 0 or u0 > 1 or v0 > 1:
                keep.append(False); continue
            i0, i1 = int(max(0, v0) * gh), min(gh - 1, int(min(1, v1) * gh))
            j0, j1 = int(max(0, u0) * gw), min(gw - 1, int(min(1, u1) * gw))
            keep.append(bool(m[i0:i1 + 1, j0:j1 + 1].any()))
        return keep

    def _claim(self, idb, name):
        """give idb this exact name, renaming whatever holds it out of the way (restored on exit)."""
        import bpy
        idb.name = name
        if idb.name != name:
            coll = bpy.data.meshes if isinstance(idb, bpy.types.Mesh) else bpy.data.materials
            self._rename(coll[name])
            idb.name = name


# ---------------------------------------------------------------- materials for each target
def mtoon(m, info, outline=None, rim=False):
    """Turn a (copied) material into an MToon 1.0 approximation of our cel material."""
    import bpy
    ext = m.vrm_addon_extension.mtoon1
    ext.enabled = True
    mt = ext.extensions.vrmc_materials_mtoon
    lit = info['lit']; shade = info['shade'] or lit          # toon3's deep tone is dropped (NOT_MAPPED)
    ext.pbr_metallic_roughness.base_color_factor = (*lit, 1.0)
    mt.shade_color_factor = shade
    # our step: half-lambert h = 0.5 + 0.5 N.L crosses thresh over +-soft  ->  MToon: N.L + shift through a window of
    # half-width (1 - toony) centred on 0
    t, s = info['thresh'], info['soft']
    mt.shading_shift_factor = max(-1.0, min(1.0, 1 - 2 * t))
    mt.shading_toony_factor = max(0.0, min(1.0, 1 - 2 * s))
    mt.gi_equalization_factor = 0.9
    if info['kind'] == 'decal':
        img = bpy.data.images.load(info['image'], check_existing=True)
        ext.pbr_metallic_roughness.base_color_texture.index.source = img
        mt.shade_multiply_texture.index.source = img
        mt.shade_color_factor = (1, 1, 1)
        mt.shading_toony_factor = 1.0
        ext.alpha_mode = 'BLEND'
        mt.transparent_with_z_write = False
        mt.render_queue_offset_number = 1
        mt.gi_equalization_factor = 1.0
    elif info['kind'] == 'face' and info.get('image'):          # the blush, multiplied into lit and shade textures
        lit_img, shade_img = _blush_textures(m.name, info['image'], lit, shade)
        pbr = ext.pbr_metallic_roughness
        pbr.base_color_factor = (1, 1, 1, 1)
        pbr.base_color_texture.index.source = lit_img
        mt.shade_color_factor = (1, 1, 1)
        mt.shade_multiply_texture.index.source = shade_img
        for tex in (pbr.base_color_texture, mt.shade_multiply_texture):
            tex.index.sampler.wrap_s = tex.index.sampler.wrap_t = 'CLAMP_TO_EDGE'   # the face window's edge is plain skin
    if rim and info.get('rim') and info.get('rim_amt'):
        mt.parametric_rim_color_factor = tuple(c * info['rim_amt'] for c in info['rim'])
        mt.parametric_rim_fresnel_power_factor = 10.0
        mt.parametric_rim_lift_factor = 0.0
        mt.rim_lighting_mix_factor = 1.0
    else:                                                       # off by default: see NOT_MAPPED['rim']
        mt.parametric_rim_color_factor = (0, 0, 0)
    if outline:
        width, col = outline
        mt.outline_width_mode = 'worldCoordinates'
        mt.outline_width_factor = width
        mt.outline_color_factor = col
        mt.outline_lighting_mix_factor = 0.0
    else:
        mt.outline_width_mode = 'none'
    ext.double_sided = info['kind'] != 'decal'                  # Blender draws the cel materials two-sided


def _blush_textures(name, blush_path, lit, shade):
    """head.face_material multiplies the blush (colour, alpha) over the face: bake that over the lit and the shade tone
    into two sRGB textures in the face UV window (saved under the system temp dir; the exporter embeds them)."""
    import bpy
    import numpy as np
    src = bpy.data.images.load(blush_path, check_existing=True)
    w, h = src.size
    px = np.empty(w * h * 4, np.float32); src.pixels.foreach_get(px); px = px.reshape(h, w, 4)
    to_lin = lambda c: np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    to_srgb = lambda c: np.where(c <= 0.0031308, c * 12.92, 1.055 * np.clip(c, 0, None) ** (1 / 2.4) - 0.055)
    blush, a = to_lin(px[..., :3]), px[..., 3:4].copy()
    a[:2] = a[-2:] = 0; a[:, :2] = a[:, -2:] = 0             # a clean border: the sampler clamps it across the whole head
    out = []
    dirp = os.path.join(tempfile.gettempdir(), 'charkit_bake'); os.makedirs(dirp, exist_ok=True)
    for tag, base in (('lit', lit), ('shade', shade)):
        col = np.array(base, np.float32) * (1 - a + a * blush)
        rgba = np.concatenate([to_srgb(col), np.ones_like(a)], -1).astype(np.float32)
        img = bpy.data.images.new(f'{name}_{tag}', w, h, alpha=False)
        img.pixels.foreach_set(rgba.ravel())
        img.filepath_raw = os.path.join(dirp, f'{name}_{tag}.png'); img.file_format = 'PNG'
        img.save()
        out.append(img)
    return out


def unlit(m, info):
    """A KHR_materials_unlit material for the plain glTF: the lit tone (or the decal texture with its alpha)."""
    import bpy
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    if info['kind'] == 'decal':
        tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(info['image'], check_existing=True)
        tr = nt.nodes.new('ShaderNodeBsdfTransparent'); mx = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(tex.outputs['Alpha'], mx.inputs[0]); nt.links.new(tr.outputs[0], mx.inputs[1])
        nt.links.new(tex.outputs['Color'], mx.inputs[2]); nt.links.new(mx.outputs[0], out.inputs['Surface'])
        m.surface_render_method = 'BLENDED'
    else:
        rgb = nt.nodes.new('ShaderNodeRGB'); rgb.outputs[0].default_value = (*info['lit'], 1)
        nt.links.new(rgb.outputs[0], out.inputs['Surface'])
    m.use_backface_culling = True


# ---------------------------------------------------------------- VRM 1.0
def _snake(name):
    return re.sub(r'([A-Z])', r'_\1', name).lower()


def export_vrm(armature, meshes, out_path, meta, decals=None, defaults=None, expressions=None, springs=None):
    """Export VRM 1.0.
    armature: the character's armature (VRM humanoid bone names); meshes: its visible mesh objects;
    meta: {'name', 'version', 'authors': [...], 'copyright', 'contact', 'references': [...], 'commercial_usage',
           'avatar_permission', 'credit_notation', 'allow_redistribution', 'modification', 'other_license_url', ...}
    decals: {group: {state: object}}; defaults: {group: default state};
    expressions: {name: {group: state, ..., 'overrideBlink'/'overrideMouth'/'overrideLookAt': 'none'|'block'|'blend'}}
                 (VRM preset names in camelCase: happy, blinkLeft, aa, ...; anything else becomes a custom expression);
    springs: {bone: {'stiffness', 'drag', 'gravity', 'gravity_dir', 'hit_radius'}}.
    -> a report dict (what was mapped, what wasn't)."""
    import bpy
    enable_addon()
    springs = springs or {}
    report = {'unmapped_expressions': [], 'materials': {}, 'not_mapped': NOT_MAPPED}
    with ExportRig(armature, meshes, decals, defaults, springs=list(springs)) as R:
        arm = R.arm
        ext = arm.data.vrm_addon_extension
        ext.spec_version = '1.0'
        v1 = ext.vrm1
        # humanoid: every bone whose name is a VRM humanoid bone maps to itself
        hb = v1.humanoid.human_bones
        hb.initial_automatic_bone_assignment = False
        mapped = []
        for b in arm.data.bones:
            prop = getattr(hb, _snake(b.name), None)
            if prop is not None and hasattr(prop, 'node'):
                prop.node.bone_name = b.name
                mapped.append(b.name)
        report['humanoid'] = mapped
        v1.humanoid.pose = 'autoPose'
        # meta
        mt = v1.meta
        mt.vrm_name = meta.get('name', arm.name)
        mt.version = meta.get('version', '1.0')
        for a in meta.get('authors', ['charkit']):
            mt.authors.add().value = a
        for r in meta.get('references', []):
            mt.references.add().value = r
        for k in ('copyright_information', 'contact_information', 'third_party_licenses', 'avatar_permission',
                  'commercial_usage', 'credit_notation', 'modification', 'other_license_url', 'allow_redistribution',
                  'allow_excessively_violent_usage', 'allow_excessively_sexual_usage', 'allow_political_or_religious_usage',
                  'allow_antisocial_or_hate_usage'):
            if k in meta:
                setattr(mt, k, meta[k])
        # materials
        for name, m in R.mat_map.items():
            info = R.minfo[name]
            mtoon(m, info, outline=R.mat_outline.get(name))
            report['materials'][name] = info['kind']
        # expressions
        ex = v1.expressions
        ex.initial_automatic_expression_assignment = False
        presets = ex.preset.name_to_expression_dict()
        for name, spec in (expressions or {}).items():
            if name in presets or _snake(name) in presets:
                e = presets.get(name) or presets[_snake(name)]
            else:
                e = ex.custom.add(); e.custom_name = name
            binds = {g: s for g, s in spec.items() if g in R.groups}
            if not binds and name != 'neutral':
                report['unmapped_expressions'].append(name)
            for g, s in binds.items():
                G = R.groups[g]
                if s == G['default']:
                    continue
                for ob, key in ((G['objects'][s], 'show'), (G['objects'][G['default']], 'hide')):
                    b = e.morph_target_binds.add()
                    b.node.mesh_object_name = ob.name
                    b.index = key
                    b.weight = 1.0
            e.is_binary = True
            for k, attr in (('overrideBlink', 'override_blink'), ('overrideMouth', 'override_mouth'),
                            ('overrideLookAt', 'override_look_at')):
                if k in spec:
                    setattr(e, attr, spec[k])
        report['expressions'] = sorted(expressions or {})
        # springs: one joint per helper bone + its tail
        sb = ext.spring_bone1
        for bone, p in springs.items():
            sp = sb.add_spring(); sp.vrm_name = bone
            for jn in (bone, bone + '_end'):
                j = sp.add_joint()
                j.node.bone_name = jn
                j.stiffness = p.get('stiffness', 1.0); j.drag_force = p.get('drag', 0.4)
                j.gravity_power = p.get('gravity', 0.0); j.hit_radius = p.get('hit_radius', 0.02)
                j.gravity_dir = p.get('gravity_dir', (0, 0, -1))
        report['springs'] = list(springs)
        # look-at: expression type with no binds (the gaze lives in a shader we don't export)
        try:
            v1.look_at.type = 'expression'
        except Exception:
            pass
        # export: only the copies
        bpy.ops.object.select_all(action='DESELECT')
        for o in [arm] + R.meshes + [o for g in R.groups.values() for o in g['objects'].values()]:
            o.hide_viewport = False
            o.select_set(True)
        bpy.context.view_layer.objects.active = arm
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        res = bpy.ops.export_scene.vrm(filepath=os.path.abspath(out_path), armature_object_name=arm.name,
                                       export_only_selections=True, ignore_warning=True, export_try_sparse_sk=True)
        if res != {'FINISHED'}:
            raise RuntimeError(f'VRM export: {res}')
        report['reoriented_parts'] = {k: v for k, v in R.flipped.items() if v}
        report['decal_groups'] = {g: {'states': G['states'], 'default': G['default'], 'verts': G['verts']}
                                  for g, G in R.groups.items()}
    return report


def export_gltf(armature, meshes, out_path, decals=None, defaults=None):
    """The plain fallback: skinned glTF (GLB) with unlit materials in the lit tones, decal groups as shape keys (no
    expressions, no springs, no outlines). Any glTF viewer shows it."""
    import bpy
    with ExportRig(armature, meshes, decals, defaults) as R:
        for name, m in R.mat_map.items():
            unlit(m, R.minfo[name])
        bpy.ops.object.select_all(action='DESELECT')
        objs = [R.arm] + R.meshes + [o for g in R.groups.values() for o in g['objects'].values()]
        for o in objs:
            o.hide_viewport = False
            o.select_set(True)
        bpy.context.view_layer.objects.active = R.arm
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        res = bpy.ops.export_scene.gltf(filepath=os.path.abspath(out_path), export_format='GLB', use_selection=True,
                                        export_apply=False, export_skins=True, export_morph=True, export_def_bones=True,
                                        export_animations=False, export_yup=True, export_try_sparse_sk=True,
                                        export_materials='EXPORT', export_extras=False)
        if res != {'FINISHED'}:
            raise RuntimeError(f'glTF export: {res}')


# ---------------------------------------------------------------- validation (pure Python: parse the GLB)
def read_glb(path):
    data = open(path, 'rb').read()
    magic, ver, length = struct.unpack_from('<III', data, 0)
    assert magic == 0x46546C67, 'not a GLB'
    n, off = len(data), 12
    js, binchunk = None, b''
    while off < n:
        clen, ctype = struct.unpack_from('<II', data, off)
        chunk = data[off + 8: off + 8 + clen]
        if ctype == 0x4E4F534A:
            js = json.loads(chunk)
        elif ctype == 0x004E4942:
            binchunk = chunk
        off += 8 + clen
    return js, binchunk


def triangles(js):
    tris = 0
    for mesh in js.get('meshes', []):
        for p in mesh['primitives']:
            mode = p.get('mode', 4)
            cnt = js['accessors'][p['indices']]['count'] if 'indices' in p else js['accessors'][p['attributes']['POSITION']]['count']
            tris += cnt // 3 if mode == 4 else max(0, cnt - 2)
    return tris


REQUIRED_BONES = ['hips', 'spine', 'head', 'leftUpperArm', 'leftLowerArm', 'leftHand', 'rightUpperArm', 'rightLowerArm',
                  'rightHand', 'leftUpperLeg', 'leftLowerLeg', 'leftFoot', 'rightUpperLeg', 'rightLowerLeg', 'rightFoot']


def validate_vrm(path):
    """Check the VRMC_vrm humanoid, expressions, meta, VRMC_springBone and MToon extensions in the GLB's JSON; -> report."""
    js, _ = read_glb(path)
    rep = {'file': path, 'bytes': os.path.getsize(path), 'triangles': triangles(js), 'errors': [], 'warnings': []}
    used = js.get('extensionsUsed', [])
    rep['extensionsUsed'] = used
    vrm = js.get('extensions', {}).get('VRMC_vrm')
    if not vrm:
        rep['errors'].append('no VRMC_vrm'); return rep
    rep['specVersion'] = vrm.get('specVersion')
    nodes = js['nodes']
    hb = vrm.get('humanoid', {}).get('humanBones', {})
    rep['humanBones'] = len(hb)
    for b in REQUIRED_BONES:
        if b not in hb:
            rep['errors'].append(f'humanoid: missing required {b}')
    bad = [b for b, v in hb.items() if nodes[v['node']].get('name') != b]
    if bad:
        rep['warnings'].append(f'humanoid bones on differently named nodes: {bad}')
    # T-pose check: upper arms along +-X in the rest node world transforms (VRM 1.0 faces +Z; her left is +X)
    rep['tpose'] = _tpose_check(js, hb)
    ex = vrm.get('expressions', {})
    pre, cus = ex.get('preset', {}), ex.get('custom', {})
    rep['expressions'] = {'preset': sorted(pre), 'custom': sorted(cus)}
    for name, e in {**pre, **cus}.items():
        for mb in e.get('morphTargetBinds', []):
            mesh = js['meshes'][js['nodes'][mb['node']]['mesh']]
            names = mesh.get('extras', {}).get('targetNames', [])
            if mb['index'] >= len(mesh['primitives'][0].get('targets', [])):
                rep['errors'].append(f'expression {name}: morph index {mb["index"]} out of range')
            else:
                mb['_target'] = f"{mesh.get('name')}:{names[mb['index']] if mb['index'] < len(names) else mb['index']}"
    rep['expression_binds'] = {n: [b.get('_target') for b in e.get('morphTargetBinds', [])] for n, e in {**pre, **cus}.items()}
    meta = vrm.get('meta', {})
    rep['meta'] = {k: meta.get(k) for k in ('name', 'version', 'authors', 'licenseUrl', 'commercialUsage', 'avatarPermission')}
    for k in ('name', 'authors', 'licenseUrl'):
        if not meta.get(k):
            rep['errors'].append(f'meta: missing {k}')
    sb = js.get('extensions', {}).get('VRMC_springBone')
    if sb:
        rep['springs'] = [{'name': s.get('name'), 'joints': [nodes[j['node']].get('name') for j in s['joints']],
                           'stiffness': s['joints'][0].get('stiffness'), 'dragForce': s['joints'][0].get('dragForce')}
                          for s in sb.get('springs', [])]
    else:
        rep['warnings'].append('no VRMC_springBone')
    mats = js.get('materials', [])
    rep['materials'] = len(mats)
    rep['mtoon_materials'] = sum(1 for m in mats if 'VRMC_materials_mtoon' in m.get('extensions', {}))
    rep['outlined'] = sum(1 for m in mats if m.get('extensions', {}).get('VRMC_materials_mtoon', {}).get('outlineWidthMode', 'none') != 'none')
    rep['textures'] = len(js.get('textures', []))
    rep['skins'] = len(js.get('skins', []))
    rep['meshes'] = len(js.get('meshes', []))
    rep['morph_targets'] = {m['name']: len(m['primitives'][0].get('targets', [])) for m in js.get('meshes', [])
                            if m['primitives'][0].get('targets')}
    return rep


def _tpose_check(js, hb):
    import numpy as np

    def local(n):
        t = np.array(n.get('translation', [0, 0, 0]), float)
        q = n.get('rotation', [0, 0, 0, 1]); x, y, z, w = q
        R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                      [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                      [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])
        s = np.array(n.get('scale', [1, 1, 1]), float)
        M = np.eye(4); M[:3, :3] = R * s; M[:3, 3] = t
        return M
    nodes = js['nodes']
    parent = {}
    for i, n in enumerate(nodes):
        for c in n.get('children', []):
            parent[c] = i

    def world(i):
        M = local(nodes[i])
        while i in parent:
            i = parent[i]; M = local(nodes[i]) @ M
        return M
    out = {}
    for a, b in (('leftUpperArm', 'leftLowerArm'), ('rightUpperArm', 'rightLowerArm'), ('leftLowerArm', 'leftHand'),
                 ('leftUpperLeg', 'leftLowerLeg')):
        if a in hb and b in hb:
            d = world(hb[b]['node'])[:3, 3] - world(hb[a]['node'])[:3, 3]
            out[a] = [round(float(x), 3) for x in d / (np.linalg.norm(d) + 1e-9)]
    return out


def reimport_check(path):
    """Load the VRM back with the add-on into an empty scene: -> {'objects', 'armature bones', 'expressions', 'springs'}."""
    import bpy
    enable_addon()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    enable_addon()
    res = bpy.ops.import_scene.vrm(filepath=os.path.abspath(path))
    arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
    out = {'result': sorted(res), 'objects': len(bpy.data.objects)}
    if arm:
        v1 = arm.data.vrm_addon_extension.vrm1
        out['bones'] = len(arm.data.bones)
        out['assigned_human_bones'] = sum(1 for n, b in v1.humanoid.human_bones.human_bone_name_to_human_bone().items()
                                          if b.node.bone_name)
        out['expressions'] = len(v1.expressions.all_name_to_expression_dict())
        out['springs'] = len(arm.data.vrm_addon_extension.spring_bone1.springs)
        out['mtoon_materials'] = sum(1 for m in bpy.data.materials if m.vrm_addon_extension.mtoon1.enabled)
    return out


# ---------------------------------------------------------------- motion for the browser
def clip_to_json(npz_path, out_path, bone_map=None, twist_refs=None, decimals=5):
    """A canonical clip (SOMA joints, Y up, facing +Z: the glTF/VRM 1.0 frame) -> JSON for engine/three/vrm.js:
    per frame the WORLD rotations (x, y, z, w) of the joints the VRM map reads, the root position, contacts, and the rest
    joint positions the retarget calibrates against (motion.calibrate's idea: aim each bone along its source bone's rest
    direction, then per frame W_bone = G_source(t) . Wcal_bone). No Y-up/Z-up swap: the clip and VRM share the frame."""
    import numpy as np
    if bone_map is None:
        sys.path.insert(0, os.path.join(REPO, 'projects', 'clawd3d', 'build'))
        import soma_map
        bone_map, twist_refs = soma_map.BONE_MAP, soma_map.TWIST_REFS
    d = np.load(npz_path, allow_pickle=False)
    J = [str(j) for j in d['joints']]
    par, off = d['parents'], d['offsets'].astype(np.float64)
    rot = d['rot'].astype(np.float64)                     # T, J, (w, x, y, z) local
    T = rot.shape[0]

    def qmul(a, b):
        aw, ax, ay, az = np.moveaxis(a, -1, 0); bw, bx, by, bz = np.moveaxis(b, -1, 0)
        return np.stack([aw * bw - ax * bx - ay * by - az * bz, aw * bx + ax * bw + ay * bz - az * by,
                         aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw], -1)
    G = np.zeros_like(rot)
    for j in range(len(J)):
        G[:, j] = rot[:, j] if par[j] < 0 else qmul(G[:, par[j]], rot[:, j])
    rest = np.zeros((len(J), 3))                          # rest joint positions (rest rotations are identity)
    for j in range(len(J)):
        if par[j] >= 0:
            rest[j] = rest[par[j]] + off[j]
    rest += off[0]                                        # the root's rest position (hips above the floor)
    src = sorted({j for j, _ in bone_map.values()})
    need = sorted(set(src) | {c for _, c in bone_map.values()} | {x for ab in (twist_refs or {}).values() for x in ab})
    # continuity: keep each joint's quaternion in the hemisphere of its previous frame (slerp takes the short way anyway)
    Gs = G[:, [J.index(j) for j in src]]
    for t in range(1, T):
        flip = (Gs[t] * Gs[t - 1]).sum(-1) < 0
        Gs[t, flip] *= -1
    r = lambda x: round(float(x), decimals)
    out = {
        'source': os.path.relpath(npz_path, REPO), 'fps': float(d['fps']), 'frames': T,
        'frame': 'Y up, facing +Z (glTF / VRM 1.0), metres',
        'joints': src,
        'rot': [[[r(q[1]), r(q[2]), r(q[3]), r(q[0])] for q in Gs[t]] for t in range(T)],   # x, y, z, w
        'root': [[r(x) for x in d['root'][t]] for t in range(T)],
        'contact': [[round(float(x), 3) for x in d['contact'][t]] for t in range(T)] if 'contact' in d.files else None,
        'rest': {j: [r(x) for x in rest[J.index(j)]] for j in need},
        'hipsHeight': float(off[0][1]),
        'map': {b: list(v) for b, v in bone_map.items()},
        'twist': {b: list(v) for b, v in (twist_refs or {}).items()},
    }
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    json.dump(out, open(out_path, 'w'), separators=(',', ':'))
    return out_path


# ---------------------------------------------------------------- the test character: Clawd
CLAWD_EXPRESSIONS = {
    # presets (eyes only, so singing keeps its mouth: how Clawd acts in the dance test); emotions block the blink
    'neutral': {},
    'blink': {'eyes': 'closed'},
    'blinkLeft': {'eyes': 'wink'},                      # the drawn wink closes her left eye (image right)
    'happy': {'eyes': 'happy', 'overrideBlink': 'block'},
    'relaxed': {'eyes': 'soft', 'overrideBlink': 'block'},
    'surprised': {'eyes': 'surprised', 'overrideBlink': 'block'},
    'angry': {'eyes': 'determined', 'overrideBlink': 'block'},   # the nearest drawn state; there is no angry drawing
    'aa': {'mouth': 'A'}, 'ih': {'mouth': 'I'}, 'ou': {'mouth': 'U'}, 'ee': {'mouth': 'E'}, 'oh': {'mouth': 'O'},
    # no drawing: sad, blinkRight (only one wink is drawn), lookUp/Down/Left/Right (gaze; see NOT_MAPPED)
    'sad': {}, 'blinkRight': {},
    # custom: the rest of the drawn states
    'eyesHalf': {'eyes': 'half'},
    'mouthGrin': {'mouth': 'grin'}, 'mouthA2': {'mouth': 'A2'}, 'mouthS': {'mouth': 'S'}, 'mouthAm': {'mouth': 'Am'},
    'mouthIs': {'mouth': 'Is'}, 'mouthOs': {'mouth': 'Os'}, 'mouthMBP': {'mouth': 'MBP'}, 'mouthEh': {'mouth': 'Eh'},
    'mouthIh': {'mouth': 'Ih'},
}
CLAWD_META = {
    'name': 'Clawd', 'version': 'clawd3d', 'authors': ['animation-pipeline (charkit)'],
    'copyright_information': 'animation-pipeline', 'avatar_permission': 'onlyAuthor', 'commercial_usage': 'corporation',
    'credit_notation': 'unnecessary', 'allow_redistribution': False, 'modification': 'prohibited',
}


def springs_from(spring_table):
    """clawd.SPRINGS {bone: (k, c, limit_deg)} (motion.bake's damped rotational springs) -> VRM joint settings. There is no
    exact map (VRM springs are verlet points pulled to the rest direction); stiffness rises with k, drag with the damping
    ratio c / 2 sqrt(k)."""
    out = {}
    for bone, (k, c, lim) in spring_table.items():
        zeta = c / (2 * math.sqrt(k))
        out[bone] = {'stiffness': round(min(4.0, k / 60.0), 3), 'drag': round(min(0.9, 0.25 + 0.4 * zeta), 3),
                     'gravity': 0.0, 'hit_radius': 0.02}
    return out


def export_clawd(out_dir):
    import bpy
    sys.path.insert(0, os.path.join(REPO, 'projects', 'clawd3d', 'build'))
    import clawd
    C = clawd.build()
    arm = C['arm']
    decals = {'eyes': {n: o for (k, n), o in C['face'].items() if k == 'eyes'},
              'mouth': {n: o for (k, n), o in C['face'].items() if k == 'mouth'}}
    face = set(C['face'].values())
    meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o not in face and not o.hide_render]
    defaults = {'eyes': 'open', 'mouth': 'rest'}
    os.makedirs(out_dir, exist_ok=True)
    enable_addon()
    export_gltf(arm, meshes, os.path.join(out_dir, 'clawd.glb'), decals, defaults)
    rep = export_vrm(arm, meshes, os.path.join(out_dir, 'clawd.vrm'), CLAWD_META, decals, defaults, CLAWD_EXPRESSIONS,
                     springs_from(clawd.SPRINGS))
    return rep


if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    if '--clip' in argv:
        i = argv.index('--clip')
        print(clip_to_json(argv[i + 1], argv[i + 2]))
    elif '--check' in argv:
        p = argv[argv.index('--check') + 1]
        print(json.dumps(validate_vrm(p), indent=1))
        if '--reimport' in argv:
            print(json.dumps(reimport_check(p), indent=1))
    elif argv and argv[0] == 'clawd':
        out = argv[argv.index('--out') + 1] if '--out' in argv else os.path.join(REPO, 'charkit', 'out', 'export')
        rep = export_clawd(out)
        v = validate_vrm(os.path.join(out, 'clawd.vrm'))
        g, _ = read_glb(os.path.join(out, 'clawd.glb'))
        summary = {'export': rep, 'vrm': v, 'glb': {'bytes': os.path.getsize(os.path.join(out, 'clawd.glb')),
                                                    'triangles': triangles(g)}}
        json.dump(summary, open(os.path.join(out, 'report.json'), 'w'), indent=1)
        print(json.dumps({k: summary['vrm'].get(k) for k in ('bytes', 'triangles', 'humanBones', 'errors', 'warnings', 'tpose',
                                                              'springs', 'mtoon_materials', 'outlined', 'morph_targets')}, indent=1))
        print('glb', summary['glb'])
    else:
        print(__doc__)
