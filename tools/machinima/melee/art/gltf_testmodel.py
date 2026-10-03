"""gltf_testmodel.py: a small skinned, textured test model on a rig's skeleton, for checking `datkit gltf-model` /
fighter-build's glTF import (tools/machinima/melee/art/gltf_compare.py compares it with the export of the result).

  .venv/bin/python tools/machinima/melee/art/gltf_testmodel.py RIG.json OUTDIR

Writes OUTDIR/test.gltf (+ .bin, PNGs), OUTDIR/test_low.gltf and OUTDIR/rig_test.json (RIG.json plus a "model" entry
naming both, with eye slot 0 declared there; slot 1 is declared in its material's extras). The parts, each testing one
path of the importer:
  arm     a tube from LShoulderJ over the elbow (LArmJ) to LHandN, 2-influence blend rings at the elbow; checker texture
  head    a box on HeadN, a gradient texture (non-square 64x128)
  eyes    two quads on the face: CI8 eye textures (100x100: neither a power of two nor whole 8x4 tiles) with 3 frames each
  leg     a box on LLegJ/LKneeJ (a knee blend): metallic (sheen -> SPECULAR) and a specular map (-> a TEX1 layer)
  cape    a double-sided strip on CapeAN..CapeCN plus CapeDN, a joint the rig lacks (its weight goes to CapeCN)
  badge   an alpha-masked quad on WaistN (RGBA texture -> RGB5A3 palette, XLU)
  low     test_low.gltf: an arm box and a head box sharing the high model's checker (one image in the file)
"""
import json, math, os, struct, sys
import numpy as np
from PIL import Image, ImageDraw

rig = json.load(open(sys.argv[1])); OUT = sys.argv[2]; os.makedirs(OUT, exist_ok=True)
J = rig['joints']; NAMES = [j['name'] for j in J]; IX = {n: i for i, n in enumerate(NAMES)}


def rot(rx, ry, rz):
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]]); Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]); Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx          # HSD: rotate X, then Y, then Z (column vectors)


def local(j):
    M = np.eye(4); M[:3, :3] = rot(*j['r']); M[:3, 3] = j['t']; return M


WORLD = []
for j in J:
    WORLD.append(local(j) if j['parent'] < 0 else WORLD[j['parent']] @ local(j))
# an extra joint the rig lacks: CapeDN under CapeCN, 1.8 further down
EXTRA = {'name': 'CapeDN', 'parent': IX['CapeCN'], 't': [0, -1.8, -0.1], 'r': [0, 0, 0]}
EXTRA_W = WORLD[IX['CapeCN']] @ local(EXTRA)
pos = lambda n: (EXTRA_W if n == 'CapeDN' else WORLD[IX[n]])[:3, 3]


def quat(R):
    t = np.trace(R)
    if t > 0:
        s = math.sqrt(t + 1) * 2; return [(R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s, s / 4]
    i = int(np.argmax(np.diag(R))); j, k = (i + 1) % 3, (i + 2) % 3
    s = math.sqrt(1 + R[i, i] - R[j, j] - R[k, k]) * 2
    q = [0, 0, 0, 0]; q[i] = s / 4; q[j] = (R[j, i] + R[i, j]) / s; q[k] = (R[k, i] + R[i, k]) / s; q[3] = (R[k, j] - R[j, k]) / s
    return q


# ---- textures
def checker(path, n=128, cells=8):
    im = Image.new('RGB', (n, n)); d = ImageDraw.Draw(im); c = n // cells
    for y in range(cells):
        for x in range(cells):
            col = (230, 230, 230) if (x + y) % 2 == 0 else (30, 60, 200)
            if x < cells // 2 and y < cells // 2 and (x + y) % 2: col = (200, 40, 30)     # a red quadrant: top-left
            if x >= cells // 2 and y >= cells // 2 and (x + y) % 2: col = (40, 170, 60)   # green: bottom-right
            d.rectangle([x * c, y * c, x * c + c - 1, y * c + c - 1], fill=col)
    im.save(path)


def gradient(path, w=64, h=128):
    a = np.zeros((h, w, 3), np.uint8)
    a[..., 0] = np.linspace(255, 0, w)[None, :]; a[..., 2] = np.linspace(0, 255, w)[None, :]; a[..., 1] = np.linspace(40, 220, h)[:, None]
    Image.fromarray(a).save(path)


def eye(path, k, n=100):
    im = Image.new('RGB', (n, n), (250, 250, 245)); d = ImageDraw.Draw(im)
    if k == 2: d.rectangle([10, 46, 90, 54], fill=(20, 10, 10))                         # closed
    else:
        r = 28 if k == 0 else 16
        d.ellipse([50 - r, 50 - r, 50 + r, 50 + r], fill=(40, 90, 200)); d.ellipse([50 - r // 2, 50 - r // 2, 50 + r // 2, 50 + r // 2], fill=(10, 10, 20))
        d.rectangle([0, 0, n - 1, 12 + 20 * k], fill=(180, 130, 90))                  # the lid, lower on the half-closed frame
    im.save(path)


def badge(path, n=32):
    im = Image.new('RGBA', (n, n), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.polygon([(16, 1), (20, 12), (31, 12), (22, 19), (26, 30), (16, 23), (6, 30), (10, 19), (1, 12), (12, 12)], fill=(255, 210, 0, 255))
    im.save(path)


checker(os.path.join(OUT, 'checker.png')); gradient(os.path.join(OUT, 'gradient.png'))
for side in 'RL':
    for k in range(3): eye(os.path.join(OUT, f'eye{side}_{k}.png'), k)
badge(os.path.join(OUT, 'badge.png'))
Image.new('RGB', (32, 32), (200, 200, 200)).save(os.path.join(OUT, 'specmap.png'))


# ---- geometry helpers: each part is (positions, normals, uvs, [(joint, weight)...] per vertex, triangles CCW)
class Part:
    def __init__(self, name, mat): self.name, self.mat, self.P, self.N, self.UV, self.W, self.T = name, mat, [], [], [], [], []
    def v(self, p, n, uv, w): self.P.append(list(map(float, p))); self.N.append(list(map(float, n / np.linalg.norm(n)))); self.UV.append(list(map(float, uv))); self.W.append(w); return len(self.P) - 1


def tube(part, a, b, c, r, rings_per, weights):
    """a tube a->b->c (two segments); weights(s) -> [(joint, w)] for s in [0, 2] along it"""
    pts = [a + (b - a) * t for t in np.linspace(0, 1, rings_per, endpoint=False)] + [b + (c - b) * t for t in np.linspace(0, 1, rings_per + 1)]
    ss = list(np.linspace(0, 1, rings_per, endpoint=False)) + list(1 + np.linspace(0, 1, rings_per + 1))
    axis = (c - a) / np.linalg.norm(c - a); up = np.array([0, 1, 0.]) if abs(axis[1]) < 0.9 else np.array([1, 0, 0.])
    u = np.cross(axis, up); u /= np.linalg.norm(u); v = np.cross(u, axis)
    sides = 8; rows = []
    for p, s in zip(pts, ss):
        row = []
        for k in range(sides + 1):
            ang = 2 * math.pi * k / sides; n = math.cos(ang) * u + math.sin(ang) * v
            row.append(part.v(p + r * n, n, (k / sides, s / 2), weights(s)))
        rows.append(row)
    for i in range(len(rows) - 1):
        for k in range(sides):
            a0, a1, b0, b1 = rows[i][k], rows[i][k + 1], rows[i + 1][k], rows[i + 1][k + 1]
            part.T += [(a0, b0, a1), (a1, b0, b1)]


def box(part, centre, size, w, uvmode='face'):
    c = np.array(centre, float); h = np.array(size, float) / 2
    faces = [((1, 0, 0), (0, 0, -1), (0, 1, 0)), ((-1, 0, 0), (0, 0, 1), (0, 1, 0)), ((0, 1, 0), (1, 0, 0), (0, 0, -1)),
             ((0, -1, 0), (1, 0, 0), (0, 0, 1)), ((0, 0, 1), (1, 0, 0), (0, 1, 0)), ((0, 0, -1), (-1, 0, 0), (0, 1, 0))]
    for fi, (n, du, dv) in enumerate(faces):
        n, du, dv = map(np.array, (n, du, dv))
        base = c + n * h
        ids = []
        for (x, y) in [(0, 0), (1, 0), (1, 1), (0, 1)]:
            p = base + du * h * (2 * x - 1) + dv * h * (2 * y - 1)
            uv = (x, 1 - y) if uvmode == 'face' else ((fi + x) / 6, 1 - y)
            ids.append(part.v(p, n, uv, w(p) if callable(w) else w))
        part.T += [(ids[0], ids[1], ids[2]), (ids[0], ids[2], ids[3])]


def quad(part, centre, du, dv, n, w, uv=((0, 1), (1, 1), (1, 0), (0, 0))):
    c = np.array(centre, float); du, dv, n = map(np.array, (du, dv, n))
    ids = [part.v(c - du - dv, n, uv[0], w), part.v(c + du - dv, n, uv[1], w), part.v(c + du + dv, n, uv[2], w), part.v(c - du + dv, n, uv[3], w)]
    part.T += [(ids[0], ids[1], ids[2]), (ids[0], ids[2], ids[3])]


def blend(j0, j1, s0, s1):
    """weights: all j0 before s0, all j1 after s1, snapped to 0.25 steps between"""
    def f(s):
        t = min(1, max(0, (s - s0) / (s1 - s0))); t = round(t * 4) / 4
        return [(j0, 1.0)] if t == 0 else [(j1, 1.0)] if t == 1 else [(j0, 1 - t), (j1, t)]
    return f


# ---- the high model
parts = []
arm = Part('arm', 'checker'); tube(arm, pos('LShoulderJ'), pos('LArmJ'), pos('LHandN'), 0.45, 6, blend('LShoulderJ', 'LArmJ', 0.6, 1.4)); parts.append(arm)
hd = Part('head', 'gradient'); hc = pos('HeadN') + np.array([0, 1.8, 0.2]); box(hd, hc, (3.2, 3.4, 3.0), [('HeadN', 1.0)], 'strip'); parts.append(hd)
for side, sx, name in (('R', -0.7, 'eye_R'), ('L', 0.7, 'eye_L')):
    e = Part('eye' + side, name); quad(e, hc + np.array([sx, 0.3, 1.52]), (0.45, 0, 0), (0, 0.45, 0), (0, 0, 1), [('HeadN', 1.0)]); parts.append(e)
leg = Part('leg', 'lacquer')
lj, kj, fj = pos('LLegJ'), pos('LKneeJ'), pos('LFootJ')
tube(leg, lj, kj, fj, 0.55, 5, blend('LLegJ', 'LKneeJ', 0.7, 1.3)); parts.append(leg)
cape = Part('cape', 'cape')
cp = [pos(n) for n in ('CapeAN', 'CapeBN', 'CapeCN', 'CapeDN')]; cj = ['CapeAN', 'CapeBN', 'CapeCN', 'CapeDN']
rows = []
for i, p in enumerate(cp):
    row = []
    for k, x in enumerate((-1.2, 0, 1.2)):
        w = [(cj[i], 1.0)] if i in (0, 3) else [(cj[i], 0.75), (cj[i - 1], 0.25)]
        row.append(cape.v(p + np.array([x, 0, 0]), np.array([0, 0, -1.]), (k / 2, i / 3), w))
    rows.append(row)
for i in range(3):
    for k in range(2):
        a0, a1, b0, b1 = rows[i][k], rows[i][k + 1], rows[i + 1][k], rows[i + 1][k + 1]
        cape.T += [(a0, a1, b0), (a1, b1, b0)]          # facing -Z (the back)
parts.append(cape)
bd = Part('badge', 'badge'); quad(bd, pos('WaistN') + np.array([0.6, 1.2, 1.25]), (0.5, 0, 0), (0, 0.5, 0), (0, 0, 1), [('WaistN', 1.0)]); parts.append(bd)

MATS = {
    'checker': dict(name='checker', pbrMetallicRoughness=dict(baseColorTexture=dict(index=0), metallicFactor=0, roughnessFactor=0.8)),
    'gradient': dict(name='gradient', pbrMetallicRoughness=dict(baseColorTexture=dict(index=1), metallicFactor=0, roughnessFactor=0.8)),
    'eye_R': dict(name='eye_R', pbrMetallicRoughness=dict(baseColorTexture=dict(index=2), metallicFactor=0, roughnessFactor=0.8)),
    'eye_L': dict(name='eye_L', pbrMetallicRoughness=dict(baseColorTexture=dict(index=3), metallicFactor=0, roughnessFactor=0.8),
                  extras=dict(melee=dict(eye=1, frames=['eyeL_0.png', 'eyeL_1.png', 'eyeL_2.png']))),
    'lacquer': dict(name='lacquer', pbrMetallicRoughness=dict(baseColorTexture=dict(index=0), metallicFactor=1.0, roughnessFactor=0.3),
                    extensions=dict(KHR_materials_specular=dict(specularColorTexture=dict(index=5)))),
    'cape': dict(name='cape', doubleSided=True, pbrMetallicRoughness=dict(baseColorTexture=dict(index=1), metallicFactor=0, roughnessFactor=0.9)),
    'badge': dict(name='badge', alphaMode='MASK', alphaCutoff=0.5, pbrMetallicRoughness=dict(baseColorTexture=dict(index=4), metallicFactor=0, roughnessFactor=0.9)),
}
IMAGES = ['checker.png', 'gradient.png', 'eyeR_0.png', 'eyeL_0.png', 'badge.png', 'specmap.png']


def write(path, parts, extra_joint=True):
    bin_ = bytearray(); views = []; accs = []
    def add(arr, comp, typ, target=None, minmax=False):
        a = np.asarray(arr); raw = a.astype({5126: '<f4', 5123: '<u2', 5125: '<u4'}[comp]).tobytes()
        while len(bin_) % 4: bin_.append(0)
        v = dict(buffer=0, byteOffset=len(bin_), byteLength=len(raw)); bin_.extend(raw)
        if target: v['target'] = target
        views.append(v); acc = dict(bufferView=len(views) - 1, componentType=comp, count=len(a), type=typ)
        if minmax: acc['min'] = a.min(0).tolist(); acc['max'] = a.max(0).tolist()
        accs.append(acc); return len(accs) - 1
    joints = J + ([EXTRA] if extra_joint else [])
    nodes = []
    for i, j in enumerate(joints):
        M = local(j)
        nd = dict(name=j['name'], translation=list(map(float, M[:3, 3])), rotation=quat(M[:3, :3]))
        ch = [k for k, x in enumerate(joints) if x['parent'] == i]
        if ch: nd['children'] = ch
        nodes.append(nd)
    Wj = WORLD + ([EXTRA_W] if extra_joint else [])
    ibm = np.stack([np.linalg.inv(w).T.ravel() for w in Wj])       # column-major
    ibm_acc = add(ibm, 5126, 'MAT4')
    jix = {j['name']: i for i, j in enumerate(joints)}
    used = sorted({m for p in parts for m in [p.mat]}, key=list(MATS).index)
    prims = []
    for p in parts:
        at = dict(POSITION=add(p.P, 5126, 'VEC3', 34962, True), NORMAL=add(p.N, 5126, 'VEC3', 34962), TEXCOORD_0=add(p.UV, 5126, 'VEC2', 34962))
        jj = np.zeros((len(p.W), 4), int); ww = np.zeros((len(p.W), 4))
        for i, w in enumerate(p.W):
            for k, (n, x) in enumerate(w): jj[i, k] = jix[n]; ww[i, k] = x
        at['JOINTS_0'] = add(jj, 5123, 'VEC4', 34962); at['WEIGHTS_0'] = add(ww, 5126, 'VEC4', 34962)
        prims.append(dict(attributes=at, indices=add(np.array(p.T).ravel(), 5125, 'SCALAR', 34963), material=used.index(p.mat)))
    nodes.append(dict(name=os.path.splitext(os.path.basename(path))[0], mesh=0, skin=0))
    g = dict(asset=dict(version='2.0', generator='gltf_testmodel.py'), scene=0, scenes=[dict(nodes=[0, len(nodes) - 1])], nodes=nodes,
             meshes=[dict(name='test', primitives=prims)], skins=[dict(joints=list(range(len(joints))), inverseBindMatrices=ibm_acc, skeleton=0)],
             materials=[MATS[m] for m in used], textures=[dict(source=i, sampler=0) for i in range(len(IMAGES))],
             images=[dict(uri=u) for u in IMAGES], samplers=[dict(wrapS=10497, wrapT=10497)],
             accessors=accs, bufferViews=views)
    stem = os.path.splitext(path)[0]
    g['buffers'] = [dict(uri=os.path.basename(stem) + '.bin', byteLength=len(bin_))]
    if any('KHR_materials_specular' in MATS[m].get('extensions', {}) for m in used): g['extensionsUsed'] = ['KHR_materials_specular']
    open(stem + '.bin', 'wb').write(bin_); json.dump(g, open(path, 'w'), indent=1)
    print(path, sum(len(p.T) for p in parts), 'triangles')


write(os.path.join(OUT, 'test.gltf'), parts)
# the low model: an arm box and a head box on the same checker (single weights; skinned to the rig's joints only)
la = Part('arm_low', 'checker'); box(la, (pos('LShoulderJ') + pos('LHandN')) / 2, (np.linalg.norm(pos('LHandN') - pos('LShoulderJ')), 0.9, 0.9),
                                     lambda p: [('LShoulderJ', 1.0)] if p[0] < pos('LArmJ')[0] else [('LArmJ', 1.0)])
lh = Part('head_low', 'checker'); box(lh, hc, (3.2, 3.4, 3.0), [('HeadN', 1.0)])
write(os.path.join(OUT, 'test_low.gltf'), [la, lh], extra_joint=False)
r2 = dict(rig); r2['model'] = dict(high=os.path.join(os.path.abspath(OUT), 'test.gltf'), low=os.path.join(os.path.abspath(OUT), 'test_low.gltf'),
                                  eyes=[dict(material='eye_R', frames=['eyeR_0.png', 'eyeR_1.png', 'eyeR_2.png'])])
json.dump(r2, open(os.path.join(OUT, 'rig_test.json'), 'w'))
print(os.path.join(OUT, 'rig_test.json'))
