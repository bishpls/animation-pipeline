"""a sweep's rows as a compact table: chosen checks' values (status letter) and the pieces' shape IoUs per view.
    python tools/garments7/stab.py SWEEP.json [--checks a,b,..] [--pieces top,collar,sleeve_L] [--views front,three_quarter]"""
import sys, json, fnmatch
args = sys.argv[1:]
def opt(k, d):
    if k in args:
        i = args.index(k); v = args[i + 1]; del args[i:i + 2]; return v
    return d
CK = opt('--checks', 'art_outline_neck,art_outline_collar,art_speckle_neck,art_mirror_waist,collar_*_torn,bow_front_bleed').split(',')
PC = opt('--pieces', 'top,collar,sleeve_L,sleeve_R').split(',')
VW = opt('--views', 'front,three_quarter,profile,back').split(',')
d = json.load(open(args[0]))
rows = d['rows'] if isinstance(d, dict) else d
names = sorted({k for r in rows for k in r['checks'] if any(fnmatch.fnmatch(k, p) for p in CK)})
def short(n):
    return n.replace('art_outline_', 'ao_').replace('collar_', 'c_').replace('_torn', 'T').replace('three_quarter', '3q').replace('art_', '')
hdr = ['row'] + [short(n) for n in names] + ['%s.%s' % (p, v[:2]) for p in PC for v in VW]
print(' | '.join(hdr))
for r in rows:
    C = r['checks']
    cells = [r['name'][:28]]
    for n in names:
        c = C.get(n) or {}
        v = c.get('value'); s = (c.get('status') or '?')[0]
        cells.append('%s%s' % (round(v, 4) if isinstance(v, (int, float)) else v, s))
    for p in PC:
        vv = (C.get('piece_' + p) or {}).get('views') or {}
        for v in VW:
            x = vv.get(v)
            cells.append('%.3f' % x if isinstance(x, (int, float)) else '-')
    print(' | '.join(cells))
