"""Lane-3 runner for the drop montage (never built itself). Builds a director script on lane 3's disc and captures it.
    .venv/bin/python projects/so-back/director/drop_run.py lab NAME [--env K=V ...] [--res 1]      # -> ~/games/melee/work/soback/labs/NAME
    .venv/bin/python projects/so-back/director/drop_run.py key NAME [--env K=V ...] [--res 4]      # two passes -> plates soback_NAME/v
The key mode builds and captures the script twice (SOBACK_STAGE=0, SOBACK_BG=0,0,0 then 96,96,96), trims both between the slates,
checks the counts, and writes the delivery format (f*.jpg black pass, m*.png LA matte, audio.wav, info.json)."""
import argparse, glob, json, os, re, subprocess, sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(PROJ))
KIT = os.path.join(PROJ, 'machinima')
PY = os.path.join(ROOT, '.venv', 'bin', 'python')
LANE = dict(MELEE_DISC=os.path.expanduser('~/games/melee/disc-soback-L3'), DOLPHIN_USER=os.path.expanduser('~/games/melee/dolphin-soback-L3'))
sys.path.insert(0, KIT); sys.path.insert(0, PROJ)


def build_run(name, env, out, res, timeout=1800):
    e = dict(os.environ, **LANE, **env)
    r = subprocess.run([PY, os.path.join(KIT, 'melee', 'build.py'), PROJ, name], env=e, cwd=ROOT, capture_output=True, text=True)
    if r.returncode: sys.exit(r.stdout[-3000:] + r.stderr[-3000:])
    print(r.stdout.strip().splitlines()[-1], flush=True)
    r = subprocess.run([PY, os.path.join(KIT, 'dolphin.py'), 'run', os.path.join(LANE['MELEE_DISC'], 'sys', 'main.dol'), out,
                        '--until', 'DIRECTOR END', '--res', str(res), '--timeout', str(timeout), '--quiet'], env=e, cwd=ROOT,
                       capture_output=True, text=True)
    if r.returncode: sys.exit(r.stdout[-3000:] + r.stderr[-3000:])
    print(r.stdout.strip().splitlines()[-1][:200], flush=True)


def magenta_frac(path):
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(path).convert('RGB').resize((64, 64), Image.NEAREST)).astype(int)
    return (np.abs(a - [255, 0, 255]).max(-1) < 40).mean()


def between_slates(cap, n=None):
    """The script frames between the director's slates. A slate hides the stage on magenta, but the fighters stay drawn,
    so a close camera can put a fighter in a corner: a slate is a frame that is mostly magenta. With n (the script length)
    the frame right after the n script frames must be the end slate, or the capture dropped or doubled frames."""
    fs = sorted(glob.glob(os.path.join(cap, 'f*.png')))
    m = [magenta_frac(f) > .5 for f in fs]
    i = m.index(True); j = i
    while m[j + 1]: j += 1
    first = j + 1
    if n is None:
        k = first
        while k < len(fs) and not m[k]: k += 1
        n = k - first
    assert first + n < len(fs) and m[first + n] and not m[first + n - 1], f'{cap}: no end slate right after {n} script frames'
    return fs[first:first + n], j - i + 1


def write_info(plate_name, cap, meta, notes=''):
    """info.json from a capture's game log: fighter hits (HIT), item hits such as lasers (IHIT, no attacker logged) and laser
    spawns (LASER). Plate frame k (1-based) = script frame k-1; plate time t = (k-1)/60."""
    hits, lasers = [], []
    for l in open(os.path.join(cap, 'osreport.log')).read().splitlines():
        m = re.match(r'HIT (\d+) (\d+) (\d+) ([\d.]+) (\d+)', l)
        if m:
            s = int(m.group(1)); hits.append(dict(frame=s + 1, t=round(s / 60, 4), attacker=int(m.group(2)), victim=int(m.group(3)),
                                                   dmg=float(m.group(4)), move=int(m.group(5))))
        m = re.match(r'IHIT (\d+) (\d+) ([\d.]+)', l)
        if m:
            s = int(m.group(1)); hits.append(dict(frame=s + 1, t=round(s / 60, 4), attacker=None, victim=int(m.group(2)),
                                                   dmg=float(m.group(3)), move='item (laser)'))
        m = re.match(r'LASER (\d+) (\d+) (\S+) (\S+)', l)
        if m:
            s = int(m.group(1)); lasers.append(dict(frame=s + 1, t=round(s / 60, 4), port=int(m.group(2)), x=float(m.group(3)), y=float(m.group(4))))
    hits.sort(key=lambda h: h['frame'])
    out = os.path.expanduser(f'~/games/melee/plates/soback_{plate_name}/v')
    info = dict(n=meta['len'], fps=60, pre=0, keyed=True, chars=meta.get('chars'), hits=hits, lasers=lasers, labels=meta.get('labels'),
                notes=('plate frame k (1-based) = script frame k-1; plate time t = (k-1)/60. ' + notes).strip())
    json.dump(info, open(os.path.join(out, 'info.json'), 'w'), indent=1)
    return info


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('mode'); ap.add_argument('name'); ap.add_argument('--env', nargs='*', default=[])
    ap.add_argument('--res', type=int); ap.add_argument('--tag', default='')
    a = ap.parse_args()
    env = dict(e.split('=', 1) for e in a.env)
    if a.mode == 'lab':
        build_run(a.name, env, os.path.expanduser(f'~/games/melee/work/soback/labs/{a.name}{a.tag}'), a.res or 1)
        sys.exit(0)
    res = a.res or 4
    plate = os.path.expanduser(f'~/games/melee/plates/soback_{a.name}{a.tag}')
    caps = {}
    for tag, bg in (('black', '0,0,0'), ('grey', '96,96,96')):
        caps[tag] = os.path.join(plate, 'raw_' + tag)
        build_run(a.name, dict(env, SOBACK_STAGE='0', SOBACK_BG=bg), caps[tag], res)
    meta = json.load(open(os.path.join(HERE, 'build', a.name + '.json')))
    n = meta['len']
    fb, slate = between_slates(caps['black'], n); fg, _ = between_slates(caps['grey'], n)
    assert len(fb) == len(fg) == n, f'frame counts: black {len(fb)} grey {len(fg)} script {n}'
    out = os.path.join(plate, 'v'); os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, '*')): os.remove(f)
    from prep_plates import one
    jobs = [(i + 1, out, 'aspect', None, b, g) for i, (b, g) in enumerate(zip(fb, fg))]
    with ProcessPoolExecutor(6) as ex: list(ex.map(one, jobs, chunksize=4))
    from plates import game_audio
    game_audio(os.path.join(caps['black'], 'dsp.wav'), os.path.join(out, 'audio.wav'), n, slate)
    info = write_info(a.name + a.tag, caps['black'], meta)
    print(f'{n} frames -> {out}; hits {[(h["frame"], h["dmg"]) for h in info["hits"]]}')
