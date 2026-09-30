"""The body fit (charkit.bodypage.save_body: code_body's rings) on two hulls (locality.py's a and b: the same hull
code, the head's sections differing), the rest of the spec held: how far each part's rings move between them.
    python tools/hull_local/bodyfit.py LOCALITY_DIR [...]  -> LOCALITY_DIR/bodyfit.json"""
import contextlib, io, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import numpy as np
from charkit import bodyeval, bodypage, manifest


def fit(spec, hull_dir, out):
    orig = manifest.produced
    manifest.produced = lambda s, rid, log=print: os.path.join(hull_dir, 'hull.glb') if rid == 'hull' else orig(s, rid, log)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            bodypage.save_body(spec, out, log=lambda *a: None)
    finally:
        manifest.produced = orig
    return dict(np.load(out))


def main(dirs):
    spec = bodyeval.resolve('charkit/spec/clawd.json')
    for d in dirs:
        A = fit(spec, os.path.join(d, 'a'), os.path.join(d, 'a', 'body_code.npz'))
        B = fit(spec, os.path.join(d, 'b'), os.path.join(d, 'b', 'body_code.npz'))
        res = {}
        for k in sorted(A):
            if A[k].dtype.kind != 'f' or A[k].shape != B[k].shape:
                continue
            dd = np.abs(A[k] - B[k])
            res[k] = float('%.3g' % dd.max()) if dd.size else 0.0
        if 'torso_P' in A:
            rows = np.abs(A['torso_P'] - B['torso_P']).max(axis=(1, 2))
            res['torso_rows_moved'] = int((rows > 0).sum())
            res['torso_rows'] = int(len(rows))
        json.dump(res, open(os.path.join(d, 'bodyfit.json'), 'w'), indent=1)
        print(d, json.dumps({k: v for k, v in res.items() if not k.endswith(('_s', '_s0'))}))


if __name__ == '__main__':
    main(sys.argv[1:])
