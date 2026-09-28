"""Vertical plates from a director capture: undo the camera roll, correct the pixel aspect, crop 9:16, resize to 1080x1920.
    .venv/bin/python tools/machinima/vplate.py FRAME.png OUT.png --mode roll|crop|aspect [--w 1080]
Dolphin dumps the raw internal-resolution buffer (640x528 x res), which displays at 4:3, so its pixels are not square.
  crop:   4:3 frame -> display 4:3 (square pixels) -> centred 9:16 crop -> 1080x1920
  roll:   the camera rolled +90 degrees (world up lands on the image right; a portrait sensor): rotate back 90 CCW to a 3:4 display portrait -> centred 9:16 crop
  aspect: DirSetup.aspect = 9/16: the frame is the 9:16 view stretched to 4:3 -> squeeze straight to 1080x1920
"""
import argparse
from PIL import Image


def vplate(im, mode, W=1080, rot=90):
    w, h = im.size                               # raw buffer; display aspect 4:3
    H = W * 16 // 9
    if mode == 'aspect':
        return im.resize((W, H), Image.LANCZOS)
    if mode == 'crop':
        dw, dh = w, round(w * 3 / 4)             # display 4:3 at the raw width (square pixels)
        im = im.resize((dw, dh), Image.LANCZOS)
    else:                                        # roll: the long raw axis is world-vertical
        dw, dh = w, round(w * 3 / 4)
        im = im.resize((dw, dh), Image.LANCZOS).rotate(rot, expand=True)
        dw, dh = dh, dw
    cw = round(dh * 9 / 16)
    x0 = (dw - cw) // 2
    return im.crop((x0, 0, x0 + cw, dh)).resize((W, H), Image.LANCZOS)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('inp'); ap.add_argument('out')
    ap.add_argument('--mode', default='roll'); ap.add_argument('--w', type=int, default=1080); ap.add_argument('--rot', type=int, default=90)
    a = ap.parse_args()
    vplate(Image.open(a.inp).convert('RGB'), a.mode, a.w, a.rot).save(a.out)
