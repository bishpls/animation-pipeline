"""hair round 4's review page: per view the design, round 3 and round 4 side by side at matching scale (the render
box's boards: face_000, face_030, face_090, and body_180 for the back), the buns per view in the design's own projection
(the lab's crops on the QA's grids: drawn outline blue, ours red), the edges pictures, and the numbers table.
    python tools/hair4/page.py OUTDIR R3_RENDER_BUILD R4_RENDER_BUILD LAB_R3 LAB_R4 TABLE.json
LAB_*: a lab.py output prefix (DIR/NAME: NAME_buns.png, NAME_edges.png). TABLE.json: {title, summary, rows [{k, design,
before, after, note, cls}], open [..]}."""
import html, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from PIL import Image

out, rb, ra, lb, la, tab = sys.argv[1:7]
os.makedirs(out, exist_ok=True)
HT = os.path.join(ROOT, 'charkit/refs/clawd/gen/head_turnaround.png')


def fg_mask(a, tol=0.08):
    bg = np.median(np.r_[a[:4].reshape(-1, 3), a[-4:].reshape(-1, 3)], 0)
    return np.abs(a - bg).max(2) > tol


def figures(a, gap=12):
    fg = fg_mask(a)
    on = np.r_[False, fg.sum(0) > 2, False]
    cols, x = [], 0
    while x < len(on) - 1:
        if on[x + 1] and not on[x]:
            s = x
            while x < len(on) - 1 and (on[x + 1] or on[x + 1:x + 1 + gap].any()):
                x += 1
            cols.append((s, x))
        x += 1
    return [c for c in cols if c[1] - c[0] > 50]


def top_width(a, frac=0.22):
    """the figure's widest row in its top `frac` (the buns' outer width)."""
    fg = fg_mask(a)
    rows = np.nonzero(fg.any(1))[0]
    r0 = rows.min(); r1 = r0 + int(frac * (rows.max() - r0))
    return max(np.ptp(np.nonzero(fg[r])[0]) if fg[r].any() else 0 for r in range(r0, r1))


def board(b, n):
    return np.asarray(Image.open(os.path.join(ROOT, 'charkit/out', b, 'boards', n + '.png')).convert('RGB')).astype(float) / 255


def save(a, name, s=1.0):
    im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    if s != 1.0:
        im = im.resize((max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s))), Image.LANCZOS)
    im.save(os.path.join(out, name))
    return name, im.size


ht = np.asarray(Image.open(HT).convert('RGB')).astype(float) / 255
dviews = dict(zip(('front', 'three_quarter', 'profile', 'back'), figures(ht)[:4]))
f0 = board(rb, 'face_000')
s_design = top_width(f0) / top_width(ht[:, dviews['front'][0]:dviews['front'][1] + 1])
s_back = top_width(f0) / top_width(board(rb, 'body_000'))
BOARDS = dict(front='face_000', three_quarter='face_030', profile='face_090', back='body_180')
rows = []
for v, (x0, x1) in dviews.items():
    d = ht[:, x0:x1 + 1]
    rr = np.nonzero(fg_mask(d).any(1))[0]
    d = d[rr.min():int(rr.min() + 0.62 * (rr.max() - rr.min()))]          # the head, buns to the neck
    cells = [('design: head_turnaround.png (%s)' % v, save(d, 'design_%s.png' % v, s_design))]
    for tag, b in (('round 3', rb), ('round 4', ra)):
        a = board(b, BOARDS[v])
        s = s_back if v == 'back' else 1.0
        if v == 'back':
            fg = fg_mask(a); r_ = np.nonzero(fg.any(1))[0]
            a = a[r_.min():r_.min() + int(a.shape[0] * 0.3)]
        cells.append(('%s: %s/boards/%s.png' % (tag, b, BOARDS[v]), save(a, '%s_%s.png' % (tag.replace(' ', ''), v), s)))
    rows.append((v, cells))

T = json.load(open(tab))
h = ['<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">'
     '<title>Hair round 4</title><style>',
     ':root{--bg:#f6f5f2;--fg:#1d1d1f;--mut:#666;--line:#ddd;--good:#1a7f37;--bad:#b42318}',
     '@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#17171a;--fg:#ececec;--mut:#9a9a9a;'
     '--line:#333;--good:#4ac26b;--bad:#ff7b72}}',
     'body{background:var(--bg);color:var(--fg);font:14px/1.45 -apple-system,system-ui,sans-serif;margin:0 16px 40px}',
     'h1{font-size:22px;margin:18px 0 4px}h2{font-size:17px;margin:26px 0 8px}p{max-width:900px;color:var(--mut)}',
     'table{border-collapse:collapse;margin:8px 0}td,th{border-bottom:1px solid var(--line);padding:4px 10px;'
     'text-align:left;vertical-align:top}.tw{overflow-x:auto}',
     '.row{display:flex;gap:10px;align-items:flex-end;overflow-x:auto;padding-bottom:6px}.row figure{margin:0}',
     'figcaption{font-size:12px;color:var(--mut);max-width:420px}img{display:block;background:#fff;max-width:none}',
     '.good{color:var(--good)}.bad{color:var(--bad)}</style>',
     '<h1>%s</h1>' % html.escape(T.get('title', 'Hair round 4')), '<p>%s</p>' % html.escape(T.get('summary', ''))]
h.append('<h2>Numbers</h2><div class="tw"><table><tr><th>check</th><th>design / target</th><th>round 3</th>'
         '<th>round 4</th><th>note</th></tr>')
for r in T['rows']:
    cls = r.get('cls', '')
    h.append('<tr><td>%s</td><td>%s</td><td>%s</td><td class="%s">%s</td><td>%s</td></tr>' % (
        html.escape(str(r['k'])), html.escape(str(r.get('design', ''))), html.escape(str(r['before'])), cls,
        html.escape(str(r['after'])), html.escape(str(r.get('note', '')))))
h.append('</table></div>')
h.append('<h2>Renders: design | round 3 | round 4</h2><p>The render box\'s boards (round 3: %s, round 4: %s); the '
         'design scaled to the boards by the buns\' outer width (x%.3f); the back from body_180, scaled by body_000 '
         'against face_000 (x%.3f). The boards are 85 mm close-ups; face_030 stands in for the design\'s 35.5 degree '
         'three-quarter. The design\'s own orthographic projection is in the bun and edge pictures below.</p>'
         % (html.escape(rb), html.escape(ra), s_design, s_back))
for v, cells in rows:
    h.append('<h3>%s</h3><div class="row">' % v)
    for cap, (name, size) in cells:
        h.append('<figure><a href="%s"><img src="%s" width=%d height=%d></a><figcaption>%s</figcaption></figure>' % (
            name, name, size[0], size[1], html.escape(cap)))
    h.append('</div>')
h.append('<h2>The buns per view, in the design\'s projection (the QA\'s grids): drawn filled blue, outline blue; '
         'ours filled orange, outline red; both mauve; the rest of our hair grey</h2>')
for tag, p in (('round 3', lb), ('round 4', la)):
    src = p + '_buns.png'
    if os.path.exists(src):
        name = 'buns_%s.png' % tag.replace(' ', '')
        im = Image.open(src); im.save(os.path.join(out, name))
        h.append('<figure><a href="%s"><img src="%s" width=%d></a><figcaption>%s: %s</figcaption></figure>' % (
            name, name, min(im.size[0], 2400), tag, html.escape(src)))
h.append('<h2>Edges at the head sheet\'s scale (400 px/L): the design\'s hair beside ours per view, each lock its own '
         'tone; shards ringed red, a lock inside another magenta, silhouette steps blue, inner-line steps green</h2>')
for tag, p in (('round 3', lb), ('round 4', la)):
    src = p + '_edges.png'
    if os.path.exists(src):
        name = 'edges_%s.png' % tag.replace(' ', '')
        im = Image.open(src); im.save(os.path.join(out, name))
        h.append('<figure><a href="%s"><img src="%s" width=%d></a><figcaption>%s: %s</figcaption></figure>' % (
            name, name, min(im.size[0], 2400), tag, html.escape(src)))
h.append('<h2>Open items</h2><ul>%s</ul>' % ''.join('<li>%s</li>' % html.escape(x) for x in T.get('open', [])))
open(os.path.join(out, 'index.html'), 'w').write('\n'.join(h))
print(os.path.join(out, 'index.html'), 's_design %.3f s_back %.3f' % (s_design, s_back))
