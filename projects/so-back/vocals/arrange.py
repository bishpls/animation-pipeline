"""SO BACK's vocal stem: the arrangement (STORYBOARD.md) built from the announcer's own recordings with vox.py.
    .venv/bin/python projects/so-back/vocals/arrange.py
-> W/stem.wav (48 kHz stereo; sample 0 = film time 0; game-derived, outside the repo) and projects/so-back/assets/vox.js
   (the caption timings: text and times only, for the picture; one clock).

The song: take c4, 150 BPM, beat b at 0.05 + 0.4 b s, C minor throughout (the drop alternates Cm and Gm7 every two bars).
Sung lines are hard-tuned onto notes (vox.sing); chops are whole clips, hard-tuned to the C minor scale per syllable
(`tune`), or left as recorded. Keep syllables within about +-5-7 semitones of their recorded pitch (NOTES.md).
"""
import os, sys, json
import numpy as np
from scipy.signal import fftconvolve, butter, sosfiltfilt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import W, SR, write
import words, vox, you
from vox import shelf

HERE = os.path.dirname(os.path.abspath(__file__)); PROJ = os.path.dirname(HERE)
BEAT, OFF, OUT_SR = 0.4, 0.05, 48000
bt = lambda b: OFF + b * BEAT
CMIN = [0, 2, 3, 5, 7, 8, 10]                     # C minor pitch classes
G4, Ab4, Bb4, C5, D5, Eb5 = 67, 68, 70, 72, 74, 75
Eb4, F4, C4, G3, D4 = 63, 65, 60, 55, 62

# the sung recipes (NOTES.md: sung, the Smash /ae/ "back" with its /k/ at full level survives retuning best)
SUNG = {'its': 'is+t', 'so_over': 'sudden+no', 'over': 'gameover',
        'were': 'winner-n', 'so_back': 'single+no', 'back': 'button+smash+continue.k0'}
_WORD = {}
def word(kind, rec):
    if (kind, rec) not in _WORD: _WORD[(kind, rec)] = words.word(kind, rec)[0]
    return _WORD[(kind, rec)]

def word_syl(kind, y):
    vs = vox.voiced_spans(y); a, b = vs[0][0], vs[-1][1]
    return [(a, 0.22), (0.30, b)] if kind == 'over' else [(a, b)]

def sung(items, bright=.3):
    """items: [(kind, recipe, notes, beats, lens)] per word; each syllable's vowel onset lands on its beat, stretched to
    len beats (x .85). Returns [(y48, t)] for vox.line."""
    parts = []
    for kind, rec, notes, beats, lens in items:
        y = word(kind, rec); syl = word_syl(kind, y)
        z = vox.sing(y, notes, syl=syl, durs=[l * BEAT * .85 for l in lens])
        parts.append((vox.to48k(z, bright=bright), bt(beats[0]) - syl[0][0]))
    return parts

def phrase(name, trim=None):
    import soundfile as sf
    x, sr = sf.read(os.path.join(W, 'phrases', name + '.wav')); assert sr == SR
    x = x.astype(float)
    if trim: n = int(trim * SR); f = int(.06 * SR); x = x[:n].copy(); x[-f:] *= np.cos(np.linspace(0, np.pi / 2, f)) ** 2
    return x

PH = json.load(open(os.path.join(HERE, 'phrases.json')))
def tune(name, y, scale=CMIN, shift=0, prefer_low=True):
    """Hard autotune: every syllable (the voiced spans) held flat on the scale tone nearest its recorded pitch (+shift)."""
    spans = vox.voiced_spans(y)
    from hf0 import hf0
    t, f, sc, v = hf0(y, SR, hop=0.005, fmin=75, fmax=600)
    notes, keep = [], []
    for a, b in spans:
        m = (t >= a) & (t <= b) & v
        if m.sum() < 3 or b - a < .04: continue
        mid = vox.hz2midi(np.median(f[m])) + shift
        cands = [o * 12 + p for o in range(2, 8) for p in scale]
        best = min(cands, key=lambda c: (abs(c - mid), c if prefer_low else -c))
        notes.append(best); keep.append((a, b))
    return vox.sing(y, notes, syl=keep, glide=.02) if keep else y

def reverb(x, rt60=2.0, sr=OUT_SR, lp=6000, seed=1):
    rng = np.random.default_rng(seed); n = int(rt60 * sr)
    tt = np.arange(n) / sr; env = np.exp(-6.9 * tt / rt60)
    irs = []
    for k in range(2):
        ir = rng.standard_normal(n) * env
        ir = sosfiltfilt(butter(2, lp, 'low', fs=sr, output='sos'), ir); ir[:int(.012 * sr)] *= np.linspace(0, 1, int(.012 * sr))
        irs.append(ir / np.sqrt((ir ** 2).sum()))
    return np.stack([fftconvolve(x, ir)[:len(x) + n] for ir in irs], 1)

def lowpass(x, f, sr=OUT_SR): return sosfiltfilt(butter(4, f, 'low', fs=sr, output='sos'), x)
def up(y, bright=.3): return vox.to48k(y, bright=bright)
def vline(parts):
    """vox.line on parts [(y, t)] with absolute times (any sign): returns (y, t0), the line relative to its first start."""
    t0 = min(t for _, t in parts)
    return vox.line([(y, t - t0) for y, t in parts]), t0

# vocal level by section, measured against the music (active vocal RMS vs the section's music RMS; the drop is a dense,
# heavily compressed -6 dB wall, the "over" music box sits at -24): cold ~0 dB, over/turn ~+6, drop ~0 with the mix's ducking
SEC = [(0.0, 6.5), (bt(8) - .3, 0.0), (bt(32) - .3, 7.0), (bt(48) - .3, 7.5), (bt(60) - .3, 3.0), (bt(64) - .3, 0.0)]   # (re-balanced for take f3)
def sec_gain(t): return [g for a, g in SEC if t >= a][-1]

class Bus:
    """A stereo stem built from (y48 mono, t, gain_db, pan, send, rt60) placements; sends go to one reverb per rt60."""
    def __init__(self, dur): self.dry = np.zeros((int(dur * OUT_SR), 2)); self.sends = {}
    def add(self, y, t, gain_db=0.0, pan=0.0, send=0.0, rt60=2.0):
        y = np.asarray(y, float) * 10 ** ((gain_db + sec_gain(t)) / 20); i = int(round(t * OUT_SR))
        f = min(len(y), int(.003 * OUT_SR)); y = y.copy(); y[:f] *= np.linspace(0, 1, f)
        if i < 0: y = y[-i:]; i = 0
        n = min(len(y), len(self.dry) - i)
        if n <= 0: return
        g = np.array([np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)]) * np.sqrt(2)
        self.dry[i:i + n] += y[:n, None] * g
        if send > 0:
            s = self.sends.setdefault(rt60, np.zeros(len(self.dry)))
            s[i:i + n] += y[:n] * send
    def mix(self):
        out = self.dry.copy()
        for rt, s in self.sends.items():
            r = reverb(s, rt60=rt); n = min(len(out), len(r)); out[:n] += r[:n] * .9
        return out

# round 2 (Michael: the sung hook was "very shrill"): the hook is the announcer's own SPOKEN words ("WE'RE SO BACK", recipe #2),
# each hard-tuned only to the nearest C minor tone (we're Eb3, so F4, back C3: his chest register, ending on the tonic), a gentle
# high shelf, no doubles. Sung low, "back" fails every way (glad, bad, blood); spoken at its own length it reads (NOTES.md 7).
HOOK = ('wins+master', 'surv+no', 'break+hand+complete.k0')   # (.k0: the /k/ at its source level; at -4 dB take f3's drop masked it: 'we're so bad')
def hook_line(beats):
    out = []
    for kind, rec, b in zip(('were', 'so', 'back'), HOOK, beats):
        y = word(kind, rec); syl = word_syl(kind, y)
        out.append((shelf(up(tune(kind, y), bright=.1), -3, 3500), bt(b) - syl[0][0]))
    return out

def main():
    bus, CAP = Bus(28.9), []
    cap = lambda t, text, kind, dur=None, **k: CAP.append(dict(t=round(t, 3), text=text, kind=kind, dur=dur, **k))

    # ---- cold open (b0-7): the hook as a flash-forward, the knee on b0; "FALCON..." (game audio) is dragged by the tape stop
    hook = hook_line((0, 1, 2))
    hook[0] = (hook[0][0], max(0.0, hook[0][1]))        # the film's first sample: "we're" can't start before 0
    y, t0 = vline(hook)
    bus.add(y, t0, 0, send=.25, rt60=1.2)
    for w, b in (("WE'RE", 0), ('SO', 1), ('BACK', 2)): cap(bt(b), w, 'hook')
    # b4: the hook's echo, darker, quieter, panned
    bus.add(lowpass(y, 2500), t0 + 4 * BEAT, -8, pan=-.35, send=.3, rt60=1.2)

    # ---- over (b8-23): half-time, underwater, big reverb
    over = sung([('its', SUNG['its'], [Eb4], [8], [.6]), ('so', 'sudden+overo', [G3], [9.25], [1.0])])   # the soft o of "Game Over" (round 2)
    over[1] = (shelf(over[1][0], -3, 3500), over[1][1])
    ov = word('over', SUNG['over']); osyl = word_syl('over', ov)
    over.append((up(vox.pitch_shift(ov, 3)), bt(11) - osyl[0][0]))
    y, t1 = vline(over)
    bus.add(lowpass(y, 6000), t1, -1, send=.5, rt60=2.8)
    for w, b in (("it's", 8), ('so', 9.25), ('over', 11)): cap(bt(b), w, 'over')
    g = up(phrase('game_over'), bright=0)
    bus.add(lowpass(g, 3000), bt(16) - PH['game_over']['syllables'][0]['t0'], -2, send=.6, rt60=2.8)
    cap(bt(16), 'GAME', 'chop'); cap(bt(16) + 1.14, 'OVER.', 'chop')
    import soundfile as sf
    e, _, _ = words.phrase([(words.word(k, r)[0], []) for k, r in zip(('its', 'so', 'over'), ('is+t', 'sudden+overo', 'gameover'))], [.05, .05])
    e = up(vox.pitch_shift(np.asarray(e, float), -2), bright=0)
    bus.add(lowpass(e[:int(2.2 * OUT_SR)], 5000), bt(21), -6, pan=-.2, send=.6, rt60=3.2)
    cap(bt(21), "it's so over", 'echo')

    # ---- the turn (b24-31): dry and close
    c = phrase('continue'); bus.add(up(c), bt(24) - .01, -1, send=.12, rt60=1.0); cap(bt(24), 'CONTINUE?', 'chop')
    f5 = phrase('five'); five = up(f5)
    cut = int((bt(27) - bt(26)) * OUT_SR); a = five[:cut].copy(); a[-480:] *= np.linspace(1, 0, 480)
    bus.add(a, bt(26) - .09, 0, send=.1, rt60=1.0); bus.add(five, bt(27) - .09, 0, send=.2, rt60=1.0)
    cap(bt(26), '5', 'num'); cap(bt(27), '5.5', 'num')
    bus.add(up(phrase('ready')), bt(30) - .23, 0, send=.2, rt60=1.4); cap(bt(30), 'READY?', 'chop')
    # b32: no announcer. Falcon's own "PUNCH!" (game audio, the SFX stem) is the drop's word.

    # ---- the drop (b32-47)
    y, t2 = vline(hook_line((33, 34, 35))); bus.add(y, t2, 0, send=.2, rt60=1.2)
    for w, b in (("WE'RE", 33), ('SO', 34), ('BACK', 35)): cap(bt(b), w, 'hook')
    s = tune('success', phrase('success')); bus.add(up(s), bt(36) - .07, 1, send=.15, rt60=1.0); cap(bt(36), 'SUCCESS!', 'stamp')
    s = tune('complete', phrase('complete', trim=.66)); bus.add(up(s), bt(38) - .01, 1, send=.15, rt60=1.0); cap(bt(38), 'COMPLETE!', 'stamp')
    y, t3 = vline(hook_line((40, 41, 42))); bus.add(y, t3, 0, send=.2, rt60=1.2)
    for w, b in (("WE'RE", 40), ('SO', 41), ('BACK', 42)): cap(bt(b), w, 'hook')
    s = phrase('a_new_record', trim=1.38); bus.add(up(s), bt(44) - .01, 1, send=.15, rt60=1.0)
    cap(bt(44), 'A NEW RECORD!', 'stamp')

    # ---- drop 2 (b48-63)
    s = tune('choose', phrase('choose_your_character')); bus.add(up(s), bt(48) - .1, 0, send=.15, rt60=1.0)
    for w, dt in (('CHOOSE', 0), ('YOUR', .2), ('CHARACTER!', .35)): cap(bt(48) + dt, w, 'thesis')
    # b52: the stutter hook: we're-we're so-so BACK on eighths
    p = hook_line((52, 53, 54))
    st = [p[0], (p[0][0], p[0][1] + BEAT / 2), p[1], (p[1][0], p[1][1] + BEAT / 2), p[2]]
    y, t4 = vline(st); bus.add(y, t4, 0, send=.2, rt60=1.2)
    for w, b in (("WE'RE", 52), ("WE'RE", 52.5), ('SO', 53), ('SO', 53.5), ('BACK', 54)): cap(bt(b), w, 'hook')
    s = tune('wow', phrase('wow_incredible', trim=1.66)); bus.add(up(s), bt(56) - .04, 1, send=.15, rt60=1.0)
    cap(bt(56), 'WOW,', 'stamp'); cap(bt(56) + .75, 'INCREDIBLE!', 'stamp')
    # b60 (the 16th fill, then the breakdown): the results line, answered on the final stab by "YOU!" (Michael), spliced in his
    # name-call cadence: the /ju:/ inside his own "Mewtwo!" call (the m cut) into that call's falling reverberant tail
    s = phrase('this_games_winner_is'); bus.add(up(s), bt(60) - .03, 0, send=.3, rt60=1.8)
    cap(bt(60), "THIS GAME'S", 'winner'); cap(bt(60) + .8, 'WINNER IS...', 'winner')
    yy, _ = you.build('mew+tail')
    bus.add(shelf(up(yy, bright=.1), -2, 3500), bt(64) - you.LEAD, -1.5, send=.35, rt60=2.2); cap(bt(64), 'YOU!', 'finale')
    # Falcon's own taunt voice answers (game audio, placed by src/shots/end.js: clip time 0 = film 25.85); caption words only,
    # on the clip's measured onset (.433) and Whisper's word spacing: "Show me your moves!", spelt as Michael writes it
    for w, ct in (('SHOW', .433), ('ME', .58), ('YA', .76), ('MOVES!', .88)): cap(25.85 + ct, w, 'taunt')

    out = bus.mix()
    import soundfile as sf
    sf.write(os.path.join(W, 'stem.wav'), out.astype(np.float32), OUT_SR, subtype='FLOAT')   # float: absolute levels kept
    open(os.path.join(PROJ, 'assets', 'vox.js'), 'w').write('window.VOX = ' + json.dumps(CAP) + ';\n')
    print(f'stem {len(out) / OUT_SR:.2f}s -> {W}/stem.wav; {len(CAP)} captions -> assets/vox.js')

if __name__ == '__main__':
    main()
