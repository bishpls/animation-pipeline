"""Per-phrase audit of a rig choreography (MOTION.md §11): which bars are hand-keyed or motion-captured, how many distinct
upper-body poses each phrase holds, the hands (default-hand share, shape changes, instant swaps, shapes lost in turned views,
shape against the arm's action), and the secondary motion (hair, buns, ahoge, bow, skirt) against the body's speed.
Input: a MOTIONLAB.dump() with hands (src/motionlab.js), and the film's refs/mocap/phrases.json.

    node engine/render.mjs projects/tsuzuku --eval='JSON.stringify(MOTIONLAB.dump(45, 93, 24))' > dump.json   (unwrap the JSON string)
    .venv/bin/python tools/dance_audit.py DUMP.json projects/tsuzuku [--finale] [--out metrics.json] [--label v8] [--phrases phrases.json]
"""
import json, os, sys
import numpy as np

A = sys.argv[1:]; opt = lambda k, d=None: A[A.index(k) + 1] if k in A else d
D = json.load(open(A[0])); proj = A[1]; FIN = '--finale' in A
t = np.array(D['t']); fps = D['fps']; BAR = D['bar']; b = t / BAR
P = {k: np.array(v, float) for k, v in D['P'].items()}; view = np.array(D['view']); HL = D['hand']['L']; HR = D['hand']['R']
PHR = ([('fold', 126, 129), ('F1 continued/why', 129, 134), ('F2 call+sideways', 134, 137), ('F3 page/and-then/hit', 137, 141), ('freeze', 141, 143.5)] if FIN else
       [('build', 45, 46), ('C1a drop', 46, 50), ('C1b wave', 50, 54), ('C1 sideways', 54, 58), ('C1c ikuzo', 58, 62), ('hook', 62, 66), ('V2a telling', 66, 70),
        ('V2b wrote her own', 70, 74), ('V2c side-step', 74, 78), ('V2d walk it', 78, 82), ('C2a continued', 82, 86), ('C2b and-then', 86, 90), ('breakdown+curtsy', 90, 93)])
# motion-capture coverage (arms / body) from phrases.json
M = json.load(open(opt('--phrases', os.path.join(proj, 'refs', 'mocap', 'phrases.json'))))['phrases']     # (--phrases: another version's table)
armM = np.zeros(len(t), bool); bodyM = np.zeros(len(t), bool)
for ph in M:
    if ph.get('off'): continue
    for shift in [ph.get('shift', 0)] + list(ph.get('reuse', [])):
      for g, v in ph.get('groups', {}).items():
        span = v if isinstance(v, list) else v.get('span'); lo, hi = span[0] + shift, span[1] + shift
        m = (b >= lo) & (b < hi)
        (armM if g.startswith('arms') or g == 'body' else bodyM)[m] = True
        if g == 'body': bodyM[m] = True
wrap = lambda a: (a + 180) % 360 - 180
d = lambda x: np.gradient(x) * fps
armspd = {s: np.hypot(d(P['arm' + s]), .7 * d(P['elbow' + s])) for s in 'LR'}          # deg/s, the upper arm and (less) the forearm
out = {'label': opt('--label', ''), 'finale': FIN, 'phrases': []}
# pose clusters: HELD poses (both arms slow), vector of arm/elbow angles, torso and head tilt, hand shapes
held = (armspd['L'] < 60) & (armspd['R'] < 60)
SH = sorted({h for h in HL + HR if h})
def vec(i):
    v = [P['armL'][i], P['armR'][i], .6 * P['elbowL'][i], .6 * P['elbowR'][i], 3 * P['bodyZ'][i], 2 * P['angleZ'][i]]
    return np.array(v + [25 * (HL[i] == s) for s in SH] + [25 * (HR[i] == s) for s in SH])
def clusters(idx, r=28):
    cs = []
    for i in idx[::2]:
        v = vec(i)
        for c in cs:
            if np.linalg.norm(c[0] / c[1] - v) < r: c[0] += v; c[1] += 1; break
        else: cs.append([v.copy(), 1])
    return sorted([c[1] for c in cs], reverse=True)
allc = clusters(np.flatnonzero(held))
out['held_poses_total'] = len([c for c in allc if c >= 3]); out['held_pose_share_top6'] = round(sum(allc[:6]) / max(1, sum(allc)), 3)
for name, lo, hi in PHR:
    m = (b >= lo) & (b < hi); n = int(m.sum())
    if not n: continue
    r = {'phrase': name, 'bars': [lo, hi], 'arms_mocap': round(armM[m].mean(), 2), 'body_mocap': round(bodyM[m].mean(), 2),
         'arm_speed': round(float((armspd['L'][m] + armspd['R'][m]).mean() / 2), 1),                  # deg/s: how much the arms move
         'torso_head_sd': round(float(np.std(P['bodyZ'][m]) + np.std(P['angleZ'][m])), 2),            # deg: how much the lean and tilt vary
         'airborne': int(sum(1 for i in np.flatnonzero(m) if min(P['footLY'][i], P['footRY'][i]) > 30))}
    c = clusters(np.flatnonzero(m & held)); r['held_poses'] = len([x for x in c if x >= 3])
    for s, H in (('L', HL), ('R', HR)):
        Hm = [H[i] for i in np.flatnonzero(m)]; sp = armspd[s][m]; vw = view[m]
        ch = sum(1 for i in range(1, n) if Hm[i] != Hm[i - 1])
        # an instant swap: two different named shapes (or named <-> default) with no in-between drawing on the way
        IB = {'relax', 'loose'}; inst = sum(1 for i in range(1, n) if Hm[i] != Hm[i - 1] and Hm[i] not in IB and Hm[i - 1] not in IB)
        swing = sp > 150
        r['hand' + s] = {'default': round(np.mean([h is None for h in Hm]), 2), 'changes_per_bar': round(ch / (hi - lo), 2), 'instant_swaps': inst,
                         'shape_lost_in_view': int(sum(1 for i in range(n) if Hm[i] and vw[i] != 'F')),   # (named shapes in turned views: drawn as the plain hand before rig.js's front-drawing fallback)
                         'default_on_swings': round(np.mean([Hm[i] is None for i in np.flatnonzero(swing)]), 2) if swing.any() else None,
                         'swing_frames': int(swing.sum())}
    out['phrases'].append(r)
# secondary motion against the body
sp = {k: np.array(v, float) for k, v in D['sp'].items()}
hipv = np.hypot(d(P['hipX'] * 140 + P['rootX']), d(P['hipY']))                             # base px/s (pelvis D = 140)
chest = np.array([p if p else [np.nan, np.nan] for p in D['pts'].get('chest', [])], float) if D['pts'].get('chest') else None
chv = np.hypot(d(chest[:, 0]), d(chest[:, 1])) if chest is not None else None
def lag(x, y, maxl=12):
    x = (x - x.mean()) / (x.std() + 1e-9); y = (y - y.mean()) / (y.std() + 1e-9); best = (0, -9)
    for L in range(0, maxl + 1): c = float(np.mean(x[L:] * y[:len(y) - L])); best = max(best, (c, L)) if c > best[0] else best
    return best
out['secondary'] = {}
for k, v in sp.items():
    dv = np.abs(d(v)); c, L = lag(hipv, dv)
    out['secondary'][k] = {'rms': round(float(np.sqrt(np.mean(v ** 2))), 3), 'peak': round(float(np.abs(v).max()), 3), 'corr_with_hip_speed': round(c, 2), 'lag_frames': L}
out['hip_speed_rms'] = round(float(np.sqrt(np.mean(hipv ** 2))), 1)
if chv is not None: out['chest_speed_rms_stagepx'] = round(float(np.sqrt(np.nanmean(chv ** 2))), 1)
json.dump(out, open(opt('--out', os.path.join(os.path.dirname(A[0]), 'dance_metrics.json')), 'w'), indent=1)
# a short table
print(f"held poses (whole span, >=3 samples): {out['held_poses_total']}  top-6 share {out['held_pose_share_top6']}")
print(f"{'phrase':22s} armMC bodyMC poses arm/s  tsd air | L: def chg/bar inst turn dSw | R: def chg/bar inst turn dSw")
for r in out['phrases']:
    f = lambda h: f"{h['default']:.2f} {h['changes_per_bar']:5.2f} {h['instant_swaps']:3d} {h['shape_lost_in_view']:4d} {h['default_on_swings'] if h['default_on_swings'] is not None else '-'}"
    print(f"{r['phrase']:22s} {r['arms_mocap']:.2f}  {r['body_mocap']:.2f}  {r['held_poses']:4d} {r['arm_speed']:5.0f} {r['torso_head_sd']:4.1f} {r['airborne']:3d} | {f(r['handL'])} | {f(r['handR'])}")
print('secondary:', json.dumps(out['secondary']))
