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

### Batches 3-6 (the thin-ink measure; base h5_base: back ink 3.77, lines 3q / profile 0.205 / 0.162, folds 4)

| variant (all: ahoge fit, flyaway root) | ahoge F | attached | back ink | hem (diff) | lines 3q | lines profile | upper (prof / back) | lower (front / prof / back) | flyaways (front / back) | side | folds |
|---|---|---|---|---|---|---|---|---|---|---|---|
| base | 0.371 | 0.029 | 3.77 | 5 | 0.205 | 0.162 | 0.618 / 0.888 | 0.502 / 0.664 / 0.673 | 0.222 / 0.131 | 0.53 | 4 |
| A2 (b3: taper fixed, crescent width) | 0.516 | 0 | 3.68 | 5 | 0.178 | 0.151 | | | 0.197 pooled (r 0.01: 0.208) | 0.529 | |
| H3_hem6 (ink upper 0, lower 0.25; hem notch 6) | 0.516 | 0 | 0.74 | 3 | 0.190 | 0.096 | | | | 0.529 | |
| P3 (drawn width; ink 0.15 / 0.35; hem: drawn cuts, fine tips, notch 6) | 0.689 | 0 | 1.52 | **2 PASS** | 0.195 | 0.112 | 0.621 / 0.890 | 0.502 / 0.666 / 0.670 | 0.221 / 0.170 | 0.531 | 6 |
| P5 (P3 + ink_phi 135) | 0.689 | 0 | 2.02 | 2 | 0.193 | **0.158** | same | same | same | 0.531 | 6 |
| **P6 (ink upper 0, lower 0.25, ink_phi 120; hem as P3): the default** | **0.689** | **0** | **0.55** | **2** | 0.195 | 0.088 | 0.621 / 0.890 | 0.502 / 0.666 / 0.670 | 0.221 / 0.170 | 0.531 | 6 |
| F4 (P3's hem + the upper back cut at its drawn notches too) | 0.689 | 0 | 2.35 | 2 | 0.190 | 0.147 | / (pooled 0.776) | (pooled 0.628) | | 0.529 | |
| R1 (ribbons for the side locks) | 0.689 | 0 | 1.53 | 2 | 0.201 | 0.113 | | | | 0.535 | **38** |
| R2 (ribbons for the side locks and upper back) | 0.688 | 0 | 2.89 | 2 | 0.203 | 0.153 | | lower 0.604 | | 0.534 | **40** |
| R3 (the side locks cut at their drawn notches, fine tips) | 0.689 | 0 | 1.45 | 2 | 0.185 | 0.148 | | front 0.463 | | 0.522 | 11 |

(ink_phi 120 and 105 equal no cut-off: the upper back's side columns all lie beyond 120 deg; at 135 the side seams keep
their line.) The single-view ahoge lab (lab3) was stopped at its time limit after the front-only fit (front F 0.571
against the joint 0.516): the joint fit isn't the limit (centrelines within 1.2 px in all three views), the width was.

**Defaults chosen (hairpieces.OPTS, uncommitted build not yet made):** ahoge 'fit'; flyaway_root 'hair' with
flyaway_reach 0.01; the hem: fine_tips ('bangs', 'lower_back'), notch_piece {'lower_back': 6}, drawn_cuts
('lower_back',); the seam ink: ink_fade {'upper_back': 0.0, 'lower_back': 0.25}, ink_phi 120 (P6). Side locks:
unchanged (wedge): ribbons fold (38-40), the drawn cuts gain little and fold 11, and the stability item stays open.
Guard (anti-gaming): every family's IoU per view within 0.01 of the base, the flyaways' up; the flag checks moved:
ahoge F 0.371 -> 0.689 (WARN), bend 108 -> 19 PASS, attached 0.029 -> 0 PASS, back ink 3.77 -> 0.55 (WARN), hem 5 ->
2 PASS; **profile lines 0.162 -> 0.088 and three-quarter 0.205 -> 0.195 (both FAIL before and after: value moves)**.

**For Michael (the seam ink's trade-off):** A, P6 (the default): the back reads as one smooth mass (ink 0.55 against
the drawing's, WARN), but the profile loses lines (0.162 -> 0.088; ours sat at precision 0.17: mostly not where the
drawing's are). B, P5: the profile keeps its lines (0.158) and the back keeps half its stripes (2.02, FAIL). The
layering round (drawn lock lines in profile and three-quarter) is the real fix for the profile either way.

## Round 2 (relaunched lean, 2026-09-30 night)

Merged pipeline-3d 3f7b730 (softras round 4; no hair code) -> fcc73c5. Coordinator's decisions: one more paid reference
attempt then stop; the back seams' default stays A (P6), B (P5: keep 0.15 / 0.35, ink_phi 135) rendered beside it for
Michael (spec `tools/hair5/v/clawd_seamsB.json`: the default spec with those pieces_opts); calls F / G / H on the
review page as yes/no questions with the recommended defaults meanwhile.

### The last reference attempt: a lock-level line-art sheet (one call, n=2)

Unlike the close-up (colour-coded, the breakdown as a reference: both takes copied its blended fills), this asks for
line art: one flat orange fill, every lock outlined in closed black lines, the turnaround the only `--ref`. The refcheck
(tools/hair5truth/refcheck.py, regions split by its black lines) and score5 read it as before.

**Pass rule, fixed before the call** (a view passes when all hold; the sheet is registered, for its passing views only,
when at least one view passes and its scale holds):
- silhouette: hair IoU >= 0.80 on the design grid (the breakdown's level);
- lock lines: line F within 2.5 px >= 0.40 and >= 2x its random-partition floor (the breakdown and the close-up
  reached 0.17-0.29);
- locks: score5's lock IoU against the extended truth >= the random within-family split in that view (front 0.522,
  three-quarter 0.552, profile 0.661, back 0.495), and no family below the plain random split;
- one scale: the four views' S within 5%.
If no view passes: stop generating, and the canonical rule's step 3 (compromise) holds for the bulk's lock structure.

**Outcome: fails in every view; generation stopped.** The call (ledger 2026-09-30T21:04:49, gpt-image-2.5-sunburst,
2560x1440, high, n=2, `--ref` body_turnaround only; prompt `charkit/refs/clawd/gen/prompts.json` `hair_lock_lineart`,
also `charkit/out/hair5truth/prompt_lineart.txt`; the `.env` symlink made and removed in the same command) gave two
clean line-art sheets: `charkit/out/hair5truth/gen/hair_lock_lineart_{1,2}.png`. Refcheck
(`charkit/out/hair5truth/refcheck/lineart{1,2}.json`, pictures alongside) and score5
(`charkit/out/hair5truth/scores/scores_lineart.{json,log}`):

| take | view | S px/L | hair IoU | line F 2.5 px (P / R) / floor | lock IoU / within-family floor | pass |
|---|---|---|---|---|---|---|
| 1 | front | 386 | 0.857 | 0.310 (0.72 / 0.20) / 0.105 | 0.241 / 0.522 | no |
| 1 | three-quarter | 387 | 0.871 | 0.229 (0.53 / 0.15) / 0.096 | 0.292 / 0.552 | no |
| 1 | profile | 380 | 0.917 | 0.106 (0.26 / 0.07) / 0.098 | 0.177 / 0.661 | no |
| 1 | back | 383 | 0.914 | 0.086 (0.21 / 0.05) / 0.059 | 0.072 / 0.495 | no |
| 2 | front | 393 | 0.882 | 0.306 (0.65 / 0.20) / 0.106 | 0.241 / 0.522 | no |
| 2 | three-quarter | 390 | 0.905 | 0.254 (0.66 / 0.16) / 0.098 | 0.254 / 0.552 | no |
| 2 | profile | 388 | 0.923 | 0.170 (0.38 / 0.11) / 0.097 | 0.242 / 0.661 | no |
| 2 | back | 388 | 0.932 | 0.150 (0.45 / 0.09) / 0.063 | 0.114 / 0.495 | no |

The silhouette (0.86-0.93, the best of any sheet) and the scale (within 3.4%) pass; the locks don't. The takes draw the
turnaround's lock strokes as open strokes, as the turnaround itself does (the hem's notches, the side masses'
partial lines): few closed regions (10-22 per view), so the line F's recall is 0.05-0.20 and the locks score below the
random split (all 0.19 / 0.21 against 0.39; bangs 0.06, lower back 0.01). They hold no lock structure the turnaround
lacks. Nothing registered; no more calls. **Under the canonical rule, step 3 (compromise) holds for the bulk's lock
structure**: the base model takes the best fit across views with per-view costs; the outer masses stay unscored
(call G); the lock-lines checks are judged against their intent (the drawn lines) rather than a closed-lock truth.
Pictures with the truth: `charkit/out/hair5/truthpics/VIEW.png` (sheet | lock truth | take 1 | take 2).

### The render-box builds of the defaults (A) and of option B

`charkit/out/hair5_b` (A, the default spec at 5e1f388) and `charkit/out/hair5_bB` (B, tools/hair5/v/clawd_seamsB.json);
both `--boards views,body,design --no-blend`. The hair flags read exactly the lab's P6 / P5: ahoge F 0.371 -> 0.689
(WARN), bend 108 -> 19 PASS, attached 0.029 -> 0 PASS, back ink 3.77 -> 0.558 (A, WARN) / 2.027 (B, FAIL), hem 5 -> 2
PASS, lines 3q 0.205 -> 0.195 / 0.193, profile 0.162 -> 0.088 / 0.158. Guard: every hair_piece_* within 0.004 per view
of the base, the flyaways' back 0.131 -> 0.170, the ahoge 0.29-0.35 -> 0.55-0.75; body_*_iou_hair all up 0.002-0.004.

**But art_terminator_hair 1.804 PASS -> 2.575 WARN (grade FAIL) in A, 2.59 in B**: a flag check whose grade worsens
blocks under K. The worst view moved to the back (2.42 -> 3.49 kinks per L). `tools/hair5/term.py` (the artifact
part's own measure on a bundle with hair objects dropped or swapped from another build's; reproduces 2.575 exactly,
8 s) found it: the fitted ahoge. A without its ahoge 1.900; A with the base's ahoge 1.899; the base with A's ahoge
3.262; the base with A's upper and lower back 1.878 (the seams without ink don't add terminator: the back 1.788 ->
1.54). The ahoge, now as wide as the drawn one, shades with the envelope's normals, which turn along a strand
standing out of the mass: a staircase shadow patch on its lower half from behind (the flyaways' problem in hairtag
round 3, fixed there by strand_tone 'root'). **Fix: strand_tone 'root' covers the ahoge too**
(hairpieces.STRAND_TONE_FAMILIES = flyaways, ahoge; the style may set strand_tone_families): one tone, its root's. On
a bundle copy with the ahoge's normals set to its root's (charkit/out/hair5/tA): back 3.489 -> 0.964 ratio, worst
1.900 (front: the lower back's new hem, 1.804 -> 1.878 alone), PASS. The drawn front ahoge has a shaded lower half;
one tone loses it (the flyaways' trade-off). Test: test_strand_tone_root_shades_the_ahoge_in_one_tone.

Rebuilt both with the fix: `charkit/out/hair5_b2` (A), `charkit/out/hair5_bB2` (B).

**The rebuilds** (hair5_b2 A, hair5_bB2 B, at 2c520e5): art_terminator_hair 1.900 PASS (A; back 0.964), 1.918 PASS
(B); every hair flag and piece IoU as hair5_b. Against pipeline-3d's preview 3f7b730 (render box) the only other flag
check whose grade worsens: **art_speckle_neck 0.833 PASS -> 1.68 WARN** (profile 41.6 -> 83.9 specks per L^2: one
more, a few-pixel island of neck skin between the hem and the collar). Also reported, not blocking: art_peeks_hair 18
-> 17, collar_back_square 0.345 -> 0.325 (FAIL both: the hem over the collar), collar_back_iou 0.7461 -> 0.7454.

**Attribution** (term.py --check speckle_neck): A with the base's lower back 0.833; every other piece swapped: 1.68.
`tools/hair5/labart.py` (the artifact checks for a lab variant: the build's bundle with the lab's pieces; the shrink
from the angle-weighted normals; P6's pieces on hair5_b reproduce it, 2.576 / 1.68 against 2.575 / 1.68): b1's lower
backs: fine tips + notch 6 without the drawn cuts 0.837, with them (P3) 1.68.

Batch b8 (lower back only; flags from b8/lab.json, artifacts b8/labart.json on hair5_b2; every piece IoU as P6 but
cuts_nofine's lower 0.609):

| variant | hem (tips off) | back ink | lines 3q / prof | art_terminator_hair | art_speckle_neck | peeks | fragments |
|---|---|---|---|---|---|---|---|
| P6 (cuts, notch 6: the default) | 2 PASS | 0.554 | 0.195 / 0.088 | 1.906 | **1.68 WARN** | 17 | 1.48 |
| no drawn cuts | 3 | 0.895 | 0.196 / 0.086 | 2.124 WARN | 1.355 | 18 | 1.557 WARN |
| cuts, notch 3 | 3 | 0.570 | 0.193 / 0.088 | **1.752** | **0.836** | 17 | 1.482 |
| cuts, notch 0 (style's) | 3 | 0.566 | 0.194 / 0.088 | 1.822 | 0.836 | 17 | 1.486 |
| cuts, no fine tips | 4 | 0.525 | 0.188 / 0.082 | 1.674 | 1.355 | 16 | 1.422 |
| cuts, notch 10 | 2 | 0.543 | 0.195 / 0.088 | 1.907 | 1.679 WARN | 17 | 1.482 |

b9 (notch 4, 5) running: the deepest notch that keeps the neck clean.

b9: notch 4: neck 0.836, hem 3, art_fragments_hair 1.515 WARN; notch 5: hem 2, neck 1.68 WARN. **Default now notch 3**
(cuts kept): art_speckle_neck back to 0.836, art_terminator_hair 1.752, hem 2 -> 3 (5 tips against the drawn 8: one
tip fewer than notch 6; hair_back_hem is new, WARN doesn't block). Render builds `charkit/out/hair5_b3` (A),
`charkit/out/hair5_bB3` (B), and the gate, launched together.

Pregate at 86ed60d: PASS (13 moved, 0 blocking). pipeline-3d moved to 342e88c (face5: the jaw); merged -> 5718c65.
**Gate running** (`python -m charkit remote gate tool/hair5 --into pipeline-3d`, log charkit/out/hair5/gate.log).
The render builds hair5_b3 / hair5_bB3 were synced at 86ed60d (hair5 on 3f7b730, before face5): the review page's
pictures and numbers are hair5's own.

**Final render builds** (at 86ed60d, hair5 on 3f7b730): `charkit/out/hair5_b3` (A), `charkit/out/hair5_bB3` (B).
Against pipeline-3d's preview 3f7b730: no flag check's grade worsens. art_terminator_hair 1.804 -> 1.762 (A) / 1.771
(B), art_speckle_neck 0.833 -> 0.836, art_peeks_hair 18 -> 17, art_fragments_hair 1.414 -> 1.482 (PASS),
collar_back_square 0.345 -> 0.325 and collar_back_iou 0.7461 -> 0.7454 (FAIL both: the hem over the collar), hair_folds
4 -> 5. Flags: ahoge F 0.689 WARN, bend 19.2 PASS, attached 0 PASS, back ink 0.573 WARN (B 2.042 FAIL), hem 3 WARN,
lines 3q 0.193 / profile 0.088 (B 0.192 / 0.158), FAIL both (new). Guard: every hair_piece_* within 0.004 per view,
the ahoge 0.32 -> 0.62, the flyaways 0.196 -> 0.208.

**Review page:** `charkit/out/hair5/review_r2/index.html` (summary box: A recommended; asked: seams A/B, the ahoge in one
tone yes/no, F, G, H; key numbers; the guard per view; per flag design | start | before | after (| B); the ahoge's
shading before/after; the seams A against B; F/G/H with the truth's regions; the reference attempt). Made by
`python tools/hair5/review.py charkit/out/hair5/review_r2 charkit/out/hair5_b3 --b charkit/out/hair5_bB3 --summary
charkit/out/hair5/review_r2/summary.json --ref charkit/out/hair5/review_r2/ref.json`.

## State (2026-09-30 late night)

Branch `tool/hair5` at 5718c65 + notes (pipeline-3d 342e88c merged), never pushed. Gate launched at 5718c65.

**Scope change (coordinator, 2026-09-30):** the hair bulk moves to per-lock shells (tool/hairsplit builds the lock
splitter). No more hull-shell fixes and **no layering round on the hull approach**. The layering, the profile's and
three-quarter's lock lines (hair_lock_lines_*), the side locks' stability under a face edit, and the outer masses' locks
belong to tool/hairsplit, graded against the lock truth (charkit/refs/clawd/hair_locks_truth, with calls F/G/H as
Michael answers them on the review page). The checks of this round (charkit/hairflagqa.py), the ahoge fit, the flyaway
attachment and the seam cut-off carry over.

**Next steps:**
1. Read the gate report. If it blocks on art_speckle_neck or anything else from the hem's drawn cuts, set drawn_cuts
   off (hairpieces.OPTS `drawn_cuts=()`), keep everything else, re-gate once, and report. Don't iterate further.
2. Michael's answers (review page): the seams A/B (B is `ink_fade {'upper_back': 0.15, 'lower_back': 0.35}`,
   `ink_phi 135`), the ahoge's one tone (no: `strand_tone_families: ['flyaways']` in the style), F/G/H (the lock
   truth's source, for tool/hairsplit).
3. The side-lock stability check (`tools/hair5/stability.py BUILD_A BUILD_B`) is for tool/hairsplit's splitter on a
   face-only edit pair.

## Jobs

None running.
