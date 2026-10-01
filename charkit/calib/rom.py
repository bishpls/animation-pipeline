"""Calibration adapter for range-of-motion QA (charkit.romqa: the range-of-motion suite at the checks' poses on the
build's export; tool/rom, 2026-10-01). Defect detectors with physical limits (no drawing of these poses grades them);
the shape they could be gamed against is the body's and the garments' (sheet_pieces' piece IoUs: a fix that moves the
garments away from the drawing to clear a pose shows there).

  design     the good build measured with one nuisance setting nudged per move: every pose taken 0.95 / 0.975 / 1.025 /
             1.05 of the way, the points and edges each test casts halved or doubled, the depth that counts 0.003 /
             0.006 L (0.004). Each must PASS
  floor      'shuffled_weights': the skin's weights shuffled among its vertices (seeded): a random rig. A defect
             detector's floor may pass; reported
  known-bad  'rom_rigid_shoulder' a stored build: the default body before the joined shoulder (the arm a capped tube
             beside the torso: at the 90 deg forward raise it went 0.04 L into the torso, garments4 round 5); the rest
             computed from the build by the adapter, nothing stored (BROKEN): the skin's blends removed (each vertex on
             its dominant bone alone), the garments bound to the hips, the hair to the upper chest, each finger skinned
             to its neighbour's bones, the skirt and flaps to the left thigh, 2% of the skin's vertices given half their
             weight on a far bone
"""
CALIBRATION = []

NUDGES = {(0, 1): dict(f=1.025), (0, 2): dict(f=1.05), (1, 0): dict(f=0.975), (2, 0): dict(f=0.95),
          (0, -1): dict(max_points=3000, max_edges=15000), (0, -2): dict(max_points=12000, max_edges=60000),
          (-1, 0): dict(tol=0.003), (-2, 0): dict(tol=0.006)}


def _one_bone(o, bone_index):
    import numpy as np
    o.J = np.zeros_like(o.J) + bone_index
    o.W = np.zeros_like(o.W)
    o.W[:, 0] = 1.0


def _bone(rig, name):
    return rig.bones.index(name)


def rigid_joints(rig, skin='clawd_skin'):
    """every skin vertex on its dominant bone alone (no blend across any joint)."""
    import numpy as np
    o = rig.objs[skin]
    k = o.W.argmax(1)
    j = o.J[np.arange(len(o.J)), k]
    o.J = np.zeros_like(o.J) + j[:, None]
    o.W = np.zeros_like(o.W)
    o.W[:, 0] = 1.0


def garments_on_hips(rig):
    for o in rig.objs.values():
        if o.kind == 'garment':
            _one_bone(o, _bone(rig, 'hips'))


def hair_on_chest(rig):
    for o in rig.objs.values():
        if o.kind == 'hair':
            _one_bone(o, _bone(rig, 'upperChest'))


def skirt_on_thigh(rig):
    for n in ('skirt', 'overskirt_panel_L', 'overskirt_panel_R'):
        if n in rig.objs:
            _one_bone(rig.objs[n], _bone(rig, 'leftUpperLeg'))


def fingers_swapped(rig, skin='clawd_skin'):
    """each finger's vertices weighted to its neighbour's bones (index <-> middle, ring <-> little), both hands."""
    import numpy as np
    o = rig.objs[skin]
    names = np.array(rig.bones)
    J = o.J.copy()
    for s in ('left', 'right'):
        for a, b in (('Index', 'Middle'), ('Ring', 'Little')):
            for seg in ('Proximal', 'Intermediate', 'Distal'):
                ia, ib = _bone(rig, s + a + seg), _bone(rig, s + b + seg)
                J[o.J == ia] = ib
                J[o.J == ib] = ia
    o.J = J


def stray(rig, skin='clawd_skin', share=0.02, seed=0):
    """share of the skin's vertices given half their weight on a far bone (the opposite foot's for the upper body, the
    head's for the legs)."""
    import numpy as np
    o = rig.objs[skin]
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(o.V), int(share * len(o.V)), replace=False)
    far_up, far_down = _bone(rig, 'rightFoot'), _bone(rig, 'head')
    z = o.V[idx, 2]
    far = np.where(z > np.median(o.V[:, 2]), far_up, far_down)
    o.W[idx] *= 0.5
    k = o.W[idx].argmin(1)
    o.J[idx, k] = far
    o.W[idx, k] += 0.5


def shuffled(rig, seed=0, skin='clawd_skin'):
    import numpy as np
    o = rig.objs[skin]
    p = np.random.default_rng(seed).permutation(len(o.J))
    o.J, o.W = o.J[p], o.W[p]


BROKEN = {'rom_rigid_joints': rigid_joints, 'rom_garments_on_hips': garments_on_hips, 'rom_hair_on_chest': hair_on_chest,
          'rom_fingers_swapped': fingers_swapped, 'rom_skirt_on_thigh': skirt_on_thigh, 'rom_stray': stray}


class Rom:
    part = 'rom'
    generators = {'shuffled_weights': "the skin's weights shuffled among its vertices (seeded): a random rig"}

    def __init__(self, B, design=None):
        self.B = B

    def _checks(self, B=None, **kw):
        from .. import romqa
        rep = romqa.measure(B or self.B, **kw)
        return romqa.checks_of(rep)

    def measure(self, B):
        return self._checks(B)

    def run(self, kind, arg):
        """the good build with a nuisance nudged (kind 'design', arg a move), or the floor (a seed)."""
        if kind == 'shuffled_weights':
            return self._checks(weights=lambda rig: shuffled(rig, seed=int(arg)))
        return self._checks(**NUDGES[tuple(arg)])

    def measure_known_bad(self, name):
        if name in BROKEN:
            return self._checks(weights=BROKEN[name])
        from .. import calibrate
        d, _ = calibrate.known_bad(name)
        if d is None:
            return None
        return self._checks(calibrate.load_bundle(d))
