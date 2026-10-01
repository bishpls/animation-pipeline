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

    def __init__(self, build, pieces=None, log=print):
        """build: a build's folder or its Bundle; pieces: the loose garments (the skirt first: the layer the others lie
        on), default PIECES."""
        from .. import bodyeval
        self.pieces = tuple(pieces or PIECES)
        from ..garments import group_weights
        from ..geom import subsurf
        t0 = time.time()
        self.Bd = Bd = drape.Build(build)
        self.L = L = Bd.L
        B = Bd.B
        self.rig = riglib.Rig(B._meta['landmarks']['joints'])
        name = B.spec.get('name') or 'clawd'
        sp = os.path.join(Bd.path, name + '.spec.json')
        if not os.path.exists(sp):                      # (a rebased bundle: its spec written out for the resolver)
            import tempfile
            sp = os.path.join(tempfile.mkdtemp(prefix='sim_spec_'), name + '.spec.json')
            json.dump(dict(B.spec), open(sp, 'w'), default=str)
        spec = bodyeval.resolve(sp)
        for k in ('head_code', 'body_code'):
            p = os.path.join(Bd.path, 'geom', k + '.npz')
            spec[k] = p if os.path.exists(p) else B.spec.get(k)
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
        Wd = {b: Wb[:, k] for k, b in enumerate(self.skin_bones)}
        self.caps = riglib.fit_capsules(Vb, Wd, self.rig)                    # the legs (round 1)
        self.torso = riglib.fit_torso(Vb, Wd, self.rig)                      # the pelvis and the belly (round 2)
        # the garments: coarse (recording) and final (as shipped: the build's finalize, weights carried)
        self.co = {n: Bd.coarse[n] for n in self.pieces}
        self.fin = {n: Bd.final(n, Bd.coarse[n]['V']) for n in self.pieces}
        self.cw = {n: {b: group_weights(w) for b, w in self.co[n]['weights'].items()} for n in self.pieces}
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
        self.rest_inside = self._inside(D0, {n: self.fin[n]['V'] for n in self.pieces})
        self.graph = json.load(open(os.path.join(drape.ROOT_DIR, 'charkit', 'refs', 'clawd', 'outfit_graph.json')))
        log('scene %s: skin %d verts (subdivided, weights carried), %d leg capsules (fit p90 err %.3f L), %d torso '
            '(%.3f L), %.1f s' % (Bd.path, len(self.skin_V), len(self.caps), max(c['err_p90'] for c in self.caps) / L,
                                  len(self.torso), max([c['err_p90'] for c in self.torso] or [0]) / L, time.time() - t0))

    def colliders(self, which='legs'):
        """the capsule set: 'legs' (round 1: two per leg bone), 'body' (the legs, the pelvis and the belly), 'none'."""
        return {'legs': list(self.caps), 'body': list(self.caps) + list(self.torso), 'none': []}[which]

    def transfer(self, P):
        """the skin's weights at points P (the nearest point of the subdivided rest skin)."""
        return riglib.transfer_weights(P, self.skin_V, self.skin_F, self.skin_W)

    # ---------------------------------------------------------------- measuring
    def _inside(self, D, finals):
        from ..geom.bvh import BVH
        Xs = riglib.lbs(self.skin_V, self.skin_W, D)
        Bv = BVH((Xs, self.skin_F))
        return {n: Bv.signed_distance(finals[n][self.surf[n]], sign='winding') / self.L for n in self.pieces}

    def measure(self, D, finals, coarse):
        """penetration of each garment's surface into the posed skin (all, and new: not inside at rest as shipped),
        and its coarse stretch."""
        dd = self._inside(D, finals)
        out = {}
        for n in self.pieces:
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

    def schedule(self, pose, ramp=RAMP):
        """the pose's share per frame (settle at rest, ramp in (smoothstep), hold) and the first frame of the ramp."""
        n0, n1, n2 = int(SETTLE * FPS), int(round(ramp * FPS)), int(HOLD * FPS)
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
        fin = {n: riglib.lbs(S.fin[n]['V'], S.fin[n]['weights'], D) for n in S.pieces}
        co = {n: riglib.lbs(S.co[n]['V'], S.cw[n], D) for n in S.pieces}
        return fin, co


class Springs:
    """the outfit graph's spring chains on our garments: each flap one chain down its middle column, the skirt a ring of
    eight at the graph's azimuths; the garments carried by the chains' bones."""

    def __init__(self, S, colliders=False, settings=None, caps='legs', root='hips'):
        """colliders: run the chains against capsules (caps: S.colliders' set, shrunk to clear the chains' rest joints
        by their hit radius); settings: {piece: dict(stiffness, drag, gravity)} over the graph's (a tuning's); root:
        what carries each chain's first joint, 'hips' (the graph's parent bone), 'skin' (the skin under it: its
        weights there, chain_root) or 'skin_pos' (the joint rides the skin, the chain's rest direction stays the
        hips': as the cloth's pins ride the skin while its hold follows the hips-carried shape)."""
        self.S = S
        self.col = colliders
        L = S.L
        sp = {s['piece']: s for s in S.graph.get('springs', [])}
        self.chains = {}                    # piece -> [(Chain, u per vertex, azimuth weight per vertex)]
        for n in S.pieces:
            o = S.co[n]
            s = sp.get(n)
            if s is None:
                continue
            s = dict(s, **((settings or {}).get(n) or {}))
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
        for cs in self.chains.values():
            for ch, _, _ in cs:
                ch.root_w = root_weights(S, ch.J[0]) if root in ('skin', 'skin_pos') else None
                ch.root_rot = 'hips' if root == 'skin_pos' else 'skin'
        J = [ch.J[1:] for cs in self.chains.values() for ch, _, _ in cs]
        hit = max([ch.hit for cs in self.chains.values() for ch, _, _ in cs] or [0.0])
        self.caps = riglib.rest_clear(S.colliders(caps), np.concatenate(J) if J else np.zeros((0, 3)), hit) \
            if colliders else []
        self.started = False

    def frame(self, D, dt):
        S = self.S
        caps = riglib.capsule_rows(self.caps, D) if self.col else None
        co, fin = {}, {}
        for n in S.pieces:
            if n not in self.chains:
                co[n] = riglib.lbs(S.co[n]['V'], S.cw[n], D)
            else:
                X = np.zeros_like(S.co[n]['V'])
                for ch, u, w in self.chains[n]:
                    Dr = chain_root(ch, D)
                    if not self.started:
                        ch.reset(Dr)
                    ch.step(Dr, dt, caps)
                    X += w[:, None] * ch.carry(S.co[n]['V'], u)
                co[n] = X
        self.started = True
        return _Finals(S, co), co


def root_weights(S, p):
    """the skin's weights at a chain's first joint (its nearest point on the rest skin) -> {bone: w}, the rig's bones."""
    W = S.transfer(np.asarray(p, float)[None])
    return {b: float(w[0]) for b, w in W.items() if w[0] > 1e-4 and b in S.rig.head}


def chain_root(ch, D):
    """a chain's root deformation (4x4): the hips' (the graph's parent), or with ch.root_w the skin's under its first
    joint: the weights' blend of the bones' matrices, its rotation the nearest rotation (polar), its translation taking
    the joint where the skin takes it (the joint rides the skin; a VRM rig would carry it on a helper bone)."""
    w = getattr(ch, 'root_w', None)
    if not w:
        return D['hips']
    M = sum(x * D[b] for b, x in w.items()) / sum(w.values())
    if getattr(ch, 'root_rot', 'skin') == 'hips':
        R = D['hips'][:3, :3]
    else:
        U, _, Vt = np.linalg.svd(M[:3, :3])
        R = U @ Vt
        if np.linalg.det(R) < 0:
            U[:, -1] *= -1
            R = U @ Vt
    j = ch.J[0]
    out = np.eye(4)
    out[:3, :3] = R
    out[:3, 3] = M[:3, :3] @ j + M[:3, 3] - R @ j
    return out


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

    def __init__(self, S, style='anime', spacing=(0.05, 0.03), hold_frame='skin', colliders='legs', pins='own',
                 log=print, **dials):
        self.S = S
        self.hold_frame = hold_frame              # the hold's targets: 'skin' (the template as shipped, skinned) or
                                                  # 'hips' (the drawn shape carried by the pelvis; the legs push it)
        self.pins_follow = pins                   # the pinned rows' targets: 'own' (the garment's weights, as shipped)
                                                  # or 'body' (the skin's weights under them: the waist bends with it)
        L = S.L
        parts, off = [], 0
        V, faces, pins, rest_rad = [], [], [], []
        D0 = S.rig.skinning({}, 0.0)
        self.K, self.span = {}, {}
        for n in S.pieces:
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
        # the colliders, none holding the cloth at rest (shrunk to clear its rest vertices by 0.004 L)
        grow = float(dials.pop('radius', 0.0)) * L
        self.caps = riglib.rest_clear([dict(c, r=c['r'] + grow) for c in S.colliders(colliders)], V, 0.004 * L)
        caps0 = xpbd.Capsules(riglib.capsule_rows(self.caps, D0))
        thick = {n: max([abs(float(m['settings'].get('thickness', 0))) for m in S.co[n]['mods'].values()
                         if m['type'] == 'SOLIDIFY'] or [0.0]) for n in S.pieces}
        radius = np.zeros(C.n)
        for n in S.pieces:
            a, b = self.span[n]
            radius[a:b] = thick[n] + 0.004 * L
        rad = np.clip(caps0.distance(V), 0.0, radius)          # (rest-consistent: the template at rest never pushed)
        # the cage vertices' own skinning weights (they are template vertices)
        self.cw = {}
        for n in S.pieces:
            K = self.K[n]
            NRt, NCt = drape.grid_of(S.co[n])
            idx = (K.rows[:, None] * NCt + K.cols[None, :]).ravel()
            self.cw[n] = {b: w[idx] for b, w in S.cw[n].items()}
        self.tw = {}
        if self.pins_follow == 'body':
            Wt = S.transfer(V)
            for n in S.pieces:
                a, b = self.span[n]
                self.tw[n] = {k: w[a:b] for k, w in Wt.items()}
        st = simset.cloth(C, style, L=L, radius=rad, **dict(dict(substeps=20, iterations=2), **dials))
        self.solver = xpbd.Solver(C, st)
        self.hold = st['hold'] is not None
        # the flaps kept outside the skirt: each free flap vertex over it, its nearest skirt cage triangle at rest
        a, b = self.span['skirt']
        Fs = np.array([f for f in C.F if a <= f[0] < b and a <= f[1] < b and a <= f[2] < b])
        I, T, Bc, G = [], [], [], []
        for n in S.pieces[1:]:
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
            style, C.n, ', '.join('%s %d' % (n, self.span[n][1] - self.span[n][0]) for n in S.pieces), self.nlayer,
            st['physics'].get('hold_shape')))

    def targets(self, D, frame='skin'):
        S = self.S
        T = np.zeros_like(self.solver.c.V)
        for n in S.pieces:
            a, b = self.span[n]
            W = self.cw[n] if frame == 'skin' else self.tw[n] if frame == 'body' else {'hips': np.ones(b - a)}
            T[a:b] = riglib.lbs(self.K[n].V, W, D)
        return T

    def frame(self, D, dt):
        S = self.S
        T = self.targets(D)
        H = self.targets(D, self.hold_frame) if self.hold and self.hold_frame != 'skin' else T
        Tp = self.targets(D, 'body') if self.pins_follow == 'body' else T
        caps = riglib.capsule_rows(self.caps, D)
        if not self.started:
            self.capsules = xpbd.Capsules(caps)
            self.solver.colliders = [self.capsules]
            self.started = True
        else:
            self.capsules.move(caps)
        self.solver.set_frame(pins=Tp[self.solver.c.pins], hold=H if self.hold else None)
        self.solver.step(dt)
        co = {n: self.K[n].carry(self.solver.x[self.span[n][0]:self.span[n][1]]) for n in S.pieces}
        return _Finals(S, co), co


class _Finals(dict):
    """the finalized meshes of moved coarse ones, made when first read (a frame that isn't measured never pays for
    the three finalizes)."""

    def __init__(self, S, co):
        super().__init__()
        self.S, self.co = S, co

    def __missing__(self, n):
        v = self[n] = self.S.Bd.final(n, self.co[n])['V']
        return v

    def keys(self):
        return self.co.keys()

    def __iter__(self):
        return iter(self.co)

    def __len__(self):
        return len(self.co)

    def items(self):
        return [(n, self[n]) for n in self.co]


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


# ------------------------------------------------------------------------------------------------------ the methods
CLOTH = dict(colliders='legs', pins='body')     # round 2: the pins on the skin (the pelvis and belly capsules change nothing measured)
HOLD_FRAMES = {'xpbd_hips': 'hips', 'xpbd_anime': 'skin', 'xpbd_physics': 'hips'}


def method(S, name, style='anime', hold_shape=None, log=print, **over):
    """a motion method by name -> an object with frame(D, dt) -> (finals, coarse).
      skinned, springs, springs_col       as shipped; the graph's spring chains without and with the leg capsules
      xpbd_hips, xpbd_anime, xpbd_physics the cloth held toward the drawn shape carried by the pelvis, toward the
                                          template as skinned, not held (hold_shape None: the style's physics section;
                                          xpbd_physics 0); round 2's colliders and pins (CLOTH)
      <any xpbd>_r1                       round 1's cloth: the leg capsules only, the pins on the garment's own weights
      pelvis_rigid                        the garments carried by the pelvis alone (the hold's target, no cloth)
      skinned_shuffled                    the garments skinned with their weights shuffled among their vertices
                                          (over['seed']): a random rig, the calibration's floor
      <any xpbd>_nocol                    the cloth with no body colliders
    over: the Cloth's dials (substeps, iterations, ...) and 'radius' (L added to every collider's radius)."""
    if name == 'skinned':
        return Skinned(S)
    if name == 'springs_tuned':                 # (the chains with a tuning's settings: over['tuned'] {piece: {...}})
        return Springs(S, colliders=True, caps='body', settings=over.get('tuned'))
    if name == 'springs_tuned_skin':            # (the same, each chain's first joint riding the skin: round 3)
        return Springs(S, colliders=True, caps='body', settings=over.get('tuned'), root='skin')
    if name == 'springs_body':                  # (the graph's settings against the body colliders: the tuning's before)
        return Springs(S, colliders=True, caps='body')
    if name.startswith('springs'):
        return Springs(S, colliders=name == 'springs_col')
    if name == 'pelvis_rigid':
        return Rigid(S)
    if name == 'skinned_shuffled':              # (a random rig: the calibration's floor)
        return Shuffled(S, seed=int(over.get('seed', 0)))
    base = name.replace('_r1', '').replace('_nocol', '')
    kw = dict(CLOTH)
    if name.endswith('_r1'):
        kw = dict(colliders='legs', pins='own')
    if name.endswith('_nocol'):
        kw['colliders'] = 'none'
    over = dict(over)
    over.pop('ramp', None)
    if base == 'xpbd_physics':
        hold_shape = 0.0
    if hold_shape is not None:
        over['hold_shape'] = float(hold_shape)
    return Cloth(S, style=style, hold_frame=HOLD_FRAMES[base], log=log, **dict(kw, **over))


class Shuffled:
    """the garments skinned with their coarse vertices' weights shuffled among them (seeded): a random rig, the motion
    checks' floor (charkit/calib/motion.py). The render mesh is the build's finalize of the moved coarse one."""

    def __init__(self, S, seed=0):
        self.S = S
        rng = np.random.default_rng(seed)
        self.W = {}
        for n in S.pieces:
            p = rng.permutation(len(S.co[n]['V']))
            self.W[n] = {b: np.asarray(w)[p] for b, w in S.cw[n].items()}

    def frame(self, D, dt):
        co = {n: riglib.lbs(self.S.co[n]['V'], self.W[n], D) for n in self.S.pieces}
        return _Finals(self.S, co), co


class Rigid:
    """the garments carried by the pelvis alone (as the flaps are shipped; the cloth's hold target, no cloth)."""

    def __init__(self, S):
        self.S = S

    def frame(self, D, dt):
        S = self.S
        W = lambda n, V: {'hips': np.ones(len(V))}
        fin = {n: riglib.lbs(S.fin[n]['V'], W(n, S.fin[n]['V']), D) for n in S.pieces}
        co = {n: riglib.lbs(S.co[n]['V'], W(n, S.co[n]['V']), D) for n in S.pieces}
        return fin, co


# ------------------------------------------------------------------------------------------------------------ the run
def run(build, out, poses=LEG_POSES, methods=METHODS, every=6, style='anime', tuned=None, tuned_skin=None, log=print):
    from ..evalmesh import POSES
    os.makedirs(out, exist_ok=True)
    S = Scene(build, log=log)
    rep = dict(build=build, L=S.L, fps=FPS, settle=SETTLE, ramp=RAMP, hold=HOLD, pieces=list(S.pieces), style=style,
               capsules=[{k: (v.tolist() if hasattr(v, 'tolist') else v) for k, v in c.items()}
                         for c in S.colliders('body')],
               poses={})
    for pose in poses:
        fs, n0 = S.schedule(pose)
        rep['poses'][pose] = {}
        for m in methods:
            t0 = time.time()
            M = method(S, m, style=style, log=log, **({'tuned': tuned} if m == 'springs_tuned' else
                                                      {'tuned': tuned_skin} if m == 'springs_tuned_skin' else {}))
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
                                               for n in S.pieces}
                    rows.append(r)
                last = fin
            np.savez(os.path.join(out, 'end_%s_%s.npz' % (pose, m)), **last)
            rep['poses'][pose][m] = dict(frames=rows, seconds=round(time.time() - t0, 1),
                                         layer=getattr(M, 'nlayer', None))
            e = rows[-1]['pieces']
            log('%s %s: end new %s; %.1f s' % (pose, m, ', '.join('%s %.3f / %.3f L' % (n[-6:], e[n]['new_share'],
                                                                                  e[n]['new_depth'])
                                                            for n in S.pieces), time.time() - t0))
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
            for n in rep.get('pieces') or PIECES:
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
    best = lambda p: p and {n: {k: r['best'][k] for k in ('stiffness', 'gravity', 'drag')}
                            for n, r in json.load(open(p))['pieces'].items() if 'best' in r}
    run(build, opt('--out', os.path.join(build, 'sim_motion')), poses=tuple(opt('--poses', ','.join(LEG_POSES)).split(',')),
        methods=tuple(opt('--methods', ','.join(METHODS)).split(',')), every=int(opt('--every', 6)),
        tuned=best(opt('--tuned')), tuned_skin=best(opt('--tuned-skin')))
    return 0


# ------------------------------------------------------------------------------------ tuning the spring chains from XPBD
def _run_chains(chains, Ds, caps_of):
    """chains through frames Ds (their root: chain_root's) -> (frames, joints, 3) of their tails."""
    out = []
    for k, D in enumerate(Ds):
        caps = caps_of(D)
        P = []
        for ch in chains:
            Dr = chain_root(ch, D)
            if k == 0:
                ch.reset(Dr)
            ch.step(Dr, 1.0 / FPS, caps)
            P.append(ch.cur)
        out.append(np.concatenate(P))
    return np.array(out)


def tune_springs(build, out, poses=('kick', 'squat'), ref='xpbd_hips', grid=None, caps='body', style='anime',
                 root='hips', log=print):
    """the spring chains' settings fitted to the cloth (real-time VRM from the bake's reference): the reference method
    (the style's cloth) through each pose records every frame's coarse garments; each chain joint follows the template
    point it starts on; per piece every (stiffness, gravity, drag) of the grid runs its chains through the same frames
    against the fitted capsules (`caps`: S.colliders' set, shrunk to clear the chains' rest joints: VRM's colliders),
    scored by the joints' mean distance from the reference's points (L), over the motion after the settle, averaged
    over the poses. Then the graph's settings and the best are run as garments (Springs) and measured as motion QA
    measures: new penetration and stretch, at rest (settled) and over the motion. -> out/tune.json, tune.md."""
    from ..evalmesh import POSES
    os.makedirs(out, exist_ok=True)
    S = Scene(build, log=log)
    grid = grid or dict(stiffness=(0.5, 1.0, 2.0, 4.0, 8.0), gravity=(0.0, 0.05, 0.15, 0.3), drag=(0.3, 0.5, 0.7, 0.9))
    sp0 = Springs(S, colliders=True, caps=caps, root=root)
    cap_rows = lambda D: riglib.capsule_rows(sp0.caps, D)
    traj, Ds, n0s = {}, {}, {}
    for pose in poses:
        fs, n0 = S.schedule(pose)
        M = method(S, ref, style=style, log=log)
        traj[pose] = {n: [] for n in S.pieces}
        Ds[pose] = []
        n0s[pose] = n0
        for f in fs:
            D = S.rig.skinning(POSES[pose], f)
            Ds[pose].append(D)
            _, co = M.frame(D, 1.0 / FPS)
            for n in S.pieces:
                traj[pose][n].append(co[n])
        log('tune: reference %s through %s' % (ref, pose))
    rep = dict(build=build, poses=list(poses), ref=ref, grid=grid, root=root, caps=[dict(name=c['name'], r_L=c['r'] / S.L,
                                                                             r_fit_L=c['r_fit'] / S.L)
                                                                        for c in sp0.caps], pieces={})

    def score(n, chains, idx, st):
        e = dict(motion=[], rest=[], end=[])
        for pose in poses:
            R = np.array([t[idx] for t in traj[pose][n]])
            chs = [springbone.Chain(ch.J, stiffness=st['stiffness'], drag=st['drag'], gravity=st['gravity'],
                                    gravity_dir=ch.gdir, hit_radius=ch.hit) for ch, _, _ in chains]
            for c, (ch, _, _) in zip(chs, chains):
                c.root_w, c.root_rot = ch.root_w, ch.root_rot
            P = _run_chains(chs, Ds[pose], cap_rows)
            d = np.linalg.norm(P - R, axis=2).mean(1) / S.L
            e['motion'].append(d[n0s[pose] - 1:].mean())
            e['rest'].append(d[n0s[pose] - 1])
            e['end'].append(d[-1])
        return {k: float(np.mean(v)) for k, v in e.items()}

    best_set = {}
    for n, chains in sp0.chains.items():
        V0 = S.co[n]['V']
        idx = np.array([int(np.argmin(np.linalg.norm(V0 - j, axis=1))) for ch, _, _ in chains for j in ch.J[1:]])
        g = next(s for s in S.graph['springs'] if s['piece'] == n)
        base = dict(stiffness=g['stiffness'], gravity=g['gravity'], drag=g['drag'])
        rows = []
        for st in grid['stiffness']:
            for gr in grid['gravity']:
                for dr in grid['drag']:
                    x = dict(stiffness=st, gravity=gr, drag=dr)
                    rows.append(dict(x, **{'err_' + k: v for k, v in score(n, chains, idx, x).items()}))
        best = min(rows, key=lambda r: r['err_motion'])
        best_set[n] = {k: best[k] for k in ('stiffness', 'gravity', 'drag')}
        rep['pieces'][n] = dict(graph=dict(base, **{'err_' + k: v for k, v in score(n, chains, idx, base).items()}),
                                best=best, rows=rows, hit_radius_L=chains[0][0].hit / S.L, chains=len(chains))
        log('tune %s: graph %s err %.3f L (rest %.3f) -> best %s err %.3f L (rest %.3f)' % (
            n, base, rep['pieces'][n]['graph']['err_motion'], rep['pieces'][n]['graph']['err_rest'], best_set[n],
            best['err_motion'], best['err_rest']))
    # the garments on the chains, as motion QA measures them: the graph's settings against the tuned
    for label, sett in (('graph', None), ('tuned', best_set)):
        for pose in poses:
            M = Springs(S, colliders=True, settings=sett, caps=caps, root=root)
            rows = []
            for k, D in enumerate(Ds[pose]):
                fin, co = M.frame(D, 1.0 / FPS)
                if k >= n0s[pose] - 1 and ((k - n0s[pose] + 1) % 6 == 0 or k == len(Ds[pose]) - 1):
                    rows.append(S.measure(D, fin, co))
            for n in S.pieces:
                rep['pieces'].setdefault(n, {}).setdefault('garment', {}).setdefault(label, {})[pose] = dict(
                    rest_inside=rows[0][n]['new_share'], worst_inside=max(r[n]['new_share'] for r in rows),
                    worst_depth=max(r[n]['new_depth'] for r in rows), worst_stretch=max(r[n]['stretch_p99'] for r in rows))
            log('tune: %s chains through %s measured' % (label, pose))
    json.dump(rep, open(os.path.join(out, 'tune.json'), 'w'), indent=1)
    L_ = ['# The spring chains tuned to the cloth (%s; reference %s)' % (', '.join(poses), ref), '',
          "Per piece, its chains' joints against the reference cloth's material points (mean distance, L): over the "
          'motion after the settle, settled at rest, at the end (averaged over the poses). The graph\'s settings and the '
          'best of the grid %s. Colliders (VRM capsules, shrunk to clear the chains\' rest joints): %s.' % (
              json.dumps(grid), ', '.join('%s %.3f L' % (c['name'], c['r_L']) for c in rep['caps'])), '',
          '| piece | settings | stiffness | gravity | drag | err motion | err rest | err end |', '|---|---|---|---|---|---|---|---|']
    for n, r in rep['pieces'].items():
        for k in ('graph', 'best'):
            if k not in r:
                continue
            x = r[k]
            L_.append('| %s | %s | %s | %s | %s | %.3f | %.3f | %.3f |' % (n, k, x['stiffness'], x['gravity'], x['drag'],
                                                                         x['err_motion'], x['err_rest'], x['err_end']))
    L_ += ['', "The garments on the chains, measured as motion QA measures them (new inside share at rest settled; worst "
           'share, depth L and stretch p99 over the motion):', '',
           '| piece | pose | graph: rest / worst / depth / stretch | tuned: rest / worst / depth / stretch |',
           '|---|---|---|---|']
    for n, r in rep['pieces'].items():
        for pose in poses:
            a, b = r['garment']['graph'][pose], r['garment']['tuned'][pose]
            L_.append('| %s | %s | %.3f / %.3f / %.3f / %.2f | %.3f / %.3f / %.3f / %.2f |' % (
                n, pose, a['rest_inside'], a['worst_inside'], a['worst_depth'], a['worst_stretch'], b['rest_inside'],
                b['worst_inside'], b['worst_depth'], b['worst_stretch']))
    open(os.path.join(out, 'tune.md'), 'w').write('\n'.join(L_) + '\n')
    return rep
