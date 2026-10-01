"""charkit.limbs (a piece's parts read from its silhouette: the crab clip's legs, pincers and eye stalks) on the crab
template drawn face-on (venv: run this file, or pytest)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import accessories as acc, accfit, accqa, declared, limbs


def _crab(shape=None, px=420):
    V, F, _ = acc.crab(shape)
    return accfit.silhouette(V, F, px=px)


def test_reads_the_template_crab_parts():
    R = limbs.read(_crab())
    assert R['n_legs'] == {'L': 3, 'R': 3}
    assert R['n_stalks'] == 2 and R['fingers'] == [2, 2]
    assert 0.15 < R['leg_reach'] < 0.35 and -30 < R['leg_root'] < 15      # off the sides, not the bottom
    assert R['notch'] > 0.15


def test_scale_free_and_spoils_fail_their_own_measure():
    a, b = limbs.read(_crab(px=420)), limbs.read(_crab(px=300))
    for m in ('count', 'reach', 'root', 'fingers', 'notch', 'stalks'):
        r = limbs.compare(b, a, m)
        assert r['value'] is not None and r['value'] <= {'root': 6.0, 'notch': 0.03}.get(m, 0.1), (m, r)
    m = _crab()
    for how, meas in (('legless', 'count'), ('short_legs', 'reach'), ('bottom_legs', 'root'),
                      ('solid_claws', 'fingers'), ('no_stalks', 'stalks')):
        r = limbs.compare(limbs.read(limbs.spoil(m, how)), a, meas)
        assert r['value'] is None or r['value'] > {'count': 0, 'reach': 0.35, 'root': 25, 'fingers': 0,
                                                   'stalks': 0.5}[meas], (how, r)


def test_short_bottom_legs_and_round_claws_fail_the_declared_checks():
    # round 5's crab: legs 0.15 under the body, claws without a notch
    bad = _crab(dict(leg=0.04, leg_at=(-60.0, -85.0), leg_dir=(-80.0, -90.0), claw_cut=0.0, eye_at=(0.18, 0.3)))
    good = _crab()
    I = lambda m: dict(O={accqa.FACE: {'lab': accqa.face_labels([m])}}, names=['-', 'crab'],
                       pm={'pin_crab': [('crab', None)]}, masks={'face__pin_crab': good}, ppl=400.0,
                       dv={accqa.FACE: {}})
    ds = accfit.face_decls('crab')
    assert len(ds) == 6
    _, Cg = declared.evaluate(ds, I(good))
    _, Cb = declared.evaluate(ds, I(bad))
    assert all(c['status'] == 'PASS' for c in Cg.values()), Cg
    assert all(Cb[k]['status'] == 'FAIL' for k in ('acc_crab_legs', 'acc_crab_claw_fingers', 'acc_crab_claw_notch')), Cb


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f()
            print('ok', k)
