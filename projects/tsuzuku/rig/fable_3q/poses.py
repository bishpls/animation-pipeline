"""Fable three-quarter: the drawn arms as KEY DRAWINGS (cut-out in-betweening). tools/armpose.py cuts each drawn arm (the lantern
lifted to the chin, held overhead; the free hand clapping at the lantern wrist) into mesh/build/armposes.json. A 2D arm skeleton
can't carry the far arm between them (foreshortening changes its lengths too much: a least-squares FK fit missed by 40-190 px), so
the rig selects a drawing by NAME (p.handL / p.handR; arm and elbow 0, tolerance unlimited) and the motion places it with a rigid
transform per drawing (p.poseL / p.poseR, engine/rig.js): an in-between is the nearer key drawing moved toward the other key's
place (its fist and stick angle interpolated). This adds the far arm at rest as a key drawing too (the base's own sleeve end, hand
and stick), so the raise runs rest -> lift -> up through drawings, and stores each drawing's reference points:
  R poses: fist (the fist's centre), tip (the stick's tip), ring (where the lantern's handle hooks), wrist (for the claps)
  L clap:  hand (the clapping hand's centre)
    .venv/bin/python projects/tsuzuku/rig/fable_3q/poses.py
"""
import json, os
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

D = os.path.dirname(os.path.abspath(__file__)); P = lambda *a: os.path.join(D, *a)
TABLE = P('mesh', 'build', 'armposes.json'); ED = P('mesh', 'build', '_armpose_edits')
rd = lambda p: np.array(Image.open(p)) > 127


def axis(mask):
    ys, xs = np.nonzero(mask); c = np.array([xs.mean(), ys.mean()]); X = np.stack([xs - c[0], ys - c[1]], 1)
    w, v = np.linalg.eigh(X.T @ X / len(xs)); return c, v[:, -1]


def refs(hand, stick, img):
    """fist, stick tip, ring (the handle's hook), wrist"""
    ys, xs = np.nonzero(stick); c, v = axis(stick); t = (xs - c[0]) * v[0] + (ys - c[1]) * v[1]
    e1, e2 = c + v * t.min(), c + v * t.max(); hy, hx = np.nonzero(hand); hc = np.array([hx.mean(), hy.mean()])
    tip, butt = (e1, e2) if np.linalg.norm(e1 - hc) > np.linalg.norm(e2 - hc) else (e2, e1)
    k = np.hypot(hx - butt[0], hy - butt[1]) < 110; fist = np.array([hx[k].mean(), hy[k].mean()])
    a = img.astype(int); orange = (a[..., 0] > 140) & (a[..., 1] > 60) & (a[..., 1] < 170) & (a[..., 2] < 110) & (a[..., 3] > 200)
    m = orange & ndi.binary_dilation(stick, iterations=8) & (np.hypot(*np.meshgrid(np.arange(stick.shape[1]) - tip[0], np.arange(stick.shape[0]) - tip[1])) < 90)
    lab, n = ndi.label(m)
    if n: sz = ndi.sum(m, lab, range(1, n + 1)); m = lab == 1 + int(np.argmax(sz))       # (the ring itself, not the handle's highlights)
    yy, xx = np.nonzero(m); ring = np.array([xx.mean(), yy.max()]) if n else tip + (butt - tip) / np.linalg.norm(butt - tip) * 44
    u = (fist - tip) / np.linalg.norm(fist - tip); wrist = fist + u * 90
    r = lambda q: [round(float(q[0]), 1), round(float(q[1]), 1)]
    return {'fist': r(fist), 'tip': r(tip), 'ring': r(ring), 'wrist': r(wrist)}


def main():
    T = json.load(open(TABLE)); base = np.array(Image.open(P('base_keyed.png')))
    lay = lambda n: np.array(Image.open(P('mesh', 'layers', n + '.png')))
    # the far arm at rest, as a key drawing: the base's own pieces (sleeve end, hand, stick), composited back to front
    comp = np.zeros_like(base, dtype=float)
    for n in ('stick', 'sleeve_R', 'hand_R'):
        L = lay(n).astype(float) / 255; a = L[..., 3:4]; comp[..., :3] = comp[..., :3] * (1 - a) + L[..., :3] * a; comp[..., 3:] = comp[..., 3:] * (1 - a) + a
    comp = (comp * 255).astype(np.uint8); ys, xs = np.nonzero(comp[..., 3] > 0); x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    Image.fromarray(comp[y0:y1, x0:x1]).save(P('mesh', 'build', 'armpose_R_rest.png'))
    rest = {'name': 'rest', 'hand': 'rest', 'file': 'armpose_R_rest.png', 'x': int(x0), 'y': int(y0), 'w': int(x1 - x0), 'h': int(y1 - y0),
            'replaces': ['sleeve_R', 'hand_R', 'stick'], **refs(lay('hand_R')[..., 3] > 8, lay('stick')[..., 3] > 8, base)}
    rest['ring'] = [302.0, 2022.0]                                           # (the hook, measured: the ring's bottom, 2016-2033)
    T['R'] = [rest] + [e for e in T['R'] if e['name'] != 'rest']
    for side, poses in T.items():
        for e in poses:
            e.update(arm=0, elbow=0, tol=[999, 999], follow=True, anchor=f'sleeve_{side}')
            for k in ('fit', 'ring0', 'ringBase'): e.pop(k, None)
            if e['name'] == 'rest' or e['name'].startswith('push'): continue      # (the push's arms come from build.py pusharms, with their points)
            seg = os.path.join(ED, f'_seg_{side}_{e["name"]}'); img = np.array(Image.open(os.path.join(ED, f'_aligned_{side}_{e["name"]}.png')))
            if side == 'R': e.update(refs(rd(os.path.join(seg, 'hand.png')), rd(os.path.join(seg, 'stick.png')), img))
            else:
                hp = os.path.join(seg, 'hand.png'); c, _ = axis(rd(hp if os.path.exists(hp) else os.path.join(seg, 'arm.png')))
                e['hand0'] = [round(float(c[0]), 1), round(float(c[1]), 1)]
            print(side, e['name'], {k: e[k] for k in ('fist', 'tip', 'ring', 'wrist', 'hand0') if k in e})
    print('R rest', {k: rest[k] for k in ('fist', 'tip', 'ring', 'wrist')})
    json.dump(T, open(TABLE, 'w'), indent=1)


if __name__ == '__main__':
    main()
