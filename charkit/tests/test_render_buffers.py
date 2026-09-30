"""charkit.render.buffers (the QA's frames drawn by the toon renderer) and charkit.qarender (the QA's drawing switch):
the measuring window against charkit.geom.raster's, and on a toon sphere drawn on whatever adapter the machine has
(skipped without one): the part, hull, tone, depth and normal buffers against the sphere's own geometry and light, the
tone classes against the colour the shader gives, the outline switched off, a painted overlay, the picture's coverage,
the click-to-flag lookup; and the switch's fallback to the numpy drawing.
"""
import math, os, sys, tempfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from charkit.render import buffers, model                  # noqa: E402
from charkit.tests.test_render import _gpu, sphere_glb      # noqa: E402


def test_window_is_rasters():
    """buffers.window's projection lands every point on raster.window_project's pixel (any azimuth, off-centre)."""
    from charkit.geom import raster
    rng = np.random.default_rng(3)
    P = rng.uniform(-0.4, 0.4, (200, 3)) + [0.0, 0.0, 1.2]
    for az in (0.0, 30.0, 90.0, 217.5):
        origin, pix = (0.013, 1.25), 0.25 / 200 / 3
        win = dict(x=0.25, top=0.26, bottom=-0.32)
        cam = buffers.window(az, origin, pix, win)
        W, H = cam.res
        assert (W, H) == raster.window_shape(pix, win)
        ref, dep = raster.window_project(P, az, origin, 1.0, pix, win)
        q = (cam.proj @ cam.view @ np.c_[model.to_gltf(P), np.ones(len(P))].T).T
        ndc = q[:, :3] / q[:, 3:]
        xy = np.stack([(ndc[:, 0] + 1) / 2 * W, (1 - ndc[:, 1]) / 2 * H], 1)
        assert np.allclose(xy, ref, atol=1e-6), np.abs(xy - ref).max()
        assert 0 < ndc[:, 2].min() and ndc[:, 2].max() < 1
        # nearer (raster's smaller depth) is nearer here too
        o = np.argsort(dep)
        assert np.all(np.diff(ndc[o, 2]) >= -1e-9)


def _frames(d, r=0.1, w=0.002):
    p = os.path.join(d, 'ball.glb')
    F = sphere_glb(p, r=r, w=w)
    return buffers.Frames(model.load(p), ss=4), F


def test_sphere_buffers():
    if _gpu() is None:
        return
    r, w = 0.1, 0.002
    with tempfile.TemporaryDirectory() as d:
        Q, _ = _frames(d, r, w)
        pix = 0.002
        cam = buffers.window(0.0, (0.0, 0.0), pix, dict(x=0.16, top=0.16, bottom=-0.16))
        L = np.array([0.9, 0.15, 0.4]); L /= np.linalg.norm(L)                      # world (Blender), toward the key
        F = Q.frame(cam, light=L, aux_ss=2, colour=True)
        n = 160 * 2
        yy, xx = np.mgrid[:n, :n]
        u, z = (xx + 0.5) * pix / 2 - 0.16, 0.16 - (yy + 0.5) * pix / 2               # each sample's window position
        rr = np.hypot(u, z)
        e = pix                                                                       # a sample's reach and then some
        # parts: the sphere inside, its hull as the ring between the moved surface and the original, nothing outside
        assert (F['part'][rr < r - w - e] == 0).all() and not F['hull'][rr < r - w - e].any()
        ring = (rr > r - w + e) & (rr < r - e)
        assert F['hull'][ring].all() and (F['part'][ring] == 0).all()
        assert (F['part'][rr > r + e] == -1).all() and np.isinf(F['depth'][rr > r + e]).all()
        assert Q.object_at(F, 80, 80)['object'] == 'ball' and Q.object_at(F, 1, 1) is None
        # normals and depth on the front (Blender frame: the camera on -y)
        inner = rr < 0.6 * (r - w)
        s = r - w
        Nn = np.stack([u / s, -np.sqrt(np.clip(1 - (u ** 2 + z ** 2) / s ** 2, 0, 1)), z / s], -1)
        cos = (F['normal'][inner] * Nn[inner]).sum(-1)
        assert cos.min() > 0.999, cos.min()                   # (the sphere's smooth normals at its vertices)
        assert np.allclose(F['depth'][inner], 5.0 + Nn[inner][:, 1] * s, atol=2e-4)
        # tones: toon3's two steps on half-lambert N.L (threshold 0.5, deep 0.27, softness 0.015), where not on a step
        h = (Nn @ L) * 0.5 + 0.5
        want = np.where(h > 0.5, 0.0, np.where(h > 0.27, 1.0, 2.0))
        mid = rr < 0.85 * s
        sure = mid & (np.abs(h - 0.5) > 0.03) & (np.abs(h - 0.27) > 0.03)
        got = np.rint(F['tone'][sure])
        assert (got == want[sure]).mean() > 0.999, (got == want[sure]).mean()
        # the tone the colour shows: lit, shade and deep pixels in their colours (the shader's own, one sample a pixel)
        col = F['colour'][..., :3]
        for t, c in ((0, (0.9, 0.5, 0.3)), (1, (0.4, 0.2, 0.1)), (2, (0.2, 0.1, 0.05))):
            m = sure & (want == t)
            assert m.sum() > 50 and np.abs(col[m] - c).max() < 0.01, (t, np.abs(col[m] - c).max())
        assert np.isnan(F['tone'][F['hull']]).all()
        # the picture: coverage 1 inside, 0 outside, straight colour
        p = F['picture']
        yy1, xx1 = np.mgrid[:160, :160]
        r1 = np.hypot((xx1 + 0.5) * pix - 0.16, 0.16 - (yy1 + 0.5) * pix)
        assert (p[r1 < r - 2 * pix, 3] == 1).all() and (p[r1 > r + 2 * pix, 3] == 0).all()
        # the outline off: the surface where it is (radius r), no hull
        G = Q.frame(cam, light=L, off={'ball'}, aux_ss=2, picture=False)
        assert not G['hull'].any() and (G['part'][rr < r - e] == 0).all() and (G['part'][rr > r + e] == -1).all()
        # a painted overlay: the triangles in the upper half flat green, the rest shaded; the part stays the sphere's
        V, T = Q.triangles(0)
        up = V[T].mean(1)[:, 2] > 0.02
        Hh = Q.frame(cam, light=L, paint={0: (up, (0.0, 1.0, 0.0))}, off={'ball'}, aux_ss=2, colour=True, picture=False)
        c = Hh['colour'][..., :3]
        green = (np.abs(c - (0.0, 1.0, 0.0)).max(-1) < 1e-3)
        assert green[inner & (z > 0.03)].all() and not green[inner & (z < 0.01)].any()
        assert (Hh['part'][inner] == 0).all()
        # the same frame twice: the same pixels
        F2 = Q.frame(cam, light=L, aux_ss=2, colour=True)
        assert np.array_equal(F2['part'], F['part']) and np.array_equal(F2['picture'], F['picture'])


def test_qarender_falls_back():
    """the render drawing without an export draws with numpy, and says so."""
    from charkit import qarender

    class B:
        path = tempfile.mkdtemp()

        def __init__(self):
            self._m = {}

        def memo(self, k, fn):
            return self._m.setdefault(k, fn())
    b = B()
    old = os.environ.get(qarender.ENV)
    os.environ[qarender.ENV] = 'render'
    try:
        assert qarender.setting() == 'render' and qarender.frames(b) is None
        assert qarender.view(b, [], 0.0, None) is None
        assert any(k.startswith('numpy (no export') for k in qarender.drawn(b)), qarender.drawn(b)
        assert qarender.cache_key() and qarender.cache_key()[0]['qa_draw'] == 'render'
        os.environ[qarender.ENV] = 'numpy'
        assert qarender.setting() == 'numpy' and qarender.cache_key() == []
    finally:
        if old is None:
            os.environ.pop(qarender.ENV, None)
        else:
            os.environ[qarender.ENV] = old


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
