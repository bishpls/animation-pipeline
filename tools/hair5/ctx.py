"""Hair round 5's lab context: a build's hair on the design grids, every hair component (a lock of a mass piece, a bun's
part, the ahoge, each flyaway blade) z-buffered with its own code in the QA's scene (hair_pieces_measure's occluders:
skin, eyes, mouth, accessories, garments), and the design's side (the design views, the hair truth, the hair layers).

    python tools/hair5/ctx.py BUILD OUT.npz        # ours for a build (a build folder or a preview folder)
"""
import json, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

VIEWS = ('front', 'three_quarter', 'profile', 'back')
FAM_OF = {'bangs': 'bangs', 'side_lock_L': 'side_locks', 'side_lock_R': 'side_locks', 'upper_back': 'upper_back',
          'lower_back': 'lower_back', 'bun_L': 'buns', 'bun_R': 'buns', 'ahoge': 'ahoge', 'flyaways': 'flyaways'}


def components(T, n):
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    E = np.r_[T[:, [0, 1]], T[:, [1, 2]]]
    return connected_components(coo_matrix((np.ones(len(E)), (E[:, 0], E[:, 1])), shape=(n, n)), directed=False)


def hair_parts(B):
    """[(name 'piece.k', piece, V, T)] one per connected component of each hair object (a lock, a blade)."""
    out = []
    for o in B.objects(groups=('hair',)):
        pc = o.name[5:]
        if pc not in FAM_OF or not o.has('eval'):
            continue
        V, T = o.mesh('eval')[:2]
        k, lab = components(T, len(V))
        tl = lab[T[:, 0]]
        for c in range(k):
            t = T[tl == c]
            if len(t):
                out.append(('%s.%d' % (pc, c), pc, V, t))
    return out


def ours(B, D=None, views=VIEWS):
    """-> ({view: int image: 0 empty, 1 other surfaces, 100 + i hair part i}, [part names], [pieces], ppl)."""
    from charkit import bodyqa, qa3d
    D = D or qa3d.Design(B)
    sc = D.sheet_context()
    As = B.assembly
    meshes = []
    V, T = B.skin().mesh('masked')[:2]
    meshes.append((V, T, np.ones(len(T), int)))
    for o in B.objects(groups=('eye', 'mouth', 'accessory', 'garment')):
        if o.has('eval'):
            V, T = o.mesh('eval')[:2]
            meshes.append((V, T, np.ones(len(T), int)))
    parts = hair_parts(B)
    for i, (nm, pc, V, T) in enumerate(parts):
        meshes.append((np.asarray(V, float), np.asarray(T), np.full(len(T), 100 + i)))
    dv = D.design_views()
    lab = bodyqa.zbuffer_views(meshes, sc['az3'], np.array(qa3d.iris_centres(B)), As['centre'], As['L'], sc['ppl'],
                               [v for v in views if v in dv])
    img = {v: np.where(l[1] >= 0, l[1] + (l[1] == 0), 0).astype(np.int32) for v, l in lab.items()}
    return img, [p[0] for p in parts], [p[1] for p in parts], sc['ppl']


def load_build(build):
    from charkit import calibrate
    return calibrate.load_bundle(build)


def design(B):
    """the design side: {dv, truth (images, sets, meta), layers, ppl}."""
    from charkit import manifest, qa3d, hairlayers
    D = qa3d.Design(B)
    dv = D.design_views()
    R = manifest.load(B.spec['ref']['manifest'])['references']
    truth = hairlayers.load_truth(R['hair_truth']['path'])
    layers = qa3d.hair_layers_masks(B, D)
    return dict(D=D, dv=dv, truth=truth, layers=layers, ppl=D.sheet_context()['ppl'])


if __name__ == '__main__':
    build, out = sys.argv[1], sys.argv[2]
    B = load_build(build)
    img, names, pieces, ppl = ours(B)
    np.savez_compressed(out, names=json.dumps(names), pieces=json.dumps(pieces), ppl=ppl, **img)
    for v, m in img.items():
        print(v, m.shape, len(np.unique(m[m >= 100])), 'hair parts visible')
