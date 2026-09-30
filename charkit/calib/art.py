"""Calibration adapter for the artifact detectors calibrated on Michael's flags (charkit.artifactqa: art_*, each the worst
view's ratio to, or excess over, the design's own reading; docs/workstreams/artifacts.md). The design against itself:
the head and body sheets (with the outfit's masks) moved 1-2 px and measured by the same detectors, against the stored
design measures (the sampling phase and the frame's edge are what move). Known-bads: the builds each flag was calibrated
on. These are defect detectors (corners, specks, fragments, spikes, a mirror asymmetry): a random stand-in isn't a
floor for them; the pieces' shapes are the anti-gaming guard's.
"""
import numpy as np

CALIBRATION = [
    dict(check='art_outline_neck', part='artifacts', adapter='Art', known_bad='look_v5', kind='defect', shape=[]),
    dict(check='art_speckle_neck', part='artifacts', adapter='Art', known_bad='look_v5', kind='defect', shape=[]),
    dict(check='art_outline_collar', part='artifacts', adapter='Art', known_bad='look_v5', kind='defect',
         shape=['piece_collar']),
    dict(check='art_fragments_collar', part='artifacts', adapter='Art', known_bad='look_v5', kind='defect',
         shape=['piece_collar']),
    dict(check='art_terminator_hair', part='artifacts', adapter='Art', known_bad='look_v5', kind='defect', shape=[]),
    dict(check='art_peeks_hair', part='artifacts', adapter='Art', known_bad='look_v5', kind='defect', shape=[]),
    dict(check='art_*_boots', part='artifacts', adapter='Art', known_bad='body4b_render', kind='defect', shape=[]),
    dict(check='art_mirror_waist', part='artifacts', adapter='Art', known_bad='body4b_render', kind='defect',
         shape=['piece_waistband']),
    dict(check='art_bumps_legs', part='artifacts', adapter='Art', known_bad='body5b_render', kind='defect', shape=[]),
    dict(check='art_*_sleeves', part='artifacts', adapter='Art', known_bad='body6_render', kind='defect',
         shape=['piece_sleeve_L', 'piece_sleeve_R']),
    dict(check='art_band_lower', part='artifacts', adapter='Art', known_bad='body6_render', kind='defect',
         shape=['piece_skirt']),
]


def _shift(a, dy, dx, fill=None):
    """a picture moved dy rows and dx columns, its far edge wrapped round (the sheets' borders are their background, so
    no strip of another colour comes in: a white fill on the head sheet's black background broke its scale's detection)."""
    return np.roll(np.roll(a, dy, 0), dx, 1)


class Art:
    part = 'artifacts'
    generators = {}

    def __init__(self, B, design):
        from .. import artifactqa
        self.B, self.design = B, design
        self.D, _ = artifactqa.design_measures(B, design)

    def heads(self, dy, dx):
        """artifactqa.design_heads with the head sheet, brought to scale once (refcheck.at_scale's fit to 0.3 px doesn't
        converge on a sheet moved a pixel before it), moved dy, dx inside each head's fixed box, eye line and chin row."""
        from .. import artifactqa as aq, refcheck
        if not hasattr(self, '_at'):
            fs = self.design.ref()['face_sheet']
            rgb0, _ = refcheck.without_guides(np.asarray(self.design.rgba(fs['image'])[..., :3], float))
            rgb1, _, H = refcheck.at_scale(rgb0, self.B.assembly['eye_knobs']['x'],
                                           2 * self.B.assembly['eye_knobs']['x'] * aq.HEAD_PPL, fs.get('facing', -1))
            _, chin = refcheck.measure_heads(rgb1, H['heads'], aq.HEAD_PPL, fs.get('facing', -1))
            self._at = (rgb1, H, -float(chin) if chin is not None else 0.36)
        rgb1, H, chin_L = self._at
        rgb1 = _shift(rgb1, dy, dx)
        out = {}
        for view, h in H['heads'].items():
            if view not in aq.VIEWS:
                continue
            x0, y0, x1, y1 = h['box']
            pad = 6
            y0, x0 = max(0, y0 - pad), max(0, x0 - pad)
            y1, x1 = min(rgb1.shape[0], y1 + pad), min(rgb1.shape[1], x1 + pad)
            crop = rgb1[y0:y1, x0:x1]
            fg = aq._figure(crop, _shift(h['_mask'], dy, dx)[y0:y1, x0:x1])
            out[view] = aq.drawing_view(crop, fg, aq.HEAD_PPL, h['eye_y'] - y0 + chin_L * aq.HEAD_PPL, aq.HEAD_REGIONS)
        return out

    def run(self, kind, arg):
        """the design's drawings moved (kind 'design', arg (dy, dx)) measured as ours against the stored design ->
        {art_check: dict}."""
        from .. import artifactqa, bodymeasure
        dy, dx = arg
        head = self.heads(dy, dx)
        ctx = self.design.sheet_context()
        masks, graph, _ = bodymeasure.piece_masks(self.B.spec)
        views = {v: dict(rgb=_shift(np.asarray(x['rgb'], float), dy, dx, 1.0), fg=_shift(x['fg'], dy, dx, False),
                         cls=_shift(x['cls'], dy, dx, 0), win=x.get('win'))
                 for v, x in self.design.design_views().items()}
        mk = {k: _shift(m, dy, dx, False) for k, m in masks.items()}
        body = artifactqa.design_body(views, mk, graph, ctx['ppl'])
        C = artifactqa.promote(artifactqa.checks(dict(head=head, body=body), self.D))
        return {'art_' + k: v for k, v in C.items()}
