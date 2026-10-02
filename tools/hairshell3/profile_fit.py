"""the lock fit's CPU (round 4: the default's build CPU 1.67x): build_shells on a build's fit context under cProfile, each
Lock.fit timed with its evaluations; the top functions by own time.
    python tools/hairshell3/profile_fit.py BUILD OPTS.json OUT_DIR"""
import cProfile, json, os, pstats, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from charkit.geom import lockshell as ls

build, opts, out = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3]
os.makedirs(out, exist_ok=True)
t0 = time.time()
ctx = ls.context(build)
print('context %.1f s' % (time.time() - t0), flush=True)
o = dict(opts, split=ctx['split'])
fits = []
orig = ls.Lock.fit
def timed(self):
    t = time.process_time()
    n0 = getattr(self, '_nres', 0)
    r = orig(self)
    fits.append(dict(name=self.name, views=sorted(self.drawn), cpu=round(time.process_time() - t, 2),
                     status=list(getattr(self, 'status', None) or []),
                     cost={k: round(v, 2) for k, v in (self.cost or {}).items()}))
    return r
ls.Lock.fit = timed
pr = cProfile.Profile()
t1 = time.process_time()
pr.enable()
LS = ls.build_shells(ctx['F'], ctx['masks'], ctx['views'], ctx['hull_frame'], ctx['L'], o, log=lambda *a: None)
pr.disable()
print('build_shells CPU %.1f s, %d fits (sum %.1f s)' % (time.process_time() - t1, len(fits), sum(f['cpu'] for f in fits)), flush=True)
for f in sorted(fits, key=lambda f: -f['cpu'])[:40]:
    print('  %-34s %-28s cpu %6.1f  status %s  cost %s' % (f['name'], ','.join(f['views']), f['cpu'], f['status'], f['cost']))
st = pstats.Stats(pr); st.sort_stats('tottime').dump_stats(os.path.join(out, 'fit.prof'))
import io
s = io.StringIO(); pstats.Stats(pr, stream=s).sort_stats('tottime').print_stats(30); print(s.getvalue()[:6000])
json.dump(fits, open(os.path.join(out, 'fits.json'), 'w'), indent=1)
