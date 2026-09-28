"""The face measured without Blender, in a second or two: our face, eyes and neck for a spec's knobs, and the same graded
checks the build's QA writes (charkit/qa3d.py: eye_*, sheet_*, face_shape_*), so charkit/facefit.py can search the knobs.

What a build would make, made here:
  - the skin, eyes and mouth: charkit.character.assemble without the shape keys, the body and the wrap's knob-independent
    part kept between calls (a new head, eye or mouth knob set re-wraps the head and re-places the features, ~0.5 s);
  - the skin as Blender evaluates it: its Subdivision Surface modifier (level 1, limit surface, the eye margins creased)
    in numpy (charkit/subdiv.py; within 1 um of Blender's) over the head and neck; level 2 round the eyes for the eye
    renders (a render draws the modifier's render level);
  - the cranium from the generated hair (charkit.scene.fit_cranium on the cached arrays);
  - the generated character (the TRELLIS target) aligned on our eyes as charkit.scene.hair_shape_volume aligns it;
  - the hair, accessories and garments: cached from one Blender build (charkit/fit_blender.py --env), since the face and
    eye knobs don't make them.
What is measured, the same way the QA measures it:
  - sheet       charkit.sheetqa.measure_ours on the z-buffer of those meshes, against the model sheet measured once;
  - face_shape  charkit.faceqa.measure against the target;
  - eyes        each eye rendered head-on at the rig's scale (a supersampled z-buffer: the skin by material, the eye plates
                by their textures (charkit.eyetex, sampled at their UVs, the iris over the white by its alpha), the lashes
                flat; filtered down like the renderer's pixel filter), then charkit.eyeqa as on Blender's render.

    from charkit import faceeval
    E = faceeval.Evaluator(resolved_spec, R, cache_dir)       # R: charkit.refs.measure of the rig; cache: fit_blender's
    res = E.run(spec)                                         # {'checks': {name: {value, status, ...}}, 'raw': ...}
"""
import contextlib, copy, io, json, math, os

import numpy as np

from . import character, eyeqa, eyetex, faceqa, sheetqa, subdiv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EYE_SIZE = 0.42                  # the eye render's window, in L (charkit.qa3d._eye_render)
SS = 4                           # eye render supersampling per pixel side (3 agrees nearly as well at 40% the cost)
FILTER = 0.55                    # the pixel filter's Gaussian sigma, in output pixels (EEVEE's 1.5 px filter)
STATUS = ['PASS', 'WARN', 'FAIL', 'SKIPPED']


def _path(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def _rgba(path):
    """an image as floats (H, W, 4), row 0 = top, as Blender's image loader gives it (byte values / 255, straight alpha)."""
    from PIL import Image
    return np.asarray(Image.open(path).convert('RGBA'), np.float32) / 255.0


def _tris(faces):
    """fan-triangulated polygons -> (m, 3), and each triangle's polygon index (charkit.faceqa.triangles' order)."""
    cnt = np.array([len(f) for f in faces])
    flat = np.array([v for f in faces for v in f], np.int64)
    starts = np.concatenate([[0], np.cumsum(cnt)[:-1]])
    return faceqa.triangles(flat, starts, cnt)


# ------------------------------------------------------------------------------------------------------------ geometry
def skin_mesh(A, below=0.55, levels=1, box=None):
    """the skin as the QA sees it: the head and neck (from `below` L under the chin up) subdivided like Blender's modifier
    (the eye margins creased): levels 1 as the QA reads meshes (the viewport level), 2 as a render draws it; box: only
    the skin inside (x0, x1, z0, z1) world. -> (V, tris, per-triangle material (0 body, 1 head, 2 mouth cavity,
    3 eye line))."""
    V = np.asarray(A['verts']); Hd = A['head']; L = Hd['L']
    keep = V[:, 2] > Hd['centre'][2] - Hd['H'].chin - below * L
    if box is not None:
        x0, x1, z0, z1 = box
        keep &= (V[:, 0] > x0) & (V[:, 0] < x1) & (V[:, 2] > z0) & (V[:, 2] < z1)
    Vr, fr, fi, used = subdiv.region(V, A['faces'], keep)
    remap = np.full(len(V), -1, np.int64); remap[used] = np.arange(len(used))
    sharp = []
    for E in A['eyes']:
        lp = E['eye']['margin']
        sharp += [(remap[a], remap[b]) for a, b in zip(lp, lp[1:] + lp[:1]) if remap[a] >= 0 and remap[b] >= 0]
    V1, quads, parent = subdiv.catmull_clark(Vr, fr, sharp, levels=levels)
    T = np.concatenate([quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]])
    fm = np.asarray(A['fmat'])[fi][np.concatenate([parent, parent])]
    return V1, T, fm


def parts(A):
    """the eye and mouth parts as the build makes them: {name: (V, tris, per-triangle material, uvs or None)}; eye parts
    per side ('iris_L' ...), the lash ribbons' materials 0 lash, 1 lower lash, 2 crease."""
    out = {}
    for E in A['eyes']:
        tag = 'L' if E['side'] > 0 else 'R'
        for k in ('sclera', 'iris'):
            v, f, uv = E[k]
            t, poly = _tris(f)
            out[f'{k}_{tag}'] = (np.asarray(v), t, np.zeros(len(t), int), np.asarray(uv))
        lv, lf, lm, off = [], [], [], 0
        for k_, (rv, rq) in enumerate(E['lashes']):
            lv.append(rv); lf += [tuple(i + off for i in f) for f in rq]; lm += [min(k_, 2)] * len(rq); off += len(rv)
        t, poly = _tris(lf)
        out[f'lash_{tag}'] = (np.vstack(lv), t, np.asarray(lm)[poly], None)
        bv, bq = E['brow']
        t, _ = _tris(bq)
        out[f'brow_{tag}'] = (np.asarray(bv), t, np.zeros(len(t), int), None)
    Mo = A['mouth']
    for name, key in (('teeth', 'teeth'), ('tongue', 'tongue'), ('mouth_line', 'line')):
        v, q = Mo[key]
        t, _ = _tris(q)
        out[name] = (np.asarray(v), t, np.zeros(len(t), int), None)
    return out


def expression_data(A, spec):
    """charkit.qa3d.expression_data's arrays from an assembly with its keys (character.assemble(keys=True)): the posed
    base meshes (the skin's control mesh: the QA reads them with only the armature on), a class per triangle (the iris
    where its texture's alpha, sampled at the polygon's UV centre, is at least 0.5) and each expression key's offsets."""
    from . import exprqa
    CL = exprqa.CLASS
    Hd = A['head']; L = Hd['L']; c = np.asarray(Hd['centre'], float)
    IK = spec.get('iris')
    ir, sh = eyetex.iris(IK), eyetex.shine(IK)
    iris_a = np.maximum(ir[..., 3], sh[..., 3])
    parts = []

    def sparse(D):
        D = np.asarray(D, float)
        idx = np.nonzero(np.abs(D).max(1) > 1e-7)[0]
        return idx, D[idx]

    def put(name, V, faces, lab_fn, keys, keep=None, uvs=None):
        T, poly = _tris(faces)
        lab = lab_fn(poly, T, uvs)
        ok = lab >= 0
        if keep is not None:
            ok &= keep(V[T].mean(1))
        parts.append((name, np.asarray(V, float), T[ok], lab[ok], {k: sparse(D) for k, D in keys.items()}))

    V = np.asarray(A['verts'])
    by = np.array([CL['skin'], CL['skin'], CL['mouth'], CL['line']])
    fm = np.asarray(A['fmat'])
    head = lambda P: (P[:, 2] > c[2] - 0.85 * L) & (P[:, 2] < c[2] + 0.55 * L) & (P[:, 1] < c[1] + 0.1 * L)
    names = list(A['eyes'][0]['keys'])
    keys = {'eye_' + n: sum(E['keys'][n][0] for E in A['eyes']) for n in names}
    keys.update({'mouth_' + sh_: D for sh_, D in A['mouth']['keys'].items()})
    put('skin', V, A['faces'], lambda poly, T, uv: by[np.minimum(fm[poly], 3)], keys, head)
    from . import eyes as eyelib
    cz = eyetex._knobs(IK)['cz']
    for E in A['eyes']:
        tag = 'L' if E['side'] > 0 else 'R'
        v, f, uv = E['iris']
        uv = np.asarray(uv)
        n = iris_a.shape[0]

        def iris_lab(poly, T, _, f=f, uv=uv):
            pu = np.array([uv[list(f[p])].mean(0) for p in range(len(f))])[poly]
            pu = np.clip(pu, 0, 1 - 1e-6)
            a = iris_a[n - 1 - (pu[:, 1] * n).astype(int), (pu[:, 0] * n).astype(int)]
            return np.where(a >= 0.5, CL['iris'], -1)
        back = np.zeros((len(v), 3)); back[:, 1] = 0.006
        ik = {'eye_blink': back, 'eye_happy': back}
        ik.update({'eye_' + nm: eyelib.iris_scale(v, uv, cz, s_) for nm, s_ in getattr(eyelib, 'IRIS_SCALE', {}).items()})
        put('iris_' + tag, v, f, iris_lab, ik)
        v, f, _ = E['sclera']
        put('sclera_' + tag, v, f, lambda poly, T, uv: np.full(len(poly), CL['white']), {'eye_blink': back[:len(v)],
                                                                                          'eye_happy': back[:len(v)]})
        lv, lq, off = [], [], 0
        for rv, rq in E['lashes']:
            lv.append(rv); lq += [tuple(i + off for i in q) for q in rq]; off += len(rv)
        put('lash_' + tag, np.vstack(lv), lq, lambda poly, T, uv: np.full(len(poly), CL['line']),
            {'eye_' + nm: np.vstack(E['keys'][nm][1]) for nm in names})
        bv, bq = E['brow']
        put('brow_' + tag, bv, bq, lambda poly, T, uv: np.full(len(poly), CL['brow']),
            {'brow_' + k: D for k, D in E['brow_keys'].items()})
    Mo = A['mouth']
    for nm, key, cl, kk in (('teeth', 'teeth', CL['white'], 'teeth_keys'), ('tongue', 'tongue', CL['mouth'], 'tongue_keys'),
                            ('mouth_line', 'line', CL['line'], 'line_keys')):
        v, q = Mo[key]
        put(nm, v, q, lambda poly, T, uv, cl=cl: np.full(len(poly), cl), {'mouth_' + sh_: D for sh_, D in Mo[kk].items()})
    iw = [np.asarray(E['iris'][0]).mean(0) for E in A['eyes']]
    return dict(parts=parts, eye_z=float(np.mean([w[2] for w in iw])), L=L)


# ------------------------------------------------------------------------------------------------------------ rasterising
def raster(meshes, x0, z0, pix, W, H):
    """the nearest surface per pixel of an orthographic view from the front (looking +y), pixel (r, c)'s centre at world
    x = x0 + (c + 0.5) pix, z = z0 - (r + 0.5) pix. meshes: [(V, tris)]. -> (mesh index (H, W), -1 = nothing; triangle
    index; barycentric weights b1, b2 of the triangle's second and third corners)."""
    pix_all, dep, mid, tid, B1, B2 = [], [], [], [], [], []
    for m, (V, T) in enumerate(meshes):
        if len(T) == 0:
            continue
        cc = (V[:, 0] - x0) / pix - 0.5
        rr = (z0 - V[:, 2]) / pix - 0.5
        tc, tr = cc[T], rr[T]
        near = (tc.max(1) >= 0) & (tc.min(1) <= W - 1) & (tr.max(1) >= 0) & (tr.min(1) <= H - 1)
        T, tc, tr = T[near], tc[near], tr[near]
        tmap = np.nonzero(near)[0]
        c_lo = np.maximum(np.ceil(tc.min(1)), 0).astype(np.int64); c_hi = np.minimum(np.floor(tc.max(1)), W - 1).astype(np.int64)
        r_lo = np.maximum(np.ceil(tr.min(1)), 0).astype(np.int64); r_hi = np.minimum(np.floor(tr.max(1)), H - 1).astype(np.int64)
        nx, ny = np.maximum(c_hi - c_lo + 1, 0), np.maximum(r_hi - r_lo + 1, 0)
        cnt = nx * ny
        ok = np.nonzero(cnt > 0)[0]
        if not len(ok):
            continue
        t_id = np.repeat(ok, cnt[ok])
        local = np.arange(len(t_id)) - np.repeat(np.cumsum(cnt[ok]) - cnt[ok], cnt[ok])
        px_c = c_lo[t_id] + local % nx[t_id]
        px_r = r_lo[t_id] + local // nx[t_id]
        ax, ay = tc[t_id, 0], tr[t_id, 0]
        v0x, v0y = tc[t_id, 1] - ax, tr[t_id, 1] - ay
        v1x, v1y = tc[t_id, 2] - ax, tr[t_id, 2] - ay
        v2x, v2y = px_c - ax, px_r - ay
        den = v0x * v1y - v1x * v0y
        good = np.abs(den) > 1e-12
        den = np.where(good, den, 1.0)
        b1 = (v2x * v1y - v1x * v2y) / den
        b2 = (v0x * v2y - v2x * v0y) / den
        e = -1e-9
        ins = good & (b1 >= e) & (b2 >= e) & (1 - b1 - b2 >= e)
        yv = V[:, 1][T]
        d = yv[t_id, 0] * (1 - b1 - b2) + yv[t_id, 1] * b1 + yv[t_id, 2] * b2
        pix_all.append((px_r * W + px_c)[ins]); dep.append(d[ins]); mid.append(np.full(ins.sum(), m))
        tid.append(tmap[t_id[ins]]); B1.append(b1[ins]); B2.append(b2[ins])
    M = np.full(H * W, -1); Ti = np.zeros(H * W, np.int64); b1o = np.zeros(H * W); b2o = np.zeros(H * W)
    if pix_all:
        p, d = np.concatenate(pix_all), np.concatenate(dep)
        zb = np.full(H * W, np.inf)
        np.minimum.at(zb, p, d)
        w = d <= zb[p]                                  # the nearest sample per pixel (a tie: either)
        p = p[w]
        M[p] = np.concatenate(mid)[w]; Ti[p] = np.concatenate(tid)[w]
        b1o[p] = np.concatenate(B1)[w]; b2o[p] = np.concatenate(B2)[w]
    return M.reshape(H, W), Ti.reshape(H, W), b1o.reshape(H, W), b2o.reshape(H, W)


def _sample(tex, uv):
    """bilinear texture lookup (tex (n, n, c), row 0 = top = v 1) at uv (m, 2); outside [0, 1] -> 0 (the plates' CLIP)."""
    n = tex.shape[0]
    x = uv[:, 0] * n - 0.5; y = (1 - uv[:, 1]) * n - 0.5
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    def at(yy, xx):
        return tex[np.clip(yy, 0, n - 1), np.clip(xx, 0, n - 1)]
    out = (at(y0, x0) * (1 - fx) * (1 - fy) + at(y0, x0 + 1) * fx * (1 - fy) + at(y0 + 1, x0) * (1 - fx) * fy
           + at(y0 + 1, x0 + 1) * fx * fy)
    inside = (uv[:, 0] >= 0) & (uv[:, 0] <= 1) & (uv[:, 1] >= 0) & (uv[:, 1] <= 1)
    return np.where(inside[:, None], out, 0.0)


def _blur_down(img, ss, sigma):
    """a Gaussian pixel filter (sigma in output pixels) and decimation by ss: (H ss, W ss, c) -> (H, W, c)."""
    s = sigma * ss
    r = int(math.ceil(3 * s))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / s) ** 2); k /= k.sum()
    pad = np.pad(img, ((r, r), (r, r), (0, 0)), mode='edge')
    tmp = sum(k[i] * pad[i:i + img.shape[0], :, :] for i in range(2 * r + 1))
    tmp = sum(k[i] * tmp[:, i:i + img.shape[1], :] for i in range(2 * r + 1))
    off = ss // 2
    return tmp[off::ss, off::ss]


def shifted(G, d):
    """the geometry moved rigidly by d (world): the same scene on another pixel grid."""
    A = dict(G['A']); Hd = dict(A['head'])
    Hd['centre'] = np.asarray(Hd['centre']) + d
    A['head'] = Hd
    V, T, fm = G['skin']
    P = {k: (v + d,) + tuple(rest) for k, (v, *rest) in G['parts'].items()}
    out = dict(G, A=A, skin=(V + d, T, fm), parts=P)
    if G.get('garments') is not None:
        out['garments'] = (G['garments'][0] + d, G['garments'][1])
    out['shift'] = d
    return out


def mean_checks(runs):
    """checks measured several times (jittered) -> one set: each numeric value (and the numbers in 'ratios') averaged
    over the runs that have it, the status of the first run's; 'missing' where some runs lack the check."""
    out = {}
    for k in runs[0].keys() | set().union(*runs):
        have = [r[k] for r in runs if k in r]
        c = dict(have[0])
        vals = [h.get('value') for h in have if isinstance(h.get('value'), (int, float)) and not isinstance(h.get('value'), bool)]
        if vals:
            c['value'] = float(np.mean(vals))
        if isinstance(c.get('ratios'), dict):
            c['ratios'] = {q: float(np.mean([h['ratios'][q] for h in have if q in h.get('ratios', {})]))
                           for q in c['ratios']}
        if len(have) < len(runs):
            c['missing'] = 1 - len(have) / len(runs)
        out[k] = c
    return out


# ------------------------------------------------------------------------------------------------------------ evaluator
class Evaluator:
    """one character's face, measured for any knob set. spec: the resolved spec (charkit.cli.resolve: the manifest and
    refs.fit applied); R: the rig's measures (ref_measure.json); cache: charkit/fit_blender.py's output folder
    (target.npz, env.npz)."""

    def __init__(self, spec, R, cache):
        self.spec0 = copy.deepcopy(spec)
        self.R = R
        self.cache = {}
        tp, ep = os.path.join(cache, 'target.npz'), os.path.join(cache, 'env.npz')
        self.target = None
        if os.path.exists(tp):
            t = np.load(tp)
            self.target = (t['V'], t['T'], t['C'].astype(np.float64))
        self.env, self.env_skin = {}, None
        if os.path.exists(ep):
            e = np.load(ep)
            self.env = {g: (e[g + '_V'], e[g + '_T']) for g in ('hair', 'accessory', 'garment') if g + '_V' in e.files}
            self.env_skin = e['skin_V'] if 'skin_V' in e.files else None
            if self.env_skin is not None and 'garment' in self.env:
                from scipy.spatial import cKDTree
                gv = self.env['garment'][0]
                used = np.unique(self.env['garment'][1])
                d, i = cKDTree(self.env_skin).query(gv[used], k=8)
                w = 1 / np.maximum(d, 1e-5) ** 2
                self._gfollow = (used, i, w / w.sum(1, keepdims=True))
        self._design()
        self._tmaps, self._tcache = {}, {}

    # ---------------------------------------------------------------------------------------------- the design side
    def _design(self):
        ref = self.spec0.get('ref') if isinstance(self.spec0.get('ref'), dict) else {}
        self.D, self.sheet_ppl, self.eye_design = None, None, {}
        sh = ref.get('sheet')
        if sh and ref.get('rig'):
            rgb = _rgba(_path(sh['image']))[..., :3].astype(np.float64)
            rig_alpha = _rgba(os.path.join(_path(ref['rig']), 'base.png'))[..., 3]
            ex = self.spec0.get('eyes', {}).get('x', 0.168)
            self.sheet_ppl = sheetqa.sheet_ppl(rgb, sh['front_figure'], rig_alpha, self.R['ppl'])
            self.D = sheetqa.measure_sheet(rgb, {k: tuple(v) for k, v in sh['heads'].items()}, ex, ppl=self.sheet_ppl)
        if ref.get('rig'):
            for side, layer in (('R', 'eye_L'), ('L', 'eye_R')):
                p = os.path.join(_path(ref['rig']), 'build', layer + '.png')
                if os.path.exists(p):
                    self.eye_design[side] = (_rgba(p), eyeqa.measure(_rgba(p).astype(np.float64), self.R['ppl']))

    # ---------------------------------------------------------------------------------------------- our side
    def prepare(self, spec):
        """the spec as the build's Blender side sees it: the cranium fitted from the generated hair when unset."""
        from . import scene
        S = copy.deepcopy(spec)
        if self.target is not None:
            V, T, C = self.target
            with contextlib.redirect_stdout(io.StringIO()):
                S = scene.fit_cranium(S, ROOT, load=lambda path: (V, None, C))
        return S

    def garments(self, A):
        """the cached garments moved with the skin they were fitted on (the nearest skin vertices' displacement): body
        knobs such as the neck's length and width move the neckline."""
        V, T = self.env['garment']
        if self.env_skin is None or len(self.env_skin) != len(A['verts']):
            return V, T
        used, i, w = self._gfollow
        D = np.asarray(A['verts']) - self.env_skin
        V = V.copy()
        V[used] += (D[i] * w[..., None]).sum(1)
        return V, T

    def geometry(self, spec):
        """-> dict(A (the assembly), skin (V, tris, material per tri), parts, garments (V, tris), target (aligned V, tris,
        colours) or None)."""
        S = self.prepare(spec)
        A = character.assemble(S, keys=False, cache=self.cache)
        G = dict(spec=S, A=A, skin=skin_mesh(A), parts=parts(A), target=None,
                 garments=self.garments(A) if 'garment' in self.env else None)
        if self.target is not None:
            from . import i3d
            V, T, C = self.target
            Hd = A['head']; L = Hd['L']; EK = Hd['eye_knobs']
            shape = S['hair']['shape']
            key = ('eyes',)
            if key not in self._tmaps:
                self._tmaps[key] = i3d.find_eyes(V, C)
            eyes = self._tmaps[key]
            mid = np.array([0.0, Hd['centre'][1] - Hd['H'].df + shape.get('eye_depth', 0.01) * L, Hd['centre'][2] + EK['z'] * L])
            G['target'] = (i3d.align_by_eyes(V, eyes, mid, 2 * EK['x'] * L * shape.get('spacing', 1.0)), T, C)
        return G

    # ---------------------------------------------------------------------------------------------- the measures
    def sheet(self, G, covers=True, jitter=None):
        """the model-sheet checks (charkit.qa3d.sheet's, the same code) -> (O, checks). jitter: sub-pixel offsets (pixels,
        each (x, y, z)) to measure at and average (a smoother objective for the fit than one pixel grid; the QA's own
        grid is offset (0, 0, 0))."""
        if self.D is None:
            return None, {'sheet': {'status': 'SKIPPED', 'why': 'no spec.ref.sheet / rig'}}
        if jitter:
            runs = [self.sheet(G, covers, None) if not any(j) else self.sheet(shifted(G, np.asarray(j) / self.sheet_ppl
                                                                                     * G['A']['head']['L']), covers, None)
                    for j in jitter]
            return runs[0][0], mean_checks([c for _, c in runs])
        CL = sheetqa.CLASS
        A = G['A']; Hd = A['head']; L = Hd['L']
        V, T, fm = G['skin']
        by = np.array([CL['skin'], CL['skin'], CL['line'], CL['line']])
        meshes = [(V, T, by[np.minimum(fm, 3)])]
        P = G['parts']
        cls = {'iris': CL['iris'], 'lash': CL['line'], 'brow': CL['line'], 'sclera': CL['other']}
        for tag in ('L', 'R'):
            for k, c in cls.items():
                v, t, _, _ = P[f'{k}_{tag}']
                meshes.append((v, t, np.full(len(t), c)))
        for nm in ('teeth', 'tongue', 'mouth_line'):
            v, t, _, _ = P[nm]
            meshes.append((v, t, np.full(len(t), CL['line'] if 'line' in nm else CL['other'])))
        cov = []
        for g, c, dst in (('hair', CL['hair'], cov), ('accessory', CL['other'], cov), ('garment', CL['other'], meshes)):
            if g in self.env and len(self.env[g][1]):
                v, t = G['garments'] if g == 'garment' else self.env[g]
                if g != 'garment' and G.get('shift') is not None:
                    v = v + G['shift']
                dst.append((v, t, np.full(len(t), c)))
        irc = [P[f'iris_{t}'][0].mean(0) for t in ('L', 'R')]
        az3 = self.D.get('az_three_quarter', 35.0)
        O = sheetqa.measure_ours(meshes, cov if covers else [], irc, Hd['centre'], L, self.sheet_ppl, az3)
        C = sheetqa.compare(O, self.D)
        if covers:
            C.update(sheetqa.shown(O, self.D))
        return O, C

    def face_shape(self, G, covers=True):
        """the face-shape checks against the generated character (charkit.qa3d.face_shape's) -> (R, checks)."""
        if G['target'] is None:
            return None, {'face_shape': {'status': 'SKIPPED', 'why': 'no generated shape'}}
        A = G['A']; Hd = A['head']; L = Hd['L']
        V, T, fm = G['skin']
        ours = [(V, T, fm <= 1, True)]
        P = G['parts']
        for tag in ('L', 'R'):
            for k in ('sclera', 'iris', 'lash', 'brow'):
                v, t, _, _ = P[f'{k}_{tag}']
                ours.append((v, t, np.zeros(len(t), bool), True))
        for nm in ('teeth', 'tongue', 'mouth_line'):
            v, t, _, _ = P[nm]
            ours.append((v, t, np.zeros(len(t), bool), True))
        if covers:
            for g in ('hair', 'accessory', 'garment'):
                if g in self.env and len(self.env[g][1]):
                    v, t = G['garments'] if g == 'garment' else self.env[g]
                    ours.append((v, t, np.zeros(len(t), bool), False))
        ez = float(np.mean([E['c'][1] for E in A['eyes']]))
        Vb = np.asarray(A['verts'])
        mid = (np.abs(Vb[:, 0]) < 0.01 * L) & (Vb[:, 2] < ez - 0.05 * L) & (Vb[:, 2] > ez - 0.25 * L)
        lm = dict(L=L, eye_z=ez, centre=list(Hd['centre']), mouth_z=float(A['mouth']['c'][1]))
        if mid.any():
            lm['nose_z'] = float(Vb[mid][np.argmin(Vb[mid][:, 1]), 2])
        lm['brow_z'] = float(np.mean([P[f'brow_{t}'][0][:, 2].mean() for t in ('L', 'R')]))
        Rm = faceqa.measure(ours, G['target'], lm, self.R, tcache=self._tcache)
        C = faceqa.checks(Rm)
        return Rm, {('face_shape_' + k if not k.startswith('face_shape') else k): v for k, v in C.items()}

    def eye_image(self, G, side, ss=None):
        """one eye rendered as charkit.qa3d._eye_render renders it: head-on, orthographic, EYE_SIZE L square round the eye
        centre at the rig's scale; the skin and that eye's white, iris and lashes. -> RGBA floats (n, n, 4), row 0 = top."""
        A = G['A']; S = G['spec']; L = A['head']['L']
        SSk = ss or SS
        E = next(E for E in A['eyes'] if (E['side'] > 0) == (side == 'L'))
        n = int(round(EYE_SIZE * self.R['ppl']))
        pix = EYE_SIZE * L / n / SSk
        N = n * SSk
        x0 = E['c'][0] - EYE_SIZE * L / 2; z0 = E['c'][1] + EYE_SIZE * L / 2
        # a render draws the skin at the modifier's render level (2), not the viewport's the other measures read
        key = 'skin2_' + side
        if key not in G:
            m = 0.1 * L
            G[key] = skin_mesh(A, levels=2, box=(x0 - m, x0 + EYE_SIZE * L + m, z0 - EYE_SIZE * L - m, z0 + m))
        V, T, fm = G[key]
        P = G['parts']
        sc, ir, la = P[f'sclera_{side}'], P[f'iris_{side}'], P[f'lash_{side}']
        # (the skin's outline shell isn't drawn: in a render it can hide a lash that lies closer to folded lid skin
        # than its 1.1 mm; see docs/CHARKIT.md, the evaluator's known gaps)
        mesh_list = [(V, T), (sc[0], sc[1]), (ir[0], ir[1]), (la[0], la[1])]
        M, Ti, b1, b2 = raster(mesh_list, x0, z0, pix, N, N)
        IK = S.get('iris')
        skin_c = np.array((S.get('skin') or {}).get('lit', (1.0, 0.90, 0.86)), float)
        mats = np.array([skin_c, skin_c, S.get('cavity_color', (0.38, 0.12, 0.15)), S.get('eyeline_color', (0.22, 0.12, 0.10))],
                        float)
        lash_c = np.array([S.get('lash_color', (0.16, 0.09, 0.10))] * 2 + [S.get('crease_color', (0.78, 0.52, 0.48))], float)
        rgb = np.zeros((N, N, 3)); al = np.zeros((N, N))
        m = M == 0
        rgb[m] = mats[np.minimum(fm[Ti[m]], 3)]; al[m] = 1
        m = M == 3
        rgb[m] = lash_c[la[2][Ti[m]]]; al[m] = 1
        tex_s = eyetex.sclera(IK)
        ir_t = eyetex.iris(IK); sh_t = eyetex.shine(IK)
        a_ = sh_t[..., 3:4]
        tex_i = np.concatenate([ir_t[..., :3] * (1 - a_) + sh_t[..., :3] * a_, np.maximum(ir_t[..., 3:4], a_)], -1)
        for k, (v, t, _, uv) in ((1, sc), (2, ir)):
            m = M == k
            if not m.any():
                continue
            tt = t[Ti[m]]
            w1, w2 = b1[m][:, None], b2[m][:, None]
            u = uv[tt[:, 0]] * (1 - w1 - w2) + uv[tt[:, 1]] * w1 + uv[tt[:, 2]] * w2
            s_rgb = _sample(tex_s, u)[:, :3]
            if k == 1:
                rgb[m] = s_rgb
            else:
                ci = _sample(tex_i, u)
                rgb[m] = ci[:, :3] * ci[:, 3:4] + s_rgb * (1 - ci[:, 3:4])
            al[m] = 1
        img = _blur_down(np.concatenate([rgb * al[..., None], al[..., None]], -1), SSk, FILTER)
        a = img[..., 3:4]
        return np.concatenate([np.where(a > 1e-6, img[..., :3] / np.maximum(a, 1e-6), 0), a], -1)

    def eyes(self, G, ss=None):
        """the eye checks (charkit.qa3d.eyes': each eye against its design layer, the worse eye's status per check);
        ss: the render's supersampling (default SS)."""
        if not self.eye_design:
            return None, {'eye': {'status': 'SKIPPED', 'why': 'no design rig'}}
        table, checks, pics = {}, {}, {}
        for side in ('R', 'L'):
            des_px, md = self.eye_design[side]
            px = self.eye_image(G, side, ss)
            mo = eyeqa.measure(px, self.R['ppl'])
            table[side] = {'ours': {k: v for k, v in mo.items() if not k.startswith('_')},
                           'design': {k: v for k, v in md.items() if not k.startswith('_')}}
            for k, v in eyeqa.compare(mo, md).items():
                prev = checks.get(k)
                if prev is None or STATUS.index(v['status']) > STATUS.index(prev['status']):
                    checks[k] = dict(v, eye=side)
            pics[side] = (px, des_px, mo, md)
        return (table, pics), {'eye_' + k: v for k, v in checks.items()}

    def expressions(self, spec):
        """the checks the build's QA makes from the shape keys, on the numpy assembly with its keys (~3 s): the expression
        geometry (charkit.qa3d.face_from: face_*), the fold count round the openings (qa3d.face_folds), and the sheet's
        expression heads against our expression library (charkit.exprqa: expr_*). -> checks."""
        from . import qa3d
        S = self.prepare(spec)
        A = character.assemble(S, keys=True, cache=self.cache)
        _, fc = qa3d.face_from(A, S, qa3d.key_xz_numpy(A))
        C = {'face_' + k: v for k, v in fc.items()}
        ff = qa3d.face_folds(A)
        C['face_folds'] = {'value': ff['total'], 'rest': ff['rest'], 'per_key': ff['keys'],
                           'status': qa3d._grade('face_folds', ff['total'], False)}
        ctx = self.sheet_context()
        if ctx is not None and ctx['D'].get('expressions'):
            from . import exprqa
            _, ce, _ = exprqa.sheet_run(expression_data(A, S), ctx['rgb'], ctx['D'], ctx['eye_x'])
            C.update(ce)
        return C

    def sheet_context(self):
        """qa3d._sheet_context's picture and detected figures (for the expression heads), once."""
        if getattr(self, '_ctx', None) is None:
            from . import sheetqa
            ref = self.spec0.get('ref') if isinstance(self.spec0.get('ref'), dict) else {}
            sh = ref.get('sheet')
            if not sh or not ref.get('rig'):
                return None
            rgb = _rgba(_path(sh['image']))[..., :3].astype(np.float64)
            ex = self.spec0.get('eyes', {}).get('x', 0.168)
            self._ctx = dict(rgb=rgb, eye_x=ex, D=sheetqa.detect_figures(rgb, ppl=self.sheet_ppl, eye_x=ex,
                                                                          facing=sh.get('facing')))
        return self._ctx

    def run(self, spec, what=('eyes', 'sheet', 'face_shape'), covers=True, jitter=None, ss=None):
        """-> {'checks': {name: check}, 'raw': {'sheet': O, 'face_shape': R, 'eyes': table}, 'geometry': G}."""
        G = self.geometry(spec)
        out = {'checks': {}, 'raw': {}, 'geometry': G}
        if 'eyes' in what:
            r, c = self.eyes(G, ss); out['raw']['eyes'] = r; out['checks'].update(c)
        if 'sheet' in what:
            r, c = self.sheet(G, covers, jitter); out['raw']['sheet'] = r
            out['checks'].update({'sheet_' + k: v for k, v in c.items()})
        if 'face_shape' in what:
            r, c = self.face_shape(G, covers); out['raw']['face_shape'] = r; out['checks'].update(c)
        if 'expressions' in what:
            out['checks'].update(self.expressions(spec))
        return out
