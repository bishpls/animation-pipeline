"""Seat a song take on SO BACK's locked grid (the knee on 0.05, the punch on the drop at 12.85, every vocal on bt()), with
tools/songseat.py. Plan-f takes put the drop a bar late (their music box runs a bar longer before the riser), so the extra
is removed at the CONTINUE? downbeat (9.65), a bar line inside the music box; the riser then sits under READY? and the drop's
own downbeat lands on 12.85. The final song is take f3: --drop 14.443 (measured from its loudness jump).
    .venv/bin/python projects/so-back/song/assemble.py TAKE --drop S [--open S]   -> assets/takes/TAKE_seated.wav (48 kHz)"""
import argparse, os, sys
import numpy as np, soundfile as sf
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'tools'))
from songseat import decode, seat, SR

ap = argparse.ArgumentParser(); ap.add_argument('take'); ap.add_argument('--drop', type=float, required=True); ap.add_argument('--open', type=float, default=.05)
a = ap.parse_args()
x = decode(f'projects/so-back/assets/takes/{a.take}.mp3')
y, cut = seat(x, a.drop, drop_at=12.85, cut_at=9.65, open_=a.open, offset=.05, length=28.9)
sf.write(f'projects/so-back/assets/takes/{a.take}_seated.wav', y.astype(np.float32), SR, subtype='FLOAT')
print(f'{a.take}: drop downbeat {a.drop:.3f} -> 12.85, removed {cut:.3f} s at 9.65 (open lead {a.open - .05:+.3f}); '
      f'-> assets/takes/{a.take}_seated.wav')
