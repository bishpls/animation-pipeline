"""A candidate spec: the current default spec (charkit/spec/clawd.json) with dotted-path overrides, so a candidate never
carries a stale copy of the rest of the spec (round 3's clawd_shells.json was a full copy from before garments4).

    python tools/hairshell3/mkspec.py OUT.json 'hair.shape.pieces_opts.lock_shells=@tools/hairshell3/pilot.json' ...
        PATH=JSON sets a value; PATH=@FILE reads the JSON value from a file; --base SPEC (default charkit/spec/clawd.json)
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def derive(base, sets):
    spec = json.load(open(base))
    for s in sets:
        path, val = s.split('=', 1)
        v = json.load(open(os.path.join(ROOT, val[1:]) if not os.path.isabs(val[1:]) else val[1:])) \
            if val.startswith('@') else json.loads(val)
        d = spec
        keys = path.split('.')
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = v
    return spec


if __name__ == '__main__':
    a = sys.argv[1:]
    base = os.path.join(ROOT, 'charkit', 'spec', 'clawd.json')
    if '--base' in a:
        i = a.index('--base'); base = a[i + 1]; del a[i:i + 2]
    out, sets = a[0], a[1:]
    json.dump(derive(base, sets), open(out, 'w'), indent=1)
    print(out)
