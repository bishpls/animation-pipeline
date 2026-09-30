"""python -m charkit.render COMMAND ... (docs: charkit/render/__init__.py)

    probe                                    the adapters wgpu sees here, and one small frame's time on each
    boards VRM --out DIR [--which views,body] [--bundle DIR] [--ss 4] [--adapter A]
                                             the boards drawn from an export, as scene.boards frames them
    compare BUILD [--out DIR] [--ss 4] [--adapter A] [--open]
                                             BUILD's EEVEE boards (BUILD/boards/*.png) against ours from its export
                                             (BUILD/*.vrm), with DIR/compare.json and the review page DIR/index.html
    bench VRM [--reps 5] [--adapter A] [--ss 4] [--which views,body] [--json OUT]
                                             seconds per board (warm; the first frame and the setup apart)
    page DIR                                 DIR/compare.json -> DIR/index.html
"""
import json, os, shutil, sys, time

import numpy as np


def _opt(a, k, d=None):
    return a[a.index(k) + 1] if k in a else d


def _head(bundle_dir):
    """eye_z, L from a build's bundle (charkit.bundle's assembly meta), or (None, None)."""
    p = os.path.join(bundle_dir, 'bundle.json') if bundle_dir else None
    if p and os.path.exists(p):
        a = json.load(open(p)).get('assembly') or {}
        return a.get('eye_z'), a.get('L')
    return None, None


def _vrm_in(build):
    c = [f for f in sorted(os.listdir(build)) if f.endswith('.vrm') and '.springs.' not in f]
    if not c:
        raise SystemExit(f'{build}: no .vrm (build with --vrm, or python -m charkit export BUILD/NAME.blend)')
    return os.path.join(build, c[0])


def _save(path, img):
    from PIL import Image
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    Image.fromarray(img).save(path)


def probe(args):
    from . import gpu, model, views
    print(json.dumps(gpu.adapters(), indent=1))
    return 0


def boards(args):
    from . import gpu, model, views
    vrm, out = args[0], _opt(args, '--out', 'charkit/out/render')
    which = tuple(_opt(args, '--which', 'views,body').split(','))
    t = time.time()
    M = model.load(vrm)
    eye_z, L = _head(_opt(args, '--bundle', os.path.join(os.path.dirname(vrm), 'bundle')))
    R = gpu.Renderer(M, adapter=_opt(args, '--adapter'), ss=int(_opt(args, '--ss', 4)))
    rep = {'adapter': R.info, 'load_s': round(time.time() - t, 3), 'boards': {}}
    for v in views.board_views(M, which, eye_z=eye_z, L=L):
        t = time.time()
        img = R.render(v)
        rep['boards'][v.name] = round(time.time() - t, 4)
        _save(os.path.join(out, v.name + '.png'), img)
    rep.update(R.timing)
    json.dump(rep, open(os.path.join(out, 'render.json'), 'w'), indent=1)
    print(json.dumps(rep))
    return 0


def eevee_times(build):
    """the build's board renders from its trace (charkit.trace spans 'board' and 'board_batch') -> {name: s}, and the
    batches' per-frame seconds."""
    p = os.path.join(build, 'trace.jsonl')
    out, batches = {}, []
    if not os.path.exists(p):
        return out, batches
    for line in open(p):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get('event') == 'span' and r.get('name') == 'board':
            out[os.path.splitext(r.get('path', ''))[0]] = r['dt']
        elif r.get('event') == 'span' and r.get('name') == 'board_batch':
            batches.append({'first': r.get('first'), 'n': r.get('n'), 'dt': r['dt'], 'batched': r.get('batched'),
                            'per_frame': round(r['dt'] / max(r.get('n') or 1, 1), 4)})
    return out, batches


NOTES = [
    'The hair streaks are included: charkit.shade.hair_toon keeps its columns by an integer hash of their index '
    '(Jenkins\' lookup3, Blender\'s White Noise node; toon.wgsl computes the same in u32), the same bits on every GPU '
    '(Michael\'s call H). "Streaks" gives the difference inside the streak region of either picture (compare.streak_mask); '
    '"excl. streaks" leaves it out, as the phase 1 table did.',
    'EEVEE dithers its 8-bit output (1 level on about 80% of flat pixels), so a mean difference under 1 level is the floor.',
    'The hair and skin are shaded with normals Blender transfers after the outline, re-sampled at each view\'s moved '
    'surface (p99 1-12 degrees from the export\'s at the body boards\' width); the export carries them at the outline-off '
    'surface, so the hair keeps a few tone patches that differ (the side locks).',
    'Garments are shaded with their moved surface\'s normals, recomputed per line width from Blender\'s quads '
    '(charkit/render/normals.py), as Blender recomputes them after the outline SOLIDIFY.',
]


def speed_rows(build, et, batches):
    """seconds per board: EEVEE from the build's trace, ours from any bench_*.json (python -m charkit.render bench
    --json) beside it."""
    rows = []
    for b in batches:
        rows.append({'what': 'EEVEE, batched (%s set, %d boards%s)' % (b['first'].split('_')[0], b['n'],
                     ', features pass included' if b['first'].startswith('face') else ''),
                     'where': 'the build\'s machine (its trace)', 's_per_board': b['per_frame']})
    if et:
        rows.append({'what': 'EEVEE, stills', 'where': 'the build\'s machine (its trace)',
                     's_per_board': round(float(np.mean(list(et.values()))), 3)})
    for f in sorted(os.listdir(build)):
        if f.startswith('bench_') and f.endswith('.json'):
            r = json.load(open(os.path.join(build, f)))
            a = r['adapter']
            for k, lab in (('face_mean_s', 'face'), ('body_mean_s', 'body')):
                rows.append({'what': 'ours, %s boards (ss %d)' % (lab, r['ss']),
                             'where': '%s (%s) [%s]' % (a['device'], a['backend'], f[6:-5]), 's_per_board': r[k],
                             'note': 'warm median of %d; setup %.1f s, first frame %.2f s' % (r['reps'], r['setup_s'],
                                                                                           r['first_frame_s'])})
    return rows


def machine_rows(build, out, names):
    """ours from other machines (BUILD/ours_*/NAME.png, python -m charkit.render boards there) against ours here."""
    from PIL import Image
    rows = []
    for d in sorted(os.listdir(build)):
        p = os.path.join(build, d)
        if not (d.startswith('ours_') and os.path.isdir(p)):
            continue
        same, mx, n = [], 0, 0
        for nm in names:
            f = os.path.join(p, nm + '.png')
            if not os.path.exists(f):
                continue
            a = np.asarray(Image.open(os.path.join(out, 'ours', nm + '.png'))).astype(np.int16)
            b = np.asarray(Image.open(f).convert('RGB')).astype(np.int16)
            dd = np.abs(a - b).max(-1)
            same.append(float((dd == 0).mean())); mx = max(mx, int(dd.max())); n += 1
        info = {}
        rj = os.path.join(p, 'render.json')
        if os.path.exists(rj):
            info = json.load(open(rj)).get('adapter', {})
        if n:
            rows.append({'dir': d, 'adapter': '%s (%s)' % (info.get('device'), info.get('backend')), 'boards': n,
                         'identical_min': round(min(same), 5), 'identical_mean': round(float(np.mean(same)), 5), 'max': mx})
    return rows


def compare_build(args):
    from PIL import Image
    from . import compare, gpu, model, page, views
    build = os.path.abspath(args[0])
    out = os.path.abspath(_opt(args, '--out', os.path.join(build, 'toonrender')))
    vrm = _vrm_in(build)
    M = model.load(vrm)
    eye_z, L = _head(os.path.join(build, 'bundle'))
    kw = dict(adapter=_opt(args, '--adapter'), ss=int(_opt(args, '--ss', 4)))
    R = gpu.Renderer(M, **kw)
    R0 = gpu.Renderer(M, streaks=False, **kw)
    pal = compare.palette(M, views.BG)
    bdir = os.path.join(build, 'boards')
    V = [v for v in views.board_views(M, ('views', 'body'), eye_z=eye_z, L=L)
         if os.path.exists(os.path.join(bdir, v.name + '.png'))]
    if not V:
        raise SystemExit(f'{bdir}: no face_*/body_* boards')
    for v in V[:1]:
        R.render(v)                                     # warm: the first frame compiles the pipelines' shaders
    C = {'build': build, 'vrm': vrm, 'adapter': R.info, 'created': time.strftime('%Y-%m-%d %H:%M'),
         'settings': {'ss': R.ss, 'sigma': R.sigma, 'radius': R.radius, 'hash': 'lookup3', 'through': R.through,
                      'eye_z': eye_z, 'L': L}, 'boards': {}}
    et, batches = eevee_times(build)
    for v in V:
        ref = np.asarray(Image.open(os.path.join(bdir, v.name + '.png')).convert('RGB'))
        t = time.time()
        ours = R.render(v)
        dt = time.time() - t
        base = R0.render(v)
        ex = compare.streak_mask(ref, ours, base, M)
        m = compare.board(ref, ours, pal, views.BG, exclude=ex)
        m['diff_streaks'] = compare.region_stats(ref, ours, ex)
        files = {'eevee': f'eevee/{v.name}.png', 'ours': f'ours/{v.name}.png', 'diff': f'diff/{v.name}.png'}
        os.makedirs(os.path.join(out, 'eevee'), exist_ok=True)
        shutil.copy(os.path.join(bdir, v.name + '.png'), os.path.join(out, files['eevee']))
        _save(os.path.join(out, files['ours']), ours)
        _save(os.path.join(out, files['diff']), compare.heatmap(ref, ours))
        _save(os.path.join(out, 'streaks', v.name + '.png'), (ex * 255).astype(np.uint8))
        C['boards'][v.name] = {'res': list(v.res), 'seconds': round(dt, 4), 'eevee_seconds': et.get(v.name),
                               'metrics': m, 'files': files}
        d = m['diff']
        print(f'{v.name}: max {d["max"]} mean {d["mean"]:.3f} >8 {100 * d["over8"]:.3f}% | streaks mean '
              f'{m["diff_streaks"].get("mean", 0):.3f} >8 {100 * m["diff_streaks"].get("over8", 0):.2f}% | IoU '
              f'{m["silhouette"]["iou"]:.4f} | tones '
              f'{m.get("tones", {}).get("agree")} | {dt:.3f} s')
    C['eevee_batches'] = batches
    C['speed'] = speed_rows(build, et, batches)
    C['machines'] = machine_rows(build, out, [v.name for v in V])
    C['notes'] = NOTES
    json.dump(C, open(os.path.join(out, 'compare.json'), 'w'), indent=1, default=str)
    p = page.write(out)
    print('page', p)
    if '--open' in args:
        os.system(f'open "{p}"')
    return 0


def bench(args):
    from . import gpu, model, views
    vrm = args[0]
    reps = int(_opt(args, '--reps', 5))
    which = tuple(_opt(args, '--which', 'views,body').split(','))
    t0 = time.time()
    M = model.load(vrm)
    t1 = time.time()
    R = gpu.Renderer(M, adapter=_opt(args, '--adapter'), ss=int(_opt(args, '--ss', 4)))
    t2 = time.time()
    eye_z, L = _head(os.path.join(os.path.dirname(vrm), 'bundle'))
    V = views.board_views(M, which, eye_z=eye_z, L=L)
    t = time.time(); R.render(V[0]); first = time.time() - t
    per = {v.name: [] for v in V}
    for _ in range(reps):
        for v in V:
            t = time.time(); R.render(v); per[v.name].append(time.time() - t)
    med = {k: round(float(np.median(x)), 4) for k, x in per.items()}
    rep = {'adapter': R.info, 'ss': R.ss, 'load_s': round(t1 - t0, 3), 'setup_s': round(t2 - t1, 3),
           'first_frame_s': round(first, 3), 'per_board_median_s': med,
           'face_mean_s': round(float(np.mean([x for k, x in med.items() if k.startswith('face')] or [0])), 4),
           'body_mean_s': round(float(np.mean([x for k, x in med.items() if k.startswith('body')] or [0])), 4),
           'all_mean_s': round(float(np.mean(list(med.values()))), 4), 'reps': reps,
           'triangles': int(sum(len(p.index) // 3 for p in M.prims))}
    print(json.dumps(rep))
    if _opt(args, '--json'):
        json.dump(rep, open(_opt(args, '--json'), 'w'), indent=1)
    return 0


def main(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__); return 0
    cmd, rest = argv[0], argv[1:]
    f = {'probe': probe, 'boards': boards, 'compare': compare_build, 'bench': bench,
         'page': lambda a: print(__import__('charkit.render.page', fromlist=['write']).write(a[0])) or 0}.get(cmd)
    if f is None:
        print(__doc__); return 1
    return f(rest)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
