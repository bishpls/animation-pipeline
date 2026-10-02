"""piece_top's front IoU pieces: drawn top, ours top, overlap, and where ours differs (rows by z band, |x| bands):
python tools/garments5/topiou.py BUILD.. [--piece top] [--view front]"""
import sys, os
sys.path.insert(0, '.')
import numpy as np
from charkit import bundle, qa3d, bodyqa, declared, bodymeasure
piece = sys.argv[sys.argv.index('--piece') + 1] if '--piece' in sys.argv else 'top'
view = sys.argv[sys.argv.index('--view') + 1] if '--view' in sys.argv else 'front'
for b in [a for a in sys.argv[1:] if not a.startswith('--') and a not in (piece, view)]:
    B = bundle.load(b + '/bundle')
    D = qa3d.Design(B)
    I = declared.inputs(B, D, (view,))
    ppl = I['ppl']; W = bodyqa.WIN
    lab, names = I['O'][view]['lab'], I['names']
    S = bodymeasure.piece_shapes({view: lab}, names, I['masks'], I['graph'], I['spec'], ppl)
    r = ((S.get(piece) or {}).get('views') or {}).get(view)
    print('==', os.path.basename(b), piece, view, 'iou_tol', r and round(r['iou_tol'], 4), 'px', r and r['px'])
    Md = declared.fit(I['masks']['%s__%s' % (view, piece)], lab.shape)
    from charkit import pieceqa
    Mo = pieceqa.members(lab, names, I['pm'], piece)
    for nm, M in (('ours-only', Mo & ~Md), ('drawn-only', Md & ~Mo), ('both', Mo & Md)):
        rows = np.nonzero(M.any(1))[0]
        zs = W['top'] - (np.nonzero(M)[0] + 0.5) / ppl
        xs = (np.nonzero(M)[1] + 0.5) / ppl - W['x']
        h, e = np.histogram(zs, bins=np.arange(-2.0, -0.2, 0.1))
        print('  %-10s %.4f L^2 | by z (0.1 L bands from -2.0): %s' % (nm, M.sum() / ppl ** 2,
              ' '.join('%.0f:%.3f' % (e[i] * 10, h[i] / ppl ** 2) for i in range(len(h)) if h[i])))
        hx, ex = np.histogram(np.abs(xs), bins=np.arange(0, 1.2, 0.1))
        print('  %-10s by |x|: %s' % ('', ' '.join('%.1f:%.3f' % (ex[i], hx[i] / ppl ** 2) for i in range(len(hx)) if hx[i])))
