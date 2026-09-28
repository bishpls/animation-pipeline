"""Drop montage 1: Fox's waveshine on Falco (FRAME PERFECT's measured chain): shine, JC wavedash in with no airborne frames,
shine, then a jump-cancelled up-smash out of the second shine. Falco crouch-cancels and holds down through each shine (the
chain only holds with the crouch), at 0% so fresh shines keep him grounded; his percent is raised to USM_PCT on the frame
before the up-smash lands so it launches big (the HUD is off, so the change is invisible).
Env: SOBACK_LAB=1 (fixed wide camera, traces), SOBACK_STAGE=0 / SOBACK_BG=r,g,b (the two-pass key)."""
import json, os, sys
from dsl import Film

P = dict(T0=46, USM_PCT=95, LEN=2.07)
P.update(json.loads(os.environ.get('SOBACK_P', '{}')))
LAB = os.environ.get('SOBACK_LAB') == '1'
f = Film(len_s=P['LEN'], calib='projects/frame-perfect/director/calib.json')
f.setup(players=[('fox', dict(x=-12, face=1)), ('falco', dict(x=-7, face=-1))], seed=7, aspect=0 if LAB else 0.5625)
fox, falco = f.port(0), f.port(1)
if os.environ.get('SOBACK_STAGE') == '0': f.cue(0, 'stage', a=0)
if os.environ.get('SOBACK_BG'):
    r, g, b = (float(v) for v in os.environ['SOBACK_BG'].split(',')); f.cue(0, 'bgcolor', a=r, b=g, c=b)
fox.auto(0); falco.auto(0)
usm = fox.shine_chain(P['T0'], [0, 22], dir=1, di_port=1)      # returns the up-smash's expected contact frame
f.percent(usm - 3, 1, P['USM_PCT'])
f.mark(P['T0'], 1, 'shine1'); f.mark(P['T0'] + 22, 2, 'shine2'); f.mark(usm, 3, 'usmash')
if LAB:
    f.cam(0, eye=(0, 20, 170), at=(0, 14, 0), fov=40, ease='cut')
    fox.trace(0, f.n - 1); falco.trace(0, f.n - 1)
else:
    CAM = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'drop_waveshine_cam.json')))
    for fr, eye, at, fov, roll, how, tr in CAM['keys']:
        f.cam(fr, eye=eye, at=at, fov=fov, roll=roll, ease=how, track=tr)
f.emit(sys.argv[1])
