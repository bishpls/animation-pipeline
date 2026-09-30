"""The numpy evaluator against the box (Michael, 2026-09-30: trustworthy local loops). For one spec, a box build and the
fast evaluator (charkit.bodyeval, as the body fit reads it: bodyfit.BodyChecks) measure the same commit, and every check
both produce is compared. A check whose values differ by more than its tolerance is drift: a fit tuned on the evaluator
aims at a number the build doesn't give (the body round found the hems 0.024-0.028 L apart).

    python -m charkit evaldrift [SPEC] [--tol 0.01] [--out DIR]   a build on the build box, then the evaluator there on
                                                                  the same synced copy; the report fetched into DIR
                                                                  (default charkit/out/evaldrift/<spec>)
    python -m charkit evaldrift [SPEC] --no-build                 the same against the box build already at --out
    python -m charkit evaldrift SPEC --build DIR --here           the evaluator and the comparison where it runs, against
                                                                  the build in DIR (what the box runs); the evaluator
                                                                  reads the build's resolved spec (DIR/NAME.spec.json)

    ... --stages                                                  also the geometry, stage by stage (below)

The report: DIR/drift.json and DIR/drift.md, every compared check (box value and status, evaluator value and status,
the difference, its tolerance), the drifted ones first. It exits 1 when any check drifts.

--stages (docs/GEOM_TRUTH.md): the evaluator's geometry against the build's bundle, stage by stage, with the evaluator
given the spec the build's scene was made from (the bundle's, after its cranium fit), so each row is that stage's own
computation, not a resolve that differs upstream: the cranium fit; the assembly (the skin's `assembly` variant), the eye
and mouth parts, the landmarks and the masked skin's subdivision; each hair object, the QA's target and the hair's
silhouettes; the accessories; each garment raw (as Blender holds it) and evaluated (Solidify, then Subdivision), and the
skin mask. Distances in head lengths L; `f32` counts vertices equal once both are rounded to float32, as Blender keeps
them. A stage drifts past GEOM_TOL (an object only one side has, raw geometry apart, a silhouette or mask that differs).
"""
import fnmatch, json, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = 'charkit/spec/clawd.json'
TOL = [                          # (check pattern, the largest difference that isn't drift), the first match wins
    ('palette_*', 0.5),          # CIEDE2000
    ('*', 0.01),                 # L, IoUs and shares
]


def tolerance(check, tol=None):
    """a check's tolerance: tol (a number) for every check, else the first TOL pattern it matches."""
    if tol is not None:
        return float(tol)
    return next(t for p, t in TOL if fnmatch.fnmatchcase(check, p))


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def compare(box, ev, tol=None):
    """box's checks against the evaluator's ({check: {value, status}} each, as qa.json names them), over the checks
    both have -> dict(rows (drifted first, then by difference), drift [names], status [names whose grade differs],
    only_box, only_eval, compared). A check drifts when its values differ by more than its tolerance (numbers) or at all
    (anything else)."""
    rows = []
    for k in sorted(set(box) & set(ev)):
        b, e = box[k] or {}, ev[k] or {}
        vb, ve = b.get('value'), e.get('value')
        if vb is None and ve is None:
            continue
        t = tolerance(k, tol)
        if _num(vb) and _num(ve):
            d = round(float(ve) - float(vb), 6)
            drift = abs(d) > t + 1e-12
        else:
            d, drift = None, vb != ve
        rows.append(dict(check=k, box=[vb, b.get('status')], eval=[ve, e.get('status')], diff=d, tol=t, drift=drift,
                         status_differs=b.get('status') != e.get('status')))
    rows.sort(key=lambda r: (not r['drift'], -(abs(r['diff']) if r['diff'] is not None else float('inf')), r['check']))
    return dict(rows=rows, compared=len(rows), drift=[r['check'] for r in rows if r['drift']],
                status=[r['check'] for r in rows if r['status_differs']],
                only_box=sorted(k for k in set(box) - set(ev) if (box[k] or {}).get('value') is not None),
                only_eval=sorted(k for k in set(ev) - set(box) if (ev[k] or {}).get('value') is not None))


def build_spec(build):
    """the resolved spec a build ran (BUILD/NAME.spec.json: with the code-built head's and body's geometry files, which
    the build's own steps made), as bodyeval.validate evaluates it."""
    return next(os.path.join(build, f) for f in sorted(os.listdir(build)) if f.endswith('.spec.json'))


def evaluator_checks(spec_path):
    """every check the fast evaluator gives for the spec, as the body fit reads them (bodyfit.BodyChecks, group 'all',
    fine: the render's subdivision) -> ({check: {value, status}}, seconds)."""
    from . import bodyeval, bodyfit, bodymeasure
    t = time.time()
    spec = bodyeval.resolve(spec_path)
    graph = bodymeasure.load_graph(spec) if spec.get('ref') else None
    C = bodyfit.BodyChecks(spec, graph).checks(spec, 'all', fine=True)
    return {k: {'value': v.get('value'), 'status': v.get('status')} for k, v in C.items()}, round(time.time() - t, 1)


def _git_of(build):
    tp = os.path.join(build, 'trace.jsonl')
    if os.path.exists(tp):
        for line in open(tp):
            rec = json.loads(line)
            if rec.get('event') == 'begin':
                return rec.get('git')
    return None


def here(spec_path, build, tol=None, with_stages=False):
    """the evaluator against the build in `build` (its qa/qa.json), both on this machine -> the report (also written to
    build/drift.json and drift.md). with_stages: the geometry stage by stage too (stages())."""
    qa = json.load(open(os.path.join(build, 'qa', 'qa.json')))
    box = {k: {'value': c.get('value'), 'status': c.get('status')} for k, c in qa['checks'].items()}
    ev, secs = evaluator_checks(build_spec(build))
    rep = dict(spec=spec_path, build=os.path.relpath(build, ROOT), git=_git_of(build), tol=tol, tolerances=TOL,
               evaluator_seconds=secs, t=time.strftime('%Y-%m-%dT%H:%M:%S'), **compare(box, ev, tol))
    if with_stages:
        rep['stages'] = stages(build)
        rep['stage_drift'] = stage_drift(rep['stages'])
    json.dump(rep, open(os.path.join(build, 'drift.json'), 'w'), indent=1, default=str)
    open(os.path.join(build, 'drift.md'), 'w').write(markdown(rep))
    return rep


def markdown(rep):
    L = ['# evaldrift: %s at %s: %d of %d checks drift' % (rep['spec'], rep.get('git'), len(rep['drift']), rep['compared']),
         '', 'The box build (`%s`) against the fast evaluator (bodyeval, as bodyfit reads it) on the same commit; '
         'tolerance per check: %s. Checks only the build has: %d; only the evaluator: %d.' % (
             rep['build'], rep['tol'] if rep.get('tol') is not None else ', '.join('%s %s' % tuple(pt) for pt in rep['tolerances']),
             len(rep['only_box']), len(rep['only_eval'])), '',
         '| check | box | evaluator | eval - box | tol | |', '| --- | --- | --- | --- | --- | --- |']
    for r in rep['rows']:
        L.append('| %s | %s %s | %s %s | %s | %s | %s |' % (
            r['check'], r['box'][0], r['box'][1] or '', r['eval'][0], r['eval'][1] or '',
            '' if r['diff'] is None else '%+.4f' % r['diff'], r['tol'],
            ('**drift**' if r['drift'] else '') + (' grade differs' if r['status_differs'] else '')))
    if rep.get('stages'):
        L += ['', stages_markdown(rep['stages'], rep.get('stage_drift') or [])]
    return '\n'.join(L) + '\n'


# ------------------------------------------------------------------------------------------- the stages (--stages)
GEOM_TOL = dict(raw_L=1e-5, evaluated_L=1e-4, iou=0.999, landmark_L=1e-5)
"""what counts as drift in the geometry: raw vertices further apart than raw_L (float32 storage is 2.4e-7 L), evaluated
ones (the modifiers' numpy ports) past evaluated_L, silhouettes under iou, landmarks past landmark_L (the trace rounds
joints to 1e-4 m, so they're shown, not judged)."""


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


def pair(ours, theirs, L):
    """one object's vertices, ours against the build's: -> dict(n, n_build, max_L, mean_L, f32 (vertices equal in
    float32), exact) when the counts agree, else the counts and the symmetric nearest-vertex distance."""
    import numpy as np
    a, b = np.asarray(ours, float), np.asarray(theirs, float)
    r = dict(n=int(len(a)), n_build=int(len(b)))
    if not len(a) or not len(b):
        return r
    if len(a) == len(b):
        d = np.linalg.norm(a - b, axis=1)
        f32 = lambda x: x.astype(np.float32)
        r.update(max_L=float(d.max() / L), mean_L=float(d.mean() / L), f32=int((f32(a) == f32(b)).all(1).sum()),
                 exact=bool((a == b).all()))
        return r
    r.update(nearest(a, b, L))
    return r


def nearest(ours, theirs, L):
    """meshes whose vertex orders differ (evaluated ones): the symmetric nearest-vertex distance -> dict."""
    import numpy as np
    from scipy.spatial import cKDTree
    a, b = np.asarray(ours, float), np.asarray(theirs, float)
    if not len(a) or not len(b):
        return dict(n=int(len(a)), n_build=int(len(b)))
    d1 = cKDTree(b).query(a)[0]; d2 = cKDTree(a).query(b)[0]
    return dict(n=int(len(a)), n_build=int(len(b)), hausdorff_L=float(max(d1.max(), d2.max()) / L),
                p99_L=float(np.percentile(np.r_[d1, d2], 99) / L), mean_nn_L=float(0.5 * (d1.mean() + d2.mean()) / L))


def _sil_iou(parts_a, parts_b, az, frame):
    import numpy as np
    from .bodymeasure import iou
    from .geom.mesh import Mesh
    from .geom.raster import silhouette
    m = lambda ps: [Mesh(np.asarray(V, float), np.asarray(T)) for V, T in ps if len(T)]
    ma, mb = m(parts_a), m(parts_b)
    if not ma or not mb:
        return None
    return round(float(iou(np.any([silhouette(x, az, frame) for x in ma], 0),
                           np.any([silhouette(x, az, frame) for x in mb], 0))), 4)


def stages(build):
    """the evaluator's geometry on the build's own spec against the build's bundle, stage by stage (the module's
    --stages) -> {stage: {...}}."""
    import numpy as np
    from . import bodyeval, bundle as bundlelib, garments as gm, scene
    from .geom.parts import load_generated
    B = bundlelib.load(os.path.join(build, 'bundle'))
    spec = _local(dict(B.spec), ROOT)
    S = {}
    # the cranium fit: the build's resolved spec before Blender through the venv's GLB reader
    pre = _local(json.load(open(build_spec(build))), ROOT)
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        ev = scene.fit_cranium(json.loads(json.dumps(pre)), ROOT, load=lambda p: load_generated(p, compat=True))
    a, b = (ev.get('head') or {}).get('cranium'), (spec.get('head') or {}).get('cranium')
    S['fit_cranium'] = dict(evaluator=a, build=b, spec_set='cranium' in (pre.get('head') or {}))
    E = bodyeval.Evaluator(spec)
    t = time.time()
    G = E.geometry()
    A, L = G.A, float(G.A['head']['L'])
    ours = {p.name: p for p in G.parts if getattr(p, 'role', None) != 'unmasked'}
    skin = B.skin()
    ch = dict(assembly=pair(A['verts'], skin.V('assembly'), L))
    ch['parts'] = {o.name: pair(ours[o.name].V, o.V('eval'), L) if o.name in ours else 'build only'
                   for o in B.objects(groups=('eye', 'mouth'), visible=False)}
    lm_b, asm = dict(B._meta.get('landmarks') or {}), dict(B._meta.get('assembly') or {})
    lm = {k: abs(float(G.landmarks[k]) - float(v)) / L for k, v in (('waist', asm.get('waist_z')), ('knee', asm.get('knee_z')),
                                                                   ('chin', lm_b.get('chin_z')), ('L', lm_b.get('L')))
          if v is not None}
    dj = [np.abs(np.asarray(A['joints'][k], float) - np.asarray(v, float)).max()
          for k, v in (lm_b.get('joints') or {}).items() if k in A['joints']]
    if dj:
        lm['joints'] = float(max(dj)) / L
    ch['landmarks_L'] = lm
    sk = ours.get(skin.name)
    if sk is not None and skin.has('masked'):
        V1, polys = sk.subdivided(1)[:2]
        used = np.unique(np.concatenate([np.asarray(q).ravel() for q in polys]))      # (the mask drops the rest)
        ch['skin_evaluated'] = nearest(V1[used], skin.V('masked'), L)
    S['character'] = ch
    from .geom.raster import Frame
    for grp, bg in (('hair', 'hair'), ('accessories', 'accessory')):
        bobj = [o for o in B.objects(groups=(bg,), visible=False) if not o.name.endswith('_normals')]
        rows = {o.name: pair(ours[o.name].V, o.V('raw' if o.has('raw') else 'eval'), L) if o.name in ours else 'build only'
                for o in bobj}
        rows.update({n: 'evaluator only' for n, p in ours.items() if p.group == grp and n not in rows})
        st = dict(objects=rows)
        if bobj:
            Vb = np.concatenate([o.V('eval') for o in bobj])
            fr = Frame((0.0, 0.0, float(Vb[:, 2].mean())), float(np.ptp(Vb[:, 2])) * 1.3 + 1e-3, (400, 400))
            st['silhouette_iou'] = {az: _sil_iou([(p.V, p.tris()) for p in ours.values() if p.group == grp],
                                                 [(o.V('eval'), o.tris('eval')[0]) for o in bobj], az, fr)
                                    for az in (0, 90, 180)}
        S[grp] = st
    T = B.target()
    if T is not None and G.target is not None:
        S['hair']['target'] = pair(np.asarray(G.target[0], float), T[0], L)
    gs = {}
    for o in B.objects(groups=('garment',), visible=False):
        p = ours.get(o.name)
        gs[o.name] = 'build only' if p is None else dict(raw=pair(p.V, o.V('raw'), L),
                                                         evaluated=nearest(p.subdivided(1)[0], o.V('eval'), L))
    gs.update({n: 'evaluator only' for n, p in ours.items() if p.group == 'garments' and n not in gs})
    hull = gm.hull_pieces(spec, A) if any(g.get('source') == 'hull' for g in spec.get('garments') or []) else None
    hide = bodyeval.garment_parts(A, spec.get('garments'), None, None, hull, spec)[1]
    hb = np.asarray(B.array('skin/under_garments'), bool) if B.has('skin/under_garments') else None
    S['garments'] = dict(objects=gs, mask=None if hb is None else dict(evaluator=int(hide.sum()), build=int(hb.sum()),
                                                                       differ=int((hide != hb).sum())))
    S['seconds'] = round(time.time() - t, 1)
    return S


def stage_drift(S, tol=None):
    """the stage rows past GEOM_TOL -> ['stage: object: why', ...]."""
    T = dict(GEOM_TOL, **(tol or {}))
    out = []

    def geo(stage, name, r, key):
        if not isinstance(r, dict):
            out.append('%s: %s: %s' % (stage, name, r))
        elif 'max_L' in r and r['max_L'] > T[key]:
            out.append('%s: %s: %.3g L apart' % (stage, name, r['max_L']))
        elif 'hausdorff_L' in r and r['hausdorff_L'] > T[key]:
            out.append('%s: %s: %.3g L apart (nearest vertex; %d against %d vertices)' % (
                stage, name, r['hausdorff_L'], r['n'], r['n_build']))
        elif 'n' in r and r['n'] != r['n_build'] and 'hausdorff_L' not in r:
            out.append('%s: %s: %d against %d vertices' % (stage, name, r['n'], r['n_build']))
    fc = S.get('fit_cranium') or {}
    if fc.get('evaluator') != fc.get('build'):
        out.append('fit_cranium: %s against %s' % (fc.get('evaluator'), fc.get('build')))
    ch = S.get('character') or {}
    if ch:
        geo('character', 'assembly', ch['assembly'], 'raw_L')
        for n, r in ch['parts'].items():
            geo('character', n, r, 'raw_L')
        if 'skin_evaluated' in ch:
            geo('character (evaluated)', 'skin', ch['skin_evaluated'], 'evaluated_L')
    for g in ('hair', 'accessories'):
        st = S.get(g) or {}
        for n, r in (st.get('objects') or {}).items():
            geo(g, n, r, 'raw_L')
        if st.get('target'):
            geo(g, 'the QA target', st['target'], 'raw_L')
        low = {az: v for az, v in (st.get('silhouette_iou') or {}).items() if v is not None and v < T['iou']}
        if low:
            out.append('%s: silhouette IoU %s' % (g, low))
    gs = S.get('garments') or {}
    for n, r in (gs.get('objects') or {}).items():
        if isinstance(r, dict):
            geo('garments', n, r['raw'], 'raw_L')
            geo('garments (evaluated)', n, r['evaluated'], 'evaluated_L')
        else:
            geo('garments', n, r, 'raw_L')
    if (gs.get('mask') or {}).get('differ'):
        out.append('garments: skin mask: %d vertices differ' % gs['mask']['differ'])
    return out


def _fmt(r):
    if not isinstance(r, dict):
        return str(r)
    if 'max_L' in r:
        return 'max %.3g L (mean %.2g), %s' % (r['max_L'], r['mean_L'],
                                               'exact' if r['exact'] else 'f32 %d/%d' % (r['f32'], r['n']))
    if 'hausdorff_L' in r:
        return 'n %d/%d, nearest-vertex max %.3g L, mean %.2g' % (r['n'], r['n_build'], r['hausdorff_L'], r['mean_nn_L'])
    return 'n %s/%s' % (r.get('n'), r.get('n_build'))


def stages_markdown(S, drift):
    """the --stages section: a row per stage object, then what drifts."""
    L = ['## stages', '', 'The evaluator on the build\'s own spec against its bundle (GEOM_TOL %s): %s.' % (
        ', '.join('%s %s' % kv for kv in GEOM_TOL.items()), '%d drift' % len(drift) if drift else 'none drift'), '',
         '| stage | object | drift |', '| --- | --- | --- |']
    fc = S.get('fit_cranium')
    if fc:
        L.append('| fit_cranium | head.cranium | build %s, evaluator %s%s |' % (fc['build'], fc['evaluator'],
                                                                           ' (the spec sets it)' if fc['spec_set'] else ''))
    ch = S.get('character') or {}
    if ch:
        L.append('| character | assembly | %s |' % _fmt(ch['assembly']))
        L += ['| character | %s | %s |' % (n, _fmt(r)) for n, r in ch['parts'].items()]
        L.append('| character | landmarks | %s |' % ', '.join('%s %.2g L' % kv for kv in ch['landmarks_L'].items()))
        if 'skin_evaluated' in ch:
            L.append('| character (evaluated) | skin, masked, subdivided | %s |' % _fmt(ch['skin_evaluated']))
    for g in ('hair', 'accessories'):
        st = S.get(g) or {}
        L += ['| %s | %s | %s |' % (g, n, _fmt(r)) for n, r in (st.get('objects') or {}).items()]
        if st.get('target'):
            L.append('| %s | the QA target | %s |' % (g, _fmt(st['target'])))
        if st.get('silhouette_iou'):
            L.append('| %s | silhouette IoU (0 / 90 / 180) | %s |' % (g, ' / '.join(str(v) for v in st['silhouette_iou'].values())))
    gs = S.get('garments') or {}
    for n, r in (gs.get('objects') or {}).items():
        L.append('| garments | %s | %s |' % (n, 'raw: %s; evaluated: %s' % (_fmt(r['raw']), _fmt(r['evaluated']))
                                            if isinstance(r, dict) else r))
    if gs.get('mask'):
        m = gs['mask']
        L.append('| garments | skin mask | evaluator %d, build %d, %d differ |' % (m['evaluator'], m['build'], m['differ']))
    if drift:
        L += ['', 'Drifting:', ''] + ['- %s' % x for x in drift]
    return '\n'.join(L) + '\n'


def main(args):
    if args and args[0] in ('-h', '--help'):
        print(__doc__); return 0
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    pos = [a for i, a in enumerate(args) if not a.startswith('--') and (i == 0 or args[i - 1] not in ('--tol', '--build', '--out'))]
    spec = pos[0] if pos else SPEC
    tol = float(opt('--tol')) if opt('--tol') else None
    if '--here' in args:
        rep = here(spec, os.path.join(ROOT, opt('--build')), tol, with_stages='--stages' in args)
    else:
        from . import remote
        stem = os.path.basename(spec).split('.')[0]
        out = opt('--out', 'charkit/out/evaldrift/%s' % stem)
        if '--no-build' not in args:
            code = remote.build([spec, '--out', out, '--boards', 'views', '--no-blend'])
            if code:
                raise SystemExit('evaldrift: the box build failed (exit %d)' % code)
        more = (['--tol', str(tol)] if tol is not None else []) + (['--stages'] if '--stages' in args else [])
        code = remote.charkit(['evaldrift', remote._portable_spec(spec), '--build', out, '--here'] + more)
        remote._sh('fetch', ROOT, out)
        p = os.path.join(ROOT, out, 'drift.json')
        if not os.path.exists(p):
            raise SystemExit('evaldrift: the evaluator run failed on the box (exit %d)' % code)
        rep = json.load(open(p))
        # the box copy has no git: the commit (and whether the synced tree had changes) from here
        import subprocess
        g = lambda *a: subprocess.run(['git', '-C', ROOT, *a], capture_output=True, text=True).stdout.strip()
        rep.update(spec=spec, git=g('rev-parse', '--short', 'HEAD') + ('+dirty' if g('status', '--porcelain', '--untracked-files=no') else ''))
        json.dump(rep, open(p, 'w'), indent=1, default=str)
        open(os.path.join(ROOT, out, 'drift.md'), 'w').write(markdown(rep))
    print(markdown(rep).split('\n')[0])
    for r in rep['rows']:
        if r['drift']:
            print('  %-40s box %-10s eval %-10s diff %+.4f' % (r['check'], r['box'][0], r['eval'][0], r['diff'])
                  if r['diff'] is not None else '  %-40s box %s eval %s' % (r['check'], r['box'][0], r['eval'][0]))
    for x in rep.get('stage_drift') or []:
        print('  stage %s' % x)
    print('report', os.path.join(ROOT, rep['build'], 'drift.md'))
    return 1 if rep['drift'] or rep.get('stage_drift') else 0
