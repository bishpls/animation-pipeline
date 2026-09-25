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
RIV_SEATED = {'nape': [960, 720], 'neck': [1248, 823], 'shoulder': [1186, 1032], 'elbow': [1392, 1507], 'wrist': [1925, 1253], 'hip': [984, 2256]}

# parts front to back: region (claims black pixels), hidden extension, caps (rivet, radius), parent, pivot
PARTS_SEATED = [
 dict(name='hand', parent='forearm', pivot='wrist',              # the fist only: the fan is a code prop (fan/fan.json) held behind the fingers
      region=[[1877, 1212], [1965, 1012], [2060, 1012], [2075, 985], [2110, 990], [2125, 1060], [2112, 1164], [2028, 1308], [1920, 1356]],
      caps=[['wrist', 44]]),
 dict(name='forearm', parent='upperarm', pivot='elbow',
      # the top edge follows the master's visible sleeve edge exactly, then rounds over the elbow on an arc about its rivet
      region=[[1848, 1272], [1522, 1398], [1434, 1418], [1392, 1407], [1350, 1414], [1318, 1440], [1296, 1480], [1212, 1536],
              [1152, 1680], [1248, 1920], [1488, 2088], [1692, 2184], [1836, 1992], [1901, 1680], [1920, 1536], [1932, 1315]],
      caps=[['elbow', 62], ['wrist', 40]]),
 dict(name='upperarm', parent='torso', pivot='shoulder', region=capsule([1186, 1032], [1392, 1507], 175, 110),
      caps=[['shoulder', 70], ['elbow', 62]]),
 # the long back hair hangs from the nape as its own piece (it stays hanging when the head tilts). Its top edge is an arc about the
 # nape pin and the head keeps the matching disc, so the seam never opens however the hair swings. (Claims before the head.)
 dict(name='hair', parent='head', pivot='nape', region=g([[280, 300], [520, 300], [505, 372], [470, 392], [445, 430], [445, 630], [280, 630]]),
      minus=[['nape', 300]]),                                            # the arc spans the hair's full width: one seam, about the pin
 dict(name='head', parent='torso', pivot='neck', region=g([[300, 0], [725, 0], [725, 330], [610, 332], [565, 355], [505, 372], [470, 392], [445, 430], [445, 620], [315, 620], [300, 400]]),
      caps=[['neck', 58]], extend=g([[505, 300], [590, 300], [585, 385], [505, 395]])),
 dict(name='torso', parent='lower', pivot='hip', region=g([[300, 380], [560, 358], [640, 470], [660, 600], [700, 780], [760, 880], [640, 900], [560, 938], [470, 938], [330, 890], [300, 700]]),
      # hidden front: her body line continues behind the sleeve (chest -> belly -> lap), so a swung sleeve reveals a body, not a cut
      extend=[[828, 912], [1344, 864], [1480, 900], [1500, 1000], [1532, 1210], [1528, 1330], [1523, 1398], [1515, 1450], [1510, 1520],
              [1511, 1600], [1518, 1690], [1532, 1790], [1556, 1890], [1590, 1980], [1640, 2060], [1700, 2100], [1344, 2244], [792, 2124], [792, 1008]]),
 dict(name='lower', parent=None, pivot='hip', slits=dict(maxlen=220, add=[[1180, 2400, 150, -6], [1450, 2425, 160, -9], [1720, 2450, 130, -13], [1300, 2570, 150, -3], [1600, 2590, 150, -5], [1880, 2555, 110, -16]]), region=g([[230, 860], [950, 860], [950, 1082], [230, 1082]]),
      # hidden top: the thighs rise from the belly and run forward to the knee (what the sleeve hem covers in the master)
      extend=[[792, 2040], [1400, 2000], [1520, 1905], [1552, 1918], [1590, 1938], [1650, 1952], [1760, 1968], [1880, 1986], [1990, 2030], [2064, 2160], [2064, 2592], [720, 2592]]),
 dict(name='cushion', parent=None, pivot=None, region=g([[200, 1082], [1000, 1082], [1000, 1180], [200, 1180]])),
]


RIV_STANDING = {'nape': [800, 600], 'neck': [1046, 746], 'shoulder': [1036, 960], 'elbow': [1156, 1422], 'wrist': [1368, 1922], 'hip': [1030, 2116], 'ankle': [986, 3396]}
# standing: the hair hangs BEHIND the jacket and hood, so the head is drawn behind the torso; under the ankle-length skirt only the
# tabi and geta show, so the foot rides the ankle rivet and the skirt carries the hidden leg.
PARTS_STANDING = [
 dict(name='hand', parent='forearm', pivot='wrist', region=gs([[416, 922], [470, 950], [512, 1050], [495, 1112], [440, 1105], [420, 1000]]), caps=[['wrist', 40]]),
 dict(name='forearm', parent='upperarm', pivot='elbow', region=[[1046, 1422], [1061, 1367], [1101, 1327], [1156, 1312], [1211, 1327], [1251, 1367], [1266, 1422]] + [[1304, 1600], [1410, 1820], [1380, 1876], [1100, 1984], [1024, 2016], [992, 1920], [944, 1760]],   # top: an arc about the elbow rivet
      caps=[['elbow', 58], ['wrist', 36]]),
 dict(name='upperarm', parent='torso', pivot='shoulder', region=capsule([1036, 960], [1156, 1422], 150, 118),
      caps=[['shoulder', 66], ['elbow', 58]]),
 dict(name='torso', parent='skirt', pivot='hip',
      # front: the master's chest, then a designed body line (under-bust, waist, the haori falling to its hem) that the arm covers
      # at rest; back: a curved back under the hair. The extension fills the body solid under the arm.
      region=gs([[120, 390], [445, 378], [445, 520], [402, 540], [396, 610], [390, 680], [396, 760], [410, 860], [465, 925], [425, 1090],
                 [95, 1090], [110, 1040], [150, 900], [192, 722], [168, 672], [148, 622], [134, 568], [124, 522], [116, 470]]),
      extend=gs([[120, 390], [400, 380], [402, 540], [396, 610], [390, 680], [396, 760], [410, 860], [428, 960], [425, 1090],
                 [95, 1090], [110, 1040], [150, 900], [192, 722], [168, 672], [148, 622], [134, 568], [124, 522], [116, 470]])),
 dict(name='hair', parent='head', pivot='nape', region=gs([[30, 300], [270, 300], [260, 402], [200, 422], [192, 740], [30, 740]]),
      minus=[['nape', 250]]),                                            # arc-top joint about the nape pin, spanning the hair (see the seated note)
 dict(name='head', parent='torso', pivot='neck', region=gs([[40, 40], [460, 40], [460, 360], [330, 362], [300, 395], [250, 402], [200, 422], [192, 730], [40, 730]]),
      caps=[['neck', 50]], extend=gs([[110, 360], [320, 360], [320, 720], [95, 720]])),
 dict(name='leg', parent='skirt', pivot='hip', virtual=True),                 # hidden under the skirt: carries the foot
 dict(name='skirt', parent=None, pivot='hip', slits=dict(maxlen=220), region=gs([[40, 1040], [500, 1040], [500, 1690], [40, 1690]]),
      extend=gs([[110, 950], [440, 950], [440, 1115], [80, 1115]])),     # the waist under the jacket, overlapping the skirt proper
 dict(name='foot', parent='leg', pivot='ankle', region=gs([[160, 1680], [430, 1680], [430, 1870], [160, 1870]]),
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
        if P.get('virtual'):
            out['parts'].append({'name': P['name'], 'parent': P['parent'], 'pivot': RIV[P['pivot']], 'outline': [], 'holes': []}); continue
        reg = poly(ink.shape, P['region'])
        for r, rad in P.get('minus', []):
            cx, cy = RIV[r]; reg &= ~((xx - cx) ** 2 + (yy - cy) ** 2 <= rad ** 2)
        own = reg & figure & ~claimed
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
