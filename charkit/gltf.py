"""charkit/gltf.py: our own glTF 2.0 / VRM 1.0 writer for a built charkit character (numpy + bpy, no add-on), so the look
runs in code we control (engine/three/charkit/, docs/CHARKIT.md §2 "export and QA").

    blender -b --factory-startup charkit/out/clawd/clawd.blend --python charkit/gltf.py -- charkit/out/clawd/clawd.vrm
    python -m charkit export charkit/out/clawd/clawd.blend                       # the same, through charkit/cli.py
    from charkit import gltf; gltf.export_scene(S, 'out/clawd.vrm')              # inside Blender, from scene.build's Scene

What is written (one GLB with a .vrm extension; readable by any glTF 2.0 loader):
  skeleton     the armature's bones as nodes with identity rotations (axes = the glTF frame: Y up, facing +Z, her left +X),
               put into the T-pose VRM 1.0 requires (arms and legs straightened); the meshes keep the build's A-pose bind
               (the inverse bind matrices are the A-pose), so nothing is re-baked and every shape key stays exact.
               extensions.OPENADS_charkit_look.bindPose holds the normalized-bone rotations that bring the build pose back.
  meshes       every visible mesh as Blender renders it (modifiers evaluated: the garment mask, subdivision at --subdiv,
               default 2 = the skin's render level (level 1 visibly moves the creased eye margins), garment thickness, the
               hair's transferred envelope normals baked into NORMAL), without its armature and outline modifiers; one
               primitive per material, each with its own compacted vertices. POSITION is the surface Blender draws: charkit's
               outline SOLIDIFY (offset 1, negative thickness) moves the surface inward by the line width, so it is baked in,
               and the hull (drawn by the runtime, or MToon) goes back out by the same amount.
  attributes   JOINTS_0/WEIGHTS_0 (top four), TEXCOORD_0 = the 'uv' layer, TEXCOORD_1 = 'face' (the skin's front projection:
               the SDF, fringe and blush maps) or 'lock' (analytic hair: across, along); custom: _OUTLINE_WIDTH (0..1, the
               outline's per-vertex factor: 0 round the eye and mouth openings, fading at hair tips), _FACE_MASK (1 on the
               face, where the SDF shading replaces toon3), _HULL_NORMAL (the direction the hull extrudes along, where it differs
               from NORMAL: custom or flat normals).
  morphs       every shape key (eye_*, mouth_*, brow_*, look_*) as a sparse POSITION morph target (names in
               extras.targetNames), plus NORMAL targets on outlined meshes from the keyed hull directions (Blender rebuilds
               the outline after the keys). A keyed mesh splits into NAME (the triangles its keys move, with the targets) and
               NAME.static (the rest): a runtime's morph buffers cover only the moving part.
  textures     PNG: eye plates, the face SDF (16-bit packed into R (high) and G (low) bytes, B = R), fringe and blush maps,
               garment textures.
  materials    OPENADS_charkit_look (below) with each material's own parameters, plus a VRMC_materials_mtoon fallback.
  VRMC_vrm     humanoid (every bone already has its VRM 1.0 name), meta, expressions from our keys (visemes aa ih ou ee oh, blink
               and the per-eye blinks, happy angry sad relaxed surprised, lookUp/Down/Left/Right from the iris keys, lookAt type
               'expression'), and every other key as a custom expression of its own name.

The extension OPENADS_charkit_look (version 1), in the glTF frame, colours linear:
  root      {version, character, light: {direction}, head: {bone, centre, L}, height, features: {through: 0.55},
             bindPose: {bone: quat}}
  material  {kind: toon3 | face | hair | flat | plate, role, doubleSided, alpha: opaque | blend,
             toon3/face/hair: lit, shade, deep, threshold, deepThreshold, softness, rim: {color, amount, facing, range}, texture?,
             face: {sdf, fringe, blush (textureInfo), softness, fringeRange, mask: '_FACE_MASK'},
             hair: {lock: texCoord, ring: {color, elevation, centre, width, soft, facing, mid, amount}, gradient, strands},
             flat: color; plate: texture}
  mesh      {object, outline?: {width (m), color, widthAttribute?, normalAttribute?}, feature?: true, holdout?: true}
"""
import json, math, os, struct, sys, zlib

import numpy as np

EXT = 'OPENADS_charkit_look'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C3 = np.array([[1.0, 0, 0], [0, 0, 1.0], [0, -1.0, 0]])      # Blender (Z up, facing -Y) -> glTF (Y up, facing +Z)
FEATURES = ('sclera_', 'iris_', 'lash_', 'brow_')             # drawn again over the hair (charkit.qa.features_through)
THROUGH = 0.55

# VRM preset expressions from our shape keys: {expression: ({key: weight}, side, overrides)}; side 'L'/'R' takes the key's
# per-side version (eye_blink_L on the skin, eye_blink on the lash_L / sclera_L / iris_L objects)
PRESETS = {
    'aa': ({'mouth_aa': 1.0}, None, {}), 'ih': ({'mouth_ih': 1.0}, None, {}), 'ou': ({'mouth_ou': 1.0}, None, {}),
    'ee': ({'mouth_ee': 1.0}, None, {}), 'oh': ({'mouth_oh': 1.0}, None, {}),
    'blink': ({'eye_blink': 1.0}, None, {}),
    'blinkLeft': ({'eye_blink': 1.0}, 'L', {}), 'blinkRight': ({'eye_blink': 1.0}, 'R', {}),
    'happy': ({'eye_happy': 1.0, 'brow_relaxed': 1.0, 'mouth_smile': 1.0}, None, {'overrideBlink': 'block', 'overrideLookAt': 'block'}),
    'angry': ({'eye_angry': 1.0, 'brow_angry': 1.0, 'mouth_frown': 0.6}, None, {'overrideBlink': 'blend'}),
    'sad': ({'eye_sad': 1.0, 'brow_sad': 1.0, 'mouth_frown': 1.0}, None, {'overrideBlink': 'blend'}),
    'relaxed': ({'eye_half': 0.6, 'brow_relaxed': 1.0, 'mouth_smile': 0.6}, None, {'overrideBlink': 'blend'}),
    'surprised': ({'eye_wide': 1.0, 'brow_surprised': 1.0, 'mouth_surprised': 1.0}, None, {'overrideBlink': 'blend'}),
    'lookUp': ({'look_up': 1.0}, None, {}), 'lookDown': ({'look_down': 1.0}, None, {}),
    'lookLeft': ({'look_left': 1.0}, None, {}), 'lookRight': ({'look_right': 1.0}, None, {}),
}
META = {
    'licenseUrl': 'https://vrm.dev/licenses/1.0/', 'avatarPermission': 'onlyAuthor', 'commercialUsage': 'corporation',
    'creditNotation': 'unnecessary', 'allowRedistribution': False, 'modification': 'prohibited',
    'allowExcessivelyViolentUsage': False, 'allowExcessivelySexualUsage': False, 'allowPoliticalOrReligiousUsage': False,
    'allowAntisocialOrHateUsage': False, 'authors': ['animation-pipeline (charkit)'], 'version': 'charkit',
}


def g3(v):
    """Blender vectors (..., 3) -> glTF frame."""
    return np.asarray(v, float) @ C3.T


def srgb(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.clip(c, 0, None) ** (1 / 2.4) - 0.055)


def r6(x):
    return [round(float(v), 6) for v in np.ravel(x)]


# ------------------------------------------------------------------------------------------------------------------ PNG
def png(a):
    """(h, w, c) uint8 -> PNG bytes (no PIL in Blender's Python)."""
    a = np.ascontiguousarray(a, np.uint8)
    h, w, c = a.shape
    raw = np.concatenate([np.zeros((h, 1), np.uint8), a.reshape(h, w * c)], 1).tobytes()
    chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    ct = {1: 0, 2: 4, 3: 2, 4: 6}[c]
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, ct, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


def image_pixels(img):
    """a Blender image -> (h, w, 4) float, row 0 = top; byte images in their stored (sRGB) encoding, float ones linear."""
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    return px.reshape(h, w, 4)[::-1]


# ------------------------------------------------------------------------------------------------------------ the writer
class Writer:
    """the GLB under construction: JSON + one binary buffer."""

    def __init__(self):
        self.js = {'asset': {'version': '2.0', 'generator': 'charkit/gltf.py'}, 'scene': 0, 'scenes': [{'nodes': []}],
                   'nodes': [], 'meshes': [], 'materials': [], 'textures': [], 'images': [], 'samplers': [],
                   'accessors': [], 'bufferViews': [], 'buffers': [], 'skins': [], 'extensionsUsed': [],
                   'extensions': {}}
        self.bin = bytearray()

    def view(self, data, target=None):
        while len(self.bin) % 4:
            self.bin.append(0)
        bv = {'buffer': 0, 'byteOffset': len(self.bin), 'byteLength': len(data)}
        if target:
            bv['target'] = target
        self.bin += data
        self.js['bufferViews'].append(bv)
        return len(self.js['bufferViews']) - 1

    def accessor(self, arr, kind, ctype=None, target=None, minmax=False, normalized=False):
        arr = np.ascontiguousarray(arr)
        ctype = ctype or {np.dtype('float32'): 5126, np.dtype('uint32'): 5125, np.dtype('uint16'): 5123,
                          np.dtype('uint8'): 5121}[arr.dtype]
        n = arr.shape[0]
        a = {'bufferView': self.view(arr.tobytes(), target), 'componentType': ctype, 'count': int(n), 'type': kind}
        if normalized:
            a['normalized'] = True
        if minmax:
            flat = arr.reshape(n, -1)
            a['min'] = [float(x) for x in flat.min(0)]; a['max'] = [float(x) for x in flat.max(0)]
        self.js['accessors'].append(a)
        return len(self.js['accessors']) - 1

    def sparse_vec3(self, d, eps=1e-7):
        """a morph target's POSITION deltas (n, 3) as a sparse accessor (zeros where nothing moves)."""
        d = np.ascontiguousarray(d, np.float32)
        nz = np.nonzero(np.abs(d).max(1) > eps)[0].astype(np.uint32)
        zeros = len(nz) < len(d)                          # min/max are those of the values after substitution
        lo = d[nz].min(0) if len(nz) else np.zeros(3); hi = d[nz].max(0) if len(nz) else np.zeros(3)
        if zeros:
            lo, hi = np.minimum(lo, 0), np.maximum(hi, 0)
        a = {'componentType': 5126, 'count': int(len(d)), 'type': 'VEC3',
             'min': [float(x) for x in lo], 'max': [float(x) for x in hi]}
        if len(nz):
            a['sparse'] = {'count': int(len(nz)), 'indices': {'bufferView': self.view(nz.tobytes()), 'componentType': 5125},
                           'values': {'bufferView': self.view(d[nz].tobytes())}}
        self.js['accessors'].append(a)
        return len(self.js['accessors']) - 1

    def image(self, name, data):
        self.js['images'].append({'name': name, 'mimeType': 'image/png', 'bufferView': self.view(data)})
        return len(self.js['images']) - 1

    def use(self, ext):
        if ext not in self.js['extensionsUsed']:
            self.js['extensionsUsed'].append(ext)

    def glb(self, path):
        js = {k: v for k, v in self.js.items() if v != [] and v != {}}
        js['buffers'] = [{'byteLength': len(self.bin)}]
        j = json.dumps(js, separators=(',', ':')).encode()
        j += b' ' * (-len(j) % 4)
        b = bytes(self.bin) + b'\0' * (-len(self.bin) % 4)
        out = struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(j) + 8 + len(b))
        out += struct.pack('<II', len(j), 0x4E4F534A) + j + struct.pack('<II', len(b), 0x004E4942) + b
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        open(path, 'wb').write(out)
        return len(out)


# ------------------------------------------------------------------------------------------------ reading our materials
def _links_from(sock):
    return [l.from_node for l in sock.links] if sock.is_linked else []


def _col(sock):
    return [round(float(x), 6) for x in sock.default_value[:3]]


def material_look(m):
    """one of charkit's emission materials (shade.toon3 / flat / plate, faceshade.material, hair.material, garments._toon_tex)
    -> the OPENADS_charkit_look description (colours linear, as stored). Images are returned as Blender images under
    '_images' (the writer turns them into textures)."""
    nt = m.node_tree if m else None
    d = {'kind': 'flat', 'role': m.name if m else 'none', 'doubleSided': not (m and m.use_backface_culling),
         'alpha': 'opaque', '_images': {}}
    if nt is None:
        d['color'] = [0.8, 0.8, 0.8]
        return d
    N = nt.nodes
    em = next((n for n in N if n.type == 'EMISSION'), None)
    if em is None:
        d['color'] = [0.8, 0.8, 0.8]
        return d
    if not em.inputs['Color'].is_linked:
        d['color'] = _col(em.inputs['Color'])
        return d
    if 'ldir' not in N:                                            # a plate: an image straight to the emission
        tx = _links_from(em.inputs['Color'])[0]
        if tx.type == 'TEX_IMAGE':
            uvn = _links_from(tx.inputs['Vector'])
            d.update(kind='plate', texture={'_image': tx.image.name, 'uv': uvn[0].uv_map if uvn else 'uv',
                                            'filter': tx.interpolation.lower(), 'wrap': tx.extension.lower()})
            d['_images'][tx.image.name] = tx.image
            if any(n.type == 'MIX_SHADER' for n in N):
                d['alpha'] = 'blend'
        return d
    # toon3 core
    ld = N['ldir']
    mixes = [n for n in N if n.type == 'MIX' and n.data_type == 'RGBA']
    ramps = [n for n in N if n.type == 'VALTORGB']

    def ramp_into(mx):
        src = _links_from(mx.inputs['Factor'])
        return src[0] if src and src[0].type == 'VALTORGB' else None
    m1 = next(n for n in mixes if n.blend_type == 'MIX' and not n.inputs['A'].is_linked and not n.inputs['B'].is_linked
              and ramp_into(n) is not None)
    m2 = next(n for n in mixes if n.blend_type == 'MIX' and n.inputs['A'].is_linked and not n.inputs['B'].is_linked
              and _links_from(n.inputs['A'])[0] == m1)
    r_deep, r_lit = ramp_into(m1), ramp_into(m2)
    pos = lambda r: [e.position for e in r.color_ramp.elements]
    lo, hi = pos(r_lit)[0], pos(r_lit)[-1]
    dlo, dhi = pos(r_deep)[0], pos(r_deep)[-1]
    d.update(kind='toon3', lit=_col(m2.inputs['B']), shade=_col(m1.inputs['B']), deep=_col(m1.inputs['A']),
             threshold=round((lo + hi) / 2, 6), deepThreshold=round((dlo + dhi) / 2, 6), softness=round((hi - lo) / 2, 6),
             light=r6(g3([ld.inputs[i].default_value for i in range(3)])))
    scr = next((n for n in mixes if n.blend_type == 'SCREEN'), None)
    lw = next((n for n in N if n.type == 'LAYER_WEIGHT'), None)
    rr = next((n for n in N if n.type == 'MAP_RANGE' and lw and _links_from(n.inputs['Value']) == [lw]), None)
    amt = next((n for n in N if n.type == 'MATH' and n.operation == 'MULTIPLY' and rr
                and _links_from(n.inputs[0]) == [rr]), None)
    if scr is not None:
        d['rim'] = {'color': _col(scr.inputs['B']), 'amount': round(float(amt.inputs[1].default_value), 6) if amt else 0.0,
                    'facing': round(float(lw.inputs['Blend'].default_value), 6) if lw else 0.3,
                    'range': [round(float(rr.inputs['From Min'].default_value), 6),
                              round(float(rr.inputs['From Max'].default_value), 6)] if rr else [0.64, 0.68]}
    # a texture multiplied over the result (garments._toon_tex)
    mul = next((n for n in mixes if n.blend_type == 'MULTIPLY' and n.inputs['B'].is_linked
                and _links_from(n.inputs['B'])[0].type == 'TEX_IMAGE' and not n.inputs['Factor'].is_linked), None)
    if mul is not None:
        tx = _links_from(mul.inputs['B'])[0]
        uvn = _links_from(tx.inputs['Vector'])
        d['texture'] = {'_image': tx.image.name, 'uv': uvn[0].uv_map if uvn else 'uv', 'mode': 'multiply',
                        'filter': tx.interpolation.lower(), 'wrap': tx.extension.lower()}
        d['_images'][tx.image.name] = tx.image
    if 'ldir_head' in N:                                           # faceshade.material
        tex = [n for n in N if n.type == 'TEX_IMAGE']
        sdf = next(n for n in tex if any(l.to_node.type == 'MATH' and l.to_node.operation == 'SUBTRACT'
                                         for l in n.outputs['Color'].links))
        fr = next((n for n in tex if any(l.to_node.type == 'MAP_RANGE' for l in n.outputs['Color'].links)), None)
        bl = next((n for n in tex if n.outputs['Alpha'].is_linked), None)
        edge = next(n for n in N if n.type == 'MAP_RANGE' and n.inputs['From Min'].default_value < 0)
        frr = next((l.to_node for l in fr.outputs['Color'].links), None) if fr else None
        col = next(n for n in mixes if n.blend_type == 'MIX' and not n.inputs['A'].is_linked and not n.inputs['B'].is_linked
                   and n is not m1)
        face = {'sdf': {'_image': sdf.image.name, 'uv': 'face', 'encoding': 'rg16', 'filter': sdf.interpolation.lower(),
                        'wrap': sdf.extension.lower()},
                'softness': round(float(edge.inputs['From Max'].default_value), 6),
                'lit': _col(col.inputs['A']), 'shade': _col(col.inputs['B']), 'mask': '_FACE_MASK',
                'light': r6(g3([N['ldir_head'].inputs[i].default_value for i in range(3)]))}
        d['_images'][sdf.image.name] = sdf.image
        if fr is not None:
            face['fringe'] = {'_image': fr.image.name, 'uv': 'face', 'wrap': fr.extension.lower(), 'filter': fr.interpolation.lower()}
            face['fringeRange'] = [round(float(frr.inputs['From Min'].default_value), 6),
                                   round(float(frr.inputs['From Max'].default_value), 6)]
            d['_images'][fr.image.name] = fr.image
        if bl is not None:
            face['blush'] = {'_image': bl.image.name, 'uv': 'face', 'wrap': bl.extension.lower(), 'filter': bl.interpolation.lower()}
            d['_images'][bl.image.name] = bl.image
        d.update(kind='face', face=face)
    if any(n.type == 'UVMAP' and n.uv_map == 'lock' for n in N):   # hair.material
        maths = [n for n in N if n.type == 'MATH']
        dz = next(n for n in maths if n.operation == 'SUBTRACT' and _links_from(n.inputs[0])
                  and _links_from(n.inputs[0])[0].type == 'MATH' and _links_from(n.inputs[0])[0].operation == 'ARCTAN2')
        rel = next(n for n in N if n.type == 'VECT_MATH' and n.operation == 'SUBTRACT')
        hi_ = next(n for n in mixes if n.blend_type == 'MIX' and not n.inputs['B'].is_linked and n.inputs['A'].is_linked
                   and _links_from(n.inputs['A'])[0] == scr)
        lmix = next(n for n in mixes if n.blend_type == 'MULTIPLY' and not n.inputs['B'].is_linked)
        mrs = [n for n in N if n.type == 'MAP_RANGE' and _links_from(n.inputs['Value'])
               and _links_from(n.inputs['Value'])[0].type == 'SEPXYZ']
        grad = next(n for n in mrs if abs(n.inputs['To Max'].default_value - 1.0) < 1e-6 and n.inputs['From Max'].default_value < 0.7)
        lf = next(n for n in mrs if abs(n.inputs['To Max'].default_value) < 1e-6 and n.inputs['From Min'].default_value >= 0.4)
        d['kind'] = 'hair'
        d['hair'] = {
            'lock': 'lock',
            'ring': {'color': _col(hi_.inputs['B']), 'elevation': round(math.degrees(dz.inputs[1].default_value), 4),
                     'centre': r6(g3(rel.inputs[1].default_value)), 'width': 5.0, 'soft': 1.2, 'facing': [0.55, 0.25],
                     'facingBlend': 0.5, 'mid': [0.95, 0.85], 'amount': 0.6},
            'gradient': {'root': round(float(grad.inputs['To Min'].default_value), 6),
                         'range': [0.0, round(float(grad.inputs['From Max'].default_value), 6)]},
            'strands': {'amount': round(float(lf.inputs['To Min'].default_value), 6), 'color': _col(lmix.inputs['B']),
                        'offset': 0.5, 'width': [0.025, 0.06], 'fade': [0.5, 0.8]},
        }
    return d


# ------------------------------------------------------------------------------------------------------------ skeleton
TPOSE = {'leftUpperArm': (1, 0, 0), 'leftLowerArm': (1, 0, 0), 'leftHand': (1, 0, 0),
         'rightUpperArm': (-1, 0, 0), 'rightLowerArm': (-1, 0, 0), 'rightHand': (-1, 0, 0),
         'leftUpperLeg': (0, 0, -1), 'leftLowerLeg': (0, 0, -1), 'rightUpperLeg': (0, 0, -1), 'rightLowerLeg': (0, 0, -1)}


def _rot_between(a, b):
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b)
    v = np.cross(a, b); c = float(a @ b)
    if c < -0.999999:
        ax = np.cross(a, [1, 0, 0]) if abs(a[0]) < 0.9 else np.cross(a, [0, 1, 0])
        ax /= np.linalg.norm(ax)
        return 2 * np.outer(ax, ax) - np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K / (1 + c)


def _quat(R):
    """3x3 rotation -> (x, y, z, w)."""
    t = np.trace(R)
    if t > 0:
        s = math.sqrt(t + 1) * 2
        q = [(R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s, 0.25 * s]
    else:
        i = int(np.argmax(np.diag(R))); j, k = (i + 1) % 3, (i + 2) % 3
        s = math.sqrt(1 + R[i, i] - R[j, j] - R[k, k]) * 2
        q = [0, 0, 0, 0]
        q[i] = 0.25 * s; q[j] = (R[j, i] + R[i, j]) / s; q[k] = (R[k, i] + R[i, k]) / s; q[3] = (R[k, j] - R[j, k]) / s
    q = np.array(q); q /= np.linalg.norm(q)
    return q if q[3] >= 0 else -q


def skeleton(arm, tpose=True):
    """the armature's bones -> (names parents-first, parent names, bind (A-pose) heads, T-pose rotations R (A -> T, world)
    and T-pose heads), in Blender world coordinates."""
    mw = np.array(arm.matrix_world)
    bones = list(arm.data.bones)
    order, seen = [], set()

    def visit(b):
        if b.name in seen:
            return
        if b.parent:
            visit(b.parent)
        seen.add(b.name); order.append(b)
    for b in bones:
        visit(b)
    head = {b.name: (mw @ np.array([*b.head_local, 1.0]))[:3] for b in order}
    tail = {b.name: (mw @ np.array([*b.tail_local, 1.0]))[:3] for b in order}
    R, P = {}, {}
    for b in order:
        p = b.parent.name if b.parent else None
        Rp = R[p] if p else np.eye(3)
        P[b.name] = (P[p] + Rp @ (head[b.name] - head[p])) if p else head[b.name]
        Rb = Rp
        if tpose and b.name in TPOSE:
            cur = Rp @ (tail[b.name] - head[b.name])
            if b.name.endswith('Hand'):                     # the hand's length axis: toward the middle finger's base
                mid = b.name.replace('Hand', 'MiddleProximal')
                if mid in head:
                    cur = Rp @ (head[mid] - head[b.name])
            Rb = _rot_between(cur, np.array(TPOSE[b.name], float)) @ Rp
        R[b.name] = Rb
    return [b.name for b in order], {b.name: (b.parent.name if b.parent else None) for b in order}, head, R, P


# --------------------------------------------------------------------------------------------------------- evaluation
def _outline_mod(ob):
    for md in ob.modifiers:
        if md.type == 'SOLIDIFY' and md.use_flip_normals:
            return md
    return None


class Eval:
    """an object's mesh as Blender renders it, armature off, subdivision capped: the corner data with the outline SOLIDIFY
    off (co: the original surface), and with it on (surf: the first N vertices of its result, the surface Blender draws,
    moved inward by the line width; the hull is the original surface), for the base and for every shape key."""

    def __init__(self, ob, subdiv=2):
        import bpy
        self.ob = ob
        om = _outline_mod(ob)
        saved, levels = [], []
        for md in ob.modifiers:
            if md.type == 'ARMATURE' or (om is not None and md.name == om.name):
                saved.append((md, md.show_viewport)); md.show_viewport = False
            if md.type == 'SUBSURF':
                levels.append((md, md.levels)); md.levels = min(md.render_levels, subdiv)
        om = ob.modifiers[om.name] if om is not None else None
        ks = ob.data.shape_keys
        kvals = [k.value for k in ks.key_blocks] if ks else []
        try:
            if ks:
                for k in ks.key_blocks[1:]:
                    k.value = 0.0
            bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
            try:
                self._read(me)
            finally:
                bpy.data.meshes.remove(me)
            n = len(self.co)
            self.surf, self.hull_n = self.co, None
            if om is not None:
                om.show_viewport = True
                self.surf, self.hull_n = self._positions(n)
            self.keys = {}
            if ks:
                for k in ks.key_blocks[1:]:
                    k.value = 1.0
                    self.keys[k.name] = self._positions(n)
                    k.value = 0.0
        finally:
            if ks:
                for k, v in zip(ks.key_blocks, kvals):
                    k.value = v
            for md, s in saved:
                md.show_viewport = s
            for md, lv in levels:
                md.levels = lv
            bpy.context.view_layer.update()

    def _positions(self, n):
        """the evaluated vertex positions (the first n: with the outline on, its surface) and the hull direction per vertex
        (with the outline on: hull - surface where it moved, else the surface's vertex normal)."""
        import bpy
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        oe = self.ob.evaluated_get(dg)
        tm = oe.to_mesh()
        co = np.empty(len(tm.vertices) * 3, np.float32); tm.vertices.foreach_get('co', co)
        vn = np.empty(len(tm.vertices) * 3, np.float32); tm.vertex_normals.foreach_get('vector', vn)
        oe.to_mesh_clear()
        co = co.reshape(-1, 3); vn = vn.reshape(-1, 3)
        if len(co) not in (n, 2 * n):
            raise RuntimeError(f'{self.ob.name}: evaluated vertex count {len(co)} (expected {n} or {2 * n})')
        hn = vn[:n]
        if len(co) == 2 * n:
            d = co[n:] - co[:n]
            ln = np.linalg.norm(d, axis=1)
            hn = np.where((ln > 1e-7)[:, None], d / np.maximum(ln, 1e-12)[:, None], vn[:n])
        return co[:n], hn

    def _read(self, me):
        nv, nl = len(me.vertices), len(me.loops)
        self.co = np.empty(nv * 3, np.float32); me.vertices.foreach_get('co', self.co); self.co = self.co.reshape(-1, 3)
        self.loop_v = np.empty(nl, np.int32); me.loops.foreach_get('vertex_index', self.loop_v)
        self.loop_n = np.empty(nl * 3, np.float32); me.corner_normals.foreach_get('vector', self.loop_n)
        self.loop_n = self.loop_n.reshape(-1, 3)
        self.uv = {}
        for lay in me.uv_layers:
            a = np.empty(nl * 2, np.float32); lay.data.foreach_get('uv', a); self.uv[lay.name] = a.reshape(-1, 2)
        me.calc_loop_triangles()
        nt = len(me.loop_triangles)
        self.tri = np.empty(nt * 3, np.int32); me.loop_triangles.foreach_get('loops', self.tri); self.tri = self.tri.reshape(-1, 3)
        self.tri_mat = np.empty(nt, np.int32); me.loop_triangles.foreach_get('material_index', self.tri_mat)
        self.materials = list(me.materials)
        names = [g.name for g in self.ob.vertex_groups]
        self.groups = {}                                         # name -> (nv,) weights
        for v in me.vertices:
            for g in v.groups:
                if g.weight > 0 and g.group < len(names):
                    self.groups.setdefault(names[g.group], np.zeros(nv, np.float32))[v.index] = g.weight
        self.attrs = {}
        for a in me.attributes:
            if a.domain == 'POINT' and a.data_type in ('FLOAT_COLOR', 'FLOAT') and not a.name.startswith('.') \
                    and a.name not in ('position',):
                if a.data_type == 'FLOAT_COLOR':
                    x = np.empty(nv * 4, np.float32); a.data.foreach_get('color', x); x = x.reshape(-1, 4)[:, 0]
                else:
                    x = np.empty(nv, np.float32); a.data.foreach_get('value', x)
                self.attrs[a.name] = x


def head_frame(ob):
    """the face UV's frame (charkit.character.build: u = (x - cx + 0.42 L) / 0.84 L, v = (z - cz + 0.45 L) / 1.05 L on the
    head's faces) solved back from the original mesh's face-material corners: -> (centre x, y, z, L) in Blender world, or
    None. (The y is the head faces' mean depth: the face UV doesn't carry it.)"""
    me = ob.data
    if 'face' not in me.uv_layers:
        return None
    slots = [i for i, m in enumerate(me.materials) if m and m.node_tree and 'ldir_head' in m.node_tree.nodes]
    if not slots:
        return None
    nl = len(me.loops)
    uv = np.empty(nl * 2, np.float32); me.uv_layers['face'].data.foreach_get('uv', uv); uv = uv.reshape(-1, 2)
    lv = np.empty(nl, np.int32); me.loops.foreach_get('vertex_index', lv)
    co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    pm = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get('material_index', pm)
    ls = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get('loop_start', ls)
    lt = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get('loop_total', lt)
    sel = np.zeros(nl, bool)
    for s_, t_, m_ in zip(ls, lt, pm):
        if m_ in slots:
            sel[s_:s_ + t_] = True
    if sel.sum() < 10:
        return None
    mw = np.array(ob.matrix_world)
    p = co[lv[sel]] @ mw[:3, :3].T + mw[:3, 3]
    a = 0.84 * uv[sel, 0] - 0.42; b = 1.05 * uv[sel, 1] - 0.45
    (cx, L1), *_ = np.linalg.lstsq(np.stack([np.ones_like(a), a], 1), p[:, 0], rcond=None)
    (cz, L2), *_ = np.linalg.lstsq(np.stack([np.ones_like(b), b], 1), p[:, 2], rcond=None)
    return float(cx), float(p[:, 1].mean()), float(cz), float((L1 + L2) / 2)


# ------------------------------------------------------------------------------------------------------------- export
def _roles(objects):
    feats = [o.name for o in objects if o.name.startswith(FEATURES)]
    skin = [o.name for o in objects if o.type == 'MESH' and 'face_mask' in o.data.attributes]
    return {'features': feats, 'holdouts': skin}


def export(path, arm=None, objects=None, name=None, subdiv=2, roles=None, meta=None, tpose=True, extra=None, log=print):
    """write the character in the current Blender scene (its armature and visible, rigged meshes) to path (.vrm / .glb).
    -> a report dict."""
    import bpy
    arm = arm or next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
    if objects is None:
        objects = [o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.hide_render
                   and (o.parent == arm or any(m.type == 'ARMATURE' and m.object == arm for m in o.modifiers))]
    name = name or arm.name.replace('_rig', '')
    roles = roles or _roles(objects)
    W = Writer()
    rep = {'file': path, 'objects': {}, 'materials': {}, 'expressions': {}, 'warnings': []}

    # skeleton: nodes in the T-pose with identity rotations; inverse bind matrices from the A-pose
    names, parent, head, R, P = skeleton(arm, tpose)
    idx = {n: i for i, n in enumerate(names)}
    for n in names:
        p = parent[n]
        t = g3(P[n] - (P[p] if p else 0.0))
        W.js['nodes'].append({'name': n, 'translation': r6(t)})
    for n in names:
        kids = [idx[c] for c in names if parent[c] == n]
        if kids:
            W.js['nodes'][idx[n]]['children'] = kids
    root = len(W.js['nodes'])
    W.js['nodes'].append({'name': arm.name, 'children': [idx[n] for n in names if parent[n] is None]})
    W.js['scenes'][0]['nodes'].append(root)
    ibm = []
    for n in names:
        Rg = C3 @ R[n] @ C3.T                               # A -> T rotation in the glTF frame
        M = np.eye(4); M[:3, :3] = Rg; M[:3, 3] = -Rg @ g3(head[n])
        ibm.append(M.T.ravel())                             # column-major
    W.js['skins'].append({'name': arm.name, 'joints': [idx[n] for n in names], 'skeleton': root,
                          'inverseBindMatrices': W.accessor(np.array(ibm, np.float32), 'MAT4')})
    # bind pose as normalized-bone local rotations (three-vrm's normalized humanoid: identity rest in world axes)
    bindq = {}
    for n in names:
        D = C3 @ R[n].T @ C3.T                              # world delta T -> A (glTF)
        Dp = C3 @ R[parent[n]].T @ C3.T if parent[n] else np.eye(3)
        q = _quat(Dp.T @ D)
        if abs(q[3]) < 0.999999:
            bindq[n] = r6(q)

    # materials: keyed by (Blender material, outline) since MToon's outline lives on the material
    mat_index, tex_index, img_index = {}, {}, {}

    def texture(img, info):
        key = (img.name, info.get('encoding'))
        if key not in tex_index:
            px = image_pixels(img)
            if info.get('encoding') == 'rg16':
                v = np.clip(np.round(px[..., 0] * 65535), 0, 65535).astype(np.uint32)
                a = np.stack([v >> 8, v & 255, v >> 8], -1).astype(np.uint8)
            elif img.is_float or img.colorspace_settings.name == 'Non-Color':
                a = np.clip(np.round(px[..., :3] * 255), 0, 255).astype(np.uint8)
            else:
                a = np.clip(np.round(px * 255), 0, 255).astype(np.uint8)
                if (a[..., 3] == 255).all():
                    a = a[..., :3]
            ii = W.image(img.name, png(a))
            lin = info.get('filter') != 'closest'
            wrap = 33071 if info.get('wrap', 'extend') in ('extend', 'clip') else 10497
            W.js['samplers'].append({'magFilter': 9729 if lin else 9728, 'minFilter': 9987 if lin else 9728,
                                     'wrapS': wrap, 'wrapT': wrap})
            W.js['textures'].append({'name': img.name, 'source': ii, 'sampler': len(W.js['samplers']) - 1})
            tex_index[key] = len(W.js['textures']) - 1
        return tex_index[key]

    def texinfo(d, images):
        """our {'_image', 'uv', ...} -> a glTF-style textureInfo {index, texCoord, ...}."""
        out = {k: v for k, v in d.items() if not k.startswith('_') and k != 'uv'}
        out['index'] = texture(images[d['_image']], d)
        out['texCoord'] = 0 if d.get('uv', 'uv') == 'uv' else 1
        return out

    def material(m, outline):
        key = (m.name if m else None, tuple(outline) if outline else None)
        if key in mat_index:
            return mat_index[key]
        look = material_look(m)
        images = look.pop('_images')
        for k in ('texture',):
            if k in look:
                look[k] = texinfo(look[k], images)
        if 'face' in look:
            for k in ('sdf', 'fringe', 'blush'):
                if k in look['face']:
                    look['face'][k] = texinfo(look['face'][k], images)
        if 'hair' in look:
            look['hair']['lock'] = 1
        mat = {'name': m.name if m else 'none', 'doubleSided': look['doubleSided'],
               'pbrMetallicRoughness': {'metallicFactor': 0.0, 'roughnessFactor': 1.0}}
        pbr = mat['pbrMetallicRoughness']
        base = look.get('lit') or look.get('color') or [1, 1, 1]
        pbr['baseColorFactor'] = [*base, 1.0]
        if look['kind'] == 'plate':
            pbr['baseColorTexture'] = {'index': look['texture']['index'], 'texCoord': look['texture']['texCoord']}
        elif 'texture' in look:
            pbr['baseColorTexture'] = {'index': look['texture']['index'], 'texCoord': look['texture']['texCoord']}
        if look['alpha'] == 'blend':
            mat['alphaMode'] = 'BLEND'
        mat['extensions'] = {EXT: look, 'VRMC_materials_mtoon': mtoon(look, outline)}
        W.js['materials'].append(mat)
        mat_index[key] = len(W.js['materials']) - 1
        rep['materials'][mat['name']] = look['kind']
        return mat_index[key]

    # meshes
    skinned = [o for o in objects]
    head_info = None
    for ob in skinned:
        E = Eval(ob, subdiv)
        mw = np.array(ob.matrix_world)
        xf = lambda p: p @ mw[:3, :3].T + mw[:3, 3]
        Nm = np.linalg.inv(mw[:3, :3]).T
        unit = lambda x: x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-12)
        co, surf = xf(E.co), xf(E.surf)
        if ob.name in roles['holdouts'] and head_info is None:
            head_info = head_frame(ob)
        # outline: width (m), colour, per-vertex factor. Blender's SOLIDIFY (offset 1, negative thickness) draws the surface
        # moved inward (surf) and the hull at the original surface (co): hull direction = co - surf where it moved
        om = _outline_mod(ob)
        outline, ow = None, None
        cn = E.loop_n @ Nm.T
        bad = np.linalg.norm(cn, axis=1) < 1e-6                 # degenerate corners (the mouth cavity's folds)
        cn = unit(cn)
        vavg = np.zeros_like(co); np.add.at(vavg, E.loop_v, cn); vavg = unit(vavg)
        cn[bad] = vavg[E.loop_v[bad]]
        cn[np.linalg.norm(cn, axis=1) < 0.5] = (0.0, 0.0, 1.0)
        hulln = vavg
        if om is not None:
            mats = ob.data.materials
            lm = mats[om.material_offset] if 0 <= om.material_offset < len(mats) else None
            em = next((n for n in lm.node_tree.nodes if n.type == 'EMISSION'), None) if lm else None
            outline = (round(abs(om.thickness), 6), tuple(_col(em.inputs['Color'])) if em else (0.05, 0.03, 0.03))
            if om.vertex_group and om.vertex_group in E.groups:
                ow = om.thickness_vertex_group + (1 - om.thickness_vertex_group) * E.groups[om.vertex_group]
            elif om.vertex_group:
                ow = np.full(len(co), om.thickness_vertex_group, np.float32)
            d = co - surf
            moved = np.linalg.norm(d, axis=1) > 1e-7
            hulln = np.where(moved[:, None], unit(d), vavg)
        # skin weights: top four bones
        bone_w = {g: w for g, w in E.groups.items() if g in idx}
        if not bone_w and ob.parent_type == 'BONE' and ob.parent_bone in idx:
            bone_w = {ob.parent_bone: np.ones(len(co), np.float32)}
        if not bone_w:
            rep['warnings'].append(f'{ob.name}: no bone weights; bound to hips')
            bone_w = {'hips': np.ones(len(co), np.float32)}
        bn = list(bone_w)
        Wm = np.stack([bone_w[b] for b in bn], 1)
        if Wm.shape[1] < 4:
            Wm = np.pad(Wm, ((0, 0), (0, 4 - Wm.shape[1])))
            bn = bn + [bn[0]] * (4 - len(bn))
        top = np.argsort(-Wm, 1, kind='stable')[:, :4]
        tw = np.take_along_axis(Wm, top, 1)
        tw = np.where(tw > 1e-4, tw, 0)
        s = tw.sum(1, keepdims=True)
        tw = np.where(s > 0, tw / np.maximum(s, 1e-12), 0)
        tw[s[:, 0] <= 0, 0] = 1.0
        joints = np.where(tw > 0, np.array([idx[b] for b in bn])[top], 0)
        # per-corner attributes -> glTF vertices, one primitive per material
        L_ = E.loop_v
        uv0 = E.uv.get('uv', next(iter(E.uv.values())) if E.uv else None)
        uv1 = E.uv.get('face', E.uv.get('lock'))
        need_hull = outline is not None and np.abs(cn - hulln[L_]).max() > 2e-3
        keys = {kn: xf(kc) for kn, (kc, _) in E.keys.items()}
        # the keyed hull directions (outlined meshes): NORMAL morph deltas, so the hull (and the shading) follow the keys
        key_n = {kn: unit(kh @ Nm.T) for kn, (_, kh) in E.keys.items()} if outline else {}
        key_names = list(keys)
        # a keyed mesh splits in two: the part its keys move (with the morph targets) and the static rest (no targets),
        # so a runtime's morph buffers cover only the moving part; the seam's vertices never move, so nothing opens
        tri_v = L_[E.tri]
        if key_names:
            mv = np.zeros(len(co), bool)
            for kn in key_names:
                mv |= np.abs(keys[kn] - surf).max(1) > 1e-7
            tri_moves = mv[tri_v].any(1)
            groups = [('', tri_moves, key_names), ('.static', ~tri_moves, [])]
        else:
            groups = [('', np.ones(len(E.tri), bool), [])]
        made = []
        for suffix, tsel, knames in groups:
            prims = []
            for mi in np.unique(E.tri_mat[tsel]):
                m = E.materials[mi] if mi < len(E.materials) else None
                mat_i = material(m, outline)
                used = texcoords(W.js['materials'][mat_i]['extensions'][EXT])
                u1 = uv1 if 1 in used else None
                u0 = uv0 if (0 in used or u1 is not None) else None     # TEXCOORD_1 needs a TEXCOORD_0
                if u1 is not None and u0 is None:
                    u0 = np.zeros_like(u1)
                tl = E.tri[(E.tri_mat == mi) & tsel].ravel()
                cols = [L_[tl].astype(np.float32)[:, None], np.round(cn[tl], 4)]
                cols += [np.round(u[tl], 5) for u in (u0, u1) if u is not None]
                corner = np.ascontiguousarray(np.concatenate(cols, 1).astype(np.float32))
                view = corner.view(np.dtype((np.void, corner.dtype.itemsize * corner.shape[1])))
                _, first, inv = np.unique(view.ravel(), return_index=True, return_inverse=True)
                lp = tl[first]                                   # a representative loop per glTF vertex
                vi = L_[lp]
                P_ = g3(surf[vi]).astype(np.float32)
                attrs = {'POSITION': W.accessor(P_, 'VEC3', target=34962, minmax=True),
                         'NORMAL': W.accessor(g3(cn[lp]).astype(np.float32), 'VEC3', target=34962),
                         'JOINTS_0': W.accessor(joints[vi].astype(np.uint8 if len(names) < 256 else np.uint16), 'VEC4',
                                                target=34962),
                         'WEIGHTS_0': W.accessor(tw[vi].astype(np.float32), 'VEC4', target=34962)}
                if u0 is not None:
                    attrs['TEXCOORD_0'] = W.accessor((u0[lp] * [1, -1] + [0, 1]).astype(np.float32), 'VEC2', target=34962)
                if u1 is not None:
                    attrs['TEXCOORD_1'] = W.accessor((u1[lp] * [1, -1] + [0, 1]).astype(np.float32), 'VEC2', target=34962)
                if ow is not None:
                    attrs['_OUTLINE_WIDTH'] = W.accessor(ow[vi].astype(np.float32), 'SCALAR', target=34962)
                if need_hull:
                    attrs['_HULL_NORMAL'] = W.accessor(g3(hulln[vi]).astype(np.float32), 'VEC3', target=34962)
                if 'face_mask' in E.attrs:
                    attrs['_FACE_MASK'] = W.accessor(E.attrs['face_mask'][vi].astype(np.float32), 'SCALAR', target=34962)
                ind = inv.astype(np.uint32 if len(first) > 65535 else np.uint16)
                prim = {'attributes': attrs, 'indices': W.accessor(ind, 'SCALAR', target=34963), 'mode': 4, 'material': mat_i}
                if knames:
                    prim['targets'] = []
                    for kn in knames:
                        t_ = {'POSITION': W.sparse_vec3(g3(keys[kn][vi] - surf[vi]))}
                        if kn in key_n:
                            t_['NORMAL'] = W.sparse_vec3(g3(key_n[kn][vi] - hulln[vi]), eps=1e-5)
                        prim['targets'].append(t_)
                prims.append(prim)
            if not prims:
                continue
            mesh = {'name': ob.name + suffix, 'primitives': prims}
            if knames:
                mesh['extras'] = {'targetNames': knames}
                mesh['weights'] = [0.0] * len(knames)
            mx = {'object': ob.name}
            if outline:
                mx['outline'] = {'width': outline[0], 'color': list(outline[1])}
                if ow is not None:
                    mx['outline']['widthAttribute'] = '_OUTLINE_WIDTH'
                if need_hull:
                    mx['outline']['normalAttribute'] = '_HULL_NORMAL'
            if ob.name in roles['features']:
                mx['feature'] = True
            if ob.name in roles['holdouts']:
                mx['holdout'] = True
            mesh['extensions'] = {EXT: mx}
            W.js['meshes'].append(mesh)
            W.js['nodes'].append({'name': ob.name + suffix, 'mesh': len(W.js['meshes']) - 1, 'skin': 0})
            W.js['scenes'][0]['nodes'].append(len(W.js['nodes']) - 1)
            made += prims
        if not made:
            continue
        prims = made
        rep['objects'][ob.name] = {'vertices': int(sum(W.js['accessors'][p['attributes']['POSITION']]['count'] for p in prims)),
                                   'triangles': int(sum(W.js['accessors'][p['indices']]['count'] for p in prims) // 3),
                                   'primitives': len(prims), 'keys': len(key_names),
                                   'moving_vertices': int(sum(W.js['accessors'][p['attributes']['POSITION']]['count']
                                                              for p in prims if p.get('targets'))),
                                   'outline': bool(outline), 'custom_normals': bool(need_hull)}
        log(f'[gltf] {ob.name}: {rep["objects"][ob.name]}')

    # the root extension and VRMC_vrm
    mesh_node = {W.js['meshes'][W.js['nodes'][i]['mesh']]['name']: i for i in range(len(W.js['nodes']))
                 if 'mesh' in W.js['nodes'][i]}
    ldir = next((m['extensions'][EXT].get('light') for m in W.js['materials'] if m['extensions'][EXT].get('light')), None)
    rootx = {'version': 1, 'character': name, 'units': 'metres', 'frame': 'Y up, facing +Z, her left +X',
             'light': {'direction': ldir or r6(g3([-0.45, -0.55, 0.70]) / np.linalg.norm([-0.45, -0.55, 0.70]))},
             'features': {'through': THROUGH}, 'bindPose': bindq, 'tpose': bool(tpose)}
    if head_info:
        cx, cy, cz, L = head_info
        rootx['head'] = {'bone': 'head', 'centre': r6(g3([cx, cy, cz])), 'L': round(L, 6)}
    rootx.update(extra or {})
    W.js['extensions'][EXT] = rootx
    W.use(EXT); W.use('VRMC_materials_mtoon')
    vrm = vrmc(W, names, idx, mesh_node, P, head, name, meta or {}, rep)
    W.js['extensions']['VRMC_vrm'] = vrm
    W.use('VRMC_vrm')
    rep['bytes'] = W.glb(path)
    rep['nodes'] = len(W.js['nodes']); rep['meshes'] = len(W.js['meshes']); rep['textures'] = len(W.js['textures'])
    rep['triangles'] = sum(o['triangles'] for o in rep['objects'].values())
    return rep


def texcoords(look):
    """the texCoord sets a material description reads."""
    out = set()
    if isinstance(look, dict):
        if 'texCoord' in look:
            out.add(look['texCoord'])
        for k, v in look.items():
            if k == 'lock':
                out.add(v)
            out |= texcoords(v)
    return out


def mtoon(look, outline):
    """the VRMC_materials_mtoon fallback for standard VRM viewers: lit and shade tones, the step as shading shift and toony
    (half-lambert h = 0.5 + 0.5 N.L crossing t over +-s  <=>  MToon shift 1 - 2t, toony 1 - 2s), textures, the outline in
    world units. What it can't say (the deep tone, the SDF face, the ring, the lit-side rim) lives in OPENADS_charkit_look."""
    k = look['kind']
    mt = {'specVersion': '1.0', 'transparentWithZWrite': False, 'renderQueueOffsetNumber': 0,
          'giEqualizationFactor': 0.9, 'parametricRimColorFactor': [0, 0, 0], 'rimLightingMixFactor': 1.0,
          'parametricRimFresnelPowerFactor': 5.0, 'parametricRimLiftFactor': 0.0, 'matcapFactor': [0, 0, 0],
          'outlineWidthMode': 'none', 'outlineWidthFactor': 0.0, 'outlineColorFactor': [0, 0, 0],
          'outlineLightingMixFactor': 0.0}
    if k in ('toon3', 'face', 'hair'):
        t, s = look['threshold'], look['softness']
        mt.update(shadeColorFactor=look['shade'], shadingShiftFactor=round(1 - 2 * t, 6),
                  shadingToonyFactor=round(max(0.0, min(1.0, 1 - 2 * s)), 6))
        if k == 'face':                                      # the SDF face reads as mostly lit; the usual VRoid choice
            mt.update(shadeColorFactor=look['face']['shade'], shadingShiftFactor=0.6)
        if 'texture' in look:
            mt['shadeMultiplyTexture'] = {'index': look['texture']['index'], 'texCoord': look['texture']['texCoord']}
    else:
        col = look.get('color') or [1, 1, 1]
        mt.update(shadeColorFactor=col if k == 'flat' else [1, 1, 1], shadingShiftFactor=1.0, shadingToonyFactor=1.0,
                  giEqualizationFactor=1.0)
        if k == 'plate':
            mt['shadeMultiplyTexture'] = {'index': look['texture']['index'], 'texCoord': look['texture']['texCoord']}
            if look['alpha'] == 'blend':
                mt['renderQueueOffsetNumber'] = 1
    if outline:
        mt.update(outlineWidthMode='worldCoordinates', outlineWidthFactor=outline[0], outlineColorFactor=list(outline[1]))
    return mt


def vrmc(W, names, idx, mesh_node, P, head, name, meta, rep):
    """VRMC_vrm: humanoid, meta, expressions from the shape keys, lookAt."""
    hb = {n: {'node': idx[n]} for n in names}
    m = dict(META); m.update(meta); m['name'] = meta.get('name', name)
    targets = {}                                             # key name -> [(node, index, mesh name)]
    for i, nd in enumerate(W.js['nodes']):
        if 'mesh' not in nd:
            continue
        mesh = W.js['meshes'][nd['mesh']]
        for j, tn in enumerate(mesh.get('extras', {}).get('targetNames', [])):
            targets.setdefault(tn, []).append((i, j, mesh['name']))

    def binds(key, w, side=None):
        out = []
        if side:
            for node, j, mn in targets.get(f'{key}_{side}', []):          # per-side keys on shared meshes (the skin)
                out.append({'node': node, 'index': j, 'weight': w})
            for node, j, mn in targets.get(key, []):                       # both-eye keys on the side's own objects
                if mn.endswith('_' + side):
                    out.append({'node': node, 'index': j, 'weight': w})
        else:
            for node, j, mn in targets.get(key, []):
                out.append({'node': node, 'index': j, 'weight': w})
        return out
    preset, used = {}, set()
    for ex, (keys, side, ov) in PRESETS.items():
        b = [x for kn, w in keys.items() for x in binds(kn, w, side)]
        used.update(keys)
        if not b:
            rep['warnings'].append(f'expression {ex}: no shape keys found')
            continue
        e = {'morphTargetBinds': b, 'isBinary': False}
        e.update(ov)
        preset[ex] = e
    custom = {}
    single = {next(iter(k)) for k, side, _ in PRESETS.values() if len(k) == 1 and side is None}
    for kn in sorted(targets):
        if kn in single or kn in ('eye_blink_L', 'eye_blink_R'):
            continue
        if kn.endswith(('_L', '_R')):
            custom[kn] = {'morphTargetBinds': binds(kn[:-2], 1.0, kn[-1]), 'isBinary': False}
        else:
            custom[kn] = {'morphTargetBinds': binds(kn, 1.0), 'isBinary': False}
    # the kit's combined expressions (charkit.scene.PRESETS: eyes, mouth and brows together), where a VRM preset doesn't
    # already hold the name
    from .scene import PRESETS as COMBINED
    for ex, P in COMBINED.items():
        if ex in preset:
            continue
        b = [x for part in ('eye', 'mouth', 'brow') if P.get(part) for x in binds('%s_%s' % (part, P[part]), 1.0)]
        if b:
            custom[ex] = {'morphTargetBinds': b, 'isBinary': False}
    rep['expressions'] = {'preset': sorted(preset), 'custom': sorted(custom)}
    # lookAt: the iris keys; the offset from the head bone to between the eyes
    eyes = [n for n in mesh_node if n.startswith('sclera_')]
    off = [0.0, 0.06, 0.08]
    if eyes and 'head' in P:
        pts = []
        for n in eyes:
            acc = W.js['accessors'][W.js['meshes'][W.js['nodes'][mesh_node[n]]['mesh']]['primitives'][0]['attributes']['POSITION']]
            pts.append((np.array(acc['min']) + np.array(acc['max'])) / 2)
        off = r6(np.mean(pts, 0) - g3(P['head']))
    rng = lambda deg: {'inputMaxValue': deg, 'outputScale': 1.0}
    return {'specVersion': '1.0', 'meta': m, 'humanoid': {'humanBones': hb},
            'expressions': {'preset': preset, 'custom': custom},
            'lookAt': {'type': 'expression', 'offsetFromHeadBone': off, 'rangeMapHorizontalInner': rng(25.0),
                       'rangeMapHorizontalOuter': rng(25.0), 'rangeMapVerticalDown': rng(20.0),
                       'rangeMapVerticalUp': rng(20.0)}}


def export_scene(S, path, **kw):
    """from charkit.scene.build's Scene: its roles (features, the skin as holdout) and name."""
    import bpy
    objs = [o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.hide_render
            and o.parent == S.character['arm']]
    roles = {'features': [o.name for o in S.features], 'holdouts': [S.character['skin'].name]}
    extra = {'height': float((S.spec.get('body') or {}).get('height_m', 1.6))}
    extra.update(kw.pop('extra', {}) or {})
    return export(path, arm=S.character['arm'], objects=objs, name=S.name, roles=roles, extra=extra, **kw)


# ------------------------------------------------------------------------------------------------------------ checking
def check(path):
    """parse the file back and check it: the VRM checks (charkit.export.validate_vrm) plus our extension and accessors."""
    sys.path.insert(0, ROOT)
    from charkit.export import read_glb, validate_vrm
    rep = validate_vrm(path)
    js, bin_ = read_glb(path)
    ext = js.get('extensions', {}).get(EXT)
    if not ext:
        rep['errors'].append(f'no {EXT}')
    kinds = {}
    for m in js.get('materials', []):
        k = m.get('extensions', {}).get(EXT, {}).get('kind')
        kinds[k] = kinds.get(k, 0) + 1
    rep['look_kinds'] = kinds
    for i, a in enumerate(js['accessors']):
        if 'bufferView' in a:
            bv = js['bufferViews'][a['bufferView']]
            size = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}[a['type']] * \
                {5126: 4, 5125: 4, 5123: 2, 5121: 1}[a['componentType']]
            if bv['byteOffset'] + bv['byteLength'] > len(bin_) or a['count'] * size > bv['byteLength']:
                rep['errors'].append(f'accessor {i} overruns its view')
    rep['outlined_meshes'] = [m['name'] for m in js['meshes'] if m.get('extensions', {}).get(EXT, {}).get('outline')]
    return rep


if __name__ == '__main__':
    import bpy
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
    if '--check' in argv:
        print(json.dumps(check(opt('--check')), indent=1, default=str))
        raise SystemExit
    blend = bpy.data.filepath
    out = argv[0] if argv and not argv[0].startswith('--') else os.path.splitext(blend)[0] + '.vrm'
    spec = os.path.splitext(blend)[0] + '.spec.json'
    meta, extra = {}, {}
    if os.path.exists(spec):
        sp = json.load(open(spec))
        meta['name'] = sp.get('name', 'charkit').capitalize()
        extra['height'] = float((sp.get('body') or {}).get('height_m', 1.6))
    rep = export(out, subdiv=int(opt('--subdiv', 2)), meta=meta, tpose='--no-tpose' not in argv, extra=extra)
    json.dump(rep, open(os.path.splitext(out)[0] + '.export.json', 'w'), indent=1, default=str)
    c = check(out)
    print('CHARKIT_GLTF', json.dumps({k: c.get(k) for k in ('bytes', 'triangles', 'humanBones', 'errors', 'warnings', 'tpose',
                                                            'look_kinds', 'outlined_meshes')}, default=str))
    print('CHARKIT_GLTF_DONE', out)
