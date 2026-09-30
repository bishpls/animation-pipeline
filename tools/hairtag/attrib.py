"""Which of the hair layers' uses moves the pieces (hairtag round 2): the pieces built with the hull's labels (fam) from
one mask set and the build's mask reads (drawn tips, the side-lock trim's drawn edge, the bun fit's targets, the carve
under the buns, the ahoge's and flyaways' strokes) from another, key by key. usage:
    python tools/hairtag/attrib.py BUILD OUT OLD.npz NEW.npz 'name|{"fam": "old" | {"base": "new", "from_old": [...]}, "masks": "new", "from_old": [KEY GLOB ...],
                                                           "from_new": [...], "opts": {...}, "style": {...}}' ...
Per variant: the folds per piece with where (lock, phi, theta, surface: tools/hair4/foldlab.py's), the hair checks
under both mask sets, each bun per view, the hair's shape IoU per view; OUT/attrib.json."""
import fnmatch, json, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools', 'hair4'))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'hairtag'))
import numpy as np
from charkit import hairlab as hl
from charkit.geom import hairpieces as hp
import twobytwo as tb


def mix(M, base, from_other, other):
    out = dict(M[base])
    for pat in from_other or ():
        for k in M[other]:
            if fnmatch.fnmatchcase(k, pat):
                out[k] = M[other][k]
        for k in list(out):
            if fnmatch.fnmatchcase(k, pat) and k not in M[other]:
                del out[k]
    return out


_GEO = {}


def labels(ctx, masks):
    """the hull's families from masks (hairlab.context's label_hull on the mesh's vertices)."""
    from PIL import Image
    from charkit import manifest
    from charkit.geom import hull, io as gio
    if not _GEO:
        glb = ctx['C'].align['glb']
        side = json.load(open(glb + '.json'))
        Vh = gio.load(glb)
        _GEO.update(Vh=Vh, side=side, lab=np.load(os.path.join(os.path.dirname(glb), side['labels'])),
                    pcs=np.load(os.path.join(os.path.dirname(glb), side['pieces'])))
        M_ = manifest.load(ctx['spec']['ref']['manifest'])
        rgb = np.asarray(Image.open(M_['references']['body_turnaround']['path']).convert('RGB')).astype(float) / 255
        _GEO['ppl'] = hull.views_from_sheet(rgb, (ctx['spec'].get('eyes') or {}).get('x', 0.168), -1)[1]['ppl']
    G = _GEO
    return hp.label_hull(np.asarray(G['Vh'].V), np.asarray(G['Vh'].F), G['lab'], G['pcs'], G['side']['piece_names'],
                         ctx['views'], masks, G['ppl'])[0]


def build(ctxs, M, v):
    fk = v.get('fam', 'new')
    ctx = ctxs[fk if isinstance(fk, str) else 'new']
    mk = v.get('masks', 'new')
    masks = mix(M, mk, v.get('from_old') if mk == 'new' else v.get('from_new'), 'old' if mk == 'new' else 'new')
    C = ctx['C']
    o = dict(ctx['spec']['hair']['shape'].get('pieces_opts') or {}, **(v.get('opts') or {}))
    fam, pts = ctx['samples'].get(o.get('samples', hp.OPTS['samples']), ctx['samples']['mesh'])
    if isinstance(fk, dict):          # the labels from a mix: {"base": "new", "from_old": [...]} (the mesh's samples)
        fb = fk.get('base', 'new')
        fam = labels(ctx, mix(M, fb, fk.get('from_old') if fb == 'new' else fk.get('from_new'),
                              'old' if fb == 'new' else 'new'))
    R = hp.build(C, fam, masks, dict(ctx['style'], **(v.get('style') or {})), views=ctx['views'],
                 hull_frame=(C.align['scale'], np.asarray(C.align['translate'])), opts=o, log=lambda *a: None, points=pts)
    hair = {n: ((p['V'], np.asarray(p['T'])),) * 2 for n, p in R['pieces'].items()}
    return ctx, R, hair


def main(a):
    import foldlab
    build_dir, out, p_old, p_new = (os.path.abspath(x) for x in a[:4])
    os.makedirs(out, exist_ok=True)
    M = {'old': tb.load(p_old), 'new': tb.load(p_new)}
    t = time.time()
    ctxs = {'old': tb.context(build_dir, p_old), 'new': tb.context(build_dir, p_new)}
    print('contexts %.0f s' % (time.time() - t), flush=True)
    res = {}
    for arg in a[4:]:
        name, js = arg.split('|', 1)
        v = json.loads(js)
        t = time.time()
        ctx, R, hair = build(ctxs, M, v)
        pf = foldlab.piece_folds(R, R['fields'])
        sc = {s: tb.score(ctx, hair, M[s]) for s in ('old', 'new')}
        import lab as h4lab
        shape = h4lab.body_iou(ctx, hair)
        res[name] = dict(variant=v, folds={k: p['n'] for k, p in pf.items()}, where={k: p['where'] for k, p in pf.items()
                                                                                 if p['n']}, score=sc, shape=shape,
                         bun_fit=R['report'].get('bun_fit'), trim=R['report'].get('side_lock_trim'))
        q = lambda s, k: sc[s].get(k, {}).get('value')
        print('== %s %s (%.0f s)' % (name, js, time.time() - t))
        print('   folds %d %s' % (sum(res[name]['folds'].values()), {k: n for k, n in res[name]['folds'].items() if n}))
        for k, w in res[name]['where'].items():
            print('     %-12s %s' % (k, ['L%d ph%.0f th%.0f %s' % (x['lock'], x['ph'], x['th'], x['surf'][0]) for x in w]))
        for s in ('old', 'new'):
            print('   %s masks: bangs %s side %s %s ub %s lb %s buns %s ahoge %s fly %s | bun outline %s %s' % (
                s, q(s, 'hair_piece_bangs'), q(s, 'hair_piece_side_locks'), sc[s]['hair_piece_side_locks']['views'],
                q(s, 'hair_piece_upper_back'), q(s, 'hair_piece_lower_back'), q(s, 'hair_piece_buns'),
                q(s, 'hair_piece_ahoge'), q(s, 'hair_piece_flyaways'), q(s, 'hair_bun_outline'),
                sc[s]['hair_bun_outline']['views']))
        print('   shape (figure, hair) %s' % shape, flush=True)
        json.dump(h4lab.conv(res), open(os.path.join(out, 'attrib.json'), 'w'), indent=1)


if __name__ == '__main__':
    main(sys.argv[1:])
