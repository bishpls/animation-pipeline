"""Fable three-quarter (the room ending's mesh rig, RIGGING.md): build steps after the drawings (gen.py).
    .venv/bin/python projects/tsuzuku/rig/fable_3q/build.py reg [name ...]     key + pad + register companions -> under/<name>_al.png
The rig's canvas is the base keyed and padded PAD px at the top (room above her head for the raised lantern): base_keyed.png.
Every companion is registered onto it (affine ECC on luminance, coarse to fine) on a region its edit shouldn't have changed; the
residual is printed (a high one means the edit moved something it shouldn't).
"""
import json, os, sys
import numpy as np, cv2
from PIL import Image
from scipy import ndimage as ndi

D = os.path.dirname(os.path.abspath(__file__)); P = lambda *a: os.path.join(D, *a)
sys.path.insert(0, P('..', 'fable_seated'))
from key import key  # noqa: E402

PAD = 600
lum = lambda a: ((a[..., :3].astype(np.float32) @ [.299, .587, .114]) * (a[..., 3] / 255) + 255 * (1 - a[..., 3] / 255)).astype(np.float32)
rgba = lambda p: np.array(Image.open(p).convert('RGBA'))


def padded(path):
    k = key(path); out = np.zeros((k.shape[0] + PAD, k.shape[1], 4), np.uint8); out[PAD:] = k; return out


def boxes(shape, bs):
    m = np.zeros(shape, bool)
    for x0, y0, x1, y1 in bs: m[y0:y1, x0:x1] = True
    return m


def register(img, base, mask, motion=cv2.MOTION_AFFINE):
    """img warped onto base, fitted on mask (coarse to fine); returns (aligned, residual on the mask)"""
    H, W = base.shape[:2]; warp = np.eye(2, 3, dtype=np.float32)
    for sc in (.125, .25, .5):
        a = cv2.GaussianBlur(cv2.resize(lum(base), None, fx=sc, fy=sc), (0, 0), 1.2)
        b = cv2.GaussianBlur(cv2.resize(lum(img), None, fx=sc, fy=sc), (0, 0), 1.2)
        w = warp.copy(); w[:, 2] *= sc
        _, w = cv2.findTransformECC(a, b, w, motion, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 300, 1e-6),
                                    cv2.resize(mask.astype(np.uint8), None, fx=sc, fy=sc, interpolation=cv2.INTER_NEAREST), 5)
        warp = w.copy(); warp[:, 2] /= sc
    al = cv2.warpAffine(img, warp, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderValue=(0, 0, 0, 0))
    res = float(np.abs(lum(al) - lum(base))[mask & (base[..., 3] > 200)].mean())
    return al, res, warp


# the regions each companion's edit should have left alone (padded canvas px)
LOWER = (980, 3150, 1920, 4370)            # the hakama's lower part and the geta
SLEEVE_L = (760, 1500, 1160, 2560)         # the near sleeve (not its cuff)
LANTERN = (100, 2080, 520, 2780)
HEAD = (1000, 700, 1600, 1260)
ROI = {'noarms': [LOWER, HEAD], 'nohair': [LOWER, SLEEVE_L, LANTERN], 'noribbon': [LOWER, SLEEVE_L, HEAD, LANTERN],
       'hoodup': [LOWER, SLEEVE_L, LANTERN], 'push1': [LOWER, LANTERN], 'push2': [LOWER, LANTERN], 'turn': [LOWER, SLEEVE_L, LANTERN], 'turn_half': [LOWER, SLEEVE_L, LANTERN]}


def reg(names):
    base = rgba(P('base_keyed.png')); os.makedirs(P('under'), exist_ok=True); log = {}
    for n in names:
        img = padded(P('src', n + '.png')); m = boxes(base.shape[:2], ROI[n])
        al, res, w = register(img, base, m)
        Image.fromarray(al).save(P('under', n + '_al.png')); log[n] = {'residual': round(res, 2), 'warp': np.round(w, 4).tolist()}
        print(f'{n:10s} residual {res:5.2f}  warp {np.round(w, 4).tolist()}')
    J = P('under', 'reg.json'); old = json.load(open(J)) if os.path.exists(J) else {}; old.update(log); json.dump(old, open(J, 'w'), indent=1)


isskin = lambda I: (I[..., 0].astype(int) > 170) & (I[..., 0].astype(int) - I[..., 2].astype(int) > 8) & ((I[..., :3].astype(float) @ [.299, .587, .114]) > 150)


def labels():
    """label maps for the companions (what tools/rigbuild.py 'fromimg' takes from each): simple, by colour and region, since
    fromimg only fills where the target layer is empty and the build then drops anything visible at rest"""
    def save(name, order, maps):
        d = P('under', 'lab_' + name); os.makedirs(d, exist_ok=True); L = np.zeros(maps[0].shape, np.uint8)
        for i, m in enumerate(maps): L[m & (L == 0)] = i + 1
        Image.fromarray(L).save(os.path.join(d, 'labels.png')); json.dump({'order': order, 'size': [L.shape[1], L.shape[0]]}, open(os.path.join(d, 'labels.json'), 'w'))
        print(name, {o: int((L == i + 1).sum()) for i, o in enumerate(order)})
    rgb = lambda I: I[..., :3].astype(int)
    hairish = lambda I: (I[..., 3] > 128) & (rgb(I)[..., 2] > rgb(I)[..., 0] + 25) & (rgb(I)[..., 2] > rgb(I)[..., 1] + 10)   # blue-black hair
    teal = lambda I: (I[..., 3] > 128) & (rgb(I)[..., 1] > rgb(I)[..., 0] + 40)                                                   # the ribbon
    # (the no-arms drawing keeps a bare arm hanging where the sleeve was: its highlights and rim light aren't 'skin' by colour, so
    #  the jacket is only its dark cloth, away from any skin)
    N = rgba(P('under', 'noarms_al.png')); dark = (N[..., :3].astype(float) @ [.299, .587, .114]) < 105
    # the bare arm lies ON the vest (its front panel shows past it): paint the vest over it from the cloth around it, above the
    # hem (invented pixels: under/noarms_fixed.png is what the build takes; the arm's region is under/noarms_arm.png)
    import cv2
    arm = ndi.binary_dilation(isskin(N) | ((N[..., 3] > 128) & ~dark & (np.arange(N.shape[1])[None, :] < 1250)), iterations=8) & (N[..., 3] > 128)
    arm[2930:] = False; arm[:1500] = False
    # (from the dark cloth only: the rim light's pink and the key's green edge would smear across it)
    rimlit = (N[..., 3] > 128) & ~dark; unknown = arm | ndi.binary_dilation(rimlit, iterations=3)
    F = N.copy(); F[..., :3] = cv2.inpaint(np.ascontiguousarray(N[..., :3]), unknown.astype(np.uint8), 21, cv2.INPAINT_TELEA)
    F[~arm] = N[~arm]
    # (under the near sleeve the companion's vest side carries its own rim light and a trace of the key's green: when the sleeve
    #  lifts it should read as plain black cloth in shadow, so it's desaturated there, 75%)
    under = ndi.binary_dilation(rgba(P('mesh', 'layers', 'sleeve_L.png'))[..., 3] > 8, iterations=6)
    lum = (F[..., :3].astype(float) @ [.299, .587, .114])[..., None]; F[..., :3] = np.where(under[..., None], F[..., :3] * .25 + lum * .75, F[..., :3]).astype(np.uint8)
    Image.fromarray(F).save(P('under', 'noarms_fixed.png')); Image.fromarray((arm * 255).astype(np.uint8)).save(P('under', 'noarms_arm.png'))
    save('noarms', ['jacket'], [(N[..., 3] > 128) & (dark | arm)])
    H = rgba(P('under', 'nohair_al.png')); cloth = (H[..., 3] > 128) & ~isskin(H) & ~teal(H)
    zone = np.zeros(cloth.shape, bool); zone[1240:, :] = True
    save('nohair', ['jacket', 'skin'], [cloth & zone, isskin(H)])
    R = rgba(P('under', 'noribbon_al.png')); save('noribbon', ['hair'], [hairish(R) & ~teal(R)])


BASE_UPPER = ['sleeve_L', 'hand_L', 'hair_front', 'eye', 'face', 'ear', 'ribbon_knot', 'ribbon', 'hair_head', 'hair', 'hood', 'neck',
              'sleeve_R_back', 'jacket', 'hand_R', 'sleeve_R', 'stick']
HEADS = ['hair_front', 'eye', 'face', 'ear', 'ribbon_knot', 'hair_head']
teal = lambda I: (I[..., 3] > 128) & (I[..., 1].astype(int) > I[..., 0].astype(int) + 40) & (I[..., 2].astype(int) > 90)


def export(name, layers, feather_into):
    """write views/<name>/<layer>.png (cropped, colour bled under the edge) + manifest.json (back to front). feather_into: a mask of
    the base figure the view's layers sit on: where a layer's edge meets it (not the silhouette) the edge fades over 12 px"""
    d = P('views', name); os.makedirs(d, exist_ok=True); man = {'size': None, 'layers': []}
    for n, lay in layers:
        lay = lay.copy(); a = lay[..., 3] > 8; man['size'] = [lay.shape[1], lay.shape[0]]
        if feather_into is not None:
            inner = ~a & feather_into; ring = ndi.distance_transform_edt(~inner) <= 1.5
            seam = a & ndi.binary_dilation(inner, iterations=2)
            if seam.any():
                dd = ndi.distance_transform_edt(~(inner & ~a)); fz = a & (dd < 12)
                lay[fz, 3] = (lay[fz, 3] * np.clip(dd[fz] / 12, 0, 1)).astype(np.uint8)
        a = lay[..., 3] > 0
        _, (iy, ix) = ndi.distance_transform_edt(~a, return_indices=True); rim = ~a & (ndi.distance_transform_edt(~a) <= 3)
        lay[rim, :3] = lay[iy[rim], ix[rim], :3]
        ys, xs = np.nonzero(a); x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        Image.fromarray(lay[y0:y1, x0:x1]).save(os.path.join(d, n + '.png'))
        Image.fromarray(np.zeros((y1 - y0, x1 - x0), np.uint8)).save(os.path.join(d, n + '.inv.png'))
        man['layers'].append({'name': n, 'x': int(x0), 'y': int(y0), 'w': int(x1 - x0), 'h': int(y1 - y0)})
        print(f'  {name}/{n}: {int(a.sum())} px  box {x0},{y0} {x1 - x0}x{y1 - y0}')
    json.dump(man, open(os.path.join(d, 'manifest.json'), 'w'), indent=1)


def views(names):
    """the drawn states (rig.json views): the hood up (layered: it plays ten seconds with the body moving), the push's two drawings
    and the head's turn and half-turn (flattened: each is on screen a drawing or two)"""
    Lb = lambda n: rgba(P('mesh', 'layers', n + '.png'))[..., 3] > 8
    base = rgba(P('base_keyed.png')); fig = base[..., 3] > 8; H, W = fig.shape; yy = np.mgrid[:H, :W][0]
    upper = np.zeros(fig.shape, bool)
    for n in BASE_UPPER: upper |= Lb(n)
    lantern = ndi.binary_dilation(Lb('lantern'), iterations=6)
    for name in names:
        V = rgba(P('under', name + '_al.png')); va = V[..., 3] > 8; cut = lambda m: np.where(m[..., None], V, 0).astype(np.uint8)
        if name in ('push1', 'push2'):                   # everything above the hakama but the lantern (the base's lantern hangs on) and
            arm = np.array(Image.open(P('under', 'seg_' + {'push1': 'pushA', 'push2': 'pushB'}[name], 'arm.png'))) > 127   # the raised arm
            zone = va & (ndi.binary_dilation(upper, iterations=30) | (yy < 2600)) & ~lantern & ~ndi.binary_erosion(arm, iterations=3)   # (under the arm's edge: no crack)
            export(name, [('upper', cut(zone))], fig & ~upper)
        elif name in ('turn', 'turn_half'):              # the head, the hair and ribbon, the hood and neck; the base's arms and jacket stay
            head = np.zeros(fig.shape, bool)
            for n in HEADS + ['neck', 'hood', 'hair', 'ribbon']: head |= Lb(n)
            arms = ndi.binary_dilation(Lb('sleeve_L') | Lb('hand_L') | Lb('sleeve_R') | Lb('hand_R') | Lb('stick'), iterations=3)
            zone = va & (ndi.binary_dilation(head, iterations=40) | (yy < 1250)) & ~arms & ~lantern
            export(name, [('upper', cut(zone))], Lb('jacket') | Lb('sleeve_R_back'))
        elif name == 'hoodup':
            head = np.zeros(fig.shape, bool)
            for n in HEADS + ['neck', 'hood']: head |= Lb(n)
            skinV = (V[..., 0].astype(int) > 150) & (V[..., 0].astype(int) - V[..., 2].astype(int) > 6) & va & ((V[..., :3].astype(float) @ [.299, .587, .114]) > 130)
            ribbox = np.zeros(fig.shape, bool); ribbox[1250:2950, 1330:1820] = True     # (the ribbon and the hakama share #165E83: by place)
            rib = teal(V) & ribbox & (V[..., 2] < 200) & (V[..., 1] < 170)                  # (not the cyan rim light)
            lab, n = ndi.label(rib); sz = ndi.sum(rib, lab, range(1, n + 1)); rib = np.isin(lab, 1 + np.nonzero(sz > sz.max() * .08)[0])
            rib = ndi.binary_fill_holes(ndi.binary_closing(rib, iterations=3)); rib = ndi.binary_dilation(rib, iterations=3) & va & ~skinV & ribbox
            # the hood's opening: where the drawing shows her skin or her bangs by her face, the base's own face, eye and bangs show
            # (kept by the view: so the face's drawn states and blinks play under the hood too)
            hairblue = va & (V[..., 2].astype(int) > V[..., 0].astype(int) + 25) & (V[..., 2].astype(int) > V[..., 1].astype(int) + 10)
            opening = (skinV | hairblue) & ndi.binary_dilation(Lb('face') | Lb('eye') | Lb('hair_front'), iterations=10) & (yy > 880)
            opening = ndi.binary_closing(opening, iterations=2) & ~ndi.binary_dilation(~va, iterations=1)
            hood = va & (ndi.binary_dilation(head, iterations=60) | (yy < 1300)) & (yy < 1420) & ~rib & ~opening & ~lantern
            hood &= ~ndi.binary_dilation(Lb('sleeve_L') | Lb('hand_L'), iterations=2) | (yy < 1330)
            hairzone = np.zeros(fig.shape, bool)
            for n in ('hair', 'hair_head', 'ribbon', 'ribbon_knot', 'hood', 'neck'): hairzone |= Lb(n)
            back = va & ndi.binary_dilation(hairzone, iterations=30) & (yy >= 1380) & ~hood & ~lantern & ~ndi.binary_dilation(Lb('sleeve_L'), iterations=2)
            # the jacket's back continues under the ribbon (it swings): inpainted there from the back around it (invented)
            import cv2
            B2 = cut(back & ~rib); hole = (back & rib).astype(np.uint8)
            fill = cv2.inpaint(np.ascontiguousarray(B2[..., :3]), hole, 9, cv2.INPAINT_TELEA); B2[back & rib, :3] = fill[back & rib]; B2[back & rib, 3] = 255
            ys, xs = np.nonzero(rib); top = ys.min(); tx = xs[ys < top + 30].mean()
            print(f'  hoodup: the ribbon tails come out from under the hood at ({tx:.0f}, {top})')
            export(name, [('back_up', B2), ('ribbon_up', cut(rib)), ('hood_up', cut(hood))], Lb('jacket') | Lb('sleeve_R_back'))


PUSH_ARMS = {   # the near arm in the push's two drawings, cut as key drawings (engine/rig.js armPoses, by name; placed by p.poseL)
 'pushA': ('push1', {'forearm': {'pos': [[871, 1049], [1000, 790], [770, 1190]]},
                     'sleeve': {'pos': [[850, 1500], [820, 1800], [900, 1300]], 'box': [690, 1150, 1040, 1990]}},
           [[1250, 1500], [1180, 1000], [1300, 800], [1150, 1350]]),
 'pushB': ('push2', {'forearm': {'pos': [[1167, 1141], [1400, 1010], [880, 1180]]},
                     'sleeve': {'pos': [[900, 1500], [880, 1800], [950, 1300]], 'box': [760, 1150, 1080, 1990]}},
           [[1300, 1600], [1150, 950], [1250, 1320], [1050, 800]]),
}


def pusharms():
    import subprocess
    SAM = os.path.join(P('..', '..', '..', '..'), 'vendor', 'seed-vc', '.venv', 'bin', 'python'); SEG = os.path.join(P('..', '..', '..', '..'), 'tools', 'segment.py')
    T = json.load(open(P('mesh', 'build', 'armposes.json')))
    for nm, (src, parts, neg) in PUSH_ARMS.items():
        d = P('under', f'seg_{nm}'); os.makedirs(d, exist_ok=True)
        pj = os.path.join(d, 'parts.json'); json.dump({k: {**v, 'neg': neg} for k, v in parts.items()}, open(pj, 'w'))
        subprocess.run([SAM, SEG, P('under', src + '_al.png'), pj, d], check=True, capture_output=True)
        m = np.zeros(rgba(P('base_keyed.png')).shape[:2], bool)
        for k in parts: m |= np.array(Image.open(os.path.join(d, k + '.png'))) > 127
        Lb = lambda q: rgba(P('mesh', 'layers', q + '.png'))[..., 3] > 8
        m &= ~ndi.binary_dilation(Lb('hand_R') | Lb('stick') | Lb('sleeve_R') | Lb('lantern'), iterations=4)      # (not the lantern hand)
        if nm == 'pushB': m[1156:1262, 1150:1245] = False                                                        # (nor the ear, under the forearm)
        m = ndi.binary_closing(ndi.binary_opening(m, iterations=5), iterations=14)                              # (a clean edge through black cloth)
        m = ndi.binary_fill_holes(m); lab, n = ndi.label(m); m = lab == 1 + int(np.argmax(ndi.sum(m, lab, range(1, n + 1))))
        Image.fromarray((m * 255).astype(np.uint8)).save(os.path.join(d, 'arm.png'))
        V = rgba(P('under', src + '_al.png')); lay = V.copy(); lay[..., 3] = (V[..., 3] * np.clip(ndi.distance_transform_edt(m) / 1.5, 0, 1)).astype(np.uint8)
        ys, xs = np.nonzero(lay[..., 3] > 0); x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        fn = f'armpose_L_{nm}.png'; Image.fromarray(lay[y0:y1, x0:x1]).save(P('mesh', 'build', fn))
        sk = (V[..., 0].astype(int) > 200) & (V[..., 1].astype(int) > 150) & (V[..., 0].astype(int) - V[..., 2].astype(int) > 10) & m
        hy, hx = np.nonzero(sk); far = np.argsort(-(hx - 1062.) ** 2 - (hy - 1480.) ** 2)[:max(1, len(hx) // 12)]   # (the hand: the skin farthest from the shoulder)
        ent = {'name': nm, 'hand': nm, 'arm': 0, 'elbow': 0, 'tol': [999, 999], 'follow': True, 'anchor': 'sleeve_L', 'file': fn,
               'x': int(x0), 'y': int(y0), 'w': int(x1 - x0), 'h': int(y1 - y0), 'replaces': ['sleeve_L', 'hand_L'],
               'hand0': [round(float(hx[far].mean()), 1), round(float(hy[far].mean()), 1)]}
        T['L'] = [q for q in T.get('L', []) if q['name'] != nm] + [ent]
        print(f'  {nm}: {int(m.sum())} px  box {x0},{y0} {x1 - x0}x{y1 - y0}  hand {ent["hand0"]}')
    json.dump(T, open(P('mesh', 'build', 'armposes.json'), 'w'), indent=1)


def extend_down():
    """the 'down' arm (the hand at her shoulder, after the push) was drawn in a crop that ends at y 2136, through its hanging
    sleeve: continue it with the base sleeve's own lower part, feathered over 14 px at the seam"""
    T = json.load(open(P('mesh', 'build', 'armposes.json'))); e = [q for q in T['L'] if q['name'] == 'down'][0]
    A = np.zeros((4440, 2160, 4), np.uint8); A[e['y']:e['y'] + e['h'], e['x']:e['x'] + e['w']] = rgba(P('mesh', 'build', e['file']))
    S = rgba(P('mesh', 'layers', 'sleeve_L.png')); S[:2110] = 0
    w = np.clip((np.arange(4440) - 2110) / 14., 0, 1)[:, None]; S[..., 3] = (S[..., 3] * w).astype(np.uint8)
    a1 = A[..., 3:4] / 255.; a2 = S[..., 3:4] / 255.; al = a1 + a2 * (1 - a1)
    rgb = (A[..., :3] * a1 + S[..., :3] * a2 * (1 - a1)) / np.maximum(al, 1e-6); out = np.dstack([rgb, al * 255]).clip(0, 255).astype(np.uint8)
    ys, xs = np.nonzero(out[..., 3] > 0); x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    Image.fromarray(out[y0:y1, x0:x1]).save(P('mesh', 'build', e['file'])); e.update(x=int(x0), y=int(y0), w=int(x1 - x0), h=int(y1 - y0))
    json.dump(T, open(P('mesh', 'build', 'armposes.json'), 'w'), indent=1); print('down extended', e['x'], e['y'], e['w'], e['h'])


def fix_sweep():
    """tools/armpose.py keeps the largest piece of a cut; the sweep's hand and forearm are separate from its sleeve (a gap at the
    cuff): recut it from its three SAM parts, every piece kept"""
    ED = P('mesh', 'build', '_armpose_edits'); d = os.path.join(ED, '_seg_L_sweep'); m = None
    for k in ('hand', 'forearm', 'sleeve'): q = np.array(Image.open(os.path.join(d, k + '.png'))) > 127; m = q if m is None else m | q
    m = ndi.binary_fill_holes(ndi.binary_closing(m, iterations=4)); lab, n = ndi.label(m); sz = ndi.sum(m, lab, range(1, n + 1)); m = np.isin(lab, 1 + np.nonzero(sz > 2000)[0])
    V = rgba(os.path.join(ED, '_aligned_L_sweep.png')); lay = V.copy(); lay[..., 3] = (V[..., 3] * np.clip(ndi.distance_transform_edt(m) / 1.5, 0, 1)).astype(np.uint8)
    ys, xs = np.nonzero(lay[..., 3] > 0); x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    Image.fromarray(lay[y0:y1, x0:x1]).save(P('mesh', 'build', 'armpose_L_sweep.png'))
    T = json.load(open(P('mesh', 'build', 'armposes.json'))); e = [q for q in T['L'] if q['name'] == 'sweep'][0]
    e.update(x=int(x0), y=int(y0), w=int(x1 - x0), h=int(y1 - y0)); json.dump(T, open(P('mesh', 'build', 'armposes.json'), 'w'), indent=1)
    print('sweep recut', e['x'], e['y'], e['w'], e['h'])


def hairclone():
    """the hair plate's top continues up under the skull hair (it turns a little against the head, hanging): cloned from its own
    strands just below, column by column (hair strands run down: a vertical copy continues them), where the build left it empty
    or flat-filled; marked invented. After tools/rigbuild.py (edits mesh/build/hair.png, hair.inv.png)"""
    man = json.load(open(P('mesh', 'build', 'manifest.json'))); e = [l for l in man['layers'] if l['name'] == 'hair'][0]
    H = rgba(P('mesh', 'build', 'hair.png')); IV = np.array(Image.open(P('mesh', 'build', 'hair.inv.png'))) > 127
    real = np.array(Image.open(P('mesh', 'layers', 'hair.png')))[..., 3] > 8; real = real[e['y']:e['y'] + e['h'], e['x']:e['x'] + e['w']]
    n = 0
    for x in range(H.shape[1]):
        ys = np.nonzero(real[:, x])[0]
        if not len(ys): continue
        top = ys.min(); k = 130
        for y in range(max(0, top - k), top):
            if H[y, x, 3] < 250 or IV[y, x]:
                src = top + 6 + (top - y) % 110
                if src < H.shape[0] and real[src, x]: H[y, x] = H[src, x]; H[y, x, 3] = 255; IV[y, x] = True; n += 1
    Image.fromarray(H).save(P('mesh', 'build', 'hair.png')); Image.fromarray((IV * 255).astype(np.uint8)).save(P('mesh', 'build', 'hair.inv.png'))
    print('hair plate top: cloned', n, 'px')


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'hairclone': hairclone()
    if a[0] == 'fix_sweep': fix_sweep()
    if a[0] == 'extend_down': extend_down()
    if a[0] == 'pusharms': pusharms()
    if a[0] == 'reg': reg(a[1:] or list(ROI))
    if a[0] == 'labels': labels()
    if a[0] == 'views': views(a[1:] or ['hoodup', 'push1', 'push2', 'turn', 'turn_half'])
