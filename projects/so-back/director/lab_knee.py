"""Lab: the SHFFL'd knee into Fox. Falcon (port 0) short-hops, fairs at a swept air frame, fast-falls on the first
descending frame and L-cancels (the director's closed-loop auto tech), into Fox (port 1) standing at a swept gap, 60%.
Logs: POS/HB for both, MS (motion states: the landing state and its length), HIT (damage 18 = the sweetspot, 6 = sour),
and Fox's hurtbox capsules while standing (SHIELD/HURT lines from the shield cue)."""
import sys
from dsl import Film

f = Film(len_s=90.0)
f.setup(players=[('falcon', dict(x=-80, face=1)), ('fox', dict(x=80, face=-1))], seed=7)
fal, fox = f.port(0), f.port(1)
f.cam(0, eye=(0, 30, 330), at=(0, 10, 0), fov=40, ease='cut')
fal.auto(0, fastfall=True, lcancel=True)
T = [20]
f.shield(18, 1)
for gap in (6, 8, 10, 12):
    for af in (1, 2, 3, 4, 5, 6, 7):
        t0 = T[0]
        f.reset(t0, 0, 0, 1); f.reset(t0, 1, gap, -1); f.percent(t0, 1, 60)
        fal.trace(t0 + 1, t0 + 70); fox.trace(t0 + 1, t0 + 70)
        f.mark(t0, gap * 10 + af, f'gap {gap} fair at air frame {af}')
        fal.hold(t0 + 10, 2, btn='X')                    # short hop: jumpsquat 4, airborne at t0+15
        fal.hold(t0 + 14 + af, 2, c=(80, 0))
        T[0] += 90
f.emit(sys.argv[1])
