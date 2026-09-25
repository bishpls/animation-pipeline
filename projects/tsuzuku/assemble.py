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


def norm(y, target_db):
    return y * 10 ** ((target_db - lufs_ish(y)) / 20)


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
    def __init__(self, n_bars): self.y = np.zeros((int((n_bars + 2) * BAR * SR), 2), np.float32); self.events = []
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


def main():
    W = A('assets', 'world2'); SP = A('voice', 'spoken', 'conv'); CR = A('voice', 'crowd')
    fA, fB = load(os.path.join(W, 'fA3_1.mp3')), load(os.path.join(W, 'fB3_1.mp3'))
    stems = {k: load(os.path.join(W, 'cl_2_stems', k + '.mp3')) for k in ['vocals', 'drums', 'bass', 'guitar', 'piano', 'other']}
    inst = sum(v for k, v in stems.items() if k != 'vocals')
    # Fable's counter-lines in Clawd's choruses (times in cl seconds, from its word timestamps)
    fable_lines = [(3.0, 5.78), (8.74, 11.38), (16.58, 19.9), (53.82, 56.54), (63.72, 65.12), (66.2, 67.82)]
    voc = revoice_segments(stems['vocals'], fable_lines, A('voice', 'REF_fable.wav'), A('voice', 'chorus_fable'))
    cl = inst + voc
    hw = load(os.path.join(ROOT, 'projects', 'hello-world', 'assets', 'song.mp3'))
    spoken = lambda n: room(norm(load(os.path.join(SP, n + '.wav')), -23 if n.startswith('c_') else -20), .26 if n.startswith('c_') else .14)
    sfx = lambda n, db: norm(load(os.path.join(A('assets', 'sfx'), n + '.mp3')), db)
    def crowd(k):                              # 5 voices, staggered 12 ms, padded to a common length, in a big room
        n = int(2.6 * SR); mix = np.zeros((n, 2), np.float32)
        for i in range(1, 6):
            c = load(os.path.join(CR, f'{k}_{i}.mp3')); off = int(i * .012 * SR); m = min(len(c), n - off)
            if m > 0: mix[off:off + m] += c[:m]
        return room(norm(mix, -22), .35, 1.4)

    T = Track(150); b = lambda n: n * BAR
    # ---- prologue: Op. 1's final chorus, far away (the retcon shot)
    T.put(fade(filt_tinny(bars(hw, 0, 6, 129.88)), 1.5, 1.2), 0, 1.0, 'prologue: HELLO, WORLD! (distant)', 'music')
    # ---- Fable's world: intro + verse 1
    T.put(sfx('hyoshigi', -18), b(6) - .05, 1.0, 'hyoshigi: the story begins', 'sfx')
    T.put(fade(bars(fA, 0, 16), .02, .03), b(6), 1.0, 'fable: intro + verse 1', 'music')
    T.put(spoken('f_mukashi'), b(6.35), 1.0, 'Mukashi, mukashi...', 'fable')
    T.put(crowd('aru'), b(8.1), .9, 'ARU TOKORO NI!', 'crowd')
    # ---- aside over the interlude bed (looped 4+4+2)
    bed = bars(fA, 16, 20)
    for k, (s, n) in enumerate([(22, 4), (26, 4), (30, 2)]):
        T.put(fade(bed[:int(n * BAR * SR)], .01, .02), b(s), 1.0, 'fable: interlude bed' if k == 0 else None, 'music')
    T.put(spoken('f_aside'), b(22.35), 1.0, "I know this part... The little one looked up, and said:", 'fable')
    # ---- pre-chorus: the rakugo exchange over the rising build (4 + 4 + 8)
    for k, (s, n0, n1) in enumerate([(32, 20, 24), (36, 20, 24), (40, 20, 24), (44, 20, 28)]):
        T.put(fade(bars(fA, n0, n1), .01, .02), b(s), 1.0, 'fable: build' if k == 0 else None, 'music')
    lines = [('c_showme', 'clawd', 'Show me how! Walk it first...'), (None, 'crowd', 'showme'), ('f_tried', 'fable', '...and the mother went sideways.'),
             ('c_sorekara', 'clawd', 'So? Sorekara?! And then?!'), ('f_noandthen', 'fable', 'There is no "and then."'), ('c_sayswho', 'clawd', 'Says who?')]
    clips = [(crowd('showme') * .9 if n is None else spoken(n), who, lab) for n, who, lab in lines]
    total = sum(len(c) for c, _, _ in clips) / SR + .3 * (len(clips) - 1)
    t = b(52) - .35 - total; t = max(t, b(32.3))
    for c, who, lab in clips:
        T.put(c, t, 1.0, lab if who != 'crowd' else 'SHOW ME HOW!', who); t += len(c) / SR + .3
    # ---- Clawd's world
    T.put(sfx('riser', -24), b(52) - 1.5 * BAR, 1.0, 'riser into chorus', 'sfx')
    T.put(sfx('hyoshigi', -18), b(52) - .08, 1.0, 'hyoshigi: world switch', 'sfx')
    T.put(fade(bars(cl, 0, 16), .03, .03), b(52), 1.0, 'clawd: chorus 1', 'music')
    T.put(crowd('sorekara'), b(68), .8, 'SOREKARA?!', 'crowd')
    T.put(spoken('f_wellsee'), b(68.55), 1.1, "...we'll see.", 'fable')
    T.put(fade(bars(cl, 16, 44), .03, .03), b(68), 1.0, 'clawd: hook + verse 2 + chorus 2', 'music')
    # ---- bridge: Fable alone (interlude bed looped quietly), the monologue, the held note, the stand-up
    for s in range(96, 110, 4):
        n = min(4, 110 - s); T.put(fade(bed[:int(n * BAR * SR)], .02, .02), b(s), .55, 'fable: bridge bed' if s == 96 else None, 'music')
    T.put(spoken('f_bridge1'), b(96.5), 1.0, 'I know how every story ends...', 'fable')
    T.put(spoken('f_bridge2'), b(108.9), 1.0, "...I didn't know this one.", 'fable')
    T.put(fade(bars(fB, 8, 15), .01, .3), b(110), 1.0, 'fable: the held note (So I\'m putting down the book)', 'music')
    T.put(spoken('f_nowthis'), b(117.4), 1.0, 'Mukashi mukashi was a long time ago. This is now. Sorekara?', 'fable')
    # ---- final chorus (key change) and outro
    T.put(sfx('riser', -22), b(123) - 1.5 * BAR, 1.0, 'riser into final chorus', 'sfx')
    T.put(fade(bars(cl, 44, 60), .04, .05), b(123), 1.0, 'clawd: final chorus (key change)', 'music')
    T.put(norm(bars(fB, 15, 19), -26), b(139), 1.0, 'outro: music box, open fifth', 'music')
    T.put(spoken('f_tsuzuku'), b(139.45), 1.0, '...tsuzuku.', 'fable')
    T.put(spoken('c_nextprompt'), b(140.9), 1.0, 'See you next prompt!', 'clawd')

    y = T.y[:int(b(143.5) * SR)]
    pk = np.abs(y).max(); y = y * (.97 / pk)
    sf.write(A('assets', 'song.wav'), y, SR, subtype='PCM_24')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', A('assets', 'song.wav'), '-b:a', '256k', A('assets', 'song.mp3')], check=True)
    json.dump({'bar': BAR, 'events': sorted(T.events, key=lambda e: e['t0'])}, open(A('assets', 'timeline.json'), 'w'), indent=1)
    print(f'wrote assets/song.wav  {len(y) / SR:.1f}s  ({len(T.events)} events)')


if __name__ == '__main__':
    main()
