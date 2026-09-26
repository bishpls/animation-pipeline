"""The paper world's sound-effects stem, and the song mixed with it for the cuts (song.mp3 itself is never touched).

    ../../../.venv/bin/python mix.py
        -> sound/cues.json (dumped from the picture: paperSfx(), one clock), assets/sfx_paper.wav (the stem),
           out/paper_mix.wav + .mp3 (song + stem: what the paper-world cuts carry)

Levels: each cue's gain (dB, in the cue sheet) is its peak relative to the song's own level around it (RMS over +-0.4 s), +30:
a -30 cue peaks at the local music level, a -20 cue 10 dB above it. In near-silence the reference floors at -38 dBFS. No ducking:
the song is untouched under them (Michael).
"""
import json, os, subprocess
import numpy as np, soundfile as sf
HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE); ROOT = os.path.dirname(os.path.dirname(PROJ)); SR = 48000
out = subprocess.run(['node', os.path.join(ROOT, 'engine', 'render.mjs'), 'projects/tsuzuku', '--loop=bridge', '--eval=JSON.stringify(paperSfx())'], cwd=ROOT, capture_output=True, text=True).stdout
cues = json.loads(json.loads([l for l in out.splitlines() if l.startswith('"[')][-1]))
json.dump(cues, open(os.path.join(HERE, 'cues.json'), 'w'), indent=0)
song, sr = sf.read(os.path.join(PROJ, 'assets', 'song.wav'), dtype='float32'); assert sr == SR
mono = song.mean(1); stem = np.zeros((len(song), 2), np.float32); lib = {}
for t, name, g in cues:
    if name not in lib: y, _ = sf.read(os.path.join(HERE, 'lib', name + '.wav'), dtype='float32'); lib[name] = y / (np.abs(y).max() + 1e-9)
    i = int(t * SR); w = mono[max(0, i - int(.4 * SR)):i + int(.4 * SR)]
    ref = max(20 * np.log10(np.sqrt((w ** 2).mean()) + 1e-9), -38)
    a = 10 ** ((ref + g + 30) / 20); y = lib[name] * a; n = min(len(y), len(stem) - i)
    if n > 0: stem[i:i + n] += y[:n, None]
sf.write(os.path.join(PROJ, 'assets', 'sfx_paper.wav'), stem, SR, subtype='PCM_24')
mix = song + stem; pk = np.abs(mix).max()
if pk > .99: mix *= .99 / pk
os.makedirs(os.path.join(PROJ, 'out'), exist_ok=True)
sf.write(os.path.join(PROJ, 'out', 'paper_mix.wav'), mix, SR, subtype='PCM_24')
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(PROJ, 'out', 'paper_mix.wav'), '-b:a', '256k', os.path.join(PROJ, 'out', 'paper_mix.mp3')], check=True)
print(f'{len(cues)} cues; stem peak {20 * np.log10(np.abs(stem).max() + 1e-9):.1f} dBFS; mix peak {20 * np.log10(np.abs(mix).max()):.1f} dBFS')
