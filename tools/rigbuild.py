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
    orig = {n: L[n][:, :, 3] > 8 for n in L}                    # each layer's own drawn pixels (fills are everything else)
    shape = next(iter(L.values())).shape[:2]; review = np.zeros(shape, bool)
    inv = {n: np.zeros(shape, bool) for n in L}                 # INVENTED pixels (inpaint, flat fill, plate, tube), exported as
                                                                 # <layer>.inv.png so the ID pass can show when motion exposes them
    # fromimg: hidden parts of layers get REAL drawn pixels from a registered companion drawing that shows them (e.g. the same
    # character with her hair tied back: the full face outline, ears, neck, shoulders). Per target layer: the source labels it
    # takes; only where the target is empty, something covers that spot at rest (no change to the rest look), and not under
    # the excluded layers (eyes/mouth: variants swap there, so no second pair of eyes may sit underneath).
    FI = S.get('fromimg')
    if FI:
        base_a = load(os.path.join(os.path.dirname(spec), FI['base']))[:, :, 3] > 8
        V = load(os.path.join(os.path.dirname(spec), FI['img'])); lb = np.array(Image.open(os.path.join(os.path.dirname(spec), FI['labels'], 'labels.png')))
        vo = json.load(open(os.path.join(os.path.dirname(spec), FI['labels'], 'labels.json')))['order']
        ex = np.zeros(shape, bool)
        if 'clip' in FI:                             # only within this box (companion drawings are labelled coarsely elsewhere)
            x0, y0, x1, y1 = FI['clip']; ex[:] = True; ex[y0:y1, x0:x1] = False
        for o in FI.get('exclude', []):
            if o in L: ex |= ndi.binary_dilation(L[o][:, :, 3] > 8, iterations=FI.get('exclude_grow', 6))
        for t, names in FI['map'].items():
            if t not in L: continue
            m = np.isin(lb, [vo.index(n) + 1 for n in names if n in vo]) & (V[:, :, 3] > 200) & ~(L[t][:, :, 3] > 8) & base_a & ~ex
            L[t][m] = V[m]; review |= m; print(f'  fromimg {t:10s} +{m.sum():8d} px')
        SK = FI.get('skin')                        # skin by colour (face, ears and neck are one region in a drawing), each pixel to
        if SK:                                     # the NEAREST of the target layers (e.g. face above the jaw, neck below)
            sx, sy = SK['sample']; ref = np.median(V[sy - 6:sy + 6, sx - 6:sx + 6, :3].reshape(-1, 3), 0)
            lum = V[:, :, :3].astype(float) @ [.299, .587, .114]
            skin = (np.abs(V[:, :, :3].astype(float) - ref).max(2) < SK.get('tol', 38)) & (V[:, :, 3] > 200)
            skin |= ndi.binary_dilation(skin, iterations=3) & (lum < 90) & (V[:, :, 3] > 200)        # its own outline (the jawline)
            tg = [t for t in SK['targets'] if t in L]; dist = np.stack([ndi.distance_transform_edt(~(L[t][:, :, 3] > 8)) for t in tg]); near = np.argmin(dist, 0)
            anyT = np.zeros(shape, bool)
            for t in tg: anyT |= L[t][:, :, 3] > 8
            for i, t in enumerate(tg):
                m = skin & (near == i) & ~anyT & base_a & ~ex
                if 'ymax' in SK: m[SK['ymax']:] = False
                L[t][m] = V[m]; review |= m; print(f'  fromimg {t:10s} +{m.sum():8d} px (skin)')
    # cross-fill: body layers hidden under the hair get REAL drawn pixels from other registered views of the same body, wherever
    # a view shows that spot as body (e.g. a turned head's hair has moved off the shoulder). Each pixel goes to the nearest target.
    CF = S.get('crossfill')
    if CF:
        tg = [t for t in CF['targets'] if t in L]
        dist = []; 
        for t in tg:
            dist.append(ndi.distance_transform_edt(~(L[t][:, :, 3] > 8)))
        dist = np.stack(dist); near = np.argmin(dist, 0); reach = np.min(dist, 0) <= CF.get('reach', 140)
        filled = np.zeros(shape, bool); anyA = np.zeros(shape, bool)
        for t in tg: anyA |= L[t][:, :, 3] > 8
        for img, lab, lj, names in CF['sources']:
            V = load(os.path.join(os.path.dirname(spec), img)); lb = np.array(Image.open(os.path.join(os.path.dirname(spec), lab)))
            vo = json.load(open(os.path.join(os.path.dirname(spec), lj)))['order']; ok = np.isin(lb, [vo.index(n) + 1 for n in names if n in vo])
            ok &= (V[:, :, 3] > 200) & ~anyA & ~filled & reach
            for i, t in enumerate(tg):
                m = ok & (near == i); L[t][m] = V[m]; filled |= m
        review |= filled; print(f'  crossfill {filled.sum():8d} px from {len(CF["sources"])} views')
    for n, sp in S.get('under', {}).items():
        a = L[n][:, :, 3] > 8; Z = region(sp, L, shape) | a
        if sp.get('grow'): Z = ndi.binary_dilation(Z, iterations=sp['grow'])
        Z = ndi.binary_fill_holes(Z)
        if 'clip' in sp:
            x0, y0, x1, y1 = sp['clip']; C = np.zeros(shape, bool); C[y0:y1, x0:x1] = True; Z &= C
        for poly in sp.get('exclude', []):          # never fill here (e.g. a face fill must stop at the jaw, over the neck)
            from PIL import ImageDraw
            E = Image.new('L', (shape[1], shape[0]), 0); ImageDraw.Draw(E).polygon([tuple(q) for q in poly], fill=255); Z &= ~(np.array(E) > 127)
        if sp.get('within'):                        # only under these layers (e.g. a face fill only where hair covers it at rest)
            Wm = np.zeros(shape, bool)
            for o in sp['within']:
                if o in L: Wm |= L[o][:, :, 3] > 8
            Z &= Wm | (L[n][:, :, 3] > 8)
        if sp.get('within_hull'):                  # never grow past the layer's own outline (no floating patches)
            hull = cv2.convexHull(np.argwhere(a)[:, ::-1].astype(np.int32)); H = np.zeros(shape, np.uint8); cv2.fillPoly(H, [hull], 1); Z &= H > 0
        hole = Z & ~a
        if 'flat' in sp:                           # a flat fill sampled from the layer inside a box (e.g. skin under the eyes)
            x0, y0, x1, y1 = sp['flat']; sm = L[n][y0:y1, x0:x1]; col = np.median(sm[sm[:, :, 3] > 200][:, :3], 0)
            F = sp.get('flat_zone'); fz = region(F, L, shape) & hole if F else np.zeros(shape, bool)
            L[n] = fill_from(L[n], hole & ~fz); L[n][fz, :3] = col.astype(np.uint8); L[n][fz, 3] = 255
        else: L[n] = fill_from(L[n], hole)
        review |= hole; inv[n] |= hole
        print(f'  under {n:12s} +{hole.sum():8d} px')
    for n, T in S.get('tubes', {}).items():
        # two side lines [[x0, y0], [x1, y1]] (drawn contours, extended to their far ends); the band between them is filled with the
        # sampled tone and the lines are stroked in the sampled line colour; the layer's own pixels stay on top
        from PIL import ImageDraw
        lay = L[n]; H0, W0 = shape; im = Image.new('RGBA', (W0, H0), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        (a0, a1), (b0, b1) = T['left'], T['right']; fx, fy = T['fill']; col = tuple(int(v) for v in lay[fy, fx, :3]) if lay[fy, fx, 3] > 0 else tuple(T.get('fill_rgb', (230, 180, 170)))
        d.polygon([tuple(a0), tuple(a1), tuple(b1), tuple(b0)], fill=col + (255,))
        lc = tuple(T.get('line_rgb', (40, 22, 20))) + (255,)
        d.line([tuple(a0), tuple(a1)], fill=lc, width=T.get('line', 6)); d.line([tuple(b0), tuple(b1)], fill=lc, width=T.get('line', 6))
        ext = np.array(im); a = lay[:, :, 3:4].astype(float) / 255
        L[n] = (ext * (1 - a) + lay * a).astype(np.uint8); L[n][:, :, 3] = np.maximum(ext[:, :, 3], lay[:, :, 3]); inv[n] |= (ext[:, :, 3] > 0) & (lay[:, :, 3] < 8)
        print(f'  tube  {n:12s} extended')
    for n, sp in S.get('plates', {}).items():
        Z = np.zeros(shape, bool)
        for o in sp['from']:
            if o in L: Z |= L[o][:, :, 3] > 8
        Z = ndi.binary_fill_holes(Z); g = sp.get('grow', 0)
        if g > 0: Z = ndi.binary_dilation(Z, iterations=g)
        if g < 0: Z = ndi.binary_erosion(Z, iterations=-g)             # shrink: a plate must never peek out at rest
        src = np.concatenate([L[o][L[o][:, :, 3] > 8, :3] for o in sp['from'] if o in L and o != 'face'])
        lum = src.astype(float) @ [.299, .587, .114]
        col = np.median(src[(lum > np.percentile(lum, 15)) & (lum < np.percentile(lum, 40))], 0) if sp.get('colour', 'shadow') == 'shadow' else np.array(sp['colour'])
        P = np.zeros(shape + (4,), np.uint8); P[Z, :3] = col.astype(np.uint8); P[Z, 3] = 255
        inv[n] = Z.copy()
        if 'img' in sp:                            # real drawn back hair from a registered companion drawing, where it has some; the
            d0 = os.path.dirname(spec)             # plate extends to all of it (the build then hides whatever would show at rest)
            V = load(os.path.join(d0, sp['img'])); M = (np.array(Image.open(os.path.join(d0, sp['mask']))) > 127) & (V[:, :, 3] > 200)
            P[M] = V[M]; P[M, 3] = 255; inv[n][M] = False; Z |= M
            print(f'  plate {n:12s} drawn from {sp["img"]}: {M.sum()} px')
        L[n] = P; i = order.index(sp['behind']) + 1 if sp.get('behind') in order else len(order); order.insert(i, n)
        print(f'  plate {n:12s} {Z.sum():8d} px  colour {col.astype(int).tolist()}')
    # invariant: every filled pixel must be hidden at rest by an opaque drawn layer in front of it, so the rig at rest is exactly
    # the illustration. Front to back: remove fill pixels that nothing in front covers.
    cover = np.zeros(shape, bool); removed = 0
    for n in order:
        if n not in L: continue
        a = L[n][:, :, 3] > 8; o = orig.get(n, np.zeros(shape, bool)); leak = a & ~o & ~cover
        if S.get('hidden_only', True) and leak.any(): L[n][leak, 3] = 0; removed += leak.sum()
        cover |= (L[n][:, :, 3] > 250) & o                    # only drawn pixels count as cover (fills behind fills don't)
    print(f'  hidden-only: removed {removed} visible fill px')
    # feather: patches (eyes, mouth) fade into the layer under them over `feather` px at their outer edge
    for n, px in S.get('feather', {}).items():
        a = L[n][:, :, 3] > 8
        if isinstance(px, dict) and 'toward' in px:   # fade only the stretch of edge that borders these parts at rest (an eye fades
            lab = np.array(Image.open(os.path.join(ldir, 'labels.png'))); lo = json.load(open(os.path.join(ldir, 'labels.json')))['order']   # into skin, never over hair)
            ring = ndi.binary_dilation(a, iterations=2) & ~a; toward = ring & np.isin(lab, [lo.index(o) + 1 for o in px['toward'] if o in lo])
            d = ndi.distance_transform_edt(~toward); d[~a] = 0; hard = ring & ~toward
            dh = ndi.distance_transform_edt(~hard); d = np.where(dh < d, px['px'], d); px = px['px']   # near a hard edge: stay opaque
        elif isinstance(px, dict):                 # fade only toward the named neighbours (e.g. a yoke fades into the body, not the neck)
            seed = np.zeros(shape, bool)
            for o in px['from']: seed |= L[o][:, :, 3] > 8
            d = ndi.distance_transform_edt(~seed); px = px['px']
        else: d = ndi.distance_transform_edt(a)
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
        if n not in L or n in S.get('drop', []): continue
        lay = L[n]; ys, xs = np.where(lay[:, :, 3] > 0)
        if not len(ys): continue
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        Image.fromarray(lay[y0:y1, x0:x1]).save(os.path.join(out, n + '.png'))
        iv = inv.get(n, np.zeros(shape, bool)) & (lay[:, :, 3] > 0)
        Image.fromarray((iv[y0:y1, x0:x1] * 255).astype(np.uint8)).save(os.path.join(out, n + '.inv.png'))
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
