"""A character's references in one place: charkit/refs/NAME/manifest.json lists every picture, rig and generated asset
the build, the fit and the QA read, with what each is for, how it is scaled, where it came from, and which reference is
the authority for which measurement (so when two disagree, say the 2D design and the 3D rebuild, the choice is written
down, not implied by whichever file a module happens to open).

    {"name": "clawd",
     "references": {KEY: {"kind", "path", "role", "tracked", "sha256"?, "scale"?, "figures"?, "provenance"?, "cautions"?}},
     "authority": {MEASURE: KEY}}

A spec points at it with ref.manifest; `resolve()` fills the spec's ref (rig, image, sheet) from it and turns a
"ref:KEY" path anywhere in the spec into that reference's path, so the rest of the kit reads the spec as before.

A reference code makes ('produced_by': the hull, the outfit's masks, the hair layers) also says what it is made from,
and its stamp (stamp()) covers exactly that, so two copies holding one stamp hold the same bytes:
    "reads":       the references it reads (a produced one by its stamp, another by its entry: hash, scale, views)
    "reads_spec":  the spec sections it reads, as paths: "eyes.x", "ref", "garments[].{name,kind}" (of each garment,
                   those members), "garments[].region[].0" (of each region entry, its first item). The producer runs on
                   the build's own spec cut down to these (with those of the produced references it reads), so what it
                   doesn't declare it can't read, and a knob outside them (a body or face tune) doesn't rebuild it
    "reads_files": files it reads that no reference hashes (globs; each match by its sha256, none if absent): the
                   outfit's notes, and its TRELLIS field, gitignored, which some copies have and some don't
    "command":     how it is made, {spec} and {out} standing for the cut-down spec's file and the reference's folder

    python -m charkit refs-check SPEC        # every reference present, hashes matching, roles and authorities listed
"""
import copy, glob, hashlib, json, os

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
    are missing or stale (produced()), each from this spec (its declared sections, 'reads_spec'), not the default
    spec's: they live in gitignored outputs, so a fresh worktree (the merge gate's) has none, a merge can change the
    code that made an existing one, and a spec with other garments makes another outfit graph. The visual hull
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


# ------------------------------------------------------------------------------------------ what a producer reads
READS_SPEC = ('name', 'ref', 'style')       # an entry that declares no 'reads_spec': what stamps covered before
_NONE = object()


def _segments(path):
    """'garments[].{name,kind}' -> ['garments[]', '{name,kind}']: split on dots outside braces."""
    out, cur, depth = [], '', 0
    for ch in path:
        depth += (ch == '{') - (ch == '}')
        if ch == '.' and not depth:
            out.append(cur); cur = ''
        else:
            cur += ch
    return out + [cur]


def _keep(x, segs):
    """what a section path keeps of x, in x's own shape (so the producer reads the cut-down spec as it reads the whole):
    KEY keeps that member of a dict, an integer that item of a list (at its place), KEY[] maps the rest of the path
    over the list x[KEY], {a,b} keeps those members. -> the kept value, or _NONE where the spec has no such member."""
    if not segs:
        return copy.deepcopy(x)
    s, rest = segs[0], segs[1:]
    if s.startswith('{') and s.endswith('}'):
        if not isinstance(x, dict):
            return _NONE
        out = {}
        for k in (k.strip() for k in s[1:-1].split(',')):
            v = _keep(x[k], rest) if k in x else _NONE
            if v is not _NONE:
                out[k] = v
        return out
    if s.isdigit():
        i = int(s)
        if not isinstance(x, list) or i >= len(x):
            return _NONE
        v = _keep(x[i], rest)
        return _NONE if v is _NONE else [None] * i + [v]
    each = s.endswith('[]')
    k = s[:-2] if each else s
    if not isinstance(x, dict) or k not in x:
        return _NONE
    if not each:
        v = _keep(x[k], rest)
        return _NONE if v is _NONE else {k: v}
    if not isinstance(x[k], list):
        return _NONE
    return {k: [None if v is _NONE else v for v in (_keep(e, rest) for e in x[k])]}


def _merge(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for k, v in b.items():
            out[k] = _merge(out[k], v) if k in out else v
        return out
    if isinstance(a, list) and isinstance(b, list):
        n = max(len(a), len(b))
        a, b = a + [None] * (n - len(a)), b + [None] * (n - len(b))
        return [y if x is None else x if y is None else _merge(x, y) for x, y in zip(a, b)]
    return b


def sections(spec, paths):
    """the spec cut down to the section paths (see the module; 'reads_spec'), keys sorted -> dict."""
    out = {}
    for p in paths:
        v = _keep(spec, _segments(p))
        if v is not _NONE:
            out = _merge(out, v)
    return json.loads(json.dumps(out, sort_keys=True))


def spec_reads(R, rid, _seen=None):
    """the section paths a produced reference reads: its own 'reads_spec' and, through its 'reads', those of the produced
    references it reads (the hull builds the outfit's masks from the spec it is given) -> [path]."""
    seen = set() if _seen is None else _seen
    seen.add(rid)
    r = R[rid]
    out = list(r.get('reads_spec', READS_SPEC))
    for k in r.get('reads', ()):
        if k in R and R[k].get('produced_by') and k not in seen:
            out += spec_reads(R, k, seen)
    return list(dict.fromkeys(out))


_SHA = {}                                   # a file's sha256 by (path, inode, size, mtime): the field is 17 MB


def _file_sha(path):
    st = os.stat(path)
    key = (path, st.st_ino, st.st_size, st.st_mtime_ns)
    if key not in _SHA:
        _SHA[key] = sha256(path)
    return _SHA[key]


def read_files(r):
    """a produced reference's 'reads_files' as they are in this copy: per glob, its matches (sorted) with their sha256s,
    [] where none -> [[[path, sha256], ...], ...]."""
    return [[[os.path.relpath(f, ROOT), _file_sha(f)] for f in sorted(glob.glob(_p(g))) if os.path.isfile(f)]
            for g in r.get('reads_files', ())]


PROSE = ('role', 'cautions', 'provenance', 'checks', 'notes')      # a manifest entry's words and records, not its data


def entry(e):
    """a manifest entry's data (its path, hash, scale, layout, views, a produced one's command and declarations), as the
    stamp takes it: without its prose (PROSE), which no producer reads."""
    return {k: v for k, v in sorted(e.items()) if k not in PROSE}


def stamp(spec, r, parts=False):
    """what a produced reference is made from, as a digest: its producer's code (_producer_code: its function and what it
    imports, one import deep), its own entry (entry(): its command and declarations), the manifest's tracked references
    (their sha256s), what it reads ('reads': a produced reference by its stamp, the hull reading the outfit's masks;
    another by its entry, so its scale, layout or views' bands count, not only its picture), the spec sections it
    declares ('reads_spec': sections()) and the files it declares ('reads_files': read_files(); the outfit's gitignored
    TRELLIS field above all). Nothing else of the spec: a body or face tune changes its knobs every step, and the
    references don't read them. parts: -> (digest, {part: value}), the parts as written beside the reference
    (PATH.stamp.json), so two copies' stamps can be told apart."""
    from . import cache
    M = load(spec['ref']['manifest'])
    R = M['references']
    refs = {k: v.get('sha256') for k, v in sorted(R.items()) if v.get('sha256')}
    rk = [k for k in r.get('reads', ()) if k in R]
    reads = [stamp(spec, R[k]) if R[k].get('produced_by') else entry(R[k]) for k in rk]
    code = _producer_code(r)
    sec = sections(spec, r.get('reads_spec', READS_SPEC))
    files = read_files(r)
    st = cache.digest([code, entry(r), refs, reads, sec, files])
    if not parts:
        return st
    return st, {'code': cache.digest(code), 'entry': cache.digest(entry(r)), 'refs': cache.digest(refs),
                'reads': {k: v if isinstance(v, str) else cache.digest(v) for k, v in zip(rk, reads)},
                'spec': cache.digest(sec), 'files': files}


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
    fast path, anything else by running its manifest 'command' from the repo root, each on this spec cut down to the
    sections it and what it reads declare (sections(spec_reads), written to PATH.spec.json: the command's {spec}).
    Stale: its stamp (PATH.stamp, from stamp()) differs, as when the producer's code changed after it was made (a
    merge), the spec's declared sections differ (another spec's garments), a declared file came or went (the TRELLIS
    field), or it has none. One copy holds one version at a time: a spec that differs in those sections rebuilds it in
    place (charkit/out is a copy's own; the rebuild is under a lock, PATH.lock, so parallel builds in one copy build it
    once). None when the manifest has no such reference."""
    ref = spec.get('ref') if isinstance(spec.get('ref'), dict) else None
    if not ref or not ref.get('manifest'):
        return None
    R = load(ref['manifest'])['references']
    r = R.get(rid)
    if not r:
        return None
    p = _p(r['path'])
    if not r.get('produced_by'):
        return p
    sp = p + '.stamp'
    have = lambda: open(sp).read().strip() if os.path.exists(sp) else None
    st, parts = stamp(spec, r, parts=True)
    if os.path.exists(p) and have() == st:
        return p
    import fcntl
    d = os.path.dirname(p)
    os.makedirs(d, exist_ok=True)
    with open(p + '.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        was = have()
        if os.path.exists(p) and was == st:                      # another build in this copy made it meanwhile
            return p
        log('%s: %s, building' % (rid, 'missing' if not os.path.exists(p) else 'stale (its producer or inputs changed)'
                                  if was else 'unstamped (made before stamps, or by hand)'))
        for g, hits in zip(r.get('reads_files', ()), parts['files']):
            log('%s: reads %s: %s' % (rid, g, ', '.join('%s (%s)' % (f, h[:8]) for f, h in hits) or 'none in this copy'))
        from . import cache
        n = cache.unshare(d)                    # rebuilt in place: never through a link into another worktree
        if n:
            log('%s: %d files were hard-linked to another worktree; unshared before rebuilding' % (rid, n))
        cut = sections(spec, spec_reads(R, rid))
        cut_path = p + '.spec.json'
        with open(cut_path + '.tmp', 'w') as f:
            json.dump(cut, f, indent=1, sort_keys=True)
        os.replace(cut_path + '.tmp', cut_path)
        if r['produced_by'] == 'charkit.geom.hull':
            from .geom import hull
            hull.build(json.loads(json.dumps(cut)), d, validate_views=False, page=False)
        else:
            import shlex, subprocess, sys
            rel = lambda x: os.path.relpath(x, ROOT) if x.startswith(ROOT + os.sep) else x
            cmd = r['command'].replace('{spec}', rel(cut_path)).replace('{out}', rel(d))
            args = shlex.split(cmd)
            if args[0].startswith('python'):
                args[0] = sys.executable
            log('%s: %s' % (rid, cmd))
            subprocess.run(args, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        with open(sp + '.json.tmp', 'w') as f:
            json.dump(dict(parts, stamp=st), f, indent=1, sort_keys=True)
        os.replace(sp + '.json.tmp', sp + '.json')
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
