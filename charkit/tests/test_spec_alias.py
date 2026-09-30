"""charkit/spec/clawd_body_pieces.json is an alias of clawd.json (the authored character, 2026-09-29): workstream notes
and gates still name it. It drifted once (the eyes round's pupils reached clawd.json only), so a spec edit must go to
both, and this test fails the gate when they differ."""
import json, os

SPEC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'spec')


def test_clawd_body_pieces_is_identical_to_clawd():
    a = json.load(open(os.path.join(SPEC, 'clawd.json')))
    b = json.load(open(os.path.join(SPEC, 'clawd_body_pieces.json')))
    diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    assert not diff, 'clawd_body_pieces.json differs from clawd.json in %s: edit both (it is an alias)' % diff
