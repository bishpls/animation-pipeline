"""A build's state log, the way Dolphin's game-state log serves the Melee work: every stage writes what the scene holds after
it, so a bad board traces back to the stage, object and number that made it, and two builds diff to exactly what changed.

    out/trace.jsonl    one JSON record per line: {'t', 'event', 'name', ...}
      begin   the build's environment: git commit, Blender and numpy versions, the spec's path and hash
      stage   after each scene stage: its time, the spec sections it read (hashed), the landmarks, and each object it added,
              changed or removed: counts, world bbox, a geometry hash, mesh health, modifiers, shape keys, materials
      span    a timed sub-step (fit_cranium, a board render, the QA pass)
      note    any value a stage wants on the record (trace.note('hair.parts', kept=3, dropped=12))
      qa      the QA checks
      product a cached build product (the boards, the QA, the VRM): run or restored
      part    a cached part of one (a QA measurement: eyes, sheet, figures, body...): run or restored
      end     the total time
A cached build (charkit/cache.py) adds `cache` to each stage and product record: a hit (restored, `dt` is the restore) or a
miss with the reason (what the stage read that changed); records replayed from a cache entry carry `cached: true`.

Mesh health (`health`, pure numpy, usable outside Blender): open (boundary) edges, non-manifold edges (3+ faces), shells,
degenerate faces, loose verts, and closed shells whose signed volume is negative (inside-out). The evaluated mesh is measured
(modifiers applied) with the inverted-hull outline left off, so the numbers describe the surface that renders.

    python -m charkit trace OUT/trace.jsonl                 # a table per stage
    python -m charkit trace A/trace.jsonl B/trace.jsonl     # what changed between two builds (identical builds: nothing)
    python -m charkit trace A B --no-time                   # ... leaving out stage times (content only: a busy machine)

Inside a build: `trace.begin(path)`, then `with trace.stage('hair', S): ...`, `with trace.span('board', path=p): ...`,
`trace.note(...)`; every call is a no-op when no trace is open, so library code can log freely.
"""
import contextlib, hashlib, json, os, subprocess, sys, time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_T = None                               # the open trace
# measured with these modifiers off: render tricks, not surface (the inverted-hull outline; the mask hiding skin under clothes;
# the skin's shading normals carried from its proxy, charkit.faceshade: they move no vertex, and cost 0.7 s an evaluation)
OUTLINE_MODS = ('outline', 'under_garments', 'proxy_normals')
# parts that are open sheets by design (plates, ribbons, strips, proxies): their open edges are not a fault
SHEETS = ('brow_', 'iris_', 'sclera_', 'lash_', 'mouth_line', 'teeth', 'tongue', 'hair_shape_normals')
HEALTH_FLAGS = ('open_edges', 'nonmanifold_edges', 'inverted_shells', 'degenerate_faces', 'loose_verts')
_HEALTH = {}                            # geometry hash -> health, seeded from a restored stage's own records


def faults(rec):
    """an object record's health faults: {flag: count}, open edges left out for sheets."""
    h = rec.get('health') or {}
    return {k: h[k] for k in HEALTH_FLAGS if h.get(k) and not (k == 'open_edges' and rec.get('sheet'))}

# the spec sections each stage reads (hashed per stage, so a diff names the knobs that moved)
STAGE_KEYS = {
    'character': ('body', 'head', 'head_detail', 'eyes', 'iris', 'brows', 'mouth', 'skin', 'skin_line', 'colors'),
    'hair': ('hair', 'hair_colors', 'accessories'),
    'face_shading': ('skin',),
    'garments': ('garments',),
}


# ------------------------------------------------------------------------------------------------------------ the record
class Trace:
    def __init__(self, path, append=False):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        t_last = 0.0
        if append and os.path.exists(path):
            for line in open(path):
                try:
                    t_last = max(t_last, json.loads(line).get('t', 0.0))
                except ValueError:
                    pass
        self.f = open(path, 'a' if append else 'w')
        self.t0 = time.perf_counter() - t_last          # (appended records continue the build's clock)
        self.prev = {}                  # object name -> its last snapshot (for added / changed / removed)
        self.last = None                # the last stage record
        self.taps = []                  # lists collecting every record written (capture())

    def write(self, event, name=None, **kw):
        rec = {'t': round(time.perf_counter() - self.t0, 4), 'event': event}
        if name is not None:
            rec['name'] = name
        rec.update(kw)
        self.f.write(json.dumps(_plain(rec), separators=(',', ':')) + '\n')
        self.f.flush()
        for tap in self.taps:
            tap.append(rec)
        if event == 'stage':
            self.last = rec
        return rec

    def close(self):
        self.write('end', total=round(time.perf_counter() - self.t0, 3))
        self.f.close()


def begin(path, spec=None, spec_path=None, **env):
    """open a trace at `path` (closing any open one) and write the build's environment."""
    global _T
    if _T is not None:
        _T.close()
    _T = Trace(path)
    info = dict(git=_git(), python=sys.version.split()[0], numpy=np.__version__, spec_path=spec_path,
                spec_hash=_hash_json(spec) if spec is not None else None, **env)
    try:
        import bpy
        info['blender'] = bpy.app.version_string
    except ImportError:
        pass
    _T.write('begin', **info)
    return _T


def resume(path):
    """reopen a build's trace to append to it (the venv's QA after the Blender stage): its records continue the clock,
    and the closing `end` record carries the whole build's time (the Blender stage's `end` stays before it)."""
    global _T
    if _T is not None:
        _T.close()
    _T = Trace(path, append=True)
    return _T


def end():
    global _T
    if _T is not None:
        _T.close()
        _T = None


def active():
    return _T is not None


def last():
    """the last stage record written (None without a trace)."""
    return _T.last if _T is not None else None


@contextlib.contextmanager
def capture():
    """collect the records written inside the block (a cached step replays them on a hit)."""
    got = []
    if _T is not None:
        _T.taps.append(got)
    try:
        yield got
    finally:
        if _T is not None and got in _T.taps:
            _T.taps.remove(got)


def replay(recs, **extra):
    """write captured records again (their own time stamps dropped), each with `extra`."""
    for r in recs:
        if _T is not None:
            kw = {k: v for k, v in r.items() if k not in ('t', 'event', 'name')}
            kw.update(extra)
            _T.write(r['event'], r.get('name'), **kw)


def note(name, **values):
    if _T is not None:
        _T.write('note', name, **values)


def event(kind, name=None, **values):
    if _T is not None:
        _T.write(kind, name, **values)


@contextlib.contextmanager
def span(name, **values):
    """time a sub-step; values given up front, plus any the body adds to the yielded dict."""
    extra = {}
    t = time.perf_counter()
    try:
        yield extra
    finally:
        if _T is not None:
            _T.write('span', name, dt=round(time.perf_counter() - t, 4), **values, **extra)


@contextlib.contextmanager
def stage(name, S=None, objects=None):
    """time a scene stage, then record what it did to the scene: objects added, changed (geometry hash moved) or removed,
    with their stats, the landmarks, and hashes of the spec sections the stage reads."""
    t = time.perf_counter()
    extra = {}
    try:
        yield extra
    finally:
        if _T is not None:
            dt = time.perf_counter() - t
            snap = scene_snapshot(objects, _T.prev, reuse=extra.pop('_reuse', ()))
            added = {k: v for k, v in snap.items() if k not in _T.prev}
            changed = {k: v for k, v in snap.items() if k in _T.prev and (_T.prev[k]['hash'] != v['hash'] or
                                                                           _T.prev[k].get('modifiers') != v.get('modifiers'))}
            removed = sorted(k for k in _T.prev if k not in snap)
            rec = dict(dt=round(dt, 4), added=added, changed=changed, removed=removed, objects=len(snap))
            if S is not None:
                rec['knobs'] = {k: _hash_json(S.spec.get(k)) for k in STAGE_KEYS.get(name, ()) if k in S.spec}
                lm = landmarks(S)
                if lm:
                    rec['landmarks'] = lm
            rec.update(extra)
            _T.write('stage', name, **rec)
            _T.prev = snap


# ------------------------------------------------------------------------------------------------------- mesh health
def _flat(F):
    """faces as (loop verts, starts, counts): a list of index tuples, an (n, k) array, or the flat triple itself."""
    if isinstance(F, tuple) and len(F) == 3 and np.ndim(F[0]) == 1:
        return tuple(np.asarray(a, np.int64) for a in F)
    if isinstance(F, np.ndarray) and F.ndim == 2:
        n, k = F.shape
        return F.ravel().astype(np.int64), np.arange(n, dtype=np.int64) * k, np.full(n, k, np.int64)
    counts = np.array([len(f) for f in F], np.int64)
    starts = np.concatenate([[0], np.cumsum(counts)[:-1]]).astype(np.int64) if len(F) else np.zeros(0, np.int64)
    loopv = np.array([i for f in F for i in f], np.int64)
    return loopv, starts, counts


def _components(n, a, b):
    """connected components of n nodes under edges (a, b): union-find with path halving -> labels (0 .. k-1)."""
    parent = np.arange(n)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for u, v in zip(a.tolist(), b.tolist()):
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[max(ru, rv)] = min(ru, rv)
    roots = np.array([find(i) for i in range(n)])
    _, lab = np.unique(roots, return_inverse=True)
    return lab


def health(V, F, eps_area=1e-12):
    """mesh health of (V (n, 3), F): see the module docstring. -> dict of counts."""
    V = np.asarray(V, float)
    loopv, starts, counts = _flat(F)
    nf = len(counts)
    out = dict(verts=int(len(V)), faces=int(nf))
    if nf == 0:
        out.update(edges=0, open_edges=0, nonmanifold_edges=0, shells=0, closed_shells=0, inverted_shells=0,
                   degenerate_faces=0, loose_verts=int(len(V)))
        return out
    nxt = np.arange(len(loopv)) + 1
    nxt[starts + counts - 1] = starts
    a, b = loopv, loopv[nxt]
    e = np.sort(np.stack([a, b], 1), 1)
    ue, inv, uses = np.unique(e, axis=0, return_inverse=True, return_counts=True)
    inv = inv.ravel()
    used = np.zeros(len(V), bool); used[loopv] = True
    # shells over the used verts
    lab = _components(len(V), ue[:, 0], ue[:, 1])
    face_shell = lab[loopv[starts]]
    shells = np.unique(face_shell)
    # a shell is closed when none of its edges is open
    edge_shell = lab[ue[:, 0]]
    open_sh = set(edge_shell[uses == 1].tolist())
    closed = [s for s in shells.tolist() if s not in open_sh]
    # area vectors (Newell) -> degenerate faces and signed volume per shell
    cr = np.cross(V[a], V[b])
    A = 0.5 * np.add.reduceat(cr, starts, axis=0)
    area = np.linalg.norm(A, axis=1)
    vol = np.einsum('ij,ij->i', V[loopv[starts]], A) / 3.0
    shell_vol = np.bincount(face_shell, weights=vol, minlength=int(lab.max()) + 1)
    inverted = sum(1 for s in closed if shell_vol[s] < 0)
    out.update(edges=int(len(ue)), open_edges=int((uses == 1).sum()), nonmanifold_edges=int((uses > 2).sum()),
               shells=int(len(shells)), closed_shells=len(closed), inverted_shells=int(inverted),
               degenerate_faces=int((area < eps_area).sum()), loose_verts=int((~used).sum()),
               area=round(float(area.sum()), 6))
    return out


def geometry_hash(V, F=None, decimals=5):
    """a short hash of the positions (rounded, so float noise below 10 um doesn't count) and the faces."""
    h = hashlib.sha1(np.round(np.asarray(V, float), decimals).astype(np.float64).tobytes())
    if F is not None:
        loopv, starts, counts = _flat(F)
        h.update(loopv.tobytes()); h.update(counts.tobytes())
    return h.hexdigest()[:12]


# --------------------------------------------------------------------------------------------------- Blender snapshots
_BATCH = [False]                        # inside measuring(): the skip modifiers are already off, the depsgraph current


@contextlib.contextmanager
def measuring(obs, skip=OUTLINE_MODS):
    """the objects' `skip` modifiers off and one depsgraph update for all of them, so mesh_arrays inside needn't toggle and
    re-evaluate object by object (no object's surface depends on another's outline or mask)."""
    import bpy
    off = [m for o in obs if o.type == 'MESH' for m in o.modifiers if m.name in skip and m.show_viewport]
    for m in off:
        m.show_viewport = False
    bpy.context.evaluated_depsgraph_get().update()
    _BATCH[0] = True
    try:
        yield
    finally:
        _BATCH[0] = False
        for m in off:
            m.show_viewport = True


def mesh_arrays(ob, evaluated=True, skip=OUTLINE_MODS, materials=False, uv=None):
    """world-space (V, (loop verts, starts, counts)) of a mesh object; evaluated (modifiers, shape keys at their values)
    with the `skip` modifiers off. materials=True adds each polygon's material index as a third item; uv (a UV layer's
    name) adds each polygon's mean UV ((nf, 2), NaN without the layer) after it."""
    import bpy
    off = []
    if evaluated:
        if not _BATCH[0]:
            for m in ob.modifiers:
                if m.name in skip and m.show_viewport:
                    m.show_viewport = False; off.append(m)
        dg = bpy.context.evaluated_depsgraph_get()
        if not _BATCH[0]:
            dg.update()
        oe = ob.evaluated_get(dg)
        me = oe.to_mesh()
    else:
        me = ob.data
    try:
        n = len(me.vertices)
        co = np.empty(n * 3, np.float64); me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        M = np.array(ob.matrix_world)
        V = co @ M[:3, :3].T + M[:3, 3]
        nf = len(me.polygons)
        starts = np.empty(nf, np.int64); counts = np.empty(nf, np.int64)
        me.polygons.foreach_get('loop_start', starts); me.polygons.foreach_get('loop_total', counts)
        loopv = np.empty(len(me.loops), np.int64); me.loops.foreach_get('vertex_index', loopv)
        if materials:
            mats = np.empty(nf, np.int64); me.polygons.foreach_get('material_index', mats)
        if uv is not None:
            lay = me.uv_layers.get(uv)
            puv = np.full((nf, 2), np.nan)
            if lay is not None and nf:
                luv = np.empty(len(me.loops) * 2, np.float64); lay.data.foreach_get('uv', luv)
                luv = luv.reshape(-1, 2)
                puv = np.add.reduceat(luv, starts, axis=0) / counts[:, None]
    finally:
        if evaluated:
            oe.to_mesh_clear()
            for m in off:
                m.show_viewport = True
    out = (V, (loopv, starts, counts))
    if materials:
        out += (mats,)
    if uv is not None:
        out += (puv,)
    return out


def object_snapshot(ob, prev=None):
    """an object's record; health is only recomputed when its geometry hash moved since `prev`."""
    rec = dict(type=ob.type, parent=ob.parent.name if ob.parent else None, hidden=bool(ob.hide_render))
    if ob.type == 'MESH':
        V, F = mesh_arrays(ob)
        hsh = geometry_hash(V, F)
        hl = prev['health'] if prev and prev.get('hash') == hsh and 'health' in prev else _HEALTH.get(hsh) or health(V, F)
        rec.update(hash=hsh, health=hl, base_verts=len(ob.data.vertices))
        if ob.name.startswith(SHEETS):
            rec['sheet'] = True
        if len(V):
            rec['bbox'] = [np.round(V.min(0), 4).tolist(), np.round(V.max(0), 4).tolist()]
        rec['modifiers'] = [[m.name, m.type] for m in ob.modifiers]
        rec['materials'] = [m.name if m else None for m in ob.data.materials]
        if ob.data.shape_keys:
            rec['shape_keys'] = len(ob.data.shape_keys.key_blocks) - 1
        if ob.vertex_groups:
            rec['vertex_groups'] = len(ob.vertex_groups)
    elif ob.type == 'ARMATURE':
        bones = ob.data.bones
        P = np.array([[*b.head_local, *b.tail_local] for b in bones]) if len(bones) else np.zeros((0, 6))
        rec.update(hash=geometry_hash(P), bones=len(bones))
    else:
        M = np.array(ob.matrix_world)
        rec.update(hash=geometry_hash(M))
    return rec


def seed_health(records):
    """reuse the health of object records already measured (a restored stage's), by geometry hash."""
    for r in records.values():
        if r.get('hash') and r.get('health'):
            _HEALTH[r['hash']] = r['health']


def scene_snapshot(objects=None, prev=None, reuse=()):
    """every object's record; `reuse`: names whose record in `prev` stands (a restored stage left them as they were)."""
    import bpy
    prev = prev or {}
    obs = objects if objects is not None else [o for o in bpy.context.scene.objects if o.type in ('MESH', 'ARMATURE')]
    fresh = [o for o in obs if not (o.name in reuse and o.name in prev)]
    with measuring(fresh):
        snap = {o.name: object_snapshot(o, prev.get(o.name)) for o in fresh}
    return {o.name: snap[o.name] if o.name in snap else prev[o.name] for o in obs}


def landmarks(S):
    """the character's measured landmarks (world metres): head length, eye centres, mouth, chin, crown, the joints."""
    ch = getattr(S, 'character', None)
    if not ch:
        return None
    A = ch['data']; Hd = A['head']; H = Hd['H']; c = np.asarray(Hd['centre'], float)
    lm = dict(L=Hd['L'], centre=c, chin_z=c[2] - H.chin, crown_z=c[2] + H.top, mouth_z=c[2] + H.mouth_z,
              eyes=[list(E['c']) for E in A['eyes']], mouth=list(A['mouth']['c']))
    lm['joints'] = {k: np.round(np.asarray(v, float), 4) for k, v in A['joints'].items()}
    return lm


# ---------------------------------------------------------------------------------------------------------- reading
def read(path):
    return [json.loads(l) for l in open(path) if l.strip()]


def summary(recs):
    """a text table per stage: time, objects, and per object added/changed its verts, faces and health."""
    out = []
    b = next((r for r in recs if r['event'] == 'begin'), {})
    ends = [r for r in recs if r['event'] == 'end']
    out.append('build  git %s  blender %s  spec %s' % (b.get('git'), b.get('blender'), b.get('spec_hash')))
    for r in recs:
        ev = r['event']
        if ev == 'stage':
            out.append('\nstage %-14s %7.2fs  objects %d  (+%d ~%d -%d)%s' % (r['name'], r['dt'], r['objects'], len(r['added']),
                                                                           len(r['changed']), len(r['removed']),
                                                                           _cache_txt(r.get('cache'))))
            for tag, group in (('+', r['added']), ('~', r['changed'])):
                for nm, o in sorted(group.items()):
                    h = o.get('health')
                    if h:
                        flags = ' '.join('%s=%d' % kv for kv in faults(o).items()) + (' (sheet)' if o.get('sheet') else '')
                        out.append('  %s %-26s v%-7d f%-7d shells %-4d %s' % (tag, nm[:26], h['verts'], h['faces'],
                                                                           h['shells'], flags))
                    else:
                        out.append('  %s %-26s %s' % (tag, nm[:26], o['type'].lower()))
            for nm in r['removed']:
                out.append('  - %s' % nm)
        elif ev == 'span':
            vals = {k: v for k, v in r.items() if k not in ('t', 'event', 'name', 'dt', 'cache', 'cached')}
            out.append('span  %-14s %7.2fs  %s%s%s' % (r['name'], r['dt'], json.dumps(vals) if vals else '',
                                                    '  (cached)' if r.get('cached') else '', _cache_txt(r.get('cache'))))
        elif ev in ('product', 'part'):
            out.append('%-5s %-14s %7.2fs%s' % ('prod' if ev == 'product' else ' part', r['name'], r['dt'],
                                                _cache_txt(r.get('cache'))))
        elif ev == 'note':
            vals = {k: v for k, v in r.items() if k not in ('t', 'event', 'name', 'cached')}
            txt = json.dumps(vals)
            out.append('note  %-14s %s' % (r['name'], txt if len(txt) <= 200 else txt[:197] + '...'))
        elif ev == 'qa':
            out.append('\nqa    ' + ', '.join('%s %s (%s)' % (k, v[0], v[1]) for k, v in r.get('checks', {}).items()))
        elif ev == 'end':
            if r is not ends[-1]:                           # the Blender stage's end, before the venv's QA
                out.append('\nblender %.1fs' % r['total'])
                continue
            cs = cache_summary(recs)
            if cs:
                out.append('\n' + cs)
            out.append('\ntotal %.1fs' % r['total'])
    return '\n'.join(out)


def _num_diff(a, b, path, tol, out):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append('%s.%s: %s -> %s' % (path, k, a.get(k, '(none)'), b.get(k, '(none)')))
            else:
                _num_diff(a[k], b[k], '%s.%s' % (path, k), tol, out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        try:
            A, B = np.asarray(a, float), np.asarray(b, float)
            if A.shape == B.shape and np.max(np.abs(A - B), initial=0) > tol:
                out.append('%s: moved %.4f' % (path, float(np.max(np.abs(A - B)))))
            return
        except (TypeError, ValueError):
            pass
        for i, (x, y) in enumerate(zip(a, b)):
            _num_diff(x, y, '%s[%d]' % (path, i), tol, out)
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        if abs(a - b) > tol:
            out.append('%s: %s -> %s' % (path, a, b))
    elif a != b:
        out.append('%s: %s -> %s' % (path, a, b))


def diff(ra, rb, tol=1e-4, time_ratio=1.5):
    """what changed from build A to build B, stage by stage: knob sections, landmarks, per-object geometry and health,
    objects present in one only, stage times that moved by more than `time_ratio`, QA values."""
    out = []
    ba = next((r for r in ra if r['event'] == 'begin'), {}); bb = next((r for r in rb if r['event'] == 'begin'), {})
    for k in ('git', 'blender', 'spec_hash'):
        if ba.get(k) != bb.get(k):
            out.append('build %s: %s -> %s' % (k, ba.get(k), bb.get(k)))
    sa = {r['name']: r for r in ra if r['event'] == 'stage'}
    sb = {r['name']: r for r in rb if r['event'] == 'stage'}
    for name in list(dict.fromkeys(list(sa) + list(sb))):
        a, b = sa.get(name), sb.get(name)
        if a is None or b is None:
            out.append('stage %s only in %s' % (name, 'B' if a is None else 'A'))
            continue
        lines = []
        for k in sorted(set(a.get('knobs', {})) | set(b.get('knobs', {}))):
            if a.get('knobs', {}).get(k) != b.get('knobs', {}).get(k):
                lines.append('knobs %s changed' % k)
        if a.get('landmarks') and b.get('landmarks'):
            la, lb = dict(a['landmarks']), dict(b['landmarks'])
            ja, jb = la.pop('joints', {}) or {}, lb.pop('joints', {}) or {}
            _num_diff(la, lb, 'landmarks', tol, lines)
            moved = {k: float(np.max(np.abs(np.asarray(ja[k], float) - np.asarray(jb[k], float))))
                     for k in set(ja) & set(jb) if np.asarray(ja[k]).shape == np.asarray(jb[k]).shape}
            moved = {k: v for k, v in moved.items() if v > tol}
            if moved:
                k = max(moved, key=moved.get)
                lines.append('landmarks.joints: %d moved, most %s by %.4f' % (len(moved), k, moved[k]))
            for k in sorted(set(ja) ^ set(jb)):
                lines.append('landmarks.joints.%s %s' % (k, 'new in B' if k in jb else 'gone in B'))
        oa = {**a['added'], **a['changed']}; ob = {**b['added'], **b['changed']}
        for nm in sorted(set(oa) | set(ob)):
            x, y = oa.get(nm), ob.get(nm)
            if x is None or y is None:
                lines.append('%s %s' % (nm, 'new in B' if x is None else 'gone in B'))
                continue
            if x['hash'] == y['hash']:
                continue
            sub = []
            _num_diff({k: x.get(k) for k in ('health', 'bbox', 'shape_keys', 'modifiers', 'materials')},
                      {k: y.get(k) for k in ('health', 'bbox', 'shape_keys', 'modifiers', 'materials')}, nm, tol, sub)
            lines += sub or ['%s: geometry moved (same counts and bbox)' % nm]
        restored = (a.get('cache') or {}).get('hit') or (b.get('cache') or {}).get('hit')   # a restore's time isn't the stage's
        if time_ratio and not restored and max(a['dt'], b['dt']) > 0.5 and \
                max(a['dt'], b['dt']) / max(1e-3, min(a['dt'], b['dt'])) > time_ratio:
            lines.append('time %.2fs -> %.2fs' % (a['dt'], b['dt']))
        if lines:
            out.append('stage %s' % name)
            out += ['  ' + l for l in lines]
    qa_a = next((r for r in ra if r['event'] == 'qa'), None); qa_b = next((r for r in rb if r['event'] == 'qa'), None)
    if qa_a and qa_b:
        for k in sorted(set(qa_a['checks']) | set(qa_b['checks'])):
            x, y = qa_a['checks'].get(k), qa_b['checks'].get(k)
            if x != y:
                out.append('qa %s: %s -> %s' % (k, x, y))
    return '\n'.join(out) if out else 'no differences'


def _cache_txt(c):
    if not c:
        return ''
    if c.get('hit'):
        return '  cache hit' + (' (verified)' if c.get('verified') else '')
    why = c.get('why') or ''
    return '  cache miss%s%s' % (': ' + why if why else '', '' if c.get('stored', True) else ' [not stored: %s]' % c.get('uncacheable', '?'))


def cache_summary(recs):
    """one line: the stages and products restored and run, and the time the restores took."""
    rows = [(r['name'], r['cache']) for r in recs if r.get('cache') and r['event'] in ('stage', 'span', 'product', 'part')]
    if not rows:
        return None
    hit = [n for n, c in rows if c.get('hit')]
    miss = ['%s (%s)' % (n, c.get('why') or 'miss') for n, c in rows if not c.get('hit')]
    return 'cache: %d/%d restored%s' % (len(hit), len(rows), ('; ran ' + ', '.join(miss)) if miss else '')


def main(args):
    if not args:
        print(__doc__); return
    files = [a for a in args if not a.startswith('--')]
    if len(files) == 1:
        print(summary(read(files[0])))
    else:
        print(diff(read(files[0]), read(files[1]), time_ratio=None if '--no-time' in args else 1.5))


# ------------------------------------------------------------------------------------------------------------ helpers
def _plain(x):
    if isinstance(x, dict):
        return {str(k): _plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    if isinstance(x, np.ndarray):
        return _plain(np.round(x, 6).tolist())
    if isinstance(x, (np.floating, float)):
        return round(float(x), 6)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def _hash_json(x):
    return hashlib.sha1(json.dumps(_plain(x), sort_keys=True).encode()).hexdigest()[:12]


def _git():
    try:
        c = subprocess.run(['git', '-C', ROOT, 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
        d = subprocess.run(['git', '-C', ROOT, 'status', '--porcelain', '--', 'charkit'], capture_output=True,
                           text=True).stdout.strip()
        return c + ('+dirty' if d else '')
    except OSError:
        return None
