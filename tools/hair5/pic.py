"""Pictures of the lab's images: per view the design, the truth's families, and each build's hair parts (a colour per
part, the parts' boundaries inked), cropped round the head at one scale.

    python tools/hair5/pic.py OUT.png NAME=OURS.npz ...
"""
import json, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from PIL import Image

FAMC = {'bangs': (.85, .2, .2), 'side_locks': (1, .8, .2), 'upper_back': (.55, .3, .9), 'lower_back': (1, .5, .7),
        'buns': (.2, .4, 1), 'bun_L': (.2, .4, 1), 'bun_R': (.1, .6, 1), 'ahoge': (.1, .8, .7), 'flyaways': (.5, .9, .1)}


def load(path):
    Z = np.load(path)
    return {k: Z[k] for k in Z.files if k not in ('names', 'pieces', 'ppl')}, json.loads(str(Z['names'])), \
        json.loads(str(Z['pieces'])), float(Z['ppl'])


def crop_box(masks, pad=12):
    m = np.zeros_like(next(iter(masks)), bool)
    for x in masks:
        m |= x
    r, c = np.nonzero(m)
    return max(0, r.min() - pad), r.max() + pad, max(0, c.min() - pad), c.max() + pad


def boundaries(img):
    b = np.zeros(img.shape, bool)
    b[:-1] |= img[:-1] != img[1:]
    b[1:] |= img[:-1] != img[1:]
    b[:, :-1] |= img[:, :-1] != img[:, 1:]
    b[:, 1:] |= img[:, :-1] != img[:, 1:]
    return b


def parts_rgb(img, pieces):
    rng = np.random.default_rng(3)
    out = np.ones(img.shape + (3,))
    out[img == 1] = (.93, .9, .86)
    for i, pc in enumerate(pieces):
        m = img == 100 + i
        if m.any():
            base = np.array(FAMC.get({'side_lock_L': 'side_locks', 'side_lock_R': 'side_locks', 'bun_L': 'buns',
                                      'bun_R': 'buns'}.get(pc, pc), (.5, .5, .5)))
            out[m] = np.clip(base * rng.uniform(0.6, 1.15) + rng.uniform(-.08, .08, 3), 0, 1)
    b = boundaries(img) & (img >= 100)
    out[b] = (0.1, 0.05, 0.05)
    return out


def truth_rgb(t, sets, shape):
    out = np.ones(shape + (3,))
    for i, st in enumerate(sets):
        m = t == i
        if m.any():
            out[m] = FAMC.get(st[0], (.5, .5, .5))
    return out


if __name__ == '__main__':
    sys.path.insert(0, os.path.join(ROOT, 'tools', 'hair5'))
    import ctx
    out = sys.argv[1]
    sets = [a.split('=', 1) for a in sys.argv[2:]]
    loaded = [(n, load(p)) for n, p in sets]
    from charkit import calibrate
    B = calibrate.load_bundle(os.path.join(ROOT, 'charkit/out/h4n_nocrown'))
    Dz = ctx.design(B)
    T, tsets, _ = Dz['truth']
    rows = []
    for v in ctx.VIEWS:
        d = Dz['dv'].get(v)
        if d is None:
            continue
        hair = [(L[0][v] >= 100) for _, L in loaded if v in L[0]] + [T[v] >= 0] if v in T else []
        r0, r1, c0, c1 = crop_box(hair)
        tiles = [d['rgb'][r0:r1, c0:c1, :3]]
        raw = d['raw'][r0:r1, c0:c1]
        ln = np.ones(raw.shape + (3,)); ln[raw == 4] = 0; ln[(raw == 2)] = (1, .85, .75)
        tiles.append(ln)
        if v in T:
            tiles.append(truth_rgb(T[v][r0:r1, c0:c1], tsets, raw.shape))
        for _, (img, names, pieces, ppl) in loaded:
            tiles.append(parts_rgb(img[v][r0:r1, c0:c1], pieces))
        tiles = [np.pad(np.asarray(t, float), ((0, 0), (0, 6), (0, 0)), constant_values=1) for t in tiles]
        rows.append(np.concatenate(tiles, 1))
    W = max(r.shape[1] for r in rows)
    rows = [np.pad(r, ((0, 8), (0, W - r.shape[1]), (0, 0)), constant_values=1) for r in rows]
    im = (np.clip(np.concatenate(rows, 0), 0, 1) * 255).astype(np.uint8)
    Image.fromarray(im).resize((im.shape[1] * 2, im.shape[0] * 2), Image.NEAREST).save(out)
    print(out, im.shape, 'columns: design | drawn lines | truth | ' + ' | '.join(n for n, _ in sets))
