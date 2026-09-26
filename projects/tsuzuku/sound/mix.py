"""The paper world's sound-effects stem, and the song mixed with it for the cuts (song.mp3 itself is never touched).

    ../../../.venv/bin/python mix.py              (tools/sfxmix.py with this film's paths)
        -> sound/cues.json (dumped from the picture: paperSfx(), one clock), assets/sfx_paper.wav (the stem),
           out/paper_mix.wav + .mp3 (song + stem: what the paper-world cuts carry)

Levels: each cue's gain (dB, in the cue sheet) is its peak relative to the song's own level around it (RMS over +-0.4 s), +30:
a -30 cue peaks at the local music level, a -20 cue 10 dB above it. In near-silence the reference floors at -38 dBFS. No ducking:
the song is untouched under them (Michael).
"""
import os, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'); sys.path.insert(0, os.path.join(ROOT, 'tools'))
from sfxmix import mix  # noqa: E402
mix('projects/tsuzuku', 'JSON.stringify(paperSfx())', 'sound/lib', loop='bridge', song='assets/song.wav', cues='sound/cues.json',
    stem='assets/sfx_paper.wav', out='out/paper_mix.wav')
