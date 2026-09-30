# Hair round 5: Michael's flags measured, the hair's truth made finer, the visible fixes (tool/hair5)

State: in progress. Worktree `~/animation-pipeline-hair4`, branch `tool/hair5` from pipeline-3d `004efc3`.

## The brief

Michael's review of the current build (2026-09-30 evening, preview 1580f95; bangs and buns "much improved"):
1. The ahoge has warped (a clean curved strand at the start of the day; now bent and jagged).
2. The flyaway by the right bun is disconnected (floats in the air, front and back).
3. Much of the layering is a solid orange mass, or artifacting and janky, in three-quarter and side views.
4. Much detail in the strays, flyaways and bulk layer isn't defined at all.
5. Back view: vertical stripes (ink lines down the back mass), off-model. The design's back is a smooth mass with a
   wavy, flicked hem and flicks at the sides; ours is a smooth bob with a dark band at the bottom.

Order: (1) every flag as a calibrated check (passes on the design moved 1-2 px, fails on the current build, beats a
random floor); (2) truth granularity: lock truth beyond the bangs (side locks, lower-back flicks, strays, flyaways,
ahoge) as sub-pieces; refcheck hair_breakdown per lock, a generated close-up sheet if inadequate; (3) fixes, the
visible wins first (ahoge, the flyaway's root, the back's stripes and hem flicks), then the layering; (4) every hair
piece's shape IoU in all views beside each moved check; art_terminator_hair (<2.5), art_peeks_hair, hair_noise, folds
not regressing. A review page after steps 1-2.

## Step 1: the flags as checks

### What the numbers said before this round (preview 1580f95)

hair_piece_ahoge 0.322 and hair_piece_flyaways 0.196 INFO (ungraded); nothing measured piece connectivity, lock
layering outside the bangs, or interior lines in the back view.

### Bisecting the ahoge (the day's previews, `~/animation-pipeline-3d/charkit/out/previews/*/qa/qa.json`)

(in progress)

## Jobs

(none yet)
