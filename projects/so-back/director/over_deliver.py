"""Lane 2: deliver shots from one director capture as edit-ready plates (the format src/edit.js loads), straight from the raw
dump: slate-trimmed and count-checked (plates.py), the portrait view squeezed to 1080x1920 (vplate.py --mode aspect, one
resample), and the game audio cut sample-locked to the plates (plates.py's click sync), then split per shot.
    .venv/bin/python projects/so-back/director/over_deliver.py CAPTURE --len N SHOTS.json
SHOTS.json: [{"name": "over_star", "s0": 30, "s1": 270, "events": [[s, "label"], ...], "notes": "..."}, ...] in script frames.
Per shot, optionally: "mode": "crop" (a 4:3 capture: a 9:16 slice), "cx": 0.55 (the slice's centre, as a fraction of the width),
"v43": true (also write the full 4:3 frame at 1440x1080 into ../v43/, for screen-space text such as the GAME! splash).
--no-end: the capture has no end slate (a scene change ended the script, e.g. a stock match going to its results); frames
are counted from the opening slate and the audio is cut at the dump's nominal rate.
Writes ~/games/melee/plates/soback_<name>/v/{f00001.jpg..., audio.wav, info.json}; info.json events are in plate seconds
(frame 1 = 0.0)."""
import argparse, glob, json, os, sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np, soundfile as sf
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'machinima'))
from plates import is_slate, game_audio
from vplate import vplate


def one(job):
    src, dst, mode, cx, d43 = job
    im = Image.open(src).convert('RGB')
    if mode == 'crop' and cx != .5:                    # a 9:16 slice of the 4:3 display, off centre
        w = im.size[0]; dh = round(w * 3 / 4); im = im.resize((w, dh), Image.LANCZOS)
        cw = round(dh * 9 / 16); x0 = min(max(0, round(cx * w - cw / 2)), w - cw)
        im.crop((x0, 0, x0 + cw, dh)).resize((1080, 1920), Image.LANCZOS).save(dst, quality=95)
    else:
        vplate(im, mode).save(dst, quality=95)
    if d43:
        w = im.size[0]; im.resize((1440, 1080), Image.LANCZOS).save(os.path.join(d43, os.path.basename(dst)), quality=95)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('capture'); ap.add_argument('shots'); ap.add_argument('--len', type=int, required=True)
    ap.add_argument('--mode', default='aspect'); ap.add_argument('--workers', type=int, default=4); ap.add_argument('--no-end', action='store_true')
    a = ap.parse_args()
    fs = sorted(glob.glob(os.path.join(a.capture, 'f*.png')))
    slate = [is_slate(f) for f in fs]
    runs, i = [], 0
    while i < len(fs):
        if slate[i]:
            j = i
            while j + 1 < len(fs) and slate[j + 1]: j += 1
            runs.append((i, j)); i = j + 1
        else: i += 1
    first = runs[0][1] + 1
    if a.no_end:
        n = min(a.len, len(fs) - first)
        print(f'{len(fs)} captured; opening slate {runs[0]}; no end slate; using {n} frames')
    else:
        last = runs[1][0]; n = last - first
        print(f'{len(fs)} captured; slates {runs[:2]}; {n} script frames')
        if n != a.len: sys.exit(f'refused: {n} frames between the slates, the script has {a.len}')
    tmp = os.path.join(a.capture, '_game.wav')
    game_audio(os.path.join(a.capture, 'dsp.wav'), tmp, n, runs[0][1] - runs[0][0] + 1)
    au, sr = sf.read(tmp, always_2d=True)
    for sh in json.load(open(a.shots)):
        out = os.path.expanduser(f"~/games/melee/plates/soback_{sh['name']}/v"); os.makedirs(out, exist_ok=True)
        for f in glob.glob(os.path.join(out, 'f*.jpg')): os.remove(f)
        s0, s1 = sh['s0'], sh['s1']; mode = sh.get('mode', a.mode)
        d43 = os.path.join(os.path.dirname(out), 'v43') if sh.get('v43') else None
        if d43: os.makedirs(d43, exist_ok=True)
        jobs = [(fs[first + s], os.path.join(out, f'f{k + 1:05d}.jpg'), mode, sh.get('cx', .5), d43) for k, s in enumerate(range(s0, s1))]
        with ProcessPoolExecutor(a.workers) as ex: list(ex.map(one, jobs, chunksize=4))
        sf.write(os.path.join(out, 'audio.wav'), au[int(round(s0 / 60 * sr)):int(round(s1 / 60 * sr))], sr)
        info = {'n': s1 - s0, 'fps': 60, 'pre': 0.0, 'keyed': False, 'w': 1080, 'h': 1920, 'mode': mode,
                'v43': '../v43 (1440x1080, same numbering)' if d43 else None,
                'source': {'capture': os.path.abspath(a.capture), 'script_frames': [s0, s1]},
                'events': [{'t': round((s - s0) / 60, 4), 'frame': s - s0 + 1, 'label': lab} for s, lab in sh.get('events', [])],
                'notes': sh.get('notes', '')}
        json.dump(info, open(os.path.join(out, 'info.json'), 'w'), indent=1)
        print(f"{sh['name']}: {s1 - s0} frames -> {out}")
    os.remove(tmp)
