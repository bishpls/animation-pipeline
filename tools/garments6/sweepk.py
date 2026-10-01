"""a sweep's rows read as K reads a gate against the old body: each row's checks against a reference build's qa.json
(the old body: pipeline-3d's default), with the sweep's own drawing drift taken out (the row's value less the control's,
added to the build the control rebuilt, BASE_QA: the control's own build). Per row: the checks that would block
(PASS/WARN -> FAIL, a flag check's status worse), the guard (every piece's shape IoU per view against the old body's:
drops over 15% marked), and the named checks' values.
    python tools/garments6/sweepk.py SWEEP.json OLD_BUILD [--base BASE_BUILD] [--checks a,b] [--rows a,b]"""
import sys, os, json
sys.path.insert(0, '.')
args = sys.argv[1:]
def opt(k, d=None):
    if k in args:
        i = args.index(k); v = args[i + 1]; del args[i:i + 2]; return v
    return d
base = opt('--base')
names = opt('--checks', 'neck_crease,bow_front_bleed,art_outline_collar,art_outline_neck,shoulder_front_dip,'
            'shoulder_front_tilt,collar_back_iou,collar_back_lay')
rows_only = opt('--rows')
S = json.load(open(args[0]))
old = json.load(open(os.path.join(args[1], 'qa', 'qa.json')))['checks']
bq = json.load(open(os.path.join(base, 'qa', 'qa.json')))['checks'] if base else None
from charkit import registry
R = {'PASS': 0, 'INFO': 0, 'SKIPPED': 0, 'WARN': 1, 'FAIL': 2}
rows = S['rows']
ctrl = next((r for r in rows if r.get('control') or r['name'] == 'control'), rows[0])
for r in rows:
    if rows_only and r['name'] not in rows_only.split(','):
        continue
    C = r['checks']
    block, guard, vals = [], [], []
    for k, c in sorted(C.items()):
        o = old.get(k)
        if o is None:
            continue
        so, sr = o.get('status'), c.get('status')
        fl = registry.is_flag(o) or registry.is_flag(c) or bool(c.get('flag'))
        if k.startswith(('piece_', 'hair_piece_')) and isinstance(c.get('views'), dict):
            for v, x in c['views'].items():
                y = (o.get('views') or {}).get(v)
                if isinstance(x, (int, float)) and isinstance(y, (int, float)) and y > 0:
                    d = x / y - 1
                    if d < -0.10:
                        guard.append('%s %s %.3f->%.3f (%+.0f%%)%s' % (k, v, y, x, 100 * d, ' GUARD' if d < -0.15 else ''))
            continue
        if sr == 'FAIL' and so in ('PASS', 'WARN'):
            block.append('%s %s %s -> %s FAIL (new FAIL)' % (k, o.get('value'), so, c.get('value')))
        elif fl and R.get(sr, 0) > R.get(so, 0):
            block.append('%s %s %s -> %s %s (flag worse)' % (k, o.get('value'), so, c.get('value'), sr))
    for k in names.split(','):
        if k in C:
            vals.append('%s %s %s (old %s %s)' % (k, C[k].get('value'), C[k].get('status'), (old.get(k) or {}).get('value'),
                                                  (old.get(k) or {}).get('status')))
    print('== %s  %s' % (r['name'], json.dumps(r.get('set'))[:300]))
    print('   blocks vs the old body (%d): %s' % (len(block), '; '.join(block) or '-'))
    print('   shape IoU drops > 10%% vs the old body: %s' % ('; '.join(guard) or '-'))
    print('   ' + '; '.join(vals))
