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
    # (the probe head_subpx: the head sheet resampled half a pixel down, its figure masks alike: the design itself at
    # another sampling phase; the whole-sheet moves are whole pixels, which a speck count can't see)
    dict(check='art_speckle_neck', part='artifacts', adapter='Art', known_bad='look_v5', kind='defect',
         probes=['head_subpx'], shape=[]),
    dict(check='art_outline_collar', part='artifacts', adapter='Art', known_bad='look_v5', kind='defect',
         shape=['piece_collar']),
    dict(check='art_fragments_collar', part='artifacts', adapter='Art', known_bad='look_v5', kind='defect',
         shape=['piece_collar']),
    dict(check='art_terminator_hair', part='artifacts', adapter='Art', known_bad='look_v5', kind='defect', shape=[]),
    dict(check='art_peeks_hair', part='artifacts', adapter='Art', known_bad='look_v5', kind='defect', shape=[]),
    # (the probe boot_nudge: the right boot's piece masks moved 2 px up: the pair's own asymmetry, which a whole-sheet
    # move can't change)
    dict(check='art_mirror_self_boots', part='artifacts', adapter='Art', known_bad='body4b_render', kind='defect',
         probes=['boot_nudge'], shape=['piece_boot_L', 'piece_boot_R']),
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


def _subpx(a, dy, dx, fill=None):
    """a picture moved a fraction of a pixel (bilinear; a mask resampled alike and cut at 0.5; a label image nearest),
    its far edge wrapped round."""
    from scipy import ndimage
    if a.dtype == bool:
        return ndimage.shift(a.astype(float), (dy, dx), order=1, mode='wrap') >= 0.5
    if a.ndim == 2:
        return ndimage.shift(a, (dy, dx), order=0, mode='wrap')
    return np.stack([ndimage.shift(a[..., c], (dy, dx), order=1, mode='wrap') for c in range(a.shape[2])], -1)


class Art:
    part = 'artifacts'
    generators = {
        'head_subpx': '(probe) the head sheet resampled half a pixel down (bilinear), its figure masks alike: the '
                      'design at another sampling phase',
        'boot_nudge': "(probe) the right boot's piece masks (boot_R, boot_cuff_R) moved 2 px up in every view",
    }

    def __init__(self, B, design):
        from .. import artifactqa
        self.B, self.design = B, design
        self.D, _ = artifactqa.design_measures(B, design)

    def heads(self, dy, dx, sheet=None):
        """artifactqa.design_heads with the head sheet, brought to scale once (refcheck.at_scale's fit to 0.3 px doesn't
        converge on a sheet moved a pixel before it), moved dy, dx inside each head's fixed box, eye line and chin row.
        The hair from the hair's shape truth when it declares one (qa3d.Design.shape_head: its clips repainted away),
        as the design's measures read it (artifactqa.design_compute)."""
        from .. import artifactqa as aq, refcheck
        if sheet is None and self.design.hidden('hair'):
            out = self.heads(dy, dx, sheet='drawn')
            hair = self.heads(dy, dx, sheet='shape')
            for v, rec in out.items():
                if 'hair' in (hair.get(v) or {}):
                    rec['hair'] = hair[v]['hair']
            return out
        key = '_at_shape' if sheet == 'shape' else '_at'
        if not hasattr(self, key):
            fs = self.design.ref()['face_sheet']
            pic = self.design.shape_head('hair') if sheet == 'shape' else self.design.rgba(fs['image'])[..., :3]
            rgb0, _ = refcheck.without_guides(np.asarray(pic, float))
            rgb1, _, H = refcheck.at_scale(rgb0, self.B.assembly['eye_knobs']['x'],
                                           2 * self.B.assembly['eye_knobs']['x'] * aq.HEAD_PPL, fs.get('facing', -1))
            _, chin = refcheck.measure_heads(rgb1, H['heads'], aq.HEAD_PPL, fs.get('facing', -1))
            setattr(self, key, (rgb1, H, -float(chin) if chin is not None else 0.36))
        rgb1, H, chin_L = getattr(self, key)
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
        """the design's drawings moved (kind 'design', arg (dy, dx)) measured as ours against the stored design, or a
        probe's (head_subpx, boot_nudge) -> {art_check: dict}."""
        from .. import artifactqa, bodymeasure
        global _shift
        nudge = None
        if kind == 'head_subpx':
            whole, _shift = _shift, _subpx
            try:
                head = self.heads(0.5, 0)
            finally:
                _shift = whole
            dy, dx = 0, 0
        else:
            dy, dx = arg if kind == 'design' else (0, 0)
            nudge = ('boot_R', 'boot_cuff_R') if kind == 'boot_nudge' else None
            head = self.heads(dy, dx)
        for regs in head.values():              # (the drawing has no pieces: none of its own bits peeks past another,
            for rec in regs.values():           # so the design standing in for ours reads no peeks)
                if isinstance(rec, dict) and rec.get('fragments') is not None:
                    rec['fragments'].setdefault('peeks', 0)
        ctx = self.design.sheet_context()
        masks, graph, _ = bodymeasure.piece_masks(self.B.spec)
        views = {v: dict(rgb=_shift(np.asarray(x['rgb'], float), dy, dx, 1.0), fg=_shift(x['fg'], dy, dx, False),
                         cls=_shift(x['cls'], dy, dx, 0), win=x.get('win'))
                 for v, x in self.design.design_views().items()}
        mk = {k: _shift(m, dy, dx, False) for k, m in masks.items()}
        if nudge:
            mk = {k: np.roll(m, -2, 0) if k.split('__', 1)[-1] in nudge else m for k, m in mk.items()}
        body = artifactqa.design_body(views, mk, graph, ctx['ppl'])
        C = artifactqa.promote(artifactqa.checks(dict(head=head, body=body), self.D))
        return {'art_' + k: v for k, v in C.items()}
