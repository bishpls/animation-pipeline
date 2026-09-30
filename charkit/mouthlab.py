"""The mouth's and the expressions' lab (docs/workstreams/mouth.md): a character's mouth keys and combined expressions
measured without Blender, per key:
  - folds    skin faces round the mouth that flip or turn away under the key (qa3d.face_folds);
  - cover    the share of the open mouth's opening that shows its inside, tongue, teeth or lip line (qa3d.mouth_cover;
             skin there is the lips' rings lapped over it, nothing a hole);
  - shape    the drawn mouth as exprqa measures a drawing (width, opening, area, fill, corner lift, wave, skew) and what
             the opening shows: teeth and tongue (shares of it), the line along its top and bottom edges;
  - design   the heads the model sheet draws (the source design idol_D: on Clawd the only drawing of her expressions; the
             manifest gives the expressions no authority, so this is information), matched part by part (exprqa.sheet_run);
and per combined expression (charkit.expressions.PRESETS: the face's components together) its measures against the template's
own targets (exprqa.TARGETS).

    python -m charkit mouth BUILD [--against BUILD2] [--out DIR] [--boards DIR] [--before-boards DIR [--before-label T]]
        a build's bundle -> DIR/mouth.json, DIR/index.html (default BUILD/mouth); --boards: a build's rendered boards
        (preset_*.png, mouth_*.png, expr_*.png) for the contact sheet, at the board's face camera, beside the sheet's
        heads; --before-boards: an earlier build's, its presets beside ours
    python -m charkit mouth --spec RESOLVED.spec.json [--rig-measure ref_measure.json] [--out DIR]
        the same on the spec assembled here (charkit.faceeval's bundle: numpy, no Blender)
    python -m charkit mouth --dump SPEC.json --out HEAD.pkl.gz     (on the build box: the head, a minute; a spec as
        authored is resolved first, into HEAD's folder/resolved)
    python -m charkit mouth --head HEAD.pkl.gz [--set JSON] [--out DIR] [--no-page]
        the loop for mouth.py's shapes and the expression keys: the features re-keyed over the dumped head with this
        checkout's code (a few seconds) and measured; --set lays spec keys over the head's spec ('{"mouth": {...}}')
"""
import html, json, os, sys, time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PPL = 200.0                         # the class renders' px per L (qa3d.mouth_cover's)
# a preset's targets graded with one component swapped for its neighbours: the calibration a new target needs (it
# passes on the shape it asks for, and fails on the rest face and on the shapes it replaces). effort's eye: the
# chevron (Michael, 2026-09-30), against the squeeze it replaces and the other closed eyes
CALIBRATE = {'effort': ('eye', ('chevron', 'squeeze', 'happy', 'blink'))}
CLOSED_EYES = ('blink', 'happy', 'squeeze', 'chevron')     # the lid boards the page sets side by side
BOARD = dict(dist=0.5, lens=85.0, sensor=36.0, px=600, below=0.12)     # scene.boards' preset camera (the face camera)


# ------------------------------------------------------------------------------------------------------------ bundles
def build_bundle(build):
    from . import bundle as bl
    return bl.load(os.path.join(build, 'bundle'))


def spec_bundle(spec_path, R=None, cache=None):
    """the bundle a build of this resolved spec would export for the face (charkit.faceeval.Evaluator.bundle, with the
    shape keys): the mouth's and the expressions' measures in seconds, no Blender."""
    from . import faceeval
    txt = open(spec_path).read()
    import re
    txt = re.sub(r'/srv/work/[^/"]+/', ROOT + '/', txt)                 # (a box build's absolute paths)
    S = json.loads(txt)
    if R is None:
        rp = os.path.join(os.path.dirname(spec_path), 'ref_measure.json')
        R = json.load(open(rp)) if os.path.exists(rp) else None
    E = faceeval.Evaluator(S, R, cache or os.path.join(ROOT, 'charkit', 'out', 'mouthlab', '_nocache'))
    return E.bundle(S, keys=True, eyes=False)


def dump_head(spec_path, out):
    """the placed head a spec builds (charkit.character.geometry: the body, the head, the eyes' margins placed), pickled
    with the spec and the rig's measures: the expression keys are remade over it here in seconds (head_bundle), where the
    head itself takes a minute (the authored body) and its references (the hull) live on the build box."""
    import gzip, pickle
    from . import character
    if not spec_path.endswith('.spec.json'):                 # a spec as authored: resolved first, as a build does
        from . import cli
        d = os.path.join(os.path.dirname(os.path.abspath(out)), 'resolved')
        os.makedirs(d, exist_ok=True)
        spec, spec_path = cli.resolve(spec_path, d)
        spec = cli.code_body(cli.code_head(spec, spec_path, d), spec_path, d)     # (the authored head's and body's files)
    txt = open(spec_path).read()
    import re
    S = json.loads(re.sub(r'/srv/work/[^/"]+/', ROOT + '/', txt))
    rp = os.path.join(os.path.dirname(spec_path), 'ref_measure.json')
    G = character.geometry(S)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with gzip.open(out, 'wb', compresslevel=3) as f:
        pickle.dump(dict(G=G, R=json.load(open(rp)) if os.path.exists(rp) else None), f, protocol=pickle.HIGHEST_PROTOCOL)
    return out


def head_bundle(path, spec_over=None):
    """a dump_head pickle -> the bundle a build of it would export for the face (the features keyed with this checkout's
    eyes, brows and mouth code: charkit.character.features, then charkit.faceeval's bundle pieces), no Blender. spec_over:
    spec keys laid over the dumped spec's (a mouth knob, say)."""
    import gzip, pickle
    from . import bundle as bl, character, faceeval as fe
    with gzip.open(path, 'rb') as f:
        D = pickle.load(f)
    G = dict(D['G'])
    S = dict(G['spec'])
    for k, v in (spec_over or {}).items():
        S[k] = dict(S.get(k) or {}, **v) if isinstance(v, dict) else v
    G['spec'] = S
    A = character.features(G, keys=True)
    b = bl.Builder({k: v for k, v in S.items() if k != '_dir'}, bl.assembly_meta(A, S), D['R'])
    fe.materials(b, S)
    V1, quads, fm = fe.skin_quads(A)
    base, asm = fe.skin_variants(A, True)
    b.add('skin', 'skin', {'eval': dict(V=V1, faces=quads, pmat=fm), 'base': base, 'assembly': asm},
          materials=fe.SKIN_MATS, outline=dict(slot=4, thickness=-fe.SKIN_OUTLINE, offset=1.0))
    fe.features(b, A, S, True)
    B = b.build()
    B.A = A
    return B


# ------------------------------------------------------------------------------------------------------------ measures
def measure(B):
    """-> dict(keys {shape: {folds, cover, skin, none, m (exprqa summary)}}, rest_folds, eye_folds, presets {name: {combo,
    m, targets}}, calibration {preset: {component, variants {name or 'rest': targets grade}}} (CALIBRATE), eyes {closed
    eye: its measures}, neutral, sheet (the drawn heads: table, checks))."""
    from . import exprqa, qa3d
    from .expressions import PRESETS, weights
    data = qa3d.expression_data(B)
    lib = exprqa.library(data)
    ey, ax = exprqa._at(PPL)
    As = qa3d.assembly(B)
    ff = qa3d.face_folds(As)
    cover = qa3d.mouth_cover(B, PPL)
    chin = chin_drop(As)
    on = exprqa.summary(exprqa.measure(exprqa.render(data, {}, PPL), PPL, ey, ax, ours=True))
    keys = {}
    for name in lib['mouth']:
        cls = exprqa.render(data, {'mouth': name}, PPL) if name != 'neutral' else exprqa.render(data, {}, PPL)
        M = exprqa.measure(cls, PPL, ey, ax, ours=True)
        c = cover.get(name) or {}
        keys[name] = dict(folds=ff['keys'].get('mouth_' + name, 0), cover=c.get('cover'), skin=c.get('skin'),
                          none=c.get('none'), chin=chin.get(name, 0.0), m=exprqa.summary(M, on), cls=cls)
    presets = {}
    for name, P in PRESETS.items():
        combo = {k: v for k, v in P.items() if v}
        cls = exprqa.render(data, combo, PPL)
        M = exprqa.measure(cls, PPL, ey, ax, ours=True)
        s = exprqa.summary(M, on)
        presets[name] = dict(combo=combo, m=s, cls=cls, targets=exprqa.grade_targets(name, s, on),
                             folds={k: ff['keys'][k] for k in weights(combo) if k in ff['keys']})
    cal = {}
    for name, (comp, alts) in CALIBRATE.items():
        if name not in PRESETS or not all(a in lib.get(comp, ()) for a in alts):
            continue
        g = {'rest': dict(exprqa.grade_targets(name, on, on), combo={})}
        for a in alts:
            combo = dict({k: v for k, v in PRESETS[name].items() if v}, **{comp: a})
            cls = exprqa.render(data, combo, PPL)
            s = exprqa.summary(exprqa.measure(cls, PPL, ey, ax, ours=True), on)
            g[a] = dict(exprqa.grade_targets(name, s, on), combo=combo, cls=cls, m=s)
        cal[name] = dict(component=comp, variants=g,
                         ok=g[alts[0]]['status'] == 'PASS' and all(g[k]['status'] == 'FAIL' for k in g if k != alts[0]))
    eyes = {}
    for name in CLOSED_EYES:
        if name in lib['eye']:
            cls = exprqa.render(data, {'eye': name}, PPL)
            s = exprqa.summary(exprqa.measure(cls, PPL, ey, ax, ours=True), on)
            eyes[name] = dict(m={k: v for k, v in s.items() if k.startswith('eye_')}, cls=cls,
                              folds=ff['keys'].get('eye_' + name, 0))
    sheet = None
    try:
        D = qa3d.Design(B)
        table, C = qa3d.sheet_expressions(B, D)
        if table:
            sheet = dict(table=table, checks=C)
    except Exception as e:                                                # (a spec with no sheet, no rig measure)
        sheet = dict(error=repr(e))
    return dict(keys=keys, presets=presets, calibration=cal, eyes=eyes, neutral=on, rest_folds=ff['rest'], library=lib,
                eye_folds={k[4:]: v for k, v in ff['keys'].items() if k.startswith('eye_')}, sheet=sheet,
                L=float(B.assembly['L']))


def chin_drop(A):
    """how far each mouth key moves the chin down (L): the skin on the face's midline, in front, from 0.34 to 0.5 L under
    the eye line (the chin, whatever its exact shape), its largest drop. The design's heads keep the face's outline in
    every expression (the mouth opens inside it), so this wants to stay small. -> {shape: L}."""
    V = np.asarray(A['verts'], float); Hd = A['head']; L = Hd['L']; c = np.asarray(Hd['centre'], float)
    q = (V - c) / L
    m = (np.abs(q[:, 0]) < 0.03) & (q[:, 2] < -0.34) & (q[:, 2] > -0.5) & (q[:, 1] < 0)
    return {sh: round(float(max(0.0, -D[m, 2].min() / L)), 4) if m.any() else 0.0
            for sh, D in A['mouth']['keys'].items()}


# ------------------------------------------------------------------------------------------------------------ the proxy
MOUTH_Z = -0.27                   # L under the eye line: where the proxy draws the mouth (Clawd's: the nose's height - 0.11)


def proxy(K, shape, ppl=PPL):
    """a mouth shape drawn flat as the head draws it (charkit.mouth: the opening between the curves, the upper line
    ribbon tucked 60% into it, the lower lip's line, the teeth bands and the tongue), classed on skin on exprqa's face
    window: its measures in milliseconds, for fitting a shape's numbers to a drawing (fit_shape). The head's own render
    (measure) is what grades: the lips there follow these curves (an authored base; MakeHuman's lap over them)."""
    from matplotlib.path import Path
    from . import exprqa, mouth as ml
    L = 1.0
    win = exprqa.WIN
    H = int(round((win['top'] - win['bottom']) * ppl)); W = int(round(2 * win['x'] * ppl))
    yy, xx = np.mgrid[0:H, 0:W]
    pts = np.stack([(xx.ravel() + 0.5) / ppl - win['x'], win['top'] - (yy.ravel() + 0.5) / ppl], 1)
    cls = np.full(H * W, exprqa.CLASS['skin'])
    S = ml._shape(shape)
    up_f, lo_f = ml.curves(K, L, shape)
    t = np.linspace(0, 1, 121)
    xu, zu = up_f(t); xl, zl = lo_f(t)
    off = np.array([0.0, MOUTH_Z])
    poly = lambda P: Path(np.asarray(P) + off).contains_points(pts)
    inside = poly(np.concatenate([np.stack([xu, zu], 1), np.stack([xl, zl], 1)[::-1]]))
    cls[inside] = exprqa.CLASS['mouth']
    g, gmax = ml._opening(K, L, shape, t)
    # the tongue and the teeth (as mouth.tongue and mouth.teeth size them)
    hu = np.minimum(S.get('teeth', K['teeth']) * gmax, 0.85 * g)
    hl = np.minimum(S.get('teeth_lo', 0.0) * gmax, np.maximum(0.85 * g - hu, 0.0))
    tt = (t >= 0.12) & (t <= 0.88)
    arch = np.where(tt, np.sin(np.pi * np.clip((t - 0.12) / 0.76, 0, 1)) ** 0.35, 0.0)
    ht = np.minimum(S.get('tongue', K['tongue']) * gmax * arch, np.maximum(0.9 * g - hu, 0.0))
    if ht.max() > 0:
        cls[inside & poly(np.concatenate([np.stack([xl, zl], 1), np.stack([xl, zl + ht], 1)[::-1]]))] = exprqa.CLASS['tongue']
    tw = (t >= 0.07) & (t <= 0.93)
    if hu.max() > 0:
        cls[inside & poly(np.concatenate([np.stack([xu[tw], zu[tw]], 1), np.stack([xu[tw], zu[tw] - hu[tw]], 1)[::-1]]))] = \
            exprqa.CLASS['white']
    if hl.max() > 0:
        cls[inside & poly(np.concatenate([np.stack([xl[tw], zl[tw]], 1), np.stack([xl[tw], zl[tw] + hl[tw]], 1)[::-1]]))] = \
            exprqa.CLASS['white']
    # the lines: the upper (mouth.line: 60% inside the opening), the lower (line_lo of it as the lips part, 35% inside)
    th = K.get('line_w', 0.0075) * L * (0.35 + 0.65 * np.sin(np.pi * t) ** 0.6)
    part = np.clip(gmax / (0.03 * L), 0.0, 1.0)
    thl = th * (0.15 + (K['line_lo'] - 0.15) * part) * np.sin(np.pi * t) ** 0.5
    for x, z, w, tuck, sign in ((xu, zu, th, 0.6, 1.0), (xl, zl, thl, 0.35, -1.0)):
        P = np.stack([x, z], 1)
        tan = np.gradient(P, axis=0)
        tan /= np.maximum(np.linalg.norm(tan, axis=1, keepdims=True), 1e-12)
        n = np.stack([-tan[:, 1], tan[:, 0]], 1) * sign
        a, b = P - n * (w * tuck)[:, None], P + n * (w * (1 - tuck))[:, None]
        cls[poly(np.concatenate([a, b[::-1]]))] = exprqa.CLASS['line']
    return cls.reshape(H, W)


def proxy_summary(K, shape, ppl=PPL):
    from . import exprqa
    ey, ax = exprqa._at(ppl)
    return exprqa.summary({'eyes': [], 'brows': [], 'mouth': exprqa.mouth(proxy(K, shape, ppl), ppl, ax, ey)})


def design_mouths(B):
    """the source sheet's drawn heads' mouths, measured as exprqa.sheet_run measures them: {head name: dict(s (the
    head's exprqa summary), mask (the drawn mouth filled: its line and what it encloses, at the sheet's scale), ppl)}."""
    from . import exprqa, qa3d
    D = qa3d.Design(B)
    ctx = D.expression_sheet()
    if 'why' in ctx:
        return {}
    heads = ctx['D']['expressions']
    ppl = float(np.median([h['ppl'] for h in heads]))
    ey, ax = exprqa._at(ppl)
    cls_all = exprqa.classes(ctx['rgb'])
    out, seen = {}, {}
    for h in heads:
        M = exprqa.measure(exprqa.crop(cls_all, (h['axis_x'], h['eye_y']), ppl), ppl, ey, ax)
        s = exprqa.summary(M)
        nm = exprqa.name(s)
        seen[nm] = seen.get(nm, 0) + 1
        key = nm if seen[nm] == 1 else '%s%d' % (nm, seen[nm])
        mk = M['mouth'].get('_mask')
        out[key] = dict(s=s, mask=exprqa._fill_holes(mk[0]) if mk else None, ppl=ppl)
    return out


def mask_iou(a, b):
    """two masks' IoU, each placed on its bounding box's centre (the shape, not where it sits) -> 0..1."""
    if a is None or b is None or not a.any() or not b.any():
        return 0.0

    def cut(m):
        ys, xs = np.nonzero(m)
        return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    a, b = cut(a), cut(b)
    H, W = max(a.shape[0], b.shape[0]) + 2, max(a.shape[1], b.shape[1]) + 2

    def pad(m):
        y, x = (H - m.shape[0]) // 2, (W - m.shape[1]) // 2
        o = np.zeros((H, W), bool)
        o[y:y + m.shape[0], x:x + m.shape[1]] = m
        return o
    a, b = pad(a), pad(b)
    return float((a & b).sum() / max(1, (a | b).sum()))


def proxy_mask(K, shape, ppl):
    """the proxy's drawn mouth filled (its line and what it encloses), at ppl."""
    from . import exprqa
    ey, ax = exprqa._at(ppl)
    mo = exprqa.mouth(proxy(K, shape, ppl), ppl, ax, ey)
    return exprqa._fill_holes(mo['_mask'][0]) if mo.get('found') else None


def fit_shape(K, shape, design, free, bounds, keys=('width', 'open', 'area', 'lift', 'fill', 'wave'), ppl=PPL, iters=300,
              mask=None, mask_ppl=None, iou_unit=0.1):
    """a shape's numbers `free` fitted so its proxy measures as the drawing does (design: the drawn head's exprqa
    summary): each measure's miss in exprqa's warn units (LIMITS; fill in 0.1s, wave in 0.005s), squared and summed;
    with the drawn mouth's `mask` (design_mouths, at mask_ppl) the shape's own miss too, (1 - IoU) in iou_units, the
    proxy drawn at the drawing's scale (the mouth is drawn in the front view only: that is every view it has);
    Nelder-Mead inside `bounds` -> (the shape, the summary, the misses (with 'iou': the fitted shape's IoU))."""
    from . import exprqa, mouth as ml
    base = dict(ml._shape(shape))
    unit = {'width': lambda o, d: (o / d - 1) / exprqa.LIMITS['mouth_width'][1],
            'open': lambda o, d: (o - d) / exprqa.LIMITS['mouth_open'][1],
            'area': lambda o, d: (o / max(d, 1e-6) - 1) / exprqa.LIMITS['mouth_area'][1],
            'lift': lambda o, d: (o - d) / exprqa.LIMITS['mouth_lift'][1],
            'fill': lambda o, d: (o - d) / 0.1, 'wave': lambda o, d: (o - d) / 0.005}

    def at(x):
        S = dict(base, **{k: float(np.clip(v, *bounds[k])) for k, v in zip(free, x)})
        return S, proxy_summary(K, S, ppl)

    def cost(x):
        S, o = at(x)
        if 'mouth_width' not in o:
            return 1e3
        c = float(sum(unit[k](o['mouth_' + k], design['mouth_' + k]) ** 2 for k in keys))
        if mask is not None:
            c += ((1.0 - mask_iou(proxy_mask(K, S, mask_ppl), mask)) / iou_unit) ** 2
        return c
    x = np.array([base.get(k, 0.0) for k in free], float)
    n = len(x)
    simplex = [x] + [x + np.eye(n)[i] * max(0.05, 0.15 * abs(x[i])) for i in range(n)]
    f = [cost(v) for v in simplex]
    for _ in range(iters):
        o = np.argsort(f); simplex = [simplex[i] for i in o]; f = [f[i] for i in o]
        c = np.mean(simplex[:-1], 0)
        r = c + (c - simplex[-1]); fr = cost(r)
        if fr < f[0]:
            e = c + 2 * (c - simplex[-1]); fe = cost(e)
            simplex[-1], f[-1] = (e, fe) if fe < fr else (r, fr)
        elif fr < f[-2]:
            simplex[-1], f[-1] = r, fr
        else:
            k = c + 0.5 * (simplex[-1] - c); fk = cost(k)
            if fk < f[-1]:
                simplex[-1], f[-1] = k, fk
            else:
                simplex = [simplex[0]] + [simplex[0] + 0.5 * (v - simplex[0]) for v in simplex[1:]]
                f = [f[0]] + [cost(v) for v in simplex[1:]]
    i = int(np.argmin(f))
    S, o = at(simplex[i])
    miss = {k: round(unit[k](o['mouth_' + k], design['mouth_' + k]), 3) for k in keys}
    if mask is not None:
        miss['iou'] = round(mask_iou(proxy_mask(K, S, mask_ppl), mask), 3)
    return S, o, miss


COLS = ('folds', 'cover', 'chin', 'open', 'width', 'area', 'fill', 'lift', 'teeth', 'tongue', 'line_top', 'line_bottom', 'wave', 'skew')


def row(k):
    m = k['m']
    return dict(folds=k['folds'], cover=k['cover'], chin=k.get('chin'), open=m.get('mouth_open'), width=m.get('mouth_width'),
                area=m.get('mouth_area'), fill=m.get('mouth_fill'), lift=m.get('mouth_lift'), teeth=m.get('mouth_teeth'),
                tongue=m.get('mouth_tongue'), line_top=m.get('mouth_line_top'), line_bottom=m.get('mouth_line_bottom'),
                wave=m.get('mouth_wave'), skew=m.get('mouth_skew'))


def text(M):
    """the per-key and per-expression tables as text."""
    f = lambda v: '-' if v is None else ('%.3f' % v if isinstance(v, float) else str(v))
    out = ['mouth keys (rest folds %d; lengths in L, shares 0..1)' % M['rest_folds'],
           '%-10s ' % 'key' + ' '.join('%8s' % c[:8] for c in COLS)]
    for name, k in M['keys'].items():
        r = row(k)
        out.append('%-10s ' % name + ' '.join('%8s' % f(r[c]) for c in COLS))
    out.append('')
    out.append('expressions (eye, mouth, brow) against the template\'s targets')
    for name, p in M['presets'].items():
        T = p['targets']
        bad = ['%s %s (%s)' % (k, t['status'], f(t['value'])) for k, t in T['features'].items() if t['status'] != 'PASS']
        out.append('%-12s %-5s %-44s %s' % (name, T['status'], json.dumps(p['combo'])[:44], '; '.join(bad)))
    for name, c in (M.get('calibration') or {}).items():
        out.append('')
        out.append('%s\'s targets with its %s swapped (calibration: %s)' % (name, c['component'], 'ok' if c['ok'] else 'NOT ok'))
        for v, g in c['variants'].items():
            fk = g['features'].get('eye_fork', {}).get('value')
            out.append('  %-10s %-5s miss %-6s eye_fork %s' % (v, g['status'], f(g['miss']), f(fk)))
    if M.get('eyes'):
        out.append('')
        out.append('closed eyes: %s' % '; '.join('%s arc %s fork %s folds %s' % (
            n, f(e['m'].get('eye_arc')), f(e['m'].get('eye_fork')), e['folds']) for n, e in M['eyes'].items()))
    if M.get('sheet') and M['sheet'].get('checks'):
        out.append('')
        out.append('the sheet\'s drawn heads (%s; INFO: no authority)' % (M['sheet']['table'] or {}).get('source'))
        for k, c in sorted(M['sheet']['checks'].items()):
            out.append('%-26s %-5s match %-9s dist %s' % (k, c.get('graded_as', c.get('status')), c.get('match'),
                                                            f(c.get('value'))))
    return '\n'.join(out)


def strip(M):
    """M without its pictures, for json."""
    def s(x):
        if isinstance(x, dict):
            return {k: s(v) for k, v in x.items() if k not in ('cls', '_mask')}
        if isinstance(x, (list, tuple)):
            return [s(v) for v in x]
        if isinstance(x, np.generic):
            return x.item()
        return x
    return s(M)


# ------------------------------------------------------------------------------------------------------------ the page
def _rgb(a):
    a = np.asarray(a, float)
    if a.ndim == 3 and a.shape[2] == 4:
        return a[..., :3] * a[..., 3:4] + 0.97 * (1 - a[..., 3:4])
    return a


def board_ppl(L):
    """the preset board's px per L at the face (scene.boards: 600 px square, 85 mm lens on a 36 mm sensor, 0.5 m out)."""
    return BOARD['px'] * BOARD['lens'] / (BOARD['sensor'] * BOARD['dist']) * L


def sheet_heads(B, ppl_out, box=(0.62, 0.55, 0.62)):
    """the source sheet's expression heads cut round their eyes and scaled to ppl_out: [(name, rgb, (eye row, midline
    column))] (the rows of exprqa.sheet_run's table in order). box: (half-width, above the eye line, below it) in L."""
    from PIL import Image
    from . import qa3d
    D = qa3d.Design(B)
    ctx = D.expression_sheet()
    if 'why' in ctx:
        return []
    from .exprqa import summary, measure, crop, classes, name as hname, _at
    out = []
    heads = ctx['D']['expressions']
    ppl = float(np.median([h['ppl'] for h in heads]))
    seen = {}
    for h in heads:
        win = dict(x=box[0], top=box[1], bottom=-box[2])
        c = crop(ctx['rgb'], (h['axis_x'], h['eye_y']), ppl, win=win, fill=1.0)
        cls = crop(classes(ctx['rgb']), (h['axis_x'], h['eye_y']), ppl, win=win)
        ey, ax = _at(ppl, win)
        nm = hname(summary(measure(cls, ppl, ey, ax)))
        seen[nm] = seen.get(nm, 0) + 1
        key = nm if seen[nm] == 1 else '%s%d' % (nm, seen[nm])
        im = Image.fromarray((np.clip(c, 0, 1) * 255).astype(np.uint8))
        s = ppl_out / ppl
        im = im.resize((int(round(im.size[0] * s)), int(round(im.size[1] * s))), Image.LANCZOS)
        out.append((key, np.asarray(im).astype(float) / 255, (box[1] * ppl_out, box[0] * ppl_out)))
    return out


def board_crop(path, L, box=(0.62, 0.55, 0.62)):
    """a preset board cut to the same window round the eyes as sheet_heads (the eye line BOARD['below'] L over the
    board's centre) -> rgb at board_ppl(L)."""
    from PIL import Image
    a = np.asarray(Image.open(path).convert('RGB')).astype(float) / 255
    p = board_ppl(L)
    cy, cx = a.shape[0] / 2 - BOARD['below'] * p, a.shape[1] / 2
    y0, y1 = int(round(cy - box[1] * p)), int(round(cy + box[2] * p))
    x0, x1 = int(round(cx - box[0] * p)), int(round(cx + box[0] * p))
    pad = max(0, -y0, -x0, y1 - a.shape[0], x1 - a.shape[1])
    if pad:
        a = np.pad(a, ((pad, pad), (pad, pad), (0, 0)), constant_values=1.0)
        y0, y1, x0, x1 = y0 + pad, y1 + pad, x0 + pad, x1 + pad
    return a[y0:y1, x0:x1]




def page(M, out, B=None, boards=None, against=None, title='Mouth and expressions', before=None, before_label='before'):
    """the contact sheet: every combined expression as the build's face board draws it (when `boards` has them) beside
    the sheet's drawn head where it draws one, at one scale, with its class render and measures; the closed eyes' lid
    boards side by side, and each calibrated target on its variants (CALIBRATE, first: the preset before and after); then
    every mouth key. before: an earlier build's boards folder, its preset boards set beside ours (before_label names
    it). -> the page's path."""
    from PIL import Image
    from . import exprqa
    img = os.path.join(out, 'img')
    os.makedirs(img, exist_ok=True)

    def save(a, name, h=None):
        im = Image.fromarray((np.clip(_rgb(a), 0, 1) * 255).astype(np.uint8))
        if h and im.size[1] != h:
            im = im.resize((max(1, int(im.size[0] * h / im.size[1])), h), Image.LANCZOS)
        im.save(os.path.join(img, name))
        return 'img/' + name
    f = lambda v: '-' if v is None else ('%.3f' % v if isinstance(v, float) else html.escape(str(v)))
    css = ('body{font:14px/1.45 -apple-system,system-ui,sans-serif;margin:24px;background:#fafafa;color:#222}'
           'h2{font-size:17px;margin:28px 0 6px}.row{display:flex;gap:14px;flex-wrap:wrap;align-items:flex-start}'
           '.card{background:#fff;border:1px solid #ddd;padding:8px;font-size:12px;color:#444;max-width:560px}'
           '.card img{display:block;border:1px solid #eee}.pair{display:flex;gap:6px}.lab{font-size:11px;color:#777}'
           'table{border-collapse:collapse;font-size:12.5px;margin:6px 0}td,th{border:1px solid #ddd;padding:2px 7px;'
           'text-align:right}th{background:#f0f0f0}td:first-child{text-align:left}.PASS{color:#070}.WARN{color:#b60}'
           '.FAIL{color:#c00}.INFO{color:#666}.note{color:#666;font-size:12px;max-width:1100px}')
    L = ['<!doctype html><meta charset="utf-8"><title>%s</title><style>%s</style>' % (html.escape(title), css),
         '<h1>%s</h1>' % html.escape(title)]
    heads = {}
    ppl_b = None
    if B is not None and boards:
        ppl_b = board_ppl(M['L'])
        for key, rgb, _ in sheet_heads(B, ppl_b):
            heads[key] = rgb
    L.append('<p class="note">Each expression: the build\'s face board (the preset camera: 85 mm, 0.5 m, 600 px; %s px '
             'per head length) and, where the model sheet draws that expression, the sheet\'s head (idol_D, the source '
             'design: the only drawing of Clawd\'s expressions; the manifest gives expressions no authority, so it grades '
             'nothing) cut to the same window round the eyes at the same scale. Then the class render the measures read '
             '(skin, line, iris, white, the mouth\'s inside, the tongue pink, brows purple) and the template\'s targets '
             '(exprqa.TARGETS). Folds: skin faces turned or flipped under the key (qa3d.face_folds).</p>'
             % (('%.0f' % ppl_b) if ppl_b else '-'))
    # the focus: each calibrated preset before and after, and its component's variants as the lid boards draw them
    for name, c in (M.get('calibration') or {}).items():
        V = c['variants']
        pics = []
        for d, lab in ((before, before_label), (boards, 'after (this build)')):
            bp = os.path.join(d, 'preset_%s.png' % name) if d else None
            if bp and os.path.exists(bp):
                pics.append((save(board_crop(bp, M['L']), 'focus_%s_%s.png' % (name, lab.split()[0]), 360),
                             '%s: %s' % (lab, html.escape(', '.join('%s %s' % kv for kv in M['presets'][name]['combo'].items())))))
        lids = []
        for v, g in V.items():
            bp = os.path.join(boards, 'expr_%s.png' % v) if boards and v != 'rest' else None
            if bp and os.path.exists(bp):
                a = np.asarray(Image.open(bp).convert('RGB')).astype(float) / 255
                h_, w_ = a.shape[:2]
                fk = g['features'].get('eye_fork', {}).get('value')
                lids.append((save(a[int(0.28 * h_):int(0.72 * h_)], 'focus_lid_%s.png' % v, 180),
                             '%s: %s under %s\'s target (miss %s, eye_fork %s)' % (v, g['status'], name, f(g['miss']), f(fk)),
                             g['status']))
        L.append('<h2>%s: before and after</h2><p class="note">The preset\'s face board before and after (the same camera: '
                 '85 mm, 0.5 m); under it each %s the calibration swaps in, as the expression row draws it (the lid alone '
                 'with its brow, the mouth at rest; one camera: 85 mm, 0.42 m), graded against %s\'s target on the preset '
                 'with that %s. Calibration %s: it passes on the first and fails on the rest face and the others.</p>'
                 '<div class="row">%s</div><div class="row">%s</div>' % (
                     name, c['component'], name, c['component'], 'ok' if c['ok'] else 'NOT ok',
                     ''.join('<div class="card"><img src="%s" height="360"><div class="lab">%s</div></div>' % pc
                             for pc in pics),
                     ''.join('<div class="card"><img src="%s" height="180"><div class="lab"><span class="%s">%s</span>'
                             '</div></div>' % (src, st, html.escape(lab)) for src, lab, st in lids)))
    # the expressions
    L.append('<h2>Expressions</h2><div class="row">')
    A = against or {}
    for name, p in M['presets'].items():
        T = p['targets']
        pics = []
        bb = os.path.join(before, 'preset_%s.png' % name) if before else None
        if bb and os.path.exists(bb):
            pics.append((save(board_crop(bb, M['L']), 'before_%s.png' % name, 300), 'before (board)'))
        bp = os.path.join(boards, 'preset_%s.png' % name) if boards else None
        if bp and os.path.exists(bp):
            pics.append((save(board_crop(bp, M['L']), 'board_%s.png' % name, 300), 'ours (board)'))
        hk = next((k for k, v in exprqa.SHEET_PRESET.items() if v == name and k in heads), None)
        if hk:
            pics.append((save(heads[hk], 'sheet_%s.png' % name, 300), 'sheet: %s head' % hk))
        cls = p['cls']
        crop = cls[int((exprqa.WIN['top'] - 0.3) * PPL) if exprqa.WIN['top'] > 0.3 else 0:int((exprqa.WIN['top'] + 0.62) * PPL), :]
        pics.append((save(exprqa.paint(crop), 'cls_%s.png' % name, 300), 'class render'))
        rows = ''.join('<tr><td>%s</td><td>%s</td><td>%s</td><td class="%s">%s</td></tr>' % (
            k, f(t['value']), html.escape(t['want']), t['status'], t['status']) for k, t in T['features'].items())
        prev = A.get('presets', {}).get(name, {}).get('targets', {}).get('status')
        L.append('<div class="card"><b>%s</b> <span class="%s">%s</span>%s <span class="lab">%s; folds %s</span>'
                 '<div class="pair">%s</div><table><tr><th>feature</th><th>value</th><th>target</th><th></th></tr>%s</table>'
                 '</div>' % (name, T['status'], T['status'], (' (before: %s)' % prev) if prev else '',
                             html.escape(', '.join('%s %s' % kv for kv in p['combo'].items())),
                             ', '.join('%s %s' % kv for kv in p['folds'].items()),
                             ''.join('<div><img src="%s" height="300"><div class="lab">%s</div></div>' % pc for pc in pics),
                             rows))
    L.append('</div>')
    # the closed eyes side by side, and the calibrations
    if M.get('eyes'):
        L.append('<h2>Closed eyes</h2><p class="note">Each lid shape alone (the face board\'s expression row: its brow, '
                 'the mouth at rest) and its class render; arc: (ends - middle) / span, + an arch; fork: the gap between '
                 'its strokes over its outer half, over its span (a &gt; &lt; chevron about 0.3, one stroke about 0); '
                 'folds: skin faces flipped under the key.</p><div class="row">')
        for name, e in M['eyes'].items():
            pics = []
            bp = os.path.join(boards, 'expr_%s.png' % name) if boards else None
            if bp and os.path.exists(bp):
                a = np.asarray(Image.open(bp).convert('RGB')).astype(float) / 255
                h_, w_ = a.shape[:2]
                pics.append((save(a[int(0.3 * h_):int(0.72 * h_), int(0.12 * w_):int(0.88 * w_)], 'lid_%s.png' % name, 150),
                             'board'))
            cls = e['cls']
            y0 = int((exprqa.WIN['top'] - 0.14) * PPL)
            pics.append((save(exprqa.paint(cls[y0:int((exprqa.WIN['top'] + 0.12) * PPL), 30:-30]), 'lidcls_%s.png' % name,
                              150), 'class'))
            L.append('<div class="card"><b>%s</b> arc %s, fork %s, folds %s<div class="pair">%s</div></div>' % (
                name, f(e['m'].get('eye_arc')), f(e['m'].get('eye_fork')), e['folds'],
                ''.join('<div><img src="%s" height="150"><div class="lab">%s</div></div>' % pc for pc in pics)))
        L.append('</div>')
    for name, c in (M.get('calibration') or {}).items():
        L.append('<h2>Calibration: %s\'s targets with its %s swapped</h2><p class="note">A new target passes on the shape '
                 'it asks for (the first) and fails on the rest face and on the shapes it replaces: <b>%s</b>.</p>'
                 '<div class="row">' % (name, c['component'], 'ok' if c['ok'] else 'NOT ok'))
        for v, g in c['variants'].items():
            rows = ''.join('<tr><td>%s</td><td>%s</td><td>%s</td><td class="%s">%s</td></tr>' % (
                k, f(t['value']), html.escape(t['want']), t['status'], t['status']) for k, t in g['features'].items()
                if t['status'] != 'PASS' or k.startswith('eye_'))
            pic = ''
            if g.get('cls') is not None:
                cls = g['cls']
                crop = cls[int((exprqa.WIN['top'] - 0.3) * PPL) if exprqa.WIN['top'] > 0.3 else 0:
                           int((exprqa.WIN['top'] + 0.62) * PPL), :]
                pic = '<img src="%s" height="200">' % save(exprqa.paint(crop), 'cal_%s_%s.png' % (name, v), 200)
            L.append('<div class="card"><b>%s</b> <span class="%s">%s</span> <span class="lab">miss %s</span>%s<table>'
                     '<tr><th>feature</th><th>value</th><th>target</th><th></th></tr>%s</table></div>' % (
                         v, g['status'], g['status'], f(g['miss']), pic, rows))
        L.append('</div>')
    # the keys
    L.append('<h2>Mouth keys</h2><p class="note">Rest folds %d. open, width in L; area L&sup2;; teeth and tongue: shares of '
             'the opening; line_top / line_bottom: shares of the opening\'s columns the line draws along its top / '
             'bottom edge; cover: the share of the opening showing the inside, tongue, teeth or line.%s</p>' % (
                 M['rest_folds'], ' Each cell: this build / before.' if A else ''))
    L.append('<table><tr><th>key</th>%s</tr>' % ''.join('<th>%s</th>' % c for c in COLS))
    for name, k in M['keys'].items():
        r = row(k)
        ra = row(A['keys'][name]) if A.get('keys', {}).get(name) else None
        L.append('<tr><td>%s</td>%s</tr>' % (name, ''.join('<td>%s%s</td>' % (f(r[c]), (' / ' + f(ra[c])) if ra else '')
                                                            for c in COLS)))
    L.append('</table><div class="row">')
    for name, k in M['keys'].items():
        cls = k['cls']
        crop = cls[int((exprqa.WIN['top'] + 0.12) * PPL):int((exprqa.WIN['top'] + 0.62) * PPL), 40:-40]
        pics = [(save(exprqa.paint(crop), 'key_%s.png' % name, 150), 'class')]
        bp = os.path.join(boards, 'mouth_%s.png' % name) if boards else None
        if bp and os.path.exists(bp):
            pics.insert(0, (save(np.asarray(Image.open(bp).convert('RGB')).astype(float)[60:360, 60:540] / 255,
                                 'mboard_%s.png' % name, 150), 'board'))
        L.append('<div class="card"><b>%s</b> folds %s, cover %s<div class="pair">%s</div></div>' % (
            name, k['folds'], f(k['cover']), ''.join('<div><img src="%s" height="150"><div class="lab">%s</div></div>' % pc
                                                     for pc in pics)))
    L.append('</div>')
    # the sheet's heads against the library
    if M.get('sheet') and M['sheet'].get('checks'):
        L.append('<h2>The sheet\'s drawn heads against the library (exprqa.sheet_run; INFO)</h2><table><tr><th>check</th>'
                 '<th>graded as</th><th>match</th><th>distance</th><th>features (ours / design)</th></tr>')
        for k, c in sorted(M['sheet']['checks'].items()):
            fe = '; '.join('%s %s/%s' % (n, f(v.get('ours')), f(v.get('design'))) for n, v in (c.get('features') or {}).items()
                           if n != 'shape' and 'ours' in v)
            st = c.get('graded_as', c.get('status'))
            L.append('<tr><td>%s</td><td class="%s">%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
                k, st, st, c.get('match', ''), f(c.get('value')), html.escape(fe)))
        L.append('</table>')
    p = os.path.join(out, 'index.html')
    open(p, 'w').write('\n'.join(L))
    return p


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return 0
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    t = time.time()
    if '--dump' in args:
        print(dump_head(os.path.abspath(opt('--dump')), os.path.abspath(opt('--out'))))
        print('%.1f s' % (time.time() - t))
        return 0
    if '--head' in args:
        B = head_bundle(os.path.abspath(opt('--head')), json.loads(opt('--set', '{}')))
        out = os.path.abspath(opt('--out', os.path.join(os.path.dirname(os.path.abspath(opt('--head'))), 'mouth')))
    elif '--spec' in args:
        sp = os.path.abspath(opt('--spec'))
        rm = opt('--rig-measure')
        B = spec_bundle(sp, json.load(open(rm)) if rm else None)
        out = os.path.abspath(opt('--out', os.path.join(ROOT, 'charkit', 'out', 'mouthlab')))
    else:
        build = os.path.abspath(args[0])
        B = build_bundle(build)
        out = os.path.abspath(opt('--out', os.path.join(build, 'mouth')))
    M = measure(B)
    os.makedirs(out, exist_ok=True)
    json.dump(strip(M), open(os.path.join(out, 'mouth.json'), 'w'), indent=1, default=str)
    print(text(M))
    A = None
    if opt('--against'):
        a = os.path.abspath(opt('--against'))
        aj = os.path.join(a, 'mouth.json') if os.path.isdir(a) and os.path.exists(os.path.join(a, 'mouth.json')) else a
        A = json.load(open(aj)) if aj.endswith('.json') else strip(measure(build_bundle(a)))
    if '--no-page' not in args:
        print(page(M, out, B, opt('--boards'), A, before=opt('--before-boards'),
                   before_label=opt('--before-label', 'before')))
    print('%.1f s' % (time.time() - t))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
