"""The check for foot sliding: renders of LOOPS.fableroom_key (the figure alone on flat green, camera still, one still per
drawing at the drawing's centre time), keyed, every geta found (feet.py), and each geta followed from drawing to drawing. A geta
on the floor in two consecutive drawings is planted: it must not move. Prints screen px (1080p, the room's wide scale .697).
    node engine/render.mjs projects/tsuzuku/rig/fable_room/preview --loop=fableroom_key --stills=<(k+.5)/12,...> --out=DIR
    .venv/bin/python projects/tsuzuku/rig/fable_room/slide.py DIR
"""
import glob, os, sys
import numpy as np
from PIL import Image
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(D, '..', 'fable_seated')); sys.path.insert(0, D)
from key import key  # noqa: E402
from feet import geta  # noqa: E402

K = .697 * .5
FLOOR = 1002                                                             # (the loop's floor line, screen px)
fs = sorted(glob.glob(os.path.join(sys.argv[1], '*.png')))
rows = []
for f in fs:
    a = key(f); t = os.path.basename(f)[1:-4].replace('_', '.')
    g = geta(a, xmin=0, facing=1, k=K)['geta']
    rows.append((t, [(q['toe'][0], q['toe'][1], FLOOR - q['toe'][1]) for q in g]))
worst = 0
for i, (t, g) in enumerate(rows):
    s = '  '.join(f'({x:5.0f},{y:5.0f} up {u:3.0f})' for x, y, u in g)
    note = ''
    if i:
        for x, y, u in g:                                                # this geta on the floor, and a floor geta near it before
            prev = [(abs(x - x0), x0, y0) for x0, y0, u0 in rows[i - 1][1] if u0 <= 3]
            if u <= 3 and prev:
                d, x0, y0 = min(prev)
                if d < 40: note += f'  planted {x0:.0f}->{x:.0f} (dx {x - x0:+.0f}, dy {y - y0:+.0f})'; worst = max(worst, abs(x - x0), abs(y - y0))
    print(f'{t:>8s}  {s:60s}{note}')
print(f'worst planted-geta drift between consecutive drawings: {worst:.0f} px')
