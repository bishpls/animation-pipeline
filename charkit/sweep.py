"""charkit sweep: declared variants of a finished build, rebuilt in-process at the stage they change and measured by the
QA's own parts, in one table with every piece's shape IoU per view beside the checks (the anti-gaming guard). It
replaces the per-round variant harnesses (tool/sweep, docs/workstreams/sweep.md: 22% of the agents' active time on
2026-09-30 went to writing, running and tabulating them).

    python -m charkit sweep run DECL.json [--out DIR] [--jobs N] [--only NAME,..] [--box [NAME]] [--code ROOT]
    python -m charkit sweep BASE --stage garments|hair|qa [--spec SPEC] [--set PATH=JSON ..] [--variant NAME=JSON ..]
                                 [--grid PATH=JSONLIST ..] [--oat PATH=JSONLIST ..] [--parts P,..] [--checks PAT,..]
                                 [--objects NAME,..] [--no-control] [--no-rebase] [--out DIR] [--jobs N] [--box [NAME]]
                                 [--code ROOT]
    python -m charkit sweep swap A B --check CHECK [--part PART] [--parts P,..] [--objects PAT,..] [--drop]
                                 [--groups hair,garment,accessory] [--inputs PATH[=VALUE],..] [--stage hair|garments]
                                 [--out DIR] [--no-rebase]
    python -m charkit sweep table OUT/sweep.json [--checks PAT,..]       # the table again (markdown) from a result

The declaration (JSON; the inline form writes one to OUT/decl.json):
  base      a finished build's folder (bundle/, geom/; a box build fetched here, or one on the box with --box; a
            preview without geom/ has its head and body codes remade by the build's own steps, cli.code_head and
            code_body, each a cache.file_step)
  stage     what each variant rebuilds; everything else is the base's, restored from the cache:
              qa        nothing: the base bundle measured (variants patch the measurement: `qa:MODULE.NAME` keys)
              garments  the fast evaluator (charkit.bodyeval) at the variant's spec: the garments and accessories it
                        makes, spliced into the base bundle (the head and body codes are the base's geom/ files)
              hair      the build's own hair pieces step (charkit.cli.pieces_hair, a cache.file_step: a variant whose
                        inputs didn't change restores) on the variant's spec, its pieces spliced in with their shading
                        normals (`style.hair_pieces.KEY` overrides the style profile: run uncached)
  spec      the spec the variants start from: a spec file, resolved as the build resolves it (bodyeval.resolve), or
            by default the base bundle's own resolved spec
  set       overrides every row shares (the control too); variants, grid, oat add their own:
  variants  {name: {PATH: value}} (or [{name, set}]);  grid  {PATH: [values]} (every combination);
  oat       {PATH: [values]} (one path at a time, the rest as `set`)
            PATH is dotted, list items by name, kind or index (garments.bow.pleat.tilt); a null value deletes the key;
            `qa:charkit.pieceqa.LIMITS` patches a module attribute while the row is measured (what reads it at call
            time: a default argument bound at import, spikes(min_depth=SPIKE_MIN), keeps its value)
  control   true (default): a first row, the base spec through the same stage with `set` alone. Deltas are against
            it, so the stage's own drift from the Blender build (evaldrift) cancels
  objects   the objects spliced (default: those whose geometry any row's rebuild changed against the control's; every
            row splices the same set: with --jobs, a shard that spliced another set runs again with the union)
  parts     the QA parts run per row (registry names); the shape parts (sheet_pieces, hair_pieces: shape_parts) are
            added
  checks    the checks tabulated (fnmatch patterns; default: every check of the named parts)
  boards    optional: {"az": [0, 90], "crop": OBJECT, "pad": 0.05} a picture per row (OUT/NAME/board.png)
  rebase    true (default): the base bundle's spec paths into its build folder rebased to where it is now
            (calibrate.load_bundle); false keeps them as written (a historical harness's reading)

Every row is measured on a bundle drawn with the numpy drawing (a spliced bundle has no export of its own: the render
drawing would draw the export's geometry by name), so rows compare with each other; the base's qa.json may differ for
the parts the render drawing measures.

Outputs in OUT: sweep.json (the declaration, the code's commit, per row its overrides, seconds, spliced objects and
checks: value, status, grade, views, per_view, ratio, flag ...), sweep.md (the checks, a delta against the control per
cell, flag checks marked [F]; the shape table: every piece's IoU per view that moved; the guard: a chosen check
improving while a piece's shape IoU drops more than calibrate.DROP in a view), and per row OUT/NAME/res.json.

Swap mode (attribution): A and B two finished builds (before, after). The check's part (from A's qa.json, or --part) on
A, on B, then on A with each of B's objects in place of its own (A + B.name) and on B with each of A's (B + A.name; an
object only B has: B - name); --drop adds each build without each (A - name, B - name). Each row: the check's value,
its per-view readings, the share of the A -> B move a swap carries, and its delta against its own build; with every
object's move between the builds (its largest vertex move in L, and its rigid rotation).
--inputs PATH[=VALUE],..: B's spec with A's value at PATH (or VALUE), rebuilt at --stage (hair for head_code and
hair.*, else garments) and measured the same way (tools/hull_local/hairswap.py's question: which input moves a piece).

Parallel: --jobs N runs the rows in N processes, each in a machine build slot (charkit.procs: the laptop has one, so
keep 1 there). On the box: --box [NAME] runs it there (`remote run --fetch OUT`); the base must be a build on the box.
--code ROOT runs the sweep with another tree's charkit (an unmerged branch's checks, or the code a historical harness
ran: the acceptance reproductions in charkit/tests/test_sweep.py and docs/workstreams/sweep.md).

    python -m charkit sweep charkit/out/b2_close --stage garments --objects bow --parts collar_flags \\
        --oat 'garments.bow.pleat.tilt=[0.5,1.0]' --checks 'bow_*'
    python -m charkit sweep swap charkit/out/h5_base charkit/out/hair5_b --check art_terminator_hair --drop
"""
import contextlib, copy, fnmatch, itertools, json, os, re, subprocess, sys, time

import numpy as np

STAGES = ('qa', 'garments', 'hair')
SHAPE_PARTS = ('sheet_pieces', 'hair_pieces')          # every piece's shape IoU per view: the guard's measure
SHAPE_CHECK = re.compile(r'^(piece_|hair_piece_)')      # the shape checks (their `views`: IoU per view)
KEEP = ('value', 'status', 'grade', 'graded_as', 'flag', 'views', 'iou', 'ratio', 'per_view', 'worst', 'ours',
        'design', 'ref', 'median', 'per_side', 'count', 'why')
RANK = {'PASS': 0, 'WARN': 1, 'FAIL': 2}
QA_PATCH = 'qa:'
STYLE = 'style.'
MOVED = 1e-9                                            # m: an object's vertices moved more than this: it changed


def root():
    """the root of the charkit tree this sweep runs with (--code: another tree's)."""
    import charkit
    return os.path.dirname(os.path.dirname(os.path.abspath(charkit.__file__)))


def home():
    """where outputs go by default: the caller's tree (with --code, the tree that ran the command), else root()."""
    return os.environ.get('CHARKIT_SWEEP_HOME') or root()


def _abs(p, base=None):
    """a path made absolute against base, else the caller's working directory (with --code the command runs from the
    other tree: CHARKIT_SWEEP_CWD keeps the caller's)."""
    if p is None:
        return None
    p = os.path.expanduser(p)
    return p if os.path.isabs(p) else os.path.abspath(os.path.join(
        base or os.environ.get('CHARKIT_SWEEP_CWD') or os.getcwd(), p))


# ----------------------------------------------------------------------------------------------- the declaration
def load_decl(decl):
    """a declaration (a path or a dict) -> dict, its base an absolute path."""
    if isinstance(decl, str):
        decl = _abs(decl)
        here = os.path.dirname(decl)
        decl = json.load(open(decl))
        decl.setdefault('_dir', here)
    d = dict(decl)
    d['base'] = _abs(d['base'])
    d.setdefault('stage', 'qa')
    if d['stage'] not in STAGES:
        raise SystemExit('sweep: stage %r is not one of %s' % (d['stage'], ', '.join(STAGES)))
    return d


def _item(lst, key):
    """a list element's index by index, name or kind (bodyeval's convention)."""
    if isinstance(key, int) or (isinstance(key, str) and key.lstrip('-').isdigit()):
        return int(key)
    for i, x in enumerate(lst):
        if isinstance(x, dict) and (x.get('name') == key or x.get('kind') == key):
            return i
    raise KeyError(key)


def apply(spec, over):
    """the spec with overrides {dotted path: value} applied (a deep copy): list items by name, kind or index, missing
    dict levels made, a None value deleting the key. `qa:` and `style.` keys are not the spec's (skipped)."""
    s = copy.deepcopy(spec)
    for path, v in over.items():
        if path.startswith((QA_PATCH, STYLE)):
            continue
        ks = path.split('.')
        cur = s
        for k in ks[:-1]:
            if isinstance(cur, list):
                cur = cur[_item(cur, k)]
            else:
                cur = cur.setdefault(k, {})
        last = ks[-1]
        if isinstance(cur, list):
            i = _item(cur, last)
            if v is None:
                cur.pop(i)
            else:
                cur[i] = copy.deepcopy(v)
        elif v is None:
            cur.pop(last, None)
        else:
            cur[last] = copy.deepcopy(v)
    return s


def _short(paths):
    """each path's shortest unambiguous dotted suffix (a grid row's name)."""
    out = {}
    for p in paths:
        ks = p.split('.')
        for n in range(1, len(ks) + 1):
            s = '.'.join(ks[-n:])
            if sum(1 for q in paths if q.split('.')[-n:] == ks[-n:]) == 1:
                out[p] = s
                break
        else:
            out[p] = p
    return out


def _fmt(v):
    return json.dumps(v, separators=(',', ':')) if not isinstance(v, str) else v


def expand(decl):
    """the rows: [dict(name, set)] in order: the control (unless control is false), the named variants, the grid's
    combinations, the one-at-a-time values. Each row's set is the declaration's `set` with its own overrides."""
    shared = dict(decl.get('set') or {})
    rows = []
    if decl.get('control', True):
        rows.append(dict(name='control', set=dict(shared), control=True))
    V = decl.get('variants') or {}
    items = [(v['name'], v.get('set') or {}) for v in V] if isinstance(V, list) else list(V.items())
    for name, over in items:
        rows.append(dict(name=name, set=dict(shared, **over)))
    for k in ('grid', 'oat'):
        bad = [p for p, v in (decl.get(k) or {}).items() if not isinstance(v, list)]
        if bad:
            raise SystemExit('sweep: %s %s is not a list of values' % (k, bad[0]))
    grid = decl.get('grid') or {}
    if grid:
        keys = list(grid)
        sh = _short(keys)
        for combo in itertools.product(*[grid[k] for k in keys]):
            over = dict(zip(keys, combo))
            rows.append(dict(name=','.join('%s=%s' % (sh[k], _fmt(v)) for k, v in over.items()),
                             set=dict(shared, **over)))
    oat = decl.get('oat') or {}
    sh = _short(list(oat))
    for k, vals in oat.items():
        for v in vals:
            rows.append(dict(name='%s=%s' % (sh[k], _fmt(v)), set=dict(shared, **{k: v})))
    names = [r['name'] for r in rows]
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup:
        raise SystemExit('sweep: rows named twice: %s' % ', '.join(dup))
    return rows


# ---------------------------------------------------------------------------------------------------------- the base
def load_bundle(build, rebase=True):
    """a build's bundle (its folder or its bundle folder): with rebase, its spec's paths into the build's folder pointed
    where the folder is now (calibrate.load_bundle; a box build's /srv/work paths)."""
    from charkit import bundle as bl
    bdir = build if os.path.exists(os.path.join(build, 'bundle.json')) else os.path.join(build, 'bundle')
    if rebase:
        try:
            from charkit import calibrate
            return calibrate.load_bundle(build)
        except ImportError:                                 # (a tree from before charkit.calibrate)
            pass
    return bl.load(bdir)


def base_spec(decl, B0):
    """the spec the rows start from: the declaration's spec file resolved as the build resolves it, or the base bundle's
    own; the head and body codes from the base's geom/ when it has them (the harnesses' way: the evaluator then builds on
    the build's head and body)."""
    if decl.get('spec'):
        from charkit import bodyeval
        import io
        path = decl['spec']
        with contextlib.redirect_stdout(io.StringIO()):         # (the produced references' reports)
            spec = bodyeval.resolve(path if os.path.isabs(path) else os.path.join(root(), path))
    else:
        spec = copy.deepcopy(B0._meta.get('spec') or {})
    missing = []
    for k in ('head_code', 'body_code'):
        p = os.path.join(decl['base'], 'geom', k + '.npz')
        if os.path.exists(p):
            spec[k] = p
        elif spec.get(k) and not os.path.exists(spec[k]):
            missing.append(k)
    if missing and decl['stage'] != 'qa':
        # (a build that kept no geom/, a preview: its head and body made again by the build's own venv steps, each a
        # cache.file_step, so an unchanged head restores)
        from charkit import cli
        import io
        up = os.path.join(_abs(decl.get('_out') or os.path.join(home(), 'charkit', 'out', 'sweep', '_upstream')),
                          '_upstream')
        os.makedirs(up, exist_ok=True)
        for k in missing:
            with contextlib.redirect_stdout(io.StringIO()):
                spec = getattr(cli, k)(spec, os.path.join(up, 'spec.json'), up, 'on')
    return spec


def produce(spec):
    """the produced references the QA reads (the outfit masks, the hair layers, the hull) made or restored in this tree
    (charkit.manifest.produce: from the shared cache when it has them), as a build makes them first."""
    from charkit import manifest
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        manifest.produce(copy.deepcopy(spec))


# ------------------------------------------------------------------------------------------------------------ splices
class _Arrays:
    """a bundle's arrays with some replaced or added (rep) and some left out (drop): what a spliced Bundle reads."""

    def __init__(self, base, rep, drop=()):
        self.b, self.rep = base, rep
        names = list(base.files) if hasattr(base, 'files') else list(base)
        self.files = [f for f in names if f not in set(drop)] + [k for k in rep if k not in names]

    def __contains__(self, k):
        return k in self.files

    def __getitem__(self, k):
        return self.rep[k] if k in self.rep else self.b[k]

    def __iter__(self):
        return iter(self.files)


def spliced(B0, rep, drop=()):
    """B0 with arrays replaced (rep) and dropped: a Bundle in memory (no path: drawn with numpy; no content hash)."""
    from charkit import bundle as bl
    meta = dict(B0._meta)
    meta.pop('content', None)
    meta.pop('hashes', None)
    return bl.Bundle(meta, _Arrays(B0._arrays, rep, drop), path=None)


def garment_arrays(B0, name, V, F, pmat=None):
    """an evaluator object's arrays in place of a bundle object's eval variant (the bow harnesses' splice, tool/pieceref
    var.py): V in the bundle's dtype, the polygons, a material slot per polygon (the evaluator's when it has one per
    polygon, else the base's commonest), UVs zeroed, the outline's inward move along each vertex's normal by
    |thickness| (1 + offset) / 2 (the Solidify's), the loop normals dropped -> (rep, drop)."""
    from charkit.garments import vertex_normals
    a = B0._arrays
    files = set(a.files if hasattr(a, 'files') else a)
    p = 'o/%s/eval/' % name
    Ve, Fe = np.asarray(V, float), np.asarray(F)
    rep = {p + 'V': Ve.astype(a[p + 'V'].dtype), p + 'loopv': Fe.ravel().astype(np.int32),
           p + 'counts': np.full(len(Fe), Fe.shape[1], np.int32)}
    pm0 = a[p + 'pmat']
    pmv = np.asarray(pmat if pmat is not None else [])
    rep[p + 'pmat'] = (pmv if len(pmv) == len(Fe) else np.full(len(Fe), np.bincount(pm0.astype(int)).argmax())
                       ).astype(pm0.dtype)
    if p + 'luv' in files:
        rep[p + 'luv'] = np.zeros((Fe.size, 2), np.float32)
    if p + 'shrink' in files:
        ol = B0.obj(name).outline or {}
        Tt = [(f[0], f[k], f[k + 1]) for f in Fe for k in range(1, len(f) - 1)]
        Nv = vertex_normals(Ve, Tt)
        Nv = Nv / np.maximum(np.linalg.norm(Nv, axis=1, keepdims=True), 1e-12)
        c0 = abs(float(ol.get('thickness') or 0.0)) * (1 + float(ol.get('offset', 1.0))) / 2
        shr = -Nv * c0
        from charkit.qa3d import is_ink
        ink = [k for k, m in enumerate(B0.obj(name).materials or []) if is_ink(m)]
        if ink and len(pmv) == len(Fe):
            # a piece's ink strokes (garments.with_ink) take no outline (their outline_w 0, as Blender draws them)
            shr[np.unique(Fe[np.isin(pmv, ink)])] = 0.0
        rep[p + 'shrink'] = shr.astype(np.float32)
    return rep, [p + 'lnor']


def hair_arrays(B0, name, V, T, vn=None):
    """a rebuilt hair piece's arrays in place of a bundle object's eval variant (tools/hair5/labart.py's splice): V, the
    triangles, slot 0, the loop normals from the piece's shading normals (the build sets them exactly), the outline's
    inward move along the angle-weighted vertex normal by |thickness| (1 + offset) / 2 -> (rep, drop)."""
    from charkit.geom.mesh import vertex_normals
    a = B0._arrays
    files = set(a.files if hasattr(a, 'files') else a)
    p = 'o/%s/eval/' % name
    V, T = np.asarray(V, float), np.asarray(T, np.int64)
    rep = {p + 'V': V.astype(np.float32), p + 'loopv': T.ravel().astype(np.int32),
           p + 'counts': np.full(len(T), 3, np.int32), p + 'pmat': np.zeros(len(T), np.int32)}
    drop = []
    if vn is not None:
        rep[p + 'lnor'] = np.asarray(vn, float)[T.ravel()].astype(np.float32)
    else:
        drop.append(p + 'lnor')
    if p + 'luv' in files:
        rep[p + 'luv'] = np.zeros((T.size, 2), np.float32)
    if p + 'shrink' in files:
        ol = B0.obj(name).outline or {}
        c0 = abs(float(ol.get('thickness') or 0.0014)) * (1 + float(ol.get('offset', 1.0))) / 2
        rep[p + 'shrink'] = (-vertex_normals(V, T) * c0).astype(np.float32)
    return rep, drop


# ------------------------------------------------------------------------------------------------------------- stages
class QAStage:
    """nothing rebuilt: every row measures the base bundle (variants patch the measurement)."""
    name = 'qa'

    def __init__(self, decl, B0, spec):
        self.decl, self.B0, self.spec = decl, B0, spec

    def objects(self, row, out):
        return {}

    def bundle(self, objs):
        return spliced(self.B0, {})


class GarmentStage(QAStage):
    """the fast evaluator at the row's spec (one Evaluator: the assembly, hair and unchanged garments cached), its
    garment and accessory objects spliced into the base bundle."""
    name = 'garments'
    GROUPS = ('garments', 'accessories')

    def __init__(self, decl, B0, spec):
        QAStage.__init__(self, decl, B0, spec)
        from charkit import bodyeval
        self.E = bodyeval.Evaluator(spec)

    def objects(self, row, out):
        G = self.E.geometry(spec=apply(self.spec, row['set']))
        Bd = G.bundle('viewport')
        have = {o.name for o in self.B0.objects(visible=False)}
        return {o['name']: dict(V=np.asarray(o['V'], float), F=np.asarray(o['F']), pmat=o.get('pmat'), kind='garment')
                for o in Bd['objects'] if o.get('role') != 'unmasked' and o['name'] in have and
                (o.get('group') in self.GROUPS or o['name'] in (self.decl.get('objects') or ()))}

    def bundle(self, objs):
        rep, drop = {}, []
        for n, o in objs.items():
            if not self.B0.has('o/%s/eval/V' % n):
                continue
            r, d = garment_arrays(self.B0, n, o['V'], o['F'], o.get('pmat'))
            rep.update(r)
            drop += d
        return spliced(self.B0, rep, drop)


class HairStage(QAStage):
    """the build's own hair pieces step (cli.pieces_hair, cached by file_step) at the row's spec into OUT/NAME/geom, its
    pieces spliced into the base bundle with their shading normals. A row with `style.hair_pieces.KEY` overrides runs
    the step uncached with the style profile patched."""
    name = 'hair'

    def objects(self, row, out):
        from charkit import cli
        from charkit.geom.io import load_npz
        spec = apply(self.spec, row['set'])
        style = {k[len(STYLE):]: v for k, v in row['set'].items() if k.startswith(STYLE)}
        os.makedirs(out, exist_ok=True)
        import io
        buf = io.StringIO()
        with _style_patch(style), contextlib.redirect_stdout(buf):
            S = cli.pieces_hair(spec, os.path.join(out, 'spec.json'), out, 'off' if style else 'on')
        row['step'] = next((l.split(' ', 2)[-1] for l in buf.getvalue().splitlines()
                            if l.startswith('CHARKIT_CACHE pieces_hair')), 'uncached' if style else None)
        pdir = S['hair']['shape']['pieces']
        index = json.load(open(os.path.join(pdir, 'pieces.json')))
        got = {}
        for p in index['pieces']:
            m = load_npz(os.path.join(pdir, p['file']))
            got['hair_' + p['name']] = dict(V=np.asarray(m.V, float), F=np.asarray(m.F, np.int64),
                                            vn=None if m.vn is None else np.asarray(m.vn, float), kind='hair')
        return got

    def bundle(self, objs):
        rep, drop = {}, []
        for n, o in objs.items():
            if not self.B0.has('o/%s/eval/V' % n):
                continue
            r, d = hair_arrays(self.B0, n, o['V'], o['F'], o.get('vn'))
            rep.update(r)
            drop += d
        return spliced(self.B0, rep, drop)


@contextlib.contextmanager
def _style_patch(over):
    """charkit.styles.load with the style profile's hair_pieces keys overridden for the block."""
    if not over:
        yield
        return
    from charkit import styles
    real = styles.load

    def load(name, *a, **kw):
        s = copy.deepcopy(real(name, *a, **kw))
        for k, v in over.items():
            ks = k.split('.')
            cur = s
            for x in ks[:-1]:
                cur = cur.setdefault(x, {})
            cur[ks[-1]] = v
        return s
    styles.load = load
    try:
        yield
    finally:
        styles.load = real


STAGE = {'qa': QAStage, 'garments': GarmentStage, 'hair': HairStage}


# ---------------------------------------------------------------------------------------------------------- measuring
@contextlib.contextmanager
def patched(over):
    """module attributes `qa:MODULE.NAME` (a dotted name under the module) set for the block."""
    import importlib
    old = []
    try:
        for k, v in (over or {}).items():
            if not k.startswith(QA_PATCH):
                continue
            mod, _, attr = k[len(QA_PATCH):].rpartition('.')
            m = importlib.import_module(mod)
            old.append((m, attr, getattr(m, attr)))
            setattr(m, attr, v)
        yield
    finally:
        for m, attr, v in reversed(old):
            setattr(m, attr, v)


def measure(B, parts, over=None):
    """the named QA parts on bundle B (as qa3d.evaluate runs them: the registry's order, qa.json's names, graded only
    against their authority) -> {check: dict}; a part that raises reports its skip key SKIPPED."""
    from charkit import qa3d, registry
    D = qa3d.Design(B)
    ref = B.spec.get('ref')
    ref_image = ref.get('image') if isinstance(ref, dict) else None
    out = {}
    with patched(over):
        for P in registry.parts():
            if P.name not in parts:
                continue
            try:
                _, C = P.fn(B, D, None, *((ref_image,) if P.ref_image else ()))
            except Exception as e:
                import traceback
                traceback.print_exc()
                out[P.skip_key] = {'status': 'SKIPPED', 'why': '%s: %s' % (type(e).__name__, e), 'part': P.name}
                continue
            for k, v in (C or {}).items():
                out[qa3d._check_name(P, k)] = dict(v, part=P.name) if isinstance(v, dict) else v
    try:
        from charkit import checks as checklib
        checklib.authorize(out, D.ref().get('authority') or {})
    except (ImportError, AttributeError):
        pass
    return out


def _plain(x):
    if isinstance(x, dict):
        return {str(k): _plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    if isinstance(x, np.ndarray):
        return _plain(x.tolist()) if x.size <= 64 else '<array %s>' % (x.shape,)
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, float) and x != x:
        return None
    return x if isinstance(x, (str, int, float, bool)) or x is None else str(x)


def kept(C, patterns=None):
    """the checks' readings worth keeping (KEEP fields; the shape checks always) -> {check: dict}."""
    out = {}
    for k, c in C.items():
        if not isinstance(c, dict):
            continue
        if patterns and not SHAPE_CHECK.match(k) and not any(fnmatch.fnmatchcase(k, p) for p in patterns):
            continue
        out[k] = _plain({f: c[f] for f in KEEP + ('part',) if f in c})
    return out


# --------------------------------------------------------------------------------------------------------------- run
def _head(path):
    try:
        r = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=path, capture_output=True, text=True)
        d = subprocess.run(['git', 'status', '--porcelain', '--', 'charkit'], cwd=path, capture_output=True, text=True)
        return r.stdout.strip() + ('+edits' if d.stdout.strip() else '')
    except OSError:
        return None


def _changed(a, b):
    """has an object's geometry changed between two rebuilds (or does only one have it)?"""
    if a is None or b is None:
        return True
    if a['V'].shape != b['V'].shape or a['F'].shape != b['F'].shape or not np.array_equal(a['F'], b['F']):
        return True
    return bool(np.abs(a['V'] - b['V']).max() > MOVED)


def _rows_for(decl, only=None, shard=None):
    rows = expand(decl)
    if only:
        keep = set(only)
        rows = [r for r in rows if r['name'] in keep or r.get('control')]
    if shard:
        i, n = shard
        rows = [r for k, r in enumerate(rows) if k % n == i]
    return rows


def run_rows(decl, rows, out, log=print):
    """the rows measured in this process -> [row dict]. The stage's context is made once; with no declared objects the
    spliced objects are those any row's rebuild changed against the control's (every row splices the same set)."""
    t0 = time.time()
    decl = dict(decl, _out=out)
    B0 = load_bundle(decl['base'], decl.get('rebase', True))
    spec = base_spec(decl, B0)
    produce(spec)
    S = STAGE[decl['stage']](decl, B0, spec)
    parts = list(dict.fromkeys(list(decl.get('parts') or ()) + list(decl.get('shape_parts', SHAPE_PARTS))))
    log('sweep: %s stage on %s, %d rows, parts %s (context %.0f s)' % (
        decl['stage'], decl['base'], len(rows), ','.join(parts), time.time() - t0))
    geo = {}
    for r in rows:
        t = time.time()
        geo[r['name']] = S.objects(r, os.path.join(out, _safe(r['name'])))
        r['seconds_build'] = round(time.time() - t, 1)
    names = decl.get('objects')
    if names is None and geo:
        ctrl = next((geo[r['name']] for r in rows if r.get('control')), None)
        if ctrl is None and decl.get('control', True):
            ctrl = S.objects(dict(name='control', set=dict(decl.get('set') or {})), os.path.join(out, 'control'))
        names = sorted({n for g in geo.values() for n in g if ctrl is None or _changed(g.get(n), ctrl.get(n))})
    names = list(names or ())
    done = []
    for r in rows:
        t = time.time()
        objs = {n: o for n, o in geo.pop(r['name']).items() if n in names}
        B = S.bundle(objs)
        C = measure(B, parts, r['set'])
        rec = dict(name=r['name'], set=_plain(r['set']), control=bool(r.get('control')), objects=sorted(objs),
                   seconds=round(r['seconds_build'] + time.time() - t, 1), checks=kept(C, decl.get('checks')),
                   step=r.get('step'))
        try:
            from charkit import qarender
            rec['drawn'] = qarender.drawn(B)
        except (ImportError, AttributeError):
            pass
        d = os.path.join(out, _safe(r['name']))
        os.makedirs(d, exist_ok=True)
        json.dump(rec, open(os.path.join(d, 'res.json'), 'w'), indent=1)
        if decl.get('boards'):
            try:
                board(B, d, **decl['boards'])
            except Exception as e:                      # (a picture is optional: the numbers stand)
                log('  board %s: %s: %s' % (r['name'], type(e).__name__, e))
        done.append(rec)
        log('  %-28s %5.1f s  %s' % (r['name'], rec['seconds'], _brief(rec['checks'], decl.get('checks'))))
    return done


def _safe(name):
    return re.sub(r'[^A-Za-z0-9._=,+-]', '_', name)[:120]


def _brief(C, patterns):
    got = [(k, c) for k, c in C.items() if not patterns or any(fnmatch.fnmatchcase(k, p) for p in patterns)]
    got = [(k, c) for k, c in got if not SHAPE_CHECK.match(k) or (patterns and any(
        fnmatch.fnmatchcase(k, p) for p in patterns))]
    return '  '.join('%s %s %s' % (k, _v(c.get('value')), (c.get('status') or '?')[0]) for k, c in got[:6])


def _v(x):
    return ('%.4g' % x) if isinstance(x, (int, float)) and not isinstance(x, bool) else str(x)


def run(decl, out, jobs=1, only=None, log=print):
    """a sweep: the rows (expand), measured in this process or in `jobs` processes (each in a build slot) -> the result
    (sweep.json's), written with sweep.md into out."""
    decl = load_decl(decl)
    out = _abs(out)
    os.makedirs(out, exist_ok=True)
    json.dump({k: v for k, v in decl.items() if not k.startswith('_')}, open(os.path.join(out, 'decl.json'), 'w'),
              indent=1)
    t0 = time.time()
    if jobs and jobs > 1:
        rows = _sharded(out, jobs, only, log)
    else:
        from charkit import procs
        lock = procs.acquire_slot('sweep')
        try:
            rows = run_rows(decl, _rows_for(decl, only), out, log)
        finally:
            lock.close()
    res = dict(decl={k: v for k, v in decl.items() if not k.startswith('_')}, code=root(), commit=_head(root()),
               started=time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(t0)), seconds=round(time.time() - t0, 1),
               rows=rows)
    res['guard'] = guard(res)
    json.dump(res, open(os.path.join(out, 'sweep.json'), 'w'), indent=1)
    md = table(res)
    open(os.path.join(out, 'sweep.md'), 'w').write(md)
    log(md)
    log('sweep: %s (%.0f s)' % (os.path.join(out, 'sweep.json'), time.time() - t0))
    return res


def _sharded(out, jobs, only, log):
    """the rows in `jobs` processes (sweep run OUT/decl.json --shard i/N), each in a build slot -> their rows in the
    declaration's order. With no declared objects each shard splices what its own rows changed against the control: a
    shard whose set isn't the union of all of them runs again with the union declared, so every row splices one set."""
    decl = json.load(open(os.path.join(out, 'decl.json')))

    def shards(which, path):
        ps = []
        for i in which:
            cmd = _self_cmd(['run', path, '--out', out, '--shard', '%d/%d' % (i, jobs)] +
                            (['--only', ','.join(only)] if only else []))
            logf = open(os.path.join(out, 'shard_%d.log' % i), 'w')
            ps.append((subprocess.Popen(cmd, cwd=root(), stdout=logf, stderr=subprocess.STDOUT), logf))
        for p, f in ps:
            p.wait()
            f.close()
        got = {}
        for i in which:
            p = os.path.join(out, 'shard_%d.json' % i)
            if os.path.exists(p):
                got[i] = json.load(open(p))
                os.remove(p)
            else:
                log('sweep: shard %d failed (%s)' % (i, os.path.join(out, 'shard_%d.log' % i)))
        return got
    got = shards(range(jobs), os.path.join(out, 'decl.json'))
    if decl.get('objects') is None:
        union = sorted({o for rows in got.values() for r in rows for o in r['objects']})
        again = [i for i, rows in got.items() if any(r['objects'] != union for r in rows)]
        if again:
            path = os.path.join(out, 'decl_objects.json')
            json.dump(dict(decl, objects=union), open(path, 'w'), indent=1)
            log('sweep: shards %s spliced other objects than the union %s: run again with it' % (again, union))
            got.update(shards(again, path))
    order = {r['name']: k for k, r in enumerate(expand(load_decl(decl)))}
    return sorted([r for rows in got.values() for r in rows], key=lambda r: order.get(r['name'], 1e9))


# ---------------------------------------------------------------------------------------------- the table and guard
def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _better_dir(check):
    """'higher' or 'lower' from the check's calibration record, else None."""
    try:
        from charkit import calibrate
        return (calibrate.records().get(check) or {}).get('better')
    except Exception:
        return None


def improved(c0, c1, better=None):
    """did a check improve from c0 to c1 (its grade or status better, or its value toward `better`)?"""
    s0, s1 = (c0 or {}).get('grade') or (c0 or {}).get('status'), (c1 or {}).get('grade') or (c1 or {}).get('status')
    if s0 in RANK and s1 in RANK and s0 != s1:
        return RANK[s1] < RANK[s0]
    v0, v1 = (c0 or {}).get('value'), (c1 or {}).get('value')
    if better and _num(v0) and _num(v1) and v0 != v1:
        return (v1 > v0) == (better == 'higher')
    return False


def shape_moves(c, r, eps=5e-4):
    """{shape check: {view: [control, row]}} for every shape check whose IoU moved more than eps in a view."""
    out = {}
    for k, x in r['checks'].items():
        if not SHAPE_CHECK.match(k):
            continue
        a, b = ((c['checks'].get(k) or {}).get('views') or {}), (x.get('views') or {})
        if not isinstance(a, dict) or not isinstance(b, dict):
            continue
        mv = {v: [a.get(v), b.get(v)] for v in sorted(set(a) | set(b))
              if (_num(a.get(v)) or _num(b.get(v))) and not (_num(a.get(v)) and _num(b.get(v)) and
                                                             abs(a[v] - b[v]) <= eps)}
        if mv:
            out[k] = mv
    return out


def guard(res, drop=None):
    """the anti-gaming guard per row against the control: a chosen check that improves while a shape check its
    calibration names (calibrate.shapes_of), or any piece the row spliced, drops by more than `drop` (calibrate.DROP)
    in a view -> [dict(row, check, shape, view, control, row_value, rel)]."""
    try:
        from charkit import calibrate
        drop = calibrate.DROP if drop is None else drop
        E = calibrate.entries()
    except Exception:
        calibrate, E = None, []
        drop = 0.15 if drop is None else drop
    rows = res['rows']
    ctrl = next((r for r in rows if r.get('control')), None)
    if ctrl is None:
        return []
    pats = res['decl'].get('checks')
    out = []
    for r in rows:
        if r is ctrl:
            continue
        mv = shape_moves(ctrl, r)
        for k, c in r['checks'].items():
            if SHAPE_CHECK.match(k) and not (pats and any(fnmatch.fnmatchcase(k, p) for p in pats)):
                continue
            if not improved(ctrl['checks'].get(k), c, _better_dir(k)):
                continue
            shapes = set()
            if calibrate is not None:
                qa = ({'checks': ctrl['checks']}, {'checks': r['checks']})
                shapes |= set(calibrate.shapes_of(k, E, qa))
            shapes |= {s for s in mv if any(s == 'piece_' + o or s == 'hair_piece_' + o[5:] for o in r['objects'])}
            for s in sorted(shapes):
                for view, (a, b) in (mv.get(s) or {}).items():
                    if _num(a) and _num(b) and a > 0.05 and (a - b) / a > drop:
                        out.append(dict(row=r['name'], check=k, shape=s, view=view, control=a, row_value=b,
                                        rel=round((b - a) / a, 3)))
    return out


def _cell(c, c0, show_delta=True):
    if not c:
        return '-'
    v, st = c.get('value'), c.get('grade') or c.get('status') or ''
    s = '%s %s' % (_v(v), st[:1] if st in RANK else st)
    if show_delta and c0 and _num(v) and _num(c0.get('value')) and v != c0['value']:
        s += ' (%+.4g)' % (v - c0['value'])
    return s


def table(res, patterns=None):
    """the result as markdown: the checks table (a delta against the control in each cell, flag checks [F]), the shape
    table (every piece's IoU per view that moved against the control), the guard."""
    rows = res['rows']
    ctrl = next((r for r in rows if r.get('control')), None)
    pats = patterns or res['decl'].get('checks')
    names = []
    for r in rows:
        for k in r['checks']:
            if k not in names and not SHAPE_CHECK.match(k) and (not pats or any(fnmatch.fnmatchcase(k, p) for p in pats)):
                names.append(k)
    if pats:
        names += [k for r in rows for k in r['checks'] if SHAPE_CHECK.match(k) and k not in names and
                  any(fnmatch.fnmatchcase(k, p) for p in pats)]
        names = list(dict.fromkeys(names))
    flag = {k for r in rows for k, c in r['checks'].items() if c.get('flag')}
    d = res['decl']
    L = ['# sweep: %s stage on %s' % (d.get('stage'), os.path.basename(str(d.get('base', '')).rstrip('/'))), '',
         'Base `%s`; code %s (%s); %d rows, %s s. Rows drawn with the numpy drawing; deltas against `%s`.' % (
             d.get('base'), res.get('commit'), res.get('code'), len(rows), res.get('seconds'),
             ctrl['name'] if ctrl else 'none'), '']
    hdr = ['row', 'overrides', 's'] + [k + (' [F]' if k in flag else '') for k in names]
    L += ['| ' + ' | '.join(hdr) + ' |', '|' + '---|' * len(hdr)]
    for r in rows:
        ov = ', '.join('%s=%s' % (k, _fmt(v)[:40]) for k, v in r['set'].items()
                       if not ctrl or ctrl['set'].get(k) != v) or ('(control)' if r.get('control') else '-')
        cells = [_cell(r['checks'].get(k), None if r is ctrl or not ctrl else ctrl['checks'].get(k)) for k in names]
        L.append('| ' + ' | '.join([r['name'], ov.replace('|', '/'), str(r.get('seconds'))] + cells) + ' |')
    L.append('')
    if ctrl:
        moved = {}
        for r in rows:
            if r is not ctrl:
                for s, mv in shape_moves(ctrl, r).items():
                    moved.setdefault(s, set()).update(mv)
        if moved:
            cols = [(s, v) for s in sorted(moved) for v in ('front', 'three_quarter', 'profile', 'back') if v in moved[s]]
            L += ['Shape IoU per view (the pieces that moved against the control; the anti-gaming guard\'s measure):', '',
                  '| row | ' + ' | '.join('%s %s' % (s, v) for s, v in cols) + ' |', '|' + '---|' * (len(cols) + 1)]
            for r in rows:
                cells = []
                for s, v in cols:
                    x = ((r['checks'].get(s) or {}).get('views') or {}).get(v)
                    x0 = ((ctrl['checks'].get(s) or {}).get('views') or {}).get(v)
                    cells.append('-' if not _num(x) else '%.4f' % x + (' (%+.4f)' % (x - x0) if r is not ctrl and
                                                                         _num(x0) and x != x0 else ''))
                L.append('| %s | %s |' % (r['name'], ' | '.join(cells)))
        else:
            L.append('Shape IoU: every piece within 0.0005 of the control in every view, in every row.')
        L.append('')
    G = res.get('guard') or []
    if G:
        L += ['**Guard:** %d row(s) improve a check while a piece\'s shape IoU drops more than %d%% in a view:' % (
            len({g['row'] for g in G}), 100 * 0.15), '']
        L += ['- %s: %s improves while %s %s %.3f -> %.3f (%+.1f%%)' % (g['row'], g['check'], g['shape'], g['view'],
                                                                       g['control'], g['row_value'], 100 * g['rel'])
              for g in G]
    else:
        L.append('Guard: no row improves a check while a piece\'s shape IoU drops more than 15% in a view.')
    return '\n'.join(L) + '\n'


# ---------------------------------------------------------------------------------------------------------- boards
def board(B, out, az=(0, 90), crop=None, pad=0.05, scale=None, name='board.png'):
    """the row's bundle drawn (qa3d.draw, numpy) from each azimuth, side by side; crop: an object's pixels and `pad` L
    round them (else the whole figure); scale: the frame's resolution over the QA's full-figure frame (default 4 with
    a crop, else 1) -> the PNG's path."""
    from PIL import Image
    from charkit import qa3d
    k = scale or (4 if crop else 1)
    zr = B.assembly.get('raw_z') or qa3d.figure_frame(B).zc + np.array([-0.5, 0.5]) * qa3d.figure_frame(B).scale / 1.08
    fr = qa3d.Frame(float(zr[0]), float(zr[1]), res=(qa3d.FRAME[0] * k, qa3d.FRAME[1] * k), ss=1)
    surfs, owner = [], []
    for o in B.objects():
        if o.has('eval'):
            got = qa3d.surfaces(B, o, 'masked' if o.group == 'skin' and o.has('masked') else 'eval')
            surfs += got
            owner += [o.name] * len(got)
    tiles = []
    L = float(B.assembly['L'])
    for a in az:
        aux = {}
        px = qa3d.draw(B, surfs, a, fr, ss=1, aux=aux)
        al = px[..., 3:4]
        img = (np.clip(px[..., :3] * al + (1 - al), 0, 1) * 255).astype(np.uint8)      # (on white)
        if crop:
            mesh = qa3d._to_shape(aux['mesh'], img.shape[:2]) if 'mesh' in aux else None
            idx = [i for i, n in enumerate(owner) if n == crop]
            if mesh is not None and idx:
                m = np.isin(mesh, idx)
                if m.any():
                    rs, cs = np.nonzero(m)
                    p = int(round(pad * L / fr.pix))
                    img = img[max(0, rs.min() - p):rs.max() + p + 1, max(0, cs.min() - p):cs.max() + p + 1]
        tiles.append(img)
    h = max(t.shape[0] for t in tiles)
    row = np.concatenate([np.pad(t, ((0, h - t.shape[0]), (0, 4), (0, 0)), constant_values=255) for t in tiles], 1)
    path = os.path.join(out, name)
    Image.fromarray(row).save(path)
    return path


# ------------------------------------------------------------------------------------------------------- swap mode
def kabsch(A, B):
    """the rotation taking A's shape onto B's (both centred) -> (angle deg, residual max)."""
    a, b = A - A.mean(0), B - B.mean(0)
    U, _, Vt = np.linalg.svd(a.T @ b)
    d = np.sign(np.linalg.det(U @ Vt))
    R = (U @ np.diag([1, 1, d]) @ Vt).T
    ang = float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))
    return ang, float(np.linalg.norm(a @ R.T - b, axis=1).max())


def moves(BA, BB, groups=None):
    """how far each object moved between two bundles (tools/bunorient/pairmove.py): per object both have, with the same
    vertex count, its largest vertex move, its centroid's and its rigid rotation (deg), in L -> {name: dict}."""
    L = float(BA.assembly['L'])
    na = {o.name: o for o in BA.objects(visible=False) if groups is None or o.group in groups}
    nb = {o.name: o for o in BB.objects(visible=False) if groups is None or o.group in groups}
    out = {}
    for n in sorted(set(na) | set(nb)):
        if n not in na or n not in nb:
            out[n] = dict(only='A' if n in na else 'B')
            continue
        if not (na[n].has('eval') and nb[n].has('eval')):
            continue
        Va, Vb = np.asarray(na[n].V(), float), np.asarray(nb[n].V(), float)
        if len(Va) != len(Vb):
            out[n] = dict(verts=[len(Va), len(Vb)])
            continue
        mv = float(np.linalg.norm(Va - Vb, axis=1).max()) / L
        r = dict(max_move_L=float('%.3g' % mv))
        if mv > 1e-9 and len(Va) >= 3:
            ang, res_ = kabsch(Va, Vb)
            r.update(rot_deg=round(ang, 4), centroid_L=float('%.3g' % (np.linalg.norm(Va.mean(0) - Vb.mean(0)) / L)),
                     nonrigid_L=float('%.3g' % (res_ / L)))
        out[n] = r
    return out


def owner_part(build, check):
    """the QA part that reports a check (the build's qa.json measured.part_checks) or None."""
    p = os.path.join(build, 'qa', 'qa.json')
    if not os.path.exists(p):
        return None
    owned = (json.load(open(p)).get('measured') or {}).get('part_checks') or {}
    return next((part for part, ks in owned.items() if check in ks), None)


def _with(B0, objs_from=None, names=(), drop=()):
    """B0 (drawn with numpy) with the named objects taken from objs_from's bundle (added when B0 lacks them) and the
    `drop` objects left out: a shallow copy, B0 itself untouched."""
    from charkit import bundle as bl
    B = bl.Bundle(B0._meta, B0._arrays, path=None)
    B._loaded = B0._loaded
    for n in names:
        B._objs[n] = objs_from.obj(n) if n in objs_from._objs else None
    for n in list(names) + list(drop):
        if B._objs.get(n) is None or n in drop:
            B._objs.pop(n, None)
    return B


def _value(C, check):
    c = C.get(check) or {}
    return c.get('value'), {k: c[k] for k in ('views', 'ratio', 'per_view', 'status', 'grade', 'worst') if k in c}


def swap(a, b, check, part=None, objects=None, groups=('hair', 'garment', 'accessory'), drop=False, inputs=(),
         stage=None, out=None, extra=(), rebase=True, log=print):
    """which object (or input) carries a check's move from build a to build b (see the module doc) -> the result
    (OUT/swap.json, OUT/swap.md)."""
    t0 = time.time()
    part = part or owner_part(a, check) or owner_part(b, check)
    if not part:
        raise SystemExit('swap: no QA part reports %s in either build (--part PART)' % check)
    parts = [part] + [p for p in extra if p != part]
    BA, BB = load_bundle(a, rebase), load_bundle(b, rebase)
    produce(copy.deepcopy(BB._meta.get('spec') or {}))
    names_a = {o.name: o for o in BA.objects(visible=False)}
    names_b = {o.name: o for o in BB.objects(visible=False)}
    pool = sorted(n for n in set(names_a) | set(names_b)
                  if ((names_a.get(n) or names_b.get(n)).group in groups if groups else True) and
                  (not objects or any(fnmatch.fnmatchcase(n, p) for p in objects)))
    rows = []

    def one(name, B, kind, obj=None):
        t = time.time()
        C = measure(B, parts)
        v, extra_ = _value(C, check)
        rows.append(dict(name=name, kind=kind, object=obj, value=v, seconds=round(time.time() - t, 1), **extra_))
        log('  %-34s %s %s' % (name, _v(v), extra_.get('ratio') or extra_.get('views') or extra_.get('per_view') or ''))
    from charkit import procs
    lock = procs.acquire_slot('sweep')
    try:
        one('A', _with(BA), 'build')
        one('B', _with(BB), 'build')
        for n in pool:
            if n in names_b:
                one('A + B.%s' % n, _with(BA, BB, [n]), 'object', n)
            if n in names_a:
                one('B + A.%s' % n, _with(BB, BA, [n]), 'object', n)
            elif n in names_b:
                one('B - %s' % n, _with(BB, drop=[n]), 'object', n)
            if drop and n in names_b and n in names_a:
                one('A - %s' % n, _with(BA, drop=[n]), 'drop', n)
                one('B - %s' % n, _with(BB, drop=[n]), 'drop', n)
    finally:
        lock.close()
    va, vb = rows[0]['value'], rows[1]['value']
    for r in rows[2:]:
        own = va if r['name'].startswith('A ') else vb
        r['delta'] = round(r['value'] - own, 4) if _num(r['value']) and _num(own) else None
        r['carries'] = _carry(r, va, vb) if r['kind'] == 'object' else None
    res = dict(A=a, B=b, check=check, part=part, commit=_head(root()), moves=moves(BA, BB, groups or None),
               rows=rows)
    if inputs:
        res['inputs'] = swap_inputs(a, b, check, parts, inputs, stage, out, rebase, log)
    res['seconds'] = round(time.time() - t0, 1)
    if out:
        out = _abs(out)
        os.makedirs(out, exist_ok=True)
        json.dump(_plain(res), open(os.path.join(out, 'swap.json'), 'w'), indent=1)
        open(os.path.join(out, 'swap.md'), 'w').write(swap_table(res))
    log(swap_table(res))
    return res


def _carry(r, va, vb):
    """the share of the A -> B move a swap row carries: A + B.x moves A by (v - vA) of (vB - vA); B + A.x and B - x
    take (vB - v) of it back."""
    v = r['value']
    if not (_num(v) and _num(va) and _num(vb)) or vb == va:
        return None
    return round(((v - va) if r['name'].startswith('A ') else (vb - v)) / (vb - va), 3)


def swap_inputs(a, b, check, parts, inputs, stage, out, rebase=True, log=print):
    """B's spec with A's value at each input path (or a given VALUE), rebuilt at the stage and measured: a sweep on B
    (the control: B's own inputs through the same stage) -> its result."""
    BA = load_bundle(a, rebase)
    sa = BA._meta.get('spec') or {}
    variants = {}
    for x in inputs:
        path, eq, val = x.partition('=')
        if eq:
            v = json.loads(val) if val[:1] in '[{"0123456789-tfn' else val
        else:
            v = _get(sa, path)
            if path in ('head_code', 'body_code'):
                p = os.path.join(a, 'geom', path + '.npz')
                v = p if os.path.exists(p) else v
        variants['B+A.%s' % path] = {path: v}
    st = stage or ('hair' if all(p.split('=')[0].startswith(('hair.', 'head_code')) for p in inputs) else 'garments')
    decl = dict(base=b, stage=st, variants=variants, parts=list(parts), checks=[check], rebase=rebase)
    return run(decl, os.path.join(_abs(out or os.path.join(home(), 'charkit', 'out', 'sweep', 'swap')), 'inputs'),
               log=log)


def _get(spec, path):
    cur = spec
    for k in path.split('.'):
        if isinstance(cur, list):
            cur = cur[_item(cur, k)]
        elif isinstance(cur, dict):
            cur = cur.get(k)
        else:
            return None
    return cur


def swap_table(res):
    rows = res['rows']
    L = ['# swap: %s (part %s)' % (res['check'], res['part']), '',
         'A `%s` (before), B `%s` (after); code %s. Drawn with the numpy drawing. "carries": the share of the A -> B '
         'move a swap makes (A + B.x) or takes back (B + A.x); "delta": against the row\'s own build.' % (
             res['A'], res['B'], res.get('commit')), '',
         '| row | value | delta | carries | per view |', '|---|---|---|---|---|']
    order = rows[:2] + sorted([r for r in rows[2:] if r.get('kind') == 'object'],
                              key=lambda r: -abs(r.get('carries') or 0)) + [r for r in rows[2:] if r.get('kind') != 'object']
    for r in order:
        pv = r.get('ratio') or r.get('views') or r.get('per_view') or {}
        L.append('| %s | %s | %s | %s | %s |' % (
            r['name'], _v(r['value']), '-' if r.get('delta') is None else '%+.4g' % r['delta'],
            '-' if r.get('carries') is None else '%+.0f%%' % (100 * r['carries']),
            ', '.join('%s %s' % (k, _v(x)) for k, x in pv.items()) if isinstance(pv, dict) else pv))
    mv = {n: m for n, m in (res.get('moves') or {}).items() if m.get('max_move_L', 1) > 1e-6 or 'verts' in m or
          'only' in m}
    if mv:
        L += ['', 'Objects that differ between the builds (largest vertex move, L; rigid rotation, deg):', '']
        L += ['- %s: %s' % (n, ', '.join('%s %s' % kv for kv in m.items())) for n, m in sorted(mv.items())]
    if res.get('inputs'):
        L += ['', '## Inputs swapped (B rebuilt with A\'s input)', '', table(res['inputs'])]
    return '\n'.join(L) + '\n'


# --------------------------------------------------------------------------------------------------------------- CLI
def _opts(args, key):
    out, i = [], 0
    while i < len(args):
        if args[i] == key and i + 1 < len(args):
            out.append(args[i + 1])
            i += 2
        else:
            i += 1
    return out


def _opt(args, key, d=None):
    return args[args.index(key) + 1] if key in args and args.index(key) + 1 < len(args) else d


def _kv(x):
    k, _, v = x.partition('=')
    try:
        return k, json.loads(v)
    except ValueError:
        return k, v


def inline_decl(args):
    """the inline form's flags as a declaration."""
    d = dict(base=_abs(args[0]), stage=_opt(args, '--stage', 'qa'))
    if _opt(args, '--spec'):
        d['spec'] = _opt(args, '--spec')
    if _opts(args, '--set'):
        d['set'] = dict(_kv(x) for x in _opts(args, '--set'))
    if _opts(args, '--variant'):
        d['variants'] = {}
        for x in _opts(args, '--variant'):
            n, over = _kv(x)
            d['variants'][n] = over
    for k in ('grid', 'oat'):
        if _opts(args, '--' + k):
            d[k] = dict(_kv(x) for x in _opts(args, '--' + k))
            bad = [p for p, v in d[k].items() if not isinstance(v, list)]
            if bad:
                raise SystemExit('sweep --%s %s: give a JSON list of values (PATH=[v1,v2]); one value: --set, a '
                                 'named row: --variant NAME=\'{"PATH": value}\'' % (k, bad[0]))
    for k in ('parts', 'checks', 'objects'):
        if _opt(args, '--' + k):
            d[k] = [x for x in _opt(args, '--' + k).split(',') if x]
    if '--no-control' in args:
        d['control'] = False
    if '--no-rebase' in args:
        d['rebase'] = False
    return d


BOOT = ('import os, runpy, sys; r = os.environ["CHARKIT_SWEEP_CODE"]; sys.path.insert(0, r); os.chdir(r); '
        'f = sys.argv[1]; sys.argv = [f] + sys.argv[2:]; runpy.run_path(f, run_name="__main__")')


def _self_cmd(args):
    """the command that runs this sweep with args: `python -m charkit sweep`, or under --code this file by path with
    the other tree's charkit (the environment carries CHARKIT_SWEEP_CODE)."""
    if os.environ.get('CHARKIT_SWEEP_CODE'):
        return [sys.executable, '-c', BOOT, os.path.abspath(__file__)] + list(args)
    return [sys.executable, '-m', 'charkit', 'sweep'] + list(args)


def _recode(args):
    """--code ROOT: this command again with ROOT's charkit (this file run by path, ROOT first on sys.path, from ROOT);
    relative paths still name the caller's (CHARKIT_SWEEP_CWD), and outputs default to the caller's tree."""
    i = args.index('--code')
    code = _abs(args[i + 1])
    rest = args[:i] + args[i + 2:]
    env = dict(os.environ, CHARKIT_SWEEP_CODE=code, CHARKIT_SWEEP_CWD=os.environ.get('CHARKIT_SWEEP_CWD') or
               os.getcwd(), CHARKIT_SWEEP_HOME=home())
    return subprocess.run([sys.executable, '-c', BOOT, os.path.abspath(__file__)] + rest, cwd=code, env=env).returncode


def _box(args):
    """--box [NAME]: this command on the box (remote run --fetch OUT), its outputs fetched."""
    from charkit import remote
    i = args.index('--box')
    name = args[i + 1] if i + 1 < len(args) and not args[i + 1].startswith('-') else None
    rest = args[:i] + args[i + (2 if name else 1):]
    out = _opt(rest, '--out')
    if not out:
        raise SystemExit('sweep --box: give --out (a folder under this worktree, fetched back when it ends)')
    rel = os.path.relpath(_abs(out), root())
    rest = [rel if x == out else os.path.relpath(_abs(x), root()) if x.endswith('.json') and os.path.exists(x) else x
            for x in rest]
    return remote.main((['--box', name] if name else []) + ['run', '--fetch', rel, 'sweep'] + rest)


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    if '--code' in args:
        return _recode(args)
    if '--box' in args:
        return _box(args)
    cmd = args[0]
    jobs = int(_opt(args, '--jobs', 1))
    if cmd == 'table':
        res = json.load(open(_abs(args[1])))
        print(table(res, [x for x in (_opt(args, '--checks') or '').split(',') if x] or None))
        return 0
    if cmd == 'swap':
        out = _opt(args, '--out') or os.path.join(home(), 'charkit', 'out', 'sweep', 'swap_%s' % time.strftime('%m%d-%H%M%S'))
        swap(_abs(args[1]), _abs(args[2]), _opt(args, '--check'), part=_opt(args, '--part'),
             objects=[x for x in (_opt(args, '--objects') or '').split(',') if x] or None,
             groups=tuple(x for x in (_opt(args, '--groups') or 'hair,garment,accessory').split(',') if x),
             drop='--drop' in args, inputs=[x for x in (_opt(args, '--inputs') or '').split(',') if x],
             stage=_opt(args, '--stage'), out=out,
             extra=[x for x in (_opt(args, '--parts') or '').split(',') if x], rebase='--no-rebase' not in args)
        return 0
    if cmd == 'run':
        decl = load_decl(args[1])
        out = _opt(args, '--out') or os.path.join(home(), 'charkit', 'out', 'sweep',
                                                  os.path.splitext(os.path.basename(args[1]))[0])
        only = [x for x in (_opt(args, '--only') or '').split(',') if x] or None
        if _opt(args, '--shard'):
            i, n = (int(x) for x in _opt(args, '--shard').split('/'))
            from charkit import procs
            lock = procs.acquire_slot('sweep')
            try:
                rows = run_rows(decl, _rows_for(decl, only, (i, n)), _abs(out))
            finally:
                lock.close()
            json.dump(rows, open(os.path.join(_abs(out), 'shard_%d.json' % i), 'w'), indent=1)
            return 0
        run(decl, out, jobs=jobs, only=only)
        return 0
    decl = inline_decl(args)
    out = _opt(args, '--out') or os.path.join(home(), 'charkit', 'out', 'sweep', 'sweep_%s' % time.strftime('%m%d-%H%M%S'))
    run(decl, out, jobs=jobs)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]) or 0)
