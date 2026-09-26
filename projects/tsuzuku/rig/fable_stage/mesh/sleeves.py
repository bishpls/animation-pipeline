"""Fable's sleeves, from the no-arms companion (her jacket with the sleeves taken off, registered on the base).
A kimono sleeve over a black jacket has no drawn line to cut along, so the sleeve is defined by the drawing itself: what the base
has and the no-arms drawing doesn't (minus the hands and cuffs), grown 30 px into the body so it covers the jacket's side at rest.
  masks: writes seg/sleeve_L.png, seg/sleeve_R.png (run before tools/layers.py)
  jacket: under each sleeve, the jacket layer's pixels become the no-arms drawing's (its drawn side contour, pink rim and line):
          hidden at rest by the sleeve, seen when the sleeve lifts (run after tools/layers.py, before tools/rigbuild.py)
    .venv/bin/python rig/fable_stage/mesh/sleeves.py masks|jacket
"""
import os, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

D = os.path.dirname(os.path.abspath(__file__)); P = lambda *a: os.path.join(D, *a)
rgba = lambda p: np.array(Image.open(p).convert('RGBA'))


def sleeve_zone():
    B, N = rgba(P('..', 'base_stage_keyed.png')), rgba(P('under', 'noarms_al.png'))
    ba, na = B[..., 3] > 128, N[..., 3] > 128
    zone = np.zeros_like(ba); zone[700:1800] = True
    hc = np.zeros_like(ba)
    for n in ['hand_L', 'hand_R', 'cuff_L', 'cuff_R']: hc |= np.array(Image.open(P('seg', n + '.png'))) > 127
    hc = ndi.binary_dilation(hc, iterations=6)
    diff = ba & ~ndi.binary_dilation(na, iterations=2) & zone & ~hc
    sl = ndi.binary_dilation(diff, iterations=30) & ba & zone & ~hc
    xs = np.arange(ba.shape[1])[None, :]
    out = {}
    for side, m in [('L', sl & (xs < 1015)), ('R', sl & (xs >= 1015))]:
        lab, n = ndi.label(m); sz = ndi.sum(m, lab, range(1, n + 1)); out[side] = lab == (int(np.argmax(sz)) + 1)
    return out, N


if __name__ == '__main__':
    S, N = sleeve_zone()
    if sys.argv[1] == 'masks':
        for s, m in S.items(): Image.fromarray((m * 255).astype(np.uint8)).save(P('seg', f'sleeve_{s}.png')); print(s, m.sum())
    else:
        J = rgba(P('layers', 'jacket.png')); nj = rgba(P('under', 'layers_noarms', 'jacket.png'))[..., 3] > 128
        m = (S['L'] | S['R']) & nj & (N[..., 3] > 200)
        J[m] = N[m]
        # strays: bits of the sleeves' drawn lines the split gave the jacket (e.g. a cuff's inner line), left floating in the air
        # where the sleeve hung at rest once the sleeve moves: the jacket keeps only its large pieces
        lab, n = ndi.label(J[..., 3] > 8); sz = ndi.sum(np.ones_like(lab), lab, range(1, n + 1)); keep = np.isin(lab, 1 + np.nonzero(sz > 20000)[0])
        J[~keep, 3] = 0
        Image.fromarray(J).save(P('layers', 'jacket.png')); print('jacket: +', m.sum(), 'px from the no-arms drawing under the sleeves;', int((sz <= 20000).sum()), 'stray pieces dropped')
