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

## Step 2: truth granularity (a sub-agent; its notes: docs/workstreams/hair5-truth.md; committed 0f77b9b)

- **hair_breakdown is family-level, not a lock reference**: blended fills (front 41% flat colour), the back two flat
  masses; registered on the body sheet its lock boundaries' line F (2.5 px) is 0.237 / 0.231 / 0.281 (front, profile,
  back) against random floors 0.160 / 0.151 / 0.077; it recovers 0 of the sheet's 11 hem flicks, 4 of 8 bang locks.
- **The generated lock-level close-up** (one call, n=2, prompt `hair_lock_closeup`, ledger): both takes copied the
  breakdown's blended colours; one scale within 4%, hair IoU 0.82-0.91, but line F 0.17-0.29 against floors
  0.07-0.16. Not adequate in any view; nothing registered.
- **The lock truth extended** (charkit/refs/clawd/hair_locks_truth.json/.npz; the bangs' 12 locks pixel-identical): 52
  locks: front 18 (bangs 5, side locks 4, lower back 2, flyaways 6, ahoge 1), three-quarter 10 (4, 4, -, 1, 1), profile
  10 (3, 2, 2, 2, 1), back 14 (lower back 7 flicks, flyaways 6, ahoge 1). The scorer (hairlocks) per family, the ahoge
  and flyaways as lock families. h5_base: all 0.331 (a random split 0.392); bangs 0.435 (random 0.398), side locks
  0.382 (0.429), lower back 0.316 (0.294), flyaways 0.211 (0.375), ahoge 0.379 (0.609); worst: the profile's side
  locks 0.232, the three-quarter's flyaways 0.000.
- **Calls for Michael** (from the sub-agent): F, the side flick tips scored as flyaways rather than mass locks? G, the
  outer side masses unscored (no lock-level reference)? H, the front's and back's side flicks and lowest outer flicks
  the same physical flicks? And one more paid call (the turnaround alone as reference, line art only), or stop?

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
| fit, width and depth from the drawn strands (6a, lab) | **0.689** | 19 PASS | 0 | 0.622 pooled |

The centreline fit is within 1.2 px of the drawn centreline in front, profile and back (mean) jointly: the views agree
on the ahoge's 3-d curve (a front-only fit reaches F 0.571 front against the joint 0.516: the joint fit isn't the
limit). The shape deficit was the width: the drawn ahoge is widest at its base and nearly round (profile width 0.8 of
the front's), the crescent template thin at the root and flat (depth 0.45).

### The lines are our ink (31e6654)

The hair flags' lines now read our ink as the render draws it (`hairflagqa.our_ink`): each hair object's surface
pulled in by its outline (the bundle's per-vertex shrink, which carries the outline's vertex-group widths) and its hull
on the original surface, flipped and back-face culled per view, z-buffered on the design grids among the QA's other
surfaces; the hull's pixels drawn at least a pixel wide. For rebuilt pieces (the lab) the shrink is made from the
angle-weighted normals, LINE_W 0.0014 m and the piece's `outline_w`. Recalibrated (eeafe0e): all 7 calibrated;
h5_base reads back_lines 3.77, lock lines 0.205 / 0.162 (3q / profile), known-bad 3.76 / 0.202 / 0.164.

### The stripes and the hem: settings measured in the lab (hairlab --batch on the build box)

- `ink_fade {piece: keep}` (31e6654): a piece's locks draw no line where they meet, down to the last `keep` of their
  length (the part's `outline_w`, the Blender stage's `outline_w` vertex group, read by the outline's SOLIDIFY;
  scene.hair_pieces_objects). As the design draws its back: one smooth mass, the locks parting at the hem.
- `lock_min_piece`, `notch_piece` (per-piece lock width and notch), `fine_tips` with lower_back (the drawn hem's tips).
- `flyaway_root 'hair'`: each flyaway's root carried to the nearest drawn hair (buns included) and 0.02 L into it, its
  depth from the buns' built surfaces too.

`python -m charkit remote run --fetch charkit/out/hair5/bN hairlab charkit/out/h5_base --batch tools/hair5/v/bN.json
charkit/out/hair5/bN` (variants files must be tracked: charkit/out isn't synced). Results: charkit/out/hair5/b1/lab.json
(b1 ran at 57a1c83: the ink measure before the thin ink, so its lines aren't comparable with b2's), b2/lab.json (at
31e6654). Per variant: NAME.npz (label images), NAME.pieces.npz (the rebuilt pieces).

Results (from the batch logs; b1's lines are the pre-thin ink, b2's the thin ink, so compare lines within a batch;
h5_base reads 3.77 back ink with the thin ink, 1.85 with b1's):

| variant | ahoge F | bend | attached L | back ink | hem (tips; drawn 8) | lines 3q | lines profile | upper | lower | side | bangs | buns | ahoge IoU | flyaways IoU | bun outline |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| b1 base | 0.371 | 108 | 0.029 | 1.85 | 5 (3) | 0.183 | 0.146 | 0.768 | 0.62 | 0.53 | 0.771 | 0.862 | 0.322 | 0.196 | 0.459 |
| b1 A ahoge fit + flyaway root | **0.516** | **6.6** | **0** | 1.79 | 5 (3) | 0.146 | 0.138 | 0.771 | 0.62 | 0.529 | 0.77 | 0.862 | **0.529** | **0.163** | 0.461 |
| b1 B A + upper back lock_min 40 | 0.516 | 6.6 | 0 | 0.88 | 5 | 0.148 | **0.081** | 0.77 | 0.62 | 0.529 | 0.77 | 0.863 | 0.529 | 0.163 | 0.461 |
| b1 C A + upper back one lock | 0.516 | 6.6 | 0 | 0.09 | 5 | 0.148 | **0.071** | 0.769 | 0.62 | 0.529 | 0.77 | 0.862 | 0.529 | 0.163 | 0.461 |
| b1 D A + hem (fine tips, notch 6) | 0.516 | 6.6 | 0 | 1.92 | **3 (5)** | 0.158 | 0.150 | 0.771 | 0.62 | 0.529 | 0.77 | 0.862 | 0.529 | 0.163 | 0.461 |
| b1 E A + hem notch 10 | 0.516 | 6.6 | 0 | 1.90 | 3 (5) | 0.157 | 0.150 | 0.771 | 0.621 | 0.529 | 0.77 | 0.862 | 0.529 | 0.163 | 0.461 |
| b1 F A + hem notch 8, lower lock_min 5 | 0.516 | 6.6 | 0 | 2.03 | 3 (5) | 0.156 | 0.143 | 0.771 | 0.62 | 0.529 | 0.77 | 0.862 | 0.529 | 0.163 | 0.461 |
| b2 G A + ink_fade upper 0 | 0.516 | 6.6 | 0 | 3.14 | 5 | 0.178 | 0.149 | 0.771 | 0.62 | 0.529 | 0.77 | 0.862 | 0.529 | 0.163 | 0.461 |
| b2 H A + ink_fade upper 0.3, lower 0.6 | 0.516 | 6.6 | 0 | 3.29 | 5 | 0.178 | 0.151 | 0.771 | 0.62 | 0.529 | 0.77 | 0.862 | 0.529 | 0.163 | 0.461 |
| b2 I H + hem notch 6 | 0.516 | 6.6 | 0 | 3.39 | 3 (5) | 0.189 | 0.159 | 0.771 | 0.62 | 0.529 | 0.77 | 0.862 | 0.529 | 0.163 | 0.461 |
| b2 J H + upper lock_min 40 | 0.516 | 6.6 | 0 | 1.52 | 5 | 0.182 | **0.091** | 0.77 | 0.62 | 0.529 | 0.77 | 0.863 | 0.529 | 0.163 | 0.461 |
| b2 K H + side locks 0.6 | 0.516 | 6.6 | 0 | 3.29 | 5 | 0.178 | 0.151 | 0.771 | 0.62 | 0.529 | 0.77 | 0.862 | 0.529 | 0.163 | 0.461 |

Readings:
- **The ahoge fit and the flyaway root fix flags 1 and 2's checks**: bend 108 -> 6.6 PASS, attached 0.029 -> 0 PASS,
  ahoge F 0.37 -> 0.52 (still under the 0.55 WARN line: the fit is thinner and less curled than the drawn crescent in
  front and back; lab3.json's single-view fits say whether the views disagree), hair_piece_ahoge 0.32 -> 0.53.
- **But the anti-gaming guard would block A as it is: hair_piece_flyaways 0.196 -> 0.163 (-17%)** while hair_attached
  improves. The root's carry (flyaway_reach 0.02 L into the drawn hair, at the bun's depth) shows in front of the bun
  or mass in some view. Next: read the flyaways' per-view IoU (A's views) and the label image (b1/A_fit_fly.npz,
  tools/hair5/pic.py), then a shorter reach (0.005-0.01 L) or the carry placed behind the surface it joins (its depth
  past the bun's / mass's front), until the IoU holds within 15% in every view.
- **ink_fade barely moves the back's ink** (thin ink 3.77 -> 3.14-3.29): the seams' outline weights reach only the side
  columns (k = 0, 1), so the hull two columns in, the relief's grooves or the lock tops' edges still draw. Look at
  b2/H_ink.npz's ink (the measure's picture: render hairflagqa.picture with our_ink for the rebuilt pieces) before
  widening it; also check the lower back's horizontal top edge (the dark band's line).
- **Fewer upper-back locks clear the back's ink but cost the profile's lines** (0.146 -> 0.071-0.091): the profile
  draws lines the back doesn't. The view-dependent answer is the outline width (ink_fade), not fewer locks.
- **The hem**: fine tips + notch on the lower back give 5 tips (drawn 8): hair_back_hem FAIL -> WARN (3), the back's
  ink slightly up; notch 6 = 10. More tips need the lower back's lock count from the drawn hem (8 flicks: the
  extended lock truth's lower-back flicks, or drawn_notches on the back view).

### Coordinator's item for the layering (2026-09-30)

The side locks' partition is unstable under a face edit: tool/face5's jaw moves the hull labels near the cheek (front
6527 -> 6539), so side_lock_L's tips go 38/58/74 -> 34/58/82 deg, side_lock_R's -74/-66 -> -78/-62, the skin-clearance
trim 91 -> 88 cells, and art_terminator_hair 1.804 -> 2.111 (input swaps: ~/animation-pipeline-face/charkit/out/f5swap/
swap.json, read only). When the side locks are templated, their partition and tips come from the drawing or the lock
truth, not the hull labels; and a stability check: a face-only edit (the face5 swap) leaves the side locks put
(their lock bounds and tips within a tolerance). face5 will likely land first with that terminator WARN accepted.

## State at the checkpoint (context limit; relaunch lean from here)

Branch `tool/hair5` (from pipeline-3d 004efc3), never pushed, not gated. Every new builder path is behind a setting:
the default build is unchanged (`ahoge` '2d', `flyaway_root` 'mass', no `ink_fade`, no per-piece overrides), so a gate
now would land the 7 new flag checks (all FAIL on 004efc3: new FAILs block under K unless accepted) — land them with the
fix, not alone, or have the coordinator accept them by name as the measurement-only gate.

Local builds: `charkit/out/h5_base` (box, 004efc3 default spec; qa.json has the hair flags added by
tools/hair5/addqa.py), known-bad `hair5_1580f95` stored (charkit/out/calib/builds). Tools: tools/hair5/ (ctx, pic,
flags, ahogepic, ahogemask, linepic, lab, table, review, addqa, v/*.json).

**Running at the checkpoint (mine):**
- sub-agent (step 2, truth granularity), writing `docs/workstreams/hair5-truth.md`, `tools/hair5truth/`,
  `charkit/out/hair5truth/`, `charkit/refs/clawd/hair_locks_truth.json/.npz`, `charkit/refs/clawd/gen/prompts.json`
  (`hair_lock_closeup`), maybe `charkit/refs/clawd/gen/hair_lock_closeup.png`, `charkit/hairlocks.py` (a small scorer
  extension), `tools/ledger.jsonl` (its paid call). It was told not to run git: commit its files after reading its notes
  (`git status`: those paths only).
- a laptop lab, the ahoge fitted to single views (front / profile / back / front+back / front+profile) ->
  `charkit/out/hair5/lab3.json` (the standing rule's step 1: is the joint fit limited by the drawings disagreeing?).
- box batches b1 (charkit/out/hair5/b1/lab.json) and b2 (b2/lab.json): see the table above when filled.

**Next, in order:**
1. Read b1/b2 (`python tools/hair5/table.py charkit/out/hair5/b1/lab.json charkit/out/hair5/b2/lab.json`), then run b3
   (`tools/hair5/v/b3.json`: base, the fix candidates with the thin-ink measure) on the box the same way. Pick the
   defaults: ahoge 'fit' + flyaway_root 'hair' (b1: ahoge F 0.37 -> 0.52, bend 108 -> 6.6 PASS, attached 0.029 -> 0
   PASS), ink_fade for the back (choose keep by back_lines vs the lock lines in 3q/profile: removing seam ink must
   not drop lines the drawing has there), the hem (fine_tips lower_back + notch_piece) by hair_back_hem and the
   lower back's IoU. Guard: every hair_piece_* per view within 15% (anti-gaming), hair_noise, folds.
2. Set the chosen settings in `hairpieces.OPTS` (with the measured numbers in the comment block above OPTS), then a
   render-box build with the previews' boards: `python -m charkit remote --box render build charkit/spec/clawd.json
   --out charkit/out/h5_fix --boards views,body,design --no-blend` (art_terminator_hair < 2.5, art_peeks_hair,
   hair_noise, folds from its qa.json; the base's: 1.804 PASS, 18, 0.0716, 4).
3. Step 2's results into these notes; the review page: `python tools/hair5/review.py charkit/out/hair5/review
   charkit/out/h5_fix --summary SUMMARY.json` (summary box: Recommended / Asked of Michael / Key numbers).
4. `python -m charkit pregate`, then `python -m charkit remote gate tool/hair5 --into pipeline-3d` (merge pipeline-3d
   first if it moved). The flag checks are new: they need their calibration records (done: charkit/calib/records/
   hair_*.json; rerun `python -m charkit calibrate 'hair_ahoge_*,hair_attached,hair_back_*,hair_lock_lines_*' --build
   charkit/out/h5_base` if the measuring code changes, and move the steps' commit in charkit/steps/hairflagqa.py).
5. Then the layering (step 3's second half): side locks and lower-back flicks as templates from the drawing / the
   extended lock truth (not the hull labels: the coordinator's stability item below), the ribbons pilot's lock model,
   the envelope-depth test queued from hairlocks round 3.

## Jobs

See "Running at the checkpoint".
