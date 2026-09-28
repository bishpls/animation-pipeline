"""Residual triage: every check still WARN or FAIL after the tune loop, classified by why the loop couldn't fix it, with
its evidence, and ranked into work items (docs/CHARKIT.md §4).

    python -m charkit triage DIR [--spec SPEC]     # DIR: a tune run's folder (tune.jsonl) or one build's (qa/qa.json)

The classes (the first that applies; the others that also apply are listed as `also`):
  measurement uncertain  the number itself is in doubt: the fast evaluator predicted a severity the build doesn't
                         reproduce (or disagrees with the final build), the build didn't repeat, the check flags missing
                         data or thin data ("few pixels"), or the value is within the error the check itself states (a
                         scale caution's percentage) or the reference's (the tune config's `uncertain`) of passing. A
                         standing caution alone is soft: listed, not the class
  trade-off              fixing it costs another check: a checkpoint that improved it was rejected because another check
                         regressed (built and measured), a trade-off rule let it get worse to pay for another, or every
                         knob that improves it worsens another check (the sensitivity table: which, and by how much per
                         unit of gain)
  knob at a bound        the knobs that would improve it are at their range's end (which knob, which bound, its value), or
                         would reach it before the check passes
  needs a knob           no fitted knob moves it (the sensitivity tables), or every knob that moves it is already at its
                         best for it; hand knobs in the spec that may (the knob inventory) and the fitter that will own
                         them are listed
  needs a capability     what it measures is not a parameter at all: a template or geometry change
                         (charkit.checks.CAPABILITY names which)
  not in the objective   a knob improves it with no cost, but no fitter's objective includes the check
(A free knob that would improve a targeted check at no cost to another check, moving away from its template default,
is a trade-off with the fit's pull toward the defaults.)
Review tickets (charkit/refs/NAME/tickets.json, charkit/review.py) join the list: a measurement the metrics missed
(`needs a measurement`, until a check of that name appears in the QA; where the ticket has a prototype computed from
the QA's own tables it is measured again on this build: status PROVISIONAL PASS/WARN/FAIL), and reviewer notes on
existing checks (evidence, and a higher rank).

Each item carries its evidence: the value and status, the severity (warn bands past the pass limit), the overlays, the
reference it is measured against and the manifest's authority for its measure (with the reference's cautions), the knobs
and conflicts behind its class. Rank: severity (capped at charkit.checks.CAP) times visibility (face, eyes and silhouette
first, internals last), times 1.5 with a reviewer's note, times 0.6 when it is measured against a reference that isn't
its measure's authority.
"""
import fnmatch, json, os, re

from . import checks

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLASSES = ('measurement uncertain', 'trade-off', 'knob at a bound', 'needs a knob', 'needs a capability',
           'not in the objective', 'needs a measurement')
NOISE = checks.NOISE


def _path(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def _rel(p):
    return os.path.relpath(p, ROOT) if p and os.path.isabs(p) and p.startswith(ROOT) else p


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# ------------------------------------------------------------------------------------------------------------ sensitivity
def movers(check, tables, knobs, spec):
    """what the fitters' sensitivity tables (charkit.fitkit's schema charkit.sensitivity/1, or a bare {knob: entry}) say
    about one check -> None when no table measures it, else a list of
    {fitter, knob, gain (warn bands per step, in its improving direction; None at its optimum), moves (the larger
    severity change per step either way), dir (+1/-1), room (steps to the bound that way), x, bound, conflicts
    [{check, cost per step}]}."""
    seen, out = False, []
    for fname, T in tables.items():
        T = (T or {}).get('knobs', T) if isinstance(T, dict) and 'schema' in T else (T or {})
        for k, t in T.items():
            M = t.get('measures') or {}
            e = M.get(check)
            if e is None:
                continue
            seen = True
            at, lo_v, hi_v = e.get('at'), e.get('minus'), e.get('plus')
            if not all(_num(v) for v in (at, lo_v, hi_v)):
                continue
            s0, sp, sm = checks.severity(check, at), checks.severity(check, hi_v), checks.severity(check, lo_v)
            if s0 is None or sp is None or sm is None:
                continue
            dp, dm = sp - s0, sm - s0
            moves = max(abs(dp), abs(dm))
            if moves < NOISE:
                continue
            d = +1 if dp < -NOISE and dp <= dm else -1 if dm < -NOISE else None
            K = knobs.get(fname, {}).get(k) or {}
            step = K.get('step') or t.get('step') or 1.0
            lo, hi = K.get('bounds') or t.get('bounds') or (None, None)
            from .fitters import get
            x = get(spec, K['path'], K.get('default')) if K.get('path') else t.get('value', t.get('x'))
            room = None
            if d is not None and _num(x) and lo is not None:
                room = ((hi - x) if d > 0 else (x - lo)) / step
            conf = []
            if d is not None:
                for m, f in M.items():
                    if m == check or m.split('.')[0] == check or m.endswith('.ours'):
                        continue
                    a, b = f.get('at'), f.get('plus' if d > 0 else 'minus')
                    if not (_num(a) and _num(b)):
                        continue
                    sa, sb = checks.severity(m, a), checks.severity(m, b)
                    cost = sb - sa if sa is not None and sb is not None else 0.0
                    if cost > NOISE:
                        conf.append({'check': m, 'cost': round(cost, 3)})
                conf.sort(key=lambda c: -c['cost'])
            out.append({'fitter': fname, 'knob': k, 'gain': round(-(dp if d == 1 else dm), 3) if d else None,
                        'moves': round(moves, 3), 'dir': d, 'room': None if room is None else round(room, 2),
                        'x': x, 'default': K.get('default'), 'bound': (hi if d and d > 0 else lo) if d else None,
                        'conflicts': conf[:4]})
    return out if seen else None


# ------------------------------------------------------------------------------------------------------------ evidence
def build_evidence(recs, check):
    """what the tune's builds say about a check: rejected checkpoints that improved it while others regressed, and
    accepted ones where a rule let it get worse -> (conflicts, traded)."""
    conflicts, traded = [], []
    labels = {r['id']: r['label'] for r in recs if r.get('event') == 'checkpoint'}
    for r in recs:
        if r.get('event') != 'compare':
            continue
        rows = {x['check']: x for x in r.get('rows') or []}
        mine = rows.get(check)
        if r['verdict'] == 'reject' and mine and r.get('regressed'):
            s0 = checks.severity(check, mine['base'][0], mine['base'][1])
            s1 = checks.severity(check, mine['cand'][0], mine['cand'][1])
            others = [g for g in r['regressed'] if g['check'] != check]
            # a real gain only: a quarter of a warn band, or a tenth of how far it was from passing
            if s0 is not None and s1 is not None and s0 - s1 >= max(0.25, 0.1 * s0) and others:
                conflicts.append({'checkpoint': r['checkpoint'], 'label': labels.get(r['checkpoint'], r.get('label')),
                                  'against': r['against'], 'gain': [mine['base'], mine['cand']],
                                  'regressed': [[g['check'], g['base'], g['cand']] for g in others]})
        for t in r.get('traded') or []:
            if t['check'] == check:
                traded.append(dict(t, checkpoint=r['checkpoint']))
    return conflicts, traded


def uncertainty(check, c, ctx):
    """-> (strong flags, soft flags): reasons to doubt the number."""
    strong, soft = [], []
    for k in ('missing',):
        if _num(c.get(k)) and c[k] > 0:
            strong.append('%s %.0f%% of it unmeasured' % (k, 100 * c[k]))
    kind, p, w, wo = checks.rule(check)
    for k in ('caution', 'cautions', 'uncertain'):
        if not c.get(k):
            continue
        txt = c[k] if isinstance(c[k], str) else json.dumps(c[k])
        # a standing caution (the sheet's scale, say) is soft, unless the check is within the error it states or its
        # data is thin
        if re.search(r'\bfew\b', txt):
            strong.append('the check cautions: %s' % txt[:160])
            continue
        m = re.search(r'([+-]?\d+(?:\.\d+)?)\s*%', txt)
        v, d = c.get('value'), c.get('design')
        err = None
        if m and kind == 'ratio':
            err = abs(float(m.group(1))) / 100
        elif m and kind == 'abs' and _num(d):
            err = abs(float(m.group(1))) / 100 * abs(d)
        x = (abs(v - 1) if kind == 'ratio' else abs(v)) if _num(v) and kind in ('ratio', 'abs') else None
        if err is not None and x is not None and x - p <= err:
            strong.append('within its own stated error (%.3g) of passing: %s' % (err, txt[:120]))
        else:
            soft.append('caution: %s' % txt[:160])
    if _num(c.get('confidence')) and c['confidence'] < 0.5:
        strong.append('confidence %.2f' % c['confidence'])
    if _num(c.get('rows')) and c['rows'] < 8:
        strong.append('measured over %d rows only' % c['rows'])
    if check in ctx.get('disagree', {}):
        p, b = ctx['disagree'][check]
        strong.append('the fast evaluator predicted %s, the build measured %s' % (p, b))
    if check in ctx.get('nondeterministic', []):
        strong.append('the final build did not repeat the best checkpoint\'s value')
    if wo:
        soft.append('warn-only (a framing measure, never fails)')
    _, src = checks.measure(check)
    U = (ctx.get('config') or {}).get('uncertain', {}).get(src) if src else None
    v = c.get('value')
    if U and _num(v):
        err = U.get(kind) if isinstance(U, dict) else U
        x = abs(v - 1) if kind == 'ratio' else abs(v) if kind == 'abs' else None
        if err and x is not None and x - p <= err:
            strong.append('within the %s\'s stated error (%s) of passing' % (src, err))
    return strong, soft


def reference(check, spec):
    """the manifest's authority for the check's measure, and the reference it is measured against, with cautions."""
    m, src = checks.measure(check)
    ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else {}
    auth = (ref.get('authority') or {}).get(m) if m else None
    M = {}
    if ref.get('manifest') and os.path.exists(_path(ref['manifest'])):
        M = json.load(open(_path(ref['manifest'])))
    R = M.get('references', {})
    out = {'measure': m, 'measured_against': src, 'authority': auth}
    if src and src in R:
        out['against_path'] = R[src]['path']
        if R[src].get('cautions'):
            out['cautions'] = R[src]['cautions']
    if auth and auth in R:
        out['authority_path'] = R[auth]['path']
    if auth and src and auth != src:
        out['note'] = 'measured against the %s; the %s is the authority for %s' % (src, auth, m)
    return out


# words too common in check names to pick a knob by, and what a check's word means in knob names
GENERIC = {'sheet', 'body', 'shape', 'front', 'back', 'three', 'quarter', 'profile', 'face', 'width', 'length', 'iou',
           'mid', 'lit', 'shade', 'ratio', 'span', 'run', 'eye', 'expr', 'palette', 'hair'}
SYNONYMS = {'hem': ['skirt'], 'feet': ['height', 'heads_tall', 'leg'], 'top': ['height', 'heads_tall', 'crown'],
            'leg': ['leg', 'height'], 'sleeves': ['sleeve', 'puff'], 'boot': ['boot'], 'skin': ['skin', 'slim', 'hip'],
            'outfit': ['garments'], 'neck': ['neck'], 'jaw': ['jaw', 'chin', 'low'], 'nose': ['nose'], 'chin': ['chin']}


# ------------------------------------------------------------------------------------------------------------ classify
def classify(check, c, ctx):
    """one residual check -> (class, detail sentence, evidence dict, also [other classes])."""
    fitters, spec = ctx['fitters'], ctx['spec']
    sev = checks.sev_of(check, c)
    strong, soft = uncertainty(check, c, ctx)
    conflicts, traded = build_evidence(ctx.get('records', []), check)
    mv = movers(check, ctx.get('tables', {}), ctx.get('knobs', {}), spec)
    ev = {'uncertain': strong + soft} if strong or soft else {}
    cands = []                                   # (class, detail) in order of precedence
    if strong:
        cands.append(('measurement uncertain', '; '.join(strong)))
    if conflicts:
        x = max(conflicts, key=lambda x: (checks.severity(check, x['gain'][0][0], x['gain'][0][1]) or 0) -
                                         (checks.severity(check, x['gain'][1][0], x['gain'][1][1]) or 0))
        cands.append(('trade-off', 'ck%d (%s) improved it (%s -> %s) but was rejected for what it cost: %s' % (
            x['checkpoint'], x.get('label') or '?', x['gain'][0][0], x['gain'][1][0],
            ', '.join('%s %s -> %s' % (g, b[1], c[1] or 'gone') for g, b, c in x['regressed']))))
        ev['built_conflicts'] = conflicts
    if traded:
        t = traded[-1]
        if t['for'] == 'noise':
            cands.append(('trade-off', 'allowed across its limit in ck%d (%s -> %s, %.2f warn bands: a flip within the '
                          'measurement\'s error, paid for by the checkpoint\'s net gain): %s' % (
                              t['checkpoint'], t['base'][0], t['cand'][0], t['cost'] or 0, t['rule'])))
        else:
            cands.append(('trade-off', 'allowed to get worse in ck%d (%s -> %s) to pay for %s (%.2f warn bands better): %s' % (
                t['checkpoint'], t['base'][0], t['cand'][0], t['for'], t['gain'], t['rule'])))
        ev['traded'] = traded
    owners = [f for f in fitters if f.targets_of([check])]
    ev['fitters'] = [{'name': f.name, 'stub': not f.landed} for f in owners]
    cap = checks.capability(check)
    if isinstance(c.get('missing'), str):                  # the template has nothing close: an addition, not a knob
        cands.append(('needs a capability', '%s (closest: %s)' % (c['missing'], c.get('match'))))
    if mv is None or not mv:
        # nothing measured moves it
        stubs = [f.name for f in owners if not f.landed]
        hand = [k for k in ctx.get('inventory', {}) if any(k == s or k.startswith(s + '.') for s in checks.sections(check))
                and not any(f.owner_of(k) and f.landed for f in fitters)]
        # the knobs whose path shares a word with the check first (pupil -> iris.pupil_rz, hem -> garments.skirt.*)
        words = set()
        for w in check.split('_'):
            if len(w) >= 3 and w not in GENERIC:
                words.update(SYNONYMS.get(w, [w]))
        hand.sort(key=lambda k: -sum(w in k for w in words))
        ev['hand_knobs'] = hand[:12]
        if mv == [] :
            what = 'none of the %s fitter\'s knobs moves it by more than %.2f warn bands a step' % (
                '/'.join(sorted(ctx.get('tables', {}))), NOISE)
        else:
            what = 'no fitter measures it'
        if cap:
            cands.append(('needs a capability', '%s; it measures %s' % (what, cap)))
        else:
            cands.append(('needs a knob', what + ('; hand knobs that may: %s' % ', '.join(hand[:6]) if hand else '') +
                          ('; %s (not landed) will target it' % ', '.join('the %s fitter' % s for s in stubs) if stubs else '')))
    else:
        ev['knobs'] = mv
        imp = [m for m in mv if m['dir']]
        if not imp:
            names = ', '.join(m['knob'] for m in mv[:4])
            if cap:
                cands.append(('needs a capability', '%s move it, but each is already at its best for it; it measures %s' % (names, cap)))
            else:
                cands.append(('needs a knob', '%s move it, but each is already at its best for it: it needs a direction the '
                              'template doesn\'t have' % names))
        else:
            blocked = [m for m in imp if m['room'] is not None and m['room'] < 0.5]
            free = [m for m in imp if m not in blocked]
            clean = [m for m in free if not m['conflicts']]
            confl = [m for m in free if m['conflicts']]
            if clean:
                reach = sum(m['gain'] * (m['room'] if m['room'] is not None else 99) for m in clean)
                in_obj = any(f.targets_of([check]) and f.landed for f in fitters if f.name in {m['fitter'] for m in clean})
                if reach < sev:
                    m = max(clean, key=lambda m: m['gain'])
                    cands.append(('knob at a bound', '%s improves it %.2f warn bands a step at no cost, but reaches its bound '
                                  '(%s) %.1f steps away, before the check passes (%.2f short)' % (
                                      m['knob'], m['gain'], m['bound'], m['room'] or 0, sev - reach)))
                elif not in_obj:
                    m = max(clean, key=lambda m: m['gain'])
                    cands.append(('not in the objective', '%s improves it %.2f warn bands a step at no cost, but no fitter\'s '
                                  'objective includes %s' % (m['knob'], m['gain'], check)))
                else:
                    m = max(clean, key=lambda m: m['gain'])
                    away = _num(m.get('default')) and _num(m['x']) and (m['x'] - m['default']) * m['dir'] >= 0
                    acc = (ctx.get('accepted') or {}).get(m['fitter'])
                    if not acc:
                        cands.append(('trade-off', '%s improves it %.2f warn bands a step at no cost to another check, but the '
                                      '%s fitter\'s joint fit wasn\'t accepted from here (%s): its solution trades this '
                                      'against its other terms, or the build rejected it' % (
                                          m['knob'], m['gain'], m['fitter'], ctx.get('fit_state', {}).get(m['fitter'], 'not run'))))
                    elif away:
                        cands.append(('trade-off', '%s improves it %.2f warn bands a step at no cost to another check, but '
                                      'moves further from its template default (%s, now %s): the fit\'s pull toward the '
                                      'defaults holds it' % (m['knob'], m['gain'], m['default'], m['x'])))
                    else:
                        cands.append(('measurement uncertain', 'the table says %s improves it %.2f warn bands a step at no '
                                      'cost, yet the fit left it: a non-linear response, or a table measured elsewhere'
                                      % (m['knob'], m['gain'])))
            if confl and not clean:
                m = max(confl, key=lambda m: m['gain'])
                x = m['conflicts'][0]
                cands.append(('trade-off', 'every knob that improves it costs another check: %s gains %.2f warn bands a step '
                              'here and costs %s %.2f (%.1fx)' % (m['knob'], m['gain'], x['check'], x['cost'],
                                                                   x['cost'] / max(m['gain'], 1e-6))))
                ev['conflicts'] = [{'knob': m['knob'], 'gain': m['gain'], 'costs': m['conflicts']} for m in confl]
            if blocked:
                b = ', '.join('%s at its %s bound %s (%s)' % (m['knob'], 'upper' if m['dir'] > 0 else 'lower', m['bound'], m['x'])
                              for m in blocked)
                ev['bounds'] = [{'knob': m['knob'], 'bound': m['bound'], 'value': m['x'], 'gain': m['gain']} for m in blocked]
                cands.append(('knob at a bound', 'the knobs that would improve it are at their range\'s end: %s' % b))
    if not cands:
        cands.append(('needs a capability', cap or 'no class fits the evidence'))
    # measurement uncertainty is the primary class only when it is strong
    cls, detail = cands[0]
    also = []
    for k, _ in cands[1:]:
        if k != cls and k not in also:
            also.append(k)
    if soft and 'measurement uncertain' not in [cls] + also:
        also.append('measurement uncertain')
    return cls, detail, ev, also


# ------------------------------------------------------------------------------------------------------------ the list
def tickets_path(spec):
    ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else {}
    base = os.path.dirname(_path(ref['manifest'])) if ref.get('manifest') else _path(os.path.join('charkit', 'refs', spec['name']))
    return os.path.join(base, 'tickets.json')


def load_tickets(spec):
    p = tickets_path(spec)
    return json.load(open(p)).get('tickets', []) if os.path.exists(p) else []


def items(qa, ctx, build_dir=None):
    """the ranked work items for a build's QA -> list of dicts."""
    out = []
    tickets = ctx.get('tickets', [])
    notes = {}
    for t in tickets:
        if t.get('status', 'open') == 'closed':
            continue
        for k in t.get('checks') or []:
            notes.setdefault(k, []).append(t)
    for k, c in checks.graded(qa).items():
        if c['status'] == 'PASS':
            continue
        cls, detail, ev, also = classify(k, c, ctx)
        sev = checks.sev_of(k, c)
        reg, vis = checks.region(k)
        ov = [o for o in checks.overlays(k) if not build_dir or os.path.exists(os.path.join(build_dir, o))]
        tk = [t for t in notes.get(k, []) if t.get('kind') == 'work']
        aw = checks.weight(k, (ctx['spec'].get('ref') or {}).get('authority') if isinstance(ctx['spec'].get('ref'), dict) else None)
        rank = min(sev, checks.CAP) * vis * (1.5 if tk else 1.0) * (1.0 if aw == 1.0 else 0.6)
        it = {'check': k, 'status': c['status'], 'value': c.get('value'), 'severity': round(sev, 3), 'region': reg,
              'visibility': vis, 'rank_score': round(rank, 3), 'class': cls, 'detail': detail, 'also': also,
              'evidence': dict(ev, values={x: c[x] for x in ('ours', 'design', 'ratios', 'per_height', 'regions', 'at', 'heights', 'mean', 'rows', 'eye', 'note')
                                           if x in c},
                               overlays=[os.path.join(_rel(build_dir), o) if build_dir else o for o in ov],
                               reference=reference(k, ctx['spec']),
                               limits=dict(zip(('kind', 'pass', 'warn', 'warn_only'), checks.rule(k))))}
        if tk:
            it['evidence']['review'] = [{'ticket': t['id'], 'note': t.get('text')} for t in tk]
        out.append(it)
    present = set((qa.get('checks') or {}).keys())
    for t in tickets:
        if t.get('kind') != 'measure' or t.get('status', 'open') == 'closed':
            continue
        name = t.get('proposed', {}).get('check')
        landed = bool(name) and name in present
        reg, vis = checks.region(t.get('region_check') or name or '')
        if t.get('region') in ('face', 'eyes', 'silhouette'):
            vis = max(vis, 0.9)
        rank = float(t.get('severity', 2)) * vis * 1.5
        # a proposed measure with a prototype is measured again on this build: the note is a tracked number now
        from .review import prototype
        pv = None if landed else prototype((t.get('proposed') or {}).get('proto'), qa)
        if pv and pv['status'] == 'PASS':
            rank *= 0.3
        out.append({'check': name or t['id'], 'status': 'LANDED' if landed else ('PROVISIONAL %s' % pv['status']) if pv else 'MISSING',
                    'value': pv['value'] if pv else (t.get('proposed') or {}).get('value'),
                    'severity': float(t.get('severity', 2)), 'region': t.get('region') or reg, 'visibility': vis,
                    'rank_score': round(0.2 * rank if landed else rank, 3), 'class': 'needs a measurement',
                    'detail': ('the check landed: grade it like the rest and close ticket %s' % t['id']) if landed else
                              'a reviewer saw "%s" that no check measures%s%s' % (
                                  t.get('text'), '; checks that passed and should have caught it: %s' % ', '.join(t.get('missed_by') or [])
                                  if t.get('missed_by') else '',
                                  '; its prototype reads %s (ours %s, design %s)' % (pv['value'], pv['ours'], pv['design']) if pv else ''),
                    'also': [], 'evidence': {'ticket': t['id'], 'note': t.get('text'), 'proposed': t.get('proposed'),
                                             'board': t.get('board'), 'reference': t.get('reference')}})
    out.sort(key=lambda i: -i['rank_score'])
    for i, it in enumerate(out):
        it['rank'] = i + 1
    return out


def markdown(items_, title, meta=None):
    L = ['# %s' % title, '']
    if meta:
        L += ['%s' % meta, '']
    by = {}
    for it in items_:
        by[it['class']] = by.get(it['class'], 0) + 1
    L.append('Classes: ' + ', '.join('%s %d' % (k, v) for k, v in sorted(by.items(), key=lambda kv: -kv[1])))
    L += ['', '| # | check | status | value | severity | where | class | why |', '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for it in items_:
        v = it['value']
        vs = ('%.4g' % v) if _num(v) else str(v)[:14]
        L.append('| %d | %s | %s | %s | %.2f | %s %.2f | %s | %s |' % (it['rank'], it['check'], it['status'], vs, it['severity'],
                                                                   it['region'], it['visibility'], it['class'],
                                                                   it['detail'].replace('|', '/')[:220]))
    L += ['', '## Evidence', '']
    for it in items_:
        e = it['evidence']
        L.append('### %d. %s: %s' % (it['rank'], it['check'], it['class']))
        L.append(it['detail'] + ('  (also: %s)' % ', '.join(it['also']) if it['also'] else ''))
        r = e.get('reference') or {}
        if r:
            L.append('- reference: measured against %s; authority for %s: %s%s' % (
                r.get('measured_against') or r.get('against') or '-', r.get('measure') or '-', r.get('authority') or '-',
                ' (cautions: %s)' % '; '.join(r['cautions']) if r.get('cautions') else ''))
        if e.get('values'):
            L.append('- values: `%s`' % json.dumps(e['values'], default=str)[:400])
        if e.get('overlays'):
            L.append('- overlays: ' + ', '.join('`%s`' % o for o in e['overlays']))
        for k in ('bounds', 'conflicts', 'built_conflicts', 'traded', 'uncertain', 'review', 'proposed'):
            if e.get(k):
                L.append('- %s: `%s`' % (k, json.dumps(e[k], default=str)[:500]))
        if e.get('knobs'):
            top = sorted(e['knobs'], key=lambda m: -(m['gain'] or 0))[:4]
            L.append('- knobs (per step): ' + '; '.join('%s %s%s' % (m['knob'], ('gain %.2f' % m['gain']) if m['gain'] else 'at its best',
                                                                    ', room %.1f' % m['room'] if m['room'] is not None else '') for m in top))
        if e.get('hand_knobs'):
            L.append('- hand knobs: ' + ', '.join(e['hand_knobs'][:10]))
        L.append('')
    return '\n'.join(L) + '\n'


def run(end_ck, fits, fitters, cks, recs, cfg, spec, out_dir, nondeterministic=(), agreement=None):
    """triage a tune run's end state -> {items, json, md, classes}; writes out_dir/work_items.json and .md and copies both
    beside the tune folder."""
    from . import fitters as FT
    os.makedirs(out_dir, exist_ok=True)
    bd = _path(end_ck['out'])
    qa = end_ck.qa if hasattr(end_ck, 'qa') else json.load(open(os.path.join(bd, 'qa', 'qa.json')))
    sp = os.path.join(bd, spec['name'] + '.spec.json')
    fspec = json.load(open(sp)) if os.path.exists(sp) else spec
    fspec.setdefault('ref', spec.get('ref'))
    tables = {n: f.get('sensitivity') for n, f in (fits or {}).items() if f.get('sensitivity')}
    disagree = {}
    for r in recs:
        if r.get('event') in ('compare', 'validate'):
            disagree.update(r.get('disagree') or {})
    disagree.update(agreement or {})
    accepted = {n: f.get('accepted') is not None for n, f in (fits or {}).items()}
    state = {n: ('accepted at ck%s' % f['accepted']) if f.get('accepted') is not None else f.get('status', 'not run')
             for n, f in (fits or {}).items()}
    ctx = {'fitters': fitters, 'spec': fspec, 'tables': tables, 'knobs': {f.name: f.knobs for f in fitters},
           'accepted': accepted, 'fit_state': state,
           'records': recs, 'config': cfg, 'disagree': disagree, 'nondeterministic': list(nondeterministic),
           'inventory': FT.inventory(fspec), 'tickets': load_tickets(spec)}
    its = items(qa, ctx, bd)
    classes = {}
    for it in its:
        classes[it['class']] = classes.get(it['class'], 0) + 1
    inv = ctx['inventory']
    own = {k: next((f.name + ('' if f.landed else ' (stub)') for f in fitters if f.owner_of(k)), 'hand') for k in inv}
    A = (spec.get('ref') or {}).get('authority') if isinstance(spec.get('ref'), dict) else None
    doc = {'character': spec['name'], 'build': _rel(bd), 'summary': qa.get('summary'), 'score': checks.score(qa, authority=A),
           'classes': classes, 'items': its,
           'fitters': [f.describe() for f in fitters],
           'knob_inventory': {'total': len(inv), 'by_owner': _count(own.values()), 'knobs': own}}
    jp, mp = os.path.join(out_dir, 'work_items.json'), os.path.join(out_dir, 'work_items.md')
    json.dump(doc, open(jp, 'w'), indent=1, default=str)
    md = markdown(its, 'Work items: %s' % spec['name'],
                  'Build `%s` (%s, score %.2f). Fitters: %s. Knobs: %d (%s).' % (
                      _rel(bd), qa.get('summary'), checks.score(qa, authority=A),
                      ', '.join('%s%s' % (f.name, '' if f.landed else ' (STUB)') for f in fitters), len(inv),
                      ', '.join('%s %d' % kv for kv in _count(own.values()).items())))
    open(mp, 'w').write(md)
    parent = os.path.dirname(out_dir)
    for p in (jp, mp):
        with open(os.path.join(parent, os.path.basename(p)), 'w') as f:
            f.write(open(p).read())
    return {'items': its, 'json': os.path.join(parent, 'work_items.json'), 'md': os.path.join(parent, 'work_items.md'),
            'classes': classes}


def _count(xs):
    c = {}
    for x in xs:
        c[x] = c.get(x, 0) + 1
    return dict(sorted(c.items(), key=lambda kv: -kv[1]))


# ------------------------------------------------------------------------------------------------------------ CLI
class _Ck(dict):
    @property
    def qa(self):
        return self['_qa']


def from_dir(d, spec_path=None, config=None):
    """re-triage a tune run's folder (from its tune.jsonl and the fits' tables) or a single build's."""
    from . import fitters as FT, manifest, tune as TU
    d = _path(d)
    recs = TU.read(os.path.join(d, 'tune.jsonl'))
    if recs:
        begin = next(r for r in recs if r['event'] == 'begin')
        spec_path = spec_path or begin['spec']
        cks = [r for r in recs if r['event'] == 'checkpoint' and r.get('ok')]
        stop = [r for r in recs if r['event'] == 'stop']
        best_id = stop[-1]['best'] if stop else cks[-1]['id']
        end = next((c for c in reversed(cks) if c['label'] == 'final'), None) or next(c for c in cks if c['id'] == best_id)
        fits = {}
        labels = {c['id']: c['label'] for c in cks}
        for r in recs:
            if r['event'] == 'fit' and r.get('status') in ('fitted', 'no change') and r.get('fitter') != 'options':
                f = dict(r)
                sp = os.path.join(d, 'fit_r%d_%s' % (r['round'], r['fitter']), 'sensitivity.json')
                if os.path.exists(sp):
                    f['sensitivity'] = json.load(open(sp))
                fits[r['fitter']] = f
            elif r['event'] == 'compare' and r['verdict'] == 'accept':
                lab = labels.get(r['checkpoint'], '')
                for n, f in fits.items():
                    if lab == n or lab.startswith(n + '-'):
                        f['accepted'] = r['checkpoint']
            elif r['event'] == 'sensitivity' and r.get('ok'):
                sp = _path(r['path'])
                if os.path.exists(sp):
                    fits.setdefault(r['fitter'], {'fitter': r['fitter']})['sensitivity'] = json.load(open(sp))
        nondet = next((r.get('differs') for r in recs if r['event'] == 'repeat'), [])
        out_dir = os.path.join(d, 'triage')
    else:
        end = {'out': _rel(d), 'id': 0}
        fits, cks, nondet, out_dir = {}, [], [], os.path.join(d, 'triage')
    raw = json.load(open(_path(spec_path)))
    spec = manifest.resolve(json.loads(json.dumps(raw)))
    cfg = TU.load_config(raw, config)
    reg = FT.registry(cfg)
    ck = _Ck(end, _qa=json.load(open(os.path.join(_path(end['out']), 'qa', 'qa.json'))))
    return run(ck, fits, reg, cks, recs, cfg, spec, out_dir, nondet)


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    T = from_dir(args[0], opt('--spec', 'charkit/spec/clawd.json' if not os.path.exists(os.path.join(_path(args[0]), 'tune.jsonl')) else None),
                 opt('--config'))
    print(open(T['md']).read()[:6000])
    print('wrote', _rel(T['json']), _rel(T['md']))
