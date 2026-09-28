"""Deliver a capture to the edit: ~/games/melee/plates/soback_<name>/v/ with
  f00001.jpg ...  1080x1920 JPEG q95 (a keyed pair: the BLACK pass, premultiplied colour)
  m00001.png ...  keyed pairs only: the matte as an LA PNG (luminance 255, alpha = coverage)
  audio.wav       the capture's DSP audio (SFX and voices; the director keeps music off) cut to the plates, 48 kHz
  info.json       {n, fps, pre, keyed, hits: [{film_t, frame, attacker, victim, dmg, move, logged}], notes}
                  frame is the 1-based plate the hit is first drawn on; film_t its film time; logged the director's HIT s
Frame 1 is the first script frame after the opening slate (film time -pre).
    .venv/bin/python projects/so-back/machinima/deliver.py RAW OUTDIR --len N --pre 60 [--mode aspect] [--notes '...']
    .venv/bin/python projects/so-back/machinima/deliver.py RAW_BLACK OUTDIR --grey RAW_GREY --len N --pre 60   # a keyed pair
"""
import argparse, glob, json, os, sys
from multiprocessing import Pool
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plates import is_slate, game_audio
from vplate import vplate
from dmatte import matte


def span(cap, n):
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


def one(job):
    k, a, b, mode, out = job
    A = vplate(Image.open(a).convert('RGB'), mode)
    if b is None:
        A.save(os.path.join(out, f'f{k:05d}.jpg'), quality=95); return
    B = vplate(Image.open(b).convert('RGB'), mode)
    pb, al = matte(np.asarray(A), np.asarray(B))
    Image.fromarray(pb.astype(np.uint8)).save(os.path.join(out, f'f{k:05d}.jpg'), quality=95)
    la = np.dstack([np.full(al.shape, 255, np.uint8), (al * 255 + .5).astype(np.uint8)])
    Image.fromarray(la, 'LA').save(os.path.join(out, f'm{k:05d}.png'), optimize=False, compress_level=3)


def hits(cap, pre):
    out = []
    for line in open(os.path.join(cap, 'osreport.log'), errors='replace'):
        w = line.split()
        if w and w[0] == 'HIT' and len(w) >= 6:
            s = int(w[1]) - 1        # HIT logs s + 1 (the counter has advanced when collisions run): the hit is drawn on s
            out.append(dict(film_t=round((s - pre) / 60, 4), frame=s + 1, attacker=int(w[2]), victim=int(w[3]),
                            dmg=float(w[4]), move=int(w[5]), logged=s + 1))
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('raw'); ap.add_argument('out')
    ap.add_argument('--grey'); ap.add_argument('--len', type=int, required=True); ap.add_argument('--pre', type=int, default=0)
    ap.add_argument('--mode', default='aspect'); ap.add_argument('--notes', default=''); ap.add_argument('--workers', type=int, default=6)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for f in glob.glob(os.path.join(a.out, '[fm]*.jpg')) + glob.glob(os.path.join(a.out, 'm*.png')): os.remove(f)
    fa, slate = span(a.raw, a.len)
    fb = span(a.grey, a.len)[0] if a.grey else [None] * a.len
    with Pool(a.workers) as pool:
        pool.map(one, [(k + 1, x, y, a.mode, a.out) for k, (x, y) in enumerate(zip(fa, fb))], chunksize=8)
    if os.path.exists(os.path.join(a.raw, 'dsp.wav')):
        game_audio(os.path.join(a.raw, 'dsp.wav'), os.path.join(a.out, 'audio.wav'), a.len, slate)
    info = dict(n=a.len, fps=60, pre=round(a.pre / 60, 4), keyed=bool(a.grey), w=1080, h=1920, hits=hits(a.raw, a.pre),
                notes=a.notes, raw=os.path.abspath(a.raw), raw_grey=os.path.abspath(a.grey) if a.grey else None)
    json.dump(info, open(os.path.join(a.out, 'info.json'), 'w'), indent=1)
    print(f'delivered {a.len} frames -> {a.out}' + (' (keyed)' if a.grey else ''))
