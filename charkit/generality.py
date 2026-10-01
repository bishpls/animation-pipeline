"""The generality reading (Michael, 2026-09-30: any character's references in, a rigged model out, no per-character
tuning; the metric is the share of checks a new character passes out of the box): a build's QA tallied, with the checks
named for another character's pieces (a vocabulary: Clawd's outfit graph's piece ids and types, her hair families and
clips) apart from the checks that apply to any character.

  share     PASS / (PASS + WARN + FAIL + errored parts): the first reading's convention (a second character, 2026-09-30:
            6 / 20 = 30%; Clawd 177 / 213 = 83%), per bucket and overall
  buckets   'named' (a check whose name holds a vocabulary token: skirt, bow, crab, bangs...), 'applicable' (the rest)
  parts     the QA parts that raised (qa.json's SKIPPED entries with an error), each with its error

    python -m charkit.generality BUILD [--vocab GRAPH.json[,GRAPH.json]] [--json OUT]
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOCAB_GRAPH = 'charkit/refs/clawd/outfit_graph.json'
EXTRA = ('bangs', 'ahoge', 'flyaway', 'flyaways', 'buns', 'bun', 'crab', 'star', 'clip', 'clips', 'stair', 'stairs',
         'flap', 'flaps', 'pleat', 'pleats', 'lapel', 'lapels', 'puff', 'ribbon', 'ribbons', 'knot', 'lobe', 'lobes',
         'boots', 'cuffs', 'collar', 'bodice', 'hem', 'tails', 'waistband')
GENERIC = ('hair', 'skin', 'iris', 'eye', 'eyes', 'face', 'body', 'shape', 'mesh', 'head', 'hand', 'hands', 'arm',
           'leg', 'legs', 'neck', 'chin', 'jaw', 'mouth', 'nose', 'brow', 'brows', 'lash', 'palette', 'outline', 'line',
           'top', 'side', 'back', 'front', 'profile', 'L', 'R')


def vocabulary(paths=(VOCAB_GRAPH,)):
    """the tokens naming another character's pieces: its graph's piece ids, pairs and types split into words, the
    EXTRA hair and garment words; minus the GENERIC words any character has."""
    words = set(EXTRA)
    for p in paths:
        p = p if os.path.isabs(p) else os.path.join(ROOT, p)
        if not os.path.exists(p):
            continue
        G = json.load(open(p))
        for pc in G.get('pieces') or ():
            for s in (pc.get('id'), pc.get('pair'), pc.get('type')):
                if s:
                    words |= set(re.split(r'[\s_.\-]+', s.lower()))
    return {w for w in words if w and w not in GENERIC and not w.isdigit()}


def tokens(name):
    return set(re.split(r'[\s_.\-/:]+', name.lower()))


def tally(qa, vocab):
    """qa.json's checks into buckets -> dict(buckets {named, applicable: {status: n, share}}, overall, parts)."""
    out = {'named': {}, 'applicable': {}}
    parts = {}
    names = {'named': [], 'applicable': []}
    for k, c in qa.get('checks', {}).items():
        st = c.get('status', 'INFO')
        if st == 'SKIPPED' and c.get('why') and ('Error' in c['why'] or ':' in c['why']):
            parts[k] = c['why'][:300]
            st = 'ERROR'
        b = 'named' if tokens(k) & vocab else 'applicable'
        out[b][st] = out[b].get(st, 0) + 1
        names[b].append(k)
    for b, d in out.items():
        den = sum(d.get(s, 0) for s in ('PASS', 'WARN', 'FAIL', 'ERROR'))
        d['share'] = round(d.get('PASS', 0) / den, 4) if den else None
        d['n'] = sum(v for s, v in d.items() if s not in ('share',))
    all_ = {}
    for d in out.values():
        for s, v in d.items():
            if s not in ('share', 'n'):
                all_[s] = all_.get(s, 0) + v
    den = sum(all_.get(s, 0) for s in ('PASS', 'WARN', 'FAIL', 'ERROR'))
    all_['share'] = round(all_.get('PASS', 0) / den, 4) if den else None
    return dict(buckets=out, overall=all_, parts=parts, names=names)


def main(args):
    if not args or args[0] in ('-h', '--help'):
        print(__doc__); return 0
    opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
    build = args[0]
    qp = os.path.join(build, 'qa', 'qa.json') if os.path.isdir(os.path.join(build, 'qa')) else os.path.join(build, 'qa.json')
    vocab = vocabulary(opt('--vocab', VOCAB_GRAPH).split(','))
    T = tally(json.load(open(qp)), vocab)
    for b, d in T['buckets'].items():
        print('%-11s %s' % (b, ', '.join('%s %s' % kv for kv in sorted(d.items()))))
    print('overall     %s' % ', '.join('%s %s' % kv for kv in sorted(T['overall'].items())))
    for k, why in T['parts'].items():
        print('  part error: %s: %s' % (k, why[:160]))
    if opt('--json'):
        json.dump(T, open(opt('--json'), 'w'), indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
