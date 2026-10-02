"""the curtsy review page: both clips side by side with their numbers, and a key-frame strip per clip."""
import json, os
from PIL import Image
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'clips')
CLIPS = [('curtsy_studio_I4', 'Studio mocap curtsy', 'BONES-SEED curtsy_R (a 175 cm performer), 30 fps, 5.2 s. '
          'The take starts in the dip, left leg crossed behind, and rises. Motion Data by Bones Studio (bones.studio).'),
         ('curtsy_video_I4', 'Video-capture curtsy', 'GEM-X from curtsy_v1.mp4, 24 fps. The first 16 frames are '
          'dropped (a ~220 deg spin while the capture settles), and the clip is turned so its median heading faces '
          'the camera.')]


def strip(tag, n=6):
    fd = os.path.join(D, tag + '_frames')
    fs = sorted(x for x in os.listdir(fd) if x.endswith('.png'))
    pick = [fs[round(i * (len(fs) - 1) / (n - 1))] for i in range(n)]
    ims = [Image.open(os.path.join(fd, p)) for p in pick]
    w, h = ims[0].size
    half = [im.crop((0, 0, w // 2, h)) for im in ims]               # (the front view of each)
    out = Image.new('RGB', (len(half) * w // 2, h), 'white')
    for i, im in enumerate(half):
        out.paste(im, (i * w // 2, 0))
    out.thumbnail((1800, 600))
    out.save(os.path.join(D, tag + '_strip.jpg'), quality=88)


def fmt(m):
    f = m['feet']
    return ('<table><tr><td>hair buzz (tip power above 6 Hz)</td><td>%.2f%% mean, %.2f%% worst chain</td></tr>'
            '<tr><td>hair tip swing (in the head frame)</td><td>max %.1f cm, p95 speed %.2f m/s</td></tr>'
            '<tr><td>foot slide while planted</td><td>L %s mm/frame (p95 %s), R %s mm/frame (p95 %s)</td></tr>'
            '<tr><td>hands to the hair chains</td><td>closest %.1f cm, %d frames under 3 cm</td></tr>'
            '<tr><td>hips height</td><td>%.3f to %.3f m (rest 0.670)</td></tr></table>') % (
        100 * m['hair']['hf_share'], 100 * m['hair']['hf_share_max'], m['hair']['tip_offset_max_cm'],
        m['hair']['tip_speed_p95'], f['leftFoot']['mean_mm'], f['leftFoot']['p95_mm'], f['rightFoot']['mean_mm'],
        f['rightFoot']['p95_mm'], m['hands_to_hair']['min_cm'], m['hands_to_hair']['frames_under_3cm'],
        m['hips_z']['min'], m['hips_z']['max'])


cards = []
for tag, title, note in CLIPS:
    strip(tag)
    m = json.load(open(os.path.join(D, tag + '.measure.json')))
    cards.append('<section><h2>%s</h2><p class="note">%s</p><video src="%s.mp4" autoplay loop muted playsinline controls>'
                 '</video>%s<img src="%s_strip.jpg" alt="key frames"><p class="files"><a href="%s.mp4">%s.mp4</a> · '
                 '<a href="%s.measure.json">numbers</a> · <a href="%s_frames/">frames</a></p></section>'
                 % (title, note, tag, fmt(m), tag, tag, tag, tag, tag))
page = """<!doctype html><html><head><meta charset="utf-8"><title>Curtsy On Rig</title><style>
:root{--bg:#f4f4f6;--fg:#1d1d22;--card:#fff;--line:#dadae0;--mute:#62626c}
@media (prefers-color-scheme:dark){:root{--bg:#141417;--fg:#ececf0;--card:#202024;--line:#38383f;--mute:#a0a0aa}}
body{background:var(--bg);color:var(--fg);font:15px/1.45 -apple-system,system-ui,sans-serif;margin:0;padding:16px}
h1{font-size:20px;margin:0 0 4px} .lead{color:var(--mute);margin:0 0 14px;max-width:1100px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}
h2{font-size:17px;margin:0 0 4px} .note{color:var(--mute);font-size:13px;margin:0 0 8px}
video,img{width:100%;border-radius:6px;background:#eeeef2} table{border-collapse:collapse;margin:8px 0;font-size:13px;width:100%}
td{border-top:1px solid var(--line);padding:4px 6px;vertical-align:top} td:first-child{color:var(--mute);width:46%}
.files{font-size:13px} a{color:#c0562e}
@media (max-width:900px){.grid{grid-template-columns:1fr}}
</style></head><body><h1>Curtsy on the rig: I4 hair, first mocap test</h1>
<p class="lead">The body is the hi2_hull build's export skin. Its weights are carried onto the bundle meshes, and SOMA-77
joints are retargeted to the VRM humanoid by the clawd3d method. The hair is I4: rigid on the head, plus its spring
chains simulated against the head's full motion, a body proxy that rides the chest, and the head mesh. Not simulated:
the skirt (it's skinned to the legs, with no cloth) and the arms as hair colliders. Two views: 20&deg; and 200&deg;.</p>
<div class="grid">""" + ''.join(cards) + "</div></body></html>"
open(os.path.join(D, 'curtsy.html'), 'w').write(page)
print(os.path.join(D, 'curtsy.html'))
