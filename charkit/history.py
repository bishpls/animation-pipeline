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
    ('body_*_leg_gap', 'd35fbaf', "new: rows over the lower legs and boots where the design's legs stand apart and ours join (a bridge)"),
    ('body_*_boot_step_*', 'd35fbaf', "new: each boot's outline's largest row-to-row jump beyond the design's (the shaft/foot seam)"),
    ('body_*_skirt_aline', 'd35fbaf', "new: the skirt's width near its hem over its widest row against the design's (a bubble)"),
    ('body_profile_chest', 'd35fbaf', "new: the chest's front edge in profile against the design's"),
    ('body_*_waist_skin', 'd35fbaf', "new: the waist's skin across the body beyond the design's (a bare band)"),
    ('piece_*_extent', 'd35fbaf', "new: a spring piece's lowest row, outer edge and area per view against the drawing's"),
    ('piece_*_hang', 'd35fbaf', "new: a chained piece's top and lowest point against its drawn chain's root and tip"),
    ('garment_coverage', 'd35fbaf', 'new (INFO): garments lofted from marginal hull coverage'),
    ('piece_skirt', 'd35fbaf', "same-colour layers: pixels where a piece lies over another of its colour count for neither (the overskirt panels over the skirt); the flaps' geometry changed at the same time"),
    ('piece_overskirt_panel_*', 'd35fbaf', "same-colour layers (as piece_skirt); the flaps' geometry changed at the same time"),
    ('piece_cuff_*', 'e34aeff', 'same-colour layers: the wrist cuffs lie over the skirt (the notes; both orange), so where they overlap the pixels count for neither; the skirt was cleared of the arms at the same time'),
    ('piece_skirt', 'e34aeff', 'same-colour layers: the wrist cuffs over it too; the skirt was cleared of the arms at the same time'),
    ('body_*_skirt_width', '4053ecd', "the skirt's width measured on the design's rows free of hands when no row is free in both (the back view had fallen back to each figure's own widest free row)"),
    ('body_*_skirt_width', 'ecd4d79', "the skirt's width compared on the rows neither figure has a hand against (each figure's widest free row had sat at different heights)"),
    ('hair_noise', 'c500f21', 'QA renders undithered (charkit/geom merge): hair_noise reads ~0.31 on the default hair and '
                              '~0.19 on geom hair, where dither noise split the toon tones before'),
    ('face_folds', '8017ff3', 'the expression library grew (tool/sheet: shock eyes; laugh, yawn and wavy mouths), and '
                              'face_folds sums its folds over every key: Clawd 1014 -> 1257 with the same skin'),
    ('face_expr_range', '8017ff3', 'FACE_EXPECT gained the shock eye (tool/sheet)'),
    ('face_shape_coverage_*', '5652f64', 'framing against the generated shape is INFO: the sheet grades framing '
                                         '(sheet_shown_*), per the manifest'),
    # tool/measure: the QA measures the build's geometry bundle in the venv (charkit/bundle.py, charkit/qa3d.py)
    ('sheet_*', '5394358', 'the QA runs in the venv on the geometry bundle (tool/measure): the sheet\'s class z-buffer '
                          'rasterises at pixel centres (numba) where the point splats read about half a pixel wider; '
                          'lines stay a pixel wide. neck_to_jaw reads one row, which a pixel moves off the neck'),
    ('body_*', '5394358', 'the body classes z-buffered at pixel centres (tool/measure): heights move by a sheet pixel '
                         '(0.0087 L), IoUs by about 0.01'),
    ('expr_*', '5394358', 'the expression heads z-buffered at pixel centres (tool/measure): a match distance moves with '
                         'a pixel of the small iris (fluster 0.12 -> 0.39)'),
    ('face_shape_*', '5394358', 'the face-shape z-buffers at pixel centres (tool/measure): widths about 0.02, the chin '
                               'by two pixels (0.012 L)'),
    ('eye_*', '5394358', 'the eye renders drawn from the bundle, not EEVEE (tool/measure): within a pixel'),
    ('shape_iou*', '5394358', 'the silhouettes drawn from the bundle, anti-aliased like EEVEE (tool/measure): within 0.001'),
    ('ref_iou', '5394358', 'the front silhouette drawn from the bundle (tool/measure)'),
    ('hair_noise', '5394358', 'the hair drawn with its toon materials from the bundle, not EEVEE (tool/measure): within '
                             '2.5%'),
    ('scalp_px', '5394358', 'the scalp drawn from the bundle, not EEVEE (tool/measure)'),
    # tool/refs: the generated references are the design (Michael, 2026-09-28: idol_D is the source design, not a
    # benchmark); each check graded only against its measure's authority (checks.authorize)
    ('sheet_*', '9307073', 'the face measured against head_turnaround (generated, 200 px/L, scaled by its own eyes), not '
                          'idol_D at 115 px/L'),
    ('eye_*', '9307073', 'the eyes measured against head_turnaround\'s front eyes at its own resolution, not the rig\'s '
                        'eye layers'),
    ('body_*', '9307073', 'the body measured against body_turnaround (generated, one A-pose, 212 px/L, scaled by its own '
                         'eyes), not idol_D'),
    ('palette_*', '9307073', 'the palette read from body_turnaround, not idol_D'),
    ('figures_*', '9307073', 'the figures found on body_turnaround; no hand-typed head boxes to verify'),
    ('expr_*', '9307073', 'no expression reference: the expressions are the template library\'s (the body sheet has no '
                         'expression heads)'),
    ('shape_iou*', '9307073', 'INFO unless the measure\'s authority (checks.authorize): the body silhouette\'s is the body '
                             'turnaround, the hair shape\'s TRELLIS'),
    ('ref_iou', '9307073', 'INFO: the 3D-style key is no measure\'s authority (checks.authorize)'),
    ('face_shape_*', '9307073', 'INFO but the depth: TRELLIS is only the face depth\'s authority (checks.authorize)'),
    # tool/review: the generated 3D character grades nothing (Michael, 2026-09-28)
    ('face_shape_depth', 'b8307af', 'the face\'s depth against the generated character is INFO: face_depth has no '
                                 'authority (the hull is the hair\'s source, not a face target)'),
    ('shape_iou_hair', 'b8307af', 'the hair against the generated character is INFO: hair_shape has no authority (our '
                               'hair is cut from it; the sheet grades the hair)'),
    # tool/chin: our chin read with the design's rule
    ('sheet_*', '5843d44', 'our chin read with the design\'s rule (faceqa.drawn_chin: the turn under the chin), not '
                          'chin_bottom (0.06 L behind the lips); the chin, the widths\' rows, the neck\'s row and the '
                          'contours\' extent move with it on a receding chin'),
    ('hair_noise', '51a87aa', 'the hair drawn without its outlines (a drawn line between two locks is not shading) and behind '
     'the rest of the character (the hair\'s inside through the face is hidden, as in a render) (tool/hair-pieces): '
     'the geom hair reads 0.047, was 0.104'),
    # tool/look: the QA draws what the boards light
    ('hair_noise', '37ff417', 'the hair drawn under each view\'s board light (the style\'s look: the anime key turns with '
     'the camera), not its material\'s one fixed light: the back view is lit as the front is (tool/look)'),
    # tool/hair-detail: the buns' tones cut apart from the mass's
    ('hair_noise', 'cc79d07', 'each tone group cut at its own percentiles, the buns apart from the mass (qa3d.tone_edges; '
     'tool/hair-detail): a block bun\'s flat faces had moved the shared cuts. The clawd_body pieces build reads 0.068, '
     'was 0.088; the default spec 0.055, was 0.048'),
    # tool/look2: the look QA's speedup
    ('line_ink', '0b6e9cd', 'the lines\' own colour (their supersampled pixels before the pixel filter), not the pixels a '
     'line covers wholly after it (blended with their neighbours): the inked hair, garment and accessory lines read '
     '0.48 from the design\'s ink, were 4.5, 7.8 and 15.6; the skin\'s brown 24.67, was 24.9 (tool/look2)'),
    ('eye_pupil_*', 'b9055f7', 'the pupil read from its coverage map (sub-pixel; a value threshold had cut its soft ends) '
                               'and against the whole iris\'s height (its lid-shadowed top had fallen out of the iris): '
                               'the pre-round-2 build reads pupil_run 0.297 against the design\'s 0.405 (it had read 0.341 '
                               'against 0.394)'),
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


def load_steps(path):
    """STEPS as another tree's charkit/history.py lists them, read without importing it -> the list, or None. The gate
    reads the merged tree's: a branch registers the measurement steps it brings in its own history.py, which the
    integration branch's code (running the gate) doesn't have yet."""
    import ast
    if not os.path.exists(path):
        return None
    for node in ast.parse(open(path).read()).body:
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', None) == 'STEPS' for t in node.targets):
            return [tuple(x) for x in ast.literal_eval(node.value)]
    return None


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
