"""Fable standing (the final chorus): cut the illustrated drawings into the pieces src/fablestage.js animates.

STAGE (on Clawd's stage, front view, a riveted cut-out puppet): src/base_stage.png plus GPT Image edits of it (src/poses: noarms,
nohead, hoodup, hoodpush, face_*), registered onto the base. Parts from SAM (seg/: hair, face, skirt, feet, hands) and from the
no-arms drawing (the sleeves are what the body lacks). Every piece rotates about a brass rivet; the pieces underneath are real
drawing (the sleeveless jacket, the headless collar, a shadowed under-skirt), and each upper sleeve carries a fan past its elbow
cut (mirrored cloth) so a bent elbow never opens a hole. Writes stage/<piece>.png at SC and stage/meta.json.
ROOM (177.8-181, in Fable's room, profile facing left, hood up): src/room drawings keyed and registered on the cushion; the
props (cushion, book, the lantern once it's set down) cut from the figure. Writes room/<drawing>.png and room/meta.json.
    .venv/bin/python rig/fable_stage/build.py [stage|room]
"""
import json, os, sys
import numpy as np, cv2
from PIL import Image
from scipy import ndimage as ndi

D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(D, '..', '..', '..', '..', 'tools'))
from chroma import key  # noqa: E402

lum = lambda a: ((a[..., :3].astype(np.float32) @ [.299, .587, .114]) * (a[..., 3] / 255) + 255 * (1 - a[..., 3] / 255)).astype(np.float32)
feather = lambda m, r: np.clip(ndi.distance_transform_edt(m) / r, 0, 1)


def register(img, base, mask, motion=cv2.MOTION_AFFINE):
    """img warped onto base, fitted on mask (coarse to fine)"""
    H, W = base.shape[:2]; warp = np.eye(2, 3, dtype=np.float32)
    for sc in (.125, .25, .5):
        a = cv2.GaussianBlur(cv2.resize(lum(base), None, fx=sc, fy=sc), (0, 0), 1.2)
        b = cv2.GaussianBlur(cv2.resize(lum(img), None, fx=sc, fy=sc), (0, 0), 1.2)
        w = warp.copy(); w[:, 2] *= sc
        _, w = cv2.findTransformECC(a, b, w, motion, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 300, 1e-6),
                                    cv2.resize(mask.astype(np.uint8), None, fx=sc, fy=sc, interpolation=cv2.INTER_NEAREST), 5)
        warp = w.copy(); warp[:, 2] /= sc
    al = cv2.warpAffine(img, warp, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderValue=(0, 0, 0, 0))
    return al, float(np.abs(lum(al) - lum(base))[mask].mean())


def colour_match(al, base, k):
    for c in range(3):
        sa, sb = al[k, c].astype(float), base[k, c].astype(float)
        al[..., c] = np.clip((al[..., c] - sa.mean()) / (sa.std() + 1e-6) * sb.std() + sb.mean(), 0, 255).astype(np.uint8)
    return al


def with_alpha(img, m):
    o = img.copy(); o[..., 3] = (img[..., 3].astype(np.float32) * np.clip(m, 0, 1)).astype(np.uint8); return o


def over(dst, src):
    pa = lambda a: np.dstack([a[..., :3].astype(np.float32) * (a[..., 3:] / 255), a[..., 3:].astype(np.float32)])
    T, B = pa(src), pa(dst); P = T + B * (1 - T[..., 3:] / 255)
    A = P[..., 3:]; rgb = np.where(A > 0, P[..., :3] / np.maximum(A, 1e-6) * 255, 0)
    return np.dstack([np.clip(rgb, 0, 255), np.clip(A, 0, 255)]).astype(np.uint8)


def bleed(img, px=6):
    """colour pushed outward under transparent pixels (no dark fringes when scaled or rotated)"""
    a = img[..., 3] > 16; rgb = img[..., :3].copy()
    if not a.any(): return img
    _, (iy, ix) = ndi.distance_transform_edt(~a, return_indices=True)
    d = ndi.distance_transform_edt(~a); m = (~a) & (d <= px)
    rgb[m] = img[iy[m], ix[m], :3]; o = img.copy(); o[..., :3] = rgb; return o


def poly(shape, pts):
    m = np.zeros(shape, np.uint8); cv2.fillPoly(m, [np.array(pts, np.int32)], 1); return m.astype(bool)


# ---------------------------------------------------------------------------------------------------------------------- stage
def stage():
    SC = .75; out_dir = os.path.join(D, 'stage'); os.makedirs(out_dir, exist_ok=True)
    base = key(os.path.join(D, 'src/base_stage.png')); H, W = base.shape[:2]; A = base[..., 3] > 128
    seg = {n: ndi.binary_fill_holes(ndi.binary_closing(np.asarray(Image.open(os.path.join(D, 'seg', n + '.png')).convert('L')) > 128, iterations=3))
           for n in ('hair', 'face', 'skirt', 'feet', 'hand_L', 'hand_R')}             # (SAM's masks, closed and filled: no pinholes)
    yy, xx = np.mgrid[:H, :W]
    J = {  # rivets (full-res px): the pins the pieces turn on
        'shoulder_L': [705, 782], 'elbow_L': [590, 1085], 'wrist_L': [468, 1342],
        'shoulder_R': [1333, 782], 'elbow_R': [1440, 1085], 'wrist_R': [1560, 1343],
        'neck': [1024, 560], 'waist': [1024, 1250], 'hip_L': [930, 1330], 'hip_R': [1118, 1330], 'feet': [1024, 2860]}
    # the drawings, registered onto the base (fitted away from what each changed)
    def reg(name, exclude):
        img = key(os.path.join(D, 'src/poses', name + '.png'))
        fit = A & ~ndi.binary_dilation(exclude, iterations=40)
        al, res = register(img, base, fit); al = colour_match(al, base, fit & (al[..., 3] > 200)); print(f'{name:9s} residual {res:.1f}'); return al
    armzone = ((xx < 960) | (xx > 1090)) & (yy > 620) & (yy < 1820)
    headzone = yy < 760
    noarms = reg('noarms', armzone | seg['hand_L'] | seg['hand_R'])
    nohead = reg('nohead', headzone | seg['hair'])
    hoodup = reg('hoodup', yy < 900)
    hoodpush = reg('hoodpush', (yy < 900) | ((xx < 1000) & (yy < 1800)))
    # the sleeves: what the body lacks (the base's figure outside the sleeveless jacket), grown over the body a little where
    # the drawings differ (the sleeve's inner hem lies on the jacket), holes filled; the hands (SAM) apart
    pa = lambda a: a[..., :3].astype(np.float32) * (a[..., 3:] / 255)
    diff = np.abs(pa(base) - pa(noarms)).max(-1)
    arm0 = A & (noarms[..., 3] < 100) & armzone
    grow = ndi.binary_dilation(arm0, iterations=40) & A & (diff > 28) & armzone
    arm = ndi.binary_closing(arm0 | grow, iterations=6)
    arm = ndi.binary_fill_holes(arm) & A
    hands = {s: ndi.binary_dilation(seg['hand_' + s], iterations=2) & A for s in 'LR'}
    parts, fans = {}, {}
    for s, side in (('L', xx < 1024), ('R', xx >= 1024)):
        m = arm & side & ~hands[s]
        lab, n = ndi.label(m); m = lab == (1 + int(np.argmax(ndi.sum(m, lab, range(1, n + 1)))))
        S, E, Wr = np.array(J['shoulder_' + s], float), np.array(J['elbow_' + s], float), np.array(J['wrist_' + s], float)
        ax = (Wr - S) / np.linalg.norm(Wr - S)
        along = (xx - E[0]) * ax[0] + (yy - E[1]) * ax[1]
        clean = lambda q: (lambda lab, n: lab == (1 + int(np.argmax(ndi.sum(q, lab, range(1, n + 1))))) if n else q)(*ndi.label(ndi.binary_opening(q, iterations=4)))
        upper, fore = clean(m & (along < 0)), clean(m & (along >= 0))           # (no strands of the jacket's edge riding along)
        # the fan: the upper sleeve's cloth continued past its elbow cut (mirrored across it), clipped to where the forearm lies at
        # rest (so it's hidden there), drawn under the forearm: a bent elbow shows sleeve, never a hole
        refl_x = xx - 2 * along * ax[0]; refl_y = yy - 2 * along * ax[1]
        src_ok = (refl_x >= 0) & (refl_x < W) & (refl_y >= 0) & (refl_y < H)
        fan = fore & src_ok & (along < 320)
        fan &= upper[np.clip(refl_y, 0, H - 1).astype(int), np.clip(refl_x, 0, W - 1).astype(int)]
        fimg = np.zeros_like(base)
        fimg[fan] = base[np.clip(refl_y, 0, H - 1).astype(int)[fan], np.clip(refl_x, 0, W - 1).astype(int)[fan]]
        parts['upper_' + s] = over(fimg, with_alpha(base, feather(upper, 1.2)))
        parts['fore_' + s] = with_alpha(base, feather(fore, 1.2))
        parts['hand_' + s] = with_alpha(base, feather(hands[s], 1.2))
        # the cut edges get a line of ink where they meet the jacket (a sleeve lifted off the body keeps an outline)
        for k in ('upper_' + s, 'fore_' + s):
            pm = parts[k][..., 3] > 128; edge = pm & ~ndi.binary_erosion(pm, iterations=3) & ndi.binary_erosion(A, iterations=6) & (noarms[..., 3] > 128)
            parts[k][edge, :3] = (parts[k][edge, :3] * .25).astype(np.uint8)
        print(f'arm {s}: upper {upper.sum() / 1e3:.0f}k, fore {fore.sum() / 1e3:.0f}k, fan {fan.sum() / 1e3:.0f}k, hand {hands[s].sum() / 1e3:.0f}k')
    # the head (hair and face, SAM) over the headless collar; the long hair on the chest goes with it
    neck = poly((H, W), [[950, 480], [1098, 480], [1098, 610], [950, 610]]) & A & (base[..., 0].astype(int) > 180) & (base[..., 0].astype(int) > base[..., 2].astype(int) + 8)
    head = ndi.binary_fill_holes(ndi.binary_closing(ndi.binary_dilation(seg['hair'] | seg['face'] | neck, iterations=2), iterations=4)) & A & (yy < 900)
    parts['head'] = with_alpha(base, feather(head, 1.2))
    # the body: the sleeveless jacket, the headless collar where the head was; without the hakama (its own pieces)
    body = noarms.copy()
    hz = ndi.binary_dilation(head, iterations=30) & (yy < 900)
    body = over(with_alpha(body, ~hz), with_alpha(nohead, hz))
    skirt = ndi.binary_dilation(seg['skirt'], iterations=1) & A
    feet = (ndi.binary_dilation(seg['feet'], iterations=2) | (yy > 2540)) & A & ~skirt
    body = with_alpha(body, (~(skirt | feet) | (yy < 1100)) & (yy < 1860))   # (the kimono above the obi stays; nothing below the jacket)
    parts['body'] = body
    # the hakama: the pelvis piece (open front and obi, above the hip line) and the two legs, over a shadowed under-skirt
    hipy = J['hip_L'][1]
    sk = (skirt | (A & (yy > 1860) & (yy < 2540) & ~feet)) & (yy >= 1100)      # (below the jacket everything is hakama: its rim light too)
    parts['skirt_top'] = with_alpha(base, feather(sk & (yy < hipy), 1.2))
    parts['leg_L'] = with_alpha(base, feather(sk & (yy >= hipy) & (xx < 1024 + 6), 1.2))
    parts['leg_R'] = with_alpha(base, feather(sk & (yy >= hipy) & (xx >= 1024 - 6), 1.2))
    under = with_alpha(base, sk & (yy >= hipy - 20)); under[..., :3] = (under[..., :3] * .45).astype(np.uint8)
    parts['skirt_under'] = under
    for s, side in (('L', xx < 1024), ('R', xx >= 1024)): parts['foot_' + s] = with_alpha(base, feather(feet & side, 1.2))
    # the hood up (walking in) and the hood being pushed back: what those drawings changed, over the body
    for nm, img, extra in (('hoodup', hoodup, None), ('hoodpush', hoodpush, (xx < 1000) & (yy < 1850))):
        d = np.abs(pa(img) - pa(base)).max(-1) > 30
        zone = (yy < 950) | (extra if extra is not None else False)
        ch = ndi.binary_fill_holes(ndi.binary_closing(ndi.binary_opening(d & zone, iterations=2), iterations=8))
        ch = (ch | (head & zone)) & (img[..., 3] > 16)
        if extra is not None: ch |= extra & (img[..., 3] > 16) & ~skirt       # (the raised arm: the whole left arm from that drawing)
        parts[nm] = with_alpha(img, feather(ch, 2))
    # the faces: eyes, brows and mouth from each face drawing, registered on the head crop and patched into the head
    x0, y0, n = 640, 16, 768
    crop = base[y0:y0 + n, x0:x0 + n]
    patch = poly((H, W), cv2.ellipse2Poly((1024, 335), (158, 80), 0, 0, 360, 8)) | poly((H, W), cv2.ellipse2Poly((1024, 455), (62, 32), 0, 0, 360, 8))
    pc = patch[y0:y0 + n, x0:x0 + n]
    faces = {}
    for f in ('smile', 'closed', 'why'):
        e = np.asarray(Image.open(os.path.join(D, 'src/poses', f'face_{f}.png')).convert('RGBA').resize((n, n), Image.LANCZOS)).copy()
        e = key_rgb(e)
        al, res = register(e, crop, (crop[..., 3] > 200) & ~ndi.binary_dilation(pc, iterations=20))
        al = colour_match(al, crop, (crop[..., 3] > 200) & ~ndi.binary_dilation(pc, iterations=20) & (al[..., 3] > 200))
        full = parts['head'].copy(); m = feather(pc, 10)
        sub = full[y0:y0 + n, x0:x0 + n].astype(np.float32); sub[..., :3] = sub[..., :3] * (1 - m[..., None]) + al[..., :3] * m[..., None]
        full[y0:y0 + n, x0:x0 + n] = sub.astype(np.uint8); parts['head_' + f] = full; faces[f] = round(res, 1)
        print(f'face {f:7s} residual {res:.1f}')
    # write, scaled
    meta = {'scale': SC, 'size': [round(W * SC), round(H * SC)], 'joints': {k: [round(a * SC, 1), round(b * SC, 1)] for k, (a, b) in J.items()}, 'parts': {}}
    for k, img in parts.items():
        Image.fromarray(bleed(img)).resize((round(W * SC), round(H * SC)), Image.LANCZOS).save(os.path.join(out_dir, k + '.png')); meta['parts'][k] = k + '.png'
    json.dump(meta, open(os.path.join(out_dir, 'meta.json'), 'w'), indent=1)
    print('stage: wrote', len(parts), 'pieces')


def key_rgb(e):
    """key a green-screen RGBA (a face edit may come back opaque)"""
    if e[..., 3].min() > 250:
        r, g, b = [e[..., i].astype(np.float32) / 255 for i in range(3)]
        k = g - np.maximum(r, b); a = 1 - np.clip((k - .12) / (.38 - .12), 0, 1)
        e[..., 1] = (np.minimum(g, np.maximum(r, b) + .02) * 255).astype(np.uint8); e[..., 3] = (a * 255).astype(np.uint8)
    return e


# ---------------------------------------------------------------------------------------------------------------------- room
def room():
    SC = .5; out_dir = os.path.join(D, 'room'); os.makedirs(out_dir, exist_ok=True)
    base = key(os.path.join(D, 'src/room/base_room.png')); H, W = base.shape[:2]; yy, xx = np.mgrid[:H, :W]
    props_zone = (xx < 980) & (yy > 1780)                       # the cushion, and the lantern once it's set down (no book: Fable)
    cushion_zone = (xx < 960) & (yy > 2150)
    cushion_fit = (xx > 80) & (xx < 430) & (yy > 2150)             # (the cushion's free end: no lantern, no figure over it)
    out = {}
    def load_reg(name, fit):                                     # (the cushion is too plain for ECC: search the shift of its outline)
        img = key(os.path.join(D, 'src/room', name + '.png'))
        a0 = (base[..., 3] > 128)[2000:2560, 60:460].astype(np.float32); best = (1e18, 0, 0)
        for dy in range(-40, 161, 4):
            for dx in range(-40, 41, 4):
                M = np.float32([[1, 0, dx], [0, 1, dy]]); a1 = cv2.warpAffine((img[..., 3] > 128).astype(np.float32), M, (W, H))[2000:2560, 60:460]
                e = float(np.abs(a1 - a0).sum()); best = min(best, (e, dx, dy))
        _, dx, dy = best; print(f'{name:8s} shift {dx},{dy}')
        return cv2.warpAffine(img, np.float32([[1, 0, dx], [0, 1, dy]]), (W, H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    empty = load_reg('empty', cushion_fit)
    setdown = load_reg('setdown', cushion_fit)
    A = base[..., 3] > 128
    # the figure and its props, per drawing
    fig_hold = with_alpha(base, ~cushion_zone | (xx > 940))
    props_hold = with_alpha(base, cushion_zone & (xx <= 940))
    figmask = (base[..., 3] > 40) & ~(cushion_zone & (xx <= 940))            # (her figure standing: the same in 'empty' below the arm)
    props = props_zone & (xx <= 1000) & ~ndi.binary_dilation(figmask & props_zone, iterations=5) & (empty[..., 3] > 16)
    lab, n = ndi.label(props); props = np.isin(lab, 1 + np.flatnonzero(ndi.sum(props, lab, range(1, n + 1)) > 3000))   # (no specks)
    fig_empty = with_alpha(empty, ~props)
    props_empty = with_alpha(empty, props)
    out.update(hold=fig_hold, props_hold=props_hold, empty=fig_empty, props_empty=props_empty, setdown=setdown)
    # the walk: set on the floor (its feet on the standing figure's floor line) and centred on the standing figure's body
    ys, xs = np.nonzero(fig_empty[..., 3] > 128); floor = ys.max(); cx0 = np.median(xs[ys < 1500])
    for w in ('walk1', 'walk2'):
        img = key(os.path.join(D, 'src/room', w + '.png')); ys2, xs2 = np.nonzero(img[..., 3] > 128)
        dx, dy = cx0 - np.median(xs2[ys2 < 1500]), floor - ys2.max()
        out[w] = cv2.warpAffine(img, np.float32([[1, 0, dx], [0, 1, dy]]), (W, H), borderValue=(0, 0, 0, 0)); print(f'{w:8s} shift {dx:.0f},{dy:.0f}')
    # key points (full res): the feet on the floor, the crown, the nose, the fist, the lantern (in hand, and set down)
    ys, xs = np.nonzero(fig_hold[..., 3] > 128)
    feet_y = int(ys.max()); feet_x = int(np.median(xs[ys > feet_y - 60]))
    lz = (xx < 760) & (yy > 1000) & (yy < 1700) & (base[..., 0].astype(int) > 200) & (base[..., 1].astype(int) > 150) & (base[..., 3] > 200)
    ly, lx = ndi.center_of_mass(lz)
    lz2 = props_zone & (xx > 450) & (empty[..., 0].astype(int) > 200) & (empty[..., 1].astype(int) > 150) & (empty[..., 3] > 200)
    ly2, lx2 = ndi.center_of_mass(lz2)
    pts = {'feet': [feet_x, feet_y], 'crown': [int(xs[ys.argmin()]), int(ys.min())], 'lantern_hand': [round(lx), round(ly)], 'lantern_down': [round(lx2), round(ly2)]}
    meta = {'scale': SC, 'size': [round(W * SC), round(H * SC)], 'points': {k: [round(a * SC, 1), round(b * SC, 1)] for k, (a, b) in pts.items()}, 'drawings': {}}
    for k, img in out.items():
        Image.fromarray(bleed(img)).resize((round(W * SC), round(H * SC)), Image.LANCZOS).save(os.path.join(out_dir, k + '.png')); meta['drawings'][k] = k + '.png'
    json.dump(meta, open(os.path.join(out_dir, 'meta.json'), 'w'), indent=1)
    print('room: points (full res)', pts)


if __name__ == '__main__':
    which = sys.argv[1:] or ['stage', 'room']
    if 'stage' in which: stage()
    if 'room' in which: room()
