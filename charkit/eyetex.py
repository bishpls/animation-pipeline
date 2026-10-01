"""Eye textures drawn in numpy (resolution-independent knobs; exported as images so VRM/three.js get the same eyes): the sclera
(with the upper lid's shadow), the iris (a HoYo-style layered iris: dark top, lit bottom, limbal ring, striations, pupil, the
bottom glow) and the shine (fixed highlights). Texture space = the eye plate's UV: u = x / (SPAN W) + 0.5 (x outward),
v = z / (SPAN W) + 0.5.
"""
import math
import numpy as np

SPAN = 1.25          # eye widths a texture's side covers (UV 0..1). It was 1: an iris raised to sit inscribed in the
                     # opening (tool/face6: centre +0.105, half-height 0.425) reached 0.53 eye widths up, past the
                     # texture's edge, which cut its top flat (and the three-quarter far eye's iris read 1.45 tall)
TEX_N = 640          # texels a side (512 at SPAN 1: the same texels per eye width)

DEFAULT_IRIS = {
    'top': (0.10, 0.16, 0.42),     # sRGB: the iris's shadowed top
    'mid': (0.20, 0.42, 0.80),
    'bottom': (0.55, 0.85, 1.00),  # the lit bottom glow
    'ring': (0.05, 0.07, 0.20),    # the limbal ring and the pupil
    'pupil': (0.04, 0.05, 0.14),
    'sclera': (0.97, 0.96, 0.98),
    'sclera_shadow': (0.72, 0.74, 0.86),
    'rx': 0.27,                    # iris half-width, in eye widths
    'rz': 0.37,                    # iris half-height (taller than the opening: the lids clip it)
    'cz': -0.01,                   # iris centre above the eye centre
    'pupil_rx': 0.085, 'pupil_rz': 0.135,
    'pupil_cz': -0.01,             # the pupil's centre above the iris's (eye widths): the lids clip a tall iris, so the
                                   # pupil sits in the middle of what shows, not of the whole iris
    'striation': 0.25,             # strength of the radial fibres
    'glow': 0.8,                   # the bottom crescent
    'lid_shadow': 0.45,            # how much the upper lid's shadow darkens the iris's top (0: none; an iris inscribed
                                   # in the opening shows its whole top, drawn in its own top colour)
    'shine': [                     # (u offset, v offset, rx, rz, alpha) from the iris centre, in eye widths
        (-0.085, 0.14, 0.075, 0.062, 1.0),
        (0.10, -0.12, 0.030, 0.030, 0.9),
        (0.02, 0.16, 0.022, 0.018, 0.7),
    ],
    'converge': 0.0,               # the irises' rest place toward the nose, in eye widths (a drawing's gaze at the viewer)
    'shine_mirror': True,          # u runs outward in each eye, so the shine mirrors (both toward the nose); False: both
                                   # eyes lit from one side, the right eye's shine flipped (shine(K, side=-1))
}


def _knobs(k):
    K = dict(DEFAULT_IRIS); K.update(k or {})
    return K


def _srgb_to_lin(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _grid(n):
    u = (np.arange(n) + 0.5) / n
    U, Vv = np.meshgrid(u, u[::-1])          # row 0 = top (v = 1)
    return (U - 0.5) * SPAN, (Vv - 0.5) * SPAN       # eye widths from the eye centre


def _ss(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def _mix(a, b, t):
    return a + (b - a) * t[..., None]


def sclera(K=None, n=TEX_N, upper=0.20, soft=0.10):
    """RGBA: white with a cool shadow under the upper lid (a band from `upper` - soft up)."""
    K = _knobs(K)
    x, z = _grid(n)
    t = _ss(upper - soft, upper + 0.05, z)
    rgb = _mix(np.array(K['sclera'], float) * np.ones(x.shape + (3,)), np.array(K['sclera_shadow'], float), t * 0.9)
    # a faint corner shading toward the eye's ends
    rgb = rgb * (1 - 0.08 * _ss(0.30, 0.55, np.abs(x)))[..., None]
    return np.concatenate([rgb, np.ones(x.shape + (1,))], -1)


def iris(K=None, n=TEX_N):
    """RGBA (alpha = the iris), centred at (0, cz) in eye widths."""
    K = _knobs(K)
    x, z = _grid(n)
    zc = z - K['cz']
    r = np.sqrt((x / K['rx']) ** 2 + (zc / K['rz']) ** 2)
    # vertical gradient: shadowed top -> mid -> glowing bottom
    h = np.clip((zc / K['rz'] + 1) / 2, 0, 1)                    # 0 bottom .. 1 top
    top, mid, bot = (np.array(K[k], float) for k in ('top', 'mid', 'bottom'))
    rgb = np.where(h[..., None] > 0.5, _mix(mid, top, (h - 0.5) * 2), _mix(bot, mid, _ss(0.0, 0.5, h)))
    # fibres: radial streaks
    ang = np.arctan2(x, zc)
    fib = 0.5 + 0.5 * np.sin(ang * 38 + np.sin(ang * 7) * 2.0) * np.sin(ang * 23 + 1.3)
    rgb = rgb * (1 - K['striation'] * 0.35 * fib * _ss(0.35, 0.9, r))[..., None]
    # the bottom crescent glow (inside the ring, lower half)
    cres = _ss(0.55, 0.85, r) * (1 - _ss(0.88, 0.95, r)) * _ss(0.1, -0.5, zc / K['rz'])
    rgb = _mix(rgb, np.minimum(1, bot * 1.15 + 0.1), cres * K['glow'])
    # limbal ring
    ring = _ss(0.80, 0.97, r)
    rgb = _mix(rgb, np.array(K['ring'], float), ring)
    # pupil
    pr = np.sqrt((x / K['pupil_rx']) ** 2 + ((zc - K['pupil_cz']) / K['pupil_rz']) ** 2)
    rgb = _mix(rgb, np.array(K['pupil'], float), 1 - _ss(0.92, 1.05, pr))
    # the lid's shadow over the top of the iris
    rgb = rgb * (1 - K['lid_shadow'] * _ss(0.05, 0.28, z))[..., None]
    a = 1 - _ss(0.985, 1.03, r)
    return np.concatenate([np.clip(rgb, 0, 1), a[..., None]], -1)


def shine(K=None, n=TEX_N, side=1):
    """RGBA: the highlights (white, alpha), placed from the iris centre. side: the eye (1 her left, -1 her right): with
    K['shine_mirror'] off, the right eye's shine is flipped across the iris, so both eyes' sit on the same side of the
    face (one light), as a drawing lights them."""
    K = _knobs(K)
    x, z = _grid(n)
    a = np.zeros(x.shape)
    flip = -1.0 if (side < 0 and not K.get('shine_mirror', True)) else 1.0
    for du, dv, rx, rz, al in K['shine']:
        du = flip * du
        r = np.sqrt(((x - du) / rx) ** 2 + ((z - K['cz'] - dv) / rz) ** 2)
        a = np.maximum(a, al * (1 - _ss(0.85, 1.0, r)))
    rgb = np.ones(x.shape + (3,))
    return np.concatenate([rgb, a[..., None]], -1)


def to_blender_image(name, rgba, linear=False):
    """a packed Blender image from an (n, n, 4) sRGB array (row 0 = top)."""
    import bpy
    n = rgba.shape[0]
    img = bpy.data.images.get(name) or bpy.data.images.new(name, n, n, alpha=True)
    px = rgba[::-1].astype(np.float32).copy()                 # Blender rows run bottom-up
    img.pixels.foreach_set(px.ravel())
    img.pack()
    return img


def save_png(path, rgba):
    from PIL import Image
    Image.fromarray((np.clip(rgba, 0, 1) * 255).astype(np.uint8), 'RGBA').save(path)
