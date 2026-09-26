"""The one clock for *t*: the cue sheet, plus the loudness table the hills are drawn from.

    .venv/bin/python projects/t/build_cues.py

The song is take e2 (assets/song.mp3; song/plan_end.json: take d's first 24.057 s as a reference, plus a new ending), with its
first 50 ms trimmed (HEAD), so the downbeats fall at 0.007 + 2n s and the final hit at 30.007 s, 7 ms after the counter stops
at t = 30.000. The master (make.sh) trims the same 50 ms.

1. tools/audio_analyze.py on the trimmed song -> assets/cues.json. The grid is set at phase 0.007 s: the onsets sit on a 120 BPM
   grid at 0.057 s in the untrimmed take (median residual 6 ms, measured), and the tracker is unreliable in the sparse intro.
2. assets/env.js: the master's loudness (assets/master.wav, made first by make.sh: what you hear), 100 Hz, in dBFS: RMS over
   the 40 ms up to each sample (causal, so no hill rises before its hit). ridge() in src/film.js reads it.
3. assets/cues.js: the same cue sheet for the page.
"""
import json, os, subprocess
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
A = os.path.join(HERE, 'assets')
song = os.path.join(A, 'song.mp3')
HEAD = 0.050
trimmed = os.path.join(HERE, 'out', 'song_film.mp3')        # an analysis copy (no events file beside it)
os.makedirs(os.path.dirname(trimmed), exist_ok=True)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(HEAD), '-i', song, '-c:a', 'libmp3lame', '-b:a', '320k', trimmed], check=True)

subprocess.run([os.path.join(ROOT, '.venv/bin/python'), os.path.join(ROOT, 'tools/audio_analyze.py'), trimmed, '--bpm', '120',
                '--cues', os.path.join(A, 'cues.json')], check=True)
c = json.load(open(os.path.join(A, 'cues.json')))
PHASE, P = 0.007, 0.5
c['offset'] = PHASE
c['beats'] = [round(PHASE + i * P, 4) for i in range(int((c['duration'] - PHASE) / P) + 1)]
c['downbeats'] = c['beats'][::4]
c['sections'] = [{'name': n, 't0': a, 't1': b} for n, a, b in
                 [('Intro', 0, 8.007), ('Drop', 8.007, 16.007), ('Peak', 16.007, 24.007), ('Ending', 24.007, 30.007), ('Ring', 30.007, c['duration'])]]
c['grid_note'] = 'song trimmed by 0.050 s; grid set at phase 0.007 s (build_cues.py)'

master = os.path.join(A, 'master.wav')                   # what's heard (make.sh; already trimmed): the hills are drawn from it
raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', master, '-f', 'f32le', '-ac', '1', '-ar', '48000', '-'],
                     capture_output=True, check=True).stdout
y = np.frombuffer(raw, np.float32).astype(np.float64)
sr, hop, win = 48000, 480, 1920
cs = np.concatenate([[0], np.cumsum(y * y)])
env = []
for i in range(0, len(y) // hop):
    b = min(len(y), i * hop + 1); a = max(0, b - win)
    env.append(10 * np.log10((cs[b] - cs[a]) / max(1, b - a) + 1e-12))
env = [round(max(-90.0, e), 1) for e in env]
c['env_hz'] = 100
json.dump(c, open(os.path.join(A, 'cues.json'), 'w'), indent=0)
open(os.path.join(A, 'cues.js'), 'w').write('window.CUES = ' + json.dumps(c, indent=0) + ';\n')
open(os.path.join(A, 'env.js'), 'w').write('// the song\'s loudness in dBFS at 100 Hz, causal 40 ms RMS (build_cues.py): the hills are drawn from this\n'
                                           'window.ENV = ' + json.dumps(env, separators=(',', ':')) + ';\n')
print('offset', PHASE, 'downbeats', c['downbeats'][:4], '...', len(c['downbeats']), ' env', len(env), 'samples, range',
      min(env), max(env))
