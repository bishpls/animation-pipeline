"""Post for 3D tests: bloom from the bright parts (the stage's light), a purple lift in the blacks, a soft vignette.
    ~/animation-pipeline/.venv/bin/python projects/clawd3d/build/post.py FRAMES_DIR OUT_DIR [--workers 6] [--aux AUX_DIR] [--feat FEAT_DIR]
Inner lines come from the aux pass (dance_test.py renders it after the frames).
"""
import glob, os, sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter


LINE = np.array([0.23, 0.13, 0.11], np.float32)


def lines(aux_path, shape):
    """inner lines from the aux pass (camera-space normal x, y and depth): where the normal turns sharply or the depth
    jumps, e.g. between overlapping legs, clumps of hair, a sleeve over an arm."""
    x = np.asarray(Image.open(aux_path)).astype(np.float32)
    x = x / (65535.0 if x.max() > 255 else 255.0)
    if x.shape[:2] != shape:
        return None
    nx, ny, d = x[..., 0] * 2 - 1, x[..., 1] * 2 - 1, x[..., 2] * 12.0
    bg = (np.abs(nx) < 0.02) & (np.abs(ny) < 0.02) & (d > 11.5)

    def grad(a):
        g = np.zeros_like(a)
        g[1:-1, 1:-1] = np.maximum(np.abs(a[2:, 1:-1] - a[:-2, 1:-1]), np.abs(a[1:-1, 2:] - a[1:-1, :-2]))
        return g
    gn = np.maximum(grad(nx), grad(ny))
    gd = grad(d) / np.maximum(d, 0.1)
    e = ((gn > 0.55) | (gd > 0.035)) & ~bg
    e = e | np.roll(e, 1, 0) & ~bg                                # a touch thicker
    return gaussian_filter(e.astype(np.float32), 0.6).clip(0, 1) * 0.85


FEAT_THROUGH = 0.55                      # how strongly the eyes and brows show through the bangs


def grade(src, dst, aux=None, feat=None):
    a = np.asarray(Image.open(src).convert('RGB')).astype(np.float32) / 255
    h, w, _ = a.shape
    s = w / 1920
    if feat and os.path.exists(feat):
        f = np.asarray(Image.open(feat).convert('RGBA')).astype(np.float32) / 255
        if f.shape[:2] == (h, w):
            k = (f[..., 3] * FEAT_THROUGH)[..., None]           # where they're already visible this changes nothing
            a = a * (1 - k) + f[..., :3] * k
    if aux and os.path.exists(aux):
        ln = lines(aux, (h, w))
        if ln is not None:
            a = a * (1 - ln[..., None]) + LINE * ln[..., None]
    lum = a @ np.array([0.3, 0.59, 0.11], np.float32)
    bright = np.clip(lum - 0.62, 0, None)[..., None] * a
    bloom = gaussian_filter(bright, (10 * s, 10 * s, 0)) * 0.9 + gaussian_filter(bright, (38 * s, 38 * s, 0)) * 0.7
    out = 1 - (1 - a) * (1 - np.clip(bloom, 0, 1))                         # screen
    lift = np.array([0.045, 0.02, 0.07], np.float32)
    out = lift + out * (1 - lift)
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    out *= (1 - 0.22 * np.clip(r - 0.55, 0, None) ** 1.5)[..., None]
    Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)).save(dst)


def main(src, dst, workers=6, aux=None, feat=None):
    os.makedirs(dst, exist_ok=True)
    fs = sorted(glob.glob(os.path.join(src, '*.png')))
    auxs = [os.path.join(aux, os.path.basename(f)) if aux else None for f in fs]
    feats = [os.path.join(feat, os.path.basename(f)) if feat else None for f in fs]
    with ProcessPoolExecutor(workers) as ex:
        list(ex.map(grade, fs, [os.path.join(dst, os.path.basename(f)) for f in fs], auxs, feats))
    print(len(fs), 'frames ->', dst)


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], a[1], int(a[a.index('--workers') + 1]) if '--workers' in a else 6,
         a[a.index('--aux') + 1] if '--aux' in a else None, a[a.index('--feat') + 1] if '--feat' in a else None)
