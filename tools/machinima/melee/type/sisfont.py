"""Melee's menu font (the SIS text system) straight from the game's own main.dol: 287 glyphs of 32x32 GX I4, their
Shift-JIS character map (lbl_8040C8C0) and proportional margins (HSD_SisLib_8040CB00), as an atlas PNG and metrics JSON.
    .venv/bin/python tools/machinima/melee/type/sisfont.py [DOL] [OUT_DIR]
Default DOL: the decomp's copy of the original (orig/GALE01/sys/main.dol). Output (game-derived) to
~/games/melee/type/sis/: atlas.png (16 glyphs per row, 32x32 cells, white with alpha = intensity),
metrics.json ({char: {i, left, right}})."""
import json, os, struct, sys
import numpy as np
from PIL import Image
ADDR_CODES, ADDR_SJIS, ADDR_METRICS, ADDR_ATLAS, N = 0x8040C680, 0x8040C8C0, 0x8040CB00, 0x8040CD40, 287

def reader(dol):
    b = open(dol, 'rb').read()
    offs = struct.unpack('>18I', b[0:72]); addrs = struct.unpack('>18I', b[72:144]); sizes = struct.unpack('>18I', b[144:216])
    def read(addr, n):
        for o, a, s in zip(offs, addrs, sizes):
            if a <= addr < a + s: return b[o + addr - a:o + addr - a + n]
        raise ValueError(hex(addr))
    return read

def i4(data, w=32, h=32):
    px = np.zeros((h, w), np.uint8); k = 0
    for by in range(0, h, 8):
        for bx in range(0, w, 8):
            for y in range(8):
                for x in range(0, 8, 2):
                    v = data[k]; k += 1
                    px[by + y, bx + x] = (v >> 4) * 17; px[by + y, bx + x + 1] = (v & 15) * 17
    return px

def main(dol='~/games/melee/decomp/orig/GALE01/sys/main.dol', out='~/games/melee/type/sis'):
    DOL, OUT = os.path.expanduser(dol), os.path.expanduser(out)
    r = reader(DOL); os.makedirs(OUT, exist_ok=True)
    sj = r(ADDR_SJIS, 288 * 2); mt = r(ADDR_METRICS, 288 * 2); at = r(ADDR_ATLAS, N * 512); cd = r(ADDR_CODES, 288 * 2)
    cols = 16; rows = (N + cols - 1) // cols
    A = np.zeros((rows * 32, cols * 32), np.uint8); meta = {}
    for i in range(N):
        g = i4(at[i * 512:(i + 1) * 512]); A[(i // cols) * 32:(i // cols) * 32 + 32, (i % cols) * 32:(i % cols) * 32 + 32] = g
    import unicodedata
    # the character map: entry j pairs a Shift-JIS character (lbl_8040C8C0, in code order) with its SIS glyph code
    # (HSD_SisLib_8040C680): 0x2000 + the atlas index. The margins (HSD_SisLib_8040CB00) are indexed by atlas index.
    for j in range(288):
        code = cd[j * 2] << 8 | cd[j * 2 + 1]; lead, trail = sj[j * 2], sj[j * 2 + 1]
        if not code: continue
        g = code - 0x2000
        try: ch = bytes([lead, trail]).decode('shift_jis')
        except Exception: continue
        ch = unicodedata.normalize('NFKC', ch)                           # full-width Latin -> ASCII
        if ch.strip() == '' and ch != ' ': ch = ' '
        meta.setdefault(ch, {'i': g, 'left': mt[g * 2], 'right': mt[g * 2 + 1], 'sjis': f'{lead:02x}{trail:02x}'})
    rgba = np.dstack([np.full_like(A, 255)] * 3 + [A])
    Image.fromarray(rgba, 'RGBA').save(os.path.join(OUT, 'atlas.png'))
    json.dump({'cell': 32, 'cols': cols, 'glyphs': meta}, open(os.path.join(OUT, 'metrics.json'), 'w'), ensure_ascii=False, indent=0)
    print(N, 'glyphs;', ''.join(sorted(k for k in meta if len(k) == 1 and k.isascii())))

if __name__ == '__main__':
    main(*sys.argv[1:3])
