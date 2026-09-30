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

from .bodymeasure import AZ, iou as _iou                    # (the measurements live in charkit/bodymeasure.py)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBDIV = {'viewport': {'skin': 1, 'garments': 1}, 'render': {'skin': 2, 'garments': 1}, 'base': {}}   # the build's levels
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
    spec = manifest.produce(manifest.resolve(json.load(open(cli._path(spec_path)))))
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
def assemble_cached(spec, cache=True):
    """character.assemble, kept on disk by charkit.geomstage.assemble (the build's own venv stages share it): keyed by the
    spec, the content of the code head and body it names, and the assembly's code closure (charkit.cache.code_units)."""
    from . import geomstage
    return geomstage.assemble(spec, keep=cache)


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
    """one object: name, group (skin, eyes, mouth, hair, accessories, garments), world verts, polygons, and per polygon
    the sRGB tones its material renders unlit (lit, shade) and its model-sheet class (charkit.bodyqa.CLASS; -1: not drawn,
    a transparent texel), when known."""

    def __init__(self, name, group, V, polys, lit=None, shade=None, cls=None):
        self.name, self.group, self.V = name, group, np.asarray(V, float)
        self.polys = polys
        self.lit, self.shade, self.cls = lit, shade, cls
        self._tris = None

    def tris(self):
        if self._tris is None:
            self._tris = triangulate(self.polys, with_poly=True)
        return self._tris[0]

    def tri_poly(self):
        self.tris()
        return self._tris[1]

    def subdivided(self, levels):
        """the part after `levels` of Catmull-Clark (subdivide), as Blender's Subdivision Surface evaluates it, with each
        new face's tones (a textured part sampled at the new face's UV centre) and class. Cached on the part.
        -> (V, quads, parent polygon per quad, lit, shade, cls or None)."""
        cache = self.__dict__.setdefault('_sub', {})
        if levels not in cache:
            V, polys, parent = self.V, self.polys, np.arange(len(self.polys))
            tex = getattr(self, 'tex', None)
            uvc = tex['uvc'] if tex else None
            if getattr(self, 'solid', None):                   # the build's Solidify, before its Subdivision Surface
                polys, uvc = recalc_normals(V, polys, uvc)      # (the faces as garments._object winds them)
                V, polys, parent, uvc = solidify(V, polys, self.solid, uvc)
            for _ in range(levels):
                V, polys, par, uvc = subdivide(V, polys, uvc)
                parent = parent[par]
            if tex:
                uvm = uvc.mean(1) if uvc is not None else np.zeros((len(polys), 2))
                lit, shade = tex['fn'](uvm, parent)
            else:
                lit = self.lit[parent] if self.lit is not None else None
                shade = self.shade[parent] if self.shade is not None else None
            cache[levels] = (V, polys, parent, lit, shade, self.cls[parent] if self.cls is not None else None)
        return cache[levels]

    def __repr__(self):
        return 'Part(%s, %s, %d verts)' % (self.name, self.group, len(self.V))


def triangulate(polys, with_poly=False):
    """fan triangles of polygons (a list of index tuples or an (n, k) array). -> (m, 3) int array [, each triangle's
    polygon]."""
    if isinstance(polys, np.ndarray) and polys.ndim == 2:
        P = polys.astype(np.int64)
        k = P.shape[1]
        T = np.concatenate([P[:, [0, j, j + 1]] for j in range(1, k - 1)]) if k >= 3 else P[:0, :3]
        return (T, np.tile(np.arange(len(P)), max(0, k - 2))) if with_poly else T
    out, pid = [], []
    by = {}
    for i, f in enumerate(polys):
        by.setdefault(len(f), []).append(i)
    for k, ids in sorted(by.items()):
        if k < 3:
            continue
        P = np.asarray([polys[i] for i in ids], np.int64)
        out += [P[:, [0, j, j + 1]] for j in range(1, k - 1)]
        pid += [np.asarray(ids)] * (k - 2)
    T = np.concatenate(out) if out else np.zeros((0, 3), np.int64)
    return (T, np.concatenate(pid) if pid else np.zeros(0, np.int64)) if with_poly else T


def garment_piece(A, s, nrm=None, dom=None, hull=None, spec_all=None):
    """one garment piece as the build makes it: garments.build itself, run on the assembly with its Blender calls
    recorded (charkit.geomstage, the build's own garments stage: the same product the Blender side replays), read back
    as a Part (garment_part) and the skin vertices it hides; hull: garments.hull_pieces' points, for a garment whose
    `source` is 'hull'. (nrm, dom: unused, kept for callers; build() computes its own.) -> (Part, hide indices)."""
    from . import geomstage
    P = geomstage.product('garments', geomstage.record(A, [s], hull=hull, spec_all=spec_all))
    obs, hide = geomstage.pieces(P)
    if len(obs) != 1:
        raise ValueError('%s: garments.build made %d objects' % (s.get('name'), len(obs)))
    return garment_part(obs[0]), (np.nonzero(hide)[0] if hide is not None else np.zeros(0, np.int64))


def garment_part(o):
    """a recorded garment object (charkit.geomstage.pieces) as an evaluator Part: its mesh; per face the tones its material
    slot renders unlit (a toon's colour; a textured toon's texel at the face's UV centre, the texture as Blender's byte
    image holds it; the shade tone the material's multiplier times it); the thickness its Solidify gives it."""
    from . import garments as gm, geomstage
    polys = o['polys']
    nf = len(polys)
    slot = np.asarray(o['mat_idx'], int) if o['mat_idx'] is not None else np.zeros(nf, int)
    if o['uv_corner'] is not None:
        uvc = [np.asarray(c, float) for c in o['uv_corner']]
    elif o['uv'] is not None:
        U = np.asarray(o['uv'], float)
        uvc = [U[list(f)] for f in polys]
    else:
        uvc = None
    cols, texs, muls = [], {}, []
    for k, m in enumerate(o['materials']):
        muls.append(np.asarray(m['shade'] if m['shade'] is not None else gm.SHADE_MUL, float))
        if m['fn'] == 'toon_tex':
            texs[k] = geomstage.blender_bytes(m['image'])
            cols.append(None)
        else:
            cols.append(np.asarray(m['color'], float))
    muls = np.array(muls)

    def tones(uv_centre, parent):
        sl = slot[parent]
        lit = np.zeros((len(parent), 3))
        for k in range(len(cols)):
            sel = sl == k
            if sel.any():
                lit[sel] = _texel(texs[k], uv_centre[sel])[:, :3] if k in texs else cols[k]
        return lit, lit * muls[sl]
    base_uv = np.array([c.mean(0) for c in uvc]) if uvc is not None else np.zeros((nf, 2))
    lit, shade = tones(base_uv, np.arange(nf))
    P = Part(o['name'], 'garments', o['V'], polys, lit, shade)
    P.tex = dict(uvc=uvc, fn=tones)
    sol = o['mods'].get('thick')
    if sol is not None and sol['type'] == 'SOLIDIFY':            # the thickness the build's Solidify gives it (evaluated)
        P.solid = float(sol['settings']['thickness'])
    return P


def _texel(img, uv):
    """charkit.qa3d.poly_colours' texture lookup: an (n, n, C) image (row 0 = top, as built) at UVs (clipped), the texel
    Blender's bottom-up pixels put there."""
    h, w = img.shape[:2]
    uv = np.clip(np.nan_to_num(uv, nan=0.0), 0, 1 - 1e-6)
    return img[h - 1 - (uv[:, 1] * h).astype(int), (uv[:, 0] * w).astype(int)]


def _face_uv(faces, uv):
    """per face, the mean of its corners' UVs (per-vertex uv (n, 2) or per-corner [[uv, ...], ...])."""
    if uv is not None and len(uv) == len(faces) and len(faces) and hasattr(uv[0][0], '__len__'):
        return np.array([np.mean(c, 0) for c in uv])
    U = np.asarray(uv, float)
    return np.array([U[list(f)].mean(0) for f in faces])


GARMENT_BODIES = 4       # the garment cache keeps the pieces of this many bodies (assemblies), the most recently used


def garment_parts(A, specs, cache=None, akey=None, hull=None, spec_all=None):
    """every garment piece (garment_piece) and the skin vertices the tight shells and shoes hide, as garments.build's mask
    does. cache: a dict reused across calls; a piece is rebuilt only when its spec or the assembly (akey) changed. The
    cache keeps the pieces of the GARMENT_BODIES most recently used assemblies (a fit tries a new body every body-knob
    step: unbounded, it grew by the pieces of every one). -> ([Part], hide (N,) bool)."""
    hide = np.zeros(len(A['verts']), bool)
    parts = []
    for s in specs or []:
        key = (akey, _h(s)) if akey is not None else None
        if cache is None or key not in cache:
            r = garment_piece(A, s, hull=hull, spec_all=spec_all)
            if cache is not None:
                cache[key] = r
        else:
            r = cache.pop(key)
            cache[key] = r                                   # most recently used last
        parts.append(r[0]); hide[r[1]] = True
    if cache is not None and akey is not None:
        bodies = list(dict.fromkeys(k[0] for k in cache))    # oldest first
        for old in bodies[:-GARMENT_BODIES]:
            for k in [k for k in cache if k[0] == old]:
                del cache[k]
    return parts, hide


def _flat(n, c):
    c = np.asarray(c, float)
    return np.tile(c, (n, 1)), np.tile(c, (n, 1))


def _plate(E, key, tex):
    """an eye plate's per-polygon texture colour and alpha at the polygon's UV centre."""
    _, q, uv = E[key]
    px = _texel(tex, _face_uv(q, uv))
    return px[:, :3].astype(float), px[:, 3].astype(float)


def character_parts(A, hide=None, spec=None):
    """the skin (minus the vertices the garments hide, as the build's mask modifier does), the eyes and the mouth, with
    their materials' unlit tones and model-sheet classes per polygon (qa3d.scene_classes' rules: the skin by material,
    the iris where its texture is opaque, the sclera and teeth white, lashes, brows and lines as line)."""
    from . import eyetex
    from .bodyqa import CLASS as CL
    from .scene import SKIN
    spec = spec or {}
    F = A['faces']
    keep = np.ones(len(F), bool) if hide is None or not hide.any() else \
        np.array([not any(hide[v] for v in f) for f in F])
    sk = {k: tuple(v) for k, v in spec.get('skin', {}).items()} or SKIN
    tone = {0: (sk['lit'], sk['shade'], CL['skin']), 1: (sk['lit'], sk['shade'], CL['skin']),
            2: (spec.get('cavity_color', (0.38, 0.12, 0.15)),) * 2 + (CL['line'],),
            3: (spec.get('eyeline_color', (0.22, 0.12, 0.10)),) * 2 + (CL['line'],)}
    out = []
    # the skin as it renders (the garments' mask on) and, for the face measures that read it without the mask (qa3d.sheet),
    # the whole skin (roles 'masked' and 'unmasked': each measure reads one, charkit.bodymeasure.objects)
    for sel, role in ((keep, 'masked'), (np.ones(len(F), bool), 'unmasked')):
        if role and keep.all():
            break
        polys = [f for f, k in zip(F, sel) if k]
        fm = np.asarray(A['fmat'])[sel]
        lit = np.array([tone[m][0] for m in fm], float); shd = np.array([tone[m][1] for m in fm], float)
        out.append(Part(A.get('_name', 'char') + '_skin', 'skin', A['verts'], polys, lit, shd,
                        np.array([tone[m][2] for m in fm])))
        out[-1].role = role
    if len(out) == 1:
        out[0].role = None
    IK = spec.get('iris')
    ir = eyetex.iris(IK)

    def comp_(sd):
        sh = eyetex.shine(IK, side=sd)
        al = sh[..., 3:4]
        return np.concatenate([ir[..., :3] * (1 - al) + sh[..., :3] * al, np.maximum(ir[..., 3:4], al)], -1)
    comps = {1: comp_(1)}
    comps[-1] = comp_(-1) if not eyetex._knobs(IK).get('shine_mirror', True) else comps[1]
    scl = eyetex.sclera(IK)
    lash_c = spec.get('lash_color', (0.16, 0.09, 0.10)); brow_c = spec.get('brow_color', (0.30, 0.20, 0.20))
    for E in A['eyes']:
        tag = 'L' if E['side'] > 0 else 'R'
        c, _ = _plate(E, 'sclera', scl)
        out.append(Part('sclera_' + tag, 'eyes', E['sclera'][0], E['sclera'][1], c, c, np.full(len(c), CL['white'])))
        c, a = _plate(E, 'iris', comps[1 if E['side'] > 0 else -1])
        out.append(Part('iris_' + tag, 'eyes', E['iris'][0], E['iris'][1], c, c, np.where(a >= 0.5, CL['iris'], -1)))
        lv, lq, off = [], [], 0
        for rv, rq in E['lashes']:
            lv.append(rv); lq += [tuple(i + off for i in f) for f in rq]; off += len(rv)
        out.append(Part('lash_' + tag, 'eyes', np.vstack(lv), lq, *_flat(len(lq), lash_c), np.full(len(lq), CL['line'])))
        bq = E['brow'][1]
        out.append(Part('brow_' + tag, 'eyes', E['brow'][0], bq, *_flat(len(bq), brow_c), np.full(len(bq), CL['line'])))
    Mo = A['mouth']
    for nm, key, c, cl in (('teeth', 'teeth', (0.97, 0.96, 0.97), CL['white']), ('tongue', 'tongue', (0.86, 0.46, 0.50), CL['other']),
                           ('mouth_line', 'line', spec.get('mouth_line_color', (0.36, 0.16, 0.14)), CL['line'])):
        q = Mo[key][1]
        out.append(Part(nm, 'mouth', Mo[key][0], q, *_flat(len(q), c), np.full(len(q), cl)))
    return out


def hair_tones(parts, spec):
    """the hair's and accessories' unlit tones and classes (in place): the hair objects all hair (scene's materials:
    the generated hair's toon3 of lit/shade, the cap's of shade/deep, the locks' 'hair'), an accessory by its colour
    family (an orange one sits in the hair; one made of the hair's material is hair)."""
    from .bodyqa import CLASS as CL, family
    C = dict(lit=(0.96, 0.93, 0.98), shade=(0.72, 0.74, 0.90), deep=(0.52, 0.52, 0.72))
    C.update({k: tuple(v) for k, v in (spec.get('hair_colors') or {}).items()})
    for p in parts:
        n = len(p.polys)
        if p.group == 'hair':
            lit, shd = (C['shade'], C['deep']) if p.name == 'hair_cap' else (C['lit'], C['shade'])
            p.lit, p.shade = _flat(n, lit)[0], _flat(n, shd)[0]
            p.cls = np.full(n, CL['hair'])
        elif p.group == 'accessories':
            a = getattr(p, 'spec', {})
            if a.get('material', a.get('kind')) == 'hair':
                p.lit, p.shade = _flat(n, C['lit'])[0], _flat(n, C['shade'])[0]
            else:
                p.lit = p.shade = _flat(n, a.get('color', (0.9, 0.9, 0.9)))[0]
            fam = family(p.lit)
            p.cls = np.where(fam == CL['orange'], CL['hair'], fam)


class Geometry:
    """what `Evaluator.geometry` returns: the parts, the assembly, the landmarks the QA bands use, the aligned target."""

    def __init__(self, spec, A, parts, target=None, align=None, timings=None):
        from .garments import bone_seg
        self.spec, self.A, self.parts, self.target, self.align = spec, A, parts, target, align
        Hd = A['head']
        self.L = float(Hd['L'])
        self.landmarks = dict(L=self.L, centre=np.asarray(Hd['centre'], float), chin=float(Hd['centre'][2] - Hd['H'].chin),
                              waist=float(bone_seg(A, 'spine')[0][2]), knee=float(bone_seg(A, 'leftLowerLeg')[0][2]),
                              eye_z=float(Hd['eye_z']) if Hd.get('eye_z') is not None else None)
        self.timings = timings or {}

    def bundle(self, levels='viewport'):
        """the geometry as plain data (charkit.bodymeasure's bundle): per object its world verts, triangles, and per
        triangle a model-sheet class and the unlit tones; the landmarks; the aligned target. levels: the subdivision the
        build's evaluated meshes carry, 'viewport' (what the in-Blender QA z-buffers: skin and garments at level 1),
        'render' (what its renders show: skin 2, garments 1), 'base' (none), or {group: level}."""
        lv = SUBDIV[levels] if isinstance(levels, str) else levels
        key = json.dumps(lv, sort_keys=True)
        self.__dict__.setdefault('_bundles', {})
        if key not in self._bundles:
            from .bodyqa import CLASS as CL, family
            objs = []
            for p in self.parts:
                n_ = lv.get(p.group, 0)
                if n_:
                    V, polys, parent, lit, shd, cls = p.subdivided(n_)
                    T, pid = triangulate(polys, with_poly=True)
                    origin = parent[pid]                                  # each triangle's polygon of the part
                else:
                    V, T, pid = p.V, p.tris(), p.tri_poly()
                    lit, shd, cls = p.lit, p.shade, p.cls
                    origin = pid
                n = len(pid) and int(pid.max()) + 1
                lit = lit if lit is not None else np.full((max(n, 1), 3), 0.5)
                shd = shd if shd is not None else lit
                cls = cls if cls is not None else family(lit) if p.lit is not None else np.full(len(lit), CL['other'])
                objs.append(dict(name=p.name, group=p.group, V=V, F=T, label=np.asarray(cls)[pid], lit=lit[pid],
                                 shade=shd[pid], role=getattr(p, 'role', None)))
                if p.group == 'skin':
                    objs[-1]['scalp'] = self.scalp_polys(p)[origin]
            iris = np.array([p.V.mean(0) for p in self.parts if p.name.startswith('iris_')])
            self._bundles[key] = dict(objects=objs, landmarks=dict(self.landmarks, iris=iris), target=self.target)
        return self._bundles[key]

    def scalp_polys(self, p):
        """per polygon of a skin part: all its vertices on the scalp qa3d flags (the head's upper cranium and the back of
        the head)."""
        A = self.A; Hd = A['head']; L = Hd['L']
        V = A['verts']; hw = A['body']['head_w']; cz = Hd['centre'][2]; cy = Hd['centre'][1]
        region = (hw > 0.5) & ((V[:, 2] > cz + 0.30 * L) | ((V[:, 1] > cy + 0.10 * L) & (V[:, 2] > cz - 0.20 * L)))
        return np.array([all(region[v] for v in f) for f in p.polys], bool)

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
        self.exact_geom = False      # mode geom's hair cut afresh for each body (see hair_parts), not carried
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
            self._gen = ((np.asarray(V), np.asarray(F), np.asarray(C)), i3d.glb_eyes(p, np.asarray(V), np.asarray(C)))
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
        if shape and shape.get('mode') in ('mesh', 'geom', 'pieces'):         # (as scene.stage_hair: the hair carries them)
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
                # the extraction reads the body too (the hair is kept outside it, so the back and shoulders trim what
                # hangs there), and takes 30-60 s. By default it is cut at the evaluator's own body and garments, keyed
                # by the head and the hair's own knobs, and carried in the head frame: a body knob moves it with the head,
                # as the mesh mode's selection. exact_geom cuts it for each spec (cached on disk by the spec): the
                # measurements a fit is judged by
                hk = {k: v for k, v in shape.items() if k not in ('mode', 'geom')}
                if self.exact_geom:
                    gk = _h([head, hk, {k: v for k, v in spec.items() if k != 'hair'}])
                    cut = lambda: (lambda r: (to_head(r[0], A), r[1]))(self.geom_hair(spec, A))
                else:
                    gk = _h([head, hk])
                    S0 = dict(spec, body=self.spec.get('body'), garments=self.spec.get('garments'))
                    cut = lambda: (lambda A0: (lambda r: (to_head(r[0], A0), r[1]))(self.geom_hair(S0, A0)))(
                        self.assembly(S0)[0])
                gv, gf = self._memo('geom', gk, cut)
                objects.append(('hair_shape', gv, gf))
            elif mode == 'pieces':
                # the hair's pieces as the build makes them (charkit.geom.hairpieces, the build's venv step): read from the
                # product a build wrote (shape['pieces']), else made by that same step (cli.pieces_hair, cached). Keyed
                # and carried in the head frame as the geom mode's cut; exact_geom makes them for each spec
                hk = {k: v for k, v in shape.items() if k not in ('mode', 'pieces', 'geom')}
                if self.exact_geom:
                    pk = _h([head, hk, {k: v for k, v in spec.items() if k != 'hair'}])
                    make = lambda: [(n, to_head(v, A), f) for n, v, f in self.pieces_hair(spec)]
                else:
                    pk = _h([head, hk, shape.get('pieces')])
                    S0 = dict(spec, body=self.spec.get('body'), garments=self.spec.get('garments'))
                    make = lambda: (lambda A0: [(n, to_head(v, A0), f) for n, v, f in self.pieces_hair(S0)])(
                        self.assembly(S0)[0])
                objects += self._memo('pieces', pk, make)
            if mode in ('mesh', 'geom') and (mode == 'mesh' or shape.get('cap', False)):
                objects.append(('hair_cap',) + self._memo('cap', _h([head, style]), lambda: (lambda r: (to_head(r[0], A), r[1]))(
                    hair_cap(A, spec))))
            vkey = _h([skey, style])
            vol = lambda: self._memo('volume', _h([vkey, list(c), L]), lambda: mesh_volume(A, spec, sel_w()))
            if mode not in ('mesh', 'geom', 'pieces'):
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
        accs = self._memo('accessories', _h([vkey, acc]), lambda: [(n, to_head(v, A), f, a) for n, v, f, a in
                                                                   accessories.generate(vol(), L, acc)])
        parts = [Part(n, 'hair', from_head(q, A), f) for n, q, f in objects]
        for n, q, f, a in accs:
            parts.append(Part(n, 'accessories', from_head(q, A), f))
            parts[-1].spec = a
        return parts, full, align

    def pieces_hair(self, spec):
        """mode 'pieces': the hair's pieces in world, [(hair_NAME, V, F)] in the product's order: the product a build
        wrote (shape['pieces'], pieces.json and a part per piece), else the build's own step run for this spec
        (cli.pieces_hair, its file_step cache) into charkit/out/bodyeval/pieces/KEY."""
        from . import cli
        from .geom.io import load_npz
        shape = spec['hair']['shape']
        pdir = shape.get('pieces')
        if not (pdir and os.path.exists(os.path.join(cli._path(pdir), 'pieces.json'))):
            key = _h({k: v for k, v in spec.items() if k != 'garments'})
            out = os.path.join(ROOT, 'charkit', 'out', 'bodyeval', 'pieces', key)
            os.makedirs(out, exist_ok=True)
            S = cli.pieces_hair(copy.deepcopy(spec), os.path.join(out, 'spec.json'), out)
            pdir = S['hair']['shape']['pieces']
        pdir = cli._path(pdir)
        index = json.load(open(os.path.join(pdir, 'pieces.json')))
        out = []
        for p in index['pieces']:
            m = load_npz(os.path.join(pdir, p['file']))
            out.append(('hair_' + p['name'], np.asarray(m.V, float), np.asarray(m.F)))
        return out

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
        hull = None
        if any(g.get('source') == 'hull' for g in spec.get('garments') or []):
            from . import garments as gm
            glb = ((spec.get('hair') or {}).get('shape') or {}).get('glb')
            akey = akey + (glb,)
            hk = (akey, 'hull')
            if hk not in self._garments:
                self._garments[hk] = gm.hull_pieces(spec, A)
            hull = self._garments[hk]
        if len(self._garments) > 400:
            self._garments = {k: v for k, v in self._garments.items() if k[0] == akey}
        garm, hide = garment_parts(A, spec.get('garments'), self._garments, akey, hull, spec)
        t3 = time.time()
        hair_tones(hair, spec)
        ckey = (akey, hashlib.sha1(np.packbits(hide).tobytes()).hexdigest()[:12],
                _h({k: spec.get(k) for k in ('skin', 'iris', 'lash_color', 'brow_color', 'cavity_color', 'eyeline_color',
                                             'mouth_line_color')}))
        if getattr(self, '_char', (None,))[0] != ckey:                   # (their subdivision rides on the parts)
            self._char = (ckey, character_parts(A, hide, spec))
        parts = self._char[1] + hair + garm
        return Geometry(spec, A, parts, target, align, timings=dict(assembly=round(t1 - t0, 3), how=how,
                                                                    hair=round(t2 - t1, 3), garments=round(t3 - t2, 3)))

    # ---- measuring
    def frame(self, G):
        """qa3d's QA camera for this geometry (bodymeasure.frame over its base meshes)."""
        from . import bodymeasure
        return bodymeasure.frame(G.bundle('base'))

    def target_masks(self, G, fr, azs=AZ):
        if G.target is None:
            return None
        from . import bodymeasure
        key = (tuple(np.round(fr.centre, 7)), round(fr.scale, 7), tuple(np.round(G.target[0][:3].ravel(), 7)), tuple(azs))
        if key not in self._targets:
            if len(self._targets) >= 4:
                self._targets.pop(next(iter(self._targets)))
            self._targets[key] = bodymeasure.target_masks(G.target, fr, azs)
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

    def qa(self, G, azs=AZ, labels=False, levels='render'):
        """qa3d's silhouette checks on the geometry (bodymeasure.shape on its bundle, subdivided as the build renders):
        shape IoU against the aligned generated shape per azimuth and band, their means, and ref_iou. -> dict (labels=True
        adds the label images, the target masks, the framing and the bands)."""
        from . import bodymeasure
        fr = self.frame(G)
        return bodymeasure.shape(G.bundle(levels), fr, self.target_masks(G, fr, azs), self.ref_mask(), azs, labels)

    def sheet(self):
        """the model sheet measured once (bodymeasure.Sheet), or None without one."""
        if not hasattr(self, '_sheet'):
            from . import bodymeasure
            try:
                self._sheet = bodymeasure.Sheet(self.spec)
            except ValueError:
                self._sheet = None
        return self._sheet

    def face_checks(self, G):
        """qa3d's sheet_* checks (the face against the model sheet's heads) on the geometry (bodymeasure.sheet_face),
        as qa.json names them."""
        from . import bodymeasure
        S = self.sheet()
        if S is None:
            return {}
        return {'sheet_' + k: v for k, v in bodymeasure.sheet_face(G.bundle('viewport'), S)[1].items()}

    def sheet_checks(self, G, palette=True):
        """qa3d's body_* and palette_* checks against the model sheet on the geometry (bodymeasure.sheet_body and
        sheet_palette on its bundle, subdivided as the build evaluates it). -> {check: dict} named as qa.json names them."""
        from . import bodymeasure
        S = self.sheet()
        if S is None:
            return {}
        B = G.bundle('viewport')
        _, C, _ = bodymeasure.sheet_body(B, S)
        out = {'body_' + k: v for k, v in C.items()}
        if palette:
            out.update({'palette_' + k: v for k, v in bodymeasure.sheet_palette(B, S)[1].items()})
        return out


def measures(G, Q):
    """bodymeasure.measures for a Geometry and its qa(..., labels=True)."""
    from . import bodymeasure
    return bodymeasure.measures(Q, G.landmarks)


# ------------------------------------------------------------------------------------------------------------ validation
def compare_dump(G, dump):
    """the numpy geometry against a Blender build's dump (charkit/bodyeval_blender.py), object by object: vertex counts,
    the largest vertex distance where the counts agree, the base mesh's bbox and trace hash, and the evaluated mesh's bbox
    (Blender's modifiers applied) against ours. -> {name: dict}, in metres."""
    from .trace import geometry_hash
    D = np.load(dump, allow_pickle=False)
    meta = json.loads(str(D['meta']))
    out = {}
    ours = {p.name: p for p in G.parts if getattr(p, 'role', None) != 'unmasked'}
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
        lv = SUBDIV['viewport'].get(p.group, 0)
        if lv and p.group == 'garments':
            # the evaluated mesh (Solidify, then the Subdivision Surface) against Blender's, each of our vertices to
            # its nearest (Blender's vertex order differs; its Solidify also moves loose vertices, which draw nothing)
            from scipy.spatial import cKDTree
            Ve = p.subdivided(lv)[0]
            d = cKDTree(ev).query(Ve)[0]
            r['eval_verts'], r['blender_eval_verts'] = int(len(Ve)), int(len(ev))
            r['eval_max_d'] = float(d.max())
        out[name] = r
    for name in ours:
        if name not in out:
            out[name] = {'status': 'numpy only'}
    return out


# validate()'s tolerances: the build's own spec (exact), and a base spec with knob overrides (composed: a body knob carries
# the head over and keeps the hair selection; the collar's surface walk can jump a vertex on a sub-millimetre change)
TOL = dict(exact=dict(objects_max_m=1e-5, hair_bbox_m=0.002, hair_iou=0.96, qa=0.01, mask_ours=0.98, mask_target=0.995,
                      sheet=0.02, sheet_deg=1.5, sheet_de=0.5),
           composed=dict(objects_mean_m=1e-3, hair_bbox_m=0.002, hair_iou=0.95, qa=0.01, mask_ours=0.98, mask_target=0.99,
                         sheet=0.03, sheet_deg=2.0, sheet_de=1.0),
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
    from . import cli, trace
    build = _abs(build)
    qa = json.load(open(os.path.join(build, 'qa', 'qa.json')))
    spec_path = next(os.path.join(build, f) for f in sorted(os.listdir(build)) if f.endswith('.spec.json'))
    out = _abs(out or os.path.join(build, 'bodyeval'))
    os.makedirs(out, exist_ok=True)
    dump = os.path.join(out, 'dump.npz')
    if not os.path.exists(dump):
        log('dumping the Blender geometry ...')
        from . import procs
        r = procs.run([cli.BLENDER, '-b', '--factory-startup', '--python',
                       os.path.join(ROOT, 'charkit', 'bodyeval_blender.py'), '--', spec_path, dump], out, 'bodyeval dump')
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
    # the model sheet's body and palette checks
    SC = E.sheet_checks(G) if any(k.startswith(('body_', 'palette_')) for k in qa['checks']) else {}
    if any(k.startswith('sheet_') for k in qa['checks']):
        SC.update(E.face_checks(G))
    rep['sheet'] = {k: {'blender': [qa['checks'][k].get('value'), qa['checks'][k].get('status')],
                        'numpy': [v.get('value'), v.get('status')]} for k, v in SC.items() if k in qa['checks']}
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
    ev = {n: v for n, v in objs.items() if 'eval_max_d' in v}
    rep['evaluated_max_m'] = max(v['eval_max_d'] for v in ev.values()) if ev else None
    for n, v in ev.items():
        if v['eval_verts'] != v['blender_eval_verts']:
            fails.append('%s evaluates to %d verts, Blender %d' % (n, v['eval_verts'], v['blender_eval_verts']))
    if 'objects_max_m' in tol and (rep['evaluated_max_m'] or 0) > tol['objects_max_m']:
        fails.append('evaluated garments differ by %.2g m' % rep['evaluated_max_m'])
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
    for k, v in rep['sheet'].items():
        (bv, bs), (nv, ns) = v['blender'], v['numpy']
        t_ = tol['sheet_deg'] if k.endswith('_arms') else tol['sheet_de'] if k.startswith('palette_') else tol['sheet']
        off = abs(bv - nv) > t_ if isinstance(bv, (int, float)) and isinstance(nv, (int, float)) else bv != nv
        if k.startswith('sheet_shown'):                           # (warn only: how much face our undecimated hair covers)
            continue
        if off or (bs != ns and not k.endswith('_arms')):
            fails.append('%s: %s %s vs %s %s' % (k, nv, ns, bv, bs))
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
        print('objects (%s): max %.2g m, mean %.2g m, evaluated garments max %.2g m; hair_shape bbox %.4f m, silhouette IoU %s' % (
            rep['how'], rep['objects_same_code_max_m'] or 0, rep['objects_mean_m'] or 0, rep.get('evaluated_max_m') or 0,
            rep['objects'].get('hair_shape', {}).get('bbox_d', 0), rep.get('hair_shape_iou')))
        for k, v in rep['qa'].items():
            print('  %-18s blender %-7s numpy %s' % (k, v['blender'], v['numpy']))
        print('masks', rep.get('masks'))
        sh = rep.get('sheet') or {}
        if sh:
            same = sum(v['blender'][1] == v['numpy'][1] for v in sh.values())
            dv = [abs(v['blender'][0] - v['numpy'][0]) for k, v in sh.items() if not k.endswith('_arms') and
                  isinstance(v['blender'][0], (int, float)) and isinstance(v['numpy'][0], (int, float))]
            print('sheet checks: %d of %d grade the same; values within %.3f' % (same, len(sh), max(dv) if dv else 0))
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


# ------------------------------------------------------------------------------------------------------ subdivision


def _loops_of(polys):
    if isinstance(polys, np.ndarray) and polys.ndim == 2:
        cnt = np.full(len(polys), polys.shape[1])
        lv = polys.astype(np.int64).ravel()
    else:
        cnt = np.array([len(f) for f in polys])
        lv = np.concatenate([np.asarray(f, np.int64) for f in polys]) if len(polys) else np.zeros(0, np.int64)
    st = np.r_[0, np.cumsum(cnt)[:-1]].astype(np.int64)
    return lv, st, cnt


def vertex_normals(V, polys):
    """Blender's vertex normals: each polygon's normal (Newell's; for a quad the cross of its diagonals, as Blender's)
    weighted by the polygon's angle at the vertex, summed and normalised."""
    V = np.asarray(V, float)
    lv, st, cnt = _loops_of(polys)
    fid = np.repeat(np.arange(len(cnt)), cnt)
    nxt = np.arange(len(lv)) + 1; nxt[st + cnt - 1] = st
    prv = np.arange(len(lv)) - 1; prv[st] = st + cnt - 1
    FN = np.zeros((len(cnt), 3)); np.add.at(FN, fid, np.cross(V[lv], V[lv[nxt]]))
    FN /= np.maximum(np.linalg.norm(FN, axis=1, keepdims=True), 1e-30)
    e1 = V[lv[prv]] - V[lv]; e2 = V[lv[nxt]] - V[lv]
    e1 /= np.maximum(np.linalg.norm(e1, axis=1, keepdims=True), 1e-30)
    e2 /= np.maximum(np.linalg.norm(e2, axis=1, keepdims=True), 1e-30)
    ang = np.arccos(np.clip((e1 * e2).sum(1), -1, 1))
    N = np.zeros_like(V); np.add.at(N, lv, FN[fid] * ang[:, None])
    return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-30)


def recalc_normals(V, polys, uv=None):
    """bmesh.ops.recalc_face_normals (garments._object runs it on every piece): each connected region's polygons wound
    consistently, and the region turned so its outermost vertex's polygon faces away from the region's centre (the
    polygons' area-weighted centres; at that vertex the edge most across the outward direction, and of its polygons the
    one facing most along it). -> (polys, uv) with the flipped polygons (and their corner UVs) reversed."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    V = np.asarray(V, float)
    lv, st, cnt = _loops_of(polys)
    nf, n = len(cnt), len(V)
    fid = np.repeat(np.arange(nf), cnt)
    nxt = np.arange(len(lv)) + 1; nxt[st + cnt - 1] = st
    a, b = lv, lv[nxt]
    key = np.minimum(a, b) * n + np.maximum(a, b)
    order = np.argsort(key, kind='stable')
    ks = key[order]
    same = np.nonzero(ks[1:] == ks[:-1])[0]
    i, j = order[same], order[same + 1]                       # loops sharing an edge (consecutive pairs)
    flip_rel = (a[i] == a[j])                                 # the same direction in both: one of them is reversed
    nc, comp = connected_components(coo_matrix((np.ones(len(i)), (fid[i], fid[j])), shape=(nf, nf)), directed=False)
    flip = np.zeros(nf, bool); seen = np.zeros(nf, bool)
    adj = [[] for _ in range(nf)]
    for x, y, r in zip(fid[i], fid[j], flip_rel):
        adj[x].append((y, r)); adj[y].append((x, r))
    for f0 in range(nf):                                       # breadth first from each region's first polygon
        if seen[f0]:
            continue
        seen[f0] = True; queue = [f0]
        while queue:
            f = queue.pop()
            for g, r in adj[f]:
                if not seen[g]:
                    seen[g] = True; flip[g] = flip[f] ^ r; queue.append(g)
    FN = np.zeros((nf, 3)); np.add.at(FN, fid, np.cross(V[lv], V[lv[nxt]]))
    area = np.linalg.norm(FN, axis=1) / 2
    FN = FN / np.maximum(2 * area, 1e-30)[:, None] * np.where(flip, -1, 1)[:, None]
    FC = np.zeros((nf, 3)); np.add.at(FC, fid, V[lv]); FC /= cnt[:, None]
    for c in range(nc):
        fs = np.nonzero(comp == c)[0]
        w = area[fs]
        cent = (FC[fs] * w[:, None]).sum(0) / max(w.sum(), 1e-30)
        m = np.isin(fid, fs)
        loops = np.nonzero(m)[0]
        v = lv[loops[np.argmax(((V[lv[loops]] - cent) ** 2).sum(1))]]
        d = V[v] - cent; d /= max(np.linalg.norm(d), 1e-30)
        at = loops[(lv[loops] == v) | (b[loops] == v)]         # the edges at the vertex, by the loops that run them
        ev = V[b[at]] - V[a[at]]; ev /= np.maximum(np.linalg.norm(ev, axis=1, keepdims=True), 1e-30)
        ed = np.abs(ev @ d)
        best = at[ed <= ed.min() + 1e-6]                        # the edge most across the outward direction
        k_ = key[best]
        cand = np.nonzero(np.isin(key, k_) & m)[0]
        f = fid[cand[np.argmax(np.abs(FN[fid[cand]] @ d))]]
        if FN[f] @ d < 0:
            flip[fs] = ~flip[fs]
    P = [tuple(int(x) for x in (lv[s_:s_ + c_][::-1] if flip[q] else lv[s_:s_ + c_])) for q, (s_, c_) in enumerate(zip(st, cnt))]
    if uv is None:
        return P, None
    Uc = uv.reshape(-1, 2) if isinstance(uv, np.ndarray) else np.concatenate([np.asarray(c_, float) for c_ in uv])
    return P, [Uc[s_:s_ + c_][::-1] if flip[q] else Uc[s_:s_ + c_] for q, (s_, c_) in enumerate(zip(st, cnt))]


def solidify(V, polys, t, uv=None, rim=True):
    """Blender's Solidify (simple, offset -1, even thickness off): the surface moved t against its vertex normals and a
    copy left where it was (its polygons reversed), each open edge joined across by a rim quad. uv: per-corner UVs as
    subdivide takes them. -> (V (2n, 3), polys, parent polygon per polygon, uv or None)."""
    V = np.asarray(V, float)
    n = len(V)
    lv, st, cnt = _loops_of(polys)
    fid = np.repeat(np.arange(len(cnt)), cnt)
    nxt = np.arange(len(lv)) + 1; nxt[st + cnt - 1] = st
    NV = np.vstack([V - t * vertex_normals(V, polys), V])
    P = [tuple(int(x) for x in lv[s_:s_ + c]) for s_, c in zip(st, cnt)]
    out = P + [tuple(x + n for x in f[::-1]) for f in P]
    parent = list(range(len(P))) * 2
    U = None
    if uv is not None:
        Uc = uv.reshape(-1, 2) if isinstance(uv, np.ndarray) else np.concatenate([np.asarray(c, float) for c in uv])
        U = [Uc[s_:s_ + c] for s_, c in zip(st, cnt)]
        U = U + [u[::-1] for u in U]
    if rim:
        a, b = lv, lv[nxt]
        key = np.minimum(a, b) * n + np.maximum(a, b)
        _, inv, c_ = np.unique(key, return_inverse=True, return_counts=True)
        for i in np.nonzero(c_[inv] == 1)[0]:
            out.append((int(b[i]), int(a[i]), int(a[i]) + n, int(b[i]) + n))
            parent.append(int(fid[i]))
            if U is not None:
                ua, ub = Uc[i], Uc[nxt[i]]
                U.append(np.array([ub, ua, ua, ub]))
    return NV, out, np.asarray(parent), U


def subdivide(V, polys, uv=None, limit=True):
    """one level of Catmull-Clark (Blender's Subdivision Surface at level 1: boundaries smooth, the result pushed to the
    limit surface), numpy. polys: index tuples of any size; uv: optional per-corner UVs [[(u, v), ...] per polygon],
    interpolated linearly. -> (V (n, 3), quads (m, 4), parent polygon per quad (m,), uv per corner (m, 4, 2) or None)."""
    from scipy import sparse
    V = np.asarray(V, float)
    nv = len(V)
    if isinstance(polys, np.ndarray) and polys.ndim == 2:
        cnt = np.full(len(polys), polys.shape[1])
        lv = polys.astype(np.int64).ravel()
    else:
        cnt = np.array([len(f) for f in polys])
        lv = np.concatenate([np.asarray(f, np.int64) for f in polys])
    st = np.r_[0, np.cumsum(cnt)[:-1]]
    nf = len(polys)
    fid = np.repeat(np.arange(nf), cnt)
    nxt = np.arange(len(lv)) + 1
    nxt[st + cnt - 1] = st
    prv = np.arange(len(lv)) - 1
    prv[st] = st + cnt - 1
    FP = np.zeros((nf, 3)); np.add.at(FP, fid, V[lv]); FP /= cnt[:, None]
    # edges: one per unordered pair; each loop's edge runs to the next corner
    a, b = lv, lv[nxt]
    key = np.minimum(a, b) * nv + np.maximum(a, b)
    ukey, einv, ecnt = np.unique(key, return_inverse=True, return_counts=True)
    ne = len(ukey)
    ea, eb = ukey // nv, ukey % nv
    efs = np.zeros((ne, 3)); np.add.at(efs, einv, FP[fid])
    bnd = ecnt == 1
    EP = np.where(bnd[:, None], (V[ea] + V[eb]) / 2, (V[ea] + V[eb] + efs) / 4)      # (two faces' points summed)
    EP = np.where((ecnt > 2)[:, None], (V[ea] + V[eb]) / 2, EP)             # (non-manifold: the midpoint)
    # vertices: interior (Q + 2R + (n - 3) S) / n; boundary (prev + 6 v + next) / 8
    ones = np.ones(ne)
    VE = sparse.coo_matrix((np.r_[ones, ones], (np.r_[ea, eb], np.r_[np.arange(ne), np.arange(ne)])), shape=(nv, ne)).tocsr()
    val = np.asarray(VE.sum(1)).ravel()
    R = (VE @ ((V[ea] + V[eb]) / 2)) / np.maximum(val, 1)[:, None]
    VF = sparse.coo_matrix((np.ones(len(lv)), (lv, fid)), shape=(nv, nf)).tocsr()
    nfv = np.asarray(VF.sum(1)).ravel()
    Q = (VF @ FP) / np.maximum(nfv, 1)[:, None]
    n_ = np.maximum(val, 1)[:, None]
    VP = (Q + 2 * R + (n_ - 3) * V) / n_
    VB = sparse.coo_matrix((np.r_[ones[bnd], ones[bnd]], (np.r_[ea[bnd], eb[bnd]], np.r_[eb[bnd], ea[bnd]])), shape=(nv, nv)).tocsr()
    nb_ = np.asarray(VB.sum(1)).ravel()
    onb = nb_ == 2
    VP[onb] = ((VB @ V)[onb] + 6 * V[onb]) / 8
    VP[(nb_ > 0) & ~onb] = V[(nb_ > 0) & ~onb]                             # (a corner of several boundaries: kept)
    VP[val == 0] = V[val == 0]
    # the new mesh: vertices, then face points, then edge points; a quad per corner
    NV = np.vstack([VP, FP, EP])
    e_next = einv                                                         # the edge from this corner to the next
    e_prev = einv[prv]                                                    # the edge into this corner
    quads = np.stack([lv, nv + nf + e_next, nv + fid, nv + nf + e_prev], 1)
    # each child quad starts where Blender's does (corner c of its polygon: rotated by -c), so a fan triangulation
    # (faceqa.triangles) cuts it along the same diagonal as Blender's evaluated mesh
    corner = np.arange(len(lv)) - st[fid]
    rot = (-corner) % 4
    quads = quads[np.arange(len(quads))[:, None], (np.arange(4)[None, :] + rot[:, None]) % 4]
    parent = fid
    UV = None
    if uv is not None:
        U = uv.reshape(-1, 2) if isinstance(uv, np.ndarray) else np.concatenate([np.asarray(c, float) for c in uv])
        fuv = np.zeros((nf, 2)); np.add.at(fuv, fid, U); fuv /= cnt[:, None]
        UV = np.stack([U, (U + U[nxt]) / 2, fuv[fid], (U + U[prv]) / 2], 1)
        UV = UV[np.arange(len(UV))[:, None], (np.arange(4)[None, :] + rot[:, None]) % 4]
    if limit:
        NV = limit_positions(NV, quads)
    return NV, quads, parent, UV


def limit_positions(V, quads):
    """Catmull-Clark limit positions of an all-quad mesh's vertices: interior (n^2 v + 4 sum(edge neighbours) + sum(face
    diagonals)) / (n (n + 5)); on a boundary the cubic B-spline's (prev + 4 v + next) / 6."""
    from scipy import sparse
    nv = len(V)
    Qd = np.asarray(quads, np.int64)
    a = Qd.ravel(); b = np.roll(Qd, -1, 1).ravel(); d = np.roll(Qd, -2, 1).ravel()
    key = np.minimum(a, b) * nv + np.maximum(a, b)
    ukey, cnt_e = np.unique(key, return_counts=True)
    ea, eb = ukey // nv, ukey % nv
    ne = len(ukey)
    E = sparse.coo_matrix((np.ones(2 * ne), (np.r_[ea, eb], np.r_[eb, ea])), shape=(nv, nv)).tocsr()
    val = np.asarray(E.sum(1)).ravel()
    Dg = sparse.coo_matrix((np.ones(len(a)), (a, d)), shape=(nv, nv)).tocsr()
    n = np.maximum(val, 1)[:, None]
    out = (n * n * V + 4 * (E @ V) + Dg @ V) / (n * (n + 5))
    bnd = cnt_e == 1
    B = sparse.coo_matrix((np.ones(2 * bnd.sum()), (np.r_[ea[bnd], eb[bnd]], np.r_[eb[bnd], ea[bnd]])), shape=(nv, nv)).tocsr()
    nb_ = np.asarray(B.sum(1)).ravel()
    on = nb_ == 2
    out[on] = ((B @ V)[on] + 4 * V[on]) / 6
    odd = (nb_ > 0) & ~on
    out[odd] = V[odd]
    out[val == 0] = V[val == 0]                                          # (a loose vertex stays where it is)
    return out
