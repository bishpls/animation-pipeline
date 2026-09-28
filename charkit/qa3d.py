"""Measured QA for a built character (docs/CHARKIT.md §4): numbers instead of eyeballing, Blender-side, written as a report
with PASS / WARN / FAIL per check (a check that couldn't run says SKIPPED and why) and overlay images.

  shape      silhouette overlap (IoU) with the generated shape (a TRELLIS.2 GLB, aligned as the build aligned it) from six
             azimuths, overall and per height band (hair, torso, skirt, legs)
  ref        front silhouette overlap with the reference image (both cropped to their bounding boxes)
  scalp      pixels of scalp showing through the hair (the upper cranium and the back of the head, flagged), per view
  poke       share of garment pixels where the body shows through
  hair_noise the hair's shading noise: tone edges per hair pixel (clean anime shadow shapes are low; noisy normals high)
  mesh       open edges and loose parts per hair / garment object (information)

    from charkit import qa3d; report = qa3d.run(S, out)       # S: charkit.scene.Scene, after scene.build
"""
import json, math, os

import numpy as np

AZ = (0, 45, 90, 135, 180, 270)
LIMITS = {                     # (pass at or better, warn at or better); else fail
    'shape_iou': (0.80, 0.65), 'shape_iou_hair': (0.75, 0.60), 'ref_iou': (0.85, 0.70),
    'scalp_px': (30, 300), 'poke_share': (0.005, 0.02), 'hair_noise': (0.04, 0.08),
}


def _grade(key, v, higher_better=True):
    p, w = LIMITS[key]
    if higher_better:
        return 'PASS' if v >= p else 'WARN' if v >= w else 'FAIL'
    return 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'


# -------------------------------------------------------------------------------------------------------------- rendering
class Cam:
    """an orthographic camera round the character: azimuth, framing the whole figure."""

    def __init__(self, zmin, zmax, res=(360, 560)):
        import bpy
        sc = bpy.context.scene
        self.ob = bpy.data.objects.get('qa_cam') or bpy.data.objects.new('qa_cam', bpy.data.cameras.new('qa_cam'))
        if self.ob.name not in sc.collection.objects:
            sc.collection.objects.link(self.ob)
        self.ob.data.type = 'ORTHO'
        self.zc = (zmin + zmax) / 2
        self.scale = (zmax - zmin) * 1.08
        self.ob.data.ortho_scale = self.scale
        self.res = res

    def aim(self, az):
        from mathutils import Vector
        a = math.radians(az)
        eye = Vector((math.sin(a) * 6, -math.cos(a) * 6, self.zc))
        d = (Vector((0, 0, self.zc)) - eye).normalized()
        self.ob.location = eye
        self.ob.rotation_mode = 'QUATERNION'; self.ob.rotation_quaternion = d.to_track_quat('-Z', 'Y')

    def row(self, z):
        """the image row of a world height (orthographic, the long side vertical)."""
        W, H = self.res
        return int(round((0.5 - (z - self.zc) / self.scale) * H))


def _render(path, cam, az, show, override=None, transparent=True):
    """render only `show` objects (others hidden) from an azimuth; -> RGBA float array (row 0 = top)."""
    import bpy
    sc = bpy.context.scene
    saved = {o.name: o.hide_render for o in sc.objects}
    keep = set(o.name for o in show)
    for o in sc.objects:
        if o.type == 'MESH':
            o.hide_render = o.name not in keep
    vl = bpy.context.view_layer
    old_ov, old_ft = vl.material_override, sc.render.film_transparent
    old_cam = sc.camera
    try:
        vl.material_override = override
        sc.render.film_transparent = transparent
        sc.camera = cam.ob
        cam.aim(az)
        sc.render.resolution_x, sc.render.resolution_y = cam.res
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
    finally:
        vl.material_override = old_ov; sc.render.film_transparent = old_ft; sc.camera = old_cam
        for o in sc.objects:
            if o.name in saved:
                o.hide_render = saved[o.name]
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[::-1]
    bpy.data.images.remove(img)
    return px


def _flat(name='qa_flat', color=(1, 1, 1)):
    import bpy
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        o = nt.nodes.new('ShaderNodeOutputMaterial'); e = nt.nodes.new('ShaderNodeEmission')
        e.inputs['Color'].default_value = (*color, 1); nt.links.new(e.outputs[0], o.inputs['Surface'])
    return m


def _save_rgb(path, rgb):
    import bpy
    h, w, _ = rgb.shape
    img = bpy.data.images.new(os.path.basename(path), w, h, alpha=True)
    img.pixels.foreach_set(np.concatenate([rgb[::-1], np.ones((h, w, 1))], -1).astype(np.float32).ravel())
    img.filepath_raw = path; img.file_format = 'PNG'; img.save()
    bpy.data.images.remove(img)


def _iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 1.0


def _bbox_norm(mask, size=(200, 320)):
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return np.zeros(size[::-1], bool)
    m = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    H, W = size[1], size[0]
    yi = (np.arange(H) * m.shape[0] / H).astype(int); xi = (np.arange(W) * m.shape[1] / W).astype(int)
    return m[yi][:, xi]


# ------------------------------------------------------------------------------------------------------------------ checks
def _character_objects(S):
    return [S.character['skin']] + [o for p in S.character['eyes'] for o in p.values()] + \
        list(S.character['mouth'].values()) + list(S.hair) + list(S.accessories) + list(S.garments)


def _shape_object(S):
    import bpy
    from . import character
    full = getattr(S, 'shape_full', None)
    if full is None:
        return None
    ob = bpy.data.objects.get('qa_shape')
    if ob is None:
        ob = character._mesh('qa_shape', full[0], full[1], None, [])
    return ob


def run(S, out, ref_image=None):
    import bpy
    os.makedirs(out, exist_ok=True)
    tmp = os.path.join(out, '_qa_tmp.png')
    A = S.character['data']; Hd = A['head']; L = Hd['L']
    ours = _character_objects(S)
    zs = []
    for o in ours:
        if o.type == 'MESH' and len(o.data.vertices):
            co = np.empty(len(o.data.vertices) * 3, np.float32); o.data.vertices.foreach_get('co', co)
            M = np.array(o.matrix_world)
            zs.append((co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3])[:, 2])
    zs = np.concatenate(zs)
    cam = Cam(float(zs.min()), float(zs.max()))
    flat = _flat()
    rep = {'checks': {}, 'views': {}}
    # height bands (world z): hair (above the chin), torso (chin .. waist), skirt (waist .. knee), legs
    from .garments import bone_seg
    chin = Hd['centre'][2] - Hd['H'].chin
    waist = bone_seg(A, 'spine')[0][2]
    knee = bone_seg(A, 'leftLowerLeg')[0][2]
    bands = {'hair': (chin, 99.0), 'torso': (waist, chin), 'skirt': (knee, waist), 'legs': (-99.0, knee)}
    masks = {}
    for az in AZ:
        masks[az] = _render(tmp, cam, az, ours, flat)[..., 3] > 0.5
    # --- shape: against the generated shape
    shp = _shape_object(S)
    if shp is None:
        rep['checks']['shape'] = {'status': 'SKIPPED', 'why': 'no generated shape in this build'}
    else:
        per = {}
        overlays = []
        for az in AZ:
            g = _render(tmp, cam, az, [shp], flat)[..., 3] > 0.5
            o = masks[az]
            d = {'iou': round(_iou(o, g), 3)}
            for bn, (z0, z1) in bands.items():
                r0, r1 = cam.row(z1), cam.row(z0)
                r0, r1 = max(0, r0), min(o.shape[0], r1)
                if r1 > r0:
                    d['iou_' + bn] = round(_iou(o[r0:r1], g[r0:r1]), 3)
            per[az] = d
            ov = np.zeros(o.shape + (3,)); ov[...] = 0.93
            ov[o & g] = (0.55, 0.55, 0.6); ov[o & ~g] = (0.9, 0.2, 0.2); ov[g & ~o] = (0.2, 0.35, 0.95)
            overlays.append(ov)
        shp.hide_render = True
        mean = float(np.mean([per[a]['iou'] for a in AZ]))
        hair = float(np.mean([per[a].get('iou_hair', 0) for a in AZ]))
        rep['views'] = per
        rep['checks']['shape_iou'] = {'value': round(mean, 3), 'status': _grade('shape_iou', mean)}
        rep['checks']['shape_iou_hair'] = {'value': round(hair, 3), 'status': _grade('shape_iou_hair', hair)}
        for bn in ('torso', 'skirt', 'legs'):
            rep['checks'][f'shape_iou_{bn}'] = {'value': round(float(np.mean([per[a].get('iou_' + bn, 0) for a in AZ])), 3),
                                                'status': 'INFO'}
        _save_rgb(os.path.join(out, 'qa_shape_overlay.png'), np.concatenate(overlays, 1))
    # --- ref: the reference image's front silhouette
    if ref_image and os.path.exists(ref_image):
        img = bpy.data.images.load(ref_image)
        w, h = img.size
        px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, img.channels)[::-1]
        bpy.data.images.remove(img)
        ref = px[..., 3] > 0.5 if px.shape[2] == 4 else px[..., :3].sum(-1) < 2.8
        a, b = _bbox_norm(masks[0]), _bbox_norm(ref)
        v = _iou(a, b)
        rep['checks']['ref_iou'] = {'value': round(v, 3), 'status': _grade('ref_iou', v)}
        ov = np.zeros(a.shape + (3,)); ov[...] = 0.93
        ov[a & b] = (0.55, 0.55, 0.6); ov[a & ~b] = (0.9, 0.2, 0.2); ov[b & ~a] = (0.2, 0.35, 0.95)
        _save_rgb(os.path.join(out, 'qa_ref_overlay.png'), ov)
    else:
        rep['checks']['ref_iou'] = {'status': 'SKIPPED', 'why': 'no reference image'}
    # --- scalp: the upper cranium and the back of the head flagged green, seen through the hair
    skin = S.character['skin']; me = skin.data
    V = A['verts']; hw = A['body']['head_w']; cz = Hd['centre'][2]; cy = Hd['centre'][1]
    region = (hw > 0.5) & ((V[:, 2] > cz + 0.30 * L) | ((V[:, 1] > cy + 0.10 * L) & (V[:, 2] > cz - 0.20 * L)))
    green = _flat('qa_green', (0, 1, 0))
    me.materials.append(green)
    gi = len(me.materials) - 1
    saved = [p.material_index for p in me.polygons]
    for p in me.polygons:
        if all(region[v] for v in p.vertices):
            p.material_index = gi
    outl = [m for m in skin.modifiers if m.type == 'SOLIDIFY']
    for m in outl:
        m.show_render = False
    scalp = {}
    for az in (0, 90, 180, 270):
        px = _render(tmp, cam, az, ours, None, transparent=False)
        g_ = (px[..., 1] > 0.9) & (px[..., 0] < 0.15) & (px[..., 2] < 0.15)
        scalp[az] = int(g_.sum())
        if az == 0:
            ov = px[..., :3].copy(); ov[g_] = (0, 1, 0)
            _save_rgb(os.path.join(out, 'qa_scalp_front.png'), np.clip(ov, 0, 1))
    for p, mi in zip(me.polygons, saved):
        p.material_index = mi
    me.materials.pop(index=gi)
    for m in outl:
        m.show_render = True
    worst = max(scalp.values())
    rep['checks']['scalp_px'] = {'value': worst, 'per_view': scalp, 'status': _grade('scalp_px', worst, False)}
    # --- poke: body vertices (the unmasked ones) lying just outside a garment's surface, where the garment is close: the
    # body showing through it (3D, so legs seen below a skirt or an arm in front of it don't count)
    if S.garments:
        from mathutils import Vector
        from mathutils.bvhtree import BVHTree
        mask_g = skin.vertex_groups.get('under_garments')
        hidden = np.zeros(len(me.vertices), bool)
        if mask_g is not None:
            for v in me.vertices:
                for g_ in v.groups:
                    if g_.group == mask_g.index and g_.weight > 0.5:
                        hidden[v.index] = True
        BV = A['verts']
        from .anime_head import vertex_normals
        BN = vertex_normals(BV, A['faces'])
        per_g, tot_bad = {}, 0
        near_d = 0.06 * L
        for o in S.garments:
            # the garment's own surface (its outer side; the thickness modifier adds an inner side facing the body)
            m_ = o.data
            Mw = np.array(o.matrix_world)
            vs = np.empty(len(m_.vertices) * 3, np.float32); m_.vertices.foreach_get('co', vs)
            vs = vs.reshape(-1, 3) @ Mw[:3, :3].T + Mw[:3, 3]
            polys = [tuple(p.vertices) for p in m_.polygons]
            if not polys:
                continue
            bvh = BVHTree.FromPolygons([Vector(v) for v in vs], polys)
            lo, hi = vs.min(0) - 0.02, vs.max(0) + 0.02
            cand = np.nonzero(~hidden & np.all((BV > lo) & (BV < hi), 1))[0]
            bad = 0
            for i in cand:
                # poking through = the garment lies under the skin here: a short ray inward from the skin meets it
                o_ = Vector(BV[i] + BN[i] * 0.0005)
                hit = bvh.ray_cast(o_, Vector(-BN[i]), near_d)
                if hit[0] is not None:
                    bad += 1
            per_g[o.name] = bad; tot_bad += bad
        share = tot_bad / max(1, int((~hidden).sum()))
        rep['checks']['poke_share'] = {'value': round(share, 4), 'per_garment': per_g,
                                       'status': _grade('poke_share', share, False)}
    else:
        rep['checks']['poke_share'] = {'status': 'SKIPPED', 'why': 'no garments'}
    # --- hair shading noise: tone edges per hair pixel (the hair alone, its own materials)
    if S.hair:
        vals = []
        for az in (0, 90, 180):
            px = _render(tmp, cam, az, list(S.hair), None)
            a = px[..., 3] > 0.5
            lum = px[..., :3] @ np.array([0.3, 0.59, 0.11])
            q = np.digitize(lum, np.percentile(lum[a], [33, 66])) if a.sum() > 50 else np.zeros_like(lum)
            e = (np.abs(np.diff(q, axis=1)) > 0)[:, :] & a[:, 1:] & a[:, :-1]
            e2 = (np.abs(np.diff(q, axis=0)) > 0) & a[1:] & a[:-1]
            vals.append((e.sum() + e2.sum()) / max(1, a.sum()))
        v = float(np.mean(vals))
        rep['checks']['hair_noise'] = {'value': round(v, 4), 'status': _grade('hair_noise', v, False)}
    # --- mesh health (information)
    import bmesh
    mh = {}
    for o in list(S.hair) + list(S.garments):
        bm = bmesh.new(); bm.from_mesh(o.data)
        open_e = sum(1 for e in bm.edges if e.is_boundary)
        parts, seen = 0, set()
        for v0 in bm.verts:
            if v0.index in seen:
                continue
            parts += 1; stack = [v0]; seen.add(v0.index)
            while stack:
                u = stack.pop()
                for e in u.link_edges:
                    w_ = e.other_vert(u)
                    if w_.index not in seen:
                        seen.add(w_.index); stack.append(w_)
        mh[o.name] = {'open_edges': open_e, 'parts': parts}
        bm.free()
    rep['checks']['mesh'] = {'status': 'INFO', 'objects': mh}
    if os.path.exists(tmp):
        os.remove(tmp)
    order = {'FAIL': 0, 'WARN': 1, 'PASS': 2}
    graded = [c['status'] for c in rep['checks'].values() if c.get('status') in order]
    rep['summary'] = min(graded, key=lambda s: order[s]) if graded else 'SKIPPED'
    json.dump(rep, open(os.path.join(out, 'qa.json'), 'w'), indent=1)
    return rep
