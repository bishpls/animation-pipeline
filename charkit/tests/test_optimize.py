"""charkit sweep optimize (charkit/optimize.py) on synthetic objectives (venv: run this file): the CMA-ES core converges
and is reproducible; knobs, templates and bounds; the objective's terms and limits; the constraints enforced (the
anti-gaming guard, flags, no new FAIL, kept checks; real-only checks routed to the confirm); a run on the synthetic
problem (best feasible, the trap's unconstrained optimum refused, every output written); resume after an interrupted
generation reproduces the uninterrupted run exactly; the subprocess pool matches the in-process evaluator; a qa-stage
run through the sweep's own stage and measurement."""
import copy, json, os, shutil, sys, tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import optimize as op

os.environ.setdefault('CHARKIT_SLOT_HELD', str(os.getpid()))   # (the tests' runs take no machine build slot)
QUIET = lambda *a, **k: None

SYN = dict(stage='python', python='charkit.optimize:synthetic', set={'a': 0.2, 'b': 0.2, 'c': 0.2, 'n': 1},
           optimize=dict(knobs=[dict(path='a', lo=0, hi=1, x0=0.2), dict(path='b', lo=0, hi=1, x0=0.2),
                                dict(path='c', lo=0, hi=1, x0=0.2), dict(path='n', lo=0, hi=10, int=True, x0=1)],
                         objective=[dict(check='bowl', toward='min')], constraints=dict(keep=['keep_toy']),
                         seed=2, budget=dict(evals=300), reference=dict(hand={'a': 0.6, 'b': 0.3, 'c': 0.6, 'n': 3})))


def syn(**kw):
    d = copy.deepcopy(SYN)
    for k, v in kw.items():
        d['optimize'][k] = v
    return d


def run(decl, out, **kw):
    R = op.Run(decl, out, workers=kw.pop('workers', 1), log=QUIET, inproc=kw.pop('inproc', True))
    return R, R.run(confirm=False, **kw)


def test_cma_converges_and_is_reproducible():
    def go(seed):
        c = op.CMA(np.full(5, 0.2), 0.2, seed=seed)
        fs = []
        for g in range(400):
            Y = c.ask()
            U = op.reflect(Y)
            f = (((U - 0.6) ** 2) * np.arange(1, 6)).sum(1)
            c.tell(Y, list(np.argsort(f)))
            fs.append(float(f.min()))
            if f.min() < 1e-9:
                break
        return fs, c
    fs, c = go(4)
    assert fs[-1] < 1e-9 and len(fs) < 250, (fs[-1], len(fs))
    assert go(4)[0] == fs                                           # (seeded per generation: the same run)
    assert go(5)[0] != fs
    c2 = op.CMA.from_state(json.loads(json.dumps(c.state())))      # (the state round-trips exactly through JSON)
    assert np.array_equal(c2.ask(), c.ask())


def test_integer_floor_keeps_the_search_moving():
    c = op.CMA(np.array([0.5, 0.5]), 0.2, lam=8, floors=[0.0, 0.04], seed=0)
    for g in range(60):
        Y = c.ask()
        U = op.reflect(Y)
        c.tell(Y, list(np.argsort(((U - 0.3) ** 2).sum(1))))
    s = c.spread()
    assert s[0] < 0.01 and s[1] >= 0.04 - 1e-9, s


def test_knobs_bounds_and_templates():
    assert np.allclose(op.reflect([-0.2, 0.3, 1.3, 2.1, -1.5]), [0.2, 0.3, 0.7, 0.1, 0.5])
    k = op.Knob(dict(path='a.b', lo=5, hi=25, int=True), spec={'a': {'b': 13}})
    assert k.x0 == 13 and k.from_unit(0.52) == 15 and k.from_unit(-1) == 5 and isinstance(k.from_unit(0.3), int)
    g = op.Knob(dict(name='g', lo=0.01, hi=1.0, log=True))
    assert abs(g.from_unit(0.5) - 0.1) < 1e-4 and abs(g.to_unit(0.1) - 0.5) < 1e-9
    P = op.Problem(dict(set={'x': 1}, optimize=dict(
        knobs=[dict(name='g1', lo=6, hi=20, int=True, x0=14), dict(name='g2', lo=6, hi=20, int=True, x0=14),
               dict(name='h', lo=0.1, hi=0.3, x0=0.25), dict(path='garments.flap.square', lo=0, hi=3, x0=0)],
        template={'garments.skirt.band.stair': [[0, 0.35], ['=g1', '=h'], ['=g1+g2', '=h-0.1'], ['=max(g1, g2)', 0.1]]},
        objective=[dict(check='c')])))
    over = P.overrides(P.x0())
    assert over == {'garments.flap.square': 0.0, 'garments.skirt.band.stair': [[0, 0.35], [14, 0.25], [28, 0.15],
                                                                               [14, 0.1]]}, over
    assert isinstance(over['garments.skirt.band.stair'][2][0], int)
    assert P.row_set(P.x0())['x'] == 1
    try:
        op.expr('__import__("os")', {})
        raise AssertionError('a template may only do arithmetic')
    except SystemExit:
        pass
    assert P.stop['target'] == 0.0                                  # (every term toward PASS: stop when all pass)


def test_scorer_terms_constraints_and_fidelity():
    P = op.Problem(dict(optimize=dict(
        knobs=[dict(path='a', lo=0, hi=1)],
        objective=[dict(check='corner_*', toward='pass', limits=[3, 5]), dict(check='art_terminator_x', toward='pass',
                                                                              limits=[1.5, 3.0]),
                   dict(check='piece_bow', view='front', toward='max', weight=2)],
        constraints=dict(keep=['pleats']))))
    ctrl = {'corner_front': dict(value=8.9, status='FAIL'), 'corner_3q': dict(value=6.0, status='FAIL'),
            'art_terminator_x': dict(value=2.0, status='WARN'),
            'piece_bow': dict(value=0.8, status='PASS', views={'front': 0.9, 'profile': 0.5}),
            'piece_tiny': dict(value=0.04, status='PASS', views={'front': 0.04}),
            'flag_x': dict(value=1.1, status='PASS', flag='michael'), 'pleats': dict(value=0.5, status='PASS'),
            'other': dict(value=1, status='WARN')}
    S = op.Scorer(P, ctrl, log=QUIET)
    assert [t['check'] for t in S.terms] == ['corner_front', 'corner_3q', 'piece_bow'] and \
        S.left_out == ['art_terminator_x']                          # (real-only: scored at the confirm)
    r = S.score(ctrl)
    assert r['feasible'] and abs(r['f'] - ((8.9 - 3) / 2 + (6 - 3) / 2 - 2 * 0.9)) < 1e-6, r
    good = dict(ctrl, corner_front=dict(value=2.0, status='PASS'), corner_3q=dict(value=4, status='WARN'))
    r = S.score(good)
    assert r['feasible'] and r['terms']['corner_front'] == 0.0 and r['terms']['corner_3q'] == 0.5
    gamed = dict(good, corner_3q=dict(value=2.0, status='PASS'),         # (better, but the bow's profile -32%)
                 piece_bow=dict(value=0.7, views={'front': 0.9, 'profile': 0.34}))
    r = S.score(gamed)
    assert not r['feasible'] and [(v['kind'], v['check'], v['view']) for v in r['viol']] == [
        ('guard', 'piece_bow', 'profile')], r['viol']
    assert r['f'] < S.score(good)['f']                              # (better on the objective, yet ranked below)
    assert op.rank_key(S.score(good)) < op.rank_key(r)
    tiny = dict(good, piece_tiny=dict(value=0.0, views={'front': 0.0}))        # (an IoU under MIN_IOU: not guarded)
    assert S.score(tiny)['feasible']
    flag = dict(good, flag_x=dict(value=1.3, status='WARN', flag='michael'))
    assert [v['kind'] for v in S.score(flag)['viol']] == ['flag']
    nf = dict(good, other=dict(value=3, status='FAIL'))
    assert [v['kind'] for v in S.score(nf)['viol']] == ['new_fail']
    kp = dict(good, pleats=dict(value=1.5, status='WARN'))
    assert [v['kind'] for v in S.score(kp)['viol']] == ['keep']
    gone = {k: v for k, v in good.items() if k != 'corner_3q'}
    assert [v['kind'] for v in S.score(gone)['viol']] == ['missing']
    # a real-only check's constraint: enforced on the screen's drawing as a proxy (default), or left to the confirm
    real = dict(good, art_terminator_x=dict(value=4.0, status='FAIL'))
    assert [v['kind'] for v in S.score(real)['viol']] == ['new_fail']
    P.constraints['proxy_real'] = False
    assert op.Scorer(P, ctrl, log=QUIET).score(real)['feasible']
    R = op.Scorer(P, ctrl, mode='real', log=QUIET)                  # (the confirm: every term, every constraint)
    assert 'art_terminator_x' in [t['check'] for t in R.terms] and not R.score(real)['feasible']
    assert op.fidelity('art_fragments_bow') == 'real' and op.fidelity('stair_front_crossed') == 'fast'
    assert op.fidelity('palette_skin_lit') == 'fast'                # (the audit: the palette reads the same)
    assert op.fidelity('x', 'look') == 'real' and op.fidelity('art_band_lower', extra={'art_band_*': 'fast'}) == 'fast'


def test_declared_limits_are_read():
    lim = op.limits_for('stair_skirt_front_corner')
    assert lim == ('lo', 3.0, 5.0), lim
    assert op.limits_for('nothing_by_this_name') is None


def test_synthetic_run_enforces_the_constraints():
    with tempfile.TemporaryDirectory() as d:
        R, o = run(syn(), os.path.join(d, 'o'))
        H = R.H
        best = R.best()
        A = op.Synthetic({}).args
        # the bowl's minimum (a 0.8) lies past the guard's cliff: the best stays within 15% of the control's front IoU
        assert best['feasible'] and best['knobs']['a'] <= A['cliff'] + 0.15 * 0.9 / 2 + 1e-9, best['knobs']
        assert best['knobs']['c'] <= A['flag_at'] and best['knobs']['n'] <= A['keep_at']
        assert best['f'] < 0.05 and o['evaluations'] <= 320, (best['f'], o['evaluations'])
        gamed = [h for h in H if h.get('f') is not None and h['f'] < best['f']]
        assert gamed and all(not h['feasible'] for h in gamed)      # (the search met the trap and refused it)
        kinds = {v['kind'] for h in H for v in h.get('viol') or ()}
        assert {'guard', 'flag', 'keep'} <= kinds, kinds
        assert all(h.get('checks') for h in H if not h.get('cached'))
        assert H[0]['name'] == 'control' and H[0]['set'] == SYN['set'] and H[0]['feasible']
        ref = next(h for h in H if h['name'] == 'ref_hand')
        assert ref['knobs'] == {'a': 0.6, 'b': 0.3, 'c': 0.6, 'n': 3} and ref['feasible']
        for f in ('history.jsonl', 'history.csv', 'history.md', 'state.json', 'opt.json', 'best_override.json',
                  'sensitivity.json', 'sensitivity.md', 'sweep.json', 'convergence.png', 'review/page.json',
                  'review/index.html'):
            assert os.path.exists(os.path.join(d, 'o', f)), f
        bo = json.load(open(os.path.join(d, 'o', 'best_override.json')))
        assert bo['set']['a'] == best['knobs']['a'] and bo['feasible']
        csv = open(os.path.join(d, 'o', 'history.csv')).readline()
        assert 'iou:piece_toy.front' in csv and 'bowl:value' in csv and 'knob:n' in csv
        sens = json.load(open(os.path.join(d, 'o', 'sensitivity.json')))
        assert set(sens['knobs']) == {'a', 'b', 'c', 'n'} and sens['knobs']['a']['oat']
        page = json.load(open(os.path.join(d, 'o', 'review', 'page.json')))
        assert page['summary']['recommended'].startswith('Take ') and page['summary']['numbers']['rows']


def test_resume_reproduces_the_uninterrupted_run():
    with tempfile.TemporaryDirectory() as d:
        decl = syn(budget=dict(generations=7, evals=1000), stop=dict(stall=0))
        R1, _ = run(decl, os.path.join(d, 'whole'))
        # interrupted mid-generation (an uncaught interrupt after 30 evaluations), then resumed
        os.environ['CHARKIT_OPT_TEST_INTERRUPT'] = '30'
        try:
            run(decl, os.path.join(d, 'cut'))
            raise AssertionError('the interrupt should have stopped the run')
        except KeyboardInterrupt:
            pass
        finally:
            os.environ.pop('CHARKIT_OPT_TEST_INTERRUPT', None)
        st = json.load(open(os.path.join(d, 'cut', 'state.json')))
        assert not st.get('done') and st['opt']['gen'] < 7
        try:
            run(decl, os.path.join(d, 'cut'))
            raise AssertionError('a folder holding a run needs --resume')
        except SystemExit:
            pass
        R2, _ = run(decl, os.path.join(d, 'cut'), resume=True)
        a = sorted((h['name'], h['key'], h['f'], h['v']) for h in R1.H if h['kind'] == 'cma')
        b = sorted((h['name'], h['key'], h['f'], h['v']) for h in R2.H if h['kind'] == 'cma')
        assert a == b, (len(a), len(b))
        s1 = json.load(open(os.path.join(d, 'whole', 'state.json')))['opt']
        s2 = json.load(open(os.path.join(d, 'cut', 'state.json')))['opt']
        assert s1 == s2
        # the cut generation's evaluations were reused, not run again
        assert R2.n_evals() == R1.n_evals(), (R2.n_evals(), R1.n_evals())
        # a run stopped on its budget carries on under a larger one (the budget isn't part of the declaration's hash)
        R3, _ = run(syn(budget=dict(generations=9, evals=1000), stop=dict(stall=0)), os.path.join(d, 'cut'),
                    resume=True)
        assert json.load(open(os.path.join(d, 'cut', 'state.json')))['opt']['gen'] == 9
        # a changed declaration can't resume the old folder

        try:
            run(syn(budget=dict(generations=7), stop=dict(stall=0), seed=9), os.path.join(d, 'cut'), resume=True)
            raise AssertionError('a changed declaration must not resume')
        except SystemExit:
            pass


def test_pool_matches_in_process():
    with tempfile.TemporaryDirectory() as d:
        decl = syn(budget=dict(generations=3), stop=dict(stall=0))
        decl['args'] = dict(sleep=0.05)                             # (rows that take time: both workers serve)
        R1, _ = run(decl, os.path.join(d, 'a'))
        R2, o = run(decl, os.path.join(d, 'b'), workers=2, inproc=False)
        assert o['workers'] == 2, o['workers']
        # (the pool records rows as they finish: the same rows and values, in completion order)
        assert sorted((h['name'], h['key'], h['f']) for h in R1.H) == sorted((h['name'], h['key'], h['f']) for h in R2.H)
        assert {h.get('worker') for h in R2.H if not h.get('cached')} == {0, 1}


def test_qa_stage_through_the_sweep():
    """a `qa:` knob through the sweep's own qa stage, measurement and splice (test_sweep's probe part)."""
    from charkit.tests import test_sweep as ts
    with tempfile.TemporaryDirectory() as d:
        base = ts.build_dir(os.path.join(d, 'base'), ts.small())
        decl = dict(base=base, stage='qa', parts=['sweep_probe'], shape_parts=[], optimize=dict(
            knobs=[dict(path='qa:sweep_probe_mod.scale', lo=0.1, hi=3.0, x0=1.0)],
            objective=[dict(check='probe_z', toward='target', target=6.0)], constraints=dict(flags=False),
            budget=dict(evals=60), seed=1))
        R, o = run(decl, os.path.join(d, 'o'))
        b = R.best()
        assert abs(b['knobs']['qa:sweep_probe_mod.scale'] - 1.5) < 0.02 and b['f'] < 0.05, b
        assert ts.PROBE.scale == 1.0                                # (restored after every row)
        assert next(h for h in R.H if h['name'] == 'control')['checks']['probe_z']['value'] == 4.0


def test_confirm_builds_run_the_iterate_profile_unless_a_term_reads_motion():
    """the confirm builds' QA profile (Michael, 2026-10-01): 'iterate' by default, motion QA skipped explicitly and its
    checks left out of the comparison on both sides; 'full' when an objective term or a keep pattern reads a motion check,
    or when confirm.profile says so."""
    mk = lambda obj, keep=(), **conf: op.Problem(dict(optimize=dict(
        knobs=[dict(path='a', lo=0, hi=1)], objective=[dict(check=c, toward='pass', limits=[1, 2]) for c in obj],
        constraints=dict(keep=list(keep)), confirm=conf)))
    base = {'checks': {'motion_kick_skirt_inside': dict(value=0.1, status='PASS'), 'art_x': dict(value=1, status='PASS')},
            'measured': {'part_checks': {'motion': ['motion_kick_skirt_inside', 'motion_squat_skirt_stretch']}}}
    prof, skip, why = op.confirm_profile(mk(['art_*']), base)
    assert prof == 'iterate' and skip == ['motion'] and 'motion skipped' in why, (prof, skip, why)
    for obj, keep in ((['motion_kick_*'], ()), (['art_*'], ['motion_*']), (['motion_squat_skirt_stretch'], ()),
                      (['art_*'], ['*'])):
        prof, skip, why = op.confirm_profile(mk(obj, keep), base)
        assert prof == 'full' and skip == [] and 'motion' in why, (obj, keep, prof, why)
    assert op.confirm_profile(mk(['art_*'], profile='full'), base)[:2] == ('full', [])
    # the comparison leaves the skipped part's checks out: those the base build recorded, its prefix and its SKIPPED key
    row = {'motion': dict(status='SKIPPED', why='skipped by profile iterate'), 'art_x': dict(value=1, status='PASS')}
    drop = op.part_checks(['motion'], base)
    assert drop == {'motion_kick_skirt_inside', 'motion_squat_skirt_stretch', 'motion'}, drop
    P = mk(['art_x'])
    S = op.Scorer(P, {k: v for k, v in base['checks'].items() if k not in drop}, mode='real', log=QUIET)
    r = S.score({k: v for k, v in row.items() if k not in drop})
    assert r['feasible'] and not r['viol'], r


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)


def test_a_ring_of_starts_searches_from_each():
    with tempfile.TemporaryDirectory() as d:
        starts = {'low': {'a': 0.05, 'b': 0.05}, 'high': {'a': 0.95, 'b': 0.95}}
        decl = syn(budget=dict(generations=8, evals=1000), stop=dict(stall=0), starts=starts)
        R, res = run(decl, os.path.join(d, 'ring'))
        names = [h['name'] for h in R.H if h['kind'] == 'cma']
        assert any(n.startswith('slow_g') for n in names) and any(n.startswith('shigh_g') for n in names)
        assert {h['start'] for h in R.H if h['kind'] == 'cma'} == {'low', 'high'}
        assert any(h['name'] == 'start_low' for h in R.H) and any(h['name'] == 'start_high' for h in R.H)
        st = json.load(open(os.path.join(d, 'ring', 'state.json')))
        assert set(st['starts_done']) == {'low', 'high'}
        # each start ran its share of the generations (4 of 8), and the best is the best of either
        assert max(h['gen'] for h in R.H if h.get('start') == 'low' and h['kind'] == 'cma') == 3
        best = R.best()
        assert best['f'] == min(st['starts_done'][k]['f'] for k in ('low', 'high'))
