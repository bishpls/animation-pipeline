"""A singer's loudness envelope in song time, for lip-sync: the mouth follows the voice, so a held note keeps it open after its
word's timestamp ends (docs/MOTION.md, "Lip-sync").

    .venv/bin/python tools/vocalenv.py OUT.json --len=SECONDS VOCALS.wav[@AT] [MORE.wav@AT ...] [--key=voice] [--fps=50]

Each input is a vocal stem (tools/stems.py splits one from a song or a take) placed at AT song seconds (default 0); where
stems overlap the louder wins. Output {fps, <key>: [0..1 per frame]}: RMS per frame in dB, normalised between the 20th and
97th percentiles of the voiced frames and smoothed over 3 frames, so ~0 where the singer is silent.
From a film's script: from vocalenv import load, envelope; envelope([(load(path), at), ...], song_len, fps) (cut or edit
the loaded stems first when the song used them that way).
"""
import json, subprocess, sys
import numpy as np
SR = 48000


def load(p):
    """a stem as mono float32 at 48 kHz"""
    return np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-i', p, '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'], capture_output=True).stdout, np.float32)


def envelope(placed, song_len, fps=50):
    """placed: [(mono samples, song seconds)]. Returns (envelope 0..1 per frame, dB at 0, dB at 1)"""
    env = np.zeros(int(song_len * fps) + 1)
    for y, at in placed:
        hop = SR // fps; n = len(y) // hop; r = np.sqrt((y[:n * hop].reshape(n, hop) ** 2).mean(1))
        i0 = int(round(at * fps)); m = min(n, len(env) - i0); env[i0:i0 + m] = np.maximum(env[i0:i0 + m], r[:m])
    db = 20 * np.log10(env + 1e-6); lo, hi = np.percentile(db[db > -80], 20), np.percentile(db[db > -80], 97)
    e = np.clip((db - lo) / (hi - lo), 0, 1); e = np.convolve(e, np.ones(3) / 3, 'same')
    return e, lo, hi


if __name__ == '__main__':
    a = sys.argv[1:]; kw = dict(x[2:].split('=', 1) for x in a if x.startswith('--')); files = [x for x in a[1:] if not x.startswith('--')]
    fps = int(kw.get('fps', 50)); placed = [(load(f.rsplit('@', 1)[0]), float(f.rsplit('@', 1)[1]) if '@' in f else 0.) for f in files]
    e, lo, hi = envelope(placed, float(kw['len']), fps)
    json.dump({'fps': fps, kw.get('key', 'voice'): [round(float(v), 3) for v in e]}, open(a[0], 'w'))
    print('frames', len(e), 'voiced frac', round(float((e > .35).mean()), 3), 'dB range', round(lo, 1), round(hi, 1))
