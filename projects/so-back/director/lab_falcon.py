"""Lab: Captain Falcon's air mobility and the moves the sacred combo needs, measured from the game's own log.
Falcon is port 0, Fox port 1 (a standing target far left, or placed per segment). Every segment resets both fighters while
Falcon is still alive (a KO'd fighter can't be reset, and the respawn would ruin the next segment). Logged every frame of a
segment: POS (position, self and knockback velocity, airborne, jumps used, percent) and HB (active hitboxes).
  A  a full-run dash jump (full hop), stick held forward in the air
  B  the same run jump, stick released on takeoff (momentum alone)
  C  a run jump, then a double jump 20 frames after takeoff, stick forward
  D  running off the ledge (no jump)
  E  a run jump, then an aerial Falcon Punch (stick to neutral, B) 10 frames after takeoff
  F  a grounded Falcon Punch into a standing Fox (the hit frame and damage)
  E2 an aerial Falcon Punch at a standing full hop's apex, over the stage
(the knee is lab_knee.py)
"""
import sys
from dsl import Film

f = Film(len_s=64.0)
f.setup(players=[('falcon', dict(x=-80, face=1)), ('fox', dict(x=-84, face=1))], seed=7)
fal, fox = f.port(0), f.port(1)
f.cam(0, eye=(0, 30, 330), at=(0, 10, 0), fov=40, ease='cut')
T = [20]

def seg(n, fx=-80, foxx=-84, foxface=1, foxpct=0, label=None):
    t0 = T[0]
    f.reset(t0, 0, fx, 1); f.reset(t0, 1, foxx, foxface); f.percent(t0, 1, foxpct)
    fal.trace(t0 + 1, t0 + n - 2); fox.trace(t0 + 1, t0 + n - 2)
    f.mark(t0, len(f.labels) + 1, label)
    T[0] += n
    return t0

t = seg(150, label='A run jump, stick fwd'); fal.hold(t + 10, 30, stick=(80, 0)); fal.hold(t + 40, 6, stick=(80, 0), btn='X')
fal.hold(t + 46, 90, stick=(80, 0))
t = seg(150, label='B run jump, stick released'); fal.hold(t + 10, 30, stick=(80, 0)); fal.hold(t + 40, 6, stick=(80, 0), btn='X')
t = seg(150, label='C run jump then DJ fwd'); fal.hold(t + 10, 30, stick=(80, 0)); fal.hold(t + 40, 6, stick=(80, 0), btn='X')
fal.hold(t + 46, 18, stick=(80, 0)); fal.hold(t + 64, 3, stick=(80, 0), btn='X'); fal.hold(t + 67, 70, stick=(80, 0))
t = seg(75, fx=30, label='D run off the ledge'); fal.hold(t + 10, 60, stick=(80, 0))
t = seg(150, label='E run jump, aerial Falcon Punch'); fal.hold(t + 10, 15, stick=(80, 0))
fal.hold(t + 25, 6, stick=(80, 0), btn='X'); fal.hold(t + 31, 4, stick=(80, 0)); fal.hold(t + 39, 2, btn='B')
t = seg(170, fx=0, foxx=14, foxface=-1, label='F grounded Falcon Punch'); fal.hold(t + 10, 2, btn='B')
# E2: the aerial Falcon Punch from a standing full hop over the stage, B at the apex (the hit frame, the lunge, the landing)
t = seg(130, fx=-40, label='E2 aerial Falcon Punch at the apex'); fal.hold(t + 10, 6, btn='X'); fal.hold(t + 38, 2, btn='B')
f.emit(sys.argv[1])
