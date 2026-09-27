"""Check a director run against its script: did every intended hit land, and on which frame?
    .venv/bin/python tools/machinima/melee/report.py SCRIPT.json OSREPORT.log [--calib OUT.json] [--beats cues.json --t0 0]
SCRIPT.json is written by dsl.py next to the generated C (build/NAME.json); OSREPORT.log comes from dolphin.py or plates.py.
Each intent (port, move, intended hit frame, input frame) is matched to the attacker's first HIT at or after its input.
--calib writes the measured first-active frame of each move per character (frames counted from the input, 1-based), which
dsl.Film(calib=...) uses instead of the table. --beats reports each hit's distance from the nearest beat in the cue sheet.
"""
import argparse, json, re


def parse(log):
    hits, ms, marks = [], [], []
    for line in open(log):
        p = line.split()
        if not p: continue
        if p[0] == 'HIT' and len(p) >= 6: hits.append(dict(s=int(p[1]), a=int(p[2]), v=int(p[3]), dmg=float(p[4]), move=int(p[5])))
        elif p[0] == 'IHIT' and len(p) >= 4: hits.append(dict(s=int(p[1]), a=1 - int(p[2]), v=int(p[2]), dmg=float(p[3]), move=-1))
        elif p[0] == 'MS' and len(p) >= 6: ms.append(dict(s=int(p[1]), port=int(p[2]), msid=int(p[3]), x=float(p[4]), y=float(p[5])))
        elif p[0] == 'MARK': marks.append(dict(s=int(p[1]), id=int(p[2])))
    return hits, ms, marks


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('script'); ap.add_argument('log'); ap.add_argument('--calib', default='')
    ap.add_argument('--beats', default=''); ap.add_argument('--t0', type=float, default=0.0)
    ap.add_argument('--hits-js', default='', help='write the matched hits as window.HITS = [{f, who, move}] for a composite')
    ap.add_argument('--fix', default='', help='update the timing solve: add each hit\'s measured lateness to FIX.json')
    a = ap.parse_args()
    sc = json.load(open(a.script)); hits, ms, marks = parse(a.log)
    beats = json.load(open(a.beats))['beats'] if a.beats else []
    used, calib, rows, miss, late, matched = set(), {}, [], 0, {}, []
    for it in sorted(sc['intents'], key=lambda i: i['input']):
        cand = sorted((h for k, h in enumerate(hits) if k not in used and h['a'] == it['port'] and abs(h['s'] - it['hit']) <= 15),
                      key=lambda h: abs(h['s'] - it['hit']))                       # the attacker's nearest hit, within 15 frames
        char = sc['chars'][it['port']]
        if not cand:
            rows.append(f"  MISS  f{it['hit']:5d}  p{it['port']} {char:6s} {it['move']:10s}"); miss += 1; continue
        h = cand[0]; used.add(hits.index(h))
        matched.append({'f': h['s'], 'who': char.upper(), 'move': it['move'].replace('sh_', '').replace('jc_', '')})
        d = h['s'] - it['hit']; first = h['s'] - it['input'] + 1
        late[f"{it['port']}:{it['hit']}"] = d
        calib.setdefault(char, {})[it['move']] = first
        near = ''
        if beats:
            t = a.t0 + h['s'] / sc['fps']; b = min(beats, key=lambda x: abs(x - t)); near = f"  beat {b:6.2f} {1000 * (t - b):+5.0f} ms"
        rows.append(f"  {'ok  ' if d == 0 else 'OFF '}  f{it['hit']:5d}  p{it['port']} {char:6s} {it['move']:10s} hit f{h['s']:5d} ({d:+d})  "
                    f"active f{first}  {h['dmg']:.0f}%{near}")
    print(f"{len(sc['intents'])} intended hits, {len(hits)} logged, {miss} missed")
    print('\n'.join(rows))
    stray = [h for k, h in enumerate(hits) if k not in used]
    if stray: print('unscripted hits:', ', '.join(f"f{h['s']} p{h['a']}>p{h['v']}" for h in stray[:20]))
    if a.hits_js:
        open(a.hits_js, 'w').write('window.HITS = ' + json.dumps(sorted(matched, key=lambda m: m['f'])) + ';\n')
        print('wrote', a.hits_js)
    if a.fix:
        import os
        fx = json.load(open(a.fix)) if os.path.exists(a.fix) else {}
        for k, d in late.items():
            if d: fx[k] = fx.get(k, 0) + d
        json.dump(fx, open(a.fix, 'w'), indent=1, sort_keys=True); print('timing solve: updated', a.fix, f'({sum(1 for d in late.values() if d)} shifted)')
    if a.calib:
        json.dump(calib, open(a.calib, 'w'), indent=1, sort_keys=True); print('wrote', a.calib)
