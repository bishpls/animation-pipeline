"""The hair pieces' review page: a build with its hair in pieces (hair.shape.mode 'pieces', charkit.geom.hairpieces)
against the design and against a build before it.

    python -m charkit hairpage BUILD [--against BASE_BUILD] [--out DIR]     -> DIR/index.html (default BUILD/hair)

  renders    per view the design's turnaround figure (the manifest's head_turnaround, body_turnaround) beside BASE's
             board and this build's (BUILD/boards: build with --boards views,body)
  checks     every hair check of the QA, this build against BASE (the per-family IoUs against the hair layers, the
             fringe, penetration and folds, and the whole-hair checks: IoU, width, length, top, noise, scalp, shown);
             with BASE, the hair pieces' checks and hair_noise also remeasured on both builds by this code's QA (like
             for like)
  families   per view the drawing's families (the hair layers, charkit.hairlayers) beside ours (qa_hair_pieces.png)
  sheet      the QA's body comparison, the head's rows: the design, ours, the overlap (qa_sheet_body.png)
  noise      the hair drawn alone with its toon materials (qa_hair_front.png), BASE's beside it
  pieces     each piece alone from the front and the side, its locks' chains drawn root to tip; and exploded
  table      per piece: locks, triangles, folds, the push over the skin, fairness (the outer surface's normals against
             the smoothed envelope's: what a 'geometric' style would shade)
"""
import html, json, os, sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAL = {'bangs': (.85, .2, .2), 'side_lock_L': (1, .8, .2), 'side_lock_R': (.95, .65, .1), 'upper_back': (.55, .3, .9),
       'lower_back': (1, .5, .7), 'bun_L': (.2, .4, 1), 'bun_R': (.3, .5, 1), 'ahoge': (.1, .8, .7),
       'flyaways': (.5, .9, .1)}
EXPLODE = 0.35                  # L: how far the exploded view moves each piece out
HAIR_KEYS = ('hair', 'scalp', 'sheet_shown', '_top', 'shape_iou_hair', 'palette_hair')
HEAD_BOARDS = (('front', 'face_000'), ('three-quarter', 'face_030'), ('profile', 'face_090'), ('back (az 150)', 'face_150'))
BODY_BOARDS = ('body_000', 'body_035', 'body_090', 'body_180')


def figures(path, tol=0.06, gap=12):
    """a turnaround sheet's figures, left to right: their boxes (x0, y0, x1, y1), split where no column differs from
    the background (the border's median colour) for `gap` pixels."""
    from PIL import Image
    im = np.asarray(Image.open(path).convert('RGB')).astype(float) / 255
    bg = np.median(np.r_[im[0], im[-1]], 0)
    fg = np.abs(im - bg).max(2) > tol
    on = np.r_[False, fg.sum(0) > 2, False]
    edges = np.flatnonzero(np.diff(on.astype(int)))
    runs = [[a, b] for a, b in zip(edges[::2], edges[1::2])]
    merged = []
    for a, b in runs:
        if merged and a - merged[-1][1] < gap:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    out = []
    for a, b in merged:
        if b - a < 40:
            continue
        rows = np.flatnonzero(fg[:, a:b].any(1))
        out.append((int(a), int(rows.min()), int(b), int(rows.max()) + 1))
    return out


def _p(path):
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


def load_pieces(build):
    """the build's pieces: {name: dict(family, V, F, vn, lock, chains, outer)} and the index, from the parts the build
    wrote (its resolved spec's hair.shape.pieces, else BUILD/geom/hair_pieces)."""
    from .geom.io import load_npz
    spec = json.load(open(os.path.join(build, [f for f in os.listdir(build) if f.endswith('.spec.json')][0])))
    pdir = ((spec.get('hair') or {}).get('shape') or {}).get('pieces')
    pdir = _p(pdir) if pdir and os.path.isdir(_p(pdir)) else os.path.join(build, 'geom', 'hair_pieces')
    index = json.load(open(os.path.join(pdir, 'pieces.json')))
    out = {}
    for rec in index['pieces']:
        m, meta, extra = load_npz(os.path.join(pdir, rec['file']), with_meta=True)
        out[rec['name']] = dict(family=rec['family'], V=m.V, F=m.F, vn=m.vn, lock=extra.get('lock'),
                                chains=meta.get('chains', []), vn_geom=extra.get('vn_geom'))
    return out, index, spec


def fairness(P):
    """the outer surface's geometric normals against the envelope's (degrees): rms and 95th percentile over the vertices
    whose stored normal points away from the piece's centre (its outer surface)."""
    V, vn, vg = P['V'], P['vn'], P['vn_geom']
    if vg is None or vn is None:
        return None
    out = np.einsum('ij,ij->i', vn, V - V.mean(0)) > 0
    ang = np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', vn[out], vg[out]), -1, 1)))
    return dict(rms=round(float(np.sqrt((ang ** 2).mean())), 2), p95=round(float(np.percentile(ang, 95)), 2)) if len(ang) \
        else None


def render(pieces, az, centre, L, names=None, px=1 / 200., win=None, chains=True):
    """the pieces z-buffered from azimuth az, coloured per piece and shaded by depth, locks outlined; chains drawn."""
    from .geom import raster
    win = win or dict(x=1.3, top=1.4, bottom=-1.3)
    names = names or list(pieces)
    meshes = []
    for k, n in enumerate(names):
        P = pieces[n]
        lab = k * 1000 + (P['lock'][P['F'][:, 0]] if P['lock'] is not None else 0)
        meshes.append((P['V'], P['F'].astype(np.int64), lab))
    a = np.radians(az)
    org = (centre[0] * np.cos(a) + centre[1] * np.sin(a), centre[2])
    depth, lab = raster.window_zbuffer(meshes, az, org, L, px, win)
    img = np.ones(lab.shape + (3,))
    fin = np.isfinite(depth)
    g = np.gradient(np.where(fin, depth, np.nan))
    sh = np.clip(1 - 25 * np.nan_to_num(np.hypot(*g)) / L * px * 200, 0.45, 1)
    for k, n in enumerate(names):
        m = (lab // 1000 == k) & (lab >= 0)
        img[m] = np.array(PAL.get(n, (.6, .6, .6))) * sh[m, None]
    e = np.zeros(lab.shape, bool)
    e[:, 1:] |= lab[:, 1:] != lab[:, :-1]
    e[1:] |= lab[1:] != lab[:-1]
    img[e & (fin | np.roll(fin, 1, 0))] = 0.15
    if chains:
        H, W = lab.shape
        for n in names:
            for ch in pieces[n]['chains']:
                c = np.asarray(ch, float)
                if len(c) < 2:
                    continue
                u = c[:, 0] * np.cos(a) + c[:, 1] * np.sin(a)
                cols = ((u - org[0]) / L + win['x']) / px
                rows = (win['top'] - (c[:, 2] - org[1]) / L) / px
                for i in range(len(c) - 1):
                    for t in np.linspace(0, 1, 12):
                        cc, rr = int(cols[i] + t * (cols[i + 1] - cols[i])), int(rows[i] + t * (rows[i + 1] - rows[i]))
                        if 0 <= rr < H and 0 <= cc < W:
                            img[max(0, rr - 1):rr + 1, max(0, cc - 1):cc + 1] = (0.05, 0.05, 0.05)
    return img


def page(build, out, against=None):
    from PIL import Image
    pieces, index, spec = load_pieces(build)
    qa = json.load(open(os.path.join(build, 'qa', 'qa.json')))['checks']
    base = json.load(open(os.path.join(against, 'qa', 'qa.json')))['checks'] if against else {}
    img = os.path.join(out, 'img')
    os.makedirs(img, exist_ok=True)
    # the character's head frame: from the bundle
    from . import bundle as bl
    B = bl.load(os.path.join(build, 'bundle'))
    c, L = np.asarray(B.assembly['centre'], float), float(B.assembly['L'])

    def save(a, name):
        Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).save(os.path.join(img, name))
        return 'img/' + name

    def copy(src, name, crop=None):
        if not os.path.exists(src):
            return None
        im = Image.open(src).convert('RGB')
        if crop:
            w, h = im.size
            im = im.crop((0, 0, w, int(h * crop)))
        im.save(os.path.join(img, name))
        return 'img/' + name
    # the renders: the design's figures beside the boards
    from . import manifest
    refs = manifest.load(spec['ref']['manifest'])['references'] if isinstance(spec.get('ref'), dict) else {}
    render_rows = []
    for sheet, boards in (('head_turnaround', HEAD_BOARDS), ('body_turnaround', [(b, b) for b in BODY_BOARDS])):
        figs, src = [], (refs.get(sheet) or {}).get('path')
        if src and os.path.exists(_p(src)):
            im = Image.open(_p(src)).convert('RGB')
            figs = [im.crop(b) for b in figures(_p(src))]
        cells = []
        for k, (label, board) in enumerate(boards):
            d = None
            if sheet == 'head_turnaround' and k < len(figs):
                figs[k].save(os.path.join(img, 'design_%s.png' % board)); d = 'img/design_%s.png' % board
            b0 = copy(os.path.join(against, 'boards', board + '.png'), 'base_%s.png' % board) if against else None
            b1 = copy(os.path.join(build, 'boards', board + '.png'), '%s.png' % board)
            if b1 or b0:
                cells.append((label, d, b0, b1))
        if sheet == 'head_turnaround':
            # the close-ups: each picture's top (the buns, the fringe, the locks' relief) at twice the size
            top = []
            for label, d, b0, b1 in cells:
                row = []
                for x in (d, b0, b1):
                    if x is None:
                        row.append(None); continue
                    im = Image.open(os.path.join(out, x)).convert('RGB')
                    w, h = im.size
                    name = x.replace('img/', 'img/top_')
                    im.crop((0, 0, w, int(h * 0.55))).save(os.path.join(out, name))
                    row.append(name)
                top.append(('%s, top' % label, *row))
            render_rows.append(('head top', top, None))
        if sheet == 'body_turnaround' and figs:
            for k, f in enumerate(figs):
                f.save(os.path.join(img, 'design_body_%d.png' % k))
            cells.insert(0, ('the design', None, None, None))
            render_rows.append(('body', cells, ['img/design_body_%d.png' % k for k in range(len(figs))]))
        else:
            render_rows.append(('head', cells, None))
    rows = []
    keys = sorted(k for k in set(qa) | set(base) if any(s in k for s in HAIR_KEYS))
    for k in keys:
        a, b = base.get(k) or {}, qa.get(k) or {}
        rows.append('<tr><td>%s</td>%s<td class="%s">%s %s</td><td class="note">%s</td></tr>' % (
            k, '<td class="%s">%s %s</td>' % (a.get('status', ''), a.get('value', ''), a.get('status', '')) if against
            else '', b.get('status', ''), b.get('value', ''), b.get('status', ''),
            html.escape(json.dumps({q: v for q, v in b.items() if q in ('views', 'ours_drawn_L', 'per_piece', 'piece')}))))
    rep = index.get('report', {}).get('pieces', {})
    prow = []
    for n, P in pieces.items():
        r = rep.get(n, {})
        f = fairness(P)
        prow.append('<tr><td><span style="background:rgb(%d,%d,%d);padding:0 8px">&nbsp;</span> %s</td><td>%s</td>'
                    '<td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
                        *(np.array(PAL.get(n, (.6, .6, .6))) * 255).astype(int), n, P['family'], r.get('locks'),
                        r.get('tris'), r.get('folds'), r.get('push_L'), '' if f is None else '%.2f / %.2f' % (f['rms'],
                                                                                                          f['p95'])))
    tiles = {}
    for az in (0, 90, 180, 270):
        tiles[az] = save(render(pieces, az, c, L), 'pieces_%d.png' % az)
    # exploded: each piece moved out along its centroid's direction from the head's centre
    exploded = {}
    for n, P in pieces.items():
        d = P['V'].mean(0) - c
        d = d / max(1e-9, np.linalg.norm(d))
        exploded[n] = dict(P, V=P['V'] + d * EXPLODE * L, chains=[(np.asarray(ch_) + d * EXPLODE * L).tolist()
                                                                   for ch_ in P['chains']])
    exp_tiles = [save(render(exploded, az, c, L, win=dict(x=1.8, top=1.9, bottom=-1.7)), 'exploded_%d.png' % az)
                 for az in (0, 90, 180)]
    ex = []
    for n in pieces:
        ex.append((n, save(np.concatenate([render(pieces, 0, c, L, [n], win=dict(x=1.1, top=1.4, bottom=-1.1)),
                                           render(pieces, 90, c, L, [n], win=dict(x=1.1, top=1.4, bottom=-1.1))], 1),
                           'piece_%s.png' % n)))
    fam = copy(os.path.join(build, 'qa', 'qa_hair_pieces.png'), 'families.png')
    body = copy(os.path.join(build, 'qa', 'qa_sheet_body.png'), 'sheet_body.png', crop=0.2)
    noise = copy(os.path.join(build, 'qa', 'qa_hair_front.png'), 'noise.png')
    noise0 = copy(os.path.join(against, 'qa', 'qa_hair_front.png'), 'noise_base.png') if against else None
    body0 = copy(os.path.join(against, 'qa', 'qa_sheet_body.png'), 'sheet_body_base.png', crop=0.2) if against else None
    H = ['<!doctype html><meta charset="utf-8"><title>hair pieces</title><style>body{font:14px/1.45 -apple-system,'
         'system-ui,sans-serif;margin:24px;background:#fafafa;color:#222}h2{font-size:17px;margin-top:30px}.row{display:'
         'flex;gap:12px;flex-wrap:wrap;align-items:flex-end}.tile{text-align:center;font-size:12px;color:#555}.tile img{'
         'display:block;border:1px solid #ddd;background:#fff}table{border-collapse:collapse;font-size:13px}td,th{border:'
         '1px solid #ddd;padding:3px 8px;text-align:left}th{background:#f0f0f0}.PASS{color:#070}.WARN{color:#b60}.FAIL{'
         'color:#c00}.INFO{color:#666}.note{color:#666;font-size:12px}</style>',
         '<h1>Hair in pieces: %s</h1>' % html.escape(os.path.relpath(build, ROOT)),
         '<p class="note">The hair breakdown\'s families built as separate meshes (charkit.geom.hairpieces): the mass '
         'lofted on a chart round the crown from the visual hull, split into locks at its tips; the buns, the ahoge and '
         'the flyaways built on their own. Style: %s (normals: %s). Against: %s.</p>' % (
             html.escape(str(index.get('style'))), html.escape(str(index.get('normals'))),
             html.escape(os.path.relpath(against, ROOT)) if against else 'nothing'),
         _renders(render_rows),
         _remeasured(build, against) if against else '',
         '<h2>Checks</h2><table><tr><th>check</th>%s<th>this build</th><th>detail</th></tr>%s</table>' % (
             '<th>before</th>' if against else '', ''.join(rows)),
         '<h2>Pieces</h2><table><tr><th>piece</th><th>family</th><th>locks</th><th>triangles</th><th>folds</th>'
         '<th>push over the skin (L)</th><th>fairness rms / p95 (deg)</th></tr>%s</table>' % ''.join(prow),
         '<div class="row">%s</div>' % ''.join('<div class="tile"><img src="%s" height="360">az %d</div>' % (t, a)
                                              for a, t in tiles.items()),
         '<p class="note">Each lock outlined; its chain (root to tip, for the spring bones) drawn dark.</p>',
         '<h2>Exploded (each piece moved %.2f L out from the head\'s centre)</h2><div class="row">%s</div>' % (
             EXPLODE, ''.join('<div class="tile"><img src="%s" height="360">az %d</div>' % (t, a)
                              for a, t in zip((0, 90, 180), exp_tiles)))]
    if fam:
        H.append('<h2>Families: the drawing (left) and ours (right), front, profile, back</h2><img src="%s" '
                 'style="max-width:100%%">' % fam)
    if body:
        H.append('<h2>The QA\'s body comparison, the head\'s rows</h2><div class="row">%s%s</div>' % (
            '<div class="tile"><img src="%s" width="700">before</div>' % body0 if body0 else '',
            '<div class="tile"><img src="%s" width="700">this build</div>' % body))
    if noise:
        H.append('<h2>Hair shading (hair_noise\'s picture)</h2><div class="row">%s%s</div>' % (
            '<div class="tile"><img src="%s" height="360">before</div>' % noise0 if noise0 else '',
            '<div class="tile"><img src="%s" height="360">this build</div>' % noise))
    H.append('<h2>Each piece, front and side</h2><div class="row">%s</div>' % ''.join(
        '<div class="tile"><img src="%s" height="260">%s</div>' % (p, n) for n, p in ex))
    open(os.path.join(out, 'index.html'), 'w').write('\n'.join(H))
    return os.path.join(out, 'index.html')


def _renders(rows):
    """the renders section: per head view the design's figure, the base's board and this build's at one height; the
    body's boards under the body turnaround's figures."""
    H = []
    for kind, cells, design in rows:
        if kind in ('head', 'head top') and cells:
            H.append('<h2>%s</h2><table><tr><th></th><th>design</th><th>before</th>'
                     '<th>this build</th></tr>%s</table>' % (
                         'Renders against the design: head' if kind == 'head' else
                         'Close-ups: the buns, the fringe and the locks (the top of each picture)', ''.join(
                         '<tr><td>%s</td>%s</tr>' % (html.escape(label), ''.join(
                             '<td>%s</td>' % ('<img src="%s" height="360">' % x if x else '') for x in (d, b0, b1)))
                         for label, d, b0, b1 in cells)))
        elif kind == 'body' and cells:
            H.append('<h2>Renders: body</h2>')
            if design:
                H.append('<div class="row">%s</div>' % ''.join('<div class="tile"><img src="%s" height="300">design'
                                                              '</div>' % x for x in design))
            for tag, i in (('before', 2), ('this build', 3)):
                H.append('<div class="row">%s</div>' % ''.join(
                    '<div class="tile"><img src="%s" height="300">%s, %s</div>' % (c[i], tag, html.escape(c[0]))
                    for c in cells if c[i]))
    return '\n'.join(H)


def _remeasured(build, against):
    """the hair pieces' checks and hair_noise on both builds by this code's QA (qa3d.hair_pieces, qa3d.hair_noise over
    each bundle's hair objects)."""
    from . import bundle as bl, qa3d
    res = {}
    for tag, b in (('before', against), ('this build', build)):
        try:
            B = bl.load(os.path.join(b, 'bundle'))
            _, C = qa3d.hair_pieces(B, qa3d.Design(B))
            C.update(qa3d.hair_noise(B)[1])
            res[tag] = C
        except Exception as e:                                    # (a build without pieces, or an older bundle)
            res[tag] = {'error': {'status': 'SKIPPED', 'why': repr(e)[:200]}}
    keys = sorted(set(res['before']) | set(res['this build']))
    cell = lambda c: '<td class="%s">%s %s%s</td>' % (c.get('status', ''), c.get('value', ''), c.get('status', ''),
                                                      ' (drawn %s)' % c['drawn'] if 'drawn' in c else '') if c else '<td></td>'
    return ('<h2>Hair pieces and hair_noise, remeasured by this QA on both builds</h2><table><tr><th>check</th><th>before</th><th>this '
            'build</th></tr>%s</table>' % ''.join('<tr><td>%s</td>%s%s</tr>' % (k, cell(res['before'].get(k)),
                                                                              cell(res['this build'].get(k)))
                                                  for k in keys))


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return 0
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    build = os.path.abspath(args[0])
    out = os.path.abspath(opt('--out', os.path.join(build, 'hair')))
    against = opt('--against')
    print(page(build, out, os.path.abspath(against) if against else None))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
