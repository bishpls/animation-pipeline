"""Lab: Fox for the sacred combo.
  U  Fox's up-B (Firefox) from a double jump above the stage: the charge length, his motion while charging, the launch
  K  the knee's launch by percent, with survival DI: Falcon SHFFLs the knee (gap 8, fair on air frame 3, auto fast fall and
     L-cancel) into Fox standing near the right edge; Fox holds DI (default up-and-in, 135 degrees) from the frame after the hit until 16 frames later (hitlag).
     Percents ascend, so a KO only spoils the segments after it (a KO'd fighter can't be reset).
"""
import os, sys
from dsl import Film

DI = tuple(int(v) for v in os.environ.get('SOBACK_DI', '-56,56').split(','))
PCTS = [int(v) for v in os.environ.get('SOBACK_PCTS', '60,65,70,75,80,85,90,95,100').split(',')]
f = Film(len_s=40.0)
f.setup(players=[('falcon', dict(x=-80, face=1)), ('fox', dict(x=0, face=1))], seed=7)
fal, fox = f.port(0), f.port(1)
f.cam(0, eye=(0, 30, 330), at=(0, 10, 0), fov=40, ease='cut')
# U: full hop, double jump at air frame 12, up-B at the double jump's apex (stick neutral), let it launch straight up
f.reset(20, 1, 0, 1); fox.trace(21, 200); f.mark(20, 1, 'U Firefox after a double jump')
fox.hold(30, 6, btn='X'); fox.hold(45, 3, btn='X'); fox.hold(62, 2, stick=(0, 80), btn='B'); fox.hold(64, 40, stick=(0, 80))
fal.auto(0, fastfall=True, lcancel=True)
t = 240
for pct in PCTS:
    f.reset(t, 0, 30, 1); f.reset(t, 1, 38, -1); f.percent(t, 1, pct)
    fal.trace(t + 1, t + 208); fox.trace(t + 1, t + 150)
    f.mark(t, pct, f'K knee at {pct}%')
    fal.hold(t + 10, 2, btn='X'); fal.hold(t + 17, 2, c=(80, 0))      # hit lands about t + 31
    fox.hold(t + 32, 16, stick=DI)                       # DI only inside hitlag: before the hit, stick-up is a tap jump
    f.setpos(t + 150, 1, 0, 30)                          # rescue Fox onto the stage before he can be KO'd (a KO can't be reset)
    t += 210
f.emit(sys.argv[1])
