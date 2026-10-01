"""Run the hair_flags part on a build and add its checks to the build's qa.json (a local build made before the part
existed: calibrate reads the current build's check names from it).

    python tools/hair5/addqa.py BUILD [BUILD ...]
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from charkit import calibrate, qa3d, hairflagqa as hf

for b in sys.argv[1:]:
    B = calibrate.load_bundle(b)
    t, C = hf.measure(B, qa3d.Design(B), os.path.join(b, 'qa'))
    q = os.path.join(b, 'qa', 'qa.json')
    Q = json.load(open(q))
    Q['checks'].update(json.loads(json.dumps(C, default=float)))
    json.dump(Q, open(q, 'w'), indent=1)
    print(b, {k: (c['value'], c['status']) for k, c in C.items()})
