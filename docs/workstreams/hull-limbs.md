# Hull limbs: each limb takes its own depth (tool/hull-limbs)

Branch `tool/hull-limbs`, worktree `~/animation-pipeline-hulllimbs`, built on `tool/hull-det` (not yet merged).

## The report that started it (Michael, 2026-09-29)

The hull page's "Limbs" diagnostic: in the front view the legs are green and the arms blue; in the profile the bare
legs, forearms and hands are pink ("free skin placed by the side view"), only the boot cuffs green, and blue on what
looked like the sleeves and cuffs.

## What the measurement found (before, tool/hull-det 24fa199, the box)

`rounded()` gives each front limb part the depth of the profile's runs of `(limb == t) | FREE_SKIN`. Per height, which
profile pixels each part took, against a hand-made truth for Clawd's profile (the arm: puff, forearm, wrist cuff,
hand; the legs and boots below the shorts):

- **The legs were fine.** The thighs take the profile's thigh skin (the only free skin at their heights); the boots
  take the whole side run, which at those heights is the boot. One height (z −2.72, the right leg) fell back to the
  whole side run (0.96 L deep). The front's thighs start where the profile's do (−2.72), so no thigh is hidden under
  the skirt on this sheet, and no hand shares a height with a thigh (the hands end at −2.57 in front, −2.66 in profile).
- **The arms were wrecked**, 150 heights of each arm borrowing the body's depth:
  - z −0.50 to −0.69 (the shoulder): the neck's free skin (y 0.13 to 0.33), 0.01 to 0.09 L deep: a paper-thin puff.
  - z −0.90 to −1.21 (the puff): the bow's tail, which the profile's masks label `sleeve_cuff_R` (11% of the pixels
    the arm's).
  - z −1.51 to −2.44 (the forearm, cuff and hand): the skirt's cream front panel, which the profile's masks label
    `cuff_R` (12,579 px; the front's cuff is 3,469), running right up to the forearm: 45% of the pixels the arm's,
    sections up to 0.66 L deep against the drawn 0.22. The wrist cuff (−1.9 to −2.05) took only the panel: 0.3 L in
    front of the drawn cuff.
- **The profile's limb pieces are mostly on the wrong garments** (outfit masks, not this branch's code): `sleeve_R`
  on the bow's loop, `sleeve_cuff_R` on the bow's tail, `cuff_R` on the skirt's front panel, `sleeve_L` on the sailor
  collar's stripe. Only `cuff_L` (the wrist cuff's cream stripe) and `boot_cuff_L` are right; the puff, the sleeve's
  cream end, the cuff's orange band and the boot carry no piece. That is the blue Michael saw.
- The hull: detached forearm fragments, puffs nearly gone, arm blobs fused to the skirt's sides. The limb split cost
  the three-quarter 0.029 of held-out IoU (0.8335, against 0.8624 with no limb split).

## The fix

1. **`limb_image` on the side and oblique views (`free_limbs`).** Free skin is split into connected components by the
   drawing's line class (`View.raw`, now kept by `views_from_sheet`). Each takes the limb of the pieces within
   `SEED_REACH` (0.02 L) of it: a limb's pieces seed that limb, pieces on `SEED_BONES` (head, neck, upperChest: the
   collar, the bow, the pins) and the drawn hair and irises seed the body. Torso pieces (skirt, top, shorts) seed
   nothing: limbs are drawn over them. No seed: one step through the unlabelled drawn cells beside it (a cuff's band
   the masks missed). Seeds of two limbs (under `SEED_SHARE` 0.8 for one): FREE_SKIN. Slivers (under 0.005 L²) and
   the outlines' pixels take the nearest component's. On Clawd: the profile's legs, forearm and hand, and the
   three-quarter's forearms, hands and legs, all take their limb; the face and neck the body.
2. **The depth selection (`sections`, `LimbTrack`).** A limb part takes, per height:
   - `only`: the whole side row where the front shows nothing but this limb (the boots; a body fragment enclosed by
     one limb's parts on one side, a hole in the boot's mask, counts as the limb: `_enclosed`);
   - `limb`: the limb's skin runs in the profile, with its piece runs that overlap the skin (`TRACK_OVERLAP` 0.5);
   - `piece`: its piece runs within the skin's track (interpolated from the skin above and below), joined with the
     interpolated section;
   - `interp` (the skirt fallback's replacement): the section's centre and its depth over the limb's front width,
     interpolated between the nearest `only`/`limb` heights above and below (each the median over `TRACK_WINDOW`
     0.15 L of that sighting, away from the gap, since a sighting's edge row is cut short, e.g. skin going into a
     cuff); beyond the last one, that one's. Never the whole side run.
   - A limb the side view never shows keeps the old fallback (skin, else the side run).
   Piece runs off the skin's track are rejected, which removes the mislabelled panel, bow and tail.
3. **Diagnostic.** The page's Limbs row shows every view in one colour scheme, and a new "Limb depth" map shows the
   profile's rows with each limb's chosen interval per height (solid from skin, lighter from pieces, pale
   interpolated) and the rejected piece runs in red, with a table of heights per source.
4. **Determinism.** Integer image ops (scipy `label`, `binary_dilation`, the EDT's feature transform), IEEE `+ − × ÷`
   in a fixed order, `_round` (floor of x + 0.5) for interpolated grid indices, `det.cs` untouched.

## Results

Hull pair on the box, validated (before tool/hull-det 24fa199; after, that plus this fix):

| held out | before | after | no limb split (after) | plain |
|---|---|---|---|---|
| front | 0.9449 | 0.9449 | 0.9449 | 0.9449 |
| profile (plain carve both times) | 0.3537 | 0.3536 | 0.3536 | 0.3536 |
| three-quarter | 0.8335 | **0.8783** | 0.8614 | 0.7149 |
| back | 0.9343 | **0.9467** | 0.9458 | 0.9458 |

Per-height borrowing (front limb parts, height x side, 2+ foreign cells in the side runs, by the hand-made truth):

| | arm before | arm after | leg before | leg after |
|---|---|---|---|---|
| parts | 416 | 416 | 526 | 526 |
| borrowing | 296 | 8 | 3 | 2 |
| foreign cells / own cells | 6,793 / 6,539 | 80 / 5,890 | 106 / 23,862 | 8 / 21,324 |
| whole side run | 4 | 0 | 244 (the boots) | 0 |

The 8 left: z −0.54..−0.55 (×2 sides), the `sleeve_L` mask on the sailor collar's stripe, on the arm's track (joined
with the interpolated section, it widens nothing); z −1.36 and −2.49 (×2), 2–3 cells of the forearm's and hand's own
outline the truth gives to the skirt. Legs: z −2.73 (×2), the thigh's outline at the shorts' hem.

- **Determinism:** two fast-path builds on the box are bit-identical in every stage and output (hull.npz 908973a8…,
  hull_pieces 9bcfabaf…); the validated build's outputs match them. The new stages (limb images, sections, the
  rejected runs) and the outfit masks hash the same on the laptop (arm64) and the box (x86): 23 of 23.
- **Pieces labels:** the arm pieces gain in every view (held-out front sleeve cuffs 0.15–0.22 → 0.54–0.58, the back's
  used cuff_R 0.50 → 0.84); the skirt loses (held-out three-quarter 0.617 → 0.452) and the weighted pieces IoU dips
  (three-quarter held out 0.4235 → 0.3956). The arm blobs in front of the skirt's sides had carried the profile's
  mislabelled panel masks; without them the profile's panel labels land on the skirt's own side surface.
- **tool/hull-det can't build clawd_body** (24fa199 and 3da2530): `garments.band_hull` fails on `cuff_L` ("no row of
  the piece is measured on 20% of its circle"). Its hull's `sleeve_cuff_L` points sit on the bow's tail: they cover
  17% of the circle round the upper arm, a median 0.43 L from it. With this fix: 58%, 0.15 L. The body's before is
  therefore pipeline-3d (0122617), the gate's baseline.

### The authored body (clawd_body, the box)

| build (its hull) | thigh r median / top ring | thigh max depth | upper arm r median / top ring | upper arm max depth x width |
|---|---|---|---|---|
| pipeline-3d 6ca18da | 0.203 / 0.280 | 0.618 | 0.151 / 0.431 | 0.870 x 0.810 |
| tool/hull-det 3da2530 (before) | 0.203 / 0.283 | 0.608 | 0.151 / 0.431 | 0.870 x 0.810 |
| this branch e7b21e9 (after) | 0.204 / 0.307 | 0.604 | 0.136 / 0.193 | 0.385 x 0.355 |

- The upper arm had a 0.43 L balloon at the shoulder (the ring fitted to hull points on the bow's tail); now a tapered
  tube, 0.19 at the shoulder to 0.10 at the elbow. The thigh's depth just under the shorts (z −2.79) went 0.61 → 0.54
  (drawn 0.55); its top ring at the hip, which no view shows, is the fitter's extrapolation (0.55 → 0.60 deep).
- **Only this branch builds clawd_body.** pipeline-3d 6ca18da fails at `sleeve_L` (`sleeve_hull`), tool/hull-det at
  `cuff_L` (`band_hull`), both "no row of the piece is measured on 15/20% of its circle": the arm's hull points they
  loft round sit on the bow and the skirt panel.
- The after build's QA (111 checks): PASS 75 / WARN 27 / FAIL 9. poke_share 0.0284 FAIL (skirt 203 px, wrist_R 49).
- **The wrist cuffs run the whole forearm** (`wrist_L` z −1.06..−2.12; drawn cuff −1.74..−2.09); piece_cuff_L/R
  0.099 / 0.037. 235 of the hull's 761 `cuff_L` points (31%) lie on the other arm (x median −0.87): the profile's
  `cuff_R` mask on the skirt panel, mirrored by `label_volume` onto her right side as `cuff_L`. `band_hull` spans all
  of its piece's points along the bone; with only those within 0.35 L of it, the span is −1.66..−2.08. Not changed
  here (garments.py and the outfit masks belong to other workstreams); the one-line fix is a reach filter in
  `band_hull`, as `code_body.limb` has.
- The skirt, in 3D: its profile depth is an A-line (near hem over widest 0.995); its front width is widest at
  z −2.01 and 0.832 at the hem.

## Open items

- The outfit masks' profile: `cuff_R` on the skirt's front panel, `sleeve_R` and `sleeve_cuff_R` on the bow and its
  tail, `sleeve_L` on the sailor collar's stripe; the puff, the sleeve's cream end, the cuff's orange band and the
  boot have no piece. The limb carve now works round them; the labels (label_volume, the mirrors) still spread them.
- `band_hull` (and likely `sleeve_hull`) should take only points within reach of their bone.
- The hull-det stages hook stores `rounded`'s V by reference, so its hash is the face-carved V's (`carve_face` edits
  it in place); copy it at the stage.

## Measurement tools

The per-row source table, the truth for Clawd's profile and the before/after pages were made with scripts in the
session's scratchpad (not tracked): `sections(..., tracks=T)` gives every limb part's source, runs and the rejected
piece runs, which is what they read.
