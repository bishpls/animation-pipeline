"""The authored body's venv side: its fit saved for the build (save_body: the fit needs scipy and the produced
references), its measures and its review page (charkit/code_body.py builds it): each part against the hull's points
that measure it, the torso's sections, and the parts z-buffered over the drawing through the QA's projection. Apart from
code_body so the build's stages don't depend on the QA.

    python -m charkit.bodypage SPEC [--out DIR]
"""
import json, os

import numpy as np

from .code_body import (CUT, TIGHT, TORSO_SKIN_X, Hull, arm_mask, body, section_r, skeleton)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def save_body(spec, path, log=print):
    """venv-side (the fit needs scipy): the authored body's rings in the hull's frame, per part, with what the build
    needs to rig it -> path (.npz), which build_body_data reads in Blender."""
    from . import manifest
    hull_path = manifest.produced(spec, 'hull', log)
    masks = manifest.produced(spec, 'outfit_masks', log)
    H = Hull(os.path.dirname(hull_path))
    graph = json.load(open(os.path.join(os.path.dirname(masks), 'outfit_graph.json')))
    sk = skeleton(graph)
    B = body(H, sk)
    T_ = B['torso']
    ax, F = T_['ax'], T_['F']
    TT, TH = np.meshgrid(F.ts, F.th, indexing='ij')
    arrays = {'torso_P': ax.point(TT, TH, F.R), 'torso_z': T_['rows'], 'torso_cy': T_['params'][:, 4],
              'sole_z': np.array(float(H.V[:, 2].min()))}
    for n, L_ in B['limbs'].items():
        ch, P, rows, th = L_['chain'], L_['params'], L_['rows'], L_['th']
        R = np.stack([section_r(P[k], th, 0.0) for k in range(len(rows))])
        S, THl = np.meshgrid(rows, th, indexing='ij')
        arrays[n + '_P'] = ch.point(S, THl, R)
        arrays[n + '_s'] = rows
        arrays[n + '_J'] = ch.J
        arrays[n + '_s0'] = np.r_[ch.s0, ch.total]
    from .code_body import foot_rings
    for n, F_ in B['feet'].items():
        arrays[n + '_P'] = foot_rings(F_)
        arrays[n + '_front'] = np.array(F_['front'])
        arrays[n + '_back'] = np.array(F_['back'])
    arrays['skeleton'] = np.array(json.dumps({k: [list(a), list(b)] for k, (a, b) in sk.items()}))
    np.savez_compressed(path, **arrays)
    log('code body: %s' % path)
    return path


def signed_out(B, ax, F):
    """per point of the design (B, on its surface), how far our torso stands out of it (L; + out: it would bury a piece
    lying there)."""
    t, th, r = ax.coords(B)
    return F.at(t, th) - r


def measure(H, T, sk):
    """the torso against the hull: per tight piece, where our torso stands out of it (median, p90, share out by more
    than 0.02 L, all after its pull-in), within the torso's rows."""
    out = {}
    lo, hi = T['F'].ts[0], T['F'].ts[-1]
    for name, dt in TIGHT.items():
        Q = H.points(name)
        if name == 'skin':
            Q = Q[(np.abs(Q[:, 0]) < TORSO_SKIN_X) & (Q[:, 2] <= CUT + 0.02) & (Q[:, 2] > -1.0)]
        if not len(Q):
            continue
        Q = Q[~arm_mask(Q, sk)]
        t = T['ax'].coords(Q)[0]
        Q = Q[(t >= lo) & (t <= hi)]
        if not len(Q):
            continue
        s = signed_out(Q, T['ax'], T['F']) + dt
        out[name] = dict(n=int(len(Q)), median=round(float(np.median(s)), 4), p90=round(float(np.percentile(s, 90)), 4),
                         out=round(float((s > 0.02).mean()), 3))
    return out


def limb_out(L_, H):
    """where a limb stands out of the design's points that measure it (L; + out), after each one's pull-in."""
    out = {}
    ch, P, rows = L_['chain'], L_['params'], L_['rows']
    for Q, dt in L_['src']:
        s_, th, r, _ = ch.coords(Q)
        k = np.clip(np.rint(np.interp(s_, rows, np.arange(len(rows)))).astype(int), 0, len(rows) - 1)
        mine = np.array([section_r(P[kk], np.array([t_]), 0.0)[0] for kk, t_ in zip(k, th)])
        d = mine - (r - dt) - dt
        out.setdefault('all', []).append(d)
    d = np.concatenate(out['all'])
    return dict(n=int(len(d)), median=round(float(np.median(d)), 4), p90=round(float(np.percentile(d, 90)), 4),
                out=round(float((d > 0.02).mean()), 3))


def views(meshes, H, spec):
    """our parts z-buffered on the design's full-figure grids (the QA's projection: bodyqa.origin, faceqa.zbuffer),
    in the hull's frame and units -> ({view: label image (part index, -1 none)}, the design's views, names)."""
    from . import bodyqa, bodymeasure
    from .faceqa import zbuffer
    sheet = bodymeasure.Sheet(spec)
    names = list(meshes)
    M = [(meshes[n][0], meshes[n][1], np.full(len(meshes[n][1]), i)) for i, n in enumerate(names)]
    iris = np.array(H.eyes, float)
    az = bodyqa.azimuths(sheet.az3)
    out = {}
    for v in sheet.design:
        org = bodyqa.origin(v, az[v], iris, np.array([0.0, float(iris[:, 1].mean()) + 0.35, 0.0]))
        out[v] = zbuffer(M, az[v], org, 1.0, 1.0 / sheet.ppl, bodyqa.WIN)[1]
    return out, sheet.design, names


def page(H, T, sk, out, rep):
    """the torso's review page: sections at several heights (the hull's envelope points, the measured points, our
    section), the rows' measured share, and the numbers."""
    import html
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(os.path.join(out, 'img'), exist_ok=True)
    ax, F = T['ax'], T['F']
    picks = np.linspace(0, len(T['rows']) - 1, 12).astype(int)
    fig, axs = plt.subplots(3, 4, figsize=(14, 10.5))
    hair = H.piece == H.ids.get('hair', -1)
    allE = H.V[~hair]
    for a_, k in zip(axs.flat, picks):
        z = T['rows'][k]
        E = allE[np.abs(allE[:, 2] - z) < 0.02]
        E = E[~arm_mask(E, sk)]
        a_.scatter(E[:, 0], E[:, 1], s=2, c='#bbb', label='hull (not hair, not arms)')
        for Q, dt in T['src']:
            q = Q[np.abs(Q[:, 2] - z) < 0.02]
            if len(q):
                a_.scatter(q[:, 0], q[:, 1], s=4, label='measured (pull-in %.3f)' % dt)
        th = np.linspace(-np.pi, np.pi, 200)
        p = ax.point(np.full(200, F.ts[k]), th, F.at(np.full(200, F.ts[k]), th))
        a_.plot(p[:, 0], p[:, 1], 'k-', lw=1.5, label='our torso')
        a_.set_title('z %.2f L  measured %.0f%%' % (z, 100 * T['measured'][k]), fontsize=10)
        a_.set_aspect('equal'); a_.invert_yaxis(); a_.set_xlim(-1.1, 1.1); a_.set_ylim(0.9, -0.7)
    axs.flat[0].legend(fontsize=7, loc='lower left')
    fig.tight_layout()
    fig.savefig(os.path.join(out, 'img', 'sections.png'), dpi=90)
    plt.close(fig)
    L = ['<!doctype html><meta charset="utf-8"><title>authored torso</title><style>body{font:14px/1.45 -apple-system,'
         'system-ui,sans-serif;margin:24px;background:#fafafa;color:#222}table{border-collapse:collapse;font-size:13px}'
         'td,th{border:1px solid #ddd;padding:3px 8px;text-align:right}th{background:#f0f0f0}td:first-child{text-align:'
         'left}.note{color:#555;font-size:13px;max-width:980px}img{max-width:100%;border:1px solid #ddd}</style>',
         '<h1>The authored torso against the hull</h1>',
         '<p class="note">Sections seen from above (x across, the front up). Grey: the hull at that height (the '
         'design\'s outer surface, hair and arms left out). Colours: the points that measure the torso (a tight piece '
         'or bare skin, each pulled in by its thickness). Black: our torso. Where nothing measures a row, it is '
         'interpolated between measured rows and anchors and held inside the grey. The table: where our torso stands '
         'out of each tight piece (L; + out). The MakeHuman body under the top: median +0.077, p90 +0.155, 86%% out '
         'by more than 0.02 L.</p>',
         '<table><tr><th>piece</th><th>points</th><th>median</th><th>p90</th><th>share out &gt; 0.02 L</th></tr>']
    for k, v in rep['out'].items():
        L.append('<tr><td>%s</td><td>%d</td><td>%+.3f</td><td>%+.3f</td><td>%.0f%%</td></tr>' % (
            html.escape(k), v['n'], v['median'], v['p90'], 100 * v['out']))
    L.append('</table><h2>Sections</h2><img src="img/sections.png">')
    if rep.get('views'):
        L.append('<h2>The body against the drawing</h2><p class="note">Our authored body (torso and limbs, separate parts: '
                 'their joins sit under the puffs, shorts, cuffs and boots) outlined in white over the design; the body '
                 'tinted where it shows. It should sit inside the clothes and meet the skin where skin shows.</p>'
                 '<img src="img/views.png">')
    open(os.path.join(out, 'index.html'), 'w').write('\n'.join(L))
    json.dump(rep, open(os.path.join(out, 'torso.json'), 'w'), indent=1)
    return os.path.join(out, 'index.html')


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return 0
    from . import manifest
    spec = manifest.resolve(json.load(open(args[0])))
    out = args[args.index('--out') + 1] if '--out' in args else os.path.join(ROOT, 'charkit', 'out', 'body', spec['name'])
    hull_path = manifest.produced(spec, 'hull')
    masks = manifest.produced(spec, 'outfit_masks')
    H = Hull(os.path.dirname(hull_path))
    sk = skeleton(json.load(open(os.path.join(os.path.dirname(masks), 'outfit_graph.json'))))
    B = body(H, sk)
    T = B['torso']
    rep = {'out': measure(H, T, sk), 'measured_rows': [round(float(x), 3) for x in T['measured']],
           'rows': [round(float(z), 3) for z in T['rows']],
           'limbs': {n: limb_out(L_, H) for n, L_ in B['limbs'].items()}}
    for n, v in rep['limbs'].items():
        rep['out'][n] = v
    lab, dv, names = views(B['meshes'], H, spec)
    os.makedirs(os.path.join(out, 'img'), exist_ok=True)
    cols = []
    for v, lb in lab.items():
        img = 0.55 * np.asarray(dv[v]['rgb'], float) + 0.15
        m = lb >= 0
        img[m] = 0.55 * img[m] + 0.45 * np.array([0.35, 0.75, 0.95])
        from .bodymeasure import outline
        img[outline(m)] = (1.0, 1.0, 1.0)
        cols.append(img)
    Hh = max(c.shape[0] for c in cols)
    from PIL import Image
    pic = np.concatenate([np.pad(c, ((0, Hh - c.shape[0]), (0, 6), (0, 0)), constant_values=1.0) for c in cols], 1)
    Image.fromarray((np.clip(pic, 0, 1) * 255).astype(np.uint8)).save(os.path.join(out, 'img', 'views.png'))
    rep['views'] = list(lab)
    for k, v in rep['out'].items():
        print('%-10s n %5d  median %+.3f  p90 %+.3f  out>0.02 %.0f%%' % (k, v['n'], v['median'], v['p90'], 100 * v['out']))
    print(page(H, T, sk, out, rep))
    return 0



if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv[1:]))
