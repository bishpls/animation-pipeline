"""Measured QA for a built character (docs/CHARKIT.md §4): numbers instead of eyeballing, Blender-side, written as a report
with PASS / WARN / FAIL per check (a check that couldn't run says SKIPPED and why) and overlay images.

  shape      silhouette overlap (IoU) with the generated shape (a TRELLIS.2 GLB, aligned as the build aligned it) from six
             azimuths, overall and per height band (hair, torso, skirt, legs)
  ref        front silhouette overlap with the reference image (both cropped to their bounding boxes)
  scalp      pixels of scalp showing through the hair (the upper cranium and the back of the head, flagged), per view
  poke       share of garment pixels where the body shows through
  hair_noise the hair's shading noise: tone edges per hair pixel (clean anime shadow shapes are low; noisy normals high)
  mesh       open edges and loose parts per hair / garment object (information)
  face_shape the face's shape against the generated character's face (charkit/faceqa.py: the lower face's width, the chin,
             the profile, the cheek at three-quarter, depth from under the eyes; how much face the hair leaves showing) and
             the feature heights against the design rig; overlays qa_face_shape.png, qa_face_contours.png
  sheet      the face against the design's model sheet (charkit/sheetqa.py): front half-widths, the profile's front
             edge and reach (nose, chin), the chin's height, the far cheek at three-quarter; overlay qa_sheet.png
  eye        each eye head-on against the design rig's eye layer (charkit/eyeqa.py): the opening's aspect and width, how
             much of it the iris fills, the pupil's run and aspect; overlay qa_eyes.png
  face       per expression and mouth shape, from the shape keys' geometry (front projection, no render): each eye's
             opening (area between the lid margins, against neutral), the share of the iris the lids leave visible, left /
             right symmetry, each mouth shape's opening (area, width, height, left / right balance) and how distinct the
             visemes are from each other; graded: blink closes, no iris in a blink, eyes and mouth symmetric, visemes
             distinct, and each expression's openness inside the range it is meant to have (FACE_EXPECT, warn only)
  face_folds skin faces round the eyes and the mouth facing away at rest or flipping under a lid or mouth key (folded lid
             and lip rings: the realistic lids stretched onto the anime outline, the lip rolls), summed over the keys

    from charkit import qa3d; report = qa3d.run(S, out)       # S: charkit.scene.Scene, after scene.build
"""
import json, math, os

import numpy as np

AZ = (0, 45, 90, 135, 180, 270)
LIMITS = {                     # (pass at or better, warn at or better); else fail
    'shape_iou': (0.80, 0.65), 'shape_iou_hair': (0.75, 0.60), 'ref_iou': (0.85, 0.70),
    'scalp_px': (30, 300), 'poke_share': (0.005, 0.02), 'hair_noise': (0.04, 0.08), 'face_folds': (40, 300),
    'blink_open': (0.03, 0.10), 'blink_iris': (0.01, 0.05), 'eye_asym': (0.03, 0.08), 'mouth_asym': (0.05, 0.15),
    'viseme_gap': (0.010, 0.005),
}
# each eye expression's opening as a share of neutral: (low, high); outside it the check warns
FACE_EXPECT = {'blink': (0.0, 0.03), 'half': (0.3, 0.7), 'wide': (1.05, 2.0), 'happy': (0.0, 0.35), 'squint': (0.2, 0.8),
               'angry': (0.5, 1.05), 'sad': (0.5, 1.05), 'shock': (0.95, 1.05)}
VISEMES = ('aa', 'ih', 'ou', 'ee', 'oh')


def _grade(key, v, higher_better=True):
    p, w = LIMITS[key]
    if higher_better:
        return 'PASS' if v >= p else 'WARN' if v >= w else 'FAIL'
    return 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'


# --------------------------------------------------------------------------------------------------- face (geometry)
def _profile(P, xs):
    """a lid or lip chain's height over x (front view): P (n, 2) as (x, z), sorted by x, sampled at xs."""
    o = np.argsort(P[:, 0])
    return np.interp(xs, P[o, 0], P[o, 1], left=np.nan, right=np.nan)


def opening(upper, lower, xs):
    """the opening between an upper and a lower chain ((n, 2) x-z each) over the x samples: -> (gap per x, area)."""
    g = _profile(upper, xs) - _profile(lower, xs)
    g = np.where(np.isfinite(g), np.maximum(g, 0), 0)
    return g, float(np.trapezoid(g, xs) if hasattr(np, 'trapezoid') else np.trapz(g, xs))


def visible_share(upper, lower, pts):
    """the share of points (m, 2) lying between the chains (below the upper, above the lower)."""
    up, lo = _profile(upper, pts[:, 0]), _profile(lower, pts[:, 0])
    ok = np.isfinite(up) & np.isfinite(lo) & (pts[:, 1] < up) & (pts[:, 1] > lo)
    return float(ok.mean()) if len(pts) else 0.0


def ellipse_points(cx, cz, rx, rz, n=41):
    u = np.linspace(-1, 1, n)
    X, Z = np.meshgrid(u, u)
    m = X ** 2 + Z ** 2 <= 1
    return np.stack([cx + X[m] * rx, cz + Z[m] * rz], 1)


def _key_xz(ob, name):
    """world (x, z) of a mesh's vertices at a shape key (value 1), or the basis when the key is missing."""
    ks = ob.data.shape_keys
    kb = ks.key_blocks.get(name) if ks and name else None
    if kb is None:
        kb = ks.key_blocks[0] if ks else None
    n = len(ob.data.vertices)
    co = np.empty(n * 3, np.float64)
    (kb.data if kb is not None else ob.data.vertices).foreach_get('co', co)
    M = np.array(ob.matrix_world)
    W = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    return W[:, [0, 2]]


def face(S, expressions=None, mouths=None):
    """the face's measured expressions and mouth shapes (see the module docstring) -> (table, checks)."""
    from .eyetex import DEFAULT_IRIS
    skin = S.character['skin']; A = S.character['data']; Hd = A['head']; L = Hd['L']
    expressions = expressions or FACE_EXPECT.keys()
    EK = Hd['eye_knobs']; W = EK['width'] * L
    IK = dict(DEFAULT_IRIS); IK.update(S.spec.get('iris') or {})
    base = _key_xz(skin, None)
    table = {'eyes': {}, 'mouth': {}}
    eyes = []
    for E in A['eyes']:
        up, lo = E['eye']['upper'], E['eye']['lower']
        xs = np.linspace(base[up + lo, 0].min(), base[up + lo, 0].max(), 96)
        iris = ellipse_points(E['c'][0], E['c'][1] + IK['cz'] * W, IK['rx'] * W, IK['rz'] * W)
        _, a0 = opening(base[up], base[lo], xs)
        eyes.append((E['side'], up, lo, xs, iris, a0))
    for name in ['neutral'] + list(expressions):
        P = base if name == 'neutral' else _key_xz(skin, 'eye_' + name)
        row = {}
        for side, up, lo, xs, iris, a0 in eyes:
            _, a = opening(P[up], P[lo], xs)
            row['L' if side > 0 else 'R'] = {'open': round(a / a0, 4) if a0 > 0 else None,
                                              'iris': round(visible_share(P[up], P[lo], iris), 4)}
        table['eyes'][name] = row
    table['eyes']['neutral_area_L2'] = round(eyes[0][5] / L ** 2, 5)
    m = A['mouth']['m']
    up, lo = list(m['upper']), list(m['lower'])
    xs = np.linspace(base[up, 0].min(), base[up, 0].max(), 96)
    mid = 0.5 * (xs.min() + xs.max())
    mouths = mouths or [k.name[6:] for k in (skin.data.shape_keys.key_blocks if skin.data.shape_keys else [])
                        if k.name.startswith('mouth_')]
    for name in ['neutral'] + [k for k in mouths if k != 'neutral']:
        P = base if name == 'neutral' else _key_xz(skin, 'mouth_' + name)
        g, a = opening(P[up], P[lo], xs)
        on = g > 0.002 * L
        left, right = float(np.trapezoid(g[xs < mid], xs[xs < mid])), float(np.trapezoid(g[xs >= mid], xs[xs >= mid]))
        table['mouth'][name] = {'area_L2': round(a / L ** 2, 5), 'width_L': round(float(np.ptp(xs[on])) / L, 4) if on.any() else 0.0,
                                'height_L': round(float(g.max()) / L, 4), 'asym': round(abs(left - right) / a, 4) if a > 1e-9 else 0.0}
    # grades
    E_ = table['eyes']; M_ = table['mouth']
    checks = {}
    if 'blink' in E_:
        v = max(E_['blink'][s]['open'] or 0 for s in ('L', 'R'))
        checks['blink_open'] = {'value': round(v, 4), 'status': _grade('blink_open', v, False)}
        v = max(E_['blink'][s]['iris'] for s in ('L', 'R'))
        checks['blink_iris'] = {'value': round(v, 4), 'status': _grade('blink_iris', v, False)}
    asym = {k: abs((r['L']['open'] or 0) - (r['R']['open'] or 0)) for k, r in E_.items() if isinstance(r, dict) and 'L' in r}
    k = max(asym, key=asym.get)
    checks['eye_asym'] = {'value': round(asym[k], 4), 'worst': k, 'status': _grade('eye_asym', asym[k], False)}
    out = {k: E_[k]['L']['open'] for k, (lo_, hi_) in FACE_EXPECT.items()
           if k in E_ and not (lo_ <= (E_[k]['L']['open'] or 0) <= hi_)}
    checks['expr_range'] = {'value': len(out), 'outside': out, 'status': 'PASS' if not out else 'WARN'}
    ma = {k: r['asym'] for k, r in M_.items() if r['area_L2'] > 1e-4}
    if ma:
        k = max(ma, key=ma.get)
        checks['mouth_asym'] = {'value': ma[k], 'worst': k, 'status': _grade('mouth_asym', ma[k], False)}
    vs = [k for k in VISEMES if k in M_]
    if len(vs) > 1:
        best = min(((np.hypot(M_[a]['width_L'] - M_[b]['width_L'], M_[a]['height_L'] - M_[b]['height_L']), a, b)
                    for i, a in enumerate(vs) for b in vs[i + 1:]))
        checks['viseme_gap'] = {'value': round(float(best[0]), 4), 'closest': [best[1], best[2]],
                                'status': _grade('viseme_gap', float(best[0]))}
    return table, checks


# --------------------------------------------------------------------------------------------------- eyes
def _eye_render(S, E, parts, path, ppl, size=0.42):
    """an orthographic head-on render of one eye (the skin and that eye's white, iris and lashes; no hair, no brows) at
    `ppl` pixels per head length, `size` head lengths square. -> RGBA floats (H, W, 4)."""
    import bpy
    from mathutils import Vector
    sc = bpy.context.scene
    L = S.character['data']['head']['L']
    cam = bpy.data.objects.get('qa_eye_cam') or bpy.data.objects.new('qa_eye_cam', bpy.data.cameras.new('qa_eye_cam'))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = size * L
    cam.location = Vector((E['c'][0], -3.0, E['c'][1])); cam.rotation_mode = 'XYZ'; cam.rotation_euler = (math.pi / 2, 0, 0)
    show = [S.character['skin']] + [parts[k] for k in ('sclera', 'iris', 'lash') if parts.get(k) is not None]
    saved = {o.name: o.hide_render for o in sc.objects}
    for o in sc.objects:
        o.hide_render = o not in show
    old = (sc.camera, sc.render.resolution_x, sc.render.resolution_y, sc.render.film_transparent)
    n = int(round(size * ppl))
    sc.camera = cam; sc.render.resolution_x = sc.render.resolution_y = n; sc.render.film_transparent = True
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    sc.camera, sc.render.resolution_x, sc.render.resolution_y, sc.render.film_transparent = old
    for o in sc.objects:
        o.hide_render = saved.get(o.name, o.hide_render)
    img = bpy.data.images.load(path)
    px = np.array(img.pixels[:], dtype=np.float32).reshape(n, n, 4)[::-1]
    bpy.data.images.remove(img)
    return px


def eyes(S, out, rig=None):
    """our eyes against the design rig's eye layers (charkit.eyeqa), measured the same way -> (table, checks)."""
    from . import eyeqa
    rp = os.path.join(os.path.dirname(os.path.abspath(out)), 'ref_measure.json')
    rig = rig or ((S.spec.get('ref') or {}).get('rig') if isinstance(S.spec.get('ref'), dict) else None)
    if not rig or not os.path.exists(rp):
        return None, {'eye': {'status': 'SKIPPED', 'why': 'no design rig (spec.ref.rig) or ref_measure.json'}}
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rig = rig if os.path.isabs(rig) else os.path.join(root, rig)
    ppl = json.load(open(rp))['ppl']
    table, checks, pics = {}, {}, []
    # the rig's eye_L layer is on the picture's left: our eye at -x
    for side_name, layer in (('R', 'eye_L'), ('L', 'eye_R')):
        E, parts = next(((E, p) for E, p in zip(S.character['data']['eyes'], S.character['eyes'])
                         if (E['side'] > 0) == (side_name == 'L')))
        tmp = os.path.join(out, f'qa_eye_{side_name}.png')
        ours_px = _eye_render(S, E, parts, tmp, ppl)
        des_px = _load_rgba(os.path.join(rig, 'build', layer + '.png'))
        mo, md = eyeqa.measure(ours_px, ppl), eyeqa.measure(des_px, ppl)
        table[side_name] = {'ours': {k: v for k, v in mo.items() if not k.startswith('_')},
                            'design': {k: v for k, v in md.items() if not k.startswith('_')}}
        c = eyeqa.compare(mo, md)
        for k, v in c.items():
            prev = checks.get(k)
            if prev is None or ['PASS', 'WARN', 'FAIL', 'SKIPPED'].index(v['status']) > ['PASS', 'WARN', 'FAIL', 'SKIPPED'].index(prev['status']):
                checks[k] = dict(v, eye=side_name)
        pics.append(eyeqa.picture(ours_px, des_px, mo, md))
    Hm = max(p.shape[0] for p in pics)
    _save_rgb(os.path.join(out, 'qa_eyes.png'), np.concatenate([np.pad(p, ((0, Hm - p.shape[0]), (0, 12), (0, 0)), constant_values=1.0) for p in pics], 1))
    return table, checks


def _load_rgba(path):
    import bpy
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, img.channels)[::-1]
    bpy.data.images.remove(img)
    if px.shape[2] == 3:
        px = np.concatenate([px, np.ones(px.shape[:2] + (1,), np.float32)], -1)
    return px


# --------------------------------------------------------------------------------------------------- model sheet
def sheet(S, out):
    """our face against the design's model sheet (charkit.sheetqa): the sheet measured at its scale (from the rig's
    front figure), ours rendered in flat class colours at the same scale and angles. -> (table, checks)."""
    from . import sheetqa
    ref = S.spec.get('ref') if isinstance(S.spec.get('ref'), dict) else {}
    sh = ref.get('sheet')
    rp = os.path.join(os.path.dirname(os.path.abspath(out)), 'ref_measure.json')
    if not sh or not ref.get('rig') or not os.path.exists(rp):
        return None, {'sheet': {'status': 'SKIPPED', 'why': 'no spec.ref.sheet / rig / ref_measure.json'}}
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fp = lambda p: p if os.path.isabs(p) else os.path.join(root, p)
    rgb = _load_rgba(fp(sh['image']))[..., :3]
    rig_alpha = _load_rgba(os.path.join(fp(ref['rig']), 'base.png'))[..., 3]
    A = S.character['data']; Hd = A['head']; L = Hd['L']
    ex = Hd['eye_knobs']['x']
    ppl = sheetqa.sheet_ppl(rgb, sh['front_figure'], rig_alpha, json.load(open(rp))['ppl'])
    D = sheetqa.measure_sheet(rgb, {k: tuple(v) for k, v in sh['heads'].items()}, ex, ppl=ppl)
    az3 = D.get('az_three_quarter', 35.0)
    # ours: every visible surface z-buffered at the sheet's scale, each triangle labelled by class
    from . import faceqa, trace
    CL = sheetqa.CLASS
    meshes = []
    skin = S.character['skin']
    V, F, mats = trace.mesh_arrays(skin, materials=True)
    T, poly = faceqa.triangles(*F)
    names = [(m.name if m else '').split('.')[0] for m in skin.data.materials]
    by = np.array([CL['skin'] if n in ('skin', 'face_skin') else CL['line'] if n in ('cavity', 'eyeline') else CL['other']
                   for n in names] or [CL['other']])
    meshes.append((V, T, by[mats[poly]]))
    part_cls = {'iris': CL['iris'], 'lash': CL['line'], 'brow': CL['line'], 'sclera': CL['other']}
    for p in S.character['eyes']:
        for k, c in part_cls.items():
            if p.get(k) is not None:
                v, f = trace.mesh_arrays(p[k]); t, _ = faceqa.triangles(*f)
                meshes.append((v, t, np.full(len(t), c)))
    for nm, o in S.character['mouth'].items():
        if o is not None:
            v, f = trace.mesh_arrays(o); t, _ = faceqa.triangles(*f)
            meshes.append((v, t, np.full(len(t), CL['line'] if 'line' in nm else CL['other'])))
    covers = []                                                        # hair and what it carries: coverage only
    for group, c, dst in ((S.hair, CL['hair'], covers), (S.accessories, CL['other'], covers), (S.garments, CL['other'], meshes)):
        for o in group:
            if o.type == 'MESH' and not o.hide_render:
                v, f = trace.mesh_arrays(o); t, _ = faceqa.triangles(*f)
                dst.append((v, t, np.full(len(t), c)))
    irc = [trace.mesh_arrays(p['iris'])[0].mean(0) for p in S.character['eyes']]     # iris centres (world)
    cx, cy = Hd['centre'][0], Hd['centre'][1]
    ez = float(np.mean([c[2] for c in irc]))
    pix = 1.0 / ppl
    win = faceqa.WIN
    O, raw = {}, {}
    for view, az in (('profile', 90.0), ('front', 0.0), ('three_quarter', az3)):
        a = math.radians(az)
        org = (cx * math.cos(a) + cy * math.sin(a), ez)
        # the face's shape without the hair (we know it underneath); how much of it the hair leaves showing apart
        depth, lab = faceqa.zbuffer(meshes, az, org, L, pix)
        lab = np.where(lab < 0, CL['other'], lab)
        face = faceqa.face_region(depth, np.where(lab == CL['skin'], 1, 0), 0.035 * L, pix=pix)
        dv, lv = faceqa.zbuffer(meshes + covers, az, org, L, pix)
        shown = face & (lv == CL['skin'])
        def px(P):
            u, z, _ = faceqa.view(np.asarray(P, float)[None], az)
            return (float(((u[0] - org[0]) / L + win['x']) / pix), float((win['top'] - (z[0] - org[1]) / L) / pix))
        eyes = sorted(px(c) for c in irc)
        if view == 'profile':
            eyes = [px(max(irc, key=lambda c: c[0]))]                  # the near eye from +x: the character's left
        raw[view] = (lab, face, shown, eyes, depth, lv)
    # our chin: where the profile's front edge turns back to the neck (the under-chin runs smoothly into the neck, so
    # the face region alone doesn't stop there); every view's face is cut below it, as a drawn jaw line cuts the design's
    lab, face, shown, eyes, depth, lv = raw['profile']
    M = sheetqa.measure_labels(lab, face, 'profile', ppl, eyes)
    chin = faceqa.chin_bottom(-M['lead'], M['z'])
    for view, (lab, face, shown, eyes, depth, lv) in raw.items():
        zr = (np.mean([e[1] for e in eyes]) - np.arange(face.shape[0])) / ppl
        if chin is not None:
            # the skin below the chin out first, then the fill again: the neck beside the chin can then only be reached
            # across the jaw's depth jump
            skin = (lab == CL['skin']) & (zr >= chin)[:, None]
            face = faceqa.face_region(depth, skin.astype(int), 0.035 * L, pix=pix)
            shown = face & (lv == CL['skin'])
        O[view] = sheetqa.measure_labels(lab, face, view, ppl, eyes)
        O[view]['shown'] = round(float(shown.sum() / max(1, face.sum())), 3)
    C = sheetqa.compare(O, D)
    for view in ('front', 'three_quarter', 'profile'):             # the design's face is drawn as it shows: all of it
        if view in O and view in D:
            dsh = float((D[view]['face'] & (D[view]['z'][:, None] < -0.02)).sum())
            osh = float((O[view]['face'] & (O[view]['z'][:, None] < -0.02)).sum()) * O[view]['shown']
            r = round(osh / max(1.0, dsh), 3)
            C['shown_' + view] = {'value': r, 'status': 'PASS' if abs(r - 1) <= 0.2 else 'WARN',
                                  'note': 'our lower face left showing by the hair, against the design\'s (warns only)'}
    _save_rgb(os.path.join(out, 'qa_sheet.png'), sheetqa.picture(O, D))
    strip = lambda M: {k: v for k, v in M.items() if not isinstance(v, np.ndarray) and k not in ('face', 'lab', 'z', 'lead')}
    table = {'ppl': ppl, 'az_three_quarter': az3, 'design': {v: strip(D[v]) for v in ('front', 'three_quarter', 'profile') if v in D},
             'ours': {v: strip(O[v]) for v in O}}
    return table, C


# --------------------------------------------------------------------------------------------------- model sheet: materials
def _srgb(c):
    c = np.clip(np.asarray(c, float)[:3], 0, None)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def material_tones(m):
    """what a material renders unlit, read from its nodes (no override, no render): toon3's lit, shade and deep tones (sRGB)
    or a flat emission's colour, and the image a texture multiplies in (a textured toon, an eye plate) or None.
    -> dict(lit, shade, deep, image)."""
    out = dict(lit=None, shade=None, deep=None, image=None)
    if m is None or not m.use_nodes:
        return out
    nodes = m.node_tree.nodes
    for n in nodes:                     # toon3: the lit mix takes the shade/deep mix in A and the lit tone in B
        if n.type == 'MIX' and getattr(n, 'data_type', '') == 'RGBA' and n.blend_type == 'MIX' and \
                n.inputs['A'].is_linked and not n.inputs['B'].is_linked:
            src = n.inputs['A'].links[0].from_node
            if src.type == 'MIX' and not src.inputs['A'].is_linked and not src.inputs['B'].is_linked:
                out.update(lit=_srgb(n.inputs['B'].default_value), shade=_srgb(src.inputs['B'].default_value),
                           deep=_srgb(src.inputs['A'].default_value))
                break
    for n in nodes:
        if n.type == 'MIX' and getattr(n, 'data_type', '') == 'RGBA' and n.blend_type == 'MULTIPLY' and \
                not n.inputs['Factor'].is_linked and n.inputs['B'].is_linked and n.inputs['B'].links[0].from_node.type == 'TEX_IMAGE':
            out['image'] = n.inputs['B'].links[0].from_node.image                    # a textured toon (skirt, panel)
    em = next((n for n in nodes if n.type == 'EMISSION'), None)
    if out['lit'] is None and em is not None:
        c = em.inputs['Color']
        if not c.is_linked:
            out['lit'] = out['shade'] = out['deep'] = _srgb(c.default_value)
        elif c.links[0].from_node.type == 'TEX_IMAGE':                                # a plate: the image is the colour
            out['image'] = c.links[0].from_node.image
            out['lit'] = out['shade'] = out['deep'] = np.ones(3)
    return out


_IMAGES = {}


def _image_px(img):
    """a Blender image's pixels as stored (rows bottom-up, RGBA; charkit's images hold sRGB values), cached."""
    if img.name not in _IMAGES:
        w, h = img.size
        px = np.empty(w * h * img.channels, np.float32); img.pixels.foreach_get(px)
        px = px.reshape(h, w, img.channels)
        if img.channels == 3:
            px = np.concatenate([px, np.ones((h, w, 1), np.float32)], -1)
        _IMAGES[img.name] = px
    return _IMAGES[img.name]


def poly_colours(ob, mats, puv):
    """per polygon of an evaluated mesh: the sRGB lit and shade colours its material renders unlit (a texture sampled at
    the polygon's UV centre and multiplied in) and the texture's alpha there (1 without one). -> (lit (nf, 3), shade
    (nf, 3), alpha (nf,))."""
    nf = len(mats)
    lit, shd, alpha = np.full((nf, 3), 0.5), np.full((nf, 3), 0.5), np.ones(nf)
    for mi in np.unique(mats):
        sel = mats == mi
        m = ob.data.materials[mi] if mi < len(ob.data.materials) else None
        t = material_tones(m)
        if t['lit'] is not None:
            lit[sel], shd[sel] = t['lit'], t['shade']
        if t['image'] is not None and np.isfinite(puv[sel]).all():
            px = _image_px(t['image'])
            h, w = px.shape[:2]
            uv = np.clip(puv[sel], 0, 1 - 1e-6)
            tx = px[(uv[:, 1] * h).astype(int), (uv[:, 0] * w).astype(int)]
            lit[sel] = lit[sel] * tx[:, :3]; shd[sel] = shd[sel] * tx[:, :3]; alpha[sel] = tx[:, 3]
    return lit, shd, alpha


def _tri_area(V, T):
    return 0.5 * np.linalg.norm(np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]]), axis=1)


def scene_classes(S):
    """every visible surface of the character as triangles with a model-sheet class each (charkit.bodyqa.CLASS), by object:
    the skin (its garment mask on: what the clothes hide stays hidden) by material (skin, the mouth's cavity and the eye
    line as line), the eye plates (iris where its texture is opaque, the sclera white), lashes and brows as line, the
    teeth white, the hair, accessories and garments by their colour family (an orange accessory sits in the hair).
    -> ([(V, T, labels)], {class: [(lit, shade, area)]}) (the colours per class for the palette)."""
    from . import bodyqa, faceqa, trace
    CL = bodyqa.CLASS
    meshes, cols = [], {}

    def put(ob, labels_fn, skip=trace.OUTLINE_MODS):
        V, F, mats, puv = trace.mesh_arrays(ob, materials=True, uv='uv', skip=skip)
        T, poly = faceqa.triangles(*F)
        if not len(T):
            return
        lit, shd, alpha = poly_colours(ob, mats, puv)
        lab = labels_fn(mats[poly], lit[poly], alpha[poly])
        keep = lab >= 0
        T, lab, poly = T[keep], lab[keep], poly[keep]
        meshes.append((V, T, lab))
        area = _tri_area(V, T)
        for c in np.unique(lab):
            s = lab == c
            cols.setdefault(int(c), []).extend(zip(map(tuple, lit[poly][s]), map(tuple, shd[poly][s]), area[s]))
    skin = S.character['skin']
    names = [(m.name if m else '').split('.')[0] for m in skin.data.materials]
    by = np.array([CL['skin'] if n in ('skin', 'face_skin') else CL['line'] if n in ('cavity', 'eyeline') else CL['other']
                   for n in names] or [CL['other']])
    put(skin, lambda mi, c, a: by[mi], skip=('outline',))
    for p in S.character['eyes']:
        for k, c_ in (('iris', CL['iris']), ('sclera', CL['white']), ('lash', CL['line']), ('brow', CL['line'])):
            if p.get(k) is not None:
                put(p[k], lambda mi, c, a, c_=c_, k=k: np.where(a >= 0.5, c_, -1) if k == 'iris' else np.full(len(mi), c_))
    for nm, o in S.character['mouth'].items():
        if o is not None:
            c_ = CL['white'] if nm == 'teeth' else CL['line'] if 'line' in nm else CL['other']
            put(o, lambda mi, c, a, c_=c_: np.full(len(mi), c_))
    for o in S.hair:
        if o.type == 'MESH' and not o.hide_render:
            put(o, lambda mi, c, a: np.full(len(mi), CL['hair']))
    for o in S.accessories:
        if o.type == 'MESH' and not o.hide_render:
            put(o, lambda mi, c, a: np.where(bodyqa.family(c) == CL['orange'], CL['hair'], bodyqa.family(c)))
    for o in S.garments:
        if o.type == 'MESH' and not o.hide_render:
            put(o, lambda mi, c, a: bodyqa.family(c))
    return meshes, cols


def _sheet_context(S, out=None):
    """the design's model sheet, loaded and measured once per QA pass: the picture, its scale (the front figure's height
    against the rig's), its figures (detected; the spec's head boxes where it has them) and the three-quarter's angle."""
    if getattr(S, '_sheet_ctx', None) is not None:
        return S._sheet_ctx
    from . import sheetqa
    ref = S.spec.get('ref') if isinstance(S.spec.get('ref'), dict) else {}
    sh = ref.get('sheet')
    rp = os.path.join(os.path.dirname(os.path.abspath(out)), 'ref_measure.json') if out else None
    if not sh or not ref.get('rig') or not rp or not os.path.exists(rp):
        S._sheet_ctx = {'why': 'no spec.ref.sheet / rig / ref_measure.json'}
        return S._sheet_ctx
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fp = lambda p: p if os.path.isabs(p) else os.path.join(root, p)
    rgb = _load_rgba(fp(sh['image']))[..., :3].astype(float)
    rig_alpha = _load_rgba(os.path.join(fp(ref['rig']), 'base.png'))[..., 3]
    ex = S.character['data']['head']['eye_knobs']['x']
    ppl = sheetqa.sheet_ppl(rgb, sh['front_figure'], rig_alpha, json.load(open(rp))['ppl'])
    D = sheetqa.detect_figures(rgb, ppl=ppl, eye_x=ex, facing=sh.get('facing'))
    fe = D['figures'].get('front', {}).get('eyes') or []
    ppl_eyes = abs(fe[1][0] - fe[0][0]) / (2 * ex) if len(fe) == 2 else None
    te = D['figures'].get('three_quarter', {}).get('eyes') or []
    az3 = float(np.degrees(np.arccos(np.clip(abs(te[1][0] - te[0][0]) / (2 * ex * ppl), 0, 1)))) if len(te) == 2 else 35.0
    heads = {k: tuple(v) for k, v in (sh.get('heads') or {}).items()} or \
        {v: tuple(D['figures'][v]['head']) for v in ('front', 'three_quarter', 'profile') if v in D['figures']}
    S._sheet_ctx = dict(rgb=rgb, ppl=ppl, ppl_eyes=ppl_eyes, D=D, az3=round(az3, 1), heads=heads, eye_x=ex,
                        verify=sheetqa.verify_figures(D, sh))
    return S._sheet_ctx


def _scale_caution(ctx):
    """a caution when the sheet's two scales disagree (the rig-matched figure height against the small eye spacing)."""
    if ctx.get('ppl_eyes'):
        d = ctx['ppl_eyes'] / ctx['ppl'] - 1
        if abs(d) > 0.03:
            return 'scale: the sheet\'s eye spacing reads %+.1f%% against its figure height (used); lengths far from the ' \
                   'eyes carry it (%.2f L at the feet)' % (100 * d, abs(d) * 5.2)
    return None


def expression_data(S):
    """the head's parts for charkit.exprqa as numpy: the base meshes as posed (armature only: vertices match the shape keys)
    with a class per triangle and each expression key's world offsets (sparse). Only the skin's front head faces are kept;
    no hair (the features are measured, the drawing's brows only where its fringe shows them).
    -> dict(parts [(name, V, T, labels, {key: (idx, D)})], eye_z, L)."""
    from . import exprqa, faceqa, trace
    CL = exprqa.CLASS
    Hd = S.character['data']['head']; L = Hd['L']; c = np.asarray(Hd['centre'], float)
    parts = []

    def put(name, ob, labels_fn, keep_fn=None):
        skip = tuple(m.name for m in ob.modifiers if m.type != 'ARMATURE')
        V, F, mats, puv = trace.mesh_arrays(ob, materials=True, uv='uv', skip=skip)
        T, poly = faceqa.triangles(*F)
        lit, _, alpha = poly_colours(ob, mats, puv)
        lab = labels_fn(mats[poly], alpha[poly])
        ok = lab >= 0
        if keep_fn is not None:
            ok &= keep_fn(V[T].mean(1))
        T, lab = T[ok], lab[ok]
        keys = {}
        ks = ob.data.shape_keys
        if ks:
            n = len(ob.data.vertices)
            base = np.empty(n * 3); ks.key_blocks[0].data.foreach_get('co', base)
            M3 = np.array(ob.matrix_world)[:3, :3]
            for kb in ks.key_blocks[1:]:
                if kb.name.startswith(('eye_', 'mouth_', 'brow_')) and not kb.name.endswith(('_L', '_R')):
                    co = np.empty(n * 3); kb.data.foreach_get('co', co)
                    d = ((co - base).reshape(-1, 3)) @ M3.T
                    idx = np.nonzero(np.abs(d).max(1) > 1e-7)[0]
                    keys[kb.name] = (idx, d[idx])
        parts.append((name, V, T, lab, keys))
    skin = S.character['skin']
    names = [(m.name if m else '').split('.')[0] for m in skin.data.materials]
    by = np.array([CL['skin'] if n in ('skin', 'face_skin') else CL['mouth'] if n == 'cavity' else CL['line'] if n == 'eyeline'
                   else -1 for n in names] or [-1])
    head = lambda P: (P[:, 2] > c[2] - 0.85 * L) & (P[:, 2] < c[2] + 0.55 * L) & (P[:, 1] < c[1] + 0.1 * L)
    put('skin', skin, lambda mi, a: by[mi], head)
    for p in S.character['eyes']:
        for k, cl in (('iris', CL['iris']), ('sclera', CL['white']), ('lash', CL['line']), ('brow', CL['brow'])):
            if p.get(k) is not None:
                put(p[k].name, p[k], lambda mi, a, cl=cl, k=k: np.where(a >= 0.5, cl, -1) if k == 'iris' else np.full(len(mi), cl))
    for nm, o in S.character['mouth'].items():
        if o is not None:
            cl = CL['white'] if nm == 'teeth' else CL['mouth'] if nm == 'tongue' else CL['line']
            put(nm, o, lambda mi, a, cl=cl: np.full(len(mi), cl))
    iw = [trace.mesh_arrays(p['iris'])[0].mean(0) for p in S.character['eyes']]
    return dict(parts=parts, eye_z=float(np.mean([w[2] for w in iw])), L=L)


def sheet_expressions(S, out):
    """the sheet's expression heads against the kit's expression library (charkit.exprqa) -> (table, checks)."""
    from . import exprqa
    ctx = _sheet_context(S, out)
    if 'why' in ctx:
        return None, {'expr': {'status': 'SKIPPED', 'why': ctx['why']}}
    if not ctx['D']['expressions']:
        return None, {'expr': {'status': 'SKIPPED', 'why': 'no expression heads found on the sheet'}}
    table, C, pic = exprqa.sheet_run(expression_data(S), ctx['rgb'], ctx['D'], ctx['eye_x'])
    _save_rgb(os.path.join(out, 'qa_sheet_expr.png'), pic)
    return table, C


def sheet_body(S, out):
    """the whole character against the design's full figures (charkit.bodyqa): front, three-quarter, profile, back, each
    z-buffered at the sheet's scale from the same azimuth with a class per triangle, aligned on the eyes. -> (table,
    checks)."""
    from . import bodyqa, trace
    ctx = _sheet_context(S, out)
    if 'why' in ctx:
        return None, {'body': {'status': 'SKIPPED', 'why': ctx['why']}}
    meshes, cols = scene_classes(S)
    S._sheet_colours = cols
    Hd = S.character['data']['head']
    iw = np.array([trace.mesh_arrays(p['iris'])[0].mean(0) for p in S.character['eyes']])       # iris centres (world)
    table, C, views = bodyqa.sheet_views(meshes, ctx['rgb'], ctx['D'], ctx['ppl'], ctx['az3'], iw, Hd['centre'], Hd['L'],
                                         _scale_caution(ctx))
    if views:
        _save_rgb(os.path.join(out, 'qa_sheet_body.png'), bodyqa.picture(views))
    return table, C


# --------------------------------------------------------------------------------------------------- face shape
FACE_PARTS =('sclera', 'iris', 'lash', 'brow', 'teeth', 'tongue', 'mouth_line', 'line')


def face_shape(S, out):
    """our face against the generated character's (charkit.faceqa), from the scene's meshes. -> (result, checks)."""
    from . import faceqa, trace
    full, cols = getattr(S, 'shape_full', None), getattr(S, 'shape_colors', None)
    if full is None or cols is None:
        return None, {'face_shape': {'status': 'SKIPPED', 'why': 'no generated shape in this build'}}
    A = S.character['data']; Hd = A['head']; L = Hd['L']
    skin = S.character['skin']
    V, F, mats = trace.mesh_arrays(skin, materials=True)
    T, poly = faceqa.triangles(*F)
    names = [m.name if m else '' for m in skin.data.materials]
    is_skin = np.isin(mats[poly], [i for i, n in enumerate(names) if n in ('skin', 'face_skin')])
    ours = [(V, T, is_skin, True)]
    face_obs = [p[k] for p in S.character['eyes'] for k in ('sclera', 'iris', 'lash', 'brow') if p.get(k) is not None]
    face_obs += [o for o in S.character['mouth'].values() if o is not None]
    others = list(S.hair) + list(S.accessories) + list(S.garments)
    for obs, face in ((face_obs, True), (others, False)):
        for o in obs:
            if o.type != 'MESH' or o.hide_render:
                continue
            v, f = trace.mesh_arrays(o)
            t, _ = faceqa.triangles(*f)
            ours.append((v, t, np.zeros(len(t), bool), face))
    ez = float(np.mean([E['c'][1] for E in A['eyes']]))
    Vb = A['verts']
    mid = (np.abs(Vb[:, 0]) < 0.01 * L) & (Vb[:, 2] < ez - 0.05 * L) & (Vb[:, 2] > ez - 0.25 * L)
    lm = dict(L=L, eye_z=ez, centre=list(Hd['centre']), mouth_z=float(A['mouth']['c'][1]))
    if mid.any():
        lm['nose_z'] = float(Vb[mid][np.argmin(Vb[mid][:, 1]), 2])
    brows = [p['brow'] for p in S.character['eyes'] if p.get('brow') is not None]
    if brows:
        lm['brow_z'] = float(np.mean([trace.mesh_arrays(b)[0][:, 2].mean() for b in brows]))
    ref = None
    rp = os.path.join(os.path.dirname(os.path.abspath(out)), 'ref_measure.json')
    if os.path.exists(rp):
        ref = json.load(open(rp))
    R = faceqa.measure(ours, (np.asarray(full[0]), np.asarray(full[1]), np.asarray(cols)), lm, ref)
    _save_rgb(os.path.join(out, 'qa_face_shape.png'), faceqa.overlay(R))
    _save_rgb(os.path.join(out, 'qa_face_contours.png'), faceqa.contours_image(R))
    C = faceqa.checks(R)
    return {k: v for k, v in R.items() if not k.startswith('_')}, C


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
    old_dither = sc.render.dither_intensity
    try:
        vl.material_override = override
        sc.render.film_transparent = transparent
        # no dither: the measures below read flat toon tones, and +-0.5/255 of dither noise inside a tone splits it at
        # a luminance percentile (hair_noise read 0.19-0.73 on renders that measure 0.006-0.014 without it)
        sc.render.dither_intensity = 0.0
        sc.camera = cam.ob
        cam.aim(az)
        sc.render.resolution_x, sc.render.resolution_y = cam.res
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
    finally:
        vl.material_override = old_ov; sc.render.film_transparent = old_ft; sc.camera = old_cam
        sc.render.dither_intensity = old_dither
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
def _face_normals(V, faces):
    Q = np.array([tuple(f) + (f[-1],) * (4 - len(f)) for f in faces])      # triangles padded (their normal is unchanged)
    n = np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 1]])
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-15)


def face_folds(A):
    """skin faces round the eyes and the mouth (the openings' own walls, fmat 2 and 3, left out) facing away from the viewer
    at rest, and flipped (turned past 90 degrees) or facing away under each lid and mouth key. numpy only.
    -> dict(rest, keys {key: count}, total)."""
    V = np.asarray(A['verts']); F = A['faces']; fm = np.asarray(A['fmat']); Hd = A['head']; L = Hd['L']
    q = (np.array([V[list(f)].mean(0) for f in F]) - Hd['centre']) / L
    mouth = (fm == 1) & (np.abs(q[:, 0]) < 0.16) & (np.abs(q[:, 2] + 0.28) < 0.1) & (q[:, 1] < -0.2)
    eyes = (fm == 1) & (np.abs(np.abs(q[:, 0]) - 0.17) < 0.14) & (np.abs(q[:, 2]) < 0.12) & (q[:, 1] < -0.15)
    n0 = _face_normals(V, F)
    rest = int(((mouth | eyes) & (n0[:, 1] > 0.2)).sum())
    keys = {}
    for sh, D in A['mouth']['keys'].items():
        n1 = _face_normals(V + D, F)
        keys['mouth_' + sh] = int((mouth & (((n0 * n1).sum(1) < 0) | (n1[:, 1] > 0.2))).sum())
    for sh in A['eyes'][0]['keys']:
        n1 = _face_normals(V + sum(E['keys'][sh][0] for E in A['eyes']), F)
        keys['eye_' + sh] = int((eyes & (((n0 * n1).sum(1) < 0) | (n1[:, 1] > 0.2))).sum())
    return dict(rest=rest, keys=keys, total=rest + sum(keys.values()))


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
    # --- face folds: the skin round the openings at rest and under the keys
    ff = face_folds(A)
    rep['checks']['face_folds'] = {'value': ff['total'], 'rest': ff['rest'], 'per_key': ff['keys'],
                                   'base': S.spec.get('base', 'makehuman'), 'status': _grade('face_folds', ff['total'], False)}
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
    # --- the eyes against the design's
    try:
        rep['eyes'], ec = eyes(S, out)
        rep['checks'].update({'eye_' + k: v for k, v in ec.items()})
    except Exception as e:
        import traceback; traceback.print_exc()
        rep['checks']['eye'] = {'status': 'SKIPPED', 'why': '%s: %s' % (type(e).__name__, e)}
    # --- the face against the design's model sheet
    try:
        rep['sheet'], sc_ = sheet(S, out)
        rep['checks'].update({'sheet_' + k: v for k, v in sc_.items()})
    except Exception as e:
        import traceback; traceback.print_exc()
        rep['checks']['sheet'] = {'status': 'SKIPPED', 'why': '%s: %s' % (type(e).__name__, e)}
    # --- the whole character against the sheet's full figures
    try:
        rep['sheet_body'], sc_ = sheet_body(S, out)
        rep['checks'].update({'body_' + k: v for k, v in sc_.items()})
    except Exception as e:
        import traceback; traceback.print_exc()
        rep['checks']['body'] = {'status': 'SKIPPED', 'why': '%s: %s' % (type(e).__name__, e)}
    # --- the face's shape against the generated character's
    try:
        rep['face_shape'], fc = face_shape(S, out)
        rep['checks'].update({('face_shape_' + k if not k.startswith('face_shape') else k): v for k, v in fc.items()})
    except Exception as e:
        import traceback; traceback.print_exc()
        rep['checks']['face_shape'] = {'status': 'SKIPPED', 'why': '%s: %s' % (type(e).__name__, e)}
    # --- the face's expressions and mouth shapes (geometry)
    try:
        rep['face'], fc = face(S)
        rep['checks'].update({'face_' + k: v for k, v in fc.items()})
    except Exception as e:                                         # a face check that can't run says so, the rest stands
        rep['checks']['face'] = {'status': 'SKIPPED', 'why': '%s: %s' % (type(e).__name__, e)}
    if os.path.exists(tmp):
        os.remove(tmp)
    order = {'FAIL': 0, 'WARN': 1, 'PASS': 2}
    graded = [c['status'] for c in rep['checks'].values() if c.get('status') in order]
    rep['summary'] = min(graded, key=lambda s: order[s]) if graded else 'SKIPPED'
    json.dump(rep, open(os.path.join(out, 'qa.json'), 'w'), indent=1)
    return rep
