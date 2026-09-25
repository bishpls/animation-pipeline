"""Drawn variants of a rig's face patches (blinks, visemes): GPT Image edits a head crop, the edit is registered back onto
the crop, and the same patch shapes the rig uses are cut from it, so a variant swaps in exactly where the original sat.

    .venv/bin/python tools/variants.py SPEC.json

SPEC: {"image": base.png, "crop": [x0, y0, size], "out": "build dir", "patches": {"eye_L": [cx, cy, rx, ry], ...},
       "feather": 10, "variants": {"eyes_closed": {"prompt": "...", "patches": ["eye_L", "eye_R"]}, ...}}
Writes <out>/<patch>@<variant>.png (cropped like the build's own patch) and <out>/variants.json {patch: {variant: file}}.
Edits are cached in <out>/_edits/<variant>.png; delete one to redo it.
"""
import json, os, sys, subprocess
import numpy as np, cv2
from PIL import Image
from scipy import ndimage as ndi

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEEP = ("Keep EVERYTHING else exactly identical: the same face shape, hair, hairpin, head angle, position and size in the frame, "
        "the same crisp anime lineart and cel shading and the same colours. Only the part named changes. Transparent background.")


def main(spec):
    S = json.load(open(spec)); base_dir = os.path.dirname(os.path.abspath(spec))
    img = np.array(Image.open(os.path.join(base_dir, S['image'])).convert('RGBA'))
    x0, y0, n = S['crop']; crop = img[y0:y0 + n, x0:x0 + n]
    out = os.path.join(base_dir, S['out']); ed = os.path.join(out, '_edits'); os.makedirs(ed, exist_ok=True)
    cpath = os.path.join(ed, '_crop.png'); Image.fromarray(crop).save(cpath)
    H, W = crop.shape[:2]; yy, xx = np.mgrid[:H, :W]
    def ell(p): cx, cy, rx, ry = p; return ((xx - (cx - x0)) / rx) ** 2 + ((yy - (cy - y0)) / ry) ** 2 <= 1
    changed = np.zeros((H, W), bool)
    for p in S['patches'].values(): changed |= ndi.binary_dilation(ell(p), iterations=30)
    g = lambda a: ((a[:, :, :3].astype(np.float32) @ [.299, .587, .114]) * (a[:, :, 3] / 255) + 200 * (1 - a[:, :, 3] / 255)).astype(np.float32)
    table = json.load(open(os.path.join(out, 'variants.json'))) if os.path.exists(os.path.join(out, 'variants.json')) else {}
    for vname, V in S['variants'].items():
        ep = os.path.join(ed, vname + '.png')
        if not os.path.exists(ep):
            subprocess.run([os.path.join(ROOT, '.venv', 'bin', 'python'), os.path.join(ROOT, 'tools', 'gptimage.py'), 'Edit this character close-up. ' + V['prompt'] + ' ' + S.get('keep', KEEP),
                            ep, '--model', S.get('model', 'gpt-image-2.5-sunburst'), '--size', f'{n}x{n}', '--quality', S.get('quality', 'high')] + (['--transparent'] if S.get('transparent', True) else []) + ['--ref', cpath], check=True)
        e = np.array(Image.open(ep).convert('RGBA').resize((W, H), Image.LANCZOS))
        # register the edit onto the crop using everything except the changed parts
        m = (~changed).astype(np.uint8); warp = np.eye(2, 3, dtype=np.float32)
        for sc in (.25, .5, 1.):
            a = cv2.GaussianBlur(cv2.resize(g(crop), None, fx=sc, fy=sc), (0, 0), 1.2); b = cv2.GaussianBlur(cv2.resize(g(e), None, fx=sc, fy=sc), (0, 0), 1.2)
            w = warp.copy(); w[:, 2] *= sc
            _, w = cv2.findTransformECC(a, b, w, cv2.MOTION_AFFINE, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), cv2.resize(m, None, fx=sc, fy=sc, interpolation=cv2.INTER_NEAREST), 5)
            warp = w.copy(); warp[:, 2] /= sc
        al = cv2.warpAffine(e, warp, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)
        res = np.abs(g(al) - g(crop))[~changed & (crop[:, :, 3] > 200)].mean()
        # colour-match the edit to the crop (the model drifts a little), on the unchanged region
        for c in range(3):
            k = ~changed & (crop[:, :, 3] > 200) & (al[:, :, 3] > 200)
            sa, sb = al[k, c].astype(float), crop[k, c].astype(float)
            al[:, :, c] = np.clip((al[:, :, c] - sa.mean()) / (sa.std() + 1e-6) * sb.std() + sb.mean(), 0, 255).astype(np.uint8)
        print(f'{vname:14s} registered, residual {res:.1f}')
        for pn in V['patches']:
            M = ell(S['patches'][pn]); d = ndi.distance_transform_edt(M); a = np.clip(d / S.get('feather', 10), 0, 1)
            lay = np.zeros((img.shape[0], img.shape[1], 4), np.uint8); sub = al.copy(); sub[:, :, 3] = (255 * a * (al[:, :, 3] / 255)).astype(np.uint8)
            lay[y0:y0 + n, x0:x0 + n] = sub
            ys, xs = np.where(lay[:, :, 3] > 0); bx0, bx1, by0, by1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
            fn = f'{pn}@{vname}.png'; Image.fromarray(lay[by0:by1, bx0:bx1]).save(os.path.join(out, fn))
            table.setdefault(pn, {})[vname] = {'file': fn, 'x': int(bx0), 'y': int(by0), 'w': int(bx1 - bx0), 'h': int(by1 - by0)}
    json.dump(table, open(os.path.join(out, 'variants.json'), 'w'), indent=1)


if __name__ == '__main__':
    main(sys.argv[1])
