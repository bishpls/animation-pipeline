"""the jaw lab: the jaw's checks (charkit.faceregion.jaw: the face boards' camera and outline, emulated, against the
head sheet) on a build's bundle, or on a local assembly of a build's head and body code (the skin alone, subdivided once
as the bundle's eval mesh is), with a picture of each view's classes, ours beside the design's, the face region tinted.
    python jaw_lab.py OUT.png BUILD_DIR            # the bundle (the whole scene)
    python jaw_lab.py OUT.png --geom GEOM_DIR       # a local assembly: GEOM_DIR/head_code.npz, body_code.npz"""
import json, os, sys, time
sys.path.insert(0, os.path.expanduser('~/animation-pipeline-face'))
import numpy as np
from PIL import Image, ImageDraw
from charkit import faceregion as fr, manifest

ROOT = os.path.expanduser('~/animation-pipeline-face')
PAL = np.array([[235, 235, 238], [250, 214, 186], [205, 105, 65], [230, 180, 0], [25, 12, 12], [0, 0, 0], [255, 140, 0],
                [240, 230, 190], [80, 60, 60], [255, 255, 255], [120, 120, 255]], np.uint8)


def spec_of():
    return manifest.resolve(json.load(open(os.path.join(ROOT, 'charkit/spec/clawd_body.json'))))


def local(geom, spec=None):
    """the skin of a local assembly of GEOM's head and body code, subdivided once -> (V, T (tris), iris centres, eye_z, L)."""
    from charkit import character, subdiv
    spec = dict(spec or spec_of())
    spec['head_code'] = os.path.join(geom, 'head_code.npz'); spec['body_code'] = os.path.join(geom, 'body_code.npz')
    A = character.assemble(spec, keys=False)
    V0 = np.asarray(A['verts'], float)
    c = np.asarray(A['head']['centre']); L = A['head']['L']
    keep = V0[:, 2] > c[2] - 1.2 * L
    F = [f for f in A['faces'] if keep[list(f)].all()]
    used = sorted({v for f in F for v in f}); re = {o: n for n, o in enumerate(used)}
    sharp = []                                   # (as the modifier: the eye margins and the jaw's crease creased)
    for E in A['eyes']:
        lp = E['eye']['margin']
        sharp += list(zip(lp, lp[1:] + lp[:1]))
    sharp += list(A['body'].get('jaw_crease') or ())
    sharp = [(re[a], re[b]) for a, b in sharp if a in re and b in re]
    Vs, Q = subdiv.catmull_clark(V0[used], [tuple(re[v] for v in f) for f in F], sharp, levels=1)[:2]
    Q = np.asarray(Q)
    T = np.concatenate([Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]])
    ex = A['head']['eye_knobs']['x'] if isinstance(A['head'].get('eye_knobs'), dict) else 0.168
    iris = [np.asarray(E['c'], float) if len(E['c']) == 3 else None for E in A['eyes']]
    if any(i is None for i in iris):
        iris = [c + L * np.array([s * 0.168, -0.3, 0.0]) for s in (1, -1)]
    return np.asarray(Vs, float), T, iris, float(A['head']['eye_z']), float(L), A


def extra(A, Vs, log=print):
    """what the jaw's geometry can move elsewhere, on a local assembly: qa3d.face_folds' rest count (skin faces in its
    mouth box, down to 0.38 L under the eyes, facing away: normal y over 0.2) and the neck's crease at the join
    (faceregion.crease_of on the skin subdivided once, as the QA's eval mesh; no garments' mask)."""
    from charkit import faceregion as fr_, qa3d
    V = np.asarray(A['verts']); F = A['faces']; fm = np.asarray(A['fmat']); Hd = A['head']; L = Hd['L']
    q = (np.array([V[list(f)].mean(0) for f in F]) - Hd['centre']) / L
    mouth = (fm == 1) & (np.abs(q[:, 0]) < 0.16) & (np.abs(q[:, 2] + 0.28) < 0.1) & (q[:, 1] < -0.2)
    n0 = qa3d._face_normals(V, F)
    K = fr_.crease_of(Vs, np.asarray(Hd['centre']), L)
    log('face_folds rest (mouth box, n_y > 0.2): %d   neck_crease (whole skin, subdivided): %.1f at column %s' % (
        int((mouth & (n0[:, 1] > 0.2)).sum()), K['max'], K['worst']))


def tint(cls, face=None):
    im = PAL[np.clip(cls, 0, 10)].copy()
    if face is not None:
        im[face] = (im[face] * 0.6 + np.array([120, 200, 120]) * 0.4).astype(np.uint8)
    return im


def run(out, build=None, geom=None, log=print):
    spec = spec_of()
    t0 = time.time()
    D, ppl, Dc, az = fr.design_jaw(spec, 0.168)
    if build:
        from charkit import bundle as bl, qa3d
        B = bl.load(os.path.join(build, 'bundle'))
        meshes, _ = qa3d.scene_classes(B)
        V, T, _, _ = B.skin().mesh('masked')
        skin = (V, T); iris = qa3d.iris_centres(B); ez = float(B.assembly['eye_z']); L = float(B.assembly['L'])
    else:
        V, T, iris, ez, L, A = local(geom, spec)
        meshes = [(V, T, np.ones(len(T), int))]
        skin = (V, T)
        extra(A, V, log)
    O, Oc, Ol = fr.ours_jaw(meshes, skin, iris, ez, L, ppl, az, (D.get('front') or {}).get('chin', (0, None))[1])
    C = fr.jaw_compare(D, O, ppl)
    for k, v in C.items():
        log('%-24s %-8s %s' % (k, v.get('value'), v['status']), {a: b for a, b in v.items() if a not in ('value', 'status')})
    tiles = []
    for vn in ('front', 'three_quarter', 'profile'):
        row = []
        for who, cls in (('design', Dc[vn]), ('ours board', Oc[vn]), ('ours level', Ol[vn])):
            seeds = fr.PROFILE_SEEDS if vn == 'profile' else fr.FACE_SEEDS
            im = Image.fromarray(tint(cls, fr._region(cls, seeds, ppl)))
            d = ImageDraw.Draw(im)
            M = (D if who == 'design' else O)[vn] if who != 'ours board' else {'jaw_cols': O[vn].get('jaw_cols')}
            px = lambda u, z: ((u + fr.JAW_WIN['x']) * ppl, (fr.JAW_WIN['top'] - z) * ppl)
            if M.get('chin'):
                x, y = px(*M['chin']); d.ellipse([x - 5, y - 5, x + 5, y + 5], outline=(220, 0, 0), width=2)
            if M.get('jaw_cols') is not None:
                for cidx in np.nonzero(M['jaw_cols'])[0]:
                    d.point((cidx, 3), fill=(220, 0, 0)); d.point((cidx, 4), fill=(220, 0, 0))
            if M.get('underside') is not None:
                d.line([px(u, z) for u, z in M['underside']], fill=(220, 0, 0), width=1)
            if M.get('neck_edge') is not None:
                d.line([px(e, z) for z, e in M['neck_edge']], fill=(0, 90, 220), width=1)
            d.text((6, 6), '%s %s' % (who, vn), fill=(0, 0, 0))
            row.append(im)
        tiles.append(row)
    w, h = tiles[0][0].size
    S = Image.new('RGB', (3 * w + 16, 3 * h + 16), 'white')
    for j, row in enumerate(tiles):
        for i, im in enumerate(row):
            S.paste(im, (i * (w + 8), j * (h + 8)))
    S.save(out)
    log('%s (%.1fs)' % (out, time.time() - t0))
    return D, O, C


if __name__ == '__main__':
    a = sys.argv[1:]
    if '--geom' in a:
        run(a[0], geom=a[a.index('--geom') + 1])
    else:
        run(a[0], build=a[1])
