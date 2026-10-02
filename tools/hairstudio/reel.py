"""A multi-shot mocap reel on the rig (Michael, 2026-10-02: "a more complex mocap test on the hairstyle rig after the
curtsy ... multiple shots, across the data we used for hello_world and tsuzuku"). Each shot is one canonical clip
(projects/clawd3d/refs/mocap: tsuzuku's Seedance dances, GEM-X), put on the rig by mocap.py, with its own camera: an
azimuth (panned across the shot, eased), a framing (wide: the whole figure; medium: thighs up; close: head and
shoulders, following the hips' smoothed travel), 1280x720. Shots render in parallel processes; the reel is their frames
in order (hard cuts), with each shot's numbers (mocap.measure) beside it on the page.

    python reel.py BUILD GROOM [--jobs 3] [--only NAME,...]      -> clips/reel/{reel.mp4, index.html, SHOT.measure.json}
"""
import json, os, sys, time, subprocess
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MOCAP = os.path.join(ROOT, 'projects', 'clawd3d', 'refs', 'mocap')
OUT = os.path.join(HERE, 'clips', 'reel')
W, H = 1280, 720

# (tsuzuku's song order: a verse, the chorus's travelling bounce and claw side-step, the claw-dance hook, chorus 2,
# the finale, the bow)
REEL = [
    dict(name='verse', clip='v2a_v1', what='verse 2: the sway', az=(15, 25), frame='wide'),
    dict(name='bounce', clip='c1a_v2', what='chorus 1: the bouncing, travelling dance', az=(40, 20), frame='wide'),
    dict(name='sidestep', clip='c1s_v1', what='chorus: the claw side-step', az=(0, 0), frame='medium'),
    dict(name='hook', clip='hook_v1', what='the claw-dance hook (snip-snip)', az=(10, 30), frame='medium'),
    dict(name='chorus2', clip='c2b_v1', what='chorus 2, from behind: the long hair', az=(160, 200), frame='wide'),
    dict(name='finale_travel', clip='f2_v1', what='finale: the travelling phrase', az=(30, 30), frame='wide'),
    dict(name='finale_turn', clip='f3_v1', what='finale: the turn, close on the hair', az=(200, 150), frame='close'),
    dict(name='bow', clip='curtsy_v1', what='the curtsy (first 16 frames trimmed, turned to camera)', az=(20, 10),
         frame='wide', trim=16, face=True),
]
FRAMING = dict(wide=(0.74, 0.80), medium=(1.02, 0.50), close=(1.20, 0.36))     # (centre height, half height: m)


def ease(u):
    u = np.clip(u, 0, 1)
    return u * u * u * (u * (6 * u - 15) + 10)


def shot(build, groom, S, ss=2):
    os.environ.setdefault('CLIP_STYLED', '1'); os.environ.setdefault('CLIP_GRAV_LONG', '0.12')
    os.environ.setdefault('CLIP_RIGID_BANGS', '1'); os.environ.setdefault('CLIP_STIFF_LONG', '40,12')
    os.environ.setdefault('CLIP_K', '12'); os.environ.setdefault('CLIP_HEAD_COLLIDE', '1')
    import mocap
    import clip as C
    from charkit import rom, bundle as bl, palette, qa3d
    from charkit.detailqa import _Window
    from PIL import Image, ImageDraw
    from scipy.ndimage import gaussian_filter1d
    t0 = time.time()
    rig, _ = rom.load(build)
    B = bl.load(groom); palette.activate_spec(B.spec)
    clip = {k: v for k, v in np.load(os.path.join(MOCAP, S['clip'] + '.clip.npz'), allow_pickle=False).items()}
    trim, face = S.get('trim', 0), S.get('face', False)
    frames = mocap.retarget(rig, clip, trim, face)
    fps = float(clip['fps']); nf = len(frames)
    A = np.load(os.path.join(groom, 'arrays.npz')); M = json.load(open(os.path.join(groom, 'bundle.json')))
    hr = C.build_rig(A, M); C.collider(A, M); C.radial_collider(A, M)
    caps, rad = mocap.arm_capsules(rig, frames) if mocap.ARMS else (None, None)
    sim = mocap.simulate_head(C, hr, [f['head'] for f in frames], [f.get('upperChest', f.get('chest')) for f in frames],
                              fps, caps, rad)
    meas = mocap.measure(rig, frames, sim, clip, trim, fps)
    meas.update(name=S['name'], clip=S['clip'], what=S['what'], frame=S['frame'], az=list(S['az']))
    base = []
    for o in B.objects():
        if o.group not in ('hair', 'skin', 'eye', 'mouth', 'garment', 'accessory'):
            continue
        variant = 'masked' if o.group == 'skin' and o.has('masked') else 'eval'
        if o.has(variant):
            for s_ in qa3d.surfaces(B, o, variant):
                Jw, Ww, _ = mocap.transfer_weights(rig, o.name, o.group, s_['V'])
                base.append((o.name, s_, s_['V'].copy(), Jw, Ww))
    hips = np.array([f_['hips'][:3, :3] @ rig.sk.head['hips'] + f_['hips'][:3, 3] for f_ in frames])
    follow = gaussian_filter1d(hips[:, :2], 12, axis=0, mode='nearest')
    zc, hz = FRAMING[S['frame']]
    if S['frame'] == 'wide':
        follow[:] = hips[:, :2].mean(0)                       # (wide: a locked-off camera)
    pix = 2 * hz / (H * ss)
    fdir = os.path.join(OUT, S['name'])
    os.makedirs(fdir, exist_ok=True)
    for x in os.listdir(fdir):
        if x.endswith('.png'):
            os.remove(os.path.join(fdir, x))
    for f in range(nf):
        Rm, tm = rig.matrices(frames[f])
        D = sim[f]
        surfs = []
        for nm, s_, V0, Jw, Ww in base:
            Vd = V0.copy()
            po = hr['per_obj'].get(nm)
            if po is not None and len(V0) == len(po['vchain']):
                vc, sv = po['vchain'], po['sv']; m = vc >= 0
                u = sv[m] * (C.K - 1); i0 = np.clip(np.floor(u).astype(int), 0, C.K - 2); fr = (u - i0)[:, None]
                Vd[m] = V0[m] + (1 - fr) * D[vc[m], i0] + fr * D[vc[m], i0 + 1]
            surfs.append(dict(s_, V=mocap.lbs(Vd, Jw, Ww, Rm, tm)))
        az = S['az'][0] + (S['az'][1] - S['az'][0]) * ease(f / max(nf - 1, 1))
        c = np.array([follow[f, 0], follow[f, 1], zc])
        win = _Window(c, az, pix * W * ss / 2, pix * H * ss / 2, pix)
        img = qa3d.draw(B, surfs, az, win, transparent=False, ss=ss)
        im = Image.fromarray((np.clip(img[..., :3], 0, 1) * 255).astype(np.uint8))
        if im.size != (W, H):
            im = im.resize((W, H))
        ImageDraw.Draw(im).text((14, H - 22), '%s  ·  %s' % (S['clip'], S['what']), fill=(70, 70, 76))
        im.save(os.path.join(fdir, '%04d.png' % f))
    meas['seconds'] = round(time.time() - t0, 1)
    json.dump(meas, open(os.path.join(OUT, S['name'] + '.measure.json'), 'w'), indent=1)
    print(json.dumps(dict(shot=S['name'], frames=nf, seconds=meas['seconds'])), flush=True)


def assemble(shots):
    lst = os.path.join(OUT, 'frames.txt')
    with open(lst, 'w') as fh:
        for S in shots:
            fd = os.path.join(OUT, S['name'])
            for x in sorted(p for p in os.listdir(fd) if p.endswith('.png')):
                fh.write("file '%s'\nduration %.6f\n" % (os.path.join(fd, x), 1 / 24.0))
    mp4 = os.path.join(OUT, 'reel.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-r', '24',
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', mp4], check=True)
    for S in shots:                                        # (a strip per shot: 5 frames)
        from PIL import Image
        fd = os.path.join(OUT, S['name'])
        fs = sorted(p for p in os.listdir(fd) if p.endswith('.png'))
        ims = [Image.open(os.path.join(fd, fs[round(i * (len(fs) - 1) / 4)])).resize((384, 216)) for i in range(5)]
        st = Image.new('RGB', (384 * 5, 216), 'white')
        for i, im in enumerate(ims):
            st.paste(im, (384 * i, 0))
        st.save(os.path.join(OUT, S['name'] + '_strip.jpg'), quality=86)
    return mp4


def page(shots):
    rows = []
    t = 0.0
    for i, S in enumerate(shots):
        m = json.load(open(os.path.join(OUT, S['name'] + '.measure.json')))
        f = m['feet']; dur = m['frames'] / m['fps']
        rows.append('<tr><td>%d</td><td><b>%s</b><br><span class="mute">%s · %s, az %s&rarr;%s · %.1f&ndash;%.1f s</span>'
                    '<br><img src="%s_strip.jpg"></td><td>%.2f%%</td><td>%.1f</td><td>%s / %s</td><td>%.0f / %.0f</td>'
                    '<td class="%s">%.1f cm, %d fr</td><td>%.2f&ndash;%.2f</td></tr>' % (
                        i + 1, S['what'], S['clip'], S['frame'], S['az'][0], S['az'][1], t, t + dur, S['name'],
                        100 * m['hair']['hf_share'], m['hair']['tip_offset_max_cm'],
                        f['leftFoot']['mean_mm'], f['rightFoot']['mean_mm'],
                        f['leftFoot']['foot_shin_deg_max'], f['rightFoot']['foot_shin_deg_max'],
                        'warn' if m['hands_to_hair']['frames_under_3cm'] else '', m['hands_to_hair']['min_cm'],
                        m['hands_to_hair']['frames_under_3cm'], m['hips_z']['min'], m['hips_z']['max']))
        t += dur
    html = """<!doctype html><html><head><meta charset="utf-8"><title>Mocap Reel</title><style>
:root{--bg:#f4f4f6;--fg:#1d1d22;--card:#fff;--line:#dadae0;--mute:#62626c;--warn:#b5482a}
@media (prefers-color-scheme:dark){:root{--bg:#141417;--fg:#ececf0;--card:#202024;--line:#38383f;--mute:#a0a0aa;--warn:#f08a68}}
body{background:var(--bg);color:var(--fg);font:15px/1.45 -apple-system,system-ui,sans-serif;margin:0;padding:16px}
h1{font-size:20px;margin:0 0 4px}.lead{color:var(--mute);max-width:1100px;margin:0 0 12px}
video{width:100%;max-width:1280px;border-radius:8px;background:#000;display:block}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;margin-top:14px;overflow-x:auto}
table{border-collapse:collapse;font-size:13px;width:100%}th,td{border-top:1px solid var(--line);padding:6px;text-align:left;vertical-align:top}
th{color:var(--mute);font-weight:500}.mute{color:var(--mute)}td img{width:100%;max-width:640px;margin-top:4px;border-radius:4px}
.warn{color:var(--warn);font-weight:600}
</style></head><body><h1>Mocap reel on the rig: I4 hair, tsuzuku's dances</h1>
<p class="lead">Eight shots, hard cuts, in the song's order, with the raw captures' own timing (no music: tsuzuku warped
these onto the song, and the raw clips aren't). Each shot is a GEM-X capture from tsuzuku's Seedance dance clips, put
on Clawd's rig by mocap.py. The hair is I4's spring chains, driven by the head, with a body proxy on the chest. Not
simulated: the skirt (it's skinned to the legs) and the arms as hair colliders. The hands-to-hair column flags
frames where a hand comes within 3 cm of a hair chain: likely passes through the hair.</p>
<video src="reel.mp4" controls autoplay loop muted playsinline></video>
<div class="card"><table><tr><th>#</th><th>shot</th><th>hair buzz &gt;6 Hz</th><th>tip swing cm</th>
<th>foot slide L/R mm/f</th><th>foot/shin max deg L/R</th><th>hands to hair</th><th>hips z m</th></tr>""" + ''.join(rows) + \
        "</table></div><p class='mute'><a href='reel.mp4'>reel.mp4</a> · per-shot frames and numbers in this folder</p></body></html>"
    open(os.path.join(OUT, 'index.html'), 'w').write(html)
    return os.path.join(OUT, 'index.html')


if __name__ == '__main__':
    a = sys.argv[1:]
    opt = lambda k, d: a[a.index(k) + 1] if k in a else d
    if a[0] == 'shot':                                     # (one shot, a worker process)
        shot(a[1], a[2], next(S for S in REEL if S['name'] == a[3]))
        sys.exit(0)
    build, groom = a[0], a[1]
    os.makedirs(OUT, exist_ok=True)
    only = opt('--only', None)
    todo = [S for S in REEL if not only or S['name'] in only.split(',')]
    jobs = int(opt('--jobs', 3))
    procs, queue = [], list(todo)
    while queue or procs:
        while queue and len(procs) < jobs:
            S = queue.pop(0)
            log = open(os.path.join(OUT, S['name'] + '.log'), 'w')
            procs.append((S, subprocess.Popen([sys.executable, os.path.abspath(__file__), 'shot', build, groom, S['name']],
                                              stdout=log, stderr=subprocess.STDOUT)))
        time.sleep(2)
        for S, p in list(procs):
            if p.poll() is not None:
                procs.remove((S, p))
                print(S['name'], 'rc', p.returncode, flush=True)
    print(assemble(REEL)); print(page(REEL))
