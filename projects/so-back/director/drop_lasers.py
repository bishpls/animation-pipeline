"""Drop montage 4: Falco's short-hop low lasers into a follow-up. Two short-hop lasers (B on the 8th airborne frame, so the
laser flies at a standing fighter's height: FRAME PERFECT's laser lab) strike Fox as Falco closes in, then Falco dashes in
and forward smashes (Fox at PCT, a big launch).
Env: SOBACK_LAB=1 (wide camera, traces), SOBACK_P (tuning), SOBACK_STAGE / SOBACK_BG (the two-pass key)."""
import json, os, sys
from dsl import Film

P = dict(FX=-44.0, OX=0.0, L1=70, L2=126, FS=180, PCT=85, LEN=3.4, WALK=[80, 5, [80, 0]])
P.update(json.loads(os.environ.get('SOBACK_P', '{}')))
LAB = os.environ.get('SOBACK_LAB') == '1'
f = Film(len_s=P['LEN'], calib='projects/frame-perfect/director/calib.json')
f.setup(players=[('falco', dict(x=P['FX'], face=1)), ('fox', dict(x=P['OX'], face=-1))], seed=7, aspect=0 if LAB else 0.5625)
fa, fx = f.port(0), f.port(1)
if os.environ.get('SOBACK_STAGE') == '0': f.cue(0, 'stage', a=0)
if os.environ.get('SOBACK_BG'):
    r, g, b = (float(v) for v in os.environ['SOBACK_BG'].split(',')); f.cue(0, 'bgcolor', a=r, b=g, c=b)
f.percent(0, 1, P['PCT'])
fa.auto(0, fastfall=True, lcancel=True)
fa.move(P['L1'], 'sh_laser', dir=1)
fa.move(P['L2'], 'sh_laser', dir=1)
if P['WALK']: fa.hold(*P['WALK'])                               # [frame, frames, stick]: closing in between lasers
if P['FS'] is not None:
    fa.move(P['FS'], 'fsmash', dir=1, mark=24)                  # approach (closed loop) to the forward smash's range, then smash
if LAB:
    f.cam(0, eye=(-20, 20, 190), at=(-20, 12, 0), fov=40, ease='cut')
    fa.trace(0, f.n - 1); fx.trace(0, f.n - 1)
else:
    CAM = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'drop_lasers_cam.json')))
    for fr, eye, at, fov, roll, how, tr in CAM['keys']:
        f.cam(fr, eye=eye, at=at, fov=fov, roll=roll, ease=how, track=tr)
f.emit(sys.argv[1])
