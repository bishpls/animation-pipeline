"""set the clips (crab, star) in the six specs' accessories blocks, only that block's text changing.
    python specs.py CLIPS.json [--only clawd.json]      CLIPS.json: {"crab": {...}, "star": {...}} (whole entries) or
                                                         {"set": {"crab.shape.body_d": 0.34, ...}}"""
import json, os, sys, re
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SPECS = ['clawd.json', 'clawd_body.json', 'clawd_body_pieces.json', 'clawd_code.json', 'clawd_locks.json', 'clawd_mh.json']


def block_span(txt):
    i = txt.index('"accessories": [')
    j = txt.index('[', i)
    depth = 0
    for k in range(j, len(txt)):
        if txt[k] == '[': depth += 1
        elif txt[k] == ']':
            depth -= 1
            if depth == 0:
                return j, k + 1
    raise ValueError


def apply(entries, change):
    out = []
    for a in entries:
        a = json.loads(json.dumps(a))
        if 'set' in change:
            for path, v in change['set'].items():
                kind, *keys = path.split('.')
                if a['kind'] != kind: continue
                d = a
                for k in keys[:-1]: d = d.setdefault(k, {})
                if v is None: d.pop(keys[-1], None)
                else: d[keys[-1]] = v
        elif a['kind'] in change:
            a = change[a['kind']]
        out.append(a)
    return out


def main(args):
    change = json.load(open(args[0]))
    only = args[args.index('--only') + 1] if '--only' in args else None
    for name in SPECS:
        if only and name != only: continue
        p = os.path.join(ROOT, 'charkit/spec', name)
        txt = open(p).read()
        a, b = block_span(txt)
        entries = json.loads(txt[a:b])
        new = apply(entries, change)
        # indentation: the block's own (the line's leading spaces)
        line_start = txt.rfind('\n', 0, a) + 1
        ind = len(txt[line_start:a]) - len(txt[line_start:a].lstrip())
        body = json.dumps(new, indent=1)
        body = body.replace('\n', '\n' + ' ' * ind)
        open(p, 'w').write(txt[:a] + body + txt[b:])
        print(name, 'ok')


if __name__ == '__main__':
    main(sys.argv[1:])
