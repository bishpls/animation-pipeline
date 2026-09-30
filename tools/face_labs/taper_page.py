"""The chin's taper review page: the head sheet's front and three-quarter beside each build's face boards, close on the
chin at one px per L (registered on the eyes at the head's eye line, faceregion.eye_anchor), each with its own traced
outline overlaid (the taper checks' trace: charkit.faceregion.taper_front, tq_jaw, in the boards' camera); the taper
curves (w(t)/w(0), the lower outline, the three-quarter's near jaw line) in charts; the taper checks, the jaw's other
checks and the face region's, per build, with the design's.

    python taper_page.py OUT_DIR BUILD [BUILD ...] [--labels a,b] [--bare DIR,DIR]

BUILD: a build folder (boards/, bundle/, qa/qa.json). --bare: face_views.py render folders (hair hidden), one per build.
Opens nothing; prints the page's path."""
import html, json, math, os, sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from charkit import bundle as bl, faceregion as fr, manifest, qa3d, refcheck  # noqa: E402
import jaw_page  # noqa: E402

PPL = 420
CHIN = (-0.1, 0.46, 0.34)                     # the close crop: L over the eye line, under it, either side
BOARDS = (('front', 'face_000.png', 0.0), ('three_quarter', 'face_030.png', 30.0))
CHECKS_TAPER = ('jaw_taper_shape', 'jaw_line_bend', 'chin_angle', 'chin_tip', 'tq_cheek_hollow', 'tq_jaw_notch')
CHECKS_JAW = ('jaw_taper', 'chin_point_z', 'chin_v', 'neck_to_face', 'jaw_line_front', 'jaw_line_three_quarter',
              'chin_underside', 'neck_front_wiggle')
CHECKS_FACE = ('face_folds', 'eye_hollow_L', 'cheek_lead_L', 'eye_bowl_L', 'eye_width_three_quarter', 'eye_width_profile',
               'neck_crease', 'profile_edge', 'sheet_cheek', 'sheet_cheek_chin', 'sheet_profile', 'sheet_profile_chin',
               'sheet_width', 'sheet_neck_to_jaw', 'hair_fringe_low', 'poke_share')
COLS = ['#c22', '#888', '#15d', '#e80', '#6a9']


def eye_point(B, view):
    """the eyes' point at the head's eye line (the QA's registration, faceregion.eye_anchor)."""
    P = fr.eye_anchor(qa3d.iris_centres(B), float(B.assembly['eye_z']))
    return P[np.argmax(P[:, 0])] if view == 'profile' else P.mean(0)


def overlay(im, pts, top, half, colour, width=3):
    """(u, z) L round the eyes' point drawn on a crop cut CHIN round it at PPL."""
    if pts is None or len(pts) < 2:
        return im
    d = ImageDraw.Draw(im)
    d.line([((u + half) * PPL, (top - z) * PPL) for u, z in pts], fill=colour, width=width)
    return im


def ours_board(B, az, ppl, z0):
    """a build's boards' camera emulated at azimuth az (faceregion.board_view, the outline drawn as the look draws
    it) -> the class image, its taper_front (front) or tq_jaw (three-quarter)."""
    meshes, _ = qa3d.scene_classes(B)
    V, T, _, _ = B.skin().mesh('masked')
    L, ez = float(B.assembly['L']), float(B.assembly['eye_z'])
    ref = eye_point(B, 'front')
    cls = fr.board_view(meshes, (V, T), az, np.array([0.0, 0.0, ez + fr.BOARD_CAM['lift'] * L]), ref, L, ppl)[0]
    return cls, (fr.taper_front(cls, ppl, z0) if az == 0 else fr.tq_jaw(cls, ppl))


def charts(D, M, labels, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    series = [('design (head sheet)', D, COLS[0])] + [(l, m, COLS[1 + i]) for i, (l, m) in enumerate(zip(labels, M))]
    for lab, m, c in series:
        f, q = m.get('front'), m.get('three_quarter')
        if f is not None:
            ax[0].plot(f['t'], f['r'], color=c, lw=2, label=lab)
            if f.get('outline') is not None:
                ax[1].plot(f['outline'][:, 0], f['outline'][:, 1], color=c, lw=2, label=lab)
        if q is not None and q.get('line') is not None:
            ax[2].plot(q['line'][:, 0], q['line'][:, 1] - q['chin'][1], color=c, lw=2, label=lab)
    ax[0].set_title('front: the taper w(t) / w(0)'); ax[0].set_xlabel('t (0 the cheekbone row, 1 the chin point)')
    ax[1].set_title('front: the lower outline (L round the eyes)'); ax[1].set_aspect('equal'); ax[1].set_ylim(-0.38, -0.1)
    ax[2].set_title('three-quarter (36.5): the near jaw line'); ax[2].set_xlabel('L from the chin across')
    ax[2].set_ylabel('L over the chin point')
    for a in ax:
        a.grid(alpha=.3); a.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(path, dpi=100); plt.close(fig)


def main(args):
    out, rest = args[0], args[1:]
    opt = lambda k: rest[rest.index(k) + 1] if k in rest else None
    builds = [a for i, a in enumerate(rest) if not a.startswith('--') and (i == 0 or not rest[i - 1].startswith('--'))]
    labels = (opt('--labels') or ','.join(os.path.basename(b.rstrip('/')) for b in builds)).split(',')
    bare = (opt('--bare') or '').split(',') if opt('--bare') else []
    img = os.path.join(out, 'img')
    os.makedirs(img, exist_ok=True)
    spec = manifest.resolve(json.load(open(os.path.join(ROOT, 'charkit/spec/clawd.json'))))
    rgb0, _ = refcheck.without_guides(np.asarray(refcheck._load(spec['ref']['face_sheet']['image']), float))
    _, f, H = refcheck.at_scale(rgb0, 0.168, 2 * 0.168 * refcheck.FACE_PPL, -1)
    D, ppl, Dc, az = fr.design_jaw(spec, 0.168)
    Dt = {vn: D[vn].get('taper') for vn in ('front', 'three_quarter')}
    z0 = Dt['front']['z0']
    B = [bl.load(os.path.join(b, 'bundle')) for b in builds]
    Q = [json.load(open(os.path.join(b, 'qa', 'qa.json'))) for b in builds]
    Q = [q.get('checks', q) for q in Q]
    J = [fr.jaw(b)[1] for b in B]
    # the traced curves (arrays: jaw's table drops them) from the emulated boards' camera, at the check's azimuths
    Mc = []
    for b in B:
        meshes, _ = qa3d.scene_classes(b)
        V, T_, _, _ = b.skin().mesh('masked')
        O = fr.ours_jaw(meshes, (V, T_), qa3d.iris_centres(b), float(b.assembly['eye_z']), float(b.assembly['L']), ppl,
                        az, D['front'].get('chin', (0, None))[1], z0)[0]
        Mc.append({vn: O[vn].get('taper') for vn in ('front', 'three_quarter')})
    save = lambda im, name: (im.save(os.path.join(img, name)), 'img/' + name)[1]
    charts(Dt, Mc, labels, os.path.join(img, 'curves.png'))
    css = ('body{font:14px/1.45 -apple-system,system-ui,sans-serif;margin:24px;background:#f6f6f4;color:#222}'
           'h2{margin-top:30px;font-size:18px}.row{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-start}'
           '.tile{font-size:12px;color:#444}.tile img{display:block;border:1px solid #ccc;background:#fff}'
           'table{border-collapse:collapse;font-size:13px;margin-top:8px}td,th{border:1px solid #ccc;padding:3px 8px;'
           'text-align:right}th{background:#ecece8}td:first-child{text-align:left}.PASS{color:#070}.WARN{color:#b60}'
           '.FAIL{color:#c00}.INFO{color:#667}.note{color:#555;font-size:13px;max-width:1150px}')
    P = ['<!doctype html><meta charset="utf-8"><title>Chin taper review</title><style>%s</style>' % css,
         '<h1>The chin\'s taper: %s against the head sheet</h1>' % ' / '.join(html.escape(l) for l in labels),
         '<p class="note">Close on the chin at %d px per L, the eye line at the top tick, then every 0.1 L. The head sheet '
         'on its eye row; the builds\' face boards (85 mm, 1 m, level at the eye line + 0.06 L) cut round the eyes at the '
         'head\'s eye line. Red: the design\'s traced outline; blue: each build\'s own, traced by the checks in the boards\''
         ' camera (the front at 0 degrees; the three-quarter board is at 30 degrees, the sheet\'s at 36.5, so the '
         'three-quarter overlays are each picture\'s own trace at its own angle).</p>' % PPL]
    # the taper checks
    P.append('<h2>The taper checks (faceregion.taper_front, tq_jaw: the boards\' camera; level camera in brackets)</h2>'
             '<table><tr><th>check</th>' + ''.join('<th>%s</th>' % html.escape(l) for l in labels) + '<th>design</th>'
             '<th>limits</th></tr>')
    lim = {'jaw_taper_shape': 'rms <= %.3f / %.3f' % fr.TAPER_SHAPE, 'jaw_line_bend': 'deg <= %g / %g' % fr.ARM_BEND,
           'chin_angle': '|d| <= %g / %g deg' % fr.CHIN_ANGLE, 'chin_tip': '>= %g / %g' % fr.TIP_SHARE,
           'tq_cheek_hollow': 'L <= %g / %g' % fr.TQ_HOLLOW, 'tq_jaw_notch': 'L <= %g / %g' % fr.TQ_NOTCH}
    dval = {'jaw_taper_shape': 0.0, 'jaw_line_bend': None, 'chin_angle': None, 'chin_tip': None, 'tq_cheek_hollow': None,
            'tq_jaw_notch': None}
    for k in CHECKS_TAPER:
        row = '<tr><td>%s</td>' % k
        des = dval.get(k)
        for C in J:
            v = C.get(k) or {}
            extra = v.get('level')
            if k == 'jaw_line_bend':
                extra = 'board %s, level %s' % (v.get('board'), v.get('level'))
            row += '<td class="%s">%s %s <span class="INFO">(%s)</span></td>' % (v.get('status', ''), v.get('value'),
                                                                                 v.get('status', ''), extra)
            des = v.get('design', des)
        P.append(row + '<td>%s</td><td>%s</td></tr>' % (des, lim[k]))
    P.append('</table><p class="note">jaw_taper_shape: rms of the front outline\'s half-width w(t)/w(0), t from the '
             'design\'s cheekbone row (z %.3f) to each chin; jaw_line_bend: the jaw lines\' sharpest local bend (graded '
             'on the worse camera); chin_angle: the V\'s opening between its arms 0.06-0.12 L of arc from its point; '
             'chin_tip: the share of the V\'s turn made within 0.02 L of its point (a V near 1, a round U low); '
             'tq_cheek_hollow: the three-quarter\'s far cheek contour inside its local chord; tq_jaw_notch: the near '
             'jaw line\'s largest drop under its own rise.</p>' % z0)
    for title, keys, src in (('The jaw\'s other checks (measured now, the eye-line anchor)', CHECKS_JAW, 'J'),
                             ('The face region and the sheet (each build\'s QA)', CHECKS_FACE, 'Q')):
        P.append('<h2>%s</h2><table><tr><th>check</th>' % title + ''.join('<th>%s</th>' % html.escape(l) for l in labels) +
                 '</tr>')
        for k in keys:
            cells = []
            for i in range(len(builds)):
                v = (J[i] if src == 'J' else Q[i]).get(k) or {}
                if isinstance(v, (list, tuple)):
                    v = dict(value=v[0], status=v[1] if len(v) > 1 else '')
                cells.append('<td class="%s">%s %s</td>' % (v.get('status', ''), v.get('value'), v.get('status', '')))
            P.append('<tr><td>%s</td>%s</tr>' % (k, ''.join(cells)))
        P.append('</table>')
    P.append('<p class="note">The QA\'s own numbers for the sheet checks come from each build\'s qa.json: a build before '
             'the anchor (e9a6753) read its heights under the eyes 0.024 L low.</p>')
    # the close-ups
    top, bot, half = CHIN
    P.append('<h2>Close on the chin</h2>')
    for view, fn, az_b in BOARDS:
        P.append('<h3>%s</h3><div class="row">' % view.replace('_', '-'))
        im = jaw_page.ticks(jaw_page.design_crop(rgb0, f, H, view, top, bot, half), top).convert('RGB')
        dm = Dt[view]
        overlay(im, dm.get('outline') if view == 'front' else (dm.get('far')), top, half, (220, 30, 30))
        if view == 'three_quarter' and dm.get('line') is not None:
            overlay(im, [(dm['chin'][0] + du, z) for du, z in dm['line']], top, half, (220, 30, 30))
        P.append('<div class="tile"><img src="%s" width="%d">design (head sheet)</div>' % (
            save(im, 'design_%s.png' % view), im.size[0]))
        for b, bb, lab in zip(builds, B, labels):
            L = float(bb.assembly['L'])
            im = jaw_page.ticks(jaw_page.board_crop(b, fn, L, az_b, eye_point(bb, view), top, bot, half,
                                                    float(bb.assembly['eye_z'])), top).convert('RGB')
            _, M = ours_board(bb, az_b, PPL, z0)
            if M:
                overlay(im, M.get('outline') if view == 'front' else M.get('far'), top, half, (30, 90, 220))
                if view == 'front':
                    overlay(im, dm.get('outline'), top, half, (220, 30, 30), 2)
                if view == 'three_quarter' and M.get('line') is not None:
                    overlay(im, [(M['chin'][0] + du, z) for du, z in M['line']], top, half, (30, 90, 220))
            P.append('<div class="tile"><img src="%s" width="%d">%s <a href="%s">%s</a></div>' % (
                save(im, '%s_%s.png' % (lab, view)), im.size[0], html.escape(lab),
                html.escape(os.path.abspath(os.path.join(b, 'boards', fn))), fn))
        P.append('</div>')
    P.append('<h2>The curves</h2><img src="img/curves.png" width="1400"><p class="note">The front\'s in the boards\' '
             'camera; the three-quarter\'s at the head sheet\'s 36.5 degrees (the check\'s), both traced by the checks.</p>')
    if bare:
        P.append('<h2>Bare (hair hidden: face_views.py)</h2><div class="row">')
        for d, lab in zip(bare, labels):
            for view in ('front', 'three_quarter'):
                p = os.path.join(d, 'face_%s_bare.png' % view)
                if os.path.exists(p):
                    im = Image.open(p).convert('RGB')
                    P.append('<div class="tile"><img src="%s" width="360">%s %s <a href="%s">png</a></div>' % (
                        save(im, 'bare_%s_%s.png' % (lab, view)), html.escape(lab), view, html.escape(os.path.abspath(p))))
        P.append('</div>')
    page = os.path.join(out, 'index.html')
    open(page, 'w').write('\n'.join(P))
    print(page)


if __name__ == '__main__':
    main(sys.argv[1:])
