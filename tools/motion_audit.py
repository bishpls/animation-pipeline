"""Measure a rig choreography against motion-design principles (MOTION.md): stillness, velocity and acceleration, arcs,
overlap (successive breaking), accents against the beat grid and the drum hits, secondary motion, and energy against the
song. Input: a MOTIONLAB.dump() and the song.

    node engine/render.mjs projects/tsuzuku --eval='MOTIONLAB.dump(45, 93, 24)' > projects/tsuzuku/board/motion/dump.json
    .venv/bin/python tools/motion_audit.py projects/tsuzuku/board/motion/dump.json projects/tsuzuku/assets/song.mp3 [--out DIR]

Writes DIR/metrics.json and DIR/*.png (default: the dump's folder).
"""
import json, os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import librosa
from scipy.signal import find_peaks, correlate

a = sys.argv[1:]; dump_path, song = a[0], a[1]
OUT = a[a.index('--out') + 1] if '--out' in a else os.path.dirname(os.path.abspath(dump_path))
D = json.load(open(dump_path)); fps = D['fps']; BAR = D['bar']; BT = BAR / 4
t = np.array(D['t']); b = t / BAR; n = len(t)
SECT = [('intro', 45, 46), ('chorus 1', 46, 62), ('hook', 62, 66), ('verse 2', 66, 82), ('chorus 2', 82, 90), ('breakdown', 90, 93)]
C = {'blue': '#2a78d6', 'orange': '#eb6834', 'aqua': '#1baf7a', 'yellow': '#eda100', 'magenta': '#e87ba4', 'green': '#008300', 'ink': '#1f1f1e', 'muted': '#8a8980'}
plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.edgecolor': '#c3c2b7', 'axes.labelcolor': C['ink'],
                     'xtick.color': C['muted'], 'ytick.color': C['muted'], 'grid.color': '#ecebe4', 'axes.grid': True, 'figure.dpi': 110})
def shade(ax):
    for i, (nm, b0, b1) in enumerate(SECT):
        if i % 2: ax.axvspan(b0, b1, color='#f3f2ec', zorder=0)
        ax.text((b0 + b1) / 2, 1.01, nm, transform=ax.get_xaxis_transform(), ha='center', va='bottom', fontsize=7, color=C['muted'])

M = {}
# ---- points (stage px; she's ~1000 px tall at s .27) -> velocity (px/s), acceleration
PT = {k: np.array([p if p else [np.nan, np.nan] for p in v], float) for k, v in D['pts'].items()}
vel = {k: np.gradient(v, axis=0) * fps for k, v in PT.items()}
spd = {k: np.linalg.norm(v, axis=1) for k, v in vel.items()}
acc = {k: np.linalg.norm(np.gradient(vel[k], axis=0) * fps, axis=1) for k in PT}
major = ['hand_L', 'hand_R', 'face', 'chest', 'waistband', 'boot_L', 'boot_R']
body = sum(np.nan_to_num(spd[k]) for k in major)

# 1. stillness: every major point slower than 30 px/s (about 3% of her height per second)
still = np.all([np.nan_to_num(spd[k]) < 30 for k in major], axis=0)
runs, r = [], 0
for s_ in still:
    if s_: r += 1
    else:
        if r: runs.append(r)
        r = 0
if r: runs.append(r)
core_still = np.all([np.nan_to_num(spd[k]) < 30 for k in ['face', 'chest', 'waistband']], axis=0)
M['stillness'] = {'all_major_still_pct': round(100 * still.mean(), 1), 'core_still_pct': round(100 * core_still.mean(), 1),
                  'longest_still_s': round(max(runs or [0]) / fps, 2),
                  'by_section_core_still_pct': {nm: round(100 * core_still[(b >= b0) & (b < b1)].mean(), 1) for nm, b0, b1 in SECT}}

# 2. speed and snaps
def frame_jump(k): return np.nan_to_num(np.linalg.norm(np.diff(PT[k], axis=0), axis=1))
M['speed_px_s'] = {k: {'median': round(float(np.nanmedian(spd[k])), 1), 'p95': round(float(np.nanpercentile(spd[k], 95)), 1)} for k in major}
M['snaps'] = {k: {'max_px_per_frame': round(float(frame_jump(k).max()), 1), 'frames_over_25px': int((frame_jump(k) > 25).sum()),
                  'worst_bar': round(float(b[1:][frame_jump(k).argmax()]), 2)} for k in major}
hb = (b >= 58) & (b < 61.5)
M['hip_sway_58_61'] = {'waistband_max_px_per_frame': round(float(frame_jump('waistband')[hb[1:]].max()), 1),
                       'hipX_max_step_per_frame': round(float(np.abs(np.diff(np.array(D['P']['hipX'])))[hb[1:]].max()), 3)}
# ratio of the core's motion to the hands' (a lively body moves from the core; arms-only dancing reads stiff)
core = np.nan_to_num(spd['chest']) + np.nan_to_num(spd['waistband'])
hands = np.nan_to_num(spd['hand_L']) + np.nan_to_num(spd['hand_R'])
M['core_to_hands_motion'] = round(float(core.sum() / hands.sum()), 3)
# the core's range: pelvis and chest excursion (px) and the head's
M['core_range_px'] = {k: {'x': round(float(np.nanpercentile(PT[k][:, 0], 95) - np.nanpercentile(PT[k][:, 0], 5)), 1),
                          'y': round(float(np.nanpercentile(PT[k][:, 1], 95) - np.nanpercentile(PT[k][:, 1], 5)), 1)} for k in ['waistband', 'chest', 'face']}

# 3. arcs: hand-path straightness over each half-beat window while the hand is moving (1 = a straight line)
arcs = []
for k in ['hand_L', 'hand_R']:
    w = int(round(BT * fps / 2 * 2))                       # one beat
    for i in range(0, n - w, w // 2):
        seg = PT[k][i:i + w]; L = np.nansum(np.linalg.norm(np.diff(seg, axis=0), axis=1)); ch = np.linalg.norm(seg[-1] - seg[0])
        if L > 40: arcs.append(ch / L)
arcs = np.array(arcs)
M['hand_arcs'] = {'moving_windows': int(len(arcs)), 'median_straightness': round(float(np.median(arcs)), 3),
                  'pct_near_straight_gt_0.97': round(100 * float((arcs > .97).mean()), 1)}

# 4. overlap / successive breaking: lag of chest and face behind the pelvis (horizontal velocity), and hands behind chest
def lag(a_, b_, maxlag=12):
    a_ = np.nan_to_num(a_ - np.nanmean(a_)); b_ = np.nan_to_num(b_ - np.nanmean(b_))
    cc = correlate(b_, a_, mode='full'); lags = np.arange(-len(a_) + 1, len(a_)); m = np.abs(lags) <= maxlag
    j = np.argmax(np.abs(cc[m])); k = lags[m][j]; r_ = cc[m][j] / (np.linalg.norm(a_) * np.linalg.norm(b_) + 1e-9)   # (anti-phase counts: r < 0)
    return int(k), round(float(r_), 3)
vx = {k: vel[k][:, 0] for k in PT}; vy = {k: vel[k][:, 1] for k in PT}
M['overlap_lag_frames'] = {'chest_after_pelvis_x': lag(vx['waistband'], vx['chest']), 'face_after_chest_x': lag(vx['chest'], vx['face']),
                           'face_after_pelvis_y': lag(vy['waistband'], vy['face']), 'handL_after_chest_x': lag(vx['chest'], vx['hand_L']),
                           'bun_after_face_y': lag(vy['face'], vy['bun_L']),
                           # relative offsets: the chest's motion on the pelvis, the face's on the chest (successive breaking lives here;
                           # the positions above are dominated by the pelvis carrying everything)
                           'chest_rel_after_pelvis_x': lag(vx['waistband'], vx['chest'] - vx['waistband']),
                           'face_rel_after_chest_x': lag(vx['chest'] - vx['waistband'], vx['face'] - vx['chest'])}

# 5. accents: the audio's percussive hits (kick, snare/clap) vs the grid, and the motion's hits vs both
y, sr = librosa.load(song, sr=22050, mono=True, offset=float(t[0]) - 1, duration=float(t[-1] - t[0]) + 2); off = float(t[0]) - 1
yp = librosa.effects.percussive(y)
S_ = np.abs(librosa.stft(yp, n_fft=1024, hop_length=256)); fr = librosa.fft_frequencies(sr=sr, n_fft=1024); hop_t = 256 / sr
def band_onsets(lo, hi, h=.35):
    e = S_[(fr >= lo) & (fr < hi)].sum(0); d = np.maximum(0, np.diff(e, prepend=e[0])); d = d / (d.max() + 1e-9)
    pk, _ = find_peaks(d, height=h, distance=int(.12 / hop_t)); return off + pk * hop_t
kick, snare = band_onsets(30, 150), band_onsets(1000, 8000, .18)
grid = np.arange(np.ceil(t[0] / BT), np.floor(t[-1] / BT)) * BT
def offs(ev, ref, lim=.18):
    o = np.array([e - ref[np.argmin(np.abs(ref - e))] for e in ev]); return o[np.abs(o) < lim]
ko, so_ = offs(kick, grid), offs(snare, grid)
M['audio_vs_grid_ms'] = {'kick_median': round(1000 * float(np.median(ko)), 1), 'snare_median': round(1000 * float(np.median(so_)), 1), 'n_kick': int(len(kick)), 'n_snare': int(len(snare))}
# motion hits: sharp decelerations of the whole body (a pose arriving), and the bounce's peaks (hipY), vs grid and drums
dS = np.gradient(body) * fps; pk, _ = find_peaks(-dS, height=np.percentile(-dS, 90), distance=int(fps * BT * .6)); hits = t[pk]
drums = np.sort(np.concatenate([kick, snare]))
mo_g, mo_d = offs(hits, grid), offs(hits, drums)
M['motion_hits_ms'] = {'n': int(len(hits)), 'vs_grid_median': round(1000 * float(np.median(mo_g)), 1), 'vs_grid_spread_iqr': round(1000 * float(np.subtract(*np.percentile(mo_g, [75, 25]))), 1),
                       'vs_drums_median': round(1000 * float(np.median(mo_d)), 1), 'pct_within_1_frame_of_a_drum': round(100 * float((np.abs(mo_d) <= 1 / fps).mean()), 1)}
strong = drums[np.isin(np.round(drums, 3), np.round(drums, 3))]
M['drums_answered_pct'] = round(100 * float(np.mean([np.any(np.abs(hits - d) <= 1.5 / fps) for d in drums])), 1)
# the bounce: where hipY peaks (up on the toes) land against the beat
hy = np.array(D['P']['hipY']); hpk, _ = find_peaks(-hy, distance=int(fps * BT * .6), prominence=2)
ph = ((t[hpk] / BT) % 1); M['bounce_peak_phase_median'] = round(float(np.median(ph)), 3)

# 6. secondary motion
M['secondary_abs_p95'] = {k: round(float(np.percentile(np.abs(v), 95)), 2) for k, v in D['sp'].items()}
M['secondary_by_section_p95'] = {k: {nm: round(float(np.percentile(np.abs(np.array(v))[(b >= b0) & (b < b1)], 95)), 2) for nm, b0, b1 in SECT} for k, v in D['sp'].items()}

# 7. energy per bar vs the song (rms), correlation
bars = np.arange(45, 93); e_m = np.array([body[(b >= k) & (b < k + 1)].mean() for k in bars])
rms = librosa.feature.rms(y=y, hop_length=512)[0]; rt = off + np.arange(len(rms)) * 512 / sr
e_a = np.array([rms[(rt / BAR >= k) & (rt / BAR < k + 1)].mean() for k in bars])
M['energy_corr_bar'] = round(float(np.corrcoef(e_m, e_a)[0, 1]), 3)
M['energy_per_bar_cv'] = round(float(e_m.std() / e_m.mean()), 3)

json.dump(M, open(os.path.join(OUT, 'metrics.json'), 'w'), indent=1); print(json.dumps(M, indent=1))

# ---- plots
fig, ax = plt.subplots(figsize=(11, 3.2)); shade(ax)
ax.plot(bars + .5, e_m / e_m.max(), color=C['blue'], lw=2, label='motion energy (body speed)')
ax.plot(bars + .5, e_a / e_a.max(), color=C['orange'], lw=2, label='song loudness (rms)')
ax.set_xlabel('song bar'); ax.set_ylabel('normalised per bar'); ax.legend(frameon=False, loc='lower left'); ax.set_xlim(45, 93)
ax.set_title(f'Motion energy against the song (r = {M["energy_corr_bar"]})', loc='left', fontsize=10); fig.tight_layout(); fig.savefig(os.path.join(OUT, 'energy_vs_song.png')); plt.close(fig)

fig, axs = plt.subplots(3, 1, figsize=(11, 7), sharex=True)
for ax, ks, ttl in zip(axs, [['waistband', 'chest', 'face'], ['hand_L', 'hand_R'], ['boot_L', 'boot_R']], ['core (pelvis, chest, face)', 'hands', 'feet']):
    shade(ax)
    for k, c in zip(ks, [C['blue'], C['orange'], C['aqua']]): ax.plot(b, spd[k], color=c, lw=1, label=k)
    ax.set_ylabel('px/s'); ax.set_title(ttl, loc='left', fontsize=9); ax.legend(frameon=False, ncol=3, loc='upper right', fontsize=7)
axs[-1].set_xlabel('song bar'); axs[0].set_xlim(45, 93); fig.tight_layout(); fig.savefig(os.path.join(OUT, 'speeds.png')); plt.close(fig)

fig, axs = plt.subplots(1, 2, figsize=(10, 3.2))
for ax, (o, nm) in zip(axs, [(mo_g, 'motion hits vs the beat grid'), (mo_d, 'motion hits vs the nearest drum hit')]):
    ax.hist(1000 * o, bins=np.arange(-180, 181, 1000 / fps), color=C['blue']); ax.axvline(0, color=C['ink'], lw=1)
    ax.set_xlabel('ms (negative: motion early)'); ax.set_ylabel('hits'); ax.set_title(nm, loc='left', fontsize=9)
fig.tight_layout(); fig.savefig(os.path.join(OUT, 'accents.png')); plt.close(fig)

fig, ax = plt.subplots(figsize=(11, 2.6)); shade(ax)
ax.fill_between(b, 0, core_still.astype(float), step='mid', color=C['blue'], alpha=.8, label='core still (pelvis, chest, face < 30 px/s)')
ax.set_yticks([]); ax.set_xlim(45, 93); ax.set_xlabel('song bar'); ax.legend(frameon=False, loc='upper right', fontsize=7)
ax.set_title(f'Stillness: core still {M["stillness"]["core_still_pct"]}% of frames', loc='left', fontsize=10); fig.tight_layout(); fig.savefig(os.path.join(OUT, 'stillness.png')); plt.close(fig)

fig, axs = plt.subplots(1, 4, figsize=(12, 3.4))
for ax, (b0, nm) in zip(axs, [(47, 'chorus 1 (47-49)'), (62, 'hook (62-64)'), (79.6, 'verse 2 walk (79.6-81.6)'), (86, 'chorus 2 (86-88)')]):
    m_ = (b >= b0) & (b < b0 + 2)
    for k, c in [('hand_L', C['blue']), ('hand_R', C['orange']), ('face', C['aqua']), ('waistband', C['magenta'])]:
        ax.plot(PT[k][m_, 0], PT[k][m_, 1], color=c, lw=1.2, label=k)
    ax.invert_yaxis(); ax.set_aspect('equal'); ax.set_title(nm, loc='left', fontsize=9); ax.tick_params(labelsize=6)
axs[0].legend(frameon=False, fontsize=6, loc='lower left'); fig.suptitle('Paths over two bars (stage px): arcs, and how far the core travels', x=.01, ha='left', fontsize=10)
fig.tight_layout(); fig.savefig(os.path.join(OUT, 'paths.png')); plt.close(fig)

fig, ax = plt.subplots(figsize=(11, 3)); shade(ax)
for k, c in zip(D['sp'], [C['blue'], C['orange'], C['aqua'], C['yellow'], C['magenta']]): ax.plot(b, D['sp'][k], color=c, lw=1, label=k)
ax.set_xlim(45, 93); ax.set_xlabel('song bar'); ax.set_ylabel('spring lag x gain'); ax.legend(frameon=False, ncol=5, fontsize=7, loc='upper right')
ax.set_title('Secondary motion (the rig springs)', loc='left', fontsize=10); fig.tight_layout(); fig.savefig(os.path.join(OUT, 'secondary.png')); plt.close(fig)
