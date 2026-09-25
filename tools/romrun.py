"""One command for a rig's range-of-motion check (fast path).

    .venv/bin/python tools/romrun.py projects/<film> [--seg tilt,switch] [--sheet 18] [--workers 6]

1. reads the segment list and layer IDs from the page (window.ROM, window.RIG_IDS)
2. renders ONLY the ID pass (LOOPS.romid), for the chosen segments (substring match) plus the rest segments (baselines)
3. checks every frame (tools/romcheck2.py, parallel)
4. renders the normal look only for the worst frames and sheets them (OUT/worst.png)
Output: projects/<film>/out/rom/ (romid/, rom/, report.json, summary.txt, worst.png).
"""
import json, os, shutil, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
a = sys.argv[1:]; P = a[0]
opt = lambda k, d: type(d)(a[a.index(k) + 1]) if k in a else d
O = os.path.join(ROOT, P, 'out', 'rom'); FPS = 24
node = lambda *args: subprocess.run(['node', os.path.join(ROOT, 'engine', 'render.mjs'), P, *args], cwd=ROOT, capture_output=True, text=True)
t0 = time.time()
os.makedirs(O, exist_ok=True)
r = node('--loop=rom', '--eval=JSON.stringify({rom: window.ROM, ids: window.RIG_IDS})')
d = json.loads(json.loads(r.stdout.strip().splitlines()[-1]))
json.dump(d['rom'], open(os.path.join(O, 'rom.json'), 'w')); json.dump(d['ids'], open(os.path.join(O, 'ids.json'), 'w'))
segs = d['rom']; want = [s for s in opt('--seg', '').split(',') if s]
pick = [s for s in segs if s[0].startswith('rest ') or not want or any(w in s[0] for w in want)]
for sub in ('romid', 'rom'):
    shutil.rmtree(os.path.join(O, sub), ignore_errors=True)
# contiguous ranges (merge neighbours) -> one render each
ranges = []
for _, s0, s1, *_ in pick:
    if ranges and abs(ranges[-1][1] - s0) < 1e-6: ranges[-1][1] = s1
    else: ranges.append([s0, s1])
node('--loop=romid', '--frames', '--png', f'--framesdir={os.path.join(O, "romid")}', '--ranges=' + ','.join(f'{s0}:{s1}' for s0, s1 in ranges), f'--workers={opt("--workers", 6)}')
t1 = time.time()
chk = subprocess.run([os.path.join(ROOT, '.venv', 'bin', 'python'), os.path.join(ROOT, 'tools', 'romcheck2.py'), O, os.path.join(O, 'rom.json'), os.path.join(O, 'ids.json'),
                      '--sheet', '0'], capture_output=True, text=True)
t2 = time.time()
# the normal look, only for the worst frame of each segment
rep = json.load(open(os.path.join(O, 'report.json'))); N = opt('--sheet', 18); picked, seen = [], set()
for rr in sorted([x for x in rep if x['score'] > 0], key=lambda x: -x['score']):
    if rr['seg'] not in seen: picked.append(rr['f']); seen.add(rr['seg'])
    if len(picked) >= N: break
if picked:
    ts = ','.join(f'{f / FPS:.4f}' for f in picked)
    node('--loop=rom', f'--stills={ts}')
    os.makedirs(os.path.join(O, 'rom'), exist_ok=True); sd = os.path.join(ROOT, P, 'board', 'stills')
    for f in picked:
        tn = f'{f / FPS:.4f}'.rstrip('0').rstrip('.'); src = os.path.join(sd, 't' + tn.replace('.', '_') + '.png')
        cands = [x for x in os.listdir(sd) if x.startswith('t' + tn.split('.')[0] + '_')] if not os.path.exists(src) else []
        if not os.path.exists(src):                  # the stills naming rounds; take the closest
            best = min(os.listdir(sd), key=lambda x: abs(float(x[1:-4].replace('_', '.')) - f / FPS) if x.startswith('t') else 1e9)
            src = os.path.join(sd, best)
        shutil.copy(src, os.path.join(O, 'rom', f'f{f:05d}.png'))
    sheet = subprocess.run([os.path.join(ROOT, '.venv', 'bin', 'python'), os.path.join(ROOT, 'tools', 'romcheck2.py'), O, os.path.join(O, 'rom.json'), os.path.join(O, 'ids.json'),
                            '--sheet', str(N), '--from-report'], capture_output=True, text=True)
    print(sheet.stdout.strip())
open(os.path.join(O, 'summary.txt'), 'w').write(chk.stdout)
print(chk.stdout[-4000:])
print(f'render {t1 - t0:.0f}s  check {t2 - t1:.0f}s  total {time.time() - t0:.0f}s   ({len(pick)} segments, {sum(1 for _ in os.listdir(os.path.join(O, "romid")))} frames)')
