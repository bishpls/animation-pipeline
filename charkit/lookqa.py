"""The look's measures (charkit.shade, faceshade; docs/workstreams/look.md): how clean the skin's shading is, where its
shadows fall against the design's, and how even the outlines are. Venv-side on a build's bundle (charkit.qa3d draws it
as the boards light it: the style's look, a camera key turned with each view), the design's head and body sheets read
as the QA reads them (charkit.refcheck at FACE_PPL).

  face_noise     the head and neck skin's tone edges per skin pixel (as hair_noise counts the hair's): its toon and SDF
                 tones (0 lit, 1 shade, 2 deep) from 0, 30 and 90 degrees under each view's board light; clean anime
                 shading is one or two shadow shapes, geometry-following bands many. `sweep`: the same under four fixed
                 lights round each view (35 and 70 degrees either side, 35 up), so a light the boards don't use still
                 shows the face's banding. `islands`: the tone regions over 0.002 L^2 per view
  face_shadow    the skin's shadow against the design's (head_turnaround's skin split into its lit and shaded tones:
                 skin_classes) per view at the design's scale, aligned by the eyes, over the skin both show: the shadow's
                 share of the face (above our chin) and of the neck (the chin to 0.5 L under it), ours and drawn, and the
                 shadows' IoU. The three-quarter is the headline view (the design shades it most). `chin` (graded):
                 the shadow under the chin in the front and three-quarter views, over the neck window: its IoU with
                 the design's, and how far under the chin it reaches per column against the design's (the V drawn as
                 a profile: `chin_edge`, L). Both INFO with a proposed grade beside: not calibrated (the design's own
                 shadow moved a pixel or two reads WARN; round 1's band reads as the cast does)
  line_width     the outlines' drawn widths in the design's framing (a head sheet 1440 px tall at the design's px per L:
                 the style's 'screen' lines at that page, or each object's build width), from 0, 30 and 90 degrees: the
                 hull's pixels' widths (twice the distance to the line's edge, along its skeleton) per region (skin,
                 hair, garment, accessory), their median in px of the design's page and their spread (p90 / p10); the
                 design's lines (its pixels darker than half way from ink to paper, v < 0.5, inside its head boxes)
                 measured the same way. line_ink: the lines' colour per region (the median of their supersampled
                 pixels, before the pixel filter) against the design's ink (its line cores' median), CIEDE2000

Cost (docs/workstreams/look.md, round 2): each view is rasterized once (charkit.qa3d.draw_view) and shaded under each
light (draw_lit: the sweep's lights shade the skin alone, with no picture); face_shadow shares face_noise's board views
(board_tones); line_width prepares and shades the lines alone, at the design's scale (its widths step with the
resolution: a 2 px line at 200 px per L x 3 is three sub-pixels across).

    table, checks = lookqa.measure(B, design, out)      # charkit.qa3d's 'look' part
"""
import json, os

import numpy as np

FACE_PPL = 200                   # the QA's face scale (charkit.refcheck.FACE_PPL): px per L
WIN = (1.0, 1.05, 1.3)           # the head window round the eye line, in L: half-width, above, below
VIEWS = (0, 30, 90)
SWEEP = ((-70, 35), (-35, 35), (35, 35), (70, 35))     # (degrees to the camera's left, up) for the sweep's lights
ISLAND = 0.002                   # L^2: the smallest tone region counted
LINE_V = 0.38                    # the design's line pixels (charkit.sheetqa.LINE_V)
LINE_W_V = 0.5                   # ... for their width: half way from the ink (v ~0.15) to the paper and skin (~0.85)
REGIONS = ('skin', 'hair', 'garment', 'accessory')


class HeadFrame:
    """an orthographic window round the head at ppl px per L (supersampled ss), for charkit.qa3d.draw; off shifts the
    frame's origin by that many output pixels (x right, y down: the measures' sampling spread at sub-pixel offsets)."""

    def __init__(self, B, ppl=FACE_PPL, ss=3, win=WIN, off=(0.0, 0.0)):
        A = B.assembly
        L = float(A['L'])
        self.L, self.ppl, self.ss = L, ppl, ss
        self.eye_z = float(A['eye_z'])
        self.pix = L / ppl / ss
        self.win = dict(x=win[0] * L, top=win[1] * L, bottom=-win[2] * L)
        self.off = (float(off[0]), float(off[1]))
        self.origin = (-self.off[0] * L / ppl, self.eye_z + self.off[1] * L / ppl)
        self.key = (float(ppl), int(ss), tuple(float(w) for w in win), self.off)

    def zbuffer(self, items, az, ids=False):
        from .geom import raster
        return raster.window_zbuffer(items, az, self.origin, 1.0, self.pix, self.win, ids=ids)

    def project(self, P, az):
        """world points -> (column, row) at the frame's own resolution (not supersampled)."""
        from .geom import raster
        P2, _ = raster.window_project(np.atleast_2d(P), az, self.origin, 1.0, self.pix, self.win)
        return P2 / self.ss

    def row(self, z):
        return (self.win['top'] - (z - self.origin[1])) / (self.pix * self.ss)


def key_light(az, a0, el):
    """toward a light a0 degrees to the left of a camera at azimuth az and el up (world)."""
    a0, el, a = np.radians(a0), np.radians(el), np.radians(az)
    d = np.array([-np.sin(a0) * np.cos(el), -np.cos(a0) * np.cos(el), np.sin(el)])
    R = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1.0]])
    return R @ d


def _scene(B, skin_outline=False, line_scale=None, bare=False):
    """the skin (its outline off unless asked: its own line is not shading) first, then every other visible object as it
    renders; line_scale {object name: k} draws an object's outline k times its build width. bare: the garments left
    out and the skin unmasked under them (the bundle's 'bare' variant, when it has one), as head_turnaround draws the
    head: its neck and shoulders bare."""
    from . import qa3d
    sk = B.skin()
    bare = bare and sk.has('bare')
    var = 'bare' if bare else 'masked'
    surfs = _scaled(B, sk, var, line_scale) if skin_outline else qa3d.surfaces(B, sk, var, outline=False)
    for o in B.objects():
        if o.group != 'skin' and o.has('eval') and not (bare and o.group == 'garment'):
            surfs += _scaled(B, o, 'eval', line_scale)
    return surfs


def _scaled(B, o, variant, line_scale):
    """an object's surfaces with its outline k x its build width (line_scale): the surface moved inward by
    inward(k w0) and the hull the rest of the width outward (charkit.shade.line_inward: a thin shell's cap), from the
    build's shrink (inward(w0) along the hull direction)."""
    from . import qa3d
    S = qa3d.surfaces(B, o, variant)
    k = (line_scale or {}).get(o.name)
    sh = o.a(variant, 'shrink')
    if k is not None and sh is not None and not S[0]['hull']:
        w0 = abs(float(o.outline.get('thickness') or 0.0))
        off = float(o.outline.get('offset', 1.0))
        c0 = w0 * (1 + off) / 2                                  # the build width's inward move
        cap = o.outline.get('cap')
        if cap is None and c0 < w0 - 1e-9:                      # capped at the build width (a bundle without 'cap')
            cap = c0
        c1 = min(k * w0, cap) if cap else k * w0
        V = o.a(variant, 'V')
        # (line_k: the render drawing's width; the renderer applies the cap itself, toon.wgsl's inward())
        if c0 > 0:
            S[0] = dict(S[0], V=V + sh * (c1 / c0), line_k=k)
            for i in range(1, len(S)):
                if S[i]['hull']:
                    S[i] = dict(S[i], V=V - sh * ((k * w0 - c1) / c0))
        else:
            S[0] = dict(S[0], V=V + sh * k, line_k=k)
    return S


def _edges(q, m):
    """tone changes between 4-neighbours both in m, per pixel of m."""
    e = (q[:, 1:] != q[:, :-1]) & m[:, 1:] & m[:, :-1]
    e2 = (q[1:] != q[:-1]) & m[1:] & m[:-1]
    return (e.sum() + e2.sum()) / max(1, m.sum())


def _islands(q, m, min_px):
    from scipy import ndimage
    n = 0
    for v in np.unique(q[m]):
        lab, k = ndimage.label(m & (q == v))
        if k:
            n += int((np.bincount(lab.ravel())[1:] >= min_px).sum())
    return n


def skin_tones(B, fr, az, ldir=None, surfs=None):
    """the visible head and neck skin's tones (0 lit, 1 shade, 2 deep) at the frame's supersampled resolution, the
    skin mask, and the drawn picture."""
    from . import qa3d
    surfs = surfs if surfs is not None else _scene(B)
    return _tones(B, qa3d.draw_view(B, surfs, az, fr), fr, ldir)


def _tones(B, view, fr, ldir=None, picture=True, soft=False):
    """skin_tones from a view of _scene (charkit.qa3d.draw_view): picture=False shades the skin alone (surface 0) and
    draws no picture (-> q, m, None); soft adds the pixels between tone steps (-> q, m, px, soft)."""
    from . import qa3d
    aux = {}
    px = qa3d.draw_lit(B, view, ldir, ss=fr.ss, aux=aux, only=None if picture else (0,), picture=picture)
    m = (aux['mesh'] == 0) & np.isfinite(aux['tone'])
    t = np.nan_to_num(aux['tone'])
    q = np.where(m, np.rint(t), -1).astype(int)
    if soft:                                                    # the tone steps' soft pixels, and the depth (the jaw)
        return q, m, px, m & (np.abs(t - np.rint(t)) > 0.1), aux['depth']
    return q, m, px


def board_tones(B, fr, az, view=None):
    """skin_tones under the boards' light, once per bundle, frame and azimuth (face_noise and face_shadow share it),
    its soft pixels (a tone between steps: a ramp's width on the skin, 0.1 .. 0.9 of a step) and the depth -> (q, m, px,
    soft, depth); view: the azimuth's draw_view when the caller has one."""
    from . import qa3d

    return B.memo(('lookqa.board_tones', fr.key, float(az)),
                  lambda: _tones(B, view if view is not None else qa3d.draw_view(B, _scene(B, bare=True), az, fr), fr,
                                 soft=True))


def design_noise(D, chin):
    """the design's own tone edges per skin pixel (skin_classes' lit and shaded skin) in each head, over the face and the
    neck to 0.5 L under the chin (chin: ours, L under the eye line), and its tone regions over ISLAND."""
    out = {}
    for view, h in D['heads'].items():
        if view == 'back' or not h['eyes']:
            continue
        x0, y0, x1, y1 = h['box']
        ey = float(np.mean([e[1] for e in h['eyes']]))
        y1 = min(y1, int(ey + (chin + 0.5) * FACE_PPL))
        lab = D['lab'][y0:y1, x0:x1]
        m = (lab == 1) | (lab == 5)
        q = (lab == 5).astype(int)
        out[view] = dict(edges=round(float(_edges(q, m)), 4), islands=_islands(q, m, ISLAND * FACE_PPL ** 2))
    return out


def face_noise(B, out=None, design=None, fr=None):
    """-> (table, checks face_noise, face_noise_sweep, face_islands): see the module. Each view is rasterized once
    (charkit.qa3d.draw_view) and shaded under the board light and the sweep's four (the skin alone, no picture)."""
    from . import qa3d
    fr = fr or HeadFrame(B)
    surfs = _scene(B, bare=True)
    ss = fr.ss
    min_px = ISLAND * (fr.ppl * ss) ** 2
    chin_L = float(B.assembly['chin']) / fr.L
    chin_row = fr.row(fr.eye_z - float(B.assembly['chin'])) * ss
    per, sweep, isl, pics = {}, {}, {}, []
    for az in VIEWS:
        view = qa3d.draw_view(B, surfs, az, fr)
        q, m, px = board_tones(B, fr, az, view)[:3]
        rows = np.arange(q.shape[0])[:, None]
        m = m & (rows < chin_row + 0.5 * fr.ppl * ss)              # the face and the neck (as design_noise's)
        if m.sum() < 100:
            continue
        per[az] = dict(all=round(float(_edges(q, m) * ss), 4), face=round(float(_edges(q, m & (rows < chin_row)) * ss), 4),
                       neck=round(float(_edges(q, m & (rows >= chin_row)) * ss), 4),
                       shade_share=round(float((q[m] >= 1).mean()), 4))
        isl[az] = _islands(q, m, min_px)
        if out:
            pics += [qa_px(px), _tone_pic(q, m, ss)]
        sw = []
        for a0, el in SWEEP:
            q2, m2, _ = _tones(B, view, fr, key_light(az, a0, el), picture=False)
            sw.append(_edges(q2, m2) * ss)
            if out and az == 30:
                pics.append(_tone_pic(q2, m2, ss))
        sweep[az] = round(float(np.mean(sw)), 4)
        del view
    if not per:
        return None, {'face_noise': {'status': 'SKIPPED', 'why': 'no visible skin in the head window'}}
    v = float(np.mean([p['all'] for p in per.values()]))
    vs = float(np.mean(list(sweep.values())))
    C = {'face_noise': {'value': round(v, 4), 'per_view': {k: p['all'] for k, p in per.items()}, 'status': 'INFO'},
         'face_noise_sweep': {'value': round(vs, 4), 'per_view': sweep, 'status': 'INFO'},
         'face_islands': {'value': int(max(isl.values())), 'per_view': isl, 'status': 'INFO'}}
    D = design_heads(design) if design is not None else None
    dn = design_noise(D, chin_L) if D else None
    if dn:
        C['face_noise']['design'] = round(float(np.mean([d['edges'] for d in dn.values()])), 4)
        C['face_noise']['design_per_view'] = {v: d['edges'] for v, d in dn.items()}
        C['face_islands']['design'] = int(max(d['islands'] for d in dn.values()))
    if out and pics:
        _save_row(os.path.join(out, 'qa_face_shading.png'), pics)
    return dict(views=per, sweep=sweep, islands=isl, design=dn), C


def _tone_pic(q, m, ss):
    """a tone map (lit, shade, deep; grey off the skin) at the output resolution."""
    pal = np.array([[0.98, 0.93, 0.88], [0.86, 0.60, 0.58], [0.55, 0.32, 0.36], [0.80, 0.80, 0.82]])
    img = pal[np.where(m, np.clip(q, 0, 2), 3)]
    return img[ss // 2::ss, ss // 2::ss]


def _save_row(path, pics, gap=6):
    from . import qa3d
    h = max(p.shape[0] for p in pics)
    row = [np.pad(p[..., :3], ((0, h - p.shape[0]), (0, gap), (0, 0)), constant_values=1.0) for p in pics]
    qa3d._save_rgb(path, np.concatenate(row, 1))


# ------------------------------------------------------------------------------------------------------ the design
def skin_classes(rgb):
    """a drawing's skin split into its lit and shaded tones: -> labels (0 other, 1 lit skin, 5 shaded skin, 4 line).
    Skin is the sheet's skin hues (charkit.sheetqa.SKIN's, its shade allowed down to v 0.55); lit from shaded at the
    luminance threshold between the two (Otsu), when there are two."""
    from .i3d import hsv
    from . import sheetqa
    H, W, _ = rgb.shape
    h, s_, v = (a.reshape(H, W) for a in hsv(rgb.reshape(-1, 3)))
    skin = (h >= sheetqa.SKIN['h'][0]) & (h <= sheetqa.SKIN['h'][1]) & (s_ >= 0.08) & (s_ <= 0.5) & (v >= 0.55)
    lum = rgb @ np.array([0.3, 0.59, 0.11])
    lab = np.zeros((H, W), int)
    lab[skin] = 1
    if skin.sum() > 100:
        x = lum[skin]
        hist, e = np.histogram(x, bins=64)
        c = (e[:-1] + e[1:]) / 2
        w0 = np.cumsum(hist); w1 = w0[-1] - w0
        m0 = np.cumsum(hist * c) / np.maximum(w0, 1); m1 = (np.sum(hist * c) - np.cumsum(hist * c)) / np.maximum(w1, 1)
        k = int(np.argmax(w0 * w1 * (m0 - m1) ** 2))
        if abs(m1[k] - m0[k]) > 0.08:
            lab[skin & (lum < e[k + 1])] = 5
    lab[v < LINE_V] = 4
    return lab


def design_cut(rgb, ex, facing):
    """design_heads' measurement of the sheet's pixels (memoized on its code and arguments)."""
    from . import refcheck
    rgb0, _ = refcheck.without_guides(np.asarray(rgb, float))
    rgb1, f, H = refcheck.at_scale(rgb0, ex, 2 * ex * FACE_PPL, facing)
    heads = {v: dict(box=[int(x) for x in h['box']], eyes=[list(map(float, e)) for e in h['eyes']])
             for v, h in H['heads'].items()}
    fe, te = (heads.get(v, {}).get('eyes') or [] for v in ('front', 'three_quarter'))
    az3 = float(np.degrees(np.arccos(np.clip(abs(te[1][0] - te[0][0]) / abs(fe[1][0] - fe[0][0]), 0, 1)))) \
        if len(fe) == 2 and len(te) == 2 else 35.0
    dark = rgb0.max(-1) < LINE_W_V
    lines0 = np.zeros(dark.shape, bool)
    for h in heads.values():
        x0, y0, x1, y1 = (int(round(b / f)) for b in h['box'])
        lines0[y0:y1, x0:x1] = dark[y0:y1, x0:x1]
    core = lines0 & (rgb0.max(-1) < 0.3)
    ink = np.median(rgb0[core], 0) if core.sum() > 50 else None
    return dict(rgb=rgb1, lab=skin_classes(rgb1), heads=heads, native_ppl=FACE_PPL / f, native_h=rgb0.shape[0],
                lines0=lines0, az3=round(az3, 1), ink=ink)


def design_heads(design):
    """the design's head sheet at FACE_PPL (charkit.refcheck.at_scale): dict(rgb, lab (skin_classes), heads {view:
    dict(box, eyes)}, native_ppl, native_h, lines0 (its line pixels inside the head boxes at its own resolution), az3)
    or None."""
    fs = design.ref().get('face_sheet')
    if not fs:
        return None
    return design.memo(design_cut, design.rgba(fs['image'])[..., :3], design.B.assembly['eye_knobs']['x'],
                       fs.get('facing', -1))


def _ours_eyes(B, fr, az):
    from . import qa3d
    return fr.project(np.array([c for c in qa3d.iris_centres(B)]), az)


def design_light(design):
    """the reference light the design's drawn shading implies: the manifest's design_light (charkit.designlight's fit;
    docs/workstreams/look.md round 6) -> dict(mode 'camera', key [deg left of the camera, deg up], ...) or None. A
    reference for the QA only: the boards' light is the style's look.light (Michael's call A)."""
    if design is None:
        return None
    r = design.ref()
    DL = r.get('design_light')
    if DL is None and r.get('manifest'):
        from . import manifest, qa3d
        try:
            DL = manifest.load(r['manifest']).get('design_light')
            design._rec(qa3d._path(r['manifest']))
        except (OSError, ValueError, KeyError):
            DL = None
    return DL if isinstance(DL, dict) and DL.get('mode') == 'camera' and DL.get('key') else None


_LIGHT_FRAMES = {}


def light_frames(B, el, cast=None):
    """charkit.render's Frames over the build's export with its cast shadows rebaked at elevation el (the bake keys on
    the light's elevation: charkit.designlight.rebake, bit-identical to the build's own at its elevation, carried onto
    the export's skin) -> Frames, or None (the numpy drawing: it keeps the build's bake). cast: the look's face.cast
    overridden (a lab's options: px, soft, smooth, face, lift, bias; 'hair': the occluders' names)."""
    from . import qarender
    Q = qarender.frames(B)
    look = B.meta('look') or {}
    el0 = float(((look.get('light') or {}).get('key') or (39.3, 44.6))[1])
    if Q is None or not (look.get('face') or {}).get('cast') or (abs(el - el0) < 1e-6 and not cast):
        return Q
    path = qarender.export_of(B)
    key = (os.path.abspath(path), os.path.getmtime(path), round(float(el), 6), json.dumps(cast, sort_keys=True))
    if key not in _LIGHT_FRAMES:
        from . import designlight
        from .render import buffers, model
        M = model.load(path)
        c = dict(cast or {})
        hair = c.pop('hair', None)
        for k, v in designlight.carry(B, M, designlight.rebake(B, el, c, hair)).items():
            M.prims[k].cast = np.ascontiguousarray(v, np.float32)
        _LIGHT_FRAMES.clear()
        _LIGHT_FRAMES[key] = buffers.Frames(M, adapter=os.environ.get('CHARKIT_RENDER_ADAPTER'))
    return _LIGHT_FRAMES[key]


def light_tones(B, fr, az, key, cast=None):
    """board_tones under a camera key (a0 deg left of the camera, el up: the design light), the cast rebaked at el
    (light_frames; cast: its options overridden) -> (q, m, px, soft, depth)."""
    from . import qa3d, qarender

    def make():
        surfs = _scene(B, bare=True)
        Q = light_frames(B, float(key[1]), cast)
        view = qarender.view(B, surfs, az, fr, Q=Q) if Q is not None else None
        if view is None:
            view = qa3d.draw_view(B, surfs, az, fr)
        return _tones(B, view, fr, ldir=key_light(az, *key), soft=True)
    return B.memo(('lookqa.light_tones', fr.key, float(az), tuple(float(x) for x in key),
                   json.dumps(cast, sort_keys=True)), make)


def face_shadow(B, design, out=None, fr=None):
    """-> (table, checks): see the module. Under the design light (the manifest's design_light: the light the drawing's
    shading implies) when the design has one, the boards' light's values beside ('board'); else under the boards'.
      face_shadow_3q                the three-quarter's shadow IoU with the design's (eye-aligned; front and profile in
                                    per_view)
      face_shadow_face_3q / _neck_3q  the share of the face (above our chin) and the neck in shadow, ours less the
                                    design's (per_view: every view's)
      face_shadow_chin, _chin_edge  the shadow under the chin on the jaw (chin_on_jaw): its IoU with the design's in jaw
                                    coordinates, and its lower edge's distance from the design's (L); calibrated (CHIN_CAL)
      face_shadow_chin_soft         the tone steps' soft width on the neck (INFO)"""
    D = design_heads(design) if design is not None else None
    if D is None:
        return None, {'face_shadow_3q': {'status': 'SKIPPED', 'why': 'no spec.ref.face_sheet'}}
    fr = fr or HeadFrame(B)
    DL = design_light(design)
    lights = [('design', DL['key'])] if DL else []
    lights.append(('board', None))
    tables = {}
    pics, chin_pics = [], []
    for li, (lname, key) in enumerate(lights):
        t, p, cp = _shadow_views(B, D, fr, key, pictures=bool(out) and li == 0)
        tables[lname] = t
        pics += p
        chin_pics += cp
    main = lights[0][0]
    table = dict(tables[main], light=dict(name=main, key=list(DL['key']) if DL else None,
                                          board=tables.get('board') if main != 'board' else None))
    C = _shadow_checks(tables[main], tables.get('board') if main != 'board' else None, main)
    if out and pics:
        _save_row(os.path.join(out, 'qa_face_shadow.png'), pics)
    if out and chin_pics:
        _save_row(os.path.join(out, 'qa_chin_shadow.png'), chin_pics)
    return table, C


def _shadow_views(B, D, fr, key, pictures=False, cast=None):
    """face_shadow's per-view table under a camera key (None: the boards' light; cast: light_frames') -> (table,
    pictures, chin pictures)."""
    ss = fr.ss
    chin_z = fr.eye_z - float(B.assembly['chin'])
    rows_ours = fr.row(chin_z)
    table, pics, chin_pics = {}, [], []
    for view, az in (('front', 0.0), ('three_quarter', D['az3']), ('profile', 90.0)):
        h = D['heads'].get(view)
        if not h or not h['eyes']:
            continue
        q, m, px, soft, depth = board_tones(B, fr, az) if key is None else light_tones(B, fr, az, key, cast)
        chin_soft = _soft_width(q, m, soft, int(rows_ours * ss), int((rows_ours + 0.5 * fr.ppl) * ss), fr.ppl * ss)
        q, m, depth = q[ss // 2::ss, ss // 2::ss], m[ss // 2::ss, ss // 2::ss], depth[ss // 2::ss, ss // 2::ss]
        ours_sh = m & (q >= 1)
        # the design's view, cut to our window round its eyes (translation only: one scale, one eye line)
        oe = _ours_eyes(B, fr, az)
        de = np.array(h['eyes'], float)
        if view == 'profile' or len(de) < 2:
            o_c = oe[np.argmin(oe[:, 0])] if view == 'profile' else oe.mean(0)       # the near eye (her left, x < 0)
            d_c = de[np.argmin(de[:, 0])]
        else:
            o_c, d_c = oe.mean(0), de.mean(0)
        H, W = m.shape
        dy, dx = int(round(d_c[1] - o_c[1])), int(round(d_c[0] - o_c[0]))
        lab = np.full((H, W), 0)
        y0, x0 = max(0, dy), max(0, dx)
        y1, x1 = min(D['lab'].shape[0], dy + H), min(D['lab'].shape[1], dx + W)
        bx = h['box']
        sub = D['lab'][y0:y1, x0:x1].copy()
        yy, xx = np.mgrid[y0:y1, x0:x1]
        sub[(xx < bx[0]) | (xx >= bx[2]) | (yy < bx[1]) | (yy >= bx[3])] = 0
        lab[y0 - dy:y1 - dy, x0 - dx:x1 - dx] = sub
        d_skin = (lab == 1) | (lab == 5)
        d_sh = lab == 5
        d_rgb = _crop_design(D['rgb'], dy, dx, H, W)
        rr, cc = np.mgrid[dy:dy + H, dx:dx + W]
        d_line = (d_rgb.max(-1) < LINE_W_V) & (cc >= bx[0]) & (cc < bx[2]) & (rr >= bx[1]) & (rr < bx[3])
        rows = np.arange(H)[:, None]
        face_r, neck_r = rows < rows_ours, (rows >= rows_ours) & (rows < rows_ours + 0.5 * fr.ppl)
        both = m & d_skin
        rec = {}
        for nm, r in (('face', face_r), ('neck', neck_r)):          # over the skin both show (our collar, the
            a = both & r                                            # design's bare shoulders left out)
            rec[nm] = dict(ours=round(float(ours_sh[a].mean()), 4) if a.sum() > 50 else None,
                           design=round(float(d_sh[a].mean()), 4) if a.sum() > 50 else None, px=int(a.sum()))
        u = (ours_sh | d_sh) & both
        rec['iou'] = round(float((ours_sh & d_sh & both).sum() / u.sum()), 4) if u.sum() > 50 else None
        rec['az'] = az
        if view in CHIN_VIEWS:
            cx = float(o_c[0])
            Jo = jaw_depth(m, depth, rows_ours, cx, fr.ppl, fr.L)
            Jd = jaw_drawn(d_skin, d_line, rows_ours, cx, fr.ppl)
            go, gd = jaw_frame(ours_sh, m, Jo, fr.ppl), jaw_frame(d_sh, d_skin, Jd, fr.ppl)
            rec['chin'] = dict(chin_on_jaw(go, gd, fr.ppl), soft=chin_soft,
                               eye_aligned=_chin(ours_sh, d_sh, both & neck_r, fr.ppl))
            if pictures:
                chin_pics += [_jaw_pic(d_rgb, d_sh, Jd, rows_ours, cx, fr.ppl), _jaw_pic(qa_px(px),
                              ours_sh, Jo, rows_ours, cx, fr.ppl), _jaw_grid_pic(go, gd)]
        table[view] = rec
        if pictures:
            pics += [d_rgb, qa_px(px), _shadow_pic(m, ours_sh, d_skin, d_sh)]
    return table, pics, chin_pics


def _shadow_checks(t, board, light):
    """face_shadow's checks from its table under the main light (board: the boards' light's table beside)."""
    C = {}
    note = lambda c: dict(c, light=light)
    ch = {v: r['chin'] for v, r in t.items() if r.get('chin') and r['chin'].get('iou') is not None}
    if ch:
        bch = {v: r['chin'] for v, r in (board or {}).items() if r.get('chin') and r['chin'].get('iou') is not None}
        iou = float(np.mean([c['iou'] for c in ch.values()]))
        C['face_shadow_chin'] = note(_graded({'value': round(iou, 4), 'per_view': {v: c['iou'] for v, c in ch.items()}},
                                             iou, CHIN_IOU, True, CHIN_CAL['iou']))
        m = [c for c in ch.values() if c.get('edge') is not None]
        if m:
            edge = float(np.mean([c['edge'] for c in m]))
            C['face_shadow_chin_edge'] = note(_graded({
                'value': round(edge, 4), 'per_view': {v: c['edge'] for v, c in ch.items()},
                'ours_reach': {v: c['ours_reach'] for v, c in ch.items()},
                'design_reach': {v: c['design_reach'] for v, c in ch.items()}}, edge, CHIN_EDGE, False, CHIN_CAL['edge']))
        sw = [c['soft'] for c in ch.values() if c.get('soft') is not None]
        if sw:
            C['face_shadow_chin_soft'] = note({'value': round(float(np.mean(sw)), 4), 'status': 'INFO',
                                               'per_view': {v: c['soft'] for v, c in ch.items()}})
        if bch:
            C['face_shadow_chin']['board'] = round(float(np.mean([c['iou'] for c in bch.values()])), 4)
            be = [c['edge'] for c in bch.values() if c.get('edge') is not None]
            if be and 'face_shadow_chin_edge' in C:
                C['face_shadow_chin_edge']['board'] = round(float(np.mean(be)), 4)
    v3 = t.get('three_quarter')
    if v3:
        C['face_shadow_3q'] = note({'value': v3['iou'], 'status': 'INFO', 'per_view': {v: r['iou'] for v, r in t.items()}})
        if board and board.get('three_quarter'):
            C['face_shadow_3q']['board'] = board['three_quarter']['iou']
        for nm in ('face', 'neck'):
            o, d = v3[nm]['ours'], v3[nm]['design']
            if o is not None and d is not None:
                c = {'value': round(o - d, 4), 'ours': o, 'design': d, 'status': 'INFO',
                     'per_view': {v: dict(ours=r[nm]['ours'], design=r[nm]['design']) for v, r in t.items()}}
                if board and board.get('three_quarter'):
                    c['board'] = {v: r[nm]['ours'] for v, r in board.items()}
                C['face_shadow_%s_3q' % nm] = note(c)
    return C


CHIN_VIEWS = ('front', 'three_quarter')
# on the jaw (chin_on_jaw): calibrated (look.md round 6): the design's own shadow moved 1-2 px against its jaw reads IoU
# 0.81-0.94 and edge 0.003-0.012 L (PASS); round 1's band (look5_before: chin_tilt 85, no cast) reads IoU 0.68 and edge
# 0.064 L under the boards' light (FAIL); under the design light see CHIN_CAL
CHIN_IOU = (0.8, 0.7)            # face_shadow_chin: PASS at or over, WARN at or over (the IoU in jaw coordinates)
CHIN_EDGE = (0.02, 0.04)         # face_shadow_chin_edge, L: PASS at or under, WARN at or under
CHIN_CAL = {                     # whether each grade separates the design from the band (look.md round 6); None: INFO
    'iou': None,                 # not calibrated: the band reads 0.69-0.70 (0.76 front) against the design's own moves'
                                 # 0.81: too close to its FAIL line (0.7) to separate
    'edge': 'calibrated (look.md round 6): the design\'s own shadow moved 1-2 px against its jaw reads 0.003-0.012 L '
            '(PASS <= 0.02); round 1\'s band (look5_before: chin_tilt 85, no cast) reads 0.060 L under the boards\' '
            'light and 0.061 under the design light (FAIL > 0.04)',
}
CHIN_PIC = (0.25, 0.55, 0.45)    # the chin close-up round our chin, L: above, below, either side
JAW_WIN = (0.3, 0.15, 0.45)      # where the jaw is looked for: L over and under our chin's row, either side of the eyes
JAW_RUN = 0.08                   # L: the thickest ink run a drawn jaw may be (the wedge under the chin's point)
JAW_STEP = 0.004                 # L: the smallest step back in depth that is the jaw over the neck (ours)
JAW_GRID = (0.4, 0.35)           # the jaw-aligned grid: L either side of the chin's point, L under the jaw
JAW_NEAR = 0.03                  # L: a shadow starting further under the jaw than this is not the jaw's (its reach 0)


CHIN_UNCALIBRATED = ("INFO: not calibrated (tool/look5, docs/workstreams/look.md round 5): the design's own shadow moved "
                     "1-2 px reads IoU 0.55-0.87, and round 1's band (chin_tilt 85) reads as the cast does")


def _graded(c, v, lim, higher_better, cal):
    """a chin check: graded when its measure is calibrated (cal: a note of what separates), else INFO with its proposed
    grade beside (charkit.artifactqa's way)."""
    g = _grade_chin(v, lim, higher_better)
    if cal:
        c['status'] = g
        c['calibration'] = cal
    else:
        c['status'] = 'INFO'
        c['grade'] = g
        c['why'] = 'INFO: not calibrated on the jaw (docs/workstreams/look.md round 6)'
    return c


def _flag(c):
    """a chin check: INFO with its proposed grade beside (charkit.artifactqa's way), until it separates Michael's flag
    (round 1's band) from the design: it does not yet (CHIN_UNCALIBRATED)."""
    c['status'] = 'INFO'
    c['why'] = CHIN_UNCALIBRATED
    return c


def _grade_chin(v, lim, higher_better):
    p, w = lim
    if higher_better:
        return 'PASS' if v >= p else 'WARN' if v >= w else 'FAIL'
    return 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'


# ------------------------------------------------------------------------------------------------------ the chin, on the jaw
def _jaw_cols(shape, chin_row, cx, ppl):
    r0 = max(4, int(chin_row - JAW_WIN[0] * ppl))
    r1 = min(shape[0] - 4, int(chin_row + JAW_WIN[1] * ppl))
    c0, c1 = max(0, int(cx - JAW_WIN[2] * ppl)), min(shape[1], int(cx + JAW_WIN[2] * ppl))
    return r0, r1, c0, c1


def jaw_drawn(skin, line, chin_row, cx, ppl):
    """the design's jaw per column: its lowest ink run (at most JAW_RUN L thick) with skin within 3 px over and under
    it, in the jaw window round our chin's row -> {column: the neck's first row under it}."""
    r0, r1, c0, c1 = _jaw_cols(skin.shape, chin_row, cx, ppl)
    J = {}
    for c in range(c0, c1):
        col = line[:, c]
        r, best = r0, None
        while r < r1:
            if col[r]:
                s = r
                while r < skin.shape[0] and col[r]:
                    r += 1
                if r - s <= JAW_RUN * ppl and skin[max(0, s - 3):s, c].any() and skin[r:r + 3, c].any():
                    best = r
            else:
                r += 1
        if best is not None:
            while best < min(skin.shape[0], r1 + 4) and not skin[best, c]:
                best += 1
            J[c] = best
    return J


def jaw_depth(skin, depth, chin_row, cx, ppl, L):
    """our jaw per column: the largest step back in depth (the neck behind the jaw) between skin pixels 1-3 rows apart
    in the jaw window, if over JAW_STEP L -> {column: the neck's first row}."""
    r0, r1, c0, c1 = _jaw_cols(skin.shape, chin_row, cx, ppl)
    d = np.where(skin, depth, np.nan)[:, c0:c1]
    best = np.zeros(c1 - c0)
    row = np.full(c1 - c0, -1)
    with np.errstate(invalid='ignore'):
        for k in (1, 2, 3):
            st = d[r0 + k:r1 + k] - d[r0:r1]
            st = np.where(np.isfinite(st), st, -np.inf)
            i = np.argmax(st, 0)
            v = st[i, np.arange(st.shape[1])]
            take = v > best
            best[take], row[take] = v[take], (r0 + i + k)[take]
    return {c0 + j: int(row[j]) for j in range(c1 - c0) if row[j] >= 0 and best[j] > JAW_STEP * L}


def jaw_frame(shade, skin, J, ppl):
    """the shadow and skin in jaw coordinates: columns u from the chin's point (the middle of the jaw's lowest columns)
    JAW_GRID[0] L either side, rows k under the jaw down to JAW_GRID[1] L -> dict(sh, sk (2U+1, K) bool, reach (per u:
    the bottom of the first shaded run starting within JAW_NEAR L of the jaw, L; 0 where none; NaN where no neck)) or
    None."""
    if len(J) < 5:
        return None
    cs = np.array(sorted(J))
    js = np.array([J[c] for c in cs])
    apex = int(round(cs[js >= js.max() - 1].mean()))
    U, K = int(round(JAW_GRID[0] * ppl)), int(round(JAW_GRID[1] * ppl))
    sh = np.zeros((2 * U + 1, K), bool)
    sk = np.zeros((2 * U + 1, K), bool)
    reach = np.full(2 * U + 1, np.nan)
    near = JAW_NEAR * ppl
    for i, c in enumerate(range(apex - U, apex + U + 1)):
        j = J.get(c)
        if j is None:
            continue
        n = max(0, min(K, skin.shape[0] - j))
        sk[i, :n] = skin[j:j + n, c]
        sh[i, :n] = shade[j:j + n, c] & skin[j:j + n, c]
        if not sk[i, :3].any():
            continue
        idx = np.nonzero(sh[i])[0]
        if not len(idx) or idx[0] > near:
            reach[i] = 0.0
            continue
        b, gap = idx[0], 0
        for k in range(idx[0] + 1, K):
            if sh[i, k]:
                b, gap = k, 0
            elif sk[i, k]:
                gap += 1
                if gap > 2:
                    break
            else:
                break
        reach[i] = (b + 1) / ppl
    return dict(sh=sh, sk=sk, reach=reach)


def chin_on_jaw(o, d, ppl):
    """ours against the design's on the jaw (jaw_frame's): the shadows' IoU over the cells both show skin, and the
    lower edge's distance (the mean |our reach - the design's| over the columns both have, L: the V following the jaw
    against a band low on the neck) -> dict(iou, edge, ours_reach, design_reach, cols, px)."""
    none = dict(iou=None, edge=None, ours_reach=None, design_reach=None, cols=0, px=0)
    if o is None or d is None:
        return none
    both = o['sk'] & d['sk']
    if both.sum() < 50:
        return dict(none, px=int(both.sum()))
    u = (o['sh'] | d['sh']) & both
    iou = float((o['sh'] & d['sh'] & both).sum() / max(1, u.sum()))
    m = np.isfinite(o['reach']) & np.isfinite(d['reach'])
    r4 = lambda x: round(float(x), 4)
    if m.sum() < 5:
        return dict(none, iou=r4(iou), px=int(both.sum()))
    return dict(iou=r4(iou), edge=r4(np.mean(np.abs(o['reach'][m] - d['reach'][m]))), ours_reach=r4(o['reach'][m].mean()),
                design_reach=r4(d['reach'][m].mean()), cols=int(m.sum()), px=int(both.sum()))


def _jaw_pic(rgb, sh, J, chin_row, cx, ppl):
    """a chin close-up: the picture, its shadow tinted blue, the jaw found (red)."""
    img = np.clip(np.asarray(rgb, float)[..., :3], 0, 1).copy()
    img[sh] = img[sh] * 0.55 + np.array([0.2, 0.3, 0.9]) * 0.45
    for c, j in J.items():
        if 0 <= j - 1 < img.shape[0]:
            img[j - 1, c] = (0.9, 0.05, 0.05)
    r0, r1 = int(chin_row - CHIN_PIC[0] * ppl), int(chin_row + CHIN_PIC[1] * ppl)
    return _cut(img, r0, r1, int(cx - CHIN_PIC[2] * ppl), int(cx + CHIN_PIC[2] * ppl))


def _jaw_grid_pic(o, d):
    """the jaw-aligned grids overlaid (rows under the jaw down, columns across): both shaded (dark red), ours only
    (orange), the design's only (blue), skin both lit (pale)."""
    if o is None or d is None:
        return np.full((20, 20, 3), 0.93)
    both = o['sk'] & d['sk']
    img = np.full(o['sh'].shape + (3,), 0.93)
    img[o['sk'] | d['sk']] = (0.80, 0.80, 0.82)
    img[both] = (0.99, 0.94, 0.90)
    img[o['sh'] & ~d['sh'] & both] = (0.95, 0.55, 0.20)
    img[d['sh'] & ~o['sh'] & both] = (0.25, 0.45, 0.90)
    img[o['sh'] & d['sh'] & both] = (0.60, 0.12, 0.15)
    return np.repeat(np.repeat(img.transpose(1, 0, 2), 2, 0), 2, 1)


def _chin(ours_sh, d_sh, region, ppl):
    """the shadow under the chin (region: the neck window, the chin to 0.5 L under it, over the skin both show),
    ours against the design's: their IoU, and per column how far under the chin the shadow reaches (its lowest pixel
    below the window's top, L; 0 where the column has none: the V under the jaw drawn as a profile) -> dict(iou, edge
    (the mean |our reach - the design's| over the columns both show, L), ours_reach, design_reach (their means, L),
    ours_depth, design_depth (the shadow's pixels per column, L, means: INFO), px).
    The reach, not the pixel count, is graded: a count is blind to where the shadow sits (a band of the V's mean
    thickness low on the neck reads as the V; test_chin_separates_the_v_from_the_band)."""
    a = region
    if a.sum() < 50:
        return dict(iou=None, edge=None, ours_reach=None, design_reach=None, ours_depth=None, design_depth=None,
                    px=int(a.sum()))
    u = (ours_sh | d_sh) & a
    iou = float((ours_sh & d_sh & a).sum() / max(1, u.sum()))
    cols = a.sum(0) >= 0.05 * ppl                       # columns with neck skin both show
    if not cols.any():
        return dict(iou=round(iou, 4), edge=None, ours_reach=None, design_reach=None, ours_depth=None,
                    design_depth=None, px=int(a.sum()))
    r0 = int(np.nonzero(a.any(1))[0][0])
    rows = np.arange(a.shape[0])[:, None]

    def reach(sh):
        low = np.where(sh & a, rows, -1).max(0)
        return (np.where(low >= 0, low + 1 - r0, 0) / ppl)[cols]
    ro, rd = reach(ours_sh), reach(d_sh)
    do = (ours_sh & a).sum(0)[cols] / ppl
    dd = (d_sh & a).sum(0)[cols] / ppl
    r4 = lambda x: round(float(x), 4)
    return dict(iou=r4(iou), edge=r4(np.mean(np.abs(ro - rd))), ours_reach=r4(ro.mean()), design_reach=r4(rd.mean()),
                ours_depth=r4(do.mean()), design_depth=r4(dd.mean()), px=int(a.sum()))


def _soft_width(q, m, soft, r0, r1, ppl):
    """how wide the tone steps run on the skin in rows r0..r1 (the neck window, supersampled): the soft pixels (a tone
    between steps) per pixel of step edge, in L (a clean cel edge ~0: a smeared band wide) -> float or None."""
    q, m, soft = q[r0:r1], m[r0:r1], soft[r0:r1]
    e = ((q[:, 1:] != q[:, :-1]) & m[:, 1:] & m[:, :-1]).sum() + ((q[1:] != q[:-1]) & m[1:] & m[:-1]).sum()
    if e < 10:
        return None
    return round(float(soft.sum() / e / ppl), 4)


def _cut(a, r0, r1, c0, c1):
    """a window of an image (padded pale where it runs off)."""
    H, W = a.shape[:2]
    out = np.full((r1 - r0, c1 - c0) + a.shape[2:], 0.93)
    y0, y1, x0, x1 = max(0, r0), min(H, r1), max(0, c0), min(W, c1)
    if y1 > y0 and x1 > x0:
        out[y0 - r0:y1 - r0, x0 - c0:x1 - c0] = a[y0:y1, x0:x1]
    return out


def qa_px(px):
    return np.where(px[..., 3:4] > 0.5, px[..., :3], 0.93)


def _crop_design(rgb, dy, dx, H, W):
    out = np.full((H, W, 3), 0.93)
    y0, x0 = max(0, dy), max(0, dx)
    y1, x1 = min(rgb.shape[0], dy + H), min(rgb.shape[1], dx + W)
    out[y0 - dy:y1 - dy, x0 - dx:x1 - dx] = rgb[y0:y1, x0:x1]
    return out


def _shadow_pic(m, ours_sh, d_skin, d_sh):
    """ours and the design's skin shadows overlaid: both (dark red), ours only (orange), the design's only (blue), skin
    lit in both (pale), other skin (grey)."""
    img = np.full(m.shape + (3,), 0.93)
    img[m | d_skin] = (0.80, 0.80, 0.82)
    img[m & d_skin] = (0.99, 0.94, 0.90)
    img[ours_sh & ~d_sh & d_skin] = (0.95, 0.55, 0.20)
    img[d_sh & ~ours_sh & m] = (0.25, 0.45, 0.90)
    img[ours_sh & d_sh] = (0.60, 0.12, 0.15)
    return img


# ------------------------------------------------------------------------------------------------------ lines
def widths(mask, ss=1, min_px=10):
    """a line mask's widths: twice the distance to its edge at each skeleton pixel, in output pixels (supersampled
    masks divided by ss) -> array. Measured on the mask cut to its lines' box and a pixel round it (the same distances
    and skeleton as on the whole mask: the ring is background, and where the box meets the mask's edge, so does the
    cut)."""
    from scipy import ndimage
    from skimage.morphology import skeletonize
    if mask.sum() < max(1, min_px):
        return np.zeros(0)
    ys, xs = np.nonzero(mask.any(1))[0], np.nonzero(mask.any(0))[0]
    mask = mask[max(0, ys[0] - 1):ys[-1] + 2, max(0, xs[0] - 1):xs[-1] + 2]
    d = ndimage.distance_transform_edt(mask)
    sk = skeletonize(mask)
    return (2 * d[sk] - 1) / ss if ss > 1 else 2 * d[sk] - 1


def _stats(w):
    if len(w) < 20:
        return None
    p10, p50, p90 = np.percentile(w, [10, 50, 90])
    return dict(median=round(float(p50), 3), p10=round(float(p10), 3), p90=round(float(p90), 3),
                spread=round(float(p90 / max(p10, 1e-6)), 3), n=int(len(w)))


def _region(o):
    return {'skin': 'skin', 'hair': 'hair', 'garment': 'garment'}.get(o.group, 'accessory')


def line_scale(B, native_ppl, native_h):
    """{object: k}: each outlined object's width in the design's framing as its build width's multiple (the style's
    'screen' lines: frac of a native_h-tall page at native_ppl px per L; 'world' lines: 1)."""
    look = B.meta('look') or {}
    ln = dict(look.get('lines') or {})
    if ln.get('mode') != 'screen':
        return {}
    L = float(B.assembly['L'])
    reg = dict(ln.get('regions') or {})
    out = {}
    for o in B.objects():
        if o.outline and o.outline.get('thickness'):
            w0 = abs(float(o.outline['thickness']))
            out[o.name] = ln.get('frac', 0.0025) * native_h * (L / native_ppl) * reg.get(_region(o), 1.0) / w0
    return out


LINE_WIN = (0.85, 1.05, 0.95)    # the line measure's window round the eye line, in L (the head and its hair)


def _hull_colours(B, surfs, hulls, az):
    """per surface, the colour charkit.qa3d.draw gives a line (an outline hull's material, shaded as draw shades it
    under the view's light; NaN for the rest) -> (len(surfs), 3) linear."""
    from . import qa3d
    a = np.radians(az)
    view_d = np.array([-np.sin(a), np.cos(a), 0.0])
    ldir = qa3d.view_light(B, az)
    col = np.full((len(surfs), 3), np.nan)
    for i in hulls:
        s_ = surfs[i]
        mat = s_['o'].material(int(s_['slots'][0]))[1]
        col[i] = qa3d._shade(B, s_['o'], mat, -view_d[None, :], view_d, ldir)[0]
    return col


def _lines_pic(mi, rgb, hulls, ss):
    """what line_width measures, at the output resolution: the lines in their own colour over the figure's silhouette
    (pale) on grey."""
    from . import qa3d
    H, W = mi.shape[0] // ss, mi.shape[1] // ss
    mi, rgb = mi[:H * ss, :W * ss], rgb[:H * ss, :W * ss]
    ln = np.isin(mi, list(hulls))
    cov = ln.reshape(H, ss, W, ss).mean(axis=(1, 3))[..., None]
    col = (np.where(ln[..., None], rgb, 0.0).reshape(H, ss, W, ss, 3).sum(axis=(1, 3))
           / np.maximum(ln.reshape(H, ss, W, ss).sum(axis=(1, 3)), 1)[..., None])
    fig = (mi >= 0).reshape(H, ss, W, ss).mean(axis=(1, 3))[..., None]
    base = 0.93 * (1 - fig) + 0.99 * fig
    return base * (1 - cov) + qa3d._srgb(col) * cov


def design_widths(lines0, ss=4):
    """the design's line widths: widths() of its line pixels (lines0, at its own resolution) upsampled x ss, one group
    of lines at a time (lines within 4 px of each other together: the same widths as the whole sheet's, on a fraction
    of its pixels)."""
    from scipy import ndimage
    if lines0.sum() * ss * ss < 10:
        return np.zeros(0)
    lab, n = ndimage.label(ndimage.binary_dilation(lines0, iterations=2), structure=np.ones((3, 3)))
    out = []
    for i, sl in enumerate(ndimage.find_objects(lab)):
        cut = lines0[sl] & (lab[sl] == i + 1)
        out.append(widths(np.repeat(np.repeat(cut, ss, 0), ss, 1), ss, min_px=1))
    return np.concatenate(out) if out else np.zeros(0)


def line_width(B, design, out=None, ss=4, ppl=None, off=(0.0, 0.0)):
    """-> (table, checks line_width (our median width over the design's), line_spread (p90 / p10 of ours), line_ink),
    in px of the design's own page: ours drawn at ppl px per L (None: the design's own), supersampled ss, their widths
    scaled by the design's px per L over ppl; its lines measured at its resolution x ss. Only the z-buffer is drawn
    (every surface occludes the lines), each line in its hull's flat colour: our lines' colour is the median of their
    supersampled pixels (a line's own colour, not its blend with its neighbours after the pixel filter).
    The widths need the design's scale: at 200 px per L x 3 a 2 px line is 3 sub-pixels across and the median steps
    by 0.67 px (docs/workstreams/look.md, round 2)."""
    D = design_heads(design) if design is not None else None
    native_ppl, native_h = (D['native_ppl'], D['native_h']) if D else (401.0, 1440)
    ppl = native_ppl if ppl is None else ppl
    k = native_ppl / ppl
    fr = HeadFrame(B, ppl=ppl, ss=ss, win=LINE_WIN, off=off)
    ks = line_scale(B, native_ppl, native_h)
    surfs = _scene(B, skin_outline=True, line_scale=ks)
    from . import qa3d
    hull_region = [(_region(s_['o']) if s_['hull'] else None) for s_ in surfs]
    hulls = {i for i, h in enumerate(hull_region) if h}
    allw = {r: [] for r in REGIONS}
    allc = {r: [] for r in REGIONS}
    pics = []
    for az in VIEWS:
        mi = qa3d.draw_ids(B, surfs, az, fr)                    # the surface per pixel (draw()'s aux['mesh'])
        col = _hull_colours(B, surfs, hulls, az)                # each line's colour as draw() shades it (flat)
        rgb = col[np.maximum(mi, 0)]
        for r in REGIONS:
            ids = [i for i, h in enumerate(hull_region) if h == r]
            if ids:
                mk = np.isin(mi, ids)
                allw[r].append(widths(mk, ss) * k)
                allc[r].append(rgb[mk])
        if out:
            pics.append(_lines_pic(mi, rgb, hulls, ss))
    ours = {r: _stats(np.concatenate(w)) for r, w in allw.items() if w}
    ours = {r: v for r, v in ours.items() if v}
    table = {'ours': ours, 'page': dict(native_ppl=round(native_ppl, 1), native_h=native_h),
             'drawn': dict(ppl=round(float(ppl), 1), ss=ss),
             'scale': {k_: round(v, 3) for k_, v in ks.items()} or 'build widths'}
    C = {}
    allo = [np.concatenate(w) for w in allw.values() if w]
    so = _stats(np.concatenate(allo)) if allo else None
    table['ours_all'] = so
    from . import paletteqa
    ours_ink = {r: np.floor(np.clip(qa3d._srgb(np.median(np.concatenate(c), 0)), 0, 1) * 255 + 0.5) / 255
                for r, c in allc.items() if c and sum(len(x) for x in c) > 20}
    table['ink'] = {r: paletteqa._hex(c) for r, c in ours_ink.items()}
    if D:
        dw = _stats(design.memo(design_widths, D['lines0'], 4))
        table['design'] = dw
        di = D.get('ink')
        if di is not None and ours_ink:
            table['design_ink'] = paletteqa._hex(di)
            dE = {r: round(float(paletteqa.ciede2000(paletteqa.srgb_to_lab(c), paletteqa.srgb_to_lab(di))), 2)
                  for r, c in ours_ink.items()}
            C['line_ink'] = {'value': max(dE.values()), 'per_region': dE, 'ours': table['ink'],
                             'design': table['design_ink'], 'status': 'INFO'}
        if dw and so:
            C['line_width'] = {'value': round(so['median'] / dw['median'], 3), 'ours_px': so['median'],
                               'design_px': dw['median'], 'status': 'INFO'}
            C['line_spread'] = {'value': so['spread'], 'design': dw['spread'],
                                'per_region': {r: v['spread'] for r, v in ours.items()}, 'status': 'INFO'}
    if out and pics:
        _save_row(os.path.join(out, 'qa_lines.png'), pics)
    return table, C


def measure(B, design=None, out=None):
    """the look's part: face_noise, face_shadow, line_width -> (table, checks)."""
    table, C = {}, {}
    for name, fn in (('noise', lambda: face_noise(B, out, design)), ('shadow', lambda: face_shadow(B, design, out)),
                     ('lines', lambda: line_width(B, design, out))):
        t, c = fn()
        table[name] = t
        C.update(c)
    return table, C


def main(args):
    """python -m charkit.lookqa BUILD_OUT [--out DIR] [--note TEXT]: the look's QA alone on a build's bundle (its pictures
    and look.json {checks, table, note} into DIR, default BUILD_OUT/qa_look: what charkit.lookpage reads)."""
    import json
    from . import bundle, qa3d
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    B = bundle.load(os.path.join(args[0], 'bundle'))
    out = opt('--out', os.path.join(args[0], 'qa_look'))
    os.makedirs(out, exist_ok=True)
    table, C = measure(B, qa3d.Design(B), out)
    json.dump(dict(checks=C, table=table, note=opt('--note', '')), open(os.path.join(out, 'look.json'), 'w'), indent=1,
              default=qa3d._json)
    print(json.dumps({k: (v.get('value'), v.get('status')) for k, v in C.items()}, default=qa3d._json))


if __name__ == '__main__':
    import sys
    from charkit import lookqa as _lq            # the module's own functions (the venv memo keys on their module)
    _lq.main(sys.argv[1:])
