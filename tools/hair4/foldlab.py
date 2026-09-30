"""hair round 4: why the shell samples fold and shard more than the mesh's vertices. usage:
    python tools/hair4/foldlab.py BUILD OUTDIR [OPTS_JSON] [--fine]
--fine: the envelope's swap split three ways (R and Rn; reach and valid; the skin S with the body cut), shell with the
mesh's each. Every variant's chart fields are kept in OUTDIR/fields.npz (NAME__R, __Rn, __S, __L, __Lfill, __reach).
The pieces built from the mesh's vertices and from the shell's samples, then twice more with the chart's fields swapped
between the two right after mass_fields (before the crown and side-lock trims): the envelope (R, Rn, S, reach, valid,
the body cut) and the partition (L, nothair). Each fold and shard is then put down to the envelope, the partition, or
the points themselves (the buns and flyaways read the samples directly). Per variant, OUTDIR/foldlab.json: folds per
piece and per lock with where (phi, theta; outer, inner or wall), each piece's locks and tips, every view's shards with
where, the partition's cells that differ (by family pair, with each side's vote share), the envelope's difference.
OUTDIR/foldlab.png: the partition per cell (mesh, shell, where they differ), the envelope's difference, folds marked."""
import json, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import numpy as np
from charkit import hairlab as hl, qa3d
from charkit.geom import hairpieces as hp

ENV = ('R', 'Rn', 'S', 'reach', 'valid', 'clear', 'body_cut')
FINE = {'Rs': ('R', 'Rn'), 'reach': ('reach', 'valid'), 'skin': ('S', 'clear', 'body_cut')}
PART = ('L', 'nothair')


def fold_faces(V, T, outer, vn_env):
    """hp.folds' faces as a mask (the same test, face by face)."""
    T = np.asarray(T)
    fo = outer[T]
    surf = fo.all(1) | ~fo.any(1)
    fn = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-18
    ref = vn_env[T].mean(1)
    ref /= np.linalg.norm(ref, axis=1, keepdims=True) + 1e-18
    against = np.einsum('ij,ij->i', fn, ref) < -0.5
    E = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
    f = np.tile(np.arange(len(T)), 3)
    key = np.sort(E, 1)
    o = np.lexsort((key[:, 1], key[:, 0]))
    key, f = key[o], f[o]
    same = np.all(key[1:] == key[:-1], axis=1)
    a, b = f[:-1][same], f[1:][same]
    d = np.einsum('ij,ij->i', fn[a], fn[b])
    tot = np.bincount(a, d, len(T)) + np.bincount(b, d, len(T))
    cnt = np.bincount(a, None, len(T)) + np.bincount(b, None, len(T))
    flipped = (cnt > 0) & (tot / np.maximum(cnt, 1) < 0)
    return surf & (against | flipped), fo.all(1), against


class Swap:
    """hp.mass_fields wrapped: `save` keeps a copy of what it returns (and its points and families), `swap` (src, keys)
    replaces those keys with a saved result's."""

    def __init__(self):
        self.orig, self.store, self.save, self.swap = hp.mass_fields, {}, None, None
        hp.mass_fields = self

    def __call__(self, case, V, fam, o):
        F = self.orig(case, V, fam, o)
        cp = lambda x: x.copy() if isinstance(x, np.ndarray) else x
        if self.save:
            self.store[self.save] = dict({k: cp(v) for k, v in F.items()}, _V=np.asarray(V).copy(), _fam=fam.copy())
        if self.swap:
            src, keys = self.swap
            for k in keys:
                F[k] = cp(self.store[src][k])
        return F


def votes(case, F, V, fam):
    """per cell the mass points' family counts (mass_fields' vote, before its mode filter) -> (nph, nth, nfam+1)."""
    from charkit.geom.parts import hair_region
    ch, G = F['chart'], F['grid']
    inreg = hair_region(case)(V)
    mass = np.isin(fam, [hp.fam_id(f) for f in hp.MASS]) & inreg
    ph, th, r = ch.coords(V[mass])
    i, j, ok = G.cell(ph, th)
    fc = np.zeros((G.nph, G.nth, len(hp.FAMILIES) + 1))
    np.add.at(fc, (i[ok], j[ok], fam[mass][ok]), 1)
    return fc


def piece_folds(R, F):
    ch = F['chart']
    out = {}
    for name, p in R['pieces'].items():
        V, T = p['V'], np.asarray(p['T'])
        bad, outer_f, against = fold_faces(V, T, p['outer'], p['vn_env'])
        lk = p['lock'][T[:, 0]]
        inner_f = ~p['outer'][T].any(1)
        rows = []
        for k in np.nonzero(bad)[0]:
            c = V[T[k]].mean(0)
            ph, th, r = ch.coords(c[None])
            rows.append(dict(lock=int(lk[k]), ph=round(float(ph[0]), 1), th=round(float(th[0]), 1),
                             surf='outer' if outer_f[k] else 'inner' if inner_f[k] else 'wall',
                             how='against' if against[k] else 'flipped'))
        out[name] = dict(n=int(bad.sum()), locks=int(p['lock'].max()) + 1,
                         tips=R['report']['pieces'][name].get('tips_deg'), where=rows)
    return out


def shards(ctx, hair, design):
    ours = hl.our_edges(ctx, hair)
    C = hl.edge_checks(ours, design)
    out = {}
    for v in hl.EDGE_VIEWS:
        if v in ours:
            sh = ours[v].get('shards') or {}
            out[v] = dict(fragments=C.get('hair_fragments_' + v, {}).get('value'),
                          loose=ours[v]['fragments']['n'], loose_by=ours[v]['fragments']['by'],
                          shards=sh.get('n'), by=sh.get('by'), where=sh.get('where'),
                          design=C.get('hair_fragments_' + v, {}).get('design'))
    return out, ours


def variant(ctx, design, sw, name, samples, swap=None, opts=None):
    C = ctx['C']
    o = dict(ctx['spec']['hair']['shape'].get('pieces_opts') or {}, **(opts or {}))
    o['samples'] = samples
    fam, pts = ctx['samples'][samples]
    sw.save, sw.swap = (name if swap is None else None), swap
    R = hp.build(C, fam, ctx['masks'], ctx['style'], views=ctx['views'],
                 hull_frame=(C.align['scale'], np.asarray(C.align['translate'])), opts=o, log=lambda *a: None,
                 points=pts)
    sw.save = sw.swap = None
    hair = {n: ((p['V'], np.asarray(p['T'])),) * 2 for n, p in R['pieces'].items()}
    sh, ours = shards(ctx, hair, design)
    return R, piece_folds(R, R['fields']), sh


def partition_diff(A, B, key, va, vb):
    """cells where A's and B's per-cell family differ: (mesh, shell) family pairs, with each side's vote share for
    its own winner and the cell count per pair."""
    a, b = A[key], B[key]
    d = (a != b) & ((a > 0) | (b > 0))
    pairs = {}
    name = lambda k: 'none' if k == 0 else (hp.FAMILIES[k - 1] if k <= len(hp.FAMILIES) else 'bun_base')
    for i, j in zip(*np.nonzero(d)):
        k = '%s -> %s' % (name(int(a[i, j])), name(int(b[i, j])))
        sa = va[i, j].sum(); sb = vb[i, j].sum()
        p = pairs.setdefault(k, dict(cells=0, share_mesh=[], share_shell=[], n_mesh=[], n_shell=[]))
        p['cells'] += 1
        p['share_mesh'].append(float(va[i, j, a[i, j]] / sa) if sa and a[i, j] else 0.0)
        p['share_shell'].append(float(vb[i, j, b[i, j]] / sb) if sb and b[i, j] else 0.0)
        p['n_mesh'].append(int(sa)); p['n_shell'].append(int(sb))
    for p in pairs.values():
        for k in ('share_mesh', 'share_shell', 'n_mesh', 'n_shell'):
            p[k] = round(float(np.median(p[k])), 3) if p[k] else None
    return int(d.sum()), dict(sorted(pairs.items(), key=lambda kv: -kv[1]['cells'])), d


PAL = np.array([[235, 235, 235], [230, 90, 90], [90, 150, 230], [120, 200, 120], [200, 150, 60], [170, 100, 200],
                [60, 190, 190], [240, 200, 60], [120, 120, 120]], np.uint8)


def chart_img(Lc, G, marks=(), s=6, diff=None):
    """a (phi across, theta down) picture of a per-cell family field, fold faces marked black, `diff` cells ringed."""
    img = PAL[np.clip(Lc, 0, len(PAL) - 1)].transpose(1, 0, 2)
    if diff is not None:
        img = np.where(diff.T[..., None], img, (img * 0.35 + 165).astype(np.uint8))
    img = np.repeat(np.repeat(img, s, 0), s, 1).copy()
    for ph, th in marks:
        c = int((ph + 180) / G.dphi * s); r = int(th / G.dth * s)
        img[max(0, r - 2):r + 3, max(0, c - 2):c + 3] = 0
    return img


def heat(D, s=6, lim=0.02):
    x = np.clip(D / lim, -1, 1).T
    rgb = np.stack([np.where(x > 0, 255, 255 * (1 + x)), 255 * (1 - np.abs(x)), np.where(x < 0, 255, 255 * (1 - x))], -1)
    rgb = np.where(np.isfinite(D.T)[..., None], rgb, 200).astype(np.uint8)
    return np.repeat(np.repeat(rgb, s, 0), s, 1)


def picture(path, rows):
    from PIL import Image, ImageDraw
    pad, lab = 8, 16
    H = sum(max(im.shape[0] for _, im in r) + lab + pad for r in rows)
    W = max(sum(im.shape[1] + pad for _, im in r) for r in rows)
    can = Image.new('RGB', (W + pad, H + pad), (255, 255, 255))
    dr = ImageDraw.Draw(can)
    y = pad
    for r in rows:
        x = pad
        for title, im in r:
            dr.text((x, y), title, fill=(0, 0, 0))
            can.paste(Image.fromarray(im), (x, y + lab))
            x += im.shape[1] + pad
        y += max(im.shape[0] for _, im in r) + lab + pad
    can.save(path)


if __name__ == '__main__':
    build, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    fine = '--fine' in sys.argv
    argv = [a for a in sys.argv if a != '--fine']
    opts = json.loads(argv[3]) if len(argv) > 3 else {}
    os.makedirs(out, exist_ok=True)
    t = time.time()
    ctx = hl.context(build)
    design = hl.design_edges(ctx)
    print('context %.0f s' % (time.time() - t), flush=True)
    sw = Swap()
    res, keep = {}, {}
    plan = [('mesh', 'mesh', None), ('shell', 'shell', None),
            ('shell_envmesh', 'shell', ('mesh', ENV)), ('shell_partmesh', 'shell', ('mesh', PART)),
            ('mesh_envshell', 'mesh', ('shell', ENV)), ('mesh_partshell', 'mesh', ('shell', PART))]
    if fine:
        plan += [('shell_%smesh' % k, 'shell', ('mesh', v)) for k, v in FINE.items()]
    for name, samples, swap in plan:
        t = time.time()
        R, fo, sh = variant(ctx, design, sw, name, samples, swap, opts)
        F = R['fields']
        keep[name] = F
        res[name] = dict(folds={k: v['n'] for k, v in fo.items()}, total=sum(v['n'] for k, v in fo.items()),
                         mass_folds=sum(v['n'] for k, v in fo.items() if k in ('bangs', 'side_lock_L', 'side_lock_R',
                                                                                'upper_back', 'lower_back')),
                         pieces=fo, frags={v: s['fragments'] for v, s in sh.items()}, shards=sh)
        print('== %s (%.0f s): folds %d %s | frags f/3q/p/b %s' % (
            name, time.time() - t, res[name]['total'], res[name]['folds'],
            ' '.join(str(sh[v]['fragments']) for v in hl.EDGE_VIEWS if v in sh)), flush=True)
        for v in ('profile',):
            print('   %s shards %s loose %s' % (v, sh[v]['by'], sh[v]['loose_by']))
    np.savez_compressed(os.path.join(out, 'fields.npz'), **{'%s__%s' % (n, k): np.asarray(F[k], float)
                                                            for n, F in keep.items()
                                                            for k in ('R', 'Rn', 'S', 'L', 'Lfill', 'reach')})
    Fm, Fs = sw.store['mesh'], sw.store['shell']
    G = Fm['grid']
    va = votes(ctx['C'], Fm, Fm['_V'], Fm['_fam'])
    vb = votes(ctx['C'], Fs, Fs['_V'], Fs['_fam'])
    nL, pairsL, dL = partition_diff(Fm, Fs, 'L', va, vb)
    nF, pairsF, dF = partition_diff(keep['mesh'], keep['shell'], 'Lfill', va, vb)
    dR = np.where(np.isfinite(Fm['R']) & np.isfinite(Fs['R']), Fs['R'] - Fm['R'], np.nan) / ctx['C'].L
    hairc = keep['mesh']['Lfill'] > 0
    res['partition'] = dict(L_cells_differ=nL, L_pairs=pairsL, Lfill_cells_differ=nF, Lfill_pairs=pairsF,
                            hair_cells=int(hairc.sum()),
                            density=dict(mesh_pts=int(va.sum()), shell_pts=int(vb.sum()),
                                         mesh_per_cell_med=float(np.median(va.sum(2)[va.sum(2) > 0])),
                                         shell_per_cell_med=float(np.median(vb.sum(2)[vb.sum(2) > 0]))))
    res['envelope'] = dict(dR_L=dict(med=round(float(np.nanmedian(np.abs(dR[hairc]))), 4),
                                     p90=round(float(np.nanpercentile(np.abs(dR[hairc]), 90)), 4),
                                     max=round(float(np.nanmax(np.abs(dR[hairc]))), 4)))
    # the envelope's roughness: the cell-to-cell second difference of R (L) over the hair's cells, each source
    def rough(Rf):
        a = Rf / ctx['C'].L
        d2 = np.abs(np.roll(a, 1, 0) + np.roll(a, -1, 0) - 2 * a)[:, 1:-1] + np.abs(a[:, 2:] + a[:, :-2] - 2 * a[:, 1:-1])
        m = hairc[:, 1:-1]
        return dict(med=round(float(np.median(d2[m])), 5), p90=round(float(np.percentile(d2[m], 90)), 5),
                    p99=round(float(np.percentile(d2[m], 99)), 5))
    res['envelope']['rough'] = dict(mesh=rough(Fm['R']), shell=rough(Fs['R']))
    json.dump(res, open(os.path.join(out, 'foldlab.json'), 'w'), indent=1, default=lambda x: x.item()
              if isinstance(x, np.generic) else str(x))
    mk = lambda n: [(w['ph'], w['th']) for k, p in res[n]['pieces'].items() for w in p['where']]
    rows = [[('mesh: partition L (folds)', chart_img(Fm['L'], G, mk('mesh'))),
             ('shell: partition L (folds)', chart_img(Fs['L'], G, mk('shell'))),
             ('L differs (shell family shown)', chart_img(Fs['L'], G, diff=dL))],
            [('mesh: Lfill', chart_img(keep['mesh']['Lfill'], G, mk('mesh'))),
             ('shell: Lfill', chart_img(keep['shell']['Lfill'], G, mk('shell'))),
             ('Lfill differs', chart_img(keep['shell']['Lfill'], G, diff=dF))],
            [('shell env + mesh part (folds)', chart_img(keep['shell_partmesh']['Lfill'], G, mk('shell_partmesh'))),
             ('shell part + mesh env (folds)', chart_img(keep['shell_envmesh']['Lfill'], G, mk('shell_envmesh'))),
             ('R shell - mesh (red out, blue in, +-0.02 L)', heat(dR))]]
    picture(os.path.join(out, 'foldlab.png'), rows)
    print('partition: L differs in %d cells, Lfill in %d (of %d hair cells)' % (nL, nF, int(hairc.sum())))
    for k, v in list(pairsF.items())[:8]:
        print('   Lfill %-28s %s' % (k, v))
    print('envelope: |dR| %s rough %s' % (res['envelope']['dR_L'], res['envelope']['rough']))
    print('density: %s' % res['partition']['density'])
