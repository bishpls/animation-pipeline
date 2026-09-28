"""SOMA 77 (GEM-X, Kimodo, BONES-SEED) -> VRM 1.0 humanoid bones: {bone: (source joint, source child for the rest
direction)}, plus the hands' twist references (the knuckle line), for motion.retarget / motion.calibrate."""

BONE_MAP = {
    'hips': ('Hips', 'Spine1'), 'spine': ('Spine1', 'Spine2'), 'chest': ('Spine2', 'Chest'),
    'upperChest': ('Chest', 'Neck1'), 'neck': ('Neck1', 'Head'), 'head': ('Head', 'HeadEnd'),
}
for side, S in (('left', 'Left'), ('right', 'Right')):
    BONE_MAP.update({
        f'{side}Shoulder': (f'{S}Shoulder', f'{S}Arm'), f'{side}UpperArm': (f'{S}Arm', f'{S}ForeArm'),
        f'{side}LowerArm': (f'{S}ForeArm', f'{S}Hand'), f'{side}Hand': (f'{S}Hand', f'{S}HandMiddle2'),
        f'{side}UpperLeg': (f'{S}Leg', f'{S}Shin'), f'{side}LowerLeg': (f'{S}Shin', f'{S}Foot'),
        f'{side}Foot': (f'{S}Foot', f'{S}ToeBase'), f'{side}Toes': (f'{S}ToeBase', f'{S}ToeEnd'),
        f'{side}ThumbMetacarpal': (f'{S}HandThumb1', f'{S}HandThumb2'),
        f'{side}ThumbProximal': (f'{S}HandThumb2', f'{S}HandThumb3'),
        f'{side}ThumbDistal': (f'{S}HandThumb3', f'{S}HandThumbEnd'),
    })
    for ours, theirs in (('Index', 'Index'), ('Middle', 'Middle'), ('Ring', 'Ring'), ('Little', 'Pinky')):
        BONE_MAP.update({
            f'{side}{ours}Proximal': (f'{S}Hand{theirs}2', f'{S}Hand{theirs}3'),
            f'{side}{ours}Intermediate': (f'{S}Hand{theirs}3', f'{S}Hand{theirs}4'),
            f'{side}{ours}Distal': (f'{S}Hand{theirs}4', f'{S}Hand{theirs}End'),
        })

# the hands turn about their length so the knuckle line (index -> little) matches the source's
TWIST_REFS = {f'{side}Hand': (f'{S}HandIndex2', f'{S}HandPinky2') for side, S in (('left', 'Left'), ('right', 'Right'))}


def target_twist(arm_joint):
    """-> {bone: fn(arm) -> the bone's rest across vector (index knuckle -> little knuckle), armature space}."""
    return {f'{side}Hand': (lambda a, s=s: arm_joint(f'Little0.{s}') - arm_joint(f'Index0.{s}'))
            for side, s in (('left', 'L'), ('right', 'R'))}
