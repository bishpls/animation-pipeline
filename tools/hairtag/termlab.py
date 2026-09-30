"""Which hair piece moves a bundle-level hair check (hairtag round 3: art_terminator_hair 2.286 -> 2.905 at the gate,
the back view): two finished builds of the same code, BEFORE and AFTER, and the QA part run on AFTER's bundle with one
hair object at a time taken whole from BEFORE's (and the other way round). usage:
    python tools/hairtag/termlab.py BEFORE AFTER OUT.json [--part artifacts] [--check art_terminator_hair]
                                    [--pieces hair_bangs,...] [--only]
--only: just the two builds as they are (no swaps).
Per variant: the check's value, grade and per-view readings (and its ratio per view where the check has one)."""
import json, os, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from charkit import bundle as bl, qa3d


def _kv(a, k, d=None):
    return a[a.index(k) + 1] if k in a else d


def measure(B, part, check, swap=None):
    """the part on bundle B with the objects in swap ({name: another bundle's object}) put in its object table."""
    B._rec_objects()
    for n, o in (swap or {}).items():
        B._objs[n] = o
    rep = qa3d.run(B, tempfile.mkdtemp(prefix='termlab-'), parts=[part], mode='off')
    c = rep['checks'].get(check, {})
    return dict(value=c.get('value'), grade=c.get('grade'), status=c.get('status'), per_view=c.get('per_view'),
                ratio=c.get('ratio'))


def main(a):
    before, after, out = a[:3]
    part, check = _kv(a, '--part', 'artifacts'), _kv(a, '--check', 'art_terminator_hair')
    Bb, Ba = bl.load(os.path.join(before, 'bundle')), bl.load(os.path.join(after, 'bundle'))
    nb, na = {o.name: o for o in Bb.objects(visible=False)}, {o.name: o for o in Ba.objects(visible=False)}
    hair = [n for n, o in na.items() if o.group == 'hair' and n in nb]
    only = _kv(a, '--pieces')
    if only:
        hair = [h for h in hair if h in only.split(',')]
    res = {}
    t = time.time()
    res['before'] = measure(bl.load(os.path.join(before, 'bundle')), part, check)
    res['after'] = measure(bl.load(os.path.join(after, 'bundle')), part, check)
    print('%-28s %s' % ('before', res['before'])); print('%-28s %s' % ('after', res['after']))
    if '--only' not in a:
        for h in hair:
            res['after, %s before' % h] = measure(bl.load(os.path.join(after, 'bundle')), part, check, {h: nb[h]})
            res['before, %s after' % h] = measure(bl.load(os.path.join(before, 'bundle')), part, check, {h: na[h]})
            for k in ('after, %s before' % h, 'before, %s after' % h):
                print('%-28s %s %s' % (k, res[k]['value'], res[k]['ratio'] or res[k]['per_view']))
    json.dump(dict(before=before, after=after, part=part, check=check, results=res), open(out, 'w'), indent=1)
    print('(%.0f s) %s' % (time.time() - t, out))


if __name__ == '__main__':
    main(sys.argv[1:])
