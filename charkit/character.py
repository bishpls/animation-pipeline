"""Assemble a character from a spec (docs/CHARKIT.md §3): the MakeHuman body with its own head reshaped into the anime head
(charkit/anime_head.py: one seamless skin, artist topology, MakeHuman's UVs), the armature with the head joints following
the new head, weights, UVs and the face-bone region masks.
    from charkit import character; C = character.build(spec)     # inside Blender
"""
import numpy as np

from . import anime_head, body as bodylib


def assemble(spec):
    """numpy assembly: -> dict(verts, faces, fmat (0 body, 1 head), weights {vrm bone: (N,)}, joints, face_w {MakeHuman face
    bone: (N,)}, body (the body data), head info)."""
    B = bodylib.build_body_data(spec.get('body'), keep_head=True)
    L = B['head_len']
    V0 = B['verts']
    fw = B['face_w']
    eye_w = np.max([fw[b] for b in fw if b.startswith(('orbicularis', 'oculi'))], axis=0)
    lips_w = np.max([fw[b] for b in fw if b.startswith('oris')], axis=0)
    wings_w = np.max([fw[b] for b in fw if b.startswith('levator06')], axis=0)
    V, H, centre, info = anime_head.reshape(V0, B['faces'], B['head_w'], B['marks'], L, spec.get('head'),
                                            detail=spec.get('head_detail'), eye_w=eye_w, lips_w=lips_w, wings_w=wings_w)
    hw = B['head_w']
    fmat = [1 if hw[list(f)].mean() > 0.5 else 0 for f in B['faces']]
    # joints in and around the head follow the reshaped surface
    J = dict(B['joints'])
    near = [k for k, p in J.items() if p[2] > B['marks']['chin'][2] - 0.35 * L]
    moved = anime_head.follow([J[k] for k in near], V0, V)
    for k, p in zip(near, moved):
        J[k] = p
    head_info = dict(L=L, H=H, centre=centre, eye_z=centre[2], info=info, marks=B['marks'])
    return dict(verts=V, faces=B['faces'], fmat=fmat, body=B, weights=B['weights'], joints=J, face_w=B['face_w'],
                head=head_info)


def build(spec, clay=None):
    """Blender objects for a character: (armature, skin mesh) plus the assembly data."""
    import bpy
    A = assemble(spec)
    V, F = A['verts'], A['faces']
    me = bpy.data.meshes.new(spec.get('name', 'char') + '_skin')
    me.from_pydata([tuple(v) for v in V], [], F)
    me.update()
    # UVs: MakeHuman's layout everywhere (the head keeps its face layout); 'face' is the front projection the face features
    # and paint use
    uv = me.uv_layers.new(name='uv')
    fuv = me.uv_layers.new(name='face')
    B, Hd = A['body'], A['head']
    L, c = Hd['L'], Hd['centre']
    for pi, p in enumerate(me.polygons):
        p.material_index = A['fmat'][pi]
        p.use_smooth = True
        for li, ui in zip(p.loop_indices, B['face_uv'][pi]):
            uv.data[li].uv = B['uvs'][ui]
        if A['fmat'][pi] == 1:
            for li in p.loop_indices:
                q = V[me.loops[li].vertex_index] - c
                fuv.data[li].uv = ((q[0] + 0.16 * L) / (0.32 * L), (q[2] + 0.45 * L) / (0.70 * L))
    ob = bpy.data.objects.new(spec.get('name', 'char') + '_skin', me)
    bpy.context.scene.collection.objects.link(ob)
    if clay:
        me.materials.append(clay); me.materials.append(clay)
    arm = bodylib.build_armature(A['joints'], name=spec.get('name', 'char') + '_rig')
    for b, w in A['weights'].items():
        if b not in arm.data.bones:
            continue
        g = ob.vertex_groups.new(name=b)
        for i in np.nonzero(w > 1e-4)[0]:
            g.add([int(i)], float(w[i]), 'REPLACE')
    # the face-bone masks ride along as vertex groups (prefixed; the armature ignores them)
    for b, w in A['face_w'].items():
        g = ob.vertex_groups.new(name='face.' + b)
        for i in np.nonzero(w > 1e-4)[0]:
            g.add([int(i)], float(w[i]), 'REPLACE')
    mod = ob.modifiers.new('rig', 'ARMATURE'); mod.object = arm
    ob.parent = arm
    sub = ob.modifiers.new('sub', 'SUBSURF'); sub.levels = 1; sub.render_levels = 2
    return {'arm': arm, 'skin': ob, 'data': A}
