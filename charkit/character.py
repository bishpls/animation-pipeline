"""Assemble a character from a spec (docs/CHARKIT.md §3): the MakeHuman body with its own head reshaped into the anime head
(charkit/anime_head.py: one seamless skin, artist topology, MakeHuman's UVs), the armature with the head joints following
the new head, weights, UVs and the face-bone region masks.
    from charkit import character; C = character.build(spec)     # inside Blender
"""
import numpy as np

from . import anime_head, body as bodylib, brows as browlib, eyes as eyelib, mouth as mouthlib


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
    # the eyes: the margins onto the anime outline, the lids and pockets after them; plates, lashes and lid keys
    EK = eyelib._knobs(spec.get('eyes'))
    F = eyelib.Face(H, centre)
    eyes = []
    for side, s_ in ((1, 'l'), (-1, 'r')):
        E = dict(side=side, eye=eyelib.detect(B['base_body'], B['faces'], B['eyeballs'][s_]),
                 c=(side * EK['x'] * L, centre[2] + EK['z'] * L))
        V, _ = eyelib.place(V, E['eye'], F, EK, L, side, E['c'])
        eyes.append(E)
    gaze = {'look_left': (0.13, 0.0), 'look_right': (-0.13, 0.0), 'look_up': (0.0, 0.07), 'look_down': (0.0, -0.06)}
    for E in eyes:
        sd, c = E['side'], E['c']
        W = EK['width'] * L
        E['sclera'] = eyelib.plate(F, EK, L, sd, c)
        E['iris'] = eyelib.plate(F, EK, L, sd, c, bias=0.0004)
        E['iris_keys'] = {k: eyelib.plate(F, EK, L, sd, c, bias=0.0004, shift=(sd * g[0] * W, g[1] * W))[0] - E['iris'][0]
                          for k, g in gaze.items()}
        E['lashes'] = eyelib.lashes(F, EK, L, sd, c)
        BK = browlib._knobs(spec.get('brows'))
        E['brow'] = browlib.ribbon(F, BK, EK, L, sd, c)
        E['brow_keys'] = {k: browlib.ribbon(F, BK, EK, L, sd, c, knobs=kn)[0] - E['brow'][0]
                          for k, kn in browlib.expressions(BK).items()}
        E['keys'] = {}
        for name, (uf, lf) in eyelib.expressions(EK, L).items():
            D = eyelib.lid_key(V, E['eye'], F, EK, L, sd, c, uf, lf)
            lash = eyelib.lashes(F, EK, L, sd, c, uf, lf)
            E['keys'][name] = (D, [lv - bv for (lv, _), (bv, _) in zip(lash, E['lashes'])])
    # the mouth: the lips' loop onto the neutral line, the cavity behind; the viseme and expression keys
    MK = mouthlib._knobs(spec.get('mouth'))
    fw = B['face_w']
    uw = sum(fw.get(b, 0) for b in ('oris05', 'oris03.L', 'oris03.R', 'levator06.L', 'levator06.R'))
    lw = sum(fw.get(b, 0) for b in ('oris01', 'oris07.L', 'oris07.R'))
    lw8 = fw['oris05'] + fw['oris01']
    lips_b = (B['base_body'] * lw8[:, None]).sum(0) / lw8.sum()
    Mo = dict(m=mouthlib.detect(B['base_body'], B['faces'], lips_b, uw, lw), c=(0.0, centre[2] + H.mouth_z))
    V = mouthlib.place(V, Mo['m'], F, MK, L, Mo['c'])
    Mo['keys'] = {sh: mouthlib.key(V, Mo['m'], F, MK, L, Mo['c'], sh, jaw_w=fw.get('jaw'))
                  for sh in mouthlib.SHAPES if sh != 'neutral'}
    Mo['teeth'] = mouthlib.teeth(F, MK, L, Mo['c'])
    Mo['tongue'] = mouthlib.tongue(F, MK, L, Mo['c'])
    Mo['teeth_keys'] = {sh: mouthlib.teeth(F, MK, L, Mo['c'], sh)[0] - Mo['teeth'][0] for sh in Mo['keys']}
    Mo['tongue_keys'] = {sh: mouthlib.tongue(F, MK, L, Mo['c'], sh)[0] - Mo['tongue'][0] for sh in Mo['keys']}
    hw = B['head_w']
    fmat = [1 if hw[list(f)].mean() > 0.5 else 0 for f in B['faces']]
    inside = set(Mo['m']['cavity'])
    ring0 = inside | set(Mo['m']['upper']) | set(Mo['m']['lower'])
    fmat = [2 if all(v in ring0 for v in f) and any(v in inside for v in f) else m_ for f, m_ in zip(B['faces'], fmat)]
    # joints in and around the head follow the reshaped surface
    J = dict(B['joints'])
    near = [k for k, p in J.items() if p[2] > B['marks']['chin'][2] - 0.35 * L]
    moved = anime_head.follow([J[k] for k in near], V0, V)
    for k, p in zip(near, moved):
        J[k] = p
    head_info = dict(L=L, H=H, centre=centre, eye_z=centre[2], info=info, marks=B['marks'], eye_knobs=EK)
    return dict(verts=V, faces=B['faces'], fmat=fmat, body=B, weights=B['weights'], joints=J, face_w=B['face_w'],
                head=head_info, eyes=eyes, mouth=Mo)


def build(spec, clay=None, look=None):
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
                fuv.data[li].uv = ((q[0] + 0.16 * L) / (0.32 * L), (q[2] + 0.45 * L) / (1.05 * L))
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
    parts, mouth_parts = build_eyes(A, arm, ob, spec, look=look)
    return {'arm': arm, 'skin': ob, 'data': A, 'eyes': parts, 'mouth': mouth_parts}


def _mesh(name, verts, faces, uvs=None, mats=(), smooth=True):
    import bpy
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    if uvs is not None:
        uv = me.uv_layers.new(name='uv')
        for p in me.polygons:
            p.use_smooth = smooth
            for li in p.loop_indices:
                uv.data[li].uv = uvs[me.loops[li].vertex_index]
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def _key(ob, name, offsets):
    if ob.data.shape_keys is None:
        ob.shape_key_add(name='Basis', from_mix=False)
    kb = ob.shape_key_add(name=name, from_mix=False)
    kb.value = 0.0
    base = np.array([v.co for v in ob.data.vertices])
    kb.data.foreach_set('co', (base + offsets).ravel())
    return kb


def _to_head(ob, arm):
    ob.parent = arm
    g = ob.vertex_groups.new(name='head')
    g.add(list(range(len(ob.data.vertices))), 1.0, 'REPLACE')
    m = ob.modifiers.new('rig', 'ARMATURE'); m.object = arm


def build_eyes(A, arm, skin, spec, look=None):
    """the eye plates (sclera, iris with gaze keys), lash ribbons, and the lid shape keys on the skin and lashes: per side
    ('eye_blink_L') and both ('eye_blink'). look: optional materials {sclera, iris, lash} (default: charkit's)."""
    from . import eyetex, shade
    look = look or {}
    IK = spec.get('iris')
    sclera_m = look.get('sclera') or shade.plate('sclera', eyetex.to_blender_image('sclera', eyetex.sclera(IK)), alpha=False)
    ir = eyetex.iris(IK); sh = eyetex.shine(IK)
    a = sh[..., 3:4]
    comp = np.concatenate([ir[..., :3] * (1 - a) + sh[..., :3] * a, np.maximum(ir[..., 3:4], a)], -1)
    iris_m = look.get('iris') or shade.plate('iris', eyetex.to_blender_image('iris', comp))
    lash_m = look.get('lash') or shade.flat('lash', spec.get('lash_color', (0.16, 0.09, 0.10)))
    brow_m = look.get('brow') or shade.flat('brow', spec.get('brow_color', (0.30, 0.20, 0.20)))
    out = []
    for E in A['eyes']:
        tag = 'L' if E['side'] > 0 else 'R'
        v, q, uv = E['sclera']
        sc = _mesh(f'sclera_{tag}', v, q, uv, [sclera_m])
        v, q, uv = E['iris']
        iob = _mesh(f'iris_{tag}', v, q, uv, [iris_m])
        for k, d in E['iris_keys'].items():
            _key(iob, k, d)
        # closed eyes: the plates sink back so nothing shows through the lids' seam
        for o in (sc, iob):
            back = np.zeros((len(o.data.vertices), 3)); back[:, 1] = 0.006
            for name in ('blink', 'happy'):
                _key(o, f'eye_{name}', back)
        lv, lq, off = [], [], 0
        for rv, rq in E['lashes']:
            lv.append(rv); lq += [tuple(i + off for i in f) for f in rq]; off += len(rv)
        lob = _mesh(f'lash_{tag}', np.vstack(lv), lq, None, [lash_m])
        for name, (D, lash_d) in E['keys'].items():
            _key(lob, f'eye_{name}', np.vstack(lash_d))
        bv, bq = E['brow']
        bob = _mesh(f'brow_{tag}', bv, bq, None, [brow_m])
        for k, d in E['brow_keys'].items():
            _key(bob, f'brow_{k}', d)
        for o in (sc, iob, lob, bob):
            _to_head(o, arm)
        out.append(dict(sclera=sc, iris=iob, lash=lob, brow=bob))
    # the mouth: the cavity's material on the skin, its keys, the teeth and the tongue
    Mo = A['mouth']
    mouth_parts = {}
    cav_m = look.get('cavity') or shade.flat('cavity', spec.get('cavity_color', (0.38, 0.12, 0.15)))
    while len(skin.data.materials) < 2:
        skin.data.materials.append(skin.data.materials[0] if skin.data.materials else None)
    skin.data.materials.append(cav_m)
    for sh, D in Mo['keys'].items():
        _key(skin, f'mouth_{sh}', D)
    for part, col, keys in (('teeth', (0.97, 0.96, 0.97), Mo['teeth_keys']), ('tongue', (0.86, 0.46, 0.50), Mo['tongue_keys'])):
        v, q = Mo[part]
        o = _mesh(part, v, q, None, [look.get(part) or shade.flat(part, col)])
        for sh, d in keys.items():
            _key(o, f'mouth_{sh}', d)
        _to_head(o, arm)
        mouth_parts[part] = o
    # the skin's lid keys: each side, and both
    names = list(A['eyes'][0]['keys'])
    for name in names:
        both = np.zeros_like(A['verts'])
        for E in A['eyes']:
            D = E['keys'][name][0]
            _key(skin, f'eye_{name}_' + ('L' if E['side'] > 0 else 'R'), D)
            both += D
        _key(skin, f'eye_{name}', both)
    return out, mouth_parts
