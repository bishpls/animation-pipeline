"""On the box: the fresh known-bads stored (they were built there), then the shadow-edge and peeks detectors calibrated
under the hair's shape truth (charkit/calib/records/art_terminator_hair.json, art_peeks_hair.json).

    python -m charkit script tools/hairident/calib_art.py CURRENT_BUILD
"""
import os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable
cur = sys.argv[1]
for name, b in (('hi_torn', 'charkit/out/hi_torn'), ('hi_gaps', 'charkit/out/hi_gaps')):
    why = open(os.path.join(ROOT, 'charkit/calib/known_bad/%s.json' % name)).read()
    import json
    J = json.loads(why)
    subprocess.run([PY, '-m', 'charkit', 'calibrate', 'store', name, b, '--why', J['why'], '--flag', J['flag']], cwd=ROOT, check=True)
    # (the store rewrote the record with this machine's source path: the committed one is the laptop's)
    open(os.path.join(ROOT, 'charkit/calib/known_bad/%s.json' % name), 'w').write(why)
r = subprocess.run([PY, '-m', 'charkit', 'calibrate', 'art_terminator_hair,art_peeks_hair', '--build', cur], cwd=ROOT)
sys.exit(r.returncode)
