"""Melee's own type from its disc, assembled for the engine (engine/meleetype.js): the game's word graphics, its menu font
(SIS), the HUD digits and tags, and the character name textures.
    .venv/bin/python tools/machinima/melee/type/dumpall.py IfAll.usd GmGover.dat GmRegClr.dat IfComSn.usd GmPause.usd GmRst.usd
    .venv/bin/python tools/machinima/melee/type/sisfont.py
    .venv/bin/python tools/machinima/melee/type/build_type.py [--dump ~/games/melee/type/dump] [--out ~/games/melee/type]
Reads dumpall.py's datkit dumps and sisfont.py's atlas, and writes (game-derived: never in the repo) OUT/: words/*.png,
swatches/*.png, hud/*.png, names/{banner,label}/*.png, sis/atlas_hi.png, and manifest.js (window.MTYPE: every image's
size and role, the font's metrics, the word styles). First used by SO BACK (projects/so-back/type/ wraps it)."""
import json, os
import numpy as np
from PIL import Image, ImageFilter
D = OUT = None                                       # the dump folder and the output folder: set by main()
ld = lambda p: Image.open(os.path.join(D, p)).convert('RGBA')

# ---- 1. the word graphics (textures on quads in the game: IfAll.usd's ScInfCnt scene models; GmGover's letters)
WORDS = {                                            # name: (file, the game's exact text)
    'time': ('IfAll.usd/ScInfCnt_scene_models_0/j1_d0_t0.png', 'Time!'),
    'sudden': ('IfAll.usd/ScInfCnt_scene_models_1/j2_d0_t0.png', 'Sudden'),
    'death': ('IfAll.usd/ScInfCnt_scene_models_1/j1_d0_t0.png', 'Death'),
    'success': ('IfAll.usd/ScInfCnt_scene_models_2/j1_d0_t0.png', 'Success!'),
    'ready': ('IfAll.usd/ScInfCnt_scene_models_3/j3_d0_t0.png', 'Ready'),
    'go': ('IfAll.usd/ScInfCnt_scene_models_4/j1_d0_t0.png', 'Go!'),
    'game': ('IfAll.usd/ScInfCnt_scene_models_5/j1_d0_t0.png', 'Game!'),
    'failure': ('IfAll.usd/ScInfCnt_scene_models_6/j1_d0_t0.png', 'Failure'),
    'complete': ('IfAll.usd/ScInfCnt_scene_models_7/j1_d0_t0.png', 'Complete!'),
    'continue_small': ('GmGover.dat/ScGamRegGover_scene_data_0/j57_d0_t0.png', 'CONTINUE?'),
    'gameover_small': ('GmGover.dat/ScGamRegGover_scene_data_0/j10_d0_t0.png', 'GAME OVER'),
    'coming': ('IfComSn.usd/ScComSoon_scene_data_0/j4_d0_t0.png', 'COMING'),
    'soon': ('IfComSn.usd/ScComSoon_scene_data_0/j3_d0_t0.png', 'SOON'),
    'pause': ('GmPause.usd/ScGamPause_scene_data_0/j7_d0_t0.png', 'Pause'),
}
GOVER = ['j14', 'j19', 'j24', 'j29', None, 'j34', 'j39', 'j44', 'j49']       # G A M E _ O V E R (56x56 I4 each)

def crop(im):
    a = np.asarray(im)[..., 3]; ys, xs = np.nonzero(a > 8)
    return im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)) if len(xs) else im

def swatch(im):
    """The word's fill as a full rectangle: per row, the fill pixels (not the outline's pure black, not the white stroke),
    interpolated across the row, so our own letters can be filled with the game's own gradient and streaks."""
    a = np.asarray(im).astype(float); rgb, al = a[..., :3], a[..., 3]
    black = (rgb.max(-1) < 6) | (al < 200); white = rgb.min(-1) > 240
    fill = ~black & ~white
    h, w = al.shape; out = np.zeros((h, w, 3)); prof = []
    for y in range(h):
        xs = np.nonzero(fill[y])[0]
        if len(xs) < 3: out[y] = np.nan; prof.append(None); continue
        for c in range(3): out[y, :, c] = np.interp(np.arange(w), xs, rgb[y, xs, c])
        prof.append(np.median(rgb[y, xs], 0))
    good = [y for y in range(h) if prof[y] is not None]
    for y in range(h):                                                   # rows with no fill: the nearest filled row
        if prof[y] is None: out[y] = out[min(good, key=lambda g: abs(g - y))]
    y0, y1 = good[0], good[-1]
    near = lambda y: prof[min(good, key=lambda g: abs(g - y))]
    stops = [[round((y - y0) / max(1, y1 - y0), 3), '#%02x%02x%02x' % tuple(int(v) for v in near(y))] for y in np.linspace(y0, y1, 7).astype(int)]
    return Image.fromarray(out[y0:y1 + 1].clip(0, 255).astype(np.uint8), 'RGB'), stops

def main(dump='~/games/melee/type/dump', out='~/games/melee/type'):
    global D, OUT
    D, OUT = os.path.expanduser(dump), os.path.expanduser(out)
    for sub in ('words', 'swatches', 'hud', 'names/banner', 'names/label', 'sis'): os.makedirs(os.path.join(OUT, sub), exist_ok=True)
    M = {'words': {}, 'styles': {}, 'hud': {}, 'names': {'banner': {}, 'label': {}}}
    for k, (p, text) in WORDS.items():
        im = crop(ld(p)); im.save(os.path.join(OUT, 'words', k + '.png'))
        M['words'][k] = {'w': im.size[0], 'h': im.size[1], 'text': text, 'src': p}
        if k in ('time', 'sudden', 'death', 'success', 'go', 'game', 'failure', 'complete'):
            sw, stops = swatch(im); sw.save(os.path.join(OUT, 'swatches', k + '.png'))
            M['styles'][k] = {'swatch': f'swatches/{k}.png', 'stops': stops}
    # GAME OVER (1P mode): the serif capitals the game drops in one by one, set on their own advance
    letters = [ld(f'GmGover.dat/ScGamRegGover_scene_data_0/{j}_d0_t0.png') if j else None for j in GOVER]
    W = sum(56 if l is not None else 30 for l in letters); go = Image.new('RGBA', (W, 56)); x = 0
    for l in letters:
        if l is not None: go.alpha_composite(l, (x, 0)); x += 56
        else: x += 30
    go = crop(go); go.save(os.path.join(OUT, 'words', 'gameover.png'))
    M['words']['gameover'] = {'w': go.size[0], 'h': go.size[1], 'text': 'GAME OVER', 'src': 'GmGover.dat (9 letter textures)', 'tint': True}
    for k in ('continue_small', 'gameover_small', 'pause'): M['words'][k]['tint'] = True
    # ---- 2. the HUD: damage digits (the percent font), %, HP, player tags, timer digits
    for i in range(10):
        ld(f'IfAll.usd/DmgNum_scene_models_0/j1_m0_ta0_{i:03d}.png').save(os.path.join(OUT, 'hud', f'dmg_{i}.png'))
    hud_more = {'dmg_pct': 'IfAll.usd/DmgNum_scene_models_0/j4_m0_ta0_000.png', 'hp': 'IfAll.usd/DmgNum_scene_models_0/j4_m0_ta0_001.png'}
    for k, p in hud_more.items():
        if os.path.exists(os.path.join(D, p)): ld(p).save(os.path.join(OUT, 'hud', k + '.png'))
    import glob
    pnm = sorted(glob.glob(os.path.join(D, 'IfAll.usd/ScInfPnm_scene_models_0/j1_m0_ta0_*.png')))
    for i, p in enumerate(pnm): Image.open(p).convert('RGBA').save(os.path.join(OUT, 'hud', f'tag_{i}.png'))
    # the damage digits and % are flat two-tone art (white, black outline): lift them to 8x with crisp edges, like the font
    for f in [x for x in os.listdir(os.path.join(OUT, 'hud')) if x.startswith('dmg_')]:
        im = Image.open(os.path.join(OUT, 'hud', f)).convert('RGBA'); w, h = im.size
        up = np.asarray(im.resize((w * 8, h * 8), Image.LANCZOS).filter(ImageFilter.GaussianBlur(2))).astype(float) / 255
        ss = lambda v, a, b: (lambda u: u * u * (3 - 2 * u))(np.clip((v - a) / (b - a), 0, 1))
        al = ss(up[..., 3], .35, .65); lum = ss(up[..., :3].mean(-1), .35, .65)
        rgb = np.dstack([lum] * 3)
        Image.fromarray((np.dstack([rgb, al]) * 255).astype(np.uint8), 'RGBA').save(os.path.join(OUT, 'hud', f[:-4] + '_hi.png'))
    for f in sorted(os.listdir(os.path.join(OUT, 'hud'))):
        im = Image.open(os.path.join(OUT, 'hud', f)); M['hud'][f[:-4]] = {'w': im.size[0], 'h': im.size[1]}
    # ---- 3. names: the results banner (outlined serif caps) and the results name labels (bold sans caps), same order
    KEYS = ['falcon', 'dk', 'fox', 'gnw', 'kirby', 'bowser', 'link', 'luigi', 'mario', 'marth', 'mewtwo', 'ness', 'peach',
            'pikachu', 'ics', 'puff', 'samus', 'yoshi', 'zelda', 'falco', 'ylink', 'doc', 'roy', 'pichu', 'ganon']
    BANNER = KEYS + ['red_team', 'blue_team', 'green_team', 'no_contest', 'sheik']
    LABEL = KEYS + [None, 'sheik']
    R = 'GmRst.usd/pnlsce_0'
    for i, k in enumerate(BANNER):
        im = crop(ld(f'{R}/j10_m1_ta0_{i:03d}.png')); im.save(os.path.join(OUT, 'names/banner', k + '.png'))
        M['names']['banner'][k] = {'w': im.size[0], 'h': im.size[1]}
    for i, k in enumerate(LABEL):
        if not k: continue
        im = crop(ld(f'{R}/j33_m0_ta0_{i:03d}.png')); im.save(os.path.join(OUT, 'names/label', k + '.png'))
        M['names']['label'][k] = {'w': im.size[0], 'h': im.size[1]}
    # ---- 4. the menu font: the SIS atlas (sisfont.py) lifted to 128 px cells for display sizes: Lanczos x4, then the
    # 4-bit intensity re-thresholded as a smooth step (crisp edges at size, the stems' weight kept)
    sis = json.load(open(os.path.join(OUT, 'sis', 'metrics.json')))
    at = Image.open(os.path.join(OUT, 'sis', 'atlas.png')).split()[3]
    hi = at.resize((at.size[0] * 4, at.size[1] * 4), Image.LANCZOS).filter(ImageFilter.GaussianBlur(1.2))
    a = np.asarray(hi).astype(float) / 255; a = np.clip((a - .38) / .24, 0, 1); a = a * a * (3 - 2 * a)
    A = (a * 255).astype(np.uint8)
    Image.fromarray(np.dstack([np.full_like(A, 255)] * 3 + [A]), 'RGBA').save(os.path.join(OUT, 'sis', 'atlas_hi.png'))
    M['font'] = {'atlas': 'sis/atlas_hi.png', 'cell': 128, 'native': 32, 'cols': sis['cols'],
                 'glyphs': {k: [v['i'], v['left'], v['right']] for k, v in sis['glyphs'].items()}}
    open(os.path.join(OUT, 'manifest.js'), 'w').write('window.MTYPE = ' + json.dumps(M) + ';\n')
    print(len(M['words']), 'words;', len(M['styles']), 'styles;', len(M['hud']), 'hud;',
          len(M['names']['banner']), '+', len(M['names']['label']), 'names;', len(M['font']['glyphs']), 'glyphs')

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument('--dump', default='~/games/melee/type/dump'); ap.add_argument('--out', default='~/games/melee/type')
    a = ap.parse_args(); main(a.dump, a.out)
