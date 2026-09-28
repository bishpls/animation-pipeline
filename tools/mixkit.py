"""mixkit: helpers for a film's final mix, all numpy at 48 kHz stereo (arrays (n, 2), sample 0 = film time 0).
Promoted from SO BACK's mix.py.

    song = decode('assets/song.wav'); vox = stem('vox.wav', len(song))
    bus = tape_stop(duck(song, vox, 3) + vox, 2.85, 3.25)     # a tape stop: speed 1 -> 0 as (1-u)^2, then silence
    out = limit(sections(bus, [(3.25, 9.65, -5)]) + sfx)       # section levels, then a -1 dBFS lookahead limiter

- duck: sidechain the music under a vocal by its envelope (up to depth_db). A spliced consonant after a closure can escape
  it: the envelope releases in the gap.
- carve: a dynamic-EQ dip of a band at given times (e.g. to clear a masked consonant).
- sections: music level by section, with smooth ramps.
- tape_stop: time-varying resampling, so pitch falls with speed. Put the vocals and any SFX that should drag through the
  same bus.
- limit: a lookahead peak limiter (instant attack, exponential release); the output never exceeds ceil.
"""
import os, subprocess
import numpy as np, soundfile as sf
SR = 48000


def decode(p):
    raw = subprocess.run(['ffmpeg', '-v', 'quiet', '-i', p, '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)


def stem(p, n):
    if not p or not os.path.exists(p): return np.zeros((n, 2))
    x, sr = sf.read(p, always_2d=True); assert sr == SR, (p, sr)
    x = np.repeat(x, 2, 1) if x.shape[1] == 1 else x[:, :2]
    out = np.zeros((n, 2)); m = min(n, len(x)); out[:m] = x[:m]; return out


def tape_stop(x, t0, t1, curve=2.0):
    """Between t0 and t1 the playback speed falls from 1 to 0 as (1-u)^curve (pitch falls with it); after t1, silence until
    the original resumes at t1. The source consumed is the integral of the speed."""
    a, b = int(t0 * SR), int(t1 * SR); D = (b - a) / SR
    u = np.arange(b - a) / (b - a)
    pos = a + SR * D * (1 - (1 - u) ** (curve + 1)) / (curve + 1)         # source sample index at each output sample
    i = np.floor(pos).astype(int); f = (pos - i)[:, None]
    seg = x[i] * (1 - f) + x[np.minimum(i + 1, len(x) - 1)] * f
    seg *= np.cos(np.clip((u - .85) / .15, 0, 1) * np.pi / 2)[:, None] ** 2   # the last 15% fades (no click at the stop)
    y = x.copy(); y[a:b] = seg
    return y


def limit(x, ceil=10 ** (-1 / 20), look=.005, release=.08):
    """A lookahead peak limiter: the gain needed per sample (ceil / |x|), its minimum over the lookahead window, then an
    instant attack and an exponential release; output never exceeds ceil (-1 dBFS)."""
    from scipy.ndimage import minimum_filter1d
    from scipy.signal import lfilter
    need = np.minimum(1.0, ceil / (np.abs(x).max(1) + 1e-12))
    L = int(look * SR); g = minimum_filter1d(need, 2 * L + 1)
    a = np.exp(-1 / (release * SR)); out = np.empty_like(g); cur = 1.0
    for i in range(0, len(g), 64):                          # block-wise release (fast enough in numpy)
        blk = g[i:i + 64]; m = blk.min()
        cur = min(m, 1 - (1 - cur) * a ** 64); out[i:i + 64] = np.minimum(blk, cur)
    return x * out[:, None]


def duck(music, vox, depth_db=3.0, att=.01, rel=.15):
    """Sidechain: the music dips by up to depth_db while the vocal sounds (its envelope, normalised to its loud parts)."""
    from scipy.signal import lfilter
    env = np.abs(vox).max(1)
    a = np.exp(-1 / (rel * SR)); env = lfilter([1 - a], [1, -a], env)
    env = np.clip(env / (np.percentile(env[env > 1e-4], 90) + 1e-9), 0, 1) if (env > 1e-4).any() else env
    g = 10 ** (-depth_db * env / 20)
    return music * g[:, None]


def carve(music, times, lo=1800, hi=7000, depth_db=-12.0, dur=.35, fade=.03):
    """A dynamic-EQ dip: the music's lo-hi band cut by depth_db over [t, t + dur] (smooth edges) at each time. On the hook's
    "back" the word's /k/ is a short burst after a closure: the level ducking releases in the closure and a bright drop
    masks the burst ("we're so bad"); carving its band keeps it."""
    from scipy.signal import butter, sosfiltfilt
    band = sosfiltfilt(butter(4, [lo, hi], 'band', fs=SR, output='sos'), music, axis=0)
    g = np.zeros(len(music)); k = 1 - 10 ** (depth_db / 20)
    for t in times:
        a, b, f = int(t * SR), int((t + dur) * SR), int(fade * SR)
        env = np.ones(b - a); env[:f] = np.sin(np.linspace(0, np.pi / 2, f)) ** 2; env[-f:] = np.cos(np.linspace(0, np.pi / 2, f)) ** 2
        g[a:b] = np.maximum(g[a:b], env)
    return music - band * (k * g)[:, None]

def sections(x, gains, ramp=.08):
    """Music level by section: gains [(t0, t1, dB)], smooth ramps at the edges."""
    g = np.zeros(len(x))
    for a, b, d in gains:
        i, j, r = int(a * SR), int(b * SR), int(ramp * SR)
        env = np.ones(j - i); env[:r] = np.linspace(0, 1, r); env[-r:] = np.linspace(1, 0, r)
        g[i:j] += d * env
    return x * (10 ** (g / 20))[:, None]
