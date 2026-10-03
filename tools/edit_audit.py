"""The edit audit (docs/CRAFT.md §0.5, "let every shot conclude"; run it on every draft before it goes to Michael).
Generalised from Geno's trailer edit kit (pacing.py + check.py), so any film can run it from its own shot list.

    .venv/bin/python tools/edit_audit.py SHOTS.json [--video DRAFT.mp4] [--sfx STEM.wav] [--out AUDIT.json]

SHOTS.json, exported by the film (e.g. `node engine/render.mjs P --eval='JSON.stringify(...)'` over its own cut table):
    {"fps": 60, "shots": [{"id": "4.6", "t0": 27.48, "len": 3.42, "kind": "action", "payoff": 2.67,
                           "tail": 0.8, "flurry": false, "continues": false, "audio": "take.wav", "audio_in": 0.2}, ...]}
  kind     action (hold >= 0.75 s after the payoff) | reveal (a punchline, reaction or reveal: >= 1.0 s) |
           card (>= 1.5 s once legible) | impact (an impact frame or white-out: no minimum) | flurry (a deliberate run of
           short details, at most 3 in a row)
  payoff   seconds into the shot where its action pays off (null: not logged yet, flagged)
  tail     seconds of the shot's own sound deliberately carried past the cut (a J/L-cut)
  continues  the next shot carries the same performance on (multi-angle coverage of one action): no hold, no audio check
  audio    optional: the shot's own sound (a take's wav), `audio_in` = its time at the shot's first frame. Without it,
           --sfx (a film-length stem of the non-music sound) is read at the shot's own film times.

Checks:
  picture  each shot's hold after its payoff against its kind's minimum; shots under 1.5 s (except impact and flurry);
           runs of more than 3 short shots; the median and mean shot.
  audio    "audio concludes too": a sound that starts in the shot and is still within 20 dB of its own peak at the cut
           (and well over the shot's bed) is flagged with how long it needs, unless `tail` carries it that far.
  --video  each cut on its frame (the onset of the frame-difference spike, +-6 frames); clicks at every cut (the 3 kHz+
           band's 3 ms energy at the cut against the 30 ms either side, flagged over 6 dB); loudness and true peak (EBU R128).
Prints a summary and writes the full result as JSON (default: next to SHOTS.json as *_audit.json).
"""
import argparse, json, math, os, statistics, subprocess
import numpy as np

HOLD_MIN = {'action': 0.75, 'reveal': 1.0, 'card': 1.5, 'impact': 0.0, 'flurry': 0.0}
SHORT = 1.5
SR = 48000
W = int(SR * .05)


def decode(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vn', '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64)


def db(x):
    return 20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-9) if len(x) else -180.0


def ringing(y, a, b, carried):
    """the shot's sound from a to b (seconds in y): an event still sounding at the cut, and how long it needs to fall"""
    win = lambda t: y[int(t * SR):int(t * SR) + W]
    inside = [db(win(t)) for t in np.arange(a, max(a, b - .05), .05)]
    if not inside: return None, None
    peak = max(inside); at_cut = db(win(max(a, b - .05))); floor = float(np.percentile(inside, 20))
    res = dict(peak_db=round(peak, 1), at_cut_db=round(at_cut, 1), floor_db=round(floor, 1), below_peak=round(peak - at_cut, 1))
    if not (peak > -60 and peak - floor > 10 and peak - at_cut < 20 and at_cut > floor + 6): return res, None
    t, need = b, None
    while t < len(y) / SR - .05:
        if peak - db(win(t)) >= 20 or db(win(t)) <= floor + 6: need = t - b; break
        t += .05
    res['needs_s'] = round(need, 2) if need is not None else None
    if need is not None and (need <= .1 or need <= carried): return res, None
    if need is None and carried >= .5: return res, None
    return res, (f"sound still ringing at the cut ({peak - at_cut:.0f} dB under its peak; it falls 20 dB "
                 + (f"{need:.2f} s later)" if need is not None else "only after its audio ends)"))


def pacing(shots, sfx):
    cache = {}
    for s in shots:
        s['flags'] = []
        s['t1'] = s['t0'] + s['len']
        kind = s.get('kind', 'action')
        s['holdMin'] = HOLD_MIN.get(kind, 0.75)
        s['hold'] = None if s.get('payoff') is None else round(s['len'] - s['payoff'], 3)
        if s.get('continues'): continue
        if kind not in ('impact', 'flurry') and not s.get('flurry'):
            if s['hold'] is None: s['flags'].append('no payoff logged')
            elif s['hold'] < s['holdMin'] - 1e-6: s['flags'].append(f"hold {s['hold']:.2f} s < {s['holdMin']:.2f} after the payoff")
            if s['len'] < SHORT - 1e-6: s['flags'].append(f"short shot {s['len']:.2f} s")
        # audio concludes too
        src, a = (s.get('audio'), s.get('audio_in', 0.0)) if s.get('audio') else (sfx, s['t0'])
        if src and not s.get('flurry'):
            if src not in cache: cache[src] = decode(src)
            res, flag = ringing(cache[src], max(0.0, a), max(0.0, a) + s['len'], s.get('tail') or 0.0)
            s['audio_check'] = res
            if flag: s['flags'].append(flag)
    run = []
    for s in shots + [None]:
        if s is not None and s['len'] < SHORT - 1e-6 and s.get('kind') != 'impact': run.append(s); continue
        if len(run) > 3:
            for r in run: r['flags'].append(f"one of {len(run)} short shots in a row ({run[0]['id']}..{run[-1]['id']})")
        run = []
    lens = [s['len'] for s in shots]
    return dict(n=len(shots), runtime=round(shots[-1]['t1'], 3), median_shot=round(statistics.median(lens), 3),
                mean_shot=round(sum(lens) / len(lens), 3), flagged=[s['id'] for s in shots if s['flags']])


def video_checks(video, shots, fps):
    w, h = 96, 54
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', video, '-vf', f'scale={w}:{h},format=gray', '-f', 'rawvideo', '-'],
                         capture_output=True, check=True).stdout
    V = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
    D = np.r_[0, np.abs(np.diff(V, axis=0)).mean(axis=(1, 2))]
    nF = len(V)

    def onset(f, r=6):
        lo, hi = max(1, f - r), min(nF - 1, f + r); win = D[lo:hi + 1]
        return int(lo + np.argmax(win >= .6 * win.max())) if win.max() > 0 else None
    cuts = []
    for s in shots[1:]:
        f0 = round(s['t0'] * fps); m = onset(f0)
        cuts.append(dict(id=s['id'], f0=f0, measured=m, ok=m == f0))
    from scipy.signal import butter, sosfilt
    A = decode(video)
    hp = sosfilt(butter(4, 3000, 'high', fs=SR, output='sos'), A)
    k3, k30 = int(.003 * SR), int(.03 * SR)
    e = lambda x: float(np.sqrt((x ** 2).mean()) + 1e-9)
    clicks = []
    for s in shots[1:]:
        i = int(s['t0'] * SR)
        if i - k3 - k30 < 0 or i + k3 + k30 > len(hp): continue
        at, before, after = e(hp[i - k3:i + k3]), e(hp[i - k3 - k30:i - k3]), e(hp[i + k3:i + k3 + k30])
        clicks.append(dict(id=s['id'], t=round(s['t0'], 3), db_over=round(20 * math.log10(at / max(before, after)), 1)))
    eb = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', video, '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                        capture_output=True, text=True).stderr
    tail = eb[eb.rfind('Summary:'):]
    loud = dict(I=float(tail.split('I:')[1].split('LUFS')[0]), TP=float(tail.split('Peak:')[1].split('dBFS')[0]),
                LRA=float(tail.split('LRA:')[1].split('LU')[0]))
    return dict(frames=nF, duration_s=round(nF / fps, 3), cuts_on_frame=sum(c['ok'] for c in cuts), cuts=len(cuts),
                cuts_off=[c for c in cuts if not c['ok']], clicks_over_6db=[c for c in clicks if c['db_over'] > 6],
                loudness=loud)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('shots'); ap.add_argument('--video'); ap.add_argument('--sfx'); ap.add_argument('--out')
    a = ap.parse_args()
    spec = json.load(open(a.shots))
    fps = spec.get('fps', 60); shots = spec['shots']
    res = dict(pacing=pacing(shots, a.sfx), shots=shots)
    if a.video: res['video'] = video_checks(a.video, shots, fps)
    out = a.out or os.path.splitext(a.shots)[0] + '_audit.json'
    json.dump(res, open(out, 'w'), indent=1)
    p = res['pacing']
    print(f"{p['n']} shots, {p['runtime']:.2f} s, median {p['median_shot']:.2f} s, mean {p['mean_shot']:.2f} s; flagged {len(p['flagged'])}")
    for s in shots:
        if s['flags']: print(f"  {s['id']:6s} {s['len']:.2f} s  " + '; '.join(s['flags']))
    if a.video:
        v = res['video']
        print(f"  cuts on their frame {v['cuts_on_frame']}/{v['cuts']}"
              + ''.join(f"; {c['id']} f{c['f0']} measured {c['measured']}" for c in v['cuts_off']))
        print(f"  loudness {v['loudness']['I']} LUFS, true peak {v['loudness']['TP']} dBTP; clicks over 6 dB: "
              + (', '.join(f"{c['id']} ({c['db_over']})" for c in v['clicks_over_6db']) or 'none'))
    print('wrote', out)


if __name__ == '__main__':
    main()
