"""Print a director run as action timelines: per labelled segment (dsl Film.mark(t, id, label)), each fighter's motion states
with their start frame (relative to the segment), duration and position, and the hits.
    .venv/bin/python tools/machinima/melee/timeline.py SCRIPT.json OSREPORT.log [--only TEXT]
Motion ids are Melee's (common: 14 Wait, 15-17 Walk, 20 Dash, 24 KneeBend (jumpsquat), 25/26 Jump, 29 Fall, 42 Landing,
43 LandingFallSpecial (wavedash landing), 65-69 aerials, 70-74 their landings, 236 EscapeAir (air dodge); character specials
start at 341, e.g. Fox's shine 360-363 on the ground, 365-368 in the air).
"""
import argparse, json
from report import parse

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('script'); ap.add_argument('log'); ap.add_argument('--only', default='')
    a = ap.parse_args()
    sc = json.load(open(a.script)); hits, ms, _ = parse(a.log)
    labels = sc.get('labels') or [[0, 'all']]
    for k, (t0, lab) in enumerate(labels):
        if a.only and a.only not in lab: continue
        t1 = labels[k + 1][0] if k + 1 < len(labels) else sc['len']
        hh = [f"f{h['s'] - t0} p{h['a']}>p{h['v']} {h['dmg']:.0f}%" for h in hits if t0 <= h['s'] < t1]
        print(f"[{k + 1:2d}] {lab}   hits: {', '.join(hh) or '-'}")
        for p in range(len(sc['chars'])):
            seq = [e for e in ms if e['port'] == p and t0 <= e['s'] < t1]
            tl = [f"{e['msid']}@{e['s'] - t0}({(seq[i + 1]['s'] if i + 1 < len(seq) else t1) - e['s']}) x{e['x']:+.1f}"
                  + (f" y{e['y']:.1f}" if abs(e['y']) > 0.05 else '') for i, e in enumerate(seq)]
            if tl: print(f"   p{p}: " + '  '.join(tl))
