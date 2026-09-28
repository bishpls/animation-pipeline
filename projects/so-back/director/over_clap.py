"""Lane 2 (SO BACK's "over" flashes): THE CLAP. A real one-stock match that ends: Fox (port 0) up-smashes Falcon (port 1,
default costume) at 150% off the top, GAME!, and the game goes on to its results screen, where the loser claps for the
winner. The match camera keeps the game's 4:3 (aspect 0): the HUD (stock icons, the GAME! splash) is screen-space and the
results screen has its own camera, so the edit crops 9:16 (vplate --mode crop). The director stops at the scene change,
so the capture runs by frame count (dolphin.py --frames), not to DIRECTOR END."""
import sys
from dsl import Film

f = Film(len_s=60.0)
f.setup(players=[('fox', dict(x=-6, face=1)), ('falcon', dict(x=6, face=-1))], seed=7, stocks=1)
fox, fal = f.port(0), f.port(1)
f.percent(20, 1, 150)
f.cam(0, eye=(0, 22, 120), at=(0, 22, 0), fov=34, ease='linear')
f.cam(58, eye=(0, 40, 170), at=(0, 60, 0), fov=40, ease='cut')
f.mark(30, 1, 'usmash')
fox.move(60, 'usmash')
fal.trace(40, 200)
f.emit(sys.argv[1])
