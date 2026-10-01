"""The pilot's checks from a sweep result, one line per row and check (the brief's list): every hair piece's IoU per
view (the guard), the lock lines, the artifact flags, noise, attachment, penetration, and the builder's folds from
each row's own pieces report (the sweep's hair_folds reads the base's).

    python tools/hairshell/sweepkeys.py OUT/sweep.json [--json OUT.json]
"""
import json, os, sys

KEYS = ['hair_piece_side_locks', 'hair_piece_lower_back', 'hair_piece_upper_back', 'hair_piece_flyaways',
        'hair_piece_bangs', 'hair_piece_buns', 'hair_piece_ahoge', 'art_terminator_hair', 'art_peeks_hair',
        'art_fragments_hair', 'art_speckle_neck', 'hair_noise', 'hair_lock_lines_three_quarter',
        'hair_lock_lines_profile', 'hair_back_lines', 'hair_back_hem', 'hair_attached', 'hair_penetration']

if __name__ == '__main__':
    a = sys.argv[1:]
    J = json.load(open(a[0]))
    out = {}
    for r in J['rows']:
        c = r['checks']
        row = {}
        for k in KEYS:
            x = c.get(k, {})
            row[k] = dict(value=x.get('value'), status=x.get('status'), views=x.get('views') or x.get('per_view'))
        pj = os.path.join(os.path.dirname(a[0]), r['name'], 'geom', 'hair_pieces', 'pieces.json')
        if os.path.exists(pj):
            rep = json.load(open(pj))['report']['pieces']
            row['folds'] = {n: p.get('folds', 0) for n, p in rep.items()}
            row['folds_total'] = sum(row['folds'].values())
        out[r['name']] = row
        print('==', r['name'], 'folds', row.get('folds_total'), row.get('folds'))
        for k in KEYS:
            x = row[k]
            print('  %-32s %-8s %-5s %s' % (k, x['value'], x['status'], x['views'] or ''))
    if '--json' in a:
        json.dump(out, open(a[a.index('--json') + 1], 'w'), indent=1)
