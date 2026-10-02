"""The checkpoint review page (docs/CHARKIT_HANDOFF.md, step 5): one local HTML page, opened in the browser, with the
design (the generated references, the manifest's sheets) next to our builds view by view, the QA across the builds, and
the open decisions. Nothing to find or arrange by hand: every picture is cut, scaled alike and labelled.

    python -m charkit checkpoint SPEC --build LABEL=DIR [--build LABEL=DIR ...] [--out DIR] [--decisions FILE.md]
                                       [--link LABEL=PATH ...] [--no-open]
        the builds in order, oldest first (e.g. before=charkit/out/clawd reviewed=charkit/out/e2e/ck3_final
        now=charkit/out/confirm/ck5_final); a build's QA says which references graded it (its checks' own names);
        --decisions: a short markdown file (## headings, - bullets, paragraphs) shown after the summary
        -> DIR/index.html (default charkit/out/checkpoint) and its pictures in DIR/img
"""
import html, json, os, re, subprocess, sys, time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACE = {'front': 0, 'three_quarter': None, 'profile': 90}          # our face boards: 0 30 60 90 150 (3/4: the nearest)
BODY = {'front': 0, 'three_quarter': 35, 'profile': 90, 'back': 180}
KEY_CHECKS = [                                                     # (check, what it says) for the summary table
    ('sheet_profile', 'profile front edge vs the design, L'), ('sheet_nose_reach', 'nose projection, L'),
    ('sheet_chin_reach', 'chin projection, L'), ('sheet_profile_chin', 'chin height, L'),
    ('sheet_width', 'face width (worst ratio)'), ('sheet_neck_to_jaw', 'neck against jaw'),
    ('sheet_shown_front', 'face showing past the hair, front'), ('sheet_shown_three_quarter', 'face showing, 3/4'),
    ('sheet_shown_profile', 'face showing, profile'),
    ('eye_aspect', 'eye opening height / width'), ('eye_width', 'eye opening width'), ('eye_iris_ratio', 'iris in the opening'),
    ('eye_pupil_run', 'pupil height in the iris'), ('eye_pupil_aspect', 'pupil shape'),
    ('body_front_iou', 'front silhouette IoU'), ('body_profile_iou', 'profile silhouette IoU'),
    ('body_front_top', 'top of the head (buns), L'), ('body_front_boot', 'boot top, L'), ('body_front_feet', 'feet, L'),
    ('body_front_skirt_width', 'skirt width, front'), ('body_back_skirt_width', 'skirt width, back'),
    ('hair_noise', 'hair speckle'), ('face_folds', 'face mesh folds'), ('poke_share', 'skin through clothes'),
]


def _p(x):
    return x if os.path.isabs(x) else os.path.join(ROOT, x)


def _img(path):
    from PIL import Image
    return Image.open(path).convert('RGB')


def _trim(im, pad=10):
    a = np.asarray(im).astype(int)
    bg = a[:4, :4].reshape(-1, 3).mean(0)
    ys, xs = np.nonzero(np.abs(a - bg).sum(-1) > 30)
    if not len(ys):
        return im
    return im.crop((max(0, xs.min() - pad), max(0, ys.min() - pad), min(im.width, xs.max() + pad), min(im.height, ys.max() + pad)))


def _cut(full, box, mask, f=1.0):
    """a figure's box cut from a sheet at full resolution, everything outside its own silhouette (`mask`, at the sheet
    scaled by f) painted the sheet's background: no neighbour's hair or hand in the tile."""
    from PIL import Image
    x0, y0, x1, y1 = [int(round(c / f)) for c in box]
    im = np.asarray(full.crop((x0, y0, x1, y1))).copy()
    a = np.asarray(full)
    bg = np.median(np.concatenate([a[:4].reshape(-1, 3), a[-4:].reshape(-1, 3)]), 0).astype(np.uint8)
    H, W = mask.shape
    ys = np.clip(((np.arange(y0, y1) + 0.5) * f).astype(int), 0, H - 1)
    xs = np.clip(((np.arange(x0, x1) + 0.5) * f).astype(int), 0, W - 1)
    from scipy.ndimage import binary_dilation
    m = binary_dilation(mask, iterations=2)[np.ix_(ys, xs)]
    im[~m] = bg
    return Image.fromarray(im)


def _fit(im, h):
    return im.resize((max(1, int(im.width * h / im.height)), h))


def design_views(spec):
    """the design's pictures, cut from the manifest's generated sheets: {'face': {view: img}, 'body': {view: img},
    'eyes': {side: img}, 'az3': the head sheet's three-quarter angle}."""
    from PIL import Image
    from . import eyes as eyelib, refcheck, sheetqa
    ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else {}
    ex = eyelib._knobs(spec.get('eyes'))['x']
    out = {'face': {}, 'body': {}, 'eyes': {}, 'az3': 35.0}
    fs, bs, es = ref.get('face_sheet'), ref.get('body_sheet'), ref.get('eyes_sheet')
    if fs:
        rgb0 = refcheck._load(fs['image'])
        clean, _ = refcheck.without_guides(rgb0)
        rgb, f, H = refcheck.at_scale(clean, ex, 2 * ex * refcheck.FACE_PPL, fs.get('facing', -1))
        full = Image.fromarray((np.clip(rgb0, 0, 1) * 255).astype(np.uint8))
        for v in FACE:
            if v in H['heads']:
                out['face'][v] = _cut(full, H['heads'][v]['head'], H['heads'][v]['_mask'], f)
        out['az3'] = refcheck.face_design(rgb0, ex).get('az_three_quarter', 35.0)
    if es:
        crops, own = refcheck.eye_design(refcheck._load(es['image']), ex)
        out['eyes'] = {k: Image.fromarray((np.clip(v[..., :3], 0, 1) * 255).astype(np.uint8)) for k, v in crops.items()}
    if bs:
        rgb = refcheck._load(bs['image'])
        D = sheetqa.detect_figures(rgb, None, ex, bs.get('facing', -1))
        full = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
        for v in BODY:
            if v in D['figures']:
                out['body'][v] = _trim(_cut(full, D['figures'][v]['box'], D['figures'][v]['_mask']))
    return out


def _qa(build):
    p = os.path.join(_p(build), 'qa', 'qa.json')
    return json.load(open(p)).get('checks', {}) if os.path.exists(p) else {}


def _graded_against(checks):
    """which design a build's QA graded against: the generated sheets (retired checks gone, INFO by authority) or the
    model sheet."""
    if any(c.get('graded_as') for c in checks.values() if isinstance(c, dict)):
        return 'generated sheets'
    return 'idol_D / rig' if any(k.startswith('sheet_') for k in checks) else 'n/a'


def _counts(checks):
    n = {'PASS': 0, 'WARN': 0, 'FAIL': 0}
    for c in checks.values():
        if isinstance(c, dict) and c.get('status') in n:
            n[c['status']] += 1
    return n


def _md(text):
    """a short markdown file as HTML: ## headings, - bullets (one level), **bold**, paragraphs."""
    out, ul = [], False
    for line in text.splitlines():
        s = html.escape(line.rstrip())
        s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
        s = re.sub(r'`(.+?)`', r'<code>\1</code>', s)
        if s.startswith('- '):
            if not ul:
                out.append('<ul>'); ul = True
            out.append('<li>%s</li>' % s[2:])
            continue
        if ul and not s.startswith('  '):
            out.append('</ul>'); ul = False
        if s.startswith('## '):
            out.append('<h3>%s</h3>' % s[3:])
        elif s.startswith('  ') and ul:
            out[-1] = out[-1][:-5] + ' ' + s.strip() + '</li>'
        elif s.strip():
            out.append('<p>%s</p>' % s)
    if ul:
        out.append('</ul>')
    return '\n'.join(out)


def page(spec, builds, out, decisions=None, links=()):
    """-> the page's path. builds: [(label, dir)] oldest first."""
    img = os.path.join(out, 'img')
    os.makedirs(img, exist_ok=True)
    for f in os.listdir(img):
        os.remove(os.path.join(img, f))
    n = [0]

    def save(im, stem):
        n[0] += 1
        name = '%03d_%s.png' % (n[0], re.sub(r'[^a-z0-9_]+', '_', stem.lower()))
        im.save(os.path.join(img, name))
        return 'img/' + name
    D = design_views(spec)
    Q = {lab: _qa(d) for lab, d in builds}
    css = ('body{font:14px/1.45 -apple-system,system-ui,sans-serif;margin:24px;background:#fafafa;color:#222;max-width:1500px}'
           'h1{font-size:21px}h2{font-size:17px;margin-top:34px;border-bottom:1px solid #ddd;padding-bottom:4px}'
           'h3{font-size:15px;margin:16px 0 6px}.row{display:flex;gap:14px;align-items:flex-end;flex-wrap:wrap;margin:8px 0}'
           '.tile{text-align:center;font-size:12px;color:#555}.tile img{display:block;border:1px solid #ddd;background:#fff}'
           '.design img{border:2px solid #7a5}table{border-collapse:collapse;font-size:13px;margin:8px 0}'
           'td,th{border:1px solid #ddd;padding:3px 8px;text-align:right}th{background:#f0f0f0}'
           'td:first-child,th:first-child{text-align:left}.PASS{color:#1a7f37;font-weight:600}.WARN{color:#9a6700;'
           'font-weight:600}.FAIL{color:#cf222e;font-weight:600}.INFO,.SKIPPED{color:#888}.note{color:#666;font-size:12px}'
           'code{background:#f0f0f0;padding:0 3px}')
    L = ['<!doctype html><meta charset="utf-8"><title>charkit checkpoint: %s</title><style>%s</style>' % (
        html.escape(spec.get('name', '')), css),
        '<h1>charkit checkpoint review: %s</h1><p class="note">%s. The design is the generated references (the '
        'manifest\'s sheets: <code>head_turnaround</code>, <code>body_turnaround</code>; idol_D is the source design). '
        'Builds, oldest first: %s.</p>' % (html.escape(spec.get('name', '')), time.strftime('%Y-%m-%d %H:%M'),
                                           ', '.join('<b>%s</b> (<code>%s</code>)' % (html.escape(l), html.escape(d))
                                                     for l, d in builds))]
    # the summary
    L.append('<h2>QA summary</h2><table><tr><th>build</th><th>graded against</th><th>PASS</th><th>WARN</th><th>FAIL</th></tr>')
    for lab, d in builds:
        c = _counts(Q[lab])
        L.append('<tr><td>%s</td><td>%s</td><td class="PASS">%d</td><td class="WARN">%d</td><td class="FAIL">%d</td></tr>' % (
            html.escape(lab), _graded_against(Q[lab]), c['PASS'], c['WARN'], c['FAIL']))
    L.append('</table><p class="note">Counts across different references are not comparable one to one: the builds '
             'graded against idol_D were measured against another drawing, at another scale.</p>')
    L.append('<table><tr><th>check</th><th>what it says</th>%s</tr>' % ''.join('<th>%s</th>' % html.escape(l) for l, _ in builds))
    for k, what in KEY_CHECKS:
        cells = []
        for lab, _ in builds:
            c = Q[lab].get(k)
            if not c:
                cells.append('<td></td>'); continue
            v = c.get('value')
            v = ('%.3f' % v) if isinstance(v, float) else json.dumps(v)
            cells.append('<td class="%s">%s %s</td>' % (c.get('status', ''), html.escape(v), c.get('status', '')))
        L.append('<tr><td><code>%s</code></td><td>%s</td>%s</tr>' % (k, html.escape(what), ''.join(cells)))
    L.append('</table>')
    L += _moved(builds, Q)
    if decisions and os.path.exists(_p(decisions)):
        L.append('<h2>Decisions for this review</h2>' + _md(open(_p(decisions)).read()))

    def row(title, items, h):
        L.append('<h3>%s</h3><div class="row">' % html.escape(title))
        for im, cap, design in items:
            if im is None:
                continue
            L.append('<div class="tile%s"><img src="%s">%s</div>' % (' design' if design else '', save(_fit(im, h), title + cap),
                                                                      html.escape(cap)))
        L.append('</div>')
    # the body, view by view
    L.append('<h2>The whole figure</h2><p class="note">Each figure cut to its outline and scaled to one height (the design '
             'framed green). Proportions are the QA\'s job (above); this is for the eye.</p>')
    for v, a in BODY.items():
        items = [(D['body'].get(v), 'design: body_turnaround %s' % v.replace('_', '-'), True)]
        for lab, d in builds:
            p = os.path.join(_p(d), 'boards', 'body_%03d.png' % a)
            items.append((_trim(_img(p)) if os.path.exists(p) else None, '%s: %d deg' % (lab, a), False))
        row(v.replace('_', '-'), items, 520)
    # the face
    L.append('<h2>The face</h2>')
    a3 = min((30, 60), key=lambda a: abs(a - D['az3']))
    for v, a in FACE.items():
        a = a3 if a is None else a
        items = [(D['face'].get(v), 'design: head_turnaround %s' % v.replace('_', '-'), True)]
        for lab, d in builds:
            p = os.path.join(_p(d), 'boards', 'face_%03d.png' % a)
            items.append((_img(p) if os.path.exists(p) else None, '%s: %d deg' % (lab, a), False))
        row(v.replace('_', '-'), items, 340)
    # the eyes
    L.append('<h2>The eyes</h2>')
    items = [(D['eyes'].get(s), 'design: head_turnaround eye (%s)' % s, True) for s in ('R', 'L')]
    lab, d = builds[-1]
    p = os.path.join(_p(d), 'qa', 'qa_eyes.png')
    items.append((_img(p) if os.path.exists(p) else None, '%s: the QA\'s eye measurement (design crop | its masks | ours | '
                                                           'ours masked)' % lab, False))
    row('front eyes', items, 260)
    # expressions: the template library, no reference
    L.append('<h2>Expressions and mouths</h2><p class="note">The template library (cross-character), with no design '
             'reference to compare against (Michael, 2026-09-28).</p>')
    items = []
    for lab, d in builds[-2:]:
        p = os.path.join(_p(d), 'sheet_face.png')
        items.append((_img(p) if os.path.exists(p) else None, lab, False))
    row('expression and mouth boards', items, 300)
    # the QA's own overlays of the newest build
    lab, d = builds[-1]
    L.append('<h2>The QA\'s overlays (%s)</h2>' % html.escape(lab))
    for f, cap in (('qa_sheet_body.png', 'body classes against body_turnaround (grey both, red ours only, blue the design only)'),
                   ('qa_sheet.png', 'face regions against head_turnaround, front, three-quarter, profile')):
        p = os.path.join(_p(d), 'qa', f)
        if os.path.exists(p):
            row(cap, [(_img(p), f, False)], 700 if 'body' in f else 260)
    if links:
        L.append('<h2>More</h2><ul>%s</ul>' % ''.join('<li><a href="%s">%s</a></li>' % (
            html.escape(os.path.relpath(_p(p), out)), html.escape(lab)) for lab, p in links))
    path = os.path.join(out, 'index.html')
    open(path, 'w').write('\n'.join(L))
    return path


MOVED = 0.25                    # warn bands: a check that moves this far without changing its status is listed


def _moved(builds, Q):
    """the checks the newest build moved by MOVED warn bands or more (charkit.checks.severity) without changing their
    status: a WARN that slid to the edge of FAIL reads the same in a status count."""
    from . import checks
    if len(builds) < 2:
        return []
    (la, _), (lb, _) = builds[-2], builds[-1]
    rows = []
    for k in sorted(set(Q[la]) & set(Q[lb])):
        a, b = Q[la][k], Q[lb][k]
        if a.get('status') != b.get('status') or a.get('status') not in ('WARN', 'FAIL'):
            continue
        sa, sb = checks.severity(k, a.get('value')), checks.severity(k, b.get('value'))
        if sa is None or sb is None or abs(sb - sa) < MOVED:
            continue
        rows.append((sb - sa, k, a, b))
    if not rows:
        return []
    L = ['<h3>Moved within their status: %s against %s</h3><p class="note">%d checks moved %.2f warn bands or more '
         'without changing status (a status count hides them). + is worse.</p><table><tr><th>check</th><th>status</th>'
         '<th>%s</th><th>%s</th><th>warn bands</th></tr>' % (html.escape(lb), html.escape(la), len(rows), MOVED,
                                                           html.escape(la), html.escape(lb))]
    for d, k, a, b in sorted(rows, key=lambda r: -r[0]):
        L.append('<tr><td><code>%s</code></td><td class="%s">%s</td><td>%s</td><td>%s</td><td class="%s">%+.2f</td></tr>' % (
            k, b['status'], b['status'], html.escape(json.dumps(a.get('value'))), html.escape(json.dumps(b.get('value'))),
            'FAIL' if d > 0 else 'PASS', d))
    L.append('</table>')
    return L


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return
    from . import bodyeval
    spec = bodyeval.resolve(args[0])
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    builds = [tuple(args[i + 1].split('=', 1)) for i, a in enumerate(args) if a == '--build']
    links = [tuple(args[i + 1].split('=', 1)) for i, a in enumerate(args) if a == '--link']
    out = _p(opt('--out', 'charkit/out/checkpoint'))
    p = page(spec, builds, out, opt('--decisions'), links)
    print('page:', p)
    if '--no-open' not in args:
        subprocess.run(['open', p])


if __name__ == '__main__':
    main(sys.argv[1:])
