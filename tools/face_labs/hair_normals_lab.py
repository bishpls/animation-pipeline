"""the hair's corner normals as the QA reads them (face round 4): which piece moves art_terminator_hair, and how far the
build's corner normals sit from the pieces' own.

    python hair_normals_lab.py BUILD                      # art_terminator_hair (the QA's artifacts part alone, ~10 s)
    python hair_normals_lab.py BUILD --exact              # ... with every hair corner given its piece's own normal
    python hair_normals_lab.py BUILD --from OTHER [PIECES] # ... with OTHER's hair corner normals (PIECES: hair_bangs,..)
    python hair_normals_lab.py BUILD --errors             # per piece: corners off their piece's normal (degrees)

BUILD holds bundle/ and geom/hair_pieces/*.npz. Round 4: the crown's build and pipeline-3d's differ in art_terminator_hair
(2.552 against 2.376) by their hair corner normals alone (--from), side_lock_L and _R; --errors showed the proxy
transfer's misses (400 of side_lock_L's vertices, up to 12.7 degrees); --exact is what geom.blender.set_normals builds."""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import numpy as np
from charkit import bundle as bl, qa3d


class Swap:
    """a bundle object with some of its 'eval' arrays replaced."""

    def __init__(self, o, over):
        self._o, self._over = o, over

    def __getattr__(self, k):
        return getattr(self._o, k)

    def a(self, variant, field):
        if variant == 'eval' and field in self._over:
            return self._over[field]
        return self._o.a(variant, field)


def with_swaps(B, over):
    objs = B.objects
    B.objects = lambda *a, **k: [Swap(o, over[o.name]) if o.name in over else o for o in objs(*a, **k)]
    return B


def terminator(B):
    rep = qa3d.run(B, tempfile.mkdtemp(prefix='hnl-'), parts=['artifacts'], mode='off')
    c = rep['checks']['art_terminator_hair']
    return dict(value=c['value'], grade=c.get('grade'), per_view=c.get('per_view'))


def piece_normals(build, o):
    p = os.path.join(build, 'geom', 'hair_pieces', o.name[5:] + '.npz')
    if o.group != 'hair' or not os.path.exists(p):
        return None
    T = np.asarray(o.tris('eval')[0])
    return np.load(p)['vn'][T.ravel()]


def main(argv):
    build = argv[0]
    B = bl.load(os.path.join(build, 'bundle'))
    if '--errors' in argv:
        out = {}
        for o in B.objects():
            want = piece_normals(build, o)
            if want is None:
                continue
            ln = np.asarray(o.a('eval', 'lnor'))
            d = np.degrees(np.arccos(np.clip((ln * want).sum(1) / np.maximum(np.linalg.norm(ln, axis=1), 1e-12), -1, 1)))
            T = np.asarray(o.tris('eval')[0]).ravel()
            out[o.name] = dict(mean=round(float(d.mean()), 3), max=round(float(d.max()), 2),
                               corners_over_3=int((d > 3).sum()), vertices_over_3=int(len(np.unique(T[d > 3]))))
        print(json.dumps(out, indent=1))
        return out
    over = {}
    if '--exact' in argv:
        for o in B.objects():
            want = piece_normals(build, o)
            if want is not None:
                over[o.name] = {'lnor': want.astype(np.float32)}
    elif '--from' in argv:
        other = argv[argv.index('--from') + 1]
        names = argv[argv.index('--from') + 2:] or None
        ob = {o.name: o for o in bl.load(os.path.join(other, 'bundle')).objects()}
        for o in B.objects():
            if o.group == 'hair' and (names is None or o.name in names):
                over[o.name] = {'lnor': np.asarray(ob[o.name].a('eval', 'lnor'))}
    r = terminator(with_swaps(B, over) if over else B)
    print(json.dumps(r))
    return r


if __name__ == '__main__':
    main(sys.argv[1:])
