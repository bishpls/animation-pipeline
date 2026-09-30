"""The chin and jaw review page: the head sheet's front, three-quarter and profile beside the builds' face boards, at one
px per L (the boards' camera: 85 mm, 1 m, level at the eye line + 0.06 L), whole heads and close on the chin and neck;
the jaw checks' pictures (charkit.faceregion: the boards' camera and outline emulated, the face region tinted, the jaw
line's columns marked); and the numbers, before and after, with the face region's other checks and the gate's.

    python jaw_page.py OUT_DIR BUILD [BUILD ...] [--labels a,b,...] [--bare DIR,DIR,...]

BUILD: a build folder (boards/, bundle/, qa/qa.json). --bare: face_views.py render folders (hair hidden), one per build.
Opens nothing; prints the page's path."""
import html, json, os, sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from charkit import bundle as bl, faceregion as fr, manifest, refcheck  # noqa: E402

PPL = 420                                       # px per L on the page
VIEWS = (('front', 'face_000.png'), ('three_quarter', 'face_030.png'), ('profile', 'face_090.png'))
CROPS = {'head': (0.35, 0.8, 0.55), 'chin': (-0.15, 0.6, 0.32)}   # (L over the eyes, L under, L either side)
CHECKS_JAW = ('jaw_taper', 'chin_point_z', 'chin_v', 'neck_to_face', 'jaw_line_front', 'jaw_line_three_quarter',
              'chin_underside', 'neck_front_wiggle')
CHECKS_FACE = ('eye_hollow_L', 'cheek_lead_L', 'eye_bowl_L', 'eye_width_three_quarter', 'eye_width_profile',
               'neck_crease', 'neck_crease_all', 'profile_edge', 'sheet_cheek', 'sheet_neck_to_jaw', 'sheet_width')
CHECKS_GATE = ('face_folds', 'hair_fringe_low', 'body_back_leg', 'poke_share', 'hair_noise')


def design_crop(rgb0, f, H, view, top, bot, half):
    h = H['heads'][view]
    ey = h['eye_y'] / f
    eyes = sorted(h['eyes'])
    cx = np.mean([e[0] for e in eyes]) / f if view != 'profile' else eyes[0][0] / f
    own = refcheck.FACE_PPL / f
    im = Image.fromarray((np.clip(rgb0, 0, 1) * 255).astype(np.uint8))
    box = (cx - half * own, ey - top * own, cx + half * own, ey + bot * own)
    return im.crop(tuple(int(round(v)) for v in box)).resize((int(2 * half * PPL), int((top + bot) * PPL)), Image.LANCZOS)


def board_crop(build, fn, L, eye_u, top, bot, half):
    """a face board cut round the eyes' point: eye_u, the eyes' point's offset right of the picture's centre (L)."""
    im = Image.open(os.path.join(build, 'boards', fn)).convert('RGB')
    ppl = 85 / 36 * im.size[0] * L                     # px per L at the target's distance (1 m)
    cx, ey = im.size[0] / 2 + eye_u * ppl, im.size[1] / 2 + 0.06 * ppl
    box = (cx - half * ppl, ey - top * ppl, cx + half * ppl, ey + bot * ppl)
    return im.crop(tuple(int(round(v)) for v in box)).resize((int(2 * half * PPL), int((top + bot) * PPL)), Image.LANCZOS)


def ticks(im, top):
    """the eye line and every 0.1 L under it, marked at the left edge."""
    d = ImageDraw.Draw(im)
    for k in range(-3, 9):
        y = int((top + 0.1 * k) * PPL)
        if 0 <= y < im.size[1]:
            d.line([(0, y), (10 if k else 18, y)], fill=(220, 0, 0), width=2)
    return im


def main(args):
    out, rest = args[0], args[1:]
    opt = lambda k: rest[rest.index(k) + 1] if k in rest else None
    builds = [a for i, a in enumerate(rest) if not a.startswith('--') and (i == 0 or not rest[i - 1].startswith('--'))]
    labels = (opt('--labels') or ','.join(os.path.basename(b.rstrip('/')) for b in builds)).split(',')
    bare = (opt('--bare') or '').split(',') if opt('--bare') else []
    img = os.path.join(out, 'img')
    os.makedirs(img, exist_ok=True)
    spec = manifest.resolve(json.load(open(os.path.join(ROOT, 'charkit/spec/clawd_body.json'))))
    rgb = refcheck._load(spec['ref']['face_sheet']['image'])
    rgb0, _ = refcheck.without_guides(np.asarray(rgb, float))
    _, f, H = refcheck.at_scale(rgb0, 0.168, 2 * 0.168 * refcheck.FACE_PPL, -1)

    def save(im, name):
        im.save(os.path.join(img, name))
        return 'img/' + name
    B = [bl.load(os.path.join(b, 'bundle')) for b in builds]
    Ls = [float(b.assembly['L']) for b in B]
    # the eyes' point off the picture's centre (the board's camera aims at x 0 on the axis): the three-quarter's eyes
    eye_u = []
    for b in B:
        c = np.asarray(b.assembly['centre'], float); L = float(b.assembly['L'])
        iris = np.array([np.asarray(E['c'], float) for E in b.assembly['eyes']]) if len(b.assembly['eyes'][0].get('c', ())) == 3 \
            else None
        eye_u.append(iris)
    Q = [json.load(open(os.path.join(b, 'qa', 'qa.json'))) for b in builds]
    Q = [q.get('checks', q) for q in Q]
    # the jaw's checks, measured now on each build (the measures' current code), with their pictures
    J, P = [], []
    for b in B:
        T, C = fr.jaw(b)
        J.append(C)
    L_ = ['<!doctype html><meta charset="utf-8"><title>Chin and jaw review</title><style>body{font:14px/1.45 '
          '-apple-system,system-ui,sans-serif;margin:24px;background:#f6f6f4;color:#222}h2{margin-top:34px;font-size:18px}'
          '.row{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-start}.tile{font-size:12px;color:#444;max-width:'
          '440px}.tile img{display:block;border:1px solid #ccc;background:#fff}table{border-collapse:collapse;font-size:'
          '13px;margin-top:8px}td,th{border:1px solid #ccc;padding:3px 8px;text-align:right}th{background:#ecece8}'
          'td:first-child{text-align:left}.PASS{color:#070}.WARN{color:#b60}.FAIL{color:#c00}.INFO{color:#667}'
          '.note{color:#555;font-size:13px;max-width:1100px}</style>',
          '<h1>Chin and jaw: %s</h1>' % ' vs '.join(html.escape(l) for l in labels),
          '<p class="note">The head sheet (charkit/refs/clawd/gen/head_turnaround.png) beside each build\'s face boards '
          '(boards/face_000, face_030, face_090: 85 mm, 1 m, level at the eye line + 0.06 L), cut round the eyes at %d px '
          'per L; red ticks at the eye line and every 0.1 L under it. The three-quarter board is at 30 degrees, the sheet\'s '
          'at 36.5.</p>' % PPL]

    def cell(val):
        if isinstance(val, dict):
            return val.get('value'), val.get('status', '')
        if isinstance(val, (list, tuple)) and len(val) == 2:
            return val[0], val[1]
        return val, ''
    L_.append('<h2>The jaw checks (charkit.faceregion.jaw, measured now on each build)</h2><table><tr><th>check</th>' +
              ''.join('<th>%s</th>' % html.escape(l) for l in labels) + '<th>design</th></tr>')
    for k in CHECKS_JAW:
        row = '<tr><td>%s</td>' % k
        des = ''
        for C in J:
            v = C.get(k) or {}
            row += '<td class="%s">%s %s</td>' % (v.get('status', ''), v.get('value'), v.get('status', ''))
            des = v.get('design', des)
        L_.append(row + '<td>%s</td></tr>' % des)
    L_.append('</table><p class="note">jaw_taper: the face outline\'s rms from the cheek (z -0.1) to the design\'s chin '
              'point (L); chin_point_z: our chin point less the design\'s (L); chin_v: the V\'s rise 0.08 L either side of '
              'the chin, ours over the design\'s; neck_to_face: the neck\'s width 0.1 L under the chin over the face\'s '
              '0.1 L over it, ours over the design\'s; these four in a level camera far out, as the design is drawn. '
              'jaw_line_*: the length of jaw line with neck skin under it, ours over the design\'s, in the boards\' camera '
              'with the outline emulated (does the render ink it). chin_underside: the profile\'s underside angle (deg, + '
              'rising to the throat). neck_front_wiggle: the neck\'s front outline\'s sharpest bend 0.1 L under the throat '
              '(deg).</p>')
    for title, keys in (('The face region\'s other checks (the build\'s QA)', CHECKS_FACE),
                        ('Checks the gate watched (the build\'s QA)', CHECKS_GATE)):
        L_.append('<h2>%s</h2><table><tr><th>check</th>' % title + ''.join('<th>%s</th>' % html.escape(l) for l in labels) +
                  '</tr>')
        for k in keys:
            L_.append('<tr><td>%s</td>' % k + ''.join('<td class="%s">%s %s</td>' % (cell(q.get(k))[1], cell(q.get(k))[0],
                                                                                    cell(q.get(k))[1]) for q in Q) + '</tr>')
        L_.append('</table>')
    for crop, (top, bot, half) in CROPS.items():
        L_.append('<h2>%s</h2><div class="row">' % ('Whole heads' if crop == 'head' else 'Close on the chin and neck'))
        for view, fn in VIEWS:
            L_.append('<div class="tile"><b>%s</b><div class="row">' % view.replace('_', '-'))
            im = ticks(design_crop(rgb0, f, H, view, top, bot, half), top)
            L_.append('<div class="tile"><img src="%s" width="%d">design (head sheet)</div>' % (
                save(im, 'design_%s_%s.png' % (crop, view)), im.size[0] * 0.5 if crop == 'head' else im.size[0] * 0.75))
            for b, lab, L in zip(builds, labels, Ls):
                im = ticks(board_crop(b, fn, L, 0.0, top, bot, half), top)
                L_.append('<div class="tile"><img src="%s" width="%d">%s <a href="%s">%s</a></div>' % (
                    save(im, '%s_%s_%s.png' % (lab, crop, view)), im.size[0] * 0.5 if crop == 'head' else im.size[0] * 0.75,
                    html.escape(lab), html.escape(os.path.abspath(os.path.join(b, 'boards', fn))), fn))
            L_.append('</div></div>')
        L_.append('</div>')
    if bare:
        L_.append('<h2>Bare (hair and its clips hidden: face_views.py)</h2><div class="row">')
        for d, lab in zip(bare, labels):
            for view in ('front', 'three_quarter', 'profile'):
                p = os.path.join(d, 'neck_%s_bare.png' % view)
                if os.path.exists(p):
                    im = Image.open(p).convert('RGB')
                    L_.append('<div class="tile"><img src="%s" width="300">%s %s</div>' % (
                        save(im, 'bare_%s_%s.png' % (lab, view)), html.escape(lab), view))
        L_.append('</div>')
    page = os.path.join(out, 'index.html')
    open(page, 'w').write('\n'.join(L_))
    print(page)


if __name__ == '__main__':
    main(sys.argv[1:])
