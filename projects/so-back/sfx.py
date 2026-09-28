"""SO BACK's game-sound stems from the picture's own cue list (src/sfx.js: SFX, pushed by the shot files; one clock): a thin
wrapper over tools/machinima/platesfx.py with SO BACK's paths.
    ../../.venv/bin/python sfx.py            # -> ~/games/melee/work/soback/sfx/{stem_tape,stem}.wav, then run mix.py
A cue is [film t, plate, plate t0 (s from its frame 1), dur, gain dB, bus, label]: the plate's own audio.wav (the capture's
game sound: SFX and voices, music off) from t0 for dur, placed at film t. gain is the cue's peak over the song's local RMS
(+-0.4 s), floored at -38 dBFS, like tools/sfxmix.py. bus 'tape' goes through the cold open's tape stop with the song;
'post' is added after it. Game-derived audio: the stems live outside the repo."""
import importlib.util, os
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(H))
_spec = importlib.util.spec_from_file_location('platesfx', os.path.join(ROOT, 'tools', 'machinima', 'platesfx.py'))
platesfx = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(platesfx)

if __name__ == '__main__':
    platesfx.build('projects/so-back', os.path.join(H, 'assets/song.wav'), os.path.expanduser('~/games/melee/work/soback/sfx'),
                   prefix='soback_', names={'tape': 'stem_tape.wav', 'post': 'stem.wav'}, buses=('tape', 'post'))
