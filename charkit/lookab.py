"""The look's A/B review (docs/workstreams/look.md): two builds of one spec, before and after a look change, compared on
their boards and measured. Written for Michael's calls H (the streaks' hash) and I (lines on thin shells).

    python -m charkit.lookab MANIFEST.json [--open]

MANIFEST: {"out": DIR, "before": BUILD, "after": BUILD,
           "streaks": {"before": {LABEL: [BOARDS_DIR, BOARDS_DIR_WITHOUT_STREAKS], ...}, "after": {...}},
           "normals": {"before": normals.json, "after": normals.json},      (charkit/boards/lookprobe.py --normals)
           "compare": {"before": compare.json, "after": compare.json},      (python -m charkit.render compare)
           "crops": {NAME: [BOARD, x0, y0, x1, y1], ...}}

What it measures:
  streaks     per phase, per board, per pair of renderers (EEVEE on each GPU, charkit.render on each): each one's streak
              pixels (its board against the same renderer's board without them, more than 4 levels apart), their IoU,
              and the two boards' difference inside the union of both (mean, share over 8 levels)
  silhouette  per board: EEVEE's character mask (farther than 6 levels from the background) before against after: IoU,
              xor px, the mean move of the outline (area change over perimeter, px)
  pieces      per board and outlined object: its own silhouette alone (charkit.render ids with only its primitives, at
              4 x), before against after: the mean move of its outline in px (area change over perimeter), and the share
              of its silhouette's edge drawn by its own hull (the line; the rest its surface poking past the hull)
  lines       per board: the ink's mean width (charkit.render.compare.line_stats) before and after
  page        per board EEVEE before | after | difference at the same scale, the close-ups (x4, nearest), the tables
"""
import html, json, os, shutil, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def _img(p):
    from PIL import Image
    return np.asarray(Image.open(p).convert('RGB'))


def _save(p, a):
    from PIL import Image
    os.makedirs(os.path.dirname(p), exist_ok=True)
    Image.fromarray(a).save(p)


def _diff(a, b):
    return np.abs(a.astype(np.int16) - b.astype(np.int16)).max(-1)


def streak_pixels(on, off, tol=4):
    """a renderer's streak pixels: its board against its own board without the streaks."""
    return _diff(on, off) > tol


def streak_table(sets, names):
    """sets: {label: (on_dir, off_dir)} -> {board: {pair: {iou, union_px, mean, over8, px_a, px_b}}} and the totals."""
    labels = list(sets)
    out, tot = {}, {}
    for nm in names:
        imgs = {}
        for lb, (don, doff) in sets.items():
            pon, poff = os.path.join(don, nm + '.png'), os.path.join(doff, nm + '.png')
            if os.path.exists(pon) and os.path.exists(poff):
                on = _img(pon)
                imgs[lb] = (on, streak_pixels(on, _img(poff)))
        row = {}
        for i, a in enumerate(labels):
            for b in labels[i + 1:]:
                if a not in imgs or b not in imgs:
                    continue
                (ia, ma), (ib, mb) = imgs[a], imgs[b]
                u = ma | mb
                d = _diff(ia, ib)[u]
                r = {'px_a': int(ma.sum()), 'px_b': int(mb.sum()), 'union_px': int(u.sum()),
                     'iou': round(float((ma & mb).sum() / max(u.sum(), 1)), 4) if u.any() else None,
                     'mean': round(float(d.mean()), 3) if d.size else 0.0,
                     'over8': round(float((d > 8).mean()), 4) if d.size else 0.0}
                row[f'{a} | {b}'] = r
                t = tot.setdefault(f'{a} | {b}', {'inter': 0, 'union': 0, 'sum': 0.0, 'over8': 0})
                t['inter'] += int((ma & mb).sum()); t['union'] += int(u.sum()); t['sum'] += float(d.sum())
                t['over8'] += int((d > 8).sum())
        out[nm] = row
    totals = {k: {'iou': round(t['inter'] / max(t['union'], 1), 4), 'union_px': t['union'],
                  'mean': round(t['sum'] / max(t['union'], 1), 3), 'over8': round(t['over8'] / max(t['union'], 1), 4)}
              for k, t in tot.items()}
    return out, totals


def _perimeter(m):
    """the mask's boundary length in its own px (4-neighbour edges between in and out)."""
    return float((m[:, 1:] != m[:, :-1]).sum() + (m[1:] != m[:-1]).sum())


def silhouette(a, b, bg):
    from charkit.render import compare
    fa, fb = compare.fg_mask(a, bg), compare.fg_mask(b, bg)
    per = _perimeter(fa)
    return {'iou': round(float((fa & fb).sum() / max((fa | fb).sum(), 1)), 5), 'xor_px': int((fa ^ fb).sum()),
            'grow_px': round(float(fb.sum() - fa.sum()) / max(per, 1.0), 4), 'fg_px': int(fa.sum())}


def pieces(vrm_a, vrm_b, bundle, ss=4):
    """per board and outlined object: the mean move of its own silhouette (alone) from build a to b, px."""
    from charkit.render import gpu, model, views
    from charkit.render.__main__ import _head
    eye_z, L = _head(bundle)
    res = {}
    R = {}
    for tag, vrm in (('a', vrm_a), ('b', vrm_b)):
        M = model.load(vrm)
        R[tag] = gpu.Renderer(M, ss=1, live_normals=False)
    V = views.board_views(R['a'].M, ('views', 'body'), eye_z=eye_z, L=L)
    objs = sorted({it['P'].object for it in R['a'].items if it['outline']})
    for v in V:
        row = {}
        for ob in objs:
            area, per, ink = {}, {}, {}
            for tag in ('a', 'b'):
                Rr = R[tag]
                keep = Rr.items
                Rr.items = [it for it in keep if it['P'].object == ob]
                try:
                    part, hull = Rr.ids(v, ss=ss)
                finally:
                    Rr.items = keep
                m = part >= 0
                area[tag], per[tag] = m.sum() / ss / ss, _perimeter(m) / ss
                edge = m.copy()
                edge[1:-1, 1:-1] &= ~(m[:-2, 1:-1] & m[2:, 1:-1] & m[1:-1, :-2] & m[1:-1, 2:])
                ink[tag] = float(hull[edge].mean()) if edge.any() else None
            if area['a'] > 0:
                row[ob] = {'area_px': round(float(area['a']), 1),
                           'grow_px': round(float(area['b'] - area['a']) / max(per['a'], 1.0), 4),
                           'edge_ink_before': None if ink['a'] is None else round(ink['a'], 4),
                           'edge_ink_after': None if ink['b'] is None else round(ink['b'], 4)}
        res[v.name] = row
    return res


def _crop(a, box, k=4):
    x0, y0, x1, y1 = box
    c = a[y0:y1, x0:x1]
    return np.repeat(np.repeat(c, k, 0), k, 1)


def main(manifest, open_=False):
    from charkit.render import compare, views
    C = json.load(open(manifest))
    out = C['out']
    os.makedirs(out, exist_ok=True)
    A, B = C['before'], C['after']
    names = sorted(f[:-4] for f in os.listdir(os.path.join(A, 'boards')) if f.endswith('.png')
                   and f.startswith(('face_', 'body_')))
    rep = {'before': A, 'after': B, 'boards': {}}
    for nm in names:
        a, b = _img(os.path.join(A, 'boards', nm + '.png')), _img(os.path.join(B, 'boards', nm + '.png'))
        d = _diff(a, b)
        la, lb = compare.line_stats(a), compare.line_stats(b)
        rep['boards'][nm] = {'diff': {'mean': round(float(d.mean()), 3), 'over8': round(float((d > 8).mean()), 5),
                                      'max': int(d.max())},
                             'silhouette': silhouette(a, b, views.BG),
                             'lines': {'before': la.get('mean_width'), 'after': lb.get('mean_width'),
                                       'ink_px_before': la.get('ink_px'), 'ink_px_after': lb.get('ink_px'),
                                       'median_before': la.get('median'), 'median_after': lb.get('median')}}
        for tag, im in (('before', a), ('after', b)):
            _save(os.path.join(out, tag, nm + '.png'), im)
        _save(os.path.join(out, 'diff', nm + '.png'), compare.heatmap(a, b))
    if C.get('streaks'):
        rep['streaks'] = {}
        for phase, sets in C['streaks'].items():
            per, tot = streak_table(sets, names)
            rep['streaks'][phase] = {'boards': per, 'totals': tot}
    if C.get('pieces', True):
        vrm = lambda d: os.path.join(d, next(f for f in sorted(os.listdir(d)) if f.endswith('.vrm') and '.springs.' not in f))
        rep['pieces'] = pieces(vrm(A), vrm(B), os.path.join(A, 'bundle'))
    for key in ('normals', 'compare'):
        if C.get(key):
            rep[key] = {ph: json.load(open(p)) for ph, p in C[key].items() if p and os.path.exists(p)}
    crops = C.get('crops') or {}
    rep['crops'] = {}
    for cn, (nm, *box) in crops.items():
        files = {}
        a, b = _img(os.path.join(A, 'boards', nm + '.png')), _img(os.path.join(B, 'boards', nm + '.png'))
        for tag, im in (('before', a), ('after', b), ('diff', compare.heatmap(a, b))):
            f = f'crops/{cn}_{tag}.png'
            _save(os.path.join(out, f), _crop(im, box))
            files[tag] = f
        for phase, sets in ((C.get('streaks') or {}).items() if 'streak' in cn else ()):   # per renderer
            for lb, (don, _) in sets.items():
                p = os.path.join(don, nm + '.png')
                if os.path.exists(p):
                    f = f'crops/{cn}_{phase}_{lb}.png'.replace(' ', '_')
                    _save(os.path.join(out, f), _crop(_img(p), box))
                    files[f'{phase}: {lb}'] = f
        rep['crops'][cn] = {'board': nm, 'box': box, 'files': files}
    json.dump(rep, open(os.path.join(out, 'lookab.json'), 'w'), indent=1, default=str)
    p = page(out, rep, C)
    print('page', p)
    if open_:
        os.system(f'open "{p}"')
    return rep


# ------------------------------------------------------------------------------------------------ the page
CSS = (':root{--bg:#f4f4f6;--fg:#1d1d22;--mute:#6a6a75;--card:#fff;--line:#dcdce3;--good:#1a7f37;--bad:#b42318}'
       '@media (prefers-color-scheme:dark){:root{--bg:#16161a;--fg:#e8e8ee;--mute:#9a9aa6;--card:#202027;--line:#34343d;'
       '--good:#4ac26b;--bad:#ff7b72}}'
       'body{background:var(--bg);color:var(--fg);font:14px/1.45 -apple-system,system-ui,sans-serif;margin:0;padding:16px 24px}'
       'h1{font-size:20px;margin:4px 0 2px}h2{font-size:16px;margin:24px 0 8px}h3{font-size:14px;margin:14px 0 6px}'
       '.mute{color:var(--mute)}table{border-collapse:collapse;background:var(--card);font-variant-numeric:tabular-nums;'
       'margin:6px 0}td,th{border:1px solid var(--line);padding:3px 7px;text-align:right}th{text-align:center}'
       'td:first-child{text-align:left}.board{background:var(--card);border:1px solid var(--line);border-radius:6px;'
       'padding:10px;margin:14px 0}.row{display:flex;gap:8px;overflow-x:auto;align-items:flex-start}.row figure{margin:0}'
       '.row img{display:block;border:1px solid var(--line);image-rendering:pixelated}'
       '.big img{height:min(60vh,620px)}figcaption{font-size:12px;color:var(--mute);margin-top:3px;max-width:520px}'
       'code{font-size:12px}ul{margin:4px 0 4px 18px;padding:0}')


def _fig(src, cap, cls=''):
    e = html.escape
    return (f'<figure class="{cls}"><a href="{e(src)}"><img src="{e(src)}" alt="{e(cap)}"></a>'
            f'<figcaption>{e(cap)} &middot; <a href="{e(src)}">{e(os.path.basename(src))}</a></figcaption></figure>')


def page(out, rep, C):
    e = html.escape
    H = ['<!doctype html><html><head><meta charset="utf-8"><title>Look A/B</title>', f'<style>{CSS}</style></head><body>']
    H.append(f'<h1>{e(C.get("title", "The look, before and after"))}</h1>')
    H.append(f'<div class="mute">before <code>{e(rep["before"])}</code> &middot; after <code>{e(rep["after"])}</code>'
             f'</div>')
    for x in C.get('intro', []):
        H.append(f'<p>{x}</p>')
    # the streaks
    if rep.get('streaks'):
        H.append('<h2>The streaks: the same pixels across renderers and GPUs?</h2>')
        H.append('<p class="mute">Each renderer\'s streak pixels are its board against the same renderer\'s board '
                 'without the streaks (more than 4 levels apart). IoU of two renderers\' streak pixels, and the two '
                 'boards\' difference inside the union of both (all nine boards).</p>')
        H.append('<table><tr><th>pair</th><th colspan=3>before</th><th colspan=3>after</th></tr><tr><th></th>'
                 '<th>IoU</th><th>mean lv</th><th>&gt;8 lv</th><th>IoU</th><th>mean lv</th><th>&gt;8 lv</th></tr>')
        pairs = []
        for ph in ('before', 'after'):
            for k in (rep['streaks'].get(ph) or {}).get('totals', {}):
                if k not in pairs:
                    pairs.append(k)
        for k in pairs:
            cells = []
            for ph in ('before', 'after'):
                t = ((rep['streaks'].get(ph) or {}).get('totals') or {}).get(k)
                cells += ([f'{t["iou"]:.3f}', f'{t["mean"]:.2f}', f'{100 * t["over8"]:.1f}%'] if t else ['-'] * 3)
            H.append(f'<tr><td>{e(k)}</td>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>')
        H.append('</table>')
    # the outline on thin shells
    nr = rep.get('normals') or {}
    if nr:
        H.append('<h2>Lines on thin shells: shading normals the outline turns more than 90 degrees</h2>')
        for x in C.get('normals_note', []):
            H.append(f'<p class="mute">{x}</p>')
        H.append('<table><tr><th>piece</th><th>shell mm</th><th>cap mm</th>' + ''.join(
            f'<th>{w}: before (rim / away)</th><th>{w}: after (rim / away)</th>' for w in ('build', 'face', 'body'))
            + '</tr>')
        ob_b, ob_a = (nr.get('before') or {}).get('objects', {}), (nr.get('after') or {}).get('objects', {})
        for n in ob_b:
            a, b = ob_b[n], ob_a.get(n, {})
            if a.get('region') not in ('garment', 'accessory'):
                continue
            cells = []
            for w in ('build', 'face', 'body'):
                for r in (a, b):
                    x = (r.get('widths') or {}).get(w) or {}
                    cells.append(f'{x.get("flipped_90", "-")} ({x.get("flipped_90_rim", "-")} / {x.get("flipped_90_away", "-")})')
            cap = b.get('cap_m')
            H.append(f'<tr><td>{e(n)}</td><td>{1e3 * a.get("shell_m", 0):.2f}</td><td>{"-" if not cap else "%.2f" % (1e3 * cap)}'
                     '</td>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>')
        H.append('</table>')
    # per board numbers
    H.append('<h2>Per board (EEVEE, the render box)</h2><table><tr><th>board</th><th>mean diff lv</th><th>&gt;8 lv</th>'
             '<th>silhouette IoU</th><th>xor px</th><th>outline move px</th><th>ink mean width before / after px</th>'
             '<th>ink area before / after px</th></tr>')
    for nm, b in rep['boards'].items():
        s, ln = b['silhouette'], b['lines']
        H.append(f'<tr><td><a href="#{nm}">{nm}</a></td><td>{b["diff"]["mean"]:.3f}</td><td>{100 * b["diff"]["over8"]:.3f}%'
                 f'</td><td>{s["iou"]:.5f}</td><td>{s["xor_px"]}</td><td>{s["grow_px"]:+.3f}</td>'
                 f'<td>{ln["before"]} / {ln["after"]}</td><td>{ln["ink_px_before"]} / {ln["ink_px_after"]}</td></tr>')
    H.append('</table>')
    if rep.get('pieces'):
        P = rep['pieces']
        obs = sorted({o for r in P.values() for o in r})
        H.append('<h3>Per piece: the mean move of its own silhouette (px), before to after; and the share of its '
                 'silhouette\'s edge its line draws, before &rarr; after</h3>')
        H.append('<table><tr><th>piece</th>' + ''.join(f'<th>{e(nm)}</th>' for nm in P) + '</tr>')
        pct = lambda x: '-' if x is None else '%.0f%%' % (100 * x)
        for o in obs:
            H.append(f'<tr><td>{e(o)}</td>' + ''.join(
                f'<td>{P[nm][o]["grow_px"]:+.2f} &middot; {pct(P[nm][o].get("edge_ink_before"))}&rarr;'
                f'{pct(P[nm][o].get("edge_ink_after"))}</td>' if o in P[nm] else '<td>-</td>' for nm in P) + '</tr>')
        H.append('</table>')
    cm = rep.get('compare') or {}
    if cm:
        H.append('<h2>charkit.render against EEVEE (the render box)</h2><table><tr><th>board</th>'
                 + ''.join(f'<th>{ph}: mean</th><th>{ph}: streaks mean</th><th>{ph}: IoU</th><th>{ph}: tones</th>'
                           for ph in cm) + '</tr>')
        bn = list(next(iter(cm.values()))['boards'])
        for nm in bn:
            cells = []
            for ph, c in cm.items():
                m = (c['boards'].get(nm) or {}).get('metrics') or {}
                ds = m.get('diff_streaks') or {}
                cells += [f'{m.get("diff", {}).get("mean", 0):.3f}', '-' if 'mean' not in ds else f'{ds["mean"]:.2f}',
                          f'{m.get("silhouette", {}).get("iou", 0):.4f}', f'{(m.get("tones") or {}).get("agree", 0):.5f}']
            H.append(f'<tr><td>{nm}</td>' + ''.join(f'<td>{x}</td>' for x in cells) + '</tr>')
        H.append('</table>')
    # close-ups
    if rep.get('crops'):
        H.append('<h2>Close-ups (x4, nearest)</h2>')
        for cn, c in rep['crops'].items():
            H.append(f'<div class="board"><b>{e(cn)}</b> <span class="mute">{e(c["board"])} {c["box"]}</span><div class="row">')
            for k, f in c['files'].items():
                H.append(_fig(f, k))
            H.append('</div></div>')
    # boards
    H.append('<h2>Boards: before | after | difference</h2>')
    H.append(f'<p class="mute">{e(compare_legend())}</p>')
    for nm, b in rep['boards'].items():
        s = b['silhouette']
        H.append(f'<div class="board" id="{nm}"><b>{nm}</b> <span class="mute">mean {b["diff"]["mean"]:.3f} lv, &gt;8 '
                 f'{100 * b["diff"]["over8"]:.3f}%, silhouette IoU {s["iou"]:.5f}, outline move {s["grow_px"]:+.3f} px'
                 f'</span><div class="row big">')
        for k in ('before', 'after', 'diff'):
            H.append(_fig(f'{k}/{nm}.png', {'before': 'EEVEE before', 'after': 'EEVEE after', 'diff': 'difference'}[k]))
        H.append('</div></div>')
    H.append('</body></html>')
    p = os.path.join(out, 'index.html')
    open(p, 'w').write('\n'.join(H))
    return p


def compare_legend():
    from charkit.render import page as rp
    return rp.LEGEND


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], '--open' in a)
