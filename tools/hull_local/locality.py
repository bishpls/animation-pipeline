"""Does a face-only edit stay local in the hull? (tool/hull-local; docs/workstreams/hull-local.md.) The hull is built
twice with this worktree's hull code, the only difference the authored head's sections its face carve reads
(dump_sections.py from two trees: the integration head and a face branch), each stage kept; then every stage is
compared where the edit is and away from it:

    voxels      the carved occupancy (hull.carve_face): which voxels differ, where
    surface     marching cubes before decimation: the vertices in one mesh and not the other (bit-exact positions)
    decimated   hull.ply: vertices not bit-identical, and each vertex's distance to the other mesh's surface, by region
    pieces      hull_pieces.npy / hull_labels.npy on the vertices both meshes share

Regions: by distance from the nearest changed voxel (the edit), and by part of the figure away from it (the head's back
and crown, the neck, the torso, the legs). A local hull leaves everything beyond the edit's reach bit-identical.

    python tools/hull_local/locality.py OUT_DIR SECTIONS_A.npz SECTIONS_B.npz [--faces N] [--reuse] [--decimate-only]

--reuse: the stages already in OUT_DIR/{a,b}/stages.npz (compare only). --decimate-only: rebuild only the decimation
from the kept surfaces (a quick test of a decimation change). -> OUT_DIR/locality.json."""
import contextlib, io, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import numpy as np

KEEP = ('rounded', 'face_carved', 'surface', 'decimated', 'vertex_classes', 'vertex_pieces', 'axes')
BANDS = (0.0, 0.03, 0.06, 0.1, 0.2, 0.4, 1.0, np.inf)      # L from the edit
EDIT_REACH = 0.06                                           # L: what the edit may move (its voxels, blurred, meshed)


def sections(p):
    from charkit.geom.headgeom import Sections
    z = np.load(p)
    return Sections(z['zs'], z['cy'], z['r']), str(z['head'])


def build(spec, sec, out, faces):
    """hull.build with code_base.head_sections returning `sec` -> (report, {stage: arrays})."""
    from charkit import code_base
    from charkit.geom import hull
    orig = code_base.head_sections
    code_base.head_sections = lambda s, log=print: (sec, {}, {})
    st = []
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            rep = hull.build(spec, out, faces=faces, validate_views=False, page=False, stages=st,
                             log=lambda *a: None)
    finally:
        code_base.head_sections = orig
    S = {}
    for n, arr in st:
        if n in KEEP:
            S.update({'%s.%s' % (n, k): v for k, v in arr.items()})
    np.savez(os.path.join(out, 'stages.npz'), **S)
    return rep, S


def _key(V):
    """exact positions as hashable rows."""
    V = np.ascontiguousarray(np.asarray(V, np.float64))
    return V.view(np.dtype((np.void, V.dtype.itemsize * 3))).ravel()


def _only(VA, VB):
    """per vertex of A: its exact position absent from B."""
    return ~np.isin(_key(VA), _key(VB))


def region_of(P, d_edit, zs_head):
    """a part of the figure per point (away from the edit): 'edit' within EDIT_REACH of it, else the head's back and
    crown (above the chin), the neck, the torso, the legs (hull frame: L, eye line z 0)."""
    chin, neck, hips = zs_head
    z = P[:, 2]
    r = np.where(z >= chin, 'head', np.where(z >= neck, 'neck', np.where(z >= hips, 'torso', 'legs'))).astype(object)
    r[(z >= 0.2) & (r == 'head')] = 'crown'
    r[d_edit < EDIT_REACH] = 'edit'
    return r


def compare(A, B, fig_z):
    from scipy.spatial import cKDTree
    from charkit.geom.bvh import BVH
    from charkit.geom.mesh import Mesh
    R = {}
    xs, ys, zs = A['axes.xs'], A['axes.ys'], A['axes.zs']
    va, vb = A['face_carved.V'], B['face_carved.V']
    dv = np.argwhere(va != vb)
    R['rounded_identical'] = bool(np.array_equal(A['rounded.V'], B['rounded.V']))
    E = np.stack([xs[dv[:, 0]], ys[dv[:, 1]], zs[dv[:, 2]]], 1) if len(dv) else np.zeros((0, 3))
    R['voxels'] = dict(changed=int(len(dv)), removed_in_b=int((va & ~vb).sum()), added_in_b=int((~va & vb).sum()),
                       box=[E.min(0).round(3).tolist(), E.max(0).round(3).tolist()] if len(E) else None)
    tE = cKDTree(E) if len(E) else None
    dist_edit = (lambda P: tE.query(P)[0]) if tE is not None else (lambda P: np.full(len(P), np.inf))
    # the surface before decimation
    sa, sb = A['surface.V'], B['surface.V']
    oa, ob = _only(sa, sb), _only(sb, sa)
    d = np.concatenate([dist_edit(sa[oa]), dist_edit(sb[ob])])
    R['surface'] = dict(vertices=[len(sa), len(sb)], faces=[len(A['surface.F']), len(B['surface.F'])],
                        only_a=int(oa.sum()), only_b=int(ob.sum()),
                        farthest_from_edit=round(float(d.max()), 4) if len(d) else None,
                        beyond_reach=int((d >= EDIT_REACH).sum()))
    # the decimated mesh
    ma, mb = Mesh(A['decimated.V'], A['decimated.F']), Mesh(B['decimated.V'], B['decimated.F'])
    oa, ob = _only(ma.V, mb.V), _only(mb.V, ma.V)
    # each vertex's distance to the other mesh's surface (both ways)
    da = BVH(mb).nearest(ma.V)[0]
    db = BVH(ma).nearest(mb.V)[0]
    ea, eb = dist_edit(ma.V), dist_edit(mb.V)
    rga, rgb = region_of(ma.V, ea, fig_z), region_of(mb.V, eb, fig_z)
    dec = dict(vertices=[len(ma.V), len(mb.V)], faces=[len(ma.F), len(mb.F)], only_a=int(oa.sum()),
               only_b=int(ob.sum()), bands={}, regions={})
    for lo, hi in zip(BANDS[:-1], BANDS[1:]):
        sa_, sb_ = (ea >= lo) & (ea < hi), (eb >= lo) & (eb < hi)
        dd = np.concatenate([da[sa_], db[sb_]])
        dec['bands']['%g-%g' % (lo, hi)] = dict(
            n=int(sa_.sum() + sb_.sum()), moved=int(oa[sa_].sum() + ob[sb_].sum()),
            max_L=float('%.3g' % dd.max()) if len(dd) else 0.0,
            p99_L=float('%.3g' % np.percentile(dd, 99)) if len(dd) else 0.0)
    for g in ('edit', 'head', 'crown', 'neck', 'torso', 'legs'):
        sa_, sb_ = rga == g, rgb == g
        dd = np.concatenate([da[sa_], db[sb_]])
        dec['regions'][g] = dict(n=int(sa_.sum() + sb_.sum()), moved=int(oa[sa_].sum() + ob[sb_].sum()),
                                 max_L=float('%.3g' % dd.max()) if len(dd) else 0.0,
                                 over_1e6=int((dd > 1e-6).sum()))
    away = np.concatenate([da[rga != 'edit'], db[rgb != 'edit']])
    dec['away_from_edit'] = dict(n=int(len(away)), not_identical=int(oa[rga != 'edit'].sum() + ob[rgb != 'edit'].sum()),
                                 max_L=float('%.3g' % away.max()) if len(away) else 0.0,
                                 over_1e6=int((away > 1e-6).sum()))
    R['decimated'] = dec
    # the per-vertex labels where the two meshes share a vertex
    _, i, j = np.intersect1d(_key(ma.V), _key(mb.V), return_indices=True)
    if len(i) and 'vertex_classes.labels' in A and 'vertex_classes.labels' in B:
        R['labels'] = dict(shared=int(len(i)),
                           classes_differ=int((A['vertex_classes.labels'][i] != B['vertex_classes.labels'][j]).sum()),
                           pieces_differ=int((A['vertex_pieces.pieces'][i] != B['vertex_pieces.pieces'][j]).sum())
                           if 'vertex_pieces.pieces' in A else None)
    return R


def decimate_again(S, faces):
    """the decimation stage alone from a kept surface (charkit.geom.hull's call), for a quick test of a change to it."""
    from charkit.geom import hull, remesh
    from charkit.geom.mesh import Mesh
    m = Mesh(S['surface.V'], S['surface.F'], vc=S['surface.vc'] if len(S['surface.vc']) else None)
    fn = getattr(hull, 'decimate_hull', None)
    t = time.time()
    m = fn(m, faces) if fn else remesh.decimate(m, faces or 150000)
    S = {k: v for k, v in S.items() if not k.startswith(('vertex_classes.', 'vertex_pieces.'))}   # (stale now)
    S['decimated.V'], S['decimated.F'] = m.V, m.F
    return S, round(time.time() - t, 1)


def main(a):
    out, pa, pb = a[:3]
    faces = int(a[a.index('--faces') + 1]) if '--faces' in a else None     # None: the hull's own rule
    os.makedirs(out, exist_ok=True)
    from charkit import bodyeval
    spec = bodyeval.resolve('charkit/spec/clawd.json')
    spec.pop('head_code', None)
    res = {'faces': faces, 'code': os.popen('git -C %s rev-parse --short HEAD' % ROOT).read().strip()}
    S = {}
    for tag, p in (('a', pa), ('b', pb)):
        sec, head = sections(p)
        res['head_' + tag] = head
        d = os.path.join(out, tag)
        os.makedirs(d, exist_ok=True)
        if '--reuse' in a or '--decimate-only' in a:
            S[tag] = dict(np.load(os.path.join(d, 'stages.npz'), allow_pickle=False))
            if '--decimate-only' in a:
                S[tag], res['decimate_s_' + tag] = decimate_again(S[tag], faces)
        else:
            t = time.time()
            _, S[tag] = build(spec, sec, d, faces)
            res['build_s_' + tag] = round(time.time() - t, 1)
            print('built %s (%s) in %.0f s' % (tag, head, time.time() - t), flush=True)
    # the figure's heights (L, the eye frame): the chin from the head's sections, the neck and hips from the body's
    zs = sections(pa)[0].zs
    fig = (float(zs.min()), float(zs.min()) - 0.35, -3.2)
    res['figure_z'] = dict(chin=fig[0], neck=fig[1], hips=fig[2])
    res.update(compare(S['a'], S['b'], fig))
    json.dump(res, open(os.path.join(out, 'locality.json'), 'w'), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main(sys.argv[1:])
