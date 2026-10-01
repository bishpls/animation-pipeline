"""Calibration adapter for range-of-motion QA (charkit.romqa: the range-of-motion suite at the checks' poses on the
build's export; tool/rom, 2026-10-01). Defect detectors with physical limits (no drawing of these poses grades them);
the shape they could be gamed against is the body's and the garments' (sheet_pieces' piece IoUs: a fix that moves the
garments away from the drawing to clear a pose shows there).

  design     the adapter's reference rig (below) with one nuisance setting nudged per move: every pose taken 0.95 /
             0.975 / 1.025 / 1.05 of the way, the points and edges each test casts halved or doubled, the depth that
             counts 0.003 / 0.006 L (0.004). Each must PASS
  floor      'shuffled_weights': the skin's weights shuffled among its vertices (seeded): a random rig. A defect
             detector's floor may pass; reported
  known-bad  'rom_rigid_shoulder' a stored build: the default body before the joined shoulder (the arm a capped tube
             beside the torso: at the 90 deg forward raise it went 0.04 L into the torso, garments4 round 5); 'rom_lbs'
             the build as it ships (linear blend skinning: a 50/50 ring keeps cos(angle / 2) of its area, 0.38 at 135
             deg); the rest computed from the build by the adapter, nothing stored (BROKEN): the skin's blends removed,
             the garments bound to the hips, the hair to the upper chest, each finger skinned to the bones two fingers
             on, the skirt and flaps to the left thigh, 2% of the skin's vertices given half their weight on a far bone,
             the garments' weights shuffled
  reference  the design leg's rig per adapter: Rom and RomShoulder the build itself (the checks it passes; the shoulder's
             on the joined-shoulder candidate), RomVolume the same rig
             skinned by dual quaternions (volume-keeping), RomRigid every garment rigid on its commonest bone (garment
             strain); RomFit (the body's weights on the garments) is kept for the garment checks' next calibration
"""
CALIBRATION = [
    dict(check='rom_vol_elbow', part='rom', adapter='RomVolume', known_bad='rom_lbs', kind='defect',
         shape=['piece_cuff_L', 'piece_cuff_R'], better='higher', baseline=['shuffled_weights']),
    dict(check='rom_vol_knee', part='rom', adapter='RomVolume', known_bad='rom_lbs', kind='defect',
         shape=['piece_boot_L', 'piece_boot_R'], better='higher', baseline=['shuffled_weights']),
    dict(check='rom_vol_fingers', part='rom', adapter='RomVolume', known_bad='rom_lbs', kind='defect',
         shape=['piece_cuff_L', 'piece_cuff_R'], better='higher', baseline=['shuffled_weights']),
    dict(check='rom_shoulder_torso', part='rom', adapter='RomShoulder', known_bad='rom_rigid_shoulder', kind='defect',
         shape=['piece_top', 'piece_sleeve_L', 'piece_sleeve_R'], better='lower', baseline=['shuffled_weights']),
    dict(check='rom_shoulder_open', part='rom', adapter='RomShoulder', known_bad='rom_rigid_shoulder', kind='defect',
         shape=['piece_top', 'piece_sleeve_L', 'piece_sleeve_R'], better='lower', baseline=['shuffled_weights']),
    dict(check='rom_hair_shoulders', part='rom', adapter='Rom', known_bad='rom_hair_on_chest', kind='defect',
         shape=['piece_collar', 'piece_top'], better='lower', baseline=['shuffled_weights']),
    dict(check='rom_finger_finger', part='rom', adapter='Rom', known_bad='rom_fingers_shifted', kind='defect',
         shape=['piece_cuff_L', 'piece_cuff_R'], better='lower', baseline=['shuffled_weights']),
    dict(check='rom_weights_stray', part='rom', adapter='Rom', known_bad='rom_stray', kind='defect',
         shape=['piece_top'], better='lower', baseline=['shuffled_weights']),
    dict(check='rom_garment_strain', part='rom', adapter='RomRigid', known_bad='rom_garments_shuffled', kind='defect',
         shape=['piece_skirt', 'piece_collar', 'piece_top'], better='lower', baseline=['shuffled_weights']),
]
# Not calibrated (INFO with a proposed grade, charkit.romqa): no reference rig or build passes them yet. The puffs
# span the torso and the arm and the skirt the legs, so neither the body's own weights on the garments (garments_fit)
# nor the garments riding the skin as shells (Rig.method 'shell') keep them out of the skin at the raises and the leg
# poses (sleeve_body 0.126 / 0.126 L, skirt_legs 0.165 / 0.165, sleeve_top 0.021 / 0.022 on the default, 2026-10-01):
# rom_sleeve_body, rom_top_body, rom_skirt_legs, rom_sleeve_top (a cloth or spring solution, then calibrate); the
# joined shoulder's own strain and folding (rom_shoulder_strain, rom_shoulder_folded: no shoulder build passes yet),
# rom_knee_folded (dual quaternions fold the knee's inside more, 0.098), rom_neck_strain, rom_leg_torso and rom_leg_open
# (the legs are separate shells: no skinning fixes them), rom_hand_skirt.

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


def fingers_shifted(rig, skin='clawd_skin'):
    """each finger's vertices skinned to the bones two fingers on (index -> ring, middle -> little, ring -> index,
    little -> middle), both hands: a finger curling about another's knuckles sweeps through the fingers between."""
    import numpy as np
    o = rig.objs[skin]
    J = o.J.copy()
    order = ('Index', 'Middle', 'Ring', 'Little')
    for s in ('left', 'right'):
        for a, b in zip(order, order[2:] + order[:2]):
            for seg in ('Proximal', 'Intermediate', 'Distal'):
                J[o.J == _bone(rig, s + a + seg)] = _bone(rig, s + b + seg)
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



def garments_rigid(rig):
    """every garment on its own commonest dominant bone alone: garments that never stretch (the garment strain check's
    reference rig)."""
    import numpy as np
    for o in rig.objs.values():
        if o.kind == 'garment':
            dom = o.J[np.arange(len(o.J)), o.W.argmax(1)]
            _one_bone(o, int(np.bincount(dom).argmax()))


def garments_shuffled(rig, seed=0):
    import numpy as np
    rng = np.random.default_rng(seed)
    for o in rig.objs.values():
        if o.kind == 'garment':
            p = rng.permutation(len(o.J))
            o.J, o.W = o.J[p], o.W[p]


BROKEN = {'rom_rigid_joints': rigid_joints, 'rom_garments_on_hips': garments_on_hips,
          'rom_hair_on_chest': hair_on_chest, 'rom_fingers_shifted': fingers_shifted,
          'rom_skirt_on_thigh': skirt_on_thigh, 'rom_stray': stray, 'rom_garments_shuffled': garments_shuffled}


class Rom:
    """the build as it ships, nudged (the design leg): range-of-motion QA's checks that the build itself passes."""
    part = 'rom'
    stand_in = None                     # (kind, function) the design leg's reference rig, or None: the build itself
    floor = staticmethod(shuffled)      # the random rig
    generators = {'shuffled_weights': "the skin's weights shuffled among its vertices (seeded): a random rig"}

    def __init__(self, B, design=None):
        self.B = B

    def _poses(self):
        from .. import romqa
        return romqa.poses_needed({k: v for k, v in romqa.CHECKS.items() if k in self.checks()} or romqa.CHECKS)

    def checks(self):
        return {e['check'] for e in CALIBRATION if e['adapter'] == type(self).__name__}

    def _checks(self, B=None, weights=None, method='lbs', **kw):
        from .. import romqa
        rep = romqa.measure(B or self.B, poses=self._poses(), weights=weights, method=method, **kw)
        return romqa.checks_of(rep)

    def measure(self, B):
        return self._checks(B)

    def _design(self, **kw):
        return self._checks(**kw)

    def run(self, kind, arg):
        """the reference rig with a nuisance nudged (kind 'design', arg a move), or the floor (a seed)."""
        if kind == 'shuffled_weights':
            return self._checks(weights=lambda rig: type(self).floor(rig, seed=int(arg)))
        return self._design(**NUDGES[tuple(arg)])

    def measure_known_bad(self, name):
        if name == 'rom_lbs':                   # (the build as it ships: linear blend skinning's own collapse)
            return self._checks(method='lbs')
        if name in BROKEN:
            return self._checks(weights=BROKEN[name])
        from .. import calibrate
        d, _ = calibrate.known_bad(name)
        if d is None:
            return None
        return self._checks(calibrate.load_bundle(d))


class RomShoulder(Rom):
    """the shoulder at the arm poses: the design leg the build itself (calibrate it on a joined-shoulder build; the
    known-bad is the stored rigid-tube body)."""


class RomVolume(Rom):
    """joint volume: the design leg the same rig skinned by dual quaternions (Kavan et al. 2007: no linear blend
    collapse at a bend; a volume-keeping deformation of the same mesh, weights and poses), nudged."""

    def _design(self, **kw):
        return self._checks(method='dqs', **kw)


class RomFit(Rom):
    """garments against the body: the design leg every garment skinned with the skin's weights under it
    (garments_fit: fitted cloth following the body exactly), nudged."""
    floor = staticmethod(garments_shuffled)
    generators = {'shuffled_weights': "every garment's weights shuffled among its vertices (seeded)"}

    def _design(self, **kw):
        return self._checks(weights=garments_fit, **kw)


class RomRigid(Rom):
    """garment strain: the design leg every garment rigid on its commonest bone (garments_rigid: nothing stretches),
    nudged."""
    floor = staticmethod(garments_shuffled)
    generators = {'shuffled_weights': "every garment's weights shuffled among its vertices (seeded)"}

    def _design(self, **kw):
        return self._checks(weights=garments_rigid, **kw)


def garments_fit(rig, skin='clawd_skin'):
    """every garment skinned with the skin's own weights at its nearest skin point (barycentric, the top four): the
    garments following the body under them exactly, the production default for fitted cloth - the garment checks'
    reference rig (it can't put a garment through the skin the way mismatched weights do)."""
    import numpy as np
    from ..geom.bvh import BVH
    from .. import rom
    so = rig.objs[skin]
    Wd = rom.dense_weights(rig, so)
    names = rig.bone_names()
    first = {b: rig.bones.index(b) for b in names}
    col = np.array([first[b] for b in names])
    bv = BVH((so.V, so.F))
    for o in rig.objs.values():
        if o.kind != 'garment':
            continue
        _, f, q = bv.nearest(o.V)
        T = so.F[f]
        bc = rom._bary(q, so.V[T[:, 0]], so.V[T[:, 1]], so.V[T[:, 2]])
        Wq = sum(bc[:, i:i + 1] * Wd[T[:, i]] for i in range(3))
        top = np.argsort(-Wq, 1)[:, :4]
        w = np.take_along_axis(Wq, top, 1)
        w = w / np.maximum(w.sum(1, keepdims=True), 1e-12)
        o.J, o.W = col[top], w
