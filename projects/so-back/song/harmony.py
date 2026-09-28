"""Key and per-bar chord/melody estimate for a take (for tuning the announcer vocals onto it).
    .venv/bin/python projects/so-back/song/harmony.py TAKE [offset]"""
import subprocess, sys, numpy as np, librosa
t = sys.argv[1]; OFF = float(sys.argv[2]) if len(sys.argv) > 2 else 0.05
raw = subprocess.run(['ffmpeg', '-v', 'quiet', '-i', f'projects/so-back/assets/takes/{t}.mp3', '-ac', '1', '-ar', '22050', '-f', 'f32le', '-'],
                     capture_output=True).stdout
y = np.frombuffer(raw, np.float32).copy(); sr = 22050
yh = librosa.effects.harmonic(y, margin=3)
C = librosa.feature.chroma_cqt(y=yh, sr=sr, hop_length=512, bins_per_octave=36)
ts = librosa.times_like(C, sr=sr, hop_length=512)
N = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
maj = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
mnr = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
def key(v):
    best = max(((np.corrcoef(np.roll(p, k), v)[0, 1], f'{N[k]} {m}') for p, m in ((maj, 'major'), (mnr, 'minor')) for k in range(12)))
    return best
for name, a, b in [('cold open', 0, 3.2), ('over', 3.2, 9.6), ('turn', 9.6, 12.8), ('drop', 12.8, 19.2), ('drop2', 19.2, 25.6), ('all', 0, 28)]:
    m = (ts >= a) & (ts < b); v = C[:, m].mean(1); r, k = key(v)
    print(f'{name:9s} {k:9s} r={r:.2f}  top: ' + ' '.join(N[i] for i in np.argsort(-v)[:4]))
# per bar: chord template match (major/minor triads)
tri = {}
for k in range(12):
    for q, iv in (('', (0, 4, 7)), ('m', (0, 3, 7))):
        v = np.zeros(12); v[[(k + i) % 12 for i in iv]] = 1; tri[N[k] + q] = v
bar = 1.6; i = 0; line = []
tb = OFF
while tb + bar <= 28:
    m = (ts >= tb) & (ts < tb + bar); v = C[:, m].mean(1); v = v / (np.linalg.norm(v) + 1e-9)
    best = max(tri, key=lambda c: tri[c] @ v / np.linalg.norm(tri[c]))
    line.append(f'{i+1}@{tb:.2f}:{best}'); tb += bar; i += 1
print(' '.join(line))
# the over section's melody: dominant pitch class per eighth in 3.2-9.6 from the high band
S = np.abs(librosa.cqt(yh, sr=sr, hop_length=256, fmin=librosa.note_to_hz('C4'), n_bins=36))
tq = librosa.times_like(S, sr=sr, hop_length=256)
mel = []
for tb in np.arange(3.25, 9.6, 0.2):
    m = (tq >= tb) & (tq < tb + 0.2); v = S[:, m].mean(1)
    mel.append(librosa.midi_to_note(librosa.note_to_midi('C4') + int(np.argmax(v))) if v.max() > 0.02 else '.')
print('over melody (eighths):', ' '.join(mel))
