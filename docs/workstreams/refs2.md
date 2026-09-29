# Better references: extra views for the hull, detail sheets (`tool/refs2`)

More drawn views of Clawd for the visual hull, where the hair's back and sides, the buns and the skirt's back
panels come from, plus detail sheets for the builders. Generated with gpt-image-2.5-sunburst; nothing carves until
leave-one-out says it helps.

## What a new view can add

Only azimuths modulo 180 carve: the view from az + 180 is the same silhouette, mirrored. The sheet's four views
sit at 0, 35.5 (the drawn three-quarter's measured angle), 90 and 180 (which repeats 0). That leaves 90..180 open,
the back quarters, where the hull is the shape prior's ellipses. A right profile (270) or a back three-quarter at
225 adds nothing to the silhouette. A view from the top would need an elevation the hull's views don't have, and
it carves little, because the skirt and the hair are the widest things from above.

The baseline hull's leave-one-out (`python -m charkit.geom hull charkit/spec/clawd_body.json`):

| held out | IoU |
|---|---|
| front | 0.945 |
| profile | 0.354 (without it nothing gives depth) |
| three-quarter | 0.876 |
| back | 0.947 |

The worst held-out piece IoUs: the back view 0.50 (collar 0.13, top 0.17, waistband 0.25) and the profile 0.54
(skirt panel 0.19, overskirt L 0.22).

## Three ways to generate them (n = 3 each, same measures)

- **A. Anchored edit.** body_turnaround.png, on a canvas widened by 1,280 px of its own grey, goes to the edits
  endpoint. The prompt asks for two views added in the empty space and the four originals kept pixel for pixel.
- **B. Fresh call.** body_turnaround is attached; the prompt asks for the two views on a 1280x1440 canvas at the
  sheet's scale.
- **C. A, told the turn is rigid.** "A statue on a turntable", "halfway between the profile and the back".

`python -m charkit.refviews SPEC CAND --views back_l:4:150,back_r:5:210 [--bands ..] [--extends] --loo` measures:

- **Drift** (A, C): each redrawn original against the true sheet, registered. Tolerance: IoU 0.95, scale 2%, eye
  and ground lines 0.03 L.
- **Registration**: the new views' scale (figure height against the sheet's back view) and their soles against the
  ground line.
- **Hull agreement**: silhouette IoU against the hull of the sheet's four views at the fitted azimuth, per band and
  per class.
- **Twist**: the azimuth fitted to the head band minus the legs band's.
- **Leave-one-out**: with the new views, and a forward selection of height bands.

| method | drift | abs ground L | fit IoU | twist deg | buns | cream | banded gain |
|---|---|---|---|---|---|---|---|
| A anchored | 3/3 pass (worst IoU 0.981, scale 0.22%, eye 0.015 L) | 0.006 | 0.831 | 25 | 0.79 | 0.41 | +0.026 |
| B fresh | n/a | 0.042 | 0.811 | 36 | 0.74 | 0.28 | +0.028 |
| C anchored, rigid | 3/3 pass (worst IoU 0.983) | 0.007 | 0.842 | 15 | 0.71 | 0.40 | +0.071 |

**A gives the more stable set: C, which is A with the rigid-turn prompt, is the method to use.** The anchored edit
keeps the originals within about 1.7% IoU and puts the new views on the sheet's own lines. A fresh call drifts off
the ground line by 7-11 px and twists more. B's banded gain equals A's only because its heads are twisted furthest
toward the profile.

### The finding: generated back three-quarters are twisted

Fitting the azimuth per height band shows no candidate is a rigid turn. The head and bodice are drawn 10-45
degrees further round than the legs (A3's back_l: head 135, bodice 140, skirt 145, legs 157.5). Carving with a
whole view therefore cuts the front's and back's held-out IoU by 2-7%: every candidate failed "holds or improves"
as a whole view. `hull.extra_views` now splits a view into height bands, each fitted on its own heights
(`View.zband`: a band carves, restores, scores and colours only its heights).

Forward selection: a band joins if every sheet view's held-out IoU holds within 0.002 or improves, against the
selection so far. **The skirt band was rejected in all nine candidates** (front and back -0.6..-3.6%). Split in
two, the upper skirt (-2.3..-1.4 L) passes, but the stepped hem panels (-3.5..-2.3 L) don't: the models draw
the long back panels' hang differently from the sheet's front and back every time.

## Kept

- **`body_turnaround_back34`** (C_rigid_3; `extends: body_turnaround`, **`hull: false`**: in the manifest, off for
  the hull by default, see "Downstream"). Views back_l (figure 4) and back_r (figure 5), with the bands the
  build keeps: bodice (-1.4..-0.8) and skirt_upper (-2.3..-1.4).
  - Leave-one-out kept head (z >= -0.8), bodice, upper skirt and legs (< -3.5).
  - Fitted azimuths per band (head / bodice / skirt / legs): back_l 133.5 / 137.5 / 142 / 158.5; back_r
    223 / 219.5 / 215.5 / 208.
  - With the four LOO-kept bands, held out against the sheet alone:

    | view | change |
    |---|---|
    | front | -0.0024 (each step within 0.002; cumulatively just over) |
    | profile | +0.086 |
    | three-quarter | +0.010 |
    | back | +0.0005 |

- **`bun_detail`** (bun_detail_1): the heads at the sheet's four angles (registered by the front's eye spacing;
  head-top IoU 0.929-0.952, buns 0.89-0.94) and one bun alone from five angles. It's for the hair-detail fork's
  block-loop bun template. The single-bun row is unchecked, since no sheet view draws a bun alone.
- **`skirt_back_sides_detail`** (skirt_detail_2):

  | view | IoU against the sheet's skirt |
  |---|---|
  | front | 0.927 |
  | three-quarter | 0.844 |
  | profile | 0.799 |
  | back | 0.913 |

  Its three-quarter backs score only 0.61 against the extension's (whose hem band is rejected). Use them for panel
  order and overlaps, not widths.

## Downstream: box builds of clawd_body.json with `--hair pieces`

Before: the sheet-only hull at the merged base (0470b37).

| check | before | 4 LOO bands | V1: bodice + upper skirt | V2: V1, shape only |
|---|---|---|---|---|
| body_back_skirt_width | 1.995 FAIL | 0.963 PASS | 0.963 PASS | 0.968 PASS |
| body_front_skirt_width | 0.795 FAIL | 0.679 FAIL | 0.679 FAIL | 0.549 FAIL |
| body_back_hem_mid | 0.141 WARN | 0.188 FAIL | 0.188 FAIL | 0.198 FAIL |
| piece_overskirt_panel_R | 0.526 WARN | 0.331 FAIL | 0.330 FAIL | 0.325 FAIL |
| piece_overskirt_panel_L | 0.451 FAIL | 0.326 | 0.326 | 0.306 |
| piece_cuff_L | 0.443 FAIL | 0.693 WARN | 0.693 WARN | 0.436 FAIL |
| piece_skirt | 0.803 | 0.829 | 0.829 | 0.822 |
| hair_piece_buns | 0.686 | **0.632** | 0.684 | 0.686 |
| hair_piece_upper_back | 0.776 | 0.748 | 0.775 | 0.776 |
| body_front_feet (L) | -0.005 | **+0.047** | -0.005 | -0.005 |
| body_front_top (L) | -0.033 | -0.047 | -0.038 | -0.038 |

What the variants show:

- **The head band makes the buns rounder.** The extension draws them rounder than the sheet, and its bands carve
  their corners. Dropping it restores hair_piece_buns and the other hair checks.
- **The legs band carves the soles**, and the authored body's feet stand on the hull's lowest boot points.
- **The upper-skirt band narrows the skirt's sides.** That fixes the back's width (the ellipse prior was twice the
  design's there), but it narrows the front and the panels too. Keeping the sheet's labels (V2) doesn't bring the
  panels back, so it's the shape, not the labels.
- **Leave-one-out misses this.** The restore step keeps every silhouette, so held-out silhouettes hold while the
  volume behind them moves. A band that passes leave-one-out can still move the builders' radius fields.

Net: two checks improve (back skirt width FAIL to PASS, cuff_L FAIL to WARN) and two regress (panel_R WARN to
FAIL, back hem_mid WARN to FAIL). The front width and the panels also get worse, so the extension stays off
(`hull: false`). Turn it on with one manifest line and re-measure once tool/body's panels are flaps over the skirt.

## Rejected

- A1-3, B1-3, C1-2 as the hull's extension. All drift- and registration-clean except B, but each kept a smaller
  set or gain than C3 (see the table on the review page).
- **bow_detail 1-2**: the bust's garment against the sheet's scores 0.74 (threshold 0.85). The detail draws the
  puff sleeves without arms, so part of that gap is the sleeves. The check doesn't isolate the bow, so the sheet
  isn't trusted until a bow-only check exists.
- **skirt_detail_1**: it passes (0.846), but skirt_detail_2 measures better (0.871).
- bun_detail_2 passes (0.935), but bun_detail_1 measures better (0.940).

## In the hull

- `extras_for` reads the manifest's references with `extends` equal to the body sheet's id.
- `extra_views` calibrates them: scale and eye line from the sheet's lines, then azimuth and axis fitted per band
  against the hull of the sheet's own views.
- They carve and restore with the rest, and colour and class the surface where they face it best.
- The face's carve and the drawn pieces stay the sheet's four views. The extra views get pieces from
  `extra_pieces`: the sheet's labels, seen from their azimuth, voted per drawn cell of their own picture. Each
  held-out check remakes them without the held-out view.
- The build's report carries `leave_one_out_sheet_only` and `leave_one_out_without` (each extra view left out,
  its bands together), plus the pieces' labels with and without them. `pieces: false` on a view keeps the sheet's
  labels.
- The hull's stamp reads the extension's `views` and `hull` (the hull entry's `reads`), so changing the bands or the
  switch rebuilds it.

## Cost

Six gpt-image-2.5-sunburst calls, 15 images: **$1.02** at $30/M image-output, $8/M image-input and $5/M text
tokens. Calls are logged in the main checkout's ledger (2026-09-29T16:35 to 17:08).

## Next

- The hem panels need a view the models draw consistently, or a construction prior: the stepped panels'
  hang is where every generated view disagrees.
- The bow needs a check of its own (the cream bow's region against the sheet's, the sleeves left out).
- Pieces for the extra views come from voting. Outfit masks drawn for them (charkit.outfit on the extension's
  figures) would make them independent evidence.
