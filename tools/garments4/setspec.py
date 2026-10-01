"""edit the default spec's garments (clawd.json and its alias clawd_body_pieces.json) from a JSON of overrides
{"garments.NAME.KEY...": value}, keeping the file's formatting outside the garments list.
python tools/garments4/setspec.py OVERRIDES.json"""
import json, sys
over = json.load(open(sys.argv[1]))
for path in ('charkit/spec/clawd.json', 'charkit/spec/clawd_body_pieces.json'):
    s = open(path).read()
    d = json.loads(s)
    G = {g['name']: g for g in d['garments']}
    for k, v in over.items():
        p = k.split('.')
        assert p[0] == 'garments'
        x = G[p[1]]
        for q in p[2:-1]:
            x = x.setdefault(q, {})
        if v is None:
            x.pop(p[-1], None)
        else:
            x[p[-1]] = v
    a = s.index('\n "garments": [')
    depth, i = 0, s.index('[', a)
    for j in range(i, len(s)):
        depth += {'[': 1, ']': -1}.get(s[j], 0)
        if depth == 0:
            break
    txt = json.dumps(d['garments'], indent=1).replace('\n', '\n ')
    s2 = s[:i] + txt + s[j + 1:]
    assert json.loads(s2) == d
    open(path, 'w').write(s2)
    print(path, 'ok')
