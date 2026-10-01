"""Calibration adapter for the body sheet's hair checks (qa3d.sheet_body: body_<view>_iou_hair, bodyqa's hair class
against ours per view; tool/hairtruth, 2026-10-01: measured against the hair's shape truth, the drawing with its clips
repainted from hair_clips_layers, ours without our clips). Ours is our classes z-buffered on the design's grids
(bodyqa.zbuffer_views); here the design's own classes (the hair's shape truth: qa3d.Design.shape_views) stand in,
moved or perturbed, and the part's measuring code runs unchanged on them (patched in for the run).

Generators (the floor and the probes; seeded):
  voronoi_head   the head's box (above the hair/dress split, the drawn head's columns, background included) cut into
                 random cells (40), each hair at random (weighted by the hair's drawn share of the box) or else what the
                 drawing has there (skin where it drew hair): a random hair silhouette round the head
  voronoi_hair   (probe) the head's drawn hair and skin cut into random cells (40), each hair or skin at random
                 (weighted by their drawn areas): the head's outline kept, the hair's shape gone inside it (in profile,
                 where the hair is most of the head, the IoU can't tell it: reported)
  affine_hair    (probe) the drawn hair moved 0.03-0.06 L and scaled 0.9-1.1 about its middle (a sloppy fit)
"""
import contextlib

import numpy as np

from .labels import _shift, affine, patched, voronoi

CALIBRATION = [
    # the hair's silhouette per view, a shape check (the anti-gaming guard's kind of measure): no single flagged build
    dict(check='body_*_iou_hair', part='sheet_body', adapter='BodyHair', known_bad=None,
         no_known_bad="a shape check (the hair's silhouette per view against its shape truth): no single flagged build",
         baseline=['voronoi_head'], probes=['voronoi_hair', 'affine_hair'], shape=[], better='higher'),
]


class BodyHair:
    part = 'sheet_body'
    generators = {
        'voronoi_head': "the head's box (above the hair/dress split, the drawn head's columns, background included) cut "
                        "into random cells (40), each hair at random (weighted by the hair's share of the box) or else "
                        "what the drawing has there",
        'voronoi_hair': "the head's drawn hair and skin (above the hair/dress split) cut into random cells (40), each "
                        "hair or skin at random (weighted by their drawn areas)",
        'affine_hair': '(probe) the drawn hair moved 0.03-0.06 L and scaled 0.9-1.1 about its middle',
    }

    def __init__(self, B, design):
        from .. import bodyqa
        self.B, self.design = B, design
        self.ppl = design.sheet_context()['ppl']
        sv = design.shape_views('hair')
        self.lab = {v: np.where(d['fg'], d['cls'], -1).astype(np.int32) for v, d in sv.items()}
        self.C = bodyqa.CLASS

    def labels(self, kind, arg):
        """{view: class label image}: the design moved (kind 'design', arg (dy, dx)) or a generator's (arg its seed)."""
        from .. import bodyqa
        if kind == 'design':
            return {v: _shift(L, arg[0], arg[1], -1) for v, L in self.lab.items()}
        rng = np.random.default_rng(4000 + int(arg))
        hair, skin = self.C['hair'], self.C['skin']
        out = {}
        for v, L in self.lab.items():
            z = bodyqa.WIN['top'] - (np.arange(L.shape[0]) + 0.5) / self.ppl
            head = (z > bodyqa.HAIR_SPLIT)[:, None] & np.isin(L, [hair, skin])
            L2 = L.copy()
            if kind == 'voronoi_head':
                cols = np.nonzero(head.any(0))[0]
                box = np.zeros(L.shape, bool)
                if len(cols):
                    box[:, cols.min():cols.max() + 1] = (z > bodyqa.HAIR_SPLIT)[:, None]
                    rows = np.nonzero(head.any(1))[0]
                    box[:rows.min()] = False
                p = float((L[box] == hair).mean()) if box.any() else 0.0
                if 0 < p < 1:
                    V = voronoi(box, [1, 0], [p, 1 - p], 40, rng)
                    keep = np.where(L == hair, skin, L)
                    L2[box] = np.where(V[box] == 1, hair, keep[box])
            elif kind == 'voronoi_hair':
                nh, ns = int((L[head] == hair).sum()), int((L[head] == skin).sum())
                if nh and ns:
                    V = voronoi(head, [hair, skin], [nh, ns], 40, rng)
                    L2[head] = V[head]
            elif kind == 'affine_hair':
                m = L == hair
                L2[m] = skin
                L2[affine(m, rng, self.ppl) & (L2 >= 0)] = hair
            else:
                raise KeyError(kind)
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
