"""Shot-side helpers for putting a charkit character (charkit.scene.build) through the 3D pipeline's motion and face
machinery (build/motion.py, soma_map.py), without touching charkit itself: resolve and build the character, fix it up
for animation (hair normals baked at rest, spring bones for the hair and skirt, shot-weight outlines), calibrate the
mocap retarget against charkit's MakeHuman A-pose rest, lock the shoes to the floor, and key the face (lid, brow and mouth
shape keys, iris gaze keys, the SDF face light in head space).
    import charkit_rig as CR     (from a shot script run inside Blender; see dance_charkit.py)
"""
import math, os, subprocess, sys
from contextlib import contextmanager

import numpy as np
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))          # the repo (worktree) root
BUILD = os.path.join(os.path.dirname(HERE), 'build')
if BUILD not in sys.path:
    sys.path.insert(0, BUILD)
import motion, soma_map                                                      # noqa: E402

VENV_PY = os.path.expanduser('~/animation-pipeline/.venv/bin/python')       # has PIL, which charkit.refs needs


# ------------------------------------------------------------------------------------------------------------ build
CHARKIT = ROOT                   # where charkit is imported from (use_charkit)


def use_charkit(rev, out):
    """pin the charkit a shot is made with. rev 'live': the working tree as it is (charkit is under active development, so a
    long render can catch it mid-edit); a git revision ('HEAD', a hash): that revision's charkit exported to
    out/charkit_<rev>/, with what git does not carry linked from the working tree (charkit/out: the generated shapes; the
    design reference rig under projects/tsuzuku). Call before anything imports charkit. -> the root charkit is imported from."""
    global CHARKIT
    if rev != 'live':
        sha = subprocess.run(['git', '-C', ROOT, 'rev-parse', '--short', rev], capture_output=True, text=True,
                             check=True).stdout.strip()
        snap = os.path.join(out, f'charkit_{sha}')
        if not os.path.isdir(os.path.join(snap, 'charkit')):
            os.makedirs(snap, exist_ok=True)
            arc = subprocess.run(['git', '-C', ROOT, 'archive', sha, 'charkit'], capture_output=True, check=True).stdout
            subprocess.run(['tar', '-x', '-C', snap], input=arc, check=True)
            os.symlink(os.path.join(ROOT, 'charkit', 'out'), os.path.join(snap, 'charkit', 'out'))
            os.makedirs(os.path.join(snap, 'projects'), exist_ok=True)
            os.symlink(os.path.join(ROOT, 'projects', 'tsuzuku'), os.path.join(snap, 'projects', 'tsuzuku'))
        CHARKIT = snap
    if 'charkit' in sys.modules:
        raise RuntimeError('charkit already imported')
    sys.path.insert(0, CHARKIT)
    return CHARKIT


def resolve_spec(spec, out):
    """charkit.cli.resolve (fit the spec's knobs to its design reference) run in the venv, into `out`: -> resolved path.
    spec: relative to the pinned charkit's root (or absolute)."""
    spec = spec if os.path.isabs(spec) else os.path.join(CHARKIT, spec)
    code = f"import sys; sys.path.insert(0, {CHARKIT!r}); from charkit import cli; print(cli.resolve({spec!r}, {out!r})[1])"
    r = subprocess.run([VENV_PY, '-c', code], cwd=CHARKIT, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-2000:])
    return r.stdout.strip().splitlines()[-1]


def build(spec_path):
    from charkit import scene
    return scene.build(scene.load(spec_path))


def bake_hair_normals(S):
    """charkit's generated hair takes its shading normals from a smooth proxy through a DATA_TRANSFER modifier that runs
    before the hair's armature while the proxy is itself rigged, so once the head moves the lookup is made between a rest
    hair and a posed proxy (the hair's shading swims as the head turns). Apply the transfer at rest instead (it is first in
    the stack) and drop the proxy."""
    for ob in list(S.hair):
        md = ob.modifiers.get('volume_normals')
        if md is None:
            continue
        proxy = md.object
        with bpy.context.temp_override(object=ob, active_object=ob):
            bpy.ops.object.modifier_apply(modifier=md.name)
        if proxy is not None and not any(m.type == 'DATA_TRANSFER' and m.object == proxy
                                         for o in bpy.data.objects for m in getattr(o, 'modifiers', [])):
            bpy.data.objects.remove(proxy, do_unlink=True)


def settle_garments(S, follow=(('bow', 'top'),), push=(('collar', 0.0025), ('bow', 0.002))):
    """fit fixes for motion: `follow` gives a rigid piece the weights of the garment under it (inverse-distance mix of the 4
    nearest vertices at rest), so it rides the chest as it deforms instead of cutting into it (charkit rigs the bow rigidly
    to upperChest); `push` lifts a piece off what it lies on along its vertex normals (metres; the collar meets the top at
    rest)."""
    from mathutils import kdtree
    obs = {o.name: o for o in S.garments}
    for name, src in follow:
        ob, so = obs.get(name), obs.get(src)
        if ob is None or so is None:
            continue
        SW = _weights(so)
        SV = [so.matrix_world @ v.co for v in so.data.vertices]
        kd = kdtree.KDTree(len(SV))
        for i, p in enumerate(SV):
            kd.insert(p, i)
        kd.balance()
        n = len(ob.data.vertices)
        W = {g: np.zeros(n) for g in SW}
        for v in ob.data.vertices:
            hits = kd.find_n(ob.matrix_world @ v.co, 4)
            ws = np.array([1.0 / max(d, 1e-4) for _, _, d in hits]); ws /= ws.sum()
            for (_, i, _), w in zip(hits, ws):
                for g in SW:
                    W[g][v.index] += w * SW[g][i]
        for g in list(ob.vertex_groups):
            ob.vertex_groups.remove(g)
        for g, w in W.items():
            if w.max() > 1e-4:
                _set_weights(ob, g, w)
    for name, d in push:
        ob = obs.get(name)
        if ob is None:
            continue
        co = np.empty(len(ob.data.vertices) * 3); ob.data.vertices.foreach_get('co', co)
        nr = np.empty_like(co); ob.data.vertices.foreach_get('normal', nr)
        ob.data.vertices.foreach_set('co', co + nr * d)
        ob.data.update()


def outlines(scale):
    """scale every inverted-hull outline (charkit draws them for close-up boards; a full-body shot needs heavier lines)."""
    for ob in bpy.data.objects:
        for md in getattr(ob, 'modifiers', []):
            if md.type == 'SOLIDIFY' and md.name == 'outline':
                md.thickness *= scale


def _smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def _set_weights(ob, name, w, eps=1e-4):
    """one vertex group from a per-vertex array (batched by value)."""
    g = ob.vertex_groups.get(name) or ob.vertex_groups.new(name=name)
    q = np.round(w, 3)
    for v in np.unique(q):
        idx = [int(i) for i in np.nonzero(q == v)[0]]
        if v <= eps:
            g.remove(idx)
        else:
            g.add(idx, float(v), 'REPLACE')


def _weights(ob):
    """{group: (N,) weights} for a mesh object."""
    n = len(ob.data.vertices)
    out = {g.name: np.zeros(n) for g in ob.vertex_groups}
    names = {g.index: g.name for g in ob.vertex_groups}
    for v in ob.data.vertices:
        for ge in v.groups:
            out[names[ge.group]][v.index] = ge.weight
    return out


def add_bones(arm, bones):
    """bones: {name: (head, tail, parent)} in armature space."""
    bpy.context.view_layer.objects.active = arm
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    for n, (h, t, par) in bones.items():
        b = eb.new(n)
        b.head, b.tail = Vector(h), Vector(t)
        b.parent = eb[par]; b.use_connect = False
        b.align_roll(Vector((0, -1, 0)))
    bpy.ops.object.mode_set(mode='OBJECT')
    for n in bones:
        arm.pose.bones[n].rotation_mode = 'QUATERNION'


# stiffness, damping, limit (deg): motion.bake's damped rotational springs
SPRINGS = {'hairSpring_B': (80.0, 10.0, 12.0), 'hairSpring_L': (105.0, 10.5, 14.0), 'hairSpring_R': (95.0, 10.0, 14.0),
           'skirtSpring': (140.0, 13.0, 12.0)}


def add_springs(S, hair_amt=0.85, skirt_amt=0.45):
    """secondary motion without editing charkit: spring bones added to the built armature and weights painted onto the
    built hair and skirt. Hair: three pendulums hung from the crown (back, her left, her right), each taking the hair on its
    side by azimuth, the weight rising from nothing at the eye line (the bangs, the buns and the clips stay rigid) to
    `hair_amt` at the ends. Skirt: one pendulum from the waist, the weight rising toward the hem (v of its UV), taken
    proportionally from its hips and thigh weights. -> SPRINGS (for motion.bake)."""
    C = S.character
    arm = C['arm']
    A = C['data']
    c = Vector(A['head']['centre'])
    sk = next((o for o in S.garments if o.name == 'skirt'), None)
    bones = {'hairSpring_B': (c + Vector((0, 0.03, 0.10)), c + Vector((0, 0.09, -0.14)), 'head'),
             'hairSpring_L': (c + Vector((0.06, 0.0, 0.09)), c + Vector((0.12, 0.02, -0.14)), 'head'),
             'hairSpring_R': (c + Vector((-0.06, 0.0, 0.09)), c + Vector((-0.12, 0.02, -0.14)), 'head')}
    if sk is not None:
        zw = max(v.co.z for v in sk.data.vertices)
        cy = float(np.mean([v.co.y for v in sk.data.vertices if v.co.z > zw - 0.01]))
        bones['skirtSpring'] = (Vector((0, cy, zw)), Vector((0, cy + 0.03, zw - 0.28)), 'hips')
    add_bones(arm, bones)
    cc = np.array(c)
    for ob in S.hair:
        V = np.array([ob.matrix_world @ v.co for v in ob.data.vertices]) - cc
        s = hair_amt * _smooth(0.0, -0.18, V[:, 2]) ** 1.2
        az = np.arctan2(V[:, 0], -V[:, 1])                          # 0 front, + her left
        wb = ((1 - np.cos(az)) / 2) ** 1.5
        wl = (1 - wb) * np.clip(0.5 + V[:, 0] / 0.08, 0, 1)
        wr = (1 - wb) - wl
        W = _weights(ob)
        for g, w in W.items():
            _set_weights(ob, g, w * (1 - s))
        _set_weights(ob, 'hairSpring_B', s * wb)
        _set_weights(ob, 'hairSpring_L', s * wl)
        _set_weights(ob, 'hairSpring_R', s * wr)
    if sk is not None:
        uv = sk.data.uv_layers['uv']
        vv = np.zeros(len(sk.data.vertices))
        for lp in sk.data.loops:
            vv[lp.vertex_index] = uv.data[lp.index].uv[1]
        s = skirt_amt * vv ** 1.6
        W = _weights(sk)
        for g, w in W.items():
            _set_weights(sk, g, w * (1 - s))
        _set_weights(sk, 'skirtSpring', s)
    return {k: v for k, v in SPRINGS.items() if k in bones}


# ------------------------------------------------------------------------------------------------------ retargeting
# charkit's MakeHuman rest is an upright A-pose whose torso, neck and clavicle bones do not run along the source's joint
# offsets (the hips bone leans back 35 deg, the neck 60 deg forward: its tail follows the anime head's joint), so aiming
# them along the source's rest directions (motion.calibrate) would bend a standing body. Those bones are calibrated as
# "the same neutral as the source's rest" (Wcal = their rest), and only the limbs, hands and fingers are aimed.
REST_MATCH = ('hips', 'spine', 'chest', 'upperChest', 'neck', 'head', 'leftShoulder', 'rightShoulder')


def calibrate(arm, clip, bone_map=None, keep=REST_MATCH):
    """-> Wcal (armature-space rotations of the armature posed in the clip's rest pose), for motion.bake."""
    bone_map = bone_map or soma_map.BONE_MAP
    J = clip['joints']
    P0 = motion.rest_positions(clip)
    R = motion.rest(arm)
    rot = {b: R[b].copy() for b in keep if b in R}
    aim = {}
    for bone, (j, child) in bone_map.items():
        if bone in rot or bone not in R:
            continue
        d = P0[J.index(child)] - P0[J.index(j)]
        if np.linalg.norm(d) > 1e-6:
            aim[bone] = Vector(d)
    W = motion.solve(arm, rot=rot, aim=aim)
    # the hands turn about their length so the knuckle line (index -> little) matches the source's (palms agree)
    tw = {}
    for bone, (a, b) in soma_map.TWIST_REFS.items():
        side = 'left' if bone.startswith('left') else 'right'
        want = Vector(P0[J.index(b)] - P0[J.index(a)])
        axis = W[bone].col[1].normalized()
        want = (want - axis * want.dot(axis)).normalized()
        across = arm.data.bones[f'{side}LittleProximal'].head_local - arm.data.bones[f'{side}IndexProximal'].head_local
        have = W[bone] @ (R[bone].inverted() @ across)
        have = (have - axis * have.dot(axis)).normalized()
        ang = have.angle(want, 0.0)
        if have.cross(want).dot(axis) < 0:
            ang = -ang
        tw[bone] = Matrix.Rotation(ang, 3, axis) @ W[bone]
    if tw:
        rot.update(tw)
        W = motion.solve(arm, rot=rot, aim={k: v for k, v in aim.items() if k not in rot})
    return W


@contextmanager
def evaluating(keep):
    """frame_set evaluates only `keep` (and armatures/cameras): every other mesh is disabled in the viewport meanwhile."""
    keep = set(o.name for o in keep)
    saved = {}
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name not in keep:
            saved[o.name] = o.hide_viewport
            o.hide_viewport = True
    try:
        yield
    finally:
        for n, h in saved.items():
            bpy.data.objects[n].hide_viewport = h


def lowest(meshes):
    dg = bpy.context.evaluated_depsgraph_get()
    z = 1e9
    for m in meshes:
        ev = m.evaluated_get(dg); me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co)
        mw = np.array(ev.matrix_world)
        z = min(z, float((co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3])[:, 2].min()))
        ev.to_mesh_clear()
    return z


def floor_lock(arm, meshes, contact, start=1, floor=0.0, smooth=2, clearance=0.0):
    """motion.floor_lock over the shoes: on contact frames the lowest point of the (evaluated) shoes is put on the floor,
    interpolated between contacts; then a second pass lifts any frame where a shoe still dips below the floor (a hop's
    landing, a slide between contacts). Rewrites the hips' location keys. -> per-frame lift."""
    sc = bpy.context.scene
    n = len(contact)
    pb = arm.pose.bones['hips']
    Rh = arm.data.bones['hips'].matrix_local.to_3x3()

    def lows():
        out = []
        for i in range(n):
            sc.frame_set(start + i)
            out.append(lowest(meshes))
        return np.array(out)

    def lift(dz):
        for i in range(n):
            sc.frame_set(start + i)
            world = Rh @ pb.location + Vector((0, 0, float(dz[i])))
            pb.location = Rh.inverted() @ world
            pb.keyframe_insert('location', frame=start + i)
    with evaluating(meshes):
        low = lows()
        idx = [i for i in range(n) if contact[i] > 0.5]
        dz = np.interp(np.arange(n), idx, [floor - low[i] for i in idx]) if idx else np.zeros(n)
        if smooth:
            k = np.ones(2 * smooth + 1) / (2 * smooth + 1)
            dz = np.convolve(np.pad(dz, smooth, mode='edge'), k, mode='valid')
        lift(dz)
        low2 = lows()
        under = np.clip(floor + clearance - low2, 0, None)
        if under.max() > 1e-4:
            r = smooth + 1                                          # spread each lift over its neighbours, never less
            up = np.array([under[max(0, i - r):i + r + 1].max() for i in range(n)])
            k = np.ones(2 * r + 1) / (2 * r + 1)
            up = np.maximum(np.convolve(np.pad(up, r, mode='edge'), k, mode='valid'), under)
            lift(up)
            dz = dz + up
        low3 = lows()
    return dz, low3


# ------------------------------------------------------------------------------------------------------------- face
# lids per eye (skin 'eye_<k>_L/R', lash 'eye_<k>', plates 'eye_blink/happy'), brows per side, from a named eye state
EYES = {
    'open': ({}, {}, {}, {}),
    'half': ({'blink': 0.5}, {'blink': 0.5}, {}, {}),                  # the blink's in-betweens
    'closed': ({'blink': 1.0}, {'blink': 1.0}, {}, {}),
    'soft': ({'half': 0.55}, {'half': 0.55}, {'relaxed': 1.0}, {'relaxed': 1.0}),
    'surprised': ({'wide': 1.0}, {'wide': 1.0}, {'surprised': 1.0}, {'surprised': 1.0}),
    'wink': ({'happy': 1.0}, {'squint': 0.35}, {'relaxed': 1.0}, {'raise': 0.5}),     # her left eye shut
    'happy': ({'happy': 1.0}, {'happy': 1.0}, {'relaxed': 1.0}, {'relaxed': 1.0}),
}
# the 2D rig's mouth drawings (engine/moves.js MOVES.lips: openness x rounding) as charkit's viseme keys
MOUTHS = {
    'rest': {}, 'MBP': {'pout': 0.35}, 'S': {'ih': 0.45}, 'Is': {'ih': 0.55, 'ee': 0.2}, 'Ih': {'ih': 0.8, 'ee': 0.25},
    'Eh': {'ee': 0.6, 'aa': 0.35}, 'Am': {'aa': 0.6}, 'A': {'aa': 1.0}, 'A2': {'aa': 1.0}, 'Os': {'oh': 0.65},
    'O': {'oh': 1.0}, 'U': {'ou': 1.0}, 'I': {'ee': 0.9, 'ih': 0.3}, 'E': {'ee': 0.8, 'aa': 0.4}, 'grin': {'grin': 1.0},
}


class Face:
    """keys the charkit face's shape keys as held drawings (CONSTANT), one state per frame."""

    def __init__(self, C):
        self.C = C
        self.skin = C['skin']
        self.side = {'L': C['eyes'][0], 'R': C['eyes'][1]}
        assert C['eyes'][0]['iris'].name.endswith('_L')
        self.mouth_obs = [self.skin] + list(C['mouth'].values())
        self.touched = set()

    def _put(self, ob, name, val, frame):
        kb = ob.data.shape_keys.key_blocks.get(name) if ob.data.shape_keys else None
        if kb is None:
            return
        kb.value = val
        kb.keyframe_insert('value', frame=frame)
        self.touched.add(ob.name)

    def set(self, eyes, mouth, frame):
        eL, eR, bL, bR = EYES[eyes]
        for tag, e, b in (('L', eL, bL), ('R', eR, bR)):
            P = self.side[tag]
            for kb in self.skin.data.shape_keys.key_blocks:
                if kb.name.startswith('eye_') and kb.name.endswith('_' + tag):
                    self._put(self.skin, kb.name, e.get(kb.name[4:-2], 0.0), frame)
            for part in ('lash', 'sclera', 'iris'):
                ob = P[part]
                for kb in ob.data.shape_keys.key_blocks[1:]:
                    if kb.name.startswith('eye_'):
                        self._put(ob, kb.name, e.get(kb.name[4:], 0.0), frame)
            for kb in P['brow'].data.shape_keys.key_blocks[1:]:
                self._put(P['brow'], kb.name, b.get(kb.name[5:], 0.0), frame)
        m = MOUTHS.get(mouth, {})
        for ob in self.mouth_obs:
            for kb in ob.data.shape_keys.key_blocks[1:]:
                if kb.name.startswith('mouth_'):
                    self._put(ob, kb.name, m.get(kb.name[6:], 0.0), frame)

    def hold(self):
        for n in self.touched:
            ob = bpy.data.objects[n]
            ad = ob.data.shape_keys.animation_data
            if ad and ad.action:
                for fc in motion.all_fcurves(ad.action):
                    if 'look_' in fc.data_path:
                        continue
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'CONSTANT'


def head_rotation(arm):
    """the head bone's rotation from rest, world (so rest-aligned head space = R^-1 world)."""
    pb = arm.pose.bones['head']
    Rh = arm.data.bones['head'].matrix_local.to_3x3()
    return (arm.matrix_world @ pb.matrix).to_3x3() @ Rh.inverted(), (arm.matrix_world @ pb.matrix).translation


def look_and_light(C, cam, ldir, frames, start=1, fps=24.0, max_h=0.5, max_v=0.6, lag=0.35):
    """per frame, from the posed head: the eyes into the lens (the camera's yaw and pitch in her head's frame as the iris
    look keys, followed with a little lag: a critically damped follow, stepped on the frame grid) and the face's SDF light
    in head space (charkit.faceshade.set_light, keyed)."""
    from charkit import faceshade, shade
    sc = bpy.context.scene
    arm = C['arm']
    irises = [p['iris'] for p in C['eyes']]
    face_mats = [m for m in shade.MATS.values() if m.node_tree and 'ldir_head' in m.node_tree.nodes]
    cur = None; vel = Vector((0, 0))
    w = 2.0 / max(lag, 1e-3)
    dt = 1.0 / fps
    log = []
    with evaluating([]):
        for i in range(frames):
            f = start + i
            sc.frame_set(f)
            R, hp = head_rotation(arm)
            v = R.inverted() @ (cam.matrix_world.translation - hp)
            yaw = math.atan2(v.x, -v.y); pitch = math.atan2(v.z, math.hypot(v.x, v.y))
            tgt = Vector((max(-1.0, min(1.0, yaw / math.radians(50))) * max_h,
                          max(-1.0, min(1.0, pitch / math.radians(35))) * max_v))
            if cur is None:
                cur = tgt.copy()
            acc = (tgt - cur) * w * w - vel * 2 * w
            vel = vel + acc * dt; cur = cur + vel * dt
            vals = {'look_left': max(0.0, cur.x), 'look_right': max(0.0, -cur.x),
                    'look_up': max(0.0, cur.y), 'look_down': max(0.0, -cur.y)}
            for ob in irises:
                for k, val in vals.items():
                    kb = ob.data.shape_keys.key_blocks[k]
                    kb.value = val; kb.keyframe_insert('value', frame=f)
            faceshade.set_light(ldir, np.array(R))
            for m in face_mats:
                nd = m.node_tree.nodes['ldir_head']
                for k in range(3):
                    nd.inputs[k].keyframe_insert('default_value', frame=f)
            log.append((f, math.degrees(yaw), math.degrees(pitch), tuple(np.array(R).T @ np.asarray(ldir))))
    return log


# --------------------------------------------------------------------------------------------------------- shading
def set_light(d):
    """the world key light on every toon material ('ldir'), charkit's and the kit's."""
    v = Vector(d).normalized()
    for m in bpy.data.materials:
        if m.node_tree and 'ldir' in m.node_tree.nodes:
            for i in range(3):
                m.node_tree.nodes['ldir'].inputs[i].default_value = v[i]
    return v


def set_rim(color, amt):
    """re-tint charkit's toon rims (its toon3's SCREEN mix; the rim strength is the MULTIPLY fed by the LayerWeight map),
    keeping materials designed without a rim (the generated hair) rimless."""
    from charkit import shade
    for m in bpy.data.materials:
        nt = m.node_tree
        if not nt:
            continue
        for n in nt.nodes:
            if n.type == 'MIX' and getattr(n, 'blend_type', '') == 'SCREEN' and n.data_type == 'RGBA':
                n.inputs['B'].default_value = (*shade.lin(color), 1)
            if n.type == 'MATH' and n.operation == 'MULTIPLY' and n.inputs[0].links and \
                    n.inputs[0].links[0].from_node.type == 'MAP_RANGE' and n.inputs[0].links[0].from_node.inputs['Value'].links \
                    and n.inputs[0].links[0].from_node.inputs['Value'].links[0].from_node.type == 'LAYER_WEIGHT':
                if n.inputs[1].default_value > 0:
                    n.inputs[1].default_value = amt


def aux_material(name, flatten=None):
    """dance_test's line-pass material (camera-space normal x, y and depth/12 as emission) with the normal flattened toward
    the camera: flatten 'all' (constant: only depth jumps draw inner lines; for the generated hair, whose noisy clumps
    otherwise scribble lines all over it) or a point attribute's name (the skin's 'face_mask': no nose, cheek or lip creases
    on the anime face; the jaw over the neck still draws, by depth)."""
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    N, L = nt.nodes.new, nt.links.new
    out = N('ShaderNodeOutputMaterial'); em = N('ShaderNodeEmission'); geo = N('ShaderNodeNewGeometry')
    vt = N('ShaderNodeVectorTransform'); vt.vector_type = 'NORMAL'; vt.convert_from = 'WORLD'; vt.convert_to = 'CAMERA'
    L(geo.outputs['Normal'], vt.inputs[0])
    sep = N('ShaderNodeSeparateXYZ'); L(vt.outputs[0], sep.inputs[0])
    cam = N('ShaderNodeCameraData')
    dz = N('ShaderNodeMath'); dz.operation = 'DIVIDE'; dz.inputs[1].default_value = 12.0; L(cam.outputs['View Z Depth'], dz.inputs[0])
    c = N('ShaderNodeCombineColor'); L(dz.outputs[0], c.inputs[2])
    keep = None
    if flatten and flatten != 'all':
        at = N('ShaderNodeAttribute'); at.attribute_name = flatten; at.attribute_type = 'GEOMETRY'
        keep = N('ShaderNodeMath'); keep.operation = 'SUBTRACT'; keep.inputs[0].default_value = 1.0; keep.use_clamp = True
        L(at.outputs['Fac'], keep.inputs[1])
    for i, ax in enumerate(('X', 'Y')):
        if flatten == 'all':
            c.inputs[i].default_value = 0.5
            continue
        src = sep.outputs[ax]
        if keep is not None:
            mul = N('ShaderNodeMath'); mul.operation = 'MULTIPLY'; L(src, mul.inputs[0]); L(keep.outputs[0], mul.inputs[1])
            src = mul.outputs[0]
        r = N('ShaderNodeMath'); r.operation = 'MULTIPLY_ADD'; r.inputs[1].default_value = 0.5; r.inputs[2].default_value = 0.5
        L(src, r.inputs[0]); L(r.outputs[0], c.inputs[i])
    L(c.outputs[0], em.inputs['Color']); L(em.outputs[0], out.inputs['Surface'])
    return m


def aux_flatten(S):
    """after dance_test.aux_pass: the hair drawn with flat normals, the face with its normals flattened by its mask."""
    flat, face = aux_material('aux_flat', 'all'), aux_material('aux_face', 'face_mask')
    for o in S.hair:
        for i in range(len(o.data.materials)):
            o.data.materials[i] = flat
    sk = S.character['skin']
    for i, m in enumerate(sk.data.materials):
        if m and m.name.startswith('aux_normal_depth'):
            sk.data.materials[i] = face


def features_pass(sc, S):
    """the eyes and brows with the hair hidden and everything else held out, so post can show them through the bangs
    (never through a hand). -> undo()"""
    feats = set(o.name for o in S.features)
    hair = [o for o in S.hair]
    hold = bpy.data.collections.new('holdout'); sc.collection.children.link(hold)
    moved = []
    for o in list(sc.collection.objects):
        if o.type != 'MESH' or o.name in feats or o in hair:
            continue
        sc.collection.objects.unlink(o); hold.objects.link(o); moved.append(o)
    bpy.context.view_layer.layer_collection.children['holdout'].holdout = True
    was_hidden = {o: o.hide_render for o in hair}
    for o in hair:
        o.hide_render = True
    was_t = sc.render.film_transparent; sc.render.film_transparent = True
    sc.render.image_settings.color_mode = 'RGBA'

    def undo():
        for o in moved:
            hold.objects.unlink(o); sc.collection.objects.link(o)
        bpy.data.collections.remove(hold)
        for o, h in was_hidden.items():
            o.hide_render = h
        sc.render.film_transparent = was_t; sc.render.image_settings.color_mode = 'RGB'
    return undo
