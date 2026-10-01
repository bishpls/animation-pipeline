"""a lab batch's numbers as a markdown table: python tools/hair5/table.py LAB.json [LAB.json ...]"""
import json, sys
K = [('hair_ahoge_shape', 'ahoge F'), ('hair_ahoge_bend', 'bend'), ('hair_attached', 'attached L'),
     ('hair_back_lines', 'back ink'), ('hair_back_hem', 'hem'), ('hair_lock_lines_three_quarter', 'lines 3q'),
     ('hair_lock_lines_profile', 'lines prof'), ('hair_piece_upper_back', 'upper'), ('hair_piece_lower_back', 'lower'),
     ('hair_piece_side_locks', 'side'), ('hair_piece_bangs', 'bangs'), ('hair_piece_buns', 'buns'),
     ('hair_piece_ahoge', 'ahoge IoU'), ('hair_piece_flyaways', 'fly IoU'), ('hair_bun_outline', 'bun outline')]
print('| variant | ' + ' | '.join(n for _, n in K) + ' | folds |')
print('|---' * (len(K) + 2) + '|')
for p in sys.argv[1:]:
    for name, m in json.load(open(p)).items():
        cells = []
        for k, _ in K:
            c = m.get(k) or {}
            v = c.get('value')
            if k == 'hair_back_hem':
                v = '%s (%s)' % (v, (c.get('tips') or ['?'])[0])
            cells.append(str(v))
        print('| %s | %s | %s |' % (name, ' | '.join(cells), sum((m.get('folds_builder') or {}).values())))
