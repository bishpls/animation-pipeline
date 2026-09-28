"""Board: a character spec (charkit/spec/*.json) built and rendered in charkit's look: head views (front, 30, 60, 90, 150),
an expression row and a mouth row; next to the spec's reference art when it has one.
    blender -b --factory-startup --python charkit/boards/char_board.py -- SPEC.json OUTDIR [--fast]
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import bpy
import numpy as np
from charkit import accessories, character, faceshade, garments, hair, qa, shade
from charkit.boards.face_board import EXPR, MOUTH, set_expr, set_mouth


def main(spec_path, out, fast=False, nohair=False):
    spec = json.load(open(spec_path))
    name = spec['name']
    os.makedirs(out, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    shade.MATS.clear()
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.view_settings.view_transform = 'Standard'
    w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.86, 0.86, 0.90, 1)
    sk = {k: tuple(v) for k, v in spec.get('skin', {}).items()} or dict(lit=(1.0, 0.90, 0.86), shade=(0.95, 0.76, 0.74),
                                                                         deep=(0.84, 0.60, 0.62))
    C = character.build(spec, clay=shade.toon3('skin', **sk))
    shade.outline(C['skin'], thick=0.0011, color=(0.42, 0.24, 0.20))
    hc = {k: tuple(v) for k, v in spec.get('hair_colors', {}).items()}
    hobs, acc, bangs = [], [], None
    if not nohair:
        hobs, V = hair.build(C['data'], C['arm'], spec.get('hair'), hc)
        acc = accessories.build(C['data'], C['arm'], V, spec.get('accessories'), {'hair': shade.MATS.get('hair')})
        hb = next(o for o in hobs if o.name.startswith('hair_front'))
        bangs = (np.array([v.co for v in hb.data.vertices]), [tuple(p.vertices) for p in hb.data.polygons])
    faceshade.apply(C, bangs=bangs, colors=sk)
    gobs = garments.build(C, spec.get('garments'))
    A = C['data']; eye_z = A['head']['eye_z']; L = A['head']['L']
    cd = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cd); sc.collection.objects.link(cam)
    sc.camera = cam
    feats = [p[k] for p in C['eyes'] for k in ('sclera', 'iris', 'lash', 'brow')]
    covers = hobs + acc

    def shot(path, *a, **kw):
        qa.render_view(cam, *a, path, **kw)
        if covers:
            qa.features_through(path, feats, covers, [C['skin']])
    sc.render.resolution_x, sc.render.resolution_y = 900, 900
    tgt = (0, 0, eye_z + 0.06 * L)
    for az in (0, 30, 60, 90, 150):
        shot(os.path.join(out, f'{name}_face_{az:03d}.png'), tgt, az, 1.0 if not nohair else 0.8, 0.0, lens=85)
    if os.environ.get('CHARKIT_BODY') == '1':
        sc.render.resolution_x, sc.render.resolution_y = 600, 1000
        H_ = spec.get('body', {}).get('height_m', 1.6)
        for az in (0, 35, 90):
            qa.render_view(cam, (0, 0, H_ * 0.52), az, 6.0, 0.0, os.path.join(out, f'{name}_body_{az:03d}.png'),
                           ortho=H_ * 1.12)
    if fast:
        return
    sc.render.resolution_x, sc.render.resolution_y = 600, 600
    for e in EXPR:
        set_expr(C, e)
        shot(os.path.join(out, f'{name}_expr_{e}.png'), (0, 0, eye_z - 0.02 * L), 0, 0.42, 0.0, lens=85)
    set_expr(C, None)
    for m in MOUTH:
        set_mouth(C, m)
        qa.render_view(cam, (0, 0, eye_z - 0.28 * L), 0, 0.30, 0.0, os.path.join(out, f'{name}_mouth_{m}.png'), lens=85)
    set_mouth(C, 'neutral')


if __name__ == '__main__':
    a = sys.argv[sys.argv.index('--') + 1:]
    main(a[0], a[1], fast='--fast' in a, nohair='--nohair' in a)
