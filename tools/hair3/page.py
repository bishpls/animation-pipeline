"""the round's review page: hair close-ups (design | before | after) per view at matching scale, the numbers table.
    python page.py OUTDIR BEFORE_RENDER_BUILD AFTER_RENDER_BUILD LAB_BEFORE_PREFIX LAB_AFTER_PREFIX TABLE.json"""
import html, json, os, sys
sys.path.insert(0, os.path.expanduser('~/animation-pipeline-hair3'))
import numpy as np
from PIL import Image

out, rb, ra, lb, la, tab = sys.argv[1:7]
os.makedirs(out, exist_ok=True)
ROOT = os.path.expanduser('~/animation-pipeline-hair3')
HT = os.path.join(ROOT, 'charkit/refs/clawd/gen/head_turnaround.png')


def fg_mask(a, tol=0.08):
    bg = np.median(np.r_[a[:4].reshape(-1, 3), a[-4:].reshape(-1, 3)], 0)
    return np.abs(a - bg).max(2) > tol


def figures(a, gap=12):
    fg = fg_mask(a)
    on = np.r_[False, fg.sum(0) > 2, False]
    cols = []
    x = 0
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
    w = [np.ptp(np.nonzero(fg[r])[0]) if fg[r].any() else 0 for r in range(r0, r1)]
    return max(w)


ht = np.asarray(Image.open(HT).convert('RGB')).astype(float) / 255
figs = figures(ht)
dviews = dict(zip(('front', 'three_quarter', 'profile', 'back'), figs[:4]))
board = lambda b, n: np.asarray(Image.open(os.path.join(ROOT, 'charkit/out', b, 'boards', n + '.png')).convert('RGB')).astype(float) / 255
f0 = board(rb, 'face_000')
s_design = top_width(f0) / top_width(ht[:, dviews['front'][0]:dviews['front'][1] + 1])
s_back = top_width(board(rb, 'face_000')) / top_width(board(rb, 'body_000'))
BOARDS = dict(front='face_000', three_quarter='face_030', profile='face_090', back='body_180')


def crop_fig(a, s):
    fg = fg_mask(a)
    rr, cc = np.nonzero(fg)
    return a[max(0, rr.min() - 10):rr.max() + 10, max(0, cc.min() - 10):cc.max() + 10], s


def save(a, name, s=1.0, h=None):
    im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    if s != 1.0:
        im = im.resize((max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s))), Image.LANCZOS)
    im.save(os.path.join(out, name))
    return name, im.size


rows = []
for v, (x0, x1) in dviews.items():
    d = ht[:, x0:x1 + 1]
    rr = np.nonzero(fg_mask(d).any(1))[0]
    d = d[rr.min():int(rr.min() + 0.62 * (rr.max() - rr.min()))]          # the head, buns to the neck
    dn = save(d, 'design_%s.png' % v, s_design)
    cells = [('design (head_turnaround)', dn)]
    for tag, b in (('before', rb), ('after', ra)):
        a = board(b, BOARDS[v])
        s = s_back if v == 'back' else 1.0
        if v == 'back':
            fg = fg_mask(a); r_ = np.nonzero(fg.any(1))[0]
            a = a[r_.min():r_.min() + int(a.shape[0] * 0.3)]
        cells.append(('%s: %s %s.png' % (tag, b, BOARDS[v]), save(a, '%s_%s.png' % (tag, v), s)))
    rows.append((v, cells))

# the measurement pictures: the design's hair and our locks at the head sheet's scale (400 px/L), before and after
lab_rows = []
for v in ('front', 'three_quarter', 'profile', 'back'):
    cells = []
    for tag, p in (('before', lb), ('after', la)):
        img = os.path.join(os.path.dirname(p), os.path.basename(p) + '.png')
        cells.append((tag, img))
    lab_rows.append(v)

T = json.load(open(tab))
h = ['<!doctype html><meta charset=utf-8><title>Hair round 3</title><style>',
     ':root{--bg:#f6f5f2;--fg:#1d1d1f;--mut:#666;--line:#ddd;--good:#1a7f37;--bad:#b42318}',
     '@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#17171a;--fg:#ececec;--mut:#9a9a9a;--line:#333;--good:#4ac26b;--bad:#ff7b72}}',
     'body{background:var(--bg);color:var(--fg);font:14px/1.45 -apple-system,system-ui,sans-serif;margin:0 16px 40px}',
     'h1{font-size:22px;margin:18px 0 4px}h2{font-size:17px;margin:26px 0 8px}p{max-width:900px;color:var(--mut)}',
     'table{border-collapse:collapse;margin:8px 0}td,th{border-bottom:1px solid var(--line);padding:4px 10px;text-align:left;vertical-align:top}',
     '.row{display:flex;gap:10px;align-items:flex-end;overflow-x:auto;padding-bottom:6px}.row figure{margin:0}',
     'figcaption{font-size:12px;color:var(--mut);max-width:420px}img{display:block;background:#fff;max-width:none}',
     '.good{color:var(--good)}.bad{color:var(--bad)}</style>',
     '<h1>Hair round 3: torn tips, crown, side locks, buns</h1>',
     '<p>%s</p>' % html.escape(T.get('summary', ''))]
h.append('<h2>Numbers (hairlab over the same bundle, before = the defaults at 6ca18da, after = this branch)</h2><table>'
         '<tr><th>check</th><th>design</th><th>before</th><th>after</th><th>note</th></tr>')
for r in T['rows']:
    cls = r.get('cls', '')
    h.append('<tr><td>%s</td><td>%s</td><td>%s</td><td class="%s">%s</td><td>%s</td></tr>' % tuple(
        html.escape(str(x)) if i != 3 else x for i, x in enumerate((r['k'], r.get('design', ''), r['before'], cls, r['after'],
                                                                    r.get('note', '')))))
h.append('</table>')
h.append('<h2>Renders (the render box\'s boards: before %s, after %s; the design scaled to the boards by the buns\' '
         'width; the back from body_180, scaled by body_000 against face_000)</h2>' % (rb, ra))
for v, cells in rows:
    h.append('<h3>%s</h3><div class="row">' % v)
    for cap, (name, size) in cells:
        h.append('<figure><a href="%s"><img src="%s" width=%d height=%d></a><figcaption>%s</figcaption></figure>' % (
            name, name, size[0], size[1], html.escape(cap)))
    h.append('</div>')
h.append('<h2>Measured at the head sheet\'s scale (400 px/L): the design\'s hair beside ours per view, each lock its own '
         'tone; shards ringed red, a lock inside another magenta, silhouette steps blue, inner-line steps green</h2>')
for tag, p in (('before', lb), ('after', la)):
    src = p + '.png'
    name = 'edges_%s.png' % tag
    im = Image.open(src)
    im.save(os.path.join(out, name))
    h.append('<h3>%s</h3><div class="row"><figure><a href="%s"><img src="%s" width=%d></a><figcaption>%s</figcaption>'
             '</figure></div>' % (tag, name, name, min(im.size[0], 2400), html.escape(src)))
for tag, p in (('before', lb), ('after', la)):
    for kind in ('bun', 'face'):
        src = '%s_%s.png' % (p, kind)
        if os.path.exists(src):
            name = '%s_%s.png' % (kind, tag)
            Image.open(src).save(os.path.join(out, name))
    h.append('')
h.append('<h2>Buns (front, profile at the QA\'s scale: drawn outline blue, ours red) and face shown (green both, red '
         'ours only, blue the design\'s only)</h2>')
for kind in ('bun', 'face'):
    h.append('<div class="row">')
    for tag in ('before', 'after'):
        name = '%s_%s.png' % (kind, tag)
        if os.path.exists(os.path.join(out, name)):
            w = Image.open(os.path.join(out, name)).size[0]
            h.append('<figure><a href="%s"><img src="%s" width=%d></a><figcaption>%s %s</figcaption></figure>' % (
                name, name, min(w, 900), kind, tag))
    h.append('</div>')
h.append('<h2>Open items</h2><ul>%s</ul>' % ''.join('<li>%s</li>' % html.escape(x) for x in T.get('open', [])))
open(os.path.join(out, 'index.html'), 'w').write('\n'.join(h))
print(os.path.join(out, 'index.html'), 's_design %.3f s_back %.3f' % (s_design, s_back))
