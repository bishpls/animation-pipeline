"""Round 2 of the vocals (Michael's first listen: the hook "we're so back" and the sad "so" were shrill). Builds hook and
"so" variants, renders each into the WHOLE song (arrange.py's stem with only that slot swapped, then mix.py's chain), and
judges them in full-file context: Whisper small/medium free transcription of the full mix, a full-context forced choice
at each slot, and a shrillness proxy (spectral centroid and share of energy above 3 kHz, vocal alone and in the mix).
    .venv/bin/python projects/so-back/vocals/round2.py [check|hooks|sos|audition]
arrange.py is the coordinator's file: this imports it and never edits it. `build_stem` is arrange.main() with the hook
and sad-line sections made pluggable; `check` proves that with the current settings it reproduces W/stem.wav."""
import os, sys, json, importlib.util
import numpy as np, soundfile as sf, librosa
from scipy.signal import butter, sosfiltfilt, lfilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import W, SR, write, load
import words, vox, judge, specs
import arrange as A
from arrange import BEAT, bt, OUT_SR, word, word_syl, vline, up, phrase, lowpass, tune, PH

HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
_spec = importlib.util.spec_from_file_location('somix', os.path.join(PROJ, 'mix.py')); M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)
R2 = os.path.join(W, 'round2'); os.makedirs(R2, exist_ok=True)
C3, Eb3, F3, G3, Ab3, Bb3 = 48, 51, 53, 55, 56, 58
C4, D4, Eb4, F4, G4, Ab4, Bb4, C5, D5, Eb5 = 60, 62, 63, 65, 67, 68, 70, 72, 74, 75

# ------------------------------------------------------------------------------------------------ tone shaping
def shelf(y, db=-4.0, f=3500, sr=OUT_SR):
    """A gentle high shelf (RBJ biquad, S=0.7): db above f. (The same filter as vox.shelf, which arrange.py should use.)"""
    if not db: return y
    Aa = 10 ** (db / 40); w = 2 * np.pi * f / sr; cs, sn = np.cos(w), np.sin(w); al = sn / 2 * np.sqrt((Aa + 1 / Aa) * (1 / .7 - 1) + 2)
    b = [Aa * ((Aa + 1) + (Aa - 1) * cs + 2 * np.sqrt(Aa) * al), -2 * Aa * ((Aa - 1) + (Aa + 1) * cs),
         Aa * ((Aa + 1) + (Aa - 1) * cs - 2 * np.sqrt(Aa) * al)]
    a = [(Aa + 1) - (Aa - 1) * cs + 2 * np.sqrt(Aa) * al, 2 * ((Aa - 1) - (Aa + 1) * cs), (Aa + 1) - (Aa - 1) * cs - 2 * np.sqrt(Aa) * al]
    return lfilter(np.array(b) / a[0], np.array(a) / a[0], y)

def deess(y, band=(3500, 6000), thr_db=-26, ratio=3.0, sr=OUT_SR):
    """A split-band de-esser: the 3.5-6 kHz band is compressed (5 ms attack, 60 ms release) above thr_db (its own RMS)."""
    sos = butter(4, band, 'band', fs=sr, output='sos'); hi = sosfiltfilt(sos, y); lo = y - hi
    env = np.abs(hi); a = np.exp(-1 / (.06 * sr)); env = lfilter([1 - a], [1, -a], env)
    lev = 20 * np.log10(env + 1e-9); over = np.maximum(0, lev - thr_db)
    return lo + hi * 10 ** (-over * (1 - 1 / ratio) / 20)

def tone(y, t):
    """t: dict(shelf_db, shelf_f, deess) applied to a 48 kHz vocal."""
    if t.get('deess'): y = deess(y, thr_db=t['deess'])
    return shelf(y, t.get('shelf_db', 0.0), t.get('shelf_f', 3500))

# ------------------------------------------------------------------------------------------------ hook variants
CUR = A.SUNG
def sung_parts(recs, notes, beats, lens, bright, scale=.85, tone_=None):
    parts = []
    for kind, rec, n, b, l in zip(('were', 'so', 'back'), recs, notes, beats, lens):
        y = word(kind, rec); syl = word_syl(kind, y)
        z = up(vox.sing(y, [n], syl=syl, durs=[l * BEAT * scale]), bright=bright)
        parts.append((tone(z, tone_ or {}), bt(b) - syl[0][0]))
    return parts

def spoken_tuned_parts(recs, beats, bright, tone_=None, shift=0):
    """The spoken words at their own length, each syllable hard-tuned to the nearest C minor tone (arrange.tune)."""
    parts = []
    for kind, rec, b in zip(('were', 'so', 'back'), recs, beats):
        y = word(kind, rec); syl = word_syl(kind, y)
        z = up(tune(kind, y, shift=shift), bright=bright)
        parts.append((tone(z, tone_ or {}), bt(b) - syl[0][0]))
    return parts

def dbl_of(parts_fn, semis, formant=None):
    """An octave double: the same words shifted (after singing) by semis."""
    return parts_fn(lambda z: vox.pitch_shift(z, semis, formant=formant))

HOOKS = {
    'H0_current': dict(desc='current: sung G4 C5 Eb5 (b40: G4 Bb4 D5), octave-up formant x1.25 double -8/-9 dB, bright .3',
                       mode='sung', recs=(CUR['were'], CUR['so_back'], CUR['back']), c=(G4, C5, Eb5), g=(G4, Bb4, D5),
                       bright=.3, dbl=dict(semis=12, formant=1.25), tone={}),
    'H1_spoken1_tuned': dict(desc='spoken #1 (winner-n, single+no, break+hand+complete) at its own length, each syllable '
                             'hard-tuned to the nearest C minor tone; bright .1, shelf -3 dB @3.5k',
                             mode='spoken', recs=('winner-n', 'single+no', 'break+hand+complete'), bright=.1,
                             tone=dict(shelf_db=-3)),
    'H2_spoken2_tuned': dict(desc='spoken #2 (wins+master, surv+no, break+hand+complete), nearest C minor tones; bright .1, shelf -3',
                             mode='spoken', recs=('wins+master', 'surv+no', 'break+hand+complete'), bright=.1,
                             tone=dict(shelf_db=-3)),
    'H3_low_CEbG': dict(desc='sung C4 Eb4 G4 (b40: Bb3 D4 F4), sung recipes; bright .1, shelf -3 dB, de-ess',
                        mode='sung', recs=(CUR['were'], CUR['so_back'], CUR['back']), c=(C4, Eb4, G4), g=(Bb3, D4, F4),
                        bright=.1, tone=dict(shelf_db=-3, deess=-28)),
    'H4_low_EbFG': dict(desc='sung Eb4 F4 G4 (b40: D4 F4 G4... over Gm7: D4 Eb4 F4), sung recipes; bright .1, shelf -3, de-ess',
                        mode='sung', recs=(CUR['were'], CUR['so_back'], CUR['back']), c=(Eb4, F4, G4), g=(D4, Eb4, F4),
                        bright=.1, tone=dict(shelf_db=-3, deess=-28)),
    'H5_low_CEbG_8vb': dict(desc='H3 plus an octave-DOWN double (PSOLA -12, formants kept) at -5 dB for weight',
                            mode='sung', recs=(CUR['were'], CUR['so_back'], CUR['back']), c=(C4, Eb4, G4), g=(Bb3, D4, F4),
                            bright=.1, dbl=dict(semis=-12, formant=None, gain=-5), tone=dict(shelf_db=-3, deess=-28)),
    'H6_8vb_melody': dict(desc='the current melody an octave down, G3 C4 Eb4 (b40: G3 Bb3 D4), with the low "winner" of '
                          '"This game\'s WINNER is" (recorded ~165-210 Hz); bright .1, shelf -3, de-ess',
                          mode='sung', recs=('lowwinner', CUR['so_back'], CUR['back']), c=(G3, C4, Eb4), g=(G3, Bb3, D4),
                          bright=.1, tone=dict(shelf_db=-3, deess=-28)),
    'H7_low_CEbG_layer': dict(desc='H3 with the dry spoken "back" (break+hand+complete, natural pitch ~160 Hz) layered under the '
                              'sung one at -6 dB, onsets aligned', mode='sung', recs=(CUR['were'], CUR['so_back'], CUR['back']),
                              c=(C4, Eb4, G4), g=(Bb3, D4, F4), bright=.1, tone=dict(shelf_db=-3, deess=-28),
                              layer=dict(rec='break+hand+complete', gain=-6)),
    'H8_cadence': dict(desc='the name-call cadence, sung: C4 Eb4 then "back" DOWN on G3 with the low "hand" /ae/ (recorded '
                       '~160 Hz: break+hand+complete) (b40: Bb3 D4 G3); bright .1, shelf -3, de-ess',
                       mode='sung', recs=(CUR['were'], CUR['so_back'], 'break+hand+complete'), c=(C4, Eb4, G3), g=(Bb3, D4, G3),
                       bright=.1, tone=dict(shelf_db=-3, deess=-28)),
    # round 2b: the spoken #2 words carry "back" best, so keep their "back" and sing only "we're so"
    'H9_sung_spokenback': dict(desc='"we\'re so" sung C4 Eb4 (sung recipes), then the spoken #2 "back" (break+hand+complete) at '
                               'its own length, hard-tuned to the nearest C minor tone (recorded ~160 Hz: Eb3); b40: Bb3 D4 + '
                               'back; bright .1, shelf -3, de-ess', mode='hybrid',
                               recs=(CUR['were'], CUR['so_back'], 'break+hand+complete'), c=(C4, Eb4, None), g=(Bb3, D4, None),
                               bright=.1, tone=dict(shelf_db=-3, deess=-28)),
    'H10_spoken2_tuned_up2': dict(desc='spoken #2, each syllable tuned to the C minor tone nearest its recorded pitch +2 st '
                                  '(a slightly brighter, still chest-register take); bright .1, shelf -3',
                                  mode='spoken', recs=('wins+master', 'surv+no', 'break+hand+complete'), bright=.1, shift=2,
                                  tone=dict(shelf_db=-3)),
    'H11_spoken2_sungso': dict(desc='spoken #2 "we\'re" and "back" (nearest C minor tones) with "so" held longer and sung on '
                               'Eb4 (the hook\'s one sustained note); bright .1, shelf -3', mode='hybrid2',
                               recs=('wins+master', 'surv+no', 'break+hand+complete'), c=(None, Eb4, None), g=(None, D4, None),
                               bright=.1, tone=dict(shelf_db=-3)),
}

def hook_parts(h, beats, which='c'):
    """-> (main parts, double parts or None, layer parts or None) for one statement of the hook on beats (b, b+1, b+2)."""
    if h['mode'] == 'spoken':
        return spoken_tuned_parts(h['recs'], beats, h['bright'], h.get('tone'), shift=h.get('shift', 0)), None, None
    if h['mode'] in ('hybrid', 'hybrid2'):
        # per word: a note sings it (len .9 beat), None keeps it spoken and tuned to the nearest C minor tone
        sp = spoken_tuned_parts(h['recs'], beats, h['bright'], h.get('tone'))
        sg = sung_parts(h['recs'], [n or C4 for n in h[which]], beats, (.9, .9, 1.6), h['bright'], tone_=h.get('tone'))
        return [g if n is not None else s_ for n, s_, g in zip(h[which], sp, sg)], None, None
    notes = h[which]; lens = (.9, .9, 1.6)
    main = sung_parts(h['recs'], notes, beats, lens, h['bright'], tone_=h.get('tone'))
    dbl = None
    if h.get('dbl'):
        d = h['dbl']; dbl = []
        for kind, rec, n, b, l in zip(('were', 'so', 'back'), h['recs'], notes, beats, lens):
            y = word(kind, rec); syl = word_syl(kind, y)
            z = vox.pitch_shift(vox.sing(y, [n], syl=syl, durs=[l * BEAT * .85]), d['semis'], formant=d['formant'])
            dbl.append((tone(up(z, bright=h['bright']), h.get('tone') or {}), bt(b) - syl[0][0]))
    lay = None
    if h.get('layer'):
        y = word('back', h['layer']['rec']); syl = word_syl('back', y)
        lay = [(tone(up(y, bright=0), h.get('tone') or {}), bt(beats[2]) - syl[0][0])]
    return main, dbl, lay

# ------------------------------------------------------------------------------------------------ "so" variants
SOS = {
    'S0_current': dict(desc='current: sudden+no ("NO contest" o, ~350 Hz) sung G4, len 1.2 beats', rec='sudden+no', note=G4, len=1.2),
    'S1_no_soft_Eb4': dict(desc='the No-contest o, shorter (0.09-0.30), s -3 dB, sung Eb4, len .9, 60 ms fade-in on the vowel, '
                           'shelf -4 dB', rec='sudden+no.soft', note=Eb4, len=.9, attack=.06, tone=dict(shelf_db=-4)),
    'S2_mario_G3': dict(desc='s + Mario\'s long final o (recorded 240->150 Hz, the long "O"), sung G3, len 1.2, shelf -3',
                        rec='sudden+mario', note=G3, len=1.2, tone=dict(shelf_db=-3)),
    'S3_mario_Bb3': dict(desc='s + Mario\'s o sung Bb3, len 1.2, shelf -3', rec='sudden+mario', note=Bb3, len=1.2, tone=dict(shelf_db=-3)),
    'S4_falco_G3': dict(desc='s + Falco\'s o (recorded 220->150 Hz) sung G3, len 1.2, shelf -3', rec='sudden+falco', note=G3, len=1.2,
                        tone=dict(shelf_db=-3)),
    'S5_mario_natural': dict(desc='s + Mario\'s o NOT tuned: his own falling glide, shifted to start near Bb3 (+0 st), len 1.2',
                             rec='sudden+mario', note=None, len=1.2, tone=dict(shelf_db=-3)),
    'S6_bonus_G3': dict(desc='s + the o of "BOnus" (recorded ~170 Hz, short, stretched), sung G3, len 1.0, shelf -3',
                        rec='sudden+bonus', note=G3, len=1.0, tone=dict(shelf_db=-3)),
    'S7_overo_Eb3': dict(desc='s + "Game Over"\'s own o (recorded ~111 Hz) sung Eb3 (+6 st), len 1.0, shelf -3',
                         rec='sudden+overo', note=Eb3, len=1.0, tone=dict(shelf_db=-3)),
    'S8_overo_F3': dict(desc='s + "Game Over"\'s own o sung F3 (+8 st), len 1.0, shelf -3', rec='sudden+overo', note=F3, len=1.0,
                        tone=dict(shelf_db=-3)),
    'S9_overo_G3': dict(desc='s + "Game Over"\'s own o sung G3 (+10 st), len 1.0, shelf -3', rec='sudden+overo', note=G3, len=1.0,
                        tone=dict(shelf_db=-3)),
    'S10_falco_Bb3': dict(desc='s + Falco\'s o sung Bb3 (+1 st), len 1.2, shelf -3', rec='sudden+falco', note=Bb3, len=1.2,
                          tone=dict(shelf_db=-3)),
    'S11_falco_Eb3': dict(desc='s + Falco\'s o sung Eb3 (-5 st), len 1.2, shelf -3', rec='sudden+falco', note=Eb3, len=1.2,
                          tone=dict(shelf_db=-3)),
}

def so_part(s, bright=.3):
    y = word('so', s['rec']); syl = word_syl('so', y)
    if s['note'] is None:      # duration only: the vowel stretched to len beats, keeping his recorded glide
        a, b = syl[0]; z = _stretch(y, a, b, s['len'] * BEAT * .85 / (b - a))
    else:
        z = vox.sing(y, [s['note']], syl=syl, durs=[s['len'] * BEAT * .85])
    z = up(z, bright=bright)
    if s.get('attack'):
        a = syl[0][0]; i0 = int(a * OUT_SR); n = int(s['attack'] * OUT_SR)
        z = z.copy(); z[i0:i0 + n] *= np.linspace(.35, 1, n)
    return tone(z, s.get('tone') or {}), bt(9.25) - syl[0][0]

def _stretch(y, a, b, fac):
    import parselmouth
    from parselmouth.praat import call
    snd, manip, _ = vox._manip(y, SR, 75, 600)
    pt = call(manip, 'Extract pitch tier'); call([pt, manip], 'Replace pitch tier')
    dt = call('Create DurationTier', 'd', snd.xmin, snd.xmax)
    for tt, f in ((a - .001, 1), (a + .001, fac), (b - .001, fac), (b + .001, 1)): call(dt, 'Add point', tt, f)
    call([dt, manip], 'Replace duration tier')
    vox._seed(); return call(manip, 'Get resynthesis (overlap-add)').values[0].copy()

# ------------------------------------------------------------------------------------------------ the stem (arrange.main, pluggable)
def build_stem(hook='H0_current', so='S0_current', only=None, final=None):
    """arrange.main() with the hook statements (b0, b4 echo, b33, b40, b52 stutter) and the sad line's "so" (b8, and the b21
    echo) swapped for the named variants. only='hook'|'so'|'final': return just that slot's vocal (for the shrillness proxy).
    final: None keeps arrange's "CAPTAIN FALCON!" on the final stab; a you.py recipe name puts that "YOU!" there instead."""
    h, s = HOOKS[hook], SOS[so]
    bus, CAP = A.Bus(28.9), []
    solo = A.Bus(28.9)
    def add(y, t, g=0, keep=None, **k):
        bus.add(y, t, g, **k)
        if keep and keep == only: solo.add(y, t, g, **k)
    # ---- cold open
    main, dbl, lay = hook_parts(h, (0, 1, 2), 'c')
    main[0] = (main[0][0], max(0.0, main[0][1]))
    y, t0 = vline(main); add(y, t0, 0, 'hook', send=.25, rt60=1.2)
    if dbl:
        dbl[0] = (dbl[0][0], max(0.0, dbl[0][1])); yd, td = vline(dbl)
        if h['dbl']['semis'] > 0:   # the current octave-up double: -9 under the hook, then the b4 chipmunk echo at -6
            add(yd, td, -9, 'hook', pan=.3, send=.2, rt60=1.2); add(yd, td + 4 * BEAT, -6, 'hook', pan=-.35, send=.3, rt60=1.2)
        else:
            add(yd, td, h['dbl']['gain'], 'hook', send=.2, rt60=1.2); add(yd, td + 4 * BEAT, -6, 'hook', pan=-.35, send=.3, rt60=1.2)
    else:   # no double: the b4 echo is the hook itself through a 2.5 kHz low-pass ("radio"), -8 dB, panned
        add(lowpass(y, 2500), t0 + 4 * BEAT, -8, 'hook', pan=-.35, send=.3, rt60=1.2)
    if lay:
        yl, tl = vline(lay); add(yl, tl, h['layer']['gain'], 'hook', send=.1, rt60=1.2)
    # ---- over (b8): it's (Eb4) + the variant's so + over (+3 st)
    its = A.sung([('its', CUR['its'], [A.Eb4], [8], [.6])])
    sp = so_part(s)
    ov = word('over', CUR['over']); osyl = word_syl('over', ov)
    over = its + [sp, (up(vox.pitch_shift(ov, 3)), bt(11) - osyl[0][0])]
    y, t1 = vline(over); add(lowpass(y, 6000), t1, -1, 'so', send=.5, rt60=2.8)
    g = up(phrase('game_over'), bright=0)
    bus.add(lowpass(g, 3000), bt(16) - PH['game_over']['syllables'][0]['t0'], -2, send=.6, rt60=2.8)
    # b21 echo: the spoken spliced "it's so over" (-2 st); with a new so, the same phrase rebuilt with it
    if so == 'S0_current':
        e, _ = sf.read(os.path.join(W, 'spliced', 'its_so_over_1_is+t+sudden+no+gameover_native.wav'))
    else:
        (e, _, _), _ = __import__('build_phrases').build('its_so_over', ('is+t', s['rec'], 'gameover'))
    e = up(vox.pitch_shift(e.astype(float), -2), bright=0)
    add(lowpass(e[:int(2.2 * OUT_SR)], 5000), bt(21), -6, 'so', pan=-.2, send=.6, rt60=3.2)
    # ---- the turn (unchanged)
    c = phrase('continue'); bus.add(up(c), bt(24) - .01, -1, send=.12, rt60=1.0)
    five = up(phrase('five')); cut = int((bt(27) - bt(26)) * OUT_SR); a = five[:cut].copy(); a[-480:] *= np.linspace(1, 0, 480)
    bus.add(a, bt(26) - .09, 0, send=.1, rt60=1.0); bus.add(five, bt(27) - .09, 0, send=.2, rt60=1.0)
    bus.add(up(phrase('ready')), bt(30) - .23, 0, send=.2, rt60=1.4)
    # ---- the drop: b33 hook (+ its double), b40 hook on the Gm7 notes
    main, dbl, lay = hook_parts(h, (33, 34, 35), 'c')
    y, t2 = vline(main); add(y, t2, 0, 'hook', send=.2, rt60=1.2)
    if dbl:
        yd, td = vline(dbl)
        if h['dbl']['semis'] > 0: add(yd, td, -8, 'hook', pan=.3, send=.2, rt60=1.2); add(yd, td + .012, -10, 'hook', pan=-.3)
        else: add(yd, td, h['dbl']['gain'], 'hook', send=.2, rt60=1.2)
    if lay: yl, tl = vline(lay); add(yl, tl, h['layer']['gain'], 'hook', send=.1, rt60=1.2)
    s_ = tune('success', phrase('success')); bus.add(up(s_), bt(36) - .07, 1, send=.15, rt60=1.0)
    s_ = tune('complete', phrase('complete', trim=.66)); bus.add(up(s_), bt(38) - .01, 1, send=.15, rt60=1.0)
    main, dbl, lay = hook_parts(h, (40, 41, 42), 'g')
    y, t3 = vline(main); add(y, t3, 0, 'hook', send=.2, rt60=1.2)
    if lay: yl, tl = vline(lay); add(yl, tl, h['layer']['gain'], 'hook', send=.1, rt60=1.2)
    s_ = phrase('a_new_record', trim=1.38); bus.add(up(s_), bt(44) - .01, 1, send=.15, rt60=1.0)
    # ---- drop 2
    s_ = tune('choose', phrase('choose_your_character')); bus.add(up(s_), bt(48) - .1, 0, send=.15, rt60=1.0)
    st = []
    if h['mode'] in ('spoken', 'hybrid', 'hybrid2'):
        m, _, _ = hook_parts(h, (52, 53, 54), 'c')
        for (z, t), extra in zip(m, (.5, .5, None)):
            st.append((z, t))
            if extra: st.append((z, t + extra * BEAT))
    else:
        nw, ns, nb = h['c']
        for (k, r, n), bs in ((('were', h['recs'][0], nw), (52, 52.5)), (('so', h['recs'][1], ns), (53, 53.5))):
            y0 = word(k, r); z = tone(up(vox.sing(y0, [n], syl=word_syl(k, y0), durs=[.4 * BEAT]), bright=h['bright']), h.get('tone') or {})
            lead = word_syl(k, y0)[0][0]
            for b in bs: st.append((z, bt(b) - lead))
        y0 = word('back', h['recs'][2])
        zb = tone(up(vox.sing(y0, [nb], syl=word_syl('back', y0), durs=[1.8 * BEAT]), bright=h['bright']), h.get('tone') or {})
        st.append((zb, bt(54) - word_syl('back', y0)[0][0]))
    y, t4 = vline(st); add(y, t4, 0, 'hook', send=.2, rt60=1.2)
    s_ = tune('wow', phrase('wow_incredible', trim=1.66)); bus.add(up(s_), bt(56) - .04, 1, send=.15, rt60=1.0)
    s_ = phrase('this_games_winner_is'); bus.add(up(s_), bt(60) - .03, 0, send=.3, rt60=1.8)
    if final is None:
        cf = load('name_00'); bus.add(up(cf), bt(64) - .02, -1.5, send=.35, rt60=2.2)
    else:
        import you
        yy, _ = you.build(final); z = tone(up(yy, bright=.1), dict(shelf_db=-2))
        add(z, bt(64) - you.LEAD, -1.5, 'final', send=.35, rt60=2.2)
    return solo.mix() if only else bus.mix()

def full_mix(stem):
    song = M.decode(os.path.join(PROJ, 'assets/song.mp3')); n = len(song)
    v = np.zeros((n, 2)); m = min(n, len(stem)); v[:m] = stem[:m]; v *= 10 ** (-2.5 / 20)
    sfxp = os.path.expanduser('~/games/melee/work/soback/sfx/stem.wav')
    sfx = M.stem(sfxp, n)
    return M.limit(M.tape_stop(M.duck(song, v) + v, M.TS0, M.TS1) + sfx)

# ------------------------------------------------------------------------------------------------ judges
SLOTS = {'final64': (bt(60) - .3, 28.8), 'hook0': (0.0, bt(3.6)), 'hook33': (bt(33) - .3, bt(36) - .1), 'hook40': (bt(40) - .3, bt(43) - .1),
         'hook52': (bt(52) - .3, bt(56) - .1), 'over8': (bt(8) - .3, bt(12.5))}
PROXY = {'final64': (bt(64) - .05, bt(64) + .6), 'over8': (bt(9.25) - .15, bt(9.25) + .5), 'hook33': (bt(33) - .2, bt(35.5)), 'hook40': (bt(40) - .2, bt(42.5)),
         'hook0': (0.0, bt(2.5)), 'hook52': (bt(52) - .2, bt(54.5))}   # the sung words themselves (for over8: the "so")

def words_ts(x48, name):
    y = librosa.resample(x48.mean(1) if x48.ndim > 1 else x48, orig_sr=OUT_SR, target_sr=16000).astype(np.float32)
    r = judge.model(name).transcribe(y, fp16=False, language='en', temperature=0.0, word_timestamps=True)
    return r['text'].strip(), [(w['word'], w['start'], w['end']) for s_ in r['segments'] for w in s_['words']]

def full_forced(x48, ws, slot, hits, misses, name):
    """Full-file forced choice: the model's own transcript, with the words inside the slot replaced by each candidate."""
    a, b = SLOTS[slot]
    pre = ''.join(w for w, s0, s1 in ws if s1 <= a + .05); post = ''.join(w for w, s0, s1 in ws if s0 >= b - .05)
    y = librosa.resample(x48.mean(1), orig_sr=OUT_SR, target_sr=16000).astype(np.float32)
    m = judge.model(name)
    import whisper, torch
    tok = whisper.tokenizer.get_tokenizer(multilingual=m.is_multilingual, language='en', task='transcribe')
    mel = whisper.log_mel_spectrogram(whisper.pad_or_trim(torch.tensor(y)), n_mels=m.dims.n_mels)[None]
    with torch.no_grad():
        enc = m.encoder(mel); sc = {}
        for c in hits + misses:
            text = (pre.rstrip() + c + ' ' + post.lstrip()).strip()
            ids = list(tok.sot_sequence_including_notimestamps) + tok.encode(' ' + text) + [tok.eot]
            t = torch.tensor([ids]); lp = torch.log_softmax(m.decoder(t[:, :-1], enc), -1)[0]
            n0 = len(tok.sot_sequence_including_notimestamps)
            sc[c] = sum(lp[i - 1, ids[i]].item() for i in range(n0, len(ids)))
    v = np.array(list(sc.values())); p = np.exp(v - v.max()); p /= p.sum(); pr = dict(zip(sc, p))
    bm = max(misses, key=lambda k: sc[k])
    return round(float(sum(pr[h] for h in hits)), 3), f'{bm.strip()} ({pr[bm]:.2f})'

def slot_words(ws, slot):
    a, b = SLOTS[slot]
    return ''.join(w for w, s0, s1 in ws if s1 > a + .02 and s0 < b - .02).strip()

def bright_stats(x, a, b):
    """Spectral centroid (Hz) and % of energy above 3 kHz over [a, b] s of a 48 kHz signal (mono sum)."""
    y = x.mean(1) if x.ndim > 1 else x; y = y[int(a * OUT_SR):int(b * OUT_SR)]
    S = np.abs(np.fft.rfft(y * np.hanning(len(y)))) ** 2; f = np.fft.rfftfreq(len(y), 1 / OUT_SR)
    return round(float((f * S).sum() / S.sum())), round(float(100 * S[f > 3000].sum() / S.sum()), 1)

def f0_med(x, a, b):
    from hf0 import hf0
    y = librosa.resample(x.mean(1)[int(a * OUT_SR):int(b * OUT_SR)], orig_sr=OUT_SR, target_sr=SR)
    t, f, sc, v = hf0(y, SR, hop=.005, fmin=75, fmax=700)
    return round(float(np.median(f[v]))) if v.any() else None

# the in-song forced choice uses the confusions that actually occur (the full sets cost ~4x the decoder time)
HOOK_SPEC = dict(hits=[" We're so back!", " We're so back.", " WE'RE SO BACK!", " We are so back!"],
                 misses=[f' {m}!' for m in ["We're so bad", "We're so black", "Wear so back", "We're so big", "We're so bag",
                         "Winner so back", "Winner so bad", "Where's the back", "We're sold back", "We're so pack",
                         "We're so bat", "We're so duck", "We're so beck", "Where so back"]])
SO_SPEC = dict(hits=specs.ITS_SO_OVER['hits'], misses=specs.ITS_SO_OVER['misses'])

def evaluate(kind, name):
    hook, so = (name, 'S0_current') if kind == 'hook' else ('H0_current', name)
    stem = build_stem(hook, so); mix = full_mix(stem)
    sf.write(os.path.join(R2, f'mix_{name}.wav'), mix.astype(np.float32), OUT_SR, subtype='FLOAT')
    solo = build_stem(hook, so, only=kind)
    r = dict(name=name, desc=(HOOKS if kind == 'hook' else SOS)[name]['desc'])
    slots = ('hook33', 'hook40', 'hook0', 'hook52') if kind == 'hook' else ('over8',)
    spec = HOOK_SPEC if kind == 'hook' else SO_SPEC
    for mname in ('small.en', 'medium.en'):
        text, ws = words_ts(mix, mname); r[f'text_{mname}'] = text
        for sl in slots:
            r[f'{sl}_{mname}'] = slot_words(ws, sl)
            r[f'{sl}_p_{mname}'], r[f'{sl}_miss_{mname}'] = full_forced(mix, ws, sl, spec['hits'], spec['misses'], mname)
    for sl in slots:
        a, b = PROXY[sl]
        r[f'{sl}_vox_centroid'], r[f'{sl}_vox_hf'] = bright_stats(solo, a, b)
        r[f'{sl}_mix_centroid'], r[f'{sl}_mix_hf'] = bright_stats(mix, a, b)
        r[f'{sl}_vox_f0'] = f0_med(solo, a, b)
    print(json.dumps(r), flush=True)
    return r

def check():
    """W/stem.wav can't be reproduced bit for bit: it was built before vox seeded Praat's PSOLA, whose unvoiced stretches are
    random. So: (1) two seeded rebuilds are identical; (2) against W/stem.wav, the only differences are where a sung word
    with unvoiced stretches sounds (the hook statements and its reverb tails); the rest of the stem matches."""
    x, sr = sf.read(os.path.join(W, 'stem.wav'), always_2d=True)
    y1 = build_stem(); y2 = build_stem()
    print(f'seeded rebuilds identical: {np.abs(y1 - y2).max() == 0}')
    d = np.abs(x - y1).max(1)
    bad = [round(a, 1) for a in np.arange(0, 28.9, .5) if d[int(a * OUT_SR):int((a + .5) * OUT_SR)].max() > 1e-3]
    print(f'vs W/stem.wav: half-seconds differing by > -60 dBFS: {bad}')

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'check'
    if cmd == 'check': check()
    elif cmd in ('hooks', 'sos'):
        names = sys.argv[2:] or list(HOOKS if cmd == 'hooks' else SOS)
        out = os.path.join(HERE, f'round2_{cmd}.json'); res = json.load(open(out)) if os.path.exists(out) else {}
        for n in names:
            res = json.load(open(out)) if os.path.exists(out) else {}
            res[n] = evaluate('hook' if cmd == 'hooks' else 'so', n); json.dump(res, open(out, 'w'), indent=1)
    elif cmd == 'proxy':      # recompute the shrillness proxy for finished candidates (no Whisper)
        kind = sys.argv[2]; out = os.path.join(HERE, f'round2_{kind}s.json'); res = json.load(open(out))
        for n, r in res.items():
            hook, so = (n, 'S0_current') if kind == 'hook' else ('H0_current', n)
            solo = build_stem(hook, so, only=kind); mix, _ = sf.read(os.path.join(R2, f'mix_{n}.wav'), always_2d=True)
            for sl in [k[:-len('_p_small.en')] for k in r if k.endswith('_p_small.en')]:
                a, b = PROXY[sl]
                r[f'{sl}_vox_centroid'], r[f'{sl}_vox_hf'] = bright_stats(solo, a, b)
                r[f'{sl}_mix_centroid'], r[f'{sl}_mix_hf'] = bright_stats(mix, a, b)
                r[f'{sl}_vox_f0'] = f0_med(solo, a, b)
            print(n, {k: v for k, v in r.items() if 'centroid' in k or '_hf' in k or 'f0' in k}, flush=True)
            cur = json.load(open(out)); cur[n].update(r); json.dump(cur, open(out, 'w'), indent=1)

def audition(kind, order):
    """Song excerpts from each candidate's full mix, the current version first: kind 'hook' = the drop's hook (b32-b42,
    12.65-16.65 s), 'so' = the sad line (3.10-7.30 s). 0.8 s of silence between excerpts. -> W/round2/audition_<kind>.wav"""
    a, b = (bt(32) - .2, bt(32) + 3.8) if kind == 'hook' else (3.10, 7.30)
    out, labels, t = [], [], 0.0
    gap = np.zeros((int(.8 * OUT_SR), 2)); f = int(.02 * OUT_SR); ramp = np.linspace(0, 1, f)[:, None]
    for n in order:
        x, sr = sf.read(os.path.join(R2, f'mix_{n}.wav'), always_2d=True)
        seg = x[int(a * sr):int(b * sr)].copy(); seg[:f] *= ramp; seg[-f:] *= ramp[::-1]
        labels.append(dict(name=n, t=round(t, 2))); out += [seg, gap]; t += (len(seg) + len(gap)) / sr
    y = np.concatenate(out)
    sf.write(os.path.join(R2, f'audition_{kind}.wav'), y.astype(np.float32), OUT_SR, subtype='FLOAT')
    return labels
