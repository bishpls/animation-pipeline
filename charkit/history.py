"""QA over time: every build appends its checks to charkit/out/history/NAME.jsonl (git commit, spec hash, base, the out
folder, each check's value and status), so a check's trend across builds and merges is one command away.

    python -m charkit history NAME                    # the latest builds, one line per build with its failing checks
    python -m charkit history NAME --check eye_aspect # one check across builds
"""
import json, os, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, 'charkit', 'out', 'history')


def append(out, name, note=None):
    """record a finished build's QA (out/qa/qa.json) and its trace header."""
    qp = os.path.join(out, 'qa', 'qa.json')
    if not os.path.exists(qp):
        return None
    qa = json.load(open(qp))
    begin = {}
    tp = os.path.join(out, 'trace.jsonl')
    if os.path.exists(tp):
        for line in open(tp):
            rec = json.loads(line)
            if rec.get('event') == 'begin':
                begin = rec
                break
    spec = {}
    sp = os.path.join(out, name + '.spec.json')
    if os.path.exists(sp):
        spec = json.load(open(sp))
    row = {'t': time.strftime('%Y-%m-%dT%H:%M:%S'), 'git': begin.get('git'), 'spec_hash': begin.get('spec_hash'),
           'base': spec.get('base', 'makehuman'), 'out': os.path.relpath(out, ROOT), 'summary': qa.get('summary'),
           'checks': {k: [c.get('value'), c.get('status')] for k, c in qa.get('checks', {}).items()
                      if c.get('status') in ('PASS', 'WARN', 'FAIL', 'INFO')}}
    if note:
        row['note'] = note
    os.makedirs(DIR, exist_ok=True)
    with open(os.path.join(DIR, name + '.jsonl'), 'a') as f:
        f.write(json.dumps(row, default=float) + '\n')
    return row


def read(name):
    p = os.path.join(DIR, name + '.jsonl')
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


def main(args):
    if not args:
        print(__doc__); return
    rows = read(args[0])
    if '--check' in args:
        k = args[args.index('--check') + 1]
        for r in rows:
            v = r['checks'].get(k)
            if v:
                print('%s  %-16s %-10s %-10s %s' % (r['t'], r['git'], r['base'], v[1], v[0]))
        return
    for r in rows[-int(args[args.index('--last') + 1]) if '--last' in args else -20:]:
        fails = [k for k, v in r['checks'].items() if v[1] == 'FAIL']
        print('%s  %-16s %-10s %-5s fail %2d: %s' % (r['t'], r['git'], r['base'], r['summary'], len(fails), ', '.join(fails)))
