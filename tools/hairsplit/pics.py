"""Diagnostic pictures of a hairsplit run, per view: the sheet with the strokes (ink black, extensions red, free ends
dots), the flow (streak lines), the cells, the locks (each its colour, tips and axes, layer rank), the truth.

    python tools/hairsplit/pics.py RUN_DIR OUT_DIR       (RUN_DIR: hairsplit.npz/json; uses the inputs cache there)
"""
import json, os, pickle, sys
import numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)


def palette(n, seed=7):
    rng = np.random.RandomState(seed)
    p = rng.randint(50, 245, (n + 1, 3)).astype(np.uint8)
    p[0] = 0
    return p


def colour(lab, rgb, alpha=0.65, seed=7):
    p = palette(int(lab.max()) + 1, seed)
    out = (rgb * 255).astype(np.uint8).copy() if rgb.max() <= 1.5 else rgb.astype(np.uint8).copy()
    m = lab > 0
    out[m] = ((1 - alpha) * out[m] + alpha * p[lab[m]]).astype(np.uint8)
    return out


def edges(lab):
    e = np.zeros(lab.shape, bool)
    e[:, 1:] |= lab[:, 1:] != lab[:, :-1]
    e[1:, :] |= lab[1:, :] != lab[:-1, :]
    return e


def crop(img, box):
    r0, r1, c0, c1 = box
    return img[r0:r1, c0:c1]


def zoom(a, k):
    return np.asarray(Image.fromarray(a).resize((a.shape[1] * k, a.shape[0] * k), Image.NEAREST))
