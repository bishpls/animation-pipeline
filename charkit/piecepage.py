"""The outfit's review page, piece by piece: each piece of a build against the design's drawn piece (the outfit's
per-view masks, as the QA's sheet_pieces grades it), with another build beside it when given.

    python -m charkit pieces BUILD_DIR [--against OTHER_BUILD_DIR] [--out DIR]    -> DIR/index.html (default BUILD/pieces)

Per piece and view: a crop round the piece, the design dimmed under our outline (white) and the drawn outline (red),
and the numbers (iou_tol graded, the plain IoU, the outline agreement, pixels ours / drawn); where the drawn piece's
pixels land in ours; the pieces we don't build and what they are compared as part of. Pure venv (the bundle and the
QA's own z-buffer).
"""
import html, json, os, sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAD = 0.15                      # L round a piece's crop


def measure(build):
    """a build's pieces as the QA grades them -> dict(S (bodymeasure.piece_shapes), C (the checks), labels, names, masks,
    graph, dv, ppl, spec, confusion)."""
    from . import bodyqa, bodymeasure, bundle as bl, qa3d
    B = bl.load(os.path.join(build, 'bundle'))
    D = qa3d.Design(B)
    ctx = D.sheet_context()
    masks, graph, _ = bodymeasure.piece_masks(B.spec)
    meshes, names = qa3d.scene_objects(B)
    obj = [(V, T, np.where(V[T].mean(1)[:, 0] >= 0, i, i + 1000)) for i, (V, T, _) in enumerate(meshes)]
    dv = D.design_views()
    az = bodyqa.azimuths(ctx['az3'])
    iw = np.array(qa3d.iris_centres(B))
    As = B.assembly
    labels = {v: qa3d.bodyqa_zbuffer(obj, az[v], bodyqa.origin(v, az[v], iw, As['centre']), As['L'], ctx['ppl'])
              for v in dv}
    S = bodymeasure.piece_shapes(labels, names, masks, graph, B.spec, ctx['ppl'])
    C = qa3d.grade_pieces(S)
    conf = {v: bodymeasure.piece_confusion(labels, names, masks, graph, B.spec, v) for v in labels}
    return dict(S=S, C=C, labels=labels, names=names, masks=masks, graph=graph, dv=dv, ppl=ctx['ppl'], spec=B.spec,
                confusion=conf)


def crop(M, pid, view):
    """one piece in one view: the design dimmed, the drawn piece (folded, as graded) tinted, our outline white and the
    drawn outline red, cropped round both -> image or None."""
    from . import bodymeasure
    lab = M['labels'][view]
    idx = {n: i for i, n in enumerate(M['names'])}
    pm = bodymeasure.piece_map(M['graph'], M['spec'])
    F = bodymeasure.folded(M['masks'], M['graph'], pm)
    d = F.get('%s__%s' % (view, pid))
    if d is None or not d.any():
        return None
    m = bodymeasure.member_mask(lab, idx, pm[pid]) if pm.get(pid) else np.zeros(lab.shape, bool)
    img = 0.45 * np.asarray(M['dv'][view]['rgb'], float) + 0.2
    img[d] = 0.6 * img[d] + 0.4 * np.array([1.0, 0.75, 0.3])
    img[bodymeasure.outline(m)] = (1.0, 1.0, 1.0)
    img[bodymeasure.outline(d)] = (0.9, 0.1, 0.1)
    rr, cc = np.nonzero(d | m)
    p = int(PAD * M['ppl'])
    r0, r1 = max(0, rr.min() - p), min(lab.shape[0], rr.max() + p + 1)
    c0, c1 = max(0, cc.min() - p), min(lab.shape[1], cc.max() + p + 1)
    return img[r0:r1, c0:c1]


def page(build, out, against=None):
    from PIL import Image
    M = measure(build)
    A = measure(against) if against else None
    img = os.path.join(out, 'img')
    os.makedirs(img, exist_ok=True)

    def save(a, name, h=220):
        im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
        if im.size[1] > h:
            im = im.resize((max(1, int(im.size[0] * h / im.size[1])), h), Image.LANCZOS)
        im.save(os.path.join(img, name))
        return 'img/' + name
    C = M['C']
    order = sorted([p for p in C if p != 'built' and C[p].get('value') is not None], key=lambda p: C[p]['value'])
    order += sorted(p for p in C if p != 'built' and C[p].get('value') is None)
    L = ['<!doctype html><meta charset="utf-8"><title>outfit pieces</title><style>body{font:14px/1.45 -apple-system,'
         'system-ui,sans-serif;margin:24px;background:#fafafa;color:#222}h2{font-size:17px;margin:28px 0 6px}.row{display:'
         'flex;gap:10px;flex-wrap:wrap;align-items:flex-end}.tile{text-align:center;font-size:12px;color:#555}.tile img{'
         'display:block;border:1px solid #ddd;background:#fff}table{border-collapse:collapse;font-size:13px}td,th{border:'
         '1px solid #ddd;padding:3px 8px;text-align:right}th{background:#f0f0f0}td:first-child{text-align:left}.PASS{color:'
         '#070}.WARN{color:#b60}.FAIL{color:#c00}.INFO{color:#666}.note{color:#666;font-size:12px}</style>',
         '<h1>Outfit pieces: %s</h1>' % html.escape(os.path.relpath(build, ROOT)),
         '<p class="note">Each piece of ours against the design\'s drawn piece: the outfit\'s per-view masks (the produced '
         '<code>outfit_masks</code>, cut from body_turnaround by the outfit graph; they agree with the sheet\'s figures at '
         '0.77&ndash;0.85 IoU, the ceiling here). Graded: <b>iou_tol</b>, the overlap with a drawn line\'s width (%.2f L) '
         'either side of the drawn outline left out, over the piece\'s views weighted by how much of it each shows: PASS &ge; 0.75, WARN &ge; 0.5. Also the '
         'plain IoU and the outline agreement (the share of each outline within that width of the other). A piece we '
         'don\'t build is compared as part of the one it attaches to. In the crops: the drawn piece tinted, its outline '
         'red, ours white. Built: <b>%s</b>; not built: %s.</p>' % (
             0.02, C['built']['value'], html.escape(', '.join(C['built'].get('missing', []))))]
    L.append('<table><tr><th>piece</th><th>iou_tol (weighted)</th><th>status</th>%s<th>per view: iou_tol / iou / outline'
             '</th><th>ours are</th></tr>' % ('<th>against</th>' if A else ''))
    for pid in order:
        c = C[pid]
        r = M['S'][pid]
        vs = ' &nbsp; '.join('%s %.2f / %.2f / %.2f' % (v[:5], x['iou_tol'], x['iou'], x['f']) for v, x in r['views'].items())
        a = (A['C'].get(pid) or {}) if A else None
        who = ', '.join(r['members']) if r['members'] else ('part of <b>%s</b>' % r['part_of'] if r['part_of'] else 'none')
        if r.get('with'):
            who += ' (with %s)' % ', '.join(r['with'])
        L.append('<tr><td><a href="#%s">%s</a></td><td>%s</td><td class="%s">%s</td>%s<td>%s</td><td>%s</td></tr>' % (
            pid, pid, '' if c.get('value') is None else '%.3f' % c['value'], c['status'], c['status'],
            ('<td class="%s">%s %s</td>' % (a.get('status', ''), a.get('value', ''), a.get('status', ''))) if A else '',
            vs, who))
    L.append('</table>')
    for pid in order:
        r = M['S'][pid]
        if not r['views']:
            continue
        L.append('<h2 id="%s">%s <span class="%s">%s %s</span></h2><div class="row">' % (
            pid, pid, C[pid]['status'], '' if C[pid].get('value') is None else '%.3f' % C[pid]['value'], C[pid]['status']))
        for view, x in r['views'].items():
            for tag, MM in (('ours', M),) + ((('against', A),) if A else ()):
                im = crop(MM, pid, view)
                if im is None:
                    continue
                xx = MM['S'][pid]['views'].get(view, {})
                conf = MM['confusion'][view].get(pid) or {}
                land = ', '.join('%s %d%%' % (k, round(100 * n / max(1, sum(conf.values()))))
                                 for k, n in sorted(conf.items(), key=lambda t: -t[1])[:3])
                L.append('<div class="tile"><img src="%s"><b>%s</b>%s<br>iou_tol %.2f &middot; iou %.2f &middot; outline '
                         '%.2f<br>px %s / %s<br>drawn lands on: %s</div>' % (
                             save(im, '%s_%s_%s.png' % (pid, view, tag)), view, ' (%s)' % tag if A else '',
                             xx.get('iou_tol', 0), xx.get('iou', 0), xx.get('f', 0), *(xx.get('px') or ['', '']),
                             html.escape(land)))
        L.append('</div>')
    open(os.path.join(out, 'index.html'), 'w').write('\n'.join(L))
    json.dump({'checks': C, 'pieces': M['S'], 'confusion': M['confusion']}, open(os.path.join(out, 'pieces.json'), 'w'),
              indent=1)
    return os.path.join(out, 'index.html')


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return 0
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    build = os.path.abspath(args[0])
    out = os.path.abspath(opt('--out', os.path.join(build, 'pieces')))
    against = opt('--against')
    p = page(build, out, os.path.abspath(against) if against else None)
    print(p)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
