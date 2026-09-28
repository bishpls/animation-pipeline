"""Generated references against the design's model sheet (docs/CHARKIT.md §4, the manifest's authority map). A generated
sheet (charkit/refs/NAME/gen/) is only a candidate authority: it is used for a measure after it agrees with the model sheet
on what both show. For a head sheet (the manifest's layout 'heads': a turnaround, a construction drawing):

  1. its construction guide lines are painted out (they would wall the face into strips);
  2. its heads are found (detect_heads) and it is resampled to the model sheet's scale: its front head's eye spacing
     made the sheet's, so both are measured at the sheet's pixels and in the same head lengths;
  3. each head is measured exactly as the QA measures the design's (sheetqa.measure_figure), and graded against the
     design with the QA's own face checks (sheetqa.compare: the widths and neck to jaw in front, the front edge and the
     reach in profile, the far cheek in three-quarter, the chin), the same limits our 3D face is held to.

A reference passes a view when every graded check there passes; that view's measures can then be made its authority.

    python -m charkit refcheck SPEC [--out DIR] [--refs head_turnaround,head_construction] [--no-open]
        -> DIR/refcheck.json and DIR/index.html (opened in the browser): per reference and view, the design's head, the
           reference's at the same scale and alignment, both faces overlaid, and the checks with their numbers
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


def check(spec, ref, sheet=None, log=print):
    """one head sheet against the model sheet. spec: the resolved spec; ref: the manifest's entry.
    -> dict(ref, path, factor, guides, views {view: {checks, measures, pass}}, pass, _pictures)."""
    from PIL import Image
    from . import bodymeasure
    S = sheet or bodymeasure.Sheet(spec)
    facing = S.spec_sheet.get('facing', -1)
    D = sheetqa.measure_sheet(S.rgb, {k: tuple(v) for k, v in S.spec_sheet['heads'].items()}, S.eye_x, ppl=S.ppl)
    rgb0 = np.asarray(Image.open(_p(ref['path'])).convert('RGB')).astype(float) / 255
    rgb0, guides = without_guides(rgb0)
    spacing = S.ppl_eyes * 2 * S.eye_x                                   # the design's front eyes, px apart
    rgb, f, H = at_scale(rgb0, S.eye_x, spacing, facing)
    log('%s: x%.3f (%.2fx the model sheet), heads %s, %d guide lines out' % (
        ref['id'], f, 1 / f, ', '.join(H['heads']), len(guides)))
    OA, chin = measure_heads(rgb, H['heads'], S.ppl, facing)             # at the design's scale (S.ppl)
    out = {'ref': ref['id'], 'path': ref['path'], 'factor': round(f, 4), 'scale_vs_sheet': round(1 / f, 2),
           'guides': guides, 'chin_cut': None if chin is None else round(chin, 4), 'views': {}, '_pictures': {}}
    for view in VIEWS:
        if view not in OA or view not in D:
            continue
        h = H['heads'][view]
        O = {view: OA[view]}
        C = sheetqa.compare(O, D)
        graded = {k: v for k, v in C.items() if v.get('status') in ('PASS', 'WARN', 'FAIL')}
        out['views'][view] = {'checks': {k: {x: v[x] for x in ('value', 'status', 'design', 'ours', 'note') if x in v}
                                         for k, v in C.items()},
                              'measures': _strip(O[view]), 'design': _strip(D[view]),
                              'pass': bool(graded) and all(v['status'] == 'PASS' for v in graded.values())}
        # the pictures: the design's head and this head, framed alike (sheetqa.head_box), and both faces overlaid
        dbox = S.D['figures'][view]['head'] if view in S.D['figures'] else S.spec_sheet['heads'][view]
        out['_pictures'][view] = dict(design=_crop(S.rgb, dbox), ref=_crop(rgb, h['head']),
                                      overlay=sheetqa.picture(O, D, scale=2))
    out['pass'] = bool(out['views']) and all(v['pass'] for v in out['views'].values())
    return out


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


def page(results, out, spec_name):
    """the review page: per reference and view, the design's head | the reference's | the faces overlaid, and the
    checks (value, design, status)."""
    css = ('body{font:14px/1.4 -apple-system,system-ui,sans-serif;margin:24px;background:#fafafa;color:#222}'
           'h1{font-size:20px}h2{font-size:17px;margin-top:32px}h3{font-size:15px;margin:18px 0 6px}'
           '.row{display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap}.tile{text-align:center;font-size:12px;color:#555}'
           '.tile img{display:block;border:1px solid #ddd;image-rendering:pixelated;background:#fff}'
           'table{border-collapse:collapse;font-size:13px}td,th{border:1px solid #ddd;padding:3px 8px;text-align:right}'
           'th{background:#f0f0f0}td:first-child,th:first-child{text-align:left}'
           '.PASS{color:#1a7f37;font-weight:600}.WARN{color:#9a6700;font-weight:600}.FAIL{color:#cf222e;font-weight:600}'
           '.INFO{color:#777}.verdict{font-size:15px;margin:4px 0 12px}.note{color:#666;font-size:12px;max-width:900px}')
    L = ['<!doctype html><meta charset="utf-8"><title>refcheck %s</title><style>%s</style>' % (html.escape(spec_name), css),
         '<h1>Generated references against the model sheet (%s)</h1>' % html.escape(spec_name),
         '<p class="note">Each generated head sheet is brought to the model sheet\'s scale (its front eyes as far apart as '
         'the sheet\'s), measured the way the QA measures the sheet\'s heads, and graded with the QA\'s own face checks '
         'at the same limits our 3D face is held to. The overlay: grey both, <b style="color:#e33">red</b> the reference '
         'only, <b style="color:#35f">blue</b> the design only. %s</p>' % time.strftime('%Y-%m-%d %H:%M')]
    # the summary: per reference and view, the verdict and what didn't pass
    L.append('<h2>Summary</h2><table><tr><th>reference</th><th>scale</th>%s</tr>' % ''.join(
        '<th>%s</th>' % v.replace('_', '-') for v in VIEWS))
    for r in results:
        cells = []
        for v in VIEWS:
            V = r['views'].get(v)
            if V is None:
                cells.append('<td></td>'); continue
            bad = ['%s %s' % (k, c['status']) for k, c in V['checks'].items() if c.get('status') in ('WARN', 'FAIL')]
            worst = 'FAIL' if any(c.get('status') == 'FAIL' for c in V['checks'].values()) else 'WARN' if bad else 'PASS'
            cells.append('<td class="%s">%s%s</td>' % (worst, worst, (': ' + html.escape(', '.join(bad))) if bad else ''))
        L.append('<tr><td>%s</td><td>%.2fx</td>%s</tr>' % (html.escape(r['ref']), r['scale_vs_sheet'], ''.join(cells)))
    L.append('</table><p class="note">A view that passes every check can be the authority for what it measures. The '
             'model sheet stays the authority wherever a reference only warns or fails.</p>')
    for r in results:
        L.append('<h2>%s <span class="%s">%s</span></h2>' % (html.escape(r['ref']), 'PASS' if r['pass'] else 'FAIL',
                                                            'passes' if r['pass'] else 'does not pass every view'))
        L.append('<p class="note"><a href="%s">%s</a>: resampled x%.3f (%.2fx the model sheet\'s resolution)%s.</p>' % (
            html.escape(os.path.relpath(_p(r['path']), out)), html.escape(r['path']), r['factor'], r['scale_vs_sheet'],
            ', %d guide lines painted out' % len(r['guides']) if r['guides'] else ''))
        for view, V in r['views'].items():
            P = r['_pictures'][view]
            stem = '%s_%s' % (r['ref'], view)
            L.append('<h3>%s: <span class="%s">%s</span> <span class="note">(face bounded by %s)</span></h3>' % (
                view.replace('_', '-'), 'PASS' if V['pass'] else 'FAIL', 'PASS' if V['pass'] else 'not all PASS',
                'its own drawn lines' if V['measures'].get('bounded') == 'lines' else 'a cut at the profile\'s drawn chin'))
            L.append('<div class="row">')
            for key, cap, sc in (('design', 'design (idol_D)', 3), ('ref', r['ref'], 3), ('overlay', 'faces overlaid', 1)):
                L.append('<div class="tile"><img src="%s">%s</div>' % (_png(P[key], os.path.join(out, '%s_%s.png' % (stem, key)), sc), html.escape(cap)))
            L.append('<table><tr><th>check</th><th>value</th><th>design</th><th>status</th></tr>')
            for k, c in V['checks'].items():
                val = c.get('value'); dv = c.get('design')
                L.append('<tr><td>%s</td><td>%s</td><td>%s</td><td class="%s">%s</td></tr>' % (
                    html.escape(k), html.escape(json.dumps(val)), html.escape(json.dumps(dv)) if dv is not None else '',
                    c.get('status', ''), c.get('status', '')))
            L.append('</table></div>')
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
    want = want.split(',') if want else [r['id'] for r in refs if r.get('layout') == 'heads']
    S = bodymeasure.Sheet(spec)
    results = [check(spec, next(r for r in refs if r['id'] == rid), S) for rid in want]
    json.dump({'spec': args[0], 'sheet_ppl': S.ppl, 'results': [{k: v for k, v in r.items() if not k.startswith('_')}
                                                                for r in results]},
              open(os.path.join(out, 'refcheck.json'), 'w'), indent=1, default=str)
    p = page(results, out, name)
    for r in results:
        print('%-20s %s  %s' % (r['ref'], 'PASS' if r['pass'] else 'FAIL', '  '.join(
            '%s %s' % (v, ' '.join('%s=%s:%s' % (k, c.get('value'), c.get('status')) for k, c in V['checks'].items()
                                   if c.get('status') in ('PASS', 'WARN', 'FAIL'))) for v, V in r['views'].items())))
    print('page:', p)
    if '--no-open' not in args:
        subprocess.run(['open', p])


if __name__ == '__main__':
    main(sys.argv[1:])
