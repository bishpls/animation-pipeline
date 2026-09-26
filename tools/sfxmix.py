"""A film's sound effects mixed over its song. The cue sheet comes from the picture (one clock), each cue sits at a level
relative to the song around it, and the song itself is never touched (no ducking).

    .venv/bin/python tools/sfxmix.py projects/<film> --eval='JSON.stringify(sfxCues())' --lib=sound/lib
        [--loop=NAME] [--song=assets/song.wav] [--cues=sound/cues.json] [--stem=assets/sfx.wav] [--mix=out/sfx_mix.wav]

The page expression (run by engine/render.mjs --eval, with --loop if the cue function lives on a loop's page) returns
[[t, name, gain], ...]: t in song seconds, name a sound in --lib (<name>.wav, 48 kHz; tools/sfx.py makes them), gain in dB.
A cue's gain is its peak relative to the song's own level around it (RMS over +-0.4 s), +30: a -30 cue peaks at the local
music level, a -20 cue 10 dB above it. In near-silence the reference floors at -38 dBFS.
Writes the cue sheet (json), the stem (24-bit wav), the song + stem mix (peak-limited to -0.1 dBFS) and an mp3 of the mix.
Paths are relative to the project. The song must be 48 kHz.
"""
import json, os, subprocess, sys
import numpy as np, soundfile as sf
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); SR = 48000


def mix(project, expr, lib, loop=None, song='assets/song.wav', cues='sound/cues.json', stem='assets/sfx.wav', out='out/sfx_mix.wav'):
    P = lambda p: os.path.join(ROOT, project, p)
    cmd = ['node', os.path.join(ROOT, 'engine', 'render.mjs'), project] + ([f'--loop={loop}'] if loop else []) + [f'--eval={expr}']
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True).stdout
    C = json.loads(json.loads([l for l in res.splitlines() if l.startswith('"[')][-1]))
    json.dump(C, open(P(cues), 'w'), indent=0)
    y0, sr = sf.read(P(song), dtype='float32'); assert sr == SR
    mono = y0.mean(1); st = np.zeros((len(y0), 2), np.float32); L = {}
    for t, name, g in C:
        if name not in L: y, _ = sf.read(os.path.join(P(lib), name + '.wav'), dtype='float32'); L[name] = y / (np.abs(y).max() + 1e-9)
        i = int(t * SR); w = mono[max(0, i - int(.4 * SR)):i + int(.4 * SR)]
        ref = max(20 * np.log10(np.sqrt((w ** 2).mean()) + 1e-9), -38)
        a = 10 ** ((ref + g + 30) / 20); y = L[name] * a; n = min(len(y), len(st) - i)
        if n > 0: st[i:i + n] += y[:n, None]
    sf.write(P(stem), st, SR, subtype='PCM_24')
    m = y0 + st; pk = np.abs(m).max()
    if pk > .99: m *= .99 / pk
    os.makedirs(os.path.dirname(P(out)), exist_ok=True)
    sf.write(P(out), m, SR, subtype='PCM_24')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', P(out), '-b:a', '256k', os.path.splitext(P(out))[0] + '.mp3'], check=True)
    print(f'{len(C)} cues; stem peak {20 * np.log10(np.abs(st).max() + 1e-9):.1f} dBFS; mix peak {20 * np.log10(np.abs(m).max()):.1f} dBFS')


if __name__ == '__main__':
    a = sys.argv[1:]; kw = dict(x[2:].split('=', 1) for x in a if x.startswith('--'))
    mix(a[0], kw.pop('eval'), kw.pop('lib'), **{('out' if k == 'mix' else k): v for k, v in kw.items()})
