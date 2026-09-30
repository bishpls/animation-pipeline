"""Calibration adapters for the QA parts that read our pieces as label images on the design's grids (the body sheet's
scale): collar_flags (charkit.collarqa), sheet_pieces (piece_*: charkit.qa3d) and hair_pieces (hair_piece_*). Ours is
what our z-buffer draws (pieceqa.our_labels / fine_labels, qa3d.bodyqa_zbuffer, bodyqa.zbuffer_views); here the
design's own drawn masks (the outfit's piece masks, the hair layers) are drawn into that same label image in its place,
moved or perturbed, and the part's own measuring code runs unchanged on them (patched in for the run, nothing else).

Generators (the floor and the probes; seeded):
  voronoi_pieces   the garments' drawn area cut into random cells (3 per piece a view shows), each a random piece
                   (weighted by the pieces' drawn areas): the silhouette kept, the pieces' shapes gone
  affine_pieces    each drawn piece moved 0.03-0.06 L and scaled 0.9-1.1 about its middle at random (a sloppy fit)
  cap_up           (probe) the sleeves' top 35% (the puffs' caps) raised 0.04 L: the flag "the puff caps rose above
                   the shoulder line"
  voronoi_families the hair's drawn area cut into random cells (8 per family a view shows), each a random family
"""
import contextlib

import numpy as np

CALIBRATION = [
    # Michael's flags on the shoulders, the collar and the bow (charkit/collarqa.py; tool/bow, 2026-09-30). g3_render3:
    # pipeline-3d 3ebc3fb's build (the gate's baseline for tool/bow: its old-geometry cells are these values)
    dict(check='shoulder_back_line', part='collar_flags', adapter='Garments', known_bad='g3_render3',
         baseline=['voronoi_pieces', 'affine_pieces'], shape=['piece_top', 'piece_collar', 'piece_sleeve_L',
                                                              'piece_sleeve_R'], better='lower'),
    dict(check='shoulder_back_slope', part='collar_flags', adapter='Garments', known_bad=None,
         no_known_bad="a guard: the flagged build reads 0.08 PASS (its dip and the puffs' rise cancel)",
         baseline=['voronoi_pieces', 'affine_pieces'], shape=['piece_top', 'piece_collar'], better='lower'),
    dict(check='collar_back_iou', part='collar_flags', adapter='Garments', known_bad='g3_render3',
         baseline=['voronoi_pieces', 'affine_pieces'], shape=['piece_collar'], better='higher'),
    # (the rest are detectors of one flagged defect: a squareness, a trough, a straight end, a bleed, a width; a random
    # stand-in lacks the defect and may pass; the piece's shape is the anti-gaming guard's)
    dict(check='collar_back_*', part='collar_flags', adapter='Garments', known_bad='g3_render3', kind='defect',
         baseline=['voronoi_pieces', 'affine_pieces'], shape=['piece_collar'], better='lower'),
    dict(check='bow_front_loop_width', part='collar_flags', adapter='Garments', known_bad=None, kind='defect',
         no_known_bad='a guard: the bow is sized to the drawn span, so the flagged build reads 0',
         baseline=['voronoi_pieces', 'affine_pieces'], shape=['piece_bow'], better='lower'),
    dict(check='bow_*', part='collar_flags', adapter='Garments', known_bad='g3_render3', kind='defect',
         baseline=['voronoi_pieces', 'affine_pieces'], shape=['piece_bow'], better='lower'),
    # the sleeves' shape (qa3d.sheet_pieces): passed while the puffs' caps rose above the shoulder line (co_render:
    # tool/collar 5ffd446, the puffs' tops ~0.05 L up)
    dict(check='piece_sleeve_[LR]', part='sheet_pieces', adapter='Pieces', known_bad='co_render',
         baseline=['voronoi_pieces', 'affine_pieces'], probes=['cap_up'], shape=[], better='higher'),
    # the guard's own shapes: how much a piece's per-view shape moves with the design moved 1-2 px (the guard's DROP
    # must stand above it)
    dict(check='piece_bow', part='sheet_pieces', adapter='Pieces', known_bad=None,
         no_known_bad="a shape check, the anti-gaming guard's measure: no single flagged build",
         baseline=['voronoi_pieces', 'affine_pieces'], shape=[], better='higher'),
    dict(check='piece_collar', part='sheet_pieces', adapter='Pieces', known_bad=None,
         no_known_bad="a shape check, the anti-gaming guard's measure: no single flagged build",
         baseline=['voronoi_pieces', 'affine_pieces'], shape=[], better='higher'),
    # the bangs as a family (qa3d.hair_pieces): read 0.79 PASS while our bang locks scored at a random split's level
    # against the lock truth (tool/hairlocks: 0.439 against 0.441). hl_base: pipeline-3d 2f42155 (that measurement's)
    dict(check='hair_piece_bangs', part='hair_pieces', adapter='Hair', known_bad='hl_base',
         baseline=['voronoi_families'], shape=[], better='higher'),
]


def _shift(a, dy, dx, fill):
    """an image moved dy rows down and dx columns right, filled where it moved from."""
    out = np.full_like(a, fill)
    H, W = a.shape[:2]
    ys, yd = (slice(0, H - dy), slice(dy, H)) if dy >= 0 else (slice(-dy, H), slice(0, H + dy))
    xs, xd = (slice(0, W - dx), slice(dx, W)) if dx >= 0 else (slice(-dx, W), slice(0, W + dx))
    out[yd, xd] = a[ys, xs]
    return out


def voronoi(region, labels, weights, cells, rng):
    """region's pixels cut into `cells` random cells (nearest of random seeds in it), each given one of labels at random
    (weights: their chances) -> (H, W) label image (-1 outside region)."""
    from scipy.spatial import cKDTree
    out = np.full(region.shape, -1, np.int32)
    ys, xs = np.nonzero(region)
    if not len(ys) or not len(labels):
        return out
    k = min(cells, len(ys))
    pick = rng.choice(len(ys), k, replace=False)
    _, j = cKDTree(np.c_[ys[pick], xs[pick]]).query(np.c_[ys, xs])
    w = np.asarray(weights, float)
    lab = rng.choice(np.asarray(labels), k, p=w / w.sum())
    out[ys, xs] = lab[j]
    return out


def affine(mask, rng, ppl, shift=(0.03, 0.06), scale=(0.9, 1.1)):
    """a mask moved by a random shift (each axis shift[0]..shift[1] L, random sign) and scaled about its middle."""
    from scipy import ndimage
    ys, xs = np.nonzero(mask)
    if not len(ys):
        return mask
    c = np.array([ys.mean(), xs.mean()])
    s = rng.uniform(*scale)
    t = rng.uniform(*shift, size=2) * ppl * rng.choice([-1, 1], size=2)
    # output pixel p reads input (p - c - t) / s + c
    return ndimage.affine_transform(mask.astype(np.uint8), np.eye(2) / s, offset=c - (c + t) / s, order=0,
                                    mode='constant', cval=0).astype(bool)


@contextlib.contextmanager
def patched(pairs):
    """module attributes replaced for the block: [(module, name, value)]."""
    old = [(m, n, getattr(m, n)) for m, n, _ in pairs]
    try:
        for m, n, v in pairs:
            setattr(m, n, v)
        yield
    finally:
        for m, n, v in old:
            setattr(m, n, v)


class Garments:
    """collar_flags: the outfit's drawn piece masks as our objects' labels (skin and hair from the drawing's classes)."""
    part = 'collar_flags'
    generators = {
        'voronoi_pieces': "the garments' drawn area cut into random cells (3 per piece a view shows), each a random piece",
        'affine_pieces': 'each drawn piece moved 0.03-0.06 L and scaled 0.9-1.1 about its middle at random',
        'cap_up': "the sleeves' top 35% (the puffs' caps) raised 0.04 L",
    }

    def __init__(self, B, design):
        from .. import bodymeasure, bodyqa, qa3d
        self.B, self.design = B, design
        ctx = design.sheet_context()
        self.ppl, self.az3 = ctx['ppl'], ctx['az3']
        self.az = bodyqa.azimuths(self.az3)
        masks, graph, _ = bodymeasure.piece_masks(B.spec)
        pm = bodymeasure.piece_map(graph, B.spec)
        up = bodymeasure.built_parent(graph, pm)
        _, names = qa3d.scene_objects(B)
        self.names = list(names)
        idx = {n: i for i, n in enumerate(self.names)}
        self.dv = design.design_views()
        CL = bodyqa.CLASS
        skin = [o.name for o in B.objects(groups=('skin',)) if o.name in idx]
        hair = [n for n in self.names if n.startswith('hair')]
        over = {p['id']: (p.get('layer') or {}).get('over') or [] for p in graph['pieces']}
        depth = {}

        def dep(p, seen=()):
            if p not in depth:
                depth[p] = 1 + max([dep(q, seen + (p,)) for q in over.get(p, ()) if q not in seen] or [0])
            return depth[p]
        order = sorted(over, key=dep)
        self.lab, self.cls, self.pieces, self.garment = {}, {}, {}, {}
        for v, d in self.dv.items():
            cls = d['cls']
            lab = np.full(cls.shape, -1, np.int32)
            if skin:
                lab[d['fg'] & (cls == CL['skin'])] = idx[skin[0]]
            if hair:
                lab[d['fg'] & (cls == CL['hair'])] = idx[hair[0]]
            garment = np.zeros(cls.shape, bool)
            px = {}
            for pid in order:
                m = masks.get('%s__%s' % (v, pid))
                members = pm.get(pid) or pm.get(up.get(pid)) or []
                if m is None or not m.any() or not members or members[0][0] not in idx:
                    continue
                name, sgn = members[0]
                code = idx[name] + (1000 if sgn is not None and sgn < 0 else 0)
                m = m[:cls.shape[0], :cls.shape[1]]
                lab[m] = code
                garment |= m
                px[code] = px.get(code, 0) + int(m.sum())
            # our surfaces meet with no ink between them: the drawing's lines (and the masks' rough edges) inside the
            # figure go to the nearest labelled pixel, as the QA's classes absorb them (a gap along a drawn line read as
            # a 0.12 L trough in the shoulder line)
            from scipy import ndimage
            gap = d['fg'] & (lab < 0)
            if gap.any() and (lab >= 0).any():
                _, (iy, ix) = ndimage.distance_transform_edt(lab < 0, return_indices=True)
                lab[gap] = lab[iy[gap], ix[gap]]
                garment = np.isin(lab, list(px)) if px else garment
            self.lab[v], self.cls[v], self.pieces[v], self.garment[v] = lab, cls, px, garment

    # -------------------------------------------------------------------------------------------- the stand-ins for ours
    def labels(self, kind, arg):
        """{view: label image}: the design moved (kind 'design', arg (dy, dx)) or a generator's (arg its seed)."""
        if kind == 'design':
            return {v: _shift(L, arg[0], arg[1], -1) for v, L in self.lab.items()}
        rng = np.random.default_rng(1000 + int(arg))
        out = {}
        for v, L in self.lab.items():
            px, g = self.pieces[v], self.garment[v]
            L2 = L.copy()
            if kind == 'voronoi_pieces':
                V = voronoi(g, list(px), list(px.values()), 3 * max(1, len(px)), rng)
                L2[g] = V[g]
            elif kind == 'affine_pieces':
                L2[g] = np.where(self.cls[v][g] == 0, -1, L2[g])
                base = L2.copy()
                base[g] = -1
                for code in px:                                  # (the design's paint order: px keeps it)
                    base[affine(L == code, rng, self.ppl)] = code
                L2 = base
            elif kind == 'cap_up':
                up = int(round(0.04 * self.ppl))
                for code in px:
                    n = self.names[code % 1000] if code % 1000 < len(self.names) else ''
                    if not (n.startswith('sleeve_') and 'cuff' not in n):
                        continue
                    m = L == code
                    rs = np.nonzero(m.any(1))[0]
                    if not len(rs):
                        continue
                    cut = rs[0] + int(0.35 * (rs[-1] - rs[0]))
                    cap = m.copy()
                    cap[cut:] = False
                    L2[_shift(cap, -up, 0, False)] = code
            else:
                raise KeyError(kind)
            out[v] = L2
        return out

    def patches(self, L, kind='design'):
        from .. import collarqa, pieceqa, qa3d
        from ..geom.raster import window_shape
        names, az = self.names, self.az

        def our_labels(B, ppl, az3, views=('front', 'three_quarter', 'profile', 'back')):
            return {v: dict(lab=L[v], depth=np.zeros(L[v].shape, np.float32), az=az[v], org=(0.0, 0.0))
                    for v in views if v in L}, names

        def fine_labels(B, ppl, az3, views=('front', 'three_quarter', 'profile', 'back'), fine=pieceqa.FINE,
                        win=pieceqa.CHEST):
            W, H = window_shape(1.0 / (ppl * fine), win)
            out = {}
            for v in views:
                if v not in L:
                    continue
                c = np.repeat(np.repeat(pieceqa.crop_win(L[v], ppl, win), fine, 0), fine, 1)
                f = np.full((H, W), -1, np.int32)
                h, w = min(H, c.shape[0]), min(W, c.shape[1])
                f[:h, :w] = c[:h, :w]
                out[v] = f
            return out, names

        def our_classes(B, ppl, az3, views=('front', 'three_quarter', 'profile', 'back')):
            return {v: self.cls[v] for v in views if v in self.cls}

        by_az = {round(float(a), 3): v for v, a in az.items()}
        fake = [(np.zeros((3, 3)), np.array([[0, 1, 2]]), np.zeros(1, int)) for _ in names]

        def bodyqa_zbuffer(meshes, a, org, Lh, ppl):
            return L[by_az[round(float(a), 3)]]

        def bleed(B, design, dvf, bow_d, ppl):
            return self.bleed(dvf, bow_d, ppl, L, kind)
        return [(pieceqa, 'our_labels', our_labels), (pieceqa, 'fine_labels', fine_labels),
                (pieceqa, 'our_classes', our_classes), (qa3d, 'scene_objects', lambda B: (fake, names)),
                (qa3d, 'bodyqa_zbuffer', bodyqa_zbuffer), (collarqa, 'bleed', bleed)]

    def bleed(self, dvf, bow_d, ppl, L, kind):
        """collarqa.bleed with a stand-in for ours: the drawn bow's cream touching orange (the design's own reading),
        where the stand-in puts the bow: the design moved keeps its drawn lines between the bow and the jacket (its cream
        on orange); a generator's stand-in has no line between its pieces (its bow touching its jacket directly)."""
        from .. import bodyqa as bq, collarqa
        raw = dvf.get('raw')
        if raw is None:
            return None
        CL = bq.CLASS
        h, w = min(raw.shape[0], bow_d.shape[0]), min(raw.shape[1], bow_d.shape[1])
        cream = raw[:h, :w] == CL['cream']
        orange = raw[:h, :w] == CL['orange']
        d_len = float(collarqa.edge_touch(cream & bow_d[:h, :w], orange).sum()) / ppl
        idx = {n: i for i, n in enumerate(self.names)}
        lab = L['front'][:h, :w]
        ob = lab == idx.get('bow', -9)
        if kind == 'design':
            o_len = float(collarqa.edge_touch(cream & ob, orange).sum()) / ppl
        else:
            jk = np.isin(lab % 1000, [idx[n] for n in collarqa.JACKET if n in idx]) & (lab >= 0)
            o_len = float(collarqa.edge_touch(ob, jk).sum()) / ppl
        return dict(ours=round(o_len, 4), design=round(d_len, 4))

    @contextlib.contextmanager
    def substitute(self, kind, arg):
        with patched(self.patches(self.labels(kind, arg), kind)):
            yield


class Pieces(Garments):
    """sheet_pieces (piece_*): the same stand-ins through qa3d's z-buffer."""
    part = 'sheet_pieces'


class Hair:
    """hair_pieces (hair_piece_*): the hair layers' drawn families as our hair's family labels (bodyqa.zbuffer_views'),
    the rest of the drawn figure as other surfaces."""
    part = 'hair_pieces'
    generators = {'voronoi_families': "the hair's drawn area cut into random cells (8 per family a view shows), each a "
                                      "random family (weighted by the families' drawn areas)"}

    def __init__(self, B, design):
        from .. import qa3d
        self.B, self.design = B, design
        masks = qa3d.hair_layers_masks(B, design)
        dv = design.design_views()
        fam = {f: k + 1 for k, f in enumerate(qa3d.HAIR_FAMILIES)}
        self.lab, self.px = {}, {}
        for v, d in dv.items():
            lab = np.full(d['cls'].shape, -1, np.int32)
            lab[d['fg']] = 0
            px = {}
            for f, k in fam.items():
                m = (masks or {}).get('%s__%s' % (v, f))
                if m is not None and m.shape == lab.shape and m.any():
                    lab[m] = k
                    px[k] = int(m.sum())
            self.lab[v], self.px[v] = lab, px

    def labels(self, kind, arg):
        if kind == 'design':
            return {v: _shift(L, arg[0], arg[1], -1) for v, L in self.lab.items()}
        if kind != 'voronoi_families':
            raise KeyError(kind)
        rng = np.random.default_rng(2000 + int(arg))
        out = {}
        for v, L in self.lab.items():
            px = self.px[v]
            hair = L > 0
            L2 = L.copy()
            V = voronoi(hair, list(px), list(px.values()), 8 * max(1, len(px)), rng)
            L2[hair] = V[hair]
            out[v] = L2
        return out

    @contextlib.contextmanager
    def substitute(self, kind, arg):
        from .. import bodyqa
        L = self.labels(kind, arg)

        def zbuffer_views(meshes, az3, iris, centre, Lh, ppl, views=bodyqa.AZ):
            return {v: (np.zeros(L[v].shape, np.float32), L[v]) for v in views if v in L}
        with patched([(bodyqa, 'zbuffer_views', zbuffer_views)]):
            yield
