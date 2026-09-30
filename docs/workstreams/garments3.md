# The combined garments round (tool/garments3)

The overnight run's item 2 (docs/CHARKIT_HANDOFF.md, "Overnight run plan"): the sheet-only outfit masks, the jacket over
the band and the skirt's template flaps landed together, the garments adapted to the new masks templates first, flat
rims (Michael's call L), the skirt's fit G written into the specs, one gate under policy K.

**Branch** `tool/garments3` in `~/animation-pipeline-garments3` (sparse charkit worktree), from pipeline-3d 08f93e2.

**The merged branches' own notes** (brought along by the merges):
- `docs/workstreams/outfit-source.md`: the masks from the design sheets alone (0.972 against the hand-labelled truth);
  its "Next steps".
- `docs/workstreams/garments2.md`: the jacket over the band, the puff sleeves, the band's drawn rows; "Round 3 state".
- `docs/workstreams/skirt.md`: the template flaps, the stepped band, the tuck, 18 pleats; "Checkpoint ... start here".

## Merges

1. **tool/outfit-source (3d9f456):** clean. cli.py's usage drops the removed `--field/--no-field` and lists
   `outfit score`. Tests: 50 files ok (150 s).
2. **tool/garments2 (2bf75d1):** one conflict, `charkit/bodyeval.py`: garments2's edits to the evaluator's garment
   dispatch (`garment_piece`'s template sleeves and cuffs, `garment_tones`' collar stripe and band trim) dropped, since
   geom-truth replaced that dispatch with the build's own garments stage (`geomstage`), and garments2's
   `garments.build` already carries the same routing and materials. The shorts keep one `hem_drop` (0.03) in all
   three specs. Tests: 53 files ok (127 s).
3. **tool/skirt (73fe12c):** clean (tool/skirt already had geom-truth). Its bodyeval edit (a piece built without a
   Subdivision modifier evaluates unsubdivided: the template flaps' crisp corners) comes along. One registry clash:
   the skirt's QA part and tool/artifacts' both took order 2200; the skirt's moves to 2300 (after the artifacts, which
   test_artifactqa wants after the look). Tests: 55 files ok.

## The skirt's fit G into the specs (step 4, done first: the tuck and A-line adapt on top of it)

`make_garments.py fitG_best.json` then `apply_spec.py` (the skirt's scratch harness, copied into this session's
scratchpad and pointed at this worktree) into clawd.json, clawd_body_pieces.json (still identical) and clawd_body.json:
the template flaps (`shape: template`, `hem: band`, the edges, stand, a three-tread stair), the skirt's geometric band
(0.15 L, stair 0.35/0.25/0.15), `tuck_fit`, 18 pleats (garments2's spec had 22). `_skirt_try.json` was never tracked
(it's untracked in ~/animation-pipeline-skirt, which this round doesn't touch): nothing to delete in the branch.
`flapchains` waits for a box build of this tree.
