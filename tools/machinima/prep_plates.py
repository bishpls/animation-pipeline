"""Edit-ready plates from director captures: what a plate-based film loads (engine/plate.js; keyed pairs as in SO BACK).
    OUT/f00001.jpg ...  1080x1920 (--w) JPEG q95: the frame, or for a keyed pair the BLACK pass (premultiplied colour)
    OUT/m00001.png ...  keyed pairs only: the matte as an LA PNG (luminance 255, alpha = coverage; a browser reads a grey 'L'
                        PNG as opaque, so the coverage must be the alpha channel)
    OUT/audio.wav       slate mode: the capture's game audio (SFX and voices; the director keeps music off) cut to the plates
    OUT/info.json       slate mode: {n, fps, pre, keyed, w, h, hits: [{film_t, frame, attacker, victim, dmg, move, logged}], ...}

Slate mode, a director capture (trimmed between the magenta slates; refused if the frame count is off by one):
    .venv/bin/python tools/machinima/prep_plates.py OUT --capture RAW --len N [--pre F] [--mode aspect|crop|roll] [--notes '...']
    .venv/bin/python tools/machinima/prep_plates.py OUT --capture RAW_BLACK --grey RAW_GREY --len N --pre F      # a keyed pair
Raw mode, every f*.png of a folder in order (no slates, no audio):
    .venv/bin/python tools/machinima/prep_plates.py OUT --stage DIR
    .venv/bin/python tools/machinima/prep_plates.py OUT --black DIR --grey DIR
--mode (vplate.py): aspect is a DirSetup.aspect = 9/16 capture squeezed to portrait (2.37x supersampled at res 4); crop a
centred 9:16 slice of 4:3 (keeps the HUD undistorted); roll a 90-degree camera roll rotated back (not recommended: it
rotates camera-facing effects). A keyed pair is two captures of one script, stage hidden, on clear colour black then grey 96:
dmatte.py solves the coverage exactly and the black pass keeps additive glows. Composite: out = black + (1 - a) * BG.
Frame 1 is the first script frame after the opening slate (film time -pre/60). The director logs HIT s + 1 (its counter has
advanced when collisions run): info.json's hit frame is the one it is drawn on, and `logged` keeps the raw value.
Plates are renders of game data: keep OUT outside the repo (or under a gitignored path).
"""
import argparse, glob, json, os, sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plates import is_slate, game_audio
from vplate import vplate
from dmatte import matte


def frames(d):
    """A raw folder's frames in order (f*.png)."""
    return sorted(f for f in os.listdir(d) if f.endswith('.png') and f[0] in 'f')


def one(job):
    """One plate frame: job = (index, out, mode, stage PNG | None, black PNG | None, grey PNG | None)."""
    i, out, mode, stage, black, grey = job
    if stage:
        vplate(Image.open(stage).convert('RGB'), mode).save(f'{out}/f{i:05d}.jpg', quality=95)
        return
    b, g = (vplate(Image.open(p).convert('RGB'), mode) for p in (black, grey))
    pb, a = matte(np.asarray(b), np.asarray(g))
    Image.fromarray(pb.astype(np.uint8)).save(f'{out}/f{i:05d}.jpg', quality=95)
    la = np.dstack([np.full(a.shape, 255, np.uint8), (a * 255 + .5).astype(np.uint8)])
    Image.fromarray(la, 'LA').save(f'{out}/m{i:05d}.png', optimize=False, compress_level=3)


def span(cap, n):
    """The frames between a capture's slates (exactly n, or refused) and the opening slate's length (for the audio cut)."""
    fs = sorted(glob.glob(os.path.join(cap, 'f*.png')))
    sl = [is_slate(f) for f in fs]
    first = next(i for i in range(len(fs) - 1) if sl[i] and not sl[i + 1]) + 1
    last = next((i for i in range(first, len(fs)) if sl[i]), None)
    if last is None:                     # a close shot can cover the corners plates.is_slate checks: test the top edge instead
        top = lambda f: (np.abs(np.asarray(Image.open(f).convert('RGB').resize((64, 64)))[:4].reshape(-1, 3).astype(int)
                                - (255, 0, 255)).max(1) < 40).mean() > .5
        last = next((i for i in range(first, len(fs)) if top(fs[i])), None)
        if last is None: sys.exit(f'{cap}: no end slate found')
    if last - first != n: sys.exit(f'{cap}: {last - first} frames between the slates, the script has {n}: refused')
    slate = first - next(i for i in range(first) if sl[i])
    return fs[first:last], slate


def hits(cap, pre):
    out = []
    for line in open(os.path.join(cap, 'osreport.log'), errors='replace'):
        w = line.split()
        if w and w[0] == 'HIT' and len(w) >= 6:
            s = int(w[1]) - 1        # HIT logs s + 1 (the counter has advanced when collisions run): the hit is drawn on s
            out.append(dict(film_t=round((s - pre) / 60, 4), frame=s + 1, attacker=int(w[2]), victim=int(w[3]),
                            dmg=float(w[4]), move=int(w[5]), logged=s + 1))
    return out


def run(jobs, workers=6):
    with ProcessPoolExecutor(workers) as ex: list(ex.map(one, jobs, chunksize=4))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('out')
    ap.add_argument('--capture'); ap.add_argument('--stage'); ap.add_argument('--black'); ap.add_argument('--grey')
    ap.add_argument('--len', type=int); ap.add_argument('--pre', type=int, default=0)
    ap.add_argument('--mode', default='aspect'); ap.add_argument('--notes', default=''); ap.add_argument('--workers', type=int, default=6)
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    if a.capture:                                                     # slate mode
        if not a.len: sys.exit('--len N (the script length in frames) is required with --capture')
        for f in glob.glob(os.path.join(a.out, 'f*.jpg')) + glob.glob(os.path.join(a.out, 'm*.png')): os.remove(f)
        fa, slate = span(a.capture, a.len)
        fb = span(a.grey, a.len)[0] if a.grey else [None] * a.len
        jobs = [(k + 1, a.out, a.mode, None if a.grey else x, x if a.grey else None, y) for k, (x, y) in enumerate(zip(fa, fb))]
        run(jobs, a.workers)
        if os.path.exists(os.path.join(a.capture, 'dsp.wav')):
            game_audio(os.path.join(a.capture, 'dsp.wav'), os.path.join(a.out, 'audio.wav'), a.len, slate)
        info = dict(n=a.len, fps=60, pre=round(a.pre / 60, 4), keyed=bool(a.grey), w=1080, h=1920, hits=hits(a.capture, a.pre),
                    notes=a.notes, raw=os.path.abspath(a.capture), raw_grey=os.path.abspath(a.grey) if a.grey else None)
        json.dump(info, open(os.path.join(a.out, 'info.json'), 'w'), indent=1)
        print(f'{a.len} frames -> {a.out}' + (' (keyed)' if a.grey else ''))
    else:                                                             # raw mode
        if a.stage:
            fs = frames(a.stage); jobs = [(i + 1, a.out, a.mode, os.path.join(a.stage, f), None, None) for i, f in enumerate(fs)]
        elif a.black and a.grey:
            fb, fg = frames(a.black), frames(a.grey)
            if len(fb) != len(fg): sys.exit(f'pass lengths differ: {len(fb)} vs {len(fg)}')
            jobs = [(i + 1, a.out, a.mode, None, os.path.join(a.black, x), os.path.join(a.grey, y)) for i, (x, y) in enumerate(zip(fb, fg))]
        else:
            sys.exit('give --capture (slate mode), or --stage, or --black and --grey (raw mode)')
        run(jobs, a.workers)
        print(f'{len(jobs)} frames -> {a.out}')
