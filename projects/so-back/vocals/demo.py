"""vox.py demo: spliced words sung, hard-tuned, on a 150 BPM grid, lifted to 48 kHz.
    .venv/bin/python projects/so-back/vocals/demo.py
-> W/demo_its_so_over_sung.wav (E4 A4 | C4 A3: "so" leaps up and a 16th rest precedes "over", or so+over merge into
   "over"), W/demo_its_so_over_sung_lowover.wav (the brief's E4 D4 C4 A3, kept to show the merge),
   W/demo_were_so_back_sung.wav (A4 C#5 E5, with the high-register "back", SUNG_BACK), W/demo_chops.wav"""
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import words, vox

BPM = 150; BEAT = 60 / BPM
ev = json.load(open(os.path.join(HERE, 'phrases_eval.json')))
top = {p: ev[p]['ranked'][0]['recipe'] for p in ev}
# sung, the Smash /ae/ (recorded at ~370 Hz) survives retuning best (P(hit) .96/.91 vs .95/.04 for the spoken #1),
# and its /k/ at full level (.97/.95; -4 dB gave .96/.90 and 'We're so bad')
SUNG = {'its_so_over': top['its_so_over'], 'were_so_back': ['winner-n', 'single+no', 'button+smash+continue.k0']}

def word_syl(kind, y):
    vs = vox.voiced_spans(y); a, b = vs[0][0], vs[-1][1]
    return [(a, 0.22), (0.30, b)] if kind == 'over' else [(a, b)]

def sung(phrase, kinds, notes, beats, lens, recipes=None):
    """Each word sung onto its notes, each syllable stretched to len (beats), its vowel onset on its beat; a monophonic
    line (each word cut where the next starts)."""
    parts = []; k = 0
    for kind, rec in zip(kinds, recipes or SUNG[phrase]):
        y, _, _ = words.word(kind, rec)
        syl = word_syl(kind, y); n = len(syl)
        d = [l * BEAT * 0.85 for l in lens[k:k + n]]
        z = vox.sing(y, notes[k:k + n], syl=syl, durs=d)
        lead = syl[0][0] * (1.0)             # consonants before the vowel lead the beat
        parts.append((vox.to48k(z, bright=0.3), max(0.0, beats[k] * BEAT - lead + 0.3)))
        k += n
    return vox.line(parts)

def main():
    a = sung('its_so_over', ['its', 'so', 'over'], [64, 69, 60, 57], [0, 1, 2.25, 3.25], [0.5, 0.75, 1, 2])
    write(f'{W}/demo_its_so_over_sung.wav', a / (np.abs(a).max() + 1e-9) * 0.89, 48000)
    b = sung('were_so_back', ['were', 'so', 'back'], [69, 73, 76], [0, 1, 2], [0.75, 0.75, 1.5])
    write(f'{W}/demo_were_so_back_sung.wav', b / (np.abs(b).max() + 1e-9) * 0.89, 48000)
    # the brief's E4 D4 C4 A3 on straight beats: "so" and "o-" a step apart merge (STT hears "It's over")
    a2 = sung('its_so_over', ['its', 'so', 'over'], [64, 62, 60, 57], [0, 1, 2, 3], [0.5, 1, 1, 2])
    write(f'{W}/demo_its_so_over_sung_lowover.wav', a2 / (np.abs(a2).max() + 1e-9) * 0.89, 48000)
    # chops: "s-s-so" stutter on 16ths, "back" octave-up (formants x1.25) retriggered, "over" into a tape stop
    so, _, _ = words.word('so', SUNG['were_so_back'][1])
    back, _, _ = words.word('back', SUNG['were_so_back'][2])
    over, _, _ = words.word('over', 'gameover')
    s16 = BEAT / 4
    c = np.zeros(0)
    c = vox.place(c, vox.to48k(vox.stutter(vox.sing(so, [73], syl=[word_syl('so', so)[0]]), n=3, slice_s=s16 * 0.8, gap_s=s16 * 0.2)), 0.1)
    up = vox.pitch_shift(vox.sing(back, [64], syl=[word_syl('back', back)[0]]), 12, formant=1.25)
    c = vox.place(c, vox.to48k(vox.repeat(up, n=4, every_s=s16, length_s=s16 * 0.9, decay_db=-1.5)), 0.1 + 2 * BEAT)
    c = vox.place(c, vox.to48k(vox.tape_stop(over, dur_s=0.5)), 0.1 + 4 * BEAT)
    write(f'{W}/demo_chops.wav', c / (np.abs(c).max() + 1e-9) * 0.89, 48000)
    print('demo written', {k: v for k, v in top.items()})

if __name__ == '__main__':
    main()
