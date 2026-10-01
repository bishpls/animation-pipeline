"""face round 5: why the collar moved with the jaw. The collar (garments.collar_hull) rebuilt venv-side on every
combination of the two builds' head (head_code.npz), body fit (body_code.npz) and hull (the produced hull's folder:
hull.glb, its sidecar, hull.npz), against each build's recorded collar (geom/garments.npz); then, with the head and hull
held, the collar's stages on the two body fits (the neck bone, the neckline, the walks' starts and ends, the conform).

    python collar_trace.py OUT_DIR BEFORE_BUILD AFTER_BUILD BEFORE_HULL_DIR AFTER_HULL_DIR

BUILD: a build's folder (its clawd.spec.json and geom/); HULL_DIR: a produced hull's files (the shared produced cache's
entry for each tree's hull stamp). -> OUT_DIR/collar_trace.json."""
import contextlib, io, json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
import numpy as np
from charkit import garments, geomstage, scene
from charkit.geom.parts import load_generated


def spec_for(builds, hulls, head, body, hull):
    """the garments step's spec (fit_cranium applied, as cli.garments_geom keys it) with the chosen inputs."""
    here = lambda v: os.path.join(ROOT, 'charkit', 'out', v.split('/charkit/out/', 1)[1]) \
        if isinstance(v, str) and '/charkit/out/' in v and not os.path.exists(v) else v   # (a box build's paths)
    remap = lambda o: {k: remap(v) for k, v in o.items()} if isinstance(o, dict) else \
        [remap(v) for v in o] if isinstance(o, list) else here(o)
    s = remap(json.load(open(os.path.join(builds['after'], 'clawd.spec.json'))))
    s['head_code'] = os.path.join(builds[head], 'geom', 'head_code.npz')
    s['body_code'] = os.path.join(builds[body], 'geom', 'body_code.npz')
    s['hair']['shape']['glb'] = os.path.join(hulls[hull], 'hull.glb')
    s.pop('garments_geom', None)
    with contextlib.redirect_stdout(io.StringIO()):
        return scene.fit_cranium(s, ROOT, load=lambda p: load_generated(p, compat=True))


def build_collar(s, walks=None):
    with contextlib.redirect_stdout(io.StringIO()):
        A = geomstage.assemble(s, keep=False)
    H = garments.hull_pieces(s, A)
    cs = next(g for g in s['garments'] if g['name'] == 'collar')
    nrm = garments.vertex_normals(A['verts'], A['faces'])
    orig = garments.surface_walk
    if walks is not None:
        def rec(*a, **k):
            P = orig(*a, **k)
            walks.append(P)
            return P
        garments.surface_walk = rec
    try:
        G = garments.collar_hull(A, cs, nrm, H)
    finally:
        garments.surface_walk = orig
    return np.asarray(G['verts'], float), A, H, cs


def recorded(build):
    P = geomstage.load(os.path.join(build, 'geom', 'garments.npz'))
    e = next(e for e in P['meta']['events'] if e[0] == 'call' and e[2] == '_object' and e[3][0] == 'collar')
    return np.asarray(P['arrays'][e[3][1]['$a']], float)


def main(out, before, after, hull_before, hull_after):
    os.makedirs(out, exist_ok=True)
    builds, hulls = dict(before=before, after=after), dict(before=hull_before, after=hull_after)
    rec = {b: recorded(builds[b]) for b in builds}
    res = dict(factorial=[])
    L = None
    for head, body, hull in [('before',) * 3, ('after',) * 3, ('after', 'after', 'before'), ('before', 'before', 'after'),
                             ('after', 'before', 'after'), ('after', 'before', 'before')]:
        V, A, _, _ = build_collar(spec_for(builds, hulls, head, body, hull))
        L = A['head']['L']
        d = {b: float(np.linalg.norm(V - rec[b], axis=1).max() / L) for b in rec}
        res['factorial'].append(dict(head=head, body=body, hull=hull, vs_recorded_before=round(d['before'], 5),
                                     vs_recorded_after=round(d['after'], 5)))
        print('head %-6s body %-6s hull %-6s  vs recorded before %.5f L, after %.5f L' % (
            head, body, hull, d['before'], d['after']))
    # the stages, head and hull held (after's), the body fit swapped
    st = {}
    for body in ('before', 'after'):
        walks = []
        V, A, H, cs = build_collar(spec_for(builds, hulls, 'after', body, 'after'), walks)
        nb, _ = garments.bone_seg(A, 'neck')
        from charkit.geom import loft
        top = garments.hull_edge(garments._hull_points(H, cs), loft.Axis((nb[0], nb[1], 0.0), (0, 0, -1), (0, -1, 0)),
                                 n=cs.get('neck_sectors', 36), q=cs.get('neck_q', 3.0), low=False,
                                 smooth=cs.get('neck_smooth', 1.5), min_pts=cs.get('neck_min_pts', 10))
        st[body] = dict(V=V, nb=nb, walks=np.array(walks), body=np.asarray(A['verts'], float),
                        top=np.array([top(a) for a in np.linspace(-math.pi, math.pi, 97)]))
    a, b = st['before'], st['after']
    band = (a['body'][:, 2] > a['V'][:, 2].min() - 0.05 * L) & (a['body'][:, 2] < a['V'][:, 2].max() + 0.05 * L)
    bd = np.linalg.norm(b['body'] - a['body'], axis=1)[band] / L
    wd = np.linalg.norm(b['walks'] - a['walks'], axis=2) / L
    vd = np.linalg.norm(b['V'] - a['V'], axis=1) / L
    res['stages'] = dict(
        body_under_collar=dict(max=round(float(bd.max()), 5), median=round(float(np.median(bd)), 6), n=int(band.sum())),
        neck_bone=round(float(np.linalg.norm(b['nb'] - a['nb']) / L), 6),
        neckline=round(float(np.abs(b['top'] - a['top']).max() / L), 6),
        walk_starts=round(float(wd[:, 0].max()), 6), walk_ends=round(float(wd[:, -1].max()), 5),
        walk_ends_over_0005=int((wd[:, -1] > 0.005).sum()),
        collar=round(float(vd.max()), 5), collar_over_0005=int((vd > 0.005).sum()), L_m=round(float(L), 5))
    print(json.dumps(res['stages'], indent=1))
    json.dump(res, open(os.path.join(out, 'collar_trace.json'), 'w'), indent=1)
    return res


if __name__ == '__main__':
    main(*sys.argv[1:6])
