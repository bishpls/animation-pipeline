"""Probe: the hand sheet's cells (handref.figures) at the sheet's own px, the open pose's hand mask, its contour's
tips (local maxima of the distance along the arm from the cuff) -> a picture and numbers."""
import sys, json
sys.path.insert(0, '.')
import numpy as np
from PIL import Image
from scipy import ndimage
from charkit import handref, handqa
rgb = np.asarray(Image.open('charkit/refs/clawd/gen/hand_breakdown.png').convert('RGB'))
F = handref.figures(rgb)
print(len(F), [(f['row'], f['col'], f['box']) for f in F])
for f in F:
    wpx = handref.cuff_width_px(f)
    sk = ndimage.binary_fill_holes(ndimage.binary_closing(f['skin'], iterations=3) & ~f['cuff'])
    h = handqa.hand_mask(sk, f['cuff'], wpx)       # (ppl = the cuff's width in px: lengths in cuff widths)
    if h is None:
        print(f['row'], f['col'], 'no hand'); continue
    print(f['row'], f['col'], 'cuff px', round(wpx, 1), 'reach (cuff widths)', round(handqa.reach(h, wpx), 3),
          'u', np.round(h['u'], 3), 'px', int(h['mask'].sum()))
