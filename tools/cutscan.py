"""Cut detection for reference films: per-frame differences at low resolution, cuts as local spikes over an adaptive
threshold, fades as runs of near-black frames. Reference videos and their outputs stay outside git.

    python cutscan.py scan VIDEO OUT.json [--fps F] [--k 3.0] [--floor 18] [--minlen 4]
    python cutscan.py thumbs VIDEO CUTS.json OUT_DIR [--w 240]      # one thumbnail per shot (its middle frame)
    python cutscan.py strip VIDEO OUT.png --t0 S --t1 S [--every N] [--w 160]   # every Nth frame of a moment, to check cuts by eye

scan writes {fps, n, dur, cuts: [{f, t, score}], black: [[f0, f1]], diff: [...]} where diff is the per-frame score
(mean absolute luma difference plus a histogram term) for charts.
"""
import json, subprocess, sys, os
import numpy as np

W, H = 96, 72


def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                          'stream=r_frame_rate,nb_frames:format=duration', '-of', 'json', path],
                         capture_output=True, text=True).stdout
    j = json.loads(out)
    num, den = j['streams'][0]['r_frame_rate'].split('/')
    return float(num) / float(den), float(j['format']['duration'])


def frames(path):
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'scale={W}:{H}:flags=area', '-f', 'rawvideo',
                          '-pix_fmt', 'gray', '-'], stdout=subprocess.PIPE)
    sz = W * H
    while True:
        b = p.stdout.read(sz)
        if len(b) < sz:
            break
        yield np.frombuffer(b, np.uint8).reshape(H, W).astype(np.float32)


def scan(path, k=3.0, floor=18.0, minlen=4):
    fps, dur = probe(path)
    diffs, lum, prev, ph = [], [], None, None
    for fr in frames(path):
        h = np.histogram(fr, bins=32, range=(0, 256))[0].astype(np.float32)
        h /= h.sum()
        lum.append(float(fr.mean()))
        if prev is None:
            diffs.append(0.0)
        else:
            d = float(np.abs(fr - prev).mean())
            hd = float(np.abs(h - ph).sum()) * 50.0          # 0..100: a histogram swing
            diffs.append(0.5 * d + 0.5 * hd)
        prev, ph = fr, h
    d = np.array(diffs); n = len(d)
    cuts = []
    last = -minlen
    for i in range(1, n):
        a, b = max(0, i - 15), min(n, i + 16)
        win = np.concatenate([d[a:i], d[i + 1:b]])
        med = float(np.median(win)) if len(win) else 0.0
        mad = float(np.median(np.abs(win - med))) if len(win) else 0.0
        thr = max(floor, med + k * max(mad, 1.0) * 3.0)
        if d[i] > thr and d[i] >= d[max(0, i - 1)] and d[i] >= d[min(n - 1, i + 1)] and i - last >= minlen:
            # a flash (one bright frame) returns to the previous frame: skip it
            cuts.append({'f': i, 't': round(i / fps, 4), 'score': round(float(d[i]), 2)})
            last = i
    lum = np.array(lum)
    black, run = [], None
    for i, v in enumerate(lum):
        if v < 10:
            run = run if run is not None else i
        elif run is not None:
            if i - run >= 3: black.append([run, i - 1])
            run = None
    if run is not None and n - run >= 3: black.append([run, n - 1])
    return dict(video=os.path.basename(path), fps=fps, n=n, dur=round(n / fps, 3), cuts=cuts, black=black,
                diff=[round(float(x), 2) for x in d], lum=[round(float(x), 1) for x in lum])


def clean(cj, min_s=0.15):
    """Merge every shot shorter than min_s into the one before it (a flash, a stepped strobe or a whip through clouds
    reads as several 4-frame 'shots'; checked on strips of the Special Movie). Keeps the raw cuts as raw_cuts."""
    c = json.load(open(cj))
    raw = c.get('raw_cuts', c['cuts'])
    m = int(round(min_s * c['fps']))
    keep, prev = [], 0
    for x in raw:
        if x['f'] - prev >= m:
            keep.append(x)
            prev = x['f']
        # else: the shot starting at prev is too short so far; drop this cut and let the shot run on
    if keep and c['n'] - keep[-1]['f'] < m:
        keep.pop()
    c['raw_cuts'] = raw; c['cuts'] = keep; c['min_shot_s'] = min_s
    json.dump(c, open(cj, 'w'))
    return len(raw), len(keep)


def thumbs(path, cj, od, w=240):
    os.makedirs(od, exist_ok=True)
    c = json.load(open(cj)); fps = c['fps']
    bounds = [0] + [x['f'] for x in c['cuts']] + [c['n']]
    mids = [(bounds[i] + bounds[i + 1]) // 2 for i in range(len(bounds) - 1)]
    for i, m in enumerate(mids):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{m / fps:.4f}', '-i', path, '-frames:v', '1', '-vf',
                        f'scale={w}:-2', os.path.join(od, f's{i:04d}.jpg')])
    json.dump(dict(mids=mids, bounds=bounds), open(os.path.join(od, 'shots.json'), 'w'))


def strip(path, out, t0, t1, every=1, w=160):
    """Every Nth frame of a moment, each labelled with its frame number (no drawtext in this ffmpeg: PIL labels)."""
    from PIL import Image, ImageDraw
    fps, _ = probe(path)
    p = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t0}', '-t', f'{t1 - t0}', '-i', path, '-vf',
                        f"select='not(mod(n,{every}))',scale={w}:-2", '-fps_mode', 'passthrough', '-f', 'rawvideo',
                        '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
    probe_h = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                              '-of', 'csv=p=0', path], capture_output=True, text=True).stdout.strip().split(',')
    h = int(round(w * int(probe_h[1]) / int(probe_h[0]) / 2) * 2)
    n = len(p) // (w * h * 3)
    cols = 10; rows = (n + cols - 1) // cols
    img = Image.new('RGB', (cols * w, rows * (h + 14)), (0, 0, 0)); d = ImageDraw.Draw(img)
    f0 = int(round(t0 * fps))
    for i in range(n):
        fr = Image.frombytes('RGB', (w, h), p[i * w * h * 3:(i + 1) * w * h * 3])
        x, y = (i % cols) * w, (i // cols) * (h + 14)
        img.paste(fr, (x, y)); d.text((x + 2, y + h), f'f{f0 + i * every}', fill=(255, 255, 255))
    img.save(out)


if __name__ == '__main__':
    a = sys.argv[1:]
    opt = lambda key, d=None: a[a.index(key) + 1] if key in a else d
    if a[0] == 'scan':
        r = scan(a[1], float(opt('--k', 3.0)), float(opt('--floor', 18)), int(opt('--minlen', 4)))
        json.dump(r, open(a[2], 'w'))
        print(r['video'], 'fps', round(r['fps'], 3), 'frames', r['n'], 'cuts', len(r['cuts']), 'black runs', len(r['black']))
    elif a[0] == 'clean':
        print(a[1], 'cuts raw -> kept', clean(a[1], float(opt('--min', 0.15))))
    elif a[0] == 'thumbs':
        thumbs(a[1], a[2], a[3], int(opt('--w', 240)))
    elif a[0] == 'strip':
        strip(a[1], a[2], float(opt('--t0')), float(opt('--t1')), int(opt('--every', 1)), int(opt('--w', 160)))
