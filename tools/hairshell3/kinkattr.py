"""art_terminator_hair's kinks attributed (round 4, the back view's terminator): per view and sub-pixel placement, each
kink of the hair's cel tone boundaries (artifactqa.terminator, as the check counts them) with the hair objects within
REACH px of it: one object = a kink inside a piece (its own shading), two or more = where the terminator meets a piece
boundary (a step where two pieces' tones disagree). Totals per object, per object pair, and the kinks' share at piece
boundaries; optionally a picture of the back view with each kink's objects.

    python tools/hairshell3/kinkattr.py BUILD [--pieces DIR] [--n 6] [--views back] [--png OUT.png] [--json OUT.json]
        BUILD a build folder (its bundle); --pieces a hair_pieces folder spliced in (a sweep row's: the sweep's splice)
"""
import collections, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import numpy as np

REACH = 3


_COMPS = {}


def comps_of(s_):
    """a surface's triangles' connected components (by shared vertices), the largest first -> per triangle its index."""
    key = id(s_['T'])
    if key not in _COMPS:
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import connected_components
        T = s_['T']; nv = len(s_['V']); nt = len(T)
        r = np.repeat(np.arange(nt), 3); c = T.ravel()
        A = coo_matrix((np.ones(len(r)), (r, nt + c)), shape=(nt + nv, nt + nv))
        n, lab = connected_components(A, directed=False)
        lt = lab[:nt]
        u, inv, cnt = np.unique(lt, return_inverse=True, return_counts=True)
        rank = np.empty(len(u), int); rank[np.argsort(-cnt)] = np.arange(len(u))
        _COMPS[key] = rank[inv]
    return _COMPS[key]


def run(B, offs, views=('back',), pictures=False):
    from charkit import artifactqa as aq, lookqa
    L = float(B.assembly['L'])
    chin_L = float(B.assembly['chin']) / L
    VAZ = {'front': 0.0, 'three_quarter': 35.5, 'profile': 90.0, 'back': 180.0}
    ppl, win = aq.HEAD_PPL, aq.HEAD_WIN
    page = int(round((win[1] + win[2]) * ppl))
    surfs = None
    res = collections.defaultdict(lambda: dict(kinks=0, len=0.0, per_obj=collections.Counter(),
                                               per_pair=collections.Counter(), boundary=0, n=0))
    pics = {}
    for off in offs:
        fr = lookqa.HeadFrame(B, ppl=ppl, ss=1, win=win, off=off)
        if surfs is None:
            surfs = lookqa._scene(B, skin_outline=True, line_scale=lookqa.line_scale(B, ppl, page))
            kinds_of = np.array([aq.KINDS.index(aq.object_kind(s['o'])) for s in surfs] + [-1])
            line_of = np.array([bool(s['hull']) for s in surfs] + [False])
            names = [s['o'].name for s in surfs] + ['-']
        chin_row = (win[1] + chin_L) * ppl
        for v in views:
            mesh, tone = aq.buffers(B, surfs, VAZ[v], fr)
            items = [(s_['V'], s_['T'], s_['slots'], s_['cull']) for s_ in surfs]
            _, _, mi_, ti_, _ = fr.zbuffer(items, VAZ[v], ids=True)
            kimg = kinds_of[np.where(mesh >= 0, mesh, len(kinds_of) - 1)]
            kinds = {k: kimg == i for i, k in enumerate(aq.KINDS)}
            line = line_of[np.where(mesh >= 0, mesh, len(line_of) - 1)]
            regs = aq.view_regions(kinds, chin_row, aq.NECK * ppl, line=line, ppl=ppl, regions=('hair',))
            g = regs['hair']
            zk = g['zone']
            k = aq.frame_keep(mesh.shape)
            k = k if zk is None else k & zk
            pt = []
            st = aq.terminator(g['body'], aq.buffer_tone(tone, g['body']), ppl, keep=k, parts=pt, line=g['line'])
            R = res[v]
            R['n'] += 1
            R['kinks'] += (st or {}).get('n_kinks', 0)
            R['len'] += (st or {}).get('len', 0.0)
            hair_obj = np.where(kinds['hair'] & (mesh >= 0) & ~line, mesh, -1)
            # each surface's triangles in connected components (a lock shell is its own closed tube): name#k
            comp = np.full(mesh.shape, -1, np.int64)
            for j in np.unique(hair_obj[hair_obj >= 0]):
                cj = comps_of(surfs[j])
                sel = (hair_obj == j) & (ti_ >= 0)
                comp[sel] = j * 100000 + cj[ti_[sel]]
            hair_obj = comp
            H, W = mesh.shape
            pts = []
            for d, keep, h, p1, (cs, ks) in pt:
                for i in ks:
                    r, c = int(round(p1[i, 0])), int(round(p1[i, 1]))
                    win_ = hair_obj[max(0, r - REACH):r + REACH + 1, max(0, c - REACH):c + REACH + 1]
                    objs = sorted({'%s#%d' % (names[j // 100000], j % 100000) for j in np.unique(win_[win_ >= 0])})
                    for o in objs:
                        R['per_obj'][o] += 1.0 / max(1, len(objs))
                    if len(objs) >= 2:
                        R['boundary'] += 1
                        R['per_pair'][' + '.join(objs)] += 1
                    elif objs:
                        R['per_pair'][objs[0]] += 1
                    pts.append((r, c, objs))
            if pictures and off == offs[0]:
                pics[v] = (aq.flat_picture(kimg, tone, line), pt, pts)
    out = {}
    for v, R in res.items():
        n = max(1, R['n'])
        out[v] = dict(kinks_per_L=round(R['kinks'] / max(R['len'], 1e-9), 3), kinks=round(R['kinks'] / n, 2),
                      len=round(R['len'] / n, 3), at_boundary=round(R['boundary'] / max(1, R['kinks']), 3),
                      per_obj={o: round(x / n, 2) for o, x in R['per_obj'].most_common()},
                      per_pair={o: round(x / n, 2) for o, x in R['per_pair'].most_common(12)})
    return out, pics


def picture(pics, path):
    from PIL import Image, ImageDraw
    tiles = []
    for v, (img, pt, pts) in pics.items():
        im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).convert('RGB')
        dr = ImageDraw.Draw(im)
        for d, keep, h, p1, _ in pt:
            for i in range(len(p1) - 1):
                if keep[i]:
                    dr.line([(p1[i, 1], p1[i, 0]), (p1[i + 1, 1], p1[i + 1, 0])], fill=(40, 90, 240))
        for r, c, objs in pts:
            col = (230, 20, 230) if len(objs) >= 2 else (240, 140, 0)
            dr.ellipse([c - 4, r - 4, c + 4, r + 4], outline=col, width=2)
            dr.text((c + 5, r - 6), '/'.join(o.replace('hair_', '') for o in objs)[:40], fill=(0, 0, 0))
        dr.text((4, 4), v, fill=(0, 0, 0))
        tiles.append(im)
    W = sum(t.size[0] for t in tiles); H = max(t.size[1] for t in tiles)
    can = Image.new('RGB', (W, H), (255, 255, 255))
    x = 0
    for t in tiles:
        can.paste(t, (x, 0)); x += t.size[0]
    can.save(path)


if __name__ == '__main__':
    a = sys.argv[1:]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    from charkit import bundle
    from charkit.render.calibrate import OFFSETS
    B = bundle.load(os.path.join(a[0], 'bundle'))
    if opt('--pieces'):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from splice2x2 import splice
        B = splice(B, opt('--pieces'))
    n = int(opt('--n', 6))
    views = tuple(opt('--views', 'back').split(','))
    for k_ in ('--png', '--json'):
        if opt(k_):
            os.makedirs(os.path.dirname(os.path.abspath(opt(k_))), exist_ok=True)
    out, pics = run(B, OFFSETS[:n], views, pictures=bool(opt('--png')))
    print(json.dumps(out, indent=1))
    if opt('--png'):
        picture(pics, opt('--png'))
    if opt('--json'):
        json.dump(out, open(opt('--json'), 'w'), indent=1)
