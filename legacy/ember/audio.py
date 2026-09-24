"""EMBER — score + sound design, synthesized from scratch.
128 BPM, D minor.  Writes out/ember.wav (48k stereo float)."""
import numpy as np
from scipy import signal
import wave
from common import *

rng = np.random.default_rng(7)
N = int((DUR + 0.5) * SR)


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def tt(n):
    return np.arange(n) / SR


def new():
    return np.zeros((N, 2), np.float32)


def put(buf, t, x, gain=1.0, pan=0.0):
    """Place mono (or stereo) x at time t with equal-power pan."""
    i = int(round(t * SR))
    if x.ndim == 1:
        a = (pan + 1) * np.pi / 4
        x = np.stack([x * np.cos(a), x * np.sin(a)], 1)
    if i < 0:
        x = x[-i:]
        i = 0
    n = min(len(x), N - i)
    if n > 0:
        buf[i:i + n] += (x[:n] * gain).astype(np.float32)


def sos(kind, f, order=2, q=None):
    if kind == 'bp':
        return signal.butter(order, f, 'bandpass', fs=SR, output='sos')
    return signal.butter(order, f, kind, fs=SR, output='sos')


def filt(x, kind, f, order=2):
    return signal.sosfilt(sos(kind, f, order), x, axis=0)


def peak(x, f0, gain_db, q=1.0):
    b, a = signal.iirpeak(f0, q, fs=SR)
    g = 10 ** (gain_db / 20) - 1
    return x + g * signal.lfilter(b, a, x, axis=0)


def sweep_lp(x, fc, block=256):
    """Time-varying lowpass; fc is array (per-sample) of cutoffs."""
    y = np.zeros_like(x)
    zi = None
    for s in range(0, len(x), block):
        c = float(np.clip(fc[min(s, len(fc) - 1)], 30, SR * 0.45))
        sosm = signal.butter(2, c, 'low', fs=SR, output='sos')
        if zi is None:
            zi = np.zeros((sosm.shape[0], 2) + x.shape[1:])
        y[s:s + block], zi = signal.sosfilt(sosm, x[s:s + block], axis=0, zi=zi)
    return y


def noise(n):
    return rng.standard_normal(n)


def saw(freq, n, ph0=None):
    f = np.broadcast_to(np.asarray(freq, float), (n,))
    dt = f / SR
    ph = ((rng.random() if ph0 is None else ph0) + np.cumsum(dt)) % 1.0
    y = 2 * ph - 1
    m = ph < dt
    x = ph[m] / dt[m]
    y[m] -= x + x - x * x - 1
    m = ph > 1 - dt
    x = (ph[m] - 1) / dt[m]
    y[m] -= x * x + x + x + 1
    return y


def env_adsr(n, a, d, s, r, hold):
    t = tt(n)
    e = np.where(t < a, t / max(a, 1e-4),
                 s + (1 - s) * np.exp(-(t - a) / max(d, 1e-4)))
    rel = t > hold
    e[rel] *= np.exp(-(t[rel] - hold) / max(r, 1e-4))
    return e


# ---------------------------------------------------------------------------
# Instruments
# ---------------------------------------------------------------------------
def piano(m, dur, vel=1.0):
    f = mtof(m)
    n = int((dur + 3.0) * SR)
    t = tt(n)
    y = np.zeros(n)
    Bc = 0.0004
    for k in range(1, 16):
        fk = k * f * np.sqrt(1 + Bc * k * k)
        if fk > SR * 0.45:
            break
        amp = (1 / k ** 1.1) * (0.6 + 0.4 * vel) ** k
        dec = 0.35 + 0.28 * k + f / 900
        ph = rng.random() * 6.28
        y += amp * np.sin(2 * np.pi * fk * t + ph) * (
            0.7 * np.exp(-t * dec * 2.5) + 0.3 * np.exp(-t * dec * 0.35))
    ham = filt(noise(n), 'bp', [300, 3000]) * np.exp(-t * 90) * 0.4
    y += ham
    rel = t > dur
    y[rel] *= np.exp(-(t[rel] - dur) * 3.0)
    return y * vel * 0.22


def choir_note(m, dur, n_voices=5, vowel='a'):
    f = mtof(m)
    n = int((dur + 1.2) * SR)
    t = tt(n)
    y = np.zeros(n)
    for v in range(n_voices):
        det = 2 ** ((rng.random() - 0.5) * 0.25 / 12)
        vib = 1 + 0.006 * np.sin(2 * np.pi * (4.8 + rng.random()) * t + rng.random() * 6)
        y += saw(f * det * vib, n)
    fm = {'a': [(800, 1.0), (1150, 0.6), (2900, 0.25)],
          'o': [(450, 1.0), (800, 0.5), (2830, 0.15)]}[vowel]
    out = np.zeros(n)
    for fc, g in fm:
        out += g * filt(y, 'bp', [fc * 0.85, fc * 1.15])
    e = env_adsr(n, 0.35, 0.5, 0.85, 0.5, dur)
    return out * e * 0.10


def kick(g=1.0, tight=1.0):
    n = int(0.5 * SR)
    t = tt(n)
    f = 44 + 120 * np.exp(-t * 30 * tight)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 7 * tight)
    click = filt(noise(n), 'hp', 2500) * np.exp(-t * 400) * 0.6
    y = np.tanh(1.8 * (body + click)) * g
    return y


def snare(g=1.0):
    n = int(0.6 * SR)
    t = tt(n)
    tone = (np.sin(2 * np.pi * 190 * t) * 0.6 + np.sin(2 * np.pi * 330 * t) * 0.3) * np.exp(-t * 22)
    nz = filt(noise(n), 'bp', [1200, 9000]) * (np.exp(-t * 16) * 0.9 + np.exp(-t * 5) * 0.12)
    return np.tanh(1.5 * (tone + nz)) * g * 0.8


def hat(g=1.0, open_=False):
    n = int((0.5 if open_ else 0.09) * SR)
    t = tt(n)
    y = filt(noise(n), 'hp', 7500) * np.exp(-t * (7 if open_ else 70))
    return y * g * 0.25


_crash_cache = {}


def crash(g=1.0, length=2.4):
    key = length
    if key not in _crash_cache:
        n = int(length * SR)
        t = tt(n)
        y = filt(noise(n), 'hp', 3500) * 0.5
        for _ in range(40):
            f = 3000 + rng.random() * 9000
            y += np.sin(2 * np.pi * f * t + rng.random() * 6) * 0.03
        y *= np.exp(-t * 2.2) * (1 - np.exp(-t * 800))
        _crash_cache[key] = y
    return _crash_cache[key] * g * 0.5


def tom(m, g=1.0):
    n = int(0.6 * SR)
    t = tt(n)
    f = mtof(m) * (1 + 0.6 * np.exp(-t * 25))
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.tanh(1.5 * np.sin(ph) * np.exp(-t * 7)) * g * 0.7


def boom(g=1.0, length=1.6, f0=55):
    n = int(length * SR)
    t = tt(n)
    f = f0 * 0.55 + f0 * np.exp(-t * 6)
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.tanh(2.0 * np.sin(ph) * np.exp(-t * 2.6))
    y += filt(noise(n), 'lp', 400) * np.exp(-t * 5) * 0.6
    return y * g


def reverse_swell(length):
    c = crash(1.0, length + 0.3)[:int(length * SR)]
    y = c[::-1].copy()
    n = len(y)
    y += filt(noise(n), 'bp', [2000, 9000]) * np.linspace(0, 1, n) ** 3 * 0.25
    return y


# ---------------------------------------------------------------------------
# Distorted guitar (power chords), bass, lead
# ---------------------------------------------------------------------------
def amp_sim(di, drive=18.0):
    x = filt(di, 'hp', 120)
    x = peak(x, 900, 6, 0.8)
    x = signal.resample_poly(x, 2, 1)
    x = np.tanh(drive * x)
    x = np.tanh(1.5 * x)
    x = signal.resample_poly(x, 1, 2)
    x = filt(x, 'lp', 5200, 4)
    x = filt(x, 'hp', 80)
    x = peak(x, 2400, 3, 1.2)
    x = peak(x, 350, -4, 1.0)
    return x


def power_chord_note(root, dur, mute, n_len):
    """DI signal for one power-chord hit."""
    n = n_len
    t = tt(n)
    y = np.zeros(n)
    for iv in (0, 7, 12):
        f = mtof(root + iv) * 2 ** ((rng.random() - .5) * 0.08 / 12)
        y += saw(f, n) * (1.0 if iv == 0 else 0.8)
    if mute:
        e = np.exp(-t * 26) * (t < dur + 0.02)
        y = filt(y, 'lp', 900) * 1.6
    else:
        e = np.minimum(1, t / 0.004) * (0.4 + 0.6 * np.exp(-t * 1.5))
        e *= np.where(t > dur, np.exp(-(t - dur) * 25), 1)
    return y * e * 0.12


def guitar_track(events, side):
    """events: list of (t, root, dur, mute). Returns stereo-positioned track."""
    di_m = np.zeros(N)
    di_o = np.zeros(N)
    for (t0, root, dur, mute) in events:
        jitter = (rng.random() - 0.5) * 0.008
        nl = int((dur + 0.15) * SR)
        x = power_chord_note(root, dur, mute, nl)
        i = int((t0 + jitter + (0.004 if side > 0 else 0)) * SR)
        i = max(i, 0)
        tgt = di_m if mute else di_o
        n = min(nl, N - i)
        if n > 0:
            tgt[i:i + n] += x[:n]
    y = amp_sim(di_m, 26) * 0.9 + amp_sim(di_o, 16)
    return y


def bass_track(events):
    y = np.zeros(N)
    for (t0, root, dur, mute) in events:
        n = int((dur + 0.1) * SR)
        t = tt(n)
        f = mtof(root - 12)
        x = saw(f, n) * 0.6 + np.sin(2 * np.pi * f * t) * 0.8
        e = np.minimum(1, t / 0.003) * np.where(t > dur, np.exp(-(t - dur) * 30), 1)
        if mute:
            e *= np.exp(-t * 8)
        put1(y, t0, x * e)
    y = filt(y, 'lp', 1000)
    return np.tanh(2.0 * y) * 0.5


def put1(y, t0, x):
    i = int(t0 * SR)
    n = min(len(x), N - i)
    if n > 0 and i >= 0:
        y[i:i + n] += x[:n]


def lead_note(m, dur, vel=1.0, bend_from=None):
    n = int((dur + 0.3) * SR)
    t = tt(n)
    f0 = mtof(m)
    f = np.full(n, f0)
    if bend_from is not None:
        fb = mtof(bend_from)
        f = f0 + (fb - f0) * np.exp(-t * 25)
    vib = 1 + 0.009 * np.sin(2 * np.pi * 5.6 * t) * np.clip((t - 0.18) * 4, 0, 1)
    y = saw(f * vib, n) + saw(f * vib * 1.006, n) * 0.7 + saw(f * vib * 0.994, n) * 0.7
    y = filt(y, 'lp', 3800)
    y = np.tanh(y * 1.5)
    e = np.minimum(1, t / 0.01) * np.where(t > dur, np.exp(-(t - dur) * 14), 1)
    return y * e * 0.09 * vel


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------
MOTIF = [  # bar-relative (beat, len, midi) — "Ember theme"
    [(0, 1.5, 69), (1.5, .5, 74), (2, 1, 77), (3, 1, 76)],          # Dm
    [(0, 1.5, 74), (1.5, .5, 72), (2, 1.5, 74), (3.5, .5, 70)],     # Bb
    [(0, 1.5, 72), (1.5, .5, 74), (2, 1, 76), (3, 1, 79)],          # C
    [(0, 3, 76), (3, 1, 73)],                                       # A
]
PROG_A = [('Dm', 38), ('Bb', 34), ('C', 36), ('A', 33)]
CHORD_NOTES = {'Dm': [50, 53, 57, 62], 'Bb': [46, 50, 53, 58], 'C': [48, 52, 55, 60],
               'A': [45, 49, 52, 57], 'Eb': [51, 55, 58, 63], 'Gm': [43, 50, 55, 58],
               'D': [50, 54, 57, 62], 'F': [53, 57, 60, 65]}


def build():
    mus = {k: new() for k in ['pno', 'pad', 'drm', 'gtr', 'bas', 'lead', 'fx', 'amb']}
    # per-bus reverb sends collected separately
    verb_send = new()

    # --- ambience: wind, whole piece -------------------------------------
    n = N
    t = tt(n)
    w = noise(n)
    wl = sweep_lp(w, 400 + 300 * np.sin(2 * np.pi * 0.13 * t) + 200 * np.sin(2 * np.pi * 0.31 * t))
    wr = sweep_lp(noise(n), 450 + 300 * np.sin(2 * np.pi * 0.11 * t + 1) + 200 * np.sin(2 * np.pi * 0.27 * t))
    wind = np.stack([wl, wr], 1) * 0.10
    # wind louder in intro/break/outro, ducked under the fight
    wenv = np.interp(t, [0, 1, B(3, 3), B(4, 0), B(12, 0), B(12, .5), B(13, 0), B(14, 0), B(14, 1), DUR],
                     [0.3, 1, 0.9, 0.25, 0.25, 1.0, 0.8, 0.25, 0.7, 0.9])
    mus['amb'] += (wind * wenv[:, None]).astype(np.float32)

    # --- piano: intro motif, break, outro --------------------------------
    for bar in range(4):
        for (b, l, m) in MOTIF[bar]:
            put(mus['pno'], B(bar, b), piano(m, l * BEAT * 1.05, 0.8), 1.0, 0.15)
        # left hand: open fifths
        root = CHORD_NOTES[PROG_A[bar][0]][0] - 12
        put(mus['pno'], B(bar, 0), piano(root, BAR * 0.95, 0.6), 0.8, -0.2)
        put(mus['pno'], B(bar, 0.5), piano(root + 7, BAR * 0.8, 0.45), 0.6, -0.1)
        put(mus['pno'], B(bar, 2), piano(root + 12, BEAT * 2, 0.4), 0.5, -0.1)
    # break (bar 12): motif fragment, slow, exposed
    for (b, l, m) in [(0, 1.5, 81), (1.5, .5, 86), (2, 1.0, 89)]:
        put(mus['pno'], B(12, b), piano(m, l * BEAT * 1.4, 0.75), 1.0, 0.1)
    put(mus['pno'], B(12, 0), piano(46 - 12, BAR, 0.7), 0.9, -0.2)
    put(mus['pno'], B(12, 0), piano(46, BAR, 0.5), 0.7, -0.2)
    # outro: theme resolves to D major (Picardy)
    for (b, l, m) in [(1, 1, 78), (2, 1, 76), (3, 1, 74)]:
        put(mus['pno'], B(14, b), piano(m, BEAT * 1.1, 0.7), 1.6, 0.1)
    put(mus['pno'], B(15, 0), piano(74, 2.4, 0.75), 1.7, 0.1)
    put(mus['pno'], B(15, 0), piano(78, 2.4, 0.55), 1.4, 0.15)
    put(mus['pno'], B(15, 0), piano(81, 2.4, 0.55), 1.2, 0.2)
    put(mus['pno'], B(15, 0), piano(38, 2.4, 0.75), 1.6, -0.2)
    put(mus['pno'], B(15, 0), piano(45, 2.4, 0.55), 1.3, -0.2)

    # --- choir pad -------------------------------------------------------
    pad_plan = [(0, 'Dm', 0.35), (1, 'Bb', 0.35), (2, 'C', 0.5), (3, 'A', 0.6),
                (4, 'Dm', 0.8), (5, 'Bb', 0.8), (6, 'C', 0.8), (7, 'A', 0.9),
                (8, 'Dm', 0.9), (9, 'Bb', 1.0), (10, 'Eb', 1.0), (11, 'A', 0.9),
                (12, 'Bb', 0.8), (13, 'C', 1.0)]
    for bar, ch, g in pad_plan:
        dur = BAR * (0.72 if bar == 3 else 1.0)
        for i, m in enumerate(CHORD_NOTES[ch]):
            put(mus['pad'], B(bar, 0), choir_note(m + 12, dur, vowel='a' if bar >= 4 else 'o'),
                g, -0.5 + i * 0.33)
    # final Picardy D major, big and long
    for i, m in enumerate([50, 54, 57, 62, 66, 69, 74]):
        put(mus['pad'], B(14, 0), choir_note(m + 12 if m < 60 else m, BAR * 2 - 0.4), 0.9, -0.6 + i * 0.2)

    # --- drums -----------------------------------------------------------
    D = mus['drm']
    # build: heartbeat (bar 2), toms (bar 3)
    for b in [0, 2]:
        put(D, B(2, b), kick(0.8, 0.7), 1.0)
        put(D, B(2, b + 0.4), kick(0.55, 0.7), 1.0)
    for i, b in enumerate([0, 0.5, 1, 1.5, 2, 2.25, 2.5, 2.75]):
        put(D, B(3, b), tom(45 - (i % 3) * 3, 0.4 + i * 0.07), 1.0, [-.4, .3, 0][i % 3])
    put(D, B(3, 0), kick(0.8), 1.0)
    put(D, B(3, 2), kick(0.8), 1.0)
    # reverse swell into the drop (from the breath)
    put(mus['fx'], B(3, 3) - 0.35, reverse_swell(0.35 + BEAT), 0.7)

    def groove(bar, kind):
        if kind == 'A':
            kicks = [0, 0.75, 1.5, 2, 2.75, 3.5]
            snares = [1, 3]
        elif kind == 'B':  # double kick 16ths
            kicks = [i * 0.25 for i in range(16)]
            snares = [1, 3]
        elif kind == 'half':
            kicks = [0]
            snares = [2]
        elif kind == 'break':  # breakdown
            kicks = [0, 0.75, 1.5, 2.5, 3, 3.25]
            snares = [2]
        for k in kicks:
            put(D, B(bar, k), kick(0.9 if k % 1 == 0 else 0.7), 1.0)
        for s in snares:
            put(D, B(bar, s), snare(1.0), 1.0, 0.05)
            put(verb_send, B(bar, s), snare(0.5), 1.0, 0.05)
        if kind in ('A', 'B'):
            for h in range(8):
                put(D, B(bar, h * .5), hat(0.8 if h % 2 else 0.5), 1.0, 0.35)

    for bar in [4, 5, 6, 7]:
        groove(bar, 'A')
    groove(8, 'B')
    # bar 9: half-time under the slow-mo, snap back at the burst
    put(D, B(9, 0), kick(1.0), 1.0)
    put(D, B(9, 2), kick(1.0), 1.0)
    put(D, B(9, 2), snare(1.1), 1.0)
    for k in [2.5, 2.75, 3, 3.25, 3.5, 3.75]:
        put(D, B(9, k), kick(0.75), 1.0)
    put(D, B(9, 3), snare(1.0), 1.0)
    # bar 10: alpha stop-hit, roar gap, drums back at the block
    put(D, B(10, 0), kick(1.2), 1.0)
    groove_b10 = [2, 2.75, 3.25]
    for k in groove_b10:
        put(D, B(10, k), kick(0.9), 1.0)
    put(D, B(10, 2), snare(1.1), 1.0)
    put(D, B(10, 3), snare(1.0), 1.0)
    groove(11, 'break')
    for k in [0.5, 1.0]:
        put(D, B(11, k), snare(0.7), 1.0)
    # bar 12 break: nothing but a swell into the final
    put(mus['fx'], B(12, 1), reverse_swell(B(13, 0) - B(12, 1)), 0.9)
    # bar 13: double kick + 16th snare roll crescendo into the cleave
    for i in range(16):
        put(D, B(13, i * .25), kick(0.8), 1.0)
    for i in range(8, 16):
        put(D, B(13, i * .25), snare(0.4 + 0.045 * (i - 8)), 1.0, 0.05)
    put(D, B(13, 0), snare(1.0), 1.0)
    put(D, B(13, 1), snare(1.0), 1.0)
    # crashes
    for tc in [B(4, 0), B(6, 0), B(8, 0), B(9, 2), B(10, 0), B(11, 0), B(13, 0)]:
        put(D, tc, crash(0.9), 1.0, 0.3)
        put(verb_send, tc, crash(0.4), 1.0)
    put(D, T_CLEAVE, crash(1.2, 3.0), 1.0, -0.3)
    put(D, T_CLEAVE, crash(1.0, 3.0), 1.0, 0.3)
    put(D, T_CLEAVE, kick(1.3, 0.6), 1.0)

    # --- guitars + bass --------------------------------------------------
    ev = []
    A_roots = {4: 38, 5: 34, 6: 36, 7: 33}
    for bar, r in A_roots.items():
        # open chord on the one, chugs, open accent on the "and of 2"
        ev.append((B(bar, 0), r, BEAT * 0.7, False))
        for s in [0.75, 1, 1.25, 1.5, 2.25, 3, 3.25, 3.5, 3.75]:
            ev.append((B(bar, s), 38 if s >= 3 else r, S16 * 0.8, True))
        ev.append((B(bar, 1.75), r, BEAT * 0.45, False))
        ev.append((B(bar, 2.5), r, BEAT * 0.45, False))
    # bar 8: gallop on D
    ev.append((B(8, 0), 38, BEAT * 0.4, False))
    for i in range(1, 16):
        if i in (8, 14):
            ev.append((B(8, i * .25), 41 if i == 8 else 43, S16 * 1.8, False))
        else:
            ev.append((B(8, i * .25), 38, S16 * 0.8, True))
    # bar 9: slow-mo — one long open Bb ringing, then D chugs on the snap
    ev.append((B(9, 0), 34, BEAT * 1.9, False))
    for i in range(8, 16):
        ev.append((B(9, i * .25), 38, S16 * 0.8, True))
    # bar 10: alpha — Phrygian Eb hit, ring, then chugs on low D
    ev.append((B(10, 0), 39, BEAT * 1.8, False))
    for s in [2, 2.75, 3.25]:
        ev.append((B(10, s), 38, S16 * 0.9, True))
    ev.append((B(10, 2.5), 39, BEAT * 0.3, False))
    ev.append((B(10, 3.5), 39, BEAT * 0.4, False))
    # bar 11: breakdown pattern
    for s in [0, 0.75, 1.5, 2.5, 3, 3.25]:
        ev.append((B(11, s), 38, S16 * 0.9, True))
    ev.append((B(11, 2), 33, BEAT * 0.4, False))
    ev.append((B(11, 3.5), 33, BEAT * 0.4, False))
    # bar 13: Bb -> C open driving 8ths, into D major hit
    for i in range(8):
        ev.append((B(13, i * .5), 34 if i < 4 else 36, BEAT * 0.4, i % 2 == 1))
    ev.append((T_CLEAVE, 38, BAR * 0.85, False))
    gl = guitar_track(ev, -1)
    gr = guitar_track(ev, +1)
    mus['gtr'][:, 0] += gl.astype(np.float32) * 0.9
    mus['gtr'][:, 1] += gr.astype(np.float32) * 0.9
    mus['gtr'][:, 0] += gr.astype(np.float32) * 0.15
    mus['gtr'][:, 1] += gl.astype(np.float32) * 0.15
    bev = [(t0, r, d, m) for (t0, r, d, m) in ev]
    bs = bass_track(bev)
    mus['bas'] += np.stack([bs, bs], 1).astype(np.float32)

    # --- lead (Fight B + climax) ----------------------------------------
    L = mus['lead']
    for (b, l, m) in MOTIF[0]:
        put(L, B(8, b), lead_note(m + 12, l * BEAT * 0.95), 1.0, 0.1)
    put(L, B(9, 0), lead_note(86, BEAT * 1.9, bend_from=84), 1.0, 0.1)
    for (b, l, m) in [(2, .5, 86), (2.5, .5, 88), (3, 1, 89)]:
        put(L, B(9, b), lead_note(m, l * BEAT), 1.0, 0.1)
    for (b, l, m) in MOTIF[3]:
        put(L, B(11, b), lead_note(m + 12, l * BEAT * 0.95), 0.9, 0.1)
        put(L, B(11, b), lead_note(m + 8 if m == 76 else m + 9, l * BEAT * 0.95), 0.6, -0.1)
    run = [74, 76, 77, 79, 81, 82, 84, 86, 88, 89, 91, 93, 94, 96, 98, 98]
    for i, m in enumerate(run):
        put(L, B(13, i * .25), lead_note(m - 12 if i < 8 else m - 12, S16 * 0.95, 0.8), 1.0, 0.1)
    put(L, T_CLEAVE, lead_note(90, BAR * 1.2, 1.1, bend_from=88), 1.0, 0.1)

    # --- sound design from the cue sheet ------------------------------
    for (t0, kind, pan, g) in SFX:
        x = make_sfx(kind)
        put(mus['fx'], t0, x, g, pan)
        if kind in ('shot', 'shot_big', 'slam', 'slash_big', 'clang_big', 'burst_big', 'click', 'clack'):
            put(verb_send, t0, x, g * 0.35, pan)

    return mus, verb_send


def make_sfx(kind):
    def T(sec):
        n = int(sec * SR)
        return n, tt(n)

    if kind == 'whoosh' or kind == 'dash':
        L = 0.35 if kind == 'whoosh' else 0.8
        n, t = T(L)
        u = t / L
        fc = 300 + 5000 * np.sin(np.pi * u) ** 2
        y = sweep_lp(noise(n), fc) * np.sin(np.pi * u) ** 1.5
        return y * 0.5
    if kind in ('slash', 'slash_big', 'slash_soft'):
        big = kind == 'slash_big'
        n, t = T(1.4 if big else 0.6)
        y = filt(noise(n), 'hp', 3000) * np.exp(-t * 35) * 0.9
        for f in [2200, 3300, 4700, 6100]:
            y += np.sin(2 * np.pi * f * (1 + rng.random() * 0.02) * t) * np.exp(-t * (9 if big else 18)) * 0.12
        if big:
            b_ = boom(0.8, 1.0, 70)
            y[:len(b_)] += b_
        if kind == 'slash_soft':
            y = filt(y, 'lp', 2500) * 0.6
        return y
    if kind in ('shot', 'shot_big'):
        big = kind == 'shot_big'
        n, t = T(1.3)
        crack = noise(n) * np.exp(-t * 60) * 1.4
        body = filt(noise(n), 'lp', 1400) * np.exp(-t * 12) * 1.2
        low = boom(0.9 if big else 0.6, 1.3, 60)[:n]
        tail = filt(noise(n), 'bp', [300, 2500]) * np.exp(-t * 4) * 0.15
        y = np.tanh(1.8 * (crack + body + tail)) * 0.7 + low
        return y * (1.2 if big else 0.9)
    if kind == 'click':
        n, t = T(0.15)
        y = filt(noise(n), 'hp', 2000) * np.exp(-t * 250)
        y += np.sin(2 * np.pi * 3100 * t) * np.exp(-t * 120) * 0.4
        return y * 0.7
    if kind == 'clack':
        n, t = T(0.4)
        y = filt(noise(n), 'bp', [800, 6000]) * np.exp(-t * 90)
        y += np.sin(2 * np.pi * 1450 * t) * np.exp(-t * 40) * 0.4
        y += np.sin(2 * np.pi * 2300 * t) * np.exp(-t * 30) * 0.25
        y += boom(0.3, 0.4, 90)[:n]
        return y * 0.9
    if kind in ('clang', 'clang_big'):
        big = kind == 'clang_big'
        n, t = T(1.8 if big else 1.0)
        y = np.zeros(n)
        for f, d in [(620, 3), (1370, 4), (2210, 5), (3180, 7), (4630, 9)]:
            y += np.sin(2 * np.pi * f * t) * np.exp(-t * d * (0.6 if big else 1)) * 0.2
        y += filt(noise(n), 'hp', 2000) * np.exp(-t * 50) * 0.8
        if big:
            b_ = boom(0.9, 1.5, 50)
            y[:len(b_)] += b_
        return y
    if kind in ('burst', 'burst_big'):
        big = kind == 'burst_big'
        L = 2.2 if big else 1.1
        n, t = T(L)
        # crackle: sparse impulses through a bandpass, like shattering glass/embers
        imp = (rng.random(n) < 0.004 * np.exp(-t * (2.5 if big else 5))) * rng.standard_normal(n)
        cr = filt(imp, 'hp', 1500) * 2.0
        swish = sweep_lp(noise(n), 6000 * np.exp(-t * 3) + 200) * np.exp(-t * 3) * 0.5
        y = cr + swish + boom(1.1 if big else 0.6, L, 48)[:n]
        return y
    if kind == 'impact' or kind == 'kick':
        n, t = T(0.8)
        y = boom(0.8, 0.8, 80)[:n] + filt(noise(n), 'lp', 2500) * np.exp(-t * 30) * 0.8
        return y
    if kind == 'slam':
        n, t = T(2.6)
        y = boom(1.3, 2.6, 42) + filt(noise(n), 'lp', 1200) * np.exp(-t * 3.5) * 0.8
        y += filt(noise(n), 'hp', 3000) * np.exp(-t * 25) * 0.6
        return y
    if kind == 'slide':
        n, t = T(0.7)
        y = filt(noise(n), 'bp', [400, 4000]) * np.exp(-t * 4) * (1 + 0.3 * np.sin(2 * np.pi * 23 * t))
        return y * 0.5
    if kind == 'growl':
        n, t = T(0.5)
        y = filt(noise(n), 'lp', 400) * (0.6 + 0.4 * np.sin(2 * np.pi * 31 * t)) * np.sin(np.pi * t / 0.5)
        return y * 0.8
    if kind == 'roar':
        n, t = T(1.2)
        f = 70 + 25 * np.sin(np.pi * t / 1.2)
        base = saw(f, n) * (1 + 0.5 * np.sin(2 * np.pi * 27 * t))
        y = filt(base, 'lp', 900) + filt(noise(n), 'bp', [200, 1800]) * 0.6
        y *= np.sin(np.pi * np.clip(t / 1.2, 0, 1)) ** 0.5
        return np.tanh(2 * y) * 0.6
    if kind == 'rise':
        n, t = T(0.9)
        fc = 300 + 7000 * (t / 0.9) ** 2
        return sweep_lp(noise(n), fc) * np.sin(np.pi * t / 0.9) * 0.4
    if kind == 'slowmo':
        # a low "time-stretch" drone + reverse whoosh
        n, t = T(0.9)
        y = saw(55 * (1 - 0.3 * t / 0.9), n) * 0.2 + sweep_lp(noise(n), 1500 * np.exp(-t * 3) + 100) * 0.5
        return filt(y, 'lp', 1500) * np.exp(-t * 1.5)
    raise ValueError(kind)


def reverb_ir(length=2.6, seed=3):
    r = np.random.default_rng(seed)
    n = int(length * SR)
    t = tt(n)
    ir = r.standard_normal((n, 2)) * np.exp(-t * 3.2)[:, None]
    # darken the tail
    ir = sweep_lp(ir, 9000 * np.exp(-t * 1.8) + 700)
    ir[:int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))[:, None]
    return ir / np.sqrt((ir ** 2).sum()) * 0.9


def conv(x, ir):
    y = np.zeros((len(x), 2))
    for c in range(2):
        y[:, c] = signal.fftconvolve(x[:, c], ir[:, c])[:len(x)]
    return y


def envelope(x, att=0.002, rel=0.12):
    a = np.abs(x).max(1) if x.ndim == 2 else np.abs(x)
    # simple 1-pole followers (block-decimated for speed)
    dec = 32
    a = a[: len(a) // dec * dec].reshape(-1, dec).max(1)
    ka = np.exp(-dec / (att * SR))
    kr = np.exp(-dec / (rel * SR))
    e = np.zeros_like(a)
    v = 0.0
    for i, s in enumerate(a):
        k = ka if s > v else kr
        v = k * v + (1 - k) * s
        e[i] = v
    e = np.repeat(e, dec)
    return np.pad(e, (0, len(x) - len(e)), mode='edge')


def mix():
    mus, send = build()
    # sidechain from kicks into pad/guitars/bass/wind
    kick_env = envelope(mus['drm'], 0.001, 0.09)
    kick_env /= kick_env.max() + 1e-9
    duck = 1 - 0.35 * kick_env[:, None]

    ir = reverb_ir()
    ir_long = reverb_ir(4.5, 9)
    gains = {'pno': 0.9, 'pad': 1.25, 'drm': 0.85, 'gtr': 0.55, 'bas': 0.6,
             'lead': 2.8, 'fx': 0.8, 'amb': 1.0}
    dry = new().astype(np.float64)
    wet_in = send.astype(np.float64) * 0.6
    long_in = np.zeros_like(dry)
    for k, g in gains.items():
        x = mus[k].astype(np.float64) * g
        if k in ('pad', 'gtr', 'bas', 'amb', 'lead'):
            x *= duck
        dry += x
        if k in ('pno', 'pad', 'lead'):
            long_in += x * (0.55 if k == 'pno' else 0.35)
        if k in ('gtr',):
            wet_in += x * 0.12
    out = dry + conv(wet_in, ir) * 0.5 + conv(long_in, ir_long) * 0.6

    # master: gentle glue compression + soft clip + limiter-ish normalise
    out = filt(out, 'hp', 28)
    env = envelope(out, 0.005, 0.25)
    thr = 0.35
    gr = np.where(env > thr, (thr / (env + 1e-9)) ** 0.5, 1.0)
    out *= gr[:, None]
    out = out / (np.abs(out).max() + 1e-9) * 1.3
    out = np.tanh(out)
    # tail fade
    t = tt(len(out))
    out *= np.clip((DUR + 0.3 - t) / 1.2, 0, 1)[:, None]
    out = out / np.abs(out).max() * 0.94
    return out.astype(np.float32), mus


def write_wav(path, x):
    x16 = (np.clip(x, -1, 1) * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(x16.tobytes())


if __name__ == '__main__':
    import os, time
    os.makedirs('out', exist_ok=True)
    t0 = time.time()
    out, mus = mix()
    out = out[:int(DUR * SR)]
    write_wav('out/ember.wav', out)
    print('wrote out/ember.wav', out.shape, f'{time.time() - t0:.1f}s')
    # per-bar loudness report
    for b in range(16):
        seg = out[int(B(b) * SR):int(B(b + 1) * SR)]
        print(f'bar {b:2d} rms {20 * np.log10(np.sqrt((seg ** 2).mean()) + 1e-9):6.1f} dB'
              f'  peak {20 * np.log10(np.abs(seg).max() + 1e-9):6.1f}')
