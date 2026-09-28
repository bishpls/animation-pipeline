"""Keyed contact sheet of a delivered plate: out = black pass + (1 - a) * field, over a hot colour field (checker of two hot
colours so haze and holes show). .venv/bin/python projects/so-back/director/drop_keysheet.py NAME OUT.jpg --frames 1,10,... [--w 216]"""
import argparse, os
import numpy as np
from PIL import Image, ImageDraw
ap = argparse.ArgumentParser(); ap.add_argument('name'); ap.add_argument('out'); ap.add_argument('--frames', required=True)
ap.add_argument('--w', type=int, default=216); ap.add_argument('--cols', type=int, default=8)
a = ap.parse_args()
d = os.path.expanduser(f'~/games/melee/plates/soback_{a.name}/v')
idx = [int(x) for x in a.frames.split(',')]
W, H = 1080, 1920
yy, xx = np.mgrid[0:H, 0:W]
chk = (((xx // 120) + (yy // 120)) % 2)[..., None]
field = np.where(chk, np.array([255, 46, 154]), np.array([46, 230, 255])).astype(np.float32)
w = a.w; h = w * 16 // 9
S = Image.new('RGB', (a.cols * w, ((len(idx) + a.cols - 1) // a.cols) * (h + 14)), (17, 17, 17)); dr = ImageDraw.Draw(S)
for k, i in enumerate(idx):
    rgb = np.asarray(Image.open(f'{d}/f{i:05d}.jpg').convert('RGB')).astype(np.float32)
    al = np.asarray(Image.open(f'{d}/m{i:05d}.png'))[..., 1].astype(np.float32)[..., None] / 255
    o = np.clip(rgb + (1 - al) * field, 0, 255).astype(np.uint8)
    x, y = (k % a.cols) * w, (k // a.cols) * (h + 14)
    S.paste(Image.fromarray(o).resize((w, h), Image.LANCZOS), (x, y + 14)); dr.text((x + 3, y + 1), f'f{i}', fill=(255, 225, 77))
S.save(a.out, quality=90); print(a.out)
