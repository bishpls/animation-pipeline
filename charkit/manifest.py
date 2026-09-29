"""A character's references in one place: charkit/refs/NAME/manifest.json lists every picture, rig and generated asset
the build, the fit and the QA read, with what each is for, how it is scaled, where it came from, and which reference is
the authority for which measurement (so when two disagree, say the 2D design and the 3D rebuild, the choice is written
down, not implied by whichever file a module happens to open).

    {"name": "clawd",
     "references": {KEY: {"kind", "path", "role", "tracked", "sha256"?, "scale"?, "figures"?, "provenance"?, "cautions"?}},
     "authority": {MEASURE: KEY}}

A spec points at it with ref.manifest; `resolve()` fills the spec's ref (rig, image, sheet) from it and turns a
"ref:KEY" path anywhere in the spec into that reference's path, so the rest of the kit reads the spec as before.

    python -m charkit refs-check SPEC        # every reference present, hashes matching, roles and authorities listed
"""
import hashlib, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _p(path):
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


def load(path):
    M = json.load(open(_p(path)))
    M['_path'] = path
    return M


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(_p(path), 'rb') as f:
        for b in iter(lambda: f.read(chunk), b''):
            h.update(b)
    return h.hexdigest()


def resolve(spec):
    """a spec with ref.manifest -> the spec with ref.rig / ref.image / ref.sheet filled from the manifest (the spec's own
    values win) and every "ref:KEY" string replaced by that reference's path. Specs without a manifest pass through."""
    ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else None
    if not ref or not ref.get('manifest'):
        return spec
    M = load(ref['manifest'])
    R = M['references']
    fill = {'rig': 'rig', 'image': 'key3d'}
    for k, key in fill.items():
        if k not in ref and key in R:
            ref[k] = R[key]['path']
    if 'sheet' not in ref and 'sheet' in R:
        s = R['sheet']
        ref['sheet'] = dict(image=s['path'], **s.get('figures', {}))
    # the generated sheets that fill the design's 'sheet' role, per kind (face, eyes, body): the QA and the fits read them
    # (qa3d.Design, bodymeasure.Sheet); the model sheet above is then the source design, measured by nothing but refs.fit
    for kind, rid in (M.get('sheets') or {}).items():
        key = kind + '_sheet'
        if key not in ref and rid in R:
            ref[key] = dict(id=rid, image=R[rid]['path'], layout=R[rid].get('layout'), facing=-1)
    ref['authority'] = M.get('authority', {})

    def sub(x):
        if isinstance(x, str) and x.startswith('ref:'):
            return R[x[4:]]['path']
        if isinstance(x, dict):
            return {k: sub(v) for k, v in x.items()}
        if isinstance(x, list):
            return [sub(v) for v in x]
        return x
    for k in list(spec):
        if k != 'ref':
            spec[k] = sub(spec[k])
    return spec


def produce(spec):
    """the references the manifest says code produces ('produced_by'), built where the resolved spec uses them and they
    are missing or stale (produced()): they live in gitignored outputs, so a fresh worktree (the merge gate's) has none,
    and a merge can change the code that made an existing one. The visual hull
    (charkit.geom.hull) takes its fast path: no leave-one-out sweep, no page. -> spec."""
    ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else None
    if not ref or not ref.get('manifest'):
        return spec
    R = load(ref['manifest'])['references']
    text = json.dumps({k: v for k, v in spec.items() if k != 'ref'})
    for rid, r in R.items():
        if r.get('produced_by') and r['path'] in text:
            produced(spec, rid)
    return spec


def stamp(spec, r):
    """what a produced reference depends on, as a digest: its producer's code (_producer_code: its function and what it
    imports, one import deep), the manifest's tracked references (their sha256s), the stamps of the produced
    references it reads (its 'reads': the hull reads the outfit's masks), the spec's ref and style. Not the spec's knobs:
    a tune changes those every step, and the references don't read them."""
    from . import cache
    M = load(spec['ref']['manifest'])
    R = M['references']
    refs = {k: v.get('sha256') for k, v in sorted(R.items()) if v.get('sha256')}
    reads = [stamp(spec, R[k]) for k in r.get('reads', ()) if k in R and R[k].get('produced_by')]
    return cache.digest([_producer_code(r), refs, reads, spec['ref'].get('manifest'), spec.get('style')])


STAMP_DEPTH = 1             # the producer's code one import deep: its own module's functions it runs and the modules
                            # they import, not theirs in turn (those reach all of charkit, so any edit anywhere would
                            # rebuild the hull: 2-3 minutes a build in every worktree)


def _producer_code(r):
    """the code a produced reference depends on: its 'produced_fn' (module:function) with what it uses, else its
    'produced_by' module, one import deep (STAMP_DEPTH)."""
    import importlib
    from . import cache
    fn = r.get('produced_fn')
    if fn:
        mod, name = fn.split(':')
        return cache.code_units(getattr(importlib.import_module(mod), name), depth=STAMP_DEPTH)
    return cache.code_units(modules=(r['produced_by'],), depth=STAMP_DEPTH)


def produced(spec, rid, log=print):
    """a code-produced reference's path, built first if it is missing or stale: the visual hull by charkit.geom.hull's
    fast path, anything else by running its manifest 'command' from the repo root. Stale: its stamp (PATH.stamp, from
    stamp()) differs, as when the producer's code changed after it was made (a merge), or it has none. None when the
    manifest has no such reference."""
    ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else None
    if not ref or not ref.get('manifest'):
        return None
    r = load(ref['manifest'])['references'].get(rid)
    if not r:
        return None
    p = _p(r['path'])
    if not r.get('produced_by'):
        return p
    st = stamp(spec, r)
    sp = p + '.stamp'
    have = open(sp).read().strip() if os.path.exists(sp) else None
    if os.path.exists(p) and have == st:
        return p
    log('%s: %s, building' % (rid, 'missing' if not os.path.exists(p) else 'stale (its producer or inputs changed)'
                              if have else 'unstamped (made before stamps, or by hand)'))
    if r['produced_by'] == 'charkit.geom.hull':
        from .geom import hull
        hull.build(spec, os.path.dirname(p), validate_views=False, page=False)
    else:
        import shlex, subprocess, sys
        args = shlex.split(r['command'])
        if args[0].startswith('python'):
            args[0] = sys.executable
        log('%s: %s' % (rid, r['command']))
        subprocess.run(args, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    with open(sp + '.tmp', 'w') as f:
        f.write(st + '\n')
    os.replace(sp + '.tmp', sp)
    return p


def check(path):
    """-> list of (key, status, detail): present, hash matching for untracked files, the cautions."""
    M = load(path)
    out = []
    for key, r in M['references'].items():
        p = _p(r['path'])
        if not os.path.exists(p):
            out.append((key, 'MISSING', r['path'] + ('  (regenerate: %s)' % r['provenance'].get('command') if r.get('provenance', {}).get('command') else '')))
            continue
        if r.get('sha256') and os.path.isfile(p):
            ok = sha256(r['path']) == r['sha256']
            out.append((key, 'ok' if ok else 'CHANGED', r['path'] if ok else '%s: the hash differs from the manifest' % r['path']))
        else:
            out.append((key, 'ok', r['path']))
        for c in r.get('cautions', []):
            out.append((key, 'caution', c))
    for m, key in M.get('authority', {}).items():
        if key not in M['references']:
            out.append((m, 'BAD', 'authority names an unknown reference: %s' % key))
    return out


def main(args):
    spec = json.load(open(_p(args[0])))
    mp = (spec.get('ref') or {}).get('manifest')
    if not mp:
        raise SystemExit('the spec has no ref.manifest')
    rows = check(mp)
    for key, st, d in rows:
        print('%-10s %-8s %s' % (key, st, d))
    M = load(mp)
    print('\nauthority:')
    for m, key in M.get('authority', {}).items():
        print('  %-18s %s' % (m, key))
    if any(st in ('MISSING', 'CHANGED', 'BAD') for _, st, _ in rows):
        raise SystemExit(1)
