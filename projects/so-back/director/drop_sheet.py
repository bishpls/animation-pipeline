"""Contact sheet of a lane-3 capture (raw dir, between the slates), squeezed to 9:16 (aspect mode), every N script frames.
    .venv/bin/python projects/so-back/director/drop_sheet.py CAPTURE OUT.jpg [--every 8] [--w 216] [--frames 30,40,...]"""
import argparse, os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from drop_run import between_slates
ap = argparse.ArgumentParser(); ap.add_argument('cap'); ap.add_argument('out'); ap.add_argument('--every', type=int, default=8)
ap.add_argument('--w', type=int, default=216); ap.add_argument('--cols', type=int, default=8); ap.add_argument('--frames', default='')
a = ap.parse_args()
fs, _ = between_slates(a.cap)
idx = [int(x) for x in a.frames.split(',')] if a.frames else list(range(0, len(fs), a.every))
w = a.w; h = w * 16 // 9
S = Image.new('RGB', (a.cols * w, ((len(idx) + a.cols - 1) // a.cols) * (h + 14)), (17, 17, 17)); d = ImageDraw.Draw(S)
for k, i in enumerate(idx):
    x, y = (k % a.cols) * w, (k // a.cols) * (h + 14)
    S.paste(Image.open(fs[i]).convert('RGB').resize((w, h), Image.LANCZOS), (x, y + 14)); d.text((x + 3, y + 1), f's{i}', fill=(255, 225, 77))
S.save(a.out, quality=88); print(a.out, len(fs), 'frames')
