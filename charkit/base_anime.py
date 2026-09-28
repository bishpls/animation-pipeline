"""charkit's anime base mesh (docs/CHARKIT.md §2): our topology, derived once from MakeHuman's CC0 base (hm08) through the
default anime wrap and cleaned for anime use, stored with its regions and landmarks as data, so a build stops re-detecting
(eye margins by normals, mouth corners by fold curvature, cavities by flood fill) and fighting realistic topology.

    python -m charkit.base_anime derive        # once: writes charkit/assets/base_anime/base_anime.npz
    spec['base'] = 'anime'                     # a build on it (charkit/character.py); 'makehuman' (the default) as before

derive(): MakeHuman's body with its own head wrapped onto the anime head at neutral knobs (character.assemble, base
'makehuman': eyes on the default outline, the neutral mouth), then cleaned:
  - each eye's deep pocket (the realistic socket bag round the eyeball, 280 vertices) -> a shallow socket: two rings and a
    cap behind the margin loop, sized to sit just behind the anime eye plate (the lid-thickness wall, then the floor);
  - the lid rings round each opening re-laid: the wrap had folded them back over the opening (the realistic lids stretched
    onto the far bigger anime outline, the lid crease collapsed flat), so every face there faced away. The band's outer
    ring is pushed clear of the outline (a monotone radial push, fading out) and each radial chain of rings straightened
    from the margin to it, nearly flat on the face: clean concentric loops round an anime almond;
  - the mouth's large realistic cavity (430 vertices) -> a compact bag of five rings and a cap behind the lips' loop (the
    teeth and the tongue fit it); the lip rolls relaxed in the face's plane and flattened (the anime mouth is a line);
  - the nostrils (a web of rings under the nose) cut out and grid-filled, the nose's underside relaxed: a soft nose;
  - the ears' realistic folds flattened inside the helix: a clean anime ear;
  - the under-jaw/neck junction (where the wrap meets the neck) filleted at the throat and smoothed into one sheet;
  - MakeHuman's UVs kept (new faces get UVs interpolated from their rims; the 'face' projection is computed at build),
    skin weights kept and re-derived for new vertices from the rims they grow from, the joints kept.
The asset stores: verts, faces, UVs, skin weights (VRM bones) and MakeHuman's face-bone masks, joints, the source vertex in
hm08 of every vertex (so MakeHuman's macro targets still shape the body), region masks, the eye and mouth loops, rings and
schedules, landmarks, and the wrap's parameters (per shell vertex: the realistic direction and the neutral surface point),
so charkit/anime_head.rewrap re-shapes the head to a spec's knobs without MakeHuman's head. The 'head_detail' knobs
(reshape's detail shares) are baked in; the 'ear' knob scales the stored ear relief.

Licence: derived from MakeHuman's CC0 1.0 assets (charkit/assets/makehuman/LICENSE.md); the derived asset is CC0 too.
"""
import json, math, os
from collections import defaultdict, deque

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ASSET = os.path.join(HERE, 'assets', 'base_anime', 'base_anime.npz')
VERSION = 1

# the shallow eye socket behind the margin, per ring: (pull toward the eye's centre, depth behind the eye plate); the last
# is the cap. Ring 1 is the lid's thickness (drawn as the eye line), just behind the plate's rim; the floor stays shallow.
SOCKET = [(0.04, 0.0012), (0.45, 0.0020), (1.0, 0.0024)]
# the compact mouth cavity, per ring: (depth share of the mouth's 'depth' knob, pull toward the opening's centre); the last
# is the cap. The same funnel as MakeHuman's first rings (charkit/mouth.py), closed within five rings.
CAVITY = [(0.12, 0.22), (0.30, 0.32), (0.55, 0.45), (0.80, 0.59), (1.0, 0.70), (1.0, 1.0)]
NOSTRIL_RINGS = 6            # the nostril web cut out: this many rings round its apex
EYE_BAND = 13                # the rings round each eye opening re-laid (the lid rings the wrap folded over the opening, the
                             # collapsed lid crease beyond them): ring 13 is the first clear of the anime outline
EYE_CLEAR = 0.045            # ... pushed clear of the outline by this (in L), what lies beyond following within EYE_REACH
EYE_REACH = 0.1
LIP_BAND = 9                 # the rings round the lips relaxed (the lip rolls)
LIP_FLAT = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]      # their depth offsets from the face kept (rings 1..8)
EYE_OUTER, MOUTH_OUTER = 18, 12                          # rings stored as the eye's / the mouth's outer rings: the skin that
                                                         # follows the loops' moves (the spread fades it; enough rings that it
                                                         # is not cut off)
EAR_RIM = 3                  # the ear's outer rings kept as the helix; inside them the folds are flattened
EAR_SMOOTH = 12              # Laplacian passes over the ear's inside
NECK_BLEND = (0.15, 0.3)     # head weights over which the neck's top blends from body-relative to base placement at build
JAW_HW = 0.3                 # the junction relaxed where the head's weight is above this (below it: the neck, garments')
JAW_FILLET = 20              # Laplacian passes filleting the throat's corner (the under-jaw meeting the neck)
JAW_SMOOTH = 40              # Taubin passes over the under-jaw/neck junction

REGIONS = ['body', 'neck', 'head', 'face', 'scalp', 'ears', 'nose', 'lips', 'jaw', 'under_jaw', 'eye_margin',
           'eye_socket', 'eye_lids', 'mouth_loop', 'mouth_cavity', 'nostril_fill', 'new']


# -------------------------------------------------------------------------------------------------------------- editing
class Edit:
    """a mesh under edit: vertices can be removed (their faces with them) and added (each with a recipe [(old vertex,
    weight)] that its skin weights and other attributes are interpolated from); faces carry their UV corners."""

    def __init__(self, V, faces, face_uv, uvs):
        self.n0 = len(V)
        self.V = np.array(V, float)
        self.faces = [tuple(f) for f in faces]
        self.fuv = [tuple(u) for u in face_uv]
        self.uvs = [tuple(u) for u in uvs]
        self.alive = [True] * len(self.faces)
        self.dead = set()
        self.recipe = []                      # for vertex n0 + k

    def add_vertex(self, p, recipe):
        self.V = np.vstack([self.V, np.asarray(p, float)[None]])
        self.recipe.append(recipe)
        return len(self.V) - 1

    def add_uv(self, uv):
        self.uvs.append(tuple(float(x) for x in uv))
        return len(self.uvs) - 1

    def add_face(self, f, fuv):
        self.faces.append(tuple(f)); self.fuv.append(tuple(fuv)); self.alive.append(True)

    def live_faces(self):
        return [f for f, a in zip(self.faces, self.alive) if a]

    def adjacency(self):
        nb = defaultdict(set)
        for f in self.live_faces():
            for a, b in zip(f, f[1:] + f[:1]):
                nb[a].add(b); nb[b].add(a)
        return nb

    def remove(self, vs):
        """remove vertices (and every face touching them). -> the holes' boundary loops, each ordered as the removed faces
        ran round it (so new faces continue the surface's orientation), and {loop vertex: a UV index from those faces}."""
        vs = set(int(v) for v in vs)
        gone = [fi for fi, f in enumerate(self.faces) if self.alive[fi] and any(v in vs for v in f)]
        for fi in gone:
            self.alive[fi] = False
        # vertices left with no face (every face of theirs touched a removed one) go too
        touched = {v for fi in gone for v in self.faces[fi]} - vs
        live = {v for fi, f in enumerate(self.faces) if self.alive[fi] for v in f if v in touched}
        self.dead |= vs | (touched - live)
        directed, vuv = [], {}
        live_edges = defaultdict(int)
        for fi in gone:
            f = self.faces[fi]
            for k, (a, b) in enumerate(zip(f, f[1:] + f[:1])):
                if a not in self.dead and b not in self.dead:
                    directed.append((a, b))
                if a not in self.dead:
                    vuv.setdefault(a, self.fuv[fi][k])
        for fi, f in enumerate(self.faces):
            if self.alive[fi]:
                for a, b in zip(f, f[1:] + f[:1]):
                    live_edges[(min(a, b), max(a, b))] += 1
        nxt = {a: b for a, b in directed if live_edges[(min(a, b), max(a, b))] == 1}
        loops, seen = [], set()
        for a in nxt:
            if a in seen:
                continue
            lp = [a]; seen.add(a)
            while nxt.get(lp[-1]) is not None and nxt[lp[-1]] != a:
                lp.append(nxt[lp[-1]]); seen.add(lp[-1])
                if len(lp) > len(nxt):
                    raise RuntimeError('hole boundary is not a simple loop')
            loops.append(lp)
        return loops, vuv

    def fill(self, loop, vuv, ring_uv, cap=True):
        """close a hole: len(ring_uv) new rings (one vertex per loop vertex, weights from it) and a quad cap on a centre
        vertex. ring_uv: each ring's UV share toward the loop's UV centre. -> (rings [[vertex]], cap vertex or None)."""
        m = len(loop)
        prev = list(loop)
        uv0 = np.array([self.uvs[vuv[a]] for a in loop])
        uvc = uv0.mean(0)
        prev_uv = [vuv[a] for a in loop]
        rings = []
        for s in ring_uv:
            r = [self.add_vertex(self.V[a], [(a, 1.0)]) for a in loop]
            ru = [self.add_uv(u + (uvc - u) * s) for u in uv0]
            for j in range(m):
                j2 = (j + 1) % m
                self.add_face((prev[j], prev[j2], r[j2], r[j]), (prev_uv[j], prev_uv[j2], ru[j2], ru[j]))
            rings.append(r)
            prev, prev_uv = r, ru
        c = None
        if cap:
            c = self.add_vertex(self.V[list(loop)].mean(0), [(a, 1.0 / m) for a in loop])
            cu = self.add_uv(uvc)
            for j in range(0, m - 1, 2):
                self.add_face((c, prev[j], prev[j + 1], prev[(j + 2) % m]), (cu, prev_uv[j], prev_uv[j + 1], prev_uv[(j + 2) % m]))
            if m % 2:
                self.add_face((c, prev[m - 1], prev[0]), (cu, prev_uv[m - 1], prev_uv[0]))
        return rings, c

    def grid_fill(self, loop, vuv, nb):
        """close a hole whose loop has an even count m = 2 (a + b) with an a x b quad grid (a Coons patch of the loop, the
        corners on the loop vertices that keep the most edges outside). -> interior vertices, or None if m is odd."""
        m = len(loop)
        if m % 2 or m < 8:
            return None
        deg = np.array([len(nb[v]) for v in loop])
        best = None
        for a in range(2, m // 2 - 1):
            b = m // 2 - a
            if abs(a - b) > 2:
                continue
            for r in range(m):
                sc = deg[[(r) % m, (r + a) % m, (r + a + b) % m, (r + 2 * a + b) % m]].sum()
                if best is None or sc > best[0]:
                    best = (sc, a, b, r)
        _, a, b, r = best
        lp = list(loop[r:]) + list(loop[:r])
        G = [[None] * (b + 1) for _ in range(a + 1)]
        for i in range(a + 1):
            G[i][0] = lp[i]; G[a - i][b] = lp[a + b + i]
        for j in range(b + 1):
            G[a][j] = lp[a + j]; G[0][b - j] = lp[(2 * a + b + j) % m]
        uvl = {v: np.array(self.uvs[vuv[v]]) for v in lp}

        def coons(get, i, j):
            u, v = i / a, j / b
            return ((1 - u) * get(G[0][j]) + u * get(G[a][j]) + (1 - v) * get(G[i][0]) + v * get(G[i][b])
                    - ((1 - u) * (1 - v) * get(G[0][0]) + u * (1 - v) * get(G[a][0]) + (1 - u) * v * get(G[0][b])
                       + u * v * get(G[a][b])))
        U = {}
        inner = []
        for i in range(1, a):
            for j in range(1, b):
                u, v = i / a, j / b
                rec = [(G[0][j], (1 - u) / 2), (G[a][j], u / 2), (G[i][0], (1 - v) / 2), (G[i][b], v / 2)]
                G[i][j] = self.add_vertex(coons(lambda x: self.V[x], i, j), rec)
                U[G[i][j]] = self.add_uv(coons(lambda x: uvl[x], i, j))
                inner.append(G[i][j])
        for v in lp:
            U[v] = vuv[v]
        for i in range(a):
            for j in range(b):
                f = (G[i][j], G[i + 1][j], G[i + 1][j + 1], G[i][j + 1])
                self.add_face(f, tuple(U[x] for x in f))
        return inner

    def compact(self):
        """-> (order: new index -> edit index, remap: edit index -> new index, verts, faces, face_uv, uvs)."""
        order = [i for i in range(self.n0) if i not in self.dead] + list(range(self.n0, len(self.V)))
        remap = {o: i for i, o in enumerate(order)}
        faces, fuv = [], []
        for f, u, a in zip(self.faces, self.fuv, self.alive):
            if a:
                faces.append(tuple(remap[v] for v in f)); fuv.append(u)
        used = sorted({x for u in fuv for x in u})
        uremap = {o: i for i, o in enumerate(used)}
        fuv = [tuple(uremap[x] for x in u) for u in fuv]
        uvs = np.array([self.uvs[i] for i in used])
        return order, remap, self.V[order], faces, fuv, uvs

    def attribute(self, arr, order):
        """a per-vertex attribute (old vertices) carried to the compacted mesh (new vertices by their recipes)."""
        arr = np.asarray(arr)
        out = np.zeros((len(order),) + arr.shape[1:], arr.dtype if arr.dtype.kind == 'f' else float)
        for i, o in enumerate(order):
            if o < self.n0:
                out[i] = arr[o]
            else:
                out[i] = sum(w * arr[s] for s, w in self.recipe[o - self.n0])
        return out


def _relax(V, nb, free, iters, lam=0.5, mu=None):
    """uniform Laplacian (or Taubin with mu) on the free vertices (a list), the rest fixed."""
    V = V.copy()
    free = list(free)
    if not free:
        return V
    deg = max(len(nb[i]) for i in free)
    T = np.full((len(free), deg), -1, int)
    for r, i in enumerate(free):
        T[r, :len(nb[i])] = sorted(nb[i])
    valid = T >= 0; Tc = np.where(valid, T, 0); cnt = np.maximum(valid.sum(1), 1)[:, None]
    idx = np.array(free)
    for _ in range(iters):
        for f in ((lam, mu) if mu is not None else (lam,)):
            avg = (V[Tc] * valid[..., None]).sum(1) / cnt
            V[idx] += f * (avg - V[idx])
    return V


def _loft_band(V, nb, loop, rings, K, Fc, keep):
    """re-lay the band of rings 1..K-1 round an opening (ring 0, its loop, and ring K fixed): each radial chain (loop vertex
    -> its neighbour in the next ring -> ... -> ring K) straightened in the face's plane, the rings spaced evenly along it,
    each vertex seated back on the anime face at keep(ring / K) of its old offset from it. Unfolds lid rings that the wrap
    folded over the opening (the realistic lids stretched onto the far bigger anime outline) and the collapsed lid crease.
    (A uniform harmonic solve would not do: 28 vertices round and 13 rings out has the wrong conformal modulus, and the
    solution dips back into the opening.)"""
    done = {}
    for m in loop:
        ch = [m]
        for r in range(1, K + 1):
            nxt = [w for w in nb[ch[-1]] if rings.get(w) == r]
            if not nxt:
                break
            ch.append(min(nxt, key=lambda w: np.linalg.norm(V[w] - V[ch[-1]])))
        if len(ch) < K + 1:
            continue
        a, b = V[ch[0]], V[ch[-1]]
        for r in range(1, K):
            if ch[r] in done:
                continue
            t = (r / K) ** 1.1
            x, z = a[0] + (b[0] - a[0]) * t, a[2] + (b[2] - a[2]) * t
            off = V[ch[r], 1] - Fc.y(V[ch[r], 0], V[ch[r], 2])
            done[ch[r]] = [x, Fc.y(x, z) + off * keep(r / K), z]
    X = V.copy()
    for v, p in done.items():
        X[v] = p
    return X, len(done)


def _clear_outline(V, rings, K, cand, Fc, K_eye, L, side, c, clear, reach):
    """push the band's outer ring K clear of the anime eye outline by at least `clear` (metres), radially from the outline's
    centre in the face's plane. Everything beyond the band on this side (cand: vertices) within `reach` of the outline moves
    too, the push fading with the distance d from the outline as (1 - d / reach)^2; reach > 2 x the largest push keeps the
    map monotone along each ray, so nothing folds. -> V."""
    from . import eyes as eyelib
    poly = eyelib.outline_polygon(K_eye, L, n=64)
    oc = poly.mean(0)
    ang = np.arctan2(poly[:, 1] - oc[1], poly[:, 0] - oc[0])
    o = np.argsort(ang)
    ang, rad = ang[o], np.linalg.norm(poly - oc, axis=1)[o]
    ang = np.concatenate([ang[-1:] - 2 * np.pi, ang, ang[:1] + 2 * np.pi]); rad = np.concatenate([rad[-1:], rad, rad[:1]])
    ex, ez = c

    def polar(p):
        u = np.array([(p[0] - ex) * side, p[2] - ez]) - oc
        th = math.atan2(u[1], u[0])
        rho = float(np.hypot(*u))
        return th, rho, rho - float(np.interp(th, ang, rad))
    h = lambda d: max(0.0, 1 - d / reach) ** 2
    th_k, dl_k = [], []
    for v, r in rings.items():
        if r == K:
            th, rho, d = polar(V[v])
            th_k.append(th); dl_k.append(max(0.0, clear - d) / max(h(d), 1e-3))
    o = np.argsort(th_k)
    th_k = np.array(th_k)[o]; dl_k = np.array(dl_k)[o]
    th_k = np.concatenate([th_k[-1:] - 2 * np.pi, th_k, th_k[:1] + 2 * np.pi]); dl_k = np.concatenate([dl_k[-1:], dl_k, dl_k[:1]])
    if dl_k.max() * 2 > reach:
        raise RuntimeError('eye band: the push (%.1f mm) needs a longer reach' % (dl_k.max() * 1000))
    X = V.copy()
    for v in cand:
        th, rho, d = polar(V[v])
        if d <= 0 or d >= reach:
            continue
        # fade out toward the face's side edge (the face lookup holds on the front only)
        side_k = abs(V[v, 0]) / Fc.H.section(V[v, 2] - Fc.c[2])[0]
        push = float(np.interp(th, th_k, dl_k)) * h(d) * float(np.clip((0.9 - side_k) / 0.2, 0, 1))
        if push <= 0:
            continue
        off = V[v, 1] - Fc.y(V[v, 0], V[v, 2])
        u = oc + (rho + push) * np.array([math.cos(th), math.sin(th)])
        x, z = ex + side * u[0], ez + u[1]
        X[v] = [x, Fc.y(x, z) + off, z]
    return X


def _relax_face(V, nb, rings, Fc, keep, iters=30):
    """relax a band of rings round an opening in the face's plane (x, z; the opening's loop and the outer rings fixed), then
    seat each vertex back on the anime face at a share of its old offset from it: keep[ring - 1] (0 = on the face)."""
    free = [v for v, r in rings.items() if 1 <= r <= len(keep)]
    off = {v: V[v, 1] - Fc.y(V[v, 0], V[v, 2]) for v in free}
    X = _relax(V, nb, free, iters)
    for v in free:
        X[v, 1] = Fc.y(X[v, 0], X[v, 2]) + off[v] * keep[rings[v] - 1]
    return X


def _rings(nb, seeds, allowed=None, stop=99):
    ring = {s: 0 for s in seeds}
    q = deque(seeds)
    while q:
        u = q.popleft()
        if ring[u] >= stop:
            continue
        for w in nb[u]:
            if w not in ring and (allowed is None or w in allowed):
                ring[w] = ring[u] + 1; q.append(w)
    return ring


# ------------------------------------------------------------------------------------------------------------ detection
def _nostrils(BB, nb, head):
    """the nostrils on MakeHuman's base (Blender frame): each a web of rings under the nose round its apex (the highest point
    of the nose's underside). -> [set of vertices to cut out] per side."""
    mid = np.nonzero(head & (np.abs(BB[:, 0]) < 0.004))[0]
    eye_z = BB[head, 2].max() - 0.12
    mid = mid[(BB[mid, 2] < eye_z) & (BB[mid, 2] > eye_z - 0.08)]
    tip = BB[mid[np.argmin(BB[mid, 1])]]
    out = []
    for side in (1, -1):
        cand = np.nonzero(head & (np.linalg.norm(BB - tip, axis=1) < 0.025) & (BB[:, 0] * side > 0.003)
                          & (BB[:, 2] < tip[2]) & (BB[:, 1] < tip[1] + 0.02))[0]
        apex = [i for i in cand if all(BB[j, 2] < BB[i, 2] for j in nb[i])]
        if len(apex) != 1:
            raise RuntimeError('nostril apex: expected 1, found %d' % len(apex))
        ring = _rings(nb, [int(apex[0])], stop=NOSTRIL_RINGS)
        out.append({v for v, r in ring.items() if r < NOSTRIL_RINGS})
    return out, tip


def _ears(BB, faces, nb, head_w):
    """the ears on MakeHuman's base: the helix (the side's most outstanding point from the smooth head at ear height) and
    everything round it within the ear's outline (an ellipse in the side view, outside the skull). -> [set] per side."""
    from . import anime_head as ah
    region = head_w > 0.02
    S = ah.laplacian_smooth(BB, ah.adjacency(len(BB), faces), region, iters=120, lam=0.6, mu=-0.64)
    nS = ah.vertex_normals(S, faces)
    dn = ((BB - S) * nS).sum(1)
    head = head_w > 0.5
    eye_z = BB[head, 2].max() - 0.12
    out = []
    for side in (1, -1):
        sd = head & (BB[:, 0] * side > 0.05) & (np.abs(BB[:, 2] - eye_z) < 0.06)
        cand = np.nonzero(sd)[0]
        p = int(cand[np.argmax(dn[cand])])
        comp = _rings(nb, [p], allowed=set(np.nonzero(sd & (dn > 0.001))[0].tolist()))
        c = np.array(list(comp))
        lo, hi = BB[c].min(0), BB[c].max(0)
        cy, cz = (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2
        ay, az = (hi[1] - lo[1]) / 2 + 0.006, (hi[2] - lo[2]) / 2 + 0.012
        x_in = float(np.abs(BB[c, 0]).min()) - 0.012
        ell = ((BB[:, 1] - cy) / ay) ** 2 + ((BB[:, 2] - cz) / az) ** 2 < 1
        out.append(set(np.nonzero(head & ell & (BB[:, 0] * side > x_in))[0].tolist()))
    return out


# -------------------------------------------------------------------------------------------------------------- derive
def derive(path=ASSET, log=print):
    """build the anime base from MakeHuman + the neutral anime wrap, clean it, and save it (see the module doc)."""
    from . import anime_head as ah, character, eyes as eyelib, head as headlib, mouth as mouthlib
    A = character.assemble({'name': 'base', 'base': 'makehuman'})
    B = A['body']; Hd = A['head']; L = Hd['L']; H = Hd['H']; c0 = Hd['centre']; info = Hd['info']
    EK = eyelib._knobs(None); MK = mouthlib._knobs(None)
    Fc = eyelib.Face(H, c0)
    ed = Edit(A['verts'], B['faces'], B['face_uv'], B['uvs'])
    nb0 = ed.adjacency()
    BB = B['base_body']
    hw = B['head_w']
    # --- the eyes: the pocket out, a shallow socket in
    eyes = []
    for E in A['eyes']:
        e = E['eye']
        loops, vuv = ed.remove(e['pocket'])
        if len(loops) != 1 or set(loops[0]) != set(e['margin']):
            raise RuntimeError('eye pocket: its hole is not the margin loop')
        rings, cap = ed.fill(loops[0], vuv, [0.25, 0.7])
        sock = {}
        for k, r in enumerate(rings):
            for a, v in zip(loops[0], r):
                sock[v] = (a, SOCKET[k][0], SOCKET[k][1], k + 1)
        sock[cap] = (loops[0][0], SOCKET[2][0], SOCKET[2][1], 3)
        eyes.append(dict(side=E['side'], c=E['c'], e=e, sock=sock))
    # --- the mouth: the cavity out, a compact one in
    M = A['mouth']['m']
    loops, vuv = ed.remove(M['cavity'])
    lp_set = set(M['upper']) | set(M['lower'])
    if len(loops) != 1 or set(loops[0]) != lp_set:
        raise RuntimeError('mouth cavity: its hole is not the lips loop')
    rings, cap = ed.fill(loops[0], vuv, [0.15, 0.3, 0.5, 0.7, 0.85])
    cav = {}
    for k, r in enumerate(rings):
        for a, v in zip(loops[0], r):
            cav[v] = (a, CAVITY[k][0], CAVITY[k][1], k + 1)
    cav[cap] = (loops[0][0], CAVITY[-1][0], CAVITY[-1][1], len(CAVITY))
    # --- the nostrils: cut out and filled
    head_mask = hw > 0.5
    nost, _ = _nostrils(BB, nb0, head_mask)
    nost_fill = []
    for cut in nost:
        loops, vuv = ed.remove(cut)
        if len(loops) != 1:
            raise RuntimeError('nostril: %d boundary loops' % len(loops))
        inner = ed.grid_fill(loops[0], vuv, nb0)
        if inner is None:
            rings, cap = ed.fill(loops[0], vuv, [0.5])
            inner = [v for r in rings for v in r] + [cap]
        nost_fill.append((loops[0], inner))
    ears = _ears(BB, B['faces'], nb0, hw)
    log('removed %d vertices, added %d' % (len(ed.dead), len(ed.V) - ed.n0))
    # --- positions. The lid rings round each eye opening (folded back over the opening where the realistic lids were
    # stretched onto the big anime outline) re-laid, the lip rings (the lip rolls) relaxed in the face's plane, both seated
    # back on the face nearly flat; then the sockets and the cavity by the eye and mouth placement rules (the margin and the
    # loop stay where they are).
    V = ed.V
    nb = ed.adjacency()
    hw_e = lambda v: hw[v] if v < ed.n0 else 1.0
    for X in eyes:
        e = dict(X['e'])
        e['pocket'] = {v: s_[3] for v, s_ in X['sock'].items()}
        e['socket'] = {v: s_[:3] for v, s_ in X['sock'].items()}
        # the band round the margin (away from the socket): the detected lid rings and the collapsed lid crease beyond
        band = _rings(nb, e['margin'], allowed={v for v in nb if v not in X['sock']}, stop=EYE_BAND + 12)
        cand = [v for v, r in band.items() if r >= EYE_BAND and V[v, 0] * X['side'] > 0 and hw_e(v) > 0.5]
        V = _clear_outline(V, band, EYE_BAND, cand, Fc, EK, L, X['side'], X['c'], EYE_CLEAR * L, EYE_REACH * L)
        V, nl = _loft_band(V, nb, e['margin'], {v: r for v, r in band.items() if r <= EYE_BAND}, EYE_BAND, Fc,
                           lambda t: t ** 1.5)
        log('eye band: %d of %d vertices re-laid' % (nl, sum(1 for r in band.values() if 0 < r < EYE_BAND)))
        e['outer'] = {v: r for v, r in band.items() if 0 < r <= EYE_OUTER}
        V, _ = eyelib.place(V, e, Fc, EK, L, X['side'], X['c'])
        X['e'] = e
    Mn = dict(M)
    Mn['cavity'] = {v: s_[3] for v, s_ in cav.items()}
    Mn['cavity_src'] = {v: s_[:3] for v, s_ in cav.items()}
    Mn['side'] = {v: s_ for v, s_ in M['side'].items() if v not in ed.dead}
    for v, s_ in cav.items():
        Mn['side'][v] = M['side'].get(s_[0], 'c')
    mc = A['mouth']['c']
    band = _rings(nb, list(lp_set), allowed={v for v in nb if v not in cav}, stop=max(LIP_BAND, MOUTH_OUTER))
    Mn['outer'] = {v: r for v, r in band.items() if 0 < r <= MOUTH_OUTER}
    side = dict(Mn['side'])
    q_ = deque(v for v in band if v in side)
    while q_:                                                     # each new ring vertex's lip: the nearest chain's
        u = q_.popleft()
        for w in nb[u]:
            if w in band and w not in side:
                side[w] = side[u]; q_.append(w)
    Mn['side'] = side
    V = _relax_face(V, nb, band, Fc, LIP_FLAT, iters=300)
    V = mouthlib.place(V, Mn, Fc, MK, L, mc)
    # the nostril fills and the nose's underside: relaxed (the fill, its rim and two rings round it)
    for lp, fill in nost_fill:
        zone = _rings(nb, list(lp), stop=2)
        free = [v for v in set(zone) | set(fill) if v not in lp] + list(lp)
        V = _relax(V, nb, fill, 40)
        V = _relax(V, nb, free, 10, lam=0.5, mu=-0.53)
    # the ears: the folds inside (the concha, the antihelix, the tragus) flattened, the helix round them kept
    ear_v = set()
    for ear in ears:
        ear = {v for v in ear if v not in ed.dead}
        edge = [v for v in ear if any(w not in ear for w in nb[v])]
        depth = _rings(nb, edge, allowed=ear)
        inside = sorted(v for v, r in depth.items() if r >= EAR_RIM)
        V = _relax(V, nb, inside, EAR_SMOOTH, lam=0.5)
        V = _relax(V, nb, sorted(set(ear) - set(edge)), 10, lam=0.5, mu=-0.53)
        ear_v |= ear
    # --- the under-jaw/neck junction: what the wrap moved below the jawline and the head still owns (the jaw's underside,
    # the throat under the chin; not the lips; not the lower neck, head weight < 0.3, where the garments start and walk)
    # relaxed into one sheet from the jawline to the neck
    q = (V - c0) / L
    az = np.arctan2(q[:, 0], -q[:, 1])
    zjaw = np.array([headlib.jaw_z(H, a_) / L for a_ in az])
    lipz = set(Mn['outer']) | lp_set
    jw = [v for v in range(ed.n0) if v not in ed.dead and hw[v] > JAW_HW and q[v, 2] < zjaw[v] - 0.015 and v not in lipz
          and v not in ear_v]
    # the throat's corner (away from the jawline, which stays crisp) filleted first, then the whole sheet smoothed
    corner = [v for v in jw if q[v, 2] < zjaw[v] - 0.06]
    V = _relax(V, nb, corner, JAW_FILLET, lam=0.5)
    V = _relax(V, nb, jw, JAW_SMOOTH, lam=0.6, mu=-0.63)
    ed.V = V
    # --- compact, carry the attributes
    order, remap, Vn, faces, face_uv, uvs = ed.compact()
    N = len(Vn)
    src = np.array([o if o < ed.n0 else -1 for o in order])
    weights = {b: ed.attribute(w, order) for b, w in B['weights'].items()}
    face_w = {b: ed.attribute(w, order) for b, w in B['face_w'].items()}
    head_w = ed.attribute(hw, order)
    R = lambda v: remap[v]
    # --- labels
    lab = {}
    for X in eyes:
        s = 'L' if X['side'] > 0 else 'R'
        e = X['e']
        lab[f'eye_{s}_margin'] = np.array([R(v) for v in e['margin']])
        lab[f'eye_{s}_upper'] = np.array([R(v) for v in e['upper']])
        lab[f'eye_{s}_lower'] = np.array([R(v) for v in e['lower']])
        so = sorted(X['sock'].items())
        lab[f'eye_{s}_socket'] = np.array([[R(v), R(a), k] for v, (a, _, _, k) in so])
        ot = sorted(e['outer'].items())
        lab[f'eye_{s}_outer'] = np.array([[R(v), r] for v, r in ot])
    lab['eye_socket_sched'] = np.array(SOCKET)
    lab['mouth_corners'] = np.array([R(v) for v in M['corners']])
    lab['mouth_upper'] = np.array([R(v) for v in M['upper']])
    lab['mouth_lower'] = np.array([R(v) for v in M['lower']])
    lab['mouth_cavity'] = np.array([[R(v), R(a), k] for v, (a, _, _, k) in sorted(cav.items())])
    lab['mouth_cavity_sched'] = np.array(CAVITY)
    lab['mouth_outer'] = np.array([[R(v), r] for v, r in sorted(Mn['outer'].items())])
    code = {'u': 0, 'l': 1, 'c': 2}
    lab['mouth_side'] = np.array([[R(v), code[s]] for v, s in sorted(Mn['side'].items())])
    # --- regions (bit masks)
    reg = {k: np.zeros(N, bool) for k in REGIONS}
    q = (Vn - c0) / L
    nrm = ah.vertex_normals(Vn, faces)
    reg['body'] = head_w <= 0.02
    reg['head'] = head_w > 0.5
    reg['neck'] = ((head_w > 0.02) & (head_w <= 0.5)) | (weights.get('neck', np.zeros(N)) > 0.5)
    for X in eyes:
        e = X['e']
        reg['eye_margin'][[R(v) for v in e['margin']]] = True
        reg['eye_socket'][[R(v) for v in X['sock']]] = True
        reg['eye_lids'][[R(v) for v, r in e['outer'].items() if r <= 3]] = True
    reg['mouth_loop'][[R(v) for v in lp_set]] = True
    reg['mouth_cavity'][[R(v) for v in cav]] = True
    reg['lips'][[R(v) for v, r in Mn['outer'].items() if r <= 3]] = True
    reg['lips'] |= reg['mouth_loop']
    for _, fill in nost_fill:
        reg['nostril_fill'][[R(v) for v in fill]] = True
    reg['ears'][[R(v) for v in ear_v if v in remap]] = True
    reg['new'] = src < 0
    tipn = int(np.argmin(np.where(reg['head'] & (np.abs(Vn[:, 0]) < 0.004) & (q[:, 2] < -0.08) & (q[:, 2] > -0.2), Vn[:, 1], 9)))
    reg['nose'] = reg['head'] & (np.linalg.norm(Vn - Vn[tipn], axis=1) < 0.075 * L) & (nrm[:, 1] < 0.2) & ~reg['lips']
    reg['jaw'] = face_w.get('jaw', np.zeros(N)) > 0.3
    reg['under_jaw'] = np.zeros(N, bool)
    reg['under_jaw'][[R(v) for v in jw]] = True
    inner = reg['eye_socket'] | reg['mouth_cavity']
    reg['face'] = reg['head'] & (nrm[:, 1] < -0.35) & (q[:, 2] < 0.30) & (q[:, 2] > -H.chin / L * 1.02) & ~inner & ~reg['ears']
    reg['scalp'] = reg['head'] & ~reg['face'] & ~reg['ears'] & ~inner & ~reg['under_jaw'] & \
        ((q[:, 2] > 0.30) | ((q[:, 1] > 0.10) & (q[:, 2] > -0.20)) | (np.abs(nrm[:, 1]) < 0.5) & (q[:, 2] > -0.05))
    bits = np.zeros(N, np.uint32)
    for k, name in enumerate(REGIONS):
        bits[reg[name]] |= np.uint32(1 << k)
    # --- landmarks (world, the neutral build) and the wrap's data
    J = {k: np.asarray(v) for k, v in A['joints'].items()}
    lm = {}
    for X in eyes:
        s = 'L' if X['side'] > 0 else 'R'
        lm[f'eye_{s}'] = Fc.point(X['c'][0], X['c'][1])
        mg = X['e']['margin']
        lm[f'eye_{s}_inner'] = Vn[R(mg[0])]
        lm[f'eye_{s}_outer'] = Vn[R(X['e']['upper'][-1])]
    lm['mouth'] = Fc.point(mc[0], mc[1])
    lm['mouth_L'], lm['mouth_R'] = sorted([Vn[R(v)] for v in M['corners']], key=lambda p: -p[0])
    lm['nose_tip'] = Vn[tipn]
    lm['chin'] = c0 + H.surface(0.0, -H.chin)
    lm['skull_top'] = c0 + np.array([0.0, 0.0, H.top])
    for s, sg in (('L', 1), ('R', -1)):
        em = reg['ears'] & (Vn[:, 0] * sg > 0)
        lm[f'ear_{s}'] = Vn[em].mean(0)
    lm['head_centre'] = c0.copy()
    ringn = (head_w > 0.03) & (head_w < 0.2)
    lm['neck'] = Vn[ringn].mean(0)
    shell_new = [(k, R(v)) for k, v in enumerate(info['shell']) if v in remap and v < ed.n0]
    sk = np.array([k for k, _ in shell_new]); sv = np.array([v for _, v in shell_new])
    region = np.zeros(N, bool)
    region[src < 0] = True
    region[src >= 0] = hw[src[src >= 0]] > 0.02
    marks = B['marks']
    prof = np.array([(d, (y - marks['eye_l'][1]) / L) for d, y in info['profile']])
    # the ear's relief (for the 'ear' knob): each ear vertex's offset from the ear smoothed flat
    ear_idx = np.nonzero(reg['ears'])[0]
    nbn = defaultdict(set)
    for f in faces:
        for a, b in zip(f, f[1:] + f[:1]):
            nbn[a].add(b); nbn[b].add(a)
    flat = _relax(Vn, nbn, [v for v in ear_idx if all(w in set(ear_idx) for w in nbn[v])], 60, lam=0.5)
    ear_det = (Vn[ear_idx] - flat[ear_idx]) / L
    # the removed realistic interior (the pockets, the cavity, the nostril webs) as it sat after the neutral wrap: 'ghost'
    # points the joints follow at build as they do on the makehuman base (the head, jaw and neck joints sit among them)
    ghost = np.array(sorted(ed.dead))
    ghost_q = (A['verts'][ghost] - c0) / L
    # the neck's top (the wrap moved it, the cleaning did not): its neutral offset from MakeHuman's own body, so a build
    # places it from the spec's body as the makehuman base does (fully below NECK_BLEND[0] head weight, none above [1])
    from .anime_head import smoothstep
    nk = np.nonzero(region & (src >= 0) & (head_w < NECK_BLEND[1]))[0]
    neck_w = 1 - smoothstep(NECK_BLEND[0], NECK_BLEND[1], head_w[nk])
    neck_d0 = (Vn[nk] - B['verts'][src[nk]]) / L
    # --- save
    bones = sorted(weights); fbones = sorted(face_w)

    def sparse(W, names):
        vi, bi, wv = [], [], []
        for k, b in enumerate(names):
            nz = np.nonzero(W[b] > 1e-4)[0]
            vi.append(nz); bi.append(np.full(len(nz), k)); wv.append(W[b][nz])
        return (np.concatenate(vi).astype(np.int32), np.concatenate(bi).astype(np.uint16),
                np.concatenate(wv).astype(np.float32))
    wi, wb, wv = sparse(weights, bones)
    fi_, fb_, fv_ = sparse(face_w, fbones)
    flen = np.array([len(f) for f in faces], np.uint8)
    meta = dict(version=VERSION, source='MakeHuman hm08 base mesh (CC0 1.0) + charkit anime wrap at neutral knobs',
                licence='CC0 1.0 (derived from MakeHuman CC0 assets)', frame='Blender: metres, Z up, facing -Y, her left +X',
                n_verts=N, n_faces=len(faces), bones=bones, face_bones=fbones, regions=REGIONS,
                landmarks=sorted(lm), joints=sorted(J), L=float(L), centre=[float(x) for x in c0],
                lm_real={k: v for k, v in info['lm_real'].items()}, warps=list(info['warps']),
                c_anime=[float(x) for x in info['c_anime']], eye_knobs=EK, mouth_knobs=MK,
                mouth_c=[float(x) for x in mc], eye_c=[[float(x) for x in X['c']] for X in eyes])
    out = dict(meta=np.array(json.dumps(meta)), verts=Vn.astype(np.float32), faces=np.concatenate(faces).astype(np.int32),
               face_len=flen, uvs=uvs.astype(np.float32), face_uv=np.concatenate(face_uv).astype(np.int32),
               src=src.astype(np.int32), head_w=head_w.astype(np.float32), w_vert=wi, w_bone=wb, w_val=wv,
               fw_vert=fi_, fw_bone=fb_, fw_val=fv_, joints=np.array([J[k] for k in sorted(J)], np.float32),
               regions=bits, landmarks=np.array([lm[k] for k in sorted(lm)], np.float32),
               wrap_region=region, shell=sv.astype(np.int32), shell_rad=info['shell_rad'][sk].astype(np.float64),
               shell_P=((info['shell_P'][sk] - c0) / L), profile=prof, ear_idx=ear_idx.astype(np.int32),
               ear_det=ear_det.astype(np.float32), ghost_src=ghost.astype(np.int32), ghost_q=ghost_q,
               neck_idx=nk.astype(np.int32), neck_d0=neck_d0, neck_w=neck_w,
               **{k: v.astype(np.int32) for k, v in lab.items() if v.dtype.kind in 'iu'},
               **{k: v.astype(np.float64) for k, v in lab.items() if v.dtype.kind == 'f'})
    if path:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        np.savez_compressed(path, **out)
        log('wrote %s (%.2f MB): %d verts, %d faces' % (path, os.path.getsize(path) / 1e6, N, len(faces)))
    return out


# ----------------------------------------------------------------------------------------------------------------- load
class Base:
    """the stored anime base (see the module doc)."""

    def __init__(self, path=ASSET):
        if not os.path.exists(path):
            raise FileNotFoundError(f'{path}: run `python -m charkit.base_anime derive` first')
        d = np.load(path, allow_pickle=False)
        self.d = d
        self.meta = json.loads(str(d['meta']))
        self.verts = d['verts'].astype(np.float64)
        self.N = len(self.verts)
        fl = d['face_len']; ff = d['faces']; fu = d['face_uv']
        cut = np.concatenate([[0], np.cumsum(fl.astype(np.int64))])
        self.faces = [tuple(int(x) for x in ff[a:b]) for a, b in zip(cut[:-1], cut[1:])]
        self.face_uv = [tuple(int(x) for x in fu[a:b]) for a, b in zip(cut[:-1], cut[1:])]
        self.uvs = d['uvs'].astype(np.float64)
        self.src = d['src']
        self.head_w = d['head_w'].astype(np.float64)
        self.weights = self._dense(d['w_vert'], d['w_bone'], d['w_val'], self.meta['bones'])
        self.face_w = self._dense(d['fw_vert'], d['fw_bone'], d['fw_val'], self.meta['face_bones'])
        self.joints = {k: d['joints'][i].astype(np.float64) for i, k in enumerate(self.meta['joints'])}
        self.landmarks = {k: d['landmarks'][i].astype(np.float64) for i, k in enumerate(self.meta['landmarks'])}
        self.L = self.meta['L']
        self.centre = np.array(self.meta['centre'])
        bits = d['regions']
        self.regions = {k: (bits & np.uint32(1 << i)) > 0 for i, k in enumerate(self.meta['regions'])}

    def _dense(self, vi, bi, wv, names):
        out = {b: np.zeros(self.N) for b in names}
        for k, b in enumerate(names):
            m = bi == k
            out[b][vi[m]] = wv[m]
        return out

    def eye(self, side):
        """the eye dict charkit/eyes.py places and keys (as eyes.detect returns, plus the socket schedule)."""
        s = 'L' if side > 0 else 'R'
        d = self.d
        sched = d['eye_socket_sched']
        sock = {int(v): (int(a), float(sched[k - 1][0]), float(sched[k - 1][1])) for v, a, k in d[f'eye_{s}_socket']}
        return dict(margin=[int(v) for v in d[f'eye_{s}_margin']], upper=[int(v) for v in d[f'eye_{s}_upper']],
                    lower=[int(v) for v in d[f'eye_{s}_lower']],
                    pocket={int(v): int(k) for v, a, k in d[f'eye_{s}_socket']},
                    outer={int(v): int(r) for v, r in d[f'eye_{s}_outer']}, socket=sock)

    def mouth(self):
        """the mouth dict charkit/mouth.py places and keys (as mouth.detect returns, plus the cavity's schedule)."""
        d = self.d
        sched = d['mouth_cavity_sched']
        code = {0: 'u', 1: 'l', 2: 'c'}
        return dict(corners=[int(v) for v in d['mouth_corners']], upper=[int(v) for v in d['mouth_upper']],
                    lower=[int(v) for v in d['mouth_lower']],
                    cavity={int(v): int(k) for v, a, k in d['mouth_cavity']},
                    cavity_src={int(v): (int(a), float(sched[k - 1][0]), float(sched[k - 1][1])) for v, a, k in d['mouth_cavity']},
                    outer={int(v): int(r) for v, r in d['mouth_outer']},
                    side={int(v): code[int(c)] for v, c in d['mouth_side']})


_CACHE = {}


def load(path=ASSET):
    if path not in _CACHE:
        _CACHE[path] = Base(path)
    return _CACHE[path]


# ----------------------------------------------------------------------------------------------------------------- build
def wrap(spec):
    """the build-time path for spec['base'] == 'anime': MakeHuman's body for the spec's body knobs (same vertex indices, so
    its macro targets and proportions still shape it), the stored head re-wrapped to the spec's head knobs.
    -> (B: the body data on the base's topology (as body.build_body_data returns, 'verts' the pre-wrap positions for the
    joints to follow; new vertices have none: NaN), V, H, centre, info)."""
    from . import anime_head as ah, body as bodylib
    base = load()
    Bm = bodylib.build_body_data(spec.get('body'), keep_head=True)
    L = Bm['head_len']
    src = base.src
    kept = src >= 0
    pre = np.full((base.N, 3), np.nan)
    pre[kept] = Bm['verts'][src[kept]]
    ring = (Bm['head_w'] > 0.03) & (Bm['head_w'] < 0.2)
    nc = Bm['verts'][ring].mean(0)
    n_r = float(np.median(np.hypot(Bm['verts'][ring, 0] - nc[0], Bm['verts'][ring, 1] - nc[1])))
    d = base.d
    q0 = (base.verts - base.centre) / base.L
    V, H, centre, info = ah.rewrap(q0, d['wrap_region'], d['shell'], d['shell_rad'], d['shell_P'], base.meta['lm_real'],
                                   d['profile'], base.meta['warps'], pre, Bm['marks'], (n_r, nc), L, spec.get('head'),
                                   ear=(d['ear_idx'], d['ear_det']), extra=d['ghost_q'],
                                   body_rel=(d['neck_idx'], d['neck_d0'], d['neck_w']))
    # the joints follow the wrap as on the makehuman base: the removed interior's ghosts count among the vertices they follow
    ghosts = (Bm['verts'][d['ghost_src']], info.pop('extra'))
    B = dict(Bm, verts=pre, faces=base.faces, face_uv=base.face_uv, uvs=base.uvs, weights=dict(base.weights),
             head_w=base.head_w, face_w=dict(base.face_w), base=base, regions=base.regions, ghosts=ghosts)
    return B, V, H, centre, info


if __name__ == '__main__':
    import sys
    if sys.argv[1:2] == ['derive']:
        derive()
    else:
        print(__doc__)
