"""The hair layers against the hand-checked truth, as a review page: per view the sheet, the truth, and for each mask set
its labels and its errors, side by side at one scale; the scores per view and family, the confusions, the bun sides.

    python tools/hairtag/review.py OUT_DIR NAME=MASKS.npz [NAME=MASKS.npz ...] [--views front,profile,back,three_quarter]
"""
import json, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from charkit import hairlayers as hl
from truthpic import COL

Z = 3


def _crop(T):
    ys, xs = np.nonzero(T >= 0)
    return max(0, ys.min() - 10), ys.max() + 10, max(0, xs.min() - 10), xs.max() + 10


def _img(a, box, path):
    from PIL import Image
    r0, r1, c0, c1 = box
    Image.fromarray((np.clip(a[r0:r1, c0:c1], 0, 1) * 255).astype(np.uint8)).resize(
        ((c1 - c0) * Z, (r1 - r0) * Z), Image.NEAREST).save(path)


def labels_pic(rgb, lab, sides=None):
    """a label image (object array of family names, '' none) over the sheet; bun sides in their two blues."""
    pic = rgb * 0.45 + 0.55
    for f, c in COL.items():
        m = lab == f
        pic[m] = 0.3 * rgb[m] + 0.7 * np.array(c)
    if sides is not None:
        for s in ('bun_L', 'bun_R'):
            m = sides == s
            pic[m] = 0.3 * rgb[m] + 0.7 * np.array(COL[s])
    return pic


def main(a):
    out = a[0]
    sets_ = [x.split('=', 1) for x in a[1:] if '=' in x and not x.startswith('--')]
    views = (a[a.index('--views') + 1].split(',') if '--views' in a else ['front', 'profile', 'back', 'three_quarter'])
    from charkit import manifest
    spec = manifest.resolve(json.load(open(os.path.join(ROOT, 'charkit/spec/clawd.json'))))
    ent = manifest.load(spec['ref']['manifest'])['references']['hair_truth']
    truth = hl.load_truth(ent['path'])
    T, sets, meta = truth
    dv, _ = hl.design(spec)
    img = os.path.join(out, 'img'); os.makedirs(img, exist_ok=True)
    scores = {}
    masks = {}
    for name, p in sets_:
        M = np.load(p if os.path.isabs(p) else os.path.join(ROOT, p))
        masks[name] = {k: M[k] for k in M.files}
        scores[name] = hl.score(masks[name], truth)
    json.dump(scores, open(os.path.join(out, 'scores.json'), 'w'), indent=1)
    rows = []
    for v in views:
        t = T[v]; rgb = np.asarray(dv[v]['rgb']); box = _crop(t)
        tl = np.full(t.shape, '', object); ts = np.full(t.shape, '', object)
        for i, st in enumerate(sets):
            m = t == i
            tl[m] = hl._fam(st[0]) if st[0] != 'none' else 'none'
            if st[0] in ('bun_L', 'bun_R'):
                ts[m] = st[0]
        pic = labels_pic(rgb, tl, ts)
        yy, xx = np.mgrid[0:t.shape[0], 0:t.shape[1]]
        stripe = ((yy + xx) // 3) % 2 == 0
        for i, st in enumerate(sets):                         # a set: its second label in stripes
            if len(st) > 1:
                m = (t == i) & stripe
                pic[m] = 0.3 * rgb[m] + 0.7 * np.array(COL[st[1]])
        _img(rgb, box, os.path.join(img, '%s_sheet.png' % v))
        _img(pic, box, os.path.join(img, '%s_truth.png' % v))
        cells = ['<figure><img src="img/%s_sheet.png"><figcaption>sheet (body_turnaround)</figcaption></figure>' % v,
                 '<figure><img src="img/%s_truth.png"><figcaption>truth (stripes: a set\'s second label)</figcaption>'
                 '</figure>' % v]
        for name in masks:
            M = masks[name]
            got = np.full(t.shape, '', object)
            for f in hl.FAMILIES:
                k = '%s__%s' % (v, f)
                if k in M:
                    got[M[k] & (got == '')] = f
            gs = np.full(t.shape, '', object)
            for s in ('bun_L', 'bun_R'):
                k = '%s__%s' % (v, s)
                if k in M:
                    gs[M[k]] = s
            _img(labels_pic(rgb, got, gs), box, os.path.join(img, '%s_%s.png' % (v, name)))
            fam_view = any(k.startswith(v + '__') and k.split('__')[1] in hl.FAMILIES for k in M)
            ok = np.zeros(t.shape, bool); bad = np.zeros(t.shape, bool)
            for i, st in enumerate(sets):
                m = t == i
                if fam_view:
                    acc = [hl._fam(q) for q in st] + ([''] if st == ['none'] else [])
                    ok |= m & np.isin(got, acc); bad |= m & ~np.isin(got, acc)
                else:                                          # sides only: the buns' sides
                    sd = [q for q in st if q in ('bun_L', 'bun_R')]
                    if sd:
                        acc = sd + ([''] if st[0] not in ('bun_L', 'bun_R') else [])
                        ok |= m & np.isin(gs, acc); bad |= m & ~np.isin(gs, acc)
                    else:
                        bad |= m & (gs != ''); ok |= m & (gs == '')
            err = rgb * 0.25 + 0.75
            err[ok] = (0.75, 0.9, 0.75); err[bad] = (0.9, 0.1, 0.1)
            _img(err, box, os.path.join(img, '%s_%s_err.png' % (v, name)))
            s = scores[name].get(v)
            cap = ('accuracy %.3f, %d px wrong' % (s['accuracy'], s['wrong'])) if s else 'bun sides only'
            sd = scores[name]['sides'].get(v, {})
            cap += '; sides ' + ', '.join('%s %s' % kv for kv in sd.items())
            cells.append('<figure><img src="img/%s_%s.png"><figcaption><b>%s</b></figcaption></figure>' % (v, name, name))
            cells.append('<figure><img src="img/%s_%s_err.png"><figcaption>%s errors: %s</figcaption></figure>'
                         % (v, name, name, cap))
        rows.append('<h2>%s</h2><div class="row">%s</div>' % (v, ''.join(cells)))
    fams = hl.FAMILIES
    head = '<tr><th>masks</th>' + ''.join('<th>%s</th>' % v for v in views if v != 'three_quarter') + \
        '<th>all</th><th>mean IoU</th>' + ''.join('<th>%s</th>' % f for f in fams) + '</tr>'
    body = ''
    for name, r in scores.items():
        body += '<tr><td>%s</td>' % name + ''.join('<td>%.3f</td>' % r[v]['accuracy'] for v in views if v in r) + \
            '<td><b>%.3f</b></td><td>%.3f</td>' % (r['all']['accuracy'], r['all']['mean_iou']) + \
            ''.join('<td>%s</td>' % r['all']['iou'].get(f, '') for f in fams) + '</tr>'
    side_rows = ''.join('<tr><td>%s</td>%s</tr>' % (name, ''.join(
        '<td>%s</td>' % ', '.join('%s %s' % kv for kv in r['sides'].get(v, {}).items()) for v in views))
        for name, r in scores.items())
    conf = ''.join('<h3>%s</h3><table><tr><th>px</th><th>view</th><th>truth</th><th>got</th></tr>%s</table>' % (
        name, ''.join('<tr><td>%d</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (c['px'], c['view'], c['truth'],
                                                                              c['got'])
                      for c in r['all']['confusions'])) for name, r in scores.items())
    legend = ' '.join('<span style="background:rgb(%d,%d,%d);padding:1px 6px">%s</span>' % (
        *(np.array(c) * 255).astype(int), f) for f, c in COL.items())
    calls = ''.join('<li>%s</li>' % c for c in (meta.get('calls') or []))
    rules = ''.join('<li>%s</li>' % c for c in (meta.get('rules') or []))
    html = ('<!doctype html><meta charset="utf-8"><title>Hair tag review</title><style>'
            ':root{--bg:#fafafa;--fg:#222;--mut:#666;--bd:#ddd}body{font:14px/1.45 -apple-system,system-ui,sans-serif;'
            'margin:24px;background:var(--bg);color:var(--fg)}table{border-collapse:collapse;font-size:13px;margin:8px 0}'
            'td,th{border:1px solid var(--bd);padding:3px 8px;text-align:right}td:first-child{text-align:left}'
            '.row{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-start}figure{margin:0}figure img{height:420px;'
            'border:1px solid var(--bd)}figcaption{font-size:12px;color:var(--mut);max-width:380px}</style>'
            '<h1>Hair layers against the hand-checked truth</h1><p>%s</p>'
            '<p>Truth: <code>%s</code> (%d regions, from <code>%s</code>). Errors: green where the masks\' family is in the '
            'truth\'s set, red where not (lines, cut paths and slivers unscored, white). The three-quarter has bun sides '
            'only.</p><h2>Scores (hair accuracy per view; family IoU)</h2><table>%s%s</table>'
            '<h3>Bun sides (IoU)</h3><table><tr><th>masks</th>%s</tr>%s</table>'
            '<h3>Split rules</h3><ol>%s</ol><h3>Calls that decide numbers</h3><ol>%s</ol>%s%s') % (
        legend, ent['path'], meta.get('regions', 0), ent.get('source'), head, body,
        ''.join('<th>%s</th>' % v for v in views), side_rows, rules, calls, ''.join(rows),
        '<h2>Largest confusions</h2>' + conf)
    open(os.path.join(out, 'index.html'), 'w').write(html)
    print(os.path.join(out, 'index.html'))


if __name__ == '__main__':
    main(sys.argv[1:])
