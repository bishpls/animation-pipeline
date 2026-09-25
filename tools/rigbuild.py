"""Underpaint and export rig layers (after tools/layers.py): every region a motion can reveal gets painted, then each layer is
cropped and listed in a manifest the runtime (engine/rig.js) loads.

    .venv/bin/python tools/rigbuild.py LAYERS_DIR BUILD.json OUT_DIR

BUILD.json:
  "under": {"layer": {"hull": [other layers whose area it should also cover], "grow": px, "ellipse": [cx, cy, rx, ry],
                      "rect": [x0, y0, x1, y1], "clip": [x0, y0, x1, y1]}}
      The layer is extended over that area and the new pixels are filled from its own flat colours (OpenCV inpainting of the
      interior, lines excluded so they don't smear). The original pixels are kept on top, untouched.
  "plates": {"name": {"from": [layers], "grow": px, "colour": "shadow" | [r, g, b], "behind": "layer"}}
      New layers made from a region (e.g. the back-hair plate behind the head), filled flat.
Writes OUT_DIR/<layer>.png (cropped, premultiplied-safe RGBA), OUT_DIR/manifest.json {size, layers: [{name, x, y, w, h}]} in draw
order back-to-front, and OUT_DIR/_under.png (the underpaint shown in magenta, for review).
"""
import json, os, sys
import numpy as np, cv2
from PIL import Image
from scipy import ndimage as ndi


def load(p):
    return np.array(Image.open(p).convert('RGBA'))


def region(spec, L, shape):
    Z = np.zeros(shape, bool)
    for o in spec.get('hull', []): Z |= L[o][:, :, 3] > 8
    if 'ellipse' in spec:
        cx, cy, rx, ry = spec['ellipse']; yy, xx = np.mgrid[:shape[0], :shape[1]]; Z |= ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1
    if 'rect' in spec:
        x0, y0, x1, y1 = spec['rect']; Z[y0:y1, x0:x1] = True
    return Z


def fill_from(lay, hole, radius=12):
    """Fill `hole` with the layer's own flat colours: inpaint over (hole + its dark line pixels) so lines don't smear inward."""
    rgb = lay[:, :, :3].copy(); a = lay[:, :, 3] > 8
    lum = rgb.astype(float) @ [.299, .587, .114]
    dark = a & (lum < 90); thin = dark & ~ndi.binary_dilation(ndi.binary_opening(dark, iterations=5), iterations=5)   # lines, not dark fills
    unknown = hole | thin | ~a
    ys, xs = np.where(hole | a)
    if not len(ys): return lay
    y0, y1, x0, x1 = max(ys.min() - 20, 0), ys.max() + 20, max(xs.min() - 20, 0), xs.max() + 20       # work on the bbox only
    sub = cv2.inpaint(cv2.cvtColor(rgb[y0:y1, x0:x1], cv2.COLOR_RGB2BGR), (unknown[y0:y1, x0:x1] * 255).astype(np.uint8), radius, cv2.INPAINT_TELEA)
    out = lay.copy(); h = hole[y0:y1, x0:x1]
    out[y0:y1, x0:x1][h, :3] = cv2.cvtColor(sub, cv2.COLOR_BGR2RGB)[h]; out[y0:y1, x0:x1][h, 3] = 255
    return out


def main(ldir, spec, out):
    S = json.load(open(spec)); os.makedirs(out, exist_ok=True)
    meta = json.load(open(os.path.join(ldir, 'labels.json'))); order = meta['order']
    L = {n: load(os.path.join(ldir, n + '.png')) for n in order if os.path.exists(os.path.join(ldir, n + '.png'))}
    shape = next(iter(L.values())).shape[:2]; review = np.zeros(shape, bool)
    for n, sp in S.get('under', {}).items():
        a = L[n][:, :, 3] > 8; Z = region(sp, L, shape) | a
        if sp.get('grow'): Z = ndi.binary_dilation(Z, iterations=sp['grow'])
        Z = ndi.binary_fill_holes(Z)
        if 'clip' in sp:
            x0, y0, x1, y1 = sp['clip']; C = np.zeros(shape, bool); C[y0:y1, x0:x1] = True; Z &= C
        if sp.get('within_hull'):                  # never grow past the layer's own outline (no floating patches)
            hull = cv2.convexHull(np.argwhere(a)[:, ::-1].astype(np.int32)); H = np.zeros(shape, np.uint8); cv2.fillPoly(H, [hull], 1); Z &= H > 0
        hole = Z & ~a
        if 'flat' in sp:                           # a flat fill sampled from the layer inside a box (e.g. skin under the eyes)
            x0, y0, x1, y1 = sp['flat']; sm = L[n][y0:y1, x0:x1]; col = np.median(sm[sm[:, :, 3] > 200][:, :3], 0)
            F = sp.get('flat_zone'); fz = region(F, L, shape) & hole if F else np.zeros(shape, bool)
            L[n] = fill_from(L[n], hole & ~fz); L[n][fz, :3] = col.astype(np.uint8); L[n][fz, 3] = 255
        else: L[n] = fill_from(L[n], hole)
        review |= hole
        print(f'  under {n:12s} +{hole.sum():8d} px')
    for n, sp in S.get('plates', {}).items():
        Z = np.zeros(shape, bool)
        for o in sp['from']: Z |= L[o][:, :, 3] > 8
        Z = ndi.binary_fill_holes(Z); g = sp.get('grow', 0)
        if g > 0: Z = ndi.binary_dilation(Z, iterations=g)
        if g < 0: Z = ndi.binary_erosion(Z, iterations=-g)             # shrink: a plate must never peek out at rest
        src = np.concatenate([L[o][L[o][:, :, 3] > 8, :3] for o in sp['from']])
        lum = src.astype(float) @ [.299, .587, .114]
        col = np.median(src[(lum > np.percentile(lum, 15)) & (lum < np.percentile(lum, 40))], 0) if sp.get('colour', 'shadow') == 'shadow' else np.array(sp['colour'])
        P = np.zeros(shape + (4,), np.uint8); P[Z, :3] = col.astype(np.uint8); P[Z, 3] = 255
        L[n] = P; i = order.index(sp['behind']) + 1 if sp.get('behind') in order else len(order); order.insert(i, n)
        print(f'  plate {n:12s} {Z.sum():8d} px  colour {col.astype(int).tolist()}')
    # feather: patches (eyes, mouth) fade into the layer under them over `feather` px at their outer edge
    for n, px in S.get('feather', {}).items():
        a = L[n][:, :, 3] > 8; d = ndi.distance_transform_edt(a)
        L[n][:, :, 3] = (L[n][:, :, 3] * np.clip(d / px, 0, 1)).astype(np.uint8)
    # bleed: every layer extends a few px under the layers in front of it (no hairline seams when parts shift), then its
    # edge is anti-aliased (the cut masks are binary)
    bl = S.get('bleed', 3)
    if bl:
        cover = np.zeros(shape, bool)
        for n in order:                            # front to back
            if n not in L: continue
            lay = L[n]; a = lay[:, :, 3] > 8
            if n not in S.get('feather', {}):
                grow = ndi.binary_dilation(a, iterations=bl) & cover & ~a
                if grow.any():
                    _, (iy, ix) = ndi.distance_transform_edt(~a, return_indices=True)
                    lay[grow, :3] = lay[iy[grow], ix[grow], :3]; lay[grow, 3] = 255
                a2 = lay[:, :, 3] > 8; ring = ndi.binary_dilation(a2, iterations=3) & ~a2          # outside colour = the edge colour (no halo)
                if ring.any():
                    _, (iy, ix) = ndi.distance_transform_edt(~a2, return_indices=True); lay[ring, :3] = lay[iy[ring], ix[ring], :3]
                al = ndi.gaussian_filter(lay[:, :, 3].astype(float), S.get('aa', .8))
                lay[:, :, 3] = np.where(lay[:, :, 3] > 250, np.maximum(al, 0), al).clip(0, 255).astype(np.uint8)
            cover |= a
    man = {'size': [shape[1], shape[0]], 'layers': []}
    for n in reversed(order):                     # back to front
        if n not in L: continue
        lay = L[n]; ys, xs = np.where(lay[:, :, 3] > 0)
        if not len(ys): continue
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        Image.fromarray(lay[y0:y1, x0:x1]).save(os.path.join(out, n + '.png'))
        man['layers'].append({'name': n, 'x': int(x0), 'y': int(y0), 'w': int(x1 - x0), 'h': int(y1 - y0)})
    json.dump(man, open(os.path.join(out, 'manifest.json'), 'w'), indent=1)
    # review: the full composite with underpaint tinted
    comp = np.zeros(shape + (4,), float)
    for l in man['layers']:
        t = load(os.path.join(out, l['name'] + '.png')).astype(float) / 255; y, x, h, w = l['y'], l['x'], l['h'], l['w']
        a = t[:, :, 3:4]; comp[y:y + h, x:x + w] = comp[y:y + h, x:x + w] * (1 - a) + t * a
    rgb = comp[:, :, :3] * 255; rgb[review] = rgb[review] * .5 + np.array([255, 0, 255]) * .5
    bg = np.full(shape + (3,), 90.); a = comp[:, :, 3:4]; Image.fromarray((bg * (1 - a) + rgb * a).astype(np.uint8)).save(os.path.join(out, '_under.png'))
    print(f'wrote {len(man["layers"])} layers -> {out}')


if __name__ == '__main__':
    main(*sys.argv[1:4])
