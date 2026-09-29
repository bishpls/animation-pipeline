"""charkit's command line (run with the venv's python, which has PIL; Blender is called for the scene):

    python -m charkit build SPEC.json [--out DIR] [--boards views,body,expressions,mouths] [--no-blend] [--no-fit] [--no-qa] [--vrm]
                                     [--base makehuman|anime] [--hair geom|mesh] [--note JSON] [--qa venv|blender]
                                     [--cache on|off|refresh|stages|verify] [--no-cache] [--no-worker]
    python -m charkit qa OUT/bundle [--out OUT/qa] [--cache on|off|refresh]   # the QA on a build's geometry bundle
    python -m charkit export BUILD.blend [--out OUT.vrm] [--subdiv 2]
    python -m charkit refs RIG_DIR OUT.json [--eye-x 0.168]
    python -m charkit trace OUT/trace.jsonl [OTHER/trace.jsonl] [--no-time]  # a build's state log, or what changed
    python -m charkit worker start | stop | status                  # a live Blender that takes build jobs
    python -m charkit cache [info | clear]                          # the build cache (charkit/out/.cache)
    python -m charkit gate BRANCH [--into REF] [--args "--base anime"] # what merging BRANCH would do, measured first
    python -m charkit history NAME [--check CHECK]                     # QA across builds
    python -m charkit ps | kill OUT_DIR | wait OUT_DIR                 # running builds, by their own records
    python -m charkit slots [N]                                        # the machine's concurrent Blender builds
    python -m charkit tune SPEC [--out DIR] [--budget N|Nm] [--review]   # fit, build, check, triage (charkit/tune.py)
    python -m charkit triage DIR                                       # the residual checks as ranked work items
    python -m charkit review board|serve|note|ticket|tickets ...       # the human review checkpoint (charkit/review.py)
    python -m charkit refs-check SPEC                                  # the character's references (ref.manifest)
    python -m charkit refcheck SPEC [--refs A,B] [--no-open]           # generated head sheets against the model sheet
    python -m charkit checkpoint SPEC --build LABEL=DIR ... [--decisions F.md]  # the checkpoint review page
    python -m charkit fit SPEC.json [--out DIR] [--base anime] [--only eyes|face] [--budget N] [--views] [--verify]
                                    [--write-spec]                     # the face, eye and neck knobs from the QA
                                                                       # (charkit/facefit.py; build takes DIR/NAME.fit.json)
    python -m charkit figures SPEC [--write]     # find the model sheet's figures; check (or write) the manifest's boxes
    python -m charkit bodyeval SPEC [--knob PATH=VALUE] | --validate BUILD   # the fast numpy body/garment/hair evaluator
    python -m charkit bodysens SPEC [--only body,garments,hair]        # every body/garment/hair knob's silhouette effect
    python -m charkit bodyfit SPEC [--pieces figure,details,hair] [--palette] [--write-spec]   # fit them to the model sheet
    python -m charkit outfit SPEC [--out DIR] [--field FIELD.npz] [--no-field] [--notes NOTES.json] [--no-manifest]
                                                 # the outfit component graph from the references (charkit/outfit.py)

build writes out/trace.jsonl as it goes (charkit/trace.py): every stage's objects, geometry hashes, mesh health, landmarks
and timings. build: 1) measures the spec's design reference (spec.ref.rig, a 2D rig's layers) and fits knobs into a resolved spec
(out/NAME.spec.json; knobs the spec sets itself are kept), 2) builds the scene in Blender, renders the boards and saves
out/NAME.blend, 3) composes review sheets next to the reference image (spec.ref.image): out/sheet_views.png,
out/sheet_body.png, out/sheet_face.png. --vrm also writes out/NAME.vrm (charkit/gltf.py). --base overrides the spec's base
mesh (spec['base']: 'makehuman', the default, wraps MakeHuman's own head; 'anime' builds on charkit's derived anime base,
charkit/base_anime.py). With hair.shape.mode 'geom' (or --hair geom) the generated hair is cut out venv-side by
charkit.geom first (out/geom/hair.npz) and the Blender stage loads that closed surface (docs/GEOM.md).

The build cache (charkit/cache.py, docs/CHARKIT.md §3): each stage (the cranium fit, character, hair, face shading,
garments) is restored instead of run when nothing it read has changed (the spec keys, the earlier stages' values and
objects, the files and the code it read, recorded as it ran), and so are the boards, the QA and the VRM when the whole
scene is. The trace says per stage what was restored and, for what ran, why (`python -m charkit trace OUT/trace.jsonl`).
--cache off builds without it (--no-cache too); refresh runs and stores everything; stages restores the stages but renders
the boards and runs the QA afresh; verify runs everything and flags any step that differs from the entry a lookup would
have restored (CHARKIT_CACHE_STALE). The geom hair cut is cached the same way, venv-side.

The QA (docs/CHARKIT.md §4): Blender builds and exports the geometry bundle (out/bundle, charkit/bundle.py); the venv
measures it (charkit/qa3d.py, numba z-buffers, no Blender): out/qa/qa.json and the overlays, each QA part cached on what
it read of the bundle and its code. --qa blender runs the old Blender-side pass instead (charkit/qa3d_blender.py).

The build worker (charkit/worker.py): `worker start` keeps one Blender running with charkit loaded; build sends its job
there when it runs (a clean scene and freshly imported code per job) and starts a fresh Blender otherwise or with
--no-worker. Its process is recorded in charkit/out/worker (`ps`, `kill`), each job in its out folder.

export: a saved build (.blend) to our glTF 2.0 / VRM 1.0 with the OPENADS_charkit_look extension (charkit/gltf.py), checked
on the way out; engine/three/charkit/look.js renders it, projects/charkit-look inspects it and boards it against Blender.
"""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLENDER = os.environ.get('BLENDER', '/Applications/Blender.app/Contents/MacOS/Blender')


def _path(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def resolve(spec_path, out, do_fit=True, base=None):
    from . import refs
    from . import manifest
    spec = manifest.produce(manifest.resolve(json.load(open(spec_path))))
    if base:
        spec['base'] = base
    ref = spec.get('ref', {})
    if do_fit and isinstance(ref, dict) and ref.get('rig'):
        R = refs.measure(_path(ref['rig']), spec.get('eyes', {}).get('x', 0.168))
        c = refs.sheet_chin(spec, R)
        if c is not None:
            R['chin_sheet'] = c
        json.dump(R, open(os.path.join(out, 'ref_measure.json'), 'w'), indent=1)
        spec = refs.fit(spec, R, ref.get('fit', ('face', 'features', 'hair')))
    p = os.path.join(out, spec['name'] + '.spec.json')
    json.dump(spec, open(p, 'w'), indent=1)
    return spec, p


def _ref_image(spec):
    from PIL import Image
    ref = spec.get('ref', {})
    img = ref.get('image') if isinstance(ref, dict) else None
    if not img or not os.path.exists(_path(img)):
        return None
    a = Image.open(_path(img)).convert('RGBA')
    bg = Image.new('RGBA', a.size, (235, 235, 240, 255)); bg.alpha_composite(a)
    return bg.convert('RGB'), a


def _trim(im, pad=12):
    """a picture cut to what differs from its corner colour (the figure), with a margin."""
    import numpy as np
    a = np.asarray(im.convert('RGB')).astype(int)
    bg = a[:4, :4].reshape(-1, 3).mean(0)
    ys, xs = np.nonzero(np.abs(a - bg).sum(-1) > 30)
    if not len(ys):
        return im
    return im.crop((max(0, xs.min() - pad), max(0, ys.min() - pad), min(im.width, xs.max() + pad), min(im.height, ys.max() + pad)))


def _labelled_grid(rows, tile_h, labels):
    """rows of PIL pictures, each scaled to tile_h high, under a label per column -> one picture."""
    from PIL import Image, ImageDraw
    rows = [[im.resize((max(1, int(im.width * tile_h / im.height)), tile_h)) if im is not None else None for im in r] for r in rows]
    cols = max(len(r) for r in rows)
    cw = [max((r[c].width for r in rows if c < len(r) and r[c] is not None), default=tile_h // 2) for c in range(cols)]
    lab = 28
    S = Image.new('RGB', (sum(cw) + 10 * (cols + 1), len(rows) * (tile_h + lab) + 10), 'white')
    d = ImageDraw.Draw(S)
    for ri, r in enumerate(rows):
        x = 10
        for c in range(cols):
            y = 10 + ri * (tile_h + lab)
            d.text((x, y), labels[ri][c] if c < len(labels[ri]) else '', fill=(60, 60, 60))
            if c < len(r) and r[c] is not None:
                S.paste(r[c], (x + (cw[c] - r[c].width) // 2, y + lab - 6))
            x += cw[c] + 10
    return S


def generated_sheets(spec, out):
    """the review sheets from the generated references (spec.ref.face_sheet, body_sheet: the design's sheets since
    2026-09-28): out/sheet_views.png (the head turnaround's heads over our face boards at the matching angles) and
    out/sheet_body.png (the body turnaround's figures over our body boards), each figure cut to its outline and scaled to
    one height. -> the paths made."""
    import numpy as np
    from PIL import Image
    from . import eyes as eyelib, refcheck, sheetqa
    ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else {}
    ex = eyelib._knobs(spec.get('eyes'))['x']
    b = os.path.join(out, 'boards')
    made = []
    fs = ref.get('face_sheet')
    views = {a: os.path.join(b, 'face_%03d.png' % a) for a in (0, 30, 60, 90, 150)}
    if fs and all(os.path.exists(p) for p in views.values()):
        rgb0 = refcheck._load(fs['image'])
        clean, _ = refcheck.without_guides(rgb0)
        rgb, f, H = refcheck.at_scale(clean, ex, 2 * ex * refcheck.FACE_PPL, fs.get('facing', -1))
        az3 = refcheck.face_design(rgb0, ex).get('az_three_quarter', 35.0)
        pick = {'front': 0, 'three_quarter': min((30, 60), key=lambda a: abs(a - az3)), 'profile': 90}
        full = Image.fromarray((np.clip(rgb0, 0, 1) * 255).astype(np.uint8))
        top, bottom, la, lb = [], [], [], []
        for v, a in pick.items():
            if v not in H['heads']:
                continue
            x0, y0, x1, y1 = (int(round(c / f)) for c in H['heads'][v]['head'])
            top.append(full.crop((x0, y0, x1, y1))); la.append('%s: %s' % (fs['id'], v.replace('_', '-')))
            bottom.append(Image.open(views[a]).convert('RGB')); lb.append('ours: face %d deg' % a)
        p = os.path.join(out, 'sheet_views.png')
        _labelled_grid([top, bottom], 420, [la, lb]).save(p); made.append(p)
    bs = ref.get('body_sheet')
    body = {'front': 0, 'three_quarter': 35, 'profile': 90, 'back': 180}
    paths = {v: os.path.join(b, 'body_%03d.png' % a) for v, a in body.items()}
    if bs and all(os.path.exists(p) for p in paths.values()):
        rgb = refcheck._load(bs['image'])
        D = sheetqa.detect_figures(rgb, None, ex, bs.get('facing', -1))
        full = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
        top, bottom, la, lb = [], [], [], []
        for v, a in body.items():
            if v not in D['figures']:
                continue
            x0, y0, x1, y1 = D['figures'][v]['box']
            top.append(_trim(full.crop((x0, y0, x1, y1)))); la.append('%s: %s' % (bs['id'], v.replace('_', '-')))
            bottom.append(_trim(Image.open(paths[v]).convert('RGB'))); lb.append('ours: body %d deg' % a)
        p = os.path.join(out, 'sheet_body.png')
        _labelled_grid([top, bottom], 900, [la, lb]).save(p); made.append(p)
    return made


def sheets(spec, out):
    import numpy as np
    from PIL import Image
    ref0 = spec.get('ref') if isinstance(spec.get('ref'), dict) else {}
    if ref0.get('face_sheet') or ref0.get('body_sheet'):
        made = generated_sheets(spec, out)
        done = {os.path.basename(p) for p in made}
    else:
        made, done = [], set()
    b = os.path.join(out, 'boards')
    ref = _ref_image(spec)
    views = [os.path.join(b, f'face_{a:03d}.png') for a in (0, 30, 60, 90, 150)]
    if 'sheet_views.png' not in done and all(os.path.exists(p) for p in views):
        ims = [Image.open(p).convert('RGB').resize((400, 400)) for p in views]
        head = None
        if ref:
            rgb, a = ref
            al = np.array(a)[..., 3]; ys, xs = np.nonzero(al > 10)
            h = int((ys.max() - ys.min()) * 0.30)                     # the head: the top ~30% of the figure
            cx = (xs.min() + xs.max()) // 2
            head = rgb.crop((cx - h * 0.62, ys.min(), cx + h * 0.62, ys.min() + h)).resize((500, 400))
        W = (500 if head else 0) + 2000
        S = Image.new('RGB', (W, 400), 'white')
        if head:
            S.paste(head, (0, 0))
        for i, im in enumerate(ims):
            S.paste(im, ((500 if head else 0) + i * 400, 0))
        p = os.path.join(out, 'sheet_views.png'); S.save(p); made.append(p)
    body = [os.path.join(b, f'body_{a:03d}.png') for a in (0, 35, 90, 180)]
    if 'sheet_body.png' not in done and all(os.path.exists(p) for p in body):
        ims = [Image.open(p).convert('RGB') for p in body]
        left = None
        if ref:
            rgb, a = ref
            al = np.array(a)[..., 3]; ys, xs = np.nonzero(al > 10)
            r = rgb.crop((0, max(0, ys.min() - 40), rgb.width, min(rgb.height, ys.max() + 40)))
            left = r.resize((int(r.width * 1000 / r.height), 1000))
        W = (left.width if left else 0) + 600 * len(ims)
        S = Image.new('RGB', (W, 1000), 'white')
        if left:
            S.paste(left, (0, 0))
        for i, im in enumerate(ims):
            S.paste(im, ((left.width if left else 0) + i * 600, 0))
        p = os.path.join(out, 'sheet_body.png'); S.save(p); made.append(p)
    from .scene import EXPR, MOUTH
    ex = [os.path.join(b, f'expr_{e}.png') for e in EXPR]; mo = [os.path.join(b, f'mouth_{m}.png') for m in MOUTH]
    if all(os.path.exists(p) for p in ex + mo):
        S = Image.new('RGB', (max(257 * len(ex), 180 * len(mo)), 257 + 180), 'white')
        for i, p in enumerate(ex):
            S.paste(Image.open(p).convert('RGB').resize((257, 257)), (i * 257, 0))
        for i, p in enumerate(mo):
            S.paste(Image.open(p).convert('RGB').resize((180, 180)), (i * 180, 257))
        p = os.path.join(out, 'sheet_face.png'); S.save(p); made.append(p)
    return made


def build(args):
    spec_path = args[0]
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    name = json.load(open(spec_path))['name']
    out = _path(opt('--out', f'charkit/out/{name}'))
    os.makedirs(out, exist_ok=True)
    spec, resolved = resolve(spec_path, out, do_fit='--no-fit' not in args, base=opt('--base'))
    if opt('--hair') and (spec.get('hair') or {}).get('shape'):
        spec['hair']['shape']['mode'] = opt('--hair')
        json.dump(spec, open(resolved, 'w'), indent=1)
    mode = opt('--cache', 'off' if '--no-cache' in args else 'on')
    spec = code_head(spec, resolved, out, mode)
    spec = geom_hair(spec, resolved, out, mode)
    boards = opt('--boards', 'views,body,expressions,mouths')
    qa = None if '--no-qa' in args else opt('--qa', 'venv')
    if qa not in (None, 'venv', 'blender'):
        raise SystemExit('--qa venv|blender')
    job = [resolved, out, boards] + ([] if '--no-blend' in args else ['--blend']) + \
        {'venv': ['--bundle'], 'blender': ['--qa'], None: []}[qa] + (['--vrm'] if '--vrm' in args else []) + ['--cache', mode]
    cmd = [BLENDER, '-b', '--factory-startup', '--python', os.path.join(ROOT, 'charkit', 'build_blender.py'), '--'] + job
    from . import history, procs, worker
    r = worker.submit(job, out, 'build ' + name) if '--no-worker' not in args else None
    if r is None:
        r = procs.run(cmd, out, 'build ' + name)
    if 'CHARKIT_BUILD_DONE' not in r.stdout:
        sys.stderr.write(r.stdout[-4000:] + r.stderr[-4000:])
        raise SystemExit('blender build failed')
    for line in r.stdout.splitlines():
        if line.startswith(('CHARKIT_QA', 'CHARKIT_GLTF', 'CHARKIT_CACHE', 'CHARKIT_WORKER', 'CHARKIT_BUNDLE')):
            print(line)
    measure(out, mode, qa=qa == 'venv', blender_peak=None if str(r.args[0]) == 'worker' else _peak_mb('children'))
    for p in sheets(spec, out):
        print('sheet', p)
    note = opt('--note')
    if note:
        try:
            note = json.loads(note)
        except ValueError:
            pass
    history.append(out, name, note)
    print('trace', os.path.join(out, 'trace.jsonl'))
    print('built', out)


def _peak_mb(who='self'):
    """the peak resident memory (MB) of this process, or of its largest finished child (the build's Blender)."""
    import resource
    ru = resource.getrusage(resource.RUSAGE_SELF if who == 'self' else resource.RUSAGE_CHILDREN).ru_maxrss
    return round(ru / (1 << 20) if sys.platform == 'darwin' else ru / 1024, 1)


def measure(out, mode='on', qa=True, blender_peak=None):
    """after the Blender stage: the venv's QA on the build's bundle (out/bundle -> out/qa), appended to the build's
    trace with the parts through the QA cache (the build's --cache mode; stages and verify run them afresh), and the
    peak memory of the Blender process (a fresh one's, not a worker's) and of this one noted."""
    from . import qa3d, trace
    rep = None
    trace.resume(os.path.join(out, 'trace.jsonl'))
    try:
        if qa:
            rep = qa3d.measure(os.path.join(out, 'bundle'), os.path.join(out, 'qa'),
                               mode={'on': 'on', 'off': 'off', 'verify': 'verify'}.get(mode, 'refresh'))
        trace.note('build.memory', blender_peak_mb=blender_peak, venv_peak_mb=_peak_mb('self'))
    finally:
        trace.end()
    if rep is not None:
        print('CHARKIT_QA_SUMMARY', rep['summary'])
        print('CHARKIT_CACHE_QA', trace.cache_summary([r for r in trace.read(os.path.join(out, 'trace.jsonl'))
                                                        if r.get('where') == 'venv']))
    return rep


def _glb_inputs(glb):
    """a generated GLB and what it carries beside it (charkit.i3d.glb_eyes' sidecar and the per-vertex labels it names):
    everything the geom hair step reads, for its cache key."""
    p = _path(glb)
    out = [p]
    side = p + '.json'
    if os.path.exists(side):
        out.append(side)
        S = json.load(open(side))
        for k in ('labels', 'pieces'):
            if S.get(k):
                out.append(os.path.join(os.path.dirname(p), S[k]))
    return out


def code_head(spec, resolved, out, mode='on'):
    """venv-side, for spec['base'] == 'code': the authored head (charkit/code_base.py, from the reference images) ->
    out/geom/head_code.npz, and the resolved spec pointed at it (spec['head_code']) for the Blender side. A cached step:
    it runs again when the references it reads, the spec's eyes or style, or the code change."""
    if spec.get('base') != 'code':
        return spec
    from . import cache, code_base, manifest
    gdir = os.path.join(out, 'geom')
    os.makedirs(gdir, exist_ok=True)
    path = os.path.join(gdir, 'head_code.npz')
    M = manifest.load(spec['ref']['manifest'])['references']
    imgs = [_path(spec['ref']['face_sheet']['image']), _path(M['head_construction']['path'])]
    key = {'ref': imgs, 'eyes': spec.get('eyes'), 'style': spec.get('style', 'anime')}

    def run():
        code_base.save_head(spec, path)
        print('code head', path)
    if mode == 'off':
        run()
    else:
        r = cache.file_step('code_head', run, [code_head], key, gdir, inputs=imgs,
                            modules=('charkit.code_base', 'charkit.geom.headfit', 'charkit.geom.hull'),
                            name_key=spec['name'], refresh=mode == 'refresh')
        print('CHARKIT_CACHE code_head', r)
    spec['head_code'] = path
    json.dump(spec, open(resolved, 'w'), indent=1)
    return spec


def geom_hair(spec, resolved, out, mode='on'):
    """venv-side, for hair.shape.mode == 'geom': charkit.geom.parts.hair on the resolved spec -> out/geom/hair.npz, and the
    resolved spec pointed at it. A cached step (charkit.cache.file_step, restored by copy): the cut is given the resolved
    spec without the outfit (out/geom/cut.spec.json), so an outfit change can't reach it, and it runs again when that spec,
    the GLB's content, the charkit code it runs (charkit.geom, the character assembly) or the venv's packages change."""
    shape = (spec.get('hair') or {}).get('shape') or {}
    if shape.get('mode') != 'geom':
        return spec
    from . import cache
    gdir = os.path.join(out, 'geom')
    os.makedirs(gdir, exist_ok=True)
    path = os.path.join(gdir, 'hair.npz')
    cut = {k: v for k, v in spec.items() if k != 'garments'}
    cut['hair'] = dict(spec['hair'], shape={k: v for k, v in shape.items() if k != 'geom'})
    cut_path = os.path.join(gdir, 'cut.spec.json')
    json.dump(cut, open(cut_path, 'w'), indent=1)

    def run():
        from .geom import parts
        C = parts.Case.load(cut_path, fit=False)
        R = parts.hair(C, **shape.get('geom_opts', {}))
        st_ = parts.measure(C, R, parts.hair_region(C), parts.hair_color(C), zmin=C.chin_z, out_dir=gdir, name='hair')
        parts.save_part(R, path, meta=dict(align=C.align, measure=st_))
        print('geom hair', path, json.dumps({k: st_[k] for k in ('faces', 'parts', 'open_edges', 'nonmanifold_edges',
                                                                   'self_intersecting_faces', 'silhouette_iou_mean')}))
    if mode == 'off':
        run()
    else:
        r = cache.file_step('geom_hair', run, [geom_hair], cut, gdir, inputs=_glb_inputs(shape['glb']),
                            modules=('charkit.geom.parts',), name_key=spec['name'], refresh=mode == 'refresh')
        print('CHARKIT_CACHE geom_hair', r)
    shape['geom'] = path
    json.dump(spec, open(resolved, 'w'), indent=1)
    return spec


def export(args):
    blend = _path(args[0])
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    out = _path(opt('--out', os.path.splitext(blend)[0] + '.vrm'))
    cmd = [BLENDER, '-b', '--factory-startup', blend, '--python', os.path.join(ROOT, 'charkit', 'gltf.py'), '--', out,
           '--subdiv', str(opt('--subdiv', 2))]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if 'CHARKIT_GLTF_DONE' not in r.stdout:
        sys.stderr.write(r.stdout[-4000:] + r.stderr[-4000:])
        raise SystemExit('export failed')
    for line in r.stdout.splitlines():
        if line.startswith(('[gltf]', 'CHARKIT_GLTF')):
            print(line)


def figures(args):
    """the model sheet's figures found from the picture (charkit.sheetqa.detect_figures), scaled by the rig: the head
    boxes against the manifest's hand-typed ones, and with --write the manifest's references.sheet.figures replaced by
    the detected (the front figure's region, the head boxes, the facing, plus the back's and the expression heads')."""
    import numpy as np
    from PIL import Image
    from . import manifest, refs, sheetqa
    spec = manifest.resolve(json.load(open(_path(args[0]))))
    ref = spec.get('ref') or {}
    sh = ref.get('sheet') or {}
    if not sh.get('image'):
        raise SystemExit('the spec has no model sheet (ref.sheet)')
    rgb = np.asarray(Image.open(_path(sh['image'])).convert('RGB')).astype(float) / 255
    ex = spec.get('eyes', {}).get('x', 0.168)
    ppl = None
    if ref.get('rig') and sh.get('front_figure'):
        alpha = np.asarray(Image.open(os.path.join(_path(ref['rig']), 'base.png')).convert('RGBA'))[..., 3] / 255.0
        ppl = sheetqa.sheet_ppl(rgb, sh['front_figure'], alpha, refs.measure(_path(ref['rig']), ex)['ppl'])
    D = sheetqa.detect_figures(rgb, ppl=ppl, eye_x=ex)
    print('scale %.2f px/L (%s), facing %d' % (D['ppl'], 'rig' if ppl else 'eye spacing', D['facing']))
    for v, f in D['figures'].items():
        print('  %-14s box %-22s head %-22s eyes %d%s' % (v, f['box'], f['head'], len(f['eyes']), '  (cut)' if f['partial'] else ''))
    for i, e in enumerate(D['expressions']):
        print('  expression %d  box %-22s eyes %d' % (i, e['box'], len(e['eyes'])))
    for s_ in D['skipped']:
        print('  skipped       box %-22s %s' % (s_['box'], s_['why']))
    for v, r in sheetqa.verify_figures(D, sh).items():
        print('  %-14s detected %s typed %s: %s px %s' % (v, r['detected'], r['typed'], r.get('off'), 'ok' if r['ok'] else 'OFF'))
    if '--write' in args:
        mp = ref.get('manifest')
        if not mp:
            raise SystemExit('the spec has no ref.manifest to write to')
        M = json.load(open(_path(mp)))
        M['references']['sheet']['figures'] = sheetqa.manifest_figures(D)
        json.dump(M, open(_path(mp), 'w'), indent=1)
        print('wrote', mp)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__); return
    cmd, rest = argv[0], argv[1:]
    if cmd == 'build':
        build(rest)
    elif cmd == 'qa':
        from . import qa3d
        qa3d.main(rest)
    elif cmd == 'trace':
        from . import trace
        trace.main(rest)
    elif cmd == 'export':
        export(rest)
    elif cmd == 'bodyeval':
        from . import bodyeval
        bodyeval.main(rest)
    elif cmd == 'bodysens':
        from . import bodysens
        bodysens.main(rest)
    elif cmd == 'bodyfit':
        from . import bodyfit
        bodyfit.main(rest)
    elif cmd == 'fit':
        from . import facefit
        facefit.main(rest)
    elif cmd == 'worker':
        from . import worker
        worker.main(rest)
    elif cmd == 'cache':
        from . import cache
        cache.main(rest)
    elif cmd == 'refs-check':
        from . import manifest
        manifest.main(rest)
    elif cmd == 'refcheck':
        from . import refcheck
        refcheck.main(rest)
    elif cmd == 'checkpoint':
        from . import checkpoint
        checkpoint.main(rest)
    elif cmd == 'outfit':
        from . import outfit
        outfit.main(rest)
    elif cmd == 'figures':
        figures(rest)
    elif cmd == 'gate':
        from . import gate
        gate.main(rest)
    elif cmd == 'history':
        from . import history
        history.main(rest)
    elif cmd == 'tune':
        from . import tune
        tune.main(rest)
    elif cmd == 'triage':
        from . import triage
        triage.main(rest)
    elif cmd == 'review':
        from . import review
        review.main(rest)
    elif cmd == 'ps':
        from . import procs
        procs.ps(rest)
    elif cmd == 'kill':
        from . import procs
        procs.kill(rest)
    elif cmd == 'wait':
        from . import procs
        procs.wait(rest)
    elif cmd == 'slots':
        from . import procs
        procs.set_slots(rest)
    elif cmd == 'refs':
        from . import refs
        R = refs.measure(rest[0], float(rest[rest.index('--eye-x') + 1]) if '--eye-x' in rest else 0.168)
        json.dump(R, open(rest[1], 'w'), indent=1); print('wrote', rest[1])
    else:
        raise SystemExit(f'unknown command {cmd!r}\n{__doc__}')
