"""Clawd's singing voice as a loudness envelope in song time (for lip-sync: a held note keeps the mouth open after its word's
timestamp ends). Sources and placements mirror assemble.py (draft 6): clC_2's vocal stem at bar 42; clI_2's at bar 125 with its
bars 17-20 cut. Output: assets/vocal_env.json {fps: 50, clawd: [0..1 per frame]} (normalised; ~0 where she's silent).
The envelope itself is tools/vocalenv.py; this file holds the film's placements.
    ../../.venv/bin/python song/vocalenv.py
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); A = lambda *p: os.path.join(HERE, '..', *p)
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'tools'))
from vocalenv import SR, load, envelope  # noqa: E402
FPS = 50; BAR = 60 / 170 * 4
cut = lambda y, b0, b1: np.concatenate([y[:int(b0 * BAR * SR)], y[int(b1 * BAR * SR):]])
e, lo, hi = envelope([(load(A('assets', 'world4', 'clC_2_dm', 'vocals.wav')), 42 * BAR),
                      (cut(load(A('assets', 'world4', 'clI_2_dm', 'vocals.wav')), 17, 20), 125 * BAR)], 212.0, FPS)
json.dump({'fps': FPS, 'clawd': [round(float(v), 3) for v in e]}, open(A('assets', 'vocal_env.json'), 'w'))
print('frames', len(e), 'voiced frac', round(float((e > .35).mean()), 3), 'dB range', round(lo, 1), round(hi, 1))
