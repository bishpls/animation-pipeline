"""Cut Clawd's cut-paper puppet (her form as a visitor in Fable's world: PUPPETS.md) into pinned parts.

    ../../../../.venv/bin/python cut.py        -> puppet.json + _parts.png (review)

The master (src/front.png, 2160x2880) has exactly three tones: black paper, one clay-orange cellophane plate, open light.
Per part: `outline` (its paper, with the plate's area included), `holes` (open cut-outs: eyes, star hairpin, bow, cream
panel, boot tops, rivets) and `film` (the plate's area: cut out of the paper and filled with gel by the runtime, offset a
pixel or two from the keyline, her misregistration). Regions claim pixels front to back; hidden extensions and rivet caps
keep moving parts overlapped.
"""
import json, math, os
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from skimage import measure

HERE = os.path.dirname(os.path.abspath(__file__))

RIV = {'neck': [1076, 940], 'jaw': [905, 822], 'waist': [1076, 1320],
       'shoulder_L': [850, 1044], 'elbow_L': [716, 1272], 'wrist_L': [552, 1494],
       'shoulder_R': [1304, 1044], 'elbow_R': [1434, 1272], 'wrist_R': [1604, 1494],
       'hip_L': [894, 1962], 'knee_L': [894, 2160], 'hip_R': [1254, 1962], 'knee_R': [1260, 2160]}
SHOW = {'shoulder_L', 'elbow_L', 'wrist_L', 'shoulder_R', 'elbow_R', 'wrist_R', 'hip_L', 'knee_L', 'hip_R', 'knee_R'}   # rivets that show as light


def capsule(a, b, ra, rb, n=20):
    ang = math.atan2(b[1] - a[1], b[0] - a[0]); pts = []
    for k in range(n + 1): t = ang + math.pi / 2 + math.pi * k / n; pts.append([a[0] + ra * math.cos(t), a[1] + ra * math.sin(t)])
    for k in range(n + 1): t = ang - math.pi / 2 + math.pi * k / n; pts.append([b[0] + rb * math.cos(t), b[1] + rb * math.sin(t)])
    return pts


R = RIV
# front to back (claim order); draw order is the reverse
PARTS = [
 dict(name='claw_L', parent='forearm_L', pivot='wrist_L', region=[[400, 1440], [640, 1440], [640, 1730], [400, 1730]], caps=[['wrist_L', 42]]),
 dict(name='claw_R', parent='forearm_R', pivot='wrist_R', region=[[1520, 1440], [1760, 1440], [1760, 1730], [1520, 1730]], caps=[['wrist_R', 42]]),
 dict(name='forearm_L', parent='upperarm_L', pivot='elbow_L', region=capsule(R['elbow_L'], R['wrist_L'], 70, 60), caps=[['elbow_L', 58], ['wrist_L', 44]]),
 dict(name='forearm_R', parent='upperarm_R', pivot='elbow_R', region=capsule(R['elbow_R'], R['wrist_R'], 70, 60), caps=[['elbow_R', 58], ['wrist_R', 44]]),
 dict(name='upperarm_L', parent='torso', pivot='shoulder_L', region=capsule(R['shoulder_L'], R['elbow_L'], 80, 70), caps=[['shoulder_L', 66], ['elbow_L', 58]]),
 dict(name='upperarm_R', parent='torso', pivot='shoulder_R', region=capsule(R['shoulder_R'], R['elbow_R'], 80, 70), caps=[['shoulder_R', 66], ['elbow_R', 58]]),
 # the jaw: the lower face below a straight cut under the eyes, hinged at her right cheek; swung down, a wedge of light opens
 dict(name='jaw', parent='head', pivot='jaw', only_black=True, region=[[895, 812], [1262, 812], [1262, 900], [1180, 950], [1076, 966], [970, 950], [890, 900]]),
 dict(name='head', parent='torso', pivot='neck', region=[[0, 0], [2160, 0], [2160, 940], [1180, 940], [1076, 966], [970, 940], [0, 940]],
      extend=[[900, 790], [1262, 790], [1262, 830], [900, 830]]),       # the face continues a little under the jaw's cut
 dict(name='torso', parent='skirt', pivot='waist', region=[[740, 930], [1410, 930], [1410, 1345], [740, 1345]],
      extend=[[1020, 880], [1132, 880], [1132, 960], [1020, 960]]),      # the neck reaches up under the chin
 dict(name='skirt', parent=None, pivot='waist', region=[[540, 1300], [1620, 1300], [1620, 1945], [540, 1945]],
      extend=[[860, 1280], [1290, 1280], [1290, 1340], [860, 1340]]),    # the waistband tucks up under the bodice
 dict(name='shin_L', parent='thigh_L', pivot='knee_L', region=[[720, 2140], [1010, 2140], [1010, 2820], [720, 2820]], caps=[['knee_L', 70]]),
 dict(name='shin_R', parent='thigh_R', pivot='knee_R', region=[[1140, 2140], [1440, 2140], [1440, 2820], [1140, 2820]], caps=[['knee_R', 70]]),
 dict(name='thigh_L', parent='skirt', pivot='hip_L', region=[[780, 1930], [1010, 1930], [1010, 2160], [780, 2160]],
      extend=capsule(R['hip_L'], R['knee_L'], 80, 76)[:21] + [[970, 1850], [818, 1850]], caps=[['knee_L', 74]]),
 dict(name='thigh_R', parent='skirt', pivot='hip_R', region=[[1140, 1930], [1380, 1930], [1380, 2160], [1140, 2160]],
      extend=capsule(R['hip_R'], R['knee_R'], 80, 76)[:21] + [[1334, 1850], [1176, 1850]], caps=[['knee_R', 74]]),
]


def poly(shape, pts):
    im = Image.new('L', (shape[1], shape[0]), 0); ImageDraw.Draw(im).polygon([tuple(p) for p in pts], fill=255); return np.array(im) > 127


def trace(mask, tol=.7):
    out = []
    for c in measure.find_contours(np.pad(mask, 2).astype(float), .5):
        c = measure.approximate_polygon(c, tol)
        if len(c) >= 4: out.append([[round(float(x) - 2, 1), round(float(y) - 2, 1)] for y, x in c])
    return out


def main():
    rgb = np.array(Image.open(os.path.join(HERE, 'src', 'front.png')).convert('RGB')).astype(float); H, W = rgb.shape[:2]
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]; lum = rgb @ [.299, .587, .114]
    black = lum < 80; orange = (r > 150) & (r - b > 70) & (g < 190) & ~black
    figure = ndi.binary_fill_holes(ndi.binary_closing(black | orange, iterations=4))
    white_in = figure & ~black & ~orange
    yy, xx = np.mgrid[:H, :W]; claimed = np.zeros((H, W), bool)
    out = {'size': [W, H], 'rivets': RIV, 'parts': []}; review = np.full((H, W, 3), 255, np.uint8); rng = np.random.default_rng(3)
    for P in PARTS:
        own = poly((H, W), P['region']) & figure & ~claimed
        if P.get('only_black'): own &= black                         # e.g. the jaw: face paper only (the hair tips stay with the head)
        claimed |= own
        solid = own.copy()
        if P.get('extend'): solid |= poly((H, W), P['extend']) & figure
        for rv, rad in P.get('caps', []):
            cx, cy = RIV[rv]; solid |= (xx - cx) ** 2 + (yy - cy) ** 2 <= rad ** 2
        paper = (own & (black | orange)) | (solid & ~own)            # the extension is plain black paper
        film = own & orange
        holes = own & white_in
        for rv in SHOW:                                              # rivets that show as points of light
            cx, cy = RIV[rv]; d = (xx - cx) ** 2 + (yy - cy) ** 2 <= 16 ** 2
            if (paper & d).any(): holes |= d & (paper | holes)
        paper = ndi.binary_opening(paper, iterations=1); film = ndi.binary_opening(film, iterations=1) & paper
        lab, nl = ndi.label(paper)
        if nl > 1:
            sz = ndi.sum(paper, lab, index=np.arange(1, nl + 1)); paper = np.isin(lab, np.where(sz >= max(1500, sz.max() * .01))[0] + 1)
        outline = ndi.binary_fill_holes(paper | holes)
        holes = holes & outline
        out['parts'].append({'name': P['name'], 'parent': P['parent'], 'pivot': RIV[P['pivot']] if P['pivot'] else None,
                             'outline': trace(outline), 'holes': trace(holes & ~film, .5), 'film': trace(film, .6)})
        c = rng.integers(30, 200, 3); review[paper] = c; review[film] = (c * .4 + np.array([255, 140, 60]) * .6).astype(np.uint8)
        print(f"{P['name']:10s} paper {paper.sum():8d}  film {film.sum():7d}  holes {len(out['parts'][-1]['holes'])}")
    out['parts'].reverse()
    json.dump(out, open(os.path.join(HERE, 'puppet.json'), 'w'))
    Image.fromarray(review).resize((W // 2, H // 2)).save(os.path.join(HERE, '_parts.png'))


if __name__ == '__main__':
    main()
