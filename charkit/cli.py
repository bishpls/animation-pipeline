"""charkit's command line (run with the venv's python, which has PIL; Blender is called for the scene):

    python -m charkit build SPEC.json [--out DIR] [--boards views,body,expressions,mouths] [--no-blend] [--no-fit] [--no-qa]
    python -m charkit refs RIG_DIR OUT.json [--eye-x 0.168]

build: 1) measures the spec's design reference (spec.ref.rig, a 2D rig's layers) and fits knobs into a resolved spec
(out/NAME.spec.json; knobs the spec sets itself are kept), 2) builds the scene in Blender, renders the boards and saves
out/NAME.blend, 3) composes review sheets next to the reference image (spec.ref.image): out/sheet_views.png,
out/sheet_body.png, out/sheet_face.png.
"""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLENDER = os.environ.get('BLENDER', '/Applications/Blender.app/Contents/MacOS/Blender')


def _path(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def resolve(spec_path, out, do_fit=True):
    from . import refs
    spec = json.load(open(spec_path))
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
        S = Image.new('RGB', (1800, 257 + 180), 'white')
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
    spec, resolved = resolve(spec_path, out, do_fit='--no-fit' not in args)
    boards = opt('--boards', 'views,body,expressions,mouths')
    cmd = [BLENDER, '-b', '--factory-startup', '--python', os.path.join(ROOT, 'charkit', 'build_blender.py'), '--',
           resolved, out, boards] + ([] if '--no-blend' in args else ['--blend']) + ([] if '--no-qa' in args else ['--qa'])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if 'CHARKIT_BUILD_DONE' not in r.stdout:
        sys.stderr.write(r.stdout[-4000:] + r.stderr[-4000:])
        raise SystemExit('blender build failed')
    for line in r.stdout.splitlines():
        if line.startswith('CHARKIT_QA'):
            print(line)
    for p in sheets(spec, out):
        print('sheet', p)
    print('built', out)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__); return
    cmd, rest = argv[0], argv[1:]
    if cmd == 'build':
        build(rest)
    elif cmd == 'refs':
        from . import refs
        R = refs.measure(rest[0], float(rest[rest.index('--eye-x') + 1]) if '--eye-x' in rest else 0.168)
        json.dump(R, open(rest[1], 'w'), indent=1); print('wrote', rest[1])
    else:
        raise SystemExit(f'unknown command {cmd!r}\n{__doc__}')
