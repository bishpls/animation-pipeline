"""The QA's drawing by charkit's toon renderer (docs/workstreams/toonrender.md, phase 2): what charkit.qa3d.draw_view /
draw_lit / draw_ids draw with their own numpy rasteriser, drawn instead by charkit.render from the build's export (the
boards' passes and shader), so the QA measures the look the boards show.

The setting: charkit.qa3d.DRAW ('numpy' | 'render'), overridden by the environment's CHARKIT_QA_DRAW. The render drawing
needs the build's export beside its bundle (OUT/NAME.look.glb or OUT/NAME.vrm; every build writes one) and wgpu; without either, or for a
surface the export doesn't hold (a bundle made in memory by an evaluator), the numpy drawing draws, and qa.json's
`measured.draw` says which one measured. The skin's 'bare' variant (its garment mask off: the look QA's bare head) draws
from the export's bare skin (gltf.export look_only writes it: a mesh no scene node draws, Prim.variant 'bare'); an export
without one draws it with numpy.

    from charkit import qarender
    Q = qarender.frames(B)                        # charkit.render.buffers.Frames over B's export, or None
    v = qarender.view(B, surfs, az, fr)           # a View standing in for draw_view's dict, or None (draw with numpy)
    px = v.lit(ldir, transparent, ss, aux)        # draw_lit's picture and buffers

What a qa3d surface list says, as the renderer draws it: each surface's object (the export's primitives of that name);
a surface made with outline=False (qa3d.surfaces: the surface where it is, no hull) draws its object with the outline off;
a hull draws its object's outline; a surface lookqa scaled to another line width (`line_k`: that width over the build's)
sets the frame's screen-line width (every object's, times its region's factor, as the boards' screen lines are); `paint`
(per triangle of the bundle's mesh) is carried onto the export's triangles by nearest centre.
"""
import os

import numpy as np

ENV = 'CHARKIT_QA_DRAW'


def setting():
    """the QA's drawing: CHARKIT_QA_DRAW, else charkit.qa3d.DRAW."""
    from . import qa3d
    v = (os.environ.get(ENV) or qa3d.DRAW or 'numpy').strip().lower()
    return v if v in ('numpy', 'render') else 'numpy'


def cache_key():
    """what a QA part's cache key adds for the drawing (charkit.cache.qa_part): nothing with the numpy drawing (its keys
    as before), else the renderer's package and adapter choice (the export itself is a file the part read)."""
    if setting() != 'render':
        return []
    try:
        import importlib.metadata as md
        v = md.version('wgpu')
    except Exception:
        v = None
    return [{'qa_draw': 'render', 'wgpu': v, 'adapter': os.environ.get('CHARKIT_RENDER_ADAPTER') or 'auto'}]


def export_of(B):
    """the build's export beside its bundle (OUT/NAME.look.glb, else OUT/NAME.vrm) -> path or None."""
    p = getattr(B, 'path', None)
    if not p:
        return None
    from .render.buildboards import export_of as found
    return found(os.path.dirname(os.path.abspath(p.rstrip('/'))))


def frames(B, why=None):
    """charkit.render.buffers.Frames over B's export when the setting is 'render' and it can draw -> Frames or None
    (why, a list, gets the reason). The export is recorded as a file the QA read (its cache key follows its content)."""
    if setting() != 'render':
        return None
    path = export_of(B)
    if path is None:
        if why is not None:
            why.append('no export beside the bundle')
        return None
    try:
        from .render import buffers
        Q = buffers.load(path, adapter=os.environ.get('CHARKIT_RENDER_ADAPTER'))
    except Exception as e:                              # (no wgpu, no adapter: the numpy drawing measures)
        if why is not None:
            why.append('%s: %s' % (type(e).__name__, e))
        return None
    for r in getattr(B, '_reads', ()):
        r.files.add(os.path.abspath(path))
    return Q


def adapter_of(B):
    """the wgpu adapter B's render drawing drew on in this process (charkit.render.gpu.adapter_info: device, backend,
    type 'CPU' for llvmpipe/lavapipe, 'DiscreteGPU' for the render box's L4), without loading anything -> dict or None
    (nothing drawn by the renderer yet). The QA's readings depend on it at the rasteriser's ties: qa.json records it
    (measured.draw.adapter) and the gate reports both builds'."""
    path = export_of(B)
    if path is None:
        return None
    from .render import buffers
    for k, F in list(buffers._CACHE.items()):
        if k[0] == os.path.abspath(path):
            info = dict(getattr(F, 'info', None) or {})
            return info or None
    return None


def note(B, what):
    """record which drawing measured (qa.json's measured.draw)."""
    got = B.memo('qarender.drawn', lambda: {})
    got[what] = got.get(what, 0) + 1


def drawn(B):
    """{drawing: frames drawn} this bundle's QA drew so far."""
    return dict(B.memo('qarender.drawn', lambda: {}))


class View:
    """one view of a qa3d surface list drawn by the renderer: draw_view's dict where the QA reads it (['mesh'],
    ['depth'], ['az']), draw_lit's picture and buffers by lit(), the mesh index per pixel by ids()."""

    def __init__(self, B, Q, surfs, az, fr, draw, off, paint, line, index, variants=None):
        self.B, self.Q, self.surfs, self.az, self.fr = B, Q, surfs, az, fr
        self.draw, self.off, self.paint, self.line = draw, off, paint, line
        self.variants = variants or {}                      # {object: variant}: the skin 'bare'
        self.index = index                                  # (part, hull) -> the surface's index in surfs
        self._aux = {}

    def camera(self, k=1):
        """the frame's window (charkit.render.buffers.window) with pixels k x the frame's (the frame is the measuring
        grid; a picture's pixel is ss of them)."""
        from .render import buffers
        fr = self.fr
        W = int(round(2 * fr.win['x'] / fr.pix))
        H = int(round((fr.win['top'] - fr.win['bottom']) / fr.pix))
        Wk, Hk = -(-W // k), -(-H // k)
        pix = fr.pix * k
        win = dict(x=Wk * pix / 2, top=fr.win['top'], bottom=fr.win['top'] - Hk * pix)
        origin = (fr.origin[0] - fr.win['x'] + Wk * pix / 2, fr.origin[1])
        return buffers.window(self.az, origin, pix, win)

    def _frame(self, ldir, **kw):
        key = (None if ldir is None else tuple(np.round(np.asarray(ldir, float), 12)),
               tuple(sorted(kw.items())))
        if key not in self._aux:
            if len(self._aux) > 4:
                self._aux.pop(next(iter(self._aux)))
            self._aux[key] = self.Q.frame(self.camera(1), draw=self.draw, off=self.off, paint=self.paint,
                                          light=ldir if ldir is not None else light(self.B, self.az), line=self.line,
                                          variants=self.variants, **kw)
            note(self.B, 'render')
        return self._aux[key]

    def mesh_of(self, F):
        """a frame's parts and hulls -> the surface index per pixel (-1 none)."""
        idx = np.full((len(self.Q.prims) + 1, 2), -1, np.int64)
        for (k, h), i in self.index.items():
            idx[k, int(h)] = i
        p = F['part']
        return np.where(p >= 0, idx[np.maximum(p, 0), F['hull'].astype(int)], -1)

    def ids(self):
        """the surface index per pixel of the measuring grid (draw_view's 'mesh')."""
        return self.mesh_of(self._frame(None, picture=False))

    def __getitem__(self, k):
        if k == 'mesh':
            return self.ids()
        if k == 'depth':
            return self._frame(None, picture=False)['depth']
        if k == 'az':
            return self.az
        raise KeyError(k)

    def lit(self, ldir=None, transparent=True, ss=3, aux=None, only=None, picture=True):
        """draw_lit on the renderer: the picture over ss x ss of the frame's pixels (EEVEE's film filter over the
        renderer's own supersamples), aux's buffers ('tone', 'mesh', 'depth', 'normal') on the frame's grid. only: the
        tone kept on those surfaces alone (the rest NaN)."""
        from . import qa3d
        px = None
        if picture:
            cam = self.camera(ss)
            px = self.Q.frame(cam, draw=self.draw, off=self.off, paint=self.paint,
                              light=ldir if ldir is not None else light(self.B, self.az), line=self.line,
                              transparent=transparent, aux=False, world=qa3d.WORLD, variants=self.variants)['picture']
            note(self.B, 'render')
        if aux is not None:
            F = self._frame(ldir, picture=False)
            mesh = self.mesh_of(F)
            tone = F['tone']
            if only is not None:
                tone = np.where(np.isin(mesh, list(only)), tone, np.nan)
            aux.update(tone=tone, mesh=mesh, depth=F['depth'], normal=F['normal'])
        return px


def light(B, az):
    """the boards' light for a view (charkit.qa3d.view_light on the bundle's look), else the export's."""
    from . import qa3d
    ld = qa3d.view_light(B, az)
    return None if ld is None else np.asarray(ld, float)


def view(B, surfs, az, fr, Q=None):
    """a qa3d surface list as the renderer draws it -> View, or None (the numpy drawing draws: the setting, no export,
    or a surface the export doesn't hold). Q: the Frames to draw with (default frames(B): the build's export; lookqa's
    design light passes one whose cast shadows are rebaked at its elevation)."""
    if setting() != 'render':
        note(B, 'numpy')
        return None
    why = []
    Q = Q if Q is not None else frames(B, why)
    if Q is None:
        note(B, 'numpy (%s)' % (why[0] if why else 'no renderer'))
        return None
    by_name = {}
    for k, name in enumerate(Q.objects):
        by_name.setdefault((name, Q.prims[k].variant), []).append(k)
    draw, off, index, paint, variants = set(), set(), {}, {}, {}
    widths = []
    from .qa3d import is_ink
    names = [m.get('name') for m in (Q.M.js.get('materials') or [])] if getattr(Q, 'M', None) is not None else []
    prim_ink = lambda k: 0 <= Q.prims[k].material < len(names) and is_ink(names[Q.prims[k].material])
    for i, s in enumerate(surfs):
        o = s['o']
        var = s['variant'] if o.group == 'skin' and s['variant'] != 'masked' else None
        if (o.name, var) not in by_name or var not in (None, 'bare'):
            note(B, 'numpy (%s not in the export as drawn)' % (o.name if var is None else '%s %s' % (o.name, var)))
            return None
        draw.add(o.name)
        if var:
            variants[o.name] = var
        ks = by_name[(o.name, var)]
        if s['hull'] and len(s['slots']) and all(is_ink(o.materials[int(t)]) for t in np.unique(s['slots'])):
            # a piece's creases (qa3d.render_surfaces' ink surface: lines, as a hull is): the renderer draws its ink
            # primitives as surface pixels, so they map to this surface, not the cloth's
            for k in ks:
                if prim_ink(k):
                    index[(k, False)] = i
            continue
        for k in ks:
            index.setdefault((k, bool(s['hull'])), i)
        if s.get('line_k') is not None and o.outline and not s['hull']:
            widths.append((o, float(s['line_k'])))
        if s.get('paint') is not None and not s['hull']:
            paint.update(carry_paint(B, Q, o, s, ks))
    hulled = {s['o'].name for s in surfs if s['hull']}
    off = {s['o'].name for s in surfs if s['o'].outline and s['o'].name not in hulled}   # (qa3d.surfaces(outline=False))
    line = 0.0
    if widths:
        line = screen_line(Q, widths)
        if line is None:
            note(B, 'numpy (line widths not one screen width)')
            return None
    return View(B, Q, surfs, az, fr, draw, off, paint, line, index, variants)


def screen_line(Q, widths):
    """the screen-line width (m, before the regions' factors) that gives each (object, k) its build width x k, or None
    when they don't agree (to 0.1%)."""
    look = Q.M.root.get('lines') or {}
    regions = look.get('regions') or {}
    got = []
    for o, k in widths:
        P = next((p for p in Q.prims if p.object == o.name and p.outline), None)
        if P is None:
            continue
        w = abs(float(o.outline.get('thickness') or P.outline['width'])) * k
        got.append(w / regions.get(P.outline.get('region', 'skin'), 1.0))
    if not got:
        return 0.0
    if max(got) - min(got) > 1e-3 * max(got):
        return None
    return float(np.mean(got))


def carry_paint(B, Q, o, s, prims):
    """a surface's paint (per triangle of the bundle's mesh: linear RGB, NaN unpainted) onto the export's triangles of
    that object by nearest centre (the export's mesh is Blender's render level: each of its triangles lies in one of the
    bundle's) -> {primitive: (triangle mask, rgb)} (one colour: the first painted)."""
    from scipy.spatial import cKDTree
    p = np.asarray(s['paint'], float)
    ok = np.isfinite(p[:, 0])
    if not ok.any():
        return {}
    V, T = np.asarray(s['V'], float), np.asarray(s['T'])
    tree = cKDTree(V[T].mean(1))
    rgb = p[ok][0]
    out = {}
    for k in prims:
        Vk, Tk = Q.triangles(k)
        if not len(Tk):
            continue
        _, j = tree.query(Vk[Tk].mean(1))
        m = ok[j] & np.all(np.abs(p[j] - rgb) < 1e-9, 1)
        if m.any():
            out[k] = (m, rgb)
    return out
