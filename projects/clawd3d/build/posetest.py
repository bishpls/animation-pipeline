"""Range test for Clawd's rig: a few extreme poses (T-pose, arms up, a knee lift, a lunge and twist, a crouch) rendered
front and three-quarter into one sheet, to check skinning, the skirt, sleeves, collar and hair against the pose.
    blender -b --factory-startup --python projects/clawd3d/build/posetest.py -- projects/clawd3d/out/posetest
"""
import math, os, sys
import bpy
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import clawd, kit, motion

V = Vector
POSES = {
    'rest': {},
    'tpose': {'leftUpperArm': V((1, 0, 0)), 'leftLowerArm': V((1, 0, 0)), 'rightUpperArm': V((-1, 0, 0)),
              'rightLowerArm': V((-1, 0, 0))},
    'arms_up': {'leftUpperArm': V((0.35, -0.1, 0.93)), 'leftLowerArm': V((0.1, -0.2, 0.97)),
                'rightUpperArm': V((-0.35, -0.1, 0.93)), 'rightLowerArm': V((-0.1, -0.2, 0.97))},
    'knee_lift': {'leftUpperLeg': V((0.1, -0.8, -0.3)), 'leftLowerLeg': V((0.05, 0.1, -1)),
                  'rightUpperArm': V((-0.6, -0.5, 0.6)), 'rightLowerArm': V((-0.2, -0.6, 0.77)),
                  'leftUpperArm': V((0.5, 0.3, -0.8)), 'leftLowerArm': V((0.4, -0.3, -0.85))},
    'lunge': {'leftUpperLeg': V((0.25, -0.55, -0.8)), 'leftLowerLeg': V((0.1, 0.05, -1)),
              'rightUpperLeg': V((-0.2, 0.45, -0.87)), 'rightLowerLeg': V((-0.1, 0.6, -0.8)),
              'rightUpperArm': V((-0.95, -0.3, 0.1)), 'rightLowerArm': V((-0.7, -0.7, 0.1)),
              'leftUpperArm': V((0.9, 0.2, -0.4)), 'leftLowerArm': V((0.8, 0.1, -0.6))},
}


def main(out):
    os.makedirs(out, exist_ok=True)
    C = clawd.build()
    arm = C['arm']
    sc = kit.setup_render(res=(1080, 1080), pct=50, bg=(1, 1, 1))
    cam = kit.camera('cam', lens=50)
    tgt = Vector((0, 0, 0.8))
    for name, aim in POSES.items():
        motion.reset(arm)
        W = motion.solve(arm, aim=aim)
        if name == 'lunge':                      # turn the chest against the hips
            q = Matrix.Rotation(math.radians(25), 3, 'Z')
            W = motion.solve(arm, rot={'chest': q @ motion.rest(arm)['chest']}, aim=aim)
        motion.apply(arm, W, root_loc=None)
        for view, az in (('f', 0), ('q', 40)):
            a = math.radians(az)
            kit.aim(cam, tgt + Vector((math.sin(a) * 3.4, -math.cos(a) * 3.4, 0.3)), tgt)
            sc.render.filepath = os.path.join(out, f'{name}_{view}.png')
            bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    main(sys.argv[sys.argv.index('--') + 1])
