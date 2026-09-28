"""Contact sheet of spectrograms (full clips): python sheet.py OUT.png key [key ...]"""
import sys, os
import numpy as np, matplotlib, librosa
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
keys = sys.argv[2:]; n = len(keys); cols = 3; rows = (n + cols - 1) // cols
fig, axs = plt.subplots(rows, cols, figsize=(6 * cols, 2.2 * rows))
for ax, k in zip(axs.flat, keys):
    x = load(k)
    S = 20 * np.log10(np.abs(librosa.stft(x, n_fft=256, hop_length=24)) + 1e-9)
    ax.imshow(S, origin='lower', aspect='auto', cmap='magma', extent=(0, len(x) / SR, 0, SR / 2), vmin=S.max() - 70, vmax=S.max() - 5)
    t, e = env_db(x); ax2 = ax.twinx(); ax2.plot(t, e, 'c', lw=.6); ax2.set_ylim(e.max() - 70, e.max() + 5); ax2.set_yticks([])
    ax.set_title(f'{k}: {REG[k]["text"]}', fontsize=8); ax.tick_params(labelsize=6)
for ax in list(axs.flat)[n:]: ax.axis('off')
plt.tight_layout(); plt.savefig(sys.argv[1], dpi=65); plt.close()
