"""'YOU!' for the final line ("This game's winner is... YOU!"), spliced in the announcer's name-call cadence: the stressed
vowel high (~330-370 Hz), then falling about 7 semitones into his reverberant tail, like "FOX!" or "Mewtwo!". Every sample
is his own recording (cuts, PSOLA, gains, crossfades).
    .venv/bin/python projects/so-back/vocals/you.py build      # W/you/<recipe>.wav + isolated judges -> vocals/you_eval.json
    .venv/bin/python projects/so-back/vocals/you.py song A B   # render recipes A, B into the full song (round2 harness) + judge
    .venv/bin/python projects/so-back/vocals/you.py audition   # W/you/audition_you.wav: each in the song, bt(60)-.3 .. bt(64)+2.5
"""
import os, sys, json
import numpy as np, soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import words
from words import S, G

OUTD = os.path.join(W, 'you'); os.makedirs(OUTD, exist_ok=True)
# the cadence template (Hz over the vowel core, 0..1): hold high, fall ~7 st, as the real calls do (FOX! 300 -> 200 Hz;
# Mewtwo's "Mew" 340 -> 230 Hz)
FALL = [(0.0, 345), (0.35, 340), (0.8, 245), (1.0, 230)]

YOU = {
    # "Mewtwo!": its "Mew" is /juː/ already falling 340 -> 230 Hz; the m is cut, and the name's own reverberant tail (its "-two"
    # vowel from where its pitch meets the Mew's end, ~230 Hz) is crossfaded on, skipping the t
    'mew+tail':    [S('name_24', 0.115, 0.44, label='m-YOU-(two)'), S('name_24', 0.72, 1.16, xf=0.04, label='mewt-OO tail')],
    'mew':         [S('name_24', 0.115, 0.47, end_fade=0.08, label='m-YOU')],
    # the /j/ glide of another word + the vowel and tail of "Two!" (a count call: 330 -> 250 Hz, then its reverb)
    'yoshi+two':   [S('name_31', 0.0, 0.05, label='YO-shi (j)'), S('name_48', 0.035, 0.52, xf=0.012, label='t-WO!')],
    'young+two':   [S('name_19', 0.0, 0.06, label='YOung (j)'), S('name_48', 0.035, 0.52, xf=0.012, label='t-WO!')],
    # "YOUR" of "Choose your character" (j + the vowel at ~345 Hz) + Mewtwo's falling tail
    'your+tail':   [S('nr_select_04', 0.165, 0.29, label='choose YOU-r'), S('name_24', 0.72, 1.16, xf=0.04, label='mewt-OO tail')],
    # "Continue?"'s -nue /juː/ after the n, re-contoured from its rise to the cadence's fall
    'continue':    [S('nr_1p_02', 0.50, 0.93, pitch=FALL, end_fade=0.12, label='conti-n-YOU (recontoured)')],
    # "Computer"'s /pjuː/ after the p, re-contoured, + Mewtwo's tail
    'computer+tail': [S('name_51', 0.20, 0.33, pitch=[(0, 345), (1, 300)], label='com-p-YOU-ter'),
                      S('name_24', 0.72, 1.16, xf=0.04, label='mewt-OO tail')],
}

SPEC = dict(
    hits=[' You!', ' You.', ' YOU!', ' You?', ' Yu!', ' Youuu!'],
    misses=[f' {m}!' for m in ['Ew', 'Hugh', 'True', 'New', 'Two', 'Yo', 'Ooh', "You're", 'Who', 'Do', 'Blue', 'Q', 'View',
                               'Few', 'Mew', 'Me', 'Yeah', 'Hue', 'Lou', 'Boo', 'Woo', 'Zoo', 'Sue', 'Yule', 'Yuh', 'Your',
                               'Mewtwo', 'Yoohoo', 'Oh', 'Uh']])
CTX_SPEC = dict(hits=[" This game's winner is... You!", " This game's winner is... you!", " This game's winner is... YOU!",
                      " This game's winner is you!"],
                misses=[" This game's winner is..." + m for m in SPEC['misses']] + [" This game's winner is...!",
                                                                                    " This game's winner is... Mewtwo!"])
TARGETS = ['you']

def build(name):
    y, joins, spans = words.assemble(YOU[name])
    return y, joins

def context(y, gap=1.6 - 0.0):
    """The real "This game's winner is..." then YOU on the next bar (1.6 s after the phrase's start, as in the song)."""
    w = load('nr_vs_05'); n = int(1.6 * SR) - 0.05 * 0
    out = np.zeros(max(len(w), int(1.6 * SR)) + len(y))
    out[:len(w)] += w; i = int((1.6 - 0.05) * SR); out[i:i + len(y)] += y
    return out

def main_build():
    import judge
    res = {}
    for name in YOU:
        y, joins = build(name); write(f'{OUTD}/you_{name}.wav', y)
        c = context(y); write(f'{OUTD}/ctx_{name}.wav', c)
        r = dict(recipe=[p.label for p in YOU[name] if isinstance(p, S)], dur=round(len(y) / SR, 3))
        for m in ('small.en', 'medium.en', 'turbo'):
            r['stt_' + m] = judge.transcribe(y, m); r['ctx_' + m] = judge.transcribe(c, m)
        for m in ('small.en', 'medium.en'):
            p, bm, pm = judge.forced(y, SPEC['hits'], SPEC['misses'], m); r['p_' + m], r['miss_' + m] = round(p, 3), f'{bm} ({pm:.2f})'
            p, bm, pm = judge.forced(c, CTX_SPEC['hits'], CTX_SPEC['misses'], m)
            r['pctx_' + m], r['missctx_' + m] = round(p, 3), f'{bm} ({pm:.2f})'
        r['free_hits'] = f"{sum(judge.hit(r[k], TARGETS) for k in r if k.startswith(('stt_', 'ctx_')))}/6"
        r['seams'] = [dict(t=round(t, 3), pct=judge.seam(y, t)[1], f0_st=judge.seam_pitch(y, t)) for t in joins]
        from hf0 import hf0
        t, f, sc, v = hf0(y, SR, hop=.005, fmin=85, fmax=480)
        k = v & (t < 0.12); k2 = v & (t > 0.25) & (t < 0.45)
        r['f0_head'] = round(float(np.median(f[k]))) if k.any() else None
        r['f0_fall'] = round(float(np.median(f[k2]))) if k2.any() else None
        r['score'] = round(np.mean([r['p_small.en'], r['p_medium.en'], r['pctx_small.en'], r['pctx_medium.en']])
                           + int(r['free_hits'].split('/')[0]) / 6, 3)
        res[name] = r
        print(name, r['free_hits'], [r[k] for k in r if k.startswith('stt_')], [r[k] for k in r if k.startswith('ctx_')],
              r['p_small.en'], r['p_medium.en'], r['pctx_small.en'], r['pctx_medium.en'], r['f0_head'], r['f0_fall'], flush=True)
    jdump(dict(sorted(res.items(), key=lambda kv: -kv[1]['score'])), os.path.join(HERE, 'you_eval.json'))

LEAD = 0.04     # the /j/ glide leads the stab: the word starts 40 ms before bt(64)
FINAL_SPEC = dict(hits=[" This game's winner is... You!", " This game's winner is... YOU!", " This game's winner is you!"],
                  misses=[" This game's winner is..." + m for m in [' Two!', ' New!', ' True!', ' Ooh!', ' Who!', ' Mew!',
                          ' Yo!', " You're!", ' Blue!', ' Hugh!', ' Ew!', ' Mewtwo!', ' Captain Falcon!', '!']])

def song(names):
    """Each recipe on the final stab of the full song (round2's arrange rebuild, mix.py's chain), judged in full context."""
    import round2 as R
    out = os.path.join(HERE, 'you_song.json'); res = json.load(open(out)) if os.path.exists(out) else {}
    for n in names:
        stem = R.build_stem(final=None if n == 'falcon' else n); mix = R.full_mix(stem)
        sf.write(os.path.join(OUTD, f'mix_{n}.wav'), mix.astype(np.float32), 48000, subtype='FLOAT')
        r = {}
        for m in ('small.en', 'medium.en'):
            text, ws = R.words_ts(mix, m); r['text_' + m] = text; r['slot_' + m] = R.slot_words(ws, 'final64')
            r['p_' + m], r['miss_' + m] = R.full_forced(mix, ws, 'final64', FINAL_SPEC['hits'], FINAL_SPEC['misses'], m)
        if n != 'falcon':
            solo = R.build_stem(final=n, only='final'); a, b = R.PROXY['final64']
            r['vox_centroid'], r['vox_hf'] = R.bright_stats(solo, a, b); r['vox_f0'] = R.f0_med(solo, a, b)
        res = json.load(open(out)) if os.path.exists(out) else {}
        res[n] = r; json.dump(res, open(out, 'w'), indent=1)
        print(n, {k: v for k, v in r.items() if not k.startswith('text')}, flush=True)

def audition(order):
    """Each candidate in the song: from just before 'This game's winner is...' through the final stab's ring-out."""
    a, b = 24.0 - .3, 28.8
    out, labels, t = [], [], 0.0
    gap = np.zeros((int(.8 * 48000), 2)); f = int(.02 * 48000); ramp = np.linspace(0, 1, f)[:, None]
    for n in order:
        x, sr = sf.read(os.path.join(OUTD, f'mix_{n}.wav'), always_2d=True)
        seg = x[int(a * sr):int(b * sr)].copy(); seg[:f] *= ramp; seg[-f:] *= ramp[::-1]
        labels.append(dict(name=n, t=round(t, 2))); out += [seg, gap]; t += (len(seg) + len(gap)) / sr
    sf.write(os.path.join(OUTD, 'audition_you.wav'), np.concatenate(out).astype(np.float32), 48000, subtype='FLOAT')
    json.dump(labels, open(os.path.join(HERE, 'you_audition.json'), 'w')); print(labels)

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'build'
    if cmd == 'build': main_build()
    elif cmd == 'song': song(sys.argv[2:])
    elif cmd == 'audition': audition(sys.argv[2:])
