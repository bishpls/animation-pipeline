"""a spec with override files applied (dotted paths, as sweep sets: 'garments.top.tuck', 'body.shoulder'; set via
bodyeval.set_knob so a garment is addressed by its name):
    python tools/garments7/compose.py BASE.json OUT.json OVERRIDE.json [OVERRIDE.json ..] [--set PATH=JSON ..]
A path set to null removes the key."""
import sys, json
sys.path.insert(0, '.')
from charkit import bodyeval
args = sys.argv[1:]
sets = []
while '--set' in args:
    i = args.index('--set'); p, v = args[i + 1].split('=', 1); sets.append((p, json.loads(v))); del args[i:i + 2]
base, out, files = args[0], args[1], args[2:]
S = json.load(open(base))
fs = [(p, v) for f in files for p, v in json.load(open(f)).items()]
sets = fs + sets                                   # (the files first, then --set over them)
for p, v in sets:
    if v is None:
        head, key = p.rsplit('.', 1)
        d = bodyeval.get_knob(S, head)
        if isinstance(d, dict):
            d.pop(key, None)
    else:
        bodyeval.set_knob(S, p, v)
json.dump(S, open(out, 'w'), indent=1)
print(out, len(sets), 'sets')
