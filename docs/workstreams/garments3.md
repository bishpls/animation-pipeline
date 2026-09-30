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

## Call L: flat, square open rims (garments._thick)

**Measured first** (scratch `rimlab.py`: a garment-scale open shell, 2.5 mm, a partial tube with a hem, a top edge and
two cut edges, built as `garments.build` builds a shell and counted by `lookprobe.normals` itself, faces whose shading
the outline turns past 90 degrees, at the build / face-board / body-board widths):

| rim | flips (build 1.2 mm / face 0.93 / body 3.94) | of which rim faces |
|---|---|---|
| as built (Solidify rim, then Subdivision: a bead) | 486 / 462 / 486 | 480 of 480 |
| `edge_crease_rim` 1 (look round 3's try: "doesn't help") | 480 / 460 / 480 | 480 |
| **`edge_crease_inner` and `_outer` 1 (the border loops)** | **24 / 0 / 30** | 12 |
| all three | 18 / 0 / 18 | 6 |
| no Subdivision | 0 / 0 / 0 | 0 |

Look round 3 creased the wrong edges: in Blender (checked on a solidified grid) `edge_crease_rim` creases the rim's
cross edges, `_outer` the surface's open border loop and `_inner` the moved layer's. Creasing the two border loops keeps
the rim a flat band square to the layers under the Subdivision, so the outline's inward move (still half the shell,
call I unchanged) no longer turns it inside out. Creasing the cross edges as well makes every border vertex a corner
(the hem a polyline) for 6-12 fewer flips; not taken.

**Built:** every garment's thickness goes through `garments._thick` (the ten `thick` SOLIDIFY sites: shells, bands,
belts, cuffs, sleeves, the skirt, collars, panels), which sets both border creases (`RIM_CREASE` 1.0; 0 restores the
bead). The evaluator follows (`bodyeval.garment_part` reads the recorded creases; `solidify` returns the creased border
loops, `subdivide` and `limit_positions` treat them as sharp and pass their children on). Against Blender on the lab's
shell: evaluator vs Blender vertices 6e-8 m apart creased (7.6e-3 m without the evaluator's crease support), 6e-8
uncreased. Test: `test_bodyeval.test_creased_rims_stay_flat_and_square`. The real build's flip count is measured on
the render-box build below.
