"""where the eye window moves the face forward of its natural surface (the fill's correction < 0), on the head sections:
a map of the correction over x and z, the forward pulls flagged."""
import json, os, sys, runpy
S = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.getcwd())
sys.argv = [sys.argv[0]] + ['null']
ns = runpy.run_path(S + '/eye_lab.py', run_name='x')
from charkit.geom import headfit
import numpy as np
C, V, ycol = ns['C'], ns['V'], ns['ycol']
cfgs = [json.loads(a) for a in os.environ.get('CFGS', '{"eye_region":"window","curve":2.0,"cheek_peak":0.75,"release":0.0}').split('|')]
Sn, _ = headfit.assemble(headfit.Face(C), V, face={'cheek_peak': 0.75}, terms=('corr', 'rel', 'cheek', 'scale', 'warp'))
for cfg in cfgs:
    Sw, _ = headfit.assemble(headfit.Face(C), V, face=cfg)
    xs = np.arange(0.0, 0.42, 0.04); zs = np.arange(0.34, -0.34, -0.04)
    print(cfg)
    print('   z\\x ' + ' '.join('%6.2f' % x for x in xs))
    for z in zs:
        row = [ycol(Sw, x, z) - ycol(Sn, x, z) for x in xs]
        print('  %5.2f ' % z + ' '.join('  -   ' if not np.isfinite(v) else '%+6.3f' % v for v in row))
