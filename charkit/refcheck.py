"""Generated references checked for consistency (docs/CHARKIT.md §4, the manifest's authority map). The references
generated for the 3D pipeline (charkit/refs/NAME/gen/: turnarounds, construction drawings) are the base to build on: at
several times the model sheet's resolution, drawn for 3D, they resolve what the small 2D sheet can't. What decides whether
they can be trusted is whether they agree with each other, as views of one head must:

  - between sheets: every pair of head sheets, view by view, graded with the QA's own face checks (sheetqa.compare: the
    widths and neck to jaw in front, the front edge and the reaches in profile, the far cheek in three-quarter, the chin)
    at the limits our 3D face is held to;
  - within a sheet: its views against each other (the front's chin tip and the profile's chin are one point of one head).

How each departs from the original model sheet is reported too, as information: where the 3D references differ from the
2D design, not a verdict on them.

For a head sheet (the manifest's layout 'heads'): its construction guide lines are painted out (they would wall the face
into strips); its heads are found (detect_heads); it is resampled to a common scale (its front eyes as far apart as the
model sheet's, so every sheet is measured in the same pixels and head lengths as the QA's numbers); each head is measured
as the QA measures a drawn head (sheetqa.measure_labels), bounded by its own drawn lines, or cut at the profile's drawn
chin where the neck is drawn in the face's own skin tone (measure_heads, drawn_chin).

    python -m charkit refcheck SPEC [--out DIR] [--refs head_turnaround,head_construction] [--no-open]
        -> DIR/refcheck.json and DIR/index.html (opened in the browser): the pairs, each view side by side at the same
           scale with the faces overlaid and the checks; each sheet's own views; the departures from the model sheet
"""
import html, json, os, subprocess, sys, time

import numpy as np

from . import sheetqa

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUIDE = dict(k=4, diff=0.12, share=0.35)   # a guide line: a thin horizontal feature across much of the sheet
VIEWS = ('front', 'three_quarter', 'profile')


def _p(x):
    return x if os.path.isabs(x) else os.path.join(ROOT, x)


def without_guides(rgb):
    """a construction sheet's horizontal guide lines painted out from the rows either side of each, so they don't wall the
    face into strips -> (rgb, the rows painted out). A guide line is a thin horizontal feature: a pixel unlike both the
    rows GUIDE['k'] above and below it (over the paper and over the skin alike), across GUIDE['share'] of the row."""
    H, W, _ = rgb.shape
    k = GUIDE['k']
    d = np.zeros((H, W))                                                # unlike both rows k away (a thin line), not
    d[k:-k] = np.minimum(np.abs(rgb[k:-k] - rgb[:-2 * k]).sum(-1),       # merely unlike their mean (a row beside one)
                         np.abs(rgb[k:-k] - rgb[2 * k:]).sum(-1))
    guide = (d > GUIDE['diff']).mean(1) > GUIDE['share']
    for _ in range(2):                                                  # the anti-aliased rows either side
        guide |= np.roll(guide, 1) | np.roll(guide, -1)
    rows = np.nonzero(guide)[0]
    if not len(rows):
        return rgb, []
    out = rgb.copy()
    runs = np.split(rows, np.nonzero(np.diff(rows) > 1)[0] + 1)
    for r in runs:
        a, b = max(0, r[0] - 1), min(H - 1, r[-1] + 1)
        for i, y in enumerate(r):
            t = (i + 1) / (len(r) + 1)
            out[y] = (1 - t) * rgb[a] + t * rgb[b]
    return out, [int(r[len(r) // 2]) for r in runs]


def detect_heads(rgb, eye_x, facing=-1):
    """the heads on a head sheet: every blob off the background at least a fifth the size of the largest; its view from
    its eyes as sheetqa.detect_figures names a model sheet's (two level eyes centred on the silhouette: front; off
    centre: three_quarter; one: profile; none: back). -> dict(ppl (the front head's eye spacing, 2 eye_x L), heads
    {view: dict(box, eyes, eye_y, head (sheetqa.head_box), _mask)})."""
    bg = sheetqa.background(rgb)
    blobs, n = sheetqa.label(sheetqa.foreground(rgb, bg))
    B, area = sheetqa.boxes(blobs, n)
    lab = sheetqa.classes(rgb)
    found = []
    for i in range(n):
        if area[i] < 0.2 * area.max():
            continue
        box = [int(v) for v in B[i]]
        m = blobs == i + 1
        e = sheetqa.find_eyes(lab, box, 2, facing=facing, max_tilt=0.25) or sheetqa.find_eyes(lab, box, 1, facing=facing)
        off = None
        if len(e) == 2:
            ey = float(np.mean([p[1] for p in e]))
            c = sheetqa._row_centre(m, int(ey - 20), int(ey + 21))
            off = (c - float(np.mean([p[0] for p in e]))) / max(1.0, abs(e[1][0] - e[0][0]))
        found.append(dict(box=box, eyes=e, off=off, _mask=m))
    two = [f for f in found if f['off'] is not None]
    if not two:
        raise RuntimeError('no two-eyed head to scale the sheet by')
    front = min(two, key=lambda f: abs(f['off']))
    ppl = abs(front['eyes'][1][0] - front['eyes'][0][0]) / (2 * eye_x)
    ey_front = float(np.mean([p[1] for p in front['eyes']]))
    heads = {}
    for f in sorted(found, key=lambda f: f['box'][0]):
        e = f['eyes']
        if len(e) == 2:
            view = 'front' if f is front and abs(f['off']) < 0.5 else 'three_quarter'
        else:
            view = 'profile' if len(e) == 1 else 'back'
        eye_y = float(np.mean([p[1] for p in e])) if e else ey_front      # a sheet's heads share its eye line
        name = view if view not in heads else '%s_%d' % (view, sum(k.startswith(view) for k in heads) + 1)
        heads[name] = dict(box=f['box'], eyes=[[round(a, 2), round(b, 2)] for a, b in e], eye_y=round(eye_y, 2),
                           head=sheetqa.head_box(f['_mask'], eye_y, ppl, facing, [p[0] for p in e], view != 'front'),
                           _mask=f['_mask'])
    return dict(ppl=ppl, heads=heads)


def _resample(rgb, f):
    from PIL import Image
    im = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    return np.asarray(im.resize((max(1, round(im.width * f)), max(1, round(im.height * f))), Image.LANCZOS)).astype(float) / 255


def at_scale(rgb, eye_x, spacing, facing=-1, guess=0.25):
    """a head sheet resampled so its front head's eyes are `spacing` px apart (the model sheet's)
    -> (rgb at that scale, the factor, detect_heads' result there)."""
    f = guess
    for _ in range(6):
        small = _resample(rgb, f)
        try:
            H = detect_heads(small, eye_x, facing)
        except RuntimeError:
            f *= 0.8
            continue
        cur = H['ppl'] * 2 * eye_x
        if abs(cur - spacing) <= 0.3:
            return small, f, H
        f *= spacing / cur
    raise RuntimeError('could not bring the sheet to the model sheet\'s scale')


def drawn_chin(lead, z, below=-0.2, rate=2.0, jump=0.08, span=0.03):
    """a drawn profile's chin: going down from `below` (L from the eye line), the last face row before the front edge
    turns back steeply to the neck: it recedes faster than `rate` L per L to the next row, and more than `jump` L within
    `span` L below (not a pixel's noise). The face above recedes at about 0.4 L per L, the under-chin at 10 or more.
    faceqa.chin_bottom (the QA's, for our 3D face) takes the chin as the most forward point and stops once the edge falls
    0.06 L behind it; an anime profile's lower face slopes back all the way from the nose, so on a drawing that stops
    halfway down the slope (-0.28 L on head_turnaround, whose drawn chin is at -0.36). -> z, or None."""
    ok = np.isfinite(lead) & (z < below)
    idx = np.nonzero(ok)[0]                                              # rows top -> bottom
    for a in range(len(idx) - 1):
        r, q = idx[a], idx[a + 1]
        if lead[r] - lead[q] > rate * (z[r] - z[q]):
            near = [n for n in idx[a + 1:] if z[r] - z[n] <= span]
            if lead[r] - min(lead[n] for n in near) > jump:
                return float(z[r])
    return float(z[idx[-1]]) if len(idx) else None


def measure_heads(rgb, heads, ppl, facing=-1, below=-0.2, leak=0.06):
    """a head sheet's heads measured as sheetqa.measure_figure measures a drawing: the face is the skin reached from under
    the eyes with the drawn lines as walls, as the model sheet's is. Where a view's face runs on down the neck (a
    generated head's neck is often drawn in the face's own skin tone, where the model sheet shades it), its chin lands
    more than `leak` L below the profile's drawn chin (drawn_chin); that view is then cut at the profile's chin, as the
    QA cuts our own face at its profile's (sheetqa.measure_ours). The sheet's heads share one eye line and scale.
    -> ({view: measures, each with 'bounded': 'lines' or 'profile chin'}, the profile's drawn chin, L, or None)."""
    lab = sheetqa.classes(rgb)

    def region(lb, view, eyes):
        near = min(eyes, key=lambda e: e[0] * -facing) if view != 'front' else eyes[0]
        f = sheetqa.face_region(lb, near, ppl)
        if view == 'front' and len(eyes) > 1:
            f |= sheetqa.face_region(lb, eyes[1], ppl)
        return f

    def measure(lb, view, e):
        return sheetqa.measure_labels(lb, region(lb, view, e), view, ppl, e, facing)
    chin = None
    if 'profile' in heads and heads['profile']['eyes']:
        e = [tuple(p) for p in heads['profile']['eyes']]
        M = measure(lab, 'profile', e)
        chin = drawn_chin(M['lead'], M['z'], below)
    O = {}
    for view in VIEWS:
        if view not in heads or not heads[view]['eyes']:
            continue
        e = [tuple(p) for p in heads[view]['eyes']]
        M = measure(lab, view, e)
        M['bounded'] = 'lines'
        if chin is not None and (M.get('chin') is None or M['chin'] < chin - leak):
            zr = (float(np.mean([p[1] for p in e])) - np.arange(lab.shape[0])) / ppl
            lb = lab.copy()
            lb[(zr < chin)[:, None] & (lab == sheetqa.CLASS['skin'])] = sheetqa.CLASS['other']
            M = measure(lb, view, e)
            M['bounded'] = 'profile chin'
        O[view] = M
    return O, chin


def _strip(M):
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in M.items()
            if not isinstance(v, np.ndarray) and k not in ('lab', 'face')}


CHIN_VIEWS = 0.02    # a sheet's front chin tip and its profile's chin are one point of one head: within this (L)


def figures_at_scale(rgb, eye_x, spacing, facing=-1, guess=0.5):
    """a full-body sheet (the manifest's layout 'figures': a body turnaround) resampled so its front figure's eyes are
    `spacing` px apart, its figures found as a model sheet's are (sheetqa.detect_figures: eyes in each figure's head)
    -> (rgb, factor, dict(ppl, heads {view: dict(box, eyes, eye_y, head)}, figures))."""
    f = guess
    for _ in range(6):
        small = _resample(rgb, f)
        try:
            F = sheetqa.detect_figures(small, eye_x=eye_x, facing=facing)
        except RuntimeError:
            f *= 0.8
            continue
        cur = F['ppl'] * 2 * eye_x
        if abs(cur - spacing) <= 0.3:
            heads = {v: dict(box=g['box'], eyes=g['eyes'], eye_y=g['eye_y'], head=g['head'])
                     for v, g in F['figures'].items()}
            return small, f, dict(ppl=F['ppl'], heads=heads, figures=F['figures'])
        f *= spacing / cur
    raise RuntimeError('could not bring the sheet to the model sheet\'s scale')


def measure_ref(ref, S, log=print):
    """one head sheet (layout 'heads') or full-body sheet (layout 'figures') measured at the common scale
    -> dict(ref, path, layout, factor, scale_vs_sheet, guides, chin (the profile's drawn chin), O {view: measures},
    figures (a body sheet's: per view its eye line and ground line, L), _rgb, _heads)."""
    from PIL import Image
    facing = S.spec_sheet.get('facing', -1)
    rgb0 = np.asarray(Image.open(_p(ref['path'])).convert('RGB')).astype(float) / 255
    spacing = S.ppl_eyes * 2 * S.eye_x
    figs = None
    if ref.get('layout') == 'figures':
        guides = []
        rgb, f, H = figures_at_scale(rgb0, S.eye_x, spacing, facing)
        figs = {v: {'eye_y': round(g['eye_y'] / S.ppl, 4), 'ground': round(g['box'][3] / S.ppl, 4),
                    'top': round(g['box'][1] / S.ppl, 4), 'height': round((g['box'][3] - g['box'][1]) / S.ppl, 4)}
                for v, g in H['figures'].items()}
    else:
        rgb0, guides = without_guides(rgb0)
        rgb, f, H = at_scale(rgb0, S.eye_x, spacing, facing)
    O, chin = measure_heads(rgb, H['heads'], S.ppl, facing)
    log('%s: x%.3f (%.2fx the model sheet), heads %s, %d guide lines out, profile chin %s' % (
        ref['id'], f, 1 / f, ', '.join(H['heads']), len(guides), None if chin is None else round(chin, 3)))
    return dict(ref=ref['id'], path=ref['path'], layout=ref.get('layout'), factor=round(f, 4),
                scale_vs_sheet=round(1 / f, 2), guides=guides, chin=None if chin is None else round(chin, 4), O=O,
                figures=figs, _rgb=rgb, _rgb0=rgb0, _heads=H['heads'])


def _graded(C):
    return {k: {x: v[x] for x in ('value', 'status', 'design', 'ours', 'note') if x in v} for k, v in C.items()}


def _worst(checks):
    st = [c.get('status') for c in checks.values()]
    return 'FAIL' if 'FAIL' in st else 'WARN' if 'WARN' in st else 'PASS' if 'PASS' in st else 'INFO'


def compare_views(A, B):
    """B's faces graded against A's, view by view (sheetqa.compare: ratios and gaps are B's over or less A's)
    -> {view: dict(checks, status)}."""
    out = {}
    for view in VIEWS:
        if view in A and view in B:
            C = _graded(sheetqa.compare({view: B[view]}, {view: A[view]}))
            out[view] = {'checks': C, 'status': _worst(C)}
    return out


LINE_VIEWS = 0.02    # a body sheet's views share one eye line and one ground line: within this (L)


def within(R):
    """one sheet's views against each other -> {check: dict(value, status, note)}: the front's chin tip against the
    profile's chin; on a body sheet, every view's eye line and ground line (the spread across views)."""
    O, out = R['O'], {}
    F = R.get('figures') or {}
    for key, name, note in (('eye_y', 'eye_line_views', 'the spread of the views\' eye lines, L: one standing figure'),
                            ('ground', 'ground_views', 'the spread of the views\' feet, L: one ground line')):
        vals = [g[key] for v, g in F.items() if v in VIEWS + ('back',) and (key != 'eye_y' or v != 'back')]
        if len(vals) > 1:
            d = max(vals) - min(vals)
            out[name] = {'value': round(d, 4), 'status': 'PASS' if d <= LINE_VIEWS else 'WARN' if d <= 2 * LINE_VIEWS
                         else 'FAIL', 'note': note}
    cf, cp = (O.get(v, {}).get('chin') for v in ('front', 'profile'))
    if cf is not None and cp is not None:
        d = cf - cp
        out['chin_views'] = {'value': round(d, 4), 'status': 'PASS' if abs(d) <= CHIN_VIEWS else
                             'WARN' if abs(d) <= 2 * CHIN_VIEWS else 'FAIL',
                             'note': "the front's chin tip less the profile's chin, L: one point of one head"}
    return out


EYE_BOX = (0.18, 0.15)   # an eye's crop round its centre, half-width and half-height in L: the whole lash line (0.15 x 0.11 cut it)
FACE_PPL = 200           # the QA's face scale on a generated head sheet, px per L (the old model sheet's was 115)


def _load(path):
    from PIL import Image
    return np.asarray(Image.open(_p(path)).convert('RGB')).astype(float) / 255


def face_design(rgb, eye_x, facing=-1, ppl=FACE_PPL):
    """a head sheet as the QA's face design (sheetqa.measure_sheet's shape, qa3d.Design.sheet_measures): resampled so its
    front eyes sit 2 eye_x L apart at `ppl` (the kit's convention, as our face is drawn), every view measured as a
    drawn head is (measure_heads). rgb: the sheet's pixels, floats (H, W, 3)
    -> {view: measures, 'ppl', 'ppl_eyes', 'az_three_quarter', 'chin_cut'}."""
    rgb0, _ = without_guides(np.asarray(rgb, float))
    rgb, f, H = at_scale(rgb0, eye_x, 2 * eye_x * ppl, facing)
    O, chin = measure_heads(rgb, H['heads'], ppl, facing)
    D = dict(O, ppl=float(ppl), ppl_eyes=float(ppl), chin_cut=chin, factor=f)
    fe, te = (H['heads'].get(v, {}).get('eyes') or [] for v in ('front', 'three_quarter'))
    if len(fe) == 2 and len(te) == 2:
        D['az_three_quarter'] = round(float(np.degrees(np.arccos(np.clip(abs(te[1][0] - te[0][0]) /
                                                                          abs(fe[1][0] - fe[0][0]), 0, 1)))), 1)
    return D


def eye_design(rgb, eye_x, facing=-1, ppl=FACE_PPL, box=EYE_BOX):
    """a head sheet's front eyes cut at the sheet's own resolution, as the QA's eye design (qa3d.Design.eye_layers):
    rgb: the sheet's pixels -> ({our side: rgba}, the sheet's own px per L). The picture's left eye is our right ('R'),
    as the rig's eye_L is."""
    rgb0, _ = without_guides(np.asarray(rgb, float))
    rgb, f, H = at_scale(rgb0, eye_x, 2 * eye_x * ppl, facing)
    fe = sorted(H['heads']['front']['eyes'])
    own = ppl / f
    hw, hh = box[0] * own, box[1] * own
    out = {}
    for side, (x, y) in zip(('R', 'L'), fe):
        cx, cy = x / f, y / f
        crop = rgb0[int(cy - hh):int(cy + hh), int(cx - hw):int(cx + hw)]
        out[side] = np.concatenate([crop, np.ones(crop.shape[:2] + (1,))], -1)
    return out, own


def eye(R, S):
    """a sheet's front-view eye (the viewer's left one) measured at the sheet's own resolution (charkit.eyeqa.measure: the
    opening's aspect and width, the iris in it, the pupil's run, aspect and share of the iris, the lid line)
    -> (measures, the crop) or (None, None)."""
    from . import eyeqa
    h = R['_heads'].get('front')
    if not h or len(h['eyes']) < 2:
        return None, None
    f = R['factor']
    ex, ey = min(h['eyes'])                                             # the viewer's left eye, at the common scale
    cx, cy, ppl = ex / f, ey / f, S.ppl / f                             # at the sheet's own resolution
    hw, hh = EYE_BOX[0] * ppl, EYE_BOX[1] * ppl
    rgb = R['_rgb0'][int(cy - hh):int(cy + hh), int(cx - hw):int(cx + hw)]
    rgba = np.concatenate([rgb, np.ones(rgb.shape[:2] + (1,))], -1)
    M = eyeqa.measure(rgba, ppl)
    M.pop('_masks', None)
    return M, rgb


def run(spec, refs, S, log=print):
    """-> dict(sheets [measure_ref], pairs [dict(a, b, views)], within {ref: checks}, design {ref: views}): the pairs and
    each sheet's own views are the verdict; design (each sheet against the model sheet) is information."""
    D = sheetqa.measure_sheet(S.rgb, {k: tuple(v) for k, v in S.spec_sheet['heads'].items()}, S.eye_x, ppl=S.ppl)
    sheets = [measure_ref(r, S, log) for r in refs]
    pairs = [dict(a=A['ref'], b=B['ref'], views=compare_views(A['O'], B['O']))
             for i, A in enumerate(sheets) for B in sheets[i + 1:]]
    from . import eyeqa
    E = {R['ref']: eye(R, S) for R in sheets}
    for pr in pairs:
        a, b = E[pr['a']][0], E[pr['b']][0]
        if a and b:
            C = eyeqa.compare(b, a)
            C['pupil_share'] = {'value': b.get('pupil_share'), 'design': a.get('pupil_share'), 'status': 'INFO',
                                'note': "the pupil's share of the iris (area)"}
            pr['eye'] = {'checks': C, 'status': _worst(C)}
    res = dict(sheets=sheets, pairs=pairs, eyes={k: v[0] for k, v in E.items()}, _eye_crops={k: v[1] for k, v in E.items()},
               within={R['ref']: within(R) for R in sheets},
               design={R['ref']: compare_views({v: D[v] for v in VIEWS if v in D}, R['O']) for R in sheets}, _D=D)
    st = [v['status'] for p in pairs for v in list(p['views'].values()) + ([p['eye']] if 'eye' in p else [])] + \
         [c['status'] for w in res['within'].values() for c in w.values()]
    res['status'] = 'FAIL' if 'FAIL' in st else 'WARN' if 'WARN' in st else 'PASS'
    return res


def _crop(rgb, box):
    x0, y0, x1, y1 = box
    H, W, _ = rgb.shape
    out = np.ones((y1 - y0, x1 - x0, 3))
    a, b = max(0, y0), min(H, y1); c, d = max(0, x0), min(W, x1)
    out[a - y0:b - y0, c - x0:d - x0] = rgb[a:b, c:d]
    return out


def _png(arr, path, scale=1):
    from PIL import Image
    im = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))
    if scale != 1:
        im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    im.save(path)
    return os.path.basename(path)


def page(res, S, out, spec_name):
    """the review page: the verdict (the pairs and each sheet's own views), then the departures from the model sheet."""
    css = ('body{font:14px/1.4 -apple-system,system-ui,sans-serif;margin:24px;background:#fafafa;color:#222}'
           'h1{font-size:20px}h2{font-size:17px;margin-top:32px}h3{font-size:15px;margin:18px 0 6px}'
           '.row{display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap}.tile{text-align:center;font-size:12px;color:#555}'
           '.tile img{display:block;border:1px solid #ddd;image-rendering:pixelated;background:#fff}'
           'table{border-collapse:collapse;font-size:13px}td,th{border:1px solid #ddd;padding:3px 8px;text-align:right}'
           'th{background:#f0f0f0}td:first-child,th:first-child{text-align:left}'
           '.PASS{color:#1a7f37;font-weight:600}.WARN{color:#9a6700;font-weight:600}.FAIL{color:#cf222e;font-weight:600}'
           '.INFO{color:#777}.note{color:#666;font-size:12px;max-width:960px}')
    by = {R['ref']: R for R in res['sheets']}
    L = ['<!doctype html><meta charset="utf-8"><title>refcheck %s</title><style>%s</style>' % (html.escape(spec_name), css),
         '<h1>Generated references: consistency (%s) <span class="%s">%s</span></h1>' % (
             html.escape(spec_name), res['status'], res['status']),
         '<p class="note">The references generated for the 3D pipeline, measured against each other: each pair view by '
         'view with the QA\'s own face checks, at the limits our 3D face is held to, and each sheet\'s views against each '
         'other. Every sheet is brought to one scale (its front eyes as far apart as the model sheet\'s) and measured the '
         'way the QA measures a drawn head. Overlays: grey both, <b style="color:#e33">red</b> the second only, '
         '<b style="color:#35f">blue</b> the first only. How each departs from the original model sheet (idol_D) is at '
         'the end, as information. %s</p>' % time.strftime('%Y-%m-%d %H:%M'),
         '<h2>Between sheets</h2><table><tr><th>pair</th>%s<th>eye</th></tr>' % ''.join('<th>%s</th>' % v.replace('_', '-') for v in VIEWS)]

    def cell(V):
        if V is None:
            return '<td></td>'
        bad = ['%s %s' % (k, c['status']) for k, c in V['checks'].items() if c.get('status') in ('WARN', 'FAIL')]
        return '<td class="%s">%s%s</td>' % (V['status'], V['status'], (': ' + html.escape(', '.join(bad))) if bad else '')
    for pr in res['pairs']:
        L.append('<tr><td>%s vs %s</td>%s%s</tr>' % (html.escape(pr['a']), html.escape(pr['b']),
                                                    ''.join(cell(pr['views'].get(v)) for v in VIEWS), cell(pr.get('eye'))))
    L.append('</table><h2>Within each sheet</h2><table><tr><th>sheet</th><th>scale</th><th>views</th><th>check</th>'
             '<th>value</th><th>status</th></tr>')
    for R in res['sheets']:
        W = res['within'][R['ref']] or {'(none)': {'value': '', 'status': 'INFO', 'note': 'needs a front and a profile'}}
        for k, c in W.items():
            L.append('<tr><td>%s</td><td>%.2fx</td><td>%s</td><td>%s</td><td>%s</td><td class="%s">%s</td></tr>' % (
                html.escape(R['ref']), R['scale_vs_sheet'], ', '.join(R['O']), html.escape(k), c['value'], c['status'],
                c['status']))
    L.append('</table>')

    def tiles(stem, a_img, a_cap, b_img, b_cap, overlay, V):
        L.append('<div class="row">')
        for key, img, cap, sc in (('a', a_img, a_cap, 3), ('b', b_img, b_cap, 3), ('overlay', overlay, 'faces overlaid', 1)):
            L.append('<div class="tile"><img src="%s">%s</div>' % (_png(img, os.path.join(out, '%s_%s.png' % (stem, key)), sc),
                                                                  html.escape(cap)))
        L.append('<table><tr><th>check</th><th>value</th><th>first</th><th>status</th></tr>')
        for k, c in V['checks'].items():
            L.append('<tr><td>%s</td><td>%s</td><td>%s</td><td class="%s">%s</td></tr>' % (
                html.escape(k), html.escape(json.dumps(c.get('value'))),
                html.escape(json.dumps(c.get('design'))) if c.get('design') is not None else '', c.get('status', ''),
                c.get('status', '')))
        L.append('</table></div>')
    for pr in res['pairs']:
        A, B = by[pr['a']], by[pr['b']]
        L.append('<h2>%s vs %s</h2>' % (html.escape(pr['a']), html.escape(pr['b'])))
        for view, V in pr['views'].items():
            L.append('<h3>%s: <span class="%s">%s</span></h3>' % (view.replace('_', '-'), V['status'], V['status']))
            tiles('%s_vs_%s_%s' % (pr['a'], pr['b'], view), _crop(A['_rgb'], A['_heads'][view]['head']), pr['a'],
                  _crop(B['_rgb'], B['_heads'][view]['head']), pr['b'],
                  sheetqa.picture({view: B['O'][view]}, {view: A['O'][view]}, scale=2), V)
        if 'eye' in pr:
            ca, cb = res['_eye_crops'][pr['a']], res['_eye_crops'][pr['b']]
            L.append('<h3>front eye (each at its sheet\'s own resolution): <span class="%s">%s</span></h3>' % (
                pr['eye']['status'], pr['eye']['status']))
            from PIL import Image
            fit = lambda c: np.asarray(Image.fromarray((np.clip(c, 0, 1) * 255).astype(np.uint8)).resize(
                (240, int(240 * c.shape[0] / c.shape[1])), Image.LANCZOS)).astype(float) / 255
            blank = np.ones((10, 10, 3))
            tiles('%s_vs_%s_eye' % (pr['a'], pr['b']), fit(ca), pr['a'], fit(cb), pr['b'], blank, pr['eye'])
    L.append('<h2>Departures from the model sheet (information)</h2><p class="note">Each sheet against idol_D, the '
             'original 2D design, with the same checks: where the 3D references differ from it, not a verdict.</p>')
    for R in res['sheets']:
        for view, V in res['design'][R['ref']].items():
            dbox = S.D['figures'][view]['head'] if view in S.D['figures'] else S.spec_sheet['heads'][view]
            L.append('<h3>%s, %s: <span class="INFO">%s against idol_D</span> <span class="note">(face bounded by %s)</span></h3>' % (
                html.escape(R['ref']), view.replace('_', '-'), V['status'],
                'its own drawn lines' if R['O'][view].get('bounded') == 'lines' else 'a cut at the profile\'s drawn chin'))
            tiles('%s_vs_design_%s' % (R['ref'], view), _crop(S.rgb, dbox), 'idol_D', _crop(R['_rgb'], R['_heads'][view]['head']),
                  R['ref'], sheetqa.picture({view: R['O'][view]}, {view: res['_D'][view]}, scale=2), V)
    L.append('<p class="note">Sources: %s.</p>' % ', '.join('<a href="%s">%s</a>' % (
        html.escape(os.path.relpath(_p(R['path']), out)), html.escape(R['path'])) for R in res['sheets']))
    p = os.path.join(out, 'index.html')
    open(p, 'w').write('\n'.join(L))
    return p


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return
    from . import bodyeval, bodymeasure, manifest
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    spec = bodyeval.resolve(args[0])
    name = spec.get('name', 'char')
    out = _p(opt('--out', 'charkit/out/refcheck/%s' % name))
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):                                           # a fresh page: no pictures from an earlier run
        if f.endswith('.png'):
            os.remove(os.path.join(out, f))
    M = manifest.load(_p(spec['ref']['manifest']))
    refs = M['references'] if isinstance(M['references'], list) else [dict(id=k, **v) for k, v in M['references'].items()]
    want = opt('--refs')
    want = want.split(',') if want else [r['id'] for r in refs if r.get('layout') in ('heads', 'figures')]
    # the source design (idol_D), for the common scale and the departures: the spec without the generated sheets that
    # otherwise fill the design's role
    import copy
    src = copy.deepcopy(spec)
    for k in [k for k in src['ref'] if k.endswith('_sheet')]:
        src['ref'].pop(k)
    S = bodymeasure.Sheet(src)
    res = run(spec, [next(r for r in refs if r['id'] == rid) for rid in want], S)
    plain = lambda x: {k: v for k, v in x.items() if not k.startswith('_')}
    json.dump({'spec': args[0], 'sheet_ppl': S.ppl, 'status': res['status'],
               'sheets': [dict(plain(R), O={v: _strip(m) for v, m in R['O'].items()}) for R in res['sheets']],
               'pairs': res['pairs'], 'within': res['within'], 'design': res['design'], 'eyes': res['eyes']},
              open(os.path.join(out, 'refcheck.json'), 'w'), indent=1, default=str)
    p = page(res, S, out, name)
    for pr in res['pairs']:
        print('%s vs %s: %s' % (pr['a'], pr['b'], '  '.join('%s %s (%s)' % (v, V['status'], ', '.join(
            '%s=%s' % (k, c.get('value')) for k, c in V['checks'].items() if c.get('status') in ('PASS', 'WARN', 'FAIL')))
            for v, V in pr['views'].items())))
    for r, W in res['within'].items():
        print('%s within: %s' % (r, ', '.join('%s=%s %s' % (k, c['value'], c['status']) for k, c in W.items()) or '-'))
    print('consistency:', res['status'], '| page:', p)
    if '--no-open' not in args:
        subprocess.run(['open', p])


if __name__ == '__main__':
    main(sys.argv[1:])
