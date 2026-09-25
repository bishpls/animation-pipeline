"""つづく: assemble the duet from per-world generations on the shared bar grid (1 bar = 1.4118 s = 4/4@170 = 6/8@85).

    ../../.venv/bin/python assemble.py            -> assets/song.wav + assets/timeline.json (every event, for the picture)

Sources (chosen on evidence, see song/NOTES.md):
  fA  = assets/world2/fA3_1   Fable world: intro 4 | verse 12 (sung) | interlude bed 4 | build 8
  fB  = assets/world2/fB3_2   Fable world: silent bed 8 | the held note 7 | outro tail
  cl  = assets/world2/cl_2    Clawd world: chorus 16 | hook 4 | verse2 16 | chorus2 8 | final chorus 16
  hw  = ../hello-world/assets/song.mp3 (the Op. 1 quote)
Fable's counter-lines inside Clawd's choruses are cut from cl's vocal stem and re-voiced to REF_fable (tools/revoice.py).
Spoken lines (TTS -> Seed-VC) and crowd calls (5 layered voices) are placed on top.
"""
import json, os, subprocess, sys
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


def revoice_segments(stem, segs, ref, cache):
    """Replace segments [(t0, t1)] of a vocal stem (seconds) with voice-converted audio (cached)."""
    from revoice import convert
    out = stem.copy(); os.makedirs(cache, exist_ok=True)
    for k, (t0, t1) in enumerate(segs):
        a, b = int((t0 - .06) * SR), int((t1 + .12) * SR)
        src, dst = os.path.join(cache, f'seg{k}_src.wav'), os.path.join(cache, f'seg{k}_{os.path.basename(ref)}')
        if not os.path.exists(dst):
            sf.write(src, stem[a:b], SR); convert(src, ref, dst)
        c = load(dst); c = c[:b - a] if len(c) >= b - a else np.pad(c, ((0, b - a - len(c)), (0, 0)))
        c = norm(c, lufs_ish(stem[a:b]))
        w = np.ones(b - a); r = int(.03 * SR); w[:r] = np.linspace(0, 1, r); w[-r:] = np.linspace(1, 0, r)
        out[a:b] = out[a:b] * (1 - w[:, None]) + c * w[:, None]
    return out


def mute(stem, segs, pad=(.06, .12), fadelen=.04):
    out = stem.copy()
    for t0, t1 in segs:
        a, b = int((t0 - pad[0]) * SR), int((t1 + pad[1]) * SR); r = int(fadelen * SR)
        w = np.ones(b - a); w[:r] = np.linspace(1, 0, r); w[-r:] = np.linspace(0, 1, r); w[r:-r] = 0
        out[a:b] *= w[:, None]
    return out


def main():
    W = A('assets', 'world2'); W3 = A('assets', 'world3'); SP = A('voice', 'spoken', 'conv'); CR = A('voice', 'crowd')
    fA, fB = load(os.path.join(W, 'fA3_1.mp3')), load(os.path.join(W, 'fB3_1.mp3'))
    ofs = 4 * BAR                                   # both inpainted Clawd pieces start with a 4-bar generated lead-in
    # Clawd world A: build 4 | chorus1 16 | hook 4 | verse2 16 | chorus2 8 | breakdown 4. Fable's sung counter-lines are removed
    # from the vocal (Demucs stem) and replaced by her spoken lines (Seed-VC, locked voice): she talks back; Clawd sings.
    vA = load(os.path.join(W3, 'clA_1_dm', 'vocals.wav')); iA = load(os.path.join(W3, 'clA_1_dm', 'no_vocals.wav'))
    fl = [(3.0, 5.78), (8.74, 11.38), (16.58, 19.9), (53.82, 56.54)]
    clA = norm(iA + mute(vA, [(x + ofs, y + ofs) for x, y in fl]), -15.5)
    vB = load(os.path.join(W3, 'clB_2_dm', 'vocals.wav')); iB = load(os.path.join(W3, 'clB_2_dm', 'no_vocals.wav'))
    fl2 = [(63.72 - 62.118, 65.12 - 62.118), (66.2 - 62.118, 67.82 - 62.118)]
    clB = norm(iB + mute(vB, [(x + ofs, y + ofs) for x, y in fl2]), -14.5)
    hw = load(os.path.join(ROOT, 'projects', 'hello-world', 'assets', 'song.mp3'))
    spoken = lambda n, db=None: room(norm(load(os.path.join(SP, n + '.wav')), db or (-23 if n.startswith('c_') else -20)), .26 if n.startswith('c_') else .14)
    sfx = lambda n, db: norm(load(os.path.join(A('assets', 'sfx'), n + '.mp3')), db)
    def crowd(k):
        n = int(2.6 * SR); mix = np.zeros((n, 2), np.float32)
        for i in range(1, 6):
            c = load(os.path.join(CR, f'{k}_{i}.mp3')); off = int(i * .012 * SR); m = min(len(c), n - off)
            if m > 0: mix[off:off + m] += c[:m]
        return room(norm(mix, -22), .35, 1.4)

    T = Track(160); b = lambda n: n * BAR
    # ---- prologue (Op. 1, far away) and Fable's world
    T.put(fade(filt_tinny(bars(hw, 0, 6, 129.88)), 1.5, 1.2), 0, 1.0, 'prologue: HELLO, WORLD! (distant)', 'music')
    T.put(sfx('hyoshigi', -18), b(6) - .05, 1.0, 'hyoshigi: the story begins', 'sfx')
    T.put(fade(norm(bars(fA, 0, 16), -19), .02, .03), b(6), 1.0, 'fable: intro + verse 1', 'music')
    T.put(spoken('f_mukashi'), b(6.35), 1.0, 'Mukashi, mukashi...', 'fable')
    T.put(crowd('aru'), b(8.1), .9, 'ARU TOKORO NI!', 'crowd')
    bed = norm(bars(fA, 16, 20), -21)
    for k, (s, n) in enumerate([(22, 4), (26, 4), (30, 2)]):
        T.put(fade(bed[:int(n * BAR * SR)], .02, .02), b(s), 1.0, 'fable: interlude bed' if k == 0 else None, 'music')
    T.put(spoken('f_aside'), b(22.35), 1.0, "I know this part... The little one looked up, and said:", 'fable')
    for k, (s, n0, n1) in enumerate([(32, 20, 24), (36, 20, 24), (40, 20, 24), (44, 20, 28)]):
        T.put(fade(norm(bars(fA, n0, n1), -19.5), .02, .02), b(s), 1.0, 'fable: build' if k == 0 else None, 'music')
    # the rakugo exchange: ends with "Says who?" landing on the first bar of Clawd's build (the question starts the machine)
    lines = [('c_showme', 'clawd', 'Show me how! Walk it first...'), (None, 'crowd', 'showme'), ('f_tried', 'fable', '...and the mother went sideways.'),
             ('c_sorekara', 'clawd', 'So? Sorekara?! And then?!'), ('f_noandthen', 'fable', 'There is no "and then."')]
    clips = [(crowd('showme') * .9 if n is None else spoken(n), who, lab) for n, who, lab in lines]
    total = sum(len(c) for c, _, _ in clips) / SR + .3 * (len(clips) - 1)
    t = b(52) - .5 - total
    for c, who, lab in clips:
        T.put(c, t, 1.0, lab if who != 'crowd' else 'SHOW ME HOW!', who); t += len(c) / SR + .3
    # ---- into Clawd's world: a generated 4-bar build in her own key and timbre
    T.put(fade(clA, .02, .6), b(52), 1.0, "clawd: build + chorus 1 + hook + verse 2 + chorus 2 + breakdown", 'music')
    T.say(spoken('c_sayswho', -20), b(52) + .35, 'Says who?', 'clawd', -4)
    cA = b(52) + ofs                                  # clA chorus time 0 in song time
    for n, x, lab in [('f_counter1', 2.85, "Every story's borrowed..."), ('f_counter2', 8.45, "I have read how it ends..."),
                      ('f_counter3', 16.1, "That's the moral. No, it isn't..."), ('f_counter1', 53.7, "Every story's borrowed...")]:
        T.say(spoken(n, -17), cA + x, lab, 'fable')
    T.put(crowd('sorekara'), b(72), .8, 'SOREKARA?!', 'crowd')
    T.put(spoken('f_wellsee'), b(72.55), 1.1, "...we'll see.", 'fable')
    # ---- breath, clack, the bridge (chorus 2 winds down through its generated breakdown, bars 100-104)
    T.put(sfx('hyoshigi', -17), b(103), 1.0, 'hyoshigi: the story stops', 'sfx')
    for k, s in enumerate([103.2, 107.2, 111.2]):
        n = 4 if s < 111 else 4.8
        T.put(fade(np.concatenate([bed, bed])[:int(n * BAR * SR)], 1.2 if k == 0 else .02, .02), b(s), 1.0, 'fable: bridge bed' if k == 0 else None, 'music')
    T.put(spoken('f_bridge1'), b(103.6), 1.0, 'I know how every story ends...', 'fable')
    # the held note: start its section two bars early on its own lute, so there's air; the confession sits in that air
    T.put(fade(norm(bars(fB, 6, 15), -18.5), .4, .5), b(116), 1.0, "fable: the held note (So I'm putting down the book)", 'music')
    T.put(spoken('f_bridge2'), b(116.4), 1.0, "...I didn't know this one.", 'fable')
    # ---- "Sorekara?" launches the key-change pickup (generated 4 bars in Clawd's world), then the final chorus
    T.put(fade(bed[:int(4 * BAR * SR)], .3, .3), b(125), .5, 'fable: bed under "this is now"', 'music')
    T.put(spoken('f_nowthis'), b(125.2), 1.0, 'Mukashi mukashi was a long time ago. This is now. Sorekara?', 'fable')
    T.put(fade(clB, 1.5, .05), b(129), 1.0, 'clawd: key-change pickup + final chorus', 'music')
    cB = b(129) + ofs
    T.say(spoken('f_tsuzuku', -17), cB + 1.62, '...tsuzuku.', 'fable')
    T.say(spoken('f_counter5', -17), cB + 4.08, "And I'm made of 'and then.'", 'fable')
    # ---- outro
    T.put(norm(bars(fB, 15, 19), -26), b(149), 1.0, 'outro: music box, open fifth', 'music')
    T.put(spoken('f_tsuzuku'), b(149.45), 1.0, '...tsuzuku.', 'fable')
    T.put(spoken('c_nextprompt'), b(150.9), 1.0, 'See you next prompt!', 'clawd')

    y = T.mix()[:int(b(153.5) * SR)]
    pk = np.abs(y).max(); y = y * (.97 / pk)
    sf.write(A('assets', 'song.wav'), y, SR, subtype='PCM_24')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', A('assets', 'song.wav'), '-b:a', '256k', A('assets', 'song.mp3')], check=True)
    json.dump({'bar': BAR, 'events': sorted(T.events, key=lambda e: e['t0'])}, open(A('assets', 'timeline.json'), 'w'), indent=1)
    print(f'wrote assets/song.wav  {len(y) / SR:.1f}s  ({len(T.events)} events)')


if __name__ == '__main__':
    main()
