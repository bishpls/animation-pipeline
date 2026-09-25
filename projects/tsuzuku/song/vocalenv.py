"""Clawd's singing voice as a loudness envelope in song time (for lip-sync: a held note keeps the mouth open after its word's
timestamp ends). Sources and placements mirror assemble.py (draft 6): clC_2's vocal stem at bar 42; clI_2's at bar 125 with its
bars 17-20 cut. Output: assets/vocal_env.json {fps: 50, clawd: [0..1 per frame]} (normalised; ~0 where she's silent).
    ../../.venv/bin/python song/vocalenv.py
"""
import json, os, subprocess
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); A = lambda *p: os.path.join(HERE, '..', *p)
SR, FPS = 48000, 50; BAR = 60 / 170 * 4
def load(p):
    y = np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-i', p, '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'], capture_output=True).stdout, np.float32)
    return y
song_len = 212.0; env = np.zeros(int(song_len * FPS) + 1)
def place(stem, at, cut=None):
    y = load(stem)
    if cut: i17, i20 = int(cut[0] * BAR * SR), int(cut[1] * BAR * SR); y = np.concatenate([y[:i17], y[i20:]])
    hop = SR // FPS; n = len(y) // hop; r = np.sqrt((y[:n * hop].reshape(n, hop) ** 2).mean(1))
    i0 = int(round(at * FPS)); m = min(n, len(env) - i0); env[i0:i0 + m] = np.maximum(env[i0:i0 + m], r[:m])
place(A('assets', 'world4', 'clC_2_dm', 'vocals.wav'), 42 * BAR)
place(A('assets', 'world4', 'clI_2_dm', 'vocals.wav'), 125 * BAR, cut=(17, 20))
db = 20 * np.log10(env + 1e-6); lo, hi = np.percentile(db[db > -80], 20), np.percentile(db[db > -80], 97)
e = np.clip((db - lo) / (hi - lo), 0, 1); e = np.convolve(e, np.ones(3) / 3, 'same')
json.dump({'fps': FPS, 'clawd': [round(float(v), 3) for v in e]}, open(A('assets', 'vocal_env.json'), 'w'))
print('frames', len(e), 'voiced frac', round(float((e > .35).mean()), 3), 'dB range', round(lo, 1), round(hi, 1))
