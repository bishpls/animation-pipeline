"""Lab: Fox's path after the sacred combo's knee, to place his Firefox charge at the frozen moment. Falcon SHFFLs the knee
from a standstill (gap 8, fair on air frame 3) at x = KX; Fox holds DI up and in through hitlag; then per variant:
  n  no input in tumble (drift nothing), no double jump
  d  drift toward the stage from the end of hitstun (stick left)
  j  drift toward the stage and double-jump the moment hitstun ends
Fox is teleported back onto the stage at hit + 178 so a KO can't spoil the next segment."""
import os, sys
from dsl import Film

KX = float(os.environ.get('SOBACK_KX', '-60'))
PCTS = [int(v) for v in os.environ.get('SOBACK_PCTS', '80,90,100').split(',')]
f = Film(len_s=len(PCTS) * 3 * 200 / 60 + 1)
f.setup(players=[('falcon', dict(x=-80, face=1)), ('fox', dict(x=0, face=1))], seed=7)
fal, fox = f.port(0), f.port(1)
f.cam(0, eye=(0, 30, 330), at=(0, 10, 0), fov=40, ease='cut')
fal.auto(0, fastfall=True, lcancel=True)
t = 20
for pct in PCTS:
    for var in 'ndj':
        f.reset(t, 0, KX, 1); f.reset(t, 1, KX + 8, -1); f.percent(t, 1, pct)
        fox.trace(t + 1, t + 178)
        f.mark(t, pct * 10 + 'ndj'.index(var), f'{pct}% variant {var}')
        fal.hold(t + 10, 2, btn='X'); fal.hold(t + 17, 2, c=(80, 0))   # hit at t + 31
        fox.hold(t + 32, 16, stick=(-56, 56))
        if var in 'dj':
            fox.hold(t + 48, 130, stick=(-80, 0))                     # drift in (tumble ignores it until hitstun ends)
        f.setpos(t + 178, 1, 0, 30)
        t += 200
f.emit(sys.argv[1])
