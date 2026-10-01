# layerrefs: the separated-layer reference audit (tool/layerrefs)

Branch `tool/layerrefs` from pipeline-3d 3168961, worktree `~/animation-pipeline-layerrefs`.

**Why (Michael, 2026-10-01).** Clawd's references had no bodice without the bow, so agents guessed what lay under it
(a closed orange V, lapels bunched beside the neck, failed collar checks); the flat-lay breakdown even suggested the
orange V (a flat-lay shows the garment's inside through its neck opening). The rule: wherever accessories, drapery or
independent layers cover something, there is a reference of the cover alone and of the covered layer WITHOUT it, as
worn, in several views. Also, as a fourth trigger in the view rule's step 2 ("is the reference adequate?"): a piece
layered with no separated reference.

Excluded here: the bodice without the bow and the sailor collar alone (tool/garments4's item 2-3 generates it).

## 1. The audit (the layer graph: outfit_graph.json's layering and attachments, the hair, the accessories)

"Cover alone" / "under without": which registered reference draws the covering piece alone, and which draws the covered
layer without it, as worn, in several views. The turnaround draws every outermost piece in context, so for a cover it
is the "in context" view, not the "alone" one.

| # | cover -> covered | cover alone | covered without the cover | evidence of guessing (docs/workstreams) | rank |
|---|---|---|---|---|---|
| 1 | stepped back flaps (overskirt_panel_L/R) -> the skirt's back and side hem | garment_breakdown (flat-lay, flattened, one view); skirt_closeup / skirt_back_sides_detail draw them only with the skirt | none: the hem under the flaps is drawn nowhere | garment-sampling.md: "the hidden back hem is unconstrained, and the views pull it different ways" (body_front_hem 0.047 PASS -> 0.165 FAIL from the fill alone); garments.md: flaps over / under / one skirt was a taste call, rendered as "dark flat wedges"; the 2x2 flipped with the measure | 1 (has hurt) |
| 2 | every garment -> the body (neck-chest join, shoulders under the collar and puffs, torso under the skirt, arms under sleeves and cuffs) | the turnaround (in context) | head_construction: head, neck and shoulder tops only, front and profile, no three-quarter or back, no arms or torso | body.md: torso measured 0-6% under the bow, collar and sleeves, 0% under the skirt (a style prior fills it); "a joint nothing measures (a shoulder under its puff)"; collar.md: the body's shoulder top under the collar and puffs set by variants (body.shoulder s1..c1p2); garments4.md: neck_crease and the neck join | 1 (has hurt) |
| 3 | skirt (and flaps) -> shorts | the turnaround | garment_breakdown's shorts: a flat-lay with belt loops and pockets the design doesn't show, one view | garments.md: "the hull's shorts points aren't the shorts' shape ... only their lower edge (-2.72 L) is trustworthy, so the shorts need the 2D target" | 2 (has hurt) |
| 4 | star clip -> crab clip; both -> the side lock under them | none (the star and crab are drawn only on the hair, face-on) | none (no hair without the clips; no crab without the star) | accessories.md: "the crab's hidden claw pokes through the star", star seat +0.046 L FAIL (it rests on the crab); hairlocks.md / hair5-truth.md: the strip under the star unscored, the face-framing lock "runs from under the star"; Michael: "the crab hidden under the star is poor design" (so moving it needs the whole crab) | 2 (has hurt) |
| 5 | flaps <-> each other and the skirt -> the flaps' own tops at the waistband | garment_breakdown (flat-lay) | n/a | garments3.md / garments4.md: the flaps' tops and tuck fitted from the profile and back; the three-quarter draws the panel "more face-on than any rigid panel can be" | 3 (could hurt) |
| 6 | outer orange skirt -> the cream front panel's hidden extent (inset or underskirt?) | n/a | garment_breakdown draws the cream panel as a full circle skirt; skirt_closeup's top-down as an inset | none yet (the builder treats it as an inset) | 3 (could hurt) |
| 7 | hair -> the back of the neck, the nape, the ears, the collar's back top | n/a | head_construction (front and profile only) | hull-limbs.md: lower_back hair into the shoulder; the hair over the shoulders in back | 4 |
| 8 | waistband -> the bodice's hem and the skirt's top | n/a | none | none found | 5 |
| 9 | boot cuffs -> the boots' tops; boots -> legs and feet | garment_breakdown (boots with the cuffs on) | none | none (boots fit 0.81-0.87; "feet sit inside the boots, a simple template is enough") | 5 |
| 10 | wrist cuffs -> the wrists | sleeve_closeup and hand_breakdown (the cuff drawn plainer, larger) | none (hand_breakdown's hands come out of the cuff) | none | 5 |
| 11 | buns -> the crown | bun_detail's bottom row (a bun alone, five views) | none; the bun is gathered hair, not a separate cover | none | 6 |
| 12 | bangs -> side locks -> back layers (inside the hair) | hair_breakdown (families by colour; covered parts undrawn) | none | the lock truths handle it per drawn lock | 6 |
| -- | bow and tails -> bib, V, collar; collar -> top | bow_closeup | (tool/garments4 generating the blouse without the bow) | the orange V, bunched lapels | excluded |

Also: garment_breakdown's bodice V shows the inside of the back panel (orange), not the bodice front (caution added).

## 2. What to generate (the top gaps, three sheets, one call each, n=2)

1. `skirt_layers` (rows 1, 3, 5, 6 above): each skirt layer alone as worn on a grey mannequin, waist to knees, front /
   three-quarter / profile / back: top row the outer skirt with its cream panel and waistband WITHOUT the flaps (the
   whole hem), middle row the two flaps alone hanging from the waistband, bottom row the shorts alone.
2. `base_body_turnaround` (row 2, and 7 in front): the turnaround redrawn in the same layout, scale and pose with every
   fabric layer replaced by a plain fitted charcoal bodysuit (bare neck, collarbones, shoulders and arms; mid-thigh);
   head, hair, clips, hands and boots kept as registration anchors.
3. `hair_clips_layers` (row 4): the head without the clips (front, three-quarter, profile) and the crab and the star
   each alone (front and edge-on).

## 3. Generation (2026-10-01, tools/gptimage.py via charkit/out/layerrefs/gen.py, n=2 each, ledger)

- `base_body_turnaround` (ref body_turnaround): 2 takes, `charkit/out/layerrefs/gen/base_body_turnaround_{1,2}.png`.
- `hair_clips_layers` (ref head_turnaround): 2 takes.
- `skirt_layers`: the first two wordings were refused by the image API's moderation (no image; ledger `ok: false`;
  prompts kept as `skirt_layers_v1_blocked` / `_v2_blocked`): the lower-body mannequin, a lower-body close-up as input
  and "the shorts alone" read as unsafe. The third (the turnaround as the only input, the garments on legless tailor's
  dress forms, no shorts row) passed: 2 takes. The shorts row was dropped: the base body shows the thighs under them.
- Calls: 5 (2 refused). The `.env` is a gitignored symlink to the main checkout's (remove at the end).

## 4. Refcheck: `python -m charkit.layerref SPEC SHEET --kind body|clips|skirt` (new, QA side, no build reads it)

Tolerances declared in `layerref.TOL` before any sheet was measured. Calibrated (body): the turnaround against itself
PASS (outside 0, kept IoU 1.0); the base body widened 6% about each figure's axis FAILs every view (outside
0.036-0.048, most 0.073-0.095 L, against 0.03 / 0.04).

**Measurement fix (before reading results):** registering the base body by the eyes' spacing put the eye line
0.04-0.07 L off in every view; the sheet is pixel-identical in layout (top, eye and sole rows within 1-3 px, height
ratio 0.9985-1.0000) and the eyes' spacing reads 1.0-1.4% narrow (a pixel of a ~70 px spacing is 1.4%). The scale now
comes from the figures' heights, as refviews.drift registers a redrawn sheet; the eyes' spacing ratio is reported.

**base_body_turnaround** (take 1 / take 2), per view front, three-quarter, profile, back:

| measure | tol | take 1 | take 2 |
|---|---|---|---|
| kept head IoU | >= 0.90 | 0.989 / 0.987 / 0.972 / 0.988 | 0.987 / 0.989 / 0.966 / 0.986 |
| kept legs+boots IoU | >= 0.90 | 0.984 / 0.977 / 0.927 / 0.981 | 0.982 / 0.976 / 0.932 / 0.977 |
| outside the costume | <= 0.03 | 0.004 / 0.006 / 0.016 / 0.009 | 0.011 / 0.007 / 0.016 / 0.013 |
| most outside (L) | <= 0.04 | 0.013 / 0.030 / **0.043** / 0.019 | 0.027 / 0.032 / **0.049** / 0.030 |
| visible skin recall | >= 0.85 | 0.987 / 0.989 / 0.990 / 0.978 | 0.978 / 0.957 / 0.981 / 0.969 |
| eye over soles (L) | +-0.03 | +0.000 / -0.007 / +0.011 / -0.005 | -0.001 / -0.009 / +0.010 / -0.001 |
| hidden share (what it adds) | | 0.72 / 0.71 / 0.71 / 0.73 | 0.71 / 0.71 / 0.70 / 0.73 |

Scale 1.0011 / 1.0000; eyes' spacing 0.986 / 0.990. Take 1 chosen (lower outside in every view). Its profile FAILs
the most-outside by 0.003 L: the back of the thigh below the shorts (z -2.64..-3.20 L, u +0.33), visible skin where
the turnaround is the authority; inside the covered band its most is 0.038 L (the bust's front, z -0.95..-1.08).

**hair_clips_layers** (take 1 / take 2): heads without the clips, front / three-quarter / profile: head IoU 0.980 /
0.977 / 0.976 (take 2: 0.931 / 0.930 / 0.942), clip pixels found by accqa's finder 0 in every view (it finds 6,729 on
the turnaround's front), the turnaround's clip region drawn as hair 0.983 / 1.000 / 1.000: PASS. The clips alone FAIL
as shape references: the crab is a generic symmetric crab (shape IoU 0.49-0.54 against the turnaround's front, three-
quarter and profile crab), and the star, while its shape IoU passes (0.65-0.77), has side arms 0.48-0.51 of its height
against the turnaround's 0.31 (accessories.md's three-view fit: 0.37): an equal-armed compass star, not the design's
tall one. Only the top row (the covered layer) is registered.

## State

(updated as the round goes)
