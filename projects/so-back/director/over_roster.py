"""Lane 2: the roster strobe for "CHOOSE YOUR CHARACTER!" (drop2, bar 13): every Melee character alone, large and centred, in
one characterful pose (its taunt), framed to the same height. Four characters per run, spaced 40 units apart on Final
Destination (stage hidden, the two-pass key's clear colour); the camera takes each in turn from a 3/4 front, and that
character taunts during its own shot. The others stand far outside the portrait frame.

Env: ROSTER_RUN=k (the group, 0..6), ROSTER_CAM=lab|film (lab: one fixed distance for measuring; film: roster_cam.json's
per-character distance and aim, so every character fills the same height), SOBACK_BG='r,g,b' (0,0,0 or 96,96,96)."""
import json, os, sys
from dsl import Film

CHARS = ['doc', 'mario', 'luigi', 'bowser', 'peach', 'yoshi', 'dk', 'falcon', 'ganon', 'falco', 'fox', 'ness', 'ics', 'kirby',
         'samus', 'zelda', 'sheik', 'link', 'ylink', 'pichu', 'pikachu', 'puff', 'mewtwo', 'gnw', 'marth', 'roy']
GROUPS = [CHARS[i:i + 4] for i in range(0, len(CHARS), 4)]
XS = [-60.0, -20.0, 20.0, 60.0]
LEAD, SHOT, TAUNT_AT = 20, 150, 12        # frames: the lead-in (fighters land), each character's shot, the taunt press in it
YAW = 28.0                                 # degrees: the 3/4 front, from the side each character faces (right)

RUN = int(os.environ.get('ROSTER_RUN', '0'))
CAM = os.environ.get('ROSTER_CAM', 'lab')
group = GROUPS[RUN]
f = Film(len_s=(LEAD + SHOT * len(group)) / 60)
f.setup(players=[(c, dict(x=XS[i], face=1)) for i, c in enumerate(group)], seed=3, aspect=0.5625)
f.cue(0, 'stage', a=0)
r, g, b = (float(v) for v in os.environ.get('SOBACK_BG', '0,0,0').split(','))
f.cue(0, 'bgcolor', a=r, b=g, c=b)
fr = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'roster_cam.json'))) if CAM == 'film' else {}
for i, c in enumerate(group):
    t0 = LEAD + i * SHOT
    k = fr.get(c, {})
    d, ay, dx, fov = k.get('d', 75.0), k.get('ay', 10.0), k.get('dx', 0.0), k.get('fov', 30.0)
    f.orbit(t0 if i else 0, at=(XS[i] + dx, ay, 0), dist=d, yaw=YAW, pitch=4.0, fov=fov, ease='cut')
    f.port(i).taunt(t0 + TAUNT_AT)
    f.mark(t0, i + 1, c)
f.emit(sys.argv[1])
