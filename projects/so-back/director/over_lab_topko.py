"""Lab (lane 2): top-blast-zone KOs. Fox (port 0) up-smashes Falcon (port 1) at a high percent on Final Destination, over and
over; the MS log shows which top KO the game rolled (motion 3 DeadUp = plain blast, 4 DeadUpStar = star, 6 DeadUpFall = the
screen KO, 7 = hitting the glass) and when. A wide fixed camera; Falcon's position traced."""
import sys
from dsl import Film

N, EVERY = 8, 420
f = Film(len_s=(60 + N * EVERY) / 60)
f.setup(players=[('fox', dict(x=-6, face=1)), ('falcon', dict(x=6, face=-1))], seed=7)
fox, fal = f.port(0), f.port(1)
f.cam(0, eye=(0, 80, 520), at=(0, 80, 0), fov=45, ease='cut')
for k in range(N):
    t0 = 30 + k * EVERY
    f.reset(t0, 0, -6, 1); f.reset(t0, 1, 6, -1)
    f.percent(t0, 1, 150); f.percent(t0, 0, 0)
    f.mark(t0, k + 1, f'attempt {k + 1}')
    fox.move(t0 + 30, 'usmash')
    fal.trace(t0 + 20, t0 + 200)
f.emit(sys.argv[1])
