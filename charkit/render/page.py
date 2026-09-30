"""The review page for a comparison (charkit.render compare): per board EEVEE | ours | the difference heatmap at the
same scale, each labelled with its numbers, the files linked; the summary tables above. One local HTML file.

    python -m charkit.render page OUT          # OUT/compare.json -> OUT/index.html
"""
import html, json, os

LEGEND = ('difference per pixel, largest channel in 8-bit levels: black 0, blue 4-8, yellow 24, red 64, white 160+')


def _f(x, nd=3):
    return '-' if x is None else (f'{x:.{nd}f}' if isinstance(x, float) else str(x))


def write(out):
    C = json.load(open(os.path.join(out, 'compare.json')))
    B = C['boards']
    e = html.escape
    H = ['<!doctype html><html><head><meta charset="utf-8"><title>Toon renderer vs EEVEE</title><style>',
         ':root{--bg:#f4f4f6;--fg:#1d1d22;--mute:#6a6a75;--card:#fff;--line:#dcdce3}',
         '@media (prefers-color-scheme:dark){:root{--bg:#16161a;--fg:#e8e8ee;--mute:#9a9aa6;--card:#202027;--line:#34343d}}',
         'body{background:var(--bg);color:var(--fg);font:14px/1.45 -apple-system,system-ui,sans-serif;margin:0;padding:16px 24px}',
         'h1{font-size:20px;margin:4px 0 2px}h2{font-size:16px;margin:22px 0 8px}.mute{color:var(--mute)}',
         'table{border-collapse:collapse;background:var(--card);font-variant-numeric:tabular-nums}',
         'td,th{border:1px solid var(--line);padding:4px 8px;text-align:right}th{text-align:center}td:first-child{text-align:left}',
         '.board{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:10px;margin:14px 0}',
         '.row{display:flex;gap:8px;overflow-x:auto}.row figure{margin:0}.row img{display:block;height:min(62vh,640px);'
         'image-rendering:pixelated;border:1px solid var(--line)}figcaption{font-size:12px;color:var(--mute);margin-top:3px}',
         'code{font-size:12px}</style></head><body>']
    H.append('<h1>charkit toon renderer against EEVEE</h1>')
    H.append(f'<div class="mute">build <code>{e(C["build"])}</code> &middot; export <code>{e(os.path.basename(C["vrm"]))}'
             f'</code> &middot; ours on {e(str(C["adapter"].get("device")))} ({e(str(C["adapter"].get("backend")))}), '
             f'ss {C["settings"]["ss"]}, film sigma {C["settings"]["sigma"]:.3f} px, streak hash {e(C["settings"]["hash"])}'
             f' &middot; {e(C.get("created", ""))}</div>')
    H.append(f'<p class="mute">{e(LEGEND)}. "Excl. streaks": the hair streaks of either picture left out (their placement '
             f'is a hash of sin() that differs between GPUs; see the notes). Silhouette: pixels farther than 6 levels from '
             f'the background. Lines: dark ink (luma under 70); mean width from its coverage. Tones: pixels within 6 levels '
             f'of a palette colour, classified by the nearest.</p>')
    H.append('<h2>Per board</h2><table><tr><th>board</th><th>max</th><th>mean</th><th>p99</th><th>&gt;8 lv</th>'
             '<th>mean excl. streaks</th><th>&gt;8 excl.</th><th>silhouette IoU</th><th>xor px</th>'
             '<th>line width EEVEE / ours (px)</th><th>ink ratio</th><th>tone agree</th><th>classified</th>'
             '<th>ours s</th></tr>')
    for n, b in B.items():
        m = b['metrics']; d, dx = m['diff'], m.get('diff_excl', m['diff'])
        ln, tn = m['lines'], m.get('tones', {})
        H.append(f'<tr><td><a href="#{n}">{n}</a></td><td>{d["max"]}</td><td>{d["mean"]:.3f}</td><td>{d["p99"]}</td>'
                 f'<td>{100 * d["over8"]:.3f}%</td><td>{dx["mean"]:.3f}</td><td>{100 * dx["over8"]:.3f}%</td>'
                 f'<td>{m["silhouette"]["iou"]:.4f}</td><td>{m["silhouette"]["xor_px"]}</td>'
                 f'<td>{_f(ln["eevee"].get("mean_width"))} / {_f(ln["ours"].get("mean_width"))}</td>'
                 f'<td>{_f(ln.get("ink_ratio"))}</td><td>{_f(tn.get("agree"), 4)}</td>'
                 f'<td>{_f(tn.get("classified_share"), 3)}</td><td>{_f(b.get("seconds"), 3)}</td></tr>')
    H.append('</table>')
    if C.get('speed'):
        H.append('<h2>Speed (seconds per board)</h2><table><tr><th>what</th><th>where</th><th>s / board</th><th>note</th></tr>')
        for s in C['speed']:
            H.append(f'<tr><td>{e(s["what"])}</td><td>{e(s["where"])}</td><td>{_f(s["s_per_board"], 3)}</td>'
                     f'<td>{e(s.get("note", ""))}</td></tr>')
        H.append('</table>')
    if C.get('machines'):
        H.append('<h2>Ours across machines (against the render on this page)</h2><table><tr><th>boards from</th>'
                 '<th>adapter</th><th>boards</th><th>pixels identical (min / mean)</th><th>max diff</th></tr>')
        for r in C['machines']:
            H.append(f'<tr><td>{e(r["dir"])}</td><td>{e(r["adapter"])}</td><td>{r["boards"]}</td>'
                     f'<td>{100 * r["identical_min"]:.3f}% / {100 * r["identical_mean"]:.3f}%</td><td>{r["max"]}</td></tr>')
        H.append('</table>')
    for n, b in B.items():
        m = b['metrics']; d = m['diff']
        H.append(f'<div class="board" id="{n}"><b>{n}</b> <span class="mute">{b["res"][0]} x {b["res"][1]} &middot; '
                 f'max {d["max"]}, mean {d["mean"]:.3f}, &gt;8 levels {100 * d["over8"]:.3f}% &middot; silhouette IoU '
                 f'{m["silhouette"]["iou"]:.4f} &middot; tones agree {_f(m.get("tones", {}).get("agree"), 4)}</span>')
        H.append('<div class="row">')
        for k, cap in (('eevee', 'EEVEE (the build\'s board)'), ('ours', f'ours ({b.get("seconds", 0):.3f} s)'),
                       ('diff', 'difference')):
            p = b['files'][k]
            H.append(f'<figure><a href="{e(p)}"><img src="{e(p)}" alt="{n} {k}"></a><figcaption>{e(cap)} &middot; '
                     f'<a href="{e(p)}">{e(os.path.basename(p))}</a></figcaption></figure>')
        H.append('</div></div>')
    if C.get('notes'):
        H.append('<h2>Notes</h2><ul>' + ''.join(f'<li>{e(x)}</li>' for x in C['notes']) + '</ul>')
    H.append('</body></html>')
    p = os.path.join(out, 'index.html')
    open(p, 'w').write('\n'.join(H))
    return p
