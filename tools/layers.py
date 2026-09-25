"""Split a cel-shaded illustration into rig layers along its own drawn lines.

    .venv/bin/python tools/layers.py BASE.png LAYERS.json SEG_DIR OUT_DIR

The masks in SEG_DIR (tools/segment.py, SAM) only VOTE. The image is cut into cells: the flat-colour regions between drawn
lines (dark and thin; dark *fills* like shorts stay regions). Each cell goes whole to the part whose mask covers most of it,
so boundaries follow the artist's lines exactly. Each line pixel then goes to the front-most part within `line_r` px, so
every layer keeps its own outline. The layer pixels are always the base's pixels.

LAYERS.json:
  "order":  [front ... back]  part names, front-most first (decides overlaps and who owns a shared line)
  "split":  {"part": [["newpart", [[x, y], ...polygon]], ...]}  carve a part by polygons (e.g. hair into bangs/sides/back)
  "force":  {"part": [[x, y], ...]}  the cell under each point goes to this part (fixes wrong votes)
  "line_r": 9
Writes OUT_DIR/<part>.png (full-canvas RGBA), OUT_DIR/labels.png (index map), OUT_DIR/_labels.png and OUT_DIR/_sheet.png (review).
"""
import json, os, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi


def polymask(shape, poly):
    from PIL import ImageDraw
    im = Image.new('L', (shape[1], shape[0]), 0); ImageDraw.Draw(im).polygon([tuple(p) for p in poly], fill=255)
    return np.array(im) > 127


def main(base, spec, seg, out):
    S = json.load(open(spec)); os.makedirs(out, exist_ok=True)
    B = np.array(Image.open(base).convert('RGBA')); A = B[:, :, 3] > 8; rgb = B[:, :, :3].astype(float)
    lum = rgb @ [.299, .587, .114]
    dark = (lum < S.get('line_lum', 80)) & A
    thick = ndi.binary_opening(dark, structure=np.ones((3, 3)), iterations=S.get('line_open', 5))   # dark fills survive the opening
    thick = ndi.binary_dilation(thick, iterations=S.get('line_open', 5)) & dark
    line = (dark & ~thick) | (A & (B[:, :, 3] < 200))                                              # thin dark strokes + soft alpha edge
    if S.get('line_grow'): line = ndi.binary_dilation(line, iterations=S['line_grow']) & A   # seal hairline gaps between cells
    # dark fills (shorts, hems) swallow the lines around them, so they're labelled apart from the light regions
    c1, n1 = ndi.label(A & ~line & ~thick); c2, n2 = ndi.label(A & ~line & thick)
    cells = c1 + np.where(c2 > 0, c2 + n1, 0); nc = n1 + n2
    order = S['order']; idx = {n: i + 1 for i, n in enumerate(order)}
    # votes: SAM masks (after splits), per cell
    masks = {}
    for n in order + list(S.get('split', {})):
        p = os.path.join(seg, n + '.png')
        if os.path.exists(p): masks[n] = np.array(Image.open(p)) > 127
    for src, subs in S.get('split', {}).items():
        m = masks.pop(src)
        for new, poly in subs:
            masks[new] = m & polymask(m.shape, poly); m = m & ~masks[new]
        if src in order: masks[src] = m
    area = ndi.sum(np.ones_like(cells), cells, index=np.arange(nc + 1))
    best = np.zeros(nc + 1); lab_of = np.zeros(nc + 1, int)
    for n in reversed(order):                     # front parts processed last win ties
        if n not in masks: continue
        f = ndi.sum(masks[n], cells, index=np.arange(nc + 1)) / np.maximum(area, 1)
        take = f >= best; take &= f > .25; best[take] = f[take]; lab_of[take] = idx[n]
    lab_of[0] = 0
    L = lab_of[cells]
    for n, pts in S.get('force', {}).items():
        for x, y in pts:
            c = cells[int(y), int(x)]
            if c: L[cells == c] = idx[n]
    # unassigned cells: nearest assigned pixel
    un = A & ~line & (L == 0)
    if un.any():
        _, (iy, ix) = ndi.distance_transform_edt(L == 0, return_indices=True); L[un] = L[iy[un], ix[un]]
    # line pixels: the front-most label within line_r
    r = S.get('line_r', 9); lines = A & (L == 0)
    best_i = np.full(L.shape, 10 ** 6)
    for n in order:
        k = idx[n]; near = ndi.binary_dilation(L == k, iterations=r) & lines
        best_i[near] = np.minimum(best_i[near], k)
    L[lines & (best_i < 10 ** 6)] = best_i[lines & (best_i < 10 ** 6)]
    lines = A & (L == 0)
    if lines.any():
        _, (iy, ix) = ndi.distance_transform_edt(L == 0, return_indices=True); L[lines] = L[iy[lines], ix[lines]]
    # stray fragments: small pieces detached from a part's main body go to the part that surrounds them
    for n in order:
        k = idx[n]; lab, nn = ndi.label(L == k)
        if nn < 2: continue
        sz = ndi.sum(np.ones_like(lab), lab, index=np.arange(1, nn + 1)); main = int(np.argmax(sz)) + 1
        for c in range(1, nn + 1):
            if c == main or sz[c - 1] > S.get('min_frag', 600): continue
            m = lab == c; ring = ndi.binary_dilation(m, iterations=2) & ~m; nb = L[ring]; nb = nb[(nb != k) & (nb != 0)]
            if len(nb): L[m] = np.bincount(nb).argmax()
    # colour rules: a part keeps only cells whose mean colour is in range; the rest go to another part
    for n, (lo, hi, other) in S.get('colour', {}).items():
        for c in np.unique(cells[L == idx[n]]):
            if not c: continue
            mc = rgb[cells == c].mean(0)
            if not (np.all(mc >= lo) and np.all(mc <= hi)): L[(cells == c) & (L == idx[n])] = idx[other]
        stray = (L == idx[n]) & (cells == 0)                                   # its line pixels away from any kept cell
        keep = ndi.binary_dilation((L == idx[n]) & (cells > 0), iterations=S.get('line_r', 9))
        L[stray & ~keep] = idx[other]
    # claims: a part takes pixels near its SAM mask from named neighbours (e.g. the face takes its jawline back from the neck)
    for n, cl in S.get('claim', {}).items():
        if 'ellipse' in cl:                        # a patch: e.g. an eye with the skin around it, swapped as a unit
            cx, cy, rx, ry = cl['ellipse']; yy, xx = np.mgrid[:L.shape[0], :L.shape[1]]; zone = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1
        elif 'poly' in cl:                          # whole cells by majority, so the cut follows drawn lines (e.g. the jaw)
            pz = polymask(L.shape, cl['poly']); fr = ndi.mean(pz, cells, index=np.arange(nc + 1)); zone = (fr[cells] > .5) & (cells > 0)
            zone |= pz & (cells == 0) & ndi.binary_dilation(zone, iterations=S.get('line_r', 9))   # and the lines bordering those cells
        else: zone = ndi.binary_dilation(masks[n], iterations=cl.get('grow', 10))
        for other in cl['from']: L[zone & (L == idx[other])] = idx[n]
    Image.fromarray(L.astype(np.uint8)).save(os.path.join(out, 'labels.png'))
    json.dump({'order': order, 'size': [B.shape[1], B.shape[0]]}, open(os.path.join(out, 'labels.json'), 'w'))
    # layers
    for n in order:
        m = L == idx[n]; print(f'  {n:14s} {m.sum():8d} px')
        if not m.any(): print('EMPTY', n); continue
        lay = B.copy(); lay[~m, 3] = 0
        Image.fromarray(lay).save(os.path.join(out, n + '.png'))
    # review: label colours, and a contact sheet of every layer
    rng = np.random.default_rng(7); pal = rng.integers(30, 255, (len(order) + 1, 3)); pal[0] = 60
    ov = (rgb * .35 + pal[L] * .65).astype(np.uint8); ov[~A] = 90
    Image.fromarray(ov).save(os.path.join(out, '_labels.png'))
    tiles = []
    for n in order:
        p = os.path.join(out, n + '.png')
        if not os.path.exists(p): continue
        im = Image.open(p); bb = im.getbbox(); t = im.crop(bb); t.thumbnail((360, 360))
        cv = Image.new('RGBA', (380, 400), (235, 235, 235, 255)); cv.alpha_composite(t, ((380 - t.width) // 2, 10))
        from PIL import ImageDraw; ImageDraw.Draw(cv).text((6, 384), n, fill=(0, 0, 0, 255)); tiles.append(cv)
    cols = 8; rows = (len(tiles) + cols - 1) // cols; sh = Image.new('RGBA', (cols * 380, rows * 400), (255, 255, 255, 255))
    for i, t in enumerate(tiles): sh.alpha_composite(t, ((i % cols) * 380, (i // cols) * 400))
    sh.convert('RGB').save(os.path.join(out, '_sheet.png'))
    print(f'{nc} cells -> {len(order)} parts; wrote {out}')


if __name__ == '__main__':
    main(*sys.argv[1:5])
