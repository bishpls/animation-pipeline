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

## Round 2 (relaunched agent, 2026-10-01 from 14:14)

Fixes in progress (uncommitted until measured; all inert for Clawd):
18. outfit_sheet.draft activates the resolved spec's palette and window itself (it read a resolve's in-process state:
    standalone it raised "no two-eyed figure").
19. manifest.hull_args: produced()'s in-process hull build ignored its command's `--sheet base_body` (and --head, --h,
    --faces), so c3's body_hull was carved from the CLOTHED sheet, byte-identical to the hull (sha 523d2b05 both): his
    authored body was fitted to the chiton's volume. The fast path now follows the command; the args enter the stamp
    only when non-default (a plain hull's stamp unchanged by them). b1 (launched before) has the wrong body hull.
20. code_body.Hull reads a hull carved with no pieces (a base body's) as bare: its hair 'hair', every other vertex
    'skin' (it raised KeyError 'pieces'), and torso_skin measures a bare torso by all its skin (Clawd's dressed hull
    keeps the neckline rule: her torso is measured through her top). Shape IoU of the authored body against the BASE
    body sheet (charkit/private/c3/tools/body_iou.py; front / three-quarter / profile / back, under the chin):
      fitted to the clothed hull (b1's):           0.784 / 0.763 / 0.750 / 0.774 (legs 0.75 / 0.72 / 0.76 / 0.72)
      to the base body hull (fix 19):              0.812 / 0.752 / 0.845 / 0.805 (torso 0.771 front: a narrow waist)
      plus the bare torso (fix 20):                0.875 / 0.813 / 0.942 / 0.863 (torso 0.887 / 0.852 / 0.956 / 0.883)
    A foot coverage rule (FOOT_COVER) was tried and reverted: on the true hull it moved the feet by 0.001.
    Tests: test_code_body +2, test_manifest +2 (each fails on the old code); the set of 7 files 40 passed.
21. faceflags read its design sheets from charkit/refs/clawd/gen/ whatever the character (b1's QA: face_flags
    raised in at_scale on Clawd's drawings under the second character's palette): sheet_path() resolves them through
    the build's manifest (part() sets it from the bundle's spec); a manifest without one raises.
22. refcheck.at_scale: small dark eyes read their spacing to a pixel, not linearly in the factor, so the 0.3 px target
    never converged (face_flags and hairweight raised on his own sheet): the closest attempt within 1%
    (AT_SCALE_NEAR) is taken when none lands within 0.3 px; converging sheets return as before.
23. preview.design_refs / reviewpage: the review page's design pictures were Clawd's turnarounds for any build; they
    are the build's own manifest's (PAGE.json 'manifest', else the first build's), read with its palette and window.
    Tests: test_refcheck +1, test_faceflags +1, test_reviewpage +1 (the first two fail on the old code); the four
    files 21 passed.
24. manifest.shape_sheet(spec, part): a piece's shape from the manifest's declared shape_truth picture (its layer
    redrawn without what covers it), else the default sheet. The head fit (code_base.head_sections,
    headfit.hidden_outline, the code head's cache inputs) reads the jaw's: a beard-free redraw of the head turnaround.
    Measured (charkit/private/c3/tools/head_beard.py, b1 -> this): the head below the chin no longer follows the beard's
    steps (front y at z -0.4 / -0.5: -0.117 / +0.017 -> -0.120 / -0.103; depth 0.87 -> 0.74 L), the hull hair's
    silhouette IoU 0.581 -> 0.636; the beard cut unchanged (640 -> 716 faces, IoU 0.033 -> 0.034: see findings).
25. refcheck.at_scale falls back on the sheet's own-resolution detection, scaled (scale_heads), when small dark eyes
    are lost at every reduced scale (the beard-free redraw raised). Tests: test_refcheck +1, test_manifest +1 (each
    fails on the old code).

Item diagnoses (coordinator's read of b1, 2026-10-01):
- (4) the skin flap at the hips: the body fitted to the CLOTHED hull (fix 19) with its torso measured by its neckline
  only (fix 20): fixed, body IoU against the base body sheet 0.784/0.763/0.750/0.774 -> 0.875/0.813/0.942/0.863.
- (1) the head built round the beard: the head's face contours read the dressed sheet (fix 24 reads the declared
  beard-free redraw). Remaining: the face measure's skin flood (refcheck.face_design, measure_heads: lines as walls)
  stops at his nose (-0.236 L) on BOTH sheets: his drawn folds and mouth wall it (Clawd's face draws no such lines), so
  the chin is read at the nose and the jaw below is the construction skull's wide neck block (half-width 0.35 L); the
  outline reader (faceregion.jaw_front) finds the front chin at -0.374. The beard cut (parts.facial_hair) keeps 716
  faces: the beard lies inside that block, and its parts cleanup drops 1514 of 1591 parts.
- (2) the white hair in fragments: the hull's head top is the crown's solid (28% of the head region's surface reads crown
  gold, 42% hair): the hair cut finds hair only round the sides. The declared hair shape truth (head_nocrown) isn't
  read yet: the hair cut from a hull carved from it (a head-layout hull) is the generic fix.
- (3) Clawd's face features (big lashed eyes, blush, thin white brows): no reader of a new character's eye shape,
  lashes, blush or brows without a 2D rig (refs.fit): the spec defaults are Clawd's.
- the joined shoulder on a second body (scratch/c3-shoulder 80b2d306: tool/char3 + tool/garments4-shoulders, NOT for
  merge; tools/garments5/bodyj.py parametrised to the build's own spec and base body sheet): with Clawd's candidate
  knobs as is, topology one closed surface (arms and shoulders joined, 0 boundary / non-manifold edges; 105 flipped
  edges against 13) and the profile arm better (front/back rms 0.122/0.165 -> 0.073/0.075), but the silhouette score
  0.053 -> 0.106 L (front top/outer rms 0.018/0.042 -> 0.114/0.179: the top 0.14 L high at |x| 0.5, the deltoid pulled
  in, outer x at z -0.9 0.73 vs 1.14) and the raised arm inside the torso (side / front, pivot 0.18: 100 / 148 vertices;
  strain p95 1.30 / 1.71; folded 0.3% / 0.14%). Clawd-specific: the template's knobs are absolute L (shoulder top
  z -0.525, x 0.38, socket top 0.36), not read from the base body sheet; the harness's shoulder point misreads an
  A-pose (it lands near the elbow). Box build with it on (chiton's sleeves over it): s1, job build-char3-1001-151614-f06c
  on the build box (log charkit/private/c3/out/s1_build.log; spec charkit/private/c3/spec_shoulder.json).

Running (15:35): b2 on render2 (job build-char3-1001-145743-6f02, log charkit/private/c3/out/b2_build.log; fixes 18-20);
the gate of e64f2bbb on render2 (job gate-char3-1001-150917-ca4e, log charkit/private/c3/out/gate1.log; it predates
fixes 24-25, so re-gate the tip after); s1 on the build box.
Preflight (charkit/private/c3/out/preflight/): the draft (7 garments, 2 accessories) and every drafted garment through
the numpy builder (bodyeval.garment_piece) build without error; the sandals inherit the foot's bad width.

Clawd's pregate moves (0.001-0.002 on 3 hair readings): ATTRIBUTED, not this branch's measurement. Evidence:
- the design side is byte-identical under both trees (body sheet detection at the QA's scale, refcheck.face_design,
  detect_figures on all 18 manifest images except key3d, which no QA path detects on);
- `charkit/private/c3/tools/clawd_attr.sh` (the pregate's evaluator flow on Clawd, local): 333 wrapped detection calls
  (find_eyes 303, detect_figures 7, detect_heads 20, face_design 2, measure_sheet 1) agree with pipeline-3d's versions
  (0 diffs), and with detection swapped back the values are the candidate's (0.466 / 0.461 / 0.742), as render2's;
- the carrier is Clawd's produced HULL: the hair layers, hair split and outfit masks are byte-identical between the
  branch's fresh build and the cache's pipeline-3d entries, the hull not (face carve 126,062 vs 123,774 voxels). Built
  fresh with pipeline-3d's own code (scratchpad copy, CHARKIT_PRODUCED_CACHE=off) the hull is byte-identical to the
  branch's (sha 1c4094a4, 150,342 faces): the pipeline-3d baseline restored a STALE cached hull (sha 786abaad).
- why (infra finding): code_base.head_sections imports headfit and refcheck at run time (importlib, on purpose: kept
  out of the build stages' closure), so the hull's stamp and produced-cache key (cache.code_units, depth 1 / 2) miss
  headfit.contours / hidden_outline: face7's headfit commits changed Clawd's face carve without changing the key.
  Any branch whose edits rebuild Clawd's hull will see these moves against a cached baseline. Fix (coordinator's call):
  name head_sections' runtime deps in the hull's key (e.g. the produced entry's code list), which rebuilds every copy's
  hull once.

## Generality report, round 2 (public summary; the private report: charkit/private/c3/report/report.json)

The second character's first full builds (references in, rigged model out, no per-character tuning, no MakeHuman
fallback): b1 (the body on the clothed hull) and b2 (fixes 18-20); b3 (all fixes, 18-25) building.
- Stages (charkit/private/c3/report/stages.json, 21 stages): ran unchanged 2 (reference generation, the clothed hull);
  generic fix landed 13 (palette, sheet and head detection, refcheck, layerref, spec colours, body window, outfit
  masks and graph, the body hull, the code body, the head fit's jaw, the hull hair's colour, the QA parts' sheets and
  scale, the review page's design); missing builder built 3 (facial hair, garments by drafting, crown and pin); Clawd
  assumptions remaining 6 (below).
- QA pass share (PASS / (PASS + WARN + FAIL + errored parts)), checks named for Clawd's pieces apart:
  | build | all | applicable | Clawd-named | checks |
  | --- | --- | --- | --- | --- |
  | c3 b1 | 0.43 | 0.41 | 0.50 | 188 |
  | c3 b2 | 0.49 | 0.44 | 0.69 | 190 |
  | Clawd (g7_base) | 0.74 | 0.76 | 0.73 | 708 |
  The earlier attempt (2026-09-30) read 0.30 with nothing reaching the model.
- His references reached the model (numbers in the report): the code head from his head sheets (the jaw from the
  beard-free redraw), the body from his base body sheet (shape IoU 0.875 / 0.813 / 0.942 / 0.863), the hair and beard
  cut from his clothed hull, his palette in every colour, 7 garments and 2 accessories drafted from his outfit graph and
  masks (crown points and the pin's emblem from their own sheets).
- Remaining overfit points, ranked: (1) the face measure's skin flood stops at drawn folds: the chin read at the nose,
  the beard starved; (2) hair under headwear: the hull's head top is the crown, the hair's declared shape truth unread;
  (3) face features (eyes, lashes, blush, brows) are Clawd's defaults with no 2D rig; (4) QA checks named for her pieces
  and parts reading her objects (motion's clawd_skin); (5) slim-body garment drafts, her skirt hem, no drape/knot/strap
  templates, plain crown spikes; (6) the joined shoulder's absolute-L knobs; (7) hairlayers' fixed families; (8) hands
  (template, handref cuffs); (9) eye checks calibrated on large eyes; (10) the review page's regions; (11) MakeHuman
  legacies in the code path: mh.VRM_JOINTS (the joint names) and base_anime's SOCKET / CAVITY (hm08's eye and mouth
  rings); (12) infra: the produced hull's key misses head_sections' runtime imports.

## Exact next steps

0. (round 2, in flight) the gate of b39d996b (job gate-char3-1001-153423-9793 on render2, log
   charkit/private/c3/out/gate2.log; report into charkit/out/gate); b3 (job build-char3-1001-153450-356d on render2,
   log charkit/private/c3/out/b3_build.log, out charkit/private/c3/out/b3); s1, the joined shoulder (job
   build-char3-1001-151614-f06c on the build box, out charkit/private/c3/out/s1). When b3 lands:
   `python charkit/private/c3/review/build_page.py charkit/private/c3/out/b3 ~/animation-pipeline-garments4/charkit/out/g7_base --before charkit/private/c3/out/b1`,
   then `python -m charkit review page charkit/private/c3/out/review_build/page.json --out charkit/private/c3/out/review_build/page`.

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
