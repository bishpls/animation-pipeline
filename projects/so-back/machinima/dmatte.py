"""Difference matte from two deterministic director captures of one script: one on a black clear colour, one on a mid grey.
    .venv/bin/python projects/so-back/machinima/dmatte.py BLACK.png GREY.png OUT_PREFIX [--bg 96] [--rot 90]
Writes OUT_PREFIX.rgb.png (the black pass: premultiplied colour, additive glows included) and OUT_PREFIX.a.png (coverage).
Per pixel, a capture on clear colour B is P = a*C + E + (1-a)*B (E: additive glows, which a chroma key can't separate from
spill). With B = black and B = (g,g,g), the transmission (1-a) = (Pg - Pb) / g in every channel that didn't clip at 255;
the unclipped channels are averaged. A green second pass clipped under every bright glow (a grey haze in the composite);
grey 96 clips only in the hottest cores. The director is deterministic: the two passes differ only in the clear colour.
Composite over any background: out = Pb + (1-a) * BG  (canvas: the matte 'destination-out', then the black pass 'lighter').
"""
import argparse
import numpy as np
from PIL import Image


def matte(pb, pg, g=96.0):
    pb = pb.astype(np.float32); pg = pg.astype(np.float32)
    ok = pg < 254.5                                                   # channels that didn't clip on the grey pass
    t = np.clip((pg - pb) / g, 0, 1)
    n = ok.sum(-1)
    tm = np.where(n > 0, (t * ok).sum(-1) / np.maximum(n, 1), t.min(-1))   # all clipped: the lower bound
    return pb, 1 - tm


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('black'); ap.add_argument('grey'); ap.add_argument('out')
    ap.add_argument('--bg', type=float, default=96); ap.add_argument('--rot', type=int, default=0)
    a = ap.parse_args()
    ims = [Image.open(p).convert('RGB') for p in (a.black, a.grey)]
    if a.rot: ims = [im.rotate(a.rot, expand=True) for im in ims]
    pb, al = matte(*map(np.asarray, ims), a.bg)
    Image.fromarray(pb.astype(np.uint8)).save(a.out + '.rgb.png')
    Image.fromarray((al * 255 + .5).astype(np.uint8), 'L').save(a.out + '.a.png')
