"""rom video's renderer against the ROM boards' path (rom.Rig.model_posed + a fresh gpu.Renderer, the light in the rest
head frame), pose by pose at the hold: (a) boards, (b) ours with the head light in the rest frame, (c) ours as shipped
(the head light in the posed head's frame). Pixel differences per pair, and head crops for the eye.

    python -m charkit script tools/motionvid/parity.py BUILD OUT [POSES]
"""
import json, os, sys

import numpy as np

sys.path.insert(0, os.getcwd())
from PIL import Image
from charkit import rom, romvideo as RV, pose as P
from charkit.render import gpu

build, out = sys.argv[1], sys.argv[2]
poses = (sys.argv[3] if len(sys.argv) > 3 else 'squat,head_nod,head_turn,elbows_135,raise_side_90').split(',')
os.makedirs(out, exist_ok=True)
rig, _ = rom.load(build)
lib = P.library()
V = rom.board_views(rig, (0, 35, 90), rom.BOARD_RES)
sk = RV.Skinner(rig)
R = RV.posed_renderer(sk.rest(), None, 2)
rep = {}


def diff(a, b):
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(-1)
    return dict(max=int(d.max()), share_gt8=round(float((d > 8).mean()), 6), share_gt32=round(float((d > 32).mean()), 6))


for p in poses:
    D = rig.solve(lib[p])
    L = RV.local_rotations(rig.sk, D)
    D1 = RV.deform(rig, RV.Key(L).at(1.0))
    dD = max(float(np.abs(D1[b] - D[b]).max()) for b in rig.sk.order if b in D)
    R0 = gpu.Renderer(rig.model_posed(D), ss=2)
    a = [R0.render(v) for v in V]
    del R0
    R.set_pose(sk.prims(D1), np.eye(3))
    b = [R.render(v) for v in V]
    Rh = D1['head'][:3, :3]
    R.set_pose(sk.prims(D1), RV.C3 @ Rh @ RV.C3.T)
    c = [R.render(v) for v in V]
    rep[p] = dict(deform_max=dD, head_turn_deg=round(float(np.degrees(np.arccos(np.clip((np.trace(Rh) - 1) / 2, -1, 1)))), 2),
                  boards_vs_ours_rest_light=[diff(x, y) for x, y in zip(a, b)],
                  rest_light_vs_head_light=[diff(x, y) for x, y in zip(b, c)])
    H, _ = P.posed_joints(rig.sk, D1)
    for j, v in enumerate(V):
        row = np.concatenate([a[j], b[j], c[j]], 1)
        Image.fromarray(row).save(os.path.join(out, '%s_%03d.png' % (p, int(v.az))))
    print(p, json.dumps(rep[p]))
json.dump(rep, open(os.path.join(out, 'parity.json'), 'w'), indent=1)
