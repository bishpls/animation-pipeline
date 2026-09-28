"""songseat: seat a song take on a picture that is already locked to a grid. Promoted from SO BACK.

When picture, vocals and cuts are locked to a beat grid (first downbeat, the drop's downbeat), a new take rarely lands its
sections on the same bars. Rather than chase a perfect take:
- align the take's first downbeat to the grid's;
- remove (or pad) audio at one bar line inside a quiet section, so the take's drop downbeat lands on the picture's drop.
The joins hide in the quiet (a music box, a riser, a silent beat), and a short equal-power crossfade avoids a click.

    .venv/bin/python tools/songseat.py TAKE --drop 14.443 --drop-at 12.85 --cut-at 9.65 [--open .05 --offset .05]
        [--len 28.9] [--out TAKE_seated.wav]
--drop is the take's own drop downbeat (s): measure it from the loudness jump. Onset detectors often pick a pickup or a
later bar, so check with --probe, which prints the take's dB per 50 ms and its onsets around a time.
--open is the take's first downbeat, --offset the grid's; --cut-at a bar line of the grid inside a quiet section (the removal
happens in the take at the matching time); --len pads or trims the output (48 kHz stereo float WAV).
"""
import argparse, subprocess
import numpy as np, soundfile as sf
SR = 48000


def decode(path, sr=SR, ch=2):
    raw = subprocess.run(['ffmpeg', '-v', 'quiet', '-i', path, '-ac', str(ch), '-ar', str(sr), '-f', 'f32le', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, ch).astype(float)


def seat(x, drop, drop_at, cut_at, open_=.05, offset=.05, length=None, fade=.03):
    """x: (n, 2) at SR. Returns the seated array and the seconds removed (negative = padded)."""
    lead = open_ - offset                         # the take's first downbeat -> the grid's
    cut = drop - lead - drop_at                   # seconds to remove at cut_at (film time)
    i0 = int((cut_at + lead) * SR); f = int(fade * SR)
    if cut >= 0:
        i1 = int((cut_at + lead + cut) * SR)
        u = np.linspace(0, np.pi / 2, f)[:, None]
        head, tail = x[:i0 + f].copy(), x[i1:].copy()
        head[-f:] = head[-f:] * np.cos(u) + tail[:f] * np.sin(u)
        y = np.concatenate([head, tail[f:]])
    else:                                         # the drop is early: pad silence at the cut
        y = np.concatenate([x[:i0], np.zeros((int(-cut * SR), 2)), x[i0:]])
    if lead > 0: y = y[int(lead * SR):]
    elif lead < 0: y = np.concatenate([np.zeros((int(-lead * SR), 2)), y])
    if length:
        n = int(length * SR); y = np.concatenate([y, np.zeros((max(0, n - len(y)), 2))])[:n]
    return y, cut


def probe(x, t, span=1.3):
    import librosa
    m = x.mean(1).astype(np.float32); m = librosa.resample(m, orig_sr=SR, target_sr=22050); sr = 22050
    rms = librosa.feature.rms(y=m, frame_length=512, hop_length=110)[0]; rt = np.arange(len(rms)) * 110 / sr
    db = 20 * np.log10(rms + 1e-6)
    print('dB per 50 ms from', round(t - span / 2, 2), ':', ' '.join(f'{db[(rt >= s) & (rt < s + .05)].mean():.0f}' for s in np.arange(t - span / 2, t + span / 2, .05)))
    env = librosa.onset.onset_strength(y=m, sr=sr, hop_length=256)
    on = librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=256, units='time')
    print('onsets:', np.round(on[(on > t - span / 2) & (on < t + span / 2)], 3))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('take'); ap.add_argument('--drop', type=float); ap.add_argument('--drop-at', type=float)
    ap.add_argument('--cut-at', type=float); ap.add_argument('--open', type=float, default=.05)
    ap.add_argument('--offset', type=float, default=.05); ap.add_argument('--len', type=float)
    ap.add_argument('--out'); ap.add_argument('--probe', type=float, help='print loudness and onsets around this time, then exit')
    a = ap.parse_args()
    x = decode(a.take)
    if a.probe is not None: probe(x, a.probe); raise SystemExit
    y, cut = seat(x, a.drop, a.drop_at, a.cut_at, a.open, a.offset, a.len)
    out = a.out or a.take.rsplit('.', 1)[0] + '_seated.wav'
    sf.write(out, y.astype(np.float32), SR, subtype='FLOAT')
    print(f'drop {a.drop:.3f} -> {a.drop_at}, {"removed" if cut >= 0 else "padded"} {abs(cut):.3f} s at {a.cut_at} '
          f'(open lead {a.open - a.offset:+.3f}); -> {out}')
