"""Robust F0 for the (processed, reverberant) announcer voice: harmonic-sum with half-harmonic penalty + Viterbi.
Validated by hand against harmonic-level checks (octave errors are the failure mode of ac/pyin on this voice)."""
import numpy as np, soundfile as sf

def hf0(x, sr, hop=0.005, win=0.04, fmin=140, fmax=480, nh=6, voice_thr=4.0):
    n = int(win * sr); h = int(hop * sr); nfft = 16384
    w = np.hanning(n)
    cands = np.exp(np.linspace(np.log(fmin), np.log(fmax), 160))
    freqs = np.fft.rfftfreq(nfft, 1 / sr)
    T = max(1, 1 + (len(x) - n) // h)
    S = np.full((T, len(cands)), -1e9); energy = np.zeros(T)
    for i in range(T):
        s = x[i * h:i * h + n]
        if len(s) < n: s = np.pad(s, (0, n - len(s)))
        s = (s - s.mean()) * w
        energy[i] = np.sqrt(np.mean(s ** 2))
        X = np.abs(np.fft.rfft(s, nfft)); L = np.log(X + 1e-7)
        def at(f):
            idx = np.clip((f / (sr / nfft)).astype(int), 1, len(L) - 2)
            return np.maximum(np.maximum(L[idx - 1], L[idx]), L[idx + 1])
        sc = np.zeros(len(cands))
        for k in range(1, nh + 1):
            wk = 1.0 / k ** 0.5
            sc += wk * (at(k * cands) - at((k - 0.5) * cands))
        S[i] = sc
    # Viterbi with log-frequency jump penalty
    lc = np.log2(cands)
    trans = -8.0 * np.abs(lc[:, None] - lc[None, :]) ** 1.0
    D = S[0].copy(); B = np.zeros((T, len(cands)), int)
    for i in range(1, T):
        M = D[:, None] + trans
        B[i] = M.argmax(0); D = M.max(0) + S[i]
    path = np.zeros(T, int); path[-1] = D.argmax()
    for i in range(T - 1, 0, -1): path[i - 1] = B[i, path[i]]
    f0 = cands[path]; score = S[np.arange(T), path]
    t = (np.arange(T) * h + n / 2) / sr
    voiced = (score > voice_thr) & (energy > 0.02 * energy.max())
    return t, f0, score, voiced

if __name__ == '__main__':
    import sys
    for p in sys.argv[1:]:
        x, sr = sf.read(p)
        t, f0, sc, v = hf0(x, sr, hop=0.01)
        print(f'{p.split("/")[-1][:-4]:11s}', ' '.join(f'{f:3.0f}' if vv else '  .' for f, vv in zip(f0, v)))
