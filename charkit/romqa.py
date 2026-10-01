"""Range-of-motion QA (tool/rom, 2026-10-01): the range-of-motion suite (charkit.rom) run on a build's export at the
poses each check names, report-only. Every check is the worst reading over its poses (the pose named in `pose`, every
pose's reading in `by_pose`), graded against physical limits (charkit.rom.LIMITS: there is no drawing of these poses);
a check whose calibration record is calibrated (charkit/calib/rom.py) carries its grade as its status, the rest report
INFO beside their proposed grade (`grade`), as charkit.artifactqa's do.

  rom_vol_elbow, rom_vol_knee, rom_vol_fingers
                        joint volume: the smallest ring ratio at the joints (the elbows at 135 deg, the knees at 135
                        and in the squat, the knuckles in the fist and the point)
  rom_shoulder_torso    the arm's skin inside the torso at the shoulder's poses (forward, side, overhead; deepest, L;
                        the arm across the chest touches by design and is left out)
  rom_shoulder_open     where the arm's separate shell met the torso at rest (within 0.02 L) parted from it at the
                        shoulder's poses (how far beyond the contact, L: a gap and the tube's cap show; the old body's side raise)
  rom_leg_open          where the thigh's separate shell met the torso at rest (its top buried in the pelvis, or within
                        0.02 L) parted from it at the leg poses (how far beyond the contact, L: a gap and the cap show)
  rom_shoulder_strain, rom_shoulder_folded
                        the skin within 0.35 L of the shoulder joint at the raises: strain p95 (edges of 0.015 L and
                        more), folded + collapsed area share
  rom_knee_folded, rom_neck_strain   the same at the knees (bent) and the neck (the head poses)
  rom_leg_torso         the thigh inside the torso or the other leg at the squat and the kicks (L)
  rom_finger_finger     a finger inside its neighbour at the hand poses (L)
  rom_sleeve_body, rom_skirt_legs, rom_top_body
                        a garment group's vertices newly inside the skin (deepest, L)
  rom_sleeve_top        the puff sleeves' edges newly through the top, the collar, the bow (share)
  rom_garment_strain    p95 |edge / rest - 1| of the worst garment at the raises, the leg poses and the head turn
  rom_hair_shoulders    the hair's edges newly through the skin or the upper garments at the head poses (share)
  rom_hand_skirt        the hands' skin edges newly through the skirt and the flaps (share)
  rom_weights_stray     the skin's share of vertices with a stray influence (charkit.rom.weight_sanity)
"""
import json, os, time

from .registry import qa_part

# check -> (the summary key(s) it reads, its poses (None: every pose run), the worst is 'max' or 'min')
ARM_RAISES = ('raise_forward_90', 'raise_side_90', 'arms_up', 'arms_forward', 'arm_across')
SHOULDER_POSES = ('raise_forward_90', 'raise_side_90', 'arms_up', 'arms_forward')
HEAD_POSES = ('head_turn', 'head_turn_right', 'head_nod', 'head_tilt')
LEG_POSES = ('squat', 'kick_front', 'kick_side')
CHECKS = {
    'rom_vol_elbow': ('vol_elbow', ('elbows_135',), 'min'),
    'rom_vol_knee': ('vol_knee', ('knees_135', 'squat'), 'min'),
    'rom_vol_fingers': ('vol_fingers', ('hand_fist', 'hand_point'), 'min'),
    'rom_shoulder_torso': ('arm_torso', SHOULDER_POSES, 'max'),
    'rom_shoulder_open': ('arm_open', SHOULDER_POSES, 'max'),
    'rom_leg_open': ('leg_open', LEG_POSES, 'max'),
    'rom_shoulder_strain': ('shoulder_strain', ARM_RAISES, 'max'),
    'rom_shoulder_folded': ('shoulder_folded', ARM_RAISES, 'max'),
    'rom_knee_folded': ('knee_folded', ('knees_135', 'squat'), 'max'),
    'rom_neck_strain': ('neck_strain', HEAD_POSES, 'max'),
    'rom_leg_torso': ('leg_torso', LEG_POSES, 'max'),
    'rom_finger_finger': ('finger_finger', ('hand_fist', 'hand_point'), 'max'),
    'rom_sleeve_body': ('sleeve_body', ARM_RAISES + ('elbows_135',), 'max'),
    'rom_top_body': ('top_body', ARM_RAISES + ('spine_twist',), 'max'),
    'rom_skirt_legs': ('skirt_legs', LEG_POSES, 'max'),
    'rom_sleeve_top': (('sleeve_top_L', 'sleeve_top_R'), ARM_RAISES, 'max'),
    'rom_garment_strain': ('garment_strain', ARM_RAISES + LEG_POSES + ('head_turn',), 'max'),
    'rom_hair_shoulders': ('hair_shoulders', HEAD_POSES, 'max'),
    'rom_hand_skirt': ('hand_skirt', ('spine_twist', 'hand_fist'), 'max'),
}
WEIGHT_CHECKS = {'rom_weights_stray': ('stray_share', (0.0, 0.001), ('clawd_skin',))}
# the checks whose records are calibrated (charkit/calib/records): their grade is their status
CALIBRATED = ()


def poses_needed(checks=CHECKS):
    got = []
    for _, poses, _ in checks.values():
        for p in poses or ():
            if p not in got:
                got.append(p)
    return got


def _limit_key(check):
    k = CHECKS[check][0]
    return k[0] if isinstance(k, tuple) else k


def checks_of(rep, calibrated=CALIBRATED):
    """the suite's report (charkit.rom.run's, or measure()'s) -> {check: dict(value, status, grade, pose, by_pose)}."""
    from . import rom
    C = {}
    run = list(rep['poses'])
    for name, (keys, poses, how) in CHECKS.items():
        keys = keys if isinstance(keys, tuple) else (keys,)
        by = {}
        for p in (poses or run):
            s = (rep['poses'].get(p) or {}).get('summary')
            if s is None:
                continue
            vals = [s[k] for k in keys if k in s]
            if vals:
                by[p] = max(vals) if how == 'max' else min(vals)
        if not by:
            continue
        p = (max if how == 'max' else min)(by, key=by.get)
        v = by[p]
        g = rom.grade(_limit_key(name), v)
        C[name] = dict(value=round(float(v), 5), status=g if name in calibrated else 'INFO', grade=g, pose=p,
                       by_pose={k: round(float(x), 5) for k, x in by.items()})
    W = rep.get('weights') or {}
    for name, (key, (p_, w_), objs) in WEIGHT_CHECKS.items():
        by = {o: r.get(key) for o, r in W.items() if r.get(key) is not None and (not objs or o in objs)}
        if not by:
            continue
        o = max(by, key=by.get)
        v = by[o]
        g = 'PASS' if v <= p_ else 'WARN' if v <= w_ else 'FAIL'
        C[name] = dict(value=round(float(v), 5), status=g if name in calibrated else 'INFO', grade=g, object=o,
                       by_object={k: round(float(x), 5) for k, x in by.items() if x})
    return C


def measure(B, poses=None, weights=None, f=1.0, lib=None, max_points=6000, max_edges=30000, tol=None, log=None,
            method='lbs'):
    """the suite on a bundle's build at the checks' poses -> the report (charkit.rom.run's shape, no pictures).
    weights: a function (rig) -> None changing the rig's weights in place (the calibration's broken rigs); f: every pose
    taken f of the way; tol: the penetration depth that counts (L); method: 'lbs' (as a runtime skins the export) or
    'dqs' (the calibration's volume-keeping reference)."""
    from . import pose as P, rom
    from .render.buildboards import export_of
    build = os.path.dirname(os.path.abspath(B.path))
    export = export_of(build)
    if export is None:
        raise FileNotFoundError('no look export beside the bundle (%s)' % build)
    for r in getattr(B, '_reads', ()):                  # (the QA cache keys this part on the export too)
        r.files.add(os.path.abspath(export))
    lm = (B._meta.get('landmarks') or {}).get('joints')
    kinds = {o['name']: {'skin': 'skin', 'hair': 'hair', 'garment': 'garment', 'accessory': 'accessory'}.get(
        o.get('group'), 'face') for o in B._meta.get('objects') or ()}
    t0 = time.time()
    rig = rom.Rig(export, lm, kinds)
    if weights is not None:
        weights(rig)
    rig.method = method
    lib = lib or P.library()
    ctx = rom.Context(rig, B, max_points=max_points, max_edges=max_edges)
    if tol is not None:
        ctx.tol = tol
    rep = {'export': os.path.basename(export), 'L': ctx.L, 'poses': {}, 'f': f}
    rep['weights'] = rom.weight_sanity(rig, ctx.L, max_points=max_points)
    for n in (poses or poses_needed()):
        if n not in lib:
            continue
        D = rig.solve(lib[n], f)
        m = rom.measure_pose(ctx, D)
        rep['poses'][n] = dict(summary=rom.summary(m))
    rep['method'] = method
    rep['seconds'] = round(time.time() - t0, 1)
    if log:
        log('romqa: %d poses, %.1f s' % (len(rep['poses']), rep['seconds']))
    return rep


@qa_part('rom', order=2600, prefix='', table='rom')
def rom_qa(B, design=None, out=None):
    """the range-of-motion suite at the checks' poses on the build's export (report-only)."""
    rep = measure(B)
    C = checks_of(rep)
    table = {'L': rep['L'], 'export': rep['export'], 'seconds': rep['seconds'],
             'poses': {n: r['summary'] for n, r in rep['poses'].items()},
             'weights': rep['weights']}
    if out:
        json.dump(table, open(os.path.join(out, 'qa_rom.json'), 'w'), indent=1)
    return table, C
