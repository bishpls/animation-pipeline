"""The code map (charkit/codemap.py): generated from this tree with ast, deterministic (two runs alike), every module
listed with its public functions, the QA parts and commands read from the registry decorators and cli.main (venv or
system Python: run this file). Freshness of docs/CODEMAP.md is not tested: the map is regenerated, never a gate."""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import codemap


def test_deterministic_and_complete():
    a, b = codemap.generate(), codemap.generate()
    assert a == b
    assert a.startswith('# charkit code map') and '## Where things live' in a and '## Modules' in a
    for pkg, rel in codemap.modules():
        assert '#### `%s`' % rel in a, rel
    assert '| 1750 | `piece_details` |' in a and '`charkit/pieceqa.py:piece_details`' in a
    assert '| `sweep` | `sweep` |' in a and '| `build` | `cli.build` |' in a
    assert '- `apply(spec, over)`: the spec with overrides' in a
    assert '`shorts_{view}_hem` | edge | shorts | piece_details' in a


def test_read_module():
    m = codemap.read(codemap.ROOT, 'charkit/registry.py')
    names = [n for _, n, _ in m['defs']]
    assert any(n.startswith('qa_part(') for n in names) and m['doc'].startswith('Self-registering QA parts')
    assert not any(n.startswith('_') for n in names)


if __name__ == '__main__':
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); print('ok', k)
