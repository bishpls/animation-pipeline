"""Image helpers for rig builders: register drawings onto a base, match their colour, cut and composite layers (docs/RIGGING.md).
Every drawing is uint8 RGBA at the base's full canvas (tools/chroma.py key()); masks are bool or float 0..1 at the same size.

    sys.path.insert(0, '<repo>/tools'); from chroma import key; from rigkit import register, colour_match, feather, blend
    base = key('src/base.png'); al, warp = register(key('src/poses/wave.png'), base, fitmask)

Collected from TSUZUKU's Fable builders (projects/tsuzuku/rig/fable_seated, fable_stage, fable_room, fable_3q), which import them.
"""
import numpy as np, cv2
from scipy import ndimage as ndi


def lum(a):
    """luminance of an RGBA drawing, transparent read as white (float32)"""
    return ((a[..., :3].astype(np.float32) @ [.299, .587, .114]) * (a[..., 3] / 255) + 255 * (1 - a[..., 3] / 255)).astype(np.float32)


def register(img, base, mask, motion=cv2.MOTION_AFFINE):
    """img warped onto base (ECC on luminance, coarse to fine), fitted only on mask: the region the edit shouldn't have changed.
    Returns (aligned, warp)."""
    H, W = base.shape[:2]; warp = np.eye(2, 3, dtype=np.float32)
    for sc in (.125, .25, .5):
        a = cv2.GaussianBlur(cv2.resize(lum(base), None, fx=sc, fy=sc), (0, 0), 1.2)
        b = cv2.GaussianBlur(cv2.resize(lum(img), None, fx=sc, fy=sc), (0, 0), 1.2)
        w = warp.copy(); w[:, 2] *= sc
        _, w = cv2.findTransformECC(a, b, w, motion, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 300, 1e-6),
                                    cv2.resize(mask.astype(np.uint8), None, fx=sc, fy=sc, interpolation=cv2.INTER_NEAREST), 5)
        warp = w.copy(); warp[:, 2] /= sc
    al = cv2.warpAffine(img, warp, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderValue=(0, 0, 0, 0))
    return al, warp


def residual(al, base, mask):
    """mean absolute luminance difference on mask: a high one means the edit moved something it shouldn't have"""
    return float(np.abs(lum(al) - lum(base))[mask].mean())


def colour_match(al, base, k):
    """al's channels shifted and scaled to base's mean and spread on the pixels k (in place; returns al)"""
    for c in range(3):
        sa, sb = al[k, c].astype(float), base[k, c].astype(float)
        al[..., c] = np.clip((al[..., c] - sa.mean()) / (sa.std() + 1e-6) * sb.std() + sb.mean(), 0, 255).astype(np.uint8)
    return al


def shift(a, dx, dy):
    """a moved by (dx, dy) px"""
    return cv2.warpAffine(a, np.float32([[1, 0, dx], [0, 1, dy]]), (a.shape[1], a.shape[0]), flags=cv2.INTER_LINEAR, borderValue=0)


def feather(m, r):
    """a bool mask softened inward: 0 at its edge, 1 from r px inside"""
    d = ndi.distance_transform_edt(m); return np.clip(d / r, 0, 1)


def poly(shape, pts):
    """a filled polygon as a bool mask of shape (H, W)"""
    m = np.zeros(shape, np.uint8); cv2.fillPoly(m, [np.array(pts, np.int32)], 1); return m.astype(bool)


def with_alpha(img, m):
    """img with its alpha multiplied by m"""
    o = img.copy(); o[..., 3] = (img[..., 3].astype(np.float32) * np.clip(m, 0, 1)).astype(np.uint8); return o


def _pa(a):
    return np.dstack([a[..., :3].astype(np.float32) * (a[..., 3:] / 255), a[..., 3:].astype(np.float32)])


def _un(P):
    A = P[..., 3:]; rgb = np.where(A > 0, P[..., :3] / np.maximum(A, 1e-6) * 255, 0)
    return np.dstack([np.clip(rgb, 0, 255), np.clip(A, 0, 255)]).astype(np.uint8)


def over(dst, src):
    """src drawn over dst (premultiplied alpha)"""
    T, B = _pa(src), _pa(dst); return _un(T + B * (1 - T[..., 3:] / 255))


def blend(dst, src, m):
    """dst*(1-m) + src*m (premultiplied alpha): a patch of src laid into dst through the soft mask m"""
    return _un(_pa(dst) * (1 - m[..., None]) + _pa(src) * m[..., None])


def bleed(img, px=6):
    """colour pushed outward under transparent pixels (no dark fringes when a layer is scaled or rotated)"""
    a = img[..., 3] > 16; rgb = img[..., :3].copy()
    if not a.any(): return img
    d, (iy, ix) = ndi.distance_transform_edt(~a, return_indices=True); m = (~a) & (d <= px)
    rgb[m] = img[iy[m], ix[m], :3]; o = img.copy(); o[..., :3] = rgb; return o
