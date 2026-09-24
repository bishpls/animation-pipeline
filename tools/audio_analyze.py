"""Analyse a song take and write its cue sheet (the single clock the animation locks to).

    .venv/bin/python tools/audio_analyze.py TAKE.mp3 [--bpm 124] [--cues out.json] [--plot out.png]

Reads TAKE.events.jsonl (from tools/music.py) when present for sections + word timestamps.
Reports: tempo, beat-grid fit (how far detected beats drift from a fixed grid), seam jumps at section
boundaries (a spike = an audible join), loudness, and clipping. Writes cues:
  { bpm, offset (first downbeat, s), duration, beats[], downbeats[], sections[{name,t0,t1}], words[{w,t0,t1,section}],
    onsets[] (strong transients, for hits), rms[] (10 Hz envelope, for audio-reactive motion) }
"""
import json, os, re, sys
import numpy as np
import librosa

a = sys.argv[1:]
opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
path = a[0]
BPM = float(opt('--bpm', 124))
y, sr = librosa.load(path, sr=22050, mono=True)
dur = len(y) / sr

# ---- sections + words from the generator's metadata
sections, words = [], []
ev_path = re.sub(r'\.mp3$', '.events.jsonl', path)
if os.path.exists(ev_path):
    t = 0.0
    for line in open(ev_path):
        e = json.loads(line)
        if 'words_timestamps' not in e:
            continue
        c = e['chunk']
        name = re.match(r'\[([^\]]+)\]', c['text'])
        name = name.group(1) if name else f'chunk{e.get("index")}'
        t1 = t + c['duration_ms'] / 1000
        sections.append({'name': name, 't0': round(t, 3), 't1': round(t1, 3)})
        for w in e['words_timestamps']:
            if w['word'].startswith('{') or w['word'].endswith('}') or w['end_ms'] <= w['start_ms']:
                continue       # stage directions, not sung
            words.append({'w': w['word'], 't0': w['start_ms'] / 1000, 't1': w['end_ms'] / 1000, 'section': name})
        t = t1

# ---- beats: fit a fixed grid at BPM to the detected beats (the band plays to a click)
onset_env = librosa.onset.onset_strength(y=y, sr=sr)
tempo, beats = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr, start_bpm=BPM, tightness=400)
bt = librosa.frames_to_time(beats, sr=sr)
P = 60 / BPM
phase = np.angle(np.mean(np.exp(2j * np.pi * bt / P))) / (2 * np.pi) * P % P
resid = ((bt - phase + P / 2) % P) - P / 2
# which of the 4 beat phases carries the downbeat: the one with most low-end energy
S = np.abs(librosa.stft(y, n_fft=2048, hop_length=512))
low = S[:12].sum(0)
lt = librosa.frames_to_time(np.arange(len(low)), sr=sr, hop_length=512)
grid = np.arange(phase, dur, P)
score = [np.mean([low[np.argmin(np.abs(lt - g))] for g in grid[k::4]]) for k in range(4)]
down0 = grid[int(np.argmax(score))]
beats_grid = grid.tolist()
downbeats = [g for g in grid if abs(((g - down0) / P) % 4) < 1e-6 or abs(((g - down0) / P) % 4 - 4) < 1e-6]

# ---- seams: spectral jump across each section boundary vs typical frame-to-frame change
logS = np.log1p(S)
flux = np.r_[0, np.linalg.norm(np.diff(logS, axis=1), axis=0)]
med = np.median(flux)
seams = []
for s in sections[1:]:
    i = np.argmin(np.abs(lt - s['t0']))
    seams.append({'t': s['t0'], 'jump': round(float(flux[max(0, i - 2):i + 3].max() / med), 2)})

rms = librosa.feature.rms(y=y, frame_length=2205, hop_length=2205)[0]
on = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, units='time', backtrack=False)
strong = [float(t) for t in on if onset_env[librosa.time_to_frames(t, sr=sr)] > np.percentile(onset_env, 90)]

print(f'{os.path.basename(path)}  dur {dur:.2f}s  librosa tempo {float(np.atleast_1d(tempo)[0]):.2f}  grid {BPM} phase {phase:.3f}s')
print(f'  beat-grid fit: median |resid| {np.median(np.abs(resid)) * 1000:.0f} ms, 90th pct {np.percentile(np.abs(resid), 90) * 1000:.0f} ms')
print(f'  first downbeat {down0:.3f}s   peak {np.abs(y).max():.3f}   rms mean {rms.mean():.3f}')
print('  seams (flux/median; >6 is suspicious):', ' '.join(f"{s['t']:.1f}:{s['jump']}" for s in seams))

# drift over time: resid in 10 s windows
win = [(t0, np.median(resid[(bt >= t0) & (bt < t0 + 10)]) * 1000) for t0 in range(0, int(dur), 10) if ((bt >= t0) & (bt < t0 + 10)).sum() > 3]
print('  drift ms per 10s:', ' '.join(f'{int(t)}:{d:+.0f}' for t, d in win))

if opt('--cues'):
    json.dump({'bpm': BPM, 'offset': round(float(down0), 4), 'duration': round(dur, 3), 'beats': [round(b, 4) for b in beats_grid],
               'downbeats': [round(b, 4) for b in downbeats], 'detected_beats': [round(float(b), 4) for b in bt],
               'sections': sections, 'words': words, 'onsets': [round(t, 3) for t in strong],
               'rms': [round(float(r), 4) for r in rms]}, open(opt('--cues'), 'w'), indent=0)
    print('  wrote', opt('--cues'))
