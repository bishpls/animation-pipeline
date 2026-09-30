"""Face round 5's review page, in the design's projection: the head sheet | before | after, each build rendered
orthographic and level with the head's eye line (face_level.py; hair shown and hidden), close on the chin and jaw in
front, three-quarter and profile at one px per L, with the traces (the design's red, ours blue: level, the hair hidden)
and head_construction's registered outline (green) where the head sheet's hair covers the face's edge (over the dashed
row). Then head_construction against head_turnaround (face5_lab agree), the chin checks in both projections, the
subdivision move's QA diff, and every build's jaw numbers.

    python face5_page.py OUT_DIR BEFORE AFTER [--mid BUILD] [--labels a,b] [--head SNIPPET.html]

BEFORE / AFTER: build folders (bundle/, qa/qa.json, level/ from level_slot.py). --mid: the build between them for the
subdivision's own diff (the geometry commit before the subdivision move). Prints the page's path."""
import html, json, os, re, sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from charkit import bundle as bl, faceregion as fr, manifest, qa3d, refcheck  # noqa: E402
import face4_page, jaw3_page, jaw_page  # noqa: E402

PPL = jaw3_page.PPL
CROP = dict(jaw3_page.CROP, front=(0.02, 0.46, 0.42))     # (the front from the eye line: the rows under the hair too)
CHIN = ('chin_angle', 'chin_tip', 'jaw_taper_shape', 'jaw_line_bend', 'tq_cheek_hollow', 'tq_jaw_notch',
        'jaw_line_front', 'jaw_line_three_quarter')
SHOW = CHIN + ('jaw_outline_hidden', 'jaw_taper', 'chin_point_z', 'chin_v', 'neck_to_face', 'chin_underside',
               'neck_front_wiggle')
FACE = ('eye_', 'cheek_', 'profile_edge', 'neck_', 'jaw_', 'chin_', 'tq_', 'sheet_', 'face_', 'brow', 'mouth', 'nose',
        'art_', 'hair_penetration', 'expr_', 'body_profile_iou_skin', 'piece_collar')


def poly(im, pts, top, half, col, width=2, dash=False):
    d = ImageDraw.Draw(im)
    P = [((u + half) * PPL, (top - z) * PPL) for u, z in pts]
    if dash:
        for i in range(0, len(P) - 1, 6):
            d.line(P[i:i + 3], fill=col, width=width)
    else:
        d.line(P, fill=col, width=width)


def construction_overlay(im, H, zlo, top, half, col=(20, 150, 40)):
    """head_construction's registered outline over the sheet's hair-occlusion row zlo (and dashed under it)."""
    X = H.get('outline')
    if X is None:
        return
    for sel, dash in (((X[:, 1] > zlo) & (X[:, 1] <= fr.HIDDEN_ZMAX), False), ((X[:, 1] <= zlo), True)):
        idx = np.nonzero(sel)[0]
        if not len(idx):
            continue
        runs = np.split(idx, np.nonzero(np.diff(idx) > 1)[0] + 1)
        for r in runs:
            if len(r) > 3:
                poly(im, X[r], top, half, col, 2 if not dash else 1, dash)


def checks_of(B, D, ppl, az):
    meshes, _ = qa3d.scene_classes(B)
    V, T_, _, _ = B.skin().mesh('masked')
    Dt = {vn: D[vn].get('taper') for vn in ('front', 'three_quarter')}
    O = fr.ours_jaw(meshes, (V, T_), qa3d.iris_centres(B), float(B.assembly['eye_z']), float(B.assembly['L']), ppl, az,
                    D['front'].get('chin', (0, None))[1], Dt['front']['z0'],
                    design_tq_top=Dt['three_quarter'].get('top'))[0]
    c = fr.jaw_compare(D, O, ppl)
    c.update(fr.taper_checks(D, O))
    return c


def qa_of(b):
    q = json.load(open(os.path.join(b, 'qa', 'qa.json')))
    return q.get('checks', q)


def main(args):
    out, rest = args[0], args[1:]
    opt = lambda k: rest[rest.index(k) + 1] if k in rest else None
    flags = {'--labels', '--head', '--mid'}
    builds = [a for i, a in enumerate(rest) if a not in flags and (i == 0 or rest[i - 1] not in flags)]
    labels = (opt('--labels') or 'before,after').split(',')
    img = os.path.join(out, 'img')
    os.makedirs(img, exist_ok=True)
    spec = manifest.resolve(json.load(open(os.path.join(ROOT, 'charkit/spec/clawd.json'))))
    rgb0, _ = refcheck.without_guides(np.asarray(refcheck._load(spec['ref']['face_sheet']['image']), float))
    _, f, Hs = refcheck.at_scale(rgb0, 0.168, 2 * 0.168 * refcheck.FACE_PPL, -1)
    D, ppl, Dc, az = fr.design_jaw(spec, 0.168)
    Hc = D['front'].get('hidden') or {}
    Dt = {vn: D[vn].get('taper') for vn in ('front', 'three_quarter')}
    Dp = jaw3_page.profile_trace(Dc['profile'], ppl)
    z0, top_f, top_q = Dt['front']['z0'], Dt['front'].get('top'), Dt['three_quarter'].get('top')
    Bs = [bl.load(os.path.join(b, 'bundle')) for b in builds]
    az3 = az['three_quarter']
    Mt = [face4_page.level_traces(B, PPL, az3, z0, top_q) for B in Bs]
    C = [checks_of(B, D, ppl, az) for B in Bs]
    Q = [qa_of(b) for b in builds]
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
    P = ['<!doctype html><meta charset="utf-8"><title>Jaw under hair</title><style>%s</style>' % css,
         '<h1>The chin graded level, the jaw under the hair, round 5: design | %s</h1>' % ' | '.join(
             html.escape(l) for l in labels)]
    if opt('--head'):
        P.append(open(opt('--head')).read())
    P.append('<p class="note">The design\'s projection: each build rendered orthographic and level with the head\'s eye '
             'line in the boards\' look (face_level.py), close on the chin at %d px per L, red ticks at the eye line and '
             'every 0.1 L under it. Red: the head sheet\'s traced outline; the dashed red row is where its side locks '
             'start covering the face\'s edge (z %.3f). Green: head_construction\'s outline registered on the sheet (rows '
             'scaled %.3f so the chins meet, widths %.3f; it reads the sheet\'s outline to %.4f L rms where both show '
             'the face), solid over the dashed row where it is the authority, dotted under it. Blue: each build\'s own '
             'outline, traced in the level camera with the hair hidden.</p>' % (
                 PPL, top_f, Hc.get('sz', float('nan')), Hc.get('sx', float('nan')), Hc.get('fit', float('nan'))))
    for view, _ in face4_page.VIEWS:
        top, bot, half = CROP[view]
        for tag in ('hair', 'bare'):
            P.append('<h2>%s, %s</h2><div class="row">' % (view.replace('_', '-'), 'hair shown' if tag == 'hair'
                                                            else 'hair hidden'))
            im = jaw_page.ticks(jaw_page.design_crop(rgb0, f, Hs, view, top, bot, half), top).convert('RGB')
            jaw3_page.draw(im, view, Dp if view == 'profile' else Dt[view], top, half, (220, 30, 30))
            mz = top_f if view == 'front' else top_q if view == 'three_quarter' else None
            if mz is not None:
                jaw3_page.dashed(im, mz, top, (220, 30, 30))
            if view == 'front' and Hc:
                construction_overlay(im, Hc, top_f, top, half)
            P.append('<div class="tile"><img src="%s" width="%d">design (head sheet)</div>' % (
                save(im, 'design_%s_%s.png' % (view, tag)), im.size[0]))
            for B, b, lab, M in zip(Bs, builds, labels, Mt):
                lv = os.path.join(b, 'level')
                if not os.path.exists(os.path.join(lv, 'level.json')):
                    continue
                im = jaw_page.ticks(face4_page.level_crop(lv, view, B, top, bot, half, tag), top).convert('RGB')
                jaw3_page.draw(im, view, M.get(view), top, half, (30, 90, 220))
                if view == 'front':
                    jaw3_page.draw(im, view, Dt['front'], top, half, (220, 30, 30), 1)
                    jaw3_page.dashed(im, top_f, top, (220, 30, 30))
                    if Hc:
                        construction_overlay(im, Hc, top_f, top, half)
                P.append('<div class="tile"><img src="%s" width="%d">%s <a href="%s">level_%s_%s.png</a></div>' % (
                    save(im, '%s_%s_%s.png' % (lab, view, tag)), im.size[0], html.escape(lab),
                    html.escape(os.path.abspath(os.path.join(lv, 'level_%s_%s.png' % (view, tag)))), view, tag))
            P.append('</div>')
    # head_construction against head_turnaround
    ag = os.path.join(ROOT, 'charkit/out/face5/agree')
    if os.path.exists(os.path.join(ag, 'agree.json')):
        A = json.load(open(os.path.join(ag, 'agree.json')))
        fa = A['front']
        P.append('<h2>head_construction against head_turnaround (where both show the face)</h2><div class="row">'
                 '<div class="tile"><img src="%s" width="700">the front outlines by row (half-width either side): red '
                 'the head sheet, dark green the construction as drawn, light green registered on the chin, blue ours '
                 '(before, level, bare) <a href="%s">agree.json</a></div></div>' % (
                     save(Image.open(os.path.join(ag, 'agree.png')), 'agree.png'),
                     html.escape(os.path.join(ag, 'agree.json'))))
        P.append('<table><tr><th>measure (rows z %s to %s)</th><th>value</th></tr>' % tuple(A['rows_both']))
        for k, v in (('half-width rms, as drawn (L)', fa['half_width_rms']),
                     ('half-width mean, construction - sheet (L)', fa['half_width_mean']),
                     ('chin: construction - sheet, z (L)', fa['chin']['dz']),
                     ('face regions\' IoU, as drawn', fa['region_iou_shown']),
                     ('registered (rows scaled so the chins meet, widths fitted): rms (L)', Hc.get('fit')),
                     ('registered: sz, sx', '%s, %s' % (Hc.get('sz'), Hc.get('sx'))),
                     ('chin_angle: sheet, construction', '%s, %s' % (fa['chin_angle']['turnaround'],
                                                                    fa['chin_angle']['construction'])),
                     ('chin_tip: sheet, construction', '%s, %s' % (fa['tip_share']['turnaround'],
                                                                  fa['tip_share']['construction'])),
                     ('profile front edge rms, as drawn (L)', A['profile']['front_edge_rms']),
                     ('profile underside (deg): sheet, construction', '%s, %s' % (
                         A['profile']['underside_deg']['turnaround'], A['profile']['underside_deg']['construction']))):
            P.append('<tr><td>%s</td><td>%s</td></tr>' % (html.escape(k), html.escape(str(v))))
        P.append('</table>')
    # the chin in both projections
    P.append('<h2>The chin and jaw checks in both projections</h2><p class="note">Graded now in the level camera, '
             'orthographic (the design\'s projection); the boards\' camera (85 mm, 1 m, 6 degrees over the chin, which '
             'shortens the V) beside. "QA" is the build\'s own qa.json: before is pipeline-3d\'s measure (graded in the '
             'boards\' camera), after this branch\'s.</p><table><tr><th>check</th><th>design</th>' +
             ''.join('<th>%s level</th><th>%s board</th><th>%s QA</th>' % ((html.escape(l),) * 3) for l in labels) +
             '</tr>')
    for k in SHOW:
        dv = next((c[k].get('design') for c in C if k in c and c[k].get('design') is not None), '')
        row = '<tr><td>%s</td><td>%s</td>' % (k, html.escape(str(dv)))
        for c, q in zip(C, Q):
            v = c.get(k, {})
            qv = q.get(k) or {}
            row += '<td class="%s">%s %s</td><td>%s</td><td class="%s">%s %s</td>' % (
                v.get('status', ''), v.get('value', ''), v.get('status', ''), '' if v.get('board') is None else v['board'],
                qv.get('status', ''), qv.get('value', ''), qv.get('status', ''))
        P.append(row + '</tr>')
    P.append('</table><h2>The outlines</h2><img src="img/curves.png" width="1200">')
    # the subdivision move and every face check that moved
    mid = opt('--mid')
    pairs = [(labels[0], builds[0], labels[1], builds[1])]
    if mid:
        pairs = [(labels[0], builds[0], 'geometry', mid), ('geometry', mid, labels[1], builds[1])]
    for la, a, lb, b in pairs:
        qa_, qb = qa_of(a), qa_of(b)
        P.append('<h2>QA: %s -> %s (the face\'s checks that moved)</h2><table><tr><th>check</th><th>%s</th><th>%s</th>'
                 '</tr>' % (html.escape(la), html.escape(lb), html.escape(la), html.escape(lb)))
        n = 0
        for k in sorted(set(qa_) | set(qb)):
            if not k.startswith(FACE):
                continue
            x, y = qa_.get(k) or {}, qb.get(k) or {}
            if (x.get('value'), x.get('status')) == (y.get('value'), y.get('status')):
                continue
            n += 1
            P.append('<tr><td>%s</td><td class="%s">%s %s</td><td class="%s">%s %s</td></tr>' % (
                k, x.get('status', ''), x.get('value', ''), x.get('status', ''), y.get('status', ''), y.get('value', ''),
                y.get('status', '')))
        P.append('</table><p class="note">%d moved.</p>' % n)
    P.append('<p class="note">Builds: %s</p>' % ', '.join('<a href="%s">%s</a>' % (html.escape(os.path.abspath(b)),
                                                                                   html.escape(l))
                                                        for b, l in zip(builds + ([mid] if mid else []),
                                                                        labels + (['geometry'] if mid else []))))
    path = os.path.join(out, 'index.html')
    open(path, 'w').write('\n'.join(P))
    json.dump(dict(labels=labels, checks=[{k: {a: b for a, b in c.get(k, {}).items() if a in ('value', 'status', 'board',
                                                                                                 'design')}
                                           for k in SHOW} for c in C]),
              open(os.path.join(out, 'numbers.json'), 'w'), indent=1, default=str)
    print(path)


if __name__ == '__main__':
    main(sys.argv[1:])
