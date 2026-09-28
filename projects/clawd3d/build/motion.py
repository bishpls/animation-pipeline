"""Posing and retargeting on a Blender armature, computed in armature space and written as pose-bone rotations.

A pose is given as desired armature-space rotations W[bone] (3x3), or as aim directions for a bone's +Y (its length axis);
bones not given follow their parent rigidly. solve() walks the hierarchy once and converts to local rotations:
    basis_b = Rrest_b^-1 . Rrest_p . W_p^-1 . W_b          (root: Rrest_b^-1 . W_b)
so no depsgraph update is needed per bone. retarget() applies a canonical clip (docs/PIPELINE_3D.md §2) through a
calibration in the source's rest pose (see calibrate()).
"""
import math
import numpy as np
import bpy
from mathutils import Matrix, Quaternion, Vector


def order(arm):
    """bones parents-first."""
    out, seen = [], set()

    def visit(b):
        if b.name in seen:
            return
        if b.parent:
            visit(b.parent)
        seen.add(b.name); out.append(b)
    for b in arm.data.bones:
        visit(b)
    return out


def rest(arm):
    return {b.name: b.matrix_local.to_3x3() for b in arm.data.bones}


def swing(a, b):
    """the shortest rotation taking direction a to direction b."""
    return Vector(a).normalized().rotation_difference(Vector(b).normalized()).to_matrix()


def solve(arm, rot=None, aim=None):
    """-> {bone: armature-space 3x3} for the whole rig. rot: {bone: 3x3}; aim: {bone: direction for the bone's +Y}."""
    rot, aim = rot or {}, aim or {}
    R = rest(arm)
    W = {}
    for b in order(arm):
        n = b.name
        if n in rot:
            W[n] = rot[n]
            continue
        base = (W[b.parent.name] @ R[b.parent.name].inverted() @ R[n]) if b.parent else R[n].copy()
        if n in aim:
            base = swing(base.col[1], aim[n]) @ base
        W[n] = base
    return W


def apply(arm, W, frame=None, root_loc=None, root='hips'):
    """write W (armature-space rotations) as pose rotations; optional root head position (armature space)."""
    R = rest(arm)
    for b in order(arm):
        n = b.name
        if n not in W:
            continue
        pb = arm.pose.bones[n]
        if b.parent and b.parent.name in W:
            local = R[n].inverted() @ R[b.parent.name] @ W[b.parent.name].inverted() @ W[n]
        else:
            local = R[n].inverted() @ W[n]
        q = local.to_quaternion()
        if pb.rotation_quaternion.dot(q) < 0:              # hemisphere continuity for interpolation
            q.negate()
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = q
        if frame is not None:
            pb.keyframe_insert('rotation_quaternion', frame=frame)
    if root_loc is not None:
        b = arm.data.bones[root]
        pb = arm.pose.bones[root]
        pb.location = R[root].inverted() @ (Vector(root_loc) - b.head_local)
        if frame is not None:
            pb.keyframe_insert('location', frame=frame)


def reset(arm):
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = Quaternion(); pb.location = Vector()


# ---------------------------------------------------------------- canonical clips (SOMA, Y-up) -> this armature
YUP_TO_ZUP = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))       # Rx(+90): glTF Y-up, facing +Z -> Blender Z-up, facing -Y


def quat_to_mat(q):
    """(..., 4) w,x,y,z -> (..., 3, 3)"""
    w, x, y, z = np.moveaxis(q, -1, 0)
    return np.stack([np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], -1),
                     np.stack([2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], -1),
                     np.stack([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)], -1)], -2)


def load_clip(path):
    d = np.load(path, allow_pickle=False)
    clip = {k: d[k] for k in d.files}
    clip['joints'] = [str(j) for j in clip['joints']]
    return clip


def fk(clip):
    """-> world rotations (T,J,3,3) and positions (T,J,3), both Z-up (Blender), metres."""
    rot = quat_to_mat(clip['rot'].astype(np.float64))
    par, off, root = clip['parents'], clip['offsets'].astype(np.float64), clip['root'].astype(np.float64)
    T, J = rot.shape[:2]
    G = np.zeros((T, J, 3, 3)); Pw = np.zeros((T, J, 3))
    for j in range(J):
        p = par[j]
        if p < 0:
            G[:, j] = rot[:, j]; Pw[:, j] = root                 # the clip's root is the root joint's world position
        else:
            G[:, j] = G[:, p] @ rot[:, j]
            Pw[:, j] = Pw[:, p] + np.einsum('tab,b->ta', G[:, p], off[j])
    C = np.array(YUP_TO_ZUP)
    return C @ G @ C.T, Pw @ C.T


def rest_positions(clip):
    J = clip['joints']
    _, P0 = fk({**clip, 'rot': np.tile(np.array([1.0, 0, 0, 0]), (1, len(J), 1)), 'root': np.zeros((1, 3))})
    return P0[0]


def calibrate(arm, clip, bone_map, twist_refs=None, target_twist=None):
    """Pose the armature into the clip's rest pose by aiming each mapped bone along its source bone's rest direction (the
    rest skeleton's child offset), and return that pose's armature-space rotations: the calibration Wcal[bone].
    bone_map: {bone: (source joint, source child joint for the direction)}.
    twist_refs: {bone: (source joint a, source joint b)}: also turn the bone about its length so its own +X (per
    target_twist[bone], a function of the armature giving the bone's rest across vector) matches the source's a->b across
    direction (hands: the knuckle line), so palms and curls agree."""
    J = clip['joints']
    P0 = rest_positions(clip)
    aim = {}
    for bone, (j, child) in bone_map.items():
        d = P0[J.index(child)] - P0[J.index(j)]
        if np.linalg.norm(d) > 1e-6:
            aim[bone] = Vector(d)
    W = solve(arm, aim=aim)
    if twist_refs:
        R = rest(arm)
        rot = {}
        for bone in order(arm):
            n = bone.name
            if n not in twist_refs:
                continue
            a, b = twist_refs[n]
            want = Vector(P0[J.index(b)] - P0[J.index(a)])
            axis = W[n].col[1].normalized()
            want = (want - axis * want.dot(axis)).normalized()
            have = W[n] @ (R[n].inverted() @ target_twist[n](arm))
            have = (have - axis * have.dot(axis)).normalized()
            ang = have.angle(want, 0.0)
            if have.cross(want).dot(axis) < 0:
                ang = -ang
            rot[n] = Matrix.Rotation(ang, 3, axis) @ W[n]
        if rot:
            W = solve(arm, rot=rot, aim={k: v for k, v in aim.items() if k not in rot})
    return W


def retarget(arm, clip, bone_map, frames, fps_out=24.0, start=1, root_joint=None, height_scale=1.0,
             every=1, interp='LINEAR', Wcal=None):
    """Key the armature from a clip: W_b(t) = G_src(t) . Wcal_b (source rest rotations are identity by the clip
    format), with the root head at the source root's world position scaled by height_scale.
    frames: output frame count; the clip is resampled from its own fps. every=2 keys on twos (CONSTANT for held drawings)."""
    G, Pw = fk(clip)
    Wcal = Wcal or calibrate(arm, clip, bone_map)
    J = clip['joints']
    src_fps = float(clip['fps'])
    rj = J.index(root_joint) if root_joint else 0
    root0 = Pw[0, rj].copy(); root0[2] = 0.0                      # keep the first frame's ground position
    hips_rest = arm.data.bones['hips'].head_local
    for i in range(0, frames, every):
        t = i / fps_out
        s = min(t * src_fps, len(G) - 1.0)
        k0 = int(math.floor(s)); k1 = min(k0 + 1, len(G) - 1); a = s - k0
        rot = {}
        for bone, (j, _) in bone_map.items():
            ji = J.index(j)
            q0 = Matrix(G[k0, ji].tolist()).to_quaternion(); q1 = Matrix(G[k1, ji].tolist()).to_quaternion()
            if q0.dot(q1) < 0:
                q1.negate()
            g = q0.slerp(q1, a).to_matrix()
            rot[bone] = g @ Wcal[bone]
        W = solve(arm, rot=rot)
        p = (1 - a) * Pw[k0, rj] + a * Pw[k1, rj]
        loc = Vector(((p[0] - root0[0]) * height_scale, (p[1] - root0[1]) * height_scale, p[2] * height_scale))
        loc = Vector((hips_rest.x + loc.x, hips_rest.y + loc.y, loc.z))
        apply(arm, W, frame=start + i, root_loc=loc)
    if interp:
        act = arm.animation_data.action
        for fc in all_fcurves(act):
            for kp in fc.keyframe_points:
                kp.interpolation = interp


class Sampler:
    """A clip's world rotations and root, sampled at any source time (slerp between frames)."""

    def __init__(self, clip):
        self.clip = clip
        self.G, self.P = fk(clip)
        self.fps = float(clip['fps'])
        self.J = clip['joints']
        self.n = len(self.G)

    def at(self, t, joints):
        s = min(max(t * self.fps, 0.0), self.n - 1.0)
        k0 = int(math.floor(s)); k1 = min(k0 + 1, self.n - 1); a = s - k0
        out = {}
        for j in joints:
            ji = self.J.index(j)
            q0 = Matrix(self.G[k0, ji].tolist()).to_quaternion(); q1 = Matrix(self.G[k1, ji].tolist()).to_quaternion()
            if q0.dot(q1) < 0:
                q1.negate()
            out[j] = q0.slerp(q1, a)
        root = (1 - a) * self.P[k0, 0] + a * self.P[k1, 0]
        return out, Vector(root.tolist())


def warp(anchors):
    """'src:bar,src:bar,...' -> fn(bar) -> source seconds (piecewise linear, extrapolated at the ends)."""
    pts = sorted((float(b), float(s)) for s, b in (p.split(':') for p in anchors.split(',')))
    def f(bar):
        if bar <= pts[0][0]:
            (b0, s0), (b1, s1) = pts[0], pts[1]
        elif bar >= pts[-1][0]:
            (b0, s0), (b1, s1) = pts[-2], pts[-1]
        else:
            i = next(i for i in range(len(pts) - 1) if pts[i][0] <= bar <= pts[i + 1][0])
            (b0, s0), (b1, s1) = pts[i], pts[i + 1]
        return s0 + (bar - b0) * (s1 - s0) / (b1 - b0) if b1 != b0 else s0
    return f


def bake(arm, poses, bone_map, Wcal, height_scale, start=1, springs=None, fps=24.0):
    """poses: list of ({source joint: Quaternion world rotation}, root Vector (Z-up, metres)) per output frame.
    springs: {bone: (stiffness, damping, limit_deg)} for helper bones (hair, skirt) whose rotation lags their parent's
    like a damped spring (secondary motion), stepped on the frame grid from the first frame so every frame is repeatable."""
    hips_rest = arm.data.bones['hips'].head_local
    R = rest(arm)
    sim = {}
    dt = 1.0 / fps
    for i, (G, root) in enumerate(poses):
        rot = {bone: G[j].to_matrix() @ Wcal[bone] for bone, (j, _) in bone_map.items() if j in G}
        W = solve(arm, rot=rot)
        for bone, (k, c, lim) in (springs or {}).items():
            b = arm.data.bones[bone]
            target = (W[b.parent.name] @ R[b.parent.name].inverted() @ R[bone]).to_quaternion()
            if bone not in sim:
                sim[bone] = [target.copy(), Vector((0, 0, 0))]
            q, w = sim[bone]
            for _ in range(4):                                        # substeps
                err = (target @ q.inverted())
                if err.w < 0:
                    err.negate()
                axis, ang = err.to_axis_angle()
                e = Vector(axis) * ang
                w = w + (e * k - w * c) * (dt / 4)
                if w.length > 1e-9:
                    q = Quaternion(w.normalized(), w.length * dt / 4) @ q
            err = (q @ target.inverted())
            if err.w < 0:
                err.negate()
            axis, ang = err.to_axis_angle()
            if ang > math.radians(lim):
                q = Quaternion(axis, math.radians(lim)) @ target
            sim[bone] = [q, w]
            rot[bone] = q.to_matrix()
        if springs:
            W = solve(arm, rot=rot)
        loc = Vector((hips_rest.x + root.x * height_scale, hips_rest.y + root.y * height_scale, root.z * height_scale))
        apply(arm, W, frame=start + i, root_loc=loc)


def floor_lock(arm, mesh, contact, start=1, floor=0.0, sole_below=0.03, smooth=2):
    """Keep planted feet on the floor: per frame, the lowest sole vertex of `mesh` (vertices within sole_below of the
    rest floor) is found on the deformed mesh; on frames with a foot in contact (contact[i] > 0.5) the root is shifted so
    that sole touches the floor; between contacts the shift is interpolated (hops keep their height). Rewrites the hips'
    location keys."""
    sc = bpy.context.scene
    soles = [v.index for v in mesh.data.vertices if (mesh.matrix_world @ v.co).z < floor + sole_below]
    n = len(contact)
    low = []
    for i in range(n):
        sc.frame_set(start + i)
        dg = bpy.context.evaluated_depsgraph_get()
        ev = mesh.evaluated_get(dg); me = ev.to_mesh()
        mw = ev.matrix_world
        low.append(min((mw @ me.vertices[k].co).z for k in soles))
        ev.to_mesh_clear()
    idx = [i for i in range(n) if contact[i] > 0.5]
    if not idx:
        return
    dz = np.interp(np.arange(n), idx, [floor - low[i] for i in idx])
    if smooth:
        k = np.ones(2 * smooth + 1) / (2 * smooth + 1)
        dz = np.convolve(np.pad(dz, smooth, mode='edge'), k, mode='valid')
    pb = arm.pose.bones['hips']
    R = arm.data.bones['hips'].matrix_local.to_3x3()
    for i in range(n):
        sc.frame_set(start + i)
        world = R @ pb.location + Vector((0, 0, float(dz[i])))
        pb.location = R.inverted() @ world
        pb.keyframe_insert('location', frame=start + i)
    return dz


def all_fcurves(action):
    """Blender 5.x: F-curves live in channelbags under layers/strips."""
    out = []
    for layer in getattr(action, 'layers', []):
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out
