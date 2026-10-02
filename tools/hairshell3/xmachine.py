"""a build's hair pieces step made again here (charkit.cli.pieces_hair on the build's own resolved spec, uncached, with
this machine's produced references: the hull, the hair layers, the split) and compared with the build's: per piece and
per lock (the 'lock' index) whether the vertex and shading-normal arrays are bit-identical, else the max difference.
A box build compared on the laptop is the fit's laptop-vs-box reproducibility (tool/hairshell3).

    python tools/hairshell3/xmachine.py BUILD OUT [--pieces side_lock_L,side_lock_R,lower_back]
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import numpy as np


def main(a):
    build, out = a[0], a[1]
    names = a[a.index('--pieces') + 1].split(',') if '--pieces' in a else ['side_lock_L', 'side_lock_R', 'lower_back']
    from charkit import cli
    from charkit.geom import lockshell
    spec = lockshell._rebase(json.load(open(os.path.join(build, 'clawd.spec.json'))))
    mine = os.path.join(out, 'geom', 'hair_pieces')
    if not os.path.exists(os.path.join(mine, 'pieces.json')):
        cli.pieces_hair(spec, spec, out, mode='off')
    theirs = os.path.join(build, 'geom', 'hair_pieces')
    rep = dict(build=build, pieces={})
    for n in names:
        A, B = np.load(os.path.join(theirs, n + '.npz')), np.load(os.path.join(mine, n + '.npz'))
        r = dict(same_shape=A['V'].shape == B['V'].shape)
        if r['same_shape']:
            r['V_identical'] = bool(np.array_equal(A['V'], B['V']))
            r['vn_identical'] = bool(np.array_equal(A['vn'], B['vn'])) if 'vn' in A.files and 'vn' in B.files else None
            r['V_maxdiff'] = float(np.abs(A['V'] - B['V']).max())
            if 'lock' in A.files and 'lock' in B.files and np.array_equal(A['lock'], B['lock']):
                L = A['lock']
                r['locks'] = {int(k): dict(identical=bool(np.array_equal(A['V'][L == k], B['V'][L == k])),
                                          maxdiff=float(np.abs(A['V'][L == k] - B['V'][L == k]).max()))
                              for k in np.unique(L)}
        rep['pieces'][n] = r
        print(n, json.dumps({k: v for k, v in r.items() if k != 'locks'}),
              'locks identical %s' % (sum(x['identical'] for x in r.get('locks', {}).values()),
                                      len(r.get('locks', {}))), flush=True)
    # the lock shells' fit report, theirs against ours
    ja = json.load(open(os.path.join(theirs, 'pieces.json')))['report'].get('lock_shells') or {}
    jb = json.load(open(os.path.join(mine, 'pieces.json')))['report'].get('lock_shells') or {}
    la = {x['name']: x for x in ja.get('locks', [])}
    lb = {x['name']: x for x in jb.get('locks', [])}
    rep['fit'] = {k: dict(views=[la.get(k, {}).get('views'), lb.get(k, {}).get('views')],
                          cost=[la.get(k, {}).get('cost_px'), lb.get(k, {}).get('cost_px')])
                  for k in sorted(set(la) | set(lb))}
    same = sum(1 for k in rep['fit'] if k in la and k in lb and la[k].get('cost_px') == lb[k].get('cost_px'))
    print('locks fitted: theirs %d, ours %d, same views and costs %d' % (len(la), len(lb), same))
    json.dump(rep, open(os.path.join(out, 'xmachine.json'), 'w'), indent=1)


if __name__ == '__main__':
    main(sys.argv[1:])
