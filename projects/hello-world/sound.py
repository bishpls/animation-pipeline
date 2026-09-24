"""HELLO, WORLD!: song + sound design -> assets/mix.wav. Events in assets/sfx.json [{file, t, gain}] (film times)."""
import json, os, subprocess
import numpy as np, soundfile as sf
HERE = os.path.dirname(os.path.abspath(__file__)); A = lambda *p: os.path.join(HERE, 'assets', *p); SR = 48000
def load(path, ch=2):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', str(ch), '-ar', str(SR), '-'], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, ch)
mix = load(A('song.wav')).copy()
for e in json.load(open(A('sfx.json'))):
    y = load(A('sfx', e['file'])); i = int(e['t'] * SR); n = min(len(y), len(mix) - i)
    if n > 0: mix[i:i + n] += y[:n] * e.get('gain', .5)
pk = np.abs(mix).max(); mix *= min(1, .98 / pk)
sf.write(A('mix.wav'), mix, SR, subtype='PCM_24'); print('mix.wav peak', round(float(pk), 3))
