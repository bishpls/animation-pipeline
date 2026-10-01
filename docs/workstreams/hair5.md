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

### The checks (charkit/hairflagqa.py, QA part `hair_flags`, order 1450; calibration charkit/calib/hairflags.py)

Ours: every hair component (a lock, a bun's part, the ahoge, each flyaway blade) z-buffered with its own code on the
design grids (bodyqa.design_views, 212.5 px/L) among the QA's occluders; our ink inside the hair = the boundaries
between two of our parts (each lock is its own shell with its own outline hull: where shells meet, a line). The
design: the hair truth (tool/hairtag) with its drawn lines absorbed into the nearest region, and the sheet's drawn lines
(raw line class + outfit.ridges). Every check is a flag check (registry.flag_check).

| check | what | Michael's flag | design (moved 1-2 px) | known-bad 1580f95 | start (h4n_nocrown, = 1583cd6's hair) | h5_base (004efc3) | floor |
|---|---|---|---|---|---|---|---|
| hair_ahoge_shape | boundary F within 0.01 L at the best placement within 0.03 L, worst of 4 views (limits 0.75 / 0.55) | 1 | 1.0 | 0.371 FAIL | 0.402 FAIL | 0.371 FAIL | turned 25-45 deg 0.20, clump 0.27; probe 1.5-wave bend 0.55 |
| hair_ahoge_bend | centreline turning beyond one steady curl, beyond the design's, deg (25 / 50) | 1 | 0 | 107 FAIL | 58 FAIL (profile S) | 108 FAIL | turned 38; bend probe 78 |
| hair_attached | worst gap of a non-mass part to the rest of the hair, L (0.006 / 0.015) | 2 | 0 | 0.033 FAIL | 0.022 FAIL | 0.029 FAIL | moved pieces 0.002 (a defect detector) |
| hair_back_lines | back view: ink inside the mass per L^2 beyond the drawing's 1.30 (0.5 / 1.0) | 5 | -0.07..0.26 | 4.56 FAIL | 6.43 FAIL | 4.57 FAIL | random partition -0.39; stripes probe 8.3 |
| hair_back_hem | back hem tips vs the drawing's 8 (2 / 4) | 5 | 0 | 5 (3 tips) FAIL | 5 FAIL | 5 FAIL | smoothed hem 8 |
| hair_lock_lines_three_quarter | line F of our ink vs the drawn lines in the mass (0.7 / 0.45) | 3 | 0.97-1.0 | 0.185 FAIL | 0.194 FAIL | 0.187 FAIL | random partition 0.07, solid 0 |
| hair_lock_lines_profile | the same in profile | 3 | 0.96-1.0 | 0.208 FAIL | 0.142 FAIL | 0.211 FAIL | 0.06, 0 |

All 7 calibrated (records in charkit/calib/records, built on h5_base; known-bad `hair5_1580f95` = preview 1580f95's
bundle, copied to charkit/out/hair5/kb and stored). Flag 4 (undefined detail in strays, flyaways, bulk) is the truth's
granularity (step 2), partly the lock lines. Not measured yet: the back's dark band at the hem (a tone measure; the
head turnaround's back draws its under layer darker too).

### Bisecting the ahoge (the day's previews' qa.json and local builds)

hair_piece_ahoge is identical from 1583cd6 through 0597b58 (crowntrim, garments3, face4-crown change nothing of it) and
moves at 3ebc3fb (tool/hairtag: the structure masks). Local builds on the same merged head: h6_off (STRUCT_OFF, the plain
transfer) has the start's ahoge exactly (shape 0.402, bend 68 front), h6_m (the structure masks) has today's (0.371,
107). hull-local (004efc3) moved nothing. **Cause:** ahoge_2d builds the ahoge from the front and profile masks'
topmost stroke; the structure masks give the ahoge's shaded lower half to the bangs (hairtag noted: truth front ahoge
0.846 -> 0.827), so the stroke is a crescent cut off above its base; its centreline (path bins from the end nearest the
rest) starts at the cut's corner and turns an elbow (bent), and the bins across the cut are 2-6x wider than the strand
(root widths 17-31 px against 5 before: jagged).

The flyaway by her left bun (picture right in front, left in back) floated at the start too (0.022 L); its gap grew to
0.033 L between b43c15e and 25b1936 (hair_piece_flyaways moves at d60486a, the sheet-only outfit masks). In 3-d it is
0.077 L from any hair surface. The ahoge also floats in profile (0.0086 L) in every build since the start.

## Step 2: truth granularity (a sub-agent, notes in docs/workstreams/hair5-truth.md)

(running: refcheck hair_breakdown per lock; a lock-level close-up sheet if inadequate; the lock truth extended to the
side locks, lower-back flicks, flyaways and the ahoge)

## Step 3: fixes (lab: tools/hair5/lab.py over charkit/out/h5_base)

### The ahoge as a fitted template (hairpieces.ahoge_fit, opts ahoge='fit')

- `ahoge_region`: the drawn ahoge whole (the hair layers' stroke and the drawn hair it joins above the head's outline,
  the outline under it a circle through the crown's edge either side), so the shaded half the structure masks call
  bangs is back; `strand_centreline`: path bins from the whole base (a cut base starts mid-way, no elbow).
- `ahoge_fit`: a cubic Bezier in 3-d fitted by least squares to the drawn centrelines in front, profile and back (both
  ways' distances, root and tip), a crescent's width profile (0.45 of the widest at the root, widest at 0.4 of its
  length, 0.05 at the tip; the widest from the drawn front and back), the root carried 0.04 L on into the crown.

| ahoge (lab over h5_base) | shape F worst (front / 3q / profile / back) | bend worst | attached | hair_piece_ahoge front / profile / back |
|---|---|---|---|---|
| 2-d pairing (today) | 0.363 | 104 | profile 0.0086 | 0.29 / 0.35 / 0.33 |
| fit | 0.506 (0.516 / 0.555 / 0.701 / 0.506) | 6.8 PASS | 0 | 0.48 / 0.50 / 0.65 |

## Jobs

(none running)
