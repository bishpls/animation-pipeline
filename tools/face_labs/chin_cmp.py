"""the chin and neck, ours beside the design at the same scale: the head sheet's view and a build's face board (the
boards' 85 mm camera at eye height + 0.06 L, 900 px), cut from 0.1 L above the eyes to 0.75 L below, +-0.5 L across,
at PPL px per L.
    python chin_cmp.py OUT.png BUILD_DIR [BUILD_DIR ...]"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.expanduser('~/animation-pipeline-face'))
from charkit import manifest, refcheck

PPL = 420
TOP, BOT, HALF = 0.1, 0.75, 0.5
spec = manifest.resolve(json.load(open(os.path.expanduser('~/animation-pipeline-face/charkit/spec/clawd_body.json'))))
rgb = refcheck._load(spec['ref']['face_sheet']['image'])
rgb0, _ = refcheck.without_guides(np.asarray(rgb, float))
ex = 0.168
_, f, H = refcheck.at_scale(rgb0, ex, 2 * ex * refcheck.FACE_PPL, -1)
own = refcheck.FACE_PPL / f


def design(view):
    h = H['heads'][view]
    ey = h['eye_y'] / f
    eyes = sorted(h['eyes'])
    cx = np.mean([e[0] for e in eyes]) / f if view == 'front' else (h['box'][0] + h['box'][2]) / 2 / f
    im = Image.fromarray((np.clip(rgb0, 0, 1) * 255).astype(np.uint8))
    box = (cx - HALF * own, ey - TOP * own, cx + HALF * own, ey + BOT * own)
    return im.crop(tuple(int(round(v)) for v in box)).resize((int(2 * HALF * PPL), int((TOP + BOT) * PPL)))


def board(build, fn, L):
    im = Image.open(os.path.join(build, 'boards', fn)).convert('RGB')
    ppl = 85 / 36 * im.size[0] * L                     # px per L at the target's distance (1 m)
    cx, ey = im.size[0] / 2, im.size[1] / 2 + 0.06 * ppl
    box = (cx - HALF * ppl, ey - TOP * ppl, cx + HALF * ppl, ey + BOT * ppl)
    return im.crop(tuple(int(round(v)) for v in box)).resize((int(2 * HALF * PPL), int((TOP + BOT) * PPL)))


out, builds = sys.argv[1], sys.argv[2:]
cols = [('design', {v: design(v) for v in ('front', 'three_quarter', 'profile')})]
for b in builds:
    import glob
    from charkit import bundle as bl
    L = bl.load(os.path.join(b, 'bundle')).assembly['L']
    cols.append((os.path.basename(b.rstrip('/')), {v: board(b, fn, L) for v, fn in
                 (('front', 'face_000.png'), ('three_quarter', 'face_030.png'), ('profile', 'face_090.png'))}))
w, h = int(2 * HALF * PPL), int((TOP + BOT) * PPL)
S = Image.new('RGB', (len(cols) * (w + 8), 3 * (h + 8) + 20), (255, 255, 255))
d = ImageDraw.Draw(S)
for i, (name, ims) in enumerate(cols):
    d.text((i * (w + 8) + 6, 4), name, fill=(0, 0, 0))
    for j, v in enumerate(('front', 'three_quarter', 'profile')):
        S.paste(ims[v], (i * (w + 8), 20 + j * (h + 8)))
        # the eye line and every 0.1 L below it
        for k in range(0, 8):
            y = 20 + j * (h + 8) + int((TOP + 0.1 * k) * PPL)
            d.line([(i * (w + 8), y), (i * (w + 8) + 12, y)], fill=(255, 0, 0))
S.save(out)
print(out, S.size)
