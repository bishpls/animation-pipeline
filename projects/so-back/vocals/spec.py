"""Spectrogram + level + F0 + phone boundaries of a clip or a built phrase: my eyes, since I can't listen."""
import sys, os
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from hf0 import hf0

def plot(x, sr, path, title='', marks=(), spans=(), fmax=6000):
    fig, ax = plt.subplots(3, 1, figsize=(max(8, len(x) / sr * 7), 7), sharex=True,
                           gridspec_kw=dict(height_ratios=[3, 1, 1.2]))
    n = 256 if sr <= 16000 else 1024
    ax[0].specgram(x, NFFT=n, Fs=sr, noverlap=n - int(0.004 * sr), cmap='magma', vmin=-110)
    ax[0].set_ylim(0, min(fmax, sr / 2)); ax[0].set_title(title, fontsize=9)
    t, e = env_db(x, sr, win=0.01, hop=0.0025); ax[1].plot(t, e, lw=.8); ax[1].set_ylim(e.max() - 60, e.max() + 3)
    tt, f, sc, v = hf0(x, sr, hop=0.005, fmin=85, fmax=480)
    ax[2].plot(tt[v], f[v], '.', ms=2); ax[2].set_yscale('log'); ax[2].set_ylim(80, 500)
    ax[2].set_yticks([100, 150, 200, 250, 300, 400]); ax[2].set_yticklabels(['100', '150', '200', '250', '300', '400'])
    for a in ax:
        for m in marks: a.axvline(m, color='c', lw=.7)
    for lab, a0, a1 in spans:
        ax[0].axvline(a0, color='w', lw=.5, alpha=.6)
        ax[0].text(a0 + .002, min(fmax, sr / 2) * .93, lab, color='w', fontsize=8)
    ax[2].set_xlabel('s'); ax[0].set_xticks(np.arange(0, len(x) / sr, 0.05), minor=True)
    for a in ax: a.grid(True, which='both', axis='x', alpha=.25)
    plt.tight_layout(); plt.savefig(path, dpi=80); plt.close()

if __name__ == '__main__':
    import phones
    from lexicon import ipa_words
    out = sys.argv[1]
    for k in sys.argv[2:]:
        x = load(k); t = REG[k]['text']
        lp = phones.logprobs(x, SR); flat = [p for _, ps in ipa_words(t) for p in ps]
        al = phones.refine(x, SR, phones.align(lp, ' '.join(flat)))
        plot(x, SR, os.path.join(out, k + '.png'), f'{k}: {t}', spans=[(p, a, b) for p, a, b, s in al])
        print(k, ' '.join(f'{p}[{a:.3f}-{b:.3f}]' for p, a, b, s in al))
