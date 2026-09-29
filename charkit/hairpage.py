"""The hair pieces' review page: a build with its hair in pieces (hair.shape.mode 'pieces', charkit.geom.hairpieces)
against the design and against a build before it.

    python -m charkit hairpage BUILD [--against BASE_BUILD] [--out DIR]     -> DIR/index.html (default BUILD/hair)

  checks     every hair check of the QA, this build against BASE (the per-family IoUs against the hair layers, the
             fringe, penetration and folds, and the whole-hair checks: IoU, width, length, top, noise, scalp, shown)
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
