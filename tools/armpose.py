"""Drawn arm poses for the rig (MOTION.md §6): where the mesh can't make an arm read (the upper arm swung across the chest, say),
GPT Image redraws the whole arm (puff, upper arm, cuff, hand) at that pose as an edit of the base; the edit is registered onto
the base, SAM cuts the new arm, and the rig swaps it in whenever the performed angles are near the pose's (engine/rig.js
armPoses), rotated by the difference.

    .venv/bin/python tools/armpose.py projects/<film>/rig/clawd/armposes_spec.json

SPEC: {"image": "base.png", "out": "build", "poses": [{"name": "cross", "side": "R", "arm": -92, "elbow": -55, "hand": "flat",
       "crop": [x0, y0, n], "prompt": "...", "tol": [25, 40], "pos": [[x, y], ...] (base px, on the new arm), "neg": [[x, y], ...]}]}
Writes OUT/armpose_<side>_<name>.png and OUT/armposes.json {side: [{name, arm, elbow, hand, tol, file, x, y, w, h, replaces}]}.
Edits are cached as OUT/_armpose_edits/<side>_<name>.png; delete one to redo it.
"""
import json, os, subprocess, sys
import numpy as np, cv2
from PIL import Image
from scipy import ndimage as ndi

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEEP = ("Keep EVERYTHING else exactly identical: her face, hair, expression, body, dress, bow, skirt, her other arm and hand, the position "
        "and size of everything in the frame, the same crisp anime lineart, cel shading and colours. Transparent background.")


def lum(a): return ((a[..., :3].astype(np.float32) @ [.299, .587, .114]) * (a[..., 3] / 255) + 200 * (1 - a[..., 3] / 255)).astype(np.float32)


def main(spec):
    S = json.load(open(spec)); d = os.path.dirname(os.path.abspath(spec)); out = os.path.join(d, S['out']); ed = os.path.join(out, '_armpose_edits')
    os.makedirs(ed, exist_ok=True)
    base = np.array(Image.open(os.path.join(d, S['image'])).convert('RGBA'))
    table = json.load(open(os.path.join(out, 'armposes.json'))) if os.path.exists(os.path.join(out, 'armposes.json')) else {}
    for P in S['poses']:
        sd, nm = P['side'], P['name']; x0, y0, n = P['crop']; crop = base[y0:y0 + n, x0:x0 + n]
        cp = os.path.join(ed, f'_crop_{sd}_{nm}.png'); Image.fromarray(crop).save(cp)
        ep = os.path.join(ed, f'{sd}_{nm}.png')
        if not os.path.exists(ep):
            subprocess.run([os.path.join(ROOT, '.venv', 'bin', 'python'), os.path.join(ROOT, 'tools', 'gptimage.py'), 'Edit this character illustration. ' + P['prompt'] + ' ' + KEEP,
                            ep, '--size', f'{n}x{n}', '--quality', 'high', '--transparent', '--ref', cp], check=True)
        e = np.array(Image.open(ep).convert('RGBA').resize((n, n), Image.LANCZOS))
        # register on everything but the arm's zone (the arm's side of the body, above the waist)
        H, W = crop.shape[:2]; yy, xx = np.mgrid[:H, :W]
        zone = np.zeros((H, W), bool)
        for q in P['pos'] + [P.get('shoulder', [0, 0])]:
            zone |= (xx - (q[0] - x0)) ** 2 + (yy - (q[1] - y0)) ** 2 < 230 ** 2
        zone = ndi.binary_dilation(zone, iterations=40)
        m = ((crop[..., 3] > 200) & ~zone).astype(np.uint8); warp = np.eye(2, 3, dtype=np.float32)
        for sc in (.25, .5, 1.):
            a = cv2.GaussianBlur(cv2.resize(lum(crop), None, fx=sc, fy=sc), (0, 0), 1.2); b = cv2.GaussianBlur(cv2.resize(lum(e), None, fx=sc, fy=sc), (0, 0), 1.2)
            w = warp.copy(); w[:, 2] *= sc
            _, w = cv2.findTransformECC(a, b, w, cv2.MOTION_AFFINE, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), cv2.resize(m, None, fx=sc, fy=sc, interpolation=cv2.INTER_NEAREST), 5)
            warp = w.copy(); warp[:, 2] /= sc
        al = cv2.warpAffine(e, warp, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)
        res = np.abs(lum(al) - lum(crop))[m.astype(bool)].mean(); print(f'{sd}_{nm}: registered, residual {res:.1f}')
        # SAM on the edit: the new arm (puff to fingertips)
        full = np.zeros_like(base); full[y0:y0 + n, x0:x0 + n] = al
        fp = os.path.join(ed, f'_aligned_{sd}_{nm}.png'); Image.fromarray(full).save(fp)
        # one SAM part per piece of the arm (SAM keeps a whole limb poorly across its colour changes), unioned
        parts = P.get('parts') or {'arm': {'pos': P['pos']}}
        parts = {k: {'pos': v['pos'], 'neg': v.get('neg', P['neg']), **({'box': v['box']} if v.get('box') else {})} for k, v in parts.items()}
        pj = os.path.join(ed, f'_parts_{sd}_{nm}.json'); json.dump(parts, open(pj, 'w'))
        md = os.path.join(ed, f'_seg_{sd}_{nm}'); subprocess.run([os.path.join(ROOT, 'vendor', 'seed-vc', '.venv', 'bin', 'python'), os.path.join(ROOT, 'tools', 'segment.py'), fp, pj, md], check=True)
        mk = np.zeros(base.shape[:2], bool)
        for k in parts: mk |= np.array(Image.open(os.path.join(md, k + '.png'))) > 127
        mk = ndi.binary_fill_holes(ndi.binary_closing(mk, iterations=3))
        lab, k = ndi.label(mk); sz = ndi.sum(mk, lab, range(1, k + 1)); mk = lab == (1 + int(np.argmax(sz))) if k else mk
        a8 = (full[..., 3].astype(np.float32) * np.clip(ndi.distance_transform_edt(mk) / 1.5, 0, 1)).astype(np.uint8)
        lay = full.copy(); lay[..., 3] = a8
        ys, xs = np.nonzero(a8 > 0); bx0, bx1, by0, by1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        fn = f'armpose_{sd}_{nm}.png'; Image.fromarray(lay[by0:by1, bx0:bx1]).save(os.path.join(out, fn))
        ent = {'name': nm, 'arm': P['arm'], 'elbow': P['elbow'], 'hand': P.get('hand'), 'tol': P.get('tol', [25, 40]), 'file': fn,
               'x': int(bx0), 'y': int(by0), 'w': int(bx1 - bx0), 'h': int(by1 - by0),
               'replaces': P.get('replaces', [f'sleeve_{sd}', f'trim_{sd}', f'arm_{sd}', f'cuff_{sd}', f'hand_{sd}'])}
        table[sd] = [q for q in table.get(sd, []) if q['name'] != nm] + [ent]
        print('  wrote', fn, ent['x'], ent['y'], ent['w'], ent['h'])
    json.dump(table, open(os.path.join(out, 'armposes.json'), 'w'), indent=1)


if __name__ == '__main__':
    main(sys.argv[1])
