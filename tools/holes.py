"""Frame-by-frame hole finder for rig tests rendered on pure magenta (LOOPS.<name>mag): any magenta region NOT connected to
the frame border is background showing through the character. Prints the frames with holes, their size and centroid.

    .venv/bin/python tools/holes.py FRAMES_DIR [--min 12]
"""
import os, sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

d = sys.argv[1]; mn = int(sys.argv[sys.argv.index('--min') + 1]) if '--min' in sys.argv else 12
def holes_of(path):
    a = np.array(Image.open(path).convert('RGB')).astype(int)
    mag = (a[:, :, 0] > 200) & (a[:, :, 1] < 70) & (a[:, :, 2] > 200)
    lab, n = ndi.label(mag); edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
    return [(int(s), c) for i, (s, c) in enumerate(zip(ndi.sum(mag, lab, range(1, n + 1)), ndi.center_of_mass(mag, lab, range(1, n + 1))), 1) if i not in edge and s >= mn]
fs = sorted(f for f in os.listdir(d) if f.endswith(('.jpg', '.png')))
# gaps drawn into the art (e.g. between curls) are background at rest too: holes near one in the first frame, of similar size,
# are the design, not the rig
rest = holes_of(os.path.join(d, fs[0])); R = float(sys.argv[sys.argv.index('--track') + 1]) if '--track' in sys.argv else 70
art = lambda s, c: any(abs(c[0] - r[1][0]) < R and abs(c[1] - r[1][1]) < R and .25 < s / r[0] < 4 for r in rest)
bad = 0
for f in fs:
    holes = [(s, c) for s, c in holes_of(os.path.join(d, f)) if not art(s, c)]
    if holes:
        bad += 1; print(f, ' '.join(f'{s}px@({c[1]:.0f},{c[0]:.0f})' for s, c in sorted(holes, reverse=True)[:6]))
print(f'{bad} frames with holes')
