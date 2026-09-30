"""The look's review page (docs/workstreams/look.md): a build's head at the design's scale and angles beside the design's
own panels (charkit/boards/lookboard.py's views, head_turnaround's heads cut at the same px per L round the same eye
line), before and after; the turntables, the body boards, zoomed outlines and highlights; the look's measures
(charkit.lookqa, OUT/qa_look/look.json) side by side; and any option renders (taste calls). Venv-side.

    python -m charkit.lookpage OUT_PAGE --before OUT_A --after OUT_B [--options DIR ...] [--note TEXT]
"""
import html, json, os, shutil, sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWS = ('front', 'three_quarter', 'profile', 'back')
CHECKS = [('face_noise', 'face tone edges / skin px (design shown)'), ('face_islands', 'face tone regions'),
          ('face_shadow_3q', 'shadow IoU with the design, 3/4'), ('face_shadow_face_3q', 'face shadow share, ours - design, 3/4'),
          ('face_shadow_neck_3q', 'neck shadow share, ours - design, 3/4'), ('line_width', 'line width, ours / design'),
          ('line_spread', 'line width spread p90/p10 (design shown)'), ('line_ink', 'line colour vs design ink, dE00'),
          ('hair_noise', 'hair shading noise'), ('palette_hair_lit', 'palette: hair lit dE'),
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


def build(page, before, after, options=(), note='', title='The look: shading and lines'):
    os.makedirs(page, exist_ok=True)
    spec = json.load(open(os.path.join(after, [f for f in os.listdir(after) if f.endswith('.spec.json')][0])))
    from . import bundle
    B = bundle.load(os.path.join(after, 'bundle'))
    vj = json.load(open(os.path.join(after, 'lookboard', 'view.json')))
    from .boards.lookboard import WIN
    dp, D = design_panels(spec['ref'], B.assembly['eye_knobs']['x'], vj['ppl'], WIN, page)
    runs = [('before', before), ('after', after)]
    for tag, d in runs:
        for v in VIEWS:
            s = os.path.join(d, 'lookboard', v + '.png')
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
    H.append('<h2>5. The numbers</h2><table><tr><th>measure</th><th>before</th><th>after</th><th>design</th></tr>')

    def val(tag, k):
        c = ((L.get(tag) or {}).get('checks') or {}).get(k) or ((Q.get(tag) or {}).get('checks') or {}).get(k) or {}
        return c
    for k, cap in CHECKS:
        a_, b_ = val('before', k), val('after', k)
        if not a_ and not b_:
            continue
        des = b_.get('design', a_.get('design', ''))
        H.append('<tr><td>%s <small>(%s)</small></td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
            e(cap), e(k), a_.get('value', ''), b_.get('value', ''), des if not isinstance(des, dict) else ''))
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
    print(build(a[0], opt('--before'), opt('--after'), opts, opt('--note', '')))
