"""charkit.palette: a character's own colours read its drawings (the swatch row found, classes by nearest colour, dark
eyes by shape, the layer checks by palette), and with no palette declared nothing Clawd reads moves."""
import json, os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import bodyqa, layerref, palette, sheetqa  # noqa: E402

BG = (0.75, 0.76, 0.77)
SKIN, HAIR, IRIS, CLOTH, DRAPE = (0.82, 0.59, 0.43), (0.95, 0.94, 0.93), (0.42, 0.29, 0.23), (0.55, 0.38, 0.27), \
    (0.41, 0.29, 0.54)
INK = (0.09, 0.08, 0.08)
P = dict(swatches=[dict(name='skin', rgb=SKIN, role='skin'), dict(name='hair white', rgb=HAIR, role='hair'),
                   dict(name='eye', rgb=IRIS, role='iris'), dict(name='belt', rgb=CLOTH, role='garment'),
                   dict(name='sash', rgb=DRAPE, role='garment')])


def test_swatches_found_in_order():
    im = np.ones((300, 900, 3)) * BG
    cols = [SKIN, HAIR, IRIS, CLOTH, DRAPE]
    for i, c in enumerate(cols):
        im[200:260, 100 + i * 120:160 + i * 120] = c
    im[20:150, 300:420] = SKIN                                  # a figure: not a swatch (not square, not in the row)
    im[20:150, 330:340] = INK
    found = palette.swatches(im)
    assert len(found) == 5
    for f, c in zip(found, cols):
        assert np.allclose(f['rgb'], c, atol=0.01)


def test_classes_by_nearest_colour_and_shared_hair():
    pal = dict(P, swatches=P['swatches'] + [dict(name='tunic', rgb=(0.96, 0.95, 0.93), role='garment')])
    Pa = palette.Palette(pal)
    assert Pa.reads[-1] == 'hair'                               # a tunic in the hair's white reads as hair
    px = np.repeat(np.repeat(np.array([[SKIN, HAIR, DRAPE, INK, (0.1, 0.9, 0.1)]]), 9, 0), 9, 1)   # 9 px blocks
    lab = palette.sheet_classes(px, Pa)
    assert lab[4, 4::9].tolist() == [1, 2, 0, 4, 0]             # skin, hair, garment (other), line, far (other)
    fam = palette.family_classes(px, Pa)
    C = bodyqa.CLASS
    assert fam[4, 4::9].tolist() == [C['skin'], C['orange'], C['white'], C['dark'], C['other']]


def test_no_palette_keeps_the_constants():
    prev = palette.activate(None)
    try:
        px = np.array([[(0.98, 0.855, 0.757), (0.83, 0.48, 0.33), (0.95, 0.80, 0.10)]])     # Clawd: skin, hair, iris
        assert sheetqa.classes(px)[0].tolist() == [1, 2, 3]
        assert bodyqa.family(px)[0].tolist() == [bodyqa.CLASS['skin'], bodyqa.CLASS['orange'], bodyqa.CLASS['iris']]
        palette.activate(P)
        assert sheetqa.classes(px)[0].tolist() != [1, 2, 3]   # (the palette reads them by its own colours)
    finally:
        palette.activate(prev)


def face(eyes=True, ppl=160.0):
    """a full figure: a skin head with an ink outline and ink strokes (brow, nose), small dark irises (drawn near
    ink, 8 px across: the generated turnarounds' small dark eyes), a white body below."""
    H, W = 900, 500
    im = np.ones((H, W, 3)) * BG
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    head = ((xx - 250) / 70) ** 2 + ((yy - 160) / 95) ** 2 <= 1
    ring = (((xx - 250) / 72) ** 2 + ((yy - 160) / 97) ** 2 <= 1) & ~head
    im[head] = SKIN
    im[ring] = INK
    body = (np.abs(xx - 250) < 120) & (yy > 255) & (yy < 860)
    im[body] = HAIR
    im[(np.abs(xx - 250) < 122) & (yy > 253) & (yy < 862) & ~body & ~head] = INK
    im[120:122, 205:240] = INK                                  # a brow stroke (2 px)
    im[150:190, 249:251] = INK                                  # the nose's stroke
    if eyes:
        for x in (222, 278):
            im[((xx - x) ** 2 + (yy - 140) ** 2) <= 16] = (0.16, 0.11, 0.10)
    return im


def test_dark_eyes_are_found_by_shape_not_strokes():
    prev = palette.activate(P)
    try:
        assert palette.active().dark_eyes                       # the brown iris is skin half-blended with ink
        lab = sheetqa.classes(face())
        e = sheetqa.find_eyes(lab, (130, 60, 370, 300), 2, max_tilt=0.25)
        assert len(e) == 2 and abs(e[0][0] - 222) < 3 and abs(e[1][0] - 278) < 3, e
        assert sheetqa.find_eyes(sheetqa.classes(face(eyes=False)), (130, 60, 370, 300), 2, max_tilt=0.25) == []
    finally:
        palette.activate(prev)


def sheet(cover=True, wide=1.0):
    """two figures (a white body with a sash band across it) on one sheet; cover False paints the sash as the body under
    it, wide widens the bodies about their axes (a redraw that stands outside the original)."""
    H, W = 500, 700
    im = np.ones((H, W, 3)) * BG
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    for cx in (180, 520):
        body = (np.abs(xx - cx) < 90 * wide) & (yy > 60) & (yy < 440)
        im[body] = HAIR
        out = (np.abs(xx - cx) < 90 * wide + 2) & (yy > 58) & (yy < 442) & ~body
        im[out] = INK
        if cover:
            band = body & (np.abs((yy - 200) - 0.6 * (xx - cx)) < 22)
            im[band] = DRAPE
    return im


def test_edit_kind_calibrated():
    """the turnaround with its sash removed PASSes; left on (nothing removed) or widened 8% FAILs."""
    Pa = palette.Palette(P)
    T = sheet()
    good, _ = layerref.edit_views(T, sheet(cover=False), Pa, ['sash'], log=lambda *a: None)
    assert good['pass'], good
    same, _ = layerref.edit_views(T, T, Pa, ['sash'], log=lambda *a: None)
    assert not same['pass'] and min(v['cover_left'] for v in same['views'].values()) > 0.5
    wide, _ = layerref.edit_views(T, sheet(cover=False, wide=1.08), Pa, ['sash'], log=lambda *a: None)
    assert not wide['pass'] and max(v['outside'] for v in wide['views'].values()) > layerref.GEN_TOL['outside']
    # a cover in the colour of what it hides: graded by what the edit reveals there instead
    rv, _ = layerref.edit_views(T, sheet(cover=False), Pa, ['sash'], revealed=['hair'], ungraded=['cover_left'],
                                log=lambda *a: None)
    assert rv['pass'] and min(v['revealed'] for v in rv['views'].values()) > 0.9
    kept, _ = layerref.edit_views(T, T, Pa, ['sash'], revealed=['hair'], ungraded=['cover_left'], log=lambda *a: None)
    assert not kept['pass'] and max(v['revealed'] for v in kept['views'].values()) < layerref.GEN_TOL['revealed']


def test_manifest_resolve_activates_and_carries_the_palette(tmp_path):
    from charkit import manifest
    prev = palette.active()
    try:
        m = tmp_path / 'manifest.json'
        m.write_text(json.dumps(dict(name='x', references={}, palette=P)))
        spec = manifest.resolve(dict(name='x', ref=dict(manifest=str(m))))
        assert spec['ref']['palette'] == json.loads(json.dumps(P)) and palette.active() is not None
        m2 = tmp_path / 'm2.json'
        m2.write_text(json.dumps(dict(name='y', references={})))
        manifest.resolve(dict(name='y', ref=dict(manifest=str(m2))))
        assert palette.active() is None                         # a character without one: the constants again
    finally:
        palette.activate(prev.to_json() if prev is not None else None)


if __name__ == '__main__':          # the gate runs each test file as a script
    import pytest
    sys.exit(pytest.main([__file__, '-q']))
