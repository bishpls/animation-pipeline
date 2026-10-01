"""Write hand knobs (a JSON file of body.hand) into clawd.json and its alias clawd_body_pieces.json: the one-line
"hand" entry replaced in place (the files' own formatting kept), only the template's knobs (code_hand.DEFAULT).
    python charkit/out/hands2/setknobs.py KNOBS.json"""
import json, re, sys
sys.path.insert(0, '.')
from charkit import code_hand as ch
K = json.load(open(sys.argv[1]))
K = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in K.items() if k in ch.DEFAULT}
for p in ('charkit/spec/clawd.json', 'charkit/spec/clawd_body_pieces.json'):
    s = open(p).read()
    s2, n = re.subn(r'^(  "hand": )\{[^\n]*\}(,?)$', lambda m: m.group(1) + json.dumps(K) + m.group(2), s, flags=re.M)
    assert n == 1, (p, n)
    json.loads(s2)
    open(p, 'w').write(s2)
    print(p, K)
