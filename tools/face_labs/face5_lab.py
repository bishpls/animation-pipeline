"""face round 5's measures: head_construction against head_turnaround, and the mouth line's effect on the outline.

    python face5_lab.py agree OUT_DIR [BUILD]   # head_construction against head_turnaround where both show the face
                                                # outline (front half-widths per row, the chin, the V, the profile's
                                                # front edge and underside), and above head_turnaround's hair-occlusion
                                                # row the construction's outline beside the turnaround's hair-bound edge
                                                # (and ours, BUILD's bundle, bare, level): numbers (agree.json) and a
                                                # picture of the outlines (agree.png)
    python face5_lab.py mouth OUT_DIR BUILD     # the mouth line masked out (its pixels made skin) on the design and on
                                                # ours: every outline number with and without it (mouth.json)

Both references are read as the QA reads the head sheet (faceregion.design_jaw_views: calibrated on their eyes, round
their eyes' point, each at its own px per L); rows are compared on a common z grid (L from the eye line)."""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from charkit import faceregion as fr, manifest, refcheck

import jaw_lab

DZ = 0.0025                                         # the common row grid (L)
MOUTH_BOX = dict(u=0.13, z=(-0.28, -0.13))          # L round the eyes' point: where the mouth's line lies in front


def refs(spec=None):
    spec = spec or jaw_lab.spec_of()
    M = manifest.load(spec['ref']['manifest'])['references']
    return {k: M[k]['path'] for k in ('head_turnaround', 'head_construction')}


def views(path, which=('front', 'three_quarter', 'profile')):
    return fr.design_jaw_views(refcheck._load(os.path.join(fr.ROOT, path)), 0.168, -1, which=which)


def rows_front(cls, ppl):
    """a front picture's face outline per row: chin, half-widths either side (the region's extents from the chin's column,
    _extents), the hair-occlusion top (_half_widths) and the taper's measures -> dict."""
    M = fr.jaw_front(cls, ppl)
    chin = M['chin']
    z, xl, xr, hl, hr = fr._extents(cls, ppl, chin)
    top = fr._half_widths(cls, ppl, chin)[3]
    T = fr.taper_front(cls, ppl)
    return dict(chin=chin, z=z, xl=xl, xr=xr, top=top, taper=T, jaw=M)


def on_grid(z, v, zg):
    ok = np.isfinite(v)
    if ok.sum() < 2:
        return np.full(len(zg), np.nan)
    o = np.argsort(z[ok])
    out = np.interp(zg, z[ok][o], v[ok][o], left=np.nan, right=np.nan)
    return out


def profile_edge(cls, ppl, win=fr.JAW_WIN):
    """a profile picture's front edge per row (u of the first foreground pixel; facing -u) -> (z, u)."""
    fg = cls > 0
    H, W = fg.shape
    z = win['top'] - (np.arange(H) + 0.5) / ppl
    u = np.full(H, np.nan)
    for r in range(H):
        c = np.nonzero(fg[r])[0]
        if len(c):
            u[r] = (c[0] + 0.5) / ppl - win['x']
    return z, u


def agree(out, build=None):
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    P = refs()
    Vt, pt = views(P['head_turnaround'])
    Vc, pc = views(P['head_construction'], which=('front', 'profile'))
    print('ppl: turnaround %.1f, construction %.1f' % (pt, pc))
    Ft, Fc = rows_front(Vt['front']['cls'], pt), rows_front(Vc['front']['cls'], pc)
    top = Ft['top']
    zg = np.arange(0.05, -0.45, -DZ)
    g = lambda F, k: on_grid(F['z'], F[k], zg)
    tl, tr, cl, cr = g(Ft, 'xl'), g(Ft, 'xr'), g(Fc, 'xl'), g(Fc, 'xr')
    shown = (zg <= top) & (zg >= max(Ft['chin'][1], Fc['chin'][1]))
    d = np.concatenate([(cl - tl)[shown], (cr - tr)[shown]])
    d = d[np.isfinite(d)]
    wt, wc = 0.5 * (tl + tr), 0.5 * (cl + cr)
    dw = (wc - wt)[shown & np.isfinite(wc - wt)]
    R = dict(ppl=dict(turnaround=round(pt, 1), construction=round(pc, 1)),
             turnaround_top=top, rows_both=[round(float(zg[shown][0]), 4), round(float(zg[shown][-1]), 4)],
             front=dict(half_width_rms=round(float(np.sqrt(np.mean(dw ** 2))), 4),
                        half_width_mean=round(float(np.mean(dw)), 4), half_width_max=round(float(np.max(np.abs(dw))), 4),
                        per_side_rms=round(float(np.sqrt(np.mean(d ** 2))), 4),
                        chin=dict(turnaround=Ft['chin'], construction=Fc['chin'],
                                  dz=round(Fc['chin'][1] - Ft['chin'][1], 4), du=round(Fc['chin'][0] - Ft['chin'][0], 4))))
    for k in ('chin_angle', 'tip_share', 'z0', 'w0', 'w90'):
        R['front'][k] = dict(turnaround=Ft['taper'].get(k), construction=Fc['taper'].get(k))
    # the construction registered on the turnaround's chin (the rows scaled so the chins meet: its chin is lower)
    zs_c = Fc['chin'][1]
    zt_c = Ft['chin'][1]
    zr = zg * (zt_c / zs_c)                   # a row of the construction's at zg is drawn at zr in the turnaround's frame
    cl_r, cr_r = on_grid(zr, cl, zg), on_grid(zr, cr, zg)
    wc_r = 0.5 * (cl_r + cr_r)
    dwr = (wc_r - wt)[shown & np.isfinite(wc_r - wt)]
    R['front']['registered_on_chin'] = dict(scale_z=round(zt_c / zs_c, 4),
                                            half_width_rms=round(float(np.sqrt(np.mean(dwr ** 2))), 4),
                                            half_width_mean=round(float(np.mean(dwr)), 4),
                                            half_width_max=round(float(np.max(np.abs(dwr))), 4))
    # the region in view: IoU of the two face regions under the turnaround's top (a common grid, both from their chin up)
    def region_rows(F):
        return np.stack([g(F, 'xl'), g(F, 'xr')], 1)
    A, B_ = region_rows(Ft)[shown], region_rows(Fc)[shown]
    inter = np.nansum(np.minimum(A, B_)); uni = np.nansum(np.maximum(A, B_))
    R['front']['region_iou_shown'] = round(float(inter / uni), 4)
    # above the turnaround's top: its edge is the hair's; the construction's is the face's
    hid = (zg > top) & (zg <= 0.0)
    R['hidden_rows'] = [round(float(zg[hid][0]), 4), round(float(zg[hid][-1]), 4)]
    R['hidden'] = [dict(z=round(float(z_), 4), turnaround=None if not np.isfinite(a) else round(float(a), 4),
                        construction=None if not np.isfinite(b) else round(float(b), 4))
                   for z_, a, b in zip(zg[hid][::4], wt[hid][::4], wc[hid][::4])]
    # profile: the front edge and the chin's underside
    Pt, Pc = fr.jaw_profile(Vt['profile']['cls'], pt), fr.jaw_profile(Vc['profile']['cls'], pc)
    zt_, ut_ = profile_edge(Vt['profile']['cls'], pt)
    zc_, uc_ = profile_edge(Vc['profile']['cls'], pc)
    et, ec = on_grid(zt_, ut_, zg), on_grid(zc_, uc_, zg)
    band = (zg <= -0.05) & (zg >= min(Pt['chin'][1], Pc['chin'][1]))
    de = (ec - et)[band & np.isfinite(ec - et)]
    R['profile'] = dict(front_edge_rms=round(float(np.sqrt(np.mean(de ** 2))), 4), front_edge_max=round(float(
        np.max(np.abs(de))), 4), chin=dict(turnaround=Pt.get('chin'), construction=Pc.get('chin')),
        underside_deg=dict(turnaround=Pt.get('underside_deg'), construction=Pc.get('underside_deg')))
    ours = None
    if build:
        from charkit import bundle as bl, qa3d
        B = bl.load(os.path.join(build, 'bundle'))
        meshes, _ = qa3d.scene_classes(B)
        V, T, _, _ = B.skin().mesh('masked')
        iris = fr.eye_anchor(qa3d.iris_centres(B), float(B.assembly['eye_z']))
        L, ez = float(B.assembly['L']), float(B.assembly['eye_z'])
        cls = fr.board_view(fr.bare(meshes), (V, T), 0.0, np.array([0, 0, ez]), iris.mean(0), L, pt,
                            dist=fr.LEVEL_CAM['dist'])[0]
        Fo = rows_front(cls, pt)
        wo = 0.5 * (g(Fo, 'xl') + g(Fo, 'xr'))
        ours = dict(z=zg, w=wo, cls=cls)
        R['ours_hidden'] = [dict(z=round(float(z_), 4), ours=None if not np.isfinite(a) else round(float(a), 4))
                            for z_, a in zip(zg[hid][::4], wo[hid][::4])]
        dwo = (wo - wc)[hid & np.isfinite(wo - wc)]
        R['ours_vs_construction_hidden'] = dict(rms=round(float(np.sqrt(np.mean(dwo ** 2))), 4),
                                                mean=round(float(np.mean(dwo)), 4))
        dws = (wo - wt)[shown & np.isfinite(wo - wt)]
        R['ours_vs_turnaround_shown'] = dict(rms=round(float(np.sqrt(np.mean(dws ** 2))), 4),
                                             mean=round(float(np.mean(dws)), 4))
    json.dump(R, open(os.path.join(out, 'agree.json'), 'w'), indent=1, default=float)
    print(json.dumps({k: v for k, v in R.items() if k not in ('hidden', 'ours_hidden')}, indent=1, default=float))
    for row in R['hidden']:
        print('  hidden z %.3f  turnaround %s  construction %s' % (row['z'], row['turnaround'], row['construction']))
    # the picture: the front outlines (half-width by row) and the profile edges
    Wd, Hd, s = 900, 700, 1100.0
    im = Image.new('RGB', (Wd, Hd), 'white')
    d = ImageDraw.Draw(im)
    X = lambda w: Wd / 2 + w * s
    Y = lambda z: 40 - z * s
    d.line([(0, Y(top)), (Wd, Y(top))], fill=(200, 200, 200))
    d.text((6, Y(top) - 12), "head_turnaround's hair-occlusion row z %.3f" % top, fill=(120, 120, 120))
    for w_, col, name in ((wt, (200, 30, 30), 'head_turnaround'), (wc, (30, 130, 30), 'head_construction'),
                          (wc_r, (120, 200, 120), 'construction, chin-registered')) + (
                             ((ours['w'], (30, 60, 220), 'ours (bare, level)'),) if ours else ()):
        for sg in (-1, 1):
            pts = [(X(sg * w), Y(z_)) for z_, w in zip(zg, w_) if np.isfinite(w)]
            if len(pts) > 1:
                d.line(pts, fill=col, width=2)
    y0 = Hd - 20 * 5
    for i, (col, name) in enumerate((((200, 30, 30), 'head_turnaround (dashed above the occlusion row: the hair\'s edge)'),
                                     ((30, 130, 30), 'head_construction'), ((120, 200, 120), 'construction, chin-registered'),
                                     ((30, 60, 220), 'ours, bare, level'))):
        d.rectangle([10, y0 + 20 * i, 30, y0 + 20 * i + 10], fill=col)
        d.text((36, y0 + 20 * i), name, fill=(0, 0, 0))
    im.save(os.path.join(out, 'agree.png'))
    print('(%.1fs)' % (time.time() - t0))
    return R


# ------------------------------------------------------------------------------------------------------ the mouth line
def mouth_mask(cls, ppl, seeds=fr.FACE_SEEDS, win=fr.JAW_WIN, box=MOUTH_BOX):
    """the mouth's line in a front or three-quarter picture: the face region's holes (what fill_holes closes over)
    inside the mouth's box, and the ink grown round them a pixel (the region's walls) -> bool image."""
    face = fr._region(cls, seeds, ppl, win)
    holes = ndimage.binary_fill_holes(face) & ~face
    H, W = cls.shape
    z = win['top'] - (np.arange(H) + 0.5) / ppl
    u = (np.arange(W) + 0.5) / ppl - win['x']
    inbox = (np.abs(u)[None, :] < box['u']) & ((z > box['z'][0]) & (z < box['z'][1]))[:, None]
    lab, n = ndimage.label(holes)
    keep = np.zeros_like(holes)
    for i in range(1, n + 1):
        m = lab == i
        if (m & inbox).sum() >= 0.5 * m.sum():
            keep |= m
    return keep


def unmouthed(cls, ppl):
    m = mouth_mask(cls, ppl)
    out = cls.copy()
    out[m] = 1
    return out, int(m.sum())


def mouth(out, build):
    os.makedirs(out, exist_ok=True)
    spec = jaw_lab.spec_of()
    D, ppl, Dc, az = fr.design_jaw(spec, 0.168)
    import taper_lab
    meshes, skin, iris, ez, L, _ = taper_lab.scene(build=build)
    real = fr.board_view
    counts = {}

    def masked_view(*a, **k):
        cls, depth = real(*a, **k)
        c2, n = unmouthed(cls, ppl)
        counts.setdefault('ours', []).append(n)
        return c2, depth

    res = {}
    for tag in ('as is', 'mouth masked'):
        if tag == 'mouth masked':
            fr.board_view = masked_view
            Dv = {}
            for vn, cls in Dc.items():
                if vn == 'profile':
                    continue
                c2, n = unmouthed(cls, ppl)
                counts.setdefault('design', []).append(n)
                Dv[vn] = c2
            D2 = {vn: fr.jaw_front(Dv[vn], ppl) for vn in Dv}
            D2['profile'] = D['profile']
            D2['front']['taper'] = fr.taper_front(Dv['front'], ppl)
            D2['three_quarter']['taper'] = fr.tq_jaw(Dv['three_quarter'], ppl, -1)
            Duse = D2
            masks = {vn: mouth_mask(Dc[vn], ppl) for vn in Dv}
        else:
            Duse = D
        try:
            O = fr.ours_jaw(meshes, skin, iris, ez, L, ppl, az, Duse['front'].get('chin', (0, None))[1],
                            Duse['front']['taper']['z0'], design_tq_top=Duse['three_quarter']['taper'].get('top'))[0]
        finally:
            fr.board_view = real
        C = fr.jaw_compare(Duse, O, ppl)
        C.update(fr.taper_checks(Duse, O))
        res[tag] = dict(checks={k: dict(value=v.get('value'), level=v.get('level'), status=v['status'])
                                for k, v in C.items()},
                        design=dict(z0=Duse['front']['taper']['z0'], w0=Duse['front']['taper']['w0'],
                                    chin=Duse['front']['taper']['chin'], top=Duse['front']['taper'].get('top'),
                                    chin_angle=Duse['front']['taper'].get('chin_angle'),
                                    tip=Duse['front']['taper'].get('tip_share'),
                                    r=[None if not np.isfinite(x) else round(float(x), 5) for x in Duse['front']['taper']['r']],
                                    tq_top=Duse['three_quarter']['taper'].get('top'),
                                    tq_hollow=Duse['three_quarter']['taper'].get('hollow')),
                        ours=dict(z0=O['front']['taper']['z0'], w0=O['front']['taper']['w0'],
                                  chin_angle=O['front']['taper'].get('chin_angle'),
                                  level_chin_angle=O['front']['taper_level'].get('chin_angle'),
                                  r=[None if not np.isfinite(x) else round(float(x), 5) for x in O['front']['taper']['r']]))
    moved = {}
    for k in res['as is']['checks']:
        a, b = res['as is']['checks'][k], res['mouth masked']['checks'].get(k, {})
        if (a.get('value'), a.get('level')) != (b.get('value'), b.get('level')):
            moved[k] = [a, b]
    dr = np.array([np.nan if x is None else x for x in res['mouth masked']['design']['r']]) - \
        np.array([np.nan if x is None else x for x in res['as is']['design']['r']])
    R = dict(masked_px=counts, moved=moved, design_r_maxdiff=float(np.nanmax(np.abs(dr))), runs=res)
    json.dump(R, open(os.path.join(out, 'mouth.json'), 'w'), indent=1, default=float)
    print('masked pixels', {k: v for k, v in counts.items()})
    print('design taper curve, max |change|: %.5f' % R['design_r_maxdiff'])
    print('checks that moved: %d' % len(moved))
    for k, (a, b) in moved.items():
        print('  %-24s %s -> %s' % (k, a, b))
    for k in ('z0', 'w0', 'chin', 'top', 'chin_angle', 'tip', 'tq_top', 'tq_hollow'):
        print('  design %-10s %s -> %s' % (k, res['as is']['design'][k], res['mouth masked']['design'][k]))
    # a picture: the masks on the design's front and three-quarter
    tiles = []
    for vn in ('front', 'three_quarter'):
        im = jaw_lab.tint(Dc[vn])
        im[masks[vn]] = (255, 0, 255)
        tiles.append(Image.fromarray(im))
    w, h = tiles[0].size
    S = Image.new('RGB', (2 * w + 8, h), 'white')
    for i, t in enumerate(tiles):
        S.paste(t, (i * (w + 8), 0))
    S.save(os.path.join(out, 'mouth_masks.png'))
    return R


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'agree':
        agree(a[1], a[2] if len(a) > 2 else None)
    elif a[0] == 'mouth':
        mouth(a[1], a[2])


def mouth_fit(out):
    """the same test on the geometry's own reading of the design (charkit.geom.headfit.contours, via
    refcheck.face_design): the sheet's mouth line painted over with the skin round it; the front half-width w(z) the head
    is fitted to, and the other contours, before and after -> mouth_fit.json."""
    from charkit.geom import headfit, hull
    os.makedirs(out, exist_ok=True)
    P = refs()
    rgb = refcheck._load(os.path.join(fr.ROOT, P['head_turnaround']))
    rgb0, _ = refcheck.without_guides(np.asarray(rgb, float))
    Vw, info = hull.views_from_heads(rgb0, 0.168, -1, floor=fr.JAW_WIN['bottom'] - 0.05)
    Hd = refcheck.detect_heads(rgb0, 0.168, -1)['heads']
    Dv, ppl = fr.design_jaw_views(rgb, 0.168, -1)
    painted = np.asarray(rgb, float).copy()
    n = 0
    for vn in ('front', 'three_quarter'):
        v = Vw[vn]
        ex = float(np.mean([e[0] for e in sorted(Hd[vn]['eyes'])]))
        m = ndimage.binary_dilation(mouth_mask(Dv[vn]['cls'], ppl), iterations=2)
        r, c = np.nonzero(m)
        R = np.round(v.eye_y - fr.JAW_WIN['top'] * v.ppl + r).astype(int)
        C = np.round(ex - fr.JAW_WIN['x'] * v.ppl + c).astype(int)
        ring = ndimage.binary_dilation(m, iterations=4) & ~m & (Dv[vn]['cls'] == 1)
        rr, cc = np.nonzero(ring)
        skin = np.median(painted[np.round(v.eye_y - fr.JAW_WIN['top'] * v.ppl + rr).astype(int),
                                 np.round(ex - fr.JAW_WIN['x'] * v.ppl + cc).astype(int)], 0)
        painted[R, C] = skin
        n += len(r)
    Image.fromarray((np.clip(painted, 0, 1) * 255).astype(np.uint8) if painted.max() <= 1.0 else
                    painted.astype(np.uint8)).save(os.path.join(out, 'painted.png'))
    A, B_ = headfit.contours(np.asarray(rgb, float), 0.168), headfit.contours(painted, 0.168)
    res = dict(painted_px=n)
    for k in ('w', 'mid', 'lead3'):
        d = np.abs(np.asarray(A[k]) - np.asarray(B_[k]))
        res[k] = dict(max=None if not np.isfinite(d).any() else round(float(np.nanmax(d)), 5),
                      rows=int(np.isfinite(d).sum()))
    for k in ('chin', 'nose_z'):
        res[k] = [A[k], B_[k]]
    json.dump(res, open(os.path.join(out, 'mouth_fit.json'), 'w'), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))
    return res


if __name__ == '__main__' and sys.argv[1] == 'mouth_fit':
    mouth_fit(sys.argv[2])
