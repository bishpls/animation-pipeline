"""The motion pilot: the skirt and the flaps at motion QA's extreme leg poses (the kick first: docs/ROADMAP.md, "Missing
from a production rig" item 3, the skirt's penetration during a kick), moved four ways and measured the same way.

  skinned      as the build ships them: the final meshes skinned (the skirt's inherited weights, the flaps on the hips)
  springs      the outfit graph's spring chains (the flaps' chains, the skirt's ring of eight) run as VRMC_springBone
               runs them, with the graph's stiffness, drag, gravity and hit radius, and no colliders (none are fitted
               yet: the roadmap's item 2); the garments carried on the chains' bones
  springs_col  the same with capsule colliders fitted to the skin (VRM's collider shapes: uniform-radius capsules)
  xpbd_*       charkit.sim.xpbd cloth on the garments' cages, the skirt and the flaps in one system (the flaps kept
               outside the skirt by a two-way layer constraint), pinned where they hang from, against the same capsules;
               'anime' with the profile's hold toward the template as shipped (skinned), 'hips' the same hold
               toward the drawn shape carried by the pelvis alone (the legs push the skirt, as anime rigs do with
               skirt bones and colliders), 'physics' with no hold
Every method starts from the build's rest pose, settles 1 s there, then goes into the pose over RAMP s and holds it
HOLD s at 60 fps. Measured every few frames and at the end on the final meshes (the build's own finalize for moved
coarse meshes): the garment's surface vertices inside the posed skin (the build's skin, subdivided with its weights
carried, skinned the same way; signed by winding number): their share and depth, and the new ones (not inside at rest as
shipped: the tops tucked under the band are); the coarse mesh's stretch; how far each method departs from the skinned
result.

    python -m charkit.sim motion BUILD [--out DIR] [--poses kick,squat,split] [--methods ...]
"""
import json, os, time

import numpy as np

from . import cage as cagelib, drape, rig as riglib, settings as simset, springbone, xpbd

PIECES = ('skirt', 'overskirt_panel_L', 'overskirt_panel_R')
LEG_POSES = ('kick', 'squat', 'split')
METHODS = ('skinned', 'springs', 'springs_col', 'xpbd_anime', 'xpbd_hips', 'xpbd_physics')
FPS, SETTLE, RAMP, HOLD = 60, 1.0, 0.4, 0.6


class Scene:
    """a build's body, skeleton, garments and capsule colliders, venv-side."""

    def __init__(self, build, log=print):
        from .. import bodyeval
        from ..garments import group_weights
        from ..geom import subsurf
        t0 = time.time()
        self.Bd = Bd = drape.Build(build)
        self.L = L = Bd.L
        B = Bd.B
        self.rig = riglib.Rig(B._meta['landmarks']['joints'])
        spec = bodyeval.resolve(os.path.join(build, B.spec.get('name', 'clawd') + '.spec.json')
                                if os.path.exists(os.path.join(build, 'clawd.spec.json')) else B.spec)
        spec['head_code'] = os.path.join(build, 'geom', 'head_code.npz')
        spec['body_code'] = os.path.join(build, 'geom', 'body_code.npz')
        A = bodyeval.Evaluator(spec).assembly(spec)[0]
        A_ = B._arrays
        Vb = np.asarray(A_['o/clawd_skin/base/V'], float)
        lv, cnt = np.asarray(A_['o/clawd_skin/base/loopv'], np.int64), np.asarray(A_['o/clawd_skin/base/counts'],
                                                                                 np.int64)
        if len(Vb) != len(A['verts']):
            raise ValueError('the bundle skin (%d) and the assembly (%d) differ' % (len(Vb), len(A['verts'])))
        self.skin_bones = sorted(A['weights'])
        Wb = np.stack([np.asarray(A['weights'][b], float) for b in self.skin_bones], 1)
        R = subsurf.subdivide(Vb, (lv, cnt), levels=1, carry=Wb, carry_rule='limit')
        self.skin_V = R['V']
        self.skin_F = np.concatenate([R['quads'][:, [0, 1, 2]], R['quads'][:, [0, 2, 3]]])
        self.skin_W = {b: R['carry'][:, k] for k, b in enumerate(self.skin_bones)}
        self.caps = riglib.fit_capsules(Vb, {b: Wb[:, k] for k, b in enumerate(self.skin_bones)}, self.rig)
        # the garments: coarse (recording) and final (as shipped: the build's finalize, weights carried)
        self.co = {n: Bd.coarse[n] for n in PIECES}
        self.fin = {n: Bd.final(n, Bd.coarse[n]['V']) for n in PIECES}
        self.cw = {n: {b: group_weights(w) for b, w in self.co[n]['weights'].items()} for n in PIECES}
        self.surf = {}
        for n, F in self.fin.items():
            st = np.r_[0, np.cumsum(F['counts'])[:-1]]
            keep = np.zeros(len(F['V']), bool)
            for f in np.nonzero(np.asarray(F['layer']) == 0)[0]:
                keep[F['loopv'][st[f]:st[f] + F['counts'][f]]] = True
            self.surf[n] = keep
        # the shipped garments' surface vertices already inside the skin at rest (the tops tucked under the band):
        # the baseline the motion's new penetration is counted against
        D0 = self.rig.skinning({}, 0.0)
        self.rest_inside = self._inside(D0, {n: self.fin[n]['V'] for n in PIECES})
        self.graph = json.load(open(os.path.join(drape.ROOT_DIR, 'charkit', 'refs', 'clawd', 'outfit_graph.json')))
        log('scene %s: skin %d verts (subdivided, weights carried), %d capsules (fit p90 err %.3f L), %.1f s' % (
            build, len(self.skin_V), len(self.caps), max(c['err_p90'] for c in self.caps) / L, time.time() - t0))

    # ---------------------------------------------------------------- measuring
    def _inside(self, D, finals):
        from ..geom.bvh import BVH
        Xs = riglib.lbs(self.skin_V, self.skin_W, D)
        Bv = BVH((Xs, self.skin_F))
        return {n: Bv.signed_distance(finals[n][self.surf[n]], sign='winding') / self.L for n in PIECES}

    def measure(self, D, finals, coarse):
        """penetration of each garment's surface into the posed skin (all, and new: not inside at rest as shipped),
        and its coarse stretch."""
        dd = self._inside(D, finals)
        out = {}
        for n in PIECES:
            d = dd[n]
            ins = d < 0
            new = ins & (self.rest_inside[n] >= 0)
            o = self.co[n]
            E = _edges(o['polys'])
            l0 = np.linalg.norm(o['V'][E[:, 0]] - o['V'][E[:, 1]], axis=1)
            l = np.linalg.norm(coarse[n][E[:, 0]] - coarse[n][E[:, 1]], axis=1)
            sn = np.abs(l / np.maximum(l0, 1e-12) - 1)
            out[n] = dict(inside=int(ins.sum()), share=float(ins.mean()), depth_max=float(max(0.0, -d.min())),
                          new=int(new.sum()), new_share=float(new.mean()),
                          new_depth=float(max(0.0, -d[new].min())) if new.any() else 0.0,
                          stretch_max=float(sn.max()), stretch_p99=float(np.percentile(sn, 99)))
        return out

    def schedule(self, pose):
        """[(f, measured?)] per frame: settle at rest, ramp in (smoothstep), hold."""
        n0, n1, n2 = int(SETTLE * FPS), int(RAMP * FPS), int(HOLD * FPS)
        fs = [0.0] * n0 + [riglib.smoothstep((k + 1) / n1) for k in range(n1)] + [1.0] * n2
        return fs, n0


def _edges(polys):
    E = set()
    for f in polys:
        f = [int(i) for i in f]
        for a, b in zip(f, f[1:] + f[:1]):
            E.add((min(a, b), max(a, b)))
    return np.array(sorted(E), np.int64)


# -------------------------------------------------------------------------------------------------------- the methods
class Skinned:
    def __init__(self, S):
        self.S = S

    def frame(self, D, dt):
        S = self.S
        fin = {n: riglib.lbs(S.fin[n]['V'], S.fin[n]['weights'], D) for n in PIECES}
        co = {n: riglib.lbs(S.co[n]['V'], S.cw[n], D) for n in PIECES}
        return fin, co


class Springs:
    """the outfit graph's spring chains on our garments: each flap one chain down its middle column, the skirt a ring of
    eight at the graph's azimuths; the garments carried by the chains' bones."""

    def __init__(self, S, colliders=False):
        self.S = S
        self.col = colliders
        L = S.L
        sp = {s['piece']: s for s in S.graph.get('springs', [])}
        self.chains = {}                    # piece -> [(Chain, u per vertex, azimuth weight per vertex)]
        for n in PIECES:
            o = S.co[n]
            s = sp.get(n)
            if s is None:
                continue
            kw = dict(stiffness=s['stiffness'], drag=s['drag'], gravity=s['gravity'], gravity_dir=s['gravity_dir'],
                      hit_radius=s['hit_radius'] * L)
            NR, NC = drape.grid_of(o)
            G = o['V'].reshape(NR, NC, 3)
            V = o['V']
            if n.startswith('overskirt'):
                nj = len((s.get('chains') or s.get('drawn_chains'))[0]['joints'])
                mid = 0.5 * (G[:, NC // 2 - 1] + G[:, NC // 2])
                used = _used_rows(o, NR, NC)[NC // 2]
                mid = mid[:used + 1]
                arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(mid, axis=0), axis=1))]
                hem = arc[min(20, len(arc) - 1)]
                sj = np.r_[0.0, hem, hem + np.linspace(0, arc[-1] - hem, nj - 1)[1:]]
                J = np.stack([np.interp(sj, arc, mid[:, k]) for k in range(3)], 1)
                ch = springbone.Chain(J, **kw)
                self.chains[n] = [(ch, springbone.arc_param(V, J), np.ones(len(V)))]
            else:
                cen = G[0].mean(0)
                az_col = np.degrees(np.arctan2(G[0, :, 0] - cen[0], -(G[0, :, 1] - cen[1])))
                az_v = np.degrees(np.arctan2(V[:, 0] - cen[0], -(V[:, 1] - cen[1])))
                rows = np.arange(len(V)) // NC
                chs = sorted(s['chains'], key=lambda c: c['az'] % 360)
                azs = np.array([c['az'] % 360 for c in chs], float)
                out = []
                for k, c in enumerate(chs):
                    col = int(np.argmin(np.abs((az_col - c['az'] + 180) % 360 - 180)))
                    line = G[:, col]
                    arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(line, axis=0), axis=1))]
                    nj = len(c['joints'])
                    sj = np.linspace(0, arc[-1], nj)
                    J = np.stack([np.interp(sj, arc, line[:, q]) for q in range(3)], 1)
                    ch = springbone.Chain(J, **kw)
                    u = np.interp(rows / (NR - 1) * arc[-1], sj, np.arange(nj))
                    # azimuth weight: linear between this chain and its neighbours
                    a0 = azs[k]
                    prev_, next_ = azs[k - 1], azs[(k + 1) % len(azs)]
                    dpos = (az_v % 360 - a0) % 360
                    dneg = (a0 - az_v % 360) % 360
                    gap_n = (next_ - a0) % 360 or 360
                    gap_p = (a0 - prev_) % 360 or 360
                    w = np.where(dpos <= gap_n, 1 - dpos / gap_n, 0) + np.where((dneg <= gap_p) & (dneg > 0),
                                                                                1 - dneg / gap_p, 0)
                    out.append((ch, u, np.clip(w, 0, 1)))
                tot = sum(x[2] for x in out)
                self.chains[n] = [(ch, u, w / np.maximum(tot, 1e-12)) for ch, u, w in out]
        self.started = False

    def frame(self, D, dt):
        S = self.S
        caps = riglib.capsule_rows(S.caps, D) if self.col else None
        co, fin = {}, {}
        for n in PIECES:
            if n not in self.chains:
                co[n] = riglib.lbs(S.co[n]['V'], S.cw[n], D)
            else:
                X = np.zeros_like(S.co[n]['V'])
                for ch, u, w in self.chains[n]:
                    if not self.started:
                        ch.reset(D['hips'])
                    ch.step(D['hips'], dt, caps)
                    X += w[:, None] * ch.carry(S.co[n]['V'], u)
                co[n] = X
            fin[n] = S.Bd.final(n, co[n])['V']
        self.started = True
        return fin, co


def _used_rows(o, NR, NC):
    """per column the last row any of its faces reaches."""
    last = np.zeros(NC, int)
    for f in o['polys']:
        f = np.asarray(f)
        for v in f:
            j, i = v // NC, v % NC
            last[i] = max(last[i], j)
    return last


class Cloth:
    """the skirt and the flaps as one XPBD cloth on their cages."""

    def __init__(self, S, style='anime', spacing=(0.05, 0.03), hold_frame='skin', log=print, **dials):
        self.S = S
        self.hold_frame = hold_frame              # the hold's targets: 'skin' (the template as shipped, skinned) or
                                                  # 'hips' (the drawn shape carried by the pelvis; the legs push it)
        L = S.L
        parts, off = [], 0
        V, faces, pins, rest_rad = [], [], [], []
        D0 = S.rig.skinning({}, 0.0)
        caps0 = xpbd.Capsules(riglib.capsule_rows(S.caps, D0))
        self.K, self.span = {}, {}
        for n in PIECES:
            o = S.co[n]
            K = cagelib.of_piece(o, (spacing[0] if n == 'skirt' else spacing[1]) * L)
            nc = len(K.cols)
            self.K[n] = K
            self.span[n] = (off, off + len(K.V))
            V.append(K.V)
            faces += [tuple(int(i) + off for i in f) for f in K.faces]
            pins += list(np.r_[np.arange(2 * nc), np.nonzero(~K.used)[0]] + off)
            off += len(K.V)
        V = np.concatenate(V)
        C = xpbd.Cloth(V, faces, pins=pins)
        thick = {n: max([abs(float(m['settings'].get('thickness', 0))) for m in S.co[n]['mods'].values()
                         if m['type'] == 'SOLIDIFY'] or [0.0]) for n in PIECES}
        radius = np.zeros(C.n)
        for n in PIECES:
            a, b = self.span[n]
            radius[a:b] = thick[n] + 0.004 * L
        rad = np.clip(caps0.distance(V), 0.0, radius)          # (rest-consistent: the template at rest never pushed)
        # the cage vertices' own skinning weights (they are template vertices)
        self.cw = {}
        for n in PIECES:
            K = self.K[n]
            NRt, NCt = drape.grid_of(S.co[n])
            idx = (K.rows[:, None] * NCt + K.cols[None, :]).ravel()
            self.cw[n] = {b: w[idx] for b, w in S.cw[n].items()}
        st = simset.cloth(C, style, L=L, radius=rad, **dict(dict(substeps=20, iterations=2), **dials))
        self.solver = xpbd.Solver(C, st)
        self.hold = st['hold'] is not None
        # the flaps kept outside the skirt: each free flap vertex over it, its nearest skirt cage triangle at rest
        a, b = self.span['skirt']
        Fs = np.array([f for f in C.F if a <= f[0] < b and a <= f[1] < b and a <= f[2] < b])
        I, T, Bc, G = [], [], [], []
        for n in PIECES[1:]:
            p0, p1 = self.span[n]
            for i in range(p0, p1):
                if C.w[i] == 0:
                    continue
                q, tri, bc, dist = _nearest_tri(V[i], V, Fs)
                if dist > 0.1 * L or bc.min() < -1e-6:
                    continue
                nrm = np.cross(V[tri[1]] - V[tri[0]], V[tri[2]] - V[tri[0]])
                off_ = float(nrm @ (V[i] - q)) / np.linalg.norm(nrm)
                if off_ < 0:
                    tri, bc, off_ = tri[[0, 2, 1]], bc[[0, 2, 1]], -off_
                I.append(i); T.append(tri); Bc.append(bc); G.append(min(off_, radius[i]))
        if I:
            self.solver.add_self_layer(np.array(I), np.array(T), np.array(Bc), np.array(G))
        self.nlayer = len(I)
        self.started = False
        log('xpbd %s: cage %d vertices (%s), %d on the skirt layer, hold %s' % (
            style, C.n, ', '.join('%s %d' % (n, self.span[n][1] - self.span[n][0]) for n in PIECES), self.nlayer,
            st['physics'].get('hold_shape')))

    def targets(self, D, frame='skin'):
        S = self.S
        T = np.zeros_like(self.solver.c.V)
        for n in PIECES:
            a, b = self.span[n]
            W = self.cw[n] if frame == 'skin' else {'hips': np.ones(b - a)}
            T[a:b] = riglib.lbs(self.K[n].V, W, D)
        return T

    def frame(self, D, dt):
        S = self.S
        T = self.targets(D)
        H = self.targets(D, self.hold_frame) if self.hold and self.hold_frame != 'skin' else T
        caps = riglib.capsule_rows(S.caps, D)
        if not self.started:
            self.capsules = xpbd.Capsules(caps)
            self.solver.colliders = [self.capsules]
            self.started = True
        else:
            self.capsules.move(caps)
        self.solver.set_frame(pins=T[self.solver.c.pins], hold=H if self.hold else None)
        self.solver.step(dt)
        co, fin = {}, {}
        for n in PIECES:
            a, b = self.span[n]
            co[n] = self.K[n].carry(self.solver.x[a:b])
            fin[n] = S.Bd.final(n, co[n])['V']
        return fin, co


def _nearest_tri(p, V, F):
    """the nearest point on triangles F to p: (point, triangle, barycentric, distance)."""
    A, B, C = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    cen = (A + B + C) / 3
    k = np.argsort(np.linalg.norm(cen - p, axis=1))[:24]
    best = (None, None, None, np.inf)
    for j in k:
        a, b, c = A[j], B[j], C[j]
        n = np.cross(b - a, c - a)
        nn = n @ n
        if nn < 1e-24:
            continue
        q = p - ((p - a) @ n) / nn * n
        v0, v1, v2 = b - a, c - a, q - a
        d00, d01, d11, d20, d21 = v0 @ v0, v0 @ v1, v1 @ v1, v2 @ v0, v2 @ v1
        den = d00 * d11 - d01 * d01
        v = (d11 * d20 - d01 * d21) / den
        w = (d00 * d21 - d01 * d20) / den
        bc = np.array([1 - v - w, v, w])
        if bc.min() < 0:
            bc = np.clip(bc, 0, None); bc /= bc.sum()
            q = bc[0] * a + bc[1] * b + bc[2] * c
        d = np.linalg.norm(p - q)
        if d < best[3]:
            best = (q, F[j].copy(), bc, d)
    return best


# ------------------------------------------------------------------------------------------------------------ the run
def run(build, out, poses=LEG_POSES, methods=METHODS, every=6, log=print):
    from ..evalmesh import POSES
    os.makedirs(out, exist_ok=True)
    S = Scene(build, log=log)
    rep = dict(build=build, L=S.L, fps=FPS, settle=SETTLE, ramp=RAMP, hold=HOLD,
               capsules=[{k: (v.tolist() if hasattr(v, 'tolist') else v) for k, v in c.items()} for c in S.caps],
               poses={})
    for pose in poses:
        fs, n0 = S.schedule(pose)
        rep['poses'][pose] = {}
        for m in methods:
            t0 = time.time()
            M = (Skinned(S) if m == 'skinned' else Springs(S, colliders=m == 'springs_col') if m.startswith('springs')
                 else Cloth(S, style='anime', log=log) if m == 'xpbd_anime'
                 else Cloth(S, style='anime', hold_frame='hips', log=log) if m == 'xpbd_hips'
                 else Cloth(S, style='anime', hold_shape=0.0, log=log))
            rows, last = [], None
            skin_ref = None
            for k, f in enumerate(fs):
                D = S.rig.skinning(POSES[pose], f)
                fin, co = M.frame(D, 1.0 / FPS)
                if k >= n0 - 1 and ((k - n0 + 1) % every == 0 or k == len(fs) - 1):
                    r = dict(frame=k - n0 + 1, f=round(f, 4), pieces=S.measure(D, fin, co))
                    if m != 'skinned':
                        ref = Skinned(S).frame(D, 0)[0]
                        r['departure_mean'] = {n: float(np.linalg.norm(fin[n] - ref[n], axis=1).mean() / S.L)
                                               for n in PIECES}
                    rows.append(r)
                last = fin
            np.savez(os.path.join(out, 'end_%s_%s.npz' % (pose, m)), **last)
            rep['poses'][pose][m] = dict(frames=rows, seconds=round(time.time() - t0, 1),
                                         layer=getattr(M, 'nlayer', None))
            e = rows[-1]['pieces']
            log('%s %s: end new %s; %.1f s' % (pose, m, ', '.join('%s %.3f / %.3f L' % (n[-6:], e[n]['new_share'],
                                                                                  e[n]['new_depth'])
                                                            for n in PIECES), time.time() - t0))
            json.dump(rep, open(os.path.join(out, 'motion.json'), 'w'), indent=1)
    open(os.path.join(out, 'motion.md'), 'w').write(markdown(rep))
    return rep


def markdown(rep):
    L = ['# Motion pilot: the skirt and the flaps at the leg poses', '',
         'Build `%s`. %d fps: settle %.1f s at rest, into the pose over %.1f s, hold %.1f s. Per garment: the share of '
         'its surface vertices inside the posed skin and their deepest (L), at rest (frame 0), the worst over the '
         'motion, and at the end; the coarse stretch (p99 / max); the mean departure from the skinned result.' % (
             rep['build'], rep['fps'], rep['settle'], rep['ramp'], rep['hold']), '']
    for pose, M in rep['poses'].items():
        L += ['## %s' % pose, '', '| method | piece | settled at rest: new inside, depth | worst: new inside, depth | '
              'end: new inside, depth | end stretch p99 / max | end departure (L) |', '|---|---|---|---|---|---|---|']
        for m, r in M.items():
            fr = r['frames']
            for n in PIECES:
                p0, pe = fr[0]['pieces'][n], fr[-1]['pieces'][n]
                ws = max(x['pieces'][n]['new_share'] for x in fr)
                wd = max(x['pieces'][n]['new_depth'] for x in fr)
                dep = fr[-1].get('departure_mean', {}).get(n)
                L.append('| %s | %s | %.3f, %.3f | %.3f, %.3f | %.3f, %.3f | %.3f / %.3f | %s |' % (
                    m, n, p0['new_share'], p0['new_depth'], ws, wd, pe['new_share'], pe['new_depth'],
                    pe['stretch_p99'], pe['stretch_max'], '—' if dep is None else '%.3f' % dep))
        L.append('')
    return '\n'.join(L) + '\n'


def main(a):
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    build = a[0]
    run(build, opt('--out', os.path.join(build, 'sim_motion')), poses=tuple(opt('--poses', ','.join(LEG_POSES)).split(',')),
        methods=tuple(opt('--methods', ','.join(METHODS)).split(',')), every=int(opt('--every', 6)))
    return 0


# ------------------------------------------------------------------------------------ tuning the spring chains from XPBD
def tune_springs(build, out, pose='kick', ref=('anime', 'hips'), grid=None, log=print):
    """the spring chains' settings fitted to the cloth: the reference XPBD run (style, hold frame) records every
    frame's cage-carried template; each chain joint follows the template point it starts on; for each piece, every
    (stiffness, gravity, drag) in the grid runs its chains (the fitted capsules as their colliders) through the same
    frames, scored by the joints' mean distance from the reference's (L). -> the report (out/tune.json, out/tune.md)."""
    from ..evalmesh import POSES
    os.makedirs(out, exist_ok=True)
    S = Scene(build, log=log)
    fs, n0 = S.schedule(pose)
    M = Cloth(S, style=ref[0], hold_frame=ref[1], log=log)
    traj = {n: [] for n in PIECES}
    Ds = []
    for f in fs:
        D = S.rig.skinning(POSES[pose], f)
        Ds.append(D)
        _, co = M.frame(D, 1.0 / FPS)
        for n in PIECES:
            traj[n].append(co[n])
    grid = grid or dict(stiffness=(0.25, 0.5, 1.0, 2.0, 4.0), gravity=(0.0, 0.1, 0.3), drag=(0.4, 0.7))
    sp0 = Springs(S, colliders=True)
    rep = dict(build=build, pose=pose, ref='xpbd %s, hold toward %s' % ref, grid=grid, pieces={})
    for n, chains in sp0.chains.items():
        # the joints' material points: the nearest template vertex to each rest joint
        V0 = S.co[n]['V']
        idx = [[int(np.argmin(np.linalg.norm(V0 - j, axis=1))) for j in ch.J[1:]] for ch, _, _ in chains]
        R = np.array([[t[i] for i in ix] for t in traj[n] for ix in [sum(idx, [])]])      # (frames, joints, 3)
        g = next(s for s in S.graph['springs'] if s['piece'] == n)
        rows = []
        for st in grid['stiffness']:
            for gr in grid['gravity']:
                for dr in grid['drag']:
                    err, errs = [], []
                    chs = [springbone.Chain(ch.J, stiffness=st, drag=dr, gravity=gr, gravity_dir=ch.gdir,
                                            hit_radius=ch.hit) for ch, _, _ in chains]
                    for k, D in enumerate(Ds):
                        caps = riglib.capsule_rows(S.caps, D)
                        P = []
                        for ch in chs:
                            if k == 0:
                                ch.reset(D['hips'])
                            ch.step(D['hips'], 1.0 / FPS, caps)
                            P.append(ch.cur)
                        d = np.linalg.norm(np.concatenate(P) - R[k], axis=1) / S.L
                        errs.append(d.mean())
                        if k >= n0 - 1:
                            err.append(d.mean())
                    rows.append(dict(stiffness=st, gravity=gr, drag=dr, err_motion=float(np.mean(err)),
                                     err_rest=float(errs[n0 - 1]), err_end=float(errs[-1])))
        base = dict(stiffness=g['stiffness'], gravity=g['gravity'], drag=g['drag'])
        chs = [springbone.Chain(ch.J, hit_radius=ch.hit, gravity_dir=ch.gdir, **base) for ch, _, _ in chains]
        e0, e1 = [], []
        for k, D in enumerate(Ds):
            caps = riglib.capsule_rows(S.caps, D)
            P = []
            for ch in chs:
                if k == 0:
                    ch.reset(D['hips'])
                ch.step(D['hips'], 1.0 / FPS, caps)
                P.append(ch.cur)
            d = np.linalg.norm(np.concatenate(P) - R[k], axis=1) / S.L
            e0.append(d.mean())
        best = min(rows, key=lambda r: r['err_motion'])
        rep['pieces'][n] = dict(graph=dict(base, err_motion=float(np.mean(e0[n0 - 1:])), err_rest=float(e0[n0 - 1]),
                                           err_end=float(e0[-1])), best=best, rows=rows,
                                hit_radius_L=chains[0][0].hit / S.L)
        log('tune %s: graph (%s) err %.3f L -> best stiffness %s gravity %s drag %s err %.3f L (rest %.3f, end %.3f)' % (
            n, base, np.mean(e0[n0 - 1:]), best['stiffness'], best['gravity'], best['drag'], best['err_motion'],
            best['err_rest'], best['err_end']))
    json.dump(rep, open(os.path.join(out, 'tune.json'), 'w'), indent=1)
    L_ = ['# The spring chains tuned to the cloth (%s, reference %s)' % (pose, rep['ref']), '',
          'Per piece, its chains\' joints against the reference cloth\'s material points (mean distance, L) over the '
          'motion, at rest (settled) and at the end; the graph\'s settings and the best of the grid %s, colliders: the '
          'fitted capsules.' % json.dumps(grid), '',
          '| piece | settings | stiffness | gravity | drag | err motion | err rest | err end |', '|---|---|---|---|---|---|---|---|']
    for n, r in rep['pieces'].items():
        for k in ('graph', 'best'):
            x = r[k]
            L_.append('| %s | %s | %s | %s | %s | %.3f | %.3f | %.3f |' % (n, k, x['stiffness'], x['gravity'], x['drag'],
                                                                         x['err_motion'], x['err_rest'], x['err_end']))
    open(os.path.join(out, 'tune.md'), 'w').write('\n'.join(L_) + '\n')
    return rep
