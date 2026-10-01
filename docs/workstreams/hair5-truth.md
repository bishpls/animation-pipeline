# Hair round 5, step 2: truth granularity (tool/hair5, sub-workstream)

State: done (this step); the round's main agent commits. Truth 52 locks; h5_base 0.331 against a random split's 0.392. Worktree `~/animation-pipeline-hair4`, branch `tool/hair5`
(pipeline-3d 004efc3 + the round's commits). Michael's flags this answers: "much of the layering is a solid orange mass
or janky in three-quarter and side views", "a lot of detail in the strays, flyaways and bulk layer isn't defined at
all"; his suspicion that our truth isn't fine-grained enough (the lock truth covered only the bangs; the hair masks are
family-level).

## A. Is hair_breakdown a lock-level reference? No.

`tools/hair5truth/refcheck.py SHEET OUT.json [--breakdown] [--views ...] [--pics DIR]`, measured against the body
turnaround on its design grids (212.5 px/L):
- **silhouette**: the sheet's hair registered per view (a scale S and an offset, searched on the hair and the face's
  skin as `hairlayers.register` does, but per view, so a sheet that doesn't keep one scale shows it) -> hair IoU (all,
  and below the buns' zone);
- **flatness**: the sheet's flat-colour regions (its hair split at its black lines and at Lab steps over 7); a region is
  flat if its p90 distance to its median colour is under 6 Lab; the flat share of the hair area;
- **lock lines**: the regions' boundaries inside the hair, mapped onto the grid and skeletonised, against the body
  sheet's drawn lines inside its hair (the raw line class and the faint ridges, 3 px or more inside the outline,
  skeletonised): precision, recall, F within 2.5 px (and 5 px); the floor: a random Voronoi partition of the sheet's hair
  into as many regions, scored the same (5 seeds); the ceiling check: the sheet's lines 1 px off against themselves
  (F 1.0);
- **lock IoU against the extended truth** (C below): the sheet's regions on the grid scored as a lock partition
  (`tools/hair5truth/score5.py`).

| sheet | view | S px/L | hair IoU | below buns | line F 2.5 px / floor | line F 5 px / floor | flat share | regions |
|---|---|---|---|---|---|---|---|---|
| hair_breakdown | front | 517 | 0.825 | 0.851 | 0.237 / 0.160 | 0.424 / 0.351 | 0.41 | 48 |
| | profile | 533 | 0.813 | 0.848 | 0.231 / 0.151 | 0.390 / 0.315 | 0.60 | 32 |
| | back | 505 | 0.911 | 0.925 | 0.281 / 0.077 | 0.467 / 0.167 | 0.92 | 32 |
| close-up take 1 | front | 406 | 0.821 | 0.846 | 0.270 / 0.162 | 0.497 / 0.340 | 0.34 | 43 |
| | three-quarter | 403 | 0.823 | 0.840 | 0.231 / 0.163 | 0.430 / 0.337 | 0.30 | 37 |
| | profile | 420 | 0.826 | 0.845 | 0.201 / 0.145 | 0.378 / 0.293 | 0.42 | 25 |
| | back | 404 | 0.905 | 0.921 | 0.197 / 0.074 | 0.442 / 0.162 | 0.70 | 26 |
| close-up take 2 | front | 427 | 0.823 | 0.850 | 0.287 / 0.163 | 0.538 / 0.343 | 0.45 | 47 |
| | three-quarter | 420 | 0.818 | 0.847 | 0.243 / 0.154 | 0.442 / 0.316 | 0.29 | 39 |
| | profile | 434 | 0.842 | 0.854 | 0.250 / 0.150 | 0.470 / 0.314 | 0.58 | 27 |
| | back | 420 | 0.888 | 0.913 | 0.173 / 0.069 | 0.368 / 0.146 | 0.68 | 27 |

Readings:
- **The breakdown is family-level.** Its region boundaries meet the sheet's drawn lock lines at F 0.23-0.28 within
  2.5 px (random partitions 0.08-0.16): 70-80% of the drawn lines have no counterpart and 70% of its boundaries fall
  off them. Its front is 41% flat (the bangs and side locks blend red to orange to yellow), and its back is two flat
  masses (upper purple, lower pink: 92% flat because it has no locks at all). Its regions per family (front: bangs 4,
  side locks 12, buns 15) count highlights and the buns' shading facets, not locks.
- Its silhouette registers at 0.81-0.91 (hairlayers' one-scale registration reads 0.68-0.80 with the buns' zone out).
- Against the extended lock truth (C), as a lock partition: 0.319 over its three views (a random split of the truth
  0.392); drawn locks it recovers at IoU 0.5: side locks 5 of 6, bangs 4 of 8, flyaways 5 of 14, the hem's flicks 0 of
  11, the ahoge 1 of 3. It resolves the face-framing locks and nothing finer.

## B. The generated lock-level close-up: neither take is adequate in any view

One call, n=2 (Michael approved): `tools/gptimage.py`, gpt-image-2.5-sunburst (the default), 2560x1440, quality high,
refs in order body_turnaround (the authority), head_turnaround (detail), hair_breakdown (the colour code); prompt
recorded as `charkit/refs/clawd/gen/prompts.json` `hair_lock_closeup` (also `charkit/out/hair5truth/prompt.txt`);
outputs `charkit/out/hair5truth/gen/hair_lock_closeup_{1,2}.png`; ledger line 2026-09-30T20:09:13. The `.env` symlink
was made for the call and removed right after (in the same command).

Both takes copy the breakdown's style rather than the turnaround's locks: blended fills (front 34-45% flat, the
three-quarter 30%), the back again two flat masses (upper purple, lower pink), green strands at the side flicks.
They keep one scale (take 1: S 403-420, take 2: 420-434 px/L, within 4%) and their silhouettes register as well as the
breakdown's (0.82-0.91), and they add the three-quarter the breakdown lacks. But their lock lines meet the sheet's at
F 0.17-0.29 (floors 0.07-0.16), no better than the breakdown's. As lock partitions against the truth: take 1 0.369,
take 2 0.360 (random split 0.392); per view take 1 / take 2 / random: front 0.436 / 0.436 / 0.297, three-quarter
0.470 / 0.416 / 0.460, profile 0.369 / 0.344 / 0.363, back 0.212 / 0.232 / 0.486. Take 2 recovers the side locks (9 of
10 at IoU 0.5) and 7 of 15 strands, 3 of 12 bang locks and 0 of 11 hem flicks. **Not copied to `charkit/refs/clawd/gen/`**: no view of
either take is a lock-level reference. Where they agree with each other and the breakdown (green strands at the side
flicks), they informed call F below. Pictures: `charkit/out/hair5truth/refcheck/{breakdown,take1,take2}/` (per view the
registration outline in blue, the sheet's lines black, its boundaries red, matches green).

## C. The lock truth beyond the bangs

`charkit/refs/clawd/hair_locks_truth.{json,npz}`, rebuilt by `python -m charkit hairlocks truth`; the bangs' entries are
unchanged in the source and their 12 locks are pixel-identical in the npz (checked against the committed npz). The
same method as the bangs (the sheet's hair cells cut along polylines, regions labelled by seeds), new rules 8-14 and
calls F-J in the source. Tools: `tools/hair5truth/tpic.py VIEW SRC OUT --box ... --zoom N` (the source over a zoomed
crop with its problems and the completeness test), `pic5.py` (the sheet, the labeller's regions, the family truth),
`ctx5.py` (a lean cache of hairlocks' context), `hem.py` (the hem's tips and notches along the outline; a helper, the
cuts were read by eye).

**Size: 52 locks** (was 12):

| view | bangs | side_locks | lower_back | flyaways | ahoge | all |
|---|---|---|---|---|---|---|
| front | 5 | 4 (R_front, L_front, R_jaw, L_jaw) | 2 (flick_R3, flick_L3) | 6 (under_bun_R/L, flick_R1/R2/L1/L2) | 1 | 18 |
| three-quarter | 4 | 4 (R_front, R_jaw, L_front, L_jaw) | | 1 (under_bun_L) | 1 | 10 |
| profile | 3 | 2 (L_front, L_jaw) | 2 (flick_P1, flick_P2) | 2 (under_bun_L, flick_P) | 1 | 10 |
| back | | | 7 (flick_L3, L2, L1, C, R1, R2, R3) | 6 (under_bun_L/R, flick_L1/L2/R1/R2) | 1 | 14 |

The rules added (the source's `rules` 8-14):
8. Scope: front and profile: bangs, side_locks, lower_back, flyaways, ahoge; three-quarter: bangs, side_locks,
   flyaways, ahoge (complete: false, as before); back: lower_back, flyaways, ahoge.
9. The ahoge is one lock per view, cut straight across its base at the head's outline (the family truth's cut).
10. Each flyaway strand is its own lock: the strands under the buns, and the side flick tips the family truth reads as
    flyaways-or-mass (its call A), cut straight across their base notch to notch.
11. A hem flick is the hair below the straight line through the upper ends of the notch strokes that bound it (the
    notch's apex where there's no stroke); the notch strokes part neighbouring flicks; the mass above the bases is
    unscored ('x'); hem parts with no drawn tip (cut by the collar or the shoulder) are unscored.
12. The face-framing lock (R_front, L_front) runs from the bangs' cut at the eyes' top or from under the star to its
    tip by the cheek, bounded by the long stroke on its outer side; the jaw lock (R_jaw, L_jaw) is the next lock out.
13. The outer masses (side_locks|upper_back and the shadow-tone under-layer at the sides) are unscored: their lock
    lines are partial strokes that don't close.
14. R / L are her right / left; names kept across views where the correspondence is read; the profile's own names end
    in P.

**Calls for Michael** (the source's calls F-J):
- F. The side flick tips (front 4, back 4, profile 1) are scored as flyaways (the breakdown and both takes draw green
  strands there), not as the mass's locks.
- G. The outer masses (the bulk at the sides) are unscored: a finer cut needs a lock-level reference, and neither the
  breakdown nor the takes is one. This is the part of the bulk layer the truth still can't grade.
- H. Correspondence: the under-bun strands are the same in every view; the front's and back's side flicks
  (flick_L1/R1 rows 262-263, flick_L2/R2 rows 321-328) and lowest outer hem flicks (flick_L3/R3, rows 365-366) are the
  same flicks; the profile's back flick and hem flicks (flick_P, flick_P1, flick_P2) sit on the silhouette's back edge
  where the side flicks can't, so they keep the profile's own names.
- I. The back's hem has seven flicks; a strand stroke inside L1 and a split stroke in R1 don't part them.
- J. The three-quarter's side locks; L_jaw's outer side is cut along its drawn edge across the stroke's gaps.

## The scorer: the strands' families and per-family results (`charkit/hairlocks.py`, small, backward-compatible)

- `TRUTH_FAMILIES = LOCK_FAMILIES + ('ahoge', 'flyaways')`: a lock label may name them (`is_label`), and a build's
  ahoge and flyaway pieces are lock regions (each piece's per-vertex `lock`), not occluders; the buns still occlude as
  hair.
- `score_view` adds `families`: per truth family its locks, ours, matched, mean lock IoU (unmatched 0) and the partition
  alone; `score` adds them over the views under `all`; the CLI prints them.
- Checked: h5_base against the bangs-only truth scores the same with and without the strands as locks (0.431; front
  0.461, three-quarter 0.395, profile 0.428). No QA check reads the lock truth (grep: only the CLI and the tests).
- `charkit/tests/test_hairlocks.py`: the per-family result on the known answers and the families' own score 1.0 on the
  tracked truth added; all pass.

## The base build against it (h5_base: pipeline-3d 004efc3, the default spec)

`tools/hair5truth/ours5.py charkit/out/h5_base charkit/out/hair5truth/ours/h5_base.npz` (the build's locks z-buffered
on the grids; the strands as locks), then `tools/hair5truth/score5.py OUT.json NAME=LOCKS.npz ...` (the per-family
lock IoU with the floors: the truth against itself, filled as the scorer fills it, 1.0; a random Voronoi split of the
truth's locks in each view, as many cells as locks (hairlocks.shuffled, 5 seeds); a random split within each family,
the family boundaries kept). The sheets' regions (refcheck's `_regions.npz`) scored the same way. Scores:
`charkit/out/hair5truth/scores/scores.json` and `scores.log`.

**All views** (lock IoU, unmatched locks 0; red on the review page: below the random split):

| family | truth locks | random split | random within family | **h5_base** | locks at IoU >= 0.5 (h5_base) | breakdown | take 1 | take 2 |
|---|---|---|---|---|---|---|---|---|
| bangs | 12 | 0.398 | 0.470 | **0.435** | 5/12 | 0.320 | 0.417 | 0.319 |
| side_locks | 10 | 0.429 | 0.445 | **0.382** | 1/10 | 0.585 | 0.613 | 0.635 |
| lower_back | 11 | 0.294 | 0.619 | **0.316** | 3/11 | 0.075 | 0.037 | 0.024 |
| flyaways | 15 | 0.375 | 0.504 | **0.211** | 1/15 | 0.383 | 0.407 | 0.455 |
| ahoge | 4 | 0.609 | (1.0: one lock) | **0.379** | 0/4 | 0.390 | 0.393 | 0.355 |
| all | 52 | 0.392 | 0.547 | **0.331** | 10/52 | 0.319 | 0.369 | 0.360 |

Per view (h5_base / random split): front all 0.335 / 0.297 (bangs 0.461, side_locks 0.430 / 0.345, lower_back 0.184
/ 0.011, flyaways 0.213 / 0.256, ahoge 0.345 / 0.603); three-quarter 0.363 / 0.460 (side_locks 0.409 / 0.489,
**flyaways 0.000**: no strand of ours under her left bun there); profile 0.302 / 0.363 (**side_locks 0.232** / 0.476,
lower_back 0.117 / 0.086, flyaways 0.281 / 0.197); back 0.323 / 0.486 (lower_back 0.410 / 0.435, flyaways 0.222 /
0.516, ahoge 0.324 / 0.659).

Readings:
- **The base build's locks score below a random split of the truth overall** (0.331 against 0.392), in line with
  Michael's flags: only the bangs beat the random split (0.435 against 0.398, below the within-family split's 0.470).
- **The strands are the furthest off**: flyaways 0.211 against a random split's 0.375 (1 of 15 drawn strands and flicks
  matched at IoU 0.5; none in the three-quarter), the ahoge 0.379 against a random cell's 0.609 (0 of 4 at 0.5: the
  warped ahoge Michael flagged).
- **The side locks are worst in profile** (0.232 against 0.476): the "solid orange mass" in side view; the face-framing
  and jaw locks there aren't separate locks of ours.
- **The hem**: the back's flicks score at a random split's level (0.410 against 0.435); profile 0.117, front 0.184.
- The sheets as lock partitions confirm A and B at the lock level: they resolve the face-framing side locks (0.59-0.64,
  9 of 10 at IoU 0.5 in take 2) but not the bangs (0.32-0.42, about the random split) and not the hem at all
  (0.02-0.08: their lower back is one mass).

The CLI (`python -m charkit hairlocks score charkit/out/h5_base --json ...`, log `charkit/out/hair5truth/scores/h5_base_cli.log`) reproduces these per family exactly.

Review page: `charkit/out/hair5truth/review/index.html` (`tools/hair5truth/review.py`, `index.py`): the summary box,
per view the body sheet | the lock truth (each lock its colour in its family's hue, its name; unscored hatched) | take 1
| take 2 registered at the sheet's scale, the refcheck and per-family tables.

## Files (for the commit)

- `charkit/refs/clawd/hair_locks_truth.json`, `charkit/refs/clawd/hair_locks_truth.npz` (the truth, rebuilt)
- `charkit/hairlocks.py` (the strands' families, per-family results), `charkit/tests/test_hairlocks.py`
- `charkit/refs/clawd/gen/prompts.json` (`hair_lock_closeup`), `tools/ledger.jsonl` (the one image call's line)
- `tools/hair5truth/` (ctx5, pic5, tpic, hem, refcheck, ours5, score5, review)
- `docs/workstreams/hair5-truth.md`
- outputs (untracked): `charkit/out/hair5truth/` (gen/, refcheck/, ours/, scores/, review/, pics/, src_work.json)

## Next steps

1. Michael's calls F (side flicks as flyaways), G (outer masses unscored), H (cross-view names), and whether to spend
   another image call (below).
2. The outer masses (the bulk at the sides, call G) are the one part of Michael's "bulk layer" the truth can't grade
   yet. Options: (a) another generation with only the body turnaround as a ref (both takes copied the breakdown's
   colour code and its blends; the breakdown as a ref seems to be what pulled them to family level), asking for line
   art only (every lock outlined, no fill), which the refcheck's line F would grade directly; (b) cut them by eye from
   the head turnaround (higher resolution; a different generation, so its locks need the same refcheck first).
3. Gate-side: the scorer's change is measurement-only (no QA check reads the lock truth); if the round wants a lock
   check in the QA, it needs a calibration record (the truth passes at 1.0, h5_base is the known-bad at 0.331 against
   the random split's 0.392).
4. The fixes (step 3 of the round) can use the per-family scores as their before/after: flyaways 0.211 and ahoge 0.379
   first (the visible wins), then the profile's side locks (0.232).
