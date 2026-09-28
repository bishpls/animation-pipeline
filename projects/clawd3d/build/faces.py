"""Clawd's face decals for the 3D head, cut from TSUZUKU's 2D rig so the 3D face is the drawn face (no redraw).
Composes the rig's registered layers (eyes + brows, and the mouth) into square RGBA textures over one face window of the
base drawing: out/tex/eyes_<state>.png (open, half, closed, happy) and out/tex/mouth_<shape>.png (rest + the rig's visemes).
The window is written to out/tex/window.json so the head build maps the decals with the same numbers.
    ~/animation-pipeline/.venv/bin/python projects/clawd3d/build/faces.py
"""
import json, os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
RIG = os.path.expanduser('~/animation-pipeline/projects/tsuzuku/rig/clawd/build')
OUT = os.path.join(PROJ, 'out', 'tex')
WIN = (848, 400, 440)          # x, y, size in base-drawing px: brows to below the mouth, centred between the eyes
SIZE = 1024


def layer(name, var=None):
    man = json.load(open(os.path.join(RIG, 'manifest.json')))['layers']
    if var:
        v = json.load(open(os.path.join(RIG, 'variants.json')))[name][var]
        return Image.open(os.path.join(RIG, v['file'])).convert('RGBA'), (v['x'], v['y'])
    L = next(l for l in man if l['name'] == name)
    return Image.open(os.path.join(RIG, f'{name}.png')).convert('RGBA'), (L['x'], L['y'])


def compose(parts):
    x0, y0, s = WIN
    canvas = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    for im, (x, y) in parts:
        canvas.alpha_composite(im, (x - x0, y - y0))
    return canvas.resize((SIZE, SIZE), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    bl, (bx, by) = layer('brow_L')
    cut = 440 - by                  # brow_L's cell also holds a bang strand above the brow (the bangs are 3D here)
    brows = [(bl.crop((0, cut, bl.width, bl.height)), (bx, by + cut)), layer('brow_R')]
    for state in ('open', 'half', 'closed', 'happy'):
        v = None if state == 'open' else state
        compose([layer('eye_L', v), layer('eye_R', v)] + brows).save(os.path.join(OUT, f'eyes_{state}.png'))
    mouths = ['rest'] + list(json.load(open(os.path.join(RIG, 'variants.json')))['mouth'].keys())
    for m in mouths:
        compose([layer('mouth', None if m == 'rest' else m)]).save(os.path.join(OUT, f'mouth_{m}.png'))
    json.dump({'window': WIN, 'size': SIZE, 'eyes': ['open', 'half', 'closed', 'happy'], 'mouths': mouths},
              open(os.path.join(OUT, 'window.json'), 'w'), indent=1)
    print('eyes: 4, mouths:', len(mouths), '->', OUT)


if __name__ == '__main__':
    main()
