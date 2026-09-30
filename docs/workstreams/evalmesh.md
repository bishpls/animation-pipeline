# evalmesh: subdivision and Solidify in the venv (tool/evalmesh)

Worktree `~/animation-pipeline-evalmesh`, branch `tool/evalmesh` (fast-forwarded to pipeline-3d ae7fd45). Michael's
call J: Subdivision Surface and Solidify leave Blender. They are computed at rest in the venv and then skinned (the
game-engine way; the VRM export needs the final meshes anyway). Motion QA checks the bends at extreme poses against
Blender's per-frame modifiers. The outline's inverted hull stays render-time (call I). This is docs/GEOM_TRUTH.md
rollout step 7, with 7b decided: "own it".

## Milestones (each lands separately, gated)
- **M1 (7a): the winding decided venv-side.** Exit: evaldrift shows the sleeves' evaluated shell within GEOM_TOL, and
  no other piece moves.
- **M2: subdivision exact.** `bodyeval.subdivide` matches Blender's Subdivision Surface (OpenSubdiv) on the skin (level
  1 viewport, 2 render) and the garments (level 1), per piece: max and mean vertex error, face counts. Exit: within
  1e-4 L everywhere, or each residual explained.
- **M3: Solidify venv-side.** Exit as M2.
- **M4: the switch.** The build writes venv-made subdivided and solidified meshes at rest. Blender keeps Armature, Mask
  and the outline. QA measures a venv-made bundle. VRM carries the final meshes. Motion QA at extreme poses against
  Blender's per-frame modifiers, with numbers.

## The lab (measure first): `charkit/evalmesh.py`
A piece is a mesh (winding as given), optional corner UVs, edge creases and a modifier stack. `evalmesh.blender(pieces)`
runs the stack in a local headless Blender 5.2.2, the boxes' version (infra/gcp/build.env). `evalmesh.ours(p)` runs our
port. `evalmesh.compare` measures ours against Blender per vertex: nearest-vertex matching that must be one to one,
faces matched by vertex set, winding, and UV per corner. `evalmesh.shapes()` gives synthetic pieces: a smooth cube,
sharp and semi-sharp creases (a ring, one edge, an L), an open grid (borders and corners), UV seams, n-gons, triangles
and two levels. A run takes about 1.5 s.

## Findings
**Winding (M1), on the baseline build `charkit/out/evalmesh/base_clawd` (box, ae7fd45):**
- Blender (bmesh recalc) flips whole pieces: 14 of 18 pieces fully, the bow 456 of 942. Its reversal keeps the first
  corner ([v0, vn-1, ..., v1]). The old port reversed fully ([::-1]), so its child quads started elsewhere.
- On this head the old port and Blender agree in orientation on every piece. The sleeves' 0 of 1,856 came from an
  older sleeve (before hull-limbs) and doesn't reproduce: evaldrift's evaluated sleeves are 1.85e-6 L.
- The new rule (`charkit/geom/wind.py`): consistent per manifold region, then the sign of the region's flux
  Σ area (c − centre)·n. It gives Blender's faces tuple for tuple on all 18 pieces (0 differ). Conditioning
  |flux|/Σ|terms| is 0.68 at the lowest (a bow region), 0.85 on the collar, and 0.95 to 1.0 on the rest, so it is
  robust, unlike the old one-vertex heuristic.

**Subdivision (M2), in the lab:** OpenSubdiv as Blender 5.2 runs it. The rules, established by measurement:
- crease c becomes sharpness 10·c² (c = 0.5: 10c² matches to 2e-7, 10c is 0.1 off);
- boundaries: 'ALL' is EDGE_ONLY (open edges infinitely sharp);
- UVs: PRESERVE_BOUNDARIES smooths inside and keeps seams and borders linear, evaluated at the limit (seams match to
  3.3e-7).
- **The limit is evaluated at the adaptive isolation level (quality 3), not the true limit.** A vertex's value is the
  limit mask applied to the mesh refined to level 3. Any sharpness still semi-sharp at that level counts as smooth
  (infinite stays sharp). A border vertex with one face (a quad's corner on an open border) takes its level-3
  position (the end cap's corner). This matches darts, semi-sharp creases of 0.7 and 0.9, and borders to about 2e-7.
  The true limit is off by 0.03 to 0.07 on these shapes. Smooth extraordinary vertices and infinitely sharp creases
  are level-independent, so the old ports got those right.
- The old ports (`bodyeval.subdivide`, `charkit/subdiv.py`) get smooth, n-gon and triangle shapes to 1.5e-7. They miss
  creases (bodyeval.subdivide ignores them: 0.03 to 0.6 off) and open-border corners (0.004).

**UVs:** Blender's converter (subdiv_converter_mesh) groups a vertex's corners into one UV value when they sit within
STD_UV_CONNECT_LIMIT (1e-4) of the group's first corner *and* share its UV winding. The winding is cross_poly_v2 > 0:
the trapezium rule in float32, summed from the last corner's edge. The float32 detail matters. The boots' sole caps
have zero-area UV triangles (the trapezium gives exactly 0 in float32 and -1e-16 in float64), and deciding them in
float64 put 800 boot corners 0.18 off. With the float32 rule the boots, skin and masked skin match to 1.6e-6.

**Vertex groups through Subsurf:** Blender carries vertex data linearly: kept at the vertices, the mean of the ends at
an edge's point, the mean of the corners at a face's (`subsurf._carry`, 4.7e-8 against Blender). Not the limit
stencil. Weights above 1 are clamped when added to a group.

**Solidify, as Blender lays it out** (offset -1, the lab's strips): the input vertices first and unmoved, then the
copies moved t in along Blender's vertex normals (unit polygon normals weighted by corner angle). Then the input
polygons, the copies reversed with the first corner kept, and a rim quad (b, a, a+n, b+n) per open edge a→b (rim
faces in Blender's edge order; ours in loop order, which only reorders faces). Rim UVs are [ub, ua, ua, ub].
edge_crease_outer goes on the input's open edges, _inner on the copies', _rim on the cross edges (v, v+n). The old
port had the halves swapped and the copies fully reversed: the positions were right, the winding inside out.

**The build's pieces** (`python -m charkit evalmesh build charkit/out/evalmesh/base_clawd`, report
`charkit/out/evalmesh/lab_base/evalmesh.md`). Ours (geom.subsurf, geom.solidify) against local Blender on the same
input:

| piece | max L | mean L | faces, winding, first corner | UV max |
|---|---|---|---|---|
| skin (level 1) | 9.1e-6 | 3.0e-7 | all equal | 7.2e-7 |
| skin, masked | 3.7e-6 | 3.4e-7 | all equal | 7.2e-7 |
| garments, Solidify + Subsurf (16 pieces) | 9.9e-6 (shorts), 1.1e-5 (collar) | ≤ 4.7e-7 | all equal | ≤ 1.5e-6 |
| garments, Subsurf alone on Blender's Solidify | ≤ 9.9e-6 | ≤ 4.4e-7 | all equal | ≤ 1.5e-6 |
| garments, Solidify alone | ≤ 4.6e-7, collar 2.3e-5 | ≤ 1.3e-7 | all equal, vertex order identical | ≤ 6.6e-8 |
| boots, bow (Subsurf only) | ≤ 1.5e-6 | ≤ 4.5e-7 | all equal | ≤ 1.6e-6 |

Local Blender against the box's bundle (ARM against x86, same 5.2.2): ≤ 1.9e-6 L, except the collar at 1.1e-5.
The old evaluator (evaldrift, box) had the masked skin 0.0088 L off.

Residuals, explained:
- The largest subdivision errors sit on the skin's and shorts' highest-valence poles (valence 72, 48 and 36, and the
  edges next to them): 9e-6 L = 2.3 µm. OpenSubdiv evaluates the end-cap weights there in float32; ours is float64.
- The collar's Solidify (2.3e-5 L) is Blender's float32 vertex normal at a near-degenerate corner. Box and laptop
  Blender disagree there by 1.1e-5 themselves.
- Everything is 10x or more under GEOM_TOL (1e-4 L).

## Log
- 2026-09-30: merged pipeline-3d ae7fd45 (fast-forward). Baseline box build `charkit/out/evalmesh/base_clawd`
  (--boards views --no-blend) and `evaldrift --stages` on it: 0 of 110 checks drift. Stage drift: only the evaluated
  masked skin, 0.00879 L nearest-vertex (mean 1.4e-5), which is the subdivision port. The evaluated garments are within
  1.1e-5 L (the collar), and the sleeves 1.85e-6.
- M1 code: `charkit/geom/wind.py` (orient, reverse, consistent, flux). `geomstage._wound` winds `_object`'s faces and
  corner UVs in the recording and records `wound=True`. `garments._object(wound=)` takes them as given, and the
  in-Blender path winds with the same function. bmesh's recalc and `bodyeval.recalc_normals` are gone, and
  `Part.subdivided` uses the recorded faces. Tests: `charkit/tests/test_wind.py`; test_geomstage and test_bodyeval
  updated.

- **M1 result** (box, 82f2c5d, `charkit/out/evalmesh/m1_clawd`): evaldrift --stages shows 0 of 110 checks drifting.
  The evaluated sleeves are 1.85e-6 / 1.35e-6 L and every garment is within 1.1e-5 L. The only stage drift is the
  skin's subdivision (M2). boarddiff base_clawd -> m1_clawd: 375 QA checks identical, 22 of 24 images identical (face_030
  max 4/255 on a few pixels, sheet_views max 1). Bundle to bundle, every garment's raw loops are identical. The
  evaluated meshes are the same geometry (0 L; the collar 1.2e-7 L on one vertex) with the same winding, first corners
  and UVs. Only their vertex order changed: BMesh's to_mesh no longer reorders the edges.
- Merged pipeline-3d 4de65ab (tool/face4) at 2ac1653.
- **M1 gate: PASS under K** (73be408 into 4de65ab; report `charkit/out/gate/gate_tool-evalmesh_73be408_into_4de65ab.md`).
  No check changed, all 56 test files ok, build CPU 819.9 -> 934.6 s (1.14x), Blender and QA 315.7 -> 283.1 s.
  **M1 is mergeable at 73be408**; the commits after it are notes only.

- **M2 in the evaluator** (box: a build of the merged tree `charkit/out/evalmesh/m2_clawd`, evaldrift --stages with
  the M2 evaluator). 0 of 110 checks drift. The masked skin's subdivision went from 0.00879 L nearest-vertex (mean
  1.4e-5) to **3.42e-6 L (mean 3.6e-7)**. The garments are unchanged, ≤ 1.1e-5 L. One new stage drift, crab_1 2.05e-4
  L, isn't this branch's: the M1 evaluator on the same build shows it too (`m2_drift_M1evaluator.md`). It came with
  face4's merge (the accessories sit on the hair volume, step 2's two volume ports).
- **M3 in the evaluator** (local, the evaluator's own garment Parts against m2_clawd's bundle, per vertex one to
  one): every piece ≤ 1.1e-5 L (the collar), all faces, windings and first corners Blender's (the old port had every
  shell's winding inside out).

- **M3 evaldrift** (box, 16c0040's evaluator on m2_clawd): 0 of 110 checks drift. The stage drift is only crab_1
  (face4's, above). Masked skin 3.42e-6 L, garments ≤ 1.1e-5 L. Commits: M2 9ee0a9e, M3 16c0040. The gate on
  M2 and M3 together follows: the evaluator isn't in the build's geometry, so the QA should not move.

- **M4 groundwork: `evalmesh.finalize(o)`**, a recorded garment's final mesh at rest (geom.solidify, then
  geom.subsurf with the carried weights; materials through the parents). On m2_clawd, against the build's bundle:
  every piece ≤ 9.8e-6 L per vertex (one to one), UVs ≤ 1.2e-6 per corner, materials 100% per face, winding and
  first corners 100%. The weights, rounded as `_object` rounds them, match Blender's own evaluated vertex groups
  (lab, local Blender, Solidify + Subsurf) to 8e-8. The lab carries vertex groups now (`piece['groups']`). Not wired
  into the build yet.

- **Merged pipeline-3d d60486a** (garments3: call L's creased rims, the garment changes, the QA per-piece crops). One
  conflict, bodyeval: both sides changed the evaluator's Solidify and Subdivision. Kept: this branch's exact ports
  (geom.solidify, geom.subsurf) and `Part.solid_settings`, which already carries `edge_crease_outer/_inner/_rim` to
  geom.solidify; its creases go to geom.subsurf as OpenSubdiv sharpness 10·c² (call L's crease 1 is sharpness 10,
  infinitely sharp). Kept from garments3: `Part.subdiv = 0` for a piece built without a Subdivision Surface, and the
  QA's `min(level, subdiv)`. garments3's hand-rolled `sharp=`/`with_sharp` in the old ports went with them;
  `test_creased_rims_stay_flat_and_square` now runs on the exact API with the same assertions (24 loop edges, no cross
  edge, crease 1 infinitely sharp, every vertex at z 0, t/2 or t, 48 child sharp edges, uncreased a bead) and checks
  the evaluator's wrapper gives the same mesh.
- The lab gained a garment shell (`grid_shell`, `grid_shell_rim_creased`: Solidify 0.08, then Subsurf, UVs with a
  seam). Against local Blender: 1.0e-6 / 9.9e-7 L, all 232 faces, windings and first corners equal, UVs 3.3e-7.
  garments3's port gives the same positions there (9.9e-7 L: crease 1 is level-independent); it differed in winding.
- **Gate on the merge: PASS under K** (f35db5a into d60486a; `charkit/out/gate/gate_tool-evalmesh_f35db5a_into_d60486a.md`):
  0 items, no check changed, 64 test files ok, build CPU 717.8 -> 827.2 s (1.15x). Superseded by the fixes below.
- **evaldrift --stages on the merge** (box build `charkit/out/evalmesh/merged_clawd`, f35db5a): 0 of 110 checks drift,
  but three stage rows new with garments3 (the first report kept as `drift_oldmeasure.md`):
  - overskirt_panel_L/R evaluated: n 7526 against 2072. The panels have no Subsurf (garments3's `Part.subdiv = 0`);
    evaldrift subdivided every garment once. Fixed in evaldrift (each Part at its own level, as the QA's Geometry
    does). Then 0.01 L, n equal: a real miss, below.
  - the masked skin: n 49156 against 49251, 0.199 L. Blender's Mask keeps kept vertices whose faces it drops, and
    Subsurf carries them: 95 loose vertices (44 isolated, 51 loose-edge points) under the jacket, 0.02-0.2 L from any
    drawn vertex. evaldrift compared all of Blender's vertices with only our on-face ones. Remeasured on-face on both
    sides, the loose count and the all-vertex measure still in the row. Then 0.0107 L, n equal: a real miss, below.
- **Solidify, a loose vertex** (the template flaps' panels have 126): Blender's vertex normal has a fallback. Where the
  angle-weighted sum has no length, the normalised position. The copy moves t along it (measured to 1.2e-7 L; ours
  left it in place: exactly t = 0.01 L off). `geom.solidify.vertex_normals` takes the fallback: the panels 0.01 ->
  5.7e-7 L, vertex order identical, every face, winding and first corner equal.
- **Subsurf after the Mask, loose edges** (51 on the masked skin): Blender's subdiv converter marks both ends of a loose
  edge infinitely sharp, so a face vertex with a dangling edge subdivides as a corner. The evaluator's masked skin takes
  them as vertex creases (`bodyeval.mask_loose_edges`, `mask_corners`; `Part.corners`): 0.0107 L -> 3.1e-6 L (mean
  3.4e-7) against the bundle. The lab: pieces take `loose_edges` (Blender gets them through bmesh: `edges.add` crashes
  5.2 on the skin), compared on-face; `grid_loose_edge` 9.2e-7 L (0.039 L without the rule), level 2 1.3e-6,
  `grid_shell_loose_vertex` 9.8e-7; `skin_masked` with the Mask's loose edges 3.1e-6 L against local Blender.

- **evaldrift --stages at 1939469** (merged_clawd, the box): 0 of 110 checks drift. Stage drift: only crab_1
  (2.05e-4 L, face4's, above). Masked skin 3.8e-6 L on-face (n 49156/49156; the build's 95 loose vertices reported,
  0.199 L with them), overskirt panels 5.6e-7 L, every garment ≤ 1.2e-5 L (the collar).
- **Gate: PASS under K** (1939469 into pipeline-3d 4007276, infra3 run 3; report
  `charkit/out/gate/gate_tool-evalmesh_1939469_into_4007276.md`): 0 items, no check changed, 65 test files ok, build
  CPU 758.7 -> 751.6 s (0.99x). 4007276 merges into the branch cleanly (the gate's own merge). **M2+M3 mergeable at
  1939469**; the commits after it are notes only.

- **M2+M3 merged** into pipeline-3d (81ffcb1); pipeline-3d 25b1936 (infra-auth: box control on a service account,
  `CLOUDSDK_CONFIG=$HOME/.config/charkit/gcloud` in every box shell) fast-forwarded in. Coordinator's go-ahead for M4:
  skin weights linear (Blender's), the panels' loose vertices kept as Blender keeps them, charkit/subdiv.py left to
  tool/face5.

## M4, the switch (in progress)
- `geomstage.finalize(P)`: every recorded garment with a Solidify or Subsurf gets its final mesh at rest
  (`evalmesh.finalize`) in its `_object` call (`final=True`); its 'thick'/'sub' events go; where they stood, its
  object gets `ck_shell` (the outline's cap: `shade.shell_of` reads it) and `ck_final_levels`. The recording as made
  stays in `meta['coarse_events']` (`pieces(P, coarse=True)`: the lab, motion QA). `garments_product` and the
  evaluator's `garment_piece` finalize, so the evaluator's garments are the build's meshes by construction (no
  solid, no subdivision left in their Parts).
- Weights: `garments.group_weights` (3 decimals, 1e-4 and under dropped, clamped to 1) is what `_object` gives the
  coarse vertex groups and what finalize carries; a final object's weights go in as carried (not rounded again).
  `_object` sets corner UVs, smooth flags and material indices with foreach_set (the final meshes are 8x larger).
- On merged_clawd's product: finalize 0.9 s for 19 pieces, the product 13 MB (save 1.0 s). Against the bundle's
  Blender-evaluated meshes: all 19 one to one, ≤ 1.2e-5 L (the collar), every face, winding and first corner
  equal, UVs ≤ 1.2e-6.

## Next
- M4, the switch (plan):
  1. Garments first; they're already a venv product. The mesh content is done and measured (`evalmesh.finalize`,
     above). What's left is wiring it into the product. After `garments_geom` records build(), a venv pass gives each
     `_object` its final mesh at rest: geom.solidify then geom.subsurf at the modifier's `levels` (garments: 1 for
     viewport and render). Polygons come as (loopv, counts), per-corner UVs from subsurf, mat_idx through `parent`,
     and weights copied to the Solidify copies and carried linearly through Subsurf, as Blender carries vertex data.
     The pass drops the 'thick' and 'sub' mod events. Armature ('rig', inside _object) and the outline stay.
  2. The outline's cap reads the shell's thickness from the 'thick' SOLIDIFY (`shade.shell_of`). With the modifier
     gone it needs the thickness as a custom property the recording sets (`ob['ck_shell']`).
  3. The bundle's 'raw' variant of a garment becomes the final mesh. Checks that read raw (poke-through, open edges)
     change measure: score them both ways (the gate's 2x2). The evaluator's Part then has no solid and no subdivision:
     exact by construction.
  4. The skin waits for rollout step 4 (the character product). It carries shape keys, two UV layers, the Mask and
     render level 2. geom.subsurf is numpy-only, so Blender's character stage could call it meanwhile, but GEOM_TRUTH
     wants it venv-side.
  5. Motion QA: at extreme poses, Blender per frame (Armature, then Solidify and Subsurf on the posed coarse mesh)
     against the engine way (Armature on the final rest mesh). Per-vertex distances per piece, with linear weights
     (Blender's own) and limit-stencil weights as the two candidates.
- Follow-ups: `charkit/subdiv.py` (faceeval, code_base, headfit) is a third Catmull-Clark. Its `carry` puts vertex
  weights through the limit, but Blender carries them linearly (measured). Delegating it to geom.subsurf changes
  faceeval only near its crop border and in carried weights, so do it with tool/face.
