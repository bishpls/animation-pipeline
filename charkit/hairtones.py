"""The hair's cel tones against the design's (tool/hairstrokes, the tones milestone; Michael, 2026-10-01: the drawn shadow
and highlight shapes per lock). On the body sheet's design grids (the QA's frames, charkit.declared's), inside the hair
where both draw it, off both drawings' lines:

  shadow     the design's shade tone (its hair's value under the midpoint of its two tones: a two-means split of the
             hair's values off its lines and marks) against ours (the QA's cel tone buffer, shade or deep: tone >= 0.5):
             their IoU in the zone. The drawn shadow: the lower halves of the locks, the back's hem lobes, the buns'
             lower faces, a band under the bangs
  highlight  the design's highlight marks (value HL_OVER over its lit tone: the short pale marks on the crown and the
             bangs) against ours (our picture's value HL_OVER over our lit tone), graded as the strands are (the views
             draw their marks view by view; the canonical rule's step 3: the intent graded, exact placement each view's
             cost): their density fields (a Gaussian at HL_SCALE L over the zone), the L1 difference over their sum (0
             the same marks, 1 none where the other has them); F1 within HL_TOL L (recall: the drawn marks' pixels with
             one of ours near; precision: ours with a drawn one near) reported beside it, the exact placement

    T = design_tones(dv_view, hair_mask)       # dict(shade, mark, zone, lit, shade_v)
    O = our_tones(B, ppl, az3, views)          # {view: dict(tone, value, hair)} on the design grids
"""
import numpy as np


HL_OVER = 0.06          # value over the lit tone: a highlight mark
HL_TOL = 0.02           # L: a mark this near another counts as matched (the exact placement, reported)
HL_SCALE = 0.06         # L: the highlight density fields' Gaussian (the band's scale: a mark's length)
LINE_PAD = 1            # px: the lines' own pixels and this round them are left out of the zone


def two_tones(val):
    """a hair's lit and shade values: two-means on its values (the drawing's two cel tones) -> (lit, shade)."""
    v = np.sort(np.asarray(val, float))
    if len(v) < 20:
        return float(v.max()) if len(v) else 1.0, float(v.min()) if len(v) else 0.0
    a, b = np.percentile(v, 80), np.percentile(v, 20)
    for _ in range(20):
        t = 0.5 * (a + b)
        hi, lo = v[v >= t], v[v < t]
        if not len(hi) or not len(lo):
            break
        a, b = float(hi.mean()), float(lo.mean())
    return float(np.median(v[v >= 0.5 * (a + b)])), float(np.median(v[v < 0.5 * (a + b)]))


def design_tones(dv, hair):
    """the design's hair tones in a view on its grid: dict(shade, mark (highlight), inside (the hair off its lines),
    lit, shade_v) or None. dv: bodyqa.design_views' view (rgb, cls); hair: the drawn hair (hairflagqa.drawn_hair)."""
    from scipy import ndimage
    from . import hairflagqa
    rgb = np.asarray(dv['rgb'], float)
    rgb = rgb / 255.0 if rgb.max() > 1.5 else rgb
    sh = hair.shape
    rgb = rgb[:sh[0], :sh[1]]
    if rgb.shape[:2] != sh:
        return None
    lines = hairflagqa.drawn_lines(dv)[:sh[0], :sh[1]]
    inside = hair & ~ndimage.binary_dilation(lines, iterations=LINE_PAD)
    if inside.sum() < 50:
        return None
    val = rgb.max(-1)
    lit, shade_v = two_tones(val[inside & (val < np.percentile(val[inside], 99))])
    return dict(shade=inside & (val < 0.5 * (lit + shade_v)), mark=inside & (val > lit + HL_OVER), inside=inside,
                lit=lit, shade_v=shade_v)


def our_tones(B, ppl, az3, views):
    """our hair's cel tones per view on the design's grids (the QA's numpy drawing, qa3d.draw under the boards' light
    for each view, as the strokes' and lines' images are drawn: declared._Grid): dict(tone (0 lit .. 1 shade .. 2
    deep, NaN off the toon materials), value (the picture's), hair (our hair objects' surfaces, their outlines and ink
    left out)) -> {view: dict}. Memoized on the bundle; the calibration's stand-in patches it."""
    def make():
        from . import bodyqa, declared, qa3d
        As = B.assembly
        iw = np.array(qa3d.iris_centres(B))
        az = bodyqa.azimuths(az3)
        surfs = []
        for o in B.objects():
            variant = 'masked' if o.group == 'skin' and o.has('masked') else 'eval'
            if o.has(variant):
                surfs += qa3d.surfaces(B, o, variant)
        hair = np.array([s_['o'].group == 'hair' and not s_['hull'] for s_ in surfs] + [False])
        out = {}
        for v in views:
            fr = declared._Grid(bodyqa.origin(v, az[v], iw, As['centre']), float(As['L']), ppl)
            aux = {}
            pic = qa3d.draw(B, surfs, az[v], fr, ss=1, aux=aux)
            mesh = aux['mesh']
            out[v] = dict(tone=aux['tone'], value=pic[..., :3].max(-1), hair=hair[np.where(mesh >= 0, mesh, len(surfs))])
        return out
    return B.memo(('hairtones_ours', float(ppl), float(az3), tuple(views)), make)


def ours_classes(o, sh):
    """our tones in a view (our_tones' dict), cut to the design grid's shape sh -> dict(shade, mark, inside, lit)."""
    from scipy import ndimage

    def cut(a, fill):
        out = np.full(sh, fill, dtype=np.asarray(a).dtype)
        h, w = min(sh[0], a.shape[0]), min(sh[1], a.shape[1])
        out[:h, :w] = a[:h, :w]
        return out
    hair = cut(o['hair'], False)
    tone = cut(np.nan_to_num(o['tone'], nan=-1.0), -1.0)
    val = cut(o['value'], 0.0)
    inside = hair & (tone >= 0)
    lit_px = inside & (tone < 0.5)
    lit = float(np.median(val[lit_px])) if lit_px.sum() > 20 else 1.0
    return dict(shade=inside & (tone >= 0.5), mark=inside & (val > lit + HL_OVER), inside=inside, lit=lit)


def compare(T, O, ppl, measure):
    """the design's tones T (design_tones) against ours O (ours_classes) in one view -> dict(value, ...) or None."""
    from scipy import ndimage
    zone = T['inside'] & O['inside']
    if zone.sum() < 50:
        return None
    if measure == 'shadow':
        a, b = T['shade'] & zone, O['shade'] & zone
        u = (a | b).sum()
        return dict(value=round(float((a & b).sum()) / max(1, u), 3), design=round(float(a.sum()) / zone.sum(), 3),
                    ours=round(float(b.sum()) / zone.sum(), 3), zone=round(float(zone.sum()) / ppl ** 2, 4))
    if measure == 'highlight':
        a, b = T['mark'], O['mark']
        if a.sum() < 3:
            return None
        tol = HL_TOL * ppl
        da = ndimage.distance_transform_edt(~a)
        db = ndimage.distance_transform_edt(~b) if b.any() else np.full(a.shape, np.inf)
        rec = float((a & (db <= tol)).sum()) / max(1, a.sum())
        pre = float((b & (da <= tol)).sum()) / max(1, b.sum()) if b.any() else 0.0
        f1 = 2 * rec * pre / (rec + pre) if rec + pre > 0 else 0.0
        area = ndimage.binary_dilation(T['inside'] | O['inside'], iterations=2)
        g = lambda m: ndimage.gaussian_filter((m & area).astype(float), max(1.0, HL_SCALE * ppl))
        Da, Db = g(a), g(b)
        den = float((Da + Db).sum())
        dens = float(np.abs(Da - Db).sum()) / den if den > 0 else 1.0
        return dict(value=round(dens, 3), f1=round(f1, 3), recall=round(rec, 3), precision=round(pre, 3),
                    design=round(float(a.sum()) / ppl ** 2, 5), ours=round(float(b.sum()) / ppl ** 2, 5))
    raise KeyError(measure)
