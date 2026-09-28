"""Review boards for the Clawd build: the front orthographic render over the 2D base drawing (ref | 3D | 50% overlay), and a
turnaround sheet with a face close-up. Reads clawd.py --views output.
    ~/animation-pipeline/.venv/bin/python projects/clawd3d/build/preview.py projects/clawd3d/out/views [OUTDIR]
"""
import os, sys
from PIL import Image

REF = os.path.expanduser('~/animation-pipeline/projects/tsuzuku/rig/clawd/base.png')


def main(views, out):
    ref = Image.open(REF).convert('RGBA').resize((540, 960))
    bg = Image.new('RGBA', ref.size, (255, 255, 255, 255)); bg.alpha_composite(ref); ref = bg
    fo = Image.open(os.path.join(views, 'front_ortho.png')).convert('RGBA').resize((540, 960))
    row = Image.new('RGB', (1620, 960), 'white')
    row.paste(ref.convert('RGB'), (0, 0)); row.paste(fo.convert('RGB'), (540, 0)); row.paste(Image.blend(ref, fo, 0.5).convert('RGB'), (1080, 0))
    row.save(os.path.join(out, 'overlay.png'))
    tiles = []
    for f in ('front', 'three_q', 'side', 'back', 'three_q_back'):
        im = Image.open(os.path.join(views, f + '.png')).convert('RGB')
        w, h = im.size
        tiles.append(im.crop((int(w * 0.3), 0, int(w * 0.7), h)).resize((int(0.4 * w * 540 / h), 540)))
    face = Image.open(os.path.join(views, 'face.png')).convert('RGB')
    face = face.resize((int(face.width * 540 / face.height), 540))
    sheet = Image.new('RGB', (sum(t.width for t in tiles) + face.width, 540), 'white')
    x = 0
    for t in tiles + [face]:
        sheet.paste(t, (x, 0)); x += t.width
    sheet.save(os.path.join(out, 'turnaround.png'))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else sys.argv[1])
