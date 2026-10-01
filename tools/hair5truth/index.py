"""The hair-5 truth review page: charkit/out/hair5truth/review/index.html (the summary box, the per-view pictures from
review.py, the refcheck and per-family score tables).

    python tools/hair5truth/index.py
"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, 'charkit/out/hair5truth/review')
RC = os.path.join(ROOT, 'charkit/out/hair5truth/refcheck')


def main():
    S = json.load(open(os.path.join(ROOT, 'charkit/out/hair5truth/scores/scores.json')))
    rc = {n: json.load(open(os.path.join(RC, '%s.json' % n))) for n in ('breakdown', 'take1', 'take2')}
    sets = list(S['sets'])
    fl = S['floors']
    views = ['front', 'three_quarter', 'profile', 'back', 'all']
    fams = ['bangs', 'side_locks', 'lower_back', 'flyaways', 'ahoge', '_all']
    a = S['sets']['h5_base']['table']['all']
    h = ['<!doctype html><meta charset=utf-8><title>Hair lock truth</title><style>body{font:14px Helvetica,Arial;'
         'margin:16px;background:#fff;color:#111}table{border-collapse:collapse;margin:8px 0}td,th{border:1px solid '
         '#ccc;padding:3px 7px;text-align:right}th{background:#f2f2f2}.box{border:2px solid #333;padding:10px 14px;'
         'max-width:1100px;background:#fafafa}img{max-width:100%;border:1px solid #ddd}.lo{color:#b00}</style>',
         '<h1>Hair lock truth beyond the bangs (tool/hair5, step 2)</h1>',
         '<div class=box><p><b>Recommended:</b> use the extended lock truth (52 locks over four views) to grade the hair '
         'fixes. Neither hair_breakdown nor either generated close-up take is a lock-level reference: their lock lines '
         'meet the sheet\'s at F 0.17-0.29, against 0.07-0.16 for a random split. The base build scores %.3f over all '
         'locks, below a random split of the truth (%.3f).</p>' % (a['_all'], fl['shuffled']['all']['_all']),
         '<p><b>Asked of Michael:</b> (F) score the side flick tips as flyaways, not as the mass\'s locks? yes/no. '
         '(G) leave the outer side masses unscored until we have a lock-level reference? yes/no. (H) the '
         'cross-view names: are the front\'s and back\'s side and lowest outer flicks the same flicks? yes/no. '
         '(B) the close-up generation failed (both takes copied the breakdown\'s blended family colours): try another '
         'paid call with only the turnaround as a ref, or stop here? A/B.</p>',
         '<p><b>Key numbers</b> (lock IoU against the truth, all views; floors: a random split of the truth, and a '
         'random split within each family):</p><table><tr><th>family</th><th>truth locks</th><th>random</th>'
         '<th>random in family</th>' + ''.join('<th>%s</th>' % s for s in sets) + '</tr>']
    nl = {}
    for v, m in S['truth']['per_family'].items():
        for f, n in m.items():
            nl[f] = nl.get(f, 0) + n
    for f in fams:
        row = '<tr><td>%s</td><td>%s</td><td>%.3f</td><td>%.3f</td>' % (
            f.strip('_'), nl.get(f, sum(nl.values())), fl['shuffled']['all'][f], fl['shuffled_within_family']['all'][f])
        for s in sets:
            x = S['sets'][s]['table']['all'].get(f)
            cls = ' class=lo' if x is not None and x < fl['shuffled']['all'][f] else ''
            row += '<td%s>%s</td>' % (cls, '-' if x is None else '%.3f' % x)
        h.append(row + '</tr>')
    h.append('</table><p>Red: below the random split. ahoge: one lock per view, so a split within the family is '
             'trivially 1.0.</p></div>')
    for v in views[:-1]:
        h.append('<h2>%s</h2><p>the body sheet | the lock truth (each lock its colour, its name; hatched: unscored) | '
                 'generated take 1 | take 2, registered at the sheet\'s scale</p><img src="%s.png">' % (v, v))
    h.append('<h2>Refcheck: the sheets against the body turnaround</h2><table><tr><th>sheet</th><th>view</th>'
             '<th>S px/L</th><th>hair IoU</th><th>line F 2.5 px</th><th>random</th><th>line F 5 px</th>'
             '<th>random</th><th>flat share</th></tr>')
    for n, d in rc.items():
        for v, x in d['views'].items():
            h.append('<tr><td>%s</td><td>%s</td><td>%.0f</td><td>%.3f</td><td>%.3f</td><td>%.3f</td><td>%.3f</td>'
                     '<td>%.3f</td><td>%.2f</td></tr>' % (n, v, x['registration']['S_px_per_L'],
                                                          x['silhouette']['iou'], x['lines']['F'],
                                                          x['lines_floor_F'], x['lines_5px']['F'],
                                                          x['lines_5px_floor_F'], x['flat_share']))
    h.append('</table><h2>Lock IoU per view and family</h2><table><tr><th>view</th><th>family</th><th>locks</th>'
             '<th>random</th><th>random in family</th>' + ''.join('<th>%s</th>' % s for s in sets) + '</tr>')
    for v in views:
        for f in fams:
            if f not in fl['own'].get(v, {}):
                continue
            n = S['truth']['per_family'].get(v, {}).get(f, '') if v != 'all' else nl.get(f, '')
            row = '<tr><td>%s</td><td>%s</td><td>%s</td><td>%.3f</td><td>%.3f</td>' % (
                v, f.strip('_'), n, fl['shuffled'][v][f], fl['shuffled_within_family'][v][f])
            for s in sets:
                x = S['sets'][s]['table'].get(v, {}).get(f)
                cls = ' class=lo' if x is not None and x < fl['shuffled'][v][f] else ''
                row += '<td%s>%s</td>' % (cls, '-' if x is None else '%.3f' % x)
            h.append(row + '</tr>')
    h.append('</table><p>Files: the truth <code>charkit/refs/clawd/hair_locks_truth.json</code> (rules 8-14, calls '
             'F-J); notes <code>docs/workstreams/hair5-truth.md</code>; the takes '
             '<a href="../gen/hair_lock_closeup_1.png">1</a>, <a href="../gen/hair_lock_closeup_2.png">2</a>; the '
             'refcheck pictures <code>charkit/out/hair5truth/refcheck/</code>.</p>')
    open(os.path.join(OUT, 'index.html'), 'w').write('\n'.join(h))
    print(os.path.join(OUT, 'index.html'))


if __name__ == '__main__':
    main()
