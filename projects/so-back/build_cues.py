"""SO BACK's cue sheet: the take's analysis (assets/cues.json from tools/audio_analyze.py --bpm 150 --downbeat 0.05) with the
sections pinned to the bar grid, written as assets/cues.js for the page.
    ../../.venv/bin/python build_cues.py"""
import json, os
H = os.path.dirname(os.path.abspath(__file__))
c = json.load(open(os.path.join(H, 'assets/cues.json')))
O, BAR = c['offset'], 4 * 60 / c['bpm']
bar = lambda n: round(O + (n - 1) * BAR, 4)           # bar n (1-based) downbeat
c['sections'] = [
    {'name': 'cold', 't0': 0.0, 't1': bar(3)},        # bars 1-2: the drop, flash-forward; tape-stop into
    {'name': 'over', 't0': bar(3), 't1': bar(7)},     # bars 3-6: music box, no drums (half-time)
    {'name': 'turn', 't0': bar(7), 't1': bar(9)},     # bars 7-8: riser, one beat of silence
    {'name': 'drop', 't0': bar(9), 't1': bar(13)},    # bars 9-12
    {'name': 'drop2', 't0': bar(13), 't1': bar(17)},  # bars 13-16
    {'name': 'end', 't0': bar(17), 't1': c['duration']},
]
json.dump(c, open(os.path.join(H, 'assets/cues.json'), 'w'), indent=1)
open(os.path.join(H, 'assets/cues.js'), 'w').write('window.CUES = ' + json.dumps(c) + ';\n')
print({s['name']: (s['t0'], s['t1']) for s in c['sections']})
