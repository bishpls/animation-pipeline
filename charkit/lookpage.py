"""The look's review page (docs/workstreams/look.md): a build's head at the design's scale and angles beside the design's
own panels (charkit/boards/lookboard.py's views, head_turnaround's heads cut at the same px per L round the same eye
line), before and after; the turntables, the body boards, zoomed outlines and highlights; the look's measures
(charkit.lookqa, OUT/qa_look/look.json) side by side; and any option renders (taste calls). Venv-side.

    python -m charkit.lookpage OUT_PAGE --before OUT_A --after OUT_B [--options DIR ...] [--note TEXT]
        [--board lookboard_bare] [--shadows] [--extra NAME=OUT_C ...]

--board: the builds' lookboard folder to show (lookboard.py --bare: the neck bare, as head_turnaround draws it).
--extra: another build shown beside before and after everywhere (an option: e.g. castneck=charkit/out/look5_castneck).
--shadows: the cast shadows' close-ups (the chin's V on the neck, the hair's shadow on the temple and cheek) and the
QA's chin overlays (qa_look/qa_chin_shadow.png) first.
"""
import html, json, os, shutil, sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWS = ('front', 'three_quarter', 'profile', 'back')
CHECKS = [('face_noise', 'face tone edges / skin px (design shown)'), ('face_islands', 'face tone regions'),
          ('face_shadow_3q', 'shadow IoU with the design, 3/4'), ('face_shadow_face_3q', 'face shadow share, ours - design, 3/4'),
          ('face_shadow_neck_3q', 'neck shadow share, ours - design, 3/4'), ('line_width', 'line width, ours / design'),
          ('line_spread', 'line width spread p90/p10 (design shown)'), ('line_ink', 'line colour vs design ink, dE00'),
          ('face_shadow_chin', 'the chin\'s shadow on the neck: IoU with the design, front and 3/4 (INFO, proposed grade)'),
          ('face_shadow_chin_edge', 'its reach under the chin per column vs the design\'s, L (INFO, proposed grade)'),
          ('face_shadow_chin_soft', 'its tone steps\' soft width on the neck, L'),
          ('hair_noise', 'hair speckle'), ('palette_hair_lit', 'palette: hair lit dE'),
          ('palette_skin_lit', 'palette: skin lit dE'), ('palette_skin_shade', 'palette: skin shade dE')]


def _img(path):
    from PIL import Image
    return Image.open(path).convert('RGB')


def design_panels(spec_ref, eye_x, ppl_view, win, out):
    """head_turnaround's heads cut round their eye line at the look board's framing -> {view: file}."""
    from PIL import Image
    from . import lookqa
    from .bundle import bytes_to_float

    class _D:                                                     # the minimum lookqa.design_heads needs
        def __init__(self):
            self.B = type('B', (), {'assembly': {'eye_knobs': {'x': eye_x}}})()

        def ref(self):
            return spec_ref

        def rgba(self, p):
            return bytes_to_float(np.asarray(Image.open(os.path.join(ROOT, p)).convert('RGBA')))

        def memo(self, fn, *a):
            return fn(*a)
    D = lookqa.design_heads(_D())
    f = lookqa.FACE_PPL / D['native_ppl']
    src = Image.open(os.path.join(ROOT, spec_ref['face_sheet']['image'])).convert('RGB')
    scale = ppl_view / D['native_ppl']
    w, up, down = win
    got = {}
    for v in VIEWS:
        h = D['heads'].get(v)
        if not h:
            continue
        x0, y0, x1, y1 = (b / f for b in h['box'])
        cx = (x0 + x1) / 2
        ey = np.mean([e[1] for e in h['eyes']]) / f if h['eyes'] else y0 + 0.42 * (y1 - y0)
        box = (cx - w / 2 * D['native_ppl'], ey - up * D['native_ppl'], cx + w / 2 * D['native_ppl'], ey + down * D['native_ppl'])
        im = src.crop(tuple(int(round(b)) for b in box))
        im = im.resize((int(round(w * ppl_view)), int(round((up + down) * ppl_view))))
        p = os.path.join(out, 'design_%s.png' % v)
        im.save(p)
        got[v] = os.path.basename(p)
    return got, D


def _crop(src, box, dst, zoom=2):
    im = _img(src).crop(box)
    im.resize((im.width * zoom, im.height * zoom)).save(dst)
    return os.path.basename(dst)


def _look(out):
    p = os.path.join(out, 'qa_look', 'look.json')
    return json.load(open(p)) if os.path.exists(p) else None


def _qa(out):
    p = os.path.join(out, 'qa', 'qa.json')
    return json.load(open(p)) if os.path.exists(p) else None


SHADOW_ZOOMS = [                  # (caption, view, crop box as fractions of the look board: x0, y0, x1, y1)
    ('the chin\'s shadow on the neck, front', 'front', (0.26, 0.5, 0.74, 0.86)),
    ('the chin\'s shadow on the neck, 3/4', 'three_quarter', (0.2, 0.5, 0.72, 0.86)),
    ('the hair\'s shadow on the temple and cheek, 3/4', 'three_quarter', (0.22, 0.26, 0.78, 0.66)),
    ('the hair\'s shadow on the temple and cheek, profile', 'profile', (0.12, 0.26, 0.68, 0.66))]


def build(page, before, after, options=(), note='', title='The look: shading and lines', board='lookboard',
          shadows=False, extra=()):
    os.makedirs(page, exist_ok=True)
    spec = json.load(open(os.path.join(after, [f for f in os.listdir(after) if f.endswith('.spec.json')][0])))
    from . import bundle
    B = bundle.load(os.path.join(after, 'bundle'))
    vj = json.load(open(os.path.join(after, board, 'view.json')))
    from .boards.lookboard import WIN
    dp, D = design_panels(spec['ref'], B.assembly['eye_knobs']['x'], vj['ppl'], WIN, page)
    runs = [('before', before), ('after', after)] + list(extra)
    for tag, d in runs:
        for v in VIEWS:
            s = os.path.join(d, board, v + '.png')
            if os.path.exists(s):
                shutil.copy(s, os.path.join(page, '%s_%s.png' % (tag, v)))
        for k in ('face', 'body'):
            s = os.path.join(d, 'turntable', 'turntable_%s.gif' % k)
            if os.path.exists(s):
                shutil.copy(s, os.path.join(page, '%s_tt_%s.gif' % (tag, k)))
        for az in ('000', '035', '090', '180'):
            s = os.path.join(d, 'boards', 'body_%s.png' % az)
            if os.path.exists(s):
                shutil.copy(s, os.path.join(page, '%s_body_%s.png' % (tag, az)))
    L = {tag: _look(d) for tag, d in runs}
    Q = {tag: _qa(d) for tag, d in runs}
    e = html.escape
    H = ['<!doctype html><meta charset="utf-8"><title>Look review</title><style>',
         'body{font:14px/1.45 -apple-system,system-ui,sans-serif;margin:24px;background:#f4f3f1;color:#222}',
         'h1{font-size:22px}h2{font-size:18px;margin-top:34px}figure{display:inline-block;margin:0 10px 14px 0;vertical-align:top}',
         'figcaption{font-size:12px;color:#555;max-width:640px}img{border:1px solid #ccc;background:#fff;display:block}',
         'table{border-collapse:collapse;font-size:13px}td,th{border:1px solid #ccc;padding:4px 8px;text-align:right}',
         'th:first-child,td:first-child{text-align:left}.row{white-space:nowrap;overflow-x:auto}.note{max-width:1000px}',
         '.opt{background:#fff;border:1px solid #ddd;padding:10px 14px;margin:10px 0;max-width:1400px}</style>',
         '<h1>%s</h1><p class="note">%s</p>' % (e(title), note)]

    def fig(src, cap, w=None):
        return '<figure><a href="%s"><img src="%s"%s></a><figcaption>%s</figcaption></figure>' % (
            src, src, ' width="%d"' % w if w else '', cap)

    def shadow_cap(tag, v):
        t = (L.get(tag) or {}).get('table', {}).get('shadow', {}).get(v)
        if not t:
            return ''
        f_, n_ = t['face'], t['neck']
        return ' · face shadow %s (design %s) · neck %s (design %s) · IoU %s' % (
            f_['ours'], f_['design'], n_['ours'], n_['design'], t['iou'])
    if shadows:
        more = ''.join(' and %s (%s)' % (e(t), e(d)) for t, d in extra).replace('%', '%%')
        H.append(('<h2>0. The cast shadows, close up (2x, the design beside ours at the same scale)</h2><p class="note">'
                  'The design (head_turnaround), ours before (%s) and after (%s)' + more + ', cut from the same framing at '
                  '%.0f px per L and doubled. Then the QA\'s view of the chin: the design, ours, and the two shadows '
                  'overlaid (both dark red, ours only orange, the design\'s only blue), round our chin in the front and '
                  'three-quarter views (charkit.lookqa.face_shadow at 200 px per L).</p>') % (e(before), e(after), vj['ppl']))
        for cap, v, (a, b, c, d) in SHADOW_ZOOMS:
            H.append('<div class="row">')
            for tag, src in [('design', os.path.join(page, dp.get(v, '')))] + \
                    [(t, os.path.join(page, '%s_%s.png' % (t, v))) for t, _ in runs]:
                if os.path.isfile(src):
                    im = _img(src)
                    box = (int(a * im.width), int(b * im.height), int(c * im.width), int(d * im.height))
                    dst = os.path.join(page, 'shadow_%s_%s_%d.png' % (tag, v, int(b * 100)))
                    H.append(fig(_crop(src, box, dst), '%s · %s' % (tag, cap), 420))
            H.append('</div>')
        for tag, d in runs:
            q = os.path.join(d, 'qa_look', 'qa_chin_shadow.png')
            if os.path.exists(q):
                shutil.copy(q, os.path.join(page, '%s_qa_chin.png' % tag))
                ch = (((L.get(tag) or {}).get('checks') or {}).get('face_shadow_chin') or {})
                ce = (((L.get(tag) or {}).get('checks') or {}).get('face_shadow_chin_edge') or {})
                H.append('<div class="row">' + fig('%s_qa_chin.png' % tag, '%s · the QA\'s chin: design, ours, overlay '
                         '(front, then 3/4) · IoU %s %s · reach error %s L %s' % (
                             tag, ch.get('per_view'), ch.get('status', ''), ce.get('per_view'), ce.get('status', '')), 900)
                         + '</div>')
    H.append('<h2>1. The face at the design\'s scale and angles</h2><p class="note">Each row: head_turnaround\'s panel, '
             'cut round its eye line at %.0f px per L; ours before (%s) and after (%s), orthographic at the same scale and '
             'eye line, lit as the boards light them. Captions: the share of the skin both show that is in shadow, '
             'ours and the design\'s, and the shadows\' IoU (charkit.lookqa.face_shadow; the design\'s back shows no skin).</p>'
             % (vj['ppl'], e(before), e(after)))
    for v in VIEWS:
        H.append('<div class="row">')
        if v in dp:
            H.append(fig(dp[v], 'design · %s' % v.replace('_', ' '), 360))
        for tag, _ in runs:
            if os.path.exists(os.path.join(page, '%s_%s.png' % (tag, v))):
                H.append(fig('%s_%s.png' % (tag, v), '%s · %s%s' % (tag, v.replace('_', ' '), shadow_cap(tag, v)), 360))
        H.append('</div>')
    H.append('<h2>2. Turntables</h2><div class="row">')
    for k in ('face', 'body'):
        for tag, _ in runs:
            if os.path.exists(os.path.join(page, '%s_tt_%s.gif' % (tag, k))):
                H.append(fig('%s_tt_%s.gif' % (tag, k), '%s · %s turntable (24 views)' % (tag, k), 300 if k == 'face' else 216))
    H.append('</div><h2>3. Body boards</h2>')
    for tag, _ in runs:
        H.append('<div class="row">' + ''.join(fig('%s_body_%s.png' % (tag, az), '%s · body %s' % (tag, az), 180)
                                                for az in ('000', '035', '090', '180')
                                                if os.path.exists(os.path.join(page, '%s_body_%s.png' % (tag, az)))) + '</div>')
    # zoomed crops: the chin and neck (front), the crown (three-quarter), the hair's edge (back)
    rows = [('chin and neck, front', 'front', (0.2, 0.52, 0.8, 0.85)), ('crown and highlight, 3/4', 'three_quarter', (0.15, 0.05, 0.85, 0.45)),
            ('outlines at the hair\'s edge, back', 'back', (0.1, 0.35, 0.6, 0.85))]
    H.append('<h2>4. Close-ups (2x): the jaw line and neck shadow, the highlight, the outlines</h2>')
    for cap, v, (a, b, c, d) in rows:
        H.append('<div class="row">')
        for tag, src in [('design', os.path.join(page, dp.get(v, '')))] + [(t, os.path.join(page, '%s_%s.png' % (t, v))) for t, _ in runs]:
            if os.path.isfile(src):
                im = _img(src)
                box = (int(a * im.width), int(b * im.height), int(c * im.width), int(d * im.height))
                H.append(fig(_crop(src, box, os.path.join(page, 'zoom_%s_%s.png' % (tag, v))), '%s · %s' % (tag, cap), 420))
        H.append('</div>')
    # the numbers
    H.append('<h2>5. The numbers</h2><table><tr><th>measure</th>%s<th>design</th></tr>' % ''.join(
        '<th>%s</th>' % e(t) for t, _ in runs))

    def val(tag, k):
        c = ((L.get(tag) or {}).get('checks') or {}).get(k) or ((Q.get(tag) or {}).get('checks') or {}).get(k) or {}
        return c
    for k, cap in CHECKS:
        vs = [val(t, k) for t, _ in runs]
        if not any(vs):
            continue
        des = next((v['design'] for v in vs[::-1] if 'design' in v), '')
        H.append('<tr><td>%s <small>(%s)</small></td>%s<td>%s</td></tr>' % (
            e(cap), e(k), ''.join('<td>%s</td>' % v.get('value', '') for v in vs), des if not isinstance(des, dict) else ''))
    H.append('</table>')
    lines = {tag: (L.get(tag) or {}).get('table', {}).get('lines') for tag, _ in runs}
    if lines.get('after'):
        H.append('<p class="note">Line widths in px of the design\'s own page (median, p10, p90): ' + '; '.join(
            '%s %s' % (tag, {r: (s['median'], s['p10'], s['p90']) for r, s in (t or {}).get('ours', {}).items()})
            for tag, t in lines.items() if t) + '; design %s. Ink: %s.</p>' % (
            (lines['after'].get('design') or {}).get('median'), e(json.dumps({t: (l or {}).get('ink') for t, l in lines.items()}))))
    for o in options:
        oj = os.path.join(o, 'options.json')
        if not os.path.exists(oj):
            continue
        O = json.load(open(oj))
        H.append('<h2>%s</h2><div class="opt"><p class="note">%s</p><div class="row">' % (e(O['title']), O['what']))
        for it in O['items']:
            dst = '%s_%s' % (os.path.basename(o.rstrip('/')), it['file'])
            shutil.copy(os.path.join(o, it['file']), os.path.join(page, dst))
            H.append(fig(dst, it['caption'], it.get('w', 360)))
        H.append('</div></div>')
    open(os.path.join(page, 'index.html'), 'w').write('\n'.join(H))
    return os.path.join(page, 'index.html')


if __name__ == '__main__':
    a = sys.argv[1:]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    opts = [a[i + 1] for i, x in enumerate(a) if x == '--options']
    extra = [tuple(a[i + 1].split('=', 1)) for i, x in enumerate(a) if x == '--extra']
    print(build(a[0], opt('--before'), opt('--after'), opts, opt('--note', ''), board=opt('--board', 'lookboard'),
                shadows='--shadows' in a, extra=extra))
