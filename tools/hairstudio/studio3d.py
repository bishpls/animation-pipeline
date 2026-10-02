"""The studio's 3D-native tools (Michael, 2026-10-02: "you probably need your tools and measurements to be natively
3-dimensional"): views and measures of the hair as a 3D object, not 2D comparisons with the drawing.

  slices      horizontal cross-sections through the hair (crown, eyes, mouth, chin, under the chin, the hem), seen
              from above: each lock its own colour, the head's own section grey; thickness, layer order, gaps, volume
  turntable   the hair (lock map and shaded) from 12 azimuths: does it hold from every side?
  lockstats   per group from the locks' own centrelines: count, length (L), width (L), thickness/width, curl (mean
              curvature, 1/L), wave (RMS sideways deviation from the lock's chord, L)
  coverage    across the turntable: holes inside the hair's filled outline (gaps one can see through), share

    python studio3d.py BUNDLE TAG          -> studio/TAG_3d.png, studio/TAG_3d.json
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import studio as S                                                   # noqa: E402

HEIGHTS = (('crown', 0.45), ('eyes', 0.0), ('mouth', -0.25), ('chin', -0.36), ('under chin', -0.5), ('hem', -0.68))   # L from the eye line


def section(V, T, z):
    """segments where the triangles (V, T) cross the plane at height z -> (n, 2, 2) xy."""
    a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    out = []
    for p, q, r in ((a, b, c), (b, c, a), (c, a, b)):
        pass
    za, zb, zc = a[:, 2] - z, b[:, 2] - z, c[:, 2] - z
    segs = []
    for (P, zP), (Q, zQ), (R, zR) in (((a, za), (b, zb), (c, zc)),):
        pass
    pts = []
    for (P, zP, Q, zQ) in ((a, za, b, zb), (b, zb, c, zc), (c, zc, a, za)):
        m = (zP * zQ) < 0
        t = np.where(m, zP / np.where(m, zP - zQ, 1), 0)
        X = P + (Q - P) * t[:, None]
        pts.append((m, X[:, :2]))
    sel = (pts[0][0].astype(int) + pts[1][0] + pts[2][0]) == 2
    segs = []
    for i in np.where(sel)[0]:
        e = [pts[k][1][i] for k in range(3) if pts[k][0][i]]
        segs.append(e)
    return np.array(segs) if segs else np.zeros((0, 2, 2))


def slices(B, L, cz, out_hw=420):
    from PIL import Image, ImageDraw
    hair = [o for o in B.objects() if o.group == 'hair' and o.has('eval')]
    skin = [o for o in B.objects() if o.group == 'skin' and o.has('eval')]
    tiles, stats = [], {}
    rng = np.random.default_rng(3)
    for name, dz in HEIGHTS:
        z = cz + dz * L
        im = Image.new('RGB', (out_hw, out_hw), (246, 246, 248))
        d = ImageDraw.Draw(im)
        sc = out_hw / (1.0 * L * 1.7)
        to = lambda p: (out_hw / 2 + p[0] * sc, out_hw / 2 + (p[1] - 0.02) * sc)
        for o in skin:
            V, T, _, _ = o.mesh('eval')
            for sgm in section(V, T, z):
                d.line([to(sgm[0]), to(sgm[1])], fill=(150, 150, 155), width=1)
        n_seg = 0
        for o in hair:
            V, T, _, poly = o.mesh('eval')
            cl = o.a('eval', 'clump')
            if cl is None or len(cl) <= poly.max():
                cols = {0: tuple(int(x) for x in rng.integers(60, 220, 3))}
                lab = np.zeros(len(T), int)
            else:
                lab = cl[poly]
                cols = {k: tuple(int(x) for x in np.random.default_rng(int(k)).integers(40, 230, 3)) for k in np.unique(lab)}
            a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
            zs = np.stack([a[:, 2], b[:, 2], c[:, 2]], 1)
            hit = (zs.min(1) < z) & (zs.max(1) > z)
            if not hit.any():
                continue
            segs = section(V, T[hit], z)
            labs = lab[hit]
            # (section() keeps triangles in order; map each kept segment back to its label)
            k_ = 0
            for i, t in enumerate(np.where(hit)[0]):
                pass
            for sgm, lb in zip(segs, labs[:len(segs)]):
                d.line([to(sgm[0]), to(sgm[1])], fill=cols.get(lb, (90, 90, 90)), width=3)
            n_seg += len(segs)
        d.text((6, 4), '%s (%+.2f L)' % (name, dz), fill=(40, 40, 40))
        tiles.append(np.asarray(im))
        stats[name] = n_seg
    return np.concatenate(tiles, 1), stats


SECTORS = (('front', 180), ('side', 90), ('back', 0))


def volume_profile(B, L, cz, objs=None, step=0.05):
    """the hair's outer radius from the head's vertical axis per height (L, from 0.5 above the eye line to 0.9 under),
    per sector (front / side (both) / back, +-30 deg), in L: the volume as a 3D shape."""
    hair = objs or [o for o in B.objects() if o.group == 'hair' and o.has('eval') and 'bun' not in o.name
                    and 'ahoge' not in o.name and 'fly' not in o.name]
    V = np.concatenate([o.a('eval', 'V') for o in hair])
    ax = np.array(B.assembly['centre'], float)
    x, y, z = V[:, 0] - ax[0], V[:, 1] - ax[1], (V[:, 2] - cz) / L
    rad = np.hypot(x, y) / L
    az = np.degrees(np.arctan2(x, y))
    hs = np.arange(0.5, -0.9, -step)
    prof = {}
    for name, a0 in SECTORS:
        d = np.abs(((np.abs(az) - a0) + 180) % 360 - 180) if name == 'side' else np.abs(((az - a0) + 180) % 360 - 180)
        sel = d < 30
        row = []
        for h in hs:
            m = sel & (z <= h) & (z > h - step)
            row.append(round(float(rad[m].max()), 3) if m.any() else 0.0)
        prof[name] = row
    return dict(heights=[round(float(h), 3) for h in hs], **prof)


def profile_chart(ours, target, path, W=520, H=360):
    """the volume profiles as a chart: height down, radius across; target dashed grey, ours coloured per sector."""
    from PIL import Image, ImageDraw
    im = Image.new('RGB', (W, H), (250, 250, 252))
    d = ImageDraw.Draw(im)
    hs = ours['heights']
    rmax = max(max(max(ours[k]) for k, _ in SECTORS), max(max(target[k]) for k, _ in SECTORS), 0.1)
    X = lambda r: 40 + r / rmax * (W - 60)
    Y = lambda h: 20 + (hs[0] - h) / (hs[0] - hs[-1]) * (H - 40)
    cols = {'front': (220, 70, 60), 'side': (60, 140, 220), 'back': (70, 170, 90)}
    for k, _ in SECTORS:
        pts_t = [(X(r), Y(h)) for r, h in zip(target[k], hs) if r > 0]
        for a, b in zip(pts_t, pts_t[1:]):
            d.line([a, b], fill=(160, 160, 165), width=2)
        pts = [(X(r), Y(h)) for r, h in zip(ours[k], hs) if r > 0]
        for a, b in zip(pts, pts[1:]):
            d.line([a, b], fill=cols[k], width=3)
        if pts:
            d.text((pts[-1][0] + 4, pts[-1][1] - 6), k, fill=cols[k])
    d.line([(X(0), Y(0)), (W - 10, Y(0))], fill=(200, 200, 205))
    d.text((6, Y(0) - 6), 'eyes', fill=(120, 120, 120))
    d.text((W - 210, 4), 'grey: the hull (the drawing\'s volume)', fill=(120, 120, 120))
    im.save(path)


def crown_volume(ours, target):
    """above the eye line: our outer radius minus the hull's, mean over sectors and heights (L); negative = a helmet."""
    d = []
    for k, _ in SECTORS:
        for h, a, b in zip(ours['heights'], ours[k], target[k]):
            if h > 0 and a > 0 and b > 0:
                d.append(a - b)
    return round(float(np.mean(d)), 4) if d else 0.0


def edge_on(B, az, thr=0.35):
    """the share of visible hair pixels whose surface is seen nearly edge-on (|n . view| < thr) from azimuth az (0, 90,
    180: the sign of the view doesn't matter): thin locks seen side-on read as shards."""
    from charkit.detailqa import _Window
    L = float(B.assembly['L']); c = np.array(B.assembly['centre'], float); c[2] = float(B.assembly['eye_z'])
    fr = _Window(c, az, 1.0 * L, 1.1 * L, L / 300.0)
    items, normals, is_hair = [], [], []
    for o in B.objects():
        variant = 'masked' if o.group == 'skin' and o.has('masked') else 'eval'
        if not o.has(variant) or o.group == 'accessory':
            continue
        V, T, _, _ = o.mesh(variant)
        items.append((V, T, np.zeros(len(T), int), np.zeros(len(T), bool)))
        n = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
        normals.append(n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12))
        is_hair.append(o.group == 'hair' and 'bun' not in o.name)
    zb, lab, mi, ti, bc = fr.zbuffer(items, az, ids=True)
    a = np.radians(az)
    d = np.array([np.sin(a), -np.cos(a), 0.0])
    tot = edge = 0
    for j, (nrm, h) in enumerate(zip(normals, is_hair)):
        if not h:
            continue
        px = mi == j
        if not px.any():
            continue
        dots = np.abs(nrm[ti[px]] @ d)
        tot += px.sum(); edge += (dots < thr).sum()
    return round(float(edge / max(tot, 1)), 3)


def tips(locks, cz):
    """the lock tips' heights (L under the eye line, excluding the bangs): their spread (std) and how many lie in each
    0.15 L band from the eyes down; a cloud has tips at many heights, a curtain only at its hem."""
    L = locks['L']
    hs = [(lk['P'][-1][2] - cz) / L for lk in locks['locks'] if lk['group'] not in (6,) and lk.get('P')]
    if not hs:
        return {}
    hs = np.array(hs)
    bands = np.histogram(hs, bins=np.arange(-1.0, 0.31, 0.15))[0]
    return dict(spread=round(float(hs.std()), 3), bands=bands.tolist())


def bun_visibility(B):
    """the buns' visible pixels in the front and back lock maps (S.lockmap's object ids; names via S.NAMES)."""
    tot = 0
    for az in (0.0, 180.0):
        ids = S.lockmap(B, az)
        bun_ids = [k for k, n in S.NAMES.items() if 'bun' in n]
        tot += int(np.isin(ids, bun_ids).sum())
    return tot


def overlap(locks):
    """per group: each lock's widest over the angular gap it owns (width / (span x radius)); under 1 = gaps
    between neighbours (stringy), over 1 = overlapping (full)."""
    C = np.array(locks['centre'])
    by = {}
    for lk in locks['locks']:
        if not lk.get('span') or not lk.get('width_max'):
            continue
        P = np.array(lk['P'])
        r = np.linalg.norm(P[len(P) // 3] - C) * np.sin(np.radians(70))
        by.setdefault(lk['group'], []).append(lk['width_max'] / max(np.radians(lk['span']) * r, 1e-9))
    names = {1: 'upper', 2: 'lower', 3: 'tier2', 4: 'side_L', 5: 'side_R', 6: 'bangs', 7: 'outer'}
    return {names.get(k, str(k)): round(float(np.median(v)), 2) for k, v in sorted(by.items())}


def profile_error(ours, target):
    e = []
    for k, _ in SECTORS:
        for a, b in zip(ours[k], target[k]):
            if a > 0 or b > 0:
                e.append(abs(a - b))
    return round(float(np.mean(e)), 4)


def body(B, locks):
    """hair "body" per group, from each lock's centreline against the skin (scipy cKDTree on the skin's vertices):
      lift    mean standoff over the first 30% of the length (L): roots rising off the scalp
      arch    the lock's largest standoff (L)
      relief  the spread of neighbouring locks' standoffs at matched points along them (L): ridges and valleys
    """
    from scipy.spatial import cKDTree
    sk = [o for o in B.objects() if o.group == 'skin' and o.has('eval')][0]
    tree = cKDTree(sk.a('eval', 'V'))
    L = locks['L']
    by = {}
    for lk in locks['locks']:
        P = np.array(lk['P'])
        if len(P) < 6:
            continue
        d, _ = tree.query(P)
        n = len(P)
        by.setdefault(lk['group'], []).append(np.interp(np.linspace(0, 1, 20), np.linspace(0, 1, n), d) / L)
    names = {1: 'upper', 2: 'lower', 3: 'tier2', 4: 'side_L', 5: 'side_R', 6: 'bangs'}
    out = {}
    for g, rows in sorted(by.items()):
        A = np.array(rows)
        out[names.get(g, str(g))] = dict(lift=round(float(A[:, :6].mean()), 3), arch=round(float(np.median(A.max(1))), 3),
                                         relief=round(float(np.median(A.std(0))), 3))
    return out


def lockstats(locks):
    L = locks['L']
    by = {}
    for lk in locks['locks']:
        P = np.array(lk['P'])
        if len(P) < 4:
            continue
        seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
        length = seg.sum()
        T = np.diff(P, axis=0) / np.maximum(seg[:, None], 1e-9)
        ang = np.arccos(np.clip(np.sum(T[1:] * T[:-1], 1), -1, 1))
        curv = float(np.sum(ang) / max(length, 1e-9))                     # mean turning per unit length (1/m)
        chord = P[-1] - P[0]
        cn = chord / max(np.linalg.norm(chord), 1e-9)
        rel = P - P[0]
        dev = rel - np.outer(rel @ cn, cn)
        wave = float(np.sqrt(np.mean(np.sum(dev ** 2, 1))))
        g = by.setdefault(lk['group'], dict(n=0, length=[], width=[], ratio=[], curl=[], wave=[], tip=[], span=[]))
        if lk.get('wprof'):
            g['tip'].append(lk['wprof'][9])
        if lk.get('span'):
            g['span'].append(lk['span'])
        g['n'] += 1
        g['length'].append(length / L); g['width'].append(lk.get('width', 0) / L)
        g['ratio'].append(lk.get('thick', 0) / max(lk.get('width', 1e-9), 1e-9))
        g['curl'].append(curv * L); g['wave'].append(wave / L)
    names = {1: 'upper', 2: 'lower', 3: 'tier2', 4: 'side_L', 5: 'side_R', 6: 'bangs'}
    cv = lambda a: round(float(np.std(a) / max(np.mean(a), 1e-9)), 3) if len(a) > 1 else 0.0
    return {names.get(k, str(k)): dict(n=v['n'], **{m: round(float(np.median(v[m])), 3)
                                                     for m in ('length', 'width', 'ratio', 'curl', 'wave')},
                                         blade=round(float(np.median(v['ratio'])), 3),
                                         tip_sharp=round(float(np.median(v['tip'])), 3) if v['tip'] else None,
                                         width_cv=cv(v['width']), length_cv=cv(v['length']),
                                         spacing_cv=cv(v['span']) if v['span'] else None)
            for k, v in sorted(by.items())}


BALD = []


def turntable(B, n=12):
    from charkit import palette
    palette.activate_spec(B.spec)
    rows_s, rows_l, gaps = [], [], []
    from scipy import ndimage
    for az in np.linspace(0, 360, n, endpoint=False):
        rgb, hm = S.draw_ours(B, float(az), hide_groups=('accessory',))
        ids = S.lockmap(B, float(az))
        crop, mp = S.pv.head_crop(rgb, S.EYE_ROW, S.P, want_map=True)
        idc = S._apply_ids(ids, mp, crop.shape[:2])
        h = idc >= 0
        filled = ndimage.binary_fill_holes(ndimage.binary_closing(h, iterations=3))
        gaps.append(float((filled & ~h & (idc != -2) & (idc != -3)).sum() / max(filled.sum(), 1)))
        top = S.EYE_ROW - int(0.3 * S.P)                            # above the forehead line
        BALD.append(int(((idc[:top] == -3)).sum()))
        rows_s.append(crop[::2, ::2]); rows_l.append(S.colour_ids(idc)[::2, ::2])
    return np.concatenate([np.concatenate(rows_s, 1), np.concatenate(rows_l, 1)], 0), gaps


def main(bundle, tag):
    from PIL import Image
    from charkit import bundle as bl
    B = bl.load(bundle)
    L = float(B.assembly['L'])
    cz = float(B.assembly['eye_z'])
    sl, sstats = slices(B, L, cz)
    tt, gaps = turntable(B)
    W = max(sl.shape[1], tt.shape[1])
    pad = lambda a: np.pad(a, ((0, 0), (0, W - a.shape[1]), (0, 0)), constant_values=255)
    img = np.concatenate([pad(tt), pad(sl.astype(float) / 255.0)], 0) if sl.dtype != float else None
    tt8 = (np.clip(tt, 0, 1) * 255).astype(np.uint8)
    W = max(sl.shape[1], tt8.shape[1])
    pad8 = lambda a: np.pad(a, ((0, 0), (0, W - a.shape[1]), (0, 0)), constant_values=255)
    Image.fromarray(np.concatenate([pad8(tt8), pad8(sl)], 0)).save(os.path.join(S.OUT, tag + '_3d.png'))
    HB = bl.load(os.environ.get('HAIRSTUDIO_BASE', os.path.expanduser('~/animation-pipeline-3d/charkit/out/hairbase/bundle')))
    target = volume_profile(HB, L, cz)
    ours = volume_profile(B, L, cz)
    profile_chart(ours, target, os.path.join(S.OUT, tag + '_volume.png'))
    lp = os.path.join(bundle, 'locks.json')
    ls = lockstats(json.load(open(lp))) if os.path.exists(lp) else {}
    bd = body(B, json.load(open(lp))) if os.path.exists(lp) else {}
    lk_ = json.load(open(lp)) if os.path.exists(lp) else None
    bv = bun_visibility(B)
    bv_ref = bun_visibility(HB)
    rep = dict(edge_on={v: edge_on(B, az) for v, az in (('front', 0.0), ('profile', 90.0), ('back', 180.0))}, bald_px=int(np.mean(BALD)) if BALD else 0, bun_visible=round(bv / max(bv_ref, 1), 3), tips=tips(lk_, cz) if lk_ else {}, crown_volume=crown_volume(ours, target), overlap=overlap(json.load(open(lp))) if os.path.exists(lp) else {},
               body=bd, volume_error=profile_error(ours, target), volume=ours, lockstats=ls,
               gaps=dict(mean=round(float(np.mean(gaps)), 4), max=round(float(np.max(gaps)), 4)), slice_segments=sstats)
    json.dump(rep, open(os.path.join(S.OUT, tag + '_3d.json'), 'w'), indent=1)
    print(json.dumps(rep))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
