"""Where do a rig's problems happen? Heatmaps accumulated over every frame of a range-of-motion run (after tools/romrun.py).

    .venv/bin/python tools/romheat.py projects/<film>/out/rom [--seg tilt] [--layers hair_back,face,neck] [--view F]
Writes OUT/heat.png: one panel per layer (invented pixels exposed, counted per pixel over frames) plus holes, each drawn over
the rest frame of that view (only frames in that view are counted). Brighter = exposed in more frames.
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import romcheck2 as rc

a = sys.argv[1:]; O = a[0]; opt = lambda k, d: a[a.index(k) + 1] if k in a else d
ROM = json.load(open(os.path.join(O, 'rom.json'))); rc.setup(os.path.join(O, 'ids.json'))
want = [s for s in opt('--seg', '').split(',') if s]; layers = opt('--layers', 'hair_back,face,neck,hair_side_R').split(','); V = opt('--view', 'F')
FPS = 24; frames = []
for name, t0, t1 in ROM:
    if want and not any(w in name for w in want): continue
    frames += list(range(int(round(t0 * FPS)), int(round(t1 * FPS))))
heat = {l: np.zeros((1080, 1920), np.int32) for l in layers + ['holes']}; n = 0
for f in frames:
    p = os.path.join(O, 'romid', f'f{f:05d}.png')
    if not os.path.exists(p): continue
    r = rc.decode(p)
    if r is None: continue
    lab, inv, (x0, y0) = r; h, w = lab.shape
    names = {i + 1: k for i, k in enumerate(rc.KEYS)}
    vs = {}
    for i in np.unique(lab):
        if i and ':' in names[i]: vs[names[i].split(':')[0]] = vs.get(names[i].split(':')[0], 0) + 1
    if (max(vs, key=vs.get) if vs else 'F') != V: continue
    n += 1
    for l in layers:
        ids = [i for i, k in names.items() if k.split(':')[-1] == l]
        m = inv & np.isin(lab, ids); heat[l][y0:y0 + h, x0:x0 + w] += m
    bg = lab == 0; L, k = ndi.label(bg); edge = set(np.unique(np.concatenate([L[0], L[-1], L[:, 0], L[:, -1]])))
    hm = bg & ~np.isin(L, list(edge)); heat['holes'][y0:y0 + h, x0:x0 + w] += hm
restf = next(int((t1 - .05) * FPS) for nm, t0, t1 in ROM if nm == f'rest {V}')
base = np.array(Image.open(os.path.join(O, 'romid', f'f{restf:05d}.png')).convert('L')).astype(float) * .35
tiles = []
for l in layers + ['holes']:
    H = heat[l].astype(float); H = H / max(1, n)
    im = np.stack([base] * 3, -1); m = H > 0; im[m] = im[m] * .3 + np.stack([255 * np.clip(H[m] * 4, 0, 1), 255 * np.clip(H[m] * 1.5, 0, 1) * .6, 60 + 0 * H[m]], -1)
    t = Image.fromarray(im.clip(0, 255).astype(np.uint8)).crop((480, 0, 1440, 1080)).resize((480, 540)); ImageDraw.Draw(t).text((6, 6), f'{l}  ({n} frames, view {V})', fill=(255, 255, 0)); tiles.append(t)
sh = Image.new('RGB', (len(tiles) * 485, 540), 'black')
for i, t in enumerate(tiles): sh.paste(t, (i * 485, 0))
sh.save(os.path.join(O, 'heat.png')); print('heat:', os.path.join(O, 'heat.png'), n, 'frames')
