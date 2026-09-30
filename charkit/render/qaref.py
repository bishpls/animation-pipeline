"""The QA's two drawings against EEVEE on the QA's own frames (docs/workstreams/toonrender.md, phase 2): the evidence for
which drawing measures the look the boards show. For one build (its bundle, export and .blend), every frame a drawn QA
check reads is drawn three ways: charkit.qa3d's numpy rasteriser, charkit.render (the render drawing), and EEVEE in
Blender (charkit/render/eevee_frames.py: the same window, light and outlines). Then, per frame and per check:

  tones     the head frames (lookqa.HeadFrame: 0, 30, 90 degrees and the three-quarter, under the board light and the
            sweep's four), one sample at each pixel centre of the measuring grid (EEVEE: one sample, no film filter),
            each drawing's colour classified into the skin's tones (lit, shade, deep; the face's lit and shade) by the
            nearest of the look's colours: the share of skin pixels whose tone agrees with EEVEE's, and face_noise's
            tone edges, face_islands and the shadow shares measured on each classified map (and on each drawing's own
            exact tones, the value the QA reports)
  hair      hair_noise's frames (the figure frame from 0, 90, 180 degrees, every outline off; the boards' film: 64
            samples, the 1.5 px filter), streaks off and on: hair_noise on each picture over one hair mask, and the
            pictures' differences on the hair (levels)
  pictures  the head frames' pictures (the boards' film) against EEVEE's: mean and share over 8 levels
  body      artifactqa's body frame (the body sheet's px per L, one sample a pixel, the design's framing's line widths:
            what the art_* checks of the collar, bow, top, skirt and boots and the silhouette checks read) from the
            front, three-quarter, profile and back: each drawing's unfiltered samples against EEVEE's point-sampled
            frame (the silhouette's IoU and pixels off, mean levels and share over 8 levels on the figure and on its
            lines), and each drawing's part buffer against the other's

    python -m charkit.render qaref BUILD [--out DIR] [--no-eevee] [--blender PATH]     # DIR/qaref.json, DIR/*.png
"""
import json, os, subprocess, sys, time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TONE_NAMES = ('lit', 'shade', 'deep')


def _blender():
    return os.environ.get('BLENDER', '/Applications/Blender.app/Contents/MacOS/Blender')


def skin_palette(M, skin):
    """the skin's flat tones as 8-bit sRGB -> (colours (n, 3), tone (n,)): toon3's lit, shade, deep (0, 1, 2) and the
    face's lit and shade (0, 1)."""
    from .compare import srgb8
    cols, tone = [], []
    for P in M.prims:
        if P.object != skin:
            continue
        L = P.look
        if L.get('kind') in ('toon3', 'face'):
            for t, k in enumerate(('lit', 'shade', 'deep')):
                cols.append(srgb8(L[k])); tone.append(t)
        if L.get('kind') == 'face':
            cols.append(srgb8(L['face']['lit'])); tone.append(0)
            cols.append(srgb8(L['face']['shade'])); tone.append(1)
    C, T = np.array(cols, float), np.array(tone)
    _, first = np.unique(C, axis=0, return_index=True)
    return C[np.sort(first)], T[np.sort(first)]


def classify(rgb8, pal):
    """(H, W, 3) 8-bit sRGB -> the nearest palette colour's tone (H, W)."""
    C, T = pal
    x = rgb8.reshape(-1, 3).astype(np.float32)
    d = ((x[:, None, :] - C[None].astype(np.float32)) ** 2).sum(-1)
    return T[np.argmin(d, 1)].reshape(rgb8.shape[:2])


def lin_to_srgb8(c):
    c = np.clip(np.asarray(c, float), 0, None)
    s = np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)
    return np.floor(np.clip(s, 0, 1) * 255 + 0.5)


def _read_png(p):
    from PIL import Image
    return np.asarray(Image.open(p).convert('RGBA')).astype(np.float64) / 255.0


def head_frames(B, design=None):
    """the head frames lookqa draws: (name, az, light (world), frame) for the board light at 0, 30, 90 and the
    three-quarter (face_shadow's), and the sweep's four lights at 0, 30, 90."""
    from charkit import lookqa, qa3d
    fr = lookqa.HeadFrame(B)
    az3 = 35.0
    if design is not None:
        D = lookqa.design_heads(design)
        if D:
            az3 = float(D['az3'])
    out = []
    for az in sorted(set(lookqa.VIEWS) | {az3}):
        out.append(('head_%03d' % round(az) if az == int(az) else 'head_%05.1f' % az, float(az), qa3d.view_light(B, az), fr))
    for az in lookqa.VIEWS:
        for a0, el in lookqa.SWEEP:
            out.append(('sweep_%03d_%+03d_%02d' % (az, a0, el), float(az), lookqa.key_light(az, a0, el), fr))
    return out


def body_frames(B, design):
    """artifactqa's body frame as its checks draw it: (name, az, frame, surfaces) for the front, three-quarter, profile
    and back, or [] without the design's body sheet."""
    from charkit import artifactqa, lookqa
    ctx = design.sheet_context() if design is not None else {'why': 'no design'}
    if 'why' in ctx:
        return []
    ppl, page = ctx['ppl'], (ctx['rgb'].shape[0] if 'rgb' in ctx else 1440)
    fr = artifactqa._frame(B, ppl, artifactqa.BODY_WIN)
    surfs = lookqa._scene(B, skin_outline=True, line_scale=lookqa.line_scale(B, ppl, page))
    views = (('front', 0.0), ('three_quarter', float(ctx['az3'])), ('profile', 90.0), ('back', 180.0))
    return [('body_' + v, az, fr, surfs) for v, az in views]


def run(build, out=None, eevee=True, blender=None, streaks=(False, True)):
    """the comparison for a build directory (bundle, export, .blend) -> the report (DIR/qaref.json)."""
    from charkit import bundle, lookqa, qa3d, qarender
    from charkit.render import buffers, buildboards
    from PIL import Image
    build = os.path.abspath(build)
    out = os.path.abspath(out or os.path.join(build, 'qaref'))
    os.makedirs(out, exist_ok=True)
    B = bundle.load(os.path.join(build, 'bundle'))
    design = qa3d.Design(B)
    Q = buffers.load(buildboards.export_of(build))
    sk = B.skin()
    pal = skin_palette(Q.M, sk.name)
    heads = head_frames(B, design)
    hfr = qa3d.figure_frame(B, ss=qa3d.FIG_SS)
    outlined = sorted({P.object for P in Q.prims if P.outline})
    ss = heads[0][3].ss
    # ---- EEVEE
    jobs = []
    for name, az, ld, fr in heads:
        base = dict(az=az, origin=list(fr.origin), light=[float(x) for x in ld], off=[sk.name], transparent=True)
        jobs.append(dict(base, path=os.path.join(out, 'eevee', name + '_point.png'), pix=fr.pix,
                         win=dict(fr.win), point=True, streaks=True))
        if name.startswith('head'):
            jobs.append(dict(base, path=os.path.join(out, 'eevee', name + '_film.png'), pix=fr.pix * ss,
                             win=_win_out(fr.win, fr.pix, ss), point=False, streaks=True))
    for az in (0, 90, 180):
        for st in streaks:
            jobs.append(dict(az=float(az), origin=list(hfr.origin), light=[float(x) for x in qa3d.view_light(B, az)],
                             off=outlined, transparent=True, path=os.path.join(out, 'eevee', 'hair_%03d_%s.png' %
                                                                                 (az, 'streaks' if st else 'plain')),
                             pix=hfr.pix * qa3d.FIG_SS, win=_win_out(hfr.win, hfr.pix, qa3d.FIG_SS), point=False,
                             streaks=st))
    body = body_frames(B, design)
    for name, az, fr, surfs in body:
        jobs.append(dict(az=az, origin=list(fr.origin), light=[float(x) for x in qa3d.view_light(B, az)], off=[],
                         transparent=True, path=os.path.join(out, 'eevee', name + '_point.png'), pix=fr.pix,
                         win=dict(fr.win), point=True, streaks=True,
                         line_k={s['o'].name: float(s['line_k']) for s in surfs if s.get('line_k') is not None}))
    rep = {'build': build, 'export': Q.M.path, 'adapter': Q.info, 'created': time.strftime('%Y-%m-%d %H:%M'),
           'palette': {'colours': pal[0].tolist(), 'tone': pal[1].tolist()}}
    if eevee:
        blend = next((os.path.join(build, f) for f in sorted(os.listdir(build)) if f.endswith('.blend')), None)
        if blend is None:
            raise SystemExit('%s: no .blend (build without --no-blend)' % build)
        os.makedirs(os.path.join(out, 'eevee'), exist_ok=True)
        jp = os.path.join(out, 'eevee', 'frames.json')
        json.dump({'frames': jobs}, open(jp, 'w'), indent=1)
        t = time.time()
        r = subprocess.run([blender or _blender(), '-b', blend, '--python', os.path.join(HERE, 'eevee_frames.py'), '--',
                            jp], capture_output=True, text=True)
        rep['eevee_seconds'] = round(time.time() - t, 1)
        if r.returncode or 'EEVEE_FRAME' not in r.stdout:
            raise SystemExit('eevee_frames failed:\n' + (r.stdout + r.stderr)[-3000:])
    have = lambda p: os.path.exists(p)
    # ---- the head frames: tones
    rows = {}
    for name, az, ld, fr in heads:
        os.environ[qarender.ENV] = 'numpy'
        surfs = lookqa._scene(B)
        view = qa3d.draw_view(B, surfs, az, fr)
        a0 = {}
        px0 = qa3d.draw_lit(B, view, ld, ss=ss, aux=a0)
        # numpy's colour per sample: draw_lit's 'rgb' (linear), where the skin is
        m0 = (a0['mesh'] == 0)
        c0 = lin_to_srgb8(a0['rgb'])
        os.environ[qarender.ENV] = 'render'
        cam = buffers.window(az, fr.origin, fr.pix, fr.win)
        F = Q.frame(cam, off={sk.name}, light=ld, aux_ss=1, picture=False, colour=True)
        m1 = (Q.object_of(F['part']) == sk.name) & ~F['hull']
        col = F['colour'].astype(np.float64)
        c1 = lin_to_srgb8(np.where(col[..., 3:4] > 1e-6, col[..., :3] / np.maximum(col[..., 3:4], 1e-6), 0))
        t0_, t1_ = a0['tone'], F['tone']
        m = m0 & m1 & np.isfinite(t0_) & np.isfinite(t1_)
        row = {'az': az, 'skin_px': [int(m0.sum()), int(m1.sum())],
               'skin_iou': round(float((m0 & m1).sum() / max((m0 | m1).sum(), 1)), 5)}
        q0x, q1x = np.rint(np.nan_to_num(t0_)).astype(int), np.rint(np.nan_to_num(t1_)).astype(int)
        q0c, q1c = classify(c0, pal), classify(c1, pal)
        maps = {'numpy_exact': q0x, 'render_exact': q1x, 'numpy_colour': q0c, 'render_colour': q1c}
        pe = os.path.join(out, 'eevee', name + '_point.png')
        if have(pe):
            e = _read_png(pe)
            me = e[..., 3] > 0.5
            qe = classify(np.floor(e[..., :3] * 255 + 0.5), pal)
            maps['eevee_colour'] = qe
            m = m & me
            for k in ('numpy_exact', 'render_exact', 'numpy_colour', 'render_colour'):
                row['agree_' + k] = round(float((maps[k][m] == qe[m]).mean()), 5)
        row['px'] = int(m.sum())
        chin_row = fr.row(fr.eye_z - float(B.assembly['chin'])) * ss
        rows_ = np.arange(m.shape[0])[:, None]
        mm = m & (rows_ < chin_row + 0.5 * fr.ppl * ss)
        for k, q in maps.items():
            row['edges_' + k] = round(float(lookqa._edges(q, mm) * ss), 4)
            row['islands_' + k] = lookqa._islands(q, mm, lookqa.ISLAND * (fr.ppl * ss) ** 2)
            sub = (q[ss // 2::ss, ss // 2::ss] >= 1) & m[ss // 2::ss, ss // 2::ss]
            r_ = np.arange(sub.shape[0])[:, None]
            cr = fr.row(fr.eye_z - float(B.assembly['chin']))
            face = m[ss // 2::ss, ss // 2::ss] & (r_ < cr)
            neck = m[ss // 2::ss, ss // 2::ss] & (r_ >= cr) & (r_ < cr + 0.5 * fr.ppl)
            row['shade_face_' + k] = round(float(sub[face].mean()), 4) if face.any() else None
            row['shade_neck_' + k] = round(float(sub[neck].mean()), 4) if neck.any() else None
        if name.startswith('head'):
            os.environ[qarender.ENV] = 'render'
            pr = qa3d.draw_lit(B, qa3d.draw_view(B, surfs, az, fr), ld, ss=ss)
            pf = os.path.join(out, 'eevee', name + '_film.png')
            pics = {'numpy': px0, 'render': pr}
            if have(pf):
                e = _read_png(pf)
                for k, p in pics.items():
                    d = np.abs(p[..., :3] - e[..., :3]).max(-1) * 255
                    fg = (p[..., 3] > 0.5) | (e[..., 3] > 0.5)
                    row['pic_mean_' + k] = round(float(d[fg].mean()), 3)
                    row['pic_over8_' + k] = round(float((d[fg] > 8).mean()), 5)
                    row['pic_iou_' + k] = round(float(((p[..., 3] > 0.5) & (e[..., 3] > 0.5)).sum() / max(fg.sum(), 1)), 5)
                _strip(os.path.join(out, name + '.png'), [px0, pr, e], ['numpy', 'render', 'EEVEE'])
            _tones_pic(os.path.join(out, name + '_tones.png'), maps, m, ss)
        rows[name] = row
        print(name, {k: v for k, v in row.items() if k.startswith(('agree', 'edges'))}, flush=True)
    rep['tones'] = rows
    # ---- hair_noise's frames
    hair = qa3d._visible(B, ('hair',))
    groups = [qa3d.hair_noise_group(o) for o in hair for _ in qa3d.surfaces(B, o, outline=False)]
    hrows = {}
    for az in (0, 90, 180):
        os.environ[qarender.ENV] = 'numpy'
        surfs = [x for o in hair for x in qa3d.surfaces(B, o, outline=False)]
        occ = [x for o in B.objects() if o.group != 'hair' and o.has('eval')
               for x in qa3d.surfaces(B, o, 'masked' if o.group == 'skin' else 'eval', outline=False)]
        view = qa3d.draw_view(B, surfs + occ, az, hfr)
        px0 = qa3d.draw_lit(B, view)
        grp_of = np.array(groups + [-1] * len(occ) + [-1])
        lab = qa3d._to_shape(grp_of[view['mesh']], px0.shape[:2])
        os.environ[qarender.ENV] = 'render'
        rv = qa3d.draw_view(B, surfs + occ, az, hfr)
        pics = {'numpy': px0}
        for st in streaks:
            cam = rv.camera(qa3d.FIG_SS)
            pics['render_%s' % ('streaks' if st else 'plain')] = Q.frame(
                cam, draw=rv.draw, off=rv.off, light=qa3d.view_light(B, az), transparent=True, aux=False,
                streaks=st)['picture']
            pe = os.path.join(out, 'eevee', 'hair_%03d_%s.png' % (az, 'streaks' if st else 'plain'))
            if have(pe):
                pics['eevee_%s' % ('streaks' if st else 'plain')] = _read_png(pe)
        row = {}
        for k, px in pics.items():
            grp = np.where((px[..., 3] > 0.5) & (lab >= 1), lab, 0)
            lum = px[..., :3] @ np.array([0.3, 0.59, 0.11])
            e, n = qa3d.tone_edges(lum, grp)
            row['hair_noise_' + k] = round(float((e & (grp > 0)).sum()) / max(1, n), 4)
        for st in ('plain', 'streaks'):
            ek = 'eevee_' + st
            if ek not in pics:
                continue
            hm = (lab >= 1) & (pics[ek][..., 3] > 0.5)
            for k in ('numpy', 'render_' + st):
                if k in pics:
                    d = np.abs(pics[k][..., :3] - pics[ek][..., :3]).max(-1) * 255
                    row['hair_mean_%s_vs_%s' % (k, ek)] = round(float(d[hm].mean()), 3)
                    row['hair_over8_%s_vs_%s' % (k, ek)] = round(float((d[hm] > 8).mean()), 5)
        _strip(os.path.join(out, 'hair_%03d.png' % az), list(pics.values()), list(pics))
        hrows[az] = row
        print('hair', az, row, flush=True)
    rep['hair'] = hrows
    # ---- artifactqa's body frame: each drawing's unfiltered samples (its part buffer and colour at each pixel's centre,
    # what the art_* checks read) against EEVEE's point-sampled frame (a filtered picture against point samples would
    # measure the film filter, not the drawing)
    brows = {}
    for name, az, fr, surfs in body:
        pics, mesh, cols = {}, {}, {}
        for d in ('numpy', 'render'):
            os.environ[qarender.ENV] = d
            aux = {}
            v = qa3d.draw_view(B, surfs, az, fr)
            pics[d] = qa3d.draw_lit(B, v, ss=1, aux=aux)
            mesh[d] = aux['mesh']
            if d == 'numpy':
                cols[d] = lin_to_srgb8(aux['rgb'])
            else:
                col = v._frame(None, picture=False, colour=True)['colour'].astype(np.float64)
                cols[d] = lin_to_srgb8(np.where(col[..., 3:4] > 1e-6, col[..., :3] / np.maximum(col[..., 3:4], 1e-6), 0))
        fig = (mesh['numpy'] >= 0) | (mesh['render'] >= 0)
        row = {'az': az, 'parts_agree_figure': round(float((mesh['numpy'] == mesh['render'])[fig].mean()), 5)}
        pe = os.path.join(out, 'eevee', name + '_point.png')
        if have(pe):
            e = _read_png(pe)
            pics['eevee'] = e
            fe, ce = e[..., 3] > 0.5, np.floor(e[..., :3] * 255 + 0.5)
            for k in ('numpy', 'render'):
                fo = mesh[k] >= 0
                both = fo & fe
                hull = np.array([s_['hull'] for s_ in surfs] + [False])[np.where(fo, mesh[k], len(surfs))]
                dd = np.abs(cols[k] - ce).max(-1)
                row['sil_iou_' + k] = round(float(both.sum() / max((fo | fe).sum(), 1)), 5)
                row['sil_off_px_' + k] = int((fo ^ fe).sum())
                row['mean_' + k] = round(float(dd[both].mean()), 3)
                row['over8_' + k] = round(float((dd[both] > 8).mean()), 5)
                row['over8_lines_' + k] = round(float((dd[both & hull] > 8).mean()), 5)
        _strip(os.path.join(out, name + '.png'), list(pics.values()), list(pics))
        brows[name] = row
        print(name, row, flush=True)
    rep['body'] = brows
    rep['summary'] = summary(rep)
    os.environ.pop(qarender.ENV, None)
    json.dump(rep, open(os.path.join(out, 'qaref.json'), 'w'), indent=1, default=float)
    return rep


def _win_out(win, pix, ss):
    """a measuring grid's window at ss x its pixel (the picture's grid: the same top-left corner)."""
    W = int(round(2 * win['x'] / pix)); H = int(round((win['top'] - win['bottom']) / pix))
    Wk, Hk = -(-W // ss), -(-H // ss)
    return dict(x=Wk * pix * ss / 2, top=win['top'], bottom=win['top'] - Hk * pix * ss)


def summary(rep):
    """per measure, the drawings' mean over frames: tone agreement with EEVEE, and each check's value on each map."""
    S = {}
    T = rep.get('tones') or {}
    heads = [r for n, r in T.items() if n.startswith('head')]
    sweeps = [r for n, r in T.items() if n.startswith('sweep')]
    for label, rows in (('board', heads), ('sweep', sweeps)):
        for k in ('agree_numpy_exact', 'agree_render_exact', 'agree_numpy_colour', 'agree_render_colour'):
            v = [r[k] for r in rows if k in r]
            if v:
                S['%s_%s' % (label, k)] = round(float(np.mean(v)), 5)
        for m in ('edges', 'islands'):
            for k in ('numpy_exact', 'render_exact', 'numpy_colour', 'render_colour', 'eevee_colour'):
                v = [r.get('%s_%s' % (m, k)) for r in rows if r.get('%s_%s' % (m, k)) is not None]
                if v:
                    S['%s_%s_%s' % (label, m, k)] = round(float(np.mean(v)), 4)
    H = rep.get('hair') or {}
    for k in sorted({k for r in H.values() for k in r}):
        v = [r[k] for r in H.values() if k in r]
        S['hair_' + k] = round(float(np.mean(v)), 5)
    Bd = rep.get('body') or {}
    for k in sorted({k for r in Bd.values() for k in r if k != 'az'}):
        v = [r[k] for r in Bd.values() if k in r]
        S['body_' + k] = round(float(np.mean(v)), 5)
    return S


def _strip(path, pics, labels):
    from PIL import Image, ImageDraw
    h = max(p.shape[0] for p in pics)
    row = []
    for p in pics:
        a = p[..., 3:4] if p.shape[-1] == 4 else 1.0
        rgb = p[..., :3] * a + 0.93 * (1 - a)
        row.append(np.pad(rgb, ((0, h - p.shape[0]), (0, 8), (0, 0)), constant_values=1.0))
    img = Image.fromarray((np.clip(np.concatenate(row, 1), 0, 1) * 255 + 0.5).astype(np.uint8))
    d = ImageDraw.Draw(img)
    x = 0
    for p, lab in zip(pics, labels):
        d.text((x + 4, 4), lab, fill=(0, 0, 0))
        x += p.shape[1] + 8
    img.save(path)


def _tones_pic(path, maps, m, ss):
    from PIL import Image
    pal = np.array([[0.98, 0.93, 0.88], [0.86, 0.60, 0.58], [0.55, 0.32, 0.36], [0.80, 0.80, 0.82]])
    keys = [k for k in ('numpy_exact', 'render_exact', 'eevee_colour') if k in maps]
    row = []
    for k in keys:
        img = pal[np.where(m, np.clip(maps[k], 0, 2), 3)][ss // 2::ss, ss // 2::ss]
        row.append(np.pad(img, ((0, 0), (0, 8), (0, 0)), constant_values=1.0))
    Image.fromarray((np.concatenate(row, 1) * 255 + 0.5).astype(np.uint8)).save(path)


def main(args):
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    rep = run(args[0], opt('--out'), eevee='--no-eevee' not in args, blender=opt('--blender'))
    print(json.dumps(rep['summary'], indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
