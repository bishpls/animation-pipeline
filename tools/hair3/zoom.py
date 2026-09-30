"""zoom.py LABS.npz VIEW ROW COL [HALF] [OUT]: the lock labels round a point, each lock its own tone, lock outlines
black, the names of the locks in the window printed."""
import sys, numpy as np
from PIL import Image
Z = np.load(sys.argv[1])
v, r, c = sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
h = int(sys.argv[5]) if len(sys.argv) > 5 else 40
out = sys.argv[6] if len(sys.argv) > 6 else '/tmp/zoom.png'
lab = Z[v].astype(int)
locks = list(Z['locks'])
w = lab[max(0, r - h):r + h, max(0, c - h):c + h]
rng = np.random.default_rng(3)
n = int(lab.max()) + 1
pal = (rng.uniform(0.35, 0.95, (n + 1, 3)) * np.array([255, 190, 150])).astype(np.uint8)
img = np.where((w > 0)[..., None], pal[np.clip(w, 0, None)], np.where((w == 0)[..., None], 70, 246)).astype(np.uint8)
edge = np.zeros(w.shape, bool)
edge[:-1] |= w[:-1] != w[1:]; edge[:, :-1] |= w[:, :-1] != w[:, 1:]
img[edge] = 0
Image.fromarray(img).resize((img.shape[1] * 6, img.shape[0] * 6), Image.NEAREST).save(out)
ids, cnt = np.unique(w[w > 0], return_counts=True)
print({locks[i - 1] if i - 1 < len(locks) else i: int(k) for i, k in zip(ids, cnt)})
