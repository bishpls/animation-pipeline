"""The build cache (docs/CHARKIT.md §3): each scene stage's output is checkpointed under charkit/out/.cache/ and restored,
instead of rebuilt, when nothing the stage read has changed; the boards, the QA and the VRM are cached the same way on the
whole scene, each QA part (eyes, sheet, figures, body...) on what it reads (`part`), the model sheet's design-side
measurements per argument (`memo`), and the venv-side geom hair cut on its inputs (`file_step`). Blender-side
(charkit/scene.py and charkit/build_blender.py drive it); the hashing and the code closure are plain Python.

A stage's key is what the stage read, recorded while it ran, so a read nobody listed can't be missed:
  code      the stage function, the scene.py helpers it calls and scene.py's top-level statements, and every charkit
            module they import, transitively, as syntax trees (comments and docstrings don't count); the kit's data
            (charkit/assets); this module; the Blender, numpy and Python versions
  spec      each spec key it read, at any depth (`spec.head.width`), exactly (whether a dict is empty, its length or
            a key's presence when that is all it asked)
  upstream  each value it read of what came before: the Scene's attributes and, key by key, the dicts under them
            (`character.data.head.L`, `character.data.joints.neck01____head`), shade.MATS entries, Blender objects (their
            full state, or the part scene.DEPS declares the stage reads: garments read the body below the neck, and only the
            names of the skin's modifiers and groups)
  files     every file it opened outside the kit (the hull's GLB) and every path named in the spec sections it read, by
            sha256 (a stat-checked memo skips re-hashing unchanged files; a manifest's sha256 is compared, not trusted)
A lookup evaluates each stored entry's recorded reads against the scene as it now stands and restores the first entry
whose reads all match. A miss says what changed: `spec.hair`, `character.data.joints.neck01____head moved 5.5e-05`,
`file charkit/out/hull/clawd/hull.glb`, `code charkit/garments.py`.

A checkpoint holds what the stage changed and only that, so it restores onto a rebuilt upstream (garments onto a new face):
  data.blend   the datablocks it made (bpy.data.libraries.write); what they point at from before (the rig, a shared
               material) is re-bound by name when they are appended
  state.pkl    the Scene attributes, spec sections, dict entries and shade.MATS entries it set (pickled, Blender references by
               name), the notes it wrote, and its changes to objects made before it: new vertex groups, modifiers (settings
               and stack position), attributes and material slots, replayed on restore
  inputs.npz   the small arrays it read, so a miss can say how far they moved; images.npz the float images' pixels
Nothing is stored from a run that printed a traceback (a check that caught an error), from a build whose charkit sources
changed as it ran, or with less than CHARKIT_CACHE_MIN_FREE_GB (2) free; a store that fails leaves the build running.
The cache keeps under CHARKIT_CACHE_GB (5), least recently used entries out first.
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
def max_gb():
    """the cache's size cap (CHARKIT_CACHE_GB, default 5): past it the least recently used entries go."""
    return float(os.environ.get('CHARKIT_CACHE_GB', 5))
ALL, HAS = '\0*', '\0?'                 # path markers: the whole dict was read; only the key's presence was
NONEMPTY, LEN = '\0#', '\0n'             # ...only whether the dict is empty; only how many keys it has
MARKS = (ALL, HAS, NONEMPTY, LEN)


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


def unshare(path):
    """give every regular file under path (a directory or one file) that is hard-linked elsewhere (st_nlink > 1) its own
    copy, in place and atomically (copy, then os.replace), so writing it can't change another worktree's. Worktrees
    seeded with `cp -al` share outputs by link, and a writer that opens an existing file ('wb', shutil.copyfile, np.save)
    writes through the link: a produced hull rebuilt in one worktree silently replaced it in four others
    (2026-09-29). Readers holding the old file keep it. -> the number of files unshared."""
    if not os.path.exists(path):
        return 0
    files = [path] if os.path.isfile(path) else [os.path.join(d, f) for d, _, fs in os.walk(path) for f in fs]
    n = 0
    for f in files:
        try:
            st = os.lstat(f)
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(st.st_mode) or st.st_nlink < 2:
            continue
        tmp = f + '.unshare.tmp'
        shutil.copy2(f, tmp)
        os.replace(tmp, f)
        n += 1
    return n


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

    MAX = 20000                                 # paths remembered; past it the gone ones are dropped (a shared folder
                                                # sees every gate clone's paths, each gone when its gate ends)

    def save(self):
        if self.dirty:
            if len(self.memo) > self.MAX:
                self.memo = {p: m for p, m in self.memo.items() if os.path.exists(p)}
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


class Tree:
    """where the code walk (code_units) reads charkit's modules: another worktree's files (root: its top), or a git
    revision's (repo and rev: a commit or a tree id, read with git, nothing checked out). The default, None, is this
    checkout, as every cache key reads it. The gate compares one check's code, or one change's reach, between two trees
    (charkit.codediff)."""

    def __init__(self, root=None, repo=None, rev=None):
        self.repo, self.rev = repo, rev
        self.root = os.path.abspath(root) if root else '<git %s>' % rev
        self.id = self.root if root else 'git:%s:%s' % (os.path.abspath(repo or ROOT), rev)
        self._blobs = None
        if root is None:
            import subprocess
            r = subprocess.run(['git', 'ls-tree', '-r', '-z', rev, '--', 'charkit'], cwd=repo or ROOT,
                               capture_output=True, text=True)
            if r.returncode:
                raise ValueError('no tree %s: %s' % (rev, r.stderr.strip()))
            self._blobs = {}
            for e in r.stdout.split('\0'):
                if e:
                    meta, _, path = e.partition('\t')
                    if path.endswith('.py'):
                        self._blobs[path] = meta.split()[2]
            self.mods = digest(sorted(self._blobs))          # (which modules exist: imports resolve against them)

    def path(self, rel):
        return os.path.join(self.root, rel)

    def rel(self, path):
        return os.path.relpath(path, self.root) if self._blobs is None else path[len(self.root) + 1:]

    def isfile(self, path):
        return os.path.isfile(path) if self._blobs is None else self.rel(path) in self._blobs

    def stamp(self, path):
        if self._blobs is None:
            st = os.stat(path)
            return [st.st_mtime_ns, st.st_size]
        return [self._blobs[self.rel(path)], self.mods]

    def text(self, path):
        if self._blobs is None:
            return open(path).read()
        import subprocess
        return subprocess.run(['git', 'cat-file', 'blob', self._blobs[self.rel(path)]], cwd=self.repo or ROOT,
                              capture_output=True, text=True, check=True).stdout


_TREE = [None]                          # the tree the code walk reads (code_tree()); None: this checkout


# ------------------------------------------------------------------------------- the code that ran (the runtime closure)
RAN_TOOL = 4                            # the sys.monitoring tool id the record uses (0-2 and 5 are Python's named ones)


@contextlib.contextmanager
def ran():
    """the charkit definitions whose code runs inside the block, recorded as it runs (sys.monitoring's PY_START, each
    code object reported once: no cost to speak of) -> a dict filled when the block ends: {'path:definition' (or
    'path:<top>'): its digest now}, as code_units names units. A cache entry keeps it and a lookup checks it
    (ran_changed): the static walk behind a key can't see everything a step runs (a computed import, a depth limit),
    the record can. Nested, or without sys.monitoring (Python before 3.12) or a free tool id, the dict stays None-free
    but marked {'<unrecorded>': why}."""
    got = {}
    mon = getattr(sys, 'monitoring', None)
    if mon is None:
        got['<unrecorded>'] = 'no sys.monitoring'
        yield got
        return
    try:
        mon.use_tool_id(RAN_TOOL, 'charkit.cache.ran')
    except ValueError:
        got['<unrecorded>'] = 'the record is in use (nested)'
        yield got
        return
    codes = set()

    def seen(code, offset):
        codes.add((code.co_filename, code.co_qualname))
        return mon.DISABLE
    try:
        mon.register_callback(RAN_TOOL, mon.events.PY_START, seen)
        mon.restart_events()                    # (code reported to an earlier record reports again)
        mon.set_events(RAN_TOOL, mon.events.PY_START)
        yield got
    finally:
        mon.set_events(RAN_TOOL, 0)
        mon.register_callback(RAN_TOOL, mon.events.PY_START, None)
        mon.free_tool_id(RAN_TOOL)
        got.update(ran_units(codes))


def _ran_module(path):
    """a source file -> its charkit module name, or None (outside charkit, its tests or outputs)."""
    path = os.path.abspath(path)
    if not path.startswith(KIT + os.sep) or not path.endswith('.py') or \
            path.startswith((os.path.join(KIT, 'out') + os.sep, os.path.join(KIT, 'tests') + os.sep)):
        return None
    return os.path.relpath(path, ROOT)[:-3].replace(os.sep, '.').replace('.__init__', '')


def ran_units(codes):
    """(file, qualified name) pairs of code that ran -> {'path:definition' or 'path:<top>': digest} (a nested function
    or method counts as its top-level definition; a module's own statements and lambdas as its <top>)."""
    out = {}
    for f, qn in codes:
        m = _ran_module(f)
        if m is None:
            continue
        try:
            M = _mod(m)
        except (TypeError, OSError, SyntaxError):
            continue
        top = qn.split('.')[0]
        if top in M.defs:
            out['%s:%s' % (M.rel, top)] = M.defs[top][0]
        else:
            out[M.rel + ':<top>'] = M.top
    return dict(sorted(out.items()))


def ran_changed(rec):
    """a recorded runtime closure (ran()) against the code now -> the first unit that differs or is gone ('<unrecorded>'
    when there is no record: an entry from before the record, or one made where it couldn't record), else None (an
    empty record: no charkit code ran, nothing to change)."""
    if rec is None or '<unrecorded>' in rec:
        return '<unrecorded>'
    for u, dg in rec.items():
        rel, _, name = u.rpartition(':')
        m = rel[:-3].replace('/', '.').replace('.__init__', '')
        try:
            M = _mod(m)
        except (TypeError, OSError, SyntaxError):
            return u
        if (M.top if name == '<top>' else (M.defs.get(name) or [None])[0]) != dg:
            return u
    return None


@contextlib.contextmanager
def code_tree(tree):
    """code_units (and _mod) read tree's modules inside: a Tree, or a worktree's path. The memo of parsed modules
    is per tree (a git tree's by blob), and only this checkout's is kept on disk."""
    t = Tree(root=tree) if isinstance(tree, str) else tree
    old = _TREE[0]
    _TREE[0] = t
    try:
        yield t
    finally:
        _TREE[0] = old


def _module_file(name):
    """charkit.x.y -> its source file (None outside charkit) in the tree the code walk reads (code_tree)."""
    parts = name.split('.')
    if parts[0] != 'charkit':
        return None
    t = _TREE[0]
    kit = KIT if t is None else t.path('charkit')
    for p in (os.path.join(kit, *parts[1:]) + '.py', os.path.join(kit, *parts[1:], '__init__.py')):
        if (os.path.isfile(p) if t is None else t.isfile(p)):
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


_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
_COMPS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _bindings(node):
    """the names a function (or comprehension) binds in its own scope: arguments, assignment and loop targets, imports,
    nested definitions, handlers, with-as; not those declared global or nonlocal."""
    out, glob_ = set(), set()
    if isinstance(node, _SCOPES):
        A = node.args
        for x in A.posonlyargs + A.args + A.kwonlyargs + [A.vararg, A.kwarg]:
            if x is not None:
                out.add(x.arg)
    stack = list(ast.iter_child_nodes(node)) if not isinstance(node, _COMPS) else [g.target for g in node.generators]
    while stack:
        n = stack.pop()
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
            stack += n.decorator_list + ([a for a in n.args.defaults + n.args.kw_defaults if a is not None]
                                         if not isinstance(n, ast.ClassDef) else n.bases)
            continue                                   # (its body is its own scope)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            out |= {a.asname or a.name.split('.')[0] for a in n.names if a.name != '*'}
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            glob_ |= set(n.names)
        elif isinstance(n, ast.arg):
            out.add(n.arg)
        if isinstance(n, _SCOPES + _COMPS) and n is not node:
            continue                                   # (a lambda's or comprehension's own names stay in it)
        stack += list(ast.iter_child_nodes(n))
    return out - glob_


class _Mod:
    """a parsed charkit module: its syntax tree's digest (docstrings dropped); per top-level definition its digest and
    what it refers to outside itself, as scoping resolves it (a name its own functions bind, a local `main` above all,
    is not the module's `main`): free names (this module's definitions or imports), `module.attr` pairs, the charkit
    modules it imports inside and binds; the digest of the other top-level statements and what they refer to; the
    names the top level binds to charkit modules (bound) and to names in them (bound_from); the charkit modules it
    imports anywhere. Plain data, memoized on disk by file stamp. For the finer walk (code_units(fine=True): the
    gate's comparisons, not cache keys) also each top-level assignment to plain names (assigns: {name: [digest, names,
    attrs, local]}) and the rest of the top level without them or the imports (rest, rest_refs). An import made by a
    call with a literal name (`m = importlib.import_module('charkit.x')`, `__import__('charkit.x', fromlist=..)`)
    binds and is followed like an import statement: before 2026-10-01 it was invisible, and code_base.head_sections'
    runtime headfit import kept the hull's shared-cache key blind to headfit (a stale baseline hull faked a regression
    in a gate after face7 changed headfit)."""
    SCHEMA = 5

    def __init__(self, name, path, d=None):
        self.name, self.path = name, path
        t = _TREE[0]
        self.rel = os.path.relpath(path, ROOT) if t is None else t.rel(path)
        if d is not None:
            self.__dict__.update(d)
            self.imports = set(self.imports)
            return
        tree = ast.parse(open(path).read() if t is None else t.text(path))
        _strip_docs(tree)
        self.digest = _dump(tree)
        self.pkg = name if path.endswith('__init__.py') else name.rpartition('.')[0]
        self.defs, top, self.bound, self.bound_from = {}, [], {}, {}
        for n in tree.body:
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                for k, v in self._binds(n).items():
                    (self.bound if isinstance(v, str) else self.bound_from)[k] = v
            elif isinstance(n, ast.Assign) and self._dyn(n.value):       # (a top-level `m = import_module('..')`)
                for t_ in n.targets:
                    if isinstance(t_, ast.Name):
                        self.bound[t_.id] = self._dyn(n.value)
        used = set()
        for n in tree.body:
            refs = self._refs(n)
            used |= set(refs['names']) | {x for x, _ in refs['attrs']}
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self.defs[n.name] = [_dump(n), refs['names'], refs['imps'], refs['attrs'], refs['local']]
            else:
                top.append(n)
                if not isinstance(n, (ast.Import, ast.ImportFrom)):
                    self.top_refs = getattr(self, 'top_refs', {'names': [], 'attrs': [], 'local': [], 'called': []})
                    for k in ('names', 'attrs', 'local', 'called'):
                        self.top_refs[k] = self.top_refs[k] + [x for x in refs[k] if x not in self.top_refs[k]]
        self.top_refs = getattr(self, 'top_refs', {'names': [], 'attrs': [], 'local': [], 'called': []})
        self.top = digest([ast.dump(n, annotate_fields=False, include_attributes=False) for n in top])
        # (the finer walk's view of the top level: a constant is its own unit, reached by name; imports resolve names)
        self.assigns, rest = {}, []
        self.rest_refs = {'names': [], 'attrs': [], 'local': [], 'called': []}
        for n in top:
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                continue
            tg = n.targets if isinstance(n, ast.Assign) else [n.target] if isinstance(n, ast.AnnAssign) else None
            names = [t.id for t in tg if isinstance(t, ast.Name)] if tg else []
            refs = self._refs(n)
            if tg and len(names) == len(tg):
                for x in names:
                    self.assigns[x] = [_dump(n), refs['names'], refs['attrs'], refs['local']]
                continue
            rest.append(n)
            for k in self.rest_refs:
                self.rest_refs[k] = self.rest_refs[k] + [x for x in refs[k] if x not in self.rest_refs[k]]
        self.rest = digest([ast.dump(n, annotate_fields=False, include_attributes=False) for n in rest])
        # a top-level import nothing here names: imported for what importing it does (registering parts): taken whole
        self.side = sorted({v.lstrip('!') for k, v in self.bound.items() if k not in used} |
                           {v[0] for k, v in self.bound_from.items() if k not in used and v[1] == '*'})
        self.imports = set()
        for n in ast.walk(tree):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    self.imports |= set(self.resolve(n, a.name))

    def _binds(self, node):
        """an import statement's bindings: {local name: module} for a charkit module, {local name: [module, name]} for a
        name from one ('*': every name); a dotted `import charkit.a.b` binds `charkit` to the whole of charkit.a.b."""
        out = {}
        for a in node.names:
            for m in self.resolve(node, a.name):
                if isinstance(node, ast.Import):
                    # (`import charkit.a.b` binds `charkit`: '!' marks a binding only whole modules can resolve)
                    out[a.asname or a.name.split('.')[0]] = m if a.asname or '.' not in a.name else '!' + m
                elif a.name == '*':
                    out['*' + m] = [m, '*']
                elif m.endswith('.' + a.name):
                    out[a.asname or a.name] = m
                else:
                    out[a.asname or a.name] = [m, a.name]
        return out

    def _dyn(self, n):
        """a call importing a module by a literal name (importlib.import_module, __import__ with a fromlist: the module
        itself) -> that charkit module, or None (a computed name, or not charkit's: not followed)."""
        if not isinstance(n, ast.Call) or not n.args:
            return None
        f = n.func
        fname = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else None
        a = n.args[0]
        if fname not in ('import_module', '__import__') or not (isinstance(a, ast.Constant) and isinstance(a.value, str)):
            return None
        m = a.value
        if m.startswith('.'):                       # (import_module('.x', __package__): relative to this package)
            lv = len(m) - len(m.lstrip('.'))
            pkg = self.pkg.split('.')
            m = '.'.join(pkg[:len(pkg) - (lv - 1)] + [m.lstrip('.')])
        if fname == '__import__' and not (len(n.args) > 3 or any(k.arg == 'fromlist' for k in n.keywords)):
            m = m.split('.')[0] if '.' in m else m      # (no fromlist: __import__ returns the top package)
        return m if _module_file(m) else None

    def _refs(self, node):
        """what a top-level statement refers to outside its own scopes -> {'names': free names, 'attrs': [[name, attr]]
        (a free name's attribute), 'imps': charkit modules imported inside, 'local': [[module, attr or None]] (through
        an import inside: None, the module used bare, whole)}."""
        names, attrs, local, imps, called = set(), set(), set(), set(), set()
        binds = {}
        for n in ast.walk(node):
            if isinstance(n, (ast.Import, ast.ImportFrom)) and n is not node:
                b = self._binds(n)
                binds.update(b)
                imps |= {v if isinstance(v, str) else v[0] for v in b.values()}
            elif isinstance(n, ast.Assign) and self._dyn(n.value):
                m = self._dyn(n.value)                  # (`x = importlib.import_module('charkit.m')`: x binds m)
                binds.update({t_.id: m for t_ in n.targets if isinstance(t_, ast.Name)})
                imps.add(m)

        def walk(n, bound):
            if isinstance(n, ast.Assign) and self._dyn(n.value):
                for t_ in n.targets:                    # (the call is the binding above, not a use of the module)
                    walk(t_, bound)
                return
            if isinstance(n, ast.Attribute) and self._dyn(n.value):
                local.add((self._dyn(n.value), n.attr))     # (`__import__('charkit.m', fromlist=[..]).f`)
                return
            if isinstance(n, ast.Call) and self._dyn(n):
                local.add((self._dyn(n), None))         # (imported and used otherwise: the module whole)
                return
            if isinstance(n, _SCOPES + _COMPS):
                bound = bound | _bindings(n)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id not in bound:
                called.add(n.func.id)
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and isinstance(n.value.ctx, ast.Load):
                x = n.value.id
                if x in binds and x in bound:
                    v = binds[x]
                    local.add((v, n.attr) if isinstance(v, str) and not v.startswith('!') else
                              ((v.lstrip('!'), None) if isinstance(v, str) else tuple(v)))
                elif x not in bound:
                    attrs.add((x, n.attr))
                return
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                x = n.id
                if x in binds and x in bound:
                    v = binds[x]
                    local.add((v.lstrip('!'), None) if isinstance(v, str) else tuple(v))
                elif x not in bound:
                    names.add(x)
                return
            for c in ast.iter_child_nodes(n):
                walk(c, bound)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for d in node.decorator_list + (node.bases if isinstance(node, ast.ClassDef) else
                                            [a for a in node.args.defaults + node.args.kw_defaults if a is not None]):
                walk(d, set())
            body = node.body if isinstance(node, ast.ClassDef) else [node]
            for b in body:
                walk(b, set())
        else:
            walk(node, set())
        for k, v in binds.items():
            if isinstance(v, list) and v[1] == '*':
                local.add((v[0], None))
        return {'names': sorted(names), 'attrs': sorted([list(x) for x in attrs]), 'imps': sorted(imps),
                'local': sorted([list(x) for x in local], key=str), 'called': sorted(called)}

    def data(self):
        return dict(digest=self.digest, pkg=self.pkg, defs=self.defs, bound=self.bound, bound_from=self.bound_from,
                    top=self.top, top_refs=self.top_refs, side=self.side, imports=sorted(self.imports),
                    assigns=self.assigns, rest=self.rest, rest_refs=self.rest_refs)

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


_BLOB_MODS = {}                         # parsed modules of git trees, by (blob, module, the tree's module set)


def _mod(name):
    t = _TREE[0]
    if t is not None:                   # another tree: memo per tree in memory (a git tree's per blob, across trees)
        p = _module_file(name)
        if p is None:
            raise OSError('no module %s in %s' % (name, t.root))
        k = (t.id, name) if t._blobs is None else (name,) + tuple(t.stamp(p))
        memo = _MODS if t._blobs is None else _BLOB_MODS
        st = t.stamp(p) if t._blobs is None else None
        if k not in memo or (st is not None and memo[k][0] != st):
            memo[k] = (st, _Mod(name, p))
        M = memo[k][1]
        if t._blobs is not None and (M.path != p or M.rel != t.rel(p)):
            M = _Mod(name, p, M.data())             # (the same blob in another tree: its paths are that tree's)
        return M
    p = _module_file(name)
    st = os.stat(p)
    k = [p, st.st_mtime_ns, st.st_size, sys.version.split()[0], _Mod.SCHEMA]
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
        try:
            _write_json(os.path.join(cache_dir(), 'code.json'), _DISK[0])
            _DISK[1] = False
        except OSError:
            pass


def code_units(*fns, modules=(), depth=None, starts=(), fine=False):
    """the code the functions run, as {unit: digest}, followed definition by definition across modules: each function
    ('path:name'), the definitions it names in its own module, the definitions it reaches in other charkit modules
    through their names (`from m import f`, `m.f`), and each module's top-level statements ('path:<top>': they run on
    import); a module used other than through its attributes (passed, `import *`, a dotted import, imported only for
    what importing does) is taken whole ('path': its digest, and every definition in it followed). `modules` adds whole
    modules. depth: follow references only this many modules away (None: all). Names are resolved as Python scopes
    them: a function's own local `main` is not the module's main. (Until 2026-09-30 a module was taken whole with every
    module it imports anywhere: bodyeval's one use of `cli._path` brought cli.py's 42 imports into every QA key, and the
    hull's shared-cache key covered garments.py through a local named `main`.)
    starts: more definitions to start from, as (module, name) (name None: the module whole), for a tree whose code isn't
    imported (code_tree: another worktree or a git revision).
    fine: a module's top-level constants as units of their own ('path:=NAME', reached by name) and its other top-level
    statements, imports left out, as 'path:<top>': one constant changed then reaches only the code that names it (the
    gate's comparisons: charkit.codediff; cache keys don't use it)."""
    import collections
    units, seen, done_mod, whole = {}, set(), set(), set()
    work = collections.deque((fn.__module__, fn.__name__, 0) for fn in fns)
    work.extend((m, n, 0 if n else 1) for m, n in starts)
    work.extend((m, None, 1) for m in modules)

    def ref(M, lvl, name=None, attr=None):
        """a reference from module M (at lvl) to a name in it, or to a module's attribute ('module', attr)."""
        if attr is not None or name is None:
            return
        if name in M.defs:
            work.append((M.name, name, lvl))
        elif fine and name in M.assigns:
            work.append((M.name, '=' + name, lvl))
        elif name in M.bound_from:
            m, n = M.bound_from[name]
            work.append((m, None if n == '*' else n, lvl + 1))
        elif name in M.bound:
            work.append((M.bound[name].lstrip('!'), None, lvl + 1))      # a module used bare: whole

    def follow(M, refs, lvl, top=False):
        for x in refs['names']:
            # (the top level: this module's own functions only when called on import; a table naming them doesn't
            # run them: scene.py's list of stages would bring every stage into each one's key)
            if not (top and x in M.defs and x not in refs.get('called', ())):
                ref(M, lvl, name=x)
        for x, a in refs['attrs']:
            if x in M.bound and not M.bound[x].startswith('!'):
                work.append((M.bound[x], a, lvl + 1))
            elif x in M.bound:
                work.append((M.bound[x][1:], None, lvl + 1))
            elif x in M.defs or x in M.bound_from or fine and x in M.assigns:
                ref(M, lvl, name=x)
        for m, a in refs['local']:
            work.append((m, a, lvl + 1))
    while work:
        m, n, lvl = work.popleft()
        if depth is not None and lvl > depth or (m, n) in seen:
            continue
        seen.add((m, n))
        try:
            M = _mod(m)
        except (TypeError, OSError, SyntaxError):
            continue
        if m not in done_mod:                          # its top-level statements run whenever it's imported
            done_mod.add(m)
            units[M.rel + ':<top>'] = M.rest if fine else M.top
            follow(M, M.rest_refs if fine else M.top_refs, lvl, top=True)
            work.extend((x, None, lvl + 1) for x in M.side)
        if n is None:
            if m not in whole:
                whole.add(m)
                units[M.rel] = M.digest
                work.extend((m, d, lvl) for d in M.defs)
                if fine:
                    work.extend((m, '=' + a, lvl) for a in M.assigns)
            continue
        if fine and n.startswith('=') and n[1:] in M.assigns:
            dg, nm, at, lo = M.assigns[n[1:]]
            units['%s:%s' % (M.rel, n)] = dg
            follow(M, {'names': nm, 'attrs': at, 'local': lo}, lvl)
            continue
        if fine and n in M.assigns and n not in M.defs:
            work.append((m, '=' + n, lvl))             # (a module's constant, as `module.NAME`)
            continue
        if n in M.defs:
            dg, _, imps, _, _ = M.defs[n]
            units['%s:%s' % (M.rel, n)] = dg
            d = M.defs[n]
            follow(M, {'names': d[1], 'attrs': d[3], 'local': d[4]}, lvl)
        elif n in M.bound_from or n in M.bound:
            ref(M, lvl, name=n)
        elif _module_file(m + '.' + n):
            work.append((m + '.' + n, None, lvl + 1))  # a submodule, as the package's attribute
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
        n = dict.__len__(self)
        r = _REC
        if r is not None and not r.paused:
            r.read(self._path + (LEN,), n)
        return n

    def __bool__(self):
        b = dict.__len__(self) > 0
        r = _REC
        if r is not None and not r.paused:
            r.read(self._path + (NONEMPTY,), b)
        return b

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
    s = '.'.join(str(k) for k in p if k not in MARKS)
    return s + {ALL: '[*]', HAS: '?', NONEMPTY: '[empty?]', LEN: '[len]'}.get(p[-1] if p else None, '')


def _dep_name(path):
    return '.'.join(str(k) for k in (path[1:] if path[0] == 'S' else path) if k not in MARKS)


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
        """the value a read is keyed on: the declared part (scene.DEPS), or the whole (a spec value naming a file in the
        output folder by its path there: the file itself is keyed by content)."""
        out = getattr(self.cache, 'out', None)
        if path[0] == 'spec' and out:
            v = _out_rel(v, out + os.sep)
        dep = self.deps.get(_dep_name(path))
        if dep is None or path[-1] in MARKS:
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


def _out_rel(v, out):
    """v with strings naming paths in the output folder made relative to it ('<out>/geom/hair.npz')."""
    if isinstance(v, str):
        return '<out>/' + v[len(out):] if v.startswith(out) else v
    if isinstance(v, dict):
        return {k: _out_rel(x, out) for k, x in dict.items(v)} if any(
            isinstance(x, (str, dict, list, tuple)) for x in dict.values(v)) else v
    if isinstance(v, (list, tuple)) and v and any(isinstance(x, (str, dict, list, tuple)) for x in v):
        return type(v)(_out_rel(x, out) for x in v)
    return v


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
        if k == NONEMPTY:
            return dict.__len__(v) > 0 if isinstance(v, dict) else ABSENT
        if k == LEN:
            return dict.__len__(v) if isinstance(v, dict) else ABSENT
        if i + 1 < len(rest) and rest[i + 1] == HAS:
            return isinstance(v, dict) and dict.__contains__(v, k)
        v = dict.get(v, k, ABSENT) if isinstance(v, dict) else ABSENT
    return v


def _sources():
    """the kit's source files' stats {path: (mtime_ns, size)}. Linux stamps mtimes from a coarse clock that can trail
    time.time() by a tick, so an mtime alone can't tell an edit just after a build loaded its code from one just before;
    a changed stat can."""
    from . import closure
    out = {}
    with closure.paused():                  # a look for edits, not inputs (the gate's record, charkit/closure.py)
        return _sources_walk(out)


def _sources_walk(out):
    for d, dirs, files in os.walk(KIT):
        dirs[:] = [x for x in dirs if x not in ('out', '__pycache__', 'tests')]
        for f in files:
            if f.endswith('.py'):
                p = os.path.join(d, f)
                st = os.stat(p)
                out[p] = (st.st_mtime_ns, st.st_size)
    return out


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
        self._src0 = _sources()          # the sources' stats now: an edit in the same clock tick as t0 still shows
        self.spec_file, self.refs, self.warned = None, None, set()      # the resolved spec (its ref.manifest)
        prune(self.dir)                                                 # under its cap before this build adds to it
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
            for p, st in _sources().items():
                if st != self._src0.get(p) or st[0] > self.t0 * 1e9:
                    self._edited = os.path.relpath(p, ROOT)
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

    def hashed(self, p):
        """a read file's sha256, compared with the reference manifest's where it lists one (a file that moved on from
        its manifest is keyed by what it holds now, and said)."""
        h = self.files.get(p, fresh=True)
        if self.refs is None:
            self.refs = {}
            mp = ((self.spec_file or {}).get('ref') or {}).get('manifest') if isinstance(self.spec_file, dict) else None
            try:
                R = json.load(open(mp if os.path.isabs(mp) else os.path.join(ROOT, mp)))['references'] if mp else {}
                self.refs = {os.path.normpath(os.path.join(ROOT, r['path'])): r['sha256'] for r in R.values()
                             if r.get('sha256')}
            except (OSError, ValueError, KeyError, TypeError):
                pass
        m = self.refs.get(os.path.normpath(p))
        if m and m != h and p not in self.warned:
            from . import trace
            self.warned.add(p)
            trace.note('cache.manifest', path=os.path.relpath(p, ROOT), sha256=h, manifest=m)
            print('CHARKIT_CACHE_MANIFEST %s differs from its manifest\'s sha256 (keyed on its content)' %
                  os.path.relpath(p, ROOT))
        return h

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
            if p[-1] in MARKS or p in rec.dict_writes or p in rec.spec or rec.written(p) or \
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
            reads[self.fkey(p)] = self.hashed(p)
        key = digest([static, sorted((json.dumps(_jpath(p)), h) for p, h in reads.items())])[:24]
        state = None
        if self.edited():
            errors.append('%s changed during the build' % self.edited())
        if not errors and not room(self.dir):
            errors.append('less than CHARKIT_CACHE_MIN_FREE_GB free on the disk')
        if not errors:
            try:
                state = self.store(kind, name, static, units, run, reads, key, trace_rec)
            except Uncacheable as e:
                errors.append(str(e))
            except OSError as e:                              # (a full disk: the build goes on, uncached)
                errors.append('storing it failed: %s' % e)
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
            _write_state(os.path.join(tmp, 'state.pkl'), blob)
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
        import io
        try:
            return _Unpickler(io.BytesIO(_read_state(E.file('state.pkl')))).load()
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
        lines, errs = [], []
        _REC = rec
        try:
            with trace.capture() as got, _tee(lines, errs):
                run()
        finally:
            _REC = None
        after = _tree(self.out)
        outs = sorted(k for k, v in after.items() if before.get(k) != v and not k.endswith(('.blend', '.blend1'))
                      and os.path.basename(k) not in ('trace.jsonl', '.pid.json'))
        info = {'hit': False, 'why': why or 'miss'}
        reads = {self.fkey(p): self.hashed(p) for p in sorted(rec.files | spec_paths(spec))}
        key = digest([static, sorted((json.dumps(_jpath(p)), h) for p, h in reads.items())])
        stdout = [l for l in lines if l.startswith('CHARKIT_')]
        if sk is not None and self.edited():
            sk, why = None, '%s changed during the build' % self.edited()
        elif sk is not None and _caught(errs):
            sk, why = None, 'an error was caught while it ran (see the log)'
        elif sk is not None and not room(self.dir):
            sk, why = None, 'less than CHARKIT_CACHE_MIN_FREE_GB free on the disk'
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
                         digests={rel: content_digest(os.path.join(self.out, rel)) for rel in outs},
                         records=[{k: v for k, v in r.items() if k != 't'} for r in got if r['event'] != 'product'],
                         stdout=stdout, created=time.strftime('%Y-%m-%dT%H:%M:%S'), spec_name=self.name)
                _write_json(os.path.join(tmp, 'manifest.json'), M)
                final = os.path.join(self.dir, 'products', name, static[:20], key[:24])
                os.makedirs(os.path.dirname(final), exist_ok=True)
                try:
                    os.rename(tmp, final)
                except OSError:
                    shutil.rmtree(tmp, ignore_errors=True)
            except OSError as e:
                shutil.rmtree(tmp, ignore_errors=True)
                sk, why = None, 'storing it failed: %s' % e
            except Exception:
                shutil.rmtree(tmp, ignore_errors=True)
                raise
        if sk is None:
            info['stored'] = False
            info['uncacheable'] = why
        if self.mode == 'verify' and E is not None:
            bad = [rel for rel in sorted(set(E.m['files']) | set(outs))
                   if E.m['digests'].get(rel) != (content_digest(os.path.join(self.out, rel)) if rel in outs else None)]
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
        lines, errs = [], []
        _REC = rec
        try:
            with trace.capture() as got, _tee(lines, errs):
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
            if p[-1] in MARKS or p in writes or rec.written(p) or p[0] == 'S' and p[1] in attrs:
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
            reads[self.fkey(q)] = self.hashed(q)
        key = digest([static, sorted((json.dumps(_jpath(q)), h) for q, h in reads.items())])[:24]
        info = {'hit': False, 'why': why or 'miss'}
        state = dict(result=result, attrs=attrs, writes=writes,
                     records=[{k: v for k, v in r.items() if k != 't'} for r in got])
        final = os.path.join(self.dir, 'parts', name, static[:20], key)
        blob = None
        if self.edited():
            errors.append('%s changed during the build' % self.edited())
        if _caught(errs):
            errors.append('an error was caught while it ran (see the log)')
        if not errors and not room(self.dir):
            errors.append('less than CHARKIT_CACHE_MIN_FREE_GB free on the disk')
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
                _write_state(os.path.join(tmp, 'state.pkl'), blob)
                _write_json(os.path.join(tmp, 'manifest.json'), dict(
                    schema=SCHEMA, kind='parts', step=name, static=static, id=key, units=units, env=self.env,
                    reads=[[_jpath(q), h] for q, h in sorted(reads.items(), key=lambda kv: json.dumps(_jpath(kv[0])))],
                    files=outs, digests={rel: content_digest(os.path.join(self.out, rel)) for rel in outs},
                    created=time.strftime('%Y-%m-%dT%H:%M:%S'), spec_name=self.name))
                os.makedirs(os.path.dirname(final), exist_ok=True)
                try:
                    os.rename(tmp, final)
                except OSError:
                    shutil.rmtree(tmp, ignore_errors=True)
            except OSError as e:
                shutil.rmtree(tmp, ignore_errors=True)
                errors.append('storing it failed: %s' % e)
                info.update(stored=False, uncacheable=errors[-1])
            except Exception:
                shutil.rmtree(tmp, ignore_errors=True)
                raise
        if self.mode == 'verify' and E is not None:
            bad = [rel for rel in sorted(set(E.m['files']) | set(outs)) if E.m['digests'].get(rel) !=
                   (content_digest(os.path.join(self.out, rel)) if rel in outs else None)]
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
        self.now[name] = dict(static=static, units=units, env=self.env, entry=None if errors else key)
        trace.event('part', name, dt=round(time.perf_counter() - t, 4), cache=info)
        return result

    # --------------------------------------------------------------------------------------------------- the end
    def finish(self):
        """record this build's entries (for the next build's miss reasons), save the file memo, trim the cache."""
        global _CUR
        L = dict(self.last)
        L.update(self.now)
        try:
            _write_json(os.path.join(self.dir, 'last', self.name + '.json'), L)
            self.files.save()
            save_code_memo()
        except OSError:
            pass
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
            out = pickle.loads(_read_state(p))
            os.utime(p)
            return out
        except Exception:
            pass
    out = fn(*args, **kw)
    try:
        blob = pickle.dumps(out, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception:
        return out
    if room(C.dir) and not C.edited():
        tmp = '%s.%d.tmp' % (p, os.getpid())
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            _write_state(tmp, blob)
            os.replace(tmp, p)
        except OSError:                                     # (a full disk: computed, not kept)
            if os.path.exists(tmp):
                os.remove(tmp)
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


def step_cap_gb():
    """the shared step folder's size cap (CHARKIT_STEP_CACHE_GB, default 20; past it the least recently used go)."""
    return float(os.environ.get('CHARKIT_STEP_CACHE_GB', 20))


def _closure_note(paths):
    """a restored step's dependencies into the build's input closure (charkit.closure), as reads: a hit opens none of
    them, and a closure without them would let the gate skip a build a change to them reaches."""
    from . import closure
    for p in paths:
        closure.note(p)
        if os.path.isdir(p):                        # (charkit/assets: hashed whole)
            closure.note(p, 'L')
            for dd, ds, fs in os.walk(p):
                for f in fs:
                    closure.note(os.path.join(dd, f))


STEP_DEPTH = 2      # a venv step's code: its functions and `modules`, two imports deep. Whole and transitive, every step
                    # reached all of charkit, so any edit anywhere re-ran the head, body and hair fits (minutes a
                    # build in every worktree). Deeper changes can restore a stale product: the gate's builds are
                    # cold, and `--cache verify` re-runs everything and flags a difference.


def step_dir():
    """where the venv steps' entries live (file_step): CHARKIT_STEP_CACHE, else the build cache (cache_dir()). The gate
    points its builds at one folder on the box (gate._build: ~/.cache/charkit/steps), so its clones share them; their
    keys and reads are portable (_port), so an entry made in one clone's worktree and out folder hits in another's."""
    return os.path.abspath(os.path.expanduser(os.environ.get('CHARKIT_STEP_CACHE') or cache_dir()))


def step_depth():
    """how deep a venv step's code key follows imports: CHARKIT_STEP_DEPTH ('all': every function reached, as the
    Blender stages' keys do; the gate's builds, whose entries are shared), default STEP_DEPTH."""
    v = os.environ.get('CHARKIT_STEP_DEPTH')
    return STEP_DEPTH if not v else None if v == 'all' else int(v)


def _port_prefixes(build_out):
    """(absolute prefix, portable prefix), longest first: the build's out folder as '<out>/', the worktree (as named
    and resolved) and each link in its charkit/out (the gate's gate folder, resolved) relative to it."""
    from . import closure
    with closure.paused():                          # (a look at the worktree's links, not an input)
        pre = [(p, r) for p, r in closure._prefixes(ROOT)]
    if build_out:
        b = os.path.abspath(build_out).rstrip(os.sep) + os.sep
        pre += [(b, '<out>/'), (os.path.realpath(b).rstrip(os.sep) + os.sep, '<out>/')]
    return sorted(set(pre), key=lambda x: -len(x[0]))


def _port(v, pre):
    """v with every absolute path under a prefix made portable (strings in dicts, lists and tuples)."""
    if isinstance(v, str):
        if v.startswith(os.sep):
            for a, r in pre:
                if v.startswith(a) or v == a[:-1]:
                    return r + v[len(a):]
        return v
    if isinstance(v, dict):
        return {k: _port(x, pre) for k, x in dict.items(v)}
    if isinstance(v, (list, tuple)):
        return type(v)(_port(x, pre) for x in v)
    return v


def _unport(p, build_out):
    """a portable path back to this build's: '<out>/x' under build_out, a relative one under the worktree."""
    if p.startswith('<out>/'):
        return os.path.join(build_out, p[len('<out>/'):])
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def file_step(name, run, fns, key, out, inputs=(), modules=(), name_key=None, refresh=False, depth=None,
              build_out=None, verify=False):
    """a venv-side step whose product is files under `out` (the geom hair cut, before Blender): restored by copying them
    when its code (fns and `modules` with what they import, `depth` imports deep: step_depth()), the venv's packages,
    `key` (what it is given, exactly), the content of `inputs` and of every file it opened are unchanged. Paths in the
    key, the inputs and the reads are keyed portably (the build's out folder, build_out, default out's parent when out
    is its geom folder, as '<out>/'; the worktree's relative), so entries hit across worktrees and gate clones (step_dir()).
    A hit records what the step depends on in the build's input closure (charkit.closure: the files it would have read
    and its code), as the step itself would have. verify (a build's --cache verify): the entry a lookup would restore
    isn't; the step runs and its products are compared with the entry's (same_product): CHARKIT_CACHE_STALE when they
    differ, the entry replaced. -> 'hit' | 'miss: why' | 'verified' | 'stale: files'."""
    global _REC
    d = step_dir()
    files = Files(d)
    t0 = time.time()
    depth = step_depth() if depth is None else depth
    if build_out is None:
        build_out = os.path.dirname(os.path.abspath(out)) if os.path.basename(os.path.normpath(out)) == 'geom' else out
    build_out = os.path.abspath(build_out)
    pre = _port_prefixes(build_out)
    units = code_units(*fns, modules=('charkit.cache',) + tuple(modules), depth=depth)
    units['charkit/assets'] = files.get(os.path.join(KIT, 'assets'))
    units = dict(sorted(units.items()))
    envv = venv_env()
    static = digest([SCHEMA, 'venv', name, units, envv, _port(key, pre),
                     sorted((_port(os.path.abspath(p), pre), files.get(p)) for p in inputs)])
    kd = os.path.join(d, 'venv', name, static[:20])
    ran_why = was = None
    for c in _entries(kd) if not refresh else []:
        try:
            E = Entry(c)
            if all(files.get(_unport(p, build_out)) == h for p, h in E.m['reads']):
                # (the code the step ran, recorded as it ran: what the key's static walk can't see; a change there,
                # or an entry with no record, is a miss and the entry goes: 2026-10-01's stale baseline hull)
                ran_why = ran_changed(E.m.get('ran'))
                if ran_why is not None:
                    shutil.rmtree(E.dir, ignore_errors=True)
                    continue
                if verify:
                    was = E                             # (what a lookup would restore: compared after the run)
                    break
                for rel in E.m['files']:
                    dst = os.path.join(out, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copyfile(os.path.join(E.dir, 'files', rel), dst)
                for line in E.m['stdout']:
                    print(line.replace(E.m.get('out', '\0'), os.path.abspath(out)))
                os.utime(E.file('manifest.json'))
                files.save()
                _closure_note([_unport(p, build_out) for p, _ in E.m['reads']] + list(inputs) +
                              sorted({os.path.join(ROOT, u.split(':', 1)[0]) for u in units}))
                return 'hit'
        except (OSError, ValueError, KeyError):
            continue
    why = 'refresh' if refresh else ('code it ran changed: %s' % ran_why) if ran_why else 'file changed' \
        if _entries(kd) else 'no entry'
    last = os.path.join(d, 'last', 'venv_%s_%s.json' % (name, name_key or 'build'))
    try:
        L = json.load(open(last))
        ch = [u for u in sorted(set(L['units']) | set(units)) if L['units'].get(u) != units.get(u)]
        why = 'code ' + ', '.join(ch[:3]) if ch else 'packages' if L['env'] != envv else 'its input changed' \
            if L['key'] != digest(_port(key, pre)) else why
    except (OSError, ValueError, KeyError):
        pass
    _hook()
    rec = Recorder(types.SimpleNamespace(watch=lambda p: not p.endswith(('.py', '.pyc', '.so', '.dylib')) and
                                         not p.startswith(_skip_prefixes() + (os.path.abspath(d) + os.sep,)) and
                                         (not p.startswith(KIT + os.sep) or p.startswith(os.path.join(KIT, 'out') + os.sep))
                                         and not p.startswith(os.path.abspath(out) + os.sep)), name, None, None)
    rec.files_only = True
    before = _tree(out)
    lines, errs = [], []
    _REC = rec
    try:
        with _tee(lines, errs), ran() as R:
            run()
    finally:
        _REC = None
    after = _tree(out)
    outs = sorted(k for k, v in after.items() if before.get(k) != v)
    verdict = None
    if was is not None:
        bad = sorted(set(was.m['files']) ^ set(outs)) + [
            rel for rel in sorted(set(was.m['files']) & set(outs))
            if not same_product(os.path.join(was.dir, 'files', rel), os.path.join(out, rel))]
        verdict = ('stale: ' + ', '.join(bad[:6])) if bad else 'verified'
        if bad:
            print('CHARKIT_CACHE_STALE step %s: %s (made %s)' % (name, ', '.join(bad[:6]), was.m.get('created')),
                  flush=True)
            shutil.rmtree(was.dir, ignore_errors=True)  # (this run's own takes its place)
        else:
            return verdict
    reads = sorted((_port(p, pre), files.get(p)) for p in rec.files)
    key2 = digest([static, reads])
    from . import closure
    with closure.paused():
        edited = any(os.stat(os.path.join(dd, f)).st_mtime > t0 for dd, ds, fs in os.walk(KIT) for f in fs
                     if f.endswith('.py') and not dd.startswith((os.path.join(KIT, 'out'), os.path.join(KIT, 'tests'))))
    if edited:
        return 'miss: charkit changed during the step (not stored)'
    if _caught(errs):
        return 'miss: %s (an error was caught while it ran: not stored)' % why
    if '<unrecorded>' in R:
        return 'miss: %s (the code it ran was not recorded, %s: not stored)' % (why, R['<unrecorded>'])
    os.makedirs(d, exist_ok=True)                   # (room() asks its disk: a new shared folder has none yet)
    if not room(d):
        return 'miss: %s (the disk is nearly full: not stored)' % why
    tmp = tempfile.mkdtemp(prefix='.w-', dir=d)
    try:
        for rel in outs:
            dst = os.path.join(tmp, 'files', rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(os.path.join(out, rel), dst)
        _write_json(os.path.join(tmp, 'manifest.json'), dict(schema=SCHEMA, kind='venv', step=name, static=static, units=units,
                                                             env=envv, reads=reads, files=outs, out=os.path.abspath(out),
                                                             ran=R,
                                                             created=time.strftime('%Y-%m-%dT%H:%M:%S'),
                                                             stdout=[l for l in lines if l.startswith(('geom ', 'CHARKIT_'))]))
        final = os.path.join(kd, key2[:24])
        os.makedirs(kd, exist_ok=True)
        try:
            os.rename(tmp, final)
        except OSError:
            shutil.rmtree(tmp, ignore_errors=True)
        _write_json(last, dict(units=units, env=envv, key=digest(_port(key, pre))))
        files.save()
        if d != os.path.abspath(cache_dir()):
            prune(d, step_cap_gb())                 # (a folder of its own: no build's finish trims it)
    except OSError as e:
        shutil.rmtree(tmp, ignore_errors=True)
        return 'miss: %s (storing it failed: %s)' % (why, e)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return verdict or 'miss: ' + why


# ------------------------------------------------------------------------------------------------------ venv QA parts
_VMEMO = {}                              # this process's venv memo results by key (a fresh copy per call)
_T0 = time.time()                        # when this process loaded charkit: a source edited after it isn't what runs


def kit_edited(t0=None):
    """a charkit source changed since t0 (default: since this process loaded charkit) -> its path, or None."""
    t0 = _T0 if t0 is None else t0
    from . import closure
    with closure.paused():
        return _kit_edited(t0)


def _kit_edited(t0):
    for dd, ds, fs in os.walk(KIT):
        if dd.startswith((os.path.join(KIT, 'out'), os.path.join(KIT, 'tests'))):
            ds[:] = []
            continue
        for f in fs:
            if f.endswith('.py') and os.stat(os.path.join(dd, f)).st_mtime > t0:
                return os.path.relpath(os.path.join(dd, f), ROOT)
    return None


def venv_memo(fn, *args, **kw):
    """memo() for the venv (the QA on a bundle, charkit/qa3d.py): fn(*args, **kw) kept on disk under memo/ by its code,
    the venv's packages and its arguments' digest; each call returns a fresh copy. CHARKIT_CACHE=off (a --cache off
    build): computed once in this process and kept in memory only (2026-10-01: computing it at every call of a pass
    cost a cold build 60 s more)."""
    off = os.environ.get('CHARKIT_CACHE') == 'off'
    units = code_units(fn)
    key = digest([SCHEMA, 'venv', units, venv_env(), args, kw])[:24]
    p = os.path.join(cache_dir(), 'memo', '%s.%s' % (fn.__module__, fn.__name__), key + '.pkl')
    if key in _VMEMO:
        return pickle.loads(_VMEMO[key])
    if off:
        out = fn(*args, **kw)
        try:
            _VMEMO[key] = pickle.dumps(out, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            pass
        return out
    if os.path.exists(p):
        try:
            blob = _read_state(p)
            out = pickle.loads(blob)
            os.utime(p)
            _VMEMO[key] = blob
            return out
        except Exception:
            pass
    out = fn(*args, **kw)
    try:
        blob = pickle.dumps(out, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception:
        return out
    _VMEMO[key] = blob
    if room(cache_dir()):
        tmp = '%s.%d.tmp' % (p, os.getpid())
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            _write_state(tmp, blob)
            os.replace(tmp, p)
        except OSError:
            if os.path.exists(tmp):
                os.remove(tmp)
    return out


def qa_part(name, fn, B, design, out, args=(), mode='on'):
    """a venv QA part, fn(B, design, out, *args) -> (table, checks), run or restored (with the files it wrote under
    out). Its key is what it read, recorded as it ran: the bundle's arrays and metadata paths it touched (by the
    hashes the bundle carries), the reference files the design side opened for it (by content), its code (fn and every
    charkit module it imports) and the venv's packages. A lookup restores the first stored entry whose reads all match
    the bundle and files as they are now; a run that printed a traceback isn't stored. mode: on, off, refresh, verify
    (run it and compare with the entry a lookup would restore: CHARKIT_CACHE_STALE when they differ)."""
    from . import trace
    t = time.perf_counter()
    d = cache_dir()
    files = Files(d)
    if (fn.__module__ or '').startswith('charkit'):
        units = code_units(fn, modules=('charkit.bundle',))
    else:                                               # (a function from outside charkit: its own source)
        import inspect
        units = dict(code_units(modules=('charkit.bundle',)), **{'<%s>' % fn.__qualname__: digest(inspect.getsource(fn))})
    # (the QA's drawing: imported by name, so this module's import closure, which every stage's code key follows,
    # doesn't take in the QA through qarender; the part's own closure has it, through qa3d)
    import importlib
    qarender = importlib.import_module(__package__ + '.qarender')
    static = digest([SCHEMA, 'qa', name, units, venv_env(), args] + qarender.cache_key())
    kd = os.path.join(d, 'qa', name, static[:20])
    E, why = None, 'no entry' if mode in ('on', 'verify') else 'cache %s' % mode
    if mode in ('on', 'verify'):
        for c in _entries(kd):
            try:
                E_ = Entry(c)
                R = E_.m['reads']
                bad = next((k for k, h in R['arrays'] if not B.has(k) or B.hash_of(k) != h), None) or \
                    next(('/'.join(p) for p, h in R['meta'] if B.hash_of(tuple(p)) != h), None) or \
                    next((p for p, h in R['files'] if files.get(p) != h), None) or \
                    (lambda u: u and 'the code it ran: %s' % u)(ran_changed(E_.m.get('ran')))
                if bad is None:
                    E = E_
                    break
                why = 'changed: %s' % bad
            except (OSError, ValueError, KeyError):
                continue
        if E is None and why == 'no entry' and os.path.isdir(os.path.join(d, 'qa', name)) and not _entries(kd):
            why = 'code or packages changed'
    if E is not None and mode == 'on':
        try:
            for rel in E.m['files']:
                dst = os.path.join(out, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(os.path.join(E.dir, 'files', rel), dst)
            result = pickle.loads(_read_state(E.file('state.pkl')))
            os.utime(E.file('manifest.json'))
            files.save()
            trace.event('part', name, dt=round(time.perf_counter() - t, 4), cache={'hit': True, 'key': E.id[:12]},
                        where='venv')
            return result
        except (OSError, ValueError, KeyError, pickle.UnpicklingError, EOFError) as e:
            why = 'its entry did not restore (%s)' % e
            shutil.rmtree(E.dir, ignore_errors=True)
            E = None
    before = _tree(out) if out else {}
    lines, errs = [], []
    with B.recording() as rd, _tee(lines, errs), ran() as ran_rec:
        result = fn(B, design, out, *args)
    after = _tree(out) if out else {}
    outs = sorted(k for k, v in after.items() if before.get(k) != v and k != 'qa.json')
    info = {'hit': False, 'why': why}
    if mode == 'verify' and E is not None:
        bad = [rel for rel in sorted(set(E.m['files']) | set(outs)) if E.m['digests'].get(rel) !=
               (content_digest(os.path.join(out, rel)) if rel in outs else None)]
        try:
            if digest(pickle.loads(_read_state(E.file('state.pkl')))) != digest(result):
                bad.append('its result')
        except Exception as e:
            bad.append('its stored state does not load: %s' % e)
        info['verified'] = not bad
        if bad:
            info['stale'] = bad[:6]
            print('CHARKIT_CACHE_STALE %s: %s' % (name, ', '.join(bad[:6])))
    edited = kit_edited() if mode != 'off' else None
    def stale(final):
        try:
            return ran_changed(Entry(final).m.get('ran')) is not None
        except (OSError, ValueError, KeyError):
            return True
    if mode != 'off' and not _caught(errs) and room(d) and not edited and '<unrecorded>' not in ran_rec:
        reads = dict(arrays=sorted([k, B.hash_of(k)] for k in rd.arrays),
                     meta=sorted([list(p), B.hash_of(p)] for p in rd.meta),
                     files=sorted([p, files.get(p)] for p in rd.files))
        key = digest([static, reads])[:24]
        final = os.path.join(kd, key)
        if not os.path.exists(final) or mode == 'refresh' or stale(final):
            tmp = tempfile.mkdtemp(prefix='.w-', dir=d)
            try:
                for rel in outs:
                    dst = os.path.join(tmp, 'files', rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copyfile(os.path.join(out, rel), dst)
                _write_state(os.path.join(tmp, 'state.pkl'), pickle.dumps(result, protocol=pickle.HIGHEST_PROTOCOL))
                _write_json(os.path.join(tmp, 'manifest.json'), dict(
                    schema=SCHEMA, kind='qa', step=name, static=static, units=units, env=venv_env(), reads=reads,
                    ran=ran_rec, files=outs, digests={rel: content_digest(os.path.join(out, rel)) for rel in outs},
                    created=time.strftime('%Y-%m-%dT%H:%M:%S')))
                os.makedirs(kd, exist_ok=True)
                if os.path.exists(final):
                    shutil.rmtree(final, ignore_errors=True)
                try:
                    os.rename(tmp, final)
                except OSError:
                    shutil.rmtree(tmp, ignore_errors=True)
            except (OSError, pickle.PicklingError, TypeError) as e:
                shutil.rmtree(tmp, ignore_errors=True)
                info.update(stored=False, uncacheable='storing it failed: %s' % e)
        files.save()
    elif mode != 'off':
        info.update(stored=False, uncacheable='%s changed during the QA' % edited if edited else
                    'an error was caught while it ran' if _caught(errs) else
                    'the code it ran was not recorded (%s)' % ran_rec['<unrecorded>'] if '<unrecorded>' in ran_rec
                    else 'the disk is full')
    trace.event('part', name, dt=round(time.perf_counter() - t, 4), cache=info, where='venv')
    return result


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
    # (not the scene's total object count: that is upstream's, e.g. the hair stage's cap exists in one hair mode and not
    # the other, while this stage's own effect is pinned by what it added, changed and removed; a stray object a restore
    # made would show as added)
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
def _tee(lines, errs=None):
    """copy stdout's lines into `lines` (and stderr's into `errs`) while still printing them."""
    def tee(real, into):
        class T:
            buf = ''

            def write(self, s):
                real.write(s)
                self.buf += s
                while '\n' in self.buf:
                    l, self.buf = self.buf.split('\n', 1)
                    into.append(l)
                return len(s)

            def flush(self):
                real.flush()

            def __getattr__(self, k):
                return getattr(real, k)
        return T()
    old = sys.stdout, sys.stderr
    sys.stdout = tee(old[0], lines)
    if errs is not None:
        sys.stderr = tee(old[1], errs)
    try:
        yield lines
    finally:
        sys.stdout, sys.stderr = old


def _caught(lines):
    """a traceback printed while a step ran (an exception it caught and reported, a check SKIPPED on an error): what it
    made then isn't stored (a full disk, a missing file, a crash in a check must not come back from the cache)."""
    return any(l.startswith('Traceback (most recent call last)') for l in lines)


def content_digest(p):
    """a file's content digest; a PNG's without its text and time chunks (Blender stamps each render with the date)."""
    if p.endswith('.png'):
        try:
            b = open(p, 'rb').read()
            h, i = hashlib.sha256(b[:8]), 8
            while i + 8 <= len(b):
                n = struct.unpack('>I', b[i:i + 4])[0]
                t = b[i + 4:i + 8]
                if t not in (b'tEXt', b'zTXt', b'iTXt', b'tIME'):
                    h.update(b[i + 4:i + 8 + n])
                i += 12 + n
            return 'png:' + h.hexdigest()
        except (OSError, struct.error):
            pass
    try:
        with open(p, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return 'absent'


def same_product(a, b):
    """two products' files the same? An .npz by its arrays (its zip members carry the time it was written), anything
    else by content_digest."""
    if a.endswith('.npz') and b.endswith('.npz'):
        try:
            A, B = np.load(a, allow_pickle=False), np.load(b, allow_pickle=False)
            if sorted(A.files) != sorted(B.files):
                return False
            for k in A.files:
                x, y = A[k], B[k]
                if x.dtype != y.dtype or x.shape != y.shape or not np.array_equal(
                        x, y, equal_nan=x.dtype.kind in 'fc'):
                    return False
            return True
        except (OSError, ValueError):
            pass
    return content_digest(a) == content_digest(b)


def room(d, need_gb=None):
    """is there room to store an entry (CHARKIT_CACHE_MIN_FREE_GB, default 2, left free on the disk)?"""
    need = float(os.environ.get('CHARKIT_CACHE_MIN_FREE_GB', 2)) if need_gb is None else need_gb
    try:
        return shutil.disk_usage(d).free > need * 1e9
    except OSError:
        return False


def _write_state(path, blob):
    """a state pickle, zlib-compressed (level 1) when large."""
    import zlib
    if len(blob) > 4 << 20:
        blob = b'CKZ1' + zlib.compress(blob, 1)
    with open(path, 'wb') as f:
        f.write(blob)


def _read_state(path):
    import zlib
    with open(path, 'rb') as f:
        b = f.read()
    return zlib.decompress(b[4:]) if b[:4] == b'CKZ1' else b


# ------------------------------------------------------------------------------------------------------------ upkeep
def _ls(d):
    try:
        return os.listdir(d)
    except OSError:
        return []


def entries(d=None):
    """every entry: (kind, step, path, bytes, last used)."""
    d = d or cache_dir()
    out = []
    for kind in ('stages', 'products', 'parts', 'venv', 'qa'):
        base = os.path.join(d, kind)
        if not os.path.isdir(base):
            continue
        for step in sorted(_ls(base)):
            for sk in _ls(os.path.join(base, step)):
                for e in _ls(os.path.join(base, step, sk)):
                    p = os.path.join(base, step, sk, e)
                    m = os.path.join(p, 'manifest.json')
                    try:            # (another build may prune it meanwhile: a shared folder)
                        size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(p) for f in fs)
                        out.append((kind, step, p, size, os.path.getmtime(m)))
                    except OSError:
                        pass
    base = os.path.join(d, 'memo')
    if os.path.isdir(base):
        for step in sorted(_ls(base)):
            for f in _ls(os.path.join(base, step)):
                p = os.path.join(base, step, f)
                try:
                    out.append(('memo', step, p, os.path.getsize(p), os.path.getmtime(p)))
                except OSError:
                    pass
    return out


def prune(d=None, cap_gb=None):
    """drop the least recently used entries until the cache is under its size cap (CHARKIT_CACHE_GB, default 5)."""
    es = sorted(entries(d), key=lambda e: e[4])
    total = sum(e[3] for e in es)
    cap = (cap_gb or max_gb()) * 1e9
    while es and total > cap:
        e = es.pop(0)
        if os.path.isdir(e[2]):
            shutil.rmtree(e[2], ignore_errors=True)
        elif os.path.exists(e[2]):
            os.remove(e[2])
        total -= e[3]


def size_line(d=None, es=None):
    """'build cache: 1.23 GB of 5 GB, 40 entries (charkit/out/.cache); 8.4 GB free on the disk'."""
    d = d or cache_dir()
    es = entries(d) if es is None else es
    try:
        free = '; %.1f GB free on the disk' % (shutil.disk_usage(d if os.path.exists(d) else ROOT).free / 1e9)
    except OSError:
        free = ''
    return 'build cache: %.2f GB of %g GB, %d entries (%s)%s' % (sum(e[3] for e in es) / 1e9, max_gb(), len(es),
                                                                os.path.relpath(d, ROOT), free)


def main(args):
    d = cache_dir()
    if not args or args[0] == 'info':
        es = entries(d)
        by = {}
        for kind, step, p, size, t in es:
            b = by.setdefault((kind, step), [0, 0, 0])
            b[0] += 1; b[1] += size; b[2] = max(b[2], t)
        print(size_line(d, es))
        for (kind, step), (n, size, t) in sorted(by.items()):
            print('  %-9s %-14s %3d entries %8.1f MB  last used %s' % (kind, step, n, size / 1e6,
                                                                       time.strftime('%Y-%m-%d %H:%M', time.localtime(t))))
    elif args[0] == 'clear':
        for k in ('stages', 'products', 'parts', 'venv', 'qa', 'memo', 'last'):
            shutil.rmtree(os.path.join(d, k), ignore_errors=True)
        print('cleared', d)
    else:
        raise SystemExit(__doc__)
