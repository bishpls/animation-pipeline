"""Self-registering QA parts and measurement steps (Michael, 2026-09-30: less coupling). There is no central list to
edit, so two branches that each add a part or a step never conflict on one. How to register either is in
docs/CHARKIT.md ("Registering a QA part or a measurement step").

QA parts. A venv QA part is a function (B, design, out, ...) -> (table, checks), registered where it is defined:

    from .registry import qa_part

    @qa_part('details', order=1700, table='details')
    def details(B, design=None, out=None): ...

  order     its place in the QA pass: parts run in ascending order (ties by name), so qa.json's checks come out in a
            fixed order whatever the import order. Leave gaps (the first parts are 100 apart).
  prefix    put before each of its check names ('body_': the part's 'front_iou' is qa.json's 'body_front_iou')
  keep      names already starting with this are left as they are (face_shape's own 'face_shape_*' checks)
  table     the key its table is reported under in qa.json ('views': the report's views; None: not reported)
  ref_image the part takes the spec's reference image as a fourth argument
  skip_key  the check reported SKIPPED when the part raises (default: its name)

parts() imports every charkit module that registers one (found by the `@qa_part(` decorator at the start
of a line, nothing else imported) and returns them in order.

Flag checks. A check built from one of Michael's flags (calibrated to pass on the design and fail where he saw the
flag; decision 2) carries FLAG in its qa.json entry: `{'value': ..., 'status': ..., 'flag': 'the torn collar tips
(look_v5)'}` (flag_check(c, why) sets it). The merge gate blocks a merge on such a check's regression (policy K:
charkit/gate.py), and only reports other checks' moves; a part marks its own checks, with no list here.

Measurement steps. When a check's measurement changes (not the character), its numbers step; the gate and the tune
loop then call it `remeasured` rather than better or worse (charkit.history). A module lists the steps of the checks
it measures in a module-level literal:

    MEASUREMENT_STEPS = [
        # (check pattern, the commit that changed the measurement, what changed)
        ('body_*_skirt_width', '26c6bbb', "the design's widest free row against ours on that same row"),
    ]

steps() reads every such list under charkit/ with ast (nothing is imported: the gate reads the merged tree's, whose
code it doesn't run), module by module in the modules' dotted-name order, each list in its own order. Keep the steps of
one check pattern in one module, in the order they happened: where two steps' patterns match one check, the later one's
reason is the one reported.
"""
import ast, collections, importlib, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
STEPS_NAME = 'MEASUREMENT_STEPS'
PART_MARK = re.compile(r'^@(?:registry\.)?qa_part\(', re.M)
SKIP_DIRS = {'out', 'tests', '__pycache__'}

FLAG = 'flag'                   # a check's qa.json key: the flag of Michael's it was built from (see above)
Part = collections.namedtuple('Part', 'name fn prefix table order ref_image keep skip_key')
_PARTS = {}
_found = False


# ------------------------------------------------------------------------------------------------------------ QA parts
def qa_part(name, order, prefix='', table=None, ref_image=False, keep=None, skip_key=None):
    """register the decorated function as the QA part `name` (see the module's docstring). -> the function."""
    def deco(fn):
        old = _PARTS.get(name)
        if old is not None and (old.fn.__module__, old.fn.__qualname__) != (fn.__module__, fn.__qualname__):
            raise ValueError('QA part %r registered twice: %s.%s and %s.%s' % (
                name, old.fn.__module__, old.fn.__qualname__, fn.__module__, fn.__qualname__))
        clash = [p.name for p in _PARTS.values() if p.order == order and p.name != name]
        if clash:
            raise ValueError('QA part %r: order %s is taken by %s' % (name, order, clash[0]))
        _PARTS[name] = Part(name, fn, prefix, table, order, ref_image, keep, skip_key or name)
        return fn
    return deco


def flag_check(c, why):
    """mark check dict c as built from Michael's flag `why` (the gate blocks on its regressions) -> c."""
    c[FLAG] = why
    return c


def is_flag(c):
    """a check (its qa.json dict, or None) built from one of Michael's flags?"""
    return bool(isinstance(c, dict) and c.get(FLAG))


def part_modules(root=HERE):
    """the charkit modules (dotted names) that register a QA part: their source has `@qa_part(` at a line's start."""
    from . import closure
    out = []
    with closure.scanning(root, PART_MARK.pattern):         # the gate's record of what a build read: a scan, not reads
        for path in _py_files(root):
            with open(path, encoding='utf-8') as f:
                if PART_MARK.search(f.read()):
                    out.append(_module(path, root))
    return sorted(out)


def parts():
    """every registered QA part, its module imported once -> [Part] by (order, name)."""
    global _found
    if not _found:
        for m in part_modules():
            importlib.import_module(m)
        _found = True
    return sorted(_PARTS.values(), key=lambda p: (p.order, p.name))


# ------------------------------------------------------------------------------------------------------------ steps
def _py_files(root):
    """charkit's .py files (subpackages included; its tests and outputs left out), in a fixed order."""
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not x.startswith('.'))
        for f in sorted(files):
            if f.endswith('.py'):
                yield os.path.join(d, f)


def _module(path, root):
    rel = os.path.relpath(path, os.path.dirname(root))[:-3]
    return rel.replace(os.sep, '.').replace('.__init__', '')


def module_steps(path, name=STEPS_NAME):
    """a file's module-level `NAME = [...]` literal, read with ast -> [(pattern, commit, why)], or None without one."""
    with open(path, encoding='utf-8') as f:
        src = f.read()
    if name not in src:
        return None
    for node in ast.parse(src).body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(getattr(t, 'id', None) == name for t in targets) and node.value is not None:
            return [tuple(x) for x in ast.literal_eval(node.value)]
    return None


def steps(root=HERE):
    """every module's MEASUREMENT_STEPS under root (a charkit package directory, this tree's or another's), module by
    module in dotted-name order -> [(pattern, commit, why)]."""
    from . import closure
    out = []
    with closure.scanning(root, STEPS_NAME):
        for path in sorted(_py_files(root), key=lambda p: _module(p, root)):
            got = module_steps(path)
            if got:
                out += got
    return out


def step_sources(root=HERE):
    """-> {module: its steps} (the registry's view by module, for tests and docs)."""
    out = {}
    for path in _py_files(root):
        got = module_steps(path)
        if got:
            out[_module(path, root)] = got
    return dict(sorted(out.items()))
