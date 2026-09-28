"""MakeHuman's CC0 assets as plain data (no MakeHuman code): the hm08 base mesh with its groups and UVs, macro targets, the
default skeleton's joints (vertex lists, so they follow every morph) and its skin weights; merged onto VRM 1.0 humanoid bones.
Coordinates come out in Blender's frame: metres, Z up, the body facing -Y, her left at +X.
"""
import json, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MH = os.path.join(HERE, 'assets', 'makehuman')


def to_blender(v):
    """MakeHuman decimetres, Y up, facing +Z  ->  metres, Z up, facing -Y."""
    v = np.asarray(v, np.float64)
    return np.stack([v[..., 0], -v[..., 2], v[..., 1]], -1) * 0.1


class Base:
    """The base mesh: verts (N,3) MakeHuman frame, faces per group [(idx...)], face UVs, the joint helper groups."""

    def __init__(self, path=os.path.join(MH, 'base.obj')):
        V, VT, faces, fuv, group = [], [], [], [], []
        cur = None
        for line in open(path):
            if line.startswith('v '):
                V.append([float(x) for x in line.split()[1:4]])
            elif line.startswith('vt '):
                VT.append([float(x) for x in line.split()[1:3]])
            elif line.startswith('g '):
                cur = line.split()[1]
            elif line.startswith('f '):
                p = [t.split('/') for t in line.split()[1:]]
                faces.append(tuple(int(q[0]) - 1 for q in p))
                fuv.append(tuple(int(q[1]) - 1 for q in p) if len(p[0]) > 1 and p[0][1] else None)
                group.append(cur)
        self.verts = np.array(V)
        self.uvs = np.array(VT) if VT else None
        self.faces, self.face_uv, self.face_group = faces, fuv, group
        self.groups = {}
        for f, g in zip(faces, group):
            self.groups.setdefault(g, set()).update(f)

    def group_faces(self, name):
        return [i for i, g in enumerate(self.face_group) if g == name]


def load_target(name):
    """a .target file -> (vertex indices, offsets) in MakeHuman's frame."""
    idx, d = [], []
    for line in open(os.path.join(MH, 'targets', name)):
        if not line.strip() or line.startswith('#'):
            continue
        p = line.split()
        idx.append(int(p[0])); d.append([float(x) for x in p[1:4]])
    return np.array(idx, int), np.array(d)


def morph(verts, weights):
    """verts + sum of w * target; weights {target file: w}."""
    v = verts.copy()
    for name, w in weights.items():
        if w:
            i, d = load_target(name)
            v[i] += w * d
    return v


def macro_weights(sex=0.0, age=0.35, muscle=0.5, weight=0.5, height=0.5, proportions=0.5, ethnic=(0.5, 0.5)):
    """MakeHuman's macro modifiers, for the young-adult range we use (sex 0 female .. 1 male; age 0 child .. 1 young adult;
    muscle/weight/height 0..1 around the 0.5 average; ethnic = (caucasian, asian) shares). Returns {target: weight}."""
    w = {}
    cau, asi = ethnic
    for sx, ws in (('female', 1 - sex), ('male', sex)):
        young = age
        for eth, we in (('caucasian', cau), ('asian', asi)):
            if f'{eth}-{sx}-young.target' in TARGETS:
                w[f'{eth}-{sx}-young.target'] = ws * we * young
            if f'{eth}-{sx}-child.target' in TARGETS:
                w[f'{eth}-{sx}-child.target'] = ws * we * (1 - young)
    fem = 1 - sex
    if muscle < 0.5:
        w['universal-female-young-minmuscle-averageweight.target'] = fem * (0.5 - muscle) * 2
    else:
        w['universal-female-young-maxmuscle-averageweight.target'] = fem * (muscle - 0.5) * 2
    if weight < 0.5:
        w['universal-female-young-averagemuscle-minweight.target'] = fem * (0.5 - weight) * 2
    else:
        w['universal-female-young-averagemuscle-maxweight.target'] = fem * (weight - 0.5) * 2
    if height < 0.5:
        w['female-young-averagemuscle-averageweight-minheight.target'] = fem * (0.5 - height) * 2
    else:
        w['female-young-averagemuscle-averageweight-maxheight.target'] = fem * (height - 0.5) * 2
    w['female-young-averagemuscle-averageweight-idealproportions.target'] = fem * proportions
    return {k: v for k, v in w.items() if k in TARGETS and abs(v) > 1e-6}


TARGETS = set(os.listdir(os.path.join(MH, 'targets'))) if os.path.isdir(os.path.join(MH, 'targets')) else set()


class Skeleton:
    """The default skeleton: bone -> (head joint, tail joint, parent); joint positions from their vertex lists."""

    def __init__(self, path=os.path.join(MH, 'default.mhskel'), weights=os.path.join(MH, 'default_weights.mhw')):
        s = json.load(open(path))
        self.bones = {n: (b['head'], b['tail'], b['parent']) for n, b in s['bones'].items()}
        self.joints = s['joints']
        self.weights = json.load(open(weights))['weights']

    def joint_positions(self, verts):
        return {j: verts[np.array(ix)].mean(0) for j, ix in self.joints.items()}


# MakeHuman bone -> VRM 1.0 humanoid bone (merged). Face bones and the realistic head go to 'head' (the head is replaced).
def vrm_bone(mh):
    s = 'left' if mh.endswith('.L') else ('right' if mh.endswith('.R') else '')
    b = mh[:-2] if s else mh
    if b in ('root', 'pelvis'):
        return 'hips'
    if b in ('spine05', 'spine04'):
        return 'spine'
    if b in ('spine03', 'spine02', 'breast'):
        return 'chest'
    if b == 'spine01':
        return 'upperChest'
    if b.startswith('neck'):
        return 'neck'
    if b == 'clavicle':
        return f'{s}Shoulder'
    if b in ('shoulder01', 'upperarm01', 'upperarm02'):
        return f'{s}UpperArm'
    if b in ('lowerarm01', 'lowerarm02'):
        return f'{s}LowerArm'
    if b == 'wrist' or b.startswith('metacarpal'):
        return f'{s}Hand'
    if b.startswith('finger'):
        f, k = b[6:].split('-')
        name = {'1': 'Thumb', '2': 'Index', '3': 'Middle', '4': 'Ring', '5': 'Little'}[f]
        seg = (['Metacarpal', 'Proximal', 'Distal'] if f == '1' else ['Proximal', 'Intermediate', 'Distal'])[int(k) - 1]
        return f'{s}{name}{seg}'
    if b in ('upperleg01', 'upperleg02'):
        return f'{s}UpperLeg'
    if b in ('lowerleg01', 'lowerleg02'):
        return f'{s}LowerLeg'
    if b == 'foot':
        return f'{s}Foot'
    if b.startswith('toe'):
        return f'{s}Toes'
    return 'head'


# VRM bone -> (MakeHuman head joint, MakeHuman tail joint): the merged chains' ends
VRM_JOINTS = {
    'hips': ('spine05____head', 'spine04____head'), 'spine': ('spine04____head', 'spine03____head'),
    'chest': ('spine03____head', 'spine01____head'), 'upperChest': ('spine01____head', 'neck01____head'),
    'neck': ('neck01____head', 'head____head'), 'head': ('head____head', 'head____tail'),
}
for _s, _S in (('left', 'L'), ('right', 'R')):
    VRM_JOINTS.update({
        f'{_s}Shoulder': (f'clavicle.{_S}____head', f'shoulder01.{_S}____head'),
        f'{_s}UpperArm': (f'shoulder01.{_S}____head', f'lowerarm01.{_S}____head'),
        f'{_s}LowerArm': (f'lowerarm01.{_S}____head', f'wrist.{_S}____head'),
        f'{_s}Hand': (f'wrist.{_S}____head', f'finger3-1.{_S}____head'),
        f'{_s}UpperLeg': (f'upperleg01.{_S}____head', f'lowerleg01.{_S}____head'),
        f'{_s}LowerLeg': (f'lowerleg01.{_S}____head', f'foot.{_S}____head'),
        f'{_s}Foot': (f'foot.{_S}____head', f'toe1-1.{_S}____head'),
        f'{_s}Toes': (f'toe1-1.{_S}____head', f'toe1-1.{_S}____tail'),
    })
    for f, name in (('1', 'Thumb'), ('2', 'Index'), ('3', 'Middle'), ('4', 'Ring'), ('5', 'Little')):
        segs = ['Metacarpal', 'Proximal', 'Distal'] if f == '1' else ['Proximal', 'Intermediate', 'Distal']
        for k, seg in enumerate(segs, 1):
            VRM_JOINTS[f'{_s}{name}{seg}'] = (f'finger{f}-{k}.{_S}____head', f'finger{f}-{k}.{_S}____tail')

VRM_PARENT = {'hips': None, 'spine': 'hips', 'chest': 'spine', 'upperChest': 'chest', 'neck': 'upperChest', 'head': 'neck'}
for _s in ('left', 'right'):
    VRM_PARENT.update({f'{_s}Shoulder': 'upperChest', f'{_s}UpperArm': f'{_s}Shoulder', f'{_s}LowerArm': f'{_s}UpperArm',
                       f'{_s}Hand': f'{_s}LowerArm', f'{_s}UpperLeg': 'hips', f'{_s}LowerLeg': f'{_s}UpperLeg',
                       f'{_s}Foot': f'{_s}LowerLeg', f'{_s}Toes': f'{_s}Foot'})
    for name in ('Thumb', 'Index', 'Middle', 'Ring', 'Little'):
        segs = ['Metacarpal', 'Proximal', 'Distal'] if name == 'Thumb' else ['Proximal', 'Intermediate', 'Distal']
        prev = f'{_s}Hand'
        for seg in segs:
            VRM_PARENT[f'{_s}{name}{seg}'] = prev
            prev = f'{_s}{name}{seg}'


def vrm_weights(skel, n_verts):
    """per-vertex weights merged onto VRM bones: {vrm bone: (N,) array}, normalised."""
    W = {}
    for mh_bone, pairs in skel.weights.items():
        vb = vrm_bone(mh_bone)
        arr = W.setdefault(vb, np.zeros(n_verts))
        for vi, w in pairs:
            if vi < n_verts:
                arr[vi] += w
    tot = sum(W.values())
    tot[tot == 0] = 1
    return {k: v / tot for k, v in W.items()}
