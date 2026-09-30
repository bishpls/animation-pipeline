"""How much the hull-sourced garments depend on the hull mesh's decimation, in the fast evaluator (numpy, no Blender):
the spec's hull re-surfaced from its own occupancy (hull.npz) and decimated to other face counts (and, with --remesh,
by another decimation module, e.g. pipeline-3d's LAPACK solve), each variant's vertices and per-vertex pieces taken as
the hull build takes them, then the garments built from each (source 'mesh': the decimated vertices, as garments
built before tool/garment-sampling; 'shell': garments.hull_pieces as it is) and every body_* and piece_* check, and the
flaps' hang, measured. The body is fitted once to the shipped hull (--body fixed) or to each variant (refit: code_body
reads the decimated mesh too).

    python charkit/tests/garment_sensitivity.py [--spec charkit/spec/clawd.json] [--source mesh|shell]
        [--faces 150000,142500,157500] [--remesh FILE] [--body fixed|refit] [--out DIR]
    -> DIR/sensitivity_<source>_<body>.json: per check the reference variant's value and grade, every other
       variant's, and the largest change; per garment each variant's vertex displacement from the reference (max, p95,
       L) or its vertex count's change.

The hull is the spec's produced hull (built first when stale). Variants and fitted bodies are cached in DIR.
"""
import argparse, contextlib, importlib.util, io, json, os, sys, time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def hull_dir(spec):
    from charkit import manifest
    return os.path.dirname(manifest.produced(spec, 'hull'))


def variant(hdir, faces, remesh_file, cache):
    """the hull re-surfaced (charkit.geom.hull.surface) from its occupancy and decimated to `faces` (by remesh_file's
    decimate, else charkit.geom.remesh's), each vertex labelled as the build labels it -> (V, labels)."""
    from charkit.geom import hull as H
    tag = os.path.splitext(os.path.basename(remesh_file))[0] if remesh_file else 'det'
    p = os.path.join(cache, 'variant_%s_%d.npz' % (tag, faces))
    if os.path.exists(p):
        z = np.load(p)
        return z['V'], z['lab']
    Z = np.load(os.path.join(hdir, 'hull.npz'))
    A = H.Axes(Z['xs'], Z['ys'], Z['zs'], float(json.load(open(os.path.join(hdir, 'hull.json')))['h_L']))
    if remesh_file:
        sp = importlib.util.spec_from_file_location('remesh_' + tag, remesh_file)
        remesh = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(remesh)
    else:
        from charkit.geom import remesh
    m = remesh.decimate(H.surface(Z['V'], A), faces)
    S = Z['shell'].astype(np.int64)
    lab, _ = H.vertex_labels(m, dict(ix=S[:, 0], iy=S[:, 1], iz=S[:, 2], label=Z['shell_label'],
                                     cls=np.zeros(len(S), np.int16)), A)
    np.savez(p, V=m.V, lab=lab)
    return m.V, lab


def mesh_pieces(hdir, V, lab, spec, A):
    """hull_pieces' dict from a variant's vertices and labels (the sidecar's names and eyes): the mesh source."""
    from charkit import i3d
    J = json.load(open(os.path.join(hdir, 'hull.glb.json')))
    eye_mid, spacing = i3d.eye_target(A, spec['hair']['shape'])
    W = i3d.align_by_eyes(np.asarray(V, float), (np.asarray(J['eyes'][0], float), np.asarray(J['eyes'][1], float)),
                          eye_mid, spacing)
    return {pid: W[lab == int(k)] for k, pid in J['piece_names'].items() if (lab == int(k)).any()}


def body_code(spec, hdir, V, lab, path):
    """the authored body fitted to the hull (V, lab: a variant's mesh; None: the shipped one) -> path."""
    from charkit import bodypage, code_body
    if os.path.exists(path):
        return path
    orig = code_body.Hull

    class VHull(orig):
        def __init__(self, d):
            orig.__init__(self, d)
            if V is not None:
                self.V, self.piece = np.asarray(V, float), np.asarray(lab)
    bodypage.Hull = VHull
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            bodypage.save_body(spec, path, log=lambda *a: None)
    finally:
        bodypage.Hull = orig
    return path


def checks(E, G):
    """the body_* checks (bodymeasure.sheet_body), the piece_* checks (piece_shapes, grade_pieces) and each flap's hang
    (qa3d.spring_pieces' measure on the flap's own vertices), named as qa.json names them."""
    from charkit import bodymeasure, qa3d
    out = dict(E.sheet_checks(G, palette=False))
    S = E.sheet()
    B = G.bundle('viewport')
    masks, graph, _ = bodymeasure.piece_masks(G.spec)
    PS = bodymeasure.piece_shapes(bodymeasure.piece_views(B, S), [o['name'] for o in B['objects']], masks, graph,
                                  G.spec, S.ppl)
    out.update({'piece_' + k: v for k, v in qa3d.grade_pieces(PS).items()})
    ez = float(np.mean(np.asarray(B['landmarks']['iris'])[:, 2]))
    for sp in graph.get('springs') or []:
        pid = sp['piece']
        J = np.array((sp.get('drawn_chains') or sp.get('chains') or [{}])[0].get('joints') or [])
        if not len(J) or not any(g['name'] == pid and g.get('source') == 'flap' for g in G.spec['garments']):
            continue
        V = next(o['V'] for o in B['objects'] if o['name'] == pid)
        top, low = (float(V[:, 2].max()) - ez) / G.L, (float(V[:, 2].min()) - ez) / G.L
        v = max(abs(top - float(J[0, 2])), abs(low - float(J[:, 2].min())))
        out['piece_%s_hang' % pid] = {'value': round(v, 4), 'status': 'PASS' if v <= qa3d.HANG_PASS else 'WARN'
                                      if v <= qa3d.HANG_WARN else 'FAIL'}
    return out


def run(spec_path, source, faces, remesh_file, body, cache):
    from charkit import bodyeval, character, code_base, garments as gm
    os.makedirs(cache, exist_ok=True)
    spec = bodyeval.resolve(spec_path, check=True)
    hdir = hull_dir(spec)
    code = character.base_of(spec) == 'code'
    if code:
        hc = os.path.join(cache, 'head_code.npz')
        if not os.path.exists(hc):
            code_base.save_head(spec, hc)
        spec['head_code'] = hc
    code_body = character.body_source(spec) == 'code'
    names = [('det', f) for f in faces] + ([('remesh', faces[0])] if remesh_file else [])
    res, E, orig = {}, None, gm.hull_pieces
    for tag, f in names:
        t = time.time()
        V, lab = variant(hdir, f, remesh_file if tag == 'remesh' else None, cache)
        sp = dict(spec)
        if code_body:
            sp['body_code'] = body_code(spec, hdir, *((V, lab) if body == 'refit' else (None, None)),
                                        os.path.join(cache, 'body_code_%s.npz' % ('%s_%d' % (tag, f) if body == 'refit'
                                                                                  else 'shipped')))
        if E is None or body == 'refit':
            E = bodyeval.Evaluator(sp)
        E._garments = {}
        if source == 'mesh':
            gm.hull_pieces = lambda s, A, V=V, lab=lab: mesh_pieces(hdir, V, lab, s, A)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                G = E.geometry()
                C = checks(E, G)
        finally:
            gm.hull_pieces = orig
        res['%s_%d' % (tag, f)] = dict(checks={k: (v.get('value'), v.get('status')) for k, v in C.items() if 'value' in v},
                                       garm={p.name: np.asarray(p.V, float) for p in G.parts if p.group == 'garments'},
                                       L=G.L)
        print('%s %s_%d: %.0fs' % (source, tag, f, time.time() - t), flush=True)
    return res


def summarise(res):
    names = list(res)
    ref, others = res[names[0]], names[1:]
    out = {'reference': names[0], 'checks': {}, 'garments': {}}
    for k, (v0, s0) in sorted(ref['checks'].items()):
        row = {'ref': [v0, s0]}
        row.update({n: list(res[n]['checks'].get(k, (None, None))) for n in others})
        ds = [abs(row[n][0] - v0) for n in others if isinstance(row[n][0], (int, float)) and isinstance(v0, (int, float))]
        row['max_abs_change'] = round(float(max(ds)), 4) if ds else None
        out['checks'][k] = row
    for g, V0 in ref['garm'].items():
        row = {}
        for n in others:
            V = res[n]['garm'].get(g)
            if V is None:
                row[n] = 'missing'
            elif V.shape != V0.shape:
                row[n] = 'verts %d -> %d' % (len(V0), len(V))
            else:
                d = np.linalg.norm(V - V0, axis=1) / ref['L']
                row[n] = [round(float(d.max()), 5), round(float(np.percentile(d, 95)), 5)]
        out['garments'][g] = row
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--spec', default=os.path.join(ROOT, 'charkit', 'spec', 'clawd.json'))
    ap.add_argument('--source', default='shell', choices=('mesh', 'shell'))
    ap.add_argument('--faces', default='150000,142500,157500')
    ap.add_argument('--remesh', help="another decimation module's file (e.g. `git show pipeline-3d:charkit/geom/remesh.py`"
                                     ' with its relative imports made absolute)')
    ap.add_argument('--body', default='fixed', choices=('fixed', 'refit'))
    ap.add_argument('--out', default=os.path.join(ROOT, 'charkit', 'out', 'garment_sensitivity'))
    a = ap.parse_args()
    S = summarise(run(a.spec, a.source, [int(x) for x in a.faces.split(',')], a.remesh, a.body, a.out))
    p = os.path.join(a.out, 'sensitivity_%s_%s.json' % (a.source, a.body))
    json.dump(S, open(p, 'w'), indent=1)
    worst = sorted(((r['max_abs_change'] or 0, k) for k, r in S['checks'].items()), reverse=True)[:8]
    print('largest check changes:', ', '.join('%s %.4f' % (k, v) for v, k in worst))
    print(p)
