"""SO BACK's mix: the instrumental (assets/song.wav: take f3, seated by song/assemble.py), the announcer vocal stem and the SFX stem on the one clock, with the tape stop that drags
the cold open (instrumental and vocals together) to a halt on the last beat before the "over" section.
    ../../.venv/bin/python mix.py [--vox STEM] [--sfx STEM] [--out assets/mix.wav]
Stems are 48 kHz WAVs whose sample 0 is film time 0. The vocal stem is game-derived (the announcer's recordings): it lives
in ~/games/melee/work/soback/, and assets/mix.wav is gitignored."""
import argparse, os, subprocess
import numpy as np, soundfile as sf
H = os.path.dirname(os.path.abspath(__file__)); SR = 48000
TS0, TS1 = 2.85, 3.25          # the tape stop: beat 7 of the cold open to the "over" downbeat (bar 3)


import sys
sys.path.insert(0, os.path.join(H, '..', '..', 'tools'))
from mixkit import decode, stem, tape_stop, limit, duck, carve, sections   # tools/mixkit.py


# take f3's music box is fuller than c4's: the "over" section sits 5 dB down under the sad vocals (it should be sparse)
SONG_SECTIONS = [(3.25, 9.65, -5.0)]

BACKS = [.05 + .4 * b for b in (2, 6, 35, 42, 54)]      # the hook's "back" (bt(2), the echo bt(6), bt(35), bt(42), bt(54))

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--vox', default=os.path.expanduser('~/games/melee/work/soback/vocals/stem.wav'))
    ap.add_argument('--sfx', default=os.path.expanduser('~/games/melee/work/soback/sfx/stem.wav'))
    ap.add_argument('--sfx_tape', default=os.path.expanduser('~/games/melee/work/soback/sfx/stem_tape.wav'))
    ap.add_argument('--vox_db', type=float, default=-2.5); ap.add_argument('--sfx_db', type=float, default=0.0)
    ap.add_argument('--out', default=os.path.join(H, 'assets/mix.wav'))
    ap.add_argument('--song', default=os.path.join(H, 'assets/song.wav'))   # take f3, seated on the grid (song/assemble.py)
    ap.add_argument('--duck', type=float, default=3.0)
    ap.add_argument('--carve', type=float, default=0.0)          # (off: it didn't move the recognizer's back/bad)
    a = ap.parse_args()
    song = decode(a.song); n = len(song)
    vox = stem(a.vox, n) * 10 ** (a.vox_db / 20); sfx = stem(a.sfx, n) * 10 ** (a.sfx_db / 20)
    sfx_t = stem(a.sfx_tape, n) * 10 ** (a.sfx_db / 20)
    song = carve(song, BACKS, depth_db=a.carve) if a.carve < 0 else song
    song = sections(song, SONG_SECTIONS)
    bus = tape_stop(duck(song, vox, a.duck) + vox + sfx_t, TS0, TS1)
    mix = limit(bus + sfx)
    sf.write(a.out, mix.astype(np.float32), SR, subtype='FLOAT')
    rms = lambda s: 20 * np.log10(np.sqrt((s ** 2).mean()) + 1e-9)
    print(f'wrote {a.out}: {n / SR:.2f}s, peak {20 * np.log10(np.abs(mix).max()):.1f} dBFS, rms {rms(mix):.1f} dB '
          f'(vox {"on" if vox.any() else "off"}, sfx {"on" if sfx.any() else "off"})')
