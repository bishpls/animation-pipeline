"""Tech lab: the Melee tech the choreography needs, one test per slot, both fighters reset at 0%.
Read with tools/machinima/melee/report.py (hits) and tools/machinima/melee/framedata.py (landing lag, wavedash slides)."""
import sys
from dsl import Film

SLOT = 100
f = Film(len_s=60.0)
f.setup(players=[('fox', dict(x=-10, face=1)), ('falco', dict(x=10, face=-1))], seed=7)
P = [f.port(0), f.port(1)]
f.cam(0, eye=(0, 16, 120), at=(0, 12, 0), fov=30, ease='cut', track='mid')
slot = [0]
def new(label, fx=-10, flx=10, auto=None):
    t = 20 + slot[0] * SLOT; slot[0] += 1
    f.reset(t, 0, fx, 1 if fx < flx else -1); f.reset(t, 1, flx, -1 if fx < flx else 1)
    f.percent(t, 0, 0); f.percent(t, 1, 0)
    for i in (0, 1): f.cue(t, 'auto', i, auto if auto is not None else 0)
    f.mark(t, slot[0], label)
    return t

for jc in (5, 6, 7):
    for ad in (0, 1):
        t = new(f'waveshine jc {jc} airdodge +{ad}', -5, 5, auto=3)
        end = P[0].waveshine(t + 20, dir=1, jc_at=jc, ad=ad); P[1].di(t + 20, (0, -80))
        P[0].shine_hit(end + 1, dir=1); P[1].di(end + 1, (0, -80))
t = new('waveshine 3-3-2: shines at 0, 22.5, 45, usmash 67', -30, -25, auto=3)
b = t + 20
for k, off in enumerate((0, 22, 45)):
    P[0].waveshine(b + off, dir=1, ad=0, long=(k == 0)); P[1].di(b + off, (0, -80))
P[0].move(b + 67, 'usmash', dir=1)
t = new('falco low lasers x2', 10, 50, auto=0)
f.cue(t, 'auto', 1, 4)
P[1].jump(t + 20); P[1].jump(t + 50)
P[1].trace(t, t + 90)
f.emit(sys.argv[1])
