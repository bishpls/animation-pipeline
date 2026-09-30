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


def _shift(a, dy, dx, fill):
    from .labels import _shift as sh
    if a.ndim == 3:
        return np.stack([sh(a[..., i], dy, dx, fill) for i in range(a.shape[2])], -1)
    return sh(a, dy, dx, fill)


class Art:
    part = 'artifacts'
    generators = {}

    def __init__(self, B, design):
        from .. import artifactqa
        self.B, self.design = B, design
        self.D, _ = artifactqa.design_measures(B, design)

    def run(self, kind, arg):
        """the design's drawings moved (kind 'design', arg (dy, dx)) measured as ours against the stored design ->
        {art_check: dict}."""
        from .. import artifactqa, bodymeasure
        dy, dx = arg
        ref = self.design.ref()
        fs = ref['face_sheet']
        rgb = np.asarray(self.design.rgba(fs['image'])[..., :3], float)
        head, _ = artifactqa.design_heads(_shift(rgb, dy, dx, 1.0), self.B.assembly['eye_knobs']['x'],
                                          fs.get('facing', -1))
        ctx = self.design.sheet_context()
        masks, graph, _ = bodymeasure.piece_masks(self.B.spec)
        views = {v: dict(rgb=_shift(np.asarray(x['rgb'], float), dy, dx, 1.0), fg=_shift(x['fg'], dy, dx, False),
                         cls=_shift(x['cls'], dy, dx, 0), win=x.get('win'))
                 for v, x in self.design.design_views().items()}
        mk = {k: _shift(m, dy, dx, False) for k, m in masks.items()}
        body = artifactqa.design_body(views, mk, graph, ctx['ppl'])
        C = artifactqa.promote(artifactqa.checks(dict(head=head, body=body), self.D))
        return {'art_' + k: v for k, v in C.items()}
