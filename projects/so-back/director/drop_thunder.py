"""Drop montage 5 (the crowd-pleaser): Pikachu's up-throw into Thunder. Pikachu grabs Fox, throws him straight up, and calls
Thunder (down-B): the bolt comes down from the cloud above and strikes Fox on his way up or down, a vertical hit made for a
portrait frame. Timing (the throw release, the bolt's travel) is measured from the HIT/IHIT logs.
Env: SOBACK_LAB=1 (wide camera, traces), SOBACK_P (tuning), SOBACK_STAGE / SOBACK_BG (the two-pass key)."""
import json, os, sys
from dsl import Film

P = dict(PX=-4.0, FX=4.0, GRAB=46, UT=62, TH=109, PCT=90, LEN=3.0)
P.update(json.loads(os.environ.get('SOBACK_P', '{}')))
LAB = os.environ.get('SOBACK_LAB') == '1'
f = Film(len_s=P['LEN'])
f.setup(players=[('pikachu', dict(x=P['PX'], face=1)), ('fox', dict(x=P['FX'], face=-1))], seed=7, aspect=0 if LAB else 0.5625)
pk, fx = f.port(0), f.port(1)
if os.environ.get('SOBACK_STAGE') == '0': f.cue(0, 'stage', a=0)
if os.environ.get('SOBACK_BG'):
    r, g, b = (float(v) for v in os.environ['SOBACK_BG'].split(',')); f.cue(0, 'bgcolor', a=r, b=g, c=b)
f.percent(0, 1, P['PCT'])
pk.hold(P['GRAB'], 2, btn='Z')                    # standing grab
pk.hold(P['UT'], 3, stick=(0, 80))                # up-throw
pk.hold(P['TH'], 2, stick=(0, -80), btn='B')      # Thunder, on Pikachu's first actionable frame after the throw (109)
if LAB:
    f.cam(0, eye=(0, 60, 260), at=(0, 50, 0), fov=45, ease='cut')
    pk.trace(0, f.n - 1); fx.trace(0, f.n - 1)
else:
    CAM = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'drop_thunder_cam.json')))
    for fr, eye, at, fov, roll, how, tr in CAM['keys']:
        f.cam(fr, eye=eye, at=at, fov=fov, roll=roll, ease=how, track=tr)
f.emit(sys.argv[1])
