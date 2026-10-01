"""layerref's new kinds calibrated (garments8, 2026-10-01): each must PASS on the design and FAIL on a known-bad.

  top:          the turnaround itself moved 2 px (PASS; the collar and bow are the free cover) / its torso band widened
                6% about each figure's middle (FAIL), as bodicecal did for the bodice kind
  collar_ghost: the turnaround's own collar (the outfit truth's, each view cut to its box: a ghost drawn exactly) moved,
                and at 2.3x (the takes' size: the registration is a similarity) (PASS) / stretched 12% across (FAIL) /
                the collar drawn on the bare base body (collar_alone take 1's layer: the failure seen) (FAIL)
  bow_ghost:    the same with the bow

    python tools/garments8/layercal.py > charkit/out/garments8/layercal.txt
"""
import json, os, sys
sys.path.insert(0, os.getcwd())
import numpy as np
from scipy import ndimage
from charkit import layerref as lr, manifest, sheetqa, eyes as eyelib

spec = manifest.resolve(json.load(open('charkit/spec/clawd.json')))
bs = spec['ref']['body_sheet']
rgb = lr._load(bs['image'])
ex = eyelib._knobs(spec.get('eyes'))['x']
D = sheetqa.detect_figures(rgb, None, ex, bs.get('facing', -1))
ppl = D['ppl']
quiet = lambda *a: None


def widened(rgb, k=1.06, z0=-0.45, z1=-1.40):
    out = rgb.copy()
    for v, f in D['figures'].items():
        if v not in lr.VIEWS:
            continue
        x0, y0, x1, y1 = f['box']
        ey = f['eye_y']
        cx = np.mean([e[0] for e in f['eyes']]) if len(f.get('eyes') or []) == 2 else 0.5 * (x0 + x1)
        r0, r1 = int(ey - z0 * ppl), int(ey - z1 * ppl)
        cols = np.arange(int(x0) - 40, int(x1) + 40)
        src = np.clip(np.round(cx + (cols - cx) / k).astype(int), 0, rgb.shape[1] - 1)
        out[r0:r1, cols] = rgb[r0:r1][:, src]
    return out


def moved(a, dy, dx):
    return np.roll(np.roll(a, dy, 0), dx, 1)


def brief(rep):
    return {v: (r.get('iou_dc'), r.get('outside'), r.get('recall'), r.get('pass')) for v, r in rep['views'].items()}


which = sys.argv[1:] or ['top', 'collar_ghost', 'bow_ghost']
if 'top' in which:
    for name, im in (('moved_2_2', moved(rgb, 2, 2)), ('moved_-2_1', moved(rgb, -2, 1)), ('widened_6pct', widened(rgb))):
        rep, _ = lr.check_layer(spec, name, 'top', log=quiet, rgb=im)
        print('top', name, 'PASS' if rep['pass'] else 'FAIL', brief(rep), flush=True)

TV = lr._truth_views(spec, quiet)


def truth_piece(pieces):
    out = []
    for v in lr.VIEWS:
        P = TV[v]['pieces']
        m = np.zeros(TV[v]['fg'].shape, bool)
        for p in pieces:
            m |= P.get(p, False)
        m = ndimage.binary_closing(m, iterations=3) & TV[v]['fg']
        out.append(m)
    return out


def stretch(m, kx, ky=1.0):
    ys, xs = np.nonzero(m)
    c = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    from PIL import Image
    im = Image.fromarray(c.astype(np.uint8) * 255)
    return np.asarray(im.resize((max(1, round(im.width * kx)), max(1, round(im.height * ky))), Image.NEAREST)) > 127


for kind, pieces in (('collar_ghost', ('collar',)), ('bow_ghost', lr.BODICE_COVER)):
    if kind not in which:
        continue
    G = truth_piece(pieces)
    if kind == 'bow_ghost':              # (the turnaround has no bow from behind: the back view given the front's)
        G = G[:3] + [G[0]]
    cases = [('itself', G), ('moved_3_-2', [moved(m, 3, -2) for m in G]),
             ('at_2.3x', [stretch(m, 2.3, 2.3) for m in G]),
             ('stretched_12pct_across', [stretch(m, 1.12) for m in G]),
             ('stretched_12pct_down', [stretch(m, 1.0, 1.12) for m in G])]
    if kind == 'collar_ghost':
        km = {}
        lr.check_layer(spec, 'charkit/out/garments8/gen/collar_alone_1.png', 'collar_alone', log=quiet, keep_masks=km)
        cases.append(('on_the_bare_body', [km[v]['C'] for v in lr.VIEWS]))
    for name, given in cases:
        rep, _ = lr.check_ghost(spec, name, kind, log=quiet, given=given)
        print(kind, name, 'PASS' if rep['pass'] else 'FAIL', 'scale', rep.get('scale'), 'spread',
              rep.get('scale_spread'), brief(rep), flush=True)
