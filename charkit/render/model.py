"""A built character as the toon renderer draws it: our export (charkit/gltf.py: glTF 2.0 / VRM 1.0 with the
OPENADS_charkit_look extension) read back with numpy and Pillow, no Blender. The same data look.js reads.

    from charkit.render import model; M = model.load('charkit/out/NAME/clawd.vrm')
    M.root            the extension's root: light (mode, key), lines (mode, frac, regions), head (centre, L), height
    M.prims           one Prim per glTF primitive: its arrays in the glTF frame (Y up, facing +Z, her left +X), its
                      material's look (M.materials[i]) and its mesh's (outline, feature, holdout)
    M.textures[i]     (h, w, 4) float32, row 0 = the image's top: colour maps decoded to linear, data maps (the face's
                      SDF, fringe) as stored, the SDF's 16 bits unpacked from R (high) and G (low)

Positions are the build pose (the A-pose the build renders and the boards show): the export's inverse bind matrices are
that pose, so a mesh drawn without skinning stands as Blender drew it. POSITION is the surface Blender draws at the build
line width (the outline SOLIDIFY moved it inward by width x _OUTLINE_WIDTH along the hull normal); Prim.co() gives back
the original surface, where the hull is.
"""
import io, json, os, struct
from dataclasses import dataclass, field

import numpy as np

EXT = 'OPENADS_charkit_look'
C3 = np.array([[1.0, 0, 0], [0, 0, 1.0], [0, -1.0, 0]])      # Blender (Z up, facing -Y) -> glTF (Y up, facing +Z)
COMP = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8, 5122: np.int16, 5120: np.int8}
NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def to_gltf(v):
    """Blender vectors (..., 3) -> the glTF frame."""
    return np.asarray(v, float) @ C3.T


def srgb_to_linear(c):
    c = np.asarray(c, np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4).astype(np.float32)


def read_glb(path):
    b = open(path, 'rb').read()
    magic, ver, n = struct.unpack('<III', b[:12])
    if magic != 0x46546C67:
        raise ValueError(f'{path}: not a GLB')
    off, js, bin_ = 12, None, b''
    while off < n:
        ln, kind = struct.unpack('<II', b[off:off + 8])
        chunk = b[off + 8:off + 8 + ln]
        if kind == 0x4E4F534A:
            js = json.loads(chunk)
        elif kind == 0x004E4942:
            bin_ = chunk
        off += 8 + ln
    return js, bin_


class Accessors:
    def __init__(self, js, bin_):
        self.js, self.bin = js, bin_

    def view(self, i):
        bv = self.js['bufferViews'][i]
        o = bv.get('byteOffset', 0)
        return self.bin[o:o + bv['byteLength']], bv.get('byteStride')

    def __call__(self, i):
        """accessor i -> numpy (count, ncomp) (or (count,) for SCALAR), sparse values applied, normalized ints scaled."""
        a = self.js['accessors'][i]
        dt, nc, cnt = COMP[a['componentType']], NCOMP[a['type']], a['count']
        if 'bufferView' in a:
            raw, stride = self.view(a['bufferView'])
            item = np.dtype(dt).itemsize * nc
            o = a.get('byteOffset', 0)
            if stride and stride != item:
                rows = np.frombuffer(raw, np.uint8)[o:o + stride * (cnt - 1) + item]
                rows = np.lib.stride_tricks.as_strided(rows, (cnt, item), (stride, 1))
                arr = np.ascontiguousarray(rows).view(dt).reshape(cnt, nc)
            else:
                arr = np.frombuffer(raw, dt, cnt * nc, o).reshape(cnt, nc).copy()
        else:
            arr = np.zeros((cnt, nc), dt)
        sp = a.get('sparse')
        if sp:
            ri, _ = self.view(sp['indices']['bufferView'])
            idx = np.frombuffer(ri, COMP[sp['indices']['componentType']], sp['count'], sp['indices'].get('byteOffset', 0))
            rv, _ = self.view(sp['values']['bufferView'])
            vals = np.frombuffer(rv, dt, sp['count'] * nc, sp['values'].get('byteOffset', 0)).reshape(-1, nc)
            arr = arr.copy(); arr[idx.astype(np.int64)] = vals
        if a.get('normalized') and dt is not np.float32:
            arr = arr.astype(np.float32) / np.iinfo(dt).max
        return arr[:, 0] if nc == 1 else arr


@dataclass
class Prim:
    """one glTF primitive: arrays in the glTF frame, build pose."""
    mesh: str                          # the glTF mesh's name (clawd_skin, clawd_skin.static, hair_bangs, ...)
    object: str                        # the Blender object it came from
    material: int
    look: dict                         # the material's OPENADS_charkit_look
    mx: dict                           # the mesh's OPENADS_charkit_look: outline, feature, holdout
    position: np.ndarray               # (n, 3) float32: the surface at the build line width
    normal: np.ndarray                 # (n, 3) float32: the render's corner normals
    index: np.ndarray                  # (m,) uint32
    uv0: np.ndarray = None
    uv1: np.ndarray = None
    hull_normal: np.ndarray = None     # (n, 3): where the hull extrudes (NORMAL where the export left it out)
    outline_w: np.ndarray = None       # (n,): the outline's per-vertex factor (1 where the export left it out)
    face_mask: np.ndarray = None
    ink_w: np.ndarray = None
    targets: dict = field(default_factory=dict)    # shape key name -> (n, 3) POSITION delta

    @property
    def outline(self):
        return self.mx.get('outline')

    def hull_dir(self):
        return self.hull_normal if self.hull_normal is not None else self.normal

    def width_factor(self):
        return self.outline_w if self.outline_w is not None else np.ones(len(self.position), np.float32)

    def co(self):
        """the original surface (where Blender's hull is): POSITION moved back out by the build width."""
        if not self.outline:
            return self.position
        w = float(self.outline['width'])
        return (self.position + self.hull_dir() * (w * self.width_factor())[:, None]).astype(np.float32)


@dataclass
class Model:
    path: str
    js: dict
    root: dict
    materials: list
    prims: list
    textures: dict                     # glTF texture index -> (h, w, 4) float32
    texture_info: dict                 # glTF texture index -> {'name', 'kind': 'color' | 'data', 'encoding'}

    @property
    def head(self):
        return self.root.get('head') or {'centre': [0.0, 1.4, 0.0], 'L': 0.25}

    def bounds(self):
        P = np.concatenate([p.position for p in self.prims])
        return P.min(0), P.max(0)


def _decode_png(data):
    from PIL import Image
    im = Image.open(io.BytesIO(data))
    im.load()
    a = np.asarray(im.convert('RGBA') if im.mode not in ('RGBA',) else im)
    return a


def load(path, targets=False):
    """our export -> Model. targets: also read the morph targets (the shape keys; not needed for the build pose)."""
    js, bin_ = read_glb(path)
    A = Accessors(js, bin_)
    root = (js.get('extensions') or {}).get(EXT)
    if root is None:
        raise ValueError(f'{path}: no {EXT} (not a charkit export)')
    mats = [((m.get('extensions') or {}).get(EXT) or {'kind': 'flat', 'color': [0.8, 0.8, 0.8], 'doubleSided': True,
                                                     'alpha': 'opaque'}) for m in js.get('materials', [])]
    # which textures are data (the face's SDF and fringe: linear, as stored) and which colour (sRGB -> linear)
    kinds = {}
    for L in mats:
        F = L.get('face') or {}
        for k in ('sdf', 'fringe'):
            if k in F:
                kinds[F[k]['index']] = ('data', F[k].get('encoding'))
        for info in [L.get('texture'), F.get('blush'), F.get('ink')]:
            if info and info['index'] not in kinds:
                kinds[info['index']] = ('color', None)
    textures, tinfo = {}, {}
    for ti, kd in kinds.items():
        t = js['textures'][ti]
        img = js['images'][t['source']]
        raw, _ = A.view(img['bufferView'])
        px = _decode_png(bytes(raw))
        kind, enc = kd
        if enc == 'rg16':
            v = (px[..., 0].astype(np.float32) * 256.0 + px[..., 1].astype(np.float32)) / 65535.0
            out = np.stack([v, v, v, np.ones_like(v)], -1)
        elif kind == 'data':
            out = px.astype(np.float32) / 255.0
        else:
            out = px.astype(np.float32) / 255.0
            out[..., :3] = srgb_to_linear(out[..., :3])
        textures[ti] = np.ascontiguousarray(out, np.float32)
        tinfo[ti] = {'name': t.get('name', img.get('name')), 'kind': kind, 'encoding': enc, 'size': out.shape[:2]}
    prims = []
    for mesh in js['meshes']:
        mx = (mesh.get('extensions') or {}).get(EXT) or {}
        names = (mesh.get('extras') or {}).get('targetNames', [])
        for pr in mesh['primitives']:
            if pr.get('mode', 4) != 4:
                continue
            at = pr['attributes']
            get = lambda k: A(at[k]).astype(np.float32) if k in at else None
            P = Prim(mesh=mesh['name'], object=mx.get('object', mesh['name']), material=pr.get('material', -1),
                     look=mats[pr['material']] if pr.get('material') is not None else mats[0] if mats else {},
                     mx=mx, position=get('POSITION'), normal=get('NORMAL'),
                     index=A(pr['indices']).astype(np.uint32) if 'indices' in pr else
                     np.arange(A.js['accessors'][at['POSITION']]['count'], dtype=np.uint32),
                     uv0=get('TEXCOORD_0'), uv1=get('TEXCOORD_1'), hull_normal=get('_HULL_NORMAL'),
                     outline_w=get('_OUTLINE_WIDTH'), face_mask=get('_FACE_MASK'), ink_w=get('_INK_W'))
            if P.normal is None:
                raise ValueError(f'{mesh["name"]}: no NORMAL')
            if targets:
                for k, t in zip(names, pr.get('targets', [])):
                    if 'POSITION' in t:
                        P.targets[k] = A(t['POSITION']).astype(np.float32)
            prims.append(P)
    return Model(path=os.path.abspath(path), js=js, root=root, materials=mats, prims=prims, textures=textures,
                 texture_info=tinfo)
