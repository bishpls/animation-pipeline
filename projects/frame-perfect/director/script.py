"""FRAME PERFECT: the choreography. Every hit is placed on the song's grid (120 BPM, downbeats on even seconds, so a beat is
exactly 30 game frames). The fighters trade bars like a dance battle: each bar is one fighter's combo, three or four hits on
the beat strung from small-knockback moves (the attacker walks onto each mark in the game, closed loop), ended by a bigger
hit. Every bar is a shot; a shot cuts in LEAD frames before its downbeat and resets both fighters there, so the first move's
startup plays after the cut. The plate's frame 0 is film time 0.0 (the song's first sample).

Song (assets/cues.json, measured): 0-6.0 near silence; 6.0 the drums drop in (bar 4); 21.04-22.55 a drop-out; 28.0 the last
downbeat, then a dead stop 28.3-29.0; 29.03 the re-entry hit; the final stab and ring-out to 31.3; silence to 34.03.
"""
import sys
from dsl import Film, RANGE

B = lambda bar, beat=1.0: int(round(120 * (bar - 1) + 30 * (beat - 1)))   # bar and beat, 1-based, -> plate frame
LEAD = 16
C = lambda bar, beat=1.0: B(bar, beat) - LEAD                              # a shot's cut-in frame

f = Film(len_s=34.0, calib='projects/frame-perfect/director/calib.json', fix='projects/frame-perfect/director/fix.json')
f.setup(players=[('fox', dict(x=-60, face=1)), ('falco', dict(x=60, face=-1))], seed=7, entry=True, aspect=1.6231)
P = [f.port(0), f.port(1)]
FOX, FALCO = 0, 1
side = {FOX: 1, FALCO: -1}                                                 # facing, set by each shot


def shot(bar, fox_x, falco_x, beat=1.0, falco_pct=0):
    """A new set-up on a cut: both standing, facing each other."""
    t = C(bar, beat)
    side[FOX] = 1 if fox_x < falco_x else -1
    side[FALCO] = -side[FOX]
    f.reset(t, FOX, fox_x, side[FOX]); f.reset(t, FALCO, falco_x, side[FALCO])
    f.percent(t, FOX, 0); f.percent(t, FALCO, falco_pct)
    f.mark(t, bar, f'bar {bar}')


def phrase(who, bar, hits):
    """One fighter's bar: hits = [(beat, move), ...]. Before each hit both fighters walk in to the move's range (closed loop,
    in the game), so the string holds together whatever the last knockback did; damage returns to 0% after each hit."""
    prev = None
    for beat, move in hits:
        t = B(bar, beat)
        a = P[who].move(t, move, dir=side[who], mark=22)
        P[1 - who].approach(max(a - 22, prev + 4 if prev else 0), a - 1, RANGE.get(move, 16))
        f.percent(t + 2, 1 - who, 0)
        prev = t


def cam(t0, t1, eye0, eye1, at=(0, 10, 0), fov0=30, fov1=None, track='mid', ease='linear'):
    """A shot's camera: one move from eye0 to eye1 over [t0, t1), cut at t1."""
    f.cam(t0, eye=eye0, at=at, fov=fov0, ease=ease, track=track)
    f.cam(t1 - 1, eye=eye1, at=at, fov=fov1 or fov0, ease='cut', track=track)


# ---- cold open (0-6 s, near silence): the Arwings drop them at +-60; close-ups; they walk in; a stand-off in the silence
cam(0, B(2), (0, 70, 420), (0, 48, 330), at=(0, 6, 0), track='world')
cam(B(2), B(2, 3.5), (-22, 5, 40), (-17, 5, 33), at=(0, 8.5, 0), fov0=26, track='p0')
cam(B(2, 3.5), B(3, 2), (22, 5, 40), (17, 5, 33), at=(0, 8.5, 0), fov0=26, track='p1')
cam(B(3, 2), C(4), (0, 2.5, 100), (0, 3, 80), at=(0, 13, 0), fov0=28)
P[FOX].approach(4.0, C(4), 22, stick=44)                    # the walk-in, closed loop: both stop 22 apart, never overlapping
P[FALCO].approach(4.0, C(4), 22, stick=44)

# ---- bar 4 (6.0): the drop. Fox's waveshine: shines on the 16ths 0 and 3, then a jump-cancelled up-smash out of the second.
# Falco crouches into each shine and holds down through its hitlag (DI); fresh shines launch him on the second, so two it is.
shot(4, -34, -29)
cam(C(4), C(5), (0, 12, 90), (0, 11, 76))
P[FOX].auto(C(4)); P[FALCO].auto(C(4))
P[FOX].shine_chain(B(4, 1), [0, 22], dir=1, di_port=FALCO)      # shine, shine (16ths 0, 3), JC up-smash (~16th 5)

# ---- bar 5 (8.0): Falco's pillar, low front three-quarter: dair (b1), L-cancel, shine (b2) pops Fox up to about 25,
# dair (b3.5) as he falls back through a short hop's reach, shine (b4)
shot(5, -2, 7)
cam(C(5), C(6), (48, 4, 68), (38, 5, 58))
P[FALCO].move(B(5, 1), 'sh_dair', dir=-1, drift=40)
P[FOX].trace(B(5, 2) - 2, C(6))                             # Fox's flight after Falco's shine, to time the second aerial
P[FALCO].move(B(5, 2), 'shine', dir=-1)
P[FALCO].hold(B(5, 2), 38, btn='B')                                      # the reflector stays up until the jump-cancel
P[FALCO].move(B(5, 3.5), 'sh_dair', dir=-1, drift=80)       # meets Fox falling back through reach

# ---- bar 6 (10.0): Fox, from high left: short-hop nair (b1, fast-fallen, L-cancelled), up-smash (b2), up-air (b3)
shot(6, -10, 10)
cam(C(6), C(7), (-42, 34, 76), (-34, 28, 66))
P[FOX].move(B(6, 1), 'sh_nair', dir=1)
P[FOX].move(B(6, 2), 'usmash', dir=1, mark=12)
P[FOX].move(B(6, 4), 'dtilt', dir=1, mark=26)                               # the knocked-down Falco, on b4

# ---- bar 7 (12.0): Falco, wide: short-hop lasers (B on the 8th air frame, so they fly at Fox's height) on b1.5 and
# b2.5 as he closes in, then a forward smash (b4)
shot(7, -16, 16)
cam(C(7), C(8), (0, 22, 130), (0, 17, 110), at=(0, 12, 0))
P[FALCO].move(B(7, 1.5), 'sh_laser', dir=-1)                # a short-hop laser strikes Fox on b1.5 (its 26-frame lead
P[FALCO].approach(B(7, 1.5) + 6, B(7, 4) - 13, 20)           # can't start before the shot's cut), then Falco closes in
P[FALCO].move(B(7, 4), 'fsmash', dir=-1)

# ---- bar 8 (14.0): Fox multishines on the eighths, a taunt in rhythm, while Falco walks in; the last shine hits (b4)
shot(8, -20, 14)
cam(C(8), C(9), (0, 9, 60), (0, 9, 46), at=(0, 9, 0))
P[FOX].multishine(B(8, 1) - 1, 7, every=15)                # seven shines on the eighths; the seventh, on b4, connects
f.intents.append({'port': FOX, 'move': 'shine', 'hit': B(8, 4), 'input': B(8, 4) - 1})
P[FALCO].approach(B(8, 1), B(8, 3.5), 18, stick=40)                         # walks in to just outside the shine
P[FALCO].approach(B(8, 4) - 12, B(8, 4) - 2, 8, stick=56)                   # and steps into the last one

# ---- bar 9 (16.0): Falco, low right: up-tilt (b1), up-tilt (b2), up-air (b3), the juggle
shot(9, -5, 5)
cam(C(9), C(10), (40, 3, 60), (30, 4, 52), at=(0, 12, 0))
P[FALCO].move(B(9, 1), 'utilt', dir=-1)
P[FALCO].move(B(9, 2), 'utilt', dir=-1, mark=10)
P[FALCO].move(B(9, 3), 'sh_uair', dir=-1, drift=0)

# ---- bar 10 (18.0): Fox's up-throw up-air at 50%, from above: grab, the throw lands on b2, the up-air on b3.5
shot(10, -6, 6, falco_pct=50)
cam(C(10), C(11), (0, 44, 92), (0, 40, 80), at=(0, 16, 0))
P[FOX].hold(B(10, 2) - 25, 2, btn='Z'); P[FOX].hold(B(10, 2) - 7, 3, stick=(0, 80))
P[FOX].move(B(10, 3.5), 'sh_uair', dir=1, drift=0)

# ---- bar 11 (20.0): Falco's phrase runs into the drop-out: its last hit is 21.0, then the stand-off in the silence
shot(11, -9, 9)
STAND = B(11, 3) + 8                                        # 21.13: cut to the stand-off
cam(C(11), STAND, (-32, 8, 70), (-26, 8, 62))
phrase(FALCO, 11, [(1, 'ftilt'), (3, 'fsmash')])            # a forward smash needs the tilt's end lag behind it
f.reset(STAND, FOX, -10, 1); f.reset(STAND, FALCO, 10, -1); f.percent(STAND, FOX, 0); f.percent(STAND, FALCO, 0)
side[FOX], side[FALCO] = 1, -1
cam(STAND, C(12, 2), (0, 8, 72), (0, 9, 36), at=(0, 10, 0), fov1=50, ease='inout')      # dolly-zoom push on the pair
P[FOX].taunt(21.35)

# ---- bar 12 (22.5, the pickup): the waveshine again, from beat 2
shot(12, -34, -29, beat=2)
cam(C(12, 2), C(13), (36, 7, 62), (30, 7, 56))
P[FOX].shine_chain(B(12, 2), [0, 22], dir=1, di_port=FALCO)     # shine, shine, JC up-smash

# ---- bar 13 (24.0): Falco's last pillar
shot(13, -2, 7)
cam(C(13), C(14), (0, 12, 72), (-10, 12, 62))
P[FALCO].move(B(13, 1), 'sh_dair', dir=-1, drift=40)
P[FALCO].move(B(13, 2), 'shine', dir=-1)
P[FALCO].hold(B(13, 2), 38, btn='B')                                      # the reflector stays up until the jump-cancel
P[FALCO].move(B(13, 3.5), 'sh_dair', dir=-1, drift=80)       # meets Fox falling back through reach

# ---- bar 14 (26.0): Fox builds to the finish, from high left: nair (b1), up-smash (b2), up-air (b3)
shot(14, -10, 10)
cam(C(14), C(15), (-40, 22, 70), (-24, 16, 58), at=(0, 11, 0))
P[FOX].move(B(14, 1), 'sh_nair', dir=1)
P[FOX].move(B(14, 2), 'usmash', dir=1, mark=12)
P[FOX].move(B(14, 4), 'dtilt', dir=1, mark=26)

# ---- bar 15 (28.0): the finisher on the last downbeat. The music stops dead at 28.3 and the world freezes with it; the
# camera swings round the frozen launch; everything lets go on the re-entry hit (29.03)
shot(15, -6, 6, falco_pct=150)
f.cam(C(15), eye=(0, 8, 70), at=(0, 12, 0), fov=30, ease='cut', track='mid')
P[FOX].move(B(15), 'usmash', dir=1)
FREEZE, THAW = int(28.3 * 60), int(29.03 * 60)
f.freeze(FREEZE, True)
f.orbit(FREEZE, at=(0, 6, 0), dist=60, yaw=-10, pitch=-8, fov=30, ease='inout', track='p1')   # round the frozen Falco
f.orbit(THAW - 1, at=(0, 6, 0), dist=44, yaw=58, pitch=10, fov=32, ease='cut', track='p1')
f.freeze(THAW, False)
cam(THAW, B(16), (0, 40, 260), (0, 60, 300), at=(0, 110, 0), fov0=34, track='world')    # wide: the launch to the blast line

# ---- bar 16 (30.0): Fox, alone, taunts on the final stab; hold for the end card
cam(B(16), int(34.0 * 60), (-24, 6, 44), (-18, 6, 34), at=(0, 9, 0), fov0=28, fov1=26, track='p0')
P[FOX].taunt(30.15)

f.emit(sys.argv[1])
