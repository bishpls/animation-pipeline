"""Deliver the ending (a one-stock match: the sacred combo's punch takes Fox's last stock) from one raw 4:3 capture:
  soback_end_game     the punch, the KO and the GAME! splash (4:3 HUD: v43/ 1440x1080, plus a centred 9:16 slice in v/)
  soback_end_victory  Falcon's victory screen: the emblem sweep, his pose (v43/ + a 9:16 slice framed on him)
  soback_end_results  the results table (v43/ + a centred slice)
The match audio is synced by the slate click. A scene change loads from disc: the game presents no frames while it loads
but the DSP dump keeps running, so the victory screen's audio is re-synced: its first frame <-> where the DSP audio comes
back after the load's silence. The announcer's lines are then located by cross-correlation with his own clips.
    .venv/bin/python projects/so-back/director/end_deliver.py RAW"""
import glob, json, os, sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np, soundfile as sf
from PIL import Image
from scipy.signal import resample_poly, fftconvolve
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'machinima'))
from plates import is_slate

ANN = os.path.expanduser('~/games/melee/work/announcer')
PRE = 60


def one(job):
    src, dst, cx, d43 = job
    im = Image.open(src).convert('RGB'); w = im.size[0]; dh = round(w * 3 / 4)
    im = im.resize((w, dh), Image.LANCZOS)
    cw = round(dh * 9 / 16); x0 = min(max(0, round(cx * w - cw / 2)), w - cw)
    im.crop((x0, 0, x0 + cw, dh)).resize((1080, 1920), Image.LANCZOS).save(dst, quality=95)
    im.resize((1440, 1080), Image.LANCZOS).save(os.path.join(d43, os.path.basename(dst)), quality=95)


def find(y, sr, clip, lo, hi):
    c, cs = sf.read(clip); c = c.mean(1) if c.ndim > 1 else c; c = resample_poly(c, sr, cs)
    seg = y[int(lo * sr):int(hi * sr)]
    num = fftconvolve(seg, c[::-1], mode='valid')
    e = np.sqrt(fftconvolve(seg ** 2, np.ones(len(c)), mode='valid')) * np.sqrt(np.sum(c ** 2)) + 1e-9
    k = int(np.argmax(num / e)); return lo + k / sr, float((num / e)[k]), len(c) / sr


if __name__ == '__main__':
    raw = sys.argv[1]
    fs = sorted(glob.glob(os.path.join(raw, 'f*.png')))
    sl = [is_slate(f) for f in fs[:40]]
    first = next(i for i in range(39) if sl[i] and not sl[i + 1]) + 1
    slate = first - next(i for i in range(first) if sl[i])
    n = len(fs) - first
    small = [np.asarray(Image.open(f).convert('RGB').resize((64, 48))) for f in fs[first:]]
    # the victory screen: a black field (the match's last frame is FD); the results table: its grey panel
    dark = [float(a.mean()) for a in small]
    s_v = next(s for s in range(200, n) if dark[s] < 25 and dark[s + 1] < 25)
    s_r = next(s for s in range(s_v + 100, n) if dark[s] > dark[s_v + 100] + 1.5)   # the results panel starts to slide in
    y, sr = sf.read(os.path.join(raw, 'dsp.wav')); y = y.mean(1) if y.ndim > 1 else y
    m = np.abs(y); h = int(sr * .002)
    env = np.array([m[i:i + h].max() for i in range(0, len(m), h)])
    c0 = next(i * h for i in range(1, len(env)) if env[i] > .02 and env[i - 1] <= .02)      # the opening slate's click
    t_match = lambda s: c0 / sr + (s + slate) / 60                                              # match frames: nominal
    # the load: the longest near-silence after the GAME! call; the victory audio resumes at its end
    q = np.array([np.sqrt(np.mean(y[i:i + int(sr * .01)] ** 2)) for i in range(0, len(y) - int(sr * .01), int(sr * .01))])
    t_game = t_match(s_v - 60)
    run, best, cur = 0, (0, 0), None
    for k in range(int(t_game * 100), len(q)):
        if q[k] < 1e-4:
            cur = k if run == 0 else cur; run += 1
            if run > best[0]: best = (run, cur)
        else: run = 0
    t_resume = (best[1] + best[0]) / 100 - 0.02    # the victory screen's first frame: the DSP audio comes back
    t_vict = lambda s: t_resume + (s - s_v) / 60
    lines = {}
    for name, clip, lo, hi in (('GAME!', glob.glob(f'{ANN}/names/nr_name_37_*')[0], t_match(200), t_resume),
                               ("This game's winner is...", glob.glob(f'{ANN}/banks/nr_vs/*05*')[0], t_resume - 0.5, t_resume + 6),
                               ('CAPTAIN FALCON!', glob.glob(f'{ANN}/names/nr_name_00_*')[0], t_resume, t_resume + 8)):
        t, v, L = find(y, sr, clip, lo, hi)
        s = (t - c0 / sr) * 60 - slate if name == 'GAME!' else max(s_v, s_v + (t - t_resume) * 60)   # starts with the screen
        lines[name] = dict(dsp_s=round(t, 3), ncc=round(v, 2), plate_frame=int(round(s)) + 1, len_s=round(L, 2))
    print('victory screen from plate', s_v + 1, '; results from', s_r + 1, '; load silence', best[0] / 100, 's, resume at dsp', t_resume)
    print(json.dumps(lines, indent=1))
    cx_f = 0.52                                   # Falcon's centre on the victory screen (his guard stance), measured on v43
    shots = [('end_game', 200, s_v, .5, t_match, "The ending's KO in a real one-stock match (stocks=1; no freeze; the game's own "
              "camera): the sacred combo's Falcon Punch takes Fox's last stock, the side-blast KO, and Melee's GAME! splash with "
              "the 4:3 HUD intact. Use v43/ for the splash (it spans the 4:3 width); v/ is a centred 9:16 slice."),
             ('end_victory', s_v, s_r, cx_f, t_vict, "Falcon's victory screen: the emblem sweep and his pose, chosen by holding B on "
              "his port as the screen sets up (pose 0: a flying kick, a landing, then a low guard facing the viewer, palm out). "
              "v/ is a 9:16 slice framed on him; v43/ the full screen. Audio re-synced after the scene load: the announcer's "
              "'This game's winner is... CAPTAIN FALCON!'."),
             ('end_results', s_r, n, .5, t_vict, 'The results table (4:3 screen-space UI: use v43/).')]
    for name, s0, s1, cx, tmap, notes in shots:
        out = os.path.expanduser(f'~/games/melee/plates/soback_{name}/v'); d43 = os.path.join(os.path.dirname(out), 'v43')
        for d in (out, d43):
            os.makedirs(d, exist_ok=True)
            for f in glob.glob(os.path.join(d, 'f*.jpg')): os.remove(f)
        with ProcessPoolExecutor(6) as ex:
            list(ex.map(one, [(fs[first + s], os.path.join(out, f'f{k + 1:05d}.jpg'), cx, d43) for k, s in enumerate(range(s0, s1))], chunksize=4))
        a0 = int(round(tmap(s0) * sr)); seg = y[a0:a0 + int(round((s1 - s0) / 60 * sr))]
        sf.write(os.path.join(out, 'audio.wav'), resample_poly(seg, 48000, sr) if abs(sr - 48000) > 1 else seg, 48000)
        ev = [dict(label=k, frame=v['plate_frame'] - s0, t=round((v['plate_frame'] - 1 - s0) / 60, 3)) for k, v in lines.items()
              if s0 < v['plate_frame'] <= s1]
        json.dump(dict(n=s1 - s0, fps=60, pre=0.0, keyed=False, w=1080, h=1920, mode='crop', slice_cx=round(cx, 3),
                       v43='../v43 (1440x1080, same numbering)', source=dict(capture=os.path.abspath(raw), plate_frames=[s0 + 1, s1]),
                       events=ev, notes=notes), open(os.path.join(out, 'info.json'), 'w'), indent=1)
        print(f'{name}: {s1 - s0} frames -> {out}')
