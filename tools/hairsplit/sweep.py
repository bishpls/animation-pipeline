"""Parameter variants of the splitter scored against the lock truth, all views, each stage; the views split into a
tuning pair (front, back) and a check pair (three-quarter, profile), so a choice made on one pair is read on the other.

    python tools/hairsplit/sweep.py OUT.json 'NAME:K=V,K=V' ...     (V as JSON)
"""
import json, os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
from charkit import hairsplit as hs, hairlocks as hk
import dev

TUNE, CHECK = ('front', 'back'), ('three_quarter', 'profile')


def pooled(r, views):
    n = sum(r[v]['truth_locks'] for v in views if v in r)
    return round(sum(r[v]['lock_iou'] * r[v]['truth_locks'] for v in views if v in r) / max(1, n), 3)


def run(I, T, params):
    imgs = {}
    for name, V in I['views'].items():
        S = hs.Split(name, V, I['ppl'], params)
        S.pipeline()
        for st, im in (('cells', S.cells), ('tips', S.locks_tips), ('locks', S.locks)):
            imgs.setdefault(st, {})[name] = S.full(im.astype(np.int32))
    out = {}
    for st, x in imgs.items():
        r = hs.score(x, T)
        out[st] = dict(all=r['all']['lock_iou'], tune=pooled(r, TUNE), check=pooled(r, CHECK),
                       views={v: r[v]['lock_iou'] for v in hs.VIEWS},
                       families={f: y['lock_iou'] for f, y in r['all']['families'].items()},
                       view_families={v: {f: y['lock_iou'] for f, y in r[v].get('families', {}).items()}
                                      for v in hs.VIEWS if v in r})
    return out


if __name__ == '__main__':
    a = sys.argv[1:]
    out = a[0]
    I = dev.load_inputs()
    T = hk.load_truth('charkit/refs/clawd/hair_locks_truth.npz')
    res = json.load(open(out)) if os.path.exists(out) else {}
    for spec in a[1:]:
        name, _, kv = spec.partition(':')
        params = {}
        for q in filter(None, kv.split(',')):
            k, v = q.split('=')
            params[k] = json.loads(v)
        t0 = time.time()
        r = run(I, T, params)
        res[name] = dict(params=params, **r)
        x = r['locks']
        print('%-22s locks all %.3f (tune %.3f, check %.3f) | %s | cells %.3f tips %.3f | %s  %.0fs' % (
            name, x['all'], x['tune'], x['check'], ' '.join('%s %.3f' % (v[:5], q) for v, q in x['views'].items()),
            r['cells']['all'], r['tips']['all'], ' '.join('%s %.2f' % (f[:5], q) for f, q in x['families'].items()),
            time.time() - t0))
        print('%-22s back lower %.3f | front lower %s | profile lower %s | bangs %s' % (
            '', x['view_families']['back'].get('lower_back', 0), x['view_families']['front'].get('lower_back'),
            x['view_families']['profile'].get('lower_back'), x['families'].get('bangs')))
        json.dump(res, open(out, 'w'), indent=1)
