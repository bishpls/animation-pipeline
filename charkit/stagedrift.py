"""Per-stage drift between the numpy evaluator (charkit.bodyeval) and a build (its bundle): where the two compute the same
geometry, how far apart they land, stage by stage (docs/GEOM_TRUTH.md). A stand-in until tool/infra's `charkit evaldrift`
lands; fold it in there then.

    python -m charkit.stagedrift BUILD [--out DIR] [--no-checks]

The evaluator is given the spec the build's scene was made from (the bundle's, after its cranium fit), so each stage's
row measures that stage's own computation, not a resolve that differs upstream. Per stage:
  fit_cranium   the cranium knob: the build's (Blender, i3d.load_glb) against scene.fit_cranium with the venv's GLB reader
  character     the assembly (the skin's `assembly` variant, float64 as character.assemble made it), the eye and mouth
                parts (their `eval` variant: Blender's float32), the landmarks; the skin's evaluated mesh (subdivision
                level 1) against bodyeval's numpy subdivision
  hair          each hair object's raw mesh against the evaluator's object of the same name
  accessories   likewise
  garments      each garment's raw mesh (float32 as Blender holds it) against the evaluator's piece, and its evaluated
                mesh (Solidify, then Subdivision Surface) against bodyeval's numpy ones (nearest vertex, both ways); the
                skin mask (the vertices the garments hide)
  checks        the body_*, palette_* and sheet_* checks the evaluator measures against the build's qa.json
Distances in L (head lengths) and metres. `f32` counts vertices equal once both are rounded to float32 (as Blender keeps
them): all of them is exact. -> BUILD/stagedrift/drift.json and drift.md.
"""
import json, os, sys, time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _local(x, root):
    """a spec with paths under another copy's root (the box's) re-rooted here: every string with '/charkit/' in it that
    doesn't exist as given."""
    if isinstance(x, dict):
        return {k: _local(v, root) for k, v in x.items()}
    if isinstance(x, list):
        return [_local(v, root) for v in x]
    if isinstance(x, str) and os.path.isabs(x) and not os.path.exists(x) and '/charkit/' in x:
        return os.path.join(root, 'charkit', x.split('/charkit/', 1)[1])
    return x


def _f32(a):
    return np.asarray(a, float).astype(np.float32)


def pair(ours, theirs, L):
    """two vertex arrays of one object: -> dict(n, max_L, mean_L, f32 (vertices equal in float32), exact (all equal in
    float64)) when the counts agree, else the counts and the symmetric nearest-vertex distance (Hausdorff)."""
    a, b = np.asarray(ours, float), np.asarray(theirs, float)
    r = dict(n=int(len(a)), n_build=int(len(b)))
    if not len(a) or not len(b):
        return r
    if len(a) == len(b):
        d = np.linalg.norm(a - b, axis=1)
        r.update(max_L=float(d.max() / L), mean_L=float(d.mean() / L), max_m=float(d.max()),
                 f32=int((_f32(a) == _f32(b)).all(1).sum()), exact=bool((a == b).all()))
    else:
        from scipy.spatial import cKDTree
        d1 = cKDTree(b).query(a)[0]; d2 = cKDTree(a).query(b)[0]
        r.update(hausdorff_L=float(max(d1.max(), d2.max()) / L), mean_nn_L=float(0.5 * (d1.mean() + d2.mean()) / L))
    return r


def nearest(ours, theirs, L):
    """evaluated meshes (vertex orders differ): the symmetric nearest-vertex distance -> dict."""
    from scipy.spatial import cKDTree
    a, b = np.asarray(ours, float), np.asarray(theirs, float)
    if not len(a) or not len(b):
        return dict(n=int(len(a)), n_build=int(len(b)))
    d1 = cKDTree(b).query(a)[0]; d2 = cKDTree(a).query(b)[0]
    return dict(n=int(len(a)), n_build=int(len(b)), hausdorff_L=float(max(d1.max(), d2.max()) / L),
                p99_L=float(np.percentile(np.r_[d1, d2], 99) / L), mean_nn_L=float(0.5 * (d1.mean() + d2.mean()) / L))


def _sil_iou(parts_a, parts_b, az, frame):
    from .bodymeasure import iou
    from .geom.mesh import Mesh
    from .geom.raster import silhouette
    m = lambda ps: [Mesh(np.asarray(V, float), np.asarray(T)) for V, T in ps if len(T)]
    ma, mb = m(parts_a), m(parts_b)
    sa = np.any([silhouette(x, az, frame) for x in ma], 0) if ma else None
    sb = np.any([silhouette(x, az, frame) for x in mb], 0) if mb else None
    if sa is None or sb is None:
        return None
    return round(float(iou(sa, sb)), 4)


def measure(build, checks=True, log=print):
    """-> the drift report (see the module)."""
    from . import bodyeval, bundle as bundlelib, garments as gm, scene
    from .geom.parts import load_generated
    t0 = time.time()
    B = bundlelib.load(os.path.join(build, 'bundle'))
    spec = _local(dict(B.spec), ROOT)
    rep = dict(build=os.path.abspath(build), spec=spec.get('name'), where=os.uname().nodename.split('.')[0],
               stages={}, notes=[])
    # ---- fit_cranium: the build's resolved spec before Blender (NAME.spec.json) through the venv's GLB reader
    sp = next((os.path.join(build, f) for f in sorted(os.listdir(build)) if f.endswith('.spec.json')), None)
    if sp:
        pre = _local(json.load(open(sp)), ROOT)
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            ev = scene.fit_cranium(json.loads(json.dumps(pre)), ROOT, load=lambda p: load_generated(p, compat=True))
        a, b = (ev.get('head') or {}).get('cranium'), (spec.get('head') or {}).get('cranium')
        rep['stages']['fit_cranium'] = dict(evaluator=a, build=b, d=None if a is None or b is None else abs(a - b),
                                            spec_set='cranium' in (pre.get('head') or {}))
    # ---- the evaluator on the build's own spec
    E = bodyeval.Evaluator(spec)
    t = time.time()
    G = E.geometry()
    rep['evaluator_s'] = round(time.time() - t, 1)
    A = G.A
    L = float(A['head']['L'])
    ours = {p.name: p for p in G.parts if getattr(p, 'role', None) != 'unmasked'}
    skin = B.skin()
    # ---- character
    ch = dict(assembly=pair(A['verts'], skin.V('assembly'), L))
    parts = {}
    for o in B.objects(groups=('eye', 'mouth'), visible=False):
        p = ours.get(o.name)
        parts[o.name] = pair(p.V, o.V('eval'), L) if p is not None else 'build only'
    ch['parts'] = parts
    lm_b = dict(B._meta.get('landmarks') or {})
    asm = dict(B._meta.get('assembly') or {})
    lm = {}
    for k, v in (('waist', asm.get('waist_z')), ('knee', asm.get('knee_z')), ('chin', lm_b.get('chin_z')),
                 ('L', lm_b.get('L'))):
        if v is not None:
            lm[k] = abs(float(G.landmarks[k]) - float(v)) / L
    Jb = lm_b.get('joints') or {}
    dj = [np.abs(np.asarray(A['joints'][k], float) - np.asarray(v, float)).max() for k, v in Jb.items() if k in A['joints']]
    if dj:
        lm['joints'] = float(max(dj)) / L                    # (the trace rounds joints to 1e-4 m)
    ch['landmarks_L'] = lm
    sk = ours.get(skin.name)
    if sk is not None and skin.has('masked'):                   # (ours: the skin with the garments' mask, as 'masked')
        V1, polys = sk.subdivided(1)[:2]
        used = np.unique(np.concatenate([np.asarray(q).ravel() for q in polys]))   # (the mask drops the rest)
        ch['skin_eval_subdiv1'] = nearest(V1[used], skin.V('masked'), L)
    rep['stages']['character'] = ch
    # ---- the generated shape the QA measures against (the hair stage aligns it by its eyes)
    T = B.target()
    if T is not None and G.target is not None:
        rep['stages'].setdefault('hair', {})
        rep['target'] = pair(np.asarray(G.target[0], float), T[0], L)
    # ---- hair and accessories
    for grp, bg in (('hair', 'hair'), ('accessories', 'accessory')):
        rows = {}
        bobj = [o for o in B.objects(groups=(bg,), visible=False) if not o.name.endswith('_normals')]
        for o in bobj:
            p = ours.get(o.name)
            var = 'raw' if o.has('raw') else 'eval'
            rows[o.name] = pair(p.V, o.V(var), L) if p is not None else 'build only'
        for n, p in ours.items():
            if p.group == grp and n not in rows:
                rows[n] = 'evaluator only'
        st = dict(objects=rows)
        if grp == 'hair' and rep.get('target'):
            st['target'] = rep.pop('target')
        if bobj:
            from .geom.raster import Frame
            Vb = np.concatenate([o.V('eval') for o in bobj])
            fr = Frame((0.0, 0.0, float(Vb[:, 2].mean())), float(np.ptp(Vb[:, 2])) * 1.3 + 1e-3, (400, 400))
            pa = [(p.V, p.tris()) for p in ours.values() if p.group == grp]
            pb = [(o.V('eval'), o.tris('eval')[0]) for o in bobj]
            st['silhouette_iou'] = {az: _sil_iou(pa, pb, az, fr) for az in (0, 90, 180)}
        rep['stages'][grp] = st
    # ---- garments
    gs = {}
    for o in B.objects(groups=('garment',), visible=False):
        p = ours.get(o.name)
        if p is None:
            gs[o.name] = 'build only'
            continue
        r = dict(raw=pair(p.V, o.V('raw'), L))
        r['eval'] = nearest(p.subdivided(1)[0], o.V('eval'), L)
        gs[o.name] = r
    hide = bodyeval.garment_parts(A, spec.get('garments'), None, None, (
        gm.hull_pieces(spec, A) if any(g.get('source') == 'hull' for g in spec.get('garments') or []) else None),
        spec)[1]
    hb = B.array('skin/under_garments') if B.has('skin/under_garments') else None
    rep['stages']['garments'] = dict(objects=gs, mask=None if hb is None else dict(
        evaluator=int(hide.sum()), build=int(np.asarray(hb).sum()), differ=int((hide != np.asarray(hb, bool)).sum())))
    # ---- checks
    if checks:
        qa = json.load(open(os.path.join(build, 'qa', 'qa.json')))['checks']
        C = E.sheet_checks(G)
        C.update(E.face_checks(G))
        rows = {}
        for k, v in C.items():
            if k not in qa:
                continue
            bv, bs = qa[k].get('value'), qa[k].get('status')
            nv, ns = v.get('value'), v.get('status')
            d = abs(bv - nv) if isinstance(bv, (int, float)) and isinstance(nv, (int, float)) else None
            rows[k] = dict(build=[bv, bs], evaluator=[nv, ns], d=d)
        rep['checks'] = rows
    rep['seconds'] = round(time.time() - t0, 1)
    return rep


def _fmt(r):
    if not isinstance(r, dict):
        return str(r)
    if 'max_L' in r:
        s = 'max %.3g L (mean %.2g)' % (r['max_L'], r['mean_L'])
        s += ', exact' if r['exact'] else ', f32 %d/%d' % (r['f32'], r['n'])
        return s
    if 'hausdorff_L' in r:
        return 'n %d/%d, hausdorff %.3g L, mean %.2g' % (r['n'], r['n_build'], r['hausdorff_L'], r['mean_nn_L'])
    return 'n %s/%s' % (r.get('n'), r.get('n_build'))


def summary(rep):
    """the report as markdown: a row per stage (its worst object) and the checks that move."""
    S = rep['stages']
    lines = ['# stage drift: %s (%s, on %s)' % (rep['spec'], os.path.basename(rep['build']), rep['where']), '']
    lines += ['| stage | object | drift |', '|---|---|---|']
    fc = S.get('fit_cranium')
    if fc:
        lines.append('| fit_cranium | head.cranium | build %s, evaluator %s%s |' % (fc['build'], fc['evaluator'],
                                                                                 ' (spec sets it)' if fc['spec_set'] else ''))
    ch = S['character']
    lines.append('| character | assembly (skin) | %s |' % _fmt(ch['assembly']))
    for n, r in ch['parts'].items():
        lines.append('| character | %s | %s |' % (n, _fmt(r)))
    lines.append('| character | landmarks | %s |' % ', '.join('%s %.2g L' % kv for kv in ch['landmarks_L'].items()))
    if 'skin_eval_subdiv1' in ch:
        lines.append('| character (modifiers) | skin, subdivided | %s |' % _fmt(ch['skin_eval_subdiv1']))
    for g in ('hair', 'accessories'):
        for n, r in S[g]['objects'].items():
            lines.append('| %s | %s | %s |' % (g, n, _fmt(r)))
        if S[g].get('target'):
            lines.append('| %s | the generated shape (QA target) | %s |' % (g, _fmt(S[g]['target'])))
        if S[g].get('silhouette_iou'):
            lines.append('| %s | silhouette IoU (0/90/180) | %s |' % (g, S[g]['silhouette_iou']))
    for n, r in S['garments']['objects'].items():
        if isinstance(r, dict):
            lines.append('| garments | %s | raw: %s; evaluated: %s |' % (n, _fmt(r['raw']), _fmt(r['eval'])))
        else:
            lines.append('| garments | %s | %s |' % (n, r))
    if S['garments'].get('mask'):
        m = S['garments']['mask']
        lines.append('| garments | skin mask | evaluator %d, build %d, %d differ |' % (m['evaluator'], m['build'], m['differ']))
    if rep.get('checks'):
        C = rep['checks']
        moved = {k: v for k, v in C.items() if (v['d'] or 0) > 1e-9 or v['build'][1] != v['evaluator'][1]}
        lines += ['', '%d checks compared, %d differ:' % (len(C), len(moved)), '',
                  '| check | build | evaluator | delta |', '|---|---|---|---|']
        for k, v in sorted(moved.items(), key=lambda kv: -(kv[1]['d'] or 0)):
            lines.append('| %s | %s %s | %s %s | %s |' % (k, _r(v['build'][0]), v['build'][1], _r(v['evaluator'][0]),
                                                         v['evaluator'][1], _r(v['d'])))
    return '\n'.join(lines) + '\n'


def _r(x):
    return round(x, 4) if isinstance(x, float) else x


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return 0
    build = args[0] if os.path.isabs(args[0]) else os.path.join(ROOT, args[0])
    out = args[args.index('--out') + 1] if '--out' in args else os.path.join(build, 'stagedrift')
    os.makedirs(out, exist_ok=True)
    rep = measure(build, checks='--no-checks' not in args)
    json.dump(rep, open(os.path.join(out, 'drift.json'), 'w'), indent=1, default=float)
    md = summary(rep)
    open(os.path.join(out, 'drift.md'), 'w').write(md)
    print(md)
    print('stagedrift:', os.path.join(out, 'drift.md'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
