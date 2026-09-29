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
    are missing: they live in gitignored outputs, so a fresh worktree (the merge gate's) has none. The visual hull
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


def produced(spec, rid, log=print):
    """a code-produced reference's path, built first if it is missing: the visual hull by charkit.geom.hull's fast path,
    anything else by running its manifest 'command' from the repo root. None when the manifest has no such reference."""
    ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else None
    if not ref or not ref.get('manifest'):
        return None
    r = load(ref['manifest'])['references'].get(rid)
    if not r:
        return None
    p = _p(r['path'])
    if os.path.exists(p) or not r.get('produced_by'):
        return p
    if r['produced_by'] == 'charkit.geom.hull':
        from .geom import hull
        hull.build(spec, os.path.dirname(p), validate_views=False, page=False)
    else:
        import shlex, subprocess, sys
        args = shlex.split(r['command'])
        if args[0].startswith('python'):
            args[0] = sys.executable
        log('%s: missing, building: %s' % (rid, r['command']))
        subprocess.run(args, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
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
