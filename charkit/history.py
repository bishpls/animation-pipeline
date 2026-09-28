"""QA over time: every build appends its checks to charkit/out/history/NAME.jsonl (git commit, spec hash, base, hair mode,
the out folder, each check's value and status; the build's Blender time, whether a worker ran it, and what the build
cache restored and ran, with why; and a note: the tune run and checkpoint that made it), so a check's trend across
builds and merges is one command away.

    python -m charkit history NAME                    # the latest builds, one line per build with its failing checks
    python -m charkit history NAME --check eye_aspect # one check across builds (a line marks each measurement step)

Measurement steps: when a check's measurement changes (not the character), its numbers step. STEPS lists each one (the
check, the commit that changed it, what changed); a build is before or after a step by whether that commit is in its
history. Trends (`trend`) read only the builds since the latest step, and comparisons between two builds on either side of
a step (the gate's, the tune loop's) call the check `remeasured` instead of improved or regressed.
"""
import fnmatch, json, os, subprocess, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, 'charkit', 'out', 'history')

# (check pattern, the commit that changed the measurement, what changed)
STEPS = [
    ('hair_noise', 'c500f21', 'QA renders undithered (charkit/geom merge): hair_noise reads ~0.31 on the default hair and '
                              '~0.19 on geom hair, where dither noise split the toon tones before'),
    ('face_folds', '8017ff3', 'the expression library grew (tool/sheet: shock eyes; laugh, yawn and wavy mouths), and '
                              'face_folds sums its folds over every key: Clawd 1014 -> 1257 with the same skin'),
    ('face_expr_range', '8017ff3', 'FACE_EXPECT gained the shock eye (tool/sheet)'),
    ('face_shape_coverage_*', '5652f64', 'framing against the generated shape is INFO: the sheet grades framing '
                                         '(sheet_shown_*), per the manifest'),
]


def append(out, name, note=None):
    """record a finished build's QA (out/qa/qa.json) and its trace header."""
    qp = os.path.join(out, 'qa', 'qa.json')
    if not os.path.exists(qp):
        return None
    qa = json.load(open(qp))
    begin, cache, total = {}, {}, None
    tp = os.path.join(out, 'trace.jsonl')
    if os.path.exists(tp):
        for line in open(tp):
            rec = json.loads(line)
            if rec.get('event') == 'begin':
                begin = rec
            elif rec.get('cache') and rec.get('event') in ('stage', 'span', 'product', 'part'):
                c = rec['cache']
                cache[rec['name']] = 'hit' if c.get('hit') else 'miss: %s' % (c.get('why') or '?')
            elif rec.get('event') == 'end':
                total = rec.get('total')
    spec = {}
    sp = os.path.join(out, name + '.spec.json')
    if os.path.exists(sp):
        spec = json.load(open(sp))
    row = {'t': time.strftime('%Y-%m-%dT%H:%M:%S'), 'git': begin.get('git'), 'spec_hash': begin.get('spec_hash'),
           'base': spec.get('base', 'makehuman'), 'hair': ((spec.get('hair') or {}).get('shape') or {}).get('mode'),
           'out': os.path.relpath(out, ROOT), 'summary': qa.get('summary'),
           'checks': {k: [c.get('value'), c.get('status')] for k, c in qa.get('checks', {}).items()
                      if c.get('status') in ('PASS', 'WARN', 'FAIL', 'INFO')}}
    row.update(seconds=total, worker=bool(begin.get('worker')))
    if cache:
        row['cache'] = cache
    if note:
        row['note'] = note
    os.makedirs(DIR, exist_ok=True)
    with open(os.path.join(DIR, name + '.jsonl'), 'a') as f:
        f.write(json.dumps(row, default=float) + '\n')
    return row


def read(name):
    p = os.path.join(DIR, name + '.jsonl')
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


# ------------------------------------------------------------------------------------------------------------ steps
_ANC = {}


def _commit(git):
    return (git or '').split('+')[0] or None


def contains(git, commit):
    """is `commit` in the history of the build's commit `git` ('abc1234' or 'abc1234+dirty')? None when unknown."""
    g = _commit(git)
    if not g or not commit:
        return None
    if (commit, g) not in _ANC:
        r = subprocess.run(['git', '-C', ROOT, 'merge-base', '--is-ancestor', commit, g], capture_output=True)
        _ANC[(commit, g)] = {0: True, 1: False}.get(r.returncode)
    return _ANC[(commit, g)]


def epoch(check, git, steps=None):
    """how many of the check's measurement steps the build's commit has (None when unknown)."""
    n = 0
    for pat, commit, _ in (STEPS if steps is None else steps):
        if fnmatch.fnmatchcase(check.split('.')[0], pat):
            c = contains(git, commit)
            if c is None:
                return None
            n += int(c)
    return n


def remeasured(git_a, git_b, names=None, steps=None):
    """the checks whose measurement changed between two builds' commits -> {check pattern: why} (checks named in
    `names` only, when given). Builds of unknown commit are taken as comparable."""
    out = {}
    for pat, commit, why in (STEPS if steps is None else steps):
        a, b = contains(git_a, commit), contains(git_b, commit)
        if a is None or b is None or a == b:
            continue
        for n in (names or [pat]):
            if fnmatch.fnmatchcase(n.split('.')[0], pat):
                out[n] = why
    return out


def steps_between(ref_a, ref_b, steps=None):
    """the measurement steps in ref_b's history and not ref_a's (git refs) -> {check pattern: why}."""
    out = {}
    for pat, commit, why in (STEPS if steps is None else steps):
        if contains(ref_b, commit) and contains(ref_a, commit) is False:
            out[pat] = why
    return out


def trend(rows, check, steps=None):
    """the rows since the check's latest measurement step (the latest row's epoch), as (row, value, status)."""
    pts = [(r, *r['checks'][check]) for r in rows if check in r.get('checks', {})]
    if not pts:
        return []
    last = epoch(check, pts[-1][0].get('git'), steps)
    return [p for p in pts if last is None or epoch(check, p[0].get('git'), steps) in (last, None)]


def main(args):
    if not args:
        print(__doc__); return
    rows = read(args[0])
    if '--check' in args:
        k = args[args.index('--check') + 1]
        prev = None
        for r in rows:
            v = r['checks'].get(k)
            if not v:
                continue
            e = epoch(k, r.get('git'))
            if prev is not None and e is not None and e != prev:
                why = [w for p, _, w in STEPS if fnmatch.fnmatchcase(k, p)]
                print('--- measurement step: %s' % (why[-1] if why else 'the check changed'))
            prev = e if e is not None else prev
            tn = r.get('note', {}).get('tune') if isinstance(r.get('note'), dict) else None
            print('%s  %-16s %-10s %-5s %-10s %s%s' % (r['t'], r['git'], r['base'], r.get('hair') or '', v[1], v[0],
                                                      '  tune %s' % tn if tn else ''))
        return
    for r in rows[-int(args[args.index('--last') + 1]) if '--last' in args else -20:]:
        fails = [k for k, v in r['checks'].items() if v[1] == 'FAIL']
        c = r.get('cache') or {}
        how = ('%3.0fs%s' % (r['seconds'], ' w' if r.get('worker') else '') if r.get('seconds') else '') + \
            (' cache %d/%d' % (sum(v == 'hit' for v in c.values()), len(c)) if c else '')
        note = r.get('note')
        tag = ('  [tune %s ck%s %s]' % (note.get('tune'), note.get('checkpoint'), note.get('label', ''))
               if isinstance(note, dict) and note.get('tune') else '')
        print('%s  %-16s %-10s %-5s %-16s fail %2d: %s%s' % (r['t'], r['git'], r['base'], r['summary'], how, len(fails),
                                                            ', '.join(fails), tag))
