"""charkit's code-authored base (spec['base'] = 'code'): MakeHuman's body below the neck, the head authored in code from
the design's references and stitched on at a level cut through the neck, with no MakeHuman head.

  the head   charkit.geom.headfit: the skull from head_construction (its silhouettes, analytically), the face from
             head_turnaround's measured contours, the chin and the neck onto its drawn outline; its topology
             charkit.geom.headmesh.cylinder: all quads, concentric loops round each eye and the mouth
  the join   MakeHuman's body (the spec's body knobs, its head kept for its marks and joints) cut level through the neck at
             CUT L under the eye line; the head's lowest rows eased into the body's neck section there, the two rings
             zipped with a strip of triangles
  the face   each eye's opening gets a shallow socket (two rings and a centre behind the margin, as charkit/base_anime.py's)
             and the mouth a compact cavity (five rings and a cap), in the labels charkit/eyes.py and charkit/mouth.py
             place and key, so charkit.character.assemble treats this base as the others
  H          SectionsHead: the head's surface in head space for the eyes', brows' and mouth's placement (eyes.Face), the
             face shading and the hair (the same attributes as charkit.head.Head: section, surfaces, chin, top, df...)

The same contract as charkit/base_anime.wrap: wrap(spec, body) -> (B, V, H, centre, info).
"""
import functools, json, math, os

import numpy as np

CUT = -0.52                   # L from the eye line: the neck is cut level here (under the chin, above the shoulders' flare)
NECK_BLEND = 0.1              # L above the cut over which the head's neck eases into the body's
ZIP = 'triangles'


# ---------------------------------------------------------------------------------------------------------- the surface
class SectionsHead:
    """the authored head's surface in head space (metres, origin `centre` at the eye line on the head's axis, x her
    left, y back, z up), with charkit.head.Head's interface: sections / _xy / surfaces / surface (azimuth 0 = the front,
    a true polar angle round the row's centre), section(z) -> (wf, wb, df, db, n), and the landmarks chin, top, df, db,
    eye_x, eye_z, mouth_z, nose_z."""

    def __init__(self, S, C, L, y0, mouth_z=None):
        self.S, self.C, self.L, self.y0 = S, C, float(L), float(y0)
        self.K = {}
        ok = np.isfinite(S.cy) & np.isfinite(S.r).all(1)
        self._zs, self._cy, self._r = S.zs[ok], S.cy[ok], S.r[ok]        # descending rows (L)
        j0 = int(np.argmin(np.abs(S.th)))
        jb = int(np.argmin(np.abs(np.abs(S.th) - np.pi)))
        k0 = int(np.argmin(np.abs(self._zs)))
        self.top = float(self._zs[0]) * L
        self.chin = -float(C['chin']) * L
        self.df = float(y0 - (self._cy[k0] - self._r[k0, j0])) * L
        self.db = float(self._cy[k0] + self._r[k0, jb] - y0) * L
        self.eye_x = float(C['eye_x']) * L
        self.eye_z = 0.0
        self.nose_z = float(C['nose_z']) * L
        self.mouth_z = (mouth_z if mouth_z is not None else float(C['nose_z']) - 0.11) * L
        self.nose_relief = 0.0
        self.feat = False
        self._j0 = j0

    def sections(self, z):
        """rows interpolated at heights z (metres from the eye line) -> (cy (N,), r (N, angles)) in L."""
        zl = np.clip(np.atleast_1d(np.asarray(z, float)) / self.L, self._zs[-1], self._zs[0])
        i = np.clip(np.searchsorted(-self._zs, -zl), 1, len(self._zs) - 1)
        t = ((self._zs[i - 1] - zl) / (self._zs[i - 1] - self._zs[i]))[:, None]
        cy = (1 - t[:, 0]) * self._cy[i - 1] + t[:, 0] * self._cy[i]
        r = (1 - t) * self._r[i - 1] + t * self._r[i]
        return cy, r

    def _xy(self, a, sec):
        cy, r = sec
        a = np.asarray(a, float)
        th = self.S.th
        if r.ndim == 1:
            rr = np.interp(a, th, r, period=2 * np.pi)
        else:
            a = np.broadcast_to(a, (r.shape[0],)) if a.ndim == 0 else a
            rr = np.array([np.interp(ai, th, ri, period=2 * np.pi) for ai, ri in zip(np.atleast_1d(a), r)])
        return np.sin(a) * rr * self.L, (cy - np.cos(a) * rr - self.y0) * self.L

    def surfaces(self, a, z):
        a, z = np.broadcast_arrays(np.asarray(a, float), np.asarray(z, float))
        cy, r = self.sections(z.ravel())
        x, y = self._xy(a.ravel(), (cy, r))
        return np.stack([x, y, z.ravel()], -1).reshape(a.shape + (3,))

    def surface(self, a, z):
        return self.surfaces(np.array([a]), np.array([z]))[0]

    def section(self, z):
        cy, r = self.sections(np.array([z]))
        r, cy = r[0], cy[0]
        th = self.S.th
        side = float(np.interp(np.pi / 2, th, r, period=2 * np.pi))
        back = float(np.interp(3 * np.pi / 4, th, r, period=2 * np.pi))
        return (side * self.L, back * math.sin(3 * math.pi / 4) * self.L,
                (self.y0 - (cy - r[self._j0])) * self.L,
                (cy + float(np.interp(np.pi, th, r, period=2 * np.pi)) - self.y0) * self.L, 2.0)


# ---------------------------------------------------------------------------------------------------------- the head
_HEADS = {}


def save_head(spec, path, log=print):
    """the authored head's sections and the contours' landmarks computed venv-side (they read the reference images) into
    `path` (.npz), for the build's Blender side, which loads them (spec['head_code'])."""
    S, C, rep = head_sections(dict(spec, head_code=None), log)
    np.savez_compressed(path, zs=S.zs, cy=S.cy, r=S.r, th=S.th,
                        C=json.dumps({k: float(C[k]) for k in ('chin', 'eye_x', 'nose_z', 'az3')}),
                        rep=json.dumps(rep, default=str))
    return path


def head_sections(spec, log=print):
    """the authored head's sections and the design's contours for a resolved spec (in L, the eye frame): from the file
    spec['head_code'] names when there is one (save_head: the Blender side can't read images), else computed; kept per
    set of references and style (a build asks once; a fit asks many times with the same references)."""
    from charkit.geom.headgeom import Sections
    if spec.get('head_code') and os.path.exists(spec['head_code']):
        z = np.load(spec['head_code'])
        S = Sections(z['zs'], z['cy'], z['r'])
        return S, json.loads(str(z['C'])), json.loads(str(z['rep']))
    # computed from the reference images: venv-side only (a build's Blender side loads the file cli.code_head wrote).
    # Imported at run time, not named in an import statement: the build stages' code closure (charkit.cache) follows
    # import statements, and the fitting reaches the QA's modules, which a build stage mustn't depend on
    import importlib
    refcheck = importlib.import_module('charkit.refcheck')
    headfit = importlib.import_module('charkit.geom.headfit')
    fs = spec['ref']['face_sheet']
    key = json.dumps([spec['ref'].get('manifest'), fs.get('image'), spec.get('style', 'anime'),
                      spec.get('eyes', {}).get('x', 0.168)])
    if key not in _HEADS:
        C = headfit.contours(refcheck._load(fs['image']), spec.get('eyes', {}).get('x', 0.168), fs.get('facing', -1))
        S, rep = headfit.assemble(headfit.Face(C), headfit.skull_analytic(spec, log=log))
        _HEADS[key] = (S, C, rep)
    return _HEADS[key]


def _ring_polar(P, centre, th):
    """points round a centre (x, y) as a polar radius at the angles th (0 the front, -y): the outermost per bin,
    interpolated round."""
    a = np.arctan2(P[:, 0] - centre[0], -(P[:, 1] - centre[1]))
    r = np.hypot(P[:, 0] - centre[0], P[:, 1] - centre[1])
    o = np.argsort(a)
    a, r = a[o], r[o]
    return np.interp(th, np.r_[a[-1] - 2 * np.pi, a, a[0] + 2 * np.pi], np.r_[r[-1], r, r[0]])


def blend_neck(S, cut, ring_cy, ring_r, width=NECK_BLEND):
    """the head's sections with their lowest rows eased into the body's neck section (its centre ring_cy, radii ring_r
    at S.th, in the eye frame's L) from `width` above the cut down to it; rows under the cut dropped."""
    from charkit.geom.headgeom import Sections, _smoothstep
    cy, r = S.cy.copy(), S.r.copy()
    w = _smoothstep((cut + width - S.zs) / width)[:, None]
    ok = np.isfinite(cy)
    r[ok] = (1 - w[ok]) * r[ok] + w[ok] * ring_r[None, :]
    cy[ok] = (1 - w[ok, 0]) * cy[ok] + w[ok, 0] * ring_cy
    under = S.zs < cut - 2 * abs(S.zs[1] - S.zs[0])                  # one row past the cut kept: the ring interpolates
    cy[under] = np.nan; r[under] = np.nan
    return Sections(S.zs, cy, r)


def eye_labels(V, rings, side, socket_start):
    """an eye's labels from its loops (outer to inner; the innermost the lid's margin) and its socket's vertices
    (socket_start: ring 1's first index; ring 2 next; then the centre) -> the dict charkit/eyes.py places, with the
    loops themselves ('loops': the block's rim first, the margin last, index-aligned along spokes) for its lid keys."""
    margin = list(rings[-1])
    P = V[margin]
    n = len(margin)
    inner = int(np.argmin(P[:, 0] * side))                 # the inner corner: nearest the midline
    outer = int(np.argmax(P[:, 0] * side))
    # run from the inner corner over the top
    step = 1 if P[(inner + 1) % n, 2] >= P[(inner - 1) % n, 2] else -1
    order = [(inner + step * i) % n for i in range(n)]
    loop = [margin[i] for i in order]
    k_out = order.index(outer)
    upper = loop[:k_out + 1]
    lower = [loop[0]] + [loop[i] for i in range(n - 1, k_out - 1, -1)]
    from charkit.base_anime import SOCKET
    rings_s = [list(range(socket_start, socket_start + n)), list(range(socket_start + n, socket_start + 2 * n))]
    centre_v = socket_start + 2 * n
    pocket, sock = {}, {}
    for k, ring in enumerate(rings_s, 1):
        for i, v in enumerate(ring):
            pocket[v] = k
            sock[v] = (margin[i], SOCKET[k - 1][0], SOCKET[k - 1][1])
    pocket[centre_v] = 3
    sock[centre_v] = (margin[0], SOCKET[2][0], SOCKET[2][1])
    outer_rings = {}
    for k, ring in enumerate(rings[-2::-1], 1):
        for v in ring:
            outer_rings[v] = k
    return dict(margin=loop, upper=upper, lower=lower, pocket=pocket, outer=outer_rings, socket=sock,
                loops=[list(r) for r in rings])


def mouth_labels(V, rings, cavity_start, extra_outer=None):
    """the mouth's labels from its loops (outer to inner; the innermost the lips' line) and its cavity's vertices -> the
    dict charkit/mouth.py places."""
    from charkit.base_anime import CAVITY
    lips = list(rings[-1])
    P = V[lips]
    n = len(lips)
    left, right = int(np.argmin(P[:, 0])), int(np.argmax(P[:, 0]))       # the corners, low x first (as mouth.detect)
    # the upper line: from the low-x corner over the top to the high-x corner; the lower: under
    step = 1 if P[(left + 1) % n, 2] >= P[(left - 1) % n, 2] else -1
    order = [(left + step * i) % n for i in range(n)]
    loop = [lips[i] for i in order]
    kr = order.index(right)
    upper = loop[:kr + 1]
    lower = [loop[0]] + [loop[i] for i in range(n - 1, kr - 1, -1)]
    cavity, src = {}, {}
    for k in range(1, len(CAVITY)):
        for i in range(n):
            v = cavity_start + (k - 1) * n + i
            cavity[v] = k
            src[v] = (lips[i], CAVITY[k - 1][0], CAVITY[k - 1][1])
    cap = cavity_start + (len(CAVITY) - 1) * n
    cavity[cap] = len(CAVITY)
    src[cap] = (lips[0], CAVITY[-1][0], CAVITY[-1][1])
    outer = {}
    for k, ring in enumerate(rings[-2::-1], 1):
        for v in ring:
            outer[v] = k
    for v, k in (extra_outer or {}).items():
        outer.setdefault(v, k)
    mz = float(np.mean(V[lips, 2]))
    side = {}
    for v in list(outer) + lips:
        side[v] = 'c' if v in (lips[left], lips[right]) else ('u' if V[v, 2] >= mz else 'l')
    return dict(corners=[lips[left], lips[right]], upper=upper, lower=lower, cavity=cavity, cavity_src=src,
                outer=outer, side=side)


class CodeBase:
    """what charkit/eyes.py and charkit/mouth.py read of a base: eye(side) and mouth() labels."""

    def __init__(self, eyes, mouth):
        self._eyes, self._mouth = eyes, mouth

    def eye(self, side):
        return self._eyes[1 if side > 0 else -1]

    def mouth(self):
        return self._mouth


def _grow_rings(F, start, rings, exclude, n):
    """vertices by their graph distance (1..rings) from a set, not crossing `exclude` -> {vertex: ring}."""
    from charkit.geom.headgeom import _neighbours
    nb, off = _neighbours(F, n)
    out, front = {}, set(start)
    seen = set(start) | set(exclude)
    for k in range(1, rings + 1):
        nxt = set()
        for v in front:
            for w in nb[off[v]:off[v + 1]]:
                if w not in seen:
                    seen.add(w); nxt.add(int(w)); out[int(w)] = k
        front = nxt
    return out


LIMIT_ITERS = 10                 # rounds of fitting the cage to its own subdivision's limit surface


def fit_limit(V, faces, movable, sharp=(), iters=LIMIT_ITERS):
    """the cage moved so its Catmull-Clark limit surface (level 1, the build's viewport modifier, which the QA measures)
    passes through where the cage's vertices were placed: subdivision pulls a surface inside its cage, most on narrow
    convex features (the nose, the chin), so each round moves every movable vertex by the gap between its target and its
    limit position -> (V, the remaining gap per round, L)."""
    from charkit import subdiv
    T = np.asarray(V, float)
    P = T.copy()
    gaps = []
    for _ in range(iters):
        V1, Q, par = subdiv.catmull_clark(P, faces, sharp)
        d = T - V1[:len(P)]
        gaps.append(round(float(np.abs(d[movable]).max()), 5))
        P[movable] += d[movable]
    return P, gaps


def eye_outline(spec, n=32):
    """her left eye's opening as the spec's eye knobs draw it (charkit.eyes.outline_polygon), in L round the eye line at
    the eye's x (x outward, z up, the eye's z knob added): the outline the cage's lid loop is authored on."""
    from charkit import eyes as eyelib
    EK = eyelib._knobs(spec.get('eyes'))
    P = eyelib.outline_polygon(EK, 1.0, n=n)
    return np.stack([P[:, 0], P[:, 1] + EK['z']], 1)


def head_mesh(S, C, cut, eye_outline=None):
    """the authored head's mesh on its sections (L, eye frame): the cage with the eyes and the mouth open, each eye's
    socket and the mouth's cavity added (their positions a first guess: charkit/eyes.py and charkit/mouth.py place them),
    the labels -> dict(V, faces (lists), eyes {side: labels}, mouth labels, neck (the bottom ring, ordered round),
    groups per face). eye_outline: the lid loop's outline (eye_outline()), else the cage's default almond."""
    from charkit.geom import headgeom
    Cg, ctr = headgeom.cylinder_cage(S, C, z_bottom=cut, caps=False, eye_outline=eye_outline)
    V = list(Cg.V)
    faces = [list(f) for f in Cg.F]
    groups = [Cg.groups[g] for g in Cg.group]

    def add(p):
        V.append(np.asarray(p, float))
        return len(V) - 1
    eyes = {}
    for name, side in (('eye_L', 1), ('eye_R', -1)):
        rings = Cg.loops[name]
        margin = rings[-1]
        P = np.array([V[i] for i in margin])
        c = P.mean(0)
        start = len(V)
        for k, (pull, depth) in enumerate(((0.3, 0.02), (0.7, 0.03)), 1):     # a first guess: eyes.place moves them
            for p in P:
                add(p + (c - p) * pull + np.array([0.0, depth, 0.0]))
        centre = add(c + np.array([0.0, 0.035, 0.0]))
        n = len(margin)
        r1, r2 = list(range(start, start + n)), list(range(start + n, start + 2 * n))
        for a, b in ((margin, r1), (r1, r2)):
            for i in range(n):
                j = (i + 1) % n
                faces.append([a[i], a[j], b[j], b[i]]); groups.append(name + '_socket')
        for i in range(n):
            faces.append([r2[i], r2[(i + 1) % n], centre]); groups.append(name + '_socket')
        eyes[side] = eye_labels(np.array(V), rings, side, start)
    rings = Cg.loops['mouth']
    lips = rings[-1]
    P = np.array([V[i] for i in lips])
    c = P.mean(0)
    start = len(V)
    from charkit.base_anime import CAVITY
    prev = list(lips)
    for k, (dsh, pull) in enumerate(CAVITY[:-1], 1):
        ring = [add(p + (c - p) * pull + np.array([0.0, 0.06 * dsh, 0.0])) for p in P]
        for i in range(len(ring)):
            j = (i + 1) % len(ring)
            faces.append([prev[i], prev[j], ring[j], ring[i]]); groups.append('mouth_cavity')
        prev = ring
    cap = add(c + np.array([0.0, 0.06, 0.0]))
    for i in range(len(prev)):
        faces.append([prev[i], prev[(i + 1) % len(prev)], cap]); groups.append('mouth_cavity')
    Va = np.array(V)
    quads = np.array([f for f in faces if len(f) == 4])
    inside = set(range(start, len(Va))) | {v for r in rings[1:] for v in r}
    extra = _grow_rings(quads, set(rings[0]), 9 - (len(rings) - 1), inside, len(Va))
    mouth = mouth_labels(Va, rings, start, {v: k + len(rings) - 1 for v, k in extra.items()})
    # the eyes' outer rings beyond the cage's own loops, as far as charkit/eyes.py spreads (RINGS)
    for side, E in eyes.items():
        name = 'eye_L' if side > 0 else 'eye_R'
        inside = set(E['pocket']) | {v for r in Cg.loops[name][1:] for v in r}
        more = _grow_rings(quads, set(Cg.loops[name][0]), 6 - (len(Cg.loops[name]) - 1), inside, len(Va))
        for v, k in more.items():
            E['outer'].setdefault(v, k + len(Cg.loops[name]) - 1)
    # the cage fitted to its limit surface: the face's surface stays where it was placed after subdivision; the eyes'
    # sockets, the mouth's cavity (placed later by eyes.py and mouth.py) and the neck's rim (zipped to the body) held
    held = set(range(Cg.V.shape[0], len(Va))) | set(Cg.loops['neck'][0])
    for name in ('eye_L', 'eye_R'):             # the eyes' loops whole: fitted next to the creased margin and the socket
        held |= {v for r in Cg.loops[name] for v in r}          # (placed later), they folded 13 faces at rest
    movable = np.array([i not in held for i in range(len(Va))])
    sharp = [(a, b) for E in eyes.values() for a, b in zip(E['margin'], E['margin'][1:] + E['margin'][:1])]
    Va, gaps = fit_limit(Va, faces, movable, sharp)
    return dict(V=Va, faces=faces, groups=groups, eyes=eyes, mouth=mouth, neck=list(Cg.loops['neck'][0]), cage=Cg,
                limit_gaps=gaps)


# ------------------------------------------------------------------------------------------------------------ the join
def _boundary_loops(faces, n):
    from collections import defaultdict
    cnt = defaultdict(int)
    for f in faces:
        for a, b in zip(f, list(f[1:]) + [f[0]]):
            cnt[(min(a, b), max(a, b))] += 1
    adj = defaultdict(list)
    for (a, b), c in cnt.items():
        if c == 1:
            adj[a].append(b); adj[b].append(a)
    loops, seen = [], set()
    for s in adj:
        if s in seen:
            continue
        loop, prev = [s], None
        seen.add(s)
        while True:
            nxt = [x for x in adj[loop[-1]] if x != prev and (x not in seen or x == s)]
            if not nxt or nxt[0] == s:
                break
            prev = loop[-1]; loop.append(nxt[0]); seen.add(nxt[0])
        loops.append(loop)
    return loops


def zip_rings(A, B, PA, PB, centre):
    """triangles joining two closed rings round a vertical axis (A the head's, B the body's, each in its own loop order;
    their points PA, PB): each ring turned to run the same way round and started at its vertex nearest the front, then
    both walked by their arc length's share, each step advancing the ring whose next vertex comes first. By arc length,
    not angle: a cut's rim can double back in angle where it wiggles, and ordering it by angle would skip its own edges.
    -> [(i, j, k)] (global indices), wound outward."""
    def prepare(R, P):
        t = np.arctan2(P[:, 0] - centre[0], -(P[:, 1] - centre[1]))
        if np.sum(np.diff(np.unwrap(np.r_[t, t[0]]))) < 0:            # counter-clockwise seen from above, as the head's
            R, P, t = R[::-1], P[::-1], t[::-1]
        s0 = int(np.argmin(np.abs(t)))                               # start at the front
        R, P = R[s0:] + R[:s0], np.roll(P, -s0, 0)
        seg = np.linalg.norm(np.diff(np.vstack([P, P[:1]]), axis=0), axis=1)
        return R, P, np.r_[0.0, np.cumsum(seg)] / seg.sum()
    A, PA, sa = prepare(list(A), np.asarray(PA))
    B, PB, sb = prepare(list(B), np.asarray(PB))
    na, nb_ = len(A), len(B)
    i = j = 0
    tris = []
    while i < na or j < nb_:
        if j >= nb_ or (i < na and sa[i + 1] <= sb[j + 1]):
            tri = (A[i % na], A[(i + 1) % na], B[j % nb_]); P3 = np.array([PA[i % na], PA[(i + 1) % na], PB[j % nb_]]); i += 1
        else:
            tri = (A[i % na], B[(j + 1) % nb_], B[j % nb_]); P3 = np.array([PA[i % na], PB[(j + 1) % nb_], PB[j % nb_]]); j += 1
        n = np.cross(P3[1] - P3[0], P3[2] - P3[0])
        out = P3.mean(0)[:2] - np.asarray(centre)[:2]
        tris.append(tri if n[0] * out[0] + n[1] * out[1] >= 0 else tri[::-1])
    return tris


def wrap(spec, body=None, log=print):
    """the build-time path for spec['base'] == 'code' (see the module) -> (B, V, H, centre, info) as base_anime.wrap: B
    the body data on this base's topology ('verts' the body's positions, NaN for the head's new vertices; 'ghosts' the
    MakeHuman head's points and where they land, for the joints to follow), V the positions, H the head's surface."""
    from charkit import body as bodylib
    from charkit.geom.headgeom import Sections
    Bm = body or bodylib.build_body_data(spec.get('body'), keep_head=True)
    L = float(Bm['head_len'])
    Hm = float(Bm['params']['height_m'])
    S, C, rep = head_sections(spec, log)
    # world = O + L (x, y, z) in the head's eye frame; its chin where the body's scaling put MakeHuman's
    Oz = Hm - L - C['chin'] * L
    z_cut = Oz + CUT * L
    Vb, Fb = Bm['verts'], Bm['faces']
    # the cut: above it, within the neck's column (the shoulders' tops can reach it beside the neck, and stay)
    hv = np.asarray(Bm['head_w']) > 0.5
    axis = Vb[hv, :2].mean(0) if hv.any() else np.zeros(2)
    column = np.hypot(Vb[:, 0] - axis[0], Vb[:, 1] - axis[1]) < 0.45 * L
    above = (Vb[:, 2] > z_cut) & (column | (np.asarray(Bm['head_w']) > 0.05))    # the head's own, and the neck's
    cand = [i for i, f in enumerate(Fb) if any(above[v] for v in f)]
    # of the faces over the cut, only those joined to the head go: an isolated one (a shoulder's top grazing the cut)
    # would leave a hole
    from collections import defaultdict
    by_edge = defaultdict(list)
    for i in cand:
        f = Fb[i]
        for a, b in zip(f, list(f[1:]) + [f[0]]):
            by_edge[(min(a, b), max(a, b))].append(i)
    top_face = max(cand, key=lambda i: max(Vb[v, 2] for v in Fb[i]))
    gone, stack = {top_face}, [top_face]
    while stack:
        i = stack.pop()
        f = Fb[i]
        for a, b in zip(f, list(f[1:]) + [f[0]]):
            for j in by_edge[(min(a, b), max(a, b))]:
                if j not in gone:
                    gone.add(j); stack.append(j)
    keep = [i for i in range(len(Fb)) if i not in gone]
    Fk = [Fb[i] for i in keep]
    loops = _boundary_loops(Fk, len(Vb))
    near = [lp for lp in loops if abs(np.mean(Vb[lp, 2]) - z_cut) < 0.1 * L]
    ring_b = max(near, key=len) if near else max(loops, key=lambda lp: np.mean(Vb[lp, 2]))
    # a cut that pinches (the removed region touching the kept at one vertex) leaves small notches beside the neck's
    # ring: the removed faces lying on a notch go back, and the ring is found again
    notches = [set(lp) for lp in near if lp is not ring_b and len(lp) < 0.25 * len(ring_b)]
    if notches:
        back = [i for i in sorted(gone) if any(all(v in nt for v in Fb[i]) for nt in notches)]
        keep = sorted(set(keep) | set(back))
        Fk = [Fb[i] for i in keep]
        loops = _boundary_loops(Fk, len(Vb))
        near = [lp for lp in loops if abs(np.mean(Vb[lp, 2]) - z_cut) < 0.1 * L]
        ring_b = max(near, key=len)
    Vb = Vb.copy()
    Vb[ring_b, 2] = z_cut                                                   # the body's rim flattened onto the cut
    nc = Vb[ring_b].mean(0)
    # the head's neck centre at the cut meets the body's; the head's lowest rows ease into the body's neck section
    ok = np.isfinite(S.cy)
    cy_cut = float(np.interp(-CUT, -S.zs[ok], S.cy[ok]))
    Oy = nc[1] - cy_cut * L
    Ox = nc[0]
    ring_r = _ring_polar((Vb[ring_b, :2] - np.array([Ox, Oy])) / L, (0.0, cy_cut), S.th)
    Sb = blend_neck(S, CUT, cy_cut, ring_r)
    Hmesh = head_mesh(Sb, C, CUT, eye_outline(spec))
    Vh = np.array([Ox, Oy, Oz]) + L * Hmesh['V']
    # assemble: the kept body, the head, the zip
    used = sorted({v for f in Fk for v in f})
    remap = {o: n for n, o in enumerate(used)}
    nbv = len(used)
    V = np.vstack([Vb[used], Vh])
    faces = [tuple(remap[v] for v in f) for f in Fk]
    face_uv = [Bm['face_uv'][i] for i in keep]
    hf = [tuple(v + nbv for v in f) for f in Hmesh['faces']]
    zipped = zip_rings([v + nbv for v in Hmesh['neck']], [remap[v] for v in ring_b], Vh[Hmesh['neck']], Vb[ring_b], nc[:2])
    faces += hf + [tuple(t) for t in zipped]
    # UVs: the head's cylinder chart into MakeHuman's head island (the removed faces' UV box)
    uvs = np.asarray(Bm['uvs'])
    gone = [i for i in range(len(Fb)) if i not in set(keep)]
    box_src = np.array([uvs[u] for i in gone for u in Bm['face_uv'][i]]) if gone else uvs
    u0, v0 = box_src.min(0); u1, v1 = box_src.max(0)
    Pl = Hmesh['V']
    ctr_y = float(np.nanmean(Sb.cy))
    th = np.arctan2(Pl[:, 0], -(Pl[:, 1] - ctr_y))
    zn = (Pl[:, 2] - Pl[:, 2].min()) / max(np.ptp(Pl[:, 2]), 1e-6)
    new_uv = []
    for f in Hmesh['faces']:
        t = th[f].copy()
        t = t[0] + (t - t[0] + np.pi) % (2 * np.pi) - np.pi              # across the back seam: unwrapped
        new_uv.append([(u0 + (u1 - u0) * (ti + np.pi) / (2 * np.pi), v0 + (v1 - v0) * zn[vi]) for ti, vi in zip(t, f)])
    new_uv += [None] * len(zipped)
    base_uv = len(uvs)
    extra_uv = []
    fuv = []
    for q in new_uv:
        if q is None:
            fuv.append(None); continue
        fuv.append(tuple(range(base_uv + len(extra_uv), base_uv + len(extra_uv) + len(q))))
        extra_uv.extend(q)
    zip_uv_idx = base_uv + len(extra_uv)
    extra_uv.append(((u0 + u1) / 2, v0))
    fuv = [q if q is not None else (zip_uv_idx,) * 3 for q in fuv]
    uvs_all = np.vstack([uvs, np.array(extra_uv)])
    face_uv = face_uv + fuv
    # weights: the body's own; the head's on 'head', easing to 'neck' down the neck
    n_all = len(V)
    from charkit.geom.headgeom import _smoothstep
    zl = Hmesh['V'][:, 2]
    w_head = _smoothstep((zl - CUT) / (C['chin'] - 0.02 - CUT))
    weights = {}
    for bone, w in Bm['weights'].items():
        a = np.zeros(n_all); a[:nbv] = np.asarray(w)[used]
        weights[bone] = a
    weights.setdefault('head', np.zeros(n_all)); weights.setdefault('neck', np.zeros(n_all))
    for bone in list(weights):
        weights[bone][nbv:] = 0.0
    weights['head'][nbv:] = w_head
    weights['neck'][nbv:] = 1 - w_head
    head_w = np.zeros(n_all); head_w[:nbv] = np.asarray(Bm['head_w'])[used]; head_w[nbv:] = np.maximum(w_head, 0.51)
    # the jaw's region: under the mouth's line, in front of the jaw's angle, down to the chin's underside
    mz = float(np.mean(Hmesh['V'][Hmesh['mouth']['upper'] + Hmesh['mouth']['lower'], 2]))
    thl = np.arctan2(Hmesh['V'][:, 0], -(Hmesh['V'][:, 1] - ctr_y))
    jaw = _smoothstep((mz - zl) / 0.03) * _smoothstep((np.radians(100) - np.abs(thl)) / np.radians(40)) * \
        _smoothstep((zl - (C['chin'] - 0.1)) / 0.05)
    face_w = {b_: np.zeros(n_all) for b_ in ('jaw',)}
    face_w['jaw'][nbv:] = jaw
    # labels on the combined mesh
    off = lambda d: {int(k) + nbv: v for k, v in d.items()}
    eyes = {}
    for side, E in Hmesh['eyes'].items():
        eyes[side] = dict(margin=[v + nbv for v in E['margin']], upper=[v + nbv for v in E['upper']],
                          lower=[v + nbv for v in E['lower']], pocket=off(E['pocket']), outer=off(E['outer']),
                          socket={int(k) + nbv: (a + nbv, p, d) for k, (a, p, d) in E['socket'].items()},
                          loops=[[v + nbv for v in r] for r in E['loops']])
    M_ = Hmesh['mouth']
    mouth = dict(corners=[v + nbv for v in M_['corners']], upper=[v + nbv for v in M_['upper']],
                 lower=[v + nbv for v in M_['lower']], cavity=off(M_['cavity']),
                 cavity_src={int(k) + nbv: (a + nbv, p, d) for k, (a, p, d) in M_['cavity_src'].items()},
                 outer=off(M_['outer']), side=off(M_['side']))
    base = CodeBase(eyes, mouth)
    # the head's frame for H: origin at the eye line on the head's axis (the section's centre there)
    k0 = int(np.argmin(np.abs(Sb.zs)))
    y0 = float(Sb.cy[k0])
    centre = np.array([Ox, Oy + y0 * L, Oz])
    H = SectionsHead(Sb, C, L, y0, mouth_z=mz)
    # landmarks and joints: MakeHuman's head joints carried by the fit of its landmarks onto ours
    lm_ours = {'eye_l': (C['eye_x'], 0.0, 0.0), 'eye_r': (-C['eye_x'], 0.0, 0.0), 'chin': (0.0, 0.0, C['chin']),
               'top': (0.0, float(np.nanmean(Sb.cy)), float(Sb.zs[np.isfinite(Sb.cy)][0])),
               'mouth': (0.0, 0.0, mz), 'nose': (0.0, 0.0, C['nose_z'])}
    marks = {k: np.array([Ox, Oy, Oz]) + L * np.array(v) for k, v in lm_ours.items()}
    for k in ('chin', 'mouth', 'nose'):
        p = H.surface(0.0, marks[k][2] - centre[2]) + centre
        marks[k] = np.array([Ox, p[1], marks[k][2]])
    src = np.array([Bm['marks'][k] for k in lm_ours])
    dst = np.array([marks[k] for k in lm_ours])
    Aff = np.linalg.lstsq(np.c_[src, np.ones(len(src))], dst, rcond=None)[0]
    hv = np.nonzero(np.asarray(Bm['head_w']) > 0.5)[0]
    pick = hv[:: max(1, len(hv) // 800)]
    ghosts = (Bm['verts'][pick], np.c_[Bm['verts'][pick], np.ones(len(pick))] @ Aff)
    pre = np.full((n_all, 3), np.nan)
    pre[:nbv] = Bm['verts'][used]
    TV = Hmesh['V'] * L + np.array([Ox, Oy, Oz]) - centre
    TT = np.array([t for f in Hmesh['faces'] for t in ([[f[0], f[1], f[2]], [f[0], f[2], f[3]]] if len(f) == 4 else [list(f)])])
    region = np.zeros(n_all, bool); region[nbv:] = True
    info = dict(region=region, target=(TV, TT), profile=[], eye_world=[marks['eye_l'], marks['eye_r']], c_real=None,
                c_anime=centre, pinned=region.copy(), extra=None, code=dict(cut=CUT, head=rep, groups=Hmesh['groups']))
    B = dict(Bm, verts=pre, faces=faces, face_uv=face_uv, uvs=uvs_all, weights=weights, head_w=head_w, face_w=face_w,
             base=base, regions=None, ghosts=ghosts, marks=dict(Bm['marks'], **marks))
    return B, V, H, centre, info
