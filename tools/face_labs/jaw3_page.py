"""The round-3 chin and jaw review page: the head sheet beside each build's face boards, close on the chin and jaw in
front, three-quarter and profile at one px per L (registered on the eyes at the head's eye line, faceregion.eye_anchor),
each with the corrected measure's traced outlines overlaid:
  - front: the lower outline from the design's widest row its hair leaves in view (taper_front; the design's rows over
    it, where its side locks cover the face's edge, are masked: a dashed line marks where);
  - three-quarter: the far cheek's contour (up to where the design's lock covers it) and the near jaw line (tq_jaw);
  - profile: the lower face's front edge and the chin's underside (jaw_profile);
ours traced in the boards' camera with the hair hidden (the measure's), the design's red, ours blue (the design's front
outline also drawn over ours, thin). Then the taper curves, the jaw's shading (jaw_health, if given), and the checks per
build: the jaw measured now (faceregion.jaw) and each build's QA (qa/qa.json).

    python jaw3_page.py OUT_DIR BUILD [BUILD ...] [--labels a,b] [--health IMG,IMG] [--old QA.json,QA.json]

BUILD: a build folder (boards/, bundle/, qa/qa.json). --health: jaw_health.py pictures, one per build. --old: the
builds' QA before the remeasure (the old measure's numbers, for the before/after columns). Prints the page's path."""
import html, json, os, re, sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from charkit import bundle as bl, faceregion as fr, manifest, qa3d, refcheck  # noqa: E402
import jaw_page  # noqa: E402

PPL = 420
CROP = {'front': (-0.1, 0.46, 0.34), 'three_quarter': (-0.1, 0.46, 0.34), 'profile': (-0.1, 0.5, 0.3)}
BOARDS = (('front', 'face_000.png', 0.0), ('three_quarter', 'face_030.png', 30.0), ('profile', 'face_090.png', 90.0))
CHECKS = ('jaw_taper_shape', 'jaw_taper', 'jaw_line_bend', 'chin_angle', 'chin_tip', 'tq_cheek_hollow', 'tq_jaw_notch',
          'chin_point_z', 'chin_v', 'neck_to_face', 'jaw_line_front', 'jaw_line_three_quarter', 'chin_underside',
          'neck_front_wiggle')
CHECKS_QA = ('face_folds', 'neck_crease', 'neck_crease_all', 'profile_edge', 'body_profile_iou_skin', 'body_profile_iou',
             'sheet_cheek_chin', 'sheet_profile_chin', 'sheet_neck_to_jaw', 'eye_hollow_L', 'eye_bowl_L', 'hair_fringe_low',
             'piece_collar')
COLS = ['#c22', '#888', '#15d', '#e80', '#6a9']


def eye_point(B, view):
    P = fr.eye_anchor(qa3d.iris_centres(B), float(B.assembly['eye_z']))
    return P[np.argmax(P[:, 0])] if view == 'profile' else P.mean(0)


def profile_trace(cls, ppl, win=fr.JAW_WIN):
    """a profile's lower face (facing -u): its front edge per row from under the nose to the neck (the first figure
    pixel), and jaw_profile's underside -> (edge [(u, z)], underside [(u, z)] or None)."""
    H, W = cls.shape
    z = win['top'] - (np.arange(H) + 0.5) / ppl
    u = (np.arange(W) + 0.5) / ppl - win['x']
    fg = cls > 0
    pts = []
    for r in np.nonzero((z < -0.12) & (z > -0.62))[0]:
        c = np.nonzero(fg[r])[0]
        if len(c):
            pts.append((u[c[0]], z[r]))
    M = fr.jaw_profile(cls, ppl)
    return np.array(pts), M.get('underside')


def ours_traces(B, ppl, z0, tq_top):
    """a build's traces in the boards' camera with the hair hidden (the measure's) at each board's azimuth -> {view:
    measures}."""
    meshes, _ = qa3d.scene_classes(B)
    V, T, _, _ = B.skin().mesh('masked')
    L, ez = float(B.assembly['L']), float(B.assembly['eye_z'])
    out = {}
    for view, _, az in BOARDS:
        ref = eye_point(B, view)
        target = np.array([0.0, 0.0, ez + fr.BOARD_CAM['lift'] * L])
        cls = fr.board_view(fr.bare(meshes), (V, T), az, target, ref, L, ppl)[0]
        if view == 'front':
            out[view] = fr.taper_front(cls, ppl, z0)
        elif view == 'three_quarter':
            out[view] = fr.tq_jaw(cls, ppl, top=tq_top)
        else:
            out[view] = profile_trace(cls, ppl)
    return out


def overlay(im, pts, top, half, colour, width=3):
    if pts is None or len(pts) < 2:
        return im
    ImageDraw.Draw(im).line([((u + half) * PPL, (top - z) * PPL) for u, z in pts], fill=colour, width=width)
    return im


def dashed(im, z, top, colour):
    d = ImageDraw.Draw(im)
    y = (top - z) * PPL
    for x in range(0, im.size[0], 14):
        d.line([(x, y), (x + 7, y)], fill=colour, width=2)


def draw(im, view, M, top, half, colour, width=3):
    if not M:
        return
    if view == 'front':
        overlay(im, M.get('outline'), top, half, colour, width)
    elif view == 'three_quarter':
        overlay(im, M.get('far'), top, half, colour, width)
        if M.get('line') is not None:
            overlay(im, [(M['chin'][0] + du, z) for du, z in M['line']], top, half, colour, width)
    else:
        edge, under = M
        overlay(im, edge, top, half, colour, width)
        overlay(im, under, top, half, colour, width)


def charts(D, Ms, labels, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    series = [('design (head sheet, hair masked)', D, COLS[0])] + [(l, m, COLS[1 + i]) for i, (l, m) in enumerate(zip(labels, Ms))]
    for lab, m, c in series:
        f, q = m.get('front'), m.get('three_quarter')
        if f is not None:
            ax[0].plot(f['t'], f['r'], color=c, lw=2, label=lab)
            if f.get('outline') is not None:
                ax[1].plot(f['outline'][:, 0], f['outline'][:, 1], color=c, lw=2, label=lab)
        if q is not None and q.get('line') is not None:
            ax[2].plot(q['line'][:, 0], q['line'][:, 1] - q['chin'][1], color=c, lw=2, label=lab)
    ax[0].set_title('front: w(t) / w(0) (the boards\' camera)'); ax[0].set_xlabel('t (0 the widest row in view, 1 the chin)')
    ax[1].set_title('front: the lower outline (L round the eyes)'); ax[1].set_aspect('equal')
    ax[2].set_title('three-quarter: the near jaw line'); ax[2].set_xlabel('L from the chin across')
    ax[2].set_ylabel('L over the chin point')
    for a in ax:
        a.grid(alpha=.3); a.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(path, dpi=100); plt.close(fig)


def cell(v):
    if isinstance(v, dict):
        return v.get('value'), v.get('status', '')
    if isinstance(v, (list, tuple)) and len(v) >= 2:
        return v[0], v[1]
    return v, ''


def main(args):
    out, rest = args[0], args[1:]
    opt = lambda k: rest[rest.index(k) + 1] if k in rest else None
    flags = {'--labels', '--health', '--old'}
    builds = [a for i, a in enumerate(rest) if a not in flags and (i == 0 or rest[i - 1] not in flags)]
    labels = (opt('--labels') or ','.join(os.path.basename(b.rstrip('/')) for b in builds)).split(',')
    health = opt('--health').split(',') if opt('--health') else []
    olds = opt('--old').split(',') if opt('--old') else []
    img = os.path.join(out, 'img')
    os.makedirs(img, exist_ok=True)
    spec = manifest.resolve(json.load(open(os.path.join(ROOT, 'charkit/spec/clawd.json'))))
    rgb0, _ = refcheck.without_guides(np.asarray(refcheck._load(spec['ref']['face_sheet']['image']), float))
    _, f, H = refcheck.at_scale(rgb0, 0.168, 2 * 0.168 * refcheck.FACE_PPL, -1)
    D, ppl, Dc, az = fr.design_jaw(spec, 0.168)
    Dt = {vn: D[vn].get('taper') for vn in ('front', 'three_quarter')}
    Dp = profile_trace(Dc['profile'], ppl)
    z0, top_f, top_q = Dt['front']['z0'], Dt['front'].get('top'), Dt['three_quarter'].get('top')
    B = [bl.load(os.path.join(b, 'bundle')) for b in builds]
    Q = []
    for b in builds:
        q = json.load(open(os.path.join(b, 'qa', 'qa.json')))
        Q.append(q.get('checks', q))
    O = [json.load(open(p)) for p in olds] if olds else []
    O = [o.get('checks', o) for o in O]
    J = [fr.jaw(b)[1] for b in B]
    Mc = [ours_traces(b, PPL, z0, top_q) for b in B]
    # (the curves at the checks' own azimuths: the three-quarter at the sheet's 36.5)
    Mk = []
    for b in B:
        meshes, _ = qa3d.scene_classes(b)
        V, T_, _, _ = b.skin().mesh('masked')
        Oj = fr.ours_jaw(meshes, (V, T_), qa3d.iris_centres(b), float(b.assembly['eye_z']), float(b.assembly['L']), ppl,
                         az, D['front'].get('chin', (0, None))[1], z0, design_tq_top=top_q)[0]
        Mk.append({vn: Oj[vn].get('taper') for vn in ('front', 'three_quarter')})
    slug = lambda s_: re.sub(r'[^A-Za-z0-9_.-]+', '_', s_).strip('_')
    save = lambda im, name: (im.save(os.path.join(img, slug(name))), 'img/' + slug(name))[1]
    charts(Dt, Mk, labels, os.path.join(img, 'curves.png'))
    css = ('body{font:14px/1.45 -apple-system,system-ui,sans-serif;margin:24px;background:#f6f6f4;color:#222}'
           'h2{margin-top:30px;font-size:18px}.row{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-start}'
           '.tile{font-size:12px;color:#444}.tile img{display:block;border:1px solid #ccc;background:#fff}'
           'table{border-collapse:collapse;font-size:13px;margin-top:8px}td,th{border:1px solid #ccc;padding:3px 8px;'
           'text-align:right}th{background:#ecece8}td:first-child{text-align:left}.PASS{color:#070}.WARN{color:#b60}'
           '.FAIL{color:#c00}.INFO{color:#667}.note{color:#555;font-size:13px;max-width:1150px}')
    P = ['<!doctype html><meta charset="utf-8"><title>Chin and jaw, round 3</title><style>%s</style>' % css,
         '<h1>The chin and jaw, round 3: design | %s</h1>' % ' | '.join(html.escape(l) for l in labels),
         '<p class="note">Close on the chin at %d px per L, red ticks at the eye line and every 0.1 L under it. The head '
         'sheet on its eye row; the builds\' face boards (85 mm, 1 m, level at the eye line + 0.06 L) cut round the eyes at '
         'the head\'s eye line. Red: the design\'s traced outline (the corrected measure: its rows over the dashed line, '
         'z %.3f in front and %.3f on the three-quarter\'s far cheek, are where its side locks cover the face\'s edge, left '
         'out of the comparison); blue: each build\'s own, traced in the boards\' camera with the hair hidden, as the '
         'checks read it; the design\'s front outline thin over ours. The three-quarter boards are at 30 degrees, the '
         'sheet\'s at 36.5: each picture carries its own trace.</p>' % (PPL, top_f or 0, top_q or 0)]
    # the close-ups
    for view, fn, az_b in BOARDS:
        top, bot, half = CROP[view]
        P.append('<h2>%s</h2><div class="row">' % view.replace('_', '-'))
        im = jaw_page.ticks(jaw_page.design_crop(rgb0, f, H, view, top, bot, half), top).convert('RGB')
        if view == 'profile':
            draw(im, view, Dp, top, half, (220, 30, 30))
        else:
            draw(im, view, Dt[view], top, half, (220, 30, 30))
            mz = top_f if view == 'front' else top_q
            if mz is not None:
                dashed(im, mz, top, (220, 30, 30))
        P.append('<div class="tile"><img src="%s" width="%d">design (head sheet)</div>' % (
            save(im, 'design_%s.png' % view), im.size[0]))
        for b, bb, lab, M in zip(builds, B, labels, Mc):
            L = float(bb.assembly['L'])
            if not os.path.exists(os.path.join(b, 'boards', fn)):
                continue
            im = jaw_page.ticks(jaw_page.board_crop(b, fn, L, az_b, eye_point(bb, view), top, bot, half,
                                                    float(bb.assembly['eye_z'])), top).convert('RGB')
            draw(im, view, M.get(view), top, half, (30, 90, 220))
            if view == 'front':
                draw(im, view, Dt['front'], top, half, (220, 30, 30), 1)
                if top_f is not None:
                    dashed(im, top_f, top, (220, 30, 30))
            P.append('<div class="tile"><img src="%s" width="%d">%s <a href="%s">%s</a></div>' % (
                save(im, '%s_%s.png' % (lab, view)), im.size[0], html.escape(lab),
                html.escape(os.path.abspath(os.path.join(b, 'boards', fn))), fn))
        P.append('</div>')
    P.append('<h2>The curves (the checks\' own: the three-quarter at the sheet\'s 36.5 degrees)</h2>'
             '<img src="img/curves.png" width="1400">')
    if health:
        P.append('<h2>The jaw\'s shading (jaw_health.py: the fitted cage subdivided once; front, three-quarter, 60 '
                 'degrees; below, from under)</h2><div class="row">')
        for h, lab in zip(health, labels):
            if os.path.exists(h):
                P.append('<div class="tile"><img src="%s" width="690">%s <a href="%s">png</a></div>' % (
                    save(Image.open(h).convert('RGB'), 'health_%s.png' % lab), html.escape(lab), html.escape(os.path.abspath(h))))
        P.append('</div>')
    # the numbers
    P.append('<h2>The jaw\'s checks (measured now: the corrected measure)</h2><table><tr><th>check</th>'
             + ''.join('<th>%s</th>' % html.escape(l) for l in labels)
             + (''.join('<th>%s, old measure</th>' % html.escape(l) for l in labels[:len(O)]) if O else '') + '</tr>')
    for k in CHECKS:
        row = '<tr><td>%s</td>' % k
        for C in J:
            v, s = cell(C.get(k))
            lv = (C.get(k) or {}).get('level') if isinstance(C.get(k), dict) else None
            row += '<td class="%s">%s %s%s</td>' % (s, v, s, '' if lv is None else ' <span class="INFO">(level %s)</span>' % lv)
        for o in O:
            v, s = cell(o.get(k))
            row += '<td class="%s">%s %s</td>' % (s, v, s)
        P.append(row + '</tr>')
    P.append('</table><h2>The face region, the sheet and the body (each build\'s QA)</h2><table><tr><th>check</th>'
             + ''.join('<th>%s</th>' % html.escape(l) for l in labels) + '</tr>')
    for k in CHECKS_QA:
        P.append('<tr><td>%s</td>%s</tr>' % (k, ''.join('<td class="%s">%s %s</td>' % (cell(q.get(k))[1], cell(q.get(k))[0],
                                                                                        cell(q.get(k))[1]) for q in Q)))
    P.append('</table>')
    page = os.path.join(out, 'index.html')
    open(page, 'w').write('\n'.join(P))
    print(page)


if __name__ == '__main__':
    main(sys.argv[1:])
