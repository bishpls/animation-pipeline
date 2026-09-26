"""Before/after motion metrics per phrase from two MOTIONLAB dumps (tools/motion_audit.py's measures, per bar span), plus the
rule checks: planted feet that slide, and where the pelvis's deepest dips fall in the beat (Fable: Clawd rises ON the beat).
    .venv/bin/python tools/phrase_metrics.py BEFORE.json AFTER.json name:b0:b1 [name:b0:b1 ...] [--json OUT]
"""
import json, sys
import numpy as np
from scipy.signal import find_peaks
a = sys.argv[1:]; A, Bd = json.load(open(a[0])), json.load(open(a[1])); spans = [x for x in a[2:] if ':' in x and not x.startswith('--')]
out = a[a.index('--json') + 1] if '--json' in a else None
def metrics(D, b0, b1):
    fps = D['fps']; BAR = D['bar']; BT = BAR / 4; t = np.array(D['t']); b = t / BAR; m = (b >= b0) & (b < b1)
    PT = {k: np.array([p if p else [np.nan, np.nan] for p in v], float)[m] for k, v in D['pts'].items()}
    sp = {k: np.linalg.norm(np.gradient(v, axis=0) * fps, axis=1) for k, v in PT.items()}
    still = np.all([np.nan_to_num(sp[k]) < 30 for k in ['face', 'chest', 'waistband']], axis=0).mean() * 100
    rng = lambda k, i: float(np.nanpercentile(PT[k][:, i], 95) - np.nanpercentile(PT[k][:, i], 5))
    jump = lambda k: float(np.nan_to_num(np.linalg.norm(np.diff(PT[k], axis=0), axis=1)).max())
    core = sum(np.nan_to_num(sp[k]) for k in ['chest', 'waistband']).sum(); hands = sum(np.nan_to_num(sp[k]) for k in ['hand_L', 'hand_R']).sum()
    # planted feet (boot not rising) that slide sideways more than 1.5 stage px a frame
    slide = 0                                                        # from the channels (the heel pivot moves the boot's centroid, not its sole)
    P = {k: np.array(v)[m] for k, v in D['P'].items()}; P.update({k: np.array(D['P'].get(k, [0] * len(t)))[m] for k in ['footLX', 'footRX', 'footLY', 'footRY', 'rootX']})
    for sd in 'LR':
        sole = (P['foot' + sd + 'X'] + P['rootX']) * .27; pl = P['foot' + sd + 'Y'][1:] < 3; slide += int(((np.abs(np.diff(sole)) > 1.5) & pl).sum())
    hy = np.array(D['P']['hipY'])[m]; tt = t[m]; pk, _ = find_peaks(hy, distance=max(2, int(fps * BT * .6)), prominence=4)
    ph = ((tt[pk] / BT) % 1); dip_on_beat = float(np.mean((ph < .2) | (ph > .8)) * 100) if len(pk) else float('nan')
    return {'core_still_pct': round(still, 1), 'pelvis_y_px': round(rng('waistband', 1), 1), 'face_y_px': round(rng('face', 1), 1), 'core_to_hands': round(float(core / hands), 3),
            'hand_max_px_frame': round(max(jump('hand_L'), jump('hand_R')), 1), 'feet_moving_pct': round(float(np.mean((sp['boot_L'] > 30) | (sp['boot_R'] > 30)) * 100), 1),
            'planted_slide_frames': slide, 'dips_on_beat_pct': round(dip_on_beat, 1), 'bun_p95': round(float(np.percentile(np.abs(np.array(D['sp']['bun'])[m]), 95)), 1)}
R = {}
for s in spans:
    name, b0, b1 = s.split(':'); b0, b1 = float(b0), float(b1); x, y = metrics(A, b0, b1), metrics(Bd, b0, b1); R[name] = {'bars': [b0, b1], 'before': x, 'after': y}
    print(f'-- {name} (bars {b0}-{b1})'); [print(f'   {k:22s} {x[k]:>8} -> {y[k]:>8}') for k in x]
if out: json.dump(R, open(out, 'w'), indent=1)
