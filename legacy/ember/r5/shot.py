"""Shot framework: scene reset, character + IK + cloth, pose track keyed on twos, camera track on ones,
wolves, render to frames/<shot>/f####.png (GLOBAL frame numbers) and per-frame meta for the 2D compositor."""
import bpy, math, os, sys, json, time
from mathutils import Vector, Quaternion
from bpy_extras.object_utils import world_to_camera_view
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import char as CH, rig as R, world as WD, cloak as CK

FPS, BEAT = 24, 0.4
bf = lambda b: int(round(b * BEAT * FPS))          # beat -> global frame
bt = lambda b: b * BEAT                            # beat -> seconds


def ease(kind, u):
    return R.ease(kind, u)


class CamTrack:
    """keys: (beat, dict(eye, tgt, lens, roll)); interpolated with easing, evaluated on ones."""
    def __init__(self):
        self.keys = []

    def key(self, b, ez='io', **kw):
        self.keys.append((b, kw, ez)); self.keys.sort(key=lambda k: k[0]); return self

    def eval(self, b):
        out = {}
        prms = {k for _, kw, _ in self.keys for k in kw}
        for prm in prms:
            ks = [(bb, kw[prm], ez) for bb, kw, ez in self.keys if prm in kw]
            if b <= ks[0][0]: out[prm] = ks[0][1]; continue
            if b >= ks[-1][0]: out[prm] = ks[-1][1]; continue
            for i in range(1, len(ks)):
                if b < ks[i][0]:
                    b0, v0, _ = ks[i - 1]; b1, v1, ez = ks[i]
                    out[prm] = R.mixv(v0, v1, ease(ez, (b - b0) / (b1 - b0))); break
        return out


class Shot:
    def __init__(self, name, b0, b1, pct=100, samples=12, light=(0.45, -0.55, 0.7), fog=None, preroll=24):
        self.name, self.b0, self.b1 = name, b0, b1
        self.f0, self.f1 = bf(b0), bf(b1)
        self.preroll = preroll
        bpy.ops.wm.read_factory_settings(use_empty=True)
        CH.MATS.clear()
        CH.setup_render(pct=pct, samples=samples)
        sc = bpy.context.scene
        sc.frame_start, sc.frame_end = self.f0, self.f1 - 1
        sc.render.image_settings.file_format = 'PNG'
        CH.LDIR = tuple(Vector(light).normalized())
        if fog:
            CH.FOG.update(fog)
        self.cam = CH.camera('cam', 35)
        self.cam.data.clip_end = 2000
        self.ct = CamTrack()
        self.ch = None
        self.track = None
        self.step = 2
        self.wolves = []        # (parts, fn(t)->kin.Wolf or None)
        self.meta_fns = {}      # name -> fn(t) -> world point
        self.events = []        # (beat, kind, data)
        self.per_frame = []     # callbacks f(t, frame)
        self.trail_on = None    # fn(beat) -> bool: sample the blade's continuous sweep for smears

    # ---------------------------------------------------------------- building blocks
    def character(self, cloth=True, wind=(1.0, 0.3), base=None):
        self.ch = CH.build_character(with_cloak=True)
        R.setup_ik(self.ch)
        self.track = R.Track(base or {})
        self.cloth = cloth
        self.wind = wind
        return self.ch

    def probe(self, b):
        """evaluate the pose track at beat b and return world points (chest, gR, gL, butt, wdir, head, tip, muzzle, hinge)"""
        info = R.apply_pose(self.ch, self.track.eval(bt(b)), None)
        info['hinge'] = bpy.data.objects['w_hinge'].matrix_world.translation.copy()
        info['whead'] = bpy.data.objects['w_head'].matrix_world.translation.copy()
        return info

    def lens(self, mm):
        self.cam.data.lens = mm

    def at(self, b):
        return bt(b)

    # ---------------------------------------------------------------- bake animation
    def bake(self):
        sc = bpy.context.scene
        ch = self.ch
        start = self.f0 - (self.preroll if ch and self.cloth else 0)
        self.meta = {}
        cam = self.cam
        sim = None
        if ch and self.cloth:
            sim = self.cloak = CK.CloakSim(ch)
            wd = Vector(self.wind[2] if len(self.wind) > 2 else (0.25, 1, 0.12)).normalized()
        for f in range(start, self.f1):
            t = f / FPS
            b = t / BEAT
            # character: stepped on twos (drawn look); keyed on every frame but pose sampled at the held time
            if ch:
                lf = max(0, f - self.f0)
                st_ = self.step(b) if callable(self.step) else self.step
                hold = f if st_ == 1 else (self.f0 + (lf // st_) * st_ if f >= self.f0 else self.f0)
                p = self.track.eval(max(hold, self.f0) / FPS)
                info = R.apply_pose(ch, p, f)
                R.key_all(ch, f)
                if sim:
                    wv = self.wind_fn(t) if getattr(self, 'wind_fn', None) else wd * (4.0 * self.wind[0])
                    sim.step(1.0 / FPS, Vector(wv) * p['cloakwind'], t)
                    if f < self.f0 or hold == f:
                        sim.apply()
                    for e in sim.E.values():
                        e.keyframe_insert('location', frame=f)
            for parts, fn in self.wolves:
                lf = max(0, f - self.f0)
                hold = self.f0 + (lf // 2) * 2
                st = fn(hold / FPS)
                if st is None:
                    for ob in parts.values():
                        ob.hide_render = True; ob.keyframe_insert('hide_render', frame=f)
                else:
                    for ob in parts.values():
                        ob.hide_render = False; ob.keyframe_insert('hide_render', frame=f)
                    WD.pose_wolf(parts, st, f)
            for cb in self.per_frame:
                cb(t, f)
            # camera on ones
            c = self.ct.eval(b)
            if c:
                CH.aim(cam, c['eye'], c['tgt'], c.get('roll', 0.0) * math.pi / 180)
                cam.data.lens = c.get('lens', cam.data.lens)
                cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_quaternion', frame=f)
                cam.data.keyframe_insert('lens', frame=f)
        objs = [o for o in bpy.data.objects if o.animation_data]
        R.step_keys([o for o in objs if o != cam])
        # meta pass (after keys exist): project points each frame
        for f in range(self.f0, self.f1):
            sc.frame_set(f)
            m = {}
            for k, fn in self.meta_fns.items():
                wpt = fn()
                if wpt is None:
                    continue
                v = world_to_camera_view(sc, cam, Vector(wpt))
                m[k] = [v.x * 1920, (1 - v.y) * 1080, v.z]
            if ch and self.trail_on and self.trail_on(f / FPS / BEAT):
                m['trail'] = self.trail(f)
            self.meta[f] = m

    def trail(self, f, n=10):
        """blade sweep from the previous drawing to this one, from the UNSTEPPED pose track: [[hx,hy,tx,ty,depth]...]"""
        sc = bpy.context.scene
        b = f / FPS / BEAT
        st_ = self.step(b) if callable(self.step) else self.step
        lf = f - self.f0
        hold = f if st_ == 1 else self.f0 + (lf // st_) * st_
        out = []
        O = bpy.data.objects
        for j in range(n + 1):
            ts = (hold - st_ + st_ * j / n) / FPS
            R.apply_pose(self.ch, self.track.eval(ts), None)
            hw, tw = O['w_hinge'].matrix_world.translation, O['w_tip'].matrix_world.translation
            a = world_to_camera_view(sc, self.cam, hw); c = world_to_camera_view(sc, self.cam, tw)
            out.append([a.x * 1920, (1 - a.y) * 1080, c.x * 1920, (1 - c.y) * 1080, c.z])
        return out

    def add_cloth(self, start):
        sc = bpy.context.scene
        ob = self.ch['cloak']
        cm = ob.modifiers.new('cloth', 'CLOTH')
        # cloth must come after the armature (pinned verts follow) and before solidify/outline
        while ob.modifiers.find('cloth') > 1:
            bpy.context.view_layer.objects.active = ob
            bpy.ops.object.modifier_move_up(modifier='cloth')
        cs = cm.settings
        cs.quality = 6; cs.mass = 0.25; cs.air_damping = 1.5
        cs.tension_stiffness = 12; cs.compression_stiffness = 12; cs.shear_stiffness = 6; cs.bending_stiffness = 0.2
        cs.vertex_group_mass = 'pin'; cs.pin_stiffness = 2.0
        cm.collision_settings.use_collision = True; cm.collision_settings.distance_min = 0.01
        cm.point_cache.frame_start = start; cm.point_cache.frame_end = self.f1
        body = self.ch['body']
        body.modifiers.new('col', 'COLLISION'); body.collision.thickness_outer = 0.03
        cm.collision_settings.collision_quality = 4; cs.quality = 8
        # wind blows along self.wind[2] (world dir); default +Y = streaming back from a character facing -Y
        wd = Vector(self.wind[2] if len(self.wind) > 2 else (0.25, 1, 0.12)).normalized()
        bpy.ops.object.effector_add(type='WIND', location=tuple(-wd * 3 + Vector((0, 0, 1.2))))
        wind = bpy.context.active_object
        wind.rotation_mode = 'QUATERNION'
        wind.rotation_quaternion = wd.to_track_quat('Z', 'Y')
        wind.field.strength = 3.0 * self.wind[0]; wind.field.noise = 2.0 * self.wind[1]; wind.field.flow = 0.5
        self.windobj = wind
        sc.frame_start = start
        for f in range(start, self.f1):
            sc.frame_set(f)
        sc.frame_start = self.f0

    # ---------------------------------------------------------------- render
    def render(self, frames=None, pct=None, out=None):
        sc = bpy.context.scene
        if pct:
            sc.render.resolution_percentage = pct
        out = out or os.path.join(HERE, 'frames', self.name)
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, 'meta.json'), 'w') as fh:
            json.dump(dict(name=self.name, b0=self.b0, b1=self.b1, f0=self.f0, f1=self.f1,
                           meta={str(k): v for k, v in self.meta.items()}, events=self.events), fh)
        fl = frames if frames is not None else range(self.f0, self.f1)
        t0 = time.time()
        for f in fl:
            sc.frame_set(f)
            sc.render.filepath = os.path.join(out, f'f{f:04d}.png')
            bpy.ops.render.render(write_still=True)
        print(f'[{self.name}] rendered {len(list(fl))} frames in {time.time() - t0:.0f}s')


def args():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    d = {'pct': 100, 'frames': None, 'test': False}
    for x in a:
        if x.startswith('--pct='): d['pct'] = int(x[6:])
        elif x.startswith('--frames='): d['frames'] = [int(v) for v in x[9:].split(',')]
        elif x == '--test': d['test'] = True
        elif x.startswith('--every='): d['every'] = int(x[8:])
    return d
