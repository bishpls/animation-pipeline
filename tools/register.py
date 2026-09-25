"""Align an edited illustration (a new head view, an expression) to the rig base, using a region that should not have changed.

    .venv/bin/python tools/register.py BASE.png VIEW.png OUT.png --roi x0,y0,x1,y1 [--motion affine|similarity]

ECC on the lineart-weighted luminance inside the ROI (e.g. the torso when only the head was changed), coarse to fine.
Writes the view warped into the base's pixel frame, and prints the residual (mean abs luminance diff inside the ROI).
"""
import sys
import numpy as np, cv2
from PIL import Image


def lum(p):
    a = np.array(Image.open(p).convert('RGBA')).astype(np.float32)
    g = (a[:, :, :3] @ [.299, .587, .114]) * (a[:, :, 3] / 255) + 200 * (1 - a[:, :, 3] / 255)     # transparent -> light grey
    return a, g.astype(np.float32)


def main(base, view, out, roi, motion='affine'):
    _, gb = lum(base); va, gv = lum(view)
    x0, y0, x1, y1 = roi; M = np.zeros(gb.shape, np.uint8); M[y0:y1, x0:x1] = 1
    mode = cv2.MOTION_AFFINE if motion == 'affine' else cv2.MOTION_EUCLIDEAN
    warp = np.eye(2, 3, dtype=np.float32)
    for sc in (.125, .25, .5):
        b = cv2.resize(gb, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA); v = cv2.resize(gv, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
        m = cv2.resize(M, None, fx=sc, fy=sc, interpolation=cv2.INTER_NEAREST)
        w = warp.copy(); w[:, 2] *= sc
        b = cv2.GaussianBlur(b, (0, 0), 1.2); v = cv2.GaussianBlur(v, (0, 0), 1.2)
        _, w = cv2.findTransformECC(b, v, w, mode, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 300, 1e-6), m, 5)
        warp = w.copy(); warp[:, 2] /= sc
    H, W = gb.shape
    al = cv2.warpAffine(va, warp, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    Image.fromarray(al.clip(0, 255).astype(np.uint8)).save(out)
    _, ga = lum(out); res = np.abs(ga - gb)[y0:y1, x0:x1].mean()
    print(f'warp {np.round(warp, 4).tolist()}  residual {res:.1f} (roi mean abs lum diff)')


if __name__ == '__main__':
    a = sys.argv[1:]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    main(a[0], a[1], a[2], [int(v) for v in opt('--roi').split(',')], opt('--motion', 'affine'))
