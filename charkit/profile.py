"""A build's cost by stage (infra round 5, 2026-10-01: the default build's CPU doubled in a day and every merge passed the
relative CPU rule, so nobody saw where): wall and CPU seconds per stage, from what the build already records, and two
builds side by side.

    python -m charkit profile BUILD [--vs OTHER] [--gate GATE.json] [--json] [--md OUT.md] [--top N] [--budget]
    python -m charkit profile qa BUNDLE [--parts a,b] [--top N] [--out DIR] [--profile full|iterate] [--env K=V ..]
                                       [--no-cprofile]
        # the QA's parts one by one under cProfile on a bundle: per part its wall and CPU, the functions that cost it,
        # and its readings (each check's value and status)
    python -m charkit profile same A/qa_profile.json B/qa_profile.json    # two runs' readings equal? and their times

A build folder holds (charkit/cli.py, trace.py, qa3d.py):
  build_cpu.json   the whole build's CPU and wall seconds; `phases` {step: [wall, cpu]}: resolve (the references
                   produced, the design measured), the venv steps (code_head, code_body, hair_select, geom_hair,
                   pieces_hair, garments_geom), blender (the Blender process: CPU it and its threads used), qa (the
                   venv's QA), toon_boards, sheets. Builds before this round have no `phases`.
  trace.jsonl      the Blender stages (character, hair, face_shading, garments: `dt` wall, `cpu` since this round,
                   `snap` the trace's own snapshot after each), its spans (fit_cranium, bundle, look_export: `cpu_s`),
                   and the QA's parts (`qa.<part>` spans)
  qa/qa.json       measured.parts {part: [wall, cpu]} (the QA's CPU is the venv process's, every thread)
Rows (group, stage): venv (each step before Blender), blender (each stage and span, `other`: start-up, imports, the
scene's save and snapshots between stages), qa (each part, `other`: the design's loading and the report), total. A
figure the build didn't record is None (shown '-'), never guessed; an older build's venv steps are one row, 'before
Blender' (its wall: the build's wall less the trace's, its CPU unknown). A stage restored from a cache reads `cached`.
--gate: a gate report's json supplies an older build's step walls (its base_build or cand_build `steps`).

The budget (charkit/budget.json, infra round 5 task 2; REPORT ONLY: what blocks under policy K is Michael's call): the
default build's CPU seconds in total and per stage (gate conditions: the default spec, threads capped at 4, no boards),
set from the round's measured profile with headroom. `--budget` reads one build against it; the merge gate reports each
budgeted stage's CPU, baseline and candidate, against it (budget_rows), flagged WARN past it.
"""
import json, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_STEPS = ('resolve', 'code_head', 'code_body', 'hair_select', 'geom_hair', 'pieces_hair', 'garments_geom')
AFTER_STEPS = ('toon_boards', 'sheets')
WHAT = {        # what each stage buys (the notes' top-5 table reads these; a stage not here: its name says it)
    'venv/resolve': 'the spec resolved, the produced references (hull, outfit masks, hair layers) made or restored, '
                    'the design measured',
    'venv/hair_select': "the hull's hair selection the hair volume is made on (bodyeval.hair_selection)",
    'venv/pieces_hair': 'the hair pieces, lock shells and strokes (geom.hairpieces, hairink)',
    'venv/garments_geom': "the garments' geometry, venv-side (geomstage)",
    'blender/character': 'the head and body assembled in Blender (character.build)',
    'blender/look_export': "the look export (NAME.look.glb) every QA drawing reads",
    'blender/bundle': 'the geometry bundle the QA measures',
    'qa/declared': 'the declared checks (flags as declarations: shape, width, lines, strokes, tones, stairs)',
    'qa/look': 'the look checks (face_shadow_*, the drawn look against the design)',
    'qa/artifacts': "Michael's art_* flag checks (fragments, peeks, outline, terminator)",
    'qa/motion': 'motion QA: the skirt as cloth at the kick and the squat (motion_*)',
    'qa/face_flags': "the face's flag checks",
    'qa/face_region': 'the face regions against the design',
    'qa/skirt': 'the skirt checks',
}


def _load(p, default=None):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _trace(d):
    p = os.path.join(d, 'trace.jsonl')
    if not os.path.exists(p):
        return []
    out = []
    for line in open(p):
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def _r(x, n=1):
    return None if x is None else round(float(x), n)


def gate_steps(path, which=None):
    """a gate report's build steps (CHARKIT_PHASE walls) -> {build folder name: {step: wall}} for its baseline and
    candidate builds (the folder names its report gives: base_HEAD_..., cand_...)."""
    R = _load(path) or {}
    out = {}
    stem = os.path.basename(R.get('spec') or 'clawd.json').split('.')[0]
    opts = '_'.join(a.strip('-') for a in R.get('args') or ()) or 'default'
    for side, name in (('base_build', 'base_%s_%s_%s' % (R.get('head'), stem, opts)),
                       ('cand_build', 'cand_%s_%s_into_%s%s_%s' % (str(R.get('branch', '')).replace('/', '-'),
                                                                    R.get('tip'), R.get('head'), R.get('suffix') or '',
                                                                    opts))):
        st = (R.get(side) or {}).get('steps')
        if st:
            out[name] = st
    return out


def stages(d, steps=None):
    """a build folder's cost by stage -> dict(rows [dict(group, stage, wall, cpu, cached, note)], total dict(wall,
    cpu, threads), recorded {what was recorded}). steps: {step: wall} from a gate report, for a build with no
    `phases` in its build_cpu.json."""
    B = _load(os.path.join(d, 'build_cpu.json'), {}) or _load(os.path.join(d, 'cpu_seconds.json'), {}) or {}
    phases = B.get('phases') or {}
    recs = _trace(d)
    Q = (_load(os.path.join(d, 'qa', 'qa.json'), {}) or {}).get('measured') or {}
    rows = []

    def row(group, stage, wall, cpu, cached=False, note=''):
        rows.append(dict(group=group, stage=stage, wall=_r(wall), cpu=_r(cpu), cached=bool(cached), note=note))
    # ---- the venv's steps before Blender
    ends = [r for r in recs if r.get('event') == 'end']
    t_blender = ends[0]['total'] if ends else None
    t_all = ends[-1]['total'] if ends else None
    if phases:
        for k in VENV_STEPS:
            if k in phases:
                row('venv', k, phases[k][0], phases[k][1])
    elif steps:
        for k in VENV_STEPS:
            if k in steps:
                row('venv', k, steps[k], None, note='wall from the gate report')
    elif B.get('wall_seconds') and t_all is not None:
        row('venv', 'before Blender', B['wall_seconds'] - t_all, None, note="the build's wall less its trace's")
    # ---- Blender: its stages and spans (in the trace before the first `end`)
    bl = [r for r in recs if r.get('event') in ('stage', 'span') and (not ends or r['t'] <= ends[0]['t'] + 1e-6)]
    named_w = named_c = 0.0
    c_known = True
    snaps_w = snaps_c = 0.0
    for r in bl:
        nm = r.get('name')
        if r['event'] == 'span' and (nm or '').startswith('face.'):
            continue                                    # (inside the face_shading stage)
        cpu = r.get('cpu') if r.get('cpu') is not None else r.get('cpu_s')
        hit = (r.get('cache') or {}).get('hit') if isinstance(r.get('cache'), dict) else False
        row('blender', nm, r.get('dt'), cpu, cached=hit)
        named_w += r.get('dt') or 0.0
        if cpu is None:
            c_known = False
        else:
            named_c += cpu
        snaps_w += r.get('snap') or 0.0
        snaps_c += r.get('snap_cpu') or 0.0
    if snaps_w:
        row('blender', 'trace snapshots', snaps_w, snaps_c, note="the trace's scene snapshot after each stage")
        named_w += snaps_w
        named_c += snaps_c
    bw, bc = (phases.get('blender') or [None, None]) if phases else ((steps or {}).get('blender'), None)
    if bw is None and t_blender is not None:
        bw = t_blender
    if bw is not None and bl:
        row('blender', 'other', bw - named_w, (bc - named_c) if (bc is not None and c_known) else None,
            note='start-up, imports, the save, between stages')
    # ---- the QA's parts
    parts = Q.get('parts') or {}
    qw = qc = 0.0
    for p, v in parts.items():
        w, c = (v + [None, None])[:2] if isinstance(v, list) else (v, None)
        cached = any(r.get('event') == 'part' and r.get('name') == p and (r.get('cache') or {}).get('hit')
                     for r in recs)
        row('qa', p, w, c, cached=cached)
        qw += w or 0.0
        qc += c or 0.0
    qpw, qpc = (phases.get('qa') or [None, None]) if phases else ((steps or {}).get('qa'), None)
    if qpw is None and Q.get('seconds') is not None:
        qpw = Q.get('total') or Q.get('seconds')
    if qpc is None and Q.get('cpu_s') is not None:
        qpc = Q['cpu_s']
    if parts and qpw is not None:
        row('qa', 'other', qpw - qw, (qpc - qc) if qpc is not None else None, note="the design's loading, the report")
    for k in AFTER_STEPS:
        if k in phases:
            row('after', k, phases[k][0], phases[k][1])
    total = dict(wall=_r(B.get('wall_seconds')), cpu=_r(B.get('cpu_seconds')), threads=B.get('threads'))
    return dict(build=os.path.abspath(d), rows=rows, total=total,
                recorded=dict(phases=bool(phases), stage_cpu=any(r.get('cpu') is not None for r in bl),
                              qa_parts=bool(parts)))


def groups(P):
    """a profile's rows summed by group -> {group: dict(wall, cpu)} (cpu None when a row of it has none)."""
    out = {}
    for r in P['rows']:
        g = out.setdefault(r['group'], dict(wall=0.0, cpu=0.0))
        g['wall'] += r['wall'] or 0.0
        g['cpu'] = None if g['cpu'] is None or r['cpu'] is None else g['cpu'] + r['cpu']
    return {k: dict(wall=_r(v['wall']), cpu=_r(v['cpu'])) for k, v in out.items()}


def rest(P):
    """the build's CPU outside the QA (its total less the QA's parts): the venv steps and Blender together, which an
    older build records no finer -> seconds or None."""
    q = groups(P).get('qa')
    if P['total']['cpu'] is None or not q or q['cpu'] is None:
        return None
    return _r(P['total']['cpu'] - q['cpu'])


def top(P, n=5, key='cpu'):
    """the n costliest rows (by CPU, else wall where CPU wasn't recorded) -> [row]."""
    rs = [r for r in P['rows'] if r['stage'] != 'other']
    return sorted(rs, key=lambda r: -((r[key] if r[key] is not None else r['wall']) or 0.0))[:n]


def _f(x):
    return '-' if x is None else ('%.1f' % x)


def markdown(P, Q=None, n=5):
    """one profile, or two side by side (P the earlier, Q the later), as markdown."""
    lines = []
    if Q is None:
        lines += ['# Build profile: %s' % P['build'], '',
                  'total: %s s wall, %s s CPU (threads %s)' % (_f(P['total']['wall']), _f(P['total']['cpu']),
                                                               P['total']['threads'] or 'uncapped'), '',
                  '| group | stage | wall s | CPU s | CPU share | note |', '| --- | --- | --- | --- | --- | --- |']
        tc = P['total']['cpu'] or 0
        for r in P['rows']:
            share = ('%.0f%%' % (100 * r['cpu'] / tc)) if (tc and r['cpu'] is not None) else ''
            lines.append('| %s | %s%s | %s | %s | %s | %s |' % (r['group'], r['stage'], ' (cached)' if r['cached'] else '',
                                                             _f(r['wall']), _f(r['cpu']), share, r['note']))
        G = groups(P)
        lines += ['', '| group | wall s | CPU s |', '| --- | --- | --- |'] + [
            '| %s | %s | %s |' % (g, _f(v['wall']), _f(v['cpu'])) for g, v in G.items()]
        if rest(P) is not None:
            lines.append('| all but the QA (total - qa) | | %s |' % _f(rest(P)))
        lines += ['', 'Top %d by CPU:' % n] + ['- %s/%s: %s s CPU, %s s wall%s' % (
            r['group'], r['stage'], _f(r['cpu']), _f(r['wall']),
            (': ' + WHAT[r['group'] + '/' + r['stage']]) if r['group'] + '/' + r['stage'] in WHAT else '')
            for r in top(P, n)]
        return '\n'.join(lines) + '\n'
    lines += ['# Build profile: %s -> %s' % (P['build'], Q['build']), '',
              'total: %s -> %s s wall, %s -> %s s CPU' % (_f(P['total']['wall']), _f(Q['total']['wall']),
                                                          _f(P['total']['cpu']), _f(Q['total']['cpu'])), '',
              '| group | stage | wall A | wall B | CPU A | CPU B | CPU B - A |', '| --- | --- | --- | --- | --- | --- | --- |']
    ka = {(r['group'], r['stage']): r for r in P['rows']}
    kb = {(r['group'], r['stage']): r for r in Q['rows']}
    order = list(dict.fromkeys(list(kb) + list(ka)))
    gorder = ['venv', 'blender', 'qa', 'after']
    order.sort(key=lambda k: (gorder.index(k[0]) if k[0] in gorder else 9))
    for k in order:
        a, b = ka.get(k) or {}, kb.get(k) or {}
        d = (b.get('cpu') - a.get('cpu')) if (a.get('cpu') is not None and b.get('cpu') is not None) else None
        lines.append('| %s | %s | %s | %s | %s | %s | %s |' % (k[0], k[1], _f(a.get('wall')), _f(b.get('wall')),
                                                              _f(a.get('cpu')), _f(b.get('cpu')),
                                                              '' if d is None else '%+.1f' % d))
    ga, gb = groups(P), groups(Q)
    lines += ['', '| group | wall A | wall B | CPU A | CPU B |', '| --- | --- | --- | --- | --- |'] + [
        '| %s | %s | %s | %s | %s |' % (g, _f((ga.get(g) or {}).get('wall')), _f((gb.get(g) or {}).get('wall')),
                                        _f((ga.get(g) or {}).get('cpu')), _f((gb.get(g) or {}).get('cpu')))
        for g in gorder if g in ga or g in gb]
    ra, rb = rest(P), rest(Q)
    if ra is not None or rb is not None:
        lines.append('| all but the QA (total - qa) | | | %s | %s |' % (_f(ra), _f(rb)))
    lines += ['', 'Top %d by CPU in B:' % n] + ['- %s/%s: %s s CPU (A %s)%s' % (
        r['group'], r['stage'], _f(r['cpu']), _f((ka.get((r['group'], r['stage'])) or {}).get('cpu')),
        (': ' + WHAT[r['group'] + '/' + r['stage']]) if r['group'] + '/' + r['stage'] in WHAT else '')
        for r in top(Q, n)]
    return '\n'.join(lines) + '\n'


# ------------------------------------------------------------------------------------------------------------ budget
BUDGET = os.path.join(ROOT, 'charkit', 'budget.json')


def load_budget(path=None):
    """the build-CPU budget (charkit/budget.json, or path) -> dict(total, stages {'group/stage': seconds}, ...), or
    None without one."""
    return _load(path or BUDGET)


def cpu_by_stage(P):
    """a profile's CPU per 'group/stage' key, with each group's total as 'group/*' and 'total' -> {key: seconds or
    None}."""
    out = {'%s/%s' % (r['group'], r['stage']): r['cpu'] for r in P['rows']}
    for g, v in groups(P).items():
        out[g + '/*'] = v['cpu']
    if out.get('blender/*') is None and P['total']['cpu'] is not None:
        # (a build that recorded no stage CPU: Blender and the venv steps together, as the build's total less the QA's)
        out['blender+venv'] = rest(P)
    out['total'] = P['total']['cpu']
    return out


def budget_rows(cand, base=None, budget=None):
    """each budgeted stage's CPU on the candidate (and baseline) build folder against the budget -> [dict(stage,
    budget, base, cand, ratio (cand / budget), flag 'WARN: over budget' or '')], the total first; [] without a
    budget."""
    budget = load_budget() if budget is None else budget
    if not budget:
        return []
    C = cpu_by_stage(stages(cand))
    A = cpu_by_stage(stages(base)) if base else {}
    rows = []
    keys = ['total'] + [k for k in budget.get('stages') or {}]
    for k in keys:
        lim = budget.get('total') if k == 'total' else budget['stages'][k]
        c = C.get(k)
        r = dict(stage=k, budget=lim, base=A.get(k), cand=c, ratio=round(c / lim, 2) if (c is not None and lim) else None)
        r['flag'] = 'WARN: over budget' if (c is not None and lim and c > lim) else ''
        rows.append(r)
    return rows


# ------------------------------------------------------------------------------------------------ the QA under cProfile
def qa(bundle, parts=None, top_n=25, out=None, profile='full', log=print, cprofile=True):
    """the QA's parts one by one on a bundle (no cache), each under cProfile -> {part: dict(wall, cpu, checks,
    functions [dict(fn, calls, tottime, cumtime)])}; with out, written to out/qa_profile.json and one .prof per part."""
    import cProfile, pstats
    from . import bundle as bundlelib, qa3d, registry
    B = bundlelib.load(bundle) if isinstance(bundle, str) else bundle
    design = qa3d.Design(B)
    ref = B.spec.get('ref')
    ref_image = ref.get('image') if isinstance(ref, dict) else None
    res = {}
    if out:
        os.makedirs(out, exist_ok=True)
    tmp = out or os.path.join(ROOT, 'charkit', 'out', 'profile_qa')
    os.makedirs(tmp, exist_ok=True)
    for P in registry.parts():
        if parts and P.name not in parts:
            continue
        if P.name in getattr(qa3d, 'skipped_by', lambda p: set())(profile):
            res[P.name] = dict(skipped='profile %s' % profile)
            continue
        pr = cProfile.Profile()
        t, c = time.perf_counter(), time.process_time()
        err = None
        if cprofile:
            pr.enable()
        try:
            _, C = P.fn(B, design, tmp, *((ref_image,) if P.ref_image else ()))
        except Exception as e:                          # (measured anyway: a crash's cost is a cost)
            C, err = {}, '%s: %s' % (type(e).__name__, e)
        if cprofile:
            pr.disable()
        w, cp = time.perf_counter() - t, time.process_time() - c
        st = pstats.Stats(pr) if cprofile else None
        fns = []
        for (f, ln, fn), (cc, nc, tt, ct, _) in (st.stats.items() if st else ()):
            fns.append(dict(fn='%s:%d:%s' % (os.path.relpath(f, ROOT) if f.startswith(ROOT) else f, ln, fn),
                            calls=nc, tottime=round(tt, 3), cumtime=round(ct, 3)))
        fns.sort(key=lambda x: -x['tottime'])
        res[P.name] = dict(wall=round(w, 2), cpu=round(cp, 2), checks=len(C), error=err, functions=fns[:top_n],
                           cumulative=sorted(fns, key=lambda x: -x['cumtime'])[:top_n],
                           readings={k: [v.get('value'), v.get('status')] if isinstance(v, dict) else [v, None]
                                     for k, v in (C or {}).items()})
        if out and st:
            st.dump_stats(os.path.join(out, 'qa_%s.prof' % P.name))
        log('profile qa %-14s %7.1f s wall %7.1f s CPU  %d checks%s; top: %s' % (
            P.name, w, cp, len(C), (' (%s)' % err) if err else '',
            ', '.join('%s %.1f' % (f['fn'].rsplit(':', 1)[-1], f['tottime']) for f in fns[:3])))
    if out:
        json.dump(res, open(os.path.join(out, 'qa_profile.json'), 'w'), indent=1)
    return res


def same_readings(a, b):
    """two `profile qa` results (their json) -> {part: [checks whose reading differs]} (empty: every reading equal)."""
    A, B = (_load(x) if isinstance(x, str) else x for x in (a, b))
    out = {}
    for p in sorted((set(A) | set(B)) - {'_total'}):
        ra, rb = (A.get(p) or {}).get('readings') or {}, (B.get(p) or {}).get('readings') or {}
        bad = sorted(k for k in set(ra) | set(rb) if json.dumps(ra.get(k), default=str) != json.dumps(rb.get(k), default=str))
        if bad:
            out[p] = bad
    return out


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    if args[0] == 'same':                       # profile same A/qa_profile.json B/qa_profile.json
        d = same_readings(args[1], args[2])
        A, B = _load(args[1]), _load(args[2])
        for p in sorted((set(A) & set(B)) - {'_total'}):
            print('%-14s %7.1f -> %7.1f s wall %7.1f -> %7.1f s CPU  %s' % (
                p, A[p].get('wall') or 0, B[p].get('wall') or 0, A[p].get('cpu') or 0, B[p].get('cpu') or 0,
                'readings differ: %s' % ', '.join(d[p][:6]) if p in d else 'readings equal'))
        ta, tb = A.get('_total') or {}, B.get('_total') or {}
        if ta and tb:
            print('%-14s %7.1f -> %7.1f s wall %7.1f -> %7.1f s CPU' % ('all', ta['wall'], tb['wall'], ta['cpu'],
                                                                       tb['cpu']))
        return 1 if d else 0
    if args[0] == 'qa':
        parts = opt('--parts')
        for i, a in enumerate(args):                    # (--env K=V: a switch for this run, e.g. CHARKIT_RENDER_CULL=0)
            if a == '--env':
                k, _, v = args[i + 1].partition('=')
                os.environ[k] = v
        t, c = time.perf_counter(), time.process_time()
        R = qa(os.path.abspath(args[1]), parts=parts.split(',') if parts else None, top_n=int(opt('--top', 25)),
               out=opt('--out'), profile=opt('--profile', 'full'), cprofile='--no-cprofile' not in args)
        tot = dict(wall=round(time.perf_counter() - t, 1), cpu=round(time.process_time() - c, 1),
                   env={k: os.environ.get(k) for k in ('CHARKIT_RENDER_CULL', 'CHARKIT_CACHE', 'CHARKIT_QA_PROFILE')})
        print('profile qa: %s s wall, %s s CPU in all' % (tot['wall'], tot['cpu']))
        if opt('--out'):
            json.dump(dict(R, _total=tot), open(os.path.join(opt('--out'), 'qa_profile.json'), 'w'), indent=1)
        return 0
    steps = {}
    if opt('--gate'):
        steps = gate_steps(opt('--gate'))
    st = lambda d: steps.get(os.path.basename(os.path.normpath(d)))
    P = stages(args[0], st(args[0]))
    Q = stages(opt('--vs'), st(opt('--vs'))) if opt('--vs') else None
    if '--budget' in args:
        rows = budget_rows(opt('--vs') or args[0], args[0] if opt('--vs') else None)
        if not rows:
            print('no budget (charkit/budget.json)')
            return 1
        print('| stage | budget s | %scandidate s | of budget | |' % ('baseline s | ' if Q else ''))
        print('| --- | --- | %s--- | --- | --- |' % ('--- | ' if Q else ''))
        for r in rows:
            print('| %s | %s | %s%s | %s | %s |' % (r['stage'], _f(r['budget']), (_f(r['base']) + ' | ') if Q else '',
                                                  _f(r['cand']), '%.2fx' % r['ratio'] if r['ratio'] is not None else '',
                                                  r['flag']))
        return 0
    if '--json' in args:
        print(json.dumps(dict(a=P, b=Q) if Q else P, indent=1))
        return 0
    md = markdown(P, Q, n=int(opt('--top', 5)))
    if opt('--md'):
        open(opt('--md'), 'w').write(md)
    sys.stdout.write(md)
    return 0
