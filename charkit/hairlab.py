"""The hair pieces' lab: charkit.geom.hairpieces rebuilt venv-side over a finished build's bundle with style, opts and
shape overrides, and measured by the QA's own hair checks (qa3d.hair_pieces_measure) without Blender, in about 20 s a
variant. The loop behind each hair piece default (docs/workstreams/hair.md).

    python -m charkit hairlab BUILD [--style KEY=VALUE ...] [--opts KEY=VALUE ...] [--shape KEY=VALUE ...]
                                    [--labels OUT.png]

  BUILD    a build with its hair in pieces (its bundle, geom/pieces.spec.json and the hull it read)
  --style  the style profile's hair_pieces keys (e.g. notch=3 relief=0.015)
  --opts   hairpieces.build's opts (e.g. bun=block fine_tips=bangs,side_lock_L carve_buns=false)
  --shape  the spec's hair.shape keys, before the case is aligned (e.g. eye_anchor=iris)
  --labels the QA scene's family labels per view (front, profile, back) with the drawn families' outlines over them

Prints the hair checks (value, drawn or piece, status), the face shown against the design's per view (our skin above
the chin over the drawing's: the hair hiding or showing the face), the builder's folds and the bun fit's IoU.
"""
import json, os, re, sys, time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAL = np.array([(40, 40, 40), (230, 120, 60), (60, 160, 230), (120, 200, 90), (200, 90, 200), (240, 220, 60),
                (250, 250, 250), (160, 160, 160)], float)       # skin/other, then qa3d.HAIR_FAMILIES in order
KEYS = ('hair_piece_upper_back', 'hair_piece_lower_back', 'hair_piece_bangs', 'hair_piece_side_locks', 'hair_piece_buns',
        'hair_bun_outline', 'hair_bun_corners', 'hair_tips_front', 'hair_tips_back', 'hair_fringe_low',
        'hair_penetration')


def context(build, shape_over=None):
    """everything a variant needs from a build: its bundle and design, the case (its cut spec, paths made local and
    the shape overrides applied), the hull's family labels, the hair layers, the views and the style."""
    from PIL import Image
    from . import bundle as bl, manifest, qa3d, styles
    from .geom import hairpieces as hp, hull, io as gio, parts
    B = bl.load(os.path.join(build, 'bundle'))
    D = qa3d.Design(B)
    txt = open(os.path.join(build, 'geom', 'pieces.spec.json')).read()
    txt = re.sub(r'/srv/work/[^/"]+/', ROOT + '/', txt)          # (a box build's absolute paths)
    spec = json.loads(txt)
    spec['hair']['shape'].update(shape_over or {})
    import tempfile
    cut = os.path.join(tempfile.mkdtemp(prefix='hairlab-'), 'pieces.spec.json')
    json.dump(spec, open(cut, 'w'))
    C = parts.Case.load(cut, fit=False)
    glb = C.align['glb']
    side = json.load(open(glb + '.json'))
    Vh = gio.load(glb)
    lab = np.load(os.path.join(os.path.dirname(glb), side['labels']))
    pcs = np.load(os.path.join(os.path.dirname(glb), side['pieces']))
    M = manifest.load(spec['ref']['manifest'])
    rgb = np.asarray(Image.open(M['references']['body_turnaround']['path']).convert('RGB')).astype(float) / 255
    views, info = hull.views_from_sheet(rgb, (spec.get('eyes') or {}).get('x', 0.168), -1)
    Z = np.load(manifest.produced(spec, 'hair_layers'))
    masks = {k: Z[k] for k in Z.files}
    fam, _ = hp.label_hull(np.asarray(Vh.V), np.asarray(Vh.F), lab, pcs, side['piece_names'], views, masks, info['ppl'])
    style = styles.load(spec.get('style', 'anime'))['hair_pieces']
    return dict(B=B, D=D, C=C, masks=masks, views=views, fam=fam, style=style, spec=spec)


def labels_for(ctx, hair, views=('front', 'profile', 'back'), only=None):
    """the QA's z-buffered labels (hair_pieces_measure's scene: skin, eyes, mouth, garments, the hair by family) for
    {piece: ((V, T), raw)}; only: just these pieces, nothing else."""
    from . import bodyqa, qa3d
    B, D = ctx['B'], ctx['D']
    sc = D.sheet_context()
    As = B.assembly
    fam_k = {f: k + 1 for k, f in enumerate(qa3d.HAIR_FAMILIES)}
    meshes = []
    if only is None:
        V, T = B.skin().mesh('masked')[:2]
        meshes.append((V, T, np.zeros(len(T), int)))
        for o in B.objects(groups=('eye', 'mouth', 'accessory', 'garment')):
            if o.has('eval'):
                V, T = o.mesh('eval')[:2]
                meshes.append((V, T, np.zeros(len(T), int)))
    for n, (ev, _) in hair.items():
        if only is None or n in only:
            meshes.append((ev[0], ev[1], np.full(len(ev[1]), fam_k[qa3d.HAIR_PIECE_FAMILY[n]])))
    return bodyqa.zbuffer_views(meshes, sc['az3'], np.array(qa3d.iris_centres(B)), As['centre'], As['L'], sc['ppl'],
                                list(views))


def face_shown(ctx, hair):
    """per view (front, three-quarter, profile): our skin above the chin that shows past the hair, over the design's."""
    from . import bodyqa, qa3d
    B, D = ctx['B'], ctx['D']
    sc = D.sheet_context()
    As = B.assembly
    V, T = B.skin().mesh('masked')[:2]
    meshes = [(V, T, np.ones(len(T), int))]
    for o in B.objects(groups=('eye', 'mouth')):
        if o.has('eval'):
            V, T = o.mesh('eval')[:2]
            meshes.append((V, T, np.ones(len(T), int)))
    for o in B.objects(groups=('accessory', 'garment')):
        if o.has('eval'):
            V, T = o.mesh('eval')[:2]
            meshes.append((V, T, np.full(len(T), 3)))
    for ev, _ in hair.values():
        meshes.append((ev[0], ev[1], np.full(len(ev[1]), 2)))
    dv = D.design_views()
    lab = bodyqa.zbuffer_views(meshes, sc['az3'], np.array(qa3d.iris_centres(B)), As['centre'], As['L'], sc['ppl'],
                               [v for v in ('front', 'three_quarter', 'profile') if v in dv])
    W, ppl, out = bodyqa.WIN, sc['ppl'], {}
    for v, (_, lb) in lab.items():
        z = W['top'] - (np.arange(lb.shape[0]) + 0.5) / ppl
        head = ((z > -0.42) & (z < 0.35))[:, None]
        dsk = (dv[v]['cls'] == bodyqa.CLASS['skin']) & head
        out[v] = round(float(((lb == 1) & head).sum()) / max(1, dsk.sum()), 3)
    return out


def run(ctx, style_over=None, opts=None):
    """a variant: the pieces rebuilt with the overrides and measured. -> (build's result, checks, face shown)."""
    from . import qa3d
    from .geom import hairpieces as hp
    C = ctx['C']
    R = hp.build(C, ctx['fam'], ctx['masks'], dict(ctx['style'], **(style_over or {})), views=ctx['views'],
                 hull_frame=(C.align['scale'], np.asarray(C.align['translate'])),
                 opts=dict(ctx['spec']['hair']['shape'].get('pieces_opts') or {}, **(opts or {})), log=lambda *a: None)
    hair = {n: ((p['V'], np.asarray(p['T'])),) * 2 for n, p in R['pieces'].items()}
    _, Cq = qa3d.hair_pieces_measure(ctx['B'], ctx['D'], hair)
    return R, Cq, face_shown(ctx, hair), hair


def label_image(ctx, hair, path, views=('front', 'profile', 'back'), rows=(0, 260), scale=2):
    """the QA scene's family labels per view (bangs orange, side locks blue, upper back green, lower back purple, buns
    yellow, ahoge white, flyaways grey; skin dark), the drawn families' outlines over them darker, cropped to rows."""
    from PIL import Image
    from . import bodymeasure, qa3d
    tiles = []
    for v in views:
        L = labels_for(ctx, hair, views=(v,))[v][1]
        img = PAL[np.clip(L, 0, len(PAL) - 1)]
        img[L < 0] = (90, 90, 90)
        for i, f in enumerate(qa3d.HAIR_FAMILIES):
            m = ctx['masks'].get('%s__%s' % (v, f))
            if m is not None:
                img[bodymeasure.outline(m)] = PAL[i + 1] * 0.45
        cols = np.nonzero((L > 0).any(0))[0]
        tiles.append(img[rows[0]:rows[1], max(0, cols.min() - 20):cols.max() + 20])
    out = np.concatenate([np.pad(t, ((0, 0), (0, 6), (0, 0)), constant_values=20) for t in tiles], 1)
    Image.fromarray(out.astype(np.uint8)).resize((out.shape[1] * scale, out.shape[0] * scale), Image.NEAREST).save(path)
    return path


def _kv(args, flag):
    """KEY=VALUE pairs after flag (until the next --flag), values parsed as JSON where they parse, a comma list as a
    tuple of them."""
    out = {}
    if flag not in args:
        return out
    for a in args[args.index(flag) + 1:]:
        if a.startswith('--'):
            break
        k, v = a.split('=', 1)
        parse = lambda x: json.loads(x) if re.fullmatch(r'-?[\d.]+|true|false|null', x) else x
        out[k] = tuple(parse(x) for x in v.split(',')) if ',' in v else parse(v)
    return out


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return 0
    build = os.path.abspath(args[0])
    t = time.time()
    ctx = context(build, _kv(args, '--shape'))
    R, Cq, fs, hair = run(ctx, _kv(args, '--style'), _kv(args, '--opts'))
    for k in KEYS:
        if k in Cq:
            c = Cq[k]
            print('%-24s %s %s %s' % (k, c.get('value'), c.get('drawn', c.get('piece', '')), c.get('status')))
    print('%-24s %s' % ('face_shown/design', fs))
    print('%-24s %s' % ('folds (builder)', {k: r.get('folds') for k, r in R['report']['pieces'].items()}))
    if 'bun_fit' in R['report']:
        print('%-24s %s' % ('bun fit IoU', json.dumps(R['report']['bun_fit'])))
    if '--labels' in args:
        print('labels', label_image(ctx, hair, os.path.abspath(args[args.index('--labels') + 1])))
    print('(%.0f s)' % (time.time() - t))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
