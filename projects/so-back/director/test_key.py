"""Capture test: keying. The stage hidden throughout. Script frames 0-63 flash a frame counter in the clear colour
(R = 4 s, G = 60) so the capture can be checked frame by frame; from frame 64 the clear colour is SOBACK_BG (env, 'r,g,b') and
the fighters act (Fox's shine, Falco's laser and side-B), with the camera rolled 90 degrees (the portrait sensor).
Built twice with different SOBACK_BG, the two deterministic captures give a difference matte."""
import os, sys
from dsl import Film

BG = [float(v) for v in os.environ.get('SOBACK_BG', '0,255,0').split(',')]
ROLL = float(os.environ.get('SOBACK_ROLL', '90'))
ASPECT = float(os.environ.get('SOBACK_ASPECT', '0'))   # 9/16: the projection itself is portrait (use with SOBACK_ROLL=0)   # 0: the same framing as a centred 9:16 crop of a 4:3 frame
f = Film(len_s=5.0)
f.setup(players=[('fox', dict(x=-5, face=1)), ('falco', dict(x=5, face=-1))], seed=7, aspect=ASPECT)
fox, falco = f.port(0), f.port(1)
f.cue(0, 'stage', a=0)
for s in range(64):
    f.cue(s, 'bgcolor', a=4 * s, b=60, c=0)
f.cue(64, 'bgcolor', a=BG[0], b=BG[1], c=BG[2])
f.cam(0.0, eye=(0, 18, 124 if ROLL else 166), at=(0, 14, 0), fov=30, roll=ROLL, ease='cut')
fox.move(1.4, 'shine')
falco.move(2.0, 'laser', dir=-1)
f.reset(2.6, 0, -20, 1); f.reset(2.6, 1, 20, -1)
falco.move(3.3, 'sideb', dir=-1)
fox.move(4.2, 'shine')
f.emit(sys.argv[1])
