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
