"""A film's game-sound stems from its picture's own cue list, cut from each plate's own audio (one clock with the picture).
    .venv/bin/python tools/machinima/platesfx.py PROJECT --song SONG.wav --out DIR [--plates ~/games/melee/plates] [--prefix NAME_]
        [--expr 'JSON.stringify(SFX)'] [--bus post=stem.wav --bus tape=stem_tape.wav]
The page expression (engine/render.mjs --eval on PROJECT) returns the cues: [film t, plate, plate t0, dur, gain dB, bus, label].
Each cue is the plate's own audio.wav (a capture's game sound: SFX and voices; the director keeps music off; prep_plates.py
writes it) from t0 (seconds from its frame 1) for dur, placed at film t, with a 4 ms fade-in and a 30 ms squared fade-out.
gain is the cue's peak over the song's local RMS (+-0.4 s), floored at -38 dBFS, as in tools/sfxmix.py: the song is never
touched. One stem per bus (48 kHz float WAV): a film mixes them where it needs them (SO BACK routes 'tape' through its tape
stop with the song and adds 'post' after it). Game-derived audio: keep --out outside the repo.
"""
import argparse, json, os, subprocess
import numpy as np, soundfile as sf
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); SR = 48000


def cues(project, expr='JSON.stringify(SFX)'):
    r = subprocess.run(['node', 'engine/render.mjs', project, f'--eval={expr}'], cwd=ROOT, capture_output=True, text=True).stdout
    return json.loads(json.loads([l for l in r.splitlines() if l.startswith('"[')][-1]))


def mono(path):
    raw = subprocess.run(['ffmpeg', '-v', 'quiet', '-i', path, '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)


def build(project, song, out, plates='~/games/melee/plates', prefix='', expr='JSON.stringify(SFX)', names=None, buses=()):
    """Write one stem per bus into out (names: {bus: filename}, default stem_<bus>.wav; buses: stems always written, even
    empty). Returns the cue list."""
    plates = os.path.expanduser(plates); names = dict(names or {})
    C = cues(project, expr); m = mono(song); n = len(m); os.makedirs(out, exist_ok=True)
    stems = {b: np.zeros((n, 2)) for b in buses}; cache = {}
    for t, plate, t0, dur, g, bus, label in C:
        if plate not in cache:
            x, sr = sf.read(os.path.join(plates, f'{prefix}{plate}', 'v', 'audio.wav'), always_2d=True); assert sr == SR, (plate, sr)
            cache[plate] = x[:, :2] if x.shape[1] > 1 else np.repeat(x, 2, 1)
        x = cache[plate]; a, b = int(t0 * SR), int((t0 + dur) * SR)
        seg = x[max(0, a):b].copy()
        if a < 0: seg = np.concatenate([np.zeros((-a, 2)), seg])
        f = min(len(seg) // 4, int(.004 * SR)); seg[:f] *= np.linspace(0, 1, f)[:, None]
        f2 = min(len(seg) // 3, int(.03 * SR)); seg[-f2:] *= np.linspace(1, 0, f2)[:, None] ** 2
        i = int(t * SR); w = m[max(0, i - int(.4 * SR)):i + int(.4 * SR)]
        ref = max(20 * np.log10(np.sqrt((w ** 2).mean()) + 1e-9), -38)
        pk = np.abs(seg).max() + 1e-9; seg *= 10 ** ((ref + g) / 20) / pk
        st = stems.setdefault(bus, np.zeros((n, 2)))
        j0 = max(0, i); k = min(n - j0, len(seg) - (j0 - i))
        if k > 0: st[j0:j0 + k] += seg[j0 - i:j0 - i + k]
        print(f'{t:6.2f}  {plate:16s} {label:40s} peak {20 * np.log10(np.abs(seg).max()):6.1f} dBFS ({bus})')
    for bus, s in stems.items():
        sf.write(os.path.join(out, names.get(bus, f'stem_{bus}.wav')), s.astype(np.float32), SR, subtype='FLOAT')
    print(f'{len(C)} cues -> {out}')
    return C


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('project'); ap.add_argument('--song', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--plates', default='~/games/melee/plates'); ap.add_argument('--prefix', default='')
    ap.add_argument('--expr', default='JSON.stringify(SFX)'); ap.add_argument('--bus', action='append', default=[])
    a = ap.parse_args()
    names = dict(b.split('=', 1) for b in a.bus)
    build(a.project, a.song, os.path.expanduser(a.out), a.plates, a.prefix, a.expr, names, tuple(names))
