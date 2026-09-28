"""Screen song takes against SO BACK's locked skeleton: 150 BPM, a downbeat alignable to 0.05, the drop on bar 9 (12.85 once
aligned), a key the vocals can be re-tuned to, and a harshness proxy for the cold open (share of energy above 4 kHz, spectral
flatness; the current take c4 is the reference Michael called "very harsh").
    .venv/bin/python projects/so-back/song/screen.py c4 e1 e2 ..."""
import subprocess, sys, numpy as np, librosa
BPM = 150.0; B = 60 / BPM; SR = 22050
N = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
def load(t, sr=SR):
    raw = subprocess.run(['ffmpeg', '-v', 'quiet', '-i', f'projects/so-back/assets/takes/{t}.mp3', '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.float32).copy()
def phase(on, a, b):
    o = on[(on >= a) & (on < b)]
    if len(o) < 4: return None, None
    best = min(((np.median(np.abs((o - ph + B / 4) % (B / 2) - B / 4)), ph) for ph in np.arange(0, B, .002)))
    return best
def key(y, a, b):
    yh = librosa.effects.harmonic(y[int(a * SR):int(b * SR)], margin=3)
    v = librosa.feature.chroma_cqt(y=yh, sr=SR).mean(1)
    return max(((np.corrcoef(np.roll(p, k), v)[0, 1], f'{N[k]}{"m" if m else ""}') for p, m in ((MAJ, 0), (MIN, 1)) for k in range(12)))[1]
for t in sys.argv[1:]:
    y = load(t); env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=256)
    on = librosa.onset.onset_detect(onset_envelope=env, sr=SR, hop_length=256, units='time')
    ph = [phase(on, a, b) for a, b in [(0, 3.1), (12.9, 19.2), (19.2, 25.5)]]
    # the drop: the biggest 0.4 s RMS rise after 11.5 s, snapped to the nearest onset
    rms = librosa.feature.rms(y=y, hop_length=256)[0]; rt = librosa.times_like(rms, sr=SR, hop_length=256); w = 35
    i0, i1 = np.searchsorted(rt, 11.5), np.searchsorted(rt, 15.0)
    j = max(range(i0, i1), key=lambda i: rms[i:i + w].mean() / (rms[i - w:i].mean() + 1e-6)); drop = on[np.argmin(np.abs(on - rt[j]))]
    # alignment: the drop's phase (mod a bar) is what must match 12.85; shift needed so drop -> 12.85
    shift = 12.85 - drop
    y44 = load(t, 44100); c = y44[:int(3.0 * 44100)]
    S = np.abs(librosa.stft(c, n_fft=2048)) ** 2; f = librosa.fft_frequencies(sr=44100, n_fft=2048)
    hi = S[f > 4000].sum() / S.sum(); flat = librosa.feature.spectral_flatness(y=c).mean()
    lufs_ish = 10 * np.log10((c ** 2).mean() + 1e-12)
    phs = ' '.join(f'{p[1]:.3f}/{p[0]*1000:.0f}ms' if p[0] is not None else 'n/a' for p in ph)
    print(f'{t}: drop {drop:6.3f} (shift {shift:+.3f})  phases(open/drop/drop2) {phs}  key open {key(y, 0, 3.1)} over {key(y, 3.3, 9.5)} drop {key(y, 12.9, 25.5)}  '
          f'| cold >4k {hi*100:4.1f}%  flat {flat:.3f}  rms {lufs_ish:5.1f} dB')
