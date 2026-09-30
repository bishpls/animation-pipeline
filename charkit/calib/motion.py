"""Calibration adapter for motion QA (charkit.sim.motionqa: the skirt's new penetration into the skin and its stretch,
worst over the kick and the squat, moved as the style profile says). Defect detectors: a random stand-in has no motion
to be wrong in, so there is no floor; the shape they could be gamed against is the skirt's (piece_skirt; the rest
shape is the template, which motion never changes).

  design     the held solve (the style's garment motion) with one nuisance setting nudged per move: substeps 16 / 24
             (20), the ramp into the pose 0.35 / 0.45 s (0.4), 3 iterations (2), the colliders 0.005 L fatter (their fit's
             median error), the hold 0.05 either way (for a held method; else substeps 12 / 30). Each must PASS
  known-bad  computed from the same build by the adapter, nothing stored: 'motion_skinned' the skirt skinned as the build
             ships it (round 1: the kick's front panel dragged up with the thigh, 199% stretch p99), 'motion_pelvis_rigid'
             the skirt carried by the pelvis alone (the hold's target with no cloth: the kicking thigh goes through it;
             the skinned skirt barely enters the skin at the kick, 0.1%, because it stretches instead)
"""
CALIBRATION = [
    dict(check='motion_kick_skirt_stretch', part='motion', adapter='Motion', known_bad='motion_skinned', kind='defect',
         shape=['piece_skirt'], better='lower'),
    dict(check='motion_squat_skirt_stretch', part='motion', adapter='Motion', known_bad='motion_skinned', kind='defect',
         shape=['piece_skirt'], better='lower'),
    dict(check='motion_squat_skirt_inside', part='motion', adapter='Motion', known_bad='motion_skinned', kind='defect',
         shape=['piece_skirt'], better='lower'),
    dict(check='motion_kick_skirt_inside', part='motion', adapter='Motion', known_bad='motion_pelvis_rigid',
         kind='defect', shape=['piece_skirt'], better='lower'),
]

KNOWN = {'motion_skinned': 'skinned', 'motion_pelvis_rigid': 'pelvis_rigid'}


def nudge(move, hold):
    """a design move (rows, columns) -> the held solve's nudged settings."""
    m = tuple(move)
    table = {(0, 1): dict(substeps=16), (0, 2): dict(substeps=24), (1, 0): dict(ramp=0.35), (2, 0): dict(ramp=0.45),
             (0, -1): dict(iterations=3), (0, -2): dict(radius=0.005)}
    if hold and hold > 0:
        table.update({(-1, 0): dict(hold_shape=hold - 0.05), (-2, 0): dict(hold_shape=min(1.0, hold + 0.05))})
    else:
        table.update({(-1, 0): dict(substeps=12), (-2, 0): dict(substeps=30)})
    return table[m]


class Motion:
    part = 'motion'
    generators = {}

    def __init__(self, B, design=None):
        from ..sim import motionqa
        self.B = B
        self.gm = motionqa.settings(B)

    def _checks(self, gm, **over):
        from ..sim import motionqa
        _, C = motionqa.measure(self.B, gm, **over)
        return {'motion_' + k: v for k, v in C.items()}

    def measure(self, B):
        return self._checks(self.gm)

    def run(self, kind, arg):
        """the held solve nudged (kind 'design', arg a move)."""
        n = dict(nudge(arg, self.gm.get('hold_shape')))
        gm = dict(self.gm)
        if 'hold_shape' in n:
            gm['hold_shape'] = n.pop('hold_shape')
        return self._checks(gm, **n)

    def measure_known_bad(self, name):
        return self._checks(dict(self.gm, method=KNOWN[name]))
