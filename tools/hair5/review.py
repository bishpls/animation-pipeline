"""Hair round 5's review page: a summary box first (recommended, asked of Michael, key numbers); then per Michael flag,
the design | start (1583cd6) | before (1580f95) | after (ours) per view at one scale (the previews' head crops: 300 px/L,
the eye line 1.2 L down), with the flag's checks and every hair piece's shape IoU per view beside them (the anti-gaming
guard); the back seams' two options side by side; the lock truth's open calls with pictures of their regions; the last
reference attempt against its pass rule.

    python tools/hair5/review.py OUT_DIR OURS_BUILD [--b BUILD_B] [--summary SUMMARY.json] [--truth DIR]
                                 [--ref REF.json]

  OURS_BUILD  a build with the previews' boards (views,body,design: `remote --box render build ... --boards
              views,body,design`); its head crops are made here (charkit.preview.crops)
  --b         option B's build (the same boards): shown beside ours where B differs (the back, the profile)
  SUMMARY     {"recommended": html, "asked": [html, ...], "key": [check, ...], "notes": [html, ...],
               "sections": [{"title", "html", "rows": [[[path, caption], ...], ...], "height"}, ...],
               "calls": [{"q": html, "default": html, "pics": [[path, caption], ...]}, ...]}
  --truth     the hair-5 truth's review pictures (tools/hair5truth/review.py: VIEW.png per view)
  --ref       {"sheets": [path, ...], "rule": html, "rows": [[take, view, ...cells], ...], "head": [...], "outcome": html}
"""
import html, json, os, shutil, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
PV = os.path.expanduser('~/animation-pipeline-3d/charkit/out/previews')
VIEWS = ('front', 'three_quarter', 'profile', 'back')
FLAGS = [
    ('1. The ahoge warped', ['hair_ahoge_shape', 'hair_ahoge_bend', 'hair_piece_ahoge'], VIEWS, False),
    ('2. The flyaway by the right bun floats', ['hair_attached', 'hair_piece_flyaways'], ('front', 'back'), False),
    ('3. Layering: a solid mass, janky (three-quarter, side)', ['hair_lock_lines_three_quarter',
                                                               'hair_lock_lines_profile', 'hair_piece_side_locks',
                                                               'hair_piece_upper_back', 'hair_piece_lower_back'],
     ('three_quarter', 'profile'), True),
    ('5. The back: stripes down the mass, a bob hem', ['hair_back_lines', 'hair_back_hem', 'hair_piece_upper_back',
                                                       'hair_piece_lower_back'], ('back',), True),
]
PIECES = ['hair_piece_ahoge', 'hair_piece_bangs', 'hair_piece_buns', 'hair_piece_flyaways', 'hair_piece_lower_back',
          'hair_piece_side_locks', 'hair_piece_upper_back']
GUARD = ['art_terminator_hair', 'art_peeks_hair', 'hair_noise', 'hair_folds', 'hair_bun_outline',
         'body_front_iou_hair', 'body_three_quarter_iou_hair', 'body_profile_iou_hair', 'body_back_iou_hair']
CSS = """body{font:14px/1.45 system-ui,sans-serif;margin:16px;background:#fafafa;color:#222;max-width:1500px}
.box{background:#fff;border:2px solid #446;padding:12px 16px;margin-bottom:18px;max-width:1150px}
table{border-collapse:collapse;margin:6px 0 14px}td,th{border:1px solid #ccc;padding:3px 7px;text-align:left;
vertical-align:top}figure{display:inline-block;margin:0 6px 8px 0;vertical-align:top}
figcaption{font-size:12px;color:#555;max-width:420px}img{border:1px solid #ddd;background:#fff;max-width:100%}
.PASS{color:#1a7f37}.WARN{color:#b26b00}.FAIL{color:#c62828}.INFO{color:#666}.drop{background:#fde2e2}
h2{margin-top:28px;border-top:1px solid #ccc;padding-top:10px}small{color:#555}.q{font-weight:600}
@media (max-width:700px){body{margin:8px}td,th{padding:2px 4px;font-size:12px}}"""


def qa(path):
    return json.load(open(path))['checks'] if os.path.exists(path) else {}


def fmt(c, views=True):
    if not c:
        return '<i>absent</i>'
    v = c.get('value')
    s = c.get('status', '')
    out = '%s <span class="%s">%s</span>' % (html.escape(json.dumps(v) if not isinstance(v, str) else v), s, s)
    if views and isinstance(c.get('views'), dict):
        out += '<br><small>%s</small>' % ', '.join('%s %s' % (k, v_) for k, v_ in c['views'].items())
    return out


def table(Q, checks, views=True):
    h = ['<table><tr><th>check</th>%s</tr>' % ''.join('<th>%s</th>' % html.escape(k) for k in Q)]
    for k in checks:
        h.append('<tr><td>%s</td>%s</tr>' % (k, ''.join('<td>%s</td>' % fmt(q.get(k), views) for q in Q.values())))
    return ''.join(h) + '</table>'


def guard(Q, base, cols):
    """every hair piece's shape IoU per view: base against each column; a drop over 15% marked."""
    h = ['<table><tr><th>piece</th><th>view</th><th>%s</th>%s</tr>' % (base, ''.join(
        '<th>%s</th><th>change</th>' % html.escape(c) for c in cols))]
    for k in PIECES:
        b = (Q[base].get(k) or {}).get('views') or {}
        for v in b:
            row = '<tr><td>%s</td><td>%s</td><td>%.3f</td>' % (k[11:], v, b[v])
            for c in cols:
                x = ((Q[c].get(k) or {}).get('views') or {}).get(v)
                if x is None:
                    row += '<td>-</td><td>-</td>'
                    continue
                d = (x - b[v]) / max(1e-9, b[v]) if b[v] > 0 else 0.0
                row += '<td>%.3f</td><td class="%s">%+.1f%%</td>' % (x, 'drop' if d < -0.15 else '', 100 * d)
            h.append(row + '</tr>')
    return ''.join(h) + '</table>'


def fig(img, src, name, caption, height=340):
    if not os.path.exists(src):
        return ''
    dst = os.path.join(img, name)
    shutil.copyfile(src, dst)
    return ('<figure><a href="img/%s"><img src="img/%s" style="height:%dpx;max-width:none"></a><figcaption>%s'
            '</figcaption></figure>' % (name, name, height, caption))


def main(args):
    out, ours = os.path.abspath(args[0]), os.path.abspath(args[1])
    opt = lambda k: args[args.index(k) + 1] if k in args else None
    S = json.load(open(opt('--summary'))) if opt('--summary') else {}
    B = os.path.abspath(opt('--b')) if opt('--b') else None
    img = os.path.join(out, 'img')
    os.makedirs(img, exist_ok=True)
    from charkit import preview as P
    for d in (ours, B):
        if d and not os.path.exists(os.path.join(d, 'page', 'head_front.png')):
            P.crops(d, P.design_refs())
    cols = [('design', lambda v: os.path.join(PV, '1580f95', 'page', 'design_head_%s.png' % v)),
            ('start 1583cd6', lambda v: os.path.join(PV, '1583cd6', 'page', 'head_%s.png' % v)),
            ('before 1580f95', lambda v: os.path.join(PV, '1580f95', 'page', 'head_%s.png' % v)),
            ('after: A (%s)' % os.path.basename(ours), lambda v: os.path.join(ours, 'page', 'head_%s.png' % v))]
    colB = ('B (%s)' % os.path.basename(B), lambda v: os.path.join(B, 'page', 'head_%s.png' % v)) if B else None
    Q = {'start 1583cd6': qa(os.path.join(ROOT, 'charkit/out/h4n_nocrown/qa/qa.json')),
         'before 1580f95': qa(os.path.join(ROOT, 'charkit/out/calib/builds/hair5_1580f95/qa/qa.json')),
         'base 004efc3': qa(os.path.join(ROOT, 'charkit/out/h5_base/qa/qa.json')),
         'after A': qa(os.path.join(ours, 'qa', 'qa.json'))}
    if B:
        Q['B'] = qa(os.path.join(B, 'qa', 'qa.json'))
    h = ['<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
         '<title>Hair round 5</title><style>%s</style>' % CSS,
         '<h1>Hair round 5: Michael\'s five flags, the defaults built</h1>',
         '<div class="box"><b>Recommended:</b> %s' % S.get('recommended', '(to fill)'),
         '<p><b>Asked of Michael:</b></p><ol>%s</ol>' % ''.join(
             '<li>%s</li>' % a for a in S.get('asked', ['nothing: informational'])),
         '<p><b>Key numbers:</b></p>',
         table({k: Q[k] for k in Q if k != 'start 1583cd6'}, S.get('key') or [], views=False)]
    h.append('%s</div>' % ''.join('<p>%s</p>' % n for n in S.get('notes', [])))
    h.append('<h2>The guard: every hair piece\'s shape IoU per view (base 004efc3 against A and B)</h2><p>A drop over '
             '15%% in any view while a flag check improves blocks the merge (marked red).</p>' +
             guard(Q, 'base 004efc3', [c for c in ('after A', 'B') if c in Q]))
    h.append('<p>The other hair checks:</p>' + table(Q, GUARD))
    for k, sec in enumerate(S.get('sections', [])):       # {title, html, rows: [[[path, caption], ...], ...]}
        h.append('<h2>%s</h2>%s' % (sec['title'], sec.get('html', '')))
        for j, row in enumerate(sec.get('rows', [])):
            h.append('<div>' + ''.join(fig(img, src, 'sec%d_%d_%d.png' % (k, j, i), cap, sec.get('height', 300))
                                       for i, (src, cap) in enumerate(row)) + '</div>')
    for title, checks, views, withB in FLAGS:
        h.append('<h2>%s</h2>%s' % (title, table(Q, checks)))
        for v in views:
            h.append('<div>')
            for name, f in cols + ([colB] if (withB and colB) else []):
                h.append(fig(img, f(v), '%s_%s.png' % (name.split()[0].strip(':'), v),
                             '%s, %s' % (html.escape(name), v)))
            h.append('</div>')
    if B:
        h.append('<h2>The back seams: A (one smooth mass) against B (the side seams keep their line)</h2>'
                 '<p>A: no line where the back\'s locks meet but the lower back\'s last quarter (ink_fade upper 0, '
                 'lower 0.25, ink_phi 120). B: the upper back\'s seams keep their line in their first 15%% and the '
                 'lower back\'s in its last 35%%, and the seams nearer the front than 135 deg keep theirs (ink_fade '
                 '0.15 / 0.35, ink_phi 135).</p>' + table({k: Q[k] for k in ('base 004efc3', 'after A', 'B')},
                                                         ['hair_back_lines', 'hair_lock_lines_profile',
                                                          'hair_lock_lines_three_quarter', 'hair_back_hem']))
        for v in ('back', 'profile', 'three_quarter'):
            h.append('<div>' + ''.join(fig(img, f(v), 'seam_%s_%s.png' % (n.split()[0].strip(':'), v),
                                           '%s, %s' % (html.escape(n), v), 420)
                                       for n, f in [cols[0], cols[3], colB]) + '</div>')
        h.append('<p>The flags\' measure on the design grids (each part a shade; the drawn lines inside the mass blue, '
                 'our ink dark red):</p>')
        for n, d in (('A', ours), ('B', B)):
            h.append(fig(img, os.path.join(d, 'qa', 'qa_hair_flags.png'), 'flags_%s.png' % n,
                         '%s: qa_hair_flags.png' % n, 300))
    if S.get('calls'):
        h.append('<h2>The lock truth\'s open calls (yes / no)</h2><p>Each picture: the body sheet (the authority) | '
                 'the lock truth (each lock its own shade in its family\'s hue; unscored hatched grey) | the '
                 'line-art takes registered onto the sheet\'s grid.</p>')
        for k, c in enumerate(S['calls']):
            h.append('<p class="q">%s</p><p>Default meanwhile: %s</p>' % (c['q'], c['default']))
            for j, (src, cap) in enumerate(c.get('pics', [])):
                h.append(fig(img, src, 'call%d_%d.png' % (k, j), cap, 300))
    if opt('--ref'):
        R = json.load(open(opt('--ref')))
        h.append('<h2>The last reference attempt: a lock-level line-art hair sheet (one call, n=2)</h2><p>%s</p>'
                 % R.get('rule', ''))
        for j, src in enumerate(R.get('sheets', [])):
            h.append(fig(img, src, 'ref_take%d.png' % (j + 1), 'take %d: %s' % (j + 1, os.path.relpath(src, ROOT)),
                         300))
        h.append('<table><tr>%s</tr>%s</table>' % (''.join('<th>%s</th>' % c for c in R.get('head', [])), ''.join(
            '<tr>%s</tr>' % ''.join('<td>%s</td>' % c for c in r) for r in R.get('rows', []))))
        h.append('<p><b>Outcome:</b> %s</p>' % R.get('outcome', ''))
    for name in ('front', 'back', 'profile', 'three_quarter'):
        if opt('--truth') and os.path.exists(os.path.join(opt('--truth'), name + '.png')) and not S.get('calls'):
            h.append(fig(img, os.path.join(opt('--truth'), name + '.png'), 'truth_%s.png' % name, name, 300))
    open(os.path.join(out, 'index.html'), 'w').write('\n'.join(h))
    print(os.path.join(out, 'index.html'))


if __name__ == '__main__':
    main(sys.argv[1:])
