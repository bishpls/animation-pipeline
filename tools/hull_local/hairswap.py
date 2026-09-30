"""Which input moves a hair piece between two builds (tool/hull-local; face round 5's terminator): the hair pieces
(charkit.cli.pieces_hair's run, venv-side) rebuilt on build B's resolved inputs with one input at a time taken from
build A: its head (head_code.npz) or its hull (the produced hull's folder), and each piece compared with both builds'
own. Also the inputs the buns' fit reads: the head's centre (Case.centre) and the bun points (the hull's samples the
families call buns).

    python tools/hull_local/hairswap.py OUT.json BUILD_A HULL_A BUILD_B HULL_B [--pieces bun_L,bun_R] [--variants ...]

BUILD: a build's folder (geom/pieces.spec.json, geom/head_code.npz, geom/hair_pieces/); HULL: its hull's folder (the
produced hull the build read; locality.py's a/ and b/ reproduce them). Variants: B (B's inputs: reproduces B's pieces),
B+headA, B+hullA."""
import contextlib, io, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import numpy as np


def _cut(build, hull_dir, head_code):
    s = json.load(open(os.path.join(build, 'geom', 'pieces.spec.json')))
    s['head_code'] = head_code
    s['hair'] = dict(s['hair'], shape=dict(s['hair']['shape'], glb=os.path.join(hull_dir, 'hull.glb')))
    s.pop('garments_geom', None)
    fix = lambda v: ROOT + '/' + v.split('/animation-pipeline-', 1)[1].split('/', 1)[1] \
        if isinstance(v, str) and v.startswith('/srv/work/') else v
    walk = lambda o: {k: walk(v) for k, v in o.items()} if isinstance(o, dict) else \
        [walk(v) for v in o] if isinstance(o, list) else fix(o)
    return walk(s)


def run(cut, spec_full):
    """cli.pieces_hair's run on `cut` -> (the pieces {name: V}, the head centre, the bun points)."""
    from PIL import Image
    from charkit import manifest, styles, cli
    from charkit.geom import hairpieces as hp, hull, io as gio, parts
    path = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'hairswap.spec.json')
    json.dump(cut, open(path, 'w'))
    with contextlib.redirect_stdout(io.StringIO()):
        C = parts.Case.load(path, fit=False)
        glb = C.align['glb']
        side = json.load(open(glb + '.json'))
        Vh = gio.load(glb)
        lab = np.load(os.path.join(os.path.dirname(glb), side['labels']))
        pcs = np.load(os.path.join(os.path.dirname(glb), side['pieces']))
        M = manifest.load(spec_full['ref']['manifest'])
        sheet = cli._path(M['references']['body_turnaround']['path'])
        rgb = np.asarray(Image.open(sheet).convert('RGB')).astype(float) / 255
        views, info = hull.views_from_sheet(rgb, (spec_full.get('eyes') or {}).get('x', 0.168), -1)
        Z = np.load(manifest.produced(spec_full, 'hair_layers'))
        masks = {k: Z[k] for k in Z.files}
        shape = cut['hair']['shape']
        fam, counts = hp.label_hull(np.asarray(Vh.V), np.asarray(Vh.F), lab, pcs, side['piece_names'], views, masks,
                                    info['ppl'])
        style = styles.load(cut.get('style', 'anime'))['hair_pieces']
        R = hp.build(C, fam, masks, style, views=views, hull_frame=(C.align['scale'], np.asarray(C.align['translate'])),
                     opts=shape.get('pieces_opts'), log=lambda *a: None)
    s, tr = C.align['scale'], np.asarray(C.align['translate'])
    buns = np.asarray(Vh.V)[fam == hp.fam_id('buns')] * s + tr
    return {n: np.asarray(p['V'], float) for n, p in R['pieces'].items()}, np.asarray(C.centre, float), buns, \
        R['report'].get('bun_fit')


def own(build):
    from charkit.geom import hairpieces as hp
    d = os.path.join(build, 'geom', 'hair_pieces')
    out = {}
    for f in os.listdir(d):
        if f.endswith('.npz'):
            out[f[:-4]] = np.asarray(np.load(os.path.join(d, f))['V'], float)
    return out


def main(a):
    out, bA, hA, bB, hB = a[:5]
    only = a[a.index('--pieces') + 1].split(',') if '--pieces' in a else None
    variants = a[a.index('--variants') + 1].split(',') if '--variants' in a else ['B', 'B+headA', 'B+hullA']
    from charkit import bodyeval
    spec_full = bodyeval.resolve('charkit/spec/clawd.json')
    L = 0.25
    PA, PB = own(bA), own(bB)
    res = {'A': bA, 'B': bB, 'variants': {}}
    heads = {'A': os.path.join(bA, 'geom', 'head_code.npz'), 'B': os.path.join(bB, 'geom', 'head_code.npz')}
    for v in variants:
        head = heads['A'] if 'headA' in v else heads['B']
        hull_dir = hA if 'hullA' in v else hB
        t = time.time()
        P, centre, buns, fit = run(_cut(bB, hull_dir, head), spec_full)
        row = {'seconds': round(time.time() - t), 'centre': centre.round(7).tolist(), 'bun_points': int(len(buns)),
               'bun_points_sum': float(buns.sum()), 'bun_fit': fit, 'pieces': {}}
        for n, V in P.items():
            if only and n not in only:
                continue
            d = {}
            for tag, ref in (('vs_A', PA), ('vs_B', PB)):
                if n in ref and len(ref[n]) == len(V):
                    d[tag] = float('%.3g' % (np.linalg.norm(ref[n] - V, axis=1).max() / L))
            row['pieces'][n] = d
        res['variants'][v] = row
        print(v, json.dumps(row), flush=True)
    json.dump(res, open(out, 'w'), indent=1)


if __name__ == '__main__':
    main(sys.argv[1:])
