"""songscreen: screen generated song takes by measurement before anyone listens. Promoted from SO BACK.

Per take, it prints:
- the grid phase and fit per section (eighth-note tolerance), so a take whose sections drift or re-phase shows up;
- the drop onset: the biggest RMS rise in a window, snapped to an onset. It often catches a pickup: confirm with
  tools/songseat.py --probe;
- the key per section (Krumhansl profiles on harmonic chroma), for vocals already tuned to a key;
- a harshness proxy for a window (the share of energy above 4 kHz, spectral flatness, RMS), which on SO BACK tracked the
  director's "very harsh".

    .venv/bin/python tools/songscreen.py TAKE.mp3 ... --bpm 150 --phase open:0-3.1,drop:12.9-19.2
        [--drop-window 11.5-15] [--keys over:3.3-9.5,drop:12.9-25.5] [--harsh 0-3]

Use it to shortlist takes; choose among the shortlist by ear (in context, with the vocals).
"""
import argparse, subprocess
import numpy as np, librosa
SR = 22050
N = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def load(path, sr=SR):
    raw = subprocess.run(['ffmpeg', '-v', 'quiet', '-i', path, '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def spans(s):
    out = []
    for part in (s or '').split(','):
        if not part: continue
        name, rng = part.split(':'); a, b = rng.split('-'); out.append((name, float(a), float(b)))
    return out


def phase(on, a, b, beat):
    o = on[(on >= a) & (on < b)]
    if len(o) < 4: return None
    return min(((np.median(np.abs((o - ph + beat / 4) % (beat / 2) - beat / 4)), ph) for ph in np.arange(0, beat, .002)))


def key(y, a, b):
    yh = librosa.effects.harmonic(y[int(a * SR):int(b * SR)], margin=3)
    v = librosa.feature.chroma_cqt(y=yh, sr=SR).mean(1)
    return max(((np.corrcoef(np.roll(p, k), v)[0, 1], f'{N[k]}{"m" if m else ""}') for p, m in ((MAJ, 0), (MIN, 1)) for k in range(12)))[1]


def screen(path, bpm, phases, drop_window, keys, harsh):
    beat = 60 / bpm; y = load(path)
    env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=256)
    on = librosa.onset.onset_detect(onset_envelope=env, sr=SR, hop_length=256, units='time')
    parts = []
    for name, a, b in phases:
        p = phase(on, a, b, beat); parts.append(f'{name} {p[1]:.3f}/{p[0] * 1000:.0f}ms' if p else f'{name} n/a')
    if drop_window:
        rms = librosa.feature.rms(y=y, hop_length=256)[0]; rt = librosa.times_like(rms, sr=SR, hop_length=256); w = 35
        i0, i1 = np.searchsorted(rt, drop_window[0]), np.searchsorted(rt, drop_window[1])
        j = max(range(max(i0, w), i1), key=lambda i: rms[i:i + w].mean() / (rms[i - w:i].mean() + 1e-6))
        parts.append(f'drop ~{on[np.argmin(np.abs(on - rt[j]))]:.3f}')
    for name, a, b in keys: parts.append(f'key {name} {key(y, a, b)}')
    if harsh:
        y44 = load(path, 44100); c = y44[int(harsh[0] * 44100):int(harsh[1] * 44100)]
        S = np.abs(librosa.stft(c, n_fft=2048)) ** 2; f = librosa.fft_frequencies(sr=44100, n_fft=2048)
        parts.append(f'>4k {S[f > 4000].sum() / S.sum() * 100:.1f}%  flat {librosa.feature.spectral_flatness(y=c).mean():.3f}  '
                     f'rms {10 * np.log10((c ** 2).mean() + 1e-12):.1f} dB')
    return ' | '.join(parts)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('takes', nargs='+'); ap.add_argument('--bpm', type=float, required=True)
    ap.add_argument('--phase', default=''); ap.add_argument('--drop-window', default=''); ap.add_argument('--keys', default='')
    ap.add_argument('--harsh', default='')
    a = ap.parse_args()
    dw = tuple(map(float, a.drop_window.split('-'))) if a.drop_window else None
    hw = tuple(map(float, a.harsh.split('-'))) if a.harsh else None
    for t in a.takes: print(f'{t}: {screen(t, a.bpm, spans(a.phase), dw, spans(a.keys), hw)}')
