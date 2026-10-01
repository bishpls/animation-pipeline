"""Landmarks (thumb excluded) on the sheet's hands and the turnaround's: numbers and a picture per hand (webs red, the
MCP span's run green, the wrist blue, palm length black)."""
import sys, json, os
sys.path.insert(0, '.')
import numpy as np
from PIL import Image, ImageDraw
from charkit import handsheet, handqa
S = handsheet.cells()
from PIL import Image as I_
sheet = np.asarray(I_.open(handsheet.SHEET).convert('RGB'))
rows, tiles = {}, []


def pic(rgb, h, L, title):
    from charkit.bodymeasure import window
    w = window(h['mask'], pad=20)
    k = 300.0 / L['reach_px']
    im = Image.fromarray(np.asarray(rgb)[w].astype(np.uint8)).convert('RGB')
    im = im.resize((int(im.size[0] * k), int(im.size[1] * k)))
    d = ImageDraw.Draw(im)
    oy, ox = w[0].start, w[1].start
    T = lambda p: ((p[0] - ox) * k, (p[1] - oy) * k)
    for p in L.get('webs', []):
        x, y = T(p); d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(220, 0, 0))
    if 'mcp_run_pts' in L:
        d.line([T(L['mcp_run_pts'][0]), T(L['mcp_run_pts'][1])], fill=(0, 160, 0), width=3)
    if 'wrist_pts' in L:
        d.line([T(L['wrist_pts'][0]), T(L['wrist_pts'][1])], fill=(0, 80, 220), width=3)
    if 'mcp_mid' in L:
        d.line([T(L['wrist_mid']), T(L['mcp_mid'])], fill=(0, 0, 0), width=2)
    c = Image.new('RGB', (max(im.size[0], 260), im.size[1] + 60), 'white')
    c.paste(im, (0, 16))
    D = ImageDraw.Draw(c)
    D.text((3, 2), title, fill=(0, 0, 0))
    R = L.get('ratios') or {}
    D.text((3, im.size[1] + 18), 'MCP span / palm len: est %s run %s' % (R.get('span_est_over_len'), R.get('span_run_over_len')), fill=(0, 0, 0))
    D.text((3, im.size[1] + 32), 'wrist / palm len %s  webs %d' % (R.get('wrist_over_len'), len(L.get('webs', []))), fill=(0, 0, 0))
    return np.asarray(c)


for key in (('open', 'back'), ('relaxed', 'back'), ('point', 'back'), ('fist', 'back')):
    h = S[key]
    L = handsheet.landmarks(h, line=h['line'], open_hand=handsheet.digits(h) if key[0] == 'open' else None)
    rows['sheet_%s_%s' % key] = {k: v for k, v in L.items() if k in ('mcp_s', 'mcp_span_run', 'mcp_span_est', 'wrist_w', 'palm_len', 'ratios', 'why', 'webs')}
    b = h['box']
    tiles.append(pic(sheet[b[1]:b[3], b[0]:b[2]], h, L, 'sheet %s %s' % key))
if len(sys.argv) > 1:
    from charkit import calibrate, qa3d, bodymeasure
    from charkit.bodyqa import CLASS
    B = calibrate.load_bundle(sys.argv[1]); D = qa3d.Design(B)
    ctx = D.sheet_context(); ppl = ctx['ppl']
    masks, graph, _ = bodymeasure.piece_masks(B.spec)
    dv = D.design_views()
    for v, s in (('front', 'L'), ('front', 'R'), ('back', 'L'), ('back', 'R'), ('three_quarter', 'L'), ('profile', 'L')):
        cls, fg = dv[v]['cls'], dv[v]['fg']
        m = masks.get('%s__cuff_%s' % (v, s))
        h = handqa.hand_mask(fg & (cls == CLASS['skin']), m[:cls.shape[0], :cls.shape[1]], ppl)
        h['ppl'] = ppl
        line = dv[v]['raw'] == CLASS['line']
        L = handsheet.landmarks(h, line=line)
        rows['turnaround_%s_%s' % (v, s)] = {k: v_ for k, v_ in L.items() if k in ('mcp_s', 'mcp_span_est', 'wrist_w', 'palm_len', 'ratios', 'why', 'webs')}
        rgb = (np.clip(dv[v]['rgb'], 0, 1) * 255).astype(np.uint8)
        tiles.append(pic(rgb, h, L, 'turnaround %s %s' % (v, s)))
Hh = max(t.shape[0] for t in tiles)
Image.fromarray(np.concatenate([np.pad(t, ((0, Hh - t.shape[0]), (0, 8), (0, 0)), constant_values=255) for t in tiles], 1)).save('charkit/out/hands3/landmarks.png')
json.dump(rows, open('charkit/out/hands3/landmarks.json', 'w'), indent=1, default=lambda o: float(o) if hasattr(o, '__float__') else str(o))
for k, v in rows.items():
    print(k, {a: b for a, b in v.items() if a != 'webs'}, 'webs', len(v.get('webs', [])))
