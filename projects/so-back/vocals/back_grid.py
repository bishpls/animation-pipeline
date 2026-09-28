"""Grid over the pieces of "back" in the phrase "we're so back", scored by Whisper forced choice (small.en)."""
import os, sys, itertools, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import words, judge, specs
from words import S, G
B = {'bonus': ('nr_1p_07', 0.0, 0.022), 'break': ('name_50', 0.085, 0.115), 'bowser': ('name_16', 0.0, 0.02),
     'button': ('nr_select_17', 0.70, 0.725), 'blue': ('nr_vs_02', 0.0, 0.025)}
AE = {'smash': ('nr_title_01', 1.035, 1.20), 'hand': ('name_25', 0.56, 0.74), 'captain': ('name_00', 0.055, 0.165),
      'and': ('nr_1p_04', 0.02, 0.22), 'man': ('nr_select_00', 0.33, 0.50)}
K = {'captain': ('name_00', 0.0, 0.045), 'continue': ('nr_1p_02', 0.0, 0.045), 'kirby': ('name_15', 0.0, 0.05),
     'complete': ('nr_1p_06', 0.0, 0.045)}
CL = {'c40': (0.04, 0.02), 'c60': (0.06, 0.03)}
were, _, _ = words.word('were', 'wins+player'); so, _, _ = words.word('so', 'surv+no')
res = []
for (bn, b), (an, a), (kn, k), (cn, (cd, cf)) in itertools.product(B.items(), AE.items(), K.items(), CL.items()):
    pieces = [S(*b), S(*a, xf=0.008), G(cd, pre=cf), S(*k, end_fade=0.02, trim=-4)]
    y, js, sp = words.assemble(pieces)
    ph, _, _ = words.phrase([(were, []), (so, []), (y, [])], [0.06, 0.06])
    p, miss, pm = judge.forced(ph, specs.WERE_SO_BACK['hits'], specs.WERE_SO_BACK['misses'], 'small.en')
    res.append(dict(b=bn, ae=an, k=kn, cl=cn, p=round(p, 3), miss=f'{miss} ({pm:.2f})'))
    print(bn, an, kn, cn, round(p, 3), miss, round(pm, 2), flush=True)
jdump(res, f'{W}/back_grid.json')
