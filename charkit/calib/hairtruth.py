"""Calibration adapter for the hair truth's score (charkit.hairlayers.score: the hair layer masks against the hand-checked
truth, charkit/refs/clawd/hair_truth.npz; tool/hairtag). A score, not a graded check: its calibration is its
separations. The design: the truth's own regions as masks (each region its accepted set's first family and bun side),
moved 1-2 px; the known-bad: the masks the transfer made before the structure method (hairlayers.STRUCT_OFF, pipeline-3d
until 3ebc3fb: 0.892); the floor: each truth region given a random family; the current: the produced hair layers.
"""
import os

import numpy as np

CALIBRATION = [
    dict(check='hair_truth_accuracy', part=None, adapter='HairTruth', known_bad='hair_transfer', kind='score',
         baseline=['shuffle_regions'], shape=[], better='higher'),
]


class HairTruth:
    part = None
    generators = {'shuffle_regions': "each truth region given a random family (weighted by the families' truth areas)"}

    def __init__(self, B, design):
        from .. import hairlayers, manifest
        self.spec = B.spec if B is not None else None
        self.R = manifest.load(self.spec['ref']['manifest'])['references']
        self.truth = hairlayers.load_truth(self.R['hair_truth']['path'])

    def _score(self, masks):
        from .. import hairlayers
        r = hairlayers.score(masks, self.truth)
        return {'hair_truth_accuracy': dict(value=r['all']['accuracy'], status=None, per_view={
            v: x['accuracy'] for v, x in r.items() if isinstance(x, dict) and 'accuracy' in x and v != 'all'},
            mean_iou=r['all']['mean_iou'])}

    def _load(self, path):
        from .. import hairlayers
        Z = np.load(hairlayers._p(path))
        return {k: Z[k] for k in Z.files}

    def measure(self, B):
        return self._score(self._load(self.R['hair_layers']['path']))

    def measure_known_bad(self, name):
        """the transfer's masks (the structure method off), made once into the calibration store."""
        from .. import calibrate, hairlayers
        out = os.path.join(calibrate.STORE, name)
        p = os.path.join(out, 'hair_layers.npz')
        if not os.path.exists(p):
            os.makedirs(out, exist_ok=True)
            hairlayers.produce(self.spec, out, page=False, log=lambda *a: None, struct=hairlayers.STRUCT_OFF)
        return self._score(self._load(p))

    def masks(self, kind, arg):
        """the truth as masks: each region its set's first family (and bun side), moved (kind 'design', arg (dy, dx))
        or each region a random family (kind 'shuffle_regions', arg a seed)."""
        from .. import hairlayers
        from .labels import _shift
        T, sets, _ = self.truth
        rng = np.random.default_rng(4000 + int(arg)) if kind != 'design' else None
        fams = list(hairlayers.FAMILIES)
        area = np.array([sum(int((t == i).sum()) for t in T.values() for i, st in enumerate(sets)
                             if hairlayers._fam(st[0]) == f) for f in fams], float) + 1.0
        out = {}
        for v, t in T.items():
            fam_img = np.full(t.shape, -1, np.int32)
            side = np.full(t.shape, -1, np.int32)
            for i in np.unique(t[t >= 0]):
                st = sets[int(i)]
                m = t == i
                if kind == 'design':
                    f = hairlayers._fam(st[0])
                    if f in fams:
                        fam_img[m] = fams.index(f)
                    if st[0] in ('bun_L', 'bun_R'):
                        side[m] = ('bun_L', 'bun_R').index(st[0])
                else:
                    fam_img[m] = rng.choice(len(fams), p=area / area.sum())
            if kind == 'design':
                fam_img, side = _shift(fam_img, arg[0], arg[1], -1), _shift(side, arg[0], arg[1], -1)
            for k, f in enumerate(fams):
                out['%s__%s' % (v, f)] = fam_img == k
            if kind == 'design':
                for k, q in enumerate(('bun_L', 'bun_R')):
                    out['%s__%s' % (v, q)] = side == k
        return out

    def run(self, kind, arg):
        return self._score(self.masks(kind, arg))
