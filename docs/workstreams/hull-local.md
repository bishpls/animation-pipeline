# tool/hull-local: the hull's decimation made local

Branch `tool/hull-local` from pipeline-3d 3a0ad37 (worktree `~/animation-pipeline-hulllocal`). Started from face
round 5's collar trace (docs/workstreams/face.md, round 5): a jaw change moved the collar 0.035 L through the body fit,
which reads hull.ply, whose fixed-budget decimation had moved vertices far from the face.

## The measure (`tools/hull_local/locality.py`)

The hull built twice with one hull code, only the authored head's sections differing (`dump_sections.py` from two
trees: pipeline-3d 3a0ad37 and tool/face5 36908d0), every stage kept and compared: the carved voxels, the surface before
decimation (exact positions), hull.ply (vertices not bit-identical, and each vertex's distance to the other mesh's
surface) by distance from the changed voxels and by part of the figure, and the per-vertex labels. The lab's build of
the base reproduces the produced hull byte for byte (hull.ply and hull_pieces.npy, sha1 equal).

**Before (a fixed 150,000 faces):**
- voxels: 754 changed, all in the face's box (x -0.35..0.35, y -0.355..0.155, z -0.366..0.204 L); `rounded` identical;
- surface (marching cubes, blur 1): local. 5,912 / 5,862 vertices differ, the farthest 0.070 L from a changed voxel;
- hull.ply: 1,723 vertices differ; **401 of them farther than 0.06 L from the edit** (202 over 1e-6 L, up to 0.0008
  L), in 25 separate 2-vertex patches spread over the whole figure: the head's sides and back 314, crown 39, neck 3,
  torso 24, legs 21. These are the budget's last collapses. The face changes the face's triangle count, so the budget
  runs out at a different edge, anywhere on the figure.
- labels: 0 of the 73,280 shared vertices change class or piece.

**The change:** `hull.decimate_hull` decimates to a quadric error, `DECIMATE_COST` 1.2e-10 L^4 (the last collapse's
cost at 150,000 faces on the default spec, 1.204e-10: the same density), through `remesh.decimate(max_cost=)`. A face
count remains for labs (`--faces N`, `build(faces=N)`); the head-sheet hull (`--head`) keeps 150,000. With a count,
remesh.decimate is unchanged: it reproduces today's hull.ply exactly.

**After (the error bound; the same two surfaces):**
- hull.ply: 150,196 / 150,150 faces; 1,699 / 1,676 vertices differ;
- **the neck, torso and legs: bit-identical** (0 of 106,350 vertices; before 48 moved), and the back of the head (y >
  0.10 L) and the crown (1 vertex at 1.2e-6 L) too;
- what differs is three connected patches, all touching the edit: the face and, through the carve-filled gap between
  the cheek and the side locks, the head's sides to x +-0.69 L (1,609 vertices, the farthest 0.43 L from a changed
  voxel, 48 beyond 0.1 L), and two at the forehead within 0.08 L. That spread is the greedy collapse's own reach.
  Each vertex's quadric carries what it absorbed, so a changed collapse changes its neighbours' order. It stays on the
  surface the edit touches.
- decimation 6 s instead of 12 s (the heap stops at the bound).

**The body fit on the two hulls** (`tools/hull_local/bodyfit.py`: bodypage.save_body, code_body's rings, the spec held,
only the hull differing):

| body array (max change, L) | fixed 150,000 faces | quadric-error bound |
|---|---|---|
| torso rings (torso_P), rows moved | 0.0011, 56 of 56 | 0, 0 of 56 |
| torso centre (torso_cy) | 0.00065 | 0 |
| feet (right / left) | 0.00107 / 0.00032 | 0 / 0 |
| legs (left / right) | 0.00013 / 5.3e-6 | 0 / 0 |
| arms, joints, sole, eyes | 0 | 0 |

Under the budget a face edit moved every torso row, as round 5's trace found (1.6e-4 to 1.4e-3 L per row; the
collar amplified it to 0.035 L). Under the bound the body is bit-identical: the collar's chain is cut at the body.
The hull's per-vertex labels: 0 of 73,402 shared vertices change class or piece.

Test: `charkit/tests/geom/test_hull_local.py` (an ellipsoid with a dent: under the bound nothing moves beyond the dent's
own reach, 0.26 against the surface's 0.24; a budget of the same density moves 59 vertices beyond 0.42, up to 2.27).
A capsule's exact cylinder chains zero-cost collapses from end to end, so the test uses an ellipsoid. The hull has no
such walls: its torso and legs were bit-identical.

Contract (docs/HULL_CONTRACT.md): not breaking. The files, keys and order rules are unchanged; the face count varies
a little. Every mesh reader sees a new mesh once (the stamp changes): code_body, the hair's envelope and flyaways,
bundle.target_pieces.

## Jobs
- box builds (build box, `--boards '' --no-blend`, as a gate builds): B2 = pipeline-3d 3a0ad37 + hull-local
  (`charkit/out/hl_b2`, CPU 908.7 s cold) and B3 = tool/face5 2e4c1d6 + hull-local (`tmp/face5-on-hull-local` f6137bd,
  worktree `~/animation-pipeline-face5hl`, `charkit/out/hl_b3`).

## What face5 does on a local hull (B2 -> B3)

- body_code.npz identical (every array). The collar's checks are identical: sleeve_profile_rough_L 0.0 PASS both,
  collar_back_iou 0.7461, art_fragments_collar 6.515, art_outline_collar 1.379. The chain is cut.
- art_terminator_hair 2.514 -> 2.964 (worst view: the back, ratio 2.514 -> 2.964). Piece swaps (`tools/hairtag/termlab.py`
  on the box, `charkit/out/hl_term/term_b2_b3.json`): **hair_bun_L carries it**. B2 with B3's bun_L reads 2.903 (back),
  and B3 with B2's bun_L reads 2.61 (back 2.56). hair_bun_R adds about 0.05 (2.563 / 2.894). The side locks, bangs,
  upper and lower back, ahoge and flyaways move the back view by 0.01 at most. The buns move 0.020 / 0.011 L (1,923 /
  1,766 vertices over 1e-3 L) though the hull is identical there. So the carrier isn't the hull: it's an input of the
  bun fit that the face changes (`tools/hull_local/hairswap.py`, below).
- hull-local alone (B2) reads art_terminator_hair 2.514 against pipeline-3d's 2.308: the new mesh everywhere moves the
  flag check past its 2.5 line by itself. Its own gate would block on it.
- **What moves the buns** (`tools/hull_local/hairswap.py`, the hair pieces rebuilt on B3's inputs with one input from
  B2): the head, not the hull. With B2's head, bun_L matches B2's to 7.6e-6 L; with B2's hull, it matches B3's
  exactly. The bun points are identical. The head's centre (Case.centre, the bun fit's head_c) moves 0.8 um in y. The
  fit (hairpieces.fit_block, Nelder-Mead on a pixel loss) lands 0.027 L away. The hull is local; the bun fit isn't
  stable. B2's own 2.514 most likely comes the same way (its bun points all move once with the new mesh).

## Status

Not gated: B2 reads art_terminator_hair 2.514 (pipeline-3d ba51e43: 2.308), past the flag's 2.5 line, through the
buns' fit. Under K it would block. Next (docs/workstreams/face.md, round 5's finish): make the bun fit stable under
tiny input moves, then rebuild B2/B3 and gate this branch into pipeline-3d, and tool/face5 into it.

## Round 2 (2026-09-30, evening): the buns' fit made stable

Brief: make the bun fit stable (a 1 um move of its inputs moves the bun under 1e-4 L), holding the bun checks
(hair_piece_buns, hair_bun_outline, bun IoUs in every view, art_terminator_hair under 2.5); a unit test; then gate this
branch. The coordinator's swap on face5's gate pair (`charkit/out/hl_term/term_b0_b1.json`): either bun alone carries
most of 2.308 -> 2.751 (bun_L 2.569 / 2.503, bun_R 2.502 / 2.57), every other piece 0.03 at most: both buns.
Merged pipeline-3d 8b5ecae (softras round 3) at 32e4684. The code sits in hairpieces.fit_block and a new
`_fit_block_soft` beside it (plus one keyword in build's fit_block call); tool/hairlocks edits the locks and OPTS, not
these.

**The measure** (`tools/hull_local/bunstab.py`): `capture` rebuilds B2's hair pieces venv-side (hairswap.py's run) and
records both fit_block calls' arguments (`charkit/out/bunstab/b2_inputs.pkl`); `stab` refits each bun on them and with
the head's centre moved 1 um (+-x, +-y, +-z) or every bun point moved 1 um (3 random seeds, and all along +y): the
bun mesh's largest vertex move, in L (1 um = 4e-6 L).
- Rebuilding B2 on the laptop from B2's own inputs: bun_L within 7.6e-6 L of the box's, **bun_R 0.028 L away**: the
  platform's float noise alone moves it.
- **Nelder-Mead (the fit until now): bun_L up to 0.064 L (median 0.040), bun_R up to 0.19 L (median 0.029)**;
  16,000-47,000x the input move. IoUs across the perturbed fits: front 0.857-0.870, profile 0.920-0.938, back 0.891-0.903.
- The same loss on soft silhouettes (softras, L-BFGS-B, softness 4 -> 2 -> 1 px), no prior: worse, bun_L up to 0.23 L
  (median 0.11), bun_R up to 0.20. Even the first (softest, 9-parameter) stage ends at different losses (0.46 / 0.38 /
  0.44) from starts 1 um apart; the endpoints differ by 300-1,100 px of silhouette per view and up to 25 degrees of
  rotation, at soft losses within 0.01 of each other. **The silhouettes leave the pose under-determined**: many poses
  fit about equally, and a local optimiser's path picks one. A smooth loss alone can't fix that; the fit needs a rule
  that picks one of them continuously: the pose nearest the start (block_frame's, from the hull's bun points: a median
  and percentiles, continuous in them).
- With the prior toward the start (BUN_SOFT_PRIOR x the squared distance in the fit's units), still on softras: lambda
  0.001 / 0.01 / 0.03: bun_L up to 0.0029 / 0.0060 / 0.0031 L, bun_R 0.0136 / 0.101 / 0.0040 L; larger lambda costs
  IoU (0.03: profile 0.85). **softras's loss steps**: at the endpoint, central differences scale as 1/h in every
  direction: the objective jumps by 3.5e-5 there (its contour's edge set changes as the mesh moves: an edge kept or
  dropped moves the band pixels' distance), and L-BFGS converges onto that step and stops (a fresh restart doesn't
  move; along base -> perturbed endpoint the objective falls monotonically: one basin, stopped early). Not a softras
  bug for its own use (it's C0 up to those steps), but a smooth optimum needs a smooth loss.
- A convex-hull signed distance (each part the convex hull of its projected points, as the hard loss's `_hull_fill`):
  continuous, exact gradient (2e-10 against differences), but kinked where the nearest edge switches (every hull
  corner's bisector) and where a point joins the hull; along the weakly determined directions (curvature 2 lambda) the
  kinks leave ~1e-4 L of play (synthetic scene: 2.7e-4 L).
- **`_support_cover` (the design kept)**: each part the soft intersection of its supporting half-planes in 64 fixed
  directions, coverage prod_k k(4 (h_k - n_k . p) / s), h the support function smoothed by a log-sum-exp over the
  points (0.1 px); the parts' union 1 - prod(1 - c_i). Smooth everywhere (no edge or hull-membership switches), exact
  gradient (3e-10), numba kernels; L-BFGS converges in about half the evaluations (337 against 650). A pixel stride of
  s / 2 at the coarse softnesses.

**The prior's strength** (support-function coverage, B2's inputs, 4 perturbations each; IoU front / profile / back):

| BUN_SOFT_PRIOR | bun_L largest move (L) | bun_L IoU | bun_R largest move | bun_R IoU | s per fit L / R |
|---|---|---|---|---|---|
| Nelder-Mead (before) | 0.064 | 0.866 / 0.925 / 0.898 | 0.19 | 0.832 / 0.855 / 0.869 | 20 / 20 |
| 0.001 | 2.0e-7 | 0.869 / 0.901 / 0.920 | 5.8e-8 | 0.839 / 0.908 / 0.868 | 41 / 25 |
| **0.003 (kept)** | 1.3e-7 | 0.874 / 0.900 / 0.916 | 1.6e-7 | 0.839 / 0.907 / 0.867 | 26 / 16 |
| 0.01 | 1.2e-6 | 0.855 / 0.885 / 0.889 | 5.7e-7 | 0.832 / 0.872 / 0.859 | 23 / 15 |
| 0.03 | 9.3e-7 | 0.863 / 0.833 / 0.904 | 5.9e-7 | 0.818 / 0.857 / 0.831 | 15 / 11 |

(The Nelder-Mead IoUs are its unperturbed fit's; across its perturbed refits they spread +-0.01-0.02.) Every lambda is
stable once the loss is smooth; 0.003 fits best (only bun_L's profile under Nelder-Mead's, 0.900 against 0.925).
The unit test (`charkit/tests/test_bun_fit.py`): a drawn ribbon bun whose views no one pose reproduces (each drawn
from its own pose, rounder than our boxes), the hull's points a noisy inflated sampling; Nelder-Mead moves 0.0078 L
under the points' 1 um move (fails), the soft fit under 1e-6 L.

Jobs (2026-09-30 evening): box builds `--boards '' --no-blend` of f3682b7 (this branch: pipeline-3d 8b5ecae + the local
hull + the stable fit) -> `charkit/out/hl_b2s`, and of tmp/face5-on-hull-local 317a41c (face5 2e4c1d6 + this branch)
-> `~/animation-pipeline-face5hl/charkit/out/hl_b3s`. Laptop logs in `charkit/out/bunstab/build_b2s.log`, `build_b3s.log`.

**The box builds** (`--boards '' --no-blend`, as a gate builds; CPU 635.9 s B2s, 648.5 s B3s):

| check | B2 (local hull, Nelder-Mead) | **B2s (local hull, stable fit)** | B3s (face5 on B2s) | pipeline-3d (ba51e43, gate base) |
|---|---|---|---|---|
| art_terminator_hair (grade) | 2.514 (FAIL) | **2.045 (WARN)** | 2.179 (WARN) | 2.308 (WARN) |
| its views f / 3q / p / back | 2.233 / 2.065 / 1.160 / 2.514 | 2.045 / 1.789 / 1.208 / 1.788 | 2.179 / 2.160 / 0.847 / 1.979 | |
| hair_piece_buns f / p / back | 0.858 / 0.856 / 0.871 (0.863) | 0.864 / 0.850 / 0.875 (0.865 PASS) | 0.864 / 0.849 / 0.875 (0.865) | 0.864 PASS |
| hair_bun_outline f / p | 0.513 / 0.347 (0.456 FAIL) | 0.544 / 0.327 (0.470 FAIL) | 0.544 / 0.324 (0.469) | 0.456 FAIL |
| hair_bun_corners | 21 | 19 | | 21 |

- B2 -> B2s: 15 checks move, all hair (the buns and what the hair's silhouettes and shading read); every other flag
  check identical. art_fragments_hair 1.242 -> 1.414 and art_outline_hair 0.712 -> 0.692 (INFO, not flags).
- The fit on the box reproduces the laptop's exactly (soft loss 0.277316 / 0.357697, the same IoUs); Nelder-Mead's bun_R
  differed 0.028 L between the two machines.
- **face5's move of the buns** (the build pairs' bun meshes): Nelder-Mead B2 -> B3 0.0266 / 0.0158 L (bun_L / R);
  stable B2s -> B3s **3.9e-8 / 5.7e-8 L**. face5's terminator move is now +0.134 (2.045 -> 2.179, same grade), carried
  by the pieces face5 reshapes (side locks, bangs), not the buns (before: +0.45 through the buns).

**The prior annealed (a7ef42e).** At 1 um every perturbation passed, but at 10 um one (the bun points' random seed 0)
took bun_L to a neighbouring minimum 0.017 L away (soft loss 0.2791 against 0.2773; `charkit/out/bunstab/diag3.py`):
the 9-parameter stages agreed, the second stage (the loops freed from their defaults) forked in its first long
steps. BUN_SOFT_ANNEAL (10, 3, 1): each softness step's prior in BUN_SOFT_PRIOR, strong while the loss is coarse, in
both stages. At 10 um then all 20 perturbations move the buns under 5.4e-6 L (proportional; soft losses 0.291797 /
0.354914 on every one). bun_L's minimum is now another (0.2918, the old one's 0.2773), bun_R's lower (0.3549 against
0.3577). Rebuilt on the box: B2a (a7ef42e, `charkit/out/hl_b2a`) and B3a (tmp 5f4587e,
`~/animation-pipeline-face5hl/charkit/out/hl_b3a`); stability at 1 um / 100 um / 1 mm and the unit test running
locally (`charkit/out/bunstab/stab_soft*.json`, `test_bun_fit.log`). pipeline-3d 07fa3c2 (xpbd, opt-in) merged at
d10eb65. Pre-gate (1f854d7 into 07fa3c2): PASS, 14 moved, 0 blocking.
- **Annealed variant reverted (2542d8b)**: B2a read art_terminator_hair **2.617 (grade FAIL**, back 2.617), B3a 2.61;
  hair_piece_buns 0.867, hair_bun_outline 0.467. And its full 1 um run: bun_L 5.5e-7 L, but **bun_R 0.192 L on one of
  10 perturbations**. The non-annealed fit (f3682b7: B2s) passed all 10 at 1 um (2.4e-7 L), fits bun_L better (soft
  loss 0.2773 against 0.2918; IoUs 0.874 / 0.900 / 0.916 against 0.859 / 0.899 / 0.897) and reads 2.045. Kept: f3682b7's
  fit (the revert makes hairpieces.py identical to it).
- **Open (for the next round):** the kept fit still has near-equal minima close by: 1 of 20 perturbations at 10 um
  switched bun_L's basin (0.017 L). The terminator's back view swings 1.79 (B2s) to 2.62 (B2a) between poses that fit
  the drawing equally (IoUs within 0.02): the silhouettes don't fix the bun's 3D orientation, and the terminator reads
  it. Candidates: a constraint the drawing gives on the orientation (the bun's drawn inner lines or the three-quarter
  view in the fit: bun_views has no three_quarter by default), or fewer free parameters (the loops' place and size trade
  off); the prior alone can't separate them without costing fit.
