"""Move lab: every move each fighter throws, one test per 70-frame slot, both reset close together at 0%, the hit intended at
the slot's frame 30. tools/machinima/melee/report.py compares the director's HIT log to these intents -> director/calib.json."""
import sys
from dsl import Film

TESTS = ['jab', 'ftilt', 'utilt', 'dtilt', 'fsmash', 'usmash', 'dsmash', 'shine', 'sideb', 'laser',
         'sh_nair', 'sh_fair', 'sh_dair', 'sh_uair']
SLOT = 70
GAP = {'jab': 8, 'ftilt': 9, 'utilt': 5, 'dtilt': 9, 'fsmash': 10, 'usmash': 6, 'dsmash': 8, 'shine': 4.5, 'sideb': 20,
       'laser': 20, 'sh_nair': 11, 'sh_fair': 13, 'sh_dair': 9, 'sh_uair': 7}
f = Film(len_s=float(SLOT * len(TESTS) * 2 + 250) / 60.0)
f.setup(players=[('fox', dict(x=-9, face=1)), ('falco', dict(x=9, face=-1))], seed=7, entry=True)
fox, falco = f.port(0), f.port(1)
f.cam(0, eye=(0, 14, 110), at=(0, 10, 0), fov=30, ease='cut', track='mid')
s0 = 240                                                     # the first 4 s show the entry animation
for k, (att, vic) in enumerate([(0, 1), (1, 0)]):
    for j, m in enumerate(TESTS):
        t = s0 + (k * len(TESTS) + j) * SLOT
        gap = GAP.get(m, 9)                                  # half the spacing between them for this move
        f.reset(t, 0, -gap, 1)
        f.reset(t, 1, gap, -1)
        f.percent(t, 0, 0); f.percent(t, 1, 0)
        f.mark(t, k * 100 + j)
        f.port(att).move(t + 30, m, dir=1 if att == 0 else -1)
f.emit(sys.argv[1])
