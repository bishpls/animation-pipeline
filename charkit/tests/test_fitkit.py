"""charkit.fitkit on a toy evaluator with known answers: checks that are simple functions of two knobs (venv: run this
file). The toy is fitkit's worker protocol: a class with checks(spec, group, fine)."""
import os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import fitkit
from charkit.fitkit import Knob, Term

KNOBS = [Knob('a', ('toy', 'a'), 1.0, 0.05, (0.5, 2.0), 'g'), Knob('b', ('toy', 'b'), 0.0, 0.01, (-0.1, 0.1), 'g'),
         Knob('c', ('toy', 'c'), 1.0, 0.1, (0.5, 1.2), 'g')]


class Toy:
    """width = a / 1.3 (wants a = 1.3); reach = b - 0.04 (wants b = 0.04); far = c + 1 (wants c = 0, below its bound);
    dead: nothing moves it."""

    def __init__(self, *args):
        pass

    def checks(self, spec, group, fine=False):
        t = spec.get('toy', {})
        a, b, c = t.get('a', 1.0), t.get('b', 0.0), t.get('c', 1.0)
        return {'width': {'value': a / 1.3, 'status': 'PASS'}, 'reach': {'value': b - 0.04, 'status': 'PASS'},
                'far': {'value': c + 1.0, 'status': 'PASS'}, 'dead': {'value': 0.5, 'status': 'FAIL'}}


TERMS = [Term('width', None, 'ratio', 0.08, 'front', 'sheet', 'front', 'g'),
         Term('reach', None, 'abs', 0.02, 'profile', 'sheet', 'profile', 'g'),
         Term('far', None, 'abs', 0.2, 'profile', 'sheet', 'profile', 'g'),
         Term('dead', None, 'abs', 0.02, 'profile', 'hull', 'profile', 'g')]


def test_residuals_and_weights():
    C = Toy().checks({}, 'g')
    R = fitkit.residuals(C, TERMS, {'profile': 'sheet'})
    r = {t['name']: t for t in R}
    assert abs(r['width']['r'] - (1 / 1.3 - 1) / 0.08) < 1e-9 and abs(r['reach']['r'] + 2.0) < 1e-9
    assert r['dead']['w'] == 0.25 and r['width']['w'] == 1.0            # the hull term is not the profile's authority
    assert fitkit.residuals({}, TERMS[:1])[0]['r'] == fitkit.MISSING


def test_optimise_finds_the_knobs_and_reports_bounds():
    pool = fitkit.Pool('charkit.tests.test_fitkit:Toy', (), workers=1)
    spec, info = fitkit.optimise(pool, {'name': 'toy'}, KNOBS, TERMS, 'g', {'profile': 'sheet'}, log=lambda *a: None)
    assert abs(spec['toy']['a'] - 1.3) < 0.03, spec
    assert abs(spec['toy']['b'] - 0.04) < 0.005, spec
    assert spec['toy']['c'] == 0.5 and info['at_bound'] == {'c': 'lower'}
    assert info['evaluations'] > 0 and info['stopped'] is None


def test_budget_stops_early_with_the_best_so_far():
    pool = fitkit.Pool('charkit.tests.test_fitkit:Toy', (), workers=1)
    spec, info = fitkit.optimise(pool, {'name': 'toy'}, KNOBS, TERMS, 'g', budget=6, log=lambda *a: None)
    assert info['stopped'] == 'budget' and info['evaluations'] <= 6


def test_sensitivity_schema_and_triage():
    pool = fitkit.Pool('charkit.tests.test_fitkit:Toy', (), workers=1)
    T = fitkit.sensitivity(pool, {'name': 'toy'}, KNOBS)
    assert T['schema'] == fitkit.SCHEMA
    m = T['knobs']['a']['measures']['width']
    assert abs(m['per_unit'] - 1 / 1.3) < 1e-6 and abs(m['per_step'] - 0.05 / 1.3) < 1e-6
    assert T['knobs']['b']['measures']['width']['per_unit'] == 0
    # after a fit: 'far' can't pass with c at its bound, 'dead' has no knob
    spec = {'name': 'toy', 'toy': {'a': 1.3, 'b': 0.04, 'c': 0.5}}
    R = fitkit.residuals(Toy().checks(spec, 'g'), TERMS)
    why = {t['term']: t['why'] for t in fitkit.triage(R, T, KNOBS, spec)}
    assert why == {'far': 'knob at bound', 'dead': 'needs a knob'}, why



class TimedToy(Toy):
    """Toy that keeps its stage times, as charkit.bodyfit.BodyChecks does."""

    def checks(self, spec, group, fine=False):
        self.timing = {'measure': 0.001, 'geometry': 0.002}
        return super().checks(spec, group, fine)


def test_evaluations_are_counted_and_timed_by_phase():
    pool = fitkit.Pool('charkit.tests.test_fitkit:TimedToy', (), workers=1)
    spec, info = fitkit.optimise(pool, {'name': 'toy'}, KNOBS, TERMS, 'g', {'profile': 'sheet'}, log=lambda *a: None)
    ph = info['phases']
    assert {'start', 'gradient', 'polish'} <= set(ph), ph
    assert sum(v['evaluations'] for v in ph.values()) == info['evaluations']
    fitkit.sensitivity(pool, {'name': 'toy'}, KNOBS)
    R = pool.report()
    assert R['phases']['sensitivity']['evaluations'] == 1 + 2 * len(KNOBS)
    assert R['phases']['gradient']['evaluations'] == ph['gradient']['evaluations']
    assert R['phases']['gradient']['stages'] == {'geometry': 0.002, 'measure': 0.001}
    assert R['workers'] == 1 and R['peak_mb'] > 0 and R['phases']['polish']['parallelism'] > 0



WIDE = [Knob('k%d' % i, ('wide', 'k%d' % i), 1.0, 0.05, (0.2, 2.0), 'w') for i in range(8)]
WIDE_TERMS = [Term('t%d' % i, None, 'abs', 0.02, 'front', 'sheet', 'front', 'w') for i in range(8)] + \
             [Term('sum', None, 'abs', 0.05, 'front', 'sheet', 'front', 'w')]


class Wide:
    """eight knobs, each wanting its own value (t_i = k_i - (0.6 + 0.1 i)), and one term coupling them all (their sum
    wants 8.6, against the 7.6 the others add up to: a trade-off), read on a grid of 0.005 as a pixel-quantised check
    reads."""

    def __init__(self, *args):
        pass

    def checks(self, spec, group, fine=False):
        k = [spec.get('wide', {}).get('k%d' % i, 1.0) for i in range(8)]
        q = lambda v: round(v / 0.005) * 0.005
        C = {'t%d' % i: {'value': q(k[i] - (0.6 + 0.1 * i)), 'status': 'FAIL'} for i in range(8)}
        C['sum'] = {'value': q(sum(k) - 8.6), 'status': 'FAIL'}
        return C


def test_fast_reaches_the_same_fit_in_fewer_evaluations():
    out = {}
    for fast in (False, True):
        pool = fitkit.Pool('charkit.tests.test_fitkit:Wide', (), workers=1)
        spec, info = fitkit.optimise(pool, {'name': 'wide'}, WIDE, WIDE_TERMS, 'w', protect=False, fast=fast,
                                     log=lambda *a: None)
        R = fitkit.residuals(Wide().checks(spec, 'w'), WIDE_TERMS)
        out[fast] = (fitkit.cost(R, [k.get(spec) for k in WIDE], WIDE), info['evaluations'], spec, info)
    (c0, n0, s0, i0), (c1, n1, s1, i1) = out[False], out[True]
    assert i1['fast'] and not i0['fast']
    assert c1 <= c0 * 1.05 + 1e-6, (c0, c1)                              # as good a fit
    assert n1 < n0, (n0, n1)                                               # for fewer evaluations
    for i in range(8):                                                     # the same knobs, within a step
        assert abs(s1['wide']['k%d' % i] - s0['wide']['k%d' % i]) <= 0.05, (s0['wide'], s1['wide'])


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
