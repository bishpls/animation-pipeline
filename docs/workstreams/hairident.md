# hairident: cross-view lock identity for the hair (tool/hairident)

Worktree `~/animation-pipeline-hairident`, branch `tool/hairident` from tool/hairshell3 feee7702 (the lock-shell code:
det fit, per-vertex skin clearance, speckle hair_noise). Brief: `~/animation-pipeline-3d/charkit/out/coord/brief_hairident.md`
(read all of it: step 0 done by tool/hairtruth; the held-out-view check; the shadow-edge check's clean reading from
tool/hairtruth-art is this round's to land). Harness `tools/hairident/`, outputs `charkit/out/hairident/`.

## State
- Merged pipeline-3d 241f0547 (the hair truth without the clips; conflict in charkit/steps/qa3d.py: both sides' steps
  kept) and tool/hairshell3 08afe00f (the default switch reverted: no lock_shells, no shade_ellipsoid on the default).
- **Step 1 done: the labelling tool** (`charkit/label.py`, `charkit/labelui.html`, `python -m charkit label serve
  TASK.json` / `label status TASK.json`; tests `charkit/tests/test_label.py`; headless driver `tools/label/drive.mjs`:
  Chrome's DevTools protocol over Node's own WebSocket, real key/mouse events, screenshots). Generic task format
  (charkit-label-task/1: views, regions as index masks or polygons, items with a home region and per-view proposals
  with reason and confidence); answers (charkit-label-answers/1) written on every click (atomic replace) with a history
  (undo), resume at the first open item; 127.0.0.1 only.
- **The hair identity task** (`tools/hairident/mktask.py`, regions `tools/hairident/regions.py`): 21 locks in three
  groups (8 side locks, 6 side flicks and strands, 7 back hem flicks); regions per view = the lock truth's named locks
  (side_locks, lower_back, flyaways) + the splitter's locks over the rest of the side-lock / lower-back hair (>= 0.006
  L^2; the three-quarter, without family masks: from 0.25 L above the eye line down); proposals from the hull's
  projection (lockshell.envelope_points on round 2's context `charkit/out/hairident/ctx_r2.pkl`, copied from
  hairshell2's ctx_shells_r.pkl; visible within 0.04 L of the front-most envelope), tip heights, the splitter's layer
  ranks, and the lock truth's names as a second opinion (where they disagree the confidence drops). Inputs:
  `charkit/out/hairsplit/inputs.pkl` (the splitter's cached inputs, copied from ~/animation-pipeline-hairshell).
- **Michael's page:** server running (PID in `charkit/out/hairident/label/server.pid`, log `server.log`) at
  http://127.0.0.1:8770/ ; answers -> `charkit/out/hairident/label/answers.json`. Restart:
  `python -m charkit label serve charkit/out/hairident/label/task.json --port 8770`.
- Tested: 5 server tests (save at once, atomic, resume, undo, skip, bad input refused, 127.0.0.1); screenshots of every
  state (start, accept, pick mode, hover across views, picked, unsure, skip, undo, back, resume after reload, final
  screen; 1600x1000, 1440x900, 1280x800) in `charkit/out/hairident/label_test/shots*`; a keys-only pass of all 21 locks
  (Enter each) 12 s.

## Michael's first pass (2026-10-01, ~13 min): 21 / 21 locks; views accepted 35, fixed 3, hidden 22, unsure 3
His flag (via the coordinator): lock 7's profile lock exists inside the back mass the splitter never segmented, so the
page had no region to click: some 'hidden' / 'unsure' answers are "present but unsegmented". Asked: (1) a point mark
answer in the tool, a short second pass (every unsure; every 'hidden' where the hull's projection says mostly visible);
point marks scored as location truth; (2) a lock-delineated hair reference (Michael authorised up to ~4 image calls,
n=2, same model and tooling, ledger): the head turnaround's three-quarter, profile and back redrawn at the same pose and
scale with every lock's boundary inked, not exploded; refcheck before it is an authority; if it passes: register,
re-split, fold the back-mass locks into the second pass.

### The lock map reference: the pass rule (declared before the calls)
Prompts: `charkit/out/hairident/refgen/prompts.py` (`hair_lock_map_lines`: the sheet redrawn with the hair one flat
orange cut into closed locks by ink lines; `hair_lock_map_colours`: each lock its own flat colour), ref
head_turnaround, gpt-image-2.5-sunburst 2560x1440 high n=2. History: tool/hair5's `hair_lock_lineart` failed (open
strokes, 10-22 closed regions per view, no structure the turnaround lacks; its prompt told it NOT to cut the smooth
masses). A view passes when all hold (three-quarter, profile, back; front reported):
1. silhouette: hair IoU >= 0.80 against the turnaround's hair on the design grid after registration (shapetruth's:
   the eyes, then scale +-4%, shift +-0.04 L), the views' scales within 5% of each other;
2. structure the turnaround lacks: the back view's hair below the buns cut into >= 6 closed regions of >= 0.01 L^2,
   >= 5 of them reaching >= 0.3 L up from the hem; the profile's back mass (behind the side locks) >= 4 such regions;
3. agreement with the drawn locks: each of the back's 7 hem-flick truth regions >= 70% inside one region of the
   redraw, >= 5 of the 7 in different regions; the turnaround's drawn lock lines recalled >= 0.5 within 2.5 px.
Registered (structure only; placement stays the turnaround's) for the views that pass; else reported, not registered.


### The lock map reference: result (3 of ~4 calls; 1 left, kept: no materially different approach for the back)
Refcheck `tools/hairident/lockmap.py` (registration of a head-sheet take on the design grids by the hair's silhouette;
its locks as regions: `lines` the flat orange's components, `colours` flat colour fields; `--sheet body` for a take
drawn on the body sheet's canvas; `--swap A:B` the known-bad: views mislaid FAIL in the swapped views).
| take | 3q / profile / back hair IoU | back: flicks inside one lock (distinct) | profile back-mass locks | lines recalled 3q / P / B (floor) | pass |
|---|---|---|---|---|---|
| lines 1 (head sheet) | 0.90 / 0.93 / 0.93 | 3 (3) of 7 | 12 | 0.70 / 0.71 / 0.65 (0.29-0.38) | 3q, P |
| **lines 2 (registered)** | 0.90 / 0.93 / 0.93 | 2 (2) | 9 | 0.74 / 0.76 / 0.63 (0.31-0.40) | 3q, P |
| colours 1 (flat fields) | 0.85 / 0.92 / 0.92 | 7 (7) | 11 | 0.41 / 0.47 / 0.34 (0.26-0.29) | none |
| colours 2 | heads not found | | | | none |
| body sheet in place 1-2 | 0.68-0.71 / 0.73-0.75 / 0.83-0.87 | 2-5 | 6-7 | 0.05-0.11 (0.07-0.13) | none |
The colour take's first reading (k-means) passed 3q/P/B, but its fragments made boundaries dense (floor 0.34-0.48):
read as flat fields it fails the 0.50 line recall. Ceiling: head_turnaround's own ink recalls only 0.42-0.46 of the
body turnaround's drawn lock lines. Registered: `hair_lock_map` (lines take 2) for the three-quarter and profile
(manifest, structure only; sha in provenance: no produced reference restamped). The back: not registered.

### Michael's second pass (12 locks, 18 views, 4 min): no points used; S52.1 / S57.1 profile -> the lock map's M:8.5;
flick_R1 / R2 / under_bun_R back -> the truth's names (pass 1 said hidden); S55.1 3q -> S:44; flick_L2 back -> flick_L2.
Folded: `charkit/refs/clawd/hair_lock_links.json` (tools/hairident/truth.py: 21 items, 63 views: 32 regions, 31 not
visible; polygons on the design grids; held out, scoring only).

### Step 1: the ribbon test (`charkit/out/hairident/rib1/ribbon.md`, hi_hull's context, 16 locks Michael's pass 1 accepted)
| template | locks all views <= 4 px | pairs <= 4 px | 3+ views <= 4 px | home view's rise px | other views joint / alone px | joint IoU |
|---|---|---|---|---|---|---|
| tube (the pilot's) | 1 | 5 / 32 | 0 / 5 | 4.05 | 11.5 / 4.6 | 0.381 |
| flat ribbon (depth 0.15) | 0 | 3 / 32 | 0 / 5 | 4.10 | 11.8 / 4.6 | 0.372 |
| twist along the lock | 1 | 5 / 32 | 0 / 5 | 4.23 | 11.6 / 4.6 | 0.384 |
| tip curl | 1 | 4 / 32 | 0 / 5 | 4.28 | 11.7 / 4.5 | 0.368 |
| ribbon (all three) | 1 | 4 / 32 | 0 / 5 | 4.17 | 11.7 / 4.6 | 0.372 |
| **tube, envelope depth freed** | 6 | 14 / 32 | 0 / 5 | 2.17 | 8.3 / 3.4 | 0.454 |
| ribbon, depth freed | 6 | 15 / 32 | 0 / 5 | 2.15 | 8.2 / 3.5 | 0.442 |
Reading (canonical rule step 1): the template's shape is not what fails (flat / twist / curl change nothing); the
envelope's depth pull is ours (each view's lock pulled onto the hull's first surface: freed, pairs fitting 5 -> 14 of
32, the home view's rise 4.1 -> 2.2 px). No template fits three views: the three-quarter is drawn view-dependently
(`charkit/out/hairident/az1/az3scan.md`, depth freed: the ahoge fits front + 3q + profile best at a 25-30 deg turn
(1.2 px), the bangs at 20-30, but the side locks need 55-65 (L_jaw 1.9 px at 65, 10 px at the sheet's 35.5) and the
strand under the bun 60): step 2 (the reference is view-dependent there), so step 3 (compromise: the three-quarter
weighted down, per-view costs reported).


## Step 3: the joint fit (charkit/geom/lockident.py; opt-in: lock_shells `ident`)
Each lock's 3D path decided once (the primary views' targets fitted alone), then rounds of: per view, every family's
drawn targets matched to the locks at once (Hungarian with a dummy column at `assign_max` px: a lock may stay
unassigned; the splitter's T-junction ranks as a constraint: a flipped pair pays `layer_w`), each lock refitted with
its assigned views (`depth_two` 0: the envelope's depth pull off once two views place it; a join costing more than
`join_cost_max` px, or raising the primary past `primary_slack`, dropped for the round); a later primary view (the side
locks' profile) seeds locks only from the targets the first round left over. Where a lock's depth isn't placed yet the
assignment lets its projection slide sideways by `depth_sigma` L x |sin(views' angle)| (the hull's depth is a guess:
the oracle check on the side locks put the right target first in 6 of 9 links with the slide, 3 of 9 without).
Scoring (`tools/hairident/ident.py`, against charkit/refs/clawd/hair_lock_links.json): a lock is an item's when its
home-view target covers 30% of Michael's home region; per answered view right / wrong / missing (positive links),
right / extra (not visible), points covered within 3 px; items no fitted lock covers are `unmatched` (coverage).
Held-out views: the fit on three views, the fourth assigned without a refit, scored there.

## Extending region by region (after this round; each a real build against the hull, the guard per view)
1. Side locks (this round): the identity fit's shells; the three-quarter weighted 0.5 (drawn view-dependently).
2. The back's hem flicks, both sides (phi [90, 270] as two groups): needs the back's lock structure (the lock map's
   back failed: its hem isn't the body sheet's); the canonical rule's compromise: the hem's targets the splitter's cells
   (`unit: 'cells'`), the flicks' identity from the back to the profile only (the three-quarter shows the hem edge-on).
3. Bangs: over their wedges (`under: ['bangs']`), front primary, the profile joined through the assignment (the truth's
   bangs names are read across front / three-quarter / profile, so their links can be scored once Michael labels them).
4. The upper back: the lock map's profile locks as the profile's targets (registered for the profile), the back's
   stripes from the crown as the back's; the identity across profile and back by height and side.
5. The hooked hem: the tip curl (lockshell `tip_curl`, tested here: it doesn't help the side locks, which don't hook) on
   the hem groups, fitted to the back's lobes and the profile's J hooks.
6. The ahoge: its fitted template stays (it fits front + three-quarter + profile within 1.2 px at a 25-30 deg turn).


## Results (2026-10-01, end of session)
**Joint fit, against Michael's links** (hi_hull's context; `charkit/out/hairident/grid{2,3,4}/grid.md`; positives =
links to a drawn lock: right / wrong / missing; not-visible links all right in every row, 14 / 0; 33 views belong to
items no fitted lock covers: the flyaway strands and the hem's right side, outside the pilot's families):
| fit | locks in 2+ views | positives right / wrong / missing | held out 3q (in fit: same) | held out profile |
|---|---|---|---|---|
| the pilot's association (greedy) | 2 of 17 | 1 / 1 / 14 | - | - |
| A: compromise (joins over 12 px dropped) | 7 | 4 / 2 / 10 | 3 / 2 / 4, IoU 0.17 | 2 / 1 / 3, IoU 0.16 |
| B: every assigned join kept | 10 | 6 / 2 / 8 | 3 / 2 / 4 | 2 / 1 / 3 |
| **B2: B + held inside the figure where it faces away (the candidate)** | 10 | 5 / 3 / 8 | 3 / 2 / 4, IoU 0.17 | 2 / 1 / 3, IoU 0.17 |
(Held-out front: only 1 positive link is testable; back: none (no fitted lock's home there but the hem group's,
whose links are all not-visible).) Michael's link accuracy on positives: pilot 0.06 -> candidate 0.31-0.38.
**Builds** (render2; pre-merge head 4b..; QA tables `python tools/hairident/hairtab.py ...`): hi_ident (A) and
hi_identB (B) both trip the guard on the lower back's profile (0.664 -> 0.528 / 0.465, -20% / -30% against the hull):
the joined side locks and the hem flicks, free in depth, spread over it in profile; and a right side lock stood out in
front of the profile's face (fixed by contain_all, B2). Six placements (clean reading, `term6/t6a.json`): hull 3.211 /
3.33, pilot 1.890 / 2.10, A 1.759 / 1.98 (peeks 22 / 18.8 against 16 / 15.8). 52-lock truth: hull 0.351, pilot 0.403,
A 0.382, B 0.388. hair_back_lines: hull 0.932 W, pilot 0.584 W, A 0.499 P, B 0.165 P.
**The shadow-edge check landed** (merged tool/hairtruth-art: artifactqa.HAIR_SHAPE_TRUTH True): art_terminator_hair
and art_peeks_hair recalibrated on fresh known-bads (hi_torn: the hair's shading normals unsmoothed, 5.086 FAIL;
hi_gaps: the pilot's shells without overlap, 29 FAIL), the design 1.0 / 0 PASS, today's default 3.211 / 16 (grade
FAIL, status WARN: the art checks' cap); the design's measures stored (artifacts_design.json, stamp b7f5df42).

## Next steps (exact)
1. Michael reviews the board (`python -m charkit label board charkit/out/hairident/board`; built from hi2_hull,
   hi2_pilot, hi2_cand on the merged head, grid5's held-out projections, term6 on those builds).
2. **The default switch** (only on his yes, and only once the guard holds): set
   `hair.shape.pieces_opts.lock_shells = tools/hairident/ident_B2.json` and `hair.shape.style = {shade_ellipsoid: 1.0}`
   in charkit/spec/clawd.json and its alias clawd_body_pieces.json; first fix the lower back's profile (the guard):
   keep the hem group out of the profile joins (ident `join_views` per group: back only) and hold joined side locks to
   their family region in the joined view (contain_family on the joined views, contain 5); measure on a render2 build
   with hairtab.py (every piece per view against the hull, -15% line) and term6all.py; then pregate --box auto and
   `python -m charkit remote gate tool/hairident --into pipeline-3d` (expect: art_terminator_hair improve, back_lines
   improve, scalp_px 4 -> ~65 W (reported), hair_folds up, CPU: the joint fit's rounds add ~1-2 min to pieces_hair,
   check the 1.5x line cold against cold). tool/hairstrokes waits for the switch (its strokes sit on the locks).
3. **The back** (no registered lock map there): the canonical rule's compromise: the hem's targets the splitter's
   cells (unit 'cells'), identity back <-> profile only; or one more image call (1 left of ~4) only with a materially
   different approach (the body sheet edited in place failed on silhouette; the head sheet's back hem isn't the body
   sheet's).
4. **Region by region** (each a render2 build against the hull, the guard per view, Michael's links scored): see
   "Extending region by region" above; the bangs and the upper back need their links labelled first (`python -m
   charkit label serve` on a new task from tools/hairident/mktask.py with the bangs' and upper back's items).

## Plan (the brief's order)
1. `python -m charkit label serve TASK.json` (charkit/label.py, generic) + the hair identity task (~20 locks: side locks,
   back flicks; tools/hairident/mktask.py) -> hand the page to the coordinator.
2. While Michael labels: the ribbon template test (flat section, twist, tip curl) on the pilot's locks.
3. The joint fit with assignment across views; scored on Michael's held-out links + held-out views; sweep optimize.
4. Review page, the default switch (shells from the cross-view fit) with every hair check, pregate, gate.

## Jobs
- Box builds on render2: `charkit/out/hi_hull` (today's default), `charkit/out/hi_pilot` (tools/hairident/pilot_spec.json),
  `charkit/out/hi_torn` (tools/hairident/torn_spec.json: the torn-shadow known-bad; running).
- Joint-fit grid `charkit/out/hairident/grid2` (tools/hairident/grid2.json on hi_hull, holdout of A; running).
- Label servers (laptop): pass 1 port 8770, pass 2 port 8772 (PIDs in charkit/out/hairident/label*/server.pid).
