"""Board: the face in charkit's toon look: head close-ups (85 mm: front, 30, 60, 90 degrees) and an expression row (the lid
shapes at the front), with the eyes, lashes and the skin's outline.
    blender -b --factory-startup --python charkit/boards/face_board.py -- OUTDIR [variant ...]
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import bpy
import numpy as np
from charkit import character, faceshade, hair, qa, shade

VARIANTS = {
    'default': {},
    'soft': {'head': {'chin': 1.4, 'jaw_w': 1.08, 'cheek': 1.25, 'face_len': 0.94, 'width': 1.04}},
    'sharp': {'head': {'chin': 0.65, 'jaw_w': 0.92, 'cheek': 0.8, 'face_len': 1.06, 'width': 0.96, 'flat': 1.15}},
}
SKIN = dict(lit=(1.0, 0.90, 0.86), shade=(0.95, 0.76, 0.74), deep=(0.84, 0.60, 0.62))
EXPR = ['blink', 'happy', 'half', 'wide', 'angry', 'sad', 'squint']
HAIR = os.environ.get('CHARKIT_HAIR', '1') == '1'
MOUTH = ['neutral', 'aa', 'ih', 'ou', 'ee', 'oh', 'smile', 'grin', 'frown', 'surprised']


def set_expr(C, name):
    brow = {'angry': 'angry', 'sad': 'sad', 'wide': 'surprised', 'happy': 'relaxed'}.get(name)
    for p in C['eyes']:
        for kb in (p['brow'].data.shape_keys.key_blocks[1:] if p['brow'].data.shape_keys else []):
            kb.value = 1.0 if kb.name == f'brow_{brow}' else 0.0
    for ob in [C['skin']] + [p[k] for p in C['eyes'] for k in ('lash', 'sclera', 'iris')]:
        ks = ob.data.shape_keys
        if not ks:
            continue
        for kb in ks.key_blocks[1:]:
            if kb.name.startswith('eye_'):
                kb.value = 1.0 if kb.name == f'eye_{name}' else 0.0


def set_mouth(C, name):
    obs = [C['skin']] + list(C['mouth'].values())
    for ob in obs:
        ks = ob.data.shape_keys
        for kb in (ks.key_blocks[1:] if ks else []):
            if kb.name.startswith('mouth_'):
                kb.value = 1.0 if kb.name == f'mouth_{name}' else 0.0


def main(out, names):
    os.makedirs(out, exist_ok=True)
    for name in names:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        shade.MATS.clear()
        sc = bpy.context.scene
        sc.render.engine = 'BLENDER_EEVEE'
        sc.view_settings.view_transform = 'Standard'
        w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
        w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.55, 0.56, 0.60, 1)
        skin = shade.toon3('skin', **SKIN)
        C = character.build(dict(VARIANTS[name], name=name), clay=skin)
        shade.outline(C['skin'], thick=0.0011, color=(0.42, 0.26, 0.26))
        bangs = None
        if HAIR:
            hobs = hair.build(C['data'], C['arm'], VARIANTS[name].get('hair'))
            hb = next(o for o in hobs if o.name.startswith('hair_bangs'))
            bangs = (np.array([v.co for v in hb.data.vertices]), [tuple(p.vertices) for p in hb.data.polygons])
        faceshade.apply(C, bangs=bangs, colors=SKIN)
        A = C['data']; eye_z = A['head']['eye_z']; L = A['head']['L']
        cd = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cd); sc.collection.objects.link(cam)
        sc.camera = cam
        sc.render.resolution_x, sc.render.resolution_y = 900, 900
        tgt = (0, 0, eye_z + 0.02 * L)
        for az in (0, 30, 60, 90, 150):
            qa.render_view(cam, tgt, az, 0.78 if az < 100 else 0.95, 0.0, os.path.join(out, f'{name}_face_{az:03d}.png'), lens=85)
        if os.environ.get('CHARKIT_FAST') == '1':
            continue
        sc.render.resolution_x, sc.render.resolution_y = 600, 600
        for e in EXPR:
            set_expr(C, e)
            qa.render_view(cam, (0, 0, eye_z - 0.02 * L), 0, 0.42, 0.0, os.path.join(out, f'{name}_expr_{e}.png'), lens=85)
        set_expr(C, None)
        for m in MOUTH:
            set_mouth(C, m)
            qa.render_view(cam, (0, 0, eye_z - 0.28 * L), 0, 0.30, 0.0, os.path.join(out, f'{name}_mouth_{m}.png'), lens=85)
        set_mouth(C, 'neutral')


if __name__ == '__main__':
    a = sys.argv[sys.argv.index('--') + 1:]
    main(a[0], a[1:] or ['default'])
