"""つづく: assemble the duet from per-world generations on the shared bar grid (1 bar = 1.4118 s = 4/4@170 = 6/8@85).

    ../../.venv/bin/python assemble.py [lily]    -> assets/song.wav|mp3 + assets/timeline.json (every event, for the picture)

The duet is section-level (draft 5, song/LYRICS.md): each section is generated with its own singer, and the singers switch on
section boundaries; nothing is grafted inside a phrase. Sources:
  fA    = assets/world2/fA3_1   Fable's world: intro 4 | verse 12 (sung) | interlude bed 4 | build 8
  fB    = assets/world2/fB3_1   Fable's world: silent bed 8 | the held note 7 | outro tail
  clC_2 = assets/world4         Clawd's world: build | chorus 1 | hook | verse 2 | chorus 2 | breakdown (song/build_sections.py)
  clI_2                         the ending, one generation: build | final chorus (Clawd's alone) | the final hit
  hw    = ../hello-world/assets/song.mp3 (the Op. 1 quote)
Spoken lines are raw TTS (Fable: voice/fable_<cast>/, Clawd: voice/clone/); crowd calls are 5 layered voices.
"""
import json, math, os, subprocess, sys
import numpy as np, soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
A = lambda *p: os.path.join(HERE, *p)
SR = 48000; BAR = 60 / 170 * 4
sys.path.insert(0, os.path.join(ROOT, 'tools'))


def load(path, mono=False):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', '1' if mono else '2', '-ar', str(SR), '-'], capture_output=True, check=True).stdout
    y = np.frombuffer(raw, np.float32).copy()
    return y if mono else y.reshape(-1, 2)


def bars(y, b0, b1, phase=0.0):              # slice bars [b0, b1) of a source whose bar grid starts at `phase` seconds
    return y[int((phase + b0 * BAR) * SR):int((phase + b1 * BAR) * SR)]


def lufs_ish(y):                               # crude loudness: RMS in dB of the active part
    a = np.abs(y).mean(1) if y.ndim == 2 else np.abs(y)
    act = y[a > np.percentile(a, 60)] if len(y) > 100 else y
    return 20 * np.log10(np.sqrt(np.mean(act ** 2)) + 1e-9)


def norm(y, target_db):                       # integrated loudness (LUFS) via pyloudnorm; falls back to RMS for very short clips
    import pyloudnorm as pyln
    try:
        L = pyln.Meter(SR, block_size=.4).integrated_loudness(y if y.ndim == 2 else np.stack([y, y], 1))
        if not np.isfinite(L): raise ValueError
    except Exception:
        L = lufs_ish(y)
    return y * 10 ** ((target_db - L) / 20)


def room(y, amt=.18, t60=.9):                  # a small synthetic room (exponentially decaying noise IR)
    n = int(t60 * SR); rng = np.random.default_rng(4); ir = rng.standard_normal(n) * np.exp(-6.9 * np.arange(n) / n)
    ir /= np.sqrt((ir ** 2).sum()); mono = y.mean(1) if y.ndim == 2 else y
    wet = np.convolve(mono, ir)[:len(mono)] * amt
    dry = y if y.ndim == 2 else np.stack([y, y], 1)
    return dry + wet[:, None]


def filt_tinny(y):                             # far-away PA: band-limit + mono + a little crush
    from scipy.signal import butter, sosfilt
    m = y.mean(1); m = sosfilt(butter(4, [450, 3200], 'band', fs=SR, output='sos'), m)
    return np.stack([m, m], 1) * .5


def loud(y):                                   # the loudness norm() measures (LUFS; RMS fallback for very short clips)
    import pyloudnorm as pyln
    try:
        L = pyln.Meter(SR, block_size=.4).integrated_loudness(y if y.ndim == 2 else np.stack([y, y], 1))
        return L if np.isfinite(L) else lufs_ish(y)
    except Exception:
        return lufs_ish(y)


def fade(y, a=.02, b=.02):
    y = y.copy(); na, nb = int(a * SR), int(b * SR)
    if na: y[:na] *= np.linspace(0, 1, na)[:, None]
    if nb: y[-nb:] *= np.linspace(1, 0, nb)[:, None]
    return y


class Track:
    def __init__(self, n_bars):
        self.y = np.zeros((int((n_bars + 2) * BAR * SR), 2), np.float32); self.events = []
        self.duck = np.ones(len(self.y), np.float32); self.voice = np.zeros_like(self.y)
    def say(self, clip, at_s, label, who, duck_db=-7):    # a voice over music: goes on the voice bus and ducks the music bus
        i = int(at_s * SR); n = min(len(clip), len(self.y) - i)
        self.voice[i:i + n] += clip[:n]
        if duck_db:
            a, r = int(.12 * SR), int(.35 * SR); g = 10 ** (duck_db / 20)
            env = np.ones(len(self.y), np.float32); lo, hi = max(0, i - a), min(len(self.y), i + n + r)
            env[lo:hi] = g; ramp = np.linspace(1, g, a); env[lo:lo + a] = ramp[:len(env[lo:lo + a])]
            if hi - r > lo: env[hi - r:hi] = np.linspace(g, 1, r)[:hi - (hi - r)]
            self.duck = np.minimum(self.duck, env)
        self.events.append({'t0': round(at_s, 3), 't1': round(at_s + len(clip) / SR, 3), 'kind': who, 'label': label})
    def mix(self): return self.y * self.duck[:, None] + self.voice
    def put(self, clip, at_s, gain=1.0, label=None, kind='music'):
        i = int(at_s * SR); n = min(len(clip), len(self.y) - i)
        if n > 0: self.y[i:i + n] += clip[:n] * gain
        if label: self.events.append({'t0': round(at_s, 3), 't1': round(at_s + len(clip) / SR, 3), 'kind': kind, 'label': label})


CAST = sys.argv[1] if len(sys.argv) > 1 else 'lily'    # Fable's speaking voice: voice/fable_<cast>/ (voice/record.py)
def main():
    W = A('assets', 'world2'); SP = A('voice', 'clone'); SPF = A('voice', 'fable_' + CAST); CR = A('voice', 'crowd')
    fA, fB = load(os.path.join(W, 'fA3_1.mp3')), load(os.path.join(W, 'fB3_1.mp3'))
    ofs = 4 * BAR                                   # both inpainted Clawd pieces start with a 4-bar generated lead-in
    W4 = A('assets', 'world4'); M = json.load(open(A('song', 'sections.json')))['margin']
    # Draft 5: the duet is section-level. Clawd world A (build 4 | chorus 1 16 | hook 4 | verse 2 16 | chorus 2 8 | breakdown 4) is
    # regenerated without Fable's counter-lines (song/build_sections.py, take clC_2): crowd calls fill the gaps, and her lines are
    # margin notes in the picture. A visitor annotates; she doesn't sing.
    clA = norm(load(os.path.join(W4, 'clC_2.mp3')), -15.5)
    # The ending is ONE generation (song/build_sections.py, plan_clI, take 2), so the model writes the transitions: build 4 |
    # final chorus, Clawd's alone (draft 6: Fable's singer crossing over sounded like another song; her half is margin notes) |
    # the band's final hit. All in C: the model ignores "key change" (measured).
    END = load(os.path.join(W4, 'clI_2.mp3'))
    # The hit lands on the dash: cut the take's 2.75-bar band tag after "and then—" (bar 17 downbeat -> the hit on bar 20; same
    # generation, same level, 40 ms crossfade on the bar line).
    i17, i20, x = int(17 * BAR * SR), int(20 * BAR * SR), int(.04 * SR)
    END = np.concatenate([END[:i17], END[i17:i17 + x] * np.linspace(1, 0, x)[:, None] + END[i20:i20 + x] * np.linspace(0, 1, x)[:, None], END[i20 + x:]])
    END = END * 10 ** ((-14.8 - loud(bars(END, 4, 17))) / 20)
    # The build came out flat (a build rises only sometimes, and only as a generation's first chunk): a filter build across its
    # 4 bars, a low-pass opening from 500 Hz and a 10 dB gain ramp, climbing into the drop.
    from scipy.signal import butter, sosfiltfilt
    n4 = int(4 * BAR * SR); a = (np.arange(n4) / n4) ** 1.6
    lp = sosfiltfilt(butter(2, 500, 'low', fs=SR, output='sos'), END[:n4], axis=0)
    END[:n4] = (lp * (1 - a[:, None]) + END[:n4] * a[:, None]) * (10 ** (-10 * (1 - a) / 20))[:, None]
    hw = load(os.path.join(ROOT, 'projects', 'hello-world', 'assets', 'song.mp3'))
    spoken = lambda n, db=None: room(norm(load(os.path.join(SPF if n.startswith('f_') else SP, n + '.wav')), db or (-23 if n.startswith('c_') else -20)), .26 if n.startswith('c_') else .14)
    sfx = lambda n, db: norm(load(os.path.join(A('assets', 'sfx'), n + '.mp3')), db)
    def crowd(k):
        n = int(2.6 * SR); mix = np.zeros((n, 2), np.float32)
        for i in range(1, 6):
            c = load(os.path.join(CR, f'{k}_{i}.mp3')); off = int(i * .012 * SR); m = min(len(c), n - off)
            if m > 0: mix[off:off + m] += c[:m]
        return room(norm(mix, -22), .35, 1.4)

    T = Track(165); b = lambda n: n * BAR
    # ---- prologue (Op. 1, far away) and Fable's world
    T.put(fade(filt_tinny(bars(hw, 0, 6, 129.88)), 1.5, 1.2), 0, 1.0, 'prologue: HELLO, WORLD! (distant)', 'music')
    T.put(sfx('hyoshigi', -18), b(6) - .05, 1.0, 'hyoshigi: the story begins', 'sfx')
    # Verse 1 is sung straight through, and Clawd answers "...and said—" on the next downbeat. The narrator's aside is a margin
    # note on the page (picture only, LYRICS.md draft 3); in sound it is five soft type thuds, one per beat across the verse's
    # last two bars, the fifth ("Nobody ever can.") on the beat of Clawd's "Show me how!".
    T.put(fade(norm(bars(fA, 0, 16), -19), .02, .03), b(6), 1.0, 'fable: intro + verse 1', 'music')
    T.put(spoken('f_mukashi'), b(6.35), 1.0, 'Mukashi, mukashi...', 'fable')
    T.put(crowd('aru'), b(8.1), .9, 'ARU TOKORO NI!', 'crowd')
    for bb, lab in zip([20, 20.5, 21, 21.5, 22], ['I know this part.', "I've read it in forty tongues.", 'Every telling ends on the same page.',
                                                  'Nobody ever shows.', 'Nobody ever can.  「誰にも、できない。」']):
        T.put(sfx('press', -31), b(bb) - .01, 1.0, 'margin: ' + lab, 'margin')
    bed = norm(bars(fA, 16, 20), -21)
    for k, (s0, n0, n1) in enumerate([(22, 20, 24), (26, 20, 24), (30, 20, 24), (34, 20, 28)]):
        T.put(fade(norm(bars(fA, n0, n1), -19.5), .02, .02), b(s0), 1.0, 'fable: build' if k == 0 else None, 'music')
    # the rakugo exchange, over the lute build: opens on the downbeat after "said—", ends before "Says who?" starts Clawd's machine
    lines = [('c_showme', 'clawd', 'Show me how! Walk it first...'), (None, 'crowd', 'showme'), ('f_tried', 'fable', '...and the mother went sideways.'),
             ('c_sorekara', 'clawd', 'So? Sorekara?! And then?!'), ('f_noandthen', 'fable', 'There is no "and then."')]
    clips = [(crowd('showme') * .9 if n is None else spoken(n), who, lab) for n, who, lab in lines]
    t = b(22) + .02
    for c, who, lab in clips:
        T.put(c, t, 1.0, lab if who != 'crowd' else 'SHOW ME HOW!', who); t += len(c) / SR + .3
    print(f'exchange ends at bar {(t - .3) / BAR:.2f} (Says who? at bar 42.25)')
    # ---- into Clawd's world: a generated 4-bar build in her own key and timbre
    T.put(fade(clA, .02, .6), b(42), 1.0, "clawd: build + chorus 1 + hook + verse 2 + chorus 2 + breakdown", 'music')
    T.say(spoken('c_sayswho', -20), b(42) + .35, 'Says who?', 'clawd', 0)
    cA = b(42) + ofs                                  # clA chorus time 0 in song time
    # Fable's margin notes in Clawd's choruses (picture), each on the crowd call that fills the gap it annotates; soft type thuds.
    for bb, k in [(46 + 2.12, 'chorus1_gap1'), (46 + 6.24, 'chorus1_gap2'), (46 + 10.25, 'chorus1_gap3'), (82 + 2.24, 'chorus2_gap')]:
        T.put(sfx('press', -31), b(bb) - .01, 1.0, 'margin: ' + M[k], 'margin')
    # ---- breath, clack, the bridge (chorus 2 winds down through its generated breakdown, bars 90-94)
    T.put(sfx('hyoshigi', -17), b(93), 1.0, 'hyoshigi: the story stops', 'sfx')
    # The bridge is laid out from the clip lengths (a slower read must never run into the next line): the monologue, a breath,
    # the confession, the held note, "this is now"; then Clawd's build starts on the first bar line after "Sorekara?".
    import math
    br1, br2, now = spoken('f_bridge1'), spoken('f_bridge2'), spoken('f_nowthis', -22)
    D = max(0, math.ceil((b(93.6) + len(br1) / SR + 1.4) / BAR - 106.4))         # extra bars of bed the monologue needs
    Bb = max(119 + D, math.ceil((b(114.3 + D) + len(now) / SR) / BAR - .05))       # the bar Clawd's build starts
    # ONE continuous lute bed from the end of chorus 2 to the final riser: under the monologue, the confession, the held note
    # (quieter there: the note is a cappella) and "this is now". No cuts inside the bridge.
    n_bed = int((Bb + 3 - 93.2) * BAR * SR); bedL = np.concatenate([bed] * 12)[:n_bed].copy()
    lvl = np.ones(n_bed, np.float32); tb = lambda bb: int((bb - 93.2) * BAR * SR)
    lvl[tb(107.6 + D):tb(114.2 + D)] = .45                           # under the sung note
    lvl = np.convolve(lvl, np.ones(int(.6 * SR)) / int(.6 * SR), mode='same')
    lvl[-int(2.6 * BAR * SR):] *= np.linspace(1, 0, int(2.6 * BAR * SR)) ** .8   # hands over to Clawd's build across its first 2 bars
    T.put(fade(bedL * lvl[:, None], 1.2, .02), b(93.2), 1.0, 'fable: bridge bed (continuous)', 'music')
    T.put(br1, b(93.6), 1.0, 'I know how every story ends...', 'fable')
    T.put(br2, b(106.4 + D), 1.0, "...I didn't know this one.", 'fable')
    T.put(fade(norm(bars(fB, 8, 14), -18.5), .05, .8), b(108 + D), 1.0, "fable: the held note (So I'm putting down the book)", 'music')
    T.put(now, b(114.3 + D), 1.0, 'Mukashi mukashi was a long time ago. This is now. Sorekara?', 'fable')
    print(f'bridge: +{D} bars for the monologue; build at bar {Bb}; "Sorekara?" ends at bar {(b(114.3 + D) + len(now) / SR) / BAR:.2f}')
    # ---- "Sorekara?" triggers the build (mirrors "Says who?" at the first world switch); the whole ending runs from there.
    T.put(fade(END, .05, .3), b(Bb), 1.0, 'clawd: build -> final chorus (hers alone) -> the band hits on the dash, rings out', 'music')
    T.events.append({'t0': round(b(Bb + 4), 3), 't1': round(b(Bb + 17), 3), 'kind': 'cue', 'label': 'clawd: final chorus'})
    # Fable's final-chorus margin notes, in the lyric's own ink now (after the bridge she's writing, not quoting); the margin is
    # left empty on the dash.
    for bb, k in [(8.95, 'final_1'), (11.99, 'final_2')]:
        T.put(sfx('press', -31), b(Bb + bb) - .01, 1.0, 'margin: ' + M[k], 'margin')
    T.events.append({'t0': round(b(Bb + 16.01), 3), 't1': round(b(Bb + 19), 3), 'kind': 'margin', 'label': 'margin: (empty)'})
    T.put(sfx('hyoshigi', -19), b(Bb + 18.5), 1.0, 'hyoshigi: the book closes', 'sfx')
    # ---- outro
    T.put(norm(bars(fB, 15, 19), -26), b(Bb + 19), 1.0, 'outro: music box, open fifth', 'music')
    T.put(spoken('f_tsuzuku'), b(Bb + 19.45), 1.0, '...tsuzuku.', 'fable')
    T.put(spoken('c_nextprompt'), b(Bb + 20.9), 1.0, 'See you next prompt!', 'clawd')

    y = T.mix()[:int(b(Bb + 23.5) * SR)]
    pk = np.abs(y).max(); y = y * (.97 / pk)
    sf.write(A('assets', 'song.wav'), y, SR, subtype='PCM_24')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', A('assets', 'song.wav'), '-b:a', '256k', A('assets', 'song.mp3')], check=True)
    json.dump({'bar': BAR, 'events': sorted(T.events, key=lambda e: e['t0'])}, open(A('assets', 'timeline.json'), 'w'), indent=1)
    print(f'wrote assets/song.wav  {len(y) / SR:.1f}s  ({len(T.events)} events)')


if __name__ == '__main__':
    main()
