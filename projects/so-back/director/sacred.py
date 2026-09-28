"""SO BACK's spine: the Captain Falcon sacred combo, one continuous capture on the film clock.

Script frame s = film frame + PRE (film time t = (s - PRE) / 60). Falcon is port 0 (default costume), Fox port 1, on Final
Destination. Every frame below is a FILM frame unless it says script.

  the knee      Falcon runs in and short-hops a fair into Fox: the sweetspot (18%, angle 32, logged as HIT ... 18.0) lands on
                film frame KNEE. Auto fast fall on the first descending frame and an auto L-cancel (the director's closed
                loop). Fox, at FOX_PCT, holds survival DI (up and in) through the hitlag.
  the chase     Falcon dashes out of the halved landing lag toward the ledge, runs, then dash-dances at the edge while Fox
                recovers, and commits: a dash jump (full hop out of a dash: the takeoff speed is capped at 2.1 either way)
                and an aerial Falcon Punch a few frames later. The run momentum rides through the jump and the punch.
                Fox tumbles, double-jumps below the ledge, then starts Firefox's charge.
  the freeze    the director freezes the world at FREEZE (the "FALCON..." voice already started), the camera orbits, and it
                releases at UNFREEZE so the punch connects on film frame PUNCH (12.85 s).
  after         Fox is KO'd at the side blast line; Falcon double-jumps and up-Bs back to the ledge; Fox respawns.

Environment: SOBACK_STAGE=0 hides the stage, SOBACK_BG='r,g,b' sets the clear colour (the two-pass key), SOBACK_LAB=1 swaps in a
fixed wide camera and traces both fighters every frame.
"""
import json, os, sys
from dsl import Film

P = dict(
    PRE=60,          # script frames before film frame 0
    KNEE=4,          # the knee's sweetspot, as LOGGED (HIT s is +1: the hit is drawn on film KNEE - 1 = 3, 0.05 s)
    XF0=-60.0,       # Falcon's start x (he knees from a standstill near the left ledge)
    XFOX=-20.0,      # Fox's start x (he dashes in from the right: FOXIN)
    FOX_PCT=90,
    DI=(-56, 56),    # Fox's DI through the knee's hitlag: up and in (135 degrees)
    B=160,           # film frame of the Falcon Punch input
    V=14,            # freeze this many frames after the B press (the voice has started)
    PUNCH=772,       # the punch, as LOGGED (drawn on film 771, 12.85 s)
    END=18.5,        # film seconds captured
)
P.update(json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sacred_params.json'))))  # the tuned chase
P.update(json.loads(os.environ.get('SOBACK_P', '{}')))
LAB = os.environ.get('SOBACK_LAB') == '1'
END = os.environ.get('SOBACK_END') == '1'       # the ending: a real one-stock match, no freeze, the game's own camera and HUD;
                                                # the punch's KO ends the game: GAME!, then the victory screen and results
PRE = P['PRE']
s = lambda film: film + PRE                     # film frame -> script frame

f = Film(len_s=(PRE + int(P['END'] * 60)) / 60 if not END else 40.0)   # END: the scene change stops the director first
f.setup(players=[('falcon', dict(x=P['XF0'], face=1)), ('fox', dict(x=P['XFOX'], face=-1))], seed=11, stocks=1 if END else 0)
fal, fox = f.port(0), f.port(1)
f.percent(0, 1, P['FOX_PCT'])
fal.auto(0, fastfall=True, lcancel=True)
if os.environ.get('SOBACK_STAGE') == '0':
    f.cue(0, 'stage', a=0)
if os.environ.get('SOBACK_BG'):
    r, g, b = (float(v) for v in os.environ['SOBACK_BG'].split(','))
    f.cue(0, 'bgcolor', a=r, b=g, c=b)

# ---- the knee: Fox dashes in and stops in front of Falcon, who short-hops (X 2 frames) and fairs on air frame 3: the
# sweetspot lands X + 21 (lab_knee), with Fox 8 units ahead (the lab's spacing)
x_press = s(P['KNEE']) - 21
fal.hold(x_press, 2, btn='X')
fal.hold(x_press + 7, 2, c=(80, 0))
for fr, n, sx in P.get('FOXIN', []):              # Fox's approach: [(film frame, frames, stick x)]
    fox.hold(s(fr), n, stick=(sx, 0))
hit = s(P['KNEE'])
fox.hold(hit + 1, 16, stick=P['DI'])
f.mark(hit, 1, 'knee')

# ---- the chase (tuned from the trace: see sacred_notes)
act = x_press + 42                               # Falcon is actionable (Wait) 42 frames after the hop press (L-cancelled)
CH = P.get('CHASE', [])                          # [(film frame, frames, stick x)] after the knee: dashes and runs
for fr, n, sx in CH:
    fal.hold(s(fr), n, stick=(sx, 0))
b = s(P['B'])
if 'JUMP' in P:                                  # the dash jump: X while dashing toward the ledge
    fal.hold(s(P['JUMP']), 6, stick=(80, 0), btn='X')
    fal.hold(s(P['JUMP']) + 6, b - s(P['JUMP']) - 6, stick=(80, 0))
fal.hold(b, 2, btn='B')

# ---- the freeze
frz = s(P['B'] + P['V'])
unf = s(P['PUNCH'] - 52 + P['V'])
FRZ_LEN = unf - frz if END else 0                # END has no freeze: every input after it moves back by its length
late = lambda fr: fr - (FRZ_LEN if s(fr) > frz else 0)
for fr, n, sx, sy, btn in P.get('FOX', []):      # Fox's recovery and his DI on the punch: [(film frame, frames, sx, sy, buttons)]
    fox.hold(s(late(fr)), n, stick=(sx, sy), btn=btn)
if END:                                          # no freeze: the punch lands in plain game time
    unf = frz
else:
    f.freeze(frz, True); f.freeze(unf, False)
    f.mark(frz, 2, 'freeze'); f.mark(unf, 3, 'unfreeze')
fal.neutral(b + 2, unf + 2 - (b + 2)); fox.neutral(frz, unf + 2 - frz)

# ---- after the punch: Falcon recovers (tuned from the trace)
for fr, n, sx, sy, btn in P.get('RECOVER', []):
    fal.hold(s(late(fr)), n, stick=(sx, sy), btn=btn)

if LAB:
    f.cam(0, eye=(40, 20, 420), at=(40, 0, 0), fov=45, ease='cut')
    fal.trace(0, f.n - 1); fox.trace(0, f.n - 1)
    for fr in (300, 740, 750, 760, 766, 770, 771, 772):   # hurtbox capsules (SHIELD/HURT lines): where the fist and body are
        f.shield(s(fr), 0); f.shield(s(fr), 1)
    for fr in range(960, 1044, 2):               # the taunt: where his face and gesturing hand are, frame by frame
        f.shield(s(fr), 0)
elif END:                                        # the game's own match camera, 4:3, HUD on (a stock match keeps it)
    f.cue(0, 'gamecam', a=1)
    if os.environ.get('SOBACK_WINBTN'):          # Falcon's victory pose: B, Y or X held on his port as the victory screen
        f.menu_hold(415, 0, 300, os.environ['SOBACK_WINBTN'])   # sets up (loop frame ~423 since boot); none: random
    f.status(s(late(P['PUNCH'])) - 1, 1)
else:                                            # the portrait camera, authored from a lab trace (sacred_cam.py)
    f.cfg['aspect'] = 0.5625
    CAM = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sacred_cam.json')))
    for fr, eye, at, fov, roll, how in CAM['keys']:
        f.cam(s(fr), eye=eye, at=at, fov=fov, roll=roll, ease=how)
    f.status(s(P['KNEE']) - 1, 1); f.status(s(P['PUNCH']) - 1, 1)
f.emit(sys.argv[1])
