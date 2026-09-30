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
                   outfit's notes and the rig's files (until decision 8 also a gitignored TRELLIS field)
    "command":     how it is made, {spec} and {out} standing for the cut-down spec's file and the reference's folder

    python -m charkit refs-check SPEC        # every reference present, hashes matching, roles and authorities listed

A missing or stale one is first looked for in a shared cache (cache_root(): CHARKIT_PRODUCED_CACHE, default
~/.cache/charkit/produced, per user, so a box's gate clones and copies share it; `off` turns it off), keyed
RID/STAMP-CODE2: its stamp, and its producer's code two imports deep (code2(): deeper than the stamp, so a change two
imports down misses rather than restoring what older code made). An entry holds exactly the files its build wrote (a
before-and-after listing of the reference's folder: the hair layers share theirs with other outputs) with PATH.stamp and
PATH.stamp.json, each file's sha256 in its entry.json. A hit is copied back (never linked: builds rewrite outputs) and
checked against those sha256s on the way; a damaged or partial entry is a miss, and deleted. A store is atomic (a
folder renamed into place: the first of two racing builds wins), the newest CACHE_KEEP entries per reference are kept,
and each hit or miss prints a CHARKIT_PRODUCED line (the time saved or spent) and goes to the cache's events.jsonl.
"""
import copy, glob, hashlib, json, os, shutil, stat, time

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
    declares ('reads_spec': sections()) and the files it declares ('reads_files': read_files(); the outfit's notes and the
    rig's files). Nothing else of the spec: a body or face tune changes its knobs every step, and the
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


def _producer_code(r, depth=STAMP_DEPTH):
    """the code a produced reference depends on: its 'produced_fn' (module:function) with what it uses, else its
    'produced_by' module, `depth` imports deep (the stamp's: STAMP_DEPTH; the shared cache's key: CACHE_DEPTH)."""
    import importlib
    from . import cache
    fn = r.get('produced_fn')
    if fn:
        mod, name = fn.split(':')
        return cache.code_units(getattr(importlib.import_module(mod), name), depth=depth)
    return cache.code_units(modules=(r['produced_by'],), depth=depth)


# ------------------------------------------------------------------------------ the shared cache of produced references
CACHE_DEPTH = 2             # the key's code: two imports deep, one more than the stamp. A miss costs a rebuild (what a
                            # fresh copy pays today); a false hit would restore what older code made, so err to missing
CACHE_KEEP = 30             # entries kept per reference, newest (by last use) first; CHARKIT_PRODUCED_CACHE_KEEP
_TAG = 'CHARKIT_PRODUCED'   # the log lines' prefix, so a build's output can be searched for them


def cache_root():
    """the shared cache's folder: CHARKIT_PRODUCED_CACHE, default ~/.cache/charkit/produced (per user: gates and box
    copies run as one user, so a box's clones share it). None when it is 'off' (or 0, none, no)."""
    v = os.environ.get('CHARKIT_PRODUCED_CACHE', '').strip()
    if v.lower() in ('off', '0', 'none', 'no'):
        return None
    return os.path.abspath(os.path.expanduser(v or os.path.join('~', '.cache', 'charkit', 'produced')))


def code2(R, rid, _seen=None):
    """the part of a reference's cache key the stamp lacks: its producer's code CACHE_DEPTH imports deep, the code2 of
    each produced reference it reads (their outputs are its inputs: a hull restored under the outfit's stamp alone
    could be one made from other masks), and the Python, numpy and machine it runs on -> digest."""
    import platform, sys
    import numpy as np
    from . import cache
    seen = set() if _seen is None else _seen
    seen.add(rid)
    r = R[rid]
    reads = [[k, code2(R, k, seen)] for k in r.get('reads', ()) if k in R and R[k].get('produced_by') and k not in seen]
    env = [sys.version.split()[0], np.__version__, platform.machine(), platform.system()]
    return cache.digest([_producer_code(r, CACHE_DEPTH), reads, env])


def _listing(d):
    """every regular file under d -> {relative path: (size, mtime_ns, inode)}."""
    out = {}
    for top, _, fs in os.walk(d):
        for f in fs:
            full = os.path.join(top, f)
            try:
                st = os.lstat(full)
            except FileNotFoundError:
                continue
            if stat.S_ISREG(st.st_mode):
                out[os.path.relpath(full, d)] = (st.st_size, st.st_mtime_ns, st.st_ino)
    return out


def _written(before, after, p):
    """the files a build wrote into the reference's folder: new or changed between the listings, less produced()'s own
    (the lock, the cut-down spec, temporaries); the stamp and its parts added (they are written last) -> sorted [rel]."""
    name = os.path.basename(p)
    own = {name + '.lock', name + '.spec.json'}
    out = {k for k, v in after.items() if before.get(k) != v and os.path.basename(k) not in own
           and not k.endswith(('.tmp', '.lock'))}
    return sorted(out | {name + '.stamp', name + '.stamp.json'})


class _Damaged(Exception):
    """a cache entry that is partial or doesn't match its own sha256s."""


def _copy(src, dst):
    """src copied to a new file dst (never a link) -> its sha256. A missing or unreadable src is _Damaged."""
    h = hashlib.sha256()
    try:
        fi = open(src, 'rb')
    except OSError as e:
        raise _Damaged('%s: %s' % (os.path.basename(src), e.strerror))
    with fi, open(dst, 'wb') as fo:
        for b in iter(lambda: fi.read(1 << 20), b''):
            h.update(b)
            fo.write(b)
    return h.hexdigest()


def _safe_rel(rel):
    n = os.path.normpath(rel)
    return not os.path.isabs(n) and n != '..' and not n.startswith('..' + os.sep)


def _drop(path):
    """an entry out of the cache: renamed aside first (atomic: no reader sees it half deleted), then removed."""
    aside = '%s.del-%d' % (path, os.getpid())
    try:
        os.rename(path, aside)
    except OSError:
        return
    shutil.rmtree(aside, ignore_errors=True)


def _event(root, **kw):
    """one line in the cache's events.jsonl (hits, misses, stores: what a box's builds saved and spent)."""
    import socket
    kw = dict(t=time.strftime('%Y-%m-%dT%H:%M:%S'), host=socket.gethostname(), copy=ROOT, **kw)
    try:
        with open(os.path.join(root, 'events.jsonl'), 'a') as f:
            f.write(json.dumps(kw, sort_keys=True) + '\n')
    except OSError:
        pass


def _mb(n):
    return '%.1f MB' % (n / 1e6)


def cache_restore(root, rid, key, st, p):
    """the entry RID/KEY copied into the reference's folder, each file checked against its sha256 as it's copied and
    put in place only when all are (the stamp last: a restore cut short leaves the reference stale, not wrong)
    -> (the entry's record, 'hit'), or (None, why): no entry, a damaged one (then deleted), or this copy's disk failing."""
    e = os.path.join(root, rid, key)
    if not os.path.isdir(e):
        return None, 'no entry'
    d, name = os.path.dirname(p), os.path.basename(p)
    staged = []
    try:
        try:
            E = json.load(open(os.path.join(e, 'entry.json')))
        except (OSError, ValueError) as x:
            raise _Damaged('entry.json: %s' % x)
        files = E.get('files') or {}
        if E.get('key') != key or E.get('stamp') != st or name not in files or name + '.stamp' not in files:
            raise _Damaged('entry.json does not describe this key')
        if not all(_safe_rel(k) for k in files):
            raise _Damaged('a path outside the reference folder')
        for rel, (size, sha) in sorted(files.items()):
            src = os.path.join(e, 'files', rel)
            try:
                if os.path.getsize(src) != size:
                    raise _Damaged('%s: %d bytes, not %d' % (rel, os.path.getsize(src), size))
            except FileNotFoundError:
                raise _Damaged('%s: missing' % rel)
            dst = os.path.join(d, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            tmp = '%s.restore-%d.tmp' % (dst, os.getpid())
            staged.append((tmp, dst))
            if _copy(src, tmp) != sha:
                raise _Damaged('%s: sha256 differs' % rel)
    except _Damaged as x:
        for tmp, _ in staged:
            if os.path.exists(tmp):
                os.remove(tmp)
        _drop(e)
        return None, 'damaged (%s), deleted' % x
    except OSError as x:                                    # this copy's side (its disk), not the entry's
        for tmp, _ in staged:
            if os.path.exists(tmp):
                os.remove(tmp)
        return None, 'restore failed: %s' % x
    last = name + '.stamp'
    for tmp, dst in sorted(staged, key=lambda t: os.path.basename(t[1]) == last):
        os.replace(tmp, dst)
    try:
        os.utime(e)                                         # used: the prune keeps the most recently used
    except OSError:
        pass
    return E, 'hit'


def cache_store(root, rid, key, p, rels, **meta):
    """the files `rels` (relative to the reference's folder) stored as entry RID/KEY: copied into KEY.tmp-PID with an
    entry.json of their sizes and sha256s, then renamed into place. Where another build stored KEY first, this one is
    discarded -> 'stored', 'exists' (the other's kept) or 'skipped: why'."""
    from . import cache
    base = os.path.join(root, rid)
    final = os.path.join(base, key)
    if os.path.isdir(final):
        return 'exists'
    os.makedirs(base, exist_ok=True)
    if not cache.room(base):
        return 'skipped: under %s GB free' % os.environ.get('CHARKIT_CACHE_MIN_FREE_GB', 2)
    tmp = '%s.tmp-%d' % (final, os.getpid())
    shutil.rmtree(tmp, ignore_errors=True)
    d = os.path.dirname(p)
    try:
        files = {}
        for rel in rels:
            dst = os.path.join(tmp, 'files', rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            sha = _copy(os.path.join(d, rel), dst)
            files[rel] = [os.path.getsize(dst), sha]
        with open(os.path.join(tmp, 'entry.json'), 'w') as f:
            json.dump(dict(meta, rid=rid, key=key, files=files), f, indent=1, sort_keys=True)
    except (OSError, _Damaged) as x:
        shutil.rmtree(tmp, ignore_errors=True)
        return 'skipped: %s' % x
    try:
        os.rename(tmp, final)                   # atomic; fails when KEY exists (a directory with files in it)
    except OSError:
        shutil.rmtree(tmp, ignore_errors=True)
        return 'exists'
    return 'stored'


def cache_prune(root, rid, keep=None):
    """the newest `keep` entries of a reference kept (CACHE_KEEP, CHARKIT_PRODUCED_CACHE_KEEP), by last use; leftovers
    of stores or deletions cut short (an hour old) removed -> the number of entries removed."""
    keep = int(os.environ.get('CHARKIT_PRODUCED_CACHE_KEEP', CACHE_KEEP)) if keep is None else keep
    base = os.path.join(root, rid)
    try:
        names = os.listdir(base)
    except OSError:
        return 0
    now, es = time.time(), []
    for n in names:
        path = os.path.join(base, n)
        try:
            mt = os.path.getmtime(path)
        except OSError:
            continue
        if '.tmp-' in n or '.del-' in n:
            if now - mt > 3600:
                shutil.rmtree(path, ignore_errors=True)
        elif os.path.isdir(path):
            es.append((mt, path))
    es.sort(reverse=True)
    for _, path in es[keep:]:
        _drop(path)
    ev = os.path.join(root, 'events.jsonl')
    try:
        if os.path.getsize(ev) > 4 << 20:
            os.replace(ev, ev + '.1')
    except OSError:
        pass
    return max(0, len(es) - keep)


def produced(spec, rid, log=print):
    """a code-produced reference's path, built first if it is missing or stale: the visual hull by charkit.geom.hull's
    fast path, anything else by running its manifest 'command' from the repo root, each on this spec cut down to the
    sections it and what it reads declare (sections(spec_reads), written to PATH.spec.json: the command's {spec}).
    Stale: its stamp (PATH.stamp, from stamp()) differs, as when the producer's code changed after it was made (a
    merge), the spec's declared sections differ (another spec's garments), a declared file came or went, or it has
    none. One copy holds one version at a time: a spec that differs in those sections rebuilds it in
    place (charkit/out is a copy's own; the rebuild is under a lock, PATH.lock, so parallel builds in one copy build it
    once). Before building, the shared cache (cache_root(); the module's notes): a hit is restored, a build is stored.
    What it reads is produced first, so its build (and the time the cache records for it) is its own. None when the
    manifest has no such reference."""
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
    for k in r.get('reads', ()):
        if k != rid and (R.get(k) or {}).get('produced_by'):
            produced(spec, k, log)
    import fcntl
    d = os.path.dirname(p)
    os.makedirs(d, exist_ok=True)
    with open(p + '.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        was = have()
        if os.path.exists(p) and was == st:                      # another build in this copy made it meanwhile
            return p
        root = cache_root()
        log('%s: %s%s' % (rid, 'missing' if not os.path.exists(p) else 'stale (its producer or inputs changed)'
                          if was else 'unstamped (made before stamps, or by hand)', '' if root else ', building'))
        for g, hits in zip(r.get('reads_files', ()), parts['files']):
            log('%s: reads %s: %s' % (rid, g, ', '.join('%s (%s)' % (f, h[:8]) for f, h in hits) or 'none in this copy'))
        cut = sections(spec, spec_reads(R, rid))
        cut_path = p + '.spec.json'
        with open(cut_path + '.tmp', 'w') as f:
            json.dump(cut, f, indent=1, sort_keys=True)
        os.replace(cut_path + '.tmp', cut_path)
        key = why = None
        if root:
            t0 = time.time()
            key = '%s-%s' % (st, code2(R, rid))
            short = '%s-%s' % (st[:8], key.split('-')[1][:8])
            E, why = cache_restore(root, rid, key, st, p)
            if E:
                dt = time.time() - t0
                size = sum(v[0] for v in E['files'].values())
                built = E.get('seconds')
                log('%s %s: hit %s: %d files, %s restored in %.1f s%s' % (
                    _TAG, rid, short, len(E['files']), _mb(size), dt,
                    ' (its build took %.1f s: %.1f s saved)' % (built, built - dt) if built is not None else ''))
                _event(root, rid=rid, key=key, event='hit', seconds=round(dt, 2), built_seconds=built,
                       saved_seconds=round(built - dt, 1) if built is not None else None, files=len(E['files']),
                       bytes=size)
                return p
            log('%s %s: miss %s (%s), building' % (_TAG, rid, short, why))
        from . import cache
        n = cache.unshare(d)                    # rebuilt in place: never through a link into another worktree
        if n:
            log('%s: %d files were hard-linked to another worktree; unshared before rebuilding' % (rid, n))
        before = _listing(d) if root else None
        t0 = time.time()
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
        if not os.path.exists(p):               # a producer that ran without making it: never stamped, and the build
            raise RuntimeError('%s: its producer (%s) ran but made no %s; the build stops rather than going on '
                               'without it' % (rid, r['produced_by'], r['path']))
        dt = time.time() - t0
        with open(sp + '.json.tmp', 'w') as f:
            json.dump(dict(parts, stamp=st), f, indent=1, sort_keys=True)
        os.replace(sp + '.json.tmp', sp + '.json')
        with open(sp + '.tmp', 'w') as f:
            f.write(st + '\n')
        os.replace(sp + '.tmp', sp)
        if root and os.path.exists(p):
            rels = _written(before, _listing(d), p)
            size = sum(os.path.getsize(os.path.join(d, x)) for x in rels)
            res = cache_store(root, rid, key, p, rels, stamp=st, code2=key.split('-')[1], seconds=round(dt, 1),
                              stored=time.strftime('%Y-%m-%dT%H:%M:%S'), copy=ROOT)
            gone = cache_prune(root, rid)
            log('%s %s: built in %.1f s; %s %s: %d files, %s%s' % (
                _TAG, rid, dt, res, short, len(rels), _mb(size), '; pruned %d' % gone if gone else ''))
            _event(root, rid=rid, key=key, event='miss', why=why, seconds=round(dt, 1), store=res, files=len(rels),
                   bytes=size)
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
