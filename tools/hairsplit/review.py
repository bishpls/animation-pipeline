"""The splitter's review page: the summary box first (Recommended, Asked of Michael, Key numbers), then per view the
design's open strokes | the closed cells | the splitter's locks | the hand truth at one scale, the cross-view tip
matches drawn between views (call H's side flicks marked), the ablation and per-family tables beside the floors, and the
parameters (all in L or line widths). Reads the run folder that tools/hairsplit/ablation.py, crossview.py and
layercheck.py wrote; recomputes the splits for the pictures.

    python tools/hairsplit/review.py RUN_DIR SUMMARY.json [--open]      -> RUN_DIR/review/index.html
"""
import html, json, os, sys
import numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
from charkit import hairsplit as hs, hairlocks as hk
from charkit.reviewpage import CSS
import dev, pics

K = 2                     # px per design-grid px in the pictures (the design grid: 212.5 px per L)
esc = lambda s: html.escape(str(s))


def crop_box(S, T):
    r0, r1, c0, c1 = S.box
    return r0, r1, c0, c1


def truth_colours(t):
    """the truth: each lock its colour (seeded by its index), unscored hatched dark, out of the truth plain."""
    return np.where(t >= 0, t + 1, 0)


def panels(S, T, labels, img_dir):
    r0, r1, c0, c1 = S.box
    base = (S.rgb * 255).astype(np.uint8)
    out = {}
    # 1: the open strokes: the ink black, the free ends blue, the extensions red, the notch lines orange
    a = (0.45 * base + 0.55 * 255).astype(np.uint8)
    a[~S.H] = [255, 255, 255]
    a[S.ink] = [0, 0, 0]
    im = Image.fromarray(pics.zoom(a, K)); d = ImageDraw.Draw(im)
    for e in S.ends:
        r, c = e['rc']
        d.ellipse([(c * K - 3, r * K - 3), (c * K + 3, r * K + 3)], fill=(0, 120, 255))
    out['strokes'] = im
    # 2: the closed cells (the closing: drawn ink, extensions, trapped balls)
    b = pics.colour(S.cells, S.rgb, 0.75, seed=3)
    b[pics.edges(S.cells) & S.H] = [0, 0, 0]
    b[S.ext] = [230, 0, 0]
    out['cells'] = Image.fromarray(pics.zoom(b, K))
    # 3: the locks with the tips, the axes and the crown
    c_ = pics.colour(S.locks, S.rgb, 0.75, seed=5)
    c_[pics.edges(S.locks) & S.H] = [0, 0, 0]
    im = Image.fromarray(pics.zoom(c_, K)); d = ImageDraw.Draw(im)
    for t in S.tip_list:
        ax = t['axis'][::5]
        if len(ax) > 1:
            d.line([(p[1] * K, p[0] * K) for p in ax], fill=(255, 255, 255), width=1)
        r, c = t['rc']
        d.ellipse([(c * K - 4, r * K - 4), (c * K + 4, r * K + 4)], outline=(220, 0, 0), width=2)
    for t in S.notch_list:
        r, c = t['rc']
        d.rectangle([(c * K - 3, r * K - 3), (c * K + 3, r * K + 3)], outline=(0, 60, 255), width=2)
    d.ellipse([(S.crown[1] * K - 6, S.crown[0] * K - 6), (S.crown[1] * K + 6, S.crown[0] * K + 6)], outline=(255, 0, 255),
              width=2)
    out['locks'] = im
    # 4: the hand truth
    t = T[r0:r1, c0:c1]
    e = pics.colour(truth_colours(t), S.rgb, 0.75, seed=11)
    e[t == -2] = (0.45 * e[t == -2]).astype(np.uint8)
    out['truth'] = Image.fromarray(pics.zoom(e, K))
    files = {}
    for k, im in out.items():
        fn = '%s_%s.png' % (S.view, k)
        im.save(os.path.join(img_dir, fn))
        files[k] = 'img/' + fn
    return files


def match_pictures(splits, shell, img_dir, H_tips):
    """per pair of views, the two locks pictures side by side with a line between matched tips (call H's side flicks
    in red, the rest grey)."""
    files = {}
    tm = getattr(shell, 'tip_matches', []) or []
    for m in tm:
        va, vb = m['views']
        A, B = splits[va], splits[vb]
        ia = Image.fromarray(pics.zoom((A.rgb * 255).astype(np.uint8), 1))
        ib = Image.fromarray(pics.zoom((B.rgb * 255).astype(np.uint8), 1))
        h = max(ia.size[1], ib.size[1])
        W = ia.size[0] + ib.size[0] + 20
        cv = Image.new('RGB', (W, h), (255, 255, 255))
        cv.paste(ia, (0, 0)); cv.paste(ib, (ia.size[0] + 20, 0))
        d = ImageDraw.Draw(cv)
        hset = set()
        if va == 'front' and vb == 'back':
            for q, x in H_tips.items():
                for a_, b_, c in x.get('linked', []):
                    hset.add((a_, b_))
        for a_, b_, c in m['pairs']:
            pa, pb = A.tip_list[a_]['rc'], B.tip_list[b_]['rc']
            col = (220, 0, 0) if (a_, b_) in hset else (90, 90, 90)
            d.line([(pa[1], pa[0]), (pb[1] + ia.size[0] + 20, pb[0])], fill=col, width=2 if col[0] > 200 else 1)
            for (r, c), off in ((pa, 0), (pb, ia.size[0] + 20)):
                d.ellipse([(c + off - 3, r - 3), (c + off + 3, r + 3)], outline=col, width=2)
        fn = 'match_%s_%s.png' % (va, vb)
        cv.save(os.path.join(img_dir, fn))
        files[(va, vb)] = ('img/' + fn, len(m['pairs']), len(hset))
    return files


def table_html(cols, rows, fmt='%.3f'):
    h = ['<table><tr>%s</tr>' % ''.join('<th>%s</th>' % esc(c) for c in cols)]
    for r in rows:
        h.append('<tr>%s</tr>' % ''.join('<td>%s</td>' % (esc(x) if not isinstance(x, float) else fmt % x) for x in r))
    h.append('</table>')
    return ''.join(h)


if __name__ == '__main__':
    a = sys.argv[1:]
    run, summ = a[0], json.load(open(a[1]))
    out = os.path.join(run, 'review'); img = os.path.join(out, 'img')
    os.makedirs(img, exist_ok=True)
    I = dev.load_inputs()
    T = hk.load_truth('charkit/refs/clawd/hair_locks_truth.npz')
    splits, shell, xid, matches = hs.split_views(I, log=lambda *x: None)
    abl = json.load(open(os.path.join(run, 'ablation.json')))['table']
    xv = json.load(open(os.path.join(run, 'crossview.json')))
    H = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">',
         '<title>Hair lock splitter</title><style>%s</style><h1>The hair lock splitter (tool/hairsplit)</h1>' % CSS]
    S_ = summ['summary']
    H.append('<div class="box summary"><p><b>Recommended:</b> %s</p><p><b>Asked of Michael:</b></p><ul>%s</ul>' % (
        esc(S_['recommended']), ''.join('<li>%s</li>' % esc(q) for q in S_['asked'])))
    nums = S_['numbers']
    H.append('<p><b>Key numbers</b> (lock IoU against the 52-lock hand truth, unmatched locks 0):</p>%s</div>' %
             table_html(nums['columns'], nums['rows']))
    for p in summ.get('notes', []):
        H.append('<p>%s</p>' % esc(p))
    # per view
    H.append('<h2>Per view: open strokes | closed cells | the splitter\'s locks | the hand truth</h2><p class="k">'
             'All four at one scale (%d px per design-grid px; 212.5 px per L). Strokes: the ink the splitter reads '
             '(black) and its strokes\' free ends (blue). Cells: the closing (each upstream free end extended along the '
             'flow, red, and the hem\'s notch lines; trapped balls). Locks: each lock its colour, the tips (red rings), '
             'their axes traced up the flow (white), the notches (blue squares), the crown (magenta). Truth: each lock '
             'its colour, unscored hair darkened, buns and hair outside the truth plain.</p>' % K)
    for v, S in splits.items():
        f = panels(S, T[0][v], T[1][v], img)
        tb = abl['+ merge / split'].get(v, {})
        H.append('<h3>%s: lock IoU %.3f (random split %.3f, within family %.3f, today\'s build %.3f)</h3>' % (
            esc(v.replace('_', ' ')), tb.get('_all', 0), abl['random'][v]['_all'], abl['random_within_family'][v]['_all'],
            abl['h5_base'][v]['_all']))
        H.append('<div class="row cmp">%s</div>' % ''.join(
            '<figure><a href="%s"><img src="%s"></a><figcaption>%s</figcaption></figure>' % (f[k], f[k], esc(c))
            for k, c in (('strokes', 'open strokes (%d free ends)' % len(S.ends)),
                         ('cells', 'closed cells (%d)' % S.report.get('cells', 0)),
                         ('locks', 'the splitter\'s locks (%d; %d tips)' % (S.report.get('locks', 0), len(S.tip_list))),
                         ('truth', 'the hand truth (%d locks)' % len(T[1][v])))))
    # cross-view
    mf = match_pictures(splits, shell, img, xv.get('call_H_tip_to_tip', {}))
    H.append('<h2>Cross-view identity</h2><p class="k">Each tip in head-centred coordinates (its azimuth round the '
             'head\'s axis and its height, from each view\'s camera onto the hair\'s elliptic shell fitted to the front '
             'and profile silhouettes; a tip on the silhouette may lie up to 30 deg past the limb), matched between '
             'views by assignment, the hem\'s order kept. Lines join matched tips; red: call H\'s side flicks (front and '
             'back). The shell predicts the back\'s silhouette within %.3f / %.3f L and the three-quarter\'s within '
             '%.3f / %.3f L (median, either side).</p>' % (
                 shell.check['back']['lo_L'], shell.check['back']['hi_L'], shell.check['three_quarter']['lo_L'],
                 shell.check['three_quarter']['hi_L']))
    hrows = []
    for q, x in xv.get('call_H_tip_to_tip', {}).items():
        hrows.append([q, str(x.get('front')), str(x.get('back')),
                      ', '.join('%d-%d (%.3f L)' % (p[0], p[1], p[2]) for p in x.get('linked', [])) or 'no'])
    H.append('<h3>Call H, read independently</h3><p>%s</p>%s' % (esc(summ.get('call_H', '')), table_html(
        ['truth flick', 'our tips on it, front', 'back', 'linked by the matcher (cost)'], hrows)))
    for (va, vb), (fn, n, nh) in mf.items():
        H.append('<h3>%s and %s: %d tip matches</h3><div class="row cmp"><figure><a href="%s"><img src="%s"></a>'
                 '</figure></div>' % (esc(va), esc(vb), n, fn, fn))
    H.append('<p class="k">Lock-level links against the truth\'s names: precision %.2f, recall %.2f (a lock\'s tip is '
             'often in a different lock of ours than the flick\'s body: our per-view lock regions, not the tips, '
             'limit the lock-level identity).</p>' % (xv.get('precision', 0), xv.get('recall', 0)))
    # the tables
    cols = ['random', 'random_within_family', 'h5_base', 'labeller', 'ink cells', 'closing', '+ tips and flow',
            '+ merge / split']
    names = ['random split', 'random within family', "today's build (h5_base)", 'structure labeller',
             'ink cells', 'closing', '+ tips and flow', '+ merge / split (the splitter)']
    rows = []
    for v in hs.VIEWS + ('all',):
        for f in ('bangs', 'side_locks', 'lower_back', 'flyaways', 'ahoge', '_all'):
            vals = [abl[c].get(v, {}).get(f) for c in cols]
            if vals[0] is None:
                continue
            rows.append([v.replace('_', ' '), 'all' if f == '_all' else f.replace('_', ' ')] +
                        ['-' if q is None else float(q) for q in vals])
    H.append('<h2>The ablation and the floors</h2><p class="k">Lock IoU per view and family (the truth\'s locks, '
             'Hungarian-matched; unmatched 0). Ink cells: trapped balls on the drawn ink alone; closing: + the '
             'extensions and notch lines; + tips and flow: every pixel to the tip it reaches along the flow; + merge / '
             'split: the regions (several tips split along the flow; the tipless own or merged).</p>%s' % table_html(
                 ['view', 'family'] + names, rows))
    for p in summ.get('sections', []):
        H.append('<h2>%s</h2>%s' % (esc(p['title']), ''.join('<p>%s</p>' % esc(x) for x in p.get('paras', [])) +
                                     (table_html(p['table']['columns'], p['table']['rows']) if p.get('table') else '')))
    H.append('<h2>Files</h2><ul>%s</ul>' % ''.join('<li><a href="../%s">%s</a></li>' % (f, f) for f in (
        'hairsplit.json', 'hairsplit.npz', 'ablation.json', 'crossview.json', 'layers.json', 'stages.npz')
        if os.path.exists(os.path.join(run, f))))
    open(os.path.join(out, 'index.html'), 'w').write('\n'.join(H))
    print(os.path.join(out, 'index.html'))
    if '--open' in a:
        os.system('open %s' % os.path.join(out, 'index.html'))
