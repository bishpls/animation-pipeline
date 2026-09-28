"""Lane 2: the roster strobe plate. Captures each group twice (stage hidden; clear colour black, then grey 96) at res 4 with the
solved per-character cameras (ROSTER_CAM=film), then keys every character's 30-frame window with the difference matte into ONE
plate: ~/games/melee/plates/soback_roster/v/ (f*.jpg = the black pass, premultiplied colour; m*.png = LA matte), with
info.json's index {char: {first, n, window}} (first = the plate frame, 1-based) and audio.wav (each window's game audio).
    .venv/bin/python projects/so-back/director/over_roster_deliver.py capture [--groups 0,1,...]   # 2 passes per group
    .venv/bin/python projects/so-back/director/over_roster_deliver.py build                        # the plate + sheet"""
import glob, json, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np, soundfile as sf
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'machinima'))
from plates import is_slate, game_audio
from vplate import vplate
from dmatte import matte
CH = ['doc', 'mario', 'luigi', 'bowser', 'peach', 'yoshi', 'dk', 'falcon', 'ganon', 'falco', 'fox', 'ness', 'ics', 'kirby',
      'samus', 'zelda', 'sheik', 'link', 'ylink', 'pichu', 'pikachu', 'puff', 'mewtwo', 'gnw', 'marth', 'roy']
LEAD, SHOT = 20, 150
PL = os.path.expanduser('~/games/melee/plates')
PASSES = {'black': '0,0,0', 'grey': '96,96,96'}


def cap(g, p): return f'{PL}/soback_roster_cap{g}_{p}'


def capture(groups):
    for g in groups:
        for p, bg in PASSES.items():
            if os.path.exists(os.path.join(cap(g, p), 'run.json')): print('have', cap(g, p)); continue
            subprocess.run([os.path.join(ROOT, '.venv/bin/python'), os.path.join(HERE, 'over_run.py'), 'over_roster', '--res', '4',
                            '--out', cap(g, p), '--env', f'ROSTER_RUN={g}', 'ROSTER_CAM=film', f'SOBACK_BG={bg}'], check=True, cwd=ROOT)
            print('captured', cap(g, p))


def trimmed(d, n_script):
    fs = sorted(glob.glob(os.path.join(d, 'f*.png')))
    sl = [is_slate(f) for f in fs]
    runs, i = [], 0
    while i < len(fs):
        if sl[i]:
            j = i
            while j + 1 < len(fs) and sl[j + 1]: j += 1
            runs.append((i, j)); i = j + 1
        else: i += 1
    first, last = runs[0][1] + 1, runs[1][0]
    if last - first != n_script: sys.exit(f'{d}: {last - first} frames between the slates, the script has {n_script}')
    return fs, first, runs[0][1] - runs[0][0] + 1


def despeck(pb, a, small=600, far=150):
    """Final Destination's background star sparkles survive the stage hide and key as specks. Drop matte islands smaller than
    `small` px that lie more than `far` px from the fighter (the largest island); big separate pieces (Doc's tossed pill) and
    anything near the fighter (cheek sparks) stay."""
    from scipy import ndimage
    m = a > .03; lab, n = ndimage.label(m)
    if n < 2: return pb, a
    sizes = ndimage.sum(m, lab, range(1, n + 1)); objs = ndimage.find_objects(lab); big = int(np.argmax(sizes)); by, bx = objs[big]
    drop = np.zeros(n + 1, bool)
    for k, (sy, sx) in enumerate(objs):
        if k == big or sizes[k] >= small: continue
        gap = max(by.start - sy.stop, sy.start - by.stop, bx.start - sx.stop, sx.start - bx.stop)
        drop[k + 1] = gap > far
    kill = ndimage.binary_dilation(drop[lab], iterations=3)                 # the glow halo around each speck too
    a = np.where(kill, 0, a); pb = np.where(kill[..., None], 0, pb)
    return pb, a


def key_one(job):
    fb, fg, k, out = job
    b, g = (vplate(Image.open(p).convert('RGB'), 'aspect') for p in (fb, fg))
    pb, a = matte(np.asarray(b), np.asarray(g))
    pb, a = despeck(pb, a)
    Image.fromarray(pb.astype(np.uint8)).save(f'{out}/f{k:05d}.jpg', quality=95)
    Image.fromarray(np.dstack([np.full(a.shape, 255, np.uint8), (a * 255 + .5).astype(np.uint8)]), 'LA').save(f'{out}/m{k:05d}.png', compress_level=3)


def build():
    WIN = json.load(open(os.path.join(HERE, 'roster_windows.json'))); CAM = json.load(open(os.path.join(HERE, 'roster_cam.json')))
    out = f'{PL}/soback_roster/v'; os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, '*.jpg')) + glob.glob(os.path.join(out, '*.png')): os.remove(f)
    jobs, index, audio, k = [], {}, [], 1
    for g in range(7):
        grp = CH[g * 4:g * 4 + 4]; n_script = LEAD + SHOT * len(grp)
        fb, b0, slate = trimmed(cap(g, 'black'), n_script); fgr, g0, _ = trimmed(cap(g, 'grey'), n_script)
        tmp = os.path.join(cap(g, 'black'), '_game.wav'); game_audio(os.path.join(cap(g, 'black'), 'dsp.wav'), tmp, n_script, slate)
        au, sr = sf.read(tmp, always_2d=True)
        for i, c in enumerate(grp):
            w0, w1 = WIN[c]; s0 = LEAD + i * SHOT
            index[c] = {'first': k, 'n': w1 - w0, 'window': [w0, w1], 'script_frames': [s0 + w0, s0 + w1], 'group': g,
                        'camera': CAM[c]}
            for s in range(s0 + w0, s0 + w1):
                jobs.append((fb[b0 + s], fgr[g0 + s], k, out)); k += 1
            audio.append(au[int(round((s0 + w0) / 60 * sr)):int(round((s0 + w1) / 60 * sr))])
        os.remove(tmp)
    with ProcessPoolExecutor(6) as ex: list(ex.map(key_one, jobs, chunksize=4))
    sf.write(os.path.join(out, 'audio.wav'), np.concatenate(audio), 48000)
    json.dump({'n': k - 1, 'fps': 60, 'pre': 0.0, 'keyed': True, 'w': 1080, 'h': 1920, 'index': index, 'order': CH,
               'notes': ("The roster strobe for CHOOSE YOUR CHARACTER!: all 26 characters (Zelda and Sheik separately), each 30 frames "
                         "(0.5 s) of its own taunt, keyed by the two-pass difference matte (composite: out = f + (1 - m.alpha) * BG). "
                         "Framed on the median pose to 70% of the frame height, centred; wide poses (Bowser, DK, the Ice Climbers, G&W...) "
                         "fill the frame width instead (46-66% tall), an arm or tail may touch an edge. FD star specks removed from the matte. "
                         "3/4 front camera (yaw 28, pitch 4), portrait projection (aspect 0.5625), res 4. "
                         "Characters face right. audio.wav: each window's game audio (taunt voices and sounds), back to back.")},
              open(os.path.join(out, 'info.json'), 'w'), indent=1)
    print(f'{k - 1} frames -> {out}')


def sheet():
    out = f'{PL}/soback_roster/v'; info = json.load(open(f'{out}/info.json'))
    cols, w, h = 9, 180, 320; hot = [(255, 46, 154), (200, 255, 46), (46, 230, 255), (122, 46, 255)]
    S = Image.new('RGB', (cols * w, 3 * (h + 18)), (17, 17, 17)); d = ImageDraw.Draw(S)
    for i, c in enumerate(info['order']):
        e = info['index'][c]; k = e['first'] + e['n'] // 2
        f = np.asarray(Image.open(f'{out}/f{k:05d}.jpg').convert('RGB')).astype(np.float32)
        a = np.asarray(Image.open(f'{out}/m{k:05d}.png'))[..., 1].astype(np.float32)[..., None] / 255
        bg = np.array(hot[i % 4], np.float32)
        im = Image.fromarray(np.clip(f + (1 - a) * bg, 0, 255).astype(np.uint8)).resize((w, h))
        x, y = (i % cols) * w, (i // cols) * (h + 18)
        S.paste(im, (x, y + 18)); d.text((x + 3, y + 3), f"{c} f{k}", fill=(255, 225, 77))
    S.save(os.path.join(ROOT, 'projects/so-back/board/over/roster.jpg'), quality=90); print('sheet')


if __name__ == '__main__':
    if sys.argv[1] == 'capture':
        gs = [int(x) for x in sys.argv[sys.argv.index('--groups') + 1].split(',')] if '--groups' in sys.argv else range(7)
        capture(gs)
    elif sys.argv[1] == 'build': build(); sheet()
    elif sys.argv[1] == 'sheet': sheet()
