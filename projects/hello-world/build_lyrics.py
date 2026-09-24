"""Align the written lyric lines (song/plan.json) with the sung word times (assets/cues.json) -> assets/lyrics.js (window.LINES).
Crowd calls in parentheses are marked call:true. Stage directions {..} are dropped."""
import json, re
plan = json.load(open('song/plan.json')); cues = json.load(open('assets/cues.json'))
norm = lambda w: re.sub(r"[^a-z0-9]", '', w.lower())
sung = [w for w in cues['words'] if norm(w['w'])]
k = 0; lines = []
for ch in plan['chunks']:
    for raw in ch['text'].split('\n'):
        if raw.startswith('[') or raw.startswith('{') or not raw.strip(): continue
        toks, words, paren = raw.split(), [], False
        for tok in toks:
            if tok.startswith('('): paren = True
            found = -1
            for j in range(k, min(len(sung), k + 5)):
                if norm(sung[j]['w']) == norm(tok): found = j; break
            if found >= 0:
                src = sung[found]; k = found + 1
            else:
                prev = words[-1] if words else None
                src = {'t0': prev['t1'] if prev else (sung[k]['t0'] if k < len(sung) else 0), 't1': (prev['t1'] if prev else (sung[k]['t0'] if k < len(sung) else 0)) + .15}
            words.append({'w': tok.strip('()'), 't0': round(src['t0'], 3), 't1': round(src['t1'], 3), 'call': paren})
            if tok.endswith(')') or tok.endswith(')!') or ')' in tok: paren = False
        for q in range(1, len(words)):
            if words[q]['t0'] < words[q - 1]['t0']: words[q]['t0'] = words[q - 1]['t1']; words[q]['t1'] = max(words[q]['t1'], words[q]['t0'] + .12)
        lines.append({'text': raw, 't0': words[0]['t0'], 't1': words[-1]['t1'], 'words': words})
open('assets/lyrics.js', 'w').write('window.LINES = ' + json.dumps(lines) + ';\n')
for L in lines: print(f"{L['t0']:6.2f}-{L['t1']:6.2f}  {L['text']}")
