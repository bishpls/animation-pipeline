"""Key a flat-green drawing to RGBA at its full canvas (no crop, so every drawing of the seated Fable stays in one frame)."""
import sys
import numpy as np
from PIL import Image, ImageFilter


def key(path):
    im = np.asarray(Image.open(path).convert('RGB')).astype(np.float32) / 255
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    k = g - np.maximum(r, b)
    a = 1 - np.clip((k - .12) / (.38 - .12), 0, 1)
    A = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(3)).filter(ImageFilter.GaussianBlur(.6))
    a = np.asarray(A).astype(np.float32) / 255
    g2 = np.minimum(g, np.maximum(r, b) + .02)
    return (np.dstack([r, g2, b, a]) * 255).astype(np.uint8)


if __name__ == '__main__':
    Image.fromarray(key(sys.argv[1])).save(sys.argv[2])
