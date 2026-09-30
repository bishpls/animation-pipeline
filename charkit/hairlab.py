"""The hair pieces' lab: charkit.geom.hairpieces rebuilt venv-side over a finished build's bundle with style, opts and
shape overrides, and measured by the QA's own hair checks (qa3d.hair_pieces_measure) without Blender, in about 20 s a
variant. The loop behind each hair piece default (docs/workstreams/hair.md).

    python -m charkit hairlab BUILD [--style KEY=VALUE ...] [--opts KEY=VALUE ...] [--shape KEY=VALUE ...]
                                    [--labels OUT.png] [--noise] [--edges] [--edges-json J] [--edges-png P]
                                    [--buns] [--buns-png P]
    python -m charkit hairlab BUILD --built [--buns] [--edges-json J] [--edges-png P]   # the build's own hair, as built

  BUILD    a build with its hair in pieces (its bundle, geom/pieces.spec.json and the hull it read)
  --style  the style profile's hair_pieces keys (e.g. notch=3 relief=0.015)
  --opts   hairpieces.build's opts (e.g. bun=block fine_tips=bangs,side_lock_L carve_buns=false)
  --shape  the spec's hair.shape keys, before the case is aligned (e.g. eye_anchor=iris)
  --labels the QA scene's family labels per view (front, profile, back) with the drawn families' outlines over them
  --noise  hair_noise's measure for the rebuilt pieces (drawn with the build's hair materials and their shading normals)
  --edges  torn tips and jagged edges (round 3): fragments per view and the outline's teeth, ours against the design's
           own (hair_fragments_<view>, hair_rough_<view>, hair_rough_back_lower, hair_rough_profile_front, ...)
  --built  measure the build's hair as built (its bundle's hair objects), no rebuild: any build, e.g. a flagged one
  --buns   the buns per view, the three-quarter and back too (round 4), each bun apart and both: IoU and outline against
           the hair layers' bun sides (hairlayers.bun_sides); --buns-png P the crops

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
    samples = {'mesh': (fam, None)}
    S = hp.hull_samples(glb)
    if S is not None:                       # (the labelled shell: docs/HULL_CONTRACT.md, hair round 4)
        f2, _ = hp.label_hull(np.asarray(Vh.V), np.asarray(Vh.F), S[1], S[2], side['piece_names'], views, masks,
                              info['ppl'], P=S[0], NP=S[3])
        samples['shell'] = (f2, S[0] * C.align['scale'] + np.asarray(C.align['translate']))
        if os.environ.get('HAIRLAB_SHELL_BLOCK'):          # (a lab comparison: the shell thinned to one per block^3)
            b_ = int(os.environ['HAIRLAB_SHELL_BLOCK'])
            S2 = hp.hull_samples(glb, block=b_)
            f4, _ = hp.label_hull(np.asarray(Vh.V), np.asarray(Vh.F), S2[1], S2[2], side['piece_names'], views, masks,
                                  info['ppl'], P=S2[0], NP=S2[3])
            samples['shell_b'] = (f4, S2[0] * C.align['scale'] + np.asarray(C.align['translate']))
        if os.environ.get('HAIRLAB_SHELL_MESHN'):          # (a lab comparison: the shell with the mesh's normals)
            f3, _ = hp.label_hull(np.asarray(Vh.V), np.asarray(Vh.F), S[1], S[2], side['piece_names'], views, masks,
                                  info['ppl'], P=S[0])
            samples['shell_meshn'] = (f3, samples['shell'][1])
    style = styles.load(spec.get('style', 'anime'))['hair_pieces']
    return dict(B=B, D=D, C=C, masks=masks, views=views, fam=fam, style=style, spec=spec, samples=samples)


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


BUN_VIEWS = ('front', 'three_quarter', 'profile', 'back')
BUN_CODE = {'bun_L': 21, 'bun_R': 22}      # (the scene's other hair 11, the rest 0: clear of bodyqa.CLASS['line'])


def bun_views(ctx, hair, views=BUN_VIEWS, labels=None):
    """the buns against the drawn ones in every view the sheet draws them (hair round 4): per view, each bun apart
    (L, R) and both together, our visible bun (the QA's scene z-buffered on the design's grids) against the hair
    layers' bun sides (VIEW__bun_L / _R, hairlayers.bun_sides): IoU and the outline agreement at qa3d.HAIR_BUN_TOL
    (bodymeasure.outline_f, as hair_bun_outline). 'qa' pools both buns' outline over the views hair_bun_outline reads
    (those with a VIEW__buns layer: front and profile), 'all' over the four. -> dict."""
    from . import bodymeasure, bodyqa, qa3d
    B, D, masks = ctx['B'], ctx['D'], ctx['masks']
    sc = D.sheet_context()
    As = B.assembly
    ppl = sc['ppl']
    if labels is None:
        meshes = []
        V, T = B.skin().mesh('masked')[:2]
        meshes.append((V, T, np.zeros(len(T), int)))
        for o in B.objects(groups=('eye', 'mouth', 'accessory', 'garment')):
            if o.has('eval'):
                V, T = o.mesh('eval')[:2]
                meshes.append((V, T, np.zeros(len(T), int)))
        for n, (ev, _) in hair.items():
            meshes.append((ev[0], ev[1], np.full(len(ev[1]), BUN_CODE.get(n, 11))))
        dv = D.design_views()
        labels = bodyqa.zbuffer_views(meshes, sc['az3'], np.array(qa3d.iris_centres(B)), As['centre'], As['L'], ppl,
                                      [v for v in views if v in dv])
    tol = qa3d.HAIR_BUN_TOL * ppl
    out, pool = {}, {'qa': [0.0, 0], 'all': [0.0, 0]}
    for v in views:
        if v not in labels:
            continue
        lab = labels[v][1]
        row = {}
        both_d = np.zeros(lab.shape, bool)
        for s, code in BUN_CODE.items():
            m = masks.get('%s__%s' % (v, s))
            if m is None or m.shape != lab.shape or m.sum() < 40:
                continue
            both_d |= m
            ours = lab == code
            o = bodymeasure.outline_f(ours, m, tol)
            row[s[-1]] = dict(iou=round(float((ours & m).sum() / max(1, (ours | m).sum())), 3), f=round(o['f'], 3),
                              p=round(o['p'], 3), r=round(o['r'], 3), px=[int(ours.sum()), int(m.sum())])
        if not row:
            continue
        ours = np.isin(lab, list(BUN_CODE.values()))
        drawn = masks.get('%s__buns' % v)
        drawn = both_d if drawn is None or drawn.shape != lab.shape else drawn
        o = bodymeasure.outline_f(ours, drawn, tol)
        npx = int(bodymeasure.outline(drawn).sum()) + int(bodymeasure.outline(ours).sum())
        row['both'] = dict(iou=round(float((ours & drawn).sum() / max(1, (ours | drawn).sum())), 3), f=round(o['f'], 3),
                           p=round(o['p'], 3), r=round(o['r'], 3))
        out[v] = row
        for k in (('qa', 'all') if masks.get('%s__buns' % v) is not None and v != 'back' else ('all',)):
            pool[k][0] += o['f'] * npx; pool[k][1] += npx
    out['pooled'] = {k: round(a / max(1, n), 3) for k, (a, n) in pool.items()}
    out['_labels'] = labels
    return out


def crown_rise(ctx, hair, views=('front', 'profile', 'back'), labels=None):
    """how far our crown stands above the drawn crown (hair round 4): per view, over the columns whose topmost drawn
    hair is the mass's (bangs, side locks, upper or lower back: not a bun, the ahoge or a flyaway), our mass's topmost
    pixel against the drawing's, in L (positive: ours higher), on the QA's grids. -> {view: {median, p90, max, share
    of columns over 0.01 L, columns}}."""
    from . import bodyqa, qa3d
    B, D, masks = ctx['B'], ctx['D'], ctx['masks']
    sc = D.sheet_context()
    ppl = sc['ppl']
    fam_k = {f: k + 1 for k, f in enumerate(qa3d.HAIR_FAMILIES)}
    mass = [fam_k[f] for f in ('bangs', 'side_locks', 'upper_back', 'lower_back')]
    if labels is None:
        labels = labels_for(ctx, hair, views)
    out = {}
    for v in views:
        if v not in labels:
            continue
        lab = labels[v][1]
        drawn = np.zeros(lab.shape, np.int16)
        for f, k in fam_k.items():
            m = masks.get('%s__%s' % (v, f))
            if m is not None and m.shape == lab.shape:
                drawn[m & (drawn == 0)] = k
        cols = np.nonzero((drawn > 0).any(0) & np.isin(lab, mass).any(0))[0]
        d = []
        for c in cols:
            r_d = int(np.argmax(drawn[:, c] > 0))
            if drawn[r_d, c] not in mass:
                continue
            r_o = int(np.argmax(np.isin(lab[:, c], mass)))
            d.append((r_d - r_o) / ppl)
        if not d:
            continue
        d = np.array(d)
        out[v] = dict(median=round(float(np.median(d)), 4), p90=round(float(np.percentile(d, 90)), 4),
                      max=round(float(d.max()), 4), over=round(float((d > 0.01).mean()), 3), columns=len(d))
    return out


def bun_picture(ctx, bv, path, scale=3, pad=12):
    """per view, each bun's crop: the drawn bun filled blue with its outline, ours orange with its outline red, the rest
    of our hair grey (bun_views' labels on the design's grids), side by side at one scale."""
    from PIL import Image, ImageDraw
    from . import bodymeasure
    tiles = []
    for v in BUN_VIEWS:
        if v not in bv:
            continue
        lab = bv['_labels'][v][1]
        drawn = np.zeros(lab.shape, bool)
        for s in BUN_CODE:
            m = ctx['masks'].get('%s__%s' % (v, s))
            if m is not None and m.shape == lab.shape:
                drawn |= m
        ours = np.isin(lab, list(BUN_CODE.values()))
        img = np.full(lab.shape + (3,), 250.0)
        img[lab == 11] = (205, 205, 205)
        img[lab == 0] = (235, 225, 215)
        img[drawn] = (170, 200, 245)
        img[ours] = (250, 190, 130)
        img[ours & drawn] = (215, 190, 190)
        img[bodymeasure.outline(drawn)] = (20, 70, 210)
        img[bodymeasure.outline(ours)] = (215, 40, 20)
        rr, cc = np.nonzero(drawn | ours)
        t = img[max(0, rr.min() - pad):rr.max() + pad, max(0, cc.min() - pad):cc.max() + pad].astype(np.uint8)
        im = Image.fromarray(t).resize((t.shape[1] * scale, t.shape[0] * scale), Image.NEAREST)
        d = ImageDraw.Draw(im)
        b = bv[v]['both']
        d.text((6, 4), '%s  IoU %.3f  outline %.3f' % (v, b['iou'], b['f']), fill=(0, 0, 0))
        tiles.append(np.asarray(im))
    H = max(t.shape[0] for t in tiles)
    pic = np.concatenate([np.pad(t, ((0, H - t.shape[0]), (0, 10), (0, 0)), constant_values=255) for t in tiles], 1)
    Image.fromarray(pic).save(path)
    return path


def run(ctx, style_over=None, opts=None):
    """a variant: the pieces rebuilt with the overrides and measured. -> (build's result, checks, face shown)."""
    from . import qa3d
    from .geom import hairpieces as hp
    C = ctx['C']
    o = dict(ctx['spec']['hair']['shape'].get('pieces_opts') or {}, **(opts or {}))
    fam, pts = ctx['samples'].get(o.get('samples', hp.OPTS['samples']), ctx['samples']['mesh'])
    R = hp.build(C, fam, ctx['masks'], dict(ctx['style'], **(style_over or {})), views=ctx['views'],
                 hull_frame=(C.align['scale'], np.asarray(C.align['translate'])), opts=o, log=lambda *a: None,
                 points=pts)
    hair = {n: ((p['V'], np.asarray(p['T'])),) * 2 for n, p in R['pieces'].items()}
    _, Cq = qa3d.hair_pieces_measure(ctx['B'], ctx['D'], hair)
    return R, Cq, face_shown(ctx, hair), hair


class _Piece:
    """a bundle hair object with a rebuilt piece's mesh and shading normals in place of its eval variant (the QA's
    drawing then shades the candidate as the build would: its toon material, its custom normals)."""

    def __init__(self, o, V, T, vn):
        self._o, self._V, self._T, self._vn = o, np.asarray(V, float), np.asarray(T, np.int64), np.asarray(vn, float)

    def __getattr__(self, k):
        return getattr(self._o, k)

    def mesh(self, variant='eval'):
        return self._V, self._T, np.zeros(len(self._T), np.int64), np.arange(len(self._T))

    def tris(self, variant='eval'):
        return self._T, np.arange(len(self._T)), self._T

    def a(self, variant, field):
        return self._vn if field == 'lnor' else self._o.a(variant, field)

    def has(self, variant):
        return True


def noise(ctx, R):
    """qa3d.hair_noise's measure (tone edges per visible hair pixel, the hair drawn without outlines behind the rest, from
    0, 90 and 180 degrees, each tone group cut at its own percentiles) for rebuilt pieces, each drawn as the build's
    object of the same name with the piece's mesh and shading normals. -> (mean, {az: value}, {piece: {az: value}})."""
    from . import qa3d
    B = ctx['B']
    objs = {o.name: o for o in qa3d._visible(B, ('hair',))}
    hair = [_Piece(objs['hair_' + n], p['V'], p['T'], p['vn_shade']) for n, p in R['pieces'].items()
            if 'hair_' + n in objs]
    fr = qa3d.figure_frame(B, ss=qa3d.FIG_SS)
    surfs, owner = [], []
    for i, o in enumerate(hair):
        for x in qa3d.surfaces(B, o, outline=False):
            surfs.append(x); owner.append(i)
    occ = [x for o in B.objects() if o.group != 'hair' and o.has('eval')
           for x in qa3d.surfaces(B, o, 'masked' if o.group == 'skin' else 'eval', outline=False)]
    group = np.array([qa3d.hair_noise_group(o) for o in hair])
    per, by = {}, {}
    for az in (0, 90, 180):
        px = qa3d.draw(B, surfs + occ, az, fr)
        items = [(s_['V'], s_['T'], np.full(len(s_['T']), owner[k] + 1 if k < len(surfs) else -1), s_['cull'])
                 for k, s_ in enumerate(surfs + occ)]
        lab = qa3d._to_shape(fr.zbuffer(items, az)[1], px.shape[:2])
        a = (px[..., 3] > 0.5) & (lab >= 1)
        grp = np.where(a, group[np.clip(lab - 1, 0, len(group) - 1)], 0)
        e, n = qa3d.tone_edges(px[..., :3] @ np.array([0.3, 0.59, 0.11]), grp)
        per[az] = round(float((e & a).sum() / max(1, n)), 4)
        for i, o in enumerate(hair):
            m = a & (lab == i + 1)
            if m.sum() > 30:
                by.setdefault(o.name[5:], {})[az] = round(float(e[m].sum() / m.sum()), 3)
    return round(float(np.mean(list(per.values()))), 4), per, by


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


# ------------------------------------------------------------------------------------ torn tips and jagged edges
# Michael's flags on look_v5 (hair round 3): small loose shards at the lock tips (neck, side locks) and stepped edges
# along the back's lower edge and the fringe in profile. Measured on the QA's z-buffered labels (the hair's geometry,
# no outlines) at the design's own scale, and the same measure on the design's own class image, so every value has
# the design's beside it. The definitions follow tool/artifacts' plan (fragments under FRAG L^2; an outline against
# itself smoothed at S1 and S2, its teeth), so its shared detectors can take over when they land.
FRAG = 0.002           # L^2: a hair component under this (not the mass, not a bun) is a fragment: a shard ...
FRAG_MIN = 0.00002     # L^2: ... and over this (a render's pixel filter blurs a smaller speck away; tool/artifacts')
S1, S2 = 0.004, 0.02   # L: an outline smoothed along its length at S1 (pixel noise gone) against S2 (the shape's own)
TOOTH = 0.003          # L: a lobe of that deviation deeper than this is a tooth (a step, a shard's corner, a drawn tip)
STEP_LEN = 0.04        # L: a tooth shorter than this along the outline is a step (a drawn tip or curl is longer). On
                       # look_v5's lower edges: the design 0.0-0.4 steps per L, ours 0.7-2.9 (hair round 3's calibration)
EDGE_VIEWS = ('front', 'three_quarter', 'profile', 'back')
THIN = ('ahoge', 'flyaways')    # pieces drawn as thin blades: a view's one stroke of each is no shard
EDGE_FAMS = ('bangs', 'side_locks', 'upper_back', 'lower_back')
HEAD_PPL = 400.0       # px per L: the head sheet's own scale (~399), and the head boards' (the flags are 2-6 px there)
HOLE = 0.08            # L^2: a hole in the hair under this is filled before its outline is traced (the clips over it)
FRAG_LIMITS = (0, 2)          # fragments beyond the design's in a view: pass within, warn within
ROUGH_LIMITS = (0.25, 0.75)   # steps per L of outline, ours less the design's: pass within, warn within


def fragments(hair, fam, ppl, frag=FRAG):
    """the hair's small disconnected components (8-connected) under frag L^2: count, pixels, and per family (the
    component's majority in fam, an int image of family codes 1.. as qa3d.HAIR_FAMILIES). -> dict(n, px, L2, by)."""
    from scipy import ndimage
    from . import qa3d
    lab, n = ndimage.label(hair, np.ones((3, 3)))
    if n == 0:
        return dict(n=0, px=0, L2=0.0, by={})
    size = np.bincount(lab.ravel())[1:]
    small = np.nonzero((size < frag * ppl * ppl) & (size >= FRAG_MIN * ppl * ppl))[0] + 1
    by = {}
    for k in small:
        f = np.bincount(fam[lab == k], minlength=len(qa3d.HAIR_FAMILIES) + 1)
        f[0] = 0
        name = qa3d.HAIR_FAMILIES[int(f.argmax()) - 1] if f.any() else 'none'
        by[name] = by.get(name, 0) + 1
    px = int(size[small - 1].sum())
    return dict(n=int(len(small)), px=px, L2=round(px / ppl ** 2, 5), by=by)


def _contours(mask):
    """a mask's closed outlines at sub-pixel precision ((n, 2) row, col), each resampled every 0.5 px."""
    from scipy.ndimage import gaussian_filter
    from skimage.measure import find_contours
    soft = gaussian_filter(np.pad(mask, 4).astype(np.float32), 0.7)
    out = []
    for c in find_contours(soft, 0.5):
        c = c - 4
        if len(c) < 12:
            continue
        cc = np.vstack([c, c[:1]]) if not np.allclose(c[0], c[-1]) else c
        s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(cc, axis=0), axis=1))]
        n = max(16, int(s[-1] / 0.5))
        t = np.arange(n) * s[-1] / n
        out.append(np.stack([np.interp(t, s, cc[:, 0]), np.interp(t, s, cc[:, 1])], 1))
    return out


def edge_points(mask, ppl, s1=S1, s2=S2):
    """the band-passed outline of a mask: every outline point (row, col) with its deviation d (L, + outward) of the
    outline smoothed at s1 from the outline smoothed at s2, the outward normal (row, col) and its lobe id (runs between
    sign changes of d, numbered across outlines). -> dict(P, d, n, lobe, step (L per point))."""
    from scipy.ndimage import gaussian_filter1d, map_coordinates
    Ps, ds, ns, lobes, base = [], [], [], [], 0
    h = 0.5
    for c in _contours(mask):
        P1 = gaussian_filter1d(c, max(1.0, s1 * ppl) / h, axis=0, mode='wrap')
        P2 = gaussian_filter1d(c, s2 * ppl / h, axis=0, mode='wrap')
        t = np.gradient(P2, axis=0)
        t /= np.linalg.norm(t, axis=1, keepdims=True) + 1e-12
        nrm = np.stack([t[:, 1], -t[:, 0]], 1)
        probe = map_coordinates(mask.astype(np.float32), (P2 + 2.0 * nrm).T, order=1, mode='constant')
        if probe.mean() > 0.5:                     # (that side is inside: flip to outward)
            nrm = -nrm
        d = np.einsum('ij,ij->i', P1 - P2, nrm) / ppl
        sgn = np.sign(d)
        sgn[sgn == 0] = 1
        ch = np.r_[0, np.cumsum(sgn[1:] != sgn[:-1])]
        if len(ch) and sgn[0] == sgn[-1]:           # (a closed outline: the last run joins the first)
            ch[ch == ch[-1]] = 0
        Ps.append(c); ds.append(d); ns.append(nrm); lobes.append(ch + base)
        base += int(ch.max()) + 1
    if not Ps:
        z = np.zeros((0, 2))
        return dict(P=z, d=np.zeros(0), n=z, lobe=np.zeros(0, int), step=h / ppl)
    return dict(P=np.concatenate(Ps), d=np.concatenate(ds), n=np.concatenate(ns), lobe=np.concatenate(lobes),
                step=h / ppl)


def edge_stats(E, sel, tooth=TOOTH, step_len=STEP_LEN):
    """the outline points in sel: their length (L), the deviation's RMS and p95 (L), the teeth (lobes whose deepest
    point is in sel and deeper than tooth) and the steps (teeth shorter than step_len along the outline: a notch, a
    stair, a shard's corner; a drawn tip or a curl is longer), each per L of that length."""
    if sel.sum() < 8:
        return None
    d = np.abs(E['d'])
    lob = E['lobe']
    ln = float(sel.sum() * E['step'])
    n = int(lob.max()) + 1
    peak = np.zeros(n)
    np.maximum.at(peak, lob, d)
    at = np.zeros(n, bool)                               # the lobe's deepest point is selected
    o = np.lexsort((-d, lob))
    lead = np.r_[True, lob[o][1:] != lob[o][:-1]]
    at[lob[o][lead]] = sel[o][lead]
    size = np.bincount(lob, minlength=n) * E['step']
    teeth = at & (peak > tooth)
    steps = teeth & (size < step_len)
    return dict(len=round(ln, 3), rms=round(float(np.sqrt((E['d'][sel] ** 2).mean())), 5),
                p95=round(float(np.percentile(d[sel], 95)), 5), teeth=int(teeth.sum()),
                per_L=round(float(teeth.sum()) / ln, 2), steps=int(steps.sum()), steps_L=round(float(steps.sum()) / ln, 2))


def step_where(E, sel, tooth=TOOTH, step_len=STEP_LEN):
    """edge_stats' steps in sel, located: per step (row, col of its deepest point, depth L, length L, family code at
    it (edge_measure's fam, 0 unknown), + out / - in)."""
    d = np.abs(E['d'])
    lob = E['lobe']
    n = int(lob.max()) + 1 if len(lob) else 0
    out = []
    if not n:
        return out
    peak = np.zeros(n)
    np.maximum.at(peak, lob, d)
    size = np.bincount(lob, minlength=n) * E['step']
    o = np.lexsort((-d, lob))
    lead = o[np.r_[True, lob[o][1:] != lob[o][:-1]]]
    fam = E.get('fam', np.zeros(len(d), int))
    for i in lead:
        k = lob[i]
        if sel[i] and peak[k] > tooth and size[k] < step_len:
            out.append((int(E['P'][i, 0]), int(E['P'][i, 1]), round(float(peak[k]), 4), round(float(size[k]), 4),
                        int(fam[i]) if len(fam) else 0, 1 if E['d'][i] > 0 else -1))
    return out


def edge_measure(hair, fam, ppl, facing=0, frag=FRAG, hole=HOLE):
    """one view's hair: fragments, and its outline (the hair against everything else, holes under `hole` L^2 filled:
    the clips over it) band-passed: all of it; its lower edge (outward normal within 60 degrees of straight down); its
    front (facing: +1 the face looks toward +columns, -1 toward -columns: the outline turned toward the face, the
    fringe's and the side locks' front); and per family (the family of the nearest hair pixel; fam 0 = unknown).
    hair: the view's hair mask; fam: family codes (1.. qa3d.HAIR_FAMILIES) over it."""
    from scipy import ndimage
    from . import qa3d
    lab, n = ndimage.label(~hair)
    if n:
        size = np.bincount(lab.ravel())
        edge = np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]])
        small = np.nonzero(size < hole * ppl * ppl)[0]
        fill = np.isin(lab, np.setdiff1d(small[small > 0], edge))
        hair = hair | fill
        if fam.any():
            idx = ndimage.distance_transform_edt(fam == 0, return_distances=False, return_indices=True)
            fam = np.where(fill, fam[idx[0], idx[1]], fam)
    out = dict(fragments=fragments(hair, fam, ppl, frag), px=int(hair.sum()))
    E = edge_points(hair, ppl)
    if not len(E['d']):
        return out
    r = np.clip(np.round(E['P'][:, 0]).astype(int), 0, hair.shape[0] - 1)
    c = np.clip(np.round(E['P'][:, 1]).astype(int), 0, hair.shape[1] - 1)
    lower = E['n'][:, 0] > 0.5
    out['all'] = edge_stats(E, np.ones(len(r), bool))
    out['lower'] = edge_stats(E, lower)
    if facing:
        out['front'] = edge_stats(E, E['n'][:, 1] * facing > 0.5)
    out['fam'] = {}
    f_at = np.zeros(len(r), int)
    if fam.any():
        idx = ndimage.distance_transform_edt(fam == 0, return_distances=False, return_indices=True)
        f_at = fam[idx[0][r, c], idx[1][r, c]]
        for f in EDGE_FAMS:
            k = qa3d.HAIR_FAMILIES.index(f) + 1
            for nm, sel in ((f, f_at == k), (f + '_lower', (f_at == k) & lower)):
                st = edge_stats(E, sel)
                if st:
                    out['fam'][nm] = st
    out['_E'] = dict(E, fam=f_at, hair=hair)
    return out


def head_design(D, ppl):
    """the design's head sheet (the spec's ref.face_sheet: head_turnaround) at ppl, per view its hair: the blob's orange,
    the drawn lines absorbed, cut to the head's box. -> {view: dict(hair, facing, eyes, box)} (memoized)."""
    fs = D.ref().get('face_sheet')
    if not fs:
        return {}
    return D.memo(_head_design, D.rgba(fs['image'])[..., :3], D.B.assembly['eye_knobs']['x'], fs.get('facing', -1), ppl)


def _head_design(rgb, ex, facing, ppl):
    from scipy import ndimage
    from . import bodyqa, refcheck
    rgb0, _ = refcheck.without_guides(np.asarray(rgb, float))
    rgb1, f, H = refcheck.at_scale(rgb0, ex, 2 * ex * ppl, facing)
    fam = bodyqa.family(rgb1)
    out = {}
    for v, h in H['heads'].items():
        x0, y0, x1, y1 = (int(b) for b in h['box'])
        fg = np.zeros(fam.shape, bool)
        fg[y0:y1, x0:x1] = h['_mask'][y0:y1, x0:x1] if h['_mask'].shape == fam.shape else True
        cls = bodyqa.absorb(np.where(fg, fam, 0), fg, drop=(bodyqa.CLASS['dark'], bodyqa.CLASS['line'],
                                                            bodyqa.CLASS['other']))
        hair = (cls == bodyqa.CLASS['orange'])[y0:y1, x0:x1]
        # the hair is the orange mass and what lies within 0.01 L of it: the irises' and the collarbones' strokes in
        # hair tones are not hair (the drawn hair has no loose pieces: its flicks join the mass)
        lab, n = ndimage.label(hair, np.ones((3, 3)))
        if n > 1:
            big = lab == 1 + int(np.argmax(np.bincount(lab.ravel())[1:]))
            near = ndimage.binary_dilation(big, iterations=max(1, int(0.01 * ppl)))
            keep = np.unique(lab[near & hair])
            hair = np.isin(lab, keep[keep > 0])
        eyes = [(float(e[0]) - x0, float(e[1]) - y0) for e in h['eyes']]
        cx = hair.any(0).nonzero()[0].mean() if hair.any() else 0
        fc = 0 if v in ('front', 'back') or not eyes else (1 if np.mean([e[0] for e in eyes]) > cx else -1)
        out[v] = dict(hair=hair, facing=fc, eyes=eyes, box=[x0, y0, x1, y1])
    fe, te = (out.get(v, {}).get('eyes') or [] for v in ('front', 'three_quarter'))
    az3 = float(np.degrees(np.arccos(np.clip(abs(te[1][0] - te[0][0]) / abs(fe[1][0] - fe[0][0]), 0, 1)))) \
        if len(fe) == 2 and len(te) == 2 else 35.0
    for v in out.values():
        v['az3'] = round(az3, 1)
    return out


def design_edges(ctx, views=EDGE_VIEWS, ppl=HEAD_PPL):
    """edge_measure on the design's own hair, at the head sheet's scale (head_design)."""
    out = {}
    for v, h in head_design(ctx['D'], ppl).items():
        if v in views:
            out[v] = edge_measure(h['hair'], np.zeros(h['hair'].shape, np.int16), ppl, h['facing'])
    return out


HEAD_WIN = dict(x=1.25, top=1.6, bottom=-1.45)     # L round the eye line: the head, its buns and the hair's ends


def head_labels(ctx, hair, views=EDGE_VIEWS, ppl=HEAD_PPL, az3=None):
    """our scene z-buffered round the head at ppl, each lock apart (a piece's connected shells: its locks, a bun's
    boxes, a blade): {view: (label image: 1 + the lock's index in the returned locks, 0 anything else, -1 nothing;
    depth; facing)}, locks [(piece, k)]. hair: {piece: ((V, T), raw)}; the rest of the scene as the QA's hair checks
    draw it. A view is a name (front, three_quarter, profile, back) or an azimuth."""
    from .geom import raster
    from .geom.mesh import components
    B = ctx['B']
    As = B.assembly
    L = float(As['L'])
    meshes = []
    V, T = B.skin().mesh('masked')[:2]
    meshes.append((V, T, np.zeros(len(T), int)))
    for o in B.objects(groups=('eye', 'mouth', 'accessory', 'garment')):
        if o.has('eval'):
            V, T = o.mesh('eval')[:2]
            meshes.append((V, T, np.zeros(len(T), int)))
    locks = []
    for n, (ev, _) in hair.items():
        V, T = np.asarray(ev[0], float), np.asarray(ev[1])
        cf, k = components(T, by='face')
        lab = np.zeros(len(T), int)
        for c in range(k):
            locks.append((n, c))
            lab[cf == c] = len(locks)
        meshes.append((V, T, lab))
    if az3 is None:                         # the head sheet's three-quarter (the design these views meet)
        hd = head_design(ctx['D'], ppl)
        az3 = next(iter(hd.values()))['az3'] if hd else ctx['D'].sheet_context().get('az3', 35.0)
    az = {'front': 0.0, 'three_quarter': az3, 'profile': 90.0, 'back': 180.0}
    from . import qa3d
    iris = np.array(qa3d.iris_centres(B))
    out = {}
    for v in views:
        a = az.get(v, v if isinstance(v, (int, float)) else None)
        if a is None:
            continue
        origin = (float(As['centre'][0]), float(np.mean(iris[:, 2])))
        depth, lab = raster.window_zbuffer(meshes, a, origin, L, 1.0 / ppl, HEAD_WIN)
        # the face looks toward the eyes' side of the hair: +columns or -columns in the picture
        P2, _ = raster.window_project(iris, a, origin, L, 1.0 / ppl, HEAD_WIN)
        hx = (lab > 0).any(0).nonzero()[0]
        fc = 0 if a in (0.0, 180.0) or not len(hx) else (1 if P2[:, 0].mean() > hx.mean() else -1)
        out[v] = (lab, depth, fc)
    return out, locks


def lock_fragments(lab, locks, ppl, frag=FRAG):
    """every visible part of a lock under frag L^2 (8-connected): a lock tip showing between the neck and the collar,
    a flyaway blade poking through a lock, a sliver of a lock between two others: in the render each is a shard ringed
    by the lock's own outline. lab: head_labels' (1 + lock index). -> dict(n, px, L2, by {piece: n})."""
    from scipy import ndimage
    n, px, by, where = 0, 0, {}, []
    lk = np.where(lab > 0, lab, 0)
    objs = ndimage.find_objects(lk)
    for k, sl in enumerate(objs):
        if sl is None:
            continue
        sl = tuple(slice(max(0, a.start - 1), a.stop + 1) for a in sl)
        m = lk[sl] == k + 1
        cl, nc = ndimage.label(m, np.ones((3, 3)))
        size = np.bincount(cl.ravel())[1:]
        keep = (size < frag * ppl * ppl) & (size >= FRAG_MIN * ppl * ppl)
        if locks[k][0] in THIN and len(size):
            keep[size.argmax()] = False          # (a blade's own stroke is thin by design: only its pieces count)
        small = size[keep]
        if len(small):
            name = locks[k][0]
            by[name] = by.get(name, 0) + len(small)
            n += len(small); px += int(small.sum())
            for i in np.nonzero(keep)[0]:
                r_, c_ = np.nonzero(cl == i + 1)
                where.append([round(float(r_.mean()) + sl[0].start, 1), round(float(c_.mean()) + sl[1].start, 1),
                              int(size[i]), name, int(locks[k][1])])
    return dict(n=n, px=px, L2=round(px / ppl ** 2, 5), by=by, where=where)


ENCLOSED = 0.8         # an island: a lock's visible part whose rim is this share one other lock
POKE_GAP = 0.004       # L: at a poke the two surfaces meet (they intersect) along its rim: the depth step is under this


def lock_islands(lab, depth, locks, ppl, L, frag=FRAG):
    """every visible part of a lock (the shards under frag are lock_fragments'; a blade's any size) that another lock
    encloses (its rim at least ENCLOSED that lock): in the render a blob of one lock inside another, ringed by its
    outline. A drawn head of hair has none: a lock that shows inside another pokes through it. Classed by the depth step
    along its rim: 'poke' (under POKE_GAP L: the surfaces intersect there) or 'over' (it lies in front). A blade (ahoge,
    flyaway) lying over a lock is a 'flick' (the design's profile draws one flick over the side lock), counted apart.
    -> dict(n (pokes and non-blade overs), pokes, over, flicks, px, by {piece>other: n}, where [(row, col, px, name,
    kind, depth step L)])."""
    from scipy import ndimage
    lk = np.where(lab > 0, lab, 0)
    dz = np.where(np.isfinite(depth), depth, np.nan) / L
    cnt_ = dict(poke=0, over=0, flick=0)
    px = 0
    by, where = {}, []
    for k, sl in enumerate(ndimage.find_objects(lk)):
        if sl is None:
            continue
        thin = locks[k][0] in THIN
        sl = tuple(slice(max(0, a.start - 2), a.stop + 2) for a in sl)
        m = lk[sl] == k + 1
        cl, nc = ndimage.label(m, np.ones((3, 3)))
        size = np.bincount(cl.ravel())[1:]
        for i in range(nc):
            if size[i] < max(FRAG_MIN * ppl * ppl, 1) or (size[i] < frag * ppl * ppl and not thin):
                continue                          # (a shard: counted by lock_fragments)
            c = cl == i + 1
            ring = ndimage.binary_dilation(c, np.ones((3, 3))) & ~c
            rl = lab[sl][ring]
            if not len(rl):
                continue
            vals, cnt = np.unique(rl, return_counts=True)
            j = vals[np.argmax(cnt)]
            if j <= 0 or j == k + 1 or cnt.max() < ENCLOSED * len(rl):
                continue
            # the depth step across its rim: the rim's depth less its island neighbours' (+: the island is nearer)
            din = ndimage.grey_erosion(np.where(c, dz[sl], np.inf), size=(3, 3))
            gap = (dz[sl] - din)[ring & (lab[sl] == j) & np.isfinite(din)]
            g = float(np.nanmedian(gap)) if len(gap) else 0.0
            kind = 'poke' if abs(g) < POKE_GAP else 'flick' if thin else 'over'
            cnt_[kind] += 1
            name = '%s>%s' % (locks[k][0], locks[j - 1][0])
            if kind != 'flick':
                px += int(size[i])
                by[name] = by.get(name, 0) + 1
            r_, c_ = np.nonzero(c)
            where.append([round(float(r_.mean()) + sl[0].start, 1), round(float(c_.mean()) + sl[1].start, 1),
                          int(size[i]), name, kind, round(g, 4)])
    return dict(n=cnt_['poke'] + cnt_['over'], pokes=cnt_['poke'], over=cnt_['over'], flicks=cnt_['flick'], px=px,
                L2=round(px / ppl ** 2, 5), by=by, where=where)


def line_points(lab, depth, ppl, s1=S1, s2=S2):
    """the render's hair lines: every lock's visible outline where that lock is the nearer side (its outline hull
    draws the line there: against the background, the skin, or a lock behind it), band-passed as edge_points.
    -> edge_points' dict for all of them together, with 'lock' per point."""
    from scipy import ndimage
    from scipy.ndimage import map_coordinates
    parts = []
    lk = np.where(lab > 0, lab, 0)
    dfar = np.where(np.isfinite(depth), depth, 1e9)
    base = 0
    for k, sl in enumerate(ndimage.find_objects(lk)):
        if sl is None:
            continue
        sl = tuple(slice(max(0, a.start - 6), a.stop + 6) for a in sl)
        m = lk[sl] == k + 1
        if m.sum() < 30:
            continue
        E = edge_points(m, ppl, s1, s2)
        if not len(E['d']):
            continue
        # outside each outline point (2 px along its normal): a lock behind, or nothing: the line is this lock's
        P = E['P']
        o = P + 2.0 * E['n']
        d_in = map_coordinates(np.where(m, dfar[sl], np.nan), (P - 1.0 * E['n']).T, order=0, mode='nearest')
        d_out = map_coordinates(dfar[sl], o.T, order=0, mode='nearest')
        l_out = map_coordinates(lab[sl].astype(float), o.T, order=0, mode='nearest')
        front = (l_out < 1) | ~(d_out < d_in)
        E['sel'] = front
        E['lock'] = np.full(len(P), k)
        E['lobe'] = E['lobe'] + base
        base = int(E['lobe'].max()) + 1
        E['P'] = P + np.array([sl[0].start, sl[1].start])
        parts.append(E)
    if not parts:
        return None
    return dict(P=np.concatenate([e['P'] for e in parts]), d=np.concatenate([e['d'] for e in parts]),
                n=np.concatenate([e['n'] for e in parts]), lobe=np.concatenate([e['lobe'] for e in parts]),
                lock=np.concatenate([e['lock'] for e in parts]), sel=np.concatenate([e['sel'] for e in parts]),
                step=parts[0]['step'])


def our_edges(ctx, hair, views=EDGE_VIEWS, ppl=HEAD_PPL):
    """edge_measure on our hair ({piece: ((V, T), raw)}) at the head sheet's scale, with the locks' shards and the
    render's lines inside the hair (line_points)."""
    from . import qa3d
    labs, locks = head_labels(ctx, hair, views, ppl)
    globals()['_last_locks'] = locks                  # (the lab's pictures name each label)
    code = np.array([0] + [qa3d.HAIR_FAMILIES.index(qa3d.HAIR_PIECE_FAMILY[n]) + 1 for n, _ in locks], np.int16)
    out = {}
    for v, (lab, depth, fc) in labs.items():
        fam = code[np.clip(lab, 0, None)]
        out[v] = edge_measure(fam > 0, fam, ppl, fc)
        out[v]['shards'] = lock_fragments(lab, locks, ppl)
        out[v]['islands'] = lock_islands(lab, depth, locks, ppl, float(ctx['B'].assembly['L']))
        E = line_points(lab, depth, ppl)
        if E is not None:
            out[v]['lines'] = edge_stats(E, E['sel'])
            out[v]['lines_lower'] = edge_stats(E, E['sel'] & (E['n'][:, 0] > 0.5))
            out[v]['_L'] = E
        out[v]['_lab'] = lab
        out[v]['facing'] = fc
    return out


def edge_checks(ours, design):
    """the round's checks, ours against the design's own values: hair_fragments_<view> (small components beyond the
    design's), hair_rough_<view> (teeth per L of the whole hair outline), hair_rough_back_lower (the back view's lower
    edge), hair_rough_profile_front (the outline facing the face in profile: the fringe and side locks), each graded
    as a ratio to the design's."""
    C = {}
    for v in EDGE_VIEWS:
        if v not in ours or v not in design:
            continue
        fo, fd = ours[v]['fragments'], design[v]['fragments']
        sh = ours[v].get('shards') or dict(n=0, px=0, by={})
        extra = fo['n'] + sh['n'] - fd['n']
        C['hair_fragments_' + v] = dict(value=fo['n'] + sh['n'], loose=fo['n'], shards=sh['n'], px=fo['px'] + sh['px'],
                                        by=dict(sh['by'], **{'loose_' + k: x for k, x in fo['by'].items()}),
                                        design=fd['n'], status=(
            'PASS' if extra <= FRAG_LIMITS[0] else 'WARN' if extra <= FRAG_LIMITS[1] else 'FAIL'))
        isl = ours[v].get('islands')
        if isl is not None:                 # a lock showing inside another (the design: none)
            C['hair_islands_' + v] = dict(value=isl['n'], pokes=isl['pokes'], over=isl['over'], flicks=isl['flicks'],
                                          px=isl['px'], by=isl['by'], design=0,
                                          status='PASS' if isl['n'] <= FRAG_LIMITS[0] else
                                          'WARN' if isl['n'] <= FRAG_LIMITS[1] else 'FAIL')
    picks = [('hair_rough_%s' % v, v, ('all',)) for v in EDGE_VIEWS] + [
        ('hair_rough_back_lower', 'back', ('lower',)), ('hair_rough_profile_front', 'profile', ('front',)),
        ('hair_rough_profile_lower', 'profile', ('lower',)), ('hair_rough_three_quarter_lower', 'three_quarter', ('lower',))]
    for key, v, path in picks:
        if v not in ours or v not in design:
            continue
        o, d = ours[v], design[v]
        for p in path:
            o, d = (o or {}).get(p), (d or {}).get(p)
        if not o or not d:
            continue
        ex = o['steps_L'] - d['steps_L']
        C[key] = dict(value=o['steps_L'], steps=o['steps'], teeth_L=o['per_L'], rms=o['rms'], design=d['steps_L'],
                      design_teeth_L=d['per_L'], design_rms=d['rms'], len=o['len'],
                      status='PASS' if ex <= ROUGH_LIMITS[0] else 'WARN' if ex <= ROUGH_LIMITS[1] else 'FAIL')
    for v in EDGE_VIEWS:                    # the render's lines inside the hair (no design counterpart: INFO)
        o = (ours.get(v) or {}).get('lines')
        if o:
            C['hair_lines_' + v] = dict(value=o['steps_L'], steps=o['steps'], teeth_L=o['per_L'], rms=o['rms'],
                                        len=o['len'], status='INFO')
    return C


def edge_picture(ctx, ours, design, path, frag=FRAG, ppl=HEAD_PPL):
    """per view, the design's hair beside ours at the same scale: the design's hair orange; ours each lock its own
    tone (the rest of the scene dark), every lock shard (lock_fragments) ringed red, the outline's steps (lobes deeper
    than TOOTH and shorter than STEP_LEN) dotted blue; cropped to the hair."""
    from PIL import Image, ImageDraw
    from scipy import ndimage
    rng = np.random.default_rng(3)
    tiles = []
    for v in EDGE_VIEWS:
        if v not in ours or v not in design:
            continue
        pair = []
        dh = design[v].get('_E', {}).get('hair')
        if dh is not None:
            img = np.where(dh[..., None], np.array([226, 122, 70]), np.array([246, 246, 244])).astype(np.uint8)
            pair.append((img, design[v]['_E']))
        lab = ours[v].get('_lab')
        if lab is not None:
            n = int(lab.max()) + 1
            pal = (rng.uniform(0.35, 0.95, (n, 3)) * np.array([255, 190, 150])).astype(np.uint8)
            img = np.where((lab > 0)[..., None], pal[np.clip(lab, 0, None)], np.where((lab == 0)[..., None],
                           np.array([70, 70, 74], np.uint8), np.array([246, 246, 244], np.uint8))).astype(np.uint8)
            pair.append((img, ours[v]['_E']))
        pics = []
        rows = cols = None
        for img, E in pair:
            h = E['hair']
            rr, cc = np.nonzero(h.any(1))[0], np.nonzero(h.any(0))[0]
            im = Image.fromarray(img)
            dr = ImageDraw.Draw(im)
            lob = E['lobe']
            deep = np.zeros(int(lob.max()) + 1)
            np.maximum.at(deep, lob, np.abs(E['d']))
            size = np.bincount(lob) * E['step']
            step = (deep > TOOTH) & (size < STEP_LEN)
            for (r, c), k in zip(E['P'], lob):
                if step[k]:
                    dr.ellipse((c - 1.5, r - 1.5, c + 1.5, r + 1.5), fill=(0, 90, 230))
            pics.append((im, (rr.min(), rr.max(), cc.min(), cc.max())))
        if lab is not None:
            dr = ImageDraw.Draw(pics[-1][0])
            E = ours[v].get('_L')
            if E is not None:                       # the lines inside the hair: where drawn black, their steps green
                lob = E['lobe']
                deep = np.zeros(int(lob.max()) + 1)
                np.maximum.at(deep, lob, np.abs(E['d']))
                size = np.bincount(lob) * E['step']
                step = (deep > TOOTH) & (size < STEP_LEN)
                for (r, c), k, f in zip(E['P'], lob, E['sel']):
                    if f:
                        dr.point((c, r), fill=(20, 20, 20))
                for (r, c), k, f in zip(E['P'], lob, E['sel']):
                    if f and step[k]:
                        dr.ellipse((c - 1.5, r - 1.5, c + 1.5, r + 1.5), fill=(0, 170, 60))
            for y, x, size, *_ in ours[v]['shards']['where']:
                rad = 6 + np.sqrt(size)
                dr.ellipse((x - rad, y - rad, x + rad, y + rad), outline=(230, 0, 0), width=2)
            for y, x, size, _, kind, _ in (ours[v].get('islands') or {}).get('where', []):
                if kind != 'flick':              # a lock showing inside another: magenta
                    rad = 4 + np.sqrt(size) / 1.5
                    dr.ellipse((x - rad, y - rad, x + rad, y + rad), outline=(220, 0, 220), width=2)
        out = []
        for im, (r0, r1, c0, c1) in pics:
            a = np.asarray(im)[max(0, r0 - 20):r1 + 20, max(0, c0 - 20):c1 + 20]
            out.append(a)
        H = max(a.shape[0] for a in out)
        tiles.append(np.concatenate([np.pad(a, ((0, H - a.shape[0]), (0, 8), (0, 0)), constant_values=255)
                                     for a in out], 1))
    if not tiles:
        return None
    H = max(t.shape[0] for t in tiles)
    out = np.concatenate([np.pad(t, ((0, H - t.shape[0]), (0, 24), (0, 0)), constant_values=255) for t in tiles], 1)
    Image.fromarray(out.astype(np.uint8)).save(path)
    return path


def _strip_E(M):
    return {v: {k: x for k, x in m.items() if not k.startswith('_')} for v, m in M.items()}


def built_hair(ctx):
    """a build's hair pieces as built (the bundle's hair objects) -> {piece: ((V, T) eval, (V, T) raw)}."""
    from . import qa3d
    objs = {o.name[5:]: o for o in qa3d._visible(ctx['B'], ('hair',)) if o.name.startswith('hair_') and
            o.name[5:] in qa3d.HAIR_PIECE_FAMILY}
    return {n: (o.mesh('eval')[:2], o.mesh('raw' if o.has('raw') else 'eval')[:2]) for n, o in objs.items()}


def light_context(build):
    """what the as-built measures need (no hull, no rebuild): the bundle, its design and the hair layers."""
    from . import bundle as bl, qa3d
    B = bl.load(os.path.join(build, 'bundle'))
    D = qa3d.Design(B)
    return dict(B=B, D=D, masks=qa3d.hair_layers_masks(B, D) or {})


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


def report_edges(ctx, hair, args, tag=''):
    """--edges: the fragments and edge checks against the design's, printed; --edges-json/--edges-png written."""
    ours, design = our_edges(ctx, hair), design_edges(ctx)
    C = edge_checks(ours, design)
    for k, c in C.items():
        extra = ('px %s %s' % (c['px'], c['by'])) if 'px' in c else ('teeth/L %s rms %s%s' % (
            c['teeth_L'], c['rms'], (' design teeth/L %s rms %s' % (c['design_teeth_L'], c['design_rms']))
            if 'design_rms' in c else ''))
        print('%-32s %-6s design %-6s %s %s' % (k, c['value'], c.get('design', '-'), c['status'], extra))
    if '--edges-json' in args:
        p = os.path.abspath(args[args.index('--edges-json') + 1])
        json.dump(dict(checks=C, ours=_strip_E(ours), design=_strip_E(design)), open(p, 'w'), indent=1)
        print('edges json', p)
    if '--edges-png' in args:
        print('edges png', edge_picture(ctx, ours, design, os.path.abspath(args[args.index('--edges-png') + 1])))
    return C


def report_buns(ctx, hair, args):
    """--buns: bun_views printed per view (each bun and both: IoU, outline); --buns-png P its picture."""
    bv = bun_views(ctx, hair)
    for v in BUN_VIEWS:
        if v in bv:
            print('bun %-14s %s' % (v, '  '.join('%s IoU %.3f outline %.3f' % (s, r['iou'], r['f'])
                                                   for s, r in bv[v].items())))
    print('bun outline pooled       %s' % bv['pooled'])
    if '--buns-png' in args:
        print('buns png', bun_picture(ctx, bv, os.path.abspath(args[args.index('--buns-png') + 1])))
    return bv


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return 0
    build = os.path.abspath(args[0])
    t = time.time()
    if '--built' in args:                   # the build's own hair as built, no rebuild (any build, no hull needed)
        ctx = light_context(build)
        hair = built_hair(ctx)
        if '--buns' in args:
            report_buns(ctx, hair, args)
        if '--edges' in args or '--edges-json' in args or '--edges-png' in args:
            report_edges(ctx, hair, args)
        print('(%.0f s)' % (time.time() - t))
        return 0
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
    if '--noise' in args:
        v, per, by = noise(ctx, R)
        print('%-24s %s %s %s' % ('hair_noise', v, per, by))
    if '--labels' in args:
        print('labels', label_image(ctx, hair, os.path.abspath(args[args.index('--labels') + 1])))
    if '--buns' in args:
        report_buns(ctx, hair, args)
    if '--edges' in args or '--edges-json' in args or '--edges-png' in args:
        report_edges(ctx, hair, args)
    print('(%.0f s)' % (time.time() - t))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
