"""Every drawing of every move, side by side: rows = moves (one per key time), columns = the drawing before the key, the
in-between, the drawing past the pose, the pose, and the hold after (exact 12 fps drawing times). For stop-motion and
posed acting, the sheet a move lives or dies on: pops, slides, gaps and wrong overshoots show here, not in a playback.

    .venv/bin/python tools/drawings.py PROJECT LOOP x,y,w,h KEY_T1,KEY_T2,... OUT.png

(crop is in frame px; the loop is rendered with engine/render.mjs --stills into PROJECT/board/_drawings/.)
"""
import math, subprocess, sys, glob, os
from PIL import Image, ImageDraw
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
proj, loop, crop, keys, out = sys.argv[1], sys.argv[2], [int(v) for v in sys.argv[3].split(',')], [float(v) for v in sys.argv[4].split(',')], sys.argv[5]
d = os.path.join(ROOT, proj, 'board', '_drawings')
os.makedirs(d, exist_ok=True); [os.remove(f) for f in glob.glob(d + '/*.png')]
rows = []
for t1 in keys:
    q0 = math.ceil(t1 * 12 - 1e-6) / 12
    rows.append([round(q0 + k / 12 + .01, 3) for k in range(-1, 4)])
ts = sorted({t for r in rows for t in r})
subprocess.run(['node', 'engine/render.mjs', proj, f'--loop={loop}', '--stills=' + ','.join(map(str, ts)), f'--out={d}'], check=True, capture_output=True, cwd=ROOT)
x, y, w, h = crop; sc = 300 / w
sheet = Image.new('RGB', (5 * 306, len(rows) * (int(h * sc) + 22)), (20, 20, 20)); dr = ImageDraw.Draw(sheet)
for i, r in enumerate(rows):
    for j, t in enumerate(r):
        f = f'{d}/t{t:.2f}.png'.replace('.', '_', 1).replace('_png', '.png')
        f = f if os.path.exists(f) else None
        if f:
            im = Image.open(f).crop((x, y, x + w, y + h)).resize((300, int(h * sc))); sheet.paste(im, (j * 306, i * (int(h * sc) + 22) + 20))
        dr.text((j * 306 + 4, i * (int(h * sc) + 22) + 4), f'{t:.2f}s ' + ['hold', 'in-betw', 'past', 'pose', 'hold'][j], fill=(255, 220, 90))
sheet.save(out); print(out)
