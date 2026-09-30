"""A build's boards drawn by charkit's toon renderer (docs/workstreams/toonrender.md, phase 2): what `python -m charkit
build --boards` renders where there is no GPU for EEVEE (the CPU build box: CHARKIT_NO_RENDER=1), or with
--boards-renderer toon anywhere. The sets the renderer draws (views, body, design) from the build's export
(NAME.look.glb, else NAME.vrm), framed as scene.boards frames them (the export's `boards`); the expression and mouth sets
need the shape keys and stay EEVEE's (skipped here, and said so).

    from charkit.render import buildboards
    rep = buildboards.draw('charkit/out/NAME', ('views', 'body'))     # OUT/boards/*.png, OUT/boards/toon.json
"""
import json, os, time

import numpy as np


def export_of(out):
    """a build's export for the renderer: NAME.look.glb, else NAME.vrm (not the springs file) -> path or None."""
    try:
        fs = sorted(os.listdir(out))
    except OSError:
        return None
    for suffix in ('.look.glb', '.vrm'):
        c = [f for f in fs if f.endswith(suffix) and '.springs.' not in f]
        if c:
            return os.path.join(out, c[0])
    return None


def draw(out, which=('views', 'body'), adapter=None, ss=4):
    """the boards of `which` the renderer draws, into out/boards -> the report (also out/boards/toon.json): the adapter,
    seconds per board, the load and setup, what was skipped and why."""
    from PIL import Image
    from . import gpu, model, views
    t0, c0 = time.time(), time.process_time()
    path = export_of(out)
    if path is None:
        raise FileNotFoundError('%s: no NAME.look.glb or NAME.vrm (the build writes one)' % out)
    M = model.load(path)
    t1 = time.time()
    R = gpu.Renderer(M, adapter=adapter or os.environ.get('CHARKIT_RENDER_ADAPTER'), ss=ss)
    t2 = time.time()
    drawn = [w for w in which if w in views.SETS]
    skipped = [w for w in which if w not in views.SETS]
    bd = os.path.join(out, 'boards')
    os.makedirs(bd, exist_ok=True)
    rep = {'renderer': 'charkit.render', 'export': os.path.basename(path), 'adapter': R.info, 'ss': R.ss,
           'load_s': round(t1 - t0, 3), 'setup_s': round(t2 - t1, 3), 'boards': {}, 'drawn': drawn,
           'skipped': {w: 'needs the shape keys (morph targets): EEVEE boards on the render box' for w in skipped}}
    for v in views.board_views(M, tuple(drawn)):
        t = time.time()
        img = R.render(v)
        rep['boards'][v.name] = round(time.time() - t, 4)
        Image.fromarray(img).save(os.path.join(bd, v.name + '.png'))
    rep['seconds'] = round(time.time() - t0, 2)
    rep['cpu_s'] = round(time.process_time() - c0, 2)
    if rep['boards']:
        per = {k: [s for n, s in rep['boards'].items() if n.startswith(k)] for k in ('face', 'body', 'design')}
        rep['mean_s'] = {k: round(float(np.mean(x)), 4) for k, x in per.items() if x}
    json.dump(rep, open(os.path.join(bd, 'toon.json'), 'w'), indent=1, default=str)
    return rep
