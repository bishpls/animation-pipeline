# The outfit masks without the TRELLIS field (tool/outfit-source)

State: in progress. Worktree `~/animation-pipeline-outfitsrc`, branch `tool/outfit-source` from pipeline-3d `9397578`.

## The problem

`outfit.analyse` read a pre-computed file from one old image-to-3D run, `charkit/out/i3d/ext/runA/clawd_3dstyle_s1_field.npz`
(TRELLIS.2, run once by hand, gitignored). With it the masks are `074d9a3f`; without it `bc0f48dc`, and the authored
spec's build fails in `garments.sleeve_hull`. A second character would need the run redone by hand.

## Measured first: what the field contributes

Both mask sets reproduce the box's hashes on the laptop (`charkit outfit charkit/spec/clawd.json --no-manifest` with and
without `--no-field`): `074d9a3f` in 38 s, `bc0f48dc` in 22 s.

**Pixels relabelled by the field, per view** (of about 80-210 k labelled): front 8,055; three-quarter 40,695; profile
85,699; back 16,722. Where (field -> without it), largest first:

| view | piece | IoU field vs none | what happens without the field |
|---|---|---|---|
| profile | cuff_R | 0 | the skirt's front below the arm (12,579 px) becomes the far wrist cuff |
| profile | boot_L, sleeve_L | 0, 0.03 | the near boot (21,206 px) and puff (9,303 px) left unlabelled |
| profile | overskirt_panel_L | 0 | the tail becomes panel_R and skirt |
| profile | pin_star | 0.22 | the star spreads over the hair (4,167 px) |
| profile | skirt_panel, shorts, bow | 0.04, 0.17, 0.13 | the front panel, shorts and bow mostly unlabelled |
| three-quarter | boot_R, boot_cuff_R | 0.34 | the far boot goes to boot_L or nothing |
| three-quarter | shorts, overskirt panels | 0.28, 0.57-0.69 | shorts and panels swapped |
| three-quarter | bow tails, bodice panel | 0.13-0.38 | tails, bib and cuffs swapped |
| back | bow / collar | 0 / 0.39 | the collar's back flap (7,151 px) becomes the bow |
| front | pin_star, waistband, top | 0.19, 0.69, 0.79 | the star over the hair; waistband and top boundaries |

Why: with the field, each view's prediction is the labelled field projected (visibility and occlusion from 3D);
without it `landmark_prediction` places every rig piece at its front x (mirrored for the back, cos(az) for the 3/4, x = 0
in profile), with no visibility: far-side pieces, front-only pieces seen from the back, and everything in profile sit on
one line.

## A truth to score against

The field's masks are not the truth either, so both were scored against a hand-checked labelling of the sheet
(`body_turnaround`): every cell of 25 px or more in the four views (263 cells), labelled by eye from zoomed crops,
with an acceptable set where the drawing is ambiguous (the profile's two bow tails, a hair tuft under a bun, hem pixels
at a shorts edge) and one split rule (the back's sleeves and bodice are one cell: split at the side seams, |x| = 0.38 L
+- 0.05). Calls that decide numbers:
- the overskirt panels hang from the waistband over the skirt (Michael, 2026-09-29, in outfit_notes.json): in the back
  view cells 14/15 and in profile cell 27 run unbroken from the waistband into the tails, so they are the panels;
- the skirt's dark hem (the rig's skirt piece includes its hem trim) is the skirt, never the shorts;
- the profile shows the sleeve cuff (`sleeve_cuff_L`), which the notes list as not seen there.

Score: garment accuracy = pixels where the masks' label is among the truth's, over pixels where either puts a piece;
per piece IoU with the truth resolved per pixel.

| masks | front | 3/4 | profile | back | all | mean piece IoU |
|---|---|---|---|---|---|---|
| field `074d9a3f` | 0.943 | 0.882 | 0.801 | 0.808 | 0.865 | 0.786 |
| no field `bc0f48dc` | 0.925 | 0.793 | 0.267 | 0.752 | 0.729 | 0.646 |

The field version's own largest errors: the back panels half called skirt (30 k px), the profile's panel called skirt
(7 k), the skirt's hem called shorts (8.7 k), the crab called the star.

## The choice: (a), the masks from the design sheets alone

Option (a) beat the field on the truth, so the dependency is gone: `outfit.analyse` reads the rig and `body_turnaround`
and nothing else (no `find_field`, no `--field`/`--no-field`, no `charkit/out/i3d`).

**The sheet field** (`outfit.sheet_field`) stands in for TRELLIS in the same pipeline (predict, match, vote):
- every rig layer's whole drawing (alpha, hidden parts too) is laid on per-row elliptic shells: as wide as the rig's
  front at that height, as deep as the sheet's profile; arms and legs round, centred at the depth of their skin in the
  profile (0.319 L, 0.347 L from the near eye);
- later-drawn layers sit outside earlier ones; pieces the front shows whole (`complete()`: the bow, its tails, the bib,
  the skirt's cream panel, the crab) lie on the front half only, and a panel set into a piece shows its piece behind
  it (the skirt runs on behind its front panel); layers drawn before the first skin layer (`hair_back`, `skirt_back`)
  lie on the back half only, outermost there, and keep only their visible pixels (the rig fills the panels' layer in
  right across behind the legs); head pieces standing clear (the buns, the star) get their own round section at the
  profile's depth where they stand clear;
- **a height warp** (`z_warp`): the rig and the sheet are two drawings, not one scale apart. The torso agrees within
  0.03 L, but the sheet hangs the skirt, shorts and panels 0.08-0.24 L lower and sits the buns 0.11-0.14 L higher.
  The rows' colour profiles are aligned by dynamic time warping (`dtw`, anti-diagonal, 0.03 s);
- the front view is predicted by the rig's own layering (resampled through the warp), the others by projecting the
  field; a cell's class reads the nearest label it allows within 0.3 L under the visible surface (the per-class
  stack), not only the front-most;
- **one cell, one piece** (`match_view`): a cell predicted as two pieces is split only where the boundary runs along
  drawn lines (30% within 0.03 L: the back's sleeves-and-bodice cell, whose seams don't close); else it is one piece,
  the one over the other (the rig's order in front, the field's depths elsewhere), else the larger;
- **one vote round** (`relabel`): each field point takes the label the view seeing it most face-on gives it, then all
  views are matched again. The back view shows the panels reaching the waistband (the rig draws them only below the
  skirt), and the vote carries that to the profile.

**Each step against the truth** (garment accuracy; mean piece IoU):

| step | front | 3/4 | profile | back | all | mIoU |
|---|---|---|---|---|---|---|
| field `074d9a3f` (reference) | 0.943 | 0.882 | 0.801 | 0.808 | 0.865 | 0.786 |
| no field `bc0f48dc` | 0.925 | 0.793 | 0.267 | 0.752 | 0.729 | 0.646 |
| shells, first cut | 0.925 | 0.858 | 0.674 | 0.685 | 0.796 | 0.715 |
| + nearest-x coverage, head parts | 0.915 | 0.882 | 0.766 | 0.690 | 0.818 | 0.756 |
| + back halves, back layers' visible pixels, part depths | 0.933 | 0.901 | 0.766 | 0.789 | 0.856 | 0.789 |
| + height warp | 0.978 | 0.899 | 0.799 | 0.803 | 0.878 | 0.838 |
| + front by the rig's order, one cell one piece | 0.993 | 0.890 | 0.810 | 0.985 | 0.933 | 0.874 |
| + stack limited to 0.3 L under the surface | 0.993 | 0.890 | 0.811 | 0.994 | 0.936 | 0.881 |
| **+ one vote round (the branch)** `44f63918` | **0.993** | **0.911** | **0.899** | **0.994** | **0.956** | **0.901** |

A second vote round changes 271 of 293 k points and no score. Per piece the new masks match or beat the field's except
`bun_L` (0.941 vs 0.984), `bun_R` (0.960 vs 0.963) and `sleeve_R` (0.915 vs 0.970). Bit-identical run to run on the
laptop (masks `44f63918`, graph `424a4ed8` from clawd.json). 45 s a run (the field's took 38 s).

**Caveat on the numbers.** The truth's panel calls and the one-piece rule share a premise (a cell with no drawn line
inside is one piece); the back's gain (0.808 to 0.994) is mostly those cells. Without the rule (row "+ height warp")
the sheet-only masks already score 0.878 against the field's 0.865.

**Largest misses left** (31.6 k px): the three-quarter's near panel tail (10 k: the sheet's 3/4 draws it about 0.4 L
nearer the body than its profile does, so no one 3D shape fits both), the profile's panel side (3.6 k) and a band
of skirt called panel (2.1 k), the profile's bun underside (1.6 k), 3/4 hem vs skirt panel (1.5 k), bib vs tails in
3/4 (2 k), the crab clip (0.8 k).

## Merges and gates

- `f2fd29a`: the change (outfit.py, the manifest's outfit_masks and outfit_truth, tests, notes).
- `d74ea46`: pipeline-3d `cfcdc3a` (tool/infra: self-registering QA parts and steps, the gate's 2x2) merged in,
  cleanly; this branch adds no QA part or measurement step. `test_registry.py`, test_outfit, test_manifest pass.
- Produced stamps on the merged tree: default spec masks `1917b45a`, hull `3aa7453d`; clawd_mh masks `ad8a1377`,
  hull `4627103d` (baseline pipeline-3d: hull `0daa9204` / `42475be8`). The masks' bytes are one set for every spec
  (`44f63918`); only the graph's comparison differs by spec.

### Gate round 1: f2fd29a into pipeline-3d 8ae6ce9 (before tool/infra's 2x2)

Both **FAIL**; tests all ok. Baseline masks `074d9a3f` (the gate clone had the field), candidate `44f63918`.

**Default spec (clawd.json)**, worse: every hem (front -0.22, back -0.23, profile -0.31, 3/4 -0.21 L: ours higher),
`body_front_skirt_aline` 0 -> -0.145, `body_front_skirt_overhang_L/R` 0 -> 0.05/0.04, `body_profile_iou` 0.852 ->
0.849, `body_profile_iou_skin` 0.713 -> 0.669, `neck_crease` 27.6 -> 46.4, `piece_collar` 0.754 -> 0.318,
`piece_skirt_extent` 0.127 -> 0.353, the panels' `_extent` 0.07/0.04 -> 0.18/0.15 and `_hang` 0.02/0.03 -> 0.15/0.14.
Better: `piece_waistband` 0.453 -> 0.945, `piece_shorts` 0.393 -> 0.656, `piece_overskirt_panel_L` 0.422 -> 0.553,
`piece_cuff_L` 0.659 -> 0.786. Garments moved: skirt 0.087, waistband 0.025 (9,984 -> 6,144 verts), top 0.013,
collar 0.009, panels 0.029.

**clawd_mh**, worse: `body_front_midriff_gap` 0 -> 0.061, `body_front_skirt_aline` -0.016 -> -0.073,
`body_profile_torso_jump_back` 0.005 -> 0.405, `body_three_quarter_waist_skin` 0.029 -> 0.059, `piece_skirt` 0.831 ->
0.739, `piece_skirt_extent` 0.028 -> 0.278, `piece_sleeve_L` 0.759 -> 0.738. Better: `piece_waistband` 0.497 -> 0.877,
`piece_top` 0.487 -> 0.546, `body_front_skirt_overhang_L/R` 0.118/0.113 -> 0.019/0.028.

**Why.** The skirt, waistband and collar are `source: "hull"`: built from the hull's piece-labelled surface. The new
masks give the back view's cells 14/15 and the profile's cell 27 to the overskirt panels (they hang from the
waistband over the skirt: the truth, and Michael's call), so the hull labels the skirt only where the drawing shows it
at the back (the centre pleats, the outer sides). A skirt lofted from its visible hull points loses its back and comes
out short: the hem FAILs. The field's masks called the upper half of those panel cells skirt (wrong per the
drawing), which gave the loft a whole skirt. `piece_skirt_extent` also read the one real mask error of `44f63918`:
the 3/4's near panel tail labelled skirt (z to -3.04), fixed since (below).

### The tail fix (after round 1)

Below the skirt the profile has two runs (legs and shorts; the tail far behind). Each row's shell took the whole row,
so the shorts' and hem's shells were 1.5 L deep and in the 3/4 projected onto the tail (the 3/4's near tail went to
the skirt and shorts). Now the body's layers take the run on the body's axis (the middle of the one-run rows between
the chest and the hips) and only layers drawn behind the body span the whole row. Masks `73a6eed4`: **0.972** (front
0.993, 3/4 0.966, profile 0.909, back 0.993), mean piece IoU **0.913**, 20,108 px wrong (was 31,568). Left: the
profile's panel side (cell 27: 69% panel, split by partial lines with skirt and the far panel, 4 k px), its skirt hem
cell 69 called panel (2.1 k), the buns' undersides (2.3 k), 3/4 hem vs the skirt's panel (1.5 k), bib vs tails (1.9 k).
