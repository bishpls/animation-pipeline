"""The buns' fit review page (tool/hull-local round 2): per bun and view, the drawn bun with the Nelder-Mead fit and its
refit after a 1 um move of the head's centre, beside the soft fit and its refit (the same move), at one scale; the
stability tables (bunstab.py's JSONs); the box builds' bun checks and terminator when given.

    python tools/hull_local/bunpage.py OUT_DIR INPUTS.pkl STAB_NM.json STAB_SOFT.json [--qa LABEL=QA.json ...]
"""
import base64, io, json, os, pickle, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import numpy as np

SCALE = 3


def silhouettes(P, hc, a, k, method, style, kind, sgn):
    from charkit.geom import hairpieces as hp, raster
    fit, rep = hp.fit_block(P, hc, *a[2:], **dict(k, method=method))
    B = hp.bun_block(P, hc, style, sgn, fit, kind)
    out = {}
    for name, az, mirror, m, other in a[3]:
        win = hp.view_window(a[4][name], az, mirror, a[5])
        d, _ = raster.window_zbuffer([(B['V'], B['T'], 1)], az, *win)
        out[name] = np.isfinite(d)
    return out, rep


def outline(m):
    from scipy.ndimage import binary_erosion
    return m & ~binary_erosion(m, border_value=0)


def panel(m, other, A, Bm, colA, colB):
    rr, cc = np.nonzero(m | A | Bm)
    r0, r1, c0, c1 = max(0, rr.min() - 12), rr.max() + 13, max(0, cc.min() - 12), cc.max() + 13
    img = np.full(m[r0:r1, c0:c1].shape + (3,), 255, np.uint8)
    img[other[r0:r1, c0:c1]] = (235, 228, 214)
    img[m[r0:r1, c0:c1]] = (200, 200, 200)
    img[outline(A[r0:r1, c0:c1])] = colA
    img[outline(Bm[r0:r1, c0:c1])] = colB
    img[outline(A[r0:r1, c0:c1]) & outline(Bm[r0:r1, c0:c1])] = (40, 40, 40)
    img = img.repeat(SCALE, 0).repeat(SCALE, 1)
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(img).save(buf, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode(), int((A ^ Bm).sum())


def main(a):
    out, inp, snm, ssoft = a[:4]
    qa = [x.split('=', 1) for x in a[a.index('--qa') + 1:]] if '--qa' in a else []
    os.makedirs(out, exist_ok=True)
    D = pickle.load(open(inp, 'rb'))
    cache = os.path.join(out, 'fits.pkl')
    fits = pickle.load(open(cache, 'rb')) if os.path.exists(cache) else {}
    for S in D['sides']:
        ar, k = S['args'], S['kwargs']
        P, hc = ar[0], np.asarray(ar[1], float)
        sgn = 1 if S['side'] == 'bun_L' else -1
        for method in ('nm', 'soft'):
            for tag, h in (('base', hc), ('moved', hc + [1e-6, 0, 0])):
                key = (S['side'], method, tag)
                if key not in fits:
                    fits[key] = silhouettes(P, h, ar, k, method, ar[2], ar[7], sgn)
                    pickle.dump(fits, open(cache, 'wb'))
    H = ['<!doctype html><meta charset="utf-8"><title>Bun fit stability</title><style>body{font:14px system-ui;'
         'margin:16px;max-width:1400px;background:#fff;color:#222}td,th{padding:3px 8px;border-bottom:1px solid #ddd;'
         'text-align:right}th{text-align:left}img{image-rendering:pixelated;border:1px solid #ccc}.row{display:flex;'
         'gap:18px;flex-wrap:wrap;align-items:flex-start}.cap{font-size:12px;color:#555;margin-top:2px}</style>',
         '<h1>The buns\' fit under a 1 &micro;m input move</h1>',
         '<p>Grey: the drawn bun (hair layers). Beige: the drawing\'s other hair. Outlines: the fit on B2\'s inputs and '
         'the refit with the head\'s centre moved 1 &micro;m (+x): Nelder-Mead red / orange, soft blue / cyan; dark where '
         'the two agree. The pixel count is the silhouettes\' disagreement.</p>']
    for tag, path in (('Nelder-Mead (until now)', snm), ('soft (this round)', ssoft)):
        R = json.load(open(path))
        H.append('<h2>%s: %s</h2><table><tr><th>bun</th><th>largest move (L)</th><th>median</th><th>x input move</th>'
                 '<th>IoU front / profile / back</th><th>seconds per fit</th></tr>' % (tag, os.path.basename(path)))
        for side, r in R['sides'].items():
            H.append('<tr><th>%s</th><td>%.3g</td><td>%.3g</td><td>%.3g</td><td>%s</td><td>%s</td></tr>' % (
                side, r['max_move_L'], r['median_move_L'], r['amplification'],
                ' / '.join('%.3f' % r['after'][v] for v in ('front', 'profile', 'back')), r['seconds']))
        H.append('</table>')
    for S in D['sides']:
        H.append('<h2>%s</h2><div class="row">' % S['side'])
        for name, az, mirror, m, other in S['args'][3]:
            for method, cols in (('nm', ((215, 40, 40), (245, 150, 30))), ('soft', ((40, 90, 220), (30, 200, 220)))):
                (A, ra), (Bm, rb) = fits[(S['side'], method, 'base')], fits[(S['side'], method, 'moved')]
                src, npx = panel(m, other, A[name], Bm[name], *cols)
                H.append('<div><img src="%s"><div class="cap">%s %s: %d px differ; IoU %.3f</div></div>' % (
                    src, name, method, npx, ra['after'][name]))
        H.append('</div>')
    if qa:
        keys = ('hair_piece_buns', 'hair_bun_outline', 'art_terminator_hair')
        H.append('<h2>Box builds</h2><table><tr><th>build</th>%s</tr>' % ''.join('<th>%s</th>' % k_ for k_ in keys))
        for label, path in qa:
            C = json.load(open(path)).get('checks', {})
            cells = []
            for k_ in keys:
                c = C.get(k_, {})
                per = c.get('views') or c.get('ratio') or {}
                cells.append('<td>%s %s<br><span class="cap">%s</span></td>' % (
                    c.get('value'), c.get('grade') or c.get('status'),
                    ', '.join('%s %s' % (v, per[v]) for v in per)))
            H.append('<tr><th>%s<br><span class="cap">%s</span></th>%s</tr>' % (label, path, ''.join(cells)))
        H.append('</table>')
    open(os.path.join(out, 'index.html'), 'w').write('\n'.join(H))
    print(os.path.join(out, 'index.html'))


if __name__ == '__main__':
    main(sys.argv[1:])
