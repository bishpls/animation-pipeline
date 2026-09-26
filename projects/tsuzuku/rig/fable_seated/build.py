"""Fable, seated in the hall (world A): register the pose drawings (src/poses/*.png, GPT Image edits of src/base.png) onto the
base, find what each one changed, and cut the layers the stage draws (src/fableseat.js):
    lantern.png          the lantern alone (from a drawing where her hand has let go), in the base's place
    figure.png           the base figure without the lantern and without the ribbon (the jacket's back under it from 'noribbon')
    ribbon.png           the ribbon alone
    pose_<name>.png      each pose's patch over the figure (the changed region, feathered), cropped; meta.json has the boxes
    .venv/bin/python rig/fable_seated/build.py [--debug]
"""
import json, os, sys
import numpy as np, cv2
from PIL import Image
from scipy import ndimage as ndi
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from key import key

D = os.path.dirname(os.path.abspath(__file__)); DBG = '--debug' in sys.argv
POSES = ['write', 'ear', 'clap', 'clapopen', 'clapmid', 'wipe0', 'wipe1', 'rest', 'pull', 'pincers', 'pincersnip']
BOTH_ARMS = {'pincers', 'pincersnip'}                # poses that raise her left arm too (image-left, past the hood)
base = key(os.path.join(D, 'src/base.png')); H, W = base.shape[:2]
lum = lambda a: ((a[..., :3].astype(np.float32) @ [.299, .587, .114]) * (a[..., 3] / 255) + 255 * (1 - a[..., 3] / 255)).astype(np.float32)


def register(img, mask):
    """affine warp taking img onto base, fitted on mask (coarse to fine)"""
    warp = np.eye(2, 3, dtype=np.float32)
    for sc in (.125, .25, .5):
        a = cv2.GaussianBlur(cv2.resize(lum(base), None, fx=sc, fy=sc), (0, 0), 1.2)
        b = cv2.GaussianBlur(cv2.resize(lum(img), None, fx=sc, fy=sc), (0, 0), 1.2)
        w = warp.copy(); w[:, 2] *= sc
        _, w = cv2.findTransformECC(a, b, w, cv2.MOTION_AFFINE, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 300, 1e-6),
                                    cv2.resize(mask.astype(np.uint8), None, fx=sc, fy=sc, interpolation=cv2.INTER_NEAREST), 5)
        warp = w.copy(); warp[:, 2] /= sc
    al = cv2.warpAffine(img, warp, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    return al, warp


def colour_match(al, k):
    for c in range(3):
        sa, sb = al[k, c].astype(float), base[k, c].astype(float)
        al[..., c] = np.clip((al[..., c] - sa.mean()) / (sa.std() + 1e-6) * sb.std() + sb.mean(), 0, 255).astype(np.uint8)
    return al


if __name__ == "__main__" and "--cut" not in sys.argv:
    Z = json.load(open(os.path.join(D, 'zones.json')))
    yy, xx = np.mgrid[:H, :W]
    def poly(p): m = np.zeros((H, W), np.uint8); cv2.fillPoly(m, [np.array(p, np.int32)], 1); return m.astype(bool)
    arm = poly(Z['arm']); lant = poly(Z['lantern'])
    fitmask = (base[..., 3] > 200) & ~ndi.binary_dilation(arm | lant, iterations=40)
    out = {}
    for p in POSES + ['noribbon']:
        img = key(os.path.join(D, f'src/poses/{p}.png'))
        al, warp = register(img, fitmask)
        res = np.abs(lum(al) - lum(base))[fitmask].mean()
        al = colour_match(al, fitmask & (al[..., 3] > 200))
        np.save(os.path.join(D, f'_al_{p}.npy'), al) if DBG else None
        diff = np.abs(al.astype(np.int16) - base.astype(np.int16)).max(-1)
        out[p] = dict(res=float(res), warp=warp.tolist())
        print(f'{p:9s} residual {res:5.1f}  warp {np.round(warp, 3).tolist()}')
        Image.fromarray(np.clip(diff * 2, 0, 255).astype(np.uint8)).resize((W // 4, H // 4)).save(os.path.join(D, f'_diff_{p}.png'))
        Image.fromarray(al).save(os.path.join(D, f'_al_{p}.png'))


def lantern_offset(img, box):
    """where the lantern body (below its handle) sits in img, relative to base: template match around the base's place"""
    x0, y0, x1, y1 = box; t = lum(base)[y0:y1, x0:x1]; pad = 260
    X0, Y0 = max(0, x0 - pad), max(0, y0 - pad); s = lum(img)[Y0:y1 + pad, X0:x1 + pad]
    r = cv2.matchTemplate(s, t, cv2.TM_CCOEFF_NORMED); _, v, _, (mx, my) = cv2.minMaxLoc(r)
    return X0 + mx - x0, Y0 + my - y0, v


def shift(a, dx, dy):
    return cv2.warpAffine(a, np.float32([[1, 0, dx], [0, 1, dy]]), (a.shape[1], a.shape[0]), flags=cv2.INTER_LINEAR, borderValue=0)


def feather(m, r):
    d = ndi.distance_transform_edt(m); return np.clip(d / r, 0, 1)


def over(dst, src, m):
    """dst*(1-m) + src*m, in premultiplied alpha"""
    pa = lambda a: np.dstack([a[..., :3].astype(np.float32) * (a[..., 3:] / 255), a[..., 3:].astype(np.float32)])
    P = pa(dst) * (1 - m[..., None]) + pa(src) * m[..., None]
    A = P[..., 3:]; rgb = np.where(A > 0, P[..., :3] / np.maximum(A, 1e-6) * 255, 0)
    return np.dstack([np.clip(rgb, 0, 255), np.clip(A, 0, 255)]).astype(np.uint8)


def beneath(top, bottom):
    """top drawn over bottom (premultiplied)"""
    pa = lambda a: np.dstack([a[..., :3].astype(np.float32) * (a[..., 3:] / 255), a[..., 3:].astype(np.float32)])
    T, B = pa(top), pa(bottom); P = T + B * (1 - T[..., 3:] / 255)
    A = P[..., 3:]; rgb = np.where(A > 0, P[..., :3] / np.maximum(A, 1e-6) * 255, 0)
    return np.dstack([np.clip(rgb, 0, 255), np.clip(A, 0, 255)]).astype(np.uint8)


def cut():
    Z = json.load(open(os.path.join(D, 'zones.json'))); SC = Z.get('scale', .6)
    def poly(p): m = np.zeros((H, W), np.uint8); cv2.fillPoly(m, [np.array(p, np.int32)], 1); return m.astype(bool)
    arm, lz = poly(Z['arm']), poly(Z['lantern'])
    fitmask = (base[..., 3] > 200) & ~ndi.binary_dilation(arm | lz, iterations=40)
    AL = {}
    for p in POSES + ['noribbon', 'nolantern', 'warmlantern']:
        al, _ = register(key(os.path.join(D, f'src/poses/{p}.png')), fitmask); AL[p] = colour_match(al, fitmask & (al[..., 3] > 200))
    # the lantern: from 'write' (her hand has let go), moved to the base's place
    body = Z['lantern_body']
    ox, oy, v = lantern_offset(AL['write'], body); print(f'lantern in write: offset {ox},{oy} (ncc {v:.2f})')
    lw = shift(AL['write'], -ox, -oy); lmask = lz & (lw[..., 3] > 8)
    lmask = ndi.binary_fill_holes(ndi.binary_opening(lmask, iterations=2))
    lantern = lw.copy(); lantern[..., 3] = (lw[..., 3] * lmask).astype(np.uint8)
    if Z.get('warm', True):                            # the bridge's warm chouchin (Michael: "it makes Fable stand out from the crowd")
        wl = AL['warmlantern']; wy = np.mgrid[:H, :W][0] >= Z['hand'][2][1]           # below her hand: the warm body; above: the ring
        wb = lz & wy & (wl[..., 3] > 8); wb = ndi.binary_fill_holes(ndi.binary_opening(wb, iterations=2))
        lantern = over(lantern * (~wb[..., None]), wl, feather(wb, 1.5)); lmask = lmask | wb
    # the figure: base minus the lantern (her fingers on the handle stay: they don't match the clean lantern)
    rm = ndi.binary_dilation(lmask, iterations=4) & lz & ~poly(Z['hand'])   # (her fingers round the handle stay in the figure)
    hb = poly(Z['hand']) & lmask; rm |= hb & (np.abs(lum(base) - lum(lantern)) < 20)
    fig = base.copy(); fig[..., 3] = (fig[..., 3] * (1 - feather(rm, 2.5))).astype(np.uint8)
    # the ribbon: what 'noribbon' changed, left of the arm; under it, the jacket from 'noribbon'
    nr = AL['noribbon']; dif = np.abs(lum(nr) - lum(base)) * (base[..., 3] > 128)
    rz = poly(Z['ribbon']); rib = ndi.binary_opening(dif > 30, iterations=2) & rz
    rib = ndi.binary_fill_holes(ndi.binary_closing(rib, iterations=6)) & rz
    lab, n = ndi.label(rib); sizes = ndi.sum(rib, lab, range(1, n + 1)); rib = np.isin(lab, 1 + np.flatnonzero(sizes > 3000))
    ribbon = base.copy(); ribbon[..., 3] = (base[..., 3] * np.clip(feather(ndi.binary_dilation(rib, iterations=3), 2.5), 0, 1)).astype(np.uint8)
    under = ndi.binary_dilation(rib, iterations=22) & rz
    fig = over(fig, nr, feather(under, 10))
    # the lantern now stands on the floor at her left (both Fables: "lamp to lamp" across the cut into B1), so where it stood,
    # at her right knee, the figure needs the cushion's corner: from 'nolantern', only there, under whatever each pose draws
    nlc = AL['nolantern'].copy(); nlc[..., 3] = (nlc[..., 3] * feather(ndi.binary_dilation(lmask, iterations=10) & lz & ~poly(Z['hand']), 4)).astype(np.uint8)
    out = {'scale': SC, 'size': [round(W * SC), round(H * SC)], 'pivots': {k: [round(a * SC, 1), round(b * SC, 1)] for k, (a, b) in Z['pivots'].items()}, 'poses': {}}
    save = lambda a, name: Image.fromarray(a).resize((round(W * SC), round(H * SC)), Image.LANCZOS).save(os.path.join(D, name))
    save(lantern, 'lantern.png'); save(ribbon, 'ribbon.png')
    # each pose: the changed region of the arm (and the hood for 'ear'), feathered, laid over the figure
    for p in ['base'] + POSES:
        if p == 'base': save(fig if Z.get('lantern_at_knee') else beneath(fig, nlc), 'figure_base.png'); out['poses'][p] = 'figure_base.png'; continue
        al = AL[p].copy()
        ex, ey, v = lantern_offset(al, body)                         # take out this drawing's own (displaced) lantern
        el = shift(lmask.astype(np.uint8), ex, ey).astype(bool); el = ndi.binary_dilation(el, iterations=5)
        keep = np.abs(lum(al) - lum(shift(lantern, ex, ey))) > 40       # (except her arm where it crosses it)
        al[..., 3] = (al[..., 3] * ~(el & ~keep)).astype(np.uint8)
        pa = lambda a: a[..., :3].astype(np.float32) * (a[..., 3:] / 255)
        d = np.maximum(np.abs(pa(al) - pa(fig)).max(-1), np.abs(al[..., 3].astype(np.float32) - fig[..., 3]))
        zone = arm | (poly(Z['hood_r']) if p == 'ear' else False)
        if p in BOTH_ARMS: zone = zone | (poly(Z['left']) & ~ndi.binary_dilation(rib, iterations=10))   # (clear of the ribbon: its own layer)
        m = ndi.binary_opening(d > 45, iterations=3) & zone
        m = ndi.binary_fill_holes(ndi.binary_closing(m, iterations=8))
        lab, n = ndi.label(m); sizes = ndi.sum(m, lab, range(1, n + 1)); m = np.isin(lab, 1 + np.flatnonzero(sizes > 4000))
        m = ndi.binary_dilation(m, iterations=14) & (zone | lz)
        comp = over(fig, al, feather(m, 9))
        ring = poly(Z['hand']) & ndi.binary_dilation(lmask, iterations=14)          # what's left of the old lantern's ring handle
        if p == 'wipe0': ring &= np.mgrid[:H, :W][0] > 1520                         # (her hand passes just above it)
        if not Z.get('lantern_at_knee'): comp[..., 3] = (comp[..., 3] * ~ring).astype(np.uint8)
        if not Z.get('lantern_at_knee'): comp = beneath(comp, nlc)
        name = f'figure_{p}.png'; save(comp, name); out['poses'][p] = name
        print(f'{p:6s} patch {m.sum() / 1e3:.0f}k px, lantern offset {ex},{ey} ncc {v:.2f}')
    # her book: the paper that shows in each pose (the stage prints the screen's page on it, Michael: the book mirrors the screen)
    out['book'] = {}
    bz = poly(Z['book'])
    def paper_of(name):
        fig = np.asarray(Image.open(os.path.join(D, name)).convert('RGBA').resize((W, H), Image.LANCZOS)).astype(np.int16)
        r, g, b, a = fig[..., 0], fig[..., 1], fig[..., 2], fig[..., 3]
        return bz & (a > 200) & ((r + g + b) / 3 > 150) & ((r - b) < 60) & (np.abs(r - g) < 40)
    # the book sits still in her lap; her cuffs (the same cream) move with her arms. So the book is where it is in the poses that
    # show it plainly, and a pose's book is its paper inside that, opened to strip the cuffs' fibrous fringe
    canon = np.zeros((H, W), bool)
    for q in ('ear', 'rest', 'base'): canon |= ndi.binary_opening(paper_of(out['poses'][q]), iterations=3)
    canon = ndi.binary_dilation(ndi.binary_fill_holes(ndi.binary_closing(canon, iterations=6)), iterations=4)
    for p, name in out['poses'].items():
        paper = ndi.binary_opening(paper_of(name) & canon, iterations=5)
        lab, n = ndi.label(paper)
        if not n: continue
        sizes = ndi.sum(paper, lab, range(1, n + 1)); keep = np.isin(lab, 1 + np.flatnonzero(sizes > max(1500, sizes.max() * .15)))
        if keep.sum() < 2500: continue
        ys, xs = np.nonzero(keep); rect = cv2.minAreaRect(np.stack([xs, ys], 1).astype(np.float32))
        quad = cv2.boxPoints(rect)                                           # four corners, ordered round the rectangle
        mk = (feather(keep, 1.5) * 255).astype(np.uint8)
        Image.fromarray(np.dstack([np.full_like(mk, 255)] * 3 + [mk])).resize((round(W * SC), round(H * SC)), Image.LANCZOS).save(os.path.join(D, f'book_{p}.png'))
        out['book'][p] = {'mask': f'book_{p}.png', 'quad': [[round(float(x) * SC, 1), round(float(y) * SC, 1)] for x, y in quad]}
        print(f'book {p:10s} {keep.sum() / 1e3:.0f}k px')
    json.dump(out, open(os.path.join(D, 'meta.json'), 'w'), indent=1)


if __name__ == '__main__' and '--cut' in sys.argv:
    cut()
