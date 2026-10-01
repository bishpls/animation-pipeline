"""The standard review page (`charkit review page`): what every round's hand-made page did, from one small JSON. Michael's
order (charkit-worker rules, "Review pages for Michael"): the summary box first (Recommended, Asked of Michael, Key
numbers), then per view the design beside each build at matching scale, then close-ups by named region at matching
scale in L, then the numbers.

    python -m charkit review page PAGE.json [--out DIR] [--open]

PAGE.json:
  title       the page's title
  summary     {"recommended": "...", "asked": ["yes/no or A/B question", ...] (or "nothing: informational"),
               "numbers": {"columns": [...], "rows": [[...], ...]}} (or numbers from `checks` below when omitted)
  builds      [{"label": "before", "path": BUILD}, ...]: build folders (a preview's, a box build fetched here); each
              with boards (views,body,design) or a bundle to draw from
  views       the views shown (default front, three_quarter, profile, back)
  regions     the close-ups (default face, hair, bow, hands; REGIONS): named windows in L round the eye line, each
              cut from the design and every build and resampled to one px per L, so a column's scale is the next's
  checks      check names or fnmatch patterns for the numbers table (each build's qa.json, side by side, flag checks
              marked); with a sweep, its rows
  sweep       a sweep's result (charkit/sweep.py: OUT/sweep.json): its table (with deltas against its control) and each
              row's board
  notes       extra paragraphs (HTML-escaped) after the summary
  figures     extra sections of given pictures after the notes: [{"title", "text", "height", "images": [{"path",
              "caption"}]}] (a round's own measurement pictures: the drawn locks, a fit's overlay)

Writes DIR/index.html and DIR/img/ (default charkit/out/review_pages/<title slug>/); every picture links its source.
The design's pictures come from the manifest's head and body turnarounds (charkit.preview.design_refs); a build's from
its preview page crops when it has them, else cut from its design and body boards as charkit.preview cuts them, else
drawn from its bundle (charkit.qa3d.draw). A build folder is only read; every picture is written under DIR/img.
"""
import fnmatch, html, json, os, re, subprocess, sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWS = (('front', 0), ('three_quarter', 35), ('profile', 90), ('back', 180))
RANK = ('PASS', 'WARN', 'FAIL')
# name: (what, views, source, window (x0, x1, z_top, z_bottom) in L round the eye line, px per L on the page). source:
# head (the page's head crops: the design board / head_turnaround), design (the build's design board: the chest down to
# 1.2 L under the eye line), body (the body boards, located by the QA's body_<view>_top and _feet), bundle (drawn from
# the build's bundle at the page's scale, the design's from its body turnaround: for close-ups finer than the boards)
REGIONS = {
    'face': ('the face: eyes, brows, nose mark, mouth, jaw and chin', ('front', 'three_quarter', 'profile'), 'head',
             (-0.62, 0.62, 0.45, -0.78), 300),
    'hair': ('the hair: ahoge, bangs, side locks, the back mass and hem, flyaways, buns',
             ('three_quarter', 'profile', 'back'), 'head', (-1.0, 1.0, 1.2, -1.0), 220),
    'bow': ('the bow: knot, lobes, creases, the ribbons over the jacket (the design board stops 1.2 L under the eye '
            'line)', ('front', 'three_quarter', 'profile'), 'design', (-0.72, 0.72, -0.3, -1.2), 330),
    'hands': ('the hands below the cuffs', ('front', 'three_quarter', 'profile', 'back'), 'body',
              (-1.75, 1.75, -1.75, -3.0), 120),
    'hands_close': ('the hands close up, below the cuffs (ours drawn from each build\'s bundle with the QA\'s renderer at '
                    'this scale: the body boards draw a hand some 60 px long; the design\'s body turnaround resampled)',
                    ('front', 'three_quarter', 'profile', 'back'), 'bundle', (-1.75, 1.75, -1.85, -2.75), 320),
    'hands_board': ('the hands close up on the body boards (the build\'s renderer, EEVEE on the render boxes: what a '
                    'reviewer sees; resampled to this scale from the boards\' ~110 px/L)',
                    ('front', 'three_quarter', 'profile', 'back'), 'body', (-1.75, 1.75, -1.85, -2.75), 320),
    'skirt': ('the skirt: its cream front panel, the panel\'s creases and folds, the pleats and hem band',
              ('front', 'three_quarter', 'profile'), 'body', (-1.2, 1.2, -1.35, -2.8), 140),
}
CLOSE_H = 300                       # px: every close-up shown at this height (a region's crops share one window)
CSS = """
:root{--bg:#f6f5f2;--fg:#222;--card:#fff;--line:#ddd;--k:#666;--pass:#17803d;--warn:#a36200;--fail:#c01d1d;--acc:#2b5fb4}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#1b1b1d;--fg:#e8e8e8;--card:#26262a;
--line:#3a3a40;--k:#a0a0a8;--pass:#4cc27a;--warn:#e0a040;--fail:#ff6b6b;--acc:#7fa8ff}}
body{font:14px/1.45 -apple-system,system-ui,sans-serif;margin:20px;background:var(--bg);color:var(--fg)}
a{color:var(--acc)}h1{margin:0 0 10px}h2{margin:28px 0 8px}h3{margin:16px 0 6px}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;margin-bottom:10px}
.cmp{flex-wrap:nowrap;overflow-x:auto}.cmp figure{flex:0 0 auto}.cmp figure img{max-width:none}
figure{margin:0;background:var(--card);border:1px solid var(--line);border-radius:6px;padding:6px}
figure img{display:block;max-width:100%}figcaption{font-size:12px;color:var(--k);margin-top:4px;max-width:520px}
.box{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:10px 14px;max-width:1300px;
margin-bottom:10px}.summary{border:2px solid var(--acc)}
code{font-size:12px}.k{color:var(--k);font-size:12px}
table{border-collapse:collapse;font-size:13px}td,th{padding:3px 9px;border-bottom:1px solid var(--line);text-align:left;
vertical-align:top}th{font-weight:600}
.PASS{color:var(--pass);font-weight:600}.WARN{color:var(--warn);font-weight:600}.FAIL{color:var(--fail);font-weight:600}
.INFO,.SKIPPED{color:var(--k)}
"""


def esc(s):
    return html.escape(str(s))


def _slug(s):
    return re.sub(r'[^a-z0-9]+', '_', str(s).lower()).strip('_')[:60] or 'page'


# ------------------------------------------------------------------------------------------------------------ pictures
class Page:
    """the page being made: its folder, its pictures (written under img/), the design's references."""

    def __init__(self, out):
        self.out = out
        self.img = os.path.join(out, 'img')
        os.makedirs(self.img, exist_ok=True)
        self._design = None

    def rel(self, p):
        return os.path.relpath(p, self.out)

    def save(self, a, name):
        from . import preview as P
        p = os.path.join(self.img, name + '.png')
        P._save(a, p)
        return p

    def fig(self, src, cap, h=None, link=None):
        st = (' style="height:%dpx"' % h) if h else ''
        return '<figure><a href="%s"><img src="%s"%s loading="lazy"></a><figcaption>%s</figcaption></figure>' % (
            esc(self.rel(link or src)), esc(self.rel(src)), st, cap)

    def design(self):
        if self._design is None:
            from . import preview as P
            self._design = P.design_refs()
        return self._design


def build_crops(page, d, k, log=print):
    """a build's head and full-figure crops at the page's matching scales, written into the page's own folder (a build
    folder is only read: it may be another worktree's): its page crops when a preview made them, else cut from its
    design and body boards (charkit.preview's crops), else drawn from its bundle -> {name: path}."""
    from . import preview as P
    pj = os.path.join(d, 'page', 'crops.json')
    if os.path.exists(pj):
        got = {n: os.path.join(d, p) for n, p in (json.load(open(pj)).get('got') or {}).items()}
        if got and all(os.path.exists(p) for p in got.values()):
            return got
    got = {}
    heads, source = P.our_heads(d, log)
    for v, img in heads.items():
        got['head_' + v] = page.save(img, 'b%d_head_%s' % (k, v))
    B = None
    for az in P.BODY_AZ:
        p = os.path.join(d, 'boards', 'body_%03d.png' % az)
        if os.path.exists(p):
            img = P.figure_crop(P._load(p))
        elif os.path.isdir(os.path.join(d, 'bundle')):
            from . import bundle
            B = B or bundle.load(os.path.join(d, 'bundle'))
            img = P.figure_crop(draw_figure(B, az))
        else:
            continue
        got['body_%03d' % az] = page.save(img, 'b%d_body_%03d' % (k, az))
    return got


def draw_window(bdir, view, az, box, oppl, ss=2):
    """a close-up's window (x0, x1, z_top, z_bottom) in L round the eye line drawn from a bundle (charkit.qa3d.draw) at
    oppl px per L, from azimuth az, centred as the QA centres the view (charkit.bodyqa.origin) -> RGB floats."""
    from . import bundle, bodyqa, declared, qa3d
    B = bundle.load(bdir)
    L = float(B.assembly['L'])
    org = bodyqa.origin(view, az, np.array(qa3d.iris_centres(B)), B.assembly['centre'])
    x0, x1, zt, zb = box

    class Win(declared._Grid):
        def __init__(self):
            self.origin = (org[0] + 0.5 * (x0 + x1) * L, org[1])
            self.pix = L / (oppl * ss)
            self.win = dict(x=0.5 * (x1 - x0) * L, top=zt * L, bottom=zb * L)
    surfs = []
    for o in B.objects():
        variant = 'masked' if o.group == 'skin' and o.has('masked') else 'eval'
        if o.has(variant):
            surfs += qa3d.surfaces(B, o, variant)
    img = qa3d.draw(B, surfs, az, Win(), ss=ss)
    a = img[..., 3:4]
    return img[..., :3] * a + np.asarray(qa3d._srgb(np.array(qa3d.WORLD)))[None, None] * (1 - a)


def draw_figure(B, az, k=2):
    """the whole figure drawn from a bundle (charkit.qa3d.draw, the QA's renderer) on the world's colour -> RGB floats."""
    from . import qa3d
    zr = B.assembly.get('raw_z')
    if zr is None:
        fr0 = qa3d.figure_frame(B)
        zr = (fr0.zc - fr0.scale / 2.16, fr0.zc + fr0.scale / 2.16)
    fr = qa3d.Frame(float(zr[0]), float(zr[1]), res=(qa3d.FRAME[0] * k, qa3d.FRAME[1] * k), ss=1)
    surfs = []
    for o in B.objects():
        variant = 'masked' if o.group == 'skin' and o.has('masked') else 'eval'
        if o.has(variant):
            surfs += qa3d.surfaces(B, o, variant)
    img = qa3d.draw(B, surfs, az, fr, ss=1)
    a = img[..., 3:4]
    return img[..., :3] * a + np.asarray(qa3d._srgb(np.array(qa3d.WORLD)))[None, None] * (1 - a)


def head_cx(fg, top, ppl):
    rows = fg[max(0, int(top)):int(top + 1.3 * ppl)]
    cols = np.nonzero(rows.any(0))[0]
    return (cols[0] + cols[-1]) / 2.0 if len(cols) else fg.shape[1] / 2.0


def cut_L(rgb, eye, ppl, box, out_ppl, fill=None):
    """rgb's window box = (x0, x1, z_top, z_bottom) in L round eye (x, y px) at ppl -> resampled to out_ppl px per L."""
    from . import preview as P
    x0, x1, zt, zb = box
    fill = np.median(rgb[:8, :8].reshape(-1, 3), 0) if fill is None else fill
    c = P._cut(rgb, int(round(eye[0] + x0 * ppl)), int(round(eye[1] - zt * ppl)), int(round(eye[0] + x1 * ppl)),
               int(round(eye[1] - zb * ppl)), fill)
    return P._resize(c, (x1 - x0) * out_ppl, (zt - zb) * out_ppl)


def design_frame(design, view):
    """the design's body figure for a view: (rgb with the other figures blanked, (cx, eye_y), ppl)."""
    from . import bodyqa, preview as P, sheetqa
    if 'body_rgb' not in design:
        design['body_rgb'] = P._load(design['body'])
        design['body_D'] = sheetqa.detect_figures(design['body_rgb'], None, 0.168, -1)
    D = design['body_D']
    f, ppl = D['figures'][view], D['ppl']
    eye = bodyqa.view_eye(view, f)
    rgb = design['body_rgb'].copy()
    bg = np.median(rgb[:8, :8].reshape(-1, 3), 0)
    m = np.zeros(rgb.shape[:2], bool)
    x0, y0, x1, y1 = [int(v) for v in f['box']]
    m[y0:y1, x0:x1] = True
    rgb[~m] = bg
    return rgb, (head_cx(P._fg(rgb, bg), y0, ppl), eye[1]), ppl


def body_frame(d, view, az):
    """ours on a body board: (rgb, (cx, eye_y), ppl) from the figure's rows and the build's QA body_<view>_top / _feet."""
    from . import preview as P
    rgb = P._load(os.path.join(d, 'boards', 'body_%03d.png' % az))
    C = json.load(open(os.path.join(d, 'qa', 'qa.json')))['checks']
    top, feet = C['body_%s_top' % view]['ours'], C['body_%s_feet' % view]['ours']
    fg = P._fg(rgb)
    rows = np.nonzero(fg.any(1))[0]
    ppl = (rows[-1] + 1 - rows[0]) / (top - feet)
    return rgb, (head_cx(fg, rows[0], ppl), rows[0] + top * ppl), ppl


def closeup(page, region, view, builds, crops):
    """one region in one view: the design, then each build -> [(path, caption, link)] (a missing source: skipped)."""
    from . import preview as P
    what, views, src, box, oppl = REGIONS[region]
    az = dict(VIEWS)[view]
    design = page.design()
    row = []
    try:
        if src == 'head':
            hp = os.path.join(page.img, 'design_head_%s.png' % view)
            if not os.path.exists(hp):
                h = design['heads'].get(view)
                m = 0.03 * design['head_ppl']
                P._save(P.head_crop(P._load(design['head']), h['eye_y'], design['head_ppl'],
                                    xlim=(h['box'][0] - m, h['box'][2] + m), clip=True), hp)
            rgb = P._load(hp)
            a = cut_L(rgb, (rgb.shape[1] / 2, P.WIN['up'] * P.PPL_OUT), P.PPL_OUT, box, oppl)
            cap = 'design (head_turnaround)'
        else:
            rgb, eye, ppl = design_frame(design, view)
            a = cut_L(rgb, eye, ppl, box, oppl)
            cap = 'design (body_turnaround, %.0f px/L)' % ppl
        row.append((page.save(a, 'cu_%s_%s_design' % (region, view)), cap, None))
    except (KeyError, TypeError, OSError, IndexError):
        pass
    for k, b in enumerate(builds):
        d = b['path']
        try:
            if src == 'head':
                p = crops[k].get('head_' + view)
                rgb = P._load(p)
                a = cut_L(rgb, (rgb.shape[1] / 2, P.WIN['up'] * P.PPL_OUT), P.PPL_OUT, box, oppl)
                link = p
            elif src == 'bundle':
                link = os.path.join(d, 'bundle')
                a = draw_window(link, view, az, box, oppl)
            elif src == 'design':
                link = os.path.join(d, 'boards', 'design_%03d.png' % az)
                rgb = P._load(link)
                a = cut_L(rgb, (rgb.shape[1] / 2, rgb.shape[0] / 2), rgb.shape[0] / P.DESIGN_WINDOW, box, oppl)
            else:
                link = os.path.join(d, 'boards', 'body_%03d.png' % az)
                rgb, eye, ppl = body_frame(d, view, az)
                a = cut_L(rgb, eye, ppl, box, oppl)
        except (KeyError, TypeError, OSError, IndexError, ValueError):
            if src == 'head' or not os.path.isdir(os.path.join(d, 'bundle')):
                continue
            # no boards (a build made with --boards ''): the window drawn from its bundle at the same scale
            a, link = draw_window(os.path.join(d, 'bundle'), view, az, box, oppl), os.path.join(d, 'bundle')
        row.append((page.save(a, 'cu_%s_%s_%d' % (region, view, k)), esc(b['label']), link))
    return row


# ------------------------------------------------------------------------------------------------------------ numbers
def fmtv(v):
    if isinstance(v, float):
        return '%.4g' % v
    if isinstance(v, (list, dict)):
        return esc(json.dumps(v)[:48])
    return esc(v)


def cell(c):
    if not c:
        return '<span class="k">absent</span>'
    s = c.get('status', '?')
    g = c.get('grade')
    out = '%s <span class="%s">%s</span>' % (fmtv(c.get('value')), esc(s), esc(s))
    if g and g != s:
        out += ' <span class="k">(grade <span class="%s">%s</span>)</span>' % (esc(g), esc(g))
    return out


def qa_of(d):
    p = os.path.join(d, 'qa', 'qa.json')
    return json.load(open(p)).get('checks', {}) if os.path.exists(p) else {}


def checks_table(builds, patterns):
    """each build's qa.json on the named checks (patterns), side by side; flag checks marked [F] -> HTML."""
    Q = [qa_of(b['path']) for b in builds]
    names = []
    for C in Q:
        for k in C:
            if k not in names and any(fnmatch.fnmatchcase(k, p) for p in patterns):
                names.append(k)
    if not names:
        return '<p class="k">No check matches %s in these builds.</p>' % esc(', '.join(patterns))
    H = ['<table><tr><th>check</th>' + ''.join('<th>%s</th>' % esc(b['label']) for b in builds) + '</tr>']
    for k in names:
        flag = any((C.get(k) or {}).get('flag') for C in Q)
        H.append('<tr><td><code>%s</code>%s</td>%s</tr>' % (esc(k), ' <span class="k">[F]</span>' if flag else '',
                                                            ''.join('<td>%s</td>' % cell(C.get(k)) for C in Q)))
    return ''.join(H) + '</table>'


def key_numbers(builds, patterns, limit=8):
    """the summary's key numbers when the JSON gives none: the first `limit` named checks across the builds."""
    Q = [qa_of(b['path']) for b in builds]
    names = []
    for C in Q:
        for k in C:
            if k not in names and any(fnmatch.fnmatchcase(k, p) for p in patterns):
                names.append(k)
    rows = [[k] + [fmtv((C.get(k) or {}).get('value')) + ' ' + str((C.get(k) or {}).get('status', '')) for C in Q]
            for k in names[:limit]]
    return dict(columns=['check'] + [b['label'] for b in builds], rows=rows)


def sweep_section(page, path):
    """a sweep's table (sweep.md, as HTML) and its rows' boards -> HTML."""
    from . import sweep as sw
    res = json.load(open(path))
    rows = res['rows']
    ctrl = next((r for r in rows if r.get('control')), None)
    pats = res['decl'].get('checks')
    names = [k for k in dict.fromkeys(k for r in rows for k in r['checks'])
             if not pats or any(fnmatch.fnmatchcase(k, p) for p in pats)]
    H = ['<p class="k">%s stage on <code>%s</code>; code %s; deltas against <code>%s</code>.</p>' % (
        esc(res['decl'].get('stage')), esc(res['decl'].get('base')), esc(res.get('commit')),
        esc(ctrl['name'] if ctrl else 'none'))]
    H.append('<table><tr><th>row</th>' + ''.join('<th>%s</th>' % esc(k) for k in names) + '</tr>')
    for r in rows:
        cells = []
        for k in names:
            c, c0 = r['checks'].get(k), (ctrl or {}).get('checks', {}).get(k)
            s = cell(c)
            if c and c0 and r is not ctrl and isinstance(c.get('value'), (int, float)) and \
                    isinstance(c0.get('value'), (int, float)) and c['value'] != c0['value']:
                s += ' <span class="k">(%+.4g)</span>' % (c['value'] - c0['value'])
            cells.append('<td>%s</td>' % s)
        H.append('<tr><td><code>%s</code></td>%s</tr>' % (esc(r['name']), ''.join(cells)))
    H.append('</table>')
    G = res.get('guard') or []
    H.append('<p><b>Guard:</b> %s</p>' % (esc('; '.join('%s: %s improves while %s %s %.3f -> %.3f' % (
        g['row'], g['check'], g['shape'], g['view'], g['control'], g['row_value']) for g in G)) if G else
        'no row improves a check while a piece\'s shape IoU drops more than 15% in a view.'))
    figs = []
    base = os.path.dirname(os.path.abspath(path))
    for r in rows:
        b = os.path.join(base, sw._safe(r['name']), 'board.png')
        if os.path.exists(b):
            figs.append(page.fig(b, '<code>%s</code>' % esc(r['name']), h=260))
    if figs:
        H.append('<div class="row">%s</div>' % ''.join(figs))
    return ''.join(H)


def figures_section(page, sec):
    """a section of given pictures (a round's own measurement pictures: the drawn locks, a fit's overlay): {"title",
    "text", "height", "images": [{"path", "caption"}]}, each copied under img/ and shown in one row at one height."""
    import shutil
    H = ['<h2>%s</h2>' % esc(sec.get('title') or '')]
    if sec.get('text'):
        H.append('<p class="k">%s</p>' % esc(sec['text']))
    figs = []
    for k, f in enumerate(sec.get('images') or ()):
        src = os.path.abspath(os.path.expanduser(f['path']))
        if not os.path.exists(src):
            continue
        dst = os.path.join(page.img, 'fig_%s_%d_%s' % (_slug(sec.get('title'))[:24], k, os.path.basename(src)))
        shutil.copyfile(src, dst)
        figs.append(page.fig(dst, esc(f.get('caption') or ''), h=sec.get('height')))
    H.append('<div class="row cmp">%s</div>' % ''.join(figs))
    return ''.join(H)


# ------------------------------------------------------------------------------------------------------------ the page
def make(spec, out=None, log=print):
    """the page from a PAGE.json's dict -> its index.html path."""
    from . import preview as P
    title = spec.get('title') or 'review'
    out = os.path.abspath(out or os.path.join(ROOT, 'charkit', 'out', 'review_pages', _slug(title)))
    page = Page(out)
    builds = [dict(b, path=os.path.abspath(os.path.expanduser(b['path']))) for b in spec.get('builds') or ()]
    views = [v for v, _ in VIEWS if v in (spec.get('views') or [v for v, _ in VIEWS])]
    regions = [r for r in (spec.get('regions') or list(REGIONS)) if r in REGIONS]
    patterns = spec.get('checks') or []
    design = page.design() if builds else None
    crops = []
    for k, b in enumerate(builds):
        try:
            crops.append(build_crops(page, b['path'], k, log))
        except Exception as e:                  # (a build without boards or bundle: its pictures are skipped)
            log('review page: no crops for %s (%s: %s)' % (b['label'], type(e).__name__, e))
            crops.append({})
    H = ['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" '
         'content="width=device-width,initial-scale=1"><title>%s</title><style>%s</style>' % (esc(title), CSS),
         '<h1>%s</h1>' % esc(title)]
    # the summary box: Recommended, Asked of Michael, Key numbers
    S = spec.get('summary') or {}
    asked = S.get('asked') or ['nothing: informational']
    asked = [asked] if isinstance(asked, str) else asked
    nums = S.get('numbers') or (key_numbers(builds, patterns) if patterns and builds else None)
    H.append('<div class="box summary"><p><b>Recommended:</b> %s</p><p><b>Asked of Michael:</b></p><ul>%s</ul>' % (
        esc(S.get('recommended') or '(none given)'), ''.join('<li>%s</li>' % esc(a) for a in asked)))
    if nums:
        H.append('<p><b>Key numbers:</b></p><table><tr>%s</tr>%s</table>' % (
            ''.join('<th>%s</th>' % esc(c) for c in nums['columns']),
            ''.join('<tr>%s</tr>' % ''.join('<td>%s</td>' % esc(x) for x in r) for r in nums['rows'])))
    H.append('</div>')
    for p in spec.get('notes') or ():
        H.append('<p>%s</p>' % esc(p))
    for sec in spec.get('figures') or ():
        H.append(figures_section(page, sec))
    # per view: the design beside every build, the full figure at one height, the head at one px per L
    if builds:
        H.append('<h2>Per view: the design and %s</h2><p class="k">Full figures at %d px tall; heads at %d px per L '
                 '(the design\'s convention: its front eyes 2 eye_x L apart).</p>' % (
                     ', '.join(esc(b['label']) for b in builds), P.BODY_H, P.PPL_OUT))
        tmp = os.path.join(page.img, '_design')
        os.makedirs(tmp, exist_ok=True)
        for v in views:
            az = dict(VIEWS)[v]
            H.append('<h3>%s</h3>' % esc(v.replace('_', ' ')))
            figs = []
            try:
                if v in design['figures']:
                    img = P.figure_crop(P._load(design['body']), design['figures'][v])
                    figs.append(page.fig(page.save(img, 'design_body_' + v), 'design (body_turnaround)', link=design['body']))
            except (KeyError, OSError):
                pass
            for k, b in enumerate(builds):
                p = crops[k].get('body_%03d' % az)
                if p and os.path.exists(p):
                    figs.append(page.fig(p, esc(b['label']), link=os.path.join(b['path'], 'boards', 'body_%03d.png' % az)))
            heads = []
            hd = design['heads'].get(v) if design else None
            if hd:
                m = 0.03 * design['head_ppl']
                img = P.head_crop(P._load(design['head']), hd['eye_y'], design['head_ppl'],
                                  xlim=(hd['box'][0] - m, hd['box'][2] + m), clip=True)
                heads.append(page.fig(page.save(img, 'design_head_' + v), 'design (head_turnaround)', h=300,
                                      link=design['head']))
            for k, b in enumerate(builds):
                p = crops[k].get('head_' + v)
                if p and os.path.exists(p):
                    heads.append(page.fig(p, esc(b['label']), h=300))
            H.append('<div class="row cmp">%s</div><div class="row cmp">%s</div>' % (''.join(figs), ''.join(heads)))
        # close-ups by region
        H.append('<h2>Close-ups</h2><p class="k">Each region cut in L round the eye line from the design and every '
                 'build, resampled to one px per L: a column\'s scale is the next\'s.</p>')
        for r in regions:
            what, rviews = REGIONS[r][0], REGIONS[r][1]
            H.append('<h3>%s</h3><p class="k">%s</p>' % (esc(r), esc(what)))
            for v in rviews:
                if v not in views:
                    continue
                row = closeup(page, r, v, builds, crops)
                if row:                     # (one row, one height: the columns share the region's px per L)
                    H.append('<div class="row cmp">%s</div>' % ''.join(
                        page.fig(p, '%s, %s' % (cap, esc(v.replace('_', ' '))), h=CLOSE_H, link=link)
                        for p, cap, link in row))
    if spec.get('sweep'):
        H.append('<h2>Sweep</h2>' + sweep_section(page, os.path.abspath(os.path.expanduser(spec['sweep']))))
    if patterns and builds:
        H.append('<h2>Numbers</h2><p class="k">Each build\'s qa.json; [F]: one of Michael\'s flag checks.</p>' +
                 checks_table(builds, patterns))
    H.append('<p class="k">Builds: %s.</p>' % '; '.join('%s <a href="%s"><code>%s</code></a>' % (
        esc(b['label']), esc(page.rel(b['path'])), esc(b['path'])) for b in builds))
    path = os.path.join(out, 'index.html')
    open(path, 'w').write('\n'.join(H) + '\n')
    return path


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    spec = json.load(open(args[0]))
    path = make(spec, opt('--out'))
    print(path)
    if '--open' in args and sys.platform == 'darwin':
        subprocess.run(['open', path])
    return 0
