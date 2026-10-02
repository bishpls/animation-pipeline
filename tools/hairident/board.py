"""The identity round's analysis board for Michael (step 4; the coordinator's brief, 2026-10-01): the summary box, then
per view the design and each build at one scale with every lock numbered and coloured alike in every view (ours, and
the drawn targets it was assigned on the design), lock by lock (hover, click, keys) with its links to Michael's labels,
its per-view costs and its dropped joins; the held-out views; the shadow edges (close-ups and six placements, with the
known-bads); the guard (every hair piece's IoU per view).

    python tools/hairident/board.py OUT --build hull=DIR --build pilot=DIR --build cand=DIR [--build ...]
        [--grid GRID_DIR (ident_grid's: grid.json, holdout_*.npz)] [--grid-config NAME] [--term6 T6.json]
        [--known torn=DIR --known gaps=DIR] [--summary SUMMARY.json]
    python -m charkit label board OUT          serves it (127.0.0.1)
"""
import json, os, pickle, sys
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ident as idn, truth as tr
from charkit import hairlocks as hk, label
from charkit.geom import lockident as li, lockshell as ls

VIEWS = ('front', 'three_quarter', 'profile', 'back')
FAMS = ('side_locks', 'lower_back')
# 24 colours, distinct, readable on the drawing (Okabe-Ito first, then a spread of hues)
PALETTE = ['#E69F00', '#56B4E9', '#009E73', '#F0E442', '#0072B2', '#D55E00', '#CC79A7', '#882255', '#44AA99', '#117733',
           '#999933', '#AA4499', '#6699CC', '#DDCC77', '#332288', '#88CCEE', '#661100', '#EE7733', '#0077BB', '#33BBEE',
           '#EE3377', '#BBBBBB', '#009988', '#CC3311']


def _opt(a, k, d=None):
    return a[a.index(k) + 1] if k in a else d


def _opts(a, k):
    return [a[i + 1] for i, x in enumerate(a) if x == k]


def crops():
    T = json.load(open(os.path.join(ROOT, 'charkit/out/hairident/label/task.json')))
    return {v['id']: v['crop'] for v in T['views']}


def rings(mask, crop):
    r0, c0, H, W = crop
    m = mask[r0:r0 + H, c0:c0 + W]
    return label.mask_polygons(m, 0.8) if m.any() else []


def targets_fn():
    """the shells' drawn targets per view and family (lockident.Scene.targets without a fitting context)."""
    from charkit import manifest
    spec = manifest.resolve(json.load(open(os.path.join(ROOT, 'charkit/spec/clawd.json'))))
    Z = np.load(manifest.produced(spec, 'hair_layers'))

    class T_:
        pass
    t = T_()
    t.o, t.S, t.masks = dict(ls.DEFAULT), ls.load_split(manifest.produced(spec, 'hair_split')), {k: Z[k] for k in Z.files}
    cache = {}

    def get(vn, fam):
        if (vn, fam) not in cache:
            cache[(vn, fam)] = {tuple(x['id']): x['mask'] for x in li.Scene.targets(t, vn, fam)}
        return cache[(vn, fam)]
    return get


def build_data(label_, d, C, tget, T):
    """one build: its locks numbered (the side locks and the lower back's pieces, the shells among them), per view its
    z-buffered locks as rings and a picture, its shells' assigned targets as rings, per lock its fit and its links."""
    img, names, ppl = hk.build_locks(d)
    P = json.load(open(os.path.join(d, 'geom', 'hair_pieces', 'pieces.json')))
    rep = (P.get('report') or {}).get('lock_shells') or {}
    pieces = {p['name']: p['family'] for p in P['pieces']}
    nlock = {n: (P['report'].get('pieces') or {}).get(n, {}).get('locks', 0) for n in pieces}
    shells = rep.get('locks') or []
    # each shell's (piece, lock index): the side pieces hold their side's shells in the report's order; a laid-over
    # group's shells come after its family piece's wedges
    where = {}
    by_piece = {}
    for x in shells:
        fam = x['name'].split(':')[0]
        if fam == 'side_locks':
            pc = 'side_lock_' + x['side']
        else:
            pc = [n for n, f in pieces.items() if f == fam.rsplit('_', 1)[0] or fam.startswith(f)][0]
        by_piece.setdefault(pc, []).append(x)
    for pc, xs in by_piece.items():
        n0 = nlock.get(pc, len(xs)) - len(xs)
        for j, x in enumerate(xs):
            where['%s.%d' % (pc, n0 + j)] = x
    # the shells first (the identity's subjects), then the hull pieces' wedges
    codes = sorted([c for c, nm in names.items() if nm.split('/')[0] in FAMS],
                   key=lambda c: (names[c].split('/', 1)[1] not in where, (where.get(names[c].split('/', 1)[1]) or {}).get(
                       'name', ''), names[c]))
    locks, num = {}, {}
    for k, c in enumerate(codes, 1):
        nm = names[c]
        key = nm.split('/', 1)[1]
        x = where.get(key)
        num[c] = k
        info = dict(n=k, colour=PALETTE[(k - 1) % len(PALETTE)], piece=key, family=nm.split('/')[0],
                    shell=bool(x), name=(x or {}).get('name', key))
        if x:
            info.update(views=x.get('views'), cost=x.get('cost_px'), iou=x.get('iou'), dropped=x.get('dropped') or [],
                        twist=x.get('twist_deg'))
            asg = dict(x.get('assign') or {})
            if not asg:                      # (the pilot's: the primary from the name, the joined views from assoc)
                pv = {'f': 'front', 'p': 'profile', 'b': 'back', 't': 'three_quarter'}[x['name'].split(':')[1][0]]
                lid, j = x['name'].split(':')[1][1:].split('.')
                asg[pv] = [int(lid), int(j)]
                for vn, a in (x.get('assoc') or {}).items():
                    if a.get('status') == 'joined':
                        asg[vn] = a['target']
                info['assoc'] = {vn: a.get('status') for vn, a in (x.get('assoc') or {}).items()}
            info['assign'] = asg
        locks[k] = info
    views = {}
    masks_for_score = {k: dict(name=locks[k]['name'], assign={}) for k in locks}
    for v in VIEWS:
        cr = C[v]
        L = img[v]
        ours, drawn = {}, {}
        for c in codes:
            k = num[c]
            rr = rings(L == c, cr)
            if rr:
                ours[k] = rr
            a = locks[k].get('assign', {}).get(v)
            if a is not None:
                fam = 'lower_back' if locks[k]['name'].startswith('lower_back') else 'side_locks'
                m = tget(v, fam).get(tuple(a))
                if m is not None:
                    drawn[k] = rings(m, cr)
                    masks_for_score[k]['assign'][v] = m
        # the picture: ours, every lock in its colour, the rest of the hair grey
        r0, c0, H, W = cr
        Lc = L[r0:r0 + H, c0:c0 + W]
        pic = np.full((H, W, 3), 238, np.uint8)
        for c in np.unique(Lc[Lc > 0]):
            m = Lc == c
            if c in num:
                h = PALETTE[(num[c] - 1) % len(PALETTE)].lstrip('#')
                pic[m] = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
            else:
                pic[m] = (190, 180, 172)
        p = 'img/%s_%s.png' % (label_, v)
        Image.fromarray(pic).save(os.path.join(OUT, p))
        views[v] = dict(img=p, ours=ours, drawn=drawn)
    # the links: the shells' assigned targets scored against Michael's labels (lock -> items, per view verdicts)
    sc = idn.score([dict(name=str(k), assign=m['assign']) for k, m in masks_for_score.items() if m['assign']], T)
    for item, r in sc['items'].items():
        if r['lock'] is None:
            continue
        k = int(r['lock'])
        locks[k].setdefault('links', []).append(dict(item=item, number=T[item]['number'], title=T[item]['title'],
                                                     cover=r['cover'], views=r['views']))
    return dict(label=label_, locks=locks, views=views, counts=sc['counts'].get('all', {}),
                fam_counts={k: v for k, v in sc['counts'].items() if k.startswith('fam:')},
                fitted_2plus=rep.get('fitted_2plus'), n_shells=len(shells))


def michael(T, C):
    """Michael's labels per view: each item's region (home or answer) as rings, or its points."""
    out = {v: {} for v in VIEWS}
    for k, q in T.items():
        hv, H = q['home']
        out[hv][q['number']] = dict(rings=rings(H, C[hv]), home=True, title=q['title'])
        for v, a in q['views'].items():
            if isinstance(a, str):
                continue
            if isinstance(a, list):
                r0, c0 = C[v][0], C[v][1]
                out[v][q['number']] = dict(points=[[x - c0, y - r0] for x, y in a], title=q['title'])
            else:
                out[v][q['number']] = dict(rings=rings(a, C[v]), title=q['title'])
    return out


def holdout(grid_dir, cfg, C):
    """the held-out projections (ident.py's holdout_VIEW.npz) and the in-fit vs held-out numbers."""
    G = json.load(open(os.path.join(grid_dir, 'grid.json')))[cfg]
    out = dict(rows=[], views={})
    for v in VIEWS:
        h = (G.get('holdout') or {}).get(v)
        if not h:
            continue
        out['rows'].append(dict(view=v, in_fit=h.get('in_fit'), held_out=h.get('score'), assigned=h.get('assigned'),
                                iou=h.get('iou_mean')))
        p = os.path.join(grid_dir, 'holdout_%s.npz' % v)
        if os.path.exists(p):
            Z = np.load(p)
            lab = Z['lab']
            out['views'][v] = {int(k): rings(lab == k, C[v]) for k in np.unique(lab[lab > 0])}
            out['views'][v] = {k: r for k, r in out['views'][v].items() if r}
    out['fit'] = dict(n=G['fit'].get('n'), fitted_2plus=G['fit'].get('fitted_2plus'),
                      counts=G['fit']['score']['counts'].get('all'))
    return out


def shadows(builds, known, term6):
    """the shadow edges' close-ups (charkit.reviewpage's hair window, all four views) for the design, the builds and
    the known-bads, and art_terminator_hair at six placements beside them."""
    from charkit import reviewpage as rp
    rp.REGIONS['hair4'] = ('the hair, all four views', VIEWS, 'design', (-1.0, 1.0, 1.2, -1.0), 200)
    page = rp.Page(OUT)
    page.manifest = os.path.join(ROOT, 'charkit/refs/clawd/manifest.json')
    bl = [dict(label=l, path=d) for l, d in builds + known]
    cr = [rp.build_crops(page, b['path'], k) for k, b in enumerate(bl)]
    rows = {}
    for v in VIEWS:
        row = rp.closeup(page, 'hair4', v, bl, cr)
        rows[v] = [dict(src=os.path.relpath(p, OUT), cap=c) for p, c, _ in row]
    return dict(rows=rows, term6=term6)


def guard(builds):
    out = {}
    for l, d in builds:
        q = json.load(open(os.path.join(d, 'qa', 'qa.json')))
        out[l] = dict(iou=q.get('hair_pieces', {}).get('iou', {}),
                      checks={k: q['checks'].get(k) for k in idn_checks() if k in q['checks']})
    return out


def idn_checks():
    return ['art_terminator_hair', 'art_peeks_hair', 'hair_back_lines', 'hair_back_hem', 'hair_lock_lines_profile',
            'hair_lock_lines_three_quarter', 'hair_noise', 'hair_folds', 'hair_penetration', 'hair_strokes_front_dir',
            'hair_strokes_profile_dir', 'hair_strokes_three_quarter_dir', 'scalp_px', 'body_front_iou_hair',
            'body_three_quarter_iou_hair', 'body_profile_iou_hair', 'body_back_iou_hair']


def main(a):
    global OUT
    OUT = os.path.abspath(a[0])
    os.makedirs(os.path.join(OUT, 'img'), exist_ok=True)
    builds = [x.split('=', 1) for x in _opts(a, '--build')]
    known = [x.split('=', 1) for x in _opts(a, '--known')]
    C = crops()
    T = tr.load(os.path.join(ROOT, 'charkit/refs/clawd/hair_lock_links.json'))
    I = pickle.load(open(os.path.join(ROOT, 'charkit/out/hairsplit/inputs.pkl'), 'rb'))
    design = {}
    for v in VIEWS:
        r0, c0, H, W = C[v]
        p = 'img/design_%s.png' % v
        Image.fromarray((np.clip(I['views'][v]['rgb'], 0, 1) * 255).astype(np.uint8)[r0:r0 + H, c0:c0 + W]).save(
            os.path.join(OUT, p))
        design[v] = dict(img=p, size=[W, H])
    tget = targets_fn()
    D = dict(views=list(VIEWS), design=design, michael=michael(T, C),
             builds=[build_data(l, d, C, tget, T) for l, d in builds])
    if _opt(a, '--grid'):
        D['holdout'] = holdout(_opt(a, '--grid'), _opt(a, '--grid-config'), C)
    t6 = json.load(open(_opt(a, '--term6'))) if _opt(a, '--term6') else {}
    D['shadows'] = shadows(builds, known, t6)
    D['guard'] = guard(builds + known)
    D['summary'] = json.load(open(_opt(a, '--summary'))) if _opt(a, '--summary') else {}
    json.dump(D, open(os.path.join(OUT, 'data.json'), 'w'))
    import shutil
    shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'board.html'), os.path.join(OUT, 'index.html'))
    print('wrote', OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
