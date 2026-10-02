"""where one object stands in front of another inside a drawn piece, per view: each object z-buffered alone on the
design's grid (pieceqa.our_labels' frame), and inside the drawn piece's mask the pixels where the front object (--front,
default top) is nearer the camera than the back one (--back, default sleeve_L), with by how much (L). Prints the share
and the depth gap's quantiles per |x| and z band; --png writes the gap map.
    python tools/garments6/depthgap.py BUILD.. [--front top] [--back sleeve_L] [--piece sleeve_L] [--png OUT.png]"""
import sys, os
sys.path.insert(0, '.')
import numpy as np
from charkit import bundle, qa3d, bodyqa, declared, pieceqa
from charkit.faceqa import zbuffer

args = sys.argv[1:]
def opt(k, d):
    if k in args:
        i = args.index(k); v = args[i + 1]; del args[i:i + 2]; return v
    return d
FRONT, BACK = opt('--front', 'top'), opt('--back', 'sleeve_L')
PIECE = opt('--piece', BACK)
PNG = opt('--png', None)
VIEWS = ('front', 'three_quarter', 'profile', 'back')
maps = []
for b in args:
    B = bundle.load(b + '/bundle')
    D = qa3d.Design(B)
    I = declared.inputs(B, D)
    ppl, W = I['ppl'], bodyqa.WIN
    meshes, names = qa3d.scene_objects(B)
    As = B.assembly
    iw = np.array(qa3d.iris_centres(B))
    az = bodyqa.azimuths(D.sheet_context()['az3'])
    pick = lambda nm: [(V, T, np.zeros(len(T), int)) for (V, T, _), n in zip(meshes, names) if n == nm]
    print('==', os.path.basename(b), FRONT, 'in front of', BACK, 'inside the drawn', PIECE)
    for v in VIEWS:
        org = bodyqa.origin(v, az[v], iw, As['centre'])
        df, lf = zbuffer(pick(FRONT), az[v], org, As['L'], 1.0 / ppl, pieceqa.WIN)
        db, lb = zbuffer(pick(BACK), az[v], org, As['L'], 1.0 / ppl, pieceqa.WIN)
        m = I['masks'].get('%s__%s' % (v, PIECE))
        if m is None:
            continue
        Md = declared.fit(m, lf.shape)
        both = (lf >= 0) & (lb >= 0) & Md
        gap = np.where(both, (db - df) / As['L'], np.nan)          # > 0: the front object nearer (depth grows away)
        bad = both & (gap > 0)
        zs = W['top'] - (np.nonzero(bad)[0] + 0.5) / ppl
        xs = (np.nonzero(bad)[1] + 0.5) / ppl - W['x']
        g = gap[bad]
        print('  %-14s drawn %s %.4f L^2; %s over it %.4f L^2 (in front %.4f L^2); gap p50 %.3f p90 %.3f max %.3f L' % (
            v, PIECE, Md.sum() / ppl ** 2, FRONT, both.sum() / ppl ** 2, bad.sum() / ppl ** 2,
            *(np.percentile(g, [50, 90, 100]) if len(g) else (0, 0, 0))))
        if len(g):
            for z0 in np.arange(-0.4, -1.2, -0.1):
                k = (zs <= z0) & (zs > z0 - 0.1)
                if k.sum() > 5:
                    print('     z %.1f..%.1f: x %.2f..%.2f  %.4f L^2  gap p50 %.3f max %.3f' % (
                        z0, z0 - 0.1, xs[k].min(), xs[k].max(), k.sum() / ppl ** 2, np.median(g[k]), g[k].max()))
        maps.append((os.path.basename(b), v, gap, Md, ppl))
if PNG:
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, len(maps), figsize=(4.5 * len(maps), 4.5), squeeze=False)
    for i, (nm, v, gap, Md, ppl) in enumerate(maps):
        W = bodyqa.WIN
        r0, r1 = int((W['top'] + 0.35) * ppl), int((W['top'] + 1.2) * ppl)
        c0, c1 = int((W['x'] - 0.9) * ppl), int((W['x'] + 0.9) * ppl)
        a = ax[0, i]
        a.imshow(Md[r0:r1, c0:c1], cmap='Greys', alpha=0.25, extent=[-0.9, 0.9, -1.2, -0.35])
        im = a.imshow(gap[r0:r1, c0:c1], cmap='RdBu_r', vmin=-0.08, vmax=0.08, extent=[-0.9, 0.9, -1.2, -0.35])
        a.set_title('%s %s: %s - %s depth (red: %s nearer)' % (nm, v, BACK, FRONT, FRONT), fontsize=7)
        a.grid(alpha=0.3)
    fig.colorbar(im, ax=ax.ravel().tolist(), shrink=0.6)
    fig.savefig(PNG, dpi=80)
    print(PNG)
