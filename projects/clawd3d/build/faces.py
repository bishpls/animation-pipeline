"""Clawd's face decals for the 3D head, cut from TSUZUKU's 2D rig so the 3D face is the drawn face (no redraw).
Composes the rig's registered layers (eyes + brows, and the mouth) into square RGBA textures over one face window of the
base drawing: out/tex/eyes_<state>.png (open, half, closed, happy) and out/tex/mouth_<shape>.png (rest + the rig's visemes).
The window is written to out/tex/window.json so the head build maps the decals with the same numbers.
    ~/animation-pipeline/.venv/bin/python projects/clawd3d/build/faces.py
"""
import json, os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
RIG = os.path.expanduser('~/animation-pipeline/projects/tsuzuku/rig/clawd/build')
OUT = os.path.join(PROJ, 'out', 'tex')
WIN = (848, 400, 440)          # x, y, size in base-drawing px: brows to below the mouth, centred between the eyes
SIZE = 1024


OWN = os.path.join(PROJ, 'rig', 'build')          # Clawd 3D's own extra variants (rig/expressions.json)
EXTRA_EYES = ['surprised', 'determined', 'soft', 'wink']


def layer(name, var=None):
    man = json.load(open(os.path.join(RIG, 'manifest.json')))['layers']
    if var:
        for d in (OWN, RIG):
            vj = os.path.join(d, 'variants.json')
            if os.path.exists(vj):
                table = json.load(open(vj))
                if var in table.get(name, {}):
                    v = table[name][var]
                    return Image.open(os.path.join(d, v['file'])).convert('RGBA'), (v['x'], v['y'])
        raise KeyError(f'{name}@{var}')
    L = next(l for l in man if l['name'] == name)
    return Image.open(os.path.join(RIG, f'{name}.png')).convert('RGBA'), (L['x'], L['y'])


SKIN = (253 / 255, 219 / 255, 196 / 255)


def skin_key(im):
    """Make the drawing's own skin transparent, so a decal carries only lines, eyes and mouth and the 3D face's shading
    (the SDF shadow) shows through; otherwise the lit skin around a feature glows as a halo on the shadowed side."""
    import numpy as np
    a = np.asarray(im).astype(np.float32) / 255
    d = np.sqrt(((a[..., :3] - np.array(SKIN, np.float32)) ** 2).sum(-1))
    k = np.clip((d - 0.05) / 0.09, 0, 1)
    a[..., 3] *= k
    return Image.fromarray((a * 255 + 0.5).astype(np.uint8), 'RGBA')


def compose(parts, key=True):
    x0, y0, s = WIN
    canvas = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    for im, (x, y) in parts:
        canvas.alpha_composite(im, (x - x0, y - y0))
    if key:
        canvas = skin_key(canvas)
    return canvas.resize((SIZE, SIZE), Image.LANCZOS)


def split_eye(im):
    """one drawn open eye -> RGBA layers of the same size, which composite back to the drawing:
      white  the eye white, filled in under the iris (with the upper lid's shadow)
      iris   the iris ellipse with its ring and pupil, the shine painted out (so it can slide for gaze)
      shine  the highlights, fixed in the eye (HoYo convention: the eye moves under its light)
      lines  lashes, lid lines and the skin surround, over everything
      mask   the opening, to clip the sliding iris
    The iris is an ellipse fitted to the amber region's moments, grown to take the dark ring."""
    import numpy as np
    from scipy import ndimage as ndi
    a = np.asarray(im).astype(np.float32) / 255
    rgb, al = a[..., :3], a[..., 3]
    mx, mn = rgb.max(-1), rgb.min(-1)
    sat = (mx - mn) / np.maximum(mx, 1e-4)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    d = np.maximum(mx - mn, 1e-4)
    hue = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) / 6
    lum = rgb @ np.array([0.3, 0.59, 0.11], np.float32)
    amber = (al > 0.5) & (hue > 0.07) & (hue < 0.17) & (sat > 0.35) & (lum > 0.3)
    lab, n = ndi.label(amber)
    big = ndi.binary_fill_holes(lab == (1 + np.argmax(ndi.sum(amber, lab, range(1, n + 1)))))
    ys, xs = np.nonzero(big)
    cy, cx = ys.mean(), xs.mean()
    cov = np.cov(np.vstack([xs - cx, ys - cy]))
    ev, evec = np.linalg.eigh(cov)
    Y, X = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    P = np.stack([X - cx, Y - cy], -1) @ evec                      # ellipse frame
    radii = 2.0 * np.sqrt(ev) * 1.18                                # 2 sigma = the filled region edge; +18% for the ring
    rr = np.sqrt((P[..., 0] / radii[0]) ** 2 + (P[..., 1] / radii[1]) ** 2)
    iris = rr <= 1.0
    whiteish = (al > 0.5) & (sat < 0.18) & (lum > 0.6)
    opening = ndi.binary_fill_holes(ndi.binary_closing(whiteish | iris, iterations=3)) & (al > 0.3)
    # the shine: bright blobs touching the iris
    near = ndi.binary_dilation(iris, iterations=2)
    blobs, nb = ndi.label(whiteish & ndi.binary_dilation(iris, iterations=1) | (whiteish & near))
    shine = np.zeros_like(iris)
    for k in range(1, nb + 1):
        m = blobs == k
        if (m & iris).sum() > 4:
            shine |= m
    shine = ndi.binary_dilation(shine, iterations=1) & (al > 0.3)
    # iris colours under the shine: normalised convolution of the rest of the iris
    valid = (iris & ~shine).astype(np.float32)
    num = np.stack([ndi.gaussian_filter(rgb[..., c] * valid, 4) for c in range(3)], -1)
    den = ndi.gaussian_filter(valid, 4)[..., None]
    fill = num / np.maximum(den, 1e-4)
    iris_rgb = np.where(shine[..., None], fill, rgb)
    ok = whiteish & opening & ~iris & ~shine
    sclera = np.median(rgb[ok], axis=0) if ok.any() else np.array([0.96, 0.95, 0.96])
    shade = np.median(rgb[ok & (lum < np.median(lum[ok]))], axis=0) if ok.any() else sclera * 0.85
    yo = np.nonzero(opening.any(1))[0]
    top = yo.min() if len(yo) else 0
    k = np.clip((np.arange(a.shape[0]) - top) / 18.0, 0, 1)[:, None, None]
    wfill = shade * (1 - k) + sclera * k
    edge = np.clip((1.0 - rr) * radii.min() / 1.2, 0, 1)            # a 1-2 px soft edge on the ellipse
    out = {
        'white': np.dstack([np.where((ok)[..., None], rgb, wfill), opening.astype(np.float32)]),
        'iris': np.dstack([iris_rgb, (edge * (al > 0.3)).astype(np.float32)]),
        'shine': np.dstack([rgb, (shine & opening).astype(np.float32) * al]),
        'lines': np.dstack([rgb, np.where(~iris & ~(opening & (whiteish | shine)), al, 0)]),
        'mask': np.dstack([np.ones_like(rgb), opening.astype(np.float32)]),
    }
    return {k: Image.fromarray((np.clip(v, 0, 1) * 255).astype(np.uint8), 'RGBA') for k, v in out.items()}


def main():
    os.makedirs(OUT, exist_ok=True)
    # the open eyes as layers, for gaze (clawd.eye_material slides the iris inside the opening)
    parts = {k: [] for k in ('white', 'iris', 'shine', 'lines', 'mask')}
    for n in ('eye_L', 'eye_R'):
        im, pos = layer(n)
        for k, v in split_eye(im).items():
            parts[k].append((v, pos))
    for k, v in parts.items():
        extra = [] if k != 'lines' else [layer('brow_R')]
        if k == 'lines':
            bl, (bx, by) = layer('brow_L'); cut = 440 - by
            extra.append((bl.crop((0, cut, bl.width, bl.height)), (bx, by + cut)))
        compose(v + extra, key=(k == 'lines')).save(os.path.join(OUT, f'eyes_open_{k}.png'))
    bl, (bx, by) = layer('brow_L')
    cut = 440 - by                  # brow_L's cell also holds a bang strand above the brow (the bangs are 3D here)
    brows = [(bl.crop((0, cut, bl.width, bl.height)), (bx, by + cut)), layer('brow_R')]
    for state in ('open', 'half', 'closed', 'happy') + tuple(EXTRA_EYES):
        v = None if state == 'open' else state
        compose([layer('eye_L', v), layer('eye_R', v)] + brows).save(os.path.join(OUT, f'eyes_{state}.png'))
    mouths = ['rest'] + list(json.load(open(os.path.join(RIG, 'variants.json')))['mouth'].keys())
    for m in mouths:
        compose([layer('mouth', None if m == 'rest' else m)]).save(os.path.join(OUT, f'mouth_{m}.png'))
    json.dump({'window': WIN, 'size': SIZE, 'eyes': ['open', 'half', 'closed', 'happy'] + EXTRA_EYES, 'mouths': mouths},
              open(os.path.join(OUT, 'window.json'), 'w'), indent=1)
    print('eyes: 4, mouths:', len(mouths), '->', OUT)


if __name__ == '__main__':
    main()
