# char3: a new character end to end (tool/char3) — RELAUNCH BRIEF

Worktree `~/animation-pipeline-char3`, branch `tool/char3` (from pipeline-3d d44db780; pipeline-3d merged in at
6a30512e). The character is **c3**, PRIVATE: references, prompts, spec, manifest, builds, review pages and report live
under `charkit/private/c3/` (gitignored, synced to the boxes by fix 1). This file is public: nothing about the
character's identity goes here.

**Goal (Michael, 2026-10-01):** stress-test how much of charkit is overfit to Clawd: references in, rigged model out,
no per-character tuning. Acceptance: reference set registered and refchecked (DONE); a first c3 build where his
references demonstrably reach the model (no MakeHuman); the generality report; the generic fixes gated PASS under K.

## Where things are (private paths, all under charkit/private/c3/)

- `spec.json`: name, ref.manifest, base code, body.source code, style anime. NOTHING else (no hand-written hair,
  garments, colours): everything else comes from the manifest at resolve time and from the build's draft step.
- `refs/manifest.json`, built by `refs/build_manifest.py` (re-run after any choice changes): 22 references, the
  palette (18 swatches from the model sheet), `window`, `pieces` (6 declared: tunic, belt, drape, pin, sandals, crown;
  swatches, zone bones, side, motion, shape_ref), `shape_truth` per piece, `facial_hair: true`, produced references
  (`outfit_masks` by charkit.outfit_sheet, `hull`, `body_hull` from the base body sheet).
- `refs/gen/`: prompts (`build_prompts.py` -> `prompts.json`), takes in `takes/`, chosen sheets; `gen.py` runs calls.
- `refs/refcheck_*.sh` + `out/refcheck/summary.json`: every refcheck number.
- `review/refs/page/index.html`: the reference review page (handed over; Michael's answers below).
- `review/build_page.py BUILD [CLAWD_BUILD]`: writes `review/build/page.json` (render it with
  `python -m charkit review page charkit/private/c3/review/build/page.json --out charkit/private/c3/review/build/page`)
  and `report/report.json` (the private generality report: stages, tally, what reached the model, overfit ranked).
- `report/stages.json`: the stage ledger (below) as data.
- `stages.py OUT [stage...]`: the build's venv stages locally (resolve, outfit_masks, hull, body_hull, code_head,
  code_body), each recorded in OUT/stages.json; `box_build.sh NAME [args]`: `remote build` into out/NAME.

Michael's answers (2026-10-01, via the coordinator): the drape over the right shoulder and the pin on it over his
right chest: yes; no glasses (not part of the character); crown as is; hand sheet accepted by eye; generalise
handref's cuff scaling if cheap, else a finding (it is a finding, below).

## Stage ledger (ran unchanged / generic fix landed / Clawd assumption / missing builder)

| stage | verdict | what |
|---|---|---|
| reference generation | ran unchanged | 19 calls, n=2, all ok; prompts per character |
| palette (every sheet reader's classes) | generic fix (3) | the classes were Clawd's constants |
| sheet detection (views, eyes, scale) | generic fix (4) | her palette, her eye-spacing proportion, eye-named views |
| head-sheet detection | generic fix (10) | a construction head's ears read as eyes; layouts name views |
| refcheck (heads) | generic fix (6) | needed her source sheet + 2D rig for the scale |
| layerref (separated layers) | generic fix (7) | only her kinds; new palette kinds edit / alone |
| handref (hand sheet) | Clawd assumption, finding | scales by her wrist cuffs |
| spec colours | generic fix (3) | absent colours fell back to Clawd's |
| body window | generic fix (5) | her -6.2 L cut an 8-head figure at the shins |
| outfit masks + graph | generic fix (8) | read her hand-built 2D rig |
| hull | ran unchanged | once detection ran (~2-3 min, 305k faces) |
| code head | ran unchanged | once head sheets read (fix 10) |
| code body | generic fix (15) | feet from her boot_L/boot_R; FIT RESULT PENDING (see State) |
| hull hair | generic fix (11) | colour fitted to the head's top (a crown sits there) |
| facial hair | missing builder, built (11) | parts.facial_hair |
| garments | missing builder, partly built (13, 16) | drafted: tunic = shell + skirt, belt, sandals as shoes, drape = sash + panel |
| accessories | missing builder, built (12) | crown, pin |

## Generic fixes (shared code, tests; with nothing declared Clawd reads byte-identically: resolve, window, detections)

1. bucketsync / build.sh: `charkit/private/` synced, `charkit/private/<name>/out/` not (test_bucketsync +3, its __main__).
2. Implausible-scale guard (the 68 GB hazard): detect_figures raises under 1 head length; grids capped at
   faceqa.MAX_WINDOW_PX (test_sheetqa).
3. charkit/palette.py: manifest swatches with roles classify drawings (sheetqa.classes, bodyqa.family); dark eyes by
   shape; spec colours filled from it (test_palette).
4. sheetqa: eye-pair fallback spacing; turnaround order names views; slivers re-searched on the eye line.
5. bodyqa.use_window: a manifest's body window.
6. refcheck without a rig: the face sheet's own scale, the body sheet's departures, found head boxes.
7. layerref --kind edit / alone (palette-driven; calibrated in test_palette).
8. charkit/outfit_sheet.py: outfit graph + masks without a 2D rig; skeleton from the base body (test_outfit_sheet).
9. geom.hull --sheet base_body, manifest.body_hull: the body fitted to the base body's hull.
10. refcheck.detect_heads: edge blobs aren't eyes; a profile's ear; head layouts (HEAD_ORDERS).
11. geom.parts: hull hair colour from the palette; parts.facial_hair (hair.shape.facial); default hull hair.
12. accessories crown and pin kinds (from_eyes placement, bone parenting) (test_crown_pin).
13. outfit_sheet.draft + the build's outfit_draft step (cli.py): garments and accessories drafted from the
    character's own graph, masks and hull when its spec lists none.
14. charkit/generality.py: the QA pass share, Clawd-named checks apart (test_generality). A recent Clawd build:
    708 checks; named 0.69, applicable 0.78.
15. code_body.foot: any footwear piece, else the bare foot.
16. garments.sash kind (a band through one shoulder and the opposite hip).
17. the crown's point count from its own sheet's tip spacing.

Commits: fd078c77 (1-2), 35b169c5 (3-9), 0b342be9 (10-17), 6a30512e (merge pipeline-3d: code_hand.py conflict
resolved by taking pipeline-3d's and reapplying the body_hull routing at its Fit call).

## Generality findings so far (public summary)

- The first reading (an earlier second character, 2026-09-30) never reached the model. This one does, stage by
  stage, up to the code head; nothing silently defaults (the no-fallback rule held: base and body declared).
- Overfit points found, by kind: colour (classes, iris, hair colour, spec defaults), proportion (eye spacing over the
  band, the body window), layout assumptions that held (turnaround order), piece names (boot_L/boot_R in the body,
  cuffs in handref, Clawd-named QA checks), missing inputs (her 2D rig for the outfit graph and refcheck's scale),
  missing vocabulary (beard, crown, pin, drape, sandals).
- Remaining overfit points, ranked (proposals in report/report.json):
  1. QA checks named for Clawd's pieces (skirt, bow, clips, buns, boots): generate checks per declared piece type
     from the manifest's pieces (shape IoU per piece and view), Clawd's as her instances;
  2. the skirt template paints her stepped hem and pleat texture: a hem texture per piece from its own sheet;
  3. hairlayers' fixed 7 families and hairsplit: families from the breakdown's own colours;
  4. outfit drafting covers 6 piece types: a template per type dispatched from a character description (the
     roadmap's layer 1, a VLM-read graph); the strapped sandal built as a closed shoe; the drape's knot not built;
  5. handref scales by her cuffs: the forearm cut's width against the skeleton's wrist;
  6. anime eye checks calibrated on large eyes (a narrow eye fails lid_gap): scale by the design's own eye;
  7. the review page's close-up regions (bow, clips, skirt): regions from the manifest's pieces.

## State (2026-10-01 ~14:30, checkpoint for relaunch)

- Running when this was written (each records its own log; check before relaunching anything):
  - the local stage run: DONE, every venv stage passes on c3 (resolve 174 s incl. the produced references, code head,
    code body 99 s from the base body hull): charkit/private/c3/out/b0/stages.json;
  - the full test suite on the merged tree (logs: charkit/private/c3/out/tests/);
  - the pregate on the box (`python -m charkit pregate --box auto`, log charkit/private/c3/out/pregate.log; report
    into charkit/out/pregate/).
  - JOB IDS (2026-10-01 14:13): build `build-char3-1001-141348-1817` on the build box (log
    charkit/private/c3/out/b1_build.log; outputs fetched into charkit/private/c3/out/b1 when it ends; if the local
    follow died: `python -m charkit remote attach build-char3-1001-141348-1817`); pregate
    `pregate-char3-1001-140854-89f4` on render2 (of 6a30512e; log charkit/private/c3/out/pregate.log; attach likewise).
  - The full test suite on the merged tree (6a30512e): 99 files, 0 failed.
  - PREGATE DONE: PASS (3 moved, 0 blocking, 978 s), charkit/out/pregate/pregate_tool-char3_6a30512e_into_60c0f1a4.md.
    Moved by 0.001-0.002, value only: body_three_quarter_iou_hair 0.743 -> 0.742, sheet_shown_front 0.465 -> 0.466,
    sheet_shown_three_quarter 0.463 -> 0.461 (all hair/sheet readings: before the box gate, find which detection
    change reaches Clawd's hair path at the QA's scale (at_scale's resample factors other than the 1.0/0.5/0.25
    compared) and either make it identical or register the remeasure in charkit/steps/).
  - The first launch of the build failed in the sync: a blob's sha256 mismatched on the box (a file that changed
    between the laptop's hash and its upload: the local test suite was rewriting transient files in the worktree,
    e.g. test_cache's charkit/probe.py). The box caught it loudly; rerun after the tests: synced in 1.9 s. Finding
    (infra): the laptop could re-hash at upload and name the file. Also: keep private review pages under
    charkit/private/<name>/out/ (54 MB of review images were synced as inputs).

## Exact next steps

1. (done) the venv stages all pass locally.
2. First box build (LAUNCHED at the checkpoint: `charkit/private/c3/box_build.sh b1`, log
   charkit/private/c3/out/b1_build.log; reattach with `python -m charkit remote attach JID` from that log). The
   build's new `outfit_draft` step writes out/b1/outfit_draft.json; Blender then builds the drafted garments
   (shell, skirt, belt, shoe, sash, panel) and accessories (crown, pin) for the first time: expect breaks there
   (e.g. the sash's plane, the crown's from_eyes placement); fix generically.
3. Boards on render2 (`python -m charkit remote --box render2 build ... --boards views,body`) or the toon renderer.
4. `python -m charkit.generality charkit/private/c3/out/b1 --json charkit/private/c3/report/tally.json`; then
   `python charkit/private/c3/review/build_page.py charkit/private/c3/out/b1 <a Clawd build>` and render the page;
   fill this file's report section with the public numbers.
5. Gate: if the pregate is clean, `python -m charkit remote gate tool/char3 --into pipeline-3d` (merge pipeline-3d
   first if it moved). Report under K.
