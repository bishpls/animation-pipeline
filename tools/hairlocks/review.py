"""The lock review page: per view the sheet | the lock truth | each lock set (ours, the labeller), each lock coloured as
the truth lock it is matched to (unmatched: hatched grey), at one scale; the per-lock numbers; the calibration; the
rules and calls.

    python tools/hairlocks/review.py OUT_DIR SCORES.json NAME=LOCKS.npz ... [--labeller]
"""
import html, json, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctx as cx, ours as ou, score as sc
from charkit import hairlocks as hk
from PIL import Image, ImageDraw, ImageFont

BOX = {'front': (95, 285, 330, 650), 'three_quarter': (95, 285, 375, 695), 'profile': (95, 300, 420, 640)}
ZOOM = 2
PAL = [(.90, .25, .25), (.95, .75, .15), (.25, .55, .95), (.30, .80, .40), (.75, .35, .90), (.10, .80, .80),
       (.95, .50, .70), (.55, .40, .20)]


def panel(rgb, labels, colours, box, names=None, hatch=None):
    from scipy import ndimage
    pic = rgb.copy()
    m = labels > 0
    for code, col in colours.items():
        k = labels == code
        pic[k] = 0.35 * rgb[k] + 0.65 * np.array(col)
    other = m & ~np.isin(labels, list(colours))
    stripe = (np.indices(labels.shape).sum(0) // 3) % 2 == 0
    pic[other] = 0.5 * rgb[other] + 0.5 * np.array([.55, .55, .55])
    pic[other & stripe] = (.35, .35, .35)
    if hatch is not None:
        pic[hatch & stripe] = 0.5 * pic[hatch & stripe] + 0.5 * np.array([1, 1, 1])
    edge = m & (ndimage.grey_dilation(labels, 3) != ndimage.grey_erosion(np.where(m, labels, 10 ** 6), 3))
    pic[edge] = (0, 0, 0)
    r0, r1, c0, c1 = box
    im = Image.fromarray((np.clip(pic[r0:r1, c0:c1], 0, 1) * 255).astype(np.uint8))
    im = im.resize(((c1 - c0) * ZOOM, (r1 - r0) * ZOOM), Image.NEAREST)
    if names:
        dr = ImageDraw.Draw(im)
        font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 12)
        for code, t in names.items():
            ys, xs = np.nonzero(labels == code)
            if len(ys) < 20:
                continue
            k = np.argmin((ys - np.median(ys)) ** 2 + (xs - np.median(xs)) ** 2)
            y, x = ys[k], xs[k]
            if r0 <= y < r1 and c0 <= x < c1:
                X, Y = (x - c0) * ZOOM, (y - r0) * ZOOM
                dr.text((X - 10, Y - 6), t, fill=(0, 0, 0), font=font, stroke_width=2, stroke_fill=(255, 255, 255))
    return im


def main(a):
    out = a[0]; os.makedirs(os.path.join(out, 'img'), exist_ok=True)
    res = json.load(open(a[1]))
    sets = [q.split('=', 1) for q in a[2:] if '=' in q]
    C = cx.make()
    T, TL, meta = hk.load_truth('charkit/refs/clawd/hair_locks_truth.npz')
    hair = sc.fillable(C)
    loaded = {n: ou.load(p) for n, p in sets}
    cols = ['sheet', 'truth'] + [n for n, _ in sets] + ['labeller']
    body = []
    for v in ('front', 'three_quarter', 'profile'):
        if v not in T:
            continue
        rgb = np.asarray(C['dv'][v]['rgb'], float)
        rgb = rgb / 255 if rgb.max() > 1.5 else rgb
        labels = TL[v]
        tcol = {i + 1: PAL[i % len(PAL)] for i in range(len(labels))}
        lcol = {lab: PAL[i % len(PAL)] for i, lab in enumerate(labels)}
        t = hk.fill_walls(T[v], hair[v])
        tim = np.where(t >= 0, t + 1, 0)
        ims = {}
        r0, r1, c0, c1 = BOX[v]
        crop = Image.fromarray((np.clip(rgb[r0:r1, c0:c1], 0, 1) * 255).astype(np.uint8)).resize(
            ((c1 - c0) * ZOOM, (r1 - r0) * ZOOM), Image.LANCZOS)
        ims['sheet'] = crop
        ims['truth'] = panel(rgb, tim, tcol, BOX[v], {i + 1: l.split('/')[1] for i, l in enumerate(labels)},
                             hatch=T[v] == -2)
        for n, _ in sets:
            img, names, _ = loaded[n]
            r = res[n][v]['locks']
            col, nm = {}, {}
            inv = {nme: code for code, nme in names.items()}
            for lab, x in r.items():
                if x.get('ours') and x['ours'] in inv:
                    col[inv[x['ours']]] = lcol[lab]
            for code, nme in names.items():
                nm[code] = nme.split('/')[-1]
            ims[n] = panel(rgb, img[v], col, BOX[v], nm, hatch=T[v] == -2)
        lab_img = hk.fill_labels(C['regions'][v], hair[v])
        r = res['labeller'][v]['locks']
        col = {int(x['ours']): lcol[lab] for lab, x in r.items() if x.get('ours') is not None}
        ims['labeller'] = panel(rgb, lab_img, col, BOX[v], hatch=T[v] == -2)
        row = []
        for k in cols:
            fn = 'img/%s_%s.png' % (v, k)
            ims[k].save(os.path.join(out, fn))
            row.append('<figure><img src="%s"><figcaption>%s</figcaption></figure>' % (fn, k))
        # the per-lock table
        th = '<tr><th>truth lock</th><th>tip</th>' + ''.join(
            '<th>%s: lock</th><th>IoU</th><th>IoU in</th><th>boundary L</th><th>lines L</th><th>tip L</th><th>tip width L</th>' % n
            for n in [n for n, _ in sets] + ['labeller']) + '</tr>'
        trs = []
        for lab in labels:
            tipk = (meta.get('tips') or {}).get(v, {}).get(lab, 'drawn')
            tds = '<td><span class="sw" style="background:rgb(%d,%d,%d)"></span>%s</td><td>%s</td>' % (
                tuple(int(255 * c) for c in lcol[lab]) + (lab, tipk))
            for n in [n for n, _ in sets] + ['labeller']:
                x = res[n][v]['locks'].get(lab, {})
                f = lambda k: '' if x.get(k) is None else x[k]
                o = x.get('ours')
                tds += '<td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>' % (
                    '-' if o is None else html.escape(str(o).split('/')[-1]), f('iou'), f('iou_in'), f('boundary_L'),
                    f('line_L'), f('tip_L'), f('width_L'))
            trs.append('<tr>%s</tr>' % tds)
        summ = []
        for n in [n for n, _ in sets] + ['labeller', 'shuffled']:
            x = res[n][v]
            summ.append('<tr><td>%s</td><td>%s</td><td>%s</td><td><b>%s</b></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td>'
                        '<td>%s</td><td>%s</td></tr>' % (
                            n, x.get('truth_locks', ''), json.dumps(x.get('count_ours', '')), x['lock_iou'],
                            x.get('lock_iou_in', ''), x.get('boundary_L', ''), x.get('line_L', ''), x.get('tip_L', ''),
                            x.get('tip_width_L', ''), x['purity']))
        body.append('<h2>%s</h2><div class="row">%s</div>' % (v, ''.join(row)) +
                    '<table class="s"><tr><th>set</th><th>truth locks</th><th>ours by family</th><th>lock IoU</th>'
                    '<th>IoU within the truth</th><th>boundary L</th><th>lines L</th><th>tip L</th><th>tip width L</th>'
                    '<th>purity</th></tr>%s</table>' % ''.join(summ) +
                    '<table class="l">%s%s</table>' % (th, ''.join(trs)))
    allrows = ''.join('<tr><td>%s</td><td><b>%s</b></td><td>%s</td><td>%s</td></tr>' % (
        n, res[n]['all']['lock_iou'], res[n]['all'].get('lock_iou_in', ''), res[n]['all']['purity'])
        for n in ['truth'] + [n for n, _ in sets] + ['labeller', 'shuffled'])
    src = json.load(open(os.path.join(ROOT, 'charkit/refs/clawd/hair_locks_truth.json')))
    page = '''<!doctype html><html><head><meta charset="utf-8"><title>Hair locks review</title><style>
body{font:13px -apple-system,Helvetica,sans-serif;margin:16px;background:#fafafa;color:#222}
.row{display:flex;gap:6px;flex-wrap:wrap}figure{margin:0}figure img{display:block;border:1px solid #ccc}
figcaption{text-align:center;font-weight:600;padding:2px}table{border-collapse:collapse;margin:8px 0}
td,th{border:1px solid #ccc;padding:2px 6px;text-align:right}th{background:#eee}td:first-child{text-align:left}
.sw{display:inline-block;width:10px;height:10px;margin-right:4px;border:1px solid #333}
.note{max-width:1100px}</style></head><body>
<h1>Hair locks: the drawing's locks against ours and the structure labeller's</h1>
<p class="note">Lock truth: <code>charkit/refs/clawd/hair_locks_truth.{json,npz}</code> (%d locks, the bangs in front,
three-quarter and profile). Each lock set is coloured by the truth lock it is matched to (Hungarian on IoU);
unmatched regions are hatched grey; the unscored crown and strips are hatched white. <b>lock IoU</b>: the mean over
the truth's locks (unmatched 0), our silhouette and family edges included; <b>IoU within the truth</b>: the partition
alone (our pixels outside the truth's locks left out); <b>boundary</b>: the matched pair's mean boundary distance;
<b>lines</b>: the truth's lock lines to our lock's boundary; <b>tip</b>: tip distance (drawn tips only); <b>tip width</b>:
the width profile over the lock's last 20%%, mean difference; <b>purity</b>: each candidate region's share in its
dominant drawn lock. <b>shuffled</b>: the truth's lock area split into as many random Voronoi cells (5 seeds): the
known-bad calibration. L = the sheet's head unit (212.5 px).</p>
<table><tr><th>set (all views)</th><th>lock IoU</th><th>IoU within the truth</th><th>purity</th></tr>%s</table>
%s
<h2>Split rules</h2><ol>%s</ol><h2>Calls that decide numbers</h2><ul>%s</ul></body></html>''' % (
        meta['locks'], allrows, ''.join(body), ''.join('<li>%s</li>' % html.escape(r.split('. ', 1)[-1]) for r in src['rules']),
        ''.join('<li>%s</li>' % html.escape(c) for c in src['calls']))
    open(os.path.join(out, 'index.html'), 'w').write(page)
    print(os.path.join(out, 'index.html'))


if __name__ == '__main__':
    main(sys.argv[1:])
