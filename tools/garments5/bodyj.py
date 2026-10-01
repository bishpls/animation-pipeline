"""The joined shoulder built from a spec's body without Blender: the body data (code_body.build_body_data) on a build's
resolved spec with body.shoulder overridden, checked (topology, weights), measured against the base body reference
(shm.measure_labels; the build's own head from its bundle) and posed (the upper arm raised 90 deg forward and out to the
side by linear blend skinning on the body's own weights and joints).

    python tools/garments5/bodyj.py BUILD VARIANTS.json [--out DIR] [--only a,b]
VARIANTS.json: {name: {"body.shoulder": {...} | null, "body.KEY": ...}}; a null name value: the build's own body.
"""
import sys, os, json, copy, math
sys.path.insert(0, '.')
sys.path.insert(0, os.path.join('tools', 'garments5'))
import numpy as np

from charkit import bundle, qa3d, bodyqa, bodypage, code_body, code_base
from charkit.faceqa import zbuffer
import shm

ARM_BONES = ('UpperArm', 'LowerArm', 'Hand')
PIVOT = 0.18                       # L up the upper arm's line: the posed check's second pivot (the deltoid's centre)


def score(M):
    """one number for the fit: the mean over front and back, both sides, of the top line's (loose) and the outer
    edge's rms, and the profile arm's front and back rms (L)."""
    v = []
    for view in ('front', 'back'):
        for sd in ('left', 'right'):
            rr = M['views'].get(view, {}).get(sd)
            if rr:
                v += [rr['top_loose'].get('rms', 1.0), rr['outer'].get('rms', 1.0)]
    pr = M['views'].get('profile', {})
    v += [pr.get('arm_front', {}).get('rms', 1.0), pr.get('arm_back', {}).get('rms', 1.0)]
    return round(float(np.mean(v)), 4)


def setp(spec, path, v):
    p = path.split('.')
    x = spec
    for q in p[:-1]:
        x = x.setdefault(q, {})
    if v is None:
        x.pop(p[-1], None)
    else:
        x[p[-1]] = v


def body_data(spec, npz):
    bodypage.save_body(spec, npz, log=lambda *a: None)
    sp = dict(spec, body_code=npz)
    chin = code_base.head_sections(sp)[1]['chin']
    return code_body.build_body_data(sp, chin, log=lambda *a: None)


def tris(F):
    T = []
    for f in F:
        for k in range(1, len(f) - 1):
            T.append((f[0], f[k], f[k + 1]))
    return np.array(T, int)


def topology(Bd):
    """edges by use, components, winding, weights."""
    F = Bd['faces']
    E = {}
    for f in F:
        for k in range(len(f)):
            a, b = int(f[k]), int(f[(k + 1) % len(f)])
            E.setdefault((min(a, b), max(a, b)), []).append(1 if a < b else -1)
    boundary = sum(1 for v in E.values() if len(v) == 1)
    nonman = sum(1 for v in E.values() if len(v) > 2)
    flipped = sum(1 for v in E.values() if len(v) == 2 and v[0] == v[1])
    n = len(Bd['verts'])
    par = np.arange(n)

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    for (a, b) in E:
        ra, rb = find(a), find(b)
        if ra != rb:
            par[ra] = rb
    roots = np.array([find(i) for i in range(n)])
    used = np.zeros(n, bool)
    for f in F:
        used[list(f)] = True
    comps = len(set(roots[used]))
    parts = Bd['parts']
    t0 = parts['torso'][0]
    torso_comp = {k: bool(roots[v[0]] == roots[t0]) for k, v in parts.items() if k.startswith(('arm_', 'shoulder_'))}
    Wsum = sum(Bd['weights'].values())
    return dict(boundary_edges=boundary, nonmanifold_edges=nonman, flipped_edges=flipped, components=comps,
                joined_to_torso=torso_comp, loose_verts=int((~used).sum()),
                weight_sum=[round(float(Wsum[used].min()), 6), round(float(Wsum[used].max()), 6)],
                weight_neg=int(sum((w < -1e-9).sum() for w in Bd['weights'].values())))


def labels(Bd, Bk, cut_z):
    """our skin for the views: the body data's triangles (torso, legs, feet: TORSO; arms, bridges, hands: ARM) and the
    build's head (its skin's triangles above the cut)."""
    V = np.asarray(Bd['verts'], float)
    T = tris(Bd['faces'])
    lab = np.full(len(V), shm.TORSO)
    for k, (a, b) in Bd['parts'].items():
        if k.startswith(('arm_', 'shoulder_', 'hand_')):
            lab[a:b] = shm.ARM
    tl = np.where((lab[T] == shm.ARM).sum(1) >= 2, shm.ARM, shm.TORSO)
    Vh, Th, _, _ = Bk.skin().mesh('eval')
    Vh, Th = np.asarray(Vh, float), np.asarray(Th)
    hk = (Vh[Th][:, :, 2] > cut_z).all(1)
    return [(V, T, tl), (Vh, Th[hk], np.full(int(hk.sum()), shm.HEAD))]


def views(meshes, Bk, D):
    ctx = D.sheet_context()
    iris = np.array(qa3d.iris_centres(Bk))
    az = bodyqa.azimuths(ctx['az3'])
    out = {}
    for v in shm.VIEWS:
        org = bodyqa.origin(v, az[v], iris, Bk.assembly['centre'])
        out[v] = zbuffer(meshes, az[v], org, Bk.assembly['L'], 1.0 / ctx['ppl'], bodyqa.WIN)[1]
    return out


def rot(a, b):
    """the rotation taking unit a onto unit b."""
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    v, c = np.cross(a, b), float(a @ b)
    if np.linalg.norm(v) < 1e-9:
        return np.eye(3)
    K = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + K + K @ K * (1 / (1 + c))


def pose(Bd, side, target, clav=0.0, pivot=0.0):
    """the arm on a side raised so its upper arm points along `target` (world), the clavicle turned `clav` of the way
    with it about its own head: linear blend skinning -> posed verts. pivot: the shoulder joint moved this far (L) up
    the upper arm's line (the 2D rig's joint sits ~0.16 L under the deltoid's centre)."""
    V = np.asarray(Bd['verts'], float)
    J = Bd['joints']
    S = 'L' if side == 'left' else 'R'
    p = np.asarray(J['shoulder01.%s____head' % S], float)
    e = np.asarray(J['lowerarm01.%s____head' % S], float)
    if pivot:
        p = p - (e - p) / np.linalg.norm(e - p) * pivot * float(Bd['head_len'])
    R = rot(e - p, np.asarray(target, float))
    W = Bd['weights']
    w_arm = sum(W.get(side + b, 0) for b in ARM_BONES)
    fing = [b for b in W if b.startswith(side) and any(k in b for k in ('Thumb', 'Index', 'Middle', 'Ring', 'Little'))]
    w_arm = w_arm + sum(W[b] for b in fing)
    out = V + np.asarray(w_arm)[:, None] * ((V - p) @ R.T + p - V)
    if clav:
        c = np.asarray(J['clavicle.%s____head' % S], float)
        ang = math.acos(np.clip(((e - p) / np.linalg.norm(e - p)) @ (np.asarray(target) / np.linalg.norm(target)), -1, 1))
        ax = np.cross(e - p, target)
        ax /= np.linalg.norm(ax)
        a = clav * ang
        K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
        Rc = np.eye(3) + math.sin(a) * K + (1 - math.cos(a)) * K @ K
        w_c = np.asarray(W.get(side + 'Shoulder', np.zeros(len(V)))) + np.asarray(w_arm)
        out = out + np.clip(w_c, 0, 1)[:, None] * ((out - c) @ Rc.T + c - out)
    return out


def region(Bd, side, L):
    """the shoulder's region: the bridge, the arm's top 0.3 L, the torso within 0.25 L of the arm's head."""
    J = Bd['joints']
    S = 'L' if side == 'left' else 'R'
    p = np.asarray(J['shoulder01.%s____head' % S], float)
    V = np.asarray(Bd['verts'], float)
    m = np.linalg.norm(V - p, axis=1) < 0.45 * L
    return m


def posed_measures(Bd, P, side, L, rest_T):
    """edge stretch and face flips over the shoulder's region; arm vertices inside the torso's rest volume."""
    V = np.asarray(Bd['verts'], float)
    m = region(Bd, side, L)
    E = set()
    for f in Bd['faces']:
        for k in range(len(f)):
            a, b = int(f[k]), int(f[(k + 1) % len(f)])
            if m[a] and m[b]:
                E.add((min(a, b), max(a, b)))
    E = np.array(sorted(E))
    l0 = np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1)
    l1 = np.linalg.norm(P[E[:, 0]] - P[E[:, 1]], axis=1)
    r = l1 / np.maximum(l0, 1e-12)
    T = rest_T[m[rest_T].all(1)]
    n0 = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    n1 = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
    a0 = np.linalg.norm(n0, axis=1); a1 = np.linalg.norm(n1, axis=1)
    # (a face whose posed normal turned more than 120 degrees from where its rigid part would carry it reads folded)
    return dict(edges=int(len(E)), stretch_p1=round(float(np.percentile(r, 1)), 3), stretch_p99=round(float(np.percentile(r, 99)), 3),
                stretch_min=round(float(r.min()), 3), stretch_max=round(float(r.max()), 3),
                area_min=round(float((a1 / np.maximum(a0, 1e-12)).min()), 3),
                area_p1=round(float(np.percentile(a1 / np.maximum(a0, 1e-12), 1)), 3))


def inside_torso(Bd, P, side, Z, L, Oz):
    """posed arm/bridge vertices inside the rest torso (its radial field; L from the build's frame): count and depth."""
    a_, b_ = Bd['parts']['arm_' + side]
    idx = list(range(a_, b_))
    if 'shoulder_' + side in Bd['parts']:
        s0, s1 = Bd['parts']['shoulder_' + side]
        idx += list(range(s0, s1))
    idx = np.array(idx)
    Q = (P[idx] - np.array([0, 0, Oz])) / L                  # (the hull's frame: x, y as is, z from the eye line)
    zt = Z['torso_z']
    Tp = Z['torso_P']
    cy = Z['torso_cy']
    depth = []
    for q in Q:
        if q[2] > zt[0] or q[2] < zt[-1]:
            continue
        i = int(np.argmin(np.abs(zt - q[2])))
        ring = Tp[i]
        c = np.array([0.0, cy[i]])
        a = math.atan2(q[0] - c[0], -(q[1] - c[1]))
        ra = np.arctan2(ring[:, 0] - c[0], -(ring[:, 1] - c[1]))
        rr = np.hypot(ring[:, 0] - c[0], ring[:, 1] - c[1])
        o = np.argsort(ra)
        R = np.interp(a, ra[o], rr[o], period=2 * np.pi)
        d = R - math.hypot(q[0] - c[0], q[1] - c[1])
        if d > 0.01:
            depth.append(d)
    return dict(n=len(depth), max=round(float(max(depth)), 4) if depth else 0.0)


def png(path, rows, D, bb):
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from skimage import measure as skm
    W = bodyqa.WIN
    ppl = D.sheet_context()['ppl']
    vs = ('front', 'profile', 'back')
    fig, ax = plt.subplots(len(rows), len(vs) + 2, figsize=(4.2 * (len(vs) + 2), 4.6 * len(rows)), squeeze=False)
    for r, R in enumerate(rows):
        for j, v in enumerate(vs):
            r0, r1 = shm.rc(-0.25, 0, ppl)[0], shm.rc(-1.45, 0, ppl)[0]
            c0, c1 = shm.rc(0, -1.0, ppl)[1], shm.rc(0, 1.0, ppl)[1]
            ref, cls = bb[v]['fg'][r0:r1, c0:c1], bb[v]['cls'][r0:r1, c0:c1]
            im = np.ones(ref.shape + (3,))
            im[ref] = (0.72, 0.72, 0.76)
            im[ref & (cls == bodyqa.CLASS['skin'])] = (0.96, 0.84, 0.74)
            im[ref & (cls == bodyqa.CLASS['hair'])] = (0.95, 0.65, 0.45)
            ext = [c0 / ppl - W['x'], c1 / ppl - W['x'], W['top'] - r1 / ppl, W['top'] - r0 / ppl]
            ax[r, j].imshow(im, extent=ext)
            lab = R['labels'][v][r0:r1, c0:c1]
            for m, ls, col in ((lab >= 0, '-', 'tab:blue'), (lab == shm.ARM, ':', 'tab:red')):
                for C in skm.find_contours(np.pad(m, 1).astype(float), 0.5):
                    C = C - 1
                    ax[r, j].plot(C[:, 1] / ppl + ext[0], ext[3] - C[:, 0] / ppl, ls, color=col, lw=1.0)
            ax[r, j].set_title('%s %s' % (R['name'], v), fontsize=9)
            ax[r, j].set_aspect('equal')
        # the posed meshes (front: the forward raise from the side; the side raise from the front)
        for q, (key, a, b) in enumerate((('pose_side', 0, 2), ('pose_front', 1, 2))):
            P = R.get(key + '_V')
            if P is None:
                continue
            T = R['T']
            m = R['region']
            T2 = T[m[T].any(1)]
            axx = ax[r, len(vs) + q]
            axx.triplot(P[:, a], P[:, 2], T2, lw=0.15, color='k')
            axx.set_aspect('equal')
            axx.set_title('%s %s (%s)' % (R['name'], key, R.get(key, {})), fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=100)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    opt = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
    out = opt('--out', 'charkit/out/garments5/bodyj')
    only = opt('--only')
    args = [a for a in args if a not in (out, only)]
    build, var = args[0], json.load(open(args[1]))
    os.makedirs(out, exist_ok=True)
    Bk = bundle.load(build + '/bundle')
    D = qa3d.Design(Bk)
    bb = shm.bb_views(D)
    spec0 = json.load(open(os.path.join(build, 'clawd.spec.json')))
    res, rows = {}, []
    for name, ov in var.items():
        if only and name not in only.split(','):
            continue
        spec = copy.deepcopy(spec0)
        for k, v in (ov or {}).items():
            setp(spec, k, v)
        npz = os.path.join(out, name + '_body_code.npz')
        try:
            Bd = body_data(spec, npz)
        except Exception as ex:                                      # (a variant the template can't build)
            import traceback; traceback.print_exc()
            res[name] = dict(error=repr(ex)); print(name, 'ERROR', ex); continue
        L = float(Bd['head_len'])
        Z = np.load(npz)
        Oz = float(np.mean(np.asarray(Bd['verts'])[Bd['neck_ring'], 2])) - code_body.CUT * L
        cut_z = Oz + (code_body.CUT + 0.005) * L
        lab = views(labels(Bd, Bk, cut_z), Bk, D)
        M = shm.measure_labels(D, lab, name)
        top = topology(Bd)
        T = tris(Bd['faces'])
        rec = dict(topology=top, views={k: v for k, v in M['views'].items()}, n_verts=len(Bd['verts']))
        R = dict(name=name, labels=lab, T=T)
        for side in ('left',):
            for key, tgt, pv in (('pose_side', (1.0, 0.0, 0.0), 0.0), ('pose_front', (0.0, -1.0, 0.0), 0.0),
                                 ('pose_side_pivot', (1.0, 0.0, 0.0), PIVOT), ('pose_front_pivot', (0.0, -1.0, 0.0), PIVOT)):
                P = pose(Bd, side, tgt, pivot=pv)
                pm = posed_measures(Bd, P, side, L, T)
                pm['inside'] = inside_torso(Bd, P, side, Z, L, Oz)
                Pc = pose(Bd, side, tgt, clav=0.25, pivot=pv)
                pm['with_clavicle_25pc'] = dict(posed_measures(Bd, Pc, side, L, T), inside=inside_torso(Bd, Pc, side, Z, L, Oz))
                rec[key] = pm
                R[key] = dict(st=[pm['stretch_min'], pm['stretch_max']], inside=pm['inside']['n'])
                R[key + '_V'] = P
            R['region'] = region(Bd, 'left', L)
        rest_in = inside_torso(Bd, np.asarray(Bd['verts'], float), 'left', Z, L, Oz)
        rec['rest_inside'] = rest_in
        res[name] = rec
        rows.append(R)
        print('==', name, 'verts', len(Bd['verts']), 'topology', top)
        print('   rest: arm/bridge inside the torso', rest_in)
        for v, q in M['views'].items():
            for s in ('left', 'right'):
                rr = q.get(s)
                if rr:
                    print('   %-13s %-5s top %s outer %s point %s/%s axilla %s/%s' % (
                        v, s, rr['top_loose'].get('rms'), rr['outer'].get('rms'), rr['point_ours'], rr['point_ref'],
                        rr['axilla_ours'], rr['axilla_ref']))
                    print('       top z (ours, ref) %s' % rr['st_top'])
                    print('       outer x (ours, ref) %s' % rr['st_out'])
            if v == 'profile':
                print('   profile arm front %s back %s' % (q['arm_front'], q['arm_back']))
        for key in ('pose_side', 'pose_front', 'pose_side_pivot', 'pose_front_pivot'):
            print('   %s %s' % (key, rec[key]))
        rec['score'] = score(M)
        fl = M['views']['front']['left']
        print('SUMMARY %-10s score %.4f | front L top %s outer %s point %s axilla %s | stretch side %s/%s front %s/%s | pivot side %s/%s front %s/%s' % (
            name, rec['score'], fl['top_loose'].get('rms'), fl['outer'].get('rms'), fl['point_ours'], fl['axilla_ours'],
            rec['pose_side']['stretch_min'], rec['pose_side']['stretch_max'], rec['pose_front']['stretch_min'],
            rec['pose_front']['stretch_max'], rec['pose_side_pivot']['stretch_min'], rec['pose_side_pivot']['stretch_max'],
            rec['pose_front_pivot']['stretch_min'], rec['pose_front_pivot']['stretch_max']))
    json.dump(res, open(os.path.join(out, 'bodyj.json'), 'w'), indent=1, default=str)
    if rows:
        best = sorted(rows, key=lambda R: res[R['name']]['score'])
        png(os.path.join(out, 'bodyj.png'), best[:4], D, bb)


if __name__ == '__main__':
    main()
