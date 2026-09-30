"""The pilots' review page: one local HTML page (Michael's rule: review in the browser), everything compared side by side
at matching scale and labelled with its numbers.

    python -m charkit.sim review BUILD REST_DIR MOTION_DIR OUT_DIR

Rest drape: per variant the skirt QA's own picture (charkit.skirtqa.picture: the drawing and ours per view, the flaps
tinted, the drawn flaps' outlines on ours) from the spliced bundle, with the variant's checks. Motion: per pose the end
frame of every method, rendered front, her left side and back at one framing (the skin grey, the skirt orange, the flaps
blue and green; red where a garment's surface is newly inside the skin), with its penetration, stretch and departure.
"""
import html, json, os, shutil

import numpy as np

VIEWS = ((0, 'front'), (90, 'her left'), (180, 'back'))
KEY_CHECKS = ('piece_overskirt_panel_L', 'piece_overskirt_panel_R', 'piece_skirt', 'flap_back_iou_L', 'flap_back_iou_R',
              'flap_profile_iou_L', 'flap_profile_iou_R', 'flap_front_iou_L', 'flap_front_iou_R', 'flap_profile_hang_L',
              'flap_profile_clear_L', 'flap_profile_sweep_L', 'flap_back_hang_L', 'body_front_hem', 'body_back_hem',
              'body_profile_hem', 'body_three_quarter_hem_mid', 'skirt_back_outline', 'poke_share')


def _cell(c):
    if not c:
        return '<td>—</td>'
    v = c.get('value')
    st = c.get('status') or ''
    vs = ('%.4g' % v) if isinstance(v, (int, float)) else html.escape(str(v))
    return '<td class="%s">%s <small>%s</small></td>' % (st.lower(), vs, st)


def rest_section(build, rest_dir, out, log=print):
    from .. import qa3d, skirtqa
    from . import drape
    rep = json.load(open(os.path.join(rest_dir, 'rest.json')))
    Bd = drape.Build(build)
    V = rep['variants']
    pics = {}
    for vn in V:
        B = Bd.B if vn == 'template' else drape.splice(Bd, dict(np.load(os.path.join(rest_dir, 'rest_%s.npz' % vn))))
        d = os.path.join(out, 'rest_%s' % vn)
        os.makedirs(d, exist_ok=True)
        skirtqa.measure(B, qa3d.Design(B), d)
        pics[vn] = 'rest_%s/qa_skirt.png' % vn
        log('rest picture', vn)
    counts = {v: {st: sum(1 for c in V[v]['checks'].values() if c.get('status') == st) for st in ('PASS', 'WARN', 'FAIL')}
              for v in V}
    H = ['<h2>Rest drape: the flaps settled, against the template</h2>',
         '<p>Build <code>%s</code>. Each variant settles both flaps (on their cages, against signed-distance grids of '
         'the skin, the skirt and the shorts), splices them through the build\'s own finalize into its bundle and runs '
         'its QA parts (%s: %d checks). <b>template</b> is the build as it is.</p>' % (
             html.escape(build), ', '.join(rep['parts']), len(V['template']['checks'])),
         '<table><tr><th>check</th>' + ''.join('<th>%s</th>' % v for v in V) + '</tr>',
         '<tr><td>PASS / WARN / FAIL</td>' + ''.join('<td>%d / %d / %d</td>' % (counts[v]['PASS'], counts[v]['WARN'],
                                                                               counts[v]['FAIL']) for v in V) + '</tr>',
         '<tr><td>settings</td>' + ''.join('<td><small>%s</small></td>' % html.escape(
             '%s, %s %s' % (V[v].get('style', ''), V[v].get('rest', ''), V[v].get('dials') or '')) if v != 'template'
             else '<td></td>' for v in V) + '</tr>',
         '<tr><td>moved max / mean (L)</td>' + ''.join('<td></td>' if v == 'template' else '<td>%s</td>' % '<br>'.join(
             '%s %.3f / %.3f' % (n[-1], s['moved_max_L'], s['moved_mean_L']) for n, s in V[v]['stats'].items())
             for v in V) + '</tr>']
    for k in KEY_CHECKS:
        H.append('<tr><td>%s</td>%s</tr>' % (k, ''.join(_cell(V[v]['checks'].get(k)) for v in V)))
    H.append('</table>')
    H.append('<p>Every check that moves is in <a href="%s">rest.md</a>; the numbers in <a href="%s">rest.json</a>.</p>' % (
        os.path.relpath(os.path.join(rest_dir, 'rest.md'), out), os.path.relpath(os.path.join(rest_dir, 'rest.json'),
                                                                                  out)))
    H.append('<h3>The skirt QA\'s picture per variant (the drawing | ours, per view: back, three-quarter, profile, '
             'front; flaps tinted, the drawn flaps\' outlines in white on ours)</h3>')
    for vn in V:
        H.append('<figure><figcaption><b>%s</b>: flap IoU back %s / %s, profile %s / %s; PASS/WARN/FAIL %d/%d/%d'
                 '</figcaption><img src="%s"></figure>' % (
                     vn, *(('%.3f' % (V[vn]['checks'].get(k) or {}).get('value', float('nan')))
                           for k in ('flap_back_iou_L', 'flap_back_iou_R', 'flap_profile_iou_L', 'flap_profile_iou_R')),
                     counts[vn]['PASS'], counts[vn]['WARN'], counts[vn]['FAIL'], pics[vn]))
    return '\n'.join(H)


def motion_section(build, motion_dir, out, log=print):
    from ..evalmesh import POSES
    from ..geom import raster
    from . import motion as mo, rig as riglib
    rep = json.load(open(os.path.join(motion_dir, 'motion.json')))
    S = mo.Scene(build, log=log)
    cols = {'skirt': (0.93, 0.55, 0.25), 'overskirt_panel_L': (0.35, 0.5, 0.95), 'overskirt_panel_R': (0.35, 0.8, 0.45)}
    tris = {n: None for n in mo.PIECES}
    for n in mo.PIECES:
        F = S.fin[n]
        from .drape import _fan
        tris[n] = _fan(F['loopv'], F['counts'])
    H = ['<h2>Motion: the skirt and the flaps at the leg poses</h2>',
         '<p>Build <code>%s</code>, %d fps: 1 s settled at rest, into the pose over %.1f s, held %.1f s. Each image is '
         'the end frame at one framing per pose (front, her left side, back). Grey the skin, orange the skirt, blue and '
         'green the flaps; <b style="color:#d00">red</b> where a garment\'s surface is newly inside the skin (not '
         'inside at rest as shipped). Capsule colliders fitted to the skin: %s. Numbers per piece: new inside share and '
         'depth (L) at the end, the worst over the motion, coarse stretch p99 / max, departure from the skinned '
         'result (L).</p>' % (html.escape(build), rep['fps'], rep['ramp'], rep['hold'], ', '.join(
             '%s r %.3f L' % (c['name'], c['r'] / rep['L']) for c in rep['capsules']))]
    for pose, M in rep['poses'].items():
        D = S.rig.skinning(POSES[pose], 1.0)
        Xs = riglib.lbs(S.skin_V, S.skin_W, D)
        ends = {m: dict(np.load(os.path.join(motion_dir, 'end_%s_%s.npz' % (pose, m)))) for m in M}
        allV = [Xs] + [ends[m][n] for m in M for n in mo.PIECES]
        lo = np.min([v.min(0) for v in allV], 0)
        hi = np.max([v.max(0) for v in allV], 0)
        lo[2] = max(lo[2], S.skin_V[:, 2].min())
        fr = raster.Frame.around([(np.array([lo, hi]), np.zeros((0, 3), int))], res=300, aspect=0.8)
        H.append('<h3>%s</h3><table class="grid"><tr><th>method</th>%s<th>numbers</th></tr>' % (
            pose, ''.join('<th>%s</th>' % v for _, v in VIEWS)))
        dd = S._inside(D, {n: ends[m_][n] for n in mo.PIECES for m_ in [list(M)[0]]})
        for m in M:
            new = S._inside(D, ends[m])
            items = [((Xs, S.skin_F), dict(color=(0.78, 0.78, 0.8), shade='lambert'))]
            for n in mo.PIECES:
                C = np.tile(np.array(cols[n]), (len(ends[m][n]), 1))
                surf = np.nonzero(S.surf[n])[0]
                bad = (new[n] < 0) & (S.rest_inside[n] >= 0)
                C[surf[bad]] = (0.85, 0.0, 0.0)
                items.append(((ends[m][n], tris[n]), dict(color=C, shade='lambert')))
            cells = []
            for az, vn in VIEWS:
                img = raster.render(items, az, fr)
                p = 'motion_%s_%s_%d.png' % (pose, m, az)
                raster.save_png(img, os.path.join(out, p))
                cells.append('<td><img src="%s"></td>' % p)
            fr_ = M[m]['frames']
            nums = []
            for n in mo.PIECES:
                e = fr_[-1]['pieces'][n]
                ws = max(x['pieces'][n]['new_share'] for x in fr_)
                wd = max(x['pieces'][n]['new_depth'] for x in fr_)
                dep = fr_[-1].get('departure_mean', {}).get(n)
                nums.append('%s: end %.3f / %.3f L, worst %.3f / %.3f L, stretch %.3f / %.2f%s' % (
                    n.replace('overskirt_panel_', 'flap '), e['new_share'], e['new_depth'], ws, wd, e['stretch_p99'],
                    e['stretch_max'], '' if dep is None else ', departs %.3f L' % dep))
            H.append('<tr><td><b>%s</b></td>%s<td><small>%s</small></td></tr>' % (m, ''.join(cells), '<br>'.join(nums)))
            log('motion pictures', pose, m)
        H.append('</table>')
    H.append('<p>The numbers: <a href="%s">motion.md</a>, <a href="%s">motion.json</a>.</p>' % (
        os.path.relpath(os.path.join(motion_dir, 'motion.md'), out), os.path.relpath(os.path.join(motion_dir,
                                                                                                  'motion.json'), out)))
    return '\n'.join(H)


CSS = '''body{font:14px/1.45 -apple-system,Helvetica,sans-serif;margin:20px;max-width:1500px;color:#222;background:#fff}
table{border-collapse:collapse;margin:8px 0}td,th{border:1px solid #ccc;padding:3px 6px;vertical-align:top}
td.pass{background:#e6f5e6}td.warn{background:#fff3d6}td.fail{background:#fbe0e0}img{max-width:100%;display:block}
figure{margin:12px 0}figcaption{margin:4px 0}.grid img{width:240px}code{background:#f3f3f3;padding:0 3px}'''


def page(build, rest_dir, motion_dir, out, intro='', log=print):
    os.makedirs(out, exist_ok=True)
    parts = ['<!doctype html><meta charset="utf-8"><title>XPBD pilot</title><style>%s</style>' % CSS,
             '<h1>XPBD cloth pilot: the flaps and the skirt against the templates and the spring chains</h1>', intro]
    if rest_dir:
        parts.append(rest_section(build, rest_dir, out, log))
    if motion_dir:
        parts.append(motion_section(build, motion_dir, out, log))
    p = os.path.join(out, 'index.html')
    open(p, 'w').write('\n'.join(parts))
    return p


def main(a):
    intro = open(a[4]).read() if len(a) > 4 else ''
    print(page(a[0], a[1] if a[1] != '-' else None, a[2] if a[2] != '-' else None, a[3], intro))
    return 0
