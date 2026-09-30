"""the taper lab: the jaw's shape checks (charkit.faceregion: taper_front, tq_jaw, taper_compare: the V against a U, the
three-quarter's hollow and notch) with the jaw's other checks, on a build's bundle or a local assembly of a build's head
and body code (the skin alone, subdivided once; 30 s), and the design against itself; a picture of the outlines and the
taper curves.
    python taper_lab.py OUT.png BUILD_DIR            # the bundle (the whole scene)
    python taper_lab.py OUT.png --geom GEOM_DIR      # a local assembly: GEOM_DIR/head_code.npz, body_code.npz
    python taper_lab.py OUT.png --design             # the design against itself (the checks' own floor)
JSON=path writes the numbers; DESIGN_CACHE=path.pkl keeps the design's side between runs."""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import numpy as np
from PIL import Image, ImageDraw
from charkit import faceregion as fr

import jaw_lab

SHOW = ('jaw_taper_shape', 'jaw_line_bend', 'chin_angle', 'chin_tip', 'tq_cheek_hollow', 'tq_jaw_notch', 'jaw_taper',
        'chin_point_z', 'chin_v', 'neck_to_face', 'jaw_line_front', 'jaw_line_three_quarter', 'chin_underside',
        'neck_front_wiggle')


def scene(build=None, geom=None, log=print):
    """-> (meshes, skin, iris, eye_z, L, extra)."""
    if build:
        from charkit import bundle as bl, qa3d
        B = bl.load(os.path.join(build, 'bundle'))
        meshes, _ = qa3d.scene_classes(B)
        V, T, _, _ = B.skin().mesh('masked')
        return meshes, (V, T), qa3d.iris_centres(B), float(B.assembly['eye_z']), float(B.assembly['L']), None
    V, T, iris, ez, L, A = jaw_lab.local(geom)
    jaw_lab.extra(A, V, log)
    return [(V, T, np.ones(len(T), int))], (V, T), iris, ez, L, A


def run(out=None, build=None, geom=None, design_only=False, log=print):
    spec = jaw_lab.spec_of()
    t0 = time.time()
    cache = os.environ.get('DESIGN_CACHE')           # (a pickle of the design's side: it doesn't change between tries)
    if cache and os.path.exists(cache):
        import pickle
        D, ppl, Dc, az = pickle.load(open(cache, 'rb'))
    else:
        D, ppl, Dc, az = fr.design_jaw(spec, 0.168)
        if cache:
            import pickle
            pickle.dump((D, ppl, Dc, az), open(cache, 'wb'))
    z0 = D['front']['taper']['z0']
    if design_only:
        Dt = {vn: D[vn].get('taper') for vn in ('front', 'three_quarter')}
        C = fr.taper_compare(Dt, Dt, Dt)
        O, Ob, Ol = D, Dc, Dc
    else:
        meshes, skin, iris, ez, L, _ = scene(build, geom, log)
        O, Ob, Ol = fr.ours_jaw(meshes, skin, iris, ez, L, ppl, az, D['front'].get('chin', (0, None))[1], z0,
                                design_tq_top=D['three_quarter']['taper'].get('top'))
        C = fr.jaw_compare(D, O, ppl)
        C.update(fr.taper_checks(D, O))
    for k in SHOW:
        if k in C:
            v = C[k]
            log('%-24s %-8s %-5s %s' % (k, v.get('value'), v['status'], {a: b for a, b in v.items()
                                                                         if a not in ('value', 'status', 'note')}))
    if out:
        picture(out, D, O, Dc, Ob, Ol, ppl, design_only)
        log('%s (%.1fs)' % (out, time.time() - t0))
    if os.environ.get('JSON'):
        json.dump({k: {a: b for a, b in v.items()} for k, v in C.items()}, open(os.environ['JSON'], 'w'), indent=1,
                  default=lambda x: x.tolist() if isinstance(x, np.ndarray) else str(x))
    return D, O, C


def _plot(D, O, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.6))
    cols = {'design': '#c22', 'board': '#1a5fd6', 'level': '#6a9'}
    for tag, M in (('design', D['front'].get('taper')), ('board', (O.get('front') or {}).get('taper')),
                   ('level', (O.get('front') or {}).get('taper_level'))):
        if not M:
            continue
        ax[0].plot(M['t'], M['r'], color=cols[tag], label=tag)
        if M.get('outline') is not None:
            Q = M['outline']
            ax[1].plot(Q[:, 0], Q[:, 1], color=cols[tag], label=tag)
    for tag, M in (('design', D['three_quarter'].get('taper')), ('board', (O.get('three_quarter') or {}).get('taper')),
                   ('level', (O.get('three_quarter') or {}).get('taper_level'))):
        if M and M.get('line') is not None:
            ax[2].plot(M['line'][:, 0], M['line'][:, 1], color=cols[tag], label=tag)
    ax[0].set_title('front taper w(t)/w(0)'); ax[0].set_xlabel('t (cheekbone 0, chin 1)'); ax[0].legend(); ax[0].grid(alpha=.3)
    ax[1].set_title('front lower outline (L)'); ax[1].set_aspect('equal'); ax[1].grid(alpha=.3)
    ax[2].set_title('three-quarter near jaw line: z over du'); ax[2].grid(alpha=.3)
    fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)


def picture(out, D, O, Dc, Ob, Ol, ppl, design_only=False):
    tiles = []
    for vn in ('front', 'three_quarter'):
        row = []
        for who, cls, M in (('design', Dc[vn], D[vn].get('taper')), ('ours board', Ob[vn], (O.get(vn) or {}).get('taper')),
                            ('ours level', Ol[vn], (O.get(vn) or {}).get('taper_level'))):
            if design_only and who != 'design':
                continue
            im = Image.fromarray(jaw_lab.tint(cls, fr._region(cls, fr.FACE_SEEDS, ppl)))
            d = ImageDraw.Draw(im)
            px = lambda u, z: ((u + fr.JAW_WIN['x']) * ppl, (fr.JAW_WIN['top'] - z) * ppl)
            if M:
                for key, colour in (('outline', (220, 0, 0)), ('far', (220, 0, 0))):
                    if M.get(key) is not None:
                        d.line([px(u, z) for u, z in M[key]], fill=colour, width=2)
                if M.get('line') is not None:
                    uc = M['chin'][0]
                    d.line([px(uc + du, z) for du, z in M['line']], fill=(0, 90, 220), width=2)
            d.text((6, 6), '%s %s' % (who, vn), fill=(0, 0, 0))
            row.append(im)
        tiles.append(row)
    w, h = tiles[0][0].size
    S = Image.new('RGB', (len(tiles[0]) * (w + 8), 2 * (h + 8)), 'white')
    for j, row in enumerate(tiles):
        for i, im in enumerate(row):
            S.paste(im, (i * (w + 8), j * (h + 8)))
    S.save(out)
    _plot(D, O if not design_only else {}, os.path.splitext(out)[0] + '_curves.png')


if __name__ == '__main__':
    a = sys.argv[1:]
    if '--design' in a:
        run(a[0], design_only=True)
    elif '--geom' in a:
        run(a[0], geom=a[a.index('--geom') + 1])
    else:
        run(a[0], build=a[1])
