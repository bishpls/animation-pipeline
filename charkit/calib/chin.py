"""Calibration adapter for the chin's shadow on the jaw (charkit.lookqa: face_shadow_chin_edge, face_shadow_chin; Michael's
chin-shadow flag). look5's first chin measure failed its own calibration (the design's shadow moved 1-2 px read IoU
0.55-0.87, eye-aligned); look6 measured on the jaw (designlight.chin_calibration). Here that same code moves the
design's drawn shadow against its own jaw: MOVES for the design, 4-8 px in a random direction for the floor.
"""
import numpy as np

CALIBRATION = [
    dict(check='face_shadow_chin_edge', part='look', adapter='Chin', known_bad='look5_before',
         baseline=['shadow_moved'], shape=[], better='lower'),
    dict(check='face_shadow_chin', part='look', adapter='Chin', known_bad='look5_before',
         baseline=['shadow_moved'], shape=[], better='higher'),
]


def floor_move(seed):
    """a seed's move for the floor: 4-8 px in a random direction (rows, columns)."""
    rng = np.random.default_rng(3000 + int(seed))
    r, a = rng.uniform(4, 8), rng.uniform(0, 2 * np.pi)
    return int(round(r * np.sin(a))), int(round(r * np.cos(a)))


class Chin:
    part = 'look'
    generators = {'shadow_moved': "the design's own shadow moved 4-8 px in a random direction against its jaw"}

    def __init__(self, B, design):
        self.B, self.design = B, design
        self._moved = None

    def _all(self):
        if self._moved is None:
            from .. import calibrate, designlight
            moves = list(calibrate.MOVES) + [floor_move(s) for s in range(20)]
            got = designlight.chin_calibration(self.B, self.design, None, moves=tuple(dict.fromkeys(moves)))
            self._moved = {v: r['moved'] for v, r in got.items()}
        return self._moved

    def run(self, kind, arg):
        """the chin's two checks with the design's shadow moved (kind 'design': arg the move; 'shadow_moved': arg a
        seed) -> {check: dict(value, status)}, as lookqa grades them."""
        from .. import lookqa
        m = arg if kind == 'design' else floor_move(arg)
        key = '%+d,%+d' % tuple(m)
        per = {v: mv.get(key) for v, mv in self._all().items() if mv.get(key)}
        out = {}
        iou = [x[0] for x in per.values() if x[0] is not None]
        edge = [x[1] for x in per.values() if x[1] is not None]
        if iou:
            v = float(np.mean(iou))
            out['face_shadow_chin'] = dict(value=round(v, 4), status=lookqa._grade_chin(v, lookqa.CHIN_IOU, True),
                                           per_view={k: x[0] for k, x in per.items()})
        if edge:
            v = float(np.mean(edge))
            out['face_shadow_chin_edge'] = dict(value=round(v, 4), status=lookqa._grade_chin(v, lookqa.CHIN_EDGE, False),
                                                per_view={k: x[1] for k, x in per.items()})
        return out
