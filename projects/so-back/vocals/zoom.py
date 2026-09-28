"""Zoomed spectrogram of source spans: python zoom.py OUT.png key:t0:t1 [key:t0:t1 ...] (stacked rows, 10 ms grid)."""
import sys, os
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from hf0 import hf0
out = sys.argv[1]; specs = sys.argv[2:]
fig, axs = plt.subplots(len(specs) * 2, 1, figsize=(13, 3.3 * len(specs)), gridspec_kw=dict(height_ratios=[3, 1] * len(specs)))
for i, sp in enumerate(specs):
    k, a, b = sp.split(':'); a, b = float(a), float(b)
    x = load(k); y = x[int(a * SR):int(b * SR)]
    ax = axs[2 * i]
    import librosa
    S = 20 * np.log10(np.abs(librosa.stft(y, n_fft=256, hop_length=12, win_length=144)) + 1e-9)
    ax.imshow(S, origin='lower', aspect='auto', cmap='magma', extent=(a, b, 0, SR / 2), vmin=S.max() - 65, vmax=S.max() - 5)
    ax.set_xlim(a, b); ax.set_ylim(0, 6000); ax.set_title(f'{k} {REG[k]["text"]}  {a}-{b}', fontsize=9)
    ax.set_xticks(np.arange(np.ceil(a * 20) / 20, b, 0.05)); ax.set_xticks(np.arange(np.ceil(a * 100) / 100, b, 0.01), minor=True)
    ax.grid(True, which='minor', axis='x', alpha=.2, color='w'); ax.grid(True, which='major', axis='x', alpha=.6, color='w')
    t, e = env_db(y, SR, win=0.006, hop=0.001)
    tt, f, sc, v = hf0(y, SR, hop=0.005, fmin=85, fmax=480)
    a2 = axs[2 * i + 1]; a2.plot(a + t, e, lw=.7, color='k'); a2.set_xlim(a, b); a2.set_ylim(e.max() - 45, e.max() + 2)
    a3 = a2.twinx(); a3.plot(a + tt[v], f[v], '.', ms=2, color='r'); a3.set_ylim(80, 480)
    a2.set_xticks(np.arange(np.ceil(a * 20) / 20, b, 0.05)); a2.grid(True, axis='x', alpha=.4)
plt.tight_layout(); plt.savefig(out, dpi=70); plt.close()
