"""Design references into kit data (docs/CHARKIT.md §5): read a 2D rig's layers (a front design split into parts, like
projects/tsuzuku/rig/clawd) and measure what the kit fits to, in head space (units of the head length L, z up from the
eye line, x = her left):
  - the hair's outline: its half-width on each side at every height (the hair volume's silhouette);
  - the fringe's lower contour and its tips (the bangs' tips);
  - the scale, from the eyes' spacing (the kit's eye spacing) and a check against the chin.
    ~/animation-pipeline/.venv/bin/python -m charkit.refs projects/tsuzuku/rig/clawd charkit/spec/clawd_ref.json [--eye-x 0.168]
"""
import json, os, sys
import numpy as np


def _layers(rig):
    m = json.load(open(os.path.join(rig, 'build', 'manifest.json')))
    return {l['name']: l for l in m['layers']}, m['size']


def _alpha(rig, layer, size):
    from PIL import Image
    W, H = size
    a = np.array(Image.open(os.path.join(rig, 'build', layer['name'] + '.png')).convert('RGBA'))[..., 3] > 40
    out = np.zeros((H, W), bool)
    x, y = layer['x'], layer['y']
    h, w = a.shape
    out[y:y + h, x:x + w] |= a[:max(0, min(h, H - y)), :max(0, min(w, W - x))]
    return out


def measure(rig, eye_x=0.168, hair=('hair_front', 'hair_side_L', 'hair_side_R'), fringe='hair_front', tip_x=0.26):
    lay, size = _layers(rig)
    ec = []
    for n in ('eye_L', 'eye_R'):
        l = lay[n]
        ec.append((l['x'] + l['w'] / 2, l['y'] + l['h'] / 2))
    (x1, y1), (x2, y2) = ec
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    ppl = abs(x2 - x1) / (2 * eye_x)                     # pixels per head length
    face = lay['face']
    chin = -(face['y'] + face['h'] - cy) / ppl
    mask = np.zeros(size[::-1], bool)
    for n in hair:
        if n in lay:
            mask |= _alpha(rig, lay[n], size)
    rows = np.nonzero(mask.any(1))[0]
    z, wl, wr = [], [], []
    for y in range(rows.min(), rows.max() + 1, 4):
        xs = np.nonzero(mask[y])[0]
        if len(xs) == 0:
            continue
        z.append((cy - y) / ppl)
        # her left is the image's right (a front view)
        wr.append(max(0.0, (cx - xs.min()) / ppl)); wl.append(max(0.0, (xs.max() - cx) / ppl))
    # the fringe's lower contour across the face, and its tips (local lowest points)
    fm = _alpha(rig, lay[fringe], size)
    fx0, fx1 = face['x'], face['x'] + face['w']
    cont = []
    for x in range(int(fx0), int(fx1), 3):
        ys = np.nonzero(fm[:, x])[0]
        if len(ys):
            cont.append(((x - cx) / ppl, (cy - ys.max()) / ppl))
    cont = np.array(cont)
    tips = []
    for i in range(3, len(cont) - 3):
        if abs(cont[i, 0]) > tip_x:
            continue                                      # beyond the eyes the front layer is the side hair, not bangs
        if cont[i, 1] <= cont[i - 3:i + 4, 1].min() and (not tips or abs(cont[i, 0] - tips[-1][0]) > 0.04):
            tips.append((float(-cont[i, 0]), float(cont[i, 1])))     # x flipped: her left = +x
    # the face's contour below the eyes (the face layer is bled out under the hair by `bleed` px; take it back), as the
    # kit's lower-face half-width profile: d = 0 at the eye line .. 1 at the chin
    fl = _alpha(rig, face, size)
    # the face plate runs a little under the hair and outline (measured against the visible skin on Clawd: ~15 px)
    bleed = max(15, json.load(open(os.path.join(rig, 'build.json'))).get('bleed', 0))
    prof = []
    for d in (0.0, 0.2, 0.4, 0.6, 0.8, 0.93, 1.0):
        y = int(round(cy - d * chin * ppl))
        xs = np.nonzero(fl[min(y, fl.shape[0] - 1)])[0]
        hw = ((xs.max() - xs.min()) / 2 - bleed) / ppl if len(xs) else 0.0
        prof.append(max(0.015, hw))
    # feature landmarks from their layers (heights from the eye line, in L): the mouth line's lowest point (a smile dips in
    # the middle), the nose tip, the brows' centre; the eye layers' size (lashes included)
    feat = {}
    if 'mouth' in lay:
        mm = _alpha(rig, lay['mouth'], size)
        ys, xs = np.nonzero(mm)
        mid = np.abs(xs - cx) < 0.02 * ppl
        feat['mouth_z'] = float((cy - (ys[mid].max() if mid.any() else ys.mean())) / ppl)
    if 'nose' in lay:
        l_ = lay['nose']; feat['nose_z'] = float((cy - (l_['y'] + l_['h'])) / ppl)
    bz = [(cy - (lay[n]['y'] + lay[n]['h'] / 2)) / ppl for n in ('brow_L', 'brow_R') if n in lay]
    if bz:
        feat['brow_z'] = float(min(bz))
    feat['eye_w'] = float(np.mean([lay[n]['w'] for n in ('eye_L', 'eye_R')]) / ppl)
    feat['eye_h'] = float(np.mean([lay[n]['h'] for n in ('eye_L', 'eye_R')]) / ppl)
    return dict(ppl=ppl, chin=chin, hair_z=z, hair_wl=wl, hair_wr=wr, top=float(max(z)), bottom=float(min(z)),
                fringe=[(float(-a), float(b)) for a, b in cont], fringe_tips=sorted(tips), face_wf=prof, features=feat)


if __name__ == '__main__':
    rig, out = sys.argv[1], sys.argv[2]
    ex = float(sys.argv[sys.argv.index('--eye-x') + 1]) if '--eye-x' in sys.argv else 0.168
    R = measure(rig, ex)
    json.dump(R, open(out, 'w'), indent=1)
    print('px/L %.0f  chin %.3f L  hair z %.2f..%.2f  tips %s' % (R['ppl'], R['chin'], R['bottom'], R['top'],
                                                                   [(round(a, 3), round(b, 3)) for a, b in R['fringe_tips']]))
