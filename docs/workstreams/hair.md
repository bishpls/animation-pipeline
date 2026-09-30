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

**Defaults chosen (`586d7b6`)**, from nine batches of `hairlab` variants over h3_base (same bundle, same hull):
- `hairpieces.OPTS`: `crown_cap` 20, `crown_blend` 8, `cap_top` 0.006 L (the cover sits 0.006 L under the envelope at
  the pole, the locks' tops held just under it where it is outermost: at -0.002 it stood 2-10 px over the drawn crown
  in profile, at 400 px/L); `side_lock_trim` on with `trim_cut` false, `trim_smooth` 3, `trim_margin` 0.01 L, above
  the chin only; `tuck_flyaways` on. `cap_sectors` stays off (each sector is its own shell: shards along the crown in
  every view, fragments 9/13/6/10 -> 14/26/8/13). The ribbon fit's second start (loops set forward,
  `bun_loop_starts` 2) lowers the fit's loss but not the outline (0.423 against 0.447): off.
- The anime style's `notch` 3 -> 0: the drawn edge carries the notches; the deepening made the V's between tips that
  the steps measure counts (profile lower edge 2.28 -> 1.77 per L; hair_fringe_low 0.0094 -> 0.0047 L).
- Clawd's specs (clawd.json and its alias clawd_body_pieces.json): `bun: "ribbon"`.
- Call F (relief strength, the side-lock clamp) is untouched: `clamp_side_locks` stays off, `side_lock_trim` is its own
  switch.

| check (hairlab, h3_base) | design | before (old defaults) | after |
|---|---|---|---|
| fragments front / 3q / profile / back | 0 / 0 / 0 / 0 | 11 / 16 / 15 / 10 | 6 / 13 / 8 / 7 |
| islands (a lock inside another) | 0 | 0 (flicks 0/2/3/0) | 0 (flicks 0/2/3/0) |
| steps/L profile front (the hair's front at the jaw) | 0.38 | 1.47 | 1.52 |
| steps/L profile lower | 0.41 | 2.33 | 1.76 |
| steps/L three-quarter lower | 0.26 | 1.85 | 2.28 |
| steps/L back lower | 0.30 | 0.00 | 0.00 |
| hair_bun_outline (front, profile) | 0.7 target | 0.393 (0.443, 0.308) | 0.448 (0.52, 0.32) |
| hair_piece bangs / side locks / upper back / lower back / buns | | 0.758 / 0.537 / 0.780 / 0.723 / 0.831 | 0.764 / 0.541 / 0.776 / 0.719 / 0.834 |
| hair_fringe_low (L) | | 0.0094 | 0.0047 |
| hair_penetration (L) | | 0.0148 | 0.0148 |
| builder folds | | 9 | 5 |
| face shown / design: front, 3q, profile | 1 | 1.124, 1.040, 0.633 | 1.119, 1.046, 0.689 |

Regressions, by cause:
- **upper back -0.004**: the crown's cover in profile (a band where the fringe's slivers were, over a crown that
  stands above the drawn one) and the ribbon buns (their loops occlude the crown differently in profile).
- **lower back -0.004**: the trim's pull in the front view: the side locks drawn back at the cheek show the lower
  back behind them where the drawing has side lock.
- **three-quarter lower edge +1 step**: a lower-back tip (row 791) crosses the 0.003 L tooth threshold with notch 0.
  The step counts are single lobes at these lengths (1.7-2.7 L of edge): one lobe is 0.4-0.6 per L.

**Final state (round 3, `0bba271` + notes; pipeline-3d merged at db718ae).** Gates, into 9397578: default spec **PASS**
(`charkit/out/gate/gate_tool-hair3_0bba271_into_9397578.md`), clawd_mh **PASS** (`..._clawd_mh.md`).
- The first default gate (586d7b6 into b8097cf) FAILed on body_three_quarter_iou 0.851 -> 0.849 WARN. Ablated in the
  lab (`tools/hair3/ablate.py`, the body QA's own zbuffer): the trim on her right side (mirrored from the left
  profile, it moved the far side lock's front edge in from where the three-quarter view draws it, at the silhouette)
  and the ribbon's loops, 0.001 each. Fixed by `trim_sides: "drawn"` (only her left side, the one the sheet's profile
  draws) and `bun_over: {profile: 1}` (the bun fit weighing our bun over the head's hair whole in profile, where the
  bun is in front of it): lab 0.8511 against 0.8507 before; gate 0.855 -> 0.854 PASS.
- Gate deltas on the default spec (9397578): bangs 0.736 -> 0.761, side locks 0.533 -> 0.541, hair_folds 6 -> 4,
  hair_fringe_low 0.0141 -> 0.0094 L (the fringe on the new carve), sheet_shown_profile 0.356 -> 0.371; regressions:
  upper back 0.771 -> 0.756 (the crown cover, over a crown higher than the drawn one, and the profile-weighted bun
  uncovering crown), hair_bun_outline 0.397 -> 0.371 and buns 0.826 -> 0.824 (the profile weight: on b8097cf's hull
  the ribbon alone gave 0.403 -> 0.452, with the weight 0.420; on 9397578's it costs more), hair_noise 0.0721 ->
  0.0738 (WARN both).
- MakeHuman spec (round buns, no fit): side locks 0.479 -> 0.506, upper back +0.009, lower back +0.008, folds 5 -> 4,
  sheet_shown_profile 0.195 -> 0.235; bangs 0.718 -> 0.702 (the crown cover, upper-back family, over the crown the
  front view draws as fringe: that head shows more crown from the front), penetration 0.0007 -> 0.0015 (PASS).
- Lab, final defaults over b8097cf's bundle (`h3n_after_r`, one hull): fragments 13/17/12/12 -> 11/14/9/8; steps/L
  profile lower 1.77 -> 1.19, profile front 0.96 -> 1.00, three-quarter lower 1.12 -> 1.54 (one lobe); face in
  profile 0.632 -> 0.687; folds 9 -> 6. Trimming both sides gave fragments 5/10/9/6 but failed the three-quarter gate.
- The review page: `charkit/out/hair3_review/index.html` (design | before | after per view, the boards of
  `h3n_before_r` and `h3n_after_r` on the render box; the after render is 586d7b6's defaults, both-sided trim).
- The cover's front/back split (`cap_sectors: "half"`): upper back +0.003 for +2 front fragments; left off.

**Open, next:**
1. The bun: the profile weight trades outline for the three-quarter silhouette. A three-quarter target for the fit
   (no hair_layers three-quarter mask yet), or the drawn tails (strands from the bun's base) as blades.
2. The crown stands above the drawn crown in profile (the envelope's pole), which the cover makes a solid band: the
   upper back's loss. Lower the pole to the drawn crown, or give the cover the fringe's family where the front view
   draws fringe without shedding shards.
3. Her right side lock: untrimmed, it keeps its edge shards (front fragments 5 -> 11 against both-sided). Trim it to
   the three-quarter view's edge, not the mirrored profile's.
4. Three-quarter lower-edge steps: tips at the collar (lower back) and the side-lock tips; each is one lobe.

## Round 4 (`tool/hair4`, `~/animation-pipeline-hair4`): in progress

Branched from pipeline-3d e11fadb; tool/hull-limbs merged (f317326), then pipeline-3d 120d197 (hull-limbs landed,
db7a67e). Baselines, round 3's hair on the new hull (hull-limbs), box builds:
- `charkit/out/h4m_base` (default spec, build box), `h4m_mh_base` (clawd_mh), `h4m_base_r` (default, render box,
  boards `views,body`). The old-hull ones are `h4_base_oldhull`, `h4_base_r_oldhull`.
- Default: hair_bun_outline 0.397 FAIL, upper back 0.760, side locks 0.545, folds 6, hair_penetration 0.0124 FAIL
  (the upper back's crown, 9 vertices), body_three_quarter_iou 0.855. clawd_mh: hair_penetration 0.0484 FAIL
  (lower back in the MakeHuman shoulder, 47 vertices), folds 11.

The loop: `tools/hair4/lab.py BUILD OUT 'name|{"opts": ...}' ...` (hairlab's context once, then per variant the hair
checks, each bun per view, fragments, steps, face shown, folds, penetration with where, the three-quarter figure's
IoU as the body QA draws it, and the crown's rise over the drawn crown). Round 3 reproduced exactly in the lab with
`{"bun_occlude": false, "bun_per_side": false, "bun_views": ["front", "profile", "back"]}` (r3x = built).

**New measures (hairlab):**
- `--buns` / `bun_views`: each bun (L, R, both) per view, the three-quarter and back too: IoU and outline at
  HAIR_BUN_TOL against the hair layers' new bun sides (`hairlayers.bun_sides`: `VIEW__bun_L/_R` in all four views,
  the outfit's bun pieces rimmed into the view's hair; the three-quarter has no `three_quarter__buns`, so the QA's
  hair_bun_outline keeps its views, front and profile). `--buns-png` the crops.
- `crown_rise`: per view, over the columns whose topmost drawn hair is the mass's, our mass's top against the drawn
  one (L; median, p90, max, share over 0.01 L).

**Findings so far (lab, h4m_base / h4m_mh_base):**
- **Item 0, the MakeHuman shoulder** (`hairpieces.body_clearance`, opts `body_clear` on, `body_push_max` 0.03 L): below
  the chin, the radii a layer's outer surface may take in a cell (from 0.04 L under the envelope out to where the
  push over the skin takes it) are tested against the build's own body (case.A: the QA's plane test, without its
  0.05 L cut-off); where one is inside, the ray is marched out to the body's exit: within 0.03 L of the envelope the
  cell's skin becomes the exit (every layer pushed over it), further the cell and those below it are cut (the lock ends
  above the shoulder; `drawn_tips` never refines below the cut). Pushing along the chart's rays alone bulged the lower
  back 0.26 L out and still penetrated (0.0457): the rays from the head's centre run on into the shoulder. clawd_mh:
  hair_penetration 0.0484 FAIL -> 0.0034 PASS, lower back 0.688 -> 0.688, folds 11 -> 10. Default spec: no change
  (its authored body doesn't collide).
- **Default spec's hair_penetration 0.0124 FAIL is a measurement artifact:** the hair at the crown is 0.013 L *outside*
  the skin (z 0.643 over the head's centre, the skin's top 0.641), but the skin mesh has 120 inward-facing triangles
  at the crown (case.A; 240 in the evaluated skin), coincident with outward ones (x +-0.067 L, z 0.63-0.64). The QA's
  median of the 4 nearest triangles' planes reads 3 inward ones. The head's mesh is tool/face's; the check's robustness
  (a winding test) would be a remeasure.
- **Hull samples** (coordinator: hair_folds moved with the hull's decimation, not its shape): `hairpieces.hull_samples`
  reads the labelled shell (hull.npz), each point moved onto the smooth surface the mesh is cut from (the occupancy's
  signed distance blurred a voxel, before decimation), the shell's own point kept where the field is too flat to settle.
  Stability, clawd_mh, the hull's mesh re-decimated 150k -> 140k faces (same occupancy): from the mesh's vertices the
  bangs' folds 7 -> 4, side_lock_R 5 -> 4 locks, bun_R moved 0.045 L, the outline 0.303 -> 0.335; from the shell every
  piece identical (max move 0; bun_L 0.0004 L). The shell's class labels differ from the mesh's over the fringe (skin,
  iris and the clips' pieces where the mesh's vertices read hair: 1,900 samples), which shortened the fringe (face shown
  front 1.11 -> 1.21): shell samples are hair where the views' hair families label them, and the clips are hair.
- **Crown** (`crown_trim`, th up to 110 deg): our crown against the drawn one, per view, where the drawing shows the head's
  top (the bridge only under a bun or the ahoge). Round 3's hull-limbs baseline stood up to 0.02 L above in front and
  back (p90), 0.024 L in profile (the back of the head under the bun, theta 84-108, and 4 columns at the pole): trimmed,
  front and back p90 0, profile p90 0.009.
- **Bun fit, round 4** (`fit_block` with `scene`: our bun z-buffered behind our own hair and skin on each view's drawn
  pixels, the per-side targets in all four views, the three-quarter's from `hairlayers.bun_sides`; `bun_outline_w` adds
  per view 1 - the outline F at hair_bun_outline's tolerance; `bun_tails`: a fan of tapered blades from the knot's
  underside, flaring down and out, fitted after the knot and loops from four starts). Measured on the shell samples
  with the crown trim (h4m_base), hair_bun_outline (QA: front + profile) and each bun both-sides IoU/outline per view:

  | variant | QA outline | front | three-quarter | profile | back | buns IoU | fragments f/3q/p/b |
  |---|---|---|---|---|---|---|---|
  | round 3's fit (hv_crown) | 0.440 | 0.844 / 0.483 | 0.524 / 0.139 | 0.836 / 0.362 | 0.849 / 0.489 | 0.844 | 9/14/13/11 |
  | occlusion, area only (shell_occ) | 0.397 | 0.825 / 0.401 | 0.695 / 0.292 | 0.874 / 0.389 | 0.876 / 0.707 | 0.856 | 8/16/10/14 |
  | occlusion + outline 1 (hv_o1) | 0.496 | 0.820 / 0.540 | 0.739 / 0.384 | 0.808 / 0.428 | 0.778 / 0.342 | 0.800 | 9/16/13/9 |
  | + tails (hv_o1_t) | 0.502 | 0.827 / 0.557 | 0.735 / 0.365 | 0.806 / 0.413 | 0.791 / 0.414 | 0.808 | 15/16/14/14 |
  | outline 0.5 + tails (hv_o05_t) | 0.460 | 0.814 / 0.510 | 0.738 / 0.324 | 0.829 / 0.368 | 0.825 / 0.572 | 0.822 | 13/18/16/17 |

  The area-only fit trades the front's outline for the three-quarter and back. With the outline term the QA outline
  reaches 0.50 (0.397 -> 0.50, a third of the way to 0.7) and the three-quarter bun IoU 0.52 -> 0.74, the lab's
  three-quarter figure IoU 0.857 -> 0.867, but the back's bun IoU drops 0.85 -> 0.78 and hair_piece_buns 0.844 -> 0.800
  (the design's views disagree on the far bun: her right bun in three-quarter scores 0.33-0.66 whatever the fit). The
  fitted tails are wide blades filling the silhouette, partly hidden: +6 front and +5 back shards, and bun_R's reach
  0.010 L into the scalp. Not default yet.

### Round 4 checkpoint (2026-09-30, wrapped at the usage limit)

**Committed defaults** (`hairpieces.OPTS`): round 3's hair plus `body_clear` (item 0) and `crown_trim` (crown_th 70,
the bridged outline). Everything else is behind a setting, measured but not better on every check. Lab over the same
bundles (hull-limbs hull), round 3 as built -> the committed defaults:

| check | default spec (h4m_base) | clawd_mh (h4m_mh_base) |
|---|---|---|
| hair_bun_outline (front, profile) | 0.397 (0.409, 0.375) -> 0.437 (0.472, 0.376) | 0.303 -> 0.314 |
| buns per view, IoU / outline: front | 0.791 / 0.409 -> 0.845 / 0.472 | 0.830 / 0.425 -> 0.831 / 0.441 |
| three-quarter | 0.518 / 0.150 -> 0.519 / 0.151 | 0.623 / 0.244 -> 0.623 / 0.246 |
| profile | 0.834 / 0.375 -> 0.834 / 0.376 | 0.470 / 0.093 -> 0.470 / 0.093 |
| back | 0.853 / 0.524 -> 0.855 / 0.536 | 0.847 / 0.471 -> 0.841 / 0.443 |
| hair_piece_buns | 0.826 -> 0.846 | 0.725 -> 0.724 |
| hair_piece_upper_back | 0.760 -> 0.771 | 0.779 -> 0.778 |
| bangs / side locks / lower back | 0.762 / 0.545 / 0.703 -> 0.759 / 0.547 / 0.703 | 0.715 / 0.498 / 0.688 -> 0.713 / 0.497 / 0.688 |
| fragments f/3q/p/b | 12/16/7/8 -> 11/12/8/11 | 10/18/4/18 -> 12/18/4/19 |
| steps/L profile front, profile lower, 3q lower, back lower | 0.5 / 0.63 / 1.84 / 0.0 -> unchanged | 0.0 / 1.26 / 1.34 / 0.36 -> 0.0 / 1.26 / 1.78 / 0.36 |
| hair_penetration (L) | 0.0124 -> 0.0124 (the skin's crown artifact) | 0.0484 FAIL -> 0.0034 PASS |
| hair_folds (builder) | 6 (bangs 1, side L 2, R 1, upper back 1, lower back 1) -> 5 (bangs 0) | 11 (bangs 7, side L 1, upper back 1, lower back 2) -> 8 (bangs 5, side L 1, upper back 1, lower back 1) |
| three-quarter figure IoU (lab, the body QA's scene) | 0.8555 -> 0.8552 | 0.7267 -> 0.7266 |
| crown rise p90 (L) front / profile / back | 0.020 / 0.024 / 0.014 -> 0.0 / 0.024 / 0.0 | 0.005 / 0.075 / 0.0 -> 0.0 / 0.071 / 0.0 |

Not done: the gates, the render build of the final code, and the review page (`tools/hair4/page.py` is written:
`python tools/hair4/page.py OUT h4m_base_r AFTER_R charkit/out/h4lab/d2/r3x charkit/out/h4lab/final/default TABLE.json`).
pipeline-3d cfcdc3a (tool/infra: self-registering parts and steps, the gate's 2x2) is not merged yet; this branch adds
no QA part or step (the hair layers gain keys only; the QA's hair checks read what they read).

**The right side lock (item 3):** on the hull-limbs hull the both-sided trim no longer helps: front fragments 12 either
way (the right lock's 2 go, the lower back gains 2), folds 6 -> 12 (side_lock_R 1 -> 6), the lab's three-quarter figure
IoU 0.8555 -> 0.8542. `trim_sides: "three_quarter"` (her right pulled to the mirrored profile but never in past the
three-quarter's drawn figure edge) pulls nothing: every right side-lock cell already projects at or inside that edge.
`trim_tq_slack` (L) lets it in by that much; not swept.

**Next, in order (a lean relaunch):**
1. Merge pipeline-3d (cfcdc3a+), run `charkit/tests/test_registry.py` and the hair tests, gate both specs with the
   committed defaults (the expected deltas are the table's). Then the render build and the review page.
2. The shell samples as the default (the coordinator's stability item): they hold every piece still under a
   re-decimation, but on this bundle folds 6 -> 12 (side locks 5, lower back 3, flyaways 4 with the 'mid' plane) and
   the profile's fragments 7 -> 13 (the fringe's and upper back's lock shards). Look at where the side locks' and lower
   back's lock partition moves (the family field per cell against the mesh's), and at the upper back's profile shards.
3. The bun: the outline-weighted fit (0.50) without costing the back's IoU (a floor per view, or the far bun's
   three-quarter weighed by how well any rigid pose can match it); tails kept clear of the scalp and either fully
   visible or hidden (no partial shards).
4. The default spec's hair_penetration artifact: tool/face's head mesh (inward crown triangles), or a winding-number
   test in the QA (a remeasure, the 2x2).

### Round 4, overnight relaunch (2026-09-30 evening)

- **pipeline-3d 08f93e2 merged** (03d14ce, clean: pipeline-3d's only hair-side change is hairlayers' outfit masks
  without the silent fallback, which our bun sides read as before). `test_registry.py`, `test_hairpieces.py` and the
  whole suite (57 files, 104 s) pass. This branch adds no QA part or step.
- **Gate** (default spec only): `charkit/out/gate/gate_tool-hair4_14d9e42_into_08f93e2.md`, **PASS** as gate.py grades
  it. The moves are the checkpoint table's: hair_bun_outline 0.397 -> 0.437 (FAIL both sides), hair_piece_buns 0.826 ->
  0.846, upper back 0.760 -> 0.771, hair_folds 6 -> 5, side locks 0.545 -> 0.548, bangs 0.762 -> 0.759, hair_noise
  0.0739 -> 0.0762 (WARN both), bun corners 21 -> 19; build CPU 579 -> 379 s. **Under K it is not mergeable:**
  `art_terminator_hair` (a check calibrated on Michael's look_v5 flag, the torn hair shadow patches; capped at WARN,
  pass 2.0, warn 2.5) 2.376 -> 2.607, the front view's ratio (kinks per L of the hair's cel terminator, 8.90 -> 9.76;
  three-quarter 1.91 -> 2.05; profile and back fall). The flagged build read 2.6. Also art_fragments_hair 1.29 -> 1.49
  (the back view) and art_outline_hair 0.689 -> 0.661, both INFO (not calibrated).
- **Render builds** (`--box render`, boards views,body), both on the merged code: `h4n_r3_r` (the default spec with
  round 3's hair: `pieces_opts` body_clear and crown_trim off, spec in charkit/out/h4spec/) and `h4n_final_r` (the
  committed defaults). The pair reproduces the gate's 14 moved checks exactly (the art checks are deterministic across
  the boxes), so the page's before and after differ only in the hair. The front's new terminator kinks (44 -> 49 marks
  in qa_artifacts.png) are at the crown under the buns and on her left at the cheek.
- **The terminator is the crown trim's:** a build-box build with crown_trim off (`h4n_nocrown`, body_clear on) reads
  round 3's every hair check (terminator 2.376, per view identical): body_clear changes nothing on the default spec,
  the crown trim makes every move, the gains and art_terminator_hair both. Not through Rn: a build with the trim's
  pull blurred into Rn at shade_smooth's 2.5 cells (`h4n_crownshade`) reads the committed defaults' every value; the
  shading normals don't come from Rn (shade_normals: the whole hair as one solid, closed 0.5 L and blurred 0.45 L,
  with lock_shading 0.2 of each lock's own outer normal blended in; Rn gives only vn_env, the folds' reference). The
  option is gone. The trim is per cell (up to 0.18 L over 442 cells) with a 1-cell blur (crown_smooth 1.0), so the
  crown's locks carry its steps and a fifth of their normals shows them. `crown_smooth` 2.5 and 4 on the build box
  (`h4n_cs25`, `h4n_cs4`) and in the lab (f4).
- **crown_smooth doesn't fix it** (build box): the front's terminator ratio 2.607 (smooth 1), 2.675 (2.5), 2.516 (4),
  against 2.376 untrimmed; the hair gains hold at every smoothing (bun outline 0.439, buns 0.846, upper back 0.770,
  folds 5; lab f4). The new kinks are on the buns: the trimmed crown shows more of the bun blocks' bases (their own
  flat normals, faceted terminators; qa_artifacts front: the right bun's lower edge, the left bun's base, under the
  ahoge), so they come with the trim's depth, not its roughness. A fix is the bun's shading or fit, not the trim.
- **Decision (this run): crown_trim goes behind the setting** (`OPTS['crown_trim'] = False`): not better on every check,
  and under K a regression in a flag check blocks the merge. The default spec's hair is then round 3's exactly
  (`h4n_nocrown` reads every hair check as pipeline-3d's), body_clear stays (clawd_mh's shoulder). **Michael's call:**
  the crown trim's bun outline 0.397 -> 0.437, buns 0.826 -> 0.846, upper back 0.760 -> 0.771, folds 6 -> 5 against
  art_terminator_hair 2.376 -> 2.607 (front, past its 2.5 line); `crown_trim: true` in the spec's pieces_opts turns it on.
- **Review page:** `charkit/out/h4n_page/index.html` (`tools/hair4/page.py`, table in charkit/out/h4lab/page_table.json;
  lab pictures from 'built' on both render builds, charkit/out/h4lab/page/).
- **Why the shell samples fold more (next step 2), measured** (`tools/hair4/foldlab.py BUILD OUT [--fine]`: the pieces
  from the mesh's vertices and from the shell's samples, then with the chart's fields swapped between the two right
  after mass_fields; per lock the folds with where, every view's shards with where, the partition's differing cells):

  | h4m_base, committed defaults | mass-piece folds | flyaway folds | profile fragments |
  |---|---|---|---|
  | mesh | 5 | 0 | 8 |
  | shell | 12 | 4 | 16 (bangs 7, upper back 7) |
  | shell, the mesh's envelope (R, Rn, S, reach, valid, body cut) | 5 | 4 | 9 |
  | shell, the mesh's partition (L, nothair) | 13 | 4 | 15 |
  | shell, the mesh's R and Rn only | 5 | 4 | 8 |
  | shell, the mesh's reach and valid / skin and body cut | 11 / 12 | 4 / 4 | 16 / 16 |

  The partition does move (828 of 3,749 hair cells differ after the fill: 215 cells the shell reaches below the mesh's
  lower back, 143 upper back -> bangs at the crown's fill), but it moves no fold and 2 upper-back shards. The folds and
  the bangs' profile shards are the envelope radius R. Not the samples' density: R as the median of each cell's outer
  sheet (`env_stat` 'sheet', `env_sheet` L) folds as much (15), and the shell thinned to the mesh's density (one sample
  per 2^3 voxels) still folds 11. It is where the samples are: in the 291 cells where the shell's envelope stands 0.02 L
  or more beyond the mesh's (6 the other way), the shell's outermost mass point is off the mesh's surface. 6,652 of the
  head's 127,543 shell samples (5%) lie 0.02-0.2 L off the mesh (the BVH's distance), 4,416 beyond 0.05 L: flat slabs
  inside the head (the occupancy's inner walls where the hull's height bands meet, across the face at the nose and
  front to back), blocks behind the eyes, and thin fins on the side locks' and lower back's outer edges that the mesh's
  blur erases. hull_samples keeps each such point where it is (the field too flat to settle), so the "shell samples"
  were not the surface the mesh is cut from. `hull_samples(flat='drop')`, samples 'shell_smooth': the settled samples
  only (lab f3, foldlab fold3 with `--b shell_smooth`):

  | h4m_base, committed defaults | mesh (default) | shell | shell_smooth |
  |---|---|---|---|
  | folds (flyaways) | 5 (0) | 16 (4) | 5 (0), all side_lock_R |
  | fragments f/3q/p/b | 11/12/8/11 | 10/13/16/8 | 7/15/14/19 |
  | hair_bun_outline (front, profile) | 0.437 (0.472, 0.376) | 0.440 (0.483, 0.362) | 0.412 (0.475, 0.298) |
  | buns / upper back / side locks / bangs / lower back | 0.846 / 0.771 / 0.547 / 0.759 / 0.703 | 0.844 / 0.777 / 0.542 / 0.757 / 0.714 | 0.851 / 0.780 / 0.559 / 0.760 / 0.703 |
  | steps pf/pl/3ql/bl | 0.5 / 1.26 / 1.84 / 0.0 | 0.47 / 1.2 / 1.45 / 0.33 | 0.0 / 0.0 / 1.03 / 0.0 |

  The settled samples fold as the mesh does (the flyaways' 4 folds went too: the inner walls pulled their mid-plane),
  and five of the checks improve, but not every one: the profile's fragments 8 -> 14 (bangs 7: the envelope; with the
  mesh's envelope 1), the back's 11 -> 19 (side_lock_R 10: one lock's thin strip along the lower back's edge, the
  partition), and the bun outline in profile 0.376 -> 0.298 (the bun's points: dropping the unsettled points thins
  the buns' too). With the mesh's partition the side_lock_R folds go (5 -> 1). Not the default; behind the setting.
- **Confirming gate** (ad1872a into pipeline-3d a3073f5, default spec):
  `charkit/out/gate/gate_tool-hair4_ad1872a_into_a3073f5.md`, PASS, no check changed, build CPU 1353 -> 1529 s (1.13x).
  **Mergeable under K** (no new FAILs, no flag-check regressions, CPU under 1.5x).

**Next (a lean relaunch):**
1. The crown trim, Michael's call (the page): or fix the terminator at its source, the bun blocks' own flat normals
   where the trimmed crown shows their bases (the buns shade with the mass, or their base faces rounded), then gate
   with crown_trim on.
2. Shell samples: 'shell_smooth' folds as the mesh does; what's left is the bangs' profile shards (the envelope over
   the fringe's sides, where the shell covers cells the mesh leaves to the fill) and side_lock_R's strip along the lower
   back in back view (the partition). The buns' outline in profile drops because dropping the unsettled points thins
   the buns' points too: take the buns' points from the plain shell. foldlab `--b shell_smooth` is the loop.
3. The bun's outline-weighted fit (0.50) without costing the back view; the default spec's hair_penetration (tool/face).
