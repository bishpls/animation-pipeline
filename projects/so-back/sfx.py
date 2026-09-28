"""SO BACK's game-sound stems from the picture's own cue list (src/sfx.js: SFX, pushed by the shot files; one clock).
    ../../.venv/bin/python sfx.py            # -> ~/games/melee/work/soback/sfx/{stem_tape,stem}.wav, then run mix.py
A cue is [film t, plate, plate t0 (s from its frame 1), dur, gain dB, bus, label]: the plate's own audio.wav (the capture's
game sound: SFX and voices, music off) from t0 for dur, placed at film t. gain is the cue's peak over the song's local RMS
(+-0.4 s), floored at -38 dBFS, like tools/sfxmix.py. bus 'tape' goes through the cold open's tape stop with the song;
'post' is added after it. Game-derived audio: the stems live outside the repo."""
import json, os, subprocess
import numpy as np, soundfile as sf
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(H)); SR = 48000
OUT = os.path.expanduser('~/games/melee/work/soback/sfx'); PLATES = os.path.expanduser('~/games/melee/plates')

def cues():
    r = subprocess.run(['node', 'engine/render.mjs', 'projects/so-back', "--eval=JSON.stringify(SFX)"], cwd=ROOT, capture_output=True, text=True).stdout
    return json.loads(json.loads([l for l in r.splitlines() if l.startswith('"[')][-1]))

def song():
    raw = subprocess.run(['ffmpeg', '-v', 'quiet', '-i', os.path.join(H, 'assets/song.wav'), '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)

if __name__ == '__main__':
    C = cues(); m = song(); n = len(m); os.makedirs(OUT, exist_ok=True)
    stems = {'tape': np.zeros((n, 2)), 'post': np.zeros((n, 2))}; cache = {}
    for t, plate, t0, dur, g, bus, label in C:
        if plate not in cache:
            x, sr = sf.read(os.path.join(PLATES, f'soback_{plate}', 'v', 'audio.wav'), always_2d=True); assert sr == SR, (plate, sr)
            cache[plate] = x[:, :2] if x.shape[1] > 1 else np.repeat(x, 2, 1)
        x = cache[plate]; a, b = int(t0 * SR), int((t0 + dur) * SR)
        seg = x[max(0, a):b].copy()
        if a < 0: seg = np.concatenate([np.zeros((-a, 2)), seg])
        f = min(len(seg) // 4, int(.004 * SR)); seg[:f] *= np.linspace(0, 1, f)[:, None]
        f2 = min(len(seg) // 3, int(.03 * SR)); seg[-f2:] *= np.linspace(1, 0, f2)[:, None] ** 2
        i = int(t * SR); w = m[max(0, i - int(.4 * SR)):i + int(.4 * SR)]
        ref = max(20 * np.log10(np.sqrt((w ** 2).mean()) + 1e-9), -38)
        pk = np.abs(seg).max() + 1e-9; seg *= 10 ** ((ref + g) / 20) / pk
        j0 = max(0, i); k = min(n - j0, len(seg) - (j0 - i))
        if k > 0: stems[bus][j0:j0 + k] += seg[j0 - i:j0 - i + k]
        print(f'{t:6.2f}  {plate:16s} {label:40s} peak {20 * np.log10(np.abs(seg).max()):6.1f} dBFS ({bus})')
    for k, s in stems.items():
        sf.write(os.path.join(OUT, 'stem_tape.wav' if k == 'tape' else 'stem.wav'), s.astype(np.float32), SR, subtype='FLOAT')
    print(f'{len(C)} cues -> {OUT}')
