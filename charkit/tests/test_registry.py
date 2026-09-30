"""charkit.registry: QA parts and measurement steps register themselves (no central list), in a fixed order, and the
migration from qa3d.PARTS and history.STEPS kept both (venv: run this file, or pytest)."""
import collections, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, HERE)
from charkit import history, registry

# qa3d.PARTS before self-registration (2026-09-30): the parts in the order they ran, with their check prefix and table
LEGACY_PARTS = [
    ('shape', '', 'views'), ('scalp', '', None), ('poke', '', None), ('hair_noise', '', None), ('face_folds', '', None),
    ('mesh', '', None), ('eyes', 'eye_', 'eyes'), ('eye_views', 'eye_', 'eye_views'), ('sheet', 'sheet_', 'sheet'),
    ('sheet_figures', 'figures_', 'sheet_figures'), ('sheet_body', 'body_', 'sheet_body'), ('sheet_expr', '', 'sheet_expr'),
    ('sheet_palette', 'palette_', 'sheet_palette'), ('hair_pieces', '', 'hair_pieces'),
    ('sheet_pieces', 'piece_', 'sheet_pieces'), ('pieces_3d', 'piece3d_', 'pieces_3d'), ('details', '', 'details'),
    ('face_shape', 'face_shape_', 'face_shape'), ('face', 'face_', 'face'), ('face_region', '', 'face_region'),
    ('look', '', 'look')]
MIGRATED_AT = '9397578'          # pipeline-3d's head when history.STEPS moved to charkit/steps/


def test_parts_keep_the_legacy_order_and_fields():
    """every part qa3d.PARTS listed runs in its old place with its old prefix and table; a new one may slot in."""
    P = registry.parts()
    got = [(p.name, p.prefix, p.table) for p in P if p.name in dict((n, 1) for n, *_ in LEGACY_PARTS)]
    assert got == LEGACY_PARTS, got
    assert len({p.order for p in P}) == len(P), 'two parts share an order'
    special = {p.name: (p.ref_image, p.keep, p.skip_key) for p in P}
    assert special['shape'][0] and special['face_shape'][1] == 'face_shape' and special['eyes'][2] == 'eye'


def test_a_part_registers_once_and_its_order_is_its_own():
    reg = registry._PARTS
    saved = dict(reg)
    try:
        @registry.qa_part('_test_part', order=99990)
        def a(B, design=None, out=None):
            return None, {}
        registry.qa_part('_test_part', order=99990)(a)                 # the same function again (a reload): fine
        try:
            @registry.qa_part('_test_part', order=99991)
            def b(B, design=None, out=None):
                return None, {}
            raise AssertionError('a second function under one name should raise')
        except ValueError:
            pass
        try:
            @registry.qa_part('_test_other', order=99990)
            def c(B, design=None, out=None):
                return None, {}
            raise AssertionError('two parts at one order should raise')
        except ValueError:
            pass
    finally:
        reg.clear()
        reg.update(saved)


def test_parts_are_found_without_a_list():
    """a module that registers a part is found by its decorator, and nothing else is imported for it."""
    d = tempfile.mkdtemp()
    open(os.path.join(d, 'a.py'), 'w').write("from .registry import qa_part\n\n@qa_part('x', order=1)\ndef x(B): pass\n")
    open(os.path.join(d, 'b.py'), 'w').write("# @qa_part( in a comment is not a registration\nX = '@qa_part('\n")
    assert registry.part_modules(d) == [os.path.basename(d) + '.a']
    assert 'charkit.qa3d' in registry.part_modules()


def _legacy_steps():
    """history.STEPS as it was at MIGRATED_AT (None outside a git checkout that has it)."""
    r = subprocess.run(['git', '-C', HERE, 'show', MIGRATED_AT + ':charkit/history.py'], capture_output=True, text=True)
    if r.returncode:
        return None
    p = os.path.join(tempfile.mkdtemp(), 'history.py')
    open(p, 'w').write(r.stdout)
    return registry.module_steps(p, 'STEPS')


def test_every_legacy_step_is_still_registered_in_its_order():
    old = _legacy_steps()
    if old is None:
        print('(skipped: no git history)'); return
    new = history.registered()
    missing = collections.Counter(old) - collections.Counter(new)
    assert not missing, 'steps lost in the migration: %s' % list(missing)
    for pat in {s[0] for s in old}:                                  # a pattern's steps keep their order (its reason)
        o = [s for s in old if s[0] == pat]
        n = [s for s in new if s[0] == pat and s in o]
        assert n == o, pat


def test_steps_live_in_steps_modules_that_nothing_imports():
    """a step is data: charkit/steps/*.py are read with ast, never imported, so adding one leaves every build's code
    keys (the stages', the hull's stamp) alone."""
    src = registry.step_sources()
    assert src and all(m.startswith('charkit.steps.') for m in src), list(src)
    import re
    imp = re.compile(r'^\s*(from \.steps\b|from charkit\.steps\b|import charkit\.steps\b|from \.+ import [^#\n]*\bsteps\b)', re.M)
    for path in registry._py_files(registry.HERE):
        assert not imp.search(open(path).read()), '%s imports charkit/steps' % path
    assert registry.module_steps(os.path.join(registry.HERE, 'history.py'), 'STEPS') is None


def test_load_steps_reads_old_and_new_trees():
    """the gate reads the merged tree's steps without importing it: a tree from before the migration (history.py's
    STEPS) and one after (each module's MEASUREMENT_STEPS)."""
    old = tempfile.mkdtemp()
    open(os.path.join(old, 'history.py'), 'w').write("STEPS = [\n    ('sheet_*', 'abc1234', 'a reason '\n     'split'),\n]\n")
    assert history.load_steps(os.path.join(old, 'history.py')) == [('sheet_*', 'abc1234', 'a reason split')]
    new = tempfile.mkdtemp()
    os.makedirs(os.path.join(new, 'steps'))
    open(os.path.join(new, 'history.py'), 'w').write('def registered():\n    return []\n')
    open(os.path.join(new, 'steps', 'b.py'), 'w').write("MEASUREMENT_STEPS = [('b_*', 'bbb', 'b')]\n")
    open(os.path.join(new, 'steps', 'a.py'), 'w').write("MEASUREMENT_STEPS = [('a_*', 'aaa', 'a'), ('a_*', 'aab', 'a2')]\n")
    open(os.path.join(new, 'qaz.py'), 'w').write("MEASUREMENT_STEPS = [('z', 'zzz', 'a module may keep its own')]\n")
    assert history.load_steps(os.path.join(new, 'history.py')) == [
        ('z', 'zzz', 'a module may keep its own'), ('a_*', 'aaa', 'a'), ('a_*', 'aab', 'a2'), ('b_*', 'bbb', 'b')]
    here = os.path.join(registry.HERE, 'history.py')
    assert history.load_steps(here) == history.registered() == history.STEPS


def test_a_modules_steps_are_one_literal():
    """what the registry reads (a module's first MEASUREMENT_STEPS literal, by ast) is everything the module registers:
    the name bound once and nothing added to it. tool/look6's `MEASUREMENT_STEPS += [...]` was never read, so its first
    gate ran no 2x2 for the checks the round remeasured. A steps module run as a script holds exactly what's read."""
    import ast, runpy
    name = registry.STEPS_NAME
    for path in registry._py_files(registry.HERE):
        tree = ast.parse(open(path, encoding='utf-8').read())
        uses = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == name]
        if uses:
            assert len(uses) == 1 and isinstance(uses[0].ctx, ast.Store) and registry.module_steps(path) is not None, \
                '%s: %s must be one module-level literal, bound once and not added to (%d uses)' % (path, name, len(uses))
    steps_dir = os.path.join(registry.HERE, 'steps')
    for f in sorted(os.listdir(steps_dir)):
        if f.endswith('.py') and f != '__init__.py':
            path = os.path.join(steps_dir, f)
            assert [tuple(x) for x in runpy.run_path(path).get(name, [])] == registry.module_steps(path), path


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
