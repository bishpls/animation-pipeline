"""vox: the announcer as a hyperpop vocalist. Every sound stays his own recording: PSOLA (Praat overlap-add, pulses from
our hf0 tracker) for pitch and duration, resampling, gains, gates and crossfades. No synthesis, no voice conversion.

Rates: the bank is 12 kHz, so everything below takes and returns float64 mono numpy arrays at `sr` (default 12000)
unless it says otherwise. Do the PSOLA work at 12 kHz, then lift the finished vocal to 48 kHz with `to48k` last.

    y = vox.load_word('so_surv+no')                      # a built word or phrase from W (or vox.clip('name_37'))
    y = vox.sing(y, [69, 73, 76], syl=[(0, .3), ...])    # hard-tuned onto MIDI notes, one per syllable
    y = vox.sing(y, notes, syl, durs=[.2, .2, .4])       # ... and fitted to syllable lengths (seconds)
    y = vox.stutter(y, n=3, slice_s=.08)                 # "s-s-so"
    y = vox.repeat(y, n=4, every_s=.1, decay_db=-2)      # retrigger on a grid
    y = vox.tape_stop(y, dur_s=.4)                       # the last .4 s slows to a stop (pitch falls with speed)
    y = vox.pitch_shift(y, 12, formant=1.25)             # octave up, formants up 25% (Praat Change Gender)
    y = vox.reverse(y); y = vox.gate(y, bpm=150, pattern='1011', div=16)
    hi = vox.to48k(y, bright=.35)                        # 48 kHz, with a harmonic exciter above 6 kHz

Upsampling a 12 kHz file to 48 kHz leaves nothing above 6 kHz: it sounds dull and "lo-fi phone" next to a modern
instrumental. to48k(bright=...) adds a harmonic exciter: the 3-6 kHz band is soft-clipped (tanh), which makes its own
harmonics, and only what lands above 6 kHz is mixed back in. It brightens without inventing a voice, and at bright=0 it's
a plain resample. Octave-up shifts (a hyperpop staple) push energy upward too; both are judged by ear, by the user.
"""
import os, sys
import numpy as np, parselmouth, librosa
from parselmouth.praat import call
from scipy.signal import butter, sosfiltfilt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load as _load, W, SR, write
from hf0 import hf0

SEED = 1
def _seed():
    """Praat's overlap-add draws random numbers for unvoiced stretches (s, k, breath), so an unseeded PSOLA differs run to
    run (up to 0.1-0.3 of full scale on "back"). Seed before every resynthesis: identical inputs, identical output."""
    parselmouth.praat.run(f'random_initializeWithSeedUnsafelyButPredictably ({SEED})')

def midi2hz(m): return 440.0 * 2 ** ((m - 69) / 12)
def hz2midi(f): return 69 + 12 * np.log2(f / 440.0)

def clip(key): return _load(key)                       # a whole announcer clip (registry key, see INVENTORY.md)
def load_word(name, sub='words'):
    import soundfile as sf
    x, sr = sf.read(os.path.join(W, sub, name + '.wav')); assert sr == SR
    return x.astype(np.float64)

def _manip(y, sr, floor, ceil):
    snd = parselmouth.Sound(np.asarray(y, float), sr)
    manip = call(snd, 'To Manipulation', 0.005, floor, ceil)
    t, f, sc, v = hf0(snd.values[0], sr, hop=0.005, fmin=floor, fmax=ceil)
    pt = call('Create PitchTier', 'p', snd.xmin, snd.xmax)
    for tt, ff, vv in zip(t, f, v):
        if vv: call(pt, 'Add point', snd.xmin + tt, float(ff))
    if call(pt, 'Get number of points') >= 2:
        pitch = call(pt, 'To Pitch', 0.005, floor, ceil)
        pulses = call([snd, pitch], 'To PointProcess (cc)')
        call([manip, pulses], 'Replace pulses')
    return snd, manip, (t, f, v)

def voiced_spans(y, sr=SR, floor=85, ceil=480, min_gap=0.04):
    """Voiced regions [(t0, t1)] by our tracker, merging gaps shorter than min_gap."""
    t, f, sc, v = hf0(np.asarray(y, float), sr, hop=0.005, fmin=floor, fmax=ceil)
    spans, cur = [], None
    for tt, vv in zip(t, v):
        if vv and cur is None: cur = [tt, tt]
        elif vv: cur[1] = tt
        elif cur is not None and tt - cur[1] > min_gap: spans.append(tuple(cur)); cur = None
    if cur: spans.append(tuple(cur))
    return spans

def sing(y, notes, syl=None, sr=SR, durs=None, glide=0.025, floor=75, ceil=600, vibrato=(0.0, 5.5), scoop=0.0, fit_to=None):
    """PSOLA y onto MIDI `notes`, one per syllable span `syl` [(t0, t1)] in y's time (default: its voiced spans, which
    must number len(notes)). Hard-tuned: flat pitch across each syllable, `glide` seconds to move between notes (0.01-0.03
    reads as hard autotune), optional vibrato (semitones, Hz) and a scoop (semitones below, into each note). With `durs`
    (seconds per syllable) each syllable is time-scaled to that length (pitch kept); unvoiced parts (s, t, k) are only
    time-scaled, never pitched. With `fit_to` (seconds) the consonant stretches (everything outside the syllable spans)
    are scaled too, so the whole word lasts fit_to (consonants never below 40% of their length; the word may then run
    over). Returns an array at sr."""
    y = np.asarray(y, float)
    if syl is None:
        syl = voiced_spans(y, sr)
        assert len(syl) == len(notes), f'{len(syl)} voiced spans for {len(notes)} notes: pass syl='
    snd, manip, _ = _manip(y, sr, floor, ceil)
    pt = call('Create PitchTier', 'target', snd.xmin, snd.xmax)
    for k, ((a, b), m) in enumerate(zip(syl, notes)):
        f = midi2hz(m); g = min(glide, (b - a) / 4)
        pts = [(a + g, f * 2 ** (-scoop / 12)), (a + g + min(0.05, (b - a) / 3), f)] if scoop else [(a + g, f)]
        if vibrato[0] > 0:
            for tt in np.arange(a + 0.12, b - g, 0.01):   # vibrato only on held notes, after 120 ms
                pts.append((tt, f * 2 ** (vibrato[0] / 12 * np.sin(2 * np.pi * vibrato[1] * (tt - a - 0.12)))))
        pts.append((b - g, f))
        for tt, ff in pts:
            if snd.xmin < tt < snd.xmax: call(pt, 'Add point', float(tt), float(ff))
    call([pt, manip], 'Replace pitch tier')
    if durs is not None:
        dt = call('Create DurationTier', 'd', snd.xmin, snd.xmax)
        e = 0.0005
        for (a, b), d in zip(syl, durs):
            fac = d / max(b - a, 1e-3)
            call(dt, 'Add point', a + e, fac); call(dt, 'Add point', b - e, fac)
        # the gaps between syllables (consonants) keep their length, or scale to fit the word into fit_to
        edges = [0.0] + [v for s in syl for v in s] + [snd.xmax]
        cons = sum(b - a for a, b in zip(edges[::2], edges[1::2]))
        cf = 1.0 if fit_to is None else float(np.clip((fit_to - sum(durs)) / max(cons, 1e-3), 0.4, 1.0))
        for a, b in zip(edges[::2], edges[1::2]):
            if b - a > 4 * e:
                call(dt, 'Add point', a + e, cf); call(dt, 'Add point', b - e, cf)
        call([dt, manip], 'Replace duration tier')
    _seed(); return call(manip, 'Get resynthesis (overlap-add)').values[0].copy()

def stutter(y, n=3, slice_s=0.08, sr=SR, gap_s=0.0, fade_s=0.004):
    """The first slice_s repeated n times (each with short fades, gap_s apart), then the whole of y: "s-s-so"."""
    k = int(slice_s * sr); f = int(fade_s * sr)
    s = y[:k].copy(); s[:f] *= np.linspace(0, 1, f); s[-f:] *= np.linspace(1, 0, f)
    g = np.zeros(int(gap_s * sr))
    return np.concatenate([np.concatenate([s, g]) for _ in range(n)] + [y])

def repeat(y, n=4, every_s=0.1, sr=SR, decay_db=0.0, length_s=None, fade_s=0.004):
    """y retriggered n times every every_s seconds (each hit cut at the next, with fades), each decay_db quieter."""
    step = int(every_s * sr); L = int((length_s or every_s) * sr); f = int(fade_s * sr)
    out = np.zeros(step * (n - 1) + max(L, len(y)))
    for i in range(n):
        seg = y[:L if i < n - 1 else len(y)].copy()
        if len(seg) > 2 * f: seg[:f] *= np.linspace(0, 1, f); seg[-f:] *= np.linspace(1, 0, f)
        out[i * step:i * step + len(seg)] += seg * 10 ** (decay_db * i / 20)
    return out

def tape_stop(y, dur_s=0.4, sr=SR, curve=2.0):
    """The last dur_s seconds slow to a stop: playback rate falls from 1 to 0 (pitch falls with it), like a tape stop."""
    n = int(dur_s * sr); head, tail = y[:-n], y[-n:]
    # read position advances at rate r(t) = (1 - t/T)^curve; integrate it and resample the tail along it
    T_out = int(n * (curve + 1))            # the slowed tail lasts longer than the source span
    t = np.arange(T_out) / T_out
    pos = n * (1 - (1 - t) ** (curve + 1))  # integral of (1-t)^curve, scaled to end at n
    out = np.interp(pos, np.arange(n), tail)
    out *= np.linspace(1, 0, T_out) ** 0.5
    return np.concatenate([head, out[:int(T_out * 0.8)]])

def pitch_shift(y, semis, sr=SR, formant=None, floor=75, ceil=600):
    """Shift pitch by `semis`, keeping duration. formant=None: pure PSOLA (formants stay put). formant=r: Praat's
    Change Gender (PSOLA plus a resample that moves formants by r; r=1.2-1.3 with +12 is the pitched-up hyperpop voice)."""
    y = np.asarray(y, float)
    if formant is None:
        snd, manip, (t, f, v) = _manip(y, sr, floor, ceil)
        pt = call(manip, 'Extract pitch tier')
        call(pt, 'Multiply frequencies', snd.xmin, snd.xmax, 2 ** (semis / 12))
        call([pt, manip], 'Replace pitch tier')
        _seed(); return call(manip, 'Get resynthesis (overlap-add)').values[0].copy()
    snd = parselmouth.Sound(y, sr)
    t, f, sc, v = hf0(y, sr, hop=0.005, fmin=floor, fmax=ceil)
    med = float(np.median(f[v])) if v.any() else 200.0
    _seed(); out = call(snd, 'Change gender', floor, ceil, float(formant), med * 2 ** (semis / 12), 1.0, 1.0)
    return out.values[0].copy()

def reverse(y): return np.asarray(y)[::-1].copy()

def gate(y, bpm=150, pattern='1', div=16, sr=SR, offset_s=0.0, edge_s=0.004, floor_db=-60):
    """A rhythmic gate: pattern chars '1'/'0' per 1/div note (repeating), from offset_s; smooth edges."""
    step = 60.0 / bpm * 4 / div
    t = np.arange(len(y)) / sr - offset_s
    idx = np.floor(t / step).astype(int) % len(pattern)
    g = np.array([pattern[i] == '1' for i in idx], float); g[t < 0] = 1.0
    k = max(1, int(edge_s * sr)); g = np.convolve(g, np.ones(k) / k, 'same')
    return y * np.maximum(g, 10 ** (floor_db / 20))

def to48k(y, sr=SR, bright=0.3, out_sr=48000):
    """Resample to 48 kHz (soxr high quality); bright>0 adds a harmonic exciter above sr/2 (see module doc)."""
    y = np.asarray(y, float)
    hi = librosa.resample(y, orig_sr=sr, target_sr=out_sr, res_type='soxr_hq')
    if bright <= 0: return hi
    band = sosfiltfilt(butter(4, [3000, min(5800, sr / 2 - 100)], 'band', fs=out_sr, output='sos'), hi)
    g = 4.0 / (np.abs(band).max() + 1e-9)
    exc = np.tanh(band * g) / g                      # soft clip makes harmonics of the 3-6 kHz band
    exc = sosfiltfilt(butter(4, sr / 2, 'high', fs=out_sr, output='sos'), exc)
    return hi + bright * exc * (np.sqrt(np.mean(band ** 2)) / (np.sqrt(np.mean(exc ** 2)) + 1e-12))

def line(words, sr=48000, fade_s=0.012):
    """A monophonic vocal line: words = [(y, t_s)] (at sr), each cut where the next one starts (with a fade), so tails
    never smear into the next word. Returns the mixed array."""
    words = sorted(words, key=lambda w: w[1]); out = np.zeros(0)
    for k, (y, t) in enumerate(words):
        y = np.asarray(y, float).copy()
        if k + 1 < len(words):
            n = int((words[k + 1][1] - t) * sr) + int(fade_s * sr) // 2
            if n < len(y):
                y = y[:max(n, 1)]; f = min(int(fade_s * sr), len(y)); y[-f:] *= np.cos(np.linspace(0, np.pi / 2, f)) ** 2
        out = place(out, y, t, sr)
    return out

def shelf(y, db=-3.0, f=3500, sr=48000):
    """A gentle high shelf (RBJ biquad, slope 0.7): db above f, on a 48 kHz vocal (round 2: -3 dB @ 3.5 kHz takes the edge
    off the 12 kHz source's upper band without dulling it)."""
    from scipy.signal import lfilter
    if not db: return y
    A = 10 ** (db / 40); w = 2 * np.pi * f / sr; cs, sn = np.cos(w), np.sin(w); al = sn / 2 * np.sqrt((A + 1 / A) * (1 / .7 - 1) + 2)
    b = [A * ((A + 1) + (A - 1) * cs + 2 * np.sqrt(A) * al), -2 * A * ((A - 1) + (A + 1) * cs), A * ((A + 1) + (A - 1) * cs - 2 * np.sqrt(A) * al)]
    a = [(A + 1) - (A - 1) * cs + 2 * np.sqrt(A) * al, 2 * ((A - 1) - (A + 1) * cs), (A + 1) - (A - 1) * cs - 2 * np.sqrt(A) * al]
    return lfilter(np.array(b) / a[0], np.array(a) / a[0], y)

def place(track, y, t_s, sr=48000, gain_db=0.0):
    """Mix y into `track` (grown as needed) at t_s seconds."""
    i = int(round(t_s * sr)); need = i + len(y)
    if need > len(track): track = np.concatenate([track, np.zeros(need - len(track))])
    track[i:i + len(y)] += y * 10 ** (gain_db / 20)
    return track
