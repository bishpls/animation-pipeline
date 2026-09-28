"""Build a director script and capture it (SO BACK's pinned kit), one Dolphin run at a time.
    .venv/bin/python projects/so-back/director/run.py NAME [--res 1] [--out DIR] [--env K=V ...] [--timeout S]
Labs default to --res 1 into ~/games/melee/work/soback/labs/NAME; the game's log is DIR/osreport.log."""
import argparse, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
KIT = os.path.join(os.path.dirname(HERE), 'machinima')
PY = os.path.join(ROOT, '.venv', 'bin', 'python')

ap = argparse.ArgumentParser()
ap.add_argument('name'); ap.add_argument('--res', type=int, default=1); ap.add_argument('--out')
ap.add_argument('--env', nargs='*', default=[]); ap.add_argument('--timeout', type=float, default=1800)
ap.add_argument('--lane', default='', help="a lane suffix: '-L1b' uses ~/games/melee/disc-soback-L1b and dolphin-soback-L1b")
ap.add_argument('--frames', type=int, default=0, help='stop after N dumped frames (a scene change ends the script first)')
a = ap.parse_args()
DISC = os.path.expanduser(f'~/games/melee/disc-soback{a.lane}'); USER = os.path.expanduser(f'~/games/melee/dolphin-soback{a.lane}')
env = dict(os.environ, MELEE_DISC=DISC, DOLPHIN_USER=USER, **dict(e.split('=', 1) for e in a.env))
out = a.out or os.path.expanduser(f'~/games/melee/work/soback/labs/{a.name}')
r = subprocess.run([PY, os.path.join(KIT, 'melee', 'build.py'), os.path.join(ROOT, 'projects', 'so-back'), a.name],
                   env=env, cwd=ROOT, capture_output=True, text=True)
if r.returncode: sys.exit(r.stdout[-3000:] + r.stderr[-3000:])
print(r.stdout.strip().splitlines()[-1])
subprocess.run([PY, os.path.join(KIT, 'dolphin.py'), 'run', os.path.join(DISC, 'sys', 'main.dol'), out, '--user', USER,
                *(['--frames', str(a.frames)] if a.frames else ['--until', 'DIRECTOR END']), '--res', str(a.res),
                '--timeout', str(a.timeout), '--quiet'], check=True, cwd=ROOT, env=env)
