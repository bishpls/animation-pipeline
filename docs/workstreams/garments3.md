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
