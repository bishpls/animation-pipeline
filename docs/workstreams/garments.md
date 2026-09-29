# Garments as pieces (tool/garments)

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
