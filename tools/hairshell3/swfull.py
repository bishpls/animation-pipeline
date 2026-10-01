"""a sweep's rows with their six-placement terminator (term6.json, or the term6 log's lines) and the key checks.
    python tools/hairshell3/swfull.py SWEEP_DIR [TERM6_LOG]"""
import json, os, sys
d = sys.argv[1]
J = json.load(open(os.path.join(d, 'sweep.json')))
rows = J['rows'] if isinstance(J.get('rows'), list) else [dict(name=k, **v) for k, v in J['rows'].items()]
tp = os.path.join(d, 'term6.json')
if os.path.exists(tp):
    T = json.load(open(tp))
else:
    T = {}
    for l in open(sys.argv[2]):
        n, _, rest = l.partition(' ')
        if rest.startswith('{"terminator_hair"'):
            T[n] = json.loads(rest)
for r in rows:
    C = r['checks']; g = lambda k: C.get(k) or {}
    t = (T.get(r['name']) or {}).get('terminator_hair') or {}; p = (T.get(r['name']) or {}).get('peeks_hair') or {}
    lb = g('hair_piece_lower_back').get('views') or {}
    print('%-22s term %s/%s B %s | peeks %s/%s | back_lines %s | hem %s | LB F/P/B %s/%s/%s | UB P %s | SL P %s' % (
        r['name'], t.get('place'), t.get('mean'), (t.get('views') or {}).get('back'), p.get('place'), p.get('mean'),
        g('hair_back_lines').get('value'), g('hair_back_hem').get('value'), lb.get('front'), lb.get('profile'),
        lb.get('back'), (g('hair_piece_upper_back').get('views') or {}).get('profile'),
        (g('hair_piece_side_locks').get('views') or {}).get('profile')))
