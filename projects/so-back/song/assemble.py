"""Seat a song take on SO BACK's locked grid (the knee on 0.05, the punch on the drop at 12.85, every vocal on bt()).
Plan-f takes put the drop a bar late (their music box runs a bar longer before the riser), so one span of the "over"
section is removed at the CONTINUE? downbeat (9.65), a bar line, with a short equal-power crossfade; the riser then sits
under READY? and the drop's own downbeat lands on 12.85. The cold open is aligned by its first downbeat to 0.05.
    .venv/bin/python projects/so-back/song/assemble.py TAKE [--drop S] [--open S]   -> assets/takes/TAKE_seated.wav (48 kHz)
--drop: the take's drop downbeat (s); default: the strongest onset within 60 ms of a 0.05-phase bar line after 13.5 s."""
import argparse, subprocess, numpy as np, soundfile as sf, librosa
SR = 48000; BAR = 1.6; CUT_AT = 9.65; DROP = 12.85
ap = argparse.ArgumentParser(); ap.add_argument('take'); ap.add_argument('--drop', type=float); ap.add_argument('--open', type=float, default=.05)
a = ap.parse_args()
raw = subprocess.run(['ffmpeg', '-v', 'quiet', '-i', f'projects/so-back/assets/takes/{a.take}.mp3', '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True).stdout
x = np.frombuffer(raw, np.float32).reshape(-1, 2).astype(float)
mono = x.mean(1)
if a.drop is None:
    env = librosa.onset.onset_strength(y=mono.astype(np.float32), sr=SR, hop_length=512)
    on = librosa.onset.onset_detect(onset_envelope=env, sr=SR, hop_length=512, units='time')
    st = env[librosa.time_to_frames(on, sr=SR, hop_length=512)]
    bars = [a.open + k * BAR for k in range(8, 11)]
    cands = [(s, t) for t, s in zip(on, st) if t > 13.5 and min(abs(t - b) for b in bars) < .06]
    a.drop = max(cands)[1]
lead = a.open - .05                                   # the take's first downbeat -> 0.05
cut = a.drop - lead - DROP                            # seconds to remove at 9.65 (in film time)
i0 = int((CUT_AT + lead) * SR); i1 = int((CUT_AT + lead + cut) * SR); f = int(.03 * SR)
u = np.linspace(0, np.pi / 2, f)[:, None]
head, tail = x[:i0 + f].copy(), x[i1:].copy()
head[-f:] = head[-f:] * np.cos(u) + tail[:f] * np.sin(u)
y = np.concatenate([head, tail[f:]])
if lead > 0: y = y[int(lead * SR):]
elif lead < 0: y = np.concatenate([np.zeros((int(-lead * SR), 2)), y])
n = int(28.9 * SR); y = np.concatenate([y, np.zeros((max(0, n - len(y)), 2))])[:n]
sf.write(f'projects/so-back/assets/takes/{a.take}_seated.wav', y.astype(np.float32), SR, subtype='FLOAT')
print(f'{a.take}: drop downbeat {a.drop:.3f} -> 12.85, removed {cut:.3f} s at 9.65 (open lead {lead:+.3f}); '
      f'-> assets/takes/{a.take}_seated.wav')
