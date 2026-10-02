"""A few joint-fit configurations side by side on one build's context (each in its own process): the fit's report and
the links scored (tools/hairident/ident.py's), one table.

    python tools/hairident/ident_grid.py BUILD OUT GRID.json [--truth TRUTH.json] [--holdout NAME]
        GRID.json: {name: cfg}; --holdout NAME: that configuration again with each view held out in turn
"""
import json, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ident as idn, ribbon as rb

G = {}


def one(job):
    name, cfg, hold = job
    t0 = time.time()
    try:
        r = idn.run(G['build'], G['out'], cfg, G['links'], holdout=hold, pilot=(name == '_pilot'), log=None)
    except Exception as e:
        import traceback
        return name, dict(error=traceback.format_exc()[-2000:])
    r['seconds'] = round(time.time() - t0, 1)
    return name, r


def main(a):
    build, out, grid = a[0], a[1], json.load(open(a[2]))
    os.makedirs(out, exist_ok=True)
    import truth as tr
    G.update(build=build, out=out, links=tr.load(rb._opt(a, '--truth', os.path.join(
        ROOT, 'charkit/refs/clawd/hair_lock_links.json'))))
    rb.setup(build, out)                       # the context and inputs cached once (out/ctx.pkl, out/inputs.pkl)
    hold = rb._opt(a, '--holdout', None)
    jobs = [(n, c, n in (hold or '').split(',')) for n, c in grid.items()]
    import multiprocessing as mp
    with mp.get_context('fork').Pool(len(jobs)) as pool:
        res = dict(pool.map(one, jobs, chunksize=1))
    json.dump(res, open(os.path.join(out, 'grid.json'), 'w'), indent=1, default=str)
    L = ['| config | locks | in 2+ views | positives right / wrong / missing | negatives right / extra | unmatched | '
         'pos acc | s |', '|---|---|---|---|---|---|---|---|']
    for n, r in res.items():
        if 'error' in r:
            L.append('| %s | error | | | | | | |' % n); print(r['error']); continue
        for tag, f in (('', r['fit']), (' (pilot)', r.get('pilot'))):
            if not f:
                continue
            c = f['score']['counts'].get('all', {})
            L.append('| %s%s | %s | %s | %d / %d / %d | %d / %d | %d | %s | %s |' % (
                n, tag, f.get('n'), f.get('fitted_2plus'), c.get('right_pos', 0), c.get('wrong', 0), c.get('missing', 0),
                c.get('right_neg', 0), c.get('extra', 0), c.get('unmatched', 0), c.get('pos_accuracy'),
                r.get('seconds') if not tag else ''))
        for hv, h in (r.get('holdout') or {}).items():
            c = h['score'] or {}
            L.append('| %s held out %s | | assigned %s | %d / %d / %d | %d / %d | | %s | IoU %s |' % (
                n, hv, h['assigned'], c.get('right_pos', 0), c.get('wrong', 0), c.get('missing', 0), c.get('right_neg', 0),
                c.get('extra', 0), c.get('pos_accuracy'), h['iou_mean']))
    open(os.path.join(out, 'grid.md'), 'w').write('\n'.join(L) + '\n')
    print('\n'.join(L))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
