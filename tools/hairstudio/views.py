"""A groom's views: the four head views (studio.ours, with the studio's passes) and two tall views (back, profile) that
show the braid -> studio/TAG.png, plus TAG_ours.npz for the silhouette / speckle / edge-on measures."""
import os, sys
os.environ.setdefault('STUDIO_AO', '1'); os.environ.setdefault('STUDIO_GRADIENT', '1'); os.environ.setdefault('STUDIO_GRADIENT_MODE', 'mix')
os.environ.setdefault('STUDIO_CONTOURS', '1'); os.environ.setdefault('STUDIO_CONTOUR_JUMP', '0.03')
os.environ.setdefault('STUDIO_GRADIENT_ARGS', '{"along":0.12,"across":0.15,"depth":0.45,"streak":0.35,"band":[0.1,0.3],"streak_u":0.45,"crown_across":0.3,"bangs_across":0.0,"bangs_streak":0}')
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
sys.path.insert(0, os.path.expanduser('~/animation-pipeline-3d'))
import numpy as np
import studio as S
from PIL import Image, ImageDraw
from charkit import bundle as bl, palette, qa3d
from charkit.detailqa import _Window

bdir, tag = sys.argv[1], sys.argv[2]
O = S.ours(bdir)
np.savez_compressed(os.path.join(S.OUT, tag + '_ours.npz'), **{'%s_%s' % (v, k): x for v in O for k, x in O[v].items()})
row = np.concatenate([O[v]['rgb'] for v, _ in S.VIEWS], 1)
B = bl.load(bdir); palette.activate_spec(B.spec)
L = float(B.assembly['L'])
surfs = []
for o in B.objects():
    variant = 'masked' if o.group == 'skin' and o.has('masked') else 'eval'
    if o.has(variant):
        surfs += qa3d.surfaces(B, o, variant)
# the top-down view: the geometry turned 90 deg about x (the crown toward the camera), drawn from the front
from charkit.detailqa import _Window as _W
ez_ = float(B.assembly['eye_z'])
cen_ = np.array([0.0, 0.02, ez_ + 0.03])
Rx = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)          # (z up -> toward -y, the camera's side at az 0)
surfs_t = []
for s_ in surfs:
    if s_['o'].group in ('hair', 'skin', 'accessory'):
        s2 = dict(s_); s2['V'] = (s_['V'] - cen_) @ Rx.T + cen_
        surfs_t.append(s2)
frT = _W(np.array([0.0, 0.02, ez_ + 0.03]), 0.0, 0.85 * L, 0.85 * L, L / 300 / 2)
topv = qa3d.draw(B, surfs_t, 0.0, frT, transparent=False, ss=2)
Image.fromarray((np.clip(topv[..., :3], 0, 1) * 255).astype(np.uint8)).save(os.path.join(S.OUT, tag + '_top.png'))
tall = []
for az in (180.0, 90.0, 135.0):
    c = np.array(B.assembly['centre'], float); c[2] = float(B.assembly['eye_z']) - 1.0 * L
    fr = _Window(c, az, 1.1 * L, 2.4 * L, L / 140 / 2)
    img = qa3d.draw(B, surfs, az, fr, transparent=False, ss=2)
    tall.append(np.clip(img[..., :3], 0, 1))
tall = np.concatenate(tall, 1)
H = row.shape[0]
ti = Image.fromarray((tall * 255).astype(np.uint8)); ti = ti.resize((int(ti.size[0] * H / ti.size[1]), H))
ri = Image.fromarray((np.clip(row, 0, 1) * 255).astype(np.uint8))
out = Image.new('RGB', (ri.size[0] + ti.size[0] + 10, H), (240, 240, 244)); out.paste(ri, (0, 0)); out.paste(ti, (ri.size[0] + 10, 0))
ImageDraw.Draw(out).text((8, 8), tag, fill=(30, 30, 30))
out.save(os.path.join(S.OUT, tag + '.png'))
print('saved', out.size)
