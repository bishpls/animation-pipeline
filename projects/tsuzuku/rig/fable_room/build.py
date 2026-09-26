"""Fable in her room, 177.8-181 (src/fableroom.js): the drawings keyed, registered onto the room canvas of rig/fable_stage/room
(the base_room frame at scale .5: her standing feet at 559,1218.5) and cut from their props.

  hold, empty, props_hold      copied from rig/fable_stage/room (the drawing B9 hands off to at 177.8; she stands, hands empty)
  setdown                      rig/fable_stage/src/room/setdown.png: she kneels and sets the lantern on the cushion
  down, rise                   new: halfway down (the lantern about to touch), halfway up (hands empty)
  turn_l, front, turn_r        new: the turn, toward the viewer, the head leading
  walk_*                       new: the walk out right (contact u1/u2, trail s1/s2, passing m1, reach p1/p2), drawn walking in
                               place (walk_c1/c2/d1 are in src only: the model floated their back geta 40 px)
  props_down                   the cushion (props_hold) with the lantern and its stick where she set them in 'setdown'

Every figure layer is the figure alone (the props are drawn once, underneath, so they never jitter between drawings). Registration:
the cushion's free end (a shift, as rig/fable_stage/build.py). meta.json carries, per drawing, its geta (the front tooth of each:
the point a planted geta pivots on, full-res px / 2), its feet centre and sole, and the lantern where it carries one.
    .venv/bin/python projects/tsuzuku/rig/fable_room/build.py
"""
import json, os, sys
import numpy as np, cv2
from PIL import Image
from scipy import ndimage as ndi

D = os.path.dirname(os.path.abspath(__file__)); FS = os.path.join(D, '..', 'fable_stage')
sys.path.insert(0, os.path.join(D, '..', 'fable_seated')); sys.path.insert(0, D)
from key import key  # noqa: E402
from feet import geta  # noqa: E402

SC = .5
OUT = os.path.join(D, 'room')


def bleed(img, px=6):
    a = img[..., 3] > 16; rgb = img[..., :3].copy()
    if not a.any(): return img
    d, (iy, ix) = ndi.distance_transform_edt(~a, return_indices=True); m = (~a) & (d <= px)
    rgb[m] = img[iy[m], ix[m], :3]; o = img.copy(); o[..., :3] = rgb; return o


def save(img, name):
    """full-res RGBA (base frame) -> room/<name>.png at SC"""
    H, W = img.shape[:2]
    Image.fromarray(bleed(img)).resize((round(W * SC), round(H * SC)), Image.LANCZOS).save(os.path.join(OUT, name + '.png'))


def with_alpha(img, m):
    o = img.copy(); o[..., 3] = (img[..., 3].astype(np.float32) * np.clip(m, 0, 1)).astype(np.uint8); return o


def cushion_mask(img):
    """the purple-navy cushion (not the teal skirt, not the black geta), low in the frame at the left"""
    H, W = img.shape[:2]; yy, xx = np.mgrid[:H, :W]
    r, g, b = [img[..., i].astype(int) for i in range(3)]
    m = (img[..., 3] > 16) & (xx < 1000) & (yy > 2080) & (b > np.maximum(r, g) + 12) & (r >= g - 12)
    m = ndi.binary_closing(ndi.binary_opening(m, iterations=1), iterations=3)
    lab, n = ndi.label(m)
    if n: m = np.isin(lab, 1 + np.flatnonzero(ndi.sum(m, lab, range(1, n + 1)) > 4000))
    return ndi.binary_dilation(m, iterations=3) & (img[..., 3] > 0)


def register(img, base):
    """shift img onto base by the cushion's free end (its outline; the cushion is too plain for ECC)"""
    H, W = base.shape[:2]; win = (slice(2000, 2560), slice(60, 430))
    a0 = (base[..., 3] > 128)[win].astype(np.float32); A = (img[..., 3] > 128).astype(np.float32); best = (1e18, 0, 0)
    for dy in range(-60, 161, 4):
        for dx in range(-60, 61, 4):
            a1 = cv2.warpAffine(A, np.float32([[1, 0, dx], [0, 1, dy]]), (W, H))[win]
            best = min(best, (float(np.abs(a1 - a0).sum()), dx, dy))
    _, dx0, dy0 = best
    for dy in range(dy0 - 3, dy0 + 4):                                      # (refine to the pixel)
        for dx in range(dx0 - 3, dx0 + 4):
            a1 = cv2.warpAffine(A, np.float32([[1, 0, dx], [0, 1, dy]]), (W, H))[win]
            best = min(best, (float(np.abs(a1 - a0).sum()), dx, dy))
    e, dx, dy = best
    return cv2.warpAffine(img, np.float32([[1, 0, dx], [0, 1, dy]]), (W, H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0)), (dx, dy, e / a0.sum())


def lantern_box(img, x1=980, y0=1500):
    """the lit lantern (warm, bright) left of x1 and below y0: its box, grown to take the black caps and the handle"""
    H, W = img.shape[:2]; yy, xx = np.mgrid[:H, :W]
    r, g, b = [img[..., i].astype(int) for i in range(3)]
    lit = (img[..., 3] > 200) & (xx < x1) & (yy > y0) & (r > 215) & (g > 150) & (b < 190)
    lab, n = ndi.label(lit)
    if not n: return None
    k = 1 + int(np.argmax(ndi.sum(lit, lab, range(1, n + 1)))); ys, xs = np.nonzero(lab == k)
    return [int(xs.min()) - 22, int(ys.min()) - 70, int(xs.max()) + 22, int(ys.max()) + 34]


def over(dst, src):
    pa = lambda a: np.dstack([a[..., :3].astype(np.float32) * (a[..., 3:] / 255), a[..., 3:].astype(np.float32)])
    T, B = pa(src), pa(dst); P = T + B * (1 - T[..., 3:] / 255)
    A = P[..., 3:]; rgb = np.where(A > 0, P[..., :3] / np.maximum(A, 1e-6) * 255, 0)
    return np.dstack([np.clip(rgb, 0, 255), np.clip(A, 0, 255)]).astype(np.uint8)


def poly(shape, pts):
    m = np.zeros(shape, np.uint8); cv2.fillPoly(m, [np.array(pts, np.int32)], 1); return m.astype(bool)


def box_mask(shape, b):
    m = np.zeros(shape, bool)
    if b: m[max(0, b[1]):b[3], max(0, b[0]):b[2]] = True
    return m


def navy_mask(img):
    """the cushion's shadowed parts and tassels, low at the left (not the teal skirt: its green is well above its red; not the
    black geta)"""
    H, W = img.shape[:2]; yy, xx = np.mgrid[:H, :W]; r, g, b = [img[..., i].astype(int) for i in range(3)]
    m = (xx < 1000) & (yy > 2080) & (b > np.maximum(r, g) + 20) & (g < r + 25)
    return ndi.binary_dilation(m, iterations=2) & ~((r > b) & (r + g + b < 200))


def figure_only(img, drop, navy_in=None):
    """img with the props removed (drop: bool mask, plus the cushion's navy, only inside navy_in when given: the skirt's shadow
    is the same deep blue), and any specks the cut leaves behind"""
    nv = navy_mask(img)
    keep = (img[..., 3] > 0) & ~drop & ~(nv & navy_in if navy_in is not None else nv)
    lab, n = ndi.label(keep & (img[..., 3] > 60))
    if n > 1:
        s = ndi.sum(keep, lab, range(1, n + 1)); big = np.isin(lab, 1 + np.flatnonzero(s > .01 * s.max())); keep &= ndi.binary_dilation(big, iterations=2)
    return with_alpha(img, keep)


def main():
    os.makedirs(OUT, exist_ok=True)
    base = key(os.path.join(FS, 'src/room/base_room.png')); H, W = base.shape[:2]; yy, xx = np.mgrid[:H, :W]
    up = lambda n: np.asarray(Image.open(os.path.join(FS, 'room', n + '.png')).resize((W, H), Image.LANCZOS))   # (.5 -> full res)
    meta = {'scale': SC, 'size': [round(W * SC), round(H * SC)], 'points': {}, 'drawings': {}}
    h = lambda p: [round(p[0] * SC, 1), round(p[1] * SC, 1)]
    drawings = {}

    # the existing drawings (already cut by rig/fable_stage/build.py)
    hold, empty, props_hold = up('hold'), up('empty'), up('props_hold')
    lab, n = ndi.label(props_hold[..., 3] > 60)                            # (the cushion alone: its cut kept a sliver of her skirt at
    if n > 1:                                                               #  its right, hidden behind her until she walks away)
        big = 1 + int(np.argmax(ndi.sum(props_hold[..., 3] > 60, lab, range(1, n + 1))))
        props_hold = with_alpha(props_hold, ndi.binary_dilation(lab == big, iterations=2))
    CUSH = ndi.binary_dilation(props_hold[..., 3] > 40, iterations=4)       # (the cushion's footprint)
    drawings['hold'] = hold; drawings['empty'] = empty
    save(props_hold, 'props_hold')

    # the set-down lantern and stick, from 'rise' (they stand where 'setdown' put them, to a few px, and no hand covers the stick):
    # from the kneel on they're props, drawn once under every drawing, so the lantern stays exactly where she set it
    SRC = os.path.join(D, 'src')
    reg = {}
    for n in ['bend', 'down', 'rise', 'rise2', 'turn_l', 'front', 'turn_r', 'walk_s1', 'walk_m1', 'walk_p1', 'walk_s2', 'walk_p2', 'walk_u1', 'walk_u2']:   # (walk_c1/c2/d1: unused, their back geta floats)
        if not os.path.exists(os.path.join(SRC, n + '.png')): print('missing', n); continue
        reg[n], (dx, dy, e) = register(key(os.path.join(SRC, n + '.png')), base); print(f'{n:8s} shift {dx},{dy}  resid {e:.3f}')
    sd, (dx, dy, e) = register(key(os.path.join(FS, 'src/room/setdown.png')), base); print(f'setdown  shift {dx},{dy}  resid {e:.3f}')
    LBOX = [415, 1812, 697, 2312]                                          # (full res: the handle's top to the base ring)
    STICK = poly((H, W), [(592, 2280), (760, 2228), (852, 2212), (866, 2276), (772, 2290), (606, 2324)])
    rise = reg['rise']; cz = cushion_mask(rise)
    lant = (box_mask((H, W), LBOX) | STICK) & ~cz & (rise[..., 3] > 0)
    props_down = over(props_hold, with_alpha(rise, lant))
    save(props_down, 'props_down')
    meta['points']['lantern_down'] = h((556, 2080)); meta['points']['lantern_low'] = h((528, 1978))
    meta['points']['lantern_hand'] = [278.0, 680.5]                        # (rig/fable_stage/room/meta.json)
    r, g, b = [sd[..., i].astype(int) for i in range(3)]
    skin = (r > 190) & (g > 160) & (b > 140) & (r - b > 10) & (r - b < 90)
    skin = ndi.binary_dilation(ndi.binary_opening(skin, iterations=2), iterations=3)
    drawings['setdown'] = figure_only(sd, cushion_mask(sd) | ((box_mask((H, W), LBOX) | STICK) & ~skin), CUSH)
    drawings['rise'] = figure_only(rise, cz | box_mask((H, W), LBOX) | STICK, CUSH)
    for n in ('bend', 'down'):                                             # (the lantern is still in her hand)
        if n in reg: drawings[n] = figure_only(reg[n], cushion_mask(reg[n]), CUSH)
    if 'rise2' in reg: drawings['rise2'] = figure_only(reg['rise2'], cushion_mask(reg['rise2']) | box_mask((H, W), LBOX) | STICK, CUSH)
    if 'bend' in reg:                                                      # (the lantern in hand: the centre of its lit paper)
        lb = lantern_box(reg['bend'], x1=800, y0=1000); meta['points']['lantern_bend'] = h(((lb[0] + lb[2]) / 2, (lb[1] + lb[3]) / 2 + 18))
    # standing and walking: the props (cushion, lantern, stick) are all left of x 800 above the floor; the cushion's right end and
    # its tassel by colour (the back geta reaches x 832 in the walk)
    for n, img in reg.items():
        if n in drawings: continue
        r, g, b = [img[..., i].astype(int) for i in range(3)]
        navy = (xx < 960) & (yy > 2200) & (b > np.maximum(r, g) + 20) & (g < r + 25)      # (the cushion's shadowed corner and tassel,
        navy = ndi.binary_dilation(navy, iterations=2) & ~((r > b) & (r + g + b < 200))     #  touching the back geta: not the teal skirt)
        drawings[n] = figure_only(img, ((xx < 800) & (yy > 1780)) | ((xx < 960) & (yy > 2380)) | cushion_mask(img) | (navy & CUSH), CUSH)

    # key points per drawing: the geta (front tooth), the feet centre and the sole
    for n, img in drawings.items():
        facing = -1 if n in ('hold', 'empty', 'setdown', 'bend', 'down', 'rise', 'rise2', 'turn_l') else 1
        if n not in reg and n not in ('hold', 'empty', 'setdown'): continue
        f = geta(img, xmin=0, facing=facing)
        g = [{'toe': h(q['toe']), 'box': [round(v * SC, 1) for v in q['box']], 'lift': round(q['lift'] * SC, 1)} for q in f['geta']]
        cx = np.mean([(q['box'][0] + q['box'][2]) / 2 for q in f['geta']]) if f['geta'] else float('nan')
        ys, xs = np.nonzero(img[..., 3] > 128)
        meta['drawings'][n] = {'file': n + '.png', 'sole': round(f['sole'] * SC, 1), 'feet_cx': round(cx * SC, 1), 'geta': g,
                               'crown': [round(float(np.median(xs[ys < ys.min() + 6])) * SC, 1), round(ys.min() * SC, 1)]}
        save(img, n)
    meta['points']['feet'] = [meta['drawings']['hold']['feet_cx'], meta['drawings']['hold']['sole']]
    meta['drawings']['props_hold'] = {'file': 'props_hold.png'}; meta['drawings']['props_down'] = {'file': 'props_down.png'}
    json.dump(meta, open(os.path.join(OUT, 'meta.json'), 'w'), indent=1)
    for n, d in meta['drawings'].items():
        if 'geta' in d: print(f'{n:9s} sole {d["sole"]:7.1f} feet_cx {d["feet_cx"]:6.1f} crown {d["crown"]}  geta', [(q['toe'], q['lift']) for q in d['geta']])
    print('points', meta['points'])


if __name__ == '__main__':
    main()
