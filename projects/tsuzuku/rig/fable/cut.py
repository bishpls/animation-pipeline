"""Cut Fable's shadow-puppet master (src/seated.png, black paper on white, 2880 px) into pinned parts, traced to vector paths.

    ../../../../.venv/bin/python cut.py        -> puppet.json (parts, pivots, paths) + _parts.png (review)

Each part = the black pixels inside its region (regions claim pixels in priority order), plus a hidden black extension under the
parts in front of it (so a moving part never opens a gap), plus round caps at its rivets (real puppets overlap at the pins).
White detail inside a part (eye slit, hair slits, pleat slits) becomes holes; rivets are round holes through every part they pin.
Coordinates are master pixels; the runtime scales them.
"""
import json, os
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from skimage import measure

HERE = os.path.dirname(os.path.abspath(__file__))
G = 2.4                                                     # the review grid was 1200 px for the 2880 master
g = lambda pts: [[x * G, y * G] for x, y in pts]

# rivets (joint pivots), master px
RIV = {'neck': [1248, 823], 'shoulder': [1186, 1032], 'elbow': [1392, 1507], 'wrist': [1925, 1253], 'hip': [984, 2256]}

# parts front to back: region (claims black pixels), hidden extension, caps (rivet, radius), parent, pivot
PARTS = [
 dict(name='hand', parent='forearm', pivot='wrist', region=g([[782, 505], [830, 385], [855, 255], [935, 255], [905, 420], [880, 485], [845, 545], [800, 565]]),
      caps=[['wrist', 44]]),
 dict(name='forearm', parent='upperarm', pivot='elbow', region=g([[545, 598], [770, 530], [805, 548], [800, 640], [792, 700], [765, 830], [705, 910], [620, 870], [520, 800], [480, 700], [505, 640]]),
      caps=[['elbow', 62], ['wrist', 40]]),
 dict(name='upperarm', parent='torso', pivot='shoulder', region=g([[440, 395], [520, 388], [600, 470], [612, 560], [600, 640], [545, 660], [478, 645], [446, 520]]),
      caps=[['shoulder', 70], ['elbow', 62]]),
 dict(name='head', parent='torso', pivot='neck', region=g([[300, 0], [725, 0], [725, 330], [610, 332], [565, 355], [505, 372], [470, 392], [445, 430], [445, 620], [315, 620], [300, 400]]),
      caps=[['neck', 58]], extend=g([[505, 300], [590, 300], [585, 385], [505, 395]])),
 dict(name='torso', parent='lower', pivot='hip', region=g([[300, 380], [560, 358], [640, 470], [660, 600], [700, 780], [760, 880], [640, 900], [560, 938], [470, 938], [330, 890], [300, 700]]),
      caps=[['hip', 80]], extend=g([[345, 380], [560, 360], [640, 470], [665, 610], [705, 790], [760, 880], [560, 935], [330, 885], [330, 420]])),
 dict(name='lower', parent=None, pivot='hip', region=g([[230, 860], [950, 860], [950, 1082], [230, 1082]]),
      extend=g([[330, 850], [770, 850], [860, 900], [860, 1080], [300, 1080]])),
 dict(name='cushion', parent=None, pivot=None, region=g([[200, 1082], [1000, 1082], [1000, 1180], [200, 1180]])),
]


def poly(shape, pts):
    im = Image.new('L', (shape[1], shape[0]), 0); ImageDraw.Draw(im).polygon([tuple(p) for p in pts], fill=255); return np.array(im) > 127


def trace(mask, tol=.7):
    """Outer contours and holes of a mask, as simplified closed polylines (x, y)."""
    m = np.pad(mask, 2)
    out = []
    for c in measure.find_contours(m.astype(float), .5):
        c = measure.approximate_polygon(c, tol)
        if len(c) < 4: continue
        out.append([[round(float(x) - 2, 1), round(float(y) - 2, 1)] for y, x in c])
    return out


def main():
    im = np.array(Image.open(os.path.join(HERE, 'src', 'seated.png')).convert('L')).astype(float)
    ink = im < 128; H, W = ink.shape
    figure = ndi.binary_fill_holes(ndi.binary_closing(ink, iterations=6))       # the figure's area, slits included
    claimed = np.zeros_like(ink); yy, xx = np.mgrid[:H, :W]
    out = {'size': [W, H], 'rivets': RIV, 'parts': []}
    review = np.full((H, W, 3), 255, np.uint8); rng = np.random.default_rng(5); masks = []
    for P in PARTS:
        own = poly(ink.shape, P['region']) & figure & ~claimed
        claimed |= own
        body = own & ink                                                          # its black paper (slits stay open)
        solid = own.copy()
        if P.get('extend'): solid |= poly(ink.shape, P['extend'])                 # hidden extension under the parts in front
        for r, rad in P.get('caps', []):
            cx, cy = RIV[r]; solid |= (xx - cx) ** 2 + (yy - cy) ** 2 <= rad ** 2
        paper = body | (solid & ~own)                                             # own slits stay cut; the extension is solid
        for r in RIV.values():                                                    # rivet holes through every part they touch
            paper &= ~((xx - r[0]) ** 2 + (yy - r[1]) ** 2 <= 12 ** 2)
        paper = ndi.binary_opening(paper, iterations=1)
        masks.append(paper)
        outer = paper.copy(); holes = ndi.binary_fill_holes(paper) & ~paper
        out['parts'].append({'name': P['name'], 'parent': P['parent'], 'pivot': RIV[P['pivot']] if P['pivot'] else None,
                             'outline': trace(ndi.binary_fill_holes(paper)), 'holes': trace(holes, .5)})
        print(f"{P['name']:9s} {paper.sum():8d} px  outline {len(out['parts'][-1]['outline'])} paths, {len(out['parts'][-1]['holes'])} holes")
    out['parts'].reverse()                                                        # draw order: back to front
    for m in reversed(masks): c = rng.integers(30, 220, 3); review[m] = (255 - (255 - c) * .85).astype(np.uint8) * 0 + c.astype(np.uint8)
    json.dump(out, open(os.path.join(HERE, 'puppet.json'), 'w'))
    Image.fromarray(review).resize((1200, 1200)).save(os.path.join(HERE, '_parts.png'))


if __name__ == '__main__':
    main()
