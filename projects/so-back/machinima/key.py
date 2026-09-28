"""Key a director plate shot on a flat clear colour (stage hidden, DIR_BGCOLOR) to RGBA, with despill.
    .venv/bin/python projects/so-back/machinima/key.py IN.png OUT.png [--key green|blue|red] [--lo 40 --hi 110] [--rot 0|90|-90]
    .venv/bin/python projects/so-back/machinima/key.py IN.png OUT.jpg --board     # composite on a magenta/cyan checker to judge
The game's clear colour is exact (a flat (0,255,0) with no noise), so 'keyness' = key channel minus the larger other channel:
255 on the background, ~0 on fighters. Alpha ramps from --hi (fully keyed) down to --lo (opaque); despill clamps the key channel to
the larger other channel wherever the key channel dominates (the anti-aliased rim and light spill).
"""
import argparse
import numpy as np
from PIL import Image

KEYS = {'red': 0, 'green': 1, 'blue': 2}


def key(rgb, which='green', lo=40, hi=110):
    a = rgb.astype(np.float32)
    k = KEYS[which]; o = [c for c in range(3) if c != k]
    keyness = a[..., k] - np.maximum(a[..., o[0]], a[..., o[1]])
    alpha = 1 - np.clip((keyness - lo) / (hi - lo), 0, 1)
    out = a.copy()
    cap = np.maximum(a[..., o[0]], a[..., o[1]])
    out[..., k] = np.where(keyness > 0, cap, a[..., k])           # despill
    # un-premultiply the rim against the key colour: colour = (pixel - (1-alpha) * key) / alpha, clamped
    bg = np.zeros(3, np.float32); bg[k] = 255
    safe = np.clip(alpha, 1e-3, 1)[..., None]
    rim = (alpha > 0) & (alpha < 1)
    unmix = np.clip((a - (1 - alpha[..., None]) * bg) / safe, 0, 255)
    out[rim] = np.minimum(out[rim], np.maximum(unmix[rim], 0))
    return np.dstack([out, alpha * 255]).astype(np.uint8)


def checker(h, w, n=48):
    y, x = np.mgrid[:h, :w]
    c = ((x // n + y // n) % 2).astype(bool)
    img = np.zeros((h, w, 3), np.uint8); img[c] = (255, 0, 200); img[~c] = (0, 220, 255)
    return img


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('inp'); ap.add_argument('out')
    ap.add_argument('--key', default='green'); ap.add_argument('--lo', type=float, default=40); ap.add_argument('--hi', type=float, default=110)
    ap.add_argument('--rot', type=int, default=0); ap.add_argument('--board', action='store_true')
    a = ap.parse_args()
    im = Image.open(a.inp).convert('RGB')
    if a.rot: im = im.rotate(a.rot, expand=True)
    rgba = key(np.asarray(im), a.key, a.lo, a.hi)
    if a.board:
        bg = checker(*rgba.shape[:2]).astype(np.float32); al = rgba[..., 3:4] / 255.0
        Image.fromarray((rgba[..., :3] * al + bg * (1 - al)).astype(np.uint8)).save(a.out, quality=92)
    else:
        Image.fromarray(rgba, 'RGBA').save(a.out)
