"""The waistband's weights at motion QA's poses (round 3, decision 1: the waistband takes the body's weights near the
waist). Variants: rigid on the hips (a belt's default), the body's per vertex (garments.body_weights: the spec's
`"weights": "body"`), per column (each column's rows averaged: no shear across the band), one blend for the whole band.
Per pose: the band's surface newly inside the posed skin (share, depth L), its coarse stretch (p99, max), and the
skirt's top that the band covers at rest and uncovers posed (uncovered: a ray out from the hips axis misses the band;
exposed: it misses the posed skin too, so it shows), for the skirt skinned as shipped and moved as the style says (the
anime default: cloth, pins on the skin; its end frame).

    python -m charkit.sim waist BUILD [--out DIR]          -> DIR/waist.json (and the end meshes for the pictures)
"""
import json, os

import numpy as np


def run(build, out, pictures=('squat', 'twist_bend'), log=print):
    from .. import bodyeval, evalmesh, garments
    from ..calibrate import load_bundle
    from ..evalmesh import POSES
    from ..geom.bvh import BVH
    from . import drape, motion, motionqa, rig as R
    os.makedirs(out, exist_ok=True)
    Bn = load_bundle(build)
    gm = motionqa.settings(Bn)
    S = motionqa.scene(Bn, motionqa.loose_pieces(Bn, gm), log=log)
    B = S.Bd.B
    sp = os.path.join(S.Bd.path, (B.spec.get('name') or 'clawd') + '.spec.json')
    if not os.path.exists(sp):
        sp = os.path.join(build, 'clawd.spec.json')
    spec = bodyeval.resolve(sp)
    for k in ('head_code', 'body_code'):
        p = os.path.join(build, 'geom', k + '.npz')
        spec[k] = p if os.path.exists(p) else B.spec.get(k)
    A = bodyeval.Evaluator(spec).assembly(spec)[0]
    L = S.L
    co = S.Bd.coarse['waistband']
    z0 = float(co['V'][:, 2].min())
    joints = {b: round(float((S.rig.head[b][2] - z0) / L), 3) for b in ('hips', 'spine', 'chest', 'upperChest')}
    log('joints z (L above the band bottom):', joints)
    NR, NC = drape.grid_of(co)
    Wv = garments.body_weights(A, co['V'])
    log('per-row mean weights:', {b: [round(float(x), 2) for x in w.reshape(NR, NC).mean(1)] for b, w in Wv.items()})
    Wc = {b: np.repeat(w.reshape(NR, NC).mean(0)[None], NR, 0).ravel() for b, w in Wv.items()}
    Wm = {b: np.full(len(w), w.mean()) for b, w in Wv.items()}
    variants = {'hips': dict(co, weights={'hips': np.ones(len(co['V']))}), 'body': dict(co, weights=Wv), 'body_cols': dict(co, weights=Wc),
                'body_mean': dict(co, weights=Wm)}
    fin = {k: evalmesh.finalize(o) for k, o in variants.items()}
    E = motion._edges(co['polys'])
    l0 = np.linalg.norm(co['V'][E[:, 0]] - co['V'][E[:, 1]], axis=1)
    F = fin['hips']
    st = np.r_[0, np.cumsum(F['counts'])[:-1]]
    surf = np.zeros(len(F['V']), bool)
    for f in np.nonzero(np.asarray(F['layer']) == 0)[0]:
        surf[F['loopv'][st[f]:st[f] + F['counts'][f]]] = True
    TB = np.array([(F['loopv'][s], F['loopv'][s + j], F['loopv'][s + j + 1]) for s, c in zip(st, F['counts'])
                   for j in range(1, c - 1)], np.int64)
    B0 = BVH((S.skin_V, S.skin_F))
    d0 = B0.signed_distance(F['V'][surf], sign='winding') / L
    c = S.rig.head['hips']
    ssurf = S.surf['skirt']
    def out_dir(P):
        d = P - c; d[:, 2] = 0
        return d / np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-12)
    def covered(Pb, Ps):
        return np.isfinite(BVH((Pb, TB)).ray_cast(Ps, out_dir(Ps), tmax=0.3 * L)[0])
    sk0 = S.fin['skirt']['V'][ssurf]
    cov0 = covered(F['V'], sk0)
    rep = dict(build=build, joints_above_band_L=joints, shipped=sorted(co['weights']), weights_rows={b: [round(float(x), 3) for x in w.reshape(NR, NC).mean(1)] for b, w in Wv.items()},
               skirt_covered_rest=int(cov0.sum()), poses={})
    for pose in POSES:
        D = S.rig.skinning(POSES[pose], 1.0)
        Xs = R.lbs(S.skin_V, S.skin_W, D)
        Bv = BVH((Xs, S.skin_F))
        skirts = {'skinned': R.lbs(S.fin['skirt']['V'], S.fin['skirt']['weights'], D)[ssurf]}
        if pose in ('kick', 'squat', 'twist_bend', 'split'):
            M, r0, n0 = motionqa.settled(S, gm)
            fs, _ = S.schedule(pose)
            for f in fs[n0:]:
                Df = S.rig.skinning(POSES[pose], f)
                fn, cc = M.frame(Df, 1.0 / motion.FPS)
            skirts['cloth'] = fn['skirt'][ssurf]
            cloth_end = fn['skirt']
        row = {}
        for k, Fk in fin.items():
            X = R.lbs(Fk['V'], Fk['weights'], D)
            d = Bv.signed_distance(X[surf], sign='winding') / L
            new = (d < 0) & (d0 >= 0)
            C = R.lbs(co['V'], {b: garments.group_weights(w) for b, w in variants[k]['weights'].items()}, D)
            sn = np.abs(np.linalg.norm(C[E[:, 0]] - C[E[:, 1]], axis=1) / l0 - 1)
            hid = {s: np.isfinite(Bv.ray_cast(P, out_dir(P), tmax=0.3 * L)[0]) for s, P in skirts.items()}
            cv = {s: covered(X, P) for s, P in skirts.items()}
            row[k] = dict(new_inside=round(float(new.mean()), 4), depth=round(float(-d[new].min()) if new.any() else 0.0, 4),
                          stretch_p99=round(float(np.percentile(sn, 99)), 4), stretch_max=round(float(sn.max()), 4),
                          **{'uncovered_' + s: round(float((cov0 & ~cv[s]).sum() / max(1, cov0.sum())), 4)
                             for s in skirts},
                          **{'exposed_' + s: round(float((cov0 & ~cv[s] & ~hid[s]).sum() / max(1, cov0.sum())), 4)
                             for s in skirts})
        rep['poses'][pose] = row
        log(pose, json.dumps(row))
        if pose in (pictures or ()):
            rep.setdefault('pictures', {})[pose] = _pictures(
                out, pose, S, D, Xs, Bv, fin, surf, d0, dict(cloth=cloth_end, skinned=R.lbs(
                    S.fin['skirt']['V'], S.fin['skirt']['weights'], D)), ssurf, cov0, covered, out_dir, L)
    json.dump(rep, open(os.path.join(out, 'waist.json'), 'w'), indent=1)
    return rep


def _pictures(out, pose, S, D, Xs, Bv, fin, surf, d0, skirts, ssurf, cov0, covered, out_dir, L):
    """the band rigid on the hips against the body's weights, with the cloth skirt (the anime default) and the skinned
    one, front and her left side at one framing: grey the skin, brown the band (red where newly inside the skin),
    orange the skirt (magenta where its top, under the band at rest, now shows). -> {column: [png per view]}."""
    from ..geom import raster
    from . import rig as R
    from .drape import _fan
    tri = lambda F: _fan(F['loopv'], F['counts'])
    Fs = S.fin['skirt']
    Tb, Ts = tri(fin['hips']), tri(Fs)
    X = {k: R.lbs(fin[k]['V'], fin[k]['weights'], D) for k in ('hips', 'body')}
    allV = [X['hips'], X['body']]                     # (framed on the band: the waist, 0.5 L round it)
    lo, hi = np.min([v.min(0) for v in allV], 0) - 0.5 * L, np.max([v.max(0) for v in allV], 0) + 0.5 * L
    fr = raster.Frame.around([(np.array([lo, hi]), np.zeros((0, 3), int))], res=300, aspect=1.0)
    cols = {}
    for b in ('hips', 'body'):
        dd = Bv.signed_distance(X[b][surf], sign='winding') / L
        Cb = np.tile(np.array((0.55, 0.33, 0.22)), (len(X[b]), 1))
        Cb[np.nonzero(surf)[0][(dd < 0) & (d0 >= 0)]] = (0.9, 0.0, 0.0)
        for sk, P in skirts.items():
            Pa = P[ssurf]
            shows = cov0 & ~covered(X[b], Pa) & ~np.isfinite(Bv.ray_cast(Pa, out_dir(Pa), tmax=0.3 * L)[0])
            Cs = np.tile(np.array((0.93, 0.55, 0.25)), (len(P), 1))
            Cs[np.nonzero(ssurf)[0][shows]] = (0.85, 0.1, 0.85)
            items = [((Xs, S.skin_F), dict(color=(0.78, 0.78, 0.8), shade='lambert')),
                     ((X[b], Tb), dict(color=Cb, shade='lambert')), ((P, Ts), dict(color=Cs, shade='lambert'))]
            ps = []
            for az in (0, 90):
                fn = 'waist_%s_%s_%s_%d.png' % (pose, b, sk, az)
                raster.save_png(raster.render(items, az, fr), os.path.join(out, fn))
                ps.append(fn)
            cols['%s/%s' % (b, sk)] = ps
    return cols
