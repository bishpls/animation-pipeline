"""Fable three-quarter (room ending): her face states as drawn variants. From behind, what reads is the cheek, the corner of the
mouth and the eye's edge, and a smile lifts the cheek and, from this angle, the ear with it (Fable). So each state is ONE GPT Image
edit of a head crop (tools/gptimage.py, paid, logged), registered back onto the crop on everything the edit shouldn't change
(hair, bangs, collar), colour-matched there, and cut into the three patches the rig swaps as units (p.swap, engine/rig.js):
  eye   the lashes and the eye's outer corner (an ellipse, feathered into the face under it: the blinks swap only this)
  face  the cheek, jaw and mouth: the edit's skin and the drawn lines touching it, near the base's face, never the eye or the neck
  ear   the same for the ear
    .venv/bin/python projects/tsuzuku/rig/fable_3q/faces.py [state ...]     -> mesh/build/<patch>@<state>.png, mesh/build/variants.json
Edits are cached in mesh/build/_edits_face/<state>.png (delete one to redo it).
"""
import json, os, subprocess, sys
import numpy as np, cv2
from PIL import Image
from scipy import ndimage as ndi

D = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(D, '..', '..', '..', '..'))
P = lambda *a: os.path.join(D, *a)
X0, Y0, N = 800, 600, 1024                               # the head crop (padded canvas px)
EYE = (1070, 1045, 26, 34)                               # the eye patch (as mesh/layers.json claims it)
KEEP = ("The head does NOT turn and does not move: the same lost profile seen from behind, the same angle, position and size. Keep "
        "EVERYTHING else exactly identical: her hair, bangs, the ribbon, the collar and hood, the crisp anime lineart, cel shading, "
        "colours and edge lighting. Only the face changes as described. Transparent background.")
STATES = {
 'corner': "Her expression changes only slightly: the corner of her mouth lifts a little (the start of a smile) and her cheek rises a "
           "touch with it; her eye looks brighter, a little more open.",
 'smile': "She smiles a real, warm, closed-lips smile: the corner of her mouth lifts clearly, her cheek rises and rounds with it (the "
          "cheek's outline higher and fuller), her ear lifts a little with the cheek, and her lower eyelid lifts a touch. Her eye stays "
          "open, looking left.",
 # (v1 of the two open states turned her face toward the viewer, the open one to a three-quarter face: Fable refuses any turn to the
 #  camera beyond the push. v2 anchors the angle: only the eye's outer corner, the nose hidden, the open mouth only at the cheek's edge)
 'open_half': "She is breaking into an open smile, seen from exactly the same angle, a lost profile from behind: her jaw drops a "
              "little, so the outline of her chin and jaw below the cheek moves slightly down; at the very edge of her cheek the corner "
              "of her mouth opens a little (just a small dark notch of the open mouth at the cheek's outline); her cheek lifts and "
              "rounds; her ear lifts a little with the cheek. The eye is still seen only by its outer corner and lashes (no more of the "
              "eye than now, no iris), and her nose stays hidden behind the curve of her cheek.",
 'open': "She smiles openly, overjoyed, seen from exactly the same angle, a lost profile from behind: her jaw drops, so the outline of "
         "her chin and jaw below the cheek moves down clearly; at the edge of her cheek the corner of her wide-open mouth shows (a dark "
         "open notch at the cheek's outline, the tip of the upper lip); her cheek rises and rounds; her ear lifts a little with the "
         "cheek; her lashes lift (the eye wide open, but still seen only by its outer corner and lashes, no iris). Her nose stays hidden "
         "behind the curve of her cheek. Nothing turns toward the viewer.",
 'blink_half': "Her eye is half closed, mid-blink: the upper eyelid and lashes halfway down. Nothing else changes.",
 'blink': "Her eye is closed, a blink: the lashes' curve lowered and closed. Nothing else changes.",
}
PATCHES = {'corner': ['eye', 'face', 'ear'], 'smile': ['eye', 'face', 'ear'], 'open_half': ['eye', 'face', 'ear'], 'open': ['eye', 'face', 'ear'],
           'blink_half': ['eye'], 'blink': ['eye']}

g = lambda a: ((a[..., :3].astype(np.float32) @ [.299, .587, .114]) * (a[..., 3] / 255) + 200 * (1 - a[..., 3] / 255)).astype(np.float32)
isskin = lambda I: (I[..., 0].astype(int) > 150) & (I[..., 0].astype(int) - I[..., 2].astype(int) > 6) & ((I[..., :3].astype(float) @ [.299, .587, .114]) > 130) & (I[..., 3] > 128)


def main(names):
    base = np.array(Image.open(P('base_keyed.png')).convert('RGBA')); crop = base[Y0:Y0 + N, X0:X0 + N]
    ed = P('mesh', 'build', '_edits_face'); os.makedirs(ed, exist_ok=True); cp = os.path.join(ed, '_crop.png'); Image.fromarray(crop).save(cp)
    lay = lambda n: np.array(Image.open(P('mesh', 'layers', n + '.png')).convert('RGBA'))[Y0:Y0 + N, X0:X0 + N, 3] > 8
    face0, ear0, neck0 = lay('face'), lay('ear'), lay('neck')
    yy, xx = np.mgrid[:N, :N]; cx, cy, rx, ry = EYE; eyeM = ((xx - (cx - X0)) / rx) ** 2 + ((yy - (cy - Y0)) / ry) ** 2 <= 1
    changed = ndi.binary_dilation(face0 | ear0 | eyeM, iterations=40)
    table = json.load(open(P('mesh', 'build', 'variants.json'))) if os.path.exists(P('mesh', 'build', 'variants.json')) else {}
    for st in names:
        ep = os.path.join(ed, st + '.png')
        if not os.path.exists(ep):
            subprocess.run([os.path.join(ROOT, '.venv', 'bin', 'python'), os.path.join(ROOT, 'tools', 'gptimage.py'),
                            'Edit this character close-up, seen from behind in a lost profile. ' + STATES[st] + ' ' + KEEP, ep,
                            '--size', f'{N}x{N}', '--quality', 'high', '--transparent', '--ref', cp], check=True)
        e = np.array(Image.open(ep).convert('RGBA').resize((N, N), Image.LANCZOS))
        m = (~changed & (crop[..., 3] > 200)).astype(np.uint8); warp = np.eye(2, 3, dtype=np.float32)
        for sc in (.25, .5, 1.):
            a = cv2.GaussianBlur(cv2.resize(g(crop), None, fx=sc, fy=sc), (0, 0), 1.2); b = cv2.GaussianBlur(cv2.resize(g(e), None, fx=sc, fy=sc), (0, 0), 1.2)
            w = warp.copy(); w[:, 2] *= sc
            _, w = cv2.findTransformECC(a, b, w, cv2.MOTION_AFFINE, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6),
                                        cv2.resize(m, None, fx=sc, fy=sc, interpolation=cv2.INTER_NEAREST), 5)
            warp = w.copy(); warp[:, 2] /= sc
        al = cv2.warpAffine(e, warp, (N, N), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)
        res = float(np.abs(g(al) - g(crop))[m.astype(bool)].mean())
        k = m.astype(bool) & (al[..., 3] > 200)
        for c in range(3):                                   # colour-match the edit to the crop (the model drifts a little)
            sa, sb = al[k, c].astype(float), crop[k, c].astype(float)
            al[..., c] = np.clip((al[..., c] - sa.mean()) / (sa.std() + 1e-6) * sb.std() + sb.mean(), 0, 255).astype(np.uint8)
        Image.fromarray(al).save(os.path.join(ed, f'_al_{st}.png'))
        skin = isskin(al); dark = (al[..., :3].astype(float) @ [.299, .587, .114] < 90) & (al[..., 3] > 60)
        lines = dark & ndi.binary_dilation(skin, iterations=4) & ~ndi.binary_dilation(~(skin | dark), iterations=1) | (dark & ndi.binary_dilation(skin, iterations=2))
        print(f'{st:11s} registered, residual {res:.1f}')
        for pn in PATCHES[st]:
            if pn == 'eye':
                d = ndi.distance_transform_edt(eyeM); A = np.clip(d / 8, 0, 1) * (al[..., 3] / 255)
                sel = eyeM
            else:
                near = ndi.binary_dilation(face0 if pn == 'face' else ear0, iterations=26)
                sel = near & (skin | lines)
                if pn == 'face':
                    sel &= ~ndi.binary_erosion(eyeM, iterations=6) & ~ndi.binary_erosion(neck0, iterations=4)
                    sel |= face0 & (al[..., 3] > 128) & ~eyeM          # (never less than the base face: shadowed skin under the jaw isn't 'skin')
                else: sel &= ~ndi.binary_dilation(face0, iterations=2) | ear0
                lab, n = ndi.label(sel); sz = ndi.sum(sel, lab, range(1, n + 1)); sel = np.isin(lab, 1 + np.nonzero(sz >= max(sz) * .02)[0]) if n else sel
                A = sel * (al[..., 3] / 255)
            out = al.copy(); out[..., 3] = (A * 255).astype(np.uint8)
            ys, xs = np.nonzero(out[..., 3] > 0); x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
            fn = f'{pn}@{st}.png'; Image.fromarray(out[y0:y1, x0:x1]).save(P('mesh', 'build', fn))
            table.setdefault(pn, {})[st] = {'file': fn, 'x': int(x0 + X0), 'y': int(y0 + Y0), 'w': int(x1 - x0), 'h': int(y1 - y0)}
    json.dump(table, open(P('mesh', 'build', 'variants.json'), 'w'), indent=1)
    print('variants:', {k: list(v) for k, v in table.items()})


if __name__ == '__main__':
    main(sys.argv[1:] or list(STATES))
