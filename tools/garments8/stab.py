"""a sweep's rows as a compact table: python stab.py OUT/sweep.json [CHECK,..]"""
import json, sys
S = json.load(open(sys.argv[1]))
want = sys.argv[2].split(',') if len(sys.argv) > 2 else [
    'collar_front_truth', 'collar_three_quarter_truth', 'neck_v_front_skin', 'neck_v_three_quarter_skin',
    'top_front_truth', 'top_three_quarter_truth', 'art_outline_neck', 'art_outline_collar', 'bow_front_bleed',
    'collar_front_torn', 'collar_three_quarter_torn', 'collar_back_torn', 'collar_profile_torn', 'neck_crease',
    'art_mirror_waist', 'art_speckle_neck']
short = lambda k: k.replace('collar_', 'c_').replace('_truth', 'T').replace('three_quarter', '3q').replace(
    'neck_v_', 'v_').replace('_skin', '').replace('art_outline_', 'ol_').replace('_torn', 'Tn').replace('front', 'f')
print('%-10s' % 'row' + ''.join('%11s' % short(k)[:10] for k in want) + '  pieces (f/3q/p/b): top | collar | bow')
for r in S['rows']:
    C = r['checks']
    cells = []
    for k in want:
        c = C.get(k) or {}
        v = c.get('value')
        st = (c.get('status') or '?')[0]
        cells.append('%9s%s ' % ('-' if v is None else ('%.3f' % v if isinstance(v, (int, float)) else str(v)[:8]), st))
    P = lambda p: '/'.join('%.2f' % x for x in ((C.get('piece_' + p) or {}).get('views') or {}).values())
    print('%-10s' % r['name'][:10] + ''.join(cells) + '  ' + P('top') + ' | ' + P('collar') + ' | ' + P('bow'))
