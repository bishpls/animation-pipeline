"""The build cache on real builds of Clawd (charkit/spec/clawd.json), in a throwaway copy of the checkout with its own
cache: what each change restores and runs, the times, and the proofs (trace diffs and qa.json against a fresh build).
Blender and minutes per build: a script that prints its results, not a unit test (charkit/tests/test_cache.py is).

    ~/animation-pipeline/.venv/bin/python charkit/tests/cache_builds.py [--boards views] [--keep] [--only NAME,...]

Builds (each into its own out folder; `fresh` ones with --cache off):
  cold         everything runs and is stored                 warm      no change: everything restored
  stages       the stages restored, boards and QA run on the restored scene (qa.json must equal the fresh build's)
  eyes         eyes.width: character, hair, face shading run; garments restored
  head         head.width: garments run too (the head wrap drags the neck and shoulder joints the outfit hangs from)
  outfit       a garment's colour: character, hair, face shading restored; garments run; in the QA the parts that
               don't look at the clothes (eyes, face, expressions, the sheet's figures) restored
  glb          the TRELLIS GLB swapped for another's content at the same path: the fit and the hair run
  code         a code edit in garments.py: garments (and the products) run; a comment-only edit: nothing runs
  verify       eyes.width again with --cache verify: every stage runs and is compared with the entry a lookup would take
The changed builds are each diffed against a fresh build of the same spec: `no differences` (stage times left out).
"""
import json, os, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PY = sys.executable


def copy_checkout(dst):
    """the kit's sources into dst (a throwaway root), the generated inputs and the references linked, not copied."""
    shutil.copytree(os.path.join(REPO, 'charkit'), os.path.join(dst, 'charkit'),
                    ignore=shutil.ignore_patterns('out', '__pycache__'))
    os.makedirs(os.path.join(dst, 'charkit', 'out'))
    os.symlink(os.path.join(REPO, 'charkit', 'out', 'i3d'), os.path.join(dst, 'charkit', 'out', 'i3d'))
    os.symlink(os.path.join(REPO, 'projects'), os.path.join(dst, 'projects'))


def build(root, spec, out, *args, env=None):
    t = time.time()
    r = subprocess.run([PY, '-m', 'charkit', 'build', spec, '--out', out, '--no-worker'] + list(args), cwd=root,
                       capture_output=True, text=True, env=env)
    dt = time.time() - t
    if r.returncode:
        raise SystemExit('build %s failed:\n%s' % (out, (r.stdout + r.stderr)[-3000:]))
    recs = [json.loads(l) for l in open(os.path.join(out, 'trace.jsonl'))]
    steps = {r_['name']: r_['cache'] for r_ in recs if r_.get('cache') and r_['event'] in ('stage', 'span', 'product',
                                                                                           'part')}
    return dict(seconds=round(dt, 1), blender=next((r_['total'] for r_ in recs if r_['event'] == 'end'), None), steps=steps,
                stdout=r.stdout)


def diff(root, a, b):
    r = subprocess.run([PY, '-m', 'charkit', 'trace', os.path.join(a, 'trace.jsonl'), os.path.join(b, 'trace.jsonl'),
                        '--no-time'], cwd=root, capture_output=True, text=True)
    return r.stdout.strip()


def qa_same(a, b):
    qa = [json.load(open(os.path.join(d, 'qa', 'qa.json'))) for d in (a, b)]
    va, vb = ({k: (c.get('value'), c.get('status')) for k, c in q['checks'].items()} for q in qa)
    return va == vb, sorted(k for k in set(va) | set(vb) if va.get(k) != vb.get(k))


def ran(res):
    return sorted(k for k, c in res['steps'].items() if not c.get('hit'))


def restored(res):
    return sorted(k for k, c in res['steps'].items() if c.get('hit'))


def show(name, res):
    print('%-8s %6.1fs (Blender %6.1fs)  restored: %s' % (name, res['seconds'], res['blender'] or 0,
                                                       ', '.join(restored(res)) or '-'))
    for k in ran(res):
        print('%-8s          ran %-13s %s' % ('', k, res['steps'][k].get('why', '')))


def variant(root, name, fn):
    src = os.path.join(root, 'charkit', 'spec', 'clawd.json')
    s = json.load(open(src))
    fn(s)
    p = os.path.join(root, 'charkit', 'spec', 'clawd_%s.json' % name)
    json.dump(s, open(p, 'w'), indent=1)
    return p


def main(args):
    boards = args[args.index('--boards') + 1] if '--boards' in args else 'views'
    only = set(args[args.index('--only') + 1].split(',')) if '--only' in args else None
    root = tempfile.mkdtemp(prefix='charkit-cache-')
    copy_checkout(root)
    env = dict(os.environ, CHARKIT_CACHE_DIR=os.path.join(root, 'charkit', 'out', '.cache'))
    out = lambda n: os.path.join(root, 'charkit', 'out', n)
    spec = os.path.join(root, 'charkit', 'spec', 'clawd.json')
    B = ['--boards', boards, '--no-blend']
    fails = []

    def check(ok, what):
        print(('  ok    ' if ok else '  FAIL  ') + what)
        if not ok:
            fails.append(what)

    def want(name):
        return only is None or name in only
    R = {}
    print('checkout copy %s, cache %s, boards %s' % (root, env['CHARKIT_CACHE_DIR'], boards))
    R['fresh'] = build(root, spec, out('fresh'), *B, '--cache', 'off', env=env); show('fresh', R['fresh'])
    R['cold'] = build(root, spec, out('cold'), *B, env=env); show('cold', R['cold'])
    check(not restored(R['cold']), 'cold: nothing restored')
    R['warm'] = build(root, spec, out('warm'), *B, env=env); show('warm', R['warm'])
    check(not ran(R['warm']), 'warm: everything restored')
    check(R['cold']['seconds'] >= 3 * R['warm']['seconds'], 'warm is %.1fx faster than cold (wall clock)' %
          (R['cold']['seconds'] / R['warm']['seconds']))
    for n in ('cold', 'warm'):
        check(diff(root, out('fresh'), out(n)) == 'no differences', '%s: trace diff against fresh: no differences' % n)
        same, which = qa_same(out('fresh'), out(n))
        check(same, '%s: qa.json values identical to fresh%s' % (n, '' if same else ': ' + ', '.join(which)))
    if want('stages'):
        R['stages'] = build(root, spec, out('stages'), *B, '--cache', 'stages', env=env); show('stages', R['stages'])
        check({'boards', 'qa'} <= set(ran(R['stages'])) and not {'fit_cranium', 'character', 'hair', 'face_shading',
                                                                  'garments'} & set(ran(R['stages'])),
              'stages: the stages restored, boards and QA run')
        same, which = qa_same(out('fresh'), out('stages'))
        check(same, 'stages: QA run on the restored scene equals the fresh build\'s%s' % ('' if same else ': ' + str(which)))
        check(diff(root, out('fresh'), out('stages')) == 'no differences', 'stages: trace diff: no differences')

    def changed(name, fn, expect_ran, expect_restored, *extra):
        p = variant(root, name, fn) if fn else spec
        r = build(root, p, out(name), *B, *extra, env=env); show(name, r)
        f = build(root, p, out(name + '_fresh'), *B, '--cache', 'off', env=env)
        st = {'fit_cranium', 'character', 'hair', 'face_shading', 'garments'}
        check(set(ran(r)) & st == set(expect_ran), '%s: ran %s' % (name, ', '.join(sorted(expect_ran)) or 'no stage'))
        check(set(restored(r)) & st == set(expect_restored), '%s: restored %s' % (name, ', '.join(sorted(expect_restored))))
        d = diff(root, out(name + '_fresh'), out(name))
        check(d == 'no differences', '%s: trace diff against its fresh build: %s' % (name, d if len(d) < 300 else d[:300]))
        same, which = qa_same(out(name + '_fresh'), out(name))
        check(same, '%s: qa.json identical to its fresh build%s' % (name, '' if same else ': ' + ', '.join(which)))
        R[name] = r
        return r
    if want('eyes'):
        changed('eyes', lambda s: s['eyes'].__setitem__('width', 0.22), {'character', 'hair', 'face_shading'},
                {'fit_cranium', 'garments'})
    if want('head'):
        r = changed('head', lambda s: s['head'].__setitem__('width', 1.1), {'character', 'hair', 'face_shading', 'garments'},
                    {'fit_cranium'})
        print('          head: garments ran because: %s' % r['steps']['garments'].get('why'))
    if want('outfit'):
        def outfit(s):
            next(g for g in s['garments'] if g['name'] == 'skirt')['color'] = [0.7, 0.3, 0.5]
        r = changed('outfit', outfit, {'garments'}, {'fit_cranium', 'character', 'hair', 'face_shading'})
        parts = {'eyes', 'face', 'sheet_expr', 'sheet_figures'}
        check(parts <= set(restored(r)), 'outfit: QA parts that don\'t read the clothes restored (%s)' %
              ', '.join(sorted(set(restored(r)) - {'fit_cranium', 'character', 'hair', 'face_shading'})))
    if want('glb'):
        # the same path, other content: the build reads the GLB by path, so only its content can tell
        glb = os.path.join(root, 'glb', 'clawd.glb')
        os.makedirs(os.path.dirname(glb))
        shutil.copyfile(os.path.join(REPO, 'charkit', 'out', 'i3d', 'clawd', 'clawd_3dstyle_s1.glb'), glb)

        def to_copy(s):
            s['hair']['shape']['glb'] = glb
        p = variant(root, 'glb', to_copy)
        a = build(root, p, out('glb_a'), *B, env=env); show('glb_a', a)
        b = build(root, p, out('glb_b'), *B, env=env); show('glb_b', b)
        check(not ran(b), 'glb: a second build with the copy restores everything')
        shutil.copyfile(os.path.join(REPO, 'charkit', 'out', 'i3d', 'clawd', 'clawd_3dstyle_s2.glb'), glb)
        c = build(root, p, out('glb'), *B, env=env); show('glb', c)
        f = build(root, p, out('glb_fresh'), *B, '--cache', 'off', env=env)
        check({'fit_cranium', 'hair'} <= set(ran(c)) and 'file ' in c['steps']['hair'].get('why', ''),
              'glb: fit and hair ran on the changed file (%s)' % c['steps']['hair'].get('why'))
        check(diff(root, out('glb_fresh'), out('glb')) == 'no differences', 'glb: trace diff against fresh: no differences')
    if want('code'):
        g = os.path.join(root, 'charkit', 'garments.py')
        src = open(g).read()
        open(g, 'w').write(src.replace('"""Garments', '# a comment-only edit\n"""Garments', 1))
        r = build(root, spec, out('comment'), *B, env=env); show('comment', r)
        check(not ran(r), 'code: a comment-only edit to garments.py restores everything')
        open(g, 'w').write(src.replace("sol.thickness = 0.01 * L", "sol.thickness = 0.012 * L", 1))
        r = build(root, spec, out('code'), *B, env=env); show('code', r)
        f = build(root, spec, out('code_fresh'), *B, '--cache', 'off', env=env)
        st = {'fit_cranium', 'character', 'hair', 'face_shading', 'garments'}
        check(set(ran(r)) & st == {'garments'} and 'garments.py' in r['steps']['garments'].get('why', ''),
              'code: a skirt edit in garments.py runs garments only (%s)' % r['steps']['garments'].get('why'))
        check(diff(root, out('code_fresh'), out('code')) == 'no differences', 'code: trace diff against fresh: no differences')
        same, which = qa_same(out('code_fresh'), out('code'))
        check(same, 'code: qa.json identical to its fresh build')
        open(g, 'w').write(src)
    if want('verify'):
        p = variant(root, 'eyes', lambda s: s['eyes'].__setitem__('width', 0.22))
        r = build(root, p, out('verify'), *B, '--cache', 'verify', env=env); show('verify', r)
        stale = [l for l in r['stdout'].splitlines() if l.startswith('CHARKIT_CACHE_STALE')]
        check(not stale, 'verify: every stage and product equals the entry a lookup took%s' % ('' if not stale else
                                                                                               ': ' + '; '.join(stale)))
        check(all(c.get('verified') for c in r['steps'].values() if 'verified' in c), 'verify: all verified')
    print('\ntimes (wall clock, s):', json.dumps({k: v['seconds'] for k, v in R.items()}))
    print('%d checks failed' % len(fails) if fails else 'all checks passed')
    if '--keep' not in args:
        shutil.rmtree(root, ignore_errors=True)
    else:
        print('kept', root)
    return not fails


if __name__ == '__main__':
    sys.exit(0 if main(sys.argv[1:]) else 1)
