"""Geometry truth (docs/GEOM_TRUTH.md): a build stage's geometry is computed once, venv-side, and saved as a product
(arrays and a JSON record); Blender only instantiates meshes, materials and modifiers from it; the evaluator
(charkit.bodyeval) makes the same product in memory, so the two agree by construction. The garments are the pilot.

    P = garments_product(A, specs, hull, spec)       # venv: every garment as garments.build makes it, recorded
    save(P, 'OUT/geom/garments.npz'); P = load(path)
    obs = replay(P, C)                                # Blender: the objects, materials, modifiers and the skin mask
    parts = pieces(P)                                 # the evaluator's view: per object its mesh, materials, modifiers

Recording. garments.build talks to Blender through a few functions only, its seam (SEAM): garments._object, _toon,
_toon_tex and mask_skin, eyetex.to_blender_image and shade.outline, plus an object's modifiers.new(...) with the
settings it sets and its custom properties. record() runs build() venv-side with the seam replaced by recorders, so
build()'s own code decides every piece's geometry, materials and modifiers; replay() calls the real functions with what
was recorded, in the recorded order, in Blender, and so makes the same objects build() would have made there. Anything
else build() asks of Blender fails the recording loudly (SeamError): route it through the seam, or keep it out of
build(). The builders' math is untouched: this only moves where it runs.

The product (one .npz, schema charkit.geomstage/1): `meta` (JSON: the schema, the stage, what it was computed from,
and `events`, the recorded calls in order, values inline and arrays by name) and the arrays ('a/<n>'). An event is
    ['call', id, fn, args, kwargs]    a seam function called (its result named id)
    ['mod', id, object id, name, type] an object's modifiers.new(name, type)
    ['set', target id, attr, value]   a setting on a modifier
    ['item', target id, key, value]   an object's custom property
Values: JSON scalars and lists; {'$t': [...]} a tuple; {'$a': n} an array; {'$p': n} polygons (a list of index tuples:
arrays n/loopv, n/counts); {'$c': n} per-polygon corner values (uv_corner: n/values, n/counts); {'$d': {...}} a dict
with non-string keys kept as pairs; {'$r': id} a recorded object (the armature and skin are 'arm' and 'skin').
"""
import hashlib, json, os

import numpy as np

SCHEMA = 'charkit.geomstage/1'
SEAM = (('charkit.garments', '_object'), ('charkit.garments', '_toon'), ('charkit.garments', '_toon_tex'),
        ('charkit.garments', 'mask_skin'), ('charkit.eyetex', 'to_blender_image'), ('charkit.shade', 'outline'))


class SeamError(RuntimeError):
    """build() asked Blender for something outside the recorded seam."""


# ------------------------------------------------------------------------------------------------------------ recording
_IMAGES = {}             # recorded images by content (a fit re-records a skirt for every body: one copy of its texture)


def _intern(img):
    a = np.ascontiguousarray(np.asarray(img, np.float32))       # (to_blender_image writes float32 pixels)
    k = hashlib.sha1(a.tobytes()).hexdigest() + str(a.shape)
    if k not in _IMAGES:
        if len(_IMAGES) >= 16:
            _IMAGES.pop(next(iter(_IMAGES)))
        a.setflags(write=False)
        _IMAGES[k] = a
    return _IMAGES[k]


class _Rec:
    """one recording: the events in order (values encoded as they are recorded: a snapshot, whatever build() does to its
    arrays afterwards) and their arrays."""

    def __init__(self):
        self.events, self.arrays = [], {}
        self.n = 0

    def name(self, kind):
        self.n += 1
        return '%s%d' % (kind, self.n)

    def enc(self, x):
        return _enc(x, self)


class _Ref:
    """a recorded Blender datablock (a material, an image, a modifier): opaque to build(), which passes it on."""

    def __init__(self, rec, id_, what):
        object.__setattr__(self, '_rec', rec)
        object.__setattr__(self, '_id', id_)
        object.__setattr__(self, '_what', what)

    def __getattr__(self, k):
        raise SeamError('garments.build read %s.%s from Blender (outside the recorded seam, charkit.geomstage.SEAM)'
                        % (self._what, k))

    def __setattr__(self, k, v):
        raise SeamError('garments.build set %s.%s in Blender (outside the recorded seam)' % (self._what, k))


class _ModRef(_Ref):
    """a recorded modifier: its settings recorded as build() sets them."""

    def __setattr__(self, k, v):
        self._rec.events.append(['set', self._id, k, self._rec.enc(v)])


class _Mods:
    def __init__(self, rec, ob_id):
        self._rec, self._ob = rec, ob_id

    def new(self, name, type):
        i = self._rec.name('m')
        self._rec.events.append(['mod', i, self._ob, name, type])
        return _ModRef(self._rec, i, 'modifier %s' % name)

    def __getattr__(self, k):
        raise SeamError('garments.build used modifiers.%s (only modifiers.new is recorded)' % k)


class _ObRef(_Ref):
    """a recorded object: modifiers.new and custom properties are recorded; anything else is outside the seam."""

    def __init__(self, rec, id_, what):
        super().__init__(rec, id_, what)
        object.__setattr__(self, 'modifiers', _Mods(rec, id_))

    def __setitem__(self, k, v):
        self._rec.events.append(['item', self._id, k, self._rec.enc(v)])


def _recorder(rec, fn, make=_Ref):
    def call(*args, **kw):
        i = rec.name('c')
        if fn == 'to_blender_image':                         # the pixels as Blender takes them (float32), shared
            args = list(args)
            if len(args) > 1:
                args[1] = _intern(args[1])
            elif 'rgba' in kw:
                kw = dict(kw, rgba=_intern(kw['rgba']))
        rec.events.append(['call', i, fn, rec.enc(list(args)), rec.enc(dict(kw))])
        return make(rec, i, fn)
    return call


class recording:
    """with recording() as rec: garments.build(...) runs with the seam recorded (rec.events, rec.arrays)."""

    def __init__(self):
        self.rec = _Rec()
        self.saved = []

    def __enter__(self):
        from . import eyetex, garments, shade
        mods = {'charkit.garments': garments, 'charkit.eyetex': eyetex, 'charkit.shade': shade}
        makes = {'_object': _ObRef, 'outline': _ModRef}
        for mod, fn in SEAM:
            M = mods[mod]
            self.saved.append((M, fn, getattr(M, fn)))
            setattr(M, fn, _recorder(self.rec, fn, makes.get(fn, _Ref)))
        return self.rec

    def __exit__(self, *exc):
        for M, fn, f in reversed(self.saved):
            setattr(M, fn, f)
        self.saved = []
        return False


def record(A, specs, hull=None, spec_all=None, line=None):
    """garments.build on assembly A (numpy, no Blender) with its seam recorded. The skin and armature are stand-ins:
    build() hands them to the seam and must not touch them itself. -> the recording (events, arrays)."""
    from . import garments
    with recording() as rec:
        C = {'data': A, 'arm': _Ref(rec, 'arm', 'the armature'), 'skin': _Ref(rec, 'skin', 'the skin')}
        kw = {} if line is None else {'line': line}
        garments.build(C, specs, hull=hull, spec_all=spec_all, **kw)
    return rec


# -------------------------------------------------------------------------------------------------------- the product
def _is_num(e):
    return isinstance(e, (int, float, np.integer, np.floating, bool, np.bool_))


def _enc(x, rec):
    """a recorded value as JSON, its arrays copied into rec.arrays (see the module)."""
    A = rec.arrays
    if isinstance(x, _Ref):
        return {'$r': x._id}
    if isinstance(x, np.ndarray):
        n = rec.name('a')
        A[n] = x if not x.flags.writeable else x.copy()
        return {'$a': n}
    if isinstance(x, (np.floating, np.integer, np.bool_)):
        return x.item()
    if isinstance(x, dict):
        if all(isinstance(k, str) for k in x):
            return {k: _enc(v, rec) for k, v in x.items()}
        return {'$d': [[_enc(k, rec), _enc(v, rec)] for k, v in x.items()]}
    if isinstance(x, (list, tuple)):
        if len(x) > 8 and all(isinstance(e, (list, tuple, np.ndarray)) for e in x):
            first = np.asarray(x[0])
            if first.ndim == 1 and len(first) and np.issubdtype(first.dtype, np.integer) and \
                    all(len(e) and all(isinstance(v, (int, np.integer)) for v in e) for e in x):      # polygons
                n = rec.name('p')
                A[n + '/loopv'] = np.concatenate([np.asarray(f, np.int64) for f in x])
                A[n + '/counts'] = np.array([len(f) for f in x], np.int32)
                return {'$p': n, 'tuple': isinstance(x[0], tuple)}
            if first.ndim == 1 and all(len(e) == len(first) and all(_is_num(v) for v in e) for e in x):   # rows
                n = rec.name('a')
                A[n] = np.array([[float(v) for v in e] for e in x])
                return {'$a': n, 'rows': 'tuple' if isinstance(x[0], tuple) else 'list'}
            if first.ndim == 2:                                                    # per-polygon corner values
                n = rec.name('c')
                A[n + '/values'] = np.concatenate([np.asarray(f, float) for f in x])
                A[n + '/counts'] = np.array([len(f) for f in x], np.int32)
                return {'$c': n}
        if len(x) > 64 and all(_is_num(e) for e in x):
            n = rec.name('a')
            A[n] = np.asarray(x)
            return {'$a': n, 'list': True}
        v = [_enc(e, rec) for e in x]
        return {'$t': v} if isinstance(x, tuple) else v
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    raise TypeError('geomstage: cannot record a %s' % type(x).__name__)


def _dec(x, arrays, refs=None):
    """a recorded value back: arrays as saved, polygons as a list of tuples, references through `refs` (id -> object)."""
    if isinstance(x, list):
        return [_dec(e, arrays, refs) for e in x]
    if not isinstance(x, dict):
        return x
    if '$r' in x:
        return refs[x['$r']] if refs is not None else x
    if '$a' in x:
        a = arrays[x['$a']]
        if x.get('list'):
            return a.tolist()
        if x.get('rows'):
            mk = tuple if x['rows'] == 'tuple' else list
            return [mk(r) for r in a.tolist()]
        return a
    if '$t' in x:
        return tuple(_dec(e, arrays, refs) for e in x['$t'])
    if '$p' in x:
        lv, ct = arrays[x['$p'] + '/loopv'], arrays[x['$p'] + '/counts']
        st = np.r_[0, np.cumsum(ct)[:-1]]
        mk = tuple if x.get('tuple') else list
        return [mk(int(v) for v in lv[s:s + c]) for s, c in zip(st, ct)]
    if '$c' in x:
        vals, ct = arrays[x['$c'] + '/values'], arrays[x['$c'] + '/counts']
        st = np.r_[0, np.cumsum(ct)[:-1]]
        return [[tuple(c) for c in vals[s:s + n].tolist()] for s, n in zip(st, ct)]
    if '$d' in x:
        return {_dec(k, arrays, refs): _dec(v, arrays, refs) for k, v in x['$d']}
    return {k: _dec(v, arrays, refs) for k, v in x.items()}


def product(stage, rec, meta=None, checks=None):
    """a product in memory from a recording: -> dict(meta (JSON-able: schema, stage, events), arrays {name: array})."""
    arrays = dict(rec.arrays)
    for k, v in (checks or {}).items():
        arrays['check/' + k] = np.asarray(v)
    return dict(meta=dict(meta or {}, schema=SCHEMA, stage=stage, events=rec.events), arrays=arrays)


def save(P, path):
    """a product to one .npz (compressed); written to a temporary name first, so a reader never sees half a file."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + '.tmp.npz'
    arrays = {('a/' + k): v for k, v in P['arrays'].items()}
    np.savez_compressed(tmp, meta=np.array(json.dumps(P['meta'], sort_keys=True)), **arrays)
    os.replace(tmp, path)
    return path


def load(path):
    """-> the product saved at path (the arrays loaded)."""
    Z = np.load(path, allow_pickle=False)
    meta = json.loads(str(Z['meta']))
    if meta.get('schema') != SCHEMA:
        raise ValueError('%s: schema %s, not %s' % (path, meta.get('schema'), SCHEMA))
    return dict(meta=meta, arrays={k[2:]: Z[k] for k in Z.files if k.startswith('a/')})


def digest(P):
    """a product's content hash (its events and arrays)."""
    h = hashlib.sha1(json.dumps(P['meta']['events'], sort_keys=True).encode())
    for k in sorted(P['arrays']):
        a = np.ascontiguousarray(P['arrays'][k])
        h.update(k.encode()); h.update(str(a.dtype).encode()); h.update(str(a.shape).encode()); h.update(a.tobytes())
    return h.hexdigest()[:16]


# ------------------------------------------------------------------------------------------------------------ Blender
def replay(P, C):
    """Blender: the recorded calls made for real, in order, onto character C (charkit.character.build's: its 'arm' and
    'skin'). -> the objects garments.build would have returned."""
    from . import eyetex, garments, shade              # (named, so the stage cache's code closure holds the seam)
    mods = {'charkit.garments': garments, 'charkit.eyetex': eyetex, 'charkit.shade': shade}
    fns = {fn: getattr(mods[m], fn) for m, fn in SEAM}
    arrays = P['arrays']
    refs = {'arm': C['arm'], 'skin': C['skin']}
    obs = []
    for e in P['meta']['events']:
        if e[0] == 'call':
            _, i, fn, args, kw = e
            r = fns[fn](*_dec(args, arrays, refs), **_dec(kw, arrays, refs))
            refs[i] = r
            if fn == '_object':
                obs.append(r)
        elif e[0] == 'mod':
            _, i, ob, name, type_ = e
            refs[i] = refs[ob].modifiers.new(name, type_)
        elif e[0] == 'set':
            setattr(refs[e[1]], e[2], _dec(e[3], arrays, refs))
        elif e[0] == 'item':
            refs[e[1]][e[2]] = _dec(e[3], arrays, refs)
        else:
            raise ValueError('geomstage: unknown event %r' % (e[0],))
    return obs


# ----------------------------------------------------------------------------------------------- the evaluator's view
def pieces(P):
    """the product as the evaluator reads it: per object made (in order) dict(name, V, polys, uv (per vertex) or
    uv_corner (per polygon's corners), mat_idx, smooth, materials [dict(fn 'toon'|'toon_tex', name, color or image
    (float, row 0 = top), shade (the multiplier or None))], mods {name: dict(type, settings)}, props {key: value},
    outline (the call's kwargs)) and the skin's hidden vertices: -> (objects, hide (N,) bool or None)."""
    arrays = P['arrays']
    made = {}
    obs, hide = [], None
    for e in P['meta']['events']:
        if e[0] == 'call':
            _, i, fn, args, kw = e
            a = _dec(args, arrays)
            k = _dec(kw, arrays)
            if fn == 'to_blender_image':
                made[i] = dict(fn='image', name=a[0], rgba=a[1] if len(a) > 1 else k['rgba'])
            elif fn == '_toon':
                made[i] = dict(fn='toon', name=a[0], color=a[1] if len(a) > 1 else k.get('color'),
                               shade=a[2] if len(a) > 2 else k.get('shade_mul'))
            elif fn == '_toon_tex':
                im = a[1] if len(a) > 1 else k['image']
                made[i] = dict(fn='toon_tex', name=a[0], image=made[im['$r']]['rgba'],
                               shade=a[2] if len(a) > 2 else k.get('shade_mul'))
            elif fn == '_object':
                names = ('name', 'verts', 'faces', 'weights', 'arm', 'mats', 'uv', 'uv_corner', 'mat_idx', 'smooth')
                d = dict(zip(names, a)); d.update(k)
                o = dict(name=d['name'], V=np.asarray(d['verts'], float), polys=d['faces'], weights=d['weights'],
                         uv=d.get('uv'), uv_corner=d.get('uv_corner'), mat_idx=d.get('mat_idx'), smooth=d.get('smooth', True),
                         materials=[made[m['$r']] for m in d['mats']], mods={}, props={}, outline=None)
                made[i] = o
                obs.append(o)
            elif fn == 'outline':
                ob = a[0]['$r']
                names = ('ob', 'thick', 'color', 'name', 'region')
                d = dict(zip(names, a)); d.update(k)
                made[ob]['outline'] = {x: d[x] for x in names[1:] if x in d}
            elif fn == 'mask_skin':
                hide = np.asarray(a[1] if len(a) > 1 else k['hide'], bool)
        elif e[0] == 'mod':
            _, i, ob, name, type_ = e
            m = dict(type=type_, settings={})
            made[ob]['mods'][name] = m
            made[i] = m
        elif e[0] == 'set':
            made[e[1]]['settings'][e[2]] = _dec(e[3], arrays)
        elif e[0] == 'item':
            made[e[1]]['props'][e[2]] = _dec(e[3], arrays)
    return obs, hide


def blender_bytes(rgba):
    """an image's pixels as a Blender byte image keeps them after to_blender_image's float write (row 0 = top), as floats
    0..1: what the bundle stores and the QA samples."""
    x = np.clip(np.asarray(rgba, np.float32), 0, 1)
    return np.floor(x * np.float32(255) + np.float32(0.5)).astype(np.uint8).astype(np.float64) / 255.0


# ---------------------------------------------------------------------------------------------------- the assembly
ASM_KEYS = ('base', 'body', 'body_code', 'brows', 'eyes', 'head', 'head_code', 'head_detail', 'iris', 'mouth', 'style')
"""the spec sections character.assemble reads (measured with charkit.cache's tracked dicts on both gate specs;
charkit/tests/test_geomstage.py fails if it reads another), plus hair.shape.eye_depth (the code head's depth), and
`ref` when there is no code head file (code_base then reads the face sheet)."""
ASM_FILES = ('head_code', 'body_code')          # spec values naming files it reads (keyed by their content)


def assembly_key(spec):
    """the key character.assemble(spec) is kept under: the sections it reads (ASM_KEYS), with the files ASM_FILES name
    keyed by content, not path (a build's own folder is in the path), the assembly's code (charkit.cache.code_units,
    transitively: an edit to code_base or code_body re-assembles) and the venv's packages. The build's venv steps (the
    hair pieces' parts.Case, the garments) and the evaluator give it different specs that agree on these, so they
    share one assembly."""
    from . import cache, character
    S = {k: spec.get(k) for k in ASM_KEYS if k not in ASM_FILES}
    S['eye_depth'] = ((spec.get('hair') or {}).get('shape') or {}).get('eye_depth')
    if not spec.get('head_code'):
        S['ref'] = spec.get('ref')
    files = {k: cache.content_digest(spec[k]) if os.path.exists(str(spec[k])) else spec[k]
             for k in ASM_FILES if spec.get(k)}
    code = cache.digest(cache.code_units(character.assemble))
    return cache.digest([S, files, code, cache.venv_env()])[:20]


def assemble(spec, keep=True, log=None):
    """character.assemble(spec), kept on disk (charkit/out/geom/cache/asm_NAME_KEY.pkl, assembly_key) and in memory:
    the venv's stages and the evaluator share it, and a garment change doesn't re-assemble. keep=False computes. The
    result is a fresh copy each call (callers write into it)."""
    import pickle
    from . import character
    if not keep:
        return character.assemble(spec)
    key = assembly_key(spec)
    if key in _ASM:
        return pickle.loads(_ASM[key])
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = os.path.join(root, 'charkit', 'out', 'geom', 'cache', 'asm_%s_%s.pkl' % (spec.get('name', 'char'), key))
    blob = None
    if os.path.exists(p):
        try:
            blob = open(p, 'rb').read()
            A = pickle.loads(blob)
        except Exception:
            blob = None
    if blob is None:
        A = character.assemble(spec)
        try:
            blob = pickle.dumps(A, protocol=pickle.HIGHEST_PROTOCOL)
        except (TypeError, pickle.PicklingError):
            return A                              # (an assembly holding open files, e.g. the anime base: no cache)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = '%s.%d.tmp' % (p, os.getpid())
        open(tmp, 'wb').write(blob)
        os.replace(tmp, p)
        if log:
            log('assembled %s (%s)' % (spec.get('name'), key))
        A = pickle.loads(blob)
    while len(_ASM) >= 4:
        _ASM.pop(next(iter(_ASM)))
    _ASM[key] = blob
    return A


_ASM = {}


# ----------------------------------------------------------------------------------------------- the garments stage
def garments_product(A, specs, hull=None, spec_all=None):
    """the garments stage's product for assembly A: garments.build recorded (numpy), with the body it was built on kept
    for the Blender side's check (check/body: the assembly's vertices in float32)."""
    rec = record(A, specs, hull=hull, spec_all=spec_all)
    return product('garments', rec, meta=dict(garments=[g.get('name') for g in specs or []], numpy=np.__version__),
                   checks={'body': np.asarray(A['verts'], np.float32)})


def garments_step(spec, path, log=print):
    """venv-side, the build's garments stage: the character assembled as the Blender side assembles it
    (character.assemble on the resolved spec), the hull's pieces aligned onto it, every garment built and recorded ->
    `path` (the product). -> the product."""
    import time
    from . import garments
    t0 = time.time()
    A = assemble(spec, log=log)
    t1 = time.time()
    hull = garments.hull_pieces(spec, A) if any(g.get('source') == 'hull' for g in spec.get('garments') or []) else None
    t2 = time.time()
    P = garments_product(A, spec.get('garments'), hull, spec)
    t3 = time.time()
    P['meta']['digest'] = digest(P)
    save(P, path)                                     # (deterministic content: the Blender stage's cache keys on it;
    rep = dict(digest=P['meta']['digest'], seconds=dict(assemble=round(t1 - t0, 2), hull=round(t2 - t1, 2),  # the times
                                                         garments=round(t3 - t2, 2)))                      # go beside it)
    json.dump(rep, open(os.path.splitext(path)[0] + '.json', 'w'), indent=1)
    log('garments geom %s: %d objects, %d events, %s (%.1fs: assemble %.1f, hull %.1f, garments %.1f)' % (
        path, sum(1 for e in P['meta']['events'] if e[0] == 'call' and e[2] == '_object'), len(P['meta']['events']),
        P['meta']['digest'], t3 - t0, t1 - t0, t2 - t1, t3 - t2))
    return P


def garments_instantiate(S, path):
    """Blender, the garments stage from its product: the objects replayed onto the scene's character, and the body the
    product was built on checked against Blender's (the trace's garments_body: how far apart the venv's assembly and
    Blender's are, the character stage's drift, until it too moves venv-side). -> [objects]."""
    from . import trace
    P = load(path)
    V = np.asarray(S.character['data']['verts'], float)
    Vp = P['arrays'].get('check/body')
    if Vp is not None and len(Vp) == len(V):
        d = np.abs(V.astype(np.float32) - Vp)
        trace.note('garments_body', max_nm=round(float(d.max()) * 1e9, 3), f32_equal=int((d == 0).all(1).sum()),
                   n=int(len(V)), digest=P['meta'].get('digest'))         # (nanometres: the trace rounds to 1e-6)
    else:
        trace.note('garments_body', mismatch=True, n=int(len(V)), n_product=None if Vp is None else int(len(Vp)))
    return replay(P, S.character)
