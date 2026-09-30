"""The hair's locks against a hand-checked lock-level truth (tool/hairlocks, docs/workstreams/hairlocks.md).

The family truth (charkit.hairlayers' hair_truth) says which family each drawn hair pixel belongs to. This one splits the
families into the drawn locks, per view, along the drawing's lock lines, so the pieces' lock partition (the builder's
own, charkit.geom.hairpieces.locks: phi wedges cut at the lower edge's notches) and the structure labeller's lock regions
(hairlayers.lock_regions) can be compared with the drawing lock by lock.

  truth   the source (hair_locks_truth.json: per view cuts and seeds, as hair_truth.json's) -> the npz
          (charkit-hair-locks-truth/1): per view an index image into `locks` (-1 not in the truth, -2 unscored hair: the
          crown above the drawn lines, a lock the drawing doesn't close)
  score   a lock label image per view (0 none) against it: per view the lock count per family, the Hungarian-matched
          locks' IoU, their boundary distance (all and along the drawn lock lines), tip position and tip shape (the
          width profile over the last 20% of the lock's height), and the purity of each labelled region (the share in
          its dominant drawn lock: a region straddling a drawn lock line is impure)
  ours    a build's hair pieces z-buffered lock by lock on the design grids (the QA's scene: skin, eyes, mouth,
          garments and accessories occlude)

    python -m charkit hairlocks truth [SPEC]                   the npz rebuilt from its source
    python -m charkit hairlocks score BUILD [--json OUT]       a build's locks (BUILD/geom/hair_pieces) against it
"""
import json, os, sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORMAT = 'charkit-hair-locks-truth/1'
LOCK_FAMILIES = ('bangs', 'side_locks', 'upper_back', 'lower_back')
UNSCORED = 'x'
WALL_FILL = 2             # px: the drawn lines between locks (unlabelled) go to the nearest lock within this
MIN_PX = 30               # px: a labelled region smaller than this in a view is not a candidate lock there
MATCH_MIN = 0.1           # a matched pair below this IoU counts as unmatched
TIP_FRAC = 0.2            # the tip: the lock's last 20% of its height
TIP_ROWS = (0.80, 0.85, 0.90, 0.95)


def _p(path):
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


def is_label(q):
    return q == UNSCORED or ('/' in q and q.split('/', 1)[0] in LOCK_FAMILIES and len(q.split('/', 1)[1]) > 0)


def family_of(label):
    return label.split('/', 1)[0] if '/' in label else None


def truth_view(dv, vsrc, fam_truth=None, fam_sets=None):
    """one view's lock truth from its source -> (image: index into the view's labels, -1 none; labels [str];
    cut mask; problems). A region without a seed is out of the lock truth, unless the family truth's majority there is
    one of the view's `scope` families (then it is a problem: every drawn lock of the scope is labelled)."""
    from . import hairlayers as hl
    reg, regions, cut, problems = hl.truth_regions(dv, vsrc, valid=is_label)
    scope = set(vsrc.get('scope', [])) if vsrc.get('complete', True) else set()
    keep = []
    for p in problems:
        if ': no seed' not in p:
            keep.append(p)
            continue
        if fam_truth is None or not scope:
            continue
        # 'region N (A px) at (x, y): no seed'
        rid = int(p.split()[1])
        m = reg == rid
        f = fam_truth[m]
        f = f[f >= 0]
        if len(f):
            top = np.bincount(f).argmax()
            if fam_sets[top][0] in scope:
                keep.append(p + ' (in scope: %s)' % '|'.join(fam_sets[top]))
    labels, img = [], np.full(reg.shape, -1, np.int32)
    for rid, st, _ in regions:
        if len(st) != 1:
            keep.append('region %d: one label a lock (%s)' % (rid, '|'.join(st)))
            continue
        q = st[0]
        if q == UNSCORED:
            img[reg == rid] = -2
            continue
        if q not in labels:
            labels.append(q)
        img[reg == rid] = labels.index(q)
    return img, labels, cut, keep


def build_truth(spec, src_path, out_path, fam_path=None, log=print):
    """the lock truth's source -> its npz (charkit-hair-locks-truth/1). Stops on any problem."""
    from . import hairlayers as hl
    src = json.load(open(_p(src_path)))
    dv, ppl = hl.design(spec)
    FT = hl.load_truth(fam_path) if fam_path else None
    imgs, labels, problems, n = {}, {}, [], 0
    for view, vs in src['views'].items():
        ft = FT[0].get(view) if FT else None
        img, lab, _, pr = truth_view(dv[view], vs, ft, FT[1] if FT else None)
        problems += ['%s: %s' % (view, q) for q in pr]
        imgs[view] = img.astype(np.int16)
        labels[view] = lab
        n += len(lab)
        log('%s: %d locks (%s), %d px, %d unscored' % (view, len(lab), ', '.join(lab), int((img >= 0).sum()),
                                                       int((img == -2).sum())))
    if problems:
        raise ValueError('the lock truth has %d problems:\n  %s' % (len(problems), '\n  '.join(problems)))
    meta = dict(format=FORMAT, name=spec.get('name'), sheet=src.get('sheet', 'body_turnaround'), ppl=ppl,
                grids={v: list(i.shape) for v, i in imgs.items()}, source=src_path, locks=n, labels=labels,
                provenance=src.get('provenance'), rules=src.get('rules'), calls=src.get('calls'),
                scope={v: vs.get('scope') for v, vs in src['views'].items()},
                tips={v: vs.get('tips', {}) for v, vs in src['views'].items()})
    np.savez_compressed(_p(out_path), meta=json.dumps(meta), **imgs)
    return meta


def load_truth(path):
    """-> ({view: image}, {view: labels}, meta)."""
    Z = np.load(_p(path))
    meta = json.loads(str(Z['meta']))
    if meta.get('format') != FORMAT:
        raise ValueError('%s: not a %s file' % (path, FORMAT))
    return {v: Z[v].astype(np.int32) for v in meta['grids']}, meta['labels'], meta


def fill_walls(img, hair, n=WALL_FILL):
    """the unlabelled hair pixels (drawn lines) within n px of a lock -> that lock (nearest)."""
    from scipy import ndimage
    lab = img >= 0
    if not lab.any():
        return img
    d, idx = ndimage.distance_transform_edt(~lab, return_indices=True)
    out = img.copy()
    m = (img == -1) & hair & (d <= n)
    out[m] = img[idx[0][m], idx[1][m]]
    return out


def fill_labels(img, mask, n=WALL_FILL):
    """a region image's unlabelled pixels within mask and n px of a region -> that region (nearest): a labeller's
    walls (the drawn lines between its regions) given to its regions, as the truth's are."""
    from scipy import ndimage
    lab = img > 0
    if not lab.any():
        return img
    d, idx = ndimage.distance_transform_edt(~lab, return_indices=True)
    out = img.copy()
    m = ~lab & mask & (d <= n)
    out[m] = img[idx[0][m], idx[1][m]]
    return out


def _boundary(m):
    from scipy import ndimage
    return m & ~ndimage.binary_erosion(m, border_value=0)


def _tip(m):
    """(row, col) of the region's tip: its lowest row, the mean column of its pixels in the lowest 2 rows."""
    ys, xs = np.nonzero(m)
    r = ys.max()
    sel = ys >= r - 1
    return float(r), float(xs[sel].mean())


def _width_profile(m, top=None):
    """the region's width (px) at TIP_ROWS of its height (from its top row to its tip) -> list."""
    ys, xs = np.nonzero(m)
    r0 = ys.min() if top is None else top
    r1 = ys.max()
    out = []
    for f in TIP_ROWS:
        r = int(round(r0 + f * (r1 - r0)))
        out.append(float(m[r].sum()))
    return out


def score_view(ours, truth, labels, hair, ppl, names=None, tips=None):
    """one view: ours (int image, 0 none: a region per lock) against the truth (index image into labels, -1 none,
    -2 unscored). names: {our code: 'family/name'} (the family decides the count per family; no names: every region
    is counted under 'regions'). tips: {label: 'cut' | 'hidden'} (those locks' tips are not the drawing's: left out of
    the tip scores). -> dict."""
    tips = tips or {}
    from scipy import ndimage
    from scipy.optimize import linear_sum_assignment
    T = fill_walls(truth, hair)
    scored = T != -2
    O = np.where(scored, ours, 0)
    tl = [i for i in range(len(labels)) if (T == i).any()]
    inscope = T >= 0
    codes, cnt = np.unique(O[O > 0], return_counts=True)
    cand = []
    for c, n in zip(codes, cnt):
        m = O == c
        ov = int((m & inscope).sum())
        if n >= MIN_PX and ov >= max(MIN_PX / 2, 0.3 * n):
            cand.append(int(c))
    M = np.zeros((len(tl), len(cand)))
    area_t = {i: int((T == i).sum()) for i in tl}
    for a, i in enumerate(tl):
        ti = T == i
        for b, c in enumerate(cand):
            oc = O == c
            inter = int((ti & oc).sum())
            if inter:
                M[a, b] = inter / int((ti | oc).sum())
    pairs = []
    if len(tl) and len(cand):
        ra, cb = linear_sum_assignment(-M)
        pairs = [(tl[a], cand[b], M[a, b]) for a, b in zip(ra, cb) if M[a, b] >= MATCH_MIN]
    # the drawn lock lines: truth boundary pixels next to another truth lock
    inner = np.zeros(T.shape, bool)
    for i in tl:
        ti = T == i
        other = ndimage.binary_dilation((T >= 0) & ~ti, iterations=2)
        inner |= _boundary(ti) & other
    per, ious, bds, bdi, tipd, tipw, ins = {}, [], [], [], [], [], []
    matched_t = {p[0] for p in pairs}
    for i, c, iou in pairs:
        ti, oc = T == i, O == c
        bt, bo = _boundary(ti), _boundary(oc)
        dto = ndimage.distance_transform_edt(~bo)
        dtt = ndimage.distance_transform_edt(~bt)
        bd = 0.5 * (dto[bt].mean() + dtt[bo].mean()) / ppl
        bin_ = inner & bt
        bdin = float(dto[bin_].mean() / ppl) if bin_.any() else None
        rt, ct = _tip(ti)
        ro, co = _tip(oc)
        top = min(np.nonzero(ti)[0].min(), np.nonzero(oc)[0].min())
        wt, wo = _width_profile(ti), _width_profile(oc)
        wdiff = float(np.mean(np.abs(np.array(wt) - np.array(wo))) / ppl)
        tp = float(np.hypot(rt - ro, ct - co) / ppl)
        # the partition alone: the pair's IoU within the truth's locks (our silhouette and family edges left out)
        iin = float((ti & oc).sum() / max(1, (ti | (oc & inscope)).sum()))
        per[labels[i]] = dict(ours=names.get(c, str(c)) if names else int(c), iou=round(float(iou), 3),
                              iou_in=round(iin, 3), boundary_L=round(float(bd), 4),
                              line_L=None if bdin is None else round(bdin, 4))
        ious.append(iou); bds.append(bd); ins.append(iin)
        if tips.get(labels[i], 'drawn') == 'drawn':
            per[labels[i]].update(tip_L=round(tp, 4), tip_dz_L=round(-float(ro - rt) / ppl, 4),
                                  tip_du_L=round(float(co - ct) / ppl, 4), width_L=round(wdiff, 4),
                                  widths_truth_L=[round(w / ppl, 4) for w in wt],
                                  widths_ours_L=[round(w / ppl, 4) for w in wo])
            tipd.append(tp); tipw.append(wdiff)
        else:
            per[labels[i]]['tip'] = tips[labels[i]]
        if bdin is not None:
            bdi.append(bdin)
    for i in tl:
        if i not in matched_t:
            per[labels[i]] = dict(ours=None, iou=0.0)
    # purity: each candidate region's share in its dominant truth lock (over its pixels in the scope)
    pur_n, pur_d, purity = 0, 0, {}
    for c in cand:
        oc = (O == c) & inscope
        t_ = T[oc]
        k = np.bincount(t_).max() if len(t_) else 0
        pur_n += int(k); pur_d += int(oc.sum())
        purity[names.get(c, str(c)) if names else str(c)] = round(float(k / max(1, oc.sum())), 3)
    # best merge: each truth lock against the union of the candidates whose dominant truth lock it is
    dom = {}
    for c in cand:
        oc = (O == c) & inscope
        t_ = T[oc]
        if len(t_):
            dom.setdefault(int(np.bincount(t_).argmax()), []).append(c)
    merge = []
    for i in tl:
        ti = T == i
        u = np.isin(O, dom.get(i, [])) if dom.get(i) else np.zeros(T.shape, bool)
        merge.append(float((ti & u).sum() / max(1, (ti | u).sum())))
    fam_t, fam_o = {}, {}
    for i in tl:
        f = family_of(labels[i]); fam_t[f] = fam_t.get(f, 0) + 1
    for c in cand:
        f = family_of(names[c]) if names and c in names else 'regions'
        fam_o[f] = fam_o.get(f, 0) + 1
    n_t = len(tl)
    return dict(
        truth_locks=n_t, candidates=len(cand), matched=len(pairs), count_truth=fam_t, count_ours=fam_o,
        lock_iou=round(float(sum(ious) / max(1, n_t)), 3),            # unmatched truth locks count 0
        lock_iou_in=round(float(sum(ins) / max(1, n_t)), 3),
        lock_iou_area=round(float(sum(p[2] * area_t[p[0]] for p in pairs) / max(1, sum(area_t.values()))), 3),
        boundary_L=round(float(np.mean(bds)), 4) if bds else None,
        line_L=round(float(np.mean(bdi)), 4) if bdi else None,
        tip_L=round(float(np.mean(tipd)), 4) if tipd else None,
        tip_width_L=round(float(np.mean(tipw)), 4) if tipw else None,
        purity=round(pur_n / max(1, pur_d), 3), best_merge_iou=round(float(np.mean(merge)), 3) if merge else None,
        locks=per, purity_per=purity)


def score(ours, truth, hair, ppl, names=None, views=None):
    """ours {view: int image} against load_truth's -> {view: score_view} and 'all' (the means over the views,
    each truth lock weighing one)."""
    T, labels, meta = truth
    out = {}
    for v, t in T.items():
        if (views and v not in views) or v not in ours:
            continue
        if ours[v].shape != t.shape:
            raise ValueError('%s: ours on %s, the truth on %s' % (v, ours[v].shape, t.shape))
        nm = names.get(v) if isinstance(names, dict) and v in names else names
        out[v] = score_view(ours[v], t, labels[v], hair[v], ppl, nm, (meta.get('tips') or {}).get(v))
    vs = [r for r in out.values()]
    if vs:
        n = sum(r['truth_locks'] for r in vs)
        out['all'] = dict(truth_locks=n, matched=sum(r['matched'] for r in vs),
                          lock_iou=round(sum(r['lock_iou'] * r['truth_locks'] for r in vs) / max(1, n), 3),
                          lock_iou_in=round(sum(r['lock_iou_in'] * r['truth_locks'] for r in vs) / max(1, n), 3),
                          purity=round(float(np.mean([r['purity'] for r in vs])), 3))
    return out


def shuffled(truth_img, seed=0):
    """a known-bad partition for calibration: the truth's scope (its locks) split into as many random Voronoi cells as
    it has locks. -> int image (0 none)."""
    from scipy import ndimage
    rng = np.random.RandomState(seed)
    m = truth_img >= 0
    k = len(np.unique(truth_img[m]))
    ys, xs = np.nonzero(m)
    j = rng.choice(len(ys), k, replace=False)
    mk = np.zeros(m.shape, np.int32)
    mk[ys[j], xs[j]] = np.arange(1, k + 1)
    _, idx = ndimage.distance_transform_edt(mk == 0, return_indices=True)
    return np.where(m, mk[idx[0], idx[1]], 0)


# ------------------------------------------------------------------------------------------------------------ ours

def pieces_locks(pieces_dir, families=LOCK_FAMILIES):
    """a build's hair pieces (geom/hair_pieces: a part npz per piece with the lock index per vertex) -> [(name
    'family/piece.k', V, T)] one per lock of the mass pieces."""
    P = json.load(open(os.path.join(pieces_dir, 'pieces.json')))
    out = []
    for pc in P['pieces']:
        name, fam = pc['name'], pc['family']
        if fam not in families:
            continue
        Z = np.load(os.path.join(pieces_dir, pc['file']))
        V, T, lk = Z['V'], Z['F'], Z['lock']
        for k in np.unique(lk):
            t = T[np.all(lk[T] == k, axis=1)]
            out.append(('%s/%s.%d' % (fam, name, k), V, t))
    return out


def lock_labels(B, D, locks, views=('front', 'three_quarter', 'profile', 'back'), hair_other=None):
    """the locks z-buffered in the QA's scene (hair_pieces_measure's: skin, eyes, mouth, accessories, garments; the
    other hair pieces as hair_other [(V, T)] occlude as hair) on the design grids -> ({view: int image, 0 none},
    {code: name})."""
    from . import bodyqa, qa3d
    sc = D.sheet_context()
    As = B.assembly
    meshes = []
    V, T = B.skin().mesh('masked')[:2]
    meshes.append((V, T, np.zeros(len(T), int)))
    for o in B.objects(groups=('eye', 'mouth', 'accessory', 'garment')):
        if o.has('eval'):
            V, T = o.mesh('eval')[:2]
            meshes.append((V, T, np.zeros(len(T), int)))
    for V, T in hair_other or []:
        meshes.append((V, T, np.full(len(T), 99)))
    names = {}
    for k, (name, V, T) in enumerate(locks):
        code = 100 + k
        names[code] = name
        meshes.append((np.asarray(V, float), np.asarray(T), np.full(len(T), code)))
    dv = D.design_views()
    lab = bodyqa.zbuffer_views(meshes, sc['az3'], np.array(qa3d.iris_centres(B)), As['centre'], As['L'], sc['ppl'],
                               [v for v in views if v in dv])
    return {v: np.where(l[1] >= 100, l[1], 0).astype(np.int32) for v, l in lab.items()}, names


def build_locks(build):
    """a finished build's locks on the design grids -> ({view: image}, {code: name}, ppl)."""
    from . import bundle as bl, qa3d
    B = bl.load(os.path.join(build, 'bundle'))
    D = qa3d.Design(B)
    pdir = os.path.join(build, 'geom', 'hair_pieces')
    locks = pieces_locks(pdir)
    P = json.load(open(os.path.join(pdir, 'pieces.json')))
    other = []
    for pc in P['pieces']:
        if pc['family'] not in LOCK_FAMILIES:
            Z = np.load(os.path.join(pdir, pc['file']))
            other.append((Z['V'], Z['F']))
    img, names = lock_labels(B, D, locks, hair_other=other)
    return img, names, D.sheet_context()['ppl']


# ------------------------------------------------------------------------------------------------------------ CLI

def _spec(args):
    from . import manifest
    sp = next((a for a in args if a.endswith('.json') and 'spec' in a), 'charkit/spec/clawd.json')
    return manifest.resolve(json.load(open(_p(sp))))


def truth_main(args):
    from . import manifest
    spec = _spec(args)
    R = manifest.load(spec['ref']['manifest'])['references']
    ent = R['hair_locks_truth']
    meta = build_truth(spec, ent['source'], ent['path'], R['hair_truth']['path'])
    print('%s: %d locks' % (ent['path'], meta['locks']))


def score_main(args):
    from . import manifest
    build = args[0]
    spec = _spec(args[1:])
    R = manifest.load(spec['ref']['manifest'])['references']
    truth = load_truth(R['hair_locks_truth']['path'])
    img, names, ppl = build_locks(build)
    hair = {v: np.ones(t.shape, bool) for v, t in truth[0].items()}
    r = score(img, truth, hair, ppl, names)
    for v, x in r.items():
        if v == 'all':
            continue
        print('%-14s locks %d (ours %s) matched %d  lock IoU %.3f  boundary %s L  lines %s L  tip %s L  tip width %s L  '
              'purity %.3f' % (v, x['truth_locks'], x['count_ours'], x['matched'], x['lock_iou'], x['boundary_L'],
                               x['line_L'], x['tip_L'], x['tip_width_L'], x['purity']))
    if '--json' in args:
        json.dump(r, open(_p(args[args.index('--json') + 1]), 'w'), indent=1)
    return r


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return 0
    if args[0] == 'truth':
        return truth_main(args[1:])
    if args[0] == 'score':
        score_main(args[1:])
        return 0
    print(__doc__); return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
