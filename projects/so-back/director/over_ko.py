"""Lane 2 (SO BACK's "over" flashes): Falcon's top-blast KOs, "what if it goes wrong". Fox (port 0) up-smashes Falcon (port 1,
default costume) at 150% on Final Destination; the same exchange repeats and the game's own RNG rolls the KO kind each time
(lab over_lab_topko, seed 7): attempts 1, 3, 7 roll a STAR KO (motion 4), attempt 5 the SCREEN KO (motion 6, then 7 on the
glass); on the even attempts Falcon is still on the revival platform, so the reset is skipped. The fighter script is frozen:
cameras, aspect and the glass cue don't touch the RNG, so each attempt reproduces the lab's roll (checked in the MS log).

Film shots: STAR = attempt 1 (hit s 61), SCREEN = attempt 5 (hit s 1741). OVER_CAM (env) picks the camera set: 'game' (the game's own match camera, the vanilla check), 'lab' (side
view on attempt 1 to see the star's depth, wide fronts after) or 'film' (the portrait cameras)."""
import os, sys
from dsl import Film

N, EVERY, TAIL = 5, 420, 240
CAM = os.environ.get('OVER_CAM', 'film')
f = Film(len_s=(30 + (N - 1) * EVERY + 30 + TAIL) / 60)
f.setup(players=[('fox', dict(x=-6, face=1)), ('falcon', dict(x=6, face=-1))], seed=7)
fox, fal = f.port(0), f.port(1)
if CAM != 'game':
    f.cue(0, 'glass', a=1)
for k in range(N):
    t0 = 30 + k * EVERY
    f.reset(t0, 0, -6, 1); f.reset(t0, 1, 6, -1)
    f.percent(t0, 1, 150); f.percent(t0, 0, 0)
    f.mark(t0, k + 1, f'attempt {k + 1}')
    fox.move(t0 + 30, 'usmash')
    fal.trace(t0 + 20, t0 + 200)

if CAM == 'game':                                    # the vanilla check: the game's own match camera, 4:3, no DIR_GLASS
    f.cue(0, 'gamecam', a=1)
elif CAM == 'lab':
    f.cfg['aspect'] = 0.5625
    f.cam(0, eye=(420, 110, 0), at=(0, 110, -40), fov=50, ease='cut')                    # attempt 1 from the side: depth reads
    f.cam(400, eye=(0, 110, 470), at=(0, 110, 0), fov=50, ease='cut')                    # attempt 3: a tall front view
    f.cam(1690, eye=(0, 20, 130), at=(0, 30, 0), fov=40, ease='cut')                     # attempt 5: close front, the glass
else:
    f.cfg['aspect'] = 0.5625
    import json
    for fr, eye, at, fov, how in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'over_ko_cam.json'))):
        f.cam(fr, eye=eye, at=at, fov=fov, ease=how)
f.emit(sys.argv[1])
