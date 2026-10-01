"""Calibration adapters for a garment's parts and the lines inside them (charkit.partqa's bow_parts: the bow's knot and
lobes in every view, the knot's outline and rectangle and each lobe's crease in front) and for the pieces drawn alone
against their isolated references (charkit.isoqa's iso_pieces: the bow's silhouette against bow_closeup, its lines
against garment_breakdown). tool/pieceref, Michael 2026-09-30.

The stand-in for ours is the turnaround's own bow: the outfit's part masks (VIEW__bow.knot|lobe_L|lobe_R, the drawn
bow_tail masks) as our parts, and the design's drawn lines (partqa.design_lines: its ink and its fainter strokes) as
our outlines, where partqa and isoqa read ours:
  partqa.grid_labels   our z-buffer on the design's grids, the bow's parts coded (partqa.CODES)
  partqa.line_picture  ours drawn with the build's outlines in front at LINE_PPL: the design's parts and lines scaled
                       from its grid to LINE_PPL (nearest), the lines' pixels no part's (as our outlines are)
  isoqa.our_piece      ours alone in front: the design's parts and lines on its own grid (compare scales both)
The design moved 1-2 px keeps its lines where they were drawn against its parts (both move); a generator's stand-in
keeps the drawing's lines where they are and moves or relabels the parts under them.
Known-bad: g3_render3 (pipeline-3d 3ebc3fb's build: the round knot with no line against the lobes, pillow lobes with
no crease, the knot hidden in profile; partqa's and isoqa's checks were written against it).
"""
import contextlib

import numpy as np

from .labels import _shift, affine, patched, voronoi

CALIBRATION = [
    # the parts' shapes per view (shape checks: a random stand-in must not pass them). voronoi_parts keeps the bow's
    # silhouette and cuts it into random parts; affine_parts moves and scales each part (a sloppy fit)
    dict(check='bow_part_knot_iou', part='bow_parts', adapter='BowParts', known_bad='g3_render3',
         baseline=['voronoi_parts', 'affine_parts'], shape=['piece_bow'], better='higher'),
    dict(check='bow_part_lobe_iou', part='bow_parts', adapter='BowParts', known_bad=None,
         no_known_bad="a guard: the lobes are sized to the drawn ones, so the flagged build's pillows read 0.715 PASS",
         baseline=['voronoi_parts', 'affine_parts'], shape=['piece_bow'], better='higher'),
    # the lines inside the bow (defect detectors: a random stand-in keeps the drawing's lines and may pass)
    dict(check='bow_part_knot_line', part='bow_parts', adapter='BowParts', known_bad='g3_render3', kind='defect',
         baseline=['voronoi_parts', 'affine_parts'], shape=['piece_bow'], better='lower'),
    dict(check='bow_part_knot_rect', part='bow_parts', adapter='BowParts', known_bad='g3_render3', kind='defect',
         baseline=['voronoi_parts', 'affine_parts'], shape=['piece_bow'], better='lower'),
    dict(check='bow_part_crease_*', part='bow_parts', adapter='BowParts', known_bad='g3_render3', kind='defect',
         baseline=['voronoi_parts', 'affine_parts'], shape=['piece_bow'], better='lower'),
    # the bow alone against its isolated references: its silhouette (voronoi keeps it: affine alone is its floor)
    dict(check='iso_bow_body', part='iso_pieces', adapter='IsoParts', known_bad='g3_render3',
         baseline=['affine_parts'], shape=['piece_bow'], better='higher'),
    dict(check='iso_bow_knot_line', part='iso_pieces', adapter='IsoParts', known_bad='g3_render3', kind='defect',
         baseline=['voronoi_parts', 'affine_parts'], shape=['piece_bow'], better='lower'),
    dict(check='iso_bow_crease_*', part='iso_pieces', adapter='IsoParts', known_bad='g3_render3', kind='defect',
         baseline=['voronoi_parts', 'affine_parts'], shape=['piece_bow'], better='lower'),
]

BODY = ('knot', 'lobe_L', 'lobe_R')
TAILS = {'tail_L': 'bow_tail_L', 'tail_R': 'bow_tail_R'}


class BowParts:
    """bow_parts: the turnaround's bow parts and lines as ours."""
    part = 'bow_parts'
    generators = {
        'voronoi_parts': "the drawn bow's knot and lobes cut into random cells (3 per part), each a random part "
                         "(weighted by the parts' drawn areas): the bow's silhouette kept, its parts gone",
        'affine_parts': "each drawn part (knot, lobes) moved 0.03-0.06 L and scaled 0.9-1.1 about its middle at random",
    }

    def __init__(self, B, design):
        from .. import bodymeasure, partqa as P
        self.B, self.design = B, design
        ctx = design.sheet_context()
        self.ppl, self.az3 = ctx['ppl'], ctx['az3']
        self.dv = design.design_views()
        masks = bodymeasure.piece_masks(B.spec)[0]
        self.lab, self.px = {}, {}
        for v in P.VIEWS:
            if v not in self.dv:
                continue
            sh = self.dv[v]['cls'].shape
            lab = np.full(sh, -1, np.int32)
            px = {}
            for k, pid in TAILS.items():
                m = P._fit(masks.get('%s__%s' % (v, pid)), sh)
                lab[m] = P.CODES[k]
            for k in ('lobe_L', 'lobe_R', 'knot'):             # (the knot drawn over the lobes)
                m = P._fit(masks.get('%s__bow.%s' % (v, k)), sh)
                lab[m] = P.CODES[k]
                if m.any():
                    px[P.CODES[k]] = int(m.sum())
            self.lab[v], self.px[v] = lab, px
        self.line = P.design_lines(self.dv['front'], self.dv['front']['cls'].shape) if 'front' in self.dv else None

    def labels(self, kind, arg):
        """({view: label image (partqa.CODES, -1 elsewhere)}, the front's lines) for a stand-in."""
        if kind == 'design':
            return ({v: _shift(L, arg[0], arg[1], -1) for v, L in self.lab.items()},
                    None if self.line is None else _shift(self.line, arg[0], arg[1], False))
        rng = np.random.default_rng(3000 + int(arg))
        out = {}
        for v, L in self.lab.items():
            px = self.px[v]
            body = np.isin(L, list(px))
            L2 = L.copy()
            if kind == 'voronoi_parts':
                V = voronoi(body, list(px), list(px.values()), 3 * max(1, len(px)), rng)
                L2[body] = V[body]
            elif kind == 'affine_parts':
                L2[body] = -1
                for code in px:                                 # (lobes, then the knot over them)
                    L2[affine(L == code, rng, self.ppl)] = code
            else:
                raise KeyError(kind)
            out[v] = L2
        return out, self.line

    def patches(self, L, line):
        from .. import partqa as P
        from scipy import ndimage

        def grid_labels(B, ppl, az3, views=P.VIEWS):
            return {v: L[v] for v in views if v in L}

        def line_picture(B, az, ppl_design, win=P.LINE_WIN, ppl=P.LINE_PPL, only=None):
            # the front's parts and lines at the picture's scale (the design's grid scaled to ppl px per L)
            k = ppl / float(self.ppl)
            lab = ndimage.zoom(L['front'], k, order=0)
            ln = ndimage.zoom(line.astype(np.uint8), k, order=0) > 0 if line is not None else np.zeros(lab.shape, bool)
            h, w = min(lab.shape[0], ln.shape[0]), min(lab.shape[1], ln.shape[1])
            lab, ln = lab[:h, :w], ln[:h, :w]
            part = np.where(ln | (lab < 0), 0, lab)
            return dict(part=part, line=ln, name=np.where(lab >= 0, 'bow', ''), fr=None)
        return [(P, 'grid_labels', grid_labels), (P, 'line_picture', line_picture)]

    @contextlib.contextmanager
    def substitute(self, kind, arg):
        L, line = self.labels(kind, arg)
        with patched(self.patches(L, line)):
            yield


class IsoParts(BowParts):
    """iso_pieces: the turnaround's front bow (parts and lines) as ours drawn alone."""
    part = 'iso_pieces'

    def patches(self, L, line):
        from .. import isoqa, partqa as P
        from scipy import ndimage

        def our_piece(B, az, ppl_design, only=('bow', 'bow_knot')):
            lab = L['front']
            ln = line if line is not None else np.zeros(lab.shape, bool)
            parts = {k: (lab == c) & ~ln for k, c in P.CODES.items()}
            mask = ndimage.binary_fill_holes((lab >= 0) | (ln & ndimage.binary_dilation(lab >= 0, iterations=2)))
            return dict(mask=mask, line=ln & mask, parts=parts)
        return [(isoqa, 'our_piece', our_piece)]
