"""Our boards against EEVEE's, pixel by pixel: the numbers that say whether the toon renderer draws what Blender draws.

    from charkit.render import compare
    m = compare.board(eevee_rgb, ours_rgb, palette)        # dict of the measures below
    compare.heatmap(eevee_rgb, ours_rgb)                   # (H, W, 3) uint8: the difference, coloured

Per board (8-bit sRGB, as the PNGs are):
  diff        per pixel the largest channel difference (levels): max, mean, p99, share over 8 and over 24 levels, and the
              same outside `exclude` (a mask of pixels to leave out; region_stats: the same inside a region, e.g. the
              hair streaks of either picture, streak_mask)
  silhouette  IoU of the character's pixels (farther than 6 levels from the background colour) and the share of pixels
              where exactly one of the two has the character
  lines       the dark ink (sRGB luma under 70) upsampled x4, its widths at each skeleton pixel (charkit.lookqa.widths):
              median, p10, p90 in output px, and the ink area ratio (ours / EEVEE's)
  tones       each pixel classified by the nearest colour of the look's palette (each material's lit / shade / deep, the
              face's lit / shade, flat colours, the lines, the background) where it lies within 6 levels of one (the flat
              interiors, not edges or blends): agreement where both are classified, and per tone class the IoU
"""
import numpy as np

TONES = ('bg', 'lit', 'shade', 'deep', 'face_lit', 'face_shade', 'flat', 'line')


def srgb8(c):
    c = np.clip(np.asarray(c, float), 0, None)
    s = np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)
    return np.round(np.clip(s, 0, 1) * 255)


def palette(M, bg):
    """the look's flat colours as 8-bit sRGB -> (colours (n, 3), tone class index (n,))."""
    cols, cls = [srgb8(bg)], [0]
    for L in M.materials:
        k = L.get('kind')
        if k in ('toon3', 'hair', 'face') and not L.get('texture'):
            for t, name in ((1, 'lit'), (2, 'shade'), (3, 'deep')):
                cols.append(srgb8(L[name])); cls.append(t)
        if k == 'face':
            cols.append(srgb8(L['face']['lit'])); cls.append(4)
            cols.append(srgb8(L['face']['shade'])); cls.append(5)
        if k == 'flat':
            cols.append(srgb8(L['color'])); cls.append(6)
    for P in M.prims:
        if P.outline:
            cols.append(srgb8(P.outline['color'])); cls.append(7)
    C, K = np.array(cols), np.array(cls)
    _, first = np.unique(C, axis=0, return_index=True)          # a colour two tone classes share: its first class
    return C[np.sort(first)], K[np.sort(first)]


def classify(img, pal, tol=6.0):
    """(H, W) tone class per pixel (-1: not within tol levels of any palette colour)."""
    C, K = pal
    x = img.reshape(-1, 3).astype(np.float32)
    best = np.full(len(x), np.inf, np.float32); lab = np.full(len(x), -1, np.int32)
    for c, k in zip(C.astype(np.float32), K):
        d = np.abs(x - c).max(1)
        m = d < best
        best[m] = d[m]; lab[m] = k
    lab[best > tol] = -1
    return lab.reshape(img.shape[:2])


def fg_mask(img, bg, tol=6):
    return np.abs(img.astype(np.int16) - srgb8(bg).astype(np.int16)).max(-1) > tol


def line_mask(img, up=4, thresh=70.0):
    from scipy import ndimage
    luma = img[..., :3].astype(np.float32) @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    if up > 1:
        luma = ndimage.zoom(luma, up, order=1)
    return luma < thresh


INK_LUMA = 8.0                              # the ink's luma (sRGB levels): the look's ink #0f0606


def ink_coverage(img, win=7):
    """per pixel the share of it the ink covers, from its luma between the ink's and its surroundings' (the brightest
    luma within win px: the surface the line is drawn on) -> (H, W) float 0..1."""
    from scipy import ndimage
    luma = img[..., :3].astype(np.float32) @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    surround = ndimage.maximum_filter(luma, size=win)
    return np.clip((surround - luma) / np.maximum(surround - INK_LUMA, 30.0), 0, 1)


def line_stats(img, up=4):
    """the ink's widths: at each skeleton pixel of the upsampled dark mask (charkit.lookqa.widths), and on average from
    its coverage (the ink's area over its skeleton's length: sub-pixel, not stepped by the mask's grid)."""
    from charkit import lookqa
    from skimage.morphology import skeletonize
    m = line_mask(img, up)
    w = lookqa.widths(m, up)
    if not len(w):
        return {'n': 0}
    cov = ink_coverage(img)
    lines = cov > 0.5
    length = float(skeletonize(lines).sum())
    thin = lines & (lookqa_width_map(lines) <= 6)                  # the drawn lines, not the pupils' and lashes' areas
    return {'median': round(float(np.median(w)), 3), 'p10': round(float(np.percentile(w, 10)), 3),
            'p90': round(float(np.percentile(w, 90)), 3), 'area_px': round(float(m.sum()) / up / up, 1), 'n': int(len(w)),
            'ink_px': round(float(cov[thin].sum()), 1), 'length_px': length,
            'mean_width': round(float(cov[thin].sum()) / max(float(skeletonize(thin).sum()), 1.0), 4)}


def lookqa_width_map(mask):
    """each mask pixel's local width: twice its distance to the mask's edge, spread over the mask (grey dilation of the
    distance transform within it)."""
    from scipy import ndimage
    d = ndimage.distance_transform_edt(mask)
    return np.where(mask, 2 * ndimage.maximum_filter(d, size=5), 0)


def board(ref, ours, pal=None, bg=(0.86, 0.86, 0.90), exclude=None):
    """EEVEE's picture (ref) against ours, both (H, W, 3) uint8 -> the measures (module doc)."""
    a, b = ref[..., :3].astype(np.int16), ours[..., :3].astype(np.int16)
    d = np.abs(a - b).max(-1)

    def stats(x):
        if not x.size:
            return {}
        return {'max': int(x.max()), 'mean': round(float(x.mean()), 3), 'p99': round(float(np.percentile(x, 99)), 1),
                'over8': round(float((x > 8).mean()), 5), 'over24': round(float((x > 24).mean()), 5)}
    out = {'diff': stats(d)}
    if exclude is not None and exclude.any():
        out['diff_excl'] = stats(d[~exclude])
        out['excluded_px'] = int(exclude.sum())
    fa, fb = fg_mask(ref, bg), fg_mask(ours, bg)
    out['silhouette'] = {'iou': round(float((fa & fb).sum() / max((fa | fb).sum(), 1)), 5),
                         'xor_px': int((fa ^ fb).sum()), 'fg_px': int(fa.sum())}
    la, lb = line_stats(ref), line_stats(ours)
    out['lines'] = {'eevee': la, 'ours': lb,
                    'area_ratio': round(lb.get('area_px', 0) / max(la.get('area_px', 0), 1e-9), 4),
                    'ink_ratio': round(lb.get('ink_px', 0) / max(la.get('ink_px', 0), 1e-9), 4),
                    'mean_width_diff_px': round(lb.get('mean_width', 0) - la.get('mean_width', 0), 4)}
    if pal is not None:
        ca, cb = classify(ref, pal), classify(ours, pal)
        both = (ca >= 0) & (cb >= 0)
        per = {}
        for k, name in enumerate(TONES):
            ma, mb = ca == k, cb == k
            u = (ma | mb).sum()
            if u:
                per[name] = round(float((ma & mb).sum() / u), 4)
        out['tones'] = {'agree': round(float((ca[both] == cb[both]).mean()), 5) if both.any() else None,
                        'classified_share': round(float(both.mean()), 4), 'iou': per}
    return out


def region_stats(ref, ours, region):
    """board()'s difference measures inside a region (bool (H, W)), plus its size."""
    d = np.abs(ref[..., :3].astype(np.int16) - ours[..., :3].astype(np.int16)).max(-1)[region]
    if not d.size:
        return {'px': 0}
    return {'px': int(d.size), 'max': int(d.max()), 'mean': round(float(d.mean()), 3),
            'p99': round(float(np.percentile(d, 99)), 1), 'over8': round(float((d > 8).mean()), 5),
            'over24': round(float((d > 24).mean()), 5)}


def streak_mask(ref, ours, base, M, grow=2):
    """the hair streaks of either picture: where ours differs from ours drawn without them (base), or where EEVEE's is
    brighter than base by 8+ levels on the hair's lit tone; grown by `grow` px. The region the streaks' own agreement is
    measured in (region_stats): their columns come from an integer hash (charkit.shade.streak_hash), the same on every
    GPU, so they are no longer left out."""
    from scipy import ndimage
    lits = [srgb8(L['lit']) for L in M.materials if L.get('highlight')]
    on_hair = np.zeros(base.shape[:2], bool)
    for c in lits:
        on_hair |= np.abs(base.astype(np.int16) - c.astype(np.int16)).max(-1) <= 6
    luma = lambda x: x[..., :3].astype(np.float32) @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    m = np.abs(ours.astype(np.int16) - base.astype(np.int16)).max(-1) > 4
    m |= on_hair & (luma(ref) - luma(base) > 8)
    return ndimage.binary_dilation(m, iterations=grow) if grow else m


RAMP = np.array([[0, 0, 0], [20, 30, 110], [40, 110, 200], [250, 200, 40], [255, 80, 40], [255, 255, 255]], float)
STOPS = np.array([0, 4, 8, 24, 64, 160], float)


def heatmap(ref, ours):
    """the per-pixel difference (largest channel, levels) coloured: black 0, blue 4-8, yellow 24, red 64, white 160+."""
    d = np.abs(ref[..., :3].astype(np.int16) - ours[..., :3].astype(np.int16)).max(-1).astype(float)
    out = np.stack([np.interp(d, STOPS, RAMP[:, c]) for c in range(3)], -1)
    return out.astype(np.uint8)
