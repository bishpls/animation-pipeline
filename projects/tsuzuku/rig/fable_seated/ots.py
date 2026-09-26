"""The over-the-shoulder cuts (bars 67 and 70): Fable turns the page in her lap and the screen's card slides in on the same
drawing. Keys the three drawings (src/ots: the set-up, and two turn drawings as edits of it), registers the turns onto the set-up,
and cuts for each a mask of the flat page paper that shows (not under her hand, not under the lifting page), so code prints
the card's spread onto it. Writes ots_<d>.png and ots_<d>_page.png at 1920x1080, and ots.json with the page quads (screen px).
    .venv/bin/python rig/fable_seated/ots.py
"""
import json, os
import numpy as np, cv2
from PIL import Image
from scipy import ndimage as ndi
from key import key
from build import lum, feather

D = os.path.dirname(os.path.abspath(__file__)); S = 1920 / 2560
Q = {'left': [[1350, 650], [1700, 785], [1500, 1190], [1235, 1070]],        # outer top, spine top, spine bottom, outer bottom
     'right': [[1705, 785], [2095, 850], [1955, 1335], [1505, 1190]]}       # spine top, outer top, outer bottom, spine bottom
HAND = [[1080, 730], [1290, 730], [1290, 980], [1080, 980]]                 # her hand at the left page's corner, in the set-up
LIFT = {'turn1': [[1310, 750], [1395, 660], [1440, 492], [1500, 560], [1580, 640], [1650, 710], [1700, 790], [1650, 900], [1580, 1030], [1510, 1150],
                  [1500, 1185], [1470, 1080], [1440, 990], [1380, 880], [1310, 790]],        # the lifting page (its back is blank), traced
        'turn2': [[1625, 465], [1690, 530], [1735, 610], [1745, 690], [1725, 780], [1650, 920], [1570, 1070], [1505, 1185], [1480, 1100], [1440, 1010],
                  [1405, 955], [1480, 830], [1515, 715], [1560, 640]]}
base = key(os.path.join(D, 'src/ots/ots.png')); H, W = base.shape[:2]   # (the set-up as drawn: registration target)


def poly(p):
    m = np.zeros((H, W), np.uint8); cv2.fillPoly(m, [np.array(p, np.int32)], 1); return m.astype(bool)


def register(img, mask):
    warp = np.eye(2, 3, dtype=np.float32)
    for sc in (.125, .25, .5):
        a = cv2.GaussianBlur(cv2.resize(lum(base), None, fx=sc, fy=sc), (0, 0), 1.2); b = cv2.GaussianBlur(cv2.resize(lum(img), None, fx=sc, fy=sc), (0, 0), 1.2)
        w = warp.copy(); w[:, 2] *= sc
        _, w = cv2.findTransformECC(a, b, w, cv2.MOTION_AFFINE, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 300, 1e-6),
                                    cv2.resize(mask.astype(np.uint8), None, fx=sc, fy=sc, interpolation=cv2.INTER_NEAREST), 5)
        warp = w.copy(); warp[:, 2] /= sc
    return cv2.warpAffine(img, warp, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderValue=(0, 0, 0, 0)), warp


pages = poly(Q['left']) | poly(Q['right'])
paper = lambda a: (lum(a) > 150) & (a[..., 3] > 200)
out = {'quads': {k: [[round(x * S, 1), round(y * S, 1)] for x, y in v] for k, v in Q.items()}}
fit = (base[..., 3] > 200) & ~ndi.binary_dilation(pages | poly(HAND), iterations=60)
# the lantern moved to the floor at her left (out of this frame, behind her): its corner, bottom right, from 'ots_nolantern'
LZ = [[2100, 700], [2560, 700], [2560, 1440], [1900, 1440], [1990, 1100]]
from build import over
nl, _ = register(key(os.path.join(D, 'src/ots/ots_nolantern.png')), fit & ~poly(LZ))
lzm = poly(LZ) & ~ndi.binary_dilation(pages, iterations=8)
lzm = feather(lzm, 14)
for d in ['ots', 'turn1', 'turn2']:
    if d == 'ots': al, res = over(base, nl, lzm), 0
    else:
        al, warp = register(key(os.path.join(D, f'src/ots/{d}.png')), fit); res = np.abs(lum(al) - lum(base))[fit].mean(); al = over(al, nl, lzm)
    if d == 'ots': cover = poly(HAND)
    else:
        diff = np.abs(al[..., :3].astype(np.int16) - base[..., :3].astype(np.int16)).max(-1) > 40
        cover = ndi.binary_fill_holes(ndi.binary_closing(ndi.binary_opening(diff, iterations=2), iterations=6))
        lab, n = ndi.label(cover); sizes = ndi.sum(cover, lab, range(1, n + 1)); cover = np.isin(lab, 1 + np.flatnonzero(sizes > 3000))
        cover = ndi.binary_dilation(cover | poly(LIFT[d]), iterations=6)
    m = ndi.binary_erosion(pages & paper(al), iterations=2) & ~cover
    mk = (feather(m, 3) * 255).astype(np.uint8)
    Image.fromarray(al).resize((1920, 1080), Image.LANCZOS).save(os.path.join(D, f'ots_{d}.png'))
    mk = np.asarray(Image.fromarray(mk).resize((1920, 1080), Image.LANCZOS))                 # (as alpha: the runtime masks with it)
    Image.fromarray(np.dstack([np.full_like(mk, 255)] * 3 + [mk])).save(os.path.join(D, f'ots_{d}_page.png'))
    print(f'{d:6s} residual {res:.1f}  page {m.sum() / 1e3:.0f}k px')
json.dump(out, open(os.path.join(D, 'ots.json'), 'w'), indent=1)
