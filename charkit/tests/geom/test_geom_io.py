"""charkit.geom.io: round trips and glTF base-colour sampling (venv: python -m pytest charkit/tests/geom)."""
import io as _io, json, os, struct, sys, tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: F401
from charkit.geom import io as gio, primitives as pr
from charkit.geom.mesh import Mesh


def _tmp(ext):
    fd, p = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    return p


def _colored_sphere():
    s = pr.icosphere(2)
    vc = (s.V * 0.5 + 0.5)
    return s.with_(vc=vc, vn=s.V.copy(), uv=s.V[:, :2] * 0.5 + 0.5)


def test_ply_binary_and_ascii_round_trip():
    m = _colored_sphere()
    for ascii in (False, True):
        p = _tmp('.ply')
        gio.save_ply(m, p, ascii=ascii)
        r = gio.load(p)
        assert r.nf == m.nf and r.nv == m.nv
        assert np.abs(r.V - m.V).max() < 1e-6
        assert np.array_equal(r.F, m.F)
        assert np.abs(r.vc - m.vc).max() <= 0.5 / 255 + 1e-6
        assert np.abs(r.vn - m.vn).max() < 1e-6 and np.abs(r.uv - m.uv).max() < 1e-6
        os.remove(p)


def test_obj_and_npz_round_trip():
    m = _colored_sphere()
    p = _tmp('.obj'); gio.save(m, p); r = gio.load(p)
    assert np.abs(r.V - m.V).max() < 1e-5 and np.array_equal(r.F, m.F)
    q = _tmp('.npz'); gio.save_npz(m, q, meta={'a': 1}, extra=np.arange(3))
    r, meta, ex = gio.load_npz(q, with_meta=True)
    assert meta == {'a': 1} and np.array_equal(ex['extra'], np.arange(3))
    assert np.array_equal(r.V, m.V) and np.array_equal(r.vc, m.vc)
    os.remove(p); os.remove(q)


def test_glb_round_trip_frame_and_colour():
    m = _colored_sphere()
    p = _tmp('.glb')
    gio.save_glb(m, p)                       # z-up in, y-up in the file
    r = gio.load(p)                          # y-up in the file, z-up out
    assert np.abs(r.V - m.V).max() < 1e-6 and np.array_equal(r.F, m.F)
    assert np.abs(r.vc - m.vc).max() < 1e-5
    raw = gio.load(p, z_up=False)
    assert np.abs(raw.V[:, 1] - m.V[:, 2]).max() < 1e-6        # z-up -> y-up: y_file = z
    os.remove(p)


def _textured_quad_glb(path, texels):
    """a GLB: one quad (two triangles) with UVs at the four texel centres of a 2x2 texture."""
    from PIL import Image
    img = Image.fromarray(np.asarray(texels, np.uint8), 'RGB')
    b = _io.BytesIO(); img.save(b, 'PNG'); png = b.getvalue()
    V = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], np.float32)
    UV = np.array([[0.25, 0.25], [0.75, 0.25], [0.75, 0.75], [0.25, 0.75]], np.float32)   # texel centres
    I = np.array([0, 1, 2, 0, 2, 3], np.uint32)
    blobs = [I.tobytes(), V.tobytes(), UV.tobytes(), png]
    views, off = [], 0
    for bl in blobs:
        views.append({'buffer': 0, 'byteOffset': off, 'byteLength': len(bl)})
        off += len(bl) + (-len(bl)) % 4
    data = b''.join(bl + b'\0' * ((-len(bl)) % 4) for bl in blobs)
    J = {'asset': {'version': '2.0'}, 'scene': 0, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0}],
         'meshes': [{'primitives': [{'attributes': {'POSITION': 1, 'TEXCOORD_0': 2}, 'indices': 0, 'material': 0}]}],
         'materials': [{'pbrMetallicRoughness': {'baseColorTexture': {'index': 0}}}],
         'textures': [{'source': 0}], 'images': [{'bufferView': 3, 'mimeType': 'image/png'}],
         'accessors': [{'bufferView': 0, 'componentType': 5125, 'count': 6, 'type': 'SCALAR'},
                       {'bufferView': 1, 'componentType': 5126, 'count': 4, 'type': 'VEC3', 'min': [0, 0, 0], 'max': [1, 1, 0]},
                       {'bufferView': 2, 'componentType': 5126, 'count': 4, 'type': 'VEC2'}],
         'bufferViews': views, 'buffers': [{'byteLength': len(data)}]}
    js = json.dumps(J).encode(); js += b' ' * ((-len(js)) % 4)
    out = struct.pack('<III', 0x46546C67, 2, 28 + len(js) + len(data))
    out += struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(data), 0x004E4942) + data
    open(path, 'wb').write(out)


def test_gltf_base_colour_sampling():
    tex = [[[255, 0, 0], [0, 255, 0]], [[0, 0, 255], [255, 255, 0]]]      # row 0 = top (v = 0)
    p = _tmp('.glb')
    _textured_quad_glb(p, tex)
    for mode in ('nearest', 'bilinear'):
        m = gio.load(p, z_up=False, colors=mode)
        # uv (0.25, 0.25) -> texel row 0 col 0; (0.75, 0.25) -> row 0 col 1; (0.75, 0.75) -> row 1 col 1; (0.25, 0.75) -> row 1 col 0
        want = np.array([tex[0][0], tex[0][1], tex[1][1], tex[1][0]]) / 255.0
        assert np.abs(m.vc - want).max() < 1e-6, mode
    os.remove(p)


def test_real_generated_glb_if_present():
    # a real generated GLB to try (a textured one, as TRELLIS.2 wrote them; since decision 8 none is shipped with the
    # worktrees, so only when named)
    glb = os.environ.get('CHARKIT_GEOM_GLB')
    if not glb or not os.path.exists(glb):
        return
    from charkit import target3d
    m = gio.load(glb, blender_compat=True)
    assert m.nv > 1000 and m.vc is not None
    assert target3d.glb_eyes(glb, m.V, m.vc) is not None


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
