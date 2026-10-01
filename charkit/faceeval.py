"""The face measured without Blender, in a second or two: our face, eyes and neck for a spec's knobs, and the same graded
checks the build's QA writes (charkit/qa3d.py: eye_*, sheet_*, face_shape_*, face_*, face_folds, expr_*), so
charkit/facefit.py can search the knobs. It makes the geometry bundle a build would export (charkit/bundle.py, in
memory) and measures it with the QA's own functions: the fit's objective is the QA itself.

What a build would make, made here:
  - the skin, eyes and mouth: charkit.character.assemble (without the shape keys unless the expression checks are asked
    for), the body and the wrap's knob-independent part kept between calls (a new head, eye or mouth knob set re-wraps
    the head and re-places the features, ~0.5 s);
  - the skin as Blender evaluates it: its Subdivision Surface modifier (level 1, limit surface, the eye margins creased)
    in numpy (charkit/subdiv.py; within 1 um of Blender's) over the head and neck; level 2 round the eyes for the eye
    renders (a render draws the modifier's render level), pulled in by its outline (SKIN_OUTLINE along the vertex
    normals) with the hull left on the surface, as the solidify outline renders;
  - the cranium from the generated hair (charkit.scene.fit_cranium on the cached arrays);
  - the 3D target (the visual hull) aligned on our eyes as charkit.scene.hair_shape_volume aligns it;
  - the hair, accessories and garments: cached from one Blender build (charkit/fit_blender.py --env), since the face and
    eye knobs don't make them;
  - the eye plates' textures (charkit.eyetex) stored as Blender stores them (bytes), the materials' flat tones from the
    spec's colours.
Everything is measured by charkit.qa3d on that bundle: sheet (qa3d.sheet_measure), face_shape, eyes (qa3d.eye_image,
supersampled like the renderer's pixel filter), and from the keys face, face_folds and the sheet's expression heads.

    from charkit import faceeval
    E = faceeval.Evaluator(resolved_spec, R, cache_dir)       # R: charkit.refs.measure of the rig; cache: fit_blender's
    res = E.run(spec)                                         # {'checks': {name: {value, status, ...}}, 'raw': ...}
"""
import contextlib, copy, io, os

import numpy as np

from . import bundle as bundlelib, character, eyetex, faceqa, qa3d, subdiv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EYE_SIZE = qa3d.EYE_SIZE         # the eye render's window, in L
SS = qa3d.EYE_SS                 # eye render supersampling per pixel side (the fit's coarse passes use 3)
SKIN_OUTLINE = 0.0011            # the skin's outline hull (charkit.scene.stage_character): how far it pulls the skin in
STATUS = qa3d.STATUS
SKIN_MATS = ('skin', 'face_skin', 'cavity', 'eyeline', 'line')


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
def skin_quads(A, below=0.55, levels=1, box=None, carry=None):
    """the skin as Blender evaluates it: the head and neck (from `below` L under the chin up) subdivided like its modifier
    (the eye margins creased): levels 1 as the QA reads meshes (the viewport level), 2 as a render draws it; box: only
    the skin inside (x0, x1, z0, z1) world; carry: per-vertex values (N, k) subdivided alongside (vertex group weights,
    as the modifier carries them). -> (V, quads, per-quad material (0 body, 1 head, 2 mouth cavity, 3 eye line)), and
    the carried values when asked."""
    V = np.asarray(A['verts']); Hd = A['head']; L = Hd['L']
    if carry is not None:
        V = np.concatenate([V, np.asarray(carry, float).reshape(len(V), -1)], 1)
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
    sharp += [(remap[a], remap[b]) for a, b in (A['body'].get('jaw_crease') or ()) if remap[a] >= 0 and remap[b] >= 0]
    V1, quads, parent = subdiv.catmull_clark(Vr, fr, sharp, levels=levels)
    fm = np.asarray(A['fmat'])[fi][parent]
    if carry is not None:
        return V1[:, :3], quads, fm, V1[:, 3:]
    return V1, quads, fm


def skin_mesh(A, below=0.55, levels=1, box=None):
    """skin_quads as triangles (the fan the QA triangulates by) -> (V, tris, per-triangle material)."""
    V1, quads, fm = skin_quads(A, below, levels, box)
    return V1, np.concatenate([quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]]), np.concatenate([fm, fm])


def _shrink(V, quads, w, thick=SKIN_OUTLINE):
    """the outline's pull on a surface (charkit.shade.outline's solidify): each vertex moved inward along its
    (angle-weighted) normal by thick times its outline weight (charkit.character.outline_weights, subdivided)."""
    from .geom.mesh import vertex_normals
    T = np.concatenate([quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]])
    return (-thick * np.asarray(w).reshape(-1, 1) * vertex_normals(V, T)).astype(np.float32)


def materials(b, S):
    """the materials the face's objects use, with the flat tones the build's would render (the spec's colours)."""
    sk = (S.get('skin') or {})
    lit = sk.get('lit', (1.0, 0.90, 0.86))
    b.material('skin', lit=lit, shade=sk.get('shade', (0.95, 0.76, 0.74)), deep=sk.get('deep', (0.84, 0.60, 0.62)), kind='other')
    b.material('face_skin', lit=lit, shade=sk.get('shade', (0.95, 0.76, 0.74)), deep=sk.get('deep', (0.84, 0.60, 0.62)),
               kind='other')
    b.material('cavity', lit=S.get('cavity_color', (0.38, 0.12, 0.15)))
    b.material('eyeline', lit=S.get('eyeline_color', (0.22, 0.12, 0.10)))
    b.material('line', lit=S.get('skin_line', (0.42, 0.24, 0.20)), cull=True)
    b.material('lash', lit=S.get('lash_color', (0.16, 0.09, 0.10)))
    b.material('crease', lit=S.get('crease_color', (0.78, 0.52, 0.48)))
    b.material('brow', lit=S.get('brow_color', (0.30, 0.20, 0.20)))
    b.material('teeth', lit=(0.97, 0.96, 0.97))
    b.material('tongue', lit=(0.86, 0.46, 0.50))
    b.material('mouth_line', lit=S.get('mouth_line_color', (0.36, 0.16, 0.14)))
    IK = S.get('iris')
    ir = eyetex.iris(IK)
    b.image('sclera', eyetex.sclera(IK))
    b.material('sclera', lit=(1, 1, 1), image='sclera', kind='plate')
    # the iris with its shine: one image for both eyes, or the right eye's own when the shine isn't mirrored
    # (character.build_eyes')
    for sd in ((1, -1) if not eyetex._knobs(IK).get('shine_mirror', True) else (1,)):
        sh = eyetex.shine(IK, side=sd)
        a = sh[..., 3:4]
        name = 'iris' if sd > 0 else 'iris_R'
        b.image(name, np.concatenate([ir[..., :3] * (1 - a) + sh[..., :3] * a, np.maximum(ir[..., 3:4], a)], -1))
        b.material(name, lit=(1, 1, 1), image=name, kind='plate')


def features(b, A, S, keys=False):
    """the eye and mouth parts as the build makes them (charkit.character.build_eyes), into a bundle Builder: per side
    the sclera and iris plates (with their UVs), the lash ribbons (materials lash, lash, crease), the brow; the teeth,
    tongue and lip line. keys: their base variants with the expression keys too (the expression checks)."""
    from . import eyes as eyelib
    IK = S.get('iris')
    cz = eyetex._knobs(IK)['cz']
    for E in A['eyes']:
        tag = 'L' if E['side'] > 0 else 'R'
        for k in ('sclera', 'iris'):
            v, f, uv = E[k]
            G = dict(V=v, faces=f, uv=uv)
            var = {'eval': G}
            if keys:
                back = np.zeros((len(v), 3)); back[:, 1] = 0.006
                K = {'eye_' + nm: back for nm in eyelib.CLOSED}
                if k == 'iris':
                    K.update({kn: D for kn, D in (E.get('iris_keys') or {}).items()})
                    K.update({'eye_' + nm: eyelib.iris_scale(v, uv, cz, s_) for nm, s_ in getattr(eyelib, 'IRIS_SCALE', {}).items()})
                var['base'] = dict(G, keys=K)
            own = k == 'iris' and tag == 'R' and not eyetex._knobs(IK).get('shine_mirror', True)
            b.add('%s_%s' % (k, tag), 'eye', var, part=k, side=tag, materials=['iris_R' if own else k])
        lv, lf, lm, off = [], [], [], 0
        for k_, (rv, rq) in enumerate(E['lashes']):
            lv.append(rv); lf += [tuple(i + off for i in q) for q in rq]; lm += [min(k_, 2)] * len(rq); off += len(rv)
        G = dict(V=np.vstack(lv), faces=lf, pmat=lm)
        var = {'eval': G}
        if keys:
            var['base'] = dict(G, keys={'eye_' + nm: np.vstack(E['keys'][nm][1]) for nm in E['keys']})
        b.add('lash_' + tag, 'eye', var, part='lash', side=tag, materials=['lash', 'lash', 'crease'])
        bv, bq = E['brow']
        G = dict(V=bv, faces=bq)
        var = {'eval': G}
        if keys:
            var['base'] = dict(G, keys={'brow_' + k: D for k, D in E['brow_keys'].items()})
        b.add('brow_' + tag, 'eye', var, part='brow', side=tag, materials=['brow'])
    Mo = A['mouth']
    for nm, key, kk in (('teeth', 'teeth', 'teeth_keys'), ('tongue', 'tongue', 'tongue_keys'), ('mouth_line', 'line', 'line_keys')):
        v, q = Mo[key]
        G = dict(V=v, faces=q)
        var = {'eval': G}
        if keys:
            var['base'] = dict(G, keys={'mouth_' + sh: D for sh, D in Mo[kk].items()})
        b.add(nm, 'mouth', var, part=nm, materials=[nm])
    if Mo.get('nose') is not None:                       # the nose's mark (charkit.nose): ink and highlight, no keys
        v, q, sl = Mo['nose']
        b.add('nose', 'mouth', {'eval': dict(V=v, faces=q, pmat=sl)}, part='nose', materials=['nose', 'nose_high'])


def skin_variants(A, keys=True):
    """the skin's base and assembly variants (charkit.bundle's): `base` as Blender holds it (the assembly's vertices in
    float32, each shape key's positions float32(basis + offset), as charkit.character._key writes them), `assembly`
    the assembly's own (float64)."""
    G = dict(bundlelib.assembly_variant(A), exact=True)
    V32 = np.asarray(A['verts'], float).astype(np.float32).astype(np.float64)
    base = dict(V=V32, loopv=G['loopv'], counts=G['counts'], pmat=G['pmat'], exact=True)
    if keys and G['keys']:
        K = {}
        for kn, (idx, D) in G['keys'].items():
            full = np.zeros_like(V32); full[idx] = D
            K[kn] = (V32 + full).astype(np.float32).astype(np.float64) - V32
        base['keys'] = K
    return base, G


def shifted(B, d):
    """the bundle moved rigidly by d (world): the same scene on another pixel grid."""
    return B.moved(d)


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
        self._tmaps, self._tcache, self._design = {}, {}, {}

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

    def bundle(self, spec, keys=False, eyes=True):
        """the bundle a build of this knob set would export for the face's checks (charkit/bundle.py, in memory)."""
        S = self.prepare(spec)
        A = character.assemble(S, keys=keys, cache=self.cache)
        Hd = A['head']; L = Hd['L']
        b = bundlelib.Builder({k: v for k, v in S.items() if k != '_dir'}, bundlelib.assembly_meta(A, S), self.R)
        materials(b, S)
        V1, quads, fm = skin_quads(A)
        base, asm = skin_variants(A, keys)
        variants = {'eval': dict(V=V1, faces=quads, pmat=fm), 'base': base, 'assembly': asm}
        ow = character.outline_weights(A)
        if eyes:
            for E in A['eyes']:
                tag = 'L' if E['side'] > 0 else 'R'
                h = bundlelib.EYE_BOX / 2 + bundlelib.EYE_MARGIN
                box = (E['c'][0] - h * L, E['c'][0] + h * L, E['c'][1] - h * L, E['c'][1] + h * L)
                # (the subdivided region reaches 0.1 L further, so the patch's own surface is the limit surface's)
                Vr, qr, fr, wr = skin_quads(A, levels=2, box=(box[0] - 0.07 * L, box[1] + 0.07 * L, box[2] - 0.07 * L,
                                                              box[3] + 0.07 * L), carry=ow)
                variants['render_eye_' + tag] = dict(V=Vr, faces=qr, pmat=fr, shrink=_shrink(Vr, qr, wr))
        b.add('skin', 'skin', variants, materials=SKIN_MATS, outline=dict(slot=4, thickness=-SKIN_OUTLINE, offset=1.0))
        features(b, A, S, keys)
        for g in ('hair', 'accessory', 'garment'):
            if g in self.env and len(self.env[g][1]):
                v, t = self.garments(A) if g == 'garment' else self.env[g]
                b.add(g + '_env', g, {'eval': dict(V=v, faces=np.asarray(t))})
        if self.target is not None:
            from . import target3d, scene
            V, T, C = self.target
            shape = S['hair']['shape']
            if 'eyes' not in self._tmaps:
                self._tmaps['eyes'] = target3d.find_eyes(V, C)
            eye_mid, spacing = scene.eye_target(A, shape)
            b.target(target3d.align_by_eyes(V, self._tmaps['eyes'], eye_mid, spacing), T, C)
        B = b.build()
        B.A = A
        return B

    def design(self, B):
        """the design side (qa3d.Design) for a bundle of this character, its loaded pictures shared between calls."""
        D = qa3d.Design(B)
        D._m = self._design
        return D

    # ---------------------------------------------------------------------------------------------- the measures
    def sheet(self, B, covers=True, jitter=None):
        """the model-sheet checks (charkit.qa3d.sheet_measure: the QA's own) -> (table, checks). jitter: sub-pixel offsets
        (pixels, each (x, y, z)) to measure at and average (a smoother objective for the fit than one pixel grid; the
        QA's own grid is offset (0, 0, 0))."""
        D = self.design(B)
        got = D.sheet_measures()
        if got is None:
            return None, {'sheet': {'status': 'SKIPPED', 'why': 'no spec.ref.sheet / rig'}}
        if jitter:
            ppl, L = got[1], B.assembly['L']
            runs = [self.sheet(B if not any(j) else B.moved(np.asarray(j) / ppl * L), covers, None) for j in jitter]
            return runs[0][0], mean_checks([c for _, c in runs])
        O, Dm, ppl, az3, C = qa3d.sheet_measure(B, D, covers)
        return O, C

    def face_shape(self, B, covers=True):
        """the face-shape checks against the generated character (charkit.qa3d.face_shape) -> (R, checks)."""
        R, C = qa3d.face_shape(B, self.design(B), None, covers, tcache=self._tcache)
        return R, {('face_shape_' + k if not k.startswith('face_shape') else k): v for k, v in C.items()}

    def eyes(self, B, ss=None):
        """the eye checks (charkit.qa3d.eyes: each eye against its design layer, the worse eye's status per check);
        ss: the render's supersampling (default SS)."""
        table, C = qa3d.eyes(B, self.design(B), None, ss or SS)
        return table, {'eye_' + k: v for k, v in C.items()}

    def expressions(self, spec):
        """the checks the build's QA makes from the shape keys, on the bundle of the assembly with its keys (~3 s): the
        expression geometry (face_*), the fold count round the openings (face_folds), and the sheet's expression heads
        against our expression library (expr_*). -> checks."""
        B = self.bundle(spec, keys=True, eyes=False)
        _, fc = qa3d.face(B)
        C = {'face_' + k: v for k, v in fc.items()}
        C.update(qa3d.folds(B)[1])
        C.update(qa3d.sheet_expressions(B, self.design(B))[1])
        return C

    def run(self, spec, what=('eyes', 'sheet', 'face_shape'), covers=True, jitter=None, ss=None):
        """-> {'checks': {name: check}, 'raw': {'sheet': O, 'face_shape': R, 'eyes': table}, 'geometry': the bundle}."""
        B = self.bundle(spec, eyes='eyes' in what)
        out = {'checks': {}, 'raw': {}, 'geometry': B}
        if 'eyes' in what:
            r, c = self.eyes(B, ss); out['raw']['eyes'] = r; out['checks'].update(c)
        if 'sheet' in what:
            r, c = self.sheet(B, covers, jitter); out['raw']['sheet'] = r
            out['checks'].update({'sheet_' + k: v for k, v in c.items()})
        if 'face_shape' in what:
            r, c = self.face_shape(B, covers); out['raw']['face_shape'] = r; out['checks'].update(c)
        if 'expressions' in what:
            out['checks'].update(self.expressions(spec))
        return out
