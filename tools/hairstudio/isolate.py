"""per-group isolation (observability): the front and three-quarter views with only one hair object (plus the skin) drawn,
each group alone, at the studio's scale -> studio/TAG_iso.png"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import studio as S
from PIL import Image, ImageDraw
from charkit import bundle as bl, palette, qa3d
from charkit.detailqa import _Window


def draw_only(B, az, keep, ss=2):
    L = float(B.assembly['L']); c = np.array(B.assembly['centre'], float); c[2] = float(B.assembly['eye_z'])
    up, down, half = S.pv.WIN['up'], S.pv.WIN['down'], S.pv.WIN['half']
    c[2] += (up - down) / 2 * L
    fr = _Window(c, az, half * L, (up + down) / 2 * L, L / S.P / ss)
    surfs = []
    for o in B.objects():
        if o.group == 'hair' and o.name not in keep:
            continue
        if o.group not in ('hair', 'skin'):
            continue
        variant = 'masked' if o.group == 'skin' and o.has('masked') else 'eval'
        if o.has(variant):
            surfs += qa3d.surfaces(B, o, variant)
    img = qa3d.draw(B, surfs, az, fr, transparent=True, ss=ss)
    a = img[..., 3:4]
    rgb = img[..., :3] * a + 0.95 * (1 - a)
    return S.pv.head_crop(rgb, S.EYE_ROW, S.P)


bdir, tag = sys.argv[1], sys.argv[2]
B = bl.load(bdir); palette.activate_spec(B.spec)
groups = [('gathered', ['hair_upper_back']), ('loose', ['hair_lower_back']), ('tendrils', ['hair_side_lock_L', 'hair_side_lock_R']),
          ('bangs', ['hair_bangs']), ('wisps+fly', ['hair_flyaways']), ('all', [o.name for o in B.objects() if o.group == 'hair'])]
rows = []
for az in (0.0, 35.0):
    tiles = []
    for name, keep in groups:
        t = (np.clip(draw_only(B, az, set(keep)), 0, 1) * 255).astype(np.uint8)
        im = Image.fromarray(t); ImageDraw.Draw(im).text((8, 8), name, fill=(20, 20, 20)); tiles.append(np.asarray(im))
    rows.append(np.concatenate(tiles, 1))
Image.fromarray(np.concatenate(rows, 0)).save(os.path.join(S.OUT, tag + '_iso.png'))
print('ok')
