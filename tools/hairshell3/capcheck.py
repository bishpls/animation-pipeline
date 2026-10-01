"""round 4: the trial-join cap (det_join_nfev) must leave every shell bit-identical; skin_clear moves only the vertices
inside the skin. build_shells three ways on one fit context: as before (no cap, no skin_clear), with the cap, with cap +
skin_clear; per lock the sha256 of its vertices, the CPU of each run.
    python tools/hairshell3/capcheck.py BUILD OPTS.json OUT.json"""
import hashlib, json, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import numpy as np
from charkit.geom import lockshell as ls
build, opts, out = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3]
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
ctx = ls.context(build)
runs = {'before': dict(det_join_nfev=None, skin_clear=False), 'cap': dict(skin_clear=False), 'cap_skin': {}}
res = {}
for name, over in runs.items():
    t = time.process_time()
    LS = ls.build_shells(ctx['F'], ctx['masks'], ctx['views'], ctx['hull_frame'], ctx['L'],
                         dict(opts, split=ctx['split'], **over), log=lambda *a: None)
    cpu = time.process_time() - t
    h = {}
    for fam, parts in LS['parts'].items():
        for i, p in enumerate(parts):
            h['%s/%d' % (fam, i)] = (hashlib.sha256(np.ascontiguousarray(p['V'], np.float64).tobytes()).hexdigest()[:16],
                                     len(p['V']))
    res[name] = dict(cpu=round(cpu, 1), hashes=h, V={k: None for k in h})
    res[name]['_V'] = {'%s/%d' % (fam, i): np.asarray(p['V']) for fam, parts in LS['parts'].items() for i, p in enumerate(parts)}
    print(name, 'cpu %.1f s' % cpu, len(h), 'locks', flush=True)
a, b, c = res['before'], res['cap'], res['cap_skin']
same = [k for k in a['hashes'] if a['hashes'][k] == b['hashes'].get(k)]
print('cap vs before: %d of %d identical' % (len(same), len(a['hashes'])))
for k in a['hashes']:
    if a['hashes'][k] != b['hashes'].get(k):
        print('  differs', k, a['hashes'][k], b['hashes'].get(k))
for k in b['hashes']:
    if b['hashes'][k] != c['hashes'].get(k):
        d = np.linalg.norm(b['_V'][k] - c['_V'][k], axis=1)
        print('skin_clear moves', k, int((d > 1e-9).sum()), 'vertices, max %.4f L' % (d.max() / ctx['L']))
json.dump({k: dict(cpu=v['cpu'], hashes=v['hashes']) for k, v in res.items()}, open(out, 'w'), indent=1)
