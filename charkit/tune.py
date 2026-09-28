"""The tune loop: a character from its spec to a fitted, checked build, and whatever error is left turned into ranked work
items (docs/CHARKIT.md §4).

    python -m charkit tune SPEC [--out DIR] [--budget N | Nm] [--review] [--args "--base anime"] [--only face,options]
                                [--config PATH] [--rounds K] [--min-gain G] [--fit-budget N] [--workers N]
                                [--fresh] [--no-worker]

  1. checkpoint 0: the spec built as it is (resolved: the manifest, refs.fit's first guess) with full QA;
  2. rounds: each fitter in the registry (charkit/fitters.py: build options, the face, the body) whose target checks
     aren't all passing runs from the best checkpoint so far (the spec it resolved to), and what it changes is built and
     QA'd as a new checkpoint
     (the build worker and stage cache are used when present: tool/speed);
  3. each checkpoint is compared with the best so far by the gate's QA diff (charkit.gate.compare_qa): it is accepted
     only when no graded check regresses (a status gets worse, or a check disappears) unless an explicit trade-off rule
     in the character's tune config allows that regression, and only when the total severity (charkit.checks.score, over
     the checks both share) drops. A rejected fit with more than one knob block is tried again one block at a time;
  4. the loop stops when every graded check passes (`pass`), when the best score improved by less than --min-gain over
     the last --rounds rounds (`stalled`), when no fitter has anything left to change (`converged`), or when the budget
     (full builds including the final one, default 8, or minutes with an `m` suffix) runs out (`budget`);
  5. the best checkpoint is built once more with every board (`final`: the review's pictures, and a check that the build
     is repeatable), each landed fitter measures its sensitivity table there (its own fit's table is at its start), the
     residual checks are triaged (charkit/triage.py: DIR/work_items.json and .md), and with --review the review board,
     page and notes file are written (charkit/review.py) and the final build also exports a VRM for the inspector.

Everything goes to DIR/tune.jsonl (begin, fit, checkpoint, compare, round, stop, triage, review, end), and each
checkpoint's history row (charkit/history.py) carries a note {tune: RUN, checkpoint: N, label}. DIR/tune.json is the run's
summary. The run records its own pid in DIR (`python -m charkit ps`; `python -m charkit kill DIR` stops it and the build it
started).

The character's tune config is charkit/refs/NAME/tune.json (beside the reference manifest, whose authority table the
trade-off rules write out):
    {"tradeoffs": [{"allow": ["face_shape_width"], "when": ["sheet_width"], "floor": "FAIL", "ratio": 3.0, "why": "..."}],
     "options": [{"name": "geom hair", "set": {"hair.shape.mode": "geom"}, "targets": ["hair_noise"], "why": "..."}],
     "stop": {"rounds": 2, "min_gain": 0.5}, "uncertain": {"sheet": 0.04}}
A trade-off rule lets a check matching `allow` get worse (not below `floor`) in a checkpoint where a check matching `when`
improves by at least `min_gain` warn bands (default 0.1), and by no more than `ratio` times that gain when given.
"""
import fnmatch, hashlib, json, os, shlex, signal, subprocess, sys, time

from . import checks

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
BOARDS_STEP = 'views'
BOARDS_FINAL = 'views,body,expressions,mouths'
STATUS_RANK = checks.RANK


def _path(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def say(*a):
    print(*a, flush=True)


def _rel(p):
    return os.path.relpath(p, ROOT) if p and os.path.isabs(p) and p.startswith(ROOT) else p


# ------------------------------------------------------------------------------------------------------------ config
def config_path(spec):
    ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else {}
    if ref.get('manifest'):
        return os.path.join(os.path.dirname(_path(ref['manifest'])), 'tune.json')
    return _path(os.path.join('charkit', 'refs', spec['name'], 'tune.json'))


def load_config(spec, path=None):
    p = path or config_path(spec)
    C = json.load(open(p)) if p and os.path.exists(p) else {}
    C['_path'] = _rel(p) if p and os.path.exists(p) else None
    return C


# ------------------------------------------------------------------------------------------------------------ accept
def _match(name, pats):
    pats = [pats] if isinstance(pats, str) else pats
    return any(fnmatch.fnmatchcase(name, p) for p in pats)


def _sev(qa, k):
    c = (qa.get('checks') or {}).get(k)
    return checks.sev_of(k, c) if isinstance(c, dict) and c.get('status') in checks.GRADED else None


def tradeoff(row, prev, cand, rules):
    """the rule that allows this regressed row, with the check that paid for it -> (rule, gainer, gain, cost) or None."""
    k = row['check']
    st = row['cand'][1]
    s0, s1 = _sev(prev, k), _sev(cand, k)
    cost = (s1 - s0) if s0 is not None and s1 is not None else None
    for r in rules or []:
        if not _match(k, r.get('allow', [])):
            continue
        if st not in STATUS_RANK or STATUS_RANK[st] > STATUS_RANK.get(r.get('floor', 'FAIL'), 2):
            continue
        best = None
        for g in checks.graded(cand):
            if g == k or not _match(g, r.get('when', [])):
                continue
            a, b = _sev(prev, g), _sev(cand, g)
            if a is None or b is None:
                continue
            gain = a - b
            if gain >= r.get('min_gain', 0.1) and (best is None or gain > best[1]):
                best = (g, gain)
        if best is None:
            continue
        if r.get('ratio') is not None and cost is not None and cost > r['ratio'] * best[1]:
            continue
        return r, best[0], round(best[1], 3), None if cost is None else round(cost, 3)
    return None


def accept(prev, cand, rules=(), remeasured=None, min_gain=1e-3):
    """a candidate checkpoint's QA against the best so far -> {verdict accept|reject, why, gain, rows, regressed,
    traded, improved}. Rejected: a graded check regresses (status worse, or gone) with no trade-off rule allowing it, or
    the score (over the graded checks both share) doesn't drop by more than min_gain."""
    from . import gate
    rows = gate.compare_qa(prev, cand, remeasured)
    common = set(checks.graded(prev)) & set(checks.graded(cand))
    if remeasured:
        common = {k for k in common if not _match(k, list(remeasured))}
    s0, s1 = checks.score(prev, common), checks.score(cand, common)
    gain = round(s0 - s1, 4)
    regressed, traded = [], []
    for r in rows:
        if r['verdict'] not in ('regressed', 'gone'):
            continue
        t = tradeoff(r, prev, cand, rules) if r['verdict'] == 'regressed' else None
        if t:
            rule, g, gg, cost = t
            traded.append({'check': r['check'], 'base': r['base'], 'cand': r['cand'], 'for': g, 'gain': gg, 'cost': cost,
                           'rule': rule.get('why') or rule.get('allow')})
        else:
            regressed.append({'check': r['check'], 'base': r['base'], 'cand': r['cand'], 'verdict': r['verdict']})
    improved = [r['check'] for r in rows if r['verdict'] == 'improved']
    if regressed:
        why = 'regressed without a trade-off rule: ' + ', '.join('%s %s->%s' % (x['check'], x['base'][1], x['cand'][1]) for x in regressed)
        verdict = 'reject'
    elif gain <= min_gain:
        why = 'no gain: score %.3f -> %.3f' % (s0, s1)
        verdict = 'reject'
    else:
        why = 'score %.3f -> %.3f' % (s0, s1) + ('; traded: ' + ', '.join('%s for %s' % (t['check'], t['for']) for t in traded) if traded else '')
        verdict = 'accept'
    return {'verdict': verdict, 'why': why, 'gain': gain, 'score': [s0, s1], 'rows': rows, 'regressed': regressed,
            'traded': traded, 'improved': improved}


# ------------------------------------------------------------------------------------------------------------ stop
def stop_reason(scores, all_pass=False, builds_left=None, seconds_left=None, changed=True, rounds=2, min_gain=0.5):
    """why the loop stops now, or None to go on. `scores`: the best score after each round (index 0: the start).
    pass: every graded check passes; budget: no builds or time left; converged: no fitter changed anything this round;
    stalled: the best score dropped by less than min_gain over the last `rounds` rounds."""
    if all_pass:
        return 'pass'
    if (builds_left is not None and builds_left <= 0) or (seconds_left is not None and seconds_left <= 0):
        return 'budget'
    if not changed:
        return 'converged'
    if len(scores) > rounds and scores[-rounds - 1] - scores[-1] < min_gain:
        return 'stalled'
    return None


def all_pass(qa):
    G = checks.graded(qa)
    return bool(G) and all(c['status'] == 'PASS' for c in G.values())


def failing(qa):
    return [k for k, c in checks.graded(qa).items() if c['status'] != 'PASS']


# ------------------------------------------------------------------------------------------------------------ record
class Record:
    """tune.jsonl: one JSON line per event."""

    def __init__(self, path):
        self.path = path
        self.t0 = time.time()
        self.f = open(path, 'a')

    def write(self, event, **kw):
        rec = {'t': round(time.time() - self.t0, 1), 'at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'event': event}
        rec.update(kw)
        self.f.write(json.dumps(rec, default=str) + '\n')
        self.f.flush()
        return rec

    def close(self):
        self.f.close()


def read(path):
    return [json.loads(l) for l in open(path) if l.strip()] if os.path.exists(path) else []


# ------------------------------------------------------------------------------------------------------------ builds
def _code_state():
    """the commit and a hash of the uncommitted kit changes (a checkpoint built under other code is rebuilt)."""
    h = subprocess.run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    d = subprocess.run(['git', '-C', ROOT, 'diff', 'HEAD', '--', 'charkit'], capture_output=True, text=True).stdout
    u = subprocess.run(['git', '-C', ROOT, 'ls-files', '--others', '--exclude-standard', '--', 'charkit'],
                       capture_output=True, text=True).stdout
    return h[:12] + ':' + hashlib.sha1((d + u).encode()).hexdigest()[:10]


class Checkpoint(dict):
    """a built and QA'd state: {id, label, spec, args, out, boards, qa (loaded), score, summary, git, seconds, reused}."""

    @property
    def qa(self):
        return self['_qa']


class Builder:
    """full builds for the loop: `python -m charkit build` per checkpoint, with the history note; a checkpoint whose
    folder already holds the same build (spec, options, boards and code) is reused unless fresh."""

    def __init__(self, out, run_id, name, fresh=False, log=say):
        self.out, self.run_id, self.name, self.fresh, self.log = out, run_id, name, fresh, log
        self.builds = 0
        self.current = None
        self.code = _code_state()

    def build(self, n, label, spec_path, args, boards=BOARDS_STEP, extra=()):
        d = os.path.join(self.out, 'ck%d_%s' % (n, label.replace(' ', '-').replace('/', '-')))
        os.makedirs(d, exist_ok=True)
        spec = json.load(open(spec_path))
        key = hashlib.sha1(json.dumps([spec, list(args), boards, list(extra), self.code], sort_keys=True, default=str).encode()).hexdigest()[:16]
        kp, qp = os.path.join(d, '.tune_key'), os.path.join(d, 'qa', 'qa.json')
        reused = not self.fresh and os.path.exists(qp) and os.path.exists(kp) and open(kp).read().strip() == key
        t = time.time()
        if not reused:
            if os.path.exists(kp):
                os.remove(kp)
            note = json.dumps({'tune': self.run_id, 'checkpoint': n, 'label': label})
            cmd = [PY, '-m', 'charkit', 'build', spec_path, '--out', d, '--boards', boards, '--no-blend', '--note', note] + \
                list(args) + list(extra)
            self.log('  build ck%d %s: %s' % (n, label, ' '.join(shlex.quote(c) for c in cmd[3:])))
            self.current = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            so, _ = self.current.communicate()
            rc, self.current = self.current.returncode, None
            open(os.path.join(d, 'build.log'), 'w').write(so)
            self.builds += 1
            if rc or not os.path.exists(qp):
                return Checkpoint(id=n, label=label, spec=_rel(spec_path), args=list(args), out=_rel(d), ok=False,
                                  seconds=round(time.time() - t, 1), why=so[-1500:], _qa={})
            open(kp, 'w').write(key)
        qa = json.load(open(qp))
        begin = next((r for r in _trace(d) if r.get('event') == 'begin'), {})
        cache = _cache_info(d)
        rp = os.path.join(d, spec['name'] + '.spec.json')
        return Checkpoint(id=n, label=label, spec=_rel(spec_path), resolved=_rel(rp) if os.path.exists(rp) else None,
                          args=list(args), out=_rel(d), boards=boards, ok=True,
                          reused=reused, seconds=round(time.time() - t, 1), git=begin.get('git'), summary=qa.get('summary'),
                          score=checks.score(qa), counts=_counts(qa), cache=cache, _qa=qa)

    def stop(self):
        """stop the build this run started (its python, and the Blender it recorded)."""
        if self.current and self.current.poll() is None:
            self.current.terminate()
        from . import procs
        for pf, rec, alive in procs.records([ROOT]):
            if alive and os.path.dirname(pf).startswith(self.out) and os.path.dirname(pf) != self.out:
                try:
                    os.kill(rec['pid'], signal.SIGTERM)
                except OSError:
                    pass


def _trace(d):
    p = os.path.join(d, 'trace.jsonl')
    return [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []


def _cache_info(d):
    """what the stage cache and the worker did for a build (tool/speed), from its log's CHARKIT_CACHE / _WORKER lines."""
    p = os.path.join(d, 'build.log')
    if not os.path.exists(p):
        return None
    lines = [l for l in open(p) if l.startswith(('CHARKIT_CACHE', 'CHARKIT_WORKER'))]
    return [l.strip()[:200] for l in lines[:6]] or None


def _counts(qa):
    c = {'PASS': 0, 'WARN': 0, 'FAIL': 0}
    for x in checks.graded(qa).values():
        c[x['status']] += 1
    return c


def _public(ck):
    return {k: v for k, v in ck.items() if not k.startswith('_')}


# ------------------------------------------------------------------------------------------------------------ worker
def worker_up(log=print):
    """start the persistent Blender worker for this checkout when tool/speed has landed and none is running ->
    True when this run started it (and so stops it at the end)."""
    if not os.path.exists(os.path.join(ROOT, 'charkit', 'worker.py')):
        return False
    try:
        from . import worker
        I = worker.info()
        if I and worker._alive(I['pid']):
            return False
        r = subprocess.run([PY, '-m', 'charkit', 'worker', 'start'], cwd=ROOT, capture_output=True, text=True, timeout=300)
        log('  worker start: %s' % (r.stdout.strip().splitlines() or [''])[-1])
        return r.returncode == 0
    except Exception as e:
        log('  worker unavailable: %s' % e)
        return False


def worker_down():
    subprocess.run([PY, '-m', 'charkit', 'worker', 'stop'], cwd=ROOT, capture_output=True, text=True, timeout=120)


# ------------------------------------------------------------------------------------------------------------ the loop
def _budget(b):
    """'6' -> (6 builds, None); '45m' -> (None, 2700 s)."""
    if b is None:
        return 8, None
    b = str(b)
    if b.endswith('m'):
        return None, float(b[:-1]) * 60
    if b.endswith('s'):
        return None, float(b[:-1])
    return int(b), None


def tune(spec_path, out=None, budget=None, review=False, args=(), only=None, config=None, rounds=None, min_gain=None,
         fit_budget=None, workers=None, fresh=False, use_worker=True, log=say):
    from . import fitters as FT, gate, history
    spec_path = _path(spec_path)
    spec = json.load(open(spec_path))
    name = spec['name']
    out = _path(out or os.path.join('charkit', 'out', 'tune', name))
    os.makedirs(out, exist_ok=True)
    from . import manifest
    rspec = manifest.resolve(json.loads(json.dumps(spec)))
    cfg = load_config(spec, config)
    stop_cfg = cfg.get('stop', {})
    rounds = rounds or stop_cfg.get('rounds', 2)
    min_gain = stop_cfg.get('min_gain', 0.5) if min_gain is None else min_gain
    max_builds, max_s = _budget(budget)
    run_id = time.strftime('%Y%m%d-%H%M%S')
    R = Record(os.path.join(out, 'tune.jsonl'))
    B = Builder(out, run_id, name, fresh, log)
    reg = FT.registry(cfg, budget=fit_budget, only=only, workers=workers)
    pidf = os.path.join(out, '.pid.json')
    json.dump({'pid': os.getpid(), 'label': 'tune ' + name, 'cmd': ['charkit', 'tune', _rel(spec_path)], 'cwd': os.getcwd(),
               'root': ROOT, 'started': time.strftime('%Y-%m-%dT%H:%M:%S')}, open(pidf, 'w'))

    def on_term(*_):
        B.stop()
        raise SystemExit('tune stopped')
    old_term = signal.signal(signal.SIGTERM, on_term)
    t0 = time.time()
    started_worker = worker_up(log) if use_worker else False
    R.write('begin', run=run_id, spec=_rel(spec_path), name=name, out=_rel(out), args=list(args), budget=budget,
            max_builds=max_builds, max_seconds=max_s, rounds=rounds, min_gain=min_gain, config=cfg.get('_path'),
            tradeoffs=cfg.get('tradeoffs', []), fitters=[f.describe() for f in reg], git=B.code, worker=started_worker)
    log('tune %s: run %s -> %s' % (name, run_id, _rel(out)))
    for f in reg:
        log('  fitter %-8s %s' % (f.name, 'ready' if f.landed else 'STUB (%s not landed)' % f.branch))
    cks, fits = [], {}
    try:
        def left():                                          # the loop's builds; one is kept for the final build
            return (None if max_builds is None else max_builds - 1 - B.builds,
                    None if max_s is None else max_s - (time.time() - t0))

        def checkpoint(label, sp, a, boards=BOARDS_STEP, extra=()):
            ck = B.build(len(cks), label, sp, a, boards, extra)
            cks.append(ck)
            R.write('checkpoint', **_public(ck))
            if ck['ok']:
                log('  ck%d %-18s %s  score %.2f  pass %d warn %d fail %d%s' % (
                    ck['id'], label, ck['summary'], ck['score'], ck['counts']['PASS'], ck['counts']['WARN'],
                    ck['counts']['FAIL'], '  (reused)' if ck.get('reused') else ''))
            else:
                log('  ck%d %s: build FAILED' % (ck['id'], label))
            return ck

        def start(ck):
            """what a fitter starts from: exactly what the checkpoint built (its resolved spec)."""
            return _path(ck.get('resolved') or ck['spec'])

        def compare(best, ck, fit=None):
            rem = history.remeasured(best.get('git'), ck.get('git'), list(checks.graded(ck.qa)))
            d = accept(best.qa, ck.qa, cfg.get('tradeoffs', []), rem) if ck['ok'] else \
                {'verdict': 'reject', 'why': 'the build failed', 'gain': 0, 'rows': [], 'regressed': [], 'traded': [], 'improved': []}
            dis = disagreement(fit, ck, best) if fit and ck['ok'] else {}
            R.write('compare', checkpoint=ck['id'], against=best['id'], verdict=d['verdict'], why=d['why'], gain=d['gain'],
                    score=d.get('score'), regressed=d['regressed'], traded=d['traded'], improved=d['improved'],
                    remeasured=rem, disagree=dis,
                    rows=[r for r in d['rows'] if r['verdict'] not in ('ungraded',)])
            log('    %s ck%d vs ck%d: %s' % (d['verdict'].upper(), ck['id'], best['id'], d['why']))
            return d

        best = checkpoint('start', spec_path, list(args))
        if not best['ok']:
            raise SystemExit('the starting build failed: %s' % best.get('why', '')[-400:])
        scores = [best['score']]
        last_input = {}
        reason = None
        rnd = 0
        while True:
            rnd += 1
            changed = False
            for F in reg:
                bl, sl = left()
                if (bl is not None and bl <= 0) or (sl is not None and sl <= 0):
                    break
                fail = failing(best.qa)
                if not F.targets_of(fail) and F.name != 'options':
                    continue
                if F.name == 'options':
                    todo = F.pending(fail)
                    if not todo:
                        continue
                    for o in todo:
                        bl, sl = left()
                        if (bl is not None and bl <= 0) or (sl is not None and sl <= 0):
                            break
                        res = F.run(start(best), best['args'], os.path.join(out, 'fit_r%d_options' % rnd), log, option=o)
                        R.write('fit', round=rnd, from_checkpoint=best['id'], **_fit_public(res))
                        if res['status'] != 'fitted':
                            continue
                        changed = True
                        ck = checkpoint('option-' + o['name'], res['spec'], res['args'])
                        if compare(best, ck)['verdict'] == 'accept':
                            best = ck
                    continue
                if last_input.get(F.name) == best['id']:
                    continue                                 # nothing it reads changed since it last ran
                last_input[F.name] = best['id']
                fdir = os.path.join(out, 'fit_r%d_%s' % (rnd, F.name))
                log('  fit %s from ck%d%s' % (F.name, best['id'], '' if F.landed else ' (STUB)'))
                res = F.run(start(best), best['args'], fdir, log)
                res.setdefault('fitter', F.name)
                fits[F.name] = dict(res, from_checkpoint=best['id'], round=rnd)
                R.write('fit', round=rnd, from_checkpoint=best['id'], **_fit_public(res))
                if res['status'] != 'fitted':
                    log('    %s: %s%s' % (F.name, res['status'], ' (%s)' % res.get('why', '')[:160] if res.get('why') else ''))
                    continue
                changed = True
                log('    %s moved %d knobs: %s' % (F.name, len(res['changed']), ', '.join(
                    '%s %.4g->%.4g' % (k, a, b) for k, (a, b) in list(res['changed'].items())[:8])))
                ck = checkpoint(F.name, res['spec'], res.get('args', best['args']))
                d = compare(best, ck, res)
                if d['verdict'] == 'accept':
                    best = ck
                    fits[F.name]['accepted'] = ck['id']
                    last_input[F.name] = ck['id']             # its own output: it runs again only after another change
                elif len(res.get('blocks') or {}) > 1:
                    for blk in sorted(res['blocks']):
                        bl, sl = left()
                        if (bl is not None and bl <= 0) or (sl is not None and sl <= 0):
                            break
                        sp = FT.with_block(start(best), res['spec'], F.knobs, blk,
                                           os.path.join(fdir, '%s.%s.json' % (name, blk)))
                        ck = checkpoint('%s-%s' % (F.name, blk), sp, res.get('args', best['args']))
                        if compare(best, ck, res)['verdict'] == 'accept':
                            best = ck
                            fits[F.name]['accepted'] = ck['id']
                            last_input[F.name] = ck['id']
            scores.append(best['score'])
            bl, sl = left()
            reason = stop_reason(scores, all_pass(best.qa), bl, sl, changed, rounds, min_gain)
            R.write('round', round=rnd, best=best['id'], score=best['score'], scores=scores, changed=changed, stop=reason)
            log('  round %d: best ck%d score %.2f%s' % (rnd, best['id'], best['score'], ' -> stop: ' + reason if reason else ''))
            if reason:
                break
        R.write('stop', reason=reason, best=best['id'], score=best['score'], builds=B.builds,
                seconds=round(time.time() - t0, 1))
        # the end: the best state with every board (the review's pictures; the QA should repeat exactly)
        final = checkpoint('final', _path(best['spec']), best['args'], BOARDS_FINAL, ['--vrm'] if review else [])
        repeat = None
        if final['ok']:
            rows = gate.compare_qa(best.qa, final.qa)
            repeat = [r['check'] for r in rows if r['verdict'] != 'ungraded']
            R.write('repeat', checkpoint=final['id'], of=best['id'], differs=repeat)
            if repeat:
                log('  final differs from ck%d in: %s' % (best['id'], ', '.join(repeat)))
        end_ck = final if final['ok'] else best
        # the fitters' sensitivity at the end state (a fit's own table is measured at its start)
        esp = os.path.join(_path(end_ck['out']), name + '.spec.json')
        for F in reg:
            if hasattr(F, 'sensitivity_at') and F.landed and os.path.exists(esp):
                log('  sensitivity of the %s fitter at ck%d' % (F.name, end_ck['id']))
                T_ = F.sensitivity_at(esp, os.path.join(out, 'sensitivity_%s' % F.name), log)
                if T_:
                    fits.setdefault(F.name, {'fitter': F.name})['sensitivity'] = T_
                    fits[F.name]['sensitivity_at'] = end_ck['id']
                R.write('sensitivity', fitter=F.name, at=end_ck['id'], ok=bool(T_),
                        path=_rel(os.path.join(out, 'sensitivity_%s' % F.name, 'sensitivity.json')))
        from . import triage
        T = triage.run(end_ck, fits, reg, cks, read(os.path.join(out, 'tune.jsonl')), cfg, rspec,
                       os.path.join(out, 'triage'), nondeterministic=repeat or [])
        R.write('triage', items=len(T['items']), path=_rel(T['json']), md=_rel(T['md']),
                classes=T['classes'])
        log('  triage: %d work items -> %s' % (len(T['items']), _rel(T['md'])))
        rv = None
        if review:
            from . import review as RV
            rv = RV.prepare(_path(end_ck['out']), rspec, T, run=run_id)
            R.write('review', board=_rel(rv['board']), page=_rel(rv['page']), notes=_rel(rv['notes']))
            log('  review board: %s\n  notes: %s\n  serve: python -m charkit review serve %s' % (
                _rel(rv['board']), _rel(rv['notes']), _rel(_path(end_ck['out']))))
        summary = {'run': run_id, 'spec': _rel(spec_path), 'out': _rel(out), 'stop': reason, 'best': best['id'],
                   'final': end_ck['id'], 'builds': B.builds, 'seconds': round(time.time() - t0, 1),
                   'checkpoints': [{k: v for k, v in _public(c).items() if k in ('id', 'label', 'out', 'args', 'summary', 'score', 'counts', 'reused', 'ok', 'seconds')}
                                   for c in cks],
                   'fitters': {f.name: ('ready' if f.landed else 'STUB') for f in reg},
                   'work_items': _rel(T['json']), 'review': rv and {k: _rel(v) for k, v in rv.items()}}
        json.dump(summary, open(os.path.join(out, 'tune.json'), 'w'), indent=1, default=str)
        R.write('end', **{k: v for k, v in summary.items() if k != 'checkpoints'})
        return summary
    finally:
        R.close()
        signal.signal(signal.SIGTERM, old_term)
        if started_worker:
            worker_down()
        if os.path.exists(pidf):
            os.remove(pidf)


def _fit_public(res):
    """a fit result for the record: the sensitivity table by reference (it is in the fit's folder), not inline."""
    r = {k: v for k, v in res.items() if k not in ('sensitivity',)}
    r['sensitivity'] = bool(res.get('sensitivity'))
    for k in ('spec', 'report'):
        if r.get(k):
            r[k] = _rel(r[k])
    return r


def disagreement(fit, ck, start=None, band=0.5):
    """checks where the fitter's fast evaluator measured a severity the full build's QA doesn't reproduce (by more than
    `band` warn bands): its 'after' against the candidate's build and, when given, its 'before' against the build it
    started from -> {check: [evaluator, build]} (the larger gap of the two)."""
    out = {}
    for k, (before, after) in (fit.get('predicted') or {}).items():
        for pred, c in ((after, ck.qa.get('checks', {}).get(k)), (before, (start.qa.get('checks', {}) if start else {}).get(k))):
            if pred is None or not isinstance(c, dict) or c.get('status') not in checks.GRADED:
                continue
            a, b = checks.severity(k, pred), checks.severity(k, c.get('value'), c.get('status'))
            if a is not None and b is not None and abs(a - b) > band and abs(a - b) > out.get(k, (0, 0, 0))[2]:
                out[k] = (pred, c.get('value'), abs(a - b))
    return {k: [a, b] for k, (a, b, _) in out.items()}


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    S = tune(args[0], out=opt('--out'), budget=opt('--budget'), review='--review' in args,
             args=shlex.split(opt('--args', '')), only=opt('--only') and opt('--only').split(','), config=opt('--config'),
             rounds=opt('--rounds') and int(opt('--rounds')), min_gain=opt('--min-gain') and float(opt('--min-gain')),
             fit_budget=opt('--fit-budget') and int(opt('--fit-budget')), workers=opt('--workers') and int(opt('--workers')),
             fresh='--fresh' in args, use_worker='--no-worker' not in args)
    print('tune: stop %s, best ck%s, %d builds, %.0f s; work items %s' % (S['stop'], S['best'], S['builds'], S['seconds'],
                                                                          S['work_items']))
