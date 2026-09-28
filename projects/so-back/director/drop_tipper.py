"""Drop montage 2: Marth's tipper forward smash, a whiff punish. Fox (100%) short-hops a nair at Marth that falls short and
L-cancels; Marth has wavedashed back (the spacing tool) and forward smashes into the landing lag so the sword's tip, and only
the tip, meets Fox (the tipper: 20%, hitbox 3; lab: a standing Fox is tipped at 32-34
units, the blade wins closer, and it whiffs past 35). The hit lands 11 frames after the C-stick input.
Env: SOBACK_LAB=1 (wide camera, traces), SOBACK_P={"FS": frame or null}, SOBACK_STAGE / SOBACK_BG (two-pass key)."""
import json, os, sys
from dsl import Film

P = dict(MX=20.7, FX=40.0, HOP=40, WD=36, WDS=[-57, -57], FS=51, PCT=100, LEN=2.0)
P.update(json.loads(os.environ.get('SOBACK_P', '{}')))
LAB = os.environ.get('SOBACK_LAB') == '1'
f = Film(len_s=P['LEN'])
f.setup(players=[('marth', dict(x=P['MX'], face=1)), ('fox', dict(x=P['FX'], face=-1))], seed=7, aspect=0 if LAB else 0.5625)
m, fx = f.port(0), f.port(1)
if os.environ.get('SOBACK_STAGE') == '0': f.cue(0, 'stage', a=0)
if os.environ.get('SOBACK_BG'):
    r, g, b = (float(v) for v in os.environ['SOBACK_BG'].split(',')); f.cue(0, 'bgcolor', a=r, b=g, c=b)
f.percent(0, 1, P['PCT'])
fx.auto(0, fastfall=True, lcancel=True)                     # Fox: SHFFL, closed loop in the game
fx.hold(P['HOP'], 2, stick=(-40, 0), btn='X')               # a short hop toward Marth
fx.hold(P['HOP'] + 2, 30, stick=(-56, 0))                    # drifting in
fx.hold(P['HOP'] + 4, 2, btn='A')                           # nair on the first airborne frame (jumpsquat 3)
m.hold(P['WD'], 2, btn='X')                                 # Marth's wavedash back: jump, then air-dodge down-back on
m.airdodge(P['WD'] + 4, tuple(P['WDS']))                    # jumpsquat's last frame (4): a slide with no airborne frames
if P['FS'] is not None:
    m.hold(P['FS'], 2, c=(80, 0))                           # the forward smash (C-stick toward Fox)
    f.mark(P['FS'] + 11, 1, 'tipper')
if LAB:
    f.cam(0, eye=(20, 20, 220), at=(20, 14, 0), fov=40, ease='cut')
    m.trace(0, f.n - 1); fx.trace(0, f.n - 1)
else:
    CAM = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'drop_tipper_cam.json')))
    for fr, eye, at, fov, roll, how, tr in CAM['keys']:
        f.cam(fr, eye=eye, at=at, fov=fov, roll=roll, ease=how, track=tr)
f.emit(sys.argv[1])
