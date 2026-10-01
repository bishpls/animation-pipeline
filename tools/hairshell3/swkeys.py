"""a sweep's key hair columns per row: art_terminator_hair (and per view), peeks, back lines, hem, folds, lock lines,
the lower back / side locks / upper back IoU per view.   python tools/hairshell3/swkeys.py SWEEP_DIR [...]"""
import json, os, sys
for d in sys.argv[1:]:
    J = json.load(open(os.path.join(d, 'sweep.json')))
    rows = J['rows'] if isinstance(J.get('rows'), list) else [dict(name=k, **v) for k, v in J['rows'].items()]
    for r in rows:
        C = r.get('checks') or {}
        g = lambda k: C.get(k) or {}
        t = g('art_terminator_hair'); pv = t.get('per_view') or t.get('views') or {}
        iou = lambda k: g(k).get('views') or {}
        lb, sl, ub = iou('hair_piece_lower_back'), iou('hair_piece_side_locks'), iou('hair_piece_upper_back')
        print('%-14s term %s %s B %s | peeks %s | back_lines %s %s | hem %s | folds %s | ll3q %s llP %s | LB F/P/B %s/%s/%s | SL F/P %s/%s | UB P/B %s/%s' % (
            r.get('name'), t.get('value'), t.get('status'), pv.get('back'), g('art_peeks_hair').get('value'),
            g('hair_back_lines').get('value'), g('hair_back_lines').get('status'), g('hair_back_hem').get('value'),
            g('hair_folds').get('value'), g('hair_lock_lines_three_quarter').get('value'), g('hair_lock_lines_profile').get('value'),
            lb.get('front'), lb.get('profile'), lb.get('back'), sl.get('front'), sl.get('profile'), ub.get('profile'), ub.get('back')))
