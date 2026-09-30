"""The pilots: garments draped by charkit.sim.xpbd from a build's own products, measured by the build's own QA.

    python -m charkit sim rest BUILD [--out DIR] [--pieces a,b] [--variants NAME=k:v,...]
    python -m charkit sim motion BUILD [--out DIR] [--poses kick,...]

Rest drape: a recorded garment (the build's geom/garments.npz, before finalize) as cloth: its top rows pinned (where
it hangs from: under the band), its rest shape either the template itself ('template': the drawn folds are its rest
angles) or a flat pattern with the template's lengths ('pattern': rest angles 0, the shape left to physics), settled
under gravity against the body, the skirt and the shorts (signed-distance grids from the bundle's meshes). The settled
coarse mesh goes through the build's own finalize (Solidify, Subdivision) into a copy of the bundle, and the build's own
QA parts run on it: the same measurement as the template's (skirtqa's flap and skirt checks in every view, the pieces'
shape IoU in every view, the hems, poke-through).
"""
import json, os, time

import numpy as np

from . import settings as simset, xpbd

QA_PARTS = ('skirt', 'sheet_pieces', 'sheet_body', 'poke')
LOOSE = ('overskirt_panel_L', 'overskirt_panel_R', 'skirt')      # the loose garments the pilots drape


# ------------------------------------------------------------------------------------------------------------ inputs
class Build:
    """a build's products for the pilots: the bundle, the garments' recording (coarse and final), L."""

    def __init__(self, build):
        from .. import bundle as bl, geomstage
        self.path = build
        self.B = bl.load(os.path.join(build, 'bundle'))
        self.L = float(self.B.meta('assembly')['L'])
        self.P = geomstage.load(os.path.join(build, 'geom', 'garments.npz'))
        self.coarse = {o['name']: o for o in geomstage.pieces(self.P, coarse=True)[0]}

    def mesh(self, name, variant='eval'):
        """(V, triangles) of a bundle object's variant."""
        A = self.B._arrays
        k = 'o/%s/%s/' % (name, variant)
        V = np.asarray(A[k + 'V'], float)
        lv, cnt = np.asarray(A[k + 'loopv'], np.int64), np.asarray(A[k + 'counts'], np.int64)
        return V, _fan(lv, cnt)

    def grid(self, names, h, pieces=None):
        """the colliders' signed-distance grid (memoised) over the loose garments' box (the flaps and the skirt, 0.15 L
        round them)."""
        key = (tuple(names), round(h, 9))
        if not hasattr(self, '_grids'):
            self._grids = {}
        if key not in self._grids:
            V = np.concatenate([self.coarse[n]['V'] for n in (pieces or LOOSE) if n in self.coarse])
            box = (V.min(0) - 0.15 * self.L, V.max(0) + 0.15 * self.L)
            self._grids[key] = collider(self, names, box, h)
        return self._grids[key]

    def final(self, name, V_coarse):
        """the finalized mesh (the build's own Solidify and Subdivision at rest) of a garment with its coarse vertices
        moved: -> evalmesh.finalize's dict."""
        from .. import evalmesh
        o = dict(self.coarse[name], V=np.asarray(V_coarse, float))
        return evalmesh.finalize(o)


def _fan(lv, cnt):
    st = np.r_[0, np.cumsum(cnt)[:-1]]
    T = []
    for s, c in zip(st, cnt):
        for j in range(1, c - 1):
            T.append((lv[s], lv[s + j], lv[s + j + 1]))
    return np.asarray(T, np.int64).reshape(-1, 3)


def grid_of(o):
    """a grid-built garment's (rows, columns): its quads join j*NC + i to its neighbours 1 and NC on."""
    d = set()
    for f in o['polys'][:64]:
        f = list(f)
        for a, b in zip(f, f[1:] + f[:1]):
            d.add(abs(int(a) - int(b)))
    NC = max(d)
    if len(o['V']) % NC:
        raise ValueError('%s: not a grid (%d vertices, stride %d)' % (o['name'], len(o['V']), NC))
    return len(o['V']) // NC, NC


def piece_cloth(o, pin_rows=2, rest='template', density=0.2):
    """a grid-built garment as cloth: rows 0..pin_rows-1 pinned (where it hangs from), vertices on no face pinned
    (inert: they ride along untouched). rest 'template': its drawn shape is its rest (lengths and angles); 'pattern':
    its lengths, flat (rest angles 0)."""
    NR, NC = grid_of(o)
    V = np.asarray(o['V'], float)
    used = np.zeros(len(V), bool)
    used[np.concatenate([np.asarray(f, np.int64) for f in o['polys']])] = True
    pins = np.r_[np.arange(pin_rows * NC), np.nonzero(~used)[0]]
    C = xpbd.Cloth(V, o['polys'], pins=pins, density=density)
    if rest == 'pattern':
        C.rest_angle = np.zeros_like(C.rest_angle)
    elif rest != 'template':
        raise ValueError('rest: template or pattern, not %r' % rest)
    row = np.arange(len(V)) // NC
    return C, dict(NR=NR, NC=NC, row=row, used=used)


def collider(Bd, names, box, h):
    """the union (min) of signed-distance grids of closed bundle meshes over a box, spacing h: -> xpbd.SDFGrid. names:
    'object' (eval) or 'object:variant'."""
    G = None
    for n in names:
        obj, var = (n.split(':') + ['eval'])[:2]
        V, T = Bd.mesh(obj, var)
        g = xpbd.SDFGrid.from_mesh(V, T, h, box=box, sign='winding')
        G = g if G is None else xpbd.SDFGrid(np.minimum(G.G, g.G), G.o, G.h)
    return G


# ------------------------------------------------------------------------------------------------------------ rest drape
def rest_drape(Bd, name, style='anime', rest='template', seconds=3.0, fps=60, colliders=('clawd_skin:base', 'skirt',
               'shorts'), grid_h=None, clear=0.004, spacing=0.03, pin_rows=2, log=print, **dials):
    """settle one garment on its cage (charkit.sim.cage, `spacing` L): -> dict(V (the template's vertices, settled),
    stats)."""
    from . import cage as cagelib
    o = Bd.coarse[name]
    L = Bd.L
    K = cagelib.of_piece(o, spacing * L, keep_rows=range(pin_rows))
    nc = len(K.cols)
    pins = np.r_[np.arange(pin_rows * nc), np.nonzero(~K.used)[0]]
    C = xpbd.Cloth(K.V, K.faces, pins=pins)
    rest_from = None
    if rest == 'pattern':
        rest_from, C.rest_angle = C.rest_angle.copy(), np.zeros_like(C.rest_angle)
    elif rest != 'template':
        raise ValueError('rest: template or pattern, not %r' % rest)
    thick = max([abs(float(m['settings'].get('thickness', 0))) for m in o['mods'].values()
                 if m['type'] == 'SOLIDIFY'] or [0.0])
    radius = thick + clear * L
    dials = dict(dict(substeps=10, iterations=10), **dials)
    st = simset.cloth(C, style, L=L, radius=radius, **dials)
    st.update(rest_from=rest_from, rest_ramp=0.5 * seconds)
    S = xpbd.Solver(C, st)
    t0 = time.time()
    G = Bd.grid(tuple(c for c in colliders if c.split(':')[0] != name), grid_h or 0.01 * L)
    tg = time.time() - t0
    S.colliders = [G]
    free = S.w > 0
    V0 = K.carry(C.V)
    used = np.zeros(len(V0), bool)
    used[np.concatenate([np.asarray(f, np.int64) for f in o['polys']])] = True
    NRt, NCt = grid_of(o)
    used &= (np.arange(len(V0)) // NCt) >= pin_rows              # (the template's free vertices)
    d0 = G.distance(V0)
    t0 = time.time()
    steps = int(round(seconds * fps))
    trace = []
    for k in range(steps):
        S.step(1.0 / fps)
        if k % max(1, fps // 5) == 0 or k == steps - 1:
            trace.append(dict(t=round(S.t, 3), vmax_L=float(np.abs(S.v[free]).max() / L)))
    ts = time.time() - t0
    X = K.carry(S.x)
    d = G.distance(X)
    mv = np.linalg.norm(X - o['V'], axis=1)[used] / L
    sn = S.strain()
    stats = dict(piece=name, style=style, rest=rest, dials={k: v for k, v in st['physics'].items()},
                 n=int(len(X)), cage=int(C.n), cage_free=int(free.sum()), cage_edge_L=[float(C.rest_len.min() / L),
                                                                                     float(C.rest_len.max() / L)],
                 radius_L=radius / L, grid_h_L=G.h / L, seconds=seconds, fps=fps, substeps=S.substeps,
                 iterations=S.iterations, rest_carry_L=float(np.abs(V0 - o['V']).max() / L),
                 moved_max_L=float(mv.max()), moved_mean_L=float(mv.mean()),
                 strain_max=float(sn.max()), strain_p99=float(np.percentile(sn, 99)),
                 clear_min_L_before=float(d0[used].min() / L), clear_min_L=float(d[used].min() / L),
                 inside_before=int((d0[used] < 0).sum()), inside=int((d[used] < 0).sum()),
                 settle_vmax_L=trace[-1]['vmax_L'], trace=trace, t_grid=round(tg, 2), t_sim=round(ts, 2))
    log('rest %s %s %s: moved max %.3f L mean %.3f L, cage strain max %.4f p99 %.4f, clear min %.4f L (before %.4f), '
        'inside %d (before %d), v %.2g L/s, %.1f s + grid %.1f s' % (
            name, style, rest, stats['moved_max_L'], stats['moved_mean_L'], stats['strain_max'], stats['strain_p99'],
            stats['clear_min_L'], stats['clear_min_L_before'], stats['inside'], stats['inside_before'],
            stats['settle_vmax_L'], ts, tg))
    return dict(V=X, stats=stats, cage=K, solver=S)


# ------------------------------------------------------------------------------------------------------------ splice + QA
class _Arr:
    def __init__(self, base, rep):
        self.b, self.rep = base, rep
        self.files = list(base.files)

    def __contains__(self, k):
        return k in self.files

    def __getitem__(self, k):
        return self.rep[k] if k in self.rep else self.b[k]


def splice(Bd, moved):
    """a copy of the build's bundle with garments' final meshes moved ({name: coarse V}): the finalized vertices go into
    their eval and raw variants (the same vertex order and faces: finalize is the build's own, M4). -> Bundle."""
    from .. import bundle as bl
    A = Bd.B._arrays
    rep = {}
    for name, Vc in moved.items():
        F = Bd.final(name, Vc)
        for var in ('eval', 'raw'):
            k = 'o/%s/%s/V' % (name, var)
            if k in A.files:
                if len(A[k]) != len(F['V']):
                    raise ValueError('%s %s: %d vertices, finalize gives %d' % (name, var, len(A[k]), len(F['V'])))
                rep[k] = np.asarray(F['V'], A[k].dtype)
    meta = dict(Bd.B._meta)
    meta.pop('content', None); meta.pop('hashes', None)
    return bl.Bundle(meta, _Arr(A, rep), path=None)


def qa(B, parts=QA_PARTS):
    """the build's own QA parts on a bundle (qa3d.evaluate: run()'s check names) -> {check: dict(value, status, ...)}."""
    from .. import qa3d
    C = qa3d.evaluate(B, parts=parts)
    return {k: {x: c.get(x) for x in ('value', 'status', 'per_view', 'views', 'iou', 'why') if x in c}
            for k, c in C.items()}


# ------------------------------------------------------------------------------------------------------------ the pilot
REST_VARIANTS = {                     # name: (style, rest, dials)
    'anime': ('anime', 'template', {}),                                   # the profile as declared: hold 0.8
    'realistic': ('realistic', 'template', {}),                           # hold 0.1, stiffness 0.3
    'physics': ('anime', 'template', dict(hold_shape=0.0)),              # no hold: the drawn shape as rest, gravity
    'pattern': ('anime', 'pattern', dict(hold_shape=0.0)),               # a flat pattern, the template's lengths
    'pattern_soft': ('realistic', 'pattern', dict(hold_shape=0.0)),      # the same, realistic stiffness
}


def pilot_rest(build, out, pieces=('overskirt_panel_L', 'overskirt_panel_R'), variants=None, seconds=5.0, log=print):
    """every variant's drape of the pieces, spliced into the build's bundle and measured by its QA parts: -> the report
    (out/rest.json, out/rest.md), the settled meshes (out/rest_<variant>.npz)."""
    os.makedirs(out, exist_ok=True)
    Bd = Build(build)
    rep = dict(build=build, L=Bd.L, pieces=list(pieces), parts=list(QA_PARTS), variants={})
    t0 = time.time()
    rep['variants']['template'] = dict(checks=qa(Bd.B), stats={})
    log('template QA %.1f s' % (time.time() - t0))
    for vn, (style, rest, dials) in (variants or REST_VARIANTS).items():
        moved, stats = {}, {}
        for n in pieces:
            R = rest_drape(Bd, n, style=style, rest=rest, seconds=seconds, log=log, **dials)
            moved[n] = R['V']
            stats[n] = R['stats']
        np.savez(os.path.join(out, 'rest_%s.npz' % vn), **moved)
        t0 = time.time()
        rep['variants'][vn] = dict(style=style, rest=rest, dials=dials, stats=stats, checks=qa(splice(Bd, moved)))
        log('%s QA %.1f s' % (vn, time.time() - t0))
        json.dump(rep, open(os.path.join(out, 'rest.json'), 'w'), indent=1, default=_js)
    open(os.path.join(out, 'rest.md'), 'w').write(rest_markdown(rep))
    return rep


def _js(o):
    return o.tolist() if hasattr(o, 'tolist') else float(o) if isinstance(o, np.floating) else str(o)


def moved_checks(rep, names=None, pat=None):
    """the checks whose status or value differ between any two variants (or the named / matching ones)."""
    import re
    V = rep['variants']
    keys = list(V['template']['checks'])
    out = []
    for k in keys:
        if names and k not in names:
            continue
        if pat and not re.search(pat, k):
            continue
        vals = [(V[v]['checks'].get(k) or {}).get('value') for v in V]
        sts = [(V[v]['checks'].get(k) or {}).get('status') for v in V]
        if names or len(set(map(str, vals))) > 1 or len(set(sts)) > 1:
            out.append(k)
    return out


def rest_markdown(rep):
    V = rep['variants']
    vs = list(V)
    fmt = lambda c: '—' if not c else ('%s %s' % (('%.4g' % c['value']) if isinstance(c.get('value'), (int, float))
                                                    else c.get('value'), c.get('status')))
    L = ['# Rest drape pilot: the flaps settled by charkit.sim.xpbd against the template', '',
         'Build `%s` (L %.4f m). Each variant drapes %s on its cage, splices the settled meshes into the build\'s bundle '
         '(its own finalize) and runs its QA parts %s. template: the build as it is.' % (
             rep['build'], rep['L'], ', '.join(rep['pieces']), ', '.join(rep['parts'])), '']
    L.append('| variant | style | rest | dials | per piece: moved max / mean (L), cage strain max, clear min (L), '
             'settle speed (L/s) |')
    L.append('|---|---|---|---|---|')
    for v in vs[1:]:
        s = V[v]['stats']
        cells = '<br>'.join('%s: %.3f / %.3f, %.3f, %.4f, %.2g' % (n[-1], x['moved_max_L'], x['moved_mean_L'],
                                                                   x['strain_max'], x['clear_min_L'], x['settle_vmax_L'])
                            for n, x in s.items())
        L.append('| %s | %s | %s | %s | %s |' % (v, V[v]['style'], V[v]['rest'], V[v]['dials'] or '', cells))
    counts = {v: {st: sum(1 for c in V[v]['checks'].values() if c.get('status') == st) for st in ('PASS', 'WARN', 'FAIL')}
              for v in vs}
    L += ['', '| | ' + ' | '.join(vs) + ' |', '|---|' + '---|' * len(vs),
          '| PASS / WARN / FAIL (all %d checks) | ' % len(V['template']['checks']) +
          ' | '.join('%d / %d / %d' % (counts[v]['PASS'], counts[v]['WARN'], counts[v]['FAIL']) for v in vs) + ' |']
    L += ['', '## Checks that move', '', '| check | ' + ' | '.join(vs) + ' |', '|---|' + '---|' * len(vs)]
    for k in moved_checks(rep):
        L.append('| %s | %s |' % (k, ' | '.join(fmt(V[v]['checks'].get(k)) for v in vs)))
    return '\n'.join(L) + '\n'
