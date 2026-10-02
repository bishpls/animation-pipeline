"""pictures of builds or sweep rows against the design, round a drawn piece: per view the design, then each bundle drawn
(numpy drawing for sweep rows), and the crease overlay (drawn skeleton red: unmatched / purple: matched within tol; ours
blue) for an ink_inside reading.
python look.py OUT.png REGION VIEW[,VIEW] SRC [SRC..] [--decl DECL.json] [--pad PX] [--scale K] [--overlay PIECE]
  SRC a build folder, or with --decl a row name of that sweep declaration (rebuilt here at its stage)."""
import sys, os, json, argparse, numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from skimage.morphology import skeletonize
sys.path.insert(0, '.')
from charkit import bundle, qa3d, declared, bodyqa, pieceqa, outfit, sweep

def bundles(srcs, decl=None):
    if not decl:
        return [(s.rstrip('/').split('/')[-1], bundle.load(s + '/bundle')) for s in srcs]
    d = sweep.load_decl(decl)
    rows = {r['name']: r for r in sweep.expand(d)}
    B0 = sweep.load_bundle(d['base'], d.get('rebase', True))
    spec = sweep.base_spec(d, B0)
    sweep.produce(spec)
    S = sweep.STAGE[d['stage']](dict(d, _out='/tmp'), B0, spec)
    ctrl = S.objects(rows['control'], '/tmp') if 'control' in rows else {}
    out = []
    for s in srcs:
        g = S.objects(rows[s], '/tmp')
        names = [n for n in g if sweep._changed(g.get(n), ctrl.get(n))] if s != 'control' else [n for n in g if n in ('skirt',)]
        names = sorted(set(names) | {'skirt'} & set(g))
        out.append((s, S.bundle({n: g[n] for n in names})))
    return out

def render(B, v, ppl, az, fr_k=3):
    iw = np.array(qa3d.iris_centres(B))
    fr = declared._Grid(bodyqa.origin(v, az[v], iw, B.assembly['centre']), float(B.assembly['L']), ppl * fr_k)
    surfs = []
    for o in B.objects():
        var = 'masked' if o.group == 'skin' and o.has('masked') else 'eval'
        if o.has(var):
            surfs += qa3d.surfaces(B, o, var)
    img = qa3d.draw(B, surfs, az[v], fr, transparent=False, ss=fr_k)
    return (np.clip(img[..., :3], 0, 1) * 255).astype(np.uint8)

def overlay(B, I, v, region, piece, band=0.02, tol=0.015, edge=False, relative=None):
    ppl = I['ppl']; sh = I['O'][v]['lab'].shape
    R = declared.fit(I['masks']['%s__%s' % (v, region)], sh)
    R = ndimage.binary_fill_holes(ndimage.binary_closing(R, iterations=3))
    b_ = int(round(band * ppl)); inner = ndimage.binary_erosion(R, iterations=b_)
    if edge:
        inner = ndimage.binary_dilation(R, iterations=b_) & ~inner
    dv = I['dv'][v]
    ink = (dv['raw'] == bodyqa.CLASS['line']) | (outfit.ridges(dv['rgb']) & (dv['raw'] != bodyqa.CLASS['skin']))
    d_ = skeletonize(declared.fit(ink, sh) & inner)
    Mo = pieceqa.members(I['O'][v]['lab'], I['names'], I['pm'], piece)
    zo = inner
    if relative:
        ctx = D_ctx = pieceqa.our_classes(B, ppl, qa3d.Design(B).sheet_context()['az3'], (v,))[v]
        Ro = Mo & (ctx[:sh[0], :sh[1]] == bodyqa.CLASS[relative])
        Ro = ndimage.binary_fill_holes(ndimage.binary_closing(Ro, iterations=3))
        zo = ndimage.binary_erosion(Ro, iterations=b_)
        if edge:
            zo = ndimage.binary_dilation(Ro, iterations=b_) & ~zo
    o_ = skeletonize(I['lines'][v] & zo & ndimage.binary_dilation(Mo, iterations=2))
    if relative:
        o_ = declared.remap_rows(o_, Ro, R)
    near_o = ndimage.distance_transform_edt(~o_) <= tol * ppl if o_.any() else np.zeros(sh, bool)
    img = np.full(sh + (3,), 255, np.uint8)
    img[R] = (235, 228, 205)
    img[ndimage.binary_dilation(o_)] = (40, 90, 240)
    img[ndimage.binary_dilation(d_ & ~near_o)] = (230, 30, 30)
    img[ndimage.binary_dilation(d_ & near_o)] = (160, 40, 180)
    return img, 1 - (d_ & near_o).sum() / max(1, d_.sum())

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('out'); ap.add_argument('region'); ap.add_argument('views'); ap.add_argument('srcs', nargs='+')
    ap.add_argument('--decl'); ap.add_argument('--pad', type=int, default=40); ap.add_argument('--scale', type=int, default=2)
    ap.add_argument('--overlay'); ap.add_argument('--edge', action='store_true'); ap.add_argument('--band', type=float, default=0.02); ap.add_argument('--relative')
    a = ap.parse_args()
    Bs = bundles(a.srcs, a.decl)
    rows = []
    for v in a.views.split(','):
        tiles = []
        for bi, (name, B) in enumerate(Bs):
            D = qa3d.Design(B); ctx = D.sheet_context(); ppl = ctx['ppl']; az = bodyqa.azimuths(ctx['az3'])
            I = declared.inputs(B, D, (v,), lines=bool(a.overlay))
            sh = I['O'][v]['lab'].shape
            R = declared.fit(I['masks']['%s__%s' % (v, a.region)], sh)
            r, c = np.nonzero(R); p = a.pad
            sl = (slice(max(0, r.min() - p), r.max() + p), slice(max(0, c.min() - p), c.max() + p))
            if bi == 0:
                d = np.asarray(I['dv'][v]['rgb']); d = (np.clip(d, 0, 1) * 255).astype(np.uint8) if d.dtype != np.uint8 else d
                dd = np.zeros(sh + (3,), np.uint8); h, w = min(sh[0], d.shape[0]), min(sh[1], d.shape[1]); dd[:h, :w] = d[:h, :w, :3]
                tiles.append(('design ' + v, dd[sl]))
            img = render(B, v, ppl, az)
            H = np.zeros(sh + (3,), np.uint8); h, w = min(sh[0], img.shape[0]), min(sh[1], img.shape[1]); H[:h, :w] = img[:h, :w]
            tiles.append(('%s %s' % (name, v), H[sl]))
            if a.overlay:
                ov, val = overlay(B, I, v, a.region, a.overlay, band=a.band, edge=a.edge, relative=a.relative)
                tiles.append(('%s lines %.3f' % (name, val), ov[sl]))
        k = a.scale
        row = Image.new('RGB', (sum(t.shape[1] * k + 6 for _, t in tiles), max(t.shape[0] for _, t in tiles) * k + 18), 'white')
        x = 0
        for lab, t in tiles:
            row.paste(Image.fromarray(t).resize((t.shape[1] * k, t.shape[0] * k), Image.LANCZOS), (x, 18))
            ImageDraw.Draw(row).text((x + 4, 3), lab, fill='black'); x += t.shape[1] * k + 6
        rows.append(row)
    out = Image.new('RGB', (max(r.width for r in rows), sum(r.height for r in rows)), 'white'); y = 0
    for r in rows:
        out.paste(r, (0, y)); y += r.height
    out.save(a.out); print(a.out, out.size)
