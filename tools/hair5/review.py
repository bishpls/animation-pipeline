"""Hair round 5's review page: per Michael flag, the design | start (1583cd6) | now (1580f95) | ours, per view at one
scale (the previews' head crops: 300 px/L, the eye line 1.2 L down), with the flag's checks and every hair piece's shape
IoU per view beside them; a summary box first.

    python tools/hair5/review.py OUT_DIR OURS_BUILD [--summary SUMMARY.json] [--lab LAB.json NAME]

  OURS_BUILD  a build with the previews' boards (views,body,design: `remote --box render build ... --boards
              views,body,design`); its head crops are made here (charkit.preview.crops)
  SUMMARY     {"recommended": html, "asked": [html, ...], "notes": [html, ...]}
"""
import html, json, os, shutil, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
PV = os.path.expanduser('~/animation-pipeline-3d/charkit/out/previews')
VIEWS = ('front', 'three_quarter', 'profile', 'back')
FLAGS = [
    ('1. The ahoge warped', ['hair_ahoge_shape', 'hair_ahoge_bend', 'hair_piece_ahoge'], VIEWS),
    ('2. The flyaway by the right bun floats', ['hair_attached', 'hair_piece_flyaways'], ('front', 'back')),
    ('3. Layering: a solid mass, janky (three-quarter, side)', ['hair_lock_lines_three_quarter',
                                                               'hair_lock_lines_profile', 'hair_piece_side_locks',
                                                               'hair_piece_upper_back', 'hair_piece_lower_back'],
     ('three_quarter', 'profile')),
    ('5. The back: stripes down the mass, a bob hem', ['hair_back_lines', 'hair_back_hem', 'hair_piece_upper_back',
                                                       'hair_piece_lower_back'], ('back',)),
]
GUARD = ['art_terminator_hair', 'art_peeks_hair', 'hair_noise', 'hair_folds', 'hair_piece_bangs', 'hair_piece_buns',
         'hair_bun_outline']
CSS = """body{font:14px/1.45 system-ui,sans-serif;margin:16px;background:#fafafa;color:#222}
.box{background:#fff;border:2px solid #446;padding:12px 16px;margin-bottom:18px;max-width:1100px}
table{border-collapse:collapse;margin:6px 0 14px}td,th{border:1px solid #ccc;padding:3px 7px;text-align:left}
figure{display:inline-block;margin:0 6px 8px 0;vertical-align:top}figcaption{font-size:12px;color:#555}
img{border:1px solid #ddd;background:#fff}.PASS{color:#1a7f37}.WARN{color:#b26b00}.FAIL{color:#c62828}
h2{margin-top:28px;border-top:1px solid #ccc;padding-top:10px}"""


def qa(path):
    return json.load(open(path))['checks'] if os.path.exists(path) else {}


def fmt(c):
    if not c:
        return '<i>absent</i>'
    v = c.get('value')
    s = c.get('status', '')
    out = '%s <span class="%s">%s</span>' % (html.escape(json.dumps(v) if not isinstance(v, str) else v), s, s)
    if isinstance(c.get('views'), dict):
        out += '<br><small>%s</small>' % html.escape(json.dumps(c['views']))
    return out


def main(args):
    out, ours = os.path.abspath(args[0]), os.path.abspath(args[1])
    opt = lambda k: args[args.index(k) + 1] if k in args else None
    S = json.load(open(opt('--summary'))) if opt('--summary') else {}
    img = os.path.join(out, 'img')
    os.makedirs(img, exist_ok=True)
    from charkit import preview as P
    if not os.path.exists(os.path.join(ours, 'page', 'head_front.png')):
        P.crops(ours, P.design_refs())
    cols = [('design', lambda v: os.path.join(PV, '1580f95', 'page', 'design_head_%s.png' % v)),
            ('start 1583cd6', lambda v: os.path.join(PV, '1583cd6', 'page', 'head_%s.png' % v)),
            ('now 1580f95', lambda v: os.path.join(PV, '1580f95', 'page', 'head_%s.png' % v)),
            ('ours (%s)' % os.path.basename(ours), lambda v: os.path.join(ours, 'page', 'head_%s.png' % v))]
    Q = {'start 1583cd6': qa(os.path.join(ROOT, 'charkit/out/h4n_nocrown/qa/qa.json')),
         'now 1580f95': qa(os.path.join(ROOT, 'charkit/out/calib/builds/hair5_1580f95/qa/qa.json')),
         'base 004efc3': qa(os.path.join(ROOT, 'charkit/out/h5_base/qa/qa.json')),
         'ours': qa(os.path.join(ours, 'qa', 'qa.json'))}
    h = ['<!doctype html><meta charset="utf-8"><title>Hair round 5</title><style>%s</style>' % CSS,
         '<h1>Hair round 5: Michael\'s five flags</h1>', '<div class="box"><b>Recommended:</b> %s<br>' % S.get(
             'recommended', '(to fill)'), '<b>Asked of Michael:</b><ul>%s</ul>' % ''.join(
             '<li>%s</li>' % a for a in S.get('asked', ['nothing: informational'])), '<b>Key numbers:</b>',
         '<table><tr><th>check</th>%s</tr>' % ''.join('<th>%s</th>' % k for k in Q)]
    for k in [c for _, cs, _ in FLAGS for c in cs if c.startswith('hair_') and not c.startswith('hair_piece')] + GUARD:
        h.append('<tr><td>%s</td>%s</tr>' % (k, ''.join('<td>%s</td>' % fmt(q.get(k)) for q in Q.values())))
    h.append('</table>%s</div>' % ''.join('<p>%s</p>' % n for n in S.get('notes', [])))
    for title, checks, views in FLAGS:
        h.append('<h2>%s</h2><table><tr><th>check</th>%s</tr>' % (title, ''.join('<th>%s</th>' % k for k in Q)))
        for k in checks:
            h.append('<tr><td>%s</td>%s</tr>' % (k, ''.join('<td>%s</td>' % fmt(q.get(k)) for q in Q.values())))
        h.append('</table>')
        for v in views:
            h.append('<div>')
            for name, f in cols:
                src = f(v)
                if os.path.exists(src):
                    dst = os.path.join(img, '%s_%s.png' % (name.split()[0], v))
                    shutil.copyfile(src, dst)
                    h.append('<figure><a href="img/%s"><img src="img/%s" style="height:360px"></a><figcaption>%s, '
                             '%s</figcaption></figure>' % ((os.path.basename(dst),) * 2 + (html.escape(name), v)))
            h.append('</div>')
    for p_ in ('qa_hair_flags.png',):
        src = os.path.join(ours, 'qa', p_)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(img, p_))
            h.append('<h2>Ours on the design grids (the flags\' measure)</h2><p>each part a shade, detached parts red; '
                     'the drawn lines inside the mass blue, our ink dark red; the drawn ahoge green</p>'
                     '<img src="img/%s" style="max-width:100%%">' % p_)
    open(os.path.join(out, 'index.html'), 'w').write('\n'.join(h))
    print(os.path.join(out, 'index.html'))


if __name__ == '__main__':
    main(sys.argv[1:])
