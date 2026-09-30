"""Two builds' pictures and QA compared exactly: each PNG under boards/ and qa/ and the build's sheets (the max and
mean absolute difference per image, 0-255 per channel) and each QA check's value and status (qa/qa.json). Prints
every image and every changed check, and exits 1 on any difference: a change to how the boards render (such as
qa.render_views) must leave both untouched.
    python -m charkit.boarddiff A B
"""
import json, os, sys
import numpy as np


def pngs(d):
    out = [os.path.join(sub, f) for sub in ('boards', 'qa') if os.path.isdir(os.path.join(d, sub))
           for f in sorted(os.listdir(os.path.join(d, sub))) if f.endswith('.png')]
    return out + sorted(f for f in os.listdir(d) if f.startswith('sheet') and f.endswith('.png'))


def image_diff(a, b):
    """-> (max, mean) absolute difference of two PNGs' RGBA pixels; (None, None) if their sizes differ."""
    from PIL import Image
    x, y = (np.asarray(Image.open(p).convert('RGBA'), dtype=np.int16) for p in (a, b))
    if x.shape != y.shape:
        return None, None
    d = np.abs(x - y)
    return int(d.max()), float(d.mean())


def qa_diff(a, b):
    """-> [(check, (value, status) in a, in b)] for each check whose value or status differs."""
    q = []
    for d in (a, b):
        p = os.path.join(d, 'qa', 'qa.json')
        q.append({k: (c.get('value'), c.get('status')) for k, c in json.load(open(p))['checks'].items()}
                 if os.path.exists(p) else {})
    return [(k, q[0].get(k), q[1].get(k)) for k in sorted(set(q[0]) | set(q[1])) if q[0].get(k) != q[1].get(k)]


def main(argv):
    a, b = argv[0], argv[1]
    fa, fb = pngs(a), pngs(b)
    bad = 0
    for f in sorted(set(fa) - set(fb)) + sorted(set(fb) - set(fa)):
        print('%-40s only in %s' % (f, a if f in fa else b)); bad += 1
    for f in (f for f in fa if f in fb):
        mx, mean = image_diff(os.path.join(a, f), os.path.join(b, f))
        if mx is None:
            print('%-40s sizes differ' % f); bad += 1
        else:
            print('%-40s max %3d  mean %.5f' % (f, mx, mean)); bad += mx > 0
    qd = qa_diff(a, b)
    for k, x, y in qd:
        print('qa %-37s %s -> %s' % (k, x, y))
    print('boarddiff: %d images, %d differ; %d QA checks, %d differ' % (
        len(set(fa) & set(fb)), bad, len(json.load(open(os.path.join(a, 'qa', 'qa.json')))['checks'])
        if os.path.exists(os.path.join(a, 'qa', 'qa.json')) else 0, len(qd)))
    return 1 if bad or qd else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
