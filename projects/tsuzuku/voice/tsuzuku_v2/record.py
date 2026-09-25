"""Fable's last word, re-directed (Fable: つづく is heiban, low-high-high, no fall; "downward" fought the word). Four
directions x two takes, Lily, eleven_v3, stability .5, speed .9. Trimmed to voice/tsuzuku_v2/<k>_<take>.wav.

    ../../../../.venv/bin/python record.py
"""
import os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
import numpy as np, soundfile as sf
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', '..', '..', '..', 'tools'))
from tts import tts
LILY = 'pFZP5JQG7iQjIQuC4Bku'
DIR = {'1': '[dry, close to the mic, a small smile, the pitch stays up] …つづく。',
       '2': '[quiet, matter-of-fact, reading the last line on a page] …つづく。',
       '3': '[warm, almost amused, a half-breath first, to one person] …つづく。',
       '4': '[soft, level, unhurried; the last word of a bedtime story, left open] …つづく。'}
def take(job):
    k, n = job; out = os.path.join(HERE, 'takes', f'{k}_{n}')
    if not os.path.exists(out + '.mp3'): tts(DIR[k], out, LILY, 'eleven_v3', .5, None, .9)
    return out
os.makedirs(os.path.join(HERE, 'takes'), exist_ok=True)
with ThreadPoolExecutor(4) as ex: outs = list(ex.map(take, [(k, n) for k in DIR for n in (1, 2)]))
for o in outs:
    y = np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-i', o + '.mp3', '-f', 'f32le', '-ac', '1', '-ar', '48000', '-'], capture_output=True).stdout, np.float32)
    e = np.convolve(np.abs(y), np.ones(480) / 480, 'same'); on = np.where(e > e.max() * .03)[0]
    y = y[max(0, on[0] - 960):on[-1] + 4800]; sf.write(os.path.join(HERE, os.path.basename(o) + '.wav'), y, 48000)
    print(os.path.basename(o), f'{len(y) / 48000:.2f}s')
