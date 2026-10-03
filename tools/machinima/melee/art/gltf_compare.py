"""gltf_compare.py: compare two skinned glTFs numerically (a model before `datkit gltf-model`/fighter-build and after
`datkit export`): joint world transforms, and per primitive the triangles (positions, normals, winding), skin weights, UVs
and the texels each triangle's corners sample.

  .venv/bin/python tools/machinima/melee/art/gltf_compare.py A.gltf B.gltf [--json OUT.json] [--pairs 0:0,1:1]

Joints are matched by name (datkit export names them J00..Jnn in the rig's order; `--rig rig.json` maps the rig's
names and, through its "jnames", A's J%02d names; `--jmap A=B,...` adds others; `--wmap A=B,...` folds A's joints into
B's for the weight comparison only). Primitives are paired in order unless --pairs says otherwise. Every triangle of B is
matched to the nearest triangle of A (by corner positions, any rotation of its corners): the rotation that matches means
the same winding, a reflection means it is flipped. Texels are compared by sampling each image at the corners' UVs
(nearest texel, the image as the glTF references it), so a texture that moved, flipped or changed shows up.
"""
import json, math, os, struct, sys, zlib
import numpy as np

CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


class G:
    def __init__(self, path):
        self.path = path; self.dir = os.path.dirname(os.path.abspath(path))
        self.j = json.load(open(path))
        self.bufs = []
        for b in self.j.get('buffers', []):
            u = b['uri']
            if u.startswith('data:'):
                import base64; self.bufs.append(base64.b64decode(u.split(',', 1)[1]))
            else:
                self.bufs.append(open(os.path.join(self.dir, u), 'rb').read())
        n = len(self.j['nodes'])
        self.parent = [-1] * n
        for i, nd in enumerate(self.j['nodes']):
            for c in nd.get('children', []): self.parent[c] = i
        self.local = [self.node_matrix(nd) for nd in self.j['nodes']]
        self.world = [None] * n
        for i in range(n): self.w(i)
        self.names = [nd.get('name', f'node{i}') for i, nd in enumerate(self.j['nodes'])]
        self._img = {}

    @staticmethod
    def node_matrix(nd):
        if 'matrix' in nd: return np.array(nd['matrix'], np.float64).reshape(4, 4).T     # column vectors
        t = nd.get('translation', [0, 0, 0]); x, y, z, w = nd.get('rotation', [0, 0, 0, 1]); s = nd.get('scale', [1, 1, 1])
        R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                      [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                      [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
        M = np.eye(4); M[:3, :3] = R @ np.diag(s); M[:3, 3] = t
        return M

    def w(self, i):
        if self.world[i] is None:
            p = self.parent[i]
            self.world[i] = self.local[i] if p < 0 else self.w(p) @ self.local[i]
        return self.world[i]

    def acc(self, ai):
        a = self.j['accessors'][ai]; bv = self.j['bufferViews'][a['bufferView']]
        dt = np.dtype(CT[a['componentType']]).newbyteorder('<'); nc = NC[a['type']]
        off = bv.get('byteOffset', 0) + a.get('byteOffset', 0); stride = bv.get('byteStride', nc * dt.itemsize)
        buf = self.bufs[bv['buffer']]
        if stride == nc * dt.itemsize:
            arr = np.frombuffer(buf, dt, a['count'] * nc, off).reshape(a['count'], nc)
        else:
            arr = np.stack([np.frombuffer(buf, dt, nc, off + i * stride) for i in range(a['count'])])
        arr = arr.astype(np.float64)
        if a.get('normalized'):
            arr = arr / {5121: 255., 5123: 65535., 5120: 127., 5122: 32767.}[a['componentType']]
        return arr

    def image(self, tex_index):
        src = self.j['textures'][tex_index]['source']
        if src not in self._img:
            im = self.j['images'][src]
            if 'uri' in im: data = open(os.path.join(self.dir, im['uri']), 'rb').read()
            else:
                bv = self.j['bufferViews'][im['bufferView']]; data = self.bufs[bv['buffer']][bv.get('byteOffset', 0):bv.get('byteOffset', 0) + bv['byteLength']]
            self._img[src] = png_rgba(data)
        return self._img[src]

    def prims(self):
        out = []
        for ni, nd in enumerate(self.j['nodes']):
            if 'mesh' not in nd: continue
            for p in self.j['meshes'][nd['mesh']]['primitives']:
                out.append((ni, p))
        return out


def png_rgba(data):
    """8-bit RGBA/RGB/grey PNG -> HxWx4 uint8 (enough for the test images and datkit's exports)."""
    from PIL import Image
    import io
    return np.array(Image.open(io.BytesIO(data)).convert('RGBA'))


def tris_of(g, ni, p, skinned=True):
    at = p['attributes']
    P = g.acc(at['POSITION'])
    idx = g.acc(p['indices']).astype(int).ravel() if 'indices' in p else np.arange(len(P))
    T = idx.reshape(-1, 3)
    N = g.acc(at['NORMAL']) if 'NORMAL' in at else None
    UV = g.acc(at['TEXCOORD_0']) if 'TEXCOORD_0' in at else None
    J = g.acc(at['JOINTS_0']).astype(int) if 'JOINTS_0' in at else None
    W = g.acc(at['WEIGHTS_0']) if 'WEIGHTS_0' in at else None
    # rest-pose world positions: skinned vertices through their joints (joint world * IBM), else the node's world
    node = g.j['nodes'][ni]
    if skinned and 'skin' in node and J is not None:
        sk = g.j['skins'][node['skin']]
        ibm = g.acc(sk['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1) if 'inverseBindMatrices' in sk else np.tile(np.eye(4), (len(sk['joints']), 1, 1))
        M = np.stack([g.world[jn] @ ibm[k] for k, jn in enumerate(sk['joints'])])
        Ph = np.c_[P, np.ones(len(P))]
        Pw = np.zeros((len(P), 3)); Nw = np.zeros((len(P), 3))
        for c in range(4):
            m = M[J[:, c]]
            Pw += W[:, c:c + 1] * np.einsum('nij,nj->ni', m, Ph)[:, :3]
            if N is not None: Nw += W[:, c:c + 1] * np.einsum('nij,nj->ni', m[:, :3, :3], N)
        jn = [g.names[j] for j in sk['joints']]
    else:
        Mw = g.world[ni]; Pw = (np.c_[P, np.ones(len(P))] @ Mw.T)[:, :3]
        Nw = N @ Mw[:3, :3].T if N is not None else None; jn = None
    if N is not None: Nw = Nw / np.maximum(np.linalg.norm(Nw, axis=1, keepdims=True), 1e-12)
    return dict(T=T, P=Pw, N=Nw if N is not None else None, UV=UV, J=J, W=W, jn=jn)


def texels(g, p, d):
    """the texel colour at each corner of each triangle (nearest texel), or None"""
    mat = g.j['materials'][p['material']] if 'material' in p else {}
    bt = mat.get('pbrMetallicRoughness', {}).get('baseColorTexture')
    if bt is None or d['UV'] is None: return None
    img = g.image(bt['index']).astype(np.float64); h, w = img.shape[:2]
    uv = d['UV'].copy()
    T = d['T']; cen = uv[T].mean(1)                                    # per triangle: corners pulled 20% toward the centre
    uv = (0.8 * uv[T] + 0.2 * cen[:, None, :]).reshape(-1, 2)
    xf = bt.get('extensions', {}).get('KHR_texture_transform')
    if xf: uv = uv * np.array(xf.get('scale', [1, 1])) + np.array(xf.get('offset', [0, 0]))
    # wrap as the sampler says (datkit exports CLAMP/REPEAT/MIRROR)
    samp = g.j['samplers'][g.j['textures'][bt['index']]['sampler']] if 'sampler' in g.j['textures'][bt['index']] else {}
    def wrap(u, mode):
        if mode == 33071: return np.clip(u, 0, 1 - 1e-6)
        if mode == 33648: f = np.mod(u, 2); return np.where(f > 1, 2 - f, f).clip(0, 1 - 1e-6)
        return np.mod(u, 1)
    u = wrap(uv[:, 0], samp.get('wrapS', 10497)); v = wrap(uv[:, 1], samp.get('wrapT', 10497))
    x = np.clip((u * w).astype(int), 0, w - 1); y = np.clip((v * h).astype(int), 0, h - 1)
    return img[y, x].reshape(len(T), 3, -1)                           # per triangle corner


def base_image(g, p):
    mat = g.j['materials'][p['material']] if 'material' in p else {}
    bt = mat.get('pbrMetallicRoughness', {}).get('baseColorTexture')
    return None if bt is None else g.image(bt['index'])


def compare_prims(A, B, texA=None, texB=None):
    ta = A['P'][A['T']]; tb = B['P'][B['T']]           # (n,3,3)
    ca = ta.mean(1); cb = tb.mean(1)
    res = dict(trisA=len(ta), trisB=len(tb))
    if len(ta) == 0 or len(tb) == 0: return res
    # nearest triangle by centroid, then the best corner correspondence (3 rotations, 3 reflections)
    perms = [(0, 1, 2), (1, 2, 0), (2, 0, 1), (0, 2, 1), (2, 1, 0), (1, 0, 2)]
    match = np.empty(len(tb), int); best = np.empty(len(tb), int); err = np.empty(len(tb))
    for s in range(0, len(tb), 512):
        d = ((cb[s:s + 512, None, :] - ca[None, :, :]) ** 2).sum(-1)
        cand = np.argsort(d, axis=1)[:, :8]
        for r, row in enumerate(cand):
            i = s + r; bestv = 1e30
            for c in row:
                for k, pm in enumerate(perms):
                    e = np.abs(tb[i] - ta[c][list(pm)]).max()
                    if e < bestv: bestv, match[i], best[i] = e, c, k
            err[i] = bestv
    res['pos_max'] = float(err.max()); res['pos_mean'] = float(err.mean())
    res['unmatched'] = int((err > 0.01).sum())
    res['flipped'] = int((best >= 3).sum())
    res['matchedA'] = int(len(set(match.tolist())))
    corner = lambda k: np.array(perms)[best][:, k]
    if A['N'] is not None and B['N'] is not None:
        na = A['N'][A['T']]; nb = B['N'][B['T']]
        ang = []
        for k in range(3):
            va = na[match, corner(k)]; vb = nb[:, k]
            ang.append(np.degrees(np.arccos(np.clip((va * vb).sum(1), -1, 1))))
        ang = np.concatenate(ang); res['nrm_max_deg'] = float(ang.max()); res['nrm_mean_deg'] = float(ang.mean())
    if A['W'] is not None and B['W'] is not None and A['jn'] and B['jn']:
        def infl(D, t, c):
            v = D['T'][t, c]; return {D['jn'][j]: w for j, w in zip(D['J'][v], D['W'][v]) if w > 1e-6}
        wmax = 0.0
        for i in range(len(tb)):
            for k in range(3):
                ia = infl(A, match[i], corner(k)[i]); ib = infl(B, i, k)
                for key in set(ia) | set(ib): wmax = max(wmax, abs(ia.get(key, 0) - ib.get(key, 0)))
        res['weight_max'] = float(wmax)
    if A['UV'] is not None and B['UV'] is not None:
        ua = A['UV'][A['T']]; ub = B['UV'][B['T']]
        du = np.concatenate([np.abs(ua[match, corner(k)] - ub[:, k]).max(1) for k in range(3)])
        res['uv_max'] = float(du.max()); res['uv_mean'] = float(du.mean())
    if texA is not None and texB is not None:
        xa, xb = texA, texB
        dt = np.concatenate([np.abs(xa[match, corner(k)] - xb[:, k]).max(1) for k in range(3)])
        res['texel_max'] = float(dt.max()); res['texel_mean'] = float(dt.mean()); res['texel_over16'] = int((dt > 16).sum())
    return res


def main():
    a, b = sys.argv[1], sys.argv[2]
    opt = lambda k: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else None
    GA, GB = G(a), G(b)
    jmap = {}
    if opt('--rig'):
        rig = json.load(open(opt('--rig')))
        names = [j['name'] for j in rig['joints']]
        jmap = {n: f'J{i:02d}' for i, n in enumerate(names)}
        # "J%02d" names in A index the skeleton it was skinned to (rig.json jnames), B's are the rig's own order
        jmap.update({f'J{i:02d}': f'J{names.index(n):02d}' for i, n in enumerate(rig.get('jnames', [])) if n in names})
    if opt('--jmap'): jmap.update(dict(kv.split('=') for kv in opt('--jmap').split(',')))
    wmap = dict(kv.split('=') for kv in opt('--wmap').split(',')) if opt('--wmap') else {}   # weights only (joints A has, B folded)
    out = {'a': a, 'b': b}
    # joints
    ib = {n: i for i, n in enumerate(GB.names)}
    dj = []; missing = []
    for i, n in enumerate(GA.names):
        if 'mesh' in GA.j['nodes'][i]: continue
        m = jmap.get(n, n)
        if m not in ib: missing.append(n); continue
        WA, WB = GA.world[i], GB.world[ib[m]]
        dj.append((np.abs(WA[:3, 3] - WB[:3, 3]).max(), np.abs(WA[:3, :3] - WB[:3, :3]).max(), n))
    out['joints'] = dict(matched=len(dj), missing=missing, trans_max=max((d[0] for d in dj), default=0), rot_max=max((d[1] for d in dj), default=0))
    PA, PB = GA.prims(), GB.prims()
    pairs = [tuple(map(int, s.split(':'))) for s in opt('--pairs').split(',')] if opt('--pairs') else list(zip(range(len(PA)), range(len(PB))))
    out['prims'] = []
    for ia, ibb in pairs:
        (na, pa), (nb, pb) = PA[ia], PB[ibb]
        A, B = tris_of(GA, na, pa), tris_of(GB, nb, pb)
        if A['jn']: A['jn'] = [jmap.get(n, n) for n in A['jn']]
        if A['jn']: A['jn'] = [wmap.get(n, n) for n in A['jn']]
        r = compare_prims(A, B, texels(GA, pa, A), texels(GB, pb, B))
        r['pair'] = [ia, ibb]
        ima, imb = base_image(GA, pa), base_image(GB, pb)
        if ima is not None and imb is not None:
            if ima.shape == imb.shape:
                d = np.abs(ima.astype(int) - imb.astype(int))[..., :3]; m = ima[..., 3] > 0
                r['img'] = f'{ima.shape[1]}x{ima.shape[0]}'; r['img_max'] = int(d[m].max()); r['img_mean'] = float(d[m].mean())
            else: r['img'] = f'{ima.shape[1]}x{ima.shape[0]} vs {imb.shape[1]}x{imb.shape[0]}'
        out['prims'].append(r)
    tot = lambda k, f=max: f([p[k] for p in out['prims'] if k in p]) if any(k in p for p in out['prims']) else None
    out['summary'] = dict(prims=len(pairs), trisA=tot('trisA', sum), trisB=tot('trisB', sum), pos_max=tot('pos_max'), unmatched=tot('unmatched', sum),
                          flipped=tot('flipped', sum), nrm_max_deg=tot('nrm_max_deg'), nrm_mean_deg=tot('nrm_mean_deg', lambda v: float(np.mean(v))),
                          weight_max=tot('weight_max'), uv_max=tot('uv_max'), texel_max=tot('texel_max'), texel_mean=tot('texel_mean', lambda v: float(np.mean(v))),
                          img_max=tot('img_max'), img_mean=tot('img_mean', lambda v: float(np.mean(v))))
    if opt('--json'): json.dump(out, open(opt('--json'), 'w'), indent=1)
    print(json.dumps(out['joints']))
    for p in out['prims']: print(json.dumps({k: (round(v, 6) if isinstance(v, float) else v) for k, v in p.items()}))
    print('SUMMARY', json.dumps({k: (round(v, 6) if isinstance(v, float) else v) for k, v in out['summary'].items()}))


if __name__ == '__main__':
    main()
