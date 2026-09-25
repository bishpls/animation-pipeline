"""The prologue's far stage: HELLO, WORLD!'s own frames (assets/prologue_hw/s/, 12 fps from HW time 129.88 s), with two edits
the kuroko makes (Fable's review):
  hop   one chibi Clawd (the crowned box crab) hops on one rod beat: cut from its frame, the hole inpainted, lifted
  pull  she pulls the lyric card: from that drawing the burned-in subtitle is gone from the stage

    ../../../../.venv/bin/python hw_edit.py     -> assets/prologue_hw/s/hop_KKK.jpg, nt_KKK.jpg + board/fable/_hw_edit.jpg
"""
import os
import numpy as np, cv2
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(os.path.dirname(HERE))
S = os.path.join(PROJ, 'assets', 'prologue_hw', 's')
HOP = {38: 26, 39: 40, 40: 42, 41: 22}      # drawing -> lift (frame px): up on the rod beat, apex held a drawing, down; lands on 42
PULL = range(44, 102)                       # drawings with the subtitle gone (the pull is at 46; a margin either side)
CRAB = (690, 240, 960, 452)                 # the crowned crab's box (frame px): the right side of the unmirrored frame


def crab_mask(img):
    x0, y0, x1, y1 = CRAB; b = img[y0:y1, x0:x1].astype(int); B, G, R = b[..., 0], b[..., 1], b[..., 2]
    ink = (G < 165) | ((R + G + B) < 330)                                   # its brown paper and dark outline (the rays are yellow)
    ink = ndi.binary_closing(ink, iterations=2); ink = ndi.binary_fill_holes(ink)   # the crown and eyes, enclosed by the outline
    lab, n = ndi.label(ink); m = lab == (np.argmax(ndi.sum(ink, lab, range(1, n + 1))) + 1)
    full = np.zeros(img.shape[:2], bool); full[y0:y1, x0:x1] = ndi.binary_dilation(m, iterations=2); return full


def text_mask(img):
    b = img.astype(int); B, G, R = b[..., 0], b[..., 1], b[..., 2]; y = np.arange(img.shape[0])[:, None]
    band = (y > 441) & (y < 522)
    white = (R > 215) & (G > 215) & (B > 205); pink = (R > 190) & (G < 150) & (B > 110)
    return ndi.binary_dilation(ndi.binary_closing((white | pink) & band, iterations=3), iterations=9) & band


def main():
    review = []
    for k, lift in HOP.items():
        img = cv2.imread(os.path.join(S, f'{k:03d}.jpg')); m = crab_mask(img)
        plate = cv2.inpaint(img, m.astype(np.uint8) * 255, 7, cv2.INPAINT_TELEA)
        out = plate.copy(); ys, xs = np.where(m); out[ys - lift, xs] = img[ys, xs]
        cv2.imwrite(os.path.join(S, f'hop_{k:03d}.jpg'), out, [cv2.IMWRITE_JPEG_QUALITY, 94]); review.append(out)
    for k in PULL:
        img = cv2.imread(os.path.join(S, f'{k:03d}.jpg')); m = text_mask(img)
        cv2.imwrite(os.path.join(S, f'nt_{k:03d}.jpg'), cv2.inpaint(img, m.astype(np.uint8) * 255, 13, cv2.INPAINT_TELEA), [cv2.IMWRITE_JPEG_QUALITY, 94])
        if k in (46, 50): review.append(cv2.imread(os.path.join(S, f'nt_{k:03d}.jpg')))
    n = len(HOP); top = np.hstack(review[:n]); bot = np.hstack(review[n:] + [np.zeros_like(review[0])] * (2 * n - len(review)))
    cv2.imwrite(os.path.join(PROJ, 'board', 'fable', '_hw_edit.jpg'), cv2.resize(np.vstack([top, bot]), None, fx=.6, fy=.6))
    print('hop', list(HOP), 'pull', PULL.start, '-', PULL.stop - 1)


if __name__ == '__main__':
    main()
