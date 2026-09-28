"""Lab: Marth's forward smash against a standing Fox at a sweep of spacings, to find the tipper (the sword tip's stronger
hitbox, logged by damage). Each trial resets both on the floor, Fox at 0% (little knockback, so every trial starts clean),
Marth smashes (C-stick forward) 12 frames later. The HIT log's damage separates the tip from the blade; staling lowers both
over repeats but keeps their ratio."""
import os, sys
from dsl import Film
DS = [int(v) for v in os.environ.get('SOBACK_DS', '12,14,16,18,20,22,24,26,28,30').split(',')]
TR = 80
f = Film(len_s=(20 + TR * len(DS)) / 60)
f.setup(players=[('marth', dict(x=-20, face=1)), ('fox', dict(x=0, face=-1))], seed=7)
m, fx = f.port(0), f.port(1)
f.cam(0, eye=(0, 20, 220), at=(0, 14, 0), fov=40, ease='cut')
for k, d in enumerate(DS):
    t = 20 + k * TR
    f.reset(t, 0, -20, 1); f.reset(t, 1, -20 + d, -1); f.percent(t, 1, 0)
    f.mark(t, d)
    m.hold(t + 12, 2, c=(80, 0))
    fx.trace(t + 12, t + 40); m.trace(t + 12, t + 40)
f.emit(sys.argv[1])
