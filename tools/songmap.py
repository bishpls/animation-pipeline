"""Draw a song map: spectrogram + loudness + sections + bars + lyrics, so the song's shape can be *seen*.
    .venv/bin/python tools/songmap.py SONG.wav CUES.json OUT.png [t0 t1]"""
import json, sys
import numpy as np, librosa, librosa.display
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
wav, cues, out = sys.argv[1:4]
c = json.load(open(cues))
t0, t1 = (float(sys.argv[4]), float(sys.argv[5])) if len(sys.argv) > 5 else (0, c['duration'])
y, sr = librosa.load(wav, sr=22050, offset=t0, duration=t1 - t0)
fig, ax = plt.subplots(2, 1, figsize=(max(16, (t1 - t0) / 3), 7), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
S = librosa.amplitude_to_db(np.abs(librosa.stft(y, n_fft=2048, hop_length=256)), ref=np.max)
librosa.display.specshow(S, sr=sr, hop_length=256, x_axis='time', y_axis='log', ax=ax[0], cmap='magma')
ax[0].set_ylim(40, 11000)
rms = np.array(c['rms']); rt = np.arange(len(rms)) * 0.1
m = (rt >= t0) & (rt <= t1)
ax[1].fill_between(rt[m] - t0, rms[m], color='#ff48b0')
for d in c['downbeats']:
    if t0 <= d <= t1:
        for a in ax: a.axvline(d - t0, color='w' if a is ax[0] else 'k', alpha=.25, lw=.6)
for s in c['sections']:
    if t0 <= s['t0'] <= t1:
        for a in ax: a.axvline(s['t0'] - t0, color='#00e0ff', lw=2)
        ax[0].text(s['t0'] - t0 + .1, 9000, s['name'].split(' -')[0], color='#00e0ff', fontsize=10, weight='bold')
for i, w in enumerate(c['words']):
    if t0 <= w['t0'] <= t1:
        ax[1].text(w['t0'] - t0, rms.max() * (0.95 - 0.18 * (i % 4)), w['w'], fontsize=7, rotation=0)
ax[1].set_xlabel(f'seconds from {t0}')
plt.tight_layout(); plt.savefig(out, dpi=90); print('wrote', out)
