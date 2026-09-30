"""The QA's drawn checks under its two drawings (charkit.qa3d's numpy rasteriser, charkit.render: charkit.qarender),
check by check, with each check's own noise (Michael's decisions 2 and 3: a new measure ships calibrated; a check that
moves more than its noise is explained, not re-baselined). For each build: every drawn check under each drawing at the
frame's own placement and at sub-pixel offsets of it (the measuring grid moved by a fraction of a pixel: the spread the
sampling alone gives, its noise). With two builds (two geometries), the 2x2: each drawing on each geometry, and whether
the geometry's change reads the same way under both.

    python -m charkit.render calibrate BUILD [BUILD2] [--out DIR] [--offsets 6]    # DIR/calibrate.json, calibrate.md

The drawn checks: hair_noise, scalp_px (the figure frame's pictures), the look's face_noise, face_noise_sweep,
face_islands, face_shadow_* (the head frames' tones), line_width, line_spread, line_ink (the lines' part buffer at the
design's scale), the boots' profile checks (detailqa: the part buffer; placed as detailqa places them, not offset).
"""
import json, os, sys, time

import numpy as np

OFFSETS = ((0.0, 0.0), (1 / 3, 0.0), (0.0, 1 / 3), (2 / 3, 1 / 3), (1 / 3, 2 / 3), (2 / 3, 2 / 3))
DETAIL = ('boot_profile_double_', 'boot_profile_scrunch_')


def _figure_offset(off):
    """qa3d.figure_frame with its grid moved by off (output pixels: x right, y down)."""
    from charkit import qa3d
    orig = qa3d.figure_frame

    def fr(B, ss=1):
        f = orig(B, ss)
        p = f.pix * ss
        f.origin = (f.origin[0] - off[0] * p, f.origin[1] + off[1] * p)
        return f
    return orig, fr


def checks(build, drawing, off=(0.0, 0.0), details=False):
    """the drawn checks of one build under one drawing, its frames moved by off -> {check: value}."""
    from charkit import bundle, detailqa, lookqa, qa3d, qarender
    os.environ[qarender.ENV] = drawing
    B = bundle.load(os.path.join(build, 'bundle'))                  # (fresh: the memos hold one drawing's frames)
    design = qa3d.Design(B)
    out = {}
    orig, shifted = _figure_offset(off)
    qa3d.figure_frame = shifted
    try:
        for fn in (qa3d.hair_noise, qa3d.scalp):
            _, C = fn(B, design)
            out.update({k: v.get('value') for k, v in C.items()})
    finally:
        qa3d.figure_frame = orig
    fr = lookqa.HeadFrame(B, off=off)
    for fn in (lambda: lookqa.face_noise(B, None, design, fr=fr), lambda: lookqa.face_shadow(B, design, fr=fr),
               lambda: lookqa.line_width(B, design, off=off)):
        _, C = fn()
        out.update({k: v.get('value') for k, v in C.items()})
    if details:
        _, C = detailqa.measure(B, design, None)
        out.update({k: v.get('value') for k, v in C.items() if k.startswith(DETAIL)})
    out['_drawn'] = qarender.drawn(B)
    return out


def run(builds, out, n_off=len(OFFSETS)):
    from charkit import qarender
    t0 = time.time()
    rep = {'builds': builds, 'offsets': OFFSETS[:n_off], 'values': {}}
    for b in builds:
        rep['values'][b] = {}
        for drawing in ('numpy', 'render'):
            rows = []
            for i, off in enumerate(OFFSETS[:n_off]):
                t = time.time()
                rows.append(checks(b, drawing, off, details=(i == 0)))
                print(b, drawing, off, round(time.time() - t, 1), 's', {k: v for k, v in rows[-1].items()
                                                                        if not k.startswith('_')}, flush=True)
            rep['values'][b][drawing] = rows
    os.environ.pop(qarender.ENV, None)
    rep['table'] = table(rep)
    rep['seconds'] = round(time.time() - t0, 1)
    os.makedirs(out, exist_ok=True)
    json.dump(rep, open(os.path.join(out, 'calibrate.json'), 'w'), indent=1, default=float)
    open(os.path.join(out, 'calibrate.md'), 'w').write(markdown(rep))
    return rep


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v is not None


def table(rep):
    """per build and check: old (numpy at the frame's placement), new (render), each drawing's noise (the standard
    deviation over the offsets), new - old in units of the larger noise; and with two builds the 2x2."""
    T = {}
    for b, V in rep['values'].items():
        names = sorted({k for rows in V.values() for r in rows for k in r if not k.startswith('_')})
        for k in names:
            cells = {}
            for d in ('numpy', 'render'):
                xs = [r.get(k) for r in V[d] if _num(r.get(k))]
                cells[d] = dict(value=V[d][0].get(k), mean=round(float(np.mean(xs)), 5) if xs else None,
                                noise=round(float(np.std(xs)), 5) if len(xs) > 1 else None, n=len(xs))
            o, n = cells['numpy']['value'], cells['render']['value']
            noise = max([c['noise'] or 0.0 for c in cells.values()])
            row = dict(old=o, new=n, noise_old=cells['numpy']['noise'], noise_new=cells['render']['noise'],
                       mean_old=cells['numpy']['mean'], mean_new=cells['render']['mean'])
            if _num(o) and _num(n):
                row['diff'] = round(float(n) - float(o), 5)
                row['in_noise'] = round(abs(float(n) - float(o)) / noise, 2) if noise > 0 else (0.0 if n == o else None)
                # the offsets' means: the difference with the sampling averaged out
                if _num(row['mean_old']) and _num(row['mean_new']):
                    row['mean_diff'] = round(row['mean_new'] - row['mean_old'], 5)
            T.setdefault(k, {})[b] = row
    if len(rep['values']) == 2:
        a, b = list(rep['values'])
        for k, per in T.items():
            if a in per and b in per:
                ra, rb = per[a], per[b]
                if all(_num(x) for x in (ra['old'], ra['new'], rb['old'], rb['new'])):
                    do, dn = rb['old'] - ra['old'], rb['new'] - ra['new']
                    per['2x2'] = dict(geometry_change_old=round(do, 5), geometry_change_new=round(dn, 5),
                                      same_direction=bool(np.sign(round(do, 6)) == np.sign(round(dn, 6))),
                                      change_gap=round(dn - do, 5))
    return T


def markdown(rep):
    builds = list(rep['values'])
    L = ['# The QA\'s drawn checks: numpy drawing (old) against charkit.render (new)', '',
         'Builds: %s. Noise: the standard deviation over %d sub-pixel placements of each frame (the old drawing\'s / the '
         'new\'s). in noise: |new - old| over the larger noise.' % (', '.join(builds), len(rep['offsets'])), '']
    for b in builds:
        L += ['## %s' % b, '', '| check | old | new | new - old | noise old / new | in noise | offsets\' means old / new |',
              '| --- | --- | --- | --- | --- | --- | --- |']
        for k, per in sorted(rep['table'].items()):
            r = per.get(b)
            if not r:
                continue
            L.append('| %s | %s | %s | %s | %s / %s | %s | %s / %s |' % (
                k, r['old'], r['new'], r.get('diff', ''), r['noise_old'], r['noise_new'], r.get('in_noise', ''),
                r['mean_old'], r['mean_new']))
        L.append('')
    if len(builds) == 2:
        L += ['## The 2x2 (%s -> %s)' % tuple(builds), '',
              '| check | old drawing: A, B (change) | new drawing: A, B (change) | same direction |', '| --- | --- | --- | --- |']
        for k, per in sorted(rep['table'].items()):
            x = per.get('2x2')
            if not x:
                continue
            a, b = per[builds[0]], per[builds[1]]
            L.append('| %s | %s, %s (%+.4f) | %s, %s (%+.4f) | %s |' % (k, a['old'], b['old'], x['geometry_change_old'],
                                                                       a['new'], b['new'], x['geometry_change_new'],
                                                                       'yes' if x['same_direction'] else '**no**'))
    return '\n'.join(L) + '\n'


def main(args):
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    builds = [os.path.abspath(a) for i, a in enumerate(args) if not a.startswith('--') and
              (i == 0 or args[i - 1] not in ('--out', '--offsets'))]
    out = os.path.abspath(opt('--out', os.path.join(builds[0], 'calibrate')))
    rep = run(builds, out, int(opt('--offsets', len(OFFSETS))))
    print(markdown(rep))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
