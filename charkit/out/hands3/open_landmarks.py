"""The review page's open-hand figure: the hand sheet's open hand and ours drawn the sheet's way (the pose library's
open pose on the spec's hand, handposes.PoseGrade), each with its landmarks (webs red, the MCP span's run green, the
wrist line blue, the palm length black) and the structural ratios read off them beside the style prior's range.
    python charkit/out/hands3/open_landmarks.py [SPEC] -> charkit/out/hands3/open_landmarks.png, .json"""
import json, sys
sys.path.insert(0, '.')
import numpy as np
from PIL import Image, ImageDraw
from charkit import handsheet, handposes, code_hand
from charkit.bodymeasure import window

spec = json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'charkit/spec/clawd.json'))
S = handsheet.cells()
sheet = np.asarray(Image.open(handsheet.SHEET).convert('RGB'))
G = handposes.PoseGrade(spec=spec)
ho = G.ours(handposes.POSES['open'], 'back')[0]
hs = S[('open', 'back')]
prior = code_hand.ratio_prior(spec.get('style') or 'anime')
KEYS = ('span', 'middle', 'index', 'ring', 'little', 'taper', 'thumb', 'thumb_w')


def pic(rgb, h, L, title, lines):
    w = window(h['mask'], pad=20)
    k = 340.0 / L['reach_px']
    im = Image.fromarray(np.asarray(rgb)[w].astype(np.uint8)).convert('RGB')
    im = im.resize((int(im.size[0] * k), int(im.size[1] * k)))
    d = ImageDraw.Draw(im)
    oy, ox = w[0].start, w[1].start
    T = lambda p: ((p[0] - ox) * k, (p[1] - oy) * k)
    for i, p in enumerate(L.get('webs', [])):
        x, y = T(p)
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(220, 0, 0))
        d.text((x + 6, y - 6), 'w%d' % (i + 1), fill=(220, 0, 0))
    if 'mcp_run_pts' in L:
        d.line([T(L['mcp_run_pts'][0]), T(L['mcp_run_pts'][1])], fill=(0, 160, 0), width=3)
    if 'wrist_pts' in L:
        d.line([T(L['wrist_pts'][0]), T(L['wrist_pts'][1])], fill=(0, 80, 220), width=3)
    if 'mcp_mid' in L:
        d.line([T(L['wrist_mid']), T(L['mcp_mid'])], fill=(0, 0, 0), width=2)
    c = Image.new('RGB', (max(im.size[0], 330), im.size[1] + 22 + 14 * len(lines)), 'white')
    c.paste(im, (0, 18))
    D = ImageDraw.Draw(c)
    D.text((3, 2), title, fill=(0, 0, 0))
    for i, t in enumerate(lines):
        D.text((3, im.size[1] + 20 + 14 * i), t, fill=(0, 0, 0))
    return np.asarray(c)


Ls = handsheet.landmarks(hs, line=hs.get('line'), open_hand=handsheet.digits(hs))
Lo = handsheet.landmarks(ho, line=None, open_hand=handsheet.digits(ho))
rs, ro = handsheet.ratios_of(hs), handsheet.ratios_of(ho)
fmt = lambda v: '-' if v is None else '%.3f' % v
rows = ['ratio     sheet   ours    prior [lo, hi]']
for k in KEYS:
    p = prior.get(k)
    rows.append('%-8s  %s   %s   %s' % (k, fmt(rs.get(k)), fmt((ro or {}).get(k)),
                                        '[%s, %s]' % (p[1], p[2]) if p else ''))
b = hs['box']
legend = ['red: the finger webs (the thumb left out)', 'green: the MCP span (index edge to little edge)',
          "blue: the wrist line (the cuff's edge)", 'black: the palm length (wrist line to the middle MCP)',
          'ratios over the palm length (fingers: index, ring,', "little over the middle's)"]
t1 = pic(sheet[b[1]:b[3], b[0]:b[2]], hs, Ls, "the hand sheet's open hand (back)", legend)
g = np.where(ho['mask'][..., None], np.array([200, 200, 200], np.uint8), np.array([255, 255, 255], np.uint8))
t2 = pic(g, ho, Lo, "ours: the pose library's open pose, drawn alike", rows)
H = max(t1.shape[0], t2.shape[0])
Image.fromarray(np.concatenate([np.pad(t, ((0, H - t.shape[0]), (0, 12), (0, 0)), constant_values=255)
                                for t in (t1, t2)], 1)).save('charkit/out/hands3/open_landmarks.png')
json.dump(dict(sheet=rs, ours=ro, prior={k: prior.get(k) for k in KEYS}), open('charkit/out/hands3/open_landmarks.json', 'w'),
          indent=1, default=float)
print('\n'.join(rows))
