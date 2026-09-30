"""A head's sections shaded in numpy, fast (no Blender): the z-buffer of the sections' mesh at an azimuth, normals from
its depth, a key light from the upper front left, drawn two ways side by side: a two-tone toon ramp (the terminator's
shape is what a cel-shaded render shows) and smooth Lambert. -> RGB uint8."""
import numpy as np
from charkit.faceqa import zbuffer
from charkit.geom.headgeom import sections_mesh

WIN = dict(x=0.55, top=0.35, bottom=-0.6)
PIX = 0.0025


def depth(S, az, win=WIN, pix=PIX):
    m = sections_mesh(S, step=1)
    D, lab = zbuffer([(np.asarray(m.V, float), np.asarray(m.F), np.zeros(len(m.F), int))], az, (0.0, 0.0), 1.0, pix, win)
    return np.where(lab >= 0, D, np.nan)


def shade(S, az, light=(0.55, -0.66, 0.42), thresh=0.35, win=WIN, pix=PIX):
    D = depth(S, az, win, pix)
    gz, gu = np.gradient(D, pix)                   # rows run down (z falls), columns right (u rises)
    a = np.radians(az)
    # camera frame: u right, z up, d away from the camera; normal toward the camera (-d)
    n = np.stack([gu, -gz, -np.ones_like(D)], -1)  # (du, dz, dd): d grows away (rows run down), the surface faces -d
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    lw = np.array(light, float); lw /= np.linalg.norm(lw)
    # the world light into the camera frame: u = x cos a + y sin a, d = -x sin a + y cos a
    lc = np.array([lw[0] * np.cos(a) + lw[1] * np.sin(a), lw[2], -lw[0] * np.sin(a) + lw[1] * np.cos(a)])
    ndl = np.nan_to_num((n * lc).sum(-1), nan=-2)
    ok = np.isfinite(D)
    toon = np.where(ndl > thresh, 1.0, 0.62)
    lam = np.clip(0.25 + 0.75 * ndl, 0.25, 1.0)
    skin = np.array([0.98, 0.86, 0.78])
    bg = np.array([0.93, 0.94, 0.96])
    img = []
    for v in (toon, lam):
        c = np.where(ok[..., None], v[..., None] * skin, bg)
        img.append(c)
    gap = np.ones((D.shape[0], 6, 3))
    return (np.concatenate([img[0], gap, img[1]], 1) * 255).astype(np.uint8)
