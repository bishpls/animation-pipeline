"""Laser lab: Falco short-hops and fires one laser on each airborne frame 1..13, with and without a fast fall at the apex, at
a standing Fox 40 units away. The director logs every laser's spawn (LASER s port x y angle speed) and every item hit (IHIT)."""
import sys
from dsl import Film, JUMPSQUAT

SLOT = 70
f = Film(len_s=60.0)
f.setup(players=[('fox', dict(x=-20, face=1)), ('falco', dict(x=20, face=-1))], seed=7)
P = [f.port(0), f.port(1)]
f.cam(0, eye=(0, 16, 140), at=(0, 12, 0), fov=30, ease='cut', track='mid')
js = JUMPSQUAT['falco']; k = 0
for ff in (False, True):
    for air in range(1, 14):
        t = 20 + k * SLOT; k += 1
        f.reset(t, 0, -20, 1); f.reset(t, 1, 20, -1); f.percent(t, 0, 0)
        f.mark(t, k, f"{'ff ' if ff else ''}laser on air frame {air}")
        P[1].jump(t + 10)
        if ff: P[1].hold(t + 10 + js + 11, 2, stick=(0, -80))         # the apex of Falco's short hop is ~11 frames up
        P[1].hold(t + 10 + js + air, 2, btn='B')
f.emit(sys.argv[1])
