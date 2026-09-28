"""The body: MakeHuman's CC0 base mesh -> macro morph -> anime proportions -> the realistic head removed at the neck ->
scaled to the spec's height and head count -> a VRM 1.0 humanoid armature (fingers included) with merged skin weights.

Proportions are edited as scale transforms per VRM bone (along the bone and across it), applied to the rest mesh by linear
blend skinning with the body's own weights: a leg lengthens smoothly through the hip and knee, children move with their
parents, and the skeleton (whose joints are vertex averages) follows exactly. See docs/CHARKIT.md §2.
"""
import json, math
import numpy as np

from . import mh

DEFAULT_BODY = {
    'sex': 0.0, 'age': 0.9, 'muscle': 0.4, 'weight': 0.45, 'height': 0.5, 'ideal': 1.0, 'ethnic': [0.5, 0.5],
    'height_m': 1.60, 'heads_tall': 6.5,
    'proportions': {'leg': 1.10, 'shin': 1.04, 'arm': 1.0, 'torso': 0.94, 'shoulder': 0.86, 'hip': 1.0, 'neck_len': 0.72,
                    'neck_w': 0.82, 'arm_slim': 0.84, 'leg_slim': 0.92, 'hand': 0.88, 'foot': 0.86, 'waist': 0.92},
}


def _merge(a, b):
    out = dict(a)
    for k, v in (b or {}).items():
        out[k] = _merge(a[k], v) if isinstance(v, dict) and isinstance(a.get(k), dict) else v
    return out


def bone_scales(p):
    """proportion knobs -> {vrm bone: (along, across)}"""
    s = {}
    for side in ('left', 'right'):
        s[f'{side}UpperLeg'] = (p['leg'], p['leg_slim'])
        s[f'{side}LowerLeg'] = (p['leg'] * p['shin'], p['leg_slim'])
        s[f'{side}Foot'] = (p['foot'], p['foot'])
        s[f'{side}Toes'] = (p['foot'], p['foot'])
        s[f'{side}Shoulder'] = (p['shoulder'], 1.0)
        s[f'{side}UpperArm'] = (p['arm'], p['arm_slim'])
        s[f'{side}LowerArm'] = (p['arm'], p['arm_slim'])
        s[f'{side}Hand'] = (p['hand'], p['hand'])
        for f in ('Thumb', 'Index', 'Middle', 'Ring', 'Little'):
            for seg in ('Metacarpal', 'Proximal', 'Intermediate', 'Distal'):
                s[f'{side}{f}{seg}'] = (p['hand'], p['hand'])
    s['hips'] = (1.0, p['hip'])
    s['spine'] = (p['torso'], p['waist'])
    s['chest'] = (p['torso'], 1.0)
    s['upperChest'] = (p['torso'], 1.0)
    s['neck'] = (p['neck_len'], p['neck_w'])
    return s


def stylise(verts, joints, W, scales):
    """verts (N,3) Blender frame; joints {mh joint: pos}; W {vrm bone: (N,) weights}; scales {bone: (along, across)}.
    -> new verts. Each bone's map is x -> h' + M (x - h), M = along·aa' + across·(I - aa'); a child's head moves with its
    parent's map, so the skeleton stays connected."""
    order, seen = [], set()

    def visit(b):
        if b in seen:
            return
        par = mh.VRM_PARENT.get(b)
        if par:
            visit(par)
        seen.add(b); order.append(b)
    for b in mh.VRM_JOINTS:
        visit(b)
    H, M, Hn = {}, {}, {}
    for b in order:
        h, t = joints[mh.VRM_JOINTS[b][0]], joints[mh.VRM_JOINTS[b][1]]
        a = t - h
        a = a / (np.linalg.norm(a) + 1e-9)
        al, ac = scales.get(b, (1.0, 1.0))
        Mb = al * np.outer(a, a) + ac * (np.eye(3) - np.outer(a, a))
        par = mh.VRM_PARENT.get(b)
        H[b], M[b] = h, Mb
        Hn[b] = h if par is None else Hn[par] + M[par] @ (h - H[par])
    out = np.zeros_like(verts)
    wsum = np.zeros(len(verts))
    for b in order:
        w = W.get(b)
        if w is None:
            continue
        w = w[:len(verts)]
        out += w[:, None] * (Hn[b] + (verts - H[b]) @ M[b].T)
        wsum += w
    # vertices no bone owns (numerically) keep their place
    miss = wsum < 1e-6
    out[miss] = verts[miss]
    out[~miss] /= wsum[~miss, None]
    return out


def nearest(q, pts, chunk=512):
    """index of the nearest of pts for each of q (numpy only: Blender's Python has no scipy)."""
    out = np.empty(len(q), int)
    p2 = (pts ** 2).sum(1)
    for i in range(0, len(q), chunk):
        c = q[i:i + chunk]
        d = p2[None, :] - 2 * c @ pts.T
        out[i:i + chunk] = d.argmin(1)
    return out


def _lips_centre(verts, skel, n):
    """the lips' centre (the weighted centroid of the upper- and lower-lip bones, oris05 and oris01)."""
    tot, acc = 0.0, np.zeros(3)
    for bone in ('oris05', 'oris01'):
        for i, w in skel.weights.get(bone, []):
            if i < n:
                acc += verts[i] * w; tot += w
    return acc / max(tot, 1e-9)


_MACRO = {}


def macro_stage(P):
    """what only the macro knobs (sex, age, muscle, weight, height, ideal, ethnic) decide: MakeHuman's base morphed, its
    joints, the VRM weights and each helper vertex's nearest body vertex. Cached per macro knobs (the proportions and the
    height scaling don't touch it); callers get it read-only."""
    key = json.dumps([P[k] for k in ('sex', 'age', 'muscle', 'weight', 'height', 'ideal')] + list(P['ethnic']))
    if key not in _MACRO:
        base = mh.Base()
        skel = mh.Skeleton()
        N = 13380                                             # the body group (the helpers come after it)
        mw = mh.macro_weights(sex=P['sex'], age=P['age'], muscle=P['muscle'], weight=P['weight'], height=P['height'],
                              proportions=P['ideal'], ethnic=tuple(P['ethnic']))
        v_mh = mh.morph(base.verts, mw)
        body_bl, helpers_bl = mh.to_blender(v_mh[:N]), mh.to_blender(v_mh[N:])
        if len(_MACRO) >= 4:
            _MACRO.clear()
        _MACRO[key] = dict(base=base, skel=skel, N=N, v_mh=v_mh, body_bl=body_bl, helpers_bl=helpers_bl,
                           joints={k: mh.to_blender(p) for k, p in skel.joint_positions(v_mh).items()},
                           W=mh.vrm_weights(skel, N), nn=nearest(helpers_bl, body_bl))
    return _MACRO[key]


def build_body_data(spec_body=None, neck_below_top=0.86, keep_head=False):
    """-> dict(verts (Blender frame, stylised, scaled, feet on z=0), faces (kept, re-indexed), face_uv, uvs, weights
    {vrm bone: (n,)}, joints {mh joint: pos}, neck_ring [vertex indices of the open neck boundary, ordered], params)."""
    P = _merge(DEFAULT_BODY, spec_body or {})
    M = macro_stage(P)
    base, skel, N = M['base'], M['skel'], M['N']
    v_mh, body_bl, helpers_bl, nn = M['v_mh'], M['body_bl'], M['helpers_bl'], M['nn']
    joints = dict(M['joints'])
    W = {k: w.copy() for k, w in M['W'].items()}
    verts = stylise(body_bl, joints, W, bone_scales(P['proportions']))
    # joints follow: recompute them on the stylised mesh (joints are vertex averages; helper-vertex joints move rigidly
    # with the nearest body vertex's displacement)
    d_body = verts - body_bl
    all_new = np.vstack([verts, helpers_bl + d_body[nn]])
    joints = {j: all_new[np.array(ix)].mean(0) for j, ix in skel.joints.items()}
    body_faces = [(i, f) for i, f in enumerate(base.faces) if base.face_group[i] == 'body']
    head_w = W.get('head', np.zeros(N))
    P_ = P
    if keep_head:
        # keep MakeHuman's head (charkit/anime_head.py reshapes it); scale so its chin sits at height - head length
        faces = [tuple(f) for _, f in body_faces]
        face_uv = [base.face_uv[i] for i, _ in body_faces]
        weights = {k: w for k, w in W.items() if w.max() > 1e-4}
        eye_l = all_new[np.array(sorted(base.groups['joint-l-eye']))].mean(0)
        eye_r = all_new[np.array(sorted(base.groups['joint-r-eye']))].mean(0)
        hv = np.nonzero(head_w > 0.5)[0]
        front = hv[(np.abs(verts[hv, 0]) < 0.004) & (verts[hv, 1] < eye_l[1])]
        chin_i = front[np.argmin(verts[front, 2])] if len(front) else hv[np.argmin(verts[hv, 2])]
        top_i = hv[np.argmax(verts[hv, 2])]
        mouth = _lips_centre(verts, skel, N)
        mid = hv[(np.abs(verts[hv, 0]) < 0.004) & (verts[hv, 2] < eye_l[2]) & (verts[hv, 2] > mouth[2])]
        nose = verts[mid[np.argmin(verts[mid, 1])]].copy()                      # the nose tip: frontmost on the midline
        z0 = verts[:, 2].min()
        verts[:, 2] -= z0
        for k_ in joints:
            joints[k_] = joints[k_] - np.array([0, 0, z0])
        eye_l = eye_l - np.array([0, 0, z0]); eye_r = eye_r - np.array([0, 0, z0]); mouth = mouth - np.array([0, 0, z0]); nose = nose - np.array([0, 0, z0])
        Hm = P['height_m']; head_len = Hm / P['heads_tall']
        k = (Hm - head_len) / verts[chin_i, 2]
        verts *= k
        for j in joints:
            joints[j] = joints[j] * k
        marks = dict(eye_l=eye_l * k, eye_r=eye_r * k, chin=verts[chin_i].copy(), top=verts[top_i].copy(), mouth=mouth * k, nose=nose * k)
        # MakeHuman's face bones (lids, brows, lips, jaw, cheeks): kept as region masks for the face rig and shape keys
        face_w = {}
        for bone, lst in skel.weights.items():
            if mh.vrm_bone(bone) == 'head' and bone != 'head':
                w = np.zeros(N)
                for i, x in lst:
                    if i < N:
                        w[i] = x
                if w.max() > 0:
                    face_w[bone] = w
        # the unmorphed base (topology analysis: the eye pockets) and its eyeball helpers' centres
        vb = mh.to_blender(base.verts)
        eyeballs = {s_: vb[np.array(sorted(base.groups[f'helper-{s_}-eye']))].mean(0) for s_ in ('l', 'r')}
        return dict(verts=verts, faces=faces, face_uv=face_uv, uvs=base.uvs, weights=weights, joints=joints, neck_ring=[],
                    params=P, head_len=head_len, scale=k, marks=marks, head_w=head_w, face_w=face_w, base_body=vb[:N],
                    eyeballs=eyeballs)
    # drop the realistic head (and anything the head bone owns) at the neck
    keep_v = head_w < 0.5
    kept = [(i, f) for i, f in body_faces if all(keep_v[x] for x in f)]
    used = sorted({x for _, f in kept for x in f})
    remap = {o: n for n, o in enumerate(used)}
    faces = [tuple(remap[x] for x in f) for _, f in kept]
    face_uv = [base.face_uv[i] for i, _ in kept]
    verts = verts[used]
    weights = {k: w[used] for k, w in W.items() if k != 'head' and w[used].max() > 1e-4}
    # the open neck boundary, ordered
    from collections import defaultdict
    ecount = defaultdict(int)
    for f in faces:
        for a, b in zip(f, f[1:] + f[:1]):
            ecount[(min(a, b), max(a, b))] += 1
    bnd = [e for e, c in ecount.items() if c == 1]
    adj = defaultdict(list)
    for a, b in bnd:
        adj[a].append(b); adj[b].append(a)
    ring = []
    if bnd:
        top = max(adj, key=lambda i: verts[i][2])            # start on the highest boundary loop (the neck)
        ring = [top]; prev = None
        while True:
            nxt = [x for x in adj[ring[-1]] if x != prev]
            if not nxt or nxt[0] == ring[0]:
                break
            prev = ring[-1]; ring.append(nxt[0])
    # feet on the floor, scaled so the neck top sits where the spec's head count puts it
    z0 = verts[:, 2].min()
    verts[:, 2] -= z0
    for k in joints:
        joints[k] = joints[k] - np.array([0, 0, z0])
    neck_top = verts[ring, 2].mean() if ring else verts[:, 2].max()
    Hm = P['height_m']
    head_len = Hm / P['heads_tall']
    target_neck = Hm - head_len * neck_below_top              # where the body's neck ring sits (the head's loft meets it)
    k = target_neck / neck_top
    verts *= k
    for j in joints:
        joints[j] = joints[j] * k
    return dict(verts=verts, faces=faces, face_uv=face_uv, uvs=base.uvs, weights=weights, joints=joints, neck_ring=ring,
                params=P, head_len=head_len, scale=k)


def build_armature(joints, name='rig'):
    """a Blender armature from the stylised joints with VRM humanoid names; bones rolled so +Z points forward-ish."""
    import bpy
    from mathutils import Vector
    ad = bpy.data.armatures.new(name)
    arm = bpy.data.objects.new(name, ad)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = ad.edit_bones
    for b, (hj, tj) in mh.VRM_JOINTS.items():
        e = eb.new(b)
        e.head = Vector(joints[hj]); e.tail = Vector(joints[tj])
        if (e.tail - e.head).length < 1e-4:
            e.tail = e.head + Vector((0, 0, 0.02))
    for b, par in mh.VRM_PARENT.items():
        if par:
            eb[b].parent = eb[par]
    for e in eb:
        e.align_roll(Vector((0, -1, 0)))
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    return arm


def build_body(spec_body=None, name='body', material=None):
    """Blender objects: (armature, body mesh) with UVs and weights; returns them and the data dict."""
    import bpy
    D = build_body_data(spec_body)
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in D['verts']], [], D['faces'])
    me.update()
    if D['uvs'] is not None:
        uvl = me.uv_layers.new(name='body')
        for poly, fuv in zip(me.polygons, D['face_uv']):
            if fuv is None:
                continue
            for li, ui in zip(poly.loop_indices, fuv):
                uvl.data[li].uv = D['uvs'][ui]
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if material:
        me.materials.append(material)
    arm = build_armature(D['joints'])
    for b, w in D['weights'].items():
        g = ob.vertex_groups.new(name=b)
        nz = np.nonzero(w > 1e-4)[0]
        for i in nz:
            g.add([int(i)], float(w[i]), 'REPLACE')
    mod = ob.modifiers.new('rig', 'ARMATURE'); mod.object = arm
    ob.parent = arm
    return arm, ob, D
