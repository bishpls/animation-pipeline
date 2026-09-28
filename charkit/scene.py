"""A character scene from a spec (docs/CHARKIT.md §3), Blender-side: the stages in order, each a function of the spec and
what came before, so a build can stop after any stage, swap one out (the hair from a generated shape instead of the
analytic volume, say), or render boards from the result.

    body+head -> face features -> face shading -> hair -> accessories -> garments -> (boards, export)

    from charkit import scene; S = scene.build(spec)     # inside Blender: S.character, S.hair, S.garments, ...
    scene.boards(S, out, which=('views', 'expressions', 'mouths', 'body'))
"""
import json, os

import numpy as np

SKIN = dict(lit=(1.0, 0.90, 0.86), shade=(0.95, 0.76, 0.74), deep=(0.84, 0.60, 0.62))
EXPR = ['blink', 'happy', 'half', 'wide', 'angry', 'sad', 'squint']
MOUTH = ['neutral', 'aa', 'ih', 'ou', 'ee', 'oh', 'smile', 'grin', 'frown', 'surprised']


class Scene:
    """what a build made: the character (charkit.character.build's dict) and each stage's objects."""

    def __init__(self, spec):
        self.spec = spec
        self.name = spec['name']
        self.character = None
        self.hair, self.hair_volume, self.accessories, self.garments = [], None, [], []

    @property
    def features(self):
        return [p[k] for p in self.character['eyes'] for k in ('sclera', 'iris', 'lash', 'brow')]

    @property
    def covers(self):
        return self.hair + self.accessories


def load(path):
    spec = json.load(open(path))
    spec.setdefault('_dir', os.path.dirname(os.path.abspath(path)))
    return spec


def reset(bg=(0.86, 0.86, 0.90)):
    import bpy
    from . import shade
    bpy.ops.wm.read_factory_settings(use_empty=True)
    shade.MATS.clear()
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_EEVEE'
    sc.view_settings.view_transform = 'Standard'
    w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
    w.node_tree.nodes['Background'].inputs['Color'].default_value = (*bg, 1)


def stage_character(S):
    from . import character, shade
    sk = {k: tuple(v) for k, v in S.spec.get('skin', {}).items()} or SKIN
    S.character = character.build(S.spec, clay=shade.toon3('skin', **sk))
    shade.outline(S.character['skin'], thick=0.0011, color=tuple(S.spec.get('skin_line', (0.42, 0.24, 0.20))))
    S.skin_colors = sk


def stage_hair(S):
    from . import accessories, hair, shade
    if S.spec.get('hair') is None:
        return
    hc = {k: tuple(v) for k, v in S.spec.get('hair_colors', {}).items()}
    S.hair, S.hair_volume = hair.build(S.character['data'], S.character['arm'], S.spec.get('hair'), hc)
    S.accessories = accessories.build(S.character['data'], S.character['arm'], S.hair_volume, S.spec.get('accessories'),
                                      {'hair': shade.MATS.get('hair')})


def stage_face_shading(S):
    from . import faceshade
    bangs = None
    fr = next((o for o in S.hair if o.name.startswith('hair_front')), None)
    if fr is not None:
        bangs = (np.array([v.co for v in fr.data.vertices]), [tuple(p.vertices) for p in fr.data.polygons])
    faceshade.apply(S.character, bangs=bangs, colors=S.skin_colors)


def stage_garments(S):
    from . import garments
    S.garments = garments.build(S.character, S.spec.get('garments'))


STAGES = [('character', stage_character), ('hair', stage_hair), ('face_shading', stage_face_shading),
          ('garments', stage_garments)]


def build(spec, until=None, skip=()):
    """run the stages in order (stop after `until`, leave out `skip`). -> Scene."""
    reset()
    S = Scene(spec)
    for name, fn in STAGES:
        if name not in skip:
            fn(S)
        if name == until:
            break
    return S


# ------------------------------------------------------------------------------------------------------------------ boards
def boards(S, out, which=('views', 'expressions', 'mouths', 'body')):
    """render the review boards into out/: head views (front .. back), the expression and mouth sets, full-body views."""
    import bpy
    from . import qa
    from .boards.face_board import set_expr, set_mouth
    os.makedirs(out, exist_ok=True)
    sc = bpy.context.scene
    A = S.character['data']; eye_z = A['head']['eye_z']; L = A['head']['L']
    cam = bpy.data.objects.get('board_cam')
    if cam is None:
        cam = bpy.data.objects.new('board_cam', bpy.data.cameras.new('board_cam')); sc.collection.objects.link(cam)
    sc.camera = cam
    covers = S.covers

    def shot(path, *a, **kw):
        qa.render_view(cam, *a, path, **kw)
        if covers:
            qa.features_through(path, S.features, covers, [S.character['skin']])
    made = []
    if 'views' in which:
        sc.render.resolution_x, sc.render.resolution_y = 900, 900
        for az in (0, 30, 60, 90, 150):
            p = os.path.join(out, f'face_{az:03d}.png'); made.append(p)
            shot(p, (0, 0, eye_z + 0.06 * L), az, 1.0, 0.0, lens=85)
    if 'body' in which:
        sc.render.resolution_x, sc.render.resolution_y = 600, 1000
        H_ = S.spec.get('body', {}).get('height_m', 1.6)
        for az in (0, 35, 90, 180):
            p = os.path.join(out, f'body_{az:03d}.png'); made.append(p)
            qa.render_view(cam, (0, 0, H_ * 0.52), az, 6.0, 0.0, p, ortho=H_ * 1.12)
    if 'expressions' in which:
        sc.render.resolution_x, sc.render.resolution_y = 600, 600
        for e in EXPR:
            set_expr(S.character, e)
            p = os.path.join(out, f'expr_{e}.png'); made.append(p)
            shot(p, (0, 0, eye_z - 0.02 * L), 0, 0.42, 0.0, lens=85)
        set_expr(S.character, None)
    if 'mouths' in which:
        sc.render.resolution_x, sc.render.resolution_y = 600, 600
        for m in MOUTH:
            set_mouth(S.character, m)
            p = os.path.join(out, f'mouth_{m}.png'); made.append(p)
            qa.render_view(cam, (0, 0, eye_z - 0.28 * L), 0, 0.30, 0.0, p, lens=85)
        set_mouth(S.character, 'neutral')
    return made


def save(path):
    import bpy
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(path), compress=True)
