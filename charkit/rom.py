"""The range-of-motion suite (tool/rom, 2026-10-01; docs/CHARKIT_HANDOFF.md "Known gaps before motion testing" item 2):
the shipped rig posed through the pose library (charkit/poses/rom.json, charkit.pose) and measured per pose, numbers
before pictures. The rig is the build's export (OUT/NAME.look.glb): its skeleton (the VRM humanoid's nodes and inverse
bind matrices) and every mesh's four skin weights, skinned linearly as a runtime skins them.

    python -m charkit rom BUILD [--out DIR] [--poses a,b] [--boards] [--art] [--closeups [--only-closeups]] [--json]
        -> DIR/rom.json (every pose's measures), DIR/rom.md (the table), with --boards DIR/boards/POSE_AZ.png (the toon
           renderer's picture of each pose, front / three-quarter / profile / back, one scale), with --art the toon
           artefact detectors on the posed bundles against the rest (art_posed), with --closeups DIR/closeups/ (the
           stressed joints close up, CLOSEUPS: the elbow and knee under linear blend and dual quaternion skinning, the
           shoulder at the raises with the garments off and on, the hip in the squat, the neck turned, the hands)

Measured per pose, report-only (there is no drawing of these poses: physical limits are the thresholds, LIMITS):
  sections    joint volume: the skin's cross-section at each moved joint (the elbows, knees, shoulders, wrists,
              hips, the fingers' knuckles) and either side of it, posed over rest: the smallest ratio (1 kept; under
              ~0.7 the joint collapses, LBS's candy-wrapper under a twist)
  inside      interpenetration of the skin by region pairs (arm-torso, leg-torso, finger-finger, arm-head): a region's
              vertices inside another region's posed closed surface (its boundary loops capped), new against the rest
              pose, and the deepest (L)
  garments    each garment's surface vertices inside the posed skin, new against rest (sleeve-body, skirt-legs, ...):
              share and depth (L); and its strain (|edge / rest edge - 1|, p95)
  crossings   thin surfaces passing through each other, new against rest: the hair through the shoulders' garments
              and the skin (hair-shoulders), the hands through the skirt and the flaps (hand-skirt): the share of the
              first's edges that cross the second's surface
  skin        the skin's own strain p95, its collapsed (under 20% of its rest area) and folded (normal turned over
              against its dominant bone's) area shares
and once per rig (weight sanity): weights summing to 1, vertices with none, influences on a bone far from the vertex
(stray), on the other side's bones, and sharp weight steps across short edges; each garment's weights against the skin
under it.
"""
import json, os, sys, time

import numpy as np

from . import pose as P

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
C3 = np.array([[1.0, 0, 0], [0, 0, 1.0], [0, -1.0, 0]])       # Blender -> glTF (charkit.render.model.C3)

TORSO = ('hips', 'spine', 'chest', 'upperChest', 'leftShoulder', 'rightShoulder')
HEAD = ('neck', 'head')


def _side_bones(s, names):
    return tuple(s + n for n in names)


ARM = ('UpperArm', 'LowerArm', 'Hand', 'ThumbMetacarpal', 'ThumbProximal', 'ThumbDistal') + tuple(
    f + k for f in P.FINGERS for k in ('Proximal', 'Intermediate', 'Distal'))
LEG = ('UpperLeg', 'LowerLeg', 'Foot', 'Toes')


# ---------------------------------------------------------------------------------------------------------- the rig
class Obj:
    """one exported object welded into a mesh (Blender's frame): V (n, 3) its surface (the outline's inward move
    undone), F (m, 3) triangles, J (n, 4) bone indices into Rig.bones, W (n, 4) weights; prims: [(Model prim index,
    welded index per prim vertex)]."""

    def __init__(self, name, kind, V, F, J, W, prims):
        self.name, self.kind, self.V, self.F, self.J, self.W, self.prims = name, kind, V, F, J, W, prims

    def edges(self):
        if not hasattr(self, '_E'):
            E = np.sort(np.concatenate([self.F[:, [0, 1]], self.F[:, [1, 2]], self.F[:, [2, 0]]]), 1)
            self._E = np.unique(E, axis=0)
        return self._E

    def dominant(self):
        """each vertex's bone of largest weight (an index into Rig.bones)."""
        return self.J[np.arange(len(self.J)), self.W.argmax(1)]


class Rig:
    """a build's shipped rig: the export's skeleton (Skeleton on the bones' heads from the inverse bind matrices, tails
    from the bundle's landmarks when given) and its skinned meshes welded per object."""

    def __init__(self, export, landmarks=None, kinds=None, skip=('nose', 'mouth_line')):
        from .render import model
        self.path = export
        self.M = M = model.load(export)
        js = M.js
        sk = js['skins'][0]
        from .render.model import Accessors, read_glb
        _, bin_ = read_glb(export)
        A = Accessors(js, bin_)
        self.raw_bones = [js['nodes'][j].get('name') for j in sk['joints']]
        # a bone outside the humanoid (a helper) moves and counts as its nearest humanoid ancestor
        from .mh import VRM_PARENT
        par = {c: i for i, nd in enumerate(js['nodes']) for c in nd.get('children', ())}
        hum = []
        for j in sk['joints']:
            k = j
            while k is not None and js['nodes'][k].get('name') not in VRM_PARENT:
                k = par.get(k)
            hum.append(js['nodes'][k].get('name') if k is not None else js['nodes'][j].get('name'))
        self.bones = hum
        ibm = A(sk['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1)      # (glTF: column-major)
        rest = np.linalg.inv(ibm)
        heads = {b: C3.T @ rest[i, :3, 3] for i, b in enumerate(self.raw_bones) if b == self.bones[i]}
        tails = None
        if landmarks:
            from .mh import VRM_JOINTS
            tails = {b: np.asarray(landmarks[t], float) for b, (h, t) in VRM_JOINTS.items()
                     if t in landmarks and b in heads}
        self.sk = P.Skeleton(heads, tails)
        # the prims' skin attributes, in charkit.render.model.load's order (mode 4 primitives)
        attrs = []
        for mesh in js['meshes']:
            for pr in mesh['primitives']:
                if pr.get('mode', 4) != 4:
                    continue
                at = pr['attributes']
                attrs.append((A(at['JOINTS_0']).astype(np.int64) if 'JOINTS_0' in at else None,
                              A(at['WEIGHTS_0']).astype(np.float64) if 'WEIGHTS_0' in at else None))
        self.attrs = attrs
        groups, bare = {}, {}
        for i, p in enumerate(M.prims):
            if attrs[i][0] is None or p.object in skip:
                continue
            if p.variant == 'bare':                     # (the skin whole, its garment mask off: what's measured)
                bare.setdefault(p.object, []).append(i)
            elif not p.variant:
                groups.setdefault(p.object, []).append(i)
        groups.update(bare)
        self.objs = {}
        for name, idx in groups.items():
            kind = (kinds or {}).get(name) or _kind(name)
            self.objs[name] = _weld(name, kind, M, idx, attrs)

    def bone_names(self):
        """the humanoid bones the weights name (helpers merged into their ancestors), in the skin's joint order."""
        return list(dict.fromkeys(self.bones))

    # ---- posing
    def matrices(self, D):
        """{bone: 4x4} -> (R (nb, 3, 3), t (nb, 3)) over self.bones (bones the pose leaves out: identity)."""
        R = np.repeat(np.eye(3)[None], len(self.bones), 0)
        t = np.zeros((len(self.bones), 3))
        for i, b in enumerate(self.bones):
            if b in D:
                R[i], t[i] = D[b][:3, :3], D[b][:3, 3]
        return R, t

    def skin(self, o, D, V=None):
        """object o's vertices (or V, same rows) skinned by D -> (n, 3): linear blend skinning, as a runtime skins
        the export; with self.method 'dqs' dual quaternion skinning (Kavan et al. 2007: the bones' rigid motions blended
        as dual quaternions, no LBS collapse at a bend or twist) - the calibration's volume-keeping reference."""
        R, t = self.matrices(D) if isinstance(D, dict) else D
        V = o.V if V is None else V
        if getattr(self, 'method', 'lbs') == 'dqs':
            return dqs(V, o.J, o.W, R, t)          # (and 'shell': LBS here, the garments carried in posed())
        X = np.zeros_like(V)
        for k in range(o.J.shape[1]):
            w = o.W[:, k]
            nz = w > 0
            if not nz.any():
                continue
            j = o.J[nz, k]
            X[nz] += w[nz, None] * (np.einsum('nij,nj->ni', R[j], V[nz]) + t[j])
        tot = o.W.sum(1)
        X[tot <= 0] = V[tot <= 0]
        X[tot > 0] /= tot[tot > 0, None]
        return X

    def posed(self, D, names=None):
        """{object: posed V} for every object (or names). With self.method 'shell' the garments ride the posed skin
        as shells (shell()) instead of their own weights."""
        Rt = self.matrices(D)
        out = {n: self.skin(o, Rt) for n, o in self.objs.items() if names is None or n in names}
        if getattr(self, 'method', 'lbs') == 'shell':
            sk = next(n for n, o in self.objs.items() if o.kind == 'skin')
            Xs = out.get(sk)
            if Xs is None:
                Xs = self.skin(self.objs[sk], Rt)
            for n, o in self.objs.items():
                if o.kind == 'garment' and n in out:
                    out[n] = self.shell(o, sk, Xs)
        return out

    def shell(self, o, sk, Xs):
        """garment o carried by the posed skin Xs as a shell: each vertex keeps its offset from its nearest skin point
        in that skin triangle's own frame (a garment that follows the body exactly, never through it while the skin
        itself doesn't fold): the garment checks' reference deformation."""
        if not hasattr(self, '_shell'):
            self._shell = {}
        so = self.objs[sk]
        if o.name not in self._shell:
            from .geom.bvh import BVH
            if not hasattr(self, '_skin_bvh'):
                self._skin_bvh = BVH((so.V, so.F))
            _, f, q = self._skin_bvh.nearest(o.V)
            T = so.F[f]
            bc = _bary(q, so.V[T[:, 0]], so.V[T[:, 1]], so.V[T[:, 2]])
            E = _tri_frames(so.V, T)
            d = o.V - q
            self._shell[o.name] = (T, bc, np.einsum('nij,nj->ni', E, d))
        T, bc, loc = self._shell[o.name]
        q1 = sum(bc[:, i:i + 1] * Xs[T[:, i]] for i in range(3))
        E1 = _tri_frames(Xs, T)
        return q1 + np.einsum('nji,nj->ni', E1, loc)

    def solve(self, preset, f=1.0):
        return P.solve(self.sk, preset, f)

    def model_posed(self, D):
        """the export's Model with every primitive skinned by D (positions, normals, hull normals; the baked cast
        shadows dropped: they belong to the rest pose) -> a new Model (for the toon renderer)."""
        import copy
        R, t = self.matrices(D)
        Rg = np.einsum('ij,njk,lk->nil', C3, R, C3)                  # (the glTF frame)
        tg = t @ C3.T
        M2 = copy.copy(self.M)
        prims = []
        for i, p in enumerate(self.M.prims):
            q = copy.copy(p)
            J, W = self.attrs[i]
            if J is not None:
                tot = W.sum(1, keepdims=True)
                Wn = W / np.maximum(tot, 1e-12)
                L = np.einsum('nk,nkij->nij', Wn, Rg[J])
                T = np.einsum('nk,nkj->nj', Wn, tg[J])
                q.position = (np.einsum('nij,nj->ni', L, p.position) + T).astype(np.float32)
                q.normal = _rows_unit(np.einsum('nij,nj->ni', L, p.normal)).astype(np.float32)
                if p.hull_normal is not None:
                    q.hull_normal = _rows_unit(np.einsum('nij,nj->ni', L, p.hull_normal)).astype(np.float32)
                q.cast = None
            prims.append(q)
        M2.prims = prims
        return M2


def _quat(R):
    """rotation matrices (n, 3, 3) -> unit quaternions (n, 4) as (w, x, y, z)."""
    from scipy.spatial.transform import Rotation
    q = Rotation.from_matrix(R).as_quat()                  # (x, y, z, w)
    return np.concatenate([q[:, 3:], q[:, :3]], 1)


def _qmul(a, b):
    w1, x1, y1, z1 = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    w2, x2, y2, z2 = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
    return np.stack([w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2, w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                     w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2, w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2], -1)


def dqs(V, J, W, R, t):
    """dual quaternion skinning of V (n, 3) with bone indices J and weights W (n, k) by the bones' rotations R
    (nb, 3, 3) and translations t (nb, 3) -> (n, 3)."""
    qr = _quat(R)
    qd = 0.5 * _qmul(np.concatenate([np.zeros((len(t), 1)), t], 1), qr)
    W = W / np.maximum(W.sum(1, keepdims=True), 1e-12)
    piv = qr[J[:, 0]]
    br = np.zeros((len(V), 4))
    bd = np.zeros((len(V), 4))
    for k in range(J.shape[1]):
        s = np.sign(np.einsum('ij,ij->i', qr[J[:, k]], piv))
        s[s == 0] = 1
        br += (W[:, k] * s)[:, None] * qr[J[:, k]]
        bd += (W[:, k] * s)[:, None] * qd[J[:, k]]
    n = np.linalg.norm(br, axis=1, keepdims=True)
    br, bd = br / n, bd / n
    w, v = br[:, :1], br[:, 1:]
    rot = V + 2 * np.cross(v, np.cross(v, V) + w * V)
    conj = br * np.array([1, -1, -1, -1.0])
    tr = 2 * _qmul(bd, conj)[:, 1:]
    return rot + tr


def _tri_frames(X, T):
    """per triangle (rows of T) its orthonormal frame as rows (n, 3, 3): the first edge, the in-plane normal to it,
    the face normal."""
    e1 = _rows_unit(X[T[:, 1]] - X[T[:, 0]])
    n = _rows_unit(np.cross(X[T[:, 1]] - X[T[:, 0]], X[T[:, 2]] - X[T[:, 0]]))
    e2 = np.cross(n, e1)
    return np.stack([e1, e2, n], 1)


def _rows_unit(X):
    n = np.linalg.norm(X, axis=1, keepdims=True)
    return X / np.maximum(n, 1e-12)


def _kind(name):
    if name.startswith('clawd_skin') or name.endswith('_skin'):
        return 'skin'
    if name.startswith('hair'):
        return 'hair'
    if name.startswith(('sclera', 'iris', 'lash', 'brow', 'teeth', 'tongue', 'mouth', 'nose')):
        return 'face'
    if name.startswith(('crab', 'star', 'clip', 'pin')):
        return 'accessory'
    return 'garment'


def _weld(name, kind, M, idx, attrs):
    """an object's primitives welded on their exported positions (the split seams' copies are bit-identical) -> Obj,
    its surface the outline's inward move undone (Prim.co(), averaged over a vertex's copies)."""
    Ps, Cs, Js, Ws, Fs, maps = [], [], [], [], [], []
    for i in idx:
        p = M.prims[i]
        Ps.append(np.asarray(p.position, np.float32))
        Cs.append(np.asarray(p.co(), np.float64))
        Js.append(attrs[i][0])
        Ws.append(attrs[i][1])
    allP = np.concatenate(Ps)
    key = np.ascontiguousarray(allP).view(np.dtype((np.void, 12))).ravel()
    _, first, inv = np.unique(key, return_index=True, return_inverse=True)
    n = len(first)
    C = np.zeros((n, 3))
    np.add.at(C, inv, np.concatenate(Cs))
    C /= np.bincount(inv, minlength=n)[:, None]
    J = np.concatenate(Js)[first]
    W = np.concatenate(Ws)[first]
    off, prims = 0, []
    for i, Pi in zip(idx, Ps):
        m = inv[off:off + len(Pi)]
        tri = np.asarray(M.prims[i].index, np.int64).reshape(-1, 3)
        Fs.append(m[tri])
        prims.append((i, m))
        off += len(Pi)
    F = np.concatenate(Fs)
    F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]
    V = C @ C3                                       # glTF -> Blender (row vectors: v_b = C3^T v_g)
    return Obj(name, kind, V, F, J, W, prims)


def load(build, export=None):
    """a build folder -> (Rig, the bundle or None): the export beside the bundle (NAME.look.glb, else NAME.vrm), the
    bundle's landmarks for the bones' tails and its objects' groups for their kinds."""
    from .render.buildboards import export_of
    from . import bundle as bl
    B = None
    bp = os.path.join(build, 'bundle')
    if os.path.isdir(bp):
        B = bl.load(bp)
    export = export or export_of(build)
    if export is None:
        raise FileNotFoundError('%s: no NAME.look.glb or NAME.vrm' % build)
    lm = kinds = None
    if B is not None:
        lm = (B._meta.get('landmarks') or {}).get('joints')
        kinds = {o['name']: {'skin': 'skin', 'hair': 'hair', 'garment': 'garment', 'accessory': 'accessory'}.get(
            o.get('group'), 'face') for o in B._meta.get('objects') or ()}
    return Rig(export, lm, kinds), B


# -------------------------------------------------------------------------------------------------------- the boards
BOARD_AZ = (0, 35, 90, 180)
BOARD_RES = (640, 800)


def board_views(rig, az=BOARD_AZ, res=BOARD_RES, prefix='', centre=None, ortho=None):
    """the posed boards' views: orthographic, one scale for every pose (1.45 x the height on the picture's height, the
    middle at 0.55 of it: the arms overhead and a kick fit), at the body boards' azimuths."""
    from .render.views import BoardView
    H = float(rig.M.root.get('boards', {}).get('height_m') or rig.M.root.get('height') or 1.5)
    W_, H_ = res
    o = ortho or 1.45 * H * max(W_, H_) / H_
    c = centre or (0.0, 0.0, 0.55 * H)
    return [BoardView('%s%03d' % (prefix, a), tuple(c), a, 6.0, 0.0, tuple(res), ortho=o) for a in az]


def render_boards(rig, poses, out, az=BOARD_AZ, res=BOARD_RES, adapter=None, ss=2, log=print):
    """each pose drawn by charkit's toon renderer from every azimuth into out/POSE_AZ.png -> {pose: {az: path}}. The
    renderer is set up once per pose (the posed model uploaded), the cast shadows off (they belong to the rest pose)."""
    from PIL import Image
    from .render import gpu
    os.makedirs(out, exist_ok=True)
    got = {}
    for name, D in poses.items():
        t0 = time.time()
        M2 = rig.model_posed(D)
        R = gpu.Renderer(M2, adapter=adapter or os.environ.get('CHARKIT_RENDER_ADAPTER'), ss=ss)
        got[name] = {}
        for v in board_views(rig, az, res, prefix=name + '_'):
            img = R.render(v)
            p = os.path.join(out, v.name + '.png')
            Image.fromarray(img).save(p)
            got[name][int(v.az)] = p
        del R
        log('board %s: %.1f s' % (name, time.time() - t0))
    return got


# ------------------------------------------------------------------------------------------------------- the regions
def head_length(rig, B=None):
    """the character's head length L (m): the bundle's assembly L, else the export's boards / head L."""
    if B is not None:
        try:
            return float(B.meta('assembly')['L'])
        except Exception:
            pass
    bd = rig.M.root.get('boards') or {}
    return float(bd.get('L') or rig.M.head.get('L') or 0.25)


def regions(rig, skin='clawd_skin'):
    """the skin's vertices by region (each vertex's dominant bone): {name: bool (n,)}: torso, head, and per side the arm
    (upper arm to the fingertips), its parts (upperarm, forearm, hand: the hand and its digits), each digit, the leg."""
    o = rig.objs[skin]
    dom = np.array(rig.bones)[o.dominant()]
    R = {'torso': np.isin(dom, TORSO), 'head': np.isin(dom, HEAD)}
    for s, S in (('left', 'L'), ('right', 'R')):
        R['arm_' + S] = np.isin(dom, _side_bones(s, ARM))
        R['upperarm_' + S] = dom == s + 'UpperArm'
        R['forearm_' + S] = dom == s + 'LowerArm'
        R['hand_' + S] = np.isin(dom, _side_bones(s, ARM[2:]))
        for f in ('Thumb',) + P.FINGERS:
            R['%s_%s' % (f.lower(), S)] = np.array([d.startswith(s + f) for d in dom])
        R['leg_' + S] = np.isin(dom, _side_bones(s, LEG))
        R['thigh_' + S] = dom == s + 'UpperLeg'
    return R


def submesh(F, keep):
    """the triangles of F whose three vertices are all kept -> (m, 3)."""
    return F[keep[F].all(1)]


def boundary_loops(F):
    """an oriented triangle set's boundary loops (each directed edge with no reverse twin), chained -> [[v...]]."""
    E = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    key = E[:, 0].astype(np.int64) * (1 << 32) + E[:, 1]
    rev = E[:, 1].astype(np.int64) * (1 << 32) + E[:, 0]
    b = E[~np.isin(key, rev)]
    nxt = {}
    for a, c in b.tolist():
        nxt.setdefault(a, []).append(c)
    loops = []
    while nxt:
        a0 = next(iter(nxt))
        loop, a = [a0], a0
        while True:
            outs = nxt.get(a)
            if not outs:
                break
            c = outs.pop()
            if not outs:
                del nxt[a]
            if c == a0:
                break
            loop.append(c)
            a = c
            if len(loop) > len(b) + 1:
                break
        if len(loop) >= 3:
            loops.append(loop)
    return loops


def capped(X, F, loops):
    """X with a centroid per loop appended, F with each loop fanned shut (orientation closing the surface) -> (X', F')."""
    if not loops:
        return X, F
    C = np.array([X[l].mean(0) for l in loops])
    n0 = len(X)
    tris = []
    for i, l in enumerate(loops):
        l = np.asarray(l)
        tris.append(np.stack([np.roll(l, -1), l, np.full(len(l), n0 + i)], 1))
    return np.vstack([X, C]), np.vstack([F, np.concatenate(tris)])


class Closed:
    """a region of a mesh as a closed surface (its boundary loops capped, the same caps rest and posed)."""

    def __init__(self, F, keep):
        self.F = submesh(F, keep)
        self.loops = boundary_loops(self.F) if len(self.F) else []

    def bvh(self, X):
        from .geom.bvh import BVH
        Xc, Fc = capped(X, self.F, self.loops)
        return BVH((Xc, Fc))

    def cap_distance(self, X, Q):
        """the distance of points Q from this region's caps (inf without caps): the junction where the region meets
        its neighbour."""
        if not self.loops:
            return np.full(len(Q), np.inf)
        from .geom.bvh import BVH
        Xc, Fc = capped(X, self.F, self.loops)
        d, _, _ = BVH((Xc, Fc[len(self.F):])).nearest(Q)
        return d


# ------------------------------------------------------------------------------------------------------ the measures
def inside_new(Q0, Q1, bv0, bv1, L, tol=0.004):
    """points (rest Q0, posed Q1) inside a closed surface posed (bv1) and not at rest (bv0), deeper than tol L ->
    dict(n, share, depth (L, the deepest), p95 (L, over the new ones))."""
    if len(Q1) == 0:
        return dict(n=0, share=0.0, depth=0.0, p95=0.0)
    w1 = bv1.winding_number(Q1)
    cand = w1 > 0.5
    if cand.any():
        w0 = bv0.winding_number(Q0[cand])
        cand[np.nonzero(cand)[0][w0 > 0.5]] = False
    if not cand.any():
        return dict(n=0, share=0.0, depth=0.0, p95=0.0)
    d, _, _ = bv1.nearest(Q1[cand])
    d = d / L
    deep = d > tol
    n = int(deep.sum())
    return dict(n=n, share=round(n / len(Q1), 5), depth=round(float(d.max()), 4) if n else 0.0,
                p95=round(float(np.percentile(d[deep], 95)), 4) if n else 0.0)


def crossing_edges(X, E, bv):
    """which edges (X[E[:, 0]] -> X[E[:, 1]]) cross the surface in bv -> bool (len(E),)."""
    a, b = X[E[:, 0]], X[E[:, 1]]
    d = b - a
    ln = np.linalg.norm(d, axis=1)
    ok = ln > 1e-12
    hit = np.zeros(len(E), bool)
    if ok.any():
        t, _ = bv.ray_cast(a[ok], d[ok] / ln[ok, None], tmax=ln[ok], tmin=1e-9)
        hit[ok] = np.isfinite(t)
    return hit


def crossings_new(X0, X1, E, bv0, bv1):
    """edges crossing a surface posed and not at rest -> dict(n, share)."""
    if len(E) == 0:
        return dict(n=0, share=0.0)
    h1 = crossing_edges(X1, E, bv1)
    if h1.any():
        h0 = crossing_edges(X0, E[h1], bv0)
        h1[np.nonzero(h1)[0][h0]] = False
    n = int(h1.sum())
    return dict(n=n, share=round(n / len(E), 5))


def strain(V0, V1, E, min_len=0.0):
    """|edge / rest edge - 1| over edges E at least min_len long at rest (all of them when none is) -> dict(p95,
    max). (Over the subdivided export's every edge the bridge's tight loops dominate: garments4 read the posed shoulder
    over edges of 0.015 L and more, STRAIN_EDGE.)"""
    l0 = np.linalg.norm(V0[E[:, 0]] - V0[E[:, 1]], axis=1)
    l1 = np.linalg.norm(V1[E[:, 0]] - V1[E[:, 1]], axis=1)
    ok = l0 > max(min_len, 1e-9)
    if not ok.any():
        ok = l0 > 1e-9
    s = np.abs(l1[ok] / l0[ok] - 1)
    if not len(s):
        return dict(p95=0.0, max=0.0)
    return dict(p95=round(float(np.percentile(s, 95)), 4), max=round(float(s.max()), 3))


def tri_area_n(X, F):
    c = np.cross(X[F[:, 1]] - X[F[:, 0]], X[F[:, 2]] - X[F[:, 0]])
    a = np.linalg.norm(c, axis=1)
    return 0.5 * a, c / np.maximum(a, 1e-30)[:, None]


def skin_faces(rig, o, D, X1, F=None):
    """the skin's faces against rest: collapsed (under 20% of their rest area) and folded (their normal turned over
    against their dominant bone's rotation of the rest normal) area shares -> dict(collapsed, folded)."""
    F = o.F if F is None else F
    a0, n0 = tri_area_n(o.V, F)
    a1, n1 = tri_area_n(X1, F)
    R, _ = rig.matrices(D)
    dom = o.dominant()[F[:, 0]]
    nr = np.einsum('nij,nj->ni', R[dom], n0)
    tot = max(a0.sum(), 1e-30)
    col = a1 < 0.2 * a0
    fold = (np.einsum('ij,ij->i', nr, n1) < 0) & ~col
    return dict(collapsed=round(float(a0[col].sum() / tot), 5), folded=round(float(a0[fold].sum() / tot), 5))


# ------------------------------------------------------------------------------------------------- joint volume: rings
# per joint: (name, parent bone, child bone, offsets along the bones in ring radii (negative: into the parent), the
# region's bones): a ring is the skin's section by the plane across the bone at that offset in the rest pose, its
# material points (an edge and a share along it) carried into every pose; its area there (on its best-fit plane) over
# its rest area is the volume the joint keeps (charkit.code_hand.fist_report's measure, on the built rig)
SIDE_JOINTS = [
    ('shoulder', 'Shoulder', 'UpperArm', (0.3, 0.6, 1.0)),
    ('elbow', 'UpperArm', 'LowerArm', (-1.0, -0.5, 0.0, 0.5, 1.0)),
    ('wrist', 'LowerArm', 'Hand', (-1.0, -0.5, 0.0, 0.4)),
    ('hip', 'hips', 'UpperLeg', (0.5, 1.0, 1.5)),
    ('knee', 'UpperLeg', 'LowerLeg', (-1.0, -0.5, 0.0, 0.5, 1.0)),
] + [('%s_%s' % (f.lower(), k), p, c, o) for f in P.FINGERS for k, p, c, o in (
    ('mcp', 'Hand', f + 'Proximal', (0.3, 0.7)),
    ('pip', f + 'Proximal', f + 'Intermediate', (-0.6, 0.0, 0.6)),
    ('dip', f + 'Intermediate', f + 'Distal', (-0.6, 0.0, 0.5)))] + [
    ('thumb_cmc', 'Hand', 'ThumbMetacarpal', (0.4, 0.8)),
    ('thumb_mcp', 'ThumbMetacarpal', 'ThumbProximal', (-0.6, 0.0, 0.6)),
    ('thumb_ip', 'ThumbProximal', 'ThumbDistal', (-0.6, 0.0, 0.5))]
MID_JOINTS = [('neck', 'upperChest', 'neck', (0.5, 1.0, 1.5)), ('waist', 'spine', 'chest', (-1.0, 0.0, 1.0))]


def _plane_loops(X, F, p, n):
    """the closed loops where plane (p, n) cuts triangles F of X -> [(edges (k, 2), shares (k,))] in loop order."""
    s = (X - p) @ n
    pos = s > 0
    T = F[pos[F].any(1) & ~pos[F].all(1)]
    if not len(T):
        return []
    links = {}
    tri_e = []
    for t in T.tolist():
        es = []
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            if pos[a] != pos[b]:
                es.append((a, b) if a < b else (b, a))
        if len(es) != 2:
            continue
        tri_e.append(es)
        for e in es:
            links.setdefault(e, []).append(len(tri_e) - 1)
    used = np.zeros(len(tri_e), bool)
    loops = []
    for t0 in range(len(tri_e)):
        if used[t0]:
            continue
        used[t0] = True
        start, e = tri_e[t0]
        chain, cur, closed = [start], t0, False
        while True:
            chain.append(e)
            nx = [t for t in links.get(e, ()) if t != cur]
            if not nx:
                break
            cur = nx[0]
            if used[cur]:
                closed = e == start or cur == t0
                break
            used[cur] = True
            a, b = tri_e[cur]
            e = b if a == e else a
            if e == start:
                closed = True
                break
        if closed and len(chain) >= 4:
            E = np.array(chain[:-1] if chain[-1] == chain[0] else chain, np.int64)
            sa, sb = s[E[:, 0]], s[E[:, 1]]
            loops.append((E, sa / (sa - sb)))
    return loops


def _ring_points(X, ring):
    E, t = ring
    return (1 - t)[:, None] * X[E[:, 0]] + t[:, None] * X[E[:, 1]]


def ring_area(Q):
    """a ring's area on its best-fit plane (charkit.code_hand.ring_area)."""
    c = Q.mean(0)
    _, _, Vt = np.linalg.svd(Q - c, full_matrices=False)
    xy = (Q - c) @ Vt[:2].T
    x, y = xy[:, 0], xy[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def _in_poly(xy, pt):
    x, y = xy[:, 0], xy[:, 1]
    x2, y2 = np.roll(x, -1), np.roll(y, -1)
    c = ((y > pt[1]) != (y2 > pt[1])) & (pt[0] < (x2 - x) * (pt[1] - y) / np.where(y2 != y, y2 - y, 1e-30) + x)
    return bool(c.sum() % 2)


def joint_rings(rig, skin='clawd_skin'):
    """every joint's rest rings on the skin -> {joint: [dict(offset, ring, area (m^2), r)]}, joints named per side
    (elbow_L, ...) and in the middle (neck, waist)."""
    o = rig.objs[skin]
    sk = rig.sk
    dom = np.array(rig.bones)[o.dominant()]
    rows = [(n + '_' + S, s + pa if pa != 'hips' else pa, s + ch, off)
            for s, S in (('left', 'L'), ('right', 'R')) for n, pa, ch, off in SIDE_JOINTS] + \
        [(n, pa, ch, off) for n, pa, ch, off in MID_JOINTS]
    out = {}
    for name, pa, ch, offs in rows:
        if pa not in sk.head or ch not in sk.head:
            continue
        keep = np.isin(dom, (pa, ch) if min(offs) < 0 else (ch,))
        F = submesh(o.F, keep)
        if not len(F):
            continue
        J = sk.head[ch]
        dp, dc = sk.dir(pa), sk.dir(ch)
        mid = P._unit(dp + dc)
        got, r = [], None
        for off in sorted(offs, key=abs):
            d = dc if off > 0 else dp if off < 0 else mid
            rr = r if r is not None else 0.03
            p = J + off * rr * d
            best = None
            for ring in _plane_loops(o.V, F, p, d):
                Q = _ring_points(o.V, ring)
                u = P._perp(np.array([1.0, 0, 0]) if abs(d[0]) < 0.9 else np.array([0, 1.0, 0]), d)
                v = np.cross(d, u)
                xy = np.stack([(Q - p) @ u, (Q - p) @ v], 1)
                if not _in_poly(xy, (0.0, 0.0)):
                    continue
                a = ring_area(Q)
                if best is None or a < best[1]:
                    best = (ring, a)
            if best is None:
                continue
            if r is None:
                r = float(np.sqrt(best[1] / np.pi))
                if off != 0:                                 # (the first ring found away from the joint sets r)
                    pass
            got.append(dict(offset=off, ring=best[0], area=best[1], r=r))
        if got:
            out[name] = got
    return out


def ring_ratios(rings, X):
    """each joint's rings posed (X the posed skin) over rest -> {joint: dict(min, at (offset), ratios)}."""
    out = {}
    for j, rs in rings.items():
        rat = [ring_area(_ring_points(X, g['ring'])) / max(g['area'], 1e-30) for g in rs]
        k = int(np.argmin(rat))
        out[j] = dict(min=round(float(rat[k]), 4), at=rs[k]['offset'], ratios=[round(float(x), 4) for x in rat])
    return out


# ------------------------------------------------------------------------------------------------------- per pose
# skin against skin: (pair name, region of the points, region of the closed surface)
SKIN_PAIRS = [('arm_torso_' + S, 'arm_' + S, 'torso') for S in 'LR'] + \
    [('arm_head_' + S, 'arm_' + S, 'head') for S in 'LR'] + \
    [('arm_arm', 'arm_L', 'arm_R'), ('leg_leg', 'leg_L', 'leg_R')] + \
    [('thigh_torso_' + S, 'thigh_' + S, 'torso') for S in 'LR'] + \
    [('finger_%s_%s_%s' % (a, b, S), '%s_%s' % (a, S), '%s_%s' % (b, S))
     for S in 'LR' for a, b in (('thumb', 'index'), ('index', 'middle'), ('middle', 'ring'), ('ring', 'little'))] + \
    [('finger_%s_%s_%s' % (b, a, S), '%s_%s' % (b, S), '%s_%s' % (a, S))
     for S in 'LR' for a, b in (('thumb', 'index'), ('index', 'middle'), ('middle', 'ring'), ('ring', 'little'))]
# garments inside the skin, by group (the checks' pairs)
GARMENT_GROUPS = {
    'sleeve_body': ('sleeve_L', 'sleeve_R', 'cuff_L', 'cuff_R', 'wrist_L', 'wrist_R'),
    'skirt_legs': ('skirt', 'overskirt_panel_L', 'overskirt_panel_R'),
    'top_body': ('top', 'bodice_panel', 'collar', 'bow', 'waistband'),
    'shorts_boots': ('shorts', 'boot_L', 'boot_R', 'boot_cuff_L', 'boot_cuff_R'),
}
UPPER = ('top', 'bodice_panel', 'collar', 'bow')               # what the hair and the sleeves may pass through
SKIRT = ('skirt', 'overskirt_panel_L', 'overskirt_panel_R')
STRAIN_EDGE = 0.015         # L: strain is read over edges at least this long at rest
ZONE = 0.35                 # L: the skin round a joint read for its strain, collapsed and folded area
ZONES = [(z + '_' + S, s + b) for s, S in (('left', 'L'), ('right', 'R')) for z, b in (
    ('shoulder', 'UpperArm'), ('elbow', 'LowerArm'), ('hip', 'UpperLeg'), ('knee', 'LowerLeg'))] + [('neck', 'neck')]
JUNCTION = 0.12             # L: a skin pair's points this near the other region's caps at rest are its junction
TOL = 0.004                  # L: a new penetration shallower than this is contact, not counted
MAX_POINTS = 12000           # points a region or garment is queried with (every k-th vertex beyond)
MAX_EDGES = 60000            # edges a crossing test casts (every k-th beyond)


def _every(n, cap):
    return np.arange(0, n, max(1, int(np.ceil(n / cap))))


def _concat(rig, names, X):
    """objects' (posed) meshes as one -> (V, F)."""
    Vs, Fs, off = [], [], 0
    for n in names:
        if n in rig.objs:
            Vs.append(X[n])
            Fs.append(rig.objs[n].F + off)
            off += len(X[n])
    if not Vs:
        return None
    return np.vstack(Vs), np.vstack(Fs)


class Context:
    """what every pose shares: the rig, L, the skin's regions and rings, the closed regions and their rest BVHs, the
    sample of points and edges each test casts, the rest surfaces."""

    def __init__(self, rig, B=None, skin='clawd_skin', max_points=MAX_POINTS, max_edges=MAX_EDGES):
        from .geom.bvh import BVH
        self.rig, self.skin = rig, skin
        self.tol = TOL
        self.L = head_length(rig, B)
        o = rig.objs[skin]
        self.R = regions(rig, skin)
        self.rings = joint_rings(rig, skin)
        self.rest = {n: ob.V for n, ob in rig.objs.items()}
        names = {a for _, a, b in SKIN_PAIRS} | {b for _, a, b in SKIN_PAIRS}
        self.closed = {r: Closed(o.F, self.R[r]) for r in names if self.R[r].any()}
        self.bv0 = {r: c.bvh(o.V) for r, c in self.closed.items() if len(c.F)}
        self.pts = {r: np.nonzero(self.R[r])[0][_every(int(self.R[r].sum()), max_points)] for r in names}
        # a pair's points within JUNCTION L of the other region's caps at rest are where the two regions meet (the
        # thigh's top at the hip socket, the arm at a joined shoulder): left out, so a joint's own turn isn't counted
        self.pair_pts = {}
        for name, a, b in SKIN_PAIRS:
            if b in self.closed and a in self.pts:
                idx = self.pts[a]
                far = self.closed[b].cap_distance(o.V, o.V[idx]) > JUNCTION * self.L
                self.pair_pts[name] = idx[far]
        self.skin_bv0 = BVH((o.V, o.F))
        # the skin round each joint (within ZONE L of its head at rest): where its deformation is read
        self.zones = {}
        sk_ = rig.sk
        for zn, bone in ZONES:
            if bone in sk_.head:
                keep = np.linalg.norm(o.V - sk_.head[bone], axis=1) < ZONE * self.L
                if keep.any():
                    Fz = o.F[keep[o.F].all(1)]
                    Ez = o.edges()
                    self.zones[zn] = (Fz, Ez[keep[Ez].all(1)])
        self.gpts = {n: _every(len(ob.V), max_points) for n, ob in rig.objs.items() if ob.kind == 'garment'}
        self.edges = {n: ob.edges() for n, ob in rig.objs.items()}
        hair = [n for n, ob in rig.objs.items() if ob.kind == 'hair']
        self.hair = hair
        hv = _concat(rig, hair, self.rest)
        self.hair_E = None
        if hv is not None:
            E = np.unique(np.sort(np.concatenate([hv[1][:, [0, 1]], hv[1][:, [1, 2]], hv[1][:, [2, 0]]]), 1), axis=0)
            self.hair_E = E[_every(len(E), max_edges)]
        # the hands' skin edges (hand-skirt)
        hand = self.R.get('hand_L', np.zeros(len(o.V), bool)) | self.R.get('hand_R', np.zeros(len(o.V), bool))
        Eh = o.edges()
        Eh = Eh[hand[Eh].all(1)]
        self.hand_E = Eh[_every(len(Eh), max_edges)]
        self.sleeve_E = {n: self.edges[n][_every(len(self.edges[n]), max_edges // 2)]
                         for n in ('sleeve_L', 'sleeve_R') if n in rig.objs}
        self.upper0 = self._bvh(UPPER + (skin,), self.rest)
        self.upper_g0 = self._bvh(UPPER, self.rest)
        self.skirt0 = self._bvh(SKIRT, self.rest)

    def _bvh(self, names, X):
        from .geom.bvh import BVH
        m = _concat(self.rig, names, X)
        return None if m is None else BVH(m)


def measure_pose(ctx, D, X=None):
    """one pose's measures (D: {bone: 4x4}) -> dict(rings, skin_pairs, garments, crossings, strain, skin)."""
    from .geom.bvh import BVH
    rig, L, sk = ctx.rig, ctx.L, ctx.skin
    X = X or rig.posed(D)
    Xs = X[sk]
    out = {'rings': ring_ratios(ctx.rings, Xs)}
    # skin against skin
    bv1 = {r: c.bvh(Xs) for r, c in ctx.closed.items() if len(c.F)}
    sp = {}
    for name, a, b in SKIN_PAIRS:
        if b not in bv1 or name not in ctx.pair_pts:
            continue
        idx = ctx.pair_pts[name]
        sp[name] = inside_new(ctx.rest[sk][idx], Xs[idx], ctx.bv0[b], bv1[b], L, ctx.tol)
    out['skin_pairs'] = sp
    # garments inside the skin
    skin_bv = BVH((Xs, rig.objs[sk].F))
    g = {}
    for n, idx in ctx.gpts.items():
        g[n] = inside_new(ctx.rest[n][idx], X[n][idx], ctx.skin_bv0, skin_bv, L, ctx.tol)
        g[n]['strain'] = strain(ctx.rest[n], X[n], ctx.edges[n], STRAIN_EDGE * L)
    out['garments'] = g
    # thin surfaces through each other
    cr = {}
    if ctx.hair_E is not None and ctx.upper0 is not None:
        h0 = _concat(rig, ctx.hair, ctx.rest)[0]
        h1 = _concat(rig, ctx.hair, X)[0]
        cr['hair_shoulders'] = crossings_new(h0, h1, ctx.hair_E, ctx.upper0, ctx._bvh(UPPER + (sk,), X))
    if ctx.skirt0 is not None and len(ctx.hand_E):
        cr['hand_skirt'] = crossings_new(ctx.rest[sk], Xs, ctx.hand_E, ctx.skirt0, ctx._bvh(SKIRT, X))
    if ctx.upper_g0 is not None:
        ug1 = ctx._bvh(UPPER, X)
        for n, E in ctx.sleeve_E.items():
            cr['sleeve_top_' + n[-1]] = crossings_new(ctx.rest[n], X[n], E, ctx.upper_g0, ug1)
    out['crossings'] = cr
    # the skin's own deformation
    o = rig.objs[sk]
    out['skin'] = dict(strain(o.V, Xs, ctx.edges[sk], STRAIN_EDGE * L), **skin_faces(rig, o, D, Xs))
    out['zones'] = {zn: dict(strain(o.V, Xs, Ez, STRAIN_EDGE * L), **skin_faces(rig, o, D, Xs, Fz))
                    for zn, (Fz, Ez) in ctx.zones.items() if len(Fz)}
    return out


JOINT_FAMILIES = ('shoulder', 'elbow', 'wrist', 'hip', 'knee', 'neck', 'waist', 'fingers')


def joint_family(j):
    k = j.split('_')[0]
    return 'fingers' if k in ('thumb', 'index', 'middle', 'ring', 'little') else k


def summary(m):
    """a pose's measures as its headline numbers (the report's table and the QA's checks read these) -> dict:
    vol_FAMILY the smallest ring ratio over the family's joints (1 kept); skin pairs and garment groups the deepest new
    penetration (L) and its share; crossings the share of edges newly through; strain p95; the skin's collapsed and
    folded area shares."""
    r = m['rings']
    s = {}
    for fam in JOINT_FAMILIES:
        v = [x['min'] for k, x in r.items() if joint_family(k) == fam]
        s['vol_' + fam] = min(v) if v else 1.0
    sp, g, cr = m['skin_pairs'], m['garments'], m['crossings']
    worst = lambda keys, f='depth': max([sp[k][f] for k in keys if k in sp] or [0.0])
    gw = lambda names, f='depth': max([g[n][f] for n in names if n in g] or [0.0])
    s.update({
        'arm_torso': worst([k for k in sp if k.startswith(('arm_torso', 'arm_head', 'arm_arm'))]),
        'leg_torso': worst([k for k in sp if k.startswith(('thigh_torso', 'leg_leg'))]),
        'finger_finger': worst([k for k in sp if k.startswith('finger_')]),
        'skin_strain': m['skin']['p95'], 'skin_collapsed': m['skin']['collapsed'], 'skin_folded': m['skin']['folded'],
    })
    for grp, names in GARMENT_GROUPS.items():
        s[grp] = gw(names)
        s[grp + '_share'] = gw(names, 'share')
    s['garment_strain'] = max([g[n]['strain']['p95'] for n in g] or [0.0])
    z = m.get('zones') or {}
    for fam in ('shoulder', 'elbow', 'hip', 'knee', 'neck'):
        zz = [v for k, v in z.items() if k.split('_')[0] == fam]
        if zz:
            s[fam + '_strain'] = max(v['p95'] for v in zz)
            s[fam + '_folded'] = max(v['folded'] + v['collapsed'] for v in zz)
    for k, v in cr.items():
        s[k] = v['share']
    return {k: round(float(v), 5) for k, v in s.items()}


# ------------------------------------------------------------------------------------------------------ weight sanity
def dense_weights(rig, o, rows=None):
    """an object's weights as a dense (n, bones) float32 array (bones: rig.bone_names(), humanoid ancestors merged)."""
    names = rig.bone_names()
    col = {b: i for i, b in enumerate(names)}
    jc = np.array([col[b] for b in rig.bones])
    J, W = (o.J, o.W) if rows is None else (o.J[rows], o.W[rows])
    out = np.zeros((len(J), len(names)), np.float32)
    for k in range(J.shape[1]):
        np.add.at(out, (np.arange(len(J)), jc[J[:, k]]), W[:, k])
    return out


def seg_dist(P_, a, b):
    ab = b - a
    t = np.clip(((P_ - a) @ ab) / max(ab @ ab, 1e-24), 0, 1)
    return np.linalg.norm(P_ - (a + t[:, None] * ab), axis=1)


def weight_sanity(rig, L, skin='clawd_skin', step_len=0.03, stray_far=0.35, max_points=40000):
    """the rig's weights checked once (no pose): per object the largest |sum - 1|, the vertices with no weight, stray
    influences (over 0.05 on a bone more than stray_far L further from the vertex than its dominant bone, and twice as
    far), influences across the body's middle (a vertex on one side weighted over 0.02 to the other side's bones),
    the sharpest weight step across an edge shorter than step_len L (half the L1 difference of the two weight vectors:
    1 a full switch); per garment its weights against the skin's under it (the same measure at the skin's nearest
    point: p95). -> {object: dict}."""
    from .geom.bvh import BVH
    sk = rig.sk
    names = rig.bone_names()
    seg = {b: (sk.head[b], sk.tail[b]) for b in names if b in sk.head}
    out = {}
    so = rig.objs[skin]
    skin_bv = BVH((so.V, so.F))
    Wskin = dense_weights(rig, so)
    for n, o in rig.objs.items():
        tot = o.W.sum(1)
        r = dict(sum_err=round(float(np.abs(tot[tot > 0] - 1).max()) if (tot > 0).any() else 0.0, 6),
                 none=int((tot <= 0).sum()))
        rows = _every(len(o.V), max_points)
        V, J, W = o.V[rows], o.J[rows], o.W[rows]
        hb = np.array(rig.bones)
        dom = hb[J[np.arange(len(J)), W.argmax(1)]]
        ddom = np.zeros(len(V))
        for b in np.unique(dom):
            m = dom == b
            if b in seg:
                ddom[m] = seg_dist(V[m], *seg[b])
        stray_n, stray_w, cross_n = 0, 0.0, 0
        for k in range(J.shape[1]):
            bk = hb[J[:, k]]
            wk = W[:, k]
            for b in np.unique(bk[wk > 0.02]):
                m = (bk == b) & (wk > 0.02)
                if b not in seg:
                    continue
                d = seg_dist(V[m], *seg[b])
                far = (wk[m] > 0.05) & (d > ddom[m] + stray_far * L) & (d > 2 * ddom[m])
                stray_n += int(far.sum())
                if far.any():
                    stray_w = max(stray_w, float(wk[m][far].max()))
                s = P.side_of(b)
                if s:
                    other = 'right' if s == 'left' else 'left'
                    cross_n += int(np.char.startswith(dom[m].astype(str), other).sum())
        r.update(stray=stray_n, stray_share=round(stray_n / max(len(V), 1), 5), stray_w=round(stray_w, 3),
                 cross=cross_n)
        E = o.edges()
        if len(E):
            ln = np.linalg.norm(o.V[E[:, 0]] - o.V[E[:, 1]], axis=1)
            Es = E[ln < step_len * L]
            Es = Es[_every(len(Es), 4 * max_points)]
            if len(Es):
                Wd = Wskin if n == skin else dense_weights(rig, o)
                st = 0.5 * np.abs(Wd[Es[:, 0]] - Wd[Es[:, 1]]).sum(1)
                r.update(step_max=round(float(st.max()), 4), step_p999=round(float(np.percentile(st, 99.9)), 4))
        if o.kind == 'garment':
            Wg = dense_weights(rig, o, rows)
            _, f, q = skin_bv.nearest(V)
            T = so.F[f]
            A, Bv, C = so.V[T[:, 0]], so.V[T[:, 1]], so.V[T[:, 2]]
            bc = _bary(q, A, Bv, C)
            Wq = sum(bc[:, i:i + 1] * Wskin[T[:, i]] for i in range(3))
            dis = 0.5 * np.abs(Wg - Wq).sum(1)
            r.update(vs_skin_p95=round(float(np.percentile(dis, 95)), 4), vs_skin_over=round(float((dis > 0.3).mean()), 4))
        out[n] = r
    return out


def _bary(q, A, B, C):
    v0, v1, v2 = B - A, C - A, q - A
    d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1)
    d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
    den = np.maximum(d00 * d11 - d01 * d01, 1e-30)
    v = (d11 * d20 - d01 * d21) / den
    w = (d00 * d21 - d01 * d20) / den
    bc = np.clip(np.stack([1 - v - w, v, w], 1), 0, 1)
    return bc / np.maximum(bc.sum(1, keepdims=True), 1e-12)


# ------------------------------------------------------------------------------------------------------ thresholds
# physical limits (report-only: no drawing of these poses grades them): (pass, warn), `better` lower unless noted.
# Volume: tissue is incompressible; a bent joint's section flattens but keeps most of its area: under 0.8 the pinch
# shows, under 0.65 the joint collapses (LBS's candy-wrapper). Penetration: contact (0.01 L, about 2.5 mm on Clawd)
# passes, 0.03 L shows. Crossings: a few edges at a seam pass, a percent shows. Strain: cloth and skin stretched 25%
# pass, 50% tear the look. Fingers are thin (about 0.06 L across): one inside another past a quarter of its width
# shows.
LIMITS = {
    'vol': (0.8, 0.65, 'higher'),
    'arm_torso': (0.01, 0.03), 'leg_torso': (0.01, 0.03), 'finger_finger': (0.008, 0.015),
    'sleeve_body': (0.01, 0.03), 'skirt_legs': (0.01, 0.03), 'top_body': (0.01, 0.03), 'shorts_boots': (0.01, 0.03),
    'hair_shoulders': (0.001, 0.01), 'hand_skirt': (0.002, 0.01), 'sleeve_top': (0.002, 0.01),
    'skin_strain': (0.25, 0.5), 'garment_strain': (0.25, 0.5), 'skin_collapsed': (0.002, 0.01),
    'skin_folded': (0.002, 0.01),
    'zone_strain': (0.25, 0.5), 'zone_folded': (0.01, 0.03),
}


def limit_of(key):
    k = 'vol' if key.startswith('vol_') else 'sleeve_top' if key.startswith('sleeve_top') else key
    if key.split('_')[0] in ('shoulder', 'elbow', 'hip', 'knee', 'neck') and key.endswith(('_strain', '_folded')):
        k = 'zone_' + key.split('_')[1]
    return LIMITS.get(k)


def grade(key, v):
    lim = limit_of(key)
    if lim is None or v is None:
        return 'INFO'
    hi = len(lim) > 2 and lim[2] == 'higher'
    p, w = lim[0], lim[1]
    if hi:
        return 'PASS' if v >= p else 'WARN' if v >= w else 'FAIL'
    return 'PASS' if v <= p else 'WARN' if v <= w else 'FAIL'


# ------------------------------------------------------------------------------------------------------------ run
def run(build, out=None, poses=None, boards=False, export=None, lib=None, log=print, az=BOARD_AZ, art=False):
    """the suite on a build -> the report (also out/rom.json and out/rom.md when out is given)."""
    t0, c0 = time.time(), time.process_time()
    rig, B = load(build, export)
    lib = lib or P.library()
    names = [n for n in (poses or list(lib)) if n in lib]
    ctx = Context(rig, B)
    t1 = time.time()
    rep = {'build': os.path.abspath(build), 'export': os.path.basename(rig.path), 'L': ctx.L,
           'bones': len(rig.bone_names()), 'poses': {}, 'context_s': round(t1 - t0, 1)}
    rep['weights'] = weight_sanity(rig, ctx.L)
    Ds = {}
    for n in names:
        t = time.time()
        D = rig.solve(lib[n])
        Ds[n] = D
        m = measure_pose(ctx, D)
        smy = summary(m)
        rep['poses'][n] = dict(group=lib[n].get('group'), what=lib[n].get('what'), summary=smy,
                               grades={k: grade(k, v) for k, v in smy.items()}, measures=m,
                               seconds=round(time.time() - t, 2))
        bad = [k for k, g in rep['poses'][n]['grades'].items() if g == 'FAIL']
        log('rom %-18s %.1f s  %s' % (n, time.time() - t, ('FAIL ' + ', '.join(bad)) if bad else 'ok'))
    if art and B is not None:
        rep['art'] = art_posed(rig, B, {n: Ds[n] for n in ART_POSES if n in Ds}, log=log)
    rep['seconds'] = round(time.time() - t0, 1)
    rep['cpu_s'] = round(time.process_time() - c0, 1)
    if out:
        os.makedirs(out, exist_ok=True)
        if boards:
            rep['boards'] = render_boards(rig, Ds, os.path.join(out, 'boards'), az=az, log=log)
        json.dump(rep, open(os.path.join(out, 'rom.json'), 'w'), indent=1, default=_js)
        open(os.path.join(out, 'rom.md'), 'w').write(markdown(rep))
    return rep


def _js(x):
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, (np.floating, np.integer)):
        return x.item()
    if isinstance(x, tuple):
        return list(x)
    return str(x)


COLUMNS = ('vol_shoulder', 'vol_elbow', 'vol_wrist', 'vol_hip', 'vol_knee', 'vol_fingers', 'vol_neck', 'vol_waist',
           'shoulder_strain', 'shoulder_folded', 'elbow_folded', 'hip_strain', 'knee_folded', 'neck_strain',
           'arm_torso', 'leg_torso', 'finger_finger', 'sleeve_body', 'skirt_legs', 'top_body', 'shorts_boots',
           'hair_shoulders', 'hand_skirt', 'sleeve_top_L', 'sleeve_top_R', 'garment_strain', 'skin_strain',
           'skin_collapsed', 'skin_folded')


def markdown(rep):
    L = ['# Range of motion: %s' % rep['build'], '',
         'Export %s, L %.4f m, %d bones; %d poses in %.0f s (context %.0f s). Report-only: physical limits '
         '(charkit.rom.LIMITS); FAIL in bold.' % (rep['export'], rep['L'], rep['bones'], len(rep['poses']),
                                                 rep['seconds'], rep['context_s']), '',
         '| pose | ' + ' | '.join(COLUMNS) + ' |', '|---|' + '---|' * len(COLUMNS)]
    for n, r in rep['poses'].items():
        cells = []
        for c in COLUMNS:
            v = r['summary'].get(c)
            g = r['grades'].get(c)
            t = '-' if v is None else ('%.3g' % v)
            cells.append('**%s**' % t if g == 'FAIL' else ('_%s_' % t if g == 'WARN' else t))
        L.append('| %s | %s |' % (n, ' | '.join(cells)))
    if rep.get('art'):
        L += ['', '## Toon artefacts posed against rest (charkit.artifactqa\'s detectors and proposed grades; the rest '
              'pose standing for the design)', '', '| pose | FAIL | WARN |', '|---|---|---|']
        for n, C in rep['art'].items():
            f = ', '.join('%s %.3g' % (k, c['value']) for k, c in sorted(C.items()) if c['grade'] == 'FAIL')
            w = ', '.join('%s %.3g' % (k, c['value']) for k, c in sorted(C.items()) if c['grade'] == 'WARN')
            L.append('| %s | %s | %s |' % (n, f or '-', w or '-'))
    L += ['', '## Weights', '', '| object | sum err | none | stray | stray w | cross | step max | vs skin p95 |',
          '|---|---|---|---|---|---|---|---|']
    for n, w in rep['weights'].items():
        L.append('| %s | %s | %s | %s | %s | %s | %s | %s |' % (n, w['sum_err'], w['none'], w['stray'], w['stray_w'],
                                                                w['cross'], w.get('step_max', '-'),
                                                                w.get('vs_skin_p95', '-')))
    return '\n'.join(L) + '\n'


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    build = args[0]
    out = opt('--out', os.path.join(build, 'rom'))
    poses = opt('--poses')
    if '--closeups' in args:
        rig, _ = load(build, opt('--export'))
        render_closeups(rig, os.path.join(out, 'closeups'))
        if '--only-closeups' in args:
            return 0
    rep = run(build, out, poses.split(',') if poses else None, boards='--boards' in args, export=opt('--export'),
              art='--art' in args)
    if '--json' in args:
        print(json.dumps({n: r['summary'] for n, r in rep['poses'].items()}, indent=1))
    print('rom: %d poses, %.0f s; %s' % (len(rep['poses']), rep['seconds'], os.path.join(out, 'rom.md')))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))


# --------------------------------------------------------------------------------------- toon artefacts on the poses
ART_SKIP = ('_face', '_neck')   # the skin's regions: a posed arm or hand in the head frame counts as face or neck skin
ART_POSES = ('raise_forward_90', 'arms_up', 'arm_across', 'elbows_135', 'spine_twist', 'head_turn', 'head_nod',
             'squat', 'kick_front')


class Posable:
    """a bundle made posable: each drawn variant's vertices (the skin's 'masked', every other object's 'eval') matched
    to the export's welded vertices (the same evaluation: exact for the garments and the hair; the skin's nearest), so
    a pose's bundle is the rest bundle with those variants' positions skinned and their directions (shrink, loop
    normals) turned (charkit.artifactqa then measures it as it measures the rest)."""

    def __init__(self, rig, B):
        from scipy.spatial import cKDTree
        self.rig, self.B = rig, B
        self.A = {k: B._arrays[k] for k in (B._arrays.files if hasattr(B._arrays, 'files') else B._arrays)}
        self.maps = {}
        for o in B.objects():
            var = 'masked' if o.group == 'skin' else 'eval'
            k = 'o/%s/%s/V' % (o.name, var)
            if o.name not in rig.objs or k not in self.A:
                continue
            V = np.asarray(self.A[k], float)
            ob = rig.objs[o.name]
            d, i = cKDTree(ob.V).query(V)
            self.maps[(o.name, var)] = (i, float(d.max()))

    def bundle(self, D):
        from . import bundle as bl
        R, t = self.rig.matrices(D)
        A = dict(self.A)
        for (name, var), (idx, _) in self.maps.items():
            ob = self.rig.objs[name]
            J, W = ob.J[idx], ob.W[idx]
            W = W / np.maximum(W.sum(1, keepdims=True), 1e-12)
            Lm = np.einsum('nk,nkij->nij', W, R[J])
            T = np.einsum('nk,nkj->nj', W, t[J])
            p = 'o/%s/%s/' % (name, var)
            V = np.asarray(A[p + 'V'], float)
            A[p + 'V'] = np.einsum('nij,nj->ni', Lm, V) + T
            if p + 'shrink' in A:
                A[p + 'shrink'] = np.einsum('nij,nj->ni', Lm, np.asarray(A[p + 'shrink'], float)).astype(np.float32)
            if p + 'lnor' in A:
                lv = np.asarray(A[p + 'loopv'], np.int64)
                A[p + 'lnor'] = _rows_unit(np.einsum('nij,nj->ni', Lm[lv], np.asarray(A[p + 'lnor'], float))
                                           ).astype(np.float32)
        return bl.Bundle(self.B._meta, A, path=getattr(self.B, 'path', None))


def art_posed(rig, B, poses, log=print):
    """the toon artefact detectors (charkit.artifactqa: outline corners, terminator kinks, fragments, speckle, the
    silhouette's spikes, points and bumps) on each pose's bundle against the rest bundle's, as artifactqa grades ours
    against the design's (the rest standing for the design: a pose that makes a region rougher than it is at rest) ->
    {pose: {check: dict(value, grade, worst view)}}."""
    from . import artifactqa as aq, qa3d
    ctx = qa3d.Design(B).sheet_context()
    body_ppl = None if 'why' in ctx else ctx['ppl']
    az3 = 35.5 if 'why' in ctx else ctx['az3']
    page = ctx['rgb'].shape[0] if 'rgb' in ctx else 1440
    pz = Posable(rig, B)
    t = time.time()
    rest = aq.ours(B, az3, body_ppl, body_page=page)
    log('art rest: %.1f s' % (time.time() - t))
    C0 = aq.checks(rest, rest)
    out = {}
    for n, D in poses.items():
        t = time.time()
        O = aq.ours(pz.bundle(D), az3, body_ppl, body_page=page)
        C = aq.checks(O, rest)
        out[n] = {}
        for k, c in C.items():
            if c.get('value') is None or k.endswith(ART_SKIP):
                continue
            if k.startswith('peeks_'):                  # (a count, no ratio: the pose's extra bits over the rest's)
                v = c['value'] - ((C0.get(k) or {}).get('value') or 0)
                g = 'PASS' if v <= aq.PEEKS[0] else 'WARN' if v <= aq.PEEKS[1] else 'FAIL'
                out[n][k] = dict(value=v, grade=g, worst=c.get('worst'))
            else:
                out[n][k] = dict(value=c.get('value'), grade=c.get('grade'), worst=c.get('worst'))
        log('art %s: %.1f s, FAIL %s' % (n, time.time() - t, [k for k, c in out[n].items() if c['grade'] == 'FAIL']))
    return out


# -------------------------------------------------------------------------------------------------------- close-ups
# (name, pose, the joint looked at, its side's bone, azimuths, window (m across), what's drawn: 'all' or 'body' (the
# skin, the face and the hair: the garments off), skinning)
CLOSEUPS = [
    ('elbow_lbs', 'elbows_135', 'leftLowerArm', (90, 35), 0.32, 'body', 'lbs'),
    ('elbow_dqs', 'elbows_135', 'leftLowerArm', (90, 35), 0.32, 'body', 'dqs'),
    ('knee_lbs', 'knees_135', 'leftLowerLeg', (90,), 0.4, 'body', 'lbs'),
    ('knee_dqs', 'knees_135', 'leftLowerLeg', (90,), 0.4, 'body', 'dqs'),
    ('shoulder_fwd', 'raise_forward_90', 'leftUpperArm', (35, 90, 0), 0.5, 'body', 'lbs'),
    ('shoulder_fwd_dressed', 'raise_forward_90', 'leftUpperArm', (35, 90, 0), 0.5, 'all', 'lbs'),
    ('shoulder_side', 'raise_side_90', 'leftUpperArm', (0, 35, 180), 0.5, 'body', 'lbs'),
    ('shoulder_side_dressed', 'raise_side_90', 'leftUpperArm', (0, 35, 180), 0.5, 'all', 'lbs'),
    ('shoulder_up', 'arms_up', 'leftUpperArm', (35, 90), 0.6, 'body', 'lbs'),
    ('shoulder_up_dressed', 'arms_up', 'leftUpperArm', (35, 90), 0.6, 'all', 'lbs'),
    ('hip_squat', 'squat', 'leftUpperLeg', (90, 35), 0.5, 'body', 'lbs'),
    ('neck_turn', 'head_turn', 'neck', (0, 35), 0.4, 'all', 'lbs'),
    ('hand_fist', 'hand_fist', 'leftMiddleProximal', (0, 90, 35), 0.16, 'all', 'lbs'),
    ('hand_open', 'hand_open', 'leftMiddleProximal', (0, 90), 0.16, 'all', 'lbs'),
    ('hand_point', 'hand_point', 'leftMiddleProximal', (0, 90, 35), 0.16, 'all', 'lbs'),
    ('hand_rest', 'rest', 'leftMiddleProximal', (0, 90), 0.16, 'all', 'lbs'),
]


def render_closeups(rig, out, lib=None, which=None, res=(520, 520), adapter=None, ss=2, log=print):
    """the close-up set (CLOSEUPS) into out/NAME_AZ.png: the joint the pose stresses, posed, at a fixed window round
    its posed head, the garments on or off, linear blend or dual quaternion skinning -> {name: {az: path}}."""
    import copy
    from PIL import Image
    from .render import gpu
    from .render.views import BoardView
    lib = lib or P.library()
    os.makedirs(out, exist_ok=True)
    body = {n for n, o in rig.objs.items() if o.kind != 'garment'}
    got = {}
    for name, pose_, bone, azs, win, draw, method in CLOSEUPS:
        if which and name not in which or pose_ not in lib or bone not in rig.sk.head:
            continue
        D = rig.solve(lib[pose_])
        M2 = rig.model_posed(D) if method == 'lbs' else _model_dqs(rig, D)
        if draw == 'body':                      # (the skin whole: its bare variant drawn, the masked one off)
            M2 = copy.copy(M2)
            has_bare = {p.object for p in M2.prims if p.variant == 'bare'}
            keep = []
            for p in M2.prims:
                if p.object in body or p.object not in rig.objs:
                    if p.variant == 'bare':
                        p = copy.copy(p)
                        p.mx = dict(p.mx, variant=None)
                    elif p.object in has_bare:
                        continue
                    keep.append(p)
            M2.prims = keep
        H, _ = P.posed_joints(rig.sk, D)
        c = H[bone]
        R = gpu.Renderer(M2, adapter=adapter or os.environ.get('CHARKIT_RENDER_ADAPTER'), ss=ss)
        got[name] = {}
        for az in azs:
            v = BoardView('%s_%03d' % (name, az), tuple(float(x) for x in c), az, 6.0, 0.0, tuple(res), ortho=win)
            p = os.path.join(out, v.name + '.png')
            Image.fromarray(R.render(v)).save(p)
            got[name][az] = p
        del R
        log('closeup %s' % name)
    return got


def _model_dqs(rig, D):
    """model_posed with dual quaternion skinning (the close-ups' reference: the joint as it would keep its volume)."""
    import copy
    R, t = rig.matrices(D)
    M2 = copy.copy(rig.M)
    prims = []
    for i, p in enumerate(rig.M.prims):
        q = copy.copy(p)
        J, W = rig.attrs[i]
        if J is not None:
            Pb = np.asarray(p.position, float) @ C3
            X = dqs(Pb, J, W, R, t)
            q.position = (X @ C3.T).astype(np.float32)
            # (normals: the LBS blend's linear part, renormalised: the close-up's shading only)
            Rg = np.einsum('ij,njk,lk->nil', C3, R, C3)
            Wn = W / np.maximum(W.sum(1, keepdims=True), 1e-12)
            Lm = np.einsum('nk,nkij->nij', Wn, Rg[J])
            q.normal = _rows_unit(np.einsum('nij,nj->ni', Lm, p.normal)).astype(np.float32)
            if p.hull_normal is not None:
                q.hull_normal = _rows_unit(np.einsum('nij,nj->ni', Lm, p.hull_normal)).astype(np.float32)
            q.cast = None
        prims.append(q)
    M2.prims = prims
    return M2


# ------------------------------------------------------------------------------------------------- bodies compared
BODY_COLS = ('vol_elbow', 'vol_knee', 'vol_fingers', 'arm_torso', 'leg_torso', 'finger_finger', 'shoulder_strain',
             'shoulder_folded', 'elbow_folded', 'knee_folded', 'neck_strain')
GARMENT_COLS = ('sleeve_body', 'top_body', 'skirt_legs', 'shorts_boots', 'sleeve_top_L', 'sleeve_top_R',
                'garment_strain', 'hand_skirt', 'hair_shoulders')


def compare_markdown(reps, labels):
    """several bodies' reports (run()'s) side by side: per pose, body findings then garment findings, each cell the
    bodies' readings in order (a / b), FAIL in bold, WARN in italics."""
    def cell(key, vals):
        out = []
        for v in vals:
            if v is None:
                out.append('-')
                continue
            g = grade(key, v)
            t = '%.3g' % v
            out.append('**%s**' % t if g == 'FAIL' else '_%s_' % t if g == 'WARN' else t)
        return ' / '.join(out)
    L = ['# Range of motion: %s' % ' / '.join(labels), '',
         'Each cell: %s. Report-only, physical limits (charkit.rom.LIMITS); **FAIL**, _WARN_.' % ' / '.join(labels)]
    for title, cols in (('Body', BODY_COLS), ('Garments and hair', GARMENT_COLS)):
        L += ['', '## ' + title, '', '| pose | ' + ' | '.join(cols) + ' |', '|---|' + '---|' * len(cols)]
        for p in reps[0]['poses']:
            row = [cell(c, [(r['poses'].get(p) or {}).get('summary', {}).get(c) for r in reps]) for c in cols]
            L.append('| %s | %s |' % (p, ' | '.join(row)))
    L += ['', '## Weights (worst object)', '']
    for lab, r in zip(labels, reps):
        w = r['weights']
        worst = max(w, key=lambda n: w[n].get('stray_share', 0))
        L.append('- %s: stray influences worst on %s (%.2f%% of its vertices, weight up to %.2f); skin stray %s, '
                 'sums within %.1e' % (lab, worst, 100 * w[worst]['stray_share'], w[worst]['stray_w'],
                                       w.get('clawd_skin', {}).get('stray'), max(x['sum_err'] for x in w.values())))
    return '\n'.join(L) + '\n'
