"""A contact sheet of a tracked motion-reference clip (every Nth frame of the skeleton overlay, labelled with frame and time) plus
a plot of the wrists' heights and the hip's, to judge a generation (warped limbs, drift) and to read its event onsets for the
structural warp (tools/retarget_mocap.py --anchors).
    .venv/bin/python tools/mocap_sheet.py BASE OUT_DIR [--every 3]      (BASE: refs/mocap/<name>, with BASE_pose.json and BASE_pose_overlay.mp4)
"""
import json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt

a = sys.argv[1:]; base, out = a[0], a[1]; every = int(a[a.index('--every') + 1]) if '--every' in a else 3
os.makedirs(out, exist_ok=True); name = os.path.basename(base)
J = json.load(open(base + '_pose.json')); fps = J['fps']; n = len(J['frames'])
d = tempfile.mkdtemp(); subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', base + '_pose_overlay.mp4', '-vf', 'scale=180:320', f'{d}/f%04d.jpg'], check=True)
fr = sorted(os.listdir(d))[::every]; cols = 11
S = Image.new('RGB', (180 * cols, 340 * ((len(fr) + cols - 1) // cols)), 'white'); g = ImageDraw.Draw(S)
for i, f in enumerate(fr):
    k = i * every; S.paste(Image.open(f'{d}/{f}'), ((i % cols) * 180, (i // cols) * 340 + 18)); g.text(((i % cols) * 180 + 3, (i // cols) * 340 + 3), f'{k}  {k / fps:.2f}s', fill='black')
S.save(os.path.join(out, name + '_sheet.jpg'), quality=85)
img = np.array([[p[1] for p in f['img']] for f in J['frames']]); vis = np.array([[p[3] for p in f['img']] for f in J['frames']])
t = np.arange(n) / fps
fig, ax = plt.subplots(figsize=(11, 3))
for i, lab, c in [(16, 'right wrist (image-left)', '#2a78d6'), (15, 'left wrist (image-right)', '#eb6834'), (0, 'nose', '#8a8980')]: ax.plot(t, -img[:, i], color=c, lw=1.5, label=lab)
ax.plot(t, -(img[:, 23] + img[:, 24]) / 2 * 1 - .0, color='#1baf7a', lw=1.5, label='hip mid')
ax.set_xlabel('source s'); ax.set_ylabel('height (-y, normalised)'); ax.legend(frameon=False, fontsize=7, ncol=4); ax.grid(True, color='#ecebe4')
ax.set_title(f'{name}: min visibility {vis[:, [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]].min():.2f}', loc='left', fontsize=9)
fig.tight_layout(); fig.savefig(os.path.join(out, name + '_tracks.png'), dpi=110); print('wrote', out, name)
