"""Frame-difference scan of a rendered film: flags every frame whose change from the previous one spikes above its neighbourhood
(a pop, a jump, an unplanned cut), minus the cuts you list as known. Prints the flags with song time and writes a strip of each
(the frame before, the frame, the frame after).

    .venv/bin/python tools/filmscan.py FRAMES_DIR [--fps 24] [--known 9.0,12.7,...] [--tol 0.05] [--out DIR]
"""
import os, sys, json
import numpy as np
from PIL import Image

a = sys.argv[1:]; opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
src = a[0]; fps = float(opt('--fps', 24)); tol = float(opt('--tol', .05)); out = opt('--out', os.path.join(src, '..', 'filmscan'))
known = [float(x) for x in opt('--known', '').split(',') if x]
files = sorted(f for f in os.listdir(src) if f.endswith(('.jpg', '.png')))
os.makedirs(out, exist_ok=True)
small = lambda f: np.asarray(Image.open(os.path.join(src, f)).convert('L').resize((192, 108), Image.BILINEAR)).astype(np.float32)
prev, d = None, []
for f in files:
    cur = small(f); d.append(0. if prev is None else float(np.abs(cur - prev).mean())); prev = cur
d = np.array(d); flags = []
for i in range(1, len(d)):
    lo, hi = max(1, i - 12), min(len(d), i + 13); nb = np.r_[d[lo:i], d[i + 1:hi]]
    mv = nb[nb > .5]; ctx = np.median(mv) if len(mv) else 0.          # (content on twos holds every other frame: compare with the frames that move)
    if d[i] > max(9., 3.5 * ctx):
        t = i / fps
        if any(abs(t - k) <= tol + 1 / fps for k in known): continue
        flags.append((i, round(t, 3), round(d[i], 1), round(float(ctx), 1)))
json.dump({'diff': d.round(2).tolist(), 'flags': flags}, open(os.path.join(out, 'scan.json'), 'w'))
for i, t, v, c in flags:
    ims = [Image.open(os.path.join(src, files[j])).convert('RGB').resize((384, 216)) for j in (max(0, i - 1), i, min(len(files) - 1, i + 1))]
    W = Image.new('RGB', (384 * 3, 216)); [W.paste(im, (k * 384, 0)) for k, im in enumerate(ims)]; W.save(os.path.join(out, f'flag_{t:07.3f}.jpg'))
    print(f'{t:8.3f}s  frame {i}  diff {v}  (around {c})')
print(len(flags), 'flags')
