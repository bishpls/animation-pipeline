"""a sweep's rows judged as the landing bar asks (coordinator, 2026-10-01): the guard (every piece and view within 15% of
the control: the sweep's own guard list), new FAILs among the kept checks (a status FAIL the control doesn't have),
flag regressions (a kept check carrying a flag whose status got worse), and the targets (collar truth, the V).
    python rowjudge.py OUT/sweep.json"""
import json, sys
S = json.load(open(sys.argv[1]))
R = {'PASS': 0, 'WARN': 1, 'FAIL': 2, 'INFO': 0}
ctrl = next(r for r in S['rows'] if r.get('control'))
C0 = ctrl['checks']
G = {}
for g in S.get('guard') or ():
    G.setdefault(g['row'], set()).add((g['shape'], g['view'], g['rel']))
for r in S['rows']:
    if r.get('control'):
        continue
    C = r['checks']
    nf = [k for k, c in C.items() if c.get('status') == 'FAIL' and (C0.get(k) or {}).get('status') != 'FAIL']
    fl = [k for k, c in C.items() if (c.get('flag') or (C0.get(k) or {}).get('flag')) and
          R.get(c.get('status'), 0) > R.get((C0.get(k) or {}).get('status'), 0)]
    g = sorted(G.get(r['name'], ()))
    t = {k: (C.get(k) or {}).get('value') for k in ('collar_front_truth', 'collar_three_quarter_truth', 'neck_v_front_skin',
                                                   'neck_v_three_quarter_skin', 'art_outline_neck', 'neck_crease')}
    ok = not nf and not fl and not g
    print('%-10s %s  guard %s  new FAIL %s  flag worse %s  targets %s' % (
        r['name'], 'CLEAN' if ok else 'no', ['%s %s %+.2f' % x for x in g[:4]] or '-', nf or '-', fl or '-', t))
