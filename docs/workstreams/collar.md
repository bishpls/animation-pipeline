# The shoulders, the sailor collar and the bow (tool/collar)

Michael's review flags of 2026-09-30 on the shoulders, the collar and the bow. Branch `tool/collar` in
`~/animation-pipeline-garments3` (sparse charkit worktree), from pipeline-3d d60486a (the combined garments round).

Scratch harness (session scratchpad `co/`, not tracked): `lib.py` (a bundle's QA labels against the drawn piece
masks, iris or knob registration), `pics1.py BUNDLE` (design | drawn pieces | ours per view, chest window),
`shoulder2.py BUNDLE iris|knobs VIEWS` (the upper garments' top edge per column, and what is above it),
`collarshape.py` (the drawn and our collar's runs per row per view), `cu.py BUILD PREFIX` (chest close-ups of a build's
export with charkit.render: level, orthographic, 400 px/L, 2 s), `qaframe.py BUNDLE OUT iris|knobs` (the whole QA with
the body frame registered on the irises, as built, or on the head's eye line), `qadiff.py A B`, `runpart.py BUNDLE OUT
PARTS` (QA parts on a bundle).

## Measured first

### The eye-line offset: how much of the shoulder gap it is

The body QA (bodyqa.origin, and every piece, skirt, detail and flap check through it) registers our irises' plate
mean on the design's eye row; the garment builders, the hull's placement and the code body use the head's eye line
(`eye_knobs.z` = `eye_z`), 0.0235 L lower (g3_render3: iris mean z - eye_z = 0.02354 L). The face QA (qa3d.eye_anchor)
and the art_* frames (lookqa.HeadFrame) register on eye_z.

- **The shoulder gap:** the back view's upper-garment top edge over |x| 0.25-0.55 L reads 0.0565 L under the drawn one
  (ours -0.566, design -0.510/-0.514). 0.0235 of that is the frame; **0.033 L is geometry**, and a 0.047-0.066 L dip
  sits between the collar's edge and the puffs (the torso's top rows slope down from the neck ring: half-width 0.226
  at the cut, 0.38 at z -0.60, 0.41 at -0.64; the arm tubes start at the shoulder joint, z -0.886).
- **The whole QA under both registrations** (qaframe.py on g3_render3's bundle; the local QA reproduces the box's
  qa.json on every check but hair_folds, whose builder count is box-only): 374 checks unchanged, 98 moved, 8 better,
  7 worse. Better with eye_z: piece_sleeve_cuff_R 0.555 -> 0.803, _L 0.712 -> 0.778, piece_sleeve_R 0.779 -> 0.861,
  the shorts' hems (4 views) WARN -> PASS, body_profile_chest 0.045 -> 0.028, skirt_back_outline FAIL -> WARN. Worse:
  everything tuned by hand or by fit in the iris frame (waistband rows 0.005 -> 0.028 in three views, its profile
  overhang WARN -> FAIL, top_front_opening, piece_bow 0.696 -> 0.659, piece_top, piece_bodice_panel, flap_profile_iou_L)
  and the hair, which is placed by the irises (hair_piece_* 0.02-0.07 lower, body_*_top 0.005 -> 0.028,
  hair_fringe_low PASS -> WARN). The feet read 0.014 L high on the irises, 0.038 on eye_z.
- **Not fixed here (a decision):** a one-place fix is either the QA's registration (bodyqa.origin on eye_z: the
  hull-built pieces then read as built, but the band's rows, the bow's lift, the jacket's hang and opening, the skirt
  fit and the hair's iris placement were all tuned in the iris frame and would need refitting) or the builders' eye
  line on the irises (the hull, the code body and every garment 0.0235 L up against the head: the neck 0.0235 L
  shorter at tool/face's join). Both reach well beyond this round. This round builds and measures in the QA's current
  frame; the shoulders are raised by the geometry share (0.033 L plus the dip), not the frame's.

