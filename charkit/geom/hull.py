"""Visual hulls from calibrated orthographic reference views (docs/GEOM.md): a character's 3D shape carved from its
turnaround's silhouettes, the way a modeller blocks a figure out from front, side and back drawings.

A view is an orthographic picture of the figure at azimuth `az`, in the QA's convention (charkit.faceqa.view): a point
(x, y, z) shows at u = x cos az + y sin az with z up; 0 is the front (camera on -y), 90 is from +x (the profile, facing
the picture's left), 180 is the back. It has `ppl` px per head length L, its figure mask, its class image, and the
picture's column of its axis and row of its eye line. Coordinates are in L, with z up from the eye line.

A turnaround drawn at one scale with one eye line (charkit refcheck checks this) calibrates exactly from its eyes:
  - the front's eyes put the midline at x = 0;
  - the profile's eye gives the eyes' depth y_e (the profile's own axis is free: it only slides the figure along y);
  - the three-quarter's eyes then fix its axis, since their midpoint shows at u = y_e sin az;
  - the back's axis is its head's.

  carve      the plain hull: every voxel inside the figure in every view given. Three orthogonal views make each
             height's section the rectangle of the front width by the side depth, which a round body isn't.
  rounded    the shape prior (a style's, charkit.styles): each height's section is the union of superellipses inscribed
             in the (front run x side run) rectangles. A front run takes its depth from the side runs of its own class
             where it has them: a forearm's skin from the skin drawn over the clothes, not the torso's depth. The result
             is smoothed across heights and kept inside the plain hull of every view given.
  project    a hull's silhouette at an azimuth, on a (u, z) grid
  validate   leave one out: each view predicted from the others, its IoU against the drawing
  surface    the closed surface (volume.to_mesh), with vertex colours from the view that faces each vertex best

Clawd's body_turnaround (spike, 2026-09-28): the three-quarter predicted from front, side and back only scores IoU 0.715
plain, 0.797 with ellipses, 0.818 with class-aware pairing. TRELLIS scores 0.79 there, our build 0.68.

    python -m charkit.geom hull SPEC [--out DIR] [--h 0.01] [--style anime] [--no-open]
"""
import json, os

import numpy as np

SKIN, HAIR, OTHER = 1, 2, 0         # charkit.bodyqa.CLASS's skin and hair (its classes label the views)


class View:
    """one calibrated orthographic view: mask and class image (H, W), azimuth (deg), px per L, the picture's column of
    the axis (u = 0) and row of the eye line (z = 0), and its pixels for colour."""

    def __init__(self, name, az, mask, ppl, axis, eye_y, labels=None, rgb=None):
        self.name, self.az, self.mask, self.ppl = name, float(az), mask, float(ppl)
        self.axis, self.eye_y, self.labels, self.rgb = float(axis), float(eye_y), labels, rgb

    def pixel(self, u, z):
        """(cols, rows) of picture positions (L) as rounded ints."""
        return (np.round(self.axis + np.asarray(u) * self.ppl).astype(int),
                np.round(self.eye_y - np.asarray(z) * self.ppl).astype(int))

    def sample(self, img, u, z):
        """an image at an outer product of u (N) and z (M) -> (N, M); outside the picture: zero / False."""
        c, r = self.pixel(u, z)
        H, W = img.shape[:2]
        okc, okr = (c >= 0) & (c < W), (r >= 0) & (r < H)
        out = np.zeros((len(c), len(r)) + img.shape[2:], img.dtype)
        out[np.ix_(okc, okr)] = np.swapaxes(img[np.ix_(r[okr], c[okc])], 0, 1)
        return out

    def u_of(self, x, y):
        a = np.radians(self.az)
        return x * np.cos(a) + y * np.sin(a)


def views_from_sheet(rgb, eye_x, facing=-1):
    """a full-body turnaround's views, found as a model sheet's are (charkit.sheetqa.detect_figures) and calibrated from
    their eyes (see the module) -> ({view: View}, info {ppl, az3, y_e, axes})."""
    from charkit import bodyqa, sheetqa
    D = sheetqa.detect_figures(rgb, None, eye_x, facing)
    ppl, F = D['ppl'], D['figures']
    fe = F['front']['eyes']
    # the QA's classes (charkit.bodyqa: colour families; the orange split into hair and dress by where each drawn region
    # lies, above the shoulders or below), over every figure at once: the sheet's figures share one eye line
    fg = sheetqa.foreground(rgb, sheetqa.background(rgb))
    cls = bodyqa.classes(rgb, fg, float(np.mean([e[1] for e in fe])), ppl)[0].astype(np.uint8)
    ax_front = float(np.mean([e[0] for e in fe]))
    eye_front = float(np.mean([e[1] for e in fe]))
    m = F['profile']['_mask']
    ey_p = float(F['profile']['eye_y'])
    rows = range(int(ey_p + 1.0 * ppl), int(ey_p + 2.0 * ppl))           # the torso's band: the profile's (free) axis
    c = [(np.nonzero(m[r])[0][[0, -1]].mean()) for r in rows if m[r].any()]
    ax_prof = float(np.median(c))
    y_e = (F['profile']['eyes'][0][0] - ax_prof) / ppl
    views = {'front': View('front', 0.0, F['front']['_mask'], ppl, ax_front, eye_front, cls, rgb),
             'profile': View('profile', 90.0, m, ppl, ax_prof, ey_p, cls, rgb)}
    info = {'ppl': ppl, 'y_e': round(y_e, 4)}
    if 'three_quarter' in F and len(F['three_quarter']['eyes']) == 2:
        te = F['three_quarter']['eyes']
        az3 = float(np.degrees(np.arccos(np.clip(abs(te[1][0] - te[0][0]) / (abs(fe[1][0] - fe[0][0])), 0, 1))))
        mid = float(np.mean([e[0] for e in te]))
        ax3 = mid - y_e * np.sin(np.radians(az3)) * ppl
        views['three_quarter'] = View('three_quarter', az3, F['three_quarter']['_mask'], ppl, ax3,
                                      float(np.mean([e[1] for e in te])), cls, rgb)
        info['az3'] = round(az3, 2)
    if 'back' in F:
        b = F['back']
        views['back'] = View('back', 180.0, b['_mask'], ppl, float(b.get('axis_x') or b['box'][0] + (b['box'][2] - b['box'][0]) / 2),
                             eye_front, cls, rgb)
    info['axes'] = {k: round(v.axis, 2) for k, v in views.items()}
    return views, info


class Axes:
    """the voxel grid's axes (L): xs, ys, zs (z descending from the top), spacing h."""

    def __init__(self, xs, ys, zs, h):
        self.xs, self.ys, self.zs, self.h = xs, ys, zs, h

    @property
    def shape(self):
        return (len(self.xs), len(self.ys), len(self.zs))


def axes_for(views, h=0.01, pad=0.05):
    """a grid covering every view's figure: x from the front, y from the profile, z from the tallest to the lowest."""
    def extent(v, axis_is):
        cols = np.nonzero(v.mask.any(0))[0]; rows = np.nonzero(v.mask.any(1))[0]
        u = ((cols[[0, -1]] - v.axis) / v.ppl)
        z = ((v.eye_y - rows[[-1, 0]]) / v.ppl)
        return u, z
    uf, zf = extent(views['front'], 'x')
    up, zp = extent(views['profile'], 'y')
    zlo = min(zf[0], zp[0]) - pad; zhi = max(zf[1], zp[1]) + pad
    ext = max(abs(uf).max(), abs(extent(views['back'], 'x')[0]).max() if 'back' in views else 0) + pad
    xs = np.arange(-ext, ext + h / 2, h)
    ys = np.arange(up[0] - pad, up[1] + pad + h / 2, h)
    zs = np.arange(zhi, zlo - h / 2, -h)
    return Axes(xs, ys, zs, h)


def carve(views, A, use):
    """the plain hull of the views named in `use` -> bool (nx, ny, nz)."""
    V = np.ones(A.shape, bool)
    for n in use:
        v = views[n]
        a = np.radians(v.az)
        if abs(np.sin(a)) < 1e-9:                                          # front / back: u = +-x
            V &= v.sample(v.mask, np.cos(a) * A.xs, A.zs)[:, None, :]
        elif abs(np.cos(a)) < 1e-9:                                        # the profiles: u = +-y
            V &= v.sample(v.mask, np.sin(a) * A.ys, A.zs)[None, :, :]
        else:                                                              # an oblique view: per (x, y) column
            U = A.xs[:, None] * np.cos(a) + A.ys[None, :] * np.sin(a)
            c, r = v.pixel(U, A.zs)
            H, W = v.mask.shape
            ok = (c >= 0) & (c < W)
            cc = np.clip(c, 0, W - 1); rr = np.clip(r, 0, H - 1)
            V &= v.mask[rr[None, None, :], cc[:, :, None]] & ok[:, :, None] & ((r >= 0) & (r < H))[None, None, :]
    return V


def _runs(b):
    d = np.diff(np.concatenate([[0], b.astype(np.int8), [0]]))
    return list(zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0] - 1))


def rounded(views, A, use, p=2.0, class_share=0.6, smooth=0.02):
    """the shape prior's hull (see the module): superellipse sections |x/rx|^p + |y/ry|^p <= 1 per (front run x side
    run), class-aware, smoothed across heights by `smooth` L (a Gaussian on its signed distance), inside the plain hull
    of `use`. Needs the front and a profile among `use`; else the plain hull. -> bool (nx, ny, nz)."""
    plain = carve(views, A, use)
    if 'front' not in use or 'profile' not in use:
        return plain
    f, s = views['front'], views['profile']
    Fxz = f.sample(f.mask, A.xs, A.zs)
    if 'back' in use:
        b = views['back']
        Fxz &= b.sample(b.mask, -A.xs, A.zs)
    Fskin = f.sample(f.labels, A.xs, A.zs) == SKIN
    Syz = s.sample(s.mask, A.ys, A.zs)
    Sskin = (s.sample(s.labels, A.ys, A.zs) == SKIN) & Syz
    V = np.zeros(A.shape, bool)
    X, Y = np.meshgrid(A.xs, A.ys, indexing='ij')
    for k in range(len(A.zs)):
        side, side_skin = _runs(Syz[:, k]), _runs(Sskin[:, k])
        for x0, x1 in _runs(Fxz[:, k]):
            skin = Fskin[x0:x1 + 1, k].mean() > class_share
            for y0, y1 in (side_skin if skin and side_skin else side):
                cx, rx = (A.xs[x0] + A.xs[x1]) / 2, (A.xs[x1] - A.xs[x0]) / 2 + A.h / 2
                cy, ry = (A.ys[y0] + A.ys[y1]) / 2, (A.ys[y1] - A.ys[y0]) / 2 + A.h / 2
                V[:, :, k] |= (np.abs((X - cx) / rx) ** p + np.abs((Y - cy) / ry) ** p) <= 1
    V &= plain
    if smooth > 0:
        from scipy.ndimage import distance_transform_edt, gaussian_filter
        d = distance_transform_edt(~V) - distance_transform_edt(V)          # signed distance in voxels (+ outside)
        d = gaussian_filter(d.astype(np.float32), (0.3 * smooth / A.h, 0.3 * smooth / A.h, smooth / A.h))
        Vs = (d < 0) & plain
        # the silhouettes restored: where a given view's drawing shows figure the smoothed hull no longer covers (a
        # finger, a hair tip the blur eroded), the unsmoothed voxels on those rays come back; the smoothing acts only
        # where no view says anything
        for n in use:
            v = views[n]
            a = np.radians(v.az)
            Ps, us = project(Vs, A, v.az)
            Dm = v.sample(v.mask, us, A.zs)
            miss = Dm & ~Ps
            ix, iy, iz = np.nonzero(V & ~Vs)
            iu = np.clip(np.round((A.xs[ix] * np.cos(a) + A.ys[iy] * np.sin(a) - us[0]) / A.h).astype(int), 0, len(us) - 1)
            back = miss[iu, iz]
            ix, iy, iz, iu = ix[back], iy[back], iz[back], iu[back]
            if not len(ix):
                continue
            # one voxel per missing pixel, the one at the median depth on its ray: enough to show there, without
            # giving back the depth a slab had (which the unseen views would show)
            key = iu.astype(np.int64) * len(A.zs) + iz
            dep = -A.xs[ix] * np.sin(a) + A.ys[iy] * np.cos(a)
            o = np.lexsort((dep, key))
            k_sorted = key[o]
            starts = np.flatnonzero(np.r_[True, k_sorted[1:] != k_sorted[:-1]])
            ends = np.r_[starts[1:], len(o)]
            pick = o[(starts + ends - 1) // 2]
            Vs[ix[pick], iy[pick], iz[pick]] = True
        V = Vs
    return V


def project(V, A, az, u0=-3.0, u1=3.0):
    """a hull's silhouette at azimuth `az` on a (u, z) grid of the voxel spacing -> (bool (nu, nz), us)."""
    a = np.radians(az)
    ix, iy, iz = np.nonzero(V)
    u = A.xs[ix] * np.cos(a) + A.ys[iy] * np.sin(a)
    us = np.arange(u0, u1, A.h)
    iu = np.clip(np.round((u - u0) / A.h).astype(int), 0, len(us) - 1)
    M = np.zeros((len(us), len(A.zs)), bool)
    M[iu, iz] = True
    return M, us


def iou(a, b):
    return float((a & b).sum() / max(1, (a | b).sum()))


def score(V, A, view):
    """a hull against one view's drawing: IoU of its silhouette there, and the horizontal offset (L) at which the
    drawing fits it best (0 for a well calibrated view) -> dict."""
    P, us = project(V, A, view.az)
    Dm = view.sample(view.mask, us, A.zs)
    s = iou(P, Dm)
    best = (s, 0.0)
    for d in np.arange(-0.1, 0.1 + 1e-9, A.h):                          # the calibration check
        b = iou(P, view.sample(view.mask, us + d, A.zs))
        if b > best[0] + 1e-9:
            best = (b, d)
    return {'iou': round(s, 4), 'best_offset_L': round(best[1], 3), 'iou_at_best': round(best[0], 4)}


def refine(views, A, prior, bound=0.1):
    """the oblique views' axes refined by their silhouettes: each against the hull of the axis-aligned views, the
    horizontal offset (within `bound` L) where its drawing fits best. The eyes calibrate a three-quarter only roughly: its
    far eye shows partly, so its visible centroid sits toward the nose. In place -> {view: offset L}."""
    fixed = [n for n, v in views.items() if abs(np.sin(np.radians(v.az))) < 1e-9 or abs(np.cos(np.radians(v.az))) < 1e-9]
    out = {}
    for n, v in views.items():
        if n in fixed:
            continue
        V = rounded(views, A, fixed, **prior)
        P, us = project(V, A, v.az)
        best = (-1.0, 0.0)
        for d in np.arange(-bound, bound + 1e-9, A.h / 2):
            b = iou(P, v.sample(v.mask, us + d, A.zs))
            if b > best[0]:
                best = (b, d)
        v.axis += best[1] * v.ppl                     # the drawing at u + d fits: the axis moves by d
        out[n] = round(float(best[1]), 4)
    return out


def validate(views, A, method='rounded', **prior):
    """leave one out: each view predicted from the others -> {view: score + 'from'}; also each view against the hull of
    all of them ('used')."""
    names = list(views)
    out = {}
    for held in names:
        use = [n for n in names if n != held]
        V = rounded(views, A, use, **prior) if method == 'rounded' else carve(views, A, use)
        out[held] = dict(score(V, A, views[held]), **{'from': use, 'method': method if 'profile' in use else 'carve'})
    Vall = rounded(views, A, names, **prior) if method == 'rounded' else carve(views, A, names)
    out['used'] = {n: score(Vall, A, views[n]) for n in names}
    return out, Vall


def surface(V, A, views=None, blur=1.0):
    """the hull's closed surface (charkit.geom.volume.to_mesh on its occupancy, blurred `blur` voxels), in L, z up from
    the eye line, with vertex colours from the view whose camera faces each vertex most -> Mesh."""
    from . import mesh as meshlib, volume
    G = volume.Grid((A.xs[0], A.ys[0], A.zs[-1]), A.h, V[:, :, ::-1])     # z ascending for the grid
    m = volume.to_mesh(G, blur=blur)
    if views and len(m.V):
        N = meshlib.vertex_normals(m.V, m.F)
        cams = {n: np.array([np.sin(np.radians(v.az)), -np.cos(np.radians(v.az)), 0.0]) for n, v in views.items()}
        names = list(views)
        best = np.argmax(np.stack([N @ cams[n] for n in names], 1), 1)
        col = np.zeros((len(m.V), 3))
        for i, n in enumerate(names):
            sel = best == i
            if not sel.any():
                continue
            v = views[n]
            c, r = v.pixel(v.u_of(m.V[sel, 0], m.V[sel, 1]), m.V[sel, 2])
            H, W = v.rgb.shape[:2]
            col[sel] = v.rgb[np.clip(r, 0, H - 1), np.clip(c, 0, W - 1)]
        m.vc = col
    return m


def label_vertices(m, views):
    """each vertex's class (charkit.bodyqa.CLASS) from the view whose camera faces it most -> int array (N,)."""
    from .mesh import vertex_normals
    N = vertex_normals(m.V, m.F)
    names = list(views)
    cams = np.stack([[np.sin(np.radians(views[n].az)), -np.cos(np.radians(views[n].az)), 0.0] for n in names])
    best = np.argmax(N @ cams.T, 1)
    lab = np.zeros(len(m.V), np.int16)
    for i, n in enumerate(names):
        sel = best == i
        if sel.any():
            v = views[n]
            c, r = v.pixel(v.u_of(m.V[sel, 0], m.V[sel, 1]), m.V[sel, 2])
            H, W = v.labels.shape
            lab[sel] = v.labels[np.clip(r, 0, H - 1), np.clip(c, 0, W - 1)]
    return lab


def main(args):
    """python -m charkit.geom hull SPEC [--out DIR] [--h 0.01] [--style anime] [--no-open]"""
    import subprocess, time
    from charkit import bodyeval, eyes as eyelib, refcheck, styles
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    t0 = time.time()
    spec = bodyeval.resolve(args[0])
    ref = spec['ref']
    bs = ref.get('body_sheet')
    if not bs:
        raise SystemExit('hull: the spec has no generated body sheet (the manifest\'s sheets.body)')
    prior = styles.load(opt('--style', spec.get('style', 'anime')))['hull']
    ex = eyelib._knobs(spec.get('eyes'))['x']
    rgb = refcheck._load(bs['image'])
    views, info = views_from_sheet(rgb, ex, bs.get('facing', -1))
    A = axes_for(views, float(opt('--h', 0.01)))
    out = refcheck._p(opt('--out', 'charkit/out/hull/%s' % spec.get('name', 'char')))
    os.makedirs(out, exist_ok=True)
    loo_eyes, _ = validate(views, A, 'rounded', **prior)                # the eyes' calibration alone
    info['refined_L'] = refine(views, A, prior)
    loo, V = validate(views, A, 'rounded', **prior)
    plain, _ = validate(views, A, 'carve')
    m = surface(V, A, views)
    from . import remesh
    full = len(m.F)
    m = remesh.decimate(m, int(opt('--faces', 150000)))
    from . import io, raster, repair
    io.save(m, os.path.join(out, 'hull.ply'))
    io.save(m, os.path.join(out, 'hull.glb'))            # a coloured 'generated character' for charkit.geom.parts
    ey = info['y_e']                                      # its eyes, known exactly (charkit.i3d.glb_eyes reads them)
    np.save(os.path.join(out, 'hull_labels.npy'), label_vertices(m, views))     # per vertex, bodyqa.CLASS
    json.dump({'eyes': [[ex, ey, 0.0], [-ex, ey, 0.0]], 'labels': 'hull_labels.npy', 'units': 'L',
               'by': 'charkit.geom.hull'}, open(os.path.join(out, 'hull.glb.json'), 'w'), indent=1)
    np.savez_compressed(os.path.join(out, 'hull.npz'), V=V, xs=A.xs, ys=A.ys, zs=A.zs)
    rep = {'spec': args[0], 'sheet': bs['image'], 'style': opt('--style', spec.get('style', 'anime')), 'prior': prior,
           'grid': list(A.shape), 'h_L': A.h, 'calibration': info, 'leave_one_out': loo, 'plain_leave_one_out': plain,
           'leave_one_out_eyes_only': loo_eyes,
           'mesh': {'vertices': len(m.V), 'faces': len(m.F), 'faces_before_decimation': full, 'health': repair.report(m)},
           'seconds': round(time.time() - t0, 1)}
    json.dump(rep, open(os.path.join(out, 'hull.json'), 'w'), indent=1, default=str)
    page = _page(rep, views, A, V, m, out)
    for n in views:
        print('%-14s held out: IoU %.4f (eyes only %.4f, plain %.4f)   used: %.4f   offset left %+.3f L' % (
            n, loo[n]['iou'], loo_eyes[n]['iou'], plain[n]['iou'], loo['used'][n]['iou'], loo[n]['best_offset_L']))
    print('refined axes (L):', info['refined_L'])
    print('mesh %d vertices, %d faces; page %s (%.0fs)' % (len(m.V), len(m.F), page, time.time() - t0))
    if '--no-open' not in args:
        subprocess.run(['open', page])


def _page(rep, views, A, V, m, out):
    """the review page: per view the held-out prediction against the drawing, renders of the surface, the numbers."""
    import html
    from PIL import Image
    from . import raster
    img = os.path.join(out, 'img')
    os.makedirs(img, exist_ok=True)

    def save(a, name):
        Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).save(os.path.join(img, name))
        return 'img/' + name
    L = ['<!doctype html><meta charset="utf-8"><title>hull</title><style>body{font:14px/1.45 -apple-system,system-ui,'
         'sans-serif;margin:24px;background:#fafafa;color:#222}h2{font-size:17px;margin-top:30px}.row{display:flex;gap:12px;'
         'flex-wrap:wrap;align-items:flex-end}.tile{text-align:center;font-size:12px;color:#555}.tile img{display:block;'
         'border:1px solid #ddd;background:#fff}table{border-collapse:collapse;font-size:13px}td,th{border:1px solid #ddd;'
         'padding:3px 8px;text-align:right}th{background:#f0f0f0}td:first-child{text-align:left}.note{color:#666;font-size:12px}'
         '</style>', '<h1>Visual hull: %s</h1>' % html.escape(os.path.basename(rep['sheet'])),
         '<p class="note">Carved from the turnaround\'s calibrated orthographic views with the %s style\'s shape prior '
         '(%s). Leave one out: each view predicted from the others (grey both, <b style="color:#e33">red</b> the hull only, '
         '<b style="color:#35f">blue</b> the drawing only). %d x %d x %d voxels of %.3f L.</p>' % (
             html.escape(rep['style']), html.escape(json.dumps(rep['prior'])), *rep['grid'], rep['h_L']),
         '<table><tr><th>view</th><th>held out (prior)</th><th>held out (plain)</th><th>used (all views)</th>'
         '<th>calibration offset, L</th></tr>']
    loo, plain = rep['leave_one_out'], rep['plain_leave_one_out']
    for n in views:
        L.append('<tr><td>%s</td><td>%.4f</td><td>%.4f</td><td>%.4f</td><td>%+.3f</td></tr>' % (
            n, loo[n]['iou'], plain[n]['iou'], loo['used'][n]['iou'], loo[n]['best_offset_L']))
    L.append('</table><h2>Held-out views</h2><div class="row">')
    for n, v in views.items():
        use = [k for k in views if k != n]
        Vh = rounded(views, A, use, **rep['prior'])
        P, us = project(Vh, A, v.az)
        Dm = v.sample(v.mask, us, A.zs)
        im = np.full(P.shape + (3,), 0.96)
        im[P & Dm] = (0.55, 0.55, 0.6); im[P & ~Dm] = (0.9, 0.2, 0.2); im[Dm & ~P] = (0.2, 0.35, 0.95)
        cols = np.nonzero((P | Dm).any(1))[0]
        im = im[max(0, cols[0] - 10):cols[-1] + 10]
        L.append('<div class="tile"><img src="%s" height="520">%s: IoU %.4f</div>' % (
            save(np.transpose(im, (1, 0, 2)), 'held_%s.png' % n), n, loo[n]['iou']))
    L.append('</div><h2>The surface, coloured from the views that face it, and in clay</h2><div class="row">')
    from .mesh import vertex_normals
    N = vertex_normals(m.V, m.F)
    fr = raster.Frame.around([m], res=620, aspect=0.55)
    for shade, col in (('lambert', m.vc), ('lambert', (0.82, 0.8, 0.78))):
        L.append('<div class="row">')
        for az in (0, 35, 90, 135, 180, 225, 270, 315):
            im = raster.render([(m, dict(color=col if col is not None else (0.8, 0.8, 0.8), normals=N, shade=shade))], az, fr)
            L.append('<div class="tile"><img src="%s" height="460">%d deg</div>' % (
                save(im, 'render_%s_%03d.png' % ('colour' if col is m.vc else 'clay', az)), az))
        L.append('</div>')
    L.append('</div>')
    p = os.path.join(out, 'index.html')
    open(p, 'w').write('\n'.join(L))
    return p
