"""charkit's command line (run with the venv's python, which has PIL; Blender is called for the scene):

    python -m charkit build SPEC.json [--out DIR] [--boards views,body,expressions,mouths] [--no-blend] [--no-fit] [--no-qa] [--vrm]
                                     [--base makehuman|anime] [--hair geom|mesh] [--note JSON]
    python -m charkit export BUILD.blend [--out OUT.vrm] [--subdiv 2]
    python -m charkit refs RIG_DIR OUT.json [--eye-x 0.168]
    python -m charkit trace OUT/trace.jsonl [OTHER/trace.jsonl]     # a build's state log, or what changed between two
    python -m charkit gate BRANCH [--into REF] [--args "--base anime"] # what merging BRANCH would do, measured first
    python -m charkit history NAME [--check CHECK]                     # QA across builds
    python -m charkit ps | kill OUT_DIR                                # running builds, by their own records
    python -m charkit tune SPEC [--out DIR] [--budget N|Nm] [--review]   # fit, build, check, triage (charkit/tune.py)
    python -m charkit triage DIR                                       # the residual checks as ranked work items
    python -m charkit review board|serve|note|ticket|tickets ...       # the human review checkpoint (charkit/review.py)
    python -m charkit refs-check SPEC                                  # the character's references (ref.manifest)
    python -m charkit figures SPEC [--write]     # find the model sheet's figures; check (or write) the manifest's boxes

build writes out/trace.jsonl as it goes (charkit/trace.py): every stage's objects, geometry hashes, mesh health, landmarks
and timings. build: 1) measures the spec's design reference (spec.ref.rig, a 2D rig's layers) and fits knobs into a resolved spec
(out/NAME.spec.json; knobs the spec sets itself are kept), 2) builds the scene in Blender, renders the boards and saves
out/NAME.blend, 3) composes review sheets next to the reference image (spec.ref.image): out/sheet_views.png,
out/sheet_body.png, out/sheet_face.png. --vrm also writes out/NAME.vrm (charkit/gltf.py). --base overrides the spec's base
mesh (spec['base']: 'makehuman', the default, wraps MakeHuman's own head; 'anime' builds on charkit's derived anime base,
charkit/base_anime.py). With hair.shape.mode 'geom' (or --hair geom) the generated hair is cut out venv-side by
charkit.geom first (out/geom/hair.npz, cached by the resolved spec and the GLB) and the Blender stage loads that closed
surface (docs/GEOM.md).

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
    spec = manifest.resolve(json.load(open(spec_path)))
    if base:
        spec['base'] = base
    ref = spec.get('ref', {})
    if do_fit and isinstance(ref, dict) and ref.get('rig'):
        R = refs.measure(_path(ref['rig']), spec.get('eyes', {}).get('x', 0.168))
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


def sheets(spec, out):
    import numpy as np
    from PIL import Image
    b = os.path.join(out, 'boards')
    ref = _ref_image(spec)
    made = []
    views = [os.path.join(b, f'face_{a:03d}.png') for a in (0, 30, 60, 90, 150)]
    if all(os.path.exists(p) for p in views):
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
    if all(os.path.exists(p) for p in body):
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
    spec = geom_hair(spec, resolved, out)
    boards = opt('--boards', 'views,body,expressions,mouths')
    cmd = [BLENDER, '-b', '--factory-startup', '--python', os.path.join(ROOT, 'charkit', 'build_blender.py'), '--',
           resolved, out, boards] + ([] if '--no-blend' in args else ['--blend']) + ([] if '--no-qa' in args else ['--qa']) + \
          (['--vrm'] if '--vrm' in args else [])
    from . import history, procs
    r = procs.run(cmd, out, 'build ' + name)
    if 'CHARKIT_BUILD_DONE' not in r.stdout:
        sys.stderr.write(r.stdout[-4000:] + r.stderr[-4000:])
        raise SystemExit('blender build failed')
    for line in r.stdout.splitlines():
        if line.startswith(('CHARKIT_QA', 'CHARKIT_GLTF')):
            print(line)
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


def _geom_version():
    from .geom import parts
    return parts.VERSION


def geom_hair(spec, resolved, out):
    """venv-side, for hair.shape.mode == 'geom': charkit.geom.parts.hair on the resolved spec -> out/geom/hair.npz (reused
    while the resolved spec and the GLB are unchanged), and the resolved spec pointed at it."""
    import hashlib
    shape = (spec.get('hair') or {}).get('shape') or {}
    if shape.get('mode') != 'geom':
        return spec
    glb = _path(shape['glb'])
    st = os.stat(glb)
    key = hashlib.sha1((json.dumps({k: v for k, v in spec.items() if k != 'hair'}, sort_keys=True) +
                        json.dumps({k: v for k, v in spec['hair'].items() if k != 'shape'}, sort_keys=True) +
                        json.dumps({k: v for k, v in shape.items() if k not in ('geom', 'mode')}, sort_keys=True) +
                        f'{st.st_size}:{int(st.st_mtime)}:v{_geom_version()}').encode()).hexdigest()[:16]
    path = os.path.join(out, 'geom', 'hair.npz')
    fresh = False
    if os.path.exists(path):
        from .geom.io import load_npz
        _, meta, _ = load_npz(path, with_meta=True)
        fresh = meta.get('key') == key
    if not fresh:
        from .geom import parts
        C = parts.Case.load(resolved, fit=False)
        R = parts.hair(C, **shape.get('geom_opts', {}))
        st_ = parts.measure(C, R, parts.hair_region(C), parts.hair_color(C), zmin=C.chin_z,
                            out_dir=os.path.join(out, 'geom'), name='hair')
        parts.save_part(R, path, meta=dict(key=key, align=C.align, measure=st_))
        print('geom hair', path, json.dumps({k: st_[k] for k in ('faces', 'parts', 'open_edges', 'nonmanifold_edges',
                                                                   'self_intersecting_faces', 'silhouette_iou_mean')}))
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
    elif cmd == 'trace':
        from . import trace
        trace.main(rest)
    elif cmd == 'export':
        export(rest)
    elif cmd == 'refs-check':
        from . import manifest
        manifest.main(rest)
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
    elif cmd == 'refs':
        from . import refs
        R = refs.measure(rest[0], float(rest[rest.index('--eye-x') + 1]) if '--eye-x' in rest else 0.168)
        json.dump(R, open(rest[1], 'w'), indent=1); print('wrote', rest[1])
    else:
        raise SystemExit(f'unknown command {cmd!r}\n{__doc__}')
