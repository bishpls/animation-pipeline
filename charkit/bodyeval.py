"""The body, garments and hair as numpy geometry, fast, for fitting and sensitivity (docs/CHARKIT.md §4, the fast
evaluator): every object the Blender build makes for the character, in world space at the rest pose, without Blender, and
qa3d's silhouette checks measured on it through a numpy z-buffer (charkit.geom.raster, pixel centres, per-triangle labels).

    E = bodyeval.Evaluator('charkit/spec/clawd.json')          # resolve once; the heavy parts are cached
    G = E.geometry({'body.proportions.leg': 1.0})              # knob overrides by dotted path (list items by name/kind)
    Q = E.qa(G)                                                # shape_iou (overall, per band, per view), ref_iou

What is cached, and how a knob change reuses it:
  assembly   character.assemble at the resolved spec (pickled by the spec and the code). A body knob rebuilds only
             the body (body.build_body_data, about 1 s) and carries the assembled head over in its own frame (head centre,
             head length L): the anime head is a wrap onto an L-sized target, so it keeps its shape in L whatever the body
             (`compose`). Any other character knob (head, eyes, mouth, ...) assembles again (about 15 s).
  hair       the generated hair (hair.shape) selected, culled and smoothed as scene.hair_shape_mesh does, the hair cap
             and the accessories' volume, kept in the head frame: a body knob moves them as the build's eye alignment
             would; hair and head knobs recompute them.
  target     the generated shape aligned by its eyes (scene.eye_target), and its silhouettes per framing.

Differences from the Blender build, measured by `validate` (python -m charkit bodyeval --validate BUILD): no subdivision
surface, solidify or outline modifiers (the silhouette is the base mesh: the QA's flat renders don't show the outline
hulls, and the subdivision's shrinkage is under a pixel), the generated hair is not decimated, and a body knob keeps the
hair selection it had (the selection reads the body only round the neck).
"""
import copy, hashlib, json, os, pickle, time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, 'charkit', 'out', 'bodyeval', 'cache')
AZ = (0, 45, 90, 135, 180, 270)                                           # qa3d's azimuths
RES = (360, 560)                                                          # qa3d's QA camera
BODY_KEYS = ('body',)                                                     # spec sections compose() can take over


# ------------------------------------------------------------------------------------------------------------------ knobs
def _item(lst, key):
    """a list element by index, name or kind."""
    if isinstance(key, int) or (isinstance(key, str) and key.isdigit()):
        return int(key)
    for i, x in enumerate(lst):
        if isinstance(x, dict) and (x.get('name') == key or x.get('kind') == key):
            return i
    raise KeyError(key)


def get_knob(spec, path, default=None):
    """a knob's value by dotted path ('body.proportions.leg', 'garments.skirt.flare', 'accessories.star.size',
    'hair.shape.below'); list items by index, name or kind."""
    x = spec
    for k in path.split('.'):
        if isinstance(x, list):
            try:
                x = x[_item(x, k)]
            except (KeyError, IndexError):
                return default
        elif isinstance(x, dict) and k in x:
            x = x[k]
        else:
            return default
    return x


def set_knob(spec, path, value):
    """set a knob by dotted path in place (creating dict levels); -> spec."""
    ks = path.split('.')
    x = spec
    for k in ks[:-1]:
        if isinstance(x, list):
            x = x[_item(x, k)]
        else:
            x = x.setdefault(k, {})
    if isinstance(x, list):
        x[_item(x, ks[-1])] = value
    else:
        x[ks[-1]] = value
    return spec


def with_knobs(spec, knobs):
    S = copy.deepcopy(spec)
    for p, v in (knobs or {}).items():
        set_knob(S, p, v)
    return S


def _abs(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def _h(x):
    return hashlib.sha1(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()[:16]


# ------------------------------------------------------------------------------------------------------------ resolving
def resolve(spec_path, base=None):
    """the spec as the Blender build sees it (cli.resolve: the manifest, the design rig's fit; then scene.fit_cranium with
    the numpy GLB reader), without writing anything."""
    from . import cli, manifest, refs, scene
    from .geom.parts import load_generated
    spec = manifest.resolve(json.load(open(cli._path(spec_path))))
    if base:
        spec['base'] = base
    ref = spec.get('ref', {})
    if isinstance(ref, dict) and ref.get('rig'):
        R = refs.measure(cli._path(ref['rig']), spec.get('eyes', {}).get('x', 0.168))
        spec = refs.fit(spec, R, ref.get('fit', ('face', 'features', 'hair')))
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        spec = scene.fit_cranium(spec, ROOT, load=lambda p: load_generated(p, compat=True))
    return spec


def _glb(spec):
    from . import cli
    shape = (spec.get('hair') or {}).get('shape') or {}
    p = shape.get('glb')
    return cli._path(p) if p else None


# ------------------------------------------------------------------------------------------------------------- assembly
def _code_version():
    """a hash of the modules the assembly runs (so a cached assembly goes stale when they change)."""
    h = hashlib.sha1()
    for m in ('character', 'body', 'anime_head', 'eyes', 'mouth', 'brows', 'head', 'mh', 'base_anime'):
        p = os.path.join(ROOT, 'charkit', m + '.py')
        if os.path.exists(p):
            h.update(open(p, 'rb').read())
    return h.hexdigest()[:8]


def assemble_cached(spec, cache=True):
    """character.assemble, pickled under charkit/out/bodyeval/cache by the spec's hash and the assembly code's."""
    from . import character
    key = hashlib.sha1((json.dumps(spec, sort_keys=True, default=str) + _code_version()).encode()).hexdigest()[:16]
    path = os.path.join(CACHE, f'{spec.get("name", "char")}_{key}.pkl')
    if cache and os.path.exists(path):
        try:
            return pickle.load(open(path, 'rb'))
        except Exception:
            pass
    A = character.assemble(spec)
    if cache:
        os.makedirs(CACHE, exist_ok=True)
        try:
            open(path, 'wb').write(pickle.dumps(A))
        except (TypeError, pickle.PicklingError):
            pass
    return A


def _smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def compose(A0, spec_body, B1=None):
    """an assembly for other body knobs from one assembled at A0's: the new body (body.build_body_data), the assembled head
    carried over in its own frame. The realistic head moves between the two bodies by a similarity G (the head bone is rigid
    under the proportions; the whole body is scaled to the height), the anime head by F (head centre and L: it is a wrap
    onto an L-sized target), and the neck between blends the two by the head bone's weight:
        V = V1 + lam (V_out0 - V0) + beta(head_w) (F(V0) - G(V0))
    (pure head vertices land on F(V_out0) exactly; the region's border, where the wrap lets go, on the new body).
    -> the assembly dict (character.assemble's), keys and features carried."""
    from . import anime_head, body as bodylib, head as headlib
    B0 = A0['body']
    B1 = B1 or bodylib.build_body_data(spec_body, keep_head=True)
    Hd0 = A0['head']
    L0, L1 = Hd0['L'], B1['head_len']
    lam = L1 / L0
    hw = B0['head_w']
    V0, V1, Vo = B0['verts'], B1['verts'], A0['verts']
    pure = hw > 0.999
    sig = B1['scale'] / B0['scale']
    t = (V1[pure] - sig * V0[pure]).mean(0)
    H1 = headlib.Head(L1, Hd0['H'].K)
    samples = Hd0['info'].get('profile') or []
    fronts = [sig * y + t[1] - H1.surface(0.0, -H1.chin * d)[1] for d, y in samples]
    c0 = np.asarray(Hd0['centre'], float)
    c1 = np.array([0.0, float(np.median(fronts)) if fronts else sig * c0[1] + t[1], float(B1['marks']['chin'][2]) + H1.chin])
    F = lambda P: c1 + lam * (np.asarray(P, float) - c0)
    G = lambda P: sig * np.asarray(P, float) + t
    region = Hd0['info']['region']
    beta = np.where(region, _smoothstep(0.02, 0.5, hw), 0.0)
    V = V1 + lam * (Vo - V0) + beta[:, None] * (F(V0) - G(V0))
    # joints: the body's, those in and round the head following the carried head (as assemble does)
    J = dict(B1['joints'])
    near = [k for k, p in J.items() if p[2] > B1['marks']['chin'][2] - 0.35 * L1]
    moved = anime_head.follow([J[k] for k in near], V1, V)
    for k, p in zip(near, moved):
        J[k] = p
    info = dict(Hd0['info'])
    TV, TT = info['target']
    info['target'] = (np.asarray(TV) * lam, TT)
    for k in ('eye_world',):
        if k in info and info[k] is not None:
            info[k] = [F(p) for p in info[k]]
    for k in ('c_real', 'c_anime'):
        if info.get(k) is not None:
            info[k] = F(info[k])
    head = dict(Hd0, L=L1, H=H1, centre=c1, eye_z=c1[2], info=info, marks=B1['marks'])
    eyes = []
    for E in A0['eyes']:
        E2 = dict(E)
        E2['c'] = (E['c'][0] * lam, c1[2] + (E['c'][1] - c0[2]) * lam)
        for k in ('sclera', 'iris'):
            v, q, uv = E[k]
            E2[k] = (F(v), q, uv)
        E2['lashes'] = [(F(v), q) for v, q in E['lashes']]
        E2['brow'] = (F(E['brow'][0]), E['brow'][1])
        for k in ('iris_keys', 'brow_keys'):
            E2[k] = {n: d * lam for n, d in E[k].items()}
        E2['keys'] = {n: (D * lam, [d * lam for d in ld]) for n, (D, ld) in E['keys'].items()}
        eyes.append(E2)
    Mo = dict(A0['mouth'])
    Mo['c'] = (0.0, c1[2] + (Mo['c'][1] - c0[2]) * lam)
    for k in ('teeth', 'tongue', 'line'):
        v, q = Mo[k]
        Mo[k] = (F(v), q)
    for k in ('keys', 'teeth_keys', 'line_keys', 'tongue_keys'):
        Mo[k] = {n: d * lam for n, d in Mo[k].items()}
    B = dict(B0, verts=V1, joints=B1['joints'], marks=B1['marks'], params=B1['params'], head_len=L1, scale=B1['scale'])
    return dict(A0, verts=V, joints=J, body=B, head=head, eyes=eyes, mouth=Mo, weights=B1['weights'])


# -------------------------------------------------------------------------------------------------------------- the hair
class _S:
    """the little of a charkit.scene.Scene the numpy hair steps read."""

    def __init__(self, spec, A):
        self.spec = spec
        self.character = {'data': A}


def _frame_of(A):
    Hd = A['head']
    return np.asarray(Hd['centre'], float), float(Hd['L'])


def to_head(P, A):
    c, L = _frame_of(A)
    return (np.asarray(P, float) - c) / L


def from_head(q, A):
    c, L = _frame_of(A)
    return c + L * np.asarray(q, float)


def face_y_grid(A, n=(81, 81)):
    """charkit.eyes.Face(H, centre).y over the face window scene.cull_face tests, as a grid in head units: -> (xs, zs, Y)
    (x, z from the centre in L, y from the centre in L). Face.y bisects per point; the grid makes the cull vectorised."""
    from .eyes import Face
    Hd = A['head']; L = Hd['L']; c = np.asarray(Hd['centre'], float)
    Fc = Face(Hd['H'], c)
    xs = np.linspace(-0.30, 0.30, n[0]); zs = np.linspace(-Hd['H'].chin / L * 1.05, 0.22, n[1])
    Y = np.array([[(Fc.y(c[0] + x * L, c[2] + z * L) - c[1]) / L for x in xs] for z in zs])
    return xs, zs, Y


def _bilinear(xs, zs, Y, x, z):
    i = np.clip(np.interp(z, zs, np.arange(len(zs))), 0, len(zs) - 1.000001)
    j = np.clip(np.interp(x, xs, np.arange(len(xs))), 0, len(xs) - 1.000001)
    i0, j0 = i.astype(int), j.astype(int)
    fi, fj = i - i0, j - j0
    return ((1 - fi) * ((1 - fj) * Y[i0, j0] + fj * Y[i0, j0 + 1]) + fi * ((1 - fj) * Y[i0 + 1, j0] + fj * Y[i0 + 1, j0 + 1]))


def cull_face(A, hv, hf, shape, grid=None):
    """scene.cull_face, vectorised (the face surface from a grid): generated 'hair' on or behind our face goes."""
    Hd = A['head']; L = Hd['L']; c = np.asarray(Hd['centre'], float)
    xs, zs, Y = grid or face_y_grid(A)
    zr = hv[:, 2] - c[2]
    x = hv[:, 0]
    band = (-Hd['H'].chin * 1.05 < zr) & (zr < 0.22 * L) & (np.abs(x) < 0.30 * L)
    fy = c[1] + L * _bilinear(xs, zs, Y, (x - c[0]) / L, zr / L)
    sec = np.array([Hd['H'].section(z)[0] for z in zr[band & (zr < -0.06 * L)]])
    low = np.zeros(len(hv), bool)
    lo_i = np.nonzero(band & (zr < -0.06 * L))[0]
    low[lo_i] = (np.abs(x[lo_i]) < sec * 0.92) & (hv[lo_i, 1] < fy[lo_i] + 0.04 * L)
    high = band & (zr >= -0.06 * L) & (hv[:, 1] > fy - shape.get('clear', 0.02) * L)
    keep = ~(low | high)
    return _keep_faces(hv, hf, keep, all_=True)


def _keep_faces(V, F, keep_v, all_=True, at_least=None):
    F = np.asarray(F)
    kf = keep_v[F].all(1) if at_least is None else keep_v[F].sum(1) >= at_least
    F = F[kf]
    used = np.unique(F)
    remap = np.full(len(V), -1); remap[used] = np.arange(len(used))
    return V[used], remap[F]


def _vertex_adjacency(F, n):
    from scipy import sparse
    F = np.asarray(F)
    a = np.concatenate([F[:, k] for k in range(F.shape[1])])
    b = np.concatenate([F[:, (k + 1) % F.shape[1]] for k in range(F.shape[1])])
    M = sparse.coo_matrix((np.ones(len(a) * 2), (np.r_[a, b], np.r_[b, a])), shape=(n, n)).tocsr()
    M.data[:] = 1.0
    return M


def hair_by_outside(V, C, F, body_v, body_f, chin_z, shoulder_x, below=0.1, clear=0.006, grow=2):
    """i3d.hair_by_outside with charkit.geom's BVH: the generated surface lying outside our skin (signed along the nearest
    face's normal, as Blender's BVH find_nearest gives it) in the head region; low pale texels out; `grow` rings back."""
    from .geom.bvh import BVH
    from .geom.mesh import Mesh, face_normals
    from .i3d import hsv
    bm = Mesh.from_polys(np.asarray(body_v, float), [tuple(f) for f in body_f])
    _, f, q = BVH(bm).nearest(V)
    fn = face_normals(bm.V, bm.F)
    sd = np.where(f >= 0, np.einsum('ij,ij->i', V - q, fn[np.maximum(f, 0)]), 1.0)
    _, s_, v_ = hsv(C)
    keep_v = (sd > clear) & (V[:, 2] > chin_z - below)
    low = V[:, 2] < chin_z + 0.02
    keep_v &= ~(low & (np.abs(V[:, 0]) > shoulder_x))
    keep_v &= ~(low & (s_ < 0.3) & (v_ > 0.6))
    region = (V[:, 2] > chin_z - below) & (sd > -clear)
    M = _vertex_adjacency(F, len(V))
    for _ in range(grow):
        add = (M @ keep_v.astype(float) > 0) & region & ~keep_v
        keep_v |= add
    return _keep_faces(V, F, keep_v)


def blender_smooth(V, F, factor=0.5, iterations=6):
    """Blender's Smooth modifier: every vertex moves `factor` of the way to the mean of its edges' midpoints (so half
    way as far as a plain Laplacian step toward its neighbours), `iterations` times (uniform weights, no boundary rule)."""
    from scipy import sparse
    F = np.asarray(F)
    E = np.sort(np.concatenate([F[:, [k, (k + 1) % F.shape[1]]] for k in range(F.shape[1])]), 1)
    E = np.unique(E, axis=0)
    n = len(V)
    M = sparse.coo_matrix((np.ones(2 * len(E)), (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])), shape=(n, n)).tocsr()
    deg = np.asarray(M.sum(1)).ravel()
    V = np.asarray(V, float).copy()
    has = deg > 0
    for _ in range(iterations):
        mid = 0.5 * (V + (M @ V) / np.maximum(deg, 1)[:, None])
        V = np.where(has[:, None], V * (1 - factor) + mid * factor, V * (1 - factor))
    return V


def drop_small_parts(V, F, min_faces):
    """faces in edge-connected pieces smaller than min_faces go (scene.hair_shape_mesh's cleanup)."""
    from scipy import sparse
    from scipy.sparse.csgraph import connected_components
    F = np.asarray(F)
    k = F.shape[1]
    E = np.sort(np.stack([F, np.roll(F, -1, 1)], -1).reshape(-1, 2), 1)
    fid = np.repeat(np.arange(len(F)), k)
    key = E[:, 0] * (len(V) + 1) + E[:, 1]
    o = np.argsort(key, kind='stable')
    ks, fs = key[o], fid[o]
    same = ks[1:] == ks[:-1]
    a, b = fs[:-1][same], fs[1:][same]
    G = sparse.coo_matrix((np.ones(len(a)), (a, b)), shape=(len(F), len(F)))
    nc, lab = connected_components(G, directed=False)
    size = np.bincount(lab, minlength=nc)
    keep = size[lab] >= min_faces
    return _keep_faces(V, F[keep], np.ones(len(V), bool)) if keep.any() else (V[:0], F[:0])


def select_hair(A, spec, gen, eyes_gen, grid=None):
    """the generated hair as scene.hair_shape_volume selects it (numpy): the generated character aligned by its eyes
    (scene.eye_target), its hair selected (hair.shape.select) and culled off our face. -> dict(sel (V, F) the selection the
    volume and the mesh-mode hair are built on, full (V, F) the aligned shape, align (eye_mid, spacing))."""
    from . import i3d, scene
    shape = spec['hair']['shape']
    Hd = A['head']; L = Hd['L']
    GV, GF, GC = gen
    mid, spacing = scene.eye_target(A, shape)
    V = i3d.align_by_eyes(GV, eyes_gen, mid, spacing)
    chin_z = Hd['centre'][2] - Hd['H'].chin
    sel = shape.get('select')
    if sel == 'outside':
        hv, hf = hair_by_outside(V, GC, GF, A['verts'], A['faces'], chin_z, shape.get('shoulder_x', 0.16),
                                 below=shape.get('below', 0.25) * L, clear=shape.get('clear_skin', 0.025) * L)
    elif sel == 'exclude':
        hv, hf = i3d.hair_by_exclusion(V, GC, GF, chin_z, shape.get('shoulder_x', 0.16), below=shape.get('below', 0.25) * L)
    elif 'hue' in shape:
        hv, hf = i3d.hair_by_hue(V, GC, GF, shape['hue'], chin_z, shape.get('shoulder_x', 0.16),
                                 below=shape.get('below', 0.25) * L, sat=shape.get('sat', 0.38))
    else:
        raise NotImplementedError('bodyeval: hair.shape.select %r needs Blender' % sel)
    hv, hf = cull_face(A, np.asarray(hv, float), np.asarray(hf), shape, grid)
    return dict(sel=(hv, hf), full=(V, GF), align=dict(eye_mid=mid, spacing=spacing))


def finish_mesh_hair(sel, shape, L, decimate=False):
    """scene.hair_shape_mesh's processing of the selection (numpy): Blender's smoothing, the merge of coincident
    vertices, small loose pieces dropped. The decimation is left out (silhouette-neutral: 0.98 IoU either way at QA
    scale) unless decimate=True (charkit.geom's quadric decimation). -> (V, F)."""
    from .geom import repair
    from .geom.mesh import Mesh
    if shape.get('voxel', 0) > 0:
        raise NotImplementedError('bodyeval: hair.shape.voxel > 0 (a voxel remesh) needs Blender')
    hv, hf = sel
    m = Mesh(blender_smooth(hv, hf, shape.get('smooth_factor', 0.5), shape.get('smooth', 6)), hf)
    if decimate:
        from .geom.remesh import decimate as dec
        m = dec(m, int(len(hf) * shape.get('decimate', 0.5)))
    m = repair.merge_close(m, 0.0005 * L)
    return drop_small_parts(m.V, m.F, shape.get('min_part', 150))


def mesh_hair(A, spec, gen, eyes_gen, grid=None, decimate=False):
    """select_hair, then (mode mesh) finish_mesh_hair: -> select_hair's dict plus shape (V, F)."""
    R = select_hair(A, spec, gen, eyes_gen, grid)
    shape = spec['hair']['shape']
    if shape.get('mode') == 'mesh':
        R['shape'] = finish_mesh_hair(R['sel'], shape, A['head']['L'], decimate)
    return R


def mesh_volume(A, spec, sel):
    """the hair's charkit.hair.MeshVolume (the accessories' ground) from the selected hair, numpy."""
    from . import hair
    Hd = A['head']
    return hair.MeshVolume(Hd['H'], Hd['centre'], hair._style(spec['hair']), Hd['info']['target'], sel)


def hair_cap(A, spec):
    """scene.hair_cap's surface: the analytic volume's cap at 0.97, numpy. -> (V, F)."""
    from . import hair
    Hd = A['head']
    plain = {k: v for k, v in (spec.get('hair') or {}).items() if k not in ('silhouette', 'shape')}
    plain['thick'] = min(plain.get('thick', 1.0), 1.0)
    Vol = hair.Volume(Hd['H'], Hd['centre'], hair._style(plain), Hd['info']['target'])
    v, f, _ = hair.cap(Vol)
    return Vol.c + (v - Vol.c) * 0.97, f


# ------------------------------------------------------------------------------------------------------------ geometry
class Part:
    """one object: name, group (skin, eyes, mouth, hair, accessories, garments), world verts, polygons."""

    def __init__(self, name, group, V, polys):
        self.name, self.group, self.V = name, group, np.asarray(V, float)
        self.polys = polys
        self._tris = None

    def tris(self):
        if self._tris is None:
            self._tris = triangulate(self.polys)
        return self._tris

    def __repr__(self):
        return 'Part(%s, %s, %d verts)' % (self.name, self.group, len(self.V))


def triangulate(polys):
    """fan triangles of polygons (a list of index tuples or an (n, k) array). -> (m, 3) int array."""
    if isinstance(polys, np.ndarray) and polys.ndim == 2:
        P = polys.astype(np.int64)
        return np.concatenate([P[:, [0, j, j + 1]] for j in range(1, P.shape[1] - 1)]) if P.shape[1] >= 3 else P[:0, :3]
    out = []
    by = {}
    for f in polys:
        by.setdefault(len(f), []).append(f)
    for k, fs in sorted(by.items()):
        if k < 3:
            continue
        P = np.asarray(fs, np.int64)
        out += [P[:, [0, j, j + 1]] for j in range(1, k - 1)]
    return np.concatenate(out) if out else np.zeros((0, 3), np.int64)


def _loops(A):
    """the assembly's faces as flat (loop verts, starts, counts), computed once per assembly."""
    if '_loops' not in A:
        ct = np.array([len(f) for f in A['faces']])
        st = np.r_[0, np.cumsum(ct)[:-1]]
        A['_loops'] = (np.array([v for f in A['faces'] for v in f]), st, ct)
    return A['_loops']


def garment_piece(A, s, nrm=None, dom=None):
    """one garment piece as garments.build makes it (numpy) and the skin vertices it hides. -> (Part, hide indices)."""
    from . import garments as gm
    k, nm = s['kind'], s['name']
    hide = np.zeros(0, np.int64)
    if k == 'shell':
        G = gm.shell(A, s, nrm)
        src = G['src']; inside = np.zeros(len(A['verts']), bool); inside[src] = True
        lv, st, ct = _loops(A)
        c = np.add.reduceat(inside[lv].astype(int), st)
        border = np.zeros(len(inside), bool)
        border[lv[np.repeat((c > 0) & (c < ct), ct)]] = True
        hide = src[~border[src]]
    elif k == 'band':
        G = gm.band(A, s)
    elif k == 'shoe':
        G = gm.shoe(A, s)
        dom = gm.dominant(A)[0] if dom is None else dom
        hide = np.nonzero(np.isin(dom, [f"{s['side']}Foot", f"{s['side']}Toes"]))[0]
    elif k == 'belt':
        G = gm.belt(A, s)
    elif k == 'sleeve':
        G = gm.sleeve(A, s)
    elif k == 'skirt':
        G = gm.skirt(A, s)
    elif k == 'collar':
        G = gm.collar(A, s, nrm)
    elif k == 'bow':
        G = gm.bow(A, s)
    else:
        raise ValueError(k)
    return Part(nm, 'garments', G['verts'], G['faces']), hide


def garment_parts(A, specs, cache=None, akey=None):
    """every garment piece (garment_piece) and the skin vertices the tight shells and shoes hide, as garments.build's mask
    does. cache: a dict reused across calls; a piece is rebuilt only when its spec or the assembly (akey) changed.
    -> ([Part], hide (N,) bool)."""
    from . import garments as gm
    nrm = dom = None
    hide = np.zeros(len(A['verts']), bool)
    parts = []
    for s in specs or []:
        key = (akey, _h(s)) if akey is not None else None
        if cache is None or key not in cache:
            if nrm is None:
                nrm = gm.vertex_normals(A['verts'], A['faces']); dom = gm.dominant(A)[0]
            r = garment_piece(A, s, nrm, dom)
            if cache is not None:
                cache[key] = r
        else:
            r = cache[key]
        parts.append(r[0]); hide[r[1]] = True
    return parts, hide


def character_parts(A, hide=None):
    """the skin (minus the vertices the garments hide, as the build's mask modifier does), the eyes and the mouth."""
    F = A['faces']
    polys = F if hide is None or not hide.any() else [f for f in F if not any(hide[v] for v in f)]
    out = [Part(A.get('_name', 'char') + '_skin', 'skin', A['verts'], polys)]
    for E in A['eyes']:
        tag = 'L' if E['side'] > 0 else 'R'
        out.append(Part('sclera_' + tag, 'eyes', E['sclera'][0], E['sclera'][1]))
        out.append(Part('iris_' + tag, 'eyes', E['iris'][0], E['iris'][1]))
        lv, lq, off = [], [], 0
        for rv, rq in E['lashes']:
            lv.append(rv); lq += [tuple(i + off for i in f) for f in rq]; off += len(rv)
        out.append(Part('lash_' + tag, 'eyes', np.vstack(lv), lq))
        out.append(Part('brow_' + tag, 'eyes', E['brow'][0], E['brow'][1]))
    Mo = A['mouth']
    for nm, key in (('teeth', 'teeth'), ('tongue', 'tongue'), ('mouth_line', 'line')):
        out.append(Part(nm, 'mouth', Mo[key][0], Mo[key][1]))
    return out


class Geometry:
    """what `Evaluator.geometry` returns: the parts, the assembly, the landmarks the QA bands use, the aligned target."""

    def __init__(self, spec, A, parts, target=None, align=None, timings=None):
        from .garments import bone_seg
        self.spec, self.A, self.parts, self.target, self.align = spec, A, parts, target, align
        Hd = A['head']
        self.L = float(Hd['L'])
        self.landmarks = dict(L=self.L, centre=np.asarray(Hd['centre'], float), chin=float(Hd['centre'][2] - Hd['H'].chin),
                              waist=float(bone_seg(A, 'spine')[0][2]), knee=float(bone_seg(A, 'leftLowerLeg')[0][2]))
        self.timings = timings or {}

    def part(self, name):
        return next(p for p in self.parts if p.name == name)

    def group(self, g):
        return [p for p in self.parts if p.group == g]


# ---------------------------------------------------------------------------------------------------------- the evaluator
class Evaluator:
    """a character's fast numpy evaluation (see the module doc). spec: a spec path (resolved as the build resolves it) or
    an already resolved spec dict."""

    def __init__(self, spec, base=None, cache=True, verbose=False):
        t = time.time()
        self.spec = resolve(spec, base) if isinstance(spec, str) else spec
        self.cache = cache
        self.verbose = verbose
        self._asm = {}               # character key -> assembly (the base spec's, and the latest other)
        self._bodies = {}            # body key -> build_body_data
        self._layers = {}            # hair layers (see hair_parts) -> {key: value in the head frame}
        self._targets = {}           # (framing, align) key -> target masks
        self._garments = {}          # (assembly key, piece key) -> (Part, hide)
        self._gen = None
        self._ref = None
        self.t_resolve = time.time() - t

    # ---- the heavy inputs
    def generated(self):
        """the generated character (GLB frame, i3d-compatible colours as the build's find_eyes sees them) and its eyes."""
        if self._gen is None:
            from . import i3d
            from .geom.parts import load_generated
            p = _glb(self.spec)
            if not p:
                return None
            V, F, C = load_generated(p, compat=True)
            self._gen = ((np.asarray(V), np.asarray(F), np.asarray(C)), i3d.find_eyes(np.asarray(V), np.asarray(C)))
        return self._gen

    @staticmethod
    def char_key(spec):
        from .trace import STAGE_KEYS
        return _h({k: spec.get(k) for k in STAGE_KEYS['character'] + ('base', 'name') if k not in BODY_KEYS})

    def assembly(self, spec):
        """the assembly for a spec: cached, composed (body knobs only), or assembled again."""
        ck, bk = self.char_key(spec), _h(spec.get('body'))
        if (ck, bk) in self._asm:
            return self._asm[(ck, bk)], 'cached'
        base = next(((k, A) for k, A in self._asm.items() if k[0] == ck and k[1] == self._base_bk), None)
        if base is None and ck == self.char_key(self.spec):
            A0 = assemble_cached(self.spec, self.cache)
            self._base_bk = _h(self.spec.get('body'))
            self._asm[(ck, self._base_bk)] = A0
            if bk == self._base_bk:
                return A0, 'assembled'
            base = ((ck, self._base_bk), A0)
        if base is not None and spec.get('base', 'makehuman') != 'anime':
            if bk not in self._bodies:
                from . import body as bodylib
                self._bodies = {bk: bodylib.build_body_data(spec.get('body'), keep_head=True)}
            A = compose(base[1], spec.get('body'), self._bodies[bk])
            how = 'composed'
        else:
            A = assemble_cached(spec, self.cache)
            how = 'assembled'
        # keep the base and the latest one
        keep = {k: v for k, v in self._asm.items() if k[1] == getattr(self, '_base_bk', None)}
        keep[(ck, bk)] = A
        self._asm = keep
        return A, how

    def _memo(self, layer, key, fn, keep=6):
        """a small per-layer cache (the most recent `keep` entries)."""
        c = self._layers.setdefault(layer, {})
        if key in c:
            c[key] = c.pop(key)
            return c[key]
        v = fn()
        c[key] = v
        while len(c) > keep:
            c.pop(next(iter(c)))
        return v

    def hair_parts(self, spec, A):
        """the hair objects (and the accessories on the hair volume) as the build makes them, in world. Each layer is
        cached in the head frame by the knobs it reads: the selection (hair.shape's selection knobs and the head), the
        mesh-mode finish (its smoothing knobs), the analytic cap (the volume knobs), the accessories (the selection, the
        hair style and their own knobs). -> ([Part], target (V, F) or None, align or None)."""
        from . import accessories, hair as hairlib
        hs = spec.get('hair')
        if hs is None:
            return [], None, None
        shape = hs.get('shape')
        c, L = _frame_of(A)
        head = _h({k: spec.get(k) for k in ('head', 'eyes', 'head_detail', 'base', 'mouth')})
        style = {k: v for k, v in hs.items() if k != 'shape'}
        acc = spec.get('accessories') or []
        if shape and shape.get('mode') in ('mesh', 'geom'):
            acc = [a for a in acc if a['kind'] not in shape.get('carries', ['bun'])]
        objects, full, align = [], None, None
        if shape:
            FIN = ('smooth', 'smooth_factor', 'min_part', 'decimate', 'mode', 'voxel', 'cap', 'geom', 'geom_opts',
                   'normals', 'normal_mix', 'carries')
            skey = _h([head, {k: v for k, v in shape.items() if k not in FIN}])
            grid = lambda: self._memo('face_grid', head, lambda: face_y_grid(A))
            gen = self.generated()

            def sel_fn():
                R = select_hair(A, spec, gen[0], gen[1], grid())
                return dict(sel=(to_head(R['sel'][0], A), R['sel'][1]), full=(to_head(R['full'][0], A), R['full'][1]),
                            align=dict(eye_mid=to_head(R['align']['eye_mid'], A), spacing=R['align']['spacing'] / L))
            R = self._memo('selection', skey, sel_fn)
            full = (from_head(R['full'][0], A), R['full'][1])
            align = dict(eye_mid=from_head(R['align']['eye_mid'], A), spacing=R['align']['spacing'] * L)
            sel_w = lambda: (from_head(R['sel'][0], A), R['sel'][1])
            mode = shape.get('mode')
            if mode == 'mesh':
                fk = _h([skey, {k: shape.get(k) for k in FIN}])
                hv, hf = self._memo('finish', fk, lambda: (lambda r: (to_head(r[0], A), r[1]))(
                    finish_mesh_hair(sel_w(), shape, L)))
                objects.append(('hair_shape', hv, hf))
            elif mode == 'geom':
                gv, gf = self.geom_hair(spec, A)
                objects.append(('hair_shape', to_head(gv, A), gf))
            if mode in ('mesh', 'geom') and (mode == 'mesh' or shape.get('cap', False)):
                objects.append(('hair_cap',) + self._memo('cap', _h([head, style]), lambda: (lambda r: (to_head(r[0], A), r[1]))(
                    hair_cap(A, spec))))
            vkey = _h([skey, style])
            vol = lambda: self._memo('volume', _h([vkey, list(c), L]), lambda: mesh_volume(A, spec, sel_w()))
            if mode not in ('mesh', 'geom'):
                meshes = self._memo('locks', _h([vkey, 'locks']), lambda: {n: (to_head(v, A), f) for n, (v, f, _) in
                                                                          hairlib.generate(A['head']['H'], c, A['head']['info']['target'], hs, vol())[0].items()})
                objects += [(n, q, f) for n, (q, f) in meshes.items()]
        else:
            vkey = _h([head, style])
            V_ = lambda: self._memo('volume', _h([vkey, list(c), L]), lambda: hairlib.generate(A['head']['H'], c, A['head']['info']['target'], hs))
            meshes = self._memo('locks', _h([vkey, 'locks']), lambda: {n: (to_head(v, A), f) for n, (v, f, _) in V_()[0].items()})
            objects += [(n, q, f) for n, (q, f) in meshes.items()]
            vol = lambda: V_()[1]
            base_shape = (self.spec.get('hair') or {}).get('shape')
            if base_shape and self.generated() is not None:
                # (the build's QA skips the shape check without hair.shape; the generated character still measures us)
                from . import i3d, scene
                gen = self.generated()
                mid, spacing = scene.eye_target(A, base_shape)
                full = (i3d.align_by_eyes(gen[0][0], gen[1], mid, spacing), gen[0][1])
                align = dict(eye_mid=mid, spacing=spacing)
        accs = self._memo('accessories', _h([vkey, acc]), lambda: [(n, to_head(v, A), f) for n, v, f, _ in
                                                                   accessories.generate(vol(), L, acc)])
        parts = [Part(n, 'hair', from_head(q, A), f) for n, q, f in objects]
        parts += [Part(n, 'accessories', from_head(q, A), f) for n, q, f in accs]
        return parts, full, align

    def geom_hair(self, spec, A):
        """mode 'geom': charkit.geom's extracted hair (shape['geom'] when the build wrote it, else extracted here and cached
        like the build caches it)."""
        from . import cli
        shape = spec['hair']['shape']
        from .geom.io import load_npz
        if shape.get('geom') and os.path.exists(cli._path(shape['geom'])):
            m = load_npz(cli._path(shape['geom']))
            return m.V, m.F
        from .geom import parts
        key = _h({k: v for k, v in spec.items()})
        path = os.path.join(ROOT, 'charkit', 'out', 'bodyeval', 'geom_hair_%s.npz' % key)
        if not os.path.exists(path):
            tmp = os.path.join(ROOT, 'charkit', 'out', 'bodyeval', 'spec_%s.json' % key)
            os.makedirs(os.path.dirname(tmp), exist_ok=True)
            json.dump(spec, open(tmp, 'w'), indent=1)
            C = parts.Case.load(tmp, fit=False, verbose=False)
            parts.save_part(parts.hair(C, **shape.get('geom_opts', {})), path, meta=dict(key=key))
        m = load_npz(path)
        return m.V, m.F

    def geometry(self, knobs=None, spec=None):
        """every character object at a spec (the evaluator's, with knob overrides). -> Geometry."""
        t0 = time.time()
        spec = with_knobs(spec or self.spec, knobs)
        A, how = self.assembly(spec)
        A['_name'] = spec.get('name', 'char')
        t1 = time.time()
        hair, target, align = self.hair_parts(spec, A)
        t2 = time.time()
        akey = (self.char_key(spec), _h(spec.get('body')))
        if len(self._garments) > 400:
            self._garments = {k: v for k, v in self._garments.items() if k[0] == akey}
        garm, hide = garment_parts(A, spec.get('garments'), self._garments, akey)
        t3 = time.time()
        parts = character_parts(A, hide) + hair + garm
        return Geometry(spec, A, parts, target, align, timings=dict(assembly=round(t1 - t0, 3), how=how,
                                                                    hair=round(t2 - t1, 3), garments=round(t3 - t2, 3)))

    # ---- measuring
    def frame(self, G):
        """qa3d's QA camera: orthographic, framing the character's z range (its objects' base verts) * 1.08."""
        from .geom.raster import Frame
        zs = np.concatenate([p.V[:, 2] for p in G.parts if len(p.V)])
        zmin, zmax = float(zs.min()), float(zs.max())
        return Frame((0.0, 0.0, (zmin + zmax) / 2), (zmax - zmin) * 1.08, RES)

    def labels(self, G, az, fr, groups=None):
        """the nearest part per pixel from azimuth az: -> (label (H, W) part index or -1, depth)."""
        from .geom.raster import rasterize
        from .geom.mesh import Mesh
        Vs, Fs, lab, off = [], [], [], 0
        for i, p in enumerate(G.parts):
            if groups and p.group not in groups:
                continue
            T = p.tris()
            if not len(T):
                continue
            Vs.append(p.V); Fs.append(T + off); lab.append(np.full(len(T), i)); off += len(p.V)
        m = Mesh(np.vstack(Vs), np.vstack(Fs))
        zb, fb, _ = rasterize(m, az, fr)
        lab = np.concatenate(lab)
        return np.where(fb >= 0, lab[np.maximum(fb, 0)], -1), zb

    def target_masks(self, G, fr, azs=AZ):
        if G.target is None:
            return None
        from .geom.raster import silhouette
        from .geom.mesh import Mesh
        key = (tuple(np.round(fr.centre, 7)), round(fr.scale, 7), tuple(np.round(G.target[0][:3].ravel(), 7)), tuple(azs))
        if key not in self._targets:
            m = Mesh(G.target[0], np.asarray(G.target[1]))
            if len(self._targets) >= 4:
                self._targets.pop(next(iter(self._targets)))
            self._targets[key] = {az: silhouette(m, az, fr) for az in azs}
        return self._targets[key]

    def ref_mask(self):
        """the reference image's silhouette (spec.ref.image: alpha > 0.5) as qa3d reads it."""
        if self._ref is None:
            from PIL import Image
            from . import cli
            ref = self.spec.get('ref') if isinstance(self.spec.get('ref'), dict) else {}
            p = ref.get('image')
            if not p or not os.path.exists(cli._path(p)):
                return None
            a = np.asarray(Image.open(cli._path(p)).convert('RGBA'), float)
            self._ref = a[..., 3] / 255.0 > 0.5 if a[..., 3].min() < 255 else a[..., :3].sum(-1) / 255.0 < 2.8
        return self._ref

    def qa(self, G, azs=AZ, labels=False):
        """qa3d's silhouette checks on the numpy geometry: shape IoU against the aligned generated shape per azimuth and
        per height band (hair above the chin, torso to the waist, skirt to the knee, legs), their means, and the front
        silhouette's IoU against the reference image (both cropped to their bounding boxes). -> dict (labels=True adds the
        label images and masks)."""
        fr = self.frame(G)
        lm = G.landmarks
        bands = {'hair': (lm['chin'], 99.0), 'torso': (lm['waist'], lm['chin']), 'skirt': (lm['knee'], lm['waist']),
                 'legs': (-99.0, lm['knee'])}
        H = fr.res[1]
        row = lambda z: int(round((0.5 - (z - fr.centre[2]) / fr.scale) * H))
        tm = self.target_masks(G, fr, azs)
        out = {'views': {}, 'checks': {}}
        labs = {}
        for az in azs:
            lab, _ = self.labels(G, az, fr)
            labs[az] = lab
            o = lab >= 0
            if tm is None:
                continue
            g = tm[az]
            d = {'iou': round(_iou(o, g), 3)}
            for bn, (z0, z1) in bands.items():
                r0, r1 = max(0, row(z1)), min(H, row(z0))
                if r1 > r0:
                    d['iou_' + bn] = round(_iou(o[r0:r1], g[r0:r1]), 3)
            out['views'][az] = d
        if tm is not None:
            out['checks']['shape_iou'] = round(float(np.mean([out['views'][a]['iou'] for a in azs])), 3)
            for bn in bands:
                out['checks']['shape_iou_' + bn] = round(float(np.mean([out['views'][a].get('iou_' + bn, 0) for a in azs])), 3)
        ref = self.ref_mask()
        if ref is not None and 0 in labs:
            out['checks']['ref_iou'] = round(_iou(bbox_norm(labs[0] >= 0), bbox_norm(ref)), 3)
        if labels:
            out['labels'], out['target'], out['frame'], out['bands'] = labs, tm, fr, bands
        return out


def _iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 1.0


def bbox_norm(mask, size=(200, 320)):
    """qa3d._bbox_norm: a mask cropped to its bounding box and resampled (nearest) to size."""
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return np.zeros(size[::-1], bool)
    m = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    H, W = size[1], size[0]
    yi = (np.arange(H) * m.shape[0] / H).astype(int); xi = (np.arange(W) * m.shape[1] / W).astype(int)
    return m[yi][:, xi]


# ------------------------------------------------------------------------------------------------------------ validation
def compare_dump(G, dump):
    """the numpy geometry against a Blender build's dump (charkit/bodyeval_blender.py), object by object: vertex counts,
    the largest vertex distance where the counts agree, the base mesh's bbox and trace hash, and the evaluated mesh's bbox
    (Blender's modifiers applied) against ours. -> {name: dict}, in metres."""
    from .trace import geometry_hash
    D = np.load(dump, allow_pickle=False)
    meta = json.loads(str(D['meta']))
    out = {}
    ours = {p.name: p for p in G.parts}
    for name in meta['objects']:
        b = D['o/%s/base' % name]
        ev = D['o/%s/evaluated' % name]
        r = {'blender_verts': int(len(b))}
        p = ours.get(name)
        if p is None:
            r['status'] = 'missing'
            out[name] = r
            continue
        r['verts'] = int(len(p.V))
        if len(p.V) == len(b):
            d = np.linalg.norm(p.V - b, axis=1)
            r['max_d'] = float(d.max()); r['mean_d'] = float(d.mean())
            # the trace's hashes, of our positions as Blender stores them (float32) on Blender's loops: the base mesh's, and
            # the evaluated one's where no modifier changes the geometry (the eyes, mouth, accessories, the hair cap)
            F = (D['o/%s/loops' % name], D['o/%s/starts' % name], D['o/%s/counts' % name])
            h = geometry_hash(p.V.astype(np.float32).astype(np.float64), F)
            r['base_hash_match'] = h == str(D['o/%s/base_hash' % name])
            r['trace_hash_match'] = h == str(D['o/%s/hash' % name])
        r['bbox_d'] = float(np.abs(np.r_[p.V.min(0) - b.min(0), p.V.max(0) - b.max(0)]).max())
        r['eval_bbox_d'] = float(np.abs(np.r_[p.V.min(0) - ev.min(0), p.V.max(0) - ev.max(0)]).max())
        out[name] = r
    for name in ours:
        if name not in out:
            out[name] = {'status': 'numpy only'}
    return out


# ------------------------------------------------------------------------------------------------------------ measures
MEASURES = {
    'iou': 'shape IoU against the generated shape, the mean over the six QA azimuths (qa3d shape_iou)',
    'iou_hair': 'the same above the chin', 'iou_torso': 'chin to waist', 'iou_skirt': 'waist to knee', 'iou_legs': 'below the knee',
    'ref_iou': 'front silhouette against the reference image, both cropped to their boxes (qa3d ref_iou)',
    'top': 'the silhouette top (hair, buns) above the target\'s, L', 'bottom': 'the feet\'s bottom below the target\'s, L',
    'arm_angle': 'the arms\' outer line from vertical (front, shoulder to waist) minus the target\'s, degrees',
    'leg_angle': 'each leg\'s centre line from vertical (front, below the knee) minus the target\'s, degrees',
    'leg_gap': 'the gap between the legs (front, below the knee) minus the target\'s, L',
}
for _v in ('front', 'side'):
    for _b in ('hair', 'torso', 'skirt', 'legs'):
        MEASURES['%s_%s_fill' % (_v, _b)] = 'filled width per row in the %s band, %s view, minus the target\'s, L' % (_b, _v)
        MEASURES['%s_%s_span' % (_v, _b)] = 'outer extent per row in the %s band, %s view, minus the target\'s, L' % (_b, _v)


def _rows_z(fr):
    H = fr.res[1]
    return fr.centre[2] + (0.5 - (np.arange(H) + 0.5) / H) * fr.scale


def _profile(m):
    """per row: filled count, leftmost and rightmost column (NaN where empty)."""
    cnt = m.sum(1).astype(float)
    has = cnt > 0
    lo = np.where(has, np.argmax(m, 1), np.nan)
    hi = np.where(has, m.shape[1] - 1 - np.argmax(m[:, ::-1], 1), np.nan)
    return cnt, lo, hi


def _line_angle(z, x):
    """the angle from vertical (degrees) of a least-squares line x(z)."""
    ok = np.isfinite(x)
    if ok.sum() < 4:
        return np.nan
    k = np.polyfit(z[ok], x[ok], 1)[0]
    return float(np.degrees(np.arctan(k)))


def pose_measures(m, fr, lm):
    """the arms' and legs' lines in a front silhouette: arm_angle (outer contour, shoulder to waist, both sides' mean),
    leg_angle (each leg's centre line below the knee), leg_gap (the empty run between the legs there, L)."""
    z = _rows_z(fr)
    pix = fr.scale / fr.res[1]
    L = lm['L']
    W = m.shape[1]; mid = W // 2
    _, lo, hi = _profile(m)
    arm = (z < lm['chin'] - 0.45 * L) & (z > lm['waist'])
    a_r = _line_angle(z[arm], (hi[arm] - mid) * pix)
    a_l = _line_angle(z[arm], (mid - lo[arm]) * pix)
    legs = (z < lm['knee'] - 0.2 * L) & (z > lm['knee'] - 1.2 * L)
    cols = np.arange(W)
    left, right = m[:, :mid], m[:, mid:]
    with np.errstate(invalid='ignore'):
        cl = (left * cols[:mid]).sum(1) / left.sum(1)
        cr = (right * cols[mid:]).sum(1) / right.sum(1)
    l_r = _line_angle(z[legs], (cr[legs] - mid) * pix)
    l_l = _line_angle(z[legs], (mid - cl[legs]) * pix)
    gap = []
    for r in np.nonzero(legs)[0]:
        row = m[r]
        if row[:mid].any() and row[mid:].any():
            a_ = mid - 1 - np.argmax(row[:mid][::-1])          # the left leg's inner edge
            b_ = mid + np.argmax(row[mid:])                     # the right leg's inner edge
            gap.append((b_ - a_ - 1) * pix / L)
    return dict(arm_angle=-np.nanmean([a_r, a_l]), leg_angle=-np.nanmean([l_r, l_l]),
                leg_gap=float(np.mean(gap)) if gap else np.nan)


def measures(G, Q):
    """the silhouette measurements (MEASURES) from a qa(..., labels=True) result: the QA's IoUs, and ours minus the
    target's for the band profiles (front and side), the extents and the pose lines."""
    fr, lm, bands = Q['frame'], G.landmarks, Q['bands']
    L = lm['L']
    pix = fr.scale / fr.res[1]
    z = _rows_z(fr)
    out = {k.replace('shape_', ''): v for k, v in Q['checks'].items()}
    T = Q['target']
    if T is None:
        return out
    for view, az in (('front', 0), ('side', 90)):
        o, g = Q['labels'][az] >= 0, T[az]
        (co, lo_o, hi_o), (cg, lo_g, hi_g) = _profile(o), _profile(g)
        for b, (z0, z1) in bands.items():
            rows = (z >= z0) & (z < z1) & ((co > 0) | (cg > 0))
            if not rows.any():
                continue
            out['%s_%s_fill' % (view, b)] = float((co[rows] - cg[rows]).mean() * pix / L)
            so, sg = hi_o - lo_o + 1, hi_g - lo_g + 1
            both = rows & np.isfinite(so) & np.isfinite(sg)
            out['%s_%s_span' % (view, b)] = float(np.nanmean(so[both] - sg[both]) * pix / L) if both.any() else np.nan
        if view == 'front':
            ro, rg = np.nonzero(co)[0], np.nonzero(cg)[0]
            out['top'] = float((z[ro[0]] - z[rg[0]]) / L)
            out['bottom'] = float((z[rg[-1]] - z[ro[-1]]) / L)
            po, pg = pose_measures(o, fr, lm), pose_measures(g, fr, lm)
            for k in po:
                out[k] = float(po[k] - pg[k])
                out[k + '_ours'] = float(po[k]); out[k + '_target'] = float(pg[k])
    return out


# validate()'s tolerances: the build's own spec (exact), and a base spec with knob overrides (composed: a body knob carries
# the head over and keeps the hair selection; the collar's surface walk can jump a vertex on a sub-millimetre change)
TOL = dict(exact=dict(objects_max_m=1e-5, hair_bbox_m=0.002, hair_iou=0.97, qa=0.01, mask_ours=0.98, mask_target=0.995),
           composed=dict(objects_mean_m=1e-3, hair_bbox_m=0.002, hair_iou=0.95, qa=0.01, mask_ours=0.98, mask_target=0.99),
           speedup=10.0)


def _decode_overlay(path, n):
    """qa3d's shape overlay (six views side by side: grey both, red ours only, blue target only) -> [(ours, target)]."""
    from PIL import Image
    ov = np.asarray(Image.open(path).convert('RGB')).astype(float) / 255
    W = ov.shape[1] // n
    out = []
    for i in range(n):
        im = ov[:, i * W:(i + 1) * W]
        near = lambda c: np.abs(im - np.array(c)).sum(-1) < 0.1
        g, r, b = near((0.55, 0.55, 0.6)), near((0.9, 0.2, 0.2)), near((0.2, 0.35, 0.95))
        out.append((g | r, g | b))
    return out


def validate(build, out=None, base=None, knobs=None, probes=None, log=print):
    """the fast evaluator against a finished Blender build (`python -m charkit build SPEC --out BUILD`, with its QA): the
    geometry object by object (a Blender dump of the same resolved spec, charkit/bodyeval_blender.py), the QA checks and
    the silhouettes pixel by pixel (qa3d's overlay), and the time per evaluation. base, knobs: evaluate that spec with
    these knob overrides instead of the build's own spec (the build made from them), so the knob paths are checked (a body
    knob composes the body onto the base's head). -> report dict (also out/validate.json)."""
    import subprocess
    from . import cli, trace
    build = _abs(build)
    qa = json.load(open(os.path.join(build, 'qa', 'qa.json')))
    spec_path = next(os.path.join(build, f) for f in sorted(os.listdir(build)) if f.endswith('.spec.json'))
    out = _abs(out or os.path.join(build, 'bodyeval'))
    os.makedirs(out, exist_ok=True)
    dump = os.path.join(out, 'dump.npz')
    if not os.path.exists(dump):
        log('dumping the Blender geometry ...')
        r = subprocess.run([cli.BLENDER, '-b', '--factory-startup', '--python',
                            os.path.join(ROOT, 'charkit', 'bodyeval_blender.py'), '--', spec_path, dump],
                           capture_output=True, text=True)
        if 'CHARKIT_BODYEVAL_DUMP' not in r.stdout:
            raise SystemExit('the Blender dump failed:\n' + (r.stdout + r.stderr)[-3000:])
    rep = {'build': build, 'tolerances': TOL, 'base': base, 'knobs': knobs}
    t = time.time()
    E = Evaluator(base or spec_path)
    t_res = time.time() - t
    t = time.time()
    if knobs:
        E.geometry()                                                     # the base first: the knobs then take the fast path
    G = E.geometry(knobs)
    rep['how'] = G.timings.get('how')
    Q = E.qa(G, labels=True)
    t_cold = time.time() - t
    # objects
    objs = compare_dump(G, dump)
    D = np.load(dump)
    same = {k: v for k, v in objs.items() if 'max_d' in v}
    rep['objects'] = objs
    rep['objects_same_code_max_m'] = max(v['max_d'] for v in same.values()) if same else None
    # the ported hair against Blender's, as silhouettes at the QA framing
    hs = next((p for p in G.parts if p.name == 'hair_shape'), None)
    if hs is not None and 'o/hair_shape/base' in D:
        from .geom.mesh import Mesh
        from .geom.raster import Frame, silhouette
        bl = Mesh(D['o/hair_shape/base'], triangulate([tuple(D['o/hair_shape/loops'][a:a + c]) for a, c in
                                                        zip(D['o/hair_shape/starts'], D['o/hair_shape/counts'])]))
        fr = Frame((0.0, 0.0, float(hs.V[:, 2].mean())), float(np.ptp(hs.V[:, 2])) * 1.3, (400, 400))
        rep['hair_shape_iou'] = {az: round(_iou(silhouette(Mesh(hs.V, hs.tris()), az, fr), silhouette(bl, az, fr)), 4)
                                 for az in (0, 90, 180)}
    # QA
    rep['qa'] = {k: {'blender': qa['checks'][k].get('value'), 'numpy': v} for k, v in Q['checks'].items()
                 if k in qa['checks'] or 'shape_' + k in qa['checks']}
    for k, v in Q['checks'].items():
        bk = k if k in qa['checks'] else None
        if bk:
            rep['qa'][k] = {'blender': qa['checks'][bk].get('value'), 'numpy': v}
    rep['qa_views'] = {str(az): {'blender': qa['views'].get(str(az)), 'numpy': Q['views'][az]} for az in AZ}
    ovp = os.path.join(build, 'qa', 'qa_shape_overlay.png')
    if os.path.exists(ovp):
        masks = _decode_overlay(ovp, len(AZ))
        rep['masks'] = {str(az): {'ours': round(_iou(Q['labels'][az] >= 0, o), 4), 'target': round(_iou(Q['target'][az], g), 4)}
                        for az, (o, g) in zip(AZ, masks)}
    # time: Blender's build and QA against warm numpy evaluations, one knob of each kind
    recs = trace.read(os.path.join(build, 'trace.jsonl'))
    t_bl = next((r['total'] for r in recs if r['event'] == 'end'), None)
    t_qa = sum(r['dt'] for r in recs if r['event'] == 'span' and r.get('name') == 'qa')
    t_board = sum(r['dt'] for r in recs if r['event'] == 'span' and r.get('name') == 'board')
    probes = probes or {'garments': ('garments.skirt.flare', 38.0, -3), 'body': ('body.proportions.leg', 1.1, -0.05),
                       'hair': ('hair.shape.below', 0.25, 0.03), 'accessories': ('accessories.star.size', 0.16, 0.02)}
    per, first = {}, {}
    for grp, (path, d0, dv) in probes.items():
        if get_knob(G.spec, path.rsplit('.', 1)[0]) is None:
            continue
        v = float(get_knob(G.spec, path, d0))
        for i, val in enumerate((v + dv, v + 1.5 * dv)):                  # the first, then a warm one
            t = time.time()
            G2 = E.geometry({path: val}); measures(G2, E.qa(G2, labels=True))
            (first if i == 0 else per)[grp] = round(time.time() - t, 2)
    blender_eval = (t_bl - t_board) if t_bl else None                    # a build and its QA, without the boards
    rep['time'] = {'blender_build_and_qa_s': round(blender_eval, 1) if blender_eval else None, 'blender_qa_s': round(t_qa, 1),
                   'numpy_resolve_s': round(t_res, 1), 'numpy_first_eval_s': round(t_cold, 1),
                   'numpy_per_knob_first_s': first, 'numpy_per_knob_s': per,
                   'speedup_worst': round(blender_eval / max(per.values()), 1) if blender_eval and per else None}
    # verdict
    fails = []
    tol = TOL['composed' if knobs else 'exact']
    rep['objects_mean_m'] = max(v['mean_d'] for v in same.values()) if same else None
    if 'objects_max_m' in tol and (rep['objects_same_code_max_m'] or 0) > tol['objects_max_m']:
        fails.append('objects differ by %.2g m' % rep['objects_same_code_max_m'])
    if 'objects_mean_m' in tol and (rep['objects_mean_m'] or 0) > tol['objects_mean_m']:
        fails.append('objects differ by %.2g m on average' % rep['objects_mean_m'])
    hsr = objs.get('hair_shape', {})
    if hsr.get('bbox_d', 0) > tol['hair_bbox_m']:
        fails.append('hair_shape bbox off by %.4f m' % hsr['bbox_d'])
    if rep.get('hair_shape_iou') and min(rep['hair_shape_iou'].values()) < tol['hair_iou']:
        fails.append('hair_shape silhouette IoU %.3f' % min(rep['hair_shape_iou'].values()))
    for k, v in rep['qa'].items():
        if v['blender'] is not None and abs(v['blender'] - v['numpy']) > tol['qa']:
            fails.append('qa %s: %.3f vs %.3f' % (k, v['numpy'], v['blender']))
    for az, v in (rep.get('masks') or {}).items():
        if v['ours'] < tol['mask_ours'] or v['target'] < tol['mask_target']:
            fails.append('masks at %s: ours %.3f target %.3f' % (az, v['ours'], v['target']))
    if rep['time']['speedup_worst'] is not None and rep['time']['speedup_worst'] < TOL['speedup']:
        fails.append('only %.1fx faster' % rep['time']['speedup_worst'])
    rep['verdict'] = 'FAIL' if fails else 'PASS'
    rep['why'] = fails
    json.dump(rep, open(os.path.join(out, 'validate.json'), 'w'), indent=1, default=float)
    from .geom.raster import overlay, save_png
    save_png(np.concatenate([overlay(Q['labels'][az] >= 0, Q['target'][az]) for az in AZ], 1),
             os.path.join(out, 'shape_overlay.png'))
    return rep


def main(args):
    """python -m charkit bodyeval SPEC [--knob PATH=VALUE ...] [--out DIR]    the QA checks and measurements, numpy
       python -m charkit bodyeval --validate BUILD [--out DIR]               against a finished Blender build
       python -m charkit bodyeval --validate BUILD --from SPEC --knob PATH=VALUE ...
                                                    (BUILD made from SPEC with those knobs: checks the fast knob path)"""
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); print(main.__doc__); return
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    knobs = {}
    for i, a in enumerate(args):
        if a == '--knob':
            p, v = args[i + 1].split('=', 1)
            knobs[p] = json.loads(v)
    if '--validate' in args:
        rep = validate(opt('--validate'), opt('--out'), base=opt('--from'), knobs=knobs or None)
        print('objects (%s): max %.2g m, mean %.2g m; hair_shape bbox %.4f m, silhouette IoU %s' % (
            rep['how'], rep['objects_same_code_max_m'] or 0, rep['objects_mean_m'] or 0,
            rep['objects'].get('hair_shape', {}).get('bbox_d', 0), rep.get('hair_shape_iou')))
        for k, v in rep['qa'].items():
            print('  %-18s blender %-7s numpy %s' % (k, v['blender'], v['numpy']))
        print('masks', rep.get('masks'))
        print('time', rep['time'])
        print('validate:', rep['verdict'], '; '.join(rep['why']))
        return
    E = Evaluator(args[0])
    t = time.time()
    G = E.geometry(knobs)
    Q = E.qa(G, labels=True)
    M = measures(G, Q)
    print('%.1fs  %s' % (time.time() - t, G.timings))
    for k, v in M.items():
        print('  %-22s %s' % (k, round(v, 4) if isinstance(v, float) else v))
    out = opt('--out')
    if out:
        from .geom.raster import overlay, save_png
        os.makedirs(_abs(out), exist_ok=True)
        json.dump(dict(knobs=knobs, measures=M, views=Q['views']), open(os.path.join(_abs(out), 'eval.json'), 'w'), indent=1,
                  default=float)
        save_png(np.concatenate([overlay(Q['labels'][az] >= 0, Q['target'][az]) for az in AZ], 1),
                 os.path.join(_abs(out), 'shape_overlay.png'))
