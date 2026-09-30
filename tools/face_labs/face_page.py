"""The face workstream's review page: the eye region and the neck join, before (tool/body 849b9a7) and after (tool/face),
against the design at matching scale, with the numbers.

    python face_page.py BASE_BUILD AFTER_BUILD OUT_DIR [--renders BASE_R AFTER_R] [--lab LAB_DIR]
"""
import html, json, os, shutil, sys

import numpy as np

sys.path.insert(0, os.path.expanduser('~/animation-pipeline-face'))
from charkit import bundle as bl, eyepage, faceregion, qa3d, refcheck  # noqa: E402

args = sys.argv[1:]
opt = lambda k, n=1: args[args.index(k) + 1:args.index(k) + 1 + n] if k in args else None
BASE, AFTER, OUT = args[0], args[1], args[2]
R = opt('--renders', 2)
LAB = (opt('--lab') or [None])[0]
LABELS = opt('--labels', 2) or ['before', 'after']
IMG = os.path.join(OUT, 'img')
os.makedirs(IMG, exist_ok=True)
from PIL import Image  # noqa: E402


def save(a, name):
    a = np.asarray(a)
    if a.dtype != np.uint8:
        a = (np.clip(a, 0, 1) * 255).astype(np.uint8)
    if a.ndim == 3 and a.shape[2] == 4:                       # over the page's grey
        al = a[..., 3:4] / 255.0
        a = (a[..., :3] * al + 238 * (1 - al)).astype(np.uint8)
    Image.fromarray(a).save(os.path.join(IMG, name))
    return 'img/' + name


builds = {'before': bl.load(os.path.join(BASE, 'bundle')), 'after': bl.load(os.path.join(AFTER, 'bundle'))}
qa = {k: json.load(open(os.path.join(d, 'qa', 'qa.json')))['checks'] for k, d in (('before', BASE), ('after', AFTER))}
fr = {k: faceregion.measure(B) for k, B in builds.items()}

# ---------------------------------------------------------------- eyes at the QA's own scale: design | before | after
des, ppl = eyepage.design_eyes(builds['after'].spec)
Dz = qa3d.Design(builds['after'])
az3 = float(Dz.sheet_measures()[0].get('az_three_quarter', 35.0))
eye_rows = []
for view, az in (('front', 0.0), ('three_quarter', az3), ('profile', 90.0)):
    d = [px for side, px in des.get(view, []) if side == 'L']
    if not d:
        continue
    cells = [('design (head_turnaround)', save(d[0], 'eye_%s_design.png' % view), '')]
    for k, B in builds.items():
        im = qa3d.eye_image(B, 'L', ppl, ss=3, az=az)
        w = fr[k][1].get('eye_width_' + view, {})
        note = 'width %s L, %s x the design\'s (%s)' % (w.get('ours'), w.get('value'), w.get('status')) if w else ''
        cells.append((k, save(im, 'eye_%s_%s.png' % (view, k)), note))
    eye_rows.append((view, az, cells))

# ---------------------------------------------------------------- the design's heads, cut from the head sheet
M = __import__('charkit.manifest', fromlist=['x'])
spec = builds['after'].spec
rgb = refcheck._load(spec['ref']['face_sheet']['image'])
rgb0, _ = refcheck.without_guides(np.asarray(rgb, float))
ex = (spec.get('eyes') or {}).get('x', 0.168)
_, f, Hh = refcheck.at_scale(rgb0, ex, 2 * ex * refcheck.FACE_PPL, spec['ref']['face_sheet'].get('facing', -1))
own = refcheck.FACE_PPL / f
heads = {}
for view in ('front', 'three_quarter', 'profile'):
    h = Hh['heads'].get(view)
    if not h:
        continue
    x0, y0, x1, y1 = [v / f for v in h['box']]
    ey = h['eye_y'] / f
    cx = (x0 + x1) / 2
    half = 0.75 * own
    top, bot = int(ey - 0.85 * own), int(ey + 1.05 * own)
    crop = rgb0[max(0, top):bot, max(0, int(cx - half)):int(cx + half)]
    heads[view] = save(crop, 'design_head_%s.png' % view)

# ---------------------------------------------------------------- the eye region down the eye's column (the hollow)
import matplotlib  # noqa: E402
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
fig, axs = plt.subplots(1, 2, figsize=(10, 4.2))
for k, col in (('before', '#c0392b'), ('after', '#1f77b4')):
    for side, h in fr[k][0]['hollow'].items():
        if side != 'L' or not h['profile']:
            continue
        z, y = np.array(h['profile']).T
        y0 = np.interp(0, z[::-1], y[::-1])
        axs[0].plot(-(y - y0), z, color=col, label='%s (hollow %.3f, cheek lead %.3f L)' % (k, h['hollow'], h['cheek_lead']))
axs[0].axhline(0, color='#999', lw=0.6); axs[0].axvline(0, color='#999', lw=0.6)
axs[0].set_xlabel('forward of the eye\'s centre (L)'); axs[0].set_ylabel('height from the eye (L)')
axs[0].set_title('the face down the eye\'s column (side view of the section)'); axs[0].legend(fontsize=8)
for k, col in (('before', '#c0392b'), ('after', '#1f77b4')):
    E = fr[k][0]['profile_edge']
    if E:
        z, a, d = np.array(E['rows']).T
        axs[1].plot(a - d, z, color=col, label='%s (rms %.3f L)' % (k, E['rms']))
axs[1].axvline(0, color='#999', lw=0.6)
axs[1].set_xlabel('ours behind the design (L; the profile\'s front edge)'); axs[1].set_ylabel('height from the eye (L)')
axs[1].set_title('chin to chest in profile, against the body sheet'); axs[1].legend(fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(IMG, 'profiles.png'), dpi=110); plt.close(fig)

fig, ax = plt.subplots(figsize=(10, 3.4))
for k, col in (('before', '#c0392b'), ('after', '#1f77b4')):
    for key, ls in (('neck_crease', '-'), ('neck_crease_all', ':')):
        K = fr[k][0].get(key)
        if K:
            a = sorted(K['per'])
            ax.plot(a, [K['per'][x] for x in a], color=col, ls=ls, marker='o' if ls == '-' else None, ms=3,
                    label='%s, %s (max %.1f, median %.1f deg)' % (k, 'visible skin' if key == 'neck_crease' else 'whole skin', K['max'], K['median']))
ax.axhline(faceregion.CREASE[0], color='#070', lw=0.8, ls='--'); ax.axhline(faceregion.CREASE[1], color='#b60', lw=0.8, ls='--')
ax.set_xlabel('column round the neck (degrees from the front, + her left)'); ax.set_ylabel('sharpest bend (deg)')
ax.set_title('the join\'s crease per column (PASS under the green line, WARN under the orange)'); ax.legend(fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(IMG, 'crease.png'), dpi=110); plt.close(fig)

# ---------------------------------------------------------------- the page
css = ('body{font:14px/1.5 -apple-system,system-ui,sans-serif;margin:24px auto;background:#fafafa;color:#222;max-width:1400px;padding:0 16px}'
       'h2{font-size:19px;margin:34px 0 8px;border-bottom:1px solid #ddd;padding-bottom:4px}h3{font-size:15px;margin:18px 0 6px}'
       'table{border-collapse:collapse;font-size:13px;margin:6px 0}td,th{border:1px solid #ddd;padding:3px 8px;text-align:right}'
       'th{background:#f0f0f0}td:first-child,th:first-child{text-align:left}.PASS{color:#070}.WARN{color:#b60}.FAIL{color:#c00}'
       '.note{color:#555}.row{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-start}.cell{flex:1;min-width:200px}'
       '.cell img{width:100%;border:1px solid #ddd;background:#eee}.cap{font-size:12px;color:#444;margin-top:2px}'
       '.call{background:#fff8e6;border:1px solid #f0d890;padding:10px 14px;border-radius:6px;margin:10px 0}'
       'code{background:#f0f0f0;padding:0 3px;border-radius:3px}')
P = ['<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
     '<title>Face region review</title><style>%s</style>' % css,
     '<h1>The face region: the eye window and the neck join</h1>',
     '<p class="note">Before: %s. After: %s. Every number is measured on the assembled figure (charkit.faceregion, now a '
     'QA part) or by the build\'s own QA.</p>' % (html.escape(LABELS[0]), html.escape(LABELS[1]))]


def cls(s):
    return s if s in ('PASS', 'WARN', 'FAIL') else ''


P.append('<h2>Numbers</h2><table><tr><th>check</th><th>before</th><th>after</th><th>what it is</th></tr>')
what = {'eye_hollow': 'how far the eye sits behind the brow-to-cheek line down its column (L)',
        'cheek_lead': 'how far the cheek under the eye stands in front of it (L)',
        'eye_bowl': 'the deepest local hollow round the eye, 0.06 L across or down (L)',
        'eye_width_three_quarter': 'the eye opening\'s width in three-quarter, over the design\'s',
        'eye_width_profile': 'the eye opening\'s width in profile, over the design\'s',
        'profile_edge': 'the profile\'s front edge, chin to chest, against the body sheet (rms L)',
        'neck_crease_all': 'the same on the whole skin, under the garments too (INFO)',
        'neck_crease': 'the sharpest bend of the visible neck\'s outline at the join (deg)'}
keys = ['eye_hollow_L', 'cheek_lead_L', 'eye_bowl_L', 'eye_width_three_quarter', 'eye_width_profile', 'profile_edge', 'neck_crease',
        'neck_crease_all']
for k in keys:
    a, b = fr['before'][1].get(k, {}), fr['after'][1].get(k, {})
    w = next((v for p, v in what.items() if k.startswith(p)), '')
    P.append('<tr><td>%s</td><td class="%s">%s %s</td><td class="%s">%s %s</td><td class="note" style="text-align:left">%s</td></tr>'
             % (k, cls(a.get('status')), a.get('value'), a.get('status', ''), cls(b.get('status')), b.get('value'),
                b.get('status', ''), w))
for k in sorted(qa['after']):
    if not k.startswith(('eye_', 'sheet_', 'face_folds', 'face_mouth')):
        continue
    a, b = qa['before'].get(k, {}), qa['after'][k]
    if b.get('status') == 'INFO' and a.get('status') == 'INFO':
        continue
    P.append('<tr><td>%s</td><td class="%s">%s %s</td><td class="%s">%s %s</td><td class="note" style="text-align:left">the build\'s QA</td></tr>'
             % (k, cls(a.get('status')), a.get('value'), a.get('status', ''), cls(b.get('status')), b.get('value'), b.get('status', '')))
from collections import Counter  # noqa: E402
cnt = {k: Counter(v.get('status') for v in qa[k].values()) for k in qa}
P.append('<tr><td><b>whole QA</b> PASS / WARN / FAIL</td><td>%d / %d / %d</td><td>%d / %d / %d</td><td class="note" style="text-align:left">'
         'every check the build runs (the new face_region part not counted: it is new)</td></tr></table>'
         % (cnt['before']['PASS'], cnt['before']['WARN'], cnt['before']['FAIL'], cnt['after']['PASS'], cnt['after']['WARN'], cnt['after']['FAIL']))

BOARDS = [os.path.join(d, 'boards') for d in (BASE, AFTER)]
if all(os.path.isdir(b) for b in BOARDS):
    P.append('<h2>The face board</h2><p class="note">The build\'s own face board (its look, lights and camera), beside the '
             'head sheet\'s view. Before: %s. After: %s.</p>' % (html.escape(LABELS[0]), html.escape(LABELS[1])))
    for view, fn in (('front', 'face_000.png'), ('three_quarter', 'face_030.png'), ('profile', 'face_090.png')):
        P.append('<h3>%s</h3><div class="row">' % view.replace('_', '-'))
        if view in heads:
            P.append('<div class="cell"><img src="%s"><div class="cap">design (head_turnaround)</div></div>' % heads[view])
        for tag, b in zip(('before', 'after'), BOARDS):
            p = os.path.join(b, fn)
            if os.path.exists(p):
                dst = 'board_%s_%s' % (tag, fn)
                shutil.copy(p, os.path.join(IMG, dst))
                P.append('<div class="cell"><img src="img/%s"><div class="cap">%s (%s)</div></div>' % (dst, tag, fn))
        P.append('</div>')
if R:
    P.append('<h2>The face, hair hidden</h2><p class="note">From the builds\' saved scenes (charkit.qa.render_view, 85 mm, '
             'the boards\' lights), the hair hidden to show the face\'s own surface. (The hair in these ad-hoc renders '
             'lacks the boards\' hair pass: see the face board above for the finished look.)</p>')
    for view in ('front', 'three_quarter', 'profile'):
        P.append('<h3>%s</h3><div class="row">' % view.replace('_', '-'))
        if view in heads:
            P.append('<div class="cell"><img src="%s"><div class="cap">design (head_turnaround)</div></div>' % heads[view])
        for tag, d in zip(('before', 'after'), R):
            for hv in ('bare',):
                p = os.path.join(d, 'face_%s_%s.png' % (view, hv))
                if os.path.exists(p):
                    dst = 'face_%s_%s_%s.png' % (view, hv, tag)
                    shutil.copy(p, os.path.join(IMG, dst))
                    P.append('<div class="cell"><img src="img/%s"><div class="cap">%s, %s</div></div>' % (dst, tag, hv))
        P.append('</div>')

P.append('<h2>The eyes at the QA\'s scale</h2><p class="note">The QA\'s own eye renders (charkit.qa3d.eye_image) and the '
         'head sheet\'s eye cut the same way (charkit.eyepage), at the same pixels per L: her left eye.</p>')
for view, az, cells in eye_rows:
    P.append('<h3>%s (azimuth %.1f)</h3><div class="row">' % (view.replace('_', '-'), az))
    for lab, src, note in cells:
        P.append('<div class="cell" style="max-width:320px"><img src="%s"><div class="cap">%s %s</div></div>' % (src, lab, html.escape(note)))
    P.append('</div>')

P.append('<h2>The eye region and the chin-to-chest profile</h2><img src="img/profiles.png" style="max-width:100%">')

if R:
    P.append('<h2>The neck</h2><div class="row">')
    for view in ('front', 'three_quarter', 'profile'):
        for tag, d in zip(('before', 'after'), R):
            p = os.path.join(d, 'neck_%s_bare.png' % view)
            if os.path.exists(p):
                dst = 'neck_%s_%s.png' % (view, tag)
                shutil.copy(p, os.path.join(IMG, dst))
                P.append('<div class="cell" style="min-width:30%%"><img src="img/%s"><div class="cap">%s, %s (hair hidden)</div></div>' % (dst, view, tag))
    P.append('</div>')
P.append('<img src="img/crease.png" style="max-width:100%">')

if LAB:
    P.append('<h2>The head\'s sections, shaded before any build</h2><p class="note">A numpy z-buffer of the head sections '
             '(no eyes, no hair) lit by the boards\' key light: a two-tone toon ramp (left of each pair) and smooth Lambert '
             '(right), front, three-quarter and 70 degrees. The fast loop the eye region was designed in (seconds a try).</p>')
    for name, cap in (('shade_socket.png', 'the socket (before)'), ('shade_window.png', 'the window (after)')):
        p = os.path.join(LAB, name)
        if os.path.exists(p):
            shutil.copy(p, os.path.join(IMG, name))
            P.append('<h3>%s</h3><img src="img/%s" style="max-width:100%%">' % (cap, name))

EXTRA = (opt('--extra') or [None])[0]
if EXTRA:                                   # the prose (what changed, what's left, the calls) after the numbers
    at = next(i for i, x in enumerate(P) if x.startswith('<h2>Numbers'))
    end = next(i for i in range(at, len(P)) if '</table>' in P[i])
    P.insert(end + 1, open(EXTRA).read())
open(os.path.join(OUT, 'index.html'), 'w').write('\n'.join(P))
json.dump({k: {'checks': v[1]} for k, v in fr.items()}, open(os.path.join(OUT, 'faceregion.json'), 'w'), indent=1, default=str)
print(os.path.join(OUT, 'index.html'))
