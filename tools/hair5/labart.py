"""The artifact part's checks (charkit.artifactqa: art_terminator_hair, art_speckle_*, art_peeks_hair, ...) for a hair
lab variant without a Blender build: a build's bundle with its hair objects' meshes replaced by the lab's rebuilt pieces
(hairlab --batch's NAME.pieces.npz: V, T, vn_shade, outline_w; the bundle's eval V, loops and loop normals are exactly
these: checked on b5 P6 against hair5_b, 2e-7 m), the outline's shrink made as the build makes it (inward along the
geometric normal, LINE_W times the vertex group outline_w).

    python tools/hair5/labart.py BUILD NAME=PIECES.npz[:piece,piece] ... [--checks art_terminator_hair,art_speckle_neck]

  :piece,piece  only those pieces swapped (the rest the build's)
"""
import json, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from charkit import calibrate, artifactqa as aq, qa3d
from charkit.geom.mesh import vertex_normals

LINE_W = 0.0014


def patched(build, pieces_npz, only=None):
    B = calibrate.load_bundle(build)
    Z = np.load(pieces_npz, allow_pickle=True)
    names = [k[:-3] for k in Z.files if k.endswith('__V')]
    over = {}
    for n in names:
        if only and n not in only:
            continue
        obj = 'hair_' + n
        if not B.has('o/%s/eval/V' % obj):
            continue
        V, T = Z[n + '__V'].astype(float), np.asarray(Z[n + '__T'], np.int64)
        vn = Z[n + '__vn_shade'].astype(float)
        ow = Z[n + '__outline_w'].astype(float) if n + '__outline_w' in Z.files else np.ones(len(V))
        th = abs(float(B.obj(obj).outline.get('thickness') or LINE_W))
        p = 'o/%s/eval/' % obj
        over[p + 'V'] = V.astype(np.float32)
        over[p + 'loopv'] = T.ravel().astype(np.int32)
        over[p + 'counts'] = np.full(len(T), 3, np.int32)
        over[p + 'pmat'] = np.zeros(len(T), np.int32)
        over[p + 'lnor'] = vn[T.ravel()].astype(np.float32)
        over[p + "shrink"] = (-vertex_normals(V, T) * th * ow[:, None]).astype(np.float32)
    arr, has = B.array, B.has
    B.array = lambda k, *a, **kw: over[k] if k in over else arr(k, *a, **kw)
    B.has = lambda k: k in over or has(k)
    if hasattr(B, '_tri'):
        B._tri.clear()
    return B, sorted({k.split('/')[1] for k in over})


def checks(B, names):
    _, C = aq.measure(B, qa3d.Design(B))
    return {k: C.get(k, C.get(k[4:] if k.startswith('art_') else k)) or {} for k in names}


def main(a):
    build = a[0]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    names = opt('--checks', 'art_terminator_hair,art_speckle_neck,art_speckle_face,art_peeks_hair').split(',')
    rows = {}
    B = calibrate.load_bundle(build)
    rows['(build)'] = checks(B, names)
    for x in a[1:]:
        if x.startswith('--') or x in names or '=' not in x:
            continue
        name, src = x.split('=', 1)
        src, _, only = src.partition(':')
        B, swapped = patched(build, src, only.split(',') if only else None)
        rows[name] = checks(B, names)
    for name, C in rows.items():
        print('%-14s ' % name + '  '.join('%s %s %s %s' % (k[4:], c.get('value'), c.get('grade', c.get('status')),
                                                          c.get('ratio') or c.get('per_view')) for k, c in C.items()),
              flush=True)
    if opt('--json'):
        json.dump(rows, open(opt('--json'), 'w'), indent=1, default=float)


if __name__ == '__main__':
    main(sys.argv[1:])
