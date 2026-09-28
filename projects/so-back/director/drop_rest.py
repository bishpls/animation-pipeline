"""Drop montage 3: Jigglypuff's Rest on Fox at kill percent, "drill rest": a short-hop down air (the drill) onto Fox,
fast-fallen and L-cancelled, then Rest (down-B) on Puff's first actionable frame while Fox is still in the drill's hitstun.
Rest's hitbox is Puff's whole body for a few frames: it kills Fox at this percent; Puff sleeps after (the flower).
Env: SOBACK_LAB=1 (wide camera, traces), SOBACK_P (tuning), SOBACK_STAGE / SOBACK_BG (the two-pass key)."""
import json, os, sys
from dsl import Film

P = dict(PX=-10.0, FX=0.0, HOP=40, DAIR=1, DRIFT=30, FF=74, LC=79, REST=99, PCT=95, LEN=2.6)
P.update(json.loads(os.environ.get('SOBACK_P', '{}')))
LAB = os.environ.get('SOBACK_LAB') == '1'
f = Film(len_s=P['LEN'])
f.setup(players=[('puff', dict(x=P['PX'], face=1)), ('fox', dict(x=P['FX'], face=-1))], seed=7, aspect=0 if LAB else 0.5625)
pf, fx = f.port(0), f.port(1)
if os.environ.get('SOBACK_STAGE') == '0': f.cue(0, 'stage', a=0)
if os.environ.get('SOBACK_BG'):
    r, g, b = (float(v) for v in os.environ['SOBACK_BG'].split(',')); f.cue(0, 'bgcolor', a=r, b=g, c=b)
f.percent(0, 1, P['PCT'])
# Puff's fast fall and L-cancel are scripted: the drill's hitlag freezes (3 frames per hit, every 5) swallowed the closed-loop
# presses, so the fast fall goes in between two freezes and the L-cancel a few frames before the (measured) landing
pf.hold(P['HOP'], 2, btn='X')                                   # short hop
js = int(json.loads(os.environ.get('SOBACK_JS', '5')))
pf.hold(P['HOP'] + 2, 40, stick=(P['DRIFT'], 0))                 # drift onto Fox
pf.hold(P['HOP'] + js + P['DAIR'], 2, c=(0, -80))               # the drill (C-stick down) early in the hop
if P['FF'] is not None:
    pf.hold(P['FF'], 3, stick=(P['DRIFT'], -80))                # fast fall (a sharp down)
if P['LC'] is not None:
    pf.hold(P['LC'], 2, trig=140)                               # L-cancel
if P['REST'] is not None:
    pf.hold(P['REST'], 2, stick=(0, -80), btn='B')              # Rest
    f.mark(P['REST'], 1, 'rest')
if LAB:
    f.cam(0, eye=(0, 20, 170), at=(0, 12, 0), fov=40, ease='cut')
    pf.trace(0, f.n - 1); fx.trace(0, f.n - 1)
else:
    CAM = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'drop_rest_cam.json')))
    for fr, eye, at, fov, roll, how, tr in CAM['keys']:
        f.cam(fr, eye=eye, at=at, fov=fov, roll=roll, ease=how, track=tr)
f.emit(sys.argv[1])
