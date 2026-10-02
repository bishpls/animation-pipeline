"""face visibility (Michael: "her face is still largely covered"): front and three-quarter, with the hair against
without it: the share of the eyes' pixels (sclera, iris, lashes) still visible, and of the face's skin in the face box
(between the outer eye corners widened 40%, from the brows to the chin)."""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
sys.path.insert(0, os.path.expanduser('~/animation-pipeline-3d'))
import studio as S
from charkit import bundle as bl, palette


def face_vis(bdir):
    B = bl.load(bdir); palette.activate_spec(B.spec)
    res = {}
    for v, az in (('front', 0.0), ('three_quarter', 35.0)):
        S.NAMES.clear()
        with_h = S.lockmap(B, az)
        S.NAMES.clear()
        no_h = S.lockmap(B, az, skip_hair=True)
        eyes0 = no_h == -4
        eyes1 = with_h == -4
        ys, xs = np.where(eyes0)
        if not len(ys):
            continue
        H = with_h.shape[0]
        cx, w = (xs.min() + xs.max()) / 2, (xs.max() - xs.min()) * 1.4 / 2
        top = ys.min() - (ys.max() - ys.min()) * 0.8
        bot = ys.max() + (ys.max() - ys.min()) * 2.6
        box = np.zeros_like(eyes0)
        box[int(max(top, 0)):int(min(bot, H)), int(max(cx - w, 0)):int(cx + w)] = True
        f0 = (no_h == -3) & box
        f1 = (with_h == -3) & box
        eh = ys.max() - ys.min()
        fh = np.zeros_like(eyes0)
        fh[int(max(ys.min() - 2.6 * eh, 0)):int(max(ys.min() - 0.7 * eh, 0)), int(xs.min()):int(xs.max())] = True
        h0 = (no_h == -3) & fh
        h1 = (with_h == -3) & fh
        res[v] = dict(eyes=round(float(eyes1.sum() / max(eyes0.sum(), 1)), 3), face=round(float(f1.sum() / max(f0.sum(), 1)), 3),
                      forehead=round(float(h1.sum() / max(h0.sum(), 1)), 3))
    return res


if __name__ == '__main__':
    for b in sys.argv[1:]:
        print(os.path.basename(b), json.dumps(face_vis(b)))
