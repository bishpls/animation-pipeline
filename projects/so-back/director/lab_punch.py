"""Lab: the aerial Falcon Punch's whole action, high above the stage (a full hop and a double jump first, so he doesn't land
mid-punch): the hit frame, the stall and lunge around it, the end, and the fall during end lag. Then the same from a run
jump off the ledge (the carried momentum), and Falcon's recovery tools: double jump and up-B (Falcon Dive) from below the
ledge, with a ledge grab."""
import sys
from dsl import Film

f = Film(len_s=20.0)
f.setup(players=[('falcon', dict(x=-40, face=1)), ('fox', dict(x=-84, face=1))], seed=7)
fal, fox = f.port(0), f.port(1)
f.cam(0, eye=(0, 30, 330), at=(0, 10, 0), fov=40, ease='cut')
# P1: a run jump near the ledge, B on the second air frame; the punch plays out offstage (whiffing) to its end; then the
# double jump and up-B back, as soon as the punch allows
f.reset(20, 0, 10, 1); fal.trace(21, 290); f.mark(20, 1, 'P1 run jump punch offstage, then DJ + up-B')
fal.hold(30, 24, stick=(80, 0)); fal.hold(54, 6, stick=(80, 0), btn='X'); fal.hold(60, 1, stick=(80, 0)); fal.hold(64, 2, btn='B')
for k in range(116, 200, 2):                     # mash the double jump (with the stick home) until the punch lets it out
    fal.hold(k, 1, stick=(-80, 0), btn='X'); fal.hold(k + 1, 1, stick=(-80, 0))
# P2: recovery from offstage: Falcon placed at (130, -40) airborne, double jump then up-B toward the ledge
f.reset(300, 0, 40, 1); fal.trace(301, 520); f.mark(300, 2, 'P2 DJ + up-B from (130,-40)')
f.setpos(310, 0, 130, -40); f.cue(310, 'face', 0, -1)
fal.hold(320, 3, stick=(-80, 0), btn='X'); fal.hold(323, 20, stick=(-80, 0)); fal.hold(343, 2, stick=(0, 80), btn='B')
fal.hold(345, 60, stick=(-80, 0))
# P3: the same from (150, -60)
f.reset(560, 0, 40, 1); fal.trace(561, 800); f.mark(560, 3, 'P3 DJ + up-B from (150,-60)')
f.setpos(570, 0, 150, -60); f.cue(570, 'face', 0, -1)
fal.hold(580, 3, stick=(-80, 0), btn='X'); fal.hold(583, 20, stick=(-80, 0)); fal.hold(603, 2, stick=(0, 80), btn='B')
fal.hold(605, 60, stick=(-80, 0))
# P4: the up-B straight away (no double jump) from (120, -50)
f.reset(840, 0, 40, 1); fal.trace(841, 1080); f.mark(840, 4, 'P4 up-B only from (120,-50)')
f.setpos(850, 0, 120, -50); f.cue(850, 'face', 0, -1)
fal.hold(860, 2, stick=(0, 80), btn='B'); fal.hold(862, 80, stick=(-80, 0))
f.emit(sys.argv[1])
