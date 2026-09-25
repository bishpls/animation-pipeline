"""Fast frame-by-frame checks for a rig's range-of-motion test: ONE pass (the ID pass) is enough.

    .venv/bin/python tools/romcheck2.py OUT_DIR ROM.json IDS.json [--seg name,name] [--sheet N] [--workers 8]
        OUT_DIR/romid/f00000.png ...  (engine/render.mjs --loop=romid --frames --png --framesdir=OUT_DIR/romid)
        optional OUT_DIR/rom/ (the normal look) for the worst-frames sheet; missing frames are rendered on demand by the caller

In the ID pass every layer is a flat colour, its INVENTED pixels (fills) at half brightness, the background black.
  holes     black regions enclosed by the character, except gaps drawn into the art (present at rest in the same view)
  invented  invented pixels exposed beyond the same view's rest baseline, by layer
Decoding is one table lookup per frame (packed RGB -> layer, invented), cropped to the character, across processes.
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from multiprocessing import Pool

FPS = 24


def setup(ids_p):
    global KEYS, LUT_K, LUT_V, LUT_I
    IDS = json.load(open(ids_p)); KEYS = sorted(IDS)
    ks, vs, iv = [], [], []
    for i, k in enumerate(KEYS, 1):
        for inv, c in ((0, IDS[k]), (1, [round(v * .5) for v in IDS[k]])):
            for dr in (-1, 0, 1):                                   # half colours can round either way
                for dg in (-1, 0, 1):
                    for db in (-1, 0, 1):
                        if not inv and (dr or dg or db): continue
                        ks.append((c[0] + dr) * 65536 + (c[1] + dg) * 256 + (c[2] + db)); vs.append(i); iv.append(inv)
    o = np.argsort(ks); LUT_K = np.array(ks)[o]; LUT_V = np.array(vs)[o]; LUT_I = np.array(iv, bool)[o]


def decode(path):
    a = np.array(Image.open(path).convert('RGB')); fg = a.any(2)
    ys, xs = np.nonzero(fg)
    if not len(ys): return None
    y0, y1, x0, x1 = max(ys.min() - 4, 0), ys.max() + 5, max(xs.min() - 4, 0), xs.max() + 5
    a = a[y0:y1, x0:x1].astype(np.int64); packed = a[:, :, 0] * 65536 + a[:, :, 1] * 256 + a[:, :, 2]
    j = np.clip(np.searchsorted(LUT_K, packed), 0, len(LUT_K) - 1); hit = LUT_K[j] == packed
    lab = np.where(hit, LUT_V[j], 0); inv = hit & LUT_I[j]
    return lab, inv, (x0, y0)


def analyse(args):
    f, d = args
    r = decode(os.path.join(d, 'romid', f'f{f:05d}.png'))
    if r is None: return f, None
    lab, inv, (x0, y0) = r
    bg = lab == 0; L, n = ndi.label(bg); edge = set(np.unique(np.concatenate([L[0], L[-1], L[:, 0], L[:, -1]])))
    ids = [i for i in range(1, n + 1) if i not in edge]; holes = []
    if ids:
        sz = ndi.sum(bg, L, ids); com = ndi.center_of_mass(bg, L, ids)
        holes = [(int(s), (c[1] + x0, c[0] + y0)) for s, c in zip(sz, com) if s >= 14]
    il = np.where(inv, lab, 0); cnt = np.bincount(il.ravel(), minlength=len(KEYS) + 1)
    views = {}
    for i in np.unique(lab):
        if i and ':' in KEYS[i - 1]: views[KEYS[i - 1].split(':')[0]] = views.get(KEYS[i - 1].split(':')[0], 0) + 1
    v = max(views, key=views.get) if views else 'F'
    cents = {}
    for i in np.nonzero(cnt > 60)[0]:
        if not i: continue
        yy, xx = np.nonzero(il == i); cents[int(i)] = (float(xx.mean() + x0), float(yy.mean() + y0))
    return f, (v, holes, cnt, cents)


def main():
    a = sys.argv[1:]; out, rom_p, ids_p = a[:3]
    opt = lambda k, dflt: type(dflt)(a[a.index(k) + 1]) if k in a else dflt
    ROM = json.load(open(rom_p)); setup(ids_p)
    frames = sorted(int(f[1:6]) for f in os.listdir(os.path.join(out, 'romid')) if f.endswith('.png'))
    seg_of = lambda f: next((s for s in ROM if s[1] <= f / FPS < s[2]), ROM[-1])
    if '--from-report' in a: report = json.load(open(os.path.join(out, 'report.json'))); return sheet(out, report, opt('--sheet', 18))
    with Pool(opt('--workers', 8), initializer=setup, initargs=(ids_p,)) as pool:
        res = dict(pool.map(analyse, [(f, out) for f in frames], chunksize=8))
    base = {}
    for name, t0, t1 in ROM:                                          # rest baselines per view (settled end of the segment)
        if not name.startswith('rest '): continue
        f = int((t1 - .05) * FPS)
        if f in res and res[f]: v, h, c, _ = res[f]; base[v] = (h, c)
    report = []
    for f in frames:
        if not res[f]: continue
        v, hs, cnt, cents = res[f]; bh, bc = base.get(v, ([], np.zeros_like(cnt)))
        hs = [(s, c) for s, c in hs if not any(abs(c[0] - b[1][0]) < 110 and abs(c[1] - b[1][1]) < 110 and .25 < s / b[0] < 4 for b in bh)]
        sl = sorted([(int(cnt[i] - bc[i]), KEYS[i - 1], cents.get(i, (0, 0))) for i in range(1, len(cnt)) if cnt[i] - bc[i] > 120], reverse=True)[:5]
        report.append({'f': f, 'seg': seg_of(f)[0], 'view': v, 'holes': hs, 'slivers': sl, 'score': sum(s for s, _ in hs) + .5 * sum(e for e, _, _ in sl)})
    json.dump(report, open(os.path.join(out, 'report.json'), 'w'))
    print(f'{"segment":16s} frames  holes(fr, max px)   invented exposed (fr, worst layers px)')
    for name, t0, t1 in ROM:
        R = [r for r in report if r['seg'] == name]
        if not R: continue
        hf = [r for r in R if r['holes']]; sf = [r for r in R if r['slivers']]; worst = {}
        for r in sf:
            for e, k, _ in r['slivers']: worst[k] = max(worst.get(k, 0), e)
        wl = ', '.join(f'{k} {e}' for k, e in sorted(worst.items(), key=lambda kv: -kv[1])[:3])
        print(f'{name:16s} {len(R):5d}  {len(hf):4d} {max([s for r in hf for s, _ in r["holes"]] or [0]):6d}      {len(sf):4d}  {wl}')
    print(f'{sum(1 for r in report if r["holes"] or r["slivers"])} of {len(report)} frames flagged')
    sheet(out, report, opt('--sheet', 0))


def sheet(out, report, N):
    if N:
        picked, seen = [], set()
        for r in sorted([r for r in report if r['score'] > 0], key=lambda r: -r['score']):
            if r['seg'] not in seen: picked.append(r); seen.add(r['seg'])
            if len(picked) >= N: break
        json.dump([r['f'] for r in picked], open(os.path.join(out, 'worst_frames.json'), 'w'))
        tiles = []
        for r in picked:
            p = os.path.join(out, 'rom', f'f{r["f"]:05d}.png')
            if not os.path.exists(p): continue
            im = Image.open(p).convert('RGB'); dr = ImageDraw.Draw(im)
            for s, (x, y) in r['holes']: dr.ellipse([x - 22, y - 22, x + 22, y + 22], outline=(255, 0, 255), width=4)
            for e, k, (x, y) in r['slivers']: dr.ellipse([x - 26, y - 26, x + 26, y + 26], outline=(0, 255, 0), width=4); dr.text((x + 28, y - 8), k, fill=(0, 255, 0))
            t = im.crop((480, 0, 1440, 1080)).resize((480, 540)); ImageDraw.Draw(t).text((6, 6), f'f{r["f"]} {r["seg"]}', fill=(255, 255, 0)); tiles.append(t)
        if tiles:
            cols = 6; sh = Image.new('RGB', (cols * 485, ((len(tiles) + cols - 1) // cols) * 545), 'black')
            for i, t in enumerate(tiles): sh.paste(t, ((i % cols) * 485, (i // cols) * 545))
            sh.save(os.path.join(out, 'worst.png')); print('sheet:', os.path.join(out, 'worst.png'))


if __name__ == '__main__':
    main()
