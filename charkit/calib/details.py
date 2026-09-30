"""Calibration adapter for the garment pieces' details (charkit.pieceqa's piece_details: the sleeves' spikes, roughness,
width along the arm and stand-off, the waistband's and the shorts' edges and widths, the cuffs, the collar's and the
bow's torn edges, the bow's shape, the jacket over the band and its open front). The stand-in for ours is labels.py's
Garments (the outfit's drawn piece masks as our objects' labels, the drawing's lines absorbed), with what piece_details
reads besides the labels:
  our_classes   the drawing's classes, moved with the labels (a cuff's cream share reads its own pixels)
  alone         the named objects' pixels of the stand-in (the drawing has no hidden parts: a piece drawn alone is
                what shows of it), depth 0 (the jacket over the band: the design reads 0 tucked)
  our_section   (3D: the puff seen along its arm) sleeve_closeup's own cross-section, the close-up moved as the sheets
                are: the design against itself; a random stand-in has no section (its checks take no floor)
Known-bads: the builds the flags were seen on, measured with this tree's code (charkit/calib/known_bad/NAME.json).
"""
import contextlib

import numpy as np

from .labels import Garments, _shift, patched

TORN_EVERY = 0.06           # L of outline per bite (the probe torn_edges)
TORN_R = (0.008, 0.015)     # L: a bite's radius

CALIBRATION = [
    # Known-bads: body6_render (tool/body round 6, the build Michael reviewed: the hull-lofted sleeves' pointed,
    # spiky caps, the jacket tucked under a band at the hull's span, the hull cuffs and shorts; garments2's checks were
    # written against its faults), look_v5 (Michael: the torn collar tips), g3_d (tool/garments3 18f3b41: the bow's
    # tails' lower edge a torn sliver in profile and three-quarter), g3_render3 (Michael's bow flags: the tails' width).
    # Floors: voronoi_pieces (random cells of random pieces: the silhouette kept, the pieces gone) for a piece's shape
    # and proportions; affine_pieces (each piece moved 0.03-0.06 L and scaled 0.9-1.1 whole: a sloppy fit) where a
    # piece's place is measured (rows, hems, the opening; it keeps a piece's own proportions, so it isn't their floor);
    # affine alone for a silhouette measure (voronoi keeps the silhouette).
    # the puff sleeves' caps: defect detectors (a random stand-in lacks a spike or a torn cap and may pass)
    dict(check='sleeve_*_spikes_L', part='piece_details', adapter='Details', known_bad='body6_render', kind='defect',
         baseline=['voronoi_pieces', 'affine_pieces'], probes=['torn_edges'], shape=['piece_sleeve_L'], better='lower'),
    dict(check='sleeve_*_spikes_R', part='piece_details', adapter='Details', known_bad='body6_render', kind='defect',
         baseline=['voronoi_pieces', 'affine_pieces'], probes=['torn_edges'], shape=['piece_sleeve_R'], better='lower'),
    dict(check='sleeve_*_rough_L', part='piece_details', adapter='Details', known_bad='body6_render', kind='defect',
         baseline=['voronoi_pieces', 'affine_pieces'], probes=['torn_edges'], shape=['piece_sleeve_L'], better='lower'),
    dict(check='sleeve_*_rough_R', part='piece_details', adapter='Details', known_bad='body6_render', kind='defect',
         baseline=['voronoi_pieces', 'affine_pieces'], probes=['torn_edges'], shape=['piece_sleeve_R'], better='lower'),
    # the puff's width along its arm (the pear) against the drawn
    dict(check='sleeve_*_profile_L', part='piece_details', adapter='Details', known_bad='body6_render',
         baseline=['voronoi_pieces'], shape=['piece_sleeve_L'], better='lower'),
    dict(check='sleeve_*_profile_R', part='piece_details', adapter='Details', known_bad='body6_render',
         baseline=['voronoi_pieces'], shape=['piece_sleeve_R'], better='lower'),
    # 3D: the puff's stand-off from the arm against sleeve_closeup's cross-section. No build has failed it and a
    # label image has no section to randomise: unmeasured
    dict(check='sleeve_standoff_[LR]', part='piece_details', adapter='Details', known_bad=None,
         no_known_bad='no build has failed it (body6_render 0.003-0.006, g2_before 0.10 WARN, current 0.03-0.04)',
         baseline=[], shape=['piece_sleeve_L', 'piece_sleeve_R'], better='lower'),
    # the waistband, the shorts: their edges (placement: both floors), widths (proportions: voronoi), the jacket's
    # front over the band in profile (the figure's silhouette: voronoi keeps it, so affine alone)
    dict(check='waistband_profile_overhang', part='piece_details', adapter='Details', known_bad='body6_render',
         baseline=['affine_pieces'], shape=['piece_waistband', 'piece_top'], better='lower'),
    dict(check='waistband_*_rows', part='piece_details', adapter='Details', known_bad='body6_render',
         baseline=['voronoi_pieces', 'affine_pieces'], shape=['piece_waistband'], better='lower'),
    dict(check='waistband_*_width', part='piece_details', adapter='Details', known_bad='body6_render',
         baseline=['voronoi_pieces'], shape=['piece_waistband'], better='lower'),
    dict(check='shorts_*_hem', part='piece_details', adapter='Details', known_bad='body6_render',
         baseline=['voronoi_pieces', 'affine_pieces'], shape=['piece_shorts'], better='lower'),
    dict(check='shorts_*_width', part='piece_details', adapter='Details', known_bad='body6_render',
         baseline=['voronoi_pieces'], shape=['piece_shorts'], better='lower'),
    # the wrist cuffs' flare and cream trim (a cuff's own proportions)
    dict(check='cuff_*_L', part='piece_details', adapter='Details', known_bad='body6_render',
         baseline=['voronoi_pieces'], shape=['piece_cuff_L'], better='lower'),
    dict(check='cuff_*_R', part='piece_details', adapter='Details', known_bad='body6_render',
         baseline=['voronoi_pieces'], shape=['piece_cuff_R'], better='lower'),
    # torn edges (defect detectors; the probe torn_edges bites the drawn pieces' outlines: does the detector see it)
    dict(check='collar_back_torn', part='piece_details', adapter='Details', known_bad=None, kind='defect',

         no_known_bad='no build has read a torn back panel (look_v5, body6_render, g2_before, g3_render3, current: '
                      '0.0)',
         baseline=['voronoi_pieces', 'affine_pieces'], probes=['torn_edges'], shape=['piece_collar'], better='lower'),
    dict(check='collar_*_torn', part='piece_details', adapter='Details', known_bad='look_v5', kind='defect',
         baseline=['voronoi_pieces', 'affine_pieces'], probes=['torn_edges'], shape=['piece_collar'], better='lower'),
    dict(check='bow_*_torn', part='piece_details', adapter='Details', known_bad='g3_d', kind='defect',
         baseline=['voronoi_pieces', 'affine_pieces'], probes=['torn_edges'], shape=['piece_bow'], better='lower'),
    # the bow's shape in front: a bow tie, not a pillow; its tails' width and parting (proportions)
    dict(check='bow_front_flare', part='piece_details', adapter='Details', known_bad='g3_render3',
         baseline=['voronoi_pieces'], shape=['piece_bow'], better='lower'),
    dict(check='bow_front_tail_*', part='piece_details', adapter='Details', known_bad='g3_render3',
         baseline=['voronoi_pieces'], shape=['piece_bow'], better='lower'),
    # the jacket over the band (a defect detector), its open front (placement), the hem's step to the bib
    dict(check='top_*_over_band', part='piece_details', adapter='Details', known_bad='body6_render', kind='defect',
         baseline=['voronoi_pieces', 'affine_pieces'], shape=['piece_top', 'piece_waistband'], better='lower'),
    dict(check='top_front_hem_step', part='piece_details', adapter='Details', known_bad='body6_render',
         baseline=['voronoi_pieces'], shape=['piece_top', 'piece_bodice_panel'], better='lower'),
    dict(check='top_front_opening', part='piece_details', adapter='Details', known_bad='body6_render',
         baseline=['voronoi_pieces', 'affine_pieces'], shape=['piece_top', 'piece_bodice_panel'], better='lower'),
]


class Details(Garments):
    """piece_details: Garments' stand-ins, with the drawing's classes, a piece drawn alone and the puff's section."""
    part = 'piece_details'
    generators = dict({k: v for k, v in Garments.generators.items() if k != 'cap_up'},
                      torn_edges="(probe) every drawn piece's outline bitten: a disk 0.016-0.03 L across per 0.06 L "
                                 "of outline, given to the nearest other label")

    def __init__(self, B, design):
        """Garments' stand-in, with the band as piece_details reads the drawn band: the outfit masks give the waistband
        the jacket's lower part where the jacket hangs over it (the back's hem: 15% of the band's mask here), which
        pieceqa.ink_core cuts off on the design's side; drawn as ours, that part is the jacket's (else the design's own
        band reads 0.042-0.052 L off its rows in back)."""
        from .. import bodymeasure, pieceqa
        Garments.__init__(self, B, design)
        masks, graph, _ = bodymeasure.piece_masks(B.spec)
        pm = bodymeasure.piece_map(graph, B.spec)
        idx = {n: i for i, n in enumerate(self.names)}
        code = lambda pid: idx.get(((pm.get(pid) or [(None, None)])[0])[0], -9)
        band, top = code('waistband'), code('top')
        self.moved_to_top = {}
        for v, lab in self.lab.items():
            m = masks.get('%s__waistband' % v)
            if v == 'profile' or m is None or band < 0 or top < 0:
                continue
            m = m[:lab.shape[0], :lab.shape[1]]
            core = pieceqa.ink_core(m, self.dv[v].get('cls')[:m.shape[0], :m.shape[1]])
            off = np.zeros(lab.shape, bool)
            off[:m.shape[0], :m.shape[1]] = m & ~core
            off &= lab == band
            lab[off] = top
            self.moved_to_top[v] = int(off.sum())
            px = {c: int((lab == c).sum()) for c in self.pieces[v]}
            self.pieces[v] = {c: n for c, n in px.items() if n}

    def labels(self, kind, arg):
        """Garments' stand-ins, and the probe torn_edges: every drawn piece's outline bitten at random (one bite per
        TORN_EVERY L of outline, each a disk of radius TORN_R L, its pixels given to the nearest other label): a torn
        edge the torn and rough detectors should see."""
        if kind != 'torn_edges':
            return Garments.labels(self, kind, arg)
        from scipy import ndimage
        rng = np.random.default_rng(3000 + int(arg))
        out = {}
        for v, L in self.lab.items():
            L2 = L.copy()
            for code in self.pieces[v]:
                m = L == code
                edge = m & ~ndimage.binary_erosion(m)
                ys, xs = np.nonzero(edge)
                if len(ys) < 10:
                    continue
                k = max(2, int(len(ys) / (TORN_EVERY * self.ppl)))
                bite = np.zeros(m.shape, bool)
                yy, xx = np.mgrid[:m.shape[0], :m.shape[1]]
                for i in rng.choice(len(ys), k, replace=False):
                    r = rng.uniform(*TORN_R) * self.ppl
                    y0, x0 = ys[i], xs[i]
                    sl = (slice(max(0, int(y0 - r - 1)), int(y0 + r + 2)),
                          slice(max(0, int(x0 - r - 1)), int(x0 + r + 2)))
                    bite[sl] |= (yy[sl] - y0) ** 2 + (xx[sl] - x0) ** 2 <= r * r
                bite &= m
                if bite.any():
                    _, (iy, ix) = ndimage.distance_transform_edt(m, return_indices=True)
                    L2[bite] = L[iy[bite], ix[bite]]
            out[v] = L2
        return out

    def classes(self, kind, arg):
        """{view: classes} moved with the labels for the design (a generator's stand-in keeps the drawing's)."""
        if kind == 'design':
            return {v: _shift(c, arg[0], arg[1], 0) for v, c in self.cls.items()}
        return dict(self.cls)

    def section(self, arg):
        """sleeve_closeup's cross-section with the close-up moved (dy, dx) px (wrapped: its border is background)."""
        from .. import manifest, pieceqa
        M = manifest.load(self.design.ref()['manifest'])['references']
        if 'sleeve_closeup' not in M:
            return None
        rgb = np.asarray(self.design.rgba(manifest._p(M['sleeve_closeup']['path']))[..., :3])
        return pieceqa.closeup_section(np.roll(np.roll(rgb, arg[0], 0), arg[1], 1))

    def patches(self, L, kind='design', arg=None):
        from .. import pieceqa
        C = self.classes(kind, arg)
        names = self.names

        def our_classes(B, ppl, az3, views=('front', 'three_quarter', 'profile', 'back')):
            return {v: C[v] for v in views if v in C}

        def alone(B, names_, view, az3, ppl, keep, depth=False):
            ids = [i for i, n in enumerate(names) if n in keep]
            lab = L.get(view)
            if not ids or lab is None:
                return None
            m = (lab >= 0) & np.isin(lab % 1000, ids)
            return (m, np.zeros(m.shape, np.float32)) if depth else m

        def our_section(B, sleeve, band, skin, nth=72):
            return self.section(arg) if kind == 'design' else None
        P = [p for p in Garments.patches(self, L, kind) if p[1] != 'our_classes']
        return P + [(pieceqa, 'our_classes', our_classes), (pieceqa, 'alone', alone),
                    (pieceqa, 'our_section', our_section)]

    @contextlib.contextmanager
    def substitute(self, kind, arg):
        with patched(self.patches(self.labels(kind, arg), kind, arg)):
            yield
