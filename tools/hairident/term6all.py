"""The shadow edges' clean reading (art_terminator_hair under the hair's shape truth) and peeks at the six placements,
each build as built (tools/hairshell3/term6p.py per build) -> OUT.json {label: term6p's record}.

    python -m charkit script tools/hairident/term6all.py OUT.json LABEL=BUILD ...
"""
import json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
out, res = sys.argv[1], {}
for x in sys.argv[2:]:
    lab, b = x.split('=', 1)
    tmp = out + '.%s.json' % lab
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools/hairshell3/term6p.py'), b, '%s=-' % lab, '--json', tmp],
                   cwd=ROOT, check=True)
    res[lab] = json.load(open(tmp))[lab]
json.dump(res, open(out, 'w'), indent=1)
print(json.dumps({k: (v['terminator_hair']['place'], v['terminator_hair']['mean'], v['terminator_hair']['views'],
                      v['peeks_hair']['place']) for k, v in res.items()}))
