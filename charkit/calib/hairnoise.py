"""Calibration adapter for hair_noise (charkit.qa3d.hair_noise). Round 4 (tool/hairshell3) redefined it as a speckle
measure: blobs under 0.002 L^2 standing out by half the hair's cel step, per L^2 of hair (qa3d.speckles), on the hair
drawn with its outlines as the render draws them (the ink and its filtered edge not counted). The measure before it
(tone edges per hair pixel) read the design's own lock-shaped shadows as noise (0.216 FAIL) and the flagged blotchy
build as WARN (0.046); it stays as INFO (hair_tone_edges).

Ours is our hair's pictures from 0, 90 and 180 degrees (qa3d.hair_noise_views); here the design stands in: the body
sheet's front, profile and back hair (bodyqa.design_views: the hair class as its drawn cel tones, paletteqa's lit and
shade, each pixel the nearer, and its drawn shine marks, the pale strokes across the crown, as a third tone; the drawn
lines as the ink) brought to the QA picture's scale (its pixel filter, the ink's reach as hair_noise_ink's), the buns
their own tone group where the hair layers name them; moved 1-2 px at the sheet's own resolution (the sampling phase
moves). The part's measuring code runs unchanged on them (qa3d.hair_noise_views patched for the run).

Known-bad: ck7_blotchy, pipeline-3d's confirm run's final build ck7_final of 2026-09-28, the build the review flagged
(T003: "the hair shading is blotchy: light speckles on the back and sides").

Generators (seeded):
  speckle        the design's hair with random blots (radius 1-2 px, 6% of the hair) each in the colour of a random
                 hair pixel: speckled shading (the floor)
  voronoi_tones  (probe) the design's hair cut into random cells, as many as its own tone regions, each in the colour of a
                 random hair pixel: as many tone regions, none of its shapes. A speckle detector is blind to it by design
                 (cells are large): the hair pieces' shape checks guard the shapes
"""
import contextlib

import numpy as np

from .labels import patched

CALIBRATION = [
    dict(check='hair_noise', part='hair_noise', adapter='HairNoise', known_bad='ck7_blotchy', kind='defect',
         baseline=['speckle'], probes=['voronoi_tones'], better='lower',
         shape=['hair_piece_bangs', 'hair_piece_side_locks', 'hair_piece_upper_back', 'hair_piece_lower_back']),
]

VIEWS = ((0, 'front'), (90, 'profile'), (180, 'back'))
SHINE_DL = 0.06         # the design's shine marks: hair this much over its lit tone's luminance (tool/hairstrokes' tones)


class HairNoise:
    part = 'hair_noise'
    shine = True            # the stand-in keeps the design's drawn shine marks (False: two cel tones, round 3's)
    generators = {
        'speckle': "the design's hair with random blots (radius 1-2 px, 6% of the hair), each a random hair pixel's colour",
        'voronoi_tones': "the design's hair cut into random cells, as many as its tone regions, each a random hair "
                         "pixel's colour",
    }

    def __init__(self, B, design):
        self.B, self.design = B, design
        self._dv = None

    def _inputs(self):
        """the design's views at the sheet's resolution, the QA picture's px per L, the buns' masks (lazy: a known-bad's
        old bundle never needs them)."""
        if self._dv is None:
            from .. import qa3d
            B = self.B
            dv = self.design.design_views()
            from .. import paletteqa
            pal = self.design.memo(paletteqa.extract_views, dv).get('hair') or {}
            self._pal = (np.asarray(pal['lit'], float), np.asarray(pal['shade'], float)) if 'lit' in pal and \
                'shade' in pal else None
            fr = qa3d.figure_frame(B, ss=qa3d.FIG_SS)
            ppl_qa = B.assembly['L'] / (fr.pix * qa3d.FIG_SS)
            buns = {}
            try:
                from .. import manifest
                Z = np.load(manifest.produced(B.spec, 'hair_layers'))
                buns = {v: Z['%s__buns' % v] for _, v in VIEWS if '%s__buns' % v in Z.files}
            except Exception:
                buns = {}
            self._dv = (dv, ppl_qa, buns)
        return self._dv

    def stand_in(self, dy=0, dx=0):
        """per view (az, picture RGBA, tone group, ink) at the QA's scale: the design moved dy, dx sheet pixels."""
        from scipy import ndimage
        from .. import bodyqa, qa3d
        dv, ppl_qa, buns = self._inputs()
        out = []
        for az, v in VIEWS:
            if v not in dv:
                continue
            d = dv[v]
            rgb = np.asarray(d['rgb'], float)
            rgb = rgb / 255.0 if rgb.max() > 1.5 else rgb
            hair = d['cls'] == bodyqa.CLASS['hair']
            if self._pal is not None:
                # the hair as its drawn cel tones: each hair pixel the nearer of the design's lit and shade
                # (paletteqa's, as sheet_palette reads them), not the painting's gradients and brush texture; and
                # (round 4) its drawn shine marks, a third tone: the pixels SHINE_DL over the lit tone's luminance
                # (the short pale strokes across the crown), in their own median colour
                lit, sh = self._pal
                near_sh = ((rgb - sh) ** 2).sum(-1) < ((rgb - lit) ** 2).sum(-1)
                cel = np.where(near_sh[..., None], sh, lit)
                if self.shine:
                    lum = rgb @ np.array([0.3, 0.59, 0.11])
                    hi = hair & (lum > float(lit @ np.array([0.3, 0.59, 0.11])) + SHINE_DL)
                    if hi.sum() >= 3:
                        cel = np.where(hi[..., None], np.median(rgb[hi], 0), cel)
                rgb = np.where(hair[..., None], cel, rgb)
            line = (d['raw'] == bodyqa.CLASS['line']) & ndimage.binary_dilation(hair, iterations=2)
            bun = buns.get(v)
            bun = bun if bun is not None and bun.shape == hair.shape else np.zeros_like(hair)
            mv = lambda a: np.roll(np.roll(a, dy, 0), dx, 1)
            rgb, hair, line, bun = mv(rgb), mv(hair), mv(line), mv(bun)
            f = ppl_qa / float(d['ppl'])
            sig = qa3d.FIG_FILTER / f
            H, W = int(hair.shape[0] * f), int(hair.shape[1] * f)
            rr, cc = np.meshgrid((np.arange(H) + 0.5) / f - 0.5, (np.arange(W) + 0.5) / f - 0.5, indexing='ij')
            at = lambda a, o=1: ndimage.map_coordinates(a, [rr, cc], order=o, mode='nearest')
            px = np.zeros((H, W, 4))
            for c in range(3):
                px[..., c] = at(ndimage.gaussian_filter(rgb[..., c], sig))
            px[..., 3] = at(ndimage.gaussian_filter((hair | line).astype(float), sig))
            reach = (2 * qa3d.HAIR_NOISE_INK + 1) / f
            ink = at(ndimage.maximum_filter(line.astype(float), size=int(np.ceil(reach))), 0) > 0
            lab = np.where(at(hair.astype(float)) >= 0.5, np.where(at(bun.astype(float), 0) > 0, 2, 1), 0)
            out.append((az, px, lab, ink))
        return out

    def generated(self, kind, seed):
        from scipy import ndimage
        rng = np.random.default_rng(9100 + int(seed))
        out = []
        for az, px, lab, ink in self.stand_in():
            px = px.copy()
            hair = (lab >= 1) & ~ink
            rr, cc = np.nonzero(hair)
            if not len(rr):
                out.append((az, px, lab, ink)); continue
            if kind == 'speckle':
                n = int(0.06 * len(rr) / (np.pi * 1.5 ** 2))
                k = rng.integers(0, len(rr), n)
                src = rng.integers(0, len(rr), n)
                Y, X = np.mgrid[:px.shape[0], :px.shape[1]]
                for i in range(n):
                    r_ = rng.uniform(1.0, 2.0)
                    m = ((Y - rr[k[i]]) ** 2 + (X - cc[k[i]]) ** 2 <= r_ * r_) & hair
                    px[m, :3] = px[rr[src[i]], cc[src[i]], :3]
            elif kind == 'voronoi_tones':
                from .. import qa3d
                lum = px[..., :3] @ np.array([0.3, 0.59, 0.11])
                q = np.digitize(lum, np.percentile(lum[hair], [33, 66]))
                regions = sum(ndimage.label(hair & (q == t))[1] for t in range(3))
                n = max(2, int(regions))
                k = rng.integers(0, len(rr), n)
                _, (iy, ix) = ndimage.distance_transform_edt(
                    ~np.isin(np.arange(px.shape[0] * px.shape[1]).reshape(px.shape[:2]), rr[k] * px.shape[1] + cc[k]),
                    return_indices=True)
                cell = iy * px.shape[1] + ix
                src = rng.integers(0, len(rr), n)
                colour = {int(rr[k[i]] * px.shape[1] + cc[k[i]]): px[rr[src[i]], cc[src[i]], :3].copy() for i in range(n)}
                for key, col in colour.items():
                    m = (cell == key) & hair
                    px[m, :3] = col
            else:
                raise KeyError(kind)
            out.append((az, px, lab, ink))
        return out

    @contextlib.contextmanager
    def substitute(self, kind, arg):
        from .. import qa3d
        views = self.stand_in(*arg) if kind == 'design' else self.generated(kind, arg)
        with patched([(qa3d, 'hair_noise_views', lambda B, hair: views)]):
            yield
