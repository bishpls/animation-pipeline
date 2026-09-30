"""Code compared between two trees at the level of definitions, with the build cache's code walk (charkit.cache.code_units:
functions, classes and each module's top-level statements, followed as Python scopes names). Two uses in the merge gate
(charkit/gate.py):

  measure_changes(A, B)   which QA parts measure differently in tree B than in tree A: each part's measuring code is what
                          its cache key hashes (the part's function and what it reaches, charkit.bundle), plus the QA's
                          shared code (qa3d.Design, the check naming, checks.authorize). A part whose code changed without
                          a registered measurement step is a remeasure the gate would otherwise miss (tool/evalmesh
                          0c9eb95 changed qa3d.poke with the geometry; tool/look6's steps sat in a literal the registry
                          didn't read): the gate runs the 2x2 for its checks.
  interacts(...)          whether two changes to the code meet: one's changed definitions among the other's, or among what
                          the other's reach (`gate --carry`: the integration branch's move against the branch's own
                          change).

A tree is a worktree's path, a git revision or tree id (read with git, nothing checked out), or a charkit.cache.Tree.
Only charkit's own Python is compared here; data files and other Python are the closure's (charkit/closure.py).
"""
import ast, os, re, subprocess

from . import cache

ROOT = cache.ROOT
PART_MARK = re.compile(r'^@(?:registry\.)?qa_part\(', re.M)
# the QA's code every part runs through: the design side and the bundle handed to each part (their methods aren't
# followed from a call on the argument), the bundle's loading, the check names, the authority grading. (A part's cache
# key takes charkit.bundle whole; here its writer, bundle.export, which runs in Blender, is the geometry's side.)
SHARED = (('charkit.qa3d', 'Design'), ('charkit.qa3d', '_check_name'), ('charkit.checks', 'authorize'),
          ('charkit.bundle', 'Bundle'), ('charkit.bundle', 'Obj'), ('charkit.bundle', 'load'))


# the kit's bookkeeping, not measurement: the cache's keys and restores, the input record, the trace, the thread caps,
# the part registry. A part reaches them (cache.memo, the @qa_part decorator), and a change there moved no check: tool/
# infra4's own cache.py change flagged all 24 parts, and the 2x2 (217 s) found every check read alike.
BOOKKEEPING = ('charkit/cache.py', 'charkit/closure.py', 'charkit/trace.py', 'charkit/procs.py', 'charkit/registry.py')


def tree(t, repo=ROOT):
    """a cache.Tree for t: a Tree, a directory (a worktree), or a git revision or tree id in repo."""
    if isinstance(t, cache.Tree):
        return t
    if os.path.isdir(os.path.join(str(t), 'charkit')):
        return cache.Tree(root=t)
    return cache.Tree(repo=repo, rev=t)


def _files(T):
    """the tree's charkit .py files (relative paths), its tests and outputs left out."""
    if T._blobs is not None:
        paths = sorted(T._blobs)
    else:
        paths = []
        kit = T.path('charkit')
        for d, dirs, fs in os.walk(kit):
            dirs[:] = sorted(x for x in dirs if x not in ('out', 'tests', '__pycache__') and not x.startswith('.'))
            paths += [os.path.relpath(os.path.join(d, f), T.root) for f in sorted(fs) if f.endswith('.py')]
    return [p for p in paths if not p.startswith(('charkit/out/', 'charkit/tests/'))]


def module_of(rel):
    """'charkit/geom/hull.py' -> 'charkit.geom.hull' ('__init__.py': the package)."""
    return rel[:-3].replace('/', '.').replace('.__init__', '')


def part_defs(t):
    """the QA parts a tree registers, read with ast (nothing imported): [{name, module, fn, prefix, keep, skip_key}]
    from each `@qa_part(...)`-decorated top-level function (charkit.registry)."""
    T = tree(t)
    out = []
    for rel in _files(T):
        src = T.text(T.path(rel))
        if not PART_MARK.search(src):
            continue
        for n in ast.parse(src).body:
            if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for d in n.decorator_list:
                f = d.func if isinstance(d, ast.Call) else None
                if not (isinstance(f, ast.Name) and f.id == 'qa_part' or isinstance(f, ast.Attribute) and f.attr == 'qa_part'):
                    continue
                try:
                    name = ast.literal_eval(d.args[0])
                    kw = {k.arg: ast.literal_eval(k.value) for k in d.keywords if k.arg}
                except (ValueError, IndexError):
                    continue
                out.append(dict(name=name, module=module_of(rel), fn=n.name, prefix=kw.get('prefix') or '',
                                keep=kw.get('keep'), skip_key=kw.get('skip_key') or name))
    return sorted(out, key=lambda p: p['name'])


def measure_units(t):
    """each QA part's measuring code in tree t -> {part: {unit: digest}}: the part's function and what it reaches, and
    the QA's shared code (SHARED, where the tree has it), a module's constants each a unit (code_units' fine walk); the
    kit's bookkeeping (BOOKKEEPING) left out."""
    T = tree(t)
    with cache.code_tree(T):
        shared = [(m, n) for m, n in SHARED if _has(m, n)]
        return {P['name']: {k: v for k, v in cache.code_units(starts=[(P['module'], P['fn'])] + shared, fine=True).items()
                            if not k.startswith(BOOKKEEPING)}
                for P in part_defs(T)}


def _has(module, name):
    try:
        return name in cache._mod(module).defs
    except (OSError, SyntaxError, TypeError):
        return False


def measure_changes(a, b):
    """the QA parts whose measuring code differs between trees a and b (a part new in b is new, not changed) -> {part:
    {'units': [the units that differ], 'part': the part's registration in b}}."""
    A, B = tree(a), tree(b)
    ua, ub = measure_units(A), measure_units(B)
    parts = {P['name']: P for P in part_defs(B)}
    out = {}
    for name, u in sorted(ub.items()):
        if name not in ua:
            continue
        diff = sorted(k for k in set(u) | set(ua[name]) if u.get(k) != ua[name].get(k))
        if diff:
            out[name] = {'units': diff, 'part': parts.get(name)}
    return out


def part_checks(qa, part):
    """the checks one part reported in a build's qa.json (qa: the report): its record (measured.part_checks, written
    since 2026-09-30) -> [names], or None when the report predates the record."""
    rec = ((qa or {}).get('measured') or {}).get('part_checks')
    if rec is None:
        return None
    return list(rec.get(part) or ())


# ------------------------------------------------------------------------------------------------ definitions and reach
def defs(t, paths=None):
    """every definition in tree t (or in the charkit .py files `paths` only) -> {unit: digest}, as code_units' fine walk
    names them: 'charkit/x.py:name' for each top-level function and class, 'charkit/x.py:=NAME' for each top-level
    constant, 'charkit/x.py:<top>' for the module's other top-level statements (imports left out)."""
    T = tree(t)
    out = {}
    with cache.code_tree(T):
        for rel in _files(T) if paths is None else [p for p in paths if p.startswith('charkit/') and p.endswith('.py')
                                                     and not p.startswith(('charkit/out/', 'charkit/tests/'))]:
            try:
                M = cache._mod(module_of(rel))
            except (OSError, SyntaxError, TypeError, KeyError):
                continue
            if M.rel != rel:
                continue                       # (a package's module named like a sibling: not this file)
            out[rel + ':<top>'] = M.rest
            for n, d in M.defs.items():
                out['%s:%s' % (rel, n)] = d[0]
            for n, d in M.assigns.items():
                out['%s:=%s' % (rel, n)] = d[0]
    return out


def changed(a, b, paths=None, repo=ROOT):
    """the definitions that differ between trees a and b (added, removed or changed) -> sorted units. paths: the charkit
    .py files that differ (from git), to parse only those; None: git diff says which (both trees in repo)."""
    A, B = tree(a, repo), tree(b, repo)
    if paths is None:
        paths = _diff_paths(A, B, repo)
    da, db = defs(A, paths), defs(B, paths)
    return sorted(k for k in set(da) | set(db) if da.get(k) != db.get(k))


def _diff_paths(A, B, repo):
    if A._blobs is not None and B._blobs is not None:
        return sorted(p for p in set(A._blobs) | set(B._blobs) if A._blobs.get(p) != B._blobs.get(p))
    return None


def reach(t, units):
    """what the definitions reach in tree t (themselves included; code_units' walk from each) -> set of units
    ('path:name' and 'path:<top>'; a module taken whole shows as its definitions). Units the tree doesn't have (removed
    there) are left out."""
    T = tree(t)
    starts = []
    for u in units:
        rel, _, n = u.partition(':')
        if rel.endswith('.py') and n:
            starts.append((module_of(rel), n))
    if not starts:
        return set()
    with cache.code_tree(T):
        got = cache.code_units(starts=starts, fine=True)
    return {k for k in got if ':' in k}


def interacts(move, change, move_trees, change_trees, symmetric=True):
    """whether two code changes meet (`gate --carry`'s rule): the move's changed definitions among what the change's
    definitions reach (themselves included) in any of change_trees, or (symmetric) the change's among what the move's
    reach in move_trees -> [(unit, why)], empty when they don't. A caller changed by one side and its callee by the
    other meet either way; a helper both only call doesn't make them meet unless one side changed it."""
    move, change = set(move), set(change)
    hits = []
    rc = set()
    for t in change_trees:
        rc |= reach(t, change)
    for u in sorted(move & (rc | change)):
        hits.append((u, 'the move changes it, and the branch changes it or reaches it'))
    if symmetric and not hits:
        rm = set()
        for t in move_trees:
            rm |= reach(t, move)
        for u in sorted(change & rm):
            hits.append((u, 'the branch changes it, and the move reaches it'))
    return hits


def git_changes(repo, a, b):
    """[(status, path)] between two revisions or trees (closure.changes' shape)."""
    r = subprocess.run(['git', 'diff', '--name-status', '--no-renames', '-z', a, b], cwd=repo, capture_output=True,
                       text=True)
    f = r.stdout.split('\0')
    return [(f[i][:1], f[i + 1]) for i in range(0, len(f) - 1, 2)]
