"""The standing laptop-against-build-box test for charkit's toon renderer (Michael's decision 5, trustworthy local loops):
one build's export drawn on this machine (Metal on the laptop) and on the CPU build box (Mesa's llvmpipe), and every
number the renderer feeds compared: the boards pixel by pixel, the QA's buffers (part and tone per pixel) and the drawn
QA checks (charkit.qarender's drawing: hair_noise, scalp_px and the look's), each against its bound.

    python -m charkit.render parity BUILD [--box build]          both machines, the report in BUILD/parity/ (exit 1
                                                                 when a measure passes its bound)
    python -m charkit.render parity BUILD --here --out DIR       what each machine runs: DIR/boards/*.png, DIR/buffers.npz,
                                                                 DIR/qa/qa.json, DIR/machine.json

BUILD is a build directory (its bundle and NAME.look.glb or NAME.vrm) under this worktree; when the box's copy of this
worktree lacks it, its bundle and export are sent first. The bounds (BOUNDS) are the rasterisers' tie-breaking on part
and line edges (phase 1: 99.85% of the boards' pixels bit-identical) carried through each measure; a measure past its
bound fails the test.
"""
import fnmatch, json, os, subprocess, sys, time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PARTS = ('hair_noise', 'scalp', 'look')        # the drawn QA parts whose design inputs are the same on every machine
BOUNDS = [                                      # (measure pattern, the largest difference that passes), first match wins
    ('board_identical', 0.995),                 # the share of a board's pixels bit-identical, at least
    ('board_mean', 0.1),                        # levels, mean over a board's pixels
    ('buffer_part', 0.998),                     # the share of a frame's pixels showing the same part, at least
    ('buffer_tone', 0.998),                     # ... the same tone class, at least
    ('check:scalp_px', 0),
    ('check:face_islands', 1),
    ('check:line_*', 0.005),
    ('check:*', 0.002),
]


def bound(name):
    return next(b for p, b in BOUNDS if fnmatch.fnmatchcase(name, p))


def here(build, out, adapter=None):
    """this machine's side: the boards, two QA frames' buffers and the drawn QA checks -> DIR/machine.json."""
    from charkit import bundle, lookqa, qa3d, qarender
    from . import buffers, buildboards
    t0 = time.time()
    os.makedirs(out, exist_ok=True)
    rep = buildboards.draw(out, ('views', 'body'), adapter=adapter)
    B = bundle.load(os.path.join(build, 'bundle'))
    Q = buffers.load(buildboards.export_of(build), adapter=adapter)
    fr = lookqa.HeadFrame(B)
    arrays = {}
    for az in (0.0, 30.0, 90.0):
        F = Q.frame(buffers.window(az, fr.origin, fr.pix, fr.win), off={B.skin().name}, light=qa3d.view_light(B, az),
                    aux_ss=1, picture=False)
        arrays['head_%03d_part' % az] = F['part'].astype(np.int16)
        arrays['head_%03d_tone' % az] = np.where(np.isfinite(F['tone']), np.rint(F['tone']), -1).astype(np.int8)
    np.savez_compressed(os.path.join(out, 'buffers.npz'), **arrays)
    os.environ[qarender.ENV] = 'render'
    if adapter:
        os.environ['CHARKIT_RENDER_ADAPTER'] = adapter
    qa = qa3d.run(B, os.path.join(out, 'qa'), mode='off', parts=list(PARTS))
    info = {'adapter': Q.info, 'boards': rep['boards'], 'setup_s': rep['setup_s'], 'qa_seconds': qa['measured']['seconds'],
            'draw': qa['measured'].get('draw'), 'seconds': round(time.time() - t0, 1), 'host': os.uname().nodename}
    json.dump(info, open(os.path.join(out, 'machine.json'), 'w'), indent=1, default=str)
    return info


def compare(a, b):
    """two machines' DIRs -> rows (measure, a, b, difference, bound, ok)."""
    from PIL import Image
    rows = []
    for f in sorted(os.listdir(os.path.join(a, 'boards'))):
        if not f.endswith('.png') or not os.path.exists(os.path.join(b, 'boards', f)):
            continue
        x = np.asarray(Image.open(os.path.join(a, 'boards', f)).convert('RGB')).astype(np.int16)
        y = np.asarray(Image.open(os.path.join(b, 'boards', f)).convert('RGB')).astype(np.int16)
        d = np.abs(x - y).max(-1)
        same = float((d == 0).mean())
        rows.append(dict(measure='board_identical', what=f[:-4], value=round(same, 5), max=int(d.max()),
                         bound=bound('board_identical'), ok=same >= bound('board_identical')))
        rows.append(dict(measure='board_mean', what=f[:-4], value=round(float(d.mean()), 4),
                         bound=bound('board_mean'), ok=float(d.mean()) <= bound('board_mean')))
    A, Bz = np.load(os.path.join(a, 'buffers.npz')), np.load(os.path.join(b, 'buffers.npz'))
    for k in sorted(set(A.files) & set(Bz.files)):
        kind = 'buffer_part' if k.endswith('_part') else 'buffer_tone'
        x, y = A[k], Bz[k]
        m = (x >= 0) | (y >= 0) if kind == 'buffer_part' else (x >= 0) & (y >= 0)
        agree = float((x[m] == y[m]).mean()) if m.any() else 1.0
        rows.append(dict(measure=kind, what=k.rsplit('_', 1)[0], value=round(agree, 6), bound=bound(kind),
                         ok=agree >= bound(kind)))
    qa, qb = (json.load(open(os.path.join(d, 'qa', 'qa.json')))['checks'] for d in (a, b))
    for k in sorted(set(qa) & set(qb)):
        va, vb = qa[k].get('value'), qb[k].get('value')
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (va, vb)):
            continue
        d = abs(float(va) - float(vb))
        bd = bound('check:' + k)
        rows.append(dict(measure='check', what=k, value=[va, vb], diff=round(d, 6), bound=bd, ok=d <= bd + 1e-12,
                         status=[qa[k].get('status'), qb[k].get('status')]))
    return rows


def markdown(rep):
    bad = [r for r in rep['rows'] if not r['ok']]
    L = ['# charkit.render parity: %s, %s against %s: %s' % (
        rep['build'], rep['a']['adapter'].get('device'), rep['b']['adapter'].get('device'),
        'PASS' if not bad else 'FAIL (%d measures past their bound)' % len(bad)), '',
        'The same export drawn on each machine; each measure against its bound (charkit/render/parity.py BOUNDS).', '',
        '| measure | what | value | bound | |', '| --- | --- | --- | --- | --- |']
    for r in sorted(rep['rows'], key=lambda r: (r['ok'], r['measure'], r['what'])):
        v = r['value'] if r['measure'] != 'check' else '%s / %s (diff %s)' % (r['value'][0], r['value'][1], r['diff'])
        if r['measure'] == 'board_identical':
            v = '%s (max %d levels)' % (v, r['max'])
        L.append('| %s | %s | %s | %s | %s |' % (r['measure'], r['what'], v, r['bound'], '' if r['ok'] else '**past**'))
    return '\n'.join(L) + '\n'


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return 0
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    build = os.path.abspath(args[0])
    rel = os.path.relpath(build, ROOT)
    if '--here' in args:
        info = here(build, os.path.abspath(opt('--out')), opt('--adapter'))
        print(json.dumps(info, default=str))
        return 0
    from charkit import remote
    from .buildboards import export_of
    if '--box' in args:
        remote.BOX['env'] = os.path.join(ROOT, 'infra', 'gcp', opt('--box') + '.env')
    out = os.path.join(build, 'parity')
    local = os.path.join(out, 'laptop')
    here(build, local, opt('--adapter'))
    remote.up()
    remote._sh('sync', ROOT)
    box_dir = '/srv/work/%s/%s' % (os.path.basename(ROOT), rel)
    exp = export_of(build)
    have = remote._sh('ssh', 'test -f %s/bundle/arrays.npz && test -f %s/%s && echo yes || true' % (
        box_dir, box_dir, os.path.basename(exp)), capture=True, check=False).strip()
    if have != 'yes':
        for f in ('bundle/bundle.json', 'bundle/arrays.npz', os.path.basename(exp)):
            remote._sh('ssh', 'mkdir -p %s' % os.path.dirname(os.path.join(box_dir, f)))
            remote.put(os.path.join(build, f), os.path.join(box_dir, f))
    code = remote._sh('run', ROOT, 'python -m charkit.render parity %s --here --out %s/parity/box' % (rel, rel),
                      check=False)
    remote._sh('fetch', ROOT, os.path.join(rel, 'parity', 'box'))
    if code:
        raise SystemExit('parity: the box side failed (exit %d)' % code)
    a, b = json.load(open(os.path.join(local, 'machine.json'))), json.load(open(os.path.join(out, 'box', 'machine.json')))
    rep = dict(build=rel, t=time.strftime('%Y-%m-%dT%H:%M:%S'), a=a, b=b, bounds=BOUNDS,
               rows=compare(local, os.path.join(out, 'box')))
    rep['ok'] = all(r['ok'] for r in rep['rows'])
    json.dump(rep, open(os.path.join(out, 'parity.json'), 'w'), indent=1, default=str)
    open(os.path.join(out, 'parity.md'), 'w').write(markdown(rep))
    print(markdown(rep))
    print('report', os.path.join(out, 'parity.md'))
    return 0 if rep['ok'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
