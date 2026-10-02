"""garments8: the separated layer references (paid calls, n=2 each, logged to tools/ledger.jsonl by tools/gptimage.py).

    python tools/garments8/gen.py KEY        # KEY in tools/garments8/prompts_new.json -> charkit/out/garments8/gen/KEY_{1,2}.png
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import gptimage

G = 'charkit/refs/clawd/gen/'
REFS = {'collar_alone': [G + 'base_body_turnaround.png', G + 'bodice_layers.png'],
        'top_layers': [G + 'bodice_layers.png'],
        'bow_alone': [G + 'base_body_turnaround.png', G + 'body_turnaround.png'],
        'collar_ghost': [G + 'bodice_layers.png'],
        'bow_ghost': [G + 'body_turnaround.png']}

if __name__ == '__main__':
    key = sys.argv[1]
    P = json.load(open(os.path.join(ROOT, 'tools/garments8/prompts_new.json')))
    os.chdir(ROOT)
    gptimage.generate(P[key], 'charkit/out/garments8/gen/%s.png' % key, size='2560x1440', quality='high',
                      refs=REFS[key], n=2)
