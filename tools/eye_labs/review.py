"""The eyes' review page (round 2): each eye the head sheet draws, the design | before | after at the sheet's scale,
with charkit.eyeqa's per-view measures drawn on them (the pupil's width lines at 25/50/75% of its height and its
second-moment ellipse, the front gap per row, the fitted front edge, the lash flick), the per-view checks' table, and
the eye's surface along its corner row seen from above (the face's window, the plate, the turned surface).

    python tools/eye_labs/review.py OUT_DIR BEFORE_BUILD AFTER_BUILD      -> OUT_DIR/index.html

BEFORE/AFTER are build folders (their bundle/ is read, venv only).
"""
import html, json, os, sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from charkit import bundle as bl, eyepage, eyeqa, qa3d  # noqa: E402

VIEWS = (('front', 'R'), ('front', 'L'), ('three_quarter', 'L'), ('three_quarter', 'R'), ('profile', 'L'))
SCALE = 4


def _crop(rgba, M, box_hw):
    """a window of the design's size round the opening's centre (so the three columns frame the eye alike)."""
    S = M.get('_masks') or {}
    H, W = rgba.shape[:2]
    ob = eyeqa._box(S['opening']) if 'opening' in S else None
    cy, cx = ((ob[2] + ob[3]) / 2, (ob[0] + ob[1]) / 2) if ob else (H / 2, W / 2)
    h, w = box_hw
    y0 = int(round(cy - h / 2)); x0 = int(round(cx - w / 2))
    pad = max(h, w)
    P = np.pad(rgba, ((pad, pad), (pad, pad), (0, 0)))
    return P[y0 + pad:y0 + pad + h, x0 + pad:x0 + pad + w]


def _save(a, path):
    from PIL import Image
    Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).save(path)


def _row(B, side='L'):
    """the eye's sclera plate along its corner row: (x across the eye in eye widths, + outward; world depth in L)."""
    A = B.assembly
    L = A['L']
    E = next(E for E in A['eyes'] if (E['side'] > 0) == (side == 'L'))
    ex, ez = E['c']
    W = A['eye_knobs']['width'] * L
    sc = B.part('sclera', side).mesh('eval')[0]
    near = np.abs(sc[:, 2] - ez) < 0.03 * W
    xs = (sc[near, 0] - ex) / W * (1 if side == 'L' else -1)
    o = np.argsort(xs)
    return xs[o], (sc[near, 1][o] - A['centre'][1]) / L


def section_plot(Bb, Ba, path):
    """the eye's corner row seen from above, before and after: the sclera plate's depth (L behind the head's centre;
    the picture's top is the front) across the eye (eye widths, + outward). The side view looks along +x: a stretch
    whose depth grows toward the nose (leftward here) faces away from it."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.4, 3.0), dpi=110)
    for B, lab, st in ((Bb, 'before: the plate on the eye window', '-'), (Ba, 'after: turned round the fold', '-')):
        x, y = _row(B)
        ax.plot(x, y, st, lw=2, label=lab)
    ax.axvspan(-0.5, 0.5, color='0.93', zorder=0)
    ax.text(-0.49, ax.get_ylim()[0], ' the opening', fontsize=7, va='bottom')
    ax.invert_yaxis()
    ax.set_xlabel('across the eye (eye widths; nose to the left, + outward)'); ax.set_ylabel('depth (L; front up)')
    ax.legend(fontsize=7, loc='lower right'); fig.tight_layout(); fig.savefig(path); plt.close(fig)


def main(out, before, after):
    os.makedirs(os.path.join(out, 'img'), exist_ok=True)
    Bb, Ba = bl.load(os.path.join(before, 'bundle')), bl.load(os.path.join(after, 'bundle'))
    des, ppl = eyepage.design_eyes(Ba.spec)
    got = qa3d.Design(Ba).sheet_measures()
    az3 = float(got[0].get('az_three_quarter', 35.0)) if got else 35.0
    azs = {'front': 0.0, 'three_quarter': az3, 'profile': 90.0}
    tb, Cb = eyeqa.views(Bb)
    ta, Ca = eyeqa.views(Ba)
    rows, tiles = [], []
    for view, side in VIEWS:
        px = dict(des.get(view, [])).get(side)
        if px is None:
            continue
        n = eyeqa.NASAL[(view, side)]
        col = []
        for tag, rgba in (('design', px), ('before', qa3d.eye_image(Bb, side, ppl, ss=3, az=azs[view])),
                          ('after', qa3d.eye_image(Ba, side, ppl, ss=3, az=azs[view]))):
            M = eyeqa.measure_view(rgba, ppl, n)
            c = _crop(rgba, M, px.shape[:2])
            Mc = eyeqa.measure_view(c, ppl, n)
            name = 'eye_%s_%s_%s.png' % (view, side, tag)
            _save(eyeqa.overlay(c, Mc, SCALE), os.path.join(out, 'img', name))
            _save(c[..., :3] * c[..., 3:] + 0.93 * (1 - c[..., 3:]), os.path.join(out, 'img', 'raw_' + name))
            col.append((tag, name, Mc))
        tiles.append((view, side, col))
    section_plot(Bb, Ba, os.path.join(out, 'img', 'section.png'))
    # the table: every graded per-view measure, per eye: the design's, before and after, each graded against it
    cls = lambda st: {'PASS': 'p', 'WARN': 'w', 'FAIL': 'f'}.get(st, '')
    T = ['<table><tr><th>view, eye</th><th>measure</th><th>design</th><th>before</th><th>after</th></tr>']
    for view, side in VIEWS:
        key = '%s_%s' % (view, side)
        if key not in ta or key not in tb:
            continue
        d, b, a = ta[key]['design'], tb[key]['ours'], ta[key]['ours']
        cb = eyeqa.compare_view(b, d, eyeqa.VIEW_CHECKS[view])
        ca = eyeqa.compare_view(a, d, eyeqa.VIEW_CHECKS[view])
        for i, k in enumerate(eyeqa.VIEW_CHECKS[view]):
            T.append('<tr><td>%s</td><td>%s</td><td>%s</td><td class="%s">%s %s</td><td class="%s">%s %s</td></tr>' % (
                ('%s, %s' % (view.replace('_', '-'), side)) if i == 0 else '', k, d.get(k), cls(cb[k]['status']), b.get(k),
                cb[k]['status'], cls(ca[k]['status']), a.get(k), ca[k]['status']))
    T.append('</table>')
    rel = lambda p: html.escape(os.path.relpath(p, out))
    Hs = ['<!doctype html><meta charset="utf-8"><title>Eyes round 2</title>',
          '<style>body{font:14px/1.45 -apple-system,system-ui,sans-serif;margin:24px;background:#fafafa;color:#222;max-width:1900px}'
          'h2{font-size:17px;margin:26px 0 6px}.row{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-start}'
          '.tile{font-size:12px;color:#444}.tile img{display:block;border:1px solid #ddd;background:#fff;width:432px}'
          'table{border-collapse:collapse;font-size:13px}td,th{border:1px solid #ddd;padding:3px 8px;text-align:right}'
          'th{background:#f0f0f0}td:first-child{text-align:left}.p{color:#070}.w{color:#b60}.f{color:#c00}.n{color:#888}'
          '.key span{display:inline-block;width:12px;height:12px;margin:0 4px -2px 10px}</style>',
          '<h1>Eyes, round 2: where the iris sits, and the pupil</h1>',
          '<p>Design: head_turnaround at its own scale (%.0f px/L). Before: <code>%s</code>. After: <code>%s</code>. '
          'Ours are the QA\'s eye renders from the same azimuths (front 0&deg;, three-quarter %.1f&deg;, profile 90&deg;), '
          'framed on the opening like the design\'s crop. All three at one scale.</p>' % (ppl, rel(before), rel(after), az3),
          '<p class="key">Drawn: <span style="background:#dc1ea0"></span>the opening (sclera + iris) '
          '<span style="background:#e61414"></span>front gap per row (sclera nasal of the iris) '
          '<span style="background:#14aa3c"></span>the fitted front edge '
          '<span style="background:#00dcff"></span>the pupil\'s width at 25/50/75%% of its height '
          '<span style="background:#ffd200"></span>its second-moment ellipse '
          '<span style="background:#1e3ce6"></span>the lash flick\'s tip and the far corner</p>',
          '<h2>The per-view checks</h2>', ''.join(T)]
    for view, side, col in tiles:
        Hs.append('<h2>%s, %s eye</h2><div class="row">' % (view.replace('_', '-'), {'L': 'her left', 'R': 'her right'}[side]))
        for tag, name, M in col:
            m = ' &middot; '.join('%s %s' % (k, M.get(k)) for k in ('front_gap', 'gaze_off', 'behind', 'pupil_w50', 'pupil_area',
                                                                    'pupil_axis', 'pupil_h', 'edge_rms', 'flick_out')
                                  if M.get(k) is not None)
            Hs.append('<div class="tile"><b>%s</b><a href="img/raw_%s"><img src="img/%s"></a>%s</div>' % (tag, name, name, m))
        Hs.append('</div>')
    Hs.append('<h2>The eye\'s surface along its corner row, from above</h2><div class="row">'
              '<div class="tile"><img src="img/section.png" style="width:704px">her left eye\'s sclera plate along the corner row '
              '(<code>bundle</code> vertices within 0.03 eye widths of it). Nasal of the fold the surface faces the front, '
              'so a side view sees it edge-on or from behind.</div></div>')
    # the boards as rendered (EEVEE, with the hair): the eyes' band of the face boards, before | after
    crops = {'000': (0.28, 0.36, 0.72, 0.62), '030': (0.22, 0.36, 0.66, 0.62), '090': (0.12, 0.36, 0.56, 0.62)}
    got = []
    for v, (x0, y0, x1, y1) in crops.items():
        paths = [os.path.join(b, 'boards', 'face_%s.png' % v) for b in (before, after)]
        if not all(os.path.exists(q) for q in paths):
            continue
        from PIL import Image
        for tag, q in zip(('before', 'after'), paths):
            im = Image.open(q); W, H = im.size
            im.crop((int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H))).save(os.path.join(out, 'img', 'board_%s_%s.png' % (v, tag)))
        got.append(v)
    if got:
        Hs.append('<h2>The face boards as rendered (EEVEE, hair on), the eyes\' band</h2><p>Before and after, the board '
                  'camera at 0, 30 and 90 degrees. The hair differs between the two builds (the default spec now builds hair '
                  'pieces), so judge the eyes by the crops above; these show them in the shaded frame.</p>')
        for v in got:
            Hs.append('<div class="row">%s</div>' % ''.join(
                '<div class="tile"><b>%s, %s&deg;</b><img src="img/board_%s_%s.png" style="width:560px"></div>' % (t, int(v), v, t)
                for t in ('before', 'after')))
    open(os.path.join(out, 'index.html'), 'w').write('\n'.join(Hs))
    json.dump({'before': {k: {kk: vv for kk, vv in v.items() if kk in ('ours', 'design', 'status', 'eye')} for k, v in Cb.items()},
               'after': {k: {kk: vv for kk, vv in v.items() if kk in ('ours', 'design', 'status', 'eye')} for k, v in Ca.items()}},
              open(os.path.join(out, 'checks.json'), 'w'), indent=1, default=float)
    return os.path.join(out, 'index.html')


if __name__ == '__main__':
    print(main(*sys.argv[1:4]))
