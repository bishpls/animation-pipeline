"""A lock-truth source's view over a zoomed crop (regions coloured with their names, cuts cyan, seeds, unseeded cells
hatched red) and its problems (hairlocks.truth_view with the family truth's completeness test).

    python tools/hair5truth/tpic.py VIEW SRC.json OUT.png [--box r0 r1 c0 c1] [--zoom 3]
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'tools', 'hairlocks'))
import ctx5
import pic as P
from charkit import hairlocks as hk

if __name__ == '__main__':
    a = sys.argv[1:]
    view, src, out = a[0], json.load(open(a[1])), a[2]
    box = tuple(int(q) for q in a[a.index('--box') + 1:a.index('--box') + 5]) if '--box' in a else None
    zoom = int(a[a.index('--zoom') + 1]) if '--zoom' in a else 3
    C = ctx5.make()
    vs = src['views'][view]
    img, labels, cut, problems = hk.truth_view(C['dv'][view], vs, C['fam_truth'][view], C['fam_sets'])
    print('%s: %d locks: %s' % (view, len(labels), ', '.join('%s %d' % (q, (img == i).sum()) for i, q in enumerate(labels))))
    print('unscored px', int((img == -2).sum()))
    for p in problems:
        print('PROBLEM', p)
    if box is None:
        ys, xs = np.nonzero(C['hair'][view])
        box = (ys.min() - 10, ys.max() + 10, xs.min() - 10, xs.max() + 10)
    P.picture(C, view, box, zoom, 'truth', src).save(out)
    print(out, box)
