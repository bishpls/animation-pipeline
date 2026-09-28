"""Posing: IK arms (to weapon grips) and legs (to foot targets), FK spine/head, drawn-face swaps,
all keyed per frame with CONSTANT interpolation (anime stepping on twos/threes)."""
import bpy, math
from mathutils import Vector, Euler, Quaternion, Matrix
import char as CH

D2R = math.pi / 180


def empty(name, size=0.05):
    e = bpy.data.objects.new(name, None); e.empty_display_size = size
    bpy.context.scene.collection.objects.link(e)
    return e


def setup_ik(ch):
    arm = ch['arm']
    T = {}
    for s in 'LR':
        T[f'hand.{s}'] = empty(f'ik_hand.{s}'); T[f'elbow.{s}'] = empty(f'pole_elbow.{s}')
        T[f'foot.{s}'] = empty(f'ik_foot.{s}'); T[f'knee.{s}'] = empty(f'pole_knee.{s}')
        pb = arm.pose.bones[f'forearm.{s}']
        c = pb.constraints.new('IK'); c.target = T[f'hand.{s}']; c.pole_target = T[f'elbow.{s}']; c.chain_count = 2
        c.pole_angle = -math.pi / 2 if s == 'L' else -math.pi / 2
        pb = arm.pose.bones[f'shin.{s}']
        c = pb.constraints.new('IK'); c.target = T[f'foot.{s}']; c.pole_target = T[f'knee.{s}']; c.chain_count = 2
        c.pole_angle = -math.pi / 2
    ch['T'] = T
    # weapon grips as children of the weapon root (butt at origin, shaft along +Z)
    return T


# ---------------------------------------------------------------- pose model
# A pose is a dict in the CHARACTER frame: x = her right... we use: fwd = facing direction, right = fwd x up.
# keys: root (world xyz of pelvis), yaw (deg, 0 = facing -Y), hips (pitch, roll, yaw deg: whole-body tilt),
#       spine/chest (lean fwd deg, side deg, twist deg), head (nod, tilt, turn), feet L/R (char-frame xyz rel root, or world if 'feetW'),
#       weapon: grip point (char-frame rel chest), direction (az, el deg in char frame), roll deg; g1/g2 grip params; two-handed;
#       handL free target (char-frame rel chest) when one-handed; expr; unfold 0..1.
P0 = dict(root=(0, 0, 0.9), yaw=0.0, hips=(0, 0, 0), spine=(4, 0, 0), chest=(4, 0, 0), neck=(0, 0, 0), head=(0, 0, 0),
          footL=(0.1, 0.02, -0.86), footR=(-0.1, 0.02, -0.86), kneeL=(0.1, 0.5, -0.45), kneeR=(-0.1, 0.5, -0.45),
          wpos=(0.18, 0.28, -0.15), waz=90.0, wel=70.0, wroll=0.0, g1=0.35, g2=0.62, two=1.0,
          handL=(0.2, 0.15, -0.35), handR=(-0.2, 0.15, -0.35), elbowL=(0.5, -0.3, -0.2), elbowR=(-0.5, -0.3, -0.2),
          held=1.0, gfeet=1.0, liftL=0.0, liftR=0.0, ground=0.0, expr='neutral', extend=1.0, bopen=1.0, cloakwind=1.0)


def frame_axes(yaw):
    a = yaw * D2R
    fwd = Vector((math.sin(a), -math.cos(a), 0))       # yaw 0 -> facing -Y
    right = fwd.cross(Vector((0, 0, 1)))                # her right
    return fwd, right, Vector((0, 0, 1))


def cf(v, yaw, origin):
    """char-frame (right, fwd, up) -> world"""
    f, r, u = frame_axes(yaw)
    return Vector(origin) + r * v[0] + f * v[1] + u * v[2]


def cfl(v, yaw, origin):
    """limb targets are authored with +x = HER LEFT (L side); the weapon frame keeps +x = her right"""
    return cf((-v[0], v[1], v[2]), yaw, origin)


def apply_pose(ch, p, frame):
    arm, T = ch['arm'], ch['T']
    yaw = p['yaw']
    root = Vector(p['root'])
    arm.rotation_mode = 'XYZ'
    arm.rotation_euler = (0, 0, yaw * D2R)
    arm.location = root - Vector((0, 0, 0.90))
    PB = arm.pose.bones
    def rot(b, e, order='XYZ'):
        PB[b].rotation_mode = 'XYZ'
        PB[b].rotation_euler = Euler((e[0] * D2R, e[1] * D2R, e[2] * D2R), order)
    # hips: whole-body pitch(+ = forward flip), roll(side), yaw(twist of pelvis)
    rot('hips', (p['hips'][0], p['hips'][2], -p['hips'][1]))
    rot('spine', (p['spine'][0], p['spine'][2], -p['spine'][1]))
    rot('chest', (p['chest'][0], p['chest'][2], -p['chest'][1]))
    rot('neck', (p['neck'][0], p['neck'][2], -p['neck'][1]))
    rot('head', (p['head'][0], p['head'][2], -p['head'][1]))
    bpy.context.view_layer.update()
    chest_w = arm.matrix_world @ PB['chest'].tail
    pelvis_w = arm.matrix_world @ PB['hips'].head
    # weapon
    w = ch['weapon']
    held = p['held']
    f, r, u = frame_axes(yaw)
    az, el = p['waz'] * D2R, p['wel'] * D2R
    wdir_c = Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))   # char frame: x right, y fwd
    wdir = (r * wdir_c.x + f * wdir_c.y + u * wdir_c.z).normalized()
    grip = cf(p['wpos'], yaw, chest_w)
    L = CH.weapon_length(p['extend'])
    CH.set_weapon_state(ch['weapon'], p['extend'], p['bopen'])
    butt = grip - wdir * p['g1'] * L
    if held < 0.5:        # stowed across the back
        wdir = (u * 0.62 + r * 0.78 - f * 0.06).normalized()      # diagonal across the back, head over her right shoulder
        butt = cf((-0.2, -0.17, -0.36), yaw, chest_w)
    w.rotation_mode = 'QUATERNION'
    # blade points along +X of the weapon's local frame; roll it with wroll around the shaft
    q = wdir.to_track_quat('Z', 'X')
    q = q @ Quaternion((0, 0, 1), p['wroll'] * D2R)
    w.rotation_quaternion = q
    w.location = butt
    # hands
    gR = butt + wdir * p['g1'] * L
    gL = butt + wdir * p['g2'] * L
    hR = gR if held >= 0.5 else cfl(p['handR'], yaw, chest_w)
    hL = gL if (held >= 0.5 and p['two'] >= 0.5) else cfl(p['handL'], yaw, chest_w)
    T['hand.R'].location = hR
    T['hand.L'].location = hL
    T['elbow.R'].location = cfl(p['elbowR'], yaw, chest_w)
    T['elbow.L'].location = cfl(p['elbowL'], yaw, chest_w)
    # feet (char frame relative to root, unless world-locked)
    for s in 'LR':
        fp = p.get('footW' + s)
        ft = Vector(fp) if fp else cfl(p['foot' + s], yaw, root)
        if not fp and p['gfeet'] >= 0.5:           # grounded: foot z is world height above the snow, not root-relative
            ft.z = p['ground'] + 0.04 + p['lift' + s]
        T['foot.' + s].location = ft
        T['knee.' + s].location = cfl(p['knee' + s], yaw, root)
    # expression
    for k, o in ch['decals'].items():
        o.hide_render = k != p['expr']
    bpy.context.view_layer.update()
    return dict(chest=chest_w, pelvis=pelvis_w, gR=gR, gL=gL, butt=butt, wdir=wdir, head=arm.matrix_world @ PB['head'].head,
                tip=bpy.data.objects['w_tip'].matrix_world.translation.copy(),
                muzzle=bpy.data.objects['w_muzzle'].matrix_world.translation.copy())


def key_all(ch, frame, interp='CONSTANT'):
    arm, T = ch['arm'], ch['T']
    arm.keyframe_insert('location', frame=frame); arm.keyframe_insert('rotation_euler', frame=frame)
    for b in ('hips', 'spine', 'chest', 'neck', 'head'):
        arm.pose.bones[b].keyframe_insert('rotation_euler', frame=frame)
    for e in T.values():
        e.keyframe_insert('location', frame=frame)
    w = ch['weapon']
    w.keyframe_insert('location', frame=frame); w.keyframe_insert('rotation_quaternion', frame=frame)
    for n in w['segs']:
        bpy.data.objects[n].keyframe_insert('location', frame=frame)
    bpy.data.objects['w_hinge'].keyframe_insert('rotation_euler', frame=frame)
    for o in ch['decals'].values():
        o.keyframe_insert('hide_render', frame=frame)


def set_interp(objs, kind='CONSTANT'):
    for o in objs:
        ad = o.animation_data
        if not ad or not ad.action:
            continue
        for fc in getattr(ad.action, 'fcurves', []):
            for kp in fc.keyframe_points:
                kp.interpolation = kind


def all_fcurves(o):
    ad = o.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    if hasattr(act, 'fcurves') and len(act.fcurves):
        return list(act.fcurves)
    out = []
    for layer in getattr(act, 'layers', []):
        for strip in layer.strips:
            for cb in strip.channelbags:
                out += list(cb.fcurves)
    return out


def step_keys(objs):
    for o in objs:
        for fc in all_fcurves(o):
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'


# ---------------------------------------------------------------- pose tracks with easing
def ease(kind, u):
    u = max(0.0, min(1.0, u))
    if kind == 'lin': return u
    if kind == 'io': return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2
    if kind == 'out': return 1 - (1 - u) ** 3
    if kind == 'outx': return 1 - (1 - u) ** 5
    if kind == 'in': return u ** 3
    if kind == 'in2': return u * u
    if kind == 'back': return 1 + 2.7 * (u - 1) ** 3 + 1.7 * (u - 1) ** 2
    if kind == 'step': return 0.0 if u < 1 else 1.0
    return u


def mixv(a, b, u):
    if isinstance(a, str):
        return b if u >= 0.5 else a
    if isinstance(a, (tuple, list)):
        return tuple(x + (y - x) * u for x, y in zip(a, b))
    return a + (b - a) * u


class Track:
    """keys: list of (t_seconds, pose-dict-overrides, ease). eval(t) -> full pose."""
    def __init__(self, base=None):
        self.base = dict(P0, **(base or {}))
        self.keys = []
        self.layers = []

    def layer(self, t0, t1, fn, fade_in=0.08, fade_out=0.08):
        """procedural override (cycles): fn(t) -> dict of params, blended in/out over the fades"""
        self.layers.append((t0, t1, fn, fade_in, fade_out)); return self

    def key(self, t, ez='io', **kw):
        self.keys.append((t, kw, ez))
        self.keys.sort(key=lambda k: k[0])
        return self

    def eval(self, t):
        p = dict(self.base)
        # per-parameter: find surrounding keys that set this parameter
        params = set(p.keys()) | {k for _, kw, _ in self.keys for k in kw}
        for prm in params:
            ks = [(tk, kw[prm], ez) for tk, kw, ez in self.keys if prm in kw]
            if not ks:
                continue
            if t <= ks[0][0]:
                p[prm] = ks[0][1]; continue
            if t >= ks[-1][0]:
                p[prm] = ks[-1][1]; continue
            for i in range(1, len(ks)):
                if t < ks[i][0]:
                    t0, v0, _ = ks[i - 1]; t1, v1, ez = ks[i]
                    p[prm] = mixv(v0, v1, ease(ez, (t - t0) / (t1 - t0)))
                    break
        for (t0, t1, fn, fi, fo) in self.layers:
            if t0 - 1e-6 <= t <= t1 + 1e-6:
                w = min(1.0, (t - t0) / fi if fi > 0 else 1.0, (t1 - t) / fo if fo > 0 else 1.0)
                w = ease('io', w)
                for k, v in fn(t).items():
                    p[k] = mixv(p[k], v, w) if not isinstance(v, str) else v
        return p


# ---------------------------------------------------------------- locomotion cycles
def sprint(path, v=7.0, hz=1.65, root_z=0.82, lean=26.0, lift=0.42, stance=0.3, phase0=0.0):
    """Anime sprint on a path.  path(t) -> ((x, y), yaw_deg).  Feet are planted (no slide) when the path speed ~= v.
    Returns fn(t) -> pose overrides for Track.layer."""
    span = v / hz * stance / 2
    def foot(ph):
        ph %= 1.0
        if ph < stance:
            u = ph / stance
            return span - 2 * span * u, 0.0
        u = (ph - stance) / (1 - stance)
        y = -span + 2 * span * ease('io', u) - 0.32 * math.sin(math.pi * min(1.0, u * 1.4))     # heel kicks back first
        z = lift * math.sin(math.pi * u ** 0.75) ** 1.2
        return y, z
    def fn(t):
        ph = phase0 + t * hz
        (x, y), yaw = path(t)
        yL, zL = foot(ph); yR, zR = foot(ph + 0.5)
        bob = 0.035 * math.cos(4 * math.pi * (ph - stance * 0.5 - 0.25))
        tw = 9 * math.sin(2 * math.pi * ph)
        return dict(root=(x, y, root_z + bob), yaw=yaw, footL=(0.11, yL, -0.8), footR=(-0.11, yR, -0.8), liftL=zL, liftR=zR,
                    kneeL=(0.12, 1.0, -0.3), kneeR=(-0.12, 1.0, -0.3), hips=(4, 0, tw), spine=(lean * 0.6, 0, -tw * 0.5),
                    chest=(lean * 0.4, 0, -tw * 0.7), head=(-lean * 0.7, 0, tw * 0.3))
    return fn


def line_path(p0, p1, t0, t1, yaw=None):
    """straight constant-speed path between two ground points over [t0, t1]; yaw faces the travel direction"""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    yw = yaw if yaw is not None else math.degrees(math.atan2(dx, -dy))
    def f(t):
        u = (t - t0) / (t1 - t0)
        return (p0[0] + dx * u, p0[1] + dy * u), yw
    return f
