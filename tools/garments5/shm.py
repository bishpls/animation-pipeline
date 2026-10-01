"""The body's shoulder measured against the base body reference (base_body_turnaround: the body in a plain sleeveless
bodysuit, the authority for the bare shoulder; Michael 2026-10-01). Our skin alone (garments off) z-buffered on the
design's grid, its triangles labelled torso or arm (the nearest part of the build's geom/body_code.npz), against the
base body sheet's figures (neckm.bb_views: the sheet on the design's grid, each view shifted onto the turnaround's head).

Front and back, per side (lengths in L, z from the eye line, x out from the view's centre):
  top        the upper silhouette z_top(|x|) over |x| 0.12-0.80 where the reference's top pixel isn't hair: ours less
             the reference's, per band and rms
  outer      the outer silhouette x_out(z) over z -0.55..-1.30 (the deltoid then the upper arm), where the reference's
             outermost pixel isn't hair: ours less the reference's
  point      the shoulder point: the point of the outer contour (top line, then outer edge) farthest from the chord from
             (0.15, z_top(0.15)) to (x_out(-1.25), -1.25)
  axilla     the armpit: the highest row where the arm parts from the torso (a background gap between them)
Profile: the arm (ours: arm-labelled triangles; the reference: its skin under the bodysuit's armhole) front and back
edges per row over z -0.62..-1.25, and the upper silhouette's height over the arm's columns.
Three-quarter: the near side's outer silhouette as front's (reported).

    python tools/garments5/shm.py BUILD.. [--png OUT.png] [--json OUT.json]
"""
import sys, os, json
sys.path.insert(0, '.')
import numpy as np

from charkit import bundle, qa3d, bodyqa, sheetqa
from charkit.faceqa import zbuffer

BB = 'charkit/refs/clawd/gen/base_body_turnaround.png'
SCALE = 1.0011                 # the manifest's refcheck: the figures' heights (turnaround over the sheet)
VIEWS = ('front', 'three_quarter', 'profile', 'back')
ARM, TORSO, HEAD = 20, 1, 2     # our labels
CUT = -0.52                    # L: the neck cut (code_base.CUT): ours above it is the head
TOP_X = (0.12, 0.80)
OUT_Z = (-0.55, -1.30)
BANDS = ((0.12, 0.30), (0.30, 0.45), (0.45, 0.60), (0.60, 0.80))
_bb = {}


def bb_views(D):
    key = id(D)
    if key in _bb:
        return _bb[key]
    ctx = D.sheet_context()
    from PIL import Image
    rgb = np.asarray(Image.open(BB).convert('RGB')).astype(float) / 255.0
    if ctx['rgb'].max() > 1.5:
        rgb = rgb * 255.0
    ex = ctx['eye_x']
    facing = (D.ref().get('body_sheet') or {}).get('facing', -1)
    ppl = ctx['ppl'] / SCALE
    Dbb = sheetqa.detect_figures(rgb, ppl=ppl, eye_x=ex, facing=facing)
    dvb = bodyqa.design_views(rgb, Dbb, ppl)
    dv = D.design_views()
    out = {}
    for v in dvb:
        if v not in dv:
            continue
        t, c = dv[v]['fg'], dvb[v]['fg']
        H, W = min(t.shape[0], c.shape[0]), min(t.shape[1], c.shape[1])
        t, c = t[:H, :W], c[:H, :W]
        rows = int(round((bodyqa.WIN['top'] - (-0.40)) * ctx['ppl']))
        best = (-1, 0, 0)
        for dy in range(-8, 9):
            for dx in range(-8, 9):
                s = np.roll(np.roll(c, dy, 0), dx, 1)
                a, b = t[:rows], s[:rows]
                iou = (a & b).sum() / max(1, (a | b).sum())
                if iou > best[0]:
                    best = (iou, dy, dx)
        sh = lambda m: np.roll(np.roll(m[:H, :W], best[1], 0), best[2], 1)
        out[v] = dict(fg=sh(dvb[v]['fg']), cls=sh(dvb[v]['cls']), shift=best[1:], head_iou=round(float(best[0]), 4))
    _bb[key] = out
    return out


def arm_labels(B, build, V):
    """per skin vertex: arm (True) or not, by the nearest point of the build's body code (hull frame, mapped to world
    by the eyes)."""
    from scipy.spatial import cKDTree
    p = os.path.join(build, 'geom', 'body_code.npz')
    Z = np.load(p)
    L = float(B.assembly['L'])
    iris = np.array(qa3d.iris_centres(B))
    O = iris.mean(0) - L * np.asarray(Z['eyes'], float).mean(0)
    pts, lab = [], []
    for k in Z.files:
        if not k.endswith('_P'):
            continue
        P = np.asarray(Z[k], float).reshape(-1, 3) * L + O
        is_arm = k.startswith(('arm_', 'hand_', 'shoulder_'))
        pts.append(P); lab.append(np.full(len(P), is_arm))
    tree = cKDTree(np.concatenate(pts))
    lab = np.concatenate(lab)
    _, i = tree.query(V)
    head = (V[:, 2] - O[2]) / L > CUT + 0.01
    return np.where(head, HEAD, np.where(lab[i], ARM, TORSO))


def ours_views(B, build, D):
    ctx = D.sheet_context()
    V, T, _, _ = B.skin().mesh('eval')
    V, T = np.asarray(V, float), np.asarray(T)
    vl = arm_labels(B, build, V)
    tl = np.where((vl[T] == HEAD).sum(1) >= 2, HEAD, np.where((vl[T] == ARM).sum(1) >= 2, ARM, TORSO))
    meshes = [(V, T, tl)]
    iris = np.array(qa3d.iris_centres(B))
    az = bodyqa.azimuths(ctx['az3'])
    out = {}
    for v in VIEWS:
        org = bodyqa.origin(v, az[v], iris, B.assembly['centre'])
        out[v] = zbuffer(meshes, az[v], org, B.assembly['L'], 1.0 / ctx['ppl'], bodyqa.WIN)[1]
    return out


def rc(z, x, ppl):
    W = bodyqa.WIN
    return int(round((W['top'] - z) * ppl - 0.5)), int(round((x + W['x']) * ppl - 0.5))


def xz(r, c, ppl):
    W = bodyqa.WIN
    return (c + 0.5) / ppl - W['x'], W['top'] - (r + 0.5) / ppl


def top_line(fg, occ, ppl, side, z0=-0.42, z1=-1.0, loose=False):
    """per column over |x| TOP_X on a side (+1 the image's right): z of the first body pixel (figure, not `occ`: the
    hair (the reference's), the head (ours)) under z0, NaN where nothing is above z1 or the pixel above it isn't
    background (the hair lying on the shoulder hides its top; loose: hair above allowed)."""
    xs = np.arange(TOP_X[0], TOP_X[1], 1.0 / ppl)
    out = []
    r0, r1 = rc(z0, 0, ppl)[0], rc(z1, 0, ppl)[0]
    for x in xs:
        c = rc(0, side * x, ppl)[1]
        body = fg[r0:r1, c] & ~occ[r0:r1, c]
        k = np.nonzero(body)[0]
        if not len(k):
            out.append(np.nan); continue
        r = r0 + k[0]
        above = fg[r - 1, c] and not (loose and occ[r - 1, c])
        if not above and k[0] + 3 <= len(body) and not body[k[0]:k[0] + 3].all():
            above = True                                # (a sliver, not the shoulder's top)
        if above:
            out.append(np.nan); continue
        out.append(xz(r, c, ppl)[1])
    return xs, np.array(out)


def outer_edge(fg, occ, ppl, side):
    """per row over OUT_Z: |x| of the outermost figure pixel on a side, NaN where it's `occ` (hair, head)."""
    zs = np.arange(OUT_Z[0], OUT_Z[1], -1.0 / ppl)
    c0 = rc(0, 0, ppl)[1]
    out = []
    for z in zs:
        r = rc(z, 0, ppl)[0]
        row = fg[r]
        cs = np.nonzero(row[c0:])[0] + c0 if side > 0 else np.nonzero(row[:c0 + 1])[0]
        if not len(cs):
            out.append(np.nan); continue
        c = cs.max() if side > 0 else cs.min()
        if occ[r, c]:
            out.append(np.nan); continue
        out.append(abs(xz(r, c, ppl)[0]))
    return zs, np.array(out)


def axilla(fg, ppl, side, z_lo=-1.6):
    """the highest row (z) under the shoulder where, going out from the midline, the figure has a gap (the arm parted
    from the torso) -> z or None."""
    c0 = rc(0, 0, ppl)[1]
    for z in np.arange(-0.6, z_lo, -1.0 / ppl):
        r = rc(z, 0, ppl)[0]
        row = fg[r, c0:] if side > 0 else fg[r, :c0 + 1][::-1]
        k = np.nonzero(row)[0]
        if not len(k):
            continue
        run = np.nonzero(~row[k[0]:k[-1] + 1])[0]
        if len(run) >= 2:
            return round(float(z), 4)
    return None


def shoulder_point(xs, zt, zs, xo):
    """the point of the outer contour farthest from the chord (0.15, z_top) -> (x_out at -1.25, -1.25)."""
    P = [(x, z) for x, z in zip(xs, zt) if np.isfinite(z)] + [(x, z) for z, x in zip(zs, xo) if np.isfinite(x)]
    if len(P) < 10:
        return None
    P = np.array(P)
    i0 = np.argmin(np.abs(xs - 0.15))
    a = np.array([xs[i0], zt[i0]]) if np.isfinite(zt[i0]) else P[0]
    j = np.nanargmin(np.abs(zs + 1.25))
    b = np.array([xo[j], zs[j]]) if np.isfinite(xo[j]) else P[-1]
    d = b - a
    n = np.array([d[1], -d[0]]) / max(1e-9, np.hypot(*d))
    s = (P - a) @ n
    k = int(np.argmax(np.abs(s)))
    return [round(float(P[k, 0]), 4), round(float(P[k, 1]), 4)]


def ref_body(fg, cls):
    """the reference's body pixels: the figure less its hair, opened 3x3 (the hair's outline fringe, absorbed into the
    neighbouring class, read as body under the hair's edge) and kept to the components of 2000 px or more."""
    from scipy import ndimage
    m = ndimage.binary_opening(fg & (cls != bodyqa.CLASS['hair']), np.ones((3, 3)))
    lab, n = ndimage.label(m)
    if n:
        sz = ndimage.sum(m, lab, range(1, n + 1))
        m = np.isin(lab, 1 + np.nonzero(sz >= 2000)[0])
    return m


def station(a, v, a0, h=0.02):
    """the median of v over a within h of a0 (None: nothing there)."""
    m = (np.abs(np.asarray(a) - a0) <= h) & np.isfinite(v)
    return round(float(np.median(v[m])), 3) if m.any() else None


def stats(o, r, ok=None):
    d = o - r
    use = np.isfinite(d) if ok is None else (np.isfinite(d) & ok)
    if not use.any():
        return dict(n=0)
    return dict(n=int(use.sum()), rms=round(float(np.sqrt(np.mean(d[use] ** 2))), 4),
                med=round(float(np.median(d[use])), 4), worst=round(float(d[use][np.argmax(np.abs(d[use]))]), 4))


def profile_arm(lab, ppl, arm_mask):
    """per row over z -0.62..-1.25: the arm region's front (min x) and back (max x) -> (zs, front, back)."""
    zs = np.arange(-0.62, -1.25, -1.0 / ppl)
    f, b = [], []
    for z in zs:
        r = rc(z, 0, ppl)[0]
        cs = np.nonzero(arm_mask[r])[0]
        if len(cs) < 3:
            f.append(np.nan); b.append(np.nan); continue
        f.append(xz(r, cs.min(), ppl)[0]); b.append(xz(r, cs.max(), ppl)[0])
    return zs, np.array(f), np.array(b)


def ref_arm_profile(fg, cls, ppl):
    """the reference profile's arm: its skin (under the bodysuit's armhole) as the connected skin region through the
    upper arm's rows, the neck's and chest's skin left out (the component reaching z -1.15)."""
    from scipy import ndimage
    skin = fg & (cls == bodyqa.CLASS['skin'])
    lab, n = ndimage.label(skin)
    r = rc(-1.15, 0, ppl)[0]
    ids = set(np.unique(lab[r])) - {0}
    if not ids:
        return np.zeros_like(skin)
    # the largest component crossing that row near the figure's middle
    best = max(ids, key=lambda i: (lab[r] == i).sum())
    m = lab == best
    m[:rc(-0.55, 0, ppl)[0]] = False
    return m


def measure(build):
    B = bundle.load(build + '/bundle')
    D = qa3d.Design(B)
    return measure_labels(D, ours_views(B, build, D), os.path.basename(build.rstrip('/')))


def measure_labels(D, ob, name):
    """the measures on our label images per view (ARM / TORSO / HEAD, -1 nothing) against the reference."""
    ppl = D.sheet_context()['ppl']
    bb = bb_views(D)
    res = dict(build=name, views={})
    for v in VIEWS:
        if v not in bb:
            continue
        rf, rcl = bb[v]['fg'], bb[v]['cls']
        lab = ob[v][:rf.shape[0], :rf.shape[1]]
        of = lab >= 0
        oh = lab == HEAD
        rh = ~ref_body(rf, rcl)
        rec = dict(shift=bb[v]['shift'], head_iou=bb[v]['head_iou'])
        if v in ('front', 'back', 'three_quarter'):
            sides = (1, -1) if v != 'three_quarter' else (-1, 1)
            for s in sides:
                nm = 'right' if s > 0 else 'left'      # (the image's side)
                xs, zt_o = top_line(of, oh, ppl, s)
                _, zt_r = top_line(rf, rh, ppl, s)
                _, zt_rl = top_line(rf, rh, ppl, s, loose=True)
                zs, xo_o = outer_edge(of, oh, ppl, s)
                _, xo_r = outer_edge(rf, rh, ppl, s)
                ok = np.isfinite(zt_r)
                rr = dict(top=stats(zt_o, zt_r), top_loose=stats(zt_o, zt_rl), outer=stats(xo_o, xo_r),
                          top_bands={'%.2f-%.2f' % b: stats(zt_o, zt_r, (xs >= b[0]) & (xs < b[1])) for b in BANDS},
                          point_ours=shoulder_point(xs, zt_o, zs, xo_o),
                          point_ref=shoulder_point(xs, zt_rl, zs, xo_r),
                          axilla_ours=axilla(of, ppl, s), axilla_ref=axilla(rf, ppl, s),
                          st_top={'%.1f' % x0: [station(xs, zt_o, x0), station(xs, zt_rl, x0)] for x0 in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7)},
                          st_out={'%.2f' % z0: [station(zs, xo_o, z0), station(zs, xo_r, z0)] for z0 in (-0.6, -0.7, -0.8, -0.9, -1.0, -1.2)},
                          curves=dict(xs=np.round(xs, 4).tolist(), top_ours=np.round(zt_o, 4).tolist(),
                                      top_ref=np.round(zt_r, 4).tolist(), top_ref_loose=np.round(zt_rl, 4).tolist(), zs=np.round(zs, 4).tolist(),
                                      out_ours=np.round(xo_o, 4).tolist(), out_ref=np.round(xo_r, 4).tolist()))
                rec[nm] = rr
        if v == 'profile':
            ra = ref_arm_profile(rf, rcl, ppl)
            oa = lab == ARM
            zs, rf_f, rf_b = profile_arm(None, ppl, ra)
            _, of_f, of_b = profile_arm(None, ppl, oa)
            rec['arm_front'] = stats(of_f, rf_f)
            rec['arm_back'] = stats(of_b, rf_b)
            rec['arm_width'] = stats(of_b - of_f, rf_b - rf_f)
            # the shoulder's height over the arm's columns (between the arm's front and back at z -0.8)
            k = int(np.nanargmin(np.abs(zs + 0.8)))
            tops = {}
            for nm, fgm, cl, f_, b_ in (('ours', of, None, of_f, of_b), ('ref', rf, rcl, rf_f, rf_b)):
                if not (np.isfinite(f_[k]) and np.isfinite(b_[k])):
                    tops[nm] = None; continue
                c0, c1 = rc(0, f_[k], ppl)[1], rc(0, b_[k], ppl)[1]
                zz = []
                for c in range(c0, c1 + 1):
                    col = fgm[rc(-0.3, 0, ppl)[0]:, c]
                    q = np.nonzero(col)[0]
                    if len(q):
                        r = rc(-0.3, 0, ppl)[0] + q[0]
                        if cl is None or cl[r, c] != bodyqa.CLASS['hair']:
                            zz.append(xz(r, c, ppl)[1])
                tops[nm] = round(float(np.median(zz)), 4) if zz else None
            rec['top_over_arm'] = tops
            rec['curves'] = dict(zs=np.round(zs, 4).tolist(), front_ours=np.round(of_f, 4).tolist(),
                                 back_ours=np.round(of_b, 4).tolist(), front_ref=np.round(rf_f, 4).tolist(),
                                 back_ref=np.round(rf_b, 4).tolist())
        res['views'][v] = rec
    res['_masks'] = (ob, bb, ppl)
    return res


def png(results, path):
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from skimage import measure as skm
    n = len(VIEWS)
    fig, ax = plt.subplots(1, n, figsize=(5 * n, 5.5))
    W = bodyqa.WIN
    cols = ['tab:red', 'tab:blue', 'tab:green', 'tab:purple', 'tab:orange']
    ob0, bb, ppl = results[0]['_masks']
    for j, v in enumerate(VIEWS):
        if v not in bb:
            continue
        r0, r1 = rc(-0.25, 0, ppl)[0], rc(-1.45, 0, ppl)[0]
        c0, c1 = rc(0, -1.0, ppl)[1], rc(0, 1.0, ppl)[1]
        ref, cls = bb[v]['fg'][r0:r1, c0:c1], bb[v]['cls'][r0:r1, c0:c1]
        im = np.ones(ref.shape + (3,))
        im[ref] = (0.72, 0.72, 0.76)
        im[ref & (cls == bodyqa.CLASS['skin'])] = (0.96, 0.84, 0.74)
        im[ref & (cls == bodyqa.CLASS['hair'])] = (0.95, 0.65, 0.45)
        ext = [c0 / ppl - W['x'], c1 / ppl - W['x'], W['top'] - r1 / ppl, W['top'] - r0 / ppl]
        ax[j].imshow(im, extent=ext)
        for k, R in enumerate(results):
            lab = R['_masks'][0][v][r0:r1, c0:c1]
            for m, ls in ((lab >= 0, '-'), (lab == ARM, ':')):
                for C in skm.find_contours(np.pad(m, 1).astype(float), 0.5):
                    C = C - 1
                    ax[j].plot(C[:, 1] / ppl + ext[0], ext[3] - C[:, 0] / ppl, ls, color=cols[k % 5], lw=1.0,
                               label=R['build'] if ls == '-' and C is not None else None)
            for s in ('left', 'right'):
                rr = R['views'].get(v, {}).get(s)
                if rr and rr.get('point_ours'):
                    p = rr['point_ours']; sg = 1 if s == 'right' else -1
                    ax[j].plot(sg * p[0], p[1], 'o', color=cols[k % 5], ms=5)
                if k == 0 and rr and rr.get('point_ref'):
                    p = rr['point_ref']; sg = 1 if s == 'right' else -1
                    ax[j].plot(sg * p[0], p[1], 'kx', ms=7)
        h, l = ax[j].get_legend_handles_labels()
        uniq = dict(zip(l, h))
        ax[j].legend(uniq.values(), uniq.keys(), fontsize=7, loc='lower center')
        ax[j].set_title('%s (grey/tan: base body ref; x ref shoulder point)' % v, fontsize=9)
        ax[j].set_aspect('equal')
    fig.tight_layout(); fig.savefig(path, dpi=110)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    opt = lambda k: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else None
    out_png, out_json = opt('--png'), opt('--json')
    args = [a for a in args if a not in (out_png, out_json)]
    res = []
    for b in args:
        R = measure(b)
        res.append(R)
        print('==', R['build'])
        for v, rec in R['views'].items():
            print('  %s shift %s head_iou %s' % (v, rec['shift'], rec['head_iou']))
            for s in ('left', 'right'):
                rr = rec.get(s)
                if not rr:
                    continue
                print('    %-5s top %s | loose %s | outer %s' % (s, rr['top'], rr['top_loose'], rr['outer']))
                print('          bands %s' % {k: (q.get('med'), q.get('n')) for k, q in rr['top_bands'].items()})
                print('          point ours %s ref %s | axilla ours %s ref %s' % (rr['point_ours'], rr['point_ref'],
                                                                                rr['axilla_ours'], rr['axilla_ref']))
                print('          top z at |x| (ours, ref) %s' % rr['st_top'])
                print('          outer |x| at z (ours, ref) %s' % rr['st_out'])
            if v == 'profile':
                print('    arm front %s back %s width %s top over arm %s' % (rec['arm_front'], rec['arm_back'],
                                                                         rec['arm_width'], rec['top_over_arm']))
    for p in (out_png, out_json):
        if p:
            os.makedirs(os.path.dirname(p) or '.', exist_ok=True)
    if out_png:
        png(res, out_png)
    if out_json:
        json.dump([{k: v for k, v in R.items() if k != '_masks'} for R in res], open(out_json, 'w'), indent=1)
