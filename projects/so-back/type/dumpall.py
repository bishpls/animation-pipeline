"""Dump every model's textures from Melee files (datkit mdump) and contact-sheet them, to find the game's own text.
    .venv/bin/python projects/so-back/type/dumpall.py FILE... [--out DIR]
Game-derived images: written under ~/games/melee/work/soback/type/dump/<file>/<model>/ (never in the repo)."""
import os, re, subprocess, sys
from PIL import Image, ImageDraw
W = os.path.expanduser('~/games/melee/work/soback/type'); DK = os.path.join(W, 'dk')
DISC = os.path.expanduser('~/games/melee/disc-soback/files')

def models(f):
    r = subprocess.run([DK, 'mscan', os.path.join(DISC, f)], capture_output=True, text=True).stdout
    return [m.group(1) for m in re.finditer(r'^== (\S+): (\d+) joints', r, re.M) if int(m.group(2)) > 0]

def dump(f, out):
    for m in models(f):
        d = os.path.join(out, f, m.replace(':', '_').replace('#', '_'))
        os.makedirs(d, exist_ok=True)
        log = subprocess.run([DK, 'mdump', os.path.join(DISC, f), m, d], capture_output=True, text=True)
        open(os.path.join(d, 'dump.txt'), 'w').write(log.stdout + log.stderr)

def sheet(f, out):
    base = os.path.join(out, f); ims = []
    for root, _, fs in sorted(os.walk(base)):
        for x in sorted(fs):
            if x.endswith('.png'): ims.append(os.path.join(root, x))
    if not ims: return
    cell, cols = 200, 10; rows = (len(ims) + cols - 1) // cols
    S = Image.new('RGB', (cols * cell, rows * (cell + 14)), (40, 40, 60)); d = ImageDraw.Draw(S)
    for i, p in enumerate(ims):
        im = Image.open(p).convert('RGBA'); im.thumbnail((cell - 4, cell - 4))
        bg = Image.new('RGBA', im.size, (90, 30, 90, 255)); bg.alpha_composite(im)
        x, y = (i % cols) * cell, (i // cols) * (cell + 14)
        S.paste(bg.convert('RGB'), (x + 2, y + 14))
        d.text((x + 2, y), os.path.relpath(p, base).replace('/', ' ')[:34], fill=(255, 230, 80))
    S.save(os.path.join(out, f + '_sheet.jpg'), quality=85)
    print(f, len(ims), 'textures')

if __name__ == '__main__':
    a = sys.argv[1:]; out = os.path.join(W, 'dump')
    for f in a: dump(f, out); sheet(f, out)
