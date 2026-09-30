"""The flaps' spring chains as data: each flap (a garment panel with source 'flap') built on the character as the build
builds it (garments.flap on the evaluator's assembly and the hull's pieces), its chain (the joints along its middle
column) carried into the outfit graph's frame (the hull's: L from the eye line, x her left, y toward her back) and
written into the character's outfit notes as the piece's `chain`; the graphs then relayered (outfit.relayer). One owner
per stage: the garments stage shapes the flap and defines its path, the rig stage makes the bones and weights from the
graph's springs (tool/rig), motion simulates them (tool/motion).

    python -m charkit flapchains SPEC [--build DIR]      # DIR: a build of SPEC whose geom/ holds its head and body codes
"""
import json, os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def similarity(X, Y):
    """the similarity taking points X onto their counterparts Y (least squares, Umeyama) -> (s, R, t): Y ~ s R X + t."""
    mx, my = X.mean(0), Y.mean(0)
    Xc, Yc = X - mx, Y - my
    U, S, Vt = np.linalg.svd(Yc.T @ Xc / len(X))
    D = np.eye(3)
    D[2, 2] = np.sign(np.linalg.det(U @ Vt))
    R = U @ D @ Vt
    s = float(np.trace(np.diag(S) @ D) / (Xc ** 2).sum(1).mean())
    return s, R, my - s * R @ mx


def chains(spec_path, build=None):
    """{flap name: joints (L, the graph's frame)} for the spec's flaps, built as the build builds them."""
    from . import bodyeval, garments as gm, i3d, manifest
    from .geom import io as gio
    spec = manifest.resolve(json.load(open(spec_path)))
    geom = os.path.join(build or os.path.join(ROOT, 'charkit', 'out', 'body3'), 'geom')
    spec.setdefault('head_code', os.path.join(geom, 'head_code.npz'))
    spec.setdefault('body_code', os.path.join(geom, 'body_code.npz'))
    E = bodyeval.Evaluator(spec)
    A, _ = E.assembly(E.spec)
    H = gm.hull_pieces(E.spec, A)
    shape = E.spec['hair']['shape']
    path = shape['glb'] if os.path.isabs(shape['glb']) else os.path.join(ROOT, shape['glb'])
    J = json.load(open(path + '.json'))
    V = np.asarray(gio.load(path).V, float)
    eye_mid, spacing = i3d.eye_target(A, shape)
    W = i3d.align_by_eyes(V, (np.asarray(J['eyes'][0], float), np.asarray(J['eyes'][1], float)), eye_mid, spacing)
    s, R, t = similarity(W, V)                              # the world into the hull's frame (the graph's)
    out = {}
    for g in E.spec['garments']:
        if g.get('kind') == 'panel' and g.get('source') == 'flap':
            Jw = np.asarray(gm.flap(A, dict(g, _spec=E.spec), H)['chain']['joints'], float)
            out[g['name']] = [[round(float(x), 3) for x in s * (R @ j) + t] for j in Jw]
    return out


def write(spec_path, C, log=print):
    """the chains into the notes (each piece's own line, the rest of the file as it was), then outfit.relayer."""
    from . import outfit
    spec = json.load(open(spec_path))
    mref = spec['ref']['manifest']
    npath = os.path.join(ROOT, os.path.dirname(mref), 'outfit_notes.json')
    lines = open(npath).read().split('\n')
    for i, ln in enumerate(lines):
        st = ln.strip()
        if not st.startswith('{"id": '):
            continue
        comma = st.endswith(',')
        obj = json.loads(st.rstrip(','))
        if obj['id'] in C:
            obj['chain'] = C[obj['id']]
            lines[i] = ln[:len(ln) - len(ln.lstrip())] + json.dumps(obj, ensure_ascii=False) + (',' if comma else '')
            log('chain', obj['id'], len(C[obj['id']]), 'joints')
    text = '\n'.join(lines)
    json.loads(text)
    open(npath, 'w').write(text)
    return outfit.relayer(spec_path, log=log)


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return
    build = args[args.index('--build') + 1] if '--build' in args else None
    write(args[0], chains(args[0], build))
