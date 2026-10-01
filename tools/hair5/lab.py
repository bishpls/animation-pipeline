"""Hair round 5's lab: hairlab's context over a build once, then variants (hairpieces.build's opts and style
overrides) rebuilt venv-side and measured: the hair flags (charkit.hairflagqa), the hair pieces' checks with every
family's shape IoU per view (qa3d.hair_pieces_measure), the builder's folds, and optionally hair_noise.

    python tools/hair5/lab.py BUILD OUT.json 'name|{"opts": {...}, "style": {...}}' ... [--noise] [--save DIR]
"""
import json, os, sys, time
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from charkit import hairlab, hairflagqa as hf, qa3d

FLAGS = ('hair_ahoge_shape', 'hair_ahoge_bend', 'hair_attached', 'hair_back_lines', 'hair_back_hem',
         'hair_lock_lines_three_quarter', 'hair_lock_lines_profile')
SHAPES = ['hair_piece_' + f for f in qa3d.HAIR_FAMILIES] + ['hair_bun_outline', 'hair_folds', 'hair_tips_back',
                                                            'hair_fringe_low', 'hair_penetration']


def measure(ctx, hair, R=None, noise=False):
    B, D = ctx['B'], ctx['D']
    _, Cq = qa3d.hair_pieces_measure(B, D, {n: (vt, vt) for n, vt in hair.items()})
    Dd, ppl = hf.design_inputs(B, D)
    ours, pieces = hf.our_labels(B, D, hair)
    _, Cf = hf.measure_labels(ours, pieces, Dd, ppl)
    out = {k: {a: b for a, b in c.items() if a in ('value', 'status', 'views', 'tips', 'worst', 'p', 'r', 'per_piece',
                                                     'ours', 'design', 'wave_L', 'detached')}
           for k, c in list(Cf.items()) + list(Cq.items()) if k in FLAGS or k in SHAPES}
    if R is not None:
        out['folds_builder'] = {n: r.get('folds', 0) for n, r in R['report']['pieces'].items()}
    if noise and R is not None:
        out['hair_noise_lab'] = hairlab.noise(ctx, R)[0]
    return out, ours, pieces


def show(name, m):
    f = lambda k: m.get(k, {}).get('value')
    v = lambda k: m.get(k, {}).get('views')
    print('%-18s ahoge %s/%s att %s back %s hem %s locks %s/%s | ahoge IoU %s fly %s upper %s lower %s side %s bangs %s '
          'buns %s outline %s folds %s noise %s' % (
              name, f('hair_ahoge_shape'), f('hair_ahoge_bend'), f('hair_attached'), f('hair_back_lines'),
              f('hair_back_hem'), f('hair_lock_lines_three_quarter'), f('hair_lock_lines_profile'),
              v('hair_piece_ahoge'), v('hair_piece_flyaways'), f('hair_piece_upper_back'), f('hair_piece_lower_back'),
              f('hair_piece_side_locks'), f('hair_piece_bangs'), f('hair_piece_buns'), f('hair_bun_outline'),
              f('hair_folds'), m.get('hair_noise_lab')))


if __name__ == '__main__':
    a = sys.argv[1:]
    noise = '--noise' in a
    save = a[a.index('--save') + 1] if '--save' in a else None
    a = [x for i, x in enumerate(a) if x != '--noise' and x != '--save' and (i == 0 or a[i - 1] != '--save')]
    build, out = a[0], a[1]
    t0 = time.time()
    ctx = hairlab.context(build)
    print('context %.0f s' % (time.time() - t0))
    res = {}
    for spec in a[2:]:
        name, js = spec.split('|', 1)
        var = json.loads(js)
        t0 = time.time()
        if var.get('built'):
            hair = {n: vt for n, (vt, _) in hairlab.built_hair(ctx).items()}
            R = None
        else:
            R, _, _, h2 = hairlab.run(ctx, var.get('style'), var.get('opts'))
            hair = {n: vt for n, (vt, _) in h2.items()}
        m, ours, pieces = measure(ctx, hair, R, noise)
        res[name] = m
        show(name, m)
        print('   (%.0f s)' % (time.time() - t0))
        if save:
            os.makedirs(save, exist_ok=True)
            np.savez_compressed(os.path.join(save, name + '.npz'), names=json.dumps(pieces), pieces=json.dumps(pieces),
                                ppl=hf.design_inputs(ctx['B'], ctx['D'])[1], **ours)
            if R is not None:
                import pickle
                pickle.dump({n: dict(V=p['V'], T=np.asarray(p['T']), vn_shade=p.get('vn_shade')) for n, p in
                             R['pieces'].items()}, open(os.path.join(save, name + '.pieces.pkl'), 'wb'))
        json.dump(res, open(out, 'w'), indent=1, default=float)
