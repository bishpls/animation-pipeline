"""Frame-by-frame checks for a rig's range-of-motion test (projects/<film>/src/rom.js): three passes of the same frames.

    .venv/bin/python tools/romcheck.py OUT_DIR ROM.json IDS.json [--sheet N]
        OUT_DIR/{rom,rommag,romid}/f00000.png ...   (engine/render.mjs --loop=rom|rommag|romid --frames --png --framesdir=...)
        ROM.json: [[segment, t0, t1], ...] (window.ROM)   IDS.json: {"view:layer": [r, g, b]} (window.RIG_IDS)

Checks, per frame:
  holes    background (magenta) enclosed by the character, except gaps drawn into the art (present at rest in the same view)
  slivers  thin parts (< ~2r px wide) of a layer that are exposed now but not at rest in the same view: the layer behind
           peeking out along an edge (doubled lines, flat-fill slivers)
Writes OUT_DIR/report.json and prints a per-segment summary; --sheet N: OUT_DIR/worst.png with the N worst frames annotated.
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

FPS = 24
out, rom_p, ids_p = sys.argv[1:4]
opt = lambda k, d: type(d)(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
ROM = json.load(open(rom_p)); IDS = json.load(open(ids_p))
col2key = {tuple(v): k for k, v in IDS.items()}
keys = sorted(IDS); kidx = {k: i + 1 for i, k in enumerate(keys)}
seg_of = lambda f: next((s for s in ROM if s[1] <= f / FPS < s[2]), ROM[-1])
nframes = len([f for f in os.listdir(os.path.join(out, 'romid')) if f.endswith('.png')])
R_THIN = opt('--r', 3); MIN_SLIVER = opt('--min', 120); MIN_HOLE = 14


def idmap(f, invented=False):
    a = np.array(Image.open(os.path.join(out, 'romid', f'f{f:05d}.png')).convert('RGB')).astype(int)
    lab = np.zeros(a.shape[:2], np.int32); flat = a[:, :, 0] * 65536 + a[:, :, 1] * 256 + a[:, :, 2]; inv = np.zeros(a.shape[:2], bool)
    for c, k in col2key.items():
        lab[flat == c[0] * 65536 + c[1] * 256 + c[2]] = kidx[k]
        h = [round(v * .5) for v in c]; m = (np.abs(a[:, :, 0] - h[0]) <= 1) & (np.abs(a[:, :, 1] - h[1]) <= 1) & (np.abs(a[:, :, 2] - h[2]) <= 1)
        lab[m] = kidx[k]; inv |= m                                  # invented pixels draw at half brightness
    return (lab, inv) if invented else lab


def view_of(lab):
    vs = {}
    for i in np.unique(lab):
        if i and ':' in keys[i - 1]: vs[keys[i - 1].split(':')[0]] = vs.get(keys[i - 1].split(':')[0], 0) + 1
    return max(vs, key=vs.get) if vs else 'F'


def holes(f):
    a = np.array(Image.open(os.path.join(out, 'rommag', f'f{f:05d}.png')).convert('RGB')).astype(int)
    mag = (a[:, :, 0] > 200) & (a[:, :, 1] < 70) & (a[:, :, 2] > 200)
    lab, n = ndi.label(mag); edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
    ids = [i for i in range(1, n + 1) if i not in edge]
    if not ids: return []
    sz = ndi.sum(mag, lab, ids); com = ndi.center_of_mass(mag, lab, ids)
    return [(int(s), (c[1], c[0])) for s, c in zip(sz, com) if s >= MIN_HOLE]


def thin_by_layer(lab):
    res = {}; st = ndi.generate_binary_structure(2, 1); pad = R_THIN + 2
    for i, sl in enumerate(ndi.find_objects(lab), 1):
        if sl is None: continue
        y0, y1 = max(sl[0].start - pad, 0), min(sl[0].stop + pad, lab.shape[0]); x0, x1 = max(sl[1].start - pad, 0), min(sl[1].stop + pad, lab.shape[1])
        m = lab[y0:y1, x0:x1] == i; th = m & ~ndi.binary_opening(m, structure=st, iterations=R_THIN)
        if th.any():
            full = np.zeros(lab.shape, bool); full[y0:y1, x0:x1] = th; res[i] = full
    return res


# baselines per view: from the "rest <view>" segments
base_holes, base_inv = {}, {}
def inv_counts(lab, inv):
    il = np.where(inv, lab, 0); c = np.bincount(il.ravel(), minlength=len(keys) + 1); return c
for name, t0, t1 in ROM:                            # baselines: the settled end of each view's rest segment
    if not name.startswith('rest '): continue
    f = int((t1 - .05) * FPS); lab, inv = idmap(f, True); v = view_of(lab)
    base_holes[v] = holes(f); base_inv[v] = inv_counts(lab, inv)
report = []
for f in range(nframes):
    lab, inv = idmap(f, True); v = view_of(lab); seg = seg_of(f)[0]
    hs = [(s, c) for s, c in holes(f) if not any(abs(c[0] - b[1][0]) < 110 and abs(c[1] - b[1][1]) < 110 and .25 < s / b[0] < 4 for b in base_holes.get(v, []))]
    sl = []                                                         # INVENTED pixels exposed beyond the view's rest baseline, by layer
    ilab = np.where(inv, lab, 0); cnt = inv_counts(lab, inv); b0 = base_inv.get(v, np.zeros_like(cnt))
    for i, bb in enumerate(ndi.find_objects(ilab), 1):
        if bb is None: continue
        n = int(cnt[i] - b0[i])
        if n > MIN_SLIVER:
            ys, xs = np.nonzero(ilab[bb] == i); sl.append((n, keys[i - 1], (float(xs.mean() + bb[1].start), float(ys.mean() + bb[0].start))))
    score = sum(s for s, _ in hs) + sum(e for e, _, _ in sl) * .5
    report.append({'f': f, 'seg': seg, 'view': v, 'holes': hs, 'slivers': sorted(sl, reverse=True)[:5], 'score': score})
json.dump(report, open(os.path.join(out, 'report.json'), 'w'))
# summary per segment
print(f'{"segment":16s} frames  holes(fr, max px)   invented exposed (fr, worst layers px)')
for name, t0, t1 in ROM:
    R = [r for r in report if r['seg'] == name]
    hf = [r for r in R if r['holes']]; sf = [r for r in R if r['slivers']]
    worst = {}
    for r in sf:
        for e, k, _ in r['slivers']: worst[k] = max(worst.get(k, 0), e)
    wl = ', '.join(f'{k} {e}' for k, e in sorted(worst.items(), key=lambda kv: -kv[1])[:3])
    print(f'{name:16s} {len(R):5d}  {len(hf):4d} {max([s for r in hf for s, _ in r["holes"]] or [0]):6d}      {len(sf):4d}  {wl}')
tot = sum(1 for r in report if r['holes'] or r['slivers'])
print(f'{tot} of {len(report)} frames flagged')
N = opt('--sheet', 0)
if N:
    worst = sorted([r for r in report if r['score'] > 0], key=lambda r: -r['score'])
    picked, seen = [], set()
    for r in worst:                                  # one per segment first, then the rest
        if r['seg'] not in seen: picked.append(r); seen.add(r['seg'])
        if len(picked) >= N: break
    tiles = []
    for r in picked:
        im = Image.open(os.path.join(out, 'rom', f'f{r["f"]:05d}.png')).convert('RGB'); d = ImageDraw.Draw(im)
        for s, (x, y) in r['holes']: d.ellipse([x - 22, y - 22, x + 22, y + 22], outline=(255, 0, 255), width=4)
        for e, k, (x, y) in r['slivers']: d.ellipse([x - 26, y - 26, x + 26, y + 26], outline=(0, 255, 0), width=4); d.text((x + 28, y - 8), k, fill=(0, 255, 0))
        t = im.crop((480, 0, 1440, 1080)).resize((480, 540)); ImageDraw.Draw(t).text((6, 6), f'f{r["f"]} {r["seg"]}', fill=(255, 255, 0)); tiles.append(t)
    cols = 6; sh = Image.new('RGB', (cols * 485, ((len(tiles) + cols - 1) // cols) * 545), 'black')
    for i, t in enumerate(tiles): sh.paste(t, ((i % cols) * 485, (i // cols) * 545))
    sh.save(os.path.join(out, 'worst.png')); print('sheet:', os.path.join(out, 'worst.png'))
