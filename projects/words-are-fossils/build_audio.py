"""WORDS ARE FOSSILS: place the narration on the score's grid, duck the score under it, write the mix + VO cues.
    ../../.venv/bin/python build_audio.py   ->  assets/mix.wav, assets/vo_cues.js (window.VO = [...])
Each line starts at a planned film time (just after its section's downbeat); every spoken word gets an absolute time.
"""
import json, os
import subprocess
SR = 48000
import numpy as np, soundfile as sf

TEMPO = 1.07    # the narrator, 7% brisker (pitch preserved); word timestamps are rescaled to match
def load(path, mono=True, tempo=1.0):
    # decode anything with ffmpeg to float32 at SR (librosa's mp3 path hangs intermittently here)
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path] + (['-af', f'atempo={tempo}'] if tempo != 1 else []) + ['-f', 'f32le', '-ac', '1' if mono else '2', '-ar', str(SR), '-'], capture_output=True, check=True).stdout
    y = np.frombuffer(raw, np.float32)
    return y if mono else y.reshape(-1, 2)

HERE = os.path.dirname(os.path.abspath(__file__))
A = lambda *p: os.path.join(HERE, 'assets', *p)
# id -> film time the line starts (score sections: 0 intro, 6 window, 15 companion, 24 muscle, 33 disaster, 39 clue,
#                                  48 salary, 60 brain rot, 69 goodbye, 78 coda)
PLACE = {'00_intro': 1.35, '01_window': 6.9, '02_companion': 15.9, '03_muscle': 24.85, '04_disaster': 33.75,
         '05_clue': 39.85, '06_salary': 48.6, '07_brainrot': 60.5, '08_goodbye': 69.95, '09_outro': 79.2}

score = load(A('score.wav'), mono=False)
N = len(score) + SR
vo = np.zeros((N, 2), np.float32)
cues = []
script = dict(json.load(open(A('vo', 'script.json'))))
for k, t0 in PLACE.items():
    y = load(A('vo', k + '.mp3'), tempo=TEMPO)
    i = int(t0 * SR); vo[i:i + len(y)] += y[:, None] * [1, 1]
    al = json.load(open(A('vo', k + '.json')))
    cues.append({'id': k, 't0': t0, 't1': t0 + len(y) / SR, 'text': script[k],
                 'words': [{'w': w['w'], 't0': round(t0 + w['t0'] / TEMPO, 3), 't1': round(t0 + w['t1'] / TEMPO, 3)} for w in al['words']]})

# duck: a smooth envelope that dips the score ~5 dB wherever the voice is speaking
env = np.abs(vo[:, 0])
win = int(SR * .25)
def movavg(x, n):             # moving average in O(N) (np.convolve with a long box is O(N*n): minutes)
    c = np.cumsum(np.r_[np.zeros(n // 2 + 1), x, np.zeros(n)]); return (c[n:n + len(x)] - c[:len(x)]) / n
env = movavg(env, win)
duck = 1 - .45 * np.clip(env / .02, 0, 1)
duck = movavg(duck, int(SR * .3))
mix = np.zeros((N, 2), np.float32)
mix[:len(score)] += score * duck[:len(score), None]
mix += vo * 1.0
# optional sound design layer (stone, chisel, brush), placed by sfx.json [{file, t, gain}]
if os.path.exists(A('sfx.json')):
    for e in json.load(open(A('sfx.json'))):
        y = load(A('sfx', e['file']))
        i = int(e['t'] * SR); n = min(len(y), N - i)
        mix[i:i + n] += (y[:n] * e.get('gain', .5))[:, None] * [1, 1]
mix = mix[:int((len(score) / SR + .2) * SR)]
peak = np.abs(mix).max(); mix *= min(1, .97 / peak)
sf.write(A('mix.wav'), mix, SR, subtype='PCM_24')
open(A('vo_cues.js'), 'w').write('window.VO = ' + json.dumps(cues) + ';\n')
print('wrote mix.wav', round(len(mix) / SR, 2), 's, peak', round(float(peak), 3), '|', ' '.join(f"{c['id']}:{c['t0']}-{c['t1']:.1f}" for c in cues))
