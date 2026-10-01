"""charkit.shapetruth: a part's shape truth (its layer redrawn without what covers it) repainted into a turnaround under
the covers, the turnaround standing everywhere else (Michael, 2026-10-01: hair checks against the no-accessories
references)."""
import json, os, shutil, sys, tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import manifest, shapetruth  # noqa: E402

ORANGE, GREY, YELLOW = (0.85, 0.42, 0.25), (0.75, 0.75, 0.75), (0.98, 0.85, 0.2)


def _head(H, W, c, r, clip=None):
    """a grey sheet with an orange disk (the hair) centred c (x, y) radius r, and a yellow square clip (x0, y0, x1, y1)."""
    img = np.empty((H, W, 3))
    img[:] = GREY
    yy, xx = np.mgrid[:H, :W]
    disk = (xx - c[0]) ** 2 + (yy - c[1]) ** 2 <= r * r
    img[disk] = ORANGE
    if clip is not None:
        x0, y0, x1, y1 = clip
        img[y0:y1, x0:x1] = YELLOW
    return img, disk


def test_the_manifest_names_a_parts_shape_truth():
    """entry(): shape_truth[part] naming a picture -> its path, rows and views; none, or not a picture -> None."""
    d = tempfile.mkdtemp(prefix='charkit-shapetruth-')
    try:
        R = {'heads': {'kind': 'picture', 'path': os.path.join(d, 'heads.png')},
             'clean': {'kind': 'picture', 'path': os.path.join(d, 'clean.png')}}
        mp = os.path.join(d, 'manifest.json')
        json.dump({'name': 't', 'references': R, 'shape_truth': {
            'hair': {'shape': 'clean', 'rows': 'top', 'views': ['front'], 'placement': 'heads'},
            'jaw': {'shape': 'a breakdown (its family)'}}}, open(mp, 'w'))
        spec = {'name': 't', 'ref': {'manifest': mp}}
        e = shapetruth.entry(spec, 'hair')
        assert e['path'] == R['clean']['path'] and e['rows'] == 'top' and e['views'] == ['front']
        assert e['covers'] == 'accessories' and e['placement'] == 'heads'
        assert shapetruth.entry(spec, 'jaw') is None and shapetruth.entry(spec, 'beard') is None
        assert shapetruth.entry({'name': 't'}, 'hair') is None
    finally:
        shutil.rmtree(d, ignore_errors=True)
    clawd = manifest.resolve(json.load(open(os.path.join(manifest.ROOT, 'charkit', 'spec', 'clawd.json'))))
    e = shapetruth.entry(clawd, 'hair')
    assert e['id'] == 'hair_clips_layers' and e['rows'] == 'top' and 'back' not in e['views']


def test_labels_under_the_cover_come_from_the_nearest_drawn_label():
    """fill_labels: the part's pixels under the repainted area take the nearest label outside it, the rest none."""
    lab = np.zeros((10, 20), int)
    lab[:, :10], lab[:, 10:] = 1, 2
    cov = np.zeros(lab.shape, bool)
    cov[3:7, 6:14] = True
    lab[cov] = 9                                        # (the clip's own label: gone)
    part = np.ones(lab.shape, bool)
    part[5, 7] = False                                  # (not the part there: no label)
    out = shapetruth.fill_labels(lab, cov, part)
    assert out[4, 7] == 1 and out[4, 12] == 2 and out[5, 7] == 0 and (out[~cov] == lab[~cov]).all()


def test_the_cover_is_repainted_from_the_registered_redraw():
    """composite(): a sheet with a clip over its hair, the redraw (at twice the scale, no clip): the clip's pixels
    become the redraw's hair, registered on the view (scale and shift found), the rest of the sheet untouched; the
    refcheck numbers pass. The redraw shifted beyond the search reads a poor ring (the known-bad's way)."""
    H, W, ppl = 160, 160, 60.0
    sheet, disk = _head(H, W, (80, 80), 40, clip=(96, 60, 112, 76))
    src_rgb, src_disk = _head(2 * H, 2 * W, (160, 160), 80)
    fg = np.abs(src_rgb - GREY).sum(-1) > 0.1
    src = dict(rgb=src_rgb, ppl=2 * ppl, views={'front': (160.0, 160.0)}, fg=fg,
               part=shapetruth.part_mask(src_rgb, fg), blobs={'front': fg})
    cover = np.zeros((H, W), bool)
    cover[60:76, 96:112] = True
    out, ofg, rep, filled = shapetruth.composite(sheet, None, {'front': cover}, {'front': (80.0, 80.0)}, ppl, src)
    r = rep['front']
    assert abs(r['scale'] - 0.5) < 0.011 and r['ring_iou'] > 0.95 and r['hair_iou'] > 0.95 and r['pass']
    assert np.allclose(out[cover].mean(0), ORANGE, atol=0.05)          # the clip repainted as the hair
    assert np.array_equal(out[~filled['front']], sheet[~filled['front']])     # the turnaround everywhere else
    # mislaid: the redraw's head 40 px off (beyond SHIFT): the ring disagrees
    src2 = dict(src, views={'front': (160.0 + 80, 160.0)})
    _, _, rep2, _ = shapetruth.composite(sheet, None, {'front': cover}, {'front': (80.0, 80.0)}, ppl, src2)
    assert rep2['front']['hair_iou'] < 0.85 and not rep2['front']['pass']


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f()
            print('ok', k)
