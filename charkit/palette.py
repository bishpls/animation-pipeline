"""A character's palette: the colours its design is drawn in, each with a role, so reading a drawing (which pixels are
skin, hair, iris, line, garment) comes from the character's own references instead of constants tuned to one design.

The colour classes were Clawd's (sheetqa.SKIN / HAIR / IRIS, bodyqa.family's orange, cream, dark and white): on a second
character every reader of a sheet failed or misread it (2026-10-01: an olive skin read as Clawd's orange hair, brown
irises in no class, so no eyes, no views, no scale). A character's manifest now declares its palette:

    "palette": {"source": REF_ID, "found_by": "charkit.palette.swatches",
                "swatches": [{"name": "skin", "rgb": [r, g, b], "role": "skin"}, ...],
                "line": [r, g, b]}                       (optional: the ink; near-black when absent)

roles: skin, skin_shade, hair, hair_shade, iris, garment, accessory (anything else is read as accessory). The swatches
come from the design itself (a model sheet's row of colour swatches: swatches()), named in the order its prompt or
designer declared them. A manifest without a palette keeps the constants (Clawd's: nothing she reads moves).

Reading a picture with a palette: every pixel takes its nearest colour (CIE Lab distance) among the swatches and the
line's ink; a pixel farther than FAR from all of them is 'other'. A garment drawn in a hair colour (within SHARED of a
hair swatch: a white tunic under white hair) reads as hair, as Clawd's orange dress reads as her orange hair; position
tells them apart where the readers already do it (bodyqa.classes' split at the shoulders).

The active palette: set where a spec resolves (manifest.resolve) or a resolved spec is loaded (qa3d.run, from
spec.ref.palette); sheetqa.classes and bodyqa.family read it. One character per process, as one spec per build.

    python -m charkit.palette swatches SHEET.png [--names a,b,c]     # the swatch row found on a sheet, as manifest JSON
"""
import json, os, sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAR = 32.0                 # Lab distance: a pixel farther than this from every swatch and the ink is 'other'
SHARED = 6.0               # Lab distance: a garment colour this close to a hair colour reads as hair (told apart by place)
BLEND = 8.0                # Lab distance: a swatch this close to a blend of two others (or of one and the ink) is what an
                           # anti-aliased edge between them looks like (a dark-brown iris is skin half-blended with ink):
                           # its pixels count only where they survive a 1-px opening (edges are 1-2 px, the feature isn't)
INK = (0.09, 0.08, 0.08)   # the line's ink when the palette declares none
ROLES = ('skin', 'skin_shade', 'hair', 'hair_shade', 'iris', 'garment', 'accessory')

_ACTIVE = None


def activate(P):
    """make P (a manifest palette dict, or None for the constants) the process's active palette. -> the previous one."""
    global _ACTIVE
    prev, _ACTIVE = _ACTIVE, (Palette(P) if P else None)
    return prev


def activate_spec(spec):
    """activate the character a resolved spec carries: its palette (spec.ref.palette) and its body window
    (spec.ref.window, bodyqa.use_window), or the defaults."""
    from .bodyqa import use_window
    ref = spec.get('ref') if isinstance(spec, dict) and isinstance(spec.get('ref'), dict) else {}
    use_window(ref.get('window'))
    return activate(ref.get('palette'))


def active():
    return _ACTIVE


def lab(rgb):
    from .paletteqa import srgb_to_lab
    return srgb_to_lab(np.clip(np.asarray(rgb, float), 0, 1))


class Palette:
    def __init__(self, P):
        sw = P['swatches']
        self.names = [s['name'] for s in sw]
        self.roles = [s.get('role', 'accessory') if s.get('role') in ROLES else 'accessory' for s in sw]
        self.rgb = np.array([s['rgb'] for s in sw], float)
        self.ink = np.array(P.get('line') or INK, float)
        self.lab = lab(np.vstack([self.rgb, self.ink[None]]))          # the ink last
        hair = [i for i, r in enumerate(self.roles) if r in ('hair', 'hair_shade')]
        # a non-hair swatch within SHARED of a hair swatch reads as that hair role
        self.reads = list(self.roles)
        for i, r in enumerate(self.roles):
            if r not in ('hair', 'hair_shade') and hair:
                d = [np.linalg.norm(self.lab[i] - self.lab[j]) for j in hair]
                if min(d) < SHARED:
                    self.reads[i] = self.roles[hair[int(np.argmin(d))]]
        self.blend = [self._blend_distance(i) < BLEND for i in range(len(self.names))]
        # dark eyes: an iris the ink's blends can draw (a dark-brown iris is skin half-blended with ink). Drawn small,
        # such an iris is ink-dark, so the eye search reads compact dark blobs instead (sheetqa.find_eyes: eye_mask)
        self.dark_eyes = any(r == 'iris' and self.blend[i] for i, r in enumerate(self.roles))

    def _blend_distance(self, i):
        """how close swatch i is to an sRGB blend (a quarter to three quarters) of two other colours (swatches or the
        ink), in Lab."""
        cols = np.vstack([self.rgb, self.ink[None]])
        others = [j for j in range(len(cols)) if j != i]
        t = np.linspace(0.25, 0.75, 11)[:, None]      # a mixture, not a near copy of either end
        best = np.inf
        for a in range(len(others)):
            for b in range(a + 1, len(others)):
                seg = lab(cols[others[a]] * (1 - t) + cols[others[b]] * t)
                best = min(best, float(np.sqrt(((seg - self.lab[i]) ** 2).sum(1)).min()))
        return best

    def nearest(self, rgb):
        """per pixel (..., 3): the nearest swatch's index, len(swatches) for the ink, -1 past FAR."""
        L = lab(rgb)
        sh = L.shape[:-1]
        L = L.reshape(-1, 3)
        best = np.full(len(L), -1, int)
        bd = np.full(len(L), FAR, float)
        for k, c in enumerate(self.lab):
            d = np.sqrt(((L - c) ** 2).sum(1))
            m = d < bd
            best[m], bd[m] = k, d[m]
        return best.reshape(sh)

    def nearest_among(self, L, idx):
        """per pixel (L: Lab, (..., 3)) the nearest of the swatches idx and the ink: the swatch index, len(swatches) for
        the ink, -1 past FAR."""
        sh = L.shape[:-1]
        L = L.reshape(-1, 3)
        best = np.full(len(L), -1, int)
        bd = np.full(len(L), FAR, float)
        for k in list(idx) + [len(self.names)]:
            d = np.sqrt(((L - self.lab[k]) ** 2).sum(1))
            m = d < bd
            best[m], bd[m] = k, d[m]
        return best.reshape(sh)

    def role_image(self, rgb):
        """per pixel its read role: one of ROLES, 'line', or 'other'. A blend-ambiguous swatch's pixels (self.blend) that
        an opening removes (an edge's anti-aliasing) are 'other'. -> (role names, index image into them)."""
        names = list(ROLES) + ['line', 'other']
        lut = np.array([names.index(r) for r in self.reads] + [names.index('line'), names.index('other')])
        k = self.nearest(rgb)
        if k.ndim == 2:
            for i, b in enumerate(self.blend):
                if b:
                    m = k == i
                    if m.any():
                        k[m & ~_open(m)] = -1
        return names, lut[np.where(k < 0, len(lut) - 1, k)]

    def to_json(self):
        return dict(swatches=[dict(name=n, rgb=[round(float(v), 4) for v in c], role=r)
                              for n, c, r in zip(self.names, self.rgb, self.roles)],
                    line=[round(float(v), 4) for v in self.ink])


def _open(m, r=1):
    """an r-px opening ((2r+1)^2 erode then dilate) of a bool image."""
    from .bodyqa import dilate, erode
    return dilate(erode(m, r), r)


EYE_OPEN = 2               # px: the opening that leaves a dark eye's iris (8+ px across on a full-body sheet) and removes
                           # the strokes (1-2 px half-width on the generated sheets)


def eye_mask(lab, P, soft=False):
    """the pixels the eye search reads (sheetqa.find_eyes), from a label image (sheet_classes'): the iris class, and
    for dark eyes (P.dark_eyes) the iris or ink pixels that survive an EYE_OPEN opening (compact dark blobs, not
    strokes); soft: a 1-px opening (a profile's eye is a sliver; the caller bounds the search to the eye line)."""
    m = lab == 3
    if P is not None and P.dark_eyes:
        m = _open(m | (lab == 4), 1 if soft else EYE_OPEN)
    return m


def sheet_classes(rgb, P):
    """sheetqa.classes' label image (0 other, 1 skin, 2 hair, 3 iris, 4 line, 5 shaded skin) from palette P."""
    names, k = P.role_image(rgb)
    to = {'skin': 1, 'skin_shade': 5, 'hair': 2, 'hair_shade': 2, 'iris': 3, 'line': 4}
    lut = np.array([to.get(n, 0) for n in names])
    return lut[k]


def family_classes(rgb, P):
    """bodyqa.family's class ids from palette P: skin (its shade too) 1, iris 3, the ink 'dark' (bodyqa.classes splits
    thin dark into line), accessories 'other'. Hair (and a garment drawn in its colour) takes the 'orange' slot, the one
    bodyqa.classes splits into hair (regions centred above the shoulders) and garment (below), as Clawd's orange hair
    and dress are split; every other garment colour takes the 'white' slot (a garment family the split leaves alone).
    The outfit is thus read as one union of garments, not Clawd's four families (cream, dark trims, white boots)."""
    from .bodyqa import CLASS
    names, k = P.role_image(rgb)
    to = {'skin': CLASS['skin'], 'skin_shade': CLASS['skin'], 'hair': CLASS['orange'], 'hair_shade': CLASS['orange'],
          'iris': CLASS['iris'], 'garment': CLASS['white'], 'accessory': CLASS['other'], 'line': CLASS['dark'],
          'other': CLASS['other']}
    lut = np.array([to[n] for n in names])
    return lut[k]


# ------------------------------------------------------------------------------------- the spec's colours from it
def _first(P, roles):
    for r in roles:
        for n, c, ro in zip(P.names, P.rgb, P.roles):
            if ro == r:
                return np.asarray(c, float)
    return None


def spec_colours(P):
    """the spec's colour sections from palette P (a Palette), where it names the roles: skin (lit, shade, deep), the
    hair's (lit, shade, deep, line), the iris (its top, mid and bottom gradient, ring and pupil round the eye swatch), the
    brows and lashes (the brows in the hair's colour, the lashes the ink). The anime style's look multiplies these as it
    does any character's: these are only the design's own colours, where the code had Clawd's. -> dict (may be empty)."""
    out = {}
    sk, sh = _first(P, ('skin',)), _first(P, ('skin_shade',))
    if sk is not None:
        sh = sh if sh is not None else sk * 0.82
        out['skin'] = dict(lit=_r(sk), shade=_r(sh), deep=_r(sh * 0.88))
        out['skin_line'] = _r(sh * 0.55)
    hl, hs = _first(P, ('hair',)), _first(P, ('hair_shade',))
    if hl is not None:
        hs = hs if hs is not None else hl * 0.8
        out['hair_colors'] = dict(lit=_r(hl), shade=_r(hs), deep=_r(hs * 0.85), line=_r(hs * 0.55), strand=_r(hs * 0.95))
        out['brow_color'] = _r(hl)
    ir = _first(P, ('iris',))
    if ir is not None:
        out['iris'] = dict(top=_r(ir * 0.6), mid=_r(ir), bottom=_r(ir + (1 - ir) * 0.35), ring=_r(ir * 0.4),
                           pupil=_r(ir * 0.22))
    out['lash_color'] = _r(P.ink)
    return out


def _r(c):
    return [round(float(v), 4) for v in np.clip(c, 0, 1)]


# --------------------------------------------------------------------------------------------- finding the swatches
def swatches(rgb, min_px=400, fill=0.9, aspect=(0.7, 1.4), flat=0.02):
    """a sheet's row of colour swatches (flat, near-square blobs of one size on one row), left to right ->
    [dict(box=[x0, y0, x1, y1], rgb=[...])]. The colour is the median of the blob's inner three fifths (its edge is
    anti-aliased); a blob whose inner part isn't flat (std over `flat`) is no swatch. [] when no row of three is found."""
    from . import sheetqa
    rgb = np.asarray(rgb, float)
    bg = sheetqa.background(rgb)
    fg = sheetqa.foreground(rgb, bg)
    lab_, n = sheetqa.label(fg)
    B, area = sheetqa.boxes(lab_, n)
    cand = []
    for i in range(n):
        x0, y0, x1, y1 = (int(v) for v in B[i])
        w, h = x1 - x0 + 1, y1 - y0 + 1
        if area[i] < min_px or area[i] < fill * w * h or not (aspect[0] < w / h < aspect[1]):
            continue
        inner = rgb[y0 + h // 5:y1 - h // 5 + 1, x0 + w // 5:x1 - w // 5 + 1].reshape(-1, 3)
        if not len(inner) or inner.std(0).max() > flat:
            continue
        cand.append(dict(box=[x0, y0, x1, y1], rgb=[round(float(v), 4) for v in np.median(inner, 0)], w=w, h=h))
    # the largest group sharing one row and one size
    best = []
    for c in cand:
        grp = [d for d in cand if abs(d['box'][1] - c['box'][1]) <= 0.25 * c['h'] and abs(d['w'] - c['w']) <= 0.15 * c['w']
               and abs(d['h'] - c['h']) <= 0.15 * c['h']]
        if len(grp) > len(best):
            best = grp
    if len(best) < 3:
        return []
    return [dict(box=d['box'], rgb=d['rgb']) for d in sorted(best, key=lambda d: d['box'][0])]


def main(args):
    if not args or args[0] != 'swatches':
        sys.exit(__doc__)
    from PIL import Image
    rgb = np.asarray(Image.open(args[1]).convert('RGB')).astype(float) / 255
    found = swatches(rgb)
    names = args[args.index('--names') + 1].split(',') if '--names' in args else []
    out = [dict(name=names[i] if i < len(names) else 'swatch_%d' % i, rgb=s['rgb'], box=s['box'])
           for i, s in enumerate(found)]
    print(json.dumps(out, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
