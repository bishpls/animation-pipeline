"""Per-section beat-grid fit and drop onset for SO BACK's takes (the whole-take fit is skewed by the drumless 'over' section).
    .venv/bin/python projects/so-back/song/dropfit.py c1 c2 ..."""
import subprocess, sys, numpy as np, librosa
BPM = 150.0; B = 60 / BPM
def load(p):
    raw = subprocess.run(['ffmpeg', '-v', 'quiet', '-i', p, '-ac', '1', '-ar', '22050', '-f', 'f32le', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.float32), 22050
for t in sys.argv[1:]:
    y, sr = load(f'projects/so-back/assets/takes/{t}.mp3')
    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=256)
    ts = librosa.times_like(env, sr=sr, hop_length=256)
    on = librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=256, units='time')
    def fit(a, b):
        o = on[(on >= a) & (on < b)]
        if len(o) < 4: return None, None
        # best phase on the 150 grid for this section, residual of onsets to nearest beat (eighths allowed)
        best = None
        for ph in np.arange(0, B, 0.002):
            r = (o - ph + B / 4) % (B / 2) - B / 4
            m = np.median(np.abs(r))
            if best is None or m < best[0]: best = (m, ph)
        return best
    # drop onset: first frame after 11.5 s where the 1-s RMS doubles over the previous second
    rms = librosa.feature.rms(y=y, hop_length=256)[0]; rt = librosa.times_like(rms, sr=sr, hop_length=256)
    i0 = np.searchsorted(rt, 11.0); w = int(0.4 / (256 / sr))
    jump = [(rms[i:i + w].mean() / (rms[i - w:i].mean() + 1e-6), rt[i]) for i in range(i0, np.searchsorted(rt, 15.0))]
    j = max(jump)[1]
    # the first strong onset near that
    o_drop = on[np.argmin(np.abs(on - j))]
    s = []
    for a, b in [(0, 3.2), (12.8, 19.2), (19.2, 25.6)]:
        m, ph = fit(a, b); s.append(f'{a:>5}-{b:<5} fit {m*1000:4.0f} ms phase {ph:.3f}' if m is not None else f'{a}-{b} n/a')
    print(f'{t}: drop onset {o_drop:.3f} s ({(o_drop - 12.8) * 1000:+.0f} ms vs 12.8) | ' + ' | '.join(s))
