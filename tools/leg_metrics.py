"""Per-bar leg metrics from a dump of the performed channels (t_bar, rootX, footLX, footLY, footRX, footRY, hipX, hipY, ...):
how far the root travels, how far each foot travels in world (root + foot), how many steps (a foot lifted above 12 px and set
down), and how much a planted foot slides (world x change while its Y is ~0 and the frame isn't a lift), in base px.
    python3 tools/leg_metrics.py DUMP.txt [--scale .27] [--bars 45:93]
"""
import sys
a = sys.argv[1:]; opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
rows = [list(map(float, l.split(','))) for l in open(a[0]) if l.strip() and ',' in l]
lo, hi = (float(x) for x in opt('--bars', '0:999').split(':'))
rows = [r for r in rows if lo <= r[0] < hi]
bars = {}
for r in rows: bars.setdefault(int(r[0]), []).append(r)
tot = dict(root=0, steps=0, slide=0, still=0, n=0)
print(' bar  root-range  root-path  footL-path  footR-path  steps  slide>3px  frames-no-foot-motion')
for b in sorted(bars):
    R = bars[b]; root = [r[1] for r in R]; fl = [r[1] + r[2] for r in R]; fr = [r[1] + r[4] for r in R]
    path = lambda v: sum(abs(v[i] - v[i - 1]) for i in range(1, len(v)))
    steps = 0; slide = 0; still = 0
    for key, w in ((3, fl), (5, fr)):
        up = False
        for i, r in enumerate(R):
            if r[key] > 12 and not up: steps += 1; up = True
            elif r[key] < 3: up = False
            if i and r[key] < 2 and R[i - 1][key] < 2 and abs(w[i] - w[i - 1]) > 3: slide += 1
    for i in range(1, len(R)):
        if abs(fl[i] - fl[i - 1]) < .5 and abs(fr[i] - fr[i - 1]) < .5 and R[i][3] < 1 and R[i][5] < 1: still += 1
    tot['root'] += path(root); tot['steps'] += steps; tot['slide'] += slide; tot['still'] += still; tot['n'] += len(R)
    print(f'{b:4d}  {max(root) - min(root):9.0f}  {path(root):9.0f}  {path(fl):10.0f}  {path(fr):10.0f}  {steps:5d}  {slide:9d}  {still:5d}/{len(R)}')
print(f"TOTAL root path {tot['root']:.0f}  steps {tot['steps']}  slide frames {tot['slide']}  feet-still frames {tot['still']}/{tot['n']} ({100 * tot['still'] / max(1, tot['n']):.0f}%)")
