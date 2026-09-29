"""The eyes' and mouth's review page: a build's eyes against the design's in every view the head sheet draws, each
expression of the library side by side with its measures, the blink's closure, the folds per key, and how much of each
open mouth the cavity covers.

    python -m charkit eyes BUILD_DIR [--against OTHER_BUILD_DIR] [--out DIR]     -> DIR/index.html (default BUILD/eyes)

The design is the manifest's eyes sheet (head_turnaround): its front, three-quarter and profile eyes cut at the sheet's
own resolution (charkit.refcheck), ours rendered as the QA renders its eyes (qa3d.eye_image) from the same azimuths, both
measured by charkit.eyeqa. The expressions are ours only (the library has no reference: exprqa's class render and
measures). Pure venv.
"""
import html, json, os, sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYS = ('aspect', 'open_w', 'iris_ratio', 'iris_fill', 'iris_cx', 'pupil_run', 'pupil_share', 'lid_span', 'lid_gap', 'tilt')
COVER = (11, 9, 4)                  # exprqa classes an open mouth may show: its inside and tongue, teeth, the lip line


def design_eyes(spec, ppl_face=None):
    """the eyes sheet's eyes per view at its own resolution: {view: [(our side, rgba)]}, the sheet's px per L, and the
    three-quarter's azimuth. The picture's left eye is our right in the front; turned to the picture's left, the
    three-quarter's near eye (the picture's right) and the profile's one eye are her left."""
    from . import manifest, refcheck
    M = manifest.load(spec['ref']['manifest'])
    key = (M.get('sheets') or {}).get('eyes', 'head_turnaround')
    r = M['references'][key]
    rgb = refcheck._load(r['path'])
    ex = (spec.get('eyes') or {}).get('x', 0.168)
    rgb0, _ = refcheck.without_guides(np.asarray(rgb, float))
    ppl = ppl_face or refcheck.FACE_PPL
    _, f, H = refcheck.at_scale(rgb0, ex, 2 * ex * ppl, r.get('facing', -1))
    own = ppl / f
    hw, hh = refcheck.EYE_BOX[0] * own, refcheck.EYE_BOX[1] * own
    out = {}
    for view, sides in (('front', ('R', 'L')), ('three_quarter', ('R', 'L')), ('profile', ('L',))):
        eyes = sorted((H['heads'].get(view) or {}).get('eyes') or [])
        if len(eyes) != len(sides):
            continue
        for side, (x, y) in zip(sides, eyes):
            cx, cy = x / f, y / f
            crop = rgb0[int(cy - hh):int(cy + hh), int(cx - hw):int(cx + hw)]
            out.setdefault(view, []).append((side, np.concatenate([crop, np.ones(crop.shape[:2] + (1,))], -1)))
    return out, own


def measure(build, az3=None):
    """a build's eyes, expressions and mouths measured -> dict."""
    from . import bundle as bl, exprqa, eyeqa, qa3d
    B = bl.load(os.path.join(build, 'bundle'))
    Dz = qa3d.Design(B)
    if az3 is None:
        got = Dz.sheet_measures()
        az3 = float(got[0].get('az_three_quarter', 35.0)) if got else 35.0
    des, ppl = design_eyes(B.spec)
    views = {'front': 0.0, 'three_quarter': az3, 'profile': 90.0}
    eyes = {}
    for view, pairs in des.items():
        for side, px in pairs:
            ours = qa3d.eye_image(B, side, ppl, ss=3, az=views[view])
            mo, md = eyeqa.measure(ours, ppl), eyeqa.measure(px, ppl)
            eyes['%s_%s' % (view, side)] = dict(view=view, side=side, ours=ours, design=px, mo=mo, md=md,
                                                cmp=eyeqa.compare(mo, md) if mo.get('found') and md.get('found') else {})
    # the expressions: the library's shapes rendered (exprqa's class image) and measured
    data = qa3d.expression_data(B)
    lib = exprqa.library(data)
    eppl = 200.0
    ey, ax = exprqa._at(eppl)
    A = qa3d.assembly(B, 'base')
    L = A['head']['L']
    m = A['mouth']['m']
    ex = {}
    for part in ('eye', 'mouth'):
        for name in lib[part]:
            cls = exprqa.render(data, {part: name}, eppl)
            M = exprqa.measure(cls, eppl, ey, ax, ours=True)
            rec = dict(cls=cls, m=exprqa.summary(M))
            if part == 'mouth':
                rec['cover'] = mouth_cover(cls, A, name, eppl, data['eye_z'], L)
            ex['%s_%s' % (part, name)] = rec
    face_t, face_c = qa3d.face(B)
    folds = qa3d.face_folds(qa3d.assembly(B))
    qa = json.load(open(os.path.join(build, 'qa', 'qa.json')))['checks']
    return dict(build=build, eyes=eyes, ppl=ppl, az3=az3, ex=ex, face=face_t, face_checks=face_c, folds=folds, qa=qa)


def mouth_cover(cls, A, name, ppl, eye_z, L, win=None):
    """the share of an open mouth's opening (the lips' loop under the shape's key, seen head-on) that shows its inside,
    tongue, teeth or lip line, rather than skin (the lips' rings lapped over the opening) or nothing (a hole) -> dict(
    cover, skin, none, px) or None for a closed mouth (under 20 px open)."""
    from matplotlib.path import Path
    from . import exprqa
    win = win or exprqa.WIN
    V = np.asarray(A['verts'], float)
    D = A['mouth']['keys'].get(name) if name != 'neutral' else None
    P = V + D if D is not None else V
    m = A['mouth']['m']
    loop = list(m['upper']) + list(m['lower'])[::-1][1:-1]
    xz = P[loop][:, [0, 2]]
    col = xz[:, 0] / L * ppl + win['x'] * ppl
    row = (win['top'] - (xz[:, 1] - eye_z) / L) * ppl
    H, W = cls.shape
    yy, xx = np.mgrid[0:H, 0:W]
    inside = Path(np.stack([col, row], 1)).contains_points(np.stack([xx.ravel() + 0.5, yy.ravel() + 0.5], 1)).reshape(H, W)
    n = int(inside.sum())
    if n < 20:
        return None
    c = cls[inside]
    return dict(cover=round(float(np.isin(c, COVER).mean()), 3), skin=round(float((c == 1).mean()), 3),
                none=round(float((c == 0).mean()), 3), px=n)


def _rgb(a):
    a = np.asarray(a, float)
    if a.ndim == 3 and a.shape[2] == 4:
        return a[..., :3] * a[..., 3:4] + 0.93 * (1 - a[..., 3:4])
    return a


def page(build, out, against=None):
    from PIL import Image
    from . import exprqa
    Mb = measure(build)
    Ma = measure(against, az3=Mb['az3']) if against else None
    img = os.path.join(out, 'img')
    os.makedirs(img, exist_ok=True)

    def save(a, name, h=None):
        im = Image.fromarray((np.clip(_rgb(a), 0, 1) * 255).astype(np.uint8))
        if h and im.size[1] != h:
            im = im.resize((max(1, int(im.size[0] * h / im.size[1])), h), Image.LANCZOS)
        im.save(os.path.join(img, name))
        return 'img/' + name
    tag = lambda p: html.escape(os.path.relpath(p, ROOT))
    L = ['<!doctype html><meta charset="utf-8"><title>eyes and mouth</title><style>body{font:14px/1.45 -apple-system,'
         'system-ui,sans-serif;margin:24px;background:#fafafa;color:#222}h2{font-size:17px;margin:28px 0 6px}.row{display:'
         'flex;gap:10px;flex-wrap:wrap;align-items:flex-end}.tile{text-align:center;font-size:12px;color:#555}.tile img{'
         'display:block;border:1px solid #ddd;background:#fff}table{border-collapse:collapse;font-size:13px;margin:6px 0}'
         'td,th{border:1px solid #ddd;padding:3px 8px;text-align:right}th{background:#f0f0f0}td:first-child{text-align:left}'
         '.PASS{color:#070}.WARN{color:#b60}.FAIL{color:#c00}.INFO{color:#666}.note{color:#666;font-size:12px}</style>',
         '<h1>Eyes and mouth: %s</h1>' % tag(build),
         '<p class="note">The design is the eyes sheet (head_turnaround), cut at its own resolution (%.0f px per L); ours '
         'rendered as the QA renders its eyes, from the same azimuths (front 0&deg;, three-quarter %.1f&deg;, profile '
         '90&deg;), both measured by charkit.eyeqa. The graded eye checks are the front\'s; the other views are '
         'information. %s</p>' % (Mb['ppl'], Mb['az3'], ('Against: <b>%s</b>.' % tag(against)) if against else '')]
    # the checks
    names = sorted(k for k in Mb['qa'] if k.startswith(('eye_', 'face_', 'sheet_')) and not k.startswith('face_shape'))
    L.append('<h2>Checks</h2><table><tr><th>check</th><th>this build</th>%s</tr>' % ('<th>against</th>' if Ma else ''))
    for k in names:
        c = Mb['qa'][k]
        a = (Ma['qa'].get(k) or {}) if Ma else None
        cell = lambda c: '<td class="%s">%s %s</td>' % (c.get('status', ''), c.get('value', ''), c.get('status', ''))
        L.append('<tr><td>%s</td>%s%s</tr>' % (k, cell(c), cell(a) if Ma else ''))
    L.append('</table>')
    # eyes per view
    L.append('<h2>Eyes per view</h2><p class="note">Each pair: the design, then ours, at one scale. aspect = opening '
             'height / width; open_w in L; iris_ratio its width over the opening\'s; iris_cx where it sits across the '
             'opening (+ the picture\'s right; the three-quarter\'s parallax); tilt the corner line (degrees).</p>')
    L.append('<table><tr><th>view, eye</th>%s</tr>' % ''.join('<th>%s<br>design / ours%s</th>' % (k, ' / against' if Ma
                                                                                                      else '') for k in KEYS))
    for key, e in Mb['eyes'].items():
        ea = Ma['eyes'].get(key) if Ma else None
        cells = []
        for k in KEYS:
            vals = [e['md'].get(k), e['mo'].get(k)] + ([ea['mo'].get(k)] if ea else [])
            st = (e['cmp'].get('width' if k == 'open_w' else k) or {}).get('status', '')
            cells.append('<td class="%s">%s</td>' % (st, ' / '.join('-' if v is None else str(v) for v in vals)))
        L.append('<tr><td>%s</td>%s</tr>' % (key.replace('_', ' '), ''.join(cells)))
    L.append('</table><div class="row">')
    for key, e in Mb['eyes'].items():
        L.append('<div class="tile"><img src="%s" height="170"><img src="%s" height="170">%s<br>%s</div>' % (
            save(e['design'], 'eye_%s_design.png' % key, 170), save(e['ours'], 'eye_%s_ours.png' % key, 170),
            ('<img src="%s" height="170">' % save(Ma['eyes'][key]['ours'], 'eye_%s_against.png' % key, 170))
            if Ma and key in Ma['eyes'] else '', key.replace('_', ' ')))
    L.append('</div>')
    # expressions
    fk = Mb['folds']['keys']
    fa = Ma['folds']['keys'] if Ma else {}
    L.append('<h2>Expressions</h2><p class="note">The library\'s eye and mouth shapes as the build keys them (exprqa\'s '
             'class render: skin, line, iris, white, the mouth\'s inside). folds: skin faces flipped or turned away under '
             'the key (qa3d.face_folds; at rest %d%s). The mouth\'s cover: the share of its opening that shows its inside, '
             'tongue, teeth or lip line (skin there is the lips\' rings lapped over the opening; none is a hole).</p>' % (
                 Mb['folds']['rest'], (', against %d' % Ma['folds']['rest']) if Ma else ''))
    for part in ('eye', 'mouth'):
        L.append('<div class="row">')
        for key, r in Mb['ex'].items():
            if not key.startswith(part + '_'):
                continue
            name = key[len(part) + 1:]
            cls = r['cls']
            if part == 'eye':
                crop = cls[:int(0.45 * 2 * 200) // 2 + 40, :]
            else:
                crop = cls[int((exprqa.WIN['top'] + 0.12) * 200):int((exprqa.WIN['top'] + 0.62) * 200), 30:-30]
            pic = exprqa.paint(crop)
            ra = Ma['ex'].get(key) if Ma else None
            fold = fk.get(key)
            extra = ''
            if part == 'mouth' and r.get('cover'):
                c = r['cover']
                extra = '<br>cover %.2f (skin %.2f, none %.2f)' % (c['cover'], c['skin'], c['none'])
                if ra and ra.get('cover'):
                    extra += '<br>against %.2f' % ra['cover']['cover']
            L.append('<div class="tile"><img src="%s" height="150">%s<br><b>%s</b> folds %s%s%s</div>' % (
                save(pic, 'ex_%s.png' % key, 150),
                ('<img src="%s" height="150">' % save(exprqa.paint(ra['cls'][:crop.shape[0], :] if part == 'eye' else
                                                                  ra['cls'][int((exprqa.WIN['top'] + 0.12) * 200):int((exprqa.WIN['top'] + 0.62) * 200), 30:-30]),
                                                      'ex_%s_against.png' % key, 150)) if ra else '',
                name, '-' if fold is None else fold, (' (against %s)' % fa.get(key)) if Ma and fa.get(key) is not None else '',
                extra))
        L.append('</div>')
    # blink and openings
    E = Mb['face'].get('eyes', {})
    L.append('<h2>Lids</h2><table><tr><th>eye key</th><th>opening (share of neutral) L / R</th><th>iris showing</th>'
             '<th>folds</th></tr>')
    for k, r in E.items():
        if not isinstance(r, dict) or 'L' not in r:
            continue
        L.append('<tr><td>%s</td><td>%s / %s</td><td>%s</td><td>%s</td></tr>' % (
            k, r['L']['open'], r['R']['open'], r['L']['iris'], fk.get('eye_' + k, '')))
    L.append('</table>')
    open(os.path.join(out, 'index.html'), 'w').write('\n'.join(L))
    strip = lambda M: {k: v for k, v in M.items() if not k.startswith('_')}
    json.dump({'eyes': {k: dict(view=e['view'], side=e['side'], ours=strip(e['mo']), design=strip(e['md']),
                                checks=e['cmp']) for k, e in Mb['eyes'].items()},
               'expressions': {k: dict(m=r['m'], cover=r.get('cover')) for k, r in Mb['ex'].items()},
               'folds': Mb['folds'], 'face': Mb['face'], 'az3': Mb['az3']},
              open(os.path.join(out, 'eyes.json'), 'w'), indent=1, default=lambda o: o.tolist() if hasattr(o, 'tolist') else str(o))
    return os.path.join(out, 'index.html')


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return 0
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    build = os.path.abspath(args[0])
    out = os.path.abspath(opt('--out', os.path.join(build, 'eyes')))
    against = opt('--against')
    print(page(build, out, os.path.abspath(against) if against else None))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
