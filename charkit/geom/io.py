"""Mesh IO in plain numpy (PIL only to decode glTF textures), so the same readers run in the venv and in Blender's Python:

    load(path)            .glb/.gltf, .ply, .obj, .npz  -> Mesh (per-vertex colour sampled from a glTF base-colour texture)
    save(mesh, path)      .glb, .ply (binary), .obj, .npz

glTF is y-up; `load(..., z_up=True)` turns it into Blender's frame ((x, y, z) -> (x, -z, y)) as Blender's importer does,
so vertex i here is vertex i of a Blender import of the same file.
"""
import io as _io
import json
import os
import struct

import numpy as np

from .mesh import Mesh, y_up_to_z_up, z_up_to_y_up


def load(path, z_up=None, **kw):
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.glb', '.gltf'):
        return load_gltf(path, z_up=True if z_up is None else z_up, **kw)
    if ext == '.ply':
        return load_ply(path)
    if ext == '.obj':
        return load_obj(path)
    if ext == '.npz':
        return load_npz(path)
    raise ValueError(f'unsupported mesh format {ext!r}')


def save(m, path, **kw):
    ext = os.path.splitext(path)[1].lower()
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    if ext == '.glb':
        return save_glb(m, path, **kw)
    if ext == '.ply':
        return save_ply(m, path, **kw)
    if ext == '.obj':
        return save_obj(m, path, **kw)
    if ext == '.npz':
        return save_npz(m, path, **kw)
    raise ValueError(f'unsupported mesh format {ext!r}')


# ------------------------------------------------------------------------------------------------------------------ colour
def srgb_to_linear(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(np.asarray(c, float), 0, None)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def sample_texture(img, uv, mode='bilinear'):
    """sample an (H,W,C) float image at glTF UVs (u right, v down from the top-left; repeat wrap). mode: 'bilinear' or
    'nearest'."""
    h, w = img.shape[:2]
    u = np.mod(uv[:, 0], 1.0) * w - 0.5
    v = np.mod(uv[:, 1], 1.0) * h - 0.5
    if mode == 'nearest':
        xi = np.mod(np.round(u).astype(np.int64), w)
        yi = np.mod(np.round(v).astype(np.int64), h)
        return img[yi, xi]
    x0 = np.floor(u).astype(np.int64); y0 = np.floor(v).astype(np.int64)
    fx = (u - x0)[:, None]; fy = (v - y0)[:, None]
    x1 = np.mod(x0 + 1, w); y1 = np.mod(y0 + 1, h); x0 = np.mod(x0, w); y0 = np.mod(y0, h)
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x1] * fx * (1 - fy) +
            img[y1, x0] * (1 - fx) * fy + img[y1, x1] * fx * fy)


# -------------------------------------------------------------------------------------------------------------------- glTF
_CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
_NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def _read_gltf(path):
    raw = open(path, 'rb').read()
    if raw[:4] == b'glTF':
        _, _, length = struct.unpack('<III', raw[:12])
        off, J, BIN = 12, None, None
        while off < length:
            cl, ct = struct.unpack('<II', raw[off:off + 8])
            chunk = raw[off + 8:off + 8 + cl]
            if ct == 0x4E4F534A:
                J = json.loads(chunk)
            elif ct == 0x004E4942:
                BIN = chunk
            off += 8 + cl
        bufs = [BIN]
    else:
        J = json.loads(raw)
        bufs = []
    base = os.path.dirname(os.path.abspath(path))
    for i, b in enumerate(J.get('buffers', [])):
        if 'uri' in b:
            uri = b['uri']
            if uri.startswith('data:'):
                import base64
                data = base64.b64decode(uri.split(',', 1)[1])
            else:
                data = open(os.path.join(base, uri), 'rb').read()
            if i < len(bufs):
                bufs[i] = data
            else:
                bufs.append(data)
    return J, bufs, base


def _accessor(J, bufs, i):
    a = J['accessors'][i]
    dt = np.dtype(_CT[a['componentType']])
    nc = _NC[a['type']]
    n = a['count']
    if 'bufferView' not in a:
        out = np.zeros((n, nc), dt)
    else:
        bv = J['bufferViews'][a['bufferView']]
        buf = bufs[bv.get('buffer', 0)]
        off = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
        stride = bv.get('byteStride', 0) or dt.itemsize * nc
        if stride == dt.itemsize * nc:
            out = np.frombuffer(buf, dt, n * nc, off).reshape(n, nc).copy()
        else:
            rows = np.frombuffer(buf, np.uint8, (n - 1) * stride + dt.itemsize * nc, off)
            out = np.stack([np.frombuffer(rows[k * stride:k * stride + dt.itemsize * nc].tobytes(), dt) for k in range(n)])
    if 'sparse' in a:
        s = a['sparse']
        ib = J['bufferViews'][s['indices']['bufferView']]
        idx = np.frombuffer(bufs[ib.get('buffer', 0)], _CT[s['indices']['componentType']], s['count'],
                            ib.get('byteOffset', 0) + s['indices'].get('byteOffset', 0))
        vb = J['bufferViews'][s['values']['bufferView']]
        val = np.frombuffer(bufs[vb.get('buffer', 0)], dt, s['count'] * nc,
                            vb.get('byteOffset', 0) + s['values'].get('byteOffset', 0)).reshape(-1, nc)
        out = out.copy(); out[idx] = val
    if a.get('normalized') and dt.kind in 'iu':
        out = out.astype(np.float64) / np.iinfo(dt).max
    return out


def _image(J, bufs, base, ti, cache):
    if ti in cache:
        return cache[ti]
    from PIL import Image
    src = J['textures'][ti].get('source')
    im = J['images'][src]
    if 'bufferView' in im:
        bv = J['bufferViews'][im['bufferView']]
        data = bufs[bv.get('buffer', 0)][bv.get('byteOffset', 0):bv.get('byteOffset', 0) + bv['byteLength']]
        pil = Image.open(_io.BytesIO(data))
    elif im.get('uri', '').startswith('data:'):
        import base64
        pil = Image.open(_io.BytesIO(base64.b64decode(im['uri'].split(',', 1)[1])))
    else:
        pil = Image.open(os.path.join(base, im['uri']))
    arr = np.asarray(pil.convert('RGBA'), dtype=np.float32) / 255.0
    cache[ti] = arr
    return arr


def _node_matrix(nd):
    if 'matrix' in nd:
        return np.array(nd['matrix'], float).reshape(4, 4).T
    M = np.eye(4)
    if 'scale' in nd:
        M = np.diag(list(nd['scale']) + [1.0]) @ M
    if 'rotation' in nd:
        x, y, z, w = nd['rotation']
        R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                      [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                      [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
        Rm = np.eye(4); Rm[:3, :3] = R
        M = Rm @ M
    if 'translation' in nd:
        T = np.eye(4); T[:3, 3] = nd['translation']
        M = T @ M
    return M


def load_gltf(path, z_up=True, colors='bilinear', blender_compat=False):
    """a glTF/GLB's triangle primitives joined into one Mesh in world space (node transforms applied), with per-vertex
    colour vc (sRGB 0..1): the base-colour texture sampled at each vertex's UV ('bilinear' or 'nearest') times the
    material's baseColorFactor and COLOR_0 when present; vn from NORMAL; uv from TEXCOORD_0.
    blender_compat: reproduce charkit.i3d.load_glb's colours exactly (its nearest texel, and the extra linear->sRGB
    encoding it applies to Blender's already-sRGB pixels), so i3d.find_eyes and friends see the same numbers."""
    J, bufs, base = _read_gltf(path)
    cache = {}
    Vs, Fs, Cs, Ns, Us = [], [], [], [], []
    off = 0
    scene = J.get('scenes', [{}])[J.get('scene', 0)] if J.get('scenes') else {'nodes': list(range(len(J.get('nodes', []))))}
    stack = [(n, np.eye(4)) for n in scene.get('nodes', [])]
    if not stack and J.get('meshes'):
        stack = []
        for mi in range(len(J['meshes'])):
            J.setdefault('nodes', []).append({'mesh': mi})
            stack.append((len(J['nodes']) - 1, np.eye(4)))
    while stack:
        ni, P = stack.pop(0)
        nd = J['nodes'][ni]
        M = P @ _node_matrix(nd)
        for c in nd.get('children', []):
            stack.append((c, M))
        if 'mesh' not in nd:
            continue
        for pr in J['meshes'][nd['mesh']]['primitives']:
            mode = pr.get('mode', 4)
            if mode not in (4, 5, 6):
                continue
            at = pr['attributes']
            V = _accessor(J, bufs, at['POSITION']).astype(np.float64)
            n = len(V)
            if 'indices' in pr:
                idx = _accessor(J, bufs, pr['indices']).ravel().astype(np.int64)
            else:
                idx = np.arange(n, dtype=np.int64)
            if mode == 4:
                F = idx.reshape(-1, 3)
            elif mode == 5:
                F = np.array([(idx[i], idx[i + 1], idx[i + 2]) if i % 2 == 0 else (idx[i + 1], idx[i], idx[i + 2])
                              for i in range(len(idx) - 2)], np.int64).reshape(-1, 3)
            else:
                F = np.array([(idx[0], idx[i], idx[i + 1]) for i in range(1, len(idx) - 1)], np.int64).reshape(-1, 3)
            Vw = V @ M[:3, :3].T + M[:3, 3]
            if np.linalg.det(M[:3, :3]) < 0:
                F = F[:, ::-1]
            N = None
            if 'NORMAL' in at:
                N = _accessor(J, bufs, at['NORMAL']).astype(np.float64) @ np.linalg.inv(M[:3, :3])
                N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-300)
            uv = _accessor(J, bufs, at['TEXCOORD_0']).astype(np.float64) if 'TEXCOORD_0' in at else None
            col = np.ones((n, 3))
            mat = J['materials'][pr['material']] if 'material' in pr and J.get('materials') else {}
            pbr = mat.get('pbrMetallicRoughness', {})
            fac = np.array(pbr.get('baseColorFactor', [1, 1, 1, 1])[:3], float)
            tex = pbr.get('baseColorTexture')
            if tex is not None and 'TEXCOORD_%d' % tex.get('texCoord', 0) in at:
                img = _image(J, bufs, base, tex['index'], cache)[..., :3]
                tuv = _accessor(J, bufs, at['TEXCOORD_%d' % tex.get('texCoord', 0)]).astype(np.float64)
                if blender_compat:
                    h, w = img.shape[:2]
                    # Blender flips v and stores rows bottom-up; i3d.load_glb takes the texel at floor(v' * (h-1))
                    xi = np.clip((tuv[:, 0] % 1) * (w - 1), 0, w - 1).astype(np.int64)
                    yi = np.clip(((1 - tuv[:, 1]) % 1) * (h - 1), 0, h - 1).astype(np.int64)
                    col = linear_to_srgb(img[h - 1 - yi, xi].astype(np.float64))
                else:
                    col = sample_texture(img, tuv, colors).astype(np.float64)
            if 'COLOR_0' in at:
                c0 = _accessor(J, bufs, at['COLOR_0']).astype(np.float64)[:, :3]
                if c0.max() > 1.0:
                    c0 = c0 / 255.0
                col = linear_to_srgb(srgb_to_linear(col) * c0)
            if not blender_compat and np.any(fac != 1.0):
                col = linear_to_srgb(srgb_to_linear(col) * fac)
            Vs.append(Vw); Fs.append(F + off); Cs.append(col); Ns.append(N); Us.append(uv)
            off += n
    if not Vs:
        raise ValueError(f'{path}: no triangle meshes')
    kw = dict(vc=np.vstack(Cs))
    if all(x is not None for x in Ns):
        kw['vn'] = np.vstack(Ns)
    if all(x is not None for x in Us):
        kw['uv'] = np.vstack(Us)
    m = Mesh(np.vstack(Vs), np.vstack(Fs), **kw)
    return y_up_to_z_up(m) if z_up else m


def save_glb(m, path, z_up=True):
    """a GLB with POSITION, NORMAL (vn when set), COLOR_0 (vc, as linear floats) and indices; no materials. z_up: the mesh is
    in Blender's frame and is written y-up."""
    if z_up:
        m = z_up_to_y_up(m)
    parts, views, accs = [], [], []
    attrs = {}

    def add(arr, target, typ, comp, minmax=False):
        data = np.ascontiguousarray(arr).tobytes()
        off = sum(len(p) for p in parts)
        pad = (-len(data)) % 4
        parts.append(data + b'\0' * pad)
        views.append({'buffer': 0, 'byteOffset': off, 'byteLength': len(data), 'target': target})
        a = {'bufferView': len(views) - 1, 'componentType': comp, 'count': int(len(arr)), 'type': typ}
        if minmax:
            a['min'] = [float(x) for x in arr.min(0)]; a['max'] = [float(x) for x in arr.max(0)]
        accs.append(a)
        return len(accs) - 1
    ind = add(m.F.astype(np.uint32).ravel(), 34963, 'SCALAR', 5125)
    attrs['POSITION'] = add(m.V.astype(np.float32), 34962, 'VEC3', 5126, minmax=True)
    if m.vn is not None:
        attrs['NORMAL'] = add(m.vn.astype(np.float32), 34962, 'VEC3', 5126)
    if m.vc is not None:
        attrs['COLOR_0'] = add(srgb_to_linear(m.vc[:, :3]).astype(np.float32), 34962, 'VEC3', 5126)
    blob = b''.join(parts)
    J = {'asset': {'version': '2.0', 'generator': 'charkit.geom'}, 'scene': 0, 'scenes': [{'nodes': [0]}],
         'nodes': [{'mesh': 0}], 'meshes': [{'primitives': [{'attributes': attrs, 'indices': ind, 'mode': 4}]}],
         'accessors': accs, 'bufferViews': views, 'buffers': [{'byteLength': len(blob)}]}
    js = json.dumps(J, separators=(',', ':')).encode()
    js += b' ' * ((-len(js)) % 4)
    out = struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(blob))
    out += struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(blob), 0x004E4942) + blob
    open(path, 'wb').write(out)
    return path


# --------------------------------------------------------------------------------------------------------------------- PLY
_PLY_T = {'char': 'i1', 'int8': 'i1', 'uchar': 'u1', 'uint8': 'u1', 'short': 'i2', 'int16': 'i2', 'ushort': 'u2',
          'uint16': 'u2', 'int': 'i4', 'int32': 'i4', 'uint': 'u4', 'uint32': 'u4', 'float': 'f4', 'float32': 'f4',
          'double': 'f8', 'float64': 'f8'}


def load_ply(path):
    """ASCII or binary PLY: vertex x y z [nx ny nz] [red green blue [alpha]] [s t | u v | texture_u texture_v], faces as
    vertex_indices / vertex_index lists (polygons fanned)."""
    raw = open(path, 'rb').read()
    end = raw.index(b'end_header') + len(b'end_header')
    while raw[end:end + 1] in (b'\r', b'\n'):
        end += 1
        if raw[end - 1:end] == b'\n':
            break
    header = raw[:end].decode('ascii', 'replace').splitlines()
    fmt = 'ascii'
    elements = []
    for ln in header:
        t = ln.split()
        if not t:
            continue
        if t[0] == 'format':
            fmt = t[1]
        elif t[0] == 'element':
            elements.append({'name': t[1], 'count': int(t[2]), 'props': []})
        elif t[0] == 'property':
            if t[1] == 'list':
                elements[-1]['props'].append((t[4], 'list', _PLY_T[t[2]], _PLY_T[t[3]]))
            else:
                elements[-1]['props'].append((t[2], _PLY_T[t[1]]))
    body = raw[end:]
    data = {}
    if fmt == 'ascii':
        toks = body.split()
        pos = 0
        for el in elements:
            if any(p[1] == 'list' for p in el['props']):
                rows = []
                for _ in range(el['count']):
                    row = {}
                    for p in el['props']:
                        if p[1] == 'list':
                            k = int(toks[pos]); pos += 1
                            row[p[0]] = [int(x) for x in toks[pos:pos + k]]; pos += k
                        else:
                            row[p[0]] = float(toks[pos]); pos += 1
                    rows.append(row)
                data[el['name']] = rows
            else:
                k = len(el['props'])
                arr = np.array(toks[pos:pos + k * el['count']], dtype=np.float64).reshape(el['count'], k)
                pos += k * el['count']
                data[el['name']] = {p[0]: arr[:, i] for i, p in enumerate(el['props'])}
    else:
        bo = '<' if fmt == 'binary_little_endian' else '>'
        pos = 0
        for el in elements:
            props = el['props']
            if not any(p[1] == 'list' for p in props):
                dt = np.dtype([(p[0], bo + p[1]) for p in props])
                arr = np.frombuffer(body, dt, el['count'], pos)
                pos += dt.itemsize * el['count']
                data[el['name']] = {p[0]: arr[p[0]].astype(np.float64) for p in props}
                continue
            # a list element: fast path for a single list of constant length (triangles)
            if len(props) == 1 and el['count']:
                _, _, ct, it = props[0]
                cs, isz = np.dtype(ct).itemsize, np.dtype(it).itemsize
                k0 = int(np.frombuffer(body, bo + ct, 1, pos)[0])
                dt = np.dtype([('n', bo + ct), ('i', bo + it, (k0,))])
                arr = np.frombuffer(body, dt, el['count'], pos) if pos + dt.itemsize * el['count'] <= len(body) else None
                if arr is not None and np.all(arr['n'] == k0):
                    data[el['name']] = {props[0][0]: arr['i'].astype(np.int64)}
                    pos += dt.itemsize * el['count']
                    continue
            rows = []
            for _ in range(el['count']):
                row = {}
                for p in props:
                    if p[1] == 'list':
                        ct, it = np.dtype(bo + p[2]), np.dtype(bo + p[3])
                        k = int(np.frombuffer(body, ct, 1, pos)[0]); pos += ct.itemsize
                        row[p[0]] = np.frombuffer(body, it, k, pos).astype(np.int64).tolist(); pos += it.itemsize * k
                    else:
                        dt = np.dtype(bo + p[1])
                        row[p[0]] = float(np.frombuffer(body, dt, 1, pos)[0]); pos += dt.itemsize
                rows.append(row)
            data[el['name']] = rows
    vx = data['vertex']
    V = np.stack([vx['x'], vx['y'], vx['z']], 1)
    kw = {}
    if 'nx' in vx:
        kw['vn'] = np.stack([vx['nx'], vx['ny'], vx['nz']], 1)
    if 'red' in vx:
        C = np.stack([vx['red'], vx['green'], vx['blue']], 1)
        kw['vc'] = C / 255.0 if C.max() > 1.0 or any(p[1] == 'u1' for p in elements[0]['props'] if p[0] == 'red') else C
    for a, b in (('s', 't'), ('u', 'v'), ('texture_u', 'texture_v')):
        if a in vx:
            kw['uv'] = np.stack([vx[a], vx[b]], 1)
    F = np.zeros((0, 3), np.int64)
    fc = data.get('face')
    if fc is not None:
        if isinstance(fc, dict):
            key = 'vertex_indices' if 'vertex_indices' in fc else 'vertex_index'
            F = np.asarray(fc[key], np.int64)
            if F.shape[1] != 3:
                return Mesh.from_polys(V, F.tolist(), **kw)
        else:
            key = 'vertex_indices' if fc and 'vertex_indices' in fc[0] else 'vertex_index'
            return Mesh.from_polys(V, [r[key] for r in fc], **kw)
    return Mesh(V, F, **kw)


def save_ply(m, path, ascii=False):
    """binary little-endian PLY: x y z float32, nx ny nz (vn), red green blue uchar (vc), s t (uv); triangles."""
    props = [('x', 'f4'), ('y', 'f4'), ('z', 'f4')]
    cols = [m.V[:, 0], m.V[:, 1], m.V[:, 2]]
    if m.vn is not None:
        props += [('nx', 'f4'), ('ny', 'f4'), ('nz', 'f4')]; cols += [m.vn[:, 0], m.vn[:, 1], m.vn[:, 2]]
    if m.vc is not None:
        c8 = np.clip(np.round(m.vc[:, :3] * 255), 0, 255)
        props += [('red', 'u1'), ('green', 'u1'), ('blue', 'u1')]; cols += [c8[:, 0], c8[:, 1], c8[:, 2]]
    if m.uv is not None:
        props += [('s', 'f4'), ('t', 'f4')]; cols += [m.uv[:, 0], m.uv[:, 1]]
    names = {'f4': 'float', 'u1': 'uchar'}
    hdr = ['ply', 'format %s 1.0' % ('ascii' if ascii else 'binary_little_endian'), 'comment charkit.geom',
           'element vertex %d' % m.nv] + ['property %s %s' % (names[t], n) for n, t in props] + \
          ['element face %d' % m.nf, 'property list uchar int vertex_indices', 'end_header']
    with open(path, 'wb') as fh:
        fh.write(('\n'.join(hdr) + '\n').encode('ascii'))
        if ascii:
            for i in range(m.nv):
                fh.write((' '.join(('%d' % c[i]) if t == 'u1' else ('%.7g' % c[i]) for c, (_, t) in zip(cols, props)) +
                          '\n').encode())
            for f in m.F:
                fh.write(('3 %d %d %d\n' % tuple(f)).encode())
        else:
            dt = np.dtype([(n, '<' + t) for n, t in props])
            arr = np.empty(m.nv, dt)
            for (n, _), c in zip(props, cols):
                arr[n] = c
            fh.write(arr.tobytes())
            ft = np.empty(m.nf, np.dtype([('n', 'u1'), ('i', '<i4', (3,))]))
            ft['n'] = 3; ft['i'] = m.F
            fh.write(ft.tobytes())
    return path


# --------------------------------------------------------------------------------------------------------------------- OBJ
def load_obj(path):
    V, VT, VN, faces = [], [], [], []
    for ln in open(path, encoding='utf-8', errors='replace'):
        t = ln.split()
        if not t:
            continue
        if t[0] == 'v':
            V.append([float(x) for x in t[1:4]])
        elif t[0] == 'vt':
            VT.append([float(x) for x in t[1:3]])
        elif t[0] == 'vn':
            VN.append([float(x) for x in t[1:4]])
        elif t[0] == 'f':
            idx = []
            for w in t[1:]:
                i = int(w.split('/')[0])
                idx.append(i - 1 if i > 0 else len(V) + i)
            faces.append(idx)
    return Mesh.from_polys(np.array(V, float).reshape(-1, 3), faces)


def save_obj(m, path):
    with open(path, 'w') as fh:
        fh.write('# charkit.geom\n')
        np.savetxt(fh, m.V, fmt='v %.7g %.7g %.7g')
        if m.vn is not None:
            np.savetxt(fh, m.vn, fmt='vn %.6g %.6g %.6g')
            np.savetxt(fh, np.repeat(m.F + 1, 2, axis=1), fmt='f %d//%d %d//%d %d//%d')
        else:
            np.savetxt(fh, m.F + 1, fmt='f %d %d %d')
    return path


# --------------------------------------------------------------------------------------------------------------------- NPZ
def save_npz(m, path, meta=None, **extra):
    """V, F and the set attributes (vc, vn, uv), plus `meta` (a JSON-able dict, stored as a string) and any extra arrays."""
    d = {'V': m.V.astype(np.float64), 'F': m.F.astype(np.int64)}
    for k in m.vattrs():
        d[k] = getattr(m, k)
    if meta is not None:
        d['meta'] = np.array(json.dumps(meta))
    d.update({k: np.asarray(v) for k, v in extra.items()})
    np.savez_compressed(path, **d)
    return path


def load_npz(path, with_meta=False):
    d = np.load(path, allow_pickle=False)
    m = Mesh(d['V'], d['F'], **{k: d[k] for k in ('vc', 'vn', 'uv') if k in d.files})
    if with_meta:
        meta = json.loads(str(d['meta'])) if 'meta' in d.files else {}
        return m, meta, {k: d[k] for k in d.files if k not in ('V', 'F', 'vc', 'vn', 'uv', 'meta')}
    return m
