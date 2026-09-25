"""Cut Fable's shadow-puppet master (src/seated.png, black paper on white, 2880 px) into pinned parts, traced to vector paths.

    ../../../../.venv/bin/python cut.py [seated|standing]   -> puppet.json / puppet_standing.json (parts, pivots, paths) + _parts_<name>.png

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
G = 2.4                                                     # the seated review grid was 1200 px for the 2880 master
g = lambda pts: [[x * G, y * G] for x, y in pts]
gs = lambda pts: [[(x + 250) * 2, y * 2] for x, y in pts]    # the standing review grid: half scale, cropped 250 px from the left


def capsule(a, b, ra, rb, n=24):
    """A tapered capsule between rivets a and b (master px): how a real puppet's limb piece is cut, round at both pins."""
    import math
    ang = math.atan2(b[1] - a[1], b[0] - a[0]); pts = []
    for k in range(n + 1): t = ang + math.pi / 2 + math.pi * k / n; pts.append([a[0] + ra * math.cos(t), a[1] + ra * math.sin(t)])
    for k in range(n + 1): t = ang - math.pi / 2 + math.pi * k / n; pts.append([b[0] + rb * math.cos(t), b[1] + rb * math.sin(t)])
    return pts



# rivets (joint pivots), master px
RIV_SEATED = {'neck': [1248, 823], 'shoulder': [1186, 1032], 'elbow': [1392, 1507], 'wrist': [1925, 1253], 'hip': [984, 2256]}

# parts front to back: region (claims black pixels), hidden extension, caps (rivet, radius), parent, pivot
PARTS_SEATED = [
 dict(name='hand', parent='forearm', pivot='wrist', region=g([[782, 505], [830, 385], [855, 255], [935, 255], [905, 420], [880, 485], [845, 545], [800, 565]]),
      caps=[['wrist', 44]]),
 dict(name='forearm', parent='upperarm', pivot='elbow', region=g([[545, 598], [770, 530], [805, 548], [800, 640], [792, 700], [765, 830], [705, 910], [620, 870], [520, 800], [480, 700], [505, 640]]),
      caps=[['elbow', 62], ['wrist', 40]]),
 dict(name='upperarm', parent='torso', pivot='shoulder', region=capsule([1186, 1032], [1392, 1507], 175, 130),
      caps=[['shoulder', 70], ['elbow', 62]]),
 dict(name='head', parent='torso', pivot='neck', region=g([[300, 0], [725, 0], [725, 330], [610, 332], [565, 355], [505, 372], [470, 392], [445, 430], [445, 620], [315, 620], [300, 400]]),
      caps=[['neck', 58]], extend=g([[505, 300], [590, 300], [585, 385], [505, 395]])),
 dict(name='torso', parent='lower', pivot='hip', region=g([[300, 380], [560, 358], [640, 470], [660, 600], [700, 780], [760, 880], [640, 900], [560, 938], [470, 938], [330, 890], [300, 700]]),
      extend=g([[345, 380], [560, 360], [640, 470], [665, 610], [705, 790], [760, 880], [560, 935], [330, 885], [330, 420]])),
 dict(name='lower', parent=None, pivot='hip', slits=dict(maxlen=220, add=[[1180, 2400, 150, -6], [1450, 2425, 160, -9], [1720, 2450, 130, -13], [1300, 2570, 150, -3], [1600, 2590, 150, -5], [1880, 2555, 110, -16]]), region=g([[230, 860], [950, 860], [950, 1082], [230, 1082]]),
      extend=g([[330, 850], [770, 850], [860, 900], [860, 1080], [300, 1080]])),
 dict(name='cushion', parent=None, pivot=None, region=g([[200, 1082], [1000, 1082], [1000, 1180], [200, 1180]])),
]


RIV_STANDING = {'neck': [1046, 746], 'shoulder': [1036, 960], 'elbow': [1156, 1422], 'wrist': [1368, 1922], 'hip': [1030, 2116], 'ankle': [986, 3396]}
# standing: the hair hangs BEHIND the jacket and hood, so the head is drawn behind the torso; under the ankle-length skirt only the
# tabi and geta show, so the foot rides the ankle rivet and the skirt carries the hidden leg.
PARTS_STANDING = [
 dict(name='hand', parent='forearm', pivot='wrist', region=gs([[416, 922], [470, 950], [512, 1050], [495, 1112], [440, 1105], [420, 1000]]), caps=[['wrist', 40]]),
 dict(name='forearm', parent='upperarm', pivot='elbow', region=gs([[212, 700], [300, 688], [362, 700], [402, 800], [455, 910], [440, 938], [300, 992], [262, 1008], [246, 960], [222, 880]]),
      caps=[['elbow', 58], ['wrist', 36]]),
 dict(name='upperarm', parent='torso', pivot='shoulder', region=capsule([1036, 960], [1156, 1422], 150, 118),
      caps=[['shoulder', 66], ['elbow', 58]]),
 dict(name='torso', parent='skirt', pivot='hip', region=gs([[120, 390], [445, 378], [445, 560], [425, 800], [465, 925], [425, 1090], [95, 1090], [110, 1040], [150, 900], [192, 722], [186, 560], [128, 535], [116, 470]])),
 dict(name='head', parent='torso', pivot='neck', region=gs([[40, 40], [460, 40], [460, 360], [330, 362], [300, 395], [250, 402], [200, 422], [192, 730], [40, 730]]),
      caps=[['neck', 50]], extend=gs([[110, 360], [320, 360], [320, 720], [95, 720]])),
 dict(name='skirt', parent=None, pivot='hip', slits=dict(maxlen=220), region=gs([[40, 1040], [500, 1040], [500, 1690], [40, 1690]]),
      extend=gs([[140, 950], [425, 950], [425, 1060], [110, 1060]])),
 dict(name='foot', parent='skirt', pivot='ankle', region=gs([[160, 1680], [430, 1680], [430, 1870], [160, 1870]]),
      caps=[['ankle', 30]], extend=gs([[212, 1560], [278, 1560], [278, 1700], [212, 1700]])),
]
MASTERS = {'seated': dict(src='seated.png', riv=RIV_SEATED, parts=PARTS_SEATED, out='puppet.json'),
           'standing': dict(src='standing.png', riv=RIV_STANDING, parts=PARTS_STANDING, out='puppet_standing.json')}


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


def main(which='seated'):
    MS = MASTERS[which]; RIV, PARTS = MS['riv'], MS['parts']
    im = np.array(Image.open(os.path.join(HERE, 'src', MS['src'])).convert('L')).astype(float)
    ink = im < 128; H, W = ink.shape
    figure = ndi.binary_fill_holes(ndi.binary_closing(ink, iterations=6))       # the figure's area, slits included
    claimed = np.zeros_like(ink); yy, xx = np.mgrid[:H, :W]
    out = {'size': [W, H], 'rivets': RIV, 'parts': []}
    review = np.full((H, W, 3), 255, np.uint8); rng = np.random.default_rng(5); masks = []
    for P in PARTS:
        own = poly(ink.shape, P['region']) & figure & ~claimed
        claimed |= own
        body = own & ink                                                          # its black paper (slits stay open)
        if P.get('slits'):                                                        # long slits filled; short ones kept; new ones cut
            sl, ns = ndi.label(own & ~ink)
            for i, sli in enumerate(ndi.find_objects(sl)):
                if sli is None: continue
                if max(sli[0].stop - sli[0].start, sli[1].stop - sli[1].start) > P['slits']['maxlen']: body |= sl == i + 1
            import math
            for x0, y0, ln, ang in P['slits'].get('add', []):
                a = math.radians(ang); dx, dy = math.cos(a) * ln / 2, math.sin(a) * ln / 2
                cut = Image.new('L', (W, H), 0); ImageDraw.Draw(cut).line([(x0 - dx, y0 - dy), (x0 + dx, y0 + dy)], fill=255, width=11)
                body &= ~(np.array(cut) > 127)
        solid = own.copy()
        if P.get('extend'): solid |= poly(ink.shape, P['extend']) & figure        # hidden extension under the parts in front, never outside the figure
        for r, rad in P.get('caps', []):
            cx, cy = RIV[r]; solid |= (xx - cx) ** 2 + (yy - cy) ** 2 <= rad ** 2
        paper = body | (solid & ~own)                                             # own slits stay cut; the extension is solid
        for r in RIV.values():                                                    # rivet holes through every part they touch
            paper &= ~((xx - r[0]) ** 2 + (yy - r[1]) ** 2 <= 12 ** 2)
        paper = ndi.binary_opening(paper, iterations=1)
        lab, nl = ndi.label(paper)                                                # drop small detached islands (they'd float free)
        if nl > 1:
            sz = ndi.sum(paper, lab, index=np.arange(1, nl + 1)); paper = np.isin(lab, np.where(sz >= max(4000, sz.max() * .01))[0] + 1)
        masks.append(paper)
        outer = paper.copy(); holes = ndi.binary_fill_holes(paper) & ~paper
        out['parts'].append({'name': P['name'], 'parent': P['parent'], 'pivot': RIV[P['pivot']] if P['pivot'] else None,
                             'outline': trace(ndi.binary_fill_holes(paper)), 'holes': trace(holes, .5)})
        print(f"{P['name']:9s} {paper.sum():8d} px  outline {len(out['parts'][-1]['outline'])} paths, {len(out['parts'][-1]['holes'])} holes")
    out['parts'].reverse()                                                        # draw order: back to front
    for m in reversed(masks): c = rng.integers(30, 220, 3); review[m] = (255 - (255 - c) * .85).astype(np.uint8) * 0 + c.astype(np.uint8)
    json.dump(out, open(os.path.join(HERE, MS['out']), 'w'))
    Image.fromarray(review).resize((W // 2, H // 2)).save(os.path.join(HERE, f'_parts_{which}.png'))


if __name__ == '__main__':
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else 'seated')
