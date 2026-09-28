"""SO BACK's mix: the instrumental (assets/song.wav: take f3, seated by song/assemble.py), the announcer vocal stem and the SFX stem on the one clock, with the tape stop that drags
the cold open (instrumental and vocals together) to a halt on the last beat before the "over" section.
    ../../.venv/bin/python mix.py [--vox STEM] [--sfx STEM] [--out assets/mix.wav]
Stems are 48 kHz WAVs whose sample 0 is film time 0. The vocal stem is game-derived (the announcer's recordings): it lives
in ~/games/melee/work/soback/, and assets/mix.wav is gitignored."""
import argparse, os, subprocess
import numpy as np, soundfile as sf
H = os.path.dirname(os.path.abspath(__file__)); SR = 48000
TS0, TS1 = 2.85, 3.25          # the tape stop: beat 7 of the cold open to the "over" downbeat (bar 3)


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

# take f3's music box is fuller than c4's: the "over" section sits 5 dB down under the sad vocals (it should be sparse)
SONG_SECTIONS = [(3.25, 9.65, -5.0)]

BACKS = [.05 + .4 * b for b in (2, 6, 35, 42, 54)]      # the hook's "back" (bt(2), the echo bt(6), bt(35), bt(42), bt(54))

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--vox', default=os.path.expanduser('~/games/melee/work/soback/vocals/stem.wav'))
    ap.add_argument('--sfx', default=os.path.expanduser('~/games/melee/work/soback/sfx/stem.wav'))
    ap.add_argument('--sfx_tape', default=os.path.expanduser('~/games/melee/work/soback/sfx/stem_tape.wav'))
    ap.add_argument('--vox_db', type=float, default=-2.5); ap.add_argument('--sfx_db', type=float, default=0.0)
    ap.add_argument('--out', default=os.path.join(H, 'assets/mix.wav'))
    ap.add_argument('--song', default=os.path.join(H, 'assets/song.wav'))   # take f3, seated on the grid (song/assemble.py)
    ap.add_argument('--duck', type=float, default=3.0)
    ap.add_argument('--carve', type=float, default=0.0)          # (off: it didn't move the recognizer's back/bad)
    a = ap.parse_args()
    song = decode(a.song); n = len(song)
    vox = stem(a.vox, n) * 10 ** (a.vox_db / 20); sfx = stem(a.sfx, n) * 10 ** (a.sfx_db / 20)
    sfx_t = stem(a.sfx_tape, n) * 10 ** (a.sfx_db / 20)
    song = carve(song, BACKS, depth_db=a.carve) if a.carve < 0 else song
    song = sections(song, SONG_SECTIONS)
    bus = tape_stop(duck(song, vox, a.duck) + vox + sfx_t, TS0, TS1)
    mix = limit(bus + sfx)
    sf.write(a.out, mix.astype(np.float32), SR, subtype='FLOAT')
    rms = lambda s: 20 * np.log10(np.sqrt((s ** 2).mean()) + 1e-9)
    print(f'wrote {a.out}: {n / SR:.2f}s, peak {20 * np.log10(np.abs(mix).max()):.1f} dBFS, rms {rms(mix):.1f} dB '
          f'(vox {"on" if vox.any() else "off"}, sfx {"on" if sfx.any() else "off"})')
