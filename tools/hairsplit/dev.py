"""A development loop for the splitter: run it on the design (the inputs cached), score each stage against the lock
truth, and draw per view: the strokes | the cells | the locks | the truth.

    python tools/hairsplit/dev.py OUT_DIR [--views front,back] [--stage locks] [--set K=V ...] [--no-pics]
"""
import json, os, pickle, sys, time
import numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
from charkit import hairsplit as hs, hairlocks as hk, manifest
import pics

CACHE = os.path.join(ROOT, 'charkit/out/hairsplit/inputs.pkl')


def load_inputs():
    spec = manifest.resolve(json.load(open(os.path.join(ROOT, 'charkit/spec/clawd.json'))))
    return hs.inputs(spec, cache=CACHE)


def draw_view(S, T, labels, out):
    box = S.box
    rgb = S.rgb
    base = (rgb * 255).astype(np.uint8)
    # 1: strokes
    a = base.copy()
    a[S.ink] = [0, 0, 0]
    a[S.ext & ~S.ink] = [255, 0, 0]
    if hasattr(S, 'lockwalls'):
        a[S.lockwalls & ~S.walls] = [0, 200, 0]
    # 2: flow streaks over the hair (a line every 12 px)
    b = (0.5 * base + 0.5 * 255).astype(np.uint8)
    b[~S.H] = [255, 255, 255]
    # 3: cells
    c = pics.colour(S.cells, rgb, 0.7, seed=3)
    c[pics.edges(S.cells) & S.H] = [0, 0, 0]
    # 4: locks
    d = pics.colour(S.locks, rgb, 0.7, seed=5)
    d[pics.edges(S.locks) & S.H] = [0, 0, 0]
    # 4b: the tips stage
    d2 = pics.colour(S.locks_tips, rgb, 0.7, seed=5)
    d2[pics.edges(S.locks_tips) & S.H] = [0, 0, 0]
    Image.fromarray(pics.zoom(d2, 2)).save(out.replace('.png', '_tipsstage.png'))
    # 4c: the regions (cut by the lock walls) with the tips' seeds
    if hasattr(S, 'regions'):
        g = pics.colour(S.regions, rgb, 0.7, seed=9)
        g[pics.edges(S.regions) & S.H] = [0, 0, 0]
        for m in S.seed_masks.values():
            g[m] = [255, 255, 255]
        g = Image.fromarray(pics.zoom(g, 2))
        dg = ImageDraw.Draw(g)
        for t_ in S.tip_list:
            r, cc = t_['rc']
            dg.ellipse([(cc * 2 - 4, r * 2 - 4), (cc * 2 + 4, r * 2 + 4)], outline=(255, 0, 0), width=2)
        g.save(out.replace('.png', '_regions.png'))
    # 5: truth
    t = T[box[0]:box[1], box[2]:box[3]]
    tt = np.where(t >= 0, t + 1, 0)
    e = pics.colour(tt, rgb, 0.7, seed=11)
    e[t == -2] = (0.5 * e[t == -2]).astype(np.uint8)
    k = 2
    ims = [Image.fromarray(pics.zoom(x, k)) for x in (a, b, c, d, e)]
    dr = ImageDraw.Draw(ims[1])
    for r in range(0, S.H.shape[0], 10):
        for cc in range(0, S.H.shape[1], 10):
            if S.H[r, cc]:
                f = S.down[:, r, cc]
                dr.line([(cc * k, r * k), ((cc + 4 * f[1]) * k, (r + 4 * f[0]) * k)], fill=(0, 0, 160), width=1)
                dr.ellipse([(cc * k - 1, r * k - 1), (cc * k + 1, r * k + 1)], fill=(0, 0, 160))
    dr.ellipse([(S.crown[1] * k - 5, S.crown[0] * k - 5), (S.crown[1] * k + 5, S.crown[0] * k + 5)], outline=(255, 0, 0), width=2)
    for im in (ims[0], ims[3]):
        dr = ImageDraw.Draw(im)
        for e_ in S.ends:
            r, cc = e_['rc']
            dr.ellipse([(cc * k - 2, r * k - 2), (cc * k + 2, r * k + 2)], fill=(0, 160, 255))
    dr = ImageDraw.Draw(ims[3])
    for t_ in S.tip_list:
        r, cc = t_['rc']
        dr.ellipse([(cc * k - 4, r * k - 4), (cc * k + 4, r * k + 4)], outline=(255, 0, 0), width=2)
        ax = t_['axis'][::6]
        dr.line([(p[1] * k, p[0] * k) for p in ax], fill=(255, 255, 255), width=1)
    for n_ in S.notch_list:
        r, cc = n_['rc']
        dr.rectangle([(cc * k - 3, r * k - 3), (cc * k + 3, r * k + 3)], outline=(0, 0, 255), width=2)
    for l_, x in S.lock_info.items():
        if x.get('layer') is not None:
            r, cc = x['tip_rc']
    W = sum(i.size[0] for i in ims) + 4 * 6
    H = ims[0].size[1]
    canvas = Image.new('RGB', (W, H), (255, 255, 255))
    x = 0
    for im in ims:
        canvas.paste(im, (x, 0)); x += im.size[0] + 6
    canvas.save(out)
    for nm, im in zip(('strokes', 'flow', 'cells', 'locks', 'truth'), ims):
        im.save(out.replace('.png', '_%s.png' % nm))


if __name__ == '__main__':
    a = sys.argv[1:]
    out = a[0]
    os.makedirs(out, exist_ok=True)
    views = a[a.index('--views') + 1].split(',') if '--views' in a else None
    params = {}
    for i, q in enumerate(a):
        if q == '--set':
            k, v = a[i + 1].split('=')
            params[k] = json.loads(v)
    I = load_inputs()
    T = hk.load_truth('charkit/refs/clawd/hair_locks_truth.npz')
    res = {}
    t0 = time.time()
    splits = {}
    for name, V in I['views'].items():
        if views and name not in views:
            continue
        S = hs.Split(name, V, I['ppl'], params)
        S.pipeline()
        stages = {'cells': S.cells, 'tips': S.locks_tips, 'locks': S.locks}
        S.layers(S.locks); S.describe(S.locks)
        splits[name] = S
        for st, img in stages.items():
            res.setdefault(st, {})[name] = S.full(img.astype(np.int32))
        print(name, json.dumps(S.report), '%.1fs' % (time.time() - t0))
        if '--no-pics' not in a:
            draw_view(S, T[0][name], T[1][name], os.path.join(out, '%s.png' % name))
    if not views: np.savez_compressed(os.path.join(out, 'stages.npz'), **{'%s__%s' % (st, v): im for st, x in res.items() for v, im in x.items()})
    tabs = {}
    for st, imgs in res.items():
        r = hs.score(imgs, T)
        tabs[st] = hs.table(r)
    json.dump(tabs, open(os.path.join(out, 'scores.json'), 'w'), indent=1)
    fams = ['bangs', 'side_locks', 'lower_back', 'flyaways', 'ahoge', '_all']
    print('%-6s %-14s %s' % ('stage', 'view', ' '.join('%10s' % f for f in fams)))
    for st, tb in tabs.items():
        for v, x in tb.items():
            print('%-6s %-14s %s' % (st, v, ' '.join('%10s' % ('-' if x.get(f) is None else '%.3f' % x[f]) for f in fams)))
