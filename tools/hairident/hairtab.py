"""The hair checks of builds side by side (each build's qa/qa.json): the look checks, the pieces' shape IoU per view
(the guard), the lock lines, the strokes' direction.

    python tools/hairident/hairtab.py LABEL=BUILD ... [--md OUT.md]
"""
import fnmatch, json, os, sys

PATS = ['art_terminator_hair', 'art_peeks_hair', 'art_outline_hair', 'art_fragments_hair', 'hair_back_lines',
        'hair_back_hem', 'hair_lock_lines_*', 'hair_noise', 'hair_tone_edges', 'hair_folds', 'hair_penetration',
        'hair_strokes_*_dir', 'scalp_px', 'body_*_iou_hair', 'hair_piece_*', 'hair_bun_outline', 'hair_attached']


def checks(build):
    q = json.load(open(os.path.join(build, 'qa', 'qa.json')))
    return q.get('checks', q)


def main(a):
    builds = [x.split('=', 1) for x in a if '=' in x]
    C = {lab: checks(b) for lab, b in builds}
    names = []
    for p in PATS:
        for lab in C:
            for k in sorted(C[lab]):
                if fnmatch.fnmatch(k, p) and k not in names:
                    names.append(k)
    rows = ['| check | ' + ' | '.join(l for l, _ in builds) + ' |', '|---|' + '---|' * len(builds)]
    for k in names:
        cells = []
        for lab, _ in builds:
            c = C[lab].get(k)
            if c is None:
                cells.append('-')
                continue
            v, st = (c[0], c[1]) if isinstance(c, list) else (c.get('value'), c.get('status'))
            if isinstance(v, dict):
                v = json.dumps(v)[:40]
            cells.append('%s %s' % (round(v, 3) if isinstance(v, float) else v, (st or '')[:1]))
        rows.append('| %s | %s |' % (k, ' | '.join(cells)))
    # the guard: every hair piece's shape IoU per view (qa hair_pieces)
    Q = {lab: json.load(open(os.path.join(b, 'qa', 'qa.json'))).get('hair_pieces', {}).get('iou', {}) for lab, b in builds}
    fams = []
    for lab in Q:
        for f, vs in Q[lab].items():
            for v in vs:
                if (f, v) not in fams:
                    fams.append((f, v))
    for f, v in fams:
        cells = []
        for lab, _ in builds:
            x = (Q[lab].get(f) or {}).get(v)
            cells.append('-' if x is None else '%.3f' % x)
        rows.append('| piece %s %s | %s |' % (f, v, ' | '.join(cells)))
    md = '\n'.join(rows)
    if '--md' in a:
        open(a[a.index('--md') + 1], 'w').write(md + '\n')
    print(md)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
