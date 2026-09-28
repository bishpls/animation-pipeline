"""DANCE TEST: 3D Clawd dances TSUZUKU's bars 58-66 (the lead-in and the hook) on a small idol stage, from GEM-X mocap of the
directed reference clips, time-warped onto the song by the phrases' structural anchors (as the 2D film did). One continuous
camera move; blinks; the mouth from the vocal's loudness. On ones (Clawd's timing in TSUZUKU).
    blender -b --factory-startup --python projects/clawd3d/shots/dance_test.py -- OUTDIR [--pct 100] [--frames a,b]
then: projects/clawd3d/shots/encode.sh OUTDIR
"""
import json, math, os, random, sys
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(os.path.dirname(HERE), 'build')
sys.path.insert(0, BUILD)
import clawd, kit, motion, soma_map, stage

TSU = os.path.expanduser('~/animation-pipeline/projects/tsuzuku')
MOCAP = os.path.join(os.path.dirname(HERE), 'refs', 'mocap')
FPS = 24
BPM = 170.0
BAR = 240.0 / BPM
B0, B1 = 58.0, 66.0                           # song bars
PAD = 0.5                                     # seconds before and after
T0 = B0 * BAR - PAD                           # song time at frame 1
NF = int(round(((B1 - B0) * BAR + 2 * PAD) * FPS))


def phrases():
    ph = {p['name']: p for p in json.load(open(os.path.join(TSU, 'refs/mocap/phrases.json')))['phrases']}
    return [('c1c_v1', ph['c1c_v1']['anchors'], None), ('hook_v1', ph['hook_v1']['anchors'], ph['hook_v1'].get('tail'))]


def source_time(bar, anchors, tail):
    if tail:
        s0, s1, b0, b1 = (float(x) for x in tail.split(':'))
        if b0 <= bar <= b1:
            return s0 + (bar - b0) / (b1 - b0) * (s1 - s0)
    return motion.warp(anchors)(bar)


def poses():
    (n1, a1, t1), (n2, a2, t2) = phrases()
    S1 = motion.Sampler(motion.load_clip(os.path.join(MOCAP, f'{n1}.clip.npz')))
    S2 = motion.Sampler(motion.load_clip(os.path.join(MOCAP, f'{n2}.clip.npz')))
    joints = sorted({j for j, _ in soma_map.BONE_MAP.values()})
    seam, blend = 62.0, 0.10                                  # bars
    _, r1_end = S1.at(source_time(seam, a1, t1), joints)
    _, r2_start = S2.at(source_time(seam, a2, t2), joints)
    carry = Vector((r1_end.x - r2_start.x, r1_end.y - r2_start.y, 0))
    out, contact = [], []
    C1 = S1.clip['contact']; C2 = S2.clip['contact']

    def cat(S, C, t):
        k = min(len(C) - 1, max(0, int(round(t * S.fps))))
        return float(C[k].max())
    for f in range(NF):
        bar = (T0 + f / FPS) / BAR
        bar_c = min(max(bar, B0), B1)
        st1, st2 = source_time(min(bar_c, seam + blend), a1, t1), source_time(max(bar_c, seam - blend), a2, t2)
        G1, R1 = S1.at(st1, joints)
        G2, R2 = S2.at(st2, joints)
        decay = max(0.0, 1 - (bar_c - seam) / 1.0) if bar_c > seam else 1.0     # recentre over a bar after the seam
        R2 = R2 + carry * decay
        w = min(1.0, max(0.0, (bar_c - (seam - blend)) / (2 * blend)))
        w = w * w * (3 - 2 * w)
        contact.append(cat(S1, C1, st1) if w < 0.5 else cat(S2, C2, st2))
        if w <= 0:
            out.append((G1, R1))
        elif w >= 1:
            out.append((G2, R2))
        else:
            out.append(({j: G1[j].slerp(G2[j], w) for j in joints}, R1.lerp(R2, w)))
    return out, S1.clip, contact


EXPRESSIONS = [  # (from bar, to bar, eyes): Clawd's acting on this phrase
    (59.75, 61.0, 'soft'),        # the held note of the lead-in
    (62.0, 62.5, 'surprised'),    # the hook lands
    (64.0, 64.5, 'wink'),         # the claw by the face
    (65.0, 99.0, 'happy'),        # the finish
]


def face_track(shells):
    """eyes: seeded blinks (half, closed, closed, half), happy on the hook's last bar; mouth: the 2D film's own lip-sync,
    baked by build/lipsync.mjs from the song's word timestamps and the vocal's loudness."""
    track = json.load(open(os.path.join(os.path.dirname(HERE), 'out', 'tex', 'mouth_track.json')))
    M, mfps = track['mouth'], track['fps']
    R = random.Random(7)
    blinks = []
    t = 0.9
    while t < NF / FPS:
        blinks.append(t); t += R.uniform(2.1, 3.2)
    prev = None
    for f in range(NF):
        t = f / FPS
        ts = T0 + t
        mouth = M[min(len(M) - 1, int(ts * mfps + 1e-6))]
        eyes = 'open'
        for b in blinks:
            d = (t - b) * FPS
            if 0 <= d < 2:
                eyes = 'closed'
            elif -1 <= d < 0 or 2 <= d < 3:
                eyes = 'half'
        bar = ts / BAR
        for b0, b1, e in EXPRESSIONS:                           # the acting, by bar (blinks only fill the open stretches)
            if b0 <= bar < b1:
                eyes = e
                break
        key = (eyes, mouth)
        if key != prev:
            clawd.set_face(shells, eyes, mouth, frame=f + 1)
            prev = key
    for ob in shells.values():                                  # held drawings: no fading between face states
        if ob.animation_data and ob.animation_data.action:
            for fc in motion.all_fcurves(ob.animation_data.action):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'


def camera_move(cam):
    """One continuous move: three-quarter left, wide; orbit to the front and push in on the hook's downbeat; drift to a
    three-quarter right medium. Minimum-jerk easing between keys; the look-at rides up from the body to the face."""
    keys = [  # (bar, azimuth deg, distance m, height m, look-at z, lens)
        (B0 - PAD / BAR, -38, 4.6, 1.05, 0.80, 38),
        (61.5, -12, 3.9, 1.00, 0.84, 38),
        (62.0, -4, 3.1, 0.98, 0.90, 40),
        (64.0, 10, 2.8, 1.02, 0.95, 42),
        (B1 + PAD / BAR, 30, 2.6, 1.08, 1.00, 44),
    ]
    def mj(u):
        return u ** 3 * (10 - 15 * u + 6 * u * u)
    for f in range(NF):
        bar = (T0 + f / FPS) / BAR
        i = max(0, min(len(keys) - 2, next((k for k in range(len(keys) - 1) if keys[k][0] <= bar <= keys[k + 1][0]), 0)))
        (b0, *v0), (b1, *v1) = keys[i], keys[i + 1]
        u = mj(min(1.0, max(0.0, (bar - b0) / (b1 - b0))))
        az, dist, h, lz, lens = (a + (b - a) * u for a, b in zip(v0, v1))
        a = math.radians(az)
        tgt = Vector((0, 0, lz))
        kit.aim(cam, tgt + Vector((math.sin(a) * dist, -math.cos(a) * dist, h - lz)), tgt)
        cam.data.lens = lens
        cam.keyframe_insert('location', frame=f + 1); cam.keyframe_insert('rotation_quaternion', frame=f + 1)
        cam.data.keyframe_insert('lens', frame=f + 1)


def main(out, pct=100, frames=None):
    os.makedirs(out, exist_ok=True)
    C = clawd.build()
    arm = C['arm']
    P, clip0, contact = poses()
    Wcal = motion.calibrate(arm, clip0, soma_map.BONE_MAP, soma_map.TWIST_REFS, soma_map.target_twist(clawd.joint))
    scale = arm.data.bones['hips'].head_local.z / float(clip0['offsets'][0][1])
    motion.bake(arm, P, soma_map.BONE_MAP, Wcal, scale, springs=clawd.SPRINGS, fps=FPS)
    motion.floor_lock(arm, C['body'], contact)
    face_track(C['face'])
    st = stage.build(arm)
    stage.sway_beams(st['beams'], NF, FPS, BAR / 4)
    sc = kit.setup_render(res=(1920, 1080), pct=pct, bg=(0.07, 0.06, 0.12))
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = 1, NF
    kit.set_light((0.72, -0.45, 0.55))                           # key from her left and above: more form than a frontal light
    kit.set_rim(kit.hexc('ff9ad5'), 0.32)                       # the stage's pink on every rim
    cam = kit.camera('cam', lens=38)
    camera_move(cam)
    clawd.look_at_camera(arm, cam, NF, fps=FPS)                  # eye contact
    sc.render.filepath = os.path.join(os.path.abspath(out), 'frames', '')
    json.dump({'frames': NF, 'fps': FPS, 'song_t0': T0, 'bars': [B0, B1]}, open(os.path.join(out, 'shot.json'), 'w'))
    def render(sub):
        if frames:
            for f in frames:
                sc.frame_set(f)
                sc.render.filepath = os.path.join(os.path.abspath(out), sub, f'{f:04d}.png')
                bpy.ops.render.render(write_still=True)
        else:
            sc.render.filepath = os.path.join(os.path.abspath(out), sub, '')
            bpy.ops.render.render(animation=True)
    render('stills' if frames else 'frames')
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.path.abspath(out), 'dance_test.blend'))
    # the features pass: eyes and brows with the hair hidden and everything else held out, so post can show them through
    # the bangs (never through a hand)
    undo = features_pass(sc, C)
    render('stills_feat' if frames else 'feat')
    undo()
    # the line pass: camera-space normals and depth of the character alone, for post.py's inner lines
    aux_pass(sc, st)
    render('stills_aux' if frames else 'aux')


def features_pass(sc, C):
    eyes = [o for (kind, nm), o in C['face'].items() if kind == 'eyes']
    hair = [o for o in bpy.data.objects if o.name.startswith('hair_') or o.name.startswith('bun.')]
    hold = bpy.data.collections.new('holdout'); sc.collection.children.link(hold)
    moved = []
    for o in list(sc.collection.objects):
        if o.type != 'MESH' or o in eyes or o in hair:
            continue
        sc.collection.objects.unlink(o); hold.objects.link(o); moved.append(o)
    lc = bpy.context.view_layer.layer_collection.children['holdout']; lc.holdout = True
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


def aux_pass(sc, st):
    m = bpy.data.materials.new('aux_normal_depth'); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    N, L = nt.nodes.new, nt.links.new
    out = N('ShaderNodeOutputMaterial'); em = N('ShaderNodeEmission'); geo = N('ShaderNodeNewGeometry')
    vt = N('ShaderNodeVectorTransform'); vt.vector_type = 'NORMAL'; vt.convert_from = 'WORLD'; vt.convert_to = 'CAMERA'
    L(geo.outputs['Normal'], vt.inputs[0])
    sep = N('ShaderNodeSeparateXYZ'); L(vt.outputs[0], sep.inputs[0])
    cam = N('ShaderNodeCameraData')
    dz = N('ShaderNodeMath'); dz.operation = 'DIVIDE'; dz.inputs[1].default_value = 12.0; L(cam.outputs['View Z Depth'], dz.inputs[0])
    rx = N('ShaderNodeMath'); rx.operation = 'MULTIPLY_ADD'; rx.inputs[1].default_value = 0.5; rx.inputs[2].default_value = 0.5
    ry = N('ShaderNodeMath'); ry.operation = 'MULTIPLY_ADD'; ry.inputs[1].default_value = 0.5; ry.inputs[2].default_value = 0.5
    L(sep.outputs['X'], rx.inputs[0]); L(sep.outputs['Y'], ry.inputs[0])
    c = N('ShaderNodeCombineColor'); L(rx.outputs[0], c.inputs[0]); L(ry.outputs[0], c.inputs[1]); L(dz.outputs[0], c.inputs[2])
    L(c.outputs[0], em.inputs['Color']); L(em.outputs[0], out.inputs['Surface'])
    for o in [st['floor'], st['backdrop'], st.get('shadow')] + st['beams'] + \
             [o for o in bpy.data.objects if o.name.startswith('clip_')]:    # tiny faceted props: outline only, no inner lines
        if o:
            o.hide_render = True
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.data.materials:
            for i in range(len(o.data.materials)):
                if o.data.materials[i] and o.data.materials[i].name.startswith('outline'):
                    continue
                o.data.materials[i] = m
            for md in o.modifiers:
                if md.type == 'SOLIDIFY' and md.name == 'outline':
                    md.show_render = False
    sc.world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.5, 0.5, 1.0, 1)
    sc.view_settings.view_transform = 'Standard'
    sc.render.image_settings.color_depth = '16'
    sc.eevee.taa_render_samples = 1                             # no anti-aliasing: exact values for the edges


if __name__ == '__main__':
    a = sys.argv[sys.argv.index('--') + 1:]
    fr = [int(x) for x in a[a.index('--frames') + 1].split(',')] if '--frames' in a else None
    main(a[0], int(a[a.index('--pct') + 1]) if '--pct' in a else 100, fr)
