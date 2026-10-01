"""Which hair piece moves an artifact check (art_terminator_hair by default; --check DET_REGION, e.g. speckle_neck): the artifact part's own measure (charkit.artifactqa.ours, the head frame:
the QA's numpy drawings, as the check reads them) on a build's bundle with hair objects left out or swapped in from
another build's bundle. Per view: kinks per L of terminator (the check's headline), its length and kink count, and the
ratio against the design (qa.json's design values).

    python tools/hair5/term.py BUILD [--other OTHER_BUILD] [--variants 'none;-hair_ahoge;swap:hair_upper_back,hair_lower_back']
                               [--check terminator_hair] [--json OUT]

  -NAME[,NAME]      left out
  swap:NAME[,NAME]  OTHER's object records in place of BUILD's (the same lighting and frame: BUILD's assembly)
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from charkit import calibrate, artifactqa as aq

VIEWS = ('front', 'three_quarter', 'profile', 'back')


def run(B, design, drop=(), swap=None, check='terminator_hair'):
    det, region = check.split('_', 1)
    orig = B.objects
    def objects(groups=None, visible=True, parts=None, side=None):
        obs = [o for o in orig(groups, visible, parts, side) if o.name not in drop]
        if swap:
            obs = [swap.get(o.name, o) for o in obs]
        return obs
    B.objects = objects
    try:
        O = aq.ours(B)
    finally:
        B.objects = orig
    out = {}
    for v in VIEWS:
        rec = (O['head'].get(v) or {}).get(region) or {}
        t = rec.get(det) or {}
        k = aq._value(rec, det)
        d = design.get(v)
        out[v] = dict(value=k, len=t.get('len'), n_kinks=t.get('n_kinks'), n=t.get('n'),
                      ratio=None if k is None or d is None else round(k / max(d, aq.DETECTORS[det][2]), 3))
    return out


def main(a):
    b = a[0]
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    B = calibrate.load_bundle(b)
    check = opt('--check', 'terminator_hair')
    design = json.load(open(os.path.join(b, 'qa', 'qa.json')))['checks']['art_' + check]['design']
    other = calibrate.load_bundle(opt('--other')) if opt('--other') else None
    res = {}
    for var in opt('--variants', 'none').split(';'):
        drop, swap = (), None
        if var.startswith('-'):
            drop = tuple(var[1:].split(','))
        elif var.startswith('swap:'):
            swap = {n: other.obj(n) for n in var[5:].split(',')}
        r = run(B, design, drop, swap, check)
        res[var] = r
        worst = max((x['ratio'] or 0) for x in r.values())
        print('%-50s worst %.3f  ' % (var, worst) + '  '.join(
            '%s %s (%s)' % (v[:5], x['ratio'], x['value']) for v, x in r.items()), flush=True)
    if opt('--json'):
        json.dump(res, open(opt('--json'), 'w'), indent=1)


if __name__ == '__main__':
    main(sys.argv[1:])
