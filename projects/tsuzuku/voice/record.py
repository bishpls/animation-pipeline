"""Record Fable's spoken lines (voice/lines.json, her own direction) in a cast voice. Two takes per line; the chosen take is
trimmed of edge silence and written to voice/fable_<cast>/<id>.wav (take 1 unless it overruns the line's max_s window).

    ../../.venv/bin/python voice/record.py lily|hi3
"""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
import numpy as np, soundfile as sf
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'tools'))
from tts import tts
CAST = {'lily': 'pFZP5JQG7iQjIQuC4Bku', 'hi3': 'ohvQvtRc4bkWyUb7rF6x'}
cast = sys.argv[1]; D = os.path.join(HERE, f'fable_{cast}'); os.makedirs(os.path.join(D, 'takes'), exist_ok=True)
L = [l for l in json.load(open(os.path.join(HERE, 'lines.json')))['lines'] if l['id'] != 'f_aside']   # the aside is a margin note now

def take(job):
    l, k = job; out = os.path.join(D, 'takes', f"{l['id']}_{k}")
    if not os.path.exists(out + '.mp3'): tts(l['text'], out, CAST[cast], 'eleven_v3', l['stability'], None, l.get('speed'))
    return out

def trimmed(p, SR=48000):
    y = np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-i', p, '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'], capture_output=True).stdout, np.float32)
    e = np.convolve(np.abs(y), np.ones(480) / 480, 'same'); on = np.where(e > e.max() * .03)[0]
    return y[max(0, on[0] - 960):on[-1] + 4800] if len(on) else y

with ThreadPoolExecutor(4) as ex: list(ex.map(take, [(l, k) for l in L for k in (1, 2)]))
for l in L:
    ys = [trimmed(os.path.join(D, 'takes', f"{l['id']}_{k}.mp3")) for k in (1, 2)]
    lim = l.get('max_s'); pick = 0 if not lim or len(ys[0]) / 48000 <= lim or len(ys[0]) <= len(ys[1]) else 1
    sf.write(os.path.join(D, l['id'] + '.wav'), ys[pick], 48000)
    print(f"{l['id']:12s} take {pick + 1}  {len(ys[pick]) / 48000:5.2f}s" + (f"  (max {lim}s, other {len(ys[1 - pick]) / 48000:.2f}s)" if lim else ''))

# fit: lines with a max_s window (counter-lines inside Clawd's chorus) get their internal pauses shortened, never time-stretched
def tighten(y, lim, SR=48000):
    if len(y) / SR <= lim: return y
    e = np.convolve(np.abs(y), np.ones(960) / 960, 'same'); quiet = e < e.max() * .04
    runs, i = [], 0
    while i < len(y):
        if quiet[i]:
            j = i
            while j < len(y) and quiet[j]: j += 1
            if i > 0 and j < len(y): runs.append((i, j))
            i = j
        else: i += 1
    for keep in (.6, .5, .42, .35, .28, .22, .16, .11):
        out, p = [], 0
        for a, b in runs:
            if b - a > keep * SR: out += [y[p:a + int(keep * SR / 2)]]; p = b - int(keep * SR / 2)
        z = np.concatenate(out + [y[p:]])
        if len(z) / SR <= lim: break
    return z
for l in L:
    if l.get('max_s'):
        p = os.path.join(D, l['id'] + '.wav'); y, _ = sf.read(p); z = tighten(y.astype(np.float32), l['max_s'])
        sf.write(p, z, 48000); print(f"  fit {l['id']:11s} {len(y) / 48000:.2f} -> {len(z) / 48000:.2f}s (max {l['max_s']})")
