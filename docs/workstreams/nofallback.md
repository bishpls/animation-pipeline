# No silent fallback to MakeHuman (tool/nofallback)

Decision 7 in docs/CHARKIT_HANDOFF.md: a spec that doesn't declare its base and body fails loudly instead of building
MakeHuman. Why: a second character's spec with only `name` and `ref.manifest` built a bald MakeHuman default and
reported success.

## The rule

- `character.base_of(spec)`: `'code' | 'anime' | 'makehuman'`; `character.body_source(spec)`: `'code' | 'makehuman'`
  (`'code'` on base `'code'` only: on another base it built MakeHuman's body). Missing or other values raise
  `character.SpecError`, naming the spec and the allowed values. `character.check_spec` runs both.
- The check runs at load, before any build work: `cli.resolve` (build, fit) and `bodyeval.resolve(..., check=True)` (the
  evaluator, bodyfit) check before `manifest.produce`. `bodyeval.resolve` doesn't check by default, because the hull's
  own command reads a cut-down spec without a base.
- The sites that defaulted now call the resolver: character.assemble, bundle.assembly_meta, qa3d face_folds,
  qa3d_blender, bodyeval.Evaluator.assembly, cli.code_head / code_body, facefit, tests/garment_sensitivity.
  history.py records `spec.get('base')` (None when unknown: a record, not a fallback).
- Specs given explicit values: clawd_mh.json and clawd_locks.json (`base` and body source `makehuman`), clawd_code.json
  (body source `makehuman`, what it built). clawd.json, clawd_body.json and clawd_body_pieces.json already declared
  `code`/`code`. clawd_ref.json isn't a spec (the rig's measurements, written by charkit.refs): the test lists it apart.
- base_anime.derive's own assembly declares its body source too.
- Test: charkit/tests/test_spec_declared.py. test_spec_alias.py had no `__main__`, so the gate (which runs each test
  file as a script) ran nothing: fixed. test_bucketsync.py has the same gap (not touched).

## Silent success (produced references)

- `manifest.produced`: a producer that ran without error but wrote no output was stamped and its (missing) path
  returned; the hull's and refviews' `if masks and os.path.exists(masks)` then built without the outfit pieces. Now it
  raises and stamps nothing.
- `hairlayers.produce` swallowed any error making the outfit masks and built the layers without them. Now it raises;
  a manifest with no outfit masks still builds without them.
- Cost: manifest.py and hairlayers.py are in the producers' stamps, so the hull, outfit masks and hair layers rebuild
  once (the hull would anyway: bodyeval.py is in its stamp).

## Not done (findings)

- `bodyeval.Evaluator.assembly` composes a body-knob change from a MakeHuman body (`compose`, `build_body_data`) on
  any base but `anime`, a `code` body included. The build doesn't use it, but the evaluator's body knobs on clawd.json
  may be read on MakeHuman's body. Worth a look with the body fits.
- `eyes.knobs` reads `spec.get('base') != 'code'` (plate eyes unless `code`) and is left as is: cut-down specs reach it.

## Gates
