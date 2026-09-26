"""Where a retargeted clip runs out of rig (MOTION.md, "Rig limits"): per channel, the target (unclamped, from the pose) against
what the rig got (the retarget's clamped curve), with the clamps marked; the arm's depth (the wrist in front of or behind the
body, which a front-view rig can only show by layer order); forearm foreshortening (its image length against its 3D length);
and the feet: toe direction, heel lift against the toe (a pivot), and planted feet that slide.

    .venv/bin/python tools/mocap_diagnose.py POSE.json RIG.json OUT_DIR
"""
import json, os, sys
import numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from scipy.signal import savgol_filter

pose, rigj, out = sys.argv[1:4]; os.makedirs(out, exist_ok=True)
J = json.load(open(pose)); R = json.load(open(rigj)); fps = J['fps']; Wd, Hd = J['size']
img = savgol_filter(np.array([[[p[0] * Wd, p[1] * Hd] for p in f['img']] for f in J['frames']]), 7, 2, axis=0)
wld = savgol_filter(np.array([[p[:3] for p in f['world']] for f in J['frames']]), 7, 2, axis=0)
n = len(img); ts = np.arange(n) / fps; deg = np.degrees
C = {'t': '#2a78d6', 'a': '#eb6834', 'lim': '#c3c2b7', 'ink': '#1f1f1e'}
plt.rcParams.update({'font.size': 8, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': True, 'grid.color': '#ecebe4'})
def outward(v, side): return deg(np.arctan2(-v[:, 0] if side == 'L' else v[:, 0], v[:, 1]))
rep = {}
# ---- arms: raw shoulder and elbow angles (unclamped, continuous), foreshortening, depth
arms = {}
for sd, (s, e, w) in {'L': (12, 14, 16), 'R': (11, 13, 15)}.items():
    up, fo = img[:, e] - img[:, s], img[:, w] - img[:, e]
    th = deg(np.unwrap(np.radians(outward(up, sd)))); ph = deg(np.unwrap(np.radians(outward(fo, sd))))
    rel = ph - th; rel -= 360 * np.round(np.median(rel) / 360)
    fl3 = np.linalg.norm(wld[:, w] - wld[:, e], axis=1); fl2 = np.linalg.norm(fo, axis=1); fsc = fl2 / np.percentile(fl2, 97)
    ul2 = np.linalg.norm(up, axis=1); usc = ul2 / np.percentile(ul2, 97)
    depth = wld[:, w, 2] - (wld[:, 11, 2] + wld[:, 12, 2]) / 2               # m; negative = the wrist in front of the shoulder plane
    arms[sd] = dict(arm=th - 29.7, elbow=rel, fore=fsc, upper=usc, depth=depth)
    rep['arm' + sd] = {'raw_range': [round(float((th - 29.7).min()), 1), round(float((th - 29.7).max()), 1)],
                       'elbow_raw_range': [round(float(rel.min()), 1), round(float(rel.max()), 1)],
                       'elbow_beyond_150_pct': round(100 * float((np.abs(rel) > 150).mean()), 1),
                       'forearm_foreshortened_below_0.7_pct': round(100 * float((fsc < .7).mean()), 1),
                       'upperarm_foreshortened_below_0.7_pct': round(100 * float((usc < .7).mean()), 1),
                       'wrist_in_front_gt_15cm_pct': round(100 * float((depth < -.15).mean()), 1),
                       'wrist_behind_body_pct': round(100 * float((depth > .05).mean()), 1),
                       'elbow_full_turns': round(float(np.ptp(rel) / 360), 2)}
# ---- feet: toe direction (heel -> foot index, image plane), heel lift against the toe (world y), sliding while planted
feet = {}
for sd, (hl, ti, an) in {'L': (30, 32, 28), 'R': (29, 31, 27)}.items():
    v = img[:, ti] - img[:, hl]; toe = deg(np.arctan2(v[:, 0], v[:, 1]))        # 0 = straight down the image
    heel_up = (wld[:, ti, 1] - wld[:, hl, 1]) * 100                             # cm; + = the heel above the toe (world y points down)
    ay = img[:, an, 1]; planted = ay > np.percentile(ay, 60); dx = np.abs(np.diff(img[:, an, 0]))
    feet[sd] = dict(toe=toe, heel=heel_up)
    rep['foot' + sd] = {'toe_angle_range_deg': [round(float(np.percentile(toe, 5)), 1), round(float(np.percentile(toe, 95)), 1)],
                        'heel_above_toe_cm_p95': round(float(np.percentile(heel_up, 95)), 1),
                        'heel_pivot_frames_pct': round(100 * float((heel_up > 4).mean()), 1),
                        'source_planted_slide_px_p95': round(float(np.percentile(dx[planted[1:]], 95)), 2)}
# the retargeted curves: planted feet that slide in the rig
for sd in 'LR':
    x = np.array(R['curves']['foot' + sd + 'X']['v']); y = np.array(R['curves']['foot' + sd + 'Y']['v']); dxr = np.abs(np.diff(x)); pl = y[1:] < 3
    rep['foot' + sd]['rig_planted_frames'] = int(pl.sum()); rep['foot' + sd]['rig_sliding_frames'] = int((dxr[pl] > 2).sum())
# clamp hits in the retargeted curves
LIM = {'armFront': (0, 2), 'armBack': (0, 2), 'arm': (-100, 175), 'elbow': (-320, 320), 'hipY': (-40, 170), 'hipX': (-1.3, 1.3), 'bodyZ': (-12, 12), 'bodyX': (-.9, .9), 'angleZ': (-14, 14), 'angleX': (-.7, .7), 'angleY': (-.8, .8)}   # (tools/retarget_mocap.py's)
rep['clamped_pct'] = {k: round(100 * float(np.mean(np.isclose(np.array(c['v']), next(v for kk, v in LIM.items() if k.startswith(kk))[0]) | np.isclose(np.array(c['v']), next(v for kk, v in LIM.items() if k.startswith(kk))[1]))), 1)
                      for k, c in R['curves'].items() if any(k.startswith(kk) for kk in LIM)}
json.dump(rep, open(os.path.join(out, 'rig_limits.json'), 'w'), indent=1); print(json.dumps(rep, indent=1))

fig, axs = plt.subplots(4, 2, figsize=(12, 9), sharex=True)
for j, sd in enumerate('LR'):
    A = arms[sd]
    for i, (k, lim, lab) in enumerate([('arm', (-40, 165), 'shoulder (deg, + out)'), ('elbow', (-150, 150), 'elbow (deg)'), ('fore', None, 'forearm image length / full'), ('depth', None, 'wrist depth vs shoulders (m, - = front)')]):
        ax = axs[i, j]; ax.plot(ts, A[k], color=C['t'], lw=1.3, label='target (pose)')
        if lim: ax.plot(ts, np.clip(A[k], *lim), color=C['a'], lw=1, ls='--', label='rig (clamped)'); [ax.axhline(v, color=C['lim'], lw=1) for v in lim]
        ax.set_title(f'{"image-left" if sd == "L" else "image-right"} arm: {lab}', loc='left', fontsize=8)
        if i == 0: ax.legend(frameon=False, fontsize=7)
axs[-1, 0].set_xlabel('source s'); axs[-1, 1].set_xlabel('source s'); fig.tight_layout(); fig.savefig(os.path.join(out, 'rig_limits_arms.png')); plt.close(fig)
fig, axs = plt.subplots(2, 2, figsize=(12, 5), sharex=True)
for j, sd in enumerate('LR'):
    axs[0, j].plot(ts, feet[sd]['toe'], color=C['t'], lw=1.3); axs[0, j].set_title(f'{"image-left" if sd == "L" else "image-right"} foot: toe direction (deg; the rig has none)', loc='left', fontsize=8)
    axs[1, j].plot(ts, feet[sd]['heel'], color=C['t'], lw=1.3); axs[1, j].axhline(4, color=C['lim'], lw=1); axs[1, j].set_title('heel above toe (cm; the rig lifts the whole boot)', loc='left', fontsize=8)
axs[-1, 0].set_xlabel('source s'); axs[-1, 1].set_xlabel('source s'); fig.tight_layout(); fig.savefig(os.path.join(out, 'rig_limits_feet.png')); plt.close(fig)
