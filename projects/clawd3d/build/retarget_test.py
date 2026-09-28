"""Retarget a canonical clip onto Clawd and render a strip beside its source video, to judge the retarget.
    blender -b --factory-startup --python projects/clawd3d/build/retarget_test.py -- CLIP.clip.npz OUTDIR [--every 4]
"""
import math, os, sys
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import clawd, kit, motion, soma_map


def main(clip_path, out, every=4):
    os.makedirs(out, exist_ok=True)
    C = clawd.build()
    arm = C['arm']
    clip = motion.load_clip(clip_path)
    tw = soma_map.target_twist(clawd.joint)
    Wcal = motion.calibrate(arm, clip, soma_map.BONE_MAP, soma_map.TWIST_REFS, tw)
    n = len(clip['rot'])
    hip_src = float(clip['offsets'][0][1])                        # the rest hips' height above the floor (Y up)
    scale = arm.data.bones['hips'].head_local.z / hip_src
    motion.retarget(arm, clip, soma_map.BONE_MAP, n, fps_out=float(clip['fps']), start=1, root_joint='Hips',
                    height_scale=scale, Wcal=Wcal)
    sc = kit.setup_render(res=(720, 1280), pct=50, bg=(1, 1, 1))
    cam = kit.camera('cam', lens=40)
    tgt = Vector((0, 0, 0.8))
    for f in range(1, n + 1, every):
        sc.frame_set(f)
        for view, az in (('f', 0), ('q', 35)):
            a = math.radians(az)
            kit.aim(cam, tgt + Vector((math.sin(a) * 4.2, -math.cos(a) * 4.2, 0.25)), tgt)
            sc.render.filepath = os.path.join(out, f'{view}_{f:04d}.png')
            bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.path.abspath(out), 'retarget.blend'))


if __name__ == '__main__':
    a = sys.argv[sys.argv.index('--') + 1:]
    main(a[0], a[1], int(a[a.index('--every') + 1]) if '--every' in a else 4)
