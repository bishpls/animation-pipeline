"""render a saved build's face and neck views (face_views.py) in one of the machine's build slots (charkit.procs.run).
    python render_slot.py BLEND OUTDIR [AZ3]"""
import os, sys
FACE = os.path.expanduser('~/animation-pipeline-face')
sys.path.insert(0, FACE)
from charkit import cli, procs
here = os.path.dirname(os.path.abspath(__file__))
blend, out = sys.argv[1], sys.argv[2]
az3 = sys.argv[3] if len(sys.argv) > 3 else '35.7'
os.makedirs(out, exist_ok=True)
r = procs.run([cli.BLENDER, '-b', blend, '--python', os.path.join(here, 'face_views.py'), '--', out, az3, FACE], out,
              label='face render')
print('exit', r.returncode, (r.stdout + r.stderr)[-300:] if r.returncode else '')
