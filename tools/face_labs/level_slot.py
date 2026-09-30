"""render a saved build's head in the design's projection (face_level.py) in one of the machine's build slots
(charkit.procs.run), the head frame's eye line and L read from the build's bundle.
    python level_slot.py BUILD [AZ3]          # BUILD/NAME.blend -> BUILD/level/ (AZ3: the head sheet's three-quarter)"""
import glob, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from charkit import bundle as bl, cli, procs

build = sys.argv[1]
az3 = sys.argv[2] if len(sys.argv) > 2 else '36.48'
blend = sorted(glob.glob(os.path.join(build, '*.blend')))[0]
B = bl.load(os.path.join(build, 'bundle'))
eye_z, L = float(B.assembly['eye_z']), float(B.assembly['L'])
out = os.path.join(build, 'level')
os.makedirs(out, exist_ok=True)
r = procs.run([cli.BLENDER, '-b', blend, '--python', os.path.join(HERE, 'face_level.py'), '--', out, repr(eye_z), repr(L),
               az3, ROOT], out, label='face level')
print('exit', r.returncode, (r.stdout + r.stderr)[-400:] if r.returncode else '')
