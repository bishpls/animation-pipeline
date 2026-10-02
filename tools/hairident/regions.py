"""The drawn locks per view as one partition for the identity work (tool/hairident): the lock truth's named locks
(charkit/refs/clawd/hair_locks_truth.npz: side locks, hem flicks, strands) first, then the splitter's locks (the
produced hair_split) over the rest of the side-lock and lower-back hair, each a region of its own.

    regions(I, masks) -> {view: dict(img (int32, 0 none, k + 1 = ids[k]), ids [..], info {id: text}, family {id: f})}
"""
import json, os, sys
import numpy as np
from scipy import ndimage

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from charkit import hairlocks as hk

VIEWS = ('front', 'three_quarter', 'profile', 'back')
TRUTH_FAMS = ('side_locks', 'lower_back', 'flyaways')
SPLIT_FAMS = ('side_locks', 'lower_back')
TOP_L = 0.25              # L: see regions()
MIN_L2 = 0.006             # L^2: a splitter part smaller than this is no region (too small to be a lock here)
TRUTH = 'charkit/refs/clawd/hair_locks_truth.npz'
SPLIT = 'charkit/out/clawd/hair/split/hairsplit.json'


def load_truth():
    T, TL, meta = hk.load_truth(os.path.join(ROOT, TRUTH))
    return T, TL, meta


def regions(I, masks, split=SPLIT):
    from charkit.geom import lockshell as ls
    T, TL, meta = load_truth()
    S = ls.load_split(os.path.join(ROOT, split))
    ppl = I['ppl']
    out = {}
    for v in VIEWS:
        d = I['views'][v]
        hair = d['hair']
        t = hk.fill_walls(T[v], hair)
        img = np.zeros(hair.shape, np.int32)
        ids, info, fam = [], {}, {}
        taken = np.zeros(hair.shape, bool)
        for i, lab in enumerate(TL[v]):
            f = hk.family_of(lab)
            m = t == i
            if f not in TRUTH_FAMS or not m.any():
                continue
            ids.append('T:' + lab)
            img[m] = len(ids)
            info['T:' + lab] = 'the lock truth\'s %s (%s)' % (lab.split('/', 1)[1], f)
            fam['T:' + lab] = f
            taken |= m
        # the rest of the side-lock and lower-back hair, by the splitter's locks; anything the truth names (bangs,
        # ahoge, the other strands) stays out
        other = np.zeros(hair.shape, bool)
        for i, lab in enumerate(TL[v]):
            if hk.family_of(lab) not in TRUTH_FAMS:
                other |= t == i
        for pm in (d.get('pieces') or {}).values():
            other |= pm
        fm = {f: masks.get('%s__%s' % (v, f)) for f in SPLIT_FAMS}
        fm = {f: m for f, m in fm.items() if m is not None}
        sv = S['views'][v]
        simg = sv['img']
        free = hair & ~taken & ~other
        if fm:
            allow = np.zeros(hair.shape, bool)
            for m in fm.values():
                allow |= m
            free &= allow
        else:
            # a view without the families' masks (the three-quarter): the hair from TOP_L above the eye line down
            # (the crown, the bangs' tops and the buns are above it), the clips out
            free[:int(d['row_eye'] - TOP_L * ppl)] = False
            free &= ~d.get('occ', np.zeros_like(free))
        for lid in np.unique(simg[free & (simg > 0)]):
            m = free & (simg == lid)
            lab_, n = ndimage.label(m)
            for j in range(1, n + 1):
                mj = lab_ == j
                if mj.sum() < MIN_L2 * ppl ** 2:
                    continue
                rid = 'S:%d' % lid if n == 1 else 'S:%d.%d' % (lid, j)
                ff = max(fm, key=lambda f: (fm[f] & mj).sum()) if fm else None
                ids.append(rid)
                img[mj] = len(ids)
                info[rid] = 'the splitter\'s lock %d%s' % (lid, ' (%s)' % ff if ff else '')
                fam[rid] = ff
        out[v] = dict(img=img, ids=ids, info=info, family=fam)
    return out
