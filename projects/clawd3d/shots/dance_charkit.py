"""DANCE TEST on charkit: dance_test.py's shot (TSUZUKU bars 58-66, the same mocap phrases time-warped onto the song, the
same camera move, stage, light and rim, blinks, acting and the 2D film's lip-sync) with Clawd rebuilt by the parametric
character kit (charkit/spec/clawd.json) instead of the hand-scripted build/clawd.py. The face is charkit's: lid, brow and
viseme shape keys, iris look keys for eye contact, the SDF face shadow lit in head space per frame. Secondary motion comes
from spring bones this script adds to the built rig (charkit_rig.add_springs), so charkit itself is untouched.
    blender -b --factory-startup --python projects/clawd3d/shots/dance_charkit.py -- OUTDIR [--pct 100] [--frames a,b]
            [--passes main,feat,aux] [--spec charkit/spec/clawd.json] [--charkit HEAD|live|REV]
(--charkit pins the charkit revision the character is built with, exported into OUTDIR; 'live' uses the working tree)
then: projects/clawd3d/shots/encode.sh OUTDIR
"""
import json, os, sys, time
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import charkit_rig as CR                                         # (puts build/ and the repo root on the path)
import dance_test as DT                                          # the shot: clip, bars, poses, camera move, aux pass
import kit, motion, soma_map, stage

FPS, NF, T0, BAR = DT.FPS, DT.NF, DT.T0, DT.BAR
LIGHT = (0.72, -0.45, 0.55)                                      # key from her left and above (dance_test's)
RIM = kit.hexc('ff9ad5')                                         # the stage's pink on every rim
OUTLINE = 2.0                                                    # charkit's board-weight outlines, heavier for a full-body shot


def face_track(face):
    """dance_test's face: seeded blinks (half, closed, closed, half), the acting by bar, the 2D film's lip-sync (baked by
    build/lipsync.mjs), keyed on change as held drawings."""
    track = json.load(open(os.path.join(os.path.dirname(HERE), 'out', 'tex', 'mouth_track.json')))
    M, mfps = track['mouth'], track['fps']
    import random
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
        for b0, b1, e in DT.EXPRESSIONS:
            if b0 <= bar < b1:
                eyes = e
                break
        if (eyes, mouth) != prev:
            face.set(eyes, mouth, f + 1)
            prev = (eyes, mouth)
    face.hold()


def main(out, pct=100, frames=None, passes=('main', 'feat', 'aux'), spec='charkit/spec/clawd.json', rev='HEAD'):
    out = os.path.abspath(out)
    os.makedirs(out, exist_ok=True)
    clock = time.time()
    log = lambda *a: print(f'[dance_charkit {time.time() - clock:6.1f}s]', *a, flush=True)
    log('charkit from', CR.use_charkit(rev, out))
    resolved = CR.resolve_spec(spec, out)
    S = CR.build(resolved)
    C = S.character
    arm = C['arm']
    log('built', resolved)
    CR.bake_hair_normals(S)
    CR.settle_garments(S)
    springs = CR.add_springs(S)
    CR.outlines(OUTLINE)
    P, clip0, contact = DT.poses()
    Wcal = CR.calibrate(arm, clip0)
    scale = arm.data.bones['hips'].head_local.z / float(clip0['offsets'][0][1])
    motion.bake(arm, P, soma_map.BONE_MAP, Wcal, scale, springs=springs, fps=FPS)
    log('baked', len(P), 'frames; springs', list(springs))
    shoes = [o for o in S.garments if o.name.startswith('shoe_')]
    dz, low = CR.floor_lock(arm, shoes, contact)
    log(f'floor lock: lift {dz.min():.3f}..{dz.max():.3f} m; lowest shoe after {low.min():.4f} m')
    face = CR.Face(C)
    face_track(face)
    st = stage.build(arm)
    stage.sway_beams(st['beams'], NF, FPS, BAR / 4)
    sc = kit.setup_render(res=(1920, 1080), pct=pct, bg=(0.07, 0.06, 0.12))
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = 1, NF
    ldir = CR.set_light(LIGHT)
    CR.set_rim(RIM, 0.32)
    cam = kit.camera('cam', lens=38)
    DT.camera_move(cam)
    gl = CR.look_and_light(C, cam, tuple(ldir), NF, fps=FPS)          # eye contact; the face light in head space
    log('face keyed; head-space light x range', round(min(g[3][0] for g in gl), 2), round(max(g[3][0] for g in gl), 2))
    json.dump({'frames': NF, 'fps': FPS, 'song_t0': T0, 'bars': [DT.B0, DT.B1], 'spec': resolved, 'charkit': CR.CHARKIT},
              open(os.path.join(out, 'shot.json'), 'w'))

    def render(sub):
        t0 = time.time()
        if frames:
            for f in frames:
                sc.frame_set(f)
                sc.render.filepath = os.path.join(out, sub, f'{f:04d}.png')
                bpy.ops.render.render(write_still=True)
        else:
            sc.render.filepath = os.path.join(out, sub, '')
            bpy.ops.render.render(animation=True)
        log(f'rendered {sub} in {time.time() - t0:.0f}s')
    if 'main' in passes:
        render('stills' if frames else 'frames')
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'dance_charkit.blend'))
    if 'feat' in passes:
        undo = CR.features_pass(sc, S)
        render('stills_feat' if frames else 'feat')
        undo()
    if 'aux' in passes:
        # the line pass: the drawn face parts and tiny props stay out of it (outline only, no inner lines)
        for o in S.features + list(C['mouth'].values()) + S.accessories:
            o.hide_render = True
        DT.aux_pass(sc, st)
        CR.aux_flatten(S)
        render('stills_aux' if frames else 'aux')
    log('done')


if __name__ == '__main__':
    a = sys.argv[sys.argv.index('--') + 1:]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    fr = [int(x) for x in opt('--frames').split(',')] if '--frames' in a else None
    main(a[0], int(opt('--pct', 100)), fr, tuple(opt('--passes', 'main,feat,aux').split(',')),
         opt('--spec', 'charkit/spec/clawd.json'), opt('--charkit', 'HEAD'))
