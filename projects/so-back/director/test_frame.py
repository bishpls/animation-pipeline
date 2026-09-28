"""Capture test: vertical framing (4:3 crop vs a 90-degree camera roll) and keying (stage hidden on a flat clear colour).
Segments of 2 s each; fighters reset at each segment start. ASPECT (env) sets DirSetup.aspect for the aspect test build."""
import os, sys
from dsl import Film

ASPECT = float(os.environ.get('SOBACK_ASPECT', '0'))
f = Film(len_s=10.0)
f.setup(players=[('fox', dict(x=-6, face=1)), ('falco', dict(x=6, face=-1))], seed=7, aspect=ASPECT)
fox, falco = f.port(0), f.port(1)
AT = (0, 14, 0)
segs = [  # (t0, roll, stage visible, bg colour, label)
    (0.0, 0, 1, (0, 0, 0), 'crop'),
    (2.0, 90, 1, (0, 0, 0), 'roll'),
    (4.0, 90, 0, (0, 255, 0), 'green'),
    (6.0, 90, 0, (0, 0, 255), 'blue'),
]
for i, (t0, roll, vis, bg, label) in enumerate(segs):
    if t0 > 0:
        f.reset(t0, 0, -6, 1); f.reset(t0, 1, 6, -1)
    f.cue(t0, 'stage', a=vis); f.cue(t0, 'bgcolor', a=bg[0], b=bg[1], c=bg[2])
    d = 166 if (roll == 0 or ASPECT) else 124
    f.cam(t0, eye=(0, AT[1] + 4, d), at=AT, fov=30, roll=roll, ease='cut')
    f.mark(t0, i + 1, label)
    fox.move(t0 + 0.4, 'shine')
    falco.move(t0 + 0.9, 'laser', dir=-1)
    fox.move(t0 + 1.4, 'shine')
# the FD background alone: stage visible, the camera looking up and away from the stage
f.reset(8.0, 0, -6, 1); f.reset(8.0, 1, 6, -1)
f.cue(8.0, 'stage', a=1); f.cue(8.0, 'bgcolor', a=0, b=0, c=0)
f.cam(8.0, eye=(0, 30, 120), at=(0, 160, -300), fov=40, roll=90, ease='cut')
f.cam(9.0, eye=(0, 30, 120), at=(120, 60, -300), fov=40, roll=90, ease='cut')
f.mark(8.0, 9, 'fdbg')
f.emit(sys.argv[1])
