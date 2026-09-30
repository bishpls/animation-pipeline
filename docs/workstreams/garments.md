# Garments as pieces (tool/garments)

## Checkpoint: end of round 3 (2026-09-29). Start here.

**Branch** `tool/body` in `~/animation-pipeline-body`. The head is the commit that adds this section (see
`git log -1`). It contains `pipeline-3d` f3e8747 (merged at a456834). Round 2 is merged into `pipeline-3d` at 76d5bdc.
The authored specs are `charkit/spec/clawd_body.json` (tracked) and `charkit/out/remote/clawd_body_pieces.json`
(gitignored; it carries the same garment edits; the box sync includes `charkit/out/remote/*.json`).

**Gate state** (both into `pipeline-3d` 966ad22, on a456834, before the refit at be410e0):

| gate | verdict | detail | report |
|---|---|---|---|
| default spec | **PASS** | | `charkit/out/gate/gate_tool-body_a456834_into_966ad22.md` |
| `--spec charkit/spec/clawd_body.json` | **FAIL** | one check worse: `body_back_iou_skin` 0.731 PASS → 0.671 WARN (the flap tails hid the backs of the thighs) | `…_into_966ad22_clawd_body.md` |

The flap refit at be410e0 targets that failure: the evaluator reads 0.728 PASS. It hasn't been box-built or gated
yet. **Next step: box-build and re-gate both specs.**

**Round 3 box numbers:** `charkit/out/body3` (clawd_body.json, a456834's garments, before the refit).

| | check | round 2 | round 3 |
|---|---|---|---|
| Boots | `body_{front,back}_leg_gap` | 0.108 / 0.127 L FAIL (bridge at z −5.19 … −5.32) | 0 PASS |
| | `boot_step` (all four) | | ≤ 0.005 L PASS |
| | `piece_boot_L` / `_R` | 0.804 / 0.838 | 0.863 / 0.894 |
| Poke | `poke_share` | 0.0203 FAIL | 0.0134 WARN (wrist cuffs 44 / 37 → 0) |
| Skirt | `front_skirt_width` | 0.795 FAIL | 1.047 PASS |
| | `three_quarter_hem` | WARN | 0.0235 PASS |
| | `back_skirt_width` | | 1.102 WARN (remeasured) |
| | `front_skirt_aline` | | 0.001 PASS |
| | `three_quarter_skirt_aline` | | −0.219 FAIL (see below) |
| | `piece_skirt` | | 0.804 |
| Flaps | `piece_overskirt_panel_L` / `_R` | 0.451 FAIL / 0.526 WARN | 0.348 / 0.453 FAIL |
| | `_extent` L / R | | 0.075 / 0.042 PASS |
| | `_hang` L / R | | 0.083 / 0.095 PASS |
| Other | `body_profile_chest` | | 0.036 WARN |
| | `waist_skin` (all views) | | 0 |
| | wrist cuffs L / R | | 0.403 / 0.774 |

- The piece checks for the skirt and flaps are registered as *remeasured* (same-colour layers), but the flaps'
  geometry changed at the same step. Don't read "remeasured" as neutral.
- The refit (be410e0) in the evaluator: flap fit 0.234 → 0.329, with front 0.61 / 0.67, back 0.50 / 0.64,
  three-quarter 0.23 / 0.44, profile L 0.13.
- The review renders are on the render box's output: `charkit/out/body3_render/sheet_body.png` (the design over
  ours at 0 / 35 / 90 / 180). Its `boards/` came back empty; find out why before relying on it.
- Round 2's page is `charkit/out/review_body2/index.html`. Round 3's generator is `review3.py` in the old session's
  scratch folder, which is lost. Rebuild it from `review.py`'s pattern: the design over ours at four views, a
  MakeHuman / checkpoint / round 2 / round 3 table, crops of the boots and flaps.

**Not done: the 2 × 2 the coordinator asked for.** Score round 2's flap geometry (template panels under the skirt,
clawd_body.json at 849b9a7) and round 3's (be410e0) under both the old measure (the graph's old layer: panels
*under* the skirt) and the new one (panels *over* it, the same-colour rule in `bodymeasure.piece_shapes`). The rule
fires only when the graph's `layer.over` holds the same-coloured piece, so toggle the overskirt entries' `layer`
in a copy of the graph. Keep the masks. Then judge the flaps against the design views on the page: Michael's
complaint was "too small, tucked under", so the render comparison outweighs the piece IoU.

**Chain ownership** (one owner per stage, keeping stages cacheable):
- garments shapes the flap and defines its chain's path as data;
- tool/rig makes the bones and weights in the rig stage from the outfit graph's `springs`;
- tool/motion simulates and exports them.

`garments.flap` no longer adds bones (that made the garments stage uncacheable). It rides `hips` rigidly and
returns `chain` (bone names `overskirt_panel_L_0`…, joints, per-vertex arc length). `charkit/flapchains.py`
(`python -m charkit flapchains SPEC [--build DIR]`) writes each flap's chain into the notes as `chain`, then
relayers. `outfit.apply_notes` puts a noted `chain` into the graph's springs.
- **Its bug:** notes entries aren't all one line (lines 19, 22 and 26 span several), and `write()` parses line by
  line. It raises before writing anything. Fix: parse the whole file, set `chain`, and re-emit only the flaps'
  entries.
- Until it runs, the graph's overskirt chains are the design's (a vertical drop at the hem's radius). Tell tool/rig
  once they're written.

**Open items:**
1. **The flaps.** Box-build and gate the refit; the 2 × 2; three-quarter is still weak because the drawn tails show
   broad beside the legs and ours sit behind (try letting the tail roll outward like a flag, then refit). The tails
   are 0.40 L from the legs, which is ample for colliders.
2. **The collar onto the neck's flare.** tool/face made the neck slender, flaring into the shoulders
   (`code_base._join_neck` in their worktree, not merged yet). Our collar rides up to the torso's top ring like a
   turtleneck; the design lays a sailor collar on the shoulders and chest. Seat it on the flare: a hull-lofted
   collar, or seat the template on the body's surface below the neck. Coordinate against tool/face's branch.
3. **Torn collar tips and bow edges** near the neck in three-quarter and side views (jagged fragments). Measure
   them: small disconnected fragments per piece and outline roughness against the design's. An artifact-measurement
   workstream will provide a shared detector. Then fix them; the likely cause is near-coincident surfaces between the
   collar, bow and top.
4. **The loft on marginal coverage:** done (2c01410). `loft.field` lets the best rows stand in, warns, and records
   `LOW_COVERAGE`; the build keeps `charkit_coverage` on the object and QA reports `garment_coverage` (INFO). Still
   to confirm: a render-box build of clawd_body.json that used to die in garments.
5. **Wrist-cuff clearance:** done (cec59df). `band_hull` clears the skin by 0.006 L plus its thickness. The left
   wrist cuff's piece score is still 0.40 FAIL: the drawn cuffs are boxy, and rounding costs silhouette score.
6. **Waistband (0.45 FAIL) and shorts (0.42 FAIL):** not started.
7. The three-quarter skirt A-line (−0.22) goes with the flaps: at the hem the design's rows are widened by the
   drawn tails, which ours hide from that camera.

**Gotchas:**
- `charkit/out/hull/clawd` and `charkit/out/clawd/outfit` were hard-linked across five worktrees until 18:08, so one
  worktree's rebuild wrote through to all. They're private now, rebuilt here from this worktree's code (hull 18:18,
  outfit 18:19). Evaluator numbers from before then may differ from box builds.
- Box builds build their own hull and outfit from code plus tracked notes (the sync leaves gitignored files at home,
  except `charkit/out/remote/*.json`), so graph edits must come from `outfit.py` and the notes. That's why chains
  go through the notes.
- The render box needs `infra/gcp/render.env` (gitignored). It was copied here from `~/animation-pipeline-3d`.
- Hull labels differ by about 3% between machines at piece boundaries (a hull-determinism workstream is on it). The
  loft now degrades rather than raising.
- Gates run in parallel on `pipeline-3d` ≥ f3e8747. A non-default spec's report ends in `_clawd_body.md`.
- Interactive git (`git add -p`) doesn't work here: commit whole files.
- Fast evaluator loop: build a `bodyeval.Evaluator` on clawd_body.json with `head_code` / `body_code` from a build's
  `geom/` (e.g. `charkit/out/body3/geom`). Then run `E.geometry(spec=…).bundle('viewport')`,
  `bodymeasure.piece_views`, `piece_shapes`, `qa3d.grade_pieces` and `bodymeasure.sheet_body`: about 20 s per run,
  about 0.5 s per flap candidate when only the flap objects are swapped in a cached bundle.
- The poke proxy on the evaluator's bundle (qa3d.poke's rays against the masked skin) overcounts against the build
  (skirt 780 against 153) but ranks changes correctly.

## What changed

Each outfit piece can take its shape from the visual hull (`source: "hull"` on a garment spec), rather than from the
MakeHuman body's section at a knob's height. The design's 3D shape comes from the hull, the piece's topology from its
template, and the body supplies only weights (and, for a tight shell, the surface under it).

- `garments.hull_pieces`: the hull aligned by its eyes, as the build aligns its target, split by the hull's
  per-vertex outfit pieces.
- `charkit.geom.loft`: a piece as a radius field r(t, θ) around its own axis. It's measured from the hull's points,
  filled where no view shows the piece, smoothed with a numpy Gaussian (the builders run in Blender's Python, which
  has no scipy), and lofted into a closed quad grid.
- **Builders:**
  - `belt_hull`: the waistband. It hides the torso across its height, because the body stands out of the design's
    waist by up to 0.12 L at the sides.
  - `skirt_hull`: a waist line and a hem per angle. The waist is tucked under the band and the back hem is longer.
    Knife pleats go on top.
  - `panel_hull`: an open overskirt panel over its own angle span.
  - `bow_hull`: sized and placed from the hull, then wrapped onto the hull's front (`front_surface`).
  - A hull-sourced shell (the top) is cut at the hull's lower edge per angle.
  - `conform`: lays a thin piece onto its hull points. It's available, but off for the collar; see "Blocked".
- The bundle carries the target's per-vertex pieces (`bundle.target_pieces`).

## Measurement

- **QA part `sheet_pieces`** (checks `piece_<id>`): every object is z-buffered with its own index, and each outfit
  piece is compared with the drawn piece mask per view.
  - Graded: `iou_tol`, the overlap with a drawn line's width either side of the drawn outline left out, in the
    piece's worst view. PASS ≥ 0.75, WARN ≥ 0.5.
  - Beside it: the plain IoU, the outline agreement, and where the drawn piece's pixels land in ours (confusion).
  - A piece we don't build (the bodice panel, the bow's tails) is compared as part of its parent.
  - `piece_built` counts the pieces we do build.
- **QA part `pieces_3d`** (checks `piece3d_<id>`, INFO): each piece against the hull's points of that piece. It
  reports reach (where the design has the piece, how far ours is), excess, and the height offset.
- **Review page:** `python -m charkit pieces BUILD [--against OTHER]` gives, per piece and view, crops with the drawn
  piece tinted, its outline red and ours white, plus the numbers.

## Results (box builds, merged at 8f2ec5d: knob garments vs the waistband, skirt, top hem and bow from the hull)

| check | knob garments | hull-sourced |
|---|---|---|
| PASS / WARN / FAIL | 49 / 28 / 33 | 54 / 32 / 24 |
| body_back_hem_mid | −0.207 FAIL | 0.028 PASS |
| body_back_leg | −0.249 FAIL | 0.038 PASS |
| body_front_hem_mid | −0.089 WARN | 0.061 PASS |
| body_profile_skirt_width | 1.291 FAIL | 0.879 WARN |
| body_front_skirt_width | 1.077 PASS | 0.953 PASS |

The piece checks (iou_tol weighted over the views), both builds graded the same way by `charkit pieces`:

| piece | knob | hull |
|---|---|---|
| skirt | 0.50 WARN | 0.77 PASS |
| bow | 0.24 FAIL | 0.58 WARN |
| collar (knobs in both) | 0.53 | 0.61 |
| top | 0.29 | 0.47 |
| waistband | 0.00 | 0.40 |
| shorts (they now show below the hem) | 0.00 | 0.20 |
| overskirt panels (knobs in both) | 0.26 / 0.26 | 0.37 / 0.37 |

In 3D (piece3d, the median reach to the hull's piece), the waistband is 0.008 L, the skirt 0.009, the bow 0.036, the
sleeves 0.04, the boots 0.035. The cuffs (0.25), the shorts (0.35) and the overskirt panels (0.27–0.33) are the far
ones.

## Blocked: the body

A piece lying on the body at the design's surface ends up inside our body. The MakeHuman body isn't the design's:
- its waist sits about 0.3 L low;
- it's up to 0.12 L wider at the sides;
- its back stands out.

Conforming the collar to its hull points halved its 3D distance, but it vanished from the back view (0.72 → 0.01),
buried in the top, which is a shell of the body.

The loose pieces (skirt, waistband, bow) work because they sit outside the body or hide it. The collar, a hull-true
top, the sleeves and the cuffs need the authored body fitted to the hull first, the body's counterpart of the code
head. `geom.loft` is the tool for it: the torso as a field around a vertical axis, and the limbs around their bones.

## Not done yet

- **Overskirt panels:** lofted from the hull (`panel_hull`, not on in the spec), they reach within 0.045 L in 3D, but
  their 2D views are mixed. The hull labels the panels over about 90° round the back sides: the skirt's back shares
  their colour and stepped hem, so the labelling can't split them.
- **Shorts:** the hull's "shorts" points aren't the shorts' shape. The hull fills the hollow under the skirt, and the
  drawings' dark shorts below the hem label that filled surface. Only their lower edge (−2.72 L) is trustworthy, so
  the shorts need the 2D target.
- Sleeves and cuffs lofted around their bones, the collar, and the boots.
- The drape solver on the style profiles.

## On the authored body (tool/body, 2026-09-29, second round)

Found in the checkpoint render (1c57bb0) and by measuring. Evaluator numbers are on `clawd_body.json`, checkpoint →
now:

| piece | checkpoint | now | what changed |
|---|---|---|---|
| bow | 0.305 (hidden behind the top) | 0.646 | See the bow notes below. |
| collar | 0.407 | 0.756 | Raised to the drawn neckline (rise 0.15, v_depth 0.5, v_half 40). It had started at the neck bone's head, 0.23 L low. |
| top | 0.425 | 0.63 | The front panel is a second material by face, from the hull's bodice-panel footprint (symmetric, stray labels dropped). It had been a texture through the MakeHuman UVs, which broke into a cross. |
| wrist cuffs | 0.32 | 0.43 | `band_hull`: a band lofted round its bone through its hull piece. |
| sleeves' cream ends | 0.24 | 0.63 | `band_hull`. |
| boot cuffs | 0.52 | 0.87 | `band_hull`. |
| boots | 0.72 | 0.81 / 0.83 | `shoe_hull`: the boot's foot lofted from above the ankle to the sole. The template shoe had ballooned. |
| overskirt panels | 0.405 / 0.675 (scraps) | 0.45 / 0.52 | See the panel notes below. |
| skirt | 0.864 | 0.814 | Its hem is filled where the panels hide it, across the back (70–180°). |

The bow:
- The torso stays behind the bow and its tails by their measured depth (the hull shows them 0.02–0.06 L proud of the
  chest). Only the bow points inside the drawn bow's extent count, because the hull labels part of the lapels as bow.
- The bow takes its size from its drawn extent (`drawn_extent`, from the outfit graph).
- Its lobes are flatter (0.06 of its size), fuller at the knot (0.6), and lifted 0.03 L. The profile's front at
  −0.70..−0.80 L is now within 0.01 L of the drawing.

The overskirt panels:
- The hull labels them across ~90° of the back, and lofted they came out as twisted scraps.
- They're now the panel template, its knobs fitted to the drawn panel masks in the evaluator (iou_tol per view, plus
  the front view's reach: the lowest row and the outermost column).
- **Not fixed.** Rendered (body2_render), they read as dark, flat wedges hanging under the skirt. The design has orange
  flares with a narrow stepped hem, sweeping into a long train in profile. They also cost two grades on the authored
  spec: front skirt width 0.896 WARN → 0.795 FAIL, three-quarter hem PASS → WARN. What they should be is a taste call
  (one skirt with a longer stepped back and sides; flaps over the skirt; or flaps under it), set out on the review page.

Other fixes:
- **The waist.** The skin showing below the waistband was between the band and the skirt, not the top and the band.
  The skirt now starts under the band all round, where its own points had started lower at the front.
- **The skirt's front panel** takes the densest arc of its points (34°, not 58°).

Measurement: `body_*_skirt_width` now compares the rows neither figure has a hand against (registered in
`history.STEPS`). Each figure's widest free row had sat at a different height, because the hands hang differently.
The results, first in the evaluator, then in the box build (body2):
- profile: 1.23 FAIL → 1.00 PASS in the evaluator; 1.013 PASS in the build.
- back: 1.02 PASS in the evaluator, but **1.995 FAIL in the build**. There, no row is free of hands in both figures, so
  the check falls back to the old measure. The fix: when no row is free in both, measure ours on the design's free
  rows.
- front: 0.77 FAIL in the evaluator; 0.795 FAIL in the build. On the rows free in both, the drawn panels join the
  skirt's run and ours leave a gap. The panel change caused this (0.804 FAIL before the remeasure), not the measure.

## Box builds, round 2 (clawd_body_pieces.json; checkpoint `body_pieces` → now `body2_pieces`)

| check | MakeHuman (code_mh) | checkpoint | now |
|---|---|---|---|
| piece_bow | 0.521 WARN | 0.302 FAIL | 0.635 WARN |
| piece_collar | 0.504 WARN | 0.407 FAIL | 0.731 WARN |
| piece_top | 0.457 FAIL | 0.423 FAIL | 0.623 WARN |
| piece_waistband | 0.439 FAIL | 0.443 FAIL | 0.435 FAIL |
| piece_skirt | 0.784 PASS | 0.864 PASS | 0.803 PASS |
| overskirt panel L / R | 0.358 / 0.361 FAIL | 0.404 FAIL / 0.674 WARN | 0.451 FAIL / 0.526 WARN |
| sleeve's cream end L / R | 0.168 / 0.046 FAIL | 0.24 / 0.002 FAIL | 0.637 / 0.585 WARN |
| wrist cuff L / R | 0.175 / 0.177 FAIL | 0.321 / 0.332 FAIL | 0.443 FAIL / 0.85 PASS |
| boot L / R | 0.722 / 0.744 WARN | 0.722 / 0.567 WARN | 0.804 / 0.838 PASS |
| boot cuff L / R | 0.027 / 0.031 FAIL | 0.519 WARN / 0.446 FAIL | 0.875 / 0.823 PASS |
| poke_share | 0.02 WARN | 0.0165 WARN | 0.0203 FAIL |

The poke rise is all the hull wrist cuffs (wrist_L 14 → 44 px, wrist_R 0 → 37): `band_hull` has no clearance over the
forearm. The fix: take the larger of the loft and the skin's own field plus a margin, per row and angle.

The review page is `charkit/out/review_body2/index.html`, with renders at matching scale, the design above each, the
table and the pieces pages.

Gates, round 2:
- The default spec, tool/body 51c0733 into pipeline-3d ead7d5f: **PASS**. So does the merged head fb9d89c into
  ae55904 (`charkit/out/gate/gate_tool-body_fb9d89c_into_ae55904.md`).
- clawd_body.json, tool/body 51c0733 into ckpt/2026-09-29 35525d1 (pipeline-3d has no clawd_body.json): **FAIL**.
  Two checks got worse: body_three_quarter_hem (PASS → WARN, the panels) and poke_share (WARN → FAIL, the wrist cuffs).
  Nineteen checks improved a grade (`charkit/out/gate/gate_tool-body_51c0733_into_35525d1.md`). The gate lists
  body_front_skirt_width WARN → FAIL as "remeasured", but the panels caused it.

## Round 3 (2026-09-29): flaps over the skirt, boots, cuffs, the new checks

**The overskirt panels are flaps over the skirt** (Michael's call: separate pieces with their own physics).
- `flap()` (a `panel` with `source: flap`):
  - It lies on the built skirt from its waist (under the band) to its hem, 0.03 L plus its thickness off the pleats'
    crests.
  - Below the hem it carries on as a longer section of the skirt's cone. Each column continues the skirt's slope,
    tilted out and toward the centre back, and runs longer at the back edge. That gives a stepped diagonal in front
    and a train in profile.
  - Six bones run along its middle column (`overskirt_panel_L_0` … `_5`, the first from the waist to the hem with
    parent `hips`), weighted by arc length.
  - The tails stay 0.44 L from the legs.
- Fitted in the evaluator to the drawn panels in all four views, weighted equally: az 135°, width 0.8 L at the hem,
  narrow 0.1, length 0.4 L, train 1.0, out −0.4, sweep 0.3. The flap's pixels on the drawn skirt are left out, since
  the drawing can't separate them.
- Per view (L / R): front 0.58 / 0.57, back 0.43 / 0.48, profile 0.14.
- **Three-quarter stays weak (0.16 / 0.23).** From that camera the drawn tails show broadly beside the legs, while
  ours lie behind the skirt and legs. The views don't agree on one sheet shape. Next: let the tail twist outward
  (a flag's roll) and refit.
- The outfit graph now has the panels over the skirt, from the notes (`apply_notes`, also run by
  `python -m charkit outfit relayer`). Each spring chain names its bones.
- The piece checks leave out same-coloured layers: where a piece lies over another of its colour, those pixels count
  for neither (`px_same_colour`).

**The skirt as an A-line:** `aline` stops a column's radius narrowing toward the hem. A visual hull rounds the hem's
corners in, so the skirt read as a bubble. Front A-line FAIL → PASS. Three-quarter is still −0.22 FAIL: all its
rows have a hand against them, and at the hem the drawn tails widen the design's rows while ours are hidden.

**Boots** (`shoe_hull`):
- Each foot keeps 0.03 L off the midline. The hull had closed the gap between the feet at the sole.
- The top 0.12 L eases from the shaft's radius (the leg's skin plus the shell's offset) into the hull's section. The
  outline had stepped at the seam.
- Evaluator: leg gap 0 (round 2's box build: 0.108 / 0.127 L FAIL), boot steps ≤ 0.005 L, boots 0.86 / 0.89.

**Cuffs** (`band_hull`):
- They clear the skin by 0.006 L plus their thickness, taking the outermost skin point per cell (the thumb's base).
- Sections are drawn 0.3 of the way to their fitted ellipse, and the ends roll in.
- Wrist-cuff pokes 415 / 417 → 0 / 0 (evaluator).

**Loft robustness:** when no row reaches `min_row`, the best-covered rows stand in, with a warning. The garment
carries `charkit_coverage`, and QA reports `garment_coverage` (INFO).

**New checks** (registered in `history.STEPS`): `body_*_leg_gap`, `body_*_boot_step_{L,R}`, `body_*_skirt_aline`,
`body_profile_chest`, `body_*_waist_skin`, `piece_*_extent`, `piece_*_hang`, `garment_coverage`.
- `boot_step` compares against the design's cleaner side, because the drawing's shading splits one side's white.
- The skirt width's fallback now measures on the design's free rows.
