#!/usr/bin/env python3
"""boards.py: export fighters to glTF (datkit export), render them in Blender (render_cast.py) and lay out reference boards.

  python boards.py [--out ~/games/melee/work/art/spec] [--steps export,render,compose] [--only Mr,Fx]
                   [--extra NAME=path/to/model.gltf:scale]      # add your own model (e.g. a Blender export of Geno) to
                                                                 # the lineup and view sheets, for side-by-side checks

Needs OUT/summary.json from measure.sh (ModelScale and head joints). Everything written under OUT is derived from game
data: keep it out of git.

Boards (OUT/boards/):
  lineup_front.png     the requested cast (and Geno's current model) front-on at in-game scale, 5-unit grid
  lineup_side.png      the same in profile
  lineup_rest.png      the rest of the cast, front-on
  views_XX.png         front / 3/4 / side / back at one shared scale, plain and with a triangle-wire overlay
  head_XX.png          head close-ups: nearest-texel filtering (texel density) and triangle wire (edge flow)
  lod_pairs.png        high model vs the low model (the off-screen bubble / Fountain of Dreams reflection model)
  atlas_XX.png         every texture of the costume at 1:1 (2x under 64 px), with format and size, and the texture-
                       animation frames (eyes, mouths)
"""
import json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
DK = os.path.join(HERE, '..', 'datkit', 'dk')
BLENDER = os.environ.get('BLENDER', '/opt/homebrew/bin/blender')
DISC = os.environ.get('DISC', os.path.expanduser('~/games/melee/disc/files'))
FONT = os.path.expanduser('~/animation-pipeline/engine/fonts/Archivo.ttf')
MONO = '/System/Library/Fonts/Menlo.ttc'

CORE = ['Mr', 'Lg', 'Dr', 'Ns', 'Pc', 'Cl', 'Lk', 'Ms', 'Fe', 'Fx', 'Fc', 'Sk', 'Ca']
BOARD8 = ['Mr', 'Ms', 'Fx', 'Lk', 'Sk', 'Ns', 'Ca', 'Fe']
REST = ['Pk', 'Kb', 'Pr', 'Pp', 'Ys', 'Pe', 'Zd', 'Ss', 'Mt', 'Gw', 'Gn', 'Dk', 'Kp']
BG = (236, 236, 240, 255); INK = (30, 30, 38, 255); MUTE = (120, 120, 132, 255); GRID = (205, 205, 214, 255)


def arg(k, d=None):
    return sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d


OUT = os.path.expanduser(arg('--out', '~/games/melee/work/art/spec'))
STEPS = arg('--steps', 'export,render,compose').split(',')
S = json.load(open(os.path.join(OUT, 'summary.json')))
G = os.path.join(OUT, 'gltf'); RD = os.path.join(OUT, 'renders'); BD = os.path.join(OUT, 'boards')
for d in (G, RD, BD): os.makedirs(d, exist_ok=True)
ONLY = arg('--only'); ONLY = ONLY.split(',') if ONLY else None
EXTRA = {}
for e in [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == '--extra']:
    name, rest = e.split('=', 1); path, _, sc = rest.partition(':'); EXTRA[name] = (os.path.abspath(path), float(sc or 1))


def font(sz, mono=False):
    try: return ImageFont.truetype(MONO if mono else FONT, sz)
    except Exception: return ImageFont.load_default()


def export():
    codes = [c for c in CORE + REST + ['Ge'] if os.path.exists(f'{DISC}/Pl{c}Nr.dat')]
    for c in codes:
        if ONLY and c not in ONLY: continue
        subprocess.run([DK, 'export', f'{DISC}/Pl{c}Nr.dat', f'{G}/{c}/{c}.gltf', '--ft', f'{DISC}/Pl{c}.dat', '--lod', 'high'], check=True)
        if c in BOARD8:
            subprocess.run([DK, 'export', f'{DISC}/Pl{c}Nr.dat', f'{G}/{c}_low/{c}_low.gltf', '--ft', f'{DISC}/Pl{c}.dat', '--lod', 'low'], check=True)


def fighters():
    F = []
    for c, f in S.items():
        g = f'{G}/{c}/{c}.gltf'
        if os.path.exists(g):
            F.append({'code': c, 'gltf': g, 'scale': f['scale'] or 1.0, 'head': f['head_joints']})
        g = f'{G}/{c}_low/{c}_low.gltf'
        if os.path.exists(g):
            F.append({'code': c + '_low', 'gltf': g, 'scale': f['scale'] or 1.0, 'head': f['head_joints']})
    for name, (path, sc) in EXTRA.items():
        F.append({'code': name, 'gltf': path, 'scale': sc, 'head': []})
    return F


def render():
    b8 = [c for c in BOARD8 if not ONLY or c in ONLY]
    ext = list(EXTRA)
    core_row = [c for c in CORE if c in S] + (['Ge'] if 'Ge' in S else []) + ext
    job = {'out': RD, 'size': [900, 900], 'fighters': fighters(), 'renders': [], 'meta': 'render_meta_only.json' if ONLY else 'render_meta.json'}
    if not ONLY:
        half = (len(core_row) + 1) // 2
        job['renders'] += [
            {'kind': 'lineup', 'name': 'lineup_front', 'rows': [core_row[:half], core_row[half:]], 'w': 3200, 'aspect': 0.19, 'gap': 1.5},
            {'kind': 'lineup', 'name': 'lineup_side', 'rows': [core_row[:half], core_row[half:]], 'yaw': 90, 'w': 3200, 'aspect': 0.19, 'gap': 3},
            {'kind': 'lineup', 'name': 'lineup_rest', 'rows': [REST[:7], REST[7:]], 'w': 3200, 'aspect': 0.24, 'gap': 1.5},
            {'kind': 'views', 'name': 'lod', 'codes': [c + s for c in ('Mr', 'Fx', 'Ms', 'Lk') for s in ('', '_low')], 'views': ['front', 'q34'],
             'size': [700, 700], 'common': True, 'wire': True, 'thick': 0.0012},
        ]
    job['renders'] += [
        {'kind': 'views', 'name': 'views', 'codes': b8 + ext, 'measure': BOARD8 + ext, 'size': [800, 800], 'common': True},
        {'kind': 'views', 'name': 'wire', 'codes': b8 + ext, 'views': ['front', 'q34', 'side'], 'size': [1400, 1400], 'wire': True, 'thick': 0.0009, 'pad': 1.04},
        {'kind': 'head', 'name': 'headtex', 'codes': b8, 'views': ['front', 'q34', 'side'], 'size': [900, 900], 'closest': True, 'pad': 1.15},
        {'kind': 'head', 'name': 'headwire', 'codes': b8, 'views': ['front', 'q34', 'side'], 'size': [900, 900], 'wire': True, 'thick': 0.0014, 'pad': 1.15},
    ]
    jp = os.path.join(RD, 'job.json'); json.dump(job, open(jp, 'w'), indent=1)
    r = subprocess.run([BLENDER, '-b', '--python', os.path.join(HERE, 'render_cast.py'), '--', jp], capture_output=True, text=True)
    if r.returncode or 'Traceback' in r.stdout + r.stderr:
        print((r.stdout + r.stderr)[-4000:]); sys.exit(1)


def label(img, xy, text, sz=22, fill=INK, mono=False, anchor='la'):
    ImageDraw.Draw(img).text(xy, text, font=font(sz, mono), fill=fill, anchor=anchor)


def load(p):
    return Image.open(p).convert('RGBA') if os.path.exists(p) else None


def compose_lineups():
    meta = json.load(open(os.path.join(RD, 'render_meta.json')))
    for name, title in (('lineup_front', 'Cast at in-game scale (ftData ModelScale applied), front, rest pose'),
                        ('lineup_side', 'Cast at in-game scale, profile'), ('lineup_rest', 'Rest of the cast at in-game scale')):
        rows = sorted(k for k in meta if k.startswith(name + '_'))
        if not rows: continue
        ims = [load(os.path.join(RD, k + '.png')) for k in rows]
        top = 70; lab = 50; W = ims[0].width + 90
        Hh = top + sum(i.height + lab for i in ims) + 20
        out = Image.new('RGBA', (W, Hh), BG); d = ImageDraw.Draw(out)
        label(out, (30, 22), title, 30)
        y = top
        for k, im in zip(rows, ims):
            m = meta[k]; ppu = m['ppu']; floor = y + m['floor_px']
            for u in range(0, 60, 5):   # 5-unit grid
                yy = floor - u * ppu
                if yy < y: break
                d.line([(70, yy), (W - 10, yy)], fill=GRID if u else MUTE, width=1 if u else 2)
                label(out, (60, yy), f'{u}', 16, MUTE, True, 'rm')
            out.alpha_composite(im, (80, y))
            for code, x0, x1, h, lz in m['placed']:
                cx = 80 + m['x0_px'] + (x0 + x1) / 2 * ppu
                nm = S[code]['name'] if code in S else code
                label(out, (cx, floor + 8), nm, 18, INK, False, 'ma')
                label(out, (cx, floor + 30), f'{h:.1f} u', 15, MUTE, True, 'ma')
            y += im.height + lab
        out.convert('RGB').save(os.path.join(BD, name + '.png'))


def fmt_tris(c):
    f = S.get(c)
    return f"{f['tris_high']} tris high / {f['tris_low']} low, {f['verts_high']} verts, {f['joints']} joints" if f else 'external model'


def compose_views():
    for c in [x for x in BOARD8 + list(EXTRA) if not ONLY or x in ONLY or x in EXTRA]:
        vs = ['front', 'q34', 'side', 'back']
        a = [load(os.path.join(RD, f'views_{c}_{v}.png')) for v in vs]
        if not a[0]: continue
        cw = 700; top = 110
        out = Image.new('RGBA', (cw * 4 + 40, top + cw + 20), BG)
        label(out, (24, 20), f"{S[c]['name'] if c in S else c}  ({c})", 32)
        label(out, (24, 60), fmt_tris(c) + '   |   every views_ board shares one scale (in-game units)', 18, MUTE)
        for i, v in enumerate(vs):
            if a[i] is not None: out.alpha_composite(a[i].resize((cw, cw), Image.LANCZOS), (20 + i * cw, top))
            label(out, (20 + i * cw + cw // 2, top - 16), {'front': 'front', 'q34': '3/4', 'side': 'side', 'back': 'back'}[v], 20, MUTE, False, 'ma')
        out.convert('RGB').save(os.path.join(BD, f'views_{c}.png'))
        b = [load(os.path.join(RD, f'wire_{c}_{v}.png')) for v in vs[:3]]
        if not b[0]: continue
        cw = 1000
        out = Image.new('RGBA', (cw * 3 + 40, top + cw + 20), BG)
        label(out, (24, 20), f"{S[c]['name'] if c in S else c}: triangles", 32)
        label(out, (24, 60), fmt_tris(c) + '   |   every triangle edge of the high model (strips/fans triangulated), framed to fit', 18, MUTE)
        for i in range(3):
            if b[i] is not None: out.alpha_composite(b[i].resize((cw, cw), Image.LANCZOS), (20 + i * cw, top))
        out.convert('RGB').save(os.path.join(BD, f'wire_{c}.png'))


def compose_heads():
    meta = json.load(open(os.path.join(RD, 'render_meta.json')))
    for c in [x for x in BOARD8 if not ONLY or x in ONLY]:
        vs = ['front', 'q34', 'side']
        a = [load(os.path.join(RD, f'headtex_{c}_{v}.png')) for v in vs]
        b = [load(os.path.join(RD, f'headwire_{c}_{v}.png')) for v in vs]
        if not a[0]: continue
        cw = 700; top = 96
        out = Image.new('RGBA', (cw * 3 + 40, top + cw * 2 + 60), BG)
        f = S[c]
        label(out, (24, 18), f"{f['name']}: head", 32)
        label(out, (24, 58), f"head {f['regions']['head']} tris ({100 * f['regions']['head'] / f['tris_high']:.0f}% of high model); "
                              f"face texel density {f['density_head']:.0f} texels/model-unit = {f['texels_per_height_head']:.0f} texels per body height; "
                              f"top row nearest-texel filtered", 17, MUTE)
        for i in range(3):
            for row, src in enumerate((a, b)):
                if src[i] is None: continue
                out.alpha_composite(src[i].resize((cw, cw), Image.LANCZOS), (20 + i * cw, top + row * (cw + 20)))
        out.convert('RGB').save(os.path.join(BD, f'head_{c}.png'))


def compose_lod():
    codes = ['Mr', 'Fx', 'Ms', 'Lk']
    if not load(os.path.join(RD, 'lod_Mr_front.png')): return
    cw = 420; top = 80
    out = Image.new('RGBA', (cw * 4 + 40, top + len(codes) * (cw + 40) + 20), BG)
    label(out, (24, 20), 'High model vs low model (off-screen magnifier bubble; Fountain of Dreams reflections)', 28)
    for r, c in enumerate(codes):
        for i, (suf, v) in enumerate([('', 'front'), ('', 'q34'), ('_low', 'front'), ('_low', 'q34')]):
            im = load(os.path.join(RD, f'lod_{c}{suf}_{v}.png'))
            if im: out.alpha_composite(im.resize((cw, cw), Image.LANCZOS), (20 + i * cw, top + r * (cw + 40)))
        f = S[c]
        label(out, (20 + cw, top + r * (cw + 40) + cw + 4), f"{f['name']}: high {f['tris_high']} tris", 18, INK, False, 'ma')
        label(out, (20 + 3 * cw, top + r * (cw + 40) + cw + 4), f"low {f['tris_low']} tris", 18, INK, False, 'ma')
    out.convert('RGB').save(os.path.join(BD, 'lod_pairs.png'))


def compose_atlas():
    for c in [x for x in BOARD8 + ['Lg', 'Dr', 'Fc', 'Cl', 'Pc'] if not ONLY or x in ONLY]:
        st = json.load(open(os.path.join(OUT, 'stats', c + '.json')))
        td = os.path.join(OUT, 'tex', c)
        seen = {}
        for o in st['dobjs']:
            for t in o['mat']['tex']:
                if t['key'] and t['key'] not in seen: seen[t['key']] = (t, o['lod'])
        items = sorted(seen.values(), key=lambda x: (-x[0]['w'] * x[0]['h'], x[0]['key']))
        W = 1800; pad = 14; x = pad; y = 110; rowh = 0; places = []
        for t, lod in items:
            s = 2 if max(t['w'], t['h']) < 64 else 1
            w, h = t['w'] * s, t['h'] * s
            if x + w > W - pad: x = pad; y += rowh + 46; rowh = 0
            places.append((t, lod, x, y, s)); x += max(w, 150) + pad; rowh = max(rowh, h)
        y += rowh + 60
        tas = st.get('texanims', [])
        ta_y = y; ta_rows = []
        for ta in tas:
            files = ta.get('files') or []
            ta_rows.append((ta, files))
        H = y + 60 + sum(200 for _ in ta_rows) + 20
        out = Image.new('RGBA', (W, max(H, y + 40)), BG); d = ImageDraw.Draw(out)
        f = S[c]
        label(out, (pad, 16), f"{f['name']}: costume textures ({f['tex_count']} textures, {f['tex_bytes'] / 1024:.0f} KiB"
                              f" + {f['texanim_bytes'] / 1024:.0f} KiB texture animation)", 30)
        label(out, (pad, 58), '1:1 texels (2x when under 64 px); checker = transparent; label: size, format, coordinate/colour op, model', 17, MUTE)
        for t, lod, px, py, s in places:
            p = os.path.join(td, f"tex_{t['key']}.png")
            im = load(p)
            if im is None: continue
            if s != 1: im = im.resize((im.width * s, im.height * s), Image.NEAREST)
            ck = Image.new('RGBA', im.size, (255, 255, 255, 255)); cd = ImageDraw.Draw(ck)
            for yy in range(0, im.height, 8):
                for xx in range(0, im.width, 8):
                    if (xx // 8 + yy // 8) % 2: cd.rectangle([xx, yy, xx + 7, yy + 7], fill=(210, 210, 210, 255))
            ck.alpha_composite(im); out.alpha_composite(ck, (px, py))
            fm = t['fmt'] + (f"/{t['tlut'].split('x')[0].replace('GX_TL_', '')}" if t['tlut'] else '')
            label(out, (px, py + im.height + 3), f"{t['w']}x{t['h']} {fm}", 14, INK, True)
            label(out, (px, py + im.height + 20), f"{t['coord']} {t['colormap']} {lod}", 12, MUTE, True)
        # texture animations: every frame
        yy = ta_y
        if ta_rows:
            label(out, (pad, yy), 'Texture animations (material animation swaps the image; frames in order)', 22); yy += 36
        for ta, files in ta_rows:
            xx = pad
            label(out, (pad, yy), f"DObj {ta['dobj']}: {ta['images']} frames, {', '.join(ta['sizes'])}", 14, MUTE, True)
            for fn in files:
                im = load(os.path.join(td, fn))
                if im is None: continue
                sc = 150 / max(im.width, im.height)
                im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.NEAREST)
                if xx + im.width > W - pad: break
                out.alpha_composite(im, (xx, yy + 20)); xx += im.width + 8
            yy += 200
        out = out.crop((0, 0, W, min(out.height, yy + 20)))
        out.convert('RGB').save(os.path.join(BD, f'atlas_{c}.png'))


if 'export' in STEPS: export()
if 'render' in STEPS: render()
if 'compose' in STEPS:
    if not ONLY: compose_lineups(); compose_lod()
    compose_views(); compose_heads(); compose_atlas()
print('boards in', BD)
