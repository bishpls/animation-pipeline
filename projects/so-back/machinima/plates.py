"""Plates from a director capture: trim to the frames between the two slates, check the count, re-encode for the engine.
    .venv/bin/python tools/machinima/plates.py trim CAPTURE OUT [--len 2040] [--aspect 16:9|4:3] [--w 1920] [--q 95]
    .venv/bin/python tools/machinima/plates.py sheet OUT --every 30 [--w 320]        # contact sheet of the plates
CAPTURE is tools/machinima/dolphin.py's output (f00001.png ...). The director (tools/machinima/melee/director) shows a
magenta slate before and after the script: its first frame after the opening slate is script frame 0. With --len, the
frames between the slates must number exactly that, or the run dropped or doubled frames and the plates are refused.
Frames are resized to the display aspect (Dolphin dumps the raw internal-resolution buffer) and written as JPEG
f00001.jpg ... for engine/plate.js, with plates.json (count, fps, size, source).
Audio: the director clicks on each slate's first frame, so the game's DSP dump (dsp.wav, which starts at emulator boot) is
cut between the two clicks and resampled to exactly the script's length at 48 kHz: game.wav, sample-locked to the plates.
"""
import argparse, glob, json, os, sys
import numpy as np
from PIL import Image

MAGENTA = np.array([255, 0, 255])


def is_slate(path):
    im = Image.open(path).convert('RGB'); w, h = im.size
    a = np.asarray(im.resize((64, 64), Image.BILINEAR)).astype(int)
    corners = np.concatenate([a[:8, :8].reshape(-1, 3), a[:8, -8:].reshape(-1, 3), a[-8:, :8].reshape(-1, 3), a[-8:, -8:].reshape(-1, 3)])
    return np.abs(corners - MAGENTA).max(axis=1).mean() < 40


def trim(a):
    fs = sorted(glob.glob(os.path.join(a.capture, 'f*.png')))
    if not fs: sys.exit('no frames in ' + a.capture)
    slate = [is_slate(f) for f in fs]
    runs, i = [], 0
    while i < len(fs):
        if slate[i]:
            j = i
            while j + 1 < len(fs) and slate[j + 1]: j += 1
            runs.append((i, j)); i = j + 1
        else: i += 1
    if len(runs) < 2: sys.exit(f'expected two slates, found {len(runs)}: {runs}')
    first, last = runs[0][1] + 1, runs[1][0]
    n = last - first
    print(f'{len(fs)} captured; slates at {runs[:2]}; script frames {first + 1}..{last} = {n}')
    if a.len and n != a.len: sys.exit(f'refused: {n} frames between the slates, the script has {a.len} (dropped or doubled frames)')
    os.makedirs(a.out, exist_ok=True)
    for f in glob.glob(os.path.join(a.out, 'f*.jpg')): os.remove(f)
    aw, ah = map(int, a.aspect.split(':')); W = a.w; H = int(round(W * ah / aw / 2)) * 2
    for k, f in enumerate(fs[first:last]):
        Image.open(f).convert('RGB').resize((W, H), Image.LANCZOS).save(os.path.join(a.out, f'f{k + 1:05d}.jpg'), quality=a.q)
    run = json.load(open(os.path.join(a.capture, 'run.json'))) if os.path.exists(os.path.join(a.capture, 'run.json')) else {}
    json.dump({'n': n, 'fps': 60, 'w': W, 'h': H, 'aspect': a.aspect, 'capture': os.path.abspath(a.capture), 'run': run},
              open(os.path.join(a.out, 'plates.json'), 'w'), indent=1)
    if os.path.exists(os.path.join(a.capture, 'dsp.wav')):
        game_audio(os.path.join(a.capture, 'dsp.wav'), os.path.join(a.out, 'game.wav'), n, runs[0][1] - runs[0][0] + 1)
    for f in ('osreport.log',):
        if os.path.exists(os.path.join(a.capture, f)):
            import shutil; shutil.copy(os.path.join(a.capture, f), a.out)
    print(f'wrote {n} plates {W}x{H} -> {a.out}')


def game_audio(src, out, n, slate, fps=60, sr_out=48000):
    import soundfile as sf
    from scipy.signal import resample
    y, sr = sf.read(src, always_2d=True)
    m = np.abs(y).max(axis=1); h = max(1, int(sr * 0.002))
    env = np.array([m[i:i + h].max() for i in range(0, len(m), h)])
    on = [i * h for i in range(1, len(env)) if env[i] > 0.02 and env[i - 1] <= 0.02]
    if not on: print('game audio: no slate click found; skipped'); return
    c0 = on[0]; want = (n + slate) / fps * sr                        # the end slate's click, n + slate frames later
    c1 = min(on, key=lambda o: abs(o - c0 - want))
    if abs(c1 - c0 - want) > 0.02 * sr: print(f'game audio: end click not found near {want / sr:.3f}s; using the nominal rate'); c1 = int(c0 + want)
    rate = (c1 - c0) / ((n + slate) / fps)                           # dump samples per film second
    a0 = int(round(c0 + slate / fps * rate)); a1 = int(round(c0 + (n + slate) / fps * rate))
    seg = resample(y[a0:a1], int(round(n / fps * sr_out)), axis=0)
    sf.write(out, np.clip(seg, -1, 1), sr_out)
    print(f'game audio: clicks {c0 / sr:.3f}s and {c1 / sr:.3f}s ({rate:.1f} samples per second), {n / fps:.3f}s -> {out}')


def sheet(a):
    fs = sorted(glob.glob(os.path.join(a.out, 'f*.jpg')) or glob.glob(os.path.join(a.out, 'f*.png')))[::a.every]
    ims = [Image.open(f).convert('RGB') for f in fs]
    w = a.w; h = int(ims[0].height * w / ims[0].width); cols = a.cols
    S = Image.new('RGB', (cols * w, ((len(ims) + cols - 1) // cols) * (h + 16)), (17, 17, 17))
    from PIL import ImageDraw
    d = ImageDraw.Draw(S)
    for i, (f, im) in enumerate(zip(fs, ims)):
        x, y = (i % cols) * w, (i // cols) * (h + 16)
        S.paste(im.resize((w, h)), (x, y + 16)); d.text((x + 4, y + 2), os.path.basename(f), fill=(255, 225, 77))
    out = a.sheet or os.path.join(a.out, 'sheet.jpg'); S.save(out, quality=88); print(out)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    t = sp.add_parser('trim'); t.add_argument('capture'); t.add_argument('out'); t.add_argument('--len', type=int, default=0)
    t.add_argument('--aspect', default='4:3'); t.add_argument('--w', type=int, default=1440); t.add_argument('--q', type=int, default=95)
    s = sp.add_parser('sheet'); s.add_argument('out'); s.add_argument('--every', type=int, default=30); s.add_argument('--w', type=int, default=320)
    s.add_argument('--cols', type=int, default=6); s.add_argument('--sheet', default='')
    a = ap.parse_args()
    trim(a) if a.cmd == 'trim' else sheet(a)
