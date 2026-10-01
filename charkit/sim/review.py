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


# ------------------------------------------------------------------------------------------------------------ round 2
NAMES = {'skinned': 'skinned, as shipped', 'xpbd_hips_r1': 'cloth held on the pelvis, round 1 (pins on the skirt\'s '
         'own weights)', 'xpbd_hips': 'cloth held toward the drawn shape on the pelvis, pins on the skin (the anime '
         'default)', 'xpbd_physics': 'cloth, no hold (the realistic default)', 'springs_body': 'spring chains, the '
         'graph\'s settings', 'springs_tuned': 'spring chains tuned to the cloth, roots on the hips',
         'springs_tuned_skin': 'spring chains tuned to the cloth, roots riding the skin', 'pelvis_rigid': 'carried by the '
         'pelvis alone (known-bad)', 'springs_col': 'spring chains, graph settings, leg colliders'}


def _worst(M, m, n='skirt'):
    fr = M[m]['frames']
    return dict(inside=max(x['pieces'][n]['new_share'] for x in fr), depth=max(x['pieces'][n]['new_depth'] for x in fr),
                stretch=max(x['pieces'][n]['stretch_p99'] for x in fr))


def summary_box(rep, recs, tune, rec_text, ask):
    P = rep['poses']
    ms = [m for m in next(iter(P.values()))]
    H = ['<div class="box"><p><b>Recommended:</b> %s</p><p><b>Asked of Michael:</b></p><ol>%s</ol>' % (
        rec_text, ''.join('<li>%s</li>' % a for a in ask)),
         '<p><b>Key numbers</b> (the skirt, worst over the motion: the share of its surface newly inside the skin, its '
         'depth, the coarse stretch p99; the gated checks PASS at inside &le; 0.01, stretch &le; 0.25):</p>',
         '<table><tr><th>option</th>' + ''.join('<th>%s inside</th><th>%s depth (L)</th><th>%s stretch</th>' % (p, p, p)
                                                for p in P) + '</tr>']
    for m in ms:
        cells = []
        for p in P:
            w = _worst(P[p], m)
            cells += ['<td class="%s">%.3f</td>' % ('pass' if w['inside'] <= 0.01 else 'warn' if w['inside'] <= 0.03
                                                    else 'fail', w['inside']), '<td>%.3f</td>' % w['depth'],
                      '<td class="%s">%.2f</td>' % ('pass' if w['stretch'] <= 0.25 else 'warn' if w['stretch'] <= 0.5
                                                    else 'fail', w['stretch'])]
        H.append('<tr><td>%s <small><code>%s</code></small></td>%s</tr>' % (NAMES.get(m, m), m, ''.join(cells)))
    H.append('</table></div>')
    return '\n'.join(H)


def calib_section(recs):
    if not recs:
        return '<h2>Calibration</h2><p>No records yet.</p>'
    H = ['<h2>The motion checks and their calibration</h2>', '<p>Each check must PASS on the held solve with one '
         'nuisance setting nudged per move (substeps 16/24, ramp 0.35/0.45 s, 3 iterations, colliders +0.005 L, hold '
         '&plusmn;0.05) and FAIL on its known-bad (computed from the same build). Records: '
         '<code>charkit/calib/records/motion_*.json</code>.</p>',
         '<table><tr><th>check</th><th>verdict</th><th>design (nudged) min..max</th><th>known-bad</th>'
         '<th>floor (a random rig: the skirt\'s weights shuffled)</th><th>current</th></tr>']
    for k, r in sorted(recs.items()):
        D, K, C = r.get('design') or {}, r.get('known_bad') or {}, r.get('current') or {}
        fl = '; '.join('%s median %s (%d of %d seeds PASS)' % (g, _f(f.get('median')), f.get('passing', 0),
                                                                 len(f.get('values') or ())) for g, f in
                       (r.get('floor') or {}).items()) or '—'
        H.append('<tr><td>%s</td><td class="%s">%s</td><td>%s..%s</td><td>%s %s <b>%s</b></td><td>%s</td>'
                 '<td>%s %s</td></tr>' % (
            k, 'pass' if r['verdict'] in ('calibrated', 'guard') else 'fail', r['verdict'], _f(D.get('min')),
            _f(D.get('max')), K.get('name'), _f(K.get('value')), K.get('status'), fl, _f(C.get('value')),
            C.get('status')))
    H.append('</table>')
    return '\n'.join(H)


def _f(x):
    return ('%.4g' % x) if isinstance(x, (int, float)) and not isinstance(x, bool) else str(x)


def tune_section(tune, out):
    if not tune:
        return ''
    H = ['<h2>The spring chains tuned to the cloth (real-time VRM)</h2>',
         '<p>Reference: %s through %s. Each chain joint follows the cloth point it starts on; the error is the joints\' '
         'mean distance from those points (L) over the motion after the settle, settled at rest, and at the end, '
         'averaged over the poses. Colliders (VRM capsules, shrunk to clear the chains\' rest joints): %s.</p>' % (
             tune['ref'], ', '.join(tune['poses']), ', '.join('%s %.3f' % (c['name'], c['r_L']) for c in tune['caps'])),
         '<table><tr><th>piece</th><th>settings</th><th>stiffness</th><th>gravity</th><th>drag</th><th>err motion</th>'
         '<th>err rest</th><th>err end</th>' + ''.join('<th>%s: rest inside / worst / depth / stretch</th>' % p
                                                       for p in tune['poses']) + '</tr>']
    for n, r in tune['pieces'].items():
        for k, g in (('graph', 'graph'), ('best', 'tuned')):
            if k not in r:
                continue
            x = r[k]
            gm = r.get('garment', {}).get(g, {})
            H.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%.3f</td><td>%.3f</td><td>%.3f</td>%s'
                     '</tr>' % (n, g, x['stiffness'], x['gravity'], x['drag'], x['err_motion'], x['err_rest'],
                                x['err_end'], ''.join('<td>%.3f / %.3f / %.3f / %.2f</td>' % (
                                    gm[p]['rest_inside'], gm[p]['worst_inside'], gm[p]['worst_depth'],
                                    gm[p]['worst_stretch']) if p in gm else '<td></td>' for p in tune['poses'])))
    H.append('</table>')
    return '\n'.join(H)


def bake_section(build, cache, out, frames=None, log=print):
    from ..geom import raster
    from . import bake as bk, motion as mo, rig as riglib
    from .drape import _fan
    if not cache or not os.path.exists(os.path.join(cache, 'cloth.json')):
        return ''
    man, X, bones = bk.load(cache)
    rp = os.path.join(cache, 'replay.json')
    replay = json.load(open(rp)) if os.path.exists(rp) else None
    files = sorted(os.listdir(cache))
    sizes = ', '.join('%s %.1f MB' % (f, os.path.getsize(os.path.join(cache, f)) / 1e6) for f in files)
    frames = frames or [man['first'] - 1, man['first'] + 12, man['first'] + 24, man['frames'] - 1]
    S = mo.Scene(build, pieces=list(man['pieces']), log=log)
    fin = bk.finals(build, cache, frames)
    cols = {'skirt': (0.93, 0.55, 0.25)}
    allV, items_by = [], {}
    for k in frames:
        D = {b: bones[b][k].astype(float) for b in bones}
        Xs = riglib.lbs(S.skin_V, S.skin_W, D)
        items = [((Xs, S.skin_F), dict(color=(0.78, 0.78, 0.8), shade='lambert'))]
        for n in man['pieces']:
            F = S.fin[n]
            items.append(((fin[k][n], _fan(F['loopv'], F['counts'])),
                          dict(color=cols.get(n, (0.35, 0.5, 0.95) if n.endswith('L') else (0.35, 0.8, 0.45)),
                               shade='lambert')))
        items_by[k] = items
        allV += [Xs] + [fin[k][n] for n in man['pieces']]
    lo, hi = np.min([v.min(0) for v in allV], 0), np.max([v.max(0) for v in allV], 0)
    fr = raster.Frame.around([(np.array([lo, hi]), np.zeros((0, 3), int))], res=260, aspect=0.8)
    cells = []
    for k in frames:
        for az in (0, 90):
            img = raster.render(items_by[k], az, fr)
            p = 'bake_%s_%d_%d.png' % (man['clip'], k, az)
            raster.save_png(img, os.path.join(out, p))
            cells.append('<td><img src="%s"><small>frame %d (%s), %s</small></td>' % (
                p, k, 'settled' if k < man['first'] else '%+.2f s' % ((k - man['first'] + 1) / man['fps']),
                'front' if az == 0 else 'her left'))
    meas = man['measures'][-1]
    H = ['<h2>The bake: cloth caches for rendered shots (pilot: the kick)</h2>',
         '<p><code>%s</code>: %s. %d frames at %d fps (the first %d the settle, pre-roll), method <b>%s</b> (hold %s, '
         'style %s), %.0f s to bake. Pieces: %s. The render mesh is the build\'s own finalize of the cached coarse '
         'positions; the PC2 caches hold that render mesh per frame (the build\'s objects hold the finalized mesh: '
         'Blender\'s Mesh Cache modifier first in the stack, Armature off, the outline following).</p>' % (
             html.escape(os.path.relpath(cache, out)), sizes, man['frames'], man['fps'], man['first'], man['method'],
             man['hold_shape'], man['style'], man['seconds'], ', '.join('%s (%d coarse, %d render vertices)' % (
                 n, p['coarse'], p['final']) for n, p in man['pieces'].items())),
         '<p>Measured as it baked (the last frame): %s.</p>' % '; '.join(
             '%s new inside %.3f at %.3f L, stretch p99 %.3f' % (n, meas[n]['new_share'], meas[n]['new_depth'],
                                                                   meas[n]['stretch_p99']) for n in man['pieces']),
         '<p>The replay (Blender\'s Mesh Cache against our finalize, max vertex distance in L per frame): %s</p>' % (
             html.escape(json.dumps(replay)) if replay else 'not run'),
         '<table class="grid"><tr>%s</tr></table>' % ''.join(cells)]
    return '\n'.join(H)


def page2(build, motion_dir, out, tune_dir=None, cache=None, rec_text='', ask=(), extra='', log=print):
    """round 2's page: the summary box, the motion pictures (every method's end frame per pose at one framing), the
    calibration, the bake, the spring tuning."""
    import glob
    os.makedirs(out, exist_ok=True)
    rep = json.load(open(os.path.join(motion_dir, 'motion.json')))
    recs = {}
    for p in glob.glob(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                    'charkit', 'calib', 'records', 'motion_*.json')):
        r = json.load(open(p))
        recs[r['check']] = r
    tune = json.load(open(os.path.join(tune_dir, 'tune.json'))) if tune_dir else None
    css = CSS + '.box{border:2px solid #333;padding:8px 14px;margin:10px 0 18px;background:#fafafa}'
    parts = ['<!doctype html><meta charset="utf-8"><title>XPBD round 2</title><style>%s</style>' % css,
             '<h1>The skirt in motion: cloth held toward the drawn shape, the squat, the checks, the bake, the chains</h1>',
             summary_box(rep, recs, tune, rec_text, ask), extra, calib_section(recs),
             motion_section(build, motion_dir, out, log), bake_section(build, cache, out, log=log),
             tune_section(tune, out)]
    p = os.path.join(out, 'index.html')
    open(p, 'w').write('\n'.join(parts))
    return p


# ------------------------------------------------------------------------------------------------------------ round 3
WAIST_NAMES = {'hips': 'rigid on the hips (as built)', 'body': "the body's weights per vertex (shipped)",
               'body_cols': "the body's, each column one blend", 'body_mean': "the body's, one blend for the band"}


def waist_section(waist_dir, out):
    """the waistband's weights: the numbers per pose and variant, and the pictures (charkit.sim.waist)."""
    W = json.load(open(os.path.join(waist_dir, 'waist.json')))
    H = ['<h2>1. The waistband takes the body\'s weights near the waist</h2>',
         '<p>The band sits across the spine/chest joint (joint heights above its bottom edge, L: %s); the skin under it '
         'is weighted %s by row, top to bottom, and not at all to the hips it was rigidly bound to. Per pose: the band\'s '
         'surface newly inside the posed skin (share / depth L), its coarse edge stretch p99, and the skirt\'s top '
         'that the band covers at rest and that shows posed (its ray out from the hips axis misses the band and the '
         'skin), for the cloth skirt (the anime default, pins on the skin) and the skinned one (VRM\'s real-time path). '
         'Rest geometry is unchanged by weights, so the band\'s shape IoU in every view is unchanged (the box build '
         'confirms it below).</p>' % (
             ', '.join('%s %+.2f' % kv for kv in W['joints_above_band_L'].items()),
             '; '.join('%s %s' % (b, '/'.join('%.2f' % x for x in r)) for b, r in W['weights_rows'].items())),
         '<table><tr><th>pose</th><th>weights</th><th>band inside</th><th>depth (L)</th><th>band stretch p99</th>'
         '<th>skirt top shows: cloth</th><th>skirt top shows: skinned</th></tr>']
    for pose, row in W['poses'].items():
        if all(v['new_inside'] == 0 and v.get('exposed_skinned', 0) == row['hips'].get('exposed_skinned', 0)
               for v in row.values()) and pose not in ('kick', 'split'):
            continue                                    # (the arm poses: nothing moves at the waist)
        for k, v in row.items():
            cls = lambda x, a, b: 'pass' if x <= a else 'warn' if x <= b else 'fail'
            H.append('<tr><td>%s</td><td>%s</td><td class="%s">%.3f</td><td>%.3f</td><td class="%s">%.2f</td>'
                     '<td>%s</td><td>%.3f</td></tr>' % (
                         pose, WAIST_NAMES.get(k, k), cls(v['new_inside'], 0.01, 0.03), v['new_inside'], v['depth'],
                         cls(v['stretch_p99'], 0.25, 0.5), v['stretch_p99'],
                         '%.3f' % v['exposed_cloth'] if 'exposed_cloth' in v else '—', v['exposed_skinned']))
    H.append('</table><p>Arm poses (arms up, elbows bent, arms crossed): nothing at the waist moves, 0 everywhere. '
             'The skin itself stretches 1.34 p99 under the band at twist_bend (LBS across the chest joint): the body\'s '
             'weights inherit it.</p>')
    for pose, cols in (W.get('pictures') or {}).items():
        H.append('<h3>%s, end of the pose</h3><p>Grey the skin, brown the band (<b style="color:#d00">red</b> where '
                 'newly inside the skin), orange the skirt (<b style="color:#c0c">magenta</b> where its top, under the '
                 'band at rest, now shows). Same framing in every image.</p><table class="grid"><tr><th>view</th>%s</tr>'
                 % pose + ''.join('<th>%s<br><small>skirt: %s</small></th>' % (WAIST_NAMES[c.split('/')[0]],
                                                                                'cloth (anime default)' if
                                                                                c.endswith('cloth') else 'skinned')
                                  for c in cols))
        for i, vn in enumerate(('front', 'her left')):
            H.append('<tr><td>%s</td>%s</tr>' % (vn, ''.join(
                '<td><img src="%s"></td>' % os.path.relpath(os.path.join(waist_dir, ps[i]), out) for ps in cols.values())))
        H.append('</table>')
    H.append('<p>Numbers: <a href="%s">waist.json</a>.</p>' % os.path.relpath(os.path.join(waist_dir, 'waist.json'), out))
    return '\n'.join(H)


def tune_compare(tunes, out):
    """the chain tunings side by side (roots on the hips, roots riding the skin): per piece the best of the grid and
    the garments on it."""
    H = ['<h2>4. The spring chains: roots on the skin, the stiffness grid past 8</h2>',
         '<p>Each tuning runs the grid (stiffness %s, gravity %s, drag %s) against the cloth (the anime default); the error '
         'is the chain joints\' mean distance from the cloth\'s points (L) over the motion. Then the garments ride the '
         'best chains and are measured as motion QA measures them (worst over the motion: new inside share / depth L / '
         'stretch p99; at rest settled: inside share).</p>' % tuple(
             '/'.join(str(x) for x in next(iter(tunes.values()))['grid'][k]) for k in ('stiffness', 'gravity', 'drag')),
         '<table><tr><th>piece</th><th>chain roots</th><th>settings</th><th>stiffness</th><th>gravity</th><th>drag</th>'
         '<th>err motion</th><th>err rest</th>%s</tr>' % ''.join(
             '<th>%s: rest / worst / depth / stretch</th>' % p for p in next(iter(tunes.values()))['poses'])]
    for n in next(iter(tunes.values()))['pieces']:
        for label, T in tunes.items():
            r = T['pieces'][n]
            for k, g in (('graph', 'graph'), ('best', 'tuned')):
                if k == 'graph' and label != next(iter(tunes)):
                    continue
                x = r[k]
                gm = r.get('garment', {}).get(g, {})
                H.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%.3f</td>'
                         '<td>%.3f</td>%s</tr>' % (
                             n, label if k == 'best' else 'the hips', g, x['stiffness'], x['gravity'], x['drag'],
                             x['err_motion'], x['err_rest'], ''.join(
                                 '<td>%.3f / %.3f / %.3f / %.2f</td>' % (gm[p]['rest_inside'], gm[p]['worst_inside'],
                                                                        gm[p]['worst_depth'], gm[p]['worst_stretch'])
                                 if p in gm else '<td></td>' for p in T['poses'])))
    H.append('</table>')
    return '\n'.join(H)


def page3(build, out, waist_dir, motion_dir=None, tunes=None, cache=None, box='', cpu='', log=print):
    """round 3's page: the summary box (box: its HTML), the waistband, the calibration, motion QA's CPU (cpu: HTML),
    the chains, the bake and its replay, the motion pictures."""
    import glob
    os.makedirs(out, exist_ok=True)
    recs = {}
    for p in glob.glob(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                    'charkit', 'calib', 'records', 'motion_*.json')):
        r = json.load(open(p))
        recs[r['check']] = r
    css = CSS + '.box{border:2px solid #333;padding:8px 14px;margin:10px 0 18px;background:#fafafa}'
    parts = ['<!doctype html><meta charset="utf-8"><title>XPBD round 3</title><style>%s</style>' % css,
             '<h1>Round 3: the waistband on the body, the motion checks calibrated, motion QA 5x cheaper, the replay, '
             'the chains on the skin</h1>', box, waist_section(waist_dir, out),
             calib_section(recs).replace('<h2>The motion checks', '<h2>2. The motion checks'), cpu,
             tune_compare(tunes, out) if tunes else '',
             bake_section(build, cache, out, log=log).replace('<h2>The bake', '<h2>5. The bake'),
             motion_section(build, motion_dir, out, log).replace('<h2>Motion', '<h2>6. Motion') if motion_dir else '']
    p = os.path.join(out, 'index.html')
    open(p, 'w').write('\n'.join(parts))
    return p
