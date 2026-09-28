"""Lane 2: solve the roster's per-character camera from a lab run (ROSTER_CAM=lab: one fixed camera, d 75, fov 30, yaw 28,
pitch 4, aim (x, 10, 0)). For each character's chosen 30-frame window, the union bounding box of the fighter (non-background
pixels, specks under 40 px removed) sets the distance (apparent size ~ 1/d) and the aim offset, so every character's window
fills TARGET of the frame height, centred, both measured on the median per-frame box (the typical pose; a tossed
pill or a sword tip may leave the frame briefly); wide poses are held to WMAX of the width instead.
    .venv/bin/python projects/so-back/director/over_roster_solve.py LABPREFIX [--iter]   # writes roster_cam.json
LABPREFIX: ~/games/melee/work/soback/labs/roster_lab (runs 0..6). With --iter the lab is a ROSTER_CAM=film run: the solve
refines the existing roster_cam.json from what that camera actually saw."""
import json, math, os, sys
import numpy as np
from PIL import Image
from scipy import ndimage
HERE = os.path.dirname(os.path.abspath(__file__))
CH = ['doc', 'mario', 'luigi', 'bowser', 'peach', 'yoshi', 'dk', 'falcon', 'ganon', 'falco', 'fox', 'ness', 'ics', 'kirby',
      'samus', 'zelda', 'sheik', 'link', 'ylink', 'pichu', 'pikachu', 'puff', 'mewtwo', 'gnw', 'marth', 'roy']
LEAD, SHOT, YAW = 20, 150, math.radians(28)
TARGET, WMAX = 0.70, 1.05                  # the median pose may reach the frame edge (a flash: an arm or tail may clip)
WIN = json.load(open(os.path.join(HERE, 'roster_windows.json')))    # char -> [first, last) shot frames


def bbox(path, bg):
    a = np.asarray(Image.open(path).convert('RGB')).astype(int)
    m = np.abs(a - np.array(bg)).max(-1) > 24
    lab, n = ndimage.label(m)
    if n == 0: return None
    sizes = ndimage.sum(m, lab, range(1, n + 1))
    objs = ndimage.find_objects(lab)
    big = int(np.argmax(sizes)); by, bx = objs[big]
    keep = []                                   # the fighter: the largest part, plus parts near it that aren't specks
    for k, (sy, sx) in enumerate(objs):
        near = sx.start < bx.stop + 120 and sx.stop > bx.start - 120 and sy.start < by.stop + 120 and sy.stop > by.start - 120
        if k == big or (near and sizes[k] >= max(40, 0.01 * sizes[big])):
            keep.append((sx.start, sx.stop - 1, sy.start, sy.stop - 1))
    return (min(b[0] for b in keep), max(b[1] for b in keep), min(b[2] for b in keep), max(b[3] for b in keep))


prefix = os.path.expanduser(sys.argv[1]); it = '--iter' in sys.argv
cams = json.load(open(os.path.join(HERE, 'roster_cam.json'))) if it else {}
out, rep = {}, []
for run in range(7):
    d = f'{prefix}{run}'; fs = sorted(x for x in os.listdir(d) if x.endswith('.png'))
    for i, c in enumerate(CH[run * 4:run * 4 + 4]):
        s0 = LEAD + i * SHOT; w0, w1 = WIN[c]
        bb = [b for b in (bbox(os.path.join(d, fs[s0 + k + 8]), (0, 0, 0)) for k in range(w0, w1)) if b]
        W, H = Image.open(os.path.join(d, fs[s0 + w0 + 8])).size
        # the typical pose: the median per-frame box (a union over 30 frames framed swinging tails, hammers and sword arcs, and
        # left the pose small; in a 0.1 s flash an extremity may touch the edge)
        med = lambda v: float(np.median(v))
        wp = med([b[1] - b[0] + 1 for b in bb]); cx = med([(b[0] + b[1]) / 2 for b in bb])
        hp = med([b[3] - b[2] + 1 for b in bb]); cy = med([(b[2] + b[3]) / 2 for b in bb])   # the median pose vertically
        # too (a tossed pill or a raised sword tip may leave the top for a few frames; the union framed Doc, Samus, Marth and
        # Roy by those and left their bodies small)
        k = cams.get(c, {'d': 75.0, 'ay': 10.0, 'dx': 0.0, 'fov': 30.0})
        dist, fov = k['d'], k.get('fov', 30.0)
        th = 2 * math.tan(math.radians(fov) / 2)
        wy = th * dist / H; wx = 0.5625 * th * dist / W                  # world units per pixel (vertical, horizontal)
        ay = k['ay'] - (cy - H / 2) * wy
        dx = k['dx'] + (cx - W / 2) * wx / math.cos(YAW)
        s = max(hp / (TARGET * H), wp / (WMAX * W))                    # scale the distance so the window fills TARGET
        if wp >= .97 * W: s = max(s, 1.0)                              # the pose already spans the frame (clipped): don't creep closer
        out[c] = {'d': round(dist * s, 2), 'ay': round(ay, 2), 'dx': round(dx, 2), 'fov': fov}
        rep.append(f'{c:8s} window {w0}-{w1}: bbox {wp}x{hp}px (frame {W}x{H}), centre ({cx:.0f},{cy:.0f}) -> d {dist * s:.1f} '
                   f'ay {ay:.2f} dx {dx:.2f}' + ('  WIDTH-LIMITED' if wp / (WMAX * W) > hp / (TARGET * H) else ''))
json.dump(out, open(os.path.join(HERE, 'roster_cam.json'), 'w'), indent=1)
print('\n'.join(rep))
