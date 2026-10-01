"""the subdivision move (face round 5): charkit/subdiv.py's own Catmull-Clark (pipeline-3d d60486a's, loaded from git)
against the same calls on charkit.geom.subsurf (the evaluator's exact port), on a local assembly of a build's head and
body code: the cage's limit fit (code_base.fit_limit, inside character.assemble), the skin as the QA's eval mesh
(level 1, the eye margins and the jaw's crease creased), faceeval's skin at levels 1 and 2 with the outline weights
carried, and the time each takes.

    python subdiv_lab.py GEOM_DIR [OLD_REF]      # OLD_REF: the commit whose charkit/subdiv.py is the old one (d60486a)
"""
import importlib.util, json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
import numpy as np
from charkit import subdiv as new

import jaw_lab


def old_module(ref):
    src = subprocess.run(['git', '-C', ROOT, 'show', '%s:charkit/subdiv.py' % ref], capture_output=True, text=True,
                         check=True).stdout
    spec = importlib.util.spec_from_loader('subdiv_old', loader=None)
    m = importlib.util.module_from_spec(spec)
    exec(src, m.__dict__)
    return m


def assemble(geom, cc):
    """character.assemble with charkit.subdiv.catmull_clark set to cc -> (assembly, seconds)."""
    from charkit import character, code_base
    keep = new.catmull_clark
    new.catmull_clark = cc
    code_base._HEADS.clear()
    try:
        spec = dict(jaw_lab.spec_of())
        spec['head_code'] = os.path.join(geom, 'head_code.npz')
        spec['body_code'] = os.path.join(geom, 'body_code.npz')
        t0 = time.time()
        A = character.assemble(spec, keys=False)
        return A, time.time() - t0
    finally:
        new.catmull_clark = keep


def stats(a, b):
    d = np.linalg.norm(np.asarray(a)[:, :3] - np.asarray(b)[:, :3], axis=1)
    return dict(max=float(d.max()), mean=float(d.mean()), over_1e4=int((d > 1e-4).sum()), n=len(d))


def main(geom, ref='d60486a'):
    old = old_module(ref)
    out = {}
    Ao, to = assemble(geom, old.catmull_clark)
    An, tn = assemble(geom, new.catmull_clark)
    L = float(An['head']['L'])
    s = stats(np.asarray(Ao['verts']) / L, np.asarray(An['verts']) / L)
    Vo, Vn = np.asarray(Ao['verts']), np.asarray(An['verts'])
    d = np.linalg.norm(Vo - Vn, axis=1) / L
    k = int(np.argmax(d))
    c = np.asarray(An['head']['centre'])
    s['worst_at_L'] = [round(float(x), 4) for x in (Vn[k] - c) / L]
    out['cage_after_limit_fit_L'] = s
    out['assemble_s'] = [round(to, 1), round(tn, 1)]
    from charkit import faceeval
    for lev in (1, 2):
        w = np.linspace(0, 1, len(An['verts']))[:, None] * np.ones((1, 2))       # (a smooth ramp carried)
        rows = {}
        for name, cc in (('old', old.catmull_clark), ('new', new.catmull_clark)):
            keep = faceeval.subdiv.catmull_clark
            faceeval.subdiv.catmull_clark = cc
            try:
                t0 = time.time()
                V1, Q, fm, C = faceeval.skin_quads(An, levels=lev, carry=w)
                rows[name] = (V1, C, time.time() - t0)
            finally:
                faceeval.subdiv.catmull_clark = keep
        V1o, Co, t_o = rows['old']; V1n, Cn, t_n = rows['new']
        dd = np.linalg.norm(V1o - V1n, axis=1) / L
        k = int(np.argmax(dd))
        out['faceeval_level%d' % lev] = dict(max_L=float(dd.max()), mean_L=float(dd.mean()), over_1e4=int((dd > 1e-4).sum()),
                                             worst_at_L=[round(float(x), 4) for x in (V1n[k] - c) / L],
                                             carried_max=float(np.abs(Co - Cn).max()), s=[round(t_o, 2), round(t_n, 2)])
    print(json.dumps(out, indent=1))
    json.dump(out, open(os.path.join(ROOT, 'charkit/out/face5/subdiv_lab.json'), 'w'), indent=1)
    return out


if __name__ == '__main__':
    main(*sys.argv[1:])
