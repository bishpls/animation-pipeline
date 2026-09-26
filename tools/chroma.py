"""Chroma-key flat-green illustrations to transparent PNGs (with despill + soft edge), cropped to content.
    .venv/bin/python tools/chroma.py IN.png [IN2.png ...] --out DIR [--full]
Writes DIR/<name>.png and prints the crop box (for placing it back in its original 16:9 frame: see <name>.json).
--full keeps the whole canvas (no crop, no .json), so every drawing of a pose set stays in one frame, ready to register.
From a rig builder: sys.path.insert(0, '<repo>/tools'); from chroma import key; key(path) -> uint8 RGBA, full canvas.
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageFilter


def keyf(path):
    """the keyed drawing as float RGBA in 0..1, full canvas"""
    im = np.asarray(Image.open(path).convert('RGB')).astype(np.float32) / 255
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    # greenness: how much green exceeds the max of red and blue
    k = g - np.maximum(r, b)
    alpha = 1 - np.clip((k - .12) / (.38 - .12), 0, 1)
    # remove isolated specks and soften the edge by one pixel
    A = Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(3)).filter(ImageFilter.GaussianBlur(.6))
    alpha = np.asarray(A).astype(np.float32) / 255
    # despill: clamp green to the max of red/blue where it exceeds it (kills green fringes)
    g2 = np.minimum(g, np.maximum(r, b) + .02)
    return np.dstack([r, g2, b, alpha])


def key(path):
    """the keyed drawing as uint8 RGBA, full canvas (the rig builders' key)"""
    return (keyf(path) * 255).astype(np.uint8)


if __name__ == '__main__':
    a = sys.argv[1:]; out = a[a.index('--out') + 1]; files = [f for f in a if f.endswith('.png') and f != out]
    os.makedirs(out, exist_ok=True)
    for f in files:
        rgba = keyf(f); name = os.path.splitext(os.path.basename(f))[0]
        if '--full' in a:
            Image.fromarray((rgba * 255).astype(np.uint8)).save(os.path.join(out, name + '.png')); print(name, 'full', list(rgba.shape[1::-1])); continue
        ys, xs = np.where(rgba[..., 3] > .02)
        box = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
        Image.fromarray((rgba * 255).astype(np.uint8)).crop(box).save(os.path.join(out, name + '.png'))
        json.dump({'src': list(rgba.shape[1::-1]), 'box': box}, open(os.path.join(out, name + '.json'), 'w'))
        print(name, 'box', box)
