"""Contact sheet of a capture's vertical frames at chosen FILM frames (plates.py-style trimming is done on the fly).
    .venv/bin/python tools/machinima/vsheet.py CAPTURE OUT.jpg --pre 60 --frames 0,3,20,... [--mode aspect] [--w 240]"""
import argparse, glob, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plates import is_slate
from vplate import vplate
from PIL import Image, ImageDraw

ap = argparse.ArgumentParser(); ap.add_argument('cap'); ap.add_argument('out')
ap.add_argument('--pre', type=int, default=60); ap.add_argument('--frames', required=True)
ap.add_argument('--mode', default='aspect'); ap.add_argument('--w', type=int, default=240); ap.add_argument('--cols', type=int, default=8)
a = ap.parse_args()
fs = sorted(glob.glob(os.path.join(a.cap, 'f*.png')))
first = next(i for i in range(40) if is_slate(fs[i]) and not is_slate(fs[i + 1])) + 1
tiles = []
for fr in [int(v) for v in a.frames.split(',')]:
    im = vplate(Image.open(fs[first + a.pre + fr]).convert('RGB'), a.mode, a.w)
    ImageDraw.Draw(im).text((4, 4), f'{fr} ({fr / 60:.2f}s)', fill=(255, 255, 0))
    tiles.append(im)
W, H = tiles[0].size; cols = min(a.cols, len(tiles)); rows = (len(tiles) + cols - 1) // cols
sheet = Image.new('RGB', (W * cols, H * rows))
for k, t in enumerate(tiles): sheet.paste(t, ((k % cols) * W, (k // cols) * H))
sheet.save(a.out, quality=88); print(a.out, sheet.size, 'first script frame index', first)
