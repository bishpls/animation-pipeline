"""Evaluated meshes (Michael's call J; docs/GEOM_TRUTH.md rollout step 7): the lab that measures charkit's own
Subdivision Surface and Solidify against Blender's, piece by piece.

A piece is a mesh (V, polygons as Blender holds them: the winding is the caller's), optional per-corner UVs, edge
creases, and a modifier stack (('SOLIDIFY', settings), ('SUBSURF', settings)). `blender(pieces)` runs the stack in a
local headless Blender (the build's version: infra/gcp/build.env) and returns each evaluated mesh; `compare(ours,
theirs)` measures ours against it per vertex (the vertex orders differ: matched by nearest vertex, and the match must be
one to one), per face count and per UV corner.

    python -m charkit evalmesh lab [--out DIR]          the synthetic shapes (creases, boundaries, n-gons, triangles)
    python -m charkit evalmesh build BUILD [--out DIR]  a build's pieces: its raw garments and its skin (the bundle's
                                                        inputs to the modifiers) through local Blender and through ours,
                                                        and the bundle's own evaluated meshes against both

Report: DIR/evalmesh.json and DIR/evalmesh.md (per piece: vertices and faces, max and mean vertex error in L, UV error).
"""
import json, os, subprocess, sys, time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLENDER = os.environ.get('BLENDER', '/Applications/Blender.app/Contents/MacOS/Blender')


# ------------------------------------------------------------------------------------------------------------ pieces
def piece(name, V, polys, uv=None, creases=None, mods=(), L=1.0, loose_edges=None):
    """a mesh for the lab. polys: index tuples (the winding as given; Blender keeps it); uv: per-corner UVs (a list per
    polygon, or (loops, 2)); creases: {(a, b): crease 0..1}; mods: [(type, {setting: value})] in stack order;
    loose_edges: (k, 2) edges on no polygon (what a Mask leaves: Blender's Subsurf makes their ends corners)."""
    lv = np.concatenate([np.asarray(f, np.int64) for f in polys]) if len(polys) else np.zeros(0, np.int64)
    cnt = np.array([len(f) for f in polys], np.int64)
    U = None
    if uv is not None:
        U = np.asarray(uv, float).reshape(-1, 2) if isinstance(uv, np.ndarray) else \
            np.concatenate([np.asarray(c, float).reshape(-1, 2) for c in uv])
    ce = np.array(sorted(creases), np.int64).reshape(-1, 2) if creases else np.zeros((0, 2), np.int64)
    cw = np.array([creases[tuple(e)] for e in ce.tolist()], float) if creases else np.zeros(0)
    le = np.asarray(loose_edges, np.int64).reshape(-1, 2) if loose_edges is not None and len(loose_edges) else None
    return dict(name=name, V=np.asarray(V, float), loopv=lv, counts=cnt, luv=U, crease_e=ce, crease_w=cw,
                mods=[(t, dict(s)) for t, s in mods], L=float(L), loose_e=le)


def polys_of(p):
    st = np.r_[0, np.cumsum(p['counts'])[:-1]]
    return [tuple(int(x) for x in p['loopv'][s:s + c]) for s, c in zip(st, p['counts'])]


def corner_uv(p):
    if p.get('luv') is None:
        return None
    st = np.r_[0, np.cumsum(p['counts'])[:-1]]
    return [p['luv'][s:s + c] for s, c in zip(st, p['counts'])]


def _save(path, pieces):
    arrays, meta = {}, []
    for i, p in enumerate(pieces):
        for k in ('V', 'loopv', 'counts', 'luv', 'crease_e', 'crease_w', 'groups', 'loose_e'):
            if p.get(k) is not None:
                arrays['%d/%s' % (i, k)] = np.asarray(p[k])
        meta.append(dict(name=p['name'], mods=p['mods'], L=p.get('L', 1.0)))
    arrays['meta'] = np.frombuffer(json.dumps(meta).encode(), np.uint8)
    np.savez(path, **arrays)


def _load(path):
    Z = np.load(path)
    meta = json.loads(bytes(Z['meta']).decode())
    out = []
    for i, m in enumerate(meta):
        p = dict(m)
        for k in ('V', 'loopv', 'counts', 'luv', 'crease_e', 'crease_w', 'parent', 'groups', 'loose_e'):
            key = '%d/%s' % (i, k)
            p[k] = Z[key] if key in Z.files else None
        out.append(p)
    return out


# ------------------------------------------------------------------------------------------------------------ Blender
def blender(pieces, work=None, log=print):
    """the pieces' modifier stacks evaluated by a local headless Blender -> [dict(name, V, loopv, counts, luv)]."""
    import tempfile
    work = work or tempfile.mkdtemp(prefix='evalmesh_')
    os.makedirs(work, exist_ok=True)
    inp, out = os.path.join(work, 'in.npz'), os.path.join(work, 'out.npz')
    _save(inp, pieces)
    expr = 'import sys; sys.path.insert(0, %r); from charkit import evalmesh; evalmesh.blender_main(%r, %r)' % (ROOT, inp, out)
    t = time.time()
    r = subprocess.run([BLENDER, '-b', '--factory-startup', '--python-exit-code', '1', '--python-expr', expr],
                       capture_output=True, text=True)
    if r.returncode or not os.path.exists(out):
        raise RuntimeError('evalmesh: Blender failed (%d):\n%s' % (r.returncode, (r.stdout + r.stderr)[-3000:]))
    log('evalmesh: Blender evaluated %d pieces in %.1f s' % (len(pieces), time.time() - t))
    return _load(out)


def _bl_mesh(p):
    import bpy
    me = bpy.data.meshes.new(p['name'])
    V, lv, cnt = p['V'], p['loopv'], p['counts']
    me.vertices.add(len(V))
    me.vertices.foreach_set('co', np.asarray(V, np.float32).ravel())
    me.loops.add(len(lv))
    me.loops.foreach_set('vertex_index', np.asarray(lv, np.int32))
    me.polygons.add(len(cnt))
    me.polygons.foreach_set('loop_start', np.r_[0, np.cumsum(cnt)[:-1]].astype(np.int32))
    me.update(calc_edges=True)
    if p.get('loose_e') is not None and len(p['loose_e']):     # (through bmesh: edges.add crashes 5.2 on a large mesh;
        import bmesh                                               # vertex, face and loop order kept)
        bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
        for a_, b_ in np.asarray(p['loose_e'], np.int64).tolist():
            bm.edges.new((bm.verts[a_], bm.verts[b_]))
        bm.to_mesh(me); bm.free()
    if p.get('luv') is not None:
        lay = me.uv_layers.new(name='uv')
        lay.data.foreach_set('uv', np.asarray(p['luv'], np.float32).ravel())
    if p.get('crease_e') is not None and len(p['crease_e']):
        cr = me.attributes.new('crease_edge', 'FLOAT', 'EDGE')
        n = len(V)
        ev = np.empty(len(me.edges) * 2, np.int64); me.edges.foreach_get('vertices', ev)
        ev = ev.reshape(-1, 2)
        ek = np.minimum(ev[:, 0], ev[:, 1]) * n + np.maximum(ev[:, 0], ev[:, 1])
        ce = np.asarray(p['crease_e'], np.int64)
        ck = np.minimum(ce[:, 0], ce[:, 1]) * n + np.maximum(ce[:, 0], ce[:, 1])
        w = np.zeros(len(ek), np.float32)
        order = np.argsort(ck)
        pos = np.searchsorted(ck[order], ek)
        pos = np.clip(pos, 0, len(ck) - 1)
        hit = ck[order][pos] == ek
        w[hit] = np.asarray(p['crease_w'], np.float32)[order][pos[hit]]
        cr.data.foreach_set('value', w)
    for poly in me.polygons:
        poly.use_smooth = True
    ob = bpy.data.objects.new(p['name'], me)
    bpy.context.scene.collection.objects.link(ob)
    G = p.get('groups')
    if G is not None and len(G):                                  # vertex groups (columns), as garments._object adds them
        for k in range(G.shape[1]):
            g = ob.vertex_groups.new(name='g%d' % k)
            for w_ in np.unique(G[:, k]):
                if w_ > 0:
                    g.add([int(i) for i in np.nonzero(G[:, k] == w_)[0]], float(w_), 'REPLACE')
    for i, (t, s) in enumerate(p['mods']):
        m = ob.modifiers.new('m%d' % i, t)
        for k, v in s.items():
            setattr(m, k, v)
    return ob


def blender_main(inp, out):
    """inside Blender: evaluate every piece of `inp` and write `out`."""
    import bpy
    pieces = _load(inp)
    res = []
    for p in pieces:
        ob = _bl_mesh(p)
        dg = bpy.context.evaluated_depsgraph_get()
        oe = ob.evaluated_get(dg)
        me = oe.to_mesh()
        n = len(me.vertices)
        co = np.empty(n * 3, np.float64); me.vertices.foreach_get('co', co)
        nf = len(me.polygons)
        cnt = np.empty(nf, np.int64); me.polygons.foreach_get('loop_total', cnt)
        st = np.empty(nf, np.int64); me.polygons.foreach_get('loop_start', st)
        lv = np.empty(len(me.loops), np.int64); me.loops.foreach_get('vertex_index', lv)
        order = np.concatenate([np.arange(s, s + c) for s, c in zip(st, cnt)]) if nf else np.zeros(0, np.int64)
        r = dict(name=p['name'], mods=p['mods'], L=p.get('L', 1.0), V=co.reshape(-1, 3), loopv=lv[order], counts=cnt)
        lay = me.uv_layers.get('uv')
        if lay is not None:
            uv = np.empty(len(me.loops) * 2, np.float32); lay.data.foreach_get('uv', uv)
            r['luv'] = uv.reshape(-1, 2)[order].astype(float)
        if p.get('groups') is not None and len(p['groups']):
            k = p['groups'].shape[1]
            Gw = np.zeros((n, k))
            for i, v in enumerate(me.vertices):
                for x in v.groups:
                    Gw[i, x.group] = x.weight
            r['groups'] = Gw
        ca = me.attributes.get('crease_edge')
        if ca is not None and len(me.edges):
            w = np.empty(len(me.edges), np.float32); ca.data.foreach_get('value', w)
            ev = np.empty(len(me.edges) * 2, np.int64); me.edges.foreach_get('vertices', ev)
            nz = w > 0
            r['crease_e'] = ev.reshape(-1, 2)[nz]; r['crease_w'] = w[nz].astype(float)
        oe.to_mesh_clear()
        res.append(r)
    _save(out, res)


# ------------------------------------------------------------------------------------------------------------ compare
def match(ours, theirs):
    """theirs' vertex j -> ours' index (nearest), and whether that is one to one. -> (idx, dist, bijective)."""
    from scipy.spatial import cKDTree
    d, idx = cKDTree(np.asarray(ours, float)).query(np.asarray(theirs, float))
    return idx, d, len(np.unique(idx)) == len(idx) == len(ours)


def on_face(m):
    """a mesh dict (V, loopv, counts, luv?) with only the vertices its polygons use (renumbered in order)."""
    lv = np.asarray(m['loopv'], np.int64)
    used = np.zeros(len(m['V']), bool); used[lv] = True
    remap = np.cumsum(used) - 1
    return dict(m, V=np.asarray(m['V'])[used], loopv=remap[lv])


def compare(ours, theirs, L=1.0):
    """ours (dict V, loopv, counts, luv?) against Blender's evaluation of the same piece -> dict(n, n_blender, faces,
    faces_blender, max_L, mean_L, p99_L, one_to_one, [uv_max, uv_mean], [winding: faces wound as Blender's]).
    ours['on_face_only'] (a piece with loose edges): both compared on their polygons' vertices (Blender's loose
    geometry, its edges' points, is never drawn; loose_blender counts it)."""
    extra = {}
    if ours.get('on_face_only'):
        n0 = len(theirs['V'])
        ours, theirs = on_face(ours), on_face(theirs)
        extra['loose_blender'] = n0 - len(theirs['V'])
    Vo, Vb = np.asarray(ours['V'], float), np.asarray(theirs['V'], float)
    r = dict(n=len(Vo), n_blender=len(Vb), faces=int(len(ours['counts'])), faces_blender=int(len(theirs['counts'])),
             **extra)
    if not len(Vo) or not len(Vb):
        return r
    idx, d, bij = match(Vo, Vb)
    r.update(max_L=float(d.max() / L), mean_L=float(d.mean() / L), p99_L=float(np.percentile(d, 99) / L), one_to_one=bool(bij))
    if bij:
        r['index_same'] = int((idx == np.arange(len(idx))).sum())             # (the vertex order: ours is Blender's)
    if bij and len(ours['counts']) == len(theirs['counts']):
        # faces matched by their vertex sets (theirs mapped into ours); corners by vertex
        Fo, Fb = polys_of(ours), polys_of(dict(theirs, loopv=idx[np.asarray(theirs['loopv'], np.int64)]))
        where = {tuple(sorted(f)): k for k, f in enumerate(Fo)}
        fo = np.array([where.get(tuple(sorted(f)), -1) for f in Fb])
        r['faces_matched'] = int((fo >= 0).sum())
        if (fo >= 0).all():
            wind = start = 0
            du = []
            Uo, Ub = corner_uv(ours), corner_uv(theirs)
            for k, f in enumerate(Fb):
                g = Fo[fo[k]]
                p0 = g.index(f[0])
                start += p0 == 0
                n_ = len(g)
                same = g[(p0 + 1) % n_] == f[1 % n_]
                wind += same
                if Uo is not None and Ub is not None:
                    pos = [g.index(v) for v in f]
                    du.append(np.linalg.norm(np.asarray(Uo[fo[k]])[pos] - np.asarray(Ub[k]), axis=1))
            r['winding_same'], r['start_same'] = int(wind), int(start)
            if du:
                du = np.concatenate(du)
                r.update(uv_max=float(du.max()), uv_mean=float(du.mean()))
    return r


# ------------------------------------------------------------------------------------------------------------ ours
def ours(p):
    """our port of a piece's modifier stack (charkit.geom.solidify, charkit.geom.subsurf) -> dict(V, loopv, counts,
    luv, crease_e, crease_w)."""
    from .geom import solidify as solid, subsurf
    V, lv, cnt, luv = p['V'], p['loopv'], p['counts'], p.get('luv')
    cre = (p['crease_e'], p['crease_w']) if p.get('crease_e') is not None and len(p['crease_e']) else None
    le = p.get('loose_e')
    vcr = None
    if le is not None and len(le):                               # (Blender's converter: a loose edge's ends are corners)
        vcr = np.zeros(len(V)); vcr[np.asarray(le, np.int64).ravel()] = 1.0
    for t, s in p['mods']:
        if t == 'SUBSURF':
            R = subsurf.subdivide(V, (lv, cnt), levels=int(s.get('levels', 1)), creases=cre, uv=luv, vcreases=vcr,
                                  uv_smooth=s.get('uv_smooth', 'PRESERVE_BOUNDARIES'))
            vcr = None
            V, lv, cnt = R['V'], R['quads'].ravel(), np.full(len(R['quads']), 4)
            luv = R['uv'].reshape(-1, 2) if R['uv'] is not None else None
            cre = None
        elif t == 'SOLIDIFY':
            if le is not None and len(le):
                raise NotImplementedError('%s: Solidify of loose edges' % p['name'])
            n = len(V)
            R = solid.solidify(V, (lv, cnt), float(s['thickness']), offset=s.get('offset', -1.0),
                               use_rim=s.get('use_rim', True), uv=luv, crease_outer=s.get('edge_crease_outer', 0.0),
                               crease_inner=s.get('edge_crease_inner', 0.0), crease_rim=s.get('edge_crease_rim', 0.0))
            pairs, vals = [R['creases'][0]], [R['creases'][1]]
            if cre is not None:                                  # (the input's creases: on both layers)
                ce = np.asarray(cre[0], np.int64)
                pairs = [ce, ce + n] + pairs; vals = [cre[1], cre[1]] + vals
            P = np.concatenate(pairs); W = np.concatenate(vals)
            cre = (P, W) if len(P) else None
            V, lv, cnt, luv = R['V'], R['loopv'], R['counts'], R['uv']
        else:
            raise NotImplementedError(t)
    return dict(V=V, loopv=lv, counts=cnt, luv=luv,
                crease_e=cre[0] if cre is not None else None, crease_w=cre[1] if cre is not None else None,
                on_face_only=le is not None and len(le) > 0)


# ------------------------------------------------------------------------------------------------------------ shapes
def _grid(nx, ny, z=lambda x, y: 0.0 * x):
    V = np.array([(x, y, z(x, y)) for y in range(ny) for x in range(nx)], float)
    F = [(y * nx + x, y * nx + x + 1, (y + 1) * nx + x + 1, (y + 1) * nx + x) for y in range(ny - 1) for x in range(nx - 1)]
    return V, F


def _cube():
    V = np.array([(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], float)
    idx = {tuple(v): i for i, v in enumerate(V.astype(int))}
    F = []
    for ax in range(3):
        for s in (-1, 1):
            cs = []
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                q = [0, 0, 0]; q[ax] = s; q[(ax + 1) % 3] = a; q[(ax + 2) % 3] = b
                cs.append(idx[tuple(q)])
            F.append(tuple(cs) if s > 0 else tuple(cs[::-1]))
    return V, F


def shapes():
    """synthetic pieces covering the rules: smooth, creased (sharp and semi-sharp), open borders and corners, n-gons
    and triangles, UV seams, two levels."""
    rng = np.random.default_rng(0)
    out = []
    V, F = _cube()
    V = V * np.array([1, 1.3, 0.8]) + 0.1 * rng.normal(size=V.shape)
    sub = lambda lev=1, **k: [('SUBSURF', dict(levels=lev, **k))]
    out.append(piece('cube', V, F, mods=sub()))
    out.append(piece('cube_l2', V, F, mods=sub(2)))
    ring = {(F[0][i], F[0][(i + 1) % 4]): 1.0 for i in range(4)}
    out.append(piece('cube_ring_sharp', V, F, creases=ring, mods=sub()))
    out.append(piece('cube_two_sharp', V, F, creases={(F[0][0], F[0][1]): 1.0, (F[0][1], F[0][2]): 1.0}, mods=sub()))
    for c in (0.2, 0.5, 0.7, 0.9):
        out.append(piece('cube_ring_c%.1f' % c, V, F, creases={k: c for k in ring}, mods=sub()))
        out.append(piece('cube_one_c%.1f' % c, V, F, creases={(F[0][0], F[0][1]): c}, mods=sub()))
    out.append(piece('cube_ring_c0.5_l2', V, F, creases={k: 0.5 for k in ring}, mods=sub(2)))
    G, GF = _grid(6, 5, lambda x, y: 0.3 * np.sin(x) * np.cos(0.7 * y))
    G = G + 0.05 * rng.normal(size=G.shape)
    out.append(piece('grid_open', G, GF, mods=sub()))
    out.append(piece('grid_open_l2', G, GF, mods=sub(2)))
    # UVs: per-vertex UVs (no seam), then a seam down the middle (the right half's UVs shifted)
    uvv = G[:, :2] / 6
    uvc = [[uvv[v] for v in f] for f in GF]
    out.append(piece('grid_uv', G, GF, uv=uvc, mods=sub()))
    uvs = [[uvv[v] + (np.array([0.5, 0.0]) if G[f, 0].mean() > 2.5 else 0) for v in f] for f in GF]
    out.append(piece('grid_uv_seam', G, GF, uv=uvs, mods=sub()))
    out.append(piece('grid_uv_seam_l2', G, GF, uv=uvs, mods=sub(2)))
    cuv = [[(0.5 + 0.3 * V[v, 0] + 0.05 * V[v, 2], 0.5 + 0.3 * V[v, 1]) for v in f] for f in F]
    out.append(piece('cube_uv', V, F, uv=cuv, mods=sub()))
    # triangles and an n-gon: a pentagon capped prism
    th = np.linspace(0, 2 * np.pi, 6)[:-1]
    P = np.array([(np.cos(t), np.sin(t), z) for z in (0, 1) for t in th]) + 0.05 * rng.normal(size=(10, 3))
    PF = [tuple(range(5))[::-1], tuple(range(5, 10))] + [(i, (i + 1) % 5, 5 + (i + 1) % 5, 5 + i) for i in range(5)]
    out.append(piece('prism_ngon', P, PF, mods=sub()))
    TF = [tuple(range(5))[::-1]] + [(i, (i + 1) % 5, 5 + (i + 1) % 5, 5 + i) for i in range(5)] + \
        [(5 + i, 5 + (i + 1) % 5, 10) for i in range(5)]
    P2 = np.vstack([P, [[0, 0, 1.4]]])
    out.append(piece('prism_tris', P2, TF, mods=sub()))
    out.append(piece('prism_tris_l2', P2, TF, mods=sub(2)))
    # a garment's shell (garments._thick): Solidify then the Subdivision, its rim rounded, then squared by Michael's
    # call L (both layers' open borders creased 1: OpenSubdiv's infinitely sharp), the UVs through both
    sol = lambda **k: [('SOLIDIFY', dict(thickness=0.08, offset=-1.0, use_rim=True, **k))] + sub()
    out.append(piece('grid_shell', G, GF, uv=uvc, mods=sol()))
    out.append(piece('grid_shell_rim_creased', G, GF, uv=uvs, mods=sol(edge_crease_outer=1.0, edge_crease_inner=1.0)))
    # what the build's Mask leaves: the two quads either side of an interior edge dropped, the edge kept (loose, its
    # ends on kept faces); a loose vertex of a dropped face; a Solidify's loose vertices (the template flaps')
    GFm = [f for i, f in enumerate(GF) if i not in (7, 12)]            # (8, 9, 15, 14) and (14, 15, 21, 20)
    out.append(piece('grid_loose_edge', G, GFm, uv=[uvc[i] for i in range(len(GF)) if i not in (7, 12)],
                     loose_edges=[(14, 15)], mods=sub()))
    out.append(piece('grid_loose_edge_l2', G, GFm, loose_edges=[(14, 15)], mods=sub(2)))
    Gl = np.vstack([G, G.mean(0) + (0.3, -0.2, 1.0)])
    out.append(piece('grid_shell_loose_vertex', Gl, GF, mods=sol(edge_crease_outer=1.0, edge_crease_inner=1.0)))
    return out


# ------------------------------------------------------------------------------------------------------------ builds
SKIP_SETTINGS = ('show_viewport', 'show_render')


def build_pieces(build, render=False):
    """a build's modifier inputs as lab pieces, and the bundle's evaluated meshes (the box's Blender) for each:
    the skin (the bundle's 'base': the armature-posed mesh, its eye margins creased as character.build creases them;
    at the viewport level, masked as it renders, and at the render level when `render`) and every garment (the
    bundle's raw mesh, its corner UVs and modifier settings from the garments product).
    -> ([piece], {name: the bundle's evaluated mesh or None}, L)."""
    from . import bundle as bundlelib, geomstage
    B = bundlelib.load(os.path.join(build, 'bundle'))
    asm = B.meta('assembly')
    L = float(asm['L'])
    out, truth = [], {}
    sk = B.skin()
    V, lv, cnt = sk.V('base'), sk.a('base', 'loopv'), sk.a('base', 'counts')
    luv = sk.a('base', 'luv')
    cre = {}
    for E in asm['eyes']:
        lp = list(E['margin'])
        for a_, b_ in zip(lp, lp[1:] + lp[:1]):
            cre[(min(a_, b_), max(a_, b_))] = 1.0
    polys = [tuple(int(x) for x in lv[s_:s_ + c]) for s_, c in zip(np.r_[0, np.cumsum(cnt)[:-1]], cnt)]
    uvc = [luv[s_:s_ + c] for s_, c in zip(np.r_[0, np.cumsum(cnt)[:-1]], cnt)] if luv is not None else None
    out.append(piece('skin', V, polys, uv=uvc, creases=cre, mods=[('SUBSURF', dict(levels=1))], L=L))
    truth['skin'] = dict(V=sk.V('eval'), loopv=sk.a('eval', 'loopv'), counts=sk.a('eval', 'counts'), luv=sk.a('eval', 'luv'))
    if B.has('skin/under_garments'):
        hide = np.asarray(B.array('skin/under_garments'), bool)
        keep = ~hide
        fk = [i for i, f in enumerate(polys) if keep[list(f)].all()]
        remap = np.full(len(V), -1, np.int64); remap[keep] = np.arange(keep.sum())
        Pm = [tuple(int(remap[v]) for v in polys[i]) for i in fk]
        Um = [uvc[i] for i in fk] if uvc is not None else None
        cm = {(int(min(remap[a_], remap[b_])), int(max(remap[a_], remap[b_]))): w for (a_, b_), w in cre.items()
              if keep[a_] and keep[b_]}
        from .bodyeval import mask_loose_edges                  # (what the Mask leaves besides: loose edges)
        out.append(piece('skin_masked', V[keep], Pm, uv=Um, creases=cm, mods=[('SUBSURF', dict(levels=1))], L=L,
                         loose_edges=remap[mask_loose_edges(polys, hide)]))
        truth['skin_masked'] = dict(V=sk.V('masked'), loopv=sk.a('masked', 'loopv'), counts=sk.a('masked', 'counts'),
                                    luv=sk.a('masked', 'luv'))
    if render:
        out.append(piece('skin_render', V, polys, uv=uvc, creases=cre, mods=[('SUBSURF', dict(levels=2))], L=L))
        truth['skin_render'] = None
    gp = os.path.join(build, 'geom', 'garments.npz')
    Pg = geomstage.load(gp) if os.path.exists(gp) else None
    final = Pg is not None and Pg['meta'].get('coarse_events') is not None     # (call J: the bundle's raw is final)
    obs = geomstage.pieces(Pg, coarse=True)[0] if Pg is not None else []
    for o in obs:
        bo = B.obj(o['name'])
        if final:                                               # the coarse mesh and its modifiers from the product
            Vr, pr = np.asarray(o['V'], float), [tuple(int(x) for x in f) for f in o['polys']]
        else:
            Vr, lvr, cntr = bo.V('raw'), bo.a('raw', 'loopv'), bo.a('raw', 'counts')
            pr = [tuple(int(x) for x in lvr[s_:s_ + c]) for s_, c in zip(np.r_[0, np.cumsum(cntr)[:-1]], cntr)]
        if o['uv_corner'] is not None:
            U = [np.asarray(u, float) for u in o['uv_corner']]
        elif o['uv'] is not None:
            U = [np.asarray(o['uv'], float)[list(f)] for f in pr]
        else:
            U = None
        if U is not None and [tuple(int(x) for x in f) for f in o['polys']] != pr:
            U = None                                            # (a product wound otherwise than the build: no UVs)
        mods = []
        for name, m in o['mods'].items():
            if m['type'] in ('SOLIDIFY', 'SUBSURF'):
                st = {k: v for k, v in m['settings'].items() if k not in SKIP_SETTINGS and k != 'render_levels'}
                mods.append((m['type'], st))
        out.append(piece(o['name'], Vr, pr, uv=U, mods=mods, L=L))
        truth[o['name']] = dict(V=bo.V('eval'), loopv=bo.a('eval', 'loopv'), counts=bo.a('eval', 'counts'),
                                luv=bo.a('eval', 'luv'))
    return out, truth, L


def run_build(build, out, render=False, names=None, log=print):
    """the lab on a build: per piece ours against local Blender, and each against the bundle's evaluated mesh."""
    pieces, truth, L = build_pieces(build, render)
    if names:
        pieces = [p for p in pieces if p['name'] in names]
    os.makedirs(out, exist_ok=True)
    # each stage on its own: Solidify alone, and the Subdivision Surface on Blender's own Solidify
    sol = [dict(p, name=p['name'] + ':solidify', mods=[m for m in p['mods'] if m[0] == 'SOLIDIFY'])
           for p in pieces if any(m[0] == 'SOLIDIFY' for m in p['mods'])]
    if sol:
        Bs = blender(sol, work=os.path.join(out, 'blender_solidify'), log=log)
        for p, b in zip(sol, Bs):
            name = p['name'].split(':')[0]
            full = next(q for q in pieces if q['name'] == name)
            sub = [m for m in full['mods'] if m[0] == 'SUBSURF']
            if sub:
                pieces.append(dict(b, name=name + ':subsurf', mods=sub, L=L,
                                   crease_e=b.get('crease_e') if b.get('crease_e') is not None else np.zeros((0, 2), np.int64),
                                   crease_w=b.get('crease_w') if b.get('crease_w') is not None else np.zeros(0)))
        pieces += sol
    Bl = blender(pieces, work=os.path.join(out, 'blender'), log=log)
    rows = []
    for p, b in zip(pieces, Bl):
        t = time.time()
        o = ours(p)
        dt = time.time() - t
        r = dict(piece=p['name'], mods=p['mods'], seconds=round(dt, 2), ours_blender=compare(o, b, L))
        tr = truth.get(p['name'])
        if tr is not None:
            r['blender_bundle'] = compare(b, tr, L)
            r['ours_bundle'] = compare(o, tr, L)
        rows.append(r)
        log('%-18s %s' % (p['name'], _fmt(r['ours_blender'])))
    rep = dict(build=build, rows=rows)
    json.dump(rep, open(os.path.join(out, 'evalmesh.json'), 'w'), indent=1, default=str)
    open(os.path.join(out, 'evalmesh.md'), 'w').write(markdown(rep))
    return rep


def _fmt(r):
    if 'max_L' not in r:
        return 'n %d/%d faces %d/%d' % (r['n'], r['n_blender'], r['faces'], r['faces_blender'])
    s = 'n %d/%d faces %d/%d max %.2e L mean %.2e%s' % (r['n'], r['n_blender'], r['faces'], r['faces_blender'],
                                                        r['max_L'], r['mean_L'], '' if r['one_to_one'] else ' (not 1:1)')
    if 'index_same' in r:
        s += ' order %d' % r['index_same']
    if 'winding_same' in r:
        s += ' wind %d start %d' % (r['winding_same'], r['start_same'])
    if 'uv_max' in r:
        s += ' uv %.1e/%.1e' % (r['uv_max'], r['uv_mean'])
    return s


def markdown(rep):
    L = ['# evalmesh: %s' % rep.get('build', 'the lab shapes'), '',
         'Ours against a local Blender 5.2.2 on the same input (per vertex, nearest and one to one; faces by vertex set; '
         'UVs per corner), and each against the build\'s bundle where it has the piece.', '',
         '| piece | modifiers | ours vs Blender | Blender (local) vs bundle | ours vs bundle |', '| --- | --- | --- | --- | --- |']
    for r in rep['rows']:
        m = ', '.join('%s%s' % (t, '(%s)' % s.get('levels') if t == 'SUBSURF' else '') for t, s in r['mods'])
        L.append('| %s | %s | %s | %s | %s |' % (r['piece'], m, _fmt(r['ours_blender']),
                                                 _fmt(r['blender_bundle']) if 'blender_bundle' in r else '-',
                                                 _fmt(r['ours_bundle']) if 'ours_bundle' in r else '-'))
    return '\n'.join(L) + '\n'


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return 0
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    if args[0] == 'lab':
        out = opt('--out', os.path.join(ROOT, 'charkit/out/evalmesh/lab'))
        ps = shapes()
        os.makedirs(out, exist_ok=True)
        Bl = blender(ps, work=os.path.join(out, 'blender'))
        rows = [dict(piece=p['name'], mods=p['mods'], ours_blender=compare(ours(p), b, p['L'])) for p, b in zip(ps, Bl)]
        rep = dict(build=None, rows=rows)
        for r in rows:
            print('%-22s %s' % (r['piece'], _fmt(r['ours_blender'])))
        json.dump(rep, open(os.path.join(out, 'evalmesh.json'), 'w'), indent=1, default=str)
        open(os.path.join(out, 'evalmesh.md'), 'w').write(markdown(rep))
        return 0
    if args[0] == 'build':
        build = args[1]
        out = opt('--out', os.path.join(build, 'evalmesh'))
        names = opt('--pieces')
        run_build(build, out, render='--render' in args, names=names.split(',') if names else None)
        print('report', os.path.join(out, 'evalmesh.md'))
        return 0
    if args[0] == 'motion':
        build = args[1]
        names = opt('--pieces')
        motion(build, opt('--out', os.path.join(build, 'motion')), names=names.split(',') if names else None)
        return 0
    print(__doc__); return 1


# ------------------------------------------------------------------------------------------------------------ M4
FINAL_MODS = ('SOLIDIFY', 'SUBSURF')     # what the venv applies at rest (call J); Armature and the outline stay in Blender
# how a final mesh's skin weights go through the subdivision (geom.subsurf carry_rule). 'limit': the positions' own
# refinement and limit stencil (R3a, measured: motion QA at 7 extreme poses against Blender's per-frame modifiers, the
# skirt's kick 0.040 L linear -> 0.019 L, the collar's twist 0.020 -> 0.016; every other piece unchanged at 1e-5 L).
# 'linear' is Blender's own vertex-data rule (what the build shipped at M4).
WEIGHT_RULE = 'limit'


def finalize(o, weight_rule=None):
    """a recorded garment object (charkit.geomstage.pieces) with its Solidify and Subdivision Surface applied at rest,
    venv-side (M4): -> dict(V, polys (m, k) or (loopv, counts), uv_corner [(k, 2)] or None, mat_idx (m,), weights
    {bone: (n,)}, shell (the Solidify's thickness, for the outline's cap) or None, levels). The weights are copied to
    the Solidify's copies and carried through the subdivision by weight_rule (default WEIGHT_RULE: the limit stencil;
    'linear' as Blender carries vertex data)."""
    from .geom import solidify as solid, subsurf
    V = np.asarray(o['V'], float)
    polys = o['polys']
    lv = np.concatenate([np.asarray(f, np.int64) for f in polys]); cnt = np.array([len(f) for f in polys], np.int64)
    nf = len(cnt)
    if o['uv_corner'] is not None:
        luv = np.concatenate([np.asarray(u, float).reshape(-1, 2) for u in o['uv_corner']])
    elif o['uv'] is not None:
        luv = np.asarray(o['uv'], float)[lv]
    else:
        luv = None
    mat = np.asarray(o['mat_idx'], np.int64) if o['mat_idx'] is not None else np.zeros(nf, np.int64)
    from .garments import group_weights                    # (the weights as the coarse object's vertex groups hold them)
    names = sorted(o['weights'])
    W = np.stack([group_weights(o['weights'][b]) for b in names], 1) if names else np.zeros((len(V), 0))
    cre, shell, levels = None, None, 0
    layer = np.zeros(nf, np.int8)                            # per face: 0 the surface, 1 the Solidify's copy, 2 its rim
    for name, m in o['mods'].items():
        st = m['settings']
        if m['type'] == 'SOLIDIFY':
            shell = abs(float(st['thickness']))
            # ink (garments.with_ink's strokes: a slot named *_ink) takes no thickness: set aside, put back after
            ink_slots = [k for k, mm in enumerate(o['materials']) if str(mm.get('name', '')).endswith('_ink')]
            ink = None
            if ink_slots:
                fi = np.isin(mat, ink_slots)
                if fi.any():
                    st_l = np.r_[0, np.cumsum(cnt)[:-1]]
                    corner = np.repeat(fi, cnt)
                    ink = dict(lv=lv[corner], cnt=cnt[fi], mat=mat[fi], uv=luv[corner] if luv is not None else None)
                    lv, cnt, mat = lv[~corner], cnt[~fi], mat[~fi]
                    luv = luv[~corner] if luv is not None else None
            R = solid.solidify(V, (lv, cnt), float(st['thickness']), uv=luv,
                               **{k: v for k, v in st.items() if k != 'thickness' and k in _SOLID_KW})
            nV = len(V)
            V0 = V
            V, lv, cnt, luv = R['V'], R['loopv'], R['counts'], R['uv']
            nf_ = len(mat)
            mat = mat[R['parent']]
            layer = np.r_[np.zeros(nf_, np.int8), np.ones(nf_, np.int8), np.full(len(R['counts']) - 2 * nf_, 2, np.int8)]
            W = np.concatenate([W, W])
            cre = R['creases'] if len(R['creases'][0]) else None
            if ink is not None:
                # the strokes' own vertices (the first copy keeps them in place: offset -1 moves only the second;
                # appended as their own so the copies' are left unused by them)
                used = np.unique(ink['lv'])
                remap = np.full(nV, -1, np.int64); remap[used] = len(V) + np.arange(len(used))
                V = np.r_[V, V0[used]]
                W = np.r_[W, W[used]]
                lv = np.r_[lv, remap[ink['lv']]]
                cnt = np.r_[cnt, ink['cnt']]
                mat = np.r_[mat, ink['mat']]
                layer = np.r_[layer, np.zeros(len(ink['cnt']), np.int8)]
                if luv is not None:
                    luv = np.r_[luv, ink['uv']]
        elif m['type'] == 'SUBSURF':
            levels = int(st.get('levels', 1))
            if int(st.get('render_levels', levels)) != levels:
                raise ValueError('%s: viewport and render levels differ (%s): one final mesh cannot serve both'
                                 % (o['name'], st))
            R = subsurf.subdivide(V, (lv, cnt), levels=levels, creases=cre, uv=luv, carry=W,
                                  carry_rule=weight_rule or WEIGHT_RULE)
            V, lv, cnt = R['V'], R['quads'].ravel(), np.full(len(R['quads']), 4)
            luv = R['uv'].reshape(-1, 2) if R['uv'] is not None else None
            mat = mat[R['parent']]
            layer = layer[R['parent']]
            W = np.clip(R['carry'], 0.0, 1.0)                # (the stencil is non-negative and affine: no-op to 1e-16)
            cre = None
    st_ = np.r_[0, np.cumsum(cnt)[:-1]]
    return dict(name=o['name'], V=V, loopv=lv, counts=cnt, mat_idx=mat, layer=layer,
                uv_corner=[luv[a:a + c] for a, c in zip(st_, cnt)] if luv is not None else None,
                weights={b: W[:, k] for k, b in enumerate(names)}, shell=shell, levels=levels)


_SOLID_KW = ('offset', 'use_rim', 'edge_crease_outer', 'edge_crease_inner', 'edge_crease_rim', 'use_even_offset',
             'use_quality_normals', 'use_flip_normals')


# ------------------------------------------------------------------------------------------------ M4: motion QA
# extreme poses: per bone a rotation in the armature's rest frame (axis, degrees) about its head, composed down the
# chain (Blender frame: +Z up, the character facing -Y, its left arm along +X)
POSES = {
    'arms_up': dict(leftUpperArm=('Y', -80), rightUpperArm=('Y', 80)),
    'elbows_bent': dict(leftUpperArm=('Y', -30), rightUpperArm=('Y', 30), leftLowerArm=('Z', -130),
                        rightLowerArm=('Z', 130)),
    'arms_forward_crossed': dict(leftUpperArm=('Z', -110), rightUpperArm=('Z', 110)),
    'kick': dict(leftUpperLeg=('X', -95), leftLowerLeg=('X', 30), rightLowerLeg=('X', 120)),
    'squat': dict(leftUpperLeg=('X', -100), rightUpperLeg=('X', -100), leftLowerLeg=('X', 130),
                  rightLowerLeg=('X', 130), spine=('X', 25)),
    'twist_bend': dict(spine=('Z', 40), chest=('X', 35), upperChest=('Z', 20), neck=('X', 20)),
    'split': dict(leftUpperLeg=('Y', 70), rightUpperLeg=('Y', -70)),
}


def _groups(ob, names, W, final):
    """vertex groups named by bone: the weights as given (grouped by value in one pass)."""
    for k, b in enumerate(names):
        g = ob.vertex_groups.new(name=b)
        w = np.asarray(W[:, k], float)
        vals, inv = np.unique(w, return_inverse=True)
        order = np.argsort(inv, kind='stable')
        for j, idx in enumerate(np.split(order, np.cumsum(np.bincount(inv, minlength=len(vals)))[:-1])):
            if vals[j] > 0:
                g.add(idx.tolist(), float(vals[j]), 'REPLACE')


def motion_main(inp, out):
    """inside Blender: the character's armature (body.build_armature on the build's joints); per piece the variants
    (Armature first, then their own modifiers), evaluated at rest and at each pose -> out (positions per variant and
    pose)."""
    import bpy
    from mathutils import Matrix
    from charkit import body
    Z = np.load(inp, allow_pickle=False)
    meta = json.loads(str(Z['meta']))
    arm = body.build_armature({k: tuple(v) for k, v in meta['joints'].items()})
    obs = []
    for i, v in enumerate(meta['variants']):
        p = dict(name=v['name'], V=Z['%d/V' % i], loopv=Z['%d/loopv' % i], counts=Z['%d/counts' % i], mods=[])
        ob = _bl_mesh(p)
        _groups(ob, v['bones'], Z['%d/W' % i], v['final'])
        m = ob.modifiers.new('rig', 'ARMATURE'); m.object = arm
        for t, st in v['mods']:
            md = ob.modifiers.new(t.lower(), t)
            for k, x in st.items():
                setattr(md, k, x)
        obs.append(ob)
    res = {}
    for pose in ['rest'] + list(meta['poses']):
        for pb in arm.pose.bones:
            pb.rotation_quaternion = (1, 0, 0, 0)
        for b, (ax, deg) in (meta['poses'].get(pose) or {}).items():
            if b not in arm.pose.bones:
                continue
            Bm = arm.data.bones[b].matrix_local.to_3x3()
            R = Matrix.Rotation(np.radians(deg), 3, ax)
            arm.pose.bones[b].rotation_quaternion = (Bm.transposed() @ R @ Bm).to_quaternion()
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        for i, ob in enumerate(obs):
            oe = ob.evaluated_get(dg)
            me = oe.to_mesh()
            co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co)
            res['%s/%d' % (pose, i)] = co.reshape(-1, 3)
            oe.to_mesh_clear()
    np.savez(out, **res)


def motion(build, out, names=None, poses=None, log=print):
    """motion QA (call J, M4's exit): each garment at extreme poses, three ways, in a local Blender with the build's
    armature: 'blender' the coarse mesh with Blender's per-frame stack (Armature, then its Solidify and Subsurf, as the
    build had them); 'linear' the venv's final mesh at rest with the Armature alone and the weights carried linearly
    (Blender's vertex-data rule, the game-engine way); 'stencil' the same with the weights through the positions' limit
    stencil (WEIGHT_RULE since R3a). Per piece and pose, each final variant's distance from 'blender' per vertex (the
    correspondence matched at rest, one to one); which candidate the build shipped (its final weights equal to 1e-6;
    'either' where the two agree, as on a piece bound to one bone);
    and each candidate's weight health as the VRM takes it (weight_stats). -> the report dict (out/motion.json,
    out/motion.md)."""
    import tempfile
    from . import bundle as bundlelib, geomstage
    from .garments import group_weights
    poses = poses or POSES
    B = bundlelib.load(os.path.join(build, 'bundle'))
    L = float(B.meta('assembly')['L'])
    joints = B._meta['landmarks']['joints']
    P = geomstage.load(os.path.join(build, 'geom', 'garments.npz'))
    if P['meta'].get('coarse_events') is None:
        P = geomstage.finalize(P)
    coarse, final = geomstage.pieces(P, coarse=True)[0], geomstage.pieces(P)[0]
    variants, arrays, rows = [], {}, []
    for c, f in zip(coarse, final):
        if names and c['name'] not in names or not c['mods']:
            continue
        bones = sorted(b for b in c['weights'])
        Wc = np.stack([group_weights(c['weights'][b]) for b in bones], 1)
        lv = np.concatenate([np.asarray(x, np.int64) for x in c['polys']]); cnt = np.array([len(x) for x in c['polys']])
        mods = [(m['type'], {k: v for k, v in m['settings'].items() if k not in SKIP_SETTINGS and k != 'render_levels'})
                for m in c['mods'].values()]
        # the two candidates, each through finalize (the same Solidify and Subsurf the build ran): linear (Blender's
        # vertex-data rule) and stencil (the positions' limit stencil); which the build shipped is read off its weights
        cand = {k: finalize(c, weight_rule=r) for k, r in (('linear', 'linear'), ('stencil', 'limit'))}
        Wk = {k: np.stack([np.asarray(F['weights'][b], float) for b in bones], 1) for k, F in cand.items()}
        Wf = np.stack([np.asarray(f['weights'][b], float) for b in bones], 1)
        dw = {k: float(np.abs(W_ - Wf).max()) if W_.shape == Wf.shape and W_.size else 0.0 for k, W_ in Wk.items()}
        ships = 'either' if max(dw.values()) < 1e-6 else min(dw, key=dw.get) if min(dw.values()) < 1e-6 else None
        flv = np.concatenate([np.asarray(x, np.int64) for x in f['polys']]); fcnt = np.array([len(x) for x in f['polys']])
        wstat = {k: weight_stats(W_) for k, W_ in Wk.items()}
        base = len(variants)
        for kind, V_, lv_, cnt_, W_, md in (('blender', c['V'], lv, cnt, Wc, mods),
                                            ('linear', f['V'], flv, fcnt, Wk['linear'], []),
                                            ('stencil', f['V'], flv, fcnt, Wk['stencil'], [])):
            i = len(variants)
            variants.append(dict(name='%s:%s' % (c['name'], kind), bones=bones, mods=md, final=kind != 'blender'))
            arrays.update({'%d/V' % i: np.asarray(V_, float), '%d/loopv' % i: lv_, '%d/counts' % i: cnt_,
                           '%d/W' % i: W_})
        rows.append(dict(piece=c['name'], base=base, ships=ships, weights=wstat))
    work = tempfile.mkdtemp(prefix='evalmesh_motion_')
    inp, res = os.path.join(work, 'in.npz'), os.path.join(work, 'out.npz')
    np.savez(inp, meta=np.array(json.dumps(dict(joints=joints, variants=variants, poses=poses))), **arrays)
    expr = 'import sys; sys.path.insert(0, %r); from charkit import evalmesh; evalmesh.motion_main(%r, %r)' % (
        ROOT, inp, res)
    t = time.time()
    r = subprocess.run([BLENDER, '-b', '--factory-startup', '--python-exit-code', '1', '--python-expr', expr],
                       capture_output=True, text=True)
    if r.returncode or not os.path.exists(res):
        raise RuntimeError('evalmesh motion: Blender failed (%d):\n%s' % (r.returncode, (r.stdout + r.stderr)[-3000:]))
    log('evalmesh motion: Blender posed %d variants at %d poses in %.1f s' % (len(variants), len(poses) + 1,
                                                                             time.time() - t))
    Z = np.load(res)
    out_rows = []
    for row in rows:
        b = row['base']
        Vb0 = Z['rest/%d' % b]
        rr = dict(piece=row['piece'], n=int(len(Vb0)), poses={}, ships=row['ships'], weights=row['weights'])
        for j, kind in ((1, 'linear'), (2, 'stencil')):
            idx, d0, bij = match(Z['rest/%d' % (b + j)], Vb0)
            rr['rest_%s' % kind] = dict(one_to_one=bool(bij), max_L=float(d0.max() / L))
            for pose in poses:                              # (idx: Blender's vertex -> the final mesh's)
                Pb = Z['%s/%d' % (pose, b)]
                d = np.linalg.norm(Z['%s/%d' % (pose, b + j)][idx] - Pb, axis=1) / L
                rr['poses'].setdefault(pose, {})[kind] = dict(max_L=float(d.max()), p99_L=float(np.percentile(d, 99)),
                                                              mean_L=float(d.mean()))
                rr['poses'][pose]['moved_L'] = float(np.linalg.norm(Pb - Vb0, axis=1).max() / L)
        out_rows.append(rr)
    rep = dict(build=build, L=L, poses=poses, rows=out_rows)
    os.makedirs(out, exist_ok=True)
    json.dump(rep, open(os.path.join(out, 'motion.json'), 'w'), indent=1)
    open(os.path.join(out, 'motion.md'), 'w').write(motion_markdown(rep))
    log('report %s' % os.path.join(out, 'motion.md'))
    return rep


def weight_stats(W, slots=4):
    """a final mesh's skin weights (n, bones) as the VRM writer takes them (gltf: the top `slots`, renormalised):
    the most bones on a vertex, vertices over the slots, the largest share the slots drop, the largest |sum - 1| as
    carried, the smallest weight."""
    W = np.asarray(W, float)
    if not W.size:
        return dict(max_influences=0, over_slots=0, dropped=0.0, sum_dev=0.0, min=0.0)
    nz = (W > 0).sum(1)
    s = W.sum(1)
    top = -np.sort(-W / np.maximum(s[:, None], 1e-12), 1)[:, :slots].sum(1)
    return dict(max_influences=int(nz.max()), over_slots=int((nz > slots).sum()), dropped=float(np.max(1 - top)),
                sum_dev=float(np.abs(s - 1).max()), min=float(W.min()))


def motion_markdown(rep):
    L = ['# motion QA: the final meshes against Blender\'s per-frame modifiers', '',
         'Build `%s`. Per garment and extreme pose, the distance per vertex (head lengths L) of the venv\'s final mesh '
         'posed by the Armature alone from the coarse mesh posed with Blender\'s per-frame stack (Armature, Solidify, '
         'Subsurf). moved: how far the pose moved the piece (max, Blender\'s); linear: the weights carried linearly '
         '(what ships); stencil: carried by the limit stencil; each max / p99 / mean.' % rep['build'], '']
    poses = list(rep['poses'])
    L.append('| piece | rest (linear, stencil) | ' + ' | '.join(poses) + ' |')
    L.append('|---|---|' + '---|' * len(poses))
    f = lambda r: '%.2g / %.2g / %.2g' % (r['max_L'], r['p99_L'], r['mean_L'])
    for r in rep['rows']:
        cells = ['moved %.2g<br>lin %s<br>st %s' % (r['poses'][p]['moved_L'], f(r['poses'][p]['linear']),
                                                     f(r['poses'][p]['stencil'])) for p in poses]
        L.append('| %s | %.1e, %.1e | %s |' % (r['piece'], r['rest_linear']['max_L'], r['rest_stencil']['max_L'],
                                              ' | '.join(cells)))
    worst = {k: max(r['poses'][p][k]['max_L'] for r in rep['rows'] for p in poses) for k in ('linear', 'stencil')}
    L += ['', 'Worst max over pieces and poses: linear %.3g L, stencil %.3g L.' % (worst['linear'], worst['stencil'])]
    ships = sorted({str(r.get('ships')) for r in rep['rows']})
    L += ['', 'The build ships: %s.' % ', '.join(ships), '',
          '## Skin weights as the VRM takes them (top 4, renormalised)', '',
          '| piece | ships | linear: most bones, over 4, dropped, max abs(sum - 1) | stencil: the same |', '|---|---|---|---|']
    g = lambda w: '%d, %d, %.2g, %.1e' % (w['max_influences'], w['over_slots'], w['dropped'], w['sum_dev'])
    for r in rep['rows']:
        if 'weights' in r:
            L.append('| %s | %s | %s | %s |' % (r['piece'], r.get('ships'), g(r['weights']['linear']),
                                               g(r['weights']['stencil'])))
    return '\n'.join(L) + '\n'
