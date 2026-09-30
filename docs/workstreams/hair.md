# Workstream A: cut-piece hair (`tool/hair-pieces`)

Clawd's hair as authored pieces instead of the visual hull's one carved mass. `hair.shape.mode: "pieces"` in a spec,
or `python -m charkit build SPEC --hair pieces`.

## What was built

| Module | What |
|---|---|
| `charkit/hairlayers.py` | The generated hair breakdown turned into per-view family masks on the body sheet's hair: the manifest's produced `hair_layers` (`python -m charkit hairlayers SPEC`, page `charkit/out/clawd/hair/index.html`). |
| `charkit/geom/hairpieces.py` | The pieces: the hull's vertices labelled by family; the mass lofted on a chart round the crown and split into locks; buns, ahoge and flyaways. |
| `charkit/cli.py` `pieces_hair` | The venv-side build step, cached as the geom hair's is: `out/geom/hair_pieces/` (a part `.npz` per piece and `pieces.json`). |
| `charkit/scene.py` `hair_pieces_objects` | The Blender stage: one `hair_NAME` object per piece, with the hair's toon material and outline, rigged to the head, and the envelope normals transferred after the outline. |
| `charkit/qa3d.py` `hair_pieces` | The QA part: `hair_piece_<family>`, `hair_fringe_low`, `hair_fringe_gap`, `hair_penetration` and `hair_folds`. |
| `charkit/hairpage.py` | The review page (`python -m charkit hairpage BUILD --against BASE`). |
| `charkit/styles` `hair_pieces` | The construction's style settings: notch, thickness, inset, lock width, normals, and the shading envelope's close and blur. |

### The families: `charkit.hairlayers`

The breakdown is segmented by its legend: the nearest swatch in Lab, with the lower back's pink above the eye line
counted as the fringe's lightest tone.

It is registered onto body_turnaround's calibrated views:
- one scale and one eye row for all three of its views;
- fitted by FFT correlation of the hair (the buns' zone left out) and the face's skin.

Then each body-sheet hair pixel takes the nearest breakdown family, within the view's own figure. The buns are the
outfit's bun pieces.

On Clawd: 514 px/L, hair overlap 0.68 / 0.72 / 0.80 (front, profile, back) and face overlap 0.69 / 0.57. Two
generations of one design, so the partition comes from the breakdown while the silhouettes stay the body sheet's.

### The pieces: `charkit.geom.hairpieces`

**Labels.** Each hull hair vertex takes the family of the view that sees it most squarely. The profile is mirrored to
label her right side.

**The mass** (bangs, side locks left and right, upper and lower back) lives on a chart round the crown: theta from the
crown direction, phi round it from the front. On that chart:
- **Envelope.** The hull's outermost mass hair per cell, filled along theta and round phi, smoothed, and made round at
  the pole.
- **Not hair.** A cell whose outermost hull point is not hair (the face) is never covered.
- **Skin.** Our skin's triangles, sampled densely: the whole head above the chin, and below it what lies inside the
  envelope. Grown and smoothed.
- **Regions.** Each family's largest region, within what its name allows (the fringe in front, the back layers
  behind), cut free of thin bridges. The crown rows take the family below them.

**Locks.** Each piece's lower edge splits into locks at its notches, which are deepened by the style's `notch`. A lock
is a closed shell:
- its columns are sampled at absolute theta steps and stitched by ladder, so a jagged tip edge shears nothing;
- the outer surface is the envelope less the layer's inset, pushed out smoothly where the skin bulges past it;
- the inner surface is the style's `thick` below, tapering to `tip_thick`, smoothed over the skin's upper envelope and
  never within `gap` of it.

Each lock stores a strand direction per vertex and a chain of 6 joints from root to tip, for VRMC_springBone.

**Buns, ahoge, flyaways.**
- The buns are icosphere radius fields round their cores.
- The ahoge comes from the drawings' strokes: front x and profile y, paired by arc length.
- The flyaways are the front mask's strokes as planar blades.

**Shading.** Every piece shades from the whole hair's envelope (`smooth.envelope_normals` over the union, closed and
blurred as the style says), as the geom hair does. The locks read as one cel-shaded mass, told apart by their outlines.

## Measurements

These are from the merge gate: **PASS**. The report is `charkit/out/gate/gate_tool-hair-pieces_14dd9f0_into_6a576ce.md`.
The gate builds Clawd's default spec (the MakeHuman head) with the geom hair before and the pieces after. The review
page is `charkit/out/hair_review/index.html` (`python -m charkit hairpage`).

| Check | Geom hair (base) | Pieces |
|---|---|---|
| body hair width front / 3/4 / back | 0.877 / 0.905 / 0.890 WARN | 0.971 / 0.956 / 0.986 PASS |
| body hair width profile | 0.976 PASS | 0.962 PASS |
| body hair IoU front / profile / 3/4 / back | 0.829 / 0.783 / 0.762 / 0.920 PASS | 0.835 / 0.752 / 0.741 / 0.897 PASS |
| hair_noise | 0.1036 FAIL (old measure; 0.047 WARN as re-measured) | 0.0444 WARN (remeasured: no outlines, occluded) |
| scalp_px | 0 PASS | 5 PASS |
| sheet_shown front / profile / 3/4 | 0.584 / 0.331 / 0.504 WARN | 0.672 / 0.181 / 0.524 WARN |
| hair_piece_* (pooled IoU against the hair layers) | none | bangs 0.605, upper back 0.725, lower back 0.645, buns 0.655 PASS; side locks 0.482 WARN; ahoge 0.22, flyaways 0.21 INFO |
| hair_penetration / hair_folds / hair_fringe_low | none | 0 PASS / 9 WARN / 0.057 L WARN |

- No graded check lost its status.
- On the code head (`--base code`, built before the last two commits), no PASS was lost either, and hair_noise went
  0.057 to 0.050. But the lower back reaches into the neck and shoulders (hair_penetration 0.049 L FAIL, 201
  vertices), and the fringe ends 0.07 L short over the eyes (FAIL).

## Detail round (`tool/hair-detail`)

Michael's note on the checkpoint: the detail of the drawn pieces was lost in the render, and the buns came out as
smooth blobs. Measured first with `python -m charkit hairlab BUILD` (new: the pieces rebuilt over a finished build's bundle with
style, opts and shape overrides, and measured by the QA's own hair checks with no Blender, about 20 s a variant). The
causes were:
- **Buns.** An icosphere radius field over the hull's bun points: the visual hull keeps outlines only, so a blob.
- **The head swelled up into the buns.** The hull is the union of head and bun (it can't carve the notch between
  them). Its fill under each bun was labelled bangs or side locks and lifted the envelope, so from the front our bangs
  covered the lower half of each drawn bun (5,600 of its 16,100 px).
- **The hair sat 0.024 L low against our eyes.** `i3d.eye_target` put the hull's eyes (the drawn irises' centroid)
  on our eye knobs' line, but our irises sit 0.024 L above it. The QA anchors on the irises, as the drawings do.
- **The fringe ended short.** A lock's lower edge was the chart's 4 degree columns interpolated, then notched 7
  degrees deeper, so the drawn points over the eyes were rounded off.
- **Side locks** stood in front of the face in profile, because the hull fills the gap between lock and cheek. This
  one is not fixed yet; see Left.
- **Shading.** Every lock shaded with the one envelope normal, so a lock had no relief of its own.

What changed:

| Where | What |
|---|---|
| `hairpieces.bun_block`, `fit_block` | A block bun template: two rounded boxes (superellipsoids, `bun_e` 0.3: flat faces, bevelled edges), the main block and the fold's slab. Its pose, size and slab are fitted by Nelder-Mead to the drawn bun's front, profile and back silhouettes (the hull's views, `view_px`). It shades with its own normals. Chosen per design: `hair.shape.pieces_opts.bun: "block"` (default `round`). |
| `hairpieces.carve_under_buns` | A mass point that the front or back view draws inside a bun, and beyond the head's outline, becomes `BUN_BASE`, out of the envelope. The head's outline is the convex hull of the drawn mass above the eye line (the buns hide the head's top). The envelope fills over it from its column. On Clawd, 723 points. |
| `i3d.eye_target` | `eye_anchor: "iris"` aligns the generated shape to our irises' height. The pieces take it from `hair.shape.pieces_opts.eye_anchor`, which only the pieces stage's case uses. Set on all of `hair.shape`, it also moved the authored body's and the garments' fits to the hull. The spec gate then regressed sheet_neck_to_jaw (0.99 to 0.69), body_back_hem_mid, body_front_leg and body_front_iou_skin. Opt-in; the default stays on the knobs' line. |
| `hairpieces.drawn_tips`, `fine_tips` | The drawn lower edge at any phi. With `fine_tips` (default `('bangs',)`), a lock's edge is the drawing's at its own 1.5 degree columns (median of 3). |
| `hairpieces.clamp_to_view`, `skin_front` | Opt-in (`clamp_side_locks`). It holds the side locks behind the drawn profile's front edge, as a shear per height, and never behind the cheek the front view draws them over. It is off because moving a built lock folds it. The first renders crumpled at the cheeks: 150-200 outer folds per side lock, per vertex; 40-130 sheared. The builder counted its folds before the clamp, so the QA missed them (they are now counted after it). |
| `hairpieces.crown_cap` | The cap's inner face clears the skin, as a lock's does. It was the upper back's penetration. |
| `lock_shell` relief, `shade_normals` lock_shading | Each lock gets a ridge across it (`relief` L), with grooves between locks. Its shading blends in the lock's outer normal, smoothed within the lock `lock_shading_smooth` times (`lock_shading`). The relief fades out again over the lock's last 30%: out along the chart's radius, a hanging tip dipped into the shoulders. On the default spec that gave the lower back 0.004 L of penetration, 1 vertex, the gate's one regression. Anime: relief 0.008 L and lock_shading 0.2. The raw facets at 0.35 put the p95 angle between adjacent shading normals at 30 degrees. Smoothed at 0.2 it is 3-7 degrees (the envelope alone gives 3), and it adds under 0.002 to hair_noise. The anime notch is now 3 (was 7), because the drawn edge already carries the notches. |
| `qa3d` | Added `hair_bun_outline` (outline agreement at 0.012 L, graded 0.7 / 0.5), `hair_bun_corners` (INFO, ours against drawn) and `hair_tips_front`/`_back` (INFO, the lock tips along the lower edge). |
| `hairlab` | The measurement loop above, as a command. `--labels PNG` draws the QA scene's family labels per view with the drawn outlines. `--noise` gives hair_noise's measure for the rebuilt pieces, drawn as the build's hair objects with the pieces' meshes and shading normals. |
| `hairpage` | A renders section: the design's turnaround figures beside the before and after boards, with close-ups of the top (buns, fringe, locks). With `--against`, the hair pieces' checks are remeasured on both builds by the current QA. |
| `charkit/spec/clawd_body_pieces.json` | clawd_body with the hair in pieces, block buns and the pieces' iris anchor (`pieces_opts: {bun: block, eye_anchor: iris}`). |

Measured by `hairlab` over the same build (`charkit/out/hd_base`, a box build of clawd_body in pieces at 849b9a7),
so the skin and the QA are the same. "Before" is the hair as built there. "After" is `--opts bun=block --shape
eye_anchor=iris` with the new defaults:

| Check | Before | After | Step that moved it |
|---|---|---|---|
| hair_piece_bangs | 0.611 | 0.757 | carve (+0.13), iris anchor (+0.04) |
| hair_piece_buns | 0.687 | 0.831 | carve, block fit with its slab |
| hair_bun_outline (0.012 L) | 0.212 FAIL | 0.400 FAIL | block fit |
| hair_bun_corners (ours / drawn) | 20 / 35 | 17 / 35 | the round buns' lumps counted as corners; the bevels round ours off |
| hair_piece_side_locks | 0.505 | 0.537 | iris anchor (the clamp's 0.557 is off, see above) |
| hair_piece_upper_back / lower_back | 0.780 / 0.692 | 0.780 / 0.723 | notch 3, iris anchor |
| hair_fringe_low (L, + short) | 0.014 | 0.009 | fine tips (the iris anchor alone made it 0.038) |
| hair_tips front / back (drawn 4 / 8) | 4 / 4 | 4 / 4 | |
| hair_penetration (L) | 0.038 | 0.015 (2 vertices) | crown cap |
| face shown / design: front, 3/4, profile | 1.12, 1.02, 0.53 | 1.12, 1.04, 0.63 | iris anchor (the clamp reached 0.82 in profile) |
| hair_noise (builds, per-group cuts) | 0.060 | 0.068 | see below |

Ablations with `hairlab` were the evidence for each default:
- **Round buns.** With the carve they score 0.772 IoU and 0.303 outline; the fitted block scores 0.829 and 0.385.
- **Knobs anchor** (final config otherwise): bangs 0.698, side locks 0.521, buns 0.811 and tips 2 / 4. The face shown
  in front is 1.06.
- **hair_noise.** hair_noise rose with the block buns, not with the lock detail. `hairlab` with the old shared cuts:
  - final 0.070; with round buns 0.047; without the carve 0.054; without the lock detail 0.069; without fine tips 0.069.
  - The measure cut tones at percentiles of all the hair's pixels, so the blocks' large flat faces moved the mass's cuts.
  - It now cuts each tone group at its own percentiles (`qa3d.tone_edges`, `HAIR_NOISE_GROUPS`: the buns apart from
    the mass). This is registered in `history.STEPS` (cc79d07), so gates call it remeasured.
  - Remeasured builds: before (849b9a7) 0.0597; after (e4c5d18) 0.0879 FAIL becomes 0.068 WARN; the default spec's
    candidate 0.048 becomes 0.055.
  - **The real cost of block buns**, the mass's front tone edges on its own cuts, block against round with all else
    equal: 0.128 to 0.139 per pixel (+9%). Between the two builds, where everything changed: front 0.125 to 0.148;
    profile 0.034 to 0.031; back 0.044 to 0.037. The buns' own edges went from 0.02 to 0.06; that is the blocks'
    faces and bevels.

## Left

- **Side locks: face shown in profile** is 0.63 of the design's (IoU 0.54, WARN). The hull fills the gap between lock
  and cheek. Pushing built locks back folds them (above), so the profile constraint has to go into the chart's
  envelope before lofting, from the drawn profile edge per row. The drawn locks also curl in at the chin.
- **Buns** outline 0.40 at 0.012 L (FAIL against 0.7), IoU 0.83. The drawn bun has two loops with a visible step
  between them. Ours is a block plus a slab, so the next template would be real loop geometry: a ribbon swept around
  the knot. Corners are 17 against the drawn 35, because our bevels round them off.
- **hair_penetration** 0.015 L (2 vertices, the upper back near the pole): the chart's coarse skin sampling at the pole.
- **eye_anchor 'iris' as the default.** It is opt-in here. It moves every hair mode's alignment 0.024 L up on Clawd,
  and bodyeval, faceeval and garments use eye_target too, so it is the integrator's call.
- **Shared generated inputs.** charkit/out/hull and charkit/out/clawd were hard-linked across seven worktrees. A build
  whose stamp is stale rewrote them in place for everyone. (It was the same content: the hull code didn't change.)
  This worktree's copies are now its own.
- **Lock outlines and highlight streaks:** not done. The relief is 0 at a lock's edges, so adjacent locks meet with no
  depth step for the inverted-hull outline to catch.
- **Folds.** 9 on clawd_body (WARN): the bangs and the side locks.
- **Springs.** The chains are stored in the parts' meta, but no bones or VRMC_springBone export yet.

## Next round: torn tips and jagged edges

These are from Michael, on the look_v5 boards, which carry this branch's pre-merge hair. Measure each one before
fixing it. Shading terminators on the locks are the look's matter, unless they come from the lock normals
(`lock_shading`).

- **Torn fragments at lock tips.** Small loose shards near the neck and the side locks.
- **Stepped, jagged edges.** Along the back hair's lower edge, and along the fringe in profile.

Target: clean lock tips with no shards, and lock edges smooth at the silhouette.

**Measure (to add to `hairlab`)** until tool/artifacts' shared detectors land (outline roughness, fragments and
slivers, terminator roughness per region, calibrated on the design):
- **Fragments.** The small disconnected components of the hair class per view (front, three-quarter, profile, back),
  from `labels_for`: count, and pixels under about 60 px. Also per family, which tells which piece sheds them.
- **Edge roughness.** The hair silhouette's lower edge per column (as `qa3d.hair_tips` reads it), against its own
  smoothed copy: RMS and p95 in L, per view. The fringe in profile and the back's lower edge are the two to watch.

A scratch version of the fragment count, run on hd_base with this round's defaults and the clamp off, as a starting
baseline:
- front 16 components, 109 px;
- three-quarter 10, 67 px;
- profile 5, 47 px.

The before-round hair had front 30 / 206 px, three-quarter 23 / 125 px and profile 6 / 75 px.

**Likely sources, to check first:**
- the lock shells' tips, where the ladder stitches columns whose tips differ by more than a step (thin slivers);
- `fine_tips`' per-column drawn edge, where a 3-column median leaves single-column spikes;
- the notch's V meeting the drawn edge;
- the lower back's edge sampled at 4 degree columns.

## Round 3 (`tool/hair3`, `~/animation-pipeline-hair3`): paused 2026-09-29, state and next steps

Paused on the coordinator's request (usage limits). Resume from here.

**Setup done.** Worktree from pipeline-3d `6ca18da`; `infra/gcp/{build,render}.env` copied; `charkit/out/i3d` cloned
(`cp -c`); `charkit/out/hull` and `charkit/out/clawd/hair` fetched from the build box's copy (the laptop copies are
`charkit/out/{hull,clawd}.laptop`, stale stamps). Working spec: `charkit/spec/clawd_body_pieces.json` (tool/default-spec
makes clawd.json identical to it).

**Baseline builds (both finished, outputs local):**
- `charkit/out/h3_base`: build box, clawd_body_pieces at 6ca18da, no boards (fetched in full).
- `charkit/out/h3_base_r`: render box, same spec, boards `views,body` (face_000..150, body_000..180).

**The measure (task 1), in `charkit/hairlab.py`** (tool/artifacts' detectors have not landed: its `artifactqa.py` is
uncommitted; these follow its plan's definitions so it can take over):
- At the head sheet's own scale (`HEAD_PPL` 400 px/L; the body sheet's ~212 px/L put the flags at 1-2 px). The design
  is `head_turnaround` (the spec's `ref.face_sheet`) through `refcheck.at_scale`, its hair the orange mass with the
  lines absorbed and anything further than 0.01 L from the mass dropped (iris and collarbone strokes). Ours is the QA
  scene z-buffered round the head (`HEAD_WIN`), **each lock apart** (a piece's connected shells).
- `hair_fragments_<view>`: loose hair components plus **lock shards**: every visible part of a lock between
  `FRAG_MIN` 0.00002 and `FRAG` 0.002 L^2 (a blade's own one stroke excepted). In the render each is a shard ringed by
  its lock's outline. Graded as the excess over the design's count (0 in every view): PASS 0, WARN 2.
- `hair_rough_<view>` / `_back_lower` / `_profile_front` / `_profile_lower` / `_three_quarter_lower`: the hair outline
  band-passed (smoothed at S1 0.004 against S2 0.02 L); **steps** = lobes deeper than 0.003 L and shorter than 0.04 L
  along the outline, per L. Graded as the excess over the design's: PASS 0.25/L, WARN 0.75/L. (All teeth per L didn't
  separate: the design's drawn curls score as high; the short ones do.)
- `hair_lines_<view>` (INFO): the same on the lines inside the hair (each lock's outline where it is the nearer side).
- CLI: `hairlab BUILD --built --edges-json J --edges-png P` (a build as built, any build, ~20 s) and
  `hairlab BUILD [--style/--opts ...] --edges ...` (rebuilt variants). The picture: the design beside ours per view,
  each lock its own tone, shards ringed red, silhouette steps blue, inner lines black with their steps green.

**Numbers so far** (design / flagged look_v5 as built / current baseline h3_base as built):

| check | design | look_v5 (flagged) | h3_base |
|---|---|---|---|
| fragments front / 3q / profile / back | 0 / 0 / 0 / 0 | 11 / 20 / 7 / 9 FAIL | 11 / 19 / 15 / 10 FAIL |
| steps/L profile_front (the fringe) | 0.38 | 1.84 FAIL | 1.47 FAIL |
| steps/L profile_lower | 0.41 | 2.85 FAIL | 2.33 FAIL |
| steps/L three_quarter_lower | 0.26 | 1.57 FAIL | 2.22 FAIL |
| steps/L back_lower | 0.30 | 0.76 WARN | 0.00 PASS |
| hair_bun_outline (rebuilt) | 0.7 target | | 0.393 FAIL |
| face shown / design, profile | 1.0 | | 0.633 |
| builder folds | | | 9 (bangs 4, side locks 4, upper back 1) |

Where h3_base's shards are (per piece, summed over views): the crown (upper_back 28, bangs 11: every lock that reaches
the crown converges to a sliver at the pole), the side locks' edges in three-quarter, bun_R in profile, and the
flyaways (blades at the front view's mid-plane, poking through the side locks in profile: the "ʃ" marks in the
renders). The zigzag lines on the side lock in profile renders are the fringe's lock tips seen from the side.

**Code in progress (committed, defaults unchanged):**
- `hairpieces.side_lock_trim` (task 3): with `clamp_side_locks` and `clamp_mode: envelope` (the default mode when the
  clamp is on), the side-lock cells whose envelope point projects in front of the drawn side lock's front edge in her
  own profile are cut from the family field before the regions and locks are made, with every cell below them in the
  column; `drawn_tips` never refines a side lock's tip below that cut. `clamp_share` 0.5 cuts half way. The old
  shear is `clamp_mode: shear`. Not yet run.
- `hairpieces.crown_cap` with `crown_blend` > 0 (opt, default 0 = the old fan): the crown's cap outermost to
  crown_cap - crown_blend, its rim tucked under every layer, the locks that reach the crown starting under it
  (`crown_top`). Meant for the crown shards; try `--opts crown_cap=20 crown_blend=8`. Not yet run.

**Next steps, in order:**
1. `hairlab charkit/out/h3_base --opts crown_cap=20 crown_blend=8 --edges` (crown shards), then
   `--opts clamp_side_locks=true` (face shown profile, folds, shards) and `clamp_share=0.5`.
2. Flyaways: root under the envelope and the blade kept outside it (no poke-through), or lying on the rim.
3. Lock tips and lower edges: back-layer tips that end within a step of the front layer's (slivers); `fine_tips`'
   single-column spikes; the front/profile view switch at |phi| 50 in `drawn_tips` (a step in the edge).
4. Buns: the two-loop ribbon template (knot block, two loops set back and lower, per `bun_detail.png`), fitted as
   `fit_block` fits, then compared on hair_bun_outline (0.393 now).
5. Decision renders on the render box into `charkit/out/decisions/hair/{relief,side_lock_clamp}/<option>.png` + json;
   look2 interface notes; gates (`remote gate tool/hair3 --into pipeline-3d`, and `--spec
   charkit/spec/clawd_body_pieces.json`); the before/after HTML page.

**Box jobs running at pause:** none (both builds done and fetched).

## Round 3, relaunched (2026-09-30): progress

pipeline-3d merged (`2e3bdd5`: clawd.json is the authored character, identical to clawd_body_pieces.json, so h3_base
stays the baseline). The loop is `hairlab` variants over `charkit/out/h3_base` (rebuilt, about 40 s each once the
context is loaded; a scratch driver loads it once and runs a list).

**New measures (`hairlab`):**
- `hair_islands_<view>`: a lock's visible part that one other lock encloses (its rim at least 80% that lock), above
  shard size. A drawn head of hair has none. Classed by the depth step along its rim: `poke` (under 0.004 L: the
  surfaces intersect) or `over`; a blade (ahoge, flyaway) lying over a lock is a `flick`, counted apart (the design's
  profile draws one flick over the side lock).
- `step_where`: each step located (row, col, depth, length, family), and shards carry their lock's index. This showed
  that `hair_rough_profile_front`'s steps are not on the fringe: they are at rows 794-810, the side locks' and the
  lower back's tips by the neck (the outline turned toward the face includes the hair's front at the jaw).

**What the variants showed (numbers against the rebuilt baseline: fragments 11/16/15/10, steps profile front/lower
and three-quarter lower 1.47/2.33/1.85, face in profile 0.633):**
- **`crown_blend`** (cap 20, blend 8): profile fragments 15 -> 6 (the pole's slivers gone), three-quarter 16 -> 14,
  back 10 -> 8. It first raised hair_penetration 0.015 -> 0.047 (the rim, tucked 0.04 L under the envelope, reached
  into the scalp where the envelope lies close): the cover's outer face is now never nearer the skin than gap and half
  a tip. As one upper-back piece it cost upper_back 0.013 IoU (it covers the fringe's crown in profile), so the cover is
  split round phi by the part lines (`cap_sectors`: each sector to the piece whose family the crown's rows take).
- **`side_lock_trim` as committed** (cut cells ahead of the drawn edge, and all below them) overshoots: face in profile
  0.633 -> 1.14, but front 1.26 and three-quarter 1.45, side locks IoU 0.537 -> 0.38, lower back 0.723 -> 0.63. Two
  causes: the cut cells (phi 50-75 at the cheek) are the ones the front view needs over the face's sides; and the
  drawn side lock's front edge is hidden under the fringe in the upper rows (now the whole drawn hair's front there,
  `drawn_front`).
- **The pull** (`trim_pull`, default on with the trim): a cell ahead of the drawn edge has its envelope radius pulled in
  along its ray until it projects onto the edge, never below the skin's clearance; cut only where even that is ahead
  (`trim_cut`: true, false = pull to the floor, or a distance in L). Pull everywhere (`trim_cut: false`,
  `trim_smooth: 2`): face in profile 0.633 -> 0.708, side locks 0.537 -> 0.544, bangs 0.758 -> 0.765, side-lock folds
  4 -> 1; the lower back 0.723 -> 0.717 (it shows past the pulled side locks in front). Cutting beyond 0.1 L: profile
  0.907, side locks 0.585, but bangs 0.744, lower back 0.716, front 1.21 and three-quarter 1.21.
- **The design's three-quarter and profile disagree** on a rigid head: a lock can cover a cheek point in three-quarter
  only from lateral and in front of it, so every cheek point it covers there lies behind its own front edge in
  profile; the design's three-quarter covers the near cheek from the eye's outer corner, which its profile shows bare.
  Face shown also counts our eyes as skin (the design's classes don't): about +0.1 in front and three-quarter.
- **Flyaways**: the drawn ones are flicks at the side locks' outer edge (five strokes in front, four in back, one
  crescent over the side lock in profile). Ours were blades at the front view's mid-plane crossing the lock surface.
  `tuck_blade` (default on, `tuck_flyaways`): the root's run dropped, the blade starting just under the surface where
  it clears it, later points lifted clear of it. A dive from deeper in, or a finer resampling, folded the tube.
- **Buns**: `bun: "ribbon"`, bun_detail's construction (a knot block, a loop either side of it set back and lower,
  their offset and size fitted with an asymmetry, as `fit_block` fits the block): hair_bun_outline 0.393 -> 0.447
  (front 0.443 -> 0.52, profile 0.308 -> 0.32), IoU 0.831 -> 0.834. The fit's 0.25 weight on our bun over the
  drawing's other hair let the box hang over the head in profile, where the bun is in front: `bun_over` per view
  (profile 1.0) raised profile to 0.42 (over 1 in front too cost the front and the IoU). The drawn front bun also has
  tails (strands flaring from its base into the hair) that no box covers.
