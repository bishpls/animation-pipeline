"""Expression QA: the model sheet's expression heads against the kit's expression library, both measured the same way from a
class image (pure numpy; ours is the head z-buffered head-on with the shape keys applied, no render).

Classes: skin, hair, iris, line (lids, lashes, lip line), white (sclera, teeth), mouth (the open mouth's inside and the
tongue: red to pink), brow (ours; the drawing's brows are the line strokes on skin above an eye). The sheet's heads are
drawn at one scale: their hair's width against the front figure's (charkit.sheetqa.detect_figures), the median over the
heads; each head is aligned on its eyes (the eye line and the midline between them; a closed eye's centre is its lid arc's).
The found eyes' spacing against 2 * eye_x L is kept as a check on the scale.

Measured (lengths in L):
  eye     open or closed (iris showing). Open: the opening's width, height and aspect, the iris's width over the
          opening's (a shrunken, shocked iris is small). Closed: the lid line's arc, (ends - middle) / span: + an arch
          (a smile's ^), - a sag (a sleepy or plain blink)
  mouth   the lip line and what it encloses: width, open height and area, fill (area over width x height: a round O is
          near 0.8, a D lower), corner lift ((corners - middle) / width, each column taken midway between its top and
          bottom edge: + a smile, an O level), wave (the edges' wobble round a smooth curve, over the width: a
          flustered mouth)
  brow    where the drawing shows one: its tilt (degrees, + = the inner end low, as in anger) and height over the eye

The library is the template's (charkit.eyes.expressions, charkit.mouth.SHAPES, charkit.brows.expressions); the sheet
never defines or limits it. Each sheet head is matched part by part to the closest library entry and graded; a part the
library has nothing close to fails with `missing`, which means: add it to the template.

    from charkit import exprqa
    M = exprqa.measure(cls, ppl, eye_y, axis)            # a face's class image, its scale, eye row and midline column
    best = exprqa.match(exprqa.summary(M), library)       # library: {part: {name: summary}}
    img = exprqa.render(data, {'eye': 'happy', 'mouth': 'laugh'}, ppl)    # ours (charkit.qa3d.expression_data)
    table, checks, picture = exprqa.sheet_run(data, rgb, figures)         # the whole pass over a sheet's heads
"""
import numpy as np

CLASS = {'none': 0, 'skin': 1, 'hair': 2, 'iris': 3, 'line': 4, 'white': 9, 'mouth': 11, 'brow': 12}
EYE_X = 0.168
WIN = dict(x=0.65, top=0.45, bottom=-0.75)           # the face window, L round the eyes (faceqa's)
EYE_BOX = dict(x=0.15, up=0.13, down=0.11)           # an eye's window round its centre
MOUTH_BOX = dict(x=0.24, top=-0.16, bottom=-0.52)    # the mouth's window (above the chin's line)
BROW_BOX = dict(x=0.17, lo=0.05, hi=0.34)            # a brow's window over the eye's top
LIMITS = {                                           # (pass within, warn within); else fail
    'mouth_width': (0.15, 0.30),                     # |ours / design - 1|
    'mouth_open': (0.03, 0.06),                      # |open height - design's|, L
    'mouth_area': (0.30, 0.60),                      # |ours / design - 1| of the open area (open mouths)
    'mouth_lift': (0.08, 0.16),                      # |corner lift - design's|
    'eye_arc': (0.08, 0.16),                         # |closed arc - design's|
    'eye_aspect': (0.15, 0.30),                      # |ours / design - 1| of an open eye's aspect
    'iris_ratio': (0.15, 0.30),                      # |ours / design - 1|
    'brow_tilt': (8.0, 16.0),                        # |tilt - design's|, degrees
}
OPEN_MIN = 0.02                                      # L: an inside shorter than this is a closed mouth's seam
MISSING = 1.0                                        # a match this far (in LIMITS' warn units) or further: not in the library
THIN = (CLASS['line'], CLASS['brow'])                # ours drawn at least a pixel wide, as the drawing's strokes are


# ------------------------------------------------------------------------------------------------------------ classes
def classes(rgb):
    """a drawn face's class image (see the module)."""
    from .i3d import hsv
    H, W, _ = rgb.shape
    h, s, v = (a.reshape(H, W) for a in hsv(rgb.reshape(-1, 3)))
    out = np.zeros((H, W), int)
    out[(s < 0.5) & (v > 0.55)] = CLASS['skin']
    out[(h >= 10) & (h <= 32) & (s > 0.42) & (v > 0.3)] = CLASS['hair']
    out[((h < 10) | (h > 340)) & (s > 0.3) & (v < 0.9) & (v >= 0.3)] = CLASS['mouth']
    out[(s < 0.15) & (v > 0.82)] = CLASS['white']
    out[(h > 28) & (h < 66) & (s > 0.35) & (v > 0.45)] = CLASS['iris']
    out[(v < 0.38) | ((v < 0.5) & (s < 0.7))] = CLASS['line']   # thin strokes anti-alias light; a dark iris is saturated
    return out


def crop(a, centre, ppl, win=WIN, fill=0):
    """the face window round (axis column, eye row) at ppl: faceqa.zbuffer's grid at pix = 1 / ppl."""
    from .bodyqa import crop as _crop
    return _crop(a, centre, ppl, win, fill)


# ------------------------------------------------------------------------------------------------------------ measures
def _box(m):
    ys, xs = np.nonzero(m)
    return (xs.min(), xs.max(), ys.min(), ys.max()) if len(xs) else None


def _largest(m):
    from .sheetqa import label
    lab, n = label(m)
    if not n:
        return m & False
    k = np.bincount(lab.ravel())[1:].argmax() + 1
    return lab == k


def _fill_holes(m):
    from .sheetqa import label
    lab, n = label(~m)
    if not n:
        return m
    H, W = m.shape
    edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    return m | (~np.isin(lab, edge) & (lab > 0))


def _arc(m, ppl):
    """a stroke's arc: per column its mean row, fitted with a parabola; (ends - middle) / span in image-up terms (+ =
    arch), its span and centre (x, y)."""
    ys, xs = np.nonzero(m)
    if len(xs) < 6 or xs.max() - xs.min() < 4:
        return None
    cols = np.unique(xs)
    my = np.array([ys[xs == c].mean() for c in cols])
    p = np.polyfit(cols - cols.mean(), my, 2)
    x0, x1 = cols.min() - cols.mean(), cols.max() - cols.mean()
    f = np.poly1d(p)
    xm = np.clip(-p[1] / (2 * p[0]), x0, x1) if abs(p[0]) > 1e-9 else 0.0
    span = cols.max() - cols.min() + 1
    arc = ((f(x0) + f(x1)) / 2 - f(xm)) / span                 # image rows grow down: ends lower than the middle = arch
    return dict(arc=round(float(arc), 4), span=round(float(span / ppl), 4),
                centre=(float(cols.mean()), float(np.mean(my))))


def eye(cls, ppl, c):
    """one eye round its expected centre c (column, row) -> dict(open, ...)."""
    H, W = cls.shape
    x0, x1 = int(c[0] - EYE_BOX['x'] * ppl), int(c[0] + EYE_BOX['x'] * ppl) + 1
    y0, y1 = int(c[1] - EYE_BOX['up'] * ppl), int(c[1] + EYE_BOX['down'] * ppl) + 1
    x0, y0 = max(0, x0), max(0, y0)
    sub = cls[y0:y1, x0:x1]
    iris = sub == CLASS['iris']
    white = sub == CLASS['white']
    out = {'px_iris': int(iris.sum()), 'px_white': int(white.sum())}
    if iris.sum() >= 6 and (iris.sum() + white.sum()) >= 0.0015 * ppl * ppl:        # an iris, or a small one in its white
        from .eyeqa import _row_fill
        op = _row_fill(_largest(_near((sub == CLASS['white']) | iris, 1)))       # the opening: sclera and iris, bridged
        ob, ib = _box(op), _box(_largest(iris))
        w, h = (ob[1] - ob[0] - 1) / ppl, (ob[3] - ob[2] - 1) / ppl            # (less the bridge's pixel each side)
        out.update(open=True, width=round(w, 4), height=round(h, 4), aspect=round(h / w, 3),
                   iris_ratio=round((ib[1] - ib[0] + 1) / ppl / w, 3),
                   centre=(x0 + (ib[0] + ib[1]) / 2, y0 + (ib[2] + ib[3]) / 2), top=y0 + ob[2])
        return out
    lid = _largest(sub == CLASS['line'])
    a = _arc(lid, ppl)
    if a is None:
        return dict(out, open=None)
    b = _box(lid)
    out.update(open=False, arc=a['arc'], span=a['span'], centre=(x0 + a['centre'][0], y0 + a['centre'][1]), top=y0 + b[2])
    return out


def _near(m, r):
    from .bodyqa import dilate
    return dilate(m, r)


def mouth(cls, ppl, axis, eye_y):
    """the mouth: the largest lip-line-or-inside component in the mouth window, filled -> dict (see the module)."""
    x0, x1 = int(axis - MOUTH_BOX['x'] * ppl), int(axis + MOUTH_BOX['x'] * ppl) + 1
    y0, y1 = int(eye_y - MOUTH_BOX['top'] * ppl), int(eye_y - MOUTH_BOX['bottom'] * ppl) + 1
    x0, y0 = max(0, x0), max(0, y0)
    sub = cls[y0:y1, x0:x1]
    m = np.isin(sub, (CLASS['line'], CLASS['mouth'], CLASS['white']))
    from .sheetqa import label
    from .bodyqa import _shift, dilate, erode
    grp = m.copy()                                            # a thin stroke broken by its anti-aliasing is one mouth:
    for dx in (-2, -1, 1, 2):                                 # its pieces are grouped along the row
        grp |= _shift(m, 0, dx)
    lab, n = label(grp)
    lab = np.where(m, lab, 0)
    if not n:
        return {'found': False}
    # the component nearest the midline with some size (the nose is a dot above it; hair strands and the jaw's line run
    # off the window's sides or bottom)
    best, score = None, np.inf
    h_, w_ = sub.shape
    for k in range(1, n + 1):
        ys, xs = np.nonzero(lab == k)
        if len(xs) < 5 or xs.min() == 0 or xs.max() == w_ - 1 or ys.max() == h_ - 1:
            continue
        sc = abs(xs.mean() + x0 - axis) / ppl - 0.02 * np.sqrt(len(xs)) - (0.1 if xs.max() - xs.min() > 0.05 * ppl else 0)
        if sc < score:
            best, score = k, sc
    if best is None:
        return {'found': False}
    comp = lab == best
    filled = _fill_holes(comp)
    # the inside: the filled mouth less the line along its boundary (a drawing's outline, our lip line ribbon); a dark
    # inside away from the boundary stays. Under OPEN_MIN tall it is a closed mouth's seam
    inner = filled & ~((sub == CLASS['line']) & ~erode(filled, 2))
    b = _box(comp)
    w = (b[1] - b[0] + 1) / ppl
    ib = _box(inner) if inner.sum() >= 3 else None
    if ib and (ib[3] - ib[2] + 1) / ppl < OPEN_MIN:
        ib = None
    oh = (ib[3] - ib[2] + 1) / ppl if ib else 0.0
    area = inner.sum() / ppl ** 2 if ib else 0.0
    # the corners against the middle (each column's centre between the top and bottom edges: an O's corners sit level
    # with its middle, a smile's above it), and the edges' wobble
    cols = np.arange(b[0], b[1] + 1)
    top = np.array([np.nonzero(comp[:, c])[0].min() if comp[:, c].any() else np.nan for c in cols], float)
    bot = np.array([np.nonzero(comp[:, c])[0].max() if comp[:, c].any() else np.nan for c in cols], float)
    ctr = (top + bot) / 2
    k = max(1, len(cols) // 8)
    x = np.arange(len(cols))
    ok = np.isfinite(ctr)
    ctr = np.interp(x, x[ok], ctr[ok])                           # gaps between a broken stroke's pieces
    mid = np.mean(ctr[len(cols) // 2 - k:len(cols) // 2 + k + 1])
    ends = np.mean(np.r_[ctr[:k], ctr[-k:]])
    lift = (mid - ends) / (len(cols))                            # rows grow down: corners above the middle = +
    wave = 0.0
    inner_cols = slice(max(1, len(cols) // 10), len(cols) - max(1, len(cols) // 10))
    for e in (top, bot):
        e = e[inner_cols]
        x = np.arange(len(e))
        ok = np.isfinite(e)
        if ok.sum() > 5:
            r = e[ok] - np.poly1d(np.polyfit(x[ok], e[ok], 2))(x[ok])
            wave = max(wave, float(np.sqrt(np.mean(r ** 2))) / len(cols))
    return {'found': True, 'width': round(w, 4), 'open': round(oh, 4), 'area': round(float(area), 5),
            'fill': round(float(area / (w * oh)), 3) if oh > 0 else 0.0, 'lift': round(float(lift), 4),
            'wave': round(wave, 4), 'aspect': round(oh / w, 3), 'centre_z': round(float((eye_y - (y0 + (b[2] + b[3]) / 2)) / ppl), 4),
            '_mask': (comp, inner, (x0, y0))}


def brow(cls, ppl, e, axis, ours=False):
    """a brow over an eye e (eye()'s dict): ours by its class; the drawing's the line stroke on skin in the window over
    the eye's top (elongated, bordered mostly by skin; the fringe's strokes border hair). -> dict or None (hidden)."""
    if e.get('centre') is None:
        return None
    cx, top = e['centre'][0], e.get('top', e['centre'][1])
    x0, x1 = int(cx - BROW_BOX['x'] * ppl), int(cx + BROW_BOX['x'] * ppl) + 1
    y0, y1 = int(top - BROW_BOX['hi'] * ppl), int(top - BROW_BOX['lo'] * ppl) + 1
    x0, y0 = max(0, x0), max(0, y0)
    sub = cls[y0:y1, x0:x1]
    from .sheetqa import label
    from .bodyqa import dilate
    lab, n = label(sub == (CLASS['brow'] if ours else CLASS['line']))
    best = None
    for k in range(1, n + 1):
        m = lab == k
        b = _box(m)
        w, h = b[1] - b[0] + 1, b[3] - b[2] + 1
        if w < 0.05 * ppl or w < 1.5 * h:
            continue
        ring = dilate(m, 1) & ~m
        skin = float((sub[ring] == CLASS['skin']).mean()) if ring.any() else 0.0
        if not ours and skin < 0.55:
            continue
        if best is None or m.sum() > best[0].sum():
            best = (m, skin)
    if best is None:
        return None
    ys, xs = np.nonzero(best[0])
    p = np.polyfit(xs.astype(float), ys.astype(float), 1)
    inward = np.sign(axis - (xs.mean() + x0)) or 1.0            # +1: the inner end is to the right
    tilt = float(np.degrees(np.arctan(p[0] * inward)))          # rows grow down: + = the inner end lower
    return {'tilt': round(tilt, 1), 'height': round(float((e['centre'][1] - (ys.mean() + y0)) / ppl), 4),
            'skin_border': round(best[1], 2)}


def measure(cls, ppl, eye_y, axis, eye_x=EYE_X, ours=False, refine=True):
    """a face's expression measures from its class image: eye_y, axis: the eye row and midline column (refined to the
    found eyes' centres when refine is on); ppl: the scale -> dict(eyes [left, right], mouth, brows, ppl, spacing: the found
    eyes' spacing over 2 * eye_x L, a check on the scale)."""
    E = [eye(cls, ppl, (axis + s * eye_x * ppl, eye_y)) for s in (-1, 1)]
    out = {}
    if all(e.get('centre') for e in E):
        out['spacing'] = round(abs(E[1]['centre'][0] - E[0]['centre'][0]) / (2 * eye_x * ppl), 3)
        if refine:
            eye_y = float(np.mean([e['centre'][1] for e in E]))
            axis = float(np.mean([e['centre'][0] for e in E]))
            E = [eye(cls, ppl, (axis + s * eye_x * ppl, eye_y)) for s in (-1, 1)]
    out.update(ppl=round(float(ppl), 2), eye_y=round(eye_y, 2), axis=round(axis, 2))
    out['eyes'] = E
    out['mouth'] = mouth(cls, ppl, axis, eye_y)
    out['brows'] = [brow(cls, ppl, e, axis, ours) for e in E]
    return out


# ------------------------------------------------------------------------------------------------------------ matching
def summary(M, neutral=None):
    """the parts' features as flat numbers (eyes averaged over both sides; left out where not found). neutral: the same
    face's neutral summary: adds each size against it (*_rel: an open eye's aspect and iris ratio, the mouth's width), the
    expression apart from the face's own proportions."""
    E = [e for e in M['eyes'] if e.get('open') is not None]
    s = {}
    if E:
        s['eye_open'] = float(np.mean([bool(e['open']) for e in E]))
        op = [e for e in E if e['open']]
        cl = [e for e in E if not e['open']]
        if op:
            s['eye_aspect'] = float(np.mean([e['aspect'] for e in op]))
            s['iris_ratio'] = float(np.mean([e['iris_ratio'] for e in op]))
        if cl:
            s['eye_arc'] = float(np.mean([e['arc'] for e in cl]))
    mo = M['mouth']
    if mo.get('found'):
        s.update({'mouth_' + k: mo[k] for k in ('width', 'open', 'area', 'fill', 'lift', 'wave', 'aspect')})
    B = [b for b in M['brows'] if b]
    if B:
        s['brow_tilt'] = float(np.mean([b['tilt'] for b in B]))
        s['brow_height'] = float(np.mean([b['height'] for b in B]))
    if neutral:
        for k in ('eye_aspect', 'iris_ratio'):
            if k in s and neutral.get(k):
                s[k + '_rel'] = s[k] / neutral[k]
    return s


def _eye_dist(d, o):
    if 'eye_open' not in d or 'eye_open' not in o:
        return np.inf
    if round(d['eye_open']) != round(o['eye_open']):
        return 10.0
    if d['eye_open'] >= 0.5:
        k = '_rel' if 'eye_aspect_rel' in d and 'eye_aspect_rel' in o else ''
        a = abs(o.get('eye_aspect' + k, 0) / max(1e-6, d['eye_aspect' + k]) - 1) / LIMITS['eye_aspect'][1]
        b = abs(o.get('iris_ratio' + k, 0) / max(1e-6, d['iris_ratio' + k]) - 1) / LIMITS['iris_ratio'][1]
        return float(np.hypot(a, b))
    return abs(o.get('eye_arc', 0) - d['eye_arc']) / LIMITS['eye_arc'][1]


def _mouth_dist(d, o):
    if 'mouth_width' not in d or 'mouth_width' not in o:
        return np.inf
    k = '_rel' if 'mouth_width_rel' in d and 'mouth_width_rel' in o else ''
    t = [abs(o['mouth_width' + k] / d['mouth_width' + k] - 1) / LIMITS['mouth_width'][1],
         abs(o['mouth_open'] - d['mouth_open']) / LIMITS['mouth_open'][1],
         abs(o['mouth_lift'] - d['mouth_lift']) / LIMITS['mouth_lift'][1]]
    if d['mouth_open'] > 0.02:
        t.append(abs(o['mouth_area'] / max(1e-6, d['mouth_area']) - 1) / LIMITS['mouth_area'][1])
    return float(np.sqrt(np.mean(np.square(t))))


def _brow_dist(d, o):
    if 'brow_tilt' not in d or 'brow_tilt' not in o:
        return np.inf
    return abs(o['brow_tilt'] - d['brow_tilt']) / LIMITS['brow_tilt'][1]


DIST = {'eye': _eye_dist, 'mouth': _mouth_dist, 'brow': _brow_dist}


def match(d, library):
    """a sheet head's summary against the library {part: {name: summary}} -> {part: (best name, distance, ranked
    [(name, distance)])} (distance in LIMITS' warn units: under 1 is within warn on every feature)."""
    out = {}
    for part, fn in DIST.items():
        ranked = sorted(((name, fn(d, o)) for name, o in library.get(part, {}).items()), key=lambda t: t[1])
        ranked = [(n, round(float(v), 3)) for n, v in ranked if np.isfinite(v)]
        if ranked:
            out[part] = (ranked[0][0], ranked[0][1], ranked[:4])
    return out


def _grade(key, v):
    p, w = LIMITS[key]
    return 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'


def grade(d, o, part):
    """the graded features of one part, ours (o) against the design (d) -> {feature: check}."""
    C = {}
    if part == 'eye':
        C['state'] = {'value': 'open' if o.get('eye_open', 0) >= 0.5 else 'closed',
                      'design': 'open' if d.get('eye_open', 0) >= 0.5 else 'closed'}
        C['state']['status'] = 'PASS' if C['state']['value'] == C['state']['design'] else 'FAIL'
        if C['state']['status'] == 'PASS':
            if d['eye_open'] >= 0.5:
                for k in ('eye_aspect', 'iris_ratio'):
                    kk = k + '_rel' if k + '_rel' in d and k + '_rel' in o else k
                    r = o[kk] / d[kk]
                    C[k] = {'value': round(r, 3), 'ours': round(o[kk], 3), 'design': round(d[kk], 3), 'status': _grade(k, abs(r - 1)),
                            'against': 'each face\'s neutral' if kk != k else 'absolute'}
            else:
                dv = o['eye_arc'] - d['eye_arc']
                C['eye_arc'] = {'value': round(dv, 4), 'ours': round(o['eye_arc'], 4), 'design': round(d['eye_arc'], 4),
                                'status': _grade('eye_arc', abs(dv)), 'note': '+ arch (a smile), - sag'}
    elif part == 'mouth':
        kk = 'mouth_width_rel' if 'mouth_width_rel' in d and 'mouth_width_rel' in o else 'mouth_width'
        r = o[kk] / d[kk]
        C['width'] = {'value': round(r, 3), 'ours': round(o[kk], 4), 'design': round(d[kk], 4), 'status': _grade('mouth_width', abs(r - 1)),
                      'against': 'each face\'s neutral' if kk != 'mouth_width' else 'absolute',
                      'absolute': {'ours': o['mouth_width'], 'design': d['mouth_width']}}
        dv = o['mouth_open'] - d['mouth_open']
        C['open'] = {'value': round(dv, 4), 'ours': o['mouth_open'], 'design': d['mouth_open'], 'status': _grade('mouth_open', abs(dv))}
        if d['mouth_open'] > 0.02:
            r = o['mouth_area'] / max(1e-6, d['mouth_area'])
            C['area'] = {'value': round(r, 3), 'ours': o['mouth_area'], 'design': d['mouth_area'], 'status': _grade('mouth_area', abs(r - 1))}
        dv = o['mouth_lift'] - d['mouth_lift']
        C['lift'] = {'value': round(dv, 4), 'ours': o['mouth_lift'], 'design': d['mouth_lift'], 'status': _grade('mouth_lift', abs(dv))}
        C['shape'] = {'value': {'fill': o['mouth_fill'], 'wave': o['mouth_wave'], 'aspect': o['mouth_aspect']},
                      'design': {'fill': d['mouth_fill'], 'wave': d['mouth_wave'], 'aspect': d['mouth_aspect']}, 'status': 'INFO'}
    elif part == 'brow':
        dv = o['brow_tilt'] - d['brow_tilt']
        C['tilt'] = {'value': round(dv, 1), 'ours': round(o['brow_tilt'], 1), 'design': round(d['brow_tilt'], 1),
                     'status': _grade('brow_tilt', abs(dv))}
    return C


def name(s):
    """a readable name for a sheet head from what it shows."""
    eyes = 'open' if s.get('eye_open', 1) >= 0.5 else ('arched' if s.get('eye_arc', 0) > 0 else 'shut')
    op = s.get('mouth_open', 0) > 0.03
    if eyes == 'arched' and op:
        return 'laugh'
    if eyes == 'shut' and op:
        return 'yawn'
    if eyes == 'open' and op and s.get('mouth_wave', 0) > 0.012:
        return 'fluster'
    if eyes == 'open' and s.get('brow_tilt', 0) > 8:
        return 'angry'
    if eyes == 'open' and op:
        return 'surprise'
    return {'arched': 'happy', 'shut': 'sleep', 'open': 'neutral'}[eyes]


# ------------------------------------------------------------------------------------------------------------ pictures
PAL = {0: (0.97, 0.97, 0.95), 1: (0.98, 0.85, 0.77), 2: (0.85, 0.45, 0.28), 3: (0.95, 0.75, 0.1), 4: (0.12, 0.08, 0.08),
       9: (1.0, 1.0, 1.0), 11: (0.75, 0.2, 0.3), 12: (0.35, 0.2, 0.6)}


def paint(cls, M=None):
    """a class image, with the measured parts marked: eye windows' centres, the mouth's outline (green) and inside (cyan)."""
    im = np.zeros(cls.shape + (3,))
    for c, col in PAL.items():
        im[cls == c] = col
    if M:
        for e in M['eyes']:
            if e.get('centre'):
                x, y = (int(round(v)) for v in e['centre'])
                im[max(0, y - 1):y + 2, max(0, x - 1):x + 2] = (0.1, 0.8, 0.2)
        mo = M['mouth']
        if mo.get('found'):
            comp, inner, (x0, y0) = mo['_mask']
            h, w = comp.shape
            reg = im[y0:y0 + h, x0:x0 + w]
            reg[comp] = (0.1, 0.7, 0.2); reg[inner] = (0.1, 0.8, 0.9)
    return im


# ------------------------------------------------------------------------------------------------------------ ours
def render(data, combo, ppl, win=WIN):
    """our face head-on with a combination's keys applied ({'eye': name, 'mouth': name, 'brow': name}; None or 'neutral'
    = the basis): the parts' offsets summed onto the posed base meshes and z-buffered (charkit.faceqa) at ppl round the
    eyes -> class image on the face window (eye line at row win.top * ppl, midline at column win.x * ppl)."""
    from .faceqa import zbuffer
    keys = ['%s_%s' % (p, n) for p, n in combo.items() if n and n != 'neutral']
    meshes = []
    for _, V, T, lab, K in data['parts']:
        P = V.copy()
        for k in keys:
            if k in K:
                idx, D = K[k]
                P[idx] += D
        meshes.append((P, T, lab))
    _, cls = zbuffer(meshes, 0.0, (0.0, data['eye_z']), data['L'], 1.0 / ppl, win, thin=THIN)
    return np.where(cls < 0, 0, cls)


def library(data):
    """the template's expression library as the built character carries it: {part: [names]} from the shape keys."""
    lib = {'eye': {'neutral'}, 'mouth': {'neutral'}, 'brow': {'neutral'}}
    for _, _, _, _, K in data['parts']:
        for k in K:
            p, n = k.split('_', 1)
            if p in lib:
                lib[p].add(n)
    return {p: sorted(v) for p, v in lib.items()}


def _at(ppl, win=WIN):
    return win['top'] * ppl, win['x'] * ppl                     # the eye row and the midline column on the window


def sheet_run(data, rgb, D, eye_x=EYE_X):
    """every expression head on the sheet (sheetqa.detect_figures' D['expressions']) measured, matched part by part to
    the library, our match rendered and graded. -> (table, checks, picture)."""
    heads = D['expressions']
    ppl = float(np.median([h['ppl'] for h in heads]))
    ey, ax = _at(ppl)
    names = library(data)
    on = summary(measure(render(data, {}, ppl), ppl, ey, ax, eye_x, ours=True))
    lib = {p: {n: summary(measure(render(data, {p: n}, ppl), ppl, ey, ax, eye_x, ours=True), on) for n in ns}
           for p, ns in names.items()}
    cls_all = classes(rgb)
    # the design's neutral: the front figure's face, at its own scale
    dn = None
    F = D['figures'].get('front')
    if F and len(F['eyes']) == 2:
        fp = D['ppl']
        fy, fx = _at(fp)
        dn = summary(measure(crop(cls_all, (float(np.mean([e[0] for e in F['eyes']])), F['eye_y']), fp), fp, fy, fx, eye_x))
    table = {'ppl': round(ppl, 2), 'library': names, 'heads': [], 'neutral': {'ours': on, 'design': dn}}
    C, rows, seen = {}, [], {}
    for i, h in enumerate(heads):
        c = crop(cls_all, (h['axis_x'], h['eye_y']), ppl)
        M = measure(c, ppl, ey, ax, eye_x)
        d = summary(M, dn)
        nm = name(d)
        seen[nm] = seen.get(nm, 0) + 1
        key = nm if seen[nm] == 1 else '%s%d' % (nm, seen[nm])
        m = match(d, lib)
        combo = {p: m[p][0] for p in m}
        oc = render(data, combo, ppl)
        Mo = measure(oc, ppl, ey, ax, eye_x, ours=True)
        o = summary(Mo, on)
        caution = None
        if M.get('spacing') and abs(M['spacing'] - 1) > 0.1:
            caution = "the head's eyes sit %.2fx the kit's spacing at the sheet's head scale (its hair's width): lengths " \
                      "are in that scale" % M['spacing']
        for part in ('eye', 'mouth', 'brow'):
            ck = 'expr_%s_%s' % (key, part)
            if part not in m or (part == 'brow' and 'brow_tilt' not in d):
                C[ck] = {'status': 'SKIPPED', 'why': 'hidden in the drawing' if part == 'brow' else 'not found'}
                continue
            G = grade(d, o, part)
            st = [g['status'] for g in G.values() if g['status'] != 'INFO']
            worst = max(st, key=['PASS', 'WARN', 'FAIL'].index) if st else 'INFO'
            chk = {'value': m[part][1], 'status': worst, 'match': m[part][0], 'ranked': m[part][2],
                   'features': {k: {kk: g[kk] for kk in ('value', 'ours', 'design', 'status') if kk in g} for k, g in G.items()}}
            if m[part][1] > MISSING:
                chk.update(status='FAIL', missing='the library has nothing within tolerance: add it to the template')
            if caution:
                chk['caution'] = caution
            C[ck] = chk
        table['heads'].append({'name': key, 'box': h['box'], 'combo': combo, 'design': d, 'ours': o,
                               'spacing': M.get('spacing')})
        crgb = crop(rgb, (h['axis_x'], h['eye_y']), ppl, fill=1.0)
        rows.append([crgb, paint(c, M), paint(oc, Mo)])
    sep = lambda a: np.pad(a, ((0, 4), (0, 4), (0, 0)), constant_values=1.0)
    pic = np.concatenate([np.concatenate([sep(t) for t in r], 1) for r in rows], 0)
    return table, C, np.repeat(np.repeat(pic, 2, 0), 2, 1)
