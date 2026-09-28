"""Edit-ready vertical plates from director captures (the format projects/so-back/src/edit.js loads).
    .venv/bin/python projects/so-back/prep_plates.py OUT_DIR --stage CAPTURE [--mode aspect]          # stage-on
    .venv/bin/python projects/so-back/prep_plates.py OUT_DIR --black CAP_B --grey CAP_G [--mode aspect]   # keyed pair
Writes OUT_DIR/f00001.jpg (the frame, or the black pass = premultiplied colour) and, for a keyed pair, OUT_DIR/m00001.png
(LA: luminance 255, alpha = coverage; a browser reads a grey 'L' PNG as opaque). Captures are plates.py-trimmed dirs of
f00001.png... (or raw dumps; frames are taken in sorted order)."""
import argparse, os, sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'machinima'))
from vplate import vplate
from dmatte import matte


def frames(d):
    return sorted(f for f in os.listdir(d) if f.endswith('.png') and f[0] in 'f')


def one(job):
    i, out, mode, stage, black, grey = job
    if stage:
        vplate(Image.open(stage).convert('RGB'), mode).save(f'{out}/f{i:05d}.jpg', quality=95)
        return
    b, g = (vplate(Image.open(p).convert('RGB'), mode) for p in (black, grey))
    pb, a = matte(np.asarray(b), np.asarray(g))
    Image.fromarray(pb.astype(np.uint8)).save(f'{out}/f{i:05d}.jpg', quality=95)
    la = np.dstack([np.full(a.shape, 255, np.uint8), (a * 255 + .5).astype(np.uint8)])
    Image.fromarray(la, 'LA').save(f'{out}/m{i:05d}.png', optimize=False, compress_level=3)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('--stage'); ap.add_argument('--black'); ap.add_argument('--grey')
    ap.add_argument('--mode', default='aspect'); ap.add_argument('--workers', type=int, default=6)
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    if a.stage:
        fs = frames(a.stage); jobs = [(i + 1, a.out, a.mode, os.path.join(a.stage, f), None, None) for i, f in enumerate(fs)]
    else:
        fb, fg = frames(a.black), frames(a.grey)
        if len(fb) != len(fg): sys.exit(f'pass lengths differ: {len(fb)} vs {len(fg)}')
        jobs = [(i + 1, a.out, a.mode, None, os.path.join(a.black, x), os.path.join(a.grey, y)) for i, (x, y) in enumerate(zip(fb, fg))]
    with ProcessPoolExecutor(a.workers) as ex: list(ex.map(one, jobs, chunksize=4))
    print(f'{len(jobs)} frames -> {a.out}')
