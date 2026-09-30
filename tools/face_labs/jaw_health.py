"""the jaw's mesh health on a local assembly of a build's head code (what the outline checks can't see: folds and
crumples in the underside and where it meets the neck): the fitted cage in the jaw's region (headgeom.quality: folded
corners, the worst corners) and its subdivision once (edges whose faces turn more than 60 / 90 degrees, and where), and
shaded renders (a depth-gradient Lambert, level cameras far out) from the front, the three-quarter and 60 degrees, and
from below. headgeom constants can be set for a try: KEY=VALUE (python literals).

    python jaw_health.py OUT.png GEOM_DIR [KEY=VALUE ...]      # GEOM_DIR/head_code.npz (and body_code.npz)"""
import math, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import numpy as np
from PIL import Image
from charkit.geom import headgeom as hg

JAW_Z = (-0.45, -0.25)                        # L from the eye line: the region graded


def cage_health(geom, log=print):
    import jaw_lab
    from charkit import code_base, subdiv
    spec = dict(jaw_lab.spec_of())
    spec['head_code'] = os.path.join(geom, 'head_code.npz')
    S, C, rep = code_base.head_sections(spec)
    H = code_base.head_mesh(S, C, -0.52, code_base.eye_outline(spec), code_base.mouth_block(spec))
    V = np.asarray(H['V'])
    F = np.array([f for f in H['faces'] if len(f) == 4])
    c = V[F].mean(1)
    jaw = (c[:, 2] < JAW_Z[1]) & (c[:, 2] > JAW_Z[0])
    q = hg.quality(V, F[jaw])
    Vs, Q = subdiv.catmull_clark(V, [list(f) for f in F], levels=1)[:2]
    Vs, Q = np.asarray(Vs), np.asarray(Q)
    n = np.cross(Vs[Q[:, 2]] - Vs[Q[:, 0]], Vs[Q[:, 3]] - Vs[Q[:, 1]])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    E = defaultdict(list)
    for i, f in enumerate(Q):
        for a, b in zip(f, list(f[1:]) + [f[0]]):
            E[(min(a, b), max(a, b))].append(i)
    cz = Vs[Q].mean(1)[:, 2]
    ang, at = [], []
    for e, fs in E.items():
        if len(fs) == 2 and JAW_Z[0] < cz[fs[0]] < JAW_Z[1]:
            ang.append(math.degrees(math.acos(float(np.clip(n[fs[0]] @ n[fs[1]], -1, 1)))))
            at.append(Vs[list(e)].mean(0))
    ang, at = np.array(ang), np.array(at)
    out = dict(quads=q['faces'], folded_corners=q['folded_corners'], corner_p05=q['corner_p05'],
               corner_min=q['corner_min'], edges_over_60=int((ang > 60).sum()), edges_over_90=int((ang > 90).sum()),
               dihedral_p99=round(float(np.percentile(ang, 99)), 1), dihedral_max=round(float(ang.max()), 1),
               worst_at=[round(float(v), 3) for v in at[np.argmax(ang)]])
    log('cage health (z %s..%s): %s' % (JAW_Z[0], JAW_Z[1], out))
    return out


def shaded(geom, out):
    import taper_lab
    from charkit import faceregion as fr
    meshes, skin, iris, ez, L, _ = taper_lab.scene(geom=geom, log=lambda *a: None)
    V, T = skin
    c = np.array([0.0, float(np.mean(np.asarray(iris)[:, 1])) + 0.2 * L, ez])
    ppl = 401.136 * 2.2
    rows = []
    for views in (((0.0, 0.0), (36.48, 0.0), (60.0, 0.0)), ((0.0, -35.0), (35.0, -30.0), (60.0, -15.0))):
        row = []
        for az, el in views:
            e = math.radians(el)
            R = np.array([[1, 0, 0], [0, math.cos(e), -math.sin(e)], [0, math.sin(e), math.cos(e)]])
            Vr = (V - c) @ R.T + c
            _, dep = fr.board_view([(Vr, T, np.ones(len(T), int))], None, az, np.array([0, 0, ez]), c, L, ppl,
                                   win=dict(x=0.35, top=-0.05, bottom=-0.5), dist=100.0)
            d = np.where(np.isfinite(dep), dep, np.nan)
            gy, gx = np.gradient(d * ppl)
            nn = np.stack([-gx, gy, np.ones_like(d)], -1)
            nn /= np.linalg.norm(nn, axis=-1, keepdims=True)
            lt = np.array([-0.4, 0.5, 0.75]) / np.linalg.norm([-0.4, 0.5, 0.75])
            img = np.where(np.isfinite(d), 40 + 200 * np.clip(np.nan_to_num(nn @ lt), 0, 1), 235).astype(np.uint8)
            row.append(np.pad(img, ((0, 4), (0, 4)), constant_values=255))
        rows.append(np.concatenate(row, 1))
    Image.fromarray(np.concatenate(rows, 0)).save(out)


if __name__ == '__main__':
    a = sys.argv[1:]
    for kv in a[2:]:
        k, v = kv.split('=', 1)
        setattr(hg, k, eval(v))
    cage_health(a[1])
    shaded(a[1], a[0])
    print(a[0])
