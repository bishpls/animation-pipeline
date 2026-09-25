"""Part masks for rig art with SAM 2.1 (local, CPU). The layer pixels always come from the base image itself: masks only.

    vendor/seed-vc/.venv/bin/python tools/segment.py BASE.png PARTS.json OUT_DIR [--only name,name]

PARTS.json: {"name": {"pos": [[x, y], ...], "neg": [[x, y], ...], "box": [x0, y0, x1, y1] (optional), "grow": px (optional)}}
Writes OUT_DIR/<name>.png (8-bit mask, restricted to the base's alpha) and OUT_DIR/_overlay.png (every part tinted, for review).
Needs vendor/sam2ckpt/sam2.1_hiera_large.pt (gitignored). The image embedding is cached next to OUT_DIR.
"""
import json, os, sys
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def predictor():
    import torch
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    m = build_sam2('configs/sam2.1/sam2.1_hiera_l.yaml', os.path.join(ROOT, 'vendor', 'sam2ckpt', 'sam2.1_hiera_large.pt'), device='cpu')
    return SAM2ImagePredictor(m)


def main(base, parts_json, out, only=None):
    im = Image.open(base).convert('RGBA'); A = np.array(im)[:, :, 3] > 8
    rgb = np.array(Image.alpha_composite(Image.new('RGBA', im.size, (200, 200, 200, 255)), im).convert('RGB'))
    P = json.load(open(parts_json)); os.makedirs(out, exist_ok=True)
    pr = predictor(); pr.set_image(rgb)
    from scipy.ndimage import binary_dilation
    names = [n for n in P if not n.startswith('_') and (not only or n in only)]
    for n in names:
        p = P[n]; pts = p.get('pos', []) + p.get('neg', []); lab = [1] * len(p.get('pos', [])) + [0] * len(p.get('neg', []))
        kw = dict(multimask_output=False)
        if pts: kw.update(point_coords=np.array(pts, float), point_labels=np.array(lab))
        if 'box' in p: kw['box'] = np.array(p['box'], float)
        m, s, _ = pr.predict(**kw); m = m[0] > 0
        if p.get('grow'): m = binary_dilation(m, iterations=int(p['grow']))
        m &= A
        Image.fromarray((m * 255).astype(np.uint8)).save(os.path.join(out, n + '.png'))
        print(f'{n:18s} {m.sum():9d} px  score {float(s[0]):.2f}')
    # overview: every mask on disk, tinted
    rng = np.random.default_rng(3); ov = rgb.astype(float) * .45
    for f in sorted(os.listdir(out)):
        if f.startswith('_') or not f.endswith('.png'): continue
        m = np.array(Image.open(os.path.join(out, f))) > 127; c = rng.integers(40, 255, 3)
        ov[m] = ov[m] * .4 + c * .6
    Image.fromarray(ov.clip(0, 255).astype(np.uint8)).save(os.path.join(out, '_overlay.png'))


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], a[1], a[2], a[a.index('--only') + 1].split(',') if '--only' in a else None)
