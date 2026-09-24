"""OPEN ALL NIGHT: sound design over the song, locked to the picture's own schedules.
The neon sign's clicks and hum are synthesized from the SAME stutter patterns S01 and S29 draw, so every click
lands on the frame a tube lights.   ../../.venv/bin/python sound.py  ->  assets/mix.wav
"""
import math, os
import numpy as np, soundfile as sf
from scipy.signal import butter, sosfilt

HERE = os.path.dirname(os.path.abspath(__file__))
song, SR = sf.read(os.path.join(HERE, 'assets/song.wav'), always_2d=True)
N = len(song)
fx = np.zeros((N, 2))
rng = np.random.default_rng(3)
FPS = 24

def hashj(n):  # engine/core.js hash()
    v = math.sin(n * 127.1 + 311.7) * 43758.5453123
    return v - math.floor(v)
BF = lambda t: math.floor(t * FPS / 2 + 1e-6)

def stutter(t, t0, pat):
    if t < t0: return 0
    v = 0
    for dt, on in pat:
        if t >= t0 + dt: v = on
    return v

DEF = [[0, 1], [.04, 0], [.12, 1], [.16, 0], [.26, 1], [.29, .35], [.33, 1]]
NPAT = [[0, 1], [.05, 0], [.09, .6], [.13, 0], [.22, 1]]
ON = [.14, .52, .74, .95]

def sign_state(t):
    if t < 3.977:                                    # S01
        L = [stutter(t, t0, NPAT if i == 3 else DEF) for i, t0 in enumerate(ON)]
        return L + [stutter(t, 2.02, [[0, 1], [.06, 0], [.1, 1]])]
    if 89.54 <= t < 91.95:                           # S29 storefront: one stutter before the end
        fl = (1 if hashj(BF(t) * 3.3) > .45 else 0) if t > 91.5 else 1
        return [fl] * 5
    return None

def click(t, amp, bright=6000):
    n = int(.018 * SR); i = int(t * SR)
    if i + n >= N: return
    e = np.exp(-np.arange(n) / (SR * .003))
    s = rng.standard_normal(n) * e
    s = sosfilt(butter(2, [600, bright], 'band', fs=SR, output='sos'), s)
    fx[i:i + n] += (s * amp)[:, None] * [1, .9]

# hum: 60 Hz family + a little arc noise, level follows how many tubes are lit (per video frame)
hum = np.zeros(N)
tt = np.arange(N) / SR
base = sum(a * np.sin(2 * np.pi * f * tt + p) for f, a, p in [(60, 1, 0), (120, .6, 1), (180, .35, 2), (240, .2, .5), (360, .12, 1.3)])
arc = sosfilt(butter(2, [2000, 7000], 'band', fs=SR, output='sos'), rng.standard_normal(N)) * .25
prev = [0] * 5
lvl = np.zeros(N)
for f in range(int(N / SR * FPS)):
    t = f / FPS
    st = sign_state(t)
    cur = st if st else [0] * 5
    for k in range(5):
        if cur[k] > .3 and prev[k] <= .3: click(t, .22 if k < 4 else .16)
        if cur[k] <= .3 and prev[k] > .3: click(t, .08, 3000)
    lvl[int(t * SR):int((t + 1 / FPS) * SR)] = sum(cur) / 5
    prev = cur
lvl = np.convolve(lvl, np.ones(int(SR * .004)) / int(SR * .004), mode='same')
hum = (base * .5 + arc) * lvl * .035
# the final death at 91.95: a heavier clunk, and the hum drops away
click(91.95, .35, 2500)
fx[:, 0] += hum; fx[:, 1] += hum * .95

mix = song + fx
peak = np.abs(mix).max()
if peak > .99: mix *= .99 / peak
sf.write(os.path.join(HERE, 'assets/mix.wav'), mix.astype(np.float32), SR, subtype='PCM_24')
print('wrote assets/mix.wav  peak', round(float(peak), 3))
