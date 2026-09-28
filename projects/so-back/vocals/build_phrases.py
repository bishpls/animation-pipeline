"""Build and judge the spliced phrases "it's so over" and "we're so back".
    .venv/bin/python projects/so-back/vocals/build_phrases.py screen     # every word combination, Whisper small.en forced choice
    .venv/bin/python projects/so-back/vocals/build_phrases.py final      # the kept recipes: full judges, deliverables, auditions
Outputs (W = ~/games/melee/work/soback/vocals): cands/ (screen), spliced/<phrase>_<n>_<recipe>[_tuned|_words].wav,
audition_<phrase>.wav (the candidates in rank order, 0.5 s apart), and vocals/phrases_eval.json."""
import os, sys, json, itertools
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import words, judge, specs, vox

PHRASES = {
    'its_so_over': dict(parts=['its', 'so', 'over'], spec=specs.ITS_SO_OVER, gap=0.05,
                        # the sad register of "Game over.": syllables it's, so, o, ver (Hz), a gentle fall
                        tune=[190, 175, 150, 125]),
    'were_so_back': dict(parts=['were', 'so', 'back'], spec=specs.WERE_SO_BACK, gap=0.05,
                         # the hype register of the name calls: a rise to the stressed word, the name-call drop on the last
                         tune=[300, 330, 350]),
}

def build(phrase, recipe, gap=None):
    P = PHRASES[phrase]; g = P['gap'] if gap is None else gap
    parts = [words.word(k, r) for k, r in zip(P['parts'], recipe)]
    return words.phrase([(y, js) for y, js, sp in parts], [g] * (len(parts) - 1)), parts

def syllables(phrase, parts, starts):
    """Syllable spans (for tuning) in phrase time: each word's voiced span; 'over' split at its /v/."""
    out = []
    for (y, js, sp), t0, kind in zip(parts, starts, PHRASES[phrase]['parts']):
        vs = vox.voiced_spans(y)
        a, b = vs[0][0], vs[-1][1]
        if kind == 'over':          # "Game over" from 1.10 s: o until the /v/ at ~1.33 s of the source
            out += [(t0 + a, t0 + 0.22), (t0 + 0.30, t0 + b)]
        else:
            out.append((t0 + a, t0 + b))
    return out

def tuned(phrase, y, parts, starts):
    """Speech-like (not sung) contour in one register: each syllable glides 4% down from its target."""
    syl = syllables(phrase, parts, starts); hz = PHRASES[phrase]['tune']
    snd, manip, _ = vox._manip(y, SR, 75, 600)
    from parselmouth.praat import call
    pt = call('Create PitchTier', 't', snd.xmin, snd.xmax)
    for (a, b), f in zip(syl, hz):
        call(pt, 'Add point', a + 0.01, f * 1.02); call(pt, 'Add point', b - 0.01, f * 0.94)
    call([pt, manip], 'Replace pitch tier')
    return call(manip, 'Get resynthesis (overlap-add)').values[0].copy()

def screen():
    os.makedirs(f'{W}/cands', exist_ok=True)
    res = {}
    for phrase, P in PHRASES.items():
        combos = list(itertools.product(*[list(words.WORDS[k]) for k in P['parts']]))
        rows = []
        for rec in combos:
            (y, joins, starts), parts = build(phrase, rec)
            p, miss, pm = judge.forced(y, P['spec']['hits'], P['spec']['misses'], 'small.en')
            rows.append(dict(recipe=rec, p=round(p, 3), miss=f'{miss} ({pm:.2f})'))
            print(phrase, rec, rows[-1]['p'], rows[-1]['miss'], flush=True)
        res[phrase] = sorted(rows, key=lambda r: -r['p'])
    jdump(res, f'{W}/cands/screen.json')

def final(keep):
    """keep: {phrase: [recipe tuples]} in no particular order; judged fully, ranked, delivered."""
    os.makedirs(f'{W}/spliced', exist_ok=True)
    out = {}
    for phrase, recipes in keep.items():
        P = PHRASES[phrase]; rows = []
        for rec in recipes:
            (y, joins, starts), parts = build(phrase, rec)
            yt = tuned(phrase, y, parts, starts)
            for variant, z in (('native', y), ('tuned', yt)):
                r = judge.evaluate(z, P['spec'], joins=joins)
                hits = sum(judge.hit(r[k], P['spec']['targets']) for k in r if k.startswith(('stt_', 'ctx_')))
                r.update(recipe=list(rec), variant=variant, free_hits=f'{hits}/6', starts=[round(s, 3) for s in starts],
                         dur=round(len(z) / SR, 3))
                r['score'] = round(np.mean([r['phit_small.en'], r['phit_medium.en']]) + hits / 6 + r['phone_p'], 3)
                rows.append((r, z, parts, starts))
                print(phrase, rec, variant, r['free_hits'], r['phit_small.en'], r['phit_medium.en'], r['phone_p'],
                      [r[k] for k in r if k.startswith('stt_')], flush=True)
        rows.sort(key=lambda z: -z[0]['score'])
        aud, labels = [], []
        for n, (r, z, parts, starts) in enumerate(rows, 1):
            tag = f"{phrase}_{n}_{'+'.join(r['recipe'])}_{r['variant']}".replace(' ', '')
            write(f'{W}/spliced/{tag}.wav', z); r['file'] = f'spliced/{tag}.wav'
            # separate words, 0.30 s apart, for placing on beats
            sep, _, _ = words.phrase([(p[0], []) for p in parts], [0.30] * (len(parts) - 1))
            write(f'{W}/spliced/{tag}_words.wav', sep)
            t0 = sum(len(a) for a in aud) / SR
            aud += [z, np.zeros(int(0.5 * SR))]; labels.append(dict(n=n, t=round(t0, 2), file=r['file']))
        write(f'{W}/audition_{phrase}.wav', np.concatenate(aud))
        out[phrase] = dict(ranked=[r for r, *_ in rows], audition=labels)
    jdump(out, os.path.join(HERE, 'phrases_eval.json'))

if __name__ == '__main__':
    if sys.argv[1] == 'screen': screen()
    else:
        keep = json.load(open(os.path.join(HERE, 'keep.json')))
        final({k: [tuple(r) for r in v] for k, v in keep.items()})
