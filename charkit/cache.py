"""The build cache (docs/CHARKIT.md §3): each scene stage's output is checkpointed under charkit/out/.cache/ and restored,
instead of rebuilt, when nothing the stage read has changed; the boards, the QA and the VRM are cached the same way on the
whole scene. Blender-side (charkit/scene.py and charkit/build_blender.py drive it); the hashing and the code closure are
plain Python.

A stage's key is what the stage read, recorded while it ran, so a read nobody listed can't be missed:
  code      the stage function, the scene.py helpers it calls and scene.py's top-level statements, and every charkit
            module they import, transitively, as syntax trees (comments and docstrings don't count); the kit's data
            (charkit/assets); this module; the Blender, numpy and Python versions
  spec      each top-level spec section it read (`spec.hair`), exactly
  upstream  each value it read of what came before: the Scene's attributes and, key by key, the dicts under them
            (`character.data.head.L`, `character.data.joints.neck01____head`), shade.MATS entries, Blender objects (their
            full state, or the part scene.DEPS declares the stage reads: garments read the body below the neck, and only the
            names of the skin's modifiers and groups)
  files     every file it opened outside the kit (the TRELLIS GLB) and every path named in the spec sections it read, by
            sha256 (a stat-checked memo skips re-hashing unchanged files; a manifest's sha256 is compared, not trusted)
A lookup evaluates each stored entry's recorded reads against the scene as it now stands and restores the first entry
whose reads all match. A miss says what changed: `spec.hair`, `character.data.joints.neck01____head moved 5.5e-05`,
`file charkit/out/i3d/clawd/clawd_3dstyle_s1.glb`, `code charkit/garments.py`.

A checkpoint holds what the stage changed and only that, so it restores onto a rebuilt upstream (garments onto a new face):
  data.blend   the datablocks it made (bpy.data.libraries.write); what they point at from before (the rig, a shared
               material) is re-bound by name when they are appended
  state.pkl    the Scene attributes, spec sections, dict entries and shade.MATS entries it set (pickled, Blender references by
               name), the notes it wrote, and its changes to objects made before it: new vertex groups, modifiers (settings
               and stack position), attributes and material slots, replayed on restore
  inputs.npz   the small arrays it read, so a miss can say how far they moved; images.npz the float images' pixels
Anything else a stage changes (an earlier mesh's vertices, a material made before it, an object it reached without
reading it through the Scene) makes it uncacheable: it runs every time and the trace says why. After a restore the trace's
own snapshot of the stage (the objects it added, their geometry hashes and health) must equal the one stored with the
entry, or the build starts over without the cache. Pickle is the state format because a stage's state is numpy arrays
and charkit's own classes as Python holds them; a .npz/.json schema would have to track every structure a stage keeps.
Entries are read only from this directory, which charkit alone writes.

Modes (`build --cache MODE`): on (the default), off, refresh (run everything and store it), stages (restore the stages,
run the boards, QA and VRM afresh on the restored scene), verify (run everything and compare each stage and product with
the entry a lookup would have restored; a difference is a key that missed an input, printed as CHARKIT_CACHE_STALE and
recorded in the trace).
    python -m charkit cache [info | clear]
"""
import ast, contextlib, hashlib, json, os, pickle, shutil, stat, struct, sys, tempfile, time, types

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.join(ROOT, 'charkit')
SCHEMA = 1
MODES = ('on', 'off', 'refresh', 'verify', 'stages')
MAX_GB = float(os.environ.get('CHARKIT_CACHE_MAX_GB', 12))
ALL, HAS = '\0*', '\0?'                 # path markers: the whole dict was read; only the key's presence was


def cache_dir():
    return os.environ.get('CHARKIT_CACHE_DIR') or os.path.join(KIT, 'out', '.cache')


class Uncacheable(Exception):
    """a step read or changed something the cache can't key or restore: it runs every time."""


class RestoreError(Exception):
    """a restore didn't reproduce the stored step: the build starts over without the cache."""


class _Absent:
    def __repr__(self):
        return '<absent>'

    def __reduce__(self):
        return 'ABSENT'                                     # unpickles as this module's own


ABSENT = _Absent()


# ------------------------------------------------------------------------------------------------------------ hashing
def digest(x, facet=None):
    """an exact, typed, order-keeping hash of a value (equal digests: equal values). Blender objects by their full state
    (facet 'structure': names and transforms only), other datablocks by name."""
    h = hashlib.sha256()                                 # (hardware-accelerated here: faster than sha1 or blake2)
    _feed(h, x, facet)
    return h.hexdigest()[:40]


def _tag(x):
    t = type(x)
    return b'' if t in (dict, list, tuple, TrackedDict) else ('<%s.%s>' % (t.__module__, t.__qualname__)).encode()


def _feed(h, x, facet=None):
    t = type(x)
    if x is None:
        h.update(b'N')
    elif x is ABSENT:
        h.update(b'A')
    elif t is bool:
        h.update(b'T' if x else b'F')
    elif t is int:
        h.update(b'i%d;' % x)
    elif t is float:
        h.update(b'f' + struct.pack('<d', x))
    elif t is str:
        b = x.encode('utf-8', 'surrogatepass')
        h.update(b's%d:' % len(b)); h.update(b)
    elif t is bytes:
        h.update(b'b%d:' % len(x)); h.update(x)
    elif isinstance(x, np.ndarray):
        if x.dtype.hasobject:
            h.update(b'O' + repr(x.shape).encode())
            for e in x.ravel():
                _feed(h, e, facet)
        else:
            a = np.ascontiguousarray(x)
            h.update(b'a' + a.dtype.str.encode() + repr(a.shape).encode())
            h.update(memoryview(a.reshape(-1)).cast('B') if a.size else b'')
    elif isinstance(x, np.generic):
        _feed(h, np.asarray(x))
    elif isinstance(x, dict):
        h.update(b'd' + _tag(x) + b'%d:' % len(x))
        for k, v in dict.items(x):
            _feed(h, k); _feed(h, v, facet)
    elif isinstance(x, (list, tuple)):
        if not _feed_seq(h, x):
            h.update(b'l' + _tag(x) + b'%d:' % len(x))
            for e in x:
                _feed(h, e, facet)
    elif isinstance(x, (set, frozenset)):
        ds = sorted(digest(e, facet) for e in x)
        h.update(b'S%d:' % len(ds) + ''.join(ds).encode())
    elif _is_id(x):
        _feed_id(h, x, facet)
    elif _mathutils(x) is not None:
        h.update(b'm'); _feed(h, _mathutils(x))
    elif isinstance(x, (types.FunctionType, types.BuiltinFunctionType, types.MethodType, type, types.ModuleType)):
        h.update(b'c'); _feed(h, '%s.%s' % (getattr(x, '__module__', ''), getattr(x, '__qualname__', getattr(x, '__name__', ''))))
    else:
        _feed_object(h, x, facet)


def _feed_seq(h, x):
    """long lists of numbers or of number tuples (faces, UVs) in one go; False when x isn't one."""
    if len(x) < 16:
        return False
    t0 = type(x[0])
    try:
        if t0 in (int, float) and all(type(e) is t0 for e in x):
            h.update(b'q' + (b'I' if t0 is int else b'F') + _tag(x) + b'%d:' % len(x))
            h.update(memoryview(np.array(x, np.int64 if t0 is int else np.float64)).cast('B'))
            return True
        if t0 in (tuple, list) and all(type(e) is t0 for e in x):
            flat = [v for e in x for v in e]
            if not flat:
                return False
            v0 = type(flat[0])
            if v0 not in (int, float) or not all(type(v) is v0 for v in flat):
                return False
            h.update(b'Q' + (b'I' if v0 is int else b'F') + (b'T' if t0 is tuple else b'L') + _tag(x) + b'%d:' % len(x))
            h.update(memoryview(np.array([len(e) for e in x], np.int64)).cast('B'))
            h.update(memoryview(np.array(flat, np.int64 if v0 is int else np.float64)).cast('B'))
            return True
    except (OverflowError, ValueError):
        return False
    return False


def _feed_object(h, x, facet):
    """an instance of a class: its class and its state (a class's own __reduce__, else __getstate__ / __dict__)."""
    cls = type(x)
    h.update(b'o' + ('%s.%s' % (cls.__module__, cls.__qualname__)).encode())
    red = next((c.__dict__['__reduce__'] for c in cls.__mro__ if '__reduce__' in c.__dict__), None)
    if red is not None and red is not object.__reduce__:
        r = x.__reduce__()
        _feed(h, list(r[:2]) if isinstance(r, tuple) else r, facet)
        return
    if hasattr(x, '__dict__') or hasattr(cls, '__slots__'):
        st = x.__getstate__() if hasattr(x, '__getstate__') else x.__dict__
        _feed(h, st, facet)
        return
    raise Uncacheable('cannot key a %s' % cls.__name__)


def _bpy():
    return sys.modules.get('bpy')


def _is_id(x):
    bpy = _bpy()
    return bpy is not None and isinstance(x, bpy.types.ID)


def _mathutils(x):
    mu = sys.modules.get('mathutils')
    if mu is None:
        return None
    if isinstance(x, (mu.Vector, mu.Quaternion, mu.Euler, mu.Color)):
        return tuple(x)
    if isinstance(x, mu.Matrix):
        return tuple(tuple(r) for r in x)
    return None


def _feed_id(h, x, facet):
    h.update(b'ID'); _feed(h, [x.id_type, x.name, x.library.filepath if x.library else None])
    if facet == 'name' or x.id_type != 'OBJECT':
        return
    _feed(h, render_parts(x) if facet == 'render' else ob_parts(x, full=facet != 'structure'))


# ---------------------------------------------------------------------------------------------------- Blender state
COLL = {'OBJECT': 'objects', 'MESH': 'meshes', 'MATERIAL': 'materials', 'IMAGE': 'images', 'ARMATURE': 'armatures',
        'NODETREE': 'node_groups', 'CAMERA': 'cameras', 'LIGHT': 'lights', 'WORLD': 'worlds', 'COLLECTION': 'collections',
        'CURVE': 'curves', 'TEXTURE': 'textures', 'ACTION': 'actions', 'KEY': 'shape_keys', 'LATTICE': 'lattices',
        'META': 'metaballs', 'FONT': 'fonts', 'GREASEPENCIL': 'grease_pencils', 'CURVES': 'hair_curves',
        'POINTCLOUD': 'pointclouds', 'VOLUME': 'volumes', 'TEXT': 'texts', 'SCENE': 'scenes', 'SPEAKER': 'speakers',
        'LIGHT_PROBE': 'lightprobes', 'PALETTE': 'palettes', 'PARTICLE': 'particles', 'SOUND': 'sounds',
        'MOVIECLIP': 'movieclips', 'MASK': 'masks', 'CACHEFILE': 'cache_files', 'LINESTYLE': 'linestyles',
        'BRUSH': 'brushes', 'PAINTCURVE': 'paint_curves', 'WORKSPACE': 'workspaces', 'SCREEN': 'screens',
        'WINDOWMANAGER': 'window_managers', 'LIBRARY': 'libraries', 'VFONT': 'fonts', 'GREASEPENCIL_V3': 'grease_pencils'}
WRITABLE = ('objects', 'meshes', 'materials', 'images', 'armatures', 'node_groups', 'cameras', 'lights', 'curves',
            'textures', 'actions', 'lattices', 'metaballs', 'hair_curves', 'pointclouds', 'volumes', 'texts', 'palettes',
            'particles', 'fonts')
# attribute data types -> (foreach property, components, buffer dtype)
_ATTR = {'FLOAT': ('value', 1, np.float32), 'INT': ('value', 1, np.int32), 'INT8': ('value', 1, np.int32),
         'BOOLEAN': ('value', 1, bool), 'FLOAT_VECTOR': ('vector', 3, np.float32), 'FLOAT2': ('vector', 2, np.float32),
         'INT32_2D': ('value', 2, np.int32), 'INT16_2D': ('value', 2, np.int32), 'FLOAT_COLOR': ('color', 4, np.float32),
         'BYTE_COLOR': ('color', 4, np.float32), 'QUATERNION': ('value', 4, np.float32),
         'FLOAT4X4': ('value', 16, np.float32)}


def _colls():
    bpy = _bpy()
    return [c for c in dict.fromkeys(COLL.values()) if hasattr(bpy.data, c)]


def datablocks():
    """{(collection, pointer): datablock} of everything in bpy.data (libraries aside)."""
    bpy = _bpy()
    return {(c, i.as_pointer()): i for c in _colls() if c != 'libraries' for i in getattr(bpy.data, c)}


def _m(M):
    return tuple(tuple(r) for r in M)


def _arr(coll, prop, n, k=1, dt=np.float32):
    a = np.empty(n * k, dt)
    if n:
        coll.foreach_get(prop, a)
    return a


def attr_data(a):
    try:
        prop, k, dt = _ATTR[a.data_type]
    except KeyError:
        raise Uncacheable('attribute %s of type %s' % (a.name, a.data_type))
    return _arr(a.data, prop, len(a.data), k, dt)


def vgroup_weights(ob):
    """{group name: (vertex indices, weights)} of a mesh object."""
    gi, vi, w = [], [], []
    for v in ob.data.vertices:
        for g in v.groups:
            gi.append(g.group); vi.append(v.index); w.append(g.weight)
    gi, vi, w = np.array(gi, np.int32), np.array(vi, np.int32), np.array(w, np.float32)
    return {g.name: (vi[gi == g.index], w[gi == g.index]) for g in ob.vertex_groups}


def rna(s, depth=0):
    """a struct's settable properties as plain values (datablocks as ('ID', type, name))."""
    bpy = _bpy()
    out = {}
    for p in s.bl_rna.properties:
        k = p.identifier
        if k in ('rna_type', 'name', 'type', 'is_active', 'show_expanded', 'is_override_data', 'persistent_uid'):
            continue                                        # identity and panel state, not settings
        if p.type == 'COLLECTION':
            if len(getattr(s, k)):
                raise Uncacheable('%s.%s: a collection' % (getattr(s, 'name', type(s).__name__), k))
            continue
        v = getattr(s, k)
        if p.type == 'POINTER':
            if v is None:
                out[k] = None
            elif isinstance(v, bpy.types.ID):
                out[k] = ('ID', v.id_type, v.name)
            elif depth < 2 and not p.is_readonly or depth < 2 and k in ('settings',):
                out[k] = rna(v, depth + 1)
            continue
        if p.is_readonly:
            continue
        if p.type == 'ENUM' and p.is_enum_flag:
            v = sorted(v)
        elif getattr(p, 'is_array', False):
            v = _plain_seq(v)
        out[k] = v
    return out


def _plain_seq(v):
    try:
        return tuple(_plain_seq(e) for e in v)
    except TypeError:
        return v


def ob_parts(ob, full=True):
    """an object's state as named parts, each a digest: 'object' (name, type, data, parent, transform, visibility), 'mods'
    (the stack), 'vgs', 'mats' (slots), 'layout' (counts, attribute and key names); full adds 'geom', 'attr:NAME',
    'vg:NAME' (weights), 'sk' (shape keys), 'mod:NAME' (settings) and the bones. full=False is what a stage that parents
    to an object, or adds groups and modifiers to it, depends on."""
    P = {'object': digest([ob.name, ob.type, ob.data.name if ob.data else None, ob.parent.name if ob.parent else None,
                           ob.parent_type, ob.parent_bone, _m(ob.matrix_world), _m(ob.matrix_parent_inverse),
                           ob.hide_render, ob.hide_viewport]),
         'mods': digest([(m.name, m.type) for m in ob.modifiers]),
         'vgs': digest([g.name for g in ob.vertex_groups]),
         'mats': digest([(s.link, s.material.name if s.material else None) for s in ob.material_slots])}
    if ob.type == 'MESH':
        me = ob.data
        ca = me.color_attributes
        P['layout'] = digest([len(me.vertices), len(me.edges), len(me.polygons), len(me.loops),
                              [(a.name, a.domain, a.data_type) for a in me.attributes if not a.name.startswith('.select')],
                              list(me.shape_keys.key_blocks.keys()) if me.shape_keys else None,
                              [u.name for u in me.uv_layers], ca.active_color_name, ca.default_color_name])
        if full:
            P['geom'] = digest([_arr(me.vertices, 'co', len(me.vertices), 3), _arr(me.edges, 'vertices', len(me.edges), 2, np.int32),
                                _arr(me.polygons, 'loop_start', len(me.polygons), 1, np.int32),
                                _arr(me.polygons, 'loop_total', len(me.polygons), 1, np.int32),
                                _arr(me.loops, 'vertex_index', len(me.loops), 1, np.int32)])
            for a in me.attributes:
                if not a.name.startswith('.select'):
                    P['attr:' + a.name] = digest([a.domain, a.data_type, attr_data(a)])
            for n, (vi, w) in vgroup_weights(ob).items():
                P['vg:' + n] = digest([vi, w])
            if me.shape_keys:
                ks = me.shape_keys
                P['sk'] = digest([ks.use_relative, ks.reference_key.name] + [
                    [k.name, k.value, k.mute, k.relative_key.name, k.vertex_group, k.slider_min, k.slider_max,
                     k.interpolation, _arr(k.data, 'co', len(k.data), 3)] for k in ks.key_blocks])
    if full:
        for m in ob.modifiers:
            P['mod:' + m.name] = digest(rna(m))
    if ob.type == 'ARMATURE':
        arm = ob.data
        P['bones'] = digest([arm.pose_position] + [b.name for b in arm.bones] +
                            [_m(pb.matrix_basis) for pb in ob.pose.bones] +
                            ([[b.parent.name if b.parent else None, _m(b.matrix_local), tuple(b.head_local),
                               tuple(b.tail_local), b.use_deform, b.use_connect] for b in arm.bones] if full else []))
    return P


def render_parts(ob):
    """what a render or a measurement of an object reads (a QA part): its full state, its materials' node graphs and the
    images they sample, and the objects its modifiers take from (the rig's pose and bones, a normals source)."""
    P = ob_parts(ob, full=True)
    for i, s_ in enumerate(ob.material_slots):
        if s_.material is not None:
            P['mat:%d' % i] = _mat_digest(s_.material, images=True)
    for m in ob.modifiers:
        for k, v in rna(m).items():
            if isinstance(v, tuple) and len(v) == 3 and v[0] == 'ID' and v[1] == 'OBJECT' and v[2] != ob.name:
                t = _bpy().data.objects.get(v[2])
                if t is not None:
                    P['from:%s.%s' % (m.name, k)] = digest(ob_parts(t, full=True))
    return P


def _loose_rna(s):
    """a node's settable settings (its operation, blend type, interpolation...): no collections, pointers or layout."""
    out = {}
    for p in s.bl_rna.properties:
        k = p.identifier
        if p.type in ('COLLECTION', 'POINTER') or p.is_readonly or k in _LAYOUT:
            continue
        v = getattr(s, k)
        out[k] = sorted(v) if p.type == 'ENUM' and p.is_enum_flag else _plain_seq(v) if getattr(p, 'is_array', False) else v
    return out


_LAYOUT = ('rna_type', 'location', 'width', 'height', 'select', 'hide', 'show_options', 'show_preview', 'label', 'color',
           'use_custom_color', 'location_absolute', 'show_texture', 'warning_propagation', 'color_tag')


def _tree_digest(nt, images, depth=0):
    nodes = []
    for n in nt.nodes:
        ins = []
        for s_ in n.inputs:
            dv = getattr(s_, 'default_value', None)
            ins.append(_plain_seq(dv) if dv is not None and not isinstance(dv, (str, int, float, bool)) else dv)
        img = getattr(n, 'image', None)
        ramp = getattr(n, 'color_ramp', None)
        sub = getattr(n, 'node_tree', None)
        nodes.append([n.name, n.bl_idname, ins, _loose_rna(n), img and img.name,
                      _img_digest(img) if img and images else None,
                      [(e.position, tuple(e.color)) for e in ramp.elements] if ramp is not None else None,
                      (ramp.interpolation, ramp.color_mode) if ramp is not None else None,
                      _tree_digest(sub, images, depth + 1) if sub is not None and depth < 4 else None])
    nodes.append(sorted((l.from_node.name, l.from_socket.identifier, l.to_node.name, l.to_socket.identifier)
                        for l in nt.links))
    return digest(nodes)


def _mat_digest(m, images=False):
    """a material's settings and node graph: every node's inputs and settings, its colour ramp, its image (by content with
    images=True) and a group's own graph (what a later stage could change on a material it didn't make; what a render
    reads)."""
    return digest([m.name, m.use_backface_culling, getattr(m, 'blend_method', None),
                   getattr(m, 'surface_render_method', None), _tree_digest(m.node_tree, images) if m.node_tree else None])


def _img_digest(i, pixels=False):
    """an image's digest: its packed file's bytes and whether its buffer was changed since (cheap: what world() compares),
    or with pixels=True its buffer itself (a checkpoint's own images, which must come back bit for bit)."""
    head = [tuple(i.size), i.channels, i.is_float, i.colorspace_settings.name]
    if not pixels and i.packed_file is not None:
        return digest(head + [i.is_dirty, i.packed_file.size, hashlib.sha1(i.packed_file.data).hexdigest()])
    return digest(head + [_pixels(i)])


def _pixels(i):
    a = np.empty(i.size[0] * i.size[1] * i.channels, np.float32)
    if len(a):
        i.pixels.foreach_get(a)
    return a


def scene_state():
    """the scene-level state a stage could touch: the active object, the camera, the render size and engine."""
    bpy = _bpy()
    sc = bpy.context.scene
    ao = bpy.context.view_layer.objects.active
    return dict(active=ao.name if ao else None, camera=sc.camera.name if sc.camera else None,
                render=[sc.render.engine, sc.render.resolution_x, sc.render.resolution_y, sc.render.film_transparent],
                world=sc.world.name if sc.world else None, frame=sc.frame_current)


def world(prev=None):
    """what a stage's changes are measured against: every datablock, the digests of the materials and the images in use,
    each object's structure, the scene state. With `prev`, digests only for what `prev` had."""
    bpy = _bpy()
    keep = (lambda c, i: (c, i.as_pointer()) in prev['ids']) if prev else (lambda c, i: True)
    return dict(ids=datablocks(),
                mats={m.as_pointer(): _mat_digest(m) for m in bpy.data.materials if keep('materials', m)},
                imgs={i.as_pointer(): _img_digest(i) for i in bpy.data.images if i.users and keep('images', i)},
                obs={o.as_pointer(): ob_parts(o, full=False) for o in bpy.data.objects if keep('objects', o)},
                scene=scene_state())


# --------------------------------------------------------------------------------------------------------------- files
class Files:
    """sha256 of files and directories, memoized on (size, mtime, inode): a file is hashed again when any of those moves,
    or when it was hashed within 2 s of its last change (a write in the same clock tick)."""

    def __init__(self, d):
        self.path = os.path.join(d, 'files.json')
        try:
            self.memo = json.load(open(self.path))
        except (OSError, ValueError):
            self.memo = {}
        self.dirty = False
        self.seen = {}

    def get(self, p, fresh=False):
        p = os.path.abspath(p)
        if p in self.seen and not fresh:
            return self.seen[p]
        try:
            st = os.stat(p)
        except OSError:
            h = 'absent'
        else:
            h = self._dir(p) if stat.S_ISDIR(st.st_mode) else self._file(p, st)
        self.seen[p] = h
        return h

    def _file(self, p, st):
        key = [st.st_size, st.st_mtime_ns, st.st_ino]
        m = self.memo.get(p)
        if m and m[:3] == key and m[4] - st.st_mtime_ns / 1e9 > 2:
            return m[3]
        h = hashlib.sha256()
        with open(p, 'rb') as f:
            for b in iter(lambda: f.read(1 << 20), b''):
                h.update(b)
        h = h.hexdigest()
        self.memo[p] = key + [h, time.time()]
        self.dirty = True
        return h

    def _dir(self, p):
        rows = []
        for d, dirs, files in os.walk(p):
            dirs.sort()
            for f in sorted(files):
                if f != '.DS_Store':
                    q = os.path.join(d, f)
                    rows.append((os.path.relpath(q, p), self.get(q)))
        return 'dir:' + digest(rows)

    def save(self):
        if self.dirty:
            _write_json(self.path, self.memo)
            self.dirty = False


def spec_paths(x, out=None):
    """the existing files and folders a spec value names (relative to the repo, or absolute)."""
    out = set() if out is None else out
    if isinstance(x, str):
        if 0 < len(x) < 1024 and ('/' in x or '.' in x):
            p = os.path.normpath(x if os.path.isabs(x) else os.path.join(ROOT, x))
            if os.path.exists(p) and p not in (ROOT, KIT) and not ROOT.startswith(p + os.sep):
                out.add(p)
    elif isinstance(x, dict):
        for v in dict.values(x):
            spec_paths(v, out)
    elif isinstance(x, (list, tuple)):
        for v in x:
            spec_paths(v, out)
    return out


def _skip_prefixes():
    ps = {sys.prefix, sys.base_prefix, sys.exec_prefix, '/System', '/usr', '/dev', '/Library'}
    bpy = _bpy()
    if bpy is not None:
        ps.add(os.path.dirname(os.path.dirname(os.path.abspath(bpy.app.binary_path))))
    return tuple(sorted(p.rstrip(os.sep) + os.sep for p in ps if p))


# ------------------------------------------------------------------------------------------------------------------ code
_MODS = {}


def _module_file(name):
    """charkit.x.y -> its source file (None outside charkit)."""
    parts = name.split('.')
    if parts[0] != 'charkit':
        return None
    for p in (os.path.join(KIT, *parts[1:]) + '.py', os.path.join(KIT, *parts[1:], '__init__.py')):
        if os.path.isfile(p):
            return p
    return None


def _strip_docs(tree):
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body and \
                isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], 'value', None), ast.Constant) and \
                isinstance(n.body[0].value.value, str):
            n.body = n.body[1:] or [ast.Pass()]


def _dump(node):
    return digest(ast.dump(node, annotate_fields=False, include_attributes=False))


class _Mod:
    """a parsed charkit module: its syntax tree's digest (docstrings dropped); per top-level definition its digest, the
    names it uses and the charkit modules it imports; the digest of its other top-level statements and the names they bind
    to charkit modules; the charkit modules it imports anywhere. Plain data, memoized on disk by file stamp."""

    def __init__(self, name, path, d=None):
        self.name, self.path = name, path
        self.rel = os.path.relpath(path, ROOT)
        if d is not None:
            self.__dict__.update(d)
            self.imports = set(self.imports)
            return
        tree = ast.parse(open(path).read())
        _strip_docs(tree)
        self.digest = _dump(tree)
        self.pkg = name if path.endswith('__init__.py') else name.rpartition('.')[0]
        self.defs, top, self.bound = {}, [], {}
        for n in tree.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names, imps = set(), set()
                for s_ in ast.walk(n):
                    if isinstance(s_, ast.Name):
                        names.add(s_.id)
                    elif isinstance(s_, (ast.Import, ast.ImportFrom)):
                        for a in s_.names:
                            imps |= set(self.resolve(s_, a.name))
                self.defs[n.name] = [_dump(n), sorted(names), sorted(imps)]
            else:
                top.append(n)
                if isinstance(n, (ast.Import, ast.ImportFrom)):
                    for a in n.names:
                        for m in self.resolve(n, a.name):
                            self.bound[a.asname or a.name.split('.')[0]] = m
        self.top = digest([ast.dump(n, annotate_fields=False, include_attributes=False) for n in top])
        self.imports = set()
        for n in ast.walk(tree):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    self.imports |= set(self.resolve(n, a.name))

    def data(self):
        return dict(digest=self.digest, pkg=self.pkg, defs=self.defs, bound=self.bound, top=self.top,
                    imports=sorted(self.imports))

    def resolve(self, node, alias):
        """the charkit modules an import statement brings in."""
        if isinstance(node, ast.Import):
            base = [alias]
        else:
            if node.level:
                pkg = self.pkg.split('.')
                pkg = pkg[:len(pkg) - (node.level - 1)]
                mod = '.'.join(pkg + ([node.module] if node.module else []))
            else:
                mod = node.module
            base = [mod + '.' + alias, mod]
        out = []
        for b in base:
            if _module_file(b):
                out.append(b)
                break
        if isinstance(node, ast.Import) and not out:
            parts = alias.split('.')
            out = [m for m in ('.'.join(parts[:i]) for i in range(len(parts), 0, -1)) if _module_file(m)][:1]
        return out


_DISK = [None, False]                   # the on-disk memo of parsed modules, and whether it changed


def _mod(name):
    p = _module_file(name)
    st = os.stat(p)
    k = [p, st.st_mtime_ns, st.st_size, sys.version.split()[0]]
    if _MODS.get(name, (None,))[0] != k:
        if _DISK[0] is None:
            try:
                _DISK[0] = json.load(open(os.path.join(cache_dir(), 'code.json')))
            except (OSError, ValueError):
                _DISK[0] = {}
        m = _DISK[0].get(name)
        if m and m[0] == k:
            M = _Mod(name, p, m[1])
        else:
            M = _Mod(name, p)
            _DISK[0][name] = [k, M.data()]
            _DISK[1] = True
        _MODS[name] = (k, M)
    return _MODS[name][1]


def save_code_memo():
    if _DISK[1] and _DISK[0] is not None:
        _write_json(os.path.join(cache_dir(), 'code.json'), _DISK[0])
        _DISK[1] = False


def code_units(*fns, modules=()):
    """the code the functions run, as {unit: digest}: each function and the top-level names it uses in its own module,
    function by function (with that module's other top-level statements), and every charkit module they import, whole
    and transitively; `modules` adds whole modules."""
    units, mods = {}, set(modules)
    for fn in fns:
        M = _mod(fn.__module__)
        units[M.rel + ':<top>'] = M.top
        mods |= set(M.bound.values())                  # the charkit modules its module imports at the top run with it
        todo, done = [fn.__name__], set()
        while todo:
            n = todo.pop()
            if n in done or n not in M.defs:
                continue
            done.add(n)
            dg, names, imps = M.defs[n]
            units['%s:%s' % (M.rel, n)] = dg
            todo += names
            mods |= set(imps) | {M.bound[x] for x in names if x in M.bound}
    seen = set()
    while mods:
        m = mods.pop()
        if m in seen:
            continue
        seen.add(m)
        P = _mod(m)
        units[P.rel] = P.digest
        mods |= P.imports
    save_code_memo()
    return dict(sorted(units.items()))


def env():
    bpy = _bpy()
    bh = bpy.app.build_hash if bpy else None
    return dict(python=sys.version.split()[0], numpy=np.__version__, blender=bpy.app.version_string if bpy else None,
                build=bh.decode() if isinstance(bh, bytes) else bh)


# -------------------------------------------------------------------------------------------------------------- tracking
_REC = None                             # the running step's recorder
_CUR = None                             # the build's Cache (its `wrote`: files written during the build)


class TrackedDict(dict):
    """a dict that tells the running step's recorder which keys it reads and writes (outside a step it is a plain dict).
    The Scene's dict trees become these after each stage (adopt), the spec at the top level, and shade.MATS."""
    __slots__ = ('_path',)

    def __init__(self, d=(), path=()):
        dict.__init__(self, d)
        self._path = path

    def __reduce_ex__(self, proto):
        self._all()                                         # a copy or a pickle reads it all
        return (dict, (), None, None, iter(dict.items(self)))

    def _r(self, k, v):
        r = _REC
        if r is not None and not r.paused:
            r.read(self._path + (k,), v)
        return v

    def _all(self):
        r = _REC
        if r is not None and not r.paused:
            r.read(self._path + (ALL,), self)

    def _w(self, k):
        r = _REC
        if r is not None and not r.paused:
            r.write(self._path + (k,))

    def __getitem__(self, k):
        try:
            v = dict.__getitem__(self, k)
        except KeyError:
            self._r(k, ABSENT)
            raise
        return self._r(k, v)

    def get(self, k, d=None):
        v = self._r(k, dict.get(self, k, ABSENT))
        return d if v is ABSENT else v

    def __contains__(self, k):
        has = dict.__contains__(self, k)
        r = _REC
        if r is not None and not r.paused:
            r.read(self._path + (k, HAS), has)
        return has

    def setdefault(self, k, d=None):
        if dict.__contains__(self, k):
            return self[k]
        self._w(k)
        return dict.setdefault(self, k, d)

    def __setitem__(self, k, v):
        self._w(k); dict.__setitem__(self, k, v)

    def __delitem__(self, k):
        self._w(k); dict.__delitem__(self, k)

    def pop(self, k, *d):
        self._w(k); return dict.pop(self, k, *d)

    def popitem(self):
        self._all(); self._w(ALL); return dict.popitem(self)

    def update(self, *a, **kw):
        for k in dict(*a, **kw):
            self._w(k)
        dict.update(self, *a, **kw)

    def clear(self):
        self._w(ALL); dict.clear(self)

    def __iter__(self):
        self._all(); return dict.__iter__(self)

    def __len__(self):
        self._all(); return dict.__len__(self)

    def keys(self):
        self._all(); return dict.keys(self)

    def values(self):
        self._all(); return dict.values(self)

    def items(self):
        self._all(); return dict.items(self)

    def copy(self):
        self._all(); return dict(dict.items(self))

    def __eq__(self, o):
        self._all(); return dict.__eq__(self, o)

    def __ne__(self, o):
        self._all(); return dict.__ne__(self, o)

    def __or__(self, o):
        self._all(); return dict.__or__(self, o)

    def __ior__(self, o):
        self._all(); self._w(ALL); return dict.__ior__(self, o)

    def __repr__(self):
        return dict.__repr__(self)

    __hash__ = None


def track(d, path, seen=None):
    """d as a TrackedDict under `path`, and the dicts in it too, all the way down (a dict met twice is converted once, under
    its first path; dicts inside lists stay plain: the list is read whole)."""
    seen = {} if seen is None else seen
    if id(d) in seen:
        return seen[id(d)]
    t = d if isinstance(d, TrackedDict) else TrackedDict(d, path)
    seen[id(d)] = t
    for k, v in dict.items(t):
        if isinstance(v, dict):
            c = track(v, path + (k,), seen)
            if c is not v:
                dict.__setitem__(t, k, c)
    return t


def adopt(S, names=None):
    """make the dict trees under the Scene's attributes TrackedDicts (the spec's under 'spec')."""
    seen = {}
    for k in list(vars(S)) if names is None else names:
        v = vars(S).get(k)
        if isinstance(v, dict):
            c = track(v, ('spec',) if k == 'spec' else ('S', k), seen)
            if c is not v:
                setattr(S, k, c)


def readable(path):
    """('S', 'character', 'data', 'verts') -> 'character.data.verts'."""
    p = list(path[1:] if path[0] == 'S' else path)
    s = '.'.join(str(k) for k in p if k not in (ALL, HAS))
    return s + ('[*]' if p and p[-1] == ALL else '?' if p and p[-1] == HAS else '')


def _dep_name(path):
    return '.'.join(str(k) for k in (path[1:] if path[0] == 'S' else path) if k not in (ALL, HAS))


class Scoped:
    """the Scene as a stage sees it: attribute reads recorded (properties run against this view, so their own reads
    count), writes passed through."""
    __slots__ = ('_S', '_rec')

    def __init__(self, S, rec):
        object.__setattr__(self, '_S', S); object.__setattr__(self, '_rec', rec)

    def __getattr__(self, k):
        S = object.__getattribute__(self, '_S')
        rec = object.__getattribute__(self, '_rec')
        prop = getattr(type(S), k, None)
        if isinstance(prop, property):
            return prop.fget(self)
        try:
            v = getattr(S, k)
        except AttributeError:
            rec.read(('S', k), ABSENT)
            raise
        if not isinstance(v, TrackedDict) and _REC is rec and not rec.paused:
            rec.read(('S', k), v)
        return v

    def __setattr__(self, k, v):
        object.__getattribute__(self, '_rec').write(('S', k))
        setattr(object.__getattribute__(self, '_S'), k, v)

    def __delattr__(self, k):
        object.__getattribute__(self, '_rec').write(('S', k))
        delattr(object.__getattribute__(self, '_S'), k)


class Recorder:
    """one step's reads (path -> digest at the first read), writes, files opened, and the earlier objects it reached."""

    def __init__(self, cache, step, deps, S, default=None):
        self.cache, self.step, self.deps, self.S = cache, step, deps or {}, S
        self.default = default           # the facet objects are keyed on ('render' for QA parts)
        self.reads, self.writes, self.values = {}, set(), {}
        self.files, self.wrote = set(), set()
        self.touched, self.errors = {}, []
        self.paused = 0
        self.w0 = None                   # the world before the step (pointers of what existed)
        self.files_only = False          # a product's recorder: files only (its scene is keyed whole)

    def facet(self, path, v):
        """the value a read is keyed on: the declared part (scene.DEPS), or the whole."""
        dep = self.deps.get(_dep_name(path))
        if dep is None or path[-1] in (ALL, HAS):
            return v, self.default
        if callable(dep):
            return dep(v, self.S), None
        return v, dep

    def written(self, path):
        return any(path[:i] in self.writes for i in range(2, len(path) + 1)) or (path[0], ALL) in self.writes

    def read(self, path, v):
        if self.paused or self.files_only or path in self.reads or self.written(path) or \
                isinstance(v, TrackedDict) and path[-1] != ALL:
            return                                          # (a tracked dict records the reads inside it itself)
        self.paused += 1
        try:
            fv, facet = self.facet(path, v)
            self.reads[path] = digest(fv, facet)
            if isinstance(fv, np.ndarray) and fv.dtype.kind in 'fiu' and fv.nbytes <= 1 << 20:
                self.values[path] = fv.copy()
            elif isinstance(fv, tuple) and fv and isinstance(fv[-1], np.ndarray) and fv[-1].nbytes <= 1 << 20:
                self.values[path] = fv[-1].copy()
            if self.w0 is not None:
                for ob in _objects_in(v):
                    if (ob.as_pointer() not in self.touched and ('objects', ob.as_pointer()) in self.w0['ids']):
                        self.touched[ob.as_pointer()] = (ob.name, ob_parts(ob, full=True))
        except Uncacheable as e:
            self.errors.append('reads %s: %s' % (readable(path), e))
        except Exception as e:                                      # a read that can't be keyed never hits
            self.errors.append('reads %s: %s: %s' % (readable(path), type(e).__name__, e))
        finally:
            self.paused -= 1

    def write(self, path):
        if not self.files_only and not self.paused:
            self.writes.add(path)

    def opened(self, p, write):
        if write:
            self.wrote.add(p)
        elif p not in self.wrote and self.cache.watch(p):
            self.files.add(p)


def _objects_in(v, depth=0):
    """the Blender objects in a value (in small lists and dicts, a few levels down: where the Scene keeps them)."""
    bpy = _bpy()
    if bpy is None:
        return
    if isinstance(v, bpy.types.Object):
        yield v
    elif depth < 3 and isinstance(v, (list, tuple)) and len(v) <= 64:
        for e in v:
            yield from _objects_in(e, depth + 1)
    elif depth < 3 and isinstance(v, dict) and len(v) <= 64:
        for e in dict.values(v):
            yield from _objects_in(e, depth + 1)


def _audit(event, args):
    if event != 'open':
        return
    r, c = _REC, _CUR
    if (r is None or r.paused) and c is None:
        return
    try:
        path, mode, flags = args
        if path is None or isinstance(path, int):
            return
        write = bool((flags or 0) & (os.O_WRONLY | os.O_RDWR | os.O_CREAT)) if mode is None else \
            any(ch in mode for ch in 'wax+')
        p = os.path.abspath(os.fsdecode(path))
        if write and c is not None:
            c.wrote.add(p)
        if r is not None and not r.paused:
            r.paused += 1
            try:
                r.opened(p, write)
            finally:
                r.paused -= 1
    except Exception:
        pass


def _hook():
    """one audit hook per process (a worker imports this module afresh per job), calling this module's _audit."""
    box = getattr(sys, '_charkit_audit', None)
    if box is None:
        box = [None]
        sys._charkit_audit = box
        sys.addaudithook(lambda e, a: box[0] is not None and box[0](e, a))
    box[0] = _audit


# ------------------------------------------------------------------------------------------------------------- pickling
_PLAIN = frozenset((int, float, str, bool, type(None), tuple, list, dict, bytes, np.ndarray, np.float64, np.int64,
                    np.float32, np.int32, set, frozenset))


class _Pickler(pickle.Pickler):
    def __init__(self, f, ids):
        super().__init__(f, protocol=pickle.HIGHEST_PROTOCOL)
        self.ids = ids

    def persistent_id(self, x):
        if type(x) in _PLAIN:
            return None
        if _is_id(x):
            self.ids[(COLL.get(x.id_type), x.as_pointer())] = x
            return ('ID', x.id_type, x.name)
        mu = _mathutils(x)
        if mu is not None:
            return ('MU', type(x).__name__, mu)
        bpy = _bpy()
        if bpy is not None and isinstance(x, bpy.types.bpy_struct):
            raise Uncacheable('keeps a %s' % type(x).__name__)
        return None

    def reducer_override(self, x):
        if type(x) is TrackedDict:
            return (dict, (), None, None, iter(dict.items(x)))
        return NotImplemented


class _Unpickler(pickle.Unpickler):
    def persistent_load(self, pid):
        if pid[0] == 'ID':
            coll = getattr(_bpy().data, COLL[pid[1]])
            if pid[2] not in coll:
                raise RestoreError('%s %s is missing' % (pid[1].lower(), pid[2]))
            return coll[pid[2]]
        if pid[0] == 'MU':
            import mathutils
            return getattr(mathutils, pid[1])(pid[2])
        raise pickle.UnpicklingError(pid)


def _dumps(x, ids):
    import io
    f = io.BytesIO()
    try:
        _Pickler(f, ids).dump(x)
    except (pickle.PicklingError, TypeError, AttributeError, ReferenceError) as e:
        raise Uncacheable('state: %s' % e)
    return f.getvalue()


# ----------------------------------------------------------------------------------------------------------------- store
def _write_json(path, x):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = '%s.%d.tmp' % (path, os.getpid())
    with open(tmp, 'w') as f:
        json.dump(x, f, indent=0, default=_json_default)
    os.replace(tmp, path)


def _json_default(x):
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, np.ndarray):
        return x.tolist()
    return str(x)


def _jpath(path):
    return [k if isinstance(k, (str, int, float, bool)) else ['repr', repr(k)] for k in path]


def _tpath(j):
    return tuple(k if not isinstance(k, list) else k[1] for k in j)


class Entry:
    def __init__(self, d):
        self.dir = d
        self.id = os.path.basename(d)
        self.m = json.load(open(os.path.join(d, 'manifest.json')))

    def file(self, name):
        return os.path.join(self.dir, name)


def _entries(d):
    """the entries under a key folder, the most recently used first."""
    out = []
    if os.path.isdir(d):
        for e in os.listdir(d):
            p = os.path.join(d, e, 'manifest.json')
            if os.path.exists(p):
                out.append((os.path.getmtime(p), os.path.join(d, e)))
    return [p for _, p in sorted(out, reverse=True)]


def _resolve(path, S):
    """the current value at a recorded read path (ABSENT where it no longer exists)."""
    from . import shade
    root = path[0]
    if root == 'S':
        v, rest = getattr(S, path[1], ABSENT), path[2:]
    elif root == 'spec':
        v, rest = S.spec, path[1:]
    elif root == 'MATS':
        v, rest = shade.MATS, path[1:]
    else:
        raise KeyError(root)
    for i, k in enumerate(rest):
        if k == ALL:
            return v
        if i + 1 < len(rest) and rest[i + 1] == HAS:
            return isinstance(v, dict) and dict.__contains__(v, k)
        v = dict.get(v, k, ABSENT) if isinstance(v, dict) else ABSENT
    return v


class Cache:
    """one build's use of the cache: `stage` runs or restores a scene stage, `spec_step` the spec-only cranium fit,
    `product` a build product; each step's entry id joins `chain`, which keys the products on the whole scene."""

    def __init__(self, mode='on', name='build', out=None, t0=None):
        if mode not in MODES:
            raise ValueError('cache mode %r (one of %s)' % (mode, ', '.join(MODES)))
        self.mode, self.name = mode, name
        self.out = os.path.abspath(out) if out else None
        self.dir = cache_dir()
        os.makedirs(self.dir, exist_ok=True)
        self.files = Files(self.dir)
        self.env = env()
        self.chain = []                  # (step, entry id or None)
        self.ran = []                    # the steps that ran (misses)
        self.stale = []
        try:
            self.last = json.load(open(os.path.join(self.dir, 'last', name + '.json')))
        except (OSError, ValueError):
            self.last = {}
        self.now = {}
        self.skip = _skip_prefixes() + (os.path.abspath(self.dir).rstrip(os.sep) + os.sep,)
        self.kit_out = os.path.join(KIT, 'out') + os.sep
        self.wrote = set()               # files written during this build: outputs, not inputs
        self._assets = None
        self.spec = None                 # the build's spec, for the products (set once the scene is built)
        self.t0 = t0 or time.time()      # when this build's code was loaded
        self._edited = None
        global _CUR
        _CUR = self
        from . import shade
        if not isinstance(shade.MATS, TrackedDict):          # charkit's material registry: its reads count too
            shade.MATS = TrackedDict(shade.MATS, ('MATS',))
        _hook()

    # --------------------------------------------------------------------------------------------------- keys
    def edited(self):
        """a charkit source file changed since this build loaded its code? Its entries would be keyed on code it didn't
        run (the keys read the files on disk), so it stores none from then on."""
        if not self._edited:
            for d, dirs, files in os.walk(KIT):
                dirs[:] = [x for x in dirs if x not in ('out', '__pycache__', 'tests')]
                for f in files:
                    if f.endswith('.py') and os.stat(os.path.join(d, f)).st_mtime > self.t0:
                        self._edited = os.path.relpath(os.path.join(d, f), ROOT)
                        break
                if self._edited:
                    break
        return self._edited

    def watch(self, p):
        """is an opened file an input to key on (not the kit's own code and data, Python's or Blender's, nor a file this
        build wrote)? The output folder's own inputs (out/geom/hair.npz, cut before Blender) count."""
        if p.endswith(('.py', '.pyc', '.pyo', '.so', '.dylib')) or p.startswith(self.skip) or p in self.wrote:
            return False
        return not p.startswith(KIT + os.sep) or p.startswith(self.kit_out)

    def assets(self):
        if self._assets is None:
            self._assets = self.files.get(os.path.join(KIT, 'assets'))
        return self._assets

    def static(self, kind, name, fns, extra=None):
        units = code_units(*fns, modules=('charkit.cache',))
        units['charkit/assets'] = self.assets()
        units = dict(sorted(units.items()))
        return digest([SCHEMA, kind, name, units, self.env, extra]), units

    def fkey(self, p):
        """a file read's key: ('out', relative path) under this build's output folder (read afresh from the current
        build's), else ('file', absolute path)."""
        if self.out and p.startswith(self.out + os.sep):
            return ('out', os.path.relpath(p, self.out))
        return ('file', p)

    def fpath(self, k):
        return os.path.join(self.out, k[1]) if k[0] == 'out' else k[1]

    def current(self, path, S, deps, memo, default=None):
        """the digest a recorded read has now."""
        if path in memo:
            return memo[path]
        if path[0] in ('file', 'out'):
            h = self.files.get(self.fpath(path), fresh=path[0] == 'out')
        else:
            rec = Recorder(self, None, deps, S, default)
            rec.paused = 1
            v = _resolve(path, S)
            fv, facet = rec.facet(path, v)
            h = digest(fv, facet)
        memo[path] = h
        return h

    def lookup(self, kind, name, static, units, S, deps, default=None):
        """-> (the first entry whose reads all match, or None; why not)."""
        d = os.path.join(self.dir, kind, name, static[:20])
        cands = _entries(d)
        if not cands:
            return None, self.why_static(name, units)
        memo, first = {}, None
        prev = (self.last.get(name) or {}).get('entry')
        for c in sorted(cands, key=lambda c: os.path.basename(c) != prev):
            try:
                E = Entry(c)
                bad = []
                for jp, h in E.m['reads']:
                    p = _tpath(jp)
                    try:
                        if self.current(p, S, deps, memo, default) != h:
                            bad.append(p)
                    except Exception as e:
                        bad.append(p)
                    if bad and first is not None:
                        break
                if not bad:
                    return E, None
                if first is None:
                    first = (E, bad)
            except (OSError, ValueError, KeyError):
                continue
        if first is None:
            return None, 'no usable entry'
        return None, self.why_reads(first[0], first[1], S, deps, default)

    def why_static(self, name, units):
        L = self.last.get(name)
        if not L:
            return 'no entry'
        ch = [u for u in sorted(set(L['units']) | set(units)) if L['units'].get(u) != units.get(u)]
        if ch:
            ch = [u[:-6] if u.endswith(':<top>') else u for u in ch]
            return 'code ' + ', '.join(ch[:3]) + (' +%d more' % (len(ch) - 3) if len(ch) > 3 else '')
        if L.get('env') != self.env:
            return 'env ' + ', '.join('%s %s -> %s' % (k, L['env'].get(k), v) for k, v in self.env.items()
                                      if L['env'].get(k) != v)
        return 'no entry for this code'

    def why_reads(self, E, bad, S, deps, default=None):
        vals = {}
        p = E.file('inputs.npz')
        if os.path.exists(p):
            with np.load(p) as z:
                idx = {k: 'v%d' % i for i, k in enumerate(json.loads(str(z['_index'])))} if '_index' in z.files else {}
                for tp in bad:
                    k = idx.get(json.dumps(_jpath(tp)))
                    if k is not None:
                        vals[tp] = z[k]
        out = []
        for tp in bad[:4]:
            if tp[0] in ('file', 'out'):
                out.append('file ' + (os.path.join('OUT', tp[1]) if tp[0] == 'out' else os.path.relpath(tp[1], ROOT)))
                continue
            txt = readable(tp)
            if tp in vals:
                try:
                    rec = Recorder(self, None, deps, S, default)
                    rec.paused = 1
                    fv, _ = rec.facet(tp, _resolve(tp, S))
                    cur = fv[-1] if isinstance(fv, tuple) else fv
                    if isinstance(cur, np.ndarray) and cur.shape == vals[tp].shape and cur.size:
                        mv = float(np.max(np.abs(cur.astype(float) - vals[tp].astype(float))))
                        if mv > 0:
                            txt += ' moved %.2g' % mv
                except Exception:
                    pass
            out.append(txt + ('' if 'moved' in txt else ' changed'))
        if len(bad) > 4:
            out.append('+%d more' % (len(bad) - 4))
        return '; '.join(out)

    # --------------------------------------------------------------------------------------------------- steps
    def stage(self, name, fn, S, deps=None):
        """run or restore one scene stage, inside its trace record."""
        from . import trace
        static, units = self.static('stages', name, [fn] + [d for d in (deps or {}).values() if callable(d)],
                                    extra=sorted((k, v if isinstance(v, str) else v.__name__) for k, v in (deps or {}).items()))
        E, info, run = None, {}, None
        with trace.stage(name, S) as extra:
            if self.mode in ('on', 'verify', 'stages'):
                E, why = self.lookup('stages', name, static, units, S, deps)
            else:
                why = 'cache %s' % self.mode
            if E is not None and self.mode in ('on', 'stages'):
                t = time.perf_counter()
                try:
                    self.restore(E, S)
                except RestoreError as e:
                    e.entry = E.dir
                    e.args = ('stage %s: %s' % (name, e.args[0] if e.args else ''),)
                    raise
                adopt(S)
                trace.seed_health({**E.m['trace'].get('added', {}), **E.m['trace'].get('changed', {})})
                # a restore appends its own objects and replays its changes on the ones it names: the rest stand as the
                # trace last measured them
                touched = set(E.m['trace'].get('added', {})) | set(E.m['trace'].get('changed', {})) | \
                    set(E.m.get('modified', []))
                extra['_reuse'] = {o.name for o in _bpy().context.scene.objects if o.name not in touched}
                info = {'hit': True, 'key': E.id[:12], 'restore_s': round(time.perf_counter() - t, 3)}
            else:
                run = self.run(name, fn, S, deps, blender=True)
                adopt(S)
                info = {'hit': False, 'why': why or 'miss', 'overhead': {k: round(v, 3) for k, v in run.t.items()}}
                if E is not None:
                    info['would_hit'] = E.id[:12]
            extra['cache'] = info
        rec = trace.last()
        if info.get('hit'):
            bad = _record_diff(E.m['trace'], _norm(rec))
            if bad:
                err = RestoreError('stage %s restored differently from its entry: %s' % (name, '; '.join(bad[:4])))
                err.entry = E.dir
                raise err
            os.utime(E.file('manifest.json'))
            self.chain.append((name, E.id))
            self.now[name] = dict(static=static, units=units, env=self.env, entry=E.id)
            return
        self.finish_run('stages', name, static, units, run, S, deps, rec, E, info)

    def spec_step(self, name, fn, spec, *args):
        """a step that only changes the spec (the cranium fit, fn(spec, *args)): run or restored inside a trace span.
        -> the spec (a TrackedDict: the stages' spec reads are recorded)."""
        from . import trace
        holder = types.SimpleNamespace(spec=track(spec, ('spec',)))
        static, units = self.static('stages', name, [fn], extra=[os.path.relpath(a, ROOT) if isinstance(a, str) and
                                                                  os.path.isabs(a) else a for a in args])
        with trace.span(name) as extra:
            E, why = (self.lookup('stages', name, static, units, holder, None) if self.mode in ('on', 'verify', 'stages')
                      else (None, 'cache %s' % self.mode))
            if E is not None and self.mode in ('on', 'stages'):
                t = time.perf_counter()
                st = self.load_state(E)
                _apply(holder, st['spec'])
                track(holder.spec, ('spec',))
                trace.replay(st['notes'], cached=True)
                extra['cache'] = {'hit': True, 'key': E.id[:12], 'restore_s': round(time.perf_counter() - t, 3)}
                self.chain.append((name, E.id))
                self.now[name] = dict(static=static, units=units, env=self.env, entry=E.id)
                os.utime(E.file('manifest.json'))
                return holder.spec
            run = self.run(name, lambda S: fn(S.spec, *args), holder, None, blender=False)
            info = {'hit': False, 'why': why or 'miss'}
            if E is not None:
                info['would_hit'] = E.id[:12]
            self.finish_run('stages', name, static, units, run, holder, None, None, E, info)
            extra['cache'] = info
        return holder.spec

    def run(self, name, fn, S, deps, blender=True):
        """run a step with its reads recorded; -> the recorder, with what it changed."""
        from . import shade, trace
        global _REC
        rec = Recorder(self, name, deps, S)
        T = rec.t = {}
        t0 = time.perf_counter()
        mats0 = None
        if blender:
            rec.w0 = world()
            mats0 = dict(dict.items(shade.MATS))
        T['world0'] = time.perf_counter() - t0; t0 = time.perf_counter()
        import copy
        spec0 = copy.deepcopy(S.spec)                        # (plain dicts: a TrackedDict copies as one)
        attrs0 = dict(vars(S))
        _REC = rec
        try:
            with trace.capture() as got:
                fn(Scoped(S, rec))
        finally:
            _REC = None
        T['run'] = time.perf_counter() - t0; t0 = time.perf_counter()
        rec.notes = [{k: v for k, v in r.items() if k != 't'} for r in got if r['event'] == 'note']
        rec.paused = 1
        # what it changed: the Scene's attributes, and key by key the entries it wrote in the spec and in dicts that were
        # there before (a restore sets those keys, and only those: a knob it never read keeps the value it has now)
        rec.attrs = {k: v for k, v in vars(S).items() if k != 'spec' and (k not in attrs0 or attrs0[k] is not v)}
        rec.attrs.update({k: ABSENT for k in attrs0 if k not in vars(S)})
        rec.spec, rec.dict_writes = {}, {}
        for p in sorted(rec.writes, key=len):
            if p[0] == 'S' and (len(p) <= 2 or p[1] in rec.attrs) or p[0] == 'MATS':
                continue
            if p[-1] == ALL:
                rec.errors.append('clears %s' % readable(p))
                continue
            parent = _resolve(p[:-1], S)
            (rec.spec if p[0] == 'spec' else rec.dict_writes)[p] = \
                dict.get(parent, p[-1], ABSENT) if isinstance(parent, dict) else ABSENT
        check = types.SimpleNamespace(spec=spec0)
        try:
            _apply(check, rec.spec)
            if digest(check.spec) != digest(S.spec):
                rec.errors.append('changes the spec other than key by key')
        except RestoreError as e:
            rec.errors.append('changes the spec: %s' % e)
        # a value it read and then changed in place is an input and an output at once
        for p, h in rec.reads.items():
            if p[-1] in (ALL, HAS) or p in rec.dict_writes or p in rec.spec or rec.written(p) or \
                    p[0] == 'S' and p[1] in rec.attrs:
                continue
            v = _resolve(p, S)
            if isinstance(v, (np.ndarray, list, dict)) or hasattr(v, '__dict__') and not _is_id(v):
                try:
                    fv, facet = rec.facet(p, v)
                    if digest(fv, facet) != h:
                        rec.errors.append('changes %s in place' % readable(p))
                except Exception as e:
                    rec.errors.append('re-reads %s: %s' % (readable(p), e))
        T['recheck'] = time.perf_counter() - t0; t0 = time.perf_counter()
        if blender:
            self.blender_delta(rec, mats0)
        T['delta'] = time.perf_counter() - t0
        return rec

    def blender_delta(self, rec, mats0):
        """what a stage did in Blender: the datablocks it made, its shade.MATS entries, and its changes to what existed."""
        from . import shade
        bpy = _bpy()
        w0, w1 = rec.w0, world(rec.w0)
        rec.new = {k: v for k, v in w1['ids'].items() if k not in w0['ids']}
        gone = [k for k in w0['ids'] if k not in w1['ids']]
        if gone:
            rec.errors.append('removes %d datablocks made before it' % len(gone))
        rec.mats = {k: m for k, m in dict.items(shade.MATS) if mats0.get(k) is not m}
        if any(k not in dict.keys(shade.MATS) for k in mats0):
            rec.errors.append('drops shade.MATS entries')
        for p, d0 in w0['mats'].items():
            if w1['mats'].get(p) not in (None, d0):
                rec.errors.append('changes material %s' % w0['ids'][('materials', p)].name)
        for p, d0 in w0['imgs'].items():
            if w1['imgs'].get(p) not in (None, d0):
                rec.errors.append('changes image %s' % w0['ids'][('images', p)].name)
        # earlier objects: those it read (full state compared) and the rest (their structure)
        rec.modified = {}
        for p, parts0 in w0['obs'].items():
            ob = w0['ids'][('objects', p)]
            if p in rec.touched:
                continue
            if w1['obs'].get(p) != parts0:
                rec.errors.append('changes %s, which it reached other than through the Scene' % ob.name)
        for p, (nm, parts0) in rec.touched.items():
            ob = w1['ids'].get(('objects', p))
            if ob is None:
                continue
            try:
                parts1 = ob_parts(ob, full=True)
                d = _ob_delta(ob, parts0, parts1)
            except Uncacheable as e:
                rec.errors.append('changes %s: %s' % (nm, e))
                continue
            if d:
                rec.modified[nm] = d
        s0, s1 = w0['scene'], w1['scene']
        for k in s0:
            if k != 'active' and s0[k] != s1[k]:
                rec.errors.append('changes the scene\'s %s' % k)
        rec.active = s1['active'] if s1['active'] != s0['active'] else ABSENT
        newobs = [i for (c, _), i in rec.new.items() if c == 'objects']
        rec.selected = sorted(o.name for o in newobs if o.select_get())
        for o in newobs:
            if any(c != bpy.context.scene.collection for c in o.users_collection):
                rec.errors.append('links %s outside the scene\'s own collection' % o.name)
        bad = sorted({c for (c, _) in rec.new if c not in WRITABLE and c != 'shape_keys'})
        if bad:
            rec.errors.append('makes %s' % ', '.join(bad))

    def finish_run(self, kind, name, static, units, run, S, deps, trace_rec, E, info):
        """after a step ran: its checks against the trace, then its entry stored (or why not); verify mode compares."""
        errors = list(run.errors)
        if trace_rec is not None:
            ch = set(trace_rec.get('changed', {})) | set(trace_rec.get('removed', []))
            mod = set(getattr(run, 'modified', {}))
            extra_ch = sorted(n for n in ch if n not in mod)
            if extra_ch:
                errors.append('the trace saw it change %s' % ', '.join(extra_ch[:3]))
        run.files |= {p for jp in run.reads if jp[0] == 'spec' for p in spec_paths(_resolve(jp, S))}
        reads = {p: h for p, h in run.reads.items()}
        for p in sorted(run.files):
            reads[self.fkey(p)] = self.files.get(p, fresh=True)
        key = digest([static, sorted((json.dumps(_jpath(p)), h) for p, h in reads.items())])[:24]
        state = None
        if self.edited():
            errors.append('%s changed during the build' % self.edited())
        if not errors:
            try:
                state = self.store(kind, name, static, units, run, reads, key, trace_rec)
            except Uncacheable as e:
                errors.append(str(e))
        self.ran.append(name)
        if errors:
            info['stored'] = False
            info['uncacheable'] = errors[0] if len(errors) == 1 else '%s (+%d more)' % (errors[0], len(errors) - 1)
            print('CHARKIT_CACHE_UNCACHEABLE %s: %s' % (name, '; '.join(errors)))
            self.chain.append((name, None))
        else:
            self.chain.append((name, key))
        self.now[name] = dict(static=static, units=units, env=self.env, entry=key if not errors else None)
        if self.mode == 'verify' and E is not None:
            bad = []
            if trace_rec is not None:
                bad += _record_diff(E.m['trace'], _norm(trace_rec))
            if state is not None:
                try:
                    if _state_digest(self.load_state(E)) != _state_digest(state):
                        bad.append('its Python state differs')
                except RestoreError as e:
                    bad.append('its stored state does not load: %s' % e)
            mine = {json.dumps(_jpath(p)): h for p, h in reads.items()}
            theirs = {json.dumps(j): h for j, h in E.m['reads']}
            odd = sorted(k for k in set(mine) | set(theirs) if mine.get(k) != theirs.get(k))
            if odd:
                bad.append('it read differently: %s' % ', '.join(readable(_tpath(json.loads(k))) for k in odd[:4]))
            info['verified'] = not bad
            if bad:
                info['stale'] = bad[:6]
                self.stale.append((name, bad))
                print('CHARKIT_CACHE_STALE %s: %s' % (name, '; '.join(bad[:6])))

    def store(self, kind, name, static, units, run, reads, key, trace_rec):
        """write a step's entry (atomically). -> the digest of its Python state."""
        bpy = _bpy()
        final = os.path.join(self.dir, kind, name, static[:20], key)
        state = dict(attrs=run.attrs, spec=run.spec, writes=getattr(run, 'dict_writes', {}),
                     mats=getattr(run, 'mats', {}), notes=run.notes, modified=getattr(run, 'modified', {}),
                     active=getattr(run, 'active', ABSENT), selected=getattr(run, 'selected', []))
        ids = {}
        blob = _dumps(state, ids)
        if os.path.exists(final):
            return state
        tmp = tempfile.mkdtemp(prefix='.w-', dir=self.dir)
        try:
            M = dict(schema=SCHEMA, kind=kind, step=name, static=static, id=key, units=units, env=self.env,
                     reads=[[_jpath(p), h] for p, h in sorted(reads.items(), key=lambda kv: json.dumps(_jpath(kv[0])))],
                     created=time.strftime('%Y-%m-%dT%H:%M:%S'), spec_name=self.name,
                     modified=sorted(getattr(run, 'modified', {})),
                     trace=_norm({k: trace_rec.get(k) for k in ('added', 'changed', 'removed', 'objects')}) if trace_rec else {})
            if getattr(run, 'new', None) is not None:
                new = dict(run.new)
                # what the state names that the stage made must travel even with no other user (a shade.MATS material)
                for k, i in ids.items():
                    if k in run.w0['ids']:
                        continue
                    new[k] = i
                keep = {k: i for k, i in new.items() if k[0] in WRITABLE and (i.users > 0 or k in ids)}
                M['new'] = {}
                for (c, _), i in sorted(keep.items(), key=lambda kv: (kv[0][0], kv[1].name)):
                    M['new'].setdefault(c, []).append(i.name)
                M['fake'] = sorted(i.name for i in keep.values() if i.use_fake_user)
                M['orphans'] = sorted('%s/%s' % (c, i.name) for (c, _), i in new.items() if (c, _) not in keep)
                sc = bpy.context.scene
                M['link'] = [o.name for o in sc.collection.objects if ('objects', o.as_pointer()) in keep]
                if keep:
                    blend = os.path.join(tmp, 'data.blend')
                    bpy.data.libraries.write(blend, set(keep.values()), fake_user=True, compress=False)
                    with bpy.data.libraries.load(blend) as (src, _):
                        M['library'] = {c: list(getattr(src, c)) for c in WRITABLE if hasattr(src, c) and len(getattr(src, c))}
                # a packed 8-bit image comes back bit for bit (PNG); float and unpacked ones travel as their pixels
                imgs = {i.name: i for (c, _), i in keep.items() if c == 'images'}
                fl = {n: _pixels(i) for n, i in imgs.items() if i.is_float or i.packed_file is None}
                M['images'] = sorted(fl)
                if fl:
                    np.savez(os.path.join(tmp, 'images.npz'), **fl)
            with open(os.path.join(tmp, 'state.pkl'), 'wb') as f:
                f.write(blob)
            vals = {json.dumps(_jpath(p)): v for p, v in getattr(run, 'values', {}).items()}
            if vals:
                arrs = {'v%d' % i: v for i, v in enumerate(vals.values())}
                arrs['_index'] = np.array(json.dumps(list(vals)))
                np.savez(os.path.join(tmp, 'inputs.npz'), **arrs)
            _write_json(os.path.join(tmp, 'manifest.json'), M)
            os.makedirs(os.path.dirname(final), exist_ok=True)
            try:
                os.rename(tmp, final)
            except OSError:
                shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        return state

    def load_state(self, E):
        with open(E.file('state.pkl'), 'rb') as f:
            try:
                return _Unpickler(f).load()
            except RestoreError:
                raise
            except Exception as e:
                raise RestoreError('state: %s: %s' % (type(e).__name__, e))

    def restore(self, E, S):
        """put a stage's checkpoint into the scene and the Scene: its datablocks appended (what they point at re-bound to
        the scene's own), its state set, its changes to earlier objects replayed."""
        from . import shade, trace
        bpy = _bpy()
        M = E.m
        try:
            if M.get('library'):
                before = set(datablocks())
                with bpy.data.libraries.load(E.file('data.blend'), link=False) as (src, dst):
                    for c, names in M['library'].items():
                        setattr(dst, c, list(names))
                newset = {c: set(n) for c, n in M.get('new', {}).items()}
                got, dups = {}, []
                for c, names in M['library'].items():
                    for n, i in zip(names, getattr(dst, c)):
                        if i is None:
                            raise RestoreError('%s %s did not load' % (c, n))
                        if n in newset.get(c, ()):
                            if i.name != n:
                                raise RestoreError('%s %s came back as %s' % (c, n, i.name))
                            got[(c, n)] = i
                        else:
                            coll = getattr(bpy.data, c)
                            cur = coll.get(n)
                            if cur is None or cur == i:
                                raise RestoreError('%s %s, which it points at, is not in the scene' % (c, n))
                            dups.append((i, cur, c))
                for i, cur, c in dups:
                    i.user_remap(cur)
                for i, cur, c in sorted(dups, key=lambda d: d[2] != 'objects'):
                    getattr(bpy.data, c).remove(i)
                now = datablocks()
                extra = sorted('%s/%s' % (k[0], i.name) for k, i in now.items() if k not in before and k[0] != 'shape_keys'
                               and (k[0], i.name) not in got)
                if extra:
                    raise RestoreError('the library brought what it shouldn\'t: %s' % ', '.join(extra[:4]))
                fake = set(M.get('fake', []))
                for (c, n), i in got.items():
                    if n not in fake:
                        i.use_fake_user = False
                sc = bpy.context.scene
                for n in M.get('link', []):
                    sc.collection.objects.link(bpy.data.objects[n])
                if M.get('images'):
                    with np.load(E.file('images.npz')) as fl:
                        for n in M['images']:
                            i = bpy.data.images[n]
                            px = fl[n]
                            if len(px) != i.size[0] * i.size[1] * i.channels:
                                raise RestoreError('image %s came back %s' % (n, tuple(i.size)))
                            if not np.array_equal(_pixels(i), px):
                                i.pixels.foreach_set(px)
            st = self.load_state(E)
            _apply(S, st['spec'])
            for k, v in st['attrs'].items():
                if v is ABSENT:
                    if hasattr(S, k):
                        delattr(S, k)
                else:
                    setattr(S, k, v)
            _apply(S, st['writes'])
            for k, m in st['mats'].items():
                dict.__setitem__(shade.MATS, k, m)
            for n, d in st['modified'].items():
                ob = bpy.data.objects.get(n)
                if ob is None:
                    raise RestoreError('object %s is missing' % n)
                _replay(ob, d)
            if st['active'] is not ABSENT:
                bpy.context.view_layer.objects.active = bpy.data.objects[st['active']] if st['active'] else None
            for n in st['selected']:
                bpy.data.objects[n].select_set(True)
            trace.replay(st['notes'], cached=True)
        except RestoreError:
            raise
        except Exception as e:
            raise RestoreError('%s: %s' % (type(e).__name__, e))

    # --------------------------------------------------------------------------------------------------- products
    def scene_key(self):
        return None if any(k is None for _, k in self.chain) else digest(self.chain)

    def product(self, name, run, fns, opts=None, modules=()):
        """a build product (boards, QA, a VRM): run() writes files under the output folder, trace records and stdout lines;
        restored by copying them when the scene (every stage's entry), the product's code and options, the whole spec and
        the files it read are unchanged. Products are keyed apart: each sets its own camera, render size and visibility,
        so none reads another's leftovers (boards restored and QA run agree with both run: charkit/tests)."""
        from . import trace
        sk = self.scene_key()
        spec = {k: v for k, v in dict.items(self.spec or {}) if k != '_dir'}       # _dir: the output folder
        static, units = self.static('products', name, fns, extra=[sk, opts, digest(spec)])
        units.update({u: d for m in modules for u, d in code_units(modules=(m,)).items()})
        static = digest([static, sorted(units.items())])
        t = time.perf_counter()
        holder = types.SimpleNamespace(spec=spec)
        if sk is None:
            E, why = None, 'the scene is not cached'
        elif self.mode in ('on', 'verify'):
            E, why = self.lookup('products', name, static, units, holder, None)
            L = self.last.get(name) or {}
            if E is None and L.get('scene') not in (None, sk) and why and not why.startswith('code'):
                ran = [n for n, c in self.chain if c is None or n in self.ran]
                why = 'the scene changed' + (' (%s ran)' % ', '.join(ran) if ran else '')
        else:
            E, why = None, 'cache %s' % self.mode
        self.now[name] = dict(static=static, units=units, env=self.env, scene=sk)
        if E is not None and self.mode == 'on':
            for rel in E.m['files']:
                dst = os.path.join(self.out, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(os.path.join(E.dir, 'files', rel), dst)
            trace.replay(E.m['records'], cached=True)
            for line in E.m['stdout']:
                print(line)
            os.utime(E.file('manifest.json'))
            trace.event('product', name, dt=round(time.perf_counter() - t, 4), cache={'hit': True, 'key': E.id[:12]})
            self.chain.append((name, E.id))
            self.now[name]['entry'] = E.id
            return True
        before = _tree(self.out)
        rec = Recorder(self, name, None, holder)
        rec.files_only = True
        global _REC
        lines = []
        _REC = rec
        try:
            with trace.capture() as got, _tee(lines):
                run()
        finally:
            _REC = None
        after = _tree(self.out)
        outs = sorted(k for k, v in after.items() if before.get(k) != v and not k.endswith(('.blend', '.blend1'))
                      and os.path.basename(k) not in ('trace.jsonl', '.pid.json'))
        info = {'hit': False, 'why': why or 'miss'}
        reads = {self.fkey(p): self.files.get(p, fresh=True) for p in sorted(rec.files | spec_paths(spec))}
        key = digest([static, sorted((json.dumps(_jpath(p)), h) for p, h in reads.items())])
        stdout = [l for l in lines if l.startswith('CHARKIT_')]
        if sk is not None and self.edited():
            sk, why = None, '%s changed during the build' % self.edited()
        if sk is not None and self.mode != 'off' and not os.path.exists(os.path.join(self.dir, 'products', name,
                                                                                         static[:20], key[:24])):
            tmp = tempfile.mkdtemp(prefix='.w-', dir=self.dir)
            try:
                for rel in outs:
                    d = os.path.join(tmp, 'files', rel)
                    os.makedirs(os.path.dirname(d), exist_ok=True)
                    shutil.copyfile(os.path.join(self.out, rel), d)
                M = dict(schema=SCHEMA, kind='products', step=name, static=static, id=key[:24], units=units, env=self.env,
                         reads=[[_jpath(p), h] for p, h in sorted(reads.items())], files=outs,
                         digests={rel: self.files.get(os.path.join(self.out, rel), fresh=True) for rel in outs},
                         records=[{k: v for k, v in r.items() if k != 't'} for r in got if r['event'] != 'product'],
                         stdout=stdout, created=time.strftime('%Y-%m-%dT%H:%M:%S'), spec_name=self.name)
                _write_json(os.path.join(tmp, 'manifest.json'), M)
                final = os.path.join(self.dir, 'products', name, static[:20], key[:24])
                os.makedirs(os.path.dirname(final), exist_ok=True)
                try:
                    os.rename(tmp, final)
                except OSError:
                    shutil.rmtree(tmp, ignore_errors=True)
            except Exception:
                shutil.rmtree(tmp, ignore_errors=True)
                raise
        if sk is None:
            info['stored'] = False
            info['uncacheable'] = why
        if self.mode == 'verify' and E is not None:
            bad = [rel for rel in sorted(set(E.m['files']) | set(outs))
                   if E.m['digests'].get(rel) != (self.files.get(os.path.join(self.out, rel), fresh=True) if rel in outs
                                                  else None)]
            info['verified'] = not bad
            if bad:
                info['stale'] = bad[:6]
                self.stale.append((name, bad))
                print('CHARKIT_CACHE_STALE %s: %s' % (name, ', '.join(bad[:6])))
        trace.event('product', name, dt=round(time.perf_counter() - t, 4), cache=info)
        self.chain.append((name, key[:24] if sk is not None else None))
        self.now[name]['entry'] = key[:24] if sk is not None else None
        self.ran.append(name)
        return False

    # --------------------------------------------------------------------------------------------------- QA parts
    def part(self, name, fn, S, *args):
        """a part of a product (a QA measurement: fn(S, *args)), run or restored: keyed like a stage on what it reads
        through the Scene, with objects keyed as rendered (geometry, materials and their images, the rig), and on the
        files it opens and the spec paths it reads; its return value, its Scene writes, the files it writes under the
        output folder and its trace records come back on a hit. An argument naming the output folder is keyed as such."""
        from . import trace
        t = time.perf_counter()
        key_args = [('<out>', os.path.relpath(os.path.abspath(a), self.out)) if isinstance(a, str) and self.out and
                    os.path.abspath(a).startswith(self.out) else a for a in args]
        static, units = self.static('parts', name, [fn], extra=key_args)
        adopt(S)
        E, why = (self.lookup('parts', name, static, units, S, None, 'render') if self.mode in ('on', 'verify')
                  else (None, 'cache %s' % self.mode))
        if E is not None and self.mode == 'on':
            try:
                st = self.load_state(E)
                for rel in E.m['files']:
                    dst = os.path.join(self.out, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copyfile(os.path.join(E.dir, 'files', rel), dst)
                for k, v in st['attrs'].items():
                    setattr(S, k, v)
                _apply(S, st['writes'])
                adopt(S)
                trace.replay(st['records'], cached=True)
                os.utime(E.file('manifest.json'))
                trace.event('part', name, dt=round(time.perf_counter() - t, 4), cache={'hit': True, 'key': E.id[:12]})
                return st['result']
            except (RestoreError, OSError, KeyError) as e:          # a part that doesn't restore runs (nothing to undo)
                why = 'its entry did not restore (%s)' % e
                shutil.rmtree(E.dir, ignore_errors=True)
        global _REC
        rec = Recorder(self, name, None, S, 'render')
        obs0 = {o.as_pointer(): ob_parts(o, full=False) for o in _bpy().data.objects}
        attrs0 = dict(vars(S))
        before = _tree(self.out)
        _REC = rec
        try:
            with trace.capture() as got:
                result = fn(Scoped(S, rec), *args)
        finally:
            _REC = None
        rec.paused = 1
        after = _tree(self.out)
        outs = sorted(k for k, v in after.items() if before.get(k) != v and not k.endswith(('.blend', '.blend1'))
                      and os.path.basename(k) not in ('trace.jsonl', '.pid.json'))
        attrs = {k: v for k, v in vars(S).items() if k != 'spec' and (k not in attrs0 or attrs0[k] is not v)}
        writes, errors = {}, list(rec.errors)
        for p in sorted(rec.writes, key=len):
            if p[0] != 'S' or len(p) <= 2 or p[1] in attrs:
                if p[0] != 'S':
                    errors.append('writes %s' % readable(p))
                continue
            parent = _resolve(p[:-1], S)
            writes[p] = dict.get(parent, p[-1], ABSENT) if isinstance(parent, dict) else ABSENT
        for p, h in rec.reads.items():
            if p[-1] in (ALL, HAS) or p in writes or rec.written(p) or p[0] == 'S' and p[1] in attrs:
                continue
            v = _resolve(p, S)
            if isinstance(v, (np.ndarray, list, dict)) or hasattr(v, '__dict__') and not _is_id(v):
                if digest(*rec.facet(p, v)) != h:
                    errors.append('changes %s in place' % readable(p))
        obs1 = {o.as_pointer(): o for o in _bpy().data.objects}
        for ptr, parts0 in obs0.items():
            o = obs1.get(ptr)
            if o is None or ob_parts(o, full=False) != parts0:
                errors.append('changes or removes the object %s' % (o.name if o is not None else '?'))
                break
        run_files = rec.files | {q for jp in rec.reads if jp[0] == 'spec' for q in spec_paths(_resolve(jp, S))}
        reads = dict(rec.reads)
        for q in sorted(run_files):
            reads[self.fkey(q)] = self.files.get(q, fresh=True)
        key = digest([static, sorted((json.dumps(_jpath(q)), h) for q, h in reads.items())])[:24]
        info = {'hit': False, 'why': why or 'miss'}
        state = dict(result=result, attrs=attrs, writes=writes,
                     records=[{k: v for k, v in r.items() if k != 't'} for r in got])
        final = os.path.join(self.dir, 'parts', name, static[:20], key)
        blob = None
        if self.edited():
            errors.append('%s changed during the build' % self.edited())
        if not errors:
            try:
                blob = _dumps(state, {})
            except Uncacheable as e:
                errors.append(str(e))
        if errors:
            info.update(stored=False, uncacheable='; '.join(errors[:2]))
            print('CHARKIT_CACHE_UNCACHEABLE %s: %s' % (name, '; '.join(errors)))
        elif self.mode != 'off' and not os.path.exists(final):
            tmp = tempfile.mkdtemp(prefix='.w-', dir=self.dir)
            try:
                for rel in outs:
                    d = os.path.join(tmp, 'files', rel)
                    os.makedirs(os.path.dirname(d), exist_ok=True)
                    shutil.copyfile(os.path.join(self.out, rel), d)
                open(os.path.join(tmp, 'state.pkl'), 'wb').write(blob)
                _write_json(os.path.join(tmp, 'manifest.json'), dict(
                    schema=SCHEMA, kind='parts', step=name, static=static, id=key, units=units, env=self.env,
                    reads=[[_jpath(q), h] for q, h in sorted(reads.items(), key=lambda kv: json.dumps(_jpath(kv[0])))],
                    files=outs, digests={rel: self.files.get(os.path.join(self.out, rel), fresh=True) for rel in outs},
                    created=time.strftime('%Y-%m-%dT%H:%M:%S'), spec_name=self.name))
                os.makedirs(os.path.dirname(final), exist_ok=True)
                try:
                    os.rename(tmp, final)
                except OSError:
                    shutil.rmtree(tmp, ignore_errors=True)
            except Exception:
                shutil.rmtree(tmp, ignore_errors=True)
                raise
        if self.mode == 'verify' and E is not None:
            bad = [rel for rel in sorted(set(E.m['files']) | set(outs)) if E.m['digests'].get(rel) !=
                   (self.files.get(os.path.join(self.out, rel), fresh=True) if rel in outs else None)]
            try:
                if digest(self.load_state(E)['result'], 'name') != digest(result, 'name'):
                    bad.append('its result')
            except RestoreError as e:
                bad.append('its stored state does not load: %s' % e)
            info['verified'] = not bad
            if bad:
                info['stale'] = bad[:6]
                self.stale.append((name, bad))
                print('CHARKIT_CACHE_STALE %s: %s' % (name, ', '.join(bad[:6])))
        adopt(S)
        trace.event('part', name, dt=round(time.perf_counter() - t, 4), cache=info)
        return result

    # --------------------------------------------------------------------------------------------------- the end
    def finish(self):
        """record this build's entries (for the next build's miss reasons), save the file memo, trim the cache."""
        global _CUR
        L = dict(self.last)
        L.update(self.now)
        _write_json(os.path.join(self.dir, 'last', self.name + '.json'), L)
        self.files.save()
        prune(self.dir)
        if _CUR is self:
            _CUR = None


def part(name, fn, S, *args):
    """a QA part through the running build's cache (Cache.part), or called when there is none."""
    C = _CUR
    if C is None or C.mode == 'off':
        return fn(S, *args)
    return C.part(name, fn, S, *args)


def memo(fn, *args, **kw):
    """fn(*args, **kw) for a pure function (numpy in, numpy out: the design-side measurements of a model sheet), kept on
    disk by its code and its arguments' digest; each call returns a fresh copy. Outside a build it just calls."""
    C = _CUR
    if C is None or C.mode == 'off':
        return fn(*args, **kw)
    r = _REC
    if r is not None and not r.paused:                      # the step around it reads the arguments whole
        for a in list(args) + list(kw.values()):
            for t in _tracked_in(a):
                r.read(t._path + (ALL,), t)
    units = code_units(fn)
    key = digest([SCHEMA, units, env(), args, kw])[:24]
    p = os.path.join(C.dir, 'memo', '%s.%s' % (fn.__module__, fn.__name__), key + '.pkl')
    if os.path.exists(p) and C.mode in ('on', 'stages'):
        try:
            with open(p, 'rb') as f:
                out = pickle.load(f)
            os.utime(p)
            return out
        except Exception:
            pass
    out = fn(*args, **kw)
    try:
        blob = pickle.dumps(out, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception:
        return out
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = '%s.%d.tmp' % (p, os.getpid())
    open(tmp, 'wb').write(blob)
    os.replace(tmp, p)
    return out


def _tracked_in(v, depth=0):
    if isinstance(v, TrackedDict):
        yield v
    elif depth < 2 and isinstance(v, (list, tuple)):
        for e in v:
            yield from _tracked_in(e, depth + 1)
    elif depth < 2 and isinstance(v, dict):
        for e in dict.values(v):
            yield from _tracked_in(e, depth + 1)


def venv_env():
    """the venv's Python and the packages charkit.geom runs on."""
    import importlib.metadata as md
    out = dict(python=sys.version.split()[0])
    for p in ('numpy', 'scipy', 'scikit-image', 'numba', 'manifold3d', 'pillow'):
        try:
            out[p] = md.version(p)
        except md.PackageNotFoundError:
            out[p] = None
    return out


def file_step(name, run, fns, key, out, inputs=(), modules=(), name_key=None):
    """a venv-side step whose product is files under `out` (the geom hair cut, before Blender): restored by copying them
    when its code (fns and every charkit module they import), the venv's packages, `key` (what it is given, exactly), the
    content of `inputs` and of every file it opened are unchanged. -> 'hit' | 'miss: why'."""
    global _REC
    d = cache_dir()
    files = Files(d)
    t0 = time.time()
    units = code_units(*fns, modules=('charkit.cache',) + tuple(modules))
    units['charkit/assets'] = files.get(os.path.join(KIT, 'assets'))
    units = dict(sorted(units.items()))
    envv = venv_env()
    static = digest([SCHEMA, 'venv', name, units, envv, key, sorted((os.path.abspath(p), files.get(p)) for p in inputs)])
    kd = os.path.join(d, 'venv', name, static[:20])
    for c in _entries(kd):
        try:
            E = Entry(c)
            if all(files.get(p) == h for p, h in E.m['reads']):
                for rel in E.m['files']:
                    dst = os.path.join(out, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copyfile(os.path.join(E.dir, 'files', rel), dst)
                for line in E.m['stdout']:
                    print(line)
                os.utime(E.file('manifest.json'))
                files.save()
                return 'hit'
        except (OSError, ValueError, KeyError):
            continue
    why = 'file changed' if _entries(kd) else 'no entry'
    last = os.path.join(d, 'last', 'venv_%s_%s.json' % (name, name_key or 'build'))
    try:
        L = json.load(open(last))
        ch = [u for u in sorted(set(L['units']) | set(units)) if L['units'].get(u) != units.get(u)]
        why = 'code ' + ', '.join(ch[:3]) if ch else 'packages' if L['env'] != envv else 'its input changed' \
            if L['key'] != digest(key) else why
    except (OSError, ValueError, KeyError):
        pass
    _hook()
    rec = Recorder(types.SimpleNamespace(watch=lambda p: not p.endswith(('.py', '.pyc', '.so', '.dylib')) and
                                         not p.startswith(_skip_prefixes() + (os.path.abspath(d) + os.sep,)) and
                                         (not p.startswith(KIT + os.sep) or p.startswith(os.path.join(KIT, 'out') + os.sep))
                                         and not p.startswith(os.path.abspath(out) + os.sep)), name, None, None)
    rec.files_only = True
    before = _tree(out)
    lines = []
    _REC = rec
    try:
        with _tee(lines):
            run()
    finally:
        _REC = None
    after = _tree(out)
    outs = sorted(k for k, v in after.items() if before.get(k) != v)
    reads = sorted((p, files.get(p)) for p in rec.files)
    key2 = digest([static, reads])
    if any(os.stat(os.path.join(dd, f)).st_mtime > t0 for dd, ds, fs in os.walk(KIT) for f in fs if f.endswith('.py')
           and not dd.startswith((os.path.join(KIT, 'out'), os.path.join(KIT, 'tests')))):
        return 'miss: charkit changed during the step (not stored)'

    tmp = tempfile.mkdtemp(prefix='.w-', dir=d)
    try:
        for rel in outs:
            dst = os.path.join(tmp, 'files', rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(os.path.join(out, rel), dst)
        _write_json(os.path.join(tmp, 'manifest.json'), dict(schema=SCHEMA, kind='venv', step=name, static=static, units=units,
                                                             env=envv, reads=reads, files=outs, created=time.strftime(
                                                                 '%Y-%m-%dT%H:%M:%S'),
                                                             stdout=[l for l in lines if l.startswith(('geom ', 'CHARKIT_'))]))
        final = os.path.join(kd, key2[:24])
        os.makedirs(kd, exist_ok=True)
        try:
            os.rename(tmp, final)
        except OSError:
            shutil.rmtree(tmp, ignore_errors=True)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    _write_json(last, dict(units=units, env=envv, key=digest(key)))
    files.save()
    return 'miss: ' + why


def _apply(S, writes):
    """set a step's recorded writes ({path: value or ABSENT}, the shorter paths first) under S (its spec, its dicts)."""
    for p, v in sorted(writes.items(), key=lambda kv: len(kv[0])):
        parent = _resolve(p[:-1], S)
        if not isinstance(parent, dict):
            raise RestoreError('%s is not there to write into' % readable(p[:-1]))
        if v is ABSENT:
            dict.pop(parent, p[-1], None)
        else:
            dict.__setitem__(parent, p[-1], v)


def _state_digest(st):
    """what a checkpoint sets, as one digest (Blender objects by name: their content is the trace's to compare)."""
    return digest([st['attrs'], st['spec'], st['writes'], st['mats'], st['modified']], 'name')


def _record_diff(a, b):
    """what differs between a stored stage record and a restored (or re-run) one: the objects it added, in full; the names
    it changed or removed, and their modifier stacks and materials (their geometry is upstream's)."""
    out = []
    aa, ba = a.get('added', {}), b.get('added', {})
    for n in sorted(set(aa) | set(ba)):
        x, y = aa.get(n), ba.get(n)
        if x is None or y is None:
            out.append('%s %s' % (n, 'added' if x is None else 'not added'))
        elif x != y:
            ks = [k for k in sorted(set(x) | set(y)) if x.get(k) != y.get(k)]
            out.append('%s: %s' % (n, ', '.join(ks)))
    ac, bc = a.get('changed', {}), b.get('changed', {})
    if sorted(ac) != sorted(bc):
        out.append('changed %s -> %s' % (sorted(ac), sorted(bc)))
    for n in set(ac) & set(bc):
        for k in ('modifiers', 'materials'):
            if ac[n].get(k) != bc[n].get(k):
                out.append('%s.%s' % (n, k))
    if a.get('removed', []) != b.get('removed', []):
        out.append('removed %s -> %s' % (a.get('removed'), b.get('removed')))
    if a.get('objects') != b.get('objects'):
        out.append('objects %s -> %s' % (a.get('objects'), b.get('objects')))
    return out


def _ob_delta(ob, p0, p1):
    """what a stage did to an object that existed before it, in the kinds a restore can replay: new vertex groups (with
    their weights), modifiers (settings, and the stack's order), attributes (data) and material slots. Anything else
    raises Uncacheable."""
    ch = [k for k in sorted(set(p0) | set(p1)) if p0.get(k) != p1.get(k)]
    if not ch:
        return None
    me = ob.data if ob.type == 'MESH' else None
    d = dict(vgroups={}, modifiers=[], order=None, attrs=[], mats=None, colors=None)
    new_vg = [k[3:] for k in ch if k.startswith('vg:') and k not in p0]
    new_mod = [k[4:] for k in ch if k.startswith('mod:') and k not in p0]
    new_attr = [k[5:] for k in ch if k.startswith('attr:') and k not in p0]
    allowed = {'vgs', 'mods', 'mats', 'layout'} | {'vg:' + n for n in new_vg} | {'mod:' + n for n in new_mod} | \
        {'attr:' + n for n in new_attr}
    other = [k for k in ch if k not in allowed]
    if other:
        raise Uncacheable(', '.join(other[:4]))
    if new_vg:
        W = vgroup_weights(ob)
        d['vgroups'] = {n: W[n] for n in new_vg}
    names0 = [m.name for m in ob.modifiers if 'mod:' + m.name in p0]
    for m in ob.modifiers:
        if m.name in new_mod:
            d['modifiers'].append((m.name, m.type, rna(m)))
    d['order'] = [m.name for m in ob.modifiers]
    if [n for n in d['order'] if n in names0] != names0:
        raise Uncacheable('reorders its modifiers')
    for n in new_attr:
        a = me.attributes[n]
        d['attrs'].append((n, a.domain, a.data_type, attr_data(a)))
    if me is not None:
        d['mats'] = [s.material.name if s.material else None for s in ob.material_slots]
        if any(s.link != 'DATA' for s in ob.material_slots):
            raise Uncacheable('object-linked material slots')
        d['colors'] = (me.color_attributes.active_color_name, me.color_attributes.default_color_name)
    d['parts'] = {k: p1[k] for k in ch}
    return d


def _replay(ob, d):
    """replay a stage's changes to an object that existed before it (see _ob_delta); checked part by part."""
    bpy = _bpy()
    me = ob.data if ob.type == 'MESH' else None
    for n, (vi, w) in d['vgroups'].items():
        if n in ob.vertex_groups:
            raise RestoreError('%s already has a group %s' % (ob.name, n))
        g = ob.vertex_groups.new(name=n)
        for wv in np.unique(w):
            g.add([int(i) for i in vi[w == wv]], float(wv), 'REPLACE')
    for n, dom, typ, arr in d['attrs']:
        coll = me.color_attributes if typ in ('FLOAT_COLOR', 'BYTE_COLOR') and dom in ('POINT', 'CORNER') else me.attributes
        a = coll.new(n, typ, dom)
        prop = _ATTR[typ][0]
        a.data.foreach_set(prop, arr)
    for n, typ, props in d['modifiers']:
        m = ob.modifiers.new(n, typ)
        if m.name != n:
            raise RestoreError('%s: modifier %s came back as %s' % (ob.name, n, m.name))
        for _ in range(2):                                   # settings that gate others go in on the second pass too
            _set_rna(m, props)
        if rna(m) != props:
            raise RestoreError('%s: modifier %s settings differ' % (ob.name, n))
    order = d['order']
    for i, n in enumerate(order):
        j = ob.modifiers.find(n)
        if j < 0:
            raise RestoreError('%s: no modifier %s' % (ob.name, n))
        if j != i:
            ob.modifiers.move(j, i)
    if [m.name for m in ob.modifiers] != order:
        raise RestoreError('%s: modifier stack differs' % ob.name)
    if me is not None and d['mats'] is not None:
        for i, n in enumerate(d['mats']):
            m = bpy.data.materials[n] if n else None
            if i < len(me.materials):
                me.materials[i] = m
            else:
                me.materials.append(m)
        while len(me.materials) > len(d['mats']):
            me.materials.pop()
        ca = me.color_attributes
        if d['colors'][0]:
            ca.active_color_name = d['colors'][0]
        if d['colors'][1]:
            ca.default_color_name = d['colors'][1]
    parts = ob_parts(ob, full=True)
    bad = [k for k, v in d['parts'].items() if parts.get(k) != v]
    if bad:
        raise RestoreError('%s: %s came back different' % (ob.name, ', '.join(bad[:4])))


def _set_rna(s, props):
    bpy = _bpy()
    for k, v in props.items():
        try:
            if isinstance(v, tuple) and len(v) == 3 and v and v[0] == 'ID':
                coll = getattr(bpy.data, COLL[v[1]])
                setattr(s, k, coll[v[2]])
            elif isinstance(v, dict):
                _set_rna(getattr(s, k), v)
            elif v is None:
                if getattr(s, k) is not None:
                    setattr(s, k, None)
            elif isinstance(v, list):
                setattr(s, k, set(v))
            else:
                if getattr(s, k) != v:
                    setattr(s, k, v)
        except (AttributeError, TypeError, ValueError, KeyError):
            pass


def _norm(x):
    """a trace record as it reads back from trace.jsonl (plain JSON, floats rounded as the trace rounds them)."""
    from . import trace
    return json.loads(json.dumps(trace._plain(x)))


def _tree(d):
    out = {}
    if d and os.path.isdir(d):
        for r, dirs, files in os.walk(d):
            for f in files:
                p = os.path.join(r, f)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                out[os.path.relpath(p, d)] = (st.st_size, st.st_mtime_ns)
    return out


@contextlib.contextmanager
def _tee(lines):
    """copy stdout's lines into `lines` while still printing them."""
    real = sys.stdout

    class T:
        buf = ''

        def write(self, s):
            real.write(s)
            self.buf += s
            while '\n' in self.buf:
                l, self.buf = self.buf.split('\n', 1)
                lines.append(l)
            return len(s)

        def flush(self):
            real.flush()

        def __getattr__(self, k):
            return getattr(real, k)
    sys.stdout = T()
    try:
        yield lines
    finally:
        sys.stdout = real


# ------------------------------------------------------------------------------------------------------------ upkeep
def entries(d=None):
    """every entry: (kind, step, path, bytes, last used)."""
    d = d or cache_dir()
    out = []
    for kind in ('stages', 'products', 'parts', 'venv'):
        base = os.path.join(d, kind)
        if not os.path.isdir(base):
            continue
        for step in sorted(os.listdir(base)):
            for sk in os.listdir(os.path.join(base, step)):
                for e in os.listdir(os.path.join(base, step, sk)):
                    p = os.path.join(base, step, sk, e)
                    m = os.path.join(p, 'manifest.json')
                    if os.path.exists(m):
                        size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(p) for f in fs)
                        out.append((kind, step, p, size, os.path.getmtime(m)))
    base = os.path.join(d, 'memo')
    if os.path.isdir(base):
        for step in sorted(os.listdir(base)):
            for f in os.listdir(os.path.join(base, step)):
                p = os.path.join(base, step, f)
                out.append(('memo', step, p, os.path.getsize(p), os.path.getmtime(p)))
    return out


def prune(d=None, max_gb=None):
    """drop the least recently used entries until the cache is under its size cap (CHARKIT_CACHE_MAX_GB, default 12)."""
    es = sorted(entries(d), key=lambda e: e[4])
    total = sum(e[3] for e in es)
    cap = (max_gb or MAX_GB) * 1e9
    while es and total > cap:
        e = es.pop(0)
        if os.path.isdir(e[2]):
            shutil.rmtree(e[2], ignore_errors=True)
        elif os.path.exists(e[2]):
            os.remove(e[2])
        total -= e[3]


def main(args):
    d = cache_dir()
    if not args or args[0] == 'info':
        es = entries(d)
        by = {}
        for kind, step, p, size, t in es:
            b = by.setdefault((kind, step), [0, 0, 0])
            b[0] += 1; b[1] += size; b[2] = max(b[2], t)
        print('cache %s: %d entries, %.2f GB (cap %.0f GB)' % (d, len(es), sum(e[3] for e in es) / 1e9, MAX_GB))
        for (kind, step), (n, size, t) in sorted(by.items()):
            print('  %-9s %-14s %3d entries %8.1f MB  last used %s' % (kind, step, n, size / 1e6,
                                                                       time.strftime('%Y-%m-%d %H:%M', time.localtime(t))))
    elif args[0] == 'clear':
        for k in ('stages', 'products', 'parts', 'venv', 'memo', 'last'):
            shutil.rmtree(os.path.join(d, k), ignore_errors=True)
        print('cleared', d)
    else:
        raise SystemExit(__doc__)
