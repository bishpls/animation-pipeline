"""Recompute seam measures (crossfade seams only; gaps and closures are not seams) for the judged phrases."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import judge, build_phrases as bp, words
p = os.path.join(HERE, 'phrases_eval.json'); d = json.load(open(p))
for ph, v in d.items():
    for r in v['ranked']:
        (y, joins, starts), parts = bp.build(ph, tuple(r['recipe']))
        if r['variant'] == 'tuned': y = bp.tuned(ph, y, parts, starts)
        labels = []
        for kind, rec in zip(bp.PHRASES[ph]['parts'], r['recipe']):
            ps = [q for q in words.WORDS[kind][rec] if isinstance(q, words.S)]
            labels += [f'{a.label}|{b.label}' for a, b in zip(ps, ps[1:])]
        r['seams'] = [dict(seam=l, t=round(t, 3), pct=judge.seam(y, t)[1], f0_st=judge.seam_pitch(y, t)) for l, t in zip(labels, joins)]
        print(ph, r['recipe'], r['variant'], [(s['seam'], s['pct'], s['f0_st']) for s in r['seams']])
jdump(d, p)
