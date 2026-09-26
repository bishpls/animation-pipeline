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
    .venv/bin/python projects/tsuzuku/rig/fable_room/build.py            (the walk-out: room/)
    .venv/bin/python projects/tsuzuku/rig/fable_room/build.py ending     (the room ending: ending/)
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


# ================================================================================================================ the room ending
# (Michael + Fable, the final chorus: she stays in the room, lantern in hand, watching the window.) Written to ending/.
# The stationary drawings are hold with patches: only what an edit changed is pasted onto hold (the diff, cleaned and feathered),
# never the lantern arm, so the lantern, its stick, the fist and the far sleeve are hold's own pixels from 177.8 to the walk-off
# ("the lantern hand holds still throughout"). Patches: a head state (hood up / down, chin up / down), an arm state (the push,
# the wipe), or both from one drawing (the push). The step, the turn and the walk-off are whole drawings, placed by their geta.
LANTERN = [(400, 1090, 700, 1625), (515, 1025, 835, 1140), (770, 995, 962, 1345)]   # hold, full res: lantern, stick + fist, far sleeve
ENDOUT = os.path.join(D, 'ending')


def lantern_center(img):
    """the lit lantern: the largest patch of bright paper (full-res px)"""
    r, g, b = [img[..., i].astype(int) for i in range(3)]
    m = ndi.binary_closing((img[..., 3] > 200) & (r > 235) & (g > 185) & (b > 80) & (b < 215), iterations=6)
    lab, n = ndi.label(m)
    if not n: return None
    k = 1 + int(np.argmax(ndi.sum(m, lab, range(1, n + 1)))); cy, cx = ndi.center_of_mass(lab == k); return cx, cy


def feather_mask(ch, grow=10, soft=6):
    ch = ndi.binary_fill_holes(ndi.binary_closing(ch, iterations=4))
    return np.clip(ndi.distance_transform_edt(ndi.binary_dilation(ch, iterations=grow)) / soft, 0, 1)


def changed(img, ref, zone, thr=30, minpx=600):
    a0 = ref[..., 3:] / 255.; a1 = img[..., 3:] / 255.
    d = np.abs(img[..., :3] * a1 - ref[..., :3] * a0).max(-1)
    ch = ndi.binary_opening(ndi.gaussian_filter(d, 2) > thr, iterations=2)
    lab, n = ndi.label(ch)
    if n: ch = np.isin(lab, 1 + np.flatnonzero(ndi.sum(ch, lab, range(1, n + 1)) > minpx))
    return ch & zone


def blend(dst, src, m):
    """dst with src pasted through the soft mask m (premultiplied lerp)"""
    pa = lambda a: np.dstack([a[..., :3].astype(np.float32) * (a[..., 3:] / 255), a[..., 3:].astype(np.float32)])
    A, B = pa(dst), pa(src); P = A * (1 - m[..., None]) + B * m[..., None]
    al = P[..., 3:]; rgb = np.where(al > 0, P[..., :3] / np.maximum(al, 1e-6) * 255, 0)
    return np.dstack([np.clip(rgb, 0, 255), np.clip(al, 0, 255)]).astype(np.uint8)


def ending():
    os.makedirs(ENDOUT, exist_ok=True)
    base = key(os.path.join(FS, 'src/room/base_room.png')); H, W = base.shape[:2]; yy, xx = np.mgrid[:H, :W]
    cz = (xx < 960) & (yy > 2150)
    props = with_alpha(base, cz & (xx <= 940))                           # the cushion (as rig/fable_stage/build.py cut it)
    lab, n = ndi.label(props[..., 3] > 60)
    big = 1 + int(np.argmax(ndi.sum(props[..., 3] > 60, lab, range(1, n + 1)))); props = with_alpha(props, ndi.binary_dilation(lab == big, iterations=2))
    CUSH = ndi.binary_dilation(props[..., 3] > 40, iterations=4)
    hold0 = figure_only(base, cushion_mask(base), CUSH)                  # (hold as drawn: what every edit's change is measured from)
    keep = np.zeros((H, W), bool)
    for bx in LANTERN: keep |= box_mask((H, W), bx)
    zone = ~keep & (yy < 1800) & ~CUSH                                   # (patches: never the lantern arm; never the feet or the floor)
    SRC = os.path.join(D, 'src'); reg = {}
    def load_reg(n):
        img, (dx, dy, e) = register(key(os.path.join(SRC, n + '.png')), base); print(f'{n:8s} shift {dx},{dy} resid {e:.3f}')
        return figure_only(img, cushion_mask(img), CUSH)
    for n in ['e_down', 'e_push1', 'e_push2', 'e_push3', 'e_wipe1', 'e_wipe2', 'e_hu_up', 'e_hd_up', 'e_hd_dn']: reg[n] = load_reg(n)
    # the deckle edge (Fable's ruling; the director: "the deckle reads as fur"): the base, and every drawing whose patch shows a
    # cuff, is its deckle edit (k_*: the same drawing, the trim redrawn as a thin torn edge in a lighter value of the cloth). The
    # patch masks still come from the original edits against the original hold (the gesture's region), the pixels from k_*
    hold = load_reg('k_hold')
    K = {n: load_reg('k_' + n[2:]) for n in ['e_push1', 'e_push2', 'e_push3', 'e_wipe1', 'e_wipe2']}
    M = {n: feather_mask(changed(reg[n], hold0, zone)) for n in reg}
    # (head patches: never a cuff or the hem, where the fur was; the model re-rendered its texture everywhere)
    trims = box_mask((H, W), (990, 1240, 1310, 1410)) | (yy >= 1585)
    headz = ndi.gaussian_filter((~trims).astype(np.float32), 4)
    armz = ndi.gaussian_filter((yy < 1585).astype(np.float32), 4)
    out = {'u': hold}
    for n, k in [('e_hu_up', 'u_up'), ('e_down', 'd'), ('e_hd_up', 'd_up'), ('e_hd_dn', 'd_dn')]:
        out[k] = blend(hold, reg[n], M[n] * headz)
    for n, k in [('e_wipe1', 'push0'), ('e_push1', 'push1'), ('e_push2', 'push2'), ('e_push3', 'push3')]:
        out[k] = blend(hold, K[n], M[n] * armz)
    # the wipe with the hood down: the hood-down head, then the raised arm (in front of the hood fallen on her shoulders); the arm
    # only: in front of her body, below the jaw (the rest of those edits is the hood-up drawing's)
    arm = ((xx < 1170) & (yy > 520)) | ((xx < 1320) & (yy > 1000))
    for n, k in [('e_wipe1', 'd_wipe1'), ('e_wipe2', 'd_wipe2')]:
        out[k] = blend(out['d'], K[n], M[n] * ndi.gaussian_filter(arm.astype(np.float32), 5) * armz)
    # whole drawings: the step, the turn, the walk-off (the cushion cut by colour: the only prop; the back geta may sit over it)
    for n, k in [('k_step2', 'step'), ('k_turn1', 'turn1'), ('k_turn2', 'turn2'), ('k_wc1', 'wc1'), ('k_wp1', 'wp1'), ('k_wc2', 'wc2')]:
        img = key(os.path.join(SRC, n + '.png'))
        # the cushion: where this drawing matches hold's cushion at the same place (these edits keep it where hold has it), in
        # its footprint; its torn shadow edge left of her feet; and its tassels (purple). Her tabi, geta and skirt over it stay.
        near = (np.abs(img[..., :3].astype(int) - props[..., :3].astype(int)).max(-1) < 36) & (img[..., :3].astype(int).sum(-1) < 560)
        foot = ndi.binary_dilation(CUSH, iterations=6)
        plum = props[..., :3].astype(int).sum(-1)                        # (not its black outline: the geta over it would lose a notch)
        cush = foot & ((near & (props[..., 3] > 100) & (plum > 150)) | (img[..., 3] < 100))
        r, g, b = [img[..., i].astype(int) for i in range(3)]
        purple = foot & (((r > g + 20) & (b > g + 20) & (r + g + b < 480)) | ((b > 170) & (b > r + 80)))   # (tassels; its blue lights; not the lavender tabi)
        edge = (yy > 2370) & (xx < 900) & navy_mask(img) & ((r + g + b) < 360)   # (its torn bottom edge on the floor: dark navy)
        cush = ndi.binary_opening(cush | purple, iterations=1) | ((xx < 640) & (yy > 2000)) | ((xx < 700) & (yy > 2380)) | ndi.binary_dilation(edge, iterations=2)
        fig = (img[..., 3] > 0) & ~cush                                  # (in the footprint, no slivers: what's left there is geta,
        thin = foot & fig & ~ndi.binary_opening(fig, iterations=3)       #  tabi or skirt, all solid)
        out[k] = figure_only(img, cush | thin, np.zeros_like(cush))       # (no default navy cut: the tabi shades lavender)
    meta = {'scale': SC, 'size': [round(W * SC), round(H * SC)], 'points': {}, 'drawings': {}}
    h = lambda p: [round(p[0] * SC, 1), round(p[1] * SC, 1)]
    for k, img in out.items():
        facing = 1 if k in ('turn2', 'wc1', 'wp1', 'wc2') else -1
        f = geta(img, xmin=0, facing=facing)
        g = [{'toe': h(q['toe']), 'box': [round(v * SC, 1) for v in q['box']], 'lift': round(q['lift'] * SC, 1)} for q in f['geta']]
        lc = lantern_center(img)
        ys, xs = np.nonzero(img[..., 3] > 128)
        meta['drawings'][k] = {'file': k + '.png', 'sole': round(f['sole'] * SC, 1), 'geta': g, 'crown': round(ys.min() * SC, 1),
                               'lantern': h(lc) if lc else None}
        save_to(img, os.path.join(ENDOUT, k + '.png'))
    save_to(props, os.path.join(ENDOUT, 'props.png')); meta['drawings']['props'] = {'file': 'props.png'}
    meta['points']['feet'] = [559.0, 1218.5]                             # (the room drawings' feet: T is given there)
    json.dump(meta, open(os.path.join(ENDOUT, 'meta.json'), 'w'), indent=1)
    for k, d in meta['drawings'].items():
        if 'geta' in d: print(f'{k:8s} sole {d["sole"]:7.1f} crown {d["crown"]:6.1f} lantern {d["lantern"]}  geta', [(q['toe'], q['lift']) for q in d['geta']])


def save_to(img, path):
    H, W = img.shape[:2]
    Image.fromarray(bleed(img)).resize((round(W * SC), round(H * SC)), Image.LANCZOS).save(path)


if __name__ == '__main__':
    ending() if sys.argv[1:] == ['ending'] else main()
