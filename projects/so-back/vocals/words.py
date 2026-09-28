"""Spliced words for SO BACK: "it's", "so", "over", "we're", "back", each from several recipes of the announcer's own
recorded segments (cut, PSOLA'd, gain-matched and crossfaded with the splice engine, splice.py), then assembled into the
phrases "it's so over" and "we're so back", both as one take and as separate words with a gap between them.

A piece is S(src, t0, t1, ...) (a source span, times in the source clip) or G(dur) (silence: a stop closure, or a gap).
Consecutive S pieces are joined by splice.build (pitch-synchronous alignment, correlation-adaptive crossfade); a G
between them cuts the sound with 3 ms fades and inserts silence, which is how /t/ in "it's" and /k/ in "back" are made.
Gains: every segment is set so its SOURCE CLIP's active RMS meets REF_DB (each phone keeps its level relative to its own
recording), plus any per-piece trim."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import splice
from splice import Seg

REF_DB = -11.3                 # median RMS of the real name calls (measured)
_clip_db = {}
def clip_db(src):
    if src not in _clip_db:
        x = load(src); _clip_db[src] = db(x[int(onset(x) * SR):int(tail_end(x) * SR) + 1])
    return _clip_db[src]

class S:
    def __init__(self, src, t0, t1, dur=None, pitch=None, trim=0.0, xf=0.016, floor=85, ceil=480, label='', end_fade=None):
        self.src, self.t0, self.t1, self.dur, self.pitch, self.trim, self.xf = src, t0, t1, dur, pitch, trim, xf
        self.end_fade = end_fade   # seconds: a word-final piece ends at its core end with a cos^2 fade of this length
        self.floor, self.ceil, self.label = floor, ceil, label or f'{src}[{t0:.3f}-{t1:.3f}]'
    def seg(self):
        return Seg(self.src, self.t0, self.t1, dur=self.dur, pitch=self.pitch, gain_db=REF_DB - clip_db(self.src) + self.trim,
                   floor=self.floor, ceil=self.ceil, label=self.label)

class G:
    def __init__(self, dur, pre=0.003, post=0.003):   # silence; fade-out of the block before it, fade-in of the one after
        self.dur, self.pre, self.post = dur, pre, post

def _fade(y, n_in, n_out):
    y = y.copy()
    if n_in: y[:n_in] *= np.sin(np.linspace(0, np.pi / 2, n_in)) ** 2
    if n_out: y[-n_out:] *= np.cos(np.linspace(0, np.pi / 2, n_out)) ** 2
    return y

def assemble(pieces, margin=0.03):
    """-> (y, joins, spans): joins = output times of the crossfade seams (gap edges are not seams)."""
    out, joins, spans, t = [], [], [], 0.0
    i = 0
    first = True
    fin = 0.004
    while i < len(pieces):
        if isinstance(pieces[i], G):
            g = pieces[i]
            if out: out[-1] = _fade(out[-1], 0, int(g.pre * SR))
            n = int(round(g.dur * SR)); out.append(np.zeros(n)); t += n / SR; fin = g.post; i += 1; continue
        run = []
        while i < len(pieces) and isinstance(pieces[i], S):
            run.append(pieces[i]); i += 1
        segs = [p.seg() for p in run]
        y, js, sp = splice.build(segs, [p.xf for p in run[1:]], margin=margin, lead=0.004 if first else 0.0)
        # cut the block at its last core end (drop the trailing margin) unless it is the word's end (keep the tail)
        end = int(round(sp[-1][1] * SR))
        last = i >= len(pieces)
        if not last or run[-1].end_fade: y = y[:end]
        fo = int((run[-1].end_fade or 0.02) * SR) if last else 0
        y = _fade(y, int(fin * SR), fo)
        joins += [t + j for j in js]; spans += [(t + a, t + b) for a, b in sp]
        out.append(y); t += len(y) / SR; first = False
    y = np.concatenate(out)
    return y, joins, spans

# ---------------------------------------------------------------------------------------------------- recipes
# source times read off spectrograms (plots/z_*.png) and the forced alignment; see NOTES.md
ITS = {
    'targets':  [S('name_50', 1.035, 1.56, label='targ-ETS')],
    'this+t':   [S('nr_vs_05', 0.035, 0.14, label='th-I-s'), G(0.035), S('nr_vs_05', 0.15, 0.30, label='thi-S')],
    'is+t':     [S('nr_vs_05', 1.10, 1.25, label='winner I-s'), G(0.035), S('name_50', 1.26, 1.52, label='target-S')],
    'this+ts':  [S('nr_vs_05', 0.035, 0.14, label='th-I-s'), G(0.03), S('name_50', 1.23, 1.52, label='targe-TS')],
}
SO = {
    'surv+no':   [S('nr_select_08', 0.0, 0.095, label='S-urvival'), S('nr_vs_00', 0.09, 0.38, xf=0.012, label='n-O contest')],
    'sudden+no': [S('nr_vs_01', 0.02, 0.185, label='S-udden'), S('nr_vs_00', 0.09, 0.38, xf=0.012, label='n-O contest')],
    'samus+go':  [S('name_30', 0.0, 0.095, label='S-amus'), S('name_38', 0.035, 0.45, xf=0.012, label='g-O')],
    'single+no': [S('nr_select_17', 0.01, 0.155, label='S-ingle'), S('nr_vs_00', 0.09, 0.38, xf=0.012, label='n-O contest')],
    'surv+go':   [S('nr_select_08', 0.0, 0.095, label='S-urvival'), S('name_38', 0.035, 0.45, xf=0.012, label='g-O')],
}
# round 2 (softer, lower "so" for the sad line): the same s, with an unshouted o
SO.update({
    'sudden+mario':   [S('nr_vs_01', 0.07, 0.185, trim=-3, label='(s)S-udden'), S('name_21', 0.44, 0.95, xf=0.014, label='mari-O')],
    'sudden+falco':   [S('nr_vs_01', 0.07, 0.185, trim=-3, label='(s)S-udden'), S('name_04', 0.45, 0.80, xf=0.014, label='falc-O')],
    'sudden+bonus':   [S('nr_vs_01', 0.07, 0.185, trim=-3, label='(s)S-udden'), S('nr_1p_07', 0.022, 0.10, xf=0.012, label='b-O-nus')],
    'sudden+overo':   [S('nr_vs_01', 0.07, 0.185, trim=-3, label='(s)S-udden'), S('nr_1p_03', 1.12, 1.33, xf=0.014, label='game O-ver')],
    'sudden+no.soft': [S('nr_vs_01', 0.07, 0.185, trim=-3, label='(s)S-udden'), S('nr_vs_00', 0.09, 0.30, xf=0.02, trim=-2, label='n-O contest')],
})

OVER = {
    'gameover':  [S('nr_1p_03', 1.10, 2.09, label='game OVER')],
}
WERE = {
    # round 2: the low "winner" of "This game's WINNER is..." (recorded at ~165-210 Hz, his chest register)
    'lowwinner':    [S('nr_vs_05', 0.73, 0.87, label='game\'s WI-nner'), S('nr_vs_05', 0.94, 1.09, xf=0.03, label='winn-ER is')],
    'wins+winner':  [S('nr_vs_06', 0.0, 0.19, label='WI-ns'), S('nr_vs_05', 0.93, 1.10, xf=0.03, label='winn-ER is')],
    'winner-n':     [S('nr_select_21', 0.0, 0.33, label='WI-nner drops'), S('nr_select_21', 0.49, 0.69, xf=0.03, label='winn-ER drops')],
    'wins+player':  [S('nr_vs_06', 0.0, 0.19, label='WI-ns'), S('nr_select_20', 0.68, 0.88, xf=0.03, label='play-ER')],
    'wins+master':  [S('nr_vs_06', 0.0, 0.19, label='WI-ns'), S('name_25', 0.42, 0.50, xf=0.025, label='mast-ER')],
}
# "back": a b burst, an /ae/ from a word with a neutral or labial onset, a 60 ms stop closure (the vowel fading over 30 ms),
# then a word-initial /k/ release (burst + aspiration, the first 45-50 ms of a clip, so no reverb before it), 4 dB down.
# Chosen from a 200-way grid (back_grid.py: 5 b x 5 ae x 4 k x 2 closures) by Whisper forced choice in "we're so back".
_CL = dict(dur=0.06, pre=0.03)
BACK = {
    'break+hand+complete':   [S('name_50', 0.085, 0.115, label='B-reak'), S('name_25', 0.56, 0.74, xf=0.008, label='h-A-nd'),
                              G(**_CL), S('nr_1p_06', 0.0, 0.045, end_fade=0.02, trim=-4, label='K-omplete')],
    # the same with the /k/ at full level and a longer burst (SO BACK, take f3: a brighter drop masked the -4 dB /k/)
    'break+hand+complete.k0': [S('name_50', 0.085, 0.115, label='B-reak'), S('name_25', 0.56, 0.74, xf=0.008, label='h-A-nd'),
                              G(**_CL), S('nr_1p_06', 0.0, 0.055, end_fade=0.02, trim=0, label='K-omplete')],
    'break+hand+complete.k3': [S('name_50', 0.085, 0.115, label='B-reak'), S('name_25', 0.56, 0.74, xf=0.008, label='h-A-nd'),
                              G(**_CL), S('nr_1p_06', 0.0, 0.055, end_fade=0.02, trim=3, label='K-omplete')],
    'bonus+hand+kirby':      [S('nr_1p_07', 0.0, 0.022, label='B-onus'), S('name_25', 0.56, 0.74, xf=0.008, label='h-A-nd'),
                              G(**_CL), S('name_15', 0.0, 0.05, end_fade=0.02, trim=-4, label='K-irby')],
    'bonus+and+kirby':       [S('nr_1p_07', 0.0, 0.022, label='B-onus'), S('nr_1p_04', 0.02, 0.22, xf=0.008, label='A-nd'),
                              G(**_CL), S('name_15', 0.0, 0.05, end_fade=0.02, trim=-4, label='K-irby')],
    'button+smash+continue': [S('nr_select_17', 0.70, 0.725, label='B-utton'), S('nr_title_01', 1.035, 1.20, xf=0.008, label='sm-A-sh'),
                              G(**_CL), S('nr_1p_02', 0.0, 0.045, end_fade=0.02, trim=-4, label='K-ontinue')],
    # the sung default (demo.py SUNG): as above with the /k/ at full level, which a retuned vowel needs to stay "back"
    'button+smash+continue.k0': [S('nr_select_17', 0.70, 0.725, label='B-utton'), S('nr_title_01', 1.035, 1.20, xf=0.008, label='sm-A-sh'),
                              G(**_CL), S('nr_1p_02', 0.0, 0.045, end_fade=0.02, trim=0, label='K-ontinue')],
    'bowser+and+complete':   [S('name_16', 0.0, 0.02, label='B-owser'), S('nr_1p_04', 0.02, 0.22, xf=0.008, label='A-nd'),
                              G(**_CL), S('nr_1p_06', 0.0, 0.045, end_fade=0.02, trim=-4, label='K-omplete')],
}
WORDS = dict(its=ITS, so=SO, over=OVER, were=WERE, back=BACK)

def word(kind, name):
    return assemble(WORDS[kind][name])

def phrase(parts, gaps):
    """parts: [(y, joins)], gaps: seconds between parts (negative = overlap, crossfaded). -> (y, joins, starts)"""
    y, joins, starts = np.zeros(0), [], []
    for k, (w, js) in enumerate(parts):
        if k == 0:
            starts.append(0.0); joins += list(js); y = w.copy(); continue
        g = gaps[k - 1]
        if g >= 0:
            t0 = len(y) / SR + g
            y = np.concatenate([y, np.zeros(int(round(g * SR))), w])
        else:
            n = int(round(-g * SR)); t0 = len(y) / SR - n / SR
            u = np.sin(np.linspace(0, np.pi / 2, n)) ** 2
            mid = y[-n:] * (1 - u) + w[:n] * u
            y = np.concatenate([y[:-n], mid, w[n:]])
        starts.append(t0); joins += [t0 + j for j in js]
    return y, sorted(joins), starts
