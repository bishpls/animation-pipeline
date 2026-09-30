"""Face round 4's review page: the chin, the jaw and the crown in the design's projection. The head sheet beside each
build rendered orthographic and level with the head's eye line (face_level.py: the boards' look, the hair shown and
hidden), close on the chin in front, three-quarter and profile at one px per L, registered on the eyes at the head's eye
line (faceregion.eye_anchor), each with its traced outline in the level camera (the design's red, ours blue: the
jaw checks' own traces, ours with the hair hidden). Then the lower outline and the taper curves, and the numbers per
build: the jaw's checks as graded (the boards' camera) with the level camera's beside, the crown (skin faces facing
in over the head's top), hair_penetration and the face's folds from each build's QA.

    python face4_page.py OUT_DIR BUILD [BUILD ...] [--labels a,b] [--level DIR,DIR] [--also LABEL=BUILD,...] [--head SNIPPET.html]

BUILD: a build folder (bundle/, qa/qa.json, boards/). --level: each build's face_level.py output (default BUILD/level).
--also: more builds whose art_terminator_hair goes in the hair's table (e.g. the crown alone). Prints the page's path."""
import html, json, math, os, re, sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from charkit import bundle as bl, faceregion as fr, manifest, qa3d, refcheck  # noqa: E402
import jaw3_page, jaw_page  # noqa: E402

PPL = jaw3_page.PPL
CROP = jaw3_page.CROP
VIEWS = (('front', 0.0), ('three_quarter', None), ('profile', 90.0))
SHOW = ('chin_angle', 'chin_tip', 'jaw_line_bend', 'jaw_taper_shape', 'tq_jaw_notch', 'tq_cheek_hollow', 'jaw_taper',
        'chin_point_z', 'chin_v', 'chin_underside', 'neck_front_wiggle', 'jaw_line_front', 'jaw_line_three_quarter')
QA = ('hair_penetration', 'art_terminator_hair', 'hair_noise', 'face_folds', 'neck_crease', 'profile_edge', 'sheet_width',
      'body_profile_iou_skin')
LOCK_BOXES = (('her left', (540, 260, 880, 760)), ('her right', (20, 260, 360, 760)))   # face_000's side locks
BOARDS = (('face_000', 'front'), ('face_030', '30 degrees'), ('face_090', 'profile'))
CHIN_BOX = (290, 540, 610, 770)                    # the boards' face pictures (900 px): the chin and jaw, 1.5x


def level_crop(level_dir, view, B, top, bot, half, tag='hair'):
    """a face_level.py picture cut round the build's eyes' point (anchored on the head's eye line), at PPL."""
    meta = json.load(open(os.path.join(level_dir, 'level.json')))
    im = Image.open(os.path.join(level_dir, 'level_%s_%s.png' % (view, tag))).convert('RGB')
    az = math.radians(meta['views'][view])
    k = meta['ppl'] / meta['L']                                        # px per metre
    eye = jaw3_page.eye_point(B, view)
    r = np.array([math.cos(az), math.sin(az), 0.0])
    cx = meta['size'] / 2 + float(eye @ r) * k
    ey = meta['size'] / 2 - (float(eye[2]) - meta['eye_z']) * k
    own = meta['ppl']
    box = (cx - half * own, ey - top * own, cx + half * own, ey + bot * own)
    return im.crop(tuple(int(round(v)) for v in box)).resize((int(2 * half * PPL), int((top + bot) * PPL)), Image.LANCZOS)


def level_traces(B, ppl, az3, z0, tq_top):
    """a build's traces in the level camera (the design's projection) with the hair hidden -> {view: measures}."""
    meshes, _ = qa3d.scene_classes(B)
    V, T, _, _ = B.skin().mesh('masked')
    L, ez = float(B.assembly['L']), float(B.assembly['eye_z'])
    out = {}
    for view, az in VIEWS:
        az = az3 if az is None else az
        ref = jaw3_page.eye_point(B, view)
        cls = fr.board_view(fr.bare(meshes), (V, T), az, np.array([0.0, 0.0, ez]), ref, L, ppl,
                            dist=fr.LEVEL_CAM['dist'])[0]
        out[view] = (fr.taper_front(cls, ppl, z0) if view == 'front' else
                     fr.tq_jaw(cls, ppl, top=tq_top) if view == 'three_quarter' else jaw3_page.profile_trace(cls, ppl))
    return out


def crown_turned_in(B):
    """the evaluated skin's faces over the head's top (0.2 L over its centre) whose normal points toward the centre."""
    V, T, _, _ = B.skin().mesh('eval')
    c = np.asarray(B.assembly['centre'], float)
    L = float(B.assembly['L'])
    P = V[T]
    m = P.mean(1)
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    top = m[:, 2] > c[2] + 0.2 * L
    return int(((np.einsum('ij,ij->i', n, m - c) < 0) & top).sum()), int(top.sum())


def cell(v):
    if isinstance(v, dict):
        return v.get('value'), v.get('status', '')
    return v, ''


def main(args):
    out, rest = args[0], args[1:]
    opt = lambda k: rest[rest.index(k) + 1] if k in rest else None
    flags = {'--labels', '--level', '--also', '--head'}
    also = [a.split('=', 1) for a in opt('--also').split(',')] if opt('--also') else []
    builds = [a for i, a in enumerate(rest) if a not in flags and (i == 0 or rest[i - 1] not in flags)]
    labels = (opt('--labels') or ','.join(os.path.basename(b.rstrip('/')) for b in builds)).split(',')
    levels = opt('--level').split(',') if opt('--level') else [os.path.join(b, 'level') for b in builds]
    img = os.path.join(out, 'img')
    os.makedirs(img, exist_ok=True)
    spec = manifest.resolve(json.load(open(os.path.join(ROOT, 'charkit/spec/clawd.json'))))
    rgb0, _ = refcheck.without_guides(np.asarray(refcheck._load(spec['ref']['face_sheet']['image']), float))
    _, f, H = refcheck.at_scale(rgb0, 0.168, 2 * 0.168 * refcheck.FACE_PPL, -1)
    D, ppl, Dc, az = fr.design_jaw(spec, 0.168)
    Dt = {vn: D[vn].get('taper') for vn in ('front', 'three_quarter')}
    Dp = jaw3_page.profile_trace(Dc['profile'], ppl)
    z0, top_f, top_q = Dt['front']['z0'], Dt['front'].get('top'), Dt['three_quarter'].get('top')
    Bs = [bl.load(os.path.join(b, 'bundle')) for b in builds]
    Q = []
    for b in builds:
        q = json.load(open(os.path.join(b, 'qa', 'qa.json')))
        Q.append(q.get('checks', q))
    az3 = az['three_quarter']
    Mt = [level_traces(B, PPL, az3, z0, top_q) for B in Bs]
    C = []
    for B in Bs:                                       # the jaw's checks as the QA grades them, the level's beside
        meshes, _ = qa3d.scene_classes(B)
        V, T_, _, _ = B.skin().mesh('masked')
        O = fr.ours_jaw(meshes, (V, T_), qa3d.iris_centres(B), float(B.assembly['eye_z']), float(B.assembly['L']), ppl,
                        az, D['front'].get('chin', (0, None))[1], z0, design_tq_top=top_q)[0]
        c = fr.jaw_compare(D, O, ppl)
        c.update(fr.taper_checks(D, O))
        C.append(c)
    Cd = fr.taper_compare(Dt, Dt, Dt)
    crowns = [crown_turned_in(B) for B in Bs]
    slug = lambda s_: re.sub(r'[^A-Za-z0-9_.-]+', '_', s_).strip('_')
    save = lambda im, name: (im.save(os.path.join(img, slug(name))), 'img/' + slug(name))[1]
    jaw3_page.charts(Dt, [{vn: M[vn] for vn in ('front', 'three_quarter')} for M in Mt], labels,
                     os.path.join(img, 'curves.png'))
    css = ('body{font:14px/1.45 -apple-system,system-ui,sans-serif;margin:24px;background:#f6f6f4;color:#222}'
           'h2{margin-top:30px;font-size:18px}.row{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-start}'
           '.tile{font-size:12px;color:#444}.tile img{display:block;border:1px solid #ccc;background:#fff}'
           'table{border-collapse:collapse;font-size:13px;margin-top:8px}td,th{border:1px solid #ccc;padding:3px 8px;'
           'text-align:right}th{background:#ecece8}td:first-child{text-align:left}.PASS{color:#070}.WARN{color:#b60}'
           '.FAIL{color:#c00}.INFO{color:#667}.note{color:#555;font-size:13px;max-width:1150px}')
    P = ['<!doctype html><meta charset="utf-8"><title>Chin and crown, round 4</title><style>%s</style>' % css,
         '<h1>The chin and the crown, round 4: design | %s</h1>' % ' | '.join(html.escape(l) for l in labels),
         '<p class="note">In the design\'s projection: each build rendered orthographic and level with the head\'s eye '
         'line in the boards\' look (tools/face_labs/face_level.py), close on the chin at %d px per L, red ticks at the '
         'eye line and every 0.1 L under it, cut round the eyes at the head\'s eye line; the head sheet on its eye row. '
         'Red: the design\'s traced outline (its rows over the dashed line are where its side locks cover the face\'s '
         'edge); blue: each build\'s own, traced in the level camera with the hair hidden. The checks grade the boards\' '
         'camera (85 mm, 1 m, 6 degrees over the chin); the level camera\'s value is beside each.</p>' % PPL]
    if opt('--head'):                                  # (the round's summary and open decisions, an HTML snippet)
        P.insert(2, open(opt('--head')).read())
    for view, _ in VIEWS:
        top, bot, half = CROP[view]
        for tag in ('hair', 'bare'):
            P.append('<h2>%s, %s</h2><div class="row">' % (view.replace('_', '-'), 'hair shown' if tag == 'hair'
                                                            else 'hair hidden'))
            im = jaw_page.ticks(jaw_page.design_crop(rgb0, f, H, view, top, bot, half), top).convert('RGB')
            jaw3_page.draw(im, view, Dp if view == 'profile' else Dt[view], top, half, (220, 30, 30))
            mz = top_f if view == 'front' else top_q if view == 'three_quarter' else None
            if mz is not None:
                jaw3_page.dashed(im, mz, top, (220, 30, 30))
            P.append('<div class="tile"><img src="%s" width="%d">design (head sheet)</div>' % (
                save(im, 'design_%s_%s.png' % (view, tag)), im.size[0]))
            for B, lv, lab, M in zip(Bs, levels, labels, Mt):
                if not os.path.exists(os.path.join(lv, 'level.json')):
                    continue
                im = jaw_page.ticks(level_crop(lv, view, B, top, bot, half, tag), top).convert('RGB')
                jaw3_page.draw(im, view, M.get(view), top, half, (30, 90, 220))
                if view == 'front':
                    jaw3_page.draw(im, view, Dt['front'], top, half, (220, 30, 30), 1)
                P.append('<div class="tile"><img src="%s" width="%d">%s <a href="%s">level_%s_%s.png</a></div>' % (
                    save(im, '%s_%s_%s.png' % (lab, view, tag)), im.size[0], html.escape(lab),
                    html.escape(os.path.abspath(os.path.join(lv, 'level_%s_%s.png' % (view, tag)))), view, tag))
            P.append('</div>')
    P.append('<h2>The boards\' camera (the one the jaw checks grade: 85 mm, 1 m, 6 degrees over the chin)</h2>'
             '<p class="note">Each build\'s own boards (EEVEE, the render box), whole at half size and the chin at 1.5x. The hair '
             'is in these: the side locks\' shading is the terminator section\'s.</p>')
    for board, name in BOARDS:
        P.append('<div class="row">')
        for b, lab in zip(builds, labels):
            fp = os.path.join(b, 'boards', board + '.png')
            if not os.path.exists(fp):
                continue
            im = Image.open(fp).convert('RGB')
            P.append('<div class="tile"><img src="%s" width="450">%s, %s <a href="%s">%s.png</a></div>' % (
                save(im, '%s_%s.png' % (lab, board)), html.escape(lab), name, html.escape(os.path.abspath(fp)), board))
            if board == 'face_000':
                P.append('<div class="tile"><img src="%s" width="480">%s, the chin 1.5x</div>' % (
                    save(im.crop(CHIN_BOX), '%s_%s_chin.png' % (lab, board)), html.escape(lab)))
        P.append('</div>')
    P.append('<h2>The hair\'s shading: art_terminator_hair (the torn hair shadow patches, look_v5)</h2>'
             '<p class="note">Kinks per L of the hair\'s cel terminators per view (the check: the worst view\'s ratio to '
             'the design\'s; PASS 2.0, WARN 2.5, capped at WARN). The crown\'s skin moves the side locks by at most 0.3 mm; '
             'with the hair\'s normals transferred from a proxy by position, 400 of a side lock\'s vertices took a '
             'coincident or near neighbour\'s normal (up to 12.7 degrees off), and which ones re-seeded with the move: '
             'front 8.90 -> 9.55. With each piece\'s own normals (geom.blender.set_normals) the crown\'s real effect is '
             'front 8.92 -> 9.11.</p><table><tr><th>build</th><th>value</th><th>grade</th><th>front</th>'
             '<th>three-quarter</th><th>profile</th><th>back</th></tr>')
    for lab, b in list(zip(labels, builds)) + also:
        q = json.load(open(os.path.join(b, 'qa', 'qa.json')))['checks'].get('art_terminator_hair') or {}
        pv = q.get('per_view') or {}
        P.append('<tr><td>%s</td><td>%s</td><td class="%s">%s</td>%s</tr>' % (
            html.escape(lab), q.get('value'), q.get('grade', ''), q.get('grade', ''),
            ''.join('<td>%s</td>' % pv.get(v) for v in ('front', 'three_quarter', 'profile', 'back'))))
    P.append('</table>')
    for side, box in LOCK_BOXES:
        P.append('<div class="row">')
        for b, lab in zip(builds, labels):
            fp = os.path.join(b, 'boards', 'face_000.png')
            if os.path.exists(fp):
                im = Image.open(fp).convert('RGB').crop(box)
                P.append('<div class="tile"><img src="%s" width="%d">%s, %s side lock (the boards\' front, 1:1)</div>' % (
                    save(im, '%s_lock_%s.png' % (lab, side)), im.size[0], html.escape(lab), side))
        P.append('</div>')
    P.append('<div class="row">')
    for b, lab in zip(builds, labels):
        fp = os.path.join(b, 'qa', 'qa_artifacts.png')
        if os.path.exists(fp):
            im = Image.open(fp).convert('RGB')
            P.append('<div class="tile"><img src="%s" width="900">%s: the QA\'s artifact marks <a href="%s">'
                     'qa_artifacts.png</a></div>' % (save(im, '%s_qa_artifacts.png' % lab), html.escape(lab),
                                                     html.escape(os.path.abspath(fp))))
    P.append('</div>')
    P.append('<h2>The outlines</h2><img src="img/curves.png" width="1200">')
    P.append('<h2>The numbers</h2><table><tr><th>check</th><th>design</th>' +
             ''.join('<th colspan="2">%s</th>' % html.escape(l) for l in labels) + '</tr>')
    for k in SHOW:
        dv = Cd.get(k, {}).get('design') if k in Cd else None
        if dv is None and C and k in C[0]:
            dv = C[0][k].get('design')
        row = '<tr><td>%s</td><td>%s</td>' % (k, '' if dv is None else html.escape(str(dv)))
        for c in C:
            v = c.get(k, {})
            lvl = v.get('level')
            row += '<td class="%s">%s %s</td><td>%s</td>' % (v.get('status', ''), v.get('value'), v.get('status', ''),
                                                            '' if lvl is None else 'level %s' % lvl)
        P.append(row + '</tr>')
    P.append('<tr><td>crown: skin faces facing in (of those over the top)</td><td>0</td>' +
             ''.join('<td colspan="2">%d of %d</td>' % cr for cr in crowns) + '</tr>')
    for k in QA:
        row = '<tr><td>%s (the build\'s QA)</td><td></td>' % k
        for q in Q:
            v, s = cell(q.get(k))
            row += '<td colspan="2" class="%s">%s %s</td>' % (s, v, s)
        P.append(row + '</tr>')
    P.append('</table>')
    P.append('<p class="note">Builds: %s</p>' % ', '.join('<a href="%s">%s</a>' % (html.escape(os.path.abspath(b)),
                                                                                   html.escape(l))
                                                        for b, l in zip(builds, labels)))
    path = os.path.join(out, 'index.html')
    open(path, 'w').write('\n'.join(P))
    json.dump(dict(labels=labels, checks=[{k: {a: b for a, b in c.get(k, {}).items() if a in ('value', 'status', 'level',
                                                                                                 'design')}
                                           for k in SHOW} for c in C], crown=crowns),
              open(os.path.join(out, 'numbers.json'), 'w'), indent=1, default=str)
    print(path)


if __name__ == '__main__':
    main(sys.argv[1:])
