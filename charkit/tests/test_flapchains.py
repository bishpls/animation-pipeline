"""charkit.flapchains' notes writer on hand-wrapped entries (venv: run this file, or pytest)."""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import flapchains

NOTES = '''{
 "name": "x",
 "pieces": [
  {"id": "top", "type": "top", "side": "C",
   "why": "a comma, a } and a ] in a string"},
  {"id": "flap_L", "type": "overskirt panel", "side": "L",
   "parent": "waistband", "over": ["skirt"],
   "views": ["front", "back"]},
  {"id": "flap_R", "type": "overskirt panel", "side": "R", "chain": [[0, 0, 0]]},
  {"id": "shorts", "type": "shorts"}
 ]
}
'''


def test_multiline_entries():
    C = {'flap_L': [[0.1, 0.2, -1.4], [0.1, 0.3, -2.4]], 'flap_R': [[-0.1, 0.2, -1.4], [-0.1, 0.3, -2.4]]}
    text, done = flapchains.set_chains(NOTES, C)
    assert done == ['flap_L', 'flap_R']
    N = json.loads(text)
    by = {p['id']: p for p in N['pieces']}
    assert by['flap_L']['chain'] == C['flap_L'] and by['flap_R']['chain'] == C['flap_R']
    assert by['flap_L']['views'] == ['front', 'back'] and by['flap_L']['over'] == ['skirt']
    # the other entries are byte for byte
    for pid in ('top', 'shorts'):
        a = next(s for s in flapchains.piece_spans(NOTES) if s[0] == pid)
        assert NOTES[a[1]:a[2]] in text
    # idempotent: writing the same chains again changes nothing
    assert flapchains.set_chains(text, C)[0] == text


def test_real_notes_parse():
    path = os.path.join(flapchains.ROOT, 'charkit', 'refs', 'clawd', 'outfit_notes.json')
    if not os.path.exists(path):
        return
    text = open(path).read()
    ids = [s[0] for s in flapchains.piece_spans(text)]
    assert ids == [p['id'] for p in json.loads(text)['pieces']]


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
