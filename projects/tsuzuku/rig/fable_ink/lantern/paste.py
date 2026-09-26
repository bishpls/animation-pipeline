"""Fable's lantern (the canon's oblong chōchin) into the ink cut-ins: an image-model edit of the lantern's region, registered
onto the drawing on everything but the lantern, pasted through a feathered mask covering old and new lantern shapes.

    ../../../../../.venv/bin/python paste.py stand     -> stand1..6.png (originals kept as src/stand_k_round.png)
    ../../../../../.venv/bin/python paste.py lamp      -> lamp.png (original kept as src/lamp_round.png)
"""
import os, shutil, sys
import numpy as np, cv2
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); INK = os.path.dirname(HERE)

def register(base_crop, edit, keep):                 # ECC affine on the region outside the lantern
    g = lambda a: cv2.GaussianBlur(cv2.cvtColor(a, cv2.COLOR_RGB2GRAY).astype(np.float32), (0, 0), 1.2)
    b, e, warp = g(base_crop), g(edit), np.eye(2, 3, dtype=np.float32)
    for sc in (.25, .5, 1.):
        w = warp.copy(); w[:, 2] *= sc
        _, w = cv2.findTransformECC(cv2.resize(b, None, fx=sc, fy=sc), cv2.resize(e, None, fx=sc, fy=sc), w, cv2.MOTION_AFFINE,
                                    (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), cv2.resize(keep, None, fx=sc, fy=sc, interpolation=cv2.INTER_NEAREST), 5)
        warp = w.copy(); warp[:, 2] /= sc
    al = cv2.warpAffine(edit, warp, (base_crop.shape[1], base_crop.shape[0]), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
    res = np.abs(g(al) - b)[keep > 0].mean(); return al, res

def run(names, crop, edit_png, box, feather=28):
    x0, y0, x1, y1 = crop; ed = np.array(Image.open(os.path.join(HERE, edit_png)).convert('RGB').resize((x1 - x0, y1 - y0), Image.LANCZOS))
    m = np.zeros((y1 - y0, x1 - x0), np.uint8); bx0, by0, bx1, by1 = [v - o for v, o in zip(box, (x0, y0, x0, y0))]
    cv2.ellipse(m, ((bx0 + bx1) // 2, (by0 + by1) // 2), ((bx1 - bx0) // 2, (by1 - by0) // 2), 0, 0, 360, 255, -1)
    alpha = cv2.GaussianBlur(m.astype(np.float32) / 255, (0, 0), feather)[:, :, None]; alpha = np.clip(alpha * 1.6, 0, 1)
    keep = (cv2.dilate(m, np.ones((61, 61), np.uint8)) == 0).astype(np.uint8)
    for n in names:
        p = os.path.join(INK, n + '.png'); bak = os.path.join(INK, 'src', n.replace('.png', '') + '_round.png')
        if not os.path.exists(bak): shutil.copy(p, bak)
        base = Image.open(bak); mode = base.mode; a = np.array(base.convert('RGB'))
        crop_b = a[y0:y1, x0:x1].copy(); al, res = register(crop_b, ed, keep)
        a[y0:y1, x0:x1] = (al * alpha + crop_b * (1 - alpha)).astype(np.uint8)
        out = Image.fromarray(a)
        if mode == 'RGBA': out.putalpha(base.getchannel('A'))
        out.save(p); print(n, f'registered residual {res:.1f}')

if __name__ == '__main__':
    if sys.argv[1] == 'stand':
        run([f'stand{k}' for k in range(1, 7)], (256, 1296, 1024, 2064), 'stand_edit.png', (330, 1330, 820, 2000))
    else:
        run(['lamp'], (1536, 720, 2688, 1936), 'lamp_edit.png', tuple(int(v) for v in sys.argv[2].split(',')))
