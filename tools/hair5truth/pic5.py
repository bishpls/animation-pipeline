"""tools/hairlocks/pic.py on the lean context (ctx5): zoomed crops for labelling locks by eye, a 10 px grid with 50 px
labels. what: sheet | regions (the labeller's) | cells | truth (a lock-truth source's regions, cuts, seeds) | fam (the
family truth's sets).

    python tools/hair5truth/pic5.py VIEW OUT.png [--box r0 r1 c0 c1] [--zoom 3] [--what ...] [--src SRC.json]
"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'tools', 'hairlocks'))
import ctx5
import pic as P


def fam_labels(C, view):
    t = C['fam_truth'][view]
    sets = C['fam_sets']
    L = np.where(t >= 0, t + 1, 0).astype(np.int32)
    names = {k + 1: '|'.join(s) for k, s in enumerate(sets)}
    return L, names


if __name__ == '__main__':
    a = sys.argv[1:]
    view, out = a[0], a[1]
    box = tuple(int(q) for q in a[a.index('--box') + 1:a.index('--box') + 5]) if '--box' in a else None
    zoom = int(a[a.index('--zoom') + 1]) if '--zoom' in a else 3
    what = a[a.index('--what') + 1] if '--what' in a else 'sheet'
    src = json.load(open(a[a.index('--src') + 1])) if '--src' in a else None
    C = ctx5.make()
    if box is None:
        ys, xs = np.nonzero(C['hair'][view])
        box = (ys.min() - 10, ys.max() + 10, xs.min() - 10, xs.max() + 10)
    if what == 'fam':
        L, names = fam_labels(C, view)
        im = P.picture(C, view, box, zoom, 'sheet', None, labels=L, names=names)
    else:
        im = P.picture(C, view, box, zoom, what, src)
    im.save(out)
    print(out, box)
