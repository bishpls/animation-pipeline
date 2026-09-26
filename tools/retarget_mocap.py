"""Retarget a MediaPipe pose track (tools/posetrack.py) onto the 2D rig's channels (engine/rig.js), time-warped onto the
song's beat grid. Writes channel curves for src/motionlab.js (MOTIONLAB.groove(P, { curves })):
    { src, bar0, bars, fps, warp: {src_dips, target}, curves: { channel: { b: [song bars], v: [values], mode } } }

    .venv/bin/python tools/retarget_mocap.py POSE.json OUT.json --bar0 62 --bars 4 [--bpm 170] [--dip beat|and] [--sheet SHEET.jpg VIDEO.mp4]

Mapping (the rig is a front view; the image plane is what reads):
  - the rig's image-left arm is the dancer's right arm (MediaPipe 12, 14, 16), the image-right arm her left (11, 13, 15): no mirror.
  - armS = the upper arm's outward angle from straight down, minus the rig's rest (29.7 deg: its arms hang along axis +-0.496,
    0.868); elbowS = the forearm's outward angle minus the upper arm's (positive bends the hand up and out; negative across).
  - hipY = the pelvis drop from her standing height (base px, + = down); hipX = the pelvis over the feet (units of the rig's
    pelvis D = 140 base px); bodyZ = the torso's lean (shoulder mid against hip mid, deg, + = the top to image right); bodyX =
    the shoulder line's yaw from world z (/35 deg); head angleZ = the ear line's roll against the shoulder line (deg), angleX =
    the nose against the ears (turn, /30 deg), angleY = the nose's drop against the ears (nod); feet: ankles against their
    standing places (base px; Y = lift, + = up); kneeOut from the knees' lateral splay.
  - scale: the rig's shoulder-to-ankle (1705 base px) over hers.
  - smoothing: Savitzky-Golay (7 frames, order 2) on every channel, after unwrapping angles.
  - time: her own beat is the minima of her hip height (the dips); dip i maps to our beat i from bar0 ('beat'), or to its "and"
    ('and': Clawd rises on the beat, Fable's rule); piecewise linear between dips, the median period beyond them.
"""
import json, sys, os, subprocess
import numpy as np
from scipy.signal import savgol_filter, find_peaks

a = sys.argv[1:]; src, out = a[0], a[1]
opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
BAR0, BARS, BPM, DIP = float(opt('--bar0', 62)), float(opt('--bars', 4)), float(opt('--bpm', 170)), opt('--dip', 'beat')
BT = 60 / BPM; BAR = BT * 4
J = json.load(open(src)); fps = J['fps']; Wd, Hd = J['size']; F = J['frames']; n = len(F)
img = np.array([[[p[0] * Wd, p[1] * Hd] for p in f['img']] for f in F])          # (n, 33, 2) image px
wld = np.array([[p[:3] for p in f['world']] for f in F])                         # (n, 33, 3) metres
img = savgol_filter(img, 7, 2, axis=0); wld = savgol_filter(wld, 7, 2, axis=0)
L = lambda i: img[:, i]
NOSE, EAR_L, EAR_R, SH_L, SH_R, EL_L, EL_R, WR_L, WR_R, HIP_L, HIP_R, KN_L, KN_R, AN_L, AN_R = 0, 7, 8, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28
deg = np.degrees
def outward(v, side):                       # angle of a vector from straight down, positive away from the body (image plane)
    return deg(np.arctan2(-v[:, 0] if side == 'L' else v[:, 0], v[:, 1]))
def wrap(x): return (x + 180) % 360 - 180
REST = 29.7
ch = {}
for sd, (s, e, w) in {'L': (SH_R, EL_R, WR_R), 'R': (SH_L, EL_L, WR_L)}.items():   # rig image-left = her right
    up, fo = L(e) - L(s), L(w) - L(e)
    th, ph = np.unwrap(np.radians(outward(up, sd))), np.unwrap(np.radians(outward(fo, sd)))
    rel = deg(ph - th); rel -= 360 * np.round(np.median(rel) / 360)              # continuous through the crossing (wrapping flips it +-180)
    ch['arm' + sd] = np.clip(deg(th) - REST, -100, 175); ch['elbow' + sd] = np.clip(rel, -320, 320)   # (rig v2: the elbow hinges past 120)
    # the arm's depth by layer order: the wrist well in front of the shoulder plane draws the arm over the face and hair; behind
    # the body plane, under the torso (rig.js armFront/armBack), held at least 3 frames so it doesn't flicker
    dz = wld[:, w, 2] - (wld[:, 11, 2] + wld[:, 12, 2]) / 2
    for key, m in (('armFront' + sd, dz < -.12), ('armBack' + sd, dz > .06)):
        m = m.astype(float); m = np.convolve(m, np.ones(3) / 3, mode='same') > .5; ch[key] = m.astype(float)
shm, hipm, anm = (L(SH_L) + L(SH_R)) / 2, (L(HIP_L) + L(HIP_R)) / 2, (L(AN_L) + L(AN_R)) / 2
scale = 1705 / np.median(anm[:, 1] - shm[:, 1])                                   # base px per image px
stand = np.percentile(hipm[:, 1], 8)                                              # her standing hip height (the highest 8%)
ch['hipY'] = np.clip((hipm[:, 1] - stand) * scale, -40, 170)
ch['hipX'] = np.clip((hipm[:, 0] - anm[:, 0]) * scale / 140, -1.3, 1.3)
tor = shm - hipm; ch['bodyZ'] = np.clip(deg(np.arctan2(tor[:, 0], -tor[:, 1])), -9, 9)
yaw = deg(np.arctan2(wld[:, SH_L, 2] - wld[:, SH_R, 2], wld[:, SH_L, 0] - wld[:, SH_R, 0]))
ch['bodyX'] = np.clip((yaw - np.median(yaw)) / 35, -.7, .7)
earm, ed = (L(EAR_L) + L(EAR_R)) / 2, np.linalg.norm(L(EAR_L) - L(EAR_R), axis=1)
roll_h = deg(np.arctan2(L(EAR_L)[:, 1] - L(EAR_R)[:, 1], L(EAR_L)[:, 0] - L(EAR_R)[:, 0]))
roll_s = deg(np.arctan2(L(SH_L)[:, 1] - L(SH_R)[:, 1], L(SH_L)[:, 0] - L(SH_R)[:, 0]))
ch['angleZ'] = np.clip(wrap(roll_h - roll_s), -14, 14)
nx, ny = (L(NOSE)[:, 0] - earm[:, 0]) / ed, (L(NOSE)[:, 1] - earm[:, 1]) / ed
ch['angleX'] = np.clip(deg(np.arcsin(np.clip(2 * (nx - np.median(nx)), -1, 1))) / 30, -.6, .6)
ch['angleY'] = np.clip((ny - np.median(ny)) * 2.2, -.8, .8)
lift = {}
for sd, i in {'L': AN_R, 'R': AN_L}.items():
    ax = L(i)[:, 0]; ay = L(i)[:, 1]; base_y = np.percentile(ay, 92); base_x = np.median(ax[ay > base_y - 4])
    ch['foot' + sd + 'X'] = np.clip((ax - base_x) * scale, -220, 220); lift[sd] = (base_y - ay) * scale
both = np.minimum(lift['L'], lift['R'])                  # both up together is a rise onto the toes, not a step: one foot stays planted
for sd in 'LR': ch['foot' + sd + 'Y'] = np.clip(lift[sd] - np.maximum(both, 0), 0, 110)
# the feet in 3D: toe direction in the ground plane (toe in/out), and the heel against the toe: planted, a heel pivot (the rig's
# heelS); lifted, a point (footSP)
mpm = 1705 / np.median(np.linalg.norm((wld[:, 11] + wld[:, 12]) / 2 - (wld[:, 27] + wld[:, 28]) / 2, axis=1))   # base px per metre
for sd, (hl, ti) in {'L': (30, 32), 'R': (29, 31)}.items():
    yaw = deg(np.arctan2(wld[:, ti, 0] - wld[:, hl, 0], wld[:, hl, 2] - wld[:, ti, 2])); yaw = (yaw - np.median(yaw)) * (-1 if sd == 'L' else 1)
    yaw = savgol_filter(yaw, 15, 2) * .5; yaw = np.sign(yaw) * np.maximum(0, np.abs(yaw) - 4)   # (the foot's depth is MediaPipe's noisiest: sustained turns only)
    up = wld[:, ti, 1] - wld[:, hl, 1]; up = up - np.median(up)                  # m; + = the heel higher than usual against the toe
    lifted = ch['foot' + sd + 'Y'] > 8
    ch['foot' + sd + 'R'] = yaw; ch['heel' + sd] = np.where(lifted, 0, up * mpm * 1.4); ch['foot' + sd + 'P'] = np.where(lifted, up / .06, 0)
splay = ((L(KN_L)[:, 0] - L(KN_R)[:, 0]) - (L(AN_L)[:, 0] - L(AN_R)[:, 0])) / ed
ch['kneeOut'] = np.clip(.5 + 1.2 * (splay - np.median(splay)), 0, 1)
LIM = {'armFront': (0, 1), 'armBack': (0, 1), 'arm': (-100, 175), 'elbow': (-320, 320), 'hipY': (-40, 170), 'hipX': (-1.3, 1.3), 'bodyZ': (-12, 12), 'bodyX': (-.9, .9),
       'angleZ': (-14, 14), 'angleX': (-.7, .7), 'angleY': (-.8, .8), 'footLX': (-220, 220), 'footRX': (-220, 220), 'footLY': (0, 110), 'footRY': (0, 110),
       'footLR': (-30, 35), 'footRR': (-30, 35), 'footLP': (-1, 1), 'footRP': (-1, 1), 'heelL': (0, 70), 'heelR': (0, 70), 'kneeOut': (.38, 1)}   # (knees no further in than a touch: knock-kneed reads wrong on her)
for k in ch:
    if k.startswith('armFront') or k.startswith('armBack'): continue
    lo, hi = next(v for kk, v in LIM.items() if k.startswith(kk)); ch[k] = np.clip(savgol_filter(ch[k], 7, 2), lo, hi)   # (re-clamped: the filter overshoots)
# contact: a planted foot holds its place (the source's ~1 px tracking jitter, x3 into base px, read as sliding); each planted run
# takes its median, and the swing between runs is eased from one to the next
for sd in 'LR':
    x, y = ch['foot' + sd + 'X'], ch['foot' + sd + 'Y']; pl = y < 4; x2 = x.copy(); i = 0
    runs = []
    while i < n:
        if pl[i]:
            j = i
            while j < n and pl[j]: j += 1
            runs.append((i, j)); x2[i:j] = np.median(x[i:j]); i = j
        else: i += 1
    for (a0, a1), (b0, b1) in zip(runs, runs[1:]):                     # the swing: ease between the two planted places
        u = np.linspace(0, 1, b0 - a1 + 2)[1:-1]; x2[a1:b0] = x2[a1 - 1] + (x2[b0] - x2[a1 - 1]) * (u * u * (3 - 2 * u))
    ch['foot' + sd + 'X'] = x2

# ---- her beat: the dips of her hip (image y maxima), and the warp onto ours
ts = np.arange(n) / fps
hy = hipm[:, 1]; pk, _ = find_peaks(hy, distance=int(.6 * fps * BT), prominence=np.ptp(hy) * .12)
dips = ts[pk]; per = np.median(np.diff(dips)) if len(dips) > 1 else BT
print(f'her dips: {len(dips)}, median period {per:.3f} s ({60 / per:.1f} bpm); ours {BT:.3f} s')
# her beat index per dip (a dip may be skipped: count periods), then onto ours
idx = np.round((dips - dips[0]) / per).astype(int)
T0 = BAR0 * BAR + (BT / 2 if DIP == 'and' else 0)
tgt = T0 + idx * BT
def warp(s):                                    # source time -> song time
    if s <= dips[0]: return tgt[0] - (dips[0] - s) * BT / per
    if s >= dips[-1]: return tgt[-1] + (s - dips[-1]) * BT / per
    j = np.searchsorted(dips, s); return tgt[j - 1] + (s - dips[j - 1]) * (tgt[j] - tgt[j - 1]) / (dips[j] - dips[j - 1])
song = np.array([warp(s) for s in ts])
# resample every channel on the target grid (24 fps, bars bar0..bar0+bars)
grid = np.arange(BAR0 * BAR, (BAR0 + BARS) * BAR, 1 / 24)
src_of = np.interp(grid, song, ts)                                              # song time -> source time
# --anchors 'src:bar,...' (structural warp: her event onsets onto the song's; the dip warp can't match a dance whose accents sit
# on a different subdivision than the song's calls) and --tail 's0:s1:b0:b1' (a segment of hers reused for bars she didn't dance)
if '--anchors' in a:
    A = np.array([[float(x) for x in p_.split(':')] for p_ in opt('--anchors').split(',')])
    src_of = np.interp(grid / BAR, A[:, 1], A[:, 0])
    if '--tail' in a:
        s0, s1, b0, b1 = [float(x) for x in opt('--tail').split(':')]; m = grid / BAR >= b0
        src_of[m] = s0 + (grid[m] / BAR - b0) / (b1 - b0) * (s1 - s0)
    DIP = 'anchors'
vals = {k: np.interp(src_of, ts, v) for k, v in ch.items()}
for j in np.flatnonzero(np.diff(src_of) < 0) + 1:                 # a splice (the reused tail): crossfade over 8 frames, not a pop
    a0, a1 = max(0, j - 4), min(len(grid) - 1, j + 4)
    for k, v in vals.items(): v[a0:a1 + 1] = np.linspace(v[a0], v[a1], a1 - a0 + 1)
curves = {k: {'b': [round(g / BAR, 5) for g in grid], 'v': [round(float(x), 4) for x in vals[k]], 'mode': 'set'} for k in ch}
json.dump({'src': os.path.basename(src), 'bar0': BAR0, 'bars': BARS, 'fps': 24, 'dip_on': DIP, 'scale': round(float(scale), 3),
           'warp': {'src_dips': [round(float(d), 4) for d in dips], 'target': [round(float(x), 4) for x in tgt]},
           'src_time': [round(float(x), 4) for x in src_of], 'grid_t': [round(float(g), 4) for g in grid], 'curves': curves},
          open(out, 'w'))
print('wrote', out, {k: (round(float(np.min(v)), 2), round(float(np.max(v)), 2)) for k, v in ch.items()})

# the reference panel: the source video (with its skeleton) as one sprite sheet, cols x rows, for the lab's third panel
if '--sheet' in a:
    sheet, video = a[a.index('--sheet') + 1], a[a.index('--sheet') + 2]
    import tempfile
    from PIL import Image
    d = tempfile.mkdtemp(); subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', video, '-vf', 'scale=270:480', f'{d}/f%04d.jpg'], check=True)
    fr = sorted(os.listdir(d)); cols = 11; rows = (len(fr) + cols - 1) // cols
    S = Image.new('RGB', (270 * cols, 480 * rows))
    for i, f in enumerate(fr): S.paste(Image.open(f'{d}/{f}'), ((i % cols) * 270, (i // cols) * 480))
    S.save(sheet, quality=85); print('sheet', sheet, len(fr), 'frames', cols, 'x', rows)
